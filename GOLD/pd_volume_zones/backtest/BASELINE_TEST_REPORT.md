# Baseline Test Report - Previous-Day Volume Zones strategy on XAUUSD 5-min

Data: Dukascopy XAUUSD M1, 2021-09-01 to 2026-09-25 UTC, 1,139,807 M1 bars aggregated to 228,031 five-minute bars. 39 of 61 calendar months are present (the gaps are missing downloads, not market closures). 829 daily profiles were built; 174 short days (Saturday stubs, holidays) kept the previous zones; 12 trading days were skipped because the last profile was older than 4 days (a data gap).

Rules under test, exactly as specified and as coded in `PD_VolumeZones_Strategy.pine` with its default inputs:

- Day = calendar day in Asia/Kolkata. Profile = fixed-range volume profile of the previous completed day, 40 bins, rectangles = protruding high-volume bins (prominence >= 0.20, >= 25% of the biggest bin, up to 3 bins tall), max 4 internal rectangles plus a 2-bin rectangle at the prior Day High and Day Low. POC = highest-volume bin.
- LONG: a bar's range crosses the POC (that bar or one of the previous 11), then a green 5-min candle closes above the rectangle top. Entry = that close. SL = rectangle bottom. TP = entry + 3 x (entry - SL). SHORT is the mirror.
- One position at a time, one entry per rectangle per day, no SL/TP changes, no session filter.
- Exits are resolved on the M1 path (open, nearer extreme, farther extreme, close). Gaps through a level fill at the open.
- Costs: the headline numbers are GROSS (no spread, like the TradingView tester by default). The 'Net R' column subtracts one spread per trade, assumed per year as {2021: 0.25, 2022: 0.25, 2023: 0.3, 2024: 0.35, 2025: 0.4, 2026: 0.5} USD; median cost = 0.10R per trade.
- 10 trades were excluded because their exit ran into a data gap or the end of the data.

## Headline

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| All trades | 2049 | 530 / 1519 | 25.9% | +69.7 | +0.034 | 1.05 | 72.0 | 22 | -178.5 |


Break-even win rate for a 1:3 trade is 25.0%. The realised win rate is 25.9%, so the gross edge is +0.034R per trade; after the assumed spread it is -0.087R per trade.

Exit reasons: SL 1519, TP 530.

## Long vs short

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| long | 1045 | 275 / 770 | 26.3% | +56.7 | +0.054 | 1.07 | 56.1 | 23 | -67.4 |
| short | 1004 | 255 / 749 | 25.4% | +13.0 | +0.013 | 1.02 | 65.5 | 17 | -111.1 |


## Rectangle type

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| HVN | 1316 | 331 / 985 | 25.2% | +5.6 | +0.004 | 1.01 | 59.0 | 22 | -157.8 |
| PDH | 380 | 108 / 272 | 28.4% | +53.3 | +0.140 | 1.20 | 19.0 | 17 | +9.3 |
| PDL | 353 | 91 / 262 | 25.8% | +10.8 | +0.031 | 1.04 | 26.0 | 19 | -30.0 |


## Side x rectangle type

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| long HVN | 674 | 170 / 504 | 25.2% | +6.7 | +0.010 | 1.01 | 42.8 | 23 | -74.6 |
| long PDH | 192 | 61 / 131 | 31.8% | +53.8 | +0.280 | 1.41 | 9.6 | 9 | +32.5 |
| long PDL | 179 | 44 / 135 | 24.6% | -3.8 | -0.021 | 0.97 | 20.1 | 12 | -25.3 |
| short HVN | 642 | 161 / 481 | 25.1% | -1.0 | -0.002 | 1.00 | 56.9 | 30 | -83.2 |
| short PDH | 188 | 47 / 141 | 25.0% | -0.5 | -0.003 | 1.00 | 23.5 | 12 | -23.1 |
| short PDL | 174 | 47 / 127 | 27.0% | +14.5 | +0.084 | 1.11 | 15.0 | 14 | -4.8 |


## Session (UTC)

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| Asia 00-07 UTC | 531 | 132 / 399 | 24.9% | -3.1 | -0.006 | 0.99 | 56.1 | 22 | -69.9 |
| Close 21-24 UTC | 178 | 46 / 132 | 25.8% | +6.0 | +0.034 | 1.05 | 29.0 | 10 | -13.1 |
| London 07-12 UTC | 259 | 72 / 187 | 27.8% | +29.5 | +0.114 | 1.16 | 27.4 | 15 | -6.1 |
| NY late 17-21 UTC | 667 | 172 / 495 | 25.8% | +21.0 | +0.031 | 1.04 | 59.0 | 19 | -63.8 |
| NY overlap 12-17 UTC | 414 | 108 / 306 | 26.1% | +16.3 | +0.039 | 1.05 | 29.0 | 17 | -25.5 |


