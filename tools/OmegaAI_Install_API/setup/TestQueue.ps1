param([Parameter(Mandatory=$true)][string]$AudioFile, [int]$Count=3)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
if($Count -lt 2 -or $Count -gt 5){throw 'Count: 2 es 5 kozott legyen.'}
$AudioFile=(Resolve-Path -LiteralPath $AudioFile).ProviderPath
$key=([IO.File]::ReadAllText((Join-Path $Base 'config\api-key.txt'))).Trim()
$headers=@{'X-Api-Key'=$key}
$endpoint='http://127.0.0.1:8768'
$ready=Invoke-RestMethod -Uri "$endpoint/v1/health/ready" -Headers $headers -TimeoutSec 10
Write-Host ('[OK] OmegaAI: '+$ready.version)
Add-Type -AssemblyName System.Net.Http
$client=[System.Net.Http.HttpClient]::new()
$client.Timeout=[TimeSpan]::FromMinutes(5)
$client.DefaultRequestHeaders.Add('X-Api-Key',$key)
$ids=New-Object System.Collections.Generic.List[string]
try {
    for($i=1;$i -le $Count;$i++){
        $body=[System.Net.Http.MultipartFormDataContent]::new()
        $stream=[IO.File]::OpenRead($AudioFile)
        try {
            $body.Add([System.Net.Http.StreamContent]::new($stream),'audio',[IO.Path]::GetFileName($AudioFile))
            $body.Add([System.Net.Http.StringContent]::new("Sorban teszt $i"),'title')
            $body.Add([System.Net.Http.StringContent]::new('false'),'diarize')
            $body.Add([System.Net.Http.StringContent]::new('false'),'summarize')
            $response=$client.PostAsync("$endpoint/v1/audio/jobs",$body).GetAwaiter().GetResult()
            $payload=$response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if(-not $response.IsSuccessStatusCode){throw ('Feltoltes HIBA: '+$response.StatusCode+' '+$payload)}
            $result=$payload|ConvertFrom-Json
            $ids.Add([string]$result.id)
            Write-Host ('['+$i+'/'+$Count+'] Azonosito='+$result.id+' | elotte='+$result.jobs_ahead+' munka | varakozo sorszam='+$result.queue_position+' | '+$result.queue_message)
        } finally {$body.Dispose();$stream.Dispose()}
    }
} finally {$client.Dispose()}
Write-Host ''
Write-Host 'Kozponti sor allapota:'
$queue=Invoke-RestMethod -Uri "$endpoint/v1/queue" -Headers $headers -TimeoutSec 20
Write-Host ('Futo='+$queue.active_job_id+' | Varakozok='+$queue.queued_jobs+' | Max egyideju audio='+$queue.max_parallel_audio_jobs)
$out=Join-Path $Base ('data\tests\queue_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -Path $out -ItemType Directory -Force|Out-Null
$ids|Set-Content -LiteralPath (Join-Path $out 'job-ids.txt') -Encoding UTF8
Write-Host ('Azonositok mentve: '+(Join-Path $out 'job-ids.txt'))
Write-Host 'A munkak automatikusan, egymas utan folytatodnak. Allapot: 13_JOB_ALLAPOT.bat ID'
Write-Host 'Ha nem szeretned a tovabbi feldolgozast, POST /v1/jobs/{id}/cancel.'
