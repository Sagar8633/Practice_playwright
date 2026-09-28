"""Staged, pre-specified combination of the single changes that improved expectancy AND
profit factor in BOTH the development and validation periods (the retention rule written
down before the experiments were run).  Each stage adds ONE change; the increment is
measured on DEV and VAL; OOS is read once, at the end, and never used for selection.

Also: bootstrap confidence intervals, ideal-vs-real, and yearly breakdown for each stage.
"""
import json
import os
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, load_all, fmt
from pbd.engine import summarize
from pbd.data import SPLITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "candidates")
os.makedirs(OUT, exist_ok=True)

STAGES = {
    "A_pingpong": [
        ("baseline", {}, None),
        ("+stop 1.5 ATR", {"pp_stop_atr": 1.5}, None),
        ("+overlap+london session", {"pp_stop_atr": 1.5}, lambda s: s["session"].isin(["overlap", "london"])),
        ("+cost gate spread<=15% stop", {"pp_stop_atr": 1.5},
         lambda s: s["session"].isin(["overlap", "london"]) & (s["spread_usd"] / s["risk"] <= 0.15)),
        ("+impulse <= 15 ATR", {"pp_stop_atr": 1.5},
         lambda s: s["session"].isin(["overlap", "london"]) & (s["spread_usd"] / s["risk"] <= 0.15) & (s["imp_size_atr"] <= 15)),
    ],
    "B1_pullback": [
        ("baseline", {}, None),
        ("+stop 1.5 ATR", {"bo_stop_atr": 1.5}, None),
        ("+breakout conf: big bar AND volume", {"bo_stop_atr": 1.5, "bo_conf": "both"}, None),
        ("+no offhours / low volume", {"bo_stop_atr": 1.5, "bo_conf": "both"},
         lambda s: (s["session"] != "offhours") & (s["vol_rel"] >= 0.5)),
        ("+impulse <= 15 ATR", {"bo_stop_atr": 1.5, "bo_conf": "both"},
         lambda s: (s["session"] != "offhours") & (s["vol_rel"] >= 0.5) & (s["imp_size_atr"] <= 15)),
    ],
    "B2_immediate": [
        ("baseline", {}, None),
        ("+stop 1.5 ATR", {"bo_stop_atr": 1.5}, None),
        ("+breakout conf: big bar AND volume", {"bo_stop_atr": 1.5, "bo_conf": "both"}, None),
        ("+penetration 0.5 ATR", {"bo_stop_atr": 1.5, "bo_conf": "both", "bo_pen_atr": 0.5}, None),
        ("+cost gate spread<=15% stop", {"bo_stop_atr": 1.5, "bo_conf": "both", "bo_pen_atr": 0.5},
         lambda s: s["spread_usd"] / s["risk"] <= 0.15),
    ],
}


def stats(tk):
    s = summarize(tk)
    return dict(n=s.get("n", 0), win_rate=s.get("win_rate", np.nan), expectancy=s.get("expectancy", np.nan),
                pf=s.get("pf", np.nan), total_r=s.get("total_r", np.nan), max_dd_r=s.get("max_dd_r", np.nan),
                ci_lo=s.get("ci_lo", np.nan), ci_hi=s.get("ci_hi", np.nan), max_loss_streak=s.get("max_loss_streak", np.nan),
                median_hold_h=s.get("median_hold_h", np.nan), max_dd_pct_1pct=s.get("max_dd_pct_1pct", np.nan))


def main():
    rows = []
    yearly = []
    for pb, stages in STAGES.items():
        for k, (label, P, filt) in enumerate(stages):
            for cost in ("real", "ideal"):
                _, _, tr = run(P, playbook=pb, cost=cost, signal_filter=filt)
                tk = tr[tr.taken == True].copy()
                if cost == "real":
                    tk.to_csv(os.path.join(OUT, f"trades_{pb}_stage{k}.csv"), index=False)
                for period in [p[0] for p in SPLITS] + ["ALL"]:
                    sel = tk if period == "ALL" else tk[tk.period == period]
                    rows.append(dict(playbook=pb, stage=k, label=label, cost=cost, period=period, **stats(sel)))
                if cost == "real":
                    tk["year"] = pd.to_datetime(tk["entry_time"]).dt.year
                    for y, g in tk.groupby("year"):
                        yearly.append(dict(playbook=pb, stage=k, label=label, year=int(y), n=len(g),
                                           expectancy=g["r_net"].mean(), total_r=g["r_net"].sum(), win_rate=(g["r_net"] > 0).mean()))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "stages.csv"), index=False)
    pd.DataFrame(yearly).to_csv(os.path.join(OUT, "stages_yearly.csv"), index=False)
    for pb in STAGES:
        print(f"\n### {pb}")
        print(fmt(df[(df.playbook == pb) & (df.period != "ALL")][["stage", "label", "cost", "period", "n", "win_rate", "expectancy", "pf", "total_r", "max_dd_r", "ci_lo", "ci_hi", "max_loss_streak"]]))
    print("\n### yearly (real)")
    print(fmt(pd.DataFrame(yearly).pivot_table(index=["playbook", "stage"], columns="year", values="expectancy").reset_index()))


if __name__ == "__main__":
    main()
