# Forex majors, silver, bitcoin and oil: final report (SimpleSMA18Bot, Sep 2021 to Sep 2026)

Ten XM instruments, two configurations, ten timeframes and three cost scenarios give 184 scenario-B baseline runs (silver and oil could only be tested from 15 minutes up). 17 are positive after realistic costs and none passes the pre-set robust rule (positive expectancy and PF above 1 in TRAIN, VAL and OOS with 30+ trades each). Below one hour every instrument loses: XM's spread plus slippage takes 20-35% of the gross profit on the majors' 1-hour runs and the whole gross edge below that. The strongest single result is USDJPY on 2 hours with the ATR-scaled exits (606 trades, PF 1.29, t-statistic 2.2, +$289 per 0.01 lot), but it is negative in the out-of-sample year, re-optimising its moving averages loses to the fixed 18/200, and no filter improves it in all three splits. Silver's daily result (+$1,764 on 30 trades) is the 2025-26 silver rally arriving in the out-of-sample window after a negative training period; bitcoin's daily ATR result (+$487 on 54 trades) has a t-statistic of 1.3 and is nothing without its five best trades. GBPUSD, AUDUSD, USDCAD and NZDUSD are negative on all 20 runs each, and every major is negative on the 2015-2026 daily history. The strategy is a gold-regime result that does not transfer to low-volatility currency pairs.

## Comparison: best after-cost timeframe per instrument (scenario B, USD per 0.01 lot)

| instrument | best TF (config) | trades | PF | exp R | net $ | max DD $ | years > 0 | OOS $ | t-stat | top-5 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 4h (FINAL_H4) | 282 | 1.06 | 0.04 | 42.75 | 65.45 | 5/6 | 44.55 | 0.35 | 299.10 | unstable |
| GBPUSD | none positive |  |  |  |  |  |  |  |  |  | negative |
| USDJPY | 2h (FINAL_H4) | 606 | 1.29 | 0.08 | 289.08 | 65.98 | 5/6 | -14.49 | 2.17 | 40.60 | unstable |
| AUDUSD | none positive |  |  |  |  |  |  |  |  |  | negative |
| USDCAD | none positive |  |  |  |  |  |  |  |  |  | negative |
| USDCHF | none positive |  |  |  |  |  |  |  |  |  | negative |
| NZDUSD | none positive |  |  |  |  |  |  |  |  |  | negative |
| Silver (XAGUSD) | 4h (ASIS) | 221 | 1.25 | -0.03 | 849.03 | 894.43 | 2/6 | 1,558.00 | 0.70 | 263.30 | unstable |
| Bitcoin (BTCUSD) | D1 (FINAL_H4) | 54 | 1.61 | 0.11 | 487.37 | 187.89 | 4/6 | 311.80 | 1.27 | 112.00 | unstable |
| US Oil (WTI) | 4h (FINAL_H4) | 194 | 1.11 | 0.08 | 20.31 | 44.74 | 3/6 | 10.29 | 0.40 | 286.10 | unstable |

## Robust-rule count per instrument (of 20 baseline B runs each)

| instrument | robust | unstable | negative |
|---|---|---|---|
| EURUSD | 0 | 2 | 18 |
| GBPUSD | 0 | 0 | 20 |
| USDJPY | 0 | 7 | 13 |
| AUDUSD | 0 | 0 | 20 |
| USDCAD | 0 | 0 | 20 |
| USDCHF | 0 | 1 | 19 |
| NZDUSD | 0 | 0 | 20 |
| Silver (XAGUSD) | 0 | 2 | 10 |
| Bitcoin (BTCUSD) | 0 | 3 | 17 |
| US Oil (WTI) | 0 | 2 | 10 |

## Instrument characteristics

| metric | EURUSD | GBPUSD | USDJPY | AUDUSD | USDCAD | USDCHF | NZDUSD | Silver (XAGUSD) | Bitcoin (BTCUSD) | US Oil (WTI) |
|---|---|---|---|---|---|---|---|---|---|---|
| median daily range % | 0.623 | 0.665 | 0.761 | 0.883 | 0.511 | 0.694 | 0.909 | 2.636 | 3.403 | 3.098 |
| median ATR14 % | 0.668 | 0.698 | 0.862 | 0.935 | 0.552 | 0.721 | 0.951 | 2.667 | 3.654 | 3.287 |
| annualised vol % (median rv20) | 6.800 | 7.000 | 9.100 | 9.100 | 5.500 | 7.100 | 9.100 | 26.800 | 37.900 | 33.700 |
| daily autocorr lag1 | 0.001 | 0.026 | -0.001 | -0.039 | -0.026 | 0.004 | -0.007 | -0.015 | -0.024 | 0.021 |
| weekly return autocorr | 0.788 | 0.785 | 0.789 | 0.765 | 0.772 | 0.799 | 0.789 | 0.785 | 0.800 | 0.790 |
| variance ratio 5d | 0.950 | 0.950 | 0.950 | 0.870 | 0.890 | 0.980 | 0.950 | 0.950 | 1.010 | 0.970 |
| days breaking prev high % | 46.900 | 48.600 | 53.300 | 50.400 | 53.100 | 49.900 | 48.100 | 50.500 | 47.200 | 52.500 |
| follow-through % | 49.300 | 47.300 | 56.800 | 47.800 | 48.100 | 50.100 | 45.800 | 52.500 | 49.000 | 53.300 |
| days breaking prev low % | 49.500 | 47.600 | 40.400 | 47.500 | 48.700 | 46.000 | 50.900 | 45.500 | 43.900 | 45.300 |
| follow-through (down) % | 51.700 | 51.500 | 48.100 | 50.400 | 47.700 | 51.100 | 51.000 | 49.300 | 46.400 | 51.400 |
| trend days bull/side/bear | 449/304/563 | 490/349/477 | 833/204/279 | 462/394/460 | 617/339/360 | 457/308/551 | 348/391/577 | 614/311/384 | 814/321/672 | 427/370/512 |
| vol days low/normal/high/extreme | 397/577/300/42 | 488/604/155/69 | 171/642/436/67 | 310/639/267/100 | 458/571/241/46 | 220/757/276/63 | 258/608/363/87 | 85/728/397/99 | 579/986/228/14 | 303/648/287/71 |
| sessions | 1316 | 1316 | 1316 | 1316 | 1316 | 1316 | 1316 | 1309 | 1807 | 1309 |

