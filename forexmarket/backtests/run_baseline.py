"""Baseline for every instrument with prepared data: AS-IS and FINAL_H4 on 1m..D1, scenarios A/B/C, plus D1 on the long hourly path
(2015-2026). Usage: python run_baseline.py [instrument ...] [quick]. Writes backtests/<instr>/<cfg>_<tf>_<sc>_trades.csv.gz,
backtests/baseline_metrics.json (merged per instrument) and research/timeframe_analysis.md."""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if a != "quick"]; QUICK = "quick" in sys.argv
INSTR = args or [i for i in C.INSTRUMENTS if os.path.exists(os.path.join(ROOT, "data", i, "m1_server.npz")) or os.path.exists(os.path.join(ROOT, "data", i, "m15_server.npz"))]
TFS = (15, 60, 1440) if QUICK else C.TFS


def path_for(instr, tf):
    """Minute path when the instrument has one (all timeframes); otherwise XM's 15-minute path for 15m and up (1m-10m untestable)."""
    aud = os.path.join(ROOT, "data", instr, "audit.json"); months = json.load(open(aud)).get("m1_months_present", 0) if os.path.exists(aud) else 0
    if os.path.exists(os.path.join(ROOT, "data", instr, "m1_server.npz")) and months >= 48:
        return instr, C.DATA_START
    if tf >= 15 and os.path.exists(os.path.join(ROOT, "data", instr, "m15_server.npz")):
        t0 = pd.Timestamp(np.load(os.path.join(ROOT, "data", instr, "m15_server.npz"))["t"][0], unit="s")
        return instr + "_m15", str(max(t0.normalize(), pd.Timestamp(C.DATA_START)))[:10]
    return None, None
MF = os.path.join(HERE, "baseline_metrics.json"); R = json.load(open(MF)) if os.path.exists(MF) else {"runs": {}, "daily_long": {}}
n = 0
for instr in INSTR:
    os.makedirs(os.path.join(HERE, instr), exist_ok=True); E._PATH_CACHE.clear(); E._TF_CACHE.clear(); E._IND_CACHE.clear()
    for cfg_name, cfg in C.CONFIGS.items():
        for tf in TFS:
            pth, pstart = path_for(instr, tf)
            if pth is None:
                continue
            for sc in ("A", "B", "C"):
                t0 = time.time(); tr, st = C.run(instr, tf, cfg, sc, start=pstart, path=pth); key = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|{sc}"
                m = C.summarize(tr, instr, pstart, C.DATA_END); sm = C.split_metrics(tr, instr); yr = C.yearly(tr, instr)
                m["first_trade"] = str(tr.time_in.min())[:10] if len(tr) else ""; m["path"] = pth; m["path_start"] = pstart; m["stats"] = {k: v for k, v in st.items() if isinstance(v, (int, float))}
                R["runs"][key] = {"metrics": m, "splits": sm, "yearly": yr.to_dict("records"), "verdict": C.classify(sm)}
                tr.to_csv(os.path.join(HERE, instr, f"{cfg_name}_{C.TF_NAME[tf]}_{sc}_trades.csv.gz"), index=False, compression="gzip"); n += 1
                if sc == "B":
                    C.log_experiment(f"BASE-{instr}-{n:03d}", instr, tf, cfg_name, cfg, "none", (C.DATA_START, C.DATA_END), sc, m, sm, "baseline", f"{C.classify(sm)}: net {m['net_usd']} USD/0.01 lot, PF {m['pf']}, OOS {sm['OOS']['net_usd']}")
                print(f"{key:34} trades {m['trades']:5} net ${m['net_usd']:9.2f} PF {m['pf']:5.2f} expR {m['exp_r']:7.3f} DD ${m['max_dd_usd']:8.2f} OOS ${sm['OOS']['net_usd']:8.2f} {time.time()-t0:5.1f}s", flush=True)
    if os.path.exists(os.path.join(ROOT, "data", instr, "h1_server.npz")):
        for cfg_name, cfg in C.CONFIGS.items():
            for sc in ("A", "B"):
                tr, st = C.run(instr, 1440, cfg, sc, start="2015-01-01", end=C.DATA_END, path=instr + "_h1")
                m = C.summarize(tr, instr, "2015-01-01", C.DATA_END); byy = (tr.groupby(tr.time_out.dt.year)["usd"].agg(["size", "sum"]).round(2) if len(tr) else pd.DataFrame(columns=["size", "sum"]))
                R["daily_long"][f"{instr}|{cfg_name}|{sc}"] = {"metrics": m, "by_year": {int(k): [int(v["size"]), float(v["sum"])] for k, v in byy.iterrows()}}
                tr.to_csv(os.path.join(HERE, instr, f"{cfg_name}_D1long_{sc}_trades.csv.gz"), index=False, compression="gzip")
                print(f"{instr} {cfg_name} D1 2015-2026 {sc}: trades {m['trades']} net ${m['net_usd']} PF {m['pf']} expR {m['exp_r']} years>0 {int((byy['sum'] > 0).sum())}/{len(byy)}", flush=True)
    json.dump(R, open(MF, "w"), indent=1, default=str)

