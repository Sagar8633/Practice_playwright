"""Collect every result into results/report_data.json, write FINAL_REPORT.md and the
deliverables folder (results/deliverables)."""
import json
import os
import shutil
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
BASE = os.path.join(RES, "baseline")
EXP = os.path.join(RES, "experiments")
ROB = os.path.join(RES, "robustness")
CAND = os.path.join(RES, "candidates")
DELIV = os.path.join(RES, "deliverables")
os.makedirs(DELIV, exist_ok=True)

PB_NAMES = {"A_pingpong": "Playbook A - ping-pong", "B1_pullback": "Playbook B1 - breakout + pullback",
            "B2_immediate": "Playbook B2 - breakout at the close (no pullback)"}


def rd(path):
    return pd.read_csv(path)


def r3(x):
    try:
        return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)
    except Exception:
        return x


def md_table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def period_tables():
    rows = []
    for pb in PB_NAMES:
        for cost in ("ideal", "real"):
            t = rd(os.path.join(BASE, f"trades_{pb}_{cost}.csv"))
            t = t[t.taken == True]
            from pbd.engine import summarize
            for period in ("DEV", "VAL", "OOS", "ALL"):
                s = summarize(t if period == "ALL" else t[t.period == period])
                rows.append(dict(playbook=pb, cost=cost, period=period, n=s["n"], win_rate=s["win_rate"], avg_win=s["avg_win"],
                                 avg_loss=s["avg_loss"], pf=s["pf"], expectancy=s["expectancy"], total_r=s["total_r"],
                                 max_dd_r=s["max_dd_r"], max_dd_pct_1pct=s["max_dd_pct_1pct"], end_equity_1pct=s["end_equity_1pct"],
                                 max_loss_streak=s["max_loss_streak"], avg_hold_h=s["avg_hold_h"], median_hold_h=s["median_hold_h"],
                                 avg_rr=s["avg_rr_planned"], mfe_r=s["mfe_r"], mae_r=s["mae_r"], ci_lo=s["ci_lo"], ci_hi=s["ci_hi"],
                                 spread_r=s["spread_r"]))
    return pd.DataFrame(rows)


def examples(pb="A_pingpong"):
    t = rd(os.path.join(BASE, f"labelled_{pb}_real.csv"))
    t = t[t.taken == True].copy()
    cols = ["entry_time", "session", "stype", "side", "entry_type", "entry", "stop", "target", "exit", "risk_usd", "rr_actual",
            "r_net", "exit_reason", "hold_h", "mfe_r", "mae_r", "imp_size_atr", "width_atr", "dist_vah_atr", "dist_val_atr", "loss_category"]
    losses = t[t.r_net <= 0]
    wins = t[t.r_net > 0]
    ex = {
        "worst_losses": losses.nsmallest(4, "r_net")[cols].to_dict(orient="records"),
        "typical_losses": losses.sample(4, random_state=1)[cols].to_dict(orient="records") if len(losses) >= 4 else [],
        "best_wins": wins.nlargest(4, "r_net")[cols].to_dict(orient="records"),
        "typical_wins": wins.sample(4, random_state=2)[cols].to_dict(orient="records") if len(wins) >= 4 else [],
    }
    return ex


