"""STEPS 17-20 / sections 17, 19, 20, 32: walk-forward selection, parameter sensitivity, Monte Carlo, overfitting audit.

Declared grid (built only from components tested in phases 1-4; nothing added after seeing results):
  filters : none | volatility ATR ratio >= 1 | ADX >= 25 | New York session (LTF only) | volatility + ADX
  stop    : swing (EA) | ATR 3.0x | swing strength 3
  exit    : E00 SL only + MA18 | E01 EA default | E03 Chandelier immediate + BE | E04 trailing 1000/500/50 + BE |
            E09 ATR trail 2x + BE | E13 TWK 3-stage | E16 Chandelier immediate + BE, no MA18 | E20 R-scaled BE 1R + swing after 1R
Every configuration is run ONCE over the full period (fixed lots -> trades are independent of the balance path) and the
walk-forward folds are time slices of that run. Selection rule per fold, declared in advance:
  train : highest expectancy/R among configs with >= MIN_TRADES in the train window (ties -> PF)
  val   : the train-best must have expectancy/R > 0 in the validation window, otherwise "no configuration passes"
  test  : the never-touched test window of the fold
"""
import itertools, json, os, time
from dataclasses import replace

import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "walkforward"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
FILTERS = {"none": {}, "vol>=1": dict(use_vol_filter=True, vol_filter_min=1.0), "ADX>=25": dict(use_adx=True, adx_min=25.0),
           "NY 13-22": dict(use_session=True, session_hours=tuple(range(13, 22))), "vol>=1+ADX>=25": dict(use_vol_filter=True, vol_filter_min=1.0, use_adx=True, adx_min=25.0)}
STOPS = {"swing": {}, "ATR3": dict(sl_mode=1, sl_atr_mult=3.0), "swing3": dict(swing_strength=3)}
EXITS = {"E00 SL+MA18": dict(protection=0, be_enable=False), "E01 EA": {}, "E03 Chand+BE": dict(protection=2, prot_start_mode=0),
         "E04 Trail+BE": dict(protection=4), "E09 ATRtrail2+BE": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=2.0),
         "E13 TWK": dict(protection=16, be_enable=False), "E16 Chand+BE noMA": dict(protection=2, prot_start_mode=0, ma_exit=False),
         "E20 R-BE1R+swing1R": dict(thr_mode=2, be_trigger_pts=100, prot_start_pts=100)}
MIN_TRADES = {1: 100, 5: 100, 15: 60, 1440: 10}
TFS = [1, 5, 15, 1440]


def slice_m(tr, a, b, months=None):
    return C.metrics_from_trades(C.slice_trades(tr, a, b), 100000.0, months)


def keyname(f, s, x):
    return f"{f} | {s} | {x}"


