@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 03_INDITAS.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - A futtatas valtozoit a jelen parancsfajlban tartjuk.
setlocal
REM TANANYAG - A projekt mappajaba valt, mert dotnet run innen keresi a .csproj fajlt.
cd /d "%~dp0.."
REM TANANYAG - Ha forrasprojektet talalunk, akkor fejlesztoi inditast valasztunk.
if exist "MeetingNotesAPI.csproj" (
REM TANANYAG - A megadott Visual Studio launch profillal inditjuk a NET10 szervert.
  dotnet run --project "MeetingNotesAPI.csproj" --launch-profile "MeetingNotesAPI - Visual Studio"
REM TANANYAG - Publikalt kornyezetben a projektfajl helyett a kesz DLL-t keressuk.
) else if exist "MeetingNotesAPI.dll" (
REM TANANYAG - A publikalt DLL elindul a helyi 5200-as porton; eles szerveren a bind/HTTPS kulon beallitando.
  dotnet "MeetingNotesAPI.dll" --urls http://127.0.0.1:5200
REM TANANYAG - Ha sem projekt, sem DLL nincs, hibas helyrol indult a batch.
) else (
REM TANANYAG - Jelzi, hogy a futtatashoz szukseges allomany hianyzik.
  echo [HIBA] Nincs .csproj vagy publikalasi DLL az inditasi konyvtarban.
REM TANANYAG - 2-es hibakoddal kilepunk az erdemi inditas nelkul.
  exit /b 2
)
REM TANANYAG - A dotnet folyamat befejezesi kodjat megorizzuk.
set "RET=%ERRORLEVEL%"
REM TANANYAG - A kilepes oka/kodja a konzolban olvashato marad.
echo [INFO] Az API kilepett. Kod: %RET%
REM TANANYAG - Pause, hogy a fejleszto lassa az esetleges futasideju hibat.
pause
REM TANANYAG - Tovabbitja a dotnet hibakodjat.
exit /b %RET%
