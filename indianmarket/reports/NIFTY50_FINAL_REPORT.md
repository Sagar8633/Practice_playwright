# NIFTY 50: final report (SimpleSMA18Bot logic, 3 Jan 2022 to 26 Sep 2026)

Verdict: **no statistically defensible positive expectancy on NIFTY 50.** The strategy loses after costs on every timeframe from 1 minute to 10 minutes and on D1 (both 2022-2026 and 2010-2026). From 15 minutes to 4 hours it is positive after realistic costs in both configurations (net +1,600 to +5,100 points per unit over 4.7 years, profit factor 1.05 to 1.68), and six of those runs pass the pre-set robust rule, but none of them is statistically distinguishable from zero: the t-statistic of the mean trade is 0.9 to 1.3 and every 95% confidence interval of the expectancy includes zero. The profit is carried by a handful of trades (the best five trades are 70% to 165% of the net result; without them four of the six 'robust' runs are flat or negative), by bear and sideways regimes (strong-bull sessions lose on every candidate timeframe), and by Fridays (on the 30m ATR configuration Fridays contribute +7,035 of the +5,118 net points; the other four weekdays together lose). The best-behaved configuration is the 30-minute ATR-scaled exit stack (FINAL_H4): positive in TRAIN, VAL and OOS, in four of five years, in 52 of 60 moving-average cells and in all 64 exit cells, but with a 65% drawdown of the Rs 2.5 lakh capital per lot and an 18% Monte Carlo chance of losing half the capital. It is a candidate for a forward test, not for trading.

## 1. Setup

Data: Upstox 1-minute index candles (IST, 09:15-15:29, 1,174 sessions) cross-checked against the official NSE daily series; daily official history 2007-2026 for the long D1 test. See data/DATA_AUDIT.md. Costs: scenario A gross, B realistic (spread 0.1 pts, slippage 0.5 pts per side, all statutory charges and Rs 20 brokerage per order), C stress. Money unit: index points per unit; one futures lot = 75 units; capital per lot for percentages Rs 250,000. Configurations: AS-IS (v1.00 rules, 1 point = 1 tick) and FINAL_H4 (the ATR-scaled exit stack selected in the gold study). The volume filter cannot be evaluated on an index and is off in both.

Splits fixed before the runs: TRAIN 2022-01-03..2024-08-31, VAL 2024-09-01..2025-08-31, OOS 2025-09-01..2026-09-26. Verdict rule: robust = positive expectancy and PF > 1 after B costs in all three splits with >= 30 trades each.


## 2a. Every timeframe, ASIS (scenario B unless stated)

| TF | trades | gross A | net B | net C | PF B | win % | exp pts | exp R | median R | max DD | Sharpe(m) | top-5 share % | TRAIN | VAL | OOS | OOS PF | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 16240 | 21,442.50 | -98,826.20 | -159,272.70 | 0.50 | 21.50 | -6.08 | -0.42 | -0.63 | 98,872.90 | -9.33 |  | -49,425.80 | -23,396.30 | -26,004.10 | 0.48 | negative |
| 3m | 5788 | 15,440.00 | -27,186.00 | -49,175.90 | 0.72 | 24.60 | -4.70 | -0.19 | -0.41 | 27,796.50 | -3.27 |  | -12,104.20 | -6,116.00 | -8,965.90 | 0.65 | negative |
| 5m | 3686 | 10,070.30 | -17,493.30 | -30,816.00 | 0.76 | 23.50 | -4.75 | -0.14 | -0.32 | 18,846.60 | -2.22 |  | -4,277.30 | -5,732.50 | -7,483.50 | 0.61 | negative |
| 10m | 1979 | 10,517.80 | -4,029.30 | -11,424.60 | 0.91 | 22.20 | -2.04 | -0.09 | -0.14 | 6,952.00 | -0.63 |  | -1,024.80 | -573.70 | -2,430.90 | 0.81 | negative |
| 15m | 1330 | 11,146.50 | 1,642.60 | -3,601.30 | 1.05 | 21.20 | 1.24 | 0.00 | -0.08 | 2,550.40 | 0.26 | 206.70 | 520.20 | -428.10 | 1,550.40 | 1.23 | unstable |
| 30m | 739 | 8,340.60 | 2,628.00 | -72.80 | 1.11 | 18.10 | 3.56 | 0.04 | -0.04 | 2,592.40 | 0.30 | 163.40 | 2,593.50 | 484.40 | -449.90 | 0.92 | unstable |
| 1h | 418 | 6,578.50 | 3,332.10 | 1,793.60 | 1.23 | 16.00 | 7.97 | 0.09 | -0.03 | 1,467.80 | 0.46 | 120.20 | 2,087.40 | 1,382.60 | -137.90 | 0.96 | unstable |
| 2h | 262 | 4,654.50 | 3,092.00 | 1,746.80 | 1.33 | 17.20 | 11.80 | 0.10 | -0.02 | 1,710.10 | 0.43 | 146.70 | 2,521.00 | 524.70 | 46.30 | 1.01 | robust |
| 4h | 139 | 4,667.40 | 4,034.70 | 4,160.30 | 1.68 | 16.50 | 29.03 | 0.13 | -0.01 | 1,547.20 | 0.57 | 123.00 | 3,310.00 | 19.90 | 704.80 | 1.49 | robust |
| D1 | 80 | -2,175.20 | -2,756.70 | -3,002.20 | 0.55 | 7.50 | -34.46 | -0.06 | -0.01 | 5,091.50 | -0.43 |  | -570.80 | -1,057.70 | -1,128.20 | 0.34 | negative |

## 2b. Every timeframe, FINAL_H4 (scenario B unless stated)

| TF | trades | gross A | net B | net C | PF B | win % | exp pts | exp R | median R | max DD | Sharpe(m) | top-5 share % | TRAIN | VAL | OOS | OOS PF | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 18431 | 31,416.70 | -104,955.60 | -172,302.30 | 0.53 | 21.00 | -5.70 | -0.38 | -0.58 | 104,996.00 | -8.99 |  | -53,762.30 | -23,580.60 | -27,612.60 | 0.51 | negative |
| 3m | 6118 | 20,953.20 | -24,564.60 | -47,374.90 | 0.77 | 25.90 | -4.01 | -0.17 | -0.41 | 25,058.30 | -2.74 |  | -12,595.60 | -4,326.60 | -7,642.40 | 0.72 | negative |
| 5m | 3669 | 13,810.50 | -13,349.80 | -26,665.10 | 0.84 | 27.30 | -3.64 | -0.11 | -0.38 | 15,698.70 | -1.57 |  | -3,109.90 | -4,144.10 | -6,095.80 | 0.70 | negative |
| 10m | 1822 | 12,792.70 | -215.10 | -7,107.90 | 1.00 | 28.60 | -0.12 | -0.04 | -0.27 | 3,889.60 | -0.03 |  | 2,503.50 | -1,299.00 | -1,419.60 | 0.90 | negative |
| 15m | 1158 | 13,302.50 | 4,285.10 | -88.60 | 1.10 | 30.20 | 3.70 | 0.03 | -0.22 | 2,790.70 | 0.48 | 92.80 | 399.50 | 1,788.00 | 2,097.50 | 1.21 | robust |
| 30m | 599 | 9,386.20 | 5,118.00 | 2,690.50 | 1.17 | 31.90 | 8.54 | 0.04 | -0.15 | 2,158.20 | 0.49 | 70.10 | 2,085.40 | 1,269.20 | 1,763.40 | 1.24 | robust |
| 1h | 315 | 4,367.90 | 1,930.20 | 458.90 | 1.09 | 31.40 | 6.13 | 0.06 | -0.20 | 1,920.50 | 0.26 | 164.80 | 1,178.10 | 583.20 | 168.90 | 1.03 | robust |
| 2h | 174 | 4,899.00 | 3,626.90 | 3,026.70 | 1.23 | 36.80 | 20.84 | 0.12 | -0.04 | 2,188.90 | 0.44 | 92.90 | 3,003.00 | 361.10 | 262.80 | 1.06 | robust |
| 4h | 79 | 4,598.50 | 3,989.10 | 3,712.20 | 1.36 | 40.50 | 50.49 | 0.14 | -0.02 | 2,734.40 | 0.42 | 159.00 | 3,869.80 | 788.30 | -669.00 | 0.83 | unstable |
| D1 | 38 | -3,426.00 | -3,717.80 | -3,854.90 | 0.62 | 28.90 | -97.84 | -0.15 | -0.22 | 6,695.90 | -0.45 |  | -311.60 | -1,621.10 | -1,785.10 | 0.58 | negative |

