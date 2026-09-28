@echo off
rem Hourly job scan, 08:00-20:00. Registered by scripts\schedule_hourly.ps1.
rem
rem THIS RUN SENDS NOTHING. It searches, scores against the profile, and writes:
rem
rem     data\jobs\openings-<date>.html    the tracker page to work through
rem     data\jobs\job-matches-<date>.xlsx ranked, with apply links
rem     data\jobs\results-<date>.json     raw, and the corpus for demand counts
rem
rem WHY HOURLY IS WORTH IT HERE AND NOT FOR --refresh:
rem   New postings appear through the working day and early applicants get read.
rem   --new-only means each run only reports what has not already appeared on an
rem   earlier run, tracked in data\jobs\seen.json - so twelve runs a day produce
rem   twelve short lists of genuinely new jobs, not twelve copies of the same
rem   list. The profile refresh is the opposite case: its timestamp is a DATE,
rem   so it is capped at once a day inside naukri\refresh.py. See
rem   daily_refresh.bat.
rem
rem Most runs will find nothing. That is the correct result, not a failure -
rem it exits 2 rather than erroring when a 24-hour filter comes back empty.
rem
rem Locations are passed explicitly because main.py defaults --locations to
rem "Pune,Ahmedabad,Gurgaon", which is not this profile's list.
rem
rem If it starts failing, the saved session has expired - run:
rem     python main.py --login
cd /d "%~dp0"

rem Task Scheduler does not inherit your shell's PATH, so prefer a repo venv
rem over whatever "python" happens to resolve to under the scheduler account.
set "PY=python"
if exist "..\venv\Scripts\python.exe" set "PY=..\venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" main.py --jobs-export --top 30 --posted-days 1 --new-only --locations "Pune,Nashik,Aurangabad"
