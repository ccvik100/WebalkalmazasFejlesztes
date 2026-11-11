param([switch]$Deep)
$ErrorActionPreference='Stop'
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$py=Join-Path $Base '.venv\Scripts\python.exe'
if(-not(Test-Path $py)){throw "Hianyzik: $py (01_TELEPITES.bat INSTALL)"}
$env:PYTHONPATH=Join-Path $Base 'app'
$env:OFFLINEAI_HOME=$Base
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
Write-Host '=== OfflineAI - kornyezetellenorzes ==='
& $py -m pip check
if($LASTEXITCODE -ne 0){throw 'pip check hibas: inkompatibilis fuggosegek.'}
& $py -m offlineai.doctor $(if ($Deep) {'--deep'}else{'--basic'})
if($LASTEXITCODE -ne 0){throw 'Az AI kornyezetellenorzes hibaval zarult.'}
