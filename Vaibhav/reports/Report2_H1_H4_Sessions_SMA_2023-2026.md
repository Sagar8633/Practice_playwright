# Study 2: H1 and H4, session-wise P/L, the 2023-2026 window, and the SMA choice

Prepared 2026-09-26 as a separate study; the first study's results are untouched. Same engine, data, costs and rules (see `../README.md`). Money per 0.01 lot.

## 1. Summary

H1 and H4 join D1 as timeframes where the untouched EA ends in profit (six years: H1 +$865, H4 +$1,181 per 0.01 lot), but with the same calendar as D1: losses in 2020-2023, profit in 2025-26. H1 fails the stress test and the walk-forward; H4 passes both more often than any other timeframe (28 of 120 configurations positive in all three splits). In the 2023-2026 window M1, M5 and M15 remain losers (-$19,017, -$2,240, -$160) and no session filter or SMA choice turns them positive in-sample; H1 (+$1,114), H4 (+$1,275) and D1 (+$594) are positive, with 2023 negative and 2025-26 carrying everything. Sessions: on H1 the profit sits in the 13-17 overlap and the Asian hours and the London morning loses; on H4 New York 17-22 is the best session; on M15 London 8-13 loses $977 while Asia, New York and Sydney fills are positive. The EA's own session filter helps only on H1 (New York 13-22: +$979 of the +$1,114 on 76% of the trades, positive in both halves) and mildly on H4; on D1 every London or New York window switches the EA off because the signal is evaluated at 01:00. SMA: 18 is not a special number. On H1 and H4 the fast average is a plateau from about 13 to 25 and the trend average matters more (150 on H1, 250-300 on H4 and D1 in this window); on D1 fast 10-14 beats 18 on 60-70 trades; nothing rescues M1, M5 or M15. The improved exit from study 1 (ADX 25 + Chandelier from the first tick) works on H4 and D1 and hurts H1. The $200 account is unchanged: the shipped EA takes no H4 or D1 trades and 4 on H1; with the gate off every timeframe except D1 is ruined in 2023 before the profitable years arrive.

## 2. H1 and H4 through the first study's pipeline (Sep 2020 - Sep 2026)

H1 and H4 are the first timeframes below D1 that end the six years in profit with the untouched rules: H1 +$865 per 0.01 lot (PF 1.18, 1,329 trades, max drawdown $450), H4 +$1,181 (PF 1.69, 470 trades, max drawdown $329). Both have the same shape as D1: the development window 2020-2023 loses (H1 -$426, H4 -$280), 2024 is small, and 2025-2026 supplies the profit (H1 +$1,111, H4 +$1,190). H1 is fragile: under stress costs it is -$45 and under the worst intrabar ordering -$121, and none of the 120 walk-forward configurations is positive in all three splits. H4 is sturdier: +$787 under stress, +$1,008 under the worst ordering, 28 of 120 configurations positive in all three splits, and every fold's train-best passed validation, although the validation-gated pick beat the untouched EA in only one of three test years. The exit mechanics are the D1 story again: on H4 the break-even stop takes 317 of 470 exits and returns -$75 on trades that were on average $20 in profit, the 52 swing-protection exits earn +$1,993, and the initial stop and the MA18 exit are the losers; 81% of H4 losers were at least $2 in profit first. Removing the MA18 exit or moving to volatility-scaled protection raises H1 to +$1,190 to +$1,509 and H4 to +$2,223 to +$2,504, but on H4 those exits are still negative in 2020-2023, so they are not classified as helpful. Stops change nothing of substance on either timeframe. On a $200 account the shipped EA takes 7 trades on H1 and none on H4 (6,853 and 1,962 setups blocked by the 1% gate); with the gate off both accounts are ruined during the 2020-2023 losing stretch, before the profitable years.

### Baseline

| TF | view | cost | trades | net $ | PF | win % | maxDD $ | end bal $ | ruin | blocked by 1% | avg risk $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H1 | strategy | A_low | 1348 | 1560.21 | 1.36 | 64.80 | 230.21 | 101560.21 | False | 0.00 | 27.57 |
| H1 | strategy | B_real | 1329 | 865.09 | 1.18 | 42.40 | 449.95 | 100865.09 | False | 0.00 | 27.72 |
| H1 | strategy | C_stress | 1347 | -44.53 | 0.99 | 17.70 | 854.42 | 99955.47 | False | 0.00 | 28.16 |
| H1 | ea_200 | A_low | 8 | -12.02 | 0.00 | 0.00 | 12.02 | 187.98 | False | 6853.00 | 1.50 |
| H1 | ea_200 | B_real | 7 | -11.55 | 0.00 | 0.00 | 11.55 | 188.45 | False | 6853.00 | 1.54 |
| H1 | ea_200 | C_stress | 7 | -14.35 | 0.00 | 0.00 | 14.35 | 185.65 | False | 6854.00 | 1.74 |
| H1 | ea_200_nofilt | A_low | 511 | -199.72 | 0.88 | 52.60 | 200.28 | 0.28 | True | 0.00 | 13.49 |
| H1 | ea_200_nofilt | B_real | 181 | -200.42 | 0.73 | 45.90 | 200.42 | -0.42 | True | 0.00 | 14.43 |
| H1 | ea_200_nofilt | C_stress | 115 | -200.09 | 0.61 | 19.10 | 200.09 | -0.09 | True | 0.00 | 15.76 |
| H4 | strategy | A_low | 469 | 1620.95 | 2.10 | 83.20 | 229.53 | 101620.95 | False | 0.00 | 49.93 |
| H4 | strategy | B_real | 470 | 1181.17 | 1.69 | 51.50 | 328.96 | 101181.17 | False | 0.00 | 49.77 |
| H4 | strategy | C_stress | 467 | 786.91 | 1.40 | 18.20 | 475.49 | 100786.91 | False | 0.00 | 50.22 |
| H4 | ea_200 | A_low | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1962.00 | - |
| H4 | ea_200 | B_real | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1962.00 | - |
| H4 | ea_200 | C_stress | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1962.00 | - |
| H4 | ea_200_nofilt | A_low | 469 | 1620.95 | 2.10 | 83.20 | 229.53 | 1820.95 | False | 0.00 | 49.93 |
| H4 | ea_200_nofilt | B_real | 192 | -199.83 | 0.74 | 61.50 | 241.95 | 0.17 | True | 0.00 | 26.37 |
| H4 | ea_200_nofilt | C_stress | 109 | -201.75 | 0.56 | 16.50 | 255.75 | -1.75 | True | 0.00 | 28.07 |

H1 strategy view, realistic costs: DEV -426.12 (-0.065 R), VAL 180.71 (0.059 R), OOS 1110.5 (0.085 R); worst intrabar ordering -121.07; exit mix {'SL_breakeven': 614, 'MA18_exit': 487, 'SL_swing': 129, 'SL_initial': 99}.
By year: 2020: -114.05 (PF 0.64, 71 tr); 2021: -182.04 (PF 0.74, 197 tr); 2022: 25.0 (PF 1.04, 200 tr); 2023: -30.2 (PF 0.95, 196 tr); 2024: 55.88 (PF 1.08, 200 tr); 2025: 373.69 (PF 1.37, 238 tr); 2026: 736.81 (PF 1.84, 227 tr)

Giveback: summed best profit 18566.62 vs realized 865.09; avg giveback 13.32, median 100.0% of best, worst 280.45. Profitable->loss (>= $2): 456 trades = 65% of losers, 4108.92 given up. By exit: MA18_exit: 487 tr, net -823.87, avg best 12.4; SL_breakeven: 614 tr, net -62.27, avg best 11.84; SL_initial: 99 tr, net -1206.81, avg best 1.74; SL_swing: 129 tr, net 2958.04, avg best 39.41.
Loss categories: 01 bad entry (never reached 0.25R): 58.2% (261 tr); 03 whipsaw (MA18 exit within 3 bars): 10.9% (72 tr); 12 other: 10.1% (92 tr); 10 low-liquidity hour: 8.2% (37 tr); 04 excessive SL: 5.4% (5 tr); 09 news/volatility event: 4.7% (15 tr); 02 correct entry, market reversal: 2.2% (37 tr); 06 protection too loose (gave back >60% of >=1R): 0.2% (8 tr); 11 spread/slippage (positive before costs): 0.0% (170 tr)

H4 strategy view, realistic costs: DEV -280.25 (-0.037 R), VAL 271.75 (0.115 R), OOS 1189.67 (0.178 R); worst intrabar ordering 1008.25; exit mix {'SL_breakeven': 317, 'MA18_exit': 77, 'SL_swing': 52, 'SL_initial': 24}.
By year: 2020: -45.03 (PF 0.31, 15 tr); 2021: 6.62 (PF 1.03, 65 tr); 2022: -85.65 (PF 0.73, 76 tr); 2023: -76.54 (PF 0.74, 78 tr); 2024: 192.1 (PF 1.73, 69 tr); 2025: 483.6 (PF 2.5, 89 tr); 2026: 706.07 (PF 4.0, 78 tr)

Giveback: summed best profit 10750.86 vs realized 1181.17; avg giveback 20.36, median 100.0% of best, worst 378.14. Profitable->loss (>= $2): 158 trades = 81% of losers, 2586.87 given up. By exit: MA18_exit: 77 tr, net -226.79, avg best 25.28; SL_breakeven: 317 tr, net -74.84, avg best 14.47; SL_initial: 24 tr, net -510.26, avg best 2.1; SL_swing: 52 tr, net 1993.05, avg best 80.11.
Loss categories: 01 bad entry (never reached 0.25R): 55.2% (66 tr); 09 news/volatility event: 15.2% (3 tr); 03 whipsaw (MA18 exit within 3 bars): 13.9% (15 tr); 10 low-liquidity hour: 10.1% (14 tr); 12 other: 3.4% (21 tr); 02 correct entry, market reversal: 1.5% (13 tr); 06 protection too loose (gave back >60% of >=1R): 0.7% (8 tr); 11 spread/slippage (positive before costs): 0.0% (56 tr)

### Entry filters (H1 / H4)

**H1** (base: 1329 trades, net 865.09, exp R DEV/VAL/OOS -0.065 / 0.059 / 0.085)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F01 volume filter OFF | 1806 | 506.04 | 1.08 | 729.99 | 0.00 | -0.079 | 0.018 | 0.096 | Harmful |
| F02 MA200 trend filter OFF | 2387 | 434.43 | 1.05 | 973.41 | -0.02 | -0.069 | 0.008 | 0.039 | Harmful |
| F03 1-bar confirmation | 1692 | 975.25 | 1.18 | 468.79 | 0.01 | -0.078 | 0.040 | 0.095 | Harmful |
| F04 3-bar confirmation | 1140 | 864.48 | 1.21 | 312.33 | 0.05 | -0.013 | 0.134 | 0.071 | Neutral |
| F05 ADX>=25 | 1012 | -439.86 | 0.89 | 502.67 | 0.01 | -0.028 | 0.082 | 0.017 | Neutral (still negative) |
| F06 ADX>=20 | 1204 | 51.53 | 1.01 | 387.11 | 0.01 | -0.042 | 0.063 | 0.039 | Neutral |
| F07 ADX>=30 | 772 | -433.36 | 0.86 | 628.84 | 0.03 | 0.065 | 0.025 | 0.002 | Harmful |
| F08 ADX>=25 rising(3) | 792 | -287.12 | 0.91 | 426.94 | 0.02 | -0.027 | 0.131 | 0.012 | Neutral (still negative) |
| F09 ADX>=25 consecutive rise(3) | 638 | -581.12 | 0.78 | 622.64 | 0.00 | -0.016 | 0.081 | -0.020 | Neutral (still negative) |
| F10 session London 8-17 | 861 | -228.45 | 0.93 | 403.58 | 0.01 | -0.068 | 0.138 | 0.036 | Harmful |
| F11 session New York 13-22 | 1037 | 887.25 | 1.24 | 318.99 | 0.03 | -0.039 | 0.098 | 0.073 | Neutral |
| F12 session London+NY 8-22 | 1216 | 461.66 | 1.10 | 360.79 | 0.01 | -0.045 | 0.082 | 0.055 | Neutral |
| F13 session Tokyo 0-9 | 333 | -110.14 | 0.92 | 199.74 | 0.04 | -0.051 | 0.166 | 0.042 | Neutral (still negative) |
| F14 session overlap 13-17 | 648 | 232.44 | 1.10 | 312.81 | 0.03 | -0.059 | 0.179 | 0.078 | Neutral |
| F15 pending expires 1 bar | 1266 | 597.25 | 1.14 | 467.72 | 0.03 | -0.054 | 0.113 | 0.087 | Neutral |
| F16 pending expires 3 bars | 1316 | 458.08 | 1.10 | 507.10 | 0.01 | -0.077 | 0.110 | 0.059 | Harmful |
| F17 pending invalidation OFF | 88 | -73.08 | 0.79 | 86.90 | -0.00 | -0.045 | 0.056 | - | Harmful |
| F18 entry buffer 0 | 1343 | 920.92 | 1.20 | 438.50 | 0.01 | -0.063 | 0.047 | 0.083 | Harmful |
| F19 entry buffer 50 | 1305 | 693.62 | 1.15 | 364.41 | 0.01 | -0.047 | 0.023 | 0.064 | Harmful |
| F20 volatility ATR ratio >= 1.0 | 648 | 424.69 | 1.18 | 303.54 | -0.00 | -0.034 | -0.011 | 0.050 | Harmful |
| F21 volatility ATR ratio <= 1.5 | 1313 | 866.72 | 1.18 | 412.40 | 0.02 | -0.064 | 0.080 | 0.085 | Neutral |
| F22 volatility ATR ratio 0.8-1.5 | 1175 | 707.20 | 1.17 | 581.30 | -0.01 | -0.093 | 0.051 | 0.076 | Harmful |
| F23 max spread 40 pts | 1102 | 128.28 | 1.03 | 449.95 | -0.00 | -0.065 | 0.059 | 0.081 | Neutral |
| F24 MA18 slope over 3 bars | 1166 | 1371.01 | 1.34 | 290.00 | 0.05 | -0.034 | 0.114 | 0.110 | Helpful |
| F25 not extended |close-MA18| <= 1 ATR | 750 | 633.77 | 1.28 | 155.06 | 0.02 | -0.054 | 0.124 | 0.078 | Neutral |
| F26 not extended |close-MA18| <= 2 ATR | 1156 | 606.99 | 1.16 | 574.77 | 0.01 | -0.084 | 0.063 | 0.102 | Neutral |

