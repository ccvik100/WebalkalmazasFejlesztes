param([string]$Base = 'C:\OmegaAI')
$ErrorActionPreference = 'Stop'
$Source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Target = [IO.Path]::GetFullPath($Base)
$Python = Join-Path $Target '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw ('Nem letezik az OmegaAI Python kornyezete: ' + $Python)
}
foreach ($name in @('app\offlineai\engines.py','app\offlineai\core.py','app\offlineai\__init__.py','app\requirements-ai.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Source $name) -PathType Leaf)) { throw ('Hianyzo hotfix forras: ' + $name) }
    if (-not (Test-Path -LiteralPath (Join-Path $Target $name) -PathType Leaf)) { throw ('Hianyzo cel fajl: ' + $name) }
}
Write-Host ('[OmegaAI HOTFIX] Csomag: ' + $Source)
Write-Host ('[OmegaAI HOTFIX] Telepites: ' + $Target)
Write-Host 'Az OmegaAI REST szolgaltatasnak LEALLITVA kell lennie!'
$port = Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue
if ($port) { throw 'A 8768-as OfflineAI REST szolgaltatas meg fut. Allitsd le a 03_INDITAS.bat ablakot (Ctrl+C).' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Target ('logs\hangdekoder_backup_' + $stamp)
New-Item -ItemType Directory -Path $Backup -Force | Out-Null
$names = @('app\offlineai\engines.py','app\offlineai\core.py','app\offlineai\__init__.py','app\requirements-ai.txt')
foreach ($name in $names) {
    $dest = Join-Path $Backup $name
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $Target $name) -Destination $dest -Force
}
Write-Host ('[OK] Biztonsagi masolat: ' + $Backup)
Write-Host '[1/2] Kompatibilis PyAV (18.1.0) telepitese, csak ezt a csomagot erinti ...'
& $Python -m pip install --no-deps --only-binary=:all: --force-reinstall 'av==18.1.0'
if ($LASTEXITCODE -ne 0) { throw 'A PyAV telepites nem sikerult. A forraskod valtozatlan, a modellek erintetlenek.' }
Write-Host '[2/2] Hangfeldolgozasi forrasfajlok csereje ...'
try {
    foreach ($name in $names) {
        Copy-Item -LiteralPath (Join-Path $Source $name) -Destination (Join-Path $Target $name) -Force
    }
    & $Python -m compileall -q (Join-Path $Target 'app\offlineai')
    if ($LASTEXITCODE -ne 0) { throw 'A Python forraskod ellenorzese hibara futott.' }
} catch {
    foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $Backup $name) -Destination (Join-Path $Target $name) -Force }
    throw ('A frissites sikertelen; az eredeti fajlok visszaallitva. Ok: ' + $_.Exception.Message)
}
Write-Host '[OK] OmegaAI 1.3 hangdekoder javitas kesz.'
Write-Host 'Most inditsd ujra a 03_INDITAS.bat folyamatot, majd futtasd ujra az 05_TEST_MP3.bat tesztet.'
