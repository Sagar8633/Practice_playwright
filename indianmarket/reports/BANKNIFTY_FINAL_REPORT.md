# NIFTY BANK: final report (SimpleSMA18Bot logic, 3 Jan 2022 to 26 Sep 2026)

Verdict: **no statistically defensible positive expectancy on NIFTY BANK.** The strategy as written (AS-IS) is negative after costs on nine of ten timeframes (the 1h run is +4,206 points but loses 4,321 in the out-of-sample year). With the ATR-scaled exits (FINAL_H4) 15m, 30m and 1h are positive after costs; 15m (+15,190 points per unit, PF 1.15, 4 of 5 years, positive in all three splits) and 1h (+5,448, all three splits) pass the robust rule. Neither is statistically distinguishable from zero (t = 1.45 and 0.51), the 1h result disappears without its five best trades (-7,245 pts without them), the 15m result has a 30-trade losing streak and a 7,130-point drawdown that equals the whole Rs 2.5 lakh capital per lot, and both lose in strong-bull sessions and on Mondays while Fridays contribute 12,546 of the 15,190 points. D1 is negative in 2022-2026 in both configurations; the 2010-2026 daily history is positive only for the AS-IS rules (+6,795 pts, PF 1.31, 10 of 17 years) and 2022-2023 were its two worst years. The 15-minute ATR configuration is the best-behaved candidate for a forward test.

## 1. Setup

Data: Upstox 1-minute index candles (IST, 09:15-15:29, 1,174 sessions) cross-checked against the official NSE daily series; daily official history 2007-2026 for the long D1 test. See data/DATA_AUDIT.md. Costs: scenario A gross, B realistic (spread 0.3 pts, slippage 1.5 pts per side, all statutory charges and Rs 20 brokerage per order), C stress. Money unit: index points per unit; one futures lot = 35 units; capital per lot for percentages Rs 250,000. Configurations: AS-IS (v1.00 rules, 1 point = 1 tick) and FINAL_H4 (the ATR-scaled exit stack selected in the gold study). The volume filter cannot be evaluated on an index and is off in both.

Splits fixed before the runs: TRAIN 2022-01-03..2024-08-31, VAL 2024-09-01..2025-08-31, OOS 2025-09-01..2026-09-26. Verdict rule: robust = positive expectancy and PF > 1 after B costs in all three splits with >= 30 trades each.


## 2a. Every timeframe, ASIS (scenario B unless stated)

| TF | trades | gross A | net B | net C | PF B | win % | exp pts | exp R | median R | max DD | Sharpe(m) | top-5 share % | TRAIN | VAL | OOS | OOS PF | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 19595 | 23,211.90 | -316,654.60 | -508,531.60 | 0.45 | 16.20 | -16.16 | -0.37 | -0.46 | 318,044.60 | -8.91 |  | -163,466.30 | -72,719.10 | -80,469.10 | 0.43 | negative |
| 3m | 7861 | 19,352.90 | -118,398.20 | -190,910.20 | 0.56 | 14.10 | -15.06 | -0.20 | -0.18 | 121,448.70 | -4.44 |  | -56,091.70 | -28,552.80 | -33,753.70 | 0.52 | negative |
| 5m | 5183 | 10,963.20 | -78,272.70 | -126,308.30 | 0.59 | 12.20 | -15.10 | -0.14 | -0.12 | 79,826.70 | -3.71 |  | -36,235.80 | -20,830.90 | -21,206.00 | 0.55 | negative |
| 10m | 2869 | 27,234.40 | -21,548.90 | -45,269.20 | 0.81 | 11.70 | -7.51 | -0.07 | -0.08 | 28,190.90 | -0.91 |  | -12,009.80 | -9,799.30 | 260.20 | 1.01 | negative |
| 15m | 1958 | 27,322.20 | -5,002.30 | -23,500.90 | 0.94 | 10.50 | -2.56 | -0.04 | -0.06 | 15,269.60 | -0.26 |  | -4,582.20 | -693.50 | 273.50 | 1.01 | negative |
| 30m | 1190 | 13,247.80 | -9,709.00 | -19,598.70 | 0.82 | 7.60 | -8.16 | -0.03 | -0.04 | 17,208.40 | -0.54 |  | -8,189.90 | 424.70 | -1,943.80 | 0.86 | negative |
| 1h | 627 | 14,010.50 | 4,206.40 | -4,070.90 | 1.13 | 7.30 | 6.71 | 0.02 | -0.02 | 5,943.20 | 0.24 | 329.70 | 617.60 | 7,910.10 | -4,321.30 | 0.59 | unstable |
| 2h | 410 | 1,464.40 | -5,417.60 | -10,609.10 | 0.76 | 5.90 | -13.21 | -0.01 | -0.02 | 7,705.30 | -0.41 |  | -3,828.00 | 744.50 | -2,334.10 | 0.57 | negative |
| 4h | 245 | -2,643.70 | -8,238.60 | -8,796.90 | 0.44 | 3.30 | -33.63 | -0.04 | -0.01 | 8,238.60 | -0.85 |  | -3,399.40 | -480.70 | -4,358.60 | 0.09 | negative |
| D1 | 107 | -3,135.30 | -4,873.10 | -5,537.00 | 0.00 | 0.90 | -45.54 | -0.03 | -0.01 | 4,873.10 | -1.51 |  | -2,273.20 | -1,392.70 | -1,207.20 | 0.00 | negative |

