# USDJPY: final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)

USDJPY is the only major with a positive multi-timeframe result: 1h, 2h and 4h are positive in both configurations, best on 2h with the ATR exits (606 trades, PF 1.29, +$289 per 0.01 lot, t-statistic 2.17, the highest of the study, 5 of 6 years positive, top-5 trades 41% of net). It fails the robust rule because the out-of-sample year is negative (-$14), the walk-forward re-optimisation earns $69 against $175 for the fixed 18/200, and no variant improves expectancy in all three splits; the profit is the 2021-24 yen decline (833 bull sessions against 279 bear) traded from the long side. The 2015-2026 daily history is negative (PF 0.81-0.97). Candidate for a forward test on 2h with London/New York hours (V04), not for trading.

## 1. Setup

Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol USDJPY: point 0.001, contract 100,000, quote currency JPY, swap long/short 2.11/-29.59 points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage 3 pts per side, swap), C stress (1.5x spread, 10 pts slippage). Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.


## 2a. Every timeframe, ASIS

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 52963 | 591.55 | -8,510.12 | -15,195.57 | 0.42 | 19.90 | -0.16 | -0.36 | 8,510.13 | -11.20 |  | -5,125.47 | -1,854.79 | -1,529.85 | negative |
| 3m | 19743 | 551.58 | -2,814.49 | -5,648.93 | 0.62 | 23.40 | -0.14 | -0.23 | 2,821.52 | -6.85 |  | -1,728.24 | -596.35 | -489.89 | negative |
| 5m | 12098 | 509.20 | -1,523.89 | -3,352.01 | 0.71 | 25.10 | -0.13 | -0.17 | 1,524.38 | -4.28 |  | -868.71 | -337.08 | -318.10 | negative |
| 10m | 6218 | 362.62 | -707.60 | -1,712.69 | 0.80 | 27.20 | -0.11 | -0.11 | 729.39 | -2.43 |  | -377.41 | -223.65 | -106.54 | negative |
| 15m | 4227 | 393.49 | -371.50 | -1,046.09 | 0.87 | 27.90 | -0.09 | -0.08 | 425.24 | -1.23 |  | -184.84 | -115.80 | -70.85 | negative |
| 30m | 2129 | 404.72 | 20.26 | -334.81 | 1.01 | 31.10 | 0.01 | 0.01 | 155.20 | 0.07 | 652.30 | -27.70 | 32.50 | 15.46 | unstable |
| 1h | 1069 | 362.08 | 115.84 | -64.57 | 1.09 | 34.10 | 0.11 | 0.06 | 104.49 | 0.42 | 112.60 | 99.36 | 62.28 | -45.80 | unstable |
| 2h | 581 | 348.63 | 211.67 | 141.90 | 1.24 | 45.10 | 0.36 | 0.08 | 75.97 | 0.71 | 68.20 | 230.67 | 2.46 | -21.46 | unstable |
| 4h | 300 | 207.53 | 96.35 | 39.35 | 1.15 | 49.70 | 0.32 | 0.05 | 119.13 | 0.32 | 189.50 | 188.81 | -104.22 | 11.75 | unstable |
| D1 | 85 | -94.11 | -102.04 | -119.22 | 0.44 | 64.70 | -1.20 | -0.08 | 131.80 | -0.71 |  | 2.09 | -44.22 | -59.91 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -672 / 3503 | -1585 / 11755 | -1694 / 11603 | -1784 / 10433 | -1914 / 10664 | -860 / 5005 |
| 3m | -285 / 1407 | -461 / 4317 | -578 / 4273 | -589 / 3971 | -647 / 3946 | -254 / 1829 |
| 5m | -181 / 844 | -214 / 2656 | -269 / 2573 | -286 / 2439 | -429 / 2420 | -144 / 1166 |
| 10m | -73 / 450 | 19 / 1323 | -210 / 1351 | -167 / 1247 | -220 / 1257 | -56 / 590 |
| 15m | -45 / 298 | 52 / 908 | -155 / 949 | -69 / 828 | -109 / 822 | -46 / 422 |
| 30m | -33 / 147 | 105 / 461 | -115 / 477 | 46 / 423 | 28 / 405 | -10 / 216 |
| 1h | -13 / 68 | 84 / 228 | -10 / 236 | 74 / 230 | 13 / 202 | -32 / 105 |
| 2h | -7 / 37 | 138 / 120 | 37 / 132 | 78 / 121 | 16 / 109 | -50 / 62 |
| 4h | -23 / 11 | 84 / 64 | 50 / 71 | 82 / 59 | -90 / 67 | -7 / 28 |
| D1 | 0 / 0 | 26 / 12 | -21 / 21 | -24 / 20 | -21 / 17 | -61 / 15 |

