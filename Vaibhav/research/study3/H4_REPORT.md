# Study 3: H4 only, from the E19 exit stack to a final configuration

Same engine, data (Sep 2020 - Sep 2026, XM costs, 0.01 lot) and splits as studies 1 and 2 (DEV Sep 2020 - Aug 2023, VAL Sep 2023 - Dec 2024, OOS Jan 2025 - Sep 2026). ATR units: the break-even trigger and the trailing start / distance / step are multiples of ATR(22) measured on the last completed bar when the trade opened.

## 1. Summary

The E19 result stands and improves slightly with a cleaner definition. What made E19 work was not the 2-ATR trailing start written in its name: the exit lab left the protection-start input at 500 units, which in ATR mode is 5 ATR, so the trailing stop only began after 5 ATR of profit. Read that way, E19 is 'break-even at 1 ATR, then a 1-ATR trail that starts at 5 ATR', and the grid confirms that the late start is the ingredient: with the trail starting at 2 ATR the same stack earns $1,424, with it starting at 5 ATR $2,504. The selected configuration (break-even 2 ATR, trailing start 5 ATR, distance 0.5 ATR, step 0.1 ATR, MA18 exit, swing stop, entry buffer 0) earns +$2,530 per 0.01 lot over Sep 2020 - Sep 2026 (PF 1.74, max drawdown $304, 306 trades) and is positive in DEV, VAL and OOS, in every train / validate / test window of the three walk-forward folds, under stress costs (+$2,340) and under the worst intrabar ordering (+$2,380). It is also on a plateau: any trailing distance from 0.5 to 2 ATR is within 10% of it, break-even 1 to 2 ATR and trailing start 5 to 6 ATR are all positive in every split, and 43 of the 150 grid settings pass the three-split test. No entry filter, stop or MA period adds anything the declared rule accepts, apart from removing the 10-point entry buffer (+$41). The caveat has not changed: $2,178 of the $2,530 comes from 2025-26, 2020-21 are flat, and on the hourly path from 2003 the configuration earns $2,762 with 11 of 24 years positive and 2003-2020 at zero. It is the best version of this EA on H4 and a bull-regime strategy. Funding: the median stop is $30 per 0.01 lot, so the EA's own 1% rule needs about $3,000; on $200 the Monte Carlo ruin probability is 20%.

## 2. Stage 0: what E19 actually was

Three runs to establish what is being optimised. The untouched EA on H4: +$1,181, PF 1.69, with 317 of 470 exits on the break-even stop. E19 exactly as it ran in study 1: +$2,504, PF 1.85, max drawdown $284, DEV +$9 / VAL +$344 / OOS +$2,152. E19 with the trailing start really at 2 ATR (protection start immediate): +$1,424, PF 1.35, drawdown $429. The 5-ATR gate that study 1 applied by accident is what turned the stack from mediocre to good, because on H4 a 1-ATR trail that starts early keeps closing trades that the MA18 exit and the 2-ATR structure would have carried further.

| configuration | trades | net $ | PF | maxDD $ | win % | exp R | DEV net / R | VAL net / R | OOS net / R | giveback avg $ | P->L >$2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Untouched EA (E01) | 470 | 1181.17 | 1.69 | 328.96 | 51.50 | 0.068 | -280.25 / -0.037 | 271.75 / 0.115 | 1189.67 / 0.178 | 20.36 | 158 |
| E19 as tested (trail starts at 5 ATR because ProtectionStart = 500 units) | 355 | 2504.48 | 1.85 | 284.23 | 46.20 | 0.134 | 9.43 / 0.050 | 343.53 / 0.194 | 2151.53 / 0.231 | 28.56 | 157 |
| E19 as intended (trail starts at 2 ATR) | 433 | 1424.46 | 1.35 | 429.46 | 51.30 | 0.066 | -1.39 / 0.024 | 206.78 / 0.095 | 1219.07 / 0.111 | 24.74 | 168 |

## 3. Stage 1: the exit parameter grid

150 exit settings, each judged on the same three splits. The late trailing start dominates every other parameter: the 5-ATR row is the best row in every heat table and the 6-ATR row is second; below 3 ATR every distance loses money in the development window. Trailing distance is a plateau (0.5 to 2 ATR within $500 of each other at a 5-ATR start), and the break-even trigger matters little between 1 and 2 ATR while switching it off costs about $400. The rule declared before running (highest weakest-split expectancy among settings positive in all three splits with at least 40 development trades) selects break-even 2 ATR, trailing start 5 ATR, distance 0.5 ATR: +$2,489, PF 1.72, DEV +$93 / VAL +$226 / OOS +$2,169. The highest six-year net in the grid is the neighbouring cell break-even 2 ATR, start 5 ATR, distance 1 ATR (+$2,709, PF 1.76), also positive in all splits; the difference between the two is inside the plateau and either is defensible. I kept the rule's pick and exposed the distance as an input.

150 settings (break-even 0/0.5/1/1.5/2 ATR x trailing start 1-6 ATR x distance 0.5-2 ATR, step 0.1 ATR): 43 positive in all three splits; share positive DEV 0.287, VAL 1.0, OOS 1.0. Chosen (highest weakest-split expectancy among settings positive in all splits with >= 40 DEV trades): {'thr_mode': 1, 'protection': 4, 'be_enable': True, 'be_trigger_pts': 200, 'prot_start_mode': 0, 'trail_start_pts': 500, 'trail_dist_pts': 50, 'trail_step_pts': 10}.

Top settings positive in all three splits (nb = one-step neighbours also positive in all splits):

