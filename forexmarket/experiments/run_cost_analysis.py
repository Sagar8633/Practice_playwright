"""Gross -> costs -> net per instrument and timeframe, spread/swap/slippage decomposition, and a slippage sweep on the
gross-positive timeframes. Writes research/cost_analysis.md and experiments/cost_tables.json."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

R = json.load(open(os.path.join(ROOT, "backtests", "baseline_metrics.json")))["runs"]
INSTR = [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in R)]
models = json.load(open(os.path.join(ROOT, "data", "xm", "spread_models.json")))
OUT = {"gross_to_net": [], "slippage": [], "spreads": []}
L = ["# Cost analysis\n", "## Assumptions\n",
     "Spread: XM's own spread, the median of XM's H1 bars by year and server hour (2015-2026, every hour of every year); applied at every fill as ask = bid + spread. Oil (OILCash) reports a zero spread on H1 bars, so a flat 4 points (its M15/M1 medians) is used. Slippage: per side, in points (B / C): "
     + ", ".join(f"{C.NAME[i]} {C.SLIP[i][0]}/{C.SLIP[i][1]}" for i in C.INSTRUMENTS) + ". Swap: XM points per night from the symbol specification, triple on Wednesday (Bitcoin: every calendar day, no triple; Oil CFD: none). "
     "Scenario C multiplies the spread by 1.5. Money: USD per 0.01 lot; USD-base pairs converted at the exit price.\n", "## Spread model (points, 2026 median by server hour and yearly medians)\n"]
rows = []
for i in INSTR:
    m = models.get(i, {}); sp = C.specs(i)
    rows.append({"instrument": C.NAME[i], "point": sp["point"], "contract": sp["contract"], "2026 median spread pts": round(float(np.median(m.get("2026", [np.nan]))), 1), "= USD per 0.01 lot": round(float(np.median(m.get("2026", [0]))) * C.usd_per_point_001(i), 3),
                 "min hour pts": round(float(np.min(m.get("2026", [np.nan]))), 1), "max hour pts": round(float(np.max(m.get("2026", [np.nan]))), 1), "swap L/S pts": f"{sp['swap_long_pts']}/{sp['swap_short_pts']}", "swap L per night $/0.01": round(sp["swap_long_pts"] * C.usd_per_point_001(i), 3)})
    OUT["spreads"].append(rows[-1])
L.append(C.md_table(pd.DataFrame(rows), "{:,.3f}"))
L.append("\n## Gross -> costs -> net (USD per 0.01 lot, Sep 2021 to Sep 2026)\n'exec cost' = spread + slippage as it changed the fills (A minus B before swap); 'swap' = scenario B swap; 'break-even cost/trade' = gross A divided by trades.\n")
for i in INSTR:
    for cfg in C.CONFIGS:
        L.append(f"\n### {C.NAME[i]}: {cfg}\n"); rows = []
        for tf in C.TFS:
            ka, kb, kc = (f"{i}|{cfg}|{C.TF_NAME[tf]}|{s}" for s in "ABC")
            if ka not in R: continue
            a = R[ka]["metrics"]; b = R[kb]["metrics"]; c = R[kc]["metrics"]
            exec_cost = a["net_usd"] - (b["net_usd"] - b["swap_usd"]); swap = -b["swap_usd"]
            rows.append({"TF": C.TF_NAME[tf], "trades": b["trades"], "gross A $": a["net_usd"], "exec cost $": round(exec_cost, 2), "swap $": round(swap, 2), "net B $": b["net_usd"], "net C $": c["net_usd"], "cost/trade B $": round((exec_cost + swap) / max(1, b["trades"]), 3),
                         "break-even cost/trade $": round(a["net_usd"] / max(1, a["trades"]), 3), "costs % of gross profit": round(100.0 * (exec_cost + swap) / max(1e-9, b["gross_profit_usd"] + exec_cost + swap), 1), "PF A": a["pf"], "PF B": b["pf"], "PF C": c["pf"]})
            OUT["gross_to_net"].append({"instrument": i, "config": cfg, "tf": C.TF_NAME[tf], **rows[-1]})
        L.append(C.md_table(pd.DataFrame(rows), "{:,.3f}"))
L.append("\n## Slippage sensitivity (B spread and swap kept, slippage per side varied; USD per 0.01 lot)\n")
for i in INSTR:
    base_slip = C.SLIP[i][0]; slips = [0, base_slip, 2 * base_slip, 4 * base_slip, 8 * base_slip]
    cand = [(cfg, tf) for cfg in C.CONFIGS for tf in C.TFS if f"{i}|{cfg}|{C.TF_NAME[tf]}|A" in R and R[f"{i}|{cfg}|{C.TF_NAME[tf]}|A"]["metrics"]["net_usd"] > 0 and R[f"{i}|{cfg}|{C.TF_NAME[tf]}|A"]["metrics"]["trades"] >= 100]
    rows = []
    for cfg, tf in cand:
        row = {"config": cfg, "TF": C.TF_NAME[tf]}
        for s_ in slips:
            tr, st = C.run(i, tf, C.CONFIGS[cfg], "B", slippage_pts=float(s_)); row[f"slip {s_} pts"] = round(float(tr.usd.sum()), 2)
        rows.append(row); OUT["slippage"].append({"instrument": i, **row}); print(i, row, flush=True)
    E._IND_CACHE.clear()
    L.append(f"\n### {C.NAME[i]}\n"); L.append(C.md_table(pd.DataFrame(rows)) if rows else "no gross-positive timeframe with 100+ trades")
json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cost_tables.json"), "w"), indent=1)
open(os.path.join(ROOT, "research", "cost_analysis.md"), "w", encoding="utf-8").write("\n".join(L)); print("written research/cost_analysis.md")
