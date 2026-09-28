# Strategy variants and higher-timeframe confirmation (scenario B, candidate timeframes)

One change per row versus the baseline of the same instrument / config / timeframe. 'helpful' = better expectancy in TRAIN, VAL and OOS; 'harmful' = worse in two or more splits. USD per 0.01 lot.


## Silver (XAGUSD) 4h ASIS (baseline 221 trades, net $849.03, PF 1.251, TRAIN -702 / VAL -7 / OOS 1,558, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 171 | 206.80 | -642.23 | 1.07 | -0.04 | 734.28 | -522.38 | -91.17 | 820.36 | unstable | harmful |
| V02 | ADX(14) >= 20 | 202 | 56.63 | -792.40 | 1.02 | -0.07 | 1,069.00 | -764.83 | -197.53 | 1,018.99 | unstable | harmful |
| V03 | no volume filter | 287 | 518.03 | -331.00 | 1.12 | -0.05 | 864.28 | -559.01 | -86.81 | 1,163.85 | unstable | harmful |
| V04 | entries 08:00-21:59 server (London + New York) | 222 | 591.34 | -257.69 | 1.18 | -0.04 | 917.18 | -726.98 | -4.73 | 1,323.06 | unstable | harmful |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 143 | -29.15 | -878.18 | 0.98 | -0.14 | 773.46 | -506.77 | -72.32 | 549.94 | negative | harmful |
| V06 | no entries 00:00-06:59 server (Asia) | 222 | 591.34 | -257.69 | 1.18 | -0.04 | 917.18 | -726.98 | -4.73 | 1,323.06 | unstable | harmful |
| V07 | no entries on Monday before 08:00 (weekend gap) | 220 | 872.90 | 23.87 | 1.26 | -0.01 | 922.03 | -694.77 | -41.79 | 1,609.47 | unstable | mixed |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 127 | 323.99 | -525.04 | 1.15 | -0.05 | 663.18 | -296.73 | -310.61 | 931.33 | unstable | mixed |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 216 | 896.77 | 47.74 | 1.27 | -0.03 | 849.25 | -656.74 | -7.05 | 1,560.55 | unstable | mixed |
| V10 | MA18 slope filter over 3 bars | 199 | 935.14 | 86.11 | 1.35 | -0.04 | 899.31 | -675.05 | -39.37 | 1,649.57 | unstable | harmful |
| V11 | no entry when |close - MA18| > 2 ATR | 199 | 1,144.14 | 295.11 | 1.38 | -0.01 | 733.72 | -507.40 | 1.76 | 1,649.78 | unstable | helpful |
| V12 | trend-regime gate: no sideways days | 187 | 1,249.95 | 400.92 | 1.51 | 0.01 | 646.77 | -511.40 | 50.10 | 1,711.25 | unstable | helpful |
| V13 | regime-aligned direction | 131 | 1,094.61 | 245.58 | 1.63 | 0.02 | 557.47 | -444.79 | 73.25 | 1,466.15 | unstable | mixed |
| V14 | long only | 126 | 1,560.29 | 711.26 | 1.91 | -0.00 | 603.88 | -497.77 | 59.95 | 1,998.11 | unstable | mixed |
| V15 | short only | 95 | -711.26 | -1,560.29 | 0.57 | -0.07 | 1,077.10 | -204.62 | -66.53 | -440.11 | negative | harmful |
| V16 | pending order expires after 3 bars | 217 | 754.94 | -94.09 | 1.21 | -0.04 | 865.06 | -669.96 | -28.78 | 1,453.68 | unstable | harmful |
| V17 | confirmation window 1 bar | 286 | 172.34 | -676.69 | 1.04 | -0.09 | 1,182.89 | -951.19 | -56.74 | 1,180.26 | unstable | harmful |
| V18 | confirmation window 3 bars | 182 | 866.74 | 17.71 | 1.31 | -0.01 | 707.77 | -498.63 | -52.48 | 1,417.86 | unstable | mixed |
| V19 | no high/extreme volatility days | 110 | -247.80 | -1,096.83 | 0.80 | -0.10 | 526.85 | -424.23 | 93.59 | 82.84 | negative | mixed |
| V20 | max spread filter: no setup when spread > 2x model median | 221 | 849.03 | 0.00 | 1.25 | -0.03 | 894.43 | -702.38 | -6.58 | 1,558.00 | unstable | mixed |

