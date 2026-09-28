# Loss Pattern Report - Previous-Day Volume Zones strategy on XAUUSD 5-min

Base: 2,049 trades, 1,519 losses (74.1%), 530 wins, total +69.7R gross. Every loss is exactly -1R (stop at the rectangle edge) and every win +3R, so 'negative R contribution' of a bucket equals its number of losses; what separates buckets is the WIN RATE against the 25% break-even. 'Lift' = the bucket's loss rate divided by the overall loss rate (1.00 = no different). 'z' = two-proportion z-score of the bucket's win rate against all other trades; |z| >= 2 is the usual significance bar, and with 40+ buckets a few |z| of 2 appear by chance.

## How to read the tables

- Conditions known BEFORE entry can become filters. Conditions marked post-hoc (false breakout, immediate reversal) describe HOW trades lose, not what to filter on.

## All conditions

### Side

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| short | 1004 | 255 | 749 | 25.4% | +0.013 | +13.0 | 1.02 | 49.3% | 1.01 | -0.5 |
| long | 1045 | 275 | 770 | 26.3% | +0.054 | +56.7 | 1.07 | 50.7% | 0.99 | +0.5 |

### Rectangle type

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| HVN | 1316 | 331 | 985 | 25.2% | +0.004 | +5.6 | 1.01 | 64.8% | 1.01 | -1.0 |
| PDL | 353 | 91 | 262 | 25.8% | +0.031 | +10.8 | 1.04 | 17.2% | 1.00 | -0.0 |
| PDH | 380 | 108 | 272 | 28.4% | +0.140 | +53.3 | 1.20 | 17.9% | 0.97 | +1.3 |

### Session (UTC)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| NY late 17-21 UTC | 667 | 172 | 495 | 25.8% | +0.031 | +21.0 | 1.04 | 32.6% | 1.00 | -0.1 |
| NY overlap 12-17 UTC | 414 | 108 | 306 | 26.1% | +0.039 | +16.3 | 1.05 | 20.1% | 1.00 | +0.1 |
| Asia 00-07 UTC | 531 | 132 | 399 | 24.9% | -0.006 | -3.1 | 0.99 | 26.3% | 1.01 | -0.6 |
| London 07-12 UTC | 259 | 72 | 187 | 27.8% | +0.114 | +29.5 | 1.16 | 12.3% | 0.97 | +0.8 |
| Close 21-24 UTC | 178 | 46 | 132 | 25.8% | +0.034 | +6.0 | 1.05 | 8.7% | 1.00 | -0.0 |

### Hour (IST)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 00 | 460 | 123 | 337 | 26.7% | +0.059 | +27.3 | 1.08 | 22.2% | 0.99 | +0.5 |
| 19 | 128 | 32 | 96 | 25.0% | -0.025 | -3.2 | 0.97 | 6.3% | 1.01 | -0.2 |
| 08 | 69 | 15 | 54 | 21.7% | -0.130 | -9.0 | 0.83 | 3.6% | 1.06 | -0.8 |
| 17 | 49 | 11 | 38 | 22.4% | -0.102 | -5.0 | 0.87 | 2.5% | 1.05 | -0.6 |
| 01 | 147 | 32 | 115 | 21.8% | -0.103 | -15.1 | 0.87 | 7.6% | 1.06 | -1.2 |
| 14 | 60 | 23 | 37 | 38.3% | +0.533 | +32.0 | 1.86 | 2.4% | 0.83 | +2.2 |
| 03 | 83 | 26 | 57 | 31.3% | +0.253 | +21.0 | 1.37 | 3.8% | 0.93 | +1.2 |
| 05 | 93 | 23 | 70 | 24.7% | -0.011 | -1.1 | 0.98 | 4.6% | 1.02 | -0.3 |
| 11 | 66 | 22 | 44 | 33.3% | +0.333 | +22.0 | 1.50 | 2.9% | 0.90 | +1.4 |
| 16 | 38 | 10 | 28 | 26.3% | +0.053 | +2.0 | 1.07 | 1.8% | 0.99 | +0.1 |
| 20 | 88 | 21 | 67 | 23.9% | -0.045 | -4.0 | 0.94 | 4.4% | 1.03 | -0.4 |
| 18 | 120 | 35 | 85 | 29.2% | +0.179 | +21.5 | 1.25 | 5.6% | 0.96 | +0.9 |
| 09 | 37 | 11 | 26 | 29.7% | +0.189 | +7.0 | 1.27 | 1.7% | 0.95 | +0.5 |
| 02 | 43 | 13 | 30 | 30.2% | +0.228 | +9.8 | 1.33 | 2.0% | 0.94 | +0.7 |
| 10 | 40 | 11 | 29 | 27.5% | +0.099 | +4.0 | 1.14 | 1.9% | 0.98 | +0.2 |
| 07 | 92 | 19 | 73 | 20.7% | -0.174 | -16.0 | 0.78 | 4.8% | 1.07 | -1.2 |
| 15 | 36 | 6 | 30 | 16.7% | -0.333 | -12.0 | 0.60 | 2.0% | 1.12 | -1.3 |
| 06 | 125 | 29 | 96 | 23.2% | -0.072 | -9.0 | 0.91 | 6.3% | 1.04 | -0.7 |
| 23 | 17 | 5 | 12 | 29.4% | +0.176 | +3.0 | 1.25 | 0.8% | 0.95 | +0.3 |
| 13 | 79 | 21 | 58 | 26.6% | +0.070 | +5.5 | 1.10 | 3.8% | 0.99 | +0.1 |
| 21 | 39 | 10 | 29 | 25.6% | +0.026 | +1.0 | 1.03 | 1.9% | 1.00 | -0.0 |
| 04 | 61 | 13 | 48 | 21.3% | -0.148 | -9.0 | 0.81 | 3.2% | 1.06 | -0.8 |
| 12 | 62 | 14 | 48 | 22.6% | -0.097 | -6.0 | 0.88 | 3.2% | 1.04 | -0.6 |
| 22 | 17 | 5 | 12 | 29.4% | +0.176 | +3.0 | 1.25 | 0.8% | 0.95 | +0.3 |

