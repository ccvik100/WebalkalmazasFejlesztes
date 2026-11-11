@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\TestApi.ps1" -Mode QWEN
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" echo [HIBA] Qwen teszt sikertelen. Kod: %CODE%
pause
exit /b %CODE%