**H4** (base: 470 trades, net 1181.17, exp R DEV/VAL/OOS -0.037 / 0.115 / 0.178)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F01 volume filter OFF | 590 | 1903.08 | 1.96 | 325.93 | 0.07 | -0.003 | 0.072 | 0.167 | Harmful |
| F02 MA200 trend filter OFF | 797 | 1369.87 | 1.46 | 620.52 | 0.03 | -0.053 | 0.064 | 0.125 | Harmful |
| F03 1-bar confirmation | 583 | 856.22 | 1.35 | 454.14 | 0.03 | -0.062 | 0.038 | 0.163 | Harmful |
| F04 3-bar confirmation | 412 | 1145.63 | 1.74 | 296.56 | 0.08 | -0.032 | 0.154 | 0.203 | Neutral |
| F05 ADX>=25 | 341 | 961.10 | 1.75 | 185.60 | 0.07 | -0.022 | 0.171 | 0.109 | Neutral |
| F06 ADX>=20 | 400 | 1167.42 | 1.79 | 185.91 | 0.08 | -0.007 | 0.138 | 0.153 | Neutral |
| F07 ADX>=30 | 278 | 236.81 | 1.15 | 383.98 | 0.01 | -0.117 | 0.155 | 0.058 | Harmful |
| F08 ADX>=25 rising(3) | 270 | 467.28 | 1.42 | 212.96 | 0.07 | -0.030 | 0.207 | 0.096 | Neutral |
| F09 ADX>=25 consecutive rise(3) | 217 | 254.66 | 1.27 | 216.52 | 0.05 | -0.055 | 0.268 | 0.060 | Harmful |
| F10 session London 8-17 | 389 | 952.43 | 1.74 | 175.37 | 0.09 | -0.015 | 0.217 | 0.186 | Neutral |
| F11 session New York 13-22 | 391 | 996.70 | 1.79 | 220.85 | 0.05 | -0.007 | 0.145 | 0.069 | Neutral |
| F12 session London+NY 8-22 | 463 | 1133.43 | 1.71 | 310.70 | 0.07 | -0.034 | 0.113 | 0.179 | Neutral |
| F13 session Tokyo 0-9 | 180 | 418.19 | 1.41 | 281.09 | 0.10 | -0.137 | 0.217 | 0.220 | Neutral |
| F14 session overlap 13-17 | 281 | 222.45 | 1.24 | 190.60 | 0.01 | -0.020 | 0.042 | 0.040 | Harmful |
| F15 pending expires 1 bar | 419 | 824.38 | 1.53 | 285.19 | 0.09 | 0.009 | 0.189 | 0.142 | Neutral |
| F16 pending expires 3 bars | 459 | 953.89 | 1.55 | 313.52 | 0.07 | -0.012 | 0.116 | 0.161 | Neutral |
| F17 pending invalidation OFF | 48 | -85.26 | 0.52 | 97.57 | -0.11 | -0.104 | -0.122 | - | Harmful |
| F18 entry buffer 0 | 464 | 1264.09 | 1.78 | 322.79 | 0.07 | -0.031 | 0.110 | 0.193 | Neutral |
| F19 entry buffer 50 | 474 | 796.56 | 1.39 | 436.87 | 0.06 | -0.061 | 0.194 | 0.143 | Harmful |
| F20 volatility ATR ratio >= 1.0 | 229 | 754.46 | 1.91 | 198.53 | 0.07 | -0.083 | 0.346 | 0.141 | Harmful |
| F21 volatility ATR ratio <= 1.5 | 457 | 1234.54 | 1.73 | 346.96 | 0.07 | -0.042 | 0.115 | 0.190 | Neutral |
| F22 volatility ATR ratio 0.8-1.5 | 408 | 1151.04 | 1.74 | 343.20 | 0.08 | -0.044 | 0.187 | 0.201 | Neutral |
| F23 max spread 40 pts | 392 | 475.10 | 1.32 | 328.96 | 0.07 | -0.037 | 0.115 | 0.280 | Neutral |
| F24 MA18 slope over 3 bars | 417 | 1257.63 | 1.81 | 318.05 | 0.08 | -0.026 | 0.127 | 0.197 | Neutral |
| F25 not extended |close-MA18| <= 1 ATR | 246 | 1001.13 | 2.33 | 167.38 | 0.12 | -0.003 | 0.178 | 0.304 | Helpful |
| F26 not extended |close-MA18| <= 2 ATR | 389 | 1541.22 | 2.33 | 241.02 | 0.09 | -0.046 | 0.133 | 0.250 | Neutral |

### Stops (H1 / H4)

**H1** (base: 1329 trades, net 865.09, exp R DEV/VAL/OOS -0.065 / 0.059 / 0.085)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 1329 | 865.09 | 1.18 | 449.95 | 0.01 | -0.065 | 0.059 | 0.085 | base |
| B ATR 1.0x | 1603 | 416.76 | 1.08 | 490.04 | -0.03 | -0.164 | 0.084 | 0.098 | Neutral |
| B ATR 1.5x | 1451 | 613.30 | 1.12 | 491.09 | -0.01 | -0.124 | 0.069 | 0.090 | Neutral |
| B ATR 2.0x | 1369 | 935.03 | 1.20 | 505.24 | 0.01 | -0.092 | 0.093 | 0.094 | Neutral |
| B ATR 2.5x | 1343 | 850.16 | 1.18 | 522.35 | 0.01 | -0.071 | 0.079 | 0.072 | Harmful |
| B ATR 3.0x | 1332 | 804.84 | 1.17 | 528.32 | 0.01 | -0.058 | 0.065 | 0.065 | Neutral |
| C swing strength 1 | 1434 | 877.06 | 1.18 | 461.78 | -0.01 | -0.095 | 0.072 | 0.067 | Harmful |
| C swing strength 3 | 1303 | 818.59 | 1.18 | 438.26 | -0.00 | -0.064 | 0.015 | 0.066 | Harmful |
| C swing - 0.5 ATR buffer | 1325 | 775.41 | 1.16 | 468.99 | 0.01 | -0.052 | 0.045 | 0.069 | Harmful |
| C swing - 0.25 ATR buffer | 1326 | 832.47 | 1.17 | 454.88 | 0.01 | -0.057 | 0.052 | 0.077 | Harmful |
| C swing capped 1000 pts | 1444 | 101.03 | 1.02 | 546.49 | -0.00 | -0.090 | 0.045 | 0.079 | Harmful |
| C swing capped 1500 pts (v13) | 1380 | 563.07 | 1.11 | 471.56 | 0.02 | -0.070 | 0.059 | 0.108 | Neutral |
| C swing capped 2000 pts | 1351 | 932.13 | 1.20 | 491.14 | 0.03 | -0.067 | 0.059 | 0.130 | Neutral |
| D MA18 - 0 pts | 1416 | 811.66 | 1.17 | 451.33 | -0.01 | -0.158 | 0.083 | 0.148 | Neutral |
| D MA18 - 50 pts | 1387 | 813.81 | 1.17 | 486.68 | -0.01 | -0.156 | 0.075 | 0.149 | Neutral |
| E swing clamped [0.5, 3] ATR | 1338 | 818.75 | 1.17 | 527.25 | 0.01 | -0.077 | 0.073 | 0.087 | Neutral |
| E swing clamped [1, 4] ATR | 1330 | 842.49 | 1.17 | 474.96 | 0.01 | -0.067 | 0.061 | 0.083 | Harmful |
| E swing clamped [0.5, 2] ATR | 1372 | 939.15 | 1.20 | 489.12 | 0.01 | -0.098 | 0.092 | 0.104 | Neutral |
| F swing with 0.5 ATR floor | 1329 | 865.29 | 1.18 | 449.95 | 0.01 | -0.065 | 0.060 | 0.085 | Neutral |
| F swing with 1.0 ATR floor | 1329 | 861.35 | 1.18 | 451.63 | 0.01 | -0.065 | 0.061 | 0.084 | Neutral |
| F min stop 150 pts (v13 MinStopPoints) | 1329 | 865.09 | 1.18 | 449.95 | 0.01 | -0.065 | 0.059 | 0.085 | Neutral |
| F min stop 300 pts | 1329 | 864.85 | 1.18 | 450.39 | 0.01 | -0.065 | 0.061 | 0.085 | Neutral |

**H4** (base: 470 trades, net 1181.17, exp R DEV/VAL/OOS -0.037 / 0.115 / 0.178)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 470 | 1181.17 | 1.69 | 328.96 | 0.07 | -0.037 | 0.115 | 0.178 | base |
| B ATR 1.0x | 508 | 1362.51 | 1.86 | 279.44 | 0.09 | -0.121 | 0.238 | 0.296 | Neutral |
| B ATR 1.5x | 484 | 1299.55 | 1.82 | 275.19 | 0.06 | -0.090 | 0.178 | 0.205 | Neutral |
| B ATR 2.0x | 472 | 1324.52 | 1.82 | 307.23 | 0.06 | -0.077 | 0.212 | 0.164 | Harmful |
| B ATR 2.5x | 468 | 1348.55 | 1.85 | 310.76 | 0.06 | -0.064 | 0.199 | 0.144 | Harmful |
| B ATR 3.0x | 467 | 1333.32 | 1.83 | 308.53 | 0.06 | -0.050 | 0.196 | 0.130 | Harmful |
| C swing strength 1 | 513 | 1292.49 | 1.74 | 298.65 | 0.05 | -0.049 | 0.146 | 0.136 | Harmful |
| C swing strength 3 | 451 | 1313.07 | 1.81 | 358.22 | 0.07 | -0.052 | 0.192 | 0.171 | Harmful |
| C swing - 0.5 ATR buffer | 467 | 1225.37 | 1.72 | 325.95 | 0.07 | -0.034 | 0.215 | 0.142 | Neutral |
| C swing - 0.25 ATR buffer | 467 | 1226.92 | 1.72 | 321.37 | 0.09 | -0.033 | 0.237 | 0.160 | Neutral |
| C swing capped 1000 pts | 539 | 788.48 | 1.43 | 300.71 | 0.14 | -0.122 | 0.230 | 0.405 | Neutral |
| C swing capped 1500 pts (v13) | 504 | 1000.59 | 1.55 | 225.92 | 0.13 | -0.060 | 0.180 | 0.327 | Neutral |
| C swing capped 2000 pts | 491 | 1039.82 | 1.56 | 288.62 | 0.11 | -0.059 | 0.125 | 0.311 | Neutral |
| D MA18 - 0 pts | 483 | 1222.24 | 1.73 | 310.25 | 0.08 | -0.073 | 0.132 | 0.253 | Neutral |
| D MA18 - 50 pts | 478 | 1223.15 | 1.73 | 298.77 | 0.08 | -0.064 | 0.123 | 0.249 | Neutral |
| E swing clamped [0.5, 3] ATR | 472 | 1251.23 | 1.76 | 315.78 | 0.07 | -0.045 | 0.121 | 0.182 | Neutral |
| E swing clamped [1, 4] ATR | 470 | 1199.45 | 1.71 | 322.84 | 0.07 | -0.036 | 0.117 | 0.171 | Neutral |
| E swing clamped [0.5, 2] ATR | 476 | 1291.09 | 1.81 | 304.24 | 0.07 | -0.073 | 0.135 | 0.204 | Neutral |
| F swing with 0.5 ATR floor | 471 | 1186.35 | 1.70 | 328.96 | 0.07 | -0.037 | 0.115 | 0.181 | Neutral |
| F swing with 1.0 ATR floor | 470 | 1198.43 | 1.71 | 322.84 | 0.07 | -0.035 | 0.115 | 0.173 | Neutral |
| F min stop 150 pts (v13 MinStopPoints) | 471 | 1186.35 | 1.70 | 328.96 | 0.07 | -0.037 | 0.115 | 0.196 | Neutral |
| F min stop 300 pts | 471 | 1186.35 | 1.70 | 328.96 | 0.07 | -0.037 | 0.115 | 0.186 | Neutral |

### Exits (H1 / H4)

**H1** (base: 1329 trades, net 865.09, exp R DEV/VAL/OOS -0.065 / 0.059 / 0.085)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 1010 | 876.07 | 1.12 | 728.04 | 0.03 | -0.061 | -0.002 | 0.216 | Neutral |
| E01 EA default: BE + swing after 500 + MA18 | 1329 | 865.09 | 1.18 | 449.95 | 0.01 | -0.065 | 0.059 | 0.085 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 1332 | 1190.82 | 1.25 | 431.34 | 0.02 | -0.050 | 0.070 | 0.091 | Helpful |
| E03 Chandelier immediate + BE + MA18 (v13) | 1374 | 1136.40 | 1.23 | 417.22 | 0.02 | -0.048 | 0.066 | 0.083 | Neutral |
| E04 Trailing 1000/500/50 + BE + MA18 | 1732 | -198.17 | 0.97 | 659.49 | -0.01 | -0.050 | 0.030 | 0.014 | Harmful |
| E05 BE only + MA18 | 1296 | 922.59 | 1.19 | 457.42 | 0.01 | -0.061 | 0.051 | 0.087 | Neutral |
| E06 Trailing 1000/500/50 without BE + MA18 | 1561 | 146.60 | 1.02 | 698.45 | -0.01 | -0.062 | 0.005 | 0.033 | Harmful |
| E07 Chandelier + Trailing + BE + MA18 | 1777 | -262.36 | 0.96 | 679.27 | -0.01 | -0.043 | 0.030 | 0.014 | Harmful |
| E08 Swing immediate + BE + MA18 | 1353 | 846.36 | 1.18 | 394.72 | 0.01 | -0.063 | 0.060 | 0.083 | Neutral |
| E09 ATR trail 2.0x immediate + BE + MA18 | 1549 | 404.02 | 1.08 | 480.50 | 0.00 | -0.048 | 0.003 | 0.063 | Harmful |
| E10 ATR trail 3.0x immediate + BE + MA18 | 1345 | 1118.14 | 1.23 | 405.24 | 0.03 | -0.043 | 0.071 | 0.091 | Helpful |
| E11 ATR trail 1.5x immediate + BE + MA18 | 1778 | 43.91 | 1.01 | 671.71 | -0.02 | -0.059 | -0.017 | 0.043 | Harmful |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 1475 | 409.03 | 1.08 | 444.68 | 0.01 | -0.043 | 0.013 | 0.066 | Harmful |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 1915 | -199.91 | 0.97 | 607.26 | -0.01 | -0.050 | 0.017 | 0.020 | Harmful |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 1808 | 40.80 | 1.01 | 508.46 | -0.01 | -0.039 | 0.005 | 0.025 | Harmful |
| E15 EA default without MA18 exit | 1131 | 1192.82 | 1.26 | 307.58 | 0.04 | -0.055 | 0.121 | 0.104 | Helpful |
| E16 Chandelier immediate without MA18 exit + BE | 1256 | 1330.90 | 1.28 | 403.80 | 0.04 | -0.033 | 0.094 | 0.103 | Helpful |
| E17 Swing after 500 + MA18, no BE | 1046 | 823.14 | 1.11 | 725.44 | 0.04 | -0.043 | 0.044 | 0.201 | Neutral |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 1192 | 1509.49 | 1.26 | 482.03 | 0.03 | -0.062 | 0.079 | 0.162 | Neutral |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 1315 | 1169.01 | 1.17 | 520.87 | 0.01 | -0.065 | 0.059 | 0.116 | Neutral |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 1031 | 891.80 | 1.13 | 695.68 | 0.02 | -0.066 | 0.027 | 0.186 | Harmful |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 1042 | 931.30 | 1.13 | 765.46 | 0.04 | -0.048 | 0.030 | 0.210 | Neutral |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 1632 | 413.50 | 1.08 | 389.00 | 0.00 | -0.044 | 0.003 | 0.065 | Harmful |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 1303 | 1109.74 | 1.23 | 362.33 | 0.02 | -0.048 | 0.070 | 0.088 | Helpful |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 1086 | 803.03 | 1.11 | 710.31 | 0.01 | -0.064 | 0.002 | 0.174 | Neutral |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 981 | 801.57 | 1.11 | 821.13 | 0.05 | -0.024 | 0.053 | 0.213 | Neutral |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 1272 | 256.58 | 1.03 | 418.75 | -0.00 | -0.041 | 0.043 | 0.015 | Harmful |
| E27 BE 1000/10 + swing after 500 + MA18 | 1164 | 1016.71 | 1.19 | 478.70 | 0.01 | -0.057 | 0.026 | 0.105 | Neutral |
| E28 BE 2000/10 + swing after 500 + MA18 | 1076 | 1319.17 | 1.21 | 512.94 | 0.04 | -0.045 | 0.049 | 0.177 | Neutral |
| E29 time exit 5 bars (not in profit) + EA default | 1427 | 925.13 | 1.20 | 348.13 | 0.03 | -0.038 | 0.077 | 0.084 | Neutral |

