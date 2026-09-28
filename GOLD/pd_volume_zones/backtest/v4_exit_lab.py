"""
v4_exit_lab.py - exit-structure research on the frozen V1 entries.

Entry, zones, POC and filters are untouched. Every exit variant is applied to the SAME
2,049 V1 entries (pinned 39 months) as independent trades, so the comparison isolates the
exit; the position-slot interaction is then checked with exact engine runs for anything
that survives the acceptance criteria. The 21 months added to the data folder after V1
was frozen are evaluated for every variant but are NOT used by the selection code.

Acceptance (pre-registered, applied against "Original 3R" under the same conservative
execution rule): improvement in average net R overall, in Development, in Validation and
Out-of-sample; improvement in at least 4 of 6 years and still positive with the best year
removed; improvement kept at 1.5x spread; an adjacent parameter in the family also
improves (where the family has parameters); and only then the 21 untouched months.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import exit_sim as X
import pdvz_engine as E

OUT = "results/v4"
os.makedirs(OUT, exist_ok=True)
PERIODS = ("DEV", "VAL", "OOS")
HORIZON = 3 * 86400000

VARIANTS = [
    ("fixed", "Original 3R", dict(target_R=3.0)),
    ("fixed", "Target 0.5R", dict(target_R=0.5)),
    ("fixed", "Target 0.75R", dict(target_R=0.75)),
    ("fixed", "Target 1R", dict(target_R=1.0)),
    ("fixed", "Target 1.25R", dict(target_R=1.25)),
    ("fixed", "Target 1.5R", dict(target_R=1.5)),
    ("fixed", "Target 2R", dict(target_R=2.0)),
    ("fixed", "Target 2.5R", dict(target_R=2.5)),
    ("fixed", "Target 4R", dict(target_R=4.0)),
    ("be", "BE-1: stop to entry after +1R (TP 3R)", dict(target_R=3.0, be=(1.0, 0.0))),
    ("be", "BE-1.5: stop to entry after +1.5R (TP 3R)", dict(target_R=3.0, be=(1.5, 0.0))),
    ("be", "BE-2: stop to entry after +2R (TP 3R)", dict(target_R=3.0, be=(2.0, 0.0))),
    ("lock", "Lock A: at +1R stop to +0.25R (TP 3R)", dict(target_R=3.0, locks=[(1.0, 0.25)])),
    ("lock", "Lock B: at +1.5R stop to +0.5R (TP 3R)", dict(target_R=3.0, locks=[(1.5, 0.5)])),
    ("lock", "Lock C: at +2R stop to +1R (TP 3R)", dict(target_R=3.0, locks=[(2.0, 1.0)])),
    ("atr", "ATR trail 1.0 x ATR14 after +1R (TP 3R)", dict(target_R=3.0, trail=dict(kind="atr", mult=1.0, activate_R=1.0))),
    ("atr", "ATR trail 1.5 x ATR14 after +1R (TP 3R)", dict(target_R=3.0, trail=dict(kind="atr", mult=1.5, activate_R=1.0))),
    ("atr", "ATR trail 2.0 x ATR14 after +1R (TP 3R)", dict(target_R=3.0, trail=dict(kind="atr", mult=2.0, activate_R=1.0))),
    ("atr_nt", "ATR trail 1.0 x ATR14 after +1R, no target", dict(target_R=None, trail=dict(kind="atr", mult=1.0, activate_R=1.0))),
    ("atr_nt", "ATR trail 1.5 x ATR14 after +1R, no target", dict(target_R=None, trail=dict(kind="atr", mult=1.5, activate_R=1.0))),
    ("atr_nt", "ATR trail 2.0 x ATR14 after +1R, no target", dict(target_R=None, trail=dict(kind="atr", mult=2.0, activate_R=1.0))),
    ("struct", "Structure trail: last completed 5-min candle low/high after +1R (TP 3R)", dict(target_R=3.0, trail=dict(kind="bar", activate_R=1.0))),
    ("struct", "Structure trail: confirmed 2-candle swing low/high after +1R (TP 3R)", dict(target_R=3.0, trail=dict(kind="swing", activate_R=1.0, k=2))),
    ("partial", "P1: 50% at 1R, 50% at 3R", dict(target_R=3.0, partial=(0.5, 1.0))),
    ("partial", "P2: 50% at 1.5R, 50% at 3R", dict(target_R=3.0, partial=(0.5, 1.5))),
    ("partial", "P3: 50% at 2R, 50% at 4R", dict(target_R=4.0, partial=(0.5, 2.0))),
]
FAMILY_ORDER = {"fixed": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0]}


def get_trades(D):
    tr, _, _ = E.run(D, dict(simulate_skipped=False), verbose=False)
    tr = tr[tr.exit_reason.isin(["SL", "TP"])].reset_index(drop=True)
    tf_ms = D["tf_min"] * 60000
    tr["i5"] = np.searchsorted(D["t"], tr.t_ms.values)
    tr["j0"] = np.searchsorted(D["m1t"], tr.t_ms.values + tf_ms)
    return tr


def walk_all(tr, D, spec, horizon=None):
    return [X.walk(r.side, r.entry, r.sl, r.risk_pts, int(r.j0), int(r.i5), D, spec, horizon_ms=horizon, atr=r.atr14) for r in tr.itertuples()]


def metrics(R, net):
    R = np.asarray(R, float)
    net = np.asarray(net, float)
    if len(R) == 0:
        return dict(n=0, wr=np.nan, gross=0.0, net=0.0, avg=np.nan, avg_net=np.nan, pf=np.nan, dd=0.0, streak=0)
    gp, gl = R[R > 0].sum(), -R[R < 0].sum()
    cum = np.cumsum(R)
    streak = best = 0
    for x in R:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return dict(n=int(len(R)), wr=float((R > 0).mean()), gross=float(R.sum()), net=float(net.sum()), avg=float(R.mean()),
                avg_net=float(net.mean()), pf=float(gp / gl) if gl > 0 else float("inf"),
                dd=float((np.maximum.accumulate(cum) - cum).max()), streak=int(best))


def f(x, spec):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) else ""
    return spec.format(x)


def main():
    # ------------------------------------------------------------ data and entries
    D39 = E.prepare(E.load_m1(E.v1_chunk_files()))
    tr = get_trades(D39)
    cuts = (float(np.quantile(tr.t_ms, 0.6)), float(np.quantile(tr.t_ms, 0.8)))
    cut_dates = [str(pd.Timestamp(c, unit="ms").date()) for c in cuts]
    tr["period"] = np.where(tr.t_ms < cuts[0], "DEV", np.where(tr.t_ms < cuts[1], "VAL", "OOS"))
    years = sorted(tr.year.unique().tolist())
    print("entries", len(tr), cut_dates)

    # ------------------------------------------------------------ STEP 1: path with the original stop only (3-day horizon)
    free = walk_all(tr, D39, dict(target_R=None), horizon=HORIZON)
    ref = walk_all(tr, D39, dict(target_R=3.0))
    valid = np.array([w["reason"] in ("SL", "TP") for w in ref])
    tr = tr[valid].reset_index(drop=True)
    free = [w for w, v in zip(free, valid) if v]
    ref = [w for w, v in zip(ref, valid) if v]
    refR = np.array([w["R"] for w in ref])
    cost = tr.cost_R.values
    reached = {L: np.array([w["first"][L] is not None for w in free]) for L in X.LEVELS}
    reach3 = reached[3.0]
    step1 = []
    for L in X.LEVELS:
        m = reached[L]
        step1.append(dict(level=L, pct_reach=float(m.mean()), n=int(m.sum()),
                          pct_reach_and_lose=float((refR[m] <= 0).mean()) if m.sum() else np.nan,
                          pct_reach_and_3R=float(reach3[m].mean()) if m.sum() else np.nan))
    mfe_free = np.array([w["mfe"] for w in free])
    mfe_ref = np.array([w["mfe"] for w in ref])
    mae_ref = np.array([w["mae"] for w in ref])
    censored = float(np.mean([w["reason"] == "horizon" for w in free]))
    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    dist = dict(
        mfe_free_mean=float(mfe_free.mean()), mfe_free_median=float(np.median(mfe_free)), censored_3d=censored,
        mfe_ref_mean=float(mfe_ref.mean()), mfe_ref_median=float(np.median(mfe_ref)),
        mfe_winners=[float(np.quantile(mfe_free[refR > 0], q)) for q in qs],
        mfe_losers=[float(np.quantile(mfe_free[refR <= 0], q)) for q in qs],
        mfe_losers_capped=[float(np.quantile(mfe_ref[refR <= 0], q)) for q in qs],
        mae_all=[float(np.quantile(mae_ref, q)) for q in qs],
        mae_winners=[float(np.quantile(mae_ref[refR > 0], q)) for q in qs],
        losers_reached={L: float(reached[L][refR <= 0].mean()) for L in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5)},
        winners_mae_ge={x: float((mae_ref[refR > 0] >= x).mean()) for x in (0.25, 0.5, 0.75)},
    )
    # ------------------------------------------------------------ STEP 8: path dependency (measured on the 3R-rule walk: before 3R or the stop)
    path = []
    for L in X.POST_LEVELS:
        m = np.array([w["post_min"][L] is not None for w in ref])
        pm = np.array([w["post_min"][L] if w["post_min"][L] is not None else np.nan for w in ref])
        for gb, lab in ((0.5, "gave back >= 0.5R"), (1.0, "gave back >= 1R (to entry for L=1)")):
            g = m & (pm <= L - gb)
            ng = m & (pm > L - gb)
            path.append(dict(level=L, split=lab, n_gaveback=int(g.sum()), p3_gaveback=float((refR[g] > 0).mean()) if g.sum() else np.nan,
                             n_held=int(ng.sum()), p3_held=float((refR[ng] > 0).mean()) if ng.sum() else np.nan))
    seq = {}
    m1_ = reached[1.0]
    seq["reached 1R then 2R"] = m1_ & reached[2.0]
    seq["reached 1R, never 2R"] = m1_ & ~reached[2.0]
    pm15 = np.array([w["post_min"][1.5] if w["post_min"][1.5] is not None else np.nan for w in ref])
    seq["reached 1.5R then fell to <= 0.5R"] = reached[1.5] & (pm15 <= 0.5)
    seq["reached 1.5R and held above 0.5R"] = reached[1.5] & (pm15 > 0.5)
    seq_rows = [dict(seq=k, n=int(v.sum()), p3=float(reach3[v].mean()) if v.sum() else np.nan, avg_ref_R=float(refR[v].mean()) if v.sum() else np.nan) for k, v in seq.items()]

    # ------------------------------------------------------------ STEPS 2-7: variants on the fixed entry set
    res = {}
    walks = {}
    for fam, label, spec in VARIANTS:
        ws = walk_all(tr, D39, spec)
        walks[label] = ws
        R = np.array([w["R"] for w in ws])
        net = R - cost
        net15 = R - 1.5 * cost
        s = dict(family=fam, label=label, all=metrics(R, net), net15_avg=float(net15.mean()),
                 reasons=pd.Series([w["reason"] for w in ws]).value_counts().to_dict())
        for per in PERIODS:
            m = (tr.period == per).values
            s[per] = metrics(R[m], net[m])
        s["years"] = {int(y): metrics(R[(tr.year == y).values], net[(tr.year == y).values]) for y in years}
        s["R"] = R
        res[label] = s
        print(f"  {label[:55]:55s} n={s['all']['n']} wr={s['all']['wr']:.3f} net={s['all']['net']:+.1f} avg net={s['all']['avg_net']:+.3f}")
    REF = res["Original 3R"]
    # break-even decomposition (STEP 3) and lock decomposition
    decomp = {}
    for fam, label, spec in VARIANTS:
        if fam in ("be", "lock", "atr", "struct", "partial", "atr_nt"):
            R = res[label]["R"]
            killed = int(((refR > 0) & (R <= 0.001)).sum())
            saved = int(((refR < 0) & (R >= -0.001)).sum())
            reduced = int(((refR < 0) & (R > refR + 1e-9) & (R < -0.001)).sum())
            cut_short = int(((refR > 0) & (R > 0.001) & (R < refR - 1e-9)).sum())
            decomp[label] = dict(killed_winners=killed, saved_losers=saved, losers_reduced=reduced, winners_cut_short=cut_short,
                                 net_effect=float((R - refR).sum()))

    # ------------------------------------------------------------ acceptance (39 months only)
    def imp(s, per=None):
        a, b = (s[per] if per else s["all"]), (REF[per] if per else REF["all"])
        return a["avg_net"] - b["avg_net"]

    fam_members = {}
    for fam, label, spec in VARIANTS:
        fam_members.setdefault(fam, []).append(label)
    accept = {}
    for fam, label, spec in VARIANTS:
        if label == "Original 3R":
            continue
        s = res[label]
        yr_imp = {y: s["years"][y]["avg_net"] - REF["years"][y]["avg_net"] for y in years if s["years"][y]["n"] > 0}
        best_year = max(yr_imp, key=yr_imp.get)
        n_y = sum(1 for y in years if s["years"][y]["n"] > 0)
        w_all = sum(s["years"][y]["n"] * (s["years"][y]["avg_net"] - REF["years"][y]["avg_net"]) for y in yr_imp if y != best_year)
        n_all = sum(s["years"][y]["n"] for y in yr_imp if y != best_year)
        c = dict(
            c1_all=imp(s) > 0, c2_dev=imp(s, "DEV") > 0, c3_val=imp(s, "VAL") > 0, c4_oos=imp(s, "OOS") > 0,
            c5_years=(sum(1 for v in yr_imp.values() if v > 0) >= 4) and (w_all / n_all > 0 if n_all else False),
            c6_cost=(s["net15_avg"] - REF["net15_avg"]) > 0,
        )
        members = fam_members[fam]
        others = [m for m in members if m != label and m != "Original 3R"]
        if fam in ("struct",) or not others:
            c["c7_param"] = None
        else:
            idx = members.index(label)
            neigh = [m for m in (members[idx - 1] if idx - 1 >= 0 else None, members[idx + 1] if idx + 1 < len(members) else None) if m and m != "Original 3R"]
            c["c7_param"] = any(imp(res[m]) > 0 for m in neigh) if neigh else None
        c["pass_1_7"] = all(v for k, v in c.items() if v is not None and k != "pass_1_7")
        c["years_improved"] = sum(1 for v in yr_imp.values() if v > 0)
        c["n_years"] = n_y
        c["imp_all"], c["imp_DEV"], c["imp_VAL"], c["imp_OOS"] = imp(s), imp(s, "DEV"), imp(s, "VAL"), imp(s, "OOS")
        accept[label] = c
    survivors = [l for l, c in accept.items() if c["pass_1_7"]]
    print("survivors of criteria 1-7:", survivors)

    # ------------------------------------------------------------ 21 untouched months (evaluated for every variant; used only for criterion 8)
    all_files = sorted(x for x in os.listdir(E.CHUNK_DIR) if x.startswith("bid_"))
    new_months = sorted(x[4:11] for x in all_files if x[4:11] not in E.V1_MONTHS)
    D57 = E.prepare(E.load_m1([f"{E.CHUNK_DIR}/{x}" for x in all_files]))
    trn = get_trades(D57)
    trn = trn[trn.month.isin(new_months)].reset_index(drop=True)
    refn = walk_all(trn, D57, dict(target_R=3.0))
    vn = np.array([w["reason"] in ("SL", "TP") for w in refn])
    trn = trn[vn].reset_index(drop=True)
    costn = trn.cost_R.values
    newres = {}
    for fam, label, spec in VARIANTS:
        ws = walk_all(trn, D57, spec)
        R = np.array([w["R"] for w in ws])
        newres[label] = metrics(R, R - costn)
        newres[label]["years"] = {int(y): metrics(R[(trn.year == y).values], (R - costn)[(trn.year == y).values]) for y in sorted(trn.year.unique())}
    for l in accept:
        accept[l]["c8_new21"] = newres[l]["avg_net"] - newres["Original 3R"]["avg_net"] > 0
        accept[l]["imp_new21"] = newres[l]["avg_net"] - newres["Original 3R"]["avg_net"]

    # ------------------------------------------------------------ exact engine runs (position interaction) for the reference and survivors
    exact = {}
    for label in ["Original 3R"] + survivors:
        spec = next(sp for fam, l, sp in VARIANTS if l == label)
        t2, _, _ = E.run(D39, dict(simulate_skipped=False, exit_spec=spec), verbose=False)
        t2 = t2[t2.exit_reason.isin(("SL", "TP", "TSL"))]
        t2p = np.where(t2.t_ms < cuts[0], "DEV", np.where(t2.t_ms < cuts[1], "VAL", "OOS"))
        exact[label] = dict(all=metrics(t2.result_R.values, t2.net_R.values),
                            **{per: metrics(t2.result_R.values[t2p == per], t2.net_R.values[t2p == per]) for per in PERIODS})

    # ------------------------------------------------------------ report
    L = []
    w = L.append
    w("# V4 Exit Structure Report - does the path after entry contain exploitable information?\n")
    w(f"Entries: the {len(tr):,} V1 trades of the pinned 39 months (Development before {cut_dates[0]}: {int((tr.period == 'DEV').sum())}, "
      f"Validation to {cut_dates[1]}: {int((tr.period == 'VAL').sum())}, Out-of-sample after: {int((tr.period == 'OOS').sum())}). Entry price, initial stop, "
      "zones, POC and filters are exactly V1. Every exit variant is applied to the same entries as independent trades, so trade counts are "
      "equal by construction and the comparison isolates the exit. Costs: one spread per trade as in V1-V3; the '1.5x spread' column is the "
      "slippage sensitivity.\n")
    w("**Execution rule (STEP 9).** Inside an M1 candle the stop is checked first against the level in force before the candle; the target or "
      "partial level is checked only if the stop was not hit, so when both lie inside one candle the stop wins. Gaps fill at the open. Every "
      "stop move (break-even, lock, ATR or structure trail) is computed at the candle's close and applies from the next candle; structure "
      "levels use completed 5-min candles and a swing is confirmed 2 candles after its centre; the ATR is the 5-min ATR14 at entry. This is "
      f"more conservative than the V1 engine's TradingView-style path guess: the same 3R rule gives {REF['all']['avg_net']:+.3f}R net per trade "
      f"here against -0.087 in V1 (the difference is the candles where stop and target overlapped).\n")
    # STEP 1
    w("## STEP 1 - MFE / MAE distribution (original stop only, 3-day horizon; 'eventually' = under the original 3R rule)\n")
    w(f"Uncapped MFE before the original stop: mean {dist['mfe_free_mean']:.2f}R, median {dist['mfe_free_median']:.2f}R "
      f"({100 * dist['censored_3d']:.0f}% of trades were still open after 3 days and are censored there). Under the 3R rule: mean "
      f"{dist['mfe_ref_mean']:.2f}R, median {dist['mfe_ref_median']:.2f}R.\n")
    w("| Level | Reached before the original stop | Reached and eventually lost | Reached and eventually hit 3R |\n|---|---|---|---|")
    for r in step1:
        w(f"| +{r['level']}R | {100 * r['pct_reach']:.1f}% ({r['n']}) | {f(100 * r['pct_reach_and_lose'], '{:.1f}%')} | {f(100 * r['pct_reach_and_3R'], '{:.1f}%')} |")
    w("")
    w("| Distribution (R) | p10 | p25 | median | p75 | p90 |\n|---|---|---|---|---|---|")
    for k, lab in (("mfe_winners", "MFE of winners (uncapped)"), ("mfe_losers", "MFE of losers (uncapped, before the stop)"),
                   ("mfe_losers_capped", "MFE of losers before the stop (3R rule)"), ("mae_all", "MAE of all trades"), ("mae_winners", "MAE of winners")):
        w(f"| {lab} | " + " | ".join(f"{x:.2f}" for x in dist[k]) + " |")
    w("")
    w("Losers that were first in profit by at least: " + ", ".join(f"{L}R {100 * v:.0f}%" for L, v in dist["losers_reached"].items()) +
      ". Winners that first went against by at least: " + ", ".join(f"{x}R {100 * v:.0f}%" for x, v in dist["winners_mae_ge"].items()) + ".\n")
    # STEP 8
    w("## STEP 8 - Path dependency (measured before the 3R target or the stop was hit)\n")
    w("| After first reaching | Split | n | Went on to 3R |\n|---|---|---|---|")
    for r in path:
        w(f"| +{r['level']}R | {r['split']} | {r['n_gaveback']} | {f(100 * r['p3_gaveback'], '{:.1f}%')} |")
        w(f"| +{r['level']}R | held (did not give back that much) | {r['n_held']} | {f(100 * r['p3_held'], '{:.1f}%')} |")
    w("")
    w("| Sequence | n | Reached 3R | Avg R under the 3R rule |\n|---|---|---|---|")
    for r in seq_rows:
        w(f"| {r['seq']} | {r['n']} | {f(100 * r['p3'], '{:.1f}%')} | {f(r['avg_ref_R'], '{:+.3f}')} |")
    w("")
    # STEPS 2-7 tables
    HEAD = ("| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD (R) | Longest losing run | Avg net R at 1.5x spread | DEV avg net R | VAL | OOS |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def row(label):
        s = res[label]
        return (f"| {label} | {s['all']['n']} | {s['all']['wr']:.1%} | {s['all']['gross']:+.1f} | {s['all']['net']:+.1f} | {s['all']['avg_net']:+.3f} | "
                f"{f(s['all']['pf'], '{:.2f}')} | {s['all']['dd']:.0f} | {s['all']['streak']} | {s['net15_avg']:+.3f} | "
                f"{s['DEV']['avg_net']:+.3f} | {s['VAL']['avg_net']:+.3f} | {s['OOS']['avg_net']:+.3f} |")

    for fam, title in (("fixed", "STEP 2 - Fixed R:R exit curve"), ("be", "STEP 3 - Break-even"), ("lock", "STEP 4 - Profit lock"),
                       ("atr", "STEP 5 - ATR trailing stop (target kept)"), ("atr_nt", "STEP 5b - ATR trailing stop, no target"),
                       ("struct", "STEP 6 - Structure trailing"), ("partial", "STEP 7 - Partial exits")):
        w(f"## {title}\n")
        w(HEAD)
        if fam != "fixed":
            w(row("Original 3R"))
        for f_, label, spec in VARIANTS:
            if f_ == fam:
                w(row(label))
        w("")
        if fam in ("be", "lock", "atr", "atr_nt", "struct", "partial"):
            w("| Exit | Winners killed (3R -> <= 0) | Losers saved (-1 -> >= 0) | Losers reduced | Winners cut short | Net effect vs 3R (R) |\n|---|---|---|---|---|---|")
            for f_, label, spec in VARIANTS:
                if f_ == fam:
                    d = decomp[label]
                    w(f"| {label} | {d['killed_winners']} | {d['saved_losers']} | {d['losers_reduced']} | {d['winners_cut_short']} | {d['net_effect']:+.1f} |")
            w("")
    w("### Per-year average net R\n")
    w("| Exit | " + " | ".join(str(y) for y in years) + " |\n|---|" + "---|" * len(years))
    for fam, label, spec in VARIANTS:
        s = res[label]
        w(f"| {label} | " + " | ".join(f"{s['years'][y]['avg_net']:+.3f}" if s["years"][y]["n"] else "-" for y in years) + " |")
    w("")
    # STEP 12 final table
    w("## STEP 12 - Final comparison\n")
    w("| Exit | Trades | Win rate | Gross R | Net R | Avg net R | PF | Max DD | DEV | VAL | OOS | New 21 months (n / avg net R) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for fam, label, spec in VARIANTS:
        s = res[label]
        nn = newres[label]
        w(f"| {label} | {s['all']['n']} | {s['all']['wr']:.1%} | {s['all']['gross']:+.1f} | {s['all']['net']:+.1f} | {s['all']['avg_net']:+.3f} | "
          f"{f(s['all']['pf'], '{:.2f}')} | {s['all']['dd']:.0f} | {s['DEV']['avg_net']:+.3f} | {s['VAL']['avg_net']:+.3f} | {s['OOS']['avg_net']:+.3f} | "
          f"{nn['n']} / {nn['avg_net']:+.3f} |")
    w("")
    w("## Acceptance criteria (improvement in average net R against 'Original 3R' under the same execution rule)\n")
    w("| Exit | 1 overall | 2 DEV | 3 VAL | 4 OOS | 5 years (improved / with best year removed) | 6 at 1.5x spread | 7 adjacent parameter | Passes 1-7 | 8 untouched 21 months |\n|---|---|---|---|---|---|---|---|---|---|")
    for fam, label, spec in VARIANTS:
        if label == "Original 3R":
            continue
        c = accept[label]
        yn = lambda v: "n/a" if v is None else ("yes" if v else "no")
        w(f"| {label} | {yn(c['c1_all'])} ({c['imp_all']:+.3f}) | {yn(c['c2_dev'])} ({c['imp_DEV']:+.3f}) | {yn(c['c3_val'])} ({c['imp_VAL']:+.3f}) | "
          f"{yn(c['c4_oos'])} ({c['imp_OOS']:+.3f}) | {yn(c['c5_years'])} ({c['years_improved']}/{c['n_years']}) | {yn(c['c6_cost'])} | {yn(c['c7_param'])} | "
          f"**{yn(c['pass_1_7'])}** | {yn(c['c8_new21'])} ({c['imp_new21']:+.3f}) |")
    w("")
    w("## Exact engine runs (one position at a time, an earlier exit frees the slot for the next signal)\n")
    w("| Exit | Trades | Win rate | Net R | Avg net R | DEV | VAL | OOS |\n|---|---|---|---|---|---|---|---|")
    for label, s in exact.items():
        w(f"| {label} | {s['all']['n']} | {s['all']['wr']:.1%} | {s['all']['net']:+.1f} | {s['all']['avg_net']:+.3f} | {s['DEV']['avg_net']:+.3f} | {s['VAL']['avg_net']:+.3f} | {s['OOS']['avg_net']:+.3f} |")
    w("")
    open("V4_EXIT_RESEARCH_REPORT.md", "w", encoding="utf-8").write("\n".join(L))
    json.dump(dict(cut_dates=cut_dates, step1=step1, dist=dist, path=path, seq=seq_rows,
                   variants={l: {k: v for k, v in s.items() if k != "R"} for l, s in res.items()},
                   decomp=decomp, accept=accept, new21=newres, new_months=new_months, exact=exact, survivors=survivors),
              open(f"{OUT}/v4_lab.json", "w"), indent=1, default=str)
    pd.DataFrame({"time_utc": tr.time_utc, "side": tr.side, "period": tr.period, "year": tr.year, "risk": tr.risk_pts, "cost_R": cost,
                  **{l: res[l]["R"] for l in res}}).to_csv(f"{OUT}/per_trade_R_by_exit.csv", index=False)
    print("report written")


if __name__ == "__main__":
    main()