## 2b. Every timeframe, FINAL_H4

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 60330 | 1,517.78 | -9,191.33 | -17,988.84 | 0.43 | 24.60 | -0.15 | -0.43 | 9,191.80 | -10.97 |  | -5,543.17 | -2,005.43 | -1,642.73 | negative |
| 3m | 22479 | 789.53 | -3,115.13 | -6,147.23 | 0.62 | 30.60 | -0.14 | -0.23 | 3,120.61 | -7.01 |  | -1,854.80 | -718.23 | -542.10 | negative |
| 5m | 13948 | 669.80 | -1,755.37 | -3,725.70 | 0.71 | 33.90 | -0.13 | -0.16 | 1,756.74 | -4.94 |  | -983.61 | -423.97 | -347.78 | negative |
| 10m | 7310 | 502.79 | -794.70 | -1,878.58 | 0.80 | 36.00 | -0.11 | -0.11 | 817.12 | -2.64 |  | -404.32 | -257.74 | -132.65 | negative |
| 15m | 4928 | 384.22 | -462.98 | -1,200.80 | 0.86 | 36.90 | -0.09 | -0.08 | 475.24 | -1.62 |  | -191.76 | -164.16 | -107.06 | negative |
| 30m | 2444 | 377.64 | -49.68 | -437.91 | 0.98 | 38.30 | -0.02 | -0.02 | 138.95 | -0.19 |  | -51.93 | 10.85 | -8.61 | negative |
| 1h | 1185 | 366.41 | 76.39 | -121.87 | 1.05 | 37.10 | 0.06 | 0.02 | 121.32 | 0.30 | 145.10 | 86.15 | 57.81 | -67.57 | unstable |
| 2h | 606 | 435.69 | 289.08 | 169.96 | 1.29 | 40.90 | 0.48 | 0.08 | 65.98 | 1.04 | 40.60 | 258.61 | 44.95 | -14.49 | unstable |
| 4h | 295 | 151.91 | 60.07 | 12.21 | 1.07 | 41.00 | 0.20 | 0.06 | 155.95 | 0.20 | 236.80 | 166.67 | -117.18 | 10.58 | unstable |
| D1 | 42 | 9.76 | -10.76 | -15.75 | 0.95 | 28.60 | -0.26 | -0.13 | 148.14 | -0.05 |  | 126.44 | -61.82 | -75.38 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -676 / 3814 | -1681 / 13068 | -1907 / 13449 | -1951 / 12178 | -2043 / 12230 | -933 / 5591 |
| 3m | -282 / 1481 | -555 / 4943 | -642 / 5032 | -621 / 4485 | -735 / 4525 | -281 / 2013 |
| 5m | -193 / 948 | -271 / 3103 | -289 / 2995 | -346 / 2800 | -497 / 2829 | -158 / 1273 |
| 10m | -94 / 537 | -34 / 1592 | -196 / 1569 | -131 / 1434 | -281 / 1502 | -60 / 676 |
| 15m | -53 / 345 | 30 / 1104 | -127 / 1068 | -91 / 958 | -145 / 971 | -76 / 482 |
| 30m | -32 / 161 | 72 / 541 | -99 / 532 | 43 / 491 | 3 / 475 | -38 / 244 |
| 1h | 6 / 71 | 69 / 267 | -27 / 251 | 88 / 246 | -9 / 228 | -50 / 122 |
| 2h | 0 / 39 | 155 / 134 | 30 / 131 | 110 / 131 | 36 / 108 | -43 / 63 |
| 4h | -25 / 11 | 108 / 68 | 28 / 64 | 56 / 63 | -89 / 58 | -18 / 31 |
| D1 | 0 / 0 | 77 / 4 | 21 / 8 | 13 / 11 | -56 / 9 | -66 / 10 |

