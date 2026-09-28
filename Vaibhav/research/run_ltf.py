"""Sections 13-15: lower-timeframe noise study (M1 / M5 / M15) plus the M15 balance question.

Uses the untouched EA (strategy view, realistic costs) and small declared sweeps of the lower-timeframe protection knobs.
"""
import os, time
from dataclasses import replace
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "ltf"); os.makedirs(OUT, exist_ok=True)
BASE = os.path.join(C.RES, "baseline")
t0 = time.time()
res = {}
for tf in (1, 5, 15):
    name = C.TF_NAME[tf]
    tr = pd.read_csv(os.path.join(BASE, f"trades_{name}_6y_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    path = E.load_path("m1"); tfb = E.build_tf(path, tf); ind = E.indicators(tfb, E.Params(tf_minutes=tf))
    atr_med = float(np.nanmedian(np.where(ind["atr"] > 0, ind["atr"], np.nan)))
    spr = E._spread_array(path, E.Params(**C.COST["B_real"]))
    d = {"trades": int(len(tr)), "median_atr_usd": round(atr_med, 2), "median_spread_usd": round(float(np.median(spr)), 3),
         "spread_pct_of_atr": round(100 * float(np.median(spr)) / atr_med, 1), "spread_pct_of_median_mfe": round(100 * float(np.median(spr)) / max(float(tr["mfe_usd"].median()), 1e-9), 1),
         "median_mfe_usd": round(float(tr["mfe_usd"].median()), 2), "median_risk_usd": round(float(tr["risk_usd"].median()), 2),
         "share_held_le_2_bars": round(float((tr["bars_held"] <= 2).mean()), 3), "share_held_le_5_bars": round(float((tr["bars_held"] <= 5).mean()), 3), "median_hold_min": float(tr["hold_min"].median()),
         "share_MA18_exit": round(float((tr["exit_reason"] == "MA18_exit").mean()), 3), "share_MA18_exit_losing": round(float(((tr["exit_reason"] == "MA18_exit") & (tr["pnl"] < 0)).mean()), 3),
         "share_never_in_profit_ge_spread": round(float((tr["mfe_usd"] < float(np.median(spr))).mean()), 3)}
    # rapid reversals: next trade opposite direction within N bars of the previous exit
    tr = tr.sort_values("time_in").reset_index(drop=True)
    gap_bars = (tr["j_in"].shift(-1) - (tr["j_in"] + tr["bars_held"]))
    opp = (tr["side"].shift(-1) == -tr["side"])
    d["share_next_trade_opposite_within_5_bars"] = round(float((opp & (gap_bars <= 5)).mean()), 3)
    d["share_next_trade_same_dir_within_5_bars"] = round(float((~opp & (gap_bars <= 5)).mean()), 3)
    d["loss_after_reversal_within_5_bars"] = round(float(tr.loc[(opp & (gap_bars <= 5)).shift(1, fill_value=False), "pnl"].mean()), 3) if (opp & (gap_bars <= 5)).any() else None
    # cost sensitivity from the baseline A/B/C views
    import json
    S = json.load(open(os.path.join(BASE, "summary.json")))
    d["cost_sensitivity"] = {c: {"net": S[name]["6y"]["strategy"][c]["net_profit"], "pf": S[name]["6y"]["strategy"][c]["profit_factor"], "trades": S[name]["6y"]["strategy"][c]["trades"]} for c in ("A_low", "B_real", "C_stress")}
    gross = float(tr["gross_usd"].sum()); spread_cost = float((tr["spread_entry"] * E.CONTRACT * tr["lots"]).sum()); slip = float((tr["slip_usd"] * E.CONTRACT * tr["lots"]).sum())
    d["gross_before_spread_and_slippage"] = round(gross + spread_cost + slip, 2); d["spread_paid"] = round(spread_cost, 2); d["slippage_paid"] = round(slip, 2); d["swap_paid"] = round(float(tr["swap"].sum()), 2)
    # ---- sweeps: trailing distance x activation (fixed trailing, BE off, MA18 kept), time exit, volatility filter thresholds
    base_p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
    sweep = []
    for dist in (200, 300, 500, 800, 1200):
        for start in (0, 300, 500, 1000):
            p = replace(base_p, protection=4, be_enable=False, trail_start_pts=start, trail_dist_pts=dist, trail_step_pts=20)
            tr2, st = E.run(p); m = C.metrics_from_trades(tr2, 100000.0); mo = C.metrics_from_trades(C.slice_trades(tr2, *C.SPLITS["OOS"]), 100000.0)
            sweep.append({"trail_dist": dist, "trail_start": start, "trades": m["trades"], "net": m["net_profit"], "pf": m.get("profit_factor"), "expR": m.get("expectancy_r"), "giveback": m.get("giveback_avg"), "p2l": m.get("profit_to_loss_2usd"), "oos_net": mo["net_profit"], "oos_expR": mo.get("expectancy_r")})
            C.log_experiment("P13-ltf-trailing", f"trailing dist {dist} start {start} (no BE)", p, m, "B_real", "6y", exit_logic=C.exit_desc(p), oos_result=f"OOS net {mo['net_profit']}", conclusion="sweep")
    d["trailing_sweep"] = sweep
    te = []
    for n in (3, 5, 10, 20):
        p = replace(base_p, time_exit_bars=n)
        tr2, st = E.run(p); m = C.metrics_from_trades(tr2, 100000.0)
        te.append({"time_exit_bars": n, "trades": m["trades"], "net": m["net_profit"], "pf": m.get("profit_factor"), "expR": m.get("expectancy_r")})
        C.log_experiment("P13-ltf-timeexit", f"time exit {n} bars", p, m, "B_real", "6y", exit_logic=C.exit_desc(p), conclusion="sweep")
    d["time_exit_sweep"] = te
    vf = []
    for th in (0.8, 1.0, 1.2, 1.5, 2.0):
        p = replace(base_p, use_vol_filter=True, vol_filter_min=th)
        tr2, st = E.run(p); m = C.metrics_from_trades(tr2, 100000.0); mo = C.metrics_from_trades(C.slice_trades(tr2, *C.SPLITS["OOS"]), 100000.0); md = C.metrics_from_trades(C.slice_trades(tr2, *C.SPLITS["DEV"]), 100000.0)
        vf.append({"vol_min": th, "trades": m["trades"], "net": m["net_profit"], "pf": m.get("profit_factor"), "expR": m.get("expectancy_r"), "dev_expR": md.get("expectancy_r"), "oos_expR": mo.get("expectancy_r"), "oos_net": mo["net_profit"]})
        C.log_experiment("P13-ltf-volfilter", f"vol filter >= {th}", p, m, "B_real", "6y", filters=C.filter_desc(p), oos_result=f"OOS net {mo['net_profit']}", conclusion="sweep")
    d["vol_filter_sweep"] = vf
    res[name] = d
    print(name, {k: v for k, v in d.items() if not isinstance(v, (list, dict))}, f"({time.time()-t0:.0f}s)", flush=True)
C.save_json(res, "ltf/summary.json")

L = ["# Lower-timeframe noise study (M1 / M5 / M15)", "", "| item | M1 | M5 | M15 |", "|---|---:|---:|---:|"]
keys = ["trades", "median_atr_usd", "median_spread_usd", "spread_pct_of_atr", "median_mfe_usd", "spread_pct_of_median_mfe", "median_risk_usd", "median_hold_min", "share_held_le_2_bars", "share_held_le_5_bars",
        "share_MA18_exit", "share_MA18_exit_losing", "share_never_in_profit_ge_spread", "share_next_trade_opposite_within_5_bars", "share_next_trade_same_dir_within_5_bars", "loss_after_reversal_within_5_bars",
        "gross_before_spread_and_slippage", "spread_paid", "slippage_paid", "swap_paid"]
for k in keys:
    L.append(f"| {k} | " + " | ".join(str(res[n].get(k)) for n in ("M1", "M5", "M15")) + " |")
L += ["", "## Cost sensitivity (net $ / PF)", "", "| TF | A_low | B_real | C_stress |", "|---|---|---|---|"]
for n in ("M1", "M5", "M15"):
    cs = res[n]["cost_sensitivity"]
    L.append(f"| {n} | " + " | ".join(f"{cs[c]['net']} / {cs[c]['pf']}" for c in ("A_low", "B_real", "C_stress")) + " |")
for n in ("M1", "M5", "M15"):
    L += ["", f"## {n}: trailing distance x activation (fixed trailing, no BE, MA18 exit kept)", "", "| dist | start | trades | net $ | PF | exp R | giveback | P->L>$2 | OOS net | OOS exp R |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in res[n]["trailing_sweep"]:
        L.append(f"| {r['trail_dist']} | {r['trail_start']} | {r['trades']} | {r['net']} | {r['pf']} | {r['expR']} | {r['giveback']} | {r['p2l']} | {r['oos_net']} | {r['oos_expR']} |")
    L += ["", f"### {n}: time exit (close at the new bar if not in profit after N bars)", "", "| bars | trades | net $ | PF | exp R |", "|---:|---:|---:|---:|---:|"]
    for r in res[n]["time_exit_sweep"]:
        L.append(f"| {r['time_exit_bars']} | {r['trades']} | {r['net']} | {r['pf']} | {r['expR']} |")
    L += ["", f"### {n}: volatility filter threshold (ATR / SMA100(ATR) >= x)", "", "| x | trades | net $ | PF | exp R | DEV exp R | OOS exp R | OOS net |", "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in res[n]["vol_filter_sweep"]:
        L.append(f"| {r['vol_min']} | {r['trades']} | {r['net']} | {r['pf']} | {r['expR']} | {r['dev_expR']} | {r['oos_expR']} | {r['oos_net']} |")
with open(os.path.join(OUT, "LTF.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
