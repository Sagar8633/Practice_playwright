# GOLD EA (SimpleSMA18Bot v1.00) — systematic multi-timeframe backtest report

Prepared 2026-09-26. Engine, data and every intermediate table are in `Vaibhav/research/` (see `README.md`). Experiment log: `results/experiment_log.csv` (489 runs).

## 1. Executive summary

**What was tested.** The untouched EA on M1, M5, M15 and D1 over six years of Dukascopy XAUUSD data (Sep 2020 - Sep 2026, D1 also 2003 - 2026) with XM GOLD costs, then 26 entry filters, 22 stop variants, 30 exit stacks, 20 trailing settings, time exits, a 456-configuration walk-forward grid, parameter sensitivity, Monte Carlo and a $200 survivability analysis: 500+ logged backtests, all with the same pre-declared development / validation / out-of-sample split and acceptance rule.

**What was found.**
1. **M1 fails.** -$30,212 per 0.01 lot in six years (PF 0.55, 54,900 trades). Gross result before spread and slippage is +$877, i.e. zero; XM's spread is 56% of the one-minute ATR and 75% of the median trade's best profit. No filter, stop, exit, trailing distance or time exit is positive in any period. Every one of 120 walk-forward configurations is negative in every split.
2. **M5 fails.** -$4,977 (PF 0.79). The best filter stack (New York hours + volatility >= 1 + rising ADX) reaches -$128 with a positive 2025-26 slice only; 0 of 120 configurations are positive in development or validation.
3. **M15 is break-even before costs and a loser after them.** -$984 (PF 0.92; +$720 at a 25-point spread). Single changes (volatility filter, removing the MA18 exit, pure Chandelier or pure trailing) reach zero to +$717, but all are negative in 2020-2023 and 0 of 120 grid configurations are positive in all three splits; 91% are positive out of sample only because 2025-26 was a one-way gold rally. No statistically robust configuration identified.
4. **D1: the ~3x in 1.5 years is real but conditional.** It reproduces only with the 1% SL filter switched off (the EA as provided takes zero D1 trades on $200 and six on $5,000); the shipped rules made +$619 in 2020-2026 with 2025 alone worth +$639, and only +$121 over 23 years (8 of 23 years positive). The one component that changes D1 materially is the exit: volatility-scaled protection (Chandelier 22 x 3 or 2x ATR trailing from the first tick) with the ADX >= 25 filter turns +$619 into +$1,575 (PF 11.7, max drawdown $65) and is positive in development, validation and out-of-sample; it beats the shipped exit in every 8-year window since 2003 but is itself flat over 2003-2020, so it is a robust improvement of a regime-dependent strategy, not a proven edge. The EA's own 1% rule requires about $9,000 for this strategy at the minimum lot; on $200 every trade risks 15-130% of the account.
5. **Why winners become losers (Q5).** The $5.00 break-even stop with a $0.10 offset. On D1 it closed 70 of 85 trades that were on average $37 in profit (one had been $977 in profit) for a net of -$81; on M15 the 1,179 break-even exits averaged $10 of unrealized profit and returned $0; 62% of M15 losers were at least $1 in profit first, and the median trade gives back 100% of its best profit. On D1 volatility-scaled protection fixes this; on the lower timeframes nothing does, because the gross edge is zero and the costs are not.

**Recommendation.** Do not run this EA on M1, M5 or M15 with any of the tested settings. If D1 is traded, use the modified exit (section 17), keep the SL% filter and fund the account so that it passes (about $9,000 at 0.01 lot), or accept that a $200 account is a 40-130%-per-trade gamble whose historical survival depends on the 2024-2026 rally. Forward-test on the demo account before any change to the live one.

## 2. Data quality

Primary dataset: Dukascopy XAUUSD M1 bid, 2020-09-01 03:00:00 to 2026-09-25 16:37:00 server time (2,151,947 bars, all 73 months present, 0 duplicates, 0 invalid OHLC rows, 0 non-positive prices, 327 weekend gaps, 1269 intraweek gaps >= 1 h of which nearly all are the daily 1-hour rollover break, 26 one-minute moves > 1%, none > 3%). Long history: Dukascopy H1 2003-05-05 03:00:00 to 2026-09-25 16:00:00 (141,378 bars) for D1 before Sep 2020.
Broker check on the XM M15 overlap (Jul 2022 - Sep 2026, 98,983 bars): median |close difference| $0.05, p90 $0.17; XM ranges are 0.997x Dukascopy's; volume-filter agreement between XM tick volume and Dukascopy traded volume 82% (pass rates 46% vs 43%). Prices are therefore feed-specific: the MT5 tester on XM would not reproduce this trade list one for one.
Spread: XM's own GOLD spread by year and server hour (M15 close medians {'2022': 25.0, '2023': 25.0, '2024': 28.0, '2025': 30.0, '2026': 40.0}, M1 2026 median 51.0 pts, p99 59.0 pts) scaled to M1-equivalent; before 2022 the 2022 profile is assumed. Transformations: prices rounded to 0.01, UTC shifted to XM server time (EET with EU DST), bars outside XM's 01:00-23:59 session dropped (no gap filling, no synthetic bars). Full audit: `AUDIT.md`.

## 3. EA components

The EA (`EA_MAP.md`) is an 18/200 SMA breakout: two closes above both averages with the fast one above the slow one and volume above its 20-bar mean place a **buy stop** 10 points above the last high with the stop at the last confirmed swing low (strength 2, 100-bar search). The order never expires; it is cancelled only when a close crosses back through the 18 SMA, and its stop is ratcheted to each newer swing. Once filled: a **break-even** move at +500 points ($5.00) to fill +10 points, **swing protection** (swing low minus 50 points, tighten-only) that updates only while the trade is at least 500 points in profit, and a **market exit** on the first tick after a close through the 18 SMA. Chandelier and fixed trailing exist as alternative protection modes; the failed-breakout exit and partial close are dead code. **The lot is fixed at 0.01 and the 'MaximumSLPercent = 1%' input is a gate, not position sizing**: a setup is skipped when the swing-stop loss at 0.01 lot exceeds 1% of balance, which on $200 means every stop wider than $2.00. The ADX and session filters exist but are off by default.

## 4. Baseline results (untouched EA)

Strategy view = fixed 0.01 lot, no SL% filter, nominal balance (what the rules do, in $ per 0.01 lot = per oz). Account views = $200 with the EA as provided (SL% filter on) and with the filter off.

| TF | view | cost | trades | net $ | PF | win % | exp $ | maxDD $ | maxDD % | end bal $ | ruin | blocked by 1% rule | avg risk $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | strategy | A_low | 56640 | -13114.03 | 0.76 | 27.40 | -0.23 | 13151.97 | 13.20 | 86885.97 | False | 0.00 | 3.14 |
| M1 | strategy | B_real | 54900 | -30212.35 | 0.55 | 20.60 | -0.55 | 30239.03 | 30.20 | 69787.65 | False | 0.00 | 3.33 |
| M1 | strategy | C_stress | 51207 | -58295.55 | 0.34 | 14.20 | -1.14 | 58313.50 | 58.30 | 41704.45 | False | 0.00 | 3.69 |
| M1 | ea_200 | A_low | 702 | -193.49 | 0.40 | 14.50 | -0.28 | 193.49 | 96.70 | 6.51 | False | 440778.00 | 0.73 |
| M1 | ea_200 | B_real | 349 | -196.36 | 0.19 | 7.20 | -0.56 | 196.36 | 98.20 | 3.64 | False | 442883.00 | 0.76 |
| M1 | ea_200 | C_stress | 172 | -196.46 | 0.05 | 1.70 | -1.14 | 196.46 | 98.20 | 3.54 | False | 443968.00 | 0.97 |
| M1 | ea_200_nofilt | A_low | 668 | -198.50 | 0.62 | 27.40 | -0.30 | 198.50 | 99.20 | 1.50 | False | 0.00 | 2.38 |
| M1 | ea_200_nofilt | B_real | 284 | -199.25 | 0.36 | 18.70 | -0.70 | 199.25 | 99.60 | 0.75 | False | 0.00 | 2.58 |
| M1 | ea_200_nofilt | C_stress | 132 | -198.98 | 0.14 | 11.40 | -1.51 | 198.98 | 99.50 | 1.02 | False | 0.00 | 3.39 |
| M5 | strategy | A_low | 12422 | -707.56 | 0.97 | 36.30 | -0.06 | 2309.69 | 2.30 | 99292.44 | False | 0.00 | 7.31 |
| M5 | strategy | B_real | 12320 | -4977.42 | 0.79 | 25.80 | -0.40 | 5314.60 | 5.30 | 95022.58 | False | 0.00 | 7.55 |
| M5 | strategy | C_stress | 12009 | -11405.47 | 0.60 | 18.70 | -0.95 | 11412.23 | 11.40 | 88594.53 | False | 0.00 | 7.78 |
| M5 | ea_200 | A_low | 867 | -160.38 | 0.73 | 19.00 | -0.18 | 183.60 | 82.30 | 39.62 | False | 81903.00 | 1.18 |
| M5 | ea_200 | B_real | 469 | -170.36 | 0.58 | 14.90 | -0.36 | 170.36 | 85.20 | 29.64 | False | 84304.00 | 1.13 |
| M5 | ea_200 | C_stress | 182 | -175.74 | 0.27 | 5.50 | -0.97 | 175.74 | 87.90 | 24.26 | False | 86067.00 | 1.17 |
| M5 | ea_200_nofilt | A_low | 356 | -198.50 | 0.64 | 25.00 | -0.56 | 203.93 | 99.30 | 1.50 | False | 0.00 | 4.24 |
| M5 | ea_200_nofilt | B_real | 185 | -199.04 | 0.46 | 22.20 | -1.08 | 201.70 | 99.50 | 0.96 | False | 0.00 | 5.03 |
| M5 | ea_200_nofilt | C_stress | 143 | -200.29 | 0.41 | 18.20 | -1.40 | 200.56 | 100.10 | -0.29 | True | 0.00 | 5.64 |
| M15 | strategy | A_low | 4571 | 719.55 | 1.06 | 48.70 | 0.16 | 611.44 | 0.60 | 100719.55 | False | 0.00 | 13.56 |
| M15 | strategy | B_real | 4559 | -983.88 | 0.92 | 32.90 | -0.22 | 1581.42 | 1.60 | 99016.12 | False | 0.00 | 13.75 |
| M15 | strategy | C_stress | 4513 | -3535.11 | 0.74 | 19.60 | -0.78 | 3724.20 | 3.70 | 96464.89 | False | 0.00 | 14.06 |
| M15 | ea_200 | A_low | 289 | -45.91 | 0.84 | 20.10 | -0.16 | 68.09 | 30.60 | 154.09 | False | 28542.00 | 1.49 |
| M15 | ea_200 | B_real | 166 | -83.52 | 0.56 | 17.50 | -0.50 | 83.52 | 41.80 | 116.48 | False | 29219.00 | 1.41 |
| M15 | ea_200 | C_stress | 81 | -115.12 | 0.08 | 6.20 | -1.42 | 115.12 | 57.60 | 84.88 | False | 29730.00 | 1.43 |
| M15 | ea_200_nofilt | A_low | 607 | -198.81 | 0.84 | 37.10 | -0.33 | 227.33 | 99.50 | 1.19 | False | 0.00 | 7.30 |
| M15 | ea_200_nofilt | B_real | 404 | -199.83 | 0.78 | 37.60 | -0.49 | 199.83 | 99.90 | 0.17 | True | 0.00 | 8.08 |
| M15 | ea_200_nofilt | C_stress | 119 | -200.42 | 0.45 | 19.30 | -1.68 | 200.42 | 100.20 | -0.42 | True | 0.00 | 8.34 |
| D1 | strategy | A_low | 85 | 894.51 | 5.02 | 94.10 | 10.52 | 150.17 | 0.20 | 100894.51 | False | 0.00 | 118.97 |
| D1 | strategy | B_real | 85 | 619.14 | 2.95 | 49.40 | 7.28 | 179.40 | 0.20 | 100619.14 | False | 0.00 | 119.07 |
| D1 | strategy | C_stress | 90 | 533.32 | 2.38 | 16.70 | 5.93 | 212.17 | 0.20 | 100533.32 | False | 0.00 | 115.83 |
| D1 | ea_200 | A_low | 0 | 0.00 | - | - | - | 0.00 | 0.00 | 200.00 | 0.00 | 370.00 | - |
| D1 | ea_200 | B_real | 0 | 0.00 | - | - | - | 0.00 | 0.00 | 200.00 | 0.00 | 370.00 | - |
| D1 | ea_200 | C_stress | 0 | 0.00 | - | - | - | 0.00 | 0.00 | 200.00 | 0.00 | 370.00 | - |
| D1 | ea_200_nofilt | A_low | 85 | 894.51 | 5.02 | 94.10 | 10.52 | 150.17 | 49.80 | 1094.51 | False | 0.00 | 118.97 |
| D1 | ea_200_nofilt | B_real | 85 | 619.14 | 2.95 | 49.40 | 7.28 | 179.40 | 72.60 | 819.14 | False | 0.00 | 119.07 |
| D1 | ea_200_nofilt | C_stress | 38 | -199.94 | 0.38 | 23.70 | -5.26 | 206.96 | 100.00 | 0.06 | True | 0.00 | 71.88 |

Path-assumption sensitivity (strategy, B_real, 'worst' intrabar ordering): M1 -37534.86 vs -30212.35; M5 -7882.92 vs -4977.42; M15 -2716.34 vs -983.88; D1 610.45 vs 619.14. D1 2003-2026 on the H1 path: 121.32 net, PF 1.065 (329 trades); the same rules on the H1 path over 2020-2026 give 531.51 vs 619.14 on the M1 path (path-resolution error ~15%).

### By year (strategy view, realistic costs)

**M1**: 2020: -1551.96 (PF 0.43, 2949 tr); 2021: -4849.89 (PF 0.36, 8747 tr); 2022: -4793.36 (PF 0.38, 8972 tr); 2023: -4223.16 (PF 0.37, 8080 tr); 2024: -4664.12 (PF 0.47, 8769 tr); 2025: -5593.86 (PF 0.62, 9680 tr); 2026: -4536.0 (PF 0.76, 7703 tr)

**M5**: 2020: -432.96 (PF 0.61, 656 tr); 2021: -1249.98 (PF 0.55, 1960 tr); 2022: -1054.03 (PF 0.64, 1973 tr); 2023: -767.96 (PF 0.68, 1849 tr); 2024: -1007.3 (PF 0.7, 1961 tr); 2025: -661.83 (PF 0.88, 2137 tr); 2026: 196.64 (PF 1.03, 1784 tr)

**M15**: 2020: -106.1 (PF 0.81, 224 tr); 2021: -340.1 (PF 0.75, 681 tr); 2022: -382.97 (PF 0.75, 713 tr); 2023: -232.88 (PF 0.82, 660 tr); 2024: -220.35 (PF 0.87, 704 tr); 2025: -181.63 (PF 0.93, 834 tr); 2026: 480.16 (PF 1.16, 743 tr)

**D1**: 2021: -31.48 (PF 0.08, 7 tr); 2022: 56.56 (PF 2.03, 15 tr); 2023: -157.44 (PF 0.12, 16 tr); 2024: 128.22 (PF 6.91, 18 tr); 2025: 638.91 (PF 53.55, 16 tr); 2026: -15.63 (PF 0.0, 13 tr)

**D1 2003-2026**: 2004: -104.48; 2005: -94.56; 2006: 6.0; 2007: -66.6; 2008: 52.71; 2009: -89.9; 2010: -32.64; 2011: 137.81; 2012: -101.93; 2013: 138.39; 2014: -5.36; 2015: 9.52; 2016: -140.78; 2017: -46.87; 2018: -23.71; 2019: -50.77; 2020: -0.48; 2021: -29.6; 2022: 56.56; 2023: -157.44; 2024: 42.19; 2025: 638.91; 2026: -15.63

D1 rolling 18-month windows, $200 at 0.01 lot: 2020-2026 best 4.16x (2024-05-01), median 1.35x, 24% of windows >= 3x, 38% losing; 2003-2026: best 4.12x (2025-01-01), median 0.85x, 4% >= 3x, 62% losing, 1% ruined.

**Reading the baseline.** The rules lose on M1 and M5 at every cost level, including the unrealistically low one (M1 is negative even with a 25-point spread and no slippage). M15 is a break-even system before costs (PF 1.07 at low cost) that becomes a loser under XM's real spread, slippage and swap. D1 is the only positive timeframe over 2020-2026, but the six-year result rests on a single year (2025: +$639 of the +$619 total; 2021, 2023 and 2026 were losers) and over 2003-2026 the same rules earn $121 in 23 years with only 8 positive years. The break-even stop at +$5.00 is the dominant D1 exit (70 of 85 trades) and the swing protection captured the profit in only 7 trades. On a $200 account the EA **as provided** places no D1 trade at all in six years (370 setups blocked by the 1% rule) and loses $84-$196 on M1/M5/M15 while still blocking most setups; with the filter off it is ruined on M1, M5 and M15 and survives D1 only because the 2025 rally arrives before a $112 single loss can.

## 5. D1 validation of the reported ~3x in ~1.5 years

**The ~3x in ~1.5 years is reproducible, but only under conditions that are not the EA as provided.** The only D1 tester profile on this machine is v13 (deposit $5,000, Chandelier from the first tick, 1,500-point max-loss cap, SL% filter off) on 2024-01-01 to 2026-09-15. With v1.00 rules and the SL% filter off, $200 at 0.01 lot grows 4.5x over that window (47 trades, PF 7.8) and 4.1x over 2020-2026; with the filter **on** (the shipped default) the EA takes zero trades on $200 and six trades on $5,000. The v13-like configuration earns $1,706 over the claim window regardless of deposit, i.e. 1.34x on $5,000 or 9.5x on $200. Every one of these runs risks 15-130% of a $200 account per trade (median swing stop $92, max $425). Over 2003-2026 the v1.00 rules are net positive in 8 of 23 years, the top five trades are 48% of gross profit, and removing 2025 turns the 23-year total from +$121 to -$518: the D1 result is one exceptional period (the 2024-2026 gold rally), not a persistent edge. Bear-regime (short-side) trades were the profitable side over 23 years, the opposite of 2020-2026, so direction dependence flips with the regime as well.

| config | period | cost | trades | net $ | growth | PF | maxDD $ | blocked by 1% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1.00_defaults_$200 | claim_2024-01..2026-09 | B_real | 0 | 0.00 | 1.00 | - | 0.00 | 194.00 |
| v1.00_defaults_$200 | 6y_2020-09..2026-09 | B_real | 0 | 0.00 | 1.00 | - | 0.00 | 370.00 |
| v1.00_defaults_$200 | 23y_2003..2026 | B_real | 1 | -2.07 | 0.99 | 0.00 | 2.07 | 1669.00 |
| v1.00_defaults_$5000 | claim_2024-01..2026-09 | B_real | 6 | 78.76 | 1.02 | 13.96 | 6.08 | 178.00 |
| v1.00_defaults_$5000 | 6y_2020-09..2026-09 | B_real | 25 | 5.40 | 1.00 | 1.06 | 80.07 | 292.00 |
| v1.00_defaults_$5000 | 23y_2003..2026 | B_real | 194 | -298.17 | 0.94 | 0.71 | 439.74 | 740.00 |
| v1.00_nofilter_$200 | claim_2024-01..2026-09 | B_real | 47 | 698.52 | 4.49 | 7.82 | 52.98 | 0.00 |
| v1.00_nofilter_$200 | 6y_2020-09..2026-09 | B_real | 85 | 619.14 | 4.10 | 2.95 | 179.40 | 0.00 |
| v1.00_nofilter_$200 | 23y_2003..2026 | B_real | 18 | -200.18 | -0.00 | 0.00 | 200.18 | 0.00 |
| v13like_$5000 | claim_2024-01..2026-09 | B_real | 46 | 1705.54 | 1.34 | 12.76 | 58.26 | 0.00 |
| v13like_$5000 | 6y_2020-09..2026-09 | B_real | 98 | 1571.13 | 1.31 | 4.75 | 157.15 | 0.00 |
| v13like_$5000 | 23y_2003..2026 | B_real | 377 | 753.17 | 1.15 | 1.34 | 611.16 | 0.00 |
| v13like_$200 | claim_2024-01..2026-09 | B_real | 46 | 1705.54 | 9.53 | 12.76 | 58.26 | 0.00 |
| v13like_$200 | 6y_2020-09..2026-09 | B_real | 98 | 1571.13 | 8.86 | 4.75 | 157.15 | 0.00 |
| v13like_$200 | 23y_2003..2026 | B_real | 17 | -200.72 | -0.00 | 0.00 | 200.72 | 0.00 |

