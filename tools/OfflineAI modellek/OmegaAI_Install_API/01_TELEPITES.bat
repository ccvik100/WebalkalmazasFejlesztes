@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "MODE=%~1"
if not defined MODE set "MODE=CHECK"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\Install.ps1" -Mode "%MODE%"
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (echo [OK] Lefutott: %MODE%) else (echo [HIBA] Telepites vagy ellenorzes sikertelen. Kod: %CODE%)
echo A teljes naplo a C:\OmegaAI\logs mappaban van (ha a telepitesi cel C:\OmegaAI).
echo Nyomj meg egy gombot az ablak bezarasahoz.
pause >nul
exit /b %CODE%
