# Bitcoin (BTCUSD): final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)

Bitcoin (Binance minute data, XM costs): negative from 1m to 4h in both configurations, where XM's $50 spread and $0.35-per-night swap per 0.01 lot exceed the gross result; positive on D1 with the ATR exits (+$487 on 54 trades, PF 1.61, 4 of 6 years, OOS +$312) and as written (+$126, 144 trades). The daily ATR result has a t-statistic of 1.3, is negative without its five best trades, loses in strong-bull sessions, keeps 24 of 60 MA cells positive on TRAIN (3 in all splits) and does better with the fixed 18/200 than with walk-forward re-optimisation. On the 2018-2026 daily history it is +$572 (PF 1.56, 5 of 8 years). A slow trend-follower with a swap bill, not a defensible edge.

## 1. Setup

Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol BTCUSD: point 0.01, contract 1, quote currency USD, swap long/short -3500.13/-2333.42 points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage 300 pts per side, swap), C stress (1.5x spread, 1000 pts slippage). Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.


## 2a. Every timeframe, ASIS

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 76054 | 19,387.90 | -37,653.37 | -68,747.78 | 0.18 | 4.60 | -0.50 | -0.56 | 37,653.37 | -5.68 |  | -23,921.48 | -8,001.57 | -5,730.33 | negative |
| 3m | 31773 | 9,402.24 | -14,096.58 | -25,284.49 | 0.29 | 4.70 | -0.44 | -0.29 | 14,096.66 | -6.18 |  | -8,520.77 | -3,069.53 | -2,506.28 | negative |
| 5m | 21838 | 6,287.96 | -9,400.10 | -16,725.93 | 0.32 | 4.30 | -0.43 | -0.21 | 9,400.10 | -5.76 |  | -5,869.58 | -2,134.86 | -1,395.66 | negative |
| 10m | 12794 | 4,296.04 | -4,917.44 | -8,923.40 | 0.40 | 4.10 | -0.38 | -0.13 | 4,945.85 | -4.43 |  | -3,141.34 | -1,045.84 | -730.26 | negative |
| 15m | 9179 | 3,143.24 | -3,471.59 | -6,362.00 | 0.43 | 3.70 | -0.38 | -0.10 | 3,516.04 | -3.97 |  | -2,174.54 | -896.26 | -400.79 | negative |
| 30m | 5183 | 1,916.07 | -1,552.73 | -3,595.34 | 0.54 | 3.60 | -0.30 | -0.07 | 1,561.87 | -2.67 |  | -937.61 | -374.10 | -241.02 | negative |
| 1h | 2816 | 1,445.65 | -684.28 | -1,836.37 | 0.66 | 3.60 | -0.24 | -0.03 | 729.29 | -1.36 |  | -481.81 | -171.38 | -31.08 | negative |
| 2h | 1549 | 900.57 | -5.04 | -703.35 | 0.99 | 3.20 | -0.00 | 0.00 | 184.03 | -0.01 |  | 95.84 | 82.94 | -183.83 | negative |
| 4h | 807 | 620.03 | 136.51 | -9.97 | 1.25 | 2.90 | 0.17 | 0.02 | 141.23 | 0.32 | 258.00 | 147.95 | 26.19 | -37.63 | unstable |
| D1 | 144 | 248.17 | 125.93 | 112.81 | 2.34 | 2.80 | 0.87 | 0.04 | 60.56 | 0.38 | 174.70 | 169.81 | -41.26 | -2.62 | unstable |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -6904 / 5548 | -4948 / 16483 | -4222 / 14682 | -11607 / 14404 | -6195 / 14854 | -3777 / 10083 |
| 3m | -2351 / 1861 | -1815 / 6767 | -1540 / 5604 | -4272 / 5720 | -2428 / 7127 | -1690 / 4694 |
| 5m | -1580 / 1297 | -1276 / 4619 | -1047 / 3856 | -2880 / 3884 | -1662 / 4853 | -956 / 3329 |
| 10m | -904 / 767 | -625 / 2658 | -495 / 2225 | -1608 / 2351 | -903 / 2818 | -383 / 1975 |
| 15m | -681 / 563 | -477 / 1872 | -311 / 1560 | -1084 / 1711 | -674 / 2029 | -245 / 1444 |
| 30m | -213 / 305 | -254 / 1082 | -160 / 888 | -519 / 960 | -197 / 1128 | -209 / 820 |
| 1h | -210 / 161 | -88 / 543 | -47 / 513 | -224 / 545 | -140 / 608 | 26 / 446 |
| 2h | 13 / 85 | -47 / 301 | 27 / 257 | 51 / 327 | 57 / 334 | -105 / 245 |
| 4h | 92 / 35 | -28 / 166 | 48 / 126 | -10 / 177 | 7 / 172 | 27 / 131 |
| D1 | 0 / 0 | -4 / 26 | -3 / 22 | 118 / 32 | 16 / 38 | -1 / 26 |

