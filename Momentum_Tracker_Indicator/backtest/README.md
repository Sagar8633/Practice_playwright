# TWK gold bot backtests (local, Python)

Reproduces both TWK robots outside MetaTrader so they can be run over 5 years of XAUUSD M1 data in seconds,
plus a separate volume-profile + order-flow test.

## Files

| File | What it is |
|---|---|
| `twk_engine.py` | Exact port of `TWK_Core.mqh` (Supertrend 1.5/10, 5-bar pivots, up/down volume rows, ADX) and a bar-by-bar simulator for `TWK_PineEA` and `TWK_MomentumEA` (filters, hard SL, quick re-flip, 3-stage trailing, reverse-on-flip, XM spread and swap). |
| `run_all.py` | Runs bot x timeframe (M1/M5/M15) x window (6 months, 5 years) plus the fix candidates. Writes `results/trades_*.csv` and `results/summary.json`. |
| `vp_ob_strategy.py` | Separate test: previous-day volume profile (POC/VAH/VAL from real M1 volume) with an aggressor-delta gate. Writes `results/trades_VP_*.csv` and `results/vp_summary.json`. |
| `make_report.py` | Builds `report.html` from the two summaries and `results/narrative.json`. |
| `scenario_m3_purple.py` | The M3 purple-line-stop scenario and its 144-setting grid with an out-of-sample check. |
| `scenario_fixed_sl_tp.py` | Scenario of 2026-09-26: M3 flips, volume ratio 1.5, ADX > 20, fixed $4 stop / $12 target from the fill, no trailing, one trade at a time; last 12 months, variants, stop/target grid, by-year context (`results/scenario_fixed_sl_tp.json`). Engine options `initial_sl="fixed"`, `fixed_sl_pts`, `tp_pts`. |
| `filter_lab.py` / `filter_lab2.py` | The filter A/B study on the M3 preset: 112 single-filter runs (DEV/VAL/OOS), loss tags, MFE/MAE, profit protection, duration, HTF, hours, entry score, retention rule, combination, walk-forward, robustness, risk sizing. Outputs in `results/lab/`. Run stage 1 once, then stage 2 with `LAB_SKIP_RUNS=1`. |
| `make_lab_report.py` | Builds `filter_lab_report.html` from `results/lab/lab.json`, `ab_table.csv`, `cost_gate_by_tf.csv` and `narrative_lab.json`. |
| `signal_lab.py` | Phase 2: the raw flip as a directional predictor. First-passage to +X/-X in ATR, excursion horizons, outcome classes, feature buckets by period, continuation/reversal, regimes, location, entry timing, cost model, GOOD_SIGNAL search, cross-timeframe check. Outputs in `results/signal/`. Needs `results/lab/runs.pkl` (run `filter_lab.py` first). |
| `make_signal_report.py` | Builds `signal_edge_report.html` from `results/signal/signal_lab.json` and `narrative_signal.json`. |
| `protection_lab.py` | Loss-prevention layer: the development sequence (risk, anti-flip, environment, management) each alone and cumulatively, the recommended stack, counterfactual accounting per blocked trade and reason, chop-score check, risk-sized equity view. Outputs in `results/protection/`. |
| `make_protection_report.py` | Builds `loss_prevention_report.html` from `results/protection/protection.json` and `narrative_protection.json`. |
| `edge_lab.py` | Edge discovery, phases 5-9: A/B/C/D outcome buckets with the real stop, univariate and multivariate (scikit-learn) separation, structure and trend-vs-reversal models, five entry mechanisms, MFE/MAE timing, acceptance gates against the raw and Loss Prevention v1 controls. Outputs in `results/edge/`. Needs `results/signal/signals_M3_full.csv` from `signal_lab.py`. |
| `make_edge_report.py` | Builds `edge_discovery_report.html` from `results/edge/edge_lab.json` and `narrative_edge.json`. |
| `discovery_engine.py` | Phase 12 discovery engine: event generators (volatility, session ranges, levels, reversion, momentum, exhaustion, time of day, state transitions, sequences, TWK-as-contrarian/sequence/state), forward first-passage outcomes on the event ATR, DEV/VAL/OOS split, statuses, robustness, and the permanent ledger `results/discovery/ledger.csv`. Functions are importable; `python discovery_engine.py` runs the full ledger (about 1 minute). Add a hypothesis by adding an event generator that returns bar indices and sides. |
| `discovery_followup.py` | Wider units and longer holds for the gross asymmetries the ledger found (`results/discovery/followup.csv`). |
| `make_discovery_report.py` | Builds `discovery_report.html` from `results/discovery/discovery.json` and `narrative_discovery.json`. |
| `range_objective.py` | Phase 13 Report F: range predictability by event and hour, and the OCO straddle monetisation test (`results/phase13/`). |
| `xasset_lab.py` | Phase 13 Report C: cross-asset lead/lag, shocks and monetisation on XM H1 (`data/xasset/`, `results/phase13/`). Pull H1 only from MT5: a new symbol's M15 request downloads ~100 MB of M1 into the terminal cache on C:. |
| `build_master_ledger.py` | Builds the permanent Edge Hypothesis Ledger `results/ledger/edge_hypothesis_ledger.csv` from every study. |
| `make_phase13_report.py` | Builds `phase13_report.html` (Reports A to G) from `results/phase13/*.json`, the master ledger and `narrative_phase13.json`. |
| `tools/fetch_ticks.js` | Phase 14: Dukascopy XAUUSD ticks (bid, ask, sizes) for the hours around 15:30 server on chosen weekdays, into `data/ticks/` (`node fetch_ticks.js 2025-01-01 2026-09-25 4,5 <outDir>`; install `dukascopy-node` in `tools/` first). About 8 hour-files per minute before rate limits. |
| `release_straddle_ticks.py` | Phase 14 tick reconstruction of the frozen release straddle (`results/phase14/frozen_spec.json`): per-event trigger ordering, fills under three scenarios and three cancellation latencies, DEV-only plateaus, same-day random controls, tick audit. Writes `results/phase14/events.csv`, `plateau_dev.csv`, `tick_audit.csv`. |
| `summarize_phase14.py` / `make_phase14_report.py` | Aggregate to `results/phase14/summary.json` and build `phase14_report.html`. |
| `post_release_ticks.py` | Phase 15: tick timeline after the 15:30 release in 14 bands, spread-normalisation times (2x/1.5x/1.25x, sustained 5 s), price-discovery curve, information value after normalisation (unconditional, five shock states, continuation), same-day controls. Development 2025 only; writes `results/phase15/summary.json` and CSVs. |
| `post_release_candidates.py` | Phase 15 step 2: Track B (time to a 0.5-2 ATR move and 30-min range versus controls), OCO breakout after the release over delay bands and the normalisation time, cost scenarios, shock-range breakout, controls (`results/phase15/candidates.json`). |
| `post_release_momentum.py` | Phase 15 step 3: delayed momentum by delay band and hold with a pre-declared plateau retention rule (`results/phase15/momentum.json`). |
| `make_phase15_report.py` | Builds `phase15_report.html` from `results/phase15/*.json` and `narrative_phase15.json`. |
| `tools/regression.py` | Engine regression checks (`PYTHONPATH=. python tools/regression.py`); expected values in the file. |
| `tools/patch_engine_protection.py` | The one-off patch that added the permission system to the engine (already applied; kept for reference). |
| `data/duka_chunks/bid_YYYY-MM.csv` | Dukascopy XAUUSD M1 bid candles, UTC, one file per month (downloaded with `dukascopy-node`). |
| `data/XAUUSD_M1_servertime.csv.gz` | The merged 5-year M1 series shifted to XM server time (EET), prices rounded to 0.01. |
| `data/xm_GOLD_{M1,M5,M15,H1}.csv.gz` | XM's own GOLD bars as far back as the terminal serves them (100k bars per timeframe) with the real `spread` column. |