## 2b. Every timeframe, FINAL_H4 (scenario B unless stated)

| TF | trades | gross A | net B | net C | PF B | win % | exp pts | exp R | median R | max DD | Sharpe(m) | top-5 share % | TRAIN | VAL | OOS | OOS PF | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 18508 | 36,593.70 | -286,666.60 | -468,960.40 | 0.54 | 20.10 | -15.49 | -0.34 | -0.55 | 290,290.50 | -7.69 |  | -146,794.00 | -65,765.80 | -74,106.80 | 0.51 | negative |
| 3m | 6181 | 26,201.00 | -80,905.80 | -137,991.80 | 0.73 | 23.80 | -13.09 | -0.17 | -0.42 | 84,779.50 | -2.74 |  | -40,995.90 | -20,033.10 | -19,876.80 | 0.74 | negative |
| 5m | 3664 | 28,642.10 | -34,786.20 | -69,488.10 | 0.84 | 25.50 | -9.49 | -0.09 | -0.38 | 40,540.90 | -1.23 |  | -15,123.60 | -10,569.70 | -9,092.90 | 0.83 | negative |
| 10m | 1836 | 34,297.60 | 2,718.80 | -13,306.40 | 1.02 | 27.50 | 1.48 | -0.03 | -0.31 | 13,055.90 | 0.10 | 376.10 | 750.10 | -6,593.10 | 8,561.80 | 1.26 | unstable |
| 15m | 1125 | 34,635.80 | 15,190.20 | 4,345.10 | 1.15 | 29.40 | 13.50 | 0.01 | -0.21 | 7,129.50 | 0.64 | 66.20 | 11,058.20 | 2,164.60 | 1,967.30 | 1.07 | robust |
| 30m | 593 | 16,146.40 | 6,230.20 | 891.50 | 1.07 | 29.20 | 10.51 | 0.01 | -0.26 | 6,766.10 | 0.26 | 152.20 | 6,888.40 | -735.60 | 77.40 | 1.00 | unstable |
| 1h | 309 | 10,720.50 | 5,447.80 | 2,881.70 | 1.09 | 28.80 | 17.63 | 0.01 | -0.21 | 6,310.00 | 0.21 | 233.00 | 1,837.20 | 2,334.40 | 1,276.30 | 1.08 | robust |
| 2h | 187 | -1,967.50 | -5,395.60 | -6,936.30 | 0.89 | 31.60 | -28.85 | -0.06 | -0.24 | 11,365.60 | -0.34 |  | -1,611.30 | -2,355.40 | -1,428.80 | 0.86 | negative |
| 4h | 90 | -2,990.10 | -4,547.70 | -5,381.50 | 0.86 | 26.70 | -50.53 | -0.10 | -0.26 | 11,186.80 | -0.26 |  | 4,912.40 | -6,567.40 | -2,892.60 | 0.65 | negative |
| D1 | 42 | -14,140.20 | -14,866.10 | -15,260.10 | 0.45 | 21.40 | -353.96 | -0.16 | -0.34 | 18,848.70 | -0.78 |  | -1,076.80 | -3,566.70 | -10,222.60 | 0.22 | negative |

## 3. Year by year (scenario B, candidate timeframes)


**ASIS**

