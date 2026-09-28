# Backtest - fixed 8 USD stop, 24 USD target, stop to entry at +8 USD, 0.02 lot

Data: all 60 monthly Dukascopy XAUUSD M1 files on disk, 2021-09-01 to 2026-09-25 (UTC), 5-min entries as in V1 (previous-day rectangles, POC tap, confirmation close). Only the stop and target changed: stop = entry -/+ 8 USD, target = entry +/- 24 USD, and once price is 8 USD in profit the stop moves to the entry price. One position at a time. 0.02 lot = 2 oz, so one full loss = -16 USD, one target = +48 USD. Costs = one spread per trade (0.25-0.50 USD/oz by year, x 2 oz), shown separately.

Execution rule: the stop is checked before the target inside every 1-minute candle; the break-even move is applied from the candle after +8 USD was reached; gaps fill at the open (the most conservative reading of the data).

| Variant | Trades | Wins / BE / Losses | Win rate | Gross R | Net R | Avg net R | PF | Gross USD | Spread USD | Net USD | Max DD USD | Longest losing run | Median hold (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule: 8 USD stop, 24 USD target, stop to entry at +8 USD | 2452 | 427 / 766 / 1259 | 17.4% | +39.8 | -73.2 | -0.030 | 1.03 | +637 | 1,809 | -1,172 | 1,509 | 29 | 160 |
| Same without the break-even move | 2099 | 529 / 0 / 1570 | 25.2% | +29.0 | -70.1 | -0.033 | 1.02 | +465 | 1,587 | -1,122 | 1,580 | 20 | 166 |
| V1 rule for reference (rectangle stop, 3R) | 3217 | 813 / 0 / 2404 | 25.3% | +40.3 | -382.1 | -0.119 | 1.02 | +1,210 | 2,229 | -1,019 | 1,813 | 21 | 53 |

## The rule, year by year

| Year | Trades | Win rate | Break-even exits | Net R | Net USD | Max DD USD |
|---|---|---|---|---|---|---|
| 2021 | 106 | 15.1% | 33 | -12.3 | -197 | 259 |
| 2022 | 363 | 19.3% | 118 | +24.5 | +393 | 294 |
| 2023 | 356 | 14.6% | 102 | -58.7 | -939 | 1,030 |
| 2024 | 450 | 18.0% | 141 | -2.9 | -47 | 476 |
| 2025 | 658 | 17.5% | 232 | +5.1 | +82 | 622 |
| 2026 | 519 | 17.9% | 140 | -29.0 | -464 | 1,160 |
| last 12 months | 711 | 18.4% | 193 | -24.6 | -394 | 1,160 |

## Year by year for the two comparison variants (net USD)

| Year | Same without break-even | V1 rectangle stop, 3R |
|---|---|---|
| 2021 | -278 (75 trades) | -209 (237 trades) |
| 2022 | -235 (290 trades) | -15 (650 trades) |
| 2023 | -415 (247 trades) | -236 (586 trades) |
| 2024 | -363 (366 trades) | -995 (577 trades) |
| 2025 | +372 (604 trades) | +801 (683 trades) |
| 2026 | -204 (517 trades) | -366 (484 trades) |

Break-even effect (same entries, independent trades): the move to entry saved 492 trades that would have lost 16 USD and killed 168 trades that would have reached +48 USD; net -12R = -192 USD before costs.

Exit reasons for the rule: SL 1251, TSL 774, TP 427 (TSL = stopped at entry after the break-even move).
