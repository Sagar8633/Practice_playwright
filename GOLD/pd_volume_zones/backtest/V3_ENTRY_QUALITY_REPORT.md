# V3 Entry Quality Report - does pre-entry information separate good setups from bad ones?

V1 trade set: 2,049 trades (25.9% winners, -178R net). Split: Development before 2025-06-03 (1229), Validation to 2026-02-10 (410), Out-of-sample after (410). Exits unchanged (fixed SL at the rectangle edge, fixed 3R target). Every feature is computed from candles up to and including the confirmation candle and from the rectangles known at that time; outcome labels are analysis targets only.

How to read AUC: the probability that a random winner has a higher feature value than a random loser. 0.50 = no information; 0.55 or 0.45 = weak; the standard error is about 0.017 in Development and 0.03 in Validation / Out-of-sample, so anything inside 0.47-0.53 in DEV or 0.44-0.56 in VAL/OOS is noise. 'Consistent' = same direction in DEV and VAL with |AUC-0.5| >= 0.03 in both.

## A. Entry Failure Report and B. Entry Success Report - every pre-entry feature

Sorted by separation in Development. Medians are for losers vs winners over the whole sample.

| Feature | Median losers | Median winners | AUC all | AUC DEV | AUC VAL | AUC OOS | Consistent DEV+VAL | OOS agrees |
|---|---|---|---|---|---|---|---|---|
| Distance to the nearest opposing rectangle (R) | 1.84 | 1.64 | 0.466 | 0.467 | 0.483 | 0.459 |  | yes |
| Candles since the last POC tap | 0.00 | 0.00 | 0.518 | 0.529 | 0.497 | 0.497 |  |  |
| Momentum of the 3 candles before (ATR, + = with the trade) | 0.28 | 0.32 | 0.514 | 0.526 | 0.478 | 0.504 |  |  |
| Same-direction candles among the last 5 | 3.00 | 3.00 | 0.512 | 0.525 | 0.486 | 0.484 |  |  |
| Tap candle close vs POC (rect. heights, + = toward the trade) | 0.67 | 0.69 | 0.495 | 0.476 | 0.547 | 0.499 |  |  |
| Confirmation body / ATR14 | 0.89 | 0.79 | 0.472 | 0.476 | 0.461 | 0.470 |  | yes |
| Approach speed: 5-candle move before the confirmation (ATR) | 1.51 | 1.54 | 0.506 | 0.523 | 0.508 | 0.454 |  |  |
| Trades already taken today | 1.00 | 1.00 | 0.508 | 0.520 | 0.494 | 0.482 |  |  |
| Momentum of the 5 candles before (ATR) | 0.26 | 0.46 | 0.514 | 0.519 | 0.499 | 0.511 |  |  |
| Rectangle to prior-day High (heights) | 7.00 | 6.33 | 0.481 | 0.482 | 0.509 | 0.453 |  | yes |
| ... 50-candle extreme | 2.28 | 2.06 | 0.485 | 0.483 | 0.483 | 0.498 |  |  |
| Room to the prior-day High/Low in the trade direction (R) | 4.34 | 3.93 | 0.480 | 0.483 | 0.454 | 0.514 |  |  |
| Wick against the trade / range | 0.14 | 0.14 | 0.504 | 0.515 | 0.493 | 0.481 |  |  |
| Close position in the candle (1 = at the extreme, trade direction) | 0.86 | 0.86 | 0.496 | 0.485 | 0.507 | 0.519 |  |  |
| Prior failed breakouts the other way (today) | 0.00 | 0.00 | 0.503 | 0.515 | 0.473 | 0.492 |  |  |
| Confirmation range / ATR14 | 1.40 | 1.34 | 0.480 | 0.486 | 0.485 | 0.455 |  | yes |
| Candles since the zones were created | 69.00 | 71.00 | 0.503 | 0.514 | 0.490 | 0.481 |  |  |
| POC taps (interaction) | 2.00 | 2.00 | 0.504 | 0.487 | 0.497 | 0.566 |  |  |
| Volume prominence (HVN only) | 0.79 | 0.79 | 0.496 | 0.512 | 0.525 | 0.422 |  |  |
| POC taps today | 2.00 | 2.00 | 0.504 | 0.489 | 0.487 | 0.574 |  |  |
| Wick with the trade / range | 0.11 | 0.12 | 0.505 | 0.489 | 0.566 | 0.489 |  |  |
| Penetration into the rectangle during the interaction (1 = far edge) | 1.49 | 1.43 | 0.496 | 0.509 | 0.460 | 0.496 |  |  |
| Rectangles on the day | 5.00 | 5.00 | 0.494 | 0.492 | 0.501 | 0.493 |  |  |
| Confirmation body / range | 0.67 | 0.64 | 0.491 | 0.492 | 0.450 | 0.537 |  |  |
| Distance below the 20-candle extreme (ATR, negative = new extreme) | 0.51 | 0.58 | 0.497 | 0.492 | 0.507 | 0.508 |  |  |
| Prior failed breakouts in the trade direction (today) | 0.00 | 0.00 | 0.492 | 0.508 | 0.451 | 0.493 |  |  |
| Rectangle position in the prior-day range (0 = Low, 1 = High) | 0.54 | 0.56 | 0.515 | 0.507 | 0.497 | 0.545 |  | yes |
| Confirmation range / rectangle height | 1.42 | 1.41 | 0.491 | 0.493 | 0.496 | 0.477 |  | yes |
| Candles in the current interaction | 3.00 | 3.00 | 0.490 | 0.493 | 0.470 | 0.509 |  |  |
| Rectangle to prior-day Low (heights) | 8.00 | 8.67 | 0.503 | 0.493 | 0.503 | 0.523 |  |  |
| Entry distance from POC (rect. heights) | 1.01 | 1.04 | 0.509 | 0.507 | 0.514 | 0.499 |  |  |
| Stop distance / ATR14 | 1.68 | 1.67 | 0.498 | 0.507 | 0.498 | 0.464 |  |  |
| 20-candle trend before entry (ATR, + = with the trade) | 0.50 | 0.50 | 0.508 | 0.506 | 0.518 | 0.492 |  |  |
| ATR14 percentile (7 days) | 0.54 | 0.54 | 0.512 | 0.505 | 0.512 | 0.536 |  | yes |
| ATR14 / 7-day median | 1.04 | 1.03 | 0.513 | 0.505 | 0.513 | 0.538 |  | yes |
| Colour changes in the last 6 candles | 3.00 | 3.00 | 0.514 | 0.495 | 0.557 | 0.525 |  |  |
| Rectangle touches today | 3.00 | 3.00 | 0.502 | 0.504 | 0.466 | 0.531 |  | yes |
| Stop distance (USD) | 3.46 | 3.73 | 0.507 | 0.504 | 0.517 | 0.490 |  |  |
| ATR14 (USD) | 2.11 | 2.16 | 0.502 | 0.496 | 0.530 | 0.508 |  |  |
| POC position in the rectangle | 0.50 | 0.50 | 0.501 | 0.497 | 0.500 | 0.518 |  |  |
| Volume share of the day | 0.07 | 0.07 | 0.496 | 0.497 | 0.486 | 0.503 |  |  |
| Distance to the nearest rectangle (heights) | 2.00 | 2.00 | 0.495 | 0.503 | 0.528 | 0.439 |  |  |
| Rectangle height / prior-day range | 0.05 | 0.05 | 0.499 | 0.497 | 0.458 | 0.552 |  |  |
| Tap wick past the POC (rect. heights) | 0.35 | 0.33 | 0.484 | 0.497 | 0.471 | 0.451 |  | yes |
| ATR14 percentile (30 days) | 0.55 | 0.59 | 0.518 | 0.502 | 0.539 | 0.528 |  | yes |
| Candles closed inside (interaction) | 1.00 | 1.00 | 0.508 | 0.502 | 0.494 | 0.539 |  | yes |
| Closes inside today | 1.00 | 2.00 | 0.507 | 0.498 | 0.486 | 0.559 |  |  |
| Reject-and-return count (interaction) | 0.00 | 0.00 | 0.493 | 0.498 | 0.479 | 0.495 |  |  |
| Rectangle height / ATR14 | 1.01 | 0.97 | 0.492 | 0.499 | 0.482 | 0.483 |  |  |
| Close beyond the edge (rect. heights) | 0.51 | 0.51 | 0.501 | 0.499 | 0.514 | 0.485 |  |  |
| Rectangle height (USD) | 2.03 | 2.03 | 0.501 | 0.501 | 0.512 | 0.508 |  |  |
| Candles touching the rectangle (interaction) | 3.00 | 3.00 | 0.500 | 0.499 | 0.477 | 0.525 |  |  |
| Hour (UTC) | 14.00 | 14.00 | 0.501 | 0.500 | 0.497 | 0.484 |  |  |
| POC crosses in the last 12 candles | 1.00 | 1.00 | 0.510 | 0.500 | 0.493 | 0.559 |  | yes |
| Close beyond the edge (ATR) | 0.50 | 0.47 | 0.500 | 0.500 | 0.519 | 0.472 |  | yes |

