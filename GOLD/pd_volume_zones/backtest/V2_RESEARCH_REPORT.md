# V2 Research Report - can the V1 weaknesses be turned into a robust edge?

Same data, engine and costs as the baseline (Dukascopy XAUUSD M1 -> 5-min, 39 months between 2021-09-01 and 2026-09-25; one spread per trade of {2021: 0.25, 2022: 0.25, 2023: 0.3, 2024: 0.35, 2025: 0.4, 2026: 0.5}). V1 rules are frozen; every variant flips exactly one switch. Metrics: gross R and net R (after spread); PF and max drawdown are on gross R.

Chronological split from the V1 trade list: Development = before 2025-06-03 (1229 V1 trades), Validation = 2025-06-03 to 2026-02-10 (410), Out-of-sample = after 2026-02-10 (410). Every variant runs over the whole history and is then sliced by these dates, so a filter that removes a trade can change which later setup the one-position rule lets through; the slices are exact, not approximations.

Selection rule for the combination (fixed before running): a variant qualifies when its average net R per trade beats V1 in BOTH Development and Validation and keeps at least 40% of V1's Development trades; ranked by the smaller of the two improvements; at most one per experiment; top 3. Out-of-sample is never used for selection.

## V1 reference

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 baseline | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 |  |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 baseline | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |

## E1 Failed-breakout protection

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |
| exit at the 1st close back inside the rectangle (first 3 bars) | 2072 | 21.5% | +96.1 | -159.3 | +0.046 | -0.077 | 1.08 | 57 | +0.010 |
| exit at the 2nd close back inside the rectangle (first 3 bars) | 2056 | 24.2% | +81.5 | -168.3 | +0.040 | -0.082 | 1.06 | 66 | +0.005 |
| exit at the 1st close back inside the rectangle (first 6 bars) | 2085 | 20.0% | +55.4 | -204.2 | +0.027 | -0.098 | 1.05 | 81 | -0.011 |
| re-confirmation: a 2nd consecutive close beyond the edge before entry | 1727 | 25.8% | +53.2 | -117.8 | +0.031 | -0.068 | 1.04 | 76 | +0.019 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| exit at the 1st close back inside the rectangle (first 3 bars) | 1247 / 21% / -167 / -0.134 | 411 / 25% / +42 / +0.103 | 414 / 20% / -34 / -0.082 |
| exit at the 2nd close back inside the rectangle (first 3 bars) | 1234 / 24% / -160 / -0.129 | 411 / 27% / +36 / +0.088 | 411 / 22% / -45 / -0.109 |
| exit at the 1st close back inside the rectangle (first 6 bars) | 1259 / 19% / -195 / -0.155 | 412 / 22% / +18 / +0.043 | 414 / 20% / -26 / -0.064 |
| re-confirmation: a 2nd consecutive close beyond the edge before entry | 1053 / 25% / -120 / -0.114 | 305 / 32% / +60 / +0.196 | 369 / 22% / -58 / -0.156 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| V1 | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| exit at the 1st close back inside the rectangle (first 3 bars) | 63 / -0.301 | 264 / -0.135 | 425 / -0.113 | 268 / -0.317 | 568 / +0.068 | 484 / -0.022 |
| exit at the 2nd close back inside the rectangle (first 3 bars) | 63 / -0.020 | 263 / -0.073 | 415 / -0.134 | 268 / -0.355 | 566 / +0.050 | 481 / -0.052 |
| exit at the 1st close back inside the rectangle (first 6 bars) | 63 / -0.265 | 265 / -0.159 | 426 / -0.105 | 276 / -0.398 | 570 / +0.033 | 485 / -0.020 |
| re-confirmation: a 2nd consecutive close beyond the edge before entry | 48 / -0.117 | 250 / -0.189 | 298 / -0.099 | 242 / -0.343 | 463 / +0.155 | 426 / -0.056 |

- exit at the 1st close back inside the rectangle (first 3 bars): exits {'SL': 958, 'FB': 669, 'TP': 445}; average FB exit -0.43R (a full stop is -1R)
- exit at the 2nd close back inside the rectangle (first 3 bars): exits {'SL': 1287, 'TP': 498, 'FB': 271}; average FB exit -0.48R (a full stop is -1R)
- exit at the 1st close back inside the rectangle (first 6 bars): exits {'FB': 838, 'SL': 830, 'TP': 417}; average FB exit -0.45R (a full stop is -1R)
- re-confirmation: a 2nd consecutive close beyond the edge before entry: exits {'SL': 1282, 'TP': 445}; setups invalidated by a close back inside before entry: 2699

