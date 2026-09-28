import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import sma18_engine as E, common as C
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results")
P = json.load(open(os.path.join(HERE, "..", "study3", "results", "study3.json")))["final"]["params"]
BASE = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, **C.COST["B_real"], **P)
def acc(tr, st, sb=200.0):
    bal = sb + tr.pnl.cumsum(); peak = np.maximum.accumulate(np.concatenate([[sb], bal.to_numpy()]))
    dd = (peak[1:] - bal.to_numpy()) / peak[1:]
    return {"end": round(st["final_balance"], 2), "growth": round(st["final_balance"] / sb, 2), "dd_pct": round(100 * float(dd.max()), 1), "max_lot": float(tr.lots.max()), "worst": round(float(tr.pnl.min()), 2), "partials": int((tr.reason == 14).sum()), "ruin": bool(st["ruin"])}
R = {}
for bb in (200, 500, 1000, 2000):
    for mode, mn in (("partial skip", 0), ("partial close-all at min lot", 1)):
        nm = f"base ${bb} doubling, {mode}"; R[nm] = {}
        for w, (a, b) in {"6y": (C.DATA_START, C.DATA_END), "2023-26": ("2023-01-01", "2026-09-26"), "last12m": ("2025-09-26", "2026-09-26")}.items():
            p = E.Params(start=a, end=b, start_balance=200.0, sizing=2, base_balance=float(bb), max_lots=5.0, partial_enable=True, partial_min_mode=mn, **BASE); tr, st = E.run(p); R[nm][w] = acc(tr, st)
        R[nm]["start_years"] = {}
        for y in (2021, 2022, 2023, 2024, 2025, 2026):
            p = E.Params(start=f"{y}-01-01", end=C.DATA_END, start_balance=200.0, sizing=2, base_balance=float(bb), max_lots=5.0, partial_enable=True, partial_min_mode=mn, **BASE); tr, st = E.run(p); R[nm]["start_years"][y] = acc(tr, st)
        print(nm.ljust(48), "6y", R[nm]["6y"], "| last12m", R[nm]["last12m"]["end"], R[nm]["last12m"]["ruin"], "| start-year ruins", sum(v["ruin"] for v in R[nm]["start_years"].values()), "of 6; ends", [v["end"] for v in R[nm]["start_years"].values()], flush=True)
# MC with compounding for each base (no partial), from the fixed-lot sequence
trf = pd.read_csv(os.path.join(OUT, "trades_A_6y.csv")); pnl01 = trf.pnl.to_numpy(); rng = np.random.default_rng(11)
def compound(seq, base, start=200.0, base_lot=0.01, max_lot=5.0, margin_per_lot=500.0):
    bal = start; peak = start; dd = 0.0
    for x in seq:
        tier = 0; b2 = bal
        while b2 >= 2 * base and tier < 30: b2 /= 2; tier += 1
        if bal < base: tier = 0
        lot = min(base_lot * 2 ** tier, max_lot)
        if bal < margin_per_lot * lot: return bal, dd, True
        bal += x * (lot / 0.01)
        if bal <= 0: return bal, dd, True
        peak = max(peak, bal); dd = max(dd, (peak - bal) / peak)
    return bal, dd, False
R["mc"] = {}
for bb in (200, 500, 1000, 2000):
    res = [compound(rng.permutation(pnl01), bb) for _ in range(4000)]
    ends = np.array([r[0] for r in res]); dds = np.array([r[1] for r in res]); ruin = np.mean([r[2] for r in res])
    R["mc"][bb] = {"p_ruin": round(float(ruin), 4), "end_p05": round(float(np.percentile(ends, 5)), 2), "end_median": round(float(np.median(ends)), 2), "end_p95": round(float(np.percentile(ends, 95)), 2), "dd_median_pct": round(100 * float(np.median(dds)), 1), "dd_p95_pct": round(100 * float(np.percentile(dds, 95)), 1)}
    print("MC base", bb, R["mc"][bb], flush=True)
json.dump(R, open(os.path.join(OUT, "extra_variants.json"), "w"), indent=1, default=C._default)
