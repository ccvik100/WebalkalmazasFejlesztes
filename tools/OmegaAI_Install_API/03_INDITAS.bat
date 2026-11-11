@echo off
setlocal
chcp 65001 >nul
REM Magyar karakterek biztonsagos atadasa a Python es a worker folyamatok kozt.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8:backslashreplace"
set "PYTHONUNBUFFERED=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\Start.ps1"
set "CODE=%ERRORLEVEL%"
echo.
echo OfflineAI leallt. Exit code: %CODE%
pause
exit /b %CODE%
