@echo off
rem Naukri Remote Job Finder - daily scan
rem Called by Task Scheduler. Opens a visible browser (Akamai blocks headless).

call d:\Practice_Playwright\venv\Scripts\Activate.ps1
if errorlevel 1 exit /b 1

python -m naukri_remote_finder.main --search
exit /b %errorlevel%
