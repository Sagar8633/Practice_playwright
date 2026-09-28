@echo off
rem ===========================================================================
rem ONE-TIME SETUP on a new machine. Run this once, from inside the folder.
rem
rem     setup.bat
rem
rem It creates a virtual environment, installs the dependencies, downloads the
rem browser, and checks that the personal config files made the journey. It
rem does NOT log in and it does NOT touch the Naukri profile - the last step
rem prints what to run next.
rem
rem Needs: Python 3.9+ on PATH, and an internet connection.
rem ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo   [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: "python" is not on PATH.
    echo   Install Python 3.9 or newer from python.org and TICK
    echo   "Add Python to PATH" during the install, then run setup.bat again.
    echo.
    exit /b 1
)
python --version

echo.
echo   [2/5] Creating the virtual environment in .venv ...
if exist ".venv\Scripts\python.exe" (
    echo   .venv already exists - reusing it.
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo   ERROR: could not create .venv
        exit /b 1
    )
)
set "PY=.venv\Scripts\python.exe"

echo.
echo   [3/5] Installing dependencies ...
"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo   ERROR: pip install failed.
    exit /b 1
)

echo.
echo   [4/5] Downloading the browser ^(about 150 MB, one time^) ...
"%PY%" -m playwright install chromium
if errorlevel 1 (
    echo   ERROR: playwright install failed.
    exit /b 1
)

echo.
echo   [5/5] Checking the personal config files ...
rem These are gitignored, so a git clone will NOT bring them. If the folder was
rem copied or unzipped they will be here. If any is missing, the copy was
rem incomplete and the tool will refuse to run rather than invent the values.
set "MISSING="
if not exist "jobs.yaml"                  set "MISSING=%MISSING% jobs.yaml"
if not exist "resume\resume.yaml"         set "MISSING=%MISSING% resume\resume.yaml"
if not exist "changes.yaml"               set "MISSING=%MISSING% changes.yaml"
if not exist "scripts\profile_edits.yaml" set "MISSING=%MISSING% scripts\profile_edits.yaml"

if defined MISSING (
    echo.
    echo   WARNING - these personal config files are missing:
    echo      %MISSING%
    echo.
    echo   They are gitignored on purpose, so they never arrive via git.
    echo   Copy them across from the original folder before running a scan.
) else (
    echo   All four personal config files present.
)

echo.
"%PY%" -m pytest tests\ -q
echo.
"%PY%" main.py --roles

echo.
echo   ======================================================================
echo   SETUP DONE. Two commands left, both need you at the keyboard:
echo.
echo       .venv\Scripts\python.exe main.py --login
echo           A browser window opens. SIGN IN INSIDE THAT WINDOW - a login
echo           in your normal Edge or Chrome is invisible to it. It saves the
echo           session itself and closes.
echo.
echo       .venv\Scripts\python.exe main.py --extract
echo           Scrapes the profile into data\. Nothing else runs without it.
echo.
echo   Then, to schedule the hourly scans:
echo       powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1
echo   ======================================================================
echo.
endlocal
