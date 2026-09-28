# TWK Momentum EA: run guide (demo first, then real)

Installed and compiled (0 errors, 0 warnings):

- `MQL5\Experts\TWK\TWK_MomentumEA.ex5`: the bot
- `MQL5\Indicators\TWK\TWK_Tracker_MT5.ex5`: the chart Tracker (purple line, arrows, SL/TP boxes). Since v1.30 it is built into the EA, so this file is only needed to recompile or to attach the Tracker on its own.

## Your XM accounts (from the terminal log, 2026-09-24)

| Account | Server | Type |
|---|---|---|
| **169426800** | XMGlobal-MT5 2 | **DEMO**: start here |
| 450160565 | XMGlobal-MT5 20 | **REAL**: the EA refuses to trade here by default |

Gold is `XAUUSD` (or `GOLD`) on the demo server and `GOLD.i#` on the real server.

## Current demo deployment (2026-09-24 13:15, account 169426800)

| Chart | LotSize / Max | Volume ratio | Purple at | Lock | 1:1 gap | Spread max (auto) |
|---|---|---|---|---|---|---|
| GOLD M1 | 0.02 / 0.1 | 1.2 | +200 pts | +100 at +500 | 400 pts | 106 pts |

Health check at startup: `[PERMISSION]` all ON, `[CONFIG]` matches the table, and `[BAR]` logs one line per minute.
A trade shows up as `[MOMENTUM]`, then `[VOLUME]`/`[M1 BOX]`/`[M3 BOX]`/`[ADX]` PASS, then `[ENTRY]`, then `[FILL]` in the Experts tab.

## Step 1: Backtest (no risk)

1. Press `Ctrl+R` to open the Strategy Tester.
2. Choose Expert **TWK\TWK_MomentumEA**, symbol **XAUUSD**, period **M1**.
3. Set Model to **Every tick based on real ticks**, dates to the last 1–3 months, and deposit to 10000 USD.
4. Press **Start**.
5. At the end, the Journal prints the `TWK EA STATISTICS` block: trades, win rate, profit factor and exit breakdown.
   Per-trade R:R is written to `Common\Files\TWK_trades_XAUUSD_26092401_tester.csv`.

### Faster backtests (v1.10)

**Why only one core?** A single backtest is one pass. MT5 runs a pass on one core, because every tick depends on the previous one (open trade, trailing stage, balance). MT5 uses all cores only in **optimization**, one pass per core.

**1. A single run is already faster in v1.10.** In a non-visual test the EA skips the chart panel, the 1-second timer and the per-bar `[BAR]` log lines. Set `TesterDebugLog = true` to get the log lines back.

**2. To use all cores for one configuration, split the period into slices:**

1. Settings tab:
   - Set dates, symbol and model (**Every tick based on real ticks**) as usual.
   - Set **Optimization** to **Slow complete algorithm**.
   - Set Forward to **No**.
2. Inputs tab:
   - Set **"Tester: slice length in days"** (`TesterSliceDays`) to, for example, `7`.
   - Tick **only** **"Tester: slice number"** (`TesterSliceIndex`). Start `0`, Step `1`, Stop `N-1`, where N = test days ÷ slice days, rounded up. For example, 90 days in 7-day slices gives Stop `12`.
3. Agents tab: keep the local cores enabled. Do not use MQL5 Cloud Network, because remote agents cannot write the CSVs.
4. Start. Each core tests one slice at the same time. Every pass:
   - skips the ticks before its slice;
   - trades only inside its slice;
   - lets its last trade finish, then stops.
   The Optimization Results tab shows one row per slice.
5. Merge the slices into one report:
   ```
   python tools/merge_tester_slices.py GOLD 10000
   ```
   The arguments are the symbol and the deposit. It prints trades, win rate, net profit, profit factor, drawdown, streaks, average R:R and exit reasons, and writes `TWK_trades_GOLD_26092401_tester_MERGED.csv`.

