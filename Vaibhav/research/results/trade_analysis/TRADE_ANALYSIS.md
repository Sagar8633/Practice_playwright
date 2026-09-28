# Trade analysis of the untouched EA (strategy view, 0.01 lot, realistic costs)

## M1

Trades 54900; total MFE $110747.57 vs realized $-30212.35; average giveback $2.57 (median $1.66, worst $117.72); median giveback 163.7% of MFE; share of trades that were ever >= $1 in profit: 0.378.

### Giveback by direction

| direction | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long | 25925 | -13584.05 | 1.92 | 2.44 | 160.7 | 95.52 | 1978 | -3486.04 |
| short | 28975 | -16628.3 | 2.11 | 2.68 | 166.2 | 117.72 | 2630 | -4796.08 |

### Giveback by session

| session | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Asia | 15937 | -8282.07 | 1.79 | 2.31 | 163.8 | 117.72 | 1073 | -2114.91 |
| London | 12328 | -7029.13 | 1.84 | 2.41 | 164.9 | 54.14 | 926 | -1458.04 |
| London/NY | 10929 | -5514.53 | 2.6 | 3.1 | 159.7 | 95.52 | 1299 | -2097.21 |
| NewYork | 11905 | -7363.81 | 2.14 | 2.76 | 161.0 | 90.07 | 1116 | -2162.17 |
| Sydney | 3801 | -2022.81 | 1.51 | 2.04 | 183.2 | 75.41 | 194 | -449.79 |

### Giveback by regime

| regime | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nan/nan | 11130 | -5999.92 | 2.05 | 2.59 | 160.9 | 117.72 | 937 | -1737.02 |
| range/high_vol | 1508 | -864.7 | 1.25 | 1.82 | 168.7 | 38.34 | 56 | -74.56 |
| range/low_vol | 1108 | -521.75 | 1.2 | 1.67 | 161.4 | 22.2 | 35 | -43.64 |
| range/mid_vol | 1828 | -1387.24 | 1.52 | 2.28 | 175.7 | 34.17 | 133 | -199.83 |
| strong_trend/high_vol | 11959 | -6026.03 | 3.33 | 3.83 | 154.8 | 90.07 | 1810 | -3756.39 |
| strong_trend/low_vol | 7355 | -3927.07 | 1.05 | 1.58 | 168.9 | 14.19 | 207 | -225.82 |
| strong_trend/mid_vol | 9712 | -5409.48 | 2.04 | 2.59 | 162.8 | 75.41 | 873 | -1446.6 |
| weak_trend/high_vol | 2423 | -1578.24 | 2.18 | 2.84 | 166.9 | 47.57 | 267 | -426.68 |
| weak_trend/low_vol | 3485 | -1938.53 | 0.8 | 1.35 | 176.2 | 9.86 | 47 | -31.19 |
| weak_trend/mid_vol | 4392 | -2559.4 | 1.5 | 2.09 | 167.5 | 18.63 | 243 | -340.39 |

### Giveback by exit_reason

| exit_reason | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MA18_exit | 42814 | -27045.59 | 1.79 | 2.42 | 167.5 | 95.52 | 3343 | -7186.23 |
| SL_breakeven | 1486 | -36.98 | 8.02 | 8.05 | 100.0 | 51.28 | 1074 | -38.76 |
| SL_initial | 9186 | -14690.76 | 0.18 | 1.78 | 598.6 | 45.62 | 189 | -1050.19 |
| SL_swing | 1413 | 11553.58 | 14.68 | 6.5 | 44.7 | 117.72 | 2 | -6.94 |
| end_of_test | 1 | 7.39 | 18.53 | 11.14 | 60.1 | 11.14 | 0 | 0.0 |

### Profitable -> loss reversals

| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |
|---|---:|---:|---:|---:|---:|---|---:|
| 1usd | 9638 | 0.222 | -16606.57 | 26990.15 | 0.247 | {'MA18_exit': 8085, 'SL_breakeven': 1074, 'SL_initial': 477, 'SL_swing': 2} | 0.354 |
| 2usd | 4608 | 0.106 | -8282.12 | 19923.88 | 0.123 | {'MA18_exit': 3343, 'SL_breakeven': 1074, 'SL_initial': 189, 'SL_swing': 2} | 0.362 |
| 5usd | 1085 | 0.025 | -129.74 | 9206.39 | 0.002 | {'SL_breakeven': 1071, 'SL_initial': 11, 'SL_swing': 2, 'MA18_exit': 1} | 0.379 |
| 10usd | 220 | 0.005 | -60.03 | 3413.76 | 0.001 | {'SL_breakeven': 215, 'SL_initial': 4, 'MA18_exit': 1} | 0.377 |
| 1R | 1737 | 0.04 | -1025.13 | 6147.25 | 0.015 | {'MA18_exit': 1289, 'SL_breakeven': 289, 'SL_initial': 157, 'SL_swing': 2} | 0.546 |
| 2R | 145 | 0.003 | -96.15 | 726.77 | 0.001 | {'MA18_exit': 82, 'SL_breakeven': 35, 'SL_initial': 27, 'SL_swing': 1} | 0.683 |
| 3R | 31 | 0.001 | -41.49 | 163.7 | 0.001 | {'MA18_exit': 12, 'SL_initial': 11, 'SL_breakeven': 8} | 0.71 |

### Loss categories (all losing trades, first matching rule)

| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|
| 01 bad entry (never reached 0.25R) | 19585 | -33702.94 | -1.72 | 0.19 | 50.1 |
| 09 news/volatility event | 3083 | -8278.7 | -2.69 | 0.79 | 12.3 |
| 10 low-liquidity hour | 5341 | -7304.0 | -1.37 | 0.31 | 10.9 |
| 12 other | 4188 | -6242.86 | -1.49 | 1.18 | 9.3 |
| 03 whipsaw (MA18 exit within 3 bars) | 3078 | -5438.13 | -1.77 | 0.08 | 8.1 |
| 02 correct entry, market reversal | 2526 | -3116.86 | -1.23 | 1.83 | 4.6 |
| 04 excessive SL | 243 | -1631.6 | -6.71 | 0.83 | 2.4 |
| 11 spread/slippage (positive before costs) | 4838 | -912.56 | -0.19 | 2.9 | 1.4 |
| 06 trailing/protection too loose (gave back >60% of >=1R) | 577 | -588.54 | -1.02 | 2.5 | 0.9 |
| 05 trailing/protection too tight | 1 | -0.87 | -0.87 | 7.57 | 0.0 |

## M5

Trades 12320; total MFE $59260.29 vs realized $-4977.42; average giveback $5.21 (median $3.61, worst $177.52); median giveback 148.3% of MFE; share of trades that were ever >= $1 in profit: 0.607.

### Giveback by direction

| direction | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long | 6490 | -2569.95 | 4.45 | 4.84 | 151.0 | 116.79 | 1318 | -3138.3 |
| short | 5830 | -2407.47 | 5.21 | 5.63 | 144.3 | 177.52 | 1270 | -2918.68 |

### Giveback by session

| session | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Asia | 3633 | -1219.03 | 4.39 | 4.73 | 143.3 | 126.18 | 665 | -1433.18 |
| London | 2995 | -1731.58 | 4.01 | 4.59 | 158.3 | 120.89 | 582 | -1155.45 |
| London/NY | 2861 | -847.86 | 6.21 | 6.51 | 148.4 | 80.83 | 743 | -1984.6 |
| NewYork | 2149 | -617.16 | 5.24 | 5.52 | 124.1 | 177.52 | 483 | -1200.9 |
| Sydney | 682 | -561.78 | 3.32 | 4.15 | 184.6 | 38.48 | 115 | -282.85 |

### Giveback by regime

