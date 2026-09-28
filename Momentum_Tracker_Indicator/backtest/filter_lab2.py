"""Filter lab, stage 2: diagnostics on the baseline, filter retention, combination, walk-forward,
Monte Carlo and risk-based sizing. Needs results/lab/runs.pkl from filter_lab.py.
"""
import json, math, os, time
import numpy as np
import pandas as pd
import twk_engine as E
from filter_lab import (m1, sig, ser, spread, TF, LOTS, PERIODS, T_A, T_B, END, pm, short_metrics, bot, RUNS, META, run)

T0 = time.time()
base = RUNS["BASELINE"].copy()
OUT = {}

# ------------------------------------------------------------------ helpers
def in_period(tr, name):
    a, b = PERIODS[name]
    return tr[(tr.entry_time >= a) & (tr.entry_time < b)]

def attach_features(tr):
    """Join signal-context features onto trades via the signal bar index."""
    f = sig.set_index("bar")
    cols = ["flips_10", "flips_20", "atr_ratio", "range_ratio", "dist_ema", "htf15_aligned", "htf60_aligned", "ema15_aligned",
            "cost_over_reward", "cost_over_stop", "opp_candles5", "dist_prev_sig", "adx_slope", "bbw_atr", "hour", "dow"]
    d = tr.copy()
    for c in cols:
        d[c] = d["sig_bar"].map(f[c])
    d["risk_r"] = d["risk"]
    d["mfe_r"] = d["max_fav"] / d["risk"]
    d["mae_r"] = d["max_adv"] / d["risk"]
    d["hold_min"] = (d["exit_time"] - d["entry_time"]).dt.total_seconds() / 60
    d["prev_pnl"] = d["pnl"].shift(1)
    d["prev_exit"] = d["exit_time"].shift(1)
    d["prev_side"] = d["side"].shift(1)
    d["min_since_prev_exit"] = (d["entry_time"] - d["prev_exit"]).dt.total_seconds() / 60
    d["post_loss"] = (d["prev_pnl"] < 0)
    d["post_loss_15"] = d["post_loss"] & (d["min_since_prev_exit"] <= 15)
    d["same_dir_reentry"] = d["post_loss"] & (d["side"] == d["prev_side"])
    d["opp_dir_reentry"] = d["post_loss"] & (d["side"] != d["prev_side"])
    return d

bd = attach_features(base)
bd.to_csv("results/lab/trades_BASELINE_features.csv", index=False)

# ------------------------------------------------------------------ 20. loss tags
losers = bd[bd.pnl < 0]
total_loss = losers.pnl.sum()
worst_hours = bd[(bd.entry_time < PERIODS["DEV"][1])].groupby("hour").pnl.sum().sort_values().head(3).index.tolist()
TAGS = {
    "POST_LOSS_REENTRY": losers.post_loss_15,
    "RAPID_FLIP": (losers.opp_ago >= 0) & (losers.opp_ago <= 5),
    "CHOP": losers.flips_10 >= 3,
    "LOW_ATR": losers.atr_ratio < 0.7,
    "HIGH_ATR": losers.atr_ratio > 1.5,
    "OVEREXTENDED": losers.range_ratio > 2.5,
    "HTF_CONFLICT": ~losers.htf15_aligned.astype(bool),
    "INITIAL_STOP": losers.exit_reason.isin(["SL", "SL_gap"]),
    "REVERSAL_EXIT": losers.exit_reason.isin(["opposite", "opposite_confirmed"]),
    "TRAILING_FAILURE": losers.mfe_r >= 0.5,
    "TIMEOUT": losers.hold_min > 120,
    "SPREAD_TOO_HIGH": losers.cost_over_reward > 0.15,
    "SESSION_BAD": losers.hour.isin(worst_hours),
}
tag_rows = []
for k, m in TAGS.items():
    g = losers[m.fillna(False)]
    tag_rows.append(dict(tag=k, trades=int(len(g)), gross_loss=round(float(g.pnl.sum()), 2), pct_total_loss=round(float(g.pnl.sum() / total_loss * 100), 1) if total_loss else 0,
                         avg_loss=round(float(g.pnl.mean()), 2) if len(g) else 0.0,
                         rule={"POST_LOSS_REENTRY": "entered <= 15 min after a losing exit", "RAPID_FLIP": "opposite signal <= 5 bars earlier", "CHOP": ">= 3 other flips in the last 10 bars",
                               "LOW_ATR": "ATR < 0.7 x 30-day median", "HIGH_ATR": "ATR > 1.5 x 30-day median", "OVEREXTENDED": "signal bar range > 2.5 x ATR",
                               "HTF_CONFLICT": "M15 Supertrend against the trade", "INITIAL_STOP": "exit at the initial stop", "REVERSAL_EXIT": "closed by the opposite signal",
                               "TRAILING_FAILURE": "was up >= 0.5R before losing", "TIMEOUT": "held > 120 min", "SPREAD_TOO_HIGH": "spread > 15% of the 1:2 target distance",
                               "SESSION_BAD": f"entered in the 3 worst DEV hours {worst_hours}"}[k]))