## Silver (XAGUSD) ASIS: higher-timeframe gates

| id | entry | HTF | trades | base trades | net $ | base net $ | PF | exp R | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M09 | 4h | D1 | 103 | 221 | 1,926.62 | 849.03 | 2.61 | 0.11 | -229.02 | 67.32 | 2,088.32 | unstable | helpful |
| M09c | 4h | D1 | 95 | 221 | 1,851.23 | 849.03 | 2.86 | -0.00 | -136.02 | 71.27 | 1,915.97 | unstable | helpful |

## Bitcoin (BTCUSD) 4h ASIS (baseline 807 trades, net $136.51, PF 1.245, TRAIN 148 / VAL 26 / OOS -38, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 609 | 94.98 | -41.53 | 1.25 | 0.01 | 108.99 | 94.51 | 54.25 | -53.78 | unstable | harmful |
| V02 | ADX(14) >= 20 | 731 | 83.14 | -53.37 | 1.17 | 0.01 | 109.72 | 124.72 | 12.66 | -54.24 | unstable | harmful |
| V03 | no volume filter | 1164 | 41.11 | -95.40 | 1.05 | 0.01 | 222.51 | 82.73 | 58.33 | -99.94 | unstable | harmful |
| V04 | entries 08:00-21:59 server (London + New York) | 657 | 9.66 | -126.85 | 1.02 | 0.02 | 149.31 | 21.75 | 39.04 | -51.13 | unstable | harmful |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 249 | -60.94 | -197.45 | 0.56 | -0.02 | 72.38 | -11.26 | -30.28 | -19.40 | negative | harmful |
| V06 | no entries 00:00-06:59 server (Asia) | 657 | 9.66 | -126.85 | 1.02 | 0.02 | 149.31 | 21.75 | 39.04 | -51.13 | unstable | harmful |
| V07 | no entries on Monday before 08:00 (weekend gap) | 753 | 225.93 | 89.42 | 1.49 | 0.03 | 99.08 | 154.07 | 73.28 | -1.42 | unstable | helpful |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 380 | 96.23 | -40.28 | 1.41 | 0.03 | 116.71 | -68.60 | 84.38 | 80.45 | unstable | mixed |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 759 | 158.51 | 22.00 | 1.31 | 0.02 | 134.75 | 169.03 | 26.51 | -37.03 | unstable | mixed |
| V10 | MA18 slope filter over 3 bars | 720 | 171.86 | 35.35 | 1.39 | 0.02 | 109.14 | 161.49 | 51.99 | -41.62 | unstable | mixed |
| V11 | no entry when |close - MA18| > 2 ATR | 542 | 33.45 | -103.06 | 1.09 | 0.03 | 205.54 | 89.57 | -40.79 | -15.33 | unstable | harmful |
| V12 | trend-regime gate: no sideways days | 664 | 113.51 | -23.00 | 1.29 | 0.02 | 85.69 | 70.22 | 31.38 | 11.92 | robust | mixed |
| V13 | regime-aligned direction | 457 | 120.96 | -15.55 | 1.43 | 0.01 | 70.06 | 49.33 | 33.03 | 38.60 | robust | mixed |
| V14 | long only | 390 | 260.69 | 124.18 | 1.92 | 0.07 | 60.95 | 207.63 | 11.69 | 41.37 | robust | mixed |
| V15 | short only | 417 | -124.18 | -260.69 | 0.55 | -0.03 | 152.63 | -59.68 | 14.50 | -79.00 | negative | harmful |
| V16 | pending order expires after 3 bars | 771 | 86.31 | -50.20 | 1.15 | 0.02 | 136.44 | 98.16 | 26.83 | -38.68 | unstable | harmful |
| V17 | confirmation window 1 bar | 982 | 141.78 | 5.27 | 1.22 | 0.02 | 151.87 | 163.70 | 43.54 | -65.46 | unstable | harmful |
| V18 | confirmation window 3 bars | 704 | 124.78 | -11.73 | 1.27 | 0.02 | 124.63 | 143.27 | 70.30 | -88.78 | unstable | mixed |
| V19 | no high/extreme volatility days | 693 | 25.88 | -110.63 | 1.05 | 0.02 | 140.42 | 36.65 | 26.45 | -37.23 | unstable | harmful |
| V20 | max spread filter: no setup when spread > 2x model median | 772 | 44.48 | -92.03 | 1.08 | 0.02 | 141.23 | 55.93 | 26.19 | -37.63 | unstable | mixed |