## E2 Minimum stop (cost viability)

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 (no minimum) | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |
| minimum stop 2 USD | 1956 | 25.8% | +64.3 | -112.2 | +0.033 | -0.057 | 1.04 | 63 | +0.030 |
| minimum stop 3 USD | 1778 | 25.3% | +22.6 | -106.0 | +0.013 | -0.060 | 1.02 | 63 | +0.027 |
| minimum stop 4 USD | 1553 | 25.8% | +50.2 | -44.2 | +0.032 | -0.028 | 1.04 | 61 | +0.059 |
| minimum stop 5 USD | 1388 | 25.5% | +31.5 | -42.9 | +0.023 | -0.031 | 1.03 | 58 | +0.056 |
| minimum stop 0.5 x ATR14 | 2045 | 25.9% | +73.7 | -170.6 | +0.036 | -0.083 | 1.05 | 64 | +0.004 |
| minimum stop 1.0 x ATR14 | 1970 | 24.9% | -10.8 | -221.4 | -0.005 | -0.112 | 0.99 | 98 | -0.025 |
| minimum stop 1.5 x ATR14 | 1848 | 26.7% | +129.4 | -35.9 | +0.070 | -0.019 | 1.09 | 62 | +0.068 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 (no minimum) | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| minimum stop 2 USD | 1141 / 26% / -88 / -0.077 | 405 / 30% / +49 / +0.120 | 410 / 22% / -73 / -0.178 |
| minimum stop 3 USD | 970 / 25% / -84 / -0.086 | 398 / 30% / +47 / +0.117 | 410 / 23% / -69 / -0.168 |
| minimum stop 4 USD | 761 / 26% / -20 / -0.027 | 380 / 29% / +42 / +0.109 | 412 / 23% / -65 / -0.159 |
| minimum stop 5 USD | 610 / 27% / +10 / +0.016 | 369 / 26% / +0 / +0.001 | 409 / 23% / -53 / -0.129 |
| minimum stop 0.5 x ATR14 | 1227 / 26% / -148 / -0.121 | 408 / 30% / +50 / +0.123 | 410 / 22% / -73 / -0.177 |
| minimum stop 1.0 x ATR14 | 1194 / 25% / -171 / -0.144 | 383 / 28% / +18 / +0.047 | 393 / 22% / -68 / -0.173 |
| minimum stop 1.5 x ATR14 | 1101 / 27% / -34 / -0.031 | 368 / 29% / +44 / +0.119 | 379 / 23% / -46 / -0.120 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| V1 (no minimum) | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| minimum stop 2 USD | 57 / -0.253 | 247 / +0.041 | 347 / -0.106 | 265 / -0.272 | 561 / +0.090 | 479 / -0.103 |
| minimum stop 3 USD | 40 / -0.366 | 205 / -0.092 | 295 / +0.018 | 215 / -0.354 | 544 / +0.080 | 479 / -0.094 |
| minimum stop 4 USD | 25 / -0.410 | 149 / +0.023 | 205 / -0.121 | 170 / -0.159 | 523 / +0.107 | 481 / -0.087 |
| minimum stop 5 USD | 16 / -0.540 | 109 / +0.095 | 147 / +0.123 | 140 / -0.266 | 504 / +0.008 | 472 / -0.063 |
| minimum stop 0.5 x ATR14 | 61 / -0.098 | 262 / -0.096 | 414 / -0.093 | 265 / -0.342 | 564 / +0.061 | 479 / -0.094 |
| minimum stop 1.0 x ATR14 | 60 / -0.065 | 258 / -0.088 | 389 / -0.135 | 263 / -0.455 | 544 / +0.042 | 456 / -0.099 |
| minimum stop 1.5 x ATR14 | 57 / -0.066 | 244 / -0.010 | 366 / +0.027 | 225 / -0.349 | 518 / +0.083 | 438 / -0.010 |

- minimum stop 2 USD: setups blocked {'min_risk': 5191}
- minimum stop 3 USD: setups blocked {'min_risk': 12618}
- minimum stop 4 USD: setups blocked {'min_risk': 19915}
- minimum stop 5 USD: setups blocked {'min_risk': 25003}
- minimum stop 0.5 x ATR14: setups blocked {'min_risk': 96}
- minimum stop 1.0 x ATR14: setups blocked {'min_risk': 1495}
- minimum stop 1.5 x ATR14: setups blocked {'min_risk': 6025}