| regime | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nan/nan | 2504 | -1055.44 | 4.84 | 5.26 | 152.1 | 126.18 | 517 | -1182.11 |
| range/high_vol | 343 | -138.37 | 3.28 | 3.68 | 162.8 | 31.04 | 42 | -71.32 |
| range/low_vol | 273 | -95.14 | 3.06 | 3.41 | 168.2 | 26.07 | 34 | -69.63 |
| range/mid_vol | 411 | -375.34 | 3.72 | 4.64 | 182.8 | 35.37 | 75 | -201.72 |
| strong_trend/high_vol | 2702 | -750.2 | 7.37 | 7.65 | 114.3 | 177.52 | 805 | -2215.91 |
| strong_trend/low_vol | 1664 | -816.92 | 2.8 | 3.29 | 162.3 | 38.48 | 220 | -397.69 |
| strong_trend/mid_vol | 2147 | -564.11 | 5.03 | 5.29 | 143.3 | 116.79 | 508 | -1166.24 |
| weak_trend/high_vol | 516 | -428.74 | 5.28 | 6.11 | 154.1 | 49.23 | 133 | -331.41 |
| weak_trend/low_vol | 789 | -280.39 | 2.33 | 2.68 | 165.9 | 13.1 | 67 | -103.71 |
| weak_trend/mid_vol | 971 | -472.76 | 3.82 | 4.31 | 156.5 | 38.55 | 187 | -317.25 |

### Giveback by exit_reason

| exit_reason | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MA18_exit | 8722 | -7877.99 | 3.39 | 4.29 | 191.5 | 120.89 | 1593 | -4804.58 |
| SL_breakeven | 1458 | -4.74 | 9.32 | 9.32 | 100.0 | 80.16 | 811 | -6.33 |
| SL_initial | 1390 | -5214.78 | 0.72 | 4.47 | 512.7 | 40.2 | 184 | -1246.06 |
| SL_swing | 750 | 8120.09 | 20.14 | 9.31 | 49.3 | 177.52 | 0 | 0.0 |

### Profitable -> loss reversals

| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |
|---|---:|---:|---:|---:|---:|---|---:|
| 1usd | 4115 | 0.459 | -10487.92 | 16433.05 | 0.437 | {'MA18_exit': 2953, 'SL_breakeven': 811, 'SL_initial': 351} | 0.377 |
| 2usd | 2588 | 0.289 | -6056.98 | 14222.67 | 0.252 | {'MA18_exit': 1593, 'SL_breakeven': 811, 'SL_initial': 184} | 0.372 |
| 5usd | 813 | 0.091 | -42.56 | 8709.19 | 0.002 | {'SL_breakeven': 809, 'SL_initial': 4} | 0.371 |
| 10usd | 275 | 0.031 | -5.22 | 4980.6 | 0.0 | {'SL_breakeven': 275} | 0.364 |
| 1R | 474 | 0.053 | -392.39 | 2873.19 | 0.016 | {'MA18_exit': 292, 'SL_breakeven': 112, 'SL_initial': 70} | 0.599 |
| 2R | 35 | 0.004 | -15.07 | 324.02 | 0.001 | {'MA18_exit': 17, 'SL_breakeven': 13, 'SL_initial': 5} | 0.743 |
| 3R | 5 | 0.001 | -1.87 | 93.78 | 0.0 | {'SL_breakeven': 3, 'SL_initial': 1, 'MA18_exit': 1} | 0.6 |

### Loss categories (all losing trades, first matching rule)

| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|
| 01 bad entry (never reached 0.25R) | 3290 | -11610.11 | -3.53 | 0.54 | 48.4 |
| 12 other | 1144 | -2735.07 | -2.39 | 1.8 | 11.4 |
| 10 low-liquidity hour | 1118 | -2573.28 | -2.3 | 0.78 | 10.7 |
| 03 whipsaw (MA18 exit within 3 bars) | 807 | -2330.17 | -2.89 | 0.3 | 9.7 |
| 09 news/volatility event | 357 | -2238.14 | -6.27 | 1.61 | 9.3 |
| 02 correct entry, market reversal | 765 | -1323.5 | -1.73 | 2.41 | 5.5 |
| 04 excessive SL | 65 | -821.5 | -12.64 | 1.57 | 3.4 |
| 06 trailing/protection too loose (gave back >60% of >=1R) | 198 | -281.07 | -1.42 | 3.1 | 1.2 |
| 11 spread/slippage (positive before costs) | 1214 | -98.87 | -0.08 | 7.89 | 0.4 |

## M15