## Bitcoin (BTCUSD) D1 ASIS (baseline 144 trades, net $125.93, PF 2.338, TRAIN 170 / VAL -41 / OOS -3, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 110 | 133.72 | 7.79 | 2.47 | 0.05 | 59.78 | 159.13 | -23.00 | -2.42 | unstable | mixed |
| V02 | ADX(14) >= 20 | 137 | 102.38 | -23.55 | 2.09 | 0.03 | 60.48 | 146.08 | -41.17 | -2.53 | unstable | harmful |
| V03 | no volume filter | 202 | 117.28 | -8.65 | 2.16 | 0.02 | 62.02 | 163.51 | -42.22 | -4.02 | unstable | harmful |
| V04 | entries 08:00-21:59 server (London + New York) | 0 | 0.00 | -125.93 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 0 | 0.00 | -125.93 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V06 | no entries 00:00-06:59 server (Asia) | 0 | 0.00 | -125.93 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V07 | no entries on Monday before 08:00 (weekend gap) | 136 | 11.00 | -114.93 | 1.12 | 0.02 | 60.56 | 54.65 | -41.14 | -2.50 | unstable | harmful |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 62 | 114.21 | -11.72 | 2.31 | 0.10 | 61.08 | 174.85 | -0.81 | -59.82 | unstable | mixed |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 131 | 129.46 | 3.53 | 2.43 | 0.04 | 60.13 | 172.90 | -40.82 | -2.62 | unstable | mixed |
| V10 | MA18 slope filter over 3 bars | 127 | 118.59 | -7.34 | 2.27 | 0.03 | 60.42 | 162.09 | -41.14 | -2.36 | unstable | harmful |
| V11 | no entry when |close - MA18| > 2 ATR | 85 | 88.43 | -37.50 | 11.77 | 0.05 | 3.00 | 90.50 | -1.37 | -0.70 | unstable | mixed |
| V12 | trend-regime gate: no sideways days | 115 | 188.95 | 63.02 | 7.07 | 0.06 | 27.96 | 173.13 | 16.69 | -0.87 | unstable | helpful |
| V13 | regime-aligned direction | 101 | 190.29 | 64.36 | 7.39 | 0.07 | 26.85 | 174.27 | 16.69 | -0.67 | unstable | helpful |
| V14 | long only | 78 | 189.44 | 63.51 | 7.18 | 0.08 | 26.21 | 174.35 | 16.77 | -1.69 | unstable | mixed |
| V15 | short only | 66 | -63.51 | -189.44 | 0.00 | -0.02 | 63.51 | -4.55 | -58.03 | -0.93 | negative | harmful |
| V16 | pending order expires after 3 bars | 145 | 91.92 | -34.01 | 1.72 | 0.03 | 86.52 | 177.48 | -23.32 | -62.24 | unstable | mixed |
| V17 | confirmation window 1 bar | 180 | 124.30 | -1.63 | 2.30 | 0.03 | 60.85 | 168.59 | -41.46 | -2.82 | unstable | mixed |
| V18 | confirmation window 3 bars | 122 | 159.62 | 33.69 | 3.26 | 0.05 | 60.33 | 203.18 | -41.11 | -2.44 | unstable | harmful |
| V19 | no high/extreme volatility days | 135 | 126.43 | 0.50 | 2.35 | 0.04 | 60.56 | 170.30 | -41.26 | -2.62 | unstable | mixed |
| V20 | max spread filter: no setup when spread > 2x model median | 144 | 125.93 | 0.00 | 2.34 | 0.04 | 60.56 | 169.81 | -41.26 | -2.62 | unstable | mixed |

## Bitcoin (BTCUSD) ASIS: higher-timeframe gates

| id | entry | HTF | trades | base trades | net $ | base net $ | PF | exp R | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M09 | 4h | D1 | 407 | 807 | 42.50 | 136.51 | 1.11 | 0.01 | 36.66 | -11.25 | 17.09 | unstable | harmful |
| M09c | 4h | D1 | 386 | 807 | -14.69 | 136.51 | 0.96 | -0.00 | 49.52 | -12.05 | -52.16 | negative | harmful |

