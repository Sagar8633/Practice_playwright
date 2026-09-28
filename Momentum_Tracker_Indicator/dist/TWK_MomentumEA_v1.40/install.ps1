<#
  TWK Momentum EA - installer for MetaTrader 5 (Windows)

  Copies the two EAs (TWK_MomentumEA v1.40 and the simple TWK_PineEA, both with the chart Tracker built in),
  the Tracker indicator and the GOLD presets into an MT5 data folder,
  then (if MetaEditor is found) recompiles them on this machine's MT5 build.
  If a recompile fails, the shipped ready-to-run .ex5 is put back.

  Usage (use install.bat: it bypasses the PowerShell execution policy)
    install.bat                              pick the terminal from a list
    install.bat -DataFolder "<path>"         explicit data folder (File > Open Data Folder), portable install dir, or its MQL5 folder
    install.bat -NoCompile                   keep the shipped .ex5 files, do not recompile
#>
param(
    [string]$DataFolder = "",
    [switch]$NoCompile
)

$ErrorActionPreference = 'Stop'
$pkg = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $pkg 'MQL5'
if (-not (Test-Path -LiteralPath $src)) { throw "MQL5 folder not found next to install.ps1 ($src). Extract the whole zip first." }

# cmd.exe turns  "C:\path\" -NoCompile  into one argument (backslash-quote is a literal quote):
# split it back into the path and any trailing switch.
if ($DataFolder -match '^([^"]*)"\s*(.*)$') {
    $DataFolder = $Matches[1]
    if ($Matches[2] -match '(?i)(^|\s)-NoCompile\b') { $NoCompile = $true }
}

function Read-Origin([string]$folder) {
    $origin = Join-Path $folder 'origin.txt'
    if (Test-Path -LiteralPath $origin) {
        try { return (Get-Content -LiteralPath $origin -Encoding Unicode -Raw).Trim() } catch { }
    }
    return ''
}

function Get-TerminalFolders {
    $root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    if (-not (Test-Path -LiteralPath $root)) { return @() }
    $list = @()
    foreach ($d in Get-ChildItem -LiteralPath $root -Directory) {
        if (-not (Test-Path -LiteralPath (Join-Path $d.FullName 'MQL5'))) { continue }
        $list += [pscustomobject]@{ Path = $d.FullName; Install = (Read-Origin $d.FullName) }
    }
    return $list
}

function Resolve-DataFolder([string]$p) {
    $p = $p.Trim().Trim('"').TrimEnd('\')
    if ((Split-Path $p -Leaf) -ieq 'MQL5') { $p = Split-Path $p -Parent }
    if (-not (Test-Path -LiteralPath (Join-Path $p 'MQL5'))) {
        throw "'$p' does not contain an MQL5 folder. In MT5 use File > Open Data Folder and pass that path."
    }
    $install = Read-Origin $p
    if ($install -eq '') { $install = $p }          # portable install: data folder = install folder
    return [pscustomobject]@{ Path = $p; Install = $install }
}

# ---- choose the terminal ------------------------------------------------------
if ($DataFolder -ne '') {
    $target = Resolve-DataFolder $DataFolder
} else {
    $found = @(Get-TerminalFolders)
    if ($found.Count -eq 0) {
        throw "No MetaTrader 5 data folder found under $env:APPDATA\MetaQuotes\Terminal. Install MT5 and start it once, or run: install.bat -DataFolder `"<path from File > Open Data Folder>`""
    } elseif ($found.Count -eq 1) {
        $target = $found[0]
    } else {
        Write-Host "Several MetaTrader 5 terminals found:" -ForegroundColor Cyan
        for ($i = 0; $i -lt $found.Count; $i++) {
            $label = if ($found[$i].Install) { $found[$i].Install } else { '(unknown install)' }
            Write-Host ("  [{0}] {1}`n      {2}" -f ($i + 1), $label, $found[$i].Path)
        }
        $choice = Read-Host "Install into which terminal? (1-$($found.Count))"
        $n = 0
        if (-not [int]::TryParse($choice, [ref]$n) -or $n -lt 1 -or $n -gt $found.Count) { throw "Invalid choice '$choice'." }
        $target = $found[$n - 1]
    }
}

$mql5 = Join-Path $target.Path 'MQL5'
Write-Host "`nInstalling into: $mql5" -ForegroundColor Cyan

