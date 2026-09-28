# Silver (XAGUSD): final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)

Silver (XM's 15-minute and hourly bars, so 15m-D1 only): negative from 15m to 2h in both configurations (spread $3 and swap $1 per night per 0.01 lot), positive on 4h as written (+$849, 221 trades) and on D1 as written (+$1,764 on 30 trades, PF 3.8). Both are the 2025-26 silver rally: TRAIN is negative (-$702 and -$102), the out-of-sample window holds +$1,558 and +$1,465, seven strong-bull long trades make the D1 result, and the net without the five best trades is negative in both. The 2015-2026 daily history is +$1,681 as written (PF 2.1) but positive in only 4 of 12 years and negative with the ATR exits. A one-regime result.

## 1. Setup

Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol SILVER: point 0.001, contract 5,000, quote currency USD, swap long/short -20.39/4.39 points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage 5 pts per side, swap), C stress (1.5x spread, 15 pts slippage). Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.


## 2a. Every timeframe, ASIS

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 2632 | 2,238.60 | -5,046.70 | -9,626.34 | 0.72 | 26.80 | -1.92 | -0.23 | 5,046.70 | -2.67 |  | -2,540.56 | -1,603.95 | -902.19 | negative |
| 30m | 1442 | 2,359.70 | -951.83 | -3,597.11 | 0.92 | 31.20 | -0.66 | -0.15 | 2,392.20 | -0.38 |  | -1,493.37 | -772.88 | 1,314.41 | negative |
| 1h | 740 | 666.45 | -1,559.76 | -3,153.76 | 0.81 | 36.40 | -2.11 | -0.09 | 1,586.06 | -0.49 |  | -597.99 | -459.21 | -502.55 | negative |
| 2h | 422 | 1,109.80 | -326.74 | -1,405.67 | 0.94 | 40.50 | -0.77 | -0.03 | 1,112.32 | -0.14 |  | -603.12 | -239.22 | 515.61 | negative |
| 4h | 221 | 1,574.15 | 849.03 | 250.21 | 1.25 | 43.40 | 3.84 | -0.03 | 894.43 | 0.28 | 263.30 | -702.38 | -6.58 | 1,558.00 | unstable |
| D1 | 30 | 2,060.85 | 1,763.68 | 1,737.90 | 3.79 | 33.30 | 58.79 | 0.26 | 266.23 | 0.47 | 133.40 | -102.49 | 400.78 | 1,465.38 | unstable |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 15m | 0 / 0 | -587 / 280 | -1352 / 589 | -1125 / 584 | -1129 / 656 | -853 / 523 |
| 30m | 0 / 0 | -353 / 152 | -776 / 326 | -534 / 314 | -276 / 361 | 986 / 289 |
| 1h | 0 / 0 | -132 / 72 | -364 / 155 | -106 / 160 | -167 / 180 | -791 / 173 |
| 2h | 0 / 0 | -196 / 44 | -314 / 93 | -193 / 91 | 644 / 91 | -269 / 103 |
| 4h | 0 / 0 | -177 / 19 | -324 / 49 | -272 / 48 | 745 / 49 | 878 / 56 |
| D1 | 0 / 0 | 0 / 0 | -69 / 5 | -17 / 10 | 384 / 9 | 1465 / 6 |

## 2b. Every timeframe, FINAL_H4

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 2932 | 4,026.20 | -4,110.40 | -9,363.07 | 0.80 | 33.50 | -1.40 | -0.22 | 4,774.65 | -1.38 |  | -2,735.04 | -1,363.72 | -11.64 | negative |
| 30m | 1615 | 3,509.10 | -783.79 | -3,844.06 | 0.94 | 36.20 | -0.49 | -0.16 | 2,698.78 | -0.17 |  | -1,680.40 | -800.06 | 1,696.68 | negative |
| 1h | 790 | -565.65 | -2,728.06 | -3,832.73 | 0.77 | 33.50 | -3.45 | -0.12 | 2,780.35 | -0.74 |  | -905.32 | -542.53 | -1,280.20 | negative |
| 2h | 446 | 1,215.40 | -155.44 | -1,065.84 | 0.98 | 32.70 | -0.35 | -0.03 | 2,355.46 | -0.05 |  | -614.79 | -245.12 | 704.47 | negative |
| 4h | 208 | 937.70 | -240.11 | -633.56 | 0.96 | 31.70 | -1.15 | -0.05 | 1,433.13 | -0.09 |  | -682.75 | -124.05 | 566.69 | negative |
| D1 | 33 | -102.45 | -444.59 | -524.73 | 0.86 | 36.40 | -13.47 | -0.01 | 2,256.32 | -0.18 |  | -248.99 | -68.79 | -126.82 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 15m | 0 / 0 | -713 / 322 | -1339 / 675 | -1184 / 670 | -1094 / 716 | 219 / 549 |
| 30m | 0 / 0 | -373 / 171 | -932 / 397 | -581 / 372 | -5 / 402 | 1107 / 273 |
| 1h | 0 / 0 | -156 / 83 | -552 / 185 | -237 / 183 | -181 / 189 | -1602 / 150 |
| 2h | 0 / 0 | -162 / 54 | -363 / 116 | -202 / 95 | 969 / 103 | -398 / 78 |
| 4h | 0 / 0 | -225 / 21 | -198 / 47 | -347 / 49 | 427 / 51 | 103 / 40 |
| D1 | 0 / 0 | 0 / 0 | -145 / 5 | -170 / 10 | 1126 / 11 | -1255 / 7 |

