# Market-condition analysis (baseline trades, scenario B costs)

Tags are known before the trade: trend = 63-session return of the previous close (strong bull > +8%, weak bull +2..+8, sideways -2..+2, weak bear -8..-2, strong bear < -8); volatility = 20-session realised volatility of the previous close ranked over 2015-2026 (low < 25th pct, normal, high > 75th, extreme > 95th); gap = session open vs previous close (small < 0.25%, medium 0.25-0.75%, large > 0.75%); session phase = entry time (opening 09:15-09:44, morning 09:45-11:29, midday 11:30-13:29, afternoon 13:30-14:59, closing 15:00-15:29); consolidation = previous 5-session average range below its 60-session median. A 'failed breakout' is a losing trade whose best excursion never reached 0.3 R.

## 1. Instrument characteristics, 2022-2026 (why the two indices behave differently)

| metric | NIFTY 50 | NIFTY BANK |
|---|---|---|
| median daily range % | 0.86 | 1.10 |
| median ATR14 % | 1.04 | 1.31 |
| median |gap| % | 0.27 | 0.30 |
| days |gap| > 0.5% | 23.20 | 28.60 |
| days |gap| > 1% | 6.10 | 9.10 |
| first 15 min share of day range % | 40.90 | 43.70 |
| daily return autocorr lag1 | -0.03 | -0.04 |
| weekly return autocorr | 0.79 | 0.79 |
| variance ratio 5d | 0.98 | 0.99 |
| days breaking prev high % | 52.90 | 53.60 |
| of which close above (follow-through) % | 57.30 | 56.10 |
| days breaking prev low % | 47.40 | 47.80 |
| of which close below % | 56.10 | 51.50 |
| trend regime days: bull/side/bear | 601/245/328 | 625/236/313 |
| vol regime days: low/normal/high/extreme | 363/566/192/53 | 441/562/138/33 |

## NIFTY 50: ASIS


### 5m (3686 trades, net -17,493 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 635 | -3,569.54 | -5.62 | 22.05 | 0.72 | -0.15 |
| weak_bull | 1205 | -6,150.19 | -5.10 | 23.82 | 0.71 | -0.19 |
| sideways | 757 | -4,041.29 | -5.34 | 23.51 | 0.72 | -0.16 |
| weak_bear | 855 | -2,903.83 | -3.40 | 24.91 | 0.84 | -0.07 |
| strong_bear | 234 | -828.49 | -3.54 | 20.09 | 0.86 | -0.10 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 1146 | -5,191.29 | -4.53 | 23.82 | 0.74 | -0.14 |
| normal | 1734 | -10,323.00 | -5.95 | 24.11 | 0.70 | -0.18 |
| high | 610 | -717.90 | -1.18 | 22.46 | 0.94 | -0.05 |
| extreme | 196 | -1,261.16 | -6.43 | 18.88 | 0.74 | -0.14 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 382 | -2,492.23 | -6.52 | 29.06 | 0.71 | -0.10 |
| morning | 920 | -3,992.77 | -4.34 | 26.52 | 0.75 | -0.10 |
| midday | 1130 | -8,551.86 | -7.57 | 20.97 | 0.54 | -0.25 |
| afternoon | 940 | -1,401.03 | -1.49 | 18.62 | 0.92 | -0.11 |
| closing | 314 | -1,055.46 | -3.36 | 31.21 | 0.90 | -0.00 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 200 | -619.41 | -3.10 | 24.50 | 0.88 | -0.04 |
| large up | 180 | 519.79 | 2.89 | 27.22 | 1.13 | 0.14 |
| medium down | 501 | -1,782.44 | -3.56 | 22.75 | 0.82 | -0.14 |
| medium up | 981 | -5,491.06 | -5.60 | 22.73 | 0.71 | -0.16 |
| small down | 746 | -4,819.01 | -6.46 | 23.59 | 0.67 | -0.18 |
| small up | 1078 | -5,301.21 | -4.92 | 23.56 | 0.74 | -0.17 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 697 | -6,656.74 | -9.55 | 23.10 | 0.53 | -0.20 |
| Tue | 775 | -4,691.67 | -6.05 | 20.77 | 0.69 | -0.21 |
| Wed | 719 | -3,326.56 | -4.63 | 23.92 | 0.75 | -0.11 |
| Thu | 732 | -4,420.41 | -6.04 | 23.22 | 0.71 | -0.20 |
| Fri | 749 | 1,913.83 | 2.56 | 26.57 | 1.14 | 0.01 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 1660 | -8,573.91 | -5.17 | 23.43 | 0.73 | -0.15 |
| long above prev high | 1080 | -5,731.87 | -5.31 | 22.69 | 0.72 | -0.17 |
| short below prev low | 946 | -3,187.56 | -3.37 | 24.42 | 0.84 | -0.10 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 2014 | -3,783.58 | -1.88 | 26.17 | 0.89 | -0.10 |
| expansion | 1672 | -13,709.77 | -8.20 | 20.22 | 0.62 | -0.19 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 1436 | -51,106.17 | -35.59 | 0.00 | 0.00 | -0.74 |
| loss after progress | 1385 | -21,396.05 | -15.45 | 0.00 | 0.00 | -0.51 |
| small win | 517 | 12,723.32 | 24.61 | 100.00 | 1.27e+13 | 0.36 |
| win >= 1R | 348 | 42,285.56 | 121.51 | 100.00 | 4.23e+13 | 3.03 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 1722 | -8,882.40 |
| long | 1964 | -8,610.90 |


### 15m (1330 trades, net 1,643 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 248 | -1,669.66 | -6.73 | 19.76 | 0.73 | -0.10 |
| weak_bull | 436 | -1,779.40 | -4.08 | 20.87 | 0.83 | -0.05 |
| sideways | 262 | 794.86 | 3.03 | 21.76 | 1.12 | -0.03 |
| weak_bear | 304 | 2,931.43 | 9.64 | 22.04 | 1.37 | 0.13 |
| strong_bear | 80 | 1,365.32 | 17.07 | 22.50 | 1.77 | 0.26 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 406 | 1,520.99 | 3.75 | 22.41 | 1.18 | 0.09 |
| normal | 630 | -1,800.72 | -2.86 | 20.79 | 0.89 | -0.04 |
| high | 227 | 257.30 | 1.13 | 18.94 | 1.04 | -0.06 |
| extreme | 67 | 1,664.99 | 24.85 | 25.37 | 2.25 | 0.09 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 114 | 621.75 | 5.45 | 26.32 | 1.26 | 0.00 |
| morning | 408 | 584.12 | 1.43 | 23.04 | 1.06 | 0.02 |
| midday | 369 | -1,279.65 | -3.47 | 18.43 | 0.84 | -0.09 |
| afternoon | 322 | -251.38 | -0.78 | 15.53 | 0.97 | -0.04 |
| closing | 117 | 1,967.71 | 16.82 | 34.19 | 1.53 | 0.35 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 73 | 1,023.93 | 14.03 | 23.29 | 1.51 | 0.22 |
| large up | 66 | 1,901.22 | 28.81 | 27.27 | 2.94 | 0.19 |
| medium down | 186 | -1,097.33 | -5.90 | 16.67 | 0.79 | -0.10 |
| medium up | 323 | -651.30 | -2.02 | 21.98 | 0.93 | 0.03 |
| small down | 276 | 1,770.25 | 6.41 | 20.65 | 1.27 | 0.10 |
| small up | 406 | -1,304.22 | -3.21 | 21.67 | 0.86 | -0.10 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 256 | -881.16 | -3.44 | 17.97 | 0.87 | -0.01 |
| Tue | 277 | -460.09 | -1.66 | 19.49 | 0.93 | -0.09 |
| Wed | 274 | -785.81 | -2.87 | 21.53 | 0.89 | 0.03 |
| Thu | 263 | 1,470.71 | 5.59 | 22.05 | 1.23 | 0.02 |
| Fri | 257 | 2,303.77 | 8.96 | 24.90 | 1.39 | 0.09 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 694 | -259.56 | -0.37 | 19.60 | 0.99 | 0.00 |
| long above prev high | 330 | 1,645.68 | 4.99 | 24.24 | 1.22 | 0.03 |
| short below prev low | 306 | 256.44 | 0.84 | 21.57 | 1.03 | -0.03 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 726 | 4,087.35 | 5.63 | 23.55 | 1.25 | 0.08 |
| expansion | 604 | -2,444.80 | -4.05 | 18.38 | 0.85 | -0.09 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 587 | -25,358.78 | -43.20 | 0.00 | 0.00 | -0.52 |
| loss after progress | 461 | -7,685.32 | -16.67 | 0.00 | 0.00 | -0.31 |
| small win | 158 | 8,658.42 | 54.80 | 100.00 | 8.66e+12 | 0.39 |
| win >= 1R | 124 | 26,028.23 | 209.91 | 100.00 | 2.6e+13 | 3.16 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 634 | -219.30 |
| long | 696 | 1,861.90 |


### 30m (739 trades, net 2,628 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 122 | -1,501.10 | -12.30 | 17.21 | 0.66 | -0.11 |
| weak_bull | 251 | 11.45 | 0.05 | 19.52 | 1.00 | 0.03 |
| sideways | 146 | 1,029.03 | 7.05 | 16.44 | 1.23 | 0.01 |
| weak_bear | 177 | 3,641.29 | 20.57 | 19.21 | 1.76 | 0.18 |
| strong_bear | 43 | -552.62 | -12.85 | 13.95 | 0.73 | -0.04 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 224 | 2,407.09 | 10.75 | 22.32 | 1.42 | 0.10 |
| normal | 338 | -307.07 | -0.91 | 15.38 | 0.97 | 0.01 |
| high | 137 | 577.50 | 4.22 | 18.98 | 1.14 | 0.01 |
| extreme | 40 | -49.47 | -1.24 | 15.00 | 0.97 | -0.04 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 70 | -1,930.38 | -27.58 | 14.29 | 0.35 | -0.17 |
| morning | 225 | 616.54 | 2.74 | 14.67 | 1.10 | -0.02 |
| midday | 208 | 2,829.06 | 13.60 | 18.75 | 1.68 | 0.07 |
| afternoon | 157 | -797.21 | -5.08 | 19.11 | 0.88 | -0.04 |
| closing | 79 | 1,910.03 | 24.18 | 27.85 | 1.65 | 0.44 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 44 | -1,014.88 | -23.07 | 13.64 | 0.63 | 0.00 |
| large up | 32 | 838.77 | 26.21 | 25.00 | 2.64 | 0.23 |
| medium down | 88 | 837.79 | 9.52 | 17.05 | 1.33 | 0.03 |
| medium up | 174 | -889.51 | -5.11 | 17.24 | 0.84 | -0.01 |
| small down | 166 | 1,940.30 | 11.69 | 19.88 | 1.36 | 0.09 |
| small up | 235 | 915.58 | 3.90 | 17.87 | 1.15 | 0.02 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 126 | -254.57 | -2.02 | 19.84 | 0.94 | 0.08 |
| Tue | 145 | -2,762.68 | -19.05 | 10.34 | 0.46 | -0.18 |
| Wed | 148 | 889.59 | 6.01 | 18.24 | 1.20 | 0.05 |
| Thu | 169 | 795.04 | 4.70 | 21.30 | 1.14 | 0.12 |
| Fri | 147 | 3,990.01 | 27.14 | 21.09 | 2.27 | 0.10 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 358 | 1,606.59 | 4.49 | 16.76 | 1.15 | 0.01 |
| long above prev high | 201 | -326.33 | -1.62 | 19.40 | 0.95 | 0.05 |
| short below prev low | 180 | 1,347.78 | 7.49 | 19.44 | 1.23 | 0.09 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 410 | 5,717.66 | 13.95 | 21.22 | 1.56 | 0.13 |
| expansion | 329 | -3,089.62 | -9.39 | 14.29 | 0.76 | -0.07 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 374 | -17,875.96 | -47.80 | 0.00 | 0.00 | -0.36 |
| loss after progress | 231 | -5,057.06 | -21.89 | 0.00 | 0.00 | -0.27 |
| small win | 74 | 5,592.78 | 75.58 | 100.00 | 5.59e+12 | 0.44 |
| win >= 1R | 60 | 19,968.28 | 332.80 | 100.00 | 2e+13 | 3.18 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 350 | -608.40 |
| long | 389 | 3,236.40 |


