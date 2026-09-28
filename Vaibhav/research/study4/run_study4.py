"""Study 4: tiered lot sizing + scaled partial exit on the final H4 configuration, from $200.

Rules implemented (engine sizing=2, partial_enable):
  lot = BaseLot x 2^floor(log2(balance / BaseBalance)), never below BaseLot, capped at MaxLot, from the balance at order time
  partial exit once per position when floating profit >= PartialProfit(tier): tiers 0-1 $100, then doubling (200, 400, ...);
  closes PartialClosePercent (50%) of the volume; at tier 0 the 50% share (0.005) is below XM's 0.01 minimum ->
  mode SKIP (no partial) or CLOSE_ALL (take the whole position at the target).
Everything is a full account simulation: $200 start, margin check, stop-out, balance-dependent lots.
"""
import json, os, sys, time
from dataclasses import replace
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import sma18_engine as E
import common as C

OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
P = json.load(open(os.path.join(ROOT, "study3", "results", "study3.json")))["final"]["params"]
BASE = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, **C.COST["B_real"], **P)
VARIANTS = {"A fixed 0.01 lot": dict(sizing=0, lots=0.01),
            "B tiered lots, no partial": dict(sizing=2, base_balance=200.0, max_lots=5.0),
            "C tiered + partial 50% at $100 (skip at 0.01 lot)": dict(sizing=2, base_balance=200.0, max_lots=5.0, partial_enable=True, partial_min_mode=0),
            "D tiered + partial 50% at $100 (close all at 0.01 lot)": dict(sizing=2, base_balance=200.0, max_lots=5.0, partial_enable=True, partial_min_mode=1),
            "E tiered + partial, lot capped at 0.20": dict(sizing=2, base_balance=200.0, max_lots=0.20, partial_enable=True, partial_min_mode=0)}
WINDOWS = {"6y 2020-09..2026-09": (C.DATA_START, C.DATA_END), "2023-01..2026-09": ("2023-01-01", "2026-09-26"), "last 12 months": ("2025-09-26", "2026-09-26")}


def account_metrics(tr, st, start_bal):
    pos_rows = tr[tr.reason != 14]
    bal = start_bal + tr.pnl.cumsum() if len(tr) else pd.Series([start_bal])
    peak = np.maximum.accumulate(np.concatenate([[start_bal], bal.to_numpy()]))
    dd = peak[1:] - bal.to_numpy() if len(tr) else np.array([0.0]); ddp = dd / peak[1:] if len(tr) else np.array([0.0])
    m = {"positions": int(len(pos_rows)), "closing_deals": int(len(tr)), "partials": int((tr.reason == 14).sum()), "end_balance": round(st["final_balance"], 2), "growth_x": round(st["final_balance"] / start_bal, 2),
         "net": round(float(tr.pnl.sum()), 2), "max_dd_usd": round(float(dd.max()), 2), "max_dd_pct": round(100 * float(ddp.max()), 1), "max_lot": float(tr.lots.max()) if len(tr) else 0.0,
         "worst_deal": round(float(tr.pnl.min()), 2) if len(tr) else 0.0, "best_deal": round(float(tr.pnl.max()), 2) if len(tr) else 0.0, "ruin": bool(st["ruin"]), "stop_out": int(st["stop_out"]),
         "win_rate_positions": round(100 * float((pos_rows.pnl > 0).mean()), 1) if len(pos_rows) else None, "partial_pnl": round(float(tr.loc[tr.reason == 14, "pnl"].sum()), 2),
         "max_consec_losing_positions": 0, "peak_balance": round(float(peak.max()), 2)}
    cl = ml = 0
    for x in pos_rows.pnl:
        cl = cl + 1 if x < 0 else 0; ml = max(ml, cl)
    m["max_consec_losing_positions"] = ml
    if len(tr):
        tr = tr.copy(); tr["year"] = tr.time_out.dt.year
        m["balance_by_year_end"] = {int(y): round(float(start_bal + tr[tr.year <= y].pnl.sum()), 2) for y in sorted(tr.year.unique())}
        # tier timeline: first time each lot size was used
        m["first_use_of_lot"] = {float(l): str(tr[tr.lots >= l - 1e-9].time_in.min())[:10] for l in sorted(tr.lots.unique())}
    return m


