@echo off
setlocal
chcp 65001 >nul
set "AUDIO=%~1"
if not defined AUDIO set /p "AUDIO=MP3/WAV teljes eleresi utja: "
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\TestApi.ps1" -Mode AUDIO -AudioFile "%AUDIO%"
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" echo [HIBA] Audio teszt sikertelen. Kod: %CODE%
pause
exit /b %CODE%