**H4** (base: 470 trades, net 1181.17, exp R DEV/VAL/OOS -0.037 / 0.115 / 0.178)

| variant | trades | net $ | PF | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 260 | 1611.53 | 1.51 | 430.97 | 0.12 | -0.072 | 0.113 | 0.496 | Harmful |
| E01 EA default: BE + swing after 500 + MA18 | 470 | 1181.17 | 1.69 | 328.96 | 0.07 | -0.037 | 0.115 | 0.178 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 459 | 1606.79 | 1.98 | 314.60 | 0.06 | -0.013 | 0.046 | 0.171 | Harmful |
| E03 Chandelier immediate + BE + MA18 (v13) | 465 | 1732.92 | 2.16 | 263.97 | 0.06 | -0.021 | 0.052 | 0.174 | Harmful |
| E04 Trailing 1000/500/50 + BE + MA18 | 694 | 882.83 | 1.38 | 209.81 | 0.02 | -0.002 | 0.044 | 0.036 | Harmful |
| E05 BE only + MA18 | 441 | 1328.94 | 1.83 | 382.13 | 0.07 | -0.036 | 0.131 | 0.185 | Neutral |
| E06 Trailing 1000/500/50 without BE + MA18 | 608 | 590.88 | 1.15 | 334.18 | 0.02 | -0.010 | 0.017 | 0.047 | Harmful |
| E07 Chandelier + Trailing + BE + MA18 | 700 | 1000.64 | 1.45 | 213.66 | 0.02 | -0.009 | 0.050 | 0.040 | Harmful |
| E08 Swing immediate + BE + MA18 | 474 | 1154.00 | 1.67 | 359.55 | 0.07 | -0.039 | 0.114 | 0.177 | Harmful |
| E09 ATR trail 2.0x immediate + BE + MA18 | 516 | 2268.36 | 2.47 | 173.33 | 0.08 | 0.008 | 0.112 | 0.159 | Harmful |
| E10 ATR trail 3.0x immediate + BE + MA18 | 464 | 1838.80 | 2.24 | 210.59 | 0.07 | -0.001 | 0.054 | 0.177 | Harmful |
| E11 ATR trail 1.5x immediate + BE + MA18 | 564 | 2121.85 | 2.23 | 153.16 | 0.09 | 0.043 | 0.105 | 0.139 | Harmful |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 507 | 2101.01 | 2.23 | 210.61 | 0.08 | -0.001 | 0.112 | 0.154 | Harmful |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 736 | 899.45 | 1.38 | 207.45 | 0.03 | 0.014 | 0.048 | 0.036 | Harmful |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 710 | 1171.31 | 1.56 | 226.53 | 0.03 | 0.008 | 0.040 | 0.049 | Harmful |
| E15 EA default without MA18 exit | 443 | 1025.83 | 1.57 | 418.04 | 0.05 | -0.066 | 0.138 | 0.163 | Harmful |
| E16 Chandelier immediate without MA18 exit + BE | 452 | 1567.28 | 2.02 | 332.62 | 0.05 | -0.043 | 0.044 | 0.167 | Harmful |
| E17 Swing after 500 + MA18, no BE | 290 | 1638.15 | 1.51 | 499.92 | 0.09 | -0.097 | 0.082 | 0.428 | Harmful |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 322 | 1581.11 | 1.62 | 284.23 | 0.12 | -0.022 | 0.186 | 0.343 | Neutral |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 355 | 2504.48 | 1.85 | 284.23 | 0.13 | 0.050 | 0.194 | 0.231 | Neutral |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 269 | 1670.54 | 1.58 | 345.96 | 0.13 | -0.049 | 0.163 | 0.446 | Neutral |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 276 | 1877.45 | 1.60 | 355.73 | 0.13 | -0.041 | 0.167 | 0.407 | Neutral |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 527 | 2351.46 | 2.50 | 199.25 | 0.08 | 0.001 | 0.106 | 0.169 | Harmful |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 443 | 1525.47 | 1.97 | 334.26 | 0.08 | -0.026 | 0.121 | 0.203 | Neutral |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 290 | 1536.08 | 1.45 | 342.28 | 0.12 | -0.044 | 0.134 | 0.426 | Neutral |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 252 | 2223.29 | 1.77 | 282.24 | 0.13 | -0.031 | 0.052 | 0.464 | Neutral |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 550 | 806.25 | 1.22 | 418.27 | 0.02 | -0.019 | -0.021 | 0.068 | Harmful |
| E27 BE 1000/10 + swing after 500 + MA18 | 368 | 1292.19 | 1.59 | 296.54 | 0.09 | -0.040 | 0.104 | 0.240 | Harmful |
| E28 BE 2000/10 + swing after 500 + MA18 | 327 | 764.44 | 1.26 | 380.49 | 0.05 | -0.086 | 0.126 | 0.188 | Neutral |
| E29 time exit 5 bars (not in profit) + EA default | 488 | 1204.27 | 1.72 | 264.04 | 0.06 | -0.038 | 0.100 | 0.176 | Harmful |

### Walk-forward (H1 / H4)

**H1**: 120 configurations; positive in DEV, VAL and OOS: 0; share positive DEV 0.0, VAL 0.717, OOS 0.75.

| fold | train | test | train-best | train R | val R | test R | passes val | selected | selected test net $ | EA test net $ | share positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | vol>=1+ADX>=25 | swing | E20 R-BE1R+swing1R | 0.105 | -0.127 | -0.119 | False | none passes | - | 122.04 | 0.68 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | vol>=1+ADX>=25 | swing3 | E04 Trail+BE | 0.012 | -0.013 | -0.022 | False | vol>=1+ADX>=25 | ATR3 | E04 Trail+BE | 35.70 | 286.07 | 0.68 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | none | ATR3 | E16 Chand+BE noMA | 0.021 | 0.077 | 0.103 | True | none | ATR3 | E16 Chand+BE noMA | 1203.53 | 883.11 | 0.79 |

**H4**: 120 configurations; positive in DEV, VAL and OOS: 28; share positive DEV 0.233, VAL 1.0, OOS 1.0.

| fold | train | test | train-best | train R | val R | test R | passes val | selected | selected test net $ | EA test net $ | share positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | ADX>=25 | swing3 | E04 Trail+BE | 0.012 | 0.002 | 0.064 | True | ADX>=25 | swing3 | E04 Trail+BE | 190.25 | 163.86 | 0.99 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | 0.035 | 0.048 | 0.133 | True | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | 215.01 | 463.60 | 1.00 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | vol>=1+ADX>=25 | ATR3 | E01 EA | 0.213 | 0.126 | 0.172 | True | vol>=1+ADX>=25 | ATR3 | E01 EA | 608.74 | 833.96 | 1.00 |

Configurations positive in all three splits (top by OOS expectancy):

| config | DEV R | VAL R | OOS R | OOS net $ | all net $ | all PF | all DD $ | trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vol>=1+ADX>=25 | swing | E09 ATRtrail2+BE | -0.036 | 0.229 | 0.196 | 1186.17 | 1510.72 | 3.68 | 102.94 | 206 |
| vol>=1+ADX>=25 | ATR3 | E09 ATRtrail2+BE | -0.018 | 0.236 | 0.166 | 1177.85 | 1506.43 | 3.65 | 111.26 | 206 |
| vol>=1 | swing | E09 ATRtrail2+BE | -0.023 | 0.214 | 0.165 | 1144.66 | 1498.84 | 3.05 | 102.94 | 257 |
| vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | 0.008 | 0.212 | 0.145 | 1177.85 | 1503.25 | 3.63 | 111.26 | 206 |
| vol>=1 | ATR3 | E09 ATRtrail2+BE | -0.025 | 0.206 | 0.141 | 1136.34 | 1489.35 | 3.01 | 111.26 | 257 |
| vol>=1 | swing3 | E09 ATRtrail2+BE | -0.015 | 0.208 | 0.120 | 1136.34 | 1491.55 | 3.02 | 111.26 | 257 |
| vol>=1+ADX>=25 | swing | E04 Trail+BE | -0.016 | 0.110 | 0.056 | 323.30 | 602.52 | 1.66 | 172.76 | 281 |
| vol>=1+ADX>=25 | ATR3 | E04 Trail+BE | 0.002 | 0.140 | 0.048 | 408.59 | 688.40 | 1.84 | 128.86 | 279 |
| vol>=1 | swing | E04 Trail+BE | -0.014 | 0.089 | 0.045 | 312.28 | 572.50 | 1.50 | 172.76 | 337 |
| none | ATR3 | E04 Trail+BE | -0.015 | 0.065 | 0.043 | 785.41 | 1018.96 | 1.46 | 232.38 | 695 |

Candidate `vol>=1+ADX>=25 | swing | E09 ATRtrail2+BE`: sensitivity (value: all-period exp R (net) | OOS exp R):

- fast: 14: 0.082 (1152.1) | 0.096, 16: 0.101 (1451.74) | 0.123, 18: 0.110 (1510.72) | 0.196, 20: 0.107 (1491.69) | 0.189, 22: 0.119 (1467.1) | 0.196
- trend: 150: 0.121 (1612.95) | 0.209, 175: 0.111 (1508.93) | 0.192, 200: 0.110 (1510.72) | 0.196, 225: 0.101 (1409.72) | 0.197, 250: 0.108 (1433.0) | 0.197
- atr_trail_mult: 1.5: 0.087 (1243.86) | 0.153, 1.75: 0.089 (1305.37) | 0.143, 2.0: 0.110 (1510.72) | 0.196, 2.25: 0.106 (1380.96) | 0.174, 2.5: 0.105 (1411.53) | 0.166
- be_trigger_pts: 300: 0.050 (998.59) | 0.115, 400: 0.088 (1146.61) | 0.174, 500: 0.110 (1510.72) | 0.196, 600: 0.120 (1532.64) | 0.215, 700: 0.137 (1687.64) | 0.259
- adx_min: 20: 0.106 (1529.42) | 0.179, 22.5: 0.108 (1517.07) | 0.183, 25: 0.110 (1510.72) | 0.196, 27.5: 0.104 (1282.27) | 0.198, 30: 0.089 (1226.16) | 0.240
- vol_filter_min: 0.8: 0.098 (1859.36) | 0.146, 0.9: 0.105 (1750.89) | 0.164, 1.0: 0.110 (1510.72) | 0.196, 1.1: 0.147 (1468.14) | 0.236, 1.2: 0.182 (1107.39) | 0.272

Monte Carlo at $200: p(ruin) 0.0014 / 0.0056, DD p95 191.26, end p05/median/p95 875.84 / 1675.95 / 2671.54; median stop 41.59.

## 3. The 2023-2026 window, all six timeframes

Over 1 Jan 2023 to 26 Sep 2026 the untouched EA loses on M1 (-$19,017, PF 0.61), M5 (-$2,240, PF 0.87) and M15 (-$160, PF 0.98; +$1,094 at low cost, -$1,846 under stress), and wins on H1 (+$1,114, PF 1.35), H4 (+$1,275, PF 2.14) and D1 (+$594, PF 3.59). Every profitable timeframe has the same calendar: 2023 negative (H1 -$52, H4 -$106, D1 -$157), 2024 small (+$56, +$192, +$128), 2025-2026 large. In-sample 2023-24 is roughly zero everywhere that is not a loss (H1 +$3, H4 +$86, D1 -$29); out-of-sample 2025-26 carries it all (H1 +$1,111, H4 +$1,190, D1 +$623). Read the rest of this study with that in mind: a setting that looks good in this window is a setting that suited the 2025-26 gold rally. On $200 the shipped EA takes 304 trades on M1, 254 on M5, 130 on M15, 4 on H1 and none on H4 or D1 (blocked by the 1% gate); with the gate off every timeframe except D1 is ruined, H1 and H4 included, because 2023 losses arrive first.

### Baseline 2023-01-01 to 2026-09-26 (IS = 2023-24, OOS = 2025-26)

