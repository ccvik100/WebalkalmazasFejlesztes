$ErrorActionPreference='Stop'
$base = if ($env:OFFLINEAI_HOME) { $env:OFFLINEAI_HOME } else { 'C:\OmegaAI' }
Write-Host ('Modelleket tarolo mappa: ' + (Join-Path $base 'models\ollama'))
foreach ($part in @('blobs','manifests')) {
    $path = Join-Path $base ('models\ollama\' + $part)
    if (Test-Path -LiteralPath $path) { Write-Host ('[OK] Meglevo: ' + $path) }
    else { Write-Host ('[FIGYELEM] Nincs: ' + $path) }
}
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
$names = @($reply.models | ForEach-Object { $_.name })
Write-Host ('Ollama modellek (11434): ' + ($names -join ', '))
if ('qwen3:8b' -notin $names) { throw 'qwen3:8b nem latszik az Ollama API-ban. Fajlok jelenlete onmagaban nem bizonyitja a kapcsolodo szerver beallitasat.' }
Write-Host '[OK] qwen3:8b regisztralva es elerheto; ezt a tesztet nem tekintjuk inferencia-tesztnek.'
