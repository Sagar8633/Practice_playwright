# EURUSD: final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)

EURUSD: negative on 18 of 20 runs after costs; the two positives (4h, +$43 with the ATR exits and +$6 as written) have t-statistics of 0.35 and 0.05 and depend entirely on their five best trades. D1 2015-2026 is negative in both configurations (PF 0.61-0.62). Not tradable.

## 1. Setup

Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol EURUSD: point 1e-05, contract 100,000, quote currency USD, swap long/short -7.96/1.26 points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage 3 pts per side, swap), C stress (1.5x spread, 10 pts slippage). Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.


## 2a. Every timeframe, ASIS

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 47632 | -197.81 | -11,246.22 | -18,528.67 | 0.28 | 15.60 | -0.24 | -0.49 | 11,246.22 | -11.87 |  | -7,063.85 | -2,168.44 | -2,013.94 | negative |
| 3m | 18796 | -391.37 | -4,683.49 | -7,942.66 | 0.41 | 19.60 | -0.25 | -0.36 | 4,683.54 | -10.50 |  | -2,929.52 | -931.59 | -822.38 | negative |
| 5m | 11721 | -307.15 | -3,042.07 | -5,272.41 | 0.47 | 20.70 | -0.26 | -0.31 | 3,042.20 | -9.13 |  | -1,942.47 | -584.04 | -515.56 | negative |
| 10m | 6095 | -102.80 | -1,581.18 | -2,834.67 | 0.59 | 22.10 | -0.26 | -0.24 | 1,581.18 | -5.64 |  | -991.88 | -316.53 | -272.76 | negative |
| 15m | 4093 | -165.71 | -1,142.34 | -1,980.17 | 0.62 | 24.40 | -0.28 | -0.22 | 1,143.20 | -4.76 |  | -727.18 | -242.53 | -172.62 | negative |
| 30m | 2060 | -93.62 | -578.33 | -1,069.12 | 0.70 | 26.40 | -0.28 | -0.14 | 578.39 | -2.53 |  | -322.85 | -170.71 | -84.77 | negative |
| 1h | 1057 | -96.55 | -356.91 | -600.72 | 0.74 | 27.90 | -0.34 | -0.09 | 387.29 | -1.62 |  | -255.55 | -37.55 | -63.81 | negative |
| 2h | 533 | -9.32 | -164.32 | -293.47 | 0.83 | 30.00 | -0.31 | -0.07 | 209.93 | -0.74 |  | -155.47 | -5.37 | -3.48 | negative |
| 4h | 261 | 67.12 | 5.75 | -57.71 | 1.01 | 34.50 | 0.02 | -0.01 | 108.65 | 0.02 | 2,307.70 | -10.16 | -13.79 | 29.70 | unstable |
| D1 | 54 | -7.86 | -35.45 | -46.67 | 0.78 | 42.60 | -0.66 | -0.09 | 93.01 | -0.26 |  | -62.20 | 43.77 | -17.02 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -737 / 3290 | -2502 / 11329 | -2433 / 10342 | -2067 / 8585 | -2293 / 9657 | -1214 / 4429 |
| 3m | -305 / 1306 | -1083 / 4268 | -901 / 4032 | -951 / 3684 | -976 / 3751 | -467 / 1755 |
| 5m | -219 / 878 | -742 / 2594 | -580 / 2502 | -600 / 2335 | -619 / 2318 | -282 / 1094 |
| 10m | -121 / 447 | -317 / 1341 | -334 / 1307 | -333 / 1222 | -354 / 1219 | -122 / 559 |
| 15m | -74 / 276 | -235 / 909 | -235 / 870 | -263 / 815 | -254 / 831 | -81 / 392 |
| 30m | -60 / 135 | -75 / 446 | -132 / 452 | -109 / 390 | -171 / 432 | -32 / 205 |
| 1h | -16 / 64 | -102 / 231 | -75 / 226 | -81 / 219 | -64 / 218 | -19 / 99 |
| 2h | -8 / 31 | -61 / 127 | -30 / 120 | -71 / 103 | 3 / 99 | 2 / 53 |
| 4h | -2 / 13 | 36 / 66 | -9 / 54 | -32 / 55 | 4 / 48 | 8 / 25 |
| D1 | 0 / 0 | 0 / 9 | -18 / 14 | -45 / 13 | 35 / 11 | -8 / 7 |