D1 exit variants over 2003-2026 (H1 path, realistic costs): net $ / expectancy R per 8-year window, positive years, and the total without 2025.

| exit | trades | net $ | PF | maxDD $ | exp R | positive years | net ex-2025 $ | 2003-2012 | 2012-2020 | 2020-2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E01 EA swing after 500 + BE + MA18 | 329 | 121.32 | 1.06 | 545.02 | -0.04 | 8/23 | -517.59 | -191.67 / -0.162 | -218.52 / -0.018 | 531.51 / 0.06 |
| E02 Chandelier after 500 + BE + MA18 | 330 | 1139.71 | 1.58 | 383.99 | -0.01 | 9/23 | 311.16 | -78.76 / -0.132 | -154.5 / -0.004 | 1372.96 / 0.109 |
| E03 Chandelier immediate + BE + MA18 | 336 | 1113.15 | 1.56 | 430.26 | -0.01 | 9/23 | 284.61 | -36.18 / -0.117 | -249.17 / -0.016 | 1398.5 / 0.107 |
| E09 ATR trail 2x immediate + BE + MA18 | 369 | 1529.75 | 1.69 | 357.41 | 0.02 | 10/23 | 726.54 | 33.47 / -0.052 | -161.09 / 0.002 | 1657.38 / 0.122 |
| E10 ATR trail 3x immediate + BE + MA18 | 335 | 1295.32 | 1.69 | 432.08 | -0.01 | 9/23 | 434.90 | -123.44 / -0.134 | -180.77 / 0.004 | 1599.52 / 0.129 |
| E16 Chandelier immediate + BE, no MA18 | 318 | 1011.71 | 1.49 | 527.58 | -0.02 | 10/23 | 219.11 | 39.87 / -0.118 | -369.35 / -0.037 | 1341.19 / 0.096 |
| E19 ATR-scaled BE 1ATR + trail 2/1 ATR + MA18 | 226 | 1094.23 | 1.33 | 467.95 | 0.03 | 13/23 | 320.06 | -113.23 / -0.127 | 6.29 / 0.067 | 1201.17 / 0.196 |
| E25 pure Chandelier (no BE, no MA18) | 165 | 719.59 | 1.20 | 651.23 | -0.05 | 8/23 | -89.77 | -355.0 / -0.305 | -35.1 / 0.025 | 1109.7 / 0.177 |
| E15 EA without MA18 exit | 308 | 6.16 | 1.00 | 841.89 | -0.07 | 8/23 | -728.30 | -232.66 / -0.238 | -445.4 / -0.056 | 684.22 / 0.099 |
| E05 BE only + MA18 | 312 | 130.51 | 1.07 | 536.65 | -0.04 | 8/23 | -472.83 | -142.76 / -0.166 | -252.22 / -0.024 | 525.49 / 0.064 |

2003-2026 (v1.00 rules, filter off, realistic costs): 8 of 23 years positive; the top-5 trades are 48% of gross profit; net excluding 2025 = -517.59. By exit: swing-protection exits 1315.98 on 29 trades, break-even exits -322.08 on 232, MA18 exits -647.11 on 58.

## 6. Entry filter analysis (Phase 1 and 2)

**No entry filter changes the sign of any lower timeframe.** On M1 six filters are 'helpful' by the declared rule (better expectancy/R and PF in DEV, VAL and OOS) and every one of them still loses more than $14,000 per 0.01 lot; the most useful (volatility ratio >= 1, entry buffer 50 points) merely halve the loss rate. On M5 seven filters pass individually and the progressive stack New York session + volatility >= 1 + ADX >= 25 consecutive rise cuts the six-year loss from -$4,977 to -$128 with a positive out-of-sample slice (+$326, PF 1.18) that is not matched in DEV or VAL. On M15 nothing passes: the volatility filter (ATR / 100-bar ATR >= 1.0) is the only variant that ends positive (+$178, PF 1.03) and it improves DEV and VAL but leaves OOS expectancy unchanged, so by the pre-declared rule it is neutral; I did not relax the rule to admit it. Removing the volume filter, removing the 200 SMA condition, or taking 1-bar confirmation are all harmful on M15, so the base entry is at least internally coherent. On D1 there are 85 trades in six years; every filter verdict there is inside sampling noise and is reported but not used.

### M1

| filter | trades | removed | PF | win % | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE | 54900 |  | 0.55 | 20.60 | -30212.35 | 30239.03 | -0.33 | -0.41 | -0.36 | -0.18 | base |
| F01 volume filter OFF | 75238 | -20338 | 0.53 | 19.40 | -41445.77 | 41468.27 | -0.35 | -0.44 | -0.39 | -0.20 | Harmful |
| F02 MA200 trend filter OFF | 97963 | -43063 | 0.53 | 20.90 | -55262.13 | 55269.52 | -0.33 | -0.41 | -0.37 | -0.18 | Harmful |
| F03 1-bar confirmation | 67015 | -12115 | 0.53 | 19.20 | -37266.68 | 37288.76 | -0.36 | -0.45 | -0.40 | -0.20 | Harmful |
| F04 3-bar confirmation | 47982 | 6918 | 0.55 | 20.70 | -26574.95 | 26605.78 | -0.32 | -0.40 | -0.35 | -0.17 | Neutral |
| F05 ADX>=25 | 40005 | 14895 | 0.57 | 21.50 | -22100.47 | 22129.40 | -0.30 | -0.37 | -0.33 | -0.16 | Helpful |
| F06 ADX>=20 | 48574 | 6326 | 0.55 | 21.00 | -27051.58 | 27075.62 | -0.31 | -0.39 | -0.34 | -0.17 | Neutral |
| F07 ADX>=30 | 31375 | 23525 | 0.57 | 21.70 | -17697.30 | 17709.40 | -0.29 | -0.36 | -0.32 | -0.16 | Helpful |
| F08 ADX>=25 rising(3) | 32747 | 22153 | 0.58 | 22.40 | -17891.10 | 17922.45 | -0.27 | -0.34 | -0.30 | -0.14 | Helpful |
| F09 ADX>=25 consecutive rise(3) | 27335 | 27565 | 0.59 | 23.20 | -14994.93 | 15013.19 | -0.25 | -0.33 | -0.28 | -0.13 | Helpful |
| F10 session London 8-17 | 23506 | 31394 | 0.57 | 21.80 | -12679.96 | 12704.90 | -0.28 | -0.33 | -0.30 | -0.17 | Helpful |
| F11 session New York 13-22 | 23090 | 31810 | 0.58 | 22.00 | -13027.83 | 13045.81 | -0.27 | -0.32 | -0.29 | -0.17 | Neutral |
| F12 session London+NY 8-22 | 35411 | 19489 | 0.56 | 21.80 | -20010.08 | 20035.02 | -0.28 | -0.34 | -0.30 | -0.18 | Neutral |
| F13 session Tokyo 0-9 | 18561 | 36339 | 0.56 | 19.20 | -9224.61 | 9245.74 | -0.38 | -0.50 | -0.44 | -0.17 | Harmful |
| F14 session overlap 13-17 | 11185 | 43715 | 0.63 | 22.30 | -5697.71 | 5743.05 | -0.24 | -0.28 | -0.28 | -0.15 | Helpful |
| F15 pending expires 1 bar | 49225 | 5675 | 0.56 | 20.90 | -27020.32 | 27055.38 | -0.31 | -0.39 | -0.35 | -0.18 | Neutral |
| F16 pending expires 3 bars | 53765 | 1135 | 0.56 | 20.50 | -29187.64 | 29211.64 | -0.32 | -0.41 | -0.36 | -0.18 | Neutral |
| F17 pending invalidation OFF | 1544 | 53356 | 0.36 | 19.40 | -1040.10 | 1040.10 | -0.45 | -0.45 | - | - | Harmful (removes >95% of trades) |
| F18 entry buffer 0 | 54601 | 299 | 0.55 | 19.80 | -30074.06 | 30101.15 | -0.35 | -0.45 | -0.40 | -0.18 | Harmful |
| F19 entry buffer 50 | 46923 | 7977 | 0.58 | 22.40 | -25632.99 | 25659.93 | -0.26 | -0.33 | -0.29 | -0.15 | Helpful |
| F20 volatility ATR ratio >= 1.0 | 27996 | 26904 | 0.62 | 22.20 | -14163.71 | 14172.05 | -0.27 | -0.34 | -0.31 | -0.13 | Helpful |
| F21 volatility ATR ratio <= 1.5 | 52028 | 2872 | 0.54 | 20.20 | -29241.60 | 29267.34 | -0.33 | -0.42 | -0.37 | -0.18 | Harmful |
| F22 volatility ATR ratio 0.8-1.5 | 41359 | 13541 | 0.55 | 20.80 | -23312.45 | 23329.54 | -0.31 | -0.39 | -0.34 | -0.17 | Neutral |
| F23 max spread 40 pts | 47198 | 7702 | 0.47 | 20.10 | -25668.91 | 25676.35 | -0.36 | -0.41 | -0.36 | -0.21 | Neutral |
| F24 MA18 slope over 3 bars | 49278 | 5622 | 0.56 | 20.60 | -26812.48 | 26837.20 | -0.32 | -0.40 | -0.35 | -0.17 | Helpful |
| F25 not extended |close-MA18| <= 1 ATR | 35393 | 19507 | 0.52 | 17.60 | -19103.16 | 19114.13 | -0.40 | -0.49 | -0.44 | -0.23 | Harmful |
| F26 not extended |close-MA18| <= 2 ATR | 49748 | 5152 | 0.54 | 19.50 | -26943.79 | 26968.73 | -0.35 | -0.43 | -0.39 | -0.19 | Harmful |

Progressive combinations of the individually helpful filters:

| test | filters | trades | PF | win % | net $ | maxDD $ | exp $ | exp R DEV/VAL/OOS | OOS net $ | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C01 | F14 | 11185 | 0.63 | 22.30 | -5697.71 | 5743.05 | -0.51 | -0.283/-0.285/-0.153 | -1810.90 | Helpful |
| C02 | F14 + F09 | 5635 | 0.67 | 25.60 | -2845.64 | 2970.92 | -0.51 | -0.219/-0.208/-0.099 | -846.07 | Helpful |
| C03 | F14 + F09 + F19 | 5124 | 0.68 | 25.90 | -2608.39 | 2730.42 | -0.51 | -0.204/-0.186/-0.102 | -888.54 | Helpful |
| C04 | F14 + F09 + F19 + F10 | 5124 | 0.68 | 25.90 | -2608.39 | 2730.42 | -0.51 | -0.204/-0.186/-0.102 | -888.54 | Helpful |
| C05 | F14 + F09 + F19 + F10 + F20 | 3789 | 0.70 | 26.40 | -1881.37 | 2202.05 | -0.50 | -0.193/-0.178/-0.087 | -522.79 | Helpful |
| C06 | F14 + F09 + F19 + F10 + F20 + F08 | 3789 | 0.70 | 26.40 | -1881.37 | 2202.05 | -0.50 | -0.193/-0.178/-0.087 | -522.79 | Helpful |

### M5

| filter | trades | removed | PF | win % | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE | 12320 |  | 0.79 | 25.80 | -4977.42 | 5314.60 | -0.15 | -0.22 | -0.17 | -0.04 | base |
| F01 volume filter OFF | 17030 | -4710 | 0.78 | 24.40 | -6780.01 | 7007.86 | -0.17 | -0.24 | -0.19 | -0.04 | Harmful |
| F02 MA200 trend filter OFF | 22329 | -10009 | 0.74 | 25.90 | -11096.69 | 11110.19 | -0.16 | -0.22 | -0.18 | -0.07 | Harmful |
| F03 1-bar confirmation | 15382 | -3062 | 0.79 | 23.90 | -6118.20 | 6394.71 | -0.17 | -0.24 | -0.19 | -0.05 | Harmful |
| F04 3-bar confirmation | 10584 | 1736 | 0.82 | 26.30 | -3734.03 | 4395.33 | -0.14 | -0.21 | -0.17 | -0.02 | Neutral |
| F05 ADX>=25 | 8779 | 3541 | 0.83 | 27.30 | -3107.70 | 3745.97 | -0.14 | -0.20 | -0.16 | -0.04 | Helpful |
| F06 ADX>=20 | 10836 | 1484 | 0.81 | 26.40 | -4147.34 | 4787.53 | -0.14 | -0.21 | -0.16 | -0.04 | Neutral |
| F07 ADX>=30 | 6785 | 5535 | 0.85 | 28.20 | -2098.09 | 2821.46 | -0.12 | -0.18 | -0.14 | -0.04 | Helpful |
| F08 ADX>=25 rising(3) | 7087 | 5233 | 0.86 | 29.10 | -1990.07 | 2731.96 | -0.11 | -0.18 | -0.12 | -0.02 | Helpful |
| F09 ADX>=25 consecutive rise(3) | 5996 | 6324 | 0.87 | 29.80 | -1665.77 | 2491.77 | -0.11 | -0.17 | -0.13 | -0.01 | Helpful |
| F10 session London 8-17 | 6187 | 6133 | 0.81 | 27.00 | -2374.37 | 2505.55 | -0.12 | -0.16 | -0.12 | -0.05 | Neutral |
| F11 session New York 13-22 | 5260 | 7060 | 0.86 | 28.10 | -1614.78 | 1893.77 | -0.11 | -0.15 | -0.12 | -0.04 | Helpful |
| F12 session London+NY 8-22 | 8317 | 4003 | 0.82 | 27.10 | -3065.12 | 3381.59 | -0.13 | -0.17 | -0.13 | -0.05 | Neutral |
| F13 session Tokyo 0-9 | 4450 | 7870 | 0.81 | 24.00 | -1483.13 | 1892.63 | -0.18 | -0.27 | -0.21 | -0.02 | Harmful |
| F14 session overlap 13-17 | 3130 | 9190 | 0.87 | 28.40 | -924.04 | 1112.87 | -0.08 | -0.10 | -0.10 | -0.04 | Neutral |
| F15 pending expires 1 bar | 11568 | 752 | 0.80 | 25.80 | -4436.83 | 5006.97 | -0.15 | -0.21 | -0.16 | -0.05 | Neutral |
| F16 pending expires 3 bars | 12228 | 92 | 0.80 | 25.70 | -4727.71 | 5302.37 | -0.15 | -0.21 | -0.18 | -0.04 | Neutral |
| F17 pending invalidation OFF | 785 | 11535 | 0.59 | 22.30 | -516.43 | 521.71 | -0.28 | -0.29 | -0.22 | - | Harmful |
| F18 entry buffer 0 | 12364 | -44 | 0.79 | 24.60 | -5078.76 | 5356.09 | -0.15 | -0.22 | -0.18 | -0.04 | Harmful |
| F19 entry buffer 50 | 11139 | 1181 | 0.83 | 25.90 | -3920.64 | 4517.01 | -0.12 | -0.18 | -0.15 | -0.02 | Helpful |
| F20 volatility ATR ratio >= 1.0 | 7162 | 5158 | 0.84 | 29.20 | -2305.00 | 2746.68 | -0.11 | -0.15 | -0.12 | -0.03 | Helpful |
| F21 volatility ATR ratio <= 1.5 | 11089 | 1231 | 0.77 | 24.60 | -4875.16 | 4916.43 | -0.16 | -0.23 | -0.19 | -0.04 | Harmful |
| F22 volatility ATR ratio 0.8-1.5 | 8212 | 4108 | 0.80 | 26.70 | -3283.07 | 3351.67 | -0.12 | -0.18 | -0.14 | -0.04 | Neutral |
| F23 max spread 40 pts | 10536 | 1784 | 0.71 | 26.80 | -5174.06 | 5191.94 | -0.17 | -0.22 | -0.17 | -0.06 | Neutral |
| F24 MA18 slope over 3 bars | 11002 | 1318 | 0.81 | 26.20 | -3999.09 | 4576.55 | -0.14 | -0.21 | -0.16 | -0.04 | Neutral |
| F25 not extended |close-MA18| <= 1 ATR | 8169 | 4151 | 0.72 | 22.80 | -3936.69 | 4065.71 | -0.19 | -0.26 | -0.22 | -0.07 | Harmful |
| F26 not extended |close-MA18| <= 2 ATR | 11364 | 956 | 0.76 | 24.60 | -5128.94 | 5284.77 | -0.17 | -0.23 | -0.18 | -0.05 | Harmful |

Progressive combinations of the individually helpful filters:

| test | filters | trades | PF | win % | net $ | maxDD $ | exp $ | exp R DEV/VAL/OOS | OOS net $ | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C01 | F11 | 5260 | 0.86 | 28.10 | -1614.78 | 1893.77 | -0.31 | -0.149/-0.121/-0.039 | -71.98 | Helpful |
| C02 | F11 + F20 | 3561 | 0.92 | 31.20 | -685.36 | 1237.29 | -0.19 | -0.095/-0.109/-0.009 | 295.57 | Helpful |
| C03 | F11 + F20 + F09 | 1784 | 0.97 | 35.00 | -127.67 | 771.82 | -0.07 | -0.082/-0.081/0.011 | 325.68 | Helpful |
| C04 | F11 + F20 + F09 + F08 | 1784 | 0.97 | 35.00 | -127.67 | 771.82 | -0.07 | -0.082/-0.081/0.011 | 325.68 | Helpful |
| C05 | F11 + F20 + F09 + F08 + F07 | 1522 | 0.93 | 36.20 | -253.10 | 526.50 | -0.17 | -0.049/-0.077/-0.027 | -25.71 | Helpful |
| C06 | F11 + F20 + F09 + F08 + F07 + F19 | 1471 | 0.94 | 32.40 | -231.78 | 513.20 | -0.16 | -0.049/-0.065/-0.02 | -5.55 | Helpful |

### M15

