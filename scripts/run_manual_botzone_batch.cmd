@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 2
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B -m integrations.botzone.manual_batch %*
) else (
  python -B -m integrations.botzone.manual_batch %*
)
set "_batch_exit=%ERRORLEVEL%"
popd
endlocal & exit /b %_batch_exit%
