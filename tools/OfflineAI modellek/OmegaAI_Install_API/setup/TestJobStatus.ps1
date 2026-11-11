param([Parameter(Mandatory=$true)][string]$Id)
$ErrorActionPreference='Stop'
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$key=([IO.File]::ReadAllText((Join-Path $Base 'config\api-key.txt'))).Trim()
$h=@{'X-Api-Key'=$key}
$u='http://127.0.0.1:8768/v1/jobs/'+$Id
while($true){
    $j=Invoke-RestMethod -Uri $u -Headers $h -TimeoutSec 20
    $seconds=if($null -ne $j.completed_seconds){$j.completed_seconds}else{'-'}
    $total=if($null -ne $j.total_seconds){$j.total_seconds}else{'-'}
    if($j.status -eq 'queued') {
        $ahead=if($null -ne $j.jobs_ahead){[string]$j.jobs_ahead}else{'ismeretlen'}
        Write-Host ('[SORBAN] '+$ahead+' feldolgozas van elotted | varakozo sorszam: '+$j.queue_position+' | minden munkaval egyutt: '+$j.queue_position_overall)
    } elseif($j.status -eq 'running') {
        $stagePercent=if($null -ne $j.stage_percent){('{0:N1}%' -f [double]$j.stage_percent)}else{'nem merheto'}
        Write-Host ('[FUT] feladat='+$j.progress+'% (sulyozott) | lepes='+$j.stage+' | lepesarany='+$stagePercent+' | '+$j.stage_detail+' | '+$seconds+'/'+$total+' hangmp | chunks '+$j.chunks_completed+'/'+$j.chunks_total+' | eltelt '+$j.elapsed_sec+' mp | eszkoz '+$j.device)
    } else {
        Write-Host ('['+$j.status+'] '+$j.progress+'% | '+$j.stage+' | '+$j.message)
    }
    if($j.status -in @('completed','failed','canceled')){
        if($j.status -ne 'completed'){Write-Host ('Vegeredmeny: '+$j.message)}
        break
    }
    Start-Sleep -Seconds 5
}
