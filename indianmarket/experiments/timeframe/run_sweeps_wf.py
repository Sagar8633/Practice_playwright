"""Parameter robustness maps and walk-forward validation on the candidate timeframes.

Selection is done on TRAIN (2022-01..2024-08) only; VAL and OOS are reported for every cell so the map shows whether a
TRAIN-positive region stays positive later. Walk-forward: for each rolling fold the best (fast, trend) pair by TRAIN-window
expectancy (>= 30 trades) is chosen and traded in the next 6 months; the concatenated test months are compared with the fixed 18/200.
Writes research/robustness_analysis.md, research/walk_forward_analysis.md and experiments/timeframe/sweeps.json."""
import itertools, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO, engine_in as E

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = {"nifty50": (15, 30, 60, 120, 240), "banknifty": (15, 30, 60)}
FASTS = (8, 10, 12, 14, 16, 18, 20, 22, 25, 30); TRENDS = (50, 100, 150, 200, 250, 300)
OUT = {"ma_grid": {}, "exit_grid": {}, "stop_grid": {}, "wf": {}}
n_exp = 0


def cell(instr, tf, cfg, **over):
    tr, st = C.run(instr, tf, cfg, "B", **over)
    sm = C.split_metrics(tr, instr)
    return {k: (v["trades"], v.get("exp_pts"), v.get("net_pts"), v.get("pf")) for k, v in sm.items()}, tr


def fmt(v):
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:.2f}")


L_rob = ["# Parameter robustness (scenario B costs; selection on TRAIN only)\n",
         "Each map shows the expectancy in points per trade on TRAIN (2022-01..2024-08) and, in brackets, on OOS (2025-09..2026-09). A genuine edge shows as a broad region that is positive in both; "
         "a single positive cell surrounded by negatives is noise or overfitting. Cells with fewer than 30 TRAIN trades are marked with *.\n"]
L_wf = ["# Walk-forward analysis\n", "Rolling folds: 24 months of training, the next 6 months traded; the (fast, trend) pair with the best TRAIN-window expectancy (>= 30 trades) is chosen each fold and compared with the fixed 18/200 on the same test months. "
        "Scenario B costs, points per unit.\n"]