## 3. Year by year (scenario B, candidate timeframes)


**ASIS**

| TF | year | trades | win % | PF | exp pts | exp R | net pts | net R | max DD pts |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 2022 | 269 | 23.80 | 1.26 | 6.37 | 0.08 | 1,714.40 | 21.25 | 900.00 |
| 15m | 2023 | 269 | 21.60 | 1.02 | 0.48 | 0.06 | 128.70 | 17.09 | 871.30 |
| 15m | 2024 | 302 | 20.20 | 0.85 | -4.29 | -0.12 | -1,294.00 | -35.33 | 1,988.70 |
| 15m | 2025 | 290 | 19.30 | 0.95 | -1.40 | 0.00 | -404.70 | 0.19 | 1,451.20 |
| 15m | 2026 | 200 | 21.50 | 1.32 | 7.49 | 0.01 | 1,498.10 | 2.91 | 1,662.90 |
| 30m | 2022 | 152 | 23.70 | 1.43 | 11.60 | 0.10 | 1,763.00 | 15.39 | 952.70 |
| 30m | 2023 | 143 | 19.60 | 1.56 | 12.39 | 0.18 | 1,771.80 | 26.21 | 492.20 |
| 30m | 2024 | 164 | 17.70 | 0.80 | -7.17 | -0.03 | -1,175.00 | -4.77 | 1,985.60 |
| 30m | 2025 | 152 | 16.40 | 1.14 | 4.69 | -0.00 | 712.40 | -0.23 | 1,357.40 |
| 30m | 2026 | 128 | 12.50 | 0.90 | -3.47 | -0.08 | -444.10 | -9.65 | 2,592.40 |
| 1h | 2022 | 77 | 13.00 | 1.04 | 1.80 | 0.06 | 138.90 | 4.30 | 1,132.70 |
| 1h | 2023 | 87 | 21.80 | 1.73 | 22.24 | 0.25 | 1,934.60 | 21.82 | 488.30 |
| 1h | 2024 | 98 | 15.30 | 1.02 | 0.58 | -0.01 | 57.20 | -1.08 | 961.50 |
| 1h | 2025 | 93 | 15.10 | 1.35 | 10.33 | 0.09 | 960.60 | 8.67 | 655.10 |
| 1h | 2026 | 63 | 14.30 | 1.10 | 3.82 | 0.04 | 240.70 | 2.42 | 1,467.80 |
| 2h | 2022 | 47 | 17.00 | 1.47 | 11.89 | 0.08 | 559.00 | 3.58 | 608.90 |
| 2h | 2023 | 51 | 21.60 | 1.71 | 28.22 | 0.20 | 1,439.30 | 10.03 | 544.10 |
| 2h | 2024 | 61 | 18.00 | 1.65 | 18.55 | 0.07 | 1,131.70 | 4.34 | 1,022.10 |
| 2h | 2025 | 60 | 16.70 | 1.05 | 1.56 | 0.00 | 93.50 | 0.07 | 727.80 |
| 2h | 2026 | 43 | 11.60 | 0.95 | -3.06 | 0.20 | -131.40 | 8.39 | 1,658.50 |
| 4h | 2022 | 12 | 33.30 | 2.42 | 87.50 | 0.20 | 1,050.00 | 2.42 | 719.20 |
| 4h | 2023 | 31 | 25.80 | 1.81 | 39.74 | 0.38 | 1,231.90 | 11.74 | 742.70 |
| 4h | 2024 | 40 | 15.00 | 2.02 | 28.88 | 0.03 | 1,155.20 | 1.30 | 580.10 |
| 4h | 2025 | 36 | 8.30 | 0.52 | -26.59 | -0.06 | -957.40 | -2.01 | 1,493.70 |
| 4h | 2026 | 20 | 10.00 | 3.70 | 77.75 | 0.21 | 1,555.00 | 4.24 | 522.50 |

**FINAL_H4**

| TF | year | trades | win % | PF | exp pts | exp R | net pts | net R | max DD pts |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 2022 | 234 | 31.60 | 1.22 | 8.47 | 0.16 | 1,981.90 | 37.60 | 882.40 |
| 15m | 2023 | 259 | 28.60 | 1.06 | 1.55 | -0.00 | 400.90 | -0.81 | 815.50 |
| 15m | 2024 | 252 | 29.00 | 0.86 | -6.04 | -0.10 | -1,523.30 | -25.81 | 2,728.90 |
| 15m | 2025 | 247 | 31.20 | 1.15 | 5.24 | 0.04 | 1,294.60 | 9.37 | 1,290.70 |
| 15m | 2026 | 166 | 31.30 | 1.30 | 12.84 | 0.10 | 2,130.90 | 17.20 | 1,687.20 |
| 30m | 2022 | 125 | 32.80 | 1.21 | 11.40 | 0.20 | 1,425.60 | 24.43 | 1,090.90 |
| 30m | 2023 | 130 | 33.80 | 1.46 | 13.46 | 0.11 | 1,750.10 | 14.88 | 738.00 |
| 30m | 2024 | 127 | 30.70 | 0.94 | -3.61 | -0.06 | -459.00 | -7.79 | 1,895.40 |
| 30m | 2025 | 120 | 30.00 | 1.10 | 5.24 | -0.09 | 628.80 | -10.29 | 2,132.20 |
| 30m | 2026 | 97 | 32.00 | 1.32 | 18.27 | 0.02 | 1,772.50 | 1.94 | 2,114.90 |
| 1h | 2022 | 62 | 25.80 | 0.92 | -7.19 | -0.10 | -445.60 | -6.44 | 1,454.00 |
| 1h | 2023 | 69 | 36.20 | 1.82 | 37.47 | 0.20 | 2,585.20 | 14.09 | 443.40 |
| 1h | 2024 | 73 | 28.80 | 0.86 | -10.42 | 0.02 | -761.00 | 1.36 | 1,717.20 |
| 1h | 2025 | 64 | 34.40 | 1.03 | 1.86 | 0.04 | 118.80 | 2.75 | 824.30 |
| 1h | 2026 | 47 | 31.90 | 1.12 | 9.21 | 0.15 | 432.80 | 6.86 | 1,920.50 |
| 2h | 2022 | 27 | 48.10 | 1.49 | 44.95 | 0.23 | 1,213.60 | 6.14 | 836.10 |
| 2h | 2023 | 45 | 33.30 | 1.27 | 20.26 | 0.05 | 911.80 | 2.11 | 986.80 |
| 2h | 2024 | 36 | 41.70 | 1.59 | 47.08 | 0.20 | 1,694.90 | 7.23 | 790.90 |
| 2h | 2025 | 38 | 31.60 | 0.98 | -1.73 | 0.05 | -65.80 | 1.78 | 1,178.70 |
| 2h | 2026 | 28 | 32.10 | 0.97 | -4.55 | 0.15 | -127.50 | 4.10 | 1,970.80 |
| 4h | 2022 | 11 | 36.40 | 1.87 | 92.61 | 0.18 | 1,018.70 | 1.96 | 467.10 |
| 4h | 2023 | 19 | 47.40 | 2.11 | 88.99 | 0.14 | 1,690.80 | 2.59 | 500.40 |
| 4h | 2024 | 17 | 41.20 | 1.41 | 56.69 | -0.05 | 963.70 | -0.80 | 802.10 |
| 4h | 2025 | 18 | 38.90 | 1.40 | 58.04 | 0.43 | 1,044.70 | 7.75 | 1,157.80 |
| 4h | 2026 | 14 | 35.70 | 0.79 | -52.06 | -0.02 | -728.80 | -0.35 | 1,905.60 |

