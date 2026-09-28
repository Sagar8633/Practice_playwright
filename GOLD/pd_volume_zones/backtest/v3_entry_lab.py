"""
v3_entry_lab.py - entry quality research on the frozen V1 trade set.

Question: does the information available at the close of the confirmation candle
distinguish good setups from bad ones? Every feature below is computed by the engine
from bars <= the confirmation candle and the zones known at that time. No future bar,
no MFE/MAE, no outcome enters any feature. Outcome labels (win, false breakout) are
used only as analysis TARGETS, never as inputs.

Chronological split: same as V2 (60/80% of the V1 trades by time).
Selection of candidate filters uses Development + Validation only; Out-of-sample is
reported for every filter but never used to choose.

Outputs: results/v3/*.csv, results/v3/v3_lab.json, V3_ENTRY_QUALITY_REPORT.md
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import pdvz_engine as E

DATA = "../../../Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_*.csv"
OUT = "results/v3"
os.makedirs(OUT, exist_ok=True)
PERIODS = ("DEV", "VAL", "OOS")

NUMERIC = [
    ("tap_close_dist_poc_zh", "Tap candle close vs POC (rect. heights, + = toward the trade)"),
    ("tap_depth_zh", "Tap wick past the POC (rect. heights)"),
    ("pen_depth_zh", "Penetration into the rectangle during the interaction (1 = far edge)"),
    ("taps", "POC taps today"), ("touches_today", "Rectangle touches today"), ("inside_today", "Closes inside today"),
    ("ep_bars", "Candles in the current interaction"), ("ep_inside", "Candles closed inside (interaction)"),
    ("ep_touches", "Candles touching the rectangle (interaction)"), ("ep_taps", "POC taps (interaction)"),
    ("ep_rej", "Reject-and-return count (interaction)"),
    ("failed_same", "Prior failed breakouts in the trade direction (today)"), ("failed_opp", "Prior failed breakouts the other way (today)"),
    ("poc_crosses_12", "POC crosses in the last 12 candles"), ("bars_since_tap", "Candles since the last POC tap"),
    ("conf_body_pct", "Confirmation body / range"), ("conf_close_pos", "Close position in the candle (1 = at the extreme, trade direction)"),
    ("conf_wick_against_pct", "Wick against the trade / range"), ("conf_wick_with_pct", "Wick with the trade / range"),
    ("conf_range_atr", "Confirmation range / ATR14"), ("conf_body_atr", "Confirmation body / ATR14"),
    ("conf_range_zh", "Confirmation range / rectangle height"),
    ("conf_ext_zh", "Close beyond the edge (rect. heights)"), ("conf_ext_atr", "Close beyond the edge (ATR)"),
    ("entry_dist_poc_zh", "Entry distance from POC (rect. heights)"), ("risk_pts", "Stop distance (USD)"), ("risk_atr", "Stop distance / ATR14"),
    ("zone_height", "Rectangle height (USD)"), ("zone_h_pct_range", "Rectangle height / prior-day range"), ("zone_height_atr", "Rectangle height / ATR14"),
    ("zone_prom_rel", "Volume prominence (HVN only)"), ("zone_share", "Volume share of the day"), ("poc_pos_in_zone", "POC position in the rectangle"),
    ("room_to_pdhl_R", "Room to the prior-day High/Low in the trade direction (R)"),
    ("dist_pdh_zh", "Rectangle to prior-day High (heights)"), ("dist_pdl_zh", "Rectangle to prior-day Low (heights)"),
    ("zone_pos_range", "Rectangle position in the prior-day range (0 = Low, 1 = High)"),
    ("opp_gap_R", "Distance to the nearest opposing rectangle (R)"), ("nearest_gap_zh", "Distance to the nearest rectangle (heights)"),
    ("mom3_atr", "Momentum of the 3 candles before (ATR, + = with the trade)"), ("mom5_atr", "Momentum of the 5 candles before (ATR)"),
    ("same_dir_last5", "Same-direction candles among the last 5"), ("alternations6", "Colour changes in the last 6 candles"),
    ("trend20_atr", "20-candle trend before entry (ATR, + = with the trade)"),
    ("struct20_atr", "Distance below the 20-candle extreme (ATR, negative = new extreme)"), ("struct50_atr", "... 50-candle extreme"),
    ("approach_speed_atr", "Approach speed: 5-candle move before the confirmation (ATR)"),
    ("atr14", "ATR14 (USD)"), ("atr_rel", "ATR14 / 7-day median"), ("atr_pct7", "ATR14 percentile (7 days)"), ("atr_pct30", "ATR14 percentile (30 days)"),
    ("bars_into_day", "Candles since the zones were created"), ("hour_utc", "Hour (UTC)"), ("prior_trades_today", "Trades already taken today"),
    ("n_zones", "Rectangles on the day"),
]
CATEG = [("side", "Side"), ("zone_kind", "Rectangle type"), ("session", "Session"), ("poc_type", "POC interaction type"),
         ("prev_same_dir", "Previous candle in the trade direction"), ("first_touch", "First POC touch"),
         ("tp_clear", "No rectangle between entry and target"), ("tp_beyond_pdhl", "Target beyond the prior-day High/Low"),
         ("tap_closed_inside", "Tap candle closed inside the rectangle")]
NUM_COLS = [c for c, _ in NUMERIC]
NAME = dict(NUMERIC + CATEG)


# ----------------------------------------------------------------------------
def auc(x, y):
    """Rank AUC of x for the positive class y (True). Returns (auc, se, n)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=bool)
    m = ~np.isnan(x)
    x, y = x[m], y[m]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 < 5 or n0 < 5:
        return np.nan, np.nan, n1 + n0
    r = pd.Series(x).rank().values
    a = (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = math.sqrt(max(0.0, (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)))
    return float(a), float(se), n1 + n0


def metrics(tr):
    if len(tr) == 0:
        return dict(n=0, wr=np.nan, gross=0.0, net=0.0, avg=np.nan, avg_net=np.nan, pf=np.nan, dd=0.0)
    r = tr.result_R.values
    net = tr.net_R.values
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    cum = np.cumsum(r)
    return dict(n=int(len(r)), wr=float((r > 0).mean()), gross=float(r.sum()), net=float(net.sum()), avg=float(r.mean()),
                avg_net=float(net.mean()), pf=float(gp / gl) if gl > 0 else float("inf"), dd=float((np.maximum.accumulate(cum) - cum).max()))


def f(x, spec):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) else ""
    return spec.format(x)


