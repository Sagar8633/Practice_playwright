# Strategy variants and higher-timeframe confirmation (scenario B costs, candidate timeframes)

Each row is one experiment: the baseline configuration plus exactly one change. 'd net' = net points versus the baseline of the same instrument / config / timeframe. Verdict rule as in the baseline (robust = positive expectancy and PF > 1 after costs in TRAIN, VAL and OOS with >= 30 trades each). A variant is 'helpful' only if it improves expectancy in all three splits; improvements that appear in one split only are noise until proven otherwise.


## NIFTY 50 15m ASIS (baseline: 1330 trades, net 1,643 pts, PF 1.05, TRAIN 520 / VAL -428 / OOS 1,550, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 1014 | -527.70 | -2,170.00 | 0.98 | -0.52 | -0.01 | 3,834.80 | -1,059.30 | -231.40 | 763.10 | negative | harmful |
| V02 | ADX(14) >= 20 | 1188 | 1,462.50 | -180.00 | 1.05 | 1.23 | 0.02 | 2,674.30 | 185.50 | 371.60 | 905.50 | robust | harmful |
| V03 | no entries in the opening phase (before 09:45) | 1338 | 353.50 | -1,289.00 | 1.01 | 0.26 | -0.00 | 3,352.50 | -183.90 | -800.80 | 1,338.10 | unstable | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 992 | -729.30 | -2,372.00 | 0.97 | -0.73 | -0.02 | 2,100.00 | 297.30 | -345.70 | -680.90 | negative | harmful |
| V05 | no entries in the closing phase (after 15:00) | 1276 | -61.50 | -1,704.00 | 1.00 | -0.05 | -0.02 | 2,855.80 | -1,553.40 | -176.90 | 1,668.80 | negative | mixed |
| V06 | no entries in the first hour (before 10:15) | 1263 | 1,516.80 | -126.00 | 1.05 | 1.20 | -0.01 | 3,519.20 | -423.00 | 520.30 | 1,419.40 | unstable | harmful |
| V07 | skip sessions with |gap| > 0.5% | 1079 | -2,174.30 | -3,817.00 | 0.92 | -2.02 | -0.03 | 3,945.70 | -1,425.20 | -1,281.00 | 531.90 | negative | harmful |
| V08 | only sessions with |gap| <= 0.25% | 711 | -196.20 | -1,839.00 | 0.99 | -0.28 | -0.03 | 2,370.00 | -287.80 | -426.70 | 518.20 | negative | harmful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 694 | -1,456.70 | -3,099.00 | 0.92 | -2.10 | -0.01 | 3,196.50 | -32.50 | 791.90 | -2,216.00 | negative | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 1299 | 1,772.90 | 130.00 | 1.05 | 1.36 | 0.01 | 2,300.70 | 647.90 | -203.20 | 1,328.20 | unstable | mixed |
| V11 | MA18 slope filter over 3 bars | 1185 | 1,974.60 | 332.00 | 1.07 | 1.67 | 0.03 | 2,391.30 | -469.80 | 724.20 | 1,720.20 | unstable | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 1221 | 990.60 | -652.00 | 1.03 | 0.81 | -0.02 | 3,430.40 | 212.10 | -876.40 | 1,654.90 | unstable | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 1089 | 442.20 | -1,200.00 | 1.02 | 0.41 | 0.01 | 3,063.00 | 137.60 | -1,310.90 | 1,615.50 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 642 | -16.20 | -1,659.00 | 1.00 | -0.03 | 0.01 | 2,486.60 | 311.50 | -1,169.40 | 841.70 | negative | mixed |
| V15 | long only | 696 | 1,861.90 | 219.00 | 1.11 | 2.67 | 0.01 | 1,009.80 | 1,836.40 | -176.40 | 201.90 | unstable | mixed |
| V16 | short only | 634 | -219.30 | -1,862.00 | 0.99 | -0.35 | -0.00 | 3,488.10 | -1,316.20 | -251.70 | 1,348.50 | negative | harmful |
| V17 | pending order expires after 3 bars | 1405 | 799.50 | -843.00 | 1.02 | 0.57 | -0.01 | 2,852.80 | 412.60 | -905.70 | 1,292.60 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 1780 | -3,316.20 | -4,959.00 | 0.93 | -1.86 | -0.04 | 4,981.00 | -3,031.70 | 18.10 | -302.60 | negative | harmful |
| V19 | confirmation window 3 bars | 1164 | -238.30 | -1,881.00 | 0.99 | -0.20 | -0.02 | 3,072.70 | -101.90 | -17.90 | -118.40 | negative | harmful |
| V20 | no sessions of high/extreme realised volatility | 1037 | -284.90 | -1,928.00 | 0.99 | -0.28 | 0.01 | 2,751.60 | -1,628.60 | 674.50 | 669.20 | negative | harmful |

## NIFTY 50 30m ASIS (baseline: 739 trades, net 2,628 pts, PF 1.115, TRAIN 2,594 / VAL 484 / OOS -450, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 586 | 3,220.40 | 592.00 | 1.20 | 5.50 | 0.06 | 1,725.40 | 2,224.20 | 405.20 | 590.90 | robust | helpful |
| V02 | ADX(14) >= 20 | 688 | 3,249.20 | 621.00 | 1.16 | 4.72 | 0.05 | 1,763.20 | 1,978.80 | 953.50 | 316.90 | robust | mixed |
| V03 | no entries in the opening phase (before 09:45) | 733 | 2,797.40 | 169.00 | 1.12 | 3.82 | 0.05 | 2,592.40 | 2,736.10 | 568.70 | -507.40 | unstable | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 600 | 4,414.50 | 1,786.00 | 1.30 | 7.36 | 0.06 | 1,606.00 | 2,489.80 | 1,352.50 | 572.20 | robust | helpful |
| V05 | no entries in the closing phase (after 15:00) | 732 | 2,363.70 | -264.00 | 1.11 | 3.23 | 0.01 | 2,800.00 | 2,377.60 | 761.30 | -775.20 | unstable | harmful |
| V06 | no entries in the first hour (before 10:15) | 731 | 1,630.00 | -998.00 | 1.07 | 2.23 | 0.03 | 3,030.30 | 2,175.40 | 351.60 | -896.90 | unstable | harmful |
| V07 | skip sessions with |gap| > 0.5% | 605 | 4,535.30 | 1,907.00 | 1.26 | 7.50 | 0.06 | 1,688.00 | 2,438.30 | 1,758.60 | 338.40 | robust | helpful |
| V08 | only sessions with |gap| <= 0.25% | 437 | 3,385.00 | 757.00 | 1.28 | 7.75 | 0.06 | 1,434.60 | 1,834.30 | 973.10 | 577.60 | robust | helpful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 410 | -49.70 | -2,678.00 | 1.00 | -0.12 | 0.04 | 3,405.30 | 2,243.20 | -1,005.20 | -1,287.70 | negative | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 725 | 2,670.40 | 42.00 | 1.12 | 3.68 | 0.04 | 2,552.70 | 2,722.30 | 484.20 | -536.10 | unstable | mixed |
| V11 | MA18 slope filter over 3 bars | 656 | 2,621.70 | -6.00 | 1.13 | 4.00 | 0.07 | 2,444.10 | 1,744.20 | 1,307.60 | -430.20 | unstable | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 647 | 2,805.60 | 178.00 | 1.14 | 4.34 | 0.05 | 1,868.60 | 2,336.40 | 590.90 | -121.60 | unstable | helpful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 607 | 2,126.00 | -502.00 | 1.11 | 3.50 | 0.06 | 2,530.60 | 2,943.80 | 200.50 | -1,018.30 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 397 | 4,171.80 | 1,544.00 | 1.39 | 10.51 | 0.10 | 1,503.50 | 3,429.40 | -43.30 | 785.70 | unstable | mixed |
| V15 | long only | 389 | 3,236.40 | 608.00 | 1.29 | 8.32 | 0.09 | 2,238.80 | 3,742.60 | 733.50 | -1,239.80 | unstable | mixed |
| V16 | short only | 350 | -608.40 | -3,236.00 | 0.95 | -1.74 | -0.03 | 2,970.40 | -1,149.10 | -249.20 | 789.90 | negative | harmful |
| V17 | pending order expires after 3 bars | 771 | 3,073.60 | 446.00 | 1.13 | 3.99 | 0.03 | 2,337.40 | 3,920.10 | -325.90 | -520.60 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 956 | 2,434.80 | -193.00 | 1.09 | 2.55 | -0.02 | 2,979.00 | 3,568.40 | 520.50 | -1,654.20 | unstable | harmful |
| V19 | confirmation window 3 bars | 673 | 1,462.20 | -1,166.00 | 1.07 | 2.17 | 0.07 | 2,080.50 | 1,140.50 | 650.10 | -328.40 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 566 | 1,862.60 | -765.00 | 1.11 | 3.29 | 0.05 | 2,349.30 | 438.80 | 1,176.10 | 247.70 | robust | mixed |

## NIFTY 50 1h ASIS (baseline: 418 trades, net 3,332 pts, PF 1.233, TRAIN 2,087 / VAL 1,383 / OOS -138, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 329 | 3,078.80 | -253.00 | 1.29 | 9.36 | 0.06 | 1,121.10 | 1,790.10 | 1,806.50 | -517.70 | unstable | mixed |
| V02 | ADX(14) >= 20 | 390 | 3,834.20 | 502.00 | 1.31 | 9.83 | 0.06 | 1,176.10 | 2,719.90 | 1,165.00 | -50.70 | unstable | mixed |
| V03 | no entries in the opening phase (before 09:45) | 412 | 3,446.40 | 114.00 | 1.25 | 8.37 | 0.09 | 1,474.60 | 1,995.00 | 1,453.30 | -1.90 | unstable | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 359 | 4,563.00 | 1,231.00 | 1.42 | 12.71 | 0.11 | 1,222.00 | 2,699.80 | 1,326.40 | 536.80 | robust | helpful |
| V05 | no entries in the closing phase (after 15:00) | 410 | 3,702.60 | 370.00 | 1.27 | 9.03 | 0.10 | 1,746.40 | 2,598.40 | 1,377.50 | -273.30 | unstable | mixed |
| V06 | no entries in the first hour (before 10:15) | 412 | 3,446.40 | 114.00 | 1.25 | 8.37 | 0.09 | 1,474.60 | 1,995.00 | 1,453.30 | -1.90 | unstable | mixed |
| V07 | skip sessions with |gap| > 0.5% | 346 | 5,333.60 | 2,002.00 | 1.47 | 15.41 | 0.12 | 1,351.70 | 4,158.90 | 1,068.70 | 106.00 | robust | mixed |
| V08 | only sessions with |gap| <= 0.25% | 267 | 5,120.10 | 1,788.00 | 1.64 | 19.18 | 0.09 | 1,017.60 | 2,777.20 | 990.30 | 1,352.60 | robust | helpful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 235 | 1,447.50 | -1,885.00 | 1.19 | 6.16 | 0.03 | 1,428.50 | 1,117.70 | -753.70 | 1,083.50 | unstable | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 418 | 3,116.00 | -216.00 | 1.22 | 7.46 | 0.08 | 1,467.80 | 1,906.90 | 1,382.50 | -173.40 | unstable | harmful |
| V11 | MA18 slope filter over 3 bars | 381 | 2,659.20 | -673.00 | 1.20 | 6.98 | 0.08 | 1,895.70 | 896.10 | 2,035.20 | -272.10 | unstable | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 355 | 4,428.70 | 1,097.00 | 1.38 | 12.47 | 0.10 | 1,309.20 | 3,192.80 | 1,052.10 | 183.80 | robust | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 348 | 2,688.90 | -643.00 | 1.22 | 7.73 | 0.08 | 1,484.60 | 2,233.90 | 497.30 | -42.30 | unstable | mixed |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 266 | 1,680.00 | -1,652.00 | 1.18 | 6.32 | 0.07 | 1,642.70 | 1,274.20 | -157.80 | 563.70 | unstable | harmful |
| V15 | long only | 229 | 4,405.90 | 1,074.00 | 1.58 | 19.24 | 0.18 | 1,367.30 | 4,196.30 | 904.00 | -694.40 | unstable | mixed |
| V16 | short only | 189 | -1,073.80 | -4,406.00 | 0.84 | -5.68 | -0.03 | 2,265.90 | -2,108.90 | 478.60 | 556.50 | negative | harmful |
| V17 | pending order expires after 3 bars | 449 | 1,963.30 | -1,369.00 | 1.12 | 4.37 | 0.06 | 2,246.90 | 2,440.80 | 479.00 | -956.60 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 550 | 3,365.60 | 34.00 | 1.20 | 6.12 | 0.03 | 2,237.30 | 3,119.50 | 1,200.50 | -954.50 | unstable | harmful |
| V19 | confirmation window 3 bars | 385 | 3,093.00 | -239.00 | 1.23 | 8.03 | 0.08 | 1,593.30 | 1,818.50 | 1,371.80 | -97.30 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 332 | 2,945.40 | -387.00 | 1.28 | 8.87 | 0.08 | 1,309.10 | 2,270.30 | 499.40 | 175.70 | robust | mixed |