## 4. D1 on the official daily history 2010-2026

| config | scenario | trades | net pts | PF | exp R | max DD pts | years > 0 | by year (net) |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 253 | -442.50 | 0.97 | -0.02 | 4,487.00 | 9/17 | 2010: 587, 2011: 66, 2012: 48, 2013: -588, 2014: 1141, 2015: -483, 2016: -255, 2017: 661, 2018: 744, 2019: 320, 2020: -752, 2021: 1312, 2022: -1194, 2023: -160, 2024: 146, 2025: -1997, 2026: -39 |
| ASIS | B | 253 | -1,772.50 | 0.88 | -0.03 | 4,857.40 | 7/17 | 2010: 554, 2011: 29, 2012: -111, 2013: -636, 2014: 1106, 2015: -550, 2016: -308, 2017: 586, 2018: 706, 2019: 242, 2020: -834, 2021: 1243, 2022: -1282, 2023: -242, 2024: -26, 2025: -2133, 2026: -117 |
| FINAL_H4 | A | 169 | -3,185.30 | 0.87 | -0.03 | 7,294.80 | 9/17 | 2010: 809, 2011: -320, 2012: 65, 2013: 6, 2014: 560, 2015: -1077, 2016: -367, 2017: 731, 2018: 668, 2019: -643, 2020: -809, 2021: 1672, 2022: 90, 2023: 1924, 2024: -3066, 2025: -1649, 2026: -1780 |
| FINAL_H4 | B | 169 | -4,014.50 | 0.83 | -0.04 | 7,547.30 | 8/17 | 2010: 781, 2011: -347, 2012: 38, 2013: -19, 2014: 518, 2015: -1124, 2016: -411, 2017: 682, 2018: 627, 2019: -690, 2020: -863, 2021: 1625, 2022: 53, 2023: 1877, 2024: -3173, 2025: -1738, 2026: -1852 |

## 5. Trade quality, market conditions, robustness and variants of the candidate timeframes


### 15m ASIS (verdict unstable)

**15m ASIS: trade quality** (1330 trades)

- Expectancy 1.235 pts (0.0046 R), median R -0.0833, R percentiles p05 -1.236 / p25 -0.532 / p75 -0.024 / p95 1.855; 9.3% of trades >= +1R, 10.3% <= -1R.
- Concentration: the top 10% of trades contribute 1772.5% of the net result, the best 5 trades 206.7%; net without the best 5 trades = -1752.2 pts.
- Longest losing streak 19, max drawdown 2550.4 pts = Rs 191,279 per lot (76.5% of Rs 250,000), longest drawdown 1344 days; recovery factor 0.64.
- Per lot of 75: net Rs 123,191 over 56.74 months, CAGR on Rs 250,000 = 8.8%, monthly Sharpe 0.26, Sortino 0.4, positive months 52.6%; t-stat of the mean trade 0.47, 95% CI of the expectancy [-3.736, 6.401] pts.
- Long 696 trades / 1861.9 pts, short 634 / -219.3 pts. Exits: {'SL_breakeven': 562, 'MA18_exit': 486, 'SL_swing': 179, 'SL_initial': 103}. Average hold 625 min, 23.44 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 234,396, 95th pct Rs 368,737, probability of losing half the capital 38.4%, probability of ending below the start 0.0%.

**15m ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull -1,670/248/0.73; weak_bull -1,779/436/0.83; sideways 795/262/1.12; weak_bear 2,931/304/1.37; strong_bear 1,365/80/1.77
- volatility: low 1,521/406/1.18; normal -1,801/630/0.89; high 257/227/1.04; extreme 1,665/67/2.25
- session phase of entry: opening 622/114/1.26; morning 584/408/1.06; midday -1,280/369/0.84; afternoon -251/322/0.97; closing 1,968/117/1.53
- opening gap of the entry day: large down 1,024/73/1.51; large up 1,901/66/2.94; medium down -1,097/186/0.79; medium up -651/323/0.93; small down 1,770/276/1.27; small up -1,304/406/0.86
- trade outcome type: failed breakout (loss, MFE < 0.3R) -25,359/587/0.00; loss after progress -7,685/461/0.00; small win 8,658/158; win >= 1R 26,028/124

**15m ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 45 positive on TRAIN with >= 30 trades, 6 of them also positive on VAL and OOS. 18/200 itself: TRAIN 0.71 / VAL -1.422 / OOS 5.238 pts per trade.
- Exit grid (45 cells): 29 positive on TRAIN, 29 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 25/300, 30/300, 30/50, 25/100, 16/50; test-month net -4,777 pts versus -215 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 1/5 folds.

**15m ASIS: variants** (20 filters, 6 HTF gates)

- Helpful in all three splits: none.
- Harmful (worse expectancy in 2+ splits): V01, V02, V03, V04, V06, V07, V08, V09, V12, V13, V16, V17, V18, V19, V20.
- Variants that pass the robust rule: V02 (net 1,462, OOS 906).
- HTF gates helpful in all splits: none.


### 30m ASIS (verdict unstable)

**30m ASIS: trade quality** (739 trades)

- Expectancy 3.556 pts (0.0365 R), median R -0.045, R percentiles p05 -1.128 / p25 -0.35 / p75 -0.02 / p95 1.937; 8.1% of trades >= +1R, 8.8% <= -1R.
- Concentration: the top 10% of trades contribute 861.8% of the net result, the best 5 trades 163.4%; net without the best 5 trades = -1666.4 pts.
- Longest losing streak 28, max drawdown 2592.4 pts = Rs 194,432 per lot (77.8% of Rs 250,000), longest drawdown 321 days; recovery factor 1.01.
- Per lot of 75: net Rs 197,103 over 56.74 months, CAGR on Rs 250,000 = 13.1%, monthly Sharpe 0.3, Sortino 0.47, positive months 50.9%; t-stat of the mean trade 0.72, 95% CI of the expectancy [-5.81, 14.32] pts.
- Long 389 trades / 3236.4 pts, short 350 / -608.4 pts. Exits: {'SL_breakeven': 412, 'MA18_exit': 179, 'SL_swing': 93, 'SL_initial': 55}. Average hold 1210 min, 13.02 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 216,293, 95th pct Rs 337,447, probability of losing half the capital 29.1%, probability of ending below the start 0.0%.