all_results = {}
for tf in TFS:
    name = C.TF_NAME[tf]
    base_p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
    runs = {}
    for (fn, fkw), (sn, skw), (xn, xkw) in itertools.product(FILTERS.items(), STOPS.items(), EXITS.items()):
        if tf == 1440 and "NY" in fn:
            continue
        p = replace(base_p, **fkw, **skw, **xkw)
        tr, st = E.run(p)
        rec = {"params": {**fkw, **skw, **xkw}, "folds": [], "pnl": tr["pnl"].to_numpy().copy(), "risk_med": float(tr["risk_usd"].median()) if len(tr) else 0.0}
        for f in C.WF_FOLDS:
            rec["folds"].append({"train": slice_m(tr, *f["train"]), "val": slice_m(tr, *f["val"]), "test": slice_m(tr, *f["test"])})
        rec["dev"] = slice_m(tr, *C.SPLITS["DEV"]); rec["val"] = slice_m(tr, *C.SPLITS["VAL"]); rec["oos"] = slice_m(tr, *C.SPLITS["OOS"])
        rec["all"] = slice_m(tr, C.DATA_START, C.DATA_END, E.months_between(C.DATA_START, C.DATA_END))
        runs[keyname(fn, sn, xn)] = rec
    print(f"{name}: {len(runs)} configurations run ({time.time()-t0:.0f}s)", flush=True)
    # ---------------- walk-forward folds
    folds = []
    for i, f in enumerate(C.WF_FOLDS):
        rows = []
        for k, r in runs.items():
            mt = r["folds"][i]["train"]; mv = r["folds"][i]["val"]; ms = r["folds"][i]["test"]
            rows.append({"config": k, "train_trades": mt["trades"], "train_expR": mt.get("expectancy_r"), "train_pf": mt.get("profit_factor"), "train_net": mt["net_profit"],
                         "val_trades": mv["trades"], "val_expR": mv.get("expectancy_r"), "val_pf": mv.get("profit_factor"), "val_net": mv["net_profit"],
                         "test_trades": ms["trades"], "test_expR": ms.get("expectancy_r"), "test_pf": ms.get("profit_factor"), "test_net": ms["net_profit"], "test_dd": ms["max_dd_usd"]})
        d = pd.DataFrame(rows)
        d["train_expR"] = d["train_expR"].astype(float); d["val_expR"] = d["val_expR"].astype(float); d["test_expR"] = d["test_expR"].astype(float)
        elig = d[d["train_trades"] >= MIN_TRADES[tf]].sort_values(["train_expR", "train_pf"], ascending=False)
        ea = d[d["config"] == keyname("none", "swing", "E01 EA")].iloc[0]
        fold = {"fold": i + 1, "train": f["train"], "val": f["val"], "test": f["test"], "configs": int(len(d)), "eligible": int(len(elig)),
                "share_positive_train": round(float((d["train_net"] > 0).mean()), 3), "share_positive_val": round(float((d["val_net"] > 0).mean()), 3), "share_positive_test": round(float((d["test_net"] > 0).mean()), 3),
                "ea_untouched": {k: (None if pd.isna(v) else (float(v) if isinstance(v, (np.floating, float)) else v)) for k, v in ea.items()}}
        if len(elig):
            best = elig.iloc[0]
            fold["train_best"] = {k: (None if pd.isna(v) else (float(v) if isinstance(v, (np.floating, float)) else v)) for k, v in best.items()}
            fold["train_best_passes_val"] = bool(best["val_expR"] > 0)
            passed = elig[elig["val_expR"] > 0]
            fold["selected"] = ({k: (None if pd.isna(v) else (float(v) if isinstance(v, (np.floating, float)) else v)) for k, v in passed.iloc[0].items()} if len(passed) else None)
            fold["n_pass_val"] = int(len(passed))
            top5 = elig.head(5)
            fold["top5_train_vs_test"] = [{"config": r["config"], "train_expR": r["train_expR"], "val_expR": r["val_expR"], "test_expR": r["test_expR"], "test_net": r["test_net"]} for _, r in top5.iterrows()]
            fold["degradation_train_to_test_expR_top5"] = round(float((top5["test_expR"] - top5["train_expR"]).mean()), 3)
        d.to_csv(os.path.join(OUT, f"wf_{name}_fold{i+1}.csv"), index=False)
        folds.append(fold)
        sel = fold.get("selected")
        print(f"{name} fold {i+1}: train-best {fold.get('train_best', {}).get('config')} trainR {fold.get('train_best', {}).get('train_expR')} valR {fold.get('train_best', {}).get('val_expR')} testR {fold.get('train_best', {}).get('test_expR')} | selected {sel['config'] if sel else None} testR {sel['test_expR'] if sel else None} test net {sel['test_net'] if sel else None} | EA test net {ea['test_net']} ({time.time()-t0:.0f}s)", flush=True)
    # ---------------- full DEV+VAL selection -> OOS (the "final candidate" procedure) and the overfitting audit
    rows = []
    for k, r in runs.items():
        md = r["dev"]; mv = r["val"]; mo = r["oos"]; ma = r["all"]
        rows.append({"config": k, "dev_trades": md["trades"], "dev_expR": md.get("expectancy_r"), "dev_pf": md.get("profit_factor"), "dev_net": md["net_profit"], "val_expR": mv.get("expectancy_r"), "val_pf": mv.get("profit_factor"), "val_net": mv["net_profit"],
                     "oos_trades": mo["trades"], "oos_expR": mo.get("expectancy_r"), "oos_pf": mo.get("profit_factor"), "oos_net": mo["net_profit"], "oos_dd": mo["max_dd_usd"],
                     "all_trades": ma["trades"], "all_net": ma["net_profit"], "all_pf": ma.get("profit_factor"), "all_dd": ma["max_dd_usd"], "all_expR": ma.get("expectancy_r"), "all_win": ma.get("win_rate"), "all_giveback": ma.get("giveback_avg"), "all_p2l": ma.get("profit_to_loss_2usd"),
                     "positive_dev_val_oos": bool((md["net_profit"] > 0) and (mv["net_profit"] > 0) and (mo["net_profit"] > 0))})
    d = pd.DataFrame(rows); d.to_csv(os.path.join(OUT, f"grid_{name}.csv"), index=False)
    elig = d[d["dev_trades"] >= MIN_TRADES[tf]].copy(); elig["dev_expR"] = elig["dev_expR"].astype(float)
    elig = elig.sort_values(["dev_expR", "dev_pf"], ascending=False)
    audit = {"configs_tested": int(len(d)), "eligible": int(len(elig)), "positive_all_three_splits": int(d["positive_dev_val_oos"].sum()),
             "share_positive_dev": round(float((d["dev_net"] > 0).mean()), 3), "share_positive_val": round(float((d["val_net"] > 0).mean()), 3), "share_positive_oos": round(float((d["oos_net"] > 0).mean()), 3),
             "best_in_sample": None, "best_in_sample_oos": None, "robust_candidates": []}
    if len(elig):
        b = elig.iloc[0]
        audit["best_in_sample"] = {"config": b["config"], "dev_expR": b["dev_expR"], "dev_pf": b["dev_pf"], "val_expR": b["val_expR"], "oos_expR": b["oos_expR"], "oos_net": b["oos_net"], "oos_pf": b["oos_pf"]}
        rob = d[d["positive_dev_val_oos"] & (d["dev_trades"] >= MIN_TRADES[tf])].sort_values("oos_expR", ascending=False)
        audit["robust_candidates"] = rob.head(10).to_dict("records")
    all_results[name] = {"folds": folds, "audit": audit}
    print(name, "audit:", {k: v for k, v in audit.items() if k not in ("robust_candidates",)}, flush=True)

    # ---------------- parameter sensitivity around the best robust candidate (if any) -> stable region test
    sens = {}
    cand = all_results[name]["audit"]["robust_candidates"][0] if all_results[name]["audit"]["robust_candidates"] else None
    if cand:
        params = runs[cand["config"]]["params"]
        pc = replace(base_p, **params)
        sweeps = {}
        if pc.protection & 2: sweeps["atr_mult"] = [pc.atr_mult * f for f in (0.5, 0.75, 1.0, 1.25, 1.5)]; sweeps["chand_lookback"] = [11, 16, 22, 28, 33]
        if pc.protection & 4: sweeps["trail_dist_pts"] = [int(pc.trail_dist_pts * f) for f in (0.6, 0.8, 1.0, 1.2, 1.5)]; sweeps["trail_start_pts"] = [int(pc.trail_start_pts * f) for f in (0.5, 0.75, 1.0, 1.25, 1.5)]
        if pc.protection & 8: sweeps["atr_trail_mult"] = [pc.atr_trail_mult * f for f in (0.75, 0.875, 1.0, 1.125, 1.25)]
        if pc.protection & 16: sweeps["twk_gap_pts"] = [int(pc.twk_gap_pts * f) for f in (0.5, 0.75, 1.0, 1.25, 1.5)]; sweeps["twk_act_pts"] = [int(pc.twk_act_pts * f) for f in (0.5, 0.75, 1.0, 1.5, 2.0)]
        if pc.be_enable: sweeps["be_trigger_pts"] = [int(pc.be_trigger_pts * f) for f in (0.6, 0.8, 1.0, 1.2, 1.4)]
        if pc.protection & 1: sweeps["prot_start_pts"] = [int(pc.prot_start_pts * f) for f in (0.5, 0.75, 1.0, 1.5, 2.0)]; sweeps["swing_buffer_pts"] = [0, 25, 50, 100, 150]
        if pc.sl_mode == 1: sweeps["sl_atr_mult"] = [pc.sl_atr_mult * f for f in (0.75, 0.875, 1.0, 1.125, 1.25)]
        if pc.use_vol_filter: sweeps["vol_filter_min"] = [0.8, 0.9, 1.0, 1.1, 1.2]
        if pc.use_adx: sweeps["adx_min"] = [20, 22.5, 25, 27.5, 30]
        sweeps["fast"] = [14, 16, 18, 20, 22]; sweeps["trend"] = [150, 175, 200, 225, 250]
        for pname, vals in sweeps.items():
            row = []
            for v in vals:
                q = replace(pc, **{pname: v})
                tr, st = E.run(q)
                mo = slice_m(tr, *C.SPLITS["OOS"]); ma = C.metrics_from_trades(tr, 100000.0)
                row.append({"value": v, "all_net": ma["net_profit"], "all_expR": ma.get("expectancy_r"), "all_pf": ma.get("profit_factor"), "oos_net": mo["net_profit"], "oos_expR": mo.get("expectancy_r"), "trades": ma["trades"]})
            sens[pname] = row
        # Monte Carlo on the candidate at $200 and at 100x median risk
        pnl = runs[cand["config"]]["pnl"]; med_risk = runs[cand["config"]]["risk_med"]
        mc = {"at_200": E.monte_carlo(pnl, 200.0), "at_100x_median_risk": E.monte_carlo(pnl, max(100 * med_risk, 200.0)), "median_risk_usd": med_risk}
        all_results[name]["candidate"] = {"config": cand["config"], "params": params, "sensitivity": sens, "monte_carlo": mc}
        print(name, "candidate", cand["config"], "sensitivity params:", list(sens), flush=True)
    else:
        all_results[name]["candidate"] = None
        # Monte Carlo on the untouched EA for the record
        all_results[name]["ea_monte_carlo_200"] = E.monte_carlo(runs[keyname("none", "swing", "E01 EA")]["pnl"], 200.0)