| TF | year | trades | win % | PF | exp pts | exp R | net pts | net R | max DD pts |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 2022 | 392 | 12.80 | 1.15 | 6.04 | -0.01 | 2,366.60 | -5.31 | 3,022.20 |
| 15m | 2023 | 408 | 9.80 | 0.69 | -12.61 | -0.08 | -5,142.70 | -33.69 | 6,527.80 |
| 15m | 2024 | 415 | 10.40 | 0.93 | -2.75 | -0.04 | -1,141.70 | -15.02 | 3,901.70 |
| 15m | 2025 | 430 | 10.90 | 0.71 | -12.07 | -0.06 | -5,189.50 | -27.56 | 9,164.80 |
| 15m | 2026 | 313 | 8.30 | 1.32 | 13.12 | 0.03 | 4,105.00 | 8.43 | 4,162.90 |
| 30m | 2022 | 237 | 11.80 | 1.41 | 15.89 | 0.06 | 3,765.10 | 13.32 | 2,197.60 |
| 30m | 2023 | 268 | 6.30 | 0.56 | -19.16 | -0.06 | -5,133.90 | -16.34 | 7,407.50 |
| 30m | 2024 | 248 | 5.20 | 0.35 | -35.97 | -0.09 | -8,920.70 | -21.62 | 8,920.70 |
| 30m | 2025 | 249 | 6.00 | 0.99 | -0.41 | -0.06 | -102.50 | -14.58 | 5,417.10 |
| 30m | 2026 | 188 | 9.60 | 1.07 | 3.63 | 0.02 | 683.10 | 3.02 | 3,136.80 |
| 1h | 2022 | 117 | 8.50 | 1.32 | 12.17 | 0.04 | 1,424.40 | 4.78 | 1,435.80 |
| 1h | 2023 | 150 | 8.00 | 0.98 | -0.77 | -0.01 | -115.70 | -1.62 | 3,945.40 |
| 1h | 2024 | 114 | 7.00 | 1.47 | 18.29 | 0.04 | 2,084.90 | 4.52 | 2,380.80 |
| 1h | 2025 | 143 | 7.00 | 1.46 | 22.25 | 0.05 | 3,181.80 | 6.62 | 3,574.20 |
| 1h | 2026 | 103 | 5.80 | 0.70 | -23.00 | -0.04 | -2,369.00 | -4.06 | 5,132.60 |

**FINAL_H4**

| TF | year | trades | win % | PF | exp pts | exp R | net pts | net R | max DD pts |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 2022 | 232 | 29.30 | 1.34 | 27.48 | 0.06 | 6,376.60 | 13.90 | 2,601.40 |
| 15m | 2023 | 238 | 32.80 | 1.32 | 22.56 | 0.01 | 5,369.20 | 2.25 | 2,091.00 |
| 15m | 2024 | 238 | 28.20 | 1.06 | 6.11 | -0.02 | 1,453.70 | -3.72 | 6,523.70 |
| 15m | 2025 | 252 | 29.00 | 0.90 | -8.92 | -0.05 | -2,247.70 | -11.95 | 4,994.60 |
| 15m | 2026 | 165 | 27.30 | 1.20 | 25.69 | 0.04 | 4,238.40 | 5.86 | 4,805.40 |
| 30m | 2022 | 121 | 33.90 | 1.28 | 36.23 | 0.12 | 4,383.70 | 14.19 | 3,519.10 |
| 30m | 2023 | 124 | 29.80 | 1.22 | 22.14 | 0.02 | 2,746.00 | 1.89 | 2,575.40 |
| 30m | 2024 | 126 | 24.60 | 0.98 | -3.08 | -0.05 | -388.50 | -6.72 | 3,070.60 |
| 30m | 2025 | 132 | 28.00 | 0.86 | -19.46 | -0.11 | -2,569.10 | -14.50 | 6,328.40 |
| 30m | 2026 | 90 | 30.00 | 1.11 | 22.87 | 0.15 | 2,058.10 | 13.53 | 5,027.00 |
| 1h | 2022 | 52 | 32.70 | 1.28 | 50.34 | 0.19 | 2,617.50 | 9.98 | 2,779.30 |
| 1h | 2023 | 76 | 27.60 | 1.10 | 15.36 | -0.04 | 1,167.50 | -3.18 | 1,732.70 |
| 1h | 2024 | 62 | 30.60 | 0.94 | -13.00 | 0.09 | -806.30 | 5.60 | 4,292.80 |
| 1h | 2025 | 72 | 29.20 | 1.03 | 5.65 | -0.03 | 406.70 | -1.99 | 3,939.60 |
| 1h | 2026 | 47 | 23.40 | 1.17 | 43.88 | -0.12 | 2,062.40 | -5.76 | 6,310.00 |

## 4. D1 on the official daily history 2010-2026

