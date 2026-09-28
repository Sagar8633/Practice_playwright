"""Study 3: H4 only. Start from the E19 exit stack (ATR-scaled break-even + ATR-scaled trailing + MA18 exit), find the
stable region of its parameters, test every entry filter / stop / MA period on top of it, then check robustness
(walk-forward folds, Monte Carlo, costs, intrabar ordering, 2003-2026 on the hourly path). Same data, costs and
rules as studies 1 and 2 (Sep 2020 - Sep 2026, DEV / VAL / OOS declared in common.py). Money per 0.01 lot.

Units: in thr_mode 1 the *_pts inputs are hundredths of the ATR(22) captured at entry, so 100 = 1.0 ATR.
"""
import itertools, json, os, sys, time
from dataclasses import replace

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import sma18_engine as E
import common as C

OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
LOG = lambda *a: print(*a, f"({time.time()-t0:.0f}s)", flush=True)
TF = 240; MIN_DEV = 40
MONTHS = E.months_between(C.DATA_START, C.DATA_END)


def strat(**kw):
    base = dict(tf_minutes=TF, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False)
    base.update(C.COST["B_real"]); base.update(kw)
    return E.Params(**base)


def save(obj, name):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=C._default)


def full(p):
    """ALL + DEV/VAL/OOS metrics + a compact record."""
    var, tr = C.evaluate(p)
    a = var["ALL"]
    rec = {"trades": a["trades"], "net": a["net_profit"], "pf": a.get("profit_factor"), "dd": a["max_dd_usd"], "win": a.get("win_rate"), "expR": a.get("expectancy_r"), "exp": a.get("expectancy"), "giveback": a.get("giveback_avg"), "p2l": a.get("profit_to_loss_2usd"), "avg_hold_min": a.get("avg_hold_min"),
           "exit_mix": a.get("exit_mix"), "max_consec_losses": a.get("max_consec_losses"), "avg_win": a.get("avg_win"), "avg_loss": a.get("avg_loss"),
           "DEV": (var["DEV"]["net_profit"], var["DEV"].get("expectancy_r"), var["DEV"]["trades"], var["DEV"].get("profit_factor")), "VAL": (var["VAL"]["net_profit"], var["VAL"].get("expectancy_r"), var["VAL"]["trades"], var["VAL"].get("profit_factor")), "OOS": (var["OOS"]["net_profit"], var["OOS"].get("expectancy_r"), var["OOS"]["trades"], var["OOS"].get("profit_factor"))}
    rec["pos3"] = bool(rec["DEV"][0] > 0 and rec["VAL"][0] > 0 and rec["OOS"][0] > 0)
    rec["min_expR"] = min(x for x in (rec["DEV"][1], rec["VAL"][1], rec["OOS"][1]) if x is not None) if all(x is not None for x in (rec["DEV"][1], rec["VAL"][1], rec["OOS"][1])) else None
    return var, tr, rec


# E19 as it ran in the exit lab: protection start left at 500 (= 5 ATR in ATR units) gates the trailing stop
E19_TESTED = dict(thr_mode=1, protection=4, be_enable=True, be_trigger_pts=100, prot_start_mode=1, prot_start_pts=500, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10)
# E19 as intended: trailing governed by its own start (2 ATR)
E19_INTENDED = dict(thr_mode=1, protection=4, be_enable=True, be_trigger_pts=100, prot_start_mode=0, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10)

R = {}
# ------------------------------------------------------------------ stage 0: baselines
R["stage0"] = {}
for nm, kw in (("Untouched EA (E01)", {}), ("E19 as tested (trail starts at 5 ATR because ProtectionStart = 500 units)", E19_TESTED), ("E19 as intended (trail starts at 2 ATR)", E19_INTENDED)):
    p = strat(**kw); var, tr, rec = full(p); R["stage0"][nm] = rec
    C.log_experiment("S3-stage0", nm, p, var["ALL"], "B_real", "6y", exit_logic=C.exit_desc(p), oos_result=f"DEV/VAL/OOS {rec['DEV'][0]}/{rec['VAL'][0]}/{rec['OOS'][0]}", conclusion="baseline")
    LOG(nm, "net", rec["net"], "PF", rec["pf"], "DD", rec["dd"], "DEV/VAL/OOS", rec["DEV"][0], rec["VAL"][0], rec["OOS"][0])
save(R, "study3.json")