C.save_json(all_results, "walkforward/summary.json")

# ---------------- markdown
L = ["# Walk-forward, sensitivity, Monte Carlo and overfitting audit", "", "Grid: 5 filters x 3 stops x 8 exits = 120 configurations per timeframe (96 on D1). Folds: train 2 y -> validate 1 y -> test 1 y, rolled yearly from Sep 2020. "
     "Strategy view, 0.01 lot, realistic costs. Selection = best train expectancy/R (min trades), gated by validation expectancy/R > 0; test window never used for selection.", ""]
for name, R in all_results.items():
    L += [f"## {name}", "", "| fold | train | val | test | configs | train-best config | train R | val R | test R | passes val | selected (val-gated) | selected test R | selected test net $ | untouched EA test net $ | share of configs positive in test |", "|---|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|"]
    for f in R["folds"]:
        tb = f.get("train_best", {}); sel = f.get("selected")
        L.append(f"| {f['fold']} | {f['train'][0][:7]}..{f['train'][1][:7]} | {f['val'][0][:7]}..{f['val'][1][:7]} | {f['test'][0][:7]}..{f['test'][1][:7]} | {f['configs']} | {tb.get('config')} | {tb.get('train_expR')} | {tb.get('val_expR')} | {tb.get('test_expR')} | {f.get('train_best_passes_val')} | {sel['config'] if sel else 'none passes'} | {sel['test_expR'] if sel else ''} | {sel['test_net'] if sel else ''} | {f['ea_untouched']['test_net']} | {f['share_positive_test']} |")
    a = R["audit"]
    L += ["", f"Overfitting audit (DEV -> VAL -> OOS): {a['configs_tested']} configurations tested; positive in all three splits: {a['positive_all_three_splits']}; share positive DEV {a['share_positive_dev']}, VAL {a['share_positive_val']}, OOS {a['share_positive_oos']}. "
          f"Best in-sample: {a['best_in_sample']}.", ""]
    if a["robust_candidates"]:
        L += ["Configurations positive in DEV, VAL and OOS (top by OOS expectancy/R):", "", "| config | DEV R | VAL R | OOS R | OOS net $ | OOS PF | all net $ | all PF | all DD $ | trades |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in a["robust_candidates"]:
            L.append(f"| {r['config']} | {r['dev_expR']} | {r['val_expR']} | {r['oos_expR']} | {r['oos_net']} | {r['oos_pf']} | {r['all_net']} | {r['all_pf']} | {r['all_dd']} | {r['all_trades']} |")
    else:
        L.append("No configuration is positive in DEV, VAL and OOS on this timeframe.")
    c = R.get("candidate")
    if c:
        L += ["", f"### Sensitivity around {c['config']}", "", "| parameter | values -> all-period expectancy R (net $) | OOS expectancy R |", "|---|---|---|"]
        for pn, rows in c["sensitivity"].items():
            L.append(f"| {pn} | " + ", ".join(f"{r['value']}: {r['all_expR']} ({r['all_net']})" for r in rows) + " | " + ", ".join(f"{r['oos_expR']}" for r in rows) + " |")
        mc = c["monte_carlo"]
        L += ["", f"Monte Carlo (trade-order shuffle / bootstrap) at $200: p(ruin) {mc['at_200']['shuffle']['p_ruin']} / {mc['at_200']['bootstrap']['p_ruin']}, DD p95 ${mc['at_200']['shuffle']['dd_p95']}, ending balance p05-median-p95 ${mc['at_200']['bootstrap']['end_p05']} / ${mc['at_200']['bootstrap']['end_median']} / ${mc['at_200']['bootstrap']['end_p95']}; "
              f"at 100x median risk (${max(100*mc['median_risk_usd'],200):.0f}): p(ruin) {mc['at_100x_median_risk']['shuffle']['p_ruin']}, DD p95 ${mc['at_100x_median_risk']['shuffle']['dd_p95']}."]
    L.append("")
with open(os.path.join(OUT, "WALKFORWARD.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