## E3 Target location

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| A: V1 (3R target anywhere) | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |
| B: 3R target must lie beyond the prior-day High (long) / Low (short) | 1629 | 25.5% | +40.4 | -108.4 | +0.025 | -0.067 | 1.03 | 58 | +0.021 |
| C: ... beyond it by at least 0.5R | 1552 | 25.9% | +53.2 | -81.7 | +0.034 | -0.053 | 1.05 | 40 | +0.034 |
| C: ... beyond it by at least 1.0R | 1458 | 26.4% | +91.4 | -26.6 | +0.063 | -0.018 | 1.09 | 32 | +0.069 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| A: V1 (3R target anywhere) | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| B: 3R target must lie beyond the prior-day High (long) / Low (short) | 996 / 25% / -119 / -0.119 | 295 / 30% / +40 / +0.135 | 338 / 23% / -29 / -0.087 |
| C: ... beyond it by at least 0.5R | 950 / 25% / -82 / -0.087 | 287 / 29% / +29 / +0.102 | 315 / 24% / -29 / -0.091 |
| C: ... beyond it by at least 1.0R | 865 / 27% / -31 / -0.036 | 298 / 29% / +32 / +0.106 | 295 / 23% / -27 / -0.092 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| A: V1 (3R target anywhere) | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| B: 3R target must lie beyond the prior-day High (long) / Low (short) | 43 / -0.456 | 238 / -0.220 | 336 / -0.068 | 202 / -0.226 | 414 / +0.103 | 396 / -0.026 |
| C: ... beyond it by at least 0.5R | 42 / -0.342 | 226 / -0.188 | 331 / +0.013 | 180 / -0.146 | 405 / +0.044 | 368 / -0.055 |
| C: ... beyond it by at least 1.0R | 40 / -0.100 | 198 / -0.072 | 300 / +0.056 | 170 / -0.153 | 403 / +0.036 | 347 / -0.039 |

- B: 3R target must lie beyond the prior-day High (long) / Low (short): setups blocked {'target': 15387}
- C: ... beyond it by at least 0.5R: setups blocked {'target': 18273}
- C: ... beyond it by at least 1.0R: setups blocked {'target': 21930}

## E4 Volatility regime

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 (no filter) | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |
| avoid low: ATR14 below its 20th percentile of the last 7 days | 1945 | 25.7% | +44.2 | -179.7 | +0.023 | -0.092 | 1.03 | 59 | -0.005 |
| avoid low and high: below 20th or above 90th percentile (7 days) | 1878 | 25.8% | +49.5 | -177.4 | +0.026 | -0.094 | 1.04 | 56 | -0.007 |
| robustness: below 10th percentile | 1997 | 25.9% | +65.2 | -170.0 | +0.033 | -0.085 | 1.04 | 67 | +0.002 |
| robustness: below 30th percentile | 1843 | 27.5% | +185.0 | -14.3 | +0.100 | -0.008 | 1.14 | 53 | +0.079 |
| robustness: below 20th percentile of the last 30 days | 1937 | 26.6% | +120.9 | -99.6 | +0.062 | -0.051 | 1.08 | 59 | +0.036 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 (no filter) | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| avoid low: ATR14 below its 20th percentile of the last 7 days | 1195 / 26% / -138 / -0.115 | 377 / 28% / +6 / +0.016 | 373 / 24% / -48 / -0.128 |
| avoid low and high: below 20th or above 90th percentile (7 days) | 1164 / 27% / -103 / -0.089 | 358 / 25% / -31 / -0.088 | 356 / 24% / -43 / -0.120 |
| robustness: below 10th percentile | 1200 / 26% / -133 / -0.111 | 397 / 29% / +32 / +0.080 | 400 / 22% / -69 / -0.173 |
| robustness: below 30th percentile | 1123 / 27% / -58 / -0.052 | 366 / 29% / +38 / +0.103 | 354 / 27% / +6 / +0.017 |
| robustness: below 20th percentile of the last 30 days | 1168 / 26% / -111 / -0.095 | 383 / 29% / +32 / +0.083 | 386 / 25% / -20 / -0.051 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| V1 (no filter) | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| avoid low: ATR14 below its 20th percentile of the last 7 days | 60 / -0.356 | 260 / -0.036 | 403 / -0.141 | 265 / -0.310 | 517 / +0.022 | 440 / -0.049 |
| avoid low and high: below 20th or above 90th percentile (7 days) | 51 / -0.386 | 252 / +0.038 | 425 / -0.173 | 251 / -0.205 | 483 / -0.044 | 416 / -0.051 |
| robustness: below 10th percentile | 53 / -0.163 | 260 / -0.098 | 413 / -0.107 | 266 / -0.316 | 538 / +0.065 | 467 / -0.091 |
| robustness: below 30th percentile | 60 / -0.213 | 245 / +0.069 | 381 / -0.076 | 241 / -0.290 | 495 / +0.072 | 421 / +0.106 |
| robustness: below 20th percentile of the last 30 days | 53 / -0.254 | 255 / -0.080 | 394 / -0.098 | 264 / -0.305 | 517 / +0.080 | 454 / +0.027 |

