# Register the hourly job scan (08:00-20:00) plus the once-a-day profile nudge.
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1 -Remove
#
# Two tasks are registered, and the split is deliberate:
#
#   NaukriHourlyScan     08:07, repeating every hour for 12 hours -> 13 runs,
#                        the last at 20:07. Sends nothing. Each run reports only
#                        postings no earlier run has seen (--new-only), so this
#                        is twelve short lists of new jobs, not twelve copies of
#                        one list.
#
#   NaukriDailyRefresh   08:02, once. Bumps the profile's last-modified stamp.
#
# WHY THE REFRESH IS NOT ALSO HOURLY. naukri\refresh.py refuses a second bump on
# the same day, and its docstring gives the reason: the Naukri timestamp records
# a DATE, so runs two through thirteen change nothing a recruiter search can
# see, while adding twelve more browser sessions and twelve more edit requests
# against a live profile. Scheduling it hourly would not fail - it would simply
# print "already refreshed today" twelve times. If you want to prove that to
# yourself, run daily_refresh.bat twice in a row and read the second output.
#
# Times are off the hour on purpose. Every scheduler on the planet fires at :00,
# and a run that always starts at exactly 09:00 is a more obvious pattern than
# one that starts at 09:07.
#
# Both tasks run INTERACTIVELY (not "whether user is logged on or not"): Naukri
# serves "Access Denied" to headless Chromium, so a real desktop session is
# needed for the browser to draw into. A visible browser window opens on each
# run. The laptop must be awake and signed in - a locked screen is fine, a
# sleeping laptop is not.

param(
    [switch]$Remove,
    [string]$StartTime      = "08:07",
    [int]   $RepeatHours    = 1,
    [int]   $DurationHours  = 12,
    [string]$RefreshTime    = "08:02",

    # Wake the machine from sleep to run each scan.
    #
    # OFF BY DEFAULT, and the default is the right one for a laptop that gets
    # closed and carried around: -WakeToRun will wake it in a bag, thirteen
    # times a day, to open a browser nobody is looking at. That is a hot
    # laptop and a flat battery.
    #
    # Turn it ON for a machine that stays put and plugged in - a desk laptop
    # left closed, a spare PC, a mini-PC acting as the always-on box. There it
    # is the difference between thirteen runs a day and none.
    #
    # It cannot wake a machine that is hibernated or powered off. Nothing can.
    [switch]$WakeToRun
)

$ErrorActionPreference = "Stop"

$root        = Split-Path -Parent $PSScriptRoot
$scanBatch    = Join-Path $root "hourly_jobs.bat"
$refreshBatch = Join-Path $root "daily_refresh.bat"

foreach ($f in @($scanBatch, $refreshBatch)) {
    if (-not (Test-Path $f)) { throw "Cannot find $f" }
}

# Clear previous registrations first, so re-running updates the schedule rather
# than erroring or leaving stale tasks behind.
Get-ScheduledTask -TaskName "NaukriHourlyScan","NaukriDailyRefresh" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Removing existing task $($_.TaskName)"
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    }

if ($Remove) {
    Write-Host "Hourly scan and daily refresh unscheduled."
    return
}

# THE BATTERY FLAGS ARE LOAD-BEARING ON A LAPTOP, and this is the whole reason
# they are spelled out rather than left to defaults. Task Scheduler defaults
# DisallowStartIfOnBatteries and StopIfGoingOnBatteries to TRUE, and
# New-ScheduledTaskSettingsSet inherits both unless told otherwise. On the
# source machine that silently cost two of three runs a day:
#
#   - a run due while unplugged never starts, and the trigger is NOT retried
#   - a run that starts on mains and is unplugged mid-way is killed, surfacing
#     as 0x8007042B (ERROR_PROCESS_ABORTED)
#
# Both look identical from outside: no page, no log line, no error. On a laptop
# that is closed and carried around all day - which is the normal case for the
# person this is being set up for - leaving these at their defaults would mean
# most of the thirteen runs never happen.
#
# MultipleInstances IgnoreNew matters more at hourly cadence than at three-a-day:
# if a scan overruns its hour, the next trigger is skipped rather than starting a
# second browser on top of the first.
$settingsArgs = @{
    StartWhenAvailable        = $true
    DontStopOnIdleEnd         = $true
    AllowStartIfOnBatteries   = $true
    DontStopIfGoingOnBatteries = $true
    ExecutionTimeLimit        = (New-TimeSpan -Minutes 50)
    MultipleInstances         = 'IgnoreNew'
}
if ($WakeToRun) { $settingsArgs.WakeToRun = $true }

$settings = New-ScheduledTaskSettingsSet @settingsArgs

if ($WakeToRun) {
    Write-Host "WakeToRun is ON - this machine will wake from sleep for each run."
    Write-Host "  Only sensible on a machine that stays put and plugged in."
    Write-Host ""
}

# --- hourly scan -----------------------------------------------------------
$scanTrigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$scanTrigger.Repetition = (New-ScheduledTaskTrigger -Once -At $StartTime `
    -RepetitionInterval (New-TimeSpan -Hours $RepeatHours) `
    -RepetitionDuration (New-TimeSpan -Hours $DurationHours)).Repetition

Register-ScheduledTask `
    -TaskName "NaukriHourlyScan" `
    -Action   (New-ScheduledTaskAction -Execute $scanBatch -WorkingDirectory $root) `
    -Trigger  $scanTrigger `
    -Settings $settings `
    -Description "Naukri job scan, hourly $StartTime for $DurationHours h. Sends nothing." | Out-Null

$last = ([datetime]$StartTime).AddHours($DurationHours).ToString("HH:mm")
$runs = [math]::Floor($DurationHours / $RepeatHours) + 1
Write-Host "Scheduled NaukriHourlyScan   $StartTime, every ${RepeatHours}h for ${DurationHours}h -> $runs runs, last at $last"

# --- daily refresh ---------------------------------------------------------
Register-ScheduledTask `
    -TaskName "NaukriDailyRefresh" `
    -Action   (New-ScheduledTaskAction -Execute $refreshBatch -WorkingDirectory $root) `
    -Trigger  (New-ScheduledTaskTrigger -Daily -At $RefreshTime) `
    -Settings $settings `
    -Description "Naukri profile last-modified nudge. Once a day by design - see naukri\refresh.py." | Out-Null

Write-Host "Scheduled NaukriDailyRefresh $RefreshTime, once a day"
Write-Host ""
Write-Host "Check them:   Get-ScheduledTask -TaskName 'Naukri*' | Format-Table TaskName,State"
Write-Host "Run one now:  Start-ScheduledTask -TaskName 'NaukriHourlyScan'"
Write-Host "Last result:  Get-ScheduledTaskInfo -TaskName 'NaukriHourlyScan'"
Write-Host "Remove both:  ...\schedule_hourly.ps1 -Remove"
Write-Host ""
Write-Host "Each scan rewrites data\jobs\openings-<date>.html - the tracker page."
Write-Host "Nothing here submits an application. That needs jobs_agent.bat and"
Write-Host "answer_questionnaires: true in jobs.yaml, neither of which is on."