Limitation: every slice starts with no open position. A trade crossing a slice boundary can therefore overlap one opened by the next slice, so totals can differ slightly from a single continuous run.

## Step 2: Demo forward test (at least 2–4 weeks)

1. Log in to **169426800 (demo)**.
2. Open an **XAUUSD, M1** chart.
3. Drag **Experts → TWK → TWK_MomentumEA** onto it.
   - On the **Common** tab, tick **Allow Algo Trading**.
   - On the **Inputs** tab, set your lot size (below) and press OK.
4. Make sure the **Algo Trading** button in the toolbar is green.
5. The chart shows the panel with `DEMO account 169426800 | NEW TRADES: ON`.
6. On start it also writes `Common\Files\TWK_diag_XAUUSD_M1.csv`. Tell Claude when it exists, so it can run the MQL5-vs-Pine check (`tools/compare_mt5.py`).

## Lot size (Inputs → POSITION SIZE)

| Input | Default | Meaning |
|---|---|---|
| `LotSizingMode` | FIXED | FIXED = always `LotSize`. RISK_PERCENT = size so a hit on the initial SL loses `RiskPercent` % of balance |
| `LotSize` | 0.01 | Lot per trade in FIXED mode |
| `RiskPercent` | 0.50 | Used in RISK_PERCENT mode |
| `MaxLotSize` | 0.10 | Upper cap in both modes |
| `RealAccountMaxLot` | 0.01 | Extra hard cap that applies **only on a real account** |

## Simple version: TWK_PineEA (Pine trades, no filters)

`Experts\TWK\TWK_PineEA.ex5` is a separate, simple robot with **no filters** (no volume, box, ADX or spread check, and no hard-SL rules):
- **Every purple-line flip is a trade.** The open trade in the other direction is closed at the flip, and a new trade opens in the new direction.
- **Stops are the exact Pine ones.** SL = the last pivot (or the purple line if there is none), and TP = `RewardRisk` × the risk, both measured from the signal close.
- **Trailing:** once the trade is in profit, the SL follows the purple line (only tighter, never looser). At **+1000 points** profit ($10 on GOLD) the SL locks **+900 points** ($9). After that the purple line can still pull it tighter. A trade ends at SL, TP or the next flip.

| Input | Default | Meaning |
|---|---|---|
| `RewardRisk` | 2.0 | TP distance = this × SL distance (1:2) |
| `ReverseOnFlip` | true | true = close and reverse at every flip. false = like the Pine strategy, enter only when flat. |
| `EnablePurpleTrail` | true | Once in profit, the SL follows the purple line |
| `PurpleTrailStartPoints` | 0 | Profit needed before the purple trail starts (0 = as soon as in profit) |
| `LockTriggerPoints` / `LockProfitPoints` | 1000 / 900 | At +1000 pts profit the SL moves to +900 pts (0 = no lock) |
| `LotSize` | 0.01 | Fixed lot |
| `MagicNumber` | 26092501 | Its own number, so it never manages TWK_MomentumEA's trades |

- The purple line, arrows and SL/TP boxes are built in, as in TWK_MomentumEA. In the tester, set Period = `SignalTimeframe`.
- The Journal shows `[FLIP]`, `[CLOSE]` (closed on the flip), `[ENTRY]` / `[FILL]` and `[TRAIL]` (every SL move), `[EXIT] ... reason=SL / SL (purple trail) / SL (locked profit) / TP / flip`. When the EA is removed it prints the count of each exit type.
- Trades are listed in `Common\Files\TWK_pine_trades_<symbol>_26092501[_tester].csv`.
- Safety checks still apply: demo-only by default, and no trade if the price has already passed the SL (e.g. after a gap).

## Seeing the trades on the chart (v1.40, Inputs → CHART)

The chart Tracker is built into `TWK_MomentumEA.ex5`, so the EA file alone is the whole package. You don't attach any indicator by hand. There are two kinds of drawing.