Categorical features (n / win rate / avg net R):

| Feature | Category | All | DEV | VAL | OOS |
|---|---|---|---|---|---|
| Side | short | 1004 / 25% / -0.111 | 621 / 25% / -0.146 | 194 / 26% / -0.030 | 189 / 25% / -0.076 |
| Side | long | 1045 / 26% / -0.064 | 608 / 26% / -0.110 | 216 / 34% / +0.267 | 221 / 20% / -0.265 |
| Rectangle type | HVN | 1316 / 25% / -0.120 | 783 / 25% / -0.172 | 265 / 29% / +0.094 | 268 / 23% / -0.178 |
| Rectangle type | PDL | 353 / 26% / -0.085 | 213 / 26% / -0.119 | 60 / 32% / +0.196 | 80 / 21% / -0.206 |
| Rectangle type | PDH | 380 / 28% / +0.025 | 233 / 29% / +0.013 | 85 / 32% / +0.177 | 62 / 23% / -0.141 |
| Session | New York 16-21 UTC | 694 / 26% / -0.094 | 401 / 23% / -0.248 | 166 / 34% / +0.285 | 127 / 25% / -0.107 |
| Session | Overlap 12-16 UTC | 387 / 26% / -0.062 | 259 / 25% / -0.131 | 60 / 38% / +0.403 | 68 / 21% / -0.208 |
| Session | Asia 00-07 UTC | 531 / 25% / -0.132 | 300 / 24% / -0.191 | 108 / 27% / -0.011 | 123 / 24% / -0.093 |
| Session | London 07-12 UTC | 259 / 28% / -0.024 | 187 / 31% / +0.084 | 33 / 24% / -0.122 | 39 / 15% / -0.455 |
| Session | Close 21-24 UTC | 178 / 26% / -0.073 | 82 / 34% / +0.214 | 43 / 19% / -0.340 | 53 / 19% / -0.303 |
| POC interaction type | D multiple taps | 251 / 22% / -0.223 | 145 / 22% / -0.240 | 67 / 24% / -0.085 | 39 / 21% / -0.394 |
| POC interaction type | E deep cross | 1275 / 26% / -0.095 | 770 / 26% / -0.118 | 244 / 29% / +0.083 | 261 / 22% / -0.193 |
| POC interaction type | B reject-return | 120 / 28% / +0.008 | 76 / 33% / +0.164 | 20 / 25% / -0.098 | 24 / 17% / -0.397 |
| POC interaction type | A touch and go | 187 / 26% / -0.106 | 104 / 18% / -0.442 | 44 / 41% / +0.538 | 39 / 28% / +0.062 |
| POC interaction type | other | 181 / 28% / -0.008 | 112 / 27% / -0.059 | 30 / 33% / +0.162 | 39 / 26% / +0.008 |
| POC interaction type | C several bars inside | 35 / 37% / +0.523 | 22 / 32% / +0.374 | 5 / 80% / +2.105 | 8 / 25% / -0.054 |
| Previous candle in the trade direction | True | 1170 / 27% / -0.043 | 715 / 27% / -0.049 | 237 / 29% / +0.077 | 218 / 22% / -0.156 |
| Previous candle in the trade direction | False | 879 / 25% / -0.145 | 514 / 23% / -0.238 | 173 / 32% / +0.193 | 192 / 22% / -0.203 |
| First POC touch | False | 1214 / 26% / -0.063 | 741 / 25% / -0.148 | 239 / 31% / +0.154 | 234 / 27% / -0.014 |
| First POC touch | True | 835 / 25% / -0.123 | 488 / 26% / -0.098 | 171 / 30% / +0.087 | 176 / 16% / -0.395 |
| No rectangle between entry and target | False | 1203 / 27% / -0.047 | 732 / 26% / -0.105 | 240 / 31% / +0.175 | 231 / 25% / -0.096 |
| No rectangle between entry and target | True | 846 / 25% / -0.144 | 497 / 25% / -0.163 | 170 / 29% / +0.058 | 179 / 20% / -0.283 |
| Target beyond the prior-day High/Low | False | 1221 / 24% / -0.174 | 734 / 24% / -0.221 | 224 / 28% / +0.008 | 263 / 22% / -0.197 |
| Target beyond the prior-day High/Low | True | 828 / 28% / +0.041 | 495 / 28% / +0.010 | 186 / 33% / +0.269 | 147 / 22% / -0.144 |
| Tap candle closed inside the rectangle | False | 1430 / 25% / -0.117 | 850 / 24% / -0.181 | 269 / 31% / +0.137 | 311 / 23% / -0.164 |
| Tap candle closed inside the rectangle | True | 619 / 27% / -0.017 | 379 / 28% / -0.010 | 141 / 29% / +0.107 | 99 / 21% / -0.221 |

