# TWK Momentum EA v1.40: installing on another computer

This is an automated trading robot (Expert Advisor) for MetaTrader 5.
It trades the LONG/SHORT signals of the TWK Tracker (trade_with_kareena) indicator on GOLD, with volume, M1/M3 box and ADX filters.
- The stop loss is the indicator's pivot. With no pivot, or on a quick re-flip, it uses a hard SL instead (see `docs\RUN_GUIDE.md`). TP = 2 x the stop.
- Stops are trailed with the purple line, then a profit lock, then 1:1 trailing.
- The chart shows the purple line, the signals, TradingView-style SL/TP boxes and every trade by itself, also in the Strategy Tester.
- It **refuses to open trades on a real-money account** unless you deliberately switch that on (see Step 6).

## What is new in v1.40

- **One package.** The chart Tracker (purple line, LONG/SHORT arrows, SL/TP boxes) is built into `TWK_MomentumEA.ex5`. In the Strategy Tester you only pick the EA. Set the tester Period equal to the Signal timeframe.
- **Trade boxes.** Every real position is drawn from entry to exit, with its initial SL, TP, the trailing SL steps and the P/L. This needs a visual test or the live chart.
- **Hard SL** (`HardSL_M1` = 500 pts, plus one input per timeframe). It is used when there is no pivot, and on a **quick re-flip**: a signal a few bars after an opposite signal, whose pivot is older than that signal. That pivot is never used. `ReFlipAction` can also skip those trades.
- **New simple robot `TWK_PineEA`.** Every purple-line flip closes the trade and opens the new direction. It uses the exact Pine SL (pivot) and TP (`RewardRisk`, 1:2), trails on the purple line, and locks +900 pts at +1000 pts. It has no filters. See "Simple version" below.
- GOLD only: the BTCUSD presets were removed.

## What is in this package