## 3. D1 on the long hourly path 2015-2026

| config | scenario | trades | net $ | PF | exp R | max DD $ | years > 0 | by year |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 89 | 2,283.80 | 2.68 | 0.21 | 333.40 | 7/12 | 2015: -39, 2016: 96, 2017: -47, 2018: 32, 2019: 12, 2020: 238, 2021: -22, 2022: -95, 2023: -3, 2024: 94, 2025: 503, 2026: 1513 |
| ASIS | B | 84 | 1,680.75 | 2.08 | 0.11 | 365.54 | 4/12 | 2015: -39, 2016: -36, 2017: -66, 2018: 47, 2019: -72, 2020: 159, 2021: -5, 2022: -103, 2023: -36, 2024: -18, 2025: 384, 2026: 1466 |
| FINAL_H4 | A | 89 | 85.00 | 1.02 | 0.08 | 2,406.80 | 7/12 | 2015: -38, 2016: -7, 2017: 22, 2018: 27, 2019: 76, 2020: 90, 2021: 130, 2022: -166, 2023: -134, 2024: 5, 2025: 1322, 2026: -1241 |
| FINAL_H4 | B | 86 | -496.61 | 0.89 | 0.03 | 2,428.77 | 5/12 | 2015: -38, 2016: -17, 2017: -9, 2018: 66, 2019: 11, 2020: 50, 2021: 66, 2022: -171, 2023: -147, 2024: -164, 2025: 1133, 2026: -1278 |

## 4. Candidate timeframes: quality, conditions, robustness, variants


### 4h ASIS (verdict unstable, net $849.03, PF 1.251)

- Expectancy $3.8418 (-0.031 R), median R -0.0791, R p05/p25/p75/p95 -1.013/-0.607/0.019/1.713; 8.6% of trades >= +1R, 13.1% <= -1R.
- Concentration: top 10% of trades = 439.0% of net, best 5 trades = 263.3%; net without the best 5 = $-1386.05.
- Longest losing streak 8; max drawdown $894.43 (89.4% of $1,000 per 0.01 lot), longest drawdown 1202 days; recovery factor 0.95; swap paid $287.97.
- Monthly Sharpe 0.25, Sortino 0.67, positive months 26.2%, CAGR on $1,000 = 12.9%; t-stat 0.7, 95% CI of expectancy [-5.9657, 14.8283] $.
- Long 126 / $1560.29, short 95 / $-711.26. Exits {'MA18_exit': 104, 'SL_breakeven': 57, 'SL_swing': 31, 'SL_initial': 29}. Avg hold 2923 min, 3.63 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $808.81, p95 $1275.63, P(lose half) 29.5%.

- trend: strong_bull $1,586/58; weak_bull $-305/56; sideways $-267/48; weak_bear $-27/47; strong_bear $-139/12
- volatility: low $70/13; normal $-343/98; high $603/77; extreme $519/33
- session of entry: Asia $1,039/34; London $589/42; London/NY $-320/82; NewYork $-392/55; Sydney $-67/8
- weekday: Mon $223/37; Tue $-230/49; Wed $181/40; Thu $-424/59; Fri $1,099/36
- direction: long $1,560/126; short $-711/95
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-2,895/79; loss after progress $-490/46; small win $856/77; win >= 1R $3,378/19

- MA grid: 0/60 cells positive on TRAIN, 0 also on VAL and OOS. Exit grid: 0/45 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $-42.31 vs fixed 18/200 $1,201.54 on the test months; chosen beat fixed in 1/6 folds.

- Variants helpful in all splits: V11 no entry when |close - MA18| > 2 ATR (net $1144.14, OOS $1649.78); V12 trend-regime gate: no sideways days (net $1249.95, OOS $1711.25). Harmful: V01, V02, V03, V04, V05, V06, V10, V15, V16, V17. HTF gates helpful: M09 HTF D1 (net $1926.62, OOS $2088.32); M09 HTF D1 (net $1851.23, OOS $1915.97).