### 1h (418 trades, net 3,332 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 70 | 419.64 | 5.99 | 15.71 | 1.17 | 0.01 |
| weak_bull | 150 | 790.13 | 5.27 | 18.67 | 1.16 | 0.11 |
| sideways | 78 | 1,626.27 | 20.85 | 16.67 | 1.75 | 0.16 |
| weak_bear | 103 | 864.75 | 8.40 | 12.62 | 1.23 | 0.09 |
| strong_bear | 17 | -368.67 | -21.69 | 11.76 | 0.60 | -0.15 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 135 | 2,886.13 | 21.38 | 23.70 | 1.72 | 0.21 |
| normal | 191 | 295.83 | 1.55 | 13.61 | 1.05 | 0.02 |
| high | 71 | -619.29 | -8.72 | 7.04 | 0.78 | 0.00 |
| extreme | 21 | 769.45 | 36.64 | 19.05 | 1.85 | 0.24 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 74 | 846.10 | 11.43 | 16.22 | 1.38 | 0.05 |
| morning | 98 | 1,490.57 | 15.21 | 18.37 | 1.45 | 0.06 |
| midday | 126 | 1,902.66 | 15.10 | 14.29 | 1.52 | 0.17 |
| afternoon | 81 | -1,623.27 | -20.04 | 11.11 | 0.49 | -0.06 |
| closing | 39 | 716.05 | 18.36 | 25.64 | 1.37 | 0.26 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 31 | -1,363.52 | -43.98 | 6.45 | 0.22 | -0.09 |
| large up | 19 | 80.34 | 4.23 | 15.79 | 1.22 | -0.14 |
| medium down | 34 | -1,379.90 | -40.59 | 2.94 | 0.14 | -0.21 |
| medium up | 111 | 2,035.92 | 18.34 | 20.72 | 1.50 | 0.31 |
| small down | 100 | 3,526.25 | 35.26 | 19.00 | 2.24 | 0.18 |
| small up | 123 | 433.01 | 3.52 | 15.45 | 1.12 | -0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 81 | -380.37 | -4.70 | 12.35 | 0.85 | -0.00 |
| Tue | 67 | 1,404.23 | 20.96 | 20.90 | 1.48 | 0.38 |
| Wed | 88 | 690.83 | 7.85 | 14.77 | 1.27 | 0.01 |
| Thu | 96 | 118.91 | 1.24 | 15.62 | 1.03 | 0.07 |
| Fri | 86 | 1,498.52 | 17.42 | 17.44 | 1.69 | 0.03 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 141 | 2,685.69 | 19.05 | 16.31 | 1.63 | 0.16 |
| long above prev high | 152 | 1,423.30 | 9.36 | 19.74 | 1.29 | 0.10 |
| short below prev low | 125 | -776.87 | -6.21 | 11.20 | 0.85 | -0.01 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 245 | 4,333.78 | 17.69 | 18.37 | 1.59 | 0.18 |
| expansion | 173 | -1,001.66 | -5.79 | 12.72 | 0.86 | -0.05 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 232 | -12,292.65 | -52.99 | 0.00 | 0.00 | -0.27 |
| loss after progress | 119 | -1,994.26 | -16.76 | 0.00 | 0.00 | -0.16 |
| small win | 33 | 3,470.87 | 105.18 | 100.00 | 3.47e+12 | 0.45 |
| win >= 1R | 34 | 14,148.15 | 416.12 | 100.00 | 1.41e+13 | 3.05 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 189 | -1,073.80 |
| long | 229 | 4,405.90 |


### 2h (262 trades, net 3,092 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 43 | 15.10 | 0.35 | 16.28 | 1.01 | -0.07 |
| weak_bull | 96 | 915.41 | 9.54 | 17.71 | 1.31 | 0.12 |
| sideways | 63 | 1,536.30 | 24.39 | 20.63 | 2.03 | 0.11 |
| weak_bear | 50 | 994.50 | 19.89 | 16.00 | 1.33 | 0.26 |
| strong_bear | 10 | -369.29 | -36.93 | 0.00 | 0.00 | -0.14 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 93 | 2,354.39 | 25.32 | 21.51 | 2.01 | 0.16 |
| normal | 124 | -2,324.82 | -18.75 | 12.90 | 0.62 | -0.02 |
| high | 39 | 2,062.27 | 52.88 | 15.38 | 3.59 | 0.29 |
| extreme | 6 | 1,000.19 | 166.70 | 50.00 | 50.97 | 0.45 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 84 | 737.04 | 8.77 | 15.48 | 1.21 | 0.06 |
| morning | 35 | -335.64 | -9.59 | 22.86 | 0.83 | 0.12 |
| midday | 58 | 1,875.58 | 32.34 | 18.97 | 2.80 | 0.12 |
| afternoon | 54 | 860.54 | 15.94 | 11.11 | 1.57 | 0.18 |
| closing | 31 | -45.50 | -1.47 | 22.58 | 0.96 | 0.04 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 16 | -468.73 | -29.30 | 6.25 | 0.02 | -0.14 |
| large up | 19 | -211.82 | -11.15 | 15.79 | 0.54 | 0.01 |
| medium down | 21 | -339.51 | -16.17 | 4.76 | 0.34 | -0.08 |
| medium up | 75 | 2,986.86 | 39.82 | 21.33 | 2.32 | 0.28 |
| small down | 56 | 547.20 | 9.77 | 14.29 | 1.15 | 0.18 |
| small up | 75 | 578.02 | 7.71 | 21.33 | 1.29 | -0.01 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 55 | -1,746.46 | -31.75 | 18.18 | 0.49 | -0.02 |
| Tue | 46 | 2,644.51 | 57.49 | 26.09 | 3.36 | 0.34 |
| Wed | 46 | -373.41 | -8.12 | 13.04 | 0.80 | -0.04 |
| Thu | 57 | 449.23 | 7.88 | 15.79 | 1.28 | 0.03 |
| Fri | 57 | 2,125.33 | 37.29 | 14.04 | 2.62 | 0.21 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 53 | -1,429.78 | -26.98 | 16.98 | 0.49 | -0.02 |
| long above prev high | 138 | 2,711.80 | 19.65 | 18.12 | 1.65 | 0.12 |
| short below prev low | 71 | 1,810.02 | 25.49 | 15.49 | 1.79 | 0.15 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 163 | 3,820.61 | 23.44 | 21.47 | 1.86 | 0.13 |
| expansion | 99 | -728.58 | -7.36 | 10.10 | 0.85 | 0.05 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 161 | -8,332.99 | -51.76 | 0.00 | 0.00 | -0.18 |
| loss after progress | 56 | -945.82 | -16.89 | 0.00 | 0.00 | -0.10 |
| small win | 29 | 3,731.74 | 128.68 | 100.00 | 3.73e+12 | 0.41 |
| win >= 1R | 16 | 8,639.10 | 539.94 | 100.00 | 8.64e+12 | 3.06 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 98 | 180.20 |
| long | 164 | 2,911.80 |


### 4h (139 trades, net 4,035 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 35 | -788.73 | -22.54 | 17.14 | 0.68 | -0.07 |
| weak_bull | 55 | 1,711.56 | 31.12 | 16.36 | 1.84 | 0.25 |
| sideways | 21 | 846.24 | 40.30 | 19.05 | 2.58 | 0.03 |
| weak_bear | 24 | 2,290.26 | 95.43 | 16.67 | 3.43 | 0.24 |
| strong_bear | 4 | -24.68 | -6.17 | 0.00 | 0.00 | -0.01 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 51 | 840.77 | 16.49 | 15.69 | 1.46 | 0.22 |
| normal | 69 | -1,238.91 | -17.96 | 13.04 | 0.69 | -0.05 |
| high | 14 | 3,512.58 | 250.90 | 28.57 | 52.21 | 0.61 |
| extreme | 5 | 920.22 | 184.04 | 40.00 | 46.57 | 0.25 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 53 | -309.97 | -5.85 | 7.55 | 0.89 | -0.09 |
| morning | 21 | -402.86 | -19.18 | 14.29 | 0.68 | -0.03 |
| midday | 22 | 1,356.29 | 61.65 | 27.27 | 3.73 | 0.17 |
| afternoon | 30 | 678.70 | 22.62 | 16.67 | 1.54 | 0.27 |
| closing | 13 | 2,712.49 | 208.65 | 38.46 | 12.83 | 0.87 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 6 | -296.13 | -49.35 | 0.00 | 0.00 | -0.10 |
| large up | 2 | 440.40 | 220.20 | 50.00 | 61.69 | 0.31 |
| medium down | 13 | 518.82 | 39.91 | 7.69 | 7.35 | 0.07 |
| medium up | 47 | 241.25 | 5.13 | 14.89 | 1.11 | 0.10 |
| small down | 21 | 2,683.63 | 127.79 | 23.81 | 5.20 | 0.34 |
| small up | 50 | 446.68 | 8.93 | 18.00 | 1.17 | 0.09 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 32 | -260.44 | -8.14 | 6.25 | 0.77 | -0.06 |
| Tue | 28 | 2,739.15 | 97.83 | 25.00 | 5.49 | 0.45 |
| Wed | 22 | -792.03 | -36.00 | 18.18 | 0.66 | 0.15 |
| Thu | 30 | -40.30 | -1.34 | 13.33 | 0.97 | -0.01 |
| Fri | 27 | 2,388.27 | 88.45 | 22.22 | 4.30 | 0.16 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 23 | 1,476.71 | 64.20 | 26.09 | 3.71 | 0.26 |
| long above prev high | 82 | -547.11 | -6.67 | 13.41 | 0.88 | 0.06 |
| short below prev low | 34 | 3,105.05 | 91.32 | 17.65 | 4.04 | 0.21 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 84 | 2,037.17 | 24.25 | 17.86 | 1.56 | 0.17 |
| expansion | 55 | 1,997.48 | 36.32 | 14.55 | 1.86 | 0.06 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 95 | -5,808.87 | -61.15 | 0.00 | 0.00 | -0.18 |
| loss after progress | 21 | -167.12 | -7.96 | 0.00 | 0.00 | -0.03 |
| small win | 15 | 3,893.66 | 259.58 | 100.00 | 3.89e+12 | 0.59 |
| win >= 1R | 8 | 6,116.97 | 764.62 | 100.00 | 6.12e+12 | 3.31 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 39 | 2,987.60 |
| long | 100 | 1,047.00 |


### D1 (80 trades, net -2,757 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 18 | -1,056.26 | -58.68 | 11.11 | 0.31 | -0.14 |
| weak_bull | 37 | -1,046.29 | -28.28 | 5.41 | 0.44 | -0.05 |
| sideways | 11 | 283.86 | 25.81 | 9.09 | 1.17 | 0.09 |
| weak_bear | 9 | -904.83 | -100.54 | 11.11 | 0.06 | -0.10 |
| strong_bear | 5 | -33.21 | -6.64 | 0.00 | 0.00 | -0.00 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 33 | -721.67 | -21.87 | 6.06 | 0.53 | -0.05 |
| normal | 35 | -2,166.01 | -61.89 | 5.71 | 0.49 | -0.08 |
| high | 6 | -239.07 | -39.85 | 16.67 | 0.25 | -0.07 |
| extreme | 6 | 370.01 | 61.67 | 16.67 | 11.97 | 0.02 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 4 | -931.72 | -232.93 | 0.00 | 0.00 | -0.23 |
| large up | 3 | -1,303.82 | -434.61 | 0.00 | 0.00 | -0.34 |
| medium down | 4 | -25.73 | -6.43 | 0.00 | 0.00 | -0.01 |
| medium up | 26 | -1,977.80 | -76.07 | 3.85 | 0.10 | -0.15 |
| small down | 21 | 2,254.76 | 107.37 | 19.05 | 5.76 | 0.16 |
| small up | 22 | -772.42 | -35.11 | 4.55 | 0.34 | -0.08 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 20 | -942.83 | -47.14 | 5.00 | 0.68 | -0.01 |
| Tue | 10 | 225.68 | 22.57 | 10.00 | 1.62 | -0.00 |
| Wed | 19 | -1,119.63 | -58.93 | 10.53 | 0.30 | -0.13 |
| Thu | 13 | -161.73 | -12.44 | 0.00 | 0.00 | -0.02 |
| Fri | 18 | -758.24 | -42.12 | 11.11 | 0.27 | -0.08 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 1 | 2,003.80 | 2,003.80 | 100.00 | 2e+12 | 3.09 |
| long above prev high | 63 | -4,404.78 | -69.92 | 4.76 | 0.14 | -0.12 |
| short below prev low | 16 | -355.75 | -22.23 | 12.50 | 0.64 | -0.00 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 48 | -798.30 | -16.63 | 10.42 | 0.79 | -0.01 |
| expansion | 32 | -1,958.44 | -61.20 | 3.12 | 0.17 | -0.12 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 65 | -5,598.53 | -86.13 | 0.00 | 0.00 | -0.13 |
| loss after progress | 9 | -509.38 | -56.60 | 0.00 | 0.00 | -0.15 |
| small win | 5 | 1,347.38 | 269.48 | 100.00 | 1.35e+12 | 0.44 |
| win >= 1R | 1 | 2,003.80 | 2,003.80 | 100.00 | 2e+12 | 3.09 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 16 | -355.80 |
| long | 64 | -2,401.00 |


