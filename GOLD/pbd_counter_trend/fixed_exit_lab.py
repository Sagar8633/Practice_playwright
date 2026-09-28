"""Backtest of the user's fixed-exit rule (8 USD stop, 24 USD target, breakeven at +8, 0.02 lot)
on the unchanged framework entries.  Outputs results/fixed_exit/*.csv and summary.json."""
import json
import os
import sys
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, load_all, fmt, PLAYBOOKS
from pbd.structure import BASELINE
from pbd.engine import COSTS, summarize, drawdown_r, max_streak
from pbd.fixed_exit import simulate_fixed, FIXED
from pbd.data import SPLITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "fixed_exit")
os.makedirs(OUT, exist_ok=True)
PBS = ["A_pingpong", "B1_pullback", "B2_immediate"]


def stats(tk):
    if len(tk) == 0:
        return dict(n=0)
    r = tk["r_net"].values; u = tk["pnl_usd"].values
    eq_u = np.cumsum(u); peak = np.maximum.accumulate(np.r_[0.0, eq_u])[1:]; dd_u = (eq_u - peak).min()
    s = summarize(tk)
    return dict(n=len(tk), win_rate=float((u > 0).mean()), expectancy_r=float(r.mean()), pf=s["pf"], total_r=float(r.sum()),
                pnl_usd=float(u.sum()), avg_usd=float(u.mean()), max_dd_usd=float(dd_u), max_dd_r=s["max_dd_r"],
                max_loss_streak=s["max_loss_streak"], median_hold_h=float(tk["hold_h"].median()), avg_hold_h=float(tk["hold_h"].mean()),
                ci_lo=s["ci_lo"], ci_hi=s["ci_hi"], exits=tk["exit_reason"].value_counts().to_dict(),
                be_armed_share=float(tk["be_armed"].mean()), be_same_bar=int(tk["be_same_bar"].sum()),
                mfe_r=float(tk["mfe_r"].mean()), mae_r=float(tk["mae_r"].mean()))


def by_period(tk, extra=None):
    rows = []
    for p in [x[0] for x in SPLITS] + ["ALL"]:
        sel = tk if p == "ALL" else tk[tk.period == p]
        rows.append(dict(period=p, **(extra or {}), **stats(sel)))
    return rows


def by_year(tk, extra=None):
    rows = []
    t = tk.copy(); t["year"] = pd.to_datetime(t["entry_time"]).dt.year
    for y, g in t.groupby("year"):
        rows.append(dict(year=int(y), **(extra or {}), **stats(g)))
    return rows


def main():
    m1, m15, path = load_all()
    rows = []; yrows = []; srows = []; exits = []
    summary = {}
    for pb in PBS:
        st, sg, _ = run(playbook=pb, cost="real")          # same structures/signals as the baseline
        sgp = sg[sg.entry_type.isin(PLAYBOOKS[pb])]
        for cost in ("real", "ideal"):
            for ts_label, ts in (("strict_no_time_stop", None), ("time_stop_72h", 72)):
                tr = simulate_fixed(sgp, path, m15, COSTS[cost], {"time_stop_h": ts}, one_position=True)
                tk = tr[tr.taken == True].copy()
                tag = f"{pb}_{cost}_{ts_label}"
                tk.to_csv(os.path.join(OUT, f"trades_{tag}.csv"), index=False)
                ex = {"playbook": pb, "cost": cost, "time_stop": ts_label}
                rows += by_period(tk, ex); yrows += by_year(tk, ex)
                if cost == "real":
                    for sname, g in tk.groupby("session"):
                        srows.append(dict(session=sname, **ex, **stats(g)))
                    for ename, g in tk.groupby("exit_reason"):
                        exits.append(dict(exit_reason=ename, **ex, n=len(g), avg_usd=float(g.pnl_usd.mean()), total_usd=float(g.pnl_usd.sum()),
                                          avg_hold_h=float(g.hold_h.mean()), share=len(g) / len(tk)))
                summary[tag] = stats(tk)
                print(f"{tag}: n {len(tk)} win {stats(tk)['win_rate']:.3f} exp {stats(tk)['expectancy_r']:+.3f}R pnl {stats(tk)['pnl_usd']:+.0f} USD "
                      f"DD {stats(tk)['max_dd_usd']:.0f} USD exits {stats(tk)['exits']}")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "by_period.csv"), index=False)
    pd.DataFrame(yrows).to_csv(os.path.join(OUT, "by_year.csv"), index=False)
    pd.DataFrame(srows).to_csv(os.path.join(OUT, "by_session.csv"), index=False)
    pd.DataFrame(exits).to_csv(os.path.join(OUT, "by_exit.csv"), index=False)
    # ---- sensitivity grid on the real / strict setting: SL x TP x BE trigger
    grid = []
    for pb in PBS:
        st, sg, _ = run(playbook=pb, cost="real")
        sgp = sg[sg.entry_type.isin(PLAYBOOKS[pb])]
        for sl in (4.0, 8.0, 12.0, 16.0):
            for tp_mult in (1.0, 2.0, 3.0, 4.0):
                for be in ("none", "half", "full"):
                    be_trig = None if be == "none" else (sl / 2 if be == "half" else sl)
                    tr = simulate_fixed(sgp, path, m15, COSTS["real"], {"sl_usd": sl, "tp_usd": sl * tp_mult, "be_trigger_usd": be_trig, "time_stop_h": None})
                    tk = tr[tr.taken == True]
                    for p in ["DEV", "VAL", "OOS", "ALL"]:
                        sel = tk if p == "ALL" else tk[tk.period == p]
                        s = stats(sel)
                        grid.append(dict(playbook=pb, sl_usd=sl, tp_mult=tp_mult, tp_usd=sl * tp_mult, be=be, period=p,
                                         n=s.get("n", 0), win_rate=s.get("win_rate"), expectancy_r=s.get("expectancy_r"), pf=s.get("pf"),
                                         pnl_usd=s.get("pnl_usd"), max_dd_usd=s.get("max_dd_usd")))
        print("grid done", pb)
    pd.DataFrame(grid).to_csv(os.path.join(OUT, "grid_sl_tp_be.csv"), index=False)
    # ---- ATR-scaled equivalent of the same rule (stop = k ATR where k = 8 / median ATR of 2026)
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump({"exit_model": FIXED, "runs": summary}, f, indent=1, default=str)


if __name__ == "__main__":
    main()
