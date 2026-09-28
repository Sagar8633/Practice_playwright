# US Oil (WTI): final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)

US Oil (XM's 15-minute and hourly bars, 15m-D1): flat to negative everywhere; the only positives are 4h (+$20 with the ATR exits on 194 trades, +$1 as written) with t-statistics below 0.4. The 2015-2026 daily history is +$48 to +$59 on 80-89 trades (6 of 12 years). Oil's cost is tiny (4-point spread, no swap) so the result is the signal itself: no edge.

## 1. Setup

Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol OILCash: point 0.01, contract 100, quote currency USD, swap long/short 0.0/0.0 points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage 3 pts per side, swap), C stress (1.5x spread, 10 pts slippage). Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.


## 2a. Every timeframe, ASIS

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 2201 | 39.99 | -171.71 | -554.45 | 0.74 | 27.40 | -0.08 | -0.15 | 198.91 | -2.58 |  | -101.22 | -52.86 | -17.63 | negative |
| 30m | 1271 | -15.74 | -151.74 | -369.04 | 0.72 | 27.30 | -0.12 | -0.15 | 158.84 | -2.13 |  | -94.97 | -32.50 | -24.27 | negative |
| 1h | 666 | -12.16 | -72.77 | -186.52 | 0.79 | 29.90 | -0.11 | -0.10 | 100.96 | -0.75 |  | -52.72 | -28.53 | 8.48 | negative |
| 2h | 366 | -23.64 | -57.92 | -119.29 | 0.79 | 27.30 | -0.16 | -0.07 | 88.44 | -0.66 |  | -54.10 | -26.60 | 22.78 | negative |
| 4h | 166 | 19.67 | 0.98 | -28.39 | 1.01 | 38.00 | 0.01 | 0.03 | 22.03 | 0.02 | 4,000.80 | 0.04 | -7.47 | 8.41 | unstable |
| D1 | 29 | -4.57 | -10.54 | -15.03 | 0.76 | 31.00 | -0.36 | -0.10 | 35.99 | -0.17 |  | -22.46 | -12.45 | 24.37 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 15m | 0 / 0 | -5 / 296 | -59 / 522 | -62 / 511 | -45 / 468 | -1 / 404 |
| 30m | 0 / 0 | -28 / 152 | -26 / 299 | -59 / 311 | -31 / 280 | -7 / 229 |
| 1h | 0 / 0 | -32 / 82 | 6 / 150 | -48 / 169 | -16 / 149 | 18 / 116 |
| 2h | 0 / 0 | -41 / 48 | 1 / 85 | -29 / 82 | -16 / 84 | 27 / 67 |
| 4h | 0 / 0 | -6 / 15 | 7 / 33 | -10 / 45 | -4 / 42 | 13 / 31 |
| D1 | 0 / 0 | 0 / 0 | -6 / 7 | -26 / 12 | -3 / 6 | 25 / 4 |

## 2b. Every timeframe, FINAL_H4

| TF | trades | gross A $ | net B $ | net C $ | PF B | win % | exp $ | exp R | max DD $ | Sharpe(m) | top-5 % | TRAIN | VAL | OOS | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | 3389 | 73.94 | -258.84 | -753.66 | 0.70 | 38.90 | -0.08 | -0.21 | 292.39 | -2.84 |  | -162.10 | -84.54 | -12.20 | negative |
| 30m | 1834 | 13.32 | -181.19 | -476.67 | 0.72 | 40.90 | -0.10 | -0.14 | 187.56 | -2.90 |  | -104.20 | -36.33 | -40.66 | negative |
| 1h | 832 | 32.99 | -61.06 | -204.35 | 0.85 | 38.80 | -0.07 | -0.08 | 92.01 | -0.61 |  | -53.35 | -13.58 | 5.87 | negative |
| 2h | 468 | -20.48 | -54.07 | -114.74 | 0.83 | 39.50 | -0.12 | -0.09 | 102.31 | -0.51 |  | -59.67 | -31.58 | 37.18 | negative |
| 4h | 194 | 39.82 | 20.31 | -35.87 | 1.11 | 49.00 | 0.10 | 0.08 | 44.74 | 0.36 | 286.10 | 17.29 | -7.27 | 10.29 | unstable |
| D1 | 28 | -4.78 | -5.14 | -11.19 | 0.89 | 42.90 | -0.18 | -0.08 | 26.72 | -0.09 |  | -15.39 | -10.21 | 20.46 | negative |

Year by year (net B $ / trades):

| TF | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 15m | 0 / 0 | -21 / 424 | -81 / 803 | -100 / 825 | -70 / 771 | 14 / 566 |
| 30m | 0 / 0 | -17 / 206 | -37 / 453 | -72 / 449 | -34 / 419 | -21 / 307 |
| 1h | 0 / 0 | -30 / 96 | 4 / 196 | -46 / 196 | -10 / 196 | 21 / 148 |
| 2h | 0 / 0 | -38 / 54 | -2 / 106 | -34 / 109 | -26 / 116 | 45 / 83 |
| 4h | 0 / 0 | 4 / 15 | 11 / 43 | -6 / 49 | -4 / 48 | 16 / 39 |
| D1 | 0 / 0 | 0 / 0 | -4 / 6 | -20 / 11 | -3 / 6 | 21 / 5 |