- avoid low: ATR14 below its 20th percentile of the last 7 days: setups blocked {'vol': 4734}
- avoid low and high: below 20th or above 90th percentile (7 days): setups blocked {'vol': 7635}
- robustness: below 10th percentile: setups blocked {'vol': 2032}
- robustness: below 30th percentile: setups blocked {'vol': 8533}
- robustness: below 20th percentile of the last 30 days: setups blocked {'vol': 4936}

## E5 POC tap timing

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| A: tap on the confirmation candle itself only | 2006 | 24.5% | -57.2 | -334.5 | -0.029 | -0.167 | 0.96 | 119 | -0.080 |
| B: POC touched at least one candle before the confirmation | 1908 | 26.7% | +124.5 | -94.1 | +0.065 | -0.049 | 1.09 | 56 | +0.038 |
| C: either (V1) | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| A: tap on the confirmation candle itself only | 1231 / 25% / -227 / -0.184 | 380 / 26% / -22 / -0.058 | 395 / 22% / -86 / -0.217 |
| B: POC touched at least one candle before the confirmation | 1141 / 27% / -83 / -0.072 | 370 / 31% / +58 / +0.157 | 397 / 22% / -70 / -0.176 |
| C: either (V1) | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| A: tap on the confirmation candle itself only | 57 / -0.324 | 263 / -0.134 | 445 / -0.084 | 265 / -0.439 | 520 / -0.108 | 456 / -0.155 |
| B: POC touched at least one candle before the confirmation | 53 / +0.071 | 208 / -0.191 | 404 / -0.133 | 267 / -0.182 | 511 / +0.174 | 465 / -0.097 |
| C: either (V1) | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |

## E6 Sessions (information only, not a selection candidate)

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 (all sessions) | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 | +0.000 |
| exclude Asia 00-07 UTC | 1878 | 26.7% | +129.0 | -94.3 | +0.069 | -0.050 | 1.09 | 56 | +0.037 |
| exclude London 07-12 UTC | 1968 | 25.1% | -1.0 | -232.6 | -0.001 | -0.118 | 1.00 | 108 | -0.031 |
| exclude Overlap 12-16 UTC | 1856 | 25.5% | +36.0 | -197.5 | +0.019 | -0.106 | 1.03 | 61 | -0.019 |
| exclude New York 16-21 UTC | 1871 | 25.2% | +19.6 | -203.1 | +0.010 | -0.109 | 1.01 | 78 | -0.021 |
| exclude Close 21-24 UTC | 2037 | 25.5% | +41.8 | -203.0 | +0.021 | -0.100 | 1.03 | 75 | -0.013 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 (all sessions) | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| exclude Asia 00-07 UTC | 1131 / 26% / -95 / -0.084 | 376 / 30% / +36 / +0.095 | 371 / 25% / -35 / -0.094 |
| exclude London 07-12 UTC | 1179 / 24% / -218 / -0.185 | 395 / 30% / +46 / +0.116 | 394 / 23% / -60 / -0.153 |
| exclude Overlap 12-16 UTC | 1097 / 25% / -171 / -0.155 | 381 / 30% / +41 / +0.108 | 378 / 22% / -68 / -0.181 |
| exclude New York 16-21 UTC | 1127 / 26% / -134 / -0.119 | 383 / 29% / +25 / +0.065 | 361 / 20% / -94 / -0.261 |
| exclude Close 21-24 UTC | 1224 / 25% / -174 / -0.142 | 402 / 30% / +52 / +0.130 | 411 / 22% / -82 / -0.199 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| V1 (all sessions) | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| exclude Asia 00-07 UTC | 47 / -0.559 | 258 / +0.097 | 375 / -0.070 | 256 / -0.349 | 508 / +0.078 | 434 / -0.039 |
| exclude London 07-12 UTC | 58 / +0.101 | 253 / -0.153 | 390 / -0.222 | 263 / -0.393 | 542 / +0.047 | 462 / -0.077 |
| exclude Overlap 12-16 UTC | 51 / +0.101 | 193 / -0.080 | 406 / -0.224 | 237 / -0.290 | 529 / +0.024 | 440 / -0.092 |
| exclude New York 16-21 UTC | 60 / -0.415 | 234 / -0.074 | 368 / +0.040 | 259 / -0.336 | 532 / -0.036 | 418 / -0.165 |
| exclude Close 21-24 UTC | 59 / -0.125 | 259 / -0.115 | 420 / -0.127 | 260 / -0.358 | 562 / +0.084 | 477 / -0.140 |