| filter | trades | removed | PF | win % | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE | 4559 |  | 0.92 | 32.90 | -983.88 | 1581.42 | -0.07 | -0.11 | -0.07 | -0.00 | base |
| F01 volume filter OFF | 6161 | -1602 | 0.90 | 29.80 | -1493.66 | 1954.57 | -0.08 | -0.14 | -0.07 | -0.00 | Harmful |
| F02 MA200 trend filter OFF | 8231 | -3672 | 0.89 | 32.30 | -2290.10 | 3148.43 | -0.07 | -0.11 | -0.09 | -0.01 | Harmful |
| F03 1-bar confirmation | 5831 | -1272 | 0.90 | 30.40 | -1419.82 | 1996.40 | -0.07 | -0.12 | -0.07 | -0.01 | Harmful |
| F04 3-bar confirmation | 3924 | 635 | 0.89 | 33.30 | -1245.60 | 1521.60 | -0.06 | -0.10 | -0.06 | -0.01 | Neutral |
| F05 ADX>=25 | 3242 | 1317 | 0.93 | 34.90 | -664.33 | 1339.82 | -0.05 | -0.09 | -0.06 | -0.01 | Neutral |
| F06 ADX>=20 | 4019 | 540 | 0.92 | 34.00 | -826.89 | 1506.10 | -0.06 | -0.10 | -0.05 | -0.02 | Neutral |
| F07 ADX>=30 | 2499 | 2060 | 0.86 | 35.20 | -991.65 | 1184.44 | -0.06 | -0.10 | -0.05 | -0.03 | Neutral |
| F08 ADX>=25 rising(3) | 2569 | 1990 | 0.92 | 36.20 | -585.50 | 1101.35 | -0.04 | -0.08 | -0.04 | 0.03 | Neutral |
| F09 ADX>=25 consecutive rise(3) | 2146 | 2413 | 0.94 | 37.00 | -360.70 | 653.92 | -0.04 | -0.08 | -0.06 | 0.01 | Neutral |
| F10 session London 8-17 | 2696 | 1863 | 0.82 | 34.70 | -1316.77 | 1443.06 | -0.08 | -0.11 | -0.06 | -0.05 | Neutral |
| F11 session New York 13-22 | 2185 | 2374 | 0.92 | 36.60 | -533.74 | 692.52 | -0.05 | -0.06 | -0.07 | -0.03 | Harmful |
| F12 session London+NY 8-22 | 3374 | 1185 | 0.87 | 34.70 | -1207.60 | 1460.43 | -0.07 | -0.10 | -0.06 | -0.04 | Neutral |
| F13 session Tokyo 0-9 | 1643 | 2916 | 0.95 | 29.90 | -184.57 | 541.33 | -0.06 | -0.14 | -0.03 | 0.04 | Neutral |
| F14 session overlap 13-17 | 1501 | 3058 | 0.86 | 37.60 | -636.73 | 768.36 | -0.05 | -0.05 | -0.08 | -0.04 | Harmful |
| F15 pending expires 1 bar | 4371 | 188 | 0.90 | 32.80 | -1183.36 | 1293.90 | -0.06 | -0.10 | -0.07 | -0.01 | Harmful |
| F16 pending expires 3 bars | 4533 | 26 | 0.90 | 32.80 | -1135.04 | 1486.19 | -0.07 | -0.12 | -0.07 | -0.01 | Harmful |
| F17 pending invalidation OFF | 221 | 4338 | 0.63 | 35.70 | -215.22 | 215.22 | -0.18 | -0.18 | - | - | Harmful (removes >95% of trades) |
| F18 entry buffer 0 | 4583 | -24 | 0.90 | 29.70 | -1214.96 | 1705.48 | -0.07 | -0.11 | -0.07 | -0.01 | Neutral |
| F19 entry buffer 50 | 4287 | 272 | 0.96 | 30.50 | -430.10 | 1289.13 | -0.06 | -0.11 | -0.05 | 0.00 | Neutral |
| F20 volatility ATR ratio >= 1.0 | 2087 | 2472 | 1.03 | 38.60 | 178.36 | 589.42 | -0.02 | -0.03 | -0.02 | -0.00 | Neutral |
| F21 volatility ATR ratio <= 1.5 | 4359 | 200 | 0.89 | 32.10 | -1238.39 | 1756.53 | -0.07 | -0.12 | -0.08 | -0.01 | Harmful |
| F22 volatility ATR ratio 0.8-1.5 | 3221 | 1338 | 0.94 | 33.60 | -569.95 | 1580.42 | -0.06 | -0.10 | -0.10 | -0.00 | Neutral |
| F23 max spread 40 pts | 3816 | 743 | 0.84 | 35.70 | -1464.04 | 1568.25 | -0.08 | -0.11 | -0.07 | -0.02 | Neutral |
| F24 MA18 slope over 3 bars | 4058 | 501 | 0.90 | 33.80 | -1068.55 | 1497.60 | -0.06 | -0.10 | -0.07 | -0.01 | Harmful |
| F25 not extended |close-MA18| <= 1 ATR | 3014 | 1545 | 0.93 | 29.40 | -481.25 | 1267.31 | -0.10 | -0.17 | -0.10 | 0.01 | Harmful |
| F26 not extended |close-MA18| <= 2 ATR | 4096 | 463 | 0.88 | 31.20 | -1190.85 | 1735.95 | -0.08 | -0.13 | -0.09 | -0.01 | Harmful |

No individually helpful filter on this timeframe, nothing to combine.

### D1

| filter | trades | removed | PF | win % | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE | 85 |  | 2.95 | 49.40 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | base |
| F01 volume filter OFF | 136 | -51 | 2.60 | 44.90 | 594.97 | 189.22 | 0.04 | -0.04 | 0.09 | 0.07 | Harmful |
| F02 MA200 trend filter OFF | 140 | -55 | 1.45 | 47.90 | 310.77 | 300.01 | 0.01 | -0.03 | -0.06 | 0.10 | Harmful |
| F03 1-bar confirmation | 102 | -17 | 2.12 | 41.20 | 548.60 | 182.00 | 0.05 | -0.01 | -0.01 | 0.18 | Harmful |
| F04 3-bar confirmation | 75 | 10 | 2.67 | 50.70 | 544.78 | 226.08 | 0.07 | -0.02 | 0.00 | 0.21 | Harmful |
| F05 ADX>=25 | 64 | 21 | 6.86 | 46.90 | 758.85 | 66.37 | 0.12 | 0.04 | 0.05 | 0.27 | Neutral |
| F06 ADX>=20 | 78 | 7 | 3.80 | 50.00 | 689.25 | 179.40 | 0.10 | 0.07 | 0.01 | 0.22 | Neutral |
| F07 ADX>=30 | 56 | 29 | 4.07 | 51.80 | 653.43 | 174.39 | 0.13 | 0.03 | 0.02 | 0.34 | Neutral |
| F08 ADX>=25 rising(3) | 56 | 29 | 10.31 | 44.60 | 590.17 | 17.37 | 0.09 | 0.05 | 0.04 | 0.17 | Neutral |
| F09 ADX>=25 consecutive rise(3) | 47 | 38 | 11.33 | 46.80 | 556.19 | 19.97 | 0.09 | 0.07 | 0.01 | 0.20 | Harmful |
| F15 pending expires 1 bar | 80 | 5 | 2.96 | 52.50 | 530.81 | 175.34 | 0.06 | -0.04 | -0.02 | 0.26 | Harmful |
| F16 pending expires 3 bars | 79 | 6 | 2.29 | 50.60 | 481.43 | 211.96 | 0.06 | 0.01 | -0.08 | 0.23 | Neutral |
| F17 pending invalidation OFF | 13 | 72 | 0.38 | 92.30 | -6.54 | 10.49 | -0.01 | -0.01 | - | - | Harmful |
| F18 entry buffer 0 | 85 | 0 | 2.95 | 40.00 | 620.84 | 179.20 | 0.07 | -0.00 | 0.01 | 0.21 | Neutral |
| F19 entry buffer 50 | 89 | -4 | 2.49 | 39.30 | 550.91 | 208.80 | 0.06 | -0.02 | 0.01 | 0.21 | Harmful |
| F20 volatility ATR ratio >= 1.0 | 42 | 43 | 2.75 | 47.60 | 157.76 | 55.88 | 0.02 | -0.05 | 0.10 | 0.03 | Harmful |
| F21 volatility ATR ratio <= 1.5 | 81 | 4 | 3.60 | 51.90 | 813.04 | 179.40 | 0.10 | -0.00 | 0.01 | 0.32 | Neutral |
| F22 volatility ATR ratio 0.8-1.5 | 73 | 12 | 2.87 | 54.80 | 464.48 | 126.41 | 0.08 | 0.01 | 0.04 | 0.20 | Neutral |
| F24 MA18 slope over 3 bars | 76 | 9 | 2.74 | 51.30 | 595.52 | 171.15 | 0.08 | -0.01 | 0.02 | 0.22 | Neutral |
| F25 not extended |close-MA18| <= 1 ATR | 36 | 49 | 1.21 | 44.40 | 34.75 | 60.31 | 0.01 | -0.10 | 0.14 | -0.00 | Harmful |
| F26 not extended |close-MA18| <= 2 ATR | 64 | 21 | 2.54 | 46.90 | 360.83 | 105.88 | 0.10 | -0.06 | 0.02 | 0.27 | Neutral |

No individually helpful filter on this timeframe, nothing to combine.

## 7. Stop-loss analysis (Phase 3)

**The initial stop is not the problem and no alternative changes the sign.** The swing stop sits 2-3 ATR away and is hit in only 11-17% of lower-timeframe trades (1% on D1); the initial stop accounts for a minority of losses because most trades die at the MA18 exit or the break-even stop. Tight ATR stops (1.0-1.5x) are markedly worse everywhere (hit rate 40-70%). Wider structures (swing strength 3, 0.5-ATR buffer, 300-point minimum) are marginally less bad and consistent across splits, which is the opposite of the intuition that lower timeframes need tighter stops. On D1 the v13-style 1,500-point cap raises OOS expectancy to 1.2R but DEV is -0.21R with 30% stop-outs; it is a bet on the 2025 regime, not a robust improvement.

### M1

Existing swing stop: median 210 pts = $2.1 per 0.01 lot (3.26 ATR; p10-p90 88-680 pts), hit in 16.7% of trades = 21.9% of losses; average loss $-1.55 (-0.657 R), worst $-42.94; MFE before a stop-out 0.092 R; winners' MAE median 0.415 R, p90 0.727 R.

| stop | trades | median risk $ | SL hit % | avg loss $ | PF | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 54900 | 2.10 | 16.70 | -1.55 | 0.55 | -30212.35 | 30239.03 | -0.33 | -0.41 | -0.36 | -0.18 | base |
| B ATR 1.0x | 104156 | 0.69 | 89.60 | -1.07 | 0.26 | -78281.01 | 78293.11 | -1.01 | -1.17 | -1.09 | -0.67 | Harmful |
| B ATR 1.5x | 75874 | 0.94 | 70.00 | -1.24 | 0.42 | -47557.28 | 47588.99 | -0.71 | -0.86 | -0.78 | -0.36 | Harmful |
| B ATR 2.0x | 62930 | 1.26 | 47.60 | -1.39 | 0.51 | -35713.61 | 35740.16 | -0.52 | -0.65 | -0.58 | -0.24 | Harmful |
| B ATR 2.5x | 57643 | 1.59 | 30.20 | -1.48 | 0.54 | -31617.50 | 31642.44 | -0.41 | -0.52 | -0.46 | -0.19 | Harmful |
| B ATR 3.0x | 55471 | 1.90 | 19.40 | -1.53 | 0.55 | -30313.88 | 30340.72 | -0.34 | -0.44 | -0.40 | -0.16 | Harmful |
| C swing strength 1 | 58884 | 1.71 | 30.90 | -1.50 | 0.52 | -34040.62 | 34067.81 | -0.43 | -0.52 | -0.47 | -0.26 | Harmful |
| C swing strength 3 | 53820 | 2.36 | 10.70 | -1.56 | 0.56 | -29258.03 | 29284.31 | -0.28 | -0.36 | -0.32 | -0.15 | Helpful (still negative) |
| C swing - 0.5 ATR buffer | 54264 | 2.35 | 11.60 | -1.56 | 0.56 | -29677.95 | 29704.63 | -0.29 | -0.37 | -0.33 | -0.15 | Helpful (still negative) |
| C swing - 0.25 ATR buffer | 54503 | 2.22 | 13.70 | -1.56 | 0.55 | -29897.00 | 29923.68 | -0.30 | -0.39 | -0.34 | -0.16 | Helpful (still negative) |
| C swing capped 1000 pts | 55016 | 2.10 | 17.40 | -1.56 | 0.54 | -31173.90 | 31200.58 | -0.33 | -0.41 | -0.36 | -0.18 | Neutral (still negative) |
| C swing capped 1500 pts (v13) | 54931 | 2.10 | 16.90 | -1.55 | 0.55 | -30494.41 | 30521.09 | -0.33 | -0.41 | -0.36 | -0.18 | Neutral (still negative) |
| C swing capped 2000 pts | 54911 | 2.10 | 16.80 | -1.55 | 0.55 | -30283.91 | 30310.59 | -0.33 | -0.41 | -0.36 | -0.18 | Neutral (still negative) |
| D MA18 - 0 pts | 64143 | 1.24 | 53.90 | -1.38 | 0.48 | -38559.62 | 38576.57 | -0.56 | -0.67 | -0.60 | -0.35 | Harmful |
| D MA18 - 50 pts | 54975 | 1.77 | 22.90 | -1.54 | 0.55 | -30440.14 | 30466.24 | -0.34 | -0.40 | -0.37 | -0.23 | Harmful |
| E swing clamped [0.5, 3] ATR | 56289 | 1.72 | 25.20 | -1.52 | 0.54 | -31099.43 | 31126.27 | -0.38 | -0.48 | -0.43 | -0.19 | Harmful |
| E swing clamped [1, 4] ATR | 55102 | 1.96 | 18.40 | -1.54 | 0.55 | -30321.96 | 30348.64 | -0.34 | -0.43 | -0.38 | -0.18 | Harmful |
| E swing clamped [0.5, 2] ATR | 63466 | 1.23 | 49.90 | -1.39 | 0.50 | -36377.22 | 36405.91 | -0.53 | -0.67 | -0.59 | -0.26 | Harmful |
| F swing with 0.5 ATR floor | 54921 | 2.10 | 16.80 | -1.55 | 0.55 | -30231.22 | 30257.90 | -0.33 | -0.41 | -0.36 | -0.18 | Neutral (still negative) |
| F swing with 1.0 ATR floor | 54873 | 2.10 | 16.60 | -1.55 | 0.55 | -30162.54 | 30189.22 | -0.32 | -0.41 | -0.36 | -0.17 | Neutral (still negative) |
| F min stop 150 pts (v13 MinStopPoints) | 54076 | 2.13 | 10.70 | -1.57 | 0.56 | -29580.91 | 29607.59 | -0.28 | -0.34 | -0.30 | -0.17 | Helpful (still negative) |
| F min stop 300 pts | 53942 | 3.10 | 8.30 | -1.57 | 0.56 | -29450.83 | 29477.51 | -0.22 | -0.27 | -0.25 | -0.14 | Helpful (still negative) |

### M5

Existing swing stop: median 436 pts = $4.36 per 0.01 lot (2.9 ATR; p10-p90 176-1597 pts), hit in 11.3% of trades = 21.7% of losses; average loss $-2.68 (-0.553 R), worst $-74.38; MFE before a stop-out 0.245 R; winners' MAE median 0.309 R, p90 0.616 R.

| stop | trades | median risk $ | SL hit % | avg loss $ | PF | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 12320 | 4.36 | 11.30 | -2.68 | 0.79 | -4977.42 | 5314.60 | -0.15 | -0.22 | -0.17 | -0.04 | base |
| B ATR 1.0x | 17393 | 1.50 | 70.60 | -1.87 | 0.65 | -9555.37 | 9576.47 | -0.44 | -0.59 | -0.50 | -0.14 | Harmful |
| B ATR 1.5x | 13986 | 2.29 | 46.30 | -2.35 | 0.75 | -6361.08 | 6378.52 | -0.26 | -0.37 | -0.30 | -0.07 | Harmful |
| B ATR 2.0x | 12867 | 3.03 | 27.40 | -2.55 | 0.79 | -5138.12 | 5488.32 | -0.19 | -0.28 | -0.22 | -0.04 | Harmful |
| B ATR 2.5x | 12446 | 3.75 | 15.80 | -2.65 | 0.79 | -4962.56 | 5341.57 | -0.16 | -0.23 | -0.17 | -0.03 | Harmful |
| B ATR 3.0x | 12294 | 4.39 | 9.70 | -2.70 | 0.79 | -4966.18 | 5305.08 | -0.14 | -0.20 | -0.15 | -0.03 | Neutral (still negative) |
| C swing strength 1 | 12990 | 3.62 | 21.90 | -2.62 | 0.79 | -5242.04 | 5479.54 | -0.19 | -0.27 | -0.20 | -0.08 | Harmful |
| C swing strength 3 | 12126 | 4.90 | 7.10 | -2.69 | 0.79 | -4928.01 | 5293.57 | -0.13 | -0.19 | -0.15 | -0.04 | Neutral (still negative) |
| C swing - 0.5 ATR buffer | 12231 | 4.95 | 7.10 | -2.72 | 0.79 | -4979.34 | 5300.38 | -0.13 | -0.19 | -0.14 | -0.03 | Neutral (still negative) |
| C swing - 0.25 ATR buffer | 12270 | 4.66 | 8.90 | -2.70 | 0.79 | -4997.77 | 5336.72 | -0.14 | -0.20 | -0.16 | -0.04 | Neutral (still negative) |
| C swing capped 1000 pts | 12465 | 4.42 | 14.90 | -2.72 | 0.76 | -5956.11 | 5966.05 | -0.16 | -0.22 | -0.17 | -0.06 | Harmful |
| C swing capped 1500 pts (v13) | 12371 | 4.38 | 12.50 | -2.72 | 0.78 | -5506.60 | 5516.15 | -0.15 | -0.22 | -0.17 | -0.04 | Harmful |
| C swing capped 2000 pts | 12345 | 4.38 | 11.80 | -2.71 | 0.78 | -5335.27 | 5344.82 | -0.15 | -0.22 | -0.17 | -0.04 | Neutral (still negative) |
| D MA18 - 0 pts | 13657 | 2.42 | 45.80 | -2.35 | 0.77 | -5658.40 | 5973.21 | -0.28 | -0.38 | -0.34 | -0.09 | Harmful |
| D MA18 - 50 pts | 12622 | 3.01 | 28.60 | -2.58 | 0.79 | -5061.21 | 5337.00 | -0.19 | -0.27 | -0.21 | -0.07 | Harmful |
| E swing clamped [0.5, 3] ATR | 12400 | 3.82 | 15.00 | -2.66 | 0.79 | -4975.43 | 5343.09 | -0.16 | -0.24 | -0.18 | -0.04 | Harmful |
| E swing clamped [1, 4] ATR | 12306 | 4.24 | 11.40 | -2.68 | 0.79 | -4931.59 | 5287.75 | -0.15 | -0.22 | -0.17 | -0.04 | Neutral (still negative) |
| E swing clamped [0.5, 2] ATR | 12954 | 2.90 | 30.10 | -2.52 | 0.79 | -5195.61 | 5550.05 | -0.20 | -0.30 | -0.23 | -0.05 | Harmful |
| F swing with 0.5 ATR floor | 12319 | 4.36 | 11.20 | -2.68 | 0.79 | -4952.03 | 5310.70 | -0.15 | -0.22 | -0.17 | -0.04 | Neutral (still negative) |
| F swing with 1.0 ATR floor | 12302 | 4.38 | 10.90 | -2.69 | 0.79 | -4953.69 | 5290.66 | -0.15 | -0.22 | -0.17 | -0.04 | Helpful (still negative) |
| F min stop 150 pts (v13 MinStopPoints) | 12278 | 4.38 | 10.00 | -2.69 | 0.79 | -4940.23 | 5276.05 | -0.14 | -0.20 | -0.16 | -0.04 | Neutral (still negative) |
| F min stop 300 pts | 12242 | 4.39 | 7.40 | -2.70 | 0.80 | -4915.55 | 5255.29 | -0.12 | -0.17 | -0.13 | -0.04 | Helpful (still negative) |

### M15

Existing swing stop: median 817 pts = $8.17 per 0.01 lot (2.89 ATR; p10-p90 314-2944 pts), hit in 10.6% of trades = 23.8% of losses; average loss $-4.16 (-0.508 R), worst $-79.84; MFE before a stop-out 0.269 R; winners' MAE median 0.244 R, p90 0.592 R.