OUT["loss_tags"] = tag_rows
OUT["loss_tags_note"] = f"{len(losers)} losing trades, gross loss {total_loss:.0f}; tags overlap (a trade can carry several)."
untagged = losers[~np.column_stack([m.fillna(False).to_numpy() for m in TAGS.values()]).any(axis=1)]
OUT["loss_tags_other"] = dict(trades=int(len(untagged)), gross_loss=round(float(untagged.pnl.sum()), 2))

# ------------------------------------------------------------------ 11. MFE / MAE
def q(s, qs=(0.25, 0.5, 0.75, 0.9)):
    return {str(x): round(float(s.quantile(x)), 2) for x in qs}
wins = bd[bd.pnl > 0]
OUT["mfe_mae"] = dict(
    winners_mae_r=q(wins.mae_r), losers_mfe_r=q(losers.mfe_r),
    winners_mfe_r=q(wins.mfe_r), losers_mae_r=q(losers.mae_r),
    winners_share_mae_below_0_5=round(float((wins.mae_r < 0.5).mean()), 3),
    losers_share_mfe_above_0_5=round(float((losers.mfe_r >= 0.5).mean()), 3),
    losers_share_mfe_above_1=round(float((losers.mfe_r >= 1.0).mean()), 3),
    by_exit={k: dict(n=int(len(g)), mfe_r_median=round(float(g.mfe_r.median()), 2), mae_r_median=round(float(g.mae_r.median()), 2), pnl=round(float(g.pnl.sum()), 0))
             for k, g in bd.groupby("exit_reason")})

# ------------------------------------------------------------------ 13. profit protection
prot = []
for r in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
    g = bd[bd.mfe_r >= r]
    prot.append(dict(reached_r=r, trades=int(len(g)), pct_of_all=round(len(g) / len(bd) * 100, 1),
                     ended_loser=int((g.pnl < 0).sum()), ended_loser_pct=round(float((g.pnl < 0).mean() * 100), 1),
                     ended_at_or_below_be=int((g.pnl <= 0).sum()), reached_tp=int((g.exit_reason == "TP").sum()),
                     avg_r_after=round(float(g.r_multiple.mean()), 2), net=round(float(g.pnl.sum()), 0)))
OUT["profit_protection"] = prot

# ------------------------------------------------------------------ 14. duration buckets + profit at X minutes
bins = [0, 1, 3, 5, 10, 20, 30, 60, 1e9]; labels = ["<1", "1-3", "3-5", "5-10", "10-20", "20-30", "30-60", ">60"]
bd["dur_b"] = pd.cut(bd.hold_min, bins, labels=labels, right=True)
OUT["duration"] = [dict(bucket=str(k), trades=int(len(g)), net=round(float(g.pnl.sum()), 0), exp=round(float(g.pnl.mean()), 2), win=round(float((g.pnl > 0).mean()), 2))
                   for k, g in bd.groupby("dur_b", observed=True)]