### Day of week

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| Thu | 460 | 129 | 331 | 28.0% | +0.122 | +56.0 | 1.17 | 21.8% | 0.97 | +1.2 |
| Fri | 419 | 118 | 301 | 28.2% | +0.125 | +52.2 | 1.17 | 19.8% | 0.97 | +1.2 |
| Sat | 109 | 25 | 84 | 22.9% | -0.098 | -10.6 | 0.89 | 5.5% | 1.04 | -0.7 |
| Mon | 242 | 62 | 180 | 25.6% | +0.025 | +6.0 | 1.03 | 11.8% | 1.00 | -0.1 |
| Tue | 426 | 104 | 322 | 24.4% | -0.024 | -10.1 | 0.97 | 21.2% | 1.02 | -0.8 |
| Wed | 393 | 92 | 301 | 23.4% | -0.060 | -23.8 | 0.92 | 19.8% | 1.03 | -1.2 |

### False breakout (close back inside within 3 bars)  _(post-hoc pattern, not known at entry)_

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| yes | 884 | 89 | 795 | 10.1% | -0.609 | -538.2 | 0.33 | 52.3% | 1.21 | -14.2 |
| no | 1165 | 441 | 724 | 37.9% | +0.522 | +607.9 | 1.84 | 47.7% | 0.84 | +14.2 |

### Immediate reversal (-0.5R within 15 min)  _(post-hoc pattern)_

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| yes | 857 | 111 | 746 | 13.0% | -0.490 | -419.8 | 0.44 | 49.1% | 1.17 | -11.3 |
| no | 1192 | 419 | 773 | 35.2% | +0.411 | +489.6 | 1.63 | 50.9% | 0.87 | +11.3 |

### Tap on the confirmation candle itself

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| same bar | 1195 | 295 | 900 | 24.7% | -0.021 | -25.6 | 0.97 | 59.2% | 1.02 | -1.4 |
| earlier bar | 854 | 235 | 619 | 27.5% | +0.112 | +95.3 | 1.15 | 40.8% | 0.98 | +1.4 |

### Bars between tap and confirmation

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1195 | 295 | 900 | 24.7% | -0.021 | -25.6 | 0.97 | 59.2% | 1.02 | -1.4 |
| 3-5 | 128 | 30 | 98 | 23.4% | -0.048 | -6.2 | 0.94 | 6.5% | 1.03 | -0.6 |
| 1-2 | 642 | 177 | 465 | 27.6% | +0.113 | +72.5 | 1.16 | 30.6% | 0.98 | +1.2 |
| 6-11 | 84 | 28 | 56 | 33.3% | +0.344 | +28.9 | 1.52 | 3.7% | 0.90 | +1.6 |

### Touch count on the rectangle today

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 3-4 | 419 | 118 | 301 | 28.2% | +0.119 | +49.7 | 1.16 | 19.8% | 0.97 | +1.2 |
| 1 (first touch) | 835 | 209 | 626 | 25.0% | -0.005 | -4.3 | 0.99 | 41.2% | 1.01 | -0.7 |
| 2 | 494 | 133 | 361 | 26.9% | +0.086 | +42.7 | 1.12 | 23.8% | 0.99 | +0.6 |
| 5+ | 301 | 70 | 231 | 23.3% | -0.061 | -18.3 | 0.92 | 15.2% | 1.04 | -1.1 |

### Weak tap (wick past POC < 10% of rectangle)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| weak | 411 | 102 | 309 | 24.8% | -0.019 | -7.7 | 0.98 | 20.3% | 1.01 | -0.5 |
| deep | 1638 | 428 | 1210 | 26.1% | +0.047 | +77.4 | 1.06 | 79.7% | 1.00 | +0.5 |

### Tap depth past POC (rectangle heights)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.00 to 0.14 | 513 | 134 | 379 | 26.1% | +0.044 | +22.7 | 1.06 | 25.0% | 1.00 | +0.2 |
| 0.84 to 19.09 | 512 | 118 | 394 | 23.0% | -0.075 | -38.6 | 0.90 | 25.9% | 1.04 | -1.7 |
| 0.14 to 0.35 | 512 | 137 | 375 | 26.8% | +0.071 | +36.5 | 1.10 | 24.7% | 0.99 | +0.5 |
| 0.35 to 0.84 | 512 | 141 | 371 | 27.5% | +0.096 | +49.2 | 1.13 | 24.4% | 0.98 | +1.0 |

### Tap candle closed inside the rectangle

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| no | 1430 | 362 | 1068 | 25.3% | +0.006 | +8.7 | 1.01 | 70.3% | 1.01 | -0.9 |
| yes | 619 | 168 | 451 | 27.1% | +0.099 | +61.0 | 1.13 | 29.7% | 0.98 | +0.9 |

### Rectangle height (USD)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.19 to 1.19 | 514 | 124 | 390 | 24.1% | -0.035 | -18.1 | 0.95 | 25.7% | 1.02 | -1.0 |
| 1.19 to 2.03 | 511 | 143 | 368 | 28.0% | +0.114 | +58.2 | 1.16 | 24.2% | 0.97 | +1.3 |
| 2.03 to 3.95 | 512 | 135 | 377 | 26.4% | +0.054 | +27.5 | 1.07 | 24.8% | 0.99 | +0.3 |
| 3.95 to 37.90 | 512 | 128 | 384 | 25.0% | +0.004 | +2.1 | 1.01 | 25.3% | 1.01 | -0.5 |

### Rectangle height (% of prior day range)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 5.0 to 7.5 | 506 | 138 | 368 | 27.3% | +0.096 | +48.6 | 1.13 | 24.2% | 0.98 | +0.8 |
| 2.5 to 5.0 | 523 | 131 | 392 | 25.0% | -0.001 | -0.7 | 1.00 | 25.8% | 1.01 | -0.5 |
| 7.5 to 7.5 | 509 | 128 | 381 | 25.1% | +0.003 | +1.7 | 1.00 | 25.1% | 1.01 | -0.4 |
| 5.0 to 5.0 | 511 | 133 | 378 | 26.0% | +0.040 | +20.2 | 1.05 | 24.9% | 1.00 | +0.1 |