| stop | trades | median risk $ | SL hit % | avg loss $ | PF | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 4559 | 8.17 | 10.60 | -4.16 | 0.92 | -983.88 | 1581.42 | -0.07 | -0.11 | -0.07 | -0.00 | base |
| B ATR 1.0x | 5954 | 2.71 | 59.20 | -2.87 | 0.82 | -2304.50 | 2498.23 | -0.20 | -0.34 | -0.13 | -0.05 | Harmful |
| B ATR 1.5x | 5096 | 4.14 | 39.30 | -3.58 | 0.89 | -1318.45 | 1717.72 | -0.11 | -0.21 | -0.06 | -0.01 | Harmful |
| B ATR 2.0x | 4749 | 5.52 | 24.40 | -3.95 | 0.91 | -1112.60 | 1617.46 | -0.08 | -0.16 | -0.05 | 0.00 | Neutral (still negative) |
| B ATR 2.5x | 4601 | 6.82 | 14.80 | -4.14 | 0.91 | -1047.12 | 1555.09 | -0.07 | -0.13 | -0.04 | 0.00 | Neutral (still negative) |
| B ATR 3.0x | 4556 | 8.09 | 9.70 | -4.19 | 0.92 | -991.04 | 1554.00 | -0.06 | -0.11 | -0.04 | 0.00 | Neutral (still negative) |
| C swing strength 1 | 4833 | 6.61 | 19.50 | -4.05 | 0.92 | -1018.11 | 1566.74 | -0.08 | -0.15 | -0.05 | -0.00 | Neutral (still negative) |
| C swing strength 3 | 4480 | 8.77 | 7.60 | -4.19 | 0.93 | -819.08 | 1461.65 | -0.05 | -0.10 | -0.06 | 0.01 | Neutral (still negative) |
| C swing - 0.5 ATR buffer | 4530 | 9.21 | 7.40 | -4.20 | 0.92 | -932.44 | 1504.59 | -0.06 | -0.10 | -0.06 | -0.00 | Neutral (still negative) |
| C swing - 0.25 ATR buffer | 4542 | 8.68 | 8.70 | -4.19 | 0.92 | -954.72 | 1532.77 | -0.06 | -0.10 | -0.06 | -0.00 | Neutral (still negative) |
| C swing capped 1000 pts | 4714 | 8.38 | 19.40 | -4.11 | 0.83 | -2153.34 | 2236.48 | -0.08 | -0.11 | -0.06 | -0.06 | Neutral (still negative) |
| C swing capped 1500 pts (v13) | 4623 | 8.25 | 14.30 | -4.19 | 0.87 | -1638.51 | 1721.53 | -0.07 | -0.11 | -0.07 | -0.02 | Neutral (still negative) |
| C swing capped 2000 pts | 4588 | 8.20 | 12.50 | -4.22 | 0.90 | -1227.56 | 1710.89 | -0.07 | -0.11 | -0.07 | -0.01 | Neutral (still negative) |
| D MA18 - 0 pts | 5049 | 4.35 | 41.70 | -3.66 | 0.87 | -1584.90 | 1836.97 | -0.13 | -0.21 | -0.14 | -0.02 | Harmful |
| D MA18 - 50 pts | 4777 | 4.98 | 32.80 | -3.94 | 0.89 | -1369.92 | 1651.44 | -0.10 | -0.15 | -0.10 | -0.01 | Harmful |
| E swing clamped [0.5, 3] ATR | 4587 | 7.05 | 14.20 | -4.13 | 0.92 | -966.65 | 1577.38 | -0.07 | -0.12 | -0.07 | -0.00 | Harmful |
| E swing clamped [1, 4] ATR | 4562 | 7.87 | 11.00 | -4.16 | 0.92 | -969.05 | 1553.39 | -0.06 | -0.11 | -0.07 | -0.00 | Neutral (still negative) |
| E swing clamped [0.5, 2] ATR | 4768 | 5.31 | 26.60 | -3.90 | 0.91 | -1072.57 | 1621.97 | -0.09 | -0.16 | -0.07 | -0.00 | Neutral (still negative) |
| F swing with 0.5 ATR floor | 4561 | 8.16 | 10.70 | -4.16 | 0.92 | -982.48 | 1572.32 | -0.07 | -0.11 | -0.07 | -0.00 | Neutral (still negative) |
| F swing with 1.0 ATR floor | 4557 | 8.17 | 10.50 | -4.17 | 0.92 | -993.23 | 1556.32 | -0.06 | -0.11 | -0.07 | -0.00 | Neutral (still negative) |
| F min stop 150 pts (v13 MinStopPoints) | 4558 | 8.16 | 10.50 | -4.16 | 0.92 | -969.33 | 1565.17 | -0.06 | -0.11 | -0.07 | -0.00 | Neutral (still negative) |
| F min stop 300 pts | 4546 | 8.17 | 9.40 | -4.18 | 0.92 | -974.59 | 1568.93 | -0.06 | -0.11 | -0.06 | -0.00 | Neutral (still negative) |

### D1

Existing swing stop: median 9196 pts = $91.96 per 0.01 lot (2.77 ATR; p10-p90 4234-22487 pts), hit in 1.2% of trades = 12.3% of losses; average loss $-8.37 (-0.115 R), worst $-111.65; MFE before a stop-out 0.069 R; winners' MAE median 0.046 R, p90 0.489 R.

| stop | trades | median risk $ | SL hit % | avg loss $ | PF | net $ | maxDD $ | exp R | DEV R | VAL R | OOS R | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A original swing SL (strength 2) | 85 | 91.96 | 1.20 | -8.37 | 2.95 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | base |
| B ATR 1.0x | 94 | 28.05 | 12.80 | -8.56 | 2.40 | 537.84 | 140.61 | 0.16 | -0.12 | 0.03 | 0.62 | Neutral |
| B ATR 1.5x | 91 | 41.69 | 6.60 | -7.61 | 3.00 | 623.07 | 128.43 | 0.12 | -0.06 | 0.04 | 0.42 | Neutral |
| B ATR 2.0x | 85 | 56.86 | 5.90 | -7.84 | 3.04 | 639.21 | 112.29 | 0.10 | -0.04 | 0.01 | 0.31 | Neutral |
| B ATR 2.5x | 85 | 69.42 | 3.50 | -7.04 | 3.50 | 669.83 | 113.60 | 0.09 | 0.01 | -0.01 | 0.25 | Neutral |
| B ATR 3.0x | 85 | 82.35 | 1.20 | -7.35 | 3.36 | 658.20 | 121.87 | 0.07 | 0.01 | -0.00 | 0.21 | Neutral |
| C swing strength 1 | 92 | 65.92 | 5.40 | -10.82 | 2.85 | 802.92 | 166.52 | 0.09 | -0.06 | -0.02 | 0.36 | Harmful |
| C swing strength 3 | 83 | 109.32 | 1.20 | -8.60 | 3.00 | 651.89 | 179.40 | 0.04 | -0.01 | -0.00 | 0.14 | Harmful |
| C swing - 0.5 ATR buffer | 85 | 101.55 | 1.20 | -8.66 | 2.85 | 608.31 | 179.40 | 0.06 | -0.00 | 0.01 | 0.17 | Harmful |
| C swing - 0.25 ATR buffer | 85 | 97.78 | 1.20 | -8.52 | 2.90 | 613.72 | 179.40 | 0.07 | -0.00 | 0.01 | 0.19 | Harmful |
| C swing capped 1000 pts | 114 | 10.10 | 30.70 | -6.71 | 2.00 | 413.96 | 141.37 | 0.36 | -0.20 | -0.14 | 1.61 | Harmful |
| C swing capped 1500 pts (v13) | 102 | 15.10 | 22.50 | -8.42 | 2.10 | 482.89 | 170.90 | 0.31 | -0.21 | 0.10 | 1.21 | Neutral |
| C swing capped 2000 pts | 96 | 20.10 | 15.60 | -8.70 | 2.26 | 513.25 | 143.33 | 0.27 | -0.11 | 0.05 | 0.94 | Neutral |
| D MA18 - 0 pts | 90 | 59.08 | 8.90 | -8.80 | 2.60 | 578.08 | 173.55 | 0.04 | -0.08 | -0.06 | 0.26 | Harmful |
| D MA18 - 50 pts | 90 | 59.33 | 8.90 | -8.89 | 2.56 | 570.58 | 175.05 | 0.04 | -0.08 | -0.06 | 0.26 | Harmful |
| E swing clamped [0.5, 3] ATR | 85 | 70.89 | 2.40 | -6.86 | 3.60 | 676.67 | 121.87 | 0.09 | 0.00 | -0.01 | 0.26 | Neutral |
| E swing clamped [1, 4] ATR | 85 | 87.35 | 2.40 | -7.32 | 3.37 | 659.22 | 139.32 | 0.07 | -0.00 | 0.00 | 0.21 | Neutral |
| E swing clamped [0.5, 2] ATR | 85 | 55.01 | 5.90 | -7.73 | 3.08 | 643.49 | 108.01 | 0.11 | -0.04 | 0.01 | 0.34 | Neutral |
| F swing with 0.5 ATR floor | 85 | 91.96 | 1.20 | -8.37 | 2.95 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | Neutral |
| F swing with 1.0 ATR floor | 85 | 91.96 | 1.20 | -8.37 | 2.95 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | Neutral |
| F min stop 150 pts (v13 MinStopPoints) | 85 | 91.96 | 1.20 | -8.37 | 2.95 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | Neutral |
| F min stop 300 pts | 85 | 91.96 | 1.20 | -8.37 | 2.95 | 619.14 | 179.40 | 0.07 | -0.00 | 0.01 | 0.21 | Neutral |

## 8. Exit analysis (Phase 4): Chandelier vs trailing vs break-even vs hybrids

**The exit stack, not the entry, is where the timeframes differ.** M1: nothing helps; the MA18 close-exit alone costs about half of the loss (removing it improves the result from -$30,212 to -$13,469) because it pays the spread on 43,000 exits, and even the best variant loses $13,000. M5: all 30 variants are negative; pure fixed trailing without break-even or MA18 exit is the least bad (-$1,551, PF 0.95). M15: the two components that turn a break-even system into a loser are the MA18 exit and the $5 break-even stop; removing either brings the result to roughly zero (+$258 and +$0.35), pure Chandelier reaches +$717 (PF 1.05) and pure trailing +$385, but every one of them is negative in the 2020-2023 development window and none is positive in all three splits. D1: the fixed 500-point trailing and the previous strategy's TWK trail destroy the result (-$74 and -$15) because 500 points is a fraction of a daily bar in 2024-2026; volatility-scaled protection does the opposite: ATR trailing 3x from the first tick +$1,703 (PF 8.3, max DD $103), ATR trailing 2x +$1,736, Chandelier 22 x 3 +$1,435 to +$1,477, versus +$619 for the shipped swing protection. The ATR-scaled break-even (1 ATR) with ATR trailing is the only D1 exit positive in DEV, VAL and OOS (+0.15 / +0.31 / +0.30 R) but on 54 trades. **The suspicion in the brief (Chandelier for higher timeframes, trailing for lower) is half confirmed: on D1 volatility-scaled Chandelier/ATR trailing beats everything; on M1/M5/M15 no trailing variant is profitable, so 'trailing performs better on lower timeframes' cannot be shown because nothing performs.**

### M1

| exit method | trades | net $ | PF | maxDD $ | win % | avg trade $ | avg win $ | avg loss $ | giveback avg $ | P->L >$2 | P->L >=1R | exp R DEV/VAL/OOS | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 54116 | -29983.53 | 0.56 | 30009.81 | 20.80 | -0.55 | 3.42 | -1.59 | 2.59 | 4334 | 1753 | -0.407/-0.366/-0.18 | Harmful |
| E01 EA default: BE + swing after 500 + MA18 | 54900 | -30212.35 | 0.55 | 30239.03 | 20.60 | -0.55 | 3.28 | -1.55 | 2.57 | 4608 | 1737 | -0.407/-0.365/-0.177 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 55452 | -30221.67 | 0.56 | 30248.45 | 21.00 | -0.55 | 3.26 | -1.56 | 2.56 | 4617 | 1620 | -0.405/-0.365/-0.172 | Neutral (still negative) |
| E03 Chandelier immediate + BE + MA18 (v13) | 63073 | -32968.55 | 0.53 | 32982.55 | 19.70 | -0.52 | 2.99 | -1.39 | 2.28 | 4287 | 1045 | -0.401/-0.358/-0.174 | Neutral (still negative) |
| E04 Trailing 1000/500/50 + BE + MA18 | 55782 | -29139.71 | 0.58 | 29168.40 | 21.20 | -0.52 | 3.46 | -1.60 | 2.48 | 4804 | 1672 | -0.406/-0.366/-0.163 | Neutral (still negative) |
| E05 BE only + MA18 | 54641 | -30099.39 | 0.55 | 30125.67 | 20.40 | -0.55 | 3.28 | -1.54 | 2.58 | 4627 | 1749 | -0.407/-0.365/-0.175 | Neutral (still negative) |
| E06 Trailing 1000/500/50 without BE + MA18 | 55311 | -29082.58 | 0.60 | 29111.27 | 21.60 | -0.53 | 3.61 | -1.67 | 2.49 | 4513 | 1693 | -0.406/-0.366/-0.168 | Neutral (still negative) |
| E07 Chandelier + Trailing + BE + MA18 | 63860 | -32179.22 | 0.56 | 32194.29 | 20.20 | -0.50 | 3.14 | -1.43 | 2.20 | 4433 | 1021 | -0.401/-0.359/-0.166 | Neutral (still negative) |
| E08 Swing immediate + BE + MA18 | 56018 | -30613.28 | 0.55 | 30638.94 | 20.40 | -0.55 | 3.21 | -1.52 | 2.52 | 4528 | 1697 | -0.411/-0.37/-0.187 | Harmful |
| E09 ATR trail 2.0x immediate + BE + MA18 | 66053 | -33950.64 | 0.54 | 33967.29 | 22.80 | -0.51 | 2.61 | -1.44 | 2.18 | 3779 | 567 | -0.376/-0.342/-0.169 | Neutral (still negative) |
| E10 ATR trail 3.0x immediate + BE + MA18 | 57797 | -30708.42 | 0.55 | 30736.63 | 21.30 | -0.53 | 3.09 | -1.52 | 2.47 | 4394 | 1220 | -0.394/-0.354/-0.171 | Neutral (still negative) |
| E11 ATR trail 1.5x immediate + BE + MA18 | 74268 | -36336.74 | 0.52 | 36352.50 | 23.90 | -0.49 | 2.20 | -1.34 | 1.89 | 3023 | 255 | -0.357/-0.32/-0.159 | Neutral (still negative) |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 56924 | -30068.85 | 0.58 | 30089.71 | 22.10 | -0.53 | 3.28 | -1.61 | 2.47 | 4540 | 1508 | -0.398/-0.358/-0.164 | Helpful (still negative) |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 60696 | -30653.10 | 0.59 | 30673.17 | 25.20 | -0.51 | 2.89 | -1.65 | 2.28 | 3464 | 988 | -0.393/-0.352/-0.162 | Helpful (still negative) |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 43101 | -19554.55 | 0.73 | 19569.59 | 39.00 | -0.45 | 3.10 | -2.73 | 3.14 | 3722 | 1247 | -0.362/-0.313/-0.15 | Helpful (still negative) |
| E15 EA default without MA18 exit | 26494 | -13468.85 | 0.77 | 13507.31 | 26.70 | -0.51 | 6.32 | -3.04 | 4.88 | 5452 | 3055 | -0.368/-0.298/-0.151 | Helpful (still negative) |
| E16 Chandelier immediate without MA18 exit + BE | 58446 | -29488.83 | 0.57 | 29505.08 | 21.00 | -0.51 | 3.20 | -1.49 | 2.50 | 4539 | 1198 | -0.401/-0.362/-0.169 | Neutral (still negative) |
| E17 Swing after 500 + MA18, no BE | 54396 | -30021.64 | 0.56 | 30048.32 | 20.90 | -0.55 | 3.42 | -1.60 | 2.58 | 4331 | 1750 | -0.406/-0.365/-0.181 | Neutral (still negative) |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 63594 | -33229.12 | 0.49 | 33264.26 | 33.60 | -0.52 | 1.49 | -1.63 | 2.22 | 3188 | 500 | -0.383/-0.344/-0.176 | Neutral (still negative) |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 66665 | -32567.91 | 0.53 | 32600.48 | 34.00 | -0.49 | 1.64 | -1.69 | 2.07 | 3597 | 507 | -0.363/-0.324/-0.159 | Neutral (still negative) |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 54826 | -30330.97 | 0.55 | 30357.25 | 22.40 | -0.55 | 3.06 | -1.61 | 2.57 | 3827 | 557 | -0.405/-0.362/-0.182 | Neutral (still negative) |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 55029 | -30034.26 | 0.56 | 30060.54 | 22.40 | -0.55 | 3.12 | -1.62 | 2.55 | 3918 | 577 | -0.401/-0.358/-0.179 | Neutral (still negative) |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 80099 | -39799.81 | 0.48 | 39814.07 | 18.80 | -0.50 | 2.42 | -1.18 | 1.81 | 3599 | 458 | -0.372/-0.336/-0.173 | Neutral (still negative) |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 56902 | -30810.75 | 0.55 | 30839.23 | 20.20 | -0.54 | 3.21 | -1.50 | 2.49 | 4541 | 1488 | -0.405/-0.369/-0.171 | Neutral (still negative) |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 56547 | -30807.93 | 0.56 | 30832.87 | 24.00 | -0.55 | 2.94 | -1.64 | 2.50 | 3552 | 51 | -0.401/-0.355/-0.175 | Neutral (still negative) |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 58021 | -29330.82 | 0.58 | 29347.07 | 21.00 | -0.51 | 3.37 | -1.54 | 2.53 | 4347 | 1211 | -0.401/-0.361/-0.172 | Neutral (still negative) |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 18135 | -6603.32 | 0.88 | 7150.00 | 26.50 | -0.36 | 10.50 | -4.28 | 6.06 | 4838 | 2938 | -0.383/-0.274/-0.113 | Helpful (still negative) |
| E27 BE 1000/10 + swing after 500 + MA18 | 54484 | -30168.29 | 0.56 | 30194.97 | 20.80 | -0.55 | 3.39 | -1.59 | 2.59 | 4419 | 1761 | -0.406/-0.365/-0.181 | Neutral (still negative) |
| E28 BE 2000/10 + swing after 500 + MA18 | 54410 | -29971.80 | 0.56 | 29998.48 | 20.80 | -0.55 | 3.41 | -1.60 | 2.58 | 4347 | 1754 | -0.406/-0.365/-0.181 | Neutral (still negative) |
| E29 time exit 5 bars (not in profit) + EA default | 70448 | -38434.13 | 0.46 | 38461.99 | 12.40 | -0.55 | 3.74 | -1.16 | 2.04 | 5080 | 1953 | -0.413/-0.374/-0.184 | Harmful |

### M5