R = {"variants": {}, "start_years": {}, "mc": {}}
for w, (a, b) in WINDOWS.items():
    R["variants"][w] = {}
    for nm, kw in VARIANTS.items():
        p = E.Params(start=a, end=b, start_balance=200.0, **BASE, **kw); tr, st = E.run(p)
        m = account_metrics(tr, st, 200.0); R["variants"][w][nm] = m
        tr.to_csv(os.path.join(OUT, f"trades_{nm[0]}_{w.split(' ')[0].replace('..', '_')}.csv"), index=False)
        C.log_experiment("S4-dynamic-lots", f"{nm} [{w}]", p, E.metrics(tr, st, 200.0, E.months_between(a, b)), "B_real", w, exit_logic=C.exit_desc(p), conclusion=f"end {m['end_balance']} growth {m['growth_x']}x DD {m['max_dd_pct']}% max lot {m['max_lot']} ruin {m['ruin']}")
        print(f"{w:22} {nm:56} end {m['end_balance']:10.2f} ({m['growth_x']:6.2f}x) maxDD {m['max_dd_usd']:9.2f} ({m['max_dd_pct']:5.1f}%) max lot {m['max_lot']:.2f} worst deal {m['worst_deal']:9.2f} partials {m['partials']:3} ruin {m['ruin']} ({time.time()-t0:.0f}s)", flush=True)

# ---- start-date sensitivity: $200 started at the beginning of each year, run to the data end
for nm in ("A fixed 0.01 lot", "C tiered + partial 50% at $100 (skip at 0.01 lot)", "D tiered + partial 50% at $100 (close all at 0.01 lot)", "B tiered lots, no partial"):
    R["start_years"][nm] = {}
    for y in (2021, 2022, 2023, 2024, 2025, 2026):
        p = E.Params(start=f"{y}-01-01", end=C.DATA_END, start_balance=200.0, **BASE, **VARIANTS[nm]); tr, st = E.run(p); m = account_metrics(tr, st, 200.0)
        R["start_years"][nm][y] = {k: m[k] for k in ("end_balance", "growth_x", "max_dd_usd", "max_dd_pct", "max_lot", "ruin", "positions", "partials")}
    print(nm, {y: (v["end_balance"], v["max_dd_pct"], v["ruin"]) for y, v in R["start_years"][nm].items()}, flush=True)

# ---- trade-order Monte Carlo with compounding (tier rule applied to shuffled / resampled per-0.01-lot outcomes of the fixed-lot run)
trf = pd.read_csv(os.path.join(OUT, "trades_A_6y.csv"))
pnl01 = trf.pnl.to_numpy()          # $ per 0.01 lot per position (no partials in variant A)


def compound(seq, start=200.0, base=200.0, base_lot=0.01, max_lot=5.0, margin_per_lot=500.0):
    bal = start; peak = start; dd = 0.0; ml = 0.0
    for x in seq:
        tier = 0; bb = bal
        while bb >= 2 * base and tier < 30: bb /= 2; tier += 1
        if bal < base: tier = 0
        lot = min(base_lot * 2 ** tier, max_lot); ml = max(ml, lot)
        if bal < margin_per_lot * lot: return bal, dd, ml, True
        bal += x * (lot / 0.01)
        if bal <= 0: return bal, dd, ml, True
        peak = max(peak, bal); dd = max(dd, (peak - bal) / peak)
    return bal, dd, ml, False


rng = np.random.default_rng(11)
for mode in ("shuffle", "bootstrap"):
    ends = []; dds = []; ruins = 0; mls = []
    for i in range(5000):
        seq = rng.permutation(pnl01) if mode == "shuffle" else rng.choice(pnl01, len(pnl01))
        e, d, ml, r = compound(seq); ends.append(e); dds.append(d); mls.append(ml); ruins += int(r)
    ends = np.array(ends); dds = np.array(dds)
    R["mc"][mode] = {"p_ruin": round(ruins / 5000, 4), "end_p05": round(float(np.percentile(ends, 5)), 2), "end_median": round(float(np.median(ends)), 2), "end_p95": round(float(np.percentile(ends, 95)), 2), "end_below_200": round(float((ends < 200).mean()), 4),
                     "dd_median_pct": round(100 * float(np.median(dds)), 1), "dd_p95_pct": round(100 * float(np.percentile(dds, 95)), 1), "max_lot_median": float(np.median(mls))}
    print("MC", mode, R["mc"][mode], flush=True)
# same MC with the lot capped at 0.20
ends = []; ruins = 0; dds = []
for i in range(5000):
    e, d, ml, r = compound(rng.permutation(pnl01), max_lot=0.20); ends.append(e); dds.append(d); ruins += int(r)
R["mc"]["shuffle_cap_0.20"] = {"p_ruin": round(ruins / 5000, 4), "end_p05": round(float(np.percentile(ends, 5)), 2), "end_median": round(float(np.median(ends)), 2), "end_p95": round(float(np.percentile(ends, 95)), 2), "dd_p95_pct": round(100 * float(np.percentile(dds, 95)), 1)}
print("MC shuffle cap 0.20", R["mc"]["shuffle_cap_0.20"], flush=True)
with open(os.path.join(OUT, "study4.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, indent=1, default=C._default)
print("done", round(time.time() - t0), "s")