| Path | What it is |
|---|---|
| `install.bat` / `install.ps1` | One-click installer: copies everything into MT5 and recompiles it there |
| `MQL5\Experts\TWK\` | The robots, ready to run: `TWK_MomentumEA.ex5` (full bot) and `TWK_PineEA.ex5` (simple Pine trades), + sources `.mq5` and `TWK_Core.mqh` |
| `MQL5\Indicators\TWK\` | The chart Tracker: `TWK_Tracker_MT5.ex5` + source. It is already built into the EA; these files are for recompiling |
| `MQL5\Presets\TWK_GOLD_M1_demo.set` | Settings for GOLD / XAUUSD M1: 0.02 lot, volume ratio 1.2 |
| `MQL5\Presets\TWK_Pine_GOLD_M1_demo.set` | Settings for TWK_PineEA on GOLD M1: 0.02 lot, RR 1:2, reverse on flip, purple trail, lock +900 at +1000 |
| `MQL5\Presets\TWK_GOLD_M3_demo.set` | Same, with 3-minute signals: distances ×1.8, Magic number 26092403 (see "Using another timeframe") |
| `docs\` | How it works, how it was validated against TradingView, run guide, Pine sources |
| `tools\` | Optional Python scripts: re-check MT5 values against the validated formulas, merge multi-core backtests (`merge_tester_slices.py`), compare M1 vs M3 (`m3_vs_m1_stats.py`) |
| `CHECKSUMS.txt` | SHA-256 of every file |

To check a file after copying, run this in PowerShell inside the extracted folder and compare with `CHECKSUMS.txt`:
`Get-FileHash -Algorithm SHA256 MQL5\Experts\TWK\TWK_MomentumEA.ex5`

## Requirements

- Windows with the **MetaTrader 5 desktop terminal**.
- It runs with any broker; a hedging account is preferred.
- Signals, volume ratios and ADX come from **that broker's own prices and tick volume**, so they will not match XM or TradingView exactly. Repeat the demo period after changing brokers.
- MT5 must stay **open and connected** for the robot to trade. If the PC sleeps, the robot stops. For 24/7 running, use a Windows VPS or MetaTrader VPS.

## Step 1: Install the files

0. Install MetaTrader 5 (from your broker's website), then **start it once and log in** so its data folder exists. MT5 may stay open during the install.
1. Extract the **whole** zip anywhere, for example to the Desktop.
2. Double-click **`install.bat`**.
   - If Windows shows *"Windows protected your PC"*, click **More info → Run anyway**.
   - If the PC has several MT5 terminals, type the number of the one to use.
   - Wait for `Done`.
   - If your terminal is portable or not listed, run `install.bat -DataFolder "<path shown by File → Open Data Folder>"` from a command prompt in the extracted folder.

The installer recompiles the robot with that terminal's MetaEditor. If recompiling is not possible, it keeps the ready-made `.ex5` files, which were built with MT5 build 6198.

**Manual install:**
1. In MT5, choose **File → Open Data Folder**.
2. Copy this package's `MQL5` folder over the `MQL5` folder there, merging the folders.
3. In the Navigator (Ctrl+N), right-click **Expert Advisors → Refresh**.
4. If TWK_MomentumEA is missing or will not attach:
   1. Press **F4** to open MetaEditor.
   2. Open `Experts\TWK\TWK_MomentumEA.mq5`.
   3. Press **F7** (Compile).

## Step 2: Log in to a DEMO account

Use **File → Login to Trade Account** and log in to a **demo** account with its **master (trading) password**.
- With the investor (read-only) password the robot runs, but every entry is rejected with `trading disabled for this account (investor login?)`.
- No demo account yet? Choose **File → Open an Account**, pick your broker, then open a demo account.

## Step 3: Attach the robot (once per symbol)

1. Make the **Algo Trading** button on the toolbar **green**.
2. Open a chart of gold and set it to the preset's timeframe: **M1** for `TWK_GOLD_M1_demo.set`, **M3** for `TWK_GOLD_M3_demo.set`.
   - Gold's name depends on the broker: XM uses `GOLD`, others use `XAUUSD`, `XAUUSDm`, `XAUUSD.a` and so on.
   - If the symbol is not in Market Watch (Ctrl+M), press Ctrl+U, search for it, click **Show Symbol**, then right-click it in Market Watch → **Chart Window**.
   - The robot reads the Signal timeframe's data by itself, so the chart timeframe does not change its trades. It only draws the Tracker when the chart timeframe matches.
3. From the Navigator, drag **Expert Advisors → TWK → TWK_MomentumEA** onto the chart.
4. On the **Common** tab, tick **Allow Algo Trading**.
5. On the **Inputs** tab, click **Load** and choose the preset for the symbol and timeframe, e.g. `TWK_GOLD_M1_demo.set`. Press **OK**.

Use **one chart per symbol**. Do not attach the robot twice to the same symbol.

## Step 4: Check it is healthy

Open the **Experts** tab of the Toolbox (Ctrl+T if it is hidden). The start-up lines appear at once:

```
TWK Momentum EA started on GOLD | account 12345678 (DEMO) | server ... | signal TF PERIOD_M1 | lot FIXED 0.02
[SYMBOL] GOLD digits=2 point=0.01 tick=0.01 contract=100.00 ... vol min/step/max=0.01/0.01/... spread now=54 pts
[PERMISSION] terminal AlgoTrading=ON  EA AllowAlgoTrading=ON  account expert trading=ON  symbol trade mode=4
[CONFIG] trail: purple at +200 pts, lock +100 pts at +500 pts, 1:1 gap 400 pts | ... | hard SL 500 pts (PERIOD_M1) | re-flip hard SL within 10 bars
[SPREAD] auto limit 106 pts (median 53.0 pts x 2.0 over 1000 bars)
```

**Confirm the preset really loaded.** The start line must show `lot FIXED 0.02` and `signal TF PERIOD_M1` or `PERIOD_M3`.
The `[CONFIG]` line must show `purple at +200 pts, lock +100 pts at +500 pts` for M1, or `purple at +360 pts, lock +180 pts at +900 pts` for M3.
If it shows `lot FIXED 0.01` or the wrong points, the preset did not load: open the robot's properties (F7 on the chart) and load it again, or type the values in.

Also check:
- `symbol trade mode=4` means full trading. Any other number means this symbol variant cannot be traded on your account; use another variant.
- `[PERMISSION]` is written only at start. If you turned Algo Trading on afterwards it still says OFF, so check that the toolbar button is green.
- **Chart panel:** it shows `TWK Momentum EA  |  DEMO account <login>  |  NEW TRADES: ON`. "NEW TRADES" reflects only the demo/real guard. It still says ON when the Algo Trading button is off.
- **History download:** on a new computer the first minutes may show `[DATA] indicator not ready: History not ready ... - NO TRADE until data is complete` while MT5 downloads history. This clears by itself.
- **[BAR] lines:** one per minute, but only while the market is open. There are none for gold at weekends or during the daily break.
- **Rejected signals** show the reason, e.g. `[ENTRY REJECTED] Volume ratio 0.84 below 1.20`.
- **Trades:** a trade shows `[ENTRY]` then `[FILL]`, and later `[STAGE 1]`, `[PURPLE TRAIL ...]`, `[STAGE 2]`, `[1:1 TRAIL ...]` and `[EXIT]`.

**Trade log CSV:**
- Each trade that closes while the robot is running is added to `TWK_trades_<symbol>_26092401.csv`, e.g. `TWK_trades_GOLD_26092401.csv`.
- It is in `%APPDATA%\MetaQuotes\Terminal\Common\Files`. Paste that path into the File Explorer address bar.
- **Do not keep this file open in Excel.** While it is open, the robot cannot write to it, and that trade's row is lost. Copy the file and open the copy.
- Trades that close while MT5 is closed are not in the CSV. The terminal's **History** tab is the complete record.

### ⚠ Different broker? Check the [SYMBOL] line first

All distances are **broker points**. The presets assume `digits=2 point=0.01`, which is true for GOLD at XM.

These inputs are measured in points, and must be rescaled when your point size differs:
- Stage 1 activation (profit, points)
- Stage 2 activation (profit, points)
- Stage 2 locked profit (points)
- Min SL move per modification (points)
- Fallback SL / TP distance (points)
- Hard SL points for each signal timeframe (`HardSL_M1` ...)
- Max slippage (broker points)
- Max spread (points), but only if you set a fixed number

New value = preset value × 0.01 ÷ your point:

| Your [SYMBOL] line says | What to do with the point inputs |
|---|---|
| `point=0.01` | Use the presets as they are |
| `point=0.001` | Multiply by **10** (e.g. 200 → 2000) |
| `point=0.1` | Divide by **10** |
| `point=1` | Divide by **100** |

**Also compare `contract=` and `vol min/step/max=`.** The preset lots assume XM's `contract=100.00` for GOLD, with a 0.01 minimum lot.
If your contract size differs, multiply "Fixed lot size", "Never trade more than this" and "Hard lot cap on a REAL account" by (XM contract ÷ your contract). That keeps the money per trade the same.
A lot below your broker's minimum is rejected with `lot below broker minimum`.

**Automatic spread limit:** "Max spread (points). 0 = auto" uses twice the median spread of the last 1000 M1 bars, and logs it as `[SPREAD] auto limit N pts`.
If that line never appears and entries are rejected with `spread limit unavailable (auto spread needs history)`, your broker's history has no spread data. Set it to about twice the `Spread:` value shown on the chart panel.

## Using another timeframe (e.g. 3 minutes)

Nothing is tied to M1 in the code. The timeframe is one input.

| Change | MT5 label | M1 | M3 |
|---|---|---|---|
| **Required** | Signal timeframe | 1 Minute | **3 Minutes** |
| Recommended, GOLD | Stage 1 activation / Stage 2 activation / Stage 2 locked profit / Min SL move (points) | 200 / 500 / 100 / 5 | **360 / 900 / 180 / 9** |
| Your choice | Hard SL for that timeframe (`HardSL_M1` / `HardSL_M3`) | 500 | 0 = purple line, until you set a value |

- The ready-made `TWK_GOLD_M3_demo.set` already contains these values.
- Note: a backtest on this data had the default trail (200/500/100) doing better on M3 than the x1.8 one. Test both.
- Only changing the chart to M3 does **nothing**. The robot trades the "Signal timeframe" input, not the chart.
- Why ×1.8: on XM data the indicator's stop is about 1.8× larger on M3 (GOLD median 397 → 705 points).
- At the same lot, a typical M3 trade therefore risks about 1.8× more money. Multiply the lot by about 0.55 for the same money risk.
- Expect fewer trades: roughly 3–4 per day on GOLD, instead of 8–11 on M1.
- The volume filter and the M1/M3 boxes always use the 1-minute and 3-minute rows, exactly like the TradingView table. Everything else (purple line, signals, SL/TP, ADX) follows the Signal timeframe.
- To run M1 and M3 on the same symbol at the same time, they need different **Magic numbers**. The M3 presets use 26092403. Otherwise the two copies block each other.

## Faster backtests: using all CPU cores

A single backtest always runs on **one core**. That is how MT5 works, because every tick depends on the previous one.
MT5 uses all cores only in **optimization**, one pass per core. The robot has a "slice" mode that turns one backtest into many parallel passes:

1. **Settings tab:**
   - Symbol, dates and model (e.g. *Every tick based on real ticks*) as usual.
   - **Optimization: Slow complete algorithm**.
   - Forward: **No**.
2. **Inputs tab:**
   - Load your preset.
   - Set **"Tester: slice length in days"** to `7`.
   - Tick **only** **"Tester: slice number"**, with Start `0`, Step `1` and Stop `N-1`. N = test days ÷ 7, rounded up; for example, 90 days gives Stop `12`.
3. **Agents tab:** local cores enabled. Do not use the MQL5 Cloud Network.
4. **Start.** Each core tests one slice at the same time. The Optimization Results tab shows one row per slice.
5. **Merge the slices** into one report (needs Python):
   `python tools\merge_tester_slices.py GOLD 10000`
   The arguments are the symbol as shown in MT5 and your test deposit. It prints trades, win rate, net profit, profit factor, drawdown and exit reasons, and writes `TWK_trades_GOLD_26092401_tester_MERGED.csv`.

Every slice starts with no open trade, so totals can differ slightly from one continuous run.

Even without slices, a normal backtest runs faster since v1.1: in a non-visual test it skips the chart panel and the per-bar log lines. To get those log lines back, set "Tester: write the per-bar [BAR] lines" to true.

## Simple version: TWK_PineEA

Attach **Expert Advisors → TWK → TWK_PineEA** instead of TWK_MomentumEA, and load `TWK_Pine_GOLD_M1_demo.set`.

- **Every purple-line flip is a trade.** The open trade in the other direction is closed at the flip, and a new trade opens in the new direction.
- **SL** = the last pivot, or the purple line if there is none. **TP** = `RewardRisk` × the SL distance. These are the same levels as the TradingView indicator.
- **Trailing:** once the trade is in profit, the SL follows the purple line (only tighter, never looser). At **+1000 points** profit ($10 on GOLD) the SL locks **+900 points** ($9). After that the purple line can still pull it tighter. A trade ends at SL, TP or the next flip.
- **No filters.** Every flip is traded. The volume, box, ADX, spread and hard-SL rules are only in TWK_MomentumEA.
- **`ReverseOnFlip`** = false copies the Pine strategy exactly: a new trade only when no trade is open.
- **Its own Magic number, 26092501.** Do not run it on the same symbol as TWK_MomentumEA.
- The start-up line is `TWK Pine EA started ...`. `[CONFIG]` shows `Pine trades, no filters ... TP = RR 1:2.0 | reverse on flip ON | trail purple line from +0 pts, lock +900 pts at +1000 pts`.

## Step 5: Run on demo first

Let it trade on demo for at least 2–4 weeks. Review the trade CSV and the History tab before risking money.

## Step 6: Going live (only when you are satisfied)

On a real account the robot shows signals but **opens nothing** until you change **both** of these inputs (F7 on the chart → Inputs):

1. **Where new trades are allowed**: choose **Demo and Real (also needs the confirmation text)**.
2. **Type: I ACCEPT REAL RISK (real only)**: type `I ACCEPT REAL RISK` in capitals, with no quotes and no spaces before or after.

Then:

3. Log in to the real account (File → Login to Trade Account).
   If Tools → Options → Expert Advisors → *"Disable algorithmic trading when the account has been changed"* is ticked, MT5 switches **Algo Trading off** at this point. Click it green again.
4. Check the result:
   - The panel shows `REAL account <login>  |  NEW TRADES: ON`.
   - The start-up log has no `*** SAFETY:` line.
   - If signals are rejected with `Algo Trading button is OFF in the terminal`, the button is still off.

**Hard lot cap on a REAL account** caps every order on a real account: 0.02 in the GOLD presets.
Each order is the smallest of "Fixed lot size" (or the risk-% size), "Never trade more than this" and this cap. To trade bigger on real, raise all three.

## Important: one computer per trading account

**Do not run the robot on the same trading account from two computers, two MT5 terminals, or a PC plus a MetaTrader VPS at the same time.**
Each copy remembers on its own which signal it already traded, so both would open a position on the same signal. On a netting account that means one position of double size.

To move the robot to a new computer:

1. **On the old computer**, close every chart that runs the robot, then close MT5.
   - Closing MT5 alone is **not** enough. MT5 reopens its charts next time, and the robot trades again.
   - If you migrated it to a MetaTrader VPS, migrate again without the robot, or stop the VPS.
2. **On the new computer**, attach the robot to a chart of the same symbol with the same preset (same Magic number 26092401).

**What happens to a trade that is open during the move:**
- It keeps its current stop loss and take profit at the broker the whole time. It is never left without a stop.
- The new computer rebuilds the management state from the position itself (`[STATE] ... state rebuilt` in the log) and continues trailing.
- It may resume at an earlier trailing stage. The stop never loosens, but it does not trail until the robot is attached again.
- A trade that closes during the gap is missing from the new computer's CSV. It is still in the History tab.

## Input names ↔ what MT5 shows

The Inputs tab shows a description, not the variable name:

| Name (in the code / presets) | Label in MT5's Inputs tab |
|---|---|
| AccountGuard | Where new trades are allowed |
| RealTradingConfirmation | Type: I ACCEPT REAL RISK (real only) |
| RealAccountMaxLot | Hard lot cap on a REAL account |
| SignalTimeframe | Signal timeframe (independent of chart) |
| MinimumVolumeRatio | 1m: own side >= opposite x ratio |
| RequireM1Box / RequireM3Box | 1m row must agree / 3m row must agree (completed 3m bars) |
| ADXMinimum | ADX must be strictly greater |
| PurpleTrailActivationPoints | Stage 1 activation (profit, points) |
| ProfitProtectionActivationPoints | Stage 2 activation (profit, points) |
| ProfitLockPoints | Stage 2 locked profit (points) |
| EnableOneToOneTrailing | After Stage 2: 1:1 trailing |
| MinSLImprovementPoints | Min SL move per modification (points) |
| LotSizingMode | FIXED or RISK_PERCENT |
| LotSize | Fixed lot size |
| RiskPercent | % of balance risked to initial SL |
| MaxLotSize | Never trade more than this |
| MaxSpreadPoints | Max spread (points). 0 = auto |
| MaxDeviation | Max slippage (broker points) |
| MagicNumber | Magic number |
| CloseOnOppositeSignal / ReverseOnOppositeSignal | Close position on opposite signal / Close and reverse (both off by default) |
| EmergencyProtectionMode | If SL cannot be placed (default: close the position) |
| HardSL_M1 ... HardSL_Other | M1 signals: hard SL points (0 = purple line), and one per timeframe |
| ReFlipAction | Pivot older than the opposite signal: hard SL / skip / keep / purple |
| ReFlipMinutes | Opposite signal at most this many minutes back (0 = off) |
| ShowTrackerOnChart | Purple line, LONG/SHORT arrows and SL/TP boxes on the chart |
| ChartTrackerBars | History drawn when the chart opens (0 = all) |
| ChartBoxHistory | Live: signals that keep their box (a test keeps every box) |

## Uninstall

1. Remove the robot from its charts.
2. Delete `MQL5\Experts\TWK`, `MQL5\Indicators\TWK`, `MQL5\Presets\TWK_GOLD_M1_demo.set`, `TWK_GOLD_M3_demo.set` and `TWK_Pine_GOLD_M1_demo.set` from the data folder.
3. Optional: delete the `TWK.26092401.*` entries in Tools → Global Variables (F3), and the `TWK_trades_*` and `TWK_diag_*` files in `%APPDATA%\MetaQuotes\Terminal\Common\Files`.

## Disclaimer

The robot executes the strategy as specified. It does not guarantee profit.
A backtest of the underlying Tracker entry on TradingView showed an average win rate near break-even for a 1:2 target, so treat demo results as the real test.
