$ErrorActionPreference='Stop'
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$key=([IO.File]::ReadAllText((Join-Path $Base 'config\api-key.txt'))).Trim()
$h=@{'X-Api-Key'=$key}
$r=Invoke-RestMethod -Uri 'http://127.0.0.1:8768/v1/hardware' -Headers $h -TimeoutSec 90
Write-Host '[OmegaAI] CPU/GPU ellenorzes (nem benchmarking)' 
$r|ConvertTo-Json -Depth 10
Write-Host 'A tenylegesen hasznalt device az adott job /v1/jobs/{id} allapotaban ellenorizheto.'