## NIFTY 50: FINAL_H4


### 5m (3669 trades, net -13,350 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 669 | -3,374.23 | -5.04 | 23.77 | 0.76 | -0.12 |
| weak_bull | 1212 | -5,152.49 | -4.25 | 26.98 | 0.79 | -0.14 |
| sideways | 752 | -3,025.84 | -4.02 | 28.32 | 0.81 | -0.14 |
| weak_bear | 825 | -1,378.75 | -1.67 | 30.06 | 0.93 | -0.04 |
| strong_bear | 211 | -418.49 | -1.98 | 26.07 | 0.94 | -0.00 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 1188 | -5,527.11 | -4.65 | 26.35 | 0.75 | -0.12 |
| normal | 1738 | -8,281.15 | -4.76 | 27.56 | 0.79 | -0.13 |
| high | 573 | 984.37 | 1.72 | 28.80 | 1.07 | -0.00 |
| extreme | 170 | -525.92 | -3.09 | 26.47 | 0.89 | -0.06 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 439 | -3,248.20 | -7.40 | 35.76 | 0.71 | -0.10 |
| morning | 844 | -2,948.88 | -3.49 | 31.16 | 0.82 | -0.05 |
| midday | 1093 | -4,865.20 | -4.45 | 24.79 | 0.75 | -0.18 |
| afternoon | 954 | -83.78 | -0.09 | 20.55 | 1.00 | -0.08 |
| closing | 339 | -2,203.76 | -6.50 | 33.92 | 0.84 | -0.08 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 201 | -325.54 | -1.62 | 26.37 | 0.95 | 0.03 |
| large up | 182 | 1,052.73 | 5.78 | 31.87 | 1.25 | 0.12 |
| medium down | 487 | -163.40 | -0.34 | 28.34 | 0.99 | -0.08 |
| medium up | 1002 | -4,374.79 | -4.37 | 27.15 | 0.80 | -0.10 |
| small down | 736 | -5,222.34 | -7.10 | 25.41 | 0.67 | -0.19 |
| small up | 1061 | -4,316.45 | -4.07 | 27.71 | 0.80 | -0.13 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 696 | -4,937.21 | -7.09 | 28.02 | 0.70 | -0.14 |
| Tue | 755 | -3,717.38 | -4.92 | 25.70 | 0.78 | -0.16 |
| Wed | 702 | -2,421.42 | -3.45 | 28.21 | 0.83 | -0.06 |
| Thu | 755 | -3,374.11 | -4.47 | 26.23 | 0.81 | -0.15 |
| Fri | 748 | 1,309.64 | 1.75 | 28.74 | 1.08 | -0.00 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 1567 | -7,647.68 | -4.88 | 25.78 | 0.77 | -0.14 |
| long above prev high | 1135 | -2,977.53 | -2.62 | 28.11 | 0.87 | -0.10 |
| short below prev low | 967 | -2,724.60 | -2.82 | 28.85 | 0.89 | -0.06 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 2079 | -1,654.17 | -0.80 | 29.10 | 0.96 | -0.07 |
| expansion | 1590 | -11,695.64 | -7.36 | 24.97 | 0.71 | -0.16 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 1431 | -55,849.39 | -39.03 | 0.00 | 0.00 | -0.74 |
| loss after progress | 1236 | -26,041.72 | -21.07 | 0.00 | 0.00 | -0.57 |
| small win | 541 | 17,232.89 | 31.85 | 100.00 | 1.72e+13 | 0.37 |
| win >= 1R | 461 | 51,308.41 | 111.30 | 100.00 | 5.13e+13 | 2.54 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 1693 | -6,623.60 |
| long | 1976 | -6,726.20 |


### 15m (1158 trades, net 4,285 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 215 | -1,624.12 | -7.55 | 26.98 | 0.80 | -0.07 |
| weak_bull | 382 | -560.51 | -1.47 | 31.15 | 0.95 | 0.01 |
| sideways | 232 | 301.39 | 1.30 | 28.02 | 1.03 | -0.01 |
| weak_bear | 262 | 3,852.44 | 14.70 | 32.82 | 1.36 | 0.08 |
| strong_bear | 67 | 2,315.89 | 34.57 | 32.84 | 1.89 | 0.47 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 381 | 1,692.78 | 4.44 | 32.02 | 1.15 | 0.07 |
| normal | 534 | 101.55 | 0.19 | 29.40 | 1.00 | -0.00 |
| high | 187 | 517.65 | 2.77 | 27.27 | 1.06 | -0.05 |
| extreme | 56 | 1,973.10 | 35.23 | 35.71 | 2.17 | 0.36 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 117 | -728.61 | -6.23 | 30.77 | 0.84 | -0.06 |
| morning | 386 | 2,001.17 | 5.18 | 32.90 | 1.15 | 0.02 |
| midday | 307 | -891.60 | -2.90 | 24.10 | 0.92 | -0.04 |
| afternoon | 247 | 1,058.54 | 4.29 | 26.72 | 1.10 | 0.03 |
| closing | 101 | 2,845.57 | 28.17 | 46.53 | 1.77 | 0.45 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 65 | 367.65 | 5.66 | 30.77 | 1.10 | 0.13 |
| large up | 57 | 2,490.97 | 43.70 | 45.61 | 2.67 | 0.47 |
| medium down | 160 | 530.92 | 3.32 | 26.25 | 1.07 | -0.07 |
| medium up | 290 | 441.46 | 1.52 | 30.69 | 1.04 | 0.13 |
| small down | 236 | 811.59 | 3.44 | 30.93 | 1.10 | 0.00 |
| small up | 350 | -357.51 | -1.02 | 28.57 | 0.97 | -0.07 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 223 | -1,867.42 | -8.37 | 27.35 | 0.79 | -0.07 |
| Tue | 245 | -2,224.33 | -9.08 | 23.67 | 0.77 | -0.12 |
| Wed | 237 | 1,187.14 | 5.01 | 34.60 | 1.15 | 0.09 |
| Thu | 236 | 1,878.91 | 7.96 | 32.20 | 1.22 | 0.10 |
| Fri | 214 | 5,487.00 | 25.64 | 33.64 | 1.74 | 0.18 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 592 | 2,680.83 | 4.53 | 28.72 | 1.13 | 0.01 |
| long above prev high | 306 | 385.09 | 1.26 | 31.05 | 1.04 | 0.06 |
| short below prev low | 260 | 1,219.16 | 4.69 | 32.69 | 1.10 | 0.05 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 663 | 2,882.20 | 4.35 | 31.83 | 1.13 | 0.05 |
| expansion | 495 | 1,402.88 | 2.83 | 28.08 | 1.07 | 0.01 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 439 | -28,592.84 | -65.13 | 0.00 | 0.00 | -0.61 |
| loss after progress | 369 | -13,735.84 | -37.22 | 0.00 | 0.00 | -0.52 |
| small win | 175 | 11,188.16 | 63.93 | 100.00 | 1.12e+13 | 0.40 |
| win >= 1R | 175 | 35,425.59 | 202.43 | 100.00 | 3.54e+13 | 2.45 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 519 | 2,659.90 |
| long | 639 | 1,625.20 |


### 30m (599 trades, net 5,118 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 102 | -2,421.36 | -23.74 | 29.41 | 0.58 | -0.16 |
| weak_bull | 203 | 464.71 | 2.29 | 31.03 | 1.06 | 0.01 |
| sideways | 118 | 2,389.78 | 20.25 | 33.90 | 1.47 | 0.03 |
| weak_bear | 146 | 4,529.62 | 31.02 | 34.25 | 1.56 | 0.23 |
| strong_bear | 30 | 155.24 | 5.17 | 26.67 | 1.07 | 0.04 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 191 | 3,015.22 | 15.79 | 34.55 | 1.43 | 0.07 |
| normal | 283 | 1,150.98 | 4.07 | 28.98 | 1.08 | -0.01 |
| high | 97 | 296.48 | 3.06 | 34.02 | 1.05 | 0.06 |
| extreme | 28 | 655.31 | 23.40 | 35.71 | 1.36 | 0.29 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 44 | -5.36 | -0.12 | 29.55 | 1.00 | -0.04 |
| morning | 200 | 621.48 | 3.11 | 32.00 | 1.06 | 0.03 |
| midday | 181 | 3,881.07 | 21.44 | 33.70 | 1.54 | 0.15 |
| afternoon | 119 | 184.07 | 1.55 | 29.41 | 1.03 | -0.08 |
| closing | 55 | 436.73 | 7.94 | 32.73 | 1.16 | 0.02 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 39 | -3,219.05 | -82.54 | 17.95 | 0.32 | -0.20 |
| large up | 28 | 2,186.28 | 78.08 | 50.00 | 3.16 | 0.53 |
| medium down | 75 | 1,840.70 | 24.54 | 29.33 | 1.47 | 0.03 |
| medium up | 147 | -564.31 | -3.84 | 31.29 | 0.92 | -0.03 |
| small down | 131 | 2,911.35 | 22.22 | 37.40 | 1.52 | 0.06 |
| small up | 179 | 1,963.01 | 10.97 | 29.61 | 1.28 | 0.06 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 101 | -846.81 | -8.38 | 34.65 | 0.85 | 0.04 |
| Tue | 117 | -3,247.10 | -27.75 | 25.64 | 0.49 | -0.24 |
| Wed | 126 | 687.57 | 5.46 | 27.78 | 1.12 | 0.01 |
| Thu | 137 | 1,089.24 | 7.95 | 32.12 | 1.15 | 0.03 |
| Fri | 115 | 7,034.68 | 61.17 | 40.00 | 2.53 | 0.37 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 308 | 1,036.36 | 3.36 | 27.60 | 1.07 | -0.03 |
| long above prev high | 152 | 2,943.02 | 19.36 | 43.42 | 1.48 | 0.14 |
| short below prev low | 139 | 1,138.61 | 8.19 | 28.78 | 1.12 | 0.07 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 336 | 5,781.77 | 17.21 | 36.31 | 1.46 | 0.11 |
| expansion | 263 | -663.79 | -2.52 | 26.24 | 0.96 | -0.05 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 216 | -20,535.15 | -95.07 | 0.00 | 0.00 | -0.60 |
| loss after progress | 192 | -9,020.42 | -46.98 | 0.00 | 0.00 | -0.49 |
| small win | 97 | 8,052.66 | 83.02 | 100.00 | 8.05e+12 | 0.40 |
| win >= 1R | 94 | 26,620.90 | 283.20 | 100.00 | 2.66e+13 | 2.22 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 281 | 632.50 |
| long | 318 | 4,485.50 |