## Year by year

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| 2021 | 61 | 16 / 45 | 26.2% | +3.0 | +0.049 | 1.07 | 16.0 | 9 | -6.1 |
| 2022 | 263 | 68 / 195 | 25.9% | +9.0 | +0.034 | 1.05 | 37.0 | 19 | -26.3 |
| 2023 | 414 | 111 / 303 | 26.8% | +30.5 | +0.074 | 1.10 | 35.0 | 17 | -43.9 |
| 2024 | 266 | 53 / 213 | 19.9% | -57.5 | -0.216 | 0.73 | 61.5 | 22 | -100.6 |
| 2025 | 566 | 166 / 400 | 29.3% | +104.0 | +0.184 | 1.26 | 23.2 | 18 | +47.6 |
| 2026 | 479 | 116 / 363 | 24.2% | -19.2 | -0.040 | 0.95 | 63.1 | 20 | -49.2 |


## Month by month

| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |
|---|---|---|---|---|---|---|---|---|---|
| 2021-09 | 61 | 16 / 45 | 26.2% | +3.0 | +0.049 | 1.07 | 16.0 | 9 | -6.1 |
| 2022-04 | 55 | 10 / 45 | 18.2% | -15.0 | -0.273 | 0.67 | 25.0 | 19 | -21.5 |
| 2022-08 | 58 | 13 / 45 | 22.4% | -6.0 | -0.103 | 0.87 | 20.0 | 11 | -14.6 |
| 2022-09 | 2 | 1 / 1 | 50.0% | +2.0 | +1.000 | 3.00 | 1.0 | 1 | +1.7 |
| 2022-10 | 43 | 13 / 30 | 30.2% | +9.0 | +0.210 | 1.30 | 7.0 | 5 | +4.2 |
| 2022-11 | 48 | 19 / 29 | 39.6% | +28.0 | +0.583 | 1.97 | 6.0 | 6 | +21.5 |
| 2022-12 | 57 | 12 / 45 | 21.1% | -9.0 | -0.158 | 0.80 | 21.0 | 13 | -17.6 |
| 2023-02 | 27 | 5 / 22 | 18.5% | -7.0 | -0.259 | 0.68 | 10.0 | 9 | -10.5 |
| 2023-03 | 39 | 4 / 35 | 10.3% | -23.0 | -0.590 | 0.34 | 24.0 | 10 | -27.8 |
| 2023-04 | 51 | 15 / 36 | 29.4% | +9.0 | +0.176 | 1.25 | 14.0 | 12 | +1.3 |
| 2023-06 | 64 | 19 / 45 | 29.7% | +12.0 | +0.188 | 1.27 | 11.0 | 10 | -0.1 |
| 2023-07 | 59 | 16 / 43 | 27.1% | +5.0 | +0.085 | 1.12 | 10.0 | 7 | -7.4 |
| 2023-09 | 44 | 18 / 26 | 40.9% | +27.9 | +0.635 | 2.07 | 7.1 | 8 | +14.1 |
| 2023-10 | 42 | 12 / 30 | 28.6% | +6.0 | +0.143 | 1.20 | 9.0 | 9 | +0.8 |
| 2023-11 | 46 | 11 / 35 | 23.9% | -2.0 | -0.043 | 0.94 | 10.0 | 8 | -10.2 |
| 2023-12 | 42 | 11 / 31 | 26.2% | +2.6 | +0.061 | 1.08 | 9.4 | 8 | -4.0 |
| 2024-02 | 36 | 7 / 29 | 19.4% | -8.0 | -0.222 | 0.72 | 20.0 | 15 | -17.7 |
| 2024-03 | 1 | 0 / 1 | 0.0% | -1.0 | -1.000 | 0.00 | 0.0 | 1 | -1.3 |
| 2024-05 | 60 | 8 / 52 | 13.3% | -28.1 | -0.469 | 0.46 | 27.1 | 20 | -36.5 |
| 2024-06 | 54 | 13 / 41 | 24.1% | -2.0 | -0.037 | 0.95 | 5.0 | 5 | -10.0 |
| 2024-08 | 67 | 17 / 50 | 25.4% | +1.0 | +0.015 | 1.02 | 8.0 | 7 | -8.4 |
| 2024-12 | 48 | 8 / 40 | 16.7% | -19.4 | -0.403 | 0.55 | 23.4 | 19 | -26.7 |
| 2025-02 | 56 | 22 / 34 | 39.3% | +32.0 | +0.571 | 1.94 | 6.0 | 5 | +24.7 |
| 2025-03 | 51 | 15 / 36 | 29.4% | +9.0 | +0.176 | 1.25 | 11.0 | 11 | +1.8 |
| 2025-04 | 51 | 12 / 39 | 23.5% | -3.7 | -0.073 | 0.91 | 12.7 | 9 | -7.3 |
| 2025-05 | 62 | 15 / 47 | 24.2% | +3.3 | +0.053 | 1.07 | 21.0 | 18 | -2.3 |
| 2025-06 | 58 | 18 / 40 | 31.0% | +10.8 | +0.186 | 1.25 | 12.2 | 8 | +5.9 |
| 2025-07 | 60 | 15 / 45 | 25.0% | +0.5 | +0.009 | 1.01 | 17.0 | 8 | -6.8 |
| 2025-08 | 50 | 11 / 39 | 22.0% | -6.0 | -0.120 | 0.85 | 17.0 | 16 | -13.9 |
| 2025-09 | 57 | 20 / 37 | 35.1% | +23.8 | +0.418 | 1.64 | 4.0 | 4 | +17.9 |
| 2025-10 | 71 | 26 / 45 | 36.6% | +36.2 | +0.510 | 1.80 | 6.0 | 5 | +32.6 |
| 2025-11 | 50 | 12 / 38 | 24.0% | -2.0 | -0.040 | 0.95 | 15.0 | 14 | -5.1 |
| 2026-01 | 56 | 21 / 35 | 37.5% | +28.9 | +0.517 | 1.83 | 7.0 | 7 | +25.6 |
| 2026-02 | 45 | 12 / 33 | 26.7% | +4.0 | +0.088 | 1.12 | 20.5 | 20 | +1.8 |
| 2026-03 | 49 | 15 / 34 | 30.6% | +11.0 | +0.224 | 1.32 | 9.0 | 7 | +8.9 |
| 2026-04 | 57 | 9 / 48 | 15.8% | -21.1 | -0.370 | 0.56 | 23.1 | 15 | -24.7 |
| 2026-05 | 54 | 8 / 46 | 14.8% | -22.0 | -0.407 | 0.52 | 27.0 | 13 | -25.3 |
| 2026-06 | 57 | 18 / 39 | 31.6% | +15.0 | +0.263 | 1.38 | 5.0 | 5 | +11.4 |
| 2026-07 | 58 | 9 / 49 | 15.5% | -27.2 | -0.469 | 0.50 | 33.2 | 20 | -31.6 |
| 2026-08 | 51 | 15 / 36 | 29.4% | +9.0 | +0.176 | 1.25 | 10.0 | 10 | +5.2 |
| 2026-09 | 52 | 9 / 43 | 17.3% | -16.8 | -0.323 | 0.62 | 21.8 | 16 | -20.6 |


