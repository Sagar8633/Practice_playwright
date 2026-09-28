# forexmarket: SimpleSMA18Bot on the forex majors, silver, bitcoin and US oil

Third independent study (28 Sep 2026) of the 18/200 SMA breakout strategy developed on gold: EURUSD, GBPUSD, USDJPY, AUDUSD,
USDCAD, USDCHF, NZDUSD (the seven most-traded pairs), silver (XM SILVER), bitcoin (XM BTCUSD) and WTI crude (XM OILCash),
1-minute data Sep 2021 to Sep 2026, every timeframe from 1m to D1, XM Global MT5 contract specifications and spreads.

Start with `reports/FOREX_CFD_FINAL_REPORT.md`, then the per-instrument reports.

## Layout

```
forexmarket/
  data/            duka/<instr>/m1_YYYY-MM.csv, h1_YYYY.csv (Dukascopy); <instr>/m1_server.npz, h1_server.npz, audit.json;
                   xm/xm_<SYM>_<TF>.csv.gz (XM bars with spread), xm_symbol_specs.json, spread_models.json; DATA_AUDIT.md
  strategy/        engine_fx.py (gold engine generalised: point, contract, swap, spread model per instrument), common_fx.py
  backtests/       run_baseline.py, baseline_metrics.json, <instr>/<config>_<tf>_<scenario>_trades.csv.gz
  experiments/     run_cost_analysis.py, run_regime_session.py, run_sweeps_wf.py, run_variants.py (+ json results)
  research/        experiment_log.csv, timeframe_analysis.md, cost_analysis.md, regime_analysis.md, robustness_analysis.md,
                   walk_forward_analysis.md, variants_mtf_analysis.md
  reports/         FOREX_CFD_FINAL_REPORT.md, <SYM>_FINAL_REPORT.md, make_reports.py, narrative.json
  tools/           fetch_duka.js, xm_pull2.py, prep_data.py, make_data_audit.py, patch_engine_fx.py
```

## Reproduce

```
cd forexmarket
node tools/fetch_duka.js eurusd gbpusd usdjpy audusd usdcad usdchf nzdusd xagusd btcusd lightcmdusd   # one process only (429 otherwise); hours
python tools/xm_pull2.py            # needs the XM MT5 terminal logged in (demo)
python tools/prep_data.py           # server-time caches, audits, spread models
python tools/make_data_audit.py
python backtests/run_baseline.py    # 10 instruments x 2 configs x 10 timeframes x 3 scenarios + long D1
python experiments/run_cost_analysis.py; python experiments/run_regime_session.py
python experiments/run_sweeps_wf.py; python experiments/run_variants.py
python reports/make_reports.py
```

## Conventions

* Money: USD per 0.01 lot (XM minimum lot); USD-base pairs converted at the exit price. Percentages on $1,000 per 0.01 lot.
* Scenario A gross; B realistic (XM spread by server hour and year from XM's own bars, slippage per side, XM swap points);
  C stress (1.5x spread, 3x slippage). Slippage per side (B/C): forex 3/10 points, silver 5/15, bitcoin 300/1000, oil 3/10.
* Splits fixed before any run: TRAIN 2021-09-01..2024-08-31, VAL 2024-09-01..2025-08-31, OOS 2025-09-01..2026-09-26.
  Robust = positive expectancy and PF > 1 after B costs in all three splits with at least 30 trades each.
* AS-IS uses the MT5 point of each symbol (so 500 points = 50 pips on EURUSD, $5 on gold, $50 on bitcoin: the literal EA
  behaviour); FINAL_H4 is the ATR-scaled exit stack, scale-free. The volume filter is on in both (Dukascopy volumes).
* Regression check: the generalised engine reproduces the gold study's numbers on the gold data to the cent (H4 final
  config 306 trades / $2,529.90 / PF 1.737; D1 AS-IS 85 / $619.14; M15 AS-IS 4,559 / -$983.88).

## Data actually used (28 Sep 2026)

Dukascopy rate-limited this machine for the whole session, so: the seven majors use FXCM's public minute archive (Sep 2021 to
Sep 2026, June-July 2026 and late September 2026 missing, no volume, so the volume filter is off on those runs); bitcoin uses
Binance BTCUSDT minute klines (complete, with volume); silver and oil have no free minute source and run from 15 minutes up on
XM's own M15 bars (from mid-2022) with XM tick volume. Every instrument's 2015-2026 daily test and the spread model use XM's own
H1 bars with XM's spread by year and hour. Details in `data/DATA_AUDIT.md`.

## Findings

**No statistically defensible edge on any of the ten instruments.** 184 scenario-B baseline runs, 17 positive after costs, 0
pass the robust rule; below one hour every instrument loses on costs. Best single result: USDJPY 2h with the ATR exits (PF 1.29,
t 2.2, +$289 per 0.01 lot) but negative out of sample and carried by the 2021-24 yen trend; silver D1 (+$1,764 on 30 trades) is
the 2025-26 rally in the out-of-sample window; bitcoin D1 with the ATR exits (+$487 on 54 trades, t 1.3) is nothing without its
five best trades. GBPUSD, AUDUSD, USDCAD and NZDUSD are negative on every run, and all majors are negative on 2015-2026 daily.
Read `reports/FOREX_CFD_FINAL_REPORT.md` or open `reports/report_forex.html`.
