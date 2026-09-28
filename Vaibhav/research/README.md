# SimpleSMA18Bot GOLD research — index

Everything here reproduces the 36-section brief of 2026-09-26 on `../SimpleSMA18Bot.mq5` (v1.00) with a local engine instead of the MT5 tester.

## Deliverables

| # | Item | Where |
|---|---|---|
| 1 | Complete research report | `FINAL_REPORT.md` |
| 2 | Experiment log (every run: id, date, hypothesis, TF, parameters, filters, exit, trades, PF, net, DD, expectancy, OOS result, conclusion) | `results/experiment_log.csv` |
| 3 | Trade-level data (per trade: times, direction, prices, initial SL, lot, risk $, P&L $ and R, MFE/MAE $ and R, drawdown after MFE, exit mechanism, hold time, regime, session, spread, indicator state) | `results/trade_analysis/trade_level_{TF}.csv`, `results/baseline/trades_*.csv`, `results/research_tables.xlsx` |
| 4 | Final comparison tables (sections 25, 26, 12, 22) | `FINAL_REPORT.md` sections 8 and 14 |
| 5 | Best robust configurations / "none identified" | `FINAL_REPORT.md` section 15, `results/walkforward/summary.json` |
| 6 | Exact EA modifications | `FINAL_REPORT.md` section 17 |
| 7 | Parameters per timeframe | `FINAL_REPORT.md` section 15 |
| 8 | Backtest methodology | `FINAL_REPORT.md` section 18, engine docstring |
| 9 | Out-of-sample results | `results/walkforward/`, DEV/VAL/OOS columns in every lab table |
| 10 | Rejected configurations and why | `FINAL_REPORT.md` section 16 + `results/experiment_log.csv` (conclusion column) |
| - | Data audit | `AUDIT.md`, `data/audit.json` |
| - | EA component map and tick-flow diagram | `EA_MAP.md` |

## Scripts (run from this folder, in this order)

| Script | Step | Output |
|---|---|---|
| `data_prep.py` | 2-4 data build + audit | `data/*.npz`, `data/spread_model.json`, `AUDIT.md` |
| `sma18_engine.py` | engine (import) | - |
| `common.py` | splits, folds, cost scenarios, experiment log, regimes, evaluate/classify | `results/experiment_log.csv` |
| `run_baseline.py` | 5 baseline M1/M5/M15/D1, three cost scenarios, three account views, D1 2003-2026, 18-month window scan | `results/baseline/` |
| `run_trade_analysis.py` | 6-8 giveback, profitable->loss reports, loss categories, trade-level dataset | `results/trade_analysis/` |
| `run_d1_validation.py` | 16 reproduce the 3x claim, one-period test, regime dependence | `results/d1_validation/` |
| `run_filters.py` | 9-10 entry filters one at a time, then progressive combinations | `results/filters/` |
| `run_sl.py` | 11 existing stop description, alternatives A-F | `results/sl/` |
| `run_exits.py` | 12-16 Chandelier / trailing / BE / hybrids / previous TWK trail / ATR- and R-scaled | `results/exits/` |
| `run_ltf.py` | 13-15 lower-timeframe noise, trailing and time-exit sweeps, volatility filter | `results/ltf/` |
| `run_walkforward.py` | 17-20 walk-forward grid (120 configs), sensitivity, Monte Carlo, overfitting audit | `results/walkforward/` |
| `run_account.py` | 21 $200 survivability | `results/account/` |
| `make_report.py` | 23 assemble `FINAL_REPORT.md` and `results/research_tables.xlsx` from the JSON outputs + `narrative.json` | - |

Runtime: the whole chain is about 45 minutes on this machine (M1 runs are ~10 s each; D1 runs 0.05 s).

## Conventions

* **Strategy view** = fixed 0.01 lot, nominal $100,000 balance, no SL% filter: what the rules do, in $ per 0.01 lot (= per oz). **Account views** = $200 with the EA as provided (SL% filter on) and with the filter off.
* Cost scenarios: `A_low` 25-pt spread, no slippage, no swap; `B_real` XM spread by year x hour (M1-equivalent), 10-pt slippage, XM swap; `C_stress` 1.5x spread, 30-pt slippage, swap.
* Splits declared before any run: DEV 2020-09..2023-08, VAL 2023-09..2024-12, OOS 2025-01..2026-09. Walk-forward folds: 2 y train, 1 y validate, 1 y test, rolled yearly.
* Classification rule: Helpful = expectancy/R and PF better than base in DEV, VAL and OOS with >= 30 trades each; Harmful = worse expectancy/R in >= 2 splits; else Neutral. "(still negative)" marks variants that remain net losers.
* Data: Dukascopy XAUUSD M1 bid (Sep 2020 - Sep 2026) and H1 (2003 - 2026) in XM server time; XM GOLD contract facts read from the live terminal. Prices are feed-specific; the MT5 tester on XM will differ trade by trade.