## 3. D1 on the long hourly path 2015-2026

| config | scenario | trades | net $ | PF | exp R | max DD $ | years > 0 | by year |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 80 | 54.95 | 1.57 | 0.08 | 35.41 | 6/12 | 2015: 6, 2016: -9, 2017: -0, 2018: 10, 2019: -13, 2020: 21, 2021: 14, 2022: 35, 2023: -9, 2024: -23, 2025: -3, 2026: 26 |
| ASIS | B | 80 | 47.85 | 1.47 | 0.06 | 41.47 | 6/12 | 2015: 6, 2016: -9, 2017: -1, 2018: 12, 2019: -13, 2020: 21, 2021: 14, 2022: 35, 2023: -12, 2024: -26, 2025: -3, 2026: 25 |
| FINAL_H4 | A | 89 | 65.60 | 1.53 | 0.08 | 26.76 | 6/12 | 2015: 5, 2016: -8, 2017: -0, 2018: 11, 2019: -12, 2020: 6, 2021: 13, 2022: 52, 2023: -0, 2024: -21, 2025: -2, 2026: 22 |
| FINAL_H4 | B | 89 | 59.01 | 1.46 | 0.07 | 26.72 | 6/12 | 2015: 5, 2016: -9, 2017: -2, 2018: 11, 2019: -13, 2020: 6, 2021: 12, 2022: 52, 2023: -1, 2024: -20, 2025: -3, 2026: 21 |

## 4. Candidate timeframes: quality, conditions, robustness, variants


### 4h FINAL_H4 (verdict unstable, net $20.31, PF 1.113)

- Expectancy $0.1047 (0.0833 R), median R -0.0111, R p05/p25/p75/p95 -1.008/-0.517/0.312/1.965; 16.0% of trades >= +1R, 5.7% <= -1R.
- Concentration: top 10% of trades = 650.5% of net, best 5 trades = 286.1%; net without the best 5 = $-37.79.
- Longest losing streak 8; max drawdown $44.74 (4.5% of $1,000 per 0.01 lot), longest drawdown 521 days; recovery factor 0.45; swap paid $-0.00.
- Monthly Sharpe 0.33, Sortino 0.56, positive months 41.0%, CAGR on $1,000 = 0.4%; t-stat 0.4, 95% CI of expectancy [-0.4365, 0.6072] $.
- Long 92 / $9.99, short 102 / $10.32. Exits {'MA18_exit': 120, 'SL_breakeven': 34, 'SL_trailing': 30, 'SL_initial': 10}. Avg hold 3795 min, 3.19 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $45.21, p95 $64.15, P(lose half) 0.0%.

- trend: strong_bull $4/28; weak_bull $-6/21; sideways $36/63; weak_bear $-1/65; strong_bear $-14/17
- volatility: low $9/49; normal $37/104; high $-27/36; extreme $1/5
- session of entry: Asia $-34/26; London $25/38; London/NY $19/70; NewYork $9/59; Sydney $1/1
- weekday: Mon $-1/31; Tue $51/32; Wed $-8/37; Thu $-17/38; Fri $-4/56
- direction: long $10/92; short $10/102
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-137/58; loss after progress $-43/41; small win $42/64; win >= 1R $159/31

- MA grid: 19/60 cells positive on TRAIN, 0 also on VAL and OOS. Exit grid: 57/64 TRAIN-positive, 47 also OOS.
- Walk-forward: re-optimised pairs $-17.62 vs fixed 18/200 $8.46 on the test months; chosen beat fixed in 3/6 folds.

- Variants helpful in all splits: V09 ATR(22)/SMA100(ATR) <= 1.5 (net $26.41, OOS $12.64). Harmful: V01, V02, V05, V10, V12, V14, V17, V19. HTF gates helpful: none.


### 4h ASIS (verdict unstable, net $0.98, PF 1.007)

- Expectancy $0.0059 (0.032 R), median R -0.1732, R p05/p25/p75/p95 -0.898/-0.493/0.297/1.782; 9.0% of trades >= +1R, 4.8% <= -1R.
- Concentration: top 10% of trades = 9193.5% of net, best 5 trades = 4000.8%; net without the best 5 = $-38.23.
- Longest losing streak 9; max drawdown $22.03 (2.2% of $1,000 per 0.01 lot), longest drawdown 717 days; recovery factor 0.04; swap paid $-0.00.
- Monthly Sharpe 0.02, Sortino 0.02, positive months 39.3%, CAGR on $1,000 = 0.0%; t-stat 0.03, 95% CI of expectancy [-0.3479, 0.376] $.
- Long 76 / $12.38, short 90 / $-11.4. Exits {'MA18_exit': 149, 'SL_swing': 8, 'SL_initial': 7, 'SL_breakeven': 2}. Avg hold 4736 min, 2.73 trades/month.
- Monte Carlo (3,000 shuffles on $1,000): median DD $30.34, p95 $46.43, P(lose half) 0.0%.