## Bitcoin (BTCUSD) D1 FINAL_H4 (baseline 54 trades, net $487.37, PF 1.612, TRAIN 122 / VAL 53 / OOS 312, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 48 | 254.04 | -233.33 | 1.28 | 0.10 | 316.46 | 138.72 | -149.08 | 264.41 | unstable | harmful |
| V02 | ADX(14) >= 20 | 51 | 407.90 | -79.47 | 1.47 | 0.13 | 244.61 | 116.53 | -3.24 | 294.61 | unstable | harmful |
| V03 | no volume filter | 76 | 283.26 | -204.11 | 1.28 | -0.00 | 312.34 | -109.64 | 100.34 | 292.56 | unstable | harmful |
| V04 | entries 08:00-21:59 server (London + New York) | 0 | 0.00 | -487.37 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 0 | 0.00 | -487.37 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V06 | no entries 00:00-06:59 server (Asia) | 0 | 0.00 | -487.37 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | negative | mixed |
| V07 | no entries on Monday before 08:00 (weekend gap) | 53 | 627.49 | 140.12 | 1.93 | 0.16 | 149.87 | 98.77 | 239.39 | 289.33 | unstable | harmful |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 32 | -353.67 | -841.04 | 0.52 | -0.02 | 393.71 | -70.78 | -157.12 | -125.78 | negative | harmful |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 50 | 623.35 | 135.98 | 1.97 | 0.15 | 125.18 | 153.21 | 158.33 | 311.80 | unstable | mixed |
| V10 | MA18 slope filter over 3 bars | 50 | 318.81 | -168.56 | 1.45 | 0.17 | 139.04 | 46.47 | 166.48 | 105.85 | unstable | harmful |
| V11 | no entry when |close - MA18| > 2 ATR | 46 | 152.41 | -334.96 | 1.20 | 0.11 | 316.65 | 93.77 | -115.89 | 174.54 | unstable | harmful |
| V12 | trend-regime gate: no sideways days | 49 | 103.50 | -383.87 | 1.11 | 0.06 | 212.31 | 161.99 | 7.08 | -65.57 | unstable | harmful |
| V13 | regime-aligned direction | 45 | -40.97 | -528.34 | 0.96 | 0.02 | 297.21 | 153.08 | 7.08 | -201.13 | negative | harmful |
| V14 | long only | 32 | 205.63 | -281.74 | 1.39 | 0.19 | 187.16 | 54.84 | 87.22 | 63.56 | unstable | harmful |
| V15 | short only | 22 | 281.75 | -205.62 | 2.06 | 0.00 | 105.12 | 67.26 | -33.75 | 248.24 | unstable | mixed |
| V16 | pending order expires after 3 bars | 53 | 483.26 | -4.11 | 1.63 | 0.20 | 187.89 | 76.00 | 53.47 | 353.79 | unstable | mixed |
| V17 | confirmation window 1 bar | 65 | 701.34 | 213.97 | 1.78 | 0.13 | 185.73 | 216.56 | 223.50 | 261.28 | unstable | mixed |
| V18 | confirmation window 3 bars | 49 | 244.68 | -242.69 | 1.30 | 0.11 | 186.81 | 93.60 | 24.29 | 126.79 | unstable | harmful |
| V19 | no high/extreme volatility days | 52 | 498.10 | 10.73 | 1.64 | 0.14 | 187.89 | 132.83 | 53.47 | 311.80 | unstable | mixed |
| V20 | max spread filter: no setup when spread > 2x model median | 54 | 487.37 | 0.00 | 1.61 | 0.11 | 187.89 | 122.10 | 53.47 | 311.80 | unstable | mixed |