| break-even | trail start | trail distance | trades | net $ | PF | maxDD $ | DEV net / R | VAL net / R | OOS net / R | weakest exp R | nb |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BE 2.00 ATR | 5.00 ATR | 0.50 ATR | 309 | 2488.53 | 1.72 | 304.86 | 92.63 / 0.061 | 226.44 / 0.178 | 2169.46 / 0.332 | 0.061 | 2/4 |
| BE 2.00 ATR | 5.00 ATR | 0.75 ATR | 309 | 2621.87 | 1.72 | 376.83 | 79.01 / 0.059 | 233.68 / 0.177 | 2309.19 / 0.341 | 0.059 | 3/5 |
| BE 1.00 ATR | 5.00 ATR | 0.75 ATR | 357 | 2461.58 | 1.86 | 284.23 | 27.56 / 0.057 | 359.69 / 0.231 | 2074.32 / 0.212 | 0.057 | 4/6 |
| BE 1.00 ATR | 5.00 ATR | 0.50 ATR | 358 | 2173.17 | 1.73 | 406.03 | 38.74 / 0.057 | 348.53 / 0.228 | 1785.9 / 0.192 | 0.057 | 3/5 |
| BE 1.00 ATR | 6.00 ATR | 0.50 ATR | 345 | 2515.04 | 1.91 | 284.23 | 43.89 / 0.055 | 425.97 / 0.275 | 2045.18 / 0.254 | 0.055 | 2/4 |
| BE off | 5.00 ATR | 0.50 ATR | 301 | 2034.05 | 1.51 | 373.23 | 4.92 / 0.054 | 212.91 / 0.130 | 1816.22 / 0.327 | 0.054 | 0/4 |
| BE 1.00 ATR | 5.00 ATR | 1.00 ATR | 355 | 2504.48 | 1.85 | 284.23 | 9.43 / 0.050 | 343.53 / 0.194 | 2151.53 / 0.231 | 0.050 | 4/6 |
| BE 1.50 ATR | 5.00 ATR | 0.50 ATR | 326 | 2549.12 | 1.82 | 308.96 | 59.28 / 0.050 | 321.79 / 0.222 | 2168.06 / 0.272 | 0.050 | 3/5 |
| BE 1.50 ATR | 5.00 ATR | 0.75 ATR | 326 | 2602.80 | 1.80 | 454.36 | 48.41 / 0.048 | 372.23 / 0.244 | 2182.16 / 0.263 | 0.048 | 4/6 |
| BE 2.00 ATR | 5.00 ATR | 1.00 ATR | 308 | 2708.85 | 1.76 | 304.86 | 43.36 / 0.047 | 210.31 / 0.136 | 2455.18 / 0.374 | 0.047 | 3/5 |
| BE 1.00 ATR | 6.00 ATR | 0.75 ATR | 348 | 2266.44 | 1.77 | 356.19 | 18.25 / 0.046 | 397.26 / 0.262 | 1850.93 / 0.232 | 0.046 | 3/5 |
| BE 1.00 ATR | 5.00 ATR | 2.00 ATR | 340 | 2290.81 | 1.81 | 345.38 | 45.21 / 0.045 | 316.66 / 0.218 | 1928.94 / 0.248 | 0.045 | 2/5 |
| BE 1.00 ATR | 5.00 ATR | 1.50 ATR | 348 | 2330.72 | 1.82 | 379.25 | 33.28 / 0.044 | 332.79 / 0.194 | 1964.65 / 0.242 | 0.044 | 3/6 |
| BE 1.00 ATR | 6.00 ATR | 1.00 ATR | 346 | 1975.96 | 1.64 | 381.04 | 11.43 / 0.041 | 414.11 / 0.254 | 1550.42 / 0.224 | 0.041 | 2/5 |
| BE 1.50 ATR | 5.00 ATR | 1.00 ATR | 324 | 2670.16 | 1.84 | 308.10 | 28.8 / 0.040 | 336.77 / 0.198 | 2304.59 / 0.285 | 0.040 | 4/6 |

Highest net over the six years, regardless of split consistency:

| break-even | trail start | trail distance | trades | net $ | PF | maxDD $ | DEV net / R | VAL net / R | OOS net / R | positive in all splits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BE 2.00 ATR | 5.00 ATR | 1.00 ATR | 308 | 2708.85 | 1.76 | 304.86 | 43.36 / 0.047 | 210.31 / 0.136 | 2455.18 / 0.374 | yes |
| BE 1.50 ATR | 5.00 ATR | 1.00 ATR | 324 | 2670.16 | 1.84 | 308.10 | 28.8 / 0.040 | 336.77 / 0.198 | 2304.59 / 0.285 | yes |
| BE 2.00 ATR | 5.00 ATR | 0.75 ATR | 309 | 2621.87 | 1.72 | 376.83 | 79.01 / 0.059 | 233.68 / 0.177 | 2309.19 / 0.341 | yes |
| BE 1.50 ATR | 5.00 ATR | 0.75 ATR | 326 | 2602.80 | 1.80 | 454.36 | 48.41 / 0.048 | 372.23 / 0.244 | 2182.16 / 0.263 | yes |
| BE 2.00 ATR | 6.00 ATR | 0.50 ATR | 298 | 2580.54 | 1.75 | 412.93 | -21.6 / 0.029 | 391.35 / 0.274 | 2210.8 / 0.365 | no |

Net $ heat table, break-even off (rows = trailing start, columns = trailing distance):

