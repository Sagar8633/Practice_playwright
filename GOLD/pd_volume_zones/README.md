# Previous-Day Volume Zones (PD VolZones) - XAUUSD 5-min bot

Two Pine Script v6 files that implement the "yesterday's volume profile rectangles" idea, plus an offline
Python replica for testing on 5 years of Gold data.

| File | What it is |
|---|---|
| `PD_VolumeZones_Indicator.pine` | Draws, for every completed trading day, the Day High / Day Low lines, the protruding high-volume rectangles of that day's fixed-range volume profile, a dashed POC line through each rectangle, and (optionally) the profile histogram. The drawings stay on the chart through the following day. |
| `PD_VolumeZones_Strategy.pine` | Same zone engine plus the trade rules: POC tap -> confirmation close outside the rectangle -> entry at that close -> SL at the far edge of the rectangle -> TP at exactly 3R. One position at a time, one entry per rectangle per day. Fires `alert()` on every entry. |
| `backtest/pdvz_engine.py` | Exact Python port of the strategy for offline runs on Dukascopy M1 data (exits resolved on the M1 path). |
| `backtest/analyze_baseline.py` | Trade log, statistics, loss-pattern tables, what-if shadow runs, and the two reports. |
| `backtest/BASELINE_TEST_REPORT.md`, `backtest/LOSS_PATTERN_REPORT.md` | The frozen-rules test results. |
| `backtest/v2_lab.py`, `backtest/V2_RESEARCH_REPORT.md`, `backtest/results/v2/` | V2 lab: seven single-switch experiments against V1, chronological DEV/VAL/OOS split, pre-registered combination rule, yearly walk-forward. Conclusion: break-even at best, no robust edge. Run with `python v2_lab.py` (about 2 minutes). |
| `backtest/v3_entry_lab.py`, `backtest/V3_ENTRY_QUALITY_REPORT.md`, `backtest/results/v3/` | V3 entry-quality study: 55 pre-entry features, AUC by period, failed-breakout predictability, POC interaction types, candle anatomy, location, congestion, DEV-fitted scores, filter accounting, and a check on 21 truly unseen months. Conclusion: the entry carries no transferable information; no filter adopted. Needs scikit-learn. |
| `backtest/exit_sim.py`, `backtest/v4_exit_lab.py`, `backtest/V4_EXIT_RESEARCH_REPORT.md`, `backtest/results/v4/` | V4 exit-structure study on the same entries: MFE/MAE and path dependency, fixed R:R curve, break-even, locks, ATR and structure trails, partials, conservative intrabar rule, acceptance matrix, 21 untouched months. Conclusion: the post-entry path is a fair game (reach probability = 1/(1+L)); no exit passes. |
| `backtest/results/trade_log.csv` | Every trade with entry, SL, TP, risk, R, MFE, MAE and ~50 diagnostic features. |

## How the zones are built (both scripts, same code)

1. A "day" is the calendar day in the `Timezone` input (default `Asia/Kolkata`, matching the chart in the
   screenshot). `Day session` can narrow it (e.g. `0600-2100`). A day shorter than `Minimum day length (hours)`
   (the Saturday stub after the Friday close) is skipped and the previous zones stay active.
2. At the first bar of a new day the previous day's bars are turned into a volume profile between that day's
   High and Low (`Volume bins`, default 40). Each bar's volume is spread pro rata over the bins its range covers.
   Optionally the profile is built from 1-min intrabar data instead (`Build the profile from a lower timeframe`).
3. A bin becomes a rectangle candidate when it is the largest bin within `Peak window` bins on each side, stands
   above the valleys on both sides by `Minimum prominence` (fraction of its own volume) and holds at least
   `Minimum volume vs. day POC` of the biggest bin. Neighbouring bins with at least `Zone extension threshold` of
   the peak's volume are merged into the rectangle, up to `Maximum rectangle half-height` bins each side.
4. Candidates are ranked by volume; a weaker one whose rectangle sits closer than `Minimum zone separation`
   bins to a stronger one is dropped; at most `Maximum internal zones` survive.
5. A 2-bin rectangle is added at the Day High and at the Day Low (`Rectangle at Day High and Day Low`).
6. The POC line is the highest-volume bin of the rectangle (or its midpoint, by input).

Frozen defaults (chosen so that a typical day yields a median of 3 internal rectangles about 2 USD tall,
the density of the reference screenshot): bins 40, smoothing 1, prominence 0.20, share 0.25, peak window 2,
extension 0.75, half-height 1, separation 3, max 4 internal zones, boundary rectangles 2 bins.

## Trade rules (strategy)

- LONG: a 5-min bar's range crosses a rectangle's POC line (that bar or one of the previous `Tap validity` - 1
  bars), then a green candle closes above the rectangle top. Entry = that close (`process_orders_on_close`).
  SL = rectangle bottom (minus `SL buffer`). TP = entry + `Reward : risk` x (entry - SL). Default 3.
- SHORT: mirror (red candle closes below the bottom, SL = top, TP = entry - 3 x (SL - entry)).
- A mere touch of the rectangle is not a setup; the POC cross is mandatory. No SL/TP changes after entry.
- One position at a time; one entry per rectangle per day (`Max trades per rectangle`). When several rectangles
  qualify on the same candle the nearest one (tightest SL) is used. Setups skipped because a trade is open are
  shown as grey triangles.
- Optional: `Trading session`, `Close the open trade when the trading session ends`, `Min/Max risk`,
  `Backtest window (days)` (entries only in the last N days - useful without Deep Backtesting),
  risk-% or fixed position sizing.

## Using it on TradingView

1. Pine Editor -> paste the file -> Add to chart on OANDA:XAUUSD 5-min (or any symbol with volume).
   The indicator on a 30-min chart builds the profile from 30-min bars; on the 5-min chart from 5-min bars.
   Set `Build the profile from a lower timeframe` = on with `1` to get the same profile on every timeframe.
2. Alerts: create an alert on the strategy with "Order fills and alert() function calls". The Basic plan allows
   zero script alerts; this needs Essential or above.
3. Both scripts were compile-checked through TradingView's pine-facade API and are saved in the
   `patilkareena208` account as "Previous-Day Volume Zones" and "Previous-Day Volume Zones Strategy".

## Running the offline test

```
cd GOLD/pd_volume_zones/backtest
python -c "import pdvz_engine as E; tr,sk,info=E.run(E.load_m1('../../../Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_*.csv')); tr.to_csv('results/trade_log_raw.csv',index=False); sk.to_csv('results/skipped_log_raw.csv',index=False); import json; json.dump(info,open('results/run_info.json','w'))"
python analyze_baseline.py
```

Caveats: Dukascopy volume is traded volume, TradingView's OANDA feed shows tick volume, so the histogram is
smoother here and a day like 24 Sep 2026 yields 2 internal rectangles instead of the 4 in the screenshot.
The V1/V2/V3 results are pinned to the 39 monthly files present on 25-Sep-2026 (`pdvz_engine.V1_MONTHS`); 21 more months were added to the folder afterwards and were used only as unseen data in the V3 near-miss check. Costs are not in the headline numbers
(the TradingView tester also defaults to none); a spread-per-trade sensitivity column is in the reports.
