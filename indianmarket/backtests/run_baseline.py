"""Baseline: the strategy AS-IS (v1.00 rules, ticks as points) and the FINAL_H4 ATR-scaled exit stack, on NIFTY 50 and NIFTY BANK,
every timeframe from 1m to D1, cost scenarios A/B/C, plus D1 on the long daily history (2010-2026).

Writes backtests/<instr>/<config>_<tf>_<scenario>_trades.csv.gz, backtests/baseline_metrics.json and
research/timeframe_analysis.md; logs every run in research/experiment_log.csv.
Usage: python run_baseline.py [quick]   (quick = 15m/1h/D1 only)
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
TFS = (15, 60, 375) if QUICK else C.TFS
R = {"runs": {}, "daily_long": {}}
n = 0
for instr in C.INSTRUMENTS:
    os.makedirs(os.path.join(HERE, instr), exist_ok=True)
    for cfg_name, cfg in C.CONFIGS.items():
        for tf in TFS:
            for sc in CO.SCENARIOS:
                t0 = time.time(); tr, st = C.run(instr, tf, cfg, sc)
                key = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|{sc}"
                m = C.summarize(tr, instr, C.DATA_START, C.DATA_END); sm = C.split_metrics(tr, instr); yr = C.yearly(tr, instr)
                m["first_trade"] = str(tr.time_in.min())[:10] if len(tr) else ""; m["stats"] = {k: v for k, v in st.items() if isinstance(v, (int, float))}
                R["runs"][key] = {"metrics": m, "splits": sm, "yearly": yr.to_dict("records"), "verdict": C.classify(sm)}
                tr.to_csv(os.path.join(HERE, instr, f"{cfg_name}_{C.TF_NAME[tf]}_{sc}_trades.csv.gz"), index=False, compression="gzip")
                n += 1
                if sc == "B":
                    C.log_experiment(f"BASE-{n:03d}", instr, tf, cfg_name, cfg, "none (volume filter not evaluable on an index)", (C.DATA_START, C.DATA_END), sc, m, sm,
                                     "baseline", f"{C.classify(sm)}: net {m['net_pts']} pts after costs, PF {m['pf']}, OOS net {sm['OOS']['net_pts']}")
                print(f"{key:36} trades {m['trades']:5} net {m['net_pts']:9.1f} pts  PF {m['pf']:5.2f}  expR {m['exp_r']:7.3f}  DD {m['max_dd_pts']:8.1f}  OOS {sm['OOS']['net_pts']:8.1f}  {time.time()-t0:5.1f}s", flush=True)
    # D1 on the long daily history (one bar per session, stops tested against the day's range)
    for cfg_name, cfg in C.CONFIGS.items():
        for sc in ("A", "B"):
            tr, st = C.run(instr, 375, cfg, sc, start="2010-01-01", end=C.DATA_END, path=f"{instr}_daily")
            m = C.summarize(tr, instr, "2010-01-01", C.DATA_END)
            byy = tr.groupby(tr.time_out.dt.year)["pts_net"].agg(["size", "sum"]).round(1)
            R["daily_long"][f"{instr}|{cfg_name}|{sc}"] = {"metrics": m, "by_year": {int(k): [int(v["size"]), float(v["sum"])] for k, v in byy.iterrows()}}
            tr.to_csv(os.path.join(HERE, instr, f"{cfg_name}_D1long_{sc}_trades.csv.gz"), index=False, compression="gzip")
            if sc == "B":
                n += 1
                C.log_experiment(f"BASE-{n:03d}", instr, 375, cfg_name, cfg, "daily path 2010-2026", ("2010-01-01", C.DATA_END), sc, m, None, "baseline long D1",
                                 f"net {m['net_pts']} pts, PF {m['pf']}, positive years {int((byy['sum'] > 0).sum())}/{len(byy)}")
            print(f"{instr} {cfg_name} D1 2010-2026 {sc}: trades {m['trades']} net {m['net_pts']} PF {m['pf']} expR {m['exp_r']} years>0 {int((byy['sum'] > 0).sum())}/{len(byy)}", flush=True)
json.dump(R, open(os.path.join(HERE, "baseline_metrics.json"), "w"), indent=1, default=str)

# ---------------------------------------------------------------- research/timeframe_analysis.md
L = ["# Timeframe analysis: baseline runs (AS-IS and FINAL_H4), NIFTY 50 and NIFTY BANK, 2022-01-03 to 2026-09-26\n",
     "Money unit: index points per unit (1 futures lot = points x lot size; NIFTY 75, BANKNIFTY 35). Scenario A = gross, B = realistic costs, C = stress (see research/cost_analysis.md). "
     "Verdict rule (fixed before the runs): robust = positive expectancy and PF > 1 after B costs in TRAIN (2022-01..2024-08), VAL (2024-09..2025-08) and OOS (2025-09..2026-09) with >= 30 trades each; unstable = positive overall but not in every split; negative otherwise.\n",
     "AS-IS = v1.00 rules with 1 point = 1 tick (0.05): entry buffer 0.5 pt, break-even at +25 pts to +0.5 pt, swing protection from +25 pts with a 2.5-pt buffer, MA18 exit, swing stop. "
     "FINAL_H4 = the ATR-scaled exit stack selected in the gold study (BE 2 ATR, trailing from 5 ATR at 0.5 ATR distance, 0.1 ATR step, buffer 0, MA18 exit, swing stop). Both without the volume filter (an index has no volume).\n"]
for instr in C.INSTRUMENTS:
    for cfg_name in C.CONFIGS:
        L.append(f"\n## {CO.INSTR[instr]['name']}: {cfg_name}\n")
        rows = []
        for tf in TFS:
            a = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|A"]["metrics"]; b = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"]; c = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|C"]["metrics"]
            bm = b["metrics"]; sp = b["splits"]
            rows.append({"TF": C.TF_NAME[tf], "trades": bm["trades"], "gross A pts": a["net_pts"], "fees+slip pts": round(a["net_pts"] - bm["net_pts"], 1), "net B pts": bm["net_pts"], "net C pts": c["net_pts"],
                         "PF B": bm["pf"], "win %": bm["win_rate"], "exp pts": bm["exp_pts"], "exp R": bm["exp_r"], "median R": bm.get("median_r"), "max DD pts": bm["max_dd_pts"],
                         "Sharpe(m)": bm["sharpe_m"], "top10% share": bm.get("top10pct_share"), "TRAIN": sp["TRAIN"]["net_pts"], "VAL": sp["VAL"]["net_pts"], "OOS": sp["OOS"]["net_pts"], "verdict": b["verdict"]})
        L.append(C.md_table(pd.DataFrame(rows)))
        L.append("\nYear by year (net B points / trades):\n")
        yrows = []
        for tf in TFS:
            yr = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"]["yearly"]
            yrows.append({"TF": C.TF_NAME[tf], **{str(y["year"]): f"{y['net_pts']:.0f} / {y['trades']}" for y in yr}})
        L.append(C.md_table(pd.DataFrame(yrows)))
L.append("\n## D1 on the long daily history (2010-2026, one bar per session, stops tested against the day's range)\n")
rows = []
for k, v in R["daily_long"].items():
    instr, cfg_name, sc = k.split("|"); m = v["metrics"]; by = v["by_year"]
    rows.append({"instrument": CO.INSTR[instr]["name"], "config": cfg_name, "scenario": sc, "trades": m["trades"], "net pts": m["net_pts"], "PF": m["pf"], "exp R": m["exp_r"], "max DD pts": m["max_dd_pts"],
                 "years > 0": f"{sum(1 for y in by.values() if y[1] > 0)}/{len(by)}", "2022-26 net": round(sum(y[1] for yy, y in by.items() if yy >= 2022), 1)})
L.append(C.md_table(pd.DataFrame(rows)))
open(os.path.join(ROOT, "research", "timeframe_analysis.md"), "w", encoding="utf-8").write("\n".join(L))
print("written research/timeframe_analysis.md")