## NIFTY 50 2h ASIS (baseline: 262 trades, net 3,092 pts, PF 1.333, TRAIN 2,521 / VAL 525 / OOS 46, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 233 | 774.90 | -2,317.00 | 1.12 | 3.33 | 0.02 | 1,282.30 | 963.90 | 259.30 | -448.30 | unstable | harmful |
| V02 | ADX(14) >= 20 | 251 | 1,477.00 | -1,615.00 | 1.19 | 5.88 | 0.05 | 1,098.50 | 1,154.30 | 660.90 | -338.10 | unstable | harmful |
| V03 | no entries in the opening phase (before 09:45) | 256 | 3,133.00 | 41.00 | 1.34 | 12.24 | 0.11 | 1,658.50 | 2,497.10 | 575.40 | 60.50 | robust | helpful |
| V04 | entries only 09:45-13:29 (morning + midday) | 235 | 3,373.00 | 281.00 | 1.41 | 14.35 | 0.10 | 2,019.20 | 2,747.40 | 770.50 | -145.00 | unstable | mixed |
| V05 | no entries in the closing phase (after 15:00) | 249 | 4,792.10 | 1,700.00 | 1.74 | 19.25 | 0.08 | 965.50 | 2,871.70 | 815.30 | 1,105.20 | robust | helpful |
| V06 | no entries in the first hour (before 10:15) | 256 | 3,133.00 | 41.00 | 1.34 | 12.24 | 0.11 | 1,658.50 | 2,497.10 | 575.40 | 60.50 | robust | helpful |
| V07 | skip sessions with |gap| > 0.5% | 217 | 3,706.60 | 615.00 | 1.43 | 17.08 | 0.13 | 1,662.60 | 3,067.50 | 424.30 | 214.90 | robust | mixed |
| V08 | only sessions with |gap| <= 0.25% | 174 | 2,870.50 | -222.00 | 1.42 | 16.50 | 0.10 | 1,970.60 | 2,910.30 | -402.80 | 363.00 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 153 | -1,447.00 | -4,539.00 | 0.74 | -9.46 | -0.02 | 2,761.10 | 87.00 | 223.10 | -1,757.20 | negative | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 261 | 3,862.80 | 771.00 | 1.48 | 14.80 | 0.10 | 1,097.50 | 1,770.60 | 524.70 | 1,567.50 | robust | mixed |
| V11 | MA18 slope filter over 3 bars | 243 | 3,923.10 | 831.00 | 1.57 | 16.14 | 0.08 | 1,002.30 | 2,352.10 | 40.90 | 1,530.00 | robust | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 207 | 5,512.80 | 2,421.00 | 1.88 | 26.63 | 0.15 | 904.10 | 2,946.40 | 511.10 | 2,055.30 | robust | helpful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 214 | 2,196.40 | -896.00 | 1.26 | 10.26 | 0.10 | 2,314.40 | 2,147.30 | 292.80 | -243.70 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 179 | 1,539.40 | -1,553.00 | 1.20 | 8.60 | 0.10 | 2,634.10 | 1,922.40 | 307.00 | -690.00 | unstable | harmful |
| V15 | long only | 164 | 2,911.80 | -180.00 | 1.64 | 17.75 | 0.11 | 1,022.10 | 3,230.70 | -349.40 | 30.60 | unstable | mixed |
| V16 | short only | 98 | 180.20 | -2,912.00 | 1.04 | 1.84 | 0.09 | 1,658.50 | -709.70 | 874.20 | 15.80 | unstable | harmful |
| V17 | pending order expires after 3 bars | 267 | 3,381.50 | 290.00 | 1.37 | 12.66 | 0.12 | 1,699.10 | 3,379.40 | 225.80 | -223.70 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 326 | 4,511.40 | 1,419.00 | 1.41 | 13.84 | 0.12 | 1,804.60 | 2,778.80 | 489.00 | 1,243.60 | robust | harmful |
| V19 | confirmation window 3 bars | 225 | 3,270.60 | 179.00 | 1.40 | 14.54 | 0.09 | 1,622.90 | 2,793.50 | -242.10 | 719.30 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 226 | 154.30 | -2,938.00 | 1.02 | 0.68 | 0.05 | 2,335.50 | 1,346.90 | 551.20 | -1,743.90 | unstable | harmful |

## NIFTY 50 4h ASIS (baseline: 139 trades, net 4,035 pts, PF 1.675, TRAIN 3,310 / VAL 20 / OOS 705, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 108 | 2,219.90 | -1,815.00 | 1.48 | 20.55 | 0.15 | 1,626.90 | 2,871.10 | 83.20 | -734.40 | unstable | mixed |
| V02 | ADX(14) >= 20 | 134 | 1,674.00 | -2,361.00 | 1.30 | 12.49 | 0.09 | 2,087.40 | 2,821.30 | 33.30 | -1,180.60 | unstable | harmful |
| V03 | no entries in the opening phase (before 09:45) | 135 | 3,886.30 | -148.00 | 1.71 | 28.79 | 0.17 | 1,523.70 | 3,420.20 | -279.80 | 745.90 | unstable | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 135 | 3,886.30 | -148.00 | 1.71 | 28.79 | 0.17 | 1,523.70 | 3,420.20 | -279.80 | 745.90 | unstable | mixed |
| V05 | no entries in the closing phase (after 15:00) | 139 | 4,034.70 | 0.00 | 1.68 | 29.03 | 0.13 | 1,547.20 | 3,310.00 | 19.90 | 704.80 | robust | mixed |
| V06 | no entries in the first hour (before 10:15) | 135 | 3,886.30 | -148.00 | 1.71 | 28.79 | 0.17 | 1,523.70 | 3,420.20 | -279.80 | 745.90 | unstable | mixed |
| V07 | skip sessions with |gap| > 0.5% | 136 | 3,836.90 | -198.00 | 1.67 | 28.21 | 0.13 | 1,053.30 | 2,149.00 | 689.80 | 998.20 | robust | mixed |
| V08 | only sessions with |gap| <= 0.25% | 105 | 4,361.90 | 327.00 | 2.41 | 41.54 | 0.18 | 746.70 | 1,727.30 | 1,107.20 | 1,527.40 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 73 | 1,837.30 | -2,197.00 | 1.49 | 25.17 | 0.09 | 1,160.80 | 295.20 | 540.80 | 1,001.30 | unstable | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 136 | 3,599.00 | -436.00 | 1.60 | 26.46 | 0.13 | 1,540.10 | 2,867.20 | 19.90 | 711.90 | robust | mixed |
| V11 | MA18 slope filter over 3 bars | 135 | 2,317.20 | -1,718.00 | 1.45 | 17.16 | 0.10 | 1,352.40 | 1,226.90 | 181.00 | 909.30 | robust | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 122 | 3,541.20 | -494.00 | 1.69 | 29.03 | 0.13 | 1,208.30 | 2,009.60 | 773.40 | 758.10 | unstable | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 130 | 3,317.80 | -717.00 | 1.55 | 25.52 | 0.16 | 1,465.70 | 2,128.00 | 263.50 | 926.30 | unstable | mixed |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 127 | 2,469.30 | -1,565.00 | 1.42 | 19.44 | 0.13 | 1,649.10 | 1,536.30 | 80.10 | 853.00 | unstable | mixed |
| V15 | long only | 100 | 1,047.00 | -2,988.00 | 1.23 | 10.47 | 0.11 | 1,560.40 | 2,607.40 | -674.50 | -885.90 | unstable | harmful |
| V16 | short only | 39 | 2,987.60 | -1,047.00 | 3.26 | 76.61 | 0.17 | 545.60 | 702.60 | 694.40 | 1,590.70 | unstable | helpful |
| V17 | pending order expires after 3 bars | 138 | 4,079.40 | 45.00 | 1.67 | 29.56 | 0.17 | 1,519.60 | 2,968.40 | -452.90 | 1,563.90 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 181 | 2,416.00 | -1,619.00 | 1.36 | 13.35 | 0.08 | 1,475.50 | 1,545.40 | 51.40 | 819.20 | robust | mixed |
| V19 | confirmation window 3 bars | 144 | 1,147.70 | -2,887.00 | 1.17 | 7.97 | 0.11 | 2,053.50 | 1,481.30 | -266.20 | -67.50 | unstable | harmful |
| V20 | no sessions of high/extreme realised volatility | 134 | -411.00 | -4,446.00 | 0.93 | -3.07 | 0.06 | 2,056.40 | 718.70 | 55.60 | -1,185.30 | negative | harmful |

