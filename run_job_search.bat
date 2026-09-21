@echo off
echo Activating virtual environment...
call d:\Practice_Playwright\venv\Scripts\Activate.ps1

echo.
echo Running job search tool...
python job_search.py

echo.
echo Job search complete! Check remote_jobs_report.html for results.
pause