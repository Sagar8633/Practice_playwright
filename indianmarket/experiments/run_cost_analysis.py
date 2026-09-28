"""Gross -> costs -> net for every baseline run, break-even cost per trade, and a slippage sweep on the timeframes that were
positive gross. Writes research/cost_analysis.md and experiments/cost_tables.json."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO

R = json.load(open(os.path.join(ROOT, "backtests", "baseline_metrics.json")))["runs"]
OUT = {"gross_to_net": [], "slippage": []}
L = ["# Cost analysis\n", "## Assumptions\n", CO.describe(), "\nSpread and slippage are applied inside the engine at every fill (entry, stop, market exit); statutory charges and brokerage are added per round trip from the actual notional of each trade. "
     "Charges are the rates in force since 1 Oct 2024 (STT 0.02% on the sell side) applied to the whole 2022-2026 window, i.e. conservative for 2022-24. Slippage of 0.5 pt (NIFTY) and 1.5 pts (BANKNIFTY) per side "
     "is what a market or stop order in the front-month future pays in normal conditions; scenario C triples it for fast markets. Nothing here models the futures basis or rollover.\n",
     "## Gross -> costs -> net (points per unit, 2022-01-03 to 2026-09-26)\n",
     "'exec cost' = spread + slippage as it changed the fills (gross A minus B before charges); 'charges' = statutory + brokerage of scenario B. 'break-even cost/trade' = gross A points divided by trades: the all-in cost per round trip the strategy can afford before it is flat.\n"]
for instr in C.INSTRUMENTS:
    for cfg in C.CONFIGS:
        L.append(f"\n### {CO.INSTR[instr]['name']}: {cfg}\n")
        rows = []
        for tf in C.TFS:
            ka = f"{instr}|{cfg}|{C.TF_NAME[tf]}|A"; kb = f"{instr}|{cfg}|{C.TF_NAME[tf]}|B"; kc = f"{instr}|{cfg}|{C.TF_NAME[tf]}|C"
            if ka not in R: continue
            a = R[ka]["metrics"]; b = R[kb]["metrics"]; c = R[kc]["metrics"]
            exec_cost = a["net_pts"] - b["gross_pts"]; charges = b["fees_pts"]
            rows.append({"TF": C.TF_NAME[tf], "trades A/B": f"{a['trades']}/{b['trades']}", "gross A": a["net_pts"], "exec cost": round(exec_cost, 1), "charges": round(charges, 1), "net B": b["net_pts"], "net C": c["net_pts"],
                         "cost/trade B": round((exec_cost + charges) / max(1, b["trades"]), 2), "break-even cost/trade": round(a["net_pts"] / max(1, a["trades"]), 2),
                         "costs % of gross profit": round(100.0 * (exec_cost + charges) / max(1e-9, b["gross_profit_pts"] + charges), 1), "PF A": a["pf"], "PF B": b["pf"], "PF C": c["pf"]})
            OUT["gross_to_net"].append({"instrument": instr, "config": cfg, "tf": C.TF_NAME[tf], **rows[-1]})
        L.append(C.md_table(pd.DataFrame(rows)))

# ---------------------------------------------------------------- slippage sensitivity on the gross-positive timeframes with at least 100 trades
L.append("\n## Slippage sensitivity (scenario B charges kept, slippage per side varied; points per unit)\n")
for instr in C.INSTRUMENTS:
    slips = (0.0, 0.5, 1.0, 2.0, 3.0) if instr == "nifty50" else (0.0, 1.5, 3.0, 5.0, 8.0)
    cand = [(cfg, tf) for cfg in C.CONFIGS for tf in C.TFS if f"{instr}|{cfg}|{C.TF_NAME[tf]}|A" in R and R[f"{instr}|{cfg}|{C.TF_NAME[tf]}|A"]["metrics"]["net_pts"] > 0 and R[f"{instr}|{cfg}|{C.TF_NAME[tf]}|A"]["metrics"]["trades"] >= 100]
    rows = []
    for cfg, tf in cand:
        row = {"config": cfg, "TF": C.TF_NAME[tf]}
        for s in slips:
            tr, st = C.run(instr, tf, C.CONFIGS[cfg], "B", slippage_pts=round(s / CO.TICK, 6))
            row[f"slip {s}"] = round(float(tr.pts_net.sum()), 0)
        rows.append(row); OUT["slippage"].append({"instrument": instr, **row}); print(instr, row, flush=True)
    L.append(f"\n### {CO.INSTR[instr]['name']}\n"); L.append(C.md_table(pd.DataFrame(rows)) if rows else "no gross-positive timeframe with 100+ trades")
json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cost_tables.json"), "w"), indent=1)
open(os.path.join(ROOT, "research", "cost_analysis.md"), "w", encoding="utf-8").write("\n".join(L))
print("written research/cost_analysis.md")