## NIFTY 50 15m FINAL_H4 (baseline: 1158 trades, net 4,285 pts, PF 1.101, TRAIN 400 / VAL 1,788 / OOS 2,098, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 887 | 2,483.70 | -1,801.00 | 1.07 | 2.80 | 0.00 | 3,408.70 | -502.80 | 1,698.00 | 1,288.50 | unstable | harmful |
| V02 | ADX(14) >= 20 | 1038 | 5,166.90 | 882.00 | 1.13 | 4.98 | 0.05 | 2,438.50 | 506.00 | 2,623.80 | 2,037.10 | robust | helpful |
| V03 | no entries in the opening phase (before 09:45) | 1164 | 3,777.70 | -507.00 | 1.09 | 3.25 | 0.03 | 2,898.30 | 77.60 | 1,117.40 | 2,582.70 | robust | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 875 | -1,664.80 | -5,950.00 | 0.95 | -1.90 | -0.03 | 3,030.30 | -2,178.80 | 193.20 | 320.90 | negative | harmful |
| V05 | no entries in the closing phase (after 15:00) | 1089 | 3,232.60 | -1,053.00 | 1.08 | 2.97 | -0.00 | 3,007.80 | -1,116.10 | 1,686.20 | 2,662.50 | unstable | harmful |
| V06 | no entries in the first hour (before 10:15) | 1109 | 4,319.10 | 34.00 | 1.11 | 3.90 | 0.02 | 3,252.40 | -310.00 | 2,210.10 | 2,419.00 | unstable | mixed |
| V07 | skip sessions with |gap| > 0.5% | 927 | 306.60 | -3,979.00 | 1.01 | 0.33 | -0.03 | 3,489.50 | -1,802.20 | 1,328.30 | 780.50 | unstable | harmful |
| V08 | only sessions with |gap| <= 0.25% | 616 | 768.80 | -3,516.00 | 1.04 | 1.25 | -0.04 | 2,084.40 | -253.40 | -258.10 | 1,280.20 | unstable | harmful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 594 | 3,687.80 | -597.00 | 1.16 | 6.21 | 0.11 | 2,704.30 | 568.80 | 3,038.00 | 81.00 | robust | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 1144 | 5,388.30 | 1,103.00 | 1.13 | 4.71 | 0.04 | 1,736.70 | 1,358.40 | 1,881.70 | 2,148.20 | robust | helpful |
| V11 | MA18 slope filter over 3 bars | 1027 | 4,338.50 | 53.00 | 1.12 | 4.22 | 0.06 | 3,331.60 | -1,086.00 | 2,820.60 | 2,603.90 | unstable | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 1050 | 5,410.70 | 1,126.00 | 1.15 | 5.15 | 0.01 | 1,824.00 | 1,350.70 | 1,312.50 | 2,747.50 | robust | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 929 | 3,884.80 | -400.00 | 1.12 | 4.18 | 0.04 | 2,050.20 | 235.80 | 1,015.60 | 2,633.40 | robust | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 556 | 2,907.60 | -1,378.00 | 1.15 | 5.23 | 0.02 | 2,130.50 | 755.90 | 345.70 | 1,806.00 | robust | mixed |
| V15 | long only | 639 | 1,625.20 | -2,660.00 | 1.08 | 2.54 | 0.03 | 1,464.20 | 1,523.20 | -170.40 | 272.40 | unstable | harmful |
| V16 | short only | 519 | 2,659.90 | -1,625.00 | 1.12 | 5.12 | 0.04 | 3,703.70 | -1,123.70 | 1,958.40 | 1,825.10 | unstable | mixed |
| V17 | pending order expires after 3 bars | 1235 | 2,461.20 | -1,824.00 | 1.05 | 1.99 | 0.01 | 3,696.40 | -1,074.70 | 1,693.40 | 1,842.50 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 1581 | 3,917.30 | -368.00 | 1.08 | 2.48 | -0.03 | 2,435.90 | 440.80 | 1,876.30 | 1,600.20 | robust | harmful |
| V19 | confirmation window 3 bars | 1000 | 3,163.20 | -1,122.00 | 1.08 | 3.16 | 0.02 | 2,589.70 | -657.60 | 2,252.00 | 1,568.80 | unstable | harmful |
| V20 | no sessions of high/extreme realised volatility | 917 | 1,776.20 | -2,509.00 | 1.06 | 1.94 | 0.03 | 3,056.70 | -1,466.60 | 2,801.90 | 440.80 | unstable | harmful |

## NIFTY 50 30m FINAL_H4 (baseline: 599 trades, net 5,118 pts, PF 1.173, TRAIN 2,085 / VAL 1,269 / OOS 1,763, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 452 | 3,311.80 | -1,806.00 | 1.15 | 7.33 | 0.03 | 1,727.80 | 1,003.80 | 1,183.10 | 1,124.90 | robust | harmful |
| V02 | ADX(14) >= 20 | 549 | 3,668.70 | -1,449.00 | 1.13 | 6.68 | 0.03 | 2,095.10 | 943.20 | 1,608.90 | 1,116.70 | robust | harmful |
| V03 | no entries in the opening phase (before 09:45) | 594 | 4,957.90 | -160.00 | 1.17 | 8.35 | 0.04 | 2,148.10 | 1,748.80 | 1,540.50 | 1,668.60 | robust | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 486 | 6,215.30 | 1,097.00 | 1.27 | 12.79 | 0.07 | 1,493.00 | 1,966.80 | 2,205.90 | 2,042.50 | robust | helpful |
| V05 | no entries in the closing phase (after 15:00) | 582 | 4,927.80 | -190.00 | 1.17 | 8.47 | 0.04 | 2,228.30 | 1,431.00 | 1,617.30 | 1,879.50 | robust | mixed |
| V06 | no entries in the first hour (before 10:15) | 604 | 1,760.40 | -3,358.00 | 1.05 | 2.92 | 0.02 | 2,817.30 | 1,122.60 | 207.40 | 430.30 | robust | harmful |
| V07 | skip sessions with |gap| > 0.5% | 488 | 6,110.70 | 993.00 | 1.29 | 12.52 | 0.05 | 1,226.30 | 1,711.90 | 2,526.90 | 1,871.90 | robust | helpful |
| V08 | only sessions with |gap| <= 0.25% | 348 | 5,607.60 | 490.00 | 1.40 | 16.11 | 0.05 | 1,457.30 | 1,477.60 | 1,608.00 | 2,522.00 | robust | helpful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 324 | 716.20 | -4,402.00 | 1.04 | 2.21 | 0.01 | 2,442.50 | 1,070.50 | -661.80 | 307.40 | unstable | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 592 | 5,452.10 | 334.00 | 1.19 | 9.21 | 0.04 | 2,329.20 | 2,784.00 | 941.90 | 1,726.20 | robust | harmful |
| V11 | MA18 slope filter over 3 bars | 536 | 4,021.00 | -1,097.00 | 1.15 | 7.50 | 0.02 | 3,028.10 | 1,007.40 | 2,342.80 | 670.80 | robust | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 534 | 2,933.10 | -2,185.00 | 1.11 | 5.49 | 0.03 | 2,229.50 | 794.20 | 886.70 | 1,252.20 | robust | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 491 | 3,168.80 | -1,949.00 | 1.13 | 6.45 | 0.05 | 2,694.90 | 1,874.70 | 218.40 | 1,075.60 | robust | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 331 | 4,288.50 | -830.00 | 1.27 | 12.96 | 0.07 | 1,952.90 | 1,854.80 | 114.70 | 2,319.10 | robust | mixed |
| V15 | long only | 318 | 4,485.50 | -632.00 | 1.36 | 14.11 | 0.11 | 1,774.60 | 4,704.50 | 448.90 | -667.90 | unstable | harmful |
| V16 | short only | 281 | 632.50 | -4,486.00 | 1.04 | 2.25 | -0.04 | 3,130.00 | -2,619.10 | 820.30 | 2,431.30 | unstable | mixed |
| V17 | pending order expires after 3 bars | 623 | 2,361.70 | -2,756.00 | 1.07 | 3.79 | 0.02 | 2,745.40 | 1,707.40 | 170.80 | 483.50 | robust | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 774 | 5,438.10 | 320.00 | 1.15 | 7.03 | 0.00 | 3,340.10 | 3,812.80 | 579.60 | 1,045.80 | robust | harmful |
| V19 | confirmation window 3 bars | 528 | 2,880.40 | -2,238.00 | 1.11 | 5.46 | 0.02 | 3,660.00 | 522.40 | 2,075.10 | 282.80 | robust | harmful |
| V20 | no sessions of high/extreme realised volatility | 476 | 4,059.30 | -1,059.00 | 1.19 | 8.53 | 0.02 | 2,650.80 | 209.40 | 1,804.80 | 2,045.10 | robust | mixed |

## NIFTY 50 1h FINAL_H4 (baseline: 315 trades, net 1,930 pts, PF 1.088, TRAIN 1,178 / VAL 583 / OOS 169, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 249 | 650.80 | -1,279.00 | 1.03 | 2.61 | 0.09 | 2,465.30 | 707.00 | 865.40 | -921.70 | unstable | harmful |
| V02 | ADX(14) >= 20 | 298 | 635.90 | -1,294.00 | 1.03 | 2.13 | 0.04 | 2,592.60 | 1,550.30 | 412.20 | -1,326.70 | unstable | harmful |
| V03 | no entries in the opening phase (before 09:45) | 311 | 1,700.90 | -229.00 | 1.08 | 5.47 | 0.07 | 1,920.50 | 871.50 | 710.90 | 118.50 | robust | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 279 | 2,240.10 | 310.00 | 1.12 | 8.03 | 0.08 | 1,819.90 | 1,441.30 | 122.90 | 675.90 | robust | mixed |
| V05 | no entries in the closing phase (after 15:00) | 310 | 1,886.70 | -44.00 | 1.09 | 6.09 | 0.07 | 1,945.30 | 1,334.10 | 441.70 | 110.80 | robust | harmful |
| V06 | no entries in the first hour (before 10:15) | 311 | 1,700.90 | -229.00 | 1.08 | 5.47 | 0.07 | 1,920.50 | 871.50 | 710.90 | 118.50 | robust | harmful |
| V07 | skip sessions with |gap| > 0.5% | 264 | 3,624.20 | 1,694.00 | 1.21 | 13.73 | 0.12 | 1,926.80 | 3,776.60 | 376.30 | -528.70 | unstable | harmful |
| V08 | only sessions with |gap| <= 0.25% | 203 | 3,081.70 | 1,151.00 | 1.24 | 15.18 | 0.08 | 1,429.50 | 2,056.90 | -448.00 | 1,472.80 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 175 | 2,666.40 | 736.00 | 1.23 | 15.24 | 0.10 | 1,743.10 | 1,725.50 | -140.30 | 1,081.20 | unstable | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 314 | 1,855.10 | -75.00 | 1.08 | 5.91 | 0.06 | 1,920.50 | 1,088.70 | 633.10 | 133.40 | robust | harmful |
| V11 | MA18 slope filter over 3 bars | 287 | 1,663.00 | -267.00 | 1.08 | 5.79 | 0.05 | 2,205.70 | 679.60 | 907.00 | 76.30 | robust | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 267 | 1,502.50 | -428.00 | 1.08 | 5.63 | 0.04 | 1,339.10 | 904.90 | -286.50 | 884.10 | unstable | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 263 | 1,549.50 | -381.00 | 1.09 | 5.89 | 0.04 | 1,991.70 | 2,125.70 | -244.30 | -331.80 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 203 | 309.20 | -1,621.00 | 1.02 | 1.52 | -0.02 | 2,000.20 | 438.90 | -1,219.70 | 1,090.10 | unstable | harmful |
| V15 | long only | 182 | 1,235.40 | -695.00 | 1.10 | 6.79 | 0.09 | 2,123.90 | 2,212.10 | 206.90 | -1,183.60 | unstable | harmful |
| V16 | short only | 133 | 694.70 | -1,236.00 | 1.07 | 5.22 | 0.02 | 1,434.30 | -1,034.00 | 376.20 | 1,352.50 | unstable | mixed |
| V17 | pending order expires after 3 bars | 333 | -1,709.20 | -3,639.00 | 0.93 | -5.13 | 0.03 | 4,156.00 | 412.10 | -275.40 | -1,845.80 | negative | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 408 | 4,722.00 | 2,792.00 | 1.19 | 11.57 | 0.05 | 2,764.00 | 2,633.50 | 1,427.00 | 661.50 | robust | helpful |
| V19 | confirmation window 3 bars | 287 | -33.70 | -1,964.00 | 1.00 | -0.12 | 0.04 | 3,561.30 | 495.00 | -575.20 | 46.60 | negative | harmful |
| V20 | no sessions of high/extreme realised volatility | 257 | 2,184.80 | 255.00 | 1.14 | 8.50 | 0.09 | 2,502.40 | 1,820.80 | 73.80 | 290.20 | robust | mixed |

