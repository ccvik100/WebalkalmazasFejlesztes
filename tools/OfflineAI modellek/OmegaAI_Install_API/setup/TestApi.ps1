param(
    [ValidateSet('QWEN','AUDIO','DIARIZE')][string]$Mode='QWEN',
    [string]$AudioFile='',
    [string]$BaseUrl='http://127.0.0.1:8768'
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$keyFile=Join-Path $Base 'config\api-key.txt'
if(-not(Test-Path $keyFile)){throw "Nincs API kulcs: $keyFile"}
$key=[IO.File]::ReadAllText($keyFile).Trim()
if($key.Length -lt 40){throw 'Az API kulcs tul rovid; ujratelepites elott javitsd.'}
$headers=@{'X-Api-Key'=$key}
if($BaseUrl -notmatch '^http://127\.0\.0\.1:\d+$'){
    throw 'A lokalis teszt csak a sajat gep 127.0.0.1 cimet fogadja el. Kulso HTTP-t ne hasznalj.'
}

# Windows PowerShell 5.1 may decode JSON HTTP responses with a legacy code page
# when charset is missing. Always read the wire bytes and decode STRICTLY as UTF-8.
# This prevents double-encoding of Hungarian text (e.g. 'kÃ©pviselÅ‘').
Add-Type -AssemblyName System.Net.Http
$script:OmegaUtf8 = [System.Text.UTF8Encoding]::new($false, $true)
function Get-OmegaUtf8Bytes {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [int]$TimeoutSec=30
    )
    $http = New-Object System.Net.Http.HttpClient
    $http.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
    $null = $http.DefaultRequestHeaders.TryAddWithoutValidation('X-Api-Key', $key)
    try {
        $response = $http.GetAsync($Url).GetAwaiter().GetResult()
        try {
            [byte[]]$bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            if(-not $response.IsSuccessStatusCode){
                $errorText = $script:OmegaUtf8.GetString($bytes)
                throw ("OmegaAI HTTP $([int]$response.StatusCode): $errorText")
            }
            # A leading comma stops PowerShell from unrolling byte[] into integers.
            return ,$bytes
        }
        finally { $response.Dispose() }
    }
    finally { $http.Dispose() }
}
function Get-OmegaUtf8Json {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [int]$TimeoutSec=30
    )
    [byte[]]$bytes = Get-OmegaUtf8Bytes -Url $Url -TimeoutSec $TimeoutSec
    $json = $script:OmegaUtf8.GetString($bytes).TrimStart([char]0xFEFF)
    return (ConvertFrom-Json -InputObject $json)
}

# JSON pretty printer, amely KIZAROLAG a szovegen kivuli whitespace-t
# modositja: nem ertelmezi ujra a szamokat, szovegeket vagy tomboket.
# Igy a magyar ekezetek es az eredeti JSON-adatok pontosan megmaradnak.
# PowerShell 5.1 alatt is mukodik (System.Text.Json / Newtonsoft nelkul).
function Format-OmegaJson {
    param([Parameter(Mandatory=$true)][string]$Json)

    $result = New-Object System.Text.StringBuilder
    $depth = 0
    $inString = $false
    $escaped = $false

    for ($i = 0; $i -lt $Json.Length; $i++) {
        [char]$c = $Json[$i]

        if ($inString) {
            [void]$result.Append($c)
            if ($escaped) {
                $escaped = $false
            } elseif ($c -eq [char]92) {
                $escaped = $true
            } elseif ($c -eq [char]34) {
                $inString = $false
            }
            continue
        }

        # A JSON ertekein beluli whitespace erintetlen (string ag fent).
        # A szovegen kivuli regi behuzast ujraepitjuk.
        if ([char]::IsWhiteSpace($c)) { continue }

        if ($c -eq [char]34) {
            $inString = $true
            [void]$result.Append($c)
        } elseif ($c -eq [char]123 -or $c -eq [char]91) {
            # Nyito kapcsos / szogletes zarojel: { vagy [
            [void]$result.Append($c)
            $closing = if ($c -eq [char]123) { [char]125 } else { [char]93 }
            $next = $i + 1
            while ($next -lt $Json.Length -and [char]::IsWhiteSpace($Json[$next])) { $next++ }
            if ($next -lt $Json.Length -and $Json[$next] -eq $closing) {
                # Ures tomb/objektum: [] vagy {} maradjon egy sorban.
                [void]$result.Append($closing)
                $i = $next
            } else {
                $depth++
                [void]$result.Append("`r`n")
                [void]$result.Append(' ' * ($depth * 2))
            }
        } elseif ($c -eq [char]125 -or $c -eq [char]93) {
            # Zaro kapcsos / szogletes zarojel: } vagy ]
            $depth--
            if ($depth -lt 0) { throw 'Ervenytelen JSON: hianyzo nyito zarojel.' }
            [void]$result.Append("`r`n")
            [void]$result.Append(' ' * ($depth * 2))
            [void]$result.Append($c)
        } elseif ($c -eq [char]44) {
            # Vesszo utan uj sor, de csak JSON-szovegen kivul.
            [void]$result.Append($c)
            [void]$result.Append("`r`n")
            [void]$result.Append(' ' * ($depth * 2))
        } elseif ($c -eq [char]58) {
            [void]$result.Append(': ')
        } else {
            [void]$result.Append($c)
        }
    }
    if ($depth -ne 0 -or $inString) { throw 'Ervenytelen JSON: lezaratlan struktura.' }
    return ($result.ToString() + "`r`n")
}