## 3. D1 on the long hourly path 2015-2026

| config | scenario | trades | net $ | PF | exp R | max DD $ | years > 0 | by year |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 170 | 97.99 | 1.27 | 0.03 | 113.74 | 5/12 | 2015: 0, 2016: 88, 2017: -48, 2018: 14, 2019: -33, 2020: -8, 2021: 0, 2022: 179, 2023: -7, 2024: -21, 2025: -31, 2026: -35 |
| ASIS | B | 172 | -15.47 | 0.96 | -0.02 | 193.04 | 3/12 | 2015: -1, 2016: 51, 2017: -52, 2018: 6, 2019: -57, 2020: -36, 2021: -6, 2022: 181, 2023: -10, 2024: -21, 2025: -37, 2026: -34 |
| FINAL_H4 | A | 123 | 38.87 | 1.07 | 0.00 | 145.22 | 6/12 | 2015: -6, 2016: 51, 2017: -39, 2018: 6, 2019: -62, 2020: -9, 2021: 10, 2022: 152, 2023: 35, 2024: 2, 2025: -52, 2026: -48 |
| FINAL_H4 | B | 125 | -137.24 | 0.81 | -0.09 | 231.92 | 4/12 | 2015: -8, 2016: 9, 2017: -45, 2018: -9, 2019: -89, 2020: -51, 2021: 5, 2022: 154, 2023: 26, 2024: -3, 2025: -79, 2026: -47 |

## 4. Candidate timeframes: quality, conditions, robustness, variants


### 2h FINAL_H4 (verdict unstable, net $289.08, PF 1.29)

- Expectancy $0.477 (0.0826 R), median R -0.2005, R p05/p25/p75/p95 -1.009/-0.535/0.345/2.084; 16.8% of trades >= +1R, 12.2% <= -1R.
- Concentration: top 10% of trades = 263.4% of net, best 5 trades = 40.6%; net without the best 5 = $171.71.
- Longest losing streak 12; max drawdown $65.98 (6.6% of $1,000 per 0.01 lot), longest drawdown 570 days; recovery factor 4.38; swap paid $30.71.
- Monthly Sharpe 1.04, Sortino 2.02, positive months 59.0%, CAGR on $1,000 = 5.1%; t-stat 2.17, 95% CI of expectancy [0.0502, 0.8968] $.
- Long 417 / $188.71, short 189 / $100.37. Exits {'MA18_exit': 356, 'SL_trailing': 94, 'SL_breakeven': 80, 'SL_initial': 76}. Avg hold 1708 min, 9.96 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $73.59, p95 $117.4, P(lose half) 0.0%.

- trend: strong_bull $144/233; weak_bull $30/162; sideways $63/90; weak_bear $34/81; strong_bear $19/40
- volatility: low $40/68; normal $167/313; high $56/196; extreme $26/29
- session of entry: Asia $110/177; London $116/167; London/NY $86/118; NewYork $0/108; Sydney $-23/36
- weekday: Mon $92/100; Tue $12/132; Wed $102/126; Thu $10/129; Fri $73/119
- direction: long $189/417; short $100/189
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-730/220; loss after progress $-267/138; small win $313/146; win >= 1R $972/102

- MA grid: 60/60 cells positive on TRAIN, 5 also on VAL and OOS. Exit grid: 64/64 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $69.25 vs fixed 18/200 $174.96 on the test months; chosen beat fixed in 1/6 folds.

- Variants helpful in all splits: none. Harmful: V01, V06, V07, V08, V09, V10, V11, V12, V15, V17, V18. HTF gates helpful: none.


### 2h ASIS (verdict unstable, net $211.67, PF 1.243)