## NIFTY 50 2h FINAL_H4 (baseline: 174 trades, net 3,627 pts, PF 1.231, TRAIN 3,003 / VAL 361 / OOS 263, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 146 | 1,636.50 | -1,990.00 | 1.12 | 11.21 | 0.04 | 1,761.70 | 1,482.90 | -551.60 | 705.10 | unstable | harmful |
| V02 | ADX(14) >= 20 | 162 | 4,177.30 | 550.00 | 1.31 | 25.79 | 0.11 | 1,115.20 | 2,614.40 | 248.90 | 1,313.90 | robust | harmful |
| V03 | no entries in the opening phase (before 09:45) | 169 | 3,880.60 | 254.00 | 1.25 | 22.96 | 0.14 | 2,145.10 | 3,182.30 | 391.60 | 306.70 | robust | helpful |
| V04 | entries only 09:45-13:29 (morning + midday) | 163 | 3,667.00 | 40.00 | 1.25 | 22.50 | 0.13 | 2,649.80 | 2,950.10 | 633.10 | 83.70 | robust | mixed |
| V05 | no entries in the closing phase (after 15:00) | 170 | 3,314.40 | -312.00 | 1.22 | 19.50 | 0.12 | 2,825.20 | 3,160.90 | 361.00 | -207.50 | unstable | mixed |
| V06 | no entries in the first hour (before 10:15) | 169 | 3,880.60 | 254.00 | 1.25 | 22.96 | 0.14 | 2,145.10 | 3,182.30 | 391.60 | 306.70 | robust | helpful |
| V07 | skip sessions with |gap| > 0.5% | 156 | 4,225.90 | 599.00 | 1.31 | 27.09 | 0.15 | 2,078.50 | 2,772.60 | 343.40 | 1,109.90 | robust | helpful |
| V08 | only sessions with |gap| <= 0.25% | 127 | 3,611.20 | -16.00 | 1.34 | 28.43 | 0.11 | 2,058.70 | 2,785.30 | -362.40 | 1,188.30 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 95 | 408.30 | -3,219.00 | 1.04 | 4.30 | 0.08 | 1,902.20 | -918.10 | 1,561.20 | -234.90 | unstable | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 175 | 3,996.00 | 369.00 | 1.27 | 22.83 | 0.12 | 1,178.70 | 2,253.10 | 361.10 | 1,381.70 | robust | mixed |
| V11 | MA18 slope filter over 3 bars | 158 | 3,823.50 | 197.00 | 1.27 | 24.20 | 0.14 | 2,566.60 | 3,437.60 | 360.70 | 25.20 | robust | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 151 | 4,192.60 | 566.00 | 1.35 | 27.77 | 0.12 | 1,658.50 | 1,253.70 | 623.70 | 2,315.30 | robust | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 142 | 3,130.30 | -497.00 | 1.25 | 22.05 | 0.15 | 2,809.40 | 3,717.70 | -317.00 | -270.40 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 117 | 2,468.40 | -1,158.00 | 1.25 | 21.10 | 0.15 | 2,993.60 | 3,626.90 | -16.20 | -1,142.30 | unstable | harmful |
| V15 | long only | 104 | 3,754.00 | 127.00 | 1.52 | 36.10 | 0.17 | 896.70 | 3,709.90 | -203.20 | 247.30 | unstable | mixed |
| V16 | short only | 70 | -127.10 | -3,754.00 | 0.98 | -1.82 | 0.05 | 2,226.00 | -706.90 | 564.30 | 15.50 | negative | harmful |
| V17 | pending order expires after 3 bars | 174 | 4,144.80 | 518.00 | 1.27 | 23.82 | 0.16 | 2,513.90 | 3,032.60 | 642.80 | 469.40 | robust | helpful |
| V18 | confirmation window 1 bar (instead of 2) | 228 | 5,265.70 | 1,639.00 | 1.29 | 23.09 | 0.18 | 2,689.70 | 3,564.80 | 749.20 | 951.70 | robust | mixed |
| V19 | confirmation window 3 bars | 159 | 2,109.10 | -1,518.00 | 1.14 | 13.27 | 0.13 | 2,892.50 | 2,621.70 | 723.90 | -1,236.50 | unstable | harmful |
| V20 | no sessions of high/extreme realised volatility | 154 | 1,504.40 | -2,122.00 | 1.11 | 9.77 | 0.09 | 2,340.70 | 1,442.40 | 231.80 | -169.90 | unstable | harmful |

## NIFTY 50 4h FINAL_H4 (baseline: 79 trades, net 3,989 pts, PF 1.361, TRAIN 3,870 / VAL 788 / OOS -669, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 65 | 2,369.60 | -1,620.00 | 1.24 | 36.46 | 0.14 | 1,740.40 | 2,078.10 | 390.90 | -99.30 | unstable | harmful |
| V02 | ADX(14) >= 20 | 71 | 3,590.40 | -399.00 | 1.35 | 50.57 | 0.15 | 2,710.70 | 2,943.50 | 1,138.70 | -491.80 | unstable | mixed |
| V03 | no entries in the opening phase (before 09:45) | 75 | 4,496.70 | 508.00 | 1.45 | 59.96 | 0.12 | 1,731.00 | 3,555.30 | 429.10 | 512.30 | unstable | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 75 | 4,496.70 | 508.00 | 1.45 | 59.96 | 0.12 | 1,731.00 | 3,555.30 | 429.10 | 512.30 | unstable | harmful |
| V05 | no entries in the closing phase (after 15:00) | 79 | 3,989.10 | 0.00 | 1.36 | 50.49 | 0.14 | 2,734.40 | 3,869.80 | 788.30 | -669.00 | unstable | mixed |
| V06 | no entries in the first hour (before 10:15) | 75 | 4,496.70 | 508.00 | 1.45 | 59.96 | 0.12 | 1,731.00 | 3,555.30 | 429.10 | 512.30 | unstable | harmful |
| V07 | skip sessions with |gap| > 0.5% | 76 | 3,160.70 | -828.00 | 1.28 | 41.59 | 0.07 | 2,743.90 | 2,816.70 | 1,120.50 | -776.50 | unstable | harmful |
| V08 | only sessions with |gap| <= 0.25% | 66 | 2,976.20 | -1,013.00 | 1.32 | 45.09 | 0.05 | 3,362.40 | 1,276.80 | 976.60 | 722.80 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 38 | 2,195.10 | -1,794.00 | 1.35 | 57.77 | 0.06 | 2,007.70 | 2,082.00 | 2.80 | 110.30 | unstable | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 81 | 4,066.60 | 78.00 | 1.41 | 50.20 | 0.18 | 1,337.40 | 2,351.90 | 788.30 | 926.30 | unstable | mixed |
| V11 | MA18 slope filter over 3 bars | 72 | 2,329.20 | -1,660.00 | 1.21 | 32.35 | 0.08 | 3,444.90 | 2,725.50 | -285.50 | -110.80 | unstable | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 73 | 3,261.30 | -728.00 | 1.33 | 44.68 | 0.15 | 2,804.30 | 2,452.50 | 1,488.00 | -679.20 | unstable | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 70 | 2,997.50 | -992.00 | 1.27 | 42.82 | 0.12 | 3,313.40 | 4,227.70 | 106.30 | -1,336.40 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 68 | 1,717.20 | -2,272.00 | 1.16 | 25.25 | 0.06 | 3,445.40 | 3,190.10 | -25.70 | -1,447.20 | unstable | harmful |
| V15 | long only | 51 | 2,699.70 | -1,289.00 | 1.47 | 52.94 | 0.07 | 1,545.80 | 3,396.60 | -671.80 | -25.10 | unstable | mixed |
| V16 | short only | 28 | 1,289.40 | -2,700.00 | 1.24 | 46.05 | 0.27 | 1,812.40 | 473.20 | 1,460.10 | -643.90 | unstable | harmful |
| V17 | pending order expires after 3 bars | 79 | 3,966.80 | -22.00 | 1.36 | 50.21 | 0.11 | 2,541.90 | 3,677.60 | 619.60 | -330.50 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 90 | 8,862.30 | 4,873.00 | 2.02 | 98.47 | 0.16 | 1,341.10 | 5,078.90 | 1,691.10 | 2,092.30 | unstable | helpful |
| V19 | confirmation window 3 bars | 72 | 4,233.70 | 245.00 | 1.45 | 58.80 | 0.08 | 1,590.70 | 2,821.70 | 768.50 | 643.60 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 73 | 1,671.10 | -2,318.00 | 1.17 | 22.89 | 0.10 | 2,723.50 | 648.30 | 799.30 | 223.50 | unstable | mixed |

