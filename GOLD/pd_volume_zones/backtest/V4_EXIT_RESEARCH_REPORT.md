# V4 Exit Structure Report - does the path after entry contain exploitable information?

Entries: the 2,049 V1 trades of the pinned 39 months (Development before 2025-06-03: 1229, Validation to 2026-02-10: 410, Out-of-sample after: 410). Entry price, initial stop, zones, POC and filters are exactly V1. Every exit variant is applied to the same entries as independent trades, so trade counts are equal by construction and the comparison isolates the exit. Costs: one spread per trade as in V1-V3; the '1.5x spread' column is the slippage sensitivity.

**Execution rule (STEP 9).** Inside an M1 candle the stop is checked first against the level in force before the candle; the target or partial level is checked only if the stop was not hit, so when both lie inside one candle the stop wins. Gaps fill at the open. Every stop move (break-even, lock, ATR or structure trail) is computed at the candle's close and applies from the next candle; structure levels use completed 5-min candles and a swing is confirmed 2 candles after its centre; the ATR is the 5-min ATR14 at entry. This is more conservative than the V1 engine's TradingView-style path guess: the same 3R rule gives -0.089R net per trade here against -0.087 in V1 (the difference is the candles where stop and target overlapped).

## STEP 1 - MFE / MAE distribution (original stop only, 3-day horizon; 'eventually' = under the original 3R rule)

Uncapped MFE before the original stop: mean 3.02R, median 0.99R (9% of trades were still open after 3 days and are censored there). Under the 3R rule: mean 1.38R, median 0.99R.

| Level | Reached before the original stop | Reached and eventually lost | Reached and eventually hit 3R |
|---|---|---|---|
| +0.25R | 77.7% (1592) | 66.8% | 32.8% |
| +0.5R | 65.4% (1341) | 60.6% | 38.9% |
| +0.75R | 55.7% (1141) | 53.7% | 45.7% |
| +1.0R | 49.3% (1011) | 47.8% | 51.6% |
| +1.25R | 43.9% (899) | 41.4% | 58.1% |
| +1.5R | 40.6% (831) | 36.6% | 62.8% |
| +2.0R | 34.0% (696) | 24.4% | 75.0% |
| +2.5R | 28.5% (584) | 10.3% | 89.4% |
| +3.0R | 25.5% (522) | 0.0% | 100.0% |
| +4.0R | 19.8% (405) | 0.0% | 100.0% |
| +5.0R | 16.1% (329) | 0.0% | 100.0% |

| Distribution (R) | p10 | p25 | median | p75 | p90 |
|---|---|---|---|---|---|
| MFE of winners (uncapped) | 3.31 | 4.07 | 6.38 | 11.72 | 18.91 |
| MFE of losers (uncapped, before the stop) | 0.04 | 0.18 | 0.55 | 1.23 | 2.06 |
| MFE of losers before the stop (3R rule) | 0.04 | 0.18 | 0.55 | 1.23 | 2.06 |
| MAE of all trades | 0.28 | 0.95 | 1.00 | 1.00 | 1.00 |
| MAE of winners | 0.05 | 0.17 | 0.39 | 0.70 | 0.86 |

Losers that were first in profit by at least: 0.25R 70%, 0.5R 53%, 0.75R 40%, 1.0R 32%, 1.5R 20%, 2.0R 11%, 2.5R 4%. Winners that first went against by at least: 0.25R 66%, 0.5R 41%, 0.75R 22%.

## STEP 8 - Path dependency (measured before the 3R target or the stop was hit)

| After first reaching | Split | n | Went on to 3R |
|---|---|---|---|
| +1.0R | gave back >= 0.5R | 802 | 39.8% |
| +1.0R | held (did not give back that much) | 205 | 100.0% |
| +1.0R | gave back >= 1R (to entry for L=1) | 660 | 26.8% |
| +1.0R | held (did not give back that much) | 347 | 100.0% |
| +1.5R | gave back >= 0.5R | 599 | 49.2% |
| +1.5R | held (did not give back that much) | 222 | 100.0% |
| +1.5R | gave back >= 1R (to entry for L=1) | 482 | 36.9% |
| +1.5R | held (did not give back that much) | 339 | 100.0% |
| +2.0R | gave back >= 0.5R | 439 | 61.0% |
| +2.0R | held (did not give back that much) | 233 | 100.0% |
| +2.0R | gave back >= 1R (to entry for L=1) | 327 | 47.7% |
| +2.0R | held (did not give back that much) | 345 | 100.0% |

