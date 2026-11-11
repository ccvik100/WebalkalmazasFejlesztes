# =============================================================
# OKTATÓI MAGYARÁZAT – Configure.ps1
# A megjegyzések bemutatják a PowerShell parancsok célját.
# Az eredeti futtatási utasítások nincsenek megváltoztatva.
# =============================================================
# TANANYAG – A paraméterekkel testreszabható a tenantazonosító, az alkalmazás neve és az OmegaAI címe; a default helyi fejlesztésre mutat.
param([string]$TenantId = 'meetingnotes', [string]$ClientName = 'MeetingNotes teszt', [string]$OmegaUrl = 'http://127.0.0.1:8768')
# TANANYAG – Hiba esetén azonnal megszakítja a konfigurálást; így nem mentünk félig elkészült kulcsfájlt.
$ErrorActionPreference = 'Stop'
# TANANYAG – A tenantazonosító korlátozott karakterkészlete előre egységes URL-eket és elválasztott adattárat biztosít.
if ($TenantId -cnotmatch '^[a-z][a-z0-9_-]{2,63}$') { throw 'A TenantId kisbetűvel kezdődjön, 3-64 karakter legyen: a-z, 0-9, - vagy _.' }
# TANANYAG – A szkript helyéből megkeresi a projekttörzset, függetlenül a PowerShell aktuális mappájától.
$Root = Split-Path -Parent $PSScriptRoot
# TANANYAG – A csak szerveren lévő titkos konfiguráció pontos célfájlját állítja elő.
$Secrets = Join-Path $Root 'private\meetingnotes.secrets.json'
# TANANYAG – A logs könyvtár a diagnosztikához tartozó külön mappa.
$LogDir = Join-Path $Root 'logs'
# TANANYAG – A hiányzó private és logs mappát létrehozza, a parancs kimenetét elrejti.
New-Item -ItemType Directory -Force (Split-Path -Parent $Secrets), $LogDir | Out-Null