Quartile detail for the strongest Development features:

**Distance to the nearest opposing rectangle (R)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 1.79 to 3.04 | 404 / 27% / -0.051 | 247 / 26% / -0.125 | 77 / 34% / +0.305 | 80 / 22% / -0.165 |
| 3.04 to 25.09 | 404 / 20% / -0.355 | 238 / 21% / -0.369 | 68 / 21% / -0.311 | 98 / 18% / -0.352 |
| 0.87 to 1.79 | 404 / 26% / -0.084 | 248 / 24% / -0.190 | 71 / 34% / +0.284 | 85 / 25% / -0.081 |
| 0.00 to 0.87 | 404 / 27% / -0.001 | 241 / 27% / +0.004 | 94 / 29% / +0.043 | 69 / 26% / -0.077 |

**Candles since the last POC tap**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| -0.00 to 1.00 | 1695 / 26% / -0.111 | 1024 / 25% / -0.147 | 322 / 30% / +0.102 | 349 / 22% / -0.203 |
| 1.00 to 11.00 | 354 / 27% / +0.029 | 205 / 27% / -0.032 | 88 / 31% / +0.215 | 61 / 25% / -0.036 |

**Momentum of the 3 candles before (ATR, + = with the trade)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.28 to 1.23 | 512 / 25% / -0.122 | 308 / 23% / -0.209 | 114 / 32% / +0.201 | 90 / 22% / -0.235 |
| -6.26 to -0.91 | 513 / 25% / -0.145 | 316 / 24% / -0.198 | 75 / 29% / +0.081 | 122 / 23% / -0.149 |
| -0.91 to 0.28 | 512 / 27% / -0.066 | 296 / 25% / -0.169 | 110 / 35% / +0.310 | 106 / 23% / -0.168 |
| 1.23 to 6.35 | 512 / 27% / -0.015 | 309 / 30% / +0.063 | 111 / 24% / -0.102 | 92 / 22% / -0.172 |

**Same-direction candles among the last 5**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| -0.00 to 2.00 | 939 / 25% / -0.127 | 576 / 24% / -0.176 | 160 / 31% / +0.120 | 203 / 22% / -0.182 |
| 2.00 to 3.00 | 547 / 27% / -0.051 | 315 / 24% / -0.208 | 130 / 33% / +0.239 | 102 / 28% / +0.067 |
| 4.00 to 5.00 | 135 / 25% / -0.102 | 86 / 28% / -0.034 | 32 / 25% / -0.071 | 17 / 12% / -0.499 |
| 3.00 to 4.00 | 428 / 27% / -0.042 | 252 / 30% / +0.050 | 88 / 27% / +0.044 | 88 / 18% / -0.391 |

**Tap candle close vs POC (rect. heights, + = toward the trade)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.68 to 1.23 | 512 / 28% / -0.031 | 318 / 25% / -0.160 | 91 / 36% / +0.337 | 103 / 29% / +0.042 |
| 1.23 to 19.59 | 512 / 25% / -0.080 | 296 / 24% / -0.146 | 108 / 33% / +0.275 | 108 / 19% / -0.254 |
| 0.35 to 0.68 | 512 / 24% / -0.199 | 299 / 24% / -0.220 | 108 / 28% / +0.006 | 105 / 18% / -0.349 |
| -0.17 to 0.35 | 513 / 27% / -0.039 | 316 / 28% / +0.008 | 103 / 24% / -0.090 | 94 / 23% / -0.139 |

**Confirmation body / ATR14**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.87 to 1.44 | 512 / 21% / -0.277 | 303 / 20% / -0.323 | 106 / 19% / -0.307 | 103 / 25% / -0.110 |
| 1.44 to 18.21 | 512 / 26% / -0.041 | 315 / 27% / -0.035 | 94 / 34% / +0.304 | 103 / 17% / -0.375 |
| 0.00 to 0.48 | 513 / 30% / +0.051 | 306 / 30% / +0.028 | 98 / 37% / +0.356 | 109 / 23% / -0.159 |
| 0.48 to 0.87 | 512 / 26% / -0.081 | 305 / 25% / -0.186 | 112 / 32% / +0.186 | 95 / 25% / -0.059 |

**Approach speed: 5-candle move before the confirmation (ATR)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| -0.00 to 0.75 | 513 / 24% / -0.161 | 298 / 22% / -0.270 | 115 / 29% / +0.050 | 100 / 25% / -0.077 |
| 1.52 to 2.44 | 512 / 28% / -0.024 | 322 / 30% / +0.070 | 93 / 34% / +0.278 | 97 / 12% / -0.626 |
| 0.75 to 1.52 | 512 / 26% / -0.070 | 307 / 24% / -0.186 | 108 / 29% / +0.081 | 97 / 30% / +0.128 |
| 2.44 to 7.97 | 512 / 25% / -0.093 | 302 / 25% / -0.140 | 94 / 30% / +0.121 | 116 / 22% / -0.147 |

**Trades already taken today**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| -0.00 to 1.00 | 1452 / 26% / -0.099 | 870 / 25% / -0.151 | 285 / 31% / +0.174 | 297 / 22% / -0.206 |
| 1.00 to 2.00 | 357 / 25% / -0.106 | 211 / 24% / -0.180 | 77 / 26% / -0.037 | 69 / 28% / +0.040 |
| 2.00 to 5.00 | 240 / 28% / +0.012 | 148 / 30% / +0.083 | 48 / 31% / +0.105 | 44 / 18% / -0.327 |

## 2. Failed-breakout study - can the return inside the rectangle be seen before entry?

884 of 2049 entries (43%) closed back inside the rectangle within 3 candles (win rate 10.1% vs 37.9% for the rest). Below, AUC of each pre-entry feature for predicting that label (0.5 = no information).

