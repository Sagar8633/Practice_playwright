"""Baseline test of the ORIGINAL framework (pre-registered parameters, no tuning).

Outputs (results/baseline/):
  signals.csv, structures.csv           every detected structure and every proposed signal
  trades_<playbook>_<cost>.csv          trade-by-trade records (Part 7 columns and more)
  losses_<playbook>_real.csv            losing trades with taxonomy labels
  taxonomy_<playbook>_real.csv          Part 5 table (primary category) + _multilabel
  filters_<playbook>_real.csv           Part 6 before/after table by period
  by_<key>_<playbook>_real.csv          session / structure / side / year / month breakdowns
  equity_<playbook>_real.csv            equity + drawdown curve (R units and 1%-risk USD)
  summary.json                          headline metrics
"""
import json
import os
import sys
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, period_table, fmt, load_all, PLAYBOOKS
from pbd.structure import BASELINE
from pbd.engine import summarize, COSTS
from pbd.analysis import label_losses, taxonomy_table, filter_table, breakdown, monthly, equity_curve, LABEL_RULES, FILTERS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "baseline")
os.makedirs(OUT, exist_ok=True)
TRADE_COLS = ["sid", "time", "entry_time", "exit_time", "session", "news_slot", "period", "stype", "imp_dir", "imp_size",
              "imp_size_atr", "imp_bars", "imp_er", "origin", "extreme", "rh", "rl", "width", "width_atr", "width_over_imp",
              "vah", "val", "poc", "dist_vah_atr", "dist_val_atr", "va_inside", "entry_type", "bo_relation", "side",
              "ref_price", "entry", "stop", "target", "exit", "risk_usd", "reward_usd", "rr_actual", "hold_h", "mfe_r",
              "mae_r", "r_gross", "r_net", "spread_r", "swap_r", "exit_reason", "win", "touches_hi", "touches_lo",
              "touches_side", "failed_bo", "pos_in_range", "atr14", "atr_pct", "vol_rel", "spread_usd", "rng_age",
              "rng_drift", "bo_close_pen_atr", "bo_bar_range_atr", "bo_vol_rel", "pb_depth_atr", "bars_since_bo",
              "won_with_2x_stop", "taken", "skip_reason"]


def main():
    m1, m15, path = load_all()
    summary = {"baseline_params": BASELINE, "costs": COSTS,
               "data": {"m1_bars": int(len(m1)), "m15_bars": int(len(m15)),
                        "start": str(m15["time"].min()), "end": str(m15["time"].max()),
                        "months": int(m15["time"].dt.to_period("M").nunique()),
                        "spread_filled_share": float(m15["spread_filled"].mean())}}
    first = True
    for pb in PLAYBOOKS:
        for cost in ("ideal", "real"):
            st, sg, tr = run(playbook=pb, cost=cost)
            if first:
                st.to_csv(os.path.join(OUT, "structures.csv"), index=False)
                sg.to_csv(os.path.join(OUT, "signals.csv"), index=False)
                summary["structures"] = {"n": int(len(st)), "outcomes": st["outcome"].value_counts().to_dict(),
                                         "types": st["stype"].value_counts().to_dict(),
                                         "ranges_confirmed": int(st["rh"].notna().sum())}
                summary["signals"] = sg["entry_type"].value_counts().to_dict()
                first = False
            cols = [c for c in TRADE_COLS if c in tr.columns]
            tr[cols].to_csv(os.path.join(OUT, f"trades_{pb}_{cost}.csv"), index=False)
            tk = tr[tr["taken"] == True]
            pt = period_table(tk)
            summary[f"{pb}_{cost}"] = {"period_table": pt.to_dict(orient="records"), "all": summarize(tk),
                                       "skips": tr["skip_reason"].value_counts().to_dict()}
            print(f"\n=== {pb} / {cost}: taken {len(tk)}")
            print(fmt(pt))
            if cost == "real":
                lab = label_losses(tr, m15)
                lab.to_csv(os.path.join(OUT, f"labelled_{pb}_real.csv"), index=False)
                lab[lab["r_net"] <= 0][cols + ["loss_category", "loss_flags"]].to_csv(os.path.join(OUT, f"losses_{pb}_real.csv"), index=False)
                tx = taxonomy_table(lab); tx.to_csv(os.path.join(OUT, f"taxonomy_{pb}_real.csv"), index=False)
                taxonomy_table(lab, primary=False).to_csv(os.path.join(OUT, f"taxonomy_multilabel_{pb}_real.csv"), index=False)
                print(fmt(tx[["category", "trades_flagged", "losses", "loss_pct", "avg_loss", "total_loss", "share_of_total_loss", "max_consec"]]))
                ft = filter_table(tr); ft.to_csv(os.path.join(OUT, f"filters_{pb}_real.csv"), index=False)
                print(fmt(ft[ft["period"] == "ALL"][["filter", "n_before", "exp_before", "n_after", "exp_after", "removed", "removed_mean_r", "survives"]]))
                for key in ("session", "stype", "side", "bo_relation", "news_slot"):
                    if key in tk.columns:
                        breakdown(tk, key).to_csv(os.path.join(OUT, f"by_{key}_{pb}_real.csv"), index=False)
                tk2 = tk.copy(); tk2["year"] = pd.to_datetime(tk2["entry_time"]).dt.year
                breakdown(tk2, "year").to_csv(os.path.join(OUT, f"by_year_{pb}_real.csv"), index=False)
                tk2["stype_side"] = tk2["stype"] + "_" + tk2["side"]
                breakdown(tk2, "stype_side").to_csv(os.path.join(OUT, f"by_stype_side_{pb}_real.csv"), index=False)
                monthly(tk).to_csv(os.path.join(OUT, f"monthly_{pb}_real.csv"), index=False)
                equity_curve(tk).to_csv(os.path.join(OUT, f"equity_{pb}_real.csv"), index=False)
                print("by session:\n" + fmt(breakdown(tk, "session")))
                print("by structure:\n" + fmt(breakdown(tk, "stype")))
    # combined A + B1 (one position at a time across both playbooks)
    for cost in ("ideal", "real"):
        from pbd.engine import simulate, Path
        st, sg, _ = run(playbook="A_pingpong", cost=cost)
        tr = simulate(sg, path, m15, COSTS[cost], BASELINE, one_position=True, playbook=["pingpong", "breakout_pullback"])
        cols = [c for c in TRADE_COLS if c in tr.columns]
        tr[cols].to_csv(os.path.join(OUT, f"trades_AB1_combined_{cost}.csv"), index=False)
        tk = tr[tr["taken"] == True]
        summary[f"AB1_combined_{cost}"] = {"period_table": period_table(tk).to_dict(orient="records"), "all": summarize(tk)}
        print(f"\n=== combined A+B1 / {cost}: taken {len(tk)}\n" + fmt(period_table(tk)))
        if cost == "real":
            equity_curve(tk).to_csv(os.path.join(OUT, "equity_AB1_combined_real.csv"), index=False)
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    with open(os.path.join(OUT, "label_rules.json"), "w") as f:
        json.dump({"loss_labels": LABEL_RULES, "filters": {k: v[0] for k, v in FILTERS.items()}}, f, indent=1)


if __name__ == "__main__":
    main()