**30m ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull -1,501/122/0.66; weak_bull 11/251/1.00; sideways 1,029/146/1.23; weak_bear 3,641/177/1.76; strong_bear -553/43/0.73
- volatility: low 2,407/224/1.42; normal -307/338/0.97; high 578/137/1.14; extreme -49/40/0.97
- session phase of entry: opening -1,930/70/0.35; morning 617/225/1.10; midday 2,829/208/1.68; afternoon -797/157/0.88; closing 1,910/79/1.65
- opening gap of the entry day: large down -1,015/44/0.63; large up 839/32/2.64; medium down 838/88/1.33; medium up -890/174/0.84; small down 1,940/166/1.36; small up 916/235/1.15
- trade outcome type: failed breakout (loss, MFE < 0.3R) -17,876/374/0.00; loss after progress -5,057/231/0.00; small win 5,593/74; win >= 1R 19,968/60

**30m ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 60 positive on TRAIN with >= 30 trades, 7 of them also positive on VAL and OOS. 18/200 itself: TRAIN 6.516 / VAL 2.9 / OOS -2.585 pts per trade.
- Exit grid (45 cells): 44 positive on TRAIN, 27 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 30/300, 30/300, 18/300, 12/50, 25/100; test-month net -1,206 pts versus -909 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 1/5 folds.

**30m ASIS: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V01 ADX(14) >= 25 (EA filter) (net 3,220, OOS 591); V04 entries only 09:45-13:29 (morning + midday) (net 4,414, OOS 572); V07 skip sessions with |gap| > 0.5% (net 4,535, OOS 338); V08 only sessions with |gap| <= 0.25% (net 3,385, OOS 578); V12 no entry when |close - MA18| > 2 ATR (net 2,806, OOS -122).
- Harmful (worse expectancy in 2+ splits): V05, V06, V09, V11, V13, V16, V17, V18.
- Variants that pass the robust rule: V01 (net 3,220, OOS 591); V02 (net 3,249, OOS 317); V04 (net 4,414, OOS 572); V07 (net 4,535, OOS 338); V08 (net 3,385, OOS 578); V20 (net 1,863, OOS 248).
- HTF gates helpful in all splits: none.


### 1h ASIS (verdict unstable)

**1h ASIS: trade quality** (418 trades)

- Expectancy 7.972 pts (0.0864 R), median R -0.0315, R percentiles p05 -1.057 / p25 -0.113 / p75 -0.015 / p95 2.007; 8.1% of trades >= +1R, 6.7% <= -1R.
- Concentration: the top 10% of trades contribute 477.7% of the net result, the best 5 trades 120.2%; net without the best 5 trades = -672.4 pts.
- Longest losing streak 29, max drawdown 1467.8 pts = Rs 110,088 per lot (44.0% of Rs 250,000), longest drawdown 258 days; recovery factor 2.27.
- Per lot of 75: net Rs 249,909 over 56.74 months, CAGR on Rs 250,000 = 15.8%, monthly Sharpe 0.46, Sortino 0.9, positive months 47.4%; t-stat of the mean trade 1.05, 95% CI of the expectancy [-6.909, 23.601] pts.
- Long 229 trades / 4405.9 pts, short 189 / -1073.8 pts. Exits: {'SL_breakeven': 265, 'MA18_exit': 88, 'SL_swing': 42, 'SL_initial': 23}. Average hold 1982 min, 7.37 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 165,565, 95th pct Rs 257,632, probability of losing half the capital 14.3%, probability of ending below the start 0.0%.

**1h ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull 420/70/1.17; weak_bull 790/150/1.16; sideways 1,626/78/1.75; weak_bear 865/103/1.23; strong_bear -369/17/0.60
- volatility: low 2,886/135/1.72; normal 296/191/1.05; high -619/71/0.78; extreme 769/21/1.85
- session phase of entry: opening 846/74/1.38; morning 1,491/98/1.45; midday 1,903/126/1.52; afternoon -1,623/81/0.49; closing 716/39/1.37
- opening gap of the entry day: large down -1,364/31/0.22; large up 80/19/1.22; medium down -1,380/34/0.14; medium up 2,036/111/1.50; small down 3,526/100/2.24; small up 433/123/1.12
- trade outcome type: failed breakout (loss, MFE < 0.3R) -12,293/232/0.00; loss after progress -1,994/119/0.00; small win 3,471/33; win >= 1R 14,148/34

**1h ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 59 positive on TRAIN with >= 30 trades, 31 of them also positive on VAL and OOS. 18/200 itself: TRAIN 9.196 / VAL 14.402 / OOS -1.451 pts per trade.
- Exit grid (45 cells): 45 positive on TRAIN, 33 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 18/300, 12/150, 25/300, 18/300, 12/250; test-month net 1,056 pts versus 1,304 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 3/5 folds.

**1h ASIS: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V04 entries only 09:45-13:29 (morning + midday) (net 4,563, OOS 537); V08 only sessions with |gap| <= 0.25% (net 5,120, OOS 1,353).
- Harmful (worse expectancy in 2+ splits): V09, V10, V11, V14, V16, V17, V18.
- Variants that pass the robust rule: V04 (net 4,563, OOS 537); V07 (net 5,334, OOS 106); V08 (net 5,120, OOS 1,353); V12 (net 4,429, OOS 184); V20 (net 2,945, OOS 176).
- HTF gates helpful in all splits: none.


### 2h ASIS (verdict robust)

**2h ASIS: trade quality** (262 trades)

- Expectancy 11.802 pts (0.1008 R), median R -0.0211, R percentiles p05 -0.875 / p25 -0.037 / p75 -0.011 / p95 1.388; 6.1% of trades >= +1R, 4.2% <= -1R.
- Concentration: the top 10% of trades contribute 356.8% of the net result, the best 5 trades 146.7%; net without the best 5 trades = -1444.6 pts.
- Longest losing streak 17, max drawdown 1710.1 pts = Rs 128,261 per lot (51.3% of Rs 250,000), longest drawdown 346 days; recovery factor 1.81.
- Per lot of 75: net Rs 231,902 over 56.74 months, CAGR on Rs 250,000 = 14.9%, monthly Sharpe 0.43, Sortino 0.7, positive months 47.4%; t-stat of the mean trade 0.91, 95% CI of the expectancy [-12.764, 38.477] pts.
- Long 164 trades / 2911.8 pts, short 98 / 180.2 pts. Exits: {'SL_breakeven': 182, 'MA18_exit': 35, 'SL_swing': 33, 'SL_initial': 11, 'end_of_test': 1}. Average hold 2734 min, 4.62 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 178,595, 95th pct Rs 261,189, probability of losing half the capital 18.6%, probability of ending below the start 0.0%.

**2h ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull 15/43/1.01; weak_bull 915/96/1.31; sideways 1,536/63/2.03; weak_bear 994/50/1.33; strong_bear -369/10/0.00
- volatility: low 2,354/93/2.01; normal -2,325/124/0.62; high 2,062/39/3.59; extreme 1,000/6/50.97
- session phase of entry: opening 737/84/1.21; morning -336/35/0.83; midday 1,876/58/2.80; afternoon 861/54/1.57; closing -46/31/0.96
- opening gap of the entry day: large down -469/16/0.02; large up -212/19/0.54; medium down -340/21/0.34; medium up 2,987/75/2.32; small down 547/56/1.15; small up 578/75/1.29
- trade outcome type: failed breakout (loss, MFE < 0.3R) -8,333/161/0.00; loss after progress -946/56/0.00; small win 3,732/29; win >= 1R 8,639/16

**2h ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 59 positive on TRAIN with >= 30 trades, 15 of them also positive on VAL and OOS. 18/200 itself: TRAIN 17.629 / VAL 9.047 / OOS 0.76 pts per trade.
- Exit grid (45 cells): 45 positive on TRAIN, 24 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 30/250, 8/250, 8/250, 8/250, 16/200; test-month net 51 pts versus 686 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 3/5 folds.