## 2b. Every timeframe, FINAL_H4

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 60809 | 614.20 | -13,534.87 | -28,438.57 | 0.25 | 16.90 | -0.22 | -0.66 | 13,534.87 | -12.34 |  | -8,456.17 | -2,488.91 | -2,589.79 | negative |
| 3m | 21468 | -5.91 | -4,924.44 | -9,313.00 | 0.42 | 25.00 | -0.23 | -0.39 | 4,924.44 | -10.55 |  | -3,048.78 | -909.43 | -966.22 | negative |
| 5m | 13442 | -187.08 | -3,223.80 | -5,918.50 | 0.48 | 27.60 | -0.24 | -0.32 | 3,223.80 | -8.88 |  | -2,002.98 | -602.21 | -618.61 | negative |
| 10m | 7198 | -55.35 | -1,719.19 | -3,153.50 | 0.59 | 31.00 | -0.24 | -0.24 | 1,719.32 | -6.72 |  | -1,088.12 | -308.73 | -322.34 | negative |
| 15m | 4835 | -103.87 | -1,239.04 | -2,167.64 | 0.62 | 33.10 | -0.26 | -0.20 | 1,239.04 | -5.49 |  | -750.71 | -284.85 | -203.49 | negative |
| 30m | 2521 | -72.16 | -626.83 | -1,106.76 | 0.71 | 35.70 | -0.25 | -0.15 | 630.47 | -2.71 |  | -350.03 | -166.12 | -110.69 | negative |
| 1h | 1228 | -99.60 | -397.71 | -661.37 | 0.74 | 32.50 | -0.32 | -0.10 | 420.58 | -1.86 |  | -291.62 | -46.91 | -59.19 | negative |
| 2h | 604 | -113.49 | -298.17 | -417.75 | 0.73 | 30.00 | -0.49 | -0.09 | 304.43 | -1.33 |  | -247.58 | -21.02 | -29.57 | negative |
| 4h | 282 | 130.49 | 42.75 | 2.11 | 1.06 | 34.00 | 0.15 | 0.04 | 65.45 | 0.16 | 299.10 | -16.44 | 14.64 | 44.55 | unstable |
| D1 | 37 | 37.50 | -2.74 | -8.95 | 0.98 | 35.10 | -0.07 | 0.01 | 91.18 | -0.02 |  | -43.50 | 61.41 | -20.66 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -924 / 4365 | -2849 / 13429 | -2796 / 12592 | -2730 / 12302 | -2645 / 11808 | -1591 / 6313 |
| 3m | -349 / 1534 | -1152 / 4914 | -930 / 4523 | -918 / 4010 | -1017 / 4359 | -558 / 2128 |
| 5m | -238 / 994 | -763 / 3038 | -589 / 2813 | -633 / 2590 | -661 / 2697 | -339 / 1310 |
| 10m | -129 / 519 | -388 / 1616 | -343 / 1525 | -336 / 1389 | -372 / 1440 | -151 / 709 |
| 15m | -69 / 339 | -226 / 1061 | -273 / 1027 | -284 / 951 | -281 / 980 | -107 / 477 |
| 30m | -74 / 171 | -32 / 524 | -161 / 552 | -146 / 498 | -173 / 518 | -41 / 258 |
| 1h | -24 / 77 | -110 / 264 | -87 / 259 | -83 / 256 | -76 / 256 | -17 / 116 |
| 2h | -21 / 39 | -125 / 141 | -59 / 135 | -36 / 115 | -39 / 114 | -18 / 60 |
| 4h | -9 / 14 | 9 / 71 | 14 / 59 | 3 / 59 | 5 / 53 | 20 / 26 |
| D1 | 0 / 0 | 4 / 5 | 13 / 8 | -30 / 12 | 12 / 6 | -1 / 6 |

## 3. D1 on the long hourly path 2015-2026

| config | scenario | trades | net $ | PF | exp R | max DD $ | years > 0 | by year |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 162 | -158.31 | 0.73 | -0.04 | 187.57 | 6/12 | 2015: 0, 2016: -67, 2017: 21, 2018: -52, 2019: -27, 2020: -57, 2021: 16, 2022: 47, 2023: 4, 2024: -41, 2025: 18, 2026: -21 |
| ASIS | B | 161 | -247.34 | 0.62 | -0.08 | 260.99 | 5/12 | 2015: 0, 2016: -79, 2017: 13, 2018: -58, 2019: -26, 2020: -76, 2021: 18, 2022: 50, 2023: -21, 2024: -46, 2025: 11, 2026: -33 |
| FINAL_H4 | A | 137 | -254.40 | 0.69 | -0.04 | 319.22 | 4/12 | 2015: -25, 2016: -138, 2017: 36, 2018: -34, 2019: -58, 2020: -47, 2021: -34, 2022: 52, 2023: 37, 2024: -38, 2025: 18, 2026: -23 |
| FINAL_H4 | B | 138 | -343.01 | 0.61 | -0.08 | 367.20 | 4/12 | 2015: -26, 2016: -144, 2017: 27, 2018: -40, 2019: -68, 2020: -58, 2021: -38, 2022: 51, 2023: 21, 2024: -44, 2025: 6, 2026: -28 |

