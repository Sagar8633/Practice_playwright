"""Scalp-unit test requested 2026-09-26: on M1 and M3, TWK flip entries with fixed stops and targets of $1 to $4 measured
from the fill (ask for buys, bid for sells; the target is hit on the opposite quote, so the spread shows up as a lower
win rate rather than a smaller win). Filtered (volume ratio 1.5, boxes, ADX > 20) and raw flips, one position, no
trailing, 5 years by year, 0.02 lot. Break-even win rate = SL / (SL + TP). Yearly return shown on a $1,000 account
at fixed 0.02 lot (no compounding). usage: python scenario_scalp_units.py
"""
import json, time
import numpy as np, pandas as pd
import twk_engine as E

t0 = time.time()
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
spread = np.array([E.year_spread_model()[y] for y in m1["time"].dt.year.to_numpy()], float)
p = E.CoreParams(); m3 = E.resample(m1, 3)
END = pd.Timestamp("2026-09-25 17:00"); START5 = END - pd.DateOffset(years=5); START1 = END - pd.DateOffset(years=1)
CELLS = [(100, 100), (200, 200), (300, 300), (400, 400), (100, 200), (200, 400), (100, 300)]
rows = []
for tf in (1, 3):
    bars = E.resample(m1, tf); ser = E.compute_series(bars, p); sig = E.signal_table(bars, ser, tf, m1, m3, p, 5)
    print(f"M{tf}: bars {len(bars)}, signals {len(sig)} ({time.time()-t0:.0f}s)", flush=True)
    for label, flt in (("filtered", dict(min_volume_ratio=1.5, require_m1_box=True, require_m3_box=True, adx_min=20.0)), ("raw flips", dict(min_volume_ratio=0.0, require_m1_box=False, require_m3_box=False, adx_min=0.0))):
        for sl, tp in CELLS:
            bot = E.MomentumEAParams(name=f"M{tf}_{label}_{sl}_{tp}", initial_sl="fixed", fixed_sl_pts=sl, tp_pts=tp, purple_activation_pts=10**8, protection_activation_pts=10**8, one_to_one=False, one_position=True, lots=0.02, hard_sl_pts={1: 0, 3: 0, 5: 0, 15: 0}, **flt)
            tr = E.simulate(m1, sig, ser, tf, bot, spread, int(START5.timestamp()), int(END.timestamp()))
            if len(tr) == 0: continue
            tr["year"] = tr.entry_time.dt.year
            for y, g in list(tr.groupby("year")) + [("last 12 months", tr[tr.entry_time >= START1]), ("5 years", tr)]:
                rows.append(dict(tf=f"M{tf}", signal=label, sl=sl / 100, tp=tp / 100, period=str(y), trades=int(len(g)), win_rate=float((g.pnl > 0).mean()), break_even=sl / (sl + tp), net=float(g.pnl.sum()), spread_paid=float((g.spread * 2).sum()) if "spread" in g else np.nan, ret_pct_1000=float(g.pnl.sum() / 10)))
            print(f"  {label} SL {sl/100:.0f} TP {tp/100:.0f}: {len(tr)} trades, win {float((tr.pnl > 0).mean()):.3f} vs {sl/(sl+tp):.2f} needed, 5y net {tr.pnl.sum():.0f} ({time.time()-t0:.0f}s)", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/scenario_scalp_units.csv", index=False)
pd.set_option("display.width", 250)
for per in ("last 12 months", "5 years"):
    print(f"\n=== {per}: win rate achieved / needed, net $, return % on $1,000 at 0.02 lot ===")
    d = D[D.period == per].copy(); d["cell"] = d.sl.map(lambda v: f"${v:.0f}") + "/" + d.tp.map(lambda v: f"${v:.0f}")
    print(d.pivot_table(index=["tf", "signal"], columns="cell", values="win_rate").round(2).to_string()); print(d.pivot_table(index=["tf", "signal"], columns="cell", values="net").round(0).to_string())
print("\n=== by year, $1/$1 and $2/$2 and $4/$4, filtered, return % on $1,000 ===")
d = D[(D.period.str.len() == 4) & (D.signal == "filtered") & (D.sl == D.tp) & D.sl.isin([1, 2, 4])]
print(d.pivot_table(index=["tf", "sl"], columns="period", values="ret_pct_1000").round(1).to_string())
print(d.pivot_table(index=["tf", "sl"], columns="period", values="win_rate").round(2).to_string())
print(f"done ({time.time()-t0:.0f}s)")