| TF | view | cost | trades | net $ | PF | win % | maxDD $ | end bal $ | ruin | blocked by 1% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | strategy | A_low | 35190 | -7334.26 | 0.82 | 29.50 | 7379.42 | 92665.74 | False | 0.00 |
| M1 | strategy | B_real | 34232 | -19017.14 | 0.61 | 21.60 | 19046.70 | 80982.86 | False | 0.00 |
| M1 | strategy | C_stress | 32180 | -37236.80 | 0.40 | 15.70 | 37258.48 | 62763.20 | False | 0.00 |
| M1 | ea_200 | A_low | 599 | -190.98 | 0.32 | 11.70 | 198.65 | 9.02 | False | 267429.00 |
| M1 | ea_200 | B_real | 304 | -194.14 | 0.11 | 4.90 | 194.61 | 5.86 | False | 269070.00 |
| M1 | ea_200 | C_stress | 183 | -195.86 | 0.07 | 4.40 | 196.29 | 4.14 | False | 269510.00 |
| M1 | ea_200_nofilt | A_low | 870 | -199.76 | 0.65 | 26.10 | 206.98 | 0.24 | True | 0.00 |
| M1 | ea_200_nofilt | B_real | 374 | -200.34 | 0.40 | 20.10 | 203.22 | -0.34 | True | 0.00 |
| M1 | ea_200_nofilt | C_stress | 194 | -198.98 | 0.25 | 12.90 | 202.71 | 1.02 | False | 0.00 |
| M5 | strategy | A_low | 7768 | 794.28 | 1.05 | 41.30 | 815.99 | 100794.28 | False | 0.00 |
| M5 | strategy | B_real | 7731 | -2240.45 | 0.87 | 26.30 | 2580.98 | 97759.55 | False | 0.00 |
| M5 | strategy | C_stress | 7559 | -6306.81 | 0.69 | 19.00 | 6313.30 | 93693.19 | False | 0.00 |
| M5 | ea_200 | A_low | 429 | -142.15 | 0.51 | 14.90 | 145.48 | 57.85 | False | 50377.00 |
| M5 | ea_200 | B_real | 254 | -152.64 | 0.31 | 9.40 | 156.59 | 47.36 | False | 51205.00 |
| M5 | ea_200 | C_stress | 126 | -168.07 | 0.05 | 3.20 | 171.22 | 31.93 | False | 51903.00 |
| M5 | ea_200_nofilt | A_low | 1037 | -198.41 | 0.84 | 28.60 | 211.98 | 1.59 | False | 0.00 |
| M5 | ea_200_nofilt | B_real | 284 | -199.06 | 0.52 | 25.40 | 205.06 | 0.94 | False | 0.00 |
| M5 | ea_200_nofilt | C_stress | 183 | -200.23 | 0.40 | 20.80 | 200.23 | -0.23 | True | 0.00 |
| M15 | strategy | A_low | 2947 | 1093.68 | 1.14 | 55.00 | 332.75 | 101093.68 | False | 0.00 |
| M15 | strategy | B_real | 2941 | -159.90 | 0.98 | 31.30 | 787.05 | 99840.10 | False | 0.00 |
| M15 | strategy | C_stress | 2909 | -1845.97 | 0.81 | 18.30 | 2058.89 | 98154.03 | False | 0.00 |
| M15 | ea_200 | A_low | 159 | -46.26 | 0.71 | 16.40 | 72.17 | 153.74 | False | 17315.00 |
| M15 | ea_200 | B_real | 130 | -70.24 | 0.56 | 13.80 | 94.10 | 129.76 | False | 17455.00 |
| M15 | ea_200 | C_stress | 93 | -89.79 | 0.40 | 7.50 | 107.01 | 110.21 | False | 17639.00 |
| M15 | ea_200_nofilt | A_low | 1258 | -200.25 | 0.92 | 40.10 | 236.44 | -0.25 | True | 0.00 |
| M15 | ea_200_nofilt | B_real | 363 | -200.12 | 0.74 | 35.00 | 229.72 | -0.12 | True | 0.00 |
| M15 | ea_200_nofilt | C_stress | 120 | -200.32 | 0.39 | 16.70 | 224.16 | -0.32 | True | 0.00 |
| H1 | strategy | A_low | 870 | 1677.98 | 1.59 | 71.30 | 166.43 | 101677.98 | False | 0.00 |
| H1 | strategy | B_real | 860 | 1113.93 | 1.35 | 39.40 | 201.12 | 101113.93 | False | 0.00 |
| H1 | strategy | C_stress | 880 | 434.80 | 1.12 | 16.60 | 379.59 | 100434.80 | False | 0.00 |
| H1 | ea_200 | A_low | 4 | -5.56 | 0.00 | 0.00 | 5.56 | 194.44 | False | 4283.00 |
| H1 | ea_200 | B_real | 4 | -6.36 | 0.00 | 0.00 | 6.36 | 193.64 | False | 4283.00 |
| H1 | ea_200 | C_stress | 4 | -7.96 | 0.00 | 0.00 | 7.96 | 192.04 | False | 4283.00 |
| H1 | ea_200_nofilt | A_low | 870 | 1677.98 | 1.59 | 71.30 | 166.43 | 1877.98 | False | 0.00 |
| H1 | ea_200_nofilt | B_real | 144 | -198.96 | 0.61 | 45.10 | 198.96 | 1.04 | False | 0.00 |
| H1 | ea_200_nofilt | C_stress | 116 | -200.13 | 0.57 | 21.60 | 204.63 | -0.13 | True | 0.00 |
| H4 | strategy | A_low | 313 | 1610.32 | 2.72 | 87.50 | 173.92 | 101610.32 | False | 0.00 |
| H4 | strategy | B_real | 314 | 1275.38 | 2.14 | 45.50 | 193.74 | 101275.38 | False | 0.00 |
| H4 | strategy | C_stress | 311 | 980.66 | 1.72 | 18.30 | 228.27 | 100980.66 | False | 0.00 |
| H4 | ea_200 | A_low | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1274.00 |
| H4 | ea_200 | B_real | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1274.00 |
| H4 | ea_200 | C_stress | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 1274.00 |
| H4 | ea_200_nofilt | A_low | 313 | 1610.32 | 2.72 | 87.50 | 173.92 | 1810.32 | False | 0.00 |
| H4 | ea_200_nofilt | B_real | 62 | -199.82 | 0.30 | 61.30 | 200.94 | 0.18 | True | 0.00 |
| H4 | ea_200_nofilt | C_stress | 52 | -199.92 | 0.27 | 19.20 | 200.44 | 0.08 | True | 0.00 |
| D1 | strategy | A_low | 63 | 839.94 | 6.58 | 96.80 | 150.17 | 100839.94 | False | 0.00 |
| D1 | strategy | B_real | 63 | 594.06 | 3.59 | 42.90 | 179.40 | 100594.06 | False | 0.00 |
| D1 | strategy | C_stress | 63 | 576.63 | 3.37 | 11.10 | 183.39 | 100576.63 | False | 0.00 |
| D1 | ea_200 | A_low | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 258.00 |
| D1 | ea_200 | B_real | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 258.00 |
| D1 | ea_200 | C_stress | 0 | 0.00 | - | - | 0.00 | 200.00 | 0.00 | 258.00 |
| D1 | ea_200_nofilt | A_low | 63 | 839.94 | 6.58 | 96.80 | 150.17 | 1039.94 | False | 0.00 |
| D1 | ea_200_nofilt | B_real | 63 | 594.06 | 3.59 | 42.90 | 179.40 | 794.06 | False | 0.00 |
| D1 | ea_200_nofilt | C_stress | 63 | 576.63 | 3.37 | 11.10 | 183.39 | 776.63 | False | 0.00 |

Strategy view, realistic costs, by year and by split:

| TF | 2023 | 2024 | 2025 | 2026 | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | -4223.16 | -4664.12 | -5593.86 | -4536.0 | -8887.28 | -0.392 | -10129.86 | -0.177 |
| M5 | -767.96 | -1007.3 | -661.83 | 196.64 | -1775.26 | -0.190 | -465.19 | -0.042 |
| M15 | -238.08 | -220.35 | -181.63 | 480.16 | -458.43 | -0.093 | 298.53 | -0.004 |
| H1 | -52.45 | 55.88 | 373.69 | 736.81 | 3.42 | 0.005 | 1110.50 | 0.085 |
| H4 | -106.39 | 192.1 | 483.6 | 706.07 | 85.71 | 0.019 | 1189.67 | 0.178 |
| D1 | -157.44 | 128.22 | 638.91 | -15.63 | -29.22 | 0.008 | 623.28 | 0.208 |

## 4. Session-wise profit and loss (by fill time, server hours)

By the time the order filled (server time). M1 loses in every session and at every hour; the least bad hours (23:00, 08:00) still lose. M5 loses in every session; New York 17-22 is nearest to flat (-$69 on 1,403 trades). M15 is the first timeframe with a real session pattern: Asia 0-8 +$184, New York 17-22 +$294 and Sydney 22-24 +$436 (116 trades) against London 8-13 -$977 on 713 trades; the 10:00-12:00 hours and the 15:00 hour are the worst. H1 makes its money in the London/New York overlap 13-17 (+$573) and Asia (+$493) and loses in the London morning 8-13 (-$280); Tuesday and Friday fills are strongly positive, Wednesday and Thursday negative; longs +$1,461 versus shorts -$347. H4 is positive in every session except the nine Sydney fills, with New York 17-22 the best (+$565, PF 2.95) and the overlap the weakest (+$64 on 97 trades, most of them break-even exits); longs +$1,025, shorts +$251. D1 fills mostly in the Asian hours after the 01:00 signal (+$524 on 31 trades) and its London/New York-overlap fills lose (-$173 on 18); longs +$706, shorts -$111. The weekday and hour cells are small samples on H4 and D1 (6 to 20 trades) and should not be turned into rules.

Non-overlapping sessions: Asia 0-8, London 8-13, London/NY 13-17, New York 17-22, Sydney 22-24.

| TF | session | trades | net $ | PF | win % | exp $ | avg best $ | avg giveback $ | P->L >$2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | Asia | 10021 | -5091.41 | 0.63 | 20.80 | -0.51 | 2.46 | 2.97 | 1023 |
| M1 | London | 7568 | -4443.76 | 0.57 | 22.30 | -0.59 | 2.39 | 2.98 | 852 |
| M1 | London/NY | 6751 | -3454.65 | 0.68 | 22.70 | -0.51 | 3.21 | 3.72 | 1046 |
| M1 | NewYork | 7424 | -4836.06 | 0.57 | 22.40 | -0.65 | 2.76 | 3.41 | 970 |
| M1 | Sydney | 2468 | -1191.27 | 0.62 | 17.50 | -0.48 | 2.03 | 2.51 | 181 |
| M5 | Asia | 2305 | -541.18 | 0.89 | 25.00 | -0.23 | 5.79 | 6.03 | 563 |
| M5 | London | 1836 | -990.43 | 0.74 | 25.90 | -0.54 | 5.06 | 5.60 | 449 |
| M5 | London/NY | 1771 | -425.18 | 0.91 | 28.20 | -0.24 | 7.49 | 7.73 | 528 |
| M5 | NewYork | 1403 | -69.05 | 0.98 | 28.90 | -0.05 | 6.66 | 6.71 | 379 |
| M5 | Sydney | 416 | -214.61 | 0.74 | 19.00 | -0.52 | 4.72 | 5.23 | 89 |
| M15 | Asia | 825 | 183.78 | 1.08 | 31.20 | 0.22 | 9.71 | 9.49 | 249 |
| M15 | London | 713 | -977.04 | 0.50 | 27.60 | -1.37 | 7.18 | 8.55 | 244 |
| M15 | London/NY | 765 | -96.67 | 0.96 | 34.20 | -0.13 | 10.50 | 10.63 | 245 |
| M15 | NewYork | 522 | 293.72 | 1.19 | 33.70 | 0.56 | 11.10 | 10.54 | 193 |
| M15 | Sydney | 116 | 436.31 | 2.63 | 25.00 | 3.76 | 14.96 | 11.20 | 42 |
| H1 | Asia | 148 | 493.21 | 2.25 | 35.80 | 3.33 | 19.96 | 16.63 | 51 |
| H1 | London | 175 | -280.13 | 0.66 | 40.60 | -1.60 | 12.35 | 13.95 | 63 |
| H1 | London/NY | 238 | 572.52 | 1.72 | 43.70 | 2.41 | 16.25 | 13.84 | 79 |
| H1 | NewYork | 262 | 171.02 | 1.17 | 37.80 | 0.65 | 16.73 | 16.07 | 113 |
| H1 | Sydney | 37 | 157.30 | 2.11 | 32.40 | 4.25 | 22.71 | 18.46 | 18 |
| H4 | Asia | 60 | 251.50 | 1.97 | 43.30 | 4.19 | 37.04 | 32.85 | 20 |
| H4 | London | 72 | 398.65 | 2.64 | 48.60 | 5.54 | 24.30 | 18.76 | 27 |
| H4 | London/NY | 97 | 63.64 | 1.20 | 56.70 | 0.66 | 18.66 | 18.00 | 27 |
| H4 | NewYork | 76 | 565.37 | 2.95 | 32.90 | 7.44 | 34.00 | 26.56 | 40 |
| H4 | Sydney | 9 | -3.79 | 0.17 | 22.20 | -0.42 | 12.61 | 13.04 | 6 |
| D1 | Asia | 31 | 523.68 | 13.31 | 41.90 | 16.89 | 95.44 | 78.54 | 15 |
| D1 | London | 7 | 234.77 | 234771200000.00 | 85.70 | 33.54 | 89.48 | 55.94 | 1 |
| D1 | London/NY | 18 | -173.32 | 0.00 | 38.90 | -9.63 | 21.96 | 31.59 | 10 |
| D1 | NewYork | 6 | 8.93 | 1.69 | 16.70 | 1.49 | 40.82 | 39.34 | 4 |
| D1 | Sydney | 1 | -0.00 | 0.00 | 0.00 | -0.00 | 18.07 | 18.07 | 1 |

The EA's own (overlapping) session windows, same trades counted in every window they fall in:

| TF | EA session | trades | net $ | PF | win % | exp $ |
|---|---:|---:|---:|---:|---:|---:|
| M1 | Sydney 22-07 | 10991 | -5714.81 | 0.62 | 20.20 | -0.52 |
| M1 | Tokyo 0-9 | 11576 | -5497.12 | 0.65 | 21.00 | -0.47 |
| M1 | London 8-17 | 14319 | -7898.40 | 0.62 | 22.50 | -0.55 |
| M1 | New York 13-22 | 14175 | -8290.70 | 0.62 | 22.50 | -0.58 |
| M5 | Sydney 22-07 | 2371 | -917.55 | 0.81 | 24.00 | -0.39 |
| M5 | Tokyo 0-9 | 2739 | -627.32 | 0.89 | 25.00 | -0.23 |
| M5 | London 8-17 | 3607 | -1415.62 | 0.83 | 27.00 | -0.39 |
| M5 | New York 13-22 | 3174 | -494.24 | 0.94 | 28.50 | -0.16 |
| M15 | Sydney 22-07 | 867 | 253.41 | 1.10 | 29.30 | 0.29 |
| M15 | Tokyo 0-9 | 975 | 49.13 | 1.02 | 31.00 | 0.05 |
| M15 | London 8-17 | 1478 | -1073.71 | 0.76 | 31.10 | -0.73 |
| M15 | New York 13-22 | 1287 | 197.04 | 1.05 | 34.00 | 0.15 |
| H1 | Sydney 22-07 | 176 | 545.74 | 2.08 | 35.20 | 3.10 |
| H1 | Tokyo 0-9 | 167 | 275.55 | 1.45 | 34.70 | 1.65 |
| H1 | London 8-17 | 413 | 292.39 | 1.18 | 42.40 | 0.71 |
| H1 | New York 13-22 | 500 | 743.54 | 1.41 | 40.60 | 1.49 |
| H4 | Sydney 22-07 | 62 | 197.70 | 1.82 | 37.10 | 3.19 |
| H4 | Tokyo 0-9 | 85 | 313.36 | 1.69 | 44.70 | 3.69 |
| H4 | London 8-17 | 169 | 462.30 | 1.82 | 53.30 | 2.73 |
| H4 | New York 13-22 | 173 | 629.01 | 2.03 | 46.20 | 3.64 |
| D1 | Sydney 22-07 | 32 | 523.68 | 13.31 | 40.60 | 16.36 |
| D1 | Tokyo 0-9 | 33 | 608.52 | 15.30 | 45.50 | 18.44 |
| D1 | London 8-17 | 25 | 61.45 | 1.35 | 52.00 | 2.46 |
| D1 | New York 13-22 | 24 | -164.39 | 0.12 | 33.30 | -6.85 |