### E6 detail: V1 by session and year (n / avg net R)

| Session | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | DEV | VAL | OOS |
|---|---|---|---|---|---|---|---|---|---|
| Asia 00-07 UTC | 16 / +0.600 | 58 / -0.054 | 96 / -0.373 | 61 / -0.579 | 158 / +0.013 | 142 / -0.052 | 300 / -0.191 | 108 / -0.011 | 123 / -0.093 |
| London 07-12 UTC | 7 / -0.626 | 48 / +0.043 | 53 / +0.332 | 51 / +0.079 | 60 / -0.110 | 40 / -0.470 | 187 / +0.084 | 33 / -0.122 | 39 / -0.455 |
| Overlap 12-16 UTC | 18 / -0.458 | 48 / -0.182 | 101 / +0.017 | 65 / -0.386 | 79 / +0.341 | 76 / -0.139 | 259 / -0.131 | 60 / +0.403 | 68 / -0.208 |
| New York 16-21 UTC | 17 / -0.202 | 90 / -0.257 | 138 / -0.285 | 78 / -0.507 | 213 / +0.177 | 158 / +0.013 | 401 / -0.248 | 166 / +0.285 | 127 / -0.107 |
| Close 21-24 UTC | 3 / +0.111 | 19 / +0.346 | 26 / +0.461 | 11 / -0.426 | 56 / -0.227 | 63 / -0.231 | 82 / +0.214 | 43 / -0.340 | 53 / -0.303 |

## E7 Zone quality (V1 trades; terciles fixed on the whole sample; Spearman rank correlation of the feature with the trade's R)

| Feature | Period | rho (p) | n | low tercile (n / win / avg net R) | mid | high |
|---|---|---|---|---|---|---|
| Volume prominence (HVN rectangles only) | DEV | +0.013 () | 783 | 282 / 21% / -0.291 | 255 / 27% / -0.069 | 246 / 26% / -0.143 |
| Volume prominence (HVN rectangles only) | VAL | +0.057 () | 265 | 81 / 28% / +0.017 | 95 / 32% / +0.180 | 89 / 28% / +0.073 |
| Volume prominence (HVN rectangles only) | OOS | -0.090 () | 268 | 76 / 32% / +0.116 | 88 / 20% / -0.246 | 104 / 18% / -0.335 |
| Rectangle height (USD) | DEV | +0.001 () | 1229 | 643 / 26% / -0.162 | 478 / 25% / -0.140 | 108 / 29% / +0.127 |
| Rectangle height (USD) | VAL | +0.013 () | 410 | 40 / 25% / -0.186 | 163 / 32% / +0.181 | 207 / 30% / +0.143 |
| Rectangle height (USD) | OOS | +0.010 () | 410 |  | 43 / 28% / +0.012 | 367 / 22% / -0.200 |
| Rectangle height / prior-day range | DEV | -0.000 () | 1229 | 401 / 25% / -0.166 | 402 / 27% / -0.054 | 426 / 24% / -0.163 |
| Rectangle height / prior-day range | VAL | -0.071 () | 410 | 141 / 36% / +0.364 | 133 / 27% / -0.005 | 136 / 27% / +0.008 |
| Rectangle height / prior-day range | OOS | +0.064 () | 410 | 143 / 21% / -0.237 | 147 / 19% / -0.287 | 120 / 28% / +0.026 |
| Volume share of the day | DEV | -0.002 () | 1229 | 408 / 28% / -0.033 | 420 / 22% / -0.278 | 401 / 27% / -0.068 |
| Volume share of the day | VAL | -0.024 () | 410 | 140 / 33% / +0.232 | 133 / 26% / -0.030 | 137 / 31% / +0.171 |
| Volume share of the day | OOS | -0.002 () | 410 | 135 / 23% / -0.134 | 130 / 22% / -0.217 | 145 / 22% / -0.184 |
| POC position inside the rectangle (0 = bottom, 1 = top) | DEV | -0.009 () | 1229 | 419 / 28% / -0.039 | 402 / 23% / -0.228 | 408 / 26% / -0.121 |
| POC position inside the rectangle (0 = bottom, 1 = top) | VAL | -0.003 () | 410 | 137 / 32% / +0.207 | 145 / 29% / +0.075 | 128 / 30% / +0.098 |
| POC position inside the rectangle (0 = bottom, 1 = top) | OOS | +0.034 () | 410 | 127 / 20% / -0.235 | 137 / 26% / -0.085 | 146 / 21% / -0.215 |
| Distance to the nearest other rectangle (heights) | DEV | +0.003 () | 1229 | 418 / 24% / -0.180 | 417 / 28% / -0.032 | 394 / 25% / -0.174 |
| Distance to the nearest other rectangle (heights) | VAL | +0.054 () | 410 | 139 / 29% / +0.070 | 151 / 29% / +0.114 | 120 / 32% / +0.206 |
| Distance to the nearest other rectangle (heights) | OOS | -0.065 () | 410 | 126 / 25% / -0.080 | 125 / 25% / -0.069 | 159 / 18% / -0.341 |
| Number of touches before entry | DEV | -0.016 () | 1229 | 1229 / 26% / -0.128 |  |  |
| Number of touches before entry | VAL | -0.020 () | 410 | 410 / 30% / +0.126 |  |  |
| Number of touches before entry | OOS | +0.091 () | 410 | 410 / 22% / -0.178 |  |  |