# ---------------------------------------------------------------- research/timeframe_analysis.md (all instruments present in the metrics file)
L = ["# Timeframe analysis: baseline runs, all instruments (Sep 2021 to Sep 2026, XM Global MT5 specifications)\n",
     "Money unit: USD per 0.01 lot (XM minimum lot). Scenario A gross (no spread, slippage or swap), B realistic (XM spread by year and server hour from XM's own bars, slippage per side, swap), C stress (1.5x spread, 3x slippage). "
     "Verdict rule (fixed before the runs): robust = positive expectancy and PF > 1 after B costs in TRAIN (2021-09..2024-08), VAL (2024-09..2025-08) and OOS (2025-09..2026-09) with >= 30 trades each; unstable = positive overall but not in every split; negative otherwise.\n",
     "AS-IS = v1.00 rules with MT5 points of each symbol (buffer 10 pts, break-even 500/10 pts, swing protection from 500 pts with a 50-pt buffer, volume filter on). FINAL_H4 = the ATR-scaled exit stack selected on gold (BE 2 ATR, trailing from 5 ATR at 0.5 ATR, step 0.1 ATR, buffer 0, volume filter on).\n"]
for instr in [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in R["runs"])]:
    for cfg_name in C.CONFIGS:
        L.append(f"\n## {C.NAME[instr]}: {cfg_name}\n"); rows = []
        for tf in C.TFS:
            kb = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"
            if kb not in R["runs"]: continue
            a = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|A"]["metrics"]; b = R["runs"][kb]; c = R["runs"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|C"]["metrics"]; bm = b["metrics"]; sp = b["splits"]
            rows.append({"TF": C.TF_NAME[tf], "trades": bm["trades"], "gross A $": a["net_usd"], "net B $": bm["net_usd"], "net C $": c["net_usd"], "PF B": bm["pf"], "win %": bm["win_rate"], "exp $": bm["exp_usd"], "exp R": bm["exp_r"],
                         "median R": bm.get("median_r"), "max DD $": bm["max_dd_usd"], "Sharpe(m)": bm["sharpe_m"], "top-5 share %": bm.get("top5_trades_share"), "TRAIN": sp["TRAIN"]["net_usd"], "VAL": sp["VAL"]["net_usd"], "OOS": sp["OOS"]["net_usd"], "verdict": b["verdict"]})
        L.append(C.md_table(pd.DataFrame(rows)))
        L.append("\nYear by year (net B USD / trades):\n"); yrows = []
        for tf in C.TFS:
            kb = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"
            if kb in R["runs"]: yrows.append({"TF": C.TF_NAME[tf], **{str(y["year"]): f"{y['net_usd']:.0f} / {y['trades']}" for y in R["runs"][kb]["yearly"]}})
        L.append(C.md_table(pd.DataFrame(yrows)))
L.append("\n## D1 on the long hourly path (2015-2026; Dukascopy H1 before Sep 2021, M1 after; stops tested against the hour's range)\n"); rows = []
for k, v in R["daily_long"].items():
    instr, cfg_name, sc = k.split("|"); m = v["metrics"]; by = v["by_year"]
    rows.append({"instrument": C.NAME[instr], "config": cfg_name, "scenario": sc, "trades": m["trades"], "net $": m["net_usd"], "PF": m["pf"], "exp R": m["exp_r"], "max DD $": m["max_dd_usd"], "years > 0": f"{sum(1 for y in by.values() if y[1] > 0)}/{len(by)}",
                 "2021-26 net $": round(sum(y[1] for yy, y in by.items() if int(yy) >= 2021), 2)})
L.append(C.md_table(pd.DataFrame(rows)) if rows else "none yet")
open(os.path.join(ROOT, "research", "timeframe_analysis.md"), "w", encoding="utf-8").write("\n".join(L)); print("written research/timeframe_analysis.md")
