$ErrorActionPreference='Stop'
$Base = if ($env:OFFLINEAI_HOME) { $env:OFFLINEAI_HOME } else { 'C:\OmegaAI' }
$py = Join-Path $Base '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw 'A Python kornyezet hianyzik. Futtasd: 01_TELEPITES.bat INSTALL' }
& (Join-Path $PSScriptRoot 'StartLocalOllama.ps1') -Base $Base
$env:PYTHONPATH = Join-Path $Base 'app'
$env:OFFLINEAI_HOME = $Base
# Szabványos UTF-8 a Python REST-folyamat és a gyermek-workerek számára.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8:backslashreplace'
$env:PYTHONUNBUFFERED = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
Write-Host 'OfflineAI REST: http://127.0.0.1:8768/docs'
& $py -m offlineai
if ($LASTEXITCODE -ne 0) { throw ('OfflineAI folyamat hiba: ' + $LASTEXITCODE) }