## 2b. Every timeframe, FINAL_H4

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 64686 | 10,864.74 | -34,055.43 | -62,400.98 | 0.34 | 10.90 | -0.53 | -0.60 | 34,055.43 | -5.78 |  | -21,443.96 | -7,235.44 | -5,376.03 | negative |
| 3m | 23109 | 3,423.31 | -12,245.57 | -21,606.39 | 0.53 | 15.60 | -0.53 | -0.35 | 12,250.13 | -6.57 |  | -7,100.72 | -3,052.57 | -2,092.29 | negative |
| 5m | 14641 | 1,800.89 | -8,038.68 | -13,782.88 | 0.59 | 17.50 | -0.55 | -0.27 | 8,038.68 | -5.84 |  | -4,865.41 | -2,035.31 | -1,137.96 | negative |
| 10m | 7749 | 811.22 | -4,331.12 | -7,173.80 | 0.68 | 19.70 | -0.56 | -0.19 | 4,344.53 | -4.71 |  | -2,577.83 | -905.94 | -847.36 | negative |
| 15m | 5298 | 298.98 | -3,254.20 | -5,301.24 | 0.70 | 20.50 | -0.61 | -0.15 | 3,321.08 | -3.73 |  | -1,895.19 | -899.67 | -459.34 | negative |
| 30m | 2783 | 680.34 | -1,405.06 | -2,759.11 | 0.80 | 20.90 | -0.50 | -0.11 | 1,438.27 | -1.78 |  | -844.87 | -461.24 | -98.96 | negative |
| 1h | 1406 | 352.97 | -989.28 | -1,539.63 | 0.81 | 23.80 | -0.70 | -0.06 | 1,107.43 | -1.13 |  | -502.27 | -528.32 | 41.32 | negative |
| 2h | 733 | 323.55 | -204.82 | -466.84 | 0.94 | 26.20 | -0.28 | 0.02 | 461.64 | -0.31 |  | -179.24 | -121.51 | 95.94 | negative |
| 4h | 367 | 96.44 | -304.73 | -447.56 | 0.89 | 26.20 | -0.83 | -0.04 | 435.13 | -0.36 |  | -250.66 | -11.24 | -42.84 | negative |
| D1 | 54 | 670.93 | 487.37 | 476.40 | 1.61 | 33.30 | 9.03 | 0.11 | 187.89 | 0.60 | 112.00 | 122.10 | 53.47 | 311.80 | unstable |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1m | -6270 / 4980 | -4551 / 14176 | -3772 / 13275 | -10034 / 12103 | -5957 / 11875 | -3472 / 8277 |
| 3m | -1893 / 1383 | -1665 / 4936 | -1327 / 4532 | -3492 / 4229 | -2410 / 4766 | -1459 / 3263 |
| 5m | -1164 / 859 | -1145 / 3058 | -841 / 2896 | -2439 / 2703 | -1767 / 3008 | -682 / 2117 |
| 10m | -755 / 475 | -579 / 1577 | -351 / 1488 | -1201 / 1466 | -991 / 1584 | -454 / 1159 |
| 15m | -672 / 338 | -449 / 1059 | -204 / 1031 | -855 / 1014 | -762 / 1053 | -312 / 803 |
| 30m | -263 / 163 | -269 / 546 | -138 / 548 | -286 / 532 | -329 / 572 | -119 / 422 |
| 1h | -184 / 80 | -127 / 285 | -15 / 276 | -432 / 279 | -234 / 283 | 3 / 203 |
| 2h | -84 / 39 | -127 / 140 | 17 / 150 | -7 / 158 | -216 / 144 | 212 / 102 |
| 4h | -47 / 20 | -83 / 70 | -50 / 76 | 173 / 72 | -249 / 74 | -49 / 55 |
| D1 | 0 / 0 | 76 / 8 | -39 / 10 | 112 / 16 | 156 / 11 | 182 / 9 |

## 3. D1 on the long hourly path 2015-2026