### Confirmation candle range / ATR14

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.98 to 1.39 | 512 | 122 | 390 | 23.8% | -0.059 | -30.2 | 0.92 | 25.7% | 1.03 | -1.2 |
| 2.06 to 23.24 | 512 | 130 | 382 | 25.4% | +0.019 | +10.0 | 1.03 | 25.1% | 1.01 | -0.3 |
| 1.39 to 2.06 | 512 | 128 | 384 | 25.0% | -0.001 | -0.6 | 1.00 | 25.3% | 1.01 | -0.5 |
| 0.17 to 0.98 | 513 | 150 | 363 | 29.2% | +0.176 | +90.5 | 1.25 | 23.9% | 0.95 | +2.0 |

### Confirmation candle range / rectangle height

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.88 to 1.41 | 512 | 139 | 373 | 27.1% | +0.064 | +32.9 | 1.09 | 24.6% | 0.98 | +0.8 |
| 2.52 to 34.53 | 512 | 124 | 388 | 24.2% | -0.028 | -14.6 | 0.96 | 25.5% | 1.02 | -1.0 |
| 0.14 to 0.88 | 513 | 128 | 385 | 25.0% | +0.013 | +6.8 | 1.02 | 25.3% | 1.01 | -0.5 |
| 1.41 to 2.52 | 512 | 139 | 373 | 27.1% | +0.087 | +44.5 | 1.12 | 24.6% | 0.98 | +0.8 |

### Large confirmation candle (range > 2 ATR)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| no | 1511 | 394 | 1117 | 26.1% | +0.041 | +61.8 | 1.05 | 73.5% | 1.00 | +0.4 |
| yes | 538 | 136 | 402 | 25.3% | +0.015 | +8.0 | 1.02 | 26.5% | 1.01 | -0.4 |

### Confirmation body / range

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.66 to 0.82 | 512 | 113 | 399 | 22.1% | -0.126 | -64.7 | 0.84 | 26.3% | 1.05 | -2.3 |
| 0.82 to 1.00 | 512 | 139 | 373 | 27.1% | +0.094 | +48.0 | 1.13 | 24.6% | 0.98 | +0.8 |
| 0.00 to 0.46 | 513 | 146 | 367 | 28.5% | +0.138 | +71.0 | 1.19 | 24.2% | 0.97 | +1.5 |
| 0.46 to 0.66 | 512 | 132 | 380 | 25.8% | +0.030 | +15.5 | 1.04 | 25.0% | 1.00 | -0.1 |

### Close beyond the rectangle edge (rectangle heights)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.19 to 0.51 | 512 | 138 | 374 | 27.0% | +0.068 | +35.0 | 1.09 | 24.6% | 0.99 | +0.6 |
| 1.25 to 25.19 | 512 | 130 | 382 | 25.4% | +0.019 | +10.0 | 1.03 | 25.1% | 1.01 | -0.3 |
| -0.00 to 0.19 | 513 | 127 | 386 | 24.8% | -0.002 | -0.9 | 1.00 | 25.4% | 1.01 | -0.7 |
| 0.51 to 1.25 | 512 | 135 | 377 | 26.4% | +0.050 | +25.7 | 1.07 | 24.8% | 0.99 | +0.3 |

### Entry distance from POC (rectangle heights)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.67 to 1.01 | 512 | 136 | 376 | 26.6% | +0.050 | +25.6 | 1.07 | 24.8% | 0.99 | +0.4 |
| 1.73 to 25.69 | 512 | 128 | 384 | 25.0% | +0.004 | +2.0 | 1.01 | 25.3% | 1.01 | -0.5 |
| 0.25 to 0.67 | 513 | 124 | 389 | 24.2% | -0.027 | -13.9 | 0.96 | 25.6% | 1.02 | -1.0 |
| 1.01 to 1.73 | 512 | 142 | 370 | 27.7% | +0.110 | +56.1 | 1.15 | 24.4% | 0.97 | +1.1 |

### Entry distance from POC (R)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.54 to 0.68 | 512 | 111 | 401 | 21.7% | -0.142 | -72.7 | 0.82 | 26.4% | 1.06 | -2.5 |
| 0.82 to 0.98 | 512 | 143 | 369 | 27.9% | +0.123 | +62.9 | 1.17 | 24.3% | 0.97 | +1.2 |
| 0.25 to 0.54 | 513 | 135 | 378 | 26.3% | +0.053 | +27.1 | 1.07 | 24.9% | 0.99 | +0.3 |
| 0.68 to 0.82 | 512 | 141 | 371 | 27.5% | +0.102 | +52.4 | 1.14 | 24.4% | 0.98 | +1.0 |

### Risk in USD

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.23 to 1.99 | 513 | 133 | 380 | 25.9% | +0.038 | +19.5 | 1.05 | 25.0% | 1.00 | +0.0 |
| 1.99 to 3.52 | 512 | 120 | 392 | 23.4% | -0.069 | -35.5 | 0.91 | 25.8% | 1.03 | -1.4 |
| 3.52 to 7.12 | 512 | 137 | 375 | 26.8% | +0.056 | +28.9 | 1.08 | 24.7% | 0.99 | +0.5 |
| 7.12 to 85.39 | 512 | 140 | 372 | 27.3% | +0.111 | +56.8 | 1.15 | 24.5% | 0.98 | +0.9 |

### Risk / ATR14

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.68 to 2.33 | 512 | 119 | 393 | 23.2% | -0.079 | -40.4 | 0.90 | 25.9% | 1.04 | -1.6 |
| 0.22 to 1.20 | 513 | 142 | 371 | 27.7% | +0.107 | +55.0 | 1.15 | 24.4% | 0.98 | +1.1 |
| 1.20 to 1.68 | 512 | 128 | 384 | 25.0% | -0.006 | -2.8 | 0.99 | 25.3% | 1.01 | -0.5 |
| 2.33 to 27.11 | 512 | 141 | 371 | 27.5% | +0.113 | +58.0 | 1.16 | 24.4% | 0.98 | +1.0 |