| Feature | AUC for 'failed breakout' all | DEV | VAL | OOS |
|---|---|---|---|---|
| Close beyond the edge (ATR) | 0.274 | 0.269 | 0.250 | 0.320 |
| Close beyond the edge (rect. heights) | 0.287 | 0.281 | 0.263 | 0.331 |
| Entry distance from POC (rect. heights) | 0.303 | 0.294 | 0.278 | 0.358 |
| Stop distance / ATR14 | 0.349 | 0.348 | 0.329 | 0.370 |
| Distance to the nearest opposing rectangle (R) | 0.621 | 0.631 | 0.642 | 0.577 |
| Stop distance (USD) | 0.395 | 0.377 | 0.361 | 0.364 |
| Room to the prior-day High/Low in the trade direction (R) | 0.588 | 0.598 | 0.611 | 0.530 |
| Confirmation range / rectangle height | 0.413 | 0.405 | 0.378 | 0.479 |
| Confirmation body / ATR14 | 0.422 | 0.406 | 0.402 | 0.483 |
| Candles since the last POC tap | 0.417 | 0.412 | 0.412 | 0.444 |
| Confirmation range / ATR14 | 0.431 | 0.413 | 0.407 | 0.508 |
| Tap candle close vs POC (rect. heights, + = toward the trade) | 0.427 | 0.430 | 0.388 | 0.459 |
| Trades already taken today | 0.457 | 0.433 | 0.471 | 0.518 |
| Candles in the current interaction | 0.561 | 0.562 | 0.599 | 0.516 |
| Candles since the zones were created | 0.474 | 0.439 | 0.513 | 0.532 |

Multivariate check (models fitted on Development only, all features together):

| Target | Model | AUC DEV (in-sample) | AUC VAL | AUC OOS |
|---|---|---|---|---|
| failed breakout | logistic | 0.770 | 0.734 | 0.649 |
| failed breakout | gradient boosting | 0.937 | 0.709 | 0.691 |
| win | logistic | 0.634 | 0.499 | 0.471 |
| win | gradient boosting | 0.970 | 0.560 | 0.512 |

Largest standardized logistic coefficients for 'win' (Development fit): positive poc_type_B reject-return +0.12, zone_height +0.13, failed_opp +0.14, mom3_atr +0.15, conf_body_atr +0.16, room_to_pdhl_R +0.18, ep_inside +0.22, zone_pos_range +0.30; negative dist_pdl_zh -0.45, opp_gap_R -0.14, ep_rej -0.14, pen_depth_zh -0.14, touches_today -0.13, conf_range_atr -0.12, poc_type_A touch and go -0.12, zone_h_pct_range -0.12.

## 3. Confirmation candle quality

**Confirmation body / range**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.66 to 0.82 | 512 / 22% / -0.240 | 303 / 22% / -0.262 | 95 / 24% / -0.109 | 114 / 20% / -0.292 |
| 0.82 to 1.00 | 512 / 27% / -0.012 | 318 / 26% / -0.065 | 103 / 28% / +0.068 | 91 / 29% / +0.081 |
| 0.00 to 0.46 | 513 / 28% / -0.004 | 307 / 28% / -0.059 | 99 / 35% / +0.310 | 107 / 23% / -0.138 |
| 0.46 to 0.66 | 512 / 26% / -0.092 | 301 / 26% / -0.130 | 113 / 33% / +0.217 | 98 / 18% / -0.329 |

**Close position in the candle (1 = at the extreme, trade direction)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.86 to 0.94 | 512 / 26% / -0.092 | 294 / 25% / -0.159 | 111 / 30% / +0.112 | 107 / 23% / -0.121 |
| 0.72 to 0.86 | 512 / 27% / -0.076 | 302 / 26% / -0.122 | 106 / 31% / +0.128 | 104 / 24% / -0.151 |
| 0.94 to 1.00 | 512 / 25% / -0.091 | 325 / 25% / -0.144 | 95 / 31% / +0.148 | 92 / 23% / -0.152 |
| 0.07 to 0.72 | 513 / 26% / -0.089 | 308 / 27% / -0.088 | 98 / 30% / +0.120 | 107 / 20% / -0.282 |

**Wick against the trade / range**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.06 to 0.14 | 512 / 26% / -0.092 | 294 / 25% / -0.159 | 111 / 30% / +0.112 | 107 / 23% / -0.121 |
| 0.14 to 0.28 | 512 / 27% / -0.076 | 301 / 26% / -0.118 | 106 / 31% / +0.128 | 105 / 24% / -0.160 |
| -0.00 to 0.06 | 513 / 25% / -0.093 | 326 / 25% / -0.147 | 95 / 31% / +0.148 | 92 / 23% / -0.152 |
| 0.28 to 0.93 | 512 / 26% / -0.087 | 308 / 27% / -0.088 | 98 / 30% / +0.120 | 106 / 20% / -0.275 |

**Confirmation range / ATR14**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.98 to 1.39 | 512 / 24% / -0.187 | 316 / 22% / -0.292 | 98 / 30% / +0.059 | 98 / 24% / -0.096 |
| 2.06 to 23.24 | 512 / 25% / -0.074 | 315 / 26% / -0.090 | 92 / 36% / +0.382 | 105 / 15% / -0.427 |
| 1.39 to 2.06 | 512 / 25% / -0.113 | 289 / 25% / -0.133 | 119 / 24% / -0.135 | 104 / 27% / -0.035 |
| 0.17 to 0.98 | 513 / 29% / +0.026 | 309 / 30% / +0.005 | 101 / 34% / +0.267 | 103 / 23% / -0.147 |

**Close beyond the edge (rect. heights)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.19 to 0.51 | 512 / 27% / -0.074 | 314 / 27% / -0.064 | 94 / 31% / +0.089 | 104 / 22% / -0.252 |
| 1.25 to 25.19 | 512 / 25% / -0.046 | 293 / 26% / -0.045 | 119 / 29% / +0.099 | 100 / 20% / -0.223 |
| -0.00 to 0.19 | 513 / 25% / -0.166 | 319 / 25% / -0.207 | 97 / 27% / -0.024 | 97 / 23% / -0.176 |
| 0.51 to 1.25 | 512 / 26% / -0.061 | 303 / 24% / -0.191 | 100 / 35% / +0.339 | 109 / 25% / -0.068 |

**Close beyond the edge (ATR)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.22 to 0.50 | 512 / 26% / -0.107 | 316 / 23% / -0.238 | 99 / 31% / +0.110 | 97 / 31% / +0.099 |
| 0.50 to 1.03 | 512 / 24% / -0.125 | 304 / 24% / -0.186 | 99 / 31% / +0.199 | 109 / 20% / -0.249 |
| -0.00 to 0.22 | 513 / 27% / -0.114 | 314 / 28% / -0.101 | 97 / 27% / -0.032 | 102 / 22% / -0.229 |
| 1.03 to 24.80 | 512 / 26% / -0.003 | 295 / 27% / +0.021 | 115 / 31% / +0.211 | 102 / 18% / -0.314 |

**Strong vs weak confirmation candle**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| strong (body >= 60%, close in top 20%) | 965 / 25% / -0.086 | 578 / 25% / -0.130 | 199 / 27% / +0.017 | 188 / 25% / -0.057 |
| not strong | 1084 / 26% / -0.088 | 651 / 26% / -0.126 | 211 / 33% / +0.229 | 222 / 20% / -0.280 |

