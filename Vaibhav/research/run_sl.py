"""PHASE 3 (STEP 11): stop-loss research. Original entries and the original exit stack (BE 500/10, swing protection
after 500, MA18 close exit) are kept; only the initial stop changes. Strategy view, realistic costs, DEV/VAL/OOS slices.

Part 1 describes the existing swing stop from the baseline trades (distance, hit rate, loss distribution, MFE before a
stop-out, MAE before a win). Part 2 tests the alternatives A-F. Robustness = consistency across the three splits and
across neighbouring parameter values, not the best single number.
"""
import os, time
from dataclasses import replace
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C
from common import evaluate, classify, KEYS

OUT = os.path.join(C.RES, "sl"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
TFS = [1, 5, 15, 1440]
VARIANTS = {
    "A original swing SL (strength 2)": dict(),
    "B ATR 1.0x": dict(sl_mode=1, sl_atr_mult=1.0), "B ATR 1.5x": dict(sl_mode=1, sl_atr_mult=1.5), "B ATR 2.0x": dict(sl_mode=1, sl_atr_mult=2.0),
    "B ATR 2.5x": dict(sl_mode=1, sl_atr_mult=2.5), "B ATR 3.0x": dict(sl_mode=1, sl_atr_mult=3.0),
    "C swing strength 1": dict(swing_strength=1), "C swing strength 3": dict(swing_strength=3),
    "C swing - 0.5 ATR buffer": dict(sl_mode=7, sl_atr_mult=0.5), "C swing - 0.25 ATR buffer": dict(sl_mode=7, sl_atr_mult=0.25),
    "C swing capped 1000 pts": dict(sl_mode=2, sl_cap_pts=1000), "C swing capped 1500 pts (v13)": dict(sl_mode=2, sl_cap_pts=1500), "C swing capped 2000 pts": dict(sl_mode=2, sl_cap_pts=2000),
    "D MA18 - 0 pts": dict(sl_mode=5, swing_buffer_pts=0), "D MA18 - 50 pts": dict(sl_mode=5, swing_buffer_pts=50),
    "E swing clamped [0.5, 3] ATR": dict(sl_mode=4, sl_floor_atr=0.5, sl_atr_mult=3.0), "E swing clamped [1, 4] ATR": dict(sl_mode=4, sl_floor_atr=1.0, sl_atr_mult=4.0),
    "E swing clamped [0.5, 2] ATR": dict(sl_mode=4, sl_floor_atr=0.5, sl_atr_mult=2.0),
    "F swing with 0.5 ATR floor": dict(sl_mode=3, sl_floor_atr=0.5), "F swing with 1.0 ATR floor": dict(sl_mode=3, sl_floor_atr=1.0),
    "F min stop 150 pts (v13 MinStopPoints)": dict(min_sl_pts=150), "F min stop 300 pts": dict(min_sl_pts=300),
}


def describe_existing(tr: pd.DataFrame, tfname: str) -> dict:
    if len(tr) == 0:
        return {}
    d = {"trades": int(len(tr))}
    dist_pts = (tr["risk_usd"] / (tr["lots"] * E.CONTRACT) / E.POINT)
    d["sl_distance_pts"] = {"mean": round(float(dist_pts.mean()), 0), "median": round(float(dist_pts.median()), 0), "p10": round(float(dist_pts.quantile(0.1)), 0), "p90": round(float(dist_pts.quantile(0.9)), 0), "max": round(float(dist_pts.max()), 0)}
    d["sl_distance_usd_per_0.01lot"] = {"mean": round(float(tr["risk_usd"].mean()), 2), "median": round(float(tr["risk_usd"].median()), 2), "p90": round(float(tr["risk_usd"].quantile(0.9)), 2), "max": round(float(tr["risk_usd"].max()), 2)}
    atr_r = tr["risk_usd"] / (tr["atr_entry"] * E.CONTRACT * tr["lots"]).replace(0, np.nan)
    d["sl_distance_in_atr"] = {"median": round(float(atr_r.median()), 2), "p10": round(float(atr_r.quantile(0.1)), 2), "p90": round(float(atr_r.quantile(0.9)), 2)}
    d["sl_hit_rate_pct"] = round(100 * float((tr["reason"] == 1).mean()), 1)
    d["initial_sl_share_of_losses_pct"] = round(100 * float(tr.loc[tr["reason"] == 1, "pnl"].sum() / min(tr.loc[tr["pnl"] < 0, "pnl"].sum(), -1e-9)), 1)
    losses = tr.loc[tr["pnl"] < 0, "pnl"]
    d["loss_distribution"] = {"avg": round(float(losses.mean()), 2), "median": round(float(losses.median()), 2), "p90": round(float(losses.quantile(0.1)), 2), "worst": round(float(losses.min()), 2), "count": int(len(losses))}
    d["avg_loss_r"] = round(float(tr.loc[tr["pnl"] < 0, "r"].mean()), 3)
    sl_hit = tr[tr["reason"] == 1]
    d["mfe_before_sl_hit"] = {"avg_usd": round(float(sl_hit["mfe_usd"].mean()), 2), "avg_r": round(float(sl_hit["mfe_r"].mean()), 3), "share_ge_0.5R": round(float((sl_hit["mfe_r"] >= 0.5).mean()), 3), "share_ge_1R": round(float((sl_hit["mfe_r"] >= 1).mean()), 3)} if len(sl_hit) else {}
    win = tr[tr["pnl"] > 0]
    d["mae_before_win"] = {"avg_usd": round(float(win["mae_usd"].mean()), 2), "median_r": round(float(win["mae_r"].median()), 3), "p90_r": round(float(win["mae_r"].quantile(0.9)), 3), "share_mae_gt_0.5R": round(float((win["mae_r"] > 0.5).mean()), 3),
                          "note": "p90 MAE/R of winners = the stop fraction that would still keep 90% of today's winners"} if len(win) else {}
    return d


results = {}; rows = []; existing = {}
for tf in TFS:
    name = C.TF_NAME[tf]
    base_p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
    results[name] = {}
    base = None
    for vname, kw in VARIANTS.items():
        p = replace(base_p, **kw)
        var, tr = evaluate(p)
        if base is None:
            base = var; existing[name] = describe_existing(tr, name)
        cls = "base" if vname.startswith("A ") else classify(base, var)
        med_risk = float(tr["risk_usd"].median()) if len(tr) else None
        results[name][vname] = {"metrics": var, "class": cls, "params": kw, "median_risk_usd": med_risk, "sl_hit_rate": var["ALL"].get("sl_hit_rate")}
        for k, m in var.items():
            rows.append({"tf": name, "variant": vname, "period": k, **{kk: m.get(kk) for kk in KEYS}, "sl_hit_rate": m.get("sl_hit_rate"), "avg_loss": m.get("avg_loss"), "median_risk_usd": med_risk, "class": cls})
        C.log_experiment("P3-stoploss", vname, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                         oos_result=f"OOS net {var['OOS']['net_profit']} PF {var['OOS'].get('profit_factor')} expR {var['OOS'].get('expectancy_r')}", conclusion=cls)
        a = var["ALL"]
        print(f"{name:3} {vname:40} trades {a['trades']:6} net {a['net_profit']:10.2f} PF {a.get('profit_factor')!s:>6} expR {a.get('expectancy_r')!s:>7} SLhit {a.get('sl_hit_rate')!s:>5} risk {med_risk!s:>7} | DEV {var['DEV'].get('expectancy_r')!s:>7} VAL {var['VAL'].get('expectancy_r')!s:>7} OOS {var['OOS'].get('expectancy_r')!s:>7} -> {cls} ({time.time()-t0:.0f}s)", flush=True)

pd.DataFrame(rows).to_csv(os.path.join(OUT, "sl_table.csv"), index=False)
C.save_json({"existing": existing, "variants": results}, "sl/summary.json")

L = ["# Phase 3: stop-loss research (original entries and exit stack kept)", "", "Strategy view, 0.01 lot, realistic costs; DEV / VAL / OOS expectancy in R shown for robustness.", ""]
for name in results:
    ex = existing[name]
    L += [f"## {name}", "", "### The existing swing stop", ""]
    if ex:
        L += [f"- Distance: median {ex['sl_distance_pts']['median']:.0f} pts (${ex['sl_distance_usd_per_0.01lot']['median']} per 0.01 lot), p10-p90 {ex['sl_distance_pts']['p10']:.0f}-{ex['sl_distance_pts']['p90']:.0f} pts, max {ex['sl_distance_pts']['max']:.0f}; in ATR: median {ex['sl_distance_in_atr']['median']} (p10 {ex['sl_distance_in_atr']['p10']}, p90 {ex['sl_distance_in_atr']['p90']}).",
              f"- Initial-stop hit rate {ex['sl_hit_rate_pct']}% of trades, {ex['initial_sl_share_of_losses_pct']}% of total losses. Losses: avg ${ex['loss_distribution']['avg']}, median ${ex['loss_distribution']['median']}, worst ${ex['loss_distribution']['worst']}, avg loss {ex['avg_loss_r']} R.",
              f"- MFE before a stop-out: avg ${ex['mfe_before_sl_hit'].get('avg_usd')} ({ex['mfe_before_sl_hit'].get('avg_r')} R); {ex['mfe_before_sl_hit'].get('share_ge_0.5R')} of stopped trades were >= 0.5R in profit first.",
              f"- MAE before a win: avg ${ex['mae_before_win'].get('avg_usd')}, median {ex['mae_before_win'].get('median_r')} R, p90 {ex['mae_before_win'].get('p90_r')} R ({ex['mae_before_win'].get('note')}).", ""]
    L += ["### Alternatives", "", "| variant | trades | median risk $ | SL hit % | avg loss $ | PF | win % | net $ | maxDD $ | exp R | exp R DEV | VAL | OOS | class |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for vname, r in results[name].items():
        a = r["metrics"]["ALL"]; m = r["metrics"]
        L.append(f"| {vname} | {a['trades']} | {r['median_risk_usd']} | {a.get('sl_hit_rate')} | {a.get('avg_loss')} | {a.get('profit_factor')} | {a.get('win_rate')} | {a['net_profit']} | {a['max_dd_usd']} | {a.get('expectancy_r')} | {m['DEV'].get('expectancy_r')} | {m['VAL'].get('expectancy_r')} | {m['OOS'].get('expectancy_r')} | {r['class']} |")
    L.append("")
with open(os.path.join(OUT, "STOPLOSS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
