"""Parameter robustness maps (fast x trend SMA, exit grid, stop grid) selected on TRAIN only, and rolling walk-forward on the
candidate timeframes of each instrument (the timeframes whose scenario-B baseline is positive with >= 60 trades, max 4 per instrument
and config). Writes research/robustness_analysis.md, research/walk_forward_analysis.md, experiments/sweeps.json."""
import itertools, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

HERE = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(ROOT, "backtests", "baseline_metrics.json")))["runs"]
INSTR = sys.argv[1:] or [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in R)]
FASTS = (8, 10, 12, 14, 16, 18, 20, 22, 25, 30); TRENDS = (50, 100, 150, 200, 250, 300)
SF = os.path.join(HERE, "sweeps.json"); OUT = json.load(open(SF)) if os.path.exists(SF) else {"ma_grid": {}, "exit_grid": {}, "stop_grid": {}, "wf": {}}
fmt = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:.3f}")


def cell(instr, tf, cfg, **over):
    tr, _ = C.run(instr, tf, cfg, "B", **over); sm = C.split_metrics(tr, instr)
    return {k: (v["trades"], v.get("exp_usd"), v.get("net_usd"), v.get("pf")) for k, v in sm.items()}


def candidates(instr, cfg_name):
    c = [(tf, R[f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"]["metrics"]) for tf in C.TFS if f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B" in R]
    c = [(tf, m) for tf, m in c if m["net_usd"] > 0 and m["trades"] >= 50]
    return [tf for tf, m in sorted(c, key=lambda x: -x[1]["net_usd"])[:4]]


n_exp = 0
for instr in INSTR:
    E._PATH_CACHE.clear(); E._TF_CACHE.clear(); E._IND_CACHE.clear()
    for cfg_name, cfg in C.CONFIGS.items():
        for tf in candidates(instr, cfg_name):
            t0 = time.time(); key = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}"
            grid = {(f, t): cell(instr, tf, cfg, fast=f, trend=t) for f, t in itertools.product(FASTS, TRENDS)}; E._IND_CACHE.clear()
            OUT["ma_grid"][key] = {f"{f}/{t}": v for (f, t), v in grid.items()}
            if cfg_name == "ASIS":
                ex = {(be, sb, eb): cell(instr, tf, cfg, be_trigger_pts=be, be_enable=be > 0, swing_buffer_pts=sb, entry_buffer_pts=eb) for be in (0, 250, 500, 1000, 2000) for sb in (0, 50, 200) for eb in (0, 10, 40)}
            else:
                ex = {(be, ts, td): cell(instr, tf, cfg, be_trigger_pts=be, be_enable=be > 0, trail_start_pts=ts, trail_dist_pts=td) for be in (0, 100, 200, 300) for ts in (200, 300, 500, 700) for td in (25, 50, 100, 200)}
            OUT["exit_grid"][key] = {"/".join(str(x) for x in k): v for k, v in ex.items()}
            stp = {(ss, sw): cell(instr, tf, cfg, swing_strength=ss, swing_search=sw) for ss in (1, 2, 3, 4) for sw in (50, 100)}
            OUT["stop_grid"][key] = {f"{a}/{b}": v for (a, b), v in stp.items()}; E._IND_CACHE.clear()
            wf_rows = []
            for (tr_a, tr_b), (te_a, te_b) in C.WF_FOLDS:
                best = None
                for f, t in itertools.product(FASTS, TRENDS):
                    tr, _ = C.run(instr, tf, cfg, "B", start=tr_a, end=tr_b, fast=f, trend=t)
                    if len(tr) >= 30 and (best is None or tr.usd.mean() > best[2]): best = (f, t, tr.usd.mean(), len(tr))
                E._IND_CACHE.clear()
                if best is None: continue
                te_sel, _ = C.run(instr, tf, cfg, "B", start=te_a, end=te_b, fast=best[0], trend=best[1]); te_base, _ = C.run(instr, tf, cfg, "B", start=te_a, end=te_b)
                wf_rows.append({"train": f"{tr_a}..{tr_b}", "test": f"{te_a}..{te_b}", "chosen fast/trend": f"{best[0]}/{best[1]}", "train exp $": round(best[2], 3), "train trades": best[3], "test trades": len(te_sel),
                                "test net (chosen) $": round(float(te_sel.usd.sum()), 2), "test net (18/200) $": round(float(te_base.usd.sum()), 2)})
            OUT["wf"][key] = wf_rows
            tr_pos = sum(1 for v in grid.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30)
            both = sum(1 for v in grid.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and (v["VAL"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
            n_exp += 1
            C.log_experiment(f"SWEEP-{instr}-{n_exp:03d}", instr, tf, cfg_name, {"fast": list(FASTS), "trend": list(TRENDS)}, "none", (C.DATA_START, C.DATA_END), "B", {"trades": grid[(18, 200)]["TRAIN"][0]}, None, "robustness map",
                             f"{tr_pos}/{len(grid)} MA cells TRAIN-positive, {both} also VAL+OOS; WF chosen>base {sum(1 for r in wf_rows if r['test net (chosen) $'] > r['test net (18/200) $'])}/{len(wf_rows)}")
            print(f"{key}: MA TRAIN-positive {tr_pos}/{len(grid)}, all-split {both}; WF folds {len(wf_rows)}; {time.time()-t0:.0f}s", flush=True)
    json.dump(OUT, open(SF, "w"), indent=1, default=str)

# ---------------------------------------------------------------- markdown
L_rob = ["# Parameter robustness (scenario B, selection on TRAIN only)\n", "Each map: expectancy in USD per 0.01 lot per trade on TRAIN (2021-09..2024-08) and, in brackets, on OOS (2025-09..2026-09). Cells with < 30 TRAIN trades marked *. A genuine edge is a broad region positive in both.\n"]
L_wf = ["# Walk-forward analysis\n", "Rolling folds: 24 months of training, the next 6 months traded; the best TRAIN-window (fast, trend) pair (>= 30 trades) is re-chosen each fold and compared with the fixed 18/200 on the same test months. Scenario B, USD per 0.01 lot.\n"]
for key, g in OUT["ma_grid"].items():
    instr, cfg_name, tfn = key.split("|"); ex = OUT["exit_grid"].get(key, {}); stp = OUT["stop_grid"].get(key, {}); wf = OUT["wf"].get(key, [])
    tr_pos = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30)
    both = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and (v["VAL"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
    b = g.get("18/200", {"TRAIN": [None, None], "VAL": [None, None], "OOS": [None, None]})
    L_rob.append(f"\n## {C.NAME[instr]} {tfn} {cfg_name}\n{tr_pos} of {len(g)} MA cells positive on TRAIN (>= 30 trades); {both} also positive on VAL and OOS. 18/200: TRAIN {fmt(b['TRAIN'][1])}, VAL {fmt(b['VAL'][1])}, OOS {fmt(b['OOS'][1])} $/trade.\n")
    L_rob.append("| fast \\ trend | " + " | ".join(str(t) for t in TRENDS) + " |"); L_rob.append("|---" * (len(TRENDS) + 1) + "|")
    for f in FASTS:
        L_rob.append(f"| {f} | " + " | ".join((lambda v: f"{fmt(v['TRAIN'][1])}{'*' if v['TRAIN'][0] < 30 else ''} [{fmt(v['OOS'][1])}]")(g[f"{f}/{t}"]) for t in TRENDS) + " |")
    ex_pos = sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0); ex_both = sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
    if ex:
        bk = max(ex, key=lambda k: ex[k]["TRAIN"][1] or -1e9)
        L_rob.append(f"\n**Exit grid** ({len(ex)} cells: {'BE ticks / swing buffer / entry buffer' if cfg_name == 'ASIS' else 'BE ATR/100 / trail start / trail distance'}): {ex_pos} positive on TRAIN, {ex_both} also on OOS. Best TRAIN cell {bk}: TRAIN {fmt(ex[bk]['TRAIN'][1])}, VAL {fmt(ex[bk]['VAL'][1])}, OOS {fmt(ex[bk]['OOS'][1])} $/trade.\n")
    L_rob.append("**Stop grid** (swing strength / search): " + "; ".join(f"{k}: TRAIN {fmt(v['TRAIN'][1])} OOS {fmt(v['OOS'][1])}" for k, v in stp.items()) + "\n")
    L_wf.append(f"\n## {C.NAME[instr]} {tfn} {cfg_name}\n"); L_wf.append(C.md_table(pd.DataFrame(wf)) if wf else "no fold with 30 training trades")
    if wf:
        ts = sum(r["test net (chosen) $"] for r in wf); tb = sum(r["test net (18/200) $"] for r in wf); won = sum(1 for r in wf if r["test net (chosen) $"] > r["test net (18/200) $"])
        L_wf.append(f"\nAll test months: chosen pairs {ts:,.2f} $ vs fixed 18/200 {tb:,.2f} $; chosen beat fixed in {won}/{len(wf)} folds.\n")
open(os.path.join(ROOT, "research", "robustness_analysis.md"), "w", encoding="utf-8").write("\n".join(L_rob)); open(os.path.join(ROOT, "research", "walk_forward_analysis.md"), "w", encoding="utf-8").write("\n".join(L_wf))
print("written robustness_analysis.md, walk_forward_analysis.md")