## 4. POC interaction quality

Types (assigned in this precedence): E = price crossed the whole rectangle during the interaction; D = 3+ POC taps today; B = closed outside, came back inside, then broke; C = 3+ candles closed inside; A = tap and breakout within 2 candles of first contact; other = tapped 1-11 candles earlier without those patterns.

**POC interaction type**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| D multiple taps | 251 / 22% / -0.223 | 145 / 22% / -0.240 | 67 / 24% / -0.085 | 39 / 21% / -0.394 |
| E deep cross | 1275 / 26% / -0.095 | 770 / 26% / -0.118 | 244 / 29% / +0.083 | 261 / 22% / -0.193 |
| B reject-return | 120 / 28% / +0.008 | 76 / 33% / +0.164 | 20 / 25% / -0.098 | 24 / 17% / -0.397 |
| A touch and go | 187 / 26% / -0.106 | 104 / 18% / -0.442 | 44 / 41% / +0.538 | 39 / 28% / +0.062 |
| other | 181 / 28% / -0.008 | 112 / 27% / -0.059 | 30 / 33% / +0.162 | 39 / 26% / +0.008 |
| C several bars inside | 35 / 37% / +0.523 | 22 / 32% / +0.374 | 5 / 80% / +2.105 | 8 / 25% / -0.054 |

**Penetration depth into the rectangle**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0.75-1.0 | 249 / 24% / -0.154 | 149 / 21% / -0.318 | 50 / 36% / +0.388 | 50 / 24% / -0.208 |
| >= 1.0 (through) | 1275 / 26% / -0.095 | 770 / 26% / -0.118 | 244 / 29% / +0.083 | 261 / 22% / -0.193 |
| 0.5-0.75 | 247 / 28% / -0.031 | 145 / 28% / -0.007 | 56 / 27% / -0.084 | 46 / 26% / -0.046 |
| nan | 138 / 31% / +0.213 | 76 / 30% / +0.156 | 38 / 32% / +0.228 | 24 / 33% / +0.371 |
| < 0.5 (shallow) | 140 / 21% / -0.295 | 89 / 20% / -0.340 | 22 / 36% / +0.365 | 29 / 10% / -0.656 |

**Candles closed inside the rectangle (interaction)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 1-2 | 751 / 26% / -0.115 | 447 / 26% / -0.138 | 148 / 27% / -0.001 | 156 / 24% / -0.156 |
| 0 | 638 / 25% / -0.132 | 381 / 25% / -0.154 | 127 / 31% / +0.117 | 130 / 18% / -0.309 |
| 3-5 | 366 / 31% / +0.112 | 221 / 28% / -0.051 | 66 / 42% / +0.613 | 79 / 30% / +0.149 |
| 6+ | 294 / 23% / -0.168 | 180 / 24% / -0.144 | 69 / 25% / -0.048 | 45 / 16% / -0.448 |

## 5. Location quality

**Rectangle position in the prior-day range**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| middle | 486 / 21% / -0.290 | 295 / 20% / -0.359 | 90 / 31% / +0.115 | 101 / 17% / -0.448 |
| near prior-day Low | 378 / 26% / -0.061 | 227 / 26% / -0.101 | 62 / 34% / +0.285 | 89 / 21% / -0.203 |
| lower | 332 / 25% / -0.101 | 186 / 27% / -0.058 | 68 / 25% / -0.052 | 78 / 21% / -0.246 |
| upper | 417 / 28% / +0.021 | 262 / 27% / -0.073 | 89 / 33% / +0.251 | 66 / 29% / +0.082 |
| near prior-day High | 436 / 28% / +0.024 | 259 / 29% / +0.004 | 101 / 29% / +0.049 | 76 / 28% / +0.055 |

**Side x position**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| short / middle | 238 / 24% / -0.193 | 156 / 22% / -0.266 | 42 / 31% / +0.080 | 40 / 25% / -0.194 |
| short / near Low | 190 / 27% / -0.036 | 116 / 29% / +0.025 | 33 / 30% / +0.158 | 41 / 17% / -0.366 |
| long / lower | 184 / 26% / -0.088 | 104 / 32% / +0.117 | 34 / 18% / -0.342 | 46 / 17% / -0.365 |
| short / upper | 213 / 26% / -0.053 | 135 / 25% / -0.134 | 41 / 22% / -0.140 | 37 / 35% / +0.340 |
| short / near High | 215 / 25% / -0.138 | 132 / 27% / -0.084 | 44 / 18% / -0.383 | 39 / 26% / -0.047 |
| long / middle | 248 / 19% / -0.382 | 139 / 17% / -0.463 | 48 / 31% / +0.147 | 61 / 11% / -0.615 |
| short / lower | 148 / 25% / -0.117 | 82 / 22% / -0.281 | 34 / 32% / +0.238 | 32 / 25% / -0.076 |
| long / upper | 204 / 30% / +0.098 | 127 / 28% / -0.007 | 48 / 42% / +0.585 | 29 / 21% / -0.246 |
| long / near Low | 188 / 26% / -0.087 | 111 / 23% / -0.232 | 29 / 38% / +0.429 | 48 / 25% / -0.064 |
| long / near High | 221 / 32% / +0.181 | 127 / 31% / +0.096 | 57 / 37% / +0.382 | 37 / 30% / +0.163 |

**Nearest opposing rectangle**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| opposing rectangle 1.5-3R away | 518 / 26% / -0.089 | 311 / 24% / -0.201 | 97 / 32% / +0.227 | 110 / 25% / -0.048 |
| no rectangle in the way | 433 / 29% / +0.046 | 255 / 29% / +0.030 | 100 / 33% / +0.252 | 78 / 22% / -0.166 |
| opposing rectangle beyond the target (> 3R) | 413 / 21% / -0.343 | 242 / 21% / -0.365 | 70 / 23% / -0.220 | 101 / 18% / -0.373 |
| opposing rectangle < 1.5R away | 685 / 27% / -0.016 | 421 / 27% / -0.033 | 143 / 31% / +0.140 | 121 / 24% / -0.140 |

**Very close to another rectangle**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| no rectangle within 1 height | 1771 / 26% / -0.095 | 1064 / 25% / -0.137 | 351 / 31% / +0.174 | 356 / 21% / -0.236 |
| another rectangle within 1 height | 278 / 27% / -0.034 | 165 / 26% / -0.070 | 59 / 24% / -0.156 | 54 / 31% / +0.207 |