- trend: strong_bull $-2/19; weak_bull $-1/18; sideways $16/61; weak_bear $1/53; strong_bear $-13/15
- volatility: low $9/42; normal $-2/87; high $-3/31; extreme $-4/6
- session of entry: Asia $3/22; London $-1/33; London/NY $-5/59; NewYork $4/52
- weekday: Mon $27/29; Tue $18/30; Wed $-2/29; Thu $-8/31; Fri $-34/47
- direction: long $12/76; short $-11/90
- trade outcome type: failed breakout (loss, MFE < 0.3R) $-100/54; loss after progress $-39/49; small win $73/48; win >= 1R $67/15

- MA grid: 5/60 cells positive on TRAIN, 0 also on VAL and OOS. Exit grid: 24/45 TRAIN-positive, 24 also OOS.
- Walk-forward: re-optimised pairs $-17.17 vs fixed 18/200 $4.66 on the test months; chosen beat fixed in 1/6 folds.

- Variants helpful in all splits: none. Harmful: V01, V02, V04, V05, V06, V12, V13, V15, V16, V17, V18. HTF gates helpful: M09 HTF D1 (net $4.1, OOS $5.55).


## 5. Costs

| config | tf | TF | trades | gross A $ | exec cost $ | swap $ | net B $ | net C $ | cost/trade B $ | break-even cost/trade $ | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 2201 | 39.990 | 211.700 | -0.000 | -171.710 | -554.450 | 0.096 | 0.019 | 30.200 | 1.080 | 0.740 | 0.424 |
| ASIS | 30m | 30m | 1271 | -15.740 | 136.000 | -0.000 | -151.740 | -369.040 | 0.107 | -0.013 | 25.700 | 0.964 | 0.721 | 0.484 |
| ASIS | 1h | 1h | 666 | -12.160 | 60.610 | -0.000 | -72.770 | -186.520 | 0.091 | -0.019 | 17.900 | 0.960 | 0.793 | 0.574 |
| ASIS | 2h | 2h | 366 | -23.640 | 34.280 | -0.000 | -57.920 | -119.290 | 0.094 | -0.066 | 13.500 | 0.906 | 0.791 | 0.630 |
| ASIS | 4h | 4h | 166 | 19.670 | 18.690 | -0.000 | 0.980 | -28.390 | 0.113 | 0.121 | 11.800 | 1.158 | 1.007 | 0.822 |
| ASIS | D1 | D1 | 29 | -4.570 | 5.970 | -0.000 | -10.540 | -15.030 | 0.206 | -0.163 | 15.500 | 0.879 | 0.755 | 0.679 |
| FINAL_H4 | 15m | 15m | 3389 | 73.940 | 332.780 | -0.000 | -258.840 | -753.660 | 0.098 | 0.021 | 35.300 | 1.110 | 0.703 | 0.381 |
| FINAL_H4 | 30m | 30m | 1834 | 13.320 | 194.510 | -0.000 | -181.190 | -476.670 | 0.106 | 0.007 | 29.700 | 1.026 | 0.718 | 0.435 |
| FINAL_H4 | 1h | 1h | 832 | 32.990 | 94.050 | -0.000 | -61.060 | -204.350 | 0.113 | 0.039 | 21.300 | 1.095 | 0.851 | 0.600 |
| FINAL_H4 | 2h | 2h | 468 | -20.480 | 33.590 | -0.000 | -54.070 | -114.740 | 0.072 | -0.043 | 11.500 | 0.928 | 0.827 | 0.675 |
| FINAL_H4 | 4h | 4h | 194 | 39.820 | 19.510 | -0.000 | 20.310 | -35.870 | 0.101 | 0.204 | 8.900 | 1.235 | 1.113 | 0.816 |
| FINAL_H4 | D1 | D1 | 28 | -4.780 | 0.360 | -0.000 | -5.140 | -11.190 | 0.013 | -0.165 | 0.900 | 0.895 | 0.887 | 0.777 |

Slippage sweep (USD per 0.01 lot):

| config | TF | slip 0 pts | slip 3 pts | slip 6 pts | slip 12 pts | slip 24 pts |
|---|---|---|---|---|---|---|
| ASIS | 15m | -39.65 | -171.71 | -303.77 | -567.89 | -1,096.13 |
| ASIS | 4h | 10.88 | 0.98 | -8.92 | -33.36 | -73.08 |
| FINAL_H4 | 15m | -46.41 | -258.84 | -449.15 | -832.22 | -1,572.97 |
| FINAL_H4 | 30m | -53.52 | -181.19 | -289.39 | -508.95 | -902.28 |
| FINAL_H4 | 1h | 0.52 | -61.06 | -116.87 | -214.32 | -400.98 |
| FINAL_H4 | 4h | 30.95 | 20.31 | 8.75 | -14.93 | -61.59 |

## 6. Answers

Works: no. Stable timeframe: none. Costs: under 10% of gross on 4h; the signal has no expectancy. Verdict: negative.

## 7. Files
- backtests/lightcmdusd/: every trade list
- research/*.md, research/experiment_log.csv