## Run

```
pip install pandas numpy
python run_all.py            # ~2-4 min
python vp_ob_strategy.py     # ~1 min
python make_report.py
```

## Completing the data (22 months still missing on 2026-09-25)

Dukascopy rate-limited the session (HTTP 429) after three parallel downloaders ran at once. The ban lasted over
an hour. To fetch the missing months later, one process at a time:

```
cd tools
npm init -y && npm install dukascopy-node
node fetch_dukascopy_months.js        # skips months already in data/duka_chunks, retries with 90 s backoff
```

Then rerun the three Python scripts above. Missing on 2026-09-25: 2021-10 to 2022-03, 2022-05 to 07, 2022-09,
2023-01, 2023-05, 2023-08, 2024-01, 2024-03, 2024-04, 2024-07, 2024-09 to 11, 2025-01, 2025-12.

## Assumptions that matter

- Bars are bid. Ask = bid + spread. Spread = XM median by year (32 pts in 2021-23, 36 in 2024, 38 in 2025, 51 in 2026), taken from XM's own bars.
- Inside one M1 bar a stop is checked before a target. A trailed stop is tested against the bar's extreme on bars that close against the trade (`trail_mode="path"`); `trail_mode="worst"` tests it on every bar. Real ticks sit between the two.
- Swap: XM GOLD, long -86.84 pts/night, short +19.79 pts/night, triple on Wednesday.
- 0.01 lot = 1 oz, so $1.00 of price = $1 P&L per 0.01 lot. Results are shown at 0.02 lot.
- Dukascopy volume is traded volume, not tick count. The volume-ratio and box filters use ratios, so the effect is small, but trade lists will not match the MT5 tester one for one.

## Validation against the Strategy Tester

The Jan-Feb 2026 M3 run from the tester journal (118 trades, +$61) versus this engine on Dukascopy bars with the same inputs (120 trades, +$67); 77 of the first 120 tester entries have an engine entry within 3 minutes. Tick-level trailing in volatile months (Mar 2026) exits more often than bar-level trailing can show, which is why the Momentum EA is reported under both trailing assumptions.

## GitHub scalping-bot research (26 Sep 2026)

`GITHUB_SCALPING_RESEARCH.md` is the report. The one reproducible repository (Nyao Scalper MT5 v43) is ported in
`nyao_engine.py`; `nyao_tick_calibration.py` calibrates its $0.20 trailing stop on the phase-14 tick sample,
`nyao_lab.py` runs the profiles / periods / costs / perturbations / component tests against the TWK M3 baseline,
`nyao_lab2.py` the fixed-stop research variants and ablations, `make_nyao_tables.py` the tables and charts. Everything
lands in `results/nyao/` (inventory, code audit, comparison and component CSVs, loss-pattern and robustness analyses,
trades, charts, the EA source and its profiles). Uses `data/XAUUSD_M1_servertime_full.csv.gz`, the 60-month file built
from all Dukascopy chunks (the earlier labs used the 39-month `XAUUSD_M1_servertime.csv.gz`). Run the scripts one at a
time; two of them together exhaust the machine's memory.
