@echo off
setlocal
chcp 65001 >nul
set "DEEP="
if /I "%~1"=="DEEP" set "DEEP=-Deep"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\Check.ps1" %DEEP%
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (echo [OK] Ellenorzes sikeres.) else (echo [HIBA] Ellenorzes sikertelen. Kod: %CODE%)
pause
exit /b %CODE%
