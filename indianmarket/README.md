# indianmarket: SimpleSMA18Bot on NIFTY 50 and NIFTY BANK

Independent research project (27 Sep 2026): does the 18/200 SMA breakout strategy developed and tested on gold have a
cost-adjusted, statistically defensible edge on the Indian equity indices? Nothing here shares data or results with the gold
study; only the validated simulation core is reused (`strategy/engine_in.py`, see `strategy/original_strategy/STRATEGY_RULES.md`).

Start with `reports/INDIAN_MARKET_FINAL_REPORT.md`, then the per-index reports.

## Layout

```
indianmarket/
  data/            1-minute and daily data, official NSE daily cross-check, DATA_AUDIT.md, raw JSON per request
  strategy/        engine_in.py (rule port), costs.py (Indian futures cost model), common_in.py (splits, metrics, regimes, gates, log)
                   original_strategy/ (the EA source, its component map, STRATEGY_RULES.md)
  backtests/       run_baseline.py, baseline_metrics.json, <index>/<config>_<tf>_<scenario>_trades.csv.gz (every trade of every run)
  experiments/     run_cost_analysis.py; sessions/run_regime_session.py; timeframe/run_sweeps_wf.py; filters/run_variants.py (filters + MTF)
  research/        experiment_log.csv, timeframe_analysis.md, cost_analysis.md, regime_analysis.md, robustness_analysis.md,
                   walk_forward_analysis.md, variants_mtf_analysis.md
  reports/         NIFTY50_FINAL_REPORT.md, BANKNIFTY_FINAL_REPORT.md, INDIAN_MARKET_FINAL_REPORT.md, make_reports.py, narrative.json
  tools/           fetch_upstox.py (data download), engine patch scripts
```

## Reproduce

```
cd indianmarket
python tools/fetch_upstox.py                       # data (resumable; ~2 minutes)
python backtests/run_baseline.py                   # 120 runs + long D1 (~3 minutes)
python experiments/run_cost_analysis.py
python experiments/sessions/run_regime_session.py
python experiments/timeframe/run_sweeps_wf.py      # ~10 minutes
python experiments/filters/run_variants.py         # ~10 minutes
python reports/make_reports.py
```

Requires Python 3.11+, numpy, pandas, numba, requests. The engine caches the path arrays in `data/<index>/<index>_path.npz`.

## Conventions

* Money unit: index points per unit. One futures lot = 75 units (NIFTY 50) or 35 (NIFTY BANK); rupee columns use these multipliers
  and Rs 2,50,000 of capital per lot for percentages and drawdown ratios.
* Scenario A gross; B realistic (futures spread, slippage per side, STT, exchange, SEBI, stamp duty, brokerage, GST); C stress.
  All rates in `strategy/costs.py`.
* Splits fixed before any run: TRAIN 2022-01-03..2024-08-31, VAL 2024-09-01..2025-08-31, OOS 2025-09-01..2026-09-26.
  Verdict rule: robust = positive expectancy and PF > 1 after B costs in all three splits with at least 30 trades each.
* Timeframes: 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h (bars anchored at 09:15) and D1 (one bar per session), plus D1 on the
  official daily history 2010-2026.
* The volume filter of the original EA cannot be evaluated on an index (no volume) and is off in every run; this is the one
  forced deviation from the original rules.

## Findings (27 Sep 2026)

**No statistically defensible positive expectancy was found.** About 500 logged experiments: 120 baseline runs, 16 parameter
maps with walk-forward folds, 20 filter variants and 18 higher-timeframe gates per candidate timeframe.

* 1m to 10m: negative after costs on both indices in both configurations (charges alone are 7 points per round trip on
  NIFTY 50 and 16-17 on NIFTY BANK; the gross edge is smaller). D1: negative in 2022-2026 and in 2010-2026.
* 15m to 4h: positive after realistic costs with the ATR-scaled exits on both indices (NIFTY 50 PF 1.09-1.36, NIFTY BANK
  15m PF 1.15), eight runs pass the pre-set robust rule, but no t-statistic exceeds 1.45, every confidence interval of the
  expectancy includes zero, the top five trades carry the result, strong-bull sessions lose and Fridays earn most of it,
  walk-forward re-fitting loses to the fixed 18/200, and drawdowns are 50-100% of the Rs 2.5 lakh capital per lot.
* Best-behaved candidates for a paper forward test only: NIFTY 50 30m FINAL_H4 (+5,118 pts, 4 of 5 years) and NIFTY BANK
  15m FINAL_H4 (+15,190 pts, 4 of 5 years). Hypotheses for further research: entries 09:45-13:29 or skipping large-gap
  sessions on 30m, ADX >= 20 on 15m NIFTY BANK, the Friday effect, the bear/sideways regime dependence.

Details: `reports/INDIAN_MARKET_FINAL_REPORT.md`, `reports/NIFTY50_FINAL_REPORT.md`, `reports/BANKNIFTY_FINAL_REPORT.md`.
