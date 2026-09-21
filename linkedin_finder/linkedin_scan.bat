@echo off
rem LinkedIn Remote Job Finder - 3x daily scan
rem Called by Task Scheduler. Opens a visible browser and searches remote jobs.

call d:\Practice_Playwright\venv\Scripts\Activate.ps1
if errorlevel 1 exit /b 1

python -m linkedin_finder.main --search --pages 1
exit /b %errorlevel%