**2h ASIS: variants** (20 filters, 0 HTF gates)

- Helpful in all three splits: V03 no entries in the opening phase (before 09:45) (net 3,133, OOS 60); V05 no entries in the closing phase (after 15:00) (net 4,792, OOS 1,105); V06 no entries in the first hour (before 10:15) (net 3,133, OOS 60); V12 no entry when |close - MA18| > 2 ATR (net 5,513, OOS 2,055).
- Harmful (worse expectancy in 2+ splits): V01, V02, V09, V13, V14, V16, V17, V18, V20.
- Variants that pass the robust rule: V03 (net 3,133, OOS 60); V05 (net 4,792, OOS 1,105); V06 (net 3,133, OOS 60); V07 (net 3,707, OOS 215); V10 (net 3,863, OOS 1,568); V11 (net 3,923, OOS 1,530); V12 (net 5,513, OOS 2,055); V18 (net 4,511, OOS 1,244).
- HTF gates helpful in all splits: none.


### 4h ASIS (verdict robust)

**4h ASIS: trade quality** (139 trades)

- Expectancy 29.026 pts (0.1273 R), median R -0.0146, R percentiles p05 -1.018 / p25 -0.027 / p75 -0.009 / p95 1.082; 5.8% of trades >= +1R, 5.8% <= -1R.
- Concentration: the top 10% of trades contribute 213.3% of the net result, the best 5 trades 123.0%; net without the best 5 trades = -928.6 pts.
- Longest losing streak 19, max drawdown 1547.2 pts = Rs 116,040 per lot (46.4% of Rs 250,000), longest drawdown 329 days; recovery factor 2.61.
- Per lot of 75: net Rs 302,599 over 56.74 months, CAGR on Rs 250,000 = 18.3%, monthly Sharpe 0.57, Sortino 1.22, positive months 31.6%; t-stat of the mean trade 1.3, 95% CI of the expectancy [-12.684, 73.631] pts.
- Long 100 trades / 1047.0 pts, short 39 / 2987.6 pts. Exits: {'SL_breakeven': 94, 'MA18_exit': 22, 'SL_swing': 17, 'SL_initial': 6}. Average hold 4605 min, 2.45 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 120,416, 95th pct Rs 195,769, probability of losing half the capital 5.5%, probability of ending below the start 0.0%.

**4h ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull -789/35/0.68; weak_bull 1,712/55/1.84; sideways 846/21/2.58; weak_bear 2,290/24/3.43; strong_bear -25/4/0.00
- volatility: low 841/51/1.46; normal -1,239/69/0.69; high 3,513/14/52.21; extreme 920/5/46.57
- session phase of entry: opening -310/53/0.89; morning -403/21/0.68; midday 1,356/22/3.73; afternoon 679/30/1.54; closing 2,712/13/12.83
- opening gap of the entry day: large down -296/6/0.00; large up 440/2/61.69; medium down 519/13/7.35; medium up 241/47/1.11; small down 2,684/21/5.20; small up 447/50/1.17
- trade outcome type: failed breakout (loss, MFE < 0.3R) -5,809/95/0.00; loss after progress -167/21/0.00; small win 3,894/15; win >= 1R 6,117/8

**4h ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 60 positive on TRAIN with >= 30 trades, 3 of them also positive on VAL and OOS. 18/200 itself: TRAIN 47.286 / VAL 0.567 / OOS 20.73 pts per trade.
- Exit grid (45 cells): 44 positive on TRAIN, 17 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 12/200, 12/150, 12/200, 30/200, 12/300; test-month net -1,059 pts versus 1,116 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 2/5 folds.

**4h ASIS: variants** (20 filters, 0 HTF gates)

- Helpful in all three splits: V16 short only (net 2,988, OOS 1,591).
- Harmful (worse expectancy in 2+ splits): V02, V15, V17, V19, V20.
- Variants that pass the robust rule: V05 (net 4,035, OOS 705); V07 (net 3,837, OOS 998); V10 (net 3,599, OOS 712); V11 (net 2,317, OOS 909); V18 (net 2,416, OOS 819).
- HTF gates helpful in all splits: none.


### 15m FINAL_H4 (verdict robust)

**15m FINAL_H4: trade quality** (1158 trades)

- Expectancy 3.7 pts (0.0324 R), median R -0.2219, R percentiles p05 -1.194 / p25 -0.595 / p75 0.231 / p95 2.561; 15.1% of trades >= +1R, 10.9% <= -1R.
- Concentration: the top 10% of trades contribute 693.5% of the net result, the best 5 trades 92.8%; net without the best 5 trades = 307.2 pts.
- Longest losing streak 12, max drawdown 2790.7 pts = Rs 209,303 per lot (83.7% of Rs 250,000), longest drawdown 484 days; recovery factor 1.54.
- Per lot of 75: net Rs 321,380 over 56.74 months, CAGR on Rs 250,000 = 19.1%, monthly Sharpe 0.48, Sortino 0.77, positive months 54.4%; t-stat of the mean trade 1.04, 95% CI of the expectancy [-3.2, 10.844] pts.
- Long 639 trades / 1625.2 pts, short 519 / 2659.9 pts. Exits: {'MA18_exit': 720, 'SL_trailing': 192, 'SL_breakeven': 140, 'SL_initial': 106}. Average hold 798 min, 20.41 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 231,719, 95th pct Rs 363,167, probability of losing half the capital 27.5%, probability of ending below the start 0.0%.

**15m FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -1,624/215/0.80; weak_bull -561/382/0.95; sideways 301/232/1.03; weak_bear 3,852/262/1.36; strong_bear 2,316/67/1.89
- volatility: low 1,693/381/1.15; normal 102/534/1.00; high 518/187/1.06; extreme 1,973/56/2.17
- session phase of entry: opening -729/117/0.84; morning 2,001/386/1.15; midday -892/307/0.92; afternoon 1,059/247/1.10; closing 2,846/101/1.77
- opening gap of the entry day: large down 368/65/1.10; large up 2,491/57/2.67; medium down 531/160/1.07; medium up 441/290/1.04; small down 812/236/1.10; small up -358/350/0.97
- trade outcome type: failed breakout (loss, MFE < 0.3R) -28,593/439/0.00; loss after progress -13,736/369/0.00; small win 11,188/175; win >= 1R 35,426/175

**15m FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 55 positive on TRAIN with >= 30 trades, 36 of them also positive on VAL and OOS. 18/200 itself: TRAIN 0.606 / VAL 7.124 / OOS 8.458 pts per trade.
- Exit grid (64 cells): 46 positive on TRAIN, 46 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 30/300, 30/200, 25/200, 25/150, 25/150; test-month net 2,698 pts versus 1,898 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 3/5 folds.

**15m FINAL_H4: variants** (20 filters, 6 HTF gates)

- Helpful in all three splits: V02 ADX(14) >= 20 (net 5,167, OOS 2,037); V10 ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) (net 5,388, OOS 2,148).
- Harmful (worse expectancy in 2+ splits): V01, V03, V04, V05, V07, V08, V13, V15, V17, V18, V19, V20.
- Variants that pass the robust rule: V02 (net 5,167, OOS 2,037); V03 (net 3,778, OOS 2,583); V09 (net 3,688, OOS 81); V10 (net 5,388, OOS 2,148); V12 (net 5,411, OOS 2,748); V13 (net 3,885, OOS 2,633); V14 (net 2,908, OOS 1,806); V18 (net 3,917, OOS 1,600).
- HTF gates helpful in all splits: none.


### 30m FINAL_H4 (verdict robust)