| start \ distance | 0.50 ATR | 0.75 ATR | 1.00 ATR | 1.50 ATR | 2.00 ATR |
|---|---:|---:|---:|---:|---:|
| 1.00 ATR | 949 | 1245 | 1310 | 1845 | 2194 |
| 2.00 ATR | 1816 | 1803 | 1411 | 1903 | 2228 |
| 3.00 ATR | 2190 | 1736 | 1527 | 1882 | 2166 |
| 4.00 ATR | 1532 | 1643 | 2120 | 2154 | 2206 |
| 5.00 ATR | 2034 | 2179 | 2393 | 2286 | 2411 |
| 6.00 ATR | 1751 | 1673 | 1458 | 1450 | 1904 |

Net $ heat table, break-even 0.50 ATR (rows = trailing start, columns = trailing distance):

| start \ distance | 0.50 ATR | 0.75 ATR | 1.00 ATR | 1.50 ATR | 2.00 ATR |
|---|---:|---:|---:|---:|---:|
| 1.00 ATR | 1450 | 1723 | 1525 | 1988 | 2014 |
| 2.00 ATR | 1642 | 1607 | 1361 | 1993 | 2014 |
| 3.00 ATR | 2288 | 2175 | 1777 | 2062 | 1997 |
| 4.00 ATR | 2123 | 2326 | 1853 | 1939 | 1797 |
| 5.00 ATR | 1960 | 2280 | 2228 | 1995 | 1907 |
| 6.00 ATR | 2081 | 1872 | 2020 | 1963 | 1856 |

Net $ heat table, break-even 1.00 ATR (rows = trailing start, columns = trailing distance):

| start \ distance | 0.50 ATR | 0.75 ATR | 1.00 ATR | 1.50 ATR | 2.00 ATR |
|---|---:|---:|---:|---:|---:|
| 1.00 ATR | 949 | 1245 | 1311 | 1511 | 2106 |
| 2.00 ATR | 1659 | 1661 | 1424 | 1615 | 2106 |
| 3.00 ATR | 2309 | 2056 | 1917 | 1881 | 2100 |
| 4.00 ATR | 2029 | 2239 | 2247 | 2232 | 2104 |
| 5.00 ATR | 2173 | 2462 | 2504 | 2331 | 2291 |
| 6.00 ATR | 2515 | 2266 | 1976 | 1905 | 1910 |

Net $ heat table, break-even 1.50 ATR (rows = trailing start, columns = trailing distance):

| start \ distance | 0.50 ATR | 0.75 ATR | 1.00 ATR | 1.50 ATR | 2.00 ATR |
|---|---:|---:|---:|---:|---:|
| 1.00 ATR | 949 | 1245 | 1310 | 1846 | 2231 |
| 2.00 ATR | 1971 | 2056 | 1558 | 1878 | 2195 |
| 3.00 ATR | 2441 | 2187 | 1823 | 1928 | 2176 |
| 4.00 ATR | 2156 | 2101 | 2296 | 2300 | 2210 |
| 5.00 ATR | 2549 | 2603 | 2670 | 2577 | 2452 |
| 6.00 ATR | 2518 | 2458 | 1893 | 1937 | 1893 |

Net $ heat table, break-even 2.00 ATR (rows = trailing start, columns = trailing distance):

| start \ distance | 0.50 ATR | 0.75 ATR | 1.00 ATR | 1.50 ATR | 2.00 ATR |
|---|---:|---:|---:|---:|---:|
| 1.00 ATR | 949 | 1245 | 1310 | 1845 | 2192 |
| 2.00 ATR | 1816 | 1803 | 1411 | 1903 | 2228 |
| 3.00 ATR | 2255 | 1946 | 1602 | 1983 | 2218 |
| 4.00 ATR | 2009 | 1928 | 2207 | 2254 | 2308 |
| 5.00 ATR | 2489 | 2622 | 2709 | 2471 | 2503 |
| 6.00 ATR | 2581 | 2512 | 1925 | 1802 | 1846 |

## 4. Stage 2: entry filters on the chosen exit

Twenty-six EA filters and two information-only splits on top of the chosen exit. Only removing the 10-point entry buffer is helpful by the rule (+$2,530 vs +$2,489, better in all three splits). Every ADX variant, every session window, the volatility filters, the spread cap and the slope and distance filters reduce the six-year result, mostly by cutting trades from the 2025-26 window; the 3-bar confirmation and the volume filter are neutral or harmful. Two splits that the EA cannot apply are worth knowing: longs only (+$2,131 on 181 trades, PF 2.08, drawdown $272, positive in all splits) and no Friday entries (+$2,278, PF 1.88, drawdown $244). Both reflect the 2025-26 bull market and the weekend gap, and neither is adopted.

Base (chosen exit, no filter): 309 trades, net 2488.53, PF 1.717, maxDD 304.86, exp R DEV/VAL/OOS 0.061 / 0.178 / 0.332.

