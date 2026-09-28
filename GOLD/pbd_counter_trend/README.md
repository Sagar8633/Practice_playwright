# PBD counter-trend framework on XAUUSD

Backtest of Patrick Nill's "Counter-Trend Swing Trading" (PBD model: P = up-impulse then range,
B = down-impulse then range) translated into pre-registered objective rules and run on 5 years of
Dukascopy M1 gold with XM spread/swap. Built 2026-09-26.

Read first: `FINAL_REPORT.md` (20 sections) or the published HTML page (`report.html`).
Machine-readable rules: `spec/pbd_xauusd_rules.json`. Deliverables: `results/deliverables/` (69 files).

## Reproduce

```
cd GOLD/pbd_counter_trend
set OPENBLAS_NUM_THREADS=1
python pbd/data.py            # Dukascopy M1 -> data/m1.pkl, data/m15.pkl (needs the duka_chunks + xm_GOLD_M15.csv.gz)
python -m pbd.profile          # weekly value areas -> data/m15_va.pkl
python run_baseline.py         # results/baseline: trades, taxonomy, filters, breakdowns, equity
python experiments.py          # results/experiments: one-variable sweeps (~5 min)
python robustness.py           # results/robustness: grids, walk-forward, cost sensitivity
python candidates.py           # results/candidates: staged combinations
python va_sensitivity.py       # value-area volume-source sensitivity
python report_data.py          # results/report_data.json + results/deliverables
python make_final_report.py    # FINAL_REPORT.md
python make_html.py            # report.html
```

`duka_fetch/fetch_missing.js` backfills Dukascopy months into
`Momentum_Tracker_Indicator/backtest/data/duka_chunks/` (July 2024 is rate-limited by Dukascopy and stays missing).

## Layout

- `pbd/data.py` loading, M15 resample with M1 index map, XM spread (server time = Europe/Athens), ATR, DST-aware sessions, news-slot proxy, FOMC dates, DEV/VAL/OOS split
- `pbd/profile.py` weekly volume profile / value area (Dukascopy volume, tick volume, TPO, developing week)
- `pbd/structure.py` impulse -> range -> playbook state machine; `BASELINE` = the pre-registered parameters
- `pbd/engine.py` M1-path simulation, ideal vs realistic costs, swap, gap-through, MFE/MAE, metrics
- `pbd/analysis.py` 20-label loss taxonomy, 20 no-trade filters, breakdowns, equity curves
- `pbd/run.py` shared runner (detect + simulate, cached per parameter set)

## Verdict

No positive expectancy in any period, with or without costs (see FINAL_REPORT.md section 20).
No Gold Strategy Specification is issued.