Trades 4559; total MFE $36607.12 vs realized $-983.88; average giveback $8.25 (median $6.11, worst $181.04); median giveback 100.0% of MFE; share of trades that were ever >= $1 in profit: 0.759.

### Giveback by direction

| direction | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long | 2434 | -267.89 | 7.76 | 7.87 | 100.5 | 147.71 | 692 | -2323.5 |
| short | 2125 | -715.99 | 8.34 | 8.68 | 100.0 | 181.04 | 583 | -1900.61 |

### Giveback by session

| session | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Asia | 1280 | -45.95 | 7.61 | 7.65 | 100.0 | 181.04 | 327 | -917.06 |
| London | 1198 | -1395.02 | 6.04 | 7.21 | 138.8 | 149.05 | 337 | -1044.69 |
| London/NY | 1180 | -123.91 | 9.16 | 9.26 | 100.0 | 107.89 | 325 | -1393.15 |
| NewYork | 729 | 222.79 | 9.46 | 9.16 | 100.0 | 170.32 | 235 | -758.81 |
| Sydney | 172 | 358.22 | 11.15 | 9.07 | 122.2 | 147.71 | 51 | -110.4 |

### Giveback by regime

| regime | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nan/nan | 904 | -82.1 | 8.02 | 8.11 | 100.0 | 181.04 | 245 | -787.84 |
| range/high_vol | 123 | -70.66 | 5.75 | 6.32 | 158.6 | 32.63 | 17 | -60.44 |
| range/low_vol | 103 | 95.24 | 6.4 | 5.47 | 121.9 | 21.16 | 14 | -36.75 |
| range/mid_vol | 148 | -160.15 | 6.9 | 7.98 | 131.4 | 47.73 | 45 | -161.74 |
| strong_trend/high_vol | 1045 | -389.72 | 11.15 | 11.52 | 100.0 | 170.32 | 393 | -1305.3 |
| strong_trend/low_vol | 609 | -338.94 | 4.99 | 5.54 | 138.1 | 59.43 | 113 | -327.09 |
| strong_trend/mid_vol | 800 | 112.57 | 8.58 | 8.44 | 100.0 | 147.71 | 244 | -908.47 |
| weak_trend/high_vol | 186 | 92.09 | 9.3 | 8.8 | 100.0 | 51.55 | 61 | -255.86 |
| weak_trend/low_vol | 276 | -93.36 | 4.24 | 4.58 | 139.0 | 16.59 | 59 | -122.59 |
| weak_trend/mid_vol | 365 | -148.86 | 6.9 | 7.3 | 100.0 | 38.88 | 84 | -258.03 |

### Giveback by exit_reason

| exit_reason | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MA18_exit | 2487 | -3351.94 | 5.65 | 7.0 | 227.0 | 170.32 | 688 | -3410.33 |
| SL_breakeven | 1179 | -30.97 | 10.41 | 10.44 | 100.0 | 181.04 | 481 | -33.35 |
| SL_initial | 485 | -2853.22 | 1.12 | 7.0 | 527.6 | 38.88 | 106 | -780.44 |
| SL_swing | 408 | 5252.25 | 23.86 | 10.98 | 50.8 | 147.71 | 0 | 0.0 |

### Profitable -> loss reversals

| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |
|---|---:|---:|---:|---:|---:|---|---:|
| 1usd | 1786 | 0.619 | -6726.34 | 9605.04 | 0.561 | {'MA18_exit': 1100, 'SL_breakeven': 481, 'SL_initial': 205} | 0.409 |
| 2usd | 1275 | 0.442 | -4224.11 | 8850.17 | 0.352 | {'MA18_exit': 688, 'SL_breakeven': 481, 'SL_initial': 106} | 0.389 |
| 5usd | 485 | 0.168 | -44.74 | 6261.81 | 0.004 | {'SL_breakeven': 478, 'MA18_exit': 6, 'SL_initial': 1} | 0.375 |
| 10usd | 210 | 0.073 | -9.79 | 4349.18 | 0.001 | {'SL_breakeven': 209, 'MA18_exit': 1} | 0.357 |
| 1R | 119 | 0.041 | -107.26 | 1781.42 | 0.009 | {'MA18_exit': 51, 'SL_breakeven': 48, 'SL_initial': 20} | 0.639 |
| 2R | 7 | 0.002 | -6.23 | 106.12 | 0.001 | {'SL_breakeven': 3, 'MA18_exit': 2, 'SL_initial': 2} | 0.857 |
| 3R | 2 | 0.001 | -0.92 | 38.71 | 0.0 | {'SL_breakeven': 1, 'MA18_exit': 1} | 1.0 |