| config | scenario | trades | net pts | PF | exp R | max DD pts | years > 0 | by year (net) |
|---|---|---|---|---|---|---|---|---|
| ASIS | A | 294 | 10,749.30 | 1.58 | 0.07 | 6,312.90 | 10/17 | 2010: 2729, 2011: -389, 2012: -1376, 2013: 740, 2014: 3261, 2015: -943, 2016: 1857, 2017: 1540, 2018: -1484, 2019: 1340, 2020: 3855, 2021: 2192, 2022: -3629, 2023: -2683, 2024: 3857, 2025: 904, 2026: -1022 |
| ASIS | B | 295 | 6,795.10 | 1.31 | 0.05 | 6,857.20 | 10/17 | 2010: 2652, 2011: -483, 2012: -1464, 2013: 663, 2014: 3114, 2015: -1094, 2016: 1184, 2017: 915, 2018: -1640, 2019: 1081, 2020: 3692, 2021: 1999, 2022: -3896, 2023: -2936, 2024: 3494, 2025: 571, 2026: -1057 |
| FINAL_H4 | A | 174 | -19,375.30 | 0.69 | -0.04 | 21,493.00 | 6/17 | 2010: 1999, 2011: -2691, 2012: -1591, 2013: -1042, 2014: 3279, 2015: -4077, 2016: 1637, 2017: 1768, 2018: -1255, 2019: -1545, 2020: -199, 2021: 2106, 2022: -754, 2023: 620, 2024: -4571, 2025: -1376, 2026: -11683 |
| FINAL_H4 | B | 174 | -21,552.40 | 0.67 | -0.05 | 23,572.60 | 6/17 | 2010: 1915, 2011: -2783, 2012: -1654, 2013: -1101, 2014: 3199, 2015: -4192, 2016: 1363, 2017: 1685, 2018: -1366, 2019: -1674, 2020: -315, 2021: 1970, 2022: -866, 2023: 465, 2024: -4759, 2025: -1582, 2026: -11856 |

## 5. Trade quality, market conditions, robustness and variants of the candidate timeframes


### 1h ASIS (verdict unstable)

**1h ASIS: trade quality** (627 trades)

- Expectancy 6.709 pts (0.0163 R), median R -0.0249, R percentiles p05 -0.614 / p25 -0.045 / p75 -0.016 / p95 0.425; 2.6% of trades >= +1R, 2.6% <= -1R.
- Concentration: the top 10% of trades contribute 845.3% of the net result, the best 5 trades 329.7%; net without the best 5 trades = -9661.2 pts.
- Longest losing streak 48, max drawdown 5943.2 pts = Rs 208,013 per lot (83.2% of Rs 250,000), longest drawdown 564 days; recovery factor 0.71.
- Per lot of 35: net Rs 147,224 over 56.74 months, CAGR on Rs 250,000 = 10.3%, monthly Sharpe 0.24, Sortino 0.42, positive months 42.1%; t-stat of the mean trade 0.49, 95% CI of the expectancy [-19.034, 37.368] pts.
- Long 362 trades / 8317.4 pts, short 265 / -4111.0 pts. Exits: {'SL_breakeven': 530, 'MA18_exit': 51, 'SL_swing': 30, 'SL_initial': 15, 'end_of_test': 1}. Average hold 886 min, 11.05 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 236,488, 95th pct Rs 368,689, probability of losing half the capital 37.5%, probability of ending below the start 0.0%.

**1h ASIS: by market condition** (net pts / trades / PF)

- trend: strong_bull -3,907/132/0.51; weak_bull -312/189/0.96; sideways 8,366/145/2.47; weak_bear 3,507/115/1.67; strong_bear -3,447/46/0.13
- volatility: low 452/259/1.04; normal 5,858/285/1.46; high -1,560/65/0.64; extreme -543/18/0.66
- session phase of entry: opening 938/120/1.14; morning 4,169/153/1.54; midday -135/164/0.98; afternoon 1,140/125/1.32; closing -1,905/65/0.69
- opening gap of the entry day: large down -2,893/51/0.16; large up 6,737/41/8.33; medium down 2,562/100/1.53; medium up -3,207/120/0.68; small down -2,838/148/0.50; small up 3,846/167/1.59
- trade outcome type: failed breakout (loss, MFE < 0.3R) -29,034/503/0.00; loss after progress -2,505/78/0.00; small win 10,027/30; win >= 1R 25,719/16

**1h ASIS: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 6 positive on TRAIN with >= 30 trades, 0 of them also positive on VAL and OOS. 18/200 itself: TRAIN 1.79 / VAL 62.284 / OOS -27.879 pts per trade.
- Exit grid (45 cells): 45 positive on TRAIN, 0 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 20/250, 30/200, 30/200, 18/200, 20/150; test-month net 920 pts versus 3,036 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 2/5 folds.

**1h ASIS: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V20 no sessions of high/extreme realised volatility (net 7,265, OOS -2,246).
- Harmful (worse expectancy in 2+ splits): V01, V02, V04, V07, V08, V10, V12, V13, V14, V16, V18.
- Variants that pass the robust rule: none.
- HTF gates helpful in all splits: none.


### 15m FINAL_H4 (verdict robust)

**15m FINAL_H4: trade quality** (1125 trades)

