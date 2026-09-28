"""Scenario requested 2026-09-26: M3 Supertrend flip (Pine entry, filled next bar), volume ratio >= 1.5, ADX > 20,
fixed $4 stop and $12 target measured from the fill, no trailing, one trade at a time, ignore signals while in a trade.
Last 12 months of data (2025-09-25 to 2026-09-25). Costs: XM spread by year (38 pts 2025, 51 pts 2026), swap.
usage: python scenario_fixed_sl_tp.py
"""
import json, time
import numpy as np, pandas as pd
import twk_engine as E

t0 = time.time()
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
years = m1["time"].dt.year.to_numpy(); spread = np.array([E.year_spread_model()[y] for y in years], float)
p = E.CoreParams(); m3 = E.resample(m1, 3); ser = E.compute_series(m3, p); sig = E.signal_table(m3, ser, 3, m1, m3, p, 5)
print(f"M3 bars {len(m3)}, signals {len(sig)} ({time.time()-t0:.0f}s)", flush=True)
END = pd.Timestamp("2026-09-25 17:00"); START = END - pd.DateOffset(years=1); START5 = END - pd.DateOffset(years=5)
LOTS = 0.02; OZ = LOTS * 100

def mk(name, sl=400, tp=1200, **kw):
    base = dict(name=name, min_volume_ratio=1.5, require_m1_box=True, require_m3_box=True, adx_min=20.0,
                initial_sl="fixed", fixed_sl_pts=sl, tp_pts=tp, use_tp=True,
                purple_activation_pts=10**8, protection_activation_pts=10**8, one_to_one=False, purple_trail_always=False,
                close_on_opposite=False, reverse_on_opposite=False, one_position=True, lots=LOTS)
    base.update(kw); return E.MomentumEAParams(**base)

def run(bot, a, b):
    return E.simulate(m1, sig, ser, 3, bot, spread, int(a.timestamp()), int(b.timestamp()))

def summary(tr):
    if len(tr) == 0: return dict(trades=0)
    pnl = tr.pnl.to_numpy(); cum = np.cumsum(pnl); dd = float((np.maximum.accumulate(cum) - cum).max())
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    streak = best = 0
    for x in pnl:
        streak = streak + 1 if x <= 0 else 0; best = max(best, streak)
    reason_col = next((c for c in tr.columns if "reason" in c or c == "why" or c == "exit_by"), None)
    out = dict(trades=int(len(tr)), wins=int(len(wins)), win_rate=float(len(wins) / len(tr)), net=float(pnl.sum()), gross_win=float(wins.sum()), gross_loss=float(-losses.sum()),
               pf=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"), avg_win=float(wins.mean()) if len(wins) else 0.0, avg_loss=float(losses.mean()) if len(losses) else 0.0,
               expectancy=float(pnl.mean()), max_dd=dd, max_losing_streak=int(best), longs=int((tr.side == "BUY").sum()), shorts=int((tr.side == "SELL").sum()),
               net_longs=float(tr[tr.side == "BUY"].pnl.sum()), net_shorts=float(tr[tr.side == "SELL"].pnl.sum()), first=str(tr.entry_time.min())[:16], last=str(tr.entry_time.max())[:16])
    if "spread" in tr.columns: out["spread_cost"] = float((tr.spread * OZ).sum())
    if reason_col: out["exits"] = {str(k): int(v) for k, v in tr[reason_col].value_counts().items()}
    if "exit_time" in tr.columns: out["median_hold_min"] = float(((tr.exit_time - tr.entry_time).dt.total_seconds() / 60).median())
    return out

R = {}
main = mk("main"); tr = run(main, START, END); tr.to_csv("results/trades_scn_fixed_sl4_tp12_M3_1y.csv", index=False)
R["main_1y"] = summary(tr); print("columns:", list(tr.columns)); print("\nMAIN (1y):", json.dumps(R["main_1y"], indent=1, default=str))
tr["month"] = tr.entry_time.dt.to_period("M").astype(str)
R["by_month"] = [dict(month=m, trades=int(len(g)), wins=int((g.pnl > 0).sum()), net=round(float(g.pnl.sum()), 2)) for m, g in tr.groupby("month")]
print("\nBY MONTH:"); print(pd.DataFrame(R["by_month"]).to_string(index=False))
tr["hour"] = tr.entry_time.dt.hour
R["by_hour"] = [dict(hour=int(h), trades=int(len(g)), win_rate=round(float((g.pnl > 0).mean()), 2), net=round(float(g.pnl.sum()), 2)) for h, g in tr.groupby("hour")]
# readings of the rule and the exit on an opposite flip
variants = [mk("ratio on M1 and M3 rows", min_volume_ratio_m3=1.5), mk("ratio only, no box requirement", require_m1_box=False, require_m3_box=False),
            mk("close on opposite flip", close_on_opposite=True), mk("reverse on opposite flip", close_on_opposite=True, reverse_on_opposite=True),
            mk("no volume/ADX filter (raw flips)", min_volume_ratio=0.0, require_m1_box=False, require_m3_box=False, adx_min=0.0),
            mk("main, 15-20h server only", entry_hours=tuple(range(15, 21)))]
R["variants_1y"] = []
for b in variants:
    s = summary(run(b, START, END)); s["variant"] = b.name; R["variants_1y"].append(s)
print("\nVARIANTS (1y):"); print(pd.DataFrame(R["variants_1y"])[["variant", "trades", "win_rate", "net", "pf", "max_dd"]].round(2).to_string(index=False))
# stop/target grid, same year (in-sample: read as sensitivity, not as a tuning result)
R["grid_1y"] = []
for sl in (200, 300, 400, 500, 600, 800):
    for tp in (400, 800, 1200, 1600, 2400):
        s = summary(run(mk(f"sl{sl}_tp{tp}", sl=sl, tp=tp), START, END)); s.update(sl=sl, tp=tp); R["grid_1y"].append(s)
G = pd.DataFrame(R["grid_1y"]); print("\nGRID net $ (rows SL pts, cols TP pts):"); print(G.pivot_table(index="sl", columns="tp", values="net").round(0).to_string())
print("\nGRID win rate:"); print(G.pivot_table(index="sl", columns="tp", values="win_rate").round(2).to_string())
# the same rule on the previous four years, for context
tr5 = run(main, START5, END); tr5["year"] = tr5.entry_time.dt.year
R["by_year_5y"] = [dict(year=int(y), trades=int(len(g)), win_rate=round(float((g.pnl > 0).mean()), 3), net=round(float(g.pnl.sum()), 2), pf=round(float(g[g.pnl > 0].pnl.sum() / -g[g.pnl <= 0].pnl.sum()), 2) if (g.pnl <= 0).any() else None) for y, g in tr5.groupby("year")]
print("\nSAME RULE BY YEAR (5y):"); print(pd.DataFrame(R["by_year_5y"]).to_string(index=False))
R["break_even_win_rate"] = 400 / (400 + 1200)
json.dump(R, open("results/scenario_fixed_sl_tp.json", "w"), indent=1, default=str)
print(f"\ndone ({time.time()-t0:.0f}s)")