| Sequence | n | Reached 3R | Avg R under the 3R rule |
|---|---|---|---|
| reached 1R then 2R | 696 | 75.0% | +2.041 |
| reached 1R, never 2R | 315 | 0.0% | -0.998 |
| reached 1.5R then fell to <= 0.5R | 481 | 36.6% | +0.471 |
| reached 1.5R and held above 0.5R | 338 | 98.8% | +3.007 |

## STEP 2 - Fixed R:R exit curve

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| Target 0.5R | 2049 | 65.4% | -39.2 | -287.4 | -0.140 | 0.95 | 52 | 7 | -0.201 | -0.176 | -0.080 | -0.095 |
| Target 0.75R | 2049 | 55.7% | -53.0 | -301.3 | -0.147 | 0.94 | 70 | 7 | -0.208 | -0.176 | -0.081 | -0.127 |
| Target 1R | 2049 | 49.4% | -27.7 | -275.9 | -0.135 | 0.97 | 45 | 11 | -0.195 | -0.168 | -0.022 | -0.147 |
| Target 1.25R | 2049 | 44.0% | -25.5 | -273.7 | -0.134 | 0.98 | 56 | 14 | -0.194 | -0.167 | -0.005 | -0.162 |
| Target 1.5R | 2049 | 40.7% | +34.8 | -213.4 | -0.104 | 1.03 | 41 | 14 | -0.165 | -0.130 | +0.013 | -0.145 |
| Target 2R | 2049 | 34.2% | +53.1 | -195.2 | -0.095 | 1.04 | 67 | 20 | -0.156 | -0.116 | +0.082 | -0.209 |
| Target 2.5R | 2049 | 28.8% | +16.1 | -232.2 | -0.113 | 1.01 | 61 | 22 | -0.174 | -0.144 | +0.060 | -0.195 |
| Target 4R | 2049 | 20.6% | +48.0 | -200.2 | -0.098 | 1.03 | 96 | 29 | -0.158 | -0.144 | +0.141 | -0.198 |

## STEP 3 - Break-even

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| BE-1: stop to entry after +1R (TP 3R) | 2049 | 17.2% | +17.5 | -230.7 | -0.113 | 1.02 | 72 | 31 | -0.173 | -0.163 | +0.051 | -0.127 |
| BE-1.5: stop to entry after +1.5R (TP 3R) | 2049 | 20.4% | +35.3 | -213.0 | -0.104 | 1.03 | 71 | 31 | -0.165 | -0.151 | +0.067 | -0.134 |
| BE-2: stop to entry after +2R (TP 3R) | 2049 | 22.9% | +56.5 | -191.7 | -0.094 | 1.04 | 66 | 26 | -0.154 | -0.132 | +0.101 | -0.173 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| BE-1: stop to entry after +1R (TP 3R) | 177 | 471 | 11 | 0 | -48.2 |
| BE-1.5: stop to entry after +1.5R (TP 3R) | 110 | 298 | 5 | 0 | -30.5 |
| BE-2: stop to entry after +2R (TP 3R) | 60 | 167 | 4 | 0 | -9.2 |

## STEP 4 - Profit lock

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| Lock A: at +1R stop to +0.25R (TP 3R) | 2049 | 49.0% | +20.2 | -228.0 | -0.111 | 1.02 | 74 | 11 | -0.172 | -0.163 | +0.059 | -0.125 |
| Lock B: at +1.5R stop to +0.5R (TP 3R) | 2049 | 40.6% | +71.2 | -177.0 | -0.086 | 1.06 | 64 | 14 | -0.147 | -0.122 | +0.095 | -0.160 |
| Lock C: at +2R stop to +1R (TP 3R) | 2049 | 34.2% | +93.4 | -154.8 | -0.076 | 1.07 | 66 | 20 | -0.136 | -0.103 | +0.144 | -0.214 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| Lock A: at +1R stop to +0.25R (TP 3R) | 0 | 476 | 6 | 235 | -45.5 |
| Lock B: at +1.5R stop to +0.5R (TP 3R) | 0 | 303 | 0 | 178 | +5.5 |
| Lock C: at +2R stop to +1R (TP 3R) | 0 | 171 | 0 | 156 | +27.7 |

