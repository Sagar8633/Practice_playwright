@echo off
rem Global Remote Job Finder - daily scan
rem Called by Task Scheduler. Naukri needs a visible browser (Akamai);
rem global boards run headless internally.

call d:\Practice_Playwright\venv\Scripts\Activate.ps1
if errorlevel 1 exit /b 1

python -m global_remote_finder.main --search
exit /b %errorlevel%
