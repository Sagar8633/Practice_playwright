@echo off
REM Start the SRK swing watcher. Double-click this, or point Task Scheduler at
REM it to have it come up by itself every morning. Leave the window open -
REM closing it stops the watch.
setlocal
cd /d "%~dp0"

set PY=d:\Practice_Playwright\venv\Scripts\python.exe
if not exist "%PY%" set PY=python

title SRK Swing Watcher - NSE F&O 15m
echo Starting the SRK swing watcher on the full F&O list...
echo Signals are logged to data\signals.csv
echo.
"%PY%" watch.py %*

echo.
echo Watcher stopped.
pause