### Loss categories (all losing trades, first matching rule)

| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|
| 01 bad entry (never reached 0.25R) | 1026 | -6271.21 | -6.11 | 0.98 | 52.3 |
| 03 whipsaw (MA18 exit within 3 bars) | 323 | -1620.86 | -5.02 | 0.67 | 13.5 |
| 12 other | 425 | -1425.09 | -3.35 | 2.31 | 11.9 |
| 10 low-liquidity hour | 211 | -800.23 | -3.79 | 2.03 | 6.7 |
| 09 news/volatility event | 81 | -756.44 | -9.34 | 2.03 | 6.3 |
| 02 correct entry, market reversal | 240 | -564.0 | -2.35 | 3.07 | 4.7 |
| 04 excessive SL | 20 | -460.12 | -23.01 | 1.3 | 3.8 |
| 06 trailing/protection too loose (gave back >60% of >=1R) | 50 | -78.47 | -1.57 | 3.52 | 0.7 |
| 11 spread/slippage (positive before costs) | 508 | -11.91 | -0.02 | 12.15 | 0.1 |

## D1

Trades 85; total MFE $4937.08 vs realized $619.14; average giveback $50.8 (median $17.82, worst $977.11); median giveback 100.0% of MFE; share of trades that were ever >= $1 in profit: 1.0.

### Giveback by direction

| direction | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long | 56 | 695.81 | 77.15 | 64.73 | 100.0 | 977.11 | 29 | -174.07 |
| short | 29 | -76.67 | 21.26 | 23.9 | 100.0 | 116.08 | 8 | -122.14 |

### Giveback by session

| session | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Asia | 42 | 477.99 | 76.71 | 65.33 | 100.0 | 977.11 | 19 | -104.45 |
| London | 11 | 231.89 | 61.96 | 40.88 | 100.0 | 128.1 | 2 | -3.47 |
| London/NY | 20 | -195.34 | 20.27 | 30.04 | 101.2 | 116.08 | 10 | -173.52 |
| NewYork | 11 | 104.6 | 55.48 | 45.97 | 100.0 | 181.4 | 5 | -14.76 |
| Sydney | 1 | -0.0 | 18.07 | 18.07 | 100.0 | 18.07 | 1 | -0.0 |

### Giveback by regime

| regime | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nan/nan | 15 | 488.2 | 160.52 | 127.97 | 100.0 | 977.11 | 7 | -63.57 |
| range/high_vol | 3 | -0.27 | 26.24 | 26.33 | 100.0 | 53.01 | 1 | -0.87 |
| range/low_vol | 1 | -2.61 | 7.13 | 9.74 | 136.5 | 9.74 | 1 | -2.61 |
| strong_trend/high_vol | 15 | 61.87 | 35.62 | 31.49 | 100.0 | 257.54 | 4 | -7.82 |
| strong_trend/low_vol | 17 | -81.56 | 34.48 | 39.28 | 100.0 | 132.94 | 8 | -177.86 |
| strong_trend/mid_vol | 17 | 148.73 | 52.67 | 43.92 | 100.0 | 128.1 | 10 | -22.58 |
| weak_trend/high_vol | 1 | 0.0 | 8.75 | 8.75 | 100.0 | 8.75 | 0 | 0.0 |
| weak_trend/low_vol | 9 | 4.19 | 37.04 | 36.57 | 100.0 | 181.4 | 3 | -20.91 |
| weak_trend/mid_vol | 7 | 0.59 | 12.24 | 12.15 | 100.0 | 17.7 | 3 | -0.0 |

### Giveback by exit_reason

