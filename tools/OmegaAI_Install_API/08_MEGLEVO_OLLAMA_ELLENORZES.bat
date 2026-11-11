@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\CheckOllama.ps1"
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (echo [OK] Meglevo Ollama es Qwen megvan.) else (echo [HIBA] Ollama elofeltetel sikertelen. Kod: %CODE%)
pause
exit /b %CODE%