### 1h (315 trades, net 1,930 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 56 | -871.34 | -15.56 | 28.57 | 0.79 | -0.13 |
| weak_bull | 115 | 1,116.93 | 9.71 | 33.91 | 1.17 | 0.09 |
| sideways | 62 | 356.09 | 5.74 | 32.26 | 1.08 | 0.20 |
| weak_bear | 68 | 1,483.87 | 21.82 | 30.88 | 1.28 | 0.14 |
| strong_bear | 14 | -155.38 | -11.10 | 21.43 | 0.88 | -0.49 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 108 | 2,694.98 | 24.95 | 38.89 | 1.52 | 0.17 |
| normal | 145 | -874.79 | -6.03 | 25.52 | 0.92 | 0.01 |
| high | 47 | -359.13 | -7.64 | 29.79 | 0.92 | -0.12 |
| extreme | 15 | 469.11 | 31.27 | 40.00 | 1.31 | 0.33 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 47 | 212.43 | 4.52 | 29.79 | 1.07 | 0.14 |
| morning | 80 | 1,548.07 | 19.35 | 36.25 | 1.32 | 0.15 |
| midday | 110 | 717.12 | 6.52 | 30.91 | 1.09 | 0.03 |
| afternoon | 53 | -2,578.97 | -48.66 | 18.87 | 0.45 | -0.20 |
| closing | 25 | 2,031.51 | 81.26 | 48.00 | 2.42 | 0.31 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 18 | -1,627.19 | -90.40 | 11.11 | 0.30 | -0.26 |
| large up | 16 | 1,082.78 | 67.67 | 50.00 | 1.89 | 0.03 |
| medium down | 31 | -1,364.53 | -44.02 | 22.58 | 0.50 | -0.10 |
| medium up | 90 | -313.34 | -3.48 | 30.00 | 0.95 | 0.06 |
| small down | 69 | 2,714.08 | 39.33 | 37.68 | 1.66 | 0.21 |
| small up | 91 | 1,438.37 | 15.81 | 31.87 | 1.26 | 0.07 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 68 | -2,008.30 | -29.53 | 25.00 | 0.64 | -0.07 |
| Tue | 57 | 721.30 | 12.65 | 35.09 | 1.21 | 0.15 |
| Wed | 62 | 815.08 | 13.15 | 29.03 | 1.19 | -0.03 |
| Thu | 69 | 623.81 | 9.04 | 31.88 | 1.13 | 0.10 |
| Fri | 59 | 1,778.28 | 30.14 | 37.29 | 1.48 | 0.15 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 119 | 2,979.71 | 25.04 | 31.93 | 1.47 | 0.11 |
| long above prev high | 119 | -901.62 | -7.58 | 33.61 | 0.90 | 0.03 |
| short below prev low | 77 | -147.92 | -1.92 | 27.27 | 0.98 | 0.03 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 183 | 1,641.00 | 8.97 | 35.52 | 1.14 | 0.11 |
| expansion | 132 | 289.17 | 2.19 | 25.76 | 1.03 | -0.00 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 105 | -15,228.09 | -145.03 | 0.00 | 0.00 | -0.57 |
| loss after progress | 111 | -6,699.59 | -60.36 | 0.00 | 0.00 | -0.44 |
| small win | 48 | 5,774.31 | 120.30 | 100.00 | 5.77e+12 | 0.41 |
| win >= 1R | 51 | 18,083.53 | 354.58 | 100.00 | 1.81e+13 | 2.13 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 133 | 694.70 |
| long | 182 | 1,235.40 |


### 2h (174 trades, net 3,627 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 23 | 496.62 | 21.59 | 39.13 | 1.38 | -0.02 |
| weak_bull | 61 | 2,709.44 | 44.42 | 39.34 | 1.70 | 0.25 |
| sideways | 48 | 129.05 | 2.69 | 35.42 | 1.03 | 0.03 |
| weak_bear | 37 | 725.85 | 19.62 | 37.84 | 1.15 | 0.18 |
| strong_bear | 5 | -434.01 | -86.80 | 0.00 | 0.00 | -0.33 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 68 | 1,880.54 | 27.65 | 39.71 | 1.36 | 0.16 |
| normal | 81 | -341.68 | -4.22 | 30.86 | 0.96 | 0.05 |
| high | 21 | 921.16 | 43.86 | 38.10 | 1.41 | 0.16 |
| extreme | 4 | 1,166.92 | 291.73 | 100.00 | 1.17e+12 | 0.65 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 46 | 1,682.22 | 36.57 | 39.13 | 1.47 | 0.04 |
| morning | 14 | 2,968.08 | 212.01 | 78.57 | 8.04 | 0.68 |
| midday | 47 | 682.35 | 14.52 | 27.66 | 1.17 | 0.13 |
| afternoon | 44 | -525.32 | -11.94 | 27.27 | 0.88 | 0.11 |
| closing | 23 | -1,180.40 | -51.32 | 43.48 | 0.64 | -0.05 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 9 | 271.53 | 30.17 | 44.44 | 1.29 | 0.07 |
| large up | 13 | 34.84 | 2.68 | 38.46 | 1.03 | 0.01 |
| medium down | 13 | -1,227.22 | -94.40 | 23.08 | 0.32 | -0.24 |
| medium up | 52 | 2,952.32 | 56.78 | 42.31 | 1.79 | 0.33 |
| small down | 37 | 1,728.57 | 46.72 | 35.14 | 1.57 | 0.18 |
| small up | 50 | -133.10 | -2.66 | 34.00 | 0.97 | -0.00 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 37 | 893.57 | 24.15 | 35.14 | 1.29 | 0.11 |
| Tue | 39 | 860.10 | 22.05 | 35.90 | 1.26 | 0.13 |
| Wed | 27 | 875.35 | 32.42 | 37.04 | 1.41 | 0.15 |
| Thu | 34 | 1,336.41 | 39.31 | 41.18 | 1.48 | 0.15 |
| Fri | 36 | 1,130.43 | 31.40 | 36.11 | 1.37 | 0.15 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 30 | 1,792.66 | 59.76 | 36.67 | 2.01 | 0.22 |
| long above prev high | 91 | 2,655.60 | 29.18 | 39.56 | 1.40 | 0.13 |
| short below prev low | 53 | -821.32 | -15.50 | 32.08 | 0.89 | 0.06 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 107 | 4,479.93 | 41.87 | 42.99 | 1.56 | 0.18 |
| expansion | 67 | -852.98 | -12.73 | 26.87 | 0.89 | 0.03 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 59 | -12,172.12 | -206.31 | 0.00 | 0.00 | -0.59 |
| loss after progress | 51 | -3,527.73 | -69.17 | 0.00 | 0.00 | -0.31 |
| small win | 34 | 6,135.43 | 180.45 | 100.00 | 6.14e+12 | 0.41 |
| win >= 1R | 30 | 13,191.36 | 439.71 | 100.00 | 1.32e+13 | 1.93 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 70 | -127.10 |
| long | 104 | 3,754.00 |


### 4h (79 trades, net 3,989 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 17 | -604.45 | -35.56 | 41.18 | 0.78 | -0.17 |
| weak_bull | 26 | -27.35 | -1.05 | 34.62 | 0.99 | 0.05 |
| sideways | 15 | 3,522.56 | 234.84 | 46.67 | 4.48 | 0.36 |
| weak_bear | 16 | 2,470.67 | 154.42 | 50.00 | 1.76 | 0.60 |
| strong_bear | 5 | -1,372.31 | -274.46 | 20.00 | 0.00 | -0.42 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 27 | 928.84 | 34.40 | 37.04 | 1.35 | 0.09 |
| normal | 40 | 874.13 | 21.85 | 42.50 | 1.14 | 0.09 |
| high | 11 | 395.29 | 35.94 | 36.36 | 1.17 | 0.35 |
| extreme | 1 | 1,790.85 | 1,790.85 | 100.00 | 1.79e+12 | 1.13 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 29 | 3,868.69 | 133.40 | 37.93 | 1.95 | 0.29 |
| morning | 15 | -662.12 | -44.14 | 40.00 | 0.75 | -0.01 |
| midday | 13 | 1,040.10 | 80.01 | 46.15 | 1.90 | 0.15 |
| afternoon | 16 | -423.65 | -26.48 | 43.75 | 0.83 | 0.14 |
| closing | 6 | 166.10 | 27.68 | 33.33 | 1.26 | -0.21 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 3 | 837.72 | 279.24 | 33.33 | 2.98 | 0.29 |
| large up | 5 | 1,443.92 | 288.78 | 60.00 | 132.78 | 0.42 |
| medium down | 10 | -497.75 | -49.78 | 20.00 | 0.79 | 0.47 |
| medium up | 21 | 1,010.17 | 48.10 | 47.62 | 1.44 | 0.16 |
| small down | 14 | -137.75 | -9.84 | 50.00 | 0.95 | 0.08 |
| small up | 26 | 1,332.81 | 51.26 | 34.62 | 1.41 | -0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 20 | 978.22 | 48.91 | 50.00 | 1.26 | 0.17 |
| Tue | 18 | 925.04 | 51.39 | 38.89 | 1.42 | 0.13 |
| Wed | 8 | 654.65 | 81.83 | 50.00 | 1.81 | 0.19 |
| Thu | 18 | -1,381.04 | -76.72 | 22.22 | 0.33 | -0.16 |
| Fri | 15 | 2,812.25 | 187.48 | 46.67 | 2.27 | 0.45 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 16 | 1,085.47 | 67.84 | 37.50 | 1.36 | 0.06 |
| long above prev high | 41 | 305.48 | 7.45 | 41.46 | 1.06 | 0.02 |
| short below prev low | 22 | 2,598.17 | 118.10 | 40.91 | 1.83 | 0.42 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 44 | 2,512.97 | 57.11 | 45.45 | 1.54 | 0.14 |
| expansion | 35 | 1,476.15 | 42.18 | 34.29 | 1.23 | 0.15 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 30 | -9,533.29 | -317.78 | 0.00 | 0.00 | -0.61 |
| loss after progress | 17 | -1,512.03 | -88.94 | 0.00 | 0.00 | -0.30 |
| small win | 18 | 3,459.22 | 192.18 | 100.00 | 3.46e+12 | 0.40 |
| win >= 1R | 14 | 11,575.22 | 826.80 | 100.00 | 1.16e+13 | 1.96 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 28 | 1,289.40 |
| long | 51 | 2,699.70 |


### D1 (38 trades, net -3,718 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 9 | -2,117.80 | -235.31 | 11.11 | 0.04 | -0.35 |
| weak_bull | 12 | 915.82 | 76.32 | 41.67 | 1.52 | 0.06 |
| sideways | 9 | -906.63 | -100.74 | 33.33 | 0.66 | -0.11 |
| weak_bear | 6 | 453.00 | 75.50 | 33.33 | 1.41 | -0.14 |
| strong_bear | 2 | -2,062.20 | -1,031.10 | 0.00 | 0.00 | -0.80 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 13 | 1,338.98 | 103.00 | 38.46 | 2.30 | 0.11 |
| normal | 21 | -4,405.15 | -209.77 | 19.05 | 0.39 | -0.32 |
| high | 3 | -1,513.32 | -504.44 | 33.33 | 0.05 | -0.36 |
| extreme | 1 | 861.69 | 861.69 | 100.00 | 8.62e+11 | 0.42 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 2 | -1,430.82 | -715.41 | 0.00 | 0.00 | -0.54 |
| large up | 2 | -1,764.48 | -882.24 | 0.00 | 0.00 | -0.68 |
| medium down | 2 | -770.13 | -385.07 | 0.00 | 0.00 | -0.45 |
| medium up | 7 | -910.60 | -130.09 | 28.57 | 0.26 | -0.29 |
| small down | 11 | 1,903.05 | 173.00 | 45.45 | 1.98 | 0.28 |
| small up | 14 | -744.84 | -53.20 | 28.57 | 0.72 | -0.25 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 12 | -1,560.26 | -130.02 | 33.33 | 0.65 | 0.03 |
| Tue | 4 | -830.66 | -207.66 | 0.00 | 0.00 | -0.50 |
| Wed | 12 | -1,278.49 | -106.54 | 33.33 | 0.59 | -0.27 |
| Thu | 6 | -388.42 | -64.74 | 16.67 | 0.56 | -0.05 |
| Fri | 4 | 340.03 | 85.01 | 50.00 | 1.67 | -0.18 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 1 | 1,028.56 | 1,028.56 | 100.00 | 1.03e+12 | 1.58 |
| long above prev high | 29 | -4,006.12 | -138.14 | 24.14 | 0.40 | -0.25 |
| short below prev low | 8 | -740.25 | -92.53 | 37.50 | 0.76 | -0.01 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 26 | -2,774.72 | -106.72 | 30.77 | 0.57 | -0.15 |
| expansion | 12 | -943.08 | -78.59 | 25.00 | 0.72 | -0.15 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 15 | -8,067.19 | -537.81 | 0.00 | 0.00 | -0.62 |
| loss after progress | 12 | -1,730.96 | -144.25 | 0.00 | 0.00 | -0.33 |
| small win | 9 | 4,236.20 | 470.69 | 100.00 | 4.24e+12 | 0.39 |
| win >= 1R | 2 | 1,844.14 | 922.07 | 100.00 | 1.84e+12 | 1.95 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 8 | -740.20 |
| long | 30 | -2,977.60 |