**30m FINAL_H4: trade quality** (599 trades)

- Expectancy 8.544 pts (0.0387 R), median R -0.1516, R percentiles p05 -1.148 / p25 -0.579 / p75 0.274 / p95 2.389; 15.7% of trades >= +1R, 12.7% <= -1R.
- Concentration: the top 10% of trades contribute 419.1% of the net result, the best 5 trades 70.1%; net without the best 5 trades = 1530.8 pts.
- Longest losing streak 12, max drawdown 2158.2 pts = Rs 161,865 per lot (64.7% of Rs 250,000), longest drawdown 431 days; recovery factor 2.37.
- Per lot of 75: net Rs 383,849 over 56.74 months, CAGR on Rs 250,000 = 21.7%, monthly Sharpe 0.49, Sortino 0.94, positive months 56.1%; t-stat of the mean trade 1.32, 95% CI of the expectancy [-4.044, 21.173] pts.
- Long 318 trades / 4485.5 pts, short 281 / 632.5 pts. Exits: {'MA18_exit': 340, 'SL_trailing': 102, 'SL_breakeven': 84, 'SL_initial': 73}. Average hold 1775 min, 10.56 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 198,817, 95th pct Rs 313,837, probability of losing half the capital 18.3%, probability of ending below the start 0.0%.

**30m FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -2,421/102/0.58; weak_bull 465/203/1.06; sideways 2,390/118/1.47; weak_bear 4,530/146/1.56; strong_bear 155/30/1.07
- volatility: low 3,015/191/1.43; normal 1,151/283/1.08; high 296/97/1.05; extreme 655/28/1.36
- session phase of entry: opening -5/44/1.00; morning 621/200/1.06; midday 3,881/181/1.54; afternoon 184/119/1.03; closing 437/55/1.16
- opening gap of the entry day: large down -3,219/39/0.32; large up 2,186/28/3.16; medium down 1,841/75/1.47; medium up -564/147/0.92; small down 2,911/131/1.52; small up 1,963/179/1.28
- trade outcome type: failed breakout (loss, MFE < 0.3R) -20,535/216/0.00; loss after progress -9,020/192/0.00; small win 8,053/97; win >= 1R 26,621/94

**30m FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 59 positive on TRAIN with >= 30 trades, 52 of them also positive on VAL and OOS. 18/200 itself: TRAIN 6.152 / VAL 9.916 / OOS 13.359 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 64 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 16/250, 18/300, 18/300, 12/50, 25/100; test-month net -895 pts versus 1,734 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 2/5 folds.

**30m FINAL_H4: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V04 entries only 09:45-13:29 (morning + midday) (net 6,215, OOS 2,042); V07 skip sessions with |gap| > 0.5% (net 6,111, OOS 1,872); V08 only sessions with |gap| <= 0.25% (net 5,608, OOS 2,522).
- Harmful (worse expectancy in 2+ splits): V01, V02, V03, V06, V09, V10, V11, V12, V13, V15, V17, V18, V19.
- Variants that pass the robust rule: V01 (net 3,312, OOS 1,125); V02 (net 3,669, OOS 1,117); V03 (net 4,958, OOS 1,669); V04 (net 6,215, OOS 2,042); V05 (net 4,928, OOS 1,880); V06 (net 1,760, OOS 430); V07 (net 6,111, OOS 1,872); V08 (net 5,608, OOS 2,522); V10 (net 5,452, OOS 1,726); V11 (net 4,021, OOS 671); V12 (net 2,933, OOS 1,252); V13 (net 3,169, OOS 1,076); V14 (net 4,288, OOS 2,319); V17 (net 2,362, OOS 484); V18 (net 5,438, OOS 1,046); V19 (net 2,880, OOS 283); V20 (net 4,059, OOS 2,045).
- HTF gates helpful in all splits: none.


### 1h FINAL_H4 (verdict robust)

**1h FINAL_H4: trade quality** (315 trades)

- Expectancy 6.128 pts (0.0591 R), median R -0.2008, R percentiles p05 -1.075 / p25 -0.524 / p75 0.263 / p95 2.436; 16.2% of trades >= +1R, 10.8% <= -1R.
- Concentration: the top 10% of trades contribute 724.5% of the net result, the best 5 trades 164.8%; net without the best 5 trades = -1249.9 pts.
- Longest losing streak 13, max drawdown 1920.5 pts = Rs 144,039 per lot (57.6% of Rs 250,000), longest drawdown 793 days; recovery factor 1.01.
- Per lot of 75: net Rs 144,763 over 56.74 months, CAGR on Rs 250,000 = 10.1%, monthly Sharpe 0.26, Sortino 0.42, positive months 50.9%; t-stat of the mean trade 0.54, 95% CI of the expectancy [-15.866, 28.085] pts.
- Long 182 trades / 1235.4 pts, short 133 / 694.7 pts. Exits: {'MA18_exit': 178, 'SL_trailing': 59, 'SL_breakeven': 45, 'SL_initial': 32, 'end_of_test': 1}. Average hold 3027 min, 5.55 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 229,943, 95th pct Rs 356,978, probability of losing half the capital 34.6%, probability of ending below the start 0.0%.

**1h FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -871/56/0.79; weak_bull 1,117/115/1.17; sideways 356/62/1.08; weak_bear 1,484/68/1.28; strong_bear -155/14/0.88
- volatility: low 2,695/108/1.52; normal -875/145/0.92; high -359/47/0.92; extreme 469/15/1.31
- session phase of entry: opening 212/47/1.07; morning 1,548/80/1.32; midday 717/110/1.09; afternoon -2,579/53/0.45; closing 2,032/25/2.42
- opening gap of the entry day: large down -1,627/18/0.30; large up 1,083/16/1.89; medium down -1,365/31/0.50; medium up -313/90/0.95; small down 2,714/69/1.66; small up 1,438/91/1.26
- trade outcome type: failed breakout (loss, MFE < 0.3R) -15,228/105/0.00; loss after progress -6,700/111/0.00; small win 5,774/48; win >= 1R 18,084/51

**1h FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 56 positive on TRAIN with >= 30 trades, 48 of them also positive on VAL and OOS. 18/200 itself: TRAIN 6.619 / VAL 8.704 / OOS 2.413 pts per trade.
- Exit grid (64 cells): 47 positive on TRAIN, 37 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 22/100, 20/100, 25/200, 25/200, 16/50; test-month net -1,618 pts versus -378 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 3/5 folds.

**1h FINAL_H4: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V18 confirmation window 1 bar (instead of 2) (net 4,722, OOS 662).
- Harmful (worse expectancy in 2+ splits): V01, V02, V03, V05, V06, V07, V10, V11, V12, V13, V14, V15, V17, V19.
- Variants that pass the robust rule: V03 (net 1,701, OOS 118); V04 (net 2,240, OOS 676); V05 (net 1,887, OOS 111); V06 (net 1,701, OOS 118); V10 (net 1,855, OOS 133); V11 (net 1,663, OOS 76); V18 (net 4,722, OOS 662); V20 (net 2,185, OOS 290).
- HTF gates helpful in all splits: none.


### 2h FINAL_H4 (verdict robust)

**2h FINAL_H4: trade quality** (174 trades)