### Volatility regime (ATR14 / its 7-day median)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.28 to 0.81 | 513 | 114 | 399 | 22.2% | -0.094 | -48.5 | 0.88 | 26.3% | 1.05 | -2.2 |
| 1.37 to 6.54 | 512 | 127 | 385 | 24.8% | -0.009 | -4.7 | 0.99 | 25.3% | 1.01 | -0.6 |
| 0.81 to 1.03 | 512 | 152 | 360 | 29.7% | +0.180 | +92.3 | 1.25 | 23.7% | 0.95 | +2.3 |
| 1.03 to 1.37 | 512 | 137 | 375 | 26.8% | +0.060 | +30.6 | 1.08 | 24.7% | 0.99 | +0.5 |

### High volatility (ATR > 1.5x median)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| no | 1640 | 430 | 1210 | 26.2% | +0.048 | +79.5 | 1.06 | 79.7% | 1.00 | +0.7 |
| yes | 409 | 100 | 309 | 24.4% | -0.024 | -9.7 | 0.97 | 20.3% | 1.02 | -0.7 |

### Nearest other rectangle (gap in rectangle heights)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 3.50 to 17.00 | 512 | 126 | 386 | 24.6% | -0.015 | -7.5 | 0.98 | 25.4% | 1.02 | -0.7 |
| 2.00 to 3.50 | 511 | 138 | 373 | 27.0% | +0.082 | +42.1 | 1.11 | 24.6% | 0.98 | +0.7 |
| 1.33 to 2.00 | 513 | 137 | 376 | 26.7% | +0.071 | +36.4 | 1.10 | 24.8% | 0.99 | +0.5 |
| -0.00 to 1.33 | 513 | 129 | 384 | 25.1% | -0.003 | -1.3 | 1.00 | 25.3% | 1.01 | -0.4 |

### Rectangles too close (gap < 1 rectangle height)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| no | 1771 | 456 | 1315 | 25.7% | +0.027 | +47.5 | 1.04 | 86.6% | 1.00 | -0.3 |
| yes | 278 | 74 | 204 | 26.6% | +0.080 | +22.2 | 1.11 | 13.4% | 0.99 | +0.3 |

### Rectangles on the day

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 87 | 23 | 64 | 26.4% | +0.057 | +5.0 | 1.08 | 4.2% | 0.99 | +0.1 |
| 4 | 490 | 131 | 359 | 26.7% | +0.065 | +31.9 | 1.09 | 23.6% | 0.99 | +0.5 |
| 5 | 808 | 206 | 602 | 25.5% | +0.014 | +11.5 | 1.02 | 39.6% | 1.01 | -0.3 |
| 6 | 664 | 170 | 494 | 25.6% | +0.032 | +21.3 | 1.04 | 32.5% | 1.00 | -0.2 |

### Rectangle volume share of the day

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 12.4 to 39.4 | 512 | 129 | 383 | 25.2% | +0.002 | +1.0 | 1.00 | 25.2% | 1.01 | -0.4 |
| 0.0 to 1.4 | 513 | 146 | 367 | 28.5% | +0.139 | +71.5 | 1.19 | 24.2% | 0.97 | +1.5 |
| 6.7 to 12.4 | 512 | 138 | 374 | 27.0% | +0.079 | +40.6 | 1.11 | 24.6% | 0.99 | +0.6 |
| 1.4 to 6.7 | 512 | 117 | 395 | 22.9% | -0.085 | -43.4 | 0.89 | 26.0% | 1.04 | -1.8 |

### Target beyond the prior day's High/Low

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| no | 1221 | 295 | 926 | 24.2% | -0.038 | -46.0 | 0.95 | 61.0% | 1.02 | -2.1 |
| yes | 828 | 235 | 593 | 28.4% | +0.140 | +115.7 | 1.20 | 39.0% | 0.97 | +2.1 |

### Room to prior day High/Low (R)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 3-6R | 433 | 92 | 341 | 21.2% | -0.171 | -74.2 | 0.79 | 22.4% | 1.06 | -2.5 |
| past it already | 394 | 114 | 280 | 28.9% | +0.163 | +64.4 | 1.23 | 18.4% | 0.96 | +1.5 |
| >6R | 788 | 203 | 585 | 25.8% | +0.036 | +28.2 | 1.05 | 38.5% | 1.00 | -0.1 |
| 1.5-3R | 245 | 62 | 183 | 25.3% | +0.018 | +4.4 | 1.02 | 12.0% | 1.01 | -0.2 |
| 0-1.5R | 189 | 59 | 130 | 31.2% | +0.249 | +47.0 | 1.36 | 8.6% | 0.93 | +1.8 |

### Prior day range (USD)

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 7.60 to 21.58 | 517 | 127 | 390 | 24.6% | -0.017 | -8.5 | 0.98 | 25.7% | 1.02 | -0.8 |
| 21.58 to 37.75 | 511 | 139 | 372 | 27.2% | +0.081 | +41.5 | 1.11 | 24.5% | 0.98 | +0.8 |
| 37.75 to 77.21 | 511 | 140 | 371 | 27.4% | +0.092 | +46.8 | 1.12 | 24.4% | 0.98 | +0.9 |
| 77.21 to 757.99 | 510 | 124 | 386 | 24.3% | -0.020 | -10.0 | 0.97 | 25.4% | 1.02 | -0.9 |

### Trades already taken today

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 (first) | 832 | 211 | 621 | 25.4% | +0.016 | +13.0 | 1.02 | 40.9% | 1.01 | -0.4 |
| 1 | 620 | 161 | 459 | 26.0% | +0.040 | +24.9 | 1.05 | 30.2% | 1.00 | +0.1 |
| 2 | 357 | 90 | 267 | 25.2% | +0.008 | +3.0 | 1.01 | 17.6% | 1.01 | -0.3 |
| 3+ | 240 | 68 | 172 | 28.3% | +0.120 | +28.9 | 1.16 | 11.3% | 0.97 | +0.9 |