| filter | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | DEV net | VAL net | OOS net | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F01 volume filter OFF | 386 | 2594.63 | 1.59 | 469.20 | 0.147 | 0.046 | 0.185 | 0.284 | -13.33 | 266.47 | 2341.49 | Harmful |
| F02 MA200 trend filter OFF | 531 | 2187.48 | 1.34 | 594.47 | 0.074 | -0.023 | 0.112 | 0.216 | -175.97 | 165.17 | 2198.28 | Harmful |
| F03 1-bar confirmation | 399 | 2365.65 | 1.57 | 397.02 | 0.113 | 0.013 | 0.093 | 0.298 | 85.29 | 201.41 | 2078.95 | Harmful |
| F04 3-bar confirmation | 264 | 2258.38 | 1.74 | 276.41 | 0.194 | 0.034 | 0.238 | 0.425 | 41.68 | 203.50 | 2013.20 | Neutral |
| F05 ADX>=25 | 234 | 1667.88 | 1.54 | 265.69 | 0.147 | 0.002 | 0.280 | 0.257 | -125.29 | 323.31 | 1469.85 | Harmful |
| F06 ADX>=20 | 274 | 1708.73 | 1.48 | 337.34 | 0.165 | 0.089 | 0.213 | 0.237 | 150.46 | 197.81 | 1360.46 | Neutral |
| F07 ADX>=30 | 199 | 1089.81 | 1.34 | 392.93 | 0.070 | -0.092 | 0.201 | 0.173 | -199.07 | 181.09 | 1107.79 | Harmful |
| F08 ADX>=25 rising(3) | 188 | 1452.29 | 1.59 | 332.15 | 0.169 | 0.003 | 0.375 | 0.246 | -72.47 | 350.49 | 1174.27 | Harmful |
| F09 ADX>=25 consecutive rise(3) | 161 | 730.49 | 1.33 | 386.06 | 0.114 | -0.095 | 0.384 | 0.203 | -293.95 | 282.83 | 741.61 | Harmful |
| F10 session London 8-17 | 274 | 1593.48 | 1.45 | 373.65 | 0.168 | 0.036 | 0.194 | 0.368 | 25.43 | 73.30 | 1494.75 | Neutral |
| F11 session New York 13-22 | 275 | 1656.66 | 1.46 | 556.23 | 0.114 | 0.024 | 0.147 | 0.232 | 3.25 | 215.71 | 1437.69 | Harmful |
| F12 session London+NY 8-22 | 308 | 1955.05 | 1.51 | 412.10 | 0.142 | 0.053 | 0.111 | 0.315 | 33.31 | 120.91 | 1800.82 | Harmful |
| F13 session Tokyo 0-9 | 148 | 1647.33 | 1.67 | 444.32 | 0.183 | -0.100 | 0.236 | 0.387 | -220.57 | 42.81 | 1825.09 | Neutral |
| F14 session overlap 13-17 | 227 | 1349.08 | 1.45 | 360.28 | 0.091 | -0.032 | 0.235 | 0.196 | -178.21 | 165.11 | 1362.18 | Harmful |
| F15 pending expires 1 bar | 296 | 2031.54 | 1.62 | 271.73 | 0.170 | 0.087 | 0.241 | 0.252 | 156.69 | 281.66 | 1593.19 | Neutral |
| F16 pending expires 3 bars | 306 | 2533.61 | 1.75 | 304.86 | 0.205 | 0.104 | 0.194 | 0.378 | 218.79 | 207.06 | 2107.77 | Neutral |
| F17 pending invalidation OFF | 99 | 97.38 | 1.12 | 246.82 | 0.125 | 0.139 | 0.079 | - | 153.82 | -56.44 | 0.00 | Harmful |
| F18 entry buffer 0 | 306 | 2529.90 | 1.74 | 304.26 | 0.179 | 0.079 | 0.183 | 0.335 | 119.90 | 232.74 | 2177.26 | Helpful |
| F19 entry buffer 50 | 311 | 2324.71 | 1.64 | 307.26 | 0.154 | 0.032 | 0.196 | 0.312 | -2.42 | 207.78 | 2119.35 | Harmful |
| F20 volatility ATR ratio >= 1.0 | 158 | 1844.08 | 1.84 | 271.73 | 0.172 | -0.010 | 0.242 | 0.391 | 94.46 | 280.59 | 1469.03 | Neutral |
| F21 volatility ATR ratio <= 1.5 | 306 | 2247.33 | 1.67 | 304.86 | 0.147 | 0.039 | 0.167 | 0.307 | -1.17 | 211.65 | 2036.85 | Harmful |
| F22 volatility ATR ratio 0.8-1.5 | 277 | 1755.96 | 1.52 | 304.86 | 0.137 | 0.029 | 0.180 | 0.272 | -27.94 | 261.35 | 1522.55 | Harmful |
| F23 max spread 40 pts | 270 | 993.43 | 1.39 | 271.73 | 0.150 | 0.061 | 0.178 | 0.360 | 92.63 | 226.44 | 674.35 | Neutral |
| F24 MA18 slope over 3 bars | 272 | 2344.33 | 1.75 | 443.54 | 0.187 | 0.068 | 0.192 | 0.362 | 33.74 | 190.79 | 2119.81 | Neutral |
| F25 not extended |close-MA18| <= 1 ATR | 204 | 1634.45 | 1.74 | 400.56 | 0.205 | 0.116 | 0.243 | 0.334 | 173.02 | 251.89 | 1209.54 | Neutral |
| F26 not extended |close-MA18| <= 2 ATR | 276 | 2370.16 | 1.80 | 348.74 | 0.181 | 0.032 | 0.228 | 0.397 | 55.77 | 260.40 | 2053.99 | Neutral |
| F27 longs only | 181 | 2130.50 | 2.08 | 271.73 | 0.275 | 0.120 | 0.282 | 0.443 | 132.20 | 229.27 | 1769.02 | Helpful (information: no EA input) |
| F28 weekdays Mon-Thu only (no Friday entries) | 254 | 2277.72 | 1.88 | 243.69 | 0.193 | 0.085 | 0.194 | 0.369 | 125.13 | 187.20 | 1965.38 | Helpful (information: no EA input) |

## 5. Stage 3: combinations of the helpful filters

The single helpful filter (entry buffer 0) is the stack. Final entry side: 18/200 SMA, two closes, volume above its 20-bar mean, stop order at the bar high / low with no buffer.

