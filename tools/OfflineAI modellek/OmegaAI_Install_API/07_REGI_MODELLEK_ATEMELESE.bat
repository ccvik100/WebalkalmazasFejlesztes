@echo off
setlocal
chcp 65001 >nul
set "OLDDIR=%~1"
if not defined OLDDIR set /p "OLDDIR=Regi KIMENET\OMEGA_API mappa: "
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\ImportPrevious.ps1" -OldApi "%OLDDIR%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" echo [HIBA] Atmasolas sikertelen: %CODE%
pause
exit /b %CODE%