### Previous trade result

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 1 | 0 | 1 | 0.0% | -1.000 | -1.0 | 0.00 | 0.1% | 1.35 | -0.6 |
| loss | 1514 | 383 | 1131 | 25.3% | +0.009 | +13.0 | 1.01 | 74.5% | 1.01 | -1.0 |
| win | 534 | 147 | 387 | 27.5% | +0.108 | +57.8 | 1.15 | 25.5% | 0.98 | +1.0 |

### Year

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 61 | 16 | 45 | 26.2% | +0.049 | +3.0 | 1.07 | 3.0% | 1.00 | +0.1 |
| 2022 | 263 | 68 | 195 | 25.9% | +0.034 | +9.0 | 1.05 | 12.8% | 1.00 | -0.0 |
| 2023 | 414 | 111 | 303 | 26.8% | +0.074 | +30.5 | 1.10 | 19.9% | 0.99 | +0.5 |
| 2024 | 266 | 53 | 213 | 19.9% | -0.216 | -57.5 | 0.73 | 14.0% | 1.08 | -2.4 |
| 2025 | 566 | 166 | 400 | 29.3% | +0.184 | +104.0 | 1.26 | 26.3% | 0.95 | +2.2 |
| 2026 | 479 | 116 | 363 | 24.2% | -0.040 | -19.2 | 0.95 | 23.9% | 1.02 | -0.9 |

### Side x rectangle type

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| short HVN | 642 | 161 | 481 | 25.1% | -0.002 | -1.0 | 1.00 | 31.7% | 1.01 | -0.6 |
| short PDL | 174 | 47 | 127 | 27.0% | +0.084 | +14.5 | 1.11 | 8.4% | 0.98 | +0.4 |
| long HVN | 674 | 170 | 504 | 25.2% | +0.010 | +6.7 | 1.01 | 33.2% | 1.01 | -0.5 |
| short PDH | 188 | 47 | 141 | 25.0% | -0.003 | -0.5 | 1.00 | 9.3% | 1.01 | -0.3 |
| long PDL | 179 | 44 | 135 | 24.6% | -0.021 | -3.8 | 0.97 | 8.9% | 1.02 | -0.4 |
| long PDH | 192 | 61 | 131 | 31.8% | +0.280 | +53.8 | 1.41 | 8.6% | 0.92 | +2.0 |

### Side x session

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| short NY late 17-21 UTC | 353 | 87 | 266 | 24.6% | -0.015 | -5.4 | 0.98 | 17.5% | 1.02 | -0.6 |
| short NY overlap 12-17 UTC | 204 | 57 | 147 | 27.9% | +0.102 | +20.9 | 1.14 | 9.7% | 0.97 | +0.7 |
| long NY late 17-21 UTC | 314 | 85 | 229 | 27.1% | +0.084 | +26.3 | 1.11 | 15.1% | 0.98 | +0.5 |
| short Asia 00-07 UTC | 245 | 54 | 191 | 22.0% | -0.118 | -29.0 | 0.85 | 12.6% | 1.05 | -1.5 |
| long London 07-12 UTC | 127 | 30 | 97 | 23.6% | -0.055 | -7.0 | 0.93 | 6.4% | 1.03 | -0.6 |
| long Close 21-24 UTC | 108 | 31 | 77 | 28.7% | +0.148 | +16.0 | 1.21 | 5.1% | 0.96 | +0.7 |
| long Asia 00-07 UTC | 286 | 78 | 208 | 27.3% | +0.091 | +25.9 | 1.12 | 13.7% | 0.98 | +0.6 |
| long NY overlap 12-17 UTC | 210 | 51 | 159 | 24.3% | -0.022 | -4.6 | 0.97 | 10.5% | 1.02 | -0.6 |
| short London 07-12 UTC | 132 | 42 | 90 | 31.8% | +0.277 | +36.5 | 1.41 | 5.9% | 0.92 | +1.6 |
| short Close 21-24 UTC | 70 | 15 | 55 | 21.4% | -0.143 | -10.0 | 0.82 | 3.6% | 1.06 | -0.9 |

### Rectangle type x session

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| HVN NY late 17-21 UTC | 465 | 124 | 341 | 26.7% | +0.068 | +31.8 | 1.09 | 22.4% | 0.99 | +0.4 |
| PDL NY overlap 12-17 UTC | 90 | 21 | 69 | 23.3% | -0.067 | -6.0 | 0.91 | 4.5% | 1.03 | -0.6 |
| HVN Asia 00-07 UTC | 349 | 80 | 269 | 22.9% | -0.083 | -29.0 | 0.89 | 17.7% | 1.04 | -1.4 |
| PDH NY overlap 12-17 UTC | 102 | 32 | 70 | 31.4% | +0.269 | +27.4 | 1.39 | 4.6% | 0.93 | +1.3 |
| HVN London 07-12 UTC | 160 | 39 | 121 | 24.4% | -0.025 | -4.0 | 0.97 | 8.0% | 1.02 | -0.4 |
| HVN Close 21-24 UTC | 120 | 33 | 87 | 27.5% | +0.100 | +12.0 | 1.14 | 5.7% | 0.98 | +0.4 |
| PDL Asia 00-07 UTC | 88 | 24 | 64 | 27.3% | +0.090 | +7.9 | 1.12 | 4.2% | 0.98 | +0.3 |
| PDL NY late 17-21 UTC | 95 | 23 | 72 | 24.2% | -0.039 | -3.7 | 0.95 | 4.7% | 1.02 | -0.4 |
| HVN NY overlap 12-17 UTC | 222 | 55 | 167 | 24.8% | -0.023 | -5.1 | 0.97 | 11.0% | 1.01 | -0.4 |
| PDL London 07-12 UTC | 53 | 15 | 38 | 28.3% | +0.142 | +7.6 | 1.20 | 2.5% | 0.97 | +0.4 |
| PDH London 07-12 UTC | 46 | 18 | 28 | 39.1% | +0.565 | +26.0 | 1.93 | 1.8% | 0.82 | +2.1 |
| PDH NY late 17-21 UTC | 107 | 25 | 82 | 23.4% | -0.066 | -7.1 | 0.91 | 5.4% | 1.03 | -0.6 |
| PDH Asia 00-07 UTC | 94 | 28 | 66 | 29.8% | +0.191 | +18.0 | 1.27 | 4.3% | 0.95 | +0.9 |
| PDH Close 21-24 UTC | 31 | 5 | 26 | 16.1% | -0.355 | -11.0 | 0.58 | 1.7% | 1.13 | -1.2 |
| PDL Close 21-24 UTC | 27 | 8 | 19 | 29.6% | +0.185 | +5.0 | 1.26 | 1.3% | 0.95 | +0.4 |