## NIFTY BANK 15m ASIS (baseline: 1958 trades, net -5,002 pts, PF 0.937, TRAIN -4,582 / VAL -694 / OOS 274, negative)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 1433 | -5,054.10 | -52.00 | 0.92 | -3.53 | -0.05 | 13,191.50 | -5,182.10 | 382.00 | -254.00 | negative | harmful |
| V02 | ADX(14) >= 20 | 1757 | -1,938.90 | 3,063.00 | 0.97 | -1.10 | -0.03 | 12,860.00 | -2,045.50 | 69.30 | 37.20 | negative | mixed |
| V03 | no entries in the opening phase (before 09:45) | 1976 | -6,090.30 | -1,088.00 | 0.92 | -3.08 | -0.04 | 17,117.60 | -6,956.70 | -272.20 | 1,138.60 | negative | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 1448 | -10,863.70 | -5,861.00 | 0.78 | -7.50 | -0.05 | 11,540.40 | -4,521.50 | -460.80 | -5,881.40 | negative | harmful |
| V05 | no entries in the closing phase (after 15:00) | 1855 | -7,859.20 | -2,857.00 | 0.89 | -4.24 | -0.05 | 14,391.20 | -6,300.30 | 199.10 | -1,758.00 | negative | harmful |
| V06 | no entries in the first hour (before 10:15) | 1889 | -6,348.40 | -1,346.00 | 0.92 | -3.36 | -0.04 | 17,687.40 | -5,752.30 | -1,826.90 | 1,230.80 | negative | harmful |
| V07 | skip sessions with |gap| > 0.5% | 1472 | -11,957.70 | -6,955.00 | 0.79 | -8.12 | -0.06 | 12,829.30 | -6,619.10 | -327.40 | -5,011.20 | negative | harmful |
| V08 | only sessions with |gap| <= 0.25% | 963 | -13,511.30 | -8,509.00 | 0.66 | -14.03 | -0.08 | 14,925.30 | -5,889.40 | -3,592.20 | -4,029.60 | negative | harmful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 1033 | -4,683.50 | 319.00 | 0.89 | -4.53 | -0.03 | 7,921.10 | -858.30 | 932.90 | -4,758.10 | negative | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 1908 | -4,780.60 | 222.00 | 0.94 | -2.51 | -0.04 | 14,768.20 | -4,204.00 | -336.00 | -240.60 | negative | mixed |
| V11 | MA18 slope filter over 3 bars | 1771 | -8,779.60 | -3,777.00 | 0.88 | -4.96 | -0.03 | 13,626.10 | -5,085.90 | -618.30 | -3,075.30 | negative | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 1736 | -2,100.30 | 2,902.00 | 0.97 | -1.21 | -0.03 | 14,610.90 | -6,619.90 | 439.60 | 4,080.00 | negative | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 1607 | -11,056.30 | -6,054.00 | 0.83 | -6.88 | -0.05 | 17,517.00 | -7,722.30 | -2,583.30 | -750.70 | negative | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 944 | -7,132.30 | -2,130.00 | 0.82 | -7.55 | -0.06 | 11,273.20 | -3,102.90 | -2,783.60 | -1,245.80 | negative | harmful |
| V15 | long only | 1049 | -7,281.20 | -2,279.00 | 0.84 | -6.94 | -0.06 | 11,491.40 | -3,653.80 | -916.40 | -2,711.00 | negative | harmful |
| V16 | short only | 909 | 2,278.90 | 7,281.00 | 1.07 | 2.51 | -0.02 | 5,819.00 | -928.40 | 222.90 | 2,984.40 | unstable | helpful |
| V17 | pending order expires after 3 bars | 2072 | -6,285.00 | -1,283.00 | 0.93 | -3.03 | -0.04 | 15,779.50 | -6,067.30 | -91.40 | -126.30 | negative | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 2620 | -19,526.90 | -14,525.00 | 0.82 | -7.45 | -0.07 | 25,289.50 | -12,072.50 | -3,882.20 | -3,572.10 | negative | harmful |
| V19 | confirmation window 3 bars | 1764 | -7,581.70 | -2,579.00 | 0.89 | -4.30 | -0.04 | 15,557.00 | -9,012.20 | 2,047.00 | -616.60 | negative | harmful |
| V20 | no sessions of high/extreme realised volatility | 1672 | -9,067.80 | -4,065.00 | 0.86 | -5.42 | -0.04 | 12,810.30 | -6,490.30 | 206.60 | -2,784.10 | negative | harmful |

## NIFTY BANK 30m ASIS (baseline: 1190 trades, net -9,709 pts, PF 0.82, TRAIN -8,190 / VAL 425 / OOS -1,944, negative)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 884 | -5,159.50 | 4,550.00 | 0.87 | -5.84 | 0.02 | 9,402.90 | -6,170.30 | 2,217.20 | -1,206.50 | negative | mixed |
| V02 | ADX(14) >= 20 | 1094 | -5,399.90 | 4,309.00 | 0.89 | -4.94 | -0.02 | 12,607.20 | -4,863.60 | 1,024.80 | -1,561.10 | negative | helpful |
| V03 | no entries in the opening phase (before 09:45) | 1185 | -11,322.80 | -1,614.00 | 0.79 | -9.55 | -0.04 | 18,642.80 | -9,742.70 | 437.30 | -2,017.40 | negative | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 891 | -10,717.60 | -1,009.00 | 0.72 | -12.03 | -0.03 | 12,171.20 | -9,130.00 | 1,954.20 | -3,541.90 | negative | harmful |
| V05 | no entries in the closing phase (after 15:00) | 1139 | -10,101.90 | -393.00 | 0.80 | -8.87 | -0.03 | 14,240.40 | -8,074.70 | 746.40 | -2,773.60 | negative | harmful |
| V06 | no entries in the first hour (before 10:15) | 1195 | -11,244.50 | -1,536.00 | 0.79 | -9.41 | -0.04 | 17,981.80 | -8,174.70 | -1,121.30 | -1,948.60 | negative | harmful |
| V07 | skip sessions with |gap| > 0.5% | 888 | -6,939.40 | 2,770.00 | 0.82 | -7.82 | -0.04 | 11,905.30 | -5,564.70 | -327.30 | -1,047.40 | negative | mixed |
| V08 | only sessions with |gap| <= 0.25% | 583 | -1,338.10 | 8,371.00 | 0.94 | -2.29 | -0.01 | 6,367.90 | -2,304.50 | 1,456.70 | -490.20 | negative | helpful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 650 | -9,045.10 | 664.00 | 0.70 | -13.91 | -0.04 | 10,313.30 | -6,358.40 | -2,608.10 | -78.50 | negative | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 1168 | -8,193.00 | 1,516.00 | 0.84 | -7.01 | -0.03 | 15,704.50 | -6,803.50 | 536.50 | -1,926.00 | negative | helpful |
| V11 | MA18 slope filter over 3 bars | 1071 | -8,093.80 | 1,615.00 | 0.83 | -7.56 | -0.02 | 14,002.10 | -4,585.70 | 1,742.60 | -5,250.70 | negative | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 983 | -3,057.80 | 6,651.00 | 0.93 | -3.11 | -0.02 | 12,736.20 | -4,441.70 | -1,251.80 | 2,635.70 | negative | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 974 | -7,993.80 | 1,715.00 | 0.81 | -8.21 | -0.02 | 14,757.10 | -4,732.60 | 2,449.20 | -5,710.40 | negative | mixed |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 616 | -3,646.20 | 6,063.00 | 0.87 | -5.92 | -0.03 | 7,397.00 | -300.80 | 515.40 | -3,860.80 | negative | mixed |
| V15 | long only | 636 | 219.20 | 9,928.00 | 1.01 | 0.34 | -0.02 | 5,171.80 | 827.00 | 2,254.60 | -2,862.40 | unstable | mixed |
| V16 | short only | 554 | -9,928.10 | -219.00 | 0.60 | -17.92 | -0.04 | 14,114.40 | -9,016.90 | -1,829.80 | 918.60 | negative | harmful |
| V17 | pending order expires after 3 bars | 1296 | -11,063.40 | -1,354.00 | 0.81 | -8.54 | -0.03 | 15,979.50 | -7,317.80 | -80.10 | -3,665.50 | negative | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 1468 | -12,411.80 | -2,703.00 | 0.81 | -8.46 | -0.01 | 17,683.00 | -7,906.10 | 1,413.30 | -5,918.90 | negative | mixed |
| V19 | confirmation window 3 bars | 1058 | -4,827.30 | 4,882.00 | 0.89 | -4.56 | -0.01 | 12,267.30 | -3,020.10 | -1,336.30 | -470.90 | negative | mixed |
| V20 | no sessions of high/extreme realised volatility | 1027 | -8,242.70 | 1,466.00 | 0.81 | -8.03 | -0.03 | 14,832.40 | -9,359.10 | 1,063.20 | 53.20 | negative | mixed |

## NIFTY BANK 1h ASIS (baseline: 627 trades, net 4,206 pts, PF 1.133, TRAIN 618 / VAL 7,910 / OOS -4,321, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 470 | 3,719.30 | -487.00 | 1.16 | 7.91 | 0.03 | 6,223.90 | 3,199.80 | 4,369.50 | -3,850.00 | unstable | harmful |
| V02 | ADX(14) >= 20 | 579 | 1,976.10 | -2,230.00 | 1.07 | 3.41 | 0.02 | 5,856.40 | 1,201.00 | 5,365.30 | -4,590.30 | unstable | harmful |
| V03 | no entries in the opening phase (before 09:45) | 608 | 4,371.90 | 166.00 | 1.14 | 7.19 | 0.02 | 6,414.00 | 1,188.70 | 7,974.70 | -4,791.50 | unstable | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 495 | 1,544.00 | -2,662.00 | 1.06 | 3.12 | 0.01 | 5,117.00 | -743.70 | 5,915.70 | -3,628.10 | unstable | harmful |
| V05 | no entries in the closing phase (after 15:00) | 611 | 5,064.60 | 858.00 | 1.18 | 8.29 | 0.02 | 6,392.60 | 1,640.10 | 7,954.90 | -4,530.40 | unstable | mixed |
| V06 | no entries in the first hour (before 10:15) | 608 | 4,371.90 | 166.00 | 1.14 | 7.19 | 0.02 | 6,414.00 | 1,188.70 | 7,974.70 | -4,791.50 | unstable | mixed |
| V07 | skip sessions with |gap| > 0.5% | 498 | 5,309.90 | 1,104.00 | 1.23 | 10.66 | 0.01 | 6,171.30 | 3,383.90 | 6,296.50 | -4,370.50 | unstable | harmful |
| V08 | only sessions with |gap| <= 0.25% | 370 | 4,146.50 | -60.00 | 1.25 | 11.21 | 0.02 | 6,424.20 | 3,527.10 | 4,837.60 | -4,218.20 | unstable | harmful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 338 | 3,892.20 | -314.00 | 1.23 | 11.52 | 0.03 | 3,509.10 | -287.20 | 5,651.60 | -1,472.10 | unstable | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 616 | 2,554.90 | -1,651.00 | 1.08 | 4.15 | 0.01 | 5,819.30 | 639.20 | 6,113.10 | -4,197.40 | unstable | harmful |
| V11 | MA18 slope filter over 3 bars | 539 | 6,438.80 | 2,232.00 | 1.24 | 11.95 | 0.02 | 3,977.90 | 1,612.30 | 6,474.50 | -1,648.00 | unstable | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 489 | 3,081.00 | -1,125.00 | 1.12 | 6.30 | 0.00 | 3,467.40 | -1,323.40 | 5,977.10 | -1,572.80 | unstable | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 518 | -1,433.40 | -5,640.00 | 0.95 | -2.77 | -0.00 | 5,660.10 | -1,620.60 | 4,751.70 | -4,564.50 | negative | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 376 | -696.10 | -4,902.00 | 0.97 | -1.85 | 0.01 | 5,099.60 | -193.70 | 3,569.40 | -4,071.80 | negative | harmful |
| V15 | long only | 362 | 8,317.40 | 4,111.00 | 1.46 | 22.98 | 0.06 | 4,401.00 | 4,118.40 | 7,554.10 | -3,355.10 | unstable | mixed |
| V16 | short only | 265 | -4,111.00 | -8,317.00 | 0.70 | -15.51 | -0.04 | 4,240.30 | -3,500.80 | 356.00 | -966.30 | negative | harmful |
| V17 | pending order expires after 3 bars | 682 | 4,395.10 | 189.00 | 1.13 | 6.44 | 0.00 | 6,060.50 | 2,036.10 | 6,274.10 | -3,915.10 | unstable | mixed |
| V18 | confirmation window 1 bar (instead of 2) | 785 | 1,591.10 | -2,615.00 | 1.04 | 2.03 | 0.03 | 4,385.70 | -3,205.40 | 8,171.70 | -3,375.10 | unstable | harmful |
| V19 | confirmation window 3 bars | 544 | 6,067.40 | 1,861.00 | 1.22 | 11.15 | 0.03 | 4,642.90 | 771.40 | 6,908.10 | -1,612.10 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 546 | 7,265.40 | 3,059.00 | 1.29 | 13.31 | 0.02 | 3,977.90 | 1,550.70 | 7,960.90 | -2,246.20 | unstable | helpful |