| config | scenario | trades | net $ | PF | exp R | max DD $ | years > 0 | by year |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 175 | 534.00 | 5,226.02 | 0.14 | 0.08 | 8/8 | 2019: 0, 2020: 63, 2021: 0, 2022: 30, 2023: 29, 2024: 215, 2025: 23, 2026: 174 |
| ASIS | B | 168 | 386.35 | 4.04 | 0.10 | 60.17 | 6/8 | 2019: -24, 2020: 21, 2021: 54, 2022: -4, 2023: 15, 2024: 144, 2025: 12, 2026: 167 |
| FINAL_H4 | A | 76 | 889.15 | 2.05 | 0.16 | 152.47 | 6/8 | 2019: -19, 2020: 69, 2021: 173, 2022: 45, 2023: -34, 2024: 280, 2025: 163, 2026: 210 |
| FINAL_H4 | B | 80 | 571.88 | 1.56 | 0.01 | 161.57 | 5/8 | 2019: -37, 2020: -22, 2021: 153, 2022: 17, 2023: -74, 2024: 210, 2025: 132, 2026: 193 |

## 4. Candidate timeframes: quality, conditions, robustness, variants


### D1 FINAL_H4 (verdict unstable, net $487.37, PF 1.612)

- Expectancy $9.0254 (0.1146 R), median R -0.1233, R p05/p25/p75/p95 -0.971/-0.568/0.548/1.684; 16.7% of trades >= +1R, 5.6% <= -1R.
- Concentration: top 10% of trades = 129.9% of net, best 5 trades = 112.0%; net without the best 5 = $-58.25.
- Longest losing streak 7; max drawdown $187.89 (18.8% of $1,000 per 0.01 lot), longest drawdown 592 days; recovery factor 2.59; swap paid $158.32.
- Monthly Sharpe 0.6, Sortino 1.27, positive months 24.6%, CAGR on $1,000 = 8.1%; t-stat 1.27, 95% CI of expectancy [-5.0262, 23.236] $.
- Long 32 / $205.63, short 22 / $281.75. Exits {'MA18_exit': 30, 'SL_trailing': 12, 'SL_breakeven': 9, 'SL_initial': 3}. Avg hold 13670 min, 0.89 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $223.5, p95 $362.84, P(lose half) 0.0%.

- trend: strong_bull $-54/20; weak_bull $307/8; sideways $101/9; weak_bear $210/11; strong_bear $-77/6
- volatility: low $264/16; normal $244/35; high $-20/3
- session of entry: Asia $278/26; London $70/3; London/NY $-142/7; NewYork $276/14; Sydney $5/4
- weekday: Mon $129/7; Tue $-174/7; Wed $284/16; Thu $16/15; Fri $62/5; Sat $-5/1; Sun $176/3
- direction: long $206/32; short $282/22
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-676/20; loss after progress $-120/16; small win $544/9; win >= 1R $740/9

- MA grid: 24/60 cells positive on TRAIN, 3 also on VAL and OOS. Exit grid: 52/64 TRAIN-positive, 52 also OOS.
- Walk-forward: re-optimised pairs $82.56 vs fixed 18/200 $217.80 on the test months; chosen beat fixed in 3/5 folds.

- Variants helpful in all splits: none. Harmful: V01, V02, V03, V07, V08, V10, V11, V12, V13, V14, V18. HTF gates helpful: none.


### 4h ASIS (verdict unstable, net $136.51, PF 1.245)

- Expectancy $0.1692 (0.0217 R), median R -0.0011, R p05/p25/p75/p95 -0.206/-0.002/-0.001/-0.0; 1.4% of trades >= +1R, 1.7% <= -1R.
- Concentration: top 10% of trades = 507.4% of net, best 5 trades = 258.0%; net without the best 5 = $-215.61.
- Longest losing streak 131; max drawdown $141.23 (14.1% of $1,000 per 0.01 lot), longest drawdown 933 days; recovery factor 0.97; swap paid $43.40.
- Monthly Sharpe 0.32, Sortino 0.58, positive months 26.2%, CAGR on $1,000 = 2.6%; t-stat 0.65, 95% CI of expectancy [-0.3124, 0.7007] $.
- Long 390 / $260.69, short 417 / $-124.18. Exits {'SL_breakeven': 743, 'MA18_exit': 31, 'SL_swing': 19, 'SL_initial': 14}. Avg hold 259 min, 13.27 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $151.57, p95 $242.62, P(lose half) 0.0%.