# TANANYAG – A New-Secret kriptográfiailag véletlenszerű kliens-API-kulcsot generál.
function New-Secret {
    # TANANYAG – 32 bájtos, azaz 256 bites véletlen kulcs alapanyagot készít elő.
    $bytes = New-Object byte[] 32
    # TANANYAG – A .NET véletlenszám-generátort használja, nem a könnyen kitalálható időbélyeget.
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    # TANANYAG – A generátor feltölti a bájttömböt, végül felszabadítjuk az erőforrást.
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    # TANANYAG – Minden bájtot két hexadecimális karakterré alakít, így 64 karakteres titok készül.
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
# TANANYAG – Külön függvény gondoskodik a privát JSON biztonságos mentéséről.
function Save-Settings($object) {
    # TANANYAG – A MeetingNotes objektum a .NET konfigurációs kötő által elvárt JSON-struktúrába kerül.
    $json = @{ MeetingNotes = $object } | ConvertTo-Json -Depth 20
    # TANANYAG – UTF-8 BOM nélkül írja a fájlt, hogy a konfigurációs beolvasás megbízható legyen.
    [System.IO.File]::WriteAllText($Secrets, $json, (New-Object System.Text.UTF8Encoding($false)))
    # TANANYAG – Megkísérli a fájl NTFS-jogosultságát adminisztrátorhoz és aktuális fiókhoz kötni; sikert figyelni kell.
    try { icacls $Secrets /inheritance:r /grant:r "$($env:USERNAME):F" '*S-1-5-32-544:F' | Out-Null } catch { Write-Warning 'NTFS jogosultság ellenőrzése szükséges.' }
}
# TANANYAG – Megjelöli a különösen érzékeny konfigurálási művelet kezdetét.
Write-Host '=== MeetingNotesAPI - elso konfiguracio ===' -ForegroundColor Cyan
# TANANYAG – Ellenőrzi a telepített OmegaAI főkulcs-fájljának helyét.
if (-not (Test-Path 'C:\OmegaAI\config\api-key.txt')) {
    # TANANYAG – Hiányzó OmegaAI esetén egyértelmű hibát dob, nem hoz létre semmit találomra.
    throw 'Hiányzik: C:\OmegaAI\config\api-key.txt. Előbb az OmegaAI-t telepítsd.'
}
# TANANYAG – Beolvassa a meglévő főkulcsot, a fölösleges szóközöket/újsorokat levágva.
$master = ([IO.File]::ReadAllText('C:\OmegaAI\config\api-key.txt')).Trim()
# TANANYAG – A túl rövid kulcsot elutasítja, mert ilyen véletlen kulcs nem tekinthető megfelelőnek.
if ($master.Length -lt 40) { throw 'OmegaAI főkulcs hiányzik vagy túl rövid.' }
# TANANYAG – Az OmegaAI életjelének próbája kivételkezelő blokkban fut.
try {
    # TANANYAG – Rövid HTTP GET ellenőrzi, hogy az OmegaAI szolgáltatás válaszol-e.
    $live = Invoke-RestMethod -Method Get -Uri "$($OmegaUrl.TrimEnd('/'))/health/live" -TimeoutSec 10
    # TANANYAG – A sikeres válasz állapotát konzolra írja.
    Write-Host "[OK] OmegaAI válaszol: $($live.status)"
# TANANYAG – Ha nem fut a háttérszolgáltatás, a beállítás leáll és megmondja a teendőt.
} catch { throw "OmegaAI nem érhető el: $OmegaUrl. Előbb indítsd el a 03_INDITAS.bat fájlt." }

# TANANYAG – A korábbi konfiguráció tárolója kezdetben üres.
$existing = $null
# TANANYAG – Ha már van titkos JSON, újrafelhasználjuk, nem írjuk felül vakon a kulcsokat.
if (Test-Path $Secrets) { $existing = Get-Content $Secrets -Raw | ConvertFrom-Json }
# TANANYAG – Meglévő beállítás esetén abból indulunk ki; új telepítésnél létrehozzuk a kezdeti struktúrát.
$cfg = if ($existing) { $existing.MeetingNotes } else {
    # TANANYAG – A PowerShell custom object megőrzi az összetartozó konfigurációs mezőket.
    [pscustomobject]@{
       # TANANYAG – A belső OmegaAI kapcsolat alapadatait összeállítjuk.
       OmegaAi = [pscustomobject]@{ BaseUrl = $OmegaUrl; ApiKey = $master }
       # TANANYAG – A feltöltési korlát kezdetben 100 MB; a szerver oldali szabályok ezzel számolnak.
       MaxUploadMb = 100
       # TANANYAG – A Swagger tesztfelület az első fejlesztéshez engedélyezett.
       EnableSwagger = $true
       # TANANYAG – A kliensek listája új konfigurációnál üres, még nincs hozzáférés.
       Clients = @()
    }
}
# TANANYAG – A cél OmegaAI-címet frissíti a konfigurációban.
$cfg.OmegaAi.BaseUrl = $OmegaUrl
# TANANYAG – A frissen beolvasott OmegaAI főkulcsot beállítja a saját szerverhez.
$cfg.OmegaAi.ApiKey = $master
# TANANYAG – Megkeresi, létezik-e már ez a tenant a helyi klienslistában.
$selected = @($cfg.Clients | Where-Object { $_.TenantId -eq $TenantId })
# TANANYAG – Ha létezik, nem generálunk új kulcsot, mert az a korábbi tesztklienst kizárhatná.
if ($selected.Count -gt 0) {
    # TANANYAG – A kiírás jelzi, hogy a régi konfigurációt megőriztük.
    Write-Host "[OK] Már létező alkalmazás: $TenantId. Nem forgatunk kulcsot."
# TANANYAG – Új tenantnál külön regisztrációt kell kérni az OmegaAI-tól.
} else {
    # TANANYAG – A tenant létrehozását a központi főkulcs hitelesíti.
    $headers = @{ 'X-Api-Key' = $master }
    # TANANYAG – A regisztrációs JSON egy egyedi tenant_id-t és emberi labelt küld.
    $body = @{ tenant_id=$TenantId; label=$ClientName } | ConvertTo-Json
    # TANANYAG – A hálózati regisztráció és kulcsfogadás try/catch blokkban van.
    try {
        # TANANYAG – POST /v1/tenants új elkülönített hangprofiltárat kér az OmegaAI-tól.
        $tenant = Invoke-RestMethod -Uri "$($OmegaUrl.TrimEnd('/'))/v1/tenants" -Method POST -Headers $headers `
             # TANANYAG – UTF-8 kódolású JSON-t küld, 30 másodperces hálózati időlimittel.
             -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 30
        # TANANYAG – Az OmegaAI válaszában generált tenantkulcsot szövegként tárolja.
        $tenantKey = [string]$tenant.tenant_api_key
        # TANANYAG – Ha a szerver nem adott megfelelő kulcsot, nem lehet biztonságosan folytatni.
        if ($tenantKey.Length -lt 40) { throw 'A tenant létrehozása nem adott megfelelő kulcsot.' }
    # TANANYAG – Régi tenant/409 vagy hálózati hiba esetén kerül ide a vezérlés.
    } catch {
        # TANANYAG – A figyelmeztetés nem állítja biztosra, hogy a tenant létezik; lehet más hiba is.
        Write-Warning 'A tenant már létezhet (409), vagy az OmegaAI hibát adott.'
        # TANANYAG – Egy már meglévő tenant korábbi kulcsát az adminisztrátornak kell beírnia.
        $tenantKey = Read-Host "Add meg a(z) $TenantId tenant korábbi X-Tenant-Key értékét (nem látszik a korábbi adatbázisból)"
        # TANANYAG – A hibás vagy rövid kulcsot elutasítja.
        if ($tenantKey.Length -lt 40) { throw 'Érvénytelen/hiányzó tenantkulcs; használj új, egyedi TenantId-t.' }
        # TANANYAG – Visszaellenőrzi a kézzel megadott tenantkulcs jogosultságát.
        try {
            # TANANYAG – GET /persons sikeres válaszával ellenőrzi, hogy a főkulcs és a tenantkulcs együtt érvényes.
            Invoke-RestMethod -Uri "$($OmegaUrl.TrimEnd('/'))/v1/tenants/$TenantId/persons" -Headers @{ 'X-Api-Key' = $master; 'X-Tenant-Key' = $tenantKey } -TimeoutSec 15 | Out-Null
        # TANANYAG – Ha a jogosultsági próba elbukik, megszakítja a mentést.
        } catch { throw 'A megadott tenantkulccsal sem sikerült a jogosultsági próba.' }
    }
    # TANANYAG – Új alkalmazásobjektumot készít: név, saját klienskulcs, OmegaAI tenantazonosító és tenantkulcs.
    $newClient = [pscustomobject]@{ Name=$ClientName; ClientKey=(New-Secret); TenantId=$TenantId; TenantKey=$tenantKey }
    # TANANYAG – Az új alkalmazást a korábbi kliensek mellé fűzi, a régieket megtartja.
    $cfg.Clients = @($cfg.Clients) + @($newClient)
    # TANANYAG – Elmenti a teljes konfigurációt a private könyvtárba.
    Save-Settings $cfg
    # TANANYAG – Csak a siker tényét írja ki, a titkos kulcsértékeket nem.
    Write-Host '[OK] Tenant és MeetingNotesAPI klienskulcs elmentve a privát konfigurációba.' -ForegroundColor Green
}
# Kulcs nem kerül a telepítőnaplóba. A kulcs megtekintése privát teszteléshez:
# TANANYAG – Tájékoztat az elmentett privát konfiguráció teljes elérési útjáról.
Write-Host "Beállítás: $Secrets"
# TANANYAG – A Swagger teszthez szükséges kulcs a privát fájlban olvasható, nem publikus dokumentációban.
Write-Host 'Swagger teszthez a X-Meeting-Key értéket itt találod, csak helyben:'
# TANANYAG – Csak a helyben futtatandó PowerShell-lekérdező parancsot jeleníti meg.
Write-Host '  (Get-Content .\private\meetingnotes.secrets.json -Raw | ConvertFrom-Json).MeetingNotes.Clients[0].ClientKey'
# TANANYAG – Megkülönbözteti a kliens Meeting kulcsát az OmegaAI belső titkaitól.
Write-Host 'Kezelés: külön .NET API kulcs, semmilyen OmegaAI kulcs nem kerül a kliensekhez.'