- Expectancy 20.844 pts (0.1228 R), median R -0.0433, R percentiles p05 -1.036 / p25 -0.534 / p75 0.411 / p95 2.239; 17.2% of trades >= +1R, 7.5% <= -1R.
- Concentration: the top 10% of trades contribute 270.5% of the net result, the best 5 trades 92.9%; net without the best 5 trades = 257.2 pts.
- Longest losing streak 8, max drawdown 2188.9 pts = Rs 164,171 per lot (65.7% of Rs 250,000), longest drawdown 569 days; recovery factor 1.66.
- Per lot of 75: net Rs 272,021 over 56.74 months, CAGR on Rs 250,000 = 16.8%, monthly Sharpe 0.44, Sortino 0.66, positive months 56.1%; t-stat of the mean trade 0.98, 95% CI of the expectancy [-21.257, 65.87] pts.
- Long 104 trades / 3754.0 pts, short 70 / -127.1 pts. Exits: {'MA18_exit': 101, 'SL_trailing': 35, 'SL_breakeven': 24, 'SL_initial': 13, 'end_of_test': 1}. Average hold 5271 min, 3.07 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 208,063, 95th pct Rs 319,951, probability of losing half the capital 23.7%, probability of ending below the start 0.0%.

**2h FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull 497/23/1.38; weak_bull 2,709/61/1.70; sideways 129/48/1.03; weak_bear 726/37/1.15; strong_bear -434/5/0.00
- volatility: low 1,881/68/1.36; normal -342/81/0.96; high 921/21/1.41; extreme 1,167/4
- session phase of entry: opening 1,682/46/1.47; morning 2,968/14/8.04; midday 682/47/1.17; afternoon -525/44/0.88; closing -1,180/23/0.64
- opening gap of the entry day: large down 272/9/1.29; large up 35/13/1.03; medium down -1,227/13/0.32; medium up 2,952/52/1.79; small down 1,729/37/1.57; small up -133/50/0.97
- trade outcome type: failed breakout (loss, MFE < 0.3R) -12,172/59/0.00; loss after progress -3,528/51/0.00; small win 6,135/34; win >= 1R 13,191/30

**2h FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 59 positive on TRAIN with >= 30 trades, 32 of them also positive on VAL and OOS. 18/200 itself: TRAIN 31.281 / VAL 9.503 / OOS 6.57 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 22 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 30/300, 30/300, 30/250, 22/300, 30/200; test-month net 1,430 pts versus 1,373 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 3/5 folds.

**2h FINAL_H4: variants** (20 filters, 0 HTF gates)

- Helpful in all three splits: V03 no entries in the opening phase (before 09:45) (net 3,881, OOS 307); V06 no entries in the first hour (before 10:15) (net 3,881, OOS 307); V07 skip sessions with |gap| > 0.5% (net 4,226, OOS 1,110); V17 pending order expires after 3 bars (net 4,145, OOS 469).
- Harmful (worse expectancy in 2+ splits): V01, V02, V09, V13, V14, V16, V19, V20.
- Variants that pass the robust rule: V02 (net 4,177, OOS 1,314); V03 (net 3,881, OOS 307); V04 (net 3,667, OOS 84); V06 (net 3,881, OOS 307); V07 (net 4,226, OOS 1,110); V10 (net 3,996, OOS 1,382); V11 (net 3,824, OOS 25); V12 (net 4,193, OOS 2,315); V17 (net 4,145, OOS 469); V18 (net 5,266, OOS 952).
- HTF gates helpful in all splits: none.


### 4h FINAL_H4 (verdict unstable)

**4h FINAL_H4: trade quality** (79 trades)

- Expectancy 50.495 pts (0.1412 R), median R -0.018, R percentiles p05 -1.032 / p25 -0.511 / p75 0.504 / p95 2.16; 17.7% of trades >= +1R, 10.1% <= -1R.
- Concentration: the top 10% of trades contribute 212.4% of the net result, the best 5 trades 159.0%; net without the best 5 trades = -2352.7 pts.
- Longest losing streak 8, max drawdown 2734.4 pts = Rs 205,083 per lot (82.0% of Rs 250,000), longest drawdown 500 days; recovery factor 1.46.
- Per lot of 75: net Rs 299,184 over 56.74 months, CAGR on Rs 250,000 = 18.1%, monthly Sharpe 0.42, Sortino 0.76, positive months 40.4%; t-stat of the mean trade 0.93, 95% CI of the expectancy [-51.454, 159.306] pts.
- Long 51 trades / 2699.7 pts, short 28 / 1289.4 pts. Exits: {'MA18_exit': 47, 'SL_trailing': 16, 'SL_breakeven': 10, 'SL_initial': 6}. Average hold 11707 min, 1.39 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 216,841, 95th pct Rs 341,146, probability of losing half the capital 27.4%, probability of ending below the start 0.0%.

**4h FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -604/17/0.78; weak_bull -27/26/0.99; sideways 3,523/15/4.48; weak_bear 2,471/16/1.76; strong_bear -1,372/5/0.00
- volatility: low 929/27/1.35; normal 874/40/1.14; high 395/11/1.17; extreme 1,791/1
- session phase of entry: opening 3,869/29/1.95; morning -662/15/0.75; midday 1,040/13/1.90; afternoon -424/16/0.83; closing 166/6/1.26
- opening gap of the entry day: large down 838/3/2.98; large up 1,444/5/132.78; medium down -498/10/0.79; medium up 1,010/21/1.44; small down -138/14/0.95; small up 1,333/26/1.41
- trade outcome type: failed breakout (loss, MFE < 0.3R) -9,533/30/0.00; loss after progress -1,512/17/0.00; small win 3,459/18; win >= 1R 11,575/14

**4h FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 60 positive on TRAIN with >= 30 trades, 2 of them also positive on VAL and OOS. 18/200 itself: TRAIN 92.139 / VAL 46.372 / OOS -33.452 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 3 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 22/150, 30/250, 18/250, 16/250, 12/250; test-month net -1,808 pts versus 948 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 1/5 folds.

**4h FINAL_H4: variants** (20 filters, 0 HTF gates)

- Helpful in all three splits: V18 confirmation window 1 bar (instead of 2) (net 8,862, OOS 2,092).
- Harmful (worse expectancy in 2+ splits): V01, V03, V04, V06, V07, V11, V12, V13, V14, V16, V17.
- Variants that pass the robust rule: none.
- HTF gates helpful in all splits: none.


## 6. Cost sensitivity

| config | tf | TF | trades A/B | gross A | exec cost | charges | net B | net C | cost/trade B | break-even cost/trade | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 1334/1330 | 11,146.50 | 1,092.70 | 8,411.20 | 1,642.60 | -3,601.30 | 7.15 | 8.36 | 22.10 | 1.43 | 1.05 | 0.90 |
| ASIS | 30m | 30m | 738/739 | 8,340.60 | 1,028.90 | 4,683.70 | 2,628.00 | -72.80 | 7.73 | 11.30 | 18.90 | 1.45 | 1.11 | 1.00 |
| ASIS | 1h | 1h | 419/418 | 6,578.50 | 594.80 | 2,651.50 | 3,332.10 | 1,793.60 | 7.77 | 15.70 | 16.00 | 1.56 | 1.23 | 1.11 |
| ASIS | 2h | 2h | 262/262 | 4,654.50 | -104.50 | 1,666.90 | 3,092.00 | 1,746.80 | 5.96 | 17.77 | 11.10 | 1.58 | 1.33 | 1.16 |
| ASIS | 4h | 4h | 144/139 | 4,667.40 | -272.30 | 905.00 | 4,034.70 | 4,160.30 | 4.55 | 32.41 | 5.80 | 1.91 | 1.68 | 1.74 |
| FINAL_H4 | 15m | 15m | 1157/1158 | 13,302.50 | 1,722.60 | 7,294.80 | 4,285.10 | -88.60 | 7.79 | 11.50 | 16.70 | 1.37 | 1.10 | 1.00 |
| FINAL_H4 | 30m | 30m | 601/599 | 9,386.20 | 499.10 | 3,769.10 | 5,118.00 | 2,690.50 | 7.13 | 15.62 | 11.10 | 1.35 | 1.17 | 1.09 |
| FINAL_H4 | 1h | 1h | 315/315 | 4,367.90 | 447.30 | 1,990.40 | 1,930.20 | 458.90 | 7.74 | 13.87 | 9.40 | 1.22 | 1.09 | 1.02 |
| FINAL_H4 | 2h | 2h | 174/174 | 4,899.00 | 169.60 | 1,102.40 | 3,626.90 | 3,026.70 | 7.31 | 28.16 | 6.20 | 1.33 | 1.23 | 1.19 |
| FINAL_H4 | 4h | 4h | 79/79 | 4,598.50 | 105.20 | 504.10 | 3,989.10 | 3,712.20 | 7.71 | 58.21 | 3.90 | 1.43 | 1.36 | 1.33 |