## NIFTY BANK: ASIS


### 5m (5183 trades, net -78,273 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 1075 | -21,522.62 | -20.02 | 12.74 | 0.48 | -0.17 |
| weak_bull | 1595 | -24,131.56 | -15.13 | 12.66 | 0.59 | -0.17 |
| sideways | 1027 | -16,284.94 | -15.86 | 11.49 | 0.58 | -0.13 |
| weak_bear | 1086 | -12,837.98 | -11.82 | 11.60 | 0.65 | -0.12 |
| strong_bear | 400 | -3,495.55 | -8.74 | 12.50 | 0.78 | -0.04 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 1899 | -32,147.14 | -16.93 | 12.22 | 0.53 | -0.17 |
| normal | 2494 | -39,139.71 | -15.69 | 12.39 | 0.59 | -0.14 |
| high | 628 | -5,271.89 | -8.39 | 11.62 | 0.76 | -0.05 |
| extreme | 162 | -1,713.91 | -10.58 | 11.73 | 0.71 | -0.03 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 481 | -9,272.54 | -19.28 | 14.35 | 0.53 | -0.08 |
| morning | 1367 | -20,553.38 | -15.04 | 13.31 | 0.54 | -0.14 |
| midday | 1597 | -27,469.86 | -17.20 | 12.02 | 0.46 | -0.20 |
| afternoon | 1291 | -22,325.89 | -17.29 | 8.99 | 0.55 | -0.16 |
| closing | 447 | 1,349.01 | 3.02 | 16.55 | 1.05 | 0.06 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 397 | -3,141.58 | -7.91 | 11.34 | 0.81 | -0.04 |
| large up | 407 | -1,965.30 | -4.83 | 14.25 | 0.87 | -0.01 |
| medium down | 858 | -11,085.67 | -12.92 | 12.70 | 0.66 | -0.10 |
| medium up | 1199 | -20,693.56 | -17.26 | 12.09 | 0.52 | -0.16 |
| small down | 989 | -17,163.37 | -17.35 | 12.13 | 0.53 | -0.17 |
| small up | 1333 | -24,223.18 | -18.17 | 11.70 | 0.49 | -0.20 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 1039 | -21,174.70 | -20.38 | 12.03 | 0.47 | -0.17 |
| Tue | 1055 | -23,734.73 | -22.50 | 10.14 | 0.43 | -0.19 |
| Wed | 1003 | -9,208.37 | -9.18 | 13.36 | 0.74 | -0.09 |
| Thu | 989 | -17,078.26 | -17.27 | 12.64 | 0.53 | -0.17 |
| Fri | 1073 | -6,159.48 | -5.74 | 13.05 | 0.83 | -0.08 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 2249 | -40,862.54 | -18.17 | 11.69 | 0.50 | -0.18 |
| long above prev high | 1597 | -21,811.69 | -13.66 | 12.84 | 0.62 | -0.13 |
| short below prev low | 1337 | -15,598.42 | -11.67 | 12.34 | 0.70 | -0.09 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 2820 | -41,533.03 | -14.73 | 12.87 | 0.58 | -0.16 |
| expansion | 2363 | -36,739.62 | -15.55 | 11.43 | 0.60 | -0.12 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 2777 | -153,482.15 | -55.27 | 0.00 | 0.00 | -0.42 |
| loss after progress | 1773 | -37,999.09 | -21.43 | 0.00 | 0.00 | -0.26 |
| small win | 388 | 27,049.49 | 69.72 | 100.00 | 2.7e+13 | 0.39 |
| win >= 1R | 245 | 86,159.11 | 351.67 | 100.00 | 8.62e+13 | 3.05 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 2381 | -32,307.90 |
| long | 2802 | -45,964.70 |


### 15m (1958 trades, net -5,002 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 447 | -9,775.62 | -21.87 | 9.17 | 0.51 | -0.11 |
| weak_bull | 608 | -9,292.16 | -15.28 | 8.72 | 0.65 | -0.09 |
| sideways | 368 | 6,155.92 | 16.73 | 14.40 | 1.47 | 0.04 |
| weak_bear | 385 | 6,602.32 | 17.15 | 12.47 | 1.48 | 0.03 |
| strong_bear | 150 | 1,307.28 | 8.72 | 7.33 | 1.22 | 0.05 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 709 | -9,063.22 | -12.78 | 11.28 | 0.70 | -0.06 |
| normal | 961 | 339.22 | 0.35 | 9.89 | 1.01 | -0.02 |
| high | 233 | 2,850.44 | 12.23 | 11.16 | 1.23 | -0.04 |
| extreme | 55 | 871.31 | 15.84 | 9.09 | 1.43 | 0.01 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 176 | -1,352.80 | -7.69 | 16.48 | 0.84 | -0.04 |
| morning | 564 | -3,396.15 | -6.02 | 10.82 | 0.84 | -0.04 |
| midday | 577 | -8,857.04 | -15.35 | 6.76 | 0.55 | -0.10 |
| afternoon | 482 | 2,107.18 | 4.37 | 9.34 | 1.09 | -0.02 |
| closing | 159 | 6,496.56 | 40.86 | 20.13 | 1.85 | 0.13 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 153 | 4,013.43 | 26.23 | 14.38 | 1.63 | 0.04 |
| large up | 138 | 2,704.11 | 19.60 | 13.04 | 1.45 | 0.08 |
| medium down | 321 | 5,458.06 | 17.00 | 9.66 | 1.48 | 0.02 |
| medium up | 404 | -2,005.60 | -4.96 | 9.41 | 0.88 | -0.03 |
| small down | 439 | -8,607.09 | -19.61 | 9.34 | 0.48 | -0.12 |
| small up | 503 | -6,565.18 | -13.05 | 11.13 | 0.71 | -0.07 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 379 | -3,741.69 | -9.87 | 9.76 | 0.76 | -0.05 |
| Tue | 373 | -3,884.81 | -10.42 | 9.65 | 0.79 | -0.06 |
| Wed | 393 | -1,354.43 | -3.45 | 10.69 | 0.91 | -0.02 |
| Thu | 428 | -2,164.78 | -5.06 | 10.98 | 0.87 | -0.07 |
| Fri | 378 | 5,745.56 | 15.20 | 11.38 | 1.45 | 0.02 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 868 | -3,955.02 | -4.56 | 10.48 | 0.89 | -0.06 |
| long above prev high | 579 | -2,629.59 | -4.54 | 10.88 | 0.90 | -0.04 |
| short below prev low | 511 | 1,582.35 | 3.10 | 10.18 | 1.09 | -0.01 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 1079 | -1,379.68 | -1.28 | 11.58 | 0.97 | -0.02 |
| expansion | 879 | -3,622.57 | -4.12 | 9.22 | 0.91 | -0.05 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 1286 | -66,666.01 | -51.84 | 0.00 | 0.00 | -0.22 |
| loss after progress | 466 | -12,851.96 | -27.58 | 0.00 | 0.00 | -0.17 |
| small win | 123 | 17,959.69 | 146.01 | 100.00 | 1.8e+13 | 0.41 |
| win >= 1R | 83 | 56,556.03 | 681.40 | 100.00 | 5.66e+13 | 2.93 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 909 | 2,278.90 |
| long | 1049 | -7,281.20 |


### 30m (1190 trades, net -9,709 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 262 | -6,947.46 | -26.52 | 4.96 | 0.37 | -0.08 |
| weak_bull | 380 | -4,272.71 | -11.24 | 8.95 | 0.76 | -0.03 |
| sideways | 228 | -2,007.76 | -8.81 | 7.02 | 0.83 | -0.06 |
| weak_bear | 235 | 2,584.17 | 11.00 | 8.51 | 1.30 | 0.01 |
| strong_bear | 85 | 934.80 | 11.00 | 9.41 | 1.19 | 0.09 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 461 | -6,783.71 | -14.72 | 6.94 | 0.67 | -0.05 |
| normal | 565 | -1,848.20 | -3.27 | 7.61 | 0.92 | -0.02 |
| high | 127 | -548.03 | -4.32 | 10.24 | 0.94 | 0.01 |
| extreme | 37 | -529.02 | -14.30 | 8.11 | 0.79 | -0.11 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 131 | -3,180.39 | -24.28 | 6.87 | 0.56 | -0.05 |
| morning | 363 | -1,913.33 | -5.27 | 6.61 | 0.88 | -0.03 |
| midday | 294 | -6,965.13 | -23.69 | 4.42 | 0.39 | -0.07 |
| afternoon | 289 | 2,932.29 | 10.15 | 9.69 | 1.27 | -0.00 |
| closing | 113 | -582.39 | -5.15 | 15.04 | 0.93 | 0.02 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 91 | -796.31 | -8.75 | 6.59 | 0.83 | 0.02 |
| large up | 93 | 5,092.06 | 54.75 | 11.83 | 1.99 | 0.13 |
| medium down | 216 | -4,564.21 | -21.13 | 5.56 | 0.53 | -0.08 |
| medium up | 238 | -7,160.42 | -30.09 | 6.30 | 0.46 | -0.12 |
| small down | 241 | -1,864.21 | -7.74 | 7.88 | 0.80 | -0.03 |
| small up | 311 | -415.87 | -1.34 | 9.00 | 0.97 | 0.01 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 231 | -6,721.38 | -29.10 | 6.06 | 0.41 | -0.07 |
| Tue | 213 | 932.35 | 4.38 | 5.63 | 1.10 | -0.05 |
| Wed | 242 | -7,531.59 | -31.12 | 8.26 | 0.45 | -0.09 |
| Thu | 244 | -4,054.62 | -16.62 | 7.79 | 0.60 | -0.04 |
| Fri | 256 | 7,730.34 | 30.20 | 10.16 | 1.85 | 0.09 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 444 | -4,380.32 | -9.87 | 6.98 | 0.78 | -0.04 |
| long above prev high | 400 | -678.38 | -1.70 | 10.00 | 0.97 | -0.03 |
| short below prev low | 346 | -4,650.25 | -13.44 | 5.78 | 0.67 | -0.02 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 639 | -1,639.66 | -2.57 | 8.29 | 0.94 | -0.01 |
| expansion | 551 | -8,069.29 | -14.64 | 6.90 | 0.72 | -0.05 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 910 | -49,232.84 | -54.10 | 0.00 | 0.00 | -0.16 |
| loss after progress | 189 | -4,831.09 | -25.56 | 0.00 | 0.00 | -0.12 |
| small win | 52 | 9,512.94 | 182.94 | 100.00 | 9.51e+12 | 0.39 |
| win >= 1R | 39 | 34,842.04 | 893.39 | 100.00 | 3.48e+13 | 2.77 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 554 | -9,928.10 |
| long | 636 | 219.20 |