## NIFTY BANK 15m FINAL_H4 (baseline: 1125 trades, net 15,190 pts, PF 1.145, TRAIN 11,058 / VAL 2,165 / OOS 1,967, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 844 | 11,600.00 | -3,590.00 | 1.14 | 13.74 | 0.00 | 5,644.80 | 8,228.30 | 819.10 | 2,552.60 | robust | harmful |
| V02 | ADX(14) >= 20 | 1002 | 17,682.50 | 2,492.00 | 1.19 | 17.65 | 0.02 | 4,902.80 | 12,410.00 | 2,778.00 | 2,494.50 | robust | helpful |
| V03 | no entries in the opening phase (before 09:45) | 1114 | 18,326.10 | 3,136.00 | 1.18 | 16.45 | 0.01 | 6,078.80 | 10,393.40 | 3,279.90 | 4,652.80 | robust | mixed |
| V04 | entries only 09:45-13:29 (morning + midday) | 833 | 9,835.10 | -5,355.00 | 1.14 | 11.81 | -0.00 | 6,060.50 | 6,701.30 | 1,846.80 | 1,286.90 | robust | harmful |
| V05 | no entries in the closing phase (after 15:00) | 1060 | 9,215.30 | -5,975.00 | 1.09 | 8.69 | -0.02 | 8,745.70 | 6,160.20 | 1,833.20 | 1,221.90 | robust | harmful |
| V06 | no entries in the first hour (before 10:15) | 1096 | 12,709.60 | -2,481.00 | 1.12 | 11.60 | 0.00 | 5,534.20 | 7,588.50 | 3,181.80 | 1,939.30 | robust | harmful |
| V07 | skip sessions with |gap| > 0.5% | 852 | 6,773.00 | -8,417.00 | 1.09 | 7.95 | 0.01 | 4,795.80 | 3,852.40 | 3,221.00 | -300.40 | unstable | harmful |
| V08 | only sessions with |gap| <= 0.25% | 557 | -1,214.30 | -16,404.00 | 0.97 | -2.18 | -0.03 | 5,578.20 | 15.10 | 127.70 | -1,357.10 | negative | harmful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 591 | 10,066.00 | -5,124.00 | 1.16 | 17.03 | 0.03 | 5,008.90 | 11,416.60 | 1,267.70 | -2,618.30 | unstable | mixed |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 1108 | 12,662.00 | -2,528.00 | 1.12 | 11.43 | 0.00 | 6,270.10 | 8,577.70 | 2,735.30 | 1,349.00 | robust | harmful |
| V11 | MA18 slope filter over 3 bars | 1006 | 9,457.50 | -5,733.00 | 1.10 | 9.40 | 0.00 | 6,750.30 | 9,490.30 | 3,537.70 | -3,570.50 | unstable | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 1057 | 11,580.00 | -3,610.00 | 1.12 | 10.96 | -0.01 | 8,539.10 | 7,583.20 | 615.30 | 3,381.40 | robust | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 922 | 3,206.30 | -11,984.00 | 1.04 | 3.48 | -0.03 | 8,089.00 | 916.30 | 1,287.50 | 1,002.50 | robust | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 548 | -1,606.50 | -16,797.00 | 0.97 | -2.93 | -0.08 | 6,303.50 | 1,406.70 | -895.50 | -2,117.60 | negative | harmful |
| V15 | long only | 618 | 6,042.80 | -9,147.00 | 1.12 | 9.78 | -0.00 | 6,064.90 | 7,793.40 | -1,679.60 | -71.00 | unstable | harmful |
| V16 | short only | 507 | 9,147.40 | -6,043.00 | 1.17 | 18.04 | 0.01 | 4,687.20 | 3,264.80 | 3,844.20 | 2,038.40 | robust | mixed |
| V17 | pending order expires after 3 bars | 1200 | 13,915.00 | -1,275.00 | 1.13 | 11.60 | -0.00 | 7,888.60 | 11,267.20 | 1,501.80 | 1,145.90 | robust | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 1613 | 6,347.50 | -8,843.00 | 1.04 | 3.94 | -0.04 | 9,247.10 | 2,800.00 | 1,057.60 | 2,489.90 | robust | harmful |
| V19 | confirmation window 3 bars | 955 | 9,771.90 | -5,418.00 | 1.10 | 10.23 | -0.01 | 6,070.30 | 3,549.90 | 4,612.00 | 1,610.00 | robust | harmful |
| V20 | no sessions of high/extreme realised volatility | 967 | 7,016.80 | -8,173.00 | 1.08 | 7.26 | 0.00 | 6,369.30 | 6,537.20 | 3,523.90 | -3,044.20 | unstable | harmful |

## NIFTY BANK 30m FINAL_H4 (baseline: 593 trades, net 6,230 pts, PF 1.074, TRAIN 6,888 / VAL -736 / OOS 77, unstable)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 456 | 6,109.50 | -121.00 | 1.09 | 13.40 | 0.03 | 6,834.20 | 4,461.00 | 1,392.40 | 256.10 | robust | mixed |
| V02 | ADX(14) >= 20 | 552 | 4,516.30 | -1,714.00 | 1.06 | 8.18 | -0.00 | 7,374.50 | 4,801.40 | -227.10 | -58.00 | unstable | harmful |
| V03 | no entries in the opening phase (before 09:45) | 591 | 5,690.70 | -540.00 | 1.07 | 9.63 | 0.01 | 7,022.20 | 6,344.40 | -96.60 | -557.10 | unstable | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 486 | 6,164.20 | -66.00 | 1.09 | 12.68 | 0.01 | 6,617.60 | 7,772.70 | 482.80 | -2,091.30 | unstable | mixed |
| V05 | no entries in the closing phase (after 15:00) | 569 | 8,452.60 | 2,222.00 | 1.10 | 14.86 | 0.02 | 7,047.10 | 8,130.20 | -937.40 | 1,259.70 | unstable | mixed |
| V06 | no entries in the first hour (before 10:15) | 586 | 4,682.30 | -1,548.00 | 1.06 | 7.99 | 0.01 | 8,191.00 | 5,474.80 | -216.30 | -576.20 | unstable | harmful |
| V07 | skip sessions with |gap| > 0.5% | 452 | 8,924.20 | 2,694.00 | 1.16 | 19.74 | 0.05 | 3,706.70 | 5,600.70 | 384.10 | 2,939.40 | robust | helpful |
| V08 | only sessions with |gap| <= 0.25% | 303 | 6,048.80 | -181.00 | 1.17 | 19.96 | 0.08 | 2,841.50 | 3,663.80 | 1,805.60 | 579.40 | robust | helpful |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 339 | -114.10 | -6,344.00 | 1.00 | -0.34 | -0.03 | 8,040.40 | 5,582.10 | -1,477.30 | -4,218.90 | negative | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 586 | 7,036.10 | 806.00 | 1.09 | 12.01 | 0.01 | 6,796.50 | 7,721.80 | -1,895.80 | 1,210.10 | unstable | mixed |
| V11 | MA18 slope filter over 3 bars | 525 | 9,831.10 | 3,601.00 | 1.14 | 18.73 | 0.02 | 5,732.50 | 8,311.30 | 1,837.50 | -317.70 | unstable | mixed |
| V12 | no entry when |close - MA18| > 2 ATR | 537 | 1,006.60 | -5,224.00 | 1.01 | 1.88 | 0.04 | 6,325.80 | 1,464.10 | -1,844.00 | 1,386.50 | unstable | harmful |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 478 | 8,232.30 | 2,002.00 | 1.12 | 17.22 | 0.03 | 6,736.50 | 7,895.70 | 711.70 | -375.10 | unstable | mixed |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 311 | 2,826.70 | -3,404.00 | 1.06 | 9.09 | -0.00 | 4,827.80 | 3,192.60 | 962.90 | -1,328.80 | unstable | harmful |
| V15 | long only | 313 | 12,560.20 | 6,330.00 | 1.36 | 40.13 | 0.07 | 4,644.60 | 12,169.70 | 2,303.60 | -1,913.20 | unstable | mixed |
| V16 | short only | 280 | -6,330.00 | -12,560.00 | 0.87 | -22.61 | -0.05 | 10,278.10 | -5,281.40 | -3,039.20 | 1,990.60 | negative | harmful |
| V17 | pending order expires after 3 bars | 630 | 4,936.80 | -1,293.00 | 1.05 | 7.84 | 0.01 | 6,484.40 | 5,097.10 | 1,395.90 | -1,556.30 | unstable | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 760 | 11,746.60 | 5,516.00 | 1.12 | 15.46 | 0.04 | 5,053.90 | 7,473.40 | 1,658.80 | 2,614.40 | robust | mixed |
| V19 | confirmation window 3 bars | 505 | 7,270.90 | 1,041.00 | 1.10 | 14.40 | -0.03 | 7,093.30 | 5,923.10 | -81.10 | 1,428.90 | unstable | mixed |
| V20 | no sessions of high/extreme realised volatility | 507 | 6,580.30 | 350.00 | 1.10 | 12.98 | 0.01 | 4,971.00 | 5,026.60 | 194.50 | 1,359.20 | robust | mixed |

## NIFTY BANK 1h FINAL_H4 (baseline: 309 trades, net 5,448 pts, PF 1.091, TRAIN 1,837 / VAL 2,334 / OOS 1,276, robust)

