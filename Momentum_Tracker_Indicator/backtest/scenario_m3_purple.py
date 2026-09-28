"""Scenario requested 2026-09-25: M3 signals, volume ratio >= 1.5, M1 + M3 boxes agree, ADX > 20,
entry per Pine (flip close, filled next bar), SL on the purple line from the first tick, SL trails the
purple line on every closed M3 bar. Grid around it, then out-of-sample check.

usage: python scenario_m3_purple.py
"""
import itertools, json, time
import numpy as np
import pandas as pd
import twk_engine as E

t0 = time.time()
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
years = m1["time"].dt.year.to_numpy()
spread = np.array([E.year_spread_model()[y] for y in years], float)
p = E.CoreParams()
m3 = E.resample(m1, 3)
ser = E.compute_series(m3, p)
sig = E.signal_table(m3, ser, 3, m1, m3, p, 5)
print(f"M3 bars {len(m3)}, signals {len(sig)} ({time.time()-t0:.0f}s)", flush=True)

END = pd.Timestamp("2026-09-25 00:00")
W = {"6m": (END - pd.DateOffset(months=6), END), "5y": (END - pd.DateOffset(years=5), END),
     "IS_2021-2024": (END - pd.DateOffset(years=5), pd.Timestamp("2025-01-01")), "OOS_2025-2026": (pd.Timestamp("2025-01-01"), END)}


def run(bot, win):
    a, b = W[win]
    tr = E.simulate(m1, sig, ser, 3, bot, spread, int(a.timestamp()), int(b.timestamp()))
    m = E.metrics(tr)
    m["window"] = win
    if len(tr):
        tr["year"] = tr["entry_time"].dt.year
        m["by_year"] = {int(y): round(float(g.pnl.sum()), 2) for y, g in tr.groupby("year")}
    return tr, m


def mk(name, **kw):
    base = dict(name=name, min_volume_ratio=1.5, require_m1_box=True, require_m3_box=True, adx_min=20.0,
                initial_sl="purple", purple_trail_always=True, use_tp=True, rr=2.0,
                protection_activation_pts=10**8, one_to_one=False,   # no lock / 1:1: purple line only
                close_on_opposite=False, reverse_on_opposite=False, one_position=True, lots=0.02)
    base.update(kw)
    return E.MomentumEAParams(**base)


# 1. the exact scenario, both readings of "1.5x" (M1 row only, or M1 and M3 rows)
exact = [
    mk("exact_ratioM1", ),
    mk("exact_ratioM1M3", min_volume_ratio_m3=1.5),
    mk("exact_noTP", use_tp=False),
    mk("exact_noTP_ratioM1M3", use_tp=False, min_volume_ratio_m3=1.5),
    mk("exact_closeOnFlip", close_on_opposite=True),
    mk("exact_noTP_closeOnFlip", use_tp=False, close_on_opposite=True),
]
results = []
for bot in exact:
    for win in ("6m", "5y"):
        tr, m = run(bot, win)
        tr.to_csv(f"results/trades_scn_{bot.name}_M3_{win}.csv", index=False)
        results.append(dict(bot=bot.name, **m))
        print(f"{bot.name:26s} {win}: trades={m.get('trades',0):5d} net=${m.get('net',0):8.0f} PF={m.get('profit_factor',0):.2f} "
              f"win={m.get('win_rate',0)*100:3.0f}% avgR={m.get('avg_r',float('nan')):.2f} maxDD=${m.get('max_dd',0):.0f} "
              f"byYear={m.get('by_year')}", flush=True)

# 2. grid: what would it take? (in-sample 2021-2024, then the same settings out of sample 2025-2026)
grid = []
for ratio, adx, rr, tp, hours, opp in itertools.product((1.2, 1.5, 2.0), (20, 25, 30), (1.0, 2.0, 3.0), (True, False), (None, (15, 20)), (False, True)):
    if not tp and rr != 2.0:
        continue
    name = f"r{ratio}_adx{adx}_{'tp'+str(rr) if tp else 'noTP'}_{'all' if hours is None else 'ses'}_{'flip' if opp else 'hold'}"
    grid.append(mk(name, min_volume_ratio=ratio, adx_min=float(adx), rr=rr, use_tp=tp, entry_hours=hours, close_on_opposite=opp))
print(f"grid: {len(grid)} configs", flush=True)
rows = []
for i, bot in enumerate(grid):
    _, mi = run(bot, "IS_2021-2024")
    _, mo = run(bot, "OOS_2025-2026")
    _, m6 = run(bot, "6m")
    rows.append(dict(name=bot.name, is_net=mi.get("net", 0), is_pf=mi.get("profit_factor", 0), is_n=mi.get("trades", 0),
                     oos_net=mo.get("net", 0), oos_pf=mo.get("profit_factor", 0), oos_n=mo.get("trades", 0),
                     m6_net=m6.get("net", 0), m6_pf=m6.get("profit_factor", 0), m6_n=m6.get("trades", 0),
                     oos_ci_low=mo.get("ci_low", 0), oos_ci_high=mo.get("ci_high", 0), oos_p=mo.get("p_profit", 0)))
    if (i + 1) % 12 == 0:
        print(f"  {i+1}/{len(grid)} ({time.time()-t0:.0f}s)", flush=True)
g = pd.DataFrame(rows)
g.to_csv("results/scenario_m3_grid.csv", index=False)
print("\nGRID SUMMARY")
print("configs positive in-sample:", int((g.is_net > 0).sum()), "/", len(g))
print("configs positive out-of-sample:", int((g.oos_net > 0).sum()), "/", len(g))
print("positive in both:", int(((g.is_net > 0) & (g.oos_net > 0)).sum()))
print("positive in both AND last 6 months:", int(((g.is_net > 0) & (g.oos_net > 0) & (g.m6_net > 0)).sum()))
print("\nTop 10 by in-sample net, with their out-of-sample result:")
print(g.sort_values("is_net", ascending=False).head(10).to_string(index=False, float_format=lambda x: f"{x:.2f}"))
print("\nTop 10 by out-of-sample net:")
print(g.sort_values("oos_net", ascending=False).head(10).to_string(index=False, float_format=lambda x: f"{x:.2f}"))
json.dump(dict(exact=results, grid=rows, generated=str(pd.Timestamp.now())[:16]), open("results/scenario_m3_summary.json", "w"), indent=1, default=float)
print(f"done {time.time()-t0:.0f}s")