- Expectancy $0.3643 (0.0773 R), median R -0.1487, R p05/p25/p75/p95 -1.009/-0.561/0.249/2.103; 13.9% of trades >= +1R, 13.6% <= -1R.
- Concentration: top 10% of trades = 346.0% of net, best 5 trades = 68.2%; net without the best 5 = $67.31.
- Longest losing streak 12; max drawdown $75.97 (7.6% of $1,000 per 0.01 lot), longest drawdown 566 days; recovery factor 2.79; swap paid $31.00.
- Monthly Sharpe 0.71, Sortino 1.33, positive months 57.4%, CAGR on $1,000 = 3.9%; t-stat 1.64, 95% CI of expectancy [-0.0727, 0.813] $.
- Long 387 / $181.51, short 194 / $30.16. Exits {'MA18_exit': 301, 'SL_breakeven': 104, 'SL_swing': 96, 'SL_initial': 80}. Avg hold 1820 min, 9.55 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $78.16, p95 $124.21, P(lose half) 0.0%.

- trend: strong_bull $180/203; weak_bull $25/154; sideways $21/92; weak_bear $-8/87; strong_bear $-7/45
- volatility: low $25/62; normal $209/275; high $-39/214; extreme $17/30
- session of entry: Asia $115/168; London $86/153; London/NY $53/117; NewYork $-1/106; Sydney $-42/37
- weekday: Mon $39/91; Tue $0/126; Wed $65/124; Thu $34/115; Fri $73/125
- direction: long $182/387; short $30/194
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-629/202; loss after progress $-243/117; small win $296/181; win >= 1R $788/81

- MA grid: 60/60 cells positive on TRAIN, 1 also on VAL and OOS. Exit grid: 45/45 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $26.22 vs fixed 18/200 $96.86 on the test months; chosen beat fixed in 1/6 folds.

- Variants helpful in all splits: none. Harmful: V02, V07, V08, V09, V11, V13, V15, V17, V18. HTF gates helpful: none.


### 1h ASIS (verdict unstable, net $115.84, PF 1.088)

- Expectancy $0.1084 (0.0564 R), median R -0.3028, R p05/p25/p75/p95 -1.014/-0.603/0.039/2.276; 11.9% of trades >= +1R, 13.3% <= -1R.
- Concentration: top 10% of trades = 930.3% of net, best 5 trades = 112.6%; net without the best 5 = $-14.6.
- Longest losing streak 14; max drawdown $104.49 (10.4% of $1,000 per 0.01 lot), longest drawdown 689 days; recovery factor 1.11; swap paid $43.70.
- Monthly Sharpe 0.42, Sortino 0.76, positive months 47.5%, CAGR on $1,000 = 2.2%; t-stat 0.84, 95% CI of expectancy [-0.1456, 0.3686] $.
- Long 665 / $138.32, short 404 / $-22.48. Exits {'MA18_exit': 708, 'SL_initial': 141, 'SL_swing': 116, 'SL_breakeven': 104}. Avg hold 982 min, 17.58 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $109.9, p95 $169.56, P(lose half) 0.0%.

- trend: strong_bull $107/381; weak_bull $-42/282; sideways $2/175; weak_bear $4/157; strong_bear $45/73
- volatility: low $0/112; normal $149/520; high $-9/385; extreme $-24/51
- session of entry: Asia $60/351; London $1/227; London/NY $-32/194; NewYork $84/237; Sydney $3/60
- weekday: Mon $-41/209; Tue $25/233; Wed $38/217; Thu $104/214; Fri $-9/195; Sun $-0/1
- direction: long $138/665; short $-22/404
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-928/439; loss after progress $-386/265; small win $371/238; win >= 1R $1,059/127

- MA grid: 52/60 cells positive on TRAIN, 6 also on VAL and OOS. Exit grid: 45/45 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $21.37 vs fixed 18/200 $100.06 on the test months; chosen beat fixed in 2/6 folds.

- Variants helpful in all splits: V07 no entries on Monday before 08:00 (weekend gap) (net $137.9, OOS $-35.61); V10 MA18 slope filter over 3 bars (net $143.91, OOS $-29.4). Harmful: V02, V05, V06, V08, V11, V12, V15, V16, V17, V18. HTF gates helpful: none.


### 4h ASIS (verdict unstable, net $96.35, PF 1.154)