| stack | trades | net $ | PF | maxDD $ | DEV net / R | VAL net / R | OOS net / R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| F18 | 306 | 2529.90 | 1.74 | 304.26 | 119.9 / 0.079 | 232.74 / 0.183 | 2177.26 / 0.335 | Helpful |

## 6. Stage 4: stops on the chosen exit

Fourteen stop variants on the chosen exit: none passes the rule. ATR stops of 1.5 to 2 ATR lower the drawdown ($235 to $256) but lose in the development window; caps and floors are neutral; the swing stop stays.

| stop | trades | median risk $ | net $ | PF | maxDD $ | DEV net / R | VAL net / R | OOS net / R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 309 | 29.74 | 2488.53 | 1.72 | 304.86 | 92.63 / 0.061 | 226.44 / 0.178 | 2169.46 / 0.332 | base |
| B ATR 1.5x | 327 | 16.15 | 2534.19 | 1.74 | 235.45 | 80.45 / -0.027 | 271.74 / 0.259 | 2182.0 / 0.457 | Neutral |
| B ATR 2.0x | 311 | 21.12 | 2523.48 | 1.73 | 255.94 | 71.08 / -0.021 | 306.3 / 0.247 | 2146.1 / 0.363 | Neutral |
| B ATR 2.5x | 309 | 26.07 | 2561.79 | 1.75 | 269.03 | 121.73 / -0.000 | 243.27 / 0.206 | 2196.8 / 0.318 | Harmful |
| B ATR 3.0x | 307 | 31.10 | 2576.54 | 1.76 | 282.85 | 118.22 / 0.000 | 247.48 / 0.198 | 2210.84 / 0.299 | Harmful |
| C swing strength 1 | 317 | 24.68 | 2536.88 | 1.74 | 273.09 | 41.44 / -0.016 | 313.67 / 0.240 | 2181.77 / 0.410 | Neutral |
| C swing strength 3 | 308 | 33.39 | 2494.34 | 1.72 | 299.52 | 99.51 / 0.058 | 245.32 / 0.170 | 2149.51 / 0.277 | Harmful |
| C swing - 0.5 ATR buffer | 307 | 33.91 | 2506.53 | 1.72 | 304.86 | 115.35 / 0.050 | 243.05 / 0.203 | 2148.13 / 0.293 | Harmful |
| C swing capped 1500 pts | 367 | 15.10 | 2336.62 | 1.76 | 212.40 | 78.42 / 0.046 | 267.07 / 0.197 | 1991.12 / 0.959 | Neutral |
| C swing capped 3000 pts | 327 | 30.10 | 2702.53 | 1.82 | 240.41 | 96.29 / 0.059 | 256.81 / 0.184 | 2349.44 / 0.728 | Neutral |
| E swing clamped [0.5, 3] ATR | 309 | 27.51 | 2558.67 | 1.75 | 282.85 | 98.41 / 0.047 | 217.44 / 0.175 | 2242.82 / 0.357 | Harmful |
| E swing clamped [1, 4] ATR | 308 | 29.57 | 2499.22 | 1.72 | 304.86 | 108.97 / 0.059 | 226.44 / 0.177 | 2163.81 / 0.338 | Harmful |
| F swing with 1.0 ATR floor | 308 | 29.74 | 2498.20 | 1.72 | 304.86 | 108.97 / 0.065 | 226.44 / 0.178 | 2162.79 / 0.335 | Neutral |
| F min stop 300 pts | 309 | 29.74 | 2488.53 | 1.72 | 304.86 | 92.63 / 0.061 | 226.44 / 0.178 | 2169.46 / 0.332 | Neutral |

## 7. Stage 5: MA periods on the chosen exit (sensitivity)

MA periods are reported as sensitivity, not selection. Fast 18 to 25 with trend 250 to 300 forms a second plateau that is positive in every split (20/250 +$2,909, PF 1.95, drawdown $210; 18/250 +$2,770; 25/300 +$2,871), while fast 13 to 14 and trend 150 fail the development window. 18/200 is kept because it was tested first and sits inside the plateau; 18/250 or 20/250 is the one change worth a forward test.