## US Oil (WTI) 4h ASIS (baseline 166 trades, net $0.98, PF 1.007, TRAIN 0 / VAL -7 / OOS 8, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 131 | -25.55 | -26.53 | 0.81 | -0.02 | 35.25 | -14.04 | -7.73 | -3.78 | negative | harmful |
| V02 | ADX(14) >= 20 | 155 | -15.34 | -16.32 | 0.90 | 0.00 | 30.63 | -8.14 | -5.78 | -1.42 | negative | harmful |
| V03 | no volume filter | 209 | 8.74 | 7.76 | 1.05 | 0.04 | 24.03 | -6.59 | -3.25 | 18.58 | unstable | mixed |
| V04 | entries 08:00-21:59 server (London + New York) | 166 | -0.65 | -1.63 | 0.99 | 0.02 | 26.11 | 4.23 | -9.71 | 4.83 | negative | harmful |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 141 | -3.78 | -4.76 | 0.97 | -0.01 | 24.91 | -1.85 | -5.59 | 3.66 | negative | harmful |
| V06 | no entries 00:00-06:59 server (Asia) | 166 | -0.65 | -1.63 | 0.99 | 0.02 | 26.11 | 4.23 | -9.71 | 4.83 | negative | harmful |
| V07 | no entries on Monday before 08:00 (weekend gap) | 166 | 0.98 | 0.00 | 1.01 | 0.03 | 22.03 | 0.04 | -7.47 | 8.41 | unstable | mixed |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 78 | 8.43 | 7.45 | 1.12 | 0.10 | 14.13 | 7.18 | -1.97 | 3.22 | unstable | mixed |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 163 | 5.61 | 4.63 | 1.04 | 0.04 | 20.92 | 0.04 | -6.36 | 11.93 | unstable | mixed |
| V10 | MA18 slope filter over 3 bars | 147 | 14.09 | 13.11 | 1.12 | 0.06 | 23.69 | 7.48 | -8.70 | 15.31 | unstable | mixed |
| V11 | no entry when |close - MA18| > 2 ATR | 152 | 9.36 | 8.38 | 1.08 | 0.02 | 22.60 | 2.31 | -9.14 | 16.19 | unstable | mixed |
| V12 | trend-regime gate: no sideways days | 130 | -10.24 | -11.22 | 0.92 | 0.00 | 27.76 | -9.14 | -5.89 | 4.79 | negative | harmful |
| V13 | regime-aligned direction | 87 | -3.94 | -4.92 | 0.95 | -0.04 | 24.54 | -7.42 | -2.46 | 5.94 | negative | harmful |
| V14 | long only | 76 | 12.38 | 11.40 | 1.18 | 0.12 | 18.13 | -5.34 | -2.55 | 20.27 | unstable | mixed |
| V15 | short only | 90 | -11.40 | -12.38 | 0.84 | -0.04 | 25.83 | 5.38 | -4.92 | -11.86 | negative | harmful |
| V16 | pending order expires after 3 bars | 166 | -11.52 | -12.50 | 0.92 | 0.01 | 33.81 | 0.97 | -10.00 | -2.49 | negative | harmful |
| V17 | confirmation window 1 bar | 227 | -4.12 | -5.10 | 0.98 | -0.02 | 31.82 | -9.03 | -13.48 | 18.39 | negative | harmful |
| V18 | confirmation window 3 bars | 142 | 2.80 | 1.82 | 1.02 | 0.06 | 28.30 | 7.54 | -5.95 | 1.21 | unstable | harmful |
| V19 | no high/extreme volatility days | 131 | 4.94 | 3.96 | 1.05 | 0.02 | 20.70 | -0.94 | -6.14 | 12.02 | unstable | mixed |
| V20 | max spread filter: no setup when spread > 2x model median | 166 | 0.98 | 0.00 | 1.01 | 0.03 | 22.03 | 0.04 | -7.47 | 8.41 | unstable | mixed |

## US Oil (WTI) ASIS: higher-timeframe gates

| id | entry | HTF | trades | base trades | net $ | base net $ | PF | exp R | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M09 | 4h | D1 | 84 | 166 | 4.10 | 0.98 | 1.06 | 0.06 | 1.95 | -3.40 | 5.55 | unstable | helpful |
| M09c | 4h | D1 | 77 | 166 | -5.03 | 0.98 | 0.93 | -0.00 | -7.37 | -5.12 | 7.46 | negative | harmful |

## US Oil (WTI) 4h FINAL_H4 (baseline 194 trades, net $20.31, PF 1.113, TRAIN 17 / VAL -7 / OOS 10, unstable)