### Side x first touch

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| short repeat | 605 | 158 | 447 | 26.1% | +0.051 | +30.7 | 1.07 | 29.4% | 1.00 | +0.2 |
| short first touch | 399 | 97 | 302 | 24.3% | -0.044 | -17.6 | 0.94 | 19.9% | 1.02 | -0.8 |
| long repeat | 609 | 163 | 446 | 26.8% | +0.071 | +43.3 | 1.10 | 29.4% | 0.99 | +0.6 |
| long first touch | 436 | 112 | 324 | 25.7% | +0.031 | +13.4 | 1.04 | 21.3% | 1.00 | -0.1 |

### Session x volatility

| bucket | n | wins | losses | win_rate | avg_R | sum_R | pf | share_of_losses | lift | z_vs_rest |
|---|---|---|---|---|---|---|---|---|---|---|
| NY late 17-21 UTC normal | 557 | 144 | 413 | 25.9% | +0.035 | +19.7 | 1.05 | 27.2% | 1.00 | -0.0 |
| NY overlap 12-17 UTC high vol | 232 | 56 | 176 | 24.1% | -0.034 | -8.0 | 0.95 | 11.6% | 1.02 | -0.6 |
| Asia 00-07 UTC normal | 501 | 125 | 376 | 25.0% | -0.002 | -1.1 | 1.00 | 24.8% | 1.01 | -0.5 |
| NY overlap 12-17 UTC normal | 182 | 52 | 130 | 28.6% | +0.133 | +24.3 | 1.18 | 8.6% | 0.96 | +0.9 |
| London 07-12 UTC normal | 238 | 66 | 172 | 27.7% | +0.112 | +26.5 | 1.15 | 11.3% | 0.97 | +0.7 |
| Close 21-24 UTC normal | 162 | 43 | 119 | 26.5% | +0.062 | +10.0 | 1.08 | 7.8% | 0.99 | +0.2 |
| NY late 17-21 UTC high vol | 110 | 28 | 82 | 25.5% | +0.012 | +1.3 | 1.02 | 5.4% | 1.01 | -0.1 |
| London 07-12 UTC high vol | 21 | 6 | 15 | 28.6% | +0.143 | +3.0 | 1.20 | 1.0% | 0.96 | +0.3 |
| Close 21-24 UTC high vol | 16 | 3 | 13 | 18.8% | -0.250 | -4.0 | 0.69 | 0.9% | 1.10 | -0.7 |
| Asia 00-07 UTC high vol | 30 | 7 | 23 | 23.3% | -0.067 | -2.0 | 0.91 | 1.5% | 1.03 | -0.3 |


## Ranked findings

### Most frequent losing conditions (loss rate above average, ranked by number of losses)

| family | bucket | n | losses | share_of_losses | win_rate | lift | sum_R | z_vs_rest |
|---|---|---|---|---|---|---|---|---|
| Entry distance from POC (R) | 0.54 to 0.68 | 512 | 401 | 26.4% | 21.7% | 1.06 | -72.7 | -2.5 |
| Confirmation body / range | 0.66 to 0.82 | 512 | 399 | 26.3% | 22.1% | 1.05 | -64.7 | -2.3 |
| Room to prior day High/Low (R) | 3-6R | 433 | 341 | 22.4% | 21.2% | 1.06 | -74.2 | -2.5 |
| Year | 2024 | 266 | 213 | 14.0% | 19.9% | 1.08 | -57.5 | -2.4 |
| Side x session | short Asia 00-07 UTC | 245 | 191 | 12.6% | 22.0% | 1.05 | -29.0 | -1.5 |
| Hour (IST) | 01 | 147 | 115 | 7.6% | 21.8% | 1.06 | -15.1 | -1.2 |
| Hour (IST) | 07 | 92 | 73 | 4.8% | 20.7% | 1.07 | -16.0 | -1.2 |
| Side x session | short Close 21-24 UTC | 70 | 55 | 3.6% | 21.4% | 1.06 | -10.0 | -0.9 |
| Hour (IST) | 08 | 69 | 54 | 3.6% | 21.7% | 1.06 | -9.0 | -0.8 |
| Hour (IST) | 04 | 61 | 48 | 3.2% | 21.3% | 1.06 | -9.0 | -0.8 |


### Buckets that lose the most money (lowest average R, n >= 60)

| family | bucket | n | win_rate | avg_R | sum_R | z_vs_rest |
|---|---|---|---|---|---|---|
| Year | 2024 | 266 | 19.9% | -0.216 | -57.5 | -2.4 |
| Hour (IST) | 07 | 92 | 20.7% | -0.174 | -16.0 | -1.2 |
| Room to prior day High/Low (R) | 3-6R | 433 | 21.2% | -0.171 | -74.2 | -2.5 |
| Hour (IST) | 04 | 61 | 21.3% | -0.148 | -9.0 | -0.8 |
| Side x session | short Close 21-24 UTC | 70 | 21.4% | -0.143 | -10.0 | -0.9 |
| Entry distance from POC (R) | 0.54 to 0.68 | 512 | 21.7% | -0.142 | -72.7 | -2.5 |
| Hour (IST) | 08 | 69 | 21.7% | -0.130 | -9.0 | -0.8 |
| Confirmation body / range | 0.66 to 0.82 | 512 | 22.1% | -0.126 | -64.7 | -2.3 |
| Side x session | short Asia 00-07 UTC | 245 | 22.0% | -0.118 | -29.0 | -1.5 |
| Hour (IST) | 01 | 147 | 21.8% | -0.103 | -15.1 | -1.2 |
| Day of week | Sat | 109 | 22.9% | -0.098 | -10.6 | -0.7 |
| Hour (IST) | 12 | 62 | 22.6% | -0.097 | -6.0 | -0.6 |
| Volatility regime (ATR14 / its 7-day median) | 0.28 to 0.81 | 513 | 22.2% | -0.094 | -48.5 | -2.2 |
| Rectangle volume share of the day | 1.4 to 6.7 | 512 | 22.9% | -0.085 | -43.4 | -1.8 |
| Rectangle type x session | HVN Asia 00-07 UTC | 349 | 22.9% | -0.083 | -29.0 | -1.4 |