## 5. Costs

| config | tf | TF | trades | gross A $ | exec cost $ | swap $ | net B $ | net C $ | cost/trade B $ | break-even cost/trade $ | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 2632 | 2,238.600 | 7,175.370 | 109.930 | -5,046.700 | -9,626.340 | 2.768 | 0.881 | 35.800 | 1.172 | 0.721 | 0.545 |
| ASIS | 30m | 30m | 1442 | 2,359.700 | 3,130.040 | 181.490 | -951.830 | -3,597.110 | 2.296 | 1.680 | 23.400 | 1.241 | 0.919 | 0.730 |
| ASIS | 1h | 1h | 740 | 666.450 | 1,972.520 | 253.690 | -1,559.760 | -3,153.760 | 3.008 | 0.915 | 24.700 | 1.099 | 0.813 | 0.665 |
| ASIS | 2h | 2h | 422 | 1,109.800 | 1,176.550 | 259.990 | -326.740 | -1,405.670 | 3.404 | 2.713 | 21.000 | 1.227 | 0.943 | 0.782 |
| ASIS | 4h | 4h | 221 | 1,574.150 | 437.150 | 287.970 | 849.030 | 250.210 | 3.281 | 7.288 | 14.600 | 1.523 | 1.251 | 1.063 |
| ASIS | D1 | D1 | 30 | 2,060.850 | 11.890 | 285.280 | 1,763.680 | 1,737.900 | 9.906 | 62.450 | 11.000 | 4.652 | 3.792 | 3.675 |
| FINAL_H4 | 15m | 15m | 2932 | 4,026.200 | 8,042.030 | 94.570 | -4,110.400 | -9,363.070 | 2.775 | 1.270 | 33.100 | 1.251 | 0.800 | 0.602 |
| FINAL_H4 | 30m | 30m | 1615 | 3,509.100 | 4,128.200 | 164.690 | -783.790 | -3,844.060 | 2.658 | 2.084 | 24.500 | 1.297 | 0.944 | 0.759 |
| FINAL_H4 | 1h | 1h | 790 | -565.650 | 1,921.980 | 240.430 | -2,728.060 | -3,832.730 | 2.737 | -0.692 | 19.600 | 0.946 | 0.765 | 0.694 |
| FINAL_H4 | 2h | 2h | 446 | 1,215.400 | 1,118.350 | 252.490 | -155.440 | -1,065.840 | 3.074 | 2.762 | 15.100 | 1.171 | 0.980 | 0.867 |
| FINAL_H4 | 4h | 4h | 208 | 937.700 | 891.890 | 285.920 | -240.110 | -633.560 | 5.663 | 4.530 | 17.800 | 1.185 | 0.958 | 0.892 |
| FINAL_H4 | D1 | D1 | 33 | -102.450 | 24.400 | 317.740 | -444.590 | -524.730 | 10.368 | -3.013 | 10.900 | 0.967 | 0.863 | 0.841 |

Slippage sweep (USD per 0.01 lot):

| config | TF | slip 0 pts | slip 5 pts | slip 10 pts | slip 20 pts | slip 40 pts |
|---|---|---|---|---|---|---|
| ASIS | 15m | -3,533.10 | -5,046.70 | -6,173.90 | -8,787.35 | -13,974.60 |
| ASIS | 30m | -206.18 | -951.83 | -1,782.86 | -3,091.33 | -6,433.43 |
| ASIS | 1h | -1,108.04 | -1,559.76 | -2,068.73 | -2,940.43 | -4,371.63 |
| ASIS | 2h | -140.14 | -326.74 | -432.77 | -908.60 | -1,828.15 |
| ASIS | 4h | 930.10 | 849.03 | 747.65 | 529.33 | 38.97 |
| FINAL_H4 | 15m | -2,763.30 | -4,110.40 | -5,860.37 | -8,872.87 | -14,362.95 |
| FINAL_H4 | 30m | 24.71 | -783.79 | -1,773.84 | -3,498.30 | -6,813.24 |
| FINAL_H4 | 2h | 13.48 | -155.44 | -371.49 | -837.74 | -1,752.23 |
| FINAL_H4 | 4h | -117.61 | -240.11 | -348.63 | -622.88 | -998.29 |

## 6. Answers

Works: only in the 2025-26 rally on 4h-D1. Stable timeframe: none (0 of 60 MA cells TRAIN-positive on 4h). Costs: 15-20% of gross profit on 1h-4h, $10 per D1 trade. OOS: strongly positive, TRAIN negative. Verdict: unstable, regime-dependent.

## 7. Files
- backtests/xagusd/: every trade list
- research/*.md, research/experiment_log.csv