# ------------------------------------------------------------------ stage 1: exit parameter grid (ATR units)
BE = [0, 50, 100, 150, 200]              # 0 = break-even off
START = [100, 200, 300, 400, 500, 600]
DIST = [50, 75, 100, 150, 200]
grid = []
for be, st, di in itertools.product(BE, START, DIST):
    kw = dict(thr_mode=1, protection=4, be_enable=be > 0, be_trigger_pts=be if be > 0 else 100, prot_start_mode=0, trail_start_pts=st, trail_dist_pts=di, trail_step_pts=10)
    p = strat(**kw); var, tr, rec = full(p); rec.update({"be": be, "start": st, "dist": di}); grid.append(rec)
    C.log_experiment("S3-stage1-exitgrid", f"BE {be/100:.2f} ATR, trail start {st/100:.1f} ATR, dist {di/100:.2f} ATR", p, var["ALL"], "B_real", "6y", exit_logic=C.exit_desc(p), oos_result=f"DEV/VAL/OOS expR {rec['DEV'][1]}/{rec['VAL'][1]}/{rec['OOS'][1]}", conclusion="grid")
g = pd.DataFrame(grid); g.to_csv(os.path.join(OUT, "stage1_exit_grid.csv"), index=False)
ok = g[g.pos3 & (g.DEV.apply(lambda x: x[2]) >= MIN_DEV)].copy()
ok["min_expR"] = ok["min_expR"].astype(float)
ok = ok.sort_values(["min_expR", "pf"], ascending=False)


def neighbours(row, df):
    """How many of the up-to-6 one-step neighbours (be, start, dist) are also positive in all three splits."""
    def idx(lst, v): return lst.index(v)
    n = 0; tot = 0
    for lst, key in ((BE, "be"), (START, "start"), (DIST, "dist")):
        i = idx(lst, row[key])
        for j in (i - 1, i + 1):
            if 0 <= j < len(lst):
                q = {**{k: row[k] for k in ("be", "start", "dist")}, key: lst[j]}
                m = df[(df.be == q["be"]) & (df.start == q["start"]) & (df.dist == q["dist"])]
                if len(m): tot += 1; n += int(bool(m.iloc[0].pos3))
    return n, tot


for i in ok.index:
    ok.loc[i, "nb_pos"], ok.loc[i, "nb_tot"] = neighbours(ok.loc[i], g)
R["stage1"] = {"grid_size": int(len(g)), "pos3": int(g.pos3.sum()), "share_pos_dev": round(float((g.DEV.apply(lambda x: x[0]) > 0).mean()), 3), "share_pos_val": round(float((g.VAL.apply(lambda x: x[0]) > 0).mean()), 3), "share_pos_oos": round(float((g.OOS.apply(lambda x: x[0]) > 0).mean()), 3),
               "top": ok.head(15).to_dict("records"), "best_net": g.sort_values("net", ascending=False).head(5).to_dict("records")}
chosen = ok.iloc[0] if len(ok) else None
if chosen is not None:
    CH = dict(thr_mode=1, protection=4, be_enable=int(chosen.be) > 0, be_trigger_pts=int(chosen.be) if chosen.be > 0 else 100, prot_start_mode=0, trail_start_pts=int(chosen.start), trail_dist_pts=int(chosen.dist), trail_step_pts=10)
else:
    CH = E19_INTENDED
R["stage1"]["chosen"] = CH
LOG("stage 1 grid: positive in all splits", R["stage1"]["pos3"], "of", len(g), "; chosen", CH)
# heatmaps for the report: start x dist for each BE (net and min expR)
R["stage1"]["heat"] = {str(be): [[float(g[(g.be == be) & (g.start == st) & (g.dist == di)].iloc[0]["net"]) for di in DIST] for st in START] for be in BE}
R["stage1"]["heat_minexp"] = {str(be): [[(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v))(g[(g.be == be) & (g.start == st) & (g.dist == di)].iloc[0]["min_expR"]) for di in DIST] for st in START] for be in BE}
R["stage1"]["axes"] = {"BE": BE, "START": START, "DIST": DIST}
save(R, "study3.json")