### Buckets that make the most money (highest average R, n >= 60)

| family | bucket | n | win_rate | avg_R | sum_R | z_vs_rest |
|---|---|---|---|---|---|---|
| Hour (IST) | 14 | 60 | 38.3% | +0.533 | +32.0 | +2.2 |
| Bars between tap and confirmation | 6-11 | 84 | 33.3% | +0.344 | +28.9 | +1.6 |
| Hour (IST) | 11 | 66 | 33.3% | +0.333 | +22.0 | +1.4 |
| Side x rectangle type | long PDH | 192 | 31.8% | +0.280 | +53.8 | +2.0 |
| Side x session | short London 07-12 UTC | 132 | 31.8% | +0.277 | +36.5 | +1.6 |
| Rectangle type x session | PDH NY overlap 12-17 UTC | 102 | 31.4% | +0.269 | +27.4 | +1.3 |
| Hour (IST) | 03 | 83 | 31.3% | +0.253 | +21.0 | +1.2 |
| Room to prior day High/Low (R) | 0-1.5R | 189 | 31.2% | +0.249 | +47.0 | +1.8 |
| Rectangle type x session | PDH Asia 00-07 UTC | 94 | 29.8% | +0.191 | +18.0 | +0.9 |
| Year | 2025 | 566 | 29.3% | +0.184 | +104.0 | +2.2 |
| Volatility regime (ATR14 / its 7-day median) | 0.81 to 1.03 | 512 | 29.7% | +0.180 | +92.3 | +2.3 |
| Hour (IST) | 18 | 120 | 29.2% | +0.179 | +21.5 | +0.9 |
| Confirmation candle range / ATR14 | 0.17 to 0.98 | 513 | 29.2% | +0.176 | +90.5 | +2.0 |
| Room to prior day High/Low (R) | past it already | 394 | 28.9% | +0.163 | +64.4 | +1.5 |
| Side x session | long Close 21-24 UTC | 108 | 28.7% | +0.148 | +16.0 | +0.7 |


## What-if diagnostics (shadow runs - the baseline rules are NOT changed, these only measure what each rule does)

| Variant | Trades | Win rate | Total R | Avg R | PF | Max DD (R) | Net R (spread) |
|---|---|---|---|---|---|---|---|
| baseline (rerun) | 2049 | 25.9% | +69.7 | +0.034 | 1.05 | 72.0 | -178.5 |
| no POC-tap requirement | 575 | 25.7% | -132.9 | -0.231 | 0.79 | 168.2 | -158.6 |
| tap must be on the confirmation candle | 2006 | 24.5% | -57.2 | -0.029 | 0.96 | 119.1 | -334.5 |
| tap valid all day | 1459 | 27.8% | +84.3 | +0.058 | 1.07 | 115.1 | -78.5 |
| no candle-colour requirement | 2137 | 25.7% | +56.6 | +0.026 | 1.04 | 72.5 | -215.6 |
| unlimited trades per rectangle | 5103 | 25.3% | +60.9 | +0.012 | 1.02 | 123.8 | -576.6 |
| HVN rectangles only (no PDH/PDL) | 1357 | 26.7% | +80.8 | +0.060 | 1.08 | 43.1 | -90.0 |
| longs only | 1890 | 25.7% | +56.8 | +0.030 | 1.04 | 81.0 | -186.3 |
| shorts only | 1846 | 24.8% | -16.3 | -0.009 | 0.99 | 105.8 | -255.3 |

## Findings

### A. What is working

- The mechanics: every loss is exactly -1R and every win exactly +3R (stop at the rectangle edge, target at 3R), the entry is the confirmation close, and the zone engine reproduces the reference chart's density (median 3 internal rectangles, ~2 USD tall).
- The gross expectancy is not negative: 25.9% winners vs 25.0% needed, +0.034R per trade. The rules do not destroy money by themselves; they just do not make any before costs.
- Breakouts that continue beyond the previous day's range: setups whose 3R target lies beyond the prior Day High/Low win 28.4% (828 trades, +115.7R) against 24.2% (1221 trades, -46.0R) when the target sits inside yesterday's range (z +2.1). Long entries from the prior Day High rectangle are the best single slice (192 trades, 31.8%, +53.8R).
- A tap that happened on an EARLIER bar than the confirmation candle wins 27.5% (854 trades) vs 24.7% when the tap and the breakout are the same candle (1195 trades, -25.6R). Suggestive (z +1.4), not proven.

### B. Where exactly the money is lost

- Right after entry. 884 of 2049 entries (43%) close back inside the rectangle within 3 bars; they win 10.1% and hold 52% of all losses (-538R). 857 entries (42%) are 0.5R under water within 15 minutes and win 13.0%. Half of all losers are stopped within 34 minutes; 48% within 30 minutes. The 'confirmation close' does not confirm anything.
- In the spread. Median stop 3.52 USD against a 0.25-0.50 USD spread = 0.10R per trade; the smallest-stop quartile pays 0.24R per trade and turns +19.5R gross into -101.2R net.
- In the volume rectangles themselves: 1316 HVN trades (64% of all) return +5.6R. Rectangle height, volume share, prominence, distance to the next rectangle and number of rectangles show no relation to the outcome (all |z| < 2). The profile machinery is not adding information over a plain horizontal level.
- In 2024 (266 trades, 19.9%, -57.5R) and 2026 so far (479 trades, -19.2R).
- Shorts in the Asian session (245 trades, 22.0%, -29.0R) and low-volatility regimes (ATR14 below 0.81x its 7-day median: 513 trades, 22.2%, -48.5R, z -2.2).

### C. Most frequent losing condition