| fast/trend | trades | net $ | PF | maxDD $ | DEV net / R | VAL net / R | OOS net / R | positive in all splits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13/150 | 350 | 1987.35 | 1.54 | 344.48 | -105.44 / 0.042 | 253.35 / 0.129 | 1839.44 / 0.227 | no |
| 13/200 | 349 | 1815.53 | 1.47 | 338.77 | -74.92 / 0.008 | 141.64 / 0.077 | 1748.8 / 0.228 | no |
| 13/250 | 349 | 1975.48 | 1.52 | 329.47 | -31.38 / 0.020 | 102.82 / 0.098 | 1904.05 / 0.269 | no |
| 13/300 | 347 | 2111.94 | 1.56 | 329.47 | 134.1 / 0.079 | 219.69 / 0.191 | 1758.15 / 0.240 | yes |
| 14/150 | 341 | 2239.75 | 1.62 | 309.94 | -163.74 / 0.031 | 352.73 / 0.243 | 2050.76 / 0.234 | no |
| 14/200 | 341 | 2053.91 | 1.54 | 311.42 | -103.32 / 0.009 | 302.59 / 0.197 | 1854.64 / 0.227 | no |
| 14/250 | 339 | 2257.59 | 1.64 | 306.36 | -72.33 / 0.013 | 194.59 / 0.192 | 2135.33 / 0.291 | no |
| 14/300 | 339 | 2313.44 | 1.63 | 306.36 | 60.91 / 0.056 | 244.95 / 0.243 | 2007.58 / 0.275 | yes |
| 18/150 | 311 | 2194.17 | 1.59 | 334.86 | -74.5 / 0.074 | 255.07 / 0.215 | 2013.6 / 0.305 | no |
| 18/200 | 309 | 2488.53 | 1.72 | 304.86 | 92.63 / 0.061 | 226.44 / 0.178 | 2169.46 / 0.332 | yes |
| 18/250 | 301 | 2769.56 | 1.88 | 304.86 | 36.68 / 0.033 | 212.44 / 0.210 | 2520.44 / 0.434 | yes |
| 18/300 | 305 | 2724.21 | 1.82 | 367.48 | 205.27 / 0.071 | 248.24 / 0.277 | 2270.71 / 0.408 | yes |
| 20/150 | 297 | 2552.75 | 1.72 | 305.67 | 5.67 / 0.083 | 285.8 / 0.181 | 2261.27 / 0.349 | yes |
| 20/200 | 297 | 2617.94 | 1.81 | 303.97 | 36.11 / 0.062 | 306.44 / 0.202 | 2275.39 / 0.359 | yes |
| 20/250 | 295 | 2908.99 | 1.95 | 210.25 | 45.28 / 0.036 | 231.22 / 0.208 | 2632.49 / 0.467 | yes |
| 20/300 | 297 | 2811.05 | 1.87 | 249.79 | 144.43 / 0.071 | 245.75 / 0.212 | 2420.87 / 0.419 | yes |
| 21/150 | 300 | 2382.75 | 1.64 | 356.38 | -78.17 / -0.006 | 279.65 / 0.213 | 2181.26 / 0.343 | no |
| 21/200 | 298 | 2649.30 | 1.82 | 301.49 | -38.92 / -0.021 | 360.61 / 0.270 | 2327.61 / 0.371 | no |
| 21/250 | 298 | 2885.66 | 1.92 | 279.66 | -74.49 / -0.047 | 271.37 / 0.269 | 2688.78 / 0.492 | no |
| 21/300 | 294 | 2875.57 | 1.90 | 216.60 | 85.03 / 0.014 | 331.68 / 0.262 | 2458.86 / 0.425 | yes |
| 25/150 | 298 | 2190.39 | 1.60 | 335.82 | -110.28 / -0.034 | 289.41 / 0.268 | 2011.26 / 0.281 | no |
| 25/200 | 290 | 2247.23 | 1.68 | 399.78 | -118.75 / -0.050 | 283.88 / 0.259 | 2082.1 / 0.325 | no |
| 25/250 | 284 | 2797.94 | 1.89 | 235.28 | -59.37 / -0.060 | 262.86 / 0.285 | 2594.46 / 0.503 | no |
| 25/300 | 282 | 2870.71 | 1.93 | 252.18 | 89.81 / -0.015 | 397.66 / 0.388 | 2383.24 / 0.399 | yes |

## 8. Stage 6: final configuration and robustness

Final configuration = chosen exit + entry buffer 0, everything else v1.00. Six years: +$2,530, PF 1.74, max drawdown $304, 306 trades, win rate 40%, expectancy 0.18 R; exits: 175 MA18, 58 trailing, 43 break-even, 29 initial stop. Low cost +$3,016, stress +$2,340, worst intrabar ordering +$2,380. Walk-forward test years: +$91 (2023-24), +$393 (2024-25), +$1,926 (2025-26), with every train and validation window positive as well; the untouched EA's test years were +$164 / +$464 / +$834 with two negative training windows. By year: 2020 -$30, 2021 -$4, 2022 +$78, 2023 +$227, 2024 +$82, 2025 +$679, 2026 +$1,499. Profit comes from every session (London morning fills best, +$1,218) and from both sides (longs +$2,160, shorts +$370). 2023-2026 window: +$2,441, PF 1.95, 192 trades. 2003-2026 on the hourly path: +$2,762, PF 1.33, 11 of 24 years positive, 2003-2012 +$156, 2012-2020 -$65, 2020-2026 +$2,671; the untouched EA over the same 23 years: +$1,237 with 7 positive years. Monte Carlo on the six-year trade list at $200: ruin 20%, 95th-percentile drawdown $629, median ending balance $2,725; at $3,000 (100 x the median stop) ruin 0.

Final parameters (engine units): `{"thr_mode": 1, "protection": 4, "be_enable": true, "be_trigger_pts": 200, "prot_start_mode": 0, "trail_start_pts": 500, "trail_dist_pts": 50, "trail_step_pts": 10, "entry_buffer_pts": 0}`; filters added from stage 3: F18.

| configuration | trades | net $ | PF | maxDD $ | win % | exp R | DEV net / R | VAL net / R | OOS net / R | low cost $ | stress $ | worst ordering $ | median stop $ | MC p(ruin) $200 | MC p(ruin) 100x stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Untouched EA | 470 | 1181.17 | 1.69 | 328.96 | 51.50 | 0.068 | -280.25 / -0.037 | 271.75 / 0.115 | 1189.67 / 0.178 | 1620.95 | 786.91 | 1008.25 | 30.07 | 0.154 | 0.000 |
| E19 as tested | 355 | 2504.48 | 1.85 | 284.23 | 46.20 | 0.134 | 9.43 / 0.050 | 343.53 / 0.194 | 2151.53 / 0.231 | 2991.90 | 2352.72 | 2463.19 | 28.50 | 0.172 | 0.000 |
| Chosen exit (stage 1) | 309 | 2488.53 | 1.72 | 304.86 | 39.80 | 0.168 | 92.63 / 0.061 | 226.44 / 0.178 | 2169.46 / 0.332 | 3041.68 | 2332.74 | 2332.37 | 29.74 | 0.194 | 0.000 |
| Final (chosen exit + helpful filters) | 306 | 2529.90 | 1.74 | 304.26 | 40.20 | 0.179 | 119.9 / 0.079 | 232.74 / 0.183 | 2177.26 / 0.335 | 3015.98 | 2340.21 | 2379.77 | 29.75 | 0.199 | 0.000 |