Net $ by hour of fill (server time):

| TF | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | - | -811.27 | -616.64 | -640.52 | -644.86 | -855.00 | -955.25 | -567.87 | -405.71 | -1010.76 | -973.54 | -882.37 | -1171.37 | -910.36 | -984.17 | -915.09 | -645.03 | -713.31 | -922.48 | -1214.77 | -981.07 | -1004.42 | -788.19 | -403.08 |
| M5 | - | -89.04 | -42.91 | -249.31 | -186.92 | -114.90 | -19.88 | 161.77 | -86.14 | -210.40 | -240.21 | -229.82 | -223.87 | 126.08 | -568.45 | 6.63 | 10.55 | 12.97 | -34.51 | -230.97 | -74.95 | 258.42 | -40.61 | -174.00 |
| M15 | - | -110.43 | -124.78 | 213.52 | -64.88 | -78.57 | -17.77 | 366.68 | -134.65 | -155.47 | -103.61 | -289.30 | -294.00 | 108.24 | -114.84 | -172.98 | 82.92 | -22.54 | 95.41 | -73.63 | 194.51 | 99.96 | 396.91 | 39.40 |
| H1 | - | 82.53 | -1.42 | 118.55 | 16.46 | 28.67 | 143.64 | 104.77 | -217.66 | -92.65 | 39.04 | 57.01 | -65.87 | 118.05 | 108.40 | 149.50 | 196.58 | -160.35 | 84.73 | 131.28 | -34.04 | 149.40 | 195.29 | -37.98 |
| H4 | - | 49.27 | 14.75 | 71.43 | 22.91 | 43.13 | 0.00 | 50.01 | 61.85 | 230.10 | 93.03 | -0.67 | 14.35 | 63.60 | -33.40 | 75.76 | -42.33 | 502.15 | -89.87 | -0.00 | 87.54 | 65.56 | -2.92 | -0.87 |
| D1 | - | 50.29 | -7.82 | -10.42 | 493.36 | -1.74 | -0.00 | - | 84.84 | 59.13 | - | - | 90.81 | 0.00 | -6.95 | -162.90 | -3.47 | -13.03 | -0.00 | 21.95 | - | - | -0.00 | - |

Net $ by weekday of fill (0 = Monday):

| TF | Mon | Tue | Wed | Thu | Fri |
|---|---:|---:|---:|---:|---:|
| M1 | -3839.75 | -3695.28 | -4172.85 | -3663.89 | -3645.37 |
| M5 | -675.06 | -806.80 | -27.84 | -361.43 | -369.33 |
| M15 | -15.99 | 255.35 | -380.87 | -611.40 | 593.00 |
| H1 | 274.06 | 519.71 | -256.72 | -148.48 | 725.34 |
| H4 | 390.95 | 131.03 | -93.88 | 739.90 | 107.38 |
| D1 | 525.28 | -19.10 | -15.63 | 55.51 | 48.01 |

### The EA's session filter switched on (UseSessionFilter with each window), 2023-2026

The EA's own filter acts at the signal bar, so it can only stop new setups; it does not close trades at the session end. M1: every window loses; the filters just scale the loss with the trade count. M5: every window loses; Tokyo 0-9 and Sydney 22-07 are positive out of sample (+$228, +$76) after losing in-sample. M15: Sydney 22-07 turns the window into +$381 (PF 1.14) and Tokyo 0-9 into +$163, but both lose in 2023-24 (-$116, -$119) and win only in 2025-26, while London 8-17 and the overlap make the loss worse; this is the same M15 pattern as study 1, regime not skill. H1: New York 13-22 keeps 655 of 860 trades and +$979 of the +$1,114 with a better profit factor (1.41 vs 1.35) and is positive in both halves (+$130 in-sample, +$849 out); London 8-17 alone leaves +$48; Tokyo alone loses. H4: the base is best (+$1,275); New York 13-22 is close (+$1,058, PF 2.43, and the only window positive in-sample at +$304); the overlap-only window keeps 174 trades for +$286. D1: London, New York, overlap and 'Asia off' windows produce zero trades because the D1 signal is evaluated at 01:00 server time; only Tokyo and Sydney windows let the EA trade at all, unchanged from the base. Session filters are therefore not a lever on M1/M5/D1, a regime artefact on M15, and at best a mild, consistent improvement on H1 (New York) and H4 (New York).

| TF | session filter | trades | net $ | PF | maxDD $ | exp R | IS net $ | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | BASE (all sessions) | 34232 | -19017.14 | 0.61 | 19046.70 | -0.28 | -8887.28 | -10129.86 | -0.177 |
| M1 | London 8-17 | 14478 | -7983.68 | 0.62 | 8010.74 | -0.25 | -3744.92 | -4238.76 | -0.169 |
| M1 | New York 13-22 | 14336 | -8397.96 | 0.62 | 8416.39 | -0.24 | -3529.24 | -4868.73 | -0.175 |
| M1 | London + New York 8-22 | 21905 | -12796.56 | 0.61 | 12823.63 | -0.25 | -5499.97 | -7296.59 | -0.178 |
| M1 | Overlap 13-17 | 6909 | -3585.08 | 0.67 | 3630.42 | -0.22 | -1774.18 | -1810.90 | -0.153 |
| M1 | Tokyo 0-9 | 11643 | -5444.48 | 0.66 | 5468.49 | -0.32 | -3046.65 | -2397.83 | -0.169 |
| M1 | Sydney 22-07 | 11139 | -5784.88 | 0.62 | 5808.78 | -0.34 | -3022.15 | -2762.73 | -0.180 |
| M1 | Asia off (8-22 only) | 21905 | -12796.56 | 0.61 | 12823.63 | -0.25 | -5499.97 | -7296.59 | -0.178 |
| M5 | BASE (all sessions) | 7731 | -2240.45 | 0.87 | 2580.98 | -0.12 | -1775.26 | -465.19 | -0.042 |
| M5 | London 8-17 | 3802 | -1168.03 | 0.87 | 1303.93 | -0.09 | -752.32 | -415.71 | -0.049 |
| M5 | New York 13-22 | 3310 | -521.24 | 0.94 | 799.01 | -0.07 | -449.25 | -71.98 | -0.039 |
| M5 | London + New York 8-22 | 5195 | -1280.56 | 0.89 | 1601.61 | -0.10 | -995.43 | -285.12 | -0.047 |
| M5 | Overlap 13-17 | 1917 | -408.71 | 0.92 | 559.99 | -0.05 | -206.13 | -202.57 | -0.036 |
| M5 | Tokyo 0-9 | 2809 | -542.52 | 0.91 | 949.61 | -0.13 | -770.37 | 227.85 | -0.018 |
| M5 | Sydney 22-07 | 2540 | -673.62 | 0.87 | 1077.17 | -0.15 | -749.90 | 76.28 | -0.024 |
| M5 | Asia off (8-22 only) | 5195 | -1280.56 | 0.89 | 1601.61 | -0.10 | -995.43 | -285.12 | -0.047 |
| M15 | BASE (all sessions) | 2941 | -159.90 | 0.98 | 787.05 | -0.04 | -458.43 | 298.53 | -0.004 |
| M15 | London 8-17 | 1681 | -827.92 | 0.83 | 938.19 | -0.07 | -283.20 | -544.71 | -0.046 |
| M15 | New York 13-22 | 1437 | -241.26 | 0.95 | 415.52 | -0.05 | -130.25 | -111.02 | -0.027 |
| M15 | London + New York 8-22 | 2162 | -623.65 | 0.90 | 890.03 | -0.06 | -344.39 | -279.26 | -0.038 |
| M15 | Overlap 13-17 | 951 | -454.47 | 0.86 | 572.24 | -0.06 | -72.68 | -381.79 | -0.037 |
| M15 | Tokyo 0-9 | 1059 | 163.20 | 1.06 | 339.76 | -0.01 | -118.52 | 281.73 | 0.043 |
| M15 | Sydney 22-07 | 979 | 381.28 | 1.14 | 346.73 | -0.02 | -115.88 | 497.16 | 0.043 |
| M15 | Asia off (8-22 only) | 2162 | -623.65 | 0.90 | 890.03 | -0.06 | -344.39 | -279.26 | -0.038 |
| H1 | BASE (all sessions) | 860 | 1113.93 | 1.35 | 201.12 | 0.05 | 3.42 | 1110.50 | 0.085 |
| H1 | London 8-17 | 533 | 48.08 | 1.02 | 320.59 | 0.05 | 141.44 | -93.36 | 0.036 |
| H1 | New York 13-22 | 655 | 979.08 | 1.41 | 199.58 | 0.05 | 129.99 | 849.09 | 0.073 |
| H1 | London + New York 8-22 | 776 | 646.35 | 1.21 | 290.33 | 0.04 | 75.17 | 571.19 | 0.055 |
| H1 | Overlap 13-17 | 391 | 382.48 | 1.27 | 179.11 | 0.08 | 175.40 | 207.09 | 0.078 |
| H1 | Tokyo 0-9 | 255 | -105.91 | 0.91 | 199.74 | 0.05 | -22.16 | -83.75 | 0.042 |
| H1 | Sydney 22-07 | 356 | 556.52 | 1.48 | 171.31 | 0.05 | -90.11 | 646.63 | 0.098 |
| H1 | Asia off (8-22 only) | 776 | 646.35 | 1.21 | 290.33 | 0.04 | 75.17 | 571.19 | 0.055 |
| H4 | BASE (all sessions) | 314 | 1275.38 | 2.14 | 193.74 | 0.10 | 85.71 | 1189.67 | 0.178 |
| H4 | London 8-17 | 250 | 948.36 | 2.07 | 175.37 | 0.14 | 134.94 | 813.42 | 0.186 |
| H4 | New York 13-22 | 260 | 1058.03 | 2.43 | 145.72 | 0.07 | 303.80 | 754.23 | 0.069 |
| H4 | London + New York 8-22 | 308 | 1227.64 | 2.21 | 175.48 | 0.11 | 119.54 | 1108.10 | 0.179 |
| H4 | Overlap 13-17 | 174 | 286.31 | 1.50 | 130.53 | 0.03 | 59.08 | 227.23 | 0.040 |
| H4 | Tokyo 0-9 | 137 | 559.75 | 1.67 | 186.92 | 0.17 | -126.84 | 686.59 | 0.220 |
| H4 | Sydney 22-07 | 80 | 474.02 | 2.00 | 164.90 | 0.08 | -82.02 | 556.04 | 0.158 |
| H4 | Asia off (8-22 only) | 308 | 1227.64 | 2.21 | 175.48 | 0.11 | 119.54 | 1108.10 | 0.179 |
| D1 | BASE (all sessions) | 63 | 594.06 | 3.59 | 179.40 | 0.10 | -29.22 | 623.28 | 0.208 |
| D1 | London 8-17 | 0 | 0.00 | - | 0.00 | - | 0.00 | 0.00 | - |
| D1 | New York 13-22 | 0 | 0.00 | - | 0.00 | - | 0.00 | 0.00 | - |
| D1 | London + New York 8-22 | 0 | 0.00 | - | 0.00 | - | 0.00 | 0.00 | - |
| D1 | Overlap 13-17 | 0 | 0.00 | - | 0.00 | - | 0.00 | 0.00 | - |
| D1 | Tokyo 0-9 | 63 | 594.06 | 3.59 | 179.40 | 0.10 | -29.22 | 623.28 | 0.208 |
| D1 | Sydney 22-07 | 63 | 594.06 | 3.59 | 179.40 | 0.10 | -29.22 | 623.28 | 0.208 |
| D1 | Asia off (8-22 only) | 0 | 0.00 | - | 0.00 | - | 0.00 | 0.00 | - |

## 5. SMA sweeps, 2023-2026 (IS 2023-24 / OOS 2025-26)

Thirteen fast values (5 to 50) with the 200 trend, six trend values (50 to 300) with fast 18 and with the best in-sample fast, eleven popular pairs, and on H1/H4/D1 the fast sweep again under the improved exit: about 50 settings per timeframe, 290 in all, judged on 2023-24 in-sample and 2025-26 out-of-sample. M1: every setting loses in both halves; slower fast averages lose less (50/200 -$15,455 against 18/200 -$19,017) because they trade less. M5: every setting loses over the window; fast 25 to 50 are positive in 2025-26 only (+$85 to +$378) after losing $1,200 or more in 2023-24. M15: no setting is positive in-sample; 18/100 (+$682) and 20/100 (+$708) are the best over the window and both lose $340 to $363 in 2023-24 and win $1,000 in 2025-26. H1: 18 is already near the top of the fast sweep (13 and 14 earn a third to a half of it; 5 to 10 lose); the trend average matters more, 18/150 +$1,551 (PF 1.51) and 18/100 +$1,385 against 18/200 +$1,114, all with in-sample results within $70 of zero. The only settings positive in both halves are 21/55 (+$1,233, +0.016 R in-sample, +0.064 R out) and 13/100 and 13/200, and the shipped 18/200 itself at +0.005 R in-sample. The improved D1 exit (ADX 25 with Chandelier from the first tick) does not transfer to H1: it turns 18/200 into -$171 and every other fast value negative. H4: the fast average is a plateau from 13 to 50 (+$982 to +$1,507 over the window; 18 gives +$1,275) with in-sample expectancy between -0.004 and +0.041 R everywhere; the trend average again matters more, 18/300 +$1,616 (PF 2.52, +0.044 R in-sample) and 18/250 +$1,555, and 18/50 has the best in-sample figure (+0.076 R, +$1,228). With the improved exit every fast value from 13 to 50 is between +$1,167 and +$1,788 with drawdowns of $100 to $240, and 34/200 and 50/200 have the best in-sample numbers of the whole study (+0.091 and +0.097 R), at 286 and 252 trades. D1: fast 10 to 14 beat 18 in the window (+$814 to +$918 against +$594; 63 to 69 trades) and 10/300 is the only setting positive in every calendar year (2023 +$29, 2024 +$27, 2025 +$776, 2026 +$170; 58 trades); with the improved exit, fast 10 to 18 all land at +$1,500 to +$1,600 (PF 8.7 to 12.2, max drawdown $65 to $84). Every D1 cell rests on 50 to 76 trades. Two cautions apply to all of it: the out-of-sample half is the 2025-26 rally that flatters any long-biased breakout rule, and 290 settings were tried, so a handful of good-looking in-sample numbers are expected by chance.

Changing the fast SMA also changes the MA exit and the pending-order invalidation, which use the same average. Trend SMA stays 200 in the fast sweep.