| exit method | trades | net $ | PF | maxDD $ | win % | avg trade $ | avg win $ | avg loss $ | giveback avg $ | P->L >$2 | P->L >=1R | exp R DEV/VAL/OOS | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 11552 | -4658.80 | 0.82 | 5372.87 | 25.10 | -0.40 | 7.34 | -3.00 | 5.53 | 2469 | 611 | -0.22/-0.174/-0.038 | Harmful |
| E01 EA default: BE + swing after 500 + MA18 | 12320 | -4977.42 | 0.79 | 5314.60 | 25.80 | -0.40 | 6.00 | -2.68 | 5.21 | 2588 | 474 | -0.218/-0.168/-0.042 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 12518 | -4989.61 | 0.80 | 5302.36 | 26.50 | -0.40 | 5.93 | -2.73 | 5.18 | 2617 | 423 | -0.215/-0.159/-0.038 | Neutral (still negative) |
| E03 Chandelier immediate + BE + MA18 (v13) | 13581 | -5544.84 | 0.78 | 5689.59 | 25.30 | -0.41 | 5.66 | -2.50 | 4.82 | 2619 | 351 | -0.209/-0.163/-0.04 | Neutral (still negative) |
| E04 Trailing 1000/500/50 + BE + MA18 | 13165 | -4359.40 | 0.84 | 5421.66 | 29.60 | -0.33 | 5.76 | -2.95 | 4.56 | 2594 | 391 | -0.218/-0.163/-0.039 | Neutral (still negative) |
| E05 BE only + MA18 | 12186 | -5179.04 | 0.78 | 5413.94 | 25.30 | -0.42 | 6.01 | -2.67 | 5.28 | 2592 | 472 | -0.218/-0.17/-0.043 | Harmful |
| E06 Trailing 1000/500/50 without BE + MA18 | 12692 | -4333.80 | 0.85 | 5427.82 | 29.80 | -0.34 | 6.71 | -3.34 | 4.75 | 2531 | 507 | -0.22/-0.169/-0.04 | Harmful |
| E07 Chandelier + Trailing + BE + MA18 | 14343 | -4988.98 | 0.82 | 5815.84 | 28.40 | -0.35 | 5.51 | -2.72 | 4.25 | 2630 | 317 | -0.211/-0.164/-0.041 | Neutral (still negative) |
| E08 Swing immediate + BE + MA18 | 12642 | -5123.54 | 0.79 | 5437.30 | 25.40 | -0.41 | 5.91 | -2.60 | 5.10 | 2605 | 490 | -0.222/-0.17/-0.048 | Harmful |
| E09 ATR trail 2.0x immediate + BE + MA18 | 15203 | -5878.37 | 0.78 | 6371.63 | 27.80 | -0.39 | 4.85 | -2.43 | 4.30 | 2592 | 177 | -0.197/-0.155/-0.048 | Neutral (still negative) |
| E10 ATR trail 3.0x immediate + BE + MA18 | 13017 | -5152.81 | 0.79 | 5505.76 | 26.40 | -0.40 | 5.72 | -2.63 | 4.99 | 2641 | 350 | -0.21/-0.162/-0.036 | Neutral (still negative) |
| E11 ATR trail 1.5x immediate + BE + MA18 | 17589 | -6838.96 | 0.75 | 7118.09 | 29.20 | -0.39 | 3.99 | -2.21 | 3.64 | 2284 | 101 | -0.18/-0.145/-0.054 | Neutral (still negative) |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 13187 | -4832.50 | 0.82 | 5572.24 | 28.70 | -0.37 | 5.67 | -2.82 | 4.86 | 2666 | 396 | -0.213/-0.16/-0.043 | Neutral (still negative) |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 14837 | -5386.16 | 0.82 | 5964.44 | 37.60 | -0.36 | 4.30 | -3.17 | 4.00 | 2047 | 207 | -0.205/-0.159/-0.041 | Neutral (still negative) |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 12226 | -4439.49 | 0.85 | 5228.26 | 48.60 | -0.36 | 4.27 | -4.75 | 4.90 | 2124 | 200 | -0.201/-0.147/-0.039 | Helpful (still negative) |
| E15 EA default without MA18 exit | 7977 | -3058.53 | 0.87 | 3436.19 | 34.70 | -0.38 | 7.62 | -4.85 | 7.99 | 2147 | 541 | -0.184/-0.137/-0.034 | Helpful (still negative) |
| E16 Chandelier immediate without MA18 exit + BE | 12313 | -5245.69 | 0.79 | 5287.07 | 27.40 | -0.43 | 5.94 | -2.89 | 5.47 | 2630 | 378 | -0.208/-0.142/-0.041 | Neutral (still negative) |
| E17 Swing after 500 + MA18, no BE | 11720 | -4397.28 | 0.83 | 5301.82 | 25.40 | -0.38 | 7.26 | -2.98 | 5.45 | 2487 | 616 | -0.221/-0.171/-0.037 | Harmful |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 14018 | -5456.17 | 0.76 | 5921.22 | 41.40 | -0.39 | 3.05 | -3.05 | 4.62 | 1344 | 137 | -0.195/-0.161/-0.042 | Neutral (still negative) |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 15011 | -5035.75 | 0.80 | 6059.64 | 42.20 | -0.34 | 3.25 | -3.21 | 4.19 | 1502 | 131 | -0.186/-0.141/-0.036 | Neutral (still negative) |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 11788 | -4553.81 | 0.82 | 5319.20 | 28.30 | -0.39 | 6.24 | -3.04 | 5.43 | 2098 | 140 | -0.218/-0.16/-0.036 | Neutral (still negative) |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 11876 | -4519.99 | 0.82 | 5348.18 | 28.40 | -0.38 | 6.31 | -3.08 | 5.38 | 2128 | 143 | -0.22/-0.149/-0.042 | Neutral (still negative) |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 17563 | -6981.19 | 0.74 | 7371.73 | 24.60 | -0.40 | 4.58 | -2.03 | 3.72 | 2481 | 162 | -0.189/-0.156/-0.051 | Neutral (still negative) |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 12500 | -5210.72 | 0.78 | 5423.39 | 25.40 | -0.42 | 5.95 | -2.64 | 5.19 | 2623 | 453 | -0.212/-0.167/-0.043 | Neutral (still negative) |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 12307 | -4624.00 | 0.83 | 5363.67 | 30.50 | -0.38 | 5.90 | -3.14 | 5.21 | 2100 | 9 | -0.21/-0.153/-0.035 | Helpful (still negative) |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 11711 | -4719.24 | 0.83 | 5182.94 | 26.60 | -0.40 | 7.33 | -3.20 | 5.80 | 2578 | 485 | -0.207/-0.148/-0.042 | Neutral (still negative) |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 6547 | -1550.84 | 0.95 | 2820.44 | 41.70 | -0.24 | 10.52 | -7.94 | 8.41 | 1776 | 643 | -0.176/-0.128/-0.02 | Helpful (still negative) |
| E27 BE 1000/10 + swing after 500 + MA18 | 11857 | -4673.93 | 0.81 | 5241.87 | 25.10 | -0.39 | 6.92 | -2.85 | 5.42 | 2579 | 589 | -0.22/-0.173/-0.035 | Harmful |
| E28 BE 2000/10 + swing after 500 + MA18 | 11746 | -4625.05 | 0.82 | 5343.96 | 25.20 | -0.39 | 7.16 | -2.95 | 5.46 | 2521 | 618 | -0.221/-0.171/-0.039 | Harmful |
| E29 time exit 5 bars (not in profit) + EA default | 14936 | -6409.18 | 0.73 | 6635.31 | 18.80 | -0.43 | 6.33 | -2.02 | 4.33 | 2848 | 541 | -0.211/-0.18/-0.05 | Harmful |

### M15

| exit method | trades | net $ | PF | maxDD $ | win % | avg trade $ | avg win $ | avg loss $ | giveback avg $ | P->L >$2 | P->L >=1R | exp R DEV/VAL/OOS | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 3949 | -114.93 | 0.99 | 1351.03 | 28.50 | -0.03 | 12.40 | -4.98 | 9.55 | 1324 | 278 | -0.124/-0.053/0.011 | Neutral (still negative) |
| E01 EA default: BE + swing after 500 + MA18 | 4559 | -983.88 | 0.92 | 1581.42 | 32.90 | -0.22 | 7.34 | -4.16 | 8.25 | 1275 | 119 | -0.111/-0.07/-0.004 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 4654 | -869.80 | 0.93 | 1490.84 | 33.60 | -0.19 | 7.29 | -4.19 | 8.11 | 1286 | 99 | -0.1/-0.071/0.001 | Neutral (still negative) |
| E03 Chandelier immediate + BE + MA18 (v13) | 4959 | -1180.46 | 0.91 | 1679.13 | 31.70 | -0.24 | 7.17 | -3.87 | 7.68 | 1341 | 98 | -0.103/-0.072/-0.008 | Harmful |
| E04 Trailing 1000/500/50 + BE + MA18 | 5211 | -852.14 | 0.94 | 1418.75 | 40.40 | -0.16 | 6.52 | -4.94 | 6.46 | 1247 | 71 | -0.101/-0.061/-0.003 | Neutral (still negative) |
| E05 BE only + MA18 | 4488 | -793.93 | 0.93 | 1562.18 | 32.50 | -0.18 | 7.56 | -4.15 | 8.31 | 1259 | 117 | -0.116/-0.062/0.002 | Neutral (still negative) |
| E06 Trailing 1000/500/50 without BE + MA18 | 4842 | -686.13 | 0.96 | 1413.37 | 39.10 | -0.14 | 8.66 | -5.80 | 7.02 | 1320 | 188 | -0.106/-0.056/-0.005 | Neutral (still negative) |
| E07 Chandelier + Trailing + BE + MA18 | 5550 | -1101.40 | 0.93 | 1558.29 | 38.30 | -0.20 | 6.44 | -4.53 | 6.14 | 1313 | 71 | -0.102/-0.056/-0.011 | Neutral (still negative) |
| E08 Swing immediate + BE + MA18 | 4641 | -889.70 | 0.93 | 1525.77 | 32.60 | -0.19 | 7.27 | -4.02 | 8.07 | 1273 | 123 | -0.112/-0.072/-0.003 | Harmful |
| E09 ATR trail 2.0x immediate + BE + MA18 | 5707 | -1522.08 | 0.89 | 2030.91 | 33.00 | -0.27 | 6.31 | -3.62 | 6.70 | 1499 | 57 | -0.112/-0.062/-0.015 | Harmful |
| E10 ATR trail 3.0x immediate + BE + MA18 | 4801 | -979.46 | 0.92 | 1609.37 | 33.10 | -0.20 | 7.13 | -4.04 | 7.87 | 1324 | 94 | -0.105/-0.066/-0.007 | Neutral (still negative) |
| E11 ATR trail 1.5x immediate + BE + MA18 | 6599 | -1527.60 | 0.89 | 2477.66 | 32.60 | -0.23 | 5.70 | -3.16 | 5.57 | 1509 | 27 | -0.107/-0.072/-0.014 | Harmful |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 5016 | -1079.57 | 0.92 | 1555.11 | 36.20 | -0.21 | 6.77 | -4.35 | 7.46 | 1350 | 81 | -0.096/-0.047/-0.008 | Neutral (still negative) |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 5950 | -1182.49 | 0.93 | 1778.44 | 49.20 | -0.20 | 5.08 | -5.30 | 5.48 | 1096 | 52 | -0.113/-0.045/-0.01 | Harmful |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 5316 | -726.18 | 0.95 | 1667.46 | 56.80 | -0.14 | 5.10 | -7.03 | 6.17 | 1119 | 43 | -0.116/-0.025/-0.003 | Neutral (still negative) |
| E15 EA default without MA18 exit | 3478 | 257.97 | 1.02 | 775.67 | 42.50 | 0.07 | 8.01 | -6.34 | 10.69 | 987 | 117 | -0.108/-0.01/-0.0 | Helpful |
| E16 Chandelier immediate without MA18 exit + BE | 4505 | -530.74 | 0.96 | 1281.01 | 34.10 | -0.12 | 7.68 | -4.38 | 8.60 | 1301 | 97 | -0.105/-0.047/0.009 | Helpful (still negative) |
| E17 Swing after 500 + MA18, no BE | 4030 | 0.35 | 1.00 | 1368.21 | 29.20 | 0.00 | 11.88 | -4.90 | 9.36 | 1336 | 270 | -0.114/-0.065/0.014 | Neutral |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 4959 | -946.79 | 0.92 | 1873.60 | 46.10 | -0.19 | 5.01 | -5.07 | 7.79 | 715 | 53 | -0.117/-0.082/0.008 | Harmful |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 5373 | -1071.98 | 0.92 | 1956.95 | 46.70 | -0.20 | 5.12 | -5.33 | 7.10 | 796 | 54 | -0.108/-0.068/0.001 | Neutral (still negative) |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 4073 | -179.06 | 0.99 | 1444.53 | 32.80 | -0.04 | 10.12 | -5.09 | 9.36 | 1143 | 57 | -0.116/-0.054/0.015 | Neutral (still negative) |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 4114 | -33.52 | 1.00 | 1383.88 | 32.90 | -0.01 | 10.26 | -5.14 | 9.22 | 1162 | 57 | -0.101/-0.059/0.016 | Helpful (still negative) |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 6363 | -1982.15 | 0.85 | 2429.57 | 30.00 | -0.31 | 6.07 | -3.12 | 6.02 | 1467 | 54 | -0.107/-0.058/-0.026 | Neutral (still negative) |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 4602 | -1075.04 | 0.91 | 1554.23 | 32.20 | -0.23 | 7.41 | -4.10 | 8.24 | 1292 | 117 | -0.118/-0.077/0.002 | Harmful |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 4271 | -16.64 | 1.00 | 1282.11 | 35.40 | -0.00 | 9.62 | -5.29 | 8.83 | 1167 | 3 | -0.1/-0.035/0.009 | Helpful (still negative) |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 4014 | 716.79 | 1.05 | 1172.34 | 30.50 | 0.18 | 12.41 | -5.20 | 9.96 | 1333 | 203 | -0.107/-0.043/0.038 | Helpful |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 3196 | 384.57 | 1.02 | 834.85 | 54.90 | 0.12 | 10.30 | -12.28 | 9.96 | 806 | 176 | -0.087/0.056/0.0 | Helpful |
| E27 BE 1000/10 + swing after 500 + MA18 | 4193 | -424.88 | 0.97 | 1399.51 | 29.00 | -0.10 | 10.50 | -4.50 | 9.12 | 1386 | 232 | -0.115/-0.072/0.011 | Harmful |
| E28 BE 2000/10 + swing after 500 + MA18 | 4083 | -431.98 | 0.97 | 1362.24 | 28.50 | -0.11 | 11.57 | -4.78 | 9.47 | 1387 | 273 | -0.114/-0.065/0.006 | Neutral (still negative) |
| E29 time exit 5 bars (not in profit) + EA default | 5224 | -1333.46 | 0.89 | 1916.68 | 26.80 | -0.26 | 7.52 | -3.25 | 7.22 | 1444 | 135 | -0.125/-0.073/-0.012 | Harmful |

### D1

| exit method | trades | net $ | PF | maxDD $ | win % | avg trade $ | avg win $ | avg loss $ | giveback avg $ | P->L >$2 | P->L >=1R | exp R DEV/VAL/OOS | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E00 SL only + MA18 exit (no BE, no protection) | 42 | 154.44 | 1.12 | 323.64 | 31.00 | 3.68 | 113.55 | -45.58 | 133.12 | 28 | 5 | 0.01/0.099/0.24 | Neutral |
| E01 EA default: BE + swing after 500 + MA18 | 85 | 619.14 | 2.95 | 179.40 | 49.40 | 7.28 | 22.32 | -8.37 | 50.80 | 37 | 3 | -0.004/0.008/0.208 | base |
| E02 Chandelier(22,3.0) after 500 + BE + MA18 | 87 | 1476.57 | 5.81 | 176.80 | 50.60 | 16.97 | 40.53 | -8.08 | 39.50 | 37 | 2 | 0.003/0.05/0.342 | Neutral |
| E03 Chandelier immediate + BE + MA18 (v13) | 88 | 1435.00 | 5.12 | 119.09 | 50.00 | 16.31 | 40.53 | -8.94 | 38.78 | 37 | 1 | -0.0/0.02/0.342 | Neutral |
| E04 Trailing 1000/500/50 + BE + MA18 | 158 | -73.58 | 0.92 | 396.80 | 79.10 | -0.47 | 6.96 | -39.31 | 11.78 | 20 | 0 | -0.025/-0.009/0.027 | Harmful |
| E05 BE only + MA18 | 83 | 628.60 | 2.98 | 179.40 | 48.20 | 7.57 | 23.67 | -8.37 | 51.98 | 37 | 3 | -0.003/0.039/0.201 | Neutral |
| E06 Trailing 1000/500/50 without BE + MA18 | 147 | -11.27 | 0.99 | 396.80 | 88.40 | -0.08 | 10.29 | -79.36 | 14.56 | 14 | 0 | -0.047/0.027/0.017 | Harmful |
| E07 Chandelier + Trailing + BE + MA18 | 158 | 110.65 | 1.15 | 246.01 | 78.50 | 0.70 | 7.01 | -30.33 | 10.53 | 20 | 0 | -0.027/-0.013/0.03 | Harmful |
| E08 Swing immediate + BE + MA18 | 85 | 622.99 | 2.98 | 175.55 | 49.40 | 7.33 | 22.32 | -8.27 | 50.75 | 37 | 3 | -0.004/0.01/0.208 | Neutral |
| E09 ATR trail 2.0x immediate + BE + MA18 | 93 | 1735.82 | 4.35 | 154.85 | 50.50 | 18.66 | 47.96 | -12.65 | 34.57 | 39 | 1 | -0.005/0.102/0.337 | Neutral |
| E10 ATR trail 3.0x immediate + BE + MA18 | 87 | 1703.15 | 8.32 | 103.48 | 50.60 | 19.58 | 44.00 | -6.29 | 36.95 | 36 | 1 | 0.016/0.09/0.354 | Neutral |
| E11 ATR trail 1.5x immediate + BE + MA18 | 109 | 1686.50 | 5.08 | 115.96 | 57.80 | 15.47 | 33.33 | -10.60 | 27.97 | 37 | 0 | -0.015/0.14/0.178 | Harmful |
| E12 ATR trail 2.0x after 500 + BE + MA18 | 90 | 1509.50 | 3.06 | 396.80 | 52.20 | 16.77 | 47.69 | -19.26 | 37.51 | 36 | 1 | 0.031/0.072/0.327 | Neutral |
| E13 TWK 3-stage trail (previous strategy) + MA18, no BE | 160 | -14.51 | 0.98 | 396.80 | 92.50 | -0.09 | 5.56 | -69.84 | 9.44 | 8 | 0 | -0.025/0.0/0.026 | Harmful |
| E14 TWK 3-stage trail alone (no MA18 exit, no BE) | 156 | 319.59 | 1.66 | 161.29 | 93.60 | 2.05 | 5.50 | -48.28 | 7.32 | 8 | 0 | -0.012/-0.001/0.034 | Harmful |
| E15 EA default without MA18 exit | 82 | 665.65 | 2.96 | 237.05 | 51.20 | 8.12 | 23.92 | -9.69 | 54.88 | 35 | 3 | 0.011/-0.019/0.319 | Neutral |
| E16 Chandelier immediate without MA18 exit + BE | 85 | 1372.98 | 4.51 | 150.77 | 50.60 | 16.15 | 41.03 | -10.29 | 41.43 | 36 | 2 | -0.019/0.029/0.307 | Neutral |
| E17 Swing after 500 + MA18, no BE | 43 | 127.18 | 1.10 | 323.64 | 32.60 | 2.96 | 97.81 | -42.83 | 131.38 | 28 | 5 | 0.0/0.571/0.212 | Neutral |
| E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18 | 47 | 240.80 | 1.26 | 333.01 | 36.20 | 5.12 | 69.40 | -31.30 | 117.72 | 29 | 5 | 0.04/0.273/0.21 | Neutral |
| E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18 | 54 | 1280.14 | 2.39 | 313.90 | 40.70 | 23.71 | 100.12 | -28.83 | 81.09 | 31 | 3 | 0.151/0.307/0.296 | Neutral |
| E20 R-scaled: BE 1R, swing after 1R, MA18 | 42 | 35.50 | 1.03 | 346.22 | 31.00 | 0.84 | 101.05 | -44.07 | 135.95 | 28 | 5 | 0.035/0.137/0.185 | Neutral |
| E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18 | 44 | -33.94 | 0.98 | 692.32 | 29.50 | -0.77 | 128.00 | -54.77 | 130.77 | 29 | 5 | 0.234/0.067/0.257 | Neutral (still negative) |
| E22 Chandelier(22,2.0) immediate + BE + MA18 | 97 | 1155.58 | 2.58 | 156.71 | 52.60 | 11.91 | 36.98 | -18.26 | 38.98 | 37 | 0 | -0.032/0.063/0.291 | Neutral |
| E23 Chandelier(22,4.0) immediate + BE + MA18 | 83 | 1258.20 | 6.04 | 120.47 | 50.60 | 15.16 | 35.90 | -6.94 | 44.40 | 35 | 1 | 0.009/0.063/0.292 | Neutral |
| E24 R-lock: +1R lock +0.5R, swing, MA18, no BE | 48 | 253.78 | 1.20 | 323.64 | 47.90 | 5.29 | 67.24 | -51.71 | 114.22 | 24 | 0 | -0.091/0.192/0.22 | Neutral |
| E25 Chandelier immediate, no BE, no MA18 (pure chandelier) | 44 | 1094.93 | 1.86 | 319.72 | 38.60 | 24.89 | 139.41 | -47.22 | 105.39 | 25 | 2 | -0.089/0.174/0.689 | Neutral |
| E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing) | 143 | 63.05 | 1.05 | 329.16 | 89.50 | 0.44 | 10.74 | -87.48 | 14.74 | 14 | 0 | -0.029/-0.007/0.014 | Harmful |
| E27 BE 1000/10 + swing after 500 + MA18 | 73 | 567.65 | 2.19 | 172.26 | 38.40 | 7.78 | 37.35 | -11.38 | 63.52 | 41 | 4 | -0.044/0.146/0.198 | Harmful |
| E28 BE 2000/10 + swing after 500 + MA18 | 57 | 421.09 | 1.55 | 361.59 | 35.10 | 7.39 | 59.06 | -21.11 | 91.71 | 34 | 5 | 0.044/0.208/0.252 | Neutral |
| E29 time exit 5 bars (not in profit) + EA default | 88 | 636.23 | 3.12 | 132.63 | 48.90 | 7.23 | 21.76 | -7.49 | 49.35 | 39 | 3 | -0.018/0.028/0.208 | Neutral |

