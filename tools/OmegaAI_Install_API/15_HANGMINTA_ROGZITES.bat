@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\TestVoices.ps1" -Mode ENROLL -TenantId "%~2" -PersonName "%~3" -AudioFile "%~1" -ExternalId "%~4"
set "RET=%ERRORLEVEL%"
if not "%RET%"=="0" echo [HIBA] Hangprofil-teszt sikertelen. Hibakod: %RET%
echo.
pause
exit /b %RET%