# ------------------------------------------------------------------ stage 2: entry filters on the chosen exit
H = lambda a, b: tuple(range(a, b))
FILTERS = {"F01 volume filter OFF": dict(use_volume=False), "F02 MA200 trend filter OFF": dict(use_trend=False), "F03 1-bar confirmation": dict(confirm_bars=1), "F04 3-bar confirmation": dict(confirm_bars=3),
           "F05 ADX>=25": dict(use_adx=True, adx_min=25.0), "F06 ADX>=20": dict(use_adx=True, adx_min=20.0), "F07 ADX>=30": dict(use_adx=True, adx_min=30.0), "F08 ADX>=25 rising(3)": dict(use_adx=True, adx_min=25.0, adx_rising=True), "F09 ADX>=25 consecutive rise(3)": dict(use_adx=True, adx_min=25.0, adx_consecutive=True),
           "F10 session London 8-17": dict(use_session=True, session_hours=H(8, 17)), "F11 session New York 13-22": dict(use_session=True, session_hours=H(13, 22)), "F12 session London+NY 8-22": dict(use_session=True, session_hours=H(8, 22)), "F13 session Tokyo 0-9": dict(use_session=True, session_hours=H(0, 9)), "F14 session overlap 13-17": dict(use_session=True, session_hours=H(13, 17)),
           "F15 pending expires 1 bar": dict(pending_max_bars=1), "F16 pending expires 3 bars": dict(pending_max_bars=3), "F17 pending invalidation OFF": dict(pending_invalidate=False), "F18 entry buffer 0": dict(entry_buffer_pts=0), "F19 entry buffer 50": dict(entry_buffer_pts=50),
           "F20 volatility ATR ratio >= 1.0": dict(use_vol_filter=True, vol_filter_min=1.0), "F21 volatility ATR ratio <= 1.5": dict(use_vol_filter=True, vol_filter_max=1.5), "F22 volatility ATR ratio 0.8-1.5": dict(use_vol_filter=True, vol_filter_min=0.8, vol_filter_max=1.5), "F23 max spread 40 pts": dict(max_spread_pts=40.0),
           "F24 MA18 slope over 3 bars": dict(slope_filter_bars=3), "F25 not extended |close-MA18| <= 1 ATR": dict(max_dist_atr=1.0), "F26 not extended |close-MA18| <= 2 ATR": dict(max_dist_atr=2.0),
           "F27 longs only": dict(), "F28 weekdays Mon-Thu only (no Friday entries)": dict()}
base_p = strat(**CH); base_var, base_tr, base_rec = full(base_p); R["stage2"] = {"base": base_rec, "rows": {}}
for v, kw in FILTERS.items():
    if v.startswith("F27"):
        # longs only: emulate by removing short trades from the base run (the EA has no such input; reported as information only)
        trl = base_tr[base_tr.side == 1]; var = {"ALL": C.metrics_from_trades(trl, 100000.0, MONTHS)}
        for nm, (a, b) in C.SPLITS.items(): var[nm] = C.metrics_from_trades(C.slice_trades(trl, a, b), 100000.0)
        cls = C.classify(base_var, var) + " (information: no EA input)"
    elif v.startswith("F28"):
        trl = base_tr[base_tr.time_in.dt.weekday < 4]; var = {"ALL": C.metrics_from_trades(trl, 100000.0, MONTHS)}
        for nm, (a, b) in C.SPLITS.items(): var[nm] = C.metrics_from_trades(C.slice_trades(trl, a, b), 100000.0)
        cls = C.classify(base_var, var) + " (information: no EA input)"
    else:
        p = replace(base_p, **kw); var, tr, rec = full(p); cls = C.classify(base_var, var)
        C.log_experiment("S3-stage2-filters", v, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"OOS net {var['OOS']['net_profit']} expR {var['OOS'].get('expectancy_r')}", conclusion=cls)
    a = var["ALL"]
    R["stage2"]["rows"][v] = {"trades": a["trades"], "net": a["net_profit"], "pf": a.get("profit_factor"), "dd": a["max_dd_usd"], "expR": a.get("expectancy_r"), "dev": var["DEV"].get("expectancy_r"), "val": var["VAL"].get("expectancy_r"), "oos": var["OOS"].get("expectancy_r"), "dev_net": var["DEV"]["net_profit"], "val_net": var["VAL"]["net_profit"], "oos_net": var["OOS"]["net_profit"], "cls": cls, "params": kw}
    LOG("stage2", v, "net", a["net_profit"], "PF", a.get("profit_factor"), "->", cls)
save(R, "study3.json")

# ------------------------------------------------------------------ stage 3: progressive combinations of helpful filters (EA inputs only)
helpful = [(v, r) for v, r in R["stage2"]["rows"].items() if r["cls"].startswith("Helpful") and r["params"]]
helpful.sort(key=lambda x: -(x[1]["dev"] or -9))
R["stage3"] = []; stacked = {}
for i, (v, r) in enumerate(helpful[:6]):
    for k, val in r["params"].items():
        stacked[k] = (tuple(sorted(set(stacked[k]) & set(val))) if (k == "session_hours" and k in stacked) else val)
    p = replace(base_p, **stacked); var, tr, rec = full(p); cls = C.classify(base_var, var)
    rec.update({"filters": " + ".join(x[0][:3] for x in helpful[: i + 1]), "params": dict(stacked), "cls": cls}); R["stage3"].append(rec)
    C.log_experiment("S3-stage3-combos", rec["filters"], p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"OOS net {rec['OOS'][0]}", conclusion=cls)
    LOG("stage3", rec["filters"], "net", rec["net"], "PF", rec["pf"], "->", cls)