## STEP 5 - ATR trailing stop (target kept)

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| ATR trail 1.0 x ATR14 after +1R (TP 3R) | 2049 | 48.1% | -13.1 | -261.3 | -0.128 | 0.99 | 50 | 11 | -0.188 | -0.172 | -0.000 | -0.120 |
| ATR trail 1.5 x ATR14 after +1R (TP 3R) | 2049 | 45.1% | -11.6 | -259.8 | -0.127 | 0.99 | 54 | 13 | -0.187 | -0.174 | +0.034 | -0.146 |
| ATR trail 2.0 x ATR14 after +1R (TP 3R) | 2049 | 40.9% | +32.8 | -215.5 | -0.105 | 1.03 | 52 | 13 | -0.166 | -0.152 | +0.092 | -0.162 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| ATR trail 1.0 x ATR14 after +1R (TP 3R) | 2 | 459 | 22 | 455 | -78.8 |
| ATR trail 1.5 x ATR14 after +1R (TP 3R) | 22 | 418 | 57 | 356 | -77.3 |
| ATR trail 2.0 x ATR14 after +1R (TP 3R) | 26 | 336 | 120 | 274 | -33.0 |

## STEP 5b - ATR trailing stop, no target

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| ATR trail 1.0 x ATR14 after +1R, no target | 2049 | 48.1% | -18.1 | -266.4 | -0.130 | 0.98 | 65 | 11 | -0.191 | -0.177 | -0.002 | -0.118 |
| ATR trail 1.5 x ATR14 after +1R, no target | 2049 | 45.1% | -20.4 | -268.6 | -0.131 | 0.98 | 71 | 13 | -0.192 | -0.183 | +0.022 | -0.129 |
| ATR trail 2.0 x ATR14 after +1R, no target | 2049 | 40.8% | +42.5 | -205.7 | -0.100 | 1.04 | 73 | 13 | -0.161 | -0.167 | +0.141 | -0.143 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| ATR trail 1.0 x ATR14 after +1R, no target | 2 | 459 | 22 | 509 | -83.9 |
| ATR trail 1.5 x ATR14 after +1R, no target | 22 | 418 | 57 | 459 | -86.1 |
| ATR trail 2.0 x ATR14 after +1R, no target | 28 | 336 | 120 | 415 | -23.2 |

## STEP 6 - Structure trailing

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| Structure trail: last completed 5-min candle low/high after +1R (TP 3R) | 2049 | 46.0% | +14.5 | -233.8 | -0.114 | 1.01 | 50 | 11 | -0.175 | -0.148 | +0.016 | -0.142 |
| Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R) | 2049 | 36.0% | +7.7 | -240.5 | -0.117 | 1.01 | 66 | 14 | -0.178 | -0.172 | +0.110 | -0.181 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| Structure trail: last completed 5-min candle low/high after +1R (TP 3R) | 12 | 426 | 50 | 407 | -51.3 |
| Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R) | 24 | 232 | 112 | 205 | -58.1 |

## STEP 7 - Partial exits

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | 22 | -0.150 | -0.131 | +0.126 | -0.178 |
| P1: 50% at 1R, 50% at 3R | 2049 | 25.8% | +17.0 | -231.3 | -0.113 | 1.02 | 57 | 22 | -0.173 | -0.150 | +0.048 | -0.163 |
| P2: 50% at 1.5R, 50% at 3R | 2049 | 40.6% | +44.3 | -203.9 | -0.100 | 1.04 | 52 | 14 | -0.160 | -0.133 | +0.067 | -0.165 |
| P3: 50% at 2R, 50% at 4R | 2049 | 34.1% | +42.5 | -205.7 | -0.100 | 1.03 | 65 | 20 | -0.161 | -0.133 | +0.104 | -0.207 |

| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |
|---|---|---|---|---|---|
| P1: 50% at 1R, 50% at 3R | 0 | 479 | 4 | 529 | -48.8 |
| P2: 50% at 1.5R, 50% at 3R | 0 | 303 | 1 | 529 | -21.5 |
| P3: 50% at 2R, 50% at 4R | 1 | 171 | 0 | 115 | -23.2 |

### Per-year average net R

