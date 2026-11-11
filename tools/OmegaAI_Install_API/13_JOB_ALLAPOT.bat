@echo off
setlocal
chcp 65001 >nul
if "%~1"=="" (echo Hianyzo parametrum. & echo Hasznalat: %~nx0 "MP3_utvonal_vagy_job_id" & pause & exit /b 2)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\TestJobStatus.ps1" -Id "%~1"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (echo [HIBA] Ellenorzes hibaval zarult: %CODE%) else (echo [OK] Ellenorzes befejezodott.)
pause
exit /b %CODE%
