"""Build report.html: the visual version of FINAL_REPORT.md. Every chart is fed from the saved results; nothing is re-estimated.
Run after the whole research chain. Output: research/report.html (self-contained data; Chart.js loaded from cdnjs)."""
import json, os
from dataclasses import replace

import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

HERE = C.HERE; R = C.RES
TFS = ["M1", "M5", "M15", "D1"]
TFM = {"M1": 1, "M5": 5, "M15": 15, "D1": 1440}


def J(name):
    p = os.path.join(R, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def r2(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (np.isnan(x) or np.isinf(x)):
            return None
    except Exception:
        pass
    return round(float(x), 2)


def weekly(tr: pd.DataFrame, start_balance: float = 0.0, start=None, end=None, stop_at_ruin=False):
    """Cumulative P&L (or balance) sampled on a weekly grid, by exit time."""
    if len(tr) == 0:
        return {"t": [], "v": []}
    tr = tr.sort_values("time_out")
    cum = (start_balance + tr["pnl"].cumsum()).to_numpy()
    tout = tr["time_out"].to_numpy()
    a = pd.Timestamp(start) if start else tr["time_out"].min().normalize()
    b = pd.Timestamp(end) if end else tr["time_out"].max()
    grid = pd.date_range(a, b, freq="W")
    idx = np.searchsorted(tout, grid.to_numpy(), side="right") - 1
    vals = np.where(idx >= 0, cum[np.clip(idx, 0, None)], start_balance)
    t = [d.strftime("%Y-%m-%d") for d in grid]; v = [round(float(x), 2) for x in vals]
    if stop_at_ruin:
        for i, x in enumerate(v):
            if x <= 0:
                return {"t": t[: i + 1], "v": v[: i + 1], "ruined": t[i]}
    return {"t": t, "v": v}


D = {}
base = J("baseline/summary.json"); gb = J("trade_analysis/giveback.json"); p2l = J("trade_analysis/p2l_summary.json"); loss = J("trade_analysis/loss_summary.json")
filt = J("filters/summary.json"); sl = J("sl/summary.json"); ex = J("exits/summary.json"); ltf = J("ltf/summary.json"); wf = J("walkforward/summary.json"); acc = J("account/summary.json")
audit = json.load(open(os.path.join(HERE, "data", "audit.json"), encoding="utf-8")); spread = json.load(open(os.path.join(HERE, "data", "spread_model.json"), encoding="utf-8"))
nlog = sum(1 for _ in open(C.LOG, encoding="utf-8")) - 1 if os.path.exists(C.LOG) else 0

# ------------------------------------------------------------------ meta + verdict
D["meta"] = {"runs": nlog, "m1_start": audit["m1"]["start_server"][:10], "m1_end": audit["m1"]["end_server"][:10], "m1_bars": audit["m1"]["rows_final"], "h1_start": audit["h1"]["start_server"][:10],
             "xm_close_diff": audit["xm_vs_dukascopy"]["close_diff_median_abs"], "vol_agree": audit["xm_vs_dukascopy"]["volume_filter_agreement_M15"],
             "spread_hours": list(range(24)), "spread_2022": spread["model_points_by_year_hour"]["2022"], "spread_2026": spread["model_points_by_year_hour"]["2026"]}
verd = {"M1": ("Fails", "critical", "Zero gross edge; spread is 56% of the 1-minute ATR"), "M5": ("Fails", "critical", "Negative in every split; no filter, stop or exit turns it"),
        "M15": ("Break-even before costs", "serious", "PF 1.07 at a 25-pt spread, 0.92 with real costs; nothing robust"), "D1": ("Conditional", "warning", "One year (2025) carries 23 years; exit change is the real lever")}
D["verdict"] = []
for tf in TFS:
    m = base[tf]["6y"]["strategy"]["B_real"]
    D["verdict"].append({"tf": tf, "net": m["net_profit"], "pf": m.get("profit_factor"), "dd": m["max_dd_usd"], "trades": m["trades"], "win": m.get("win_rate"), "label": verd[tf][0], "level": verd[tf][1], "why": verd[tf][2]})

# ------------------------------------------------------------------ baseline
D["baseline"] = {"cost": {}, "equity": {}, "byYear": {}, "views": {}}
for tf in TFS:
    D["baseline"]["cost"][tf] = {c: base[tf]["6y"]["strategy"][c]["net_profit"] for c in ("A_low", "B_real", "C_stress")}
    tr = pd.read_csv(os.path.join(R, "baseline", f"trades_{tf}_6y_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    D["baseline"]["equity"][tf] = weekly(tr, 0.0, C.DATA_START, C.DATA_END)
    yt = base["by_year"].get(tf, {})
    D["baseline"]["byYear"][tf] = {"years": list(yt.keys()), "net": [v["net"] for v in yt.values()], "pf": [v["pf"] for v in yt.values()], "trades": [v["trades"] for v in yt.values()]}
    D["baseline"]["views"][tf] = {v: {k: base[tf]["6y"][v]["B_real"].get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "end_balance", "blocked_sl_pct", "ruin")} for v in ("strategy", "ea_200", "ea_200_nofilt")}
D["baseline"]["worst"] = {tf: base[tf]["6y"]["strategy"]["B_real_worst"]["net_profit"] for tf in TFS}

# ------------------------------------------------------------------ $200 paths
D["acct"] = {"paths": {}, "provided": {}}
for tf in TFS:
    tr = pd.read_csv(os.path.join(R, "baseline", f"trades_{tf}_6y_ea_200_nofilt_B_real.csv"), parse_dates=["time_in", "time_out"])
    D["acct"]["paths"][tf] = weekly(tr, 200.0, C.DATA_START, C.DATA_END, stop_at_ruin=True)
    m = base[tf]["6y"]["ea_200"]["B_real"]
    D["acct"]["provided"][tf] = {"taken": m["trades"], "blocked": m.get("blocked_sl_pct"), "net": m["net_profit"], "end": m["end_balance"]}
D["acct"]["rows"] = acc.get("per_timeframe", [])

# ------------------------------------------------------------------ D1 deep dive
pb = E.Params(tf_minutes=1440, path="h1", start=C.D1_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
CAND = dict(use_adx=True, adx_min=25.0, protection=2, prot_start_mode=0)
ATRV = dict(use_adx=True, adx_min=25.0, protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=2.0)
eq23 = {}; by23 = {}
for nm, kw in (("EA v1.00", {}), ("Candidate: ADX 25 + Chandelier", CAND), ("ADX 25 + ATR trail 2x", ATRV)):
    tr, st = E.run(replace(pb, **kw)); tr["year"] = tr["time_out"].dt.year
    eq23[nm] = weekly(tr, 0.0, C.D1_START, C.DATA_END)
    by23[nm] = tr.groupby("year")["pnl"].sum().round(2)
years23 = sorted(set().union(*[set(v.index) for v in by23.values()]))
D["d1"] = {"equity23": eq23, "byYear23": {"years": [int(y) for y in years23], "series": {nm: [float(v.get(y, 0.0)) for y in years23] for nm, v in by23.items()}}}
val = pd.read_csv(os.path.join(R, "d1_validation", "d1_validation_table.csv"))
vb = val[(val["cost"] == "B_real") & (val["period"].str.startswith("claim"))]
D["d1"]["claim"] = [{"config": r["config"].replace("_", " "), "trades": int(r["trades"]), "net": r2(r["net"]), "growth": r2(r["growth_x"]), "blocked": r2(r["blocked_sl_pct"])} for _, r in vb.iterrows()]
win = pd.read_csv(os.path.join(R, "baseline", "d1_window18m_23y_h1path.csv"))
D["d1"]["windows"] = {"start": win["start"].tolist(), "growth": win["growth_x"].round(2).tolist(), "net": win["net"].round(2).tolist()}
sc = base["D1_18month_window_scan"]["23y_h1path"]
D["d1"]["windowStats"] = {"windows": sc["windows"], "best": sc["best"]["growth_x"], "median": sc["median_growth_x"], "ge3": sc["share_windows_ge_3x"], "losing": sc["share_windows_losing"], "ruined": sc["share_windows_ruined"]}
ex23 = pd.read_csv(os.path.join(R, "d1_validation", "d1_exits_23y.csv"))
D["d1"]["exits23"] = ex23.to_dict("records")
c23 = pd.read_csv(os.path.join(R, "d1_validation", "d1_candidate_23y.csv"))
D["d1"]["cand23"] = c23.to_dict("records")
# candidate vs EA 2020-2026 on the M1 path
pm = E.Params(tf_minutes=1440, path="m1", start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
eq6 = {}; cand6 = {}
for nm, kw in (("EA v1.00", {}), ("Candidate: ADX 25 + Chandelier", CAND), ("ADX 25 + ATR trail 2x", ATRV)):
    tr, st = E.run(replace(pm, **kw))
    eq6[nm] = weekly(tr, 0.0, C.DATA_START, C.DATA_END)
    m = E.metrics(tr, st, 100000.0, E.months_between(C.DATA_START, C.DATA_END))
    cand6[nm] = {k: m.get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "win_rate", "expectancy_r", "avg_win", "avg_loss", "max_consec_losses", "giveback_avg", "profit_to_loss_2usd", "avg_hold_min", "median_risk_usd")}
    for nmx, (a, b) in C.SPLITS.items():
        ms = C.metrics_from_trades(C.slice_trades(tr, a, b), 100000.0)
        cand6[nm][nmx] = {"net": ms["net_profit"], "expR": ms.get("expectancy_r"), "trades": ms["trades"]}
D["d1"]["equity6"] = eq6; D["d1"]["cand6"] = cand6

# ------------------------------------------------------------------ giveback
D["gb"] = {"scatter": {}, "totals": [], "byExit": {}, "p2l": {}, "overall": {}}
for tf in ("M15", "D1"):
    t = pd.read_csv(os.path.join(R, "trade_analysis", f"trade_level_{tf}.csv"))
    D["gb"]["scatter"][tf] = {"be": [[r2(x), r2(y)] for x, y in zip(t.loc[t["exit_reason"] == "SL_breakeven", "mfe_usd"], t.loc[t["exit_reason"] == "SL_breakeven", "pnl"])],
                              "other": [[r2(x), r2(y)] for x, y in zip(t.loc[t["exit_reason"] != "SL_breakeven", "mfe_usd"], t.loc[t["exit_reason"] != "SL_breakeven", "pnl"])]}
for tf in TFS:
    o = gb[tf]["overall"]
    D["gb"]["totals"].append({"tf": tf, "mfe": o["total_mfe"], "realized": o["total_realized"], "avg": o["avg_giveback"], "median_pct": o["median_giveback_pct"], "worst": o["worst_giveback"], "share_ge1": o["share_trades_with_mfe_ge_1usd"]})
    D["gb"]["byExit"][tf] = [{"exit": k, **v} for k, v in gb[tf]["exit_reason"].items()]
    D["gb"]["p2l"][tf] = [{"th": k, "trades": v["trades"], "share": v["share_of_losers"], "loss": v["realized_loss"], "given": v["unrealized_profit_given_up"], "cont": v["share_price_continued_favourably_after_exit_ge_1R"]} for k, v in p2l[tf].items()]
D["loss"] = {tf: [{"cat": k, "trades": v["trades"], "loss": v["loss"], "share": v["share_of_total_loss_pct"]} for k, v in loss[tf]["categories"].items()] for tf in TFS}

# ------------------------------------------------------------------ costs + LTF sweeps
D["ltf"] = {}
for tf in ("M1", "M5", "M15"):
    d = ltf[tf]
    D["ltf"][tf] = {"gross": d["gross_before_spread_and_slippage"], "spread": -d["spread_paid"], "slip": -d["slippage_paid"], "swap": d["swap_paid"], "net": base[tf]["6y"]["strategy"]["B_real"]["net_profit"],
                    "spread_pct_atr": d["spread_pct_of_atr"], "spread_pct_mfe": d["spread_pct_of_median_mfe"], "atr": d["median_atr_usd"], "mfe": d["median_mfe_usd"], "hold": d["median_hold_min"], "ma_exit": d["share_MA18_exit"], "never": d["share_never_in_profit_ge_spread"],
                    "trail": d["trailing_sweep"], "timeExit": d["time_exit_sweep"], "vol": d["vol_filter_sweep"]}

# ------------------------------------------------------------------ filters / stops / exits tables
def lab_rows(summary, tf, skip=("BASE", "COMBOS")):
    b = summary[tf]["BASE"]["metrics"] if "BASE" in summary[tf] else None
    rows = []
    for v, r in summary[tf].items():
        if v in skip:
            continue
        m = r["metrics"]
        rows.append({"name": v, "trades": m["ALL"]["trades"], "net": m["ALL"]["net_profit"], "pf": m["ALL"].get("profit_factor"), "dd": m["ALL"]["max_dd_usd"], "expR": m["ALL"].get("expectancy_r"),
                     "dev": m["DEV"].get("expectancy_r"), "val": m["VAL"].get("expectancy_r"), "oos": m["OOS"].get("expectancy_r"), "cls": r.get("class", ""), "risk": r.get("median_risk_usd"), "slhit": m["ALL"].get("sl_hit_rate"),
                     "giveback": m["ALL"].get("giveback_avg"), "p2l": m["ALL"].get("profit_to_loss_2usd"), "win": m["ALL"].get("win_rate")})
    basem = None
    if b:
        basem = {"trades": b["ALL"]["trades"], "net": b["ALL"]["net_profit"], "pf": b["ALL"].get("profit_factor"), "dev": b["DEV"].get("expectancy_r"), "val": b["VAL"].get("expectancy_r"), "oos": b["OOS"].get("expectancy_r"), "expR": b["ALL"].get("expectancy_r")}
    return rows, basem


D["filters"] = {}; D["sl"] = {}; D["exits"] = {}
for tf in TFS:
    rows, bm = lab_rows(filt, tf); D["filters"][tf] = {"rows": rows, "base": bm, "combos": filt[tf].get("COMBOS", [])}
    rows, _ = lab_rows(sl["variants"], tf, skip=())
    bm = next((r for r in rows if r["name"].startswith("A ")), None)
    D["sl"][tf] = {"rows": rows, "base": {"dev": bm["dev"], "val": bm["val"], "oos": bm["oos"], "net": bm["net"], "expR": bm["expR"]} if bm else None, "existing": sl["existing"][tf]}
    rows, _ = lab_rows(ex, tf, skip=())
    bm = next((r for r in rows if r["name"].startswith("E01")), None)
    D["exits"][tf] = {"rows": rows, "base": {"dev": bm["dev"], "val": bm["val"], "oos": bm["oos"], "net": bm["net"], "expR": bm["expR"]} if bm else None}

# ------------------------------------------------------------------ walk-forward
D["wf"] = {}
for tf in TFS:
    Rw = wf.get(tf, {})
    a = Rw.get("audit", {})
    folds = []
    for f in Rw.get("folds", []):
        tb = f.get("train_best", {}) or {}; sel = f.get("selected")
        folds.append({"fold": f["fold"], "train": f"{f['train'][0][:7]} to {f['train'][1][:7]}", "test": f"{f['test'][0][:7]} to {f['test'][1][:7]}", "best": tb.get("config"), "trainR": tb.get("train_expR"), "valR": tb.get("val_expR"), "testR": tb.get("test_expR"),
                      "passes": f.get("train_best_passes_val"), "selected": sel["config"] if sel else None, "selNet": sel["test_net"] if sel else None, "eaNet": f["ea_untouched"]["test_net"], "sharePos": f["share_positive_test"]})
    D["wf"][tf] = {"configs": a.get("configs_tested"), "pos3": a.get("positive_all_three_splits"), "dev": a.get("share_positive_dev"), "val": a.get("share_positive_val"), "oos": a.get("share_positive_oos"), "best": a.get("best_in_sample"), "folds": folds,
                   "robust": a.get("robust_candidates", [])[:8], "candidate": Rw.get("candidate"), "mc_ea": Rw.get("ea_monte_carlo_200")}

# ------------------------------------------------------------------ write
html = open(os.path.join(HERE, "report_template.html"), encoding="utf-8").read()
out = html.replace("__DATA__", json.dumps(D, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else (o.item() if hasattr(o, "item") else str(o))))
with open(os.path.join(HERE, "report.html"), "w", encoding="utf-8") as f:
    f.write(out)
print("report.html written", len(out) // 1024, "KB")
