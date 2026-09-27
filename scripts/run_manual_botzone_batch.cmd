@echo off
setlocal
set "_batch_wait=1"
if /I "%~1"=="--no-pause" goto :without_pause
call :run_batch %*
goto :after_run

:without_pause
set "_batch_wait=0"
shift
call :run_batch %1 %2 %3 %4 %5 %6 %7 %8 %9

:after_run
set "_batch_exit=%ERRORLEVEL%"
if "%_batch_wait%"=="1" (
  echo.
  echo batch_window_exit=%_batch_exit%
  echo Press any key to close this window.
  pause >nul
)
endlocal & exit /b %_batch_exit%

:run_batch
pushd "%~dp0.."
if errorlevel 1 (
  echo batch_error category=repository_directory_unavailable exit=2
  exit /b 2
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B -m integrations.botzone.manual_batch %*
) else (
  where.exe python.exe >nul 2>&1
  if errorlevel 1 (
    echo batch_error category=python_unavailable exit=2
    popd
    exit /b 2
  )
  python -B -m integrations.botzone.manual_batch %*
)
set "_batch_exit=%ERRORLEVEL%"
popd
exit /b %_batch_exit%