- trend: strong_bull $252/220; weak_bull $-74/136; sideways $62/152; weak_bear $-106/174; strong_bear $-17/119
- volatility: low $150/271; normal $-124/419; high $91/106; extreme $-0/5
- session of entry: Asia $61/236; London $74/143; London/NY $-188/156; NewYork $107/228; Sydney $82/44
- weekday: Mon $-120/212; Tue $10/160; Wed $173/107; Thu $-24/139; Fri $51/114; Sat $38/33; Sun $9/42
- direction: long $261/390; short $-124/417
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-551/738; loss after progress $-7/46; small win $194/12; win >= 1R $500/11

- MA grid: 56/60 cells positive on TRAIN, 1 also on VAL and OOS. Exit grid: 36/45 TRAIN-positive, 18 also OOS.
- Walk-forward: re-optimised pairs $-96.81 vs fixed 18/200 $34.15 on the test months; chosen beat fixed in 2/6 folds.

- Variants helpful in all splits: V07 no entries on Monday before 08:00 (weekend gap) (net $225.93, OOS $-1.42). Harmful: V01, V02, V03, V04, V05, V06, V11, V15, V16, V17, V19. HTF gates helpful: none.


### D1 ASIS (verdict unstable, net $125.93, PF 2.338)

- Expectancy $0.8745 (0.0387 R), median R -0.0004, R p05/p25/p75/p95 -0.011/-0.001/-0.0/-0.0; 2.1% of trades >= +1R, 0.0% <= -1R.
- Concentration: top 10% of trades = 174.5% of net, best 5 trades = 174.7%; net without the best 5 = $-94.12.
- Longest losing streak 45; max drawdown $60.56 (6.1% of $1,000 per 0.01 lot), longest drawdown 839 days; recovery factor 2.08; swap paid $34.53.
- Monthly Sharpe 0.38, Sortino 0.89, positive months 6.6%, CAGR on $1,000 = 2.4%; t-stat 0.85, 95% CI of expectancy [-0.9, 3.1377] $.
- Long 78 / $189.44, short 66 / $-63.51. Exits {'SL_breakeven': 138, 'MA18_exit': 3, 'SL_swing': 3}. Avg hold 1081 min, 2.37 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $64.94, p95 $89.52, P(lose half) 0.0%.

- trend: strong_bull $111/44; weak_bull $16/28; sideways $58/27; weak_bear $-59/27; strong_bear $-1/18
- volatility: low $127/45; normal $-1/87; high $-1/12
- session of entry: Asia $68/70; London $-24/14; London/NY $-1/15; NewYork $83/36; Sydney $-1/9
- weekday: Mon $-0/16; Tue $91/20; Wed $60/25; Thu $-4/38; Fri $16/24; Sat $-35/9; Sun $-2/12
- direction: long $189/78; short $-64/66
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-91/134; loss after progress $-3/6; small win $18/1; win >= 1R $202/3

- MA grid: 60/60 cells positive on TRAIN, 0 also on VAL and OOS. Exit grid: 45/45 TRAIN-positive, 9 also OOS.
- Walk-forward: re-optimised pairs $58.83 vs fixed 18/200 $94.37 on the test months; chosen beat fixed in 2/6 folds.

- Variants helpful in all splits: V12 trend-regime gate: no sideways days (net $188.95, OOS $-0.87); V13 regime-aligned direction (net $190.29, OOS $-0.67). Harmful: V02, V03, V07, V10, V15, V18. HTF gates helpful: none.


## 5. Costs