### 1h (627 trades, net 4,206 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 132 | -3,907.22 | -29.60 | 6.06 | 0.51 | -0.04 |
| weak_bull | 189 | -311.52 | -1.65 | 7.41 | 0.96 | 0.01 |
| sideways | 145 | 8,365.84 | 57.70 | 8.97 | 2.47 | 0.08 |
| weak_bear | 115 | 3,506.65 | 30.49 | 7.83 | 1.67 | 0.04 |
| strong_bear | 46 | -3,447.36 | -74.94 | 4.35 | 0.13 | -0.08 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 259 | 451.54 | 1.74 | 8.49 | 1.04 | 0.04 |
| normal | 285 | 5,857.51 | 20.55 | 6.32 | 1.46 | -0.00 |
| high | 65 | -1,559.53 | -23.99 | 7.69 | 0.64 | -0.00 |
| extreme | 18 | -543.12 | -30.17 | 5.56 | 0.66 | 0.02 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 120 | 937.62 | 7.81 | 6.67 | 1.14 | -0.01 |
| morning | 153 | 4,168.90 | 27.25 | 6.54 | 1.54 | 0.01 |
| midday | 164 | -135.20 | -0.82 | 6.71 | 0.98 | 0.04 |
| afternoon | 125 | 1,140.21 | 9.12 | 9.60 | 1.32 | 0.03 |
| closing | 65 | -1,905.14 | -29.31 | 7.69 | 0.69 | -0.01 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 51 | -2,892.70 | -56.72 | 3.92 | 0.16 | -0.04 |
| large up | 41 | 6,736.85 | 164.31 | 14.63 | 8.33 | 0.20 |
| medium down | 100 | 2,561.57 | 25.62 | 9.00 | 1.53 | 0.05 |
| medium up | 120 | -3,207.32 | -26.73 | 7.50 | 0.68 | 0.01 |
| small down | 148 | -2,838.36 | -19.18 | 4.73 | 0.50 | -0.05 |
| small up | 167 | 3,846.36 | 23.03 | 7.78 | 1.59 | 0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 132 | 2,581.88 | 19.56 | 9.09 | 1.49 | 0.08 |
| Tue | 109 | 942.73 | 8.65 | 6.42 | 1.19 | 0.02 |
| Wed | 128 | -2,158.95 | -16.87 | 3.91 | 0.63 | -0.05 |
| Thu | 129 | -5,634.43 | -43.68 | 4.65 | 0.43 | -0.06 |
| Fri | 129 | 8,475.15 | 65.70 | 12.40 | 2.56 | 0.08 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 162 | 1,352.06 | 8.35 | 6.17 | 1.21 | 0.04 |
| long above prev high | 266 | 5,963.02 | 22.42 | 9.02 | 1.43 | 0.04 |
| short below prev low | 199 | -3,108.68 | -15.62 | 6.03 | 0.72 | -0.03 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 368 | 2,571.08 | 6.99 | 7.61 | 1.15 | 0.03 |
| expansion | 259 | 1,635.32 | 6.31 | 6.95 | 1.12 | -0.01 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 503 | -29,034.46 | -57.72 | 0.00 | 0.00 | -0.10 |
| loss after progress | 78 | -2,504.89 | -32.11 | 0.00 | 0.00 | -0.08 |
| small win | 30 | 10,026.69 | 334.22 | 100.00 | 1e+13 | 0.48 |
| win >= 1R | 16 | 25,719.05 | 1,607.44 | 100.00 | 2.57e+13 | 3.42 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 265 | -4,111.00 |
| long | 362 | 8,317.40 |


### 2h (410 trades, net -5,418 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 95 | -5,817.36 | -61.24 | 4.21 | 0.37 | -0.07 |
| weak_bull | 132 | -2,036.84 | -15.43 | 3.03 | 0.70 | 0.00 |
| sideways | 97 | 706.40 | 7.28 | 6.19 | 1.27 | -0.00 |
| weak_bear | 71 | 1,882.00 | 26.51 | 12.68 | 1.56 | 0.04 |
| strong_bear | 15 | -151.82 | -10.12 | 6.67 | 0.71 | -0.06 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 176 | -3,125.46 | -17.76 | 6.25 | 0.70 | 0.02 |
| normal | 196 | -1,871.75 | -9.55 | 5.10 | 0.82 | -0.05 |
| high | 30 | -972.36 | -32.41 | 6.67 | 0.44 | 0.01 |
| extreme | 8 | 551.94 | 68.99 | 12.50 | 6.07 | 0.10 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 113 | -3,276.03 | -28.99 | 5.31 | 0.55 | -0.00 |
| morning | 58 | 1,602.24 | 27.62 | 5.17 | 1.93 | 0.05 |
| midday | 100 | -2,174.16 | -21.74 | 4.00 | 0.48 | -0.04 |
| afternoon | 82 | -2,149.27 | -26.21 | 7.32 | 0.63 | -0.00 |
| closing | 57 | 579.59 | 10.17 | 8.77 | 1.16 | -0.06 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 30 | 476.96 | 15.90 | 10.00 | 1.98 | 0.00 |
| large up | 28 | 3,808.02 | 136.00 | 14.29 | 3.99 | 0.16 |
| medium down | 76 | -1,790.37 | -23.56 | 5.26 | 0.58 | -0.06 |
| medium up | 75 | -3,536.34 | -47.15 | 5.33 | 0.31 | -0.03 |
| small down | 96 | -1,711.69 | -17.83 | 4.17 | 0.65 | 0.03 |
| small up | 105 | -2,664.20 | -25.37 | 4.76 | 0.59 | -0.05 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 75 | -2,638.49 | -35.18 | 6.67 | 0.47 | -0.04 |
| Tue | 81 | 344.01 | 4.25 | 6.17 | 1.06 | -0.02 |
| Wed | 80 | -1,359.18 | -16.99 | 2.50 | 0.62 | 0.05 |
| Thu | 80 | -3,253.11 | -40.66 | 7.50 | 0.37 | -0.07 |
| Fri | 93 | 1,507.23 | 16.21 | 6.45 | 1.44 | 0.01 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 78 | -2,110.16 | -27.05 | 3.85 | 0.44 | -0.07 |
| long above prev high | 207 | -1,457.24 | -7.04 | 6.76 | 0.90 | 0.01 |
| short below prev low | 125 | -1,850.23 | -14.80 | 5.60 | 0.59 | -0.02 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 248 | -3,230.82 | -13.03 | 6.45 | 0.77 | 0.01 |
| expansion | 162 | -2,186.81 | -13.50 | 4.94 | 0.74 | -0.04 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 342 | -20,654.28 | -60.39 | 0.00 | 0.00 | -0.09 |
| loss after progress | 44 | -1,834.15 | -41.69 | 0.00 | 0.00 | -0.08 |
| small win | 16 | 6,181.17 | 386.32 | 100.00 | 6.18e+12 | 0.44 |
| win >= 1R | 8 | 10,889.63 | 1,361.20 | 100.00 | 1.09e+13 | 2.87 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 156 | -3,008.50 |
| long | 254 | -2,409.10 |


### 4h (245 trades, net -8,239 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 70 | -5,192.90 | -74.18 | 2.86 | 0.04 | -0.07 |
| weak_bull | 84 | 609.43 | 7.26 | 3.57 | 1.17 | -0.03 |
| sideways | 36 | -2,463.56 | -68.43 | 2.78 | 0.21 | -0.07 |
| weak_bear | 46 | -1,454.07 | -31.61 | 2.17 | 0.41 | 0.01 |
| strong_bear | 9 | 262.46 | 29.16 | 11.11 | 3.22 | 0.02 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 88 | -4,111.73 | -46.72 | 3.41 | 0.35 | -0.05 |
| normal | 135 | -4,388.07 | -32.50 | 2.22 | 0.46 | -0.04 |
| high | 16 | 168.43 | 10.53 | 6.25 | 1.79 | 0.00 |
| extreme | 6 | 92.73 | 15.46 | 16.67 | 2.19 | 0.00 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 88 | -3,694.61 | -41.98 | 4.55 | 0.42 | -0.03 |
| morning | 35 | -2,017.33 | -57.64 | 0.00 | 0.00 | -0.07 |
| midday | 38 | -1,650.76 | -43.44 | 0.00 | 0.00 | -0.05 |
| afternoon | 63 | -1,917.23 | -30.43 | 4.76 | 0.36 | -0.04 |
| closing | 21 | 1,041.28 | 49.58 | 4.76 | 1.63 | -0.01 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 16 | 160.76 | 10.05 | 6.25 | 1.73 | 0.00 |
| large up | 20 | 2,146.26 | 107.31 | 10.00 | 4.75 | 0.04 |
| medium down | 36 | -2,048.23 | -56.90 | 0.00 | 0.00 | -0.06 |
| medium up | 59 | -4,685.00 | -79.41 | 0.00 | 0.00 | -0.08 |
| small down | 46 | -625.79 | -13.60 | 2.17 | 0.70 | -0.01 |
| small up | 68 | -3,186.65 | -46.86 | 5.88 | 0.37 | -0.04 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 55 | -3,148.10 | -57.24 | 0.00 | 0.00 | -0.05 |
| Tue | 39 | 199.79 | 5.12 | 5.13 | 1.08 | -0.05 |
| Wed | 55 | -2,721.04 | -49.47 | 3.64 | 0.36 | -0.05 |
| Thu | 57 | -1,608.84 | -28.23 | 5.26 | 0.51 | -0.02 |
| Fri | 39 | -960.45 | -24.63 | 2.56 | 0.28 | -0.03 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 33 | -1,685.93 | -51.09 | 0.00 | 0.00 | -0.05 |
| long above prev high | 155 | -4,313.14 | -27.83 | 4.52 | 0.59 | -0.04 |
| short below prev low | 57 | -2,239.57 | -39.29 | 1.75 | 0.15 | -0.03 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 147 | -6,872.69 | -46.75 | 2.04 | 0.27 | -0.05 |
| expansion | 98 | -1,365.95 | -13.94 | 5.10 | 0.74 | -0.03 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 214 | -14,260.92 | -66.64 | 0.00 | 0.00 | -0.07 |
| loss after progress | 23 | -460.88 | -20.04 | 0.00 | 0.00 | -0.03 |
| small win | 5 | 1,305.17 | 261.03 | 100.00 | 1.31e+12 | 0.23 |
| win >= 1R | 3 | 5,177.99 | 1,726.00 | 100.00 | 5.18e+12 | 1.51 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 67 | -2,380.20 |
| long | 178 | -5,858.40 |


### D1 (107 trades, net -4,873 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 28 | -1,816.44 | -64.87 | 3.57 | 0.01 | -0.05 |
| weak_bull | 43 | -1,595.29 | -37.10 | 0.00 | 0.00 | -0.02 |
| sideways | 19 | -1,200.98 | -63.21 | 0.00 | 0.00 | -0.06 |
| weak_bear | 11 | -164.95 | -15.00 | 0.00 | 0.00 | -0.01 |
| strong_bear | 6 | -95.43 | -15.90 | 0.00 | 0.00 | -0.01 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 54 | -2,698.96 | -49.98 | 0.00 | 0.00 | -0.04 |
| normal | 45 | -2,081.24 | -46.25 | 0.00 | 0.00 | -0.03 |
| high | 4 | -65.01 | -16.25 | 0.00 | 0.00 | -0.00 |
| extreme | 4 | -27.87 | -6.97 | 25.00 | 0.40 | -0.00 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 5 | -78.41 | -15.68 | 0.00 | 0.00 | -0.01 |
| large up | 7 | -104.31 | -14.90 | 0.00 | 0.00 | -0.01 |
| medium down | 17 | -267.51 | -15.74 | 0.00 | 0.00 | -0.01 |
| medium up | 19 | -393.76 | -20.72 | 0.00 | 0.00 | -0.02 |
| small down | 24 | -860.70 | -35.86 | 0.00 | 0.00 | -0.03 |
| small up | 35 | -3,168.39 | -90.53 | 2.86 | 0.01 | -0.06 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 25 | -392.40 | -15.70 | 0.00 | 0.00 | -0.01 |
| Tue | 23 | -1,028.07 | -44.70 | 4.35 | 0.02 | -0.04 |
| Wed | 17 | -1,102.06 | -64.83 | 0.00 | 0.00 | -0.04 |
| Thu | 22 | -2,030.44 | -92.29 | 0.00 | 0.00 | -0.08 |
| Fri | 20 | -320.11 | -16.01 | 0.00 | 0.00 | -0.01 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 6 | -566.92 | -94.49 | 0.00 | 0.00 | -0.09 |
| long above prev high | 87 | -4,086.71 | -46.97 | 1.15 | 0.00 | -0.04 |
| short below prev low | 14 | -219.45 | -15.67 | 0.00 | 0.00 | -0.01 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 73 | -4,376.63 | -59.95 | 0.00 | 0.00 | -0.05 |
| expansion | 34 | -496.45 | -14.60 | 2.94 | 0.04 | -0.01 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 96 | -4,619.87 | -48.12 | 0.00 | 0.00 | -0.04 |
| loss after progress | 10 | -271.83 | -27.18 | 0.00 | 0.00 | -0.03 |
| small win | 1 | 18.62 | 18.62 | 100.00 | 1.86e+10 | 0.01 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 14 | -219.40 |
| long | 93 | -4,653.60 |


## NIFTY BANK: FINAL_H4