## 4. Candidate timeframes: quality, conditions, robustness, variants


### 4h FINAL_H4 (verdict unstable, net $42.75, PF 1.059)

- Expectancy $0.1516 (0.0387 R), median R -0.289, R p05/p25/p75/p95 -1.009/-0.573/0.28/1.977; 15.6% of trades >= +1R, 8.9% <= -1R.
- Concentration: top 10% of trades = 1110.9% of net, best 5 trades = 299.1%; net without the best 5 = $-85.13.
- Longest losing streak 9; max drawdown $65.45 (6.5% of $1,000 per 0.01 lot), longest drawdown 930 days; recovery factor 0.65; swap paid $17.71.
- Monthly Sharpe 0.16, Sortino 0.23, positive months 42.6%, CAGR on $1,000 = 0.8%; t-stat 0.35, 95% CI of expectancy [-0.7139, 0.9874] $.
- Long 142 / $19.49, short 140 / $23.26. Exits {'MA18_exit': 188, 'SL_trailing': 44, 'SL_initial': 26, 'SL_breakeven': 23, 'end_of_test': 1}. Avg hold 3672 min, 4.64 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $110.72, p95 $170.66, P(lose half) 0.0%.

- trend: strong_bull $-40/48; weak_bull $20/62; sideways $50/69; weak_bear $16/67; strong_bear $-3/35
- volatility: low $58/62; normal $-25/142; high $-27/70; extreme $36/7
- session of entry: Asia $5/85; London $53/87; London/NY $-78/50; NewYork $23/52; Sydney $40/8
- weekday: Mon $1/62; Tue $-7/43; Wed $29/60; Thu $12/60; Fri $8/57
- direction: long $19/142; short $23/140
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-537/118; loss after progress $-192/68; small win $191/52; win >= 1R $581/44

- MA grid: 2/60 cells positive on TRAIN, 1 also on VAL and OOS. Exit grid: 1/64 TRAIN-positive, 1 also OOS.
- Walk-forward: re-optimised pairs $48.43 vs fixed 18/200 $46.91 on the test months; chosen beat fixed in 4/6 folds.

- Variants helpful in all splits: V07 no entries on Monday before 08:00 (weekend gap) (net $88.29, OOS $60.77); V08 ATR(22)/SMA100(ATR) >= 1.0 (net $94.1, OOS $52.96). Harmful: V01, V02, V04, V05, V06, V10, V12, V13, V14, V16, V17, V19. HTF gates helpful: none.


### 4h ASIS (verdict unstable, net $5.75, PF 1.009)

- Expectancy $0.022 (-0.0119 R), median R -0.2857, R p05/p25/p75/p95 -1.012/-0.586/0.19/1.706; 12.6% of trades >= +1R, 11.9% <= -1R.
- Concentration: top 10% of trades = 7571.7% of net, best 5 trades = 2307.7%; net without the best 5 = $-126.93.
- Longest losing streak 8; max drawdown $108.65 (10.9% of $1,000 per 0.01 lot), longest drawdown 1386 days; recovery factor 0.05; swap paid $18.90.
- Monthly Sharpe 0.02, Sortino 0.03, positive months 49.2%, CAGR on $1,000 = 0.1%; t-stat 0.05, 95% CI of expectancy [-0.815, 0.8985] $.
- Long 130 / $-27.85, short 131 / $33.6. Exits {'MA18_exit': 165, 'SL_breakeven': 35, 'SL_initial': 31, 'SL_swing': 29, 'end_of_test': 1}. Avg hold 4056 min, 4.29 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $112.52, p95 $173.76, P(lose half) 0.0%.

- trend: strong_bull $-41/43; weak_bull $-10/59; sideways $39/67; weak_bear $28/55; strong_bear $-11/36
- volatility: low $37/55; normal $-10/128; high $-58/70; extreme $36/7
- session of entry: Asia $20/79; London $-14/80; London/NY $-66/42; NewYork $39/52; Sydney $27/8
- weekday: Mon $-58/66; Tue $24/40; Wed $19/52; Thu $10/51; Fri $11/52
- direction: long $-28/130; short $34/131
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-444/99; loss after progress $-178/72; small win $196/57; win >= 1R $431/33