def bucket_table(df, labels, title, w):
    """labels: Series aligned with df. Rows = bucket, columns = per period n / win / avg net R."""
    w(f"**{title}**\n")
    w("| Bucket | All (n / win / avg net R) | DEV | VAL | OOS |\n|---|---|---|---|---|")
    for lab in [x for x in pd.unique(labels.dropna())]:
        m = (labels == lab).values
        cells = [str(lab)]
        for per in (None,) + PERIODS:
            mm = m if per is None else m & (df.period.values == per)
            if mm.sum() == 0:
                cells.append("-")
            else:
                cells.append(f"{mm.sum()} / {100 * (df.result_R.values[mm] > 0).mean():.0f}% / {df.net_R.values[mm].mean():+.3f}")
        w("| " + " | ".join(cells) + " |")
    w("")


def qlabels(s, q=4):
    try:
        cats = pd.qcut(s, q, duplicates="drop")
        return cats.apply(lambda iv: f"{iv.left:.2f} to {iv.right:.2f}" if isinstance(iv, pd.Interval) else np.nan)
    except ValueError:
        return pd.Series([np.nan] * len(s), index=s.index)


def per_period_row(label, m_by):
    return "| " + label + " | " + " | ".join(
        f"{m_by[p]['n']} / {f(m_by[p]['wr'], '{:.0%}')} / {f(m_by[p]['net'], '{:+.0f}')} / {f(m_by[p]['avg_net'], '{:+.3f}')}" for p in ("all",) + PERIODS) + " |"


HEAD_PP = "| Variant | All (n / win / net R / avg net R) | DEV | VAL | OOS |\n|---|---|---|---|---|"


def by_period(tr):
    return {"all": metrics(tr), **{p: metrics(tr[tr.period == p]) for p in PERIODS}}