| id | variant | trades | net pts | d net | PF | exp pts | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | ADX(14) >= 25 (EA filter) | 230 | 7,704.40 | 2,257.00 | 1.17 | 33.50 | 0.05 | 5,077.70 | 3,789.90 | 575.90 | 3,338.70 | robust | mixed |
| V02 | ADX(14) >= 20 | 283 | 5,286.40 | -161.00 | 1.09 | 18.68 | 0.02 | 5,366.90 | 1,898.60 | 814.50 | 2,573.40 | robust | mixed |
| V03 | no entries in the opening phase (before 09:45) | 302 | 3,495.60 | -1,952.00 | 1.06 | 11.57 | 0.01 | 6,675.20 | 2,066.60 | 1,107.50 | 321.50 | robust | harmful |
| V04 | entries only 09:45-13:29 (morning + midday) | 272 | 5,595.30 | 148.00 | 1.11 | 20.57 | 0.01 | 5,549.00 | 924.10 | 3,015.70 | 1,655.60 | robust | mixed |
| V05 | no entries in the closing phase (after 15:00) | 301 | 6,969.60 | 1,522.00 | 1.12 | 23.16 | 0.03 | 6,004.40 | 2,102.10 | 3,003.30 | 1,864.10 | robust | helpful |
| V06 | no entries in the first hour (before 10:15) | 302 | 3,495.60 | -1,952.00 | 1.06 | 11.57 | 0.01 | 6,675.20 | 2,066.60 | 1,107.50 | 321.50 | robust | harmful |
| V07 | skip sessions with |gap| > 0.5% | 250 | 8,521.00 | 3,073.00 | 1.19 | 34.08 | 0.01 | 5,048.00 | 5,392.20 | 2,269.80 | 859.10 | robust | mixed |
| V08 | only sessions with |gap| <= 0.25% | 189 | 1,653.90 | -3,794.00 | 1.05 | 8.75 | -0.06 | 5,380.00 | 1,666.80 | 3,021.90 | -3,034.80 | unstable | mixed |
| V09 | ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility) | 174 | 1,129.50 | -4,318.00 | 1.03 | 6.49 | -0.02 | 5,371.50 | -914.20 | 781.10 | 1,262.50 | unstable | harmful |
| V10 | ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility) | 304 | 6,605.40 | 1,158.00 | 1.12 | 21.73 | 0.01 | 6,310.00 | 3,050.70 | 1,885.70 | 1,669.00 | robust | mixed |
| V11 | MA18 slope filter over 3 bars | 270 | 2,260.50 | -3,187.00 | 1.04 | 8.37 | -0.00 | 6,921.40 | 2,362.00 | 877.70 | -979.30 | unstable | harmful |
| V12 | no entry when |close - MA18| > 2 ATR | 276 | 8,749.30 | 3,301.00 | 1.18 | 31.70 | 0.06 | 8,532.20 | 4,276.50 | 4,031.20 | 441.60 | robust | mixed |
| V13 | trend-regime gate: no sideways sessions (63-day return within +-2%) | 259 | 230.70 | -5,217.00 | 1.00 | 0.89 | -0.03 | 5,846.20 | 974.90 | 1,028.30 | -1,772.60 | unstable | harmful |
| V14 | regime-aligned direction: longs on bull sessions, shorts on bear sessions | 197 | 1,807.00 | -3,641.00 | 1.05 | 9.17 | -0.02 | 5,080.30 | 1,810.60 | 1,469.80 | -1,473.40 | unstable | harmful |
| V15 | long only | 182 | 8,508.20 | 3,060.00 | 1.26 | 46.75 | 0.10 | 5,389.70 | 8,749.50 | 3,062.60 | -3,303.90 | unstable | mixed |
| V16 | short only | 127 | -3,060.40 | -8,508.00 | 0.89 | -24.10 | -0.11 | 11,333.70 | -6,912.40 | -728.30 | 4,580.20 | negative | harmful |
| V17 | pending order expires after 3 bars | 327 | 5,021.70 | -426.00 | 1.08 | 15.36 | 0.01 | 4,914.40 | 1,855.40 | 2,775.80 | 390.50 | robust | harmful |
| V18 | confirmation window 1 bar (instead of 2) | 396 | 2,037.10 | -3,411.00 | 1.03 | 5.14 | 0.03 | 7,638.20 | 1,324.50 | 3,312.20 | -2,599.60 | unstable | harmful |
| V19 | confirmation window 3 bars | 267 | 5,703.00 | 255.00 | 1.10 | 21.36 | 0.03 | 5,772.00 | 2,982.50 | 1,054.90 | 1,665.60 | robust | mixed |
| V20 | no sessions of high/extreme realised volatility | 272 | 3,401.80 | -2,046.00 | 1.07 | 12.51 | 0.01 | 5,482.00 | 884.90 | 2,667.70 | -150.80 | unstable | harmful |

# Higher-timeframe confirmation

Entry timeframe signals are allowed only when the last completed bar of the higher timeframe has MA18 above MA200 (buy) / below (sell). 'close' mode also needs the HTF close on the right side of its MA18. The baseline for each row is the entry timeframe without the gate.


## NIFTY 50 ASIS

| id | entry | HTF | mode | trades | base trades | net pts | base net | PF | base PF | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | 5m | 15m | ma | 2728 | 3686 | -13,938.30 | -17,493.30 | 0.74 | 0.76 | -0.14 | 15,585.20 | -3,766.30 | -4,301.60 | -5,870.40 | negative | harmful |
| M01c | 5m | 15m | close | 2440 | 3686 | -11,908.70 | -17,493.30 | 0.75 | 0.76 | -0.15 | 13,340.80 | -4,480.60 | -3,691.20 | -3,736.90 | negative | mixed |
| M02 | 5m | 1h | ma | 2025 | 3686 | -12,717.10 | -17,493.30 | 0.69 | 0.76 | -0.15 | 14,151.70 | -3,320.00 | -4,452.80 | -4,944.30 | negative | harmful |
| M02c | 5m | 1h | close | 1980 | 3686 | -12,357.40 | -17,493.30 | 0.70 | 0.76 | -0.16 | 13,873.30 | -3,628.50 | -4,246.90 | -4,482.00 | negative | harmful |
| M03 | 15m | 1h | ma | 899 | 1330 | -300.00 | 1,642.60 | 0.99 | 1.05 | -0.01 | 2,473.50 | 601.20 | -819.90 | -81.30 | negative | harmful |
| M03c | 15m | 1h | close | 788 | 1330 | -667.30 | 1,642.60 | 0.97 | 1.05 | -0.03 | 2,336.60 | 821.90 | -354.90 | -1,134.30 | negative | harmful |
| M04 | 15m | 4h | ma | 643 | 1330 | 847.20 | 1,642.60 | 1.05 | 1.05 | 0.00 | 1,806.10 | 703.50 | -590.80 | 734.50 | unstable | mixed |
| M04c | 15m | 4h | close | 621 | 1330 | 263.00 | 1,642.60 | 1.02 | 1.05 | -0.01 | 1,784.80 | 166.30 | -509.20 | 605.90 | unstable | harmful |
| M05 | 15m | D1 | ma | 590 | 1330 | -182.50 | 1,642.60 | 0.99 | 1.05 | -0.02 | 1,692.90 | 962.90 | -1,302.90 | 157.50 | negative | harmful |
| M05c | 15m | D1 | close | 490 | 1330 | -273.10 | 1,642.60 | 0.98 | 1.05 | -0.02 | 2,281.10 | 981.60 | -1,599.30 | 344.50 | negative | harmful |
| M06 | 1h | 4h | ma | 266 | 418 | 1,955.90 | 3,332.10 | 1.22 | 1.23 | 0.07 | 874.90 | 1,701.90 | -267.90 | 521.90 | unstable | mixed |
| M06c | 1h | 4h | close | 239 | 418 | 1,865.40 | 3,332.10 | 1.25 | 1.23 | 0.05 | 813.90 | 1,483.50 | -304.80 | 686.80 | unstable | mixed |
| M07 | 1h | D1 | ma | 222 | 418 | 2,308.30 | 3,332.10 | 1.33 | 1.23 | 0.11 | 981.90 | 2,485.60 | -482.40 | 305.00 | unstable | mixed |
| M07c | 1h | D1 | close | 206 | 418 | 1,949.40 | 3,332.10 | 1.28 | 1.23 | 0.11 | 1,277.10 | 2,747.90 | -748.00 | -50.40 | unstable | mixed |
| M08 | 30m | D1 | ma | 342 | 739 | 2,564.20 | 2,628.00 | 1.25 | 1.11 | 0.07 | 1,180.50 | 2,623.50 | -133.50 | 74.10 | unstable | mixed |
| M08c | 30m | D1 | close | 321 | 739 | 2,468.50 | 2,628.00 | 1.26 | 1.11 | 0.08 | 1,265.50 | 2,871.60 | -428.50 | 25.50 | unstable | mixed |
| M09 | 30m | 1h | ma | 626 | 739 | 2,009.40 | 2,628.00 | 1.10 | 1.11 | 0.02 | 2,124.40 | 2,138.50 | -252.00 | 122.90 | unstable | harmful |
| M09c | 30m | 1h | close | 591 | 739 | 2,079.00 | 2,628.00 | 1.11 | 1.11 | 0.04 | 2,139.40 | 1,669.50 | 522.00 | -112.40 | unstable | mixed |

## NIFTY 50 FINAL_H4

| id | entry | HTF | mode | trades | base trades | net pts | base net | PF | base PF | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | 5m | 15m | ma | 2716 | 3669 | -11,026.80 | -13,349.80 | 0.82 | 0.84 | -0.11 | 13,314.70 | -2,632.70 | -3,661.00 | -4,733.10 | negative | harmful |
| M01c | 5m | 15m | close | 2424 | 3669 | -8,999.50 | -13,349.80 | 0.84 | 0.84 | -0.12 | 11,538.70 | -2,949.00 | -3,410.70 | -2,639.90 | negative | harmful |
| M02 | 5m | 1h | ma | 2043 | 3669 | -10,743.80 | -13,349.80 | 0.77 | 0.84 | -0.12 | 12,245.10 | -3,124.60 | -3,591.60 | -4,027.60 | negative | harmful |
| M02c | 5m | 1h | close | 2001 | 3669 | -10,907.00 | -13,349.80 | 0.76 | 0.84 | -0.13 | 12,533.90 | -3,316.90 | -3,353.30 | -4,236.80 | negative | harmful |
| M03 | 15m | 1h | ma | 789 | 1158 | 1,760.70 | 4,285.10 | 1.06 | 1.10 | 0.01 | 2,034.90 | 721.80 | -284.30 | 1,323.10 | unstable | harmful |
| M03c | 15m | 1h | close | 689 | 1158 | 796.30 | 4,285.10 | 1.03 | 1.10 | -0.01 | 1,872.20 | 509.50 | 292.50 | -5.70 | unstable | harmful |
| M04 | 15m | 4h | ma | 572 | 1158 | 2,998.40 | 4,285.10 | 1.15 | 1.10 | -0.02 | 1,945.70 | 820.80 | 708.90 | 1,468.70 | robust | mixed |
| M04c | 15m | 4h | close | 558 | 1158 | 2,014.40 | 4,285.10 | 1.10 | 1.10 | -0.04 | 2,150.10 | 353.50 | 617.20 | 1,043.70 | robust | mixed |
| M05 | 15m | D1 | ma | 525 | 1158 | 2,424.80 | 4,285.10 | 1.14 | 1.10 | 0.01 | 1,589.80 | 1,133.60 | 402.10 | 889.20 | robust | harmful |
| M05c | 15m | D1 | close | 442 | 1158 | 930.40 | 4,285.10 | 1.06 | 1.10 | 0.00 | 2,216.40 | 897.40 | -1,362.60 | 1,395.60 | unstable | mixed |
| M06 | 1h | 4h | ma | 203 | 315 | 1,323.00 | 1,930.20 | 1.10 | 1.09 | 0.03 | 1,618.80 | 340.30 | -746.00 | 1,728.70 | unstable | harmful |
| M06c | 1h | 4h | close | 181 | 315 | 1,253.40 | 1,930.20 | 1.11 | 1.09 | 0.03 | 1,860.10 | 693.00 | -651.00 | 1,211.50 | unstable | mixed |
| M07 | 1h | D1 | ma | 165 | 315 | 1,405.60 | 1,930.20 | 1.14 | 1.09 | 0.07 | 2,283.80 | 1,329.30 | -1,454.10 | 1,530.50 | unstable | mixed |
| M07c | 1h | D1 | close | 154 | 315 | 762.60 | 1,930.20 | 1.08 | 1.09 | 0.05 | 2,547.20 | 1,525.80 | -1,827.40 | 1,064.10 | unstable | mixed |
| M08 | 30m | D1 | ma | 297 | 599 | 3,500.50 | 5,118.00 | 1.28 | 1.17 | 0.04 | 1,650.20 | 2,569.00 | -371.50 | 1,303.00 | unstable | mixed |
| M08c | 30m | D1 | close | 285 | 599 | 2,502.90 | 5,118.00 | 1.21 | 1.17 | 0.03 | 1,912.80 | 2,598.50 | -1,290.60 | 1,195.00 | unstable | mixed |
| M09 | 30m | 1h | ma | 519 | 599 | 2,570.00 | 5,118.00 | 1.10 | 1.17 | 0.01 | 2,315.40 | 1,453.50 | -395.70 | 1,512.10 | unstable | harmful |
| M09c | 30m | 1h | close | 485 | 599 | 1,825.00 | 5,118.00 | 1.07 | 1.17 | 0.02 | 2,428.20 | 644.40 | 180.40 | 1,000.30 | robust | harmful |