Walk-forward folds (train / validate / test net $):

| configuration | fold 1 (test 2023-24) | fold 2 (test 2024-25) | fold 3 (test 2025-26) |
|---|---:|---:|---:|
| Untouched EA | -101.57 / -178.68 / 163.86 | -290.06 / 163.86 / 463.6 | -14.82 / 463.6 / 833.96 |
| E19 as tested | 14.78 / -5.35 / 160.9 | -63.41 / 160.9 / 391.13 | 155.55 / 391.13 / 1943.03 |
| Chosen exit (stage 1) | 1.26 / 91.37 / 86.03 | 85.39 / 86.03 / 388.63 | 177.4 / 388.63 / 1921.24 |
| Final (chosen exit + helpful filters) | 5.55 / 114.35 / 91.13 | 106.26 / 91.13 / 392.73 | 205.48 / 392.73 / 1926.14 |

By year:

| configuration | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Untouched EA | -45.03 | 6.62 | -85.65 | -76.54 | 192.10 | 483.60 | 706.07 |
| E19 as tested | -31.98 | 70.75 | 19.36 | 104.33 | 190.50 | 514.94 | 1636.59 |
| Chosen exit (stage 1) | -48.02 | 5.70 | 80.44 | 203.75 | 77.20 | 674.35 | 1495.10 |
| Final (chosen exit + helpful filters) | -30.19 | -4.43 | 78.23 | 226.83 | 82.20 | 678.75 | 1498.50 |

2003-2026 on the hourly intrabar path (H4 bars from H1 before Sep 2020; coarser than the M1 path, so treat as a regime check, not a precise number):

| configuration | trades | net $ | PF | maxDD $ | exp R | positive years | worst year $ | 2003-2012 net / R / trades | 2012-2020 | 2020-2026 | MC p(ruin) $200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Untouched EA | 1445 | 1237.38 | 1.23 | 665.07 | 0.007 | 7/24 | -147.80 | 124.37 / -0.079 / 484 | 59.23 / 0.052 / 492 | 1053.78 / 0.049 / 469 | 0.348 |
| E19 as tested | 1382 | 2482.20 | 1.34 | 516.46 | 0.021 | 12/24 | -155.78 | 43.69 / -0.028 / 514 | -50.93 / 0.005 / 500 | 2489.44 / 0.112 / 368 | 0.309 |
| Chosen exit (stage 1) | 1213 | 2744.58 | 1.33 | 500.37 | 0.030 | 11/24 | -132.83 | 169.64 / -0.019 / 442 | -60.74 / -0.008 / 453 | 2635.69 / 0.153 / 318 | 0.316 |
| Final (chosen exit + helpful filters) | 1221 | 2761.59 | 1.33 | 517.02 | 0.034 | 11/24 | -127.58 | 156.29 / -0.018 / 450 | -65.38 / -0.002 / 456 | 2670.68 / 0.162 / 315 | 0.313 |

By session and side (six years, net $ / trades):

| configuration | Asia | London | London/NY | New York | Sydney | long / short net $ | 2023-2026 net |
|---|---:|---:|---:|---:|---:|---:|---:|
| Untouched EA | 253.02 / 74 | 361.2 / 105 | 97.59 / 154 | 482.19 / 125 | -12.83 / 12 | 1079.31 / 101.86 | 1276.25 / PF 2.14 |
| E19 as tested | 555.56 / 65 | 1063.08 / 78 | 426.09 / 121 | 427.31 / 84 | 32.44 / 7 | 1823.44 / 681.04 | 2405.33 / PF 2.12 |
| Chosen exit (stage 1) | 522.28 / 51 | 1184.99 / 72 | 412.92 / 106 | 383.23 / 71 | -14.89 / 9 | 2130.5 / 358.03 | 2405.2 / PF 1.92 |
| Final (chosen exit + helpful filters) | 513.3 / 51 | 1217.95 / 71 | 435.64 / 107 | 364.04 / 69 | -1.02 / 8 | 2159.89 / 370.01 | 2440.98 / PF 1.95 |

## 9. Sensitivity of the final configuration

One parameter at a time around the final values. Stable: trailing distance 0.5 to 2 ATR (all positive in every split, +$2,530 to +$2,760), trailing step 0.05 to 0.3 ATR (no effect), break-even trigger 1 to 2 ATR (+$2,124 to +$2,578), ATR period 10 to 22 (+$2,530 to +$2,813), fast MA 18 to 22, trend MA 175 to 250 (+$2,530 to +$2,816). Cliffs: trailing start below 5 ATR is bumpy (3 ATR +$2,351 and positive, 4 ATR +$2,056 and not, 2 ATR +$1,896 and not, 1 ATR +$983), break-even under 1 ATR loses $600, ATR period 30 or 44 fails the development window, fast 14 or 16 and trend 150 fail it too. Use 5 to 6 ATR for the start, do not shorten it.