def main():
    D = E.prepare(E.load_m1(E.v1_chunk_files()))
    v1, _, info = E.run(D, dict(simulate_skipped=False), verbose=False)
    v1 = v1[v1.exit_reason.isin(["SL", "TP"])].reset_index(drop=True)
    cuts = (float(np.quantile(v1.t_ms, 0.6)), float(np.quantile(v1.t_ms, 0.8)))
    cut_dates = [str(pd.Timestamp(c, unit="ms").date()) for c in cuts]

    def label_periods(df):
        df = df.copy()
        df["period"] = np.where(df.t_ms < cuts[0], "DEV", np.where(df.t_ms < cuts[1], "VAL", "OOS"))
        return df

    v1 = label_periods(v1)
    v1["win"] = v1.result_R > 0
    v1["fb"] = v1.false_breakout_3bars.astype(bool)
    v1.to_csv(f"{OUT}/trade_log_v1_enriched.csv", index=False)
    dev, val, oos = (v1[v1.period == p] for p in PERIODS)
    base = by_period(v1)
    print("V1", base["all"]["n"], "trades; periods", {p: base[p]["n"] for p in PERIODS}, cut_dates)

    # ================================================================ A/B feature separation
    rows = []
    for col, title in NUMERIC:
        x = v1[col].astype(float)
        rec = dict(feature=col, title=title, med_loss=float(np.nanmedian(x[~v1.win])), med_win=float(np.nanmedian(x[v1.win])))
        a, se, n = auc(x, v1.win)
        rec.update(auc_all=a, se_all=se)
        for per, sub in zip(PERIODS, (dev, val, oos)):
            a, se, n = auc(sub[col].astype(float), sub.win)
            rec[f"auc_{per}"], rec[f"se_{per}"], rec[f"n_{per}"] = a, se, n
        afb, _, _ = auc(x, v1.fb)
        rec["auc_fb_all"] = afb
        for per, sub in zip(PERIODS, (dev, val, oos)):
            rec[f"auc_fb_{per}"] = auc(sub[col].astype(float), sub.fb)[0]
        d_dev, d_val = rec["auc_DEV"] - 0.5, rec["auc_VAL"] - 0.5
        rec["consistent"] = (not np.isnan(d_dev)) and (not np.isnan(d_val)) and np.sign(d_dev) == np.sign(d_val) and abs(d_dev) >= 0.03 and abs(d_val) >= 0.03
        rec["direction"] = "higher = better" if d_dev > 0 else "lower = better"
        rec["oos_agrees"] = (not np.isnan(rec["auc_OOS"])) and np.sign(rec["auc_OOS"] - 0.5) == np.sign(d_dev) and abs(rec["auc_OOS"] - 0.5) >= 0.02
        rows.append(rec)
    FT = pd.DataFrame(rows)
    FT["abs_dev"] = (FT.auc_DEV - 0.5).abs()
    FT = FT.sort_values("abs_dev", ascending=False)
    FT.to_csv(f"{OUT}/feature_separation.csv", index=False)
    cat_rows = []
    for col, title in CATEG:
        for lab in pd.unique(v1[col].astype(str)):
            rec = dict(feature=col, title=title, category=lab)
            for per, sub in zip(("all",) + PERIODS, (v1, dev, val, oos)):
                m = sub[col].astype(str) == lab
                rec[f"n_{per}"] = int(m.sum())
                rec[f"wr_{per}"] = float(sub.win[m].mean()) if m.sum() else np.nan
                rec[f"avgnet_{per}"] = float(sub.net_R[m].mean()) if m.sum() else np.nan
            cat_rows.append(rec)
    CT = pd.DataFrame(cat_rows)
    CT.to_csv(f"{OUT}/categorical_separation.csv", index=False)

    # ================================================================ models (fit on DEV only)
    model_res = {}
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        cat_cols = ["side", "zone_kind", "session", "poc_type"]
        X_all = pd.get_dummies(v1[NUM_COLS + cat_cols], columns=cat_cols, dtype=float)
        med = X_all[v1.period == "DEV"].median()
        X_all = X_all.fillna(med)
        for target in ("win", "fb"):
            y = v1[target].astype(int).values
            mdev = (v1.period == "DEV").values
            res = {}
            lr = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
            lr.fit(X_all[mdev], y[mdev])
            hgb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0, random_state=0)
            hgb.fit(X_all[mdev], y[mdev])
            for name, mdl in (("logistic", lr), ("gradient boosting", hgb)):
                pr = mdl.predict_proba(X_all)[:, 1]
                res[name] = {per: float(roc_auc_score(y[(v1.period == per).values], pr[(v1.period == per).values])) for per in PERIODS}
                if target == "win":
                    v1[f"score_{name.split()[0]}"] = pr
            model_res[target] = res
        # logistic coefficients (standardized) for the win model
        lr_win = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)).fit(X_all[(v1.period == "DEV").values], v1.win.astype(int).values[(v1.period == "DEV").values])
        coefs = pd.Series(lr_win[-1].coef_[0], index=X_all.columns).sort_values()
        model_res["lr_coefs_top"] = coefs.tail(8).round(3).to_dict()
        model_res["lr_coefs_bottom"] = coefs.head(8).round(3).to_dict()
    except Exception as ex:  # scikit-learn missing or similar
        model_res["error"] = repr(ex)

    # ================================================================ simple score from consistent features (DEV direction, DEV median)
    cons = FT[FT.consistent].head(5)
    simple_terms = []
    v1["score_simple"] = 0
    for _, r in cons.iterrows():
        thr = float(np.nanmedian(dev[r.feature].astype(float)))
        good = (v1[r.feature].astype(float) >= thr) if r.direction == "higher = better" else (v1[r.feature].astype(float) <= thr)
        v1["score_simple"] += good.fillna(False).astype(int)
        simple_terms.append(dict(feature=r.feature, title=r.title, direction=r.direction, threshold=thr))

    # ================================================================ candidate filters (post-filter on the trade list, approximate)
    filt_rows = []
    filters = []  # (label, keep_fn_rec, keep_mask_df)
    for _, r in FT[FT.consistent].iterrows():
        x_dev = dev[r.feature].astype(float)
        q = np.nanquantile(x_dev, 1 / 3) if r.direction == "higher = better" else np.nanquantile(x_dev, 2 / 3)
        col = r.feature
        if r.direction == "higher = better":
            keep = lambda rec, col=col, q=q: (rec[col] is None) or (isinstance(rec[col], float) and math.isnan(rec[col])) or rec[col] >= q
            mask = ~(v1[col].astype(float) < q)
            desc = f"remove {NAME[col]} < {q:.2f}"
        else:
            keep = lambda rec, col=col, q=q: (rec[col] is None) or (isinstance(rec[col], float) and math.isnan(rec[col])) or rec[col] <= q
            mask = ~(v1[col].astype(float) > q)
            desc = f"remove {NAME[col]} > {q:.2f}"
        filters.append((desc, keep, mask.values, col))
    # categorical filters: remove the worst category (DEV) if VAL agrees and n >= 60 in DEV
    for col, title in CATEG:
        sub = CT[CT.feature == col]
        sub = sub[(sub.n_DEV >= 60) & (sub.n_VAL >= 25)]
        if len(sub) < 2:
            continue
        worst = sub.sort_values("avgnet_DEV").iloc[0]
        if worst.avgnet_DEV < base["DEV"]["avg_net"] and worst.avgnet_VAL < base["VAL"]["avg_net"]:
            lab = worst.category
            keep = lambda rec, col=col, lab=lab: str(rec[col]) != lab
            mask = (v1[col].astype(str) != lab).values
            filters.append((f"remove {title} = {lab}", keep, mask, col))
    for desc, keep, mask, col in filters:
        kept = v1[mask]
        removed = v1[~mask]
        rec = dict(filter=desc, feature=col, removed=int((~mask).sum()), losers_removed=int((~removed.win).sum()), winners_removed=int(removed.win.sum()),
                   wr_before=base["all"]["wr"], wr_after=float(kept.win.mean()), net_before=base["all"]["net"], net_after=float(kept.net_R.sum()))
        for per in PERIODS:
            k = kept[kept.period == per]
            rec[f"{per}_avgnet_before"] = base[per]["avg_net"]
            rec[f"{per}_avgnet_after"] = float(k.net_R.mean()) if len(k) else np.nan
            rec[f"{per}_net_before"] = base[per]["net"]
            rec[f"{per}_net_after"] = float(k.net_R.sum()) if len(k) else np.nan
            rec[f"{per}_n_after"] = int(len(k))
        rec["imp_dev"] = rec["DEV_avgnet_after"] - rec["DEV_avgnet_before"]
        rec["imp_val"] = rec["VAL_avgnet_after"] - rec["VAL_avgnet_before"]
        rec["imp_oos"] = rec["OOS_avgnet_after"] - rec["OOS_avgnet_before"]
        rec["stability"] = min(rec["imp_dev"], rec["imp_val"])
        filt_rows.append(rec)
    FR = pd.DataFrame(filt_rows).sort_values("stability", ascending=False) if filt_rows else pd.DataFrame()
    if len(FR):
        FR.to_csv(f"{OUT}/candidate_filters.csv", index=False)

    # minimal rule: up to 3 filters that improve DEV and VAL avg net R, distinct features, keep >= 60% of DEV trades
    chosen = []
    if len(FR):
        for _, r in FR.iterrows():
            if r.imp_dev > 0 and r.imp_val > 0 and r.DEV_n_after >= 0.6 * base["DEV"]["n"] and r.feature not in [c["feature"] for c in chosen]:
                chosen.append(dict(filter=r["filter"], feature=r.feature, imp_dev=float(r.imp_dev), imp_val=float(r.imp_val), imp_oos=float(r.imp_oos)))
            if len(chosen) == 3:
                break
    keep_fns = {desc: keep for desc, keep, mask, col in filters}

    # ================================================================ exact V3 runs inside the engine
    exact = {}
    v2c = dict(min_risk_usd=4.0, target_rule="beyond_pdhl", target_margin_R=1.0)
    runs = [("V1", {}), ("V2 constraints (min stop 4 USD + target beyond by 1R)", v2c)]
    if chosen:
        fns = [keep_fns[c["filter"]] for c in chosen]
        combined = lambda rec, fns=fns: all(fn(rec) for fn in fns)
        runs.append(("V3 = V1 + minimal entry rule", dict(entry_filter=combined)))
        runs.append(("V3 on V2 constraints", dict(v2c, entry_filter=combined)))
        for c in chosen:
            runs.append((f"V1 + only: {c['filter']}", dict(entry_filter=keep_fns[c["filter"]])))
    for name, params in runs:
        p = dict(simulate_skipped=False)
        p.update(params)
        tr, _, inf = E.run(D, p, verbose=False)
        tr = label_periods(tr[tr.exit_reason.isin(["SL", "TP"])].reset_index(drop=True))
        exact[name] = by_period(tr)
        exact[name]["blocked"] = inf["blocked"]["entry_filter"]
        print(f"  exact: {name[:60]:60s} n={len(tr)} avg net {exact[name]['all']['avg_net']:+.3f}")

    # ================================================================ report
    L = []
    w = L.append
    w("# V3 Entry Quality Report - does pre-entry information separate good setups from bad ones?\n")
    w(f"V1 trade set: {base['all']['n']:,} trades ({base['all']['wr']:.1%} winners, {base['all']['net']:+.0f}R net). Split: Development before "
      f"{cut_dates[0]} ({base['DEV']['n']}), Validation to {cut_dates[1]} ({base['VAL']['n']}), Out-of-sample after ({base['OOS']['n']}). "
      "Exits unchanged (fixed SL at the rectangle edge, fixed 3R target). Every feature is computed from candles up to and including "
      "the confirmation candle and from the rectangles known at that time; outcome labels are analysis targets only.\n")
    w("How to read AUC: the probability that a random winner has a higher feature value than a random loser. 0.50 = no information; "
      "0.55 or 0.45 = weak; the standard error is about 0.017 in Development and 0.03 in Validation / Out-of-sample, so anything inside "
      "0.47-0.53 in DEV or 0.44-0.56 in VAL/OOS is noise. 'Consistent' = same direction in DEV and VAL with |AUC-0.5| >= 0.03 in both.\n")
    # ---- A / B
    w("## A. Entry Failure Report and B. Entry Success Report - every pre-entry feature\n")
    w("Sorted by separation in Development. Medians are for losers vs winners over the whole sample.\n")
    w("| Feature | Median losers | Median winners | AUC all | AUC DEV | AUC VAL | AUC OOS | Consistent DEV+VAL | OOS agrees |\n|---|---|---|---|---|---|---|---|---|")
    for _, r in FT.iterrows():
        w(f"| {r.title} | {f(r.med_loss, '{:.2f}')} | {f(r.med_win, '{:.2f}')} | {f(r.auc_all, '{:.3f}')} | {f(r.auc_DEV, '{:.3f}')} | "
          f"{f(r.auc_VAL, '{:.3f}')} | {f(r.auc_OOS, '{:.3f}')} | {'YES (' + r.direction + ')' if r.consistent else ''} | {'yes' if r.oos_agrees else ('no' if r.consistent else '')} |")
    w("")
    w("Categorical features (n / win rate / avg net R):\n")
    w("| Feature | Category | All | DEV | VAL | OOS |\n|---|---|---|---|---|---|")
    for _, r in CT.iterrows():
        w(f"| {r.title} | {r.category} | " + " | ".join(f"{int(r[f'n_{p}'])} / {f(r[f'wr_{p}'], '{:.0%}')} / {f(r[f'avgnet_{p}'], '{:+.3f}')}" for p in ("all",) + PERIODS) + " |")
    w("")
    w("Quartile detail for the strongest Development features:\n")
    for _, r in FT.head(8).iterrows():
        bucket_table(v1, qlabels(v1[r.feature].astype(float)), r.title, w)
    # ---- 2 failed breakouts
    w("## 2. Failed-breakout study - can the return inside the rectangle be seen before entry?\n")
    fb_n = int(v1.fb.sum())
    w(f"{fb_n} of {len(v1)} entries ({fb_n / len(v1):.0%}) closed back inside the rectangle within 3 candles (win rate {v1.win[v1.fb].mean():.1%} vs "
      f"{v1.win[~v1.fb].mean():.1%} for the rest). Below, AUC of each pre-entry feature for predicting that label (0.5 = no information).\n")
    FB = FT.copy()
    FB["abs_fb"] = (FB.auc_fb_DEV - 0.5).abs()
    w("| Feature | AUC for 'failed breakout' all | DEV | VAL | OOS |\n|---|---|---|---|---|")
    for _, r in FB.sort_values("abs_fb", ascending=False).head(15).iterrows():
        w(f"| {r.title} | {f(r.auc_fb_all, '{:.3f}')} | {f(r.auc_fb_DEV, '{:.3f}')} | {f(r.auc_fb_VAL, '{:.3f}')} | {f(r.auc_fb_OOS, '{:.3f}')} |")
    w("")
    if "error" not in model_res:
        w("Multivariate check (models fitted on Development only, all features together):\n")
        w("| Target | Model | AUC DEV (in-sample) | AUC VAL | AUC OOS |\n|---|---|---|---|---|")
        for target in ("fb", "win"):
            for name, res in model_res[target].items():
                w(f"| {'failed breakout' if target == 'fb' else 'win'} | {name} | {res['DEV']:.3f} | {res['VAL']:.3f} | {res['OOS']:.3f} |")
        w("")
        w("Largest standardized logistic coefficients for 'win' (Development fit): positive " +
          ", ".join(f"{k} {v:+.2f}" for k, v in model_res["lr_coefs_top"].items()) + "; negative " +
          ", ".join(f"{k} {v:+.2f}" for k, v in model_res["lr_coefs_bottom"].items()) + ".\n")
    else:
        w(f"Model check unavailable: {model_res['error']}\n")
    # ---- 3 confirmation candle
    w("## 3. Confirmation candle quality\n")
    for col in ("conf_body_pct", "conf_close_pos", "conf_wick_against_pct", "conf_range_atr", "conf_ext_zh", "conf_ext_atr"):
        bucket_table(v1, qlabels(v1[col].astype(float)), NAME[col], w)
    strong = (v1.conf_body_pct >= 0.6) & (v1.conf_close_pos >= 0.8)
    bucket_table(v1, pd.Series(np.where(strong, "strong (body >= 60%, close in top 20%)", "not strong"), index=v1.index), "Strong vs weak confirmation candle", w)
    # ---- 4 POC types
    w("## 4. POC interaction quality\n")
    w("Types (assigned in this precedence): E = price crossed the whole rectangle during the interaction; D = 3+ POC taps today; "
      "B = closed outside, came back inside, then broke; C = 3+ candles closed inside; A = tap and breakout within 2 candles of first contact; "
      "other = tapped 1-11 candles earlier without those patterns.\n")
    bucket_table(v1, v1.poc_type, "POC interaction type", w)
    bucket_table(v1, pd.cut(v1.pen_depth_zh, [-1e9, 0.5, 0.75, 1.0, 1e9], labels=["< 0.5 (shallow)", "0.5-0.75", "0.75-1.0", ">= 1.0 (through)"]).astype(str), "Penetration depth into the rectangle", w)
    bucket_table(v1, pd.cut(v1.ep_inside, [-1, 0, 2, 5, 1000], labels=["0", "1-2", "3-5", "6+"]).astype(str), "Candles closed inside the rectangle (interaction)", w)
    # ---- 5 location
    w("## 5. Location quality\n")
    bucket_table(v1, pd.cut(v1.zone_pos_range, [-0.01, 0.1, 0.35, 0.65, 0.9, 1.01], labels=["near prior-day Low", "lower", "middle", "upper", "near prior-day High"]).astype(str), "Rectangle position in the prior-day range", w)
    bucket_table(v1, v1.side + " / " + pd.cut(v1.zone_pos_range, [-0.01, 0.1, 0.35, 0.65, 0.9, 1.01], labels=["near Low", "lower", "middle", "upper", "near High"]).astype(str), "Side x position", w)
    bucket_table(v1, pd.Series(np.where(v1.opp_gap_R.isna(), "no rectangle in the way", np.where(v1.opp_gap_R > 3, "opposing rectangle beyond the target (> 3R)", np.where(v1.opp_gap_R > 1.5, "opposing rectangle 1.5-3R away", "opposing rectangle < 1.5R away"))), index=v1.index), "Nearest opposing rectangle", w)
    bucket_table(v1, pd.Series(np.where(v1.nearest_gap_zh < 1, "another rectangle within 1 height", "no rectangle within 1 height"), index=v1.index), "Very close to another rectangle", w)
    bucket_table(v1, pd.cut(v1.room_to_pdhl_R, [-1e9, 0, 1.5, 3, 6, 1e9], labels=["already beyond", "0-1.5R", "1.5-3R", "3-6R", "> 6R"]).astype(str), "Room to the prior-day High/Low in the trade direction", w)
    # ---- 6 congestion
    w("## 6. Trade congestion\n")
    bucket_table(v1, pd.cut(v1.taps, [0, 1, 2, 1000], labels=["1 tap", "2 taps", "3+ taps"]).astype(str), "POC taps today", w)
    bucket_table(v1, pd.cut(v1.failed_same, [-1, 0, 1, 1000], labels=["0", "1", "2+"]).astype(str), "Prior failed breakouts in the trade direction (today)", w)
    bucket_table(v1, pd.cut(v1.failed_opp, [-1, 0, 1, 1000], labels=["0", "1", "2+"]).astype(str), "Prior failed breakouts the other way (today)", w)
    bucket_table(v1, pd.cut(v1.poc_crosses_12, [-1, 1, 3, 1000], labels=["0-1", "2-3", "4+"]).astype(str), "POC crosses in the last 12 candles", w)
    bucket_table(v1, pd.cut(v1.alternations6, [-1, 2, 4, 6], labels=["0-2", "3-4", "5"]).astype(str), "Colour changes in the last 6 candles", w)
    bucket_table(v1, pd.cut(v1.touches_today, [0, 2, 5, 10, 1000], labels=["1-2", "3-5", "6-10", "11+"]).astype(str), "Rectangle touches today", w)
    clean = (v1.taps == 1) & (v1.failed_same == 0) & (v1.failed_opp == 0) & (v1.poc_crosses_12 <= 1) & (v1.ep_rej == 0)
    choppy = (v1.taps >= 3) | (v1.failed_same >= 1) | (v1.poc_crosses_12 >= 3)
    bucket_table(v1, pd.Series(np.where(clean, "clean first interaction", np.where(choppy, "choppy / repeated", "in between")), index=v1.index), "Clean vs choppy interaction", w)
    # ---- 7 score
    w("## 7. Entry quality score (fitted on Development only; buckets = Development terciles of the score)\n")
    for sc, title in (("score_logistic", "Logistic-regression score (all features)"), ("score_gradient", "Gradient-boosting score (all features)"), ("score_simple", f"Simple score = number of the {len(simple_terms)} consistent conditions met")):
        if sc not in v1.columns:
            continue
        if sc == "score_simple":
            labels = pd.cut(v1[sc], [-1, 1, 3, 100], labels=["Low (0-1)", "Medium (2-3)", "High (4+)"]).astype(str) if len(simple_terms) >= 4 else v1[sc].astype(str)
        else:
            q1, q2 = np.quantile(v1.loc[v1.period == "DEV", sc], [1 / 3, 2 / 3])
            labels = pd.Series(np.where(v1[sc] < q1, "Low", np.where(v1[sc] < q2, "Medium", "High")), index=v1.index)
        w(f"**{title}**\n")
        w("| Bucket | Period | Trades | Win rate | Gross R | Net R | Avg R | PF |\n|---|---|---|---|---|---|---|---|")
        for lab in (["Low", "Medium", "High"] if sc != "score_simple" else list(pd.unique(labels))):
            for per in ("all",) + PERIODS:
                m = (labels == lab) & ((v1.period == per) if per != "all" else True)
                mt = metrics(v1[m])
                w(f"| {lab} | {per} | {mt['n']} | {f(mt['wr'], '{:.1%}')} | {f(mt['gross'], '{:+.1f}')} | {f(mt['net'], '{:+.1f}')} | {f(mt['avg'], '{:+.3f}')} | {f(mt['pf'], '{:.2f}')} |")
        w("")
    if simple_terms:
        w("Simple-score conditions (direction and Development median): " + "; ".join(f"{t['title']} {'>=' if t['direction'] == 'higher = better' else '<='} {t['threshold']:.2f}" for t in simple_terms) + ".\n")
    else:
        w("No feature was consistent across Development and Validation, so no simple score could be formed.\n")
    # ---- C filters
    w("## C. Filter experiments (each filter alone, applied to the V1 trade list; thresholds = Development terciles, direction from Development)\n")
    if len(FR):
        w("| Filter | Trades removed | Losers removed | Winners removed | Win rate before -> after | Net R before -> after | DEV avg net R before -> after | VAL | OOS |\n|---|---|---|---|---|---|---|---|---|")
        for _, r in FR.iterrows():
            w(f"| {r['filter']} | {r.removed} | {r.losers_removed} | {r.winners_removed} | {r.wr_before:.1%} -> {r.wr_after:.1%} | {r.net_before:+.0f} -> {r.net_after:+.0f} | "
              f"{r.DEV_avgnet_before:+.3f} -> {r.DEV_avgnet_after:+.3f} | {r.VAL_avgnet_before:+.3f} -> {r.VAL_avgnet_after:+.3f} | {r.OOS_avgnet_before:+.3f} -> {r.OOS_avgnet_after:+.3f} |")
        w("")
    else:
        w("No consistent feature qualified, so there is no candidate filter.\n")
    # ---- D minimal rule + E/F exact
    w("## D. Minimal entry rule\n")
    if chosen:
        w("Chosen by the pre-registered rule (improves average net R in BOTH Development and Validation, keeps >= 60% of Development trades, "
          "one filter per feature, at most 3, ranked by the smaller improvement):\n")
        for c in chosen:
            w(f"- {c['filter']} (DEV {c['imp_dev']:+.3f}, VAL {c['imp_val']:+.3f}; OOS, not used for selection: {c['imp_oos']:+.3f})")
        w("")
    else:
        w("No filter improved both Development and Validation while keeping 60% of the trades. No minimal rule is proposed.\n")
    w("## E. V3 backtest (exact engine runs: the filter is applied at signal time, the rectangle is not consumed by a blocked setup)\n")
    w(HEAD_PP)
    for name, s in exact.items():
        w(per_period_row(name, s))
    w("")
    w("## F. Out-of-sample result\n")
    if chosen and "V3 = V1 + minimal entry rule" in exact:
        a, b = exact["V1"], exact["V3 = V1 + minimal entry rule"]
        w(f"V1 -> V3 average net R per trade: Development {a['DEV']['avg_net']:+.3f} -> {b['DEV']['avg_net']:+.3f}, Validation {a['VAL']['avg_net']:+.3f} -> {b['VAL']['avg_net']:+.3f}, "
          f"Out-of-sample {a['OOS']['avg_net']:+.3f} -> {b['OOS']['avg_net']:+.3f} (trades {a['OOS']['n']} -> {b['OOS']['n']}).")
        w("")
    open("V3_ENTRY_QUALITY_REPORT.md", "w", encoding="utf-8").write("\n".join(L))
    json.dump(dict(cut_dates=cut_dates, base=base, models=model_res, simple_terms=simple_terms, chosen=chosen, exact=exact,
                   consistent_features=FT[FT.consistent][["feature", "auc_DEV", "auc_VAL", "auc_OOS", "direction"]].to_dict("records")),
              open(f"{OUT}/v3_lab.json", "w"), indent=1, default=str)
    print("report written; consistent features:", FT.consistent.sum(), "; chosen:", [c["filter"] for c in chosen])


if __name__ == "__main__":
    main()
