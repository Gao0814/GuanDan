@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_manual_botzone.ps1"
set "_manual_exit=%ERRORLEVEL%"
endlocal & exit /b %_manual_exit%