### 5m (3664 trades, net -34,786 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 780 | -13,770.43 | -17.65 | 25.64 | 0.71 | -0.15 |
| weak_bull | 1180 | -14,643.32 | -12.41 | 25.00 | 0.78 | -0.14 |
| sideways | 743 | -9,198.10 | -12.38 | 24.50 | 0.79 | -0.08 |
| weak_bear | 703 | 56.47 | 0.08 | 27.17 | 1.00 | -0.02 |
| strong_bear | 258 | 2,769.17 | 10.73 | 25.58 | 1.14 | 0.04 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 1403 | -16,906.71 | -12.05 | 24.45 | 0.77 | -0.14 |
| normal | 1745 | -19,299.27 | -11.06 | 25.16 | 0.82 | -0.09 |
| high | 410 | 4,372.99 | 10.67 | 29.51 | 1.16 | 0.11 |
| extreme | 106 | -2,953.22 | -27.86 | 29.25 | 0.70 | -0.15 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 393 | -7,356.86 | -18.72 | 33.59 | 0.73 | -0.07 |
| morning | 889 | -10,756.54 | -12.10 | 29.25 | 0.78 | -0.09 |
| midday | 1097 | -15,953.21 | -14.54 | 22.42 | 0.70 | -0.17 |
| afternoon | 956 | 2,166.79 | 2.27 | 21.03 | 1.04 | -0.06 |
| closing | 329 | -2,886.39 | -8.77 | 28.88 | 0.91 | 0.05 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 249 | 2,623.81 | 10.54 | 28.51 | 1.14 | 0.14 |
| large up | 298 | 1,837.66 | 6.17 | 29.19 | 1.11 | 0.01 |
| medium down | 620 | -4,435.26 | -7.15 | 24.84 | 0.89 | -0.05 |
| medium up | 847 | -11,074.07 | -13.07 | 25.27 | 0.78 | -0.13 |
| small down | 713 | -8,942.24 | -12.54 | 23.84 | 0.78 | -0.15 |
| small up | 937 | -14,796.11 | -15.79 | 25.40 | 0.73 | -0.14 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 730 | -11,355.25 | -15.56 | 24.93 | 0.74 | -0.14 |
| Tue | 725 | -16,153.43 | -22.28 | 22.62 | 0.65 | -0.17 |
| Wed | 736 | -3,369.09 | -4.58 | 25.82 | 0.92 | -0.07 |
| Thu | 718 | -9,965.92 | -13.88 | 25.49 | 0.76 | -0.10 |
| Fri | 744 | 4,893.60 | 6.58 | 28.63 | 1.12 | 0.03 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 1651 | -25,257.93 | -15.30 | 23.14 | 0.74 | -0.14 |
| long above prev high | 1099 | -6,933.51 | -6.31 | 27.66 | 0.89 | -0.08 |
| short below prev low | 914 | -2,594.77 | -2.84 | 27.13 | 0.96 | -0.02 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 2042 | -17,458.97 | -8.55 | 26.05 | 0.84 | -0.11 |
| expansion | 1622 | -17,327.25 | -10.68 | 24.78 | 0.84 | -0.07 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 1437 | -146,422.96 | -101.89 | 0.00 | 0.00 | -0.66 |
| loss after progress | 1293 | -72,528.92 | -56.09 | 0.00 | 0.00 | -0.52 |
| small win | 514 | 47,864.15 | 93.12 | 100.00 | 4.79e+13 | 0.38 |
| win >= 1R | 420 | 136,301.51 | 324.53 | 100.00 | 1.36e+14 | 2.59 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 1679 | -15,064.40 |
| long | 1985 | -19,721.90 |


### 15m (1125 trades, net 15,190 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 270 | -5,981.28 | -22.15 | 25.93 | 0.76 | -0.18 |
| weak_bull | 339 | 1,086.34 | 3.20 | 28.91 | 1.03 | 0.02 |
| sideways | 215 | 10,699.57 | 49.77 | 35.35 | 1.62 | 0.12 |
| weak_bear | 228 | 8,607.03 | 37.75 | 30.26 | 1.43 | 0.08 |
| strong_bear | 73 | 778.52 | 10.66 | 24.66 | 1.08 | 0.07 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 435 | 4,111.97 | 9.45 | 30.80 | 1.13 | 0.02 |
| normal | 531 | 3,211.80 | 6.05 | 28.06 | 1.06 | -0.01 |
| high | 132 | 4,907.49 | 37.18 | 28.79 | 1.31 | -0.04 |
| extreme | 27 | 2,958.92 | 109.59 | 37.04 | 2.36 | 0.24 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 103 | -658.43 | -6.39 | 33.98 | 0.93 | 0.01 |
| morning | 383 | 3,814.67 | 9.96 | 31.33 | 1.11 | -0.01 |
| midday | 287 | 1,985.70 | 6.92 | 21.95 | 1.09 | -0.02 |
| afternoon | 266 | 3,805.33 | 14.31 | 28.20 | 1.13 | -0.07 |
| closing | 86 | 6,242.91 | 72.59 | 44.19 | 1.67 | 0.40 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 83 | 887.14 | 10.69 | 31.33 | 1.07 | 0.05 |
| large up | 80 | 6,589.83 | 82.37 | 42.50 | 1.99 | 0.26 |
| medium down | 190 | 9,958.13 | 52.41 | 27.89 | 1.65 | 0.05 |
| medium up | 240 | 3,723.06 | 15.51 | 29.58 | 1.18 | 0.01 |
| small down | 234 | -3,140.35 | -13.42 | 25.21 | 0.85 | -0.09 |
| small up | 298 | -2,827.62 | -9.49 | 29.53 | 0.90 | -0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 228 | -7,607.93 | -33.37 | 26.32 | 0.70 | -0.16 |
| Tue | 227 | 2,342.94 | 10.32 | 28.19 | 1.12 | -0.02 |
| Wed | 220 | 4,404.23 | 20.02 | 29.09 | 1.23 | 0.05 |
| Thu | 238 | 3,310.35 | 13.91 | 30.67 | 1.16 | 0.02 |
| Fri | 209 | 12,545.56 | 60.03 | 33.01 | 1.63 | 0.15 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 575 | 6,455.43 | 11.23 | 27.13 | 1.13 | -0.03 |
| long above prev high | 307 | 4,566.50 | 14.87 | 32.25 | 1.18 | 0.04 |
| short below prev low | 243 | 4,168.25 | 17.15 | 31.28 | 1.14 | 0.04 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 636 | 15,276.23 | 24.02 | 30.35 | 1.31 | 0.06 |
| expansion | 489 | -86.04 | -0.18 | 28.22 | 1.00 | -0.06 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 408 | -69,635.38 | -170.67 | 0.00 | 0.00 | -0.59 |
| loss after progress | 386 | -35,139.98 | -91.04 | 0.00 | 0.00 | -0.49 |
| small win | 176 | 32,444.87 | 184.35 | 100.00 | 3.24e+13 | 0.41 |
| win >= 1R | 155 | 87,520.67 | 564.65 | 100.00 | 8.75e+13 | 2.36 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 507 | 9,147.40 |
| long | 618 | 6,042.80 |


### 30m (593 trades, net 6,230 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 123 | -2,270.43 | -18.46 | 28.46 | 0.86 | -0.12 |
| weak_bull | 196 | 5,004.18 | 25.53 | 29.08 | 1.21 | 0.10 |
| sideways | 118 | -2,571.78 | -21.79 | 27.12 | 0.86 | -0.06 |
| weak_bear | 114 | 9,119.08 | 79.99 | 32.46 | 1.65 | 0.09 |
| strong_bear | 42 | -3,050.82 | -72.64 | 28.57 | 0.73 | -0.03 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 235 | 2,615.57 | 11.13 | 29.36 | 1.11 | 0.00 |
| normal | 270 | 2,568.23 | 9.51 | 27.41 | 1.06 | 0.02 |
| high | 71 | 1,194.97 | 16.83 | 35.21 | 1.08 | 0.04 |
| extreme | 17 | -148.55 | -8.74 | 29.41 | 0.95 | -0.02 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 49 | -1,664.92 | -33.98 | 24.49 | 0.79 | -0.07 |
| morning | 211 | 3,072.17 | 14.56 | 31.75 | 1.09 | 0.03 |
| midday | 159 | 7,329.14 | 46.10 | 31.45 | 1.42 | 0.06 |
| afternoon | 125 | -3,692.62 | -29.54 | 24.00 | 0.80 | -0.13 |
| closing | 49 | 1,186.45 | 24.21 | 28.57 | 1.24 | 0.22 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 43 | -4,728.66 | -109.97 | 20.93 | 0.59 | -0.00 |
| large up | 51 | 7,675.39 | 150.50 | 49.02 | 2.22 | 0.23 |
| medium down | 110 | 4,110.96 | 37.37 | 30.00 | 1.25 | 0.02 |
| medium up | 130 | -1,193.69 | -9.18 | 26.92 | 0.93 | -0.07 |
| small down | 121 | 3,052.00 | 25.22 | 28.93 | 1.22 | 0.07 |
| small up | 138 | -2,685.78 | -19.46 | 26.09 | 0.85 | -0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 118 | -10,184.44 | -86.31 | 22.03 | 0.50 | -0.25 |
| Tue | 109 | -317.97 | -2.92 | 27.52 | 0.98 | -0.09 |
| Wed | 127 | 1,132.47 | 8.92 | 33.07 | 1.06 | 0.03 |
| Thu | 117 | -4,932.57 | -42.16 | 23.93 | 0.70 | -0.07 |
| Fri | 121 | 20,550.46 | 169.84 | 38.84 | 2.38 | 0.43 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 287 | -1,775.91 | -6.19 | 26.13 | 0.95 | -0.01 |
| long above prev high | 165 | 6,678.39 | 40.48 | 33.94 | 1.33 | -0.01 |
| short below prev low | 141 | 1,327.74 | 9.42 | 29.79 | 1.05 | 0.09 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 329 | 6,431.43 | 19.55 | 28.27 | 1.16 | 0.00 |
| expansion | 264 | -201.21 | -0.76 | 30.30 | 1.00 | 0.03 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 220 | -59,923.69 | -272.38 | 0.00 | 0.00 | -0.63 |
| loss after progress | 200 | -24,217.37 | -121.09 | 0.00 | 0.00 | -0.43 |
| small win | 90 | 27,596.08 | 306.62 | 100.00 | 2.76e+13 | 0.41 |
| win >= 1R | 83 | 62,775.20 | 756.33 | 100.00 | 6.28e+13 | 2.36 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 280 | -6,330.00 |
| long | 313 | 12,560.20 |


### 1h (309 trades, net 5,448 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 67 | -4,081.32 | -60.92 | 28.36 | 0.68 | -0.05 |
| weak_bull | 103 | -720.76 | -7.00 | 25.24 | 0.96 | -0.02 |
| sideways | 68 | 10,190.52 | 149.86 | 39.71 | 1.82 | 0.21 |
| weak_bear | 52 | 2,113.27 | 40.64 | 26.92 | 1.21 | 0.06 |
| strong_bear | 19 | -2,053.89 | -108.10 | 15.79 | 0.65 | -0.36 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 131 | 2,664.24 | 20.34 | 32.82 | 1.13 | 0.01 |
| normal | 139 | -638.35 | -4.59 | 23.74 | 0.98 | 0.00 |
| high | 32 | 2,280.95 | 71.28 | 28.12 | 1.33 | -0.05 |
| extreme | 7 | 1,140.98 | 163.00 | 57.14 | 1.68 | 0.70 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 49 | -813.45 | -16.60 | 28.57 | 0.92 | -0.02 |
| morning | 79 | 7,321.20 | 92.67 | 32.91 | 1.52 | 0.10 |
| midday | 92 | 8,151.48 | 88.60 | 31.52 | 1.64 | 0.14 |
| afternoon | 62 | -3,639.53 | -58.70 | 22.58 | 0.73 | -0.14 |
| closing | 27 | -5,571.89 | -206.37 | 22.22 | 0.40 | -0.24 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 25 | 2,080.10 | 83.20 | 20.00 | 1.30 | 0.10 |
| large up | 30 | 8,193.83 | 273.13 | 50.00 | 2.52 | 0.44 |
| medium down | 50 | 1,027.56 | 20.55 | 28.00 | 1.11 | 0.09 |
| medium up | 63 | -5,385.78 | -85.49 | 23.81 | 0.64 | -0.08 |
| small down | 70 | 424.43 | 6.06 | 28.57 | 1.04 | -0.12 |
| small up | 71 | -892.33 | -12.57 | 28.17 | 0.92 | -0.02 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 66 | -2,848.00 | -43.15 | 30.30 | 0.81 | -0.01 |
| Tue | 55 | -4,426.37 | -80.48 | 20.00 | 0.59 | -0.13 |
| Wed | 73 | 4,751.31 | 65.09 | 27.40 | 1.36 | 0.00 |
| Thu | 53 | -2,366.21 | -44.65 | 18.87 | 0.77 | -0.01 |
| Fri | 62 | 10,337.09 | 166.73 | 45.16 | 2.03 | 0.21 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 108 | -3,926.80 | -36.36 | 22.22 | 0.76 | -0.11 |
| long above prev high | 112 | 9,411.65 | 84.03 | 41.07 | 1.41 | 0.20 |
| short below prev low | 89 | -37.03 | -0.42 | 21.35 | 1.00 | -0.06 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 182 | 8,021.15 | 44.07 | 30.22 | 1.29 | 0.09 |
| expansion | 127 | -2,573.33 | -20.26 | 26.77 | 0.92 | -0.10 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 120 | -45,884.08 | -382.37 | 0.00 | 0.00 | -0.59 |
| loss after progress | 100 | -13,740.56 | -137.41 | 0.00 | 0.00 | -0.38 |
| small win | 43 | 14,094.98 | 327.79 | 100.00 | 1.41e+13 | 0.42 |
| win >= 1R | 46 | 50,977.48 | 1,108.21 | 100.00 | 5.1e+13 | 2.05 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 127 | -3,060.40 |
| long | 182 | 8,508.20 |