- Expectancy 13.502 pts (0.0056 R), median R -0.2147, R percentiles p05 -1.152 / p25 -0.576 / p75 0.138 / p95 2.322; 13.8% of trades >= +1R, 12.0% <= -1R.
- Concentration: the top 10% of trades contribute 540.0% of the net result, the best 5 trades 66.2%; net without the best 5 trades = 5140.7 pts.
- Longest losing streak 30, max drawdown 7129.5 pts = Rs 249,534 per lot (99.8% of Rs 250,000), longest drawdown 652 days; recovery factor 2.13.
- Per lot of 35: net Rs 531,656 over 56.74 months, CAGR on Rs 250,000 = 27.3%, monthly Sharpe 0.64, Sortino 1.06, positive months 61.4%; t-stat of the mean trade 1.45, 95% CI of the expectancy [-5.158, 31.82] pts.
- Long 618 trades / 6042.8 pts, short 507 / 9147.4 pts. Exits: {'MA18_exit': 696, 'SL_breakeven': 156, 'SL_trailing': 156, 'SL_initial': 117}. Average hold 822 min, 19.83 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 245,664, 95th pct Rs 383,867, probability of losing half the capital 26.4%, probability of ending below the start 0.0%.

**15m FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -5,981/270/0.76; weak_bull 1,086/339/1.03; sideways 10,700/215/1.62; weak_bear 8,607/228/1.43; strong_bear 779/73/1.08
- volatility: low 4,112/435/1.13; normal 3,212/531/1.06; high 4,907/132/1.31; extreme 2,959/27/2.36
- session phase of entry: opening -658/103/0.93; morning 3,815/383/1.11; midday 1,986/287/1.09; afternoon 3,805/266/1.13; closing 6,243/86/1.67
- opening gap of the entry day: large down 887/83/1.07; large up 6,590/80/1.99; medium down 9,958/190/1.65; medium up 3,723/240/1.18; small down -3,140/234/0.85; small up -2,828/298/0.90
- trade outcome type: failed breakout (loss, MFE < 0.3R) -69,635/408/0.00; loss after progress -35,140/386/0.00; small win 32,445/176; win >= 1R 87,521/155

**15m FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 53 positive on TRAIN with >= 30 trades, 16 of them also positive on VAL and OOS. 18/200 itself: TRAIN 17.778 / VAL 8.456 / OOS 7.965 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 64 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 18/300, 25/300, 22/100, 22/250, 22/100; test-month net -339 pts versus 3,677 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 1/5 folds.

**15m FINAL_H4: variants** (20 filters, 6 HTF gates)

- Helpful in all three splits: V02 ADX(14) >= 20 (net 17,682, OOS 2,494).
- Harmful (worse expectancy in 2+ splits): V01, V04, V05, V06, V07, V08, V10, V11, V12, V13, V14, V15, V17, V18, V19, V20.
- Variants that pass the robust rule: V01 (net 11,600, OOS 2,553); V02 (net 17,682, OOS 2,494); V03 (net 18,326, OOS 4,653); V04 (net 9,835, OOS 1,287); V05 (net 9,215, OOS 1,222); V06 (net 12,710, OOS 1,939); V10 (net 12,662, OOS 1,349); V12 (net 11,580, OOS 3,381); V13 (net 3,206, OOS 1,002); V16 (net 9,147, OOS 2,038); V17 (net 13,915, OOS 1,146); V18 (net 6,348, OOS 2,490); V19 (net 9,772, OOS 1,610).
- HTF gates helpful in all splits: none.


### 30m FINAL_H4 (verdict unstable)

**30m FINAL_H4: trade quality** (593 trades)

- Expectancy 10.506 pts (0.0141 R), median R -0.2566, R percentiles p05 -1.113 / p25 -0.613 / p75 0.126 / p95 2.156; 14.0% of trades >= +1R, 14.0% <= -1R.
- Concentration: the top 10% of trades contribute 929.8% of the net result, the best 5 trades 152.2%; net without the best 5 trades = -3251.9 pts.
- Longest losing streak 14, max drawdown 6766.1 pts = Rs 236,815 per lot (94.7% of Rs 250,000), longest drawdown 333 days; recovery factor 0.92.
- Per lot of 35: net Rs 218,058 over 56.74 months, CAGR on Rs 250,000 = 14.2%, monthly Sharpe 0.26, Sortino 0.46, positive months 50.9%; t-stat of the mean trade 0.59, 95% CI of the expectancy [-23.622, 45.472] pts.
- Long 313 trades / 12560.2 pts, short 280 / -6330.0 pts. Exits: {'MA18_exit': 340, 'SL_trailing': 92, 'SL_breakeven': 83, 'SL_initial': 78}. Average hold 1693 min, 10.45 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 310,676, 95th pct Rs 487,603, probability of losing half the capital 48.2%, probability of ending below the start 0.0%.

