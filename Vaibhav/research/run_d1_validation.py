"""STEP 16 / section 16: D1 validation of the reported ~3x growth in ~1.5 years.

The only D1 tester profile on this machine is SimpleSMA18Bot_v13 on GOLD Daily, 2024-01-01 .. 2026-09-15, deposit $5,000,
LotSize 0.01, ProtectionMode=2 (Chandelier 22/22x3) from the first tick, BreakEven 500/10, MaxLossMode=1 cap 1500 pts,
MinStopPoints 150, MaxPendingBars 5, UseSLPercentFilter=false. v1.00 (the EA under study) differs: swing protection after
500 pts, no max-loss cap, no pending expiry, SL% filter on. Both are reproduced here.
"""
import os
from dataclasses import replace
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "d1_validation"); os.makedirs(OUT, exist_ok=True)
CLAIM = ("2024-01-01", "2026-09-16")

CONFIGS = {
    "v1.00_defaults_$200": dict(start_balance=200.0, use_sl_pct=True, margin_check=True),
    "v1.00_defaults_$5000": dict(start_balance=5000.0, use_sl_pct=True, margin_check=True),
    "v1.00_nofilter_$200": dict(start_balance=200.0, use_sl_pct=False, margin_check=True),
    "v13like_$5000": dict(start_balance=5000.0, use_sl_pct=False, margin_check=True, protection=2, prot_start_mode=0, sl_mode=2, sl_cap_pts=1500, min_sl_pts=150, pending_max_bars=5),
    "v13like_$200": dict(start_balance=200.0, use_sl_pct=False, margin_check=True, protection=2, prot_start_mode=0, sl_mode=2, sl_cap_pts=1500, min_sl_pts=150, pending_max_bars=5),
}
res = {}
rows = []
for cname, kw in CONFIGS.items():
    for per, (a, b), pk in (("claim_2024-01..2026-09", CLAIM, "m1"), ("6y_2020-09..2026-09", (C.DATA_START, C.DATA_END), "m1"), ("23y_2003..2026", (C.D1_START, C.DATA_END), "h1")):
        for cost in ("A_low", "B_real", "C_stress"):
            p = E.Params(tf_minutes=1440, path=pk, start=a, end=b, **kw, **C.COST[cost])
            tr, st = E.run(p); m = E.metrics(tr, st, p.start_balance, E.months_between(a, b))
            res.setdefault(cname, {}).setdefault(per, {})[cost] = m
            rows.append({"config": cname, "period": per, "cost": cost, "trades": m["trades"], "net": m["net_profit"], "growth_x": round(m["end_balance"] / p.start_balance, 2), "pf": m.get("profit_factor"),
                         "win_rate": m.get("win_rate"), "max_dd_usd": m.get("max_dd_usd"), "max_dd_pct": m.get("max_dd_pct"), "cagr_pct": m.get("cagr_pct"), "blocked_sl_pct": m.get("blocked_sl_pct"),
                         "exit_mix": m.get("exit_mix"), "ruin": m.get("ruin")})
            if cost == "B_real":
                C.tag_regimes(tr).to_csv(os.path.join(OUT, f"trades_{cname.replace('$', '')}_{per.split('_')[0]}.csv"), index=False)
                C.log_experiment("P16-D1-validation", f"Reproduce the ~3x/1.5y D1 claim: {cname}", p, m, cost, f"{a}..{b}", filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                                 conclusion=f"growth {round(m['end_balance']/p.start_balance,2)}x, PF {m.get('profit_factor')}, DD {m.get('max_dd_usd')}")
            print(f"{cname:22} {per:22} {cost:9} trades {m['trades']:4} net {m['net_profit']:9.2f} growth {m['end_balance']/p.start_balance:5.2f}x PF {m.get('profit_factor')!s:>6} DD {m.get('max_dd_usd')} blocked {m.get('blocked_sl_pct')}", flush=True)
tab = pd.DataFrame(rows); tab.to_csv(os.path.join(OUT, "d1_validation_table.csv"), index=False)

# ---- regime dependence and "one exceptional period" test on the 23-year strategy run (v1.00, filter off, realistic costs)
p = E.Params(tf_minutes=1440, path="h1", start=C.D1_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
tr, st = E.run(p); tr = C.tag_regimes(tr); tr["year"] = tr["time_out"].dt.year
yr = tr.groupby("year")["pnl"].agg(["size", "sum"]).round(2)
share_top = float(tr.nlargest(5, "pnl")["pnl"].sum() / max(tr.loc[tr["pnl"] > 0, "pnl"].sum(), 1e-9))
by_reg = C.by_group(tr, "regime"); by_dir = C.by_group(tr, "regime_direction"); by_side = C.by_group(tr, "side")
# exclude each calendar year in turn
excl = {int(y): round(float(tr.loc[tr["year"] != y, "pnl"].sum()), 2) for y in yr.index}
# same exits effective? MA18 vs BE vs swing net contribution
by_exit = C.by_group(tr, "exit_reason")
val = {"claim_source": "SimpleSMA18Bot_v13.GOLD.i#.Daily.20240101_20260915.000.ini (deposit 5000, Chandelier immediate, cap 1500, pending 5 bars, SL% filter off)",
       "years": yr.to_dict("index"), "share_of_gross_profit_from_top5_trades": round(share_top, 3), "net_excluding_year": excl,
       "by_regime": by_reg.to_dict("index"), "by_direction_regime": by_dir.to_dict("index"), "by_side": by_side.to_dict("index"), "by_exit": by_exit.to_dict("index"),
       "positive_years": int((yr["sum"] > 0).sum()), "total_years": int(len(yr))}
C.save_json({"table": rows, "robustness_23y": val}, "d1_validation/summary.json")

L = ["# D1 validation", "", "Claim source on this machine: " + val["claim_source"] + ". The EA under study is v1.00 (swing protection after 500 pts, no max-loss cap, no pending expiry, SL% filter on).", "",
     "| config | period | cost | trades | net $ | growth | PF | win % | maxDD $ | maxDD % | CAGR % | blocked by SL% | ruin |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
for r in rows:
    L.append(f"| {r['config']} | {r['period']} | {r['cost']} | {r['trades']} | {r['net']} | {r['growth_x']}x | {r['pf']} | {r['win_rate']} | {r['max_dd_usd']} | {r['max_dd_pct']} | {r['cagr_pct']} | {r['blocked_sl_pct']} | {r['ruin']} |")
L += ["", "## Is the D1 result one exceptional period? (v1.00 rules, filter off, 0.01 lot, realistic costs, 2003-2026 on the H1 path)", "",
      f"Positive years: {val['positive_years']} of {val['total_years']}. Top-5 trades = {val['share_of_gross_profit_from_top5_trades']:.0%} of gross profit.", "",
      "| year | trades | net $ | net excluding this year $ |", "|---|---:|---:|---:|"]
for y, v in val["years"].items():
    L.append(f"| {y} | {v['size']} | {v['sum']} | {excl[int(y)]} |")
L += ["", "### By regime (entry day)", "", by_reg.to_markdown() if len(by_reg) else "", "", "### By direction regime", "", by_dir.to_markdown() if len(by_dir) else "", "", "### By exit", "", by_exit.to_markdown() if len(by_exit) else ""]
with open(os.path.join(OUT, "D1_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done")