| exit_reason | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MA18_exit | 7 | -36.69 | 75.08 | 80.32 | 412.2 | 181.4 | 3 | -168.38 |
| SL_breakeven | 70 | -81.05 | 36.63 | 37.79 | 100.0 | 977.11 | 33 | -88.58 |
| SL_initial | 1 | -39.25 | 2.69 | 41.94 | 1559.1 | 41.94 | 1 | -39.25 |
| SL_swing | 7 | 776.13 | 263.51 | 152.63 | 58.5 | 427.23 | 0 | 0.0 |

### Profitable -> loss reversals

| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |
|---|---:|---:|---:|---:|---:|---|---:|
| 1usd | 38 | 1.0 | -318.23 | 2080.84 | 1.0 | {'SL_breakeven': 33, 'MA18_exit': 4, 'SL_initial': 1} | 0.342 |
| 2usd | 37 | 0.974 | -296.21 | 2079.39 | 0.931 | {'SL_breakeven': 33, 'MA18_exit': 3, 'SL_initial': 1} | 0.324 |
| 5usd | 33 | 0.868 | -88.58 | 2065.17 | 0.278 | {'SL_breakeven': 33} | 0.333 |
| 10usd | 27 | 0.711 | -81.63 | 2023.72 | 0.257 | {'SL_breakeven': 27} | 0.37 |
| 1R | 3 | 0.079 | -27.79 | 1162.18 | 0.087 | {'SL_breakeven': 3} | 0.333 |
| 2R | 1 | 0.026 | -12.16 | 964.95 | 0.038 | {'SL_breakeven': 1} | 1.0 |
| 3R | 1 | 0.026 | -12.16 | 964.95 | 0.038 | {'SL_breakeven': 1} | 1.0 |

### Loss categories (all losing trades, first matching rule)

| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|
| 01 bad entry (never reached 0.25R) | 8 | -204.96 | -25.62 | 8.52 | 64.4 |
| 05 trailing/protection too tight | 8 | -41.68 | -5.21 | 162.58 | 13.1 |
| 03 whipsaw (MA18 exit within 3 bars) | 2 | -32.51 | -16.26 | 2.41 | 10.2 |
| 06 trailing/protection too loose (gave back >60% of >=1R) | 2 | -15.63 | -7.82 | 98.62 | 4.9 |
| 12 other | 5 | -13.03 | -2.61 | 33.56 | 4.1 |
| 02 correct entry, market reversal | 3 | -10.42 | -3.47 | 56.29 | 3.3 |
| 11 spread/slippage (positive before costs) | 10 | -0.0 | -0.0 | 17.33 | 0.0 |

## D1_23y

Trades 329; total MFE $10934.3 vs realized $121.32; average giveback $32.87 (median $16.45, worst $977.11); median giveback 100.0% of MFE; share of trades that were ever >= $1 in profit: 0.967.

### Giveback by direction

| direction | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long | 230 | -116.89 | 37.12 | 37.63 | 107.9 | 977.11 | 146 | -1170.94 |
| short | 99 | 238.21 | 24.21 | 21.81 | 99.1 | 116.08 | 12 | -213.79 |

### Giveback by session

| session | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Asia | 126 | 259.54 | 45.15 | 43.09 | 100.0 | 977.11 | 63 | -682.44 |
| London | 58 | 123.29 | 26.8 | 24.67 | 100.0 | 105.02 | 17 | -70.77 |
| London/NY | 90 | -238.97 | 24.96 | 27.62 | 107.6 | 230.96 | 50 | -448.19 |
| NewYork | 51 | -36.83 | 25.44 | 26.17 | 103.4 | 181.4 | 25 | -173.78 |
| Sydney | 4 | 14.28 | 36.64 | 33.07 | 103.9 | 57.02 | 3 | -9.55 |

### Giveback by regime

