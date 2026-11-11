param([string]$Base = '')
$ErrorActionPreference='Stop'
if (-not $Base) { $Base = if ($env:OFFLINEAI_HOME) { $env:OFFLINEAI_HOME } else { 'C:\OmegaAI' } }
$url = 'http://127.0.0.1:11434/api/tags'
try {
    $tags = Invoke-RestMethod -Uri $url -TimeoutSec 5
    $names = @($tags.models | ForEach-Object { $_.name })
    if ('qwen3:8b' -notin $names) { throw ('A 11434-es Ollama fut, de nem latja a qwen3:8b modellt. Ellenorizd az OLLAMA_MODELS erteket es a ' + (Join-Path $Base 'models\ollama') + ' mappat.') }
    Write-Host '[OK] Meglevo Ollama es qwen3:8b elerheto (127.0.0.1:11434). Nem indul masodik peldany.'
    return
} catch {
    if ($_.Exception.Message -like '*nem latja*') { throw }
}
# Do not install or overwrite Ollama or model data. Start only an installed executable.
$exe = $null
$cmd = Get-Command ollama.exe -ErrorAction SilentlyContinue
if ($cmd) { $exe = $cmd.Source }
if (-not $exe) {
    $localExe = Join-Path $Base 'tools\ollama\ollama.exe'
    if (Test-Path -LiteralPath $localExe) { $exe = $localExe }
}
if (-not $exe) {
    throw 'Ollama nem fut a 11434 porton es ollama.exe sem talalhato. Telepitsd az Ollama Windows-verziot, allitsd OLLAMA_MODELS=C:\OmegaAI\models\ollama, majd inditsd el.'
}
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MODELS=Join-Path $Base 'models\ollama'
$env:OLLAMA_NO_CLOUD='1'
$log=Join-Path $Base 'logs'
New-Item -ItemType Directory -Path $log -Force | Out-Null
Start-Process -FilePath $exe -ArgumentList @('serve') -WorkingDirectory (Split-Path -Parent $exe) -RedirectStandardOutput (Join-Path $log 'ollama.stdout.log') -RedirectStandardError (Join-Path $log 'ollama.stderr.log') | Out-Null
for ($i=0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $tags = Invoke-RestMethod -Uri $url -TimeoutSec 2
        $names = @($tags.models | ForEach-Object { $_.name })
        if ('qwen3:8b' -in $names) { Write-Host '[OK] Ollama elindult; qwen3:8b elerheto.';return }
    } catch { }
}
throw ('Nem sikerult elinditani a qwen3:8b-t kiszolgalo Ollamat. Ellenorizd: ' + (Join-Path $log 'ollama.stderr.log'))