# profit at X minutes for trades still open then (from M1 closes)
m1_t = (m1["time"].astype("int64") // 10**9).to_numpy(); m1_c = m1["close"].to_numpy(float)
t_in = (bd.entry_time.astype("int64") // 10**9).to_numpy(); side = np.where(bd.side == "BUY", 1, -1)
tx = []
for X in (10, 20, 30, 60):
    still = bd.hold_min > X
    k = np.searchsorted(m1_t, t_in + X * 60, side="right") - 1
    px = m1_c[np.maximum(k, 0)]
    prof_r = np.where(side == 1, px - bd.entry.to_numpy(), bd.entry.to_numpy() - px) / bd.risk.to_numpy()
    for Y in (0.0, 0.25):
        sel = still & (prof_r < Y)
        g = bd[sel]
        rest = bd[still & ~(prof_r < Y)]
        tx.append(dict(after_min=X, below_r=Y, trades=int(len(g)), eventual_net=round(float(g.pnl.sum()), 0), eventual_exp=round(float(g.pnl.mean()), 2) if len(g) else 0,
                       eventual_win=round(float((g.pnl > 0).mean()), 2) if len(g) else 0, others_exp=round(float(rest.pnl.mean()), 2) if len(rest) else 0,
                       pnl_if_closed_then=round(float((prof_r[sel] * bd.risk.to_numpy()[sel] * LOTS * 100).sum()), 0)))
OUT["time_exit_derivation"] = tx

# ------------------------------------------------------------------ 2E. same vs opposite re-entry after a loss
OUT["reentry_direction"] = {k: dict(trades=int(len(g)), net=round(float(g.pnl.sum()), 0), exp=round(float(g.pnl.mean()), 2), win=round(float((g.pnl > 0).mean()), 2))
                            for k, g in (("after_win_or_first", bd[~bd.post_loss]), ("after_loss_same_dir", bd[bd.same_dir_reentry]), ("after_loss_opposite_dir", bd[bd.opp_dir_reentry]),
                                         ("after_loss_within_15min", bd[bd.post_loss_15]), ("after_loss_later_than_15min", bd[bd.post_loss & ~bd.post_loss_15]))}

# ------------------------------------------------------------------ 9. HTF alignment expectancy (per period)
htf = []
for nm, col in (("M15 Supertrend", "htf15_aligned"), ("H1 Supertrend", "htf60_aligned"), ("M15 EMA50 slope", "ema15_aligned")):
    for per in ("DEV", "VAL", "OOS"):
        d = in_period(bd, per)
        for al in (True, False):
            g = d[d[col].astype(bool) == al]
            htf.append(dict(htf=nm, period=per, aligned=al, trades=int(len(g)), exp=round(float(g.pnl.mean()), 2) if len(g) else 0, net=round(float(g.pnl.sum()), 0), pf=round(short_metrics(g)["pf"], 2)))
OUT["htf"] = htf

# ------------------------------------------------------------------ 15. session stability
hs = []
for hr in range(24):
    row = dict(hour=hr)
    for per in ("DEV", "VAL", "OOS"):
        d = in_period(bd, per); g = d[d.hour == hr]
        row[f"{per}_n"] = int(len(g)); row[f"{per}_exp"] = round(float(g.pnl.mean()), 2) if len(g) else 0.0
    hs.append(row)
OUT["hours"] = hs
hd = pd.DataFrame(hs)
OUT["hours_sign_agreement"] = dict(dev_val=round(float(((hd.DEV_exp > 0) == (hd.VAL_exp > 0)).mean()), 2), val_oos=round(float(((hd.VAL_exp > 0) == (hd.OOS_exp > 0)).mean()), 2),
                                   corr_dev_val=round(float(hd.DEV_exp.corr(hd.VAL_exp)), 2), corr_val_oos=round(float(hd.VAL_exp.corr(hd.OOS_exp)), 2))

# ------------------------------------------------------------------ 8. entry quality score: per-feature lift in DEV, validated in VAL
FEATS = {
    "htf15_aligned": bd.htf15_aligned.astype(bool), "htf60_aligned": bd.htf60_aligned.astype(bool), "ema15_aligned": bd.ema15_aligned.astype(bool),
    "adx>=25": bd.adx >= 25, "flips_10<=1": bd.flips_10 <= 1, "atr_ratio_0.8-1.5": (bd.atr_ratio >= 0.8) & (bd.atr_ratio <= 1.5),
    "range_ratio<=2": bd.range_ratio <= 2, "cost_over_reward<=0.10": bd.cost_over_reward <= 0.10, "opp_ago>=5": (bd.opp_ago < 0) | (bd.opp_ago >= 5),
    "dist_ema<=2": bd.dist_ema <= 2, "adx_rising": bd.adx_slope > 0, "opp_candles5<=2": bd.opp_candles5 <= 2,
}
feat_rows = []
kept = []
for k, m in FEATS.items():
    row = dict(feature=k)
    ok = True
    for per in ("DEV", "VAL", "OOS"):
        d = in_period(bd, per); mm = m.loc[d.index]
        a = d[mm]; b = d[~mm]
        row[f"{per}_with_n"] = int(len(a)); row[f"{per}_with_exp"] = round(float(a.pnl.mean()), 2) if len(a) else 0
        row[f"{per}_without_n"] = int(len(b)); row[f"{per}_without_exp"] = round(float(b.pnl.mean()), 2) if len(b) else 0
        row[f"{per}_lift"] = round(row[f"{per}_with_exp"] - row[f"{per}_without_exp"], 2)
        if per in ("DEV", "VAL") and (row[f"{per}_lift"] <= 0 or len(a) < 100):
            ok = False
    row["kept"] = ok
    if ok:
        kept.append(k)
    feat_rows.append(row)
OUT["score_features"] = feat_rows
OUT["score_kept"] = kept
# score on signals
sigf = {"htf15_aligned": sig.htf15_aligned.astype(bool), "htf60_aligned": sig.htf60_aligned.astype(bool), "ema15_aligned": sig.ema15_aligned.astype(bool),
        "adx>=25": sig.adx >= 25, "flips_10<=1": sig.flips_10 <= 1, "atr_ratio_0.8-1.5": (sig.atr_ratio >= 0.8) & (sig.atr_ratio <= 1.5),
        "range_ratio<=2": sig.range_ratio <= 2, "cost_over_reward<=0.10": sig.cost_over_reward <= 0.10, "opp_ago>=5": (sig.opp_ago < 0) | (sig.opp_ago >= 5),
        "dist_ema<=2": sig.dist_ema <= 2, "adx_rising": sig.adx_slope > 0, "opp_candles5<=2": sig.opp_candles5 <= 2}
score = sum(sigf[k].astype(int) for k in kept) if kept else pd.Series(0, index=sig.index)
sig["score"] = score
for thr in sorted(set([max(1, len(kept) - 2), max(1, len(kept) - 1), max(1, len(kept))])):
    run(f"score>={thr}_of_{len(kept)}", "T8 score", f"entry score >= {thr} of {len(kept)} kept features {kept}", mask=(score >= thr).to_numpy())

# ------------------------------------------------------------------ 21. retention rule + A/B table
basem = pm(base)
def ab_row(name, tr):
    m = pm(tr)
    row = dict(name=name, group=META[name]["group"], rule=META[name]["rule"])
    for per in ("DEV", "VAL", "OOS", "ALL"):
        b, f = basem[per], m[per]
        row[f"{per}_n"] = f["n"]; row[f"{per}_net"] = round(f["net"], 0); row[f"{per}_pf"] = round(f["pf"], 2); row[f"{per}_exp"] = round(f["exp"], 2); row[f"{per}_dd"] = round(f["dd"], 0)
        row[f"{per}_win_removed"] = b["wins"] - f["wins"]; row[f"{per}_loss_removed"] = b["losses"] - f["losses"]
        row[f"{per}_gross_ex"] = round(f["gross_ex"], 0); row[f"{per}_spread"] = round(f["spread"], 0)
    def better(per):
        b, f = basem[per], m[per]
        if f["n"] < 30:
            return False
        w_share = (b["wins"] - f["wins"]) / max(1, b["wins"]); l_share = (b["losses"] - f["losses"]) / max(1, b["losses"])
        return f["exp"] > b["exp"] and f["pf"] > b["pf"] and f["dd"] <= b["dd"] * 1.05 and l_share >= w_share
    row["pass_DEV"] = better("DEV"); row["pass_VAL"] = better("VAL"); row["pass_OOS"] = better("OOS")
    row["retain"] = row["pass_DEV"] and row["pass_VAL"]
    return row
ab = pd.DataFrame([ab_row(n, t) for n, t in RUNS.items()])
ab.to_csv("results/lab/ab_table.csv", index=False)
OUT["ab"] = ab.to_dict("records")
retained = ab[ab.retain & (ab.name != "BASELINE")].sort_values("VAL_exp", ascending=False)
print("RETAINED (pass DEV and VAL):"); print(retained[["name", "DEV_n", "DEV_exp", "DEV_pf", "VAL_n", "VAL_exp", "VAL_pf", "OOS_n", "OOS_exp", "OOS_pf", "pass_OOS"]].to_string(index=False), flush=True)

# ------------------------------------------------------------------ 25/10. combined configuration
# one representative per group among the retained, chosen by VAL expectancy (never by OOS)
best_by_group = {}
for _, r in retained.iterrows():
    g = r["group"]
    if g not in best_by_group:
        best_by_group[g] = r["name"]
OUT["combined_members"] = best_by_group
# rebuild the combined bot + mask from the member names
def cfg_from_names(names):
    kw = {}; mask = np.ones(len(sig), bool)
    for n in names:
        if n.startswith("cost_reward<="): mask &= (sig.cost_over_reward <= float(n.split("<=")[1])).to_numpy()
        elif n.startswith("cost_stop<="): mask &= (sig.cost_over_stop <= float(n.split("<=")[1])).to_numpy()
        elif n.startswith("cool_") and n.endswith("bars"): kw["cooldown_bars_after_loss"] = int(n[5:-4])
        elif n.startswith("cool_"): parts = n.split("_"); kw["cooldown_min_after_loss"] = int(parts[1][:-1]); kw["cooldown_mode"] = parts[2]
        elif n.startswith("reentry_dist>="): kw["reentry_atr_mult"] = float(n.split(">=")[1].replace("atr", ""))
        elif n.startswith("opp_signal_age>="): x = int(n.split(">=")[1]); mask &= ((sig.opp_ago < 0) | (sig.opp_ago >= x)).to_numpy()
        elif n.startswith("flips_"): N, X = n[6:].split("<="); mask &= (sig[f"flips_{N}"] <= int(X)).to_numpy()
        elif n.startswith("atr_ratio>="): mask &= (sig.atr_ratio >= float(n.split(">=")[1])).to_numpy()
        elif n.startswith("atr_ratio<="): mask &= (sig.atr_ratio <= float(n.split("<=")[1])).to_numpy()
        elif n.startswith("adx>"): mask &= (sig.adx > float(n.split(">")[1])).to_numpy()
        elif n == "adx_rising": mask &= (sig.adx_slope > 0).to_numpy()
        elif n.startswith("bbw_atr>="): mask &= (sig.bbw_atr >= float(n.split(">=")[1])).to_numpy()
        elif n.startswith("opp_candles5<="): mask &= (sig.opp_candles5 <= int(n.split("<=")[1])).to_numpy()
        elif n.startswith("dist_prev_sig>="): mask &= (sig.dist_prev_sig >= float(n.split(">=")[1])).to_numpy()
        elif n.startswith("stop_atr"): kw["initial_sl"] = "atr"; kw["atr_stop_mult"] = float(n[8:])
        elif n.startswith("stop_hybrid"): fl, cap = n[11:].split("_cap"); kw["initial_sl"] = "hybrid"; kw["atr_stop_mult"] = float(fl); kw["atr_stop_cap"] = float(cap)
        elif n.startswith("stop_pivot_cap"): kw["atr_stop_cap"] = float(n[14:])
        elif n == "stop_purple": kw["initial_sl"] = "purple"
        elif n == "rev_reverse": kw["close_on_opposite"] = True; kw["reverse_on_opposite"] = True
        elif n == "rev_modelA_close": kw["close_on_opposite"] = True
        elif n.startswith("rev_modelB_confirm"): kw["close_on_opposite"] = True; kw["opposite_confirm_bars"] = int(n[-1])
        elif n.startswith("rev_modelD_adx"): kw["close_on_opposite"] = True; kw["opposite_min_adx"] = float(n[14:])
        elif n == "htf15": mask &= sig.htf15_aligned.to_numpy()
        elif n == "htf60": mask &= sig.htf60_aligned.to_numpy()
        elif n == "htf15_and_60": mask &= (sig.htf15_aligned & sig.htf60_aligned).to_numpy()
        elif n == "ema50_m15": mask &= sig.ema15_aligned.to_numpy()
        elif n.startswith("range_ratio<="): mask &= (sig.range_ratio <= float(n.split("<=")[1])).to_numpy()
        elif n.startswith("dist_ema<="): mask &= (sig.dist_ema <= float(n.split("<=")[1])).to_numpy()
        elif n.startswith("trail_at"): kw["trail_activation_r"] = float(n[8:-1])
        elif n.startswith("be_at"): kw["breakeven_r"] = float(n[5:-1])
        elif n.startswith("lock_"): ra, rl = n[5:].split("R_keep"); kw["lock_activation_r"] = float(ra); kw["lock_level_r"] = float(rl[:-1]); kw["one_to_one_gap_r"] = float(ra) - float(rl[:-1])
        elif n.startswith("timeexit_"): parts = n[9:].split("m_below"); kw["time_exit_min"] = int(parts[0]); kw["time_exit_below_r"] = float(parts[1][:-1])
        elif n.startswith("session_"): key = n[8:]; hrs = {"asia_02-10": (2, 10), "london_10-15": (10, 15), "overlap_15-20": (15, 20), "ny_20-24": (20, 24), "london+ny_10-20": (10, 20)}[key]; kw["entry_hours"] = hrs
        elif n.startswith("score>="): thr = int(n.split(">=")[1].split("_")[0]); mask &= (sig.score >= thr).to_numpy()
        elif n == "htf15_conflict": mask &= (~sig.htf15_aligned).to_numpy()
    return kw, mask
members = list(best_by_group.values())
kw, mask = cfg_from_names(members)
comb = run("COMBINED", "combined", "all retained filters, one per group: " + ", ".join(members), b=bot("COMBINED", **kw), mask=mask)
comb.to_csv("results/lab/trades_COMBINED.csv", index=False)
OUT["combined_kw"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}
abc = ab_row("COMBINED", comb); OUT["combined_row"] = abc
# progressive build: add members one at a time in VAL-expectancy order
prog = []
for i in range(1, len(members) + 1):
    kw_i, mask_i = cfg_from_names(members[:i])
    tr_i = E.simulate(m1, sig[mask_i], ser, TF, bot(f"prog{i}", **kw_i), spread, T_A, T_B)
    mi = pm(tr_i)
    prog.append(dict(step=i, added=members[i - 1], **{f"{per}_{k}": (round(mi[per][k], 2) if isinstance(mi[per][k], float) else mi[per][k]) for per in ("DEV", "VAL", "OOS") for k in ("n", "net", "pf", "exp", "dd")}))
OUT["progressive"] = prog
print("progressive build:"); print(pd.DataFrame(prog).to_string(index=False), flush=True)

# ------------------------------------------------------------------ 26. walk-forward: re-select on rotating windows
def select_on(train_periods):
    """Apply the retention rule using only `train_periods`; returns member names (one per group)."""
    chosen = {}
    rows = []
    for n, tr in RUNS.items():
        if n in ("BASELINE", "COMBINED") or n.startswith("prog"): continue
        ok = True; val_exp = None
        for per in train_periods:
            a, b = per
            d = tr[(tr.entry_time >= a) & (tr.entry_time < b)]; bb = base[(base.entry_time >= a) & (base.entry_time < b)]
            f, bm = short_metrics(d), short_metrics(bb)
            if f["n"] < 30 or not (f["exp"] > bm["exp"] and f["pf"] > bm["pf"] and f["dd"] <= bm["dd"] * 1.05 and (bm["losses"] - f["losses"]) / max(1, bm["losses"]) >= (bm["wins"] - f["wins"]) / max(1, bm["wins"])):
                ok = False
            val_exp = f["exp"]
        if ok:
            rows.append((META[n]["group"], val_exp, n))
    for g, v, n in sorted(rows, key=lambda x: -x[1]):
        chosen.setdefault(g, n)
    return list(chosen.values())
WF = [
    dict(name="A: select 2021-09..2023, test 2024", train=[(pd.Timestamp("2021-09-01"), pd.Timestamp("2023-01-01")), (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"))], test=(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"))),
    dict(name="B: select 2022..2024, test 2025", train=[(pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01")), (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"))], test=(pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"))),
    dict(name="C: select 2023..2025, test 2026", train=[(pd.Timestamp("2023-01-01"), pd.Timestamp("2025-01-01")), (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"))], test=(pd.Timestamp("2026-01-01"), END)),
]
wf_rows = []
for w in WF:
    mem = select_on(w["train"])
    kw_w, mask_w = cfg_from_names(mem)
    tr_w = E.simulate(m1, sig[mask_w], ser, TF, bot("wf", **kw_w), spread, T_A, T_B)
    a, b = w["test"]
    f = short_metrics(tr_w[(tr_w.entry_time >= a) & (tr_w.entry_time < b)]); bm = short_metrics(base[(base.entry_time >= a) & (base.entry_time < b)])
    wf_rows.append(dict(window=w["name"], members=mem, test_n=f["n"], test_net=round(f["net"], 0), test_pf=round(f["pf"], 2), test_exp=round(f["exp"], 2), test_dd=round(f["dd"], 0),
                        base_n=bm["n"], base_net=round(bm["net"], 0), base_pf=round(bm["pf"], 2), base_exp=round(bm["exp"], 2)))
OUT["walk_forward"] = wf_rows
print("walk-forward:"); print(pd.DataFrame(wf_rows).drop(columns=["members"]).to_string(index=False), flush=True)

# ------------------------------------------------------------------ 27. robustness of the combined config
rob = []
def rob_run(label, spread_mult=1.0, **extra):
    kw2 = dict(kw); kw2.update(extra)
    tr = E.simulate(m1, sig[mask], ser, TF, bot("rob", **kw2), spread * spread_mult, T_A, T_B)
    m = pm(tr)
    rob.append(dict(variant=label, **{f"{per}_{k}": (round(m[per][k], 2) if isinstance(m[per][k], float) else m[per][k]) for per in ("DEV", "VAL", "OOS", "ALL") for k in ("n", "net", "pf", "exp", "dd")}))
rob_run("as selected")
rob_run("spread x1.25", spread_mult=1.25)
rob_run("spread x1.5", spread_mult=1.5)
for s in (1, 2, 3):
    rob_run(f"slippage {s} pts each way", slippage_pts=s)
if "atr_stop_mult" in kw:
    rob_run("stop -10%", atr_stop_mult=kw["atr_stop_mult"] * 0.9); rob_run("stop +10%", atr_stop_mult=kw["atr_stop_mult"] * 1.1)
if "trail_activation_r" in kw:
    rob_run("trail activation -20%", trail_activation_r=kw["trail_activation_r"] * 0.8); rob_run("trail activation +20%", trail_activation_r=kw["trail_activation_r"] * 1.2)
if "cooldown_min_after_loss" in kw:
    rob_run("cooldown -33%", cooldown_min_after_loss=max(1, int(kw["cooldown_min_after_loss"] * 0.67))); rob_run("cooldown +50%", cooldown_min_after_loss=int(kw["cooldown_min_after_loss"] * 1.5))
rob_run("worst-path trailing", trail_mode="worst")
OUT["robustness"] = rob
print("robustness:"); print(pd.DataFrame(rob).to_string(index=False), flush=True)
# Monte Carlo: trade-order shuffle of the combined trades (fixed lots) -> drawdown distribution
rng = np.random.default_rng(11)
pnl = comb.pnl.to_numpy(float)
dds = []
for _ in range(2000):
    x = rng.permutation(pnl); eq = np.cumsum(x); dds.append(float((np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq).max()))
OUT["monte_carlo"] = dict(trades=int(len(pnl)), net=round(float(pnl.sum()), 0), dd_p5=round(float(np.percentile(dds, 5)), 0), dd_p50=round(float(np.percentile(dds, 50)), 0), dd_p95=round(float(np.percentile(dds, 95)), 0),
                          bootstrap_p_profit=round(float((rng.choice(pnl, size=(2000, len(pnl))).sum(axis=1) > 0).mean()), 3) if len(pnl) else 0)

# ------------------------------------------------------------------ 6. risk-based sizing (post-hoc equity simulation)
def equity_sim(tr, start=1000.0, risk_pct=1.0, max_lot=0.10, min_lot=0.01, max_daily_loss_pct=3.0, max_consec=5, max_stop_pct=2.0):
    eq = start; peak = start; dd = 0.0; skipped = 0; consec = 0; day = None; day_pnl = 0.0; n = 0; ruin = False
    paused_day = None
    curve = []
    for _, r in tr.sort_values("entry_time").iterrows():
        d = r.entry_time.date()
        if d != day:
            day, day_pnl = d, 0.0
            if paused_day is not None and d != paused_day:
                paused_day = None; consec = 0            # a losing streak pauses the rest of that day only
        if paused_day == d or day_pnl <= -eq * max_daily_loss_pct / 100:
            skipped += 1; continue
        risk_usd = eq * risk_pct / 100
        per_001 = r.risk * 1.0                       # $ lost per 0.01 lot if the initial stop is hit (1 oz)
        if per_001 <= 0: continue
        lot = math.floor(risk_usd / per_001) * 0.01  # number of 0.01 lots the risk budget allows
        if lot < min_lot or per_001 > eq * max_stop_pct / 100:
            skipped += 1; continue
        lot = min(lot, max_lot)
        pnl = r.pnl_px * lot * 100 + r.swap / LOTS * lot
        eq += pnl; day_pnl += pnl; n += 1
        consec = consec + 1 if pnl < 0 else 0
        if consec >= max_consec:
            paused_day = d
        peak = max(peak, eq); dd = max(dd, (peak - eq) / peak)
        curve.append(eq)
        if eq <= start * 0.2: ruin = True; break
    return dict(start=start, risk_pct=risk_pct, trades=n, skipped=skipped, final=round(eq, 0), ret_pct=round((eq / start - 1) * 100, 1), max_dd_pct=round(dd * 100, 1), ruin=ruin)
sizing = []
for label, tr in (("BASELINE", base), ("COMBINED", comb)):
    for rp in (0.5, 1.0, 2.0):
        sizing.append(dict(config=label, **equity_sim(tr, risk_pct=rp)))
    # fixed lots for comparison
    pnl = tr.pnl.to_numpy(); eq = 1000 + np.cumsum(pnl)
    sizing.append(dict(config=label, start=1000, risk_pct="fixed 0.02", trades=int(len(pnl)), skipped=0, final=round(float(eq[-1]), 0), ret_pct=round(float(eq[-1] / 1000 - 1) * 100, 1),
                       max_dd_pct=round(float(((np.maximum.accumulate(np.concatenate([[1000.0], eq]))[1:] - eq) / np.maximum.accumulate(np.concatenate([[1000.0], eq]))[1:]).max() * 100), 1), ruin=bool(eq.min() <= 200)))
OUT["sizing"] = sizing
print("sizing:"); print(pd.DataFrame(sizing).to_string(index=False), flush=True)

# ------------------------------------------------------------------ before/after summary (29F)
def full_row(tr):
    m = short_metrics(tr)
    return dict(trades=m["n"], win_rate=round(m["wins"] / max(1, m["n"]), 3), gross_profit=round(m["gp"], 0), gross_loss=round(m["gl"], 0), net=round(m["net"], 0), spread_cost=round(m["spread"], 0),
                gross_before_costs=round(m["gross_ex"], 0), pf=round(m["pf"], 2), expectancy=round(m["exp"], 2), max_dd=round(m["dd"], 0), avg_win=round(m["avg_win"], 2), avg_loss=round(m["avg_loss"], 2), max_consec_losses=m["mcl"], avg_r=round(m["avg_r"], 3))
OUT["before_after"] = {per: dict(baseline=full_row(in_period(base, per) if per != "ALL" else base), combined=full_row(in_period(comb, per) if per != "ALL" else comb)) for per in ("DEV", "VAL", "OOS", "ALL")}
OUT["baseline_exits"] = base.exit_reason.value_counts().to_dict(); OUT["combined_exits"] = comb.exit_reason.value_counts().to_dict()
OUT["generated"] = str(pd.Timestamp.now())[:16]
json.dump(OUT, open("results/lab/lab.json", "w"), indent=1, default=lambda x: float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
print(f"stage 2 done ({time.time()-T0:.0f}s)")