**Room to the prior-day High/Low in the trade direction**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 3-6R | 433 / 21% / -0.287 | 256 / 20% / -0.365 | 87 / 28% / -0.019 | 90 / 20% / -0.325 |
| already beyond | 394 / 29% / +0.058 | 235 / 29% / +0.042 | 90 / 33% / +0.266 | 69 / 22% / -0.163 |
| > 6R | 788 / 26% / -0.112 | 478 / 26% / -0.145 | 137 / 28% / +0.025 | 173 / 24% / -0.130 |
| 1.5-3R | 245 / 25% / -0.080 | 149 / 26% / -0.097 | 53 / 32% / +0.228 | 43 / 16% / -0.402 |
| 0-1.5R | 189 / 31% / +0.164 | 111 / 30% / +0.087 | 43 / 35% / +0.326 | 35 / 31% / +0.211 |

## 6. Trade congestion

**POC taps today**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 3+ taps | 720 / 26% / -0.079 | 432 / 25% / -0.150 | 159 / 27% / +0.021 | 129 / 29% / +0.036 |
| 1 tap | 835 / 25% / -0.123 | 488 / 26% / -0.098 | 171 / 30% / +0.087 | 176 / 16% / -0.395 |
| 2 taps | 494 / 27% / -0.039 | 309 / 25% / -0.145 | 80 / 38% / +0.419 | 105 / 25% / -0.076 |

**Prior failed breakouts in the trade direction (today)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0 | 1315 / 26% / -0.072 | 783 / 25% / -0.144 | 271 / 33% / +0.222 | 261 / 23% / -0.161 |
| 1 | 533 / 25% / -0.117 | 328 / 26% / -0.135 | 92 / 29% / +0.118 | 113 / 20% / -0.254 |
| 2+ | 201 / 25% / -0.109 | 118 / 28% / -0.005 | 47 / 17% / -0.407 | 36 / 25% / -0.061 |

**Prior failed breakouts the other way (today)**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0 | 1063 / 26% / -0.107 | 656 / 24% / -0.183 | 190 / 33% / +0.207 | 217 / 24% / -0.155 |
| 1 | 750 / 27% / -0.055 | 433 / 28% / -0.028 | 171 / 28% / +0.050 | 146 / 20% / -0.258 |
| 2+ | 236 / 25% / -0.098 | 140 / 24% / -0.182 | 49 / 29% / +0.078 | 47 / 26% / -0.033 |

**POC crosses in the last 12 candles**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 0-1 | 1546 / 26% / -0.085 | 923 / 26% / -0.096 | 310 / 30% / +0.119 | 313 / 20% / -0.258 |
| 2-3 | 435 / 26% / -0.092 | 265 / 23% / -0.222 | 85 / 28% / +0.074 | 85 / 31% / +0.147 |
| 4+ | 68 / 25% / -0.098 | 41 / 22% / -0.252 | 15 / 40% / +0.563 | 12 / 17% / -0.400 |

**Colour changes in the last 6 candles**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 3-4 | 1017 / 26% / -0.086 | 601 / 25% / -0.152 | 211 / 32% / +0.205 | 205 / 22% / -0.191 |
| 0-2 | 864 / 25% / -0.109 | 525 / 26% / -0.097 | 164 / 26% / -0.035 | 175 / 22% / -0.214 |
| 5 | 168 / 29% / +0.018 | 103 / 25% / -0.145 | 35 / 37% / +0.405 | 30 / 30% / +0.123 |

**Rectangle touches today**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| 3-5 | 614 / 27% / -0.059 | 383 / 27% / -0.085 | 101 / 33% / +0.206 | 130 / 23% / -0.187 |
| 1-2 | 759 / 25% / -0.112 | 440 / 25% / -0.156 | 160 / 32% / +0.196 | 159 / 19% / -0.299 |
| 6-10 | 390 / 25% / -0.086 | 221 / 23% / -0.219 | 94 / 29% / +0.123 | 75 / 28% / +0.045 |
| 11+ | 286 / 26% / -0.084 | 185 / 27% / -0.042 | 55 / 22% / -0.217 | 46 / 24% / -0.097 |

**Clean vs choppy interaction**

| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| choppy / repeated | 1065 / 26% / -0.070 | 649 / 25% / -0.136 | 212 / 28% / +0.064 | 204 / 27% / +0.002 |
| in between | 681 / 26% / -0.082 | 406 / 27% / -0.075 | 136 / 32% / +0.184 | 139 / 17% / -0.363 |
| clean first interaction | 303 / 24% / -0.160 | 174 / 24% / -0.222 | 62 / 34% / +0.211 | 67 / 18% / -0.343 |

## 7. Entry quality score (fitted on Development only; buckets = Development terciles of the score)

**Logistic-regression score (all features)**

| Bucket | Period | Trades | Win rate | Gross R | Net R | Avg R | PF |
|---|---|---|---|---|---|---|---|
| Low | all | 761 | 20.6% | -140.4 | -233.5 | -0.184 | 0.77 |
| Low | DEV | 410 | 16.1% | -149.0 | -215.4 | -0.363 | 0.57 |
| Low | VAL | 173 | 28.9% | +27.8 | +12.2 | +0.161 | 1.23 |
| Low | OOS | 178 | 23.0% | -19.2 | -30.3 | -0.108 | 0.86 |
| Medium | all | 634 | 26.3% | +36.0 | -42.9 | +0.057 | 1.08 |
| Medium | DEV | 409 | 24.0% | -16.5 | -76.8 | -0.040 | 0.95 |
| Medium | VAL | 114 | 37.7% | +58.9 | +48.2 | +0.517 | 1.83 |
| Medium | OOS | 111 | 23.4% | -6.5 | -14.4 | -0.058 | 0.92 |
| High | all | 654 | 31.5% | +174.2 | +97.9 | +0.266 | 1.39 |
| High | DEV | 410 | 36.6% | +194.1 | +134.8 | +0.473 | 1.74 |
| High | VAL | 123 | 25.2% | +1.1 | -8.6 | +0.009 | 1.01 |
| High | OOS | 121 | 20.7% | -21.0 | -28.3 | -0.174 | 0.78 |

**Gradient-boosting score (all features)**