| Exit | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Original 3R | -0.100 | -0.100 | -0.106 | -0.393 | +0.084 | -0.103 |
| Target 0.5R | -0.166 | -0.165 | -0.153 | -0.226 | -0.129 | -0.079 |
| Target 0.75R | -0.088 | -0.169 | -0.152 | -0.241 | -0.122 | -0.115 |
| Target 1R | -0.066 | -0.152 | -0.184 | -0.245 | -0.047 | -0.133 |
| Target 1.25R | -0.002 | -0.125 | -0.207 | -0.257 | -0.035 | -0.140 |
| Target 1.5R | -0.043 | -0.098 | -0.165 | -0.223 | -0.004 | -0.115 |
| Target 2R | -0.018 | -0.085 | -0.147 | -0.217 | +0.035 | -0.152 |
| Target 2.5R | -0.117 | -0.149 | -0.154 | -0.280 | +0.023 | -0.126 |
| Target 4R | -0.166 | -0.041 | -0.140 | -0.461 | +0.080 | -0.092 |
| BE-1: stop to entry after +1R (TP 3R) | -0.169 | -0.108 | -0.197 | -0.312 | +0.023 | -0.084 |
| BE-1.5: stop to entry after +1.5R (TP 3R) | -0.018 | -0.115 | -0.171 | -0.363 | +0.046 | -0.084 |
| BE-2: stop to entry after +2R (TP 3R) | -0.084 | -0.066 | -0.140 | -0.348 | +0.048 | -0.096 |
| Lock A: at +1R stop to +0.25R (TP 3R) | -0.113 | -0.103 | -0.202 | -0.315 | +0.030 | -0.091 |
| Lock B: at +1.5R stop to +0.5R (TP 3R) | +0.006 | -0.066 | -0.142 | -0.354 | +0.072 | -0.100 |
| Lock C: at +2R stop to +1R (TP 3R) | -0.035 | -0.077 | -0.117 | -0.259 | +0.087 | -0.134 |
| ATR trail 1.0 x ATR14 after +1R (TP 3R) | -0.186 | -0.155 | -0.175 | -0.278 | -0.018 | -0.109 |
| ATR trail 1.5 x ATR14 after +1R (TP 3R) | -0.276 | -0.142 | -0.166 | -0.307 | +0.019 | -0.138 |
| ATR trail 2.0 x ATR14 after +1R (TP 3R) | -0.199 | -0.130 | -0.126 | -0.304 | +0.043 | -0.126 |
| ATR trail 1.0 x ATR14 after +1R, no target | -0.186 | -0.164 | -0.189 | -0.304 | +0.002 | -0.112 |
| ATR trail 1.5 x ATR14 after +1R, no target | -0.269 | -0.146 | -0.171 | -0.355 | +0.014 | -0.118 |
| ATR trail 2.0 x ATR14 after +1R, no target | -0.262 | -0.137 | -0.105 | -0.379 | +0.049 | -0.077 |
| Structure trail: last completed 5-min candle low/high after +1R (TP 3R) | -0.127 | -0.123 | -0.130 | -0.297 | -0.005 | -0.121 |
| Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R) | -0.162 | -0.161 | -0.154 | -0.348 | +0.047 | -0.123 |
| P1: 50% at 1R, 50% at 3R | -0.084 | -0.127 | -0.145 | -0.319 | +0.019 | -0.122 |
| P2: 50% at 1.5R, 50% at 3R | -0.072 | -0.099 | -0.136 | -0.308 | +0.034 | -0.115 |
| P3: 50% at 2R, 50% at 4R | -0.092 | -0.063 | -0.145 | -0.339 | +0.048 | -0.127 |

## STEP 12 - Final comparison

| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD | DEV | VAL | OOS | New 21 months (n / avg net R) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | +65.7 | -182.5 | -0.089 | 1.04 | 76 | -0.131 | +0.126 | -0.178 | 1151 / -0.205 |
| Target 0.5R | 2049 | 65.4% | -39.2 | -287.4 | -0.140 | 0.95 | 52 | -0.176 | -0.080 | -0.095 | 1151 / -0.154 |
| Target 0.75R | 2049 | 55.7% | -53.0 | -301.3 | -0.147 | 0.94 | 70 | -0.176 | -0.081 | -0.127 | 1151 / -0.151 |
| Target 1R | 2049 | 49.4% | -27.7 | -275.9 | -0.135 | 0.97 | 45 | -0.168 | -0.022 | -0.147 | 1151 / -0.146 |
| Target 1.25R | 2049 | 44.0% | -25.5 | -273.7 | -0.134 | 0.98 | 56 | -0.167 | -0.005 | -0.162 | 1151 / -0.158 |
| Target 1.5R | 2049 | 40.7% | +34.8 | -213.4 | -0.104 | 1.03 | 41 | -0.130 | +0.013 | -0.145 | 1151 / -0.165 |
| Target 2R | 2049 | 34.2% | +53.1 | -195.2 | -0.095 | 1.04 | 67 | -0.116 | +0.082 | -0.209 | 1151 / -0.187 |
| Target 2.5R | 2049 | 28.8% | +16.1 | -232.2 | -0.113 | 1.01 | 61 | -0.144 | +0.060 | -0.195 | 1151 / -0.189 |
| Target 4R | 2049 | 20.6% | +48.0 | -200.2 | -0.098 | 1.03 | 96 | -0.144 | +0.141 | -0.198 | 1151 / -0.170 |
| BE-1: stop to entry after +1R (TP 3R) | 2049 | 17.2% | +17.5 | -230.7 | -0.113 | 1.02 | 72 | -0.163 | +0.051 | -0.127 | 1151 / -0.170 |
| BE-1.5: stop to entry after +1.5R (TP 3R) | 2049 | 20.4% | +35.3 | -213.0 | -0.104 | 1.03 | 71 | -0.151 | +0.067 | -0.134 | 1151 / -0.186 |
| BE-2: stop to entry after +2R (TP 3R) | 2049 | 22.9% | +56.5 | -191.7 | -0.094 | 1.04 | 66 | -0.132 | +0.101 | -0.173 | 1151 / -0.204 |
| Lock A: at +1R stop to +0.25R (TP 3R) | 2049 | 49.0% | +20.2 | -228.0 | -0.111 | 1.02 | 74 | -0.163 | +0.059 | -0.125 | 1151 / -0.172 |
| Lock B: at +1.5R stop to +0.5R (TP 3R) | 2049 | 40.6% | +71.2 | -177.0 | -0.086 | 1.06 | 64 | -0.122 | +0.095 | -0.160 | 1151 / -0.179 |
| Lock C: at +2R stop to +1R (TP 3R) | 2049 | 34.2% | +93.4 | -154.8 | -0.076 | 1.07 | 66 | -0.103 | +0.144 | -0.214 | 1151 / -0.194 |
| ATR trail 1.0 x ATR14 after +1R (TP 3R) | 2049 | 48.1% | -13.1 | -261.3 | -0.128 | 0.99 | 50 | -0.172 | -0.000 | -0.120 | 1151 / -0.166 |
| ATR trail 1.5 x ATR14 after +1R (TP 3R) | 2049 | 45.1% | -11.6 | -259.8 | -0.127 | 0.99 | 54 | -0.174 | +0.034 | -0.146 | 1151 / -0.162 |
| ATR trail 2.0 x ATR14 after +1R (TP 3R) | 2049 | 40.9% | +32.8 | -215.5 | -0.105 | 1.03 | 52 | -0.152 | +0.092 | -0.162 | 1151 / -0.177 |
| ATR trail 1.0 x ATR14 after +1R, no target | 2049 | 48.1% | -18.1 | -266.4 | -0.130 | 0.98 | 65 | -0.177 | -0.002 | -0.118 | 1151 / -0.168 |
| ATR trail 1.5 x ATR14 after +1R, no target | 2049 | 45.1% | -20.4 | -268.6 | -0.131 | 0.98 | 71 | -0.183 | +0.022 | -0.129 | 1151 / -0.154 |
| ATR trail 2.0 x ATR14 after +1R, no target | 2049 | 40.8% | +42.5 | -205.7 | -0.100 | 1.04 | 73 | -0.167 | +0.141 | -0.143 | 1151 / -0.135 |
| Structure trail: last completed 5-min candle low/high after +1R (TP 3R) | 2049 | 46.0% | +14.5 | -233.8 | -0.114 | 1.01 | 50 | -0.148 | +0.016 | -0.142 | 1151 / -0.166 |
| Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R) | 2049 | 36.0% | +7.7 | -240.5 | -0.117 | 1.01 | 66 | -0.172 | +0.110 | -0.181 | 1151 / -0.208 |
| P1: 50% at 1R, 50% at 3R | 2049 | 25.8% | +17.0 | -231.3 | -0.113 | 1.02 | 57 | -0.150 | +0.048 | -0.163 | 1151 / -0.179 |
| P2: 50% at 1.5R, 50% at 3R | 2049 | 40.6% | +44.3 | -203.9 | -0.100 | 1.04 | 52 | -0.133 | +0.067 | -0.165 | 1151 / -0.188 |
| P3: 50% at 2R, 50% at 4R | 2049 | 34.1% | +42.5 | -205.7 | -0.100 | 1.03 | 65 | -0.133 | +0.104 | -0.207 | 1151 / -0.181 |