- Expectancy $0.3212 (0.0451 R), median R -0.0039, R p05/p25/p75/p95 -1.003/-0.498/0.074/1.578; 9.3% of trades >= +1R, 7.7% <= -1R.
- Concentration: top 10% of trades = 536.5% of net, best 5 trades = 189.5%; net without the best 5 = $-86.19.
- Longest losing streak 9; max drawdown $119.13 (11.9% of $1,000 per 0.01 lot), longest drawdown 728 days; recovery factor 0.81; swap paid $22.54.
- Monthly Sharpe 0.32, Sortino 0.57, positive months 49.2%, CAGR on $1,000 = 1.8%; t-stat 0.73, 95% CI of expectancy [-0.4683, 1.2146] $.
- Long 196 / $143.73, short 104 / $-47.38. Exits {'MA18_exit': 142, 'SL_breakeven': 93, 'SL_swing': 40, 'SL_initial': 25}. Avg hold 3190 min, 4.93 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $97.57, p95 $154.35, P(lose half) 0.0%.

- trend: strong_bull $100/98; weak_bull $-7/80; sideways $11/52; weak_bear $0/43; strong_bear $-4/26
- volatility: low $60/20; normal $16/149; high $11/115; extreme $13/15
- session of entry: Asia $-45/119; London $69/75; London/NY $64/62; NewYork $20/39; Sydney $-12/5
- weekday: Mon $48/61; Tue $54/69; Wed $-53/59; Thu $52/54; Fri $-0/56; Sun $-4/1
- direction: long $144/196; short $-47/104
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-531/109; loss after progress $-95/42; small win $255/121; win >= 1R $467/28

- MA grid: 59/60 cells positive on TRAIN, 9 also on VAL and OOS. Exit grid: 45/45 TRAIN-positive, 37 also OOS.
- Walk-forward: re-optimised pairs $25.20 vs fixed 18/200 $0.04 on the test months; chosen beat fixed in 4/6 folds.

- Variants helpful in all splits: V16 pending order expires after 3 bars (net $119.95, OOS $14.51); V18 confirmation window 3 bars (net $134.59, OOS $11.11). Harmful: V07, V08, V09, V10, V11, V14, V17, V19. HTF gates helpful: none.


### 1h FINAL_H4 (verdict unstable, net $76.39, PF 1.052)

- Expectancy $0.0645 (0.019 R), median R -0.253, R p05/p25/p75/p95 -1.01/-0.555/0.066/2.157; 13.2% of trades >= +1R, 11.1% <= -1R.
- Concentration: top 10% of trades = 1390.0% of net, best 5 trades = 145.1%; net without the best 5 = $-34.43.
- Longest losing streak 12; max drawdown $121.32 (12.1% of $1,000 per 0.01 lot), longest drawdown 625 days; recovery factor 0.63; swap paid $42.55.
- Monthly Sharpe 0.3, Sortino 0.49, positive months 45.9%, CAGR on $1,000 = 1.5%; t-stat 0.57, 95% CI of expectancy [-0.1604, 0.2898] $.
- Long 737 / $124.82, short 448 / $-48.43. Exits {'MA18_exit': 741, 'SL_trailing': 157, 'SL_breakeven': 156, 'SL_initial': 131}. Avg hold 861 min, 19.49 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $116.44, p95 $180.13, P(lose half) 0.0%.

- trend: strong_bull $110/433; weak_bull $-29/314; sideways $-39/195; weak_bear $-16/164; strong_bear $49/78
- volatility: low $4/126; normal $152/592; high $-32/407; extreme $-50/59
- session of entry: Asia $6/391; London $79/266; London/NY $7/202; NewYork $5/261; Sydney $-20/65
- weekday: Mon $-71/222; Tue $26/255; Wed $39/251; Thu $80/243; Fri $0/213; Sun $2/1
- direction: long $125/737; short $-48/448
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-1,052/473; loss after progress $-424/272; small win $460/284; win >= 1R $1,092/156

- MA grid: 51/60 cells positive on TRAIN, 3 also on VAL and OOS. Exit grid: 64/64 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $-23.61 vs fixed 18/200 $75.20 on the test months; chosen beat fixed in 2/6 folds.

- Variants helpful in all splits: V07 no entries on Monday before 08:00 (weekend gap) (net $109.98, OOS $-46.06). Harmful: V04, V05, V06, V08, V09, V11, V15, V17. HTF gates helpful: none.