- Post-hoc (how): the failed breakout - price back inside the rectangle within 3 bars - is present in 52% of losses.
- Pre-entry (when): 'tap and breakout on the same candle' (1195 trades, 59% of losses, win rate 24.7%) and 'target inside yesterday's range' (1221 trades, 61% of losses, 24.2%). Both are frequent mainly because the strategy trades there often (lift 1.02 and 1.02); neither is toxic on its own.

### D. Condition contributing the most negative R

- Every loss is -1R, so a bucket's negative R equals its loss count; the meaningful ranking is by NET result. The largest net-negative buckets with a plausible mechanism:
  - target inside the prior day's range, 3-6R of room to the Day High/Low: 433 trades, 21.2%, -74.2R (z -2.5);
  - low-volatility regime: 513 trades, -48.5R;
  - 2024: -57.5R; Asian-session shorts: -29.0R;
  - the smallest-stop quartile after costs: -101.2R net.
- Quartile buckets that look bad but whose neighbours are fine (entry distance 0.54-0.68R, candle body 0.66-0.82) are non-monotonic and treated as noise.

### E. Rules that appear unnecessary (shadow runs)

| Variant | Trades | Win rate | Total R | Avg R | Net R | Delta |
|---|---|---|---|---|---|---|
| baseline (rerun) | 2049 | 25.9% | +69.7 | +0.034 | -178.5 | +0 trades, +0.000R/trade vs baseline |
| no POC-tap requirement | 575 | 25.7% | -132.9 | -0.231 | -158.6 | -1474 trades, -0.265R/trade vs baseline |
| tap must be on the confirmation candle | 2006 | 24.5% | -57.2 | -0.029 | -334.5 | -43 trades, -0.063R/trade vs baseline |
| tap valid all day | 1459 | 27.8% | +84.3 | +0.058 | -78.5 | -590 trades, +0.024R/trade vs baseline |
| no candle-colour requirement | 2137 | 25.7% | +56.6 | +0.026 | -215.6 | +88 trades, -0.008R/trade vs baseline |
| unlimited trades per rectangle | 5103 | 25.3% | +60.9 | +0.012 | -576.6 | +3054 trades, -0.022R/trade vs baseline |
| HVN rectangles only (no PDH/PDL) | 1357 | 26.7% | +80.8 | +0.060 | -90.0 | -692 trades, +0.025R/trade vs baseline |
| longs only | 1890 | 25.7% | +56.8 | +0.030 | -186.3 | -159 trades, -0.004R/trade vs baseline |
| shorts only | 1846 | 24.8% | -16.3 | -0.009 | -255.3 | -203 trades, -0.043R/trade vs baseline |

Read the deltas against the baseline row: a rule is 'doing nothing' when removing it leaves the win rate and the R per trade unchanged and only changes the trade count; it is 'protective' when removing it lowers the R per trade; it is 'harmful' when removing it raises the R per trade.

Interpretation:

- **POC tap**: removing it is not a fair test - without the tap nothing keeps the entry near the rectangle, so the run degenerates into 575 multi-day trades with huge stops (-0.231R each). The tap's real job is proximity, not confirmation.
- **Tap timing**: allowing only same-candle taps makes things worse (-0.029R/trade); letting a tap stay valid all day makes them better (+0.058R/trade on 1,459 trades, the best net result at -79R). The 12-bar window is arbitrary and, if anything, too short. The baseline's same-bar trades (58% of all) are its weakest group.
- **Candle colour**: no effect (+0.026 vs +0.034R/trade, 88 extra trades). Unnecessary but harmless.
- **One entry per rectangle**: protective. Unlimited re-entries add 3,054 trades at roughly zero gross and -400R of extra spread.
- **Day High / Day Low rectangles**: not needed. Trading the HVN rectangles alone gives +0.060R/trade (1,357 trades, +81R) - better than the baseline, and it contradicts the baseline's own 'PDH-long is the best slice' reading. The two readings differ only in WHICH trades the one-position rule blocked, which is the noise level of this test.
- **One position at a time**: not protective. The 8,367 setups that fired while a trade was open would have won 28.4% (+0.139R) - better than the taken ones (inflated by re-firing, but certainly not worse).
- **3R target**: with the same entries and stop, no target from 0.5R to 3R does better than +0.03R per trade (target curve in the baseline report). 32% of losers were +1R in profit first, yet a 1R target still nets -0.01R. The target is not the problem; neither is the stop.
- **Longs vs shorts**: +0.030 vs -0.009R/trade, inside the noise.

**Noise level.** Mean trade +0.034R, standard error 0.039R, 95% CI -0.043 to +0.111R gross (total -88R to +228R); net of spread -0.087R, 95% CI -0.164 to -0.010R. Every shadow-run difference above, and every year-to-year swing, sits inside that band. The one statement that survives the noise is the sign of the net result: negative.

### F. Gaps worth testing in Version 2

1. Failed-breakout handling: exit when a bar closes back inside the rectangle (cut at a fraction of R instead of the full -1R), or require a second close beyond the edge / a retest that holds. This targets the mechanism behind half of all losses.
2. Cost-aware selection: skip stops smaller than a minimum in USD or in ATR; the smallest-stop quartile is where the spread eats the result.
3. Previous-day range as the target boundary: only take setups whose 3R target lies beyond the prior Day High/Low (or whose room is > 6R).
4. Directional context: the only positive slice is long breakouts of the prior Day High; test a with-trend filter (prior day close vs open, price vs the prior day's POC) and PDH-long / PDL-short only.
5. Volatility gate: skip when ATR14 is below 0.8x its 7-day median.
6. Tap timing: require the POC tap at least one bar before the confirmation candle (the 'tap, hold, then break' pattern).
7. Session: Asian-session shorts and the 15:00-17:00 IST hours are the weak spots; London open (14:00 IST) the strong one. Test a session window.
8. Target: see the target curve in the baseline report - compare the expectancy at 1.5R/2R/3R with the same stop before deciding that 3R is right.
9. Data: repeat on OANDA tick-volume profiles on TradingView (the rectangles differ from Dukascopy's) and with 1-min intrabar profiles.
