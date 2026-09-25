@echo off
setlocal
set "_manual_wait=1"
if /I "%~1"=="--no-pause" set "_manual_wait=0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_manual_botzone.ps1"
set "_manual_exit=%ERRORLEVEL%"
if "%_manual_wait%"=="1" (
  echo.
  echo Manual Botzone launcher finished. Press any key to close this window.
  pause >nul
)
endlocal & exit /b %_manual_exit%
