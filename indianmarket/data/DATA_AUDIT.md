# Data audit: NIFTY 50 and NIFTY BANK (27 Sep 2026)

## Sources

| Set | Source | Interval | Coverage | Rows | Adjusted | Volume |
|---|---|---|---|---|---|---|
| Intraday path | Upstox public historical-candle API (`api.upstox.com/v2/historical-candle/NSE_INDEX|Nifty 50/1minute`, same for `Nifty Bank`), no login | 1 minute | 3 Jan 2022 to 25 Sep 2026, 1,174 sessions | 438,667 (NIFTY 50), 438,613 (NIFTY BANK) | index level, not adjusted (indices need none) | none: index candles carry 0 volume |
| Daily, official | NSE Indices (`niftyindices.com/reports/historical-data`, fetched through the site's own endpoint in a browser session) | 1 day | 1 Jan 2019 to 25 Sep 2026 | 1,919 each | official index OHLC | none |
| Daily, long | Upstox `v3/historical-candle/.../days/1` | 1 day | 2 Jan 2007 to 25 Sep 2026 | 4,890 / 4,881 | index level | none |
| Daily, cross-check | Yahoo Finance `^NSEI`, `^NSEBANK` | 1 day | 2010 to 2026 | 4,142 each | index level | none |

Why not NSE intraday: NSE does not distribute historical minute data for indices free of charge; the official site serves daily OHLC only. The Upstox feed is the broker's own NSE index tick record aggregated to minutes; it starts in January 2022 for 1-minute candles (requests for 2021 return nothing), so the intraday history is 4.7 years, not 5. The daily official series covers the full 5 years and more.

Timestamps: Upstox returns IST with the +05:30 offset; the offset is dropped and every timestamp is IST wall-clock. A 1-minute candle stamped 09:15 covers 09:15:00 to 09:15:59.

## Cross-checks against the official NSE daily series

| Check | NIFTY 50 | NIFTY BANK |
|---|---|---|
| Upstox daily vs official: open/high/low/close | identical to the paisa on all 1,919 sessions (one high off by 0.40, one low by 1.00) | identical on all 1,919 sessions |
| Yahoo close vs official | identical (1,908 sessions) | identical |
| 1-minute-built daily high vs official high | median 0.00, 95th pct 1.60, 99th pct 7.4 pts; 22 sessions differ by more than 5 pts | median 0.00, 95th pct 6.2, 99th pct 25 pts; 71 sessions differ by more than 5 pts |
| 1-minute-built daily low vs official low | median 0.00, 95th pct 1.67; 16 sessions > 5 pts | median 0.00, 95th pct 7.4; 86 sessions > 5 pts |
| 1-minute last print (15:29) vs official close | median 9.3 pts (0.043%), 90th pct 28, max 120 | median 27 pts (0.055%), 90th pct 83, max 278 |
| Sessions present in official data but not in the 1-minute file | 2022-10-24, 2023-11-12, 2024-11-01 (Muhurat evening sessions, outside 09:15-15:30) | same |
| Sessions present in the 1-minute file but not official | none | none |

Reading: the intraday feed reproduces the official daily range to within a couple of points on NIFTY 50 and within 6 to 7 points (95th percentile) on NIFTY BANK; on a handful of sessions the official extreme exceeds the minute extreme by 20 to 30 points, so intraday stop hits are marginally understated in the backtest. The official daily **close** is NSE's closing-price computation (constituent closing prices), which no intraday print reproduces; every daily-bar signal that is built from the 1-minute path therefore uses the 15:29 print as the close. D1 tests are run twice: from the 1-minute path (2022-2026) and from the official daily series (2007-2026), and both are reported.

## Session handling

* Kept: bars from 09:15 to 15:29 IST (375 per regular session). Dropped and counted (404 bars per index): 84 pre-open prints at 09:07, the 15:30/15:31 closing prints, and the evening Muhurat sessions (2022-10-24, 2023-11-12, 2024-11-01; 60 bars each around 18:15-19:15).
* Special sessions kept because they were real trading sessions in regular hours: Saturday 20 Jan 2024 (full day), Saturday 2 Mar 2024 and Saturday 18 May 2024 (disaster-recovery drills, 105 bars: 09:15-10:00 and 11:30-12:30), Saturday 1 Feb 2025 and Sunday 1 Feb 2026 (Union Budget, full sessions), and 21 Oct 2025 (60 bars, the Muhurat session held in the afternoon). They form short signal bars on that day; 6 sessions out of 1,174.
* Holidays: 67 weekdays with no bars in 4.7 years (12 to 16 per year), consistent with the NSE holiday calendar. No synthetic bars were added.
* Missing minutes inside otherwise complete weekday sessions: 7 (NIFTY 50) and 4 (NIFTY BANK) in total, plus 50 minutes missing on 7 Mar 2022 for NIFTY BANK (09:15-10:05).
* Duplicated candles: 0 in both files. OHLC consistency (high >= max(open, close), low <= min(open, close)): 0 violations. Zero or negative prices: 0. Flat bars (high = low): 795 / 775, all at thin minutes.
* Largest one-minute move: NIFTY 50 -3.86% at 09:15 on 7 Apr 2025 (gap open), NIFTY BANK 4.04% at 09:15 on 8 Apr 2026; both are opening gaps against the previous 15:29 print, not spikes.

## Look-ahead and survivorship

* Signals use only completed bars (shift 1 and 2), stops and fills are evaluated on the next 1-minute bar's range, exactly as in the gold engine. Regime tags use the previous session's values; the gap tag uses the session's opening print, which is known at 09:15.
* Index-level data has no survivorship problem: the index history is the published history of the index, constituent changes included.

## Limitations to keep in mind

1. **No volume.** NSE index candles carry no volume; the EA's volume filter (volume[1] > SMA20(volume)) cannot be evaluated and is switched off in every run. On gold it removed about half of the signals, so the Indian baseline is a version of the strategy with one filter fewer. Futures volume would be the substitute, but expired-contract minute data is not freely available.
2. **Index, not futures.** Trading happens in NIFTY / BANKNIFTY futures; the backtest uses the index level. The futures basis (premium that decays to zero at expiry) and the monthly rollover are not modelled. For a strategy that holds for hours to days the point P&L is nearly the same; the costs model (costs.py) adds the futures spread, slippage and all statutory charges.
3. **Intraday history is 4.7 years (Jan 2022 onwards).** The 1-minute feed does not go back further; the daily official series does (2007).
4. The MT5 "point" of the original EA becomes the NSE tick (0.05) in the AS-IS runs; this mapping is a documented choice, and the ATR-scaled configuration is run alongside because it needs no such mapping.

Files: `data/<index>/<index>_1min_upstox.csv.gz`, `<index>_daily_upstox.csv.gz`, `<index>_daily_nse_official.csv`, `<index>_path.npz` (engine cache), raw JSON per request in `data/raw/`, `upstox_download_summary.json`, `intraday_vs_official_audit.json`, fetch script `tools/fetch_upstox.py`.
