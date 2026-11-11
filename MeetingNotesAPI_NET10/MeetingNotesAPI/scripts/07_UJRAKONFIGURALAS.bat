@echo off
REM MeetingNotesAPI - helyreallitas elveszett tenantkulcs utan.
REM Masold ezt ES a 07_UJRAKONFIGURALAS.ps1 fajlt a MeetingNotesAPI\scripts mappaba.
REM Az OmegaAI adatbazisaihoz nem nyul; szukseg eseten uj tenantot regisztral.
setlocal
cd /d "%~dp0.."
echo ============================================
echo MeetingNotesAPI - tenant ujraregisztralas
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp007_UJRAKONFIGURALAS.ps1" %*
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
    echo [OK] Az uj tenant es a kulcsok elmentve.
    echo A MeetingNotesAPI-t ujra kell inditani.
) else (
    echo [HIBA] A helyreallitas nem fejezodott be. Kod: %CODE%
)
pause
exit /b %CODE%