def main():
    summary = json.load(open(os.path.join(BASE, "summary.json")))
    D = {"data": summary["data"], "structures": summary["structures"], "signals": summary["signals"],
         "baseline_params": summary["baseline_params"]}
    st = rd(os.path.join(BASE, "structures.csv"))
    r = st[st.rh.notna()]
    D["structure_stats"] = {
        "impulses_detected": int(len(st)), "ranges_confirmed": int(len(r)), "ranges_per_month": round(len(r) / 60, 1),
        "abandoned_retrace": int((st.outcome == "abandoned_retrace").sum()),
        "imp_size_atr_q10_50_90": [r3(x) for x in (r.imp_size / r.atr_ref).quantile([.1, .5, .9])],
        "imp_bars_q10_50_90": [float(x) for x in r.imp_bars.quantile([.1, .5, .9])],
        "width_atr_q10_50_90": [r3(x) for x in (r.width / r.atr_ref).quantile([.1, .5, .9])],
        "range_life_bars_q10_50_90": [float(x) for x in (r.end_idx - r.rng_start).quantile([.1, .5, .9])],
        "outcomes": r.outcome.value_counts().to_dict(),
        "touches_hi_mean": r3(r.touches_hi.mean()), "touches_lo_mean": r3(r.touches_lo.mean()),
        "failed_bo_per_range": r3(r.failed_bo.mean()),
    }
    pt = period_tables()
    D["period_tables"] = pt.to_dict(orient="records")
    pt.to_csv(os.path.join(DELIV, "05_performance_by_period.csv"), index=False)
    # combined
    D["combined"] = summary["AB1_combined_real"]["period_table"]
    # breakdowns
    for pb in PB_NAMES:
        D[f"by_session_{pb}"] = rd(os.path.join(BASE, f"by_session_{pb}_real.csv")).to_dict(orient="records")
        D[f"by_stype_{pb}"] = rd(os.path.join(BASE, f"by_stype_{pb}_real.csv")).to_dict(orient="records")
        D[f"by_stype_side_{pb}"] = rd(os.path.join(BASE, f"by_stype_side_{pb}_real.csv")).to_dict(orient="records")
        D[f"by_year_{pb}"] = rd(os.path.join(BASE, f"by_year_{pb}_real.csv")).to_dict(orient="records")
        D[f"taxonomy_{pb}"] = rd(os.path.join(BASE, f"taxonomy_{pb}_real.csv")).to_dict(orient="records")
        D[f"taxonomy_multi_{pb}"] = rd(os.path.join(BASE, f"taxonomy_multilabel_{pb}_real.csv")).to_dict(orient="records")
        D[f"filters_{pb}"] = rd(os.path.join(BASE, f"filters_{pb}_real.csv")).to_dict(orient="records")
        D[f"monthly_{pb}"] = rd(os.path.join(BASE, f"monthly_{pb}_real.csv")).to_dict(orient="records")
        eq = rd(os.path.join(BASE, f"equity_{pb}_real.csv"))
        D[f"equity_{pb}"] = {"t": eq.entry_time.tolist(), "eq": eq.equity_r.round(2).tolist(), "dd": eq.drawdown_r.round(2).tolist(),
                             "eq_usd": eq.equity_usd_1pct_10k.round(0).tolist(), "dd_pct": eq.drawdown_pct_1pct.round(1).tolist()}
        ti = rd(os.path.join(BASE, f"trades_{pb}_ideal.csv")); ti = ti[ti.taken == True].sort_values("entry_time")
        D[f"equity_ideal_{pb}"] = {"t": ti.entry_time.tolist(), "eq": ti.r_net.cumsum().round(2).tolist()}
        D[f"news_{pb}"] = rd(os.path.join(BASE, f"by_news_slot_{pb}_real.csv")).fillna("none").to_dict(orient="records")
    D["examples_A"] = examples("A_pingpong")
    D["examples_B1"] = examples("B1_pullback")
    # experiments
    D["experiments"] = {}
    for f in sorted(os.listdir(EXP)):
        if f.endswith(".csv"):
            D["experiments"][f[:-4]] = rd(os.path.join(EXP, f)).to_dict(orient="records")
    # robustness
    D["walk_forward"] = rd(os.path.join(ROB, "walk_forward.csv")).to_dict(orient="records")
    D["costs"] = {pb: rd(os.path.join(ROB, f"costs_{pb}.csv")).to_dict(orient="records") for pb in ("A_pingpong", "B1_pullback")}
    D["grids"] = {g[5:-4]: rd(os.path.join(ROB, g)).to_dict(orient="records") for g in os.listdir(ROB) if g.startswith("grid_")}
    D["stages"] = rd(os.path.join(CAND, "stages.csv")).to_dict(orient="records")
    D["stages_yearly"] = rd(os.path.join(CAND, "stages_yearly.csv")).to_dict(orient="records")
    D["label_rules"] = json.load(open(os.path.join(BASE, "label_rules.json")))
    # extremes / gap facts
    ta = rd(os.path.join(BASE, "trades_A_pingpong_real.csv")); ta = ta[ta.taken == True]
    ta["year"] = pd.to_datetime(ta.entry_time).dt.year
    D["A_facts"] = {"worst_r": r3(ta.r_net.min()), "n_below_minus2": int((ta.r_net < -2).sum()),
                    "sum_below_minus2": r3(ta[ta.r_net < -2].r_net.sum()),
                    "hold_le_4h_share": r3((ta.hold_h <= 4).mean()), "hold_ge_24h_share": r3((ta.hold_h >= 24).mean()),
                    "risk_usd_median_by_year": ta.groupby("year").risk_usd.median().round(2).to_dict(),
                    "spread_r_median_by_year": ta.groupby("year").spread_r.median().round(3).to_dict(),
                    "atr_median_by_year": ta.groupby("year").atr14.median().round(2).to_dict(),
                    "risk_atr_median": r3((ta.risk_usd / ta.atr14).median()), "rr_median": r3(ta.rr_actual.median())}
    with open(os.path.join(RES, "report_data.json"), "w") as f:
        json.dump(D, f, default=str)
    # deliverables copies
    shutil.copy(os.path.join(ROOT, "spec", "pbd_xauusd_rules.json"), os.path.join(DELIV, "01_rule_specification.json"))
    shutil.copy(os.path.join(BASE, "trades_A_pingpong_real.csv"), os.path.join(DELIV, "03_trades_A_pingpong_real.csv"))
    shutil.copy(os.path.join(BASE, "trades_B1_pullback_real.csv"), os.path.join(DELIV, "03_trades_B1_pullback_real.csv"))
    shutil.copy(os.path.join(BASE, "trades_B2_immediate_real.csv"), os.path.join(DELIV, "03_trades_B2_immediate_real.csv"))
    shutil.copy(os.path.join(BASE, "trades_A_pingpong_ideal.csv"), os.path.join(DELIV, "03_trades_A_pingpong_ideal.csv"))
    shutil.copy(os.path.join(BASE, "trades_B1_pullback_ideal.csv"), os.path.join(DELIV, "03_trades_B1_pullback_ideal.csv"))
    shutil.copy(os.path.join(BASE, "trades_AB1_combined_real.csv"), os.path.join(DELIV, "03_trades_AB1_combined_real.csv"))
    shutil.copy(os.path.join(BASE, "signals.csv"), os.path.join(DELIV, "02_all_signals_including_untaken.csv"))
    shutil.copy(os.path.join(BASE, "structures.csv"), os.path.join(DELIV, "02_all_structures.csv"))
    for pb in PB_NAMES:
        shutil.copy(os.path.join(BASE, f"losses_{pb}_real.csv"), os.path.join(DELIV, f"04_loss_classification_{pb}.csv"))
        shutil.copy(os.path.join(BASE, f"taxonomy_{pb}_real.csv"), os.path.join(DELIV, f"04_loss_taxonomy_{pb}.csv"))
        shutil.copy(os.path.join(BASE, f"equity_{pb}_real.csv"), os.path.join(DELIV, f"06_07_equity_drawdown_{pb}_real.csv"))
        shutil.copy(os.path.join(BASE, f"monthly_{pb}_real.csv"), os.path.join(DELIV, f"08_monthly_{pb}_real.csv"))
        shutil.copy(os.path.join(BASE, f"by_session_{pb}_real.csv"), os.path.join(DELIV, f"09_session_{pb}_real.csv"))
        shutil.copy(os.path.join(BASE, f"by_stype_side_{pb}_real.csv"), os.path.join(DELIV, f"10_P_vs_B_{pb}_real.csv"))
        shutil.copy(os.path.join(BASE, f"filters_{pb}_real.csv"), os.path.join(DELIV, f"12_no_trade_filters_{pb}.csv"))
    shutil.copy(os.path.join(BASE, "equity_AB1_combined_real.csv"), os.path.join(DELIV, "06_07_equity_drawdown_AB1_combined_real.csv"))
    pt[pt.period == "OOS"].to_csv(os.path.join(DELIV, "13_out_of_sample_results.csv"), index=False)
    shutil.copy(os.path.join(ROB, "walk_forward.csv"), os.path.join(DELIV, "13_walk_forward.csv"))
    shutil.copy(os.path.join(CAND, "stages.csv"), os.path.join(DELIV, "13_staged_adaptations.csv"))
    for f in os.listdir(EXP):
        shutil.copy(os.path.join(EXP, f), os.path.join(DELIV, "11_experiment_" + f))
    for f in os.listdir(ROB):
        shutil.copy(os.path.join(ROB, f), os.path.join(DELIV, "11_robustness_" + f))
    # dataset pointer (the dataset itself is 200+ MB; the pickles are in data/)
    with open(os.path.join(DELIV, "02_backtest_dataset_README.txt"), "w") as f:
        f.write("Backtest dataset\n================\n"
                "M1 bid bars with Dukascopy volume: Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_YYYY-MM.csv (UTC ms)\n"
                "M1 cache: GOLD/pbd_counter_trend/data/m1.pkl (pandas)\n"
                "M15 bars with XM spread, tick volume, ATR, sessions, news proxy, weekly VA (three volume sources + developing):\n"
                "  GOLD/pbd_counter_trend/data/m15_va.pkl\n"
                "Weekly profiles: GOLD/pbd_counter_trend/data/weekly_profile_{duka,tick,tpo}.csv\n"
                "XM M15 source with spread column: Momentum_Tracker_Indicator/backtest/data/xm_GOLD_M15.csv.gz (server time = Europe/Athens)\n"
                "Missing month: July 2024 (Dukascopy rate-limited every attempt).\n")
    print("report_data.json written; deliverables:", len(os.listdir(DELIV)))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
