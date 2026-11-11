@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 01_KONFIGURALAS.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - A SETLOCAL korlatozza a batch valtozokat erre a futasra.
setlocal
REM TANANYAG - A scriptet a projekt gyokerkonyvtarabol futtatjuk, a hivo aktualis mappajatol fuggetlenul.
cd /d "%~dp0.."
REM TANANYAG - A Configure.ps1 letrehozza a privat kliens- es tenantkulcsokat, a %* tovabbitja a parametereket.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Configure.ps1" %*
REM TANANYAG - Az elozo powershell parancs valodi kilepesi kodjat elmentjuk.
set "RET=%ERRORLEVEL%"
REM TANANYAG - Ures sor segiti a kimenet olvashatosagat.
echo.
REM TANANYAG - Hiba eseten egyertelmu hibajelzest adunk.
if not "%RET%"=="0" echo [HIBA] Konfiguracio sikertelen. Kod: %RET%
REM TANANYAG - Sikeres beallitaskor megerosito uzenet jelenik meg.
if "%RET%"=="0" echo [OK] Konfiguracio kesz.
REM TANANYAG - A PAUSE miatt a konzolablak nem zarodik be azonnal.
pause
REM TANANYAG - A BAT visszaadja a powershell eredeti kilepesi kodjat.
exit /b %RET%