First touch vs repeated touch (V1):

| Period | Touch | n | Win rate | Avg net R |
|---|---|---|---|---|
| DEV | first touch | 488 | 26.4% | -0.098 |
| DEV | repeat | 741 | 25.0% | -0.148 |
| OOS | first touch | 176 | 16.5% | -0.395 |
| OOS | repeat | 234 | 26.9% | -0.014 |
| VAL | first touch | 171 | 29.8% | +0.087 |
| VAL | repeat | 239 | 30.5% | +0.154 |

## Combination test

Candidates (rule above):

- E5 POC tap timing: B: POC touched at least one candle before the confirmation (improvement in avg net R: DEV +0.056, VAL +0.031)
- E1 Failed-breakout protection: re-confirmation: a 2nd consecutive close beyond the edge before entry (improvement in avg net R: DEV +0.014, VAL +0.070)
- E3 Target location: B: 3R target must lie beyond the prior-day High (long) / Low (short) (improvement in avg net R: DEV +0.009, VAL +0.008)

| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |
|---|---|---|---|---|---|---|---|---|---|
| V1 baseline | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | -0.087 | 1.05 | 72 |  |
| E5 alone: B: POC touched at least one candle before the confirmation | 1908 | 26.7% | +124.5 | -94.1 | +0.065 | -0.049 | 1.09 | 56 | +0.038 |
| E1 alone: re-confirmation: a 2nd consecutive close beyond the edge before entry | 1727 | 25.8% | +53.2 | -117.8 | +0.031 | -0.068 | 1.04 | 76 | +0.019 |
| E3 alone: B: 3R target must lie beyond the prior-day High (long) / Low (short) | 1629 | 25.5% | +40.4 | -108.4 | +0.025 | -0.067 | 1.03 | 58 | +0.021 |
| E5 + E1: B: POC touched at least one candle  + re-confirmation: a 2nd consecutive  | 1685 | 24.4% | -38.0 | -204.3 | -0.023 | -0.121 | 0.97 | 112 | -0.034 |
| E5 + E3: B: POC touched at least one candle  + B: 3R target must lie beyond the pr | 1486 | 26.6% | +103.7 | -24.0 | +0.070 | -0.016 | 1.09 | 45 | +0.071 |
| E1 + E3: re-confirmation: a 2nd consecutive  + B: 3R target must lie beyond the pr | 1375 | 25.9% | +78.4 | -24.6 | +0.057 | -0.018 | 1.08 | 45 | +0.069 |
| E5 + E1 + E3: B: POC touched at least one candle  + re-confirmation: a 2nd consecutive  + B: 3R target must lie beyond the pr | 1307 | 25.5% | +53.3 | -43.7 | +0.041 | -0.033 | 1.05 | 53 | +0.054 |

| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |
|---|---|---|---|
| V1 baseline | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| E5 alone | 1141 / 27% / -83 / -0.072 | 370 / 31% / +58 / +0.157 | 397 / 22% / -70 / -0.176 |
| E1 alone | 1053 / 25% / -120 / -0.114 | 305 / 32% / +60 / +0.196 | 369 / 22% / -58 / -0.156 |
| E3 alone | 996 / 25% / -119 / -0.119 | 295 / 30% / +40 / +0.135 | 338 / 23% / -29 / -0.087 |
| E5 + E1 | 1047 / 24% / -174 / -0.166 | 274 / 30% / +38 / +0.139 | 364 / 21% / -68 / -0.187 |
| E5 + E3 | 882 / 26% / -43 / -0.049 | 278 / 29% / +31 / +0.113 | 326 / 25% / -12 / -0.038 |
| E1 + E3 | 838 / 25% / -67 / -0.080 | 249 / 29% / +47 / +0.190 | 288 / 25% / -5 / -0.016 |
| E5 + E1 + E3 | 797 / 25% / -57 / -0.071 | 231 / 27% / +25 / +0.108 | 279 / 24% / -12 / -0.044 |

| Variant | 2021 (n / avg net R) | 2022 (n / avg net R) | 2023 (n / avg net R) | 2024 (n / avg net R) | 2025 (n / avg net R) | 2026 (n / avg net R) |
|---|---|---|---|---|---|---|
| V1 baseline | 61 / -0.100 | 263 / -0.100 | 414 / -0.106 | 266 / -0.378 | 566 / +0.084 | 479 / -0.103 |
| E5 + E1 | 29 / -0.558 | 239 / -0.214 | 334 / -0.161 | 238 / -0.368 | 423 / +0.085 | 422 / -0.075 |
| E5 + E3 | 38 / -0.467 | 189 / -0.218 | 308 / +0.111 | 193 / -0.174 | 376 / +0.067 | 382 / +0.024 |
| E1 + E3 | 38 / -0.137 | 214 / -0.232 | 232 / +0.114 | 176 / -0.120 | 378 / +0.032 | 337 / +0.038 |
| E5 + E1 + E3 | 22 / -0.532 | 201 / -0.255 | 249 / +0.178 | 160 / -0.194 | 347 / -0.009 | 328 / +0.028 |

## Walk-forward (selection redone each year on the years before it, then applied to that year only)

| Test year | Switches picked on the prior years | V1 in that year (n / avg net R / net R) | Picked combination in that year |
|---|---|---|---|
| 2023 | E4: robustness: below 30th percentile; E2: minimum stop 2 USD; E1: exit at the 2nd close back inside the rectangle (first 3 bars) | 414 / -0.106 / -43.9 | 321 / -0.082 / -26.2 |
| 2024 | E2: minimum stop 1.5 x ATR14; E3: C: ... beyond it by at least 1.0R; E4: robustness: below 30th percentile | 266 / -0.378 / -100.6 | 141 / -0.194 / -27.3 |
| 2025 | E3: C: ... beyond it by at least 1.0R; E2: minimum stop 5 USD; E4: robustness: below 30th percentile | 566 / +0.084 / +47.6 | 341 / +0.116 / +39.6 |
| 2026 | E2: minimum stop 4 USD; E3: C: ... beyond it by at least 1.0R; E5: B: POC touched at least one candle before the confirmation | 479 / -0.103 / -49.2 | 327 / +0.024 / +8.0 |

## Conclusion against the success criteria

**Verdict: no modification, alone or combined, produces a robust positive net expectancy.** The two mechanically
sound changes - a minimum stop (cost viability) and a 3R target that lies beyond the prior day's High/Low - move the
strategy from -0.087R to about -0.02R per trade after costs, i.e. from a loser to break-even. The walk-forward of the
whole selection procedure over 2023-2026 returns -6R on 1,130 trades where V1 returned -146R: the procedure removes
the bleeding, it does not create an edge.

| Criterion | Result |
|---|---|
| Positive net expectancy after realistic costs | Not met. Best single switch: E3 target beyond the prior-day range by 1R, -0.018R/trade (-27R). Best combinations: E5+E3 -0.016R (-24R), E1+E3 -0.018R (-25R). |
| Positive results across multiple years | Partly. E5+E3 is positive in 3 of 6 years (2023 +0.11, 2025 +0.07, 2026 +0.02) and negative in 2021, 2022 (-0.22) and 2024 (-0.17). |
| Improvement in out-of-sample data | Only through E3: OOS -0.178 (V1) -> -0.087 (E3 alone) -> -0.038 / -0.016 (E5+E3 / E1+E3). Still negative. E5 and E1 do not improve OOS at all. |
| Reasonable drawdown | Combinations 45R vs 72R for V1; E3 alone 32R. At a 25% win rate a 20-trade losing run stays normal. |
| No dependence on one exceptional year | V1's gross profit is 2025 alone. The combinations spread the result more evenly, but none is positive without 2023 and 2025 together. |
| No dependence on one precise parameter | E2 (2/3/4/5 USD: -112/-106/-44/-43R) and E3 (margin 0/0.5/1.0R: -108/-82/-27R) move monotonically = robust direction. E4 is a spike: the 30th-percentile filter (-14R) sits between the 10th (-170R) and 20th (-180R) = not robust, excluded. |
| No suspicious reduction in trade count | Met: the combinations keep 64-73% of V1's trades; a 5 USD minimum stop keeps 68%. |
| Stability across reasonable parameter changes | E2 and E3 yes; E4 no; E5-B and E1 re-confirmation are single-form rules without a parameter. |