### Section 12 summary table (net $ / PF / max DD $ / win % / exp R / giveback $ / P->L >$2)

| TF | Chandelier (E03) | Trailing (E04) | Break-even only (E05) | Chandelier+Trailing (E07) | Swing = EA (E01) | Previous TWK trail (E13) | ATR trail 2x (E09) |
|---|---:|---:|---:|---:|---:|---:|---:|
| M1 | -32968.55 / 0.53 / 32982.55 / 19.7 / -0.324 / 2.28 / 4287 | -29139.71 / 0.584 / 29168.4 / 21.2 / -0.319 / 2.48 / 4804 | -30099.39 / 0.549 / 30125.67 / 20.4 / -0.325 / 2.58 / 4627 | -32179.22 / 0.557 / 32194.29 / 20.2 / -0.32 / 2.2 / 4433 | -30212.35 / 0.551 / 30239.03 / 20.6 / -0.325 / 2.57 / 4608 | -30653.1 / 0.59 / 30673.17 / 25.2 / -0.306 / 2.28 / 3464 | -33950.64 / 0.537 / 33967.29 / 22.8 / -0.302 / 2.18 / 3779 |
| M5 | -5544.84 / 0.778 / 5689.59 / 25.3 / -0.148 / 4.82 / 2619 | -4359.4 / 0.837 / 5421.66 / 29.6 / -0.144 / 4.56 / 2594 | -5179.04 / 0.782 / 5413.94 / 25.3 / -0.153 / 5.28 / 2592 | -4988.98 / 0.818 / 5815.84 / 28.4 / -0.144 / 4.25 / 2630 | -4977.42 / 0.793 / 5314.6 / 25.8 / -0.152 / 5.21 / 2588 | -5386.16 / 0.816 / 5964.44 / 37.6 / -0.138 / 4.0 / 2047 | -5878.37 / 0.778 / 6371.63 / 27.8 / -0.142 / 4.3 / 2592 |
| M15 | -1180.46 / 0.905 / 1679.13 / 31.7 / -0.065 / 7.68 / 1341 | -852.14 / 0.942 / 1418.75 / 40.4 / -0.055 / 6.46 / 1247 | -793.93 / 0.933 / 1562.18 / 32.5 / -0.065 / 8.31 / 1259 | -1101.4 / 0.926 / 1558.29 / 38.3 / -0.059 / 6.14 / 1313 | -983.88 / 0.918 / 1581.42 / 32.9 / -0.066 / 8.25 / 1275 | -1182.49 / 0.926 / 1778.44 / 49.2 / -0.061 / 5.48 / 1096 | -1522.08 / 0.886 / 2030.91 / 33.0 / -0.071 / 6.7 / 1499 |
| D1 | 1435.0 / 5.118 / 119.09 / 50.0 / 0.119 / 38.78 / 37 | -73.58 / 0.922 / 396.8 / 79.1 / -0.002 / 11.78 / 20 | 628.6 / 2.975 / 179.4 / 48.2 / 0.081 / 51.98 / 37 | 110.65 / 1.146 / 246.01 / 78.5 / -0.002 / 10.53 / 20 | 619.14 / 2.946 / 179.4 / 49.4 / 0.072 / 50.8 / 37 | -14.51 / 0.983 / 396.8 / 92.5 / 0.001 / 9.44 / 8 | 1735.82 / 4.348 / 154.85 / 50.5 / 0.141 / 34.57 / 39 |

### Section 22: current EA vs previous trailing-SL strategy vs hybrids

| TF | Current EA | Current entry + previous TWK trail | TWK trail alone | Current entry + Chandelier | ATR-adaptive exit | R-adaptive exit |
|---|---:|---:|---:|---:|---:|---:|
| M1 | -30212.35 / 0.551 / 30239.03 / -0.325 | -30653.1 / 0.59 / 30673.17 / -0.306 | -19554.55 / 0.727 / 19569.59 / -0.269 | -32968.55 / 0.53 / 32982.55 / -0.324 | -32567.91 / 0.533 / 32600.48 / -0.291 | -30034.26 / 0.561 / 30060.54 / -0.323 |
| M5 | -4977.42 / 0.793 / 5314.6 / -0.152 | -5386.16 / 0.816 / 5964.44 / -0.138 | -4439.49 / 0.851 / 5228.26 / -0.128 | -5544.84 / 0.778 / 5689.59 / -0.148 | -5035.75 / 0.804 / 6059.64 / -0.133 | -4519.99 / 0.825 / 5348.18 / -0.154 |
| M15 | -983.88 / 0.918 / 1581.42 / -0.066 | -1182.49 / 0.926 / 1778.44 / -0.061 | -726.18 / 0.955 / 1667.46 / -0.054 | -1180.46 / 0.905 / 1679.13 / -0.065 | -1071.98 / 0.923 / 1956.95 / -0.068 | -33.52 / 0.998 / 1383.88 / -0.058 |
| D1 | 619.14 / 2.946 / 179.4 / 0.072 | -14.51 / 0.983 / 396.8 / 0.001 | 319.59 / 1.662 / 161.29 / 0.007 | 1435.0 / 5.118 / 119.09 / 0.119 | 1280.14 / 2.388 / 313.9 / 0.248 | -33.94 / 0.98 / 692.32 / 0.189 |

Cell: net $ / PF / max DD $ / expectancy R.

## 9. Profit giveback and profitable-to-loss reversals

**Profit giveback is the mechanism of failure on every timeframe.** On M15 the trades were collectively $36,607 in unrealized profit at their best and realized -$984; the median trade gives back 100% of its best profit (it ends at or below zero) and 62% of losing trades were at least $1 in profit first. The break-even stop is the largest single culprit: the 1,179 M15 trades that ended on the break-even stop had an average best profit of $10.41 and returned $0 net; on D1 the 70 break-even exits averaged $37 of unrealized profit and returned -$81 net including swap, and one trade gave back $977. Profit given up by profitable-to-loss trades (>$1 threshold) is $9,605 on M15 and $2,081 on D1, i.e. several times the realized result. The MA18 exit gives back the most per trade among the exits that close in the money on lower timeframes because it fires one bar late and pays the spread. Reversals cluster in strong-trend/low-volatility regimes and in the London/New York overlap on D1.

| TF | trades | total MFE $ | realized $ | avg giveback $ | median $ | worst $ | median giveback % of MFE | share ever >= $1 | avg DD after MFE $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 54900 | 110747.57 | -30212.35 | 2.57 | 1.66 | 117.72 | 163.70 | 0.38 | 2.97 |
| M5 | 12320 | 59260.29 | -4977.42 | 5.21 | 3.61 | 177.52 | 148.30 | 0.61 | 5.93 |
| M15 | 4559 | 36607.12 | -983.88 | 8.25 | 6.11 | 181.04 | 100.00 | 0.76 | 9.34 |
| D1 | 85 | 4937.08 | 619.14 | 50.80 | 17.82 | 977.11 | 100.00 | 1.00 | 50.10 |
| D1_23y | 329 | 10934.30 | 121.32 | 32.87 | 16.45 | 977.11 | 100.00 | 0.97 | 34.07 |

Giveback by exit mechanism (trades / net $ / avg MFE $ / avg giveback $ / P->L >$2):

| TF | exit | trades | net $ | avg MFE $ | avg giveback $ | P->L >$2 | P->L damage $ |
|---|---:|---:|---:|---:|---:|---:|---:|
| M1 | MA18_exit | 42814 | -27045.59 | 1.79 | 2.42 | 3343 | -7186.23 |
| M1 | SL_breakeven | 1486 | -36.98 | 8.02 | 8.05 | 1074 | -38.76 |
| M1 | SL_initial | 9186 | -14690.76 | 0.18 | 1.78 | 189 | -1050.19 |
| M1 | SL_swing | 1413 | 11553.58 | 14.68 | 6.50 | 2 | -6.94 |
| M1 | end_of_test | 1 | 7.39 | 18.53 | 11.14 | 0 | 0.00 |
| M5 | MA18_exit | 8722 | -7877.99 | 3.39 | 4.29 | 1593 | -4804.58 |
| M5 | SL_breakeven | 1458 | -4.74 | 9.32 | 9.32 | 811 | -6.33 |
| M5 | SL_initial | 1390 | -5214.78 | 0.72 | 4.47 | 184 | -1246.06 |
| M5 | SL_swing | 750 | 8120.09 | 20.14 | 9.31 | 0 | 0.00 |
| M15 | MA18_exit | 2487 | -3351.94 | 5.65 | 7.00 | 688 | -3410.33 |
| M15 | SL_breakeven | 1179 | -30.97 | 10.41 | 10.44 | 481 | -33.35 |
| M15 | SL_initial | 485 | -2853.22 | 1.12 | 7.00 | 106 | -780.44 |
| M15 | SL_swing | 408 | 5252.25 | 23.86 | 10.98 | 0 | 0.00 |
| D1 | MA18_exit | 7 | -36.69 | 75.08 | 80.32 | 3 | -168.38 |
| D1 | SL_breakeven | 70 | -81.05 | 36.63 | 37.79 | 33 | -88.58 |
| D1 | SL_initial | 1 | -39.25 | 2.69 | 41.94 | 1 | -39.25 |
| D1 | SL_swing | 7 | 776.13 | 263.51 | 152.63 | 0 | 0.00 |
| D1_23y | MA18_exit | 58 | -647.11 | 36.70 | 47.85 | 29 | -818.31 |
| D1_23y | SL_breakeven | 232 | -322.08 | 21.28 | 22.66 | 117 | -356.91 |
| D1_23y | SL_initial | 10 | -225.48 | 1.76 | 24.31 | 4 | -113.64 |
| D1_23y | SL_swing | 29 | 1315.98 | 132.84 | 87.46 | 8 | -95.86 |

Giveback by direction and session (net $ / avg giveback $ / P->L >$2):

| TF | direction and session |
|---|---:|
| M1 | long: -13584.05 / 2.44 / 1978; short: -16628.3 / 2.68 / 2630; Asia: -8282.07 / 2.31 / 1073; London: -7029.13 / 2.41 / 926; London/NY: -5514.53 / 3.1 / 1299; NewYork: -7363.81 / 2.76 / 1116; Sydney: -2022.81 / 2.04 / 194 |
| M5 | long: -2569.95 / 4.84 / 1318; short: -2407.47 / 5.63 / 1270; Asia: -1219.03 / 4.73 / 665; London: -1731.58 / 4.59 / 582; London/NY: -847.86 / 6.51 / 743; NewYork: -617.16 / 5.52 / 483; Sydney: -561.78 / 4.15 / 115 |
| M15 | long: -267.89 / 7.87 / 692; short: -715.99 / 8.68 / 583; Asia: -45.95 / 7.65 / 327; London: -1395.02 / 7.21 / 337; London/NY: -123.91 / 9.26 / 325; NewYork: 222.79 / 9.16 / 235; Sydney: 358.22 / 9.07 / 51 |
| D1 | long: 695.81 / 64.73 / 29; short: -76.67 / 23.9 / 8; Asia: 477.99 / 65.33 / 19; London: 231.89 / 40.88 / 2; London/NY: -195.34 / 30.04 / 10; NewYork: 104.6 / 45.97 / 5; Sydney: -0.0 / 18.07 / 1 |
| D1_23y | long: -116.89 / 37.63 / 146; short: 238.21 / 21.81 / 12; Asia: 259.54 / 43.09 / 63; London: 123.29 / 24.67 / 17; London/NY: -238.97 / 27.62 / 50; NewYork: -36.83 / 26.17 / 25; Sydney: 14.28 / 33.07 / 3 |

Profitable -> loss reversals by threshold (count / share of losers / realized loss $ / profit given up $ / share of total losses / price continued >= 1R after exit):

| TF | threshold | trades | share of losers | realized loss $ | profit given up $ | share of losses | continued >= 1R | exit mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 1usd | 9638 | 0.22 | -16606.57 | 26990.15 | 0.25 | 0.35 | {"MA18_exit": 8085, "SL_breakeven": 1074, "SL_initial": 477, "SL_swing": 2} |
| M1 | 2usd | 4608 | 0.11 | -8282.12 | 19923.88 | 0.12 | 0.36 | {"MA18_exit": 3343, "SL_breakeven": 1074, "SL_initial": 189, "SL_swing": 2} |
| M1 | 5usd | 1085 | 0.03 | -129.74 | 9206.39 | 0.00 | 0.38 | {"SL_breakeven": 1071, "SL_initial": 11, "SL_swing": 2, "MA18_exit": 1} |
| M1 | 10usd | 220 | 0.01 | -60.03 | 3413.76 | 0.00 | 0.38 | {"SL_breakeven": 215, "SL_initial": 4, "MA18_exit": 1} |
| M1 | 1R | 1737 | 0.04 | -1025.13 | 6147.25 | 0.01 | 0.55 | {"MA18_exit": 1289, "SL_breakeven": 289, "SL_initial": 157, "SL_swing": 2} |
| M1 | 2R | 145 | 0.00 | -96.15 | 726.77 | 0.00 | 0.68 | {"MA18_exit": 82, "SL_breakeven": 35, "SL_initial": 27, "SL_swing": 1} |
| M1 | 3R | 31 | 0.00 | -41.49 | 163.70 | 0.00 | 0.71 | {"MA18_exit": 12, "SL_initial": 11, "SL_breakeven": 8} |
| M5 | 1usd | 4115 | 0.46 | -10487.92 | 16433.05 | 0.44 | 0.38 | {"MA18_exit": 2953, "SL_breakeven": 811, "SL_initial": 351} |
| M5 | 2usd | 2588 | 0.29 | -6056.98 | 14222.67 | 0.25 | 0.37 | {"MA18_exit": 1593, "SL_breakeven": 811, "SL_initial": 184} |
| M5 | 5usd | 813 | 0.09 | -42.56 | 8709.19 | 0.00 | 0.37 | {"SL_breakeven": 809, "SL_initial": 4} |
| M5 | 10usd | 275 | 0.03 | -5.22 | 4980.60 | 0.00 | 0.36 | {"SL_breakeven": 275} |
| M5 | 1R | 474 | 0.05 | -392.39 | 2873.19 | 0.02 | 0.60 | {"MA18_exit": 292, "SL_breakeven": 112, "SL_initial": 70} |
| M5 | 2R | 35 | 0.00 | -15.07 | 324.02 | 0.00 | 0.74 | {"MA18_exit": 17, "SL_breakeven": 13, "SL_initial": 5} |
| M5 | 3R | 5 | 0.00 | -1.87 | 93.78 | 0.00 | 0.60 | {"SL_breakeven": 3, "SL_initial": 1, "MA18_exit": 1} |
| M15 | 1usd | 1786 | 0.62 | -6726.34 | 9605.04 | 0.56 | 0.41 | {"MA18_exit": 1100, "SL_breakeven": 481, "SL_initial": 205} |
| M15 | 2usd | 1275 | 0.44 | -4224.11 | 8850.17 | 0.35 | 0.39 | {"MA18_exit": 688, "SL_breakeven": 481, "SL_initial": 106} |
| M15 | 5usd | 485 | 0.17 | -44.74 | 6261.81 | 0.00 | 0.38 | {"SL_breakeven": 478, "MA18_exit": 6, "SL_initial": 1} |
| M15 | 10usd | 210 | 0.07 | -9.79 | 4349.18 | 0.00 | 0.36 | {"SL_breakeven": 209, "MA18_exit": 1} |
| M15 | 1R | 119 | 0.04 | -107.26 | 1781.42 | 0.01 | 0.64 | {"MA18_exit": 51, "SL_breakeven": 48, "SL_initial": 20} |
| M15 | 2R | 7 | 0.00 | -6.23 | 106.12 | 0.00 | 0.86 | {"SL_breakeven": 3, "MA18_exit": 2, "SL_initial": 2} |
| M15 | 3R | 2 | 0.00 | -0.92 | 38.71 | 0.00 | 1.00 | {"SL_breakeven": 1, "MA18_exit": 1} |
| D1 | 1usd | 38 | 1.00 | -318.23 | 2080.84 | 1.00 | 0.34 | {"SL_breakeven": 33, "MA18_exit": 4, "SL_initial": 1} |
| D1 | 2usd | 37 | 0.97 | -296.21 | 2079.39 | 0.93 | 0.32 | {"SL_breakeven": 33, "MA18_exit": 3, "SL_initial": 1} |
| D1 | 5usd | 33 | 0.87 | -88.58 | 2065.17 | 0.28 | 0.33 | {"SL_breakeven": 33} |
| D1 | 10usd | 27 | 0.71 | -81.63 | 2023.72 | 0.26 | 0.37 | {"SL_breakeven": 27} |
| D1 | 1R | 3 | 0.08 | -27.79 | 1162.18 | 0.09 | 0.33 | {"SL_breakeven": 3} |
| D1 | 2R | 1 | 0.03 | -12.16 | 964.95 | 0.04 | 1.00 | {"SL_breakeven": 1} |
| D1 | 3R | 1 | 0.03 | -12.16 | 964.95 | 0.04 | 1.00 | {"SL_breakeven": 1} |
| D1_23y | 1usd | 167 | 0.94 | -1615.18 | 4112.43 | 0.87 | 0.43 | {"SL_breakeven": 117, "MA18_exit": 36, "SL_swing": 8, "SL_initial": 6} |
| D1_23y | 2usd | 158 | 0.89 | -1384.73 | 4097.10 | 0.74 | 0.41 | {"SL_breakeven": 117, "MA18_exit": 29, "SL_swing": 8, "SL_initial": 4} |
| D1_23y | 5usd | 130 | 0.73 | -487.56 | 3994.08 | 0.26 | 0.39 | {"SL_breakeven": 117, "SL_swing": 8, "MA18_exit": 5} |
| D1_23y | 10usd | 94 | 0.53 | -421.56 | 3747.29 | 0.23 | 0.39 | {"SL_breakeven": 81, "SL_swing": 8, "MA18_exit": 5} |
| D1_23y | 1R | 18 | 0.10 | -151.05 | 1734.21 | 0.08 | 0.39 | {"SL_breakeven": 11, "MA18_exit": 4, "SL_swing": 3} |
| D1_23y | 2R | 5 | 0.03 | -43.08 | 1089.92 | 0.02 | 0.60 | {"SL_breakeven": 3, "MA18_exit": 2} |
| D1_23y | 3R | 3 | 0.02 | -28.66 | 1026.87 | 0.01 | 0.67 | {"SL_breakeven": 3} |

Full per-trade reversal reports: `results/trade_analysis/p2l_{TF}_{threshold}.csv` (entry/exit time, direction, entry, initial SL, max favourable price, max unrealized profit and its time, exit, P&L, drawdown after MFE, exit mechanism, indicator state at the MFE bar and at exit).

## 10. Loss pattern analysis

**Why trades lose.** Half of all lower-timeframe losses (52% on M15, similar on M5/M1) come from entries that never reached 0.25R: the breakout stop fills on the high of a bar that then reverses, which is the signature of a stop-entry system paying the spread on noise. Whipsaws (MA18 exit within three bars) are another 13%, low-liquidity hours 7%, news/volatility bars 6%; stop width ('excessive SL') explains under 4%. On D1 the pattern is different: 64% of the loss comes from eight bad entries, 13% from protection that was too tight (the break-even stop closed trades that then ran >= 1R), and 'trailing too loose' is negligible. Category rules and every classified trade are in `results/trade_analysis/`.

| TF | category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |
|---|---:|---:|---:|---:|---:|---:|
| M1 | 01 bad entry (never reached 0.25R) | 19585 | -33702.94 | -1.72 | 0.19 | 50.10 |
| M1 | 09 news/volatility event | 3083 | -8278.70 | -2.69 | 0.79 | 12.30 |
| M1 | 10 low-liquidity hour | 5341 | -7304.00 | -1.37 | 0.31 | 10.90 |
| M1 | 12 other | 4188 | -6242.86 | -1.49 | 1.18 | 9.30 |
| M1 | 03 whipsaw (MA18 exit within 3 bars) | 3078 | -5438.13 | -1.77 | 0.08 | 8.10 |
| M1 | 02 correct entry, market reversal | 2526 | -3116.86 | -1.23 | 1.83 | 4.60 |
| M1 | 04 excessive SL | 243 | -1631.60 | -6.71 | 0.83 | 2.40 |
| M1 | 11 spread/slippage (positive before costs) | 4838 | -912.56 | -0.19 | 2.90 | 1.40 |
| M1 | 06 trailing/protection too loose (gave back >60% of >=1R) | 577 | -588.54 | -1.02 | 2.50 | 0.90 |
| M1 | 05 trailing/protection too tight | 1 | -0.87 | -0.87 | 7.57 | 0.00 |
| M5 | 01 bad entry (never reached 0.25R) | 3290 | -11610.11 | -3.53 | 0.54 | 48.40 |
| M5 | 12 other | 1144 | -2735.07 | -2.39 | 1.80 | 11.40 |
| M5 | 10 low-liquidity hour | 1118 | -2573.28 | -2.30 | 0.78 | 10.70 |
| M5 | 03 whipsaw (MA18 exit within 3 bars) | 807 | -2330.17 | -2.89 | 0.30 | 9.70 |
| M5 | 09 news/volatility event | 357 | -2238.14 | -6.27 | 1.61 | 9.30 |
| M5 | 02 correct entry, market reversal | 765 | -1323.50 | -1.73 | 2.41 | 5.50 |
| M5 | 04 excessive SL | 65 | -821.50 | -12.64 | 1.57 | 3.40 |
| M5 | 06 trailing/protection too loose (gave back >60% of >=1R) | 198 | -281.07 | -1.42 | 3.10 | 1.20 |
| M5 | 11 spread/slippage (positive before costs) | 1214 | -98.87 | -0.08 | 7.89 | 0.40 |
| M15 | 01 bad entry (never reached 0.25R) | 1026 | -6271.21 | -6.11 | 0.98 | 52.30 |
| M15 | 03 whipsaw (MA18 exit within 3 bars) | 323 | -1620.86 | -5.02 | 0.67 | 13.50 |
| M15 | 12 other | 425 | -1425.09 | -3.35 | 2.31 | 11.90 |
| M15 | 10 low-liquidity hour | 211 | -800.23 | -3.79 | 2.03 | 6.70 |
| M15 | 09 news/volatility event | 81 | -756.44 | -9.34 | 2.03 | 6.30 |
| M15 | 02 correct entry, market reversal | 240 | -564.00 | -2.35 | 3.07 | 4.70 |
| M15 | 04 excessive SL | 20 | -460.12 | -23.01 | 1.30 | 3.80 |
| M15 | 06 trailing/protection too loose (gave back >60% of >=1R) | 50 | -78.47 | -1.57 | 3.52 | 0.70 |
| M15 | 11 spread/slippage (positive before costs) | 508 | -11.91 | -0.02 | 12.15 | 0.10 |
| D1 | 01 bad entry (never reached 0.25R) | 8 | -204.96 | -25.62 | 8.52 | 64.40 |
| D1 | 05 trailing/protection too tight | 8 | -41.68 | -5.21 | 162.58 | 13.10 |
| D1 | 03 whipsaw (MA18 exit within 3 bars) | 2 | -32.51 | -16.26 | 2.41 | 10.20 |
| D1 | 06 trailing/protection too loose (gave back >60% of >=1R) | 2 | -15.63 | -7.82 | 98.62 | 4.90 |
| D1 | 12 other | 5 | -13.03 | -2.61 | 33.56 | 4.10 |
| D1 | 02 correct entry, market reversal | 3 | -10.42 | -3.47 | 56.29 | 3.30 |
| D1 | 11 spread/slippage (positive before costs) | 10 | -0.00 | -0.00 | 17.33 | 0.00 |
| D1_23y | 01 bad entry (never reached 0.25R) | 51 | -1014.45 | -19.89 | 5.25 | 54.60 |
| D1_23y | 03 whipsaw (MA18 exit within 3 bars) | 14 | -341.75 | -24.41 | 2.51 | 18.40 |
| D1_23y | 05 trailing/protection too tight | 42 | -162.19 | -3.86 | 45.02 | 8.70 |
| D1_23y | 06 trailing/protection too loose (gave back >60% of >=1R) | 13 | -121.52 | -9.35 | 46.40 | 6.50 |
| D1_23y | 12 other | 25 | -109.35 | -4.37 | 22.50 | 5.90 |
| D1_23y | 02 correct entry, market reversal | 11 | -55.18 | -5.02 | 38.46 | 3.00 |
| D1_23y | 09 news/volatility event | 4 | -53.17 | -13.29 | 25.21 | 2.90 |
| D1_23y | 11 spread/slippage (positive before costs) | 18 | -0.00 | -0.00 | 12.97 | 0.00 |

## 11. Lower-timeframe noise study (M1 / M5 / M15)

**M1 is destroyed by microstructure costs, not by a lack of signal.** Before spread and slippage the 54,900 M1 trades sum to +$877 over six years (a coin flip: $0.02 per trade); the spread then costs $19,973 and slippage $10,980. The median XM spread is 56% of the median M1 ATR and 75% of the median M1 trade's best unrealized profit, 47% of M1 trades never reach a profit equal to one spread, 78% of them end on the MA18 exit (61% of all trades are losing MA18 exits, i.e. the exit fires one bar late and pays the spread again), and the median hold is 8 minutes. No trailing distance (200-1,200 points) or activation level (0-1,000 points) helps: the best M1 trailing setting still loses $26,811. Time exits make M1 worse at every horizon. The only lever that moves M1 is the volatility filter, and only because it removes trades: at ATR ratio >= 2.0 it leaves 1,225 trades and -$294. M1 fails. **M5** has the same structure with lower cost drag (spread 23% of ATR, gross +$2,102 versus $6,959 of costs): trailing sweeps, time exits and volatility thresholds below 2.0 are all negative; ATR ratio >= 2.0 keeps 463 trades and +$113 (PF 1.10), too few to mean anything. M5 fails. **M15** is the balance point the brief asked about: spread is 12.6% of ATR, gross before costs +$1,788 against $2,772 of costs, median hold 90 minutes, 55% MA18 exits. It is the only lower timeframe where single changes reach zero or slightly above (volatility >= 1.0 or 1.2: +$178 / +$174, PF 1.03-1.05; wide 1,200-point trailing: -$352 but +$935 in OOS), but every such variant is negative in the 2020-2023 development window and its out-of-sample gain comes from the 2025-2026 regime, in which the 15-minute ATR tripled. Whipsaws are not the issue (consecutive opposite signals within five bars are under 1% on all three timeframes); same-direction re-entries within five bars after a loss are 16-27% and lose again. Answer to section 15: M15 offers the best signal-to-cost ratio of the three, but 'better' means break-even, not profitable, and it is not statistically distinguishable from zero in any split.

| item | M1 | M5 | M15 |
|---|---:|---:|---:|
| trades | 54900 | 12320 | 4559 |
| median_atr_usd | 0.60 | 1.47 | 2.69 |
| median_spread_usd | 0.34 | 0.34 | 0.34 |
| spread_pct_of_atr | 56.00 | 23.10 | 12.60 |
| median_mfe_usd | 0.45 | 1.78 | 4.16 |
| spread_pct_of_median_mfe | 75.10 | 19.00 | 8.10 |
| median_risk_usd | 2.10 | 4.36 | 8.17 |
| median_hold_min | 8.00 | 38.00 | 90.00 |
| share_held_le_2_bars | 0.12 | 0.10 | 0.15 |
| share_MA18_exit | 0.78 | 0.71 | 0.55 |
| share_MA18_exit_losing | 0.60 | 0.55 | 0.42 |
| share_never_in_profit_ge_spread | 0.47 | 0.26 | 0.15 |
| share_next_trade_opposite_within_5_bars | 0.00 | 0.00 | 0.00 |
| gross_before_spread_and_slippage | 877.09 | 2102.47 | 1787.69 |
| spread_paid | 19973.31 | 4495.08 | 1678.09 |
| slippage_paid | 10980.00 | 2464.00 | 911.80 |
| swap_paid | -136.13 | -120.80 | -181.68 |

M1 trailing sweep (20 settings): best 200/0 -> net -26810.66, PF 0.651, exp R -0.301, OOS net -6730.03; time exits: 3b -45194.72, 5b -38434.13, 10b -32419.62, 20b -30289.91; volatility filter: >=0.8 -24267.05 (OOS -8067.89), >=1.0 -14163.71 (OOS -3650.1), >=1.2 -6907.95 (OOS -1168.91), >=1.5 -2044.45 (OOS -100.58), >=2.0 -293.77 (OOS -95.39).

M5 trailing sweep (20 settings): best 200/0 -> net -4015.48, PF 0.873, exp R -0.131, OOS net 907.13; time exits: 3b -7793.35, 5b -6409.18, 10b -5404.11, 20b -4981.08; volatility filter: >=0.8 -3392.86 (OOS -404.53), >=1.0 -2305.0 (OOS 93.2), >=1.2 -1758.51 (OOS -331.72), >=1.5 -710.76 (OOS -5.41), >=2.0 113.13 (OOS 175.61).

M15 trailing sweep (20 settings): best 500/0 -> net -669.47, PF 0.956, exp R -0.048, OOS net 483.19; time exits: 3b -1917.07, 5b -1333.46, 10b -908.45, 20b -994.59; volatility filter: >=0.8 -312.37 (OOS 774.5), >=1.0 178.36 (OOS 464.83), >=1.2 173.86 (OOS 342.66), >=1.5 5.49 (OOS 19.64), >=2.0 135.18 (OOS 81.38).

## 12. Walk-forward, robustness and overfitting audit

**Walk-forward.** Three yearly folds (2 y train, 1 y validate, 1 y test) over a declared grid of 5 filters x 3 stops x 8 exits, every configuration run once and sliced, selection by train expectancy/R gated by validation expectancy/R > 0. M1: no configuration passes validation in any fold; the train-best is negative in every test year. M5: the same; 64% of configurations are positive in the 2025-26 out-of-sample slice and 0% in development or validation. M15: the train-best fails validation in folds 1 and 3; the validation-gated pick lost -$276 in the 2024-25 test year (the untouched EA -$212) and made +$525 in 2025-26 (EA +$449); 0 of 120 configurations are positive in all three splits although 91% are positive out of sample, a regime artifact. D1: the selection beat the untouched EA in two of three test years (+$141 vs -$32, +$792 vs +$479) and lost in one (-$58 vs +$138); the train-best failed validation in two folds, which is the usual sign that in-sample ranking is unreliable even where the strategy has something. 19 of 96 D1 configurations are positive in all three splits, all of them combinations of ADX >= 25 and/or volatility-scaled protection. **Sensitivity of the D1 candidate.** Chandelier lookback 11-33 and multiplier 2.25-4.5 form a stable region ($1,230-$1,677, expectancy 0.18-0.24 R); ADX threshold 20-30 and slow MA 150-250 are stable; two cliffs exist: fast MA 20 or 22 loses 40% of the result ($950) and a break-even trigger of 300-400 points loses 40% ($900). The initial stop (swing, ATR 3x, swing strength 3) changes nothing because the Chandelier takes over on day one. **Monte Carlo.** At $200 with the candidate's 2020-2026 trade list the ruin probability is 0-0.2% and the 95th-percentile drawdown $105; with the 23-year trade list it is 27% (Chandelier) and 19% (ATR trail), because 2003-2020 is a 17-year flat stretch with runs of 16 consecutive losses. At the balance the EA's own 1% rule implies (~$8,700) the ruin probability is 0 in both cases. **Overfitting audit.** 456 grid configurations plus the 300+ single-variable runs of phases 1-4 were tested; on M15 the best in-sample configuration (volatility + ADX, swing 3, trailing + BE) has out-of-sample expectancy -0.014 R, and on M1/M5 the best in-sample configurations are the least bad in every split, not good in any. Only D1 shows configurations that are positive in all three windows, and their development-window sample is 21-34 trades.

### M1

| fold | train | test | configs | train-best | train R | val R | test R | passes val | selected | sel test R | sel test net $ | EA test net $ | share configs positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.24 | -0.25 | -0.22 | False | none passes |  |  | -4183.03 | 0.00 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.26 | -0.22 | -0.15 | False | none passes |  |  | -5495.54 | 0.00 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.24 | -0.15 | -0.05 | False | none passes |  |  | -6374.91 | 0.00 |

Overfitting audit: 120 configurations; positive in DEV, VAL and OOS: 0; share positive DEV 0.0, VAL 0.0, OOS 0.0. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE', 'dev_expR': -0.245, 'dev_pf': 0.424, 'val_expR': -0.211, 'oos_expR': -0.085, 'oos_net': -2761.64, 'oos_pf': 0.82}.

No robust candidate. Monte Carlo of the untouched EA at $200: p(ruin) 1.0 (shuffle) / 1.0 (bootstrap).

### M5

| fold | train | test | configs | train-best | train R | val R | test R | passes val | selected | sel test R | sel test net $ | EA test net $ | share configs positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | -0.12 | -0.10 | -0.12 | False | none passes |  |  | -923.22 | 0.00 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | 120 | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | -0.10 | -0.12 | -0.05 | False | none passes |  |  | -648.13 | 0.00 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | 120 | NY 13-22 | swing3 | E09 ATRtrail2+BE | -0.10 | -0.05 | -0.02 | False | none passes |  |  | -17.31 | 0.87 |

Overfitting audit: 120 configurations; positive in DEV, VAL and OOS: 0; share positive DEV 0.0, VAL 0.0, OOS 0.642. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA', 'dev_expR': -0.112, 'dev_pf': 0.709, 'val_expR': -0.099, 'oos_expR': -0.021, 'oos_net': 51.96, 'oos_pf': 1.009}.

No robust candidate. Monte Carlo of the untouched EA at $200: p(ruin) 1.0 (shuffle) / 1.0 (bootstrap).

### M15

| fold | train | test | configs | train-best | train R | val R | test R | passes val | selected | sel test R | sel test net $ | EA test net $ | share configs positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E04 Trail+BE | 0.01 | -0.06 | 0.00 | False | none passes |  |  | -139.14 | 0.33 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | 120 | vol>=1 | swing3 | E13 TWK | -0.02 | -0.01 | -0.05 | False | vol>=1+ADX>=25 | swing3 | E13 TWK | -0.05 | -275.50 | -212.38 | 0.15 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | 120 | vol>=1+ADX>=25 | ATR3 | E00 SL+MA18 | 0.01 | -0.05 | 0.11 | False | none | swing3 | E16 Chand+BE noMA | 0.02 | 524.77 | 448.95 | 0.94 |

Overfitting audit: 120 configurations; positive in DEV, VAL and OOS: 0; share positive DEV 0.0, VAL 0.283, OOS 0.908. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E04 Trail+BE', 'dev_expR': -0.01, 'dev_pf': 0.874, 'val_expR': -0.006, 'oos_expR': -0.014, 'oos_net': 247.37, 'oos_pf': 1.082}.

No robust candidate. Monte Carlo of the untouched EA at $200: p(ruin) 1.0 (shuffle) / 0.963 (bootstrap).

### D1

| fold | train | test | configs | train-best | train R | val R | test R | passes val | selected | sel test R | sel test net $ | EA test net $ | share configs positive in test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2023-09..2024-09 | 96 | ADX>=25 | ATR3 | E09 ATRtrail2+BE | 0.17 | -0.05 | 0.25 | False | ADX>=25 | swing | E03 Chand+BE | 0.18 | 140.60 | -32.36 | 0.74 |
| 2 | 2021-09..2023-09 | 2024-09..2025-09 | 96 | none | ATR3 | E00 SL+MA18 | 0.07 | -0.12 | -0.00 | False | none | swing | E00 SL+MA18 | 0.01 | -58.27 | 138.02 | 0.60 |
| 3 | 2022-09..2024-09 | 2025-09..2026-09 | 96 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | 0.12 | 0.16 | 0.22 | True | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | 0.22 | 792.32 | 479.47 | 0.75 |

Overfitting audit: 96 configurations; positive in DEV, VAL and OOS: 19; share positive DEV 0.302, VAL 0.604, OOS 0.792. Best in-sample: {'config': 'none | ATR3 | E20 R-BE1R+swing1R', 'dev_expR': 0.052, 'dev_pf': 0.81, 'val_expR': -0.061, 'oos_expR': 0.302, 'oos_net': 219.36, 'oos_pf': 1.39}.

Configurations positive in all three splits (top by OOS expectancy/R):