E._IND_CACHE.clear()
for instr, tfs in CANDIDATES.items():
    for cfg_name in C.CONFIGS:
        cfg = C.CONFIGS[cfg_name]
        for tf in tfs:
            t0 = time.time(); key = f"{instr}|{cfg_name}|{C.TF_NAME[tf]}"
            # ------------------------------------------------ MA grid
            grid = {}
            for f, t in itertools.product(FASTS, TRENDS):
                if f >= t: continue
                sm, _ = cell(instr, tf, cfg, fast=f, trend=t); grid[(f, t)] = sm
            E._IND_CACHE.clear()
            OUT["ma_grid"][key] = {f"{f}/{t}": v for (f, t), v in grid.items()}
            tr_pos = sum(1 for v in grid.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30)
            both = sum(1 for v in grid.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and v["OOS"][1] is not None and v["OOS"][1] > 0 and v["VAL"][1] is not None and v["VAL"][1] > 0)
            L_rob.append(f"\n## {CO.INSTR[instr]['name']} {C.TF_NAME[tf]} {cfg_name}: fast x trend SMA (TRAIN exp pts [OOS exp pts])\n")
            L_rob.append(f"{tr_pos} of {len(grid)} cells positive on TRAIN with >= 30 trades; {both} of those also positive on VAL and OOS. Baseline 18/200: TRAIN {fmt(grid[(18, 200)]['TRAIN'][1])}, VAL {fmt(grid[(18, 200)]['VAL'][1])}, OOS {fmt(grid[(18, 200)]['OOS'][1])} pts/trade.\n")
            hdr = "| fast \\ trend | " + " | ".join(str(t) for t in TRENDS) + " |"; L_rob.append(hdr); L_rob.append("|---" * (len(TRENDS) + 1) + "|")
            for f in FASTS:
                cells = []
                for t in TRENDS:
                    v = grid.get((f, t))
                    if v is None: cells.append(""); continue
                    star = "*" if v["TRAIN"][0] < 30 else ""
                    cells.append(f"{fmt(v['TRAIN'][1])}{star} [{fmt(v['OOS'][1])}]")
                L_rob.append(f"| {f} | " + " | ".join(cells) + " |")
            # ------------------------------------------------ exit grid
            if cfg_name == "ASIS":
                ex = {(be, sb, eb): cell(instr, tf, cfg, be_trigger_pts=be, be_enable=be > 0, swing_buffer_pts=sb, entry_buffer_pts=eb)[0]
                      for be in (0, 250, 500, 1000, 2000) for sb in (0, 50, 200) for eb in (0, 10, 40)}
                lab = "BE trigger ticks / swing buffer ticks / entry buffer ticks (0 BE = off)"
            else:
                ex = {(be, ts, td): cell(instr, tf, cfg, be_trigger_pts=be, be_enable=be > 0, trail_start_pts=ts, trail_dist_pts=td)[0]
                      for be in (0, 100, 200, 300) for ts in (200, 300, 500, 700) for td in (25, 50, 100, 200)}
                lab = "BE (hundredths of ATR, 0 = off) / trail start / trail distance"
            OUT["exit_grid"][key] = {"/".join(str(x) for x in k): v for k, v in ex.items()}
            pos = sum(1 for v in ex.values() if v["TRAIN"][1] and v["TRAIN"][1] > 0); both = sum(1 for v in ex.values() if v["TRAIN"][1] and v["TRAIN"][1] > 0 and v["OOS"][1] and v["OOS"][1] > 0)
            L_rob.append(f"\n**Exit grid** ({lab}): {pos}/{len(ex)} cells positive on TRAIN, {both} also positive on OOS. Best TRAIN cell: " +
                         (lambda k: f"{k} -> TRAIN {fmt(ex[k]['TRAIN'][1])}, VAL {fmt(ex[k]['VAL'][1])}, OOS {fmt(ex[k]['OOS'][1])} pts/trade")(max(ex, key=lambda k: ex[k]["TRAIN"][1] or -1e9)) + "\n")
            # ------------------------------------------------ stop grid
            stp = {(ss, sw): cell(instr, tf, cfg, swing_strength=ss, swing_search=sw)[0] for ss in (1, 2, 3, 4) for sw in (50, 100)}
            OUT["stop_grid"][key] = {f"{a}/{b}": v for (a, b), v in stp.items()}
            L_rob.append("**Stop grid** (swing strength / search bars): " + "; ".join(f"{a}/{b}: TRAIN {fmt(v['TRAIN'][1])} OOS {fmt(v['OOS'][1])}" for (a, b), v in stp.items()) + "\n")
            E._IND_CACHE.clear()
            # ------------------------------------------------ walk-forward on the MA grid
            wf_rows = []; wf_sel = []; wf_base = []
            for (tr_a, tr_b), (te_a, te_b) in C.WF_FOLDS:
                best = None
                for f, t in itertools.product(FASTS, TRENDS):
                    if f >= t: continue
                    tr, _ = C.run(instr, tf, cfg, "B", start=tr_a, end=tr_b, fast=f, trend=t)
                    if len(tr) >= 30 and (best is None or tr.pts_net.mean() > best[2]):
                        best = (f, t, tr.pts_net.mean(), len(tr))
                E._IND_CACHE.clear()
                if best is None:
                    continue
                te_sel, _ = C.run(instr, tf, cfg, "B", start=te_a, end=te_b, fast=best[0], trend=best[1])
                te_base, _ = C.run(instr, tf, cfg, "B", start=te_a, end=te_b)
                wf_sel.append(te_sel); wf_base.append(te_base)
                wf_rows.append({"train": f"{tr_a}..{tr_b}", "test": f"{te_a}..{te_b}", "chosen fast/trend": f"{best[0]}/{best[1]}", "train exp": round(best[2], 2), "train trades": best[3],
                                "test trades": len(te_sel), "test net (chosen)": round(float(te_sel.pts_net.sum()), 0), "test net (18/200)": round(float(te_base.pts_net.sum()), 0)})
            OUT["wf"][key] = wf_rows
            L_wf.append(f"\n## {CO.INSTR[instr]['name']} {C.TF_NAME[tf]} {cfg_name}\n"); L_wf.append(C.md_table(pd.DataFrame(wf_rows)))
            if wf_sel:
                s = pd.concat(wf_sel); b = pd.concat(wf_base)
                pf = lambda x: (x[x > 0].sum() / max(1e-9, -x[x < 0].sum()))
                L_wf.append(f"\nAll test months together: chosen parameters {len(s)} trades, net {s.pts_net.sum():,.0f} pts, PF {pf(s.pts_net):.2f}, exp {s.pts_net.mean():.2f} pts/trade; "
                            f"fixed 18/200: {len(b)} trades, net {b.pts_net.sum():,.0f} pts, PF {pf(b.pts_net):.2f}, exp {b.pts_net.mean():.2f} pts/trade. Folds where the chosen pair beat 18/200: {sum(1 for r in wf_rows if r['test net (chosen)'] > r['test net (18/200)'])}/{len(wf_rows)}.\n")
            n_exp += 1
            C.log_experiment(f"SWEEP-{n_exp:03d}", instr, tf, cfg_name, {"fast": list(FASTS), "trend": list(TRENDS), "exit_grid": lab}, "none", (C.DATA_START, C.DATA_END), "B",
                             {"trades": grid[(18, 200)]["TRAIN"][0]}, None, "robustness map", f"{tr_pos}/{len(grid)} MA cells TRAIN-positive, {both} exit cells positive TRAIN and OOS; WF folds chosen>base {sum(1 for r in wf_rows if r['test net (chosen)'] > r['test net (18/200)'])}/{len(wf_rows)}")
            print(f"{key}: MA grid TRAIN-positive {tr_pos}/{len(grid)}; WF folds {len(wf_rows)}; {time.time()-t0:.0f}s", flush=True)
json.dump(OUT, open(os.path.join(HERE, "sweeps.json"), "w"), indent=1, default=str)
open(os.path.join(ROOT, "research", "robustness_analysis.md"), "w", encoding="utf-8").write("\n".join(L_rob))
open(os.path.join(ROOT, "research", "walk_forward_analysis.md"), "w", encoding="utf-8").write("\n".join(L_wf))
print("written robustness_analysis.md and walk_forward_analysis.md")