| id | variant | trades | net $ | d net $ | PF | exp R | max DD $ | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 155 | -11.54 | -31.85 | 0.93 | 0.02 | 40.36 | -12.46 | -4.61 | 5.53 | negative | harmful |
| V02 | ADX(14) >= 20 | 181 | 3.50 | -16.81 | 1.02 | 0.05 | 46.82 | 0.35 | -5.39 | 8.54 | unstable | harmful |
| V03 | no volume filter | 258 | 16.38 | -3.93 | 1.07 | 0.03 | 39.50 | 5.15 | -3.30 | 14.53 | unstable | mixed |
| V04 | entries 08:00-21:59 server (London + New York) | 194 | 42.03 | 21.72 | 1.28 | 0.07 | 24.64 | 18.13 | -10.46 | 34.36 | unstable | mixed |
| V05 | entries 13:00-16:59 server (London/NY overlap) | 165 | -5.62 | -25.93 | 0.96 | 0.05 | 42.16 | 9.42 | -2.15 | -12.89 | negative | harmful |
| V06 | no entries 00:00-06:59 server (Asia) | 194 | 42.03 | 21.72 | 1.28 | 0.07 | 24.64 | 18.13 | -10.46 | 34.36 | unstable | mixed |
| V07 | no entries on Monday before 08:00 (weekend gap) | 194 | 51.36 | 31.05 | 1.34 | 0.09 | 20.22 | 17.29 | -7.27 | 41.34 | unstable | mixed |
| V08 | ATR(22)/SMA100(ATR) >= 1.0 | 94 | 11.69 | -8.62 | 1.11 | 0.12 | 41.36 | 13.05 | 4.65 | -6.01 | unstable | mixed |
| V09 | ATR(22)/SMA100(ATR) <= 1.5 | 188 | 26.41 | 6.10 | 1.18 | 0.08 | 23.05 | 20.03 | -6.26 | 12.64 | unstable | helpful |
| V10 | MA18 slope filter over 3 bars | 175 | 6.85 | -13.46 | 1.04 | 0.06 | 53.18 | 21.43 | -8.25 | -6.33 | unstable | harmful |
| V11 | no entry when |close - MA18| > 2 ATR | 179 | 23.75 | 3.44 | 1.19 | 0.05 | 18.90 | 7.62 | -5.48 | 21.61 | unstable | mixed |
| V12 | trend-regime gate: no sideways days | 151 | 14.07 | -6.24 | 1.09 | 0.04 | 44.74 | 8.18 | -1.24 | 7.13 | unstable | harmful |
| V13 | regime-aligned direction | 103 | 18.61 | -1.70 | 1.17 | 0.04 | 39.35 | 11.70 | 1.22 | 5.69 | unstable | mixed |
| V14 | long only | 92 | 9.99 | -10.32 | 1.10 | 0.13 | 39.35 | -4.58 | -7.49 | 22.06 | unstable | harmful |
| V15 | short only | 102 | 10.32 | -9.99 | 1.14 | 0.04 | 19.90 | 21.87 | 0.22 | -11.77 | unstable | mixed |
| V16 | pending order expires after 3 bars | 198 | 12.16 | -8.15 | 1.07 | 0.06 | 48.57 | 20.10 | -7.59 | -0.35 | unstable | mixed |
| V17 | confirmation window 1 bar | 267 | -3.81 | -24.12 | 0.98 | 0.01 | 45.36 | -6.97 | -6.88 | 10.04 | negative | harmful |
| V18 | confirmation window 3 bars | 167 | 1.72 | -18.59 | 1.01 | 0.10 | 46.82 | 19.98 | -2.84 | -15.42 | unstable | mixed |
| V19 | no high/extreme volatility days | 157 | 41.53 | 21.22 | 1.38 | 0.07 | 22.11 | 13.41 | -9.16 | 37.28 | unstable | harmful |
| V20 | max spread filter: no setup when spread > 2x model median | 194 | 20.31 | 0.00 | 1.11 | 0.08 | 44.74 | 17.29 | -7.27 | 10.29 | unstable | mixed |

## US Oil (WTI) FINAL_H4: higher-timeframe gates

| id | entry | HTF | trades | base trades | net $ | base net $ | PF | exp R | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M09 | 4h | D1 | 101 | 194 | 19.95 | 20.31 | 1.19 | 0.14 | 7.26 | 1.74 | 10.95 | unstable | mixed |
| M09c | 4h | D1 | 90 | 194 | 12.91 | 20.31 | 1.13 | 0.09 | 0.09 | 0.50 | 12.32 | unstable | mixed |