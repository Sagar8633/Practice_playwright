@echo off
echo ========================================
echo  LinkedIn Remote Job Finder
echo ========================================
echo.

echo Activating virtual environment...
call d:\Practice_Playwright\venv\Scripts\Activate.ps1

echo.
echo Choose an option:
echo   1. Login (one-time setup)
echo   2. Search remote jobs
echo   3. Search with custom keywords
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo.
    echo Starting LinkedIn login...
    python -m linkedin_finder.main --login
) else if "%choice%"=="2" (
    echo.
    echo Searching for remote jobs...
    python -m linkedin_finder.main --search
) else if "%choice%"=="3" (
    echo.
    set /p keywords="Enter keywords (comma-separated): "
    python -m linkedin_finder.main --search --keywords "%keywords%"
) else (
    echo Invalid choice.
)

echo.
pause