param([ValidateSet('CHECK','INSTALL')][string]$Mode = 'CHECK')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Source = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).ProviderPath
$HomePath = if ($env:OFFLINEAI_HOME) { $env:OFFLINEAI_HOME } else { 'C:\OmegaAI' }
$HomePath = [IO.Path]::GetFullPath($HomePath).TrimEnd('\')
$LogDir = Join-Path $HomePath 'logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Log = Join-Path $LogDir ('install_' + $Mode + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
Start-Transcript -Path $Log -Force | Out-Null
function WriteStep([string]$msg) { Write-Host ''; Write-Host ('[OmegaAI] ' + $msg) }
function AssertFile([string]$path) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Hianyzo fajl: ' + $path) } }
function Run([string]$binary, [string[]]$arguments) {
    $global:LASTEXITCODE = 0
    & $binary @arguments
    if ($LASTEXITCODE -ne 0) { throw ('Hibas parancs (' + $LASTEXITCODE + '): ' + $binary + ' ' + ($arguments -join ' ')) }
}
function FindPython312 {
    # A Python-verzio ellenorzeset onallo .py fajl vegzi.
    # Igy nem adunk at Windows PowerShell 5.1-en torheto python -c idezojeleket.
    $probe = Join-Path $PSScriptRoot 'ProbePython.py'
    AssertFile $probe
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            & $launcher.Source -3.12 $probe 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{ Exe = $launcher.Source; Prefix = @('-3.12') }
            }
        } catch {
            # Nincs mukodo Python 3.12 a Windows py launcherben; ellenorizzuk a PATH-ot.
        }
    }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            & $cmd.Source $probe 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{ Exe = $cmd.Source; Prefix = @() }
            }
        } catch {
            # Nem a kert Python-verzio vagy architektura: ertelmes hibat adunk.
        }
    }
    throw 'Python 3.12 64 bites verzio nem erheto el (py -3.12 vagy python.exe).'
}
function TestQwen {
    $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 6
    $names = @($tags.models | ForEach-Object { $_.name })
    if ('qwen3:8b' -notin $names) {
        throw ('Ollama fut (11434), de qwen3:8b nincs a listaban. Meglevo modelleket NEM irjuk felul. Modellek: ' + ($names -join ', ') + '. Ellenorizd az OLLAMA_MODELS beallitast: ' + (Join-Path $HomePath 'models\ollama'))
    }
    Write-Host '[OK] Meglevo Ollama 11434; qwen3:8b elerheto. Nem telepitjuk/letoltjuk ujra.'
}
function InstallFfmpeg {
    $exe = Join-Path $HomePath 'tools\ffmpeg.exe'
    if (Test-Path -LiteralPath $exe) { Write-Host '[OK] Meglevo FFmpeg megorizve.'; return }
    $external = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($external -and (Test-Path -LiteralPath $external.Source)) {
        Copy-Item -LiteralPath $external.Source -Destination $exe -Force
        Write-Host '[OK] FFmpeg a PATH-bol atmasolva.'
        return
    }
    $url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    $zip = Join-Path $HomePath 'downloads\ffmpeg-release-essentials.zip'
    if (-not (Test-Path $zip)) {
        WriteStep 'Hianyzo FFmpeg beszerzese HTTPS-en...'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 3600
    }
    if ((Get-Item $zip).Length -lt 100000) { throw 'Az FFmpeg ZIP ures vagy tul kicsi.' }
    $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
    Write-Host ('FFmpeg ZIP helyi SHA256: ' + $hash)
    Write-Host '[FIGYELEM] Ez nem fuggetlen kiadoi hash-ellenorzes.'
    $temp = Join-Path $HomePath 'downloads\ffmpeg-unpack'
    if (Test-Path $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
    Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force
    $found = Get-ChildItem -LiteralPath $temp -Filter ffmpeg.exe -File -Recurse | Select-Object -First 1
    if (-not $found) { throw 'A ZIP nem tartalmaz ffmpeg.exe fajlt.' }
    Copy-Item -LiteralPath $found.FullName -Destination $exe -Force
    Remove-Item -LiteralPath $temp -Recurse -Force
    Write-Host '[OK] FFmpeg telepitve.'
}
function CopyWhenSeparate([string]$relative) {
    $origin = Join-Path $Source $relative
    $target = Join-Path $HomePath $relative
    if (-not (Test-Path $origin)) { return }
    # Same source and destination: no self-copy, no "cannot copy onto itself" error.
    $originFull = [IO.Path]::GetFullPath($origin).TrimEnd('\')
    $targetFull = [IO.Path]::GetFullPath($target).TrimEnd('\')
    if ($originFull -ieq $targetFull) { return }
    if (Test-Path -LiteralPath $origin -PathType Container) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        Copy-Item -Path (Join-Path $origin '*') -Destination $target -Recurse -Force
    } else {
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Copy-Item -LiteralPath $origin -Destination $target -Force
    }
}
try {
    WriteStep ('Mod: ' + $Mode + ' | Gyoker: ' + $HomePath + ' | Csomag: ' + $Source)
    foreach ($file in @('app\offlineai\main.py','app\requirements-api.txt','app\requirements-ai.txt','config\settings.example.json')) {
        AssertFile (Join-Path $Source $file)
    }
    $python = FindPython312
    Write-Host ('[OK] Python 3.12 x64: ' + $python.Exe + ' ' + ($python.Prefix -join ' '))
    Write-Host ('Meglevo Ollama-modelltar: ' + (Join-Path $HomePath 'models\ollama'))
    if ($Mode -eq 'CHECK') {
        try { TestQwen } catch { Write-Host ('[FIGYELEM] Ollama elofeltetel: ' + $_.Exception.Message) }
        Write-Host '[OK] CHECK sikeres: forras + Python 3.12. Nincs letoltes vagy Python-modellbetoltes.'
    } else {
        WriteStep 'Forrasok atemelese; meglevo modellek, adatok, titkok es Ollama tarhely megorzese'
        foreach ($sub in @('app','config','tools','models','downloads','data\jobs','data\tenants','logs')) {
            New-Item -ItemType Directory -Path (Join-Path $HomePath $sub) -Force | Out-Null
        }
        foreach ($relative in @('app','setup','docs','config\settings.example.json','README_HU.md','CHANGELOG_HU.md','OmegaAI_v1_6_TELJES_Hangprofil_SQLite_API_Kezikonyv.docx')) {
            CopyWhenSeparate $relative
        }
        foreach ($file in Get-ChildItem -LiteralPath $Source -Filter '*.bat' -File) {
            CopyWhenSeparate $file.Name
        }
        $settings = Join-Path $HomePath 'config\settings.json'
        if (-not (Test-Path $settings)) {
            Copy-Item -LiteralPath (Join-Path $Source 'config\settings.example.json') -Destination $settings
        } else {
            # Change only the legacy port of this project's configuration; preserve everything else.
            $cfg = Get-Content -LiteralPath $settings -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($cfg.ollama_url -eq 'http://127.0.0.1:11435') {
                Copy-Item -LiteralPath $settings -Destination ($settings + '.before-11434.bak') -Force
                $cfg.ollama_url = 'http://127.0.0.1:11434'
                [IO.File]::WriteAllText($settings,($cfg | ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false)))
                Write-Host '[OK] Regi 11435 port beallitas atallitva 11434-re, biztonsagi masolat keszult.'
            }
        }
        $key = Join-Path $HomePath 'config\api-key.txt'
        if (-not (Test-Path $key)) {
            $bytes = New-Object byte[] 48
            $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
            try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
            [IO.File]::WriteAllText($key,[Convert]::ToBase64String($bytes),(New-Object Text.UTF8Encoding($false)))
            Write-Host '[OK] Uj API-kulcs kesz; nem kerul a naploba.'
        }
        WriteStep 'Python izolalt kornyezet es csomagok'
        $venv = Join-Path $HomePath '.venv\Scripts\python.exe'
        if (-not (Test-Path $venv)) {
            Run $python.Exe (@($python.Prefix) + @('-m','venv',(Join-Path $HomePath '.venv')))
        }
        AssertFile $venv
        Run $venv @('-m','pip','install','-r',(Join-Path $HomePath 'app\requirements-api.txt'))
        Run $venv @('-m','pip','install','-r',(Join-Path $HomePath 'app\requirements-ai.txt'))
        Run $venv @('-m','pip','check')
        WriteStep 'FFmpeg ellenorzes / szukseg eseten telepites'
        InstallFfmpeg
        WriteStep 'Whisper es pyannote modellek ellenorzese / hianyzo modellek letoltese'
        $env:OFFLINEAI_HOME=$HomePath
        $env:PYTHONPATH=Join-Path $HomePath 'app'
        $env:HF_HUB_OFFLINE='0'
        $env:TRANSFORMERS_OFFLINE='0'
        Run $venv @((Join-Path $HomePath 'app\prepare_models.py'))
        WriteStep 'Meglevo Ollama 11434 es Qwen3:8b ellenorzese (nem tolti le ujra)'
        TestQwen
        Write-Host '[OK] INSTALL sikeresen befejezodott.'
    }
    Write-Host ('Naplo: ' + $Log)
    exit 0
} catch {
    Write-Host ('[HIBA] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Naplo: ' + $Log)
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