### 2h (187 trades, net -5,396 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 42 | -5,381.19 | -128.12 | 26.19 | 0.56 | -0.09 |
| weak_bull | 63 | -8,538.30 | -135.53 | 25.40 | 0.55 | -0.18 |
| sideways | 39 | 5,840.05 | 149.74 | 41.03 | 1.72 | 0.14 |
| weak_bear | 36 | 5,767.72 | 160.21 | 41.67 | 1.90 | 0.04 |
| strong_bear | 7 | -3,083.83 | -440.55 | 14.29 | 0.06 | -0.48 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 75 | 814.35 | 10.86 | 28.00 | 1.06 | -0.04 |
| normal | 93 | -4,618.38 | -49.66 | 32.26 | 0.84 | -0.10 |
| high | 16 | -3,225.05 | -201.57 | 31.25 | 0.45 | -0.19 |
| extreme | 3 | 1,633.54 | 544.51 | 100.00 | 1.63e+12 | 1.05 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 52 | -4,490.06 | -86.35 | 21.15 | 0.70 | -0.21 |
| morning | 20 | 5,684.95 | 284.25 | 65.00 | 2.25 | 0.27 |
| midday | 41 | -2,274.89 | -55.49 | 26.83 | 0.76 | -0.11 |
| afternoon | 49 | 1,079.95 | 22.04 | 32.65 | 1.09 | 0.04 |
| closing | 25 | -5,395.50 | -215.82 | 32.00 | 0.32 | -0.15 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 15 | -1,187.46 | -79.16 | 40.00 | 0.72 | -0.12 |
| large up | 16 | 515.22 | 32.20 | 43.75 | 1.07 | 0.27 |
| medium down | 33 | 780.98 | 23.67 | 21.21 | 1.10 | -0.12 |
| medium up | 42 | -2,680.31 | -63.82 | 35.71 | 0.75 | -0.04 |
| small down | 38 | 792.79 | 20.86 | 34.21 | 1.10 | 0.02 |
| small up | 43 | -3,616.78 | -84.11 | 25.58 | 0.67 | -0.21 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 38 | -3,487.78 | -91.78 | 28.95 | 0.72 | -0.08 |
| Tue | 36 | 1,737.37 | 48.26 | 33.33 | 1.24 | 0.07 |
| Wed | 34 | -2,747.71 | -80.81 | 26.47 | 0.69 | -0.06 |
| Thu | 38 | -7,861.93 | -206.89 | 21.05 | 0.36 | -0.40 |
| Fri | 40 | 7,582.47 | 189.56 | 47.50 | 2.04 | 0.18 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 58 | -1,082.36 | -18.66 | 27.59 | 0.92 | -0.19 |
| long above prev high | 77 | 1,136.98 | 14.77 | 38.96 | 1.05 | 0.08 |
| short below prev low | 52 | -5,450.17 | -104.81 | 25.00 | 0.64 | -0.13 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 106 | 5,096.34 | 48.08 | 32.08 | 1.23 | 0.05 |
| expansion | 81 | -10,491.89 | -129.53 | 30.86 | 0.60 | -0.21 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 67 | -32,281.00 | -481.81 | 0.00 | 0.00 | -0.60 |
| loss after progress | 61 | -16,613.98 | -272.36 | 0.00 | 0.00 | -0.45 |
| small win | 34 | 12,253.63 | 360.40 | 100.00 | 1.23e+13 | 0.38 |
| win >= 1R | 25 | 31,245.80 | 1,249.83 | 100.00 | 3.12e+13 | 1.70 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 75 | -5,590.20 |
| long | 112 | 194.60 |


### 4h (90 trades, net -4,548 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 24 | -5,234.27 | -218.09 | 20.83 | 0.48 | -0.23 |
| weak_bull | 32 | -4,438.00 | -138.69 | 18.75 | 0.65 | -0.28 |
| sideways | 16 | 2,069.65 | 129.35 | 37.50 | 1.36 | 0.01 |
| weak_bear | 16 | 3,821.34 | 238.83 | 43.75 | 2.26 | 0.35 |
| strong_bear | 2 | -766.41 | -383.20 | 0.00 | 0.00 | -0.16 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 32 | -4,867.79 | -152.12 | 25.00 | 0.60 | -0.11 |
| normal | 50 | -6,040.68 | -120.81 | 24.00 | 0.68 | -0.21 |
| high | 7 | 3,612.59 | 516.08 | 42.86 | 4.39 | 0.57 |
| extreme | 1 | 2,748.19 | 2,748.19 | 100.00 | 2.75e+12 | 0.83 |

**session phase of entry**

| session | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| opening | 30 | -2,258.65 | -75.29 | 20.00 | 0.78 | -0.10 |
| morning | 18 | -2,639.75 | -146.65 | 33.33 | 0.68 | -0.25 |
| midday | 6 | -1,079.81 | -179.97 | 33.33 | 0.43 | -0.26 |
| afternoon | 24 | 2,693.09 | 112.21 | 29.17 | 1.42 | 0.13 |
| closing | 12 | -1,262.56 | -105.21 | 25.00 | 0.76 | -0.24 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 6 | -1,000.41 | -166.74 | 33.33 | 0.53 | -0.42 |
| large up | 5 | 1,637.56 | 327.51 | 60.00 | 1.77 | 0.26 |
| medium down | 17 | -2,884.80 | -169.69 | 23.53 | 0.65 | -0.21 |
| medium up | 15 | -2,964.67 | -197.64 | 26.67 | 0.51 | -0.25 |
| small down | 15 | 834.58 | 55.64 | 20.00 | 1.21 | -0.07 |
| small up | 32 | -169.94 | -5.31 | 25.00 | 0.98 | 0.03 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 21 | -2,605.38 | -124.07 | 38.10 | 0.67 | -0.06 |
| Tue | 15 | 1,446.52 | 96.43 | 33.33 | 1.30 | -0.10 |
| Wed | 18 | 701.68 | 38.98 | 22.22 | 1.11 | -0.03 |
| Thu | 20 | -1,504.04 | -75.20 | 25.00 | 0.76 | 0.00 |
| Fri | 16 | -2,586.47 | -161.65 | 12.50 | 0.62 | -0.35 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 17 | 993.42 | 58.44 | 29.41 | 1.16 | -0.17 |
| long above prev high | 54 | -4,559.29 | -84.43 | 25.93 | 0.78 | -0.13 |
| short below prev low | 19 | -981.81 | -51.67 | 26.32 | 0.80 | 0.05 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 46 | -3,391.98 | -73.74 | 28.26 | 0.75 | -0.04 |
| expansion | 44 | -1,155.70 | -26.27 | 25.00 | 0.94 | -0.16 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 36 | -22,528.76 | -625.80 | 0.00 | 0.00 | -0.57 |
| loss after progress | 30 | -9,907.00 | -330.23 | 0.00 | 0.00 | -0.42 |
| small win | 15 | 9,668.67 | 644.58 | 100.00 | 9.67e+12 | 0.41 |
| win >= 1R | 9 | 18,219.41 | 2,024.38 | 100.00 | 1.82e+13 | 1.99 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 22 | 2,676.30 |
| long | 68 | -7,224.00 |


### D1 (42 trades, net -14,866 pts)

**trend**

| trend | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| strong_bull | 9 | -2,228.09 | -247.57 | 22.22 | 0.43 | -0.06 |
| weak_bull | 16 | -7,056.67 | -441.04 | 12.50 | 0.32 | -0.28 |
| sideways | 8 | 2,256.55 | 282.07 | 37.50 | 2.26 | 0.04 |
| weak_bear | 6 | -900.59 | -150.10 | 33.33 | 0.76 | 0.03 |
| strong_bear | 3 | -6,937.34 | -2,312.45 | 0.00 | 0.00 | -0.66 |

**volatility**

| vol | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| low | 16 | 829.72 | 51.86 | 25.00 | 1.21 | -0.01 |
| normal | 22 | -10,394.57 | -472.48 | 18.18 | 0.30 | -0.23 |
| high | 3 | -7,825.61 | -2,608.54 | 0.00 | 0.00 | -0.62 |
| extreme | 1 | 2,524.32 | 2,524.32 | 100.00 | 2.52e+12 | 0.70 |

**opening gap of the entry day**

| gap | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| large down | 3 | -4,163.90 | -1,387.97 | 33.33 | 0.02 | -0.31 |
| large up | 3 | -3,503.36 | -1,167.79 | 33.33 | 0.31 | 0.07 |
| medium down | 4 | -3,827.10 | -956.77 | 0.00 | 0.00 | -0.47 |
| medium up | 3 | -1,287.91 | -429.30 | 0.00 | 0.00 | -0.38 |
| small down | 11 | 208.58 | 18.96 | 18.18 | 1.08 | -0.14 |
| small up | 18 | -2,292.45 | -127.36 | 27.78 | 0.76 | -0.07 |

**weekday**

| weekday | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| Mon | 8 | -9,766.81 | -1,220.85 | 25.00 | 0.15 | -0.23 |
| Tue | 12 | -4,031.17 | -335.93 | 16.67 | 0.41 | -0.11 |
| Wed | 9 | -5,828.67 | -647.63 | 0.00 | 0.00 | -0.49 |
| Thu | 8 | 1,418.73 | 177.34 | 37.50 | 1.93 | -0.01 |
| Fri | 5 | 3,341.78 | 668.36 | 40.00 | 3.95 | 0.21 |

**previous-day level**

| prev_day_level | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| inside prev range | 3 | 1,795.54 | 598.51 | 33.33 | 2.95 | 0.28 |
| long above prev high | 32 | -6,469.76 | -202.18 | 21.88 | 0.58 | -0.13 |
| short below prev low | 7 | -10,191.92 | -1,455.99 | 14.29 | 0.01 | -0.44 |

**consolidation vs expansion (prior 5 sessions)**

| consolidation | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| consolidation | 24 | -665.31 | -27.72 | 29.17 | 0.92 | -0.06 |
| expansion | 18 | -14,200.83 | -788.94 | 11.11 | 0.24 | -0.29 |

**trade outcome type**

| outcome | trades | net_pts | exp_pts | win_pct | pf | exp_r |
|---|---|---|---|---|---|---|
| failed breakout (loss, MFE < 0.3R) | 15 | -16,328.09 | -1,088.54 | 0.00 | 0.00 | -0.51 |
| loss after progress | 18 | -10,436.42 | -579.80 | 0.00 | 0.00 | -0.40 |
| small win | 4 | 2,863.54 | 715.88 | 100.00 | 2.86e+12 | 0.22 |
| win >= 1R | 5 | 9,034.84 | 1,806.97 | 100.00 | 9.03e+12 | 1.48 |

**direction**

| side | trades | net_pts |
|---|---|---|
| short | 7 | -10,191.90 |
| long | 35 | -4,674.20 |