**30m FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -2,270/123/0.86; weak_bull 5,004/196/1.21; sideways -2,572/118/0.86; weak_bear 9,119/114/1.65; strong_bear -3,051/42/0.73
- volatility: low 2,616/235/1.11; normal 2,568/270/1.06; high 1,195/71/1.08; extreme -149/17/0.95
- session phase of entry: opening -1,665/49/0.79; morning 3,072/211/1.09; midday 7,329/159/1.42; afternoon -3,693/125/0.80; closing 1,186/49/1.24
- opening gap of the entry day: large down -4,729/43/0.59; large up 7,675/51/2.22; medium down 4,111/110/1.25; medium up -1,194/130/0.93; small down 3,052/121/1.22; small up -2,686/138/0.85
- trade outcome type: failed breakout (loss, MFE < 0.3R) -59,924/220/0.00; loss after progress -24,217/200/0.00; small win 27,596/90; win >= 1R 62,775/83

**30m FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 58 positive on TRAIN with >= 30 trades, 17 of them also positive on VAL and OOS. 18/200 itself: TRAIN 20.937 / VAL -5.615 / OOS 0.582 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 24 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 25/50, 18/250, 12/250, 30/300, 30/300; test-month net -9,323 pts versus -1,124 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 2/5 folds.

**30m FINAL_H4: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V07 skip sessions with |gap| > 0.5% (net 8,924, OOS 2,939); V08 only sessions with |gap| <= 0.25% (net 6,049, OOS 579).
- Harmful (worse expectancy in 2+ splits): V02, V03, V06, V09, V12, V14, V16, V17.
- Variants that pass the robust rule: V01 (net 6,110, OOS 256); V07 (net 8,924, OOS 2,939); V08 (net 6,049, OOS 579); V18 (net 11,747, OOS 2,614); V20 (net 6,580, OOS 1,359).
- HTF gates helpful in all splits: none.


### 1h FINAL_H4 (verdict robust)

**1h FINAL_H4: trade quality** (309 trades)

- Expectancy 17.63 pts (0.015 R), median R -0.2142, R percentiles p05 -1.07 / p25 -0.588 / p75 0.196 / p95 2.024; 14.9% of trades >= +1R, 9.7% <= -1R.
- Concentration: the top 10% of trades contribute 770.8% of the net result, the best 5 trades 233.0%; net without the best 5 trades = -7245.4 pts.
- Longest losing streak 18, max drawdown 6310.0 pts = Rs 220,849 per lot (88.3% of Rs 250,000), longest drawdown 599 days; recovery factor 0.86.
- Per lot of 35: net Rs 190,674 over 56.74 months, CAGR on Rs 250,000 = 12.7%, monthly Sharpe 0.21, Sortino 0.39, positive months 49.1%; t-stat of the mean trade 0.51, 95% CI of the expectancy [-50.213, 88.177] pts.
- Long 182 trades / 8508.2 pts, short 127 / -3060.4 pts. Exits: {'MA18_exit': 181, 'SL_breakeven': 51, 'SL_trailing': 50, 'SL_initial': 26, 'end_of_test': 1}. Average hold 2927 min, 5.45 trades per month.
- Monte Carlo (3,000 trade-order shuffles, one lot on Rs 250,000): median drawdown Rs 317,488, 95th pct Rs 497,517, probability of losing half the capital 52.1%, probability of ending below the start 0.0%.

**1h FINAL_H4: by market condition** (net pts / trades / PF)

- trend: strong_bull -4,081/67/0.68; weak_bull -721/103/0.96; sideways 10,191/68/1.82; weak_bear 2,113/52/1.21; strong_bear -2,054/19/0.65
- volatility: low 2,664/131/1.13; normal -638/139/0.98; high 2,281/32/1.33; extreme 1,141/7/1.68
- session phase of entry: opening -813/49/0.92; morning 7,321/79/1.52; midday 8,151/92/1.64; afternoon -3,640/62/0.73; closing -5,572/27/0.40
- opening gap of the entry day: large down 2,080/25/1.30; large up 8,194/30/2.52; medium down 1,028/50/1.11; medium up -5,386/63/0.64; small down 424/70/1.04; small up -892/71/0.92
- trade outcome type: failed breakout (loss, MFE < 0.3R) -45,884/120/0.00; loss after progress -13,741/100/0.00; small win 14,095/43; win >= 1R 50,977/46

**1h FINAL_H4: parameter robustness and walk-forward**

- MA grid (10 fast x 6 trend = 60 cells): 41 positive on TRAIN with >= 30 trades, 12 of them also positive on VAL and OOS. 18/200 itself: TRAIN 10.681 / VAL 35.913 / OOS 17.726 pts per trade.
- Exit grid (64 cells): 64 positive on TRAIN, 5 also positive on OOS.
- Walk-forward (5 folds, best TRAIN pair re-chosen each fold): chosen pairs 10/50, 25/100, 10/200, 10/200, 18/50; test-month net 5,354 pts versus 2,064 pts for the fixed 18/200; the re-optimised pair beat 18/200 in 4/5 folds.