## NIFTY BANK ASIS

| id | entry | HTF | mode | trades | base trades | net pts | base net | PF | base PF | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | 5m | 15m | ma | 3741 | 5183 | -58,348.90 | -78,272.70 | 0.58 | 0.59 | -0.14 | 59,352.40 | -28,211.50 | -14,822.10 | -15,315.30 | negative | harmful |
| M01c | 5m | 15m | close | 3323 | 5183 | -51,919.80 | -78,272.70 | 0.58 | 0.59 | -0.14 | 53,340.40 | -24,052.00 | -12,766.40 | -15,101.40 | negative | harmful |
| M02 | 5m | 1h | ma | 2748 | 5183 | -46,283.10 | -78,272.70 | 0.57 | 0.59 | -0.15 | 46,283.10 | -22,353.00 | -10,834.70 | -13,095.40 | negative | harmful |
| M02c | 5m | 1h | close | 2662 | 5183 | -44,573.00 | -78,272.70 | 0.57 | 0.59 | -0.15 | 44,585.90 | -21,124.10 | -10,430.70 | -13,018.20 | negative | harmful |
| M03 | 15m | 1h | ma | 1280 | 1958 | -6,698.60 | -5,002.30 | 0.88 | 0.94 | -0.04 | 10,764.20 | -5,203.50 | -509.10 | -985.90 | negative | harmful |
| M03c | 15m | 1h | close | 1143 | 1958 | -6,237.50 | -5,002.30 | 0.87 | 0.94 | -0.04 | 10,061.30 | -5,491.10 | 894.30 | -1,640.80 | negative | harmful |
| M04 | 15m | 4h | ma | 971 | 1958 | -6,489.20 | -5,002.30 | 0.84 | 0.94 | -0.05 | 9,351.70 | -3,212.60 | -2,575.60 | -701.10 | negative | harmful |
| M04c | 15m | 4h | close | 937 | 1958 | -5,841.60 | -5,002.30 | 0.85 | 0.94 | -0.04 | 9,143.80 | -3,014.60 | -2,362.60 | -464.40 | negative | harmful |
| M05 | 15m | D1 | ma | 870 | 1958 | -10,885.30 | -5,002.30 | 0.72 | 0.94 | -0.09 | 11,808.40 | -3,856.70 | -3,867.70 | -3,160.90 | negative | harmful |
| M05c | 15m | D1 | close | 721 | 1958 | -9,694.70 | -5,002.30 | 0.69 | 0.94 | -0.08 | 10,791.30 | -3,023.40 | -3,616.10 | -3,055.20 | negative | harmful |
| M06 | 1h | 4h | ma | 380 | 627 | 3,040.50 | 4,206.40 | 1.15 | 1.13 | 0.01 | 5,390.90 | -355.40 | 7,707.90 | -4,311.90 | unstable | harmful |
| M06c | 1h | 4h | close | 349 | 627 | 211.70 | 4,206.40 | 1.01 | 1.13 | 0.01 | 5,527.60 | -167.80 | 4,859.90 | -4,480.50 | unstable | harmful |
| M07 | 1h | D1 | ma | 318 | 627 | -1,201.40 | 4,206.40 | 0.93 | 1.13 | 0.01 | 6,504.80 | 729.40 | 3,528.10 | -5,458.90 | negative | harmful |
| M07c | 1h | D1 | close | 299 | 627 | -588.70 | 4,206.40 | 0.96 | 1.13 | 0.01 | 4,963.30 | 791.00 | 2,607.00 | -3,986.70 | negative | harmful |
| M08 | 30m | D1 | ma | 540 | 1190 | -7,976.00 | -9,709.00 | 0.69 | 0.82 | -0.06 | 7,976.00 | -4,275.70 | -1,640.20 | -2,060.20 | negative | harmful |
| M08c | 30m | D1 | close | 502 | 1190 | -5,796.30 | -9,709.00 | 0.75 | 0.82 | -0.04 | 5,796.30 | -2,712.60 | -1,170.10 | -1,913.60 | negative | harmful |
| M09 | 30m | 1h | ma | 933 | 1190 | -4,538.60 | -9,709.00 | 0.89 | 0.82 | -0.03 | 9,763.60 | -4,419.40 | 1,280.10 | -1,399.40 | negative | helpful |
| M09c | 30m | 1h | close | 880 | 1190 | -4,066.10 | -9,709.00 | 0.90 | 0.82 | -0.02 | 7,931.00 | -3,373.30 | 1,982.60 | -2,675.50 | negative | mixed |

## NIFTY BANK FINAL_H4

| id | entry | HTF | mode | trades | base trades | net pts | base net | PF | base PF | exp R | max DD | TRAIN | VAL | OOS | verdict | vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | 5m | 15m | ma | 2649 | 3664 | -27,791.70 | -34,786.20 | 0.83 | 0.84 | -0.09 | 31,125.40 | -13,671.00 | -6,361.70 | -7,759.10 | negative | harmful |
| M01c | 5m | 15m | close | 2339 | 3664 | -17,137.30 | -34,786.20 | 0.88 | 0.84 | -0.08 | 24,686.70 | -10,074.50 | -3,858.00 | -3,204.80 | negative | mixed |
| M02 | 5m | 1h | ma | 1974 | 3664 | -26,945.60 | -34,786.20 | 0.78 | 0.84 | -0.12 | 27,696.00 | -12,829.80 | -5,687.30 | -8,428.40 | negative | harmful |
| M02c | 5m | 1h | close | 1928 | 3664 | -25,465.20 | -34,786.20 | 0.78 | 0.84 | -0.11 | 26,610.50 | -11,914.30 | -4,663.20 | -8,887.80 | negative | harmful |
| M03 | 15m | 1h | ma | 752 | 1125 | 3,901.00 | 15,190.20 | 1.05 | 1.15 | -0.03 | 6,919.70 | 4,188.50 | 379.00 | -666.50 | unstable | harmful |
| M03c | 15m | 1h | close | 655 | 1125 | 4,814.30 | 15,190.20 | 1.07 | 1.15 | -0.04 | 4,358.70 | 3,767.50 | 2,062.40 | -1,015.60 | unstable | harmful |
| M04 | 15m | 4h | ma | 572 | 1125 | 651.50 | 15,190.20 | 1.01 | 1.15 | -0.04 | 6,962.00 | 3,357.90 | -2,014.10 | -692.20 | unstable | harmful |
| M04c | 15m | 4h | close | 555 | 1125 | 1,581.90 | 15,190.20 | 1.03 | 1.15 | -0.02 | 6,620.00 | 4,479.60 | -1,967.10 | -930.60 | unstable | harmful |
| M05 | 15m | D1 | ma | 505 | 1125 | -1,132.40 | 15,190.20 | 0.97 | 1.15 | -0.04 | 7,655.80 | 4,762.30 | -2,946.20 | -2,948.50 | negative | harmful |
| M05c | 15m | D1 | close | 396 | 1125 | 2,506.70 | 15,190.20 | 1.07 | 1.15 | 0.02 | 5,751.10 | 7,178.90 | -1,835.50 | -2,836.70 | unstable | harmful |
| M06 | 1h | 4h | ma | 203 | 309 | 3,380.10 | 5,447.80 | 1.09 | 1.09 | 0.00 | 5,064.60 | 1,266.50 | 2,689.10 | -575.50 | unstable | mixed |
| M06c | 1h | 4h | close | 184 | 309 | 4.00 | 5,447.80 | 1.00 | 1.09 | -0.04 | 7,068.60 | 1,757.80 | -785.30 | -968.40 | unstable | harmful |
| M07 | 1h | D1 | ma | 162 | 309 | 2,704.10 | 5,447.80 | 1.09 | 1.09 | 0.03 | 4,850.90 | 3,890.20 | 1,112.50 | -2,298.60 | unstable | harmful |
| M07c | 1h | D1 | close | 151 | 309 | 4,272.70 | 5,447.80 | 1.17 | 1.09 | 0.02 | 2,704.10 | 3,768.00 | 249.80 | 254.90 | robust | harmful |
| M08 | 30m | D1 | ma | 267 | 593 | 183.90 | 6,230.20 | 1.00 | 1.07 | -0.01 | 6,379.00 | 4,796.20 | -3,233.40 | -1,379.00 | unstable | harmful |
| M08c | 30m | D1 | close | 243 | 593 | 2,135.30 | 6,230.20 | 1.07 | 1.07 | 0.03 | 5,249.70 | 5,898.80 | -1,674.20 | -2,089.20 | unstable | harmful |
| M09 | 30m | 1h | ma | 477 | 593 | 4,991.70 | 6,230.20 | 1.07 | 1.07 | 0.04 | 6,109.80 | 4,709.80 | 3,003.80 | -2,722.00 | unstable | harmful |
| M09c | 30m | 1h | close | 434 | 593 | 7,735.30 | 6,230.20 | 1.12 | 1.07 | 0.08 | 6,720.40 | 6,965.30 | 4,227.80 | -3,457.80 | unstable | mixed |