| config | DEV R | VAL R | OOS R | OOS net $ | OOS PF | all net $ | all PF | all DD $ | trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ADX>=25 | ATR3 | E03 Chand+BE | 0.05 | 0.09 | 0.47 | 1407.66 | 86.31 | 1574.52 | 11.75 | 64.67 | 62 |
| ADX>=25 | swing | E03 Chand+BE | 0.04 | 0.08 | 0.45 | 1407.66 | 86.31 | 1574.52 | 11.75 | 64.67 | 62 |
| ADX>=25 | ATR3 | E16 Chand+BE noMA | 0.01 | 0.15 | 0.45 | 1371.72 | 84.14 | 1550.76 | 11.27 | 73.43 | 59 |
| ADX>=25 | swing | E09 ATRtrail2+BE | 0.04 | 0.15 | 0.43 | 1528.47 | 10.20 | 1818.19 | 5.98 | 154.85 | 70 |
| ADX>=25 | ATR3 | E09 ATRtrail2+BE | 0.04 | 0.17 | 0.43 | 1528.47 | 10.20 | 1818.19 | 5.98 | 154.85 | 70 |
| ADX>=25 | swing | E16 Chand+BE noMA | 0.01 | 0.13 | 0.40 | 1371.72 | 84.14 | 1550.76 | 11.27 | 73.43 | 59 |
| none | swing | E09 ATRtrail2+BE | -0.01 | 0.10 | 0.34 | 1529.33 | 10.25 | 1735.82 | 4.35 | 154.85 | 93 |
| none | ATR3 | E09 ATRtrail2+BE | 0.01 | 0.10 | 0.33 | 1529.33 | 10.25 | 1729.60 | 4.30 | 154.85 | 93 |
| ADX>=25 | swing3 | E03 Chand+BE | 0.03 | 0.02 | 0.32 | 1407.66 | 86.31 | 1574.52 | 11.75 | 64.67 | 62 |
| ADX>=25 | swing3 | E16 Chand+BE noMA | 0.01 | 0.05 | 0.31 | 1371.72 | 84.14 | 1550.76 | 11.27 | 73.43 | 59 |

Sensitivity around `ADX>=25 | ATR3 | E03 Chand+BE` (value: all-period exp R (net $) | OOS exp R):

- atr_mult: 1.5: 0.08 (973.59) | 0.154, 2.25: 0.235 (1630.38) | 0.479, 3.0: 0.21 (1574.52) | 0.469, 3.75: 0.184 (1351.61) | 0.41, 4.5: 0.176 (1230.47) | 0.365
- chand_lookback: 11: 0.212 (1592.73) | 0.469, 16: 0.214 (1602.67) | 0.469, 22: 0.21 (1574.52) | 0.469, 28: 0.231 (1677.08) | 0.471, 33: 0.225 (1521.4) | 0.448
- be_trigger_pts: 300: 0.114 (917.52) | 0.323, 400: 0.127 (900.37) | 0.335, 500: 0.21 (1574.52) | 0.469, 600: 0.203 (1521.33) | 0.469, 700: 0.234 (1552.16) | 0.467
- sl_atr_mult: 2.25: 0.271 (1578.84) | 0.595, 2.625: 0.234 (1574.52) | 0.519, 3.0: 0.21 (1574.52) | 0.469, 3.375: 0.193 (1574.52) | 0.43, 3.75: 0.179 (1574.52) | 0.399
- adx_min: 20: 0.151 (1491.1) | 0.383, 22.5: 0.19 (1540.29) | 0.398, 25: 0.21 (1574.52) | 0.469, 27.5: 0.203 (1519.59) | 0.545, 30: 0.229 (1563.38) | 0.577
- fast: 14: 0.19 (1544.19) | 0.439, 16: 0.216 (1603.94) | 0.439, 18: 0.21 (1574.52) | 0.469, 20: 0.153 (948.5) | 0.289, 22: 0.145 (909.81) | 0.281
- trend: 150: 0.2 (1546.16) | 0.413, 175: 0.216 (1576.92) | 0.43, 200: 0.21 (1574.52) | 0.469, 225: 0.204 (1529.15) | 0.491, 250: 0.241 (1574.68) | 0.607

Monte Carlo at $200 (shuffle / bootstrap): p(ruin) 0.0 / 0.0016, DD p95 $104.62, ending balance p05 / median / p95 $471.19 / $1691.33 / $3354.19; at 100x median risk ($8674): p(ruin) 0.0, DD p95 $104.62.

## 13. $200 account analysis

**Strategy performance and account survivability are different questions, and a $200 account fails both on M1-M15 and fails the second on D1.** The minimum lot (0.01 = 1 oz) makes the median swing stop 1.0% of $200 on M1, 2.2% on M5, 4.1% on M15 and 46% on D1; the EA's own 1% rule therefore requires roughly $210 (M1), $440 (M5), $820 (M15) and $9,200 (D1) for the median trade and $22,500 for the 90th-percentile D1 trade. Margin ($4.29 per 0.01 lot at 1:1000) and the 20% stop-out are irrelevant: the account is lost to ordinary stops long before either binds. Monte Carlo on the six-year trade lists at $200 gives a 100% ruin probability on M1, M5 and M15 (the historical sequence ruins the account within 1-8 months) and 2-8% on D1, where a single loss of $112 (56% of the account) is possible on any trade. Swap is material on D1 (30% of gross) because trades last days and long swap is -$0.87 per night per 0.01 lot.

| TF | trades | median risk $ | p90 risk $ | max risk $ | median risk % of $200 | share > 1% | min account (1% rule, median trade) | (p90 trade) | worst loss $ | max consec losses | worst streak $ | MC p(ruin) shuffle | bootstrap | historical first ruin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 54900 | 2.10 | 6.80 | 111.84 | 1.00 | 0.53 | $210 | $680 | -42.94 | 45 | -128.19 | 1.00 | 1.00 | 2020-09-11 |
| M5 | 12320 | 4.36 | 15.97 | 196.60 | 2.20 | 0.86 | $436 | $1597 | -74.38 | 38 | -177.22 | 1.00 | 1.00 | 2020-10-05 |
| M15 | 4559 | 8.17 | 29.44 | 380.85 | 4.10 | 0.98 | $817 | $2944 | -79.84 | 51 | -281.21 | 1.00 | 0.96 | 2021-04-14 |
| D1 | 85 | 91.96 | 224.87 | 424.90 | 46.00 | 1.00 | $9196 | $22487 | -111.65 | 8 | -111.65 | 0.02 | 0.08 | never |

Broker constraints: min lot 0.01 = 1 oz; margin per 0.01 lot $4.29 at 1:1000; stop-out at 20% margin level (equity below ~$0.90); swap long $-0.868/night, short +$0.198/night per 0.01 lot. Margin call and stop-out never bind before the account is lost to ordinary stops.

## 14. Final comparison table (section 25)

EA columns = the untouched EA (strategy view, 0.01 lot, realistic costs, Sep 2020 - Sep 2026). Candidate columns = the best configuration that was positive in DEV, VAL and OOS in the walk-forward grid; 'none identified' where no configuration met that bar.

| Metric | M1 EA | M5 EA | M15 EA | D1 EA | M1 candidate | M5 candidate | M15 candidate | D1 candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Total trades | 54900 | 12320 | 4559 | 85 | - | - | - | 62 |
| Win rate % | 20.60 | 25.80 | 32.90 | 49.40 | - | - | - | 46.80 |
| Profit factor | 0.55 | 0.79 | 0.92 | 2.95 | - | - | - | 11.75 |
| Net profit $ (0.01 lot) | -30212.35 | -4977.42 | -983.88 | 619.14 | - | - | - | 1574.52 |
| CAGR % (from $200) | ruin | ruin | ruin | 26.20 | - | - | - | 43.30 |
| Max drawdown $ | 30239.03 | 5314.60 | 1581.42 | 179.40 | - | - | - | 64.67 |
| Expectancy $ | -0.55 | -0.40 | -0.22 | 7.28 | - | - | - | 25.40 |
| Expectancy R | -0.33 | -0.15 | -0.07 | 0.07 | - | - | - | 0.21 |
| Avg winner $ | 3.28 | 6.00 | 7.34 | 22.32 | - | - | - | 59.35 |
| Avg loser $ | -1.55 | -2.68 | -4.16 | -8.37 | - | - | - | -5.05 |
| Max losing streak | 45 | 38 | 51 | 8 | - | - | - | 5 |
| Profit giveback avg $ | 2.57 | 5.21 | 8.25 | 50.80 | - | - | - | 46.46 |
| Profitable->loss (>$2) | 4608 | 2588 | 1275 | 37 | - | - | - | 28 |
| Avg holding min | 17.00 | 65.00 | 178.10 | 7381.40 | - | - | - | 8450.70 |
| Robustness | negative in every split, every fold | negative in every split | negative DEV and VAL, ~0 OOS | one year (2025) carries 23 years; 8 of 23 years positive | none identified | none identified | none identified (91% of grid positive only in the 2025-26 slice) | positive DEV/VAL/OOS (21/13/28 trades); flat 2003-2020; stable Chandelier params, cliffs at fast MA >= 20 and BE trigger <= 400 |
| Candidate config | untouched | untouched | untouched | untouched | none identified | none identified | none identified | ADX>=25 | ATR3 | E03 Chand+BE |

## 15. Final candidate configurations

**M1: no statistically robust configuration identified.** Every tested entry, stop, exit and filter loses after costs in every split; gross edge is zero and the spread is 56% of ATR. **M5: no statistically robust configuration identified.** **M15: no statistically robust configuration identified.** The nearest misses are the volatility filter (ATR / 100-bar ATR >= 1.0: +$178, PF 1.03) and pure Chandelier without break-even or MA18 exit (+$717, PF 1.05); both are negative in 2020-2023 and their profit is the 2025-26 rally. They are documented, not recommended.

**D1: best available configuration, regime-dependent (not a proven edge).**
- Entry rules: unchanged (18/200 SMA, two closes above/below both, volume > 20-bar average, stop order at high/low +/- 10 points, pending cancelled on a close through the 18 SMA, pending SL ratcheted).
- Filters: `UseADXFilter = true`, `ADXPeriod = 14`, `MinimumADX = 25` (20-30 all acceptable), `RequireRisingADX = false`; session filter off; `UseSLPercentFilter = true` with `MaximumSLPercent = 1.0` **kept**.
- Stop: swing low/high (strength 2) unchanged; irrelevant in practice because the Chandelier overrides it on the first tick.
- Protection: `ProtectionMode = PROTECTION_CHANDELIER`, `ProtectionStartMode = START_IMMEDIATELY`, `ChandelierLookback = 22`, `ATRPeriod = 22`, `ATRMultiplier = 3.0` (stable 2.25-4.5). Alternative with equal or better 23-year behaviour: ATR trailing 2 x ATR(22) from the first tick (not in v1.00; needs the code in section 17).
- Break-even: `EnableBreakEven = true`, `BreakEvenTriggerPoints = 500`, `BreakEvenOffsetPoints = 10` (do not lower the trigger).
- Exit: MA18 close exit kept. Risk filter off. Time exit none.
- Risk: `LotSize = 0.01`; median stop $87 per 0.01 lot, so the EA's 1% rule needs about $8,700 of balance to trade at all.
- Evidence: 2020-2026 62 trades, +$1,575, PF 11.7, win 47%, max DD $65, expectancy 0.21 R; DEV +$64 (21 trades), VAL +$102 (13), OOS +$1,408 (28). 2003-2026 (H1 path): 241 trades, +$1,378, PF 1.95, 10 of 23 years positive, 2003-2012 -$113, 2012-2020 -$53, 2020-2026 +$1,544; ATR-trail variant 274 trades, +$1,808, PF 2.07, 13 of 23 years positive, 2003-2012 +$40, 2012-2020 -$1. The candidate is therefore a consistent improvement on the shipped exit and a coin flip outside the 2020-2026 regime.

D1 candidate and its neighbours over 2003-2026 (H1 path, realistic costs; window cells = net $ / expectancy R / trades):

| config | trades | net $ | PF | maxDD $ | exp R | win % | positive years | net ex-2025 $ | 2003-2012 | 2012-2020 | 2020-2026 | MC p(ruin) at $200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EA v1.00 (swing after 500 + BE + MA18) | 329 | 121.32 | 1.06 | 545.02 | -0.04 | 42.60 | 8/23 | -517.59 | -191.67 / -0.162 / 112 | -218.52 / -0.018 / 122 | 531.51 / 0.06 / 95 | 0.67 |
| Candidate: ADX>=25 + Chandelier(22,3) immediate + BE + MA18 | 241 | 1377.61 | 1.95 | 383.17 | 0.03 | 40.20 | 10/23 | 549.94 | -113.46 / -0.115 / 87 | -52.51 / 0.042 / 88 | 1543.58 / 0.187 / 66 | 0.27 |
| Chandelier immediate + BE + MA18 (no ADX) | 336 | 1113.15 | 1.56 | 430.26 | -0.01 | 42.00 | 9/23 | 284.61 | -36.18 / -0.117 / 109 | -249.17 / -0.016 / 130 | 1398.5 / 0.107 / 97 | 0.44 |
| ADX>=25 + ATR trail 2x immediate + BE + MA18 | 274 | 1807.96 | 2.07 | 240.08 | 0.07 | 45.60 | 13/23 | 1005.62 | 39.96 / -0.021 / 100 | -0.75 / 0.064 / 100 | 1768.75 / 0.199 / 74 | 0.19 |
| ADX>=25 + EA exits | 237 | 440.46 | 1.34 | 376.93 | -0.01 | 40.90 | 10/23 | -197.58 | -209.61 / -0.157 / 85 | -46.68 / 0.037 / 83 | 696.75 / 0.117 / 69 | 0.40 |

## 16. Failed experiments

Everything below the line was tested and rejected. Lower-timeframe filters, stops and exits that reduced the loss were kept in the record but none produced a configuration that is positive in the development, validation and out-of-sample windows, which is the acceptance rule declared before any run.

387 of 489 logged runs ended negative or classified Harmful. Rejected configurations by phase: P4-exits: 95, P1-filters: 87, P3-stoploss: 73, P13-ltf-trailing: 60, P0-baseline: 34, P13-ltf-timeexit: 12, P2-filter-combos: 12, P13-ltf-volfilter: 10, P16-D1-validation: 4. Full list with parameters and reasons: `results/experiment_log.csv` (columns conclusion / oos_result).

## 17. Recommended EA changes (only what the tests support)

Ordered by strength of evidence. Only D1 is concerned; nothing supports trading M1, M5 or M15 with this EA.

1. **Protection: replace swing-after-500 with Chandelier from the first tick.** Set `ProtectionMode = PROTECTION_CHANDELIER`, `ProtectionStartMode = START_IMMEDIATELY`, keep `ChandelierLookback = 22`, `ATRPeriod = 22`, `ATRMultiplier = 3.0`. No code change. Evidence: 2020-2026 +$619 -> +$1,435 (PF 2.9 -> 5.1, max DD $179 -> $119); 2003-2026 +$121 -> +$1,113; better than the shipped exit in each of the three 8-year windows; stable for lookback 11-33 and multiplier 2.25-4.5.
2. **Add an ATR-trailing protection mode** (`PROTECTION_ATR_TRAIL`: SL = best bid/ask since entry -/+ `ATRTrailMult` x ATR(`ATRPeriod`), tighten-only, updated every tick like `ManageTrailingProtection`, default multiplier 2.0). Evidence: 2020-2026 +$1,736 (PF 4.3); 2003-2026 +$1,530 with 10 of 23 years positive and, with ADX >= 25, +$1,808 with 13 of 23 (the most regime-robust exit tested). Requires ~40 lines in the protection switch; the engine implementation is `protection & 8` in `sma18_engine.py`.
3. **Enable the ADX filter on D1:** `UseADXFilter = true`, `MinimumADX = 25`. Evidence: with Chandelier, +$1,435 -> +$1,575 with DD $119 -> $65 and positive DEV/VAL/OOS; with the shipped exit +$619 -> +$759 (PF 2.9 -> 6.9); 2003-2026 with Chandelier +$1,113 -> +$1,378. Weak sample (21-28 development trades): treat as supported but not proven.
4. **Do not lower `BreakEvenTriggerPoints` below 500 and do not switch break-even off** on D1: 300/400 points cut the candidate's result by 40%; removing break-even entirely gave +$1,095 (2020-26) and +$720 (2003-26) versus +$1,435 / +$1,113 with it.
5. **Do not use `PROTECTION_TRAILING` with 500-point distances on D1**, and do not port the previous strategy's TWK trail: -$74 and -$15 over 2020-2026 against +$619 for the shipped exit; 500 points is a fraction of a 2024-2026 daily range.
6. **Keep `UseSLPercentFilter = true` and make the balance requirement explicit.** The filter is doing its job: at 0.01 lot the median D1 stop is $87, so the EA needs about $8,700 to risk 1%. Add a startup check that prints the minimum balance implied by the last 100 bars' median swing distance and refuses to trade below it, instead of silently blocking every setup (which is what happened on $200: 370 setups, zero trades, no message beyond the per-setup print). Position sizing by risk % cannot help a $200 account because the minimum lot is already too large.
7. **Do not add any of the tested entry filters on D1** (volume off, MA200 off, 1- or 3-bar confirmation, pending expiry, buffers, volatility, slope, distance): none is helpful by the declared rule on 85 trades.
8. **Do not change the initial stop.** ATR, capped, clamped, MA-based and buffered stops were all neutral or harmful; the v13-style 1,500-point cap looks good only in 2025.
9. **Fixed-point thresholds should eventually be ATR-scaled** (v13's `UseATRScaledLevels` idea): the ATR-scaled break-even (1 ATR) with 2/1-ATR trailing was the only exit positive in all three D1 splits (+0.15 / +0.31 / +0.30 R) and had 13 of 23 positive years, but on 54-226 trades; test it forward before adopting.
10. **Housekeeping (no performance claim):** `ManageFailedBreakoutExit()` and the partial-close inputs are dead code; `PassSLPercentFilter` is called twice per order; buy stops placed inside the spread fail with an MT5 'invalid price' error (5 times in six years on D1, ~40% of setups on M1) and could add the spread to the buy entry as v13 does.

**Explicitly not recommended:** any deployment on M1/M5/M15; the New York-session + volatility + ADX stack on M5 (-$128 over six years, positive only in 2025-26); the volatility filter on M15 (fails the declared rule); any hybrid that combines more than the components above (section 23: nothing else was validated).

## 18. Backtest methodology

Engine: an exact Python/numba port of the MQL5 logic (`sma18_engine.py`), simulated bar by bar on M1 bars (H1 bars before Sep 2020 for the D1 long history) in XM server time. Entries and the MA18 exit run on the first path bar of each signal bar with the two completed bars, as in `OnTick`; break-even, protection, trailing and stop hits are evaluated on every M1 bar using the bar's extreme as the best price, a stop is tested against the bar's extreme, and a stop moved inside a bar is tested against the close (and against the extreme when the bar closes against the trade). MT5 order validity is modelled: a buy stop must be above the ask, a sell stop below the bid, and a stop-loss modification must be on the correct side of the market; invalid requests fail and are retried like the real EA. Costs: XM GOLD spread by year and server hour scaled to M1-equivalent (25 to 51 points), 10-point adverse slippage on every execution, XM swap (-86.84 / +19.79 points per night, triple Wednesday), no commission; stress = 1.5x spread and 30-point slippage; low = 25-point spread, no slippage, no swap. Money: 0.01 lot = 1 oz, so all $ figures are per 0.01 lot and directly comparable with a $200 account. Data: Dukascopy bid candles, so prices, volume (traded, not tick count) and fill timing differ from XM's tester; the two feeds' closes differ by cents and their volume filters agree on 82% of bars. Validation of the intrabar assumption: the D1 result on the M1 path (+$619) versus the H1 path (+$532) over the same six years, and 'path' versus 'worst' ordering (+$619 versus +$610 on D1, -$984 versus -$2,716 on M15), bound the resolution error. Splits declared before any run: DEV Sep 2020 - Aug 2023, VAL Sep 2023 - Dec 2024, OOS Jan 2025 - Sep 2026; walk-forward folds 2y train / 1y validate / 1y test rolled yearly; acceptance = better expectancy/R and PF in all three splits with at least 30 trades each; every run logged in `results/experiment_log.csv`.