save(R, "study3.json")

# ------------------------------------------------------------------ stage 4: stops on the chosen exit
STOPS = {"A original swing SL (strength 2)": dict(), "B ATR 1.5x": dict(sl_mode=1, sl_atr_mult=1.5), "B ATR 2.0x": dict(sl_mode=1, sl_atr_mult=2.0), "B ATR 2.5x": dict(sl_mode=1, sl_atr_mult=2.5), "B ATR 3.0x": dict(sl_mode=1, sl_atr_mult=3.0),
         "C swing strength 1": dict(swing_strength=1), "C swing strength 3": dict(swing_strength=3), "C swing - 0.5 ATR buffer": dict(sl_mode=7, sl_atr_mult=0.5), "C swing capped 1500 pts": dict(sl_mode=2, sl_cap_pts=1500), "C swing capped 3000 pts": dict(sl_mode=2, sl_cap_pts=3000),
         "E swing clamped [0.5, 3] ATR": dict(sl_mode=4, sl_floor_atr=0.5, sl_atr_mult=3.0), "E swing clamped [1, 4] ATR": dict(sl_mode=4, sl_floor_atr=1.0, sl_atr_mult=4.0), "F swing with 1.0 ATR floor": dict(sl_mode=3, sl_floor_atr=1.0), "F min stop 300 pts": dict(min_sl_pts=300)}
R["stage4"] = {}
for v, kw in STOPS.items():
    p = replace(base_p, **kw); var, tr, rec = full(p); cls = "base" if v.startswith("A ") else C.classify(base_var, var); rec["cls"] = cls; rec["median_risk"] = float(tr.risk_usd.median()) if len(tr) else None; R["stage4"][v] = rec
    C.log_experiment("S3-stage4-stops", v, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"OOS net {rec['OOS'][0]}", conclusion=cls)
LOG("stage4 stops done")
save(R, "study3.json")

# ------------------------------------------------------------------ stage 5: MA periods on the chosen exit (sensitivity, not selection)
R["stage5"] = {}
for f, t_ in itertools.product([13, 14, 18, 20, 21, 25], [150, 200, 250, 300]):
    E._IND_CACHE.clear(); p = replace(base_p, fast=f, trend=t_); var, tr, rec = full(p); R["stage5"][f"{f}/{t_}"] = rec
    C.log_experiment("S3-stage5-ma", f"MA {f}/{t_}", p, var["ALL"], "B_real", "6y", exit_logic=C.exit_desc(p), oos_result=f"DEV/VAL/OOS {rec['DEV'][0]}/{rec['VAL'][0]}/{rec['OOS'][0]}", conclusion="sensitivity")
LOG("stage5 MA sensitivity done")
save(R, "study3.json")

# ------------------------------------------------------------------ stage 6: final configuration and robustness
final_kw = dict(CH)
best_combo = None
for rec in R["stage3"]:
    if rec["cls"].startswith("Helpful") and rec["pos3"] and (best_combo is None or (rec["min_expR"] or -9) > (best_combo["min_expR"] or -9)):
        best_combo = rec
if best_combo:
    final_kw.update(best_combo["params"])
