#requires -Version 5.1
<#################################################################################
MeetingNotesAPI - biztonsagos helyreallitas, ha a korabbi tenantkulcs elveszett.
A regi tenantot es a hangmintait NEM torli, NEM modositja.
- Ha az OmegaAI nem fut, a C:\OmegaAI\03_INDITAS.bat segitsegevel elinditja.
- Uj tenantot hoz letre: meetingnotes2, meetingnotes3, ...
- Uj X-Meeting-Key erteket general es mindket kulcsot a private JSON-ba menti.
- A regi JSON tartalmat megorzi, es helyben biztonsagi masolatot keszit.
- Az OmegaAI fokolcsat NEM irja felul; csak beolvassa.
#################################################################################>

param(
    [string]$OmegaUrl = 'http://127.0.0.1:8768',
    [string]$TenantPrefix = 'meetingnotes',
    [switch]$NoAutoStart
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$SecretsDir = Join-Path $Root 'private'
$SecretsFile = Join-Path $SecretsDir 'meetingnotes.secrets.json'
$OmegaRoot = 'C:\OmegaAI'
$MasterFile = Join-Path $OmegaRoot 'config\api-key.txt'
$StartBat = Join-Path $OmegaRoot '03_INDITAS.bat'
$Base = $OmegaUrl.TrimEnd('/')

function Abort([string]$Message) {
    throw $Message
}

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) }
    finally { $rng.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Test-OmegaAi {
    try {
        $live = Invoke-RestMethod -Method Get -Uri "$Base/health/live" -TimeoutSec 3 -ErrorAction Stop
        return ([string]$live.status -eq 'running')
    } catch { return $false }
}

function Get-HttpStatus($record) {
    try { return [int]$record.Exception.Response.StatusCode }
    catch { return 0 }
}

function Save-Secrets($cfg) {
    if (-not (Test-Path $SecretsDir)) {
        New-Item -ItemType Directory -Path $SecretsDir -Force | Out-Null
    }
    $json = @{ MeetingNotes = $cfg } | ConvertTo-Json -Depth 20
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $tmp = Join-Path $SecretsDir ('.meetingnotes.secrets.' + [guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllText($tmp, $json, $utf8)

    try {
        if (Test-Path $SecretsFile) {
            $backups = Join-Path $SecretsDir 'backups'
            New-Item -ItemType Directory -Path $backups -Force | Out-Null
            $stamp = (Get-Date).ToString('yyyyMMdd_HHmmss_fff')
            $backupPath = Join-Path $backups "meetingnotes.secrets.$stamp.$([guid]::NewGuid().ToString('N').Substring(0,6)).json"
            Copy-Item -LiteralPath $SecretsFile -Destination $backupPath -ErrorAction Stop
            Write-Host '[OK] Korabbi privat konfiguracio biztonsagi mentese elkeszult.' -ForegroundColor Green
        }
        Move-Item -LiteralPath $tmp -Destination $SecretsFile -Force -ErrorAction Stop
    }
    finally {
        if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    }
}

try {
    Write-Host '=== MeetingNotesAPI - biztonsagos ujrakonfiguralas ===' -ForegroundColor Cyan
    if (-not (Test-Path $MasterFile)) { Abort "Nem talalhato az OmegaAI fokolcs: $MasterFile" }
    $master = [System.IO.File]::ReadAllText($MasterFile).Trim()
    if ($master.Length -lt 40) { Abort 'Az OmegaAI fokolcs ures vagy ervenytelen.' }
    if ($TenantPrefix -cnotmatch '^[a-z][a-z0-9_-]{2,40}$') {
        Abort 'A TenantPrefix 3-40 karakteres, kisbetuvel kezdodo azonosito legyen.'
    }

    if (-not (Test-OmegaAi)) {
        Write-Host '[INFO] Az OmegaAI most nem valaszol a 8768-as porton.' -ForegroundColor Yellow
        if ($NoAutoStart) { Abort 'Inditsd el kulon a C:\OmegaAI\03_INDITAS.bat programot, majd probald ujra.' }
        if (-not (Test-Path $StartBat)) { Abort "Hianyzik az OmegaAI indito BAT: $StartBat" }
        # Ha valami mar hallgat a porton, NE inditsunk ra masodik szervert.
        $occupied = Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue
        if ($occupied) {
            Abort 'A 8768-as port foglalt, de a /health/live nem valaszol. Ellenorizd a futo OmegaAI ablakot; nem inditok masodik peldanyt.'
        }
        Write-Host '[INFO] OmegaAI inditasa kulon konzolablakban ...' -ForegroundColor Cyan
        Start-Process -FilePath $env:ComSpec -ArgumentList @('/k', 'call "C:\OmegaAI\03_INDITAS.bat"') -WorkingDirectory $OmegaRoot | Out-Null
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            if (Test-OmegaAi) { $ready = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { Abort 'Az OmegaAI nem indult el vagy nem erheto el. Nezd meg a megnyilt OmegaAI konzolablak hibauezenetet.' }
    }
    Write-Host '[OK] OmegaAI elerheto: /health/live = running' -ForegroundColor Green

    $headers = @{ 'X-Api-Key' = $master }
    # A lista egyben ellenorzi, hogy a fokolcs jogosult-e tenantok kezelesere.
    try {
        $registered = @(Invoke-RestMethod -Method Get -Uri "$Base/v1/tenants" -Headers $headers -TimeoutSec 15 -ErrorAction Stop)
    }
    catch {
        $statusCode = Get-HttpStatus $_
        Abort "Az OmegaAI tenant-regiszter nem elerheto vagy elutasitja a fokolcsot. HTTP: $statusCode. Ellenorizd az OmegaAI v1.6 verziot es a fokolcsot."
    }

    $oldCfg = $null
    if (Test-Path $SecretsFile) {
        try {
            $oldJson = [System.IO.File]::ReadAllText($SecretsFile)
            $oldCfg = ($oldJson | ConvertFrom-Json -ErrorAction Stop).MeetingNotes
            if (-not $oldCfg) { Abort 'A letezo privat konfiguracioban nem talalhato a MeetingNotes szakasz.' }
        }
        catch { Abort 'A korabbi privat JSON hibas. Nem irom felul: javitsd vagy nevezd at biztonsagi mentes utan.' }
    }

    $existingIds = @($registered | Where-Object { $_ -ne $null } | ForEach-Object { [string]$_.tenant_id })
    $created = $null
    for ($suffix = 2; $suffix -le 999; $suffix++) {
        $candidate = "$TenantPrefix$suffix"
        if ($candidate.Length -gt 64) { Abort 'Az uj tenantazonosito tul hosszu.' }
        if ($existingIds -contains $candidate) { continue }
        $body = @{ tenant_id = $candidate; label = 'MeetingNotesAPI helyreallitott alkalmazas' } | ConvertTo-Json -Compress
        try {
            $created = Invoke-RestMethod -Method Post -Uri "$Base/v1/tenants" -Headers $headers `
                -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) `
                -TimeoutSec 30 -ErrorAction Stop
            break
        }
        catch {
            $statusCode = Get-HttpStatus $_
            if ($statusCode -eq 409) { continue } # Egy masik kliens idokozben lefoglalta.
            Abort "Az uj tenant regisztracioja sikertelen. HTTP: $statusCode. A regi adatokat nem modositottam."
        }
    }
    if (-not $created) { Abort 'Nem talaltam szabad tenantazonositot (meetingnotes2..999).' }
    $tenantId = [string]$created.tenant_id
    $tenantKey = [string]$created.tenant_api_key
    if ($tenantKey.Length -lt 40 -or $tenantId -cnotmatch '^[a-z][a-z0-9_-]{2,63}$') {
        Abort 'Az OmegaAI tenant-valasza hianyos. Az uj tenant esetleg letrejott; a fenti hibaval konzultalj, mielott ujra futtatod.'
    }

    $previousClients = @()
    $maxUpload = 100
    $swagger = $true
    if ($oldCfg) {
        $previousClients = @($oldCfg.Clients | Where-Object { $_ -ne $null })
        if ($oldCfg.MaxUploadMb -ge 1) { $maxUpload = [int]$oldCfg.MaxUploadMb }
        if ($null -ne $oldCfg.EnableSwagger) { $swagger = [bool]$oldCfg.EnableSwagger }
    }
    $newClient = [pscustomobject]@{
        Name = 'MeetingNotes ujraregisztralt tesztkliens'
        ClientKey = (New-Secret)
        TenantId = $tenantId
        TenantKey = $tenantKey
    }
    $cfg = [pscustomobject]@{
        OmegaAi = [pscustomobject]@{ BaseUrl = $Base; ApiKey = $master }
        Clients = @($newClient) + $previousClients # A Swagger-parancsban [0] az UJ kulcs legyen.
        MaxUploadMb = $maxUpload
        EnableSwagger = $swagger
    }
    Save-Secrets $cfg
    Write-Host "[OK] Uj, elkulonitett tenant: $tenantId" -ForegroundColor Green
    Write-Host "[OK] Kulcsok biztonsagosan elmentve: $SecretsFile" -ForegroundColor Green

    # A tulajdonoshoz tartozo API-hozzaferest ellenorizzuk. A titkos ertekek nem jelennek meg.
    try {
        $testHeaders = @{ 'X-Api-Key' = $master; 'X-Tenant-Key' = $tenantKey }
        Invoke-RestMethod -Method Get -Uri "$Base/v1/tenants/$tenantId/persons" -Headers $testHeaders -TimeoutSec 20 | Out-Null
        Write-Host '[OK] Az uj tenant hitelesitese sikeres.' -ForegroundColor Green
    }
    catch { Write-Warning 'A kulcsok mar mentve vannak, de a tenant-hitelesitesi proba nem sikerult. Ellenorizd az OmegaAI naplojat.' }

    Write-Host ''
    Write-Host 'A Swagger X-Meeting-Key lekerese a projekt gyokermappajaban:' -ForegroundColor Cyan
    Write-Host '  (Get-Content .\private\meetingnotes.secrets.json -Raw | ConvertFrom-Json).MeetingNotes.Clients[0].ClientKey'
    Write-Host 'A regi tenantok es hangmintak erintetlenek maradtak.'
    Write-Host 'A MeetingNotesAPI szolgaltatast inditsd ujra az uj konfiguracio betoltesehez.'
    exit 0
}
catch {
    Write-Host ('[HIBA] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'NEM tortent adatbazis- vagy hangminta-torles.' -ForegroundColor Yellow
    exit 1
}