## Acceptance criteria (improvement in average net R against 'Original 3R' under the same execution rule)

| Exit | 1 overall | 2 DEV | 3 VAL | 4 OOS | 5 years (improved / with best year removed) | 6 at 1.5x spread | 7 adjacent parameter | Passes 1-7 | 8 untouched 21 months |
|---|---|---|---|---|---|---|---|---|---|
| Target 0.5R | no (-0.051) | no (-0.044) | no (-0.206) | yes (+0.083) | no (2/6) | no | no | **no** | yes (+0.051) |
| Target 0.75R | no (-0.058) | no (-0.045) | no (-0.207) | yes (+0.051) | no (2/6) | no | no | **no** | yes (+0.054) |
| Target 1R | no (-0.046) | no (-0.037) | no (-0.148) | yes (+0.031) | no (2/6) | no | no | **no** | yes (+0.059) |
| Target 1.25R | no (-0.045) | no (-0.036) | no (-0.131) | yes (+0.015) | no (2/6) | no | no | **no** | yes (+0.047) |
| Target 1.5R | no (-0.015) | yes (+0.002) | no (-0.113) | yes (+0.033) | no (3/6) | no | no | **no** | yes (+0.041) |
| Target 2R | no (-0.006) | yes (+0.015) | no (-0.045) | no (-0.031) | no (3/6) | no | no | **no** | yes (+0.018) |
| Target 2.5R | no (-0.024) | no (-0.013) | no (-0.066) | no (-0.017) | no (1/6) | no | no | **no** | yes (+0.017) |
| Target 4R | no (-0.009) | no (-0.013) | yes (+0.015) | no (-0.020) | no (2/6) | no | no | **no** | yes (+0.035) |
| BE-1: stop to entry after +1R (TP 3R) | no (-0.024) | no (-0.031) | no (-0.075) | yes (+0.051) | no (2/6) | no | no | **no** | yes (+0.035) |
| BE-1.5: stop to entry after +1.5R (TP 3R) | no (-0.015) | no (-0.020) | no (-0.060) | yes (+0.044) | no (3/6) | no | no | **no** | yes (+0.019) |
| BE-2: stop to entry after +2R (TP 3R) | no (-0.004) | no (-0.001) | no (-0.025) | yes (+0.005) | no (4/6) | no | no | **no** | yes (+0.001) |
| Lock A: at +1R stop to +0.25R (TP 3R) | no (-0.022) | no (-0.032) | no (-0.068) | yes (+0.053) | no (2/6) | no | yes | **no** | yes (+0.033) |
| Lock B: at +1.5R stop to +0.5R (TP 3R) | yes (+0.003) | yes (+0.009) | no (-0.031) | yes (+0.018) | no (4/6) | yes | yes | **no** | yes (+0.026) |
| Lock C: at +2R stop to +1R (TP 3R) | yes (+0.013) | yes (+0.028) | yes (+0.018) | no (-0.036) | no (4/6) | yes | yes | **no** | yes (+0.011) |
| ATR trail 1.0 x ATR14 after +1R (TP 3R) | no (-0.038) | no (-0.041) | no (-0.126) | yes (+0.058) | no (1/6) | no | no | **no** | yes (+0.039) |
| ATR trail 1.5 x ATR14 after +1R (TP 3R) | no (-0.038) | no (-0.043) | no (-0.092) | yes (+0.031) | no (1/6) | no | no | **no** | yes (+0.043) |
| ATR trail 2.0 x ATR14 after +1R (TP 3R) | no (-0.016) | no (-0.021) | no (-0.035) | yes (+0.016) | no (1/6) | no | no | **no** | yes (+0.028) |
| ATR trail 1.0 x ATR14 after +1R, no target | no (-0.041) | no (-0.045) | no (-0.128) | yes (+0.059) | no (1/6) | no | no | **no** | yes (+0.037) |
| ATR trail 1.5 x ATR14 after +1R, no target | no (-0.042) | no (-0.052) | no (-0.104) | yes (+0.049) | no (1/6) | no | no | **no** | yes (+0.051) |
| ATR trail 2.0 x ATR14 after +1R, no target | no (-0.011) | no (-0.036) | yes (+0.015) | yes (+0.035) | no (3/6) | no | no | **no** | yes (+0.070) |
| Structure trail: last completed 5-min candle low/high after +1R (TP 3R) | no (-0.025) | no (-0.017) | no (-0.110) | yes (+0.035) | no (1/6) | no | n/a | **no** | yes (+0.039) |
| Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R) | no (-0.028) | no (-0.041) | no (-0.016) | no (-0.003) | no (1/6) | no | n/a | **no** | no (-0.002) |
| P1: 50% at 1R, 50% at 3R | no (-0.024) | no (-0.019) | no (-0.078) | yes (+0.015) | no (2/6) | no | no | **no** | yes (+0.026) |
| P2: 50% at 1.5R, 50% at 3R | no (-0.010) | no (-0.002) | no (-0.060) | yes (+0.013) | no (3/6) | no | no | **no** | yes (+0.017) |
| P3: 50% at 2R, 50% at 4R | no (-0.011) | no (-0.002) | no (-0.022) | no (-0.029) | no (3/6) | no | no | **no** | yes (+0.024) |