| Bucket | Period | Trades | Win rate | Gross R | Net R | Avg R | PF |
|---|---|---|---|---|---|---|---|
| Low | all | 670 | 9.6% | -423.5 | -509.4 | -0.632 | 0.31 |
| Low | DEV | 410 | 0.2% | -410.2 | -471.8 | -1.001 | 0.01 |
| Low | VAL | 138 | 26.8% | +10.0 | -4.7 | +0.072 | 1.10 |
| Low | OOS | 122 | 21.3% | -23.3 | -32.9 | -0.191 | 0.77 |
| Medium | all | 647 | 12.1% | -334.1 | -413.4 | -0.516 | 0.42 |
| Medium | DEV | 409 | 4.2% | -341.1 | -401.8 | -0.834 | 0.13 |
| Medium | VAL | 124 | 27.4% | +13.8 | +2.8 | +0.111 | 1.15 |
| Medium | OOS | 114 | 23.7% | -6.8 | -14.3 | -0.060 | 0.92 |
| High | all | 732 | 53.0% | +827.4 | +744.2 | +1.130 | 3.40 |
| High | DEV | 410 | 72.2% | +779.9 | +716.3 | +1.902 | 7.84 |
| High | VAL | 148 | 35.8% | +64.1 | +53.7 | +0.433 | 1.67 |
| High | OOS | 174 | 22.4% | -16.6 | -25.7 | -0.095 | 0.88 |

**Simple score = number of the 0 consistent conditions met**

| Bucket | Period | Trades | Win rate | Gross R | Net R | Avg R | PF |
|---|---|---|---|---|---|---|---|
| 0 | all | 2049 | 25.9% | +69.7 | -178.5 | +0.034 | 1.05 |
| 0 | DEV | 1229 | 25.5% | +28.6 | -157.4 | +0.023 | 1.03 |
| 0 | VAL | 410 | 30.2% | +87.8 | +51.8 | +0.214 | 1.30 |
| 0 | OOS | 410 | 22.4% | -46.7 | -72.9 | -0.114 | 0.86 |

No feature was consistent across Development and Validation, so no simple score could be formed.

## C. Filter experiments (each filter alone, applied to the V1 trade list; thresholds = Development terciles, direction from Development)

| Filter | Trades removed | Losers removed | Winners removed | Win rate before -> after | Net R before -> after | DEV avg net R before -> after | VAL | OOS |
|---|---|---|---|---|---|---|---|---|
| remove Target beyond the prior-day High/Low = False | 1221 | 926 | 295 | 25.9% -> 28.4% | -178 -> +34 | -0.128 -> +0.010 | +0.126 -> +0.269 | -0.178 -> -0.144 |
| remove Rectangle type = HVN | 1316 | 985 | 331 | 25.9% -> 27.1% | -178 -> -21 | -0.128 -> -0.050 | +0.126 -> +0.185 | -0.178 -> -0.178 |
| remove No rectangle between entry and target = True | 846 | 637 | 209 | 25.9% -> 26.7% | -178 -> -57 | -0.128 -> -0.105 | +0.126 -> +0.175 | -0.178 -> -0.096 |
| remove Side = short | 1004 | 749 | 255 | 25.9% -> 26.3% | -178 -> -67 | -0.128 -> -0.110 | +0.126 -> +0.267 | -0.178 -> -0.265 |

## D. Minimal entry rule

No filter improved both Development and Validation while keeping 60% of the trades. No minimal rule is proposed.

## E. V3 backtest (exact engine runs: the filter is applied at signal time, the rectangle is not consumed by a blocked setup)

