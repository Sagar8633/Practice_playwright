# Indian market final report: SimpleSMA18Bot on NIFTY 50 and NIFTY BANK (2022-2026)

**No statistically defensible positive expectancy was found.** Across 2 indices x 2 configurations x 10 timeframes x 3 cost scenarios (120 baseline runs), 16 parameter maps with walk-forward folds, 20 filter variants and 18 higher-timeframe gates on every candidate timeframe (about 500 logged experiments), the 18/200 SMA breakout strategy has no edge below 15 minutes and no edge on D1 in India. From 15 minutes to 4 hours the ATR-scaled exit stack is positive after realistic costs on both indices and passes the pre-set robust rule on six NIFTY 50 runs and two NIFTY BANK runs, but no run has a t-statistic above 1.45, every confidence interval of the expectancy includes zero, the profit is concentrated in the top five trades, in bear/sideways regimes and on Fridays, the walk-forward shows that re-fitting the parameters destroys value, and the drawdowns are 50-100% of the Rs 2.5 lakh capital per lot. The most stable behaviour is NIFTY 50 30m and NIFTY BANK 15m with the ATR-scaled exits; both are candidates for a paper forward test, neither is tradable on this evidence.

## Comparison

| metric | NIFTY 50 | NIFTY BANK |
|---|---|---|
| best stable timeframe (config) | 30m (FINAL_H4), verdict robust | 15m (FINAL_H4), verdict robust |
| total trades | 599 | 1125 |
| win rate % | 31.90 | 29.40 |
| profit factor (B) | 1.17 | 1.15 |
| expectancy pts / R | 8.544 / 0.0387 | 13.502 / 0.0056 |
| net R | 23.18 | 6.34 |
| net pts (B) | 5,118.00 | 15,190.20 |
| max DD pts (% of capital) | 2158.2 (64.7%) | 7129.5 (99.8%) |
| monthly Sharpe | 0.49 | 0.64 |
| cost impact: gross A -> net B pts | 9386.2 -> 5118.0 | 34635.8 -> 15190.2 |
| yearly consistency | 4/5 years positive | 4/5 years positive |
| out-of-sample (2025-09..2026-09) | net 1763.4 pts, PF 1.242, 132 trades | net 1967.3 pts, PF 1.071, 247 trades |
| top-5 trades share of net % | 70.10 | 66.20 |

## Why the two indices differ

| metric | NIFTY 50 | NIFTY BANK |
|---|---|---|
| median daily range % | 0.86 | 1.10 |
| median ATR14 % | 1.04 | 1.31 |
| median |gap| % | 0.27 | 0.30 |
| days |gap| > 0.5% | 23.20 | 28.60 |
| days |gap| > 1% | 6.10 | 9.10 |
| first 15 min share of day range % | 40.90 | 43.70 |
| daily return autocorr lag1 | -0.03 | -0.04 |
| weekly return autocorr | 0.79 | 0.79 |
| variance ratio 5d | 0.98 | 0.99 |
| days breaking prev high % | 52.90 | 53.60 |
| of which close above (follow-through) % | 57.30 | 56.10 |
| days breaking prev low % | 47.40 | 47.80 |
| of which close below % | 56.10 | 51.50 |
| trend regime days: bull/side/bear | 601/245/328 | 625/236/313 |
| vol regime days: low/normal/high/extreme | 363/566/192/53 | 441/562/138/33 |

NIFTY BANK moves 1.3x more per day (median range 1.10% vs 0.86%) and gaps more often (28.6% of sessions gap more than 0.5% vs 23.2%), so the same signal produces more points per trade; but its charges are 16-17 points per round trip against 7 for NIFTY 50 and its spread and slippage are three times higher, so the AS-IS rules, which scratch most trades at +0.5 point and rely on swing stops, are net-negative on NIFTY BANK and marginally positive on NIFTY 50. The ATR-scaled exits need no point mapping and let the winners run, which is why they are the only configuration positive on NIFTY BANK. Both indices show the same regime signature (breakouts fail in strong-bull sessions, work in sideways and weak-bear sessions), the same opening-phase losses, the same Monday losses and Friday gains, and near-zero daily autocorrelation with about 56% follow-through after a previous-day-high break: neither index trends intraday strongly enough for a breakout rule to pay its costs below 15 minutes.

## Answers to the twelve questions

1. **NIFTY 50:** not as written; weakly positive after costs on 15m-4h, not statistically defensible.
2. **NIFTY BANK:** not as written (negative on 9 of 10 timeframes); positive after costs on 15m/30m/1h only with the ATR-scaled exits, not statistically defensible.
3. **Most stable timeframe:** NIFTY 50 30m and NIFTY BANK 15m with the ATR-scaled exits (positive in TRAIN, VAL and OOS and in 4 of 5 years each). Anything below 15 minutes is dead on costs; D1 is negative.
4. **Costs:** about 7 (NIFTY) and 16-17 (BANKNIFTY) points of charges per round trip. 1m-10m gross edges are smaller than that; 15m survives realistic costs but not the stress scenario on NIFTY 50; 30m and above survive both.
5. **Slippage:** the 15m results die at 2-3 points (NIFTY) / 8 points (BANKNIFTY) per side; 30m-4h are tolerant.
6. **Years:** no configuration is positive in all five years; NIFTY 50 loses 2024, NIFTY BANK loses 2025 on the best timeframes.
7. **Regimes:** consistent and counter-intuitive on both indices: strong-bull sessions lose, sideways and weak-bear sessions earn; opening-phase entries lose; Fridays carry the result. Extreme-volatility sessions earn on NIFTY 50.
8. **Out-of-sample:** positive for the candidate runs (NIFTY 50 30m +1,763, NIFTY BANK 15m +1,967 pts), but the OOS year is a bear-to-sideways year, the regime the strategy favours.
9. **Parameter robustness:** broad positive TRAIN regions everywhere (trending TRAIN years), but only NIFTY 50 30m/1h keep most cells positive in VAL and OOS; walk-forward re-optimisation loses to the fixed 18/200 in most cases. One-off best cells (e.g. NIFTY 4h exits) collapse out of sample.
10. **Setups for further research:** NIFTY 50 30m ATR exits with entries 09:45-13:29 or with large-gap sessions skipped; NIFTY BANK 15m ATR exits with ADX >= 20 or short-only; the Friday effect and the regime dependence as separate research questions. All are hypotheses formed on the same data and must be confirmed forward.
11. **Genuine or overfitting?** The positive after-cost numbers are consistent with noise plus regime luck: t <= 1.45, outlier-driven, weekday- and regime-concentrated, unstable to re-fitting, and eight 'robust' flags out of 40 baseline runs are within chance. The evidence does not disprove an edge on 15m-4h with the ATR exits, but it does not establish one.
12. **Conditions:** better on 15m-4h with ATR-scaled exits, in sideways and weak-bear regimes, midday/closing entries, Fridays, after large gaps; worse below 15 minutes, on D1, in strong-bull regimes, opening-phase entries, Mondays, and whenever slippage exceeds 2-3 points on NIFTY 50.

## Method and reproducibility
- Engine: strategy/engine_in.py (the gold research engine with the market model swapped; exact v1.00 rule port), strategy/costs.py, strategy/common_in.py.
- Data: data/DATA_AUDIT.md.
- Runs: backtests/run_baseline.py, experiments/run_cost_analysis.py, experiments/sessions/run_regime_session.py, experiments/timeframe/run_sweeps_wf.py, experiments/filters/run_variants.py, reports/make_reports.py.
- Every run is logged in research/experiment_log.csv; every trade list is saved under backtests/.
