"""Part 10 / 11: overfitting control and cost sensitivity.

1. Parameter-sensitivity grids (2-D) on DEV, VAL, OOS separately: the result must not depend
   on a single cell.
2. Walk-forward: for each test year Y >= 2023, pick the best single-parameter variant on all
   data BEFORE Y (by expectancy with >= 100 trades) and evaluate it on Y.  Then the same with
   the pre-registered single-filter candidates.
3. Cost sensitivity: spread multiplier 0 / 0.5 / 1 / 1.5 / 2, slippage 0 / 0.1 / 0.2, commission
   0 / 0.07 USD per oz (ECN 7 USD per lot), and execution delay 1 / 5 minutes.

Outputs results/robustness/*.csv
"""
import json
import os
import sys
import time
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, load_all, fmt, PLAYBOOKS
from pbd.structure import BASELINE
from pbd.engine import simulate, summarize, COSTS
from pbd.data import SPLITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "robustness")
os.makedirs(OUT, exist_ok=True)


def cell(tr, period=None, year=None):
    tk = tr[tr["taken"] == True]
    if period:
        tk = tk[tk["period"] == period]
    if year:
        tk = tk[pd.to_datetime(tk["entry_time"]).dt.year == year]
    s = summarize(tk)
    return dict(n=s.get("n", 0), expectancy=s.get("expectancy", np.nan), pf=s.get("pf", np.nan),
                total_r=s.get("total_r", np.nan), win_rate=s.get("win_rate", np.nan), max_dd_r=s.get("max_dd_r", np.nan))


def grid(name, p1, v1, p2, v2, pb):
    rows = []
    for a in v1:
        for b in v2:
            _, _, tr = run({p1: a, p2: b}, playbook=pb, cost="real")
            for period in ["DEV", "VAL", "OOS", None]:
                rows.append(dict(grid=name, playbook=pb, **{p1: a, p2: b}, period=period or "ALL", **cell(tr, period)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, f"grid_{name}.csv"), index=False)
    return df


def walk_forward(pb, candidates):
    """candidates: dict label -> (param, value).  Choose on data before year Y, test on Y."""
    years = [2023, 2024, 2025, 2026]
    rows = []
    runs = {}
    for label, (param, value) in candidates.items():
        _, _, tr = run({param: value} if param else None, playbook=pb, cost="real")
        runs[label] = tr[tr["taken"] == True].copy()
        runs[label]["year"] = pd.to_datetime(runs[label]["entry_time"]).dt.year
    for Y in years:
        best = None
        for label, tk in runs.items():
            tr_ = tk[tk["year"] < Y]
            if len(tr_) < 100:
                continue
            e = tr_["r_net"].mean()
            if best is None or e > best[1]:
                best = (label, e, len(tr_))
        if best is None:
            continue
        label = best[0]
        te = runs[label][runs[label]["year"] == Y]
        base = runs["baseline"][runs["baseline"]["year"] == Y]
        rows.append(dict(playbook=pb, test_year=Y, chosen=label, train_expectancy=best[1], train_n=best[2],
                         test_n=len(te), test_expectancy=te["r_net"].mean() if len(te) else np.nan,
                         test_pf=summarize(te).get("pf", np.nan) if len(te) else np.nan,
                         baseline_test_n=len(base), baseline_test_expectancy=base["r_net"].mean() if len(base) else np.nan))
    return pd.DataFrame(rows)