# ---- copy files -----------------------------------------------------------------
$copies = @(
    @{ From = 'Experts\TWK';    To = 'Experts\TWK' },
    @{ From = 'Indicators\TWK'; To = 'Indicators\TWK' },
    @{ From = 'Presets';        To = 'Presets' }
)
foreach ($c in $copies) {
    $from = Join-Path $src $c.From
    $to   = Join-Path $mql5 $c.To
    New-Item -ItemType Directory -Force -Path $to | Out-Null
    foreach ($f in Get-ChildItem -LiteralPath $from -File) {
        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $to $f.Name) -Force
        Write-Host ("  copied {0}\{1}" -f $c.To, $f.Name)
    }
}

# ---- recompile on this machine (optional) -----------------------------------------
# MetaEditor deletes the old .ex5 when a compile fails, so the shipped binary is restored in that case.
# The indicator is compiled FIRST: the EA embeds whatever TWK_Tracker_MT5.ex5 is on disk (#resource).
if (-not $NoCompile) {
    $me = if ($target.Install) { Join-Path $target.Install 'MetaEditor64.exe' } else { '' }
    if ($me -and (Test-Path -LiteralPath $me)) {
        foreach ($rel in @('Indicators\TWK\TWK_Tracker_MT5.mq5', 'Experts\TWK\TWK_MomentumEA.mq5', 'Experts\TWK\TWK_PineEA.mq5')) {
            $file   = Join-Path $mql5 $rel
            $ex5Rel = [System.IO.Path]::ChangeExtension($rel, '.ex5')
            $log    = [System.IO.Path]::ChangeExtension($file, '.compile.log')
            Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
            # /inc makes <Trade\Trade.mqh> resolve inside THIS data folder (needed for portable installs)
            Start-Process -FilePath $me -ArgumentList "/compile:`"$file`"", "/inc:`"$mql5`"", "/log:`"$log`"" -Wait -WindowStyle Hidden
            $result = ''
            if (Test-Path -LiteralPath $log) {
                $result = (Get-Content -LiteralPath $log -Encoding Unicode | Where-Object { $_ -match 'Result:' } | Select-Object -Last 1)
            }
            $ok = ($result -match '(\d+) errors?') -and ([int]$Matches[1] -eq 0)
            if ($ok) {
                Write-Host "  compiled $rel  -> $result" -ForegroundColor Green
            } else {
                Copy-Item -LiteralPath (Join-Path $src $ex5Rel) -Destination (Join-Path $mql5 $ex5Rel) -Force
                $why = if ($result) { $result } else { 'no compile result' }
                Write-Host "  recompile of $rel did not succeed ($why) - the shipped ready-to-run .ex5 was restored. Log: $log" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  MetaEditor64.exe not found - using the shipped .ex5 files (built with MT5 build 6198)." -ForegroundColor Yellow
    }
}

foreach ($must in @('Experts\TWK\TWK_MomentumEA.ex5', 'Experts\TWK\TWK_PineEA.ex5', 'Indicators\TWK\TWK_Tracker_MT5.ex5')) {
    if (-not (Test-Path -LiteralPath (Join-Path $mql5 $must))) { throw "$must is missing after install - copy it from the package's MQL5 folder by hand." }
}

# ---- next steps ---------------------------------------------------------------------
Write-Host @"

Done. Next steps (details in INSTALL.md):
  1. In MetaTrader 5 log in to a DEMO account (master password, not investor).
  2. Make the toolbar 'Algo Trading' button green.
  3. Navigator (Ctrl+N) > Expert Advisors: right-click > Refresh if TWK is not listed.
  4. Open a GOLD chart with the same timeframe as SignalTimeframe (M1 preset: M1 chart; M3 preset: M3 chart).
     Gold is GOLD, XAUUSD, XAUUSDm ... depending on the broker.
  5. Drag  Expert Advisors > TWK > TWK_MomentumEA  (full bot)  or  TWK_PineEA  (simple Pine trades)  onto the chart.
       Common tab : tick 'Allow Algo Trading'
       Inputs tab : Load > TWK_GOLD_M1_demo.set / TWK_GOLD_M3_demo.set  (TWK_MomentumEA)
                    or  TWK_Pine_GOLD_M1_demo.set                      (TWK_PineEA)
  6. Experts tab (Ctrl+T): the start line must show the preset's lot, and [CONFIG] its trailing points,
     hard SL and re-flip setting. The purple line, arrows and SL/TP boxes appear on the chart by themselves.
  Check the [SYMBOL] line: the presets assume digits=2 (point 0.01). See INSTALL.md if your broker differs.
"@ -ForegroundColor Cyan