### 4h FINAL_H4 (verdict unstable, net $60.07, PF 1.072)

- Expectancy $0.2036 (0.06 R), median R -0.2373, R p05/p25/p75/p95 -1.003/-0.531/0.224/2.238; 13.9% of trades >= +1R, 8.8% <= -1R.
- Concentration: top 10% of trades = 914.5% of net, best 5 trades = 236.8%; net without the best 5 = $-82.17.
- Longest losing streak 9; max drawdown $155.95 (15.6% of $1,000 per 0.01 lot), longest drawdown 764 days; recovery factor 0.39; swap paid $26.26.
- Monthly Sharpe 0.2, Sortino 0.34, positive months 42.6%, CAGR on $1,000 = 1.2%; t-stat 0.41, 95% CI of expectancy [-0.7542, 1.1278] $.
- Long 201 / $149.17, short 94 / $-89.09. Exits {'MA18_exit': 181, 'SL_breakeven': 44, 'SL_trailing': 42, 'SL_initial': 28}. Avg hold 3348 min, 4.85 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $128.41, p95 $196.22, P(lose half) 0.0%.

- trend: strong_bull $130/107; weak_bull $-1/74; sideways $-14/48; weak_bear $-18/43; strong_bear $-34/22
- volatility: low $20/25; normal $47/151; high $4/105; extreme $-7/13
- session of entry: Asia $-74/118; London $47/68; London/NY $72/60; NewYork $-17/44; Sydney $32/5
- weekday: Mon $6/57; Tue $0/63; Wed $-68/56; Thu $42/62; Fri $84/56; Sun $-4/1
- direction: long $149/201; short $-89/94
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-612/111; loss after progress $-224/63; small win $265/80; win >= 1R $631/41

- MA grid: 60/60 cells positive on TRAIN, 4 also on VAL and OOS. Exit grid: 64/64 TRAIN-positive, 56 also OOS.
- Walk-forward: re-optimised pairs $-25.60 vs fixed 18/200 $-6.31 on the test months; chosen beat fixed in 3/6 folds.

- Variants helpful in all splits: V04 entries 08:00-21:59 server (London + New York) (net $129.95, OOS $25.31); V06 no entries 00:00-06:59 server (Asia) (net $131.94, OOS $25.31); V11 no entry when |close - MA18| > 2 ATR (net $95.65, OOS $10.94). Harmful: V01, V08, V10, V14, V16, V17, V19. HTF gates helpful: none.


## 5. Costs

| config | tf | TF | trades | gross A $ | exec cost $ | swap $ | net B $ | net C $ | cost/trade B $ | break-even cost/trade $ | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 4227 | 393.490 | 730.750 | 34.240 | -371.500 | -1,046.090 | 0.181 | 0.100 | 23.300 | 1.170 | 0.872 | 0.689 |
| ASIS | 30m | 30m | 2129 | 404.720 | 343.770 | 40.690 | 20.260 | -334.810 | 0.181 | 0.200 | 16.500 | 1.248 | 1.011 | 0.846 |
| ASIS | 1h | 1h | 1069 | 362.080 | 202.540 | 43.700 | 115.840 | -64.570 | 0.230 | 0.351 | 14.700 | 1.320 | 1.088 | 0.955 |
| ASIS | 2h | 2h | 581 | 348.630 | 105.960 | 31.000 | 211.670 | 141.900 | 0.236 | 0.619 | 11.200 | 1.451 | 1.243 | 1.157 |
| ASIS | 4h | 4h | 300 | 207.530 | 88.640 | 22.540 | 96.350 | 39.350 | 0.371 | 0.703 | 13.300 | 1.377 | 1.154 | 1.059 |
| ASIS | D1 | D1 | 85 | -94.110 | 3.200 | 4.730 | -102.040 | -119.220 | 0.093 | -1.107 | 9.000 | 0.451 | 0.439 | 0.402 |
| FINAL_H4 | 15m | 15m | 4928 | 384.220 | 811.640 | 35.560 | -462.980 | -1,200.800 | 0.172 | 0.077 | 23.600 | 1.143 | 0.856 | 0.671 |
| FINAL_H4 | 30m | 30m | 2444 | 377.640 | 386.530 | 40.790 | -49.680 | -437.910 | 0.175 | 0.153 | 17.200 | 1.205 | 0.976 | 0.817 |
| FINAL_H4 | 1h | 1h | 1185 | 366.410 | 247.470 | 42.550 | 76.390 | -121.870 | 0.245 | 0.307 | 15.700 | 1.282 | 1.052 | 0.924 |
| FINAL_H4 | 2h | 2h | 606 | 435.690 | 115.900 | 30.710 | 289.080 | 169.960 | 0.242 | 0.725 | 10.200 | 1.483 | 1.290 | 1.157 |
| FINAL_H4 | 4h | 4h | 295 | 151.910 | 65.580 | 26.260 | 60.070 | 12.210 | 0.311 | 0.520 | 9.300 | 1.196 | 1.072 | 1.014 |
| FINAL_H4 | D1 | D1 | 42 | 9.760 | -3.390 | 23.910 | -10.760 | -15.750 | 0.489 | 0.232 | 9.000 | 1.048 | 0.951 | 0.929 |