def cost_sensitivity(pb):
    rows = []
    m1, m15, path = load_all()
    st, sg, _ = run(playbook=pb, cost="real")
    variants = {
        "ideal": dict(spread_mode="zero", slip=0.0, comm_oz=0.0, swap=False, delay_m1=0, fill="signal_close"),
        "spread_only": dict(spread_mode="xm", slip=0.0, comm_oz=0.0, swap=False, delay_m1=0, fill="next_open"),
        "real_slip0": dict(spread_mode="xm", slip=0.0, comm_oz=0.0, swap=True, delay_m1=1, fill="next_open"),
        "real": COSTS["real"],
        "real_slip0.2": dict(spread_mode="xm", slip=0.2, comm_oz=0.0, swap=True, delay_m1=1, fill="next_open"),
        "real_ecn_comm": dict(spread_mode="xm", slip=0.1, comm_oz=0.07, swap=True, delay_m1=1, fill="next_open"),
        "real_delay5": dict(spread_mode="xm", slip=0.1, comm_oz=0.0, swap=True, delay_m1=5, fill="next_open"),
    }
    for label, c in variants.items():
        tr = simulate(sg, path, m15, c, BASELINE, one_position=True, playbook=PLAYBOOKS[pb])
        for period in ["DEV", "VAL", "OOS", None]:
            rows.append(dict(playbook=pb, variant=label, period=period or "ALL", **cell(tr, period),
                             spread_r=float(tr[tr.taken == True]["spread_r"].mean())))
    # spread multipliers
    for mult in [0.5, 1.5, 2.0]:
        m15x = m15.copy(); m15x["spread_usd"] = m15x["spread_usd"] * mult
        sgx = sg.copy(); sgx["spread_usd"] = sgx["spread_usd"] * mult
        tr = simulate(sgx, path, m15x, COSTS["real"], BASELINE, one_position=True, playbook=PLAYBOOKS[pb])
        for period in ["DEV", "VAL", "OOS", None]:
            rows.append(dict(playbook=pb, variant=f"real_spread_x{mult}", period=period or "ALL", **cell(tr, period),
                             spread_r=float(tr[tr.taken == True]["spread_r"].mean())))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, f"costs_{pb}.csv"), index=False)
    return df


def main():
    t0 = time.time()
    for pb in ["A_pingpong", "B1_pullback"]:
        print(f"\n### cost sensitivity {pb}")
        print(fmt(cost_sensitivity(pb)))
    print("\n### grid impulse_k x rng_min_bars (A)")
    g = grid("impk_x_minbars_A", "imp_k", [2.5, 3.5, 5.0], "rng_min_bars", [4, 8, 16], "A_pingpong")
    print(fmt(g[g.period != "ALL"]))
    print("\n### grid pp_stop_atr x zone (A)")
    g = grid("stop_x_zone_A", "pp_stop_atr", [0.5, 1.0, 2.0], "zone", [0.1, 0.2, 0.3], "A_pingpong")
    print(fmt(g[g.period != "ALL"]))
    print("\n### grid imp_k x rng_min_bars (B1)")
    g = grid("impk_x_minbars_B1", "imp_k", [2.5, 3.5, 5.0], "rng_min_bars", [4, 8, 16], "B1_pullback")
    print(fmt(g[g.period != "ALL"]))
    print("\n### grid bo_stop_atr x pb_depth_atr (B1)")
    g = grid("stop_x_depth_B1", "bo_stop_atr", [0.5, 1.0, 1.5], "pb_depth_atr", [0.0, 0.25, 0.5], "B1_pullback")
    print(fmt(g[g.period != "ALL"]))
    cands_A = {"baseline": (None, None), "stop1.0": ("pp_stop_atr", 1.0), "stop2.0": ("pp_stop_atr", 2.0),
               "minbars16": ("rng_min_bars", 16), "minwidth1.5": ("rng_min_width_atr", 1.5), "impk5": ("imp_k", 5.0),
               "target0.5": ("pp_target", 0.5), "zone0.1": ("zone", 0.1)}
    cands_B = {"baseline": (None, None), "stop1.0": ("bo_stop_atr", 1.0), "stop1.5": ("bo_stop_atr", 1.5),
               "minbars16": ("rng_min_bars", 16), "pen0.5": ("bo_pen_atr", 0.5), "depth0.5": ("pb_depth_atr", 0.5),
               "impk5": ("imp_k", 5.0), "conf_volume": ("bo_conf", "volume")}
    wf = pd.concat([walk_forward("A_pingpong", cands_A), walk_forward("B1_pullback", cands_B)])
    wf.to_csv(os.path.join(OUT, "walk_forward.csv"), index=False)
    print("\n### walk-forward\n" + fmt(wf))
    print("total %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
