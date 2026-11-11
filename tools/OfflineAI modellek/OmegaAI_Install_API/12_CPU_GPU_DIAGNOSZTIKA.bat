@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\TestHardware.ps1" 
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (echo [HIBA] Ellenorzes hibaval zarult: %CODE%) else (echo [OK] Ellenorzes befejezodott.)
pause
exit /b %CODE%