## Excursions and timing

- Average MFE 1.39R, average MAE 0.86R. Median hold 51 min (losers 34 min, winners 126 min).
- Losers stopped within 15 min: 31%, within 30 min: 48%, within 60 min: 62%.
- Share of ALL trades whose MFE reached at least: 0.25R 78%, 0.5R 66%, 1R 49%, 1.5R 41%, 2R 34%, 2.5R 29%, 3R 26%.
- Share of LOSING trades that were first in profit by at least: 0.25R 71%, 0.5R 54%, 1R 32%, 1.5R 20%, 2R 11%, 2.5R 4%.
- Share of WINNING trades that first went against by at least: 0.25R 66%, 0.5R 41%, 0.75R 21%.

Target curve (same entries and stop, target moved; computed from MFE, so it is exact for this trade set):

| Target | Hit rate | Expectancy (R per trade) |
|---|---|---|
| 0.5R | 65.7% | -0.014 |
| 1.0R | 49.4% | -0.011 |
| 1.5R | 40.7% | +0.016 |
| 2.0R | 34.2% | +0.025 |
| 2.5R | 28.8% | +0.010 |
| 3.0R | 25.8% | +0.033 |
| 4.0R | 0.1% | -0.993 |

## Setups skipped because a position was already open

8,367 setup signals fired while a trade was open (a rectangle re-fires on every new tap, so this is inflated; 8,367 distinct). Simulated independently they would have had a win rate of 28.4% and +0.139R per trade.

## Verdict

- Gross: 2,049 trades, 25.9% winners against a 25.0% break-even, +69.7R (+0.034R per trade), profit factor 1.05, worst drawdown 72R, longest losing run 22.
- Net of one spread per trade (median cost 0.10R): -178.5R (-0.087R per trade). The strategy is break-even before costs and loses after them.
- The result is one year: 2025 made +104.0R; the other four years together made -34.2R over 1,483 trades.
- Long vs short: 26.3% / 25.4%, +56.7R / +13.0R. Not a significant difference.
- Rectangle types: the volume rectangles (HVN) are flat (1316 trades, 25.2%, +5.6R); the previous Day High rectangle traded long is the only slice with a positive result (192 trades, 31.8%, +53.8R, z +2.0).

### Cost by stop size (why break-even gross becomes a loss)

| Risk quartile | Trades | Median risk (USD) | Win rate | Gross R | Avg cost (R) | Net R |
|---|---|---|---|---|---|---|
| smallest 25% | 513.0 | 1.44 | 25.9% | +19.5 | 0.24 | -101.2 |
| 25-50% | 512.0 | 2.65 | 23.4% | -35.5 | 0.13 | -100.5 |
| 50-75% | 512.0 | 4.98 | 26.8% | +28.9 | 0.08 | -12.8 |
| largest 25% | 512.0 | 10.58 | 27.3% | +56.8 | 0.04 | +36.0 |