| Variant | All (n / win / net R / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|
| V1 | 2049 / 26% / -178 / -0.087 | 1229 / 26% / -157 / -0.128 | 410 / 30% / +52 / +0.126 | 410 / 22% / -73 / -0.178 |
| V2 constraints (min stop 4 USD + target beyond by 1R) | 1199 / 26% / -26 / -0.022 | 615 / 25% / -32 / -0.051 | 289 / 28% / +25 / +0.086 | 295 / 24% / -19 / -0.064 |

## F. Out-of-sample result

### Addendum: trades sorted by the failed-breakout model (fitted on Development)

| Predicted FB risk | Period | Trades | Actually failed | Win rate | Avg net R | Median stop (USD) |
|---|---|---|---|---|---|---|
| low FB risk | all | 617 | 17% | 28.2% | +0.052 | 4.88 |
| low FB risk | DEV | 410 | 18% | 29.3% | +0.073 | 3.52 |
| low FB risk | VAL | 127 | 14% | 30.7% | +0.186 | 8.82 |
| low FB risk | OOS | 80 | 18% | 18.8% | -0.265 | 16.54 |
| medium | all | 587 | 43% | 24.4% | -0.166 | 2.63 |
| medium | DEV | 409 | 45% | 24.4% | -0.184 | 2.05 |
| medium | VAL | 95 | 38% | 30.5% | +0.100 | 4.93 |
| medium | OOS | 83 | 37% | 16.9% | -0.385 | 8.45 |
| high FB risk | all | 845 | 62% | 25.2% | -0.134 | 3.44 |
| high FB risk | DEV | 410 | 70% | 22.9% | -0.273 | 1.82 |
| high FB risk | VAL | 188 | 57% | 29.8% | +0.099 | 4.71 |
| high FB risk | OOS | 247 | 54% | 25.5% | -0.080 | 7.20 |

Strongest drivers of the failed-breakout prediction (standardized coefficients): more likely to fail with zone_height_atr (+0.25), opp_gap_R (+0.23), failed_opp (+0.19), atr14 (+0.18), trend20_atr (+0.18); less likely with conf_ext_atr (-0.66), risk_atr (-0.50), dist_pdh_zh (-0.26), conf_ext_zh (-0.25), entry_dist_poc_zh (-0.23).

## Near-miss check on the two buckets that were below average in all three periods

Neither bucket passed the pre-registered rule (type D lost to type A as the worst Development category; the opposing-rectangle distance had AUC 0.483 in Validation, under the 0.03 bar). They are reported here because they are the only pre-entry conditions that were worse than average in Development, Validation AND Out-of-sample. Exact engine runs (the blocked setup does not consume the rectangle):

| Variant | Trades removed (W / L) | All (n / win / net R / avg net R) | DEV | VAL | OOS |
|---|---|---|---|---|---|
| V1 | - | 2049 / 26% / -178 / -0.087 | 1226 / 26% / -154 / -0.126 | 413 / 30% / +48 / +0.117 | 410 / 22% / -73 / -0.178 |
| remove POC interaction type D (3+ taps without crossing the rectangle) | 251 (56 / 195) | 2080 / 27% / -129 / -0.062 | 1265 / 27% / -103 / -0.082 | 401 / 30% / +49 / +0.123 | 414 / 22% / -75 / -0.182 |
| remove setups whose nearest opposing rectangle lies beyond the 3R target | 413 (85 / 328) | 2002 / 26% / -148 / -0.074 | 1200 / 26% / -128 / -0.106 | 406 / 30% / +48 / +0.118 | 396 / 22% / -68 / -0.171 |

**Truly unseen data.** While this study ran, 21 monthly files that were missing when V1 was frozen were added to the data folder (2021-10, 2021-11, 2021-12, 2022-01, 2022-02, 2022-03, 2022-05, 2022-06, 2022-07, 2022-09, 2023-01, 2023-05, 2023-08, 2024-01, 2024-03, 2024-04, 2024-09, 2024-10, 2024-11, 2025-01, 2025-12). None of them was used in V1, V2 or V3. Running V1 and the two near-miss filters over the full folder and keeping only trades in those months:

| Variant | Trades | Win rate | Gross R | Net R | Avg net R | 2021 | 2022 | 2023 | 2024 | 2025 (n / avg net R) |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 | 1151 | 23.5% | -63.8 | -236.2 | -0.205 | 176 / -0.274 | 383 / -0.058 | 161 / -0.368 | 318 / -0.251 | 113 / -0.234 |
| remove POC interaction type D (3+ taps without crossing the rectangle) | 1164 | 24.4% | -29.3 | -209.7 | -0.180 | 175 / -0.205 | 395 / -0.041 | 156 / -0.480 | 328 / -0.156 | 110 / -0.286 |
| remove setups whose nearest opposing rectangle lies beyond the 3R target | 1133 | 24.0% | -43.3 | -195.3 | -0.172 | 175 / -0.211 | 389 / -0.095 | 146 / -0.258 | 312 / -0.205 | 111 / -0.175 |

## Findings

### A. Entry Failure Report - what losing trades have in common

- Nothing measurable before entry. Across 55 numeric pre-entry features the largest separation between losers and winners over all 2,049 trades is AUC 0.466 (distance to the nearest opposing rectangle; standard error 0.014), i.e. about 2 standard errors from no information, and no feature reaches AUC 0.54/0.46. Not one feature keeps the same direction with |AUC-0.5| >= 0.03 in both Development and Validation.
- The medians of losers and winners are nearly identical for tap distance, penetration depth, touches, candles inside, candle body, wicks, range, breakout distance, stop size, rectangle height, prominence, volume share, POC position, momentum, 20/50-candle structure, approach speed, volatility and time of day (table in section A/B).
- Categorical near-misses: POC interaction type D (3+ taps without crossing the rectangle) wins 22.1% / 23.9% / 20.5% in DEV / VAL / OOS against 25.5% / 30.2% / 22.4% for all trades, and setups whose nearest opposing rectangle lies beyond the 3R target win 21% / 23% / 18%. Both are small (251 and 413 trades) and their effect is 0.01-0.03R per trade, inside the noise band.

### B. Entry Success Report - what winning trades have in common

- Equally little. Long entries from the prior Day High rectangle (32% / 31% / 30%) and setups whose target lies beyond the prior day's range (28.3% / 33.3% / 22.4%) are the only groups above average in more than one period, and both are the V2 target-location finding restated, not a new entry characteristic.
- 'Strong' confirmation candles (body >= 60% of range, close in the top 20%) win 25% against 26% for weak ones (DEV 25/26, VAL 27/33, OOS 25/20). Close position, wick size and breakout distance show no monotone pattern in any period. Smaller candles relative to ATR win more in DEV and VAL (30%, 34%) and less in OOS (23%).
- POC interaction types are unstable: 'touch and go' wins 18% in DEV, 41% in VAL, 28% in OOS; 'reject-return' 33% / 25% / 17%. 'Several candles inside' is 37% on 35 trades. Clean first interactions (24%) are not better than choppy ones (26%).
- Location: rectangles near the prior Day High are the only position non-negative in all three periods (+0.00 / +0.05 / +0.06R); the middle of the range is worst overall (21%) but flips positive in Validation.

### 2. Failed breakouts - can they be seen before entry?

- The label itself, yes: a logistic model fitted on Development predicts 'closes back inside within 3 candles' with AUC 0.77 in DEV, 0.73 in VAL and 0.65 out of sample; its lowest-risk tercile really does fail only 14-18% of the time against 54-70% for the highest. The drivers are mechanical: a close far beyond the edge, a large stop relative to ATR and a tall rectangle make it harder to close back inside.
- The loss, no: the same low-risk tercile wins 29.3% / 30.7% / 18.8% (DEV / VAL / OOS) - no better than everything else and worst out of sample. Trades that do not fail immediately still lose at the base rate later. The failed breakout is how a coin-flip entry loses quickly, not a separate population that can be excluded.

### C. Filter experiments

- With the pre-registered rule (Development-tercile threshold, improvement in both DEV and VAL) no numeric feature qualified, so the filter table is empty by construction rather than by omission. The two near-miss filters are shown above with full accounting.
- Type D removed: 251 trades (56 winners, 195 losers); exact run 25.9% -> 26.6% win rate, -178 -> -129R net; unseen months -0.205 -> -0.180R per trade.
- Opposing rectangle beyond target removed: 413 trades (85 winners, 328 losers); exact run 25.9% -> 25.9%, -178 -> -148R; unseen months -0.205 -> -0.172R per trade.

### 7. Entry quality score

- Logistic regression on all features: AUC 0.634 in Development (in-sample), 0.499 in Validation, 0.471 out of sample. Its 'High' tercile wins 36.6% in DEV (+0.47R), 25.2% in VAL (+0.01R) and 20.7% out of sample (-0.17R) - the best in-sample bucket becomes the worst unseen bucket. Gradient boosting: 0.970 / 0.560 / 0.512, same collapse. A score built from consistent single features could not be formed because there were none.
- One reason the fitted thresholds cannot transfer: the median stop is 2-4 USD in Development and 7-17 USD in the 2026 out-of-sample months, because gold's volatility tripled. Any absolute threshold learnt in 2021-2024 describes a different market.

### D. Minimal entry rule

None is proposed. No pre-entry condition passed the rule, and the two near-misses change the result by 0.01-0.03R per trade, which is inside one standard error (0.04R) of the mean trade. Adopting them would be fitting to noise.

### E. V3 backtest

V3 = V1 (no filter adopted). For reference, the V2 constraints (minimum stop 4 USD, target beyond the prior-day range by 1R) give 2049 -> 1,199 trades and -0.087 -> -0.022R per trade net, and the near-miss filters are tabulated above.

### F. Out-of-sample result

Nothing to carry forward survived: every entry-quality signal found in Development (single features, the multivariate score, the candle and interaction categories) was flat or inverted in Validation or Out-of-sample, and the two near-misses that were consistent across the three periods moved the truly unseen 21 months by +0.025 and +0.033R per trade.

### Conclusion

The information available at the close of the confirmation candle does not distinguish good setups from bad ones. Every feature the specification asked for was measured; none carries transferable information about the outcome, and a model given all of them at once is a coin flip out of sample. The failed breakout can be predicted, but predicting it does not predict the loss. No entry filter is proposed. Per the brief, the next step is exit research (1:2, 1:2.5, break-even, trailing, partial exits), with the caveat from the V1 target curve that no fixed target from 0.5R to 3R changed the expectancy on this trade set.