Experiment by experiment:

- **E1 failed-breakout protection.** Exiting at the first close back inside the rectangle changes +0.010R/trade: those exits
  average -0.43R instead of -1R, but the win rate falls from 25.9% to 21.5% because winning trades dip back inside too.
  The arithmetic is flat by construction: about 13% of the trades that close back inside still reach 3R, so cutting all of
  them at -0.43R saves 0.57R on the 87% and forfeits 3.43R on the 13% (0.87 x 0.57 - 0.13 x 3.43 = +0.05R), and the
  one-position interaction eats most of that. The close back inside is the symptom of a coin-flip entry, not a signal.
  Re-confirmation (a second close beyond the edge) adds +0.019R/trade and invalidates 2,699 setups; better in DEV and
  VAL, OOS -0.156 vs -0.178. Marginal.
- **E2 minimum stop.** A monotone cost effect, not a market effect: 4-5 USD or 1.5 x ATR14 lifts the net result to about
  -0.03R/trade. The 5 USD variant is the only one with DEV and VAL both non-negative (+0.016, +0.001) and it is -0.129 out
  of sample. It did not qualify as a candidate because it does not beat V1 in Validation (V1's own VAL was its good period).
- **E3 target location.** Monotone in the margin. Requiring the 3R target beyond the prior-day High/Low by at least 1R gives
  -0.018R/trade, the lowest drawdown of the lab (32R), OOS -0.092 vs -0.178, positive in 2023 (+0.056) and 2025 (+0.036).
  The most robust single change found, and still not positive.
- **E4 volatility regime.** The 20th-percentile filter does nothing (-0.005R/trade); the 30th-percentile result is a spike
  with failing neighbours. Not adopted.
- **E5 POC timing.** Requiring the tap on an earlier candle than the confirmation improves DEV (+0.056) and VAL (+0.031)
  and exactly nothing out of sample (-0.176 vs -0.178). Requiring the tap on the same candle is the worst variant in the lab
  (-0.167R/trade, PF 0.96, 119R drawdown). Waiting for a separate retest does not pay for the trades it drops.
- **E6 sessions.** Only Asia is weak in 5 of 6 years (2021, +0.60 on 16 trades, is the exception). London, New York and the
  overlap flip sign between 2021-24 and 2025-26. No session rule is stable enough to adopt.
- **E7 zone quality.** No rectangle characteristic predicts the outcome: every Spearman rho is within +/-0.09 and flips
  sign across periods, the terciles are non-monotone, and first-touch vs repeat reverses (first touch better in DEV, repeat
  better OOS). The volume-profile construction carries no measurable information, which also means it cannot be fixed by
  moving its thresholds: the rectangles behave like any horizontal level.

Walk-forward: the picks change every year (2023: E4/E2/E1; 2024: E2/E3/E4; 2025: E3/E2/E4; 2026: E2/E3/E5); E2 and E3
appear in three of the four years. Test-year results: 2023 -26R (V1 -44), 2024 -27R (V1 -101), 2025 +40R (V1 +48),
2026 +8R (V1 -49).

**What V2 established.** (1) The losses come from paying the spread on tiny stops and from targets that run into the prior
day's extremes; fixing both makes the system break-even. (2) Nothing in the rectangle construction, the tap, the
confirmation candle, the volatility regime or the session carries predictive information beyond that. Under the success
criteria the previous-day volume-zone concept does not demonstrate sufficient edge. Recommendation: stop optimising this
rule set. If it is traded at all, trade it only with the two robust constraints (minimum stop >= 4 USD or 1.5 x ATR14, and
the 3R target beyond the prior-day High/Low by >= 1R), on demo, expecting break-even before slippage. A new source of
edge is needed, not new thresholds on this one.