## Exact engine runs (one position at a time, an earlier exit frees the slot for the next signal)

| Exit | Trades | Win rate | Net R | Avg net R | DEV | VAL | OOS |
|---|---|---|---|---|---|---|---|
| Original 3R | 2049 | 25.8% | -182.5 | -0.089 | -0.131 | +0.126 | -0.178 |

## The path after entry is a fair game: observed versus a driftless random walk

For a driftless price path the probability of reaching +L R before -1 R is 1 / (1 + L), and from a current level x the probability of reaching +3 R before -1 R is (x + 1) / 4. Nothing about the strategy was used to make these predictions.

| Level L | Observed reach before the stop | Random-walk prediction 1/(1+L) | Difference |
|---|---|---|---|
| +0.25R | 77.7% | 80.0% | -2.3 pts |
| +0.5R | 65.4% | 66.7% | -1.2 pts |
| +0.75R | 55.7% | 57.1% | -1.5 pts |
| +1.0R | 49.3% | 50.0% | -0.7 pts |
| +1.25R | 43.9% | 44.4% | -0.6 pts |
| +1.5R | 40.6% | 40.0% | +0.6 pts |
| +2.0R | 34.0% | 33.3% | +0.6 pts |
| +2.5R | 28.5% | 28.6% | -0.1 pts |
| +3.0R | 25.5% | 25.0% | +0.5 pts |
| +4.0R | 19.8% | 20.0% | -0.2 pts |
| +5.0R | 16.1% | 16.7% | -0.6 pts |

| After reaching | Give-back | Position after the give-back (x) | Observed went on to 3R | Random-walk (x+1)/4 |
|---|---|---|---|---|
| +1.0R | >= 0.5R | +0.5R | 39.8% (n 802) | 37.5% |
| +1.0R | >= 1.0R | +0.0R | 26.8% (n 660) | 25.0% |
| +1.5R | >= 0.5R | +1.0R | 49.2% (n 599) | 50.0% |
| +1.5R | >= 1.0R | +0.5R | 36.9% (n 482) | 37.5% |
| +2.0R | >= 0.5R | +1.5R | 61.0% (n 439) | 62.5% |
| +2.0R | >= 1.0R | +1.0R | 47.7% (n 327) | 50.0% |

The base rate of reaching 3R at all is 25.5% against 25.0% predicted; after reaching +1R and falling back to entry it is 26.8% against 25.0%; after reaching +1.5R and falling to +0.5R it is 36.6% against 37.5%; after +2R and a 1R give-back 47.7% against 50%. Every horizon and every intermediate sequence sits within one or two points of the fair-game value. The intermediate levels carry no information beyond where the price currently is, which is the formal reason no exit rule can add expectancy: exits can only reshape the payoff distribution, and the spread is paid on every shape.