Slippage per side varied (B charges kept), net points:

| config | TF | slip 0.0 | slip 0.5 | slip 1.0 | slip 2.0 | slip 3.0 |
|---|---|---|---|---|---|---|
| ASIS | 1m | -82,576.00 | -98,826.00 | -115,189.00 | -147,296.00 | -180,209.00 |
| ASIS | 3m | -21,556.00 | -27,186.00 | -33,348.00 | -44,783.00 | -56,302.00 |
| ASIS | 5m | -13,609.00 | -17,493.00 | -21,372.00 | -28,191.00 | -34,983.00 |
| ASIS | 10m | -2,199.00 | -4,029.00 | -5,688.00 | -10,311.00 | -13,741.00 |
| ASIS | 15m | 2,898.00 | 1,643.00 | 40.00 | -2,668.00 | -5,452.00 |
| ASIS | 30m | 3,569.00 | 2,628.00 | 1,922.00 | 248.00 | -1,026.00 |
| ASIS | 1h | 3,826.00 | 3,332.00 | 3,279.00 | 2,756.00 | 2,335.00 |
| ASIS | 2h | 2,806.00 | 3,092.00 | 2,821.00 | 2,060.00 | 1,515.00 |
| ASIS | 4h | 3,727.00 | 4,035.00 | 3,485.00 | 5,322.00 | 5,150.00 |
| FINAL_H4 | 1m | -86,578.00 | -104,956.00 | -123,184.00 | -158,606.00 | -193,967.00 |
| FINAL_H4 | 3m | -18,186.00 | -24,565.00 | -31,037.00 | -42,484.00 | -54,565.00 |
| FINAL_H4 | 5m | -9,712.00 | -13,350.00 | -16,744.00 | -23,947.00 | -31,118.00 |
| FINAL_H4 | 10m | 1,302.00 | -215.00 | -2,043.00 | -5,764.00 | -9,341.00 |
| FINAL_H4 | 15m | 5,901.00 | 4,285.00 | 3,036.00 | 640.00 | -1,584.00 |
| FINAL_H4 | 30m | 5,571.00 | 5,118.00 | 4,571.00 | 3,888.00 | 2,896.00 |
| FINAL_H4 | 1h | 2,372.00 | 1,930.00 | 1,363.00 | 745.00 | 453.00 |
| FINAL_H4 | 2h | 3,789.00 | 3,627.00 | 3,469.00 | 3,057.00 | 2,941.00 |

## 7. Answers

1. **Does the original strategy work on NIFTY 50?** As written (AS-IS, ticks as points) it is negative on 1m-10m and D1 and positive but weak on 15m-4h (PF 1.05-1.68, t <= 1.3). The 25-point break-even trigger dominates: 182 of 262 exits on 2h and 94 of 139 on 4h are break-even stops at +0.5 point, so the strategy behaves like the gold D1 case, taking tiny scratches and a few large swing-protected winners.
2. **Most stable timeframe:** 30 minutes with the ATR-scaled exits (net +5,118 pts, PF 1.17, TRAIN 2,085 / VAL 1,269 / OOS 1,763, 4 of 5 years positive, broad positive region in the parameter maps). 2h and 4h show higher expectancy per trade but on 79-262 trades with 2024 or the OOS year negative.
3. **Costs:** charges are about 7 points per round trip and slippage 1 point; the break-even cost per trade is 8-11 points on 15m, 16-58 points on 1h-4h. 15m survives scenario B but not the stress scenario (FINAL_H4 15m: +4,285 -> -89 pts); 30m and above survive C.
4. **Slippage:** 15m loses its edge at 2-3 points of slippage per side; 30m keeps about half of it at 3 points; 1h-4h are insensitive.
5. **Years:** no configuration is positive in all five years. 30m FINAL_H4: 2022 +1,426, 2023 +1,750, 2024 -459, 2025 +629, 2026 +1,772. The AS-IS 15m/30m runs lose 2024 and 2025 or 2026.
6. **Regimes:** every candidate loses in strong-bull sessions and earns in weak-bear and sideways sessions; low and extreme volatility sessions earn, normal volatility is flat. Entries in the opening 30 minutes lose on every timeframe; midday and closing-phase entries earn. Large gap-up days are the best gap class. Fridays carry the result on 15m and 30m.
7. **Out-of-sample (Sep 2025 - Sep 2026):** positive for FINAL_H4 15m (+2,098), 30m (+1,763), 2h (+263), 1h (+169) and for AS-IS 4h (+705) and 2h (+46); negative for FINAL_H4 4h and AS-IS 30m/1h. The OOS window is a bear-to-sideways year, exactly the regime the strategy likes, so the OOS result is regime-dependent.
8. **Parameter robustness:** the fast/trend maps are positive on TRAIN almost everywhere (the TRAIN years were a trending market) but only 30m FINAL_H4 (52/60 cells) and 1h FINAL_H4 (48/60) keep most cells positive in VAL and OOS; 4h has 2-3 of 60. Exit-parameter maps are broadly positive for the ATR configuration and 15m-30m. Walk-forward re-optimisation of the moving averages beats the fixed 18/200 in only 1-3 of 5 folds and loses money in aggregate on most timeframes: the parameter choice adds noise, not information.
9. **High-quality setups worth further research:** (a) 30m ATR-scaled exits with entries between 09:45 and 13:29 (variant V04: +6,215 pts, PF 1.27, positive in all splits) and with large-gap sessions skipped (V07: +6,111, PF 1.29) - both helpful in every split on 30m and 2h but harmful on 15m and 1h, so they are timeframe-specific until confirmed forward; (b) the Friday concentration, which needs an explanation (day after the weekly expiry) before it can be used; (c) the bear/sideways regime dependence, which argues for trading the short side or for a regime switch rather than for the strategy as written.
10. **Genuine or overfitting?** The after-cost profit is real in the backtest but not defensible: no t-statistic above 1.3, outlier-driven, regime- and weekday-concentrated, and the walk-forward shows that re-fitting hurts. With 40 baseline runs and 460 variants tested, six 'robust' flags are within what chance produces.
11. **Conditions:** better in weak-bear and sideways 63-day regimes, extreme or low volatility, midday and closing-phase entries, Fridays, after large gap-ups; worse in strong bull regimes, opening-phase entries, Mondays and Tuesdays, and at 1m-10m where costs exceed the gross edge.

## 8. Files
- backtests/nifty50/: every run's trade list (config_TF_scenario_trades.csv.gz)
- research/timeframe_analysis.md, cost_analysis.md, regime_analysis.md, robustness_analysis.md, walk_forward_analysis.md, variants_mtf_analysis.md, experiment_log.csv
