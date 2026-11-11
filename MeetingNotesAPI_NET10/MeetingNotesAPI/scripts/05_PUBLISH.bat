@echo off
REM ================================================================
REM OKTATOI MAGYARAZAT - 05_PUBLISH.bat
REM A kommentek oktatasi celokat szolgalnak; a parancsok azonosak.
REM A CMD kulonosebb kodolas nelkul is tudja olvasni (ASCII, BOM nelkul).
REM ================================================================
REM TANANYAG - SETLOCAL izolalja az ideiglenes parancssori valtozokat.
setlocal
REM TANANYAG - A projekt mappajaba valtunk a fordithatosag erdekeben.
cd /d "%~dp0.."
REM TANANYAG - A dotnet publish Release osszeallitast keszit a publish/MeetingNotesAPI mappaba.
dotnet publish "MeetingNotesAPI.csproj" -c Release -o "%~dp0..\publish\MeetingNotesAPI"
REM TANANYAG - A publikalas kilepesi kodjat elmentjuk.
set "RET=%ERRORLEVEL%"
REM TANANYAG - Csak sikeres build utan tekintjuk telepitheto allapotunak.
if "%RET%"=="0" (
REM TANANYAG - Megmutatja, honnan masolhatok a publikalasi fajlok a Rackforest szerverre.
 echo [OK] Szerverre masolando fajlok: publish\MeetingNotesAPI
REM TANANYAG - A titkos konfiguracio nem resze a publikalando csomagnak: szerveren kulon kell rogzitani.
 echo [INFO] A privat kulcsfajlt ne masold automatikusan. A cel szerveren kulon konfigurald.
REM TANANYAG - Sikertelen publish eseten kulon hibavagba jutunk.
) else (
REM TANANYAG - A forditas/restore hibakodja segit a diagnosztikaban.
 echo [HIBA] Publikalas megszakadt. Kod: %RET%
)
REM TANANYAG - Megall a vegen, hogy a kimenet elolvashato legyen.
pause
REM TANANYAG - A hivo scriptszamara is elerheto a valodi eredmeny.
exit /b %RET%