R["final"] = {"params": final_kw, "from_combo": best_combo["filters"] if best_combo else None}
pf_ = strat(**final_kw)
configs = {"Untouched EA": strat(), "E19 as tested": strat(**E19_TESTED), "Chosen exit (stage 1)": base_p, "Final (chosen exit + helpful filters)": pf_}
rob = {}
for nm, p in configs.items():
    var, tr, rec = full(p); d = {"all": rec}
    d["cost"] = {c: C.metrics_from_trades(E.run(replace(p, **C.COST[c]))[0], 100000.0, MONTHS)["net_profit"] for c in ("A_low", "C_stress")}
    d["worst_path"] = C.metrics_from_trades(E.run(replace(p, trail_mode=1))[0], 100000.0, MONTHS)["net_profit"]
    d["folds"] = [{k: (lambda m: (m["net_profit"], m.get("expectancy_r"), m["trades"]))(C.metrics_from_trades(C.slice_trades(tr, *f[k]), 100000.0)) for k in ("train", "val", "test")} for f in C.WF_FOLDS]
    tr["year"] = tr.time_out.dt.year; d["by_year"] = {int(y): round(float(v), 2) for y, v in tr.groupby("year").pnl.sum().items()}
    d["by_session"] = C.by_group(tr, "session").to_dict("index"); d["by_side"] = C.by_group(tr, "side").to_dict("index")
    d["median_risk"] = float(tr.risk_usd.median()); d["p90_risk"] = float(tr.risk_usd.quantile(0.9))
    d["mc_200"] = E.monte_carlo(tr.pnl.to_numpy(), 200.0); d["mc_100x"] = E.monte_carlo(tr.pnl.to_numpy(), max(100 * d["median_risk"], 200.0))
    # 2003-2026 on the hourly path (H4 bars built from H1 before Sep 2020)
    p23 = replace(p, path="h1", start=C.D1_START, end=C.DATA_END); tr23, st23 = E.run(p23); tr23["year"] = tr23.time_out.dt.year
    m23 = C.metrics_from_trades(tr23, 100000.0, E.months_between(C.D1_START, C.DATA_END)); yr = tr23.groupby("year").pnl.sum()
    d["h1path_2003_2026"] = {"trades": m23["trades"], "net": m23["net_profit"], "pf": m23.get("profit_factor"), "dd": m23["max_dd_usd"], "expR": m23.get("expectancy_r"), "pos_years": f"{int((yr > 0).sum())}/{len(yr)}", "worst_year": round(float(yr.min()), 2), "by_year": {int(y): round(float(v), 2) for y, v in yr.items()},
                             "windows": {w: (lambda m: (m["net_profit"], m.get("expectancy_r"), m["trades"]))(C.metrics_from_trades(C.slice_trades(tr23, a, b), 100000.0)) for w, (a, b) in {"2003-2012": ("2003-05-05", "2012-01-01"), "2012-2020": ("2012-01-01", "2020-09-01"), "2020-2026": ("2020-09-01", "2026-09-26")}.items()},
                             "mc_200": E.monte_carlo(tr23.pnl.to_numpy(), 200.0)}
    d["window_2023_26"] = (lambda m: (m["net_profit"], m.get("expectancy_r"), m["trades"], m.get("profit_factor")))(C.metrics_from_trades(C.slice_trades(tr, "2023-01-01", "2026-09-26"), 100000.0))
    tr.to_csv(os.path.join(OUT, f"trades_{nm.split(' ')[0].lower()}.csv"), index=False)
    rob[nm] = d
    C.log_experiment("S3-stage6-robustness", nm, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"folds test {[f['test'][0] for f in d['folds']]}; 2003-26 {d['h1path_2003_2026']['net']}", conclusion="final candidates")
    LOG("stage6", nm, "net", rec["net"], "PF", rec["pf"], "DD", rec["dd"], "2003-26", d["h1path_2003_2026"]["net"], d["h1path_2003_2026"]["pos_years"], "MC ruin $200", d["mc_200"]["bootstrap"]["p_ruin"])
R["stage6"] = rob
# sensitivity of the final config around its exit values and the filter thresholds
sens = {}
pfin = pf_
sw = {"be_trigger_pts": [50, 75, 100, 125, 150, 200], "trail_start_pts": [100, 150, 200, 250, 300, 400, 500, 600], "trail_dist_pts": [50, 75, 100, 125, 150, 200], "trail_step_pts": [5, 10, 20, 30], "atr_period": [10, 14, 22, 30, 44], "fast": [14, 16, 18, 20, 22], "trend": [150, 175, 200, 225, 250]}
if pfin.use_adx: sw["adx_min"] = [20, 22.5, 25, 27.5, 30]
if pfin.use_vol_filter: sw["vol_filter_min"] = [0.8, 0.9, 1.0, 1.1, 1.2]
for pn, vals in sw.items():
    sens[pn] = []
    for v in vals:
        E._IND_CACHE.clear(); q = replace(pfin, **{pn: v}); var, tr, rec = full(q)
        sens[pn].append({"value": v, "net": rec["net"], "pf": rec["pf"], "dd": rec["dd"], "expR": rec["expR"], "DEV": rec["DEV"][1], "VAL": rec["VAL"][1], "OOS": rec["OOS"][1], "pos3": rec["pos3"], "trades": rec["trades"]})
R["sensitivity"] = sens
save(R, "study3.json")
LOG("done")
