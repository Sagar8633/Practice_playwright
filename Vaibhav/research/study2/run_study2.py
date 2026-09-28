"""Study 2 (2026-09-26, second brief): H1 and H4 through the same pipeline as the first study, then a 2023-2026 window
for all six timeframes with session-wise P/L, the EA's own session filters, and a staged SMA sweep.

Part A  H1 / H4, Sep 2020 - Sep 2026, DEV/VAL/OOS as before: baseline (3 costs x 3 views), trade analysis, filters, stops,
        exits, walk-forward grid, candidate.
Part B  2023-01-01 - 2026-09-26, M1/M5/M15/H1/H4/D1: baseline, P/L by session / hour / weekday, session-filter tests,
        SMA sweeps (fast with trend 200; trend with fast 18 and the best fast; popular pairs) with IS 2023-24 / OOS 2025-26,
        and the same fast sweep under the improved exit (Chandelier immediate + ADX 25) on H1/H4/D1.
Outputs: study2/results/*.json, *.csv; every run is logged in results/experiment_log.csv with phase S2-*.
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
P3 = ("2023-01-01", "2026-09-26")
SPLIT3 = {"IS": ("2023-01-01", "2025-01-01"), "OOS": ("2025-01-01", "2026-09-26")}
ALL_TFS = [1, 5, 15, 60, 240, 1440]
HTFS = [60, 240]
VIEWS = {"strategy": dict(start_balance=100000.0, margin_check=False, use_sl_pct=False), "ea_200": dict(start_balance=200.0, margin_check=True, use_sl_pct=True), "ea_200_nofilt": dict(start_balance=200.0, margin_check=True, use_sl_pct=False)}
MIN_TR = {1: 100, 5: 100, 15: 60, 60: 40, 240: 15, 1440: 10}


def strat(tf, start=C.DATA_START, end=C.DATA_END, cost="B_real", **kw):
    base = dict(tf_minutes=tf, start=start, end=end, start_balance=100000.0, margin_check=False, use_sl_pct=False)
    base.update(C.COST[cost]); base.update(kw)
    return E.Params(**base)


def save(obj, name):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=C._default)


def m_slices(tr, splits):
    return {nm: C.metrics_from_trades(C.slice_trades(tr, a, b), 100000.0, E.months_between(a, b)) for nm, (a, b) in splits.items()}


def cat_loss(r, med_risk, tfm):
    mfe_r = r["mfe_r"] if pd.notna(r["mfe_r"]) else 0.0
    if r["exit_reason"] == "stop_out": return "12 other (stop-out)"
    cost = (r["spread_entry"] + 0.10) * E.CONTRACT * r["lots"]
    if abs(r["pnl"]) <= cost and (r["gross_usd"] + cost) >= 0: return "11 spread/slippage (positive before costs)"
    if r.get("regime_big_move") is True or r.get("regime_sharp_reversal") is True: return "09 news/volatility event"
    if r["hour_in"] in (1, 2, 22, 23) and tfm < 1440: return "10 low-liquidity hour"
    if r["exit_reason"] == "SL_initial" and r["risk_usd"] >= 2.0 * med_risk: return "04 excessive SL"
    if mfe_r >= 1.0 and (r["giveback_pct"] or 0) >= 60: return "06 protection too loose (gave back >60% of >=1R)"
    if r["bars_held"] <= 3 and r["exit_reason"] == "MA18_exit": return "03 whipsaw (MA18 exit within 3 bars)"
    if mfe_r < 0.25: return "01 bad entry (never reached 0.25R)"
    if mfe_r >= 0.5: return "02 correct entry, market reversal"
    return "12 other"


# ====================================================================== Part A: H1 / H4 through the first study's pipeline
def part_a():
    res = {}
    for tf in HTFS:
        name = C.TF_NAME[tf]; res[name] = {"baseline": {}, "by_year": {}}
        months = E.months_between(C.DATA_START, C.DATA_END)
        for view, vkw in VIEWS.items():
            res[name]["baseline"][view] = {}
            for cost in C.COST:
                p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, **vkw, **C.COST[cost])
                tr, st = E.run(p); m = E.metrics(tr, st, p.start_balance, months)
                res[name]["baseline"][view][cost] = m
                if view == "strategy" and cost == "B_real":
                    trb = C.tag_regimes(tr); trb.to_csv(os.path.join(OUT, f"trades_{name}_6y_strategy_B_real.csv"), index=False)
                    q = replace(p, trail_mode=1); tr2, st2 = E.run(q); res[name]["baseline"]["strategy"]["B_real_worst"] = E.metrics(tr2, st2, p.start_balance, months)
                    m.update({k: v for k, v in m_slices(tr, C.SPLITS).items()})
                if view != "strategy" and cost == "B_real":
                    tr.to_csv(os.path.join(OUT, f"trades_{name}_6y_{view}_B_real.csv"), index=False)
                C.log_experiment("S2A-baseline", f"H1/H4 baseline ({view})", p, m, cost, "2020-09..2026-09", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), conclusion=f"net {m['net_profit']} PF {m.get('profit_factor')} DD {m['max_dd_usd']}")
                LOG(name, view, cost, "trades", m["trades"], "net", m["net_profit"], "PF", m.get("profit_factor"))
        # by year, trade analysis
        tr = pd.read_csv(os.path.join(OUT, f"trades_{name}_6y_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
        if len(tr):
            tr["year"] = tr["time_out"].dt.year; g = tr.groupby("year")
            res[name]["by_year"] = {int(y): {"trades": int(len(x)), "net": round(float(x["pnl"].sum()), 2), "pf": round(float(x.loc[x.pnl > 0, "pnl"].sum() / max(-x.loc[x.pnl < 0, "pnl"].sum(), 1e-9)), 2), "win": round(100 * float((x.pnl > 0).mean()), 1)} for y, x in g}
            o = {"trades": int(len(tr)), "total_mfe": round(float(tr.mfe_usd.sum()), 2), "realized": round(float(tr.pnl.sum()), 2), "avg_giveback": round(float(tr.giveback_usd.mean()), 2), "median_giveback_pct": round(float(tr.giveback_pct.median()), 1), "worst_giveback": round(float(tr.giveback_usd.max()), 2), "share_ge1": round(float((tr.mfe_usd >= 1).mean()), 3)}
            byexit = C.by_group(tr, "exit_reason").to_dict("index"); bysess = C.by_group(tr, "session").to_dict("index"); bydir = C.by_group(tr, "side").to_dict("index")
            p2l = {}
            for lab, mask in [(f"{t}usd", (tr.mfe_usd >= t) & (tr.pnl < 0)) for t in (1, 2, 5, 10)] + [(f"{t}R", (tr.mfe_r >= t) & (tr.pnl < 0)) for t in (1, 2, 3)]:
                sub = tr[mask]; tot = float(tr.loc[tr.pnl < 0, "pnl"].sum())
                p2l[lab] = {"trades": int(len(sub)), "share_of_losers": round(float(len(sub) / max((tr.pnl < 0).sum(), 1)), 3), "realized_loss": round(float(sub.pnl.sum()), 2), "given_up": round(float(sub.mfe_usd.sum()), 2), "share_of_losses": round(float(sub.pnl.sum() / tot), 3) if tot else 0.0, "exit_mix": {k: int(v) for k, v in sub.exit_reason.value_counts().items()}}
            losers = tr[tr.pnl < 0].copy(); med = float(tr.risk_usd.median())
            losers["category"] = losers.apply(lambda r: cat_loss(r, med, tf), axis=1); tot = float(losers.pnl.sum())
            cats = losers.groupby("category").agg(trades=("pnl", "size"), loss=("pnl", "sum")).round(2); cats["share"] = (100 * cats["loss"] / tot).round(1)
            res[name]["trade_analysis"] = {"overall": o, "by_exit": byexit, "by_session": bysess, "by_side": bydir, "p2l": p2l, "loss_categories": cats.sort_values("loss").to_dict("index")}
        LOG(name, "baseline + trade analysis done")
    save(res, "partA_baseline.json")

    # ---- filters / stops / exits (same variants as the first study)
    H = lambda a, b: tuple(range(a, b))
    FILTERS = {"F01 volume filter OFF": dict(use_volume=False), "F02 MA200 trend filter OFF": dict(use_trend=False), "F03 1-bar confirmation": dict(confirm_bars=1), "F04 3-bar confirmation": dict(confirm_bars=3),
               "F05 ADX>=25": dict(use_adx=True, adx_min=25.0), "F06 ADX>=20": dict(use_adx=True, adx_min=20.0), "F07 ADX>=30": dict(use_adx=True, adx_min=30.0), "F08 ADX>=25 rising(3)": dict(use_adx=True, adx_min=25.0, adx_rising=True), "F09 ADX>=25 consecutive rise(3)": dict(use_adx=True, adx_min=25.0, adx_consecutive=True),
               "F10 session London 8-17": dict(use_session=True, session_hours=H(8, 17)), "F11 session New York 13-22": dict(use_session=True, session_hours=H(13, 22)), "F12 session London+NY 8-22": dict(use_session=True, session_hours=H(8, 22)), "F13 session Tokyo 0-9": dict(use_session=True, session_hours=H(0, 9)), "F14 session overlap 13-17": dict(use_session=True, session_hours=H(13, 17)),
               "F15 pending expires 1 bar": dict(pending_max_bars=1), "F16 pending expires 3 bars": dict(pending_max_bars=3), "F17 pending invalidation OFF": dict(pending_invalidate=False), "F18 entry buffer 0": dict(entry_buffer_pts=0), "F19 entry buffer 50": dict(entry_buffer_pts=50),
               "F20 volatility ATR ratio >= 1.0": dict(use_vol_filter=True, vol_filter_min=1.0), "F21 volatility ATR ratio <= 1.5": dict(use_vol_filter=True, vol_filter_max=1.5), "F22 volatility ATR ratio 0.8-1.5": dict(use_vol_filter=True, vol_filter_min=0.8, vol_filter_max=1.5), "F23 max spread 40 pts": dict(max_spread_pts=40.0),
               "F24 MA18 slope over 3 bars": dict(slope_filter_bars=3), "F25 not extended |close-MA18| <= 1 ATR": dict(max_dist_atr=1.0), "F26 not extended |close-MA18| <= 2 ATR": dict(max_dist_atr=2.0)}
    STOPS = {"A original swing SL (strength 2)": dict(), "B ATR 1.0x": dict(sl_mode=1, sl_atr_mult=1.0), "B ATR 1.5x": dict(sl_mode=1, sl_atr_mult=1.5), "B ATR 2.0x": dict(sl_mode=1, sl_atr_mult=2.0), "B ATR 2.5x": dict(sl_mode=1, sl_atr_mult=2.5), "B ATR 3.0x": dict(sl_mode=1, sl_atr_mult=3.0),
             "C swing strength 1": dict(swing_strength=1), "C swing strength 3": dict(swing_strength=3), "C swing - 0.5 ATR buffer": dict(sl_mode=7, sl_atr_mult=0.5), "C swing - 0.25 ATR buffer": dict(sl_mode=7, sl_atr_mult=0.25), "C swing capped 1000 pts": dict(sl_mode=2, sl_cap_pts=1000), "C swing capped 1500 pts (v13)": dict(sl_mode=2, sl_cap_pts=1500), "C swing capped 2000 pts": dict(sl_mode=2, sl_cap_pts=2000),
             "D MA18 - 0 pts": dict(sl_mode=5, swing_buffer_pts=0), "D MA18 - 50 pts": dict(sl_mode=5, swing_buffer_pts=50), "E swing clamped [0.5, 3] ATR": dict(sl_mode=4, sl_floor_atr=0.5, sl_atr_mult=3.0), "E swing clamped [1, 4] ATR": dict(sl_mode=4, sl_floor_atr=1.0, sl_atr_mult=4.0), "E swing clamped [0.5, 2] ATR": dict(sl_mode=4, sl_floor_atr=0.5, sl_atr_mult=2.0),
             "F swing with 0.5 ATR floor": dict(sl_mode=3, sl_floor_atr=0.5), "F swing with 1.0 ATR floor": dict(sl_mode=3, sl_floor_atr=1.0), "F min stop 150 pts (v13 MinStopPoints)": dict(min_sl_pts=150), "F min stop 300 pts": dict(min_sl_pts=300)}
    EXITS = {"E00 SL only + MA18 exit (no BE, no protection)": dict(protection=0, be_enable=False), "E01 EA default: BE + swing after 500 + MA18": dict(), "E02 Chandelier(22,3.0) after 500 + BE + MA18": dict(protection=2), "E03 Chandelier immediate + BE + MA18 (v13)": dict(protection=2, prot_start_mode=0),
             "E04 Trailing 1000/500/50 + BE + MA18": dict(protection=4), "E05 BE only + MA18": dict(protection=0), "E06 Trailing 1000/500/50 without BE + MA18": dict(protection=4, be_enable=False), "E07 Chandelier + Trailing + BE + MA18": dict(protection=6, prot_start_mode=0), "E08 Swing immediate + BE + MA18": dict(prot_start_mode=0),
             "E09 ATR trail 2.0x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=2.0), "E10 ATR trail 3.0x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=3.0), "E11 ATR trail 1.5x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=1.5), "E12 ATR trail 2.0x after 500 + BE + MA18": dict(protection=8, prot_start_mode=1, trail_start_pts=0, atr_trail_mult=2.0),
             "E13 TWK 3-stage trail (previous strategy) + MA18, no BE": dict(protection=16, be_enable=False), "E14 TWK 3-stage trail alone (no MA18 exit, no BE)": dict(protection=16, be_enable=False, ma_exit=False), "E15 EA default without MA18 exit": dict(ma_exit=False), "E16 Chandelier immediate without MA18 exit + BE": dict(protection=2, prot_start_mode=0, ma_exit=False), "E17 Swing after 500 + MA18, no BE": dict(be_enable=False),
             "E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18": dict(thr_mode=1, be_trigger_pts=100, prot_start_pts=100), "E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18": dict(thr_mode=1, protection=4, be_trigger_pts=100, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10), "E20 R-scaled: BE 1R, swing after 1R, MA18": dict(thr_mode=2, be_trigger_pts=100, prot_start_pts=100), "E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18": dict(thr_mode=2, protection=4, be_trigger_pts=100, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10),
             "E22 Chandelier(22,2.0) immediate + BE + MA18": dict(protection=2, prot_start_mode=0, atr_mult=2.0), "E23 Chandelier(22,4.0) immediate + BE + MA18": dict(protection=2, prot_start_mode=0, atr_mult=4.0), "E24 R-lock: +1R lock +0.5R, swing, MA18, no BE": dict(thr_mode=2, protection=33, lock_trigger_pts=100, lock_level_pts=50, prot_start_pts=100, be_enable=False),
             "E25 Chandelier immediate, no BE, no MA18 (pure chandelier)": dict(protection=2, prot_start_mode=0, be_enable=False, ma_exit=False), "E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing)": dict(protection=4, be_enable=False, ma_exit=False), "E27 BE 1000/10 + swing after 500 + MA18": dict(be_trigger_pts=1000), "E28 BE 2000/10 + swing after 500 + MA18": dict(be_trigger_pts=2000), "E29 time exit 5 bars (not in profit) + EA default": dict(time_exit_bars=5)}
    labs = {}
    for tf in HTFS:
        name = C.TF_NAME[tf]; labs[name] = {}
        for lab, VAR, phase, base_key in (("filters", FILTERS, "S2A-filters", None), ("sl", STOPS, "S2A-stoploss", "A "), ("exits", EXITS, "S2A-exits", "E01")):
            base_p = strat(tf); base, _ = C.evaluate(base_p); rows = {}
            for v, kw in VAR.items():
                p = replace(base_p, **kw); var, tr = C.evaluate(p)
                cls = "base" if (base_key and v.startswith(base_key)) else C.classify(base, var)
                rows[v] = {"metrics": var, "class": cls, "params": kw, "median_risk_usd": float(tr.risk_usd.median()) if len(tr) else None}
                C.log_experiment(phase, v, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"OOS net {var['OOS']['net_profit']} expR {var['OOS'].get('expectancy_r')}", conclusion=cls)
            labs[name][lab] = {"base": base, "rows": rows}
            LOG(name, lab, "done", len(rows), "variants")
    save(labs, "partA_labs.json")

    # ---- walk-forward grid
    GF = {"none": {}, "vol>=1": dict(use_vol_filter=True, vol_filter_min=1.0), "ADX>=25": dict(use_adx=True, adx_min=25.0), "NY 13-22": dict(use_session=True, session_hours=H(13, 22)), "vol>=1+ADX>=25": dict(use_vol_filter=True, vol_filter_min=1.0, use_adx=True, adx_min=25.0)}
    GS = {"swing": {}, "ATR3": dict(sl_mode=1, sl_atr_mult=3.0), "swing3": dict(swing_strength=3)}
    GX = {"E00 SL+MA18": dict(protection=0, be_enable=False), "E01 EA": {}, "E03 Chand+BE": dict(protection=2, prot_start_mode=0), "E04 Trail+BE": dict(protection=4), "E09 ATRtrail2+BE": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=2.0), "E13 TWK": dict(protection=16, be_enable=False), "E16 Chand+BE noMA": dict(protection=2, prot_start_mode=0, ma_exit=False), "E20 R-BE1R+swing1R": dict(thr_mode=2, be_trigger_pts=100, prot_start_pts=100)}
    wf = {}
    for tf in HTFS:
        name = C.TF_NAME[tf]; base_p = strat(tf); runs = {}
        for (fn, fkw), (sn, skw), (xn, xkw) in itertools.product(GF.items(), GS.items(), GX.items()):
            p = replace(base_p, **fkw, **skw, **xkw); tr, st = E.run(p)
            rec = {"params": {**fkw, **skw, **xkw}, "pnl": tr.pnl.to_numpy().copy(), "risk_med": float(tr.risk_usd.median()) if len(tr) else 0.0, "folds": [{k: C.metrics_from_trades(C.slice_trades(tr, *f[k]), 100000.0) for k in ("train", "val", "test")} for f in C.WF_FOLDS]}
            rec.update({k.lower(): C.metrics_from_trades(C.slice_trades(tr, *v), 100000.0) for k, v in C.SPLITS.items()}); rec["all"] = C.metrics_from_trades(tr, 100000.0, E.months_between(C.DATA_START, C.DATA_END))
            runs[f"{fn} | {sn} | {xn}"] = rec
        folds = []
        for i, f in enumerate(C.WF_FOLDS):
            d = pd.DataFrame([{"config": k, "train_trades": r["folds"][i]["train"]["trades"], "train_expR": r["folds"][i]["train"].get("expectancy_r"), "train_pf": r["folds"][i]["train"].get("profit_factor"), "val_expR": r["folds"][i]["val"].get("expectancy_r"), "test_expR": r["folds"][i]["test"].get("expectancy_r"), "test_net": r["folds"][i]["test"]["net_profit"]} for k, r in runs.items()])
            for c in ("train_expR", "val_expR", "test_expR"): d[c] = d[c].astype(float)
            elig = d[d.train_trades >= MIN_TR[tf]].sort_values(["train_expR", "train_pf"], ascending=False); ea = d[d.config == "none | swing | E01 EA"].iloc[0]
            fold = {"fold": i + 1, "train": f["train"], "val": f["val"], "test": f["test"], "configs": int(len(d)), "share_positive_test": round(float((d.test_net > 0).mean()), 3), "ea_test_net": float(ea.test_net)}
            if len(elig):
                b = elig.iloc[0]; passed = elig[elig.val_expR > 0]
                fold.update({"train_best": b.config, "train_best_R": (float(b.train_expR), float(b.val_expR), float(b.test_expR)), "passes_val": bool(b.val_expR > 0), "selected": passed.iloc[0].config if len(passed) else None, "selected_test": (float(passed.iloc[0].test_expR), float(passed.iloc[0].test_net)) if len(passed) else None})
            folds.append(fold)
        d = pd.DataFrame([{"config": k, "dev_trades": r["dev"]["trades"], "dev_expR": r["dev"].get("expectancy_r"), "dev_net": r["dev"]["net_profit"], "val_expR": r["val"].get("expectancy_r"), "val_net": r["val"]["net_profit"], "oos_expR": r["oos"].get("expectancy_r"), "oos_net": r["oos"]["net_profit"], "oos_pf": r["oos"].get("profit_factor"), "all_trades": r["all"]["trades"], "all_net": r["all"]["net_profit"], "all_pf": r["all"].get("profit_factor"), "all_dd": r["all"]["max_dd_usd"], "all_expR": r["all"].get("expectancy_r"), "pos3": bool(r["dev"]["net_profit"] > 0 and r["val"]["net_profit"] > 0 and r["oos"]["net_profit"] > 0)} for k, r in runs.items()])
        d.to_csv(os.path.join(OUT, f"wf_grid_{name}.csv"), index=False)
        rob = d[d.pos3 & (d.dev_trades >= MIN_TR[tf])].sort_values("oos_expR", ascending=False)
        audit = {"configs": int(len(d)), "pos3": int(d.pos3.sum()), "share_dev": round(float((d.dev_net > 0).mean()), 3), "share_val": round(float((d.val_net > 0).mean()), 3), "share_oos": round(float((d.oos_net > 0).mean()), 3), "robust": rob.head(10).to_dict("records")}
        cand = None
        if len(rob):
            cfg = rob.iloc[0].config; params = runs[cfg]["params"]; pc = replace(base_p, **params); sens = {}
            sweeps = {"fast": [14, 16, 18, 20, 22], "trend": [150, 175, 200, 225, 250]}
            if pc.protection & 2: sweeps["atr_mult"] = [pc.atr_mult * f for f in (0.5, 0.75, 1.0, 1.25, 1.5)]; sweeps["chand_lookback"] = [11, 16, 22, 28, 33]
            if pc.protection & 8: sweeps["atr_trail_mult"] = [pc.atr_trail_mult * f for f in (0.75, 0.875, 1.0, 1.125, 1.25)]
            if pc.be_enable: sweeps["be_trigger_pts"] = [int(pc.be_trigger_pts * f) for f in (0.6, 0.8, 1.0, 1.2, 1.4)]
            if pc.use_adx: sweeps["adx_min"] = [20, 22.5, 25, 27.5, 30]
            if pc.use_vol_filter: sweeps["vol_filter_min"] = [0.8, 0.9, 1.0, 1.1, 1.2]
            for pn, vals in sweeps.items():
                sens[pn] = []
                for v in vals:
                    tr, st = E.run(replace(pc, **{pn: v})); ma = C.metrics_from_trades(tr, 100000.0); mo = C.metrics_from_trades(C.slice_trades(tr, *C.SPLITS["OOS"]), 100000.0)
                    sens[pn].append({"value": v, "all_expR": ma.get("expectancy_r"), "all_net": ma["net_profit"], "oos_expR": mo.get("expectancy_r"), "trades": ma["trades"]})
            pnl = runs[cfg]["pnl"]; med = runs[cfg]["risk_med"]
            cand = {"config": cfg, "params": params, "sensitivity": sens, "mc_200": E.monte_carlo(pnl, 200.0), "mc_100x": E.monte_carlo(pnl, max(100 * med, 200.0)), "median_risk": med}
        wf[name] = {"folds": folds, "audit": audit, "candidate": cand, "ea_mc_200": E.monte_carlo(runs["none | swing | E01 EA"]["pnl"], 200.0)}
        LOG(name, "walk-forward done; positive in all splits:", audit["pos3"], "candidate:", cand["config"] if cand else None)
    save(wf, "partA_walkforward.json")


# ====================================================================== Part B: 2023-2026 window, all timeframes
def part_b():
    res = {"baseline": {}, "sessions": {}, "session_filters": {}, "sma": {}}
    months = E.months_between(*P3)
    H = lambda a, b: tuple(range(a, b))
    SESS = {"London 8-17": H(8, 17), "New York 13-22": H(13, 22), "London + New York 8-22": H(8, 22), "Overlap 13-17": H(13, 17), "Tokyo 0-9": H(0, 9), "Sydney 22-07": tuple(list(range(22, 24)) + list(range(0, 7))), "Asia off (8-22 only)": H(8, 22)}
    for tf in ALL_TFS:
        name = C.TF_NAME[tf]; b = {}
        for view, vkw in VIEWS.items():
            b[view] = {}
            for cost in C.COST:
                p = E.Params(tf_minutes=tf, start=P3[0], end=P3[1], **vkw, **C.COST[cost]); tr, st = E.run(p); m = E.metrics(tr, st, p.start_balance, months)
                if view == "strategy":
                    m["splits"] = m_slices(tr, SPLIT3)
                    if cost == "B_real":
                        trb = C.tag_regimes(tr); trb.to_csv(os.path.join(OUT, f"trades_{name}_2023_26_strategy_B_real.csv"), index=False)
                        trb["year"] = trb["time_out"].dt.year
                        m["by_year"] = {int(y): {"trades": int(len(x)), "net": round(float(x.pnl.sum()), 2), "pf": round(float(x.loc[x.pnl > 0, "pnl"].sum() / max(-x.loc[x.pnl < 0, "pnl"].sum(), 1e-9)), 2), "win": round(100 * float((x.pnl > 0).mean()), 1)} for y, x in trb.groupby("year")}
                        # sessions, hours, weekdays (by fill time)
                        s = {"by_session": C.by_group(trb, "session").to_dict("index"), "by_hour": C.by_group(trb, "hour_in").to_dict("index"), "by_weekday": C.by_group(trb, "weekday_in").to_dict("index"), "by_side": C.by_group(trb, "side").to_dict("index")}
                        # EA-style overlapping sessions
                        ea_s = {}
                        for sn, hrs in (("Sydney 22-07", SESS["Sydney 22-07"]), ("Tokyo 0-9", SESS["Tokyo 0-9"]), ("London 8-17", SESS["London 8-17"]), ("New York 13-22", SESS["New York 13-22"])):
                            sub = trb[trb.hour_in.isin(hrs)]
                            ea_s[sn] = {"trades": int(len(sub)), "net": round(float(sub.pnl.sum()), 2), "win_rate": round(100 * float((sub.pnl > 0).mean()), 1) if len(sub) else None, "pf": round(float(sub.loc[sub.pnl > 0, "pnl"].sum() / max(-sub.loc[sub.pnl < 0, "pnl"].sum(), 1e-9)), 2) if len(sub) else None, "expectancy": round(float(sub.pnl.mean()), 3) if len(sub) else None}
                        s["ea_sessions_overlapping"] = ea_s
                        # session x year
                        s["session_by_year"] = {str(k[0]) + "|" + str(k[1]): round(float(v), 2) for k, v in trb.groupby(["session", "year"]).pnl.sum().items()}
                        res["sessions"][name] = s
                b[view][cost] = m
                C.log_experiment("S2B-baseline-2023-26", f"2023-26 baseline ({view})", p, m, cost, "2023-01..2026-09", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), conclusion=f"net {m['net_profit']} PF {m.get('profit_factor')}")
        res["baseline"][name] = b
        LOG(name, "2023-26 baseline: strategy B_real net", b["strategy"]["B_real"]["net_profit"], "PF", b["strategy"]["B_real"].get("profit_factor"))
        # ---- session filter tests (EA UseSessionFilter with each window)
        sf = {}
        base_p = strat(tf, *P3); base_tr, _ = E.run(base_p); base_m = C.metrics_from_trades(base_tr, 100000.0, months); base_m["splits"] = m_slices(base_tr, SPLIT3)
        sf["BASE (all sessions)"] = base_m
        for sn, hrs in SESS.items():
            p = replace(base_p, use_session=True, session_hours=hrs); tr, st = E.run(p); m = C.metrics_from_trades(tr, 100000.0, months); m["splits"] = m_slices(tr, SPLIT3); m["blocked_session"] = st["blocked_session"]
            sf[sn] = m
            C.log_experiment("S2B-session-filter", f"session filter {sn}", p, m, "B_real", "2023-01..2026-09", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"OOS net {m['splits']['OOS']['net_profit']}", conclusion=f"IS {m['splits']['IS']['net_profit']} / OOS {m['splits']['OOS']['net_profit']}")
        res["session_filters"][name] = sf
        LOG(name, "session filters done")
    save(res, "partB_baseline_sessions.json")



def part_b_sma():
    months = E.months_between(*P3)
    # ---- SMA sweeps (resumable: timeframes already in partB_sma.json are skipped)
    FAST = [5, 8, 9, 10, 13, 14, 18, 20, 21, 25, 30, 34, 50]
    TREND = [50, 100, 150, 200, 250, 300]
    PAIRS = [(9, 21), (10, 50), (20, 50), (20, 100), (21, 55), (50, 200), (20, 200), (10, 100), (34, 144), (13, 48), (18, 200)]
    IMPROVED = dict(use_adx=True, adx_min=25.0, protection=2, prot_start_mode=0)
    sma = json.load(open(os.path.join(OUT, "partB_sma.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "partB_sma.json")) else {}
    for tf in ALL_TFS:
        name = C.TF_NAME[tf]
        if name in sma and sma[name].get("recommended") is not None:
            LOG(name, "SMA sweep already saved, skipping"); continue
        base_p = strat(tf, *P3); out = {"fast": {}, "trend": {}, "pairs": {}, "fast_improved": {}}

        def run_one(fast, trend, extra=None, phase="S2B-sma-fast"):
            E._IND_CACHE.clear()          # one indicator set per SMA combination is ~220 MB on M1; never keep them all
            p = replace(base_p, fast=fast, trend=trend, **(extra or {})); tr, st = E.run(p)
            m = C.metrics_from_trades(tr, 100000.0, months); sp = m_slices(tr, SPLIT3)
            rec = {"fast": fast, "trend": trend, "trades": m["trades"], "net": m["net_profit"], "pf": m.get("profit_factor"), "dd": m["max_dd_usd"], "win": m.get("win_rate"), "expR": m.get("expectancy_r"), "exp": m.get("expectancy"), "giveback": m.get("giveback_avg"), "p2l": m.get("profit_to_loss_2usd"),
                   "IS_net": sp["IS"]["net_profit"], "IS_expR": sp["IS"].get("expectancy_r"), "IS_pf": sp["IS"].get("profit_factor"), "IS_trades": sp["IS"]["trades"], "OOS_net": sp["OOS"]["net_profit"], "OOS_expR": sp["OOS"].get("expectancy_r"), "OOS_pf": sp["OOS"].get("profit_factor"), "OOS_trades": sp["OOS"]["trades"],
                   "by_year": {int(y): round(float(v), 2) for y, v in tr.groupby(tr.time_out.dt.year).pnl.sum().items()} if len(tr) else {}}
            C.log_experiment(phase, f"SMA {fast}/{trend}" + (" improved exit" if extra else ""), p, m, "B_real", "2023-01..2026-09", filters=C.filter_desc(p), exit_logic=C.exit_desc(p), oos_result=f"IS net {rec['IS_net']} expR {rec['IS_expR']}; OOS net {rec['OOS_net']} expR {rec['OOS_expR']}", conclusion="sweep")
            return rec, tr

        eq = {}
        for f in FAST:
            rec, tr = run_one(f, 200); out["fast"][f] = rec
            if f in (18,): eq["18/200"] = tr
        # best fast by IS expectancy with enough IS trades
        cands = [r for r in out["fast"].values() if r["IS_trades"] >= MIN_TR[tf]]
        best_is = max(cands, key=lambda r: (r["IS_expR"] if r["IS_expR"] is not None else -9))["fast"] if cands else 18
        out["best_fast_IS"] = best_is
        for tr_ in TREND:
            out["trend"][f"18/{tr_}"] = run_one(18, tr_, phase="S2B-sma-trend")[0]
            if best_is != 18: out["trend"][f"{best_is}/{tr_}"] = run_one(best_is, tr_, phase="S2B-sma-trend")[0]
        for (f, tr_) in PAIRS:
            rec, tr = run_one(f, tr_, phase="S2B-sma-pairs"); out["pairs"][f"{f}/{tr_}"] = rec
        if tf in (60, 240, 1440):
            for f in FAST:
                out["fast_improved"][f] = run_one(f, 200, IMPROVED, phase="S2B-sma-fast-improved")[0]
        # recommendation rule (declared): candidates with IS_expR > 0 and OOS_expR > 0 and >= MIN_TR trades over the window; rank by min(IS, OOS) expectancy; robustness = both neighbours in the fast list also positive OOS
        allrows = list(out["fast"].values()) + list(out["trend"].values()) + list(out["pairs"].values())
        ok = [r for r in allrows if (r["IS_expR"] or -9) > 0 and (r["OOS_expR"] or -9) > 0 and r["trades"] >= MIN_TR[tf]]
        for r in ok:
            fl = FAST; i = fl.index(r["fast"]) if r["fast"] in fl else None
            nb = [out["fast"].get(fl[j]) for j in (i - 1, i + 1) if i is not None and 0 <= j < len(fl)] if r["trend"] == 200 and i is not None else []
            r["neighbours_positive_OOS"] = (sum(1 for x in nb if x and (x["OOS_expR"] or -9) > 0), len(nb))
        ok.sort(key=lambda r: -min(r["IS_expR"], r["OOS_expR"]))
        out["recommended"] = ok[:5]
        sma[name] = out
        LOG(name, "SMA sweep done; best IS fast", best_is, "recommended:", [(r["fast"], r["trend"]) for r in ok[:3]])
        # equity curves for 18/200 vs the top recommendation (for the report)
        if ok:
            r0 = ok[0]; p = replace(base_p, fast=r0["fast"], trend=r0["trend"]); trr, _ = E.run(p)
            trr[["time_out", "pnl"]].to_csv(os.path.join(OUT, f"trades_{name}_2023_26_bestsma.csv"), index=False)
        save(sma, "partB_sma.json")
    save(sma, "partB_sma.json")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("a", "all"): part_a()
    if which in ("b", "all"): part_b(); part_b_sma()
    if which == "sma": part_b_sma()
    LOG("done")
