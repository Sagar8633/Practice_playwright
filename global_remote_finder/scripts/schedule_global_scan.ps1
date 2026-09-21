# Register the Global Remote Job Finder to run 3 times a day via Task Scheduler.
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_global_scan.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_global_scan.ps1 -Remove
#
# Times are deliberately off the hour. Naukri needs a visible browser, the
# global boards run headless internally.

param(
    [switch]$Remove,
    [string[]]$Times = @("09:02", "13:32", "18:22")
)

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$prefix = "GlobalJobFinder"
$batch  = Join-Path $root "global_scan.bat"

if (-not (Test-Path $batch)) {
    throw "Cannot find $batch"
}

Get-ScheduledTask -TaskName "$prefix*" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Removing existing task $($_.TaskName)"
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    }

if ($Remove) {
    Write-Host "Global remote finder unscheduled."
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
        -Description "Global remote job finder (Naukri+RMOK+WWR+Remotive) - run $i of $($Times.Count)." | Out-Null
    Write-Host "Scheduled $name at $time"
}

Write-Host ""
Write-Host "Check:   Get-ScheduledTask -TaskName '$prefix*'"
Write-Host "Run now: Start-ScheduledTask -TaskName '$prefix-1'"
Write-Host "Remove:  ...\schedule_global_scan.ps1 -Remove"
Write-Host ""
Write-Host "Unlimited results - rewrites data\global-remote-jobs-<date>.html"
