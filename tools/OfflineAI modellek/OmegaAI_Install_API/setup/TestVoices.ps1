param(
    [ValidateSet('CREATE','LIST','ENROLL','MATCH','APPROVE','DELETE_SAMPLE')][string]$Mode='LIST',
    [Parameter(Mandatory=$true)][string]$TenantId,
    [string]$Label='', [string]$PersonName='', [string]$ExternalId='',
    [string]$AudioFile='', [string]$JobId='', [string]$Speaker='',
    [string]$PersonId='', [string]$SampleId=''
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$url='http://127.0.0.1:8768'
$keyPath=Join-Path $Base 'config\api-key.txt'
if(-not(Test-Path -LiteralPath $keyPath)){throw "Admin kulcs nem található: $keyPath"}
$key=[IO.File]::ReadAllText($keyPath).Trim()
$headers=@{'X-Api-Key'=$key}
$uri="$url/v1/tenants/$TenantId"
# Kizárólag a szerver helyi API-ját hívjuk, publikusan nem használható.
if($TenantId -cnotmatch '^[a-z][a-z0-9_-]{2,63}$'){throw 'Érvénytelen tenant ID.'}
$secretPath=Join-Path $Base ('config\tenant-keys\'+$TenantId+'.txt')
function Secret {
    if(-not(Test-Path -LiteralPath $secretPath)){throw "Nincs tenant kulcs: $secretPath. Előbb CREATE szükséges."}
    $headers['X-Tenant-Key']=[IO.File]::ReadAllText($secretPath).Trim()
}
function JsonPost([string]$endpoint, [hashtable]$body) {
    $bytes=[Text.Encoding]::UTF8.GetBytes(($body|ConvertTo-Json -Depth 9 -Compress))
    return Invoke-RestMethod -Method Post -Uri $endpoint -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 120
}
if($Mode -eq 'CREATE'){
    if(-not $Label){throw 'CREATE: add meg a -Label paramétert.'}
    $result=JsonPost "$url/v1/tenants" @{tenant_id=$TenantId;label=$Label}
    New-Item -ItemType Directory -Force (Split-Path $secretPath -Parent)|Out-Null
    [IO.File]::WriteAllText($secretPath,$result.tenant_api_key,(New-Object Text.UTF8Encoding($false)))
    Write-Host "[OK] Új alkalmazás: $TenantId. Kulcs mentve: $secretPath (bizalmas; NTFS jogosultság szükséges!)"
    exit 0
}
Secret
if($Mode -eq 'LIST'){
    Invoke-RestMethod -Uri "$uri/persons" -Headers $headers | ConvertTo-Json -Depth 10
    exit 0
}
if($Mode -eq 'MATCH'){
    if($JobId -notmatch '^[a-f0-9]{32}$'){throw 'MATCH: -JobId 32 hex karakter.'}
    $res=JsonPost "$uri/jobs/$JobId/match" @{threshold=0.88;margin=0.04}
    $res|ConvertTo-Json -Depth 12
    Write-Host '[FIGYELEM] Csak ellenőrzendő javaslat, nem személyazonossági bizonyíték!'
    exit 0
}
if($Mode -eq 'APPROVE'){
    if(-not $PersonId -or -not $Speaker -or -not $JobId){throw 'APPROVE: -JobId -Speaker -PersonId szükséges.'}
    $approved=@{}
    $approved[$Speaker]=$PersonId
    (JsonPost "$uri/jobs/$JobId/approve" @{approved=$approved})|ConvertTo-Json -Depth 10
    exit 0
}
if($Mode -eq 'DELETE_SAMPLE'){
    if(-not $PersonId -or -not $SampleId){throw 'DELETE_SAMPLE: -PersonId -SampleId szükséges.'}
    Invoke-RestMethod -Method Delete -Uri "$uri/persons/$PersonId/samples/$SampleId" -Headers $headers|ConvertTo-Json
    exit 0
}
if($Mode -eq 'ENROLL'){
    if(-not $PersonName -or -not $AudioFile){throw 'ENROLL: -PersonName és -AudioFile szükséges.'}
    $audioPath=(Resolve-Path -LiteralPath $AudioFile).ProviderPath
    Write-Host "Hangminta: $audioPath; személy: $PersonName; tenant: $TenantId"
    $consent=Read-Host 'Az érintett kifejezetten hozzájárult a hangprofil tárolásához? Írd be: IGEN'
    if($consent -cne 'IGEN'){throw 'Jóváhagyás nélkül tilos hangprofilt létrehozni.'}
    $person=@{name=$PersonName}
    if($ExternalId){$person.external_person_id=$ExternalId}
    $p=JsonPost "$uri/persons" $person
    Add-Type -AssemblyName System.Net.Http
    $client=[System.Net.Http.HttpClient]::new()
    $client.Timeout=[TimeSpan]::FromMinutes(12)
    [void]$client.DefaultRequestHeaders.TryAddWithoutValidation('X-Api-Key',$key)
    [void]$client.DefaultRequestHeaders.TryAddWithoutValidation('X-Tenant-Key',$headers['X-Tenant-Key'])
    $multi=[System.Net.Http.MultipartFormDataContent]::new()
    $stream=[IO.File]::OpenRead($audioPath)
    try {
        $content=[System.Net.Http.StreamContent]::new($stream)
        $content.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
        $multi.Add($content,'audio',[IO.Path]::GetFileName($audioPath))
        $multi.Add(([System.Net.Http.StringContent]::new('true')),'consent_confirmed')
        $multi.Add(([System.Net.Http.StringContent]::new('Érintett személy kifejezett hozzájárulása helyben ellenőrizve')),'consent_note')
        $response=$client.PostAsync("$uri/persons/$($p.id)/samples",$multi).GetAwaiter().GetResult()
        $text=$response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if(-not $response.IsSuccessStatusCode){throw "Hangminta-feltöltési hiba: $($response.StatusCode) $text"}
        $job=$text|ConvertFrom-Json
        Write-Host "[OK] Regisztráció sorban: $($job.id)"
    } finally {$multi.Dispose();$stream.Dispose();$client.Dispose()}
    for($i=0;$i -lt 1800;$i++){
        Start-Sleep -Seconds 2
        $state=Invoke-RestMethod -Uri "$uri/enrollments/$($job.id)" -Headers $headers -TimeoutSec 30
        Write-Host "[$($state.status)] $($state.message) | előttem: $($state.jobs_ahead) | lépés: $($state.step) | belső %: $($state.stage_percent)"
        if($state.status -in @('completed','failed','canceled')){break}
    }
    if($state.status -ne 'completed'){throw "Nem készült el a profil: $($state.status) / $($state.message)"}
    Write-Host "[OK] Hangprofil kész. Személyazonosító: $($p.id); sample_id: $($state.result.sample_id)"
}