- MA grid: 7/60 cells positive on TRAIN, 1 also on VAL and OOS. Exit grid: 0/45 TRAIN-positive, 0 also OOS.
- Walk-forward: re-optimised pairs $-27.33 vs fixed 18/200 $-5.30 on the test months; chosen beat fixed in 3/6 folds.

- Variants helpful in all splits: none. Harmful: V01, V02, V04, V05, V06, V10, V11, V12, V13, V14, V16, V17, V19. HTF gates helpful: none.


## 5. Costs

| config | tf | TF | trades | gross A $ | exec cost $ | swap $ | net B $ | net C $ | cost/trade B $ | break-even cost/trade $ | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 4093 | -165.710 | 954.330 | 22.300 | -1,142.340 | -1,980.170 | 0.239 | -0.043 | 34.200 | 0.927 | 0.622 | 0.453 |
| ASIS | 30m | 30m | 2060 | -93.620 | 459.410 | 25.300 | -578.330 | -1,069.120 | 0.235 | -0.048 | 26.100 | 0.941 | 0.703 | 0.537 |
| ASIS | 1h | 1h | 1057 | -96.550 | 239.530 | 20.830 | -356.910 | -600.720 | 0.246 | -0.095 | 20.300 | 0.918 | 0.741 | 0.614 |
| ASIS | 2h | 2h | 533 | -9.320 | 134.000 | 21.000 | -164.320 | -293.470 | 0.291 | -0.018 | 16.300 | 0.989 | 0.829 | 0.722 |
| ASIS | 4h | 4h | 261 | 67.120 | 42.470 | 18.900 | 5.750 | -57.710 | 0.235 | 0.260 | 8.900 | 1.116 | 1.009 | 0.914 |
| ASIS | D1 | D1 | 54 | -7.860 | 5.760 | 21.830 | -35.450 | -46.670 | 0.511 | -0.143 | 17.900 | 0.948 | 0.781 | 0.736 |
| FINAL_H4 | 15m | 15m | 4835 | -103.870 | 1,115.970 | 19.200 | -1,239.040 | -2,167.640 | 0.235 | -0.021 | 35.600 | 0.960 | 0.624 | 0.446 |
| FINAL_H4 | 30m | 30m | 2521 | -72.160 | 531.930 | 22.740 | -626.830 | -1,106.760 | 0.220 | -0.028 | 26.400 | 0.960 | 0.711 | 0.551 |
| FINAL_H4 | 1h | 1h | 1228 | -99.600 | 279.850 | 18.260 | -397.710 | -661.370 | 0.243 | -0.082 | 21.200 | 0.923 | 0.736 | 0.610 |
| FINAL_H4 | 2h | 2h | 604 | -113.490 | 164.480 | 20.200 | -298.170 | -417.750 | 0.306 | -0.191 | 18.600 | 0.883 | 0.730 | 0.650 |
| FINAL_H4 | 4h | 4h | 282 | 130.490 | 70.030 | 17.710 | 42.750 | 2.110 | 0.311 | 0.463 | 10.200 | 1.194 | 1.059 | 1.003 |
| FINAL_H4 | D1 | D1 | 37 | 37.500 | 14.010 | 26.230 | -2.740 | -8.950 | 1.088 | 1.014 | 18.300 | 1.231 | 0.985 | 0.952 |

Slippage sweep (USD per 0.01 lot):

| config | TF | slip 0 pts | slip 3 pts | slip 6 pts | slip 12 pts | slip 24 pts |
|---|---|---|---|---|---|---|
| ASIS | 4h | 15.80 | 5.75 | -5.54 | -34.82 | -98.89 |
| FINAL_H4 | 1m | -9,977.48 | -13,534.87 | -17,131.48 | -24,154.05 | -38,048.76 |
| FINAL_H4 | 4h | 64.96 | 42.75 | 26.55 | -10.04 | -85.45 |

## 6. Answers

Works: no. Stable timeframe: none; 4h is the least negative. Costs: 2-3 pips per round trip are 10-25% of the gross profit on 1h-4h. Years: 4h ATR positive in 5 of 6 but by $43 in total. OOS: +$45 on 4h. Robustness: 2 of 60 MA cells TRAIN-positive. Variants: skipping Monday-morning entries (V07) is helpful in all splits (+$88, PF 1.13) and passes the robust rule on 282 trades; a hypothesis, not an edge. Verdict: no defensible expectancy.

## 7. Files
- backtests/eurusd/: every trade list
- research/*.md, research/experiment_log.csv
