# Build a zip of this setup, ready to copy to another machine.
#
#   powershell -ExecutionPolicy Bypass -File scripts\make_portable.ps1
#
# Writes prashant_naukri_screener_<date>.zip next to the project folder.
#
# WHAT IS DELIBERATELY LEFT OUT, and why each one:
#
#   data\state.json   IS the Naukri login. Copying a live session to another
#                     machine means two machines holding the same credential,
#                     and it expires in a few weeks anyway. The new machine
#                     signs in once with --login. This is the important
#                     exclusion - everything else here is just size.
#   data\             scraped profile, scan results, spreadsheets, study pages.
#                     All of it regenerates from --extract and a scan, and it
#                     is the bulkiest thing in the folder.
#   logs\             local run history, means nothing on another machine.
#   .venv, venv       platform-specific binaries. setup.bat rebuilds them.
#   __pycache__       compiled bytecode, rebuilt on first run.
#   .git              history is not needed to run the tool.
#
# WHAT IS DELIBERATELY KEPT, because a git clone would NOT bring it:
#
#   jobs.yaml, changes.yaml, resume\resume.yaml, scripts\profile_edits.yaml
#   and the built resume files. Every one is gitignored - that is the whole
#   point of the gitignore - so cloning the repo on the new laptop and
#   expecting these to appear is the one mistake that wastes an evening.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$name = Split-Path -Leaf $root
$stamp = Get-Date -Format "yyyy-MM-dd"
$zip  = Join-Path (Split-Path -Parent $root) "${name}_$stamp.zip"

$staging = Join-Path $env:TEMP "naukri_portable_$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

try {
    Write-Host "Staging from $root ..."

    $exclude = @('.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'data', 'logs', '.idea', '.vscode')

    robocopy $root (Join-Path $staging $name) /E /NFL /NDL /NJH /NJS /NC /NS /NP `
        /XD $exclude `
        /XF '*.pyc' '*.pyo' | Out-Null
    # robocopy uses exit codes 0-7 for success; 8+ is a real failure.
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }

    # Recreate the empty data/ and logs/ the tool expects to find.
    foreach ($d in @('data', 'logs')) {
        New-Item -ItemType Directory -Path (Join-Path $staging "$name\$d") -Force | Out-Null
    }
    New-Item -ItemType File -Path (Join-Path $staging "$name\data\.gitkeep") -Force | Out-Null

    # Belt and braces: prove the session did not sneak through.
    $leaked = Get-ChildItem -Path $staging -Recurse -Filter 'state.json' -ErrorAction SilentlyContinue
    if ($leaked) { throw "state.json found in the staging copy - refusing to package a live session." }

    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $staging $name) -DestinationPath $zip -CompressionLevel Optimal

    $mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Wrote $zip  ($mb MB)"
    Write-Host ""
    Write-Host "On the other laptop:"
    Write-Host "  1. Unzip it anywhere, e.g. C:\naukri"
    Write-Host "  2. setup.bat"
    Write-Host "  3. .venv\Scripts\python.exe main.py --login     (sign in IN that browser window)"
    Write-Host "  4. .venv\Scripts\python.exe main.py --extract"
    Write-Host "  5. powershell -ExecutionPolicy Bypass -File scripts\schedule_hourly.ps1"
    Write-Host ""
    Write-Host "See DEPLOY.md for what each step does and what can go wrong."
}
finally {
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
}