- **be_trigger_pts**: 50: net 1928.51 (PF 1.79, exp 0.098, DEV/VAL/OOS 0.044/0.115/0.172), 75: net 1796.07 (PF 1.58, exp 0.099, DEV/VAL/OOS 0.037/0.123/0.188), 100: net 2124.48 (PF 1.70, exp 0.138, DEV/VAL/OOS 0.069/0.227/0.188, all +), 125: net 2260.18 (PF 1.71, exp 0.147, DEV/VAL/OOS 0.071/0.201/0.228, all +), 150: net 2578.04 (PF 1.84, exp 0.164, DEV/VAL/OOS 0.064/0.222/0.284, all +), 200: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +)
- **trail_start_pts**: 100: net 983.31 (PF 1.20, exp 0.035, DEV/VAL/OOS -0.002/0.037/0.086), 150: net 1792.08 (PF 1.36, exp 0.069, DEV/VAL/OOS 0.039/0.056/0.120, all +), 200: net 1896.45 (PF 1.39, exp 0.077, DEV/VAL/OOS 0.001/0.121/0.160), 250: net 2107.91 (PF 1.44, exp 0.103, DEV/VAL/OOS 0.043/0.099/0.197, all +), 300: net 2351.01 (PF 1.53, exp 0.122, DEV/VAL/OOS 0.039/0.164/0.216, all +), 400: net 2056.11 (PF 1.50, exp 0.133, DEV/VAL/OOS 0.032/0.129/0.288), 500: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 600: net 2606.79 (PF 1.76, exp 0.194, DEV/VAL/OOS 0.054/0.279/0.353, all +)
- **trail_dist_pts**: 50: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 75: net 2652.51 (PF 1.73, exp 0.177, DEV/VAL/OOS 0.071/0.181/0.344, all +), 100: net 2759.64 (PF 1.79, exp 0.175, DEV/VAL/OOS 0.069/0.140/0.376, all +), 125: net 2612.1 (PF 1.77, exp 0.166, DEV/VAL/OOS 0.058/0.118/0.384, all +), 150: net 2548.55 (PF 1.73, exp 0.180, DEV/VAL/OOS 0.064/0.126/0.413, all +), 200: net 2552.61 (PF 1.78, exp 0.193, DEV/VAL/OOS 0.053/0.213/0.405, all +)
- **trail_step_pts**: 5: net 2554.0 (PF 1.74, exp 0.181, DEV/VAL/OOS 0.080/0.185/0.337, all +), 10: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 20: net 2523.53 (PF 1.73, exp 0.178, DEV/VAL/OOS 0.079/0.185/0.329, all +), 30: net 2533.61 (PF 1.74, exp 0.180, DEV/VAL/OOS 0.078/0.187/0.334, all +)
- **atr_period**: 10: net 2812.98 (PF 1.83, exp 0.176, DEV/VAL/OOS 0.042/0.218/0.355, all +), 14: net 2668.21 (PF 1.81, exp 0.185, DEV/VAL/OOS 0.048/0.217/0.381, all +), 22: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 30: net 2252.93 (PF 1.67, exp 0.136, DEV/VAL/OOS 0.028/0.117/0.330), 44: net 2387.94 (PF 1.70, exp 0.149, DEV/VAL/OOS 0.036/0.133/0.342)
- **fast**: 14: net 2023.08 (PF 1.52, exp 0.123, DEV/VAL/OOS 0.015/0.202/0.223), 16: net 2167.06 (PF 1.60, exp 0.120, DEV/VAL/OOS 0.012/0.206/0.223), 18: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 20: net 2632.14 (PF 1.82, exp 0.180, DEV/VAL/OOS 0.053/0.206/0.361, all +), 22: net 2575.11 (PF 1.80, exp 0.171, DEV/VAL/OOS -0.005/0.288/0.370, all +)
- **trend**: 150: net 2231.36 (PF 1.60, exp 0.183, DEV/VAL/OOS 0.087/0.220/0.308), 175: net 2637.65 (PF 1.78, exp 0.185, DEV/VAL/OOS 0.092/0.175/0.339, all +), 200: net 2529.9 (PF 1.74, exp 0.179, DEV/VAL/OOS 0.079/0.183/0.335, all +), 225: net 2731.0 (PF 1.87, exp 0.197, DEV/VAL/OOS 0.059/0.175/0.438, all +), 250: net 2815.76 (PF 1.91, exp 0.202, DEV/VAL/OOS 0.050/0.214/0.436, all +)

## 10. The EA changes

SimpleSMA18Bot_H4.mq5 is v1.00 plus one mechanism and new defaults; the file header lists every change. The mechanism: `UseATRScaledLevels` with `ATRBreakEvenMult`, `ATRProtectionStartMult`, `ATRTrailStartMult`, `ATRTrailDistanceMult`, `ATRTrailStepMult`; when it is on, the break-even trigger, the protection-start threshold and the trailing start / distance / step are the multiplier times ATR(`ATRPeriod`) of the last completed bar when the position was opened (`EntryATR`, captured in `UpdateTradeState` and fixed for the life of the trade, which is what the backtests assume). The point inputs keep working when the switch is off. Defaults: TimeFrame H4, ProtectionMode TRAILING, ProtectionStartMode START_IMMEDIATELY, ATRBreakEvenMult 2.0, ATRTrailStartMult 5.0, ATRTrailDistanceMult 0.5, ATRTrailStepMult 0.1, EntryBufferPoints 0, MA 18/200, ADX and session filters off, break-even offset 10 points, swing stop, MA18 exit, fixed 0.01 lot and the 1% gate unchanged. Not changed, on purpose: the dead failed-breakout and partial-close code, the double stop-percent check, and buy stops placed inside the spread (5 rejections in six years on H4). Before live use: run it in the MT5 tester on GOLD H4 2020-2026 and compare with the engine (expect the same trade dates with fills a few cents apart), fund it to about $3,000 for the 1% rule, and forward-test on the demo account.