| regime | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nan/nan | 56 | 212.74 | 57.62 | 53.82 | 100.0 | 977.11 | 27 | -326.33 |
| range/high_vol | 7 | 76.76 | 50.32 | 39.36 | 100.0 | 91.86 | 3 | -24.22 |
| range/low_vol | 11 | 9.12 | 15.45 | 14.62 | 100.0 | 43.57 | 2 | -3.47 |
| range/mid_vol | 7 | -34.09 | 15.71 | 20.58 | 105.4 | 50.73 | 5 | -12.86 |
| strong_trend/high_vol | 54 | 122.71 | 32.22 | 29.95 | 100.0 | 257.54 | 26 | -175.54 |
| strong_trend/low_vol | 77 | -178.1 | 28.51 | 30.82 | 106.4 | 189.81 | 39 | -404.74 |
| strong_trend/mid_vol | 45 | -27.26 | 29.84 | 30.45 | 100.0 | 128.1 | 22 | -153.4 |
| weak_trend/high_vol | 14 | -56.4 | 21.53 | 25.56 | 103.7 | 97.97 | 6 | -82.12 |
| weak_trend/low_vol | 27 | -65.15 | 21.72 | 24.13 | 106.0 | 181.4 | 15 | -108.26 |
| weak_trend/mid_vol | 31 | 61.0 | 29.34 | 27.37 | 100.0 | 230.96 | 13 | -93.79 |

### Giveback by exit_reason

| exit_reason | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MA18_exit | 58 | -647.11 | 36.7 | 47.85 | 584.5 | 189.81 | 29 | -818.31 |
| SL_breakeven | 232 | -322.08 | 21.28 | 22.66 | 100.0 | 977.11 | 117 | -356.91 |
| SL_initial | 10 | -225.48 | 1.76 | 24.31 | 1169.5 | 52.38 | 4 | -113.64 |
| SL_swing | 29 | 1315.98 | 132.84 | 87.46 | 72.3 | 427.23 | 8 | -95.86 |

### Profitable -> loss reversals

| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |
|---|---:|---:|---:|---:|---:|---|---:|
| 1usd | 167 | 0.938 | -1615.18 | 4112.43 | 0.869 | {'SL_breakeven': 117, 'MA18_exit': 36, 'SL_swing': 8, 'SL_initial': 6} | 0.431 |
| 2usd | 158 | 0.888 | -1384.73 | 4097.1 | 0.745 | {'SL_breakeven': 117, 'MA18_exit': 29, 'SL_swing': 8, 'SL_initial': 4} | 0.411 |
| 5usd | 130 | 0.73 | -487.56 | 3994.08 | 0.262 | {'SL_breakeven': 117, 'SL_swing': 8, 'MA18_exit': 5} | 0.392 |
| 10usd | 94 | 0.528 | -421.56 | 3747.29 | 0.227 | {'SL_breakeven': 81, 'SL_swing': 8, 'MA18_exit': 5} | 0.394 |
| 1R | 18 | 0.101 | -151.05 | 1734.21 | 0.081 | {'SL_breakeven': 11, 'MA18_exit': 4, 'SL_swing': 3} | 0.389 |
| 2R | 5 | 0.028 | -43.08 | 1089.92 | 0.023 | {'SL_breakeven': 3, 'MA18_exit': 2} | 0.6 |
| 3R | 3 | 0.017 | -28.66 | 1026.87 | 0.015 | {'SL_breakeven': 3} | 0.667 |

### Loss categories (all losing trades, first matching rule)

| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|
| 01 bad entry (never reached 0.25R) | 51 | -1014.45 | -19.89 | 5.25 | 54.6 |
| 03 whipsaw (MA18 exit within 3 bars) | 14 | -341.75 | -24.41 | 2.51 | 18.4 |
| 05 trailing/protection too tight | 42 | -162.19 | -3.86 | 45.02 | 8.7 |
| 06 trailing/protection too loose (gave back >60% of >=1R) | 13 | -121.52 | -9.35 | 46.4 | 6.5 |
| 12 other | 25 | -109.35 | -4.37 | 22.5 | 5.9 |
| 02 correct entry, market reversal | 11 | -55.18 | -5.02 | 38.46 | 3.0 |
| 09 news/volatility event | 4 | -53.17 | -13.29 | 25.21 | 2.9 |
| 11 spread/slippage (positive before costs) | 18 | -0.0 | -0.0 | 12.97 | 0.0 |
