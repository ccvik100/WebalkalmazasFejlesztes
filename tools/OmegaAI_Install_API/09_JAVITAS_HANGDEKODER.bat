@echo off
setlocal
chcp 65001 >nul
REM OmegaAI 1.3: csak PyAV / hangfeldolgozo javitas, modellek megorzese.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\FixAudio.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo [OK] HANGDEKODER JAVITAS KESZ.) else (echo [HIBA] HANGDEKODER JAVITAS: hibakod %RC%.)
echo Nyomj meg egy gombot a bezarashoz.
pause >nul
exit /b %RC%
