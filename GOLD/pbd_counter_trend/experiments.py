"""Controlled experiments: one variable at a time from the pre-registered baseline.

Each experiment re-detects structures with ONE parameter changed (or applies ONE signal-level
filter) and reports expectancy / PF / trade count per period.  Nothing is selected on OOS.

Outputs results/experiments/<name>.csv and results/experiments/index.json
"""
import json
import os
import sys
import time
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, period_table, fmt, load_all, PLAYBOOKS
from pbd.structure import BASELINE
from pbd.engine import summarize, simulate, COSTS
from pbd.data import SPLITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "experiments")
os.makedirs(OUT, exist_ok=True)
PBS = ["A_pingpong", "B1_pullback"]


def row_of(tr, label, variant, pb, extra=None):
    tk = tr[tr["taken"] == True]
    out = []
    for period in [p[0] for p in SPLITS] + ["ALL"]:
        sel = tk if period == "ALL" else tk[tk["period"] == period]
        s = summarize(sel)
        out.append(dict(experiment=label, variant=variant, playbook=pb, period=period, n=s.get("n", 0),
                        win_rate=s.get("win_rate", np.nan), expectancy=s.get("expectancy", np.nan), pf=s.get("pf", np.nan),
                        total_r=s.get("total_r", np.nan), max_dd_r=s.get("max_dd_r", np.nan),
                        median_hold_h=s.get("median_hold_h", np.nan), max_loss_streak=s.get("max_loss_streak", np.nan),
                        r_gross_exp=float(sel["r_gross"].mean()) if len(sel) else np.nan, **(extra or {})))
    return out


def param_sweep(name, param, values, pbs=PBS, cost="real"):
    rows = []
    for v in values:
        for pb in pbs:
            _, _, tr = run({param: v}, playbook=pb, cost=cost)
            rows += row_of(tr, name, f"{param}={v}", pb, {"param": param, "value": v})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    return df


def signal_filter_sweep(name, filters, pbs=PBS, cost="real"):
    """filters: dict variant -> predicate on the signals frame (keep rows where True)."""
    rows = []
    for variant, pred in filters.items():
        for pb in pbs:
            _, _, tr = run(playbook=pb, cost=cost, signal_filter=pred)
            rows += row_of(tr, name, variant, pb)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    return df


def show(df, cols=("variant", "playbook", "period", "n", "win_rate", "expectancy", "pf", "total_r", "max_dd_r", "median_hold_h")):
    print(fmt(df[list(cols)]))


