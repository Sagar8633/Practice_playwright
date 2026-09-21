# Register the Naukri Remote Job Finder to run 3 times a day via Task Scheduler.
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_naukri_scan.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_naukri_scan.ps1 -Remove
#
# Times are deliberately off the hour, matching the other finders' pattern.
# Tasks run interactively because Akamai blocks headless Chromium.

param(
    [switch]$Remove,
    [string[]]$Times = @("08:58", "13:28", "18:18")
)

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$prefix = "NaukriRemoteFinder"
$batch  = Join-Path $root "naukri_scan.bat"

if (-not (Test-Path $batch)) {
    throw "Cannot find $batch"
}

Get-ScheduledTask -TaskName "$prefix*" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Removing existing task $($_.TaskName)"
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    }

if ($Remove) {
    Write-Host "Naukri remote finder unscheduled."
    return
}

$action = New-ScheduledTaskAction -Execute $batch -WorkingDirectory $root

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
        -Description "Naukri remote job finder - run $i of $($Times.Count)." | Out-Null
    Write-Host "Scheduled $name at $time"
}

Write-Host ""
Write-Host "Check:   Get-ScheduledTask -TaskName '$prefix*'"
Write-Host "Run now: Start-ScheduledTask -TaskName '$prefix-1'"
Write-Host "Remove:  ...\schedule_naukri_scan.ps1 -Remove"
Write-Host ""
Write-Host "Unlimited results per run - rewrites data\naukri-remote-jobs-<date>.html"
