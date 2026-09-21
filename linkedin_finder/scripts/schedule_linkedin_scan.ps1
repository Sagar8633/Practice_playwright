# Register the LinkedIn Remote Job Finder to run 3 times a day via Task Scheduler.
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_linkedin_scan.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_linkedin_scan.ps1 -Remove
#
# Times are deliberately off the hour, matching the naukri_profile pattern, so
# the runs are less obvious as automation patterns.
#
# The tasks run interactively (not "whether user is logged on or not") because
# LinkedIn serves blocked pages to headless Chromium. A visible browser window
# opens while each run works.

param(
    [switch]$Remove,
    [string[]]$Times = @("08:55", "13:25", "18:15")
)

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$prefix = "LinkedInJobFinder"
$batch  = Join-Path $root "linkedin_scan.bat"

if (-not (Test-Path $batch)) {
    throw "Cannot find $batch"
}

# Clear any previous registration first, so re-running this script updates the
# schedule instead of erroring or leaving stale tasks behind.
Get-ScheduledTask -TaskName "$prefix*" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Removing existing task $($_.TaskName)"
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    }

if ($Remove) {
    Write-Host "LinkedIn job finder unscheduled."
    return
}

$action = New-ScheduledTaskAction -Execute $batch -WorkingDirectory $root

# Allow running on battery - the scan is a few minutes of browsing.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

$i = 0
foreach ($time in $Times) {
    $i++
    $name = "$prefix-$i"
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    Register-ScheduledTask `
        -TaskName $name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "LinkedIn remote job finder - run $i of $($Times.Count)." | Out-Null
    Write-Host "Scheduled $name at $time"
}

Write-Host ""
Write-Host "Check them with:   Get-ScheduledTask -TaskName '$prefix*'"
Write-Host "Run one now with:  Start-ScheduledTask -TaskName '$prefix-1'"
Write-Host "Stop them with:    ...\schedule_linkedin_scan.ps1 -Remove"
Write-Host ""
Write-Host "Each run rewrites data\linkedin-jobs-<date>.html"
