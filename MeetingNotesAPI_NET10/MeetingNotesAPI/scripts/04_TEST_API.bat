@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 04_TEST_API.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - A tesztben beallitott valtozok a batch futasakor elmulnak.
setlocal
REM TANANYAG - A teszt mindig a projekt gyokermappajabol indul.
cd /d "%~dp0.."
REM TANANYAG - A TestApi.ps1 opcionalis MP3 utvonalat kap; a %~1 leveszi a kulso idezojeleket.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TestApi.ps1" -AudioPath "%~1"
REM TANANYAG - A PowerShell teszt valodi eredmenykodjat olvassuk ki.
set "RET=%ERRORLEVEL%"
REM TANANYAG - A vegeredmeny kulon sorban jelenik meg.
echo.
REM TANANYAG - Hibas HTTP vagy MP3 tesztnel jelzest ad.
if not "%RET%"=="0" echo [HIBA] API teszt sikertelen. Kod: %RET%
REM TANANYAG - Sikeres ellenorzesnel kiirja, hogy a teszt lefutott.
if "%RET%"=="0" echo [OK] API teszt kesz.
REM TANANYAG - A konzol ne tunjon el hiba eseten.
pause
REM TANANYAG - A BAT a PowerShell kilepesi kodjat adja vissza.
exit /b %RET%
