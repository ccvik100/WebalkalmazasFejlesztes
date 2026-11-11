@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 06_BUILD_ELLENORZES.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - Csak a batch futasan belul letezo valtozo-teruletet nyit.
setlocal
REM TANANYAG - A projekt gyokerkonyvtaraba valtunk.
cd /d "%~dp0.."
REM TANANYAG - Jelzi, hogy a NET10 valodi forditasat vizsgaljuk, nem csak a fajlok letezeset.
echo === MeetingNotesAPI NET10 forditasi ellenorzes ===
REM TANANYAG - A WHERE a PATH-ban keresi a dotnet.exe parancsot.
where dotnet >nul 2>nul
REM TANANYAG - Nem folytatjuk a restore-t, ha nincs SDK.
if errorlevel 1 (
REM TANANYAG - Jol ertheto elofeltetel-hibat jelenit meg.
 echo [HIBA] A dotnet parancs nem talalhato. Telepitsd a .NET 10 SDK-t.
REM TANANYAG - Ablakot nyitva tartja hibakezeleskor.
 pause
REM TANANYAG - 2-es kod jelzi az elofeltetel hianyat.
 exit /b 2
)
REM TANANYAG - Kilistazza a tenylegesen telepitett SDK valtozatokat.
dotnet --list-sdks
REM TANANYAG - A kimenetet tagoljuk.
echo.
REM TANANYAG - Elsokent NuGet csomagok visszaallitasa szukseges.
echo [1/2] NuGet restore...
REM TANANYAG - A dotnet restore beszerzi a projekt csomaghivatkozasait.
dotnet restore "MeetingNotesAPI.csproj"
REM TANANYAG - Restore-hibanal azonnal a failed cimkere ugrik.
if errorlevel 1 goto failed
REM TANANYAG - Jelzi a kovetkezo, kodforditasi lepes kezdetet.
echo [2/2] Build...
REM TANANYAG - A dotnet build Debug osszeallitast keszit ujabb restore nelkul.
dotnet build "MeetingNotesAPI.csproj" -c Debug --no-restore
REM TANANYAG - Forditasi hibanal nem allitjuk, hogy a projekt mukodik.
if errorlevel 1 goto failed
REM TANANYAG - Csak sikeres C# forditasnal jelenik meg az OK felirat.
echo [OK] A NET10 API lefordult.
REM TANANYAG - Ablakot nyitva hagyjuk, hogy a log olvashato legyen.
pause
REM TANANYAG - 0 kod a sikeres forditas jele.
exit /b 0
REM TANANYAG - A failed cimeknel osszegyujtjuk a build/restore hibakat.
:failed
REM TANANYAG - A reszletes hiba korabban a dotnet kimeneteben lathato.
echo [HIBA] A MeetingNotesAPI forditasa sikertelen. A fenti hibakat javitsd a teszteles elott.
REM TANANYAG - Ablak nyitva marad hibas forditas eseten.
pause
REM TANANYAG - 1 kod jelzi a sikertelen forditast.
exit /b 1