## Findings

### STEP 1 - what the MFE / MAE distribution says

- 49.3% of entries reach +1R before the original stop, 34.0% reach +2R, 25.5% reach +3R, 19.8% reach +4R and 16.1% reach +5R. This is the 'many reach +1R, few reach +3R' picture the brief anticipated, and the fixed R:R curve tested the implied remedy: every lower target is worse net (0.5R -0.140, 1R -0.135, 1.5R -0.104, 2R -0.095 against -0.089 for 3R), because the reach probabilities fall exactly as fast as the payoff rises. Gross expectancy is within 0.03R of zero at every target from 0.5R to 4R.
- Losers do travel into profit first: 53% of them were +0.5R, 32% were +1R and 11% were +2R before being stopped. Winners travel against first just as often: 41% were -0.5R and 22% were -0.75R before reaching 3R. The give-backs are symmetric noise, not a signal that a loss is coming.
- Among winners the uncapped run after entry is large (median 6.4R, upper quartile 11.7R before the original stop is ever hit within 3 days), which is why the 'let it run' variants (4R target, ATR trail without target) do not lose more than the others; but their reach probabilities also fall in step, so they do not gain either.

### STEP 8 - path dependency

- Reaching an intermediate level changes the odds exactly as much as the current price implies and no more (table above). 'Reached 1.5R then fell to +0.5R' goes on to 3R 36.6% of the time; a fair game from +0.5R says 37.5%. There is no memory in the path.

### STEPS 3, 4 - break-even and profit locks

- BE-1 saved 471 losers (-1R to 0) and killed 177 winners (+3R to 0): -48R. In a fair game three quarters of the trades that return to entry after +1R would have been stopped and one quarter would have reached 3R (observed 471 : 177 = 73 : 27), so break-even is neutral by arithmetic and pays the same spread on more zero-R trades.
- Lock C (at +2R, stop to +1R) is the best variant in the lab: saved 171 losers into +1R and cut 156 winners to +1R, +28R gross, -0.076R net per trade against -0.089. It improves Development (+0.028) and Validation (+0.018) but is worse out of sample (-0.036) and negative once its best year is removed. Lock B improves DEV and OOS but not VAL. Neither passes.

### STEPS 5, 6, 7 - trails and partials

- Every ATR trail (1, 1.5, 2 ATR; with or without the target) and both structure trails are worse than 3R by 0.01-0.04R per trade: they turn 26-28% of the +3R winners into +0.3R to +1.5R exits and save fewer losers than that costs. Tighter trails are worse than looser ones in a monotone way, which is what a fair game predicts (each stop move buys protection at fair price and then pays the spread).
- Partial exits are the same arithmetic in another shape: P1 (50% at 1R) converts 529 winners from +3R to +2R and 479 losers from -1R to 0R, net -49R. P2 and P3 -22R and -23R.

### STEPS 10-12 - costs, out-of-sample, untouched months

- No variant improves net expectancy in Development, Validation and Out-of-sample together; none passes the year test; the two locks that pass the 1.5x-spread test fail elsewhere. The 21 untouched months show small positive deltas for almost every variant (+0.01 to +0.07R) because the original rule was worse there (-0.205R per trade, 23.5% winners) and anything that shortens trades loses less; every variant is still between -0.135 and -0.208R per trade on those months.
- The exact engine run with the one-position rule reproduces the reference (-0.089R per trade); no survivor existed to run.

### Conclusion

The price path after these entries is statistically a fair game at every horizon and after every intermediate sequence tested. Fixed targets from 0.5R to 4R, break-even at +1/+1.5/+2R, three profit locks, three ATR trails with and without a target, two structure trails and three partial-exit structures all end between -0.076 and -0.147R net per trade against -0.089 for the original 3R, and none satisfies the acceptance criteria. Combined with V3 (no pre-entry information) and V2 (no filter, target or session rule beyond break-even), the entry + exit combination of the previous-day volume-zone strategy does not demonstrate a reliable edge. Exit management cannot rescue an entry whose subsequent path has no drift; it can only change the shape of the same zero and add cost sensitivity. Research on this rule set should stop here.