| config | tf | TF | trades | gross A $ | exec cost $ | swap $ | net B $ | net C $ | cost/trade B $ | break-even cost/trade $ | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 9179 | 3,143.240 | 6,555.560 | 59.270 | -3,471.590 | -6,362.000 | 0.721 | 0.279 | 71.700 | 7.692 | 0.429 | 0.270 |
| ASIS | 30m | 30m | 5183 | 1,916.070 | 3,412.450 | 56.350 | -1,552.730 | -3,595.340 | 0.669 | 0.322 | 65.800 | 8.699 | 0.538 | 0.296 |
| ASIS | 1h | 1h | 2816 | 1,445.650 | 2,068.680 | 61.250 | -684.280 | -1,836.370 | 0.756 | 0.472 | 61.400 | 14.551 | 0.662 | 0.401 |
| ASIS | 2h | 2h | 1549 | 900.570 | 858.470 | 47.140 | -5.040 | -703.350 | 0.585 | 0.549 | 51.000 | 14.703 | 0.994 | 0.559 |
| ASIS | 4h | 4h | 807 | 620.030 | 440.120 | 43.400 | 136.510 | -9.970 | 0.599 | 0.739 | 41.100 | 16.354 | 1.245 | 0.987 |
| ASIS | D1 | D1 | 144 | 248.170 | 87.710 | 34.530 | 125.930 | 112.810 | 0.849 | 1.700 | 35.700 | inf | 2.338 | 2.057 |
| FINAL_H4 | 15m | 15m | 5298 | 298.980 | 3,437.560 | 115.620 | -3,254.200 | -5,301.240 | 0.671 | 0.053 | 32.300 | 1.034 | 0.696 | 0.556 |
| FINAL_H4 | 30m | 30m | 2783 | 680.340 | 1,950.530 | 134.870 | -1,405.060 | -2,759.110 | 0.749 | 0.239 | 26.800 | 1.115 | 0.802 | 0.649 |
| FINAL_H4 | 1h | 1h | 1406 | 352.970 | 1,176.110 | 166.140 | -989.280 | -1,539.630 | 0.955 | 0.249 | 24.100 | 1.078 | 0.811 | 0.722 |
| FINAL_H4 | 2h | 2h | 733 | 323.550 | 366.550 | 161.820 | -204.820 | -466.840 | 0.721 | 0.441 | 13.400 | 1.098 | 0.944 | 0.878 |
| FINAL_H4 | 4h | 4h | 367 | 96.440 | 242.150 | 159.020 | -304.730 | -447.560 | 1.093 | 0.263 | 14.500 | 1.040 | 0.886 | 0.839 |
| FINAL_H4 | D1 | D1 | 54 | 670.930 | 25.240 | 158.320 | 487.370 | 476.400 | 3.399 | 12.425 | 12.500 | 1.964 | 1.612 | 1.593 |

Slippage sweep (USD per 0.01 lot):

| config | TF | slip 0 pts | slip 300 pts | slip 600 pts | slip 1200 pts | slip 2400 pts |
|---|---|---|---|---|---|---|
| ASIS | 1m | -33,251.68 | -37,653.37 | -42,109.00 | -50,667.32 | -67,725.56 |
| ASIS | 3m | -12,364.41 | -14,096.58 | -15,892.02 | -19,528.33 | -26,642.73 |
| ASIS | 5m | -8,161.94 | -9,400.10 | -10,654.57 | -13,107.17 | -17,895.90 |
| ASIS | 10m | -4,161.77 | -4,917.44 | -5,548.03 | -6,960.28 | -9,730.89 |
| ASIS | 15m | -2,964.33 | -3,471.59 | -3,890.78 | -4,935.28 | -6,921.13 |
| ASIS | 30m | -1,308.34 | -1,552.73 | -1,781.01 | -2,372.89 | -3,532.03 |
| ASIS | 1h | -539.26 | -684.28 | -828.46 | -1,063.37 | -1,693.84 |
| ASIS | 2h | 40.47 | -5.04 | -81.18 | -204.46 | -462.60 |
| ASIS | 4h | 149.05 | 136.51 | 151.01 | 165.87 | 86.16 |
| ASIS | D1 | 191.06 | 125.93 | 121.43 | 94.20 | 75.50 |
| FINAL_H4 | 1m | -30,211.94 | -34,055.43 | -37,961.26 | -45,630.06 | -60,898.61 |
| FINAL_H4 | 3m | -10,916.77 | -12,245.57 | -13,557.28 | -16,353.56 | -21,866.59 |
| FINAL_H4 | 5m | -7,224.60 | -8,038.68 | -8,860.11 | -10,662.76 | -14,100.38 |
| FINAL_H4 | 10m | -3,897.38 | -4,331.12 | -4,771.06 | -5,692.52 | -7,465.58 |
| FINAL_H4 | 15m | -2,912.07 | -3,254.20 | -3,564.87 | -4,222.06 | -5,433.36 |
| FINAL_H4 | 30m | -1,247.56 | -1,405.06 | -1,690.06 | -1,971.64 | -2,582.92 |
| FINAL_H4 | 1h | -855.78 | -989.28 | -1,059.94 | -1,219.20 | -1,547.16 |
| FINAL_H4 | 2h | -171.59 | -204.82 | -243.41 | -329.17 | -543.22 |
| FINAL_H4 | 4h | -284.66 | -304.73 | -324.53 | -379.24 | -483.48 |

## 6. Answers

Works: only on D1. Stable timeframe: D1. Costs: swap is 12% of gross on D1 and the spread kills everything intraday. Years: 4 of 6. OOS: +$312 (2025-26 up-leg). Robustness: thin (3/60 cells all-split). Variants: none helpful in all splits. Verdict: unstable.

## 7. Files
- backtests/btcusd/: every trade list
- research/*.md, research/experiment_log.csv