**1h FINAL_H4: variants** (20 filters, 4 HTF gates)

- Helpful in all three splits: V05 no entries in the closing phase (after 15:00) (net 6,970, OOS 1,864).
- Harmful (worse expectancy in 2+ splits): V03, V06, V09, V11, V13, V14, V16, V17, V18, V20.
- Variants that pass the robust rule: V01 (net 7,704, OOS 3,339); V02 (net 5,286, OOS 2,573); V03 (net 3,496, OOS 322); V04 (net 5,595, OOS 1,656); V05 (net 6,970, OOS 1,864); V06 (net 3,496, OOS 322); V07 (net 8,521, OOS 859); V10 (net 6,605, OOS 1,669); V12 (net 8,749, OOS 442); V17 (net 5,022, OOS 390); V19 (net 5,703, OOS 1,666).
- HTF gates helpful in all splits: none.


## 6. Cost sensitivity

| config | tf | TF | trades A/B | gross A | exec cost | charges | net B | net C | cost/trade B | break-even cost/trade | costs % of gross profit | PF A | PF B | PF C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIS | 15m | 15m | 1993/1958 | 27,322.20 | 4,820.80 | 27,503.70 | -5,002.30 | -23,500.90 | 16.51 | 13.71 | 31.70 | 1.54 | 0.94 | 0.75 |
| ASIS | 30m | 30m | 1197/1190 | 13,247.80 | 6,259.40 | 16,697.40 | -9,709.00 | -19,598.70 | 19.29 | 11.07 | 37.60 | 1.40 | 0.82 | 0.69 |
| ASIS | 1h | 1h | 645/627 | 14,010.50 | 973.70 | 8,830.50 | 4,206.40 | -4,070.90 | 15.64 | 21.72 | 22.00 | 1.64 | 1.13 | 0.89 |
| ASIS | 2h | 2h | 418/410 | 1,464.40 | 1,002.00 | 5,880.10 | -5,417.60 | -10,609.10 | 16.79 | 3.50 | 30.00 | 1.09 | 0.76 | 0.60 |
| ASIS | 4h | 4h | 242/245 | -2,643.70 | 2,130.40 | 3,464.60 | -8,238.60 | -8,796.90 | 22.84 | -10.92 | 56.20 | 0.72 | 0.44 | 0.40 |
| FINAL_H4 | 15m | 15m | 1124/1125 | 34,635.80 | 3,659.00 | 15,786.60 | 15,190.20 | 4,345.10 | 17.28 | 30.81 | 14.30 | 1.38 | 1.15 | 1.04 |
| FINAL_H4 | 30m | 30m | 593/593 | 16,146.40 | 1,580.40 | 8,335.80 | 6,230.20 | 891.50 | 16.72 | 27.23 | 10.00 | 1.21 | 1.07 | 1.01 |
| FINAL_H4 | 1h | 1h | 309/309 | 10,720.50 | 905.90 | 4,366.80 | 5,447.80 | 2,881.70 | 17.06 | 34.69 | 7.60 | 1.19 | 1.09 | 1.05 |
| FINAL_H4 | 2h | 2h | 187/187 | -1,967.50 | 762.60 | 2,665.50 | -5,395.60 | -6,936.30 | 18.33 | -10.52 | 7.40 | 0.96 | 0.89 | 0.86 |
| FINAL_H4 | 4h | 4h | 90/90 | -2,990.10 | 259.60 | 1,298.00 | -4,547.70 | -5,381.50 | 17.31 | -33.22 | 5.30 | 0.90 | 0.86 | 0.84 |

Slippage per side varied (B charges kept), net points:

| config | TF | slip 0.0 | slip 1.5 | slip 3.0 | slip 5.0 | slip 8.0 |
|---|---|---|---|---|---|---|
| ASIS | 1m | -259,977.00 | -316,655.00 | -373,335.00 | -449,062.00 | -564,325.00 |
| ASIS | 3m | -94,512.00 | -118,398.00 | -139,301.00 | -170,965.00 | -218,822.00 |
| ASIS | 5m | -65,088.00 | -78,273.00 | -90,812.00 | -111,199.00 | -142,279.00 |
| ASIS | 10m | -15,227.00 | -21,549.00 | -28,957.00 | -38,601.00 | -51,974.00 |
| ASIS | 15m | -1,031.00 | -5,002.00 | -12,269.00 | -17,411.00 | -25,807.00 |
| ASIS | 30m | -3,230.00 | -9,709.00 | -13,886.00 | -16,402.00 | -22,357.00 |
| ASIS | 1h | 3,973.00 | 4,206.00 | 292.00 | -1,975.00 | -5,348.00 |
| ASIS | 2h | -5,459.00 | -5,418.00 | -6,250.00 | -9,102.00 | -8,969.00 |
| FINAL_H4 | 1m | -231,035.00 | -286,667.00 | -342,136.00 | -414,475.00 | -525,145.00 |
| FINAL_H4 | 3m | -62,625.00 | -80,906.00 | -98,083.00 | -121,017.00 | -158,194.00 |
| FINAL_H4 | 5m | -23,731.00 | -34,786.00 | -43,802.00 | -58,450.00 | -80,931.00 |
| FINAL_H4 | 10m | 8,068.00 | 2,719.00 | -2,434.00 | -8,519.00 | -19,584.00 |
| FINAL_H4 | 15m | 18,458.00 | 15,190.00 | 12,199.00 | 8,086.00 | 1,396.00 |
| FINAL_H4 | 30m | 7,662.00 | 6,230.00 | 4,566.00 | 2,805.00 | -649.00 |
| FINAL_H4 | 1h | 6,323.00 | 5,448.00 | 4,834.00 | 3,437.00 | 2,601.00 |

## 7. Answers

1. **Does the original strategy work on NIFTY BANK?** No. AS-IS is negative on 1m-30m, 2h, 4h and D1 after costs; the 1h run is positive over the whole period only because of the 2024-25 validation year (+7,910) and loses the OOS year (-4,321).
2. **Most stable timeframe:** 15 minutes with the ATR-scaled exits (net +15,190 pts, PF 1.15, TRAIN 11,058 / VAL 2,165 / OOS 1,967, years 2022 +6,377, 2023 +5,369, 2024 +1,454, 2025 -2,248, 2026 +4,238). 1h FINAL_H4 passes the rule too but depends on five trades.
3. **Costs:** charges are 16-17 points per round trip plus 3 points of spread and slippage; the break-even cost per trade is 14-31 points for the positive timeframes, so costs consume 45-60% of the gross profit on 15m-30m. AS-IS 15m/30m are gross-positive (+27,300 / +13,200) and net-negative: the costs, not the signal, decide.
4. **Slippage:** FINAL_H4 15m keeps +8,086 pts at 5 points of slippage per side and +1,396 at 8; 30m turns negative at 8; AS-IS 1h turns negative at 5.
5. **Years:** 15m FINAL_H4 loses 2025; 30m loses 2024 and 2025; 1h loses 2024. Nothing is positive in every year.
6. **Regimes:** strong-bull sessions lose heavily (15m FINAL_H4: -5,981 pts on 270 trades), sideways and weak-bear sessions earn (+10,700 and +8,607); every volatility class earns; opening-phase entries lose, closing-phase entries earn the most per trade; Mondays lose 7,608 and Fridays earn 12,546.
7. **Out-of-sample:** FINAL_H4 15m +1,967, 30m +77, 1h +1,276; AS-IS all negative except 10m/15m by a few hundred points on thousands of trades.
8. **Parameter robustness:** 15m FINAL_H4 has 53 of 60 moving-average cells positive on TRAIN but only 16 also positive on VAL and OOS; the exit map is positive everywhere. Walk-forward re-optimisation loses to the fixed 18/200 on 15m (-338 vs +3,677 in the test months) and wins on 1h (+5,354 vs +2,065, 4 of 5 folds) - inconsistent.
9. **Setups worth further research:** 15m ATR-scaled exits with ADX(14) >= 20 (V02: +17,683 pts, PF 1.19, helpful in all splits, also the only filter helpful on both indices at 15m); the short side (V16: 507 short trades +9,147 pts, PF 1.17) given the loss in bull regimes; 30m with large-gap sessions skipped (V07: +8,924, PF 1.16, helpful in all splits).
10. **Genuine or overfitting?** The 15m result is the least concentrated finding of the study (net without the best five trades still +5,141 pts, t = 1.45) but its drawdown equals the capital per lot, its 2025 is negative, Friday carries it, and the confidence interval still includes zero. Not defensible yet.
11. **Conditions:** better in sideways and weak-bear 63-day regimes, on Fridays, in the closing phase, after large gaps in either direction; worse in strong-bull regimes, on Mondays, in the opening 30 minutes, and on every timeframe below 15 minutes.

## 8. Files
- backtests/banknifty/: every run's trade list (config_TF_scenario_trades.csv.gz)
- research/timeframe_analysis.md, cost_analysis.md, regime_analysis.md, robustness_analysis.md, walk_forward_analysis.md, variants_mtf_analysis.md, experiment_log.csv