$ready=Get-OmegaUtf8Json -Url "$BaseUrl/v1/health/ready" -TimeoutSec 20
Write-Host ('[OK] Szolgaltatas: '+$ready.service+' | Qwen='+$ready.qwen_available+' | Whisper='+$ready.whisper_files+' | Pyannote='+$ready.pyannote_files)
if($Mode -eq 'QWEN'){
    $body=@{prompt='Valaszolj magyarul pontosan egy mondatban: milyen feladata van az API-nak?'}|ConvertTo-Json
    # Read POST response as UTF-8 bytes too, so Qwen's Hungarian text survives.
    $qwenClient=New-Object System.Net.Http.HttpClient
    $qwenClient.Timeout=[TimeSpan]::FromMinutes(10)
    $null=$qwenClient.DefaultRequestHeaders.TryAddWithoutValidation('X-Api-Key',$key)
    $payload=[System.Net.Http.ByteArrayContent]::new([byte[]][Text.Encoding]::UTF8.GetBytes($body))
    $payload.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/json; charset=utf-8')
    try {
        $qwenResponse=$qwenClient.PostAsync("$BaseUrl/v1/chat",$payload).GetAwaiter().GetResult()
        try {
            [byte[]]$qwenBytes=$qwenResponse.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            $qwenText=$script:OmegaUtf8.GetString($qwenBytes)
            if(-not $qwenResponse.IsSuccessStatusCode){throw ("OmegaAI Qwen HTTP $([int]$qwenResponse.StatusCode): $qwenText")}
            $result=ConvertFrom-Json -InputObject $qwenText
        } finally {$qwenResponse.Dispose()}
    } finally {$payload.Dispose();$qwenClient.Dispose()}
    Write-Host ('[QWEN] '+$result.answer)
    exit 0
}
if(-not $AudioFile){throw 'Hianyzo MP3/WAV path. Pelda: 05_TEST_MP3.bat "C:\Hangok\teszt.mp3"'}
$AudioFile=(Resolve-Path -LiteralPath $AudioFile).ProviderPath
Add-Type -AssemblyName System.Net.Http
$client=New-Object System.Net.Http.HttpClient
$client.Timeout=[TimeSpan]::FromMinutes(15)
$client.DefaultRequestHeaders.TryAddWithoutValidation('X-Api-Key',$key)|Out-Null
$stream=$null;$multipart=$null
try {
    $multipart=New-Object System.Net.Http.MultipartFormDataContent
    $stream=[IO.File]::OpenRead($AudioFile)
    $fileContent=[System.Net.Http.StreamContent]::new($stream)
    $fileContent.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
    $multipart.Add($fileContent,'audio',[IO.Path]::GetFileName($AudioFile))
    $multipart.Add(([System.Net.Http.StringContent]::new('OfflineAI teszt')),'title')
    $multipart.Add(([System.Net.Http.StringContent]::new([DateTimeOffset]::Now.ToString('o'))),'started_at')
    $multipart.Add(([System.Net.Http.StringContent]::new($(if($Mode -eq 'DIARIZE'){'true'}else{'false'}))),'diarize')
    $multipart.Add(([System.Net.Http.StringContent]::new('true')),'summarize')
    $response=$client.PostAsync("$BaseUrl/v1/audio/jobs",$multipart).GetAwaiter().GetResult()
    $json=$response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if(-not $response.IsSuccessStatusCode){throw ('Audio POST sikertelen: '+$response.StatusCode+' '+$json)}
    $job=$json|ConvertFrom-Json
    Write-Host ('[OK] Hangfelvetel feltoltve, job id='+$job.id)
} finally {if($multipart){$multipart.Dispose()};if($stream){$stream.Dispose()};$client.Dispose()}
$deadline=(Get-Date).AddMinutes(240)
while((Get-Date) -lt $deadline){
    Start-Sleep -Seconds 5
    $state=Get-OmegaUtf8Json -Url "$BaseUrl/v1/jobs/$($job.id)" -TimeoutSec 15
    if($state.status -eq 'queued'){
        # A jobs_ahead beleszamolja az eppen futo AI-munkat is.
        # Ez az ertek kerul majd a webes es mobilos sorpozicio-kijelzesre.
        $ahead=if($null -ne $state.jobs_ahead){$state.jobs_ahead}else{'ismeretlen'}
        Write-Host ('[SORBAN] '+$ahead+' feldolgozas van elotted | varakozo sorszam: '+$state.queue_position+' | '+$state.queue_message)
    } elseif($state.status -eq 'running'){
        $stepPercent=if($null -ne $state.stage_percent){('{0:N1}%' -f [double]$state.stage_percent)}else{'nem merheto'}
        Write-Host ('[FUT] '+$state.progress+'% sulyozott | '+$state.stage+' '+$stepPercent+' | '+$state.message+' | hangido: '+$state.completed_seconds+'/'+$state.total_seconds+' mp | chunk '+$state.chunks_completed+'/'+$state.chunks_total+' | belso lepes '+$state.stage_units_completed+'/'+$state.stage_units_total+' | CPU/GPU: '+$state.device+' | eltelt '+$state.elapsed_sec+' mp')
    } else {
        Write-Host ('['+$state.status+'] '+$state.progress+'% | '+$state.stage+' | '+$state.message)
    }
    if($state.waiting_for_model){Write-Host '[FIGYELEM] A feldolgozo egy ideje nem kozolt uj elorehaladast; figyeld az idokorlatot.' -ForegroundColor Yellow}
    if($state.status -in @('completed','failed','canceled')){break}
}
if($state.status -ne 'completed'){throw ('Feldolgozas nem keszult el: '+$state.status+' - '+$state.message)}
$out=Join-Path $Base ('data\tests\'+$job.id)
New-Item -ItemType Directory -Path $out -Force|Out-Null
# Do not use Invoke-WebRequest.Content here: PS 5.1 may already corrupt UTF-8.
# The API returns UTF-8 bytes; save them WITHOUT decoding and re-encoding.
[byte[]]$transBytes=Get-OmegaUtf8Bytes -Url "$BaseUrl/v1/jobs/$($job.id)/transcript" -TimeoutSec 60
[IO.File]::WriteAllBytes((Join-Path $out 'transcript.txt'),$transBytes)
[byte[]]$sumBytes=Get-OmegaUtf8Bytes -Url "$BaseUrl/v1/jobs/$($job.id)/summary" -TimeoutSec 60
[IO.File]::WriteAllBytes((Join-Path $out 'summary.txt'),$sumBytes)
Write-Host ('[OK] Atirat es osszesito: '+$out)
if($Mode -eq 'DIARIZE'){
    # Az API kompakt JSON-t ad vissza. Ujrairjuk tagolt, olvashato alakra,
    # mikozben a szovegek / szamok / speaker_id-k valtozatlanok maradnak.
    # A ConvertFrom-Json csak ellenorzi, hogy valoban ervenyes JSON-e a valasz.
    [byte[]]$segmentsBytes=Get-OmegaUtf8Bytes -Url "$BaseUrl/v1/jobs/$($job.id)/segments" -TimeoutSec 60
    $segmentsText=$script:OmegaUtf8.GetString($segmentsBytes).TrimStart([char]0xFEFF)
    if([string]::IsNullOrWhiteSpace($segmentsText)){throw 'Diarizacio: ures segments valasz.'}
    $null=ConvertFrom-Json -InputObject $segmentsText
    $prettySegments=Format-OmegaJson -Json $segmentsText
    # UTF-8 BOM nelkul, magyar ekezetekkel es tobb soros tagolassal.
    [IO.File]::WriteAllText((Join-Path $out 'segments.json'),$prettySegments,$script:OmegaUtf8)
    Write-Host ('[OK] Beszeloszakaszok: '+(Join-Path $out 'segments.json'))
    Write-Host '[FIGYELEM] A beszeloazonositoket a felvett hanggal kezzel is ellenorizni kell.'
}