### M1

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 46255 | -26209.09 | 0.50 | 26224.44 | 20.70 | -0.266 | -11483.55 | -0.370 | -14725.54 | -0.174 | 2.19 |
| 8 | 42309 | -22955.80 | 0.56 | 22974.75 | 21.60 | -0.261 | -10582.63 | -0.361 | -12373.17 | -0.168 | 2.53 |
| 9 | 41151 | -22400.15 | 0.56 | 22425.83 | 21.70 | -0.263 | -10325.41 | -0.363 | -12074.75 | -0.169 | 2.62 |
| 10 | 40064 | -21395.05 | 0.58 | 21417.87 | 21.90 | -0.263 | -10070.41 | -0.366 | -11324.64 | -0.166 | 2.70 |
| 13 | 37370 | -20379.71 | 0.59 | 20408.81 | 21.70 | -0.269 | -9566.64 | -0.373 | -10813.07 | -0.169 | 2.91 |
| 14 | 36521 | -19639.27 | 0.60 | 19667.61 | 21.90 | -0.270 | -9347.95 | -0.375 | -10291.33 | -0.168 | 2.97 |
| 18 | 34232 | -19017.14 | 0.61 | 19046.70 | 21.60 | -0.283 | -8887.28 | -0.392 | -10129.86 | -0.177 | 3.18 |
| 20 | 33317 | -18730.44 | 0.62 | 18768.00 | 21.30 | -0.289 | -8860.36 | -0.400 | -9870.08 | -0.181 | 3.27 |
| 21 | 32898 | -18360.86 | 0.62 | 18397.20 | 21.20 | -0.293 | -8779.73 | -0.404 | -9581.13 | -0.185 | 3.30 |
| 25 | 31377 | -17682.97 | 0.63 | 17713.14 | 21.10 | -0.307 | -8450.55 | -0.419 | -9232.41 | -0.199 | 3.43 |
| 30 | 30122 | -17125.86 | 0.64 | 17153.40 | 20.80 | -0.319 | -8031.71 | -0.429 | -9094.15 | -0.215 | 3.53 |
| 34 | 29345 | -16468.32 | 0.65 | 16491.98 | 20.60 | -0.329 | -7620.44 | -0.435 | -8847.88 | -0.230 | 3.60 |
| 50 | 27639 | -15454.87 | 0.66 | 15487.74 | 19.90 | -0.368 | -7081.35 | -0.472 | -8373.52 | -0.275 | 3.75 |