## Answers

1. **Does the original strategy work on the forex majors?** No. AS-IS is negative after costs on every timeframe of GBPUSD, AUDUSD, USDCAD and NZDUSD, on 18 of 20 EURUSD and USDCHF runs, and positive only on USDJPY 1h-4h (PF 1.09-1.24) where the 2021-24 yen trend carried it.
2. **Silver, bitcoin, oil?** Silver: negative from 15m to 2h, positive only on 4h and D1 (2/6 years, all of it in the 2025-26 rally). Bitcoin: negative below D1 in both configurations (swap and spread), positive on D1 with the ATR exits (+$487, 54 trades) and on the 2018-26 daily history (5/8 years). Oil: flat everywhere (+$20 on 4h).
3. **Most stable timeframe:** 2h-4h for the majors that show anything, D1 for silver and bitcoin; everything below 1 hour is negative on all ten instruments. Nothing is stable across TRAIN, VAL and OOS.
4. **Costs:** spread and slippage per round trip are $0.4-0.6 per 0.01 lot on the majors, $3-6 on silver, $1 plus $0.35 of swap per night on bitcoin. That is 20-35% of the gross profit on 1h and more than the gross edge below it; on 4h-D1 it is 8-18%.
5. **Slippage:** the 1h-2h results are sensitive (USDJPY 2h loses a third of its net at 2x slippage); 4h-D1 are not.
6. **Years:** no configuration is positive in every year on any instrument. USDJPY 2h is positive in 5 of 6 (2021 Sep-Dec is the loser), bitcoin D1 in 4 of 6, silver D1 in 2 of 6.
7. **Regimes:** the pattern found on the indices repeats: strong-trend sessions in the direction of the breakout do not pay (bitcoin D1 loses in strong-bull sessions, silver's whole result is seven strong-bull trades); Asia-session entries lose on the majors; USDJPY's profit is all long trades during the yen decline.
8. **Out-of-sample (Sep 2025 - Sep 2026):** negative for USDJPY 2h (-$14), EURUSD 4h +$45 and bitcoin D1 +$312 are the only meaningful positives, and silver's +$1,465 is a single directional move.
9. **Parameter robustness:** USDJPY 2h is positive on TRAIN for all 60 MA cells but only 5 stay positive in VAL and OOS; bitcoin D1 24/60 and 3; EURUSD 4h 2/60. Walk-forward re-optimisation loses to the fixed 18/200 on every candidate but EURUSD 4h (+$48 vs +$47). Exit-parameter maps are broadly positive on TRAIN for USDJPY only.
10. **Setups for further research:** USDJPY 2h with the ATR exits restricted to London and New York hours (V04: PF 1.28, positive in all three splits but OOS only +$7) or with sideways regimes excluded (V12); EURUSD 4h without Monday-morning entries (V07, the only variant helpful in all splits on a major, +$88); the daily ATR configuration on bitcoin as a slow trend follower with a swap budget. None of these is a trading recommendation.
11. **Genuine or overfitting?** With 184 baseline runs, 160 parameter-map cells per candidate and 20 variants plus 18 higher-timeframe gates each, 17 positive runs and a handful of 'robust' variants are what noise produces. The only t-statistic above 2 (USDJPY 2h) fails out of sample and belongs to a one-directional yen trend. The evidence does not establish an edge on any of the ten instruments.
12. **Conditions:** better on 2h-D1, in the direction of a persistent macro trend (USDJPY 2021-24, silver and bitcoin 2025-26), outside the Asian session, with volume or ATR filters not helping; worse below 1 hour, in ranging pairs (GBPUSD, AUDUSD, USDCAD, NZDUSD), at the Monday open, and wherever the spread exceeds a few percent of the daily range.

## Method and reproducibility
- strategy/engine_fx.py (gold engine generalised), strategy/common_fx.py; data via tools/fetch_duka.js, tools/xm_pull2.py, tools/prep_data.py; runs via backtests/run_baseline.py and experiments/*.py; every run in research/experiment_log.csv, every trade list under backtests/.
