@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 02_ELLENORZES.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - A valtozok e futas vegetol nem szennyezik a kulso parancssori kornyezetet.
setlocal
REM TANANYAG - A projekt mappajaba lepunk, ahol a konfiguralas es ellenorzes fajljai vannak.
cd /d "%~dp0.."
REM TANANYAG - A Check.ps1 megvizsgalja a .NET 10-et, a titkos konfiguraciot es az OmegaAI alapallapotat.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Check.ps1"
REM TANANYAG - A PowerShell eredmenyekodja azonnal bekerul a RET valtozoba.
set "RET=%ERRORLEVEL%"
REM TANANYAG - A kimenetet elvalasztjuk a fo ellenorzesi uzenetektol.
echo.
REM TANANYAG - Hibas ellenorzesnel hibauzenet jelenik meg.
if not "%RET%"=="0" echo [HIBA] Ellenorzes sikertelen. Kod: %RET%
REM TANANYAG - Csak 0-s kilepesi kodnal irunk sikert.
if "%RET%"=="0" echo [OK] Ellenorzes kesz.
REM TANANYAG - Pause segit a hiba elolvasasaban is.
pause
REM TANANYAG - A hivonak tovabbitjuk a hibakodot; automatizalasban ez fontos.
exit /b %RET%