Trend SMA (fast 18, and fast 8 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 37622 | -20736.20 | 0.61 | 20773.77 | -0.278 | -9700.60 | -0.387 | -11035.60 | -0.174 |
| 8/50 | 45456 | -24616.78 | 0.56 | 24635.53 | -0.247 | -11159.51 | -0.344 | -13457.27 | -0.157 |
| 18/100 | 35601 | -19744.78 | 0.61 | 19785.30 | -0.278 | -9201.55 | -0.385 | -10543.23 | -0.175 |
| 8/100 | 43735 | -23784.80 | 0.56 | 23808.14 | -0.255 | -10922.77 | -0.354 | -12862.03 | -0.164 |
| 18/150 | 34691 | -19547.21 | 0.61 | 19587.21 | -0.281 | -8895.92 | -0.385 | -10651.29 | -0.180 |
| 8/150 | 42798 | -23364.51 | 0.55 | 23383.27 | -0.259 | -10777.08 | -0.358 | -12587.44 | -0.167 |
| 18/200 | 34232 | -19017.14 | 0.61 | 19046.70 | -0.283 | -8887.28 | -0.392 | -10129.86 | -0.177 |
| 8/200 | 42309 | -22955.80 | 0.56 | 22974.75 | -0.261 | -10582.63 | -0.361 | -12373.17 | -0.168 |
| 18/250 | 33768 | -18342.67 | 0.62 | 18362.95 | -0.282 | -8779.20 | -0.392 | -9563.48 | -0.175 |
| 8/250 | 41890 | -22814.76 | 0.56 | 22832.77 | -0.261 | -10454.98 | -0.362 | -12359.78 | -0.169 |
| 18/300 | 33434 | -18224.38 | 0.62 | 18247.66 | -0.281 | -8669.75 | -0.390 | -9554.63 | -0.174 |
| 8/300 | 41488 | -22406.99 | 0.56 | 22421.02 | -0.261 | -10293.12 | -0.363 | -12113.86 | -0.167 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 47256 | -26151.26 | 0.56 | 26165.31 | -0.247 | -11710.78 | -0.341 | -14440.49 | -0.159 |
| 10/50 | 43424 | -24105.91 | 0.56 | 24138.60 | -0.255 | -10833.39 | -0.353 | -13272.52 | -0.164 |
| 20/50 | 36730 | -20242.72 | 0.62 | 20280.25 | -0.288 | -9820.70 | -0.401 | -10422.03 | -0.178 |
| 20/100 | 34712 | -19290.40 | 0.62 | 19342.01 | -0.286 | -9167.39 | -0.395 | -10123.02 | -0.180 |
| 21/55 | 35995 | -19840.87 | 0.62 | 19876.91 | -0.289 | -9530.70 | -0.399 | -10310.18 | -0.182 |
| 50/200 | 27639 | -15454.87 | 0.66 | 15487.74 | -0.368 | -7081.35 | -0.472 | -8373.52 | -0.275 |
| 20/200 | 33317 | -18730.44 | 0.62 | 18768.00 | -0.289 | -8860.36 | -0.400 | -9870.08 | -0.181 |
| 10/100 | 41482 | -22501.01 | 0.57 | 22539.58 | -0.261 | -10367.77 | -0.358 | -12133.24 | -0.169 |
| 34/144 | 30013 | -17108.07 | 0.64 | 17143.91 | -0.335 | -7769.02 | -0.439 | -9339.06 | -0.237 |
| 13/48 | 40821 | -22069.84 | 0.59 | 22104.41 | -0.262 | -10272.96 | -0.364 | -11796.88 | -0.165 |
| 18/200 | 34232 | -19017.14 | 0.61 | 19046.70 | -0.283 | -8887.28 | -0.392 | -10129.86 | -0.177 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

None.

### M5

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 10852 | -4895.42 | 0.74 | 4952.34 | 25.30 | -0.132 | -2683.16 | -0.188 | -2212.26 | -0.075 | 4.38 |
| 8 | 9691 | -3451.84 | 0.81 | 3496.47 | 25.70 | -0.117 | -2236.83 | -0.175 | -1215.01 | -0.057 | 5.07 |
| 9 | 9367 | -3055.48 | 0.83 | 3282.02 | 26.00 | -0.114 | -2196.34 | -0.178 | -859.14 | -0.049 | 5.24 |
| 10 | 9115 | -3134.84 | 0.83 | 3248.04 | 25.90 | -0.116 | -2220.83 | -0.178 | -914.01 | -0.053 | 5.42 |
| 13 | 8509 | -2765.82 | 0.84 | 3183.84 | 26.00 | -0.118 | -2054.11 | -0.181 | -711.71 | -0.057 | 5.85 |
| 14 | 8307 | -2478.70 | 0.86 | 2876.17 | 26.00 | -0.119 | -1955.98 | -0.184 | -522.71 | -0.056 | 5.95 |
| 18 | 7731 | -2240.45 | 0.87 | 2580.98 | 26.30 | -0.115 | -1775.26 | -0.190 | -465.19 | -0.042 | 6.40 |
| 20 | 7497 | -1917.39 | 0.89 | 2175.89 | 26.70 | -0.109 | -1605.26 | -0.185 | -312.13 | -0.036 | 6.56 |
| 21 | 7369 | -1568.64 | 0.91 | 1939.43 | 27.00 | -0.106 | -1465.28 | -0.175 | -103.36 | -0.040 | 6.62 |
| 25 | 7129 | -1362.20 | 0.92 | 1920.64 | 26.50 | -0.110 | -1446.72 | -0.175 | 84.52 | -0.050 | 6.77 |
| 30 | 6862 | -1020.68 | 0.94 | 1627.23 | 26.40 | -0.112 | -1200.22 | -0.172 | 179.54 | -0.058 | 7.04 |
| 34 | 6755 | -831.70 | 0.95 | 1582.50 | 26.40 | -0.117 | -1210.16 | -0.185 | 378.46 | -0.056 | 7.12 |
| 50 | 6637 | -863.97 | 0.95 | 1727.56 | 26.00 | -0.146 | -1224.34 | -0.218 | 360.37 | -0.084 | 7.18 |

Trend SMA (fast 18, and fast 30 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 8648 | -3219.84 | 0.83 | 3464.28 | -0.135 | -2123.17 | -0.199 | -1096.67 | -0.071 |
| 30/50 | 7940 | -3162.56 | 0.83 | 3215.85 | -0.152 | -1739.13 | -0.208 | -1423.44 | -0.100 |
| 18/100 | 8109 | -2699.12 | 0.85 | 3055.85 | -0.123 | -1862.64 | -0.184 | -836.48 | -0.063 |
| 30/100 | 7311 | -2205.85 | 0.88 | 2235.67 | -0.128 | -1378.08 | -0.176 | -827.77 | -0.085 |
| 18/150 | 7888 | -2187.14 | 0.87 | 2796.03 | -0.120 | -1820.85 | -0.188 | -366.29 | -0.054 |
| 30/150 | 7023 | -1806.89 | 0.89 | 1912.25 | -0.123 | -1381.26 | -0.176 | -425.63 | -0.076 |
| 18/200 | 7731 | -2240.45 | 0.87 | 2580.98 | -0.115 | -1775.26 | -0.190 | -465.19 | -0.042 |
| 30/200 | 6862 | -1020.68 | 0.94 | 1627.23 | -0.112 | -1200.22 | -0.172 | 179.54 | -0.058 |
| 18/250 | 7670 | -1994.91 | 0.88 | 2360.09 | -0.112 | -1706.43 | -0.189 | -288.48 | -0.036 |
| 30/250 | 6797 | -1320.38 | 0.92 | 1735.22 | -0.108 | -1290.38 | -0.179 | -30.01 | -0.044 |
| 18/300 | 7636 | -2060.61 | 0.88 | 2390.99 | -0.113 | -1570.86 | -0.187 | -489.75 | -0.041 |
| 30/300 | 6746 | -1061.33 | 0.93 | 1668.82 | -0.108 | -1108.13 | -0.171 | 46.80 | -0.051 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 10934 | -4634.83 | 0.78 | 4684.05 | -0.114 | -2621.66 | -0.167 | -2013.17 | -0.060 |
| 10/50 | 9960 | -3989.89 | 0.80 | 4011.01 | -0.121 | -2453.91 | -0.179 | -1535.98 | -0.061 |
| 20/50 | 8378 | -2770.57 | 0.85 | 3120.61 | -0.135 | -2042.63 | -0.206 | -727.94 | -0.065 |
| 20/100 | 7838 | -2649.44 | 0.85 | 2742.21 | -0.110 | -1646.14 | -0.167 | -1003.30 | -0.056 |
| 21/55 | 8199 | -2398.33 | 0.87 | 2750.51 | -0.123 | -1764.90 | -0.186 | -633.43 | -0.062 |
| 50/200 | 6637 | -863.97 | 0.95 | 1727.56 | -0.146 | -1224.34 | -0.218 | 360.37 | -0.084 |
| 20/200 | 7497 | -1917.39 | 0.89 | 2175.89 | -0.109 | -1605.26 | -0.185 | -312.13 | -0.036 |
| 10/100 | 9493 | -3687.05 | 0.81 | 3702.52 | -0.121 | -2281.30 | -0.179 | -1405.75 | -0.061 |
| 34/144 | 6941 | -1650.84 | 0.90 | 1861.06 | -0.129 | -1371.43 | -0.183 | -279.42 | -0.082 |
| 13/48 | 9339 | -3325.28 | 0.83 | 3762.40 | -0.126 | -2348.11 | -0.191 | -977.18 | -0.060 |
| 18/200 | 7731 | -2240.45 | 0.87 | 2580.98 | -0.115 | -1775.26 | -0.190 | -465.19 | -0.042 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

None.

### M15

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 3955 | -1255.13 | 0.87 | 1344.28 | 29.60 | -0.068 | -689.79 | -0.108 | -565.35 | -0.030 | 6.99 |
| 8 | 3568 | -1078.61 | 0.88 | 1308.84 | 30.20 | -0.059 | -723.09 | -0.101 | -355.52 | -0.020 | 7.87 |
| 9 | 3475 | -964.24 | 0.89 | 1107.35 | 30.00 | -0.055 | -758.89 | -0.101 | -205.34 | -0.011 | 8.19 |
| 10 | 3418 | -1038.54 | 0.89 | 1138.96 | 29.90 | -0.054 | -686.37 | -0.094 | -352.17 | -0.017 | 8.47 |
| 13 | 3180 | -674.07 | 0.92 | 860.25 | 30.40 | -0.047 | -647.05 | -0.091 | -27.01 | -0.008 | 9.14 |
| 14 | 3117 | -794.09 | 0.91 | 932.39 | 30.40 | -0.046 | -593.34 | -0.086 | -200.74 | -0.012 | 9.34 |
| 18 | 2941 | -159.90 | 0.98 | 787.05 | 31.30 | -0.045 | -458.43 | -0.093 | 298.53 | -0.004 | 9.81 |
| 20 | 2889 | -167.23 | 0.98 | 788.20 | 31.40 | -0.048 | -487.90 | -0.097 | 320.67 | -0.005 | 9.92 |
| 21 | 2867 | -306.20 | 0.96 | 806.21 | 31.10 | -0.049 | -470.94 | -0.091 | 164.75 | -0.013 | 9.99 |
| 25 | 2740 | -329.61 | 0.96 | 633.52 | 31.60 | -0.047 | -503.95 | -0.110 | 174.34 | 0.007 | 10.30 |
| 30 | 2653 | -38.29 | 0.99 | 572.95 | 31.60 | -0.052 | -419.63 | -0.117 | 381.34 | 0.003 | 10.36 |
| 34 | 2638 | -288.86 | 0.96 | 751.76 | 31.90 | -0.064 | -486.38 | -0.143 | 197.52 | 0.002 | 10.42 |
| 50 | 2631 | 180.90 | 1.02 | 622.90 | 32.10 | -0.063 | -472.23 | -0.132 | 653.13 | -0.004 | 10.25 |

Trend SMA (fast 18, and fast 14 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 3269 | 313.55 | 1.03 | 804.16 | -0.048 | -675.25 | -0.111 | 988.80 | 0.006 |
| 14/50 | 3424 | -319.54 | 0.97 | 813.52 | -0.041 | -605.58 | -0.089 | 286.04 | 0.002 |
| 18/100 | 3048 | 682.27 | 1.08 | 554.32 | -0.033 | -340.03 | -0.081 | 1022.31 | 0.010 |
| 14/100 | 3220 | 243.55 | 1.03 | 622.33 | -0.037 | -383.34 | -0.087 | 626.89 | 0.007 |
| 18/150 | 3012 | 80.38 | 1.01 | 717.47 | -0.046 | -508.17 | -0.099 | 588.55 | -0.001 |
| 14/150 | 3169 | -300.99 | 0.96 | 819.69 | -0.047 | -535.37 | -0.093 | 234.38 | -0.005 |
| 18/200 | 2941 | -159.90 | 0.98 | 787.05 | -0.045 | -458.43 | -0.093 | 298.53 | -0.004 |
| 14/200 | 3117 | -794.09 | 0.91 | 932.39 | -0.046 | -593.34 | -0.086 | -200.74 | -0.012 |
| 18/250 | 2885 | -199.85 | 0.98 | 816.42 | -0.050 | -603.21 | -0.107 | 403.37 | 0.000 |
| 14/250 | 3085 | -884.13 | 0.90 | 1011.07 | -0.055 | -679.59 | -0.102 | -204.54 | -0.014 |
| 18/300 | 2879 | -277.89 | 0.97 | 759.73 | -0.047 | -601.03 | -0.105 | 323.14 | 0.003 |
| 14/300 | 3080 | -837.69 | 0.91 | 926.79 | -0.052 | -656.61 | -0.097 | -181.08 | -0.013 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 4000 | -971.63 | 0.91 | 1070.96 | -0.045 | -722.24 | -0.078 | -249.39 | -0.014 |
| 10/50 | 3680 | -620.31 | 0.94 | 857.60 | -0.042 | -595.44 | -0.073 | -24.87 | -0.013 |
| 20/50 | 3221 | -48.37 | 0.99 | 750.57 | -0.053 | -569.72 | -0.097 | 521.35 | -0.015 |
| 20/100 | 2975 | 707.75 | 1.08 | 570.86 | -0.029 | -363.25 | -0.087 | 1070.99 | 0.022 |
| 21/55 | 3150 | -194.90 | 0.98 | 962.58 | -0.067 | -719.19 | -0.117 | 524.30 | -0.023 |
| 50/200 | 2631 | 180.90 | 1.02 | 622.90 | -0.063 | -472.23 | -0.132 | 653.13 | -0.004 |
| 20/200 | 2889 | -167.23 | 0.98 | 788.20 | -0.048 | -487.90 | -0.097 | 320.67 | -0.005 |
| 10/100 | 3484 | -228.28 | 0.97 | 729.80 | -0.039 | -500.10 | -0.081 | 271.82 | -0.001 |
| 34/144 | 2715 | -36.88 | 1.00 | 758.66 | -0.051 | -319.94 | -0.103 | 283.06 | -0.008 |
| 13/48 | 3495 | -424.39 | 0.95 | 901.26 | -0.044 | -711.52 | -0.088 | 287.13 | -0.004 |
| 18/200 | 2941 | -159.90 | 0.98 | 787.05 | -0.045 | -458.43 | -0.093 | 298.53 | -0.004 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

None.

### H1

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 1124 | -400.15 | 0.90 | 484.80 | 34.10 | -0.002 | -185.24 | -0.028 | -214.91 | 0.020 | 11.09 |
| 8 | 1037 | -52.73 | 0.99 | 583.81 | 37.00 | 0.008 | -133.29 | -0.025 | 80.56 | 0.036 | 12.87 |
| 9 | 1026 | -255.63 | 0.94 | 482.85 | 37.40 | -0.004 | -202.92 | -0.037 | -52.70 | 0.023 | 13.29 |
| 10 | 1015 | -171.56 | 0.96 | 494.51 | 36.70 | -0.005 | -164.78 | -0.030 | -6.78 | 0.016 | 13.69 |
| 13 | 950 | 363.62 | 1.10 | 377.46 | 36.50 | 0.035 | -74.81 | 0.010 | 438.43 | 0.055 | 14.40 |
| 14 | 932 | 616.63 | 1.17 | 361.70 | 37.00 | 0.030 | -48.46 | -0.002 | 665.09 | 0.055 | 14.52 |
| 18 | 860 | 1113.93 | 1.35 | 201.12 | 39.40 | 0.048 | 3.42 | 0.005 | 1110.50 | 0.085 | 15.22 |
| 20 | 858 | 902.19 | 1.28 | 258.16 | 38.90 | 0.037 | -28.18 | -0.018 | 930.38 | 0.084 | 15.63 |
| 21 | 850 | 1016.72 | 1.32 | 293.75 | 39.50 | 0.051 | -11.37 | -0.005 | 1028.09 | 0.100 | 15.72 |
| 25 | 851 | 858.18 | 1.26 | 285.14 | 39.60 | 0.055 | -39.42 | -0.024 | 897.60 | 0.123 | 15.65 |
| 30 | 845 | 725.11 | 1.22 | 340.05 | 40.00 | 0.040 | -39.39 | -0.049 | 764.49 | 0.117 | 15.62 |
| 34 | 857 | 589.07 | 1.17 | 304.34 | 38.70 | 0.011 | -18.90 | -0.047 | 607.98 | 0.060 | 15.40 |
| 50 | 818 | 966.69 | 1.31 | 350.56 | 39.00 | 0.024 | 154.72 | -0.064 | 811.96 | 0.101 | 15.69 |

Trend SMA (fast 18, and fast 13 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 920 | 1047.93 | 1.31 | 362.54 | 0.019 | -38.62 | -0.009 | 1086.55 | 0.042 |
| 13/50 | 982 | 655.54 | 1.18 | 255.90 | 0.013 | -67.66 | -0.012 | 723.20 | 0.033 |
| 18/100 | 875 | 1385.08 | 1.42 | 270.21 | 0.051 | 12.64 | -0.000 | 1372.45 | 0.093 |
| 13/100 | 951 | 571.90 | 1.16 | 334.80 | 0.031 | 4.69 | 0.010 | 567.22 | 0.047 |
| 18/150 | 865 | 1551.42 | 1.51 | 238.73 | 0.048 | 65.46 | -0.002 | 1485.97 | 0.092 |
| 13/150 | 949 | 794.89 | 1.23 | 253.82 | 0.033 | -3.26 | -0.002 | 798.15 | 0.062 |
| 18/200 | 860 | 1113.93 | 1.35 | 201.12 | 0.048 | 3.42 | 0.005 | 1110.50 | 0.085 |
| 13/200 | 950 | 363.62 | 1.10 | 377.46 | 0.035 | -74.81 | 0.010 | 438.43 | 0.055 |
| 18/250 | 860 | 1191.51 | 1.39 | 231.34 | 0.046 | -51.94 | -0.026 | 1243.45 | 0.109 |
| 13/250 | 950 | 372.25 | 1.10 | 313.35 | 0.031 | -140.45 | -0.021 | 512.70 | 0.074 |
| 18/300 | 855 | 1125.76 | 1.37 | 246.59 | 0.043 | -90.65 | -0.013 | 1216.40 | 0.091 |
| 13/300 | 941 | 318.56 | 1.09 | 357.97 | 0.024 | -187.43 | -0.016 | 505.99 | 0.058 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 1168 | -478.07 | 0.90 | 547.56 | -0.007 | -87.51 | -0.013 | -390.55 | -0.003 |
| 10/50 | 1030 | -33.91 | 0.99 | 416.39 | -0.017 | -249.58 | -0.045 | 215.67 | 0.007 |
| 20/50 | 923 | 1007.95 | 1.29 | 341.48 | 0.021 | -19.59 | -0.008 | 1027.54 | 0.046 |
| 20/100 | 869 | 1268.69 | 1.38 | 274.90 | 0.053 | -49.31 | -0.011 | 1318.00 | 0.107 |
| 21/55 | 898 | 1233.09 | 1.38 | 270.09 | 0.042 | 88.21 | 0.016 | 1144.88 | 0.064 |
| 50/200 | 818 | 966.69 | 1.31 | 350.56 | 0.024 | 154.72 | -0.064 | 811.96 | 0.101 |
| 20/200 | 858 | 902.19 | 1.28 | 258.16 | 0.037 | -28.18 | -0.018 | 930.38 | 0.084 |
| 10/100 | 1010 | 166.33 | 1.04 | 349.98 | -0.004 | -120.43 | -0.032 | 286.76 | 0.018 |
| 34/144 | 877 | 1079.05 | 1.32 | 283.03 | 0.044 | 68.10 | -0.013 | 1010.95 | 0.092 |
| 13/48 | 981 | 658.80 | 1.18 | 323.56 | 0.011 | -92.19 | -0.015 | 751.00 | 0.032 |
| 18/200 | 860 | 1113.93 | 1.35 | 201.12 | 0.048 | 3.42 | 0.005 | 1110.50 | 0.085 |

Fast SMA with the improved exit (ADX 25 + Chandelier from the first tick), trend 200:

| fast | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 831 | -951.81 | 0.67 | 975.22 | -0.022 | -80.09 | -0.019 | -871.73 | -0.024 |
| 8 | 796 | -730.54 | 0.75 | 838.49 | -0.022 | -79.57 | -0.038 | -650.97 | -0.009 |
| 9 | 785 | -876.68 | 0.72 | 881.10 | -0.031 | -120.68 | -0.038 | -755.99 | -0.026 |
| 10 | 782 | -856.45 | 0.72 | 859.67 | -0.034 | -164.99 | -0.040 | -691.46 | -0.028 |
| 13 | 742 | -566.66 | 0.81 | 763.76 | -0.000 | -119.94 | -0.008 | -446.72 | 0.006 |
| 14 | 728 | -407.30 | 0.86 | 678.85 | 0.006 | -36.81 | 0.001 | -370.49 | 0.009 |
| 18 | 689 | -171.48 | 0.94 | 495.79 | 0.026 | 21.19 | 0.029 | -192.67 | 0.024 |
| 20 | 694 | -205.36 | 0.92 | 486.28 | 0.003 | -6.88 | -0.009 | -198.48 | 0.012 |
| 21 | 689 | -106.32 | 0.96 | 476.47 | 0.012 | -6.84 | -0.004 | -99.47 | 0.026 |
| 25 | 680 | -132.80 | 0.95 | 421.11 | 0.022 | 10.46 | 0.008 | -143.27 | 0.034 |
| 30 | 677 | -159.34 | 0.94 | 420.60 | 0.008 | -21.86 | -0.033 | -137.48 | 0.043 |
| 34 | 675 | -142.52 | 0.94 | 439.33 | -0.006 | -37.51 | -0.045 | -105.02 | 0.028 |
| 50 | 672 | -205.69 | 0.92 | 549.98 | -0.005 | 78.06 | -0.040 | -283.75 | 0.025 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

| fast/trend | trades | net $ | PF | maxDD $ | IS exp R | OOS exp R | neighbours +OOS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 21/55 | 898 | 1233.09 | 1.38 | 270.09 | 0.016 | 0.064 | - |
| 13/200 | 950 | 363.62 | 1.10 | 377.46 | 0.010 | 0.055 | 2/2 |
| 13/100 | 951 | 571.90 | 1.16 | 334.80 | 0.010 | 0.047 | - |
| 18/200 | 860 | 1113.93 | 1.35 | 201.12 | 0.005 | 0.085 | 2/2 |

### H4

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 360 | 1121.10 | 1.88 | 159.93 | 44.20 | 0.056 | 21.38 | 0.032 | 1099.72 | 0.081 | 17.90 |
| 8 | 343 | 791.64 | 1.64 | 193.85 | 44.90 | 0.067 | 57.27 | 0.034 | 734.37 | 0.101 | 21.14 |
| 9 | 339 | 803.16 | 1.65 | 209.91 | 45.10 | 0.074 | 97.30 | 0.038 | 705.86 | 0.109 | 21.98 |
| 10 | 339 | 584.16 | 1.42 | 251.43 | 44.80 | 0.068 | 91.50 | 0.041 | 492.67 | 0.094 | 22.43 |
| 13 | 320 | 985.88 | 1.73 | 238.33 | 43.40 | 0.065 | 51.38 | -0.003 | 934.50 | 0.124 | 23.24 |
| 14 | 322 | 982.19 | 1.73 | 215.66 | 44.10 | 0.070 | 35.65 | 0.010 | 946.54 | 0.124 | 22.98 |
| 18 | 314 | 1275.38 | 2.14 | 193.74 | 45.50 | 0.104 | 85.71 | 0.019 | 1189.67 | 0.178 | 22.94 |
| 20 | 315 | 1101.16 | 1.92 | 206.84 | 44.10 | 0.101 | 45.73 | 0.010 | 1055.43 | 0.185 | 23.17 |
| 21 | 313 | 1047.86 | 1.82 | 225.20 | 44.10 | 0.100 | 46.10 | 0.013 | 1001.76 | 0.180 | 23.55 |
| 25 | 301 | 1032.53 | 1.86 | 234.61 | 44.50 | 0.100 | 157.39 | 0.035 | 875.14 | 0.158 | 24.59 |
| 30 | 285 | 1128.34 | 1.91 | 241.63 | 45.60 | 0.097 | 78.06 | -0.002 | 1050.27 | 0.198 | 25.84 |
| 34 | 286 | 1393.11 | 2.29 | 226.58 | 46.20 | 0.093 | 44.39 | -0.004 | 1348.72 | 0.193 | 25.52 |
| 50 | 252 | 1507.30 | 2.29 | 171.88 | 42.90 | 0.122 | 130.60 | 0.018 | 1376.70 | 0.222 | 27.17 |

Trend SMA (fast 18, and fast 10 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 326 | 1228.41 | 1.90 | 241.21 | 0.130 | 171.71 | 0.076 | 1056.70 | 0.183 |
| 10/50 | 364 | 359.01 | 1.23 | 200.57 | 0.060 | 35.46 | 0.038 | 323.54 | 0.080 |
| 18/100 | 308 | 1385.16 | 2.16 | 192.35 | 0.095 | 9.96 | 0.000 | 1375.20 | 0.191 |
| 10/100 | 346 | 590.29 | 1.45 | 214.99 | 0.062 | 72.62 | 0.035 | 517.67 | 0.089 |
| 18/150 | 309 | 1199.80 | 2.04 | 223.42 | 0.096 | 65.77 | -0.005 | 1134.03 | 0.186 |
| 10/150 | 326 | 746.06 | 1.58 | 292.00 | 0.079 | 106.40 | 0.048 | 639.66 | 0.108 |
| 18/200 | 314 | 1275.38 | 2.14 | 193.74 | 0.104 | 85.71 | 0.019 | 1189.67 | 0.178 |
| 10/200 | 339 | 584.16 | 1.42 | 251.43 | 0.068 | 91.50 | 0.041 | 492.67 | 0.094 |
| 18/250 | 296 | 1554.89 | 2.51 | 218.57 | 0.132 | 150.95 | 0.038 | 1403.93 | 0.213 |
| 10/250 | 336 | 677.48 | 1.52 | 203.41 | 0.068 | -0.81 | 0.024 | 678.29 | 0.109 |
| 18/300 | 297 | 1616.26 | 2.52 | 238.54 | 0.138 | 132.23 | 0.044 | 1484.03 | 0.222 |
| 10/300 | 330 | 843.37 | 1.68 | 203.41 | 0.088 | 100.98 | 0.059 | 742.40 | 0.115 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 373 | 608.71 | 1.42 | 183.32 | 0.055 | 130.03 | 0.023 | 478.68 | 0.084 |
| 10/50 | 364 | 359.01 | 1.23 | 200.57 | 0.060 | 35.46 | 0.038 | 323.54 | 0.080 |
| 20/50 | 335 | 961.03 | 1.68 | 204.20 | 0.091 | 51.40 | 0.011 | 909.63 | 0.174 |
| 20/100 | 304 | 1352.94 | 2.12 | 203.72 | 0.095 | -25.31 | -0.015 | 1378.26 | 0.209 |
| 21/55 | 326 | 753.22 | 1.46 | 231.19 | 0.094 | 42.12 | 0.016 | 711.10 | 0.177 |
| 50/200 | 252 | 1507.30 | 2.29 | 171.88 | 0.122 | 130.60 | 0.018 | 1376.70 | 0.222 |
| 20/200 | 315 | 1101.16 | 1.92 | 206.84 | 0.101 | 45.73 | 0.010 | 1055.43 | 0.185 |
| 10/100 | 346 | 590.29 | 1.45 | 214.99 | 0.062 | 72.62 | 0.035 | 517.67 | 0.089 |
| 34/144 | 300 | 1352.17 | 2.29 | 182.48 | 0.068 | 82.82 | -0.042 | 1269.35 | 0.179 |
| 13/48 | 351 | 372.55 | 1.20 | 393.24 | 0.047 | 22.16 | 0.008 | 350.40 | 0.080 |
| 18/200 | 314 | 1275.38 | 2.14 | 193.74 | 0.104 | 85.71 | 0.019 | 1189.67 | 0.178 |

Fast SMA with the improved exit (ADX 25 + Chandelier from the first tick), trend 200:

| fast | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 258 | 1258.18 | 2.20 | 138.82 | 0.070 | 88.61 | 0.040 | 1169.57 | 0.098 |
| 8 | 252 | 949.57 | 2.00 | 220.02 | 0.064 | 103.42 | 0.024 | 846.15 | 0.097 |
| 9 | 250 | 873.69 | 1.91 | 220.02 | 0.061 | 127.49 | 0.029 | 746.20 | 0.087 |
| 10 | 250 | 668.58 | 1.63 | 312.59 | 0.054 | 129.11 | 0.032 | 539.47 | 0.071 |
| 13 | 237 | 1168.47 | 2.37 | 239.52 | 0.075 | 120.09 | 0.011 | 1048.38 | 0.126 |
| 14 | 240 | 1166.95 | 2.30 | 239.52 | 0.087 | 165.63 | 0.056 | 1001.32 | 0.111 |
| 18 | 228 | 1503.94 | 3.00 | 129.33 | 0.088 | 71.52 | 0.012 | 1432.42 | 0.150 |
| 20 | 226 | 1380.98 | 2.71 | 153.30 | 0.088 | 62.26 | 0.021 | 1318.72 | 0.144 |
| 21 | 226 | 1309.86 | 2.50 | 163.44 | 0.083 | 52.45 | 0.017 | 1257.42 | 0.137 |
| 25 | 226 | 1304.87 | 2.65 | 130.19 | 0.087 | 71.48 | 0.047 | 1233.40 | 0.118 |
| 30 | 217 | 1323.42 | 2.66 | 129.33 | 0.092 | 62.43 | 0.045 | 1260.99 | 0.131 |
| 34 | 212 | 1657.62 | 3.50 | 103.52 | 0.105 | 96.27 | 0.091 | 1561.34 | 0.117 |
| 50 | 188 | 1788.00 | 3.29 | 159.79 | 0.142 | 126.51 | 0.097 | 1661.49 | 0.182 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

| fast/trend | trades | net $ | PF | maxDD $ | IS exp R | OOS exp R | neighbours +OOS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 326 | 1228.41 | 1.90 | 241.21 | 0.076 | 0.183 | - |
| 10/300 | 330 | 843.37 | 1.68 | 203.41 | 0.059 | 0.115 | - |
| 10/150 | 326 | 746.06 | 1.58 | 292.00 | 0.048 | 0.108 | - |
| 18/300 | 297 | 1616.26 | 2.52 | 238.54 | 0.044 | 0.222 | - |
| 10/200 | 339 | 584.16 | 1.42 | 251.43 | 0.041 | 0.094 | 2/2 |

### D1

Fast SMA (trend 200):

| fast | trades | net $ | PF | maxDD $ | win % | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R | giveback avg $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 76 | 459.52 | 2.79 | 125.24 | 47.40 | 0.038 | -107.45 | -0.050 | 566.98 | 0.160 | 40.78 |
| 8 | 74 | 573.64 | 2.37 | 172.22 | 43.20 | 0.071 | -83.74 | 0.004 | 657.38 | 0.145 | 46.84 |
| 9 | 74 | 584.17 | 2.41 | 163.61 | 43.20 | 0.071 | -73.22 | 0.004 | 657.38 | 0.145 | 46.70 |
| 10 | 69 | 918.12 | 3.49 | 163.28 | 43.50 | 0.135 | -28.18 | 0.030 | 946.30 | 0.250 | 48.66 |
| 13 | 64 | 898.23 | 4.05 | 200.02 | 39.10 | 0.147 | -67.93 | 0.019 | 966.16 | 0.292 | 53.07 |
| 14 | 63 | 813.54 | 3.64 | 200.02 | 38.10 | 0.119 | -112.17 | -0.004 | 925.71 | 0.263 | 54.97 |
| 18 | 63 | 594.06 | 3.59 | 179.40 | 42.90 | 0.100 | -29.22 | 0.008 | 623.28 | 0.208 | 57.92 |
| 20 | 68 | 546.68 | 2.97 | 204.50 | 41.20 | 0.060 | -60.72 | -0.047 | 607.40 | 0.174 | 50.33 |
| 21 | 68 | 435.96 | 2.16 | 204.50 | 41.20 | 0.045 | -143.50 | -0.069 | 579.47 | 0.165 | 51.45 |
| 25 | 69 | 377.40 | 1.91 | 197.06 | 39.10 | 0.030 | -178.65 | -0.072 | 556.05 | 0.155 | 52.44 |
| 30 | 62 | 544.70 | 2.52 | 234.18 | 41.90 | 0.083 | -177.52 | -0.092 | 722.22 | 0.341 | 55.70 |
| 34 | 63 | 577.77 | 2.77 | 197.64 | 41.30 | 0.098 | -144.46 | -0.061 | 722.22 | 0.341 | 53.68 |
| 50 | 60 | 560.75 | 2.37 | 194.82 | 40.00 | 0.094 | -192.38 | -0.082 | 753.13 | 0.398 | 54.32 |

Trend SMA (fast 18, and fast 10 = best IS):

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18/50 | 63 | 437.67 | 2.30 | 225.12 | 0.062 | -186.40 | -0.076 | 624.07 | 0.173 |
| 10/50 | 70 | 955.01 | 4.14 | 138.85 | 0.121 | 7.91 | 0.006 | 947.09 | 0.229 |
| 18/100 | 66 | 592.77 | 3.56 | 181.48 | 0.089 | -31.30 | -0.006 | 624.07 | 0.189 |
| 10/100 | 74 | 872.29 | 3.10 | 163.28 | 0.110 | -74.80 | -0.002 | 947.09 | 0.243 |
| 18/150 | 66 | 585.23 | 3.45 | 189.02 | 0.087 | -38.84 | -0.010 | 624.07 | 0.189 |
| 10/150 | 73 | 839.46 | 2.87 | 171.95 | 0.100 | -107.63 | -0.024 | 947.09 | 0.243 |
| 18/200 | 63 | 594.06 | 3.59 | 179.40 | 0.100 | -29.22 | 0.008 | 623.28 | 0.208 |
| 10/200 | 69 | 918.12 | 3.49 | 163.28 | 0.135 | -28.18 | 0.030 | 946.30 | 0.250 |
| 18/250 | 51 | 705.51 | 7.01 | 67.95 | 0.140 | 82.23 | 0.038 | 623.28 | 0.275 |
| 10/250 | 64 | 937.36 | 3.69 | 163.28 | 0.145 | -8.75 | 0.031 | 946.10 | 0.266 |
| 18/300 | 55 | 726.93 | 7.19 | 59.27 | 0.133 | 103.65 | 0.043 | 623.28 | 0.242 |
| 10/300 | 58 | 1002.01 | 4.12 | 163.28 | 0.174 | 55.91 | 0.059 | 946.10 | 0.306 |

Popular pairs:

| fast/trend | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9/21 | 74 | 615.81 | 2.60 | 144.44 | 0.068 | -82.18 | -0.014 | 697.99 | 0.140 |
| 10/50 | 70 | 955.01 | 4.14 | 138.85 | 0.121 | 7.91 | 0.006 | 947.09 | 0.229 |
| 20/50 | 67 | 458.04 | 2.44 | 178.99 | 0.052 | -150.15 | -0.083 | 608.19 | 0.144 |
| 20/100 | 74 | 567.49 | 3.20 | 184.48 | 0.062 | -40.70 | -0.032 | 608.19 | 0.151 |
| 21/55 | 64 | 481.56 | 2.38 | 178.99 | 0.056 | -164.20 | -0.086 | 645.76 | 0.166 |
| 50/200 | 60 | 560.75 | 2.37 | 194.82 | 0.094 | -192.38 | -0.082 | 753.13 | 0.398 |
| 20/200 | 68 | 546.68 | 2.97 | 204.50 | 0.060 | -60.72 | -0.047 | 607.40 | 0.174 |
| 10/100 | 74 | 872.29 | 3.10 | 163.28 | 0.110 | -74.80 | -0.002 | 947.09 | 0.243 |
| 34/144 | 70 | 529.70 | 2.41 | 246.50 | 0.073 | -193.32 | -0.083 | 723.02 | 0.294 |
| 13/48 | 71 | 892.67 | 4.53 | 147.26 | 0.114 | -74.28 | -0.019 | 966.95 | 0.243 |
| 18/200 | 63 | 594.06 | 3.59 | 179.40 | 0.100 | -29.22 | 0.008 | 623.28 | 0.208 |

Fast SMA with the improved exit (ADX 25 + Chandelier from the first tick), trend 200:

| fast | trades | net $ | PF | maxDD $ | exp R | IS net $ | IS exp R | OOS net $ | OOS exp R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 60 | 598.27 | 4.08 | 85.63 | 0.076 | 1.99 | -0.020 | 596.29 | 0.210 |
| 8 | 59 | 1202.41 | 6.04 | 111.62 | 0.141 | 65.90 | 0.028 | 1136.51 | 0.265 |
| 9 | 59 | 1204.33 | 5.97 | 115.21 | 0.140 | 67.82 | 0.027 | 1136.51 | 0.265 |
| 10 | 53 | 1514.10 | 8.67 | 70.51 | 0.232 | 112.52 | 0.062 | 1401.59 | 0.423 |
| 13 | 49 | 1596.00 | 11.39 | 81.45 | 0.256 | 80.15 | 0.050 | 1515.85 | 0.469 |
| 14 | 48 | 1563.10 | 11.17 | 83.69 | 0.237 | 87.70 | 0.052 | 1475.40 | 0.422 |
| 18 | 48 | 1518.98 | 12.23 | 64.67 | 0.240 | 111.32 | 0.062 | 1407.66 | 0.450 |
| 20 | 51 | 922.33 | 7.42 | 64.67 | 0.163 | 121.87 | 0.049 | 800.46 | 0.273 |
| 21 | 51 | 863.68 | 5.79 | 73.43 | 0.151 | 91.15 | 0.036 | 772.53 | 0.262 |
| 25 | 48 | 907.45 | 6.61 | 64.22 | 0.153 | 172.30 | 0.066 | 735.15 | 0.241 |
| 30 | 48 | 1015.60 | 7.97 | 102.21 | 0.164 | 135.18 | 0.024 | 880.42 | 0.304 |
| 34 | 49 | 1023.56 | 8.43 | 90.77 | 0.162 | 143.14 | 0.026 | 880.42 | 0.304 |
| 50 | 44 | 958.12 | 5.12 | 140.10 | 0.161 | 38.75 | -0.028 | 919.37 | 0.491 |

Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):

| fast/trend | trades | net $ | PF | maxDD $ | IS exp R | OOS exp R | neighbours +OOS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10/300 | 58 | 1002.01 | 4.12 | 163.28 | 0.059 | 0.306 | - |
| 18/300 | 55 | 726.93 | 7.19 | 59.27 | 0.043 | 0.242 | - |
| 18/250 | 51 | 705.51 | 7.01 | 67.95 | 0.038 | 0.275 | - |
| 10/250 | 64 | 937.36 | 3.69 | 163.28 | 0.031 | 0.266 | - |
| 10/200 | 69 | 918.12 | 3.49 | 163.28 | 0.030 | 0.250 | 2/2 |

## 6. Recommendation

Per timeframe, separating 'most profitable in this window' from 'suitable', where suitable means positive in both halves, on a plateau of neighbouring values, and with enough trades.

M1, M5, M15: no SMA setting and no session filter is suitable. The least bad settings (M1 50/200, M5 30-50 fast, M15 18/100 or 20/100) are still negative in 2023-24. Do not trade these timeframes with this EA.

H1: keep fast 18 (13 to 21 is the plateau; 5 to 10 lose). Trend 150 is the most profitable in the window (+$1,551, PF 1.51) and 21/55 is the only pair positive in both halves (+$1,233). Suitable: 18/150 or 18/200 with the New York 13-22 session filter on (the one session filter that improves both halves). Do not use the Chandelier + ADX exit on H1. Expect the 2023 drawdown to repeat in a range year: H1 lost $426 in 2020-2023 with the shipped settings.

H4: the most consistent timeframe in both studies. Most profitable: 18/300 (+$1,616, PF 2.5) and, with the improved exit, 34/200 or 50/200 (+$1,658 to +$1,788, PF 3.3 to 3.5, drawdown $100 to $160). Suitable: fast 18 to 25 with trend 200 to 300, ADX 25 on, Chandelier from the first tick, break-even kept at 500; New York 13-22 filter is optional (small loss of trades, better in-sample). Keep the swing stop. Fund it: the median H4 stop is about $42 per 0.01 lot, so the EA's own 1% rule needs about $4,100; on $200 the shipped gate blocks every trade and the gate-off account was ruined in 2023.

D1: fast 10 to 14 with trend 200 to 300 beats 18/200 in this window (10/300 +$1,002 and positive in all four years; 13/200 +$898, PF 4.1), and with the improved exit fast 10 to 18 are equivalent (+$1,500 to +$1,600). Suitable: keep 18/200 or move to 13/250 only after a forward test, because every D1 cell is 50 to 76 trades and the fast-10 advantage is $300 over three years. The exit change from study 1 remains the bigger lever than any SMA change.

General: the in-sample half (2023-24) is close to zero for every profitable setting on every timeframe; the out-of-sample half is the 2025-26 rally. Any setting chosen here should be treated as tuned to a bull regime and forward-tested on the demo account before real money.