def main(which=None):
    t0 = time.time()
    index = {}

    def do(name, fn):
        if which and name not in which:
            return
        t = time.time()
        df = fn()
        index[name] = {"rows": len(df), "seconds": round(time.time() - t, 1)}
        print(f"\n##### {name} ({time.time() - t:.0f}s)")
        show(df[df["period"].isin(["DEV", "VAL", "OOS"])])

    # ---- Part 3A: impulse definition sensitivity (not selected on P&L)
    do("impulse_definition", lambda: param_sweep("impulse_definition", "imp_def", ["atr", "pct", "rangeexp", "consec"]))
    do("impulse_k", lambda: param_sweep("impulse_k", "imp_k", [2.5, 3.0, 3.5, 4.0, 5.0]))
    do("impulse_N", lambda: param_sweep("impulse_N", "imp_N", [4, 8, 12, 16]))
    # ---- Part 3B/C: range definition
    do("range_min_bars", lambda: param_sweep("range_min_bars", "rng_min_bars", [4, 8, 12, 16, 24]))
    do("range_max_width", lambda: param_sweep("range_max_width", "rng_max_width_imp", [0.4, 0.6, 0.8]))
    do("range_min_width", lambda: param_sweep("range_min_width", "rng_min_width_atr", [0.5, 1.0, 1.5, 2.0]))
    do("range_max_drift", lambda: param_sweep("range_max_drift", "rng_max_drift", [0.25, 0.5, 0.75]))
    do("range_max_bars", lambda: param_sweep("range_max_bars", "rng_max_bars", [96, 288, 576]))
    # ---- Part 3D/E: breakout and pullback definitions
    do("breakout_penetration", lambda: param_sweep("breakout_penetration", "bo_pen_atr", [0.0, 0.25, 0.5, 1.0], pbs=["B1_pullback", "B2_immediate"]))
    do("breakout_confirmation", lambda: param_sweep("breakout_confirmation", "bo_conf", ["close", "bigbar", "volume", "both"], pbs=["B1_pullback", "B2_immediate"]))
    do("pullback_depth", lambda: param_sweep("pullback_depth", "pb_depth_atr", [0.0, 0.25, 0.5, 1.0], pbs=["B1_pullback"]))
    do("pullback_window", lambda: param_sweep("pullback_window", "pb_bars", [8, 16, 32], pbs=["B1_pullback"]))
    # ---- Part 9 E1: stop methodology
    do("stop_pingpong", lambda: param_sweep("stop_pingpong", "pp_stop_atr", [0.25, 0.5, 1.0, 1.5, 2.0], pbs=["A_pingpong"]))
    do("stop_breakout", lambda: param_sweep("stop_breakout", "bo_stop_atr", [0.25, 0.5, 1.0, 1.5], pbs=["B1_pullback"]))
    do("target_pingpong", lambda: param_sweep("target_pingpong", "pp_target", [0.5, 0.7, 0.9, 1.0], pbs=["A_pingpong"]))
    do("zone_pingpong", lambda: param_sweep("zone_pingpong", "zone", [0.1, 0.2, 0.3], pbs=["A_pingpong"]))
    do("max_hold", lambda: param_sweep("max_hold", "max_hold_bars", [16, 96, 288], pbs=PBS))
    # ---- Part 4 / 9 E3: session filters
    sess = {
        "A_all_sessions": lambda s: s["session"].notna(),
        "B_london_only": lambda s: s["session"] == "london",
        "C_newyork_only": lambda s: s["session"].isin(["newyork"]),
        "D_london_plus_ny": lambda s: s["session"].isin(["london", "overlap", "newyork"]),
        "E_overlap_only": lambda s: s["session"] == "overlap",
        "F_asia_only": lambda s: s["session"] == "asia",
        "G_no_offhours": lambda s: s["session"] != "offhours",
    }
    do("session_filter", lambda: signal_filter_sweep("session_filter", sess))
    # ---- Part 9 E4: volatility filter
    vol = {
        "no_filter": lambda s: s["atr_pct"].notna() | s["atr_pct"].isna(),
        "atr_pct<0.9": lambda s: s["atr_pct"] < 0.9,
        "atr_pct<0.8": lambda s: s["atr_pct"] < 0.8,
        "atr_pct>0.2": lambda s: s["atr_pct"] > 0.2,
        "0.2<atr_pct<0.8": lambda s: (s["atr_pct"] > 0.2) & (s["atr_pct"] < 0.8),
    }
    do("volatility_filter", lambda: signal_filter_sweep("volatility_filter", vol))
    # ---- news filter (proxy)
    news = {"no_filter": lambda s: s["session"].notna(), "skip_news_slots": lambda s: s["news_slot"] == "",
            "skip_0830_only": lambda s: s["news_slot"] != "us0830"}
    do("news_filter", lambda: signal_filter_sweep("news_filter", news))
    # ---- VA proximity
    va = {"no_filter": lambda s: s["session"].notna(),
          "boundary_within_1ATR_of_VAH_or_VAL": lambda s: np.minimum(s["dist_vah_atr"].abs(), s["dist_val_atr"].abs()) <= 1.0,
          "boundary_within_2ATR": lambda s: np.minimum(s["dist_vah_atr"].abs(), s["dist_val_atr"].abs()) <= 2.0,
          "boundary_beyond_2ATR": lambda s: np.minimum(s["dist_vah_atr"].abs(), s["dist_val_atr"].abs()) > 2.0,
          "range_outside_VA": lambda s: (s["rl"] > s["vah"]) | (s["rh"] < s["val"]),
          "range_inside_VA": lambda s: (s["rl"] >= s["val"]) & (s["rh"] <= s["vah"]),
          "dev_VA_within_1ATR": lambda s: np.minimum((s["boundary"] - s["vah_dev"]).abs(), (s["boundary"] - s["val_dev"]).abs()) <= s["atr14"]}
    do("va_proximity", lambda: signal_filter_sweep("va_proximity", va))
    # ---- touches
    touch = {"no_filter": lambda s: s["session"].notna(), "touches_side<=2": lambda s: s["touches_side"] <= 2,
             "touches_side>=2": lambda s: s["touches_side"] >= 2, "touches_side<=1": lambda s: s["touches_side"] <= 1}
    do("max_touches", lambda: signal_filter_sweep("max_touches", touch, pbs=["A_pingpong"]))
    # ---- P vs B and side
    pbside = {"P_long": lambda s: (s["stype"] == "P") & (s["side"] == "long"), "P_short": lambda s: (s["stype"] == "P") & (s["side"] == "short"),
              "B_long": lambda s: (s["stype"] == "B") & (s["side"] == "long"), "B_short": lambda s: (s["stype"] == "B") & (s["side"] == "short")}
    do("structure_side", lambda: signal_filter_sweep("structure_side", pbside))
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
    print("total %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