Slippage sweep (USD per 0.01 lot):

| config | TF | slip 0 pts | slip 3 pts | slip 6 pts | slip 12 pts | slip 24 pts |
|---|---|---|---|---|---|---|
| ASIS | 1m | -6,254.78 | -8,510.12 | -10,765.47 | -15,276.38 | -24,297.58 |
| ASIS | 3m | -1,973.34 | -2,814.49 | -3,657.43 | -5,340.08 | -8,709.65 |
| ASIS | 5m | -1,010.14 | -1,523.89 | -2,038.73 | -3,068.62 | -5,125.78 |
| ASIS | 10m | -443.60 | -707.60 | -978.23 | -1,507.14 | -2,567.59 |
| ASIS | 15m | -193.10 | -371.50 | -550.94 | -913.81 | -1,645.83 |
| ASIS | 30m | 112.29 | 20.26 | -72.41 | -262.22 | -606.56 |
| ASIS | 1h | 161.74 | 115.84 | 70.61 | -21.44 | -181.77 |
| ASIS | 2h | 238.19 | 211.67 | 190.44 | 163.75 | 64.80 |
| ASIS | 4h | 119.96 | 96.35 | 81.65 | 41.77 | -6.74 |
| FINAL_H4 | 1m | -6,647.15 | -9,191.33 | -11,715.47 | -16,772.80 | -26,527.42 |
| FINAL_H4 | 3m | -2,192.80 | -3,115.13 | -4,059.61 | -5,939.61 | -9,643.40 |
| FINAL_H4 | 5m | -1,153.05 | -1,755.37 | -2,340.61 | -3,497.12 | -5,820.05 |
| FINAL_H4 | 10m | -470.43 | -794.70 | -1,112.50 | -1,726.76 | -2,909.32 |
| FINAL_H4 | 15m | -255.92 | -462.98 | -664.96 | -1,103.73 | -1,891.99 |
| FINAL_H4 | 30m | 52.23 | -49.68 | -142.31 | -357.99 | -780.27 |
| FINAL_H4 | 1h | 129.33 | 76.39 | 12.38 | -66.99 | -293.29 |
| FINAL_H4 | 2h | 311.95 | 289.08 | 261.78 | 208.38 | 93.72 |
| FINAL_H4 | 4h | 70.13 | 60.07 | 47.08 | 32.33 | -12.67 |

## 6. Answers

Works: partly, on 1h-4h during a one-directional trend. Stable timeframe: 2h. Costs: 10-16% of gross profit on 1h-4h. Years: 2h ATR positive 2022-2026, negative Sep-Dec 2021. OOS: -$14. Robustness: all 60 MA cells positive on TRAIN, 5 also in VAL and OOS; exit map broadly positive on TRAIN. Variants: session filters (London+NY, no Asia) and regime gates pass the robust rule with OOS of +$1 to +$8; none is helpful in all splits. Verdict: unstable, trend-dependent.

## 7. Files
- backtests/usdjpy/: every trade list
- research/*.md, research/experiment_log.csv
