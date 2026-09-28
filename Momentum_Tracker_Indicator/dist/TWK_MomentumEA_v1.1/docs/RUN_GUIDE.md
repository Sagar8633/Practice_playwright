# TWK Momentum EA: run guide (demo first, then real)

Installed and compiled (0 errors, 0 warnings):

- `MQL5\Experts\TWK\TWK_MomentumEA.ex5`: the bot
- `MQL5\Indicators\TWK\TWK_Tracker_MT5.ex5`: optional visual check (purple line and arrows)

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
| BTCUSD M1 | 0.5 / 0.5 | 1.5 | +5400 pts | +2700 at +13500 | 10800 pts | 8000 pts |

BTCUSD distances are GOLD's × 27, the ratio of their typical Tracker stop sizes (≈10,700 vs ≈400 pts).
Health check at startup: `[PERMISSION]` all ON, `[CONFIG]` matches the table, and `[BAR]` logs one line per minute per chart.
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
- Spread filter: `MaxSpreadPoints` = 0 means auto: 2 x the median bar spread of the last 1000 bars (GOLD ≈ 106 pts, BTCUSD ≈ 8000 pts). Wider spreads reject the entry. Open trades are never closed because of spread.

## All distances are broker points

`PurpleTrailActivationPoints` 200, `ProfitProtectionActivationPoints` 500, `ProfitLockPoints` 100, `MinSLImprovementPoints` 5, `FallbackSLPoints` / `FallbackTPPoints`, `MaxSpreadPoints`.

On XM demo both GOLD and BTCUSD have digits = 2, so 1 point = 0.01 price. 200 pts is a 2.00 move on either symbol, but typical Tracker stops are about 400 pts on GOLD and about 10,700 pts on BTCUSD.
