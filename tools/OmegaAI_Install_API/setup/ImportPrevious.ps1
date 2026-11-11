param([Parameter(Mandatory=$true)][string]$OldApi)
$ErrorActionPreference='Stop'
$dest=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$old=(Resolve-Path -LiteralPath $OldApi).ProviderPath
$candidates=@(
 (Join-Path $old 'wwwroot\_offline_private'),
 (Join-Path $old '_offline_private'),
 $old
)
$models=$null
foreach($dir in $candidates){
 if(Test-Path (Join-Path $dir 'whisper-large-v3\model.bin')){ $models=$dir;break }
}
if(-not $models){throw 'Nem talalom a regi Whisper model.bin fajlt. Add meg a KIMENET\OMEGA_API mappat.'}
foreach($name in @('whisper-large-v3','pyannote-community-1')){
 $source=Join-Path $models $name
 $target=Join-Path $dest ('models\'+$name)
 if(-not(Test-Path $source)){Write-Host "[FIGYELEM] Hianyzik: $source";continue}
 if($name -eq 'whisper-large-v3' -and (Test-Path (Join-Path $target 'model.bin'))){Write-Host 'Whisper mar megvan; nem masoljuk ujra.';continue}
 if($name -eq 'pyannote-community-1' -and (Test-Path (Join-Path $target 'config.yaml'))){Write-Host 'pyannote mar megvan; nem masoljuk ujra.';continue}
 New-Item -ItemType Directory -Force -Path $target|Out-Null
 Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
 Write-Host "[OK] Atmasolva: $source -> $target"
}
Write-Host 'Modellek atemelve. Az ellenorzeshez: 02_ELLENORZES.bat DEEP'