**1. Signal boxes (the Tracker, TradingView style).** One box for every LONG/SHORT signal: a green zone from entry to TP, a red zone from entry to SL, and a dashed entry line. The purple line and the ▲/▼ arrows are drawn too. Hover over a box to see:
- entry, SL and TP;
- where the SL came from: pivot, hard SL, or purple line;
- which bar the pivot is on and how old it is;
- how many bars ago the opposite signal was.

The shade tells you what the EA did with the signal:

| Box | Meaning |
|---|---|
| Bright green/red | The signal passed the entry filters (volume ratio, M1 box, M3 box, ADX). The EA trades it unless a position is already open or the spread is too wide. |
| Very dim green/red | The signal failed a filter. The tooltip says which one, e.g. `NOT TRADED (volume ratio 0.83 below 1.20)`. |
| Grey | A quick re-flip the EA skips (`ReFlipAction` = Skip). |

The box prices are measured from the signal bar's close. The EA fills at the next bar's ask or bid, so real prices differ by about the spread.

**2. Trade boxes (drawn by the EA for every real position).** These are drawn in visual tests and on the live chart:
- a red outline from entry to the initial SL;
- a green outline from entry to TP, from the fill to the exit;
- the SL as it trails, as orange steps;
- the P/L written at the exit.

Hover over one for the ticket, the fill price, the initial SL distance and the exit reason. This is the way to check each trade.

| Input | Default | Meaning |
|---|---|---|
| `ShowTrackerOnChart` | true | Turn all drawing on or off. Trading is the same either way. |
| `ChartTrackerBars` | 50000 | History drawn when the chart opens (0 = all). New bars are added as they close, and older ones are kept. |
| `ChartBoxHistory` | 300 | Live only: how many recent signals keep their box. A Strategy Tester run keeps every box from the test start. |

**Strategy Tester:**
- Pick `TWK\TWK_MomentumEA` and set the tester **Period equal to `SignalTimeframe`** (M1 for M1 signals, M3 for M3). If they differ, the Journal prints a `*** CHART:` warning and the Tracker is not on the test chart.
- **Visual mode** shows both kinds of drawing, bar by bar.
- After a fast (non-visual) test, the chart MT5 opens shows the purple line, arrows and signal boxes, plus MT5's own entry and exit arrows. Trade boxes need visual mode, because a fast test cannot draw objects.

**Live chart:** the EA adds the Tracker to its own chart when the chart timeframe equals `SignalTimeframe`. Otherwise the Journal says to attach the EA to a chart of that timeframe. Removing the EA removes its Tracker and its trade boxes.

**To rebuild after editing:** compile `Indicators\TWK\TWK_Tracker_MT5.mq5` first, then `Experts\TWK\TWK_MomentumEA.mq5`. MetaEditor embeds whatever indicator .ex5 is already on disk, so a stale one would be embedded.

## Initial SL: pivot, hard SL and quick re-flip (v1.40)

**Normal case:** the SL is the latest confirmed pivot (5 bars on each side), below the close for a BUY and above it for a SELL. TP = `RewardRisk` × the risk, so every trade is 1:2.

**Two cases use a hard SL instead of that pivot:**

1. **No pivot:** the latest pivot is on the wrong side of the close.
2. **Quick re-flip** (Inputs → QUICK RE-FLIP): the opposite signal came at most `ReFlipMinutes` minutes ago (default 15, i.e. 15 bars on M1 and 5 bars on M3), *and* the pivot is older than that opposite signal. The small swing between the two signals is not confirmed yet (it needs 5 more bars), so the pivot sits behind the whole previous move. That produced the $27–$41 stops on 2 Sep. **This old pivot is never used.** `ReFlipAction` decides what happens:

| `ReFlipAction` | What the EA does on a quick re-flip |
|---|---|
| **Hard SL** (default) | SL = the hard SL distance below, TP = 2× that distance. If the distance is 0, the purple line is the stop. |
| **Skip the trade** | No trade. The Journal says `quick re-flip: ... trade skipped`, and the chart shows the signal as a grey box. |
| **Purple line** | SL = the purple line, TP = 2× that distance, whatever the hard SL input says. |
| **Keep the old pivot** | The v1.30 behaviour, for comparison backtests only. |

**Hard SL distance by signal timeframe** (Inputs → HARD SL):

| Input | Default | Used when `SignalTimeframe` is |
|---|---|---|
| `HardSL_M1` | 500 ($5.00 on GOLD) | M1 |
| `HardSL_M3` | 0 = purple line | M3 |
| `HardSL_M5` / `HardSL_M15` / `HardSL_M30` | 0 = purple line | M5 / M15 / M30 |
| `HardSL_H1` / `HardSL_H4` | 0 = purple line | H1 / H4 |
| `HardSL_Other` | 0 = purple line | any other timeframe |

Set the values you want for M3 and the longer timeframes.

- The Journal shows the rule used, for example `[SL] 4372.31 VALID (quick re-flip 3 bars, old pivot 4336.40 not used: hard 500 pts)`, `(no pivot: hard 500 pts)`, `(pivot)` or `(purple line, no pivot)`. The `[CONFIG]` line at start-up shows the hard SL and the re-flip setting.
- If the hard distance is not wider than the current spread + stop level, the purple line is used instead, and the Journal says so.
- A pivot that is far away but is NOT a quick re-flip is still used as it is.
- These rules take priority over `EnableFallbackSL`, which now only applies when `UseIndicatorSL` = false.
- **What the backtests say** (1–24 Sep, bar-level replay, first-order): about 70% of M1 trades and 40% of M3 trades are quick re-flips.
  - Improvement vs the old pivot, M1 / M3: hard SL (500 pts on M1, purple line on M3) +$66 / +$18; purple line +$56 / +$18; skip +$116 / −$5.
  - Skip only looks good on M1 because it drops most trades of a losing setup.
  - A fixed 500 pts can stop out a trade that the purple line would have kept. The 2 Sep 16:53 BUY dipped $5 before it won.
  - With a 30-minute window on M3, every action lost money, so keep the window near 15 minutes.
  - Treat these numbers as a guide; confirm them on a longer test.
- These trades show the exit reason "Initial SL". You can recognise them by `initial_risk` = the hard distance, or by the Journal line.
- To reproduce v1.10 exactly, set `HardSL_M1` = 0 and `ReFlipAction` = Keep the old pivot (or `ReFlipMinutes` = 0). v1.20/v1.30 settings files used the names `NoPivotSL_*`, so those values are not read any more; the defaults apply.

## Step 3: Going live (only after the demo results satisfy you)

On the real account the EA shows signals but **opens nothing** until you change **both** of these:

1. `AccountGuard` → **Demo and Real**
2. `RealTradingConfirmation` → type exactly `I ACCEPT REAL RISK`

Then raise `RealAccountMaxLot` if you want more than 0.01.
Use the same `MagicNumber` only if you want the EA to manage the same positions. Otherwise leave it.

## Safety behaviour

- The SL is sent with the order. If the broker drops it, the EA retries and then **closes the position** (`EmergencyProtectionMode`).
- The SL never loosens. A manual SL change is kept.
- After a restart, the EA recovers its position and stage.
- A manual close never re-opens on the same signal.
- An opposite signal does nothing to an open trade unless `CloseOnOppositeSignal` or `ReverseOnOppositeSignal` is enabled.
- Spread filter: `MaxSpreadPoints` = 0 means auto: 2 x the median bar spread of the last 1000 bars (GOLD ≈ 106 pts). Wider spreads reject the entry. Open trades are never closed because of spread.

## All distances are broker points

`PurpleTrailActivationPoints` 200, `ProfitProtectionActivationPoints` 500, `ProfitLockPoints` 100, `MinSLImprovementPoints` 5, `FallbackSLPoints` / `FallbackTPPoints`, `HardSL_*`, `MaxSpreadPoints`.

On XM demo GOLD has digits = 2, so 1 point = 0.01 price: 200 pts is a 2.00 move. Typical Tracker stops on GOLD M1 are about 400 pts.
