"""Edge discovery, phases 5-9: A/B/C/D outcomes with the strategy's real stop, what separates them at entry
(univariate and multivariate), market structure, trend vs reversal, entry mechanisms, MFE/MAE timing, and the
acceptance gates for any candidate, against the three controls (raw TWK, Loss Prevention v1, candidate).
"""
import json, math, os, time
os.environ["LAB_SKIP_RUNS"] = "1"
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
import twk_engine as E
from filter_lab import m1, sig as sig0, ser, spread, PERIODS, END, T_A, T_B, short_metrics

T0 = time.time()
os.makedirs("results/edge", exist_ok=True)
S = pd.read_csv("results/signal/signals_M3_full.csv", parse_dates=["time"])          # phase-2 per-signal dataset (features + 1-ATR outcomes)
S = S.reset_index(drop=True)
n = len(S); side = S["side"].to_numpy(); atr = S["atr"].to_numpy(); risk = S["risk"].to_numpy(); b = S["bar"].to_numpy()
o, h, l, c = ser["o"], ser["h"], ser["l"], ser["c"]
m1_t = (m1["time"].astype("int64") // 10**9).to_numpy(); m1_o = m1["open"].to_numpy(float); m1_h = m1["high"].to_numpy(float); m1_l = m1["low"].to_numpy(float); m1_c = m1["close"].to_numpy(float)
spr = spread * 0.01
k0 = np.searchsorted(m1_t, S["close_time"].to_numpy(), side="left")
H_M1 = 600
LEV = [0.5, 1.0, 2.0]

# ------------------------------------------------------------------ Phase 6: structure features
# previous day's and current day's high/low (server days) on M3 bars
m3t = pd.to_datetime(ser["time"]); day = m3t.floor("D")
dfm = pd.DataFrame(dict(day=day, h=h, l=l))
dh = dfm.groupby("day").h.max(); dl = dfm.groupby("day").l.min()
prev_day = pd.Series(day.unique()).shift(1); pday_map = dict(zip(day.unique(), prev_day))
pdh = pd.Series(day).map(pday_map).map(dh).to_numpy(); pdl = pd.Series(day).map(pday_map).map(dl).to_numpy()
cum_h = dfm.groupby("day").h.cummax().to_numpy(); cum_l = dfm.groupby("day").l.cummin().to_numpy()
S["prev_day_high_dist"] = (pdh[b] - c[b]) / atr * side                       # + = the prior-day high is ahead in the trade direction (buys)
S["prev_day_low_dist"] = (c[b] - pdl[b]) / atr * side
S["day_high_dist"] = (cum_h[np.maximum(b - 1, 0)] - c[b]) / atr * side
S["day_low_dist"] = (c[b] - cum_l[np.maximum(b - 1, 0)]) / atr * side
S["ahead_level_dist"] = np.where(side == 1, np.minimum(np.abs(pdh[b] - c[b]), np.abs(cum_h[np.maximum(b - 1, 0)] - c[b])), np.minimum(np.abs(c[b] - pdl[b]), np.abs(c[b] - cum_l[np.maximum(b - 1, 0)]))) / atr
S["behind_level_dist"] = np.where(side == 1, np.minimum(np.abs(c[b] - pdl[b]), np.abs(c[b] - cum_l[np.maximum(b - 1, 0)])), np.minimum(np.abs(pdh[b] - c[b]), np.abs(cum_h[np.maximum(b - 1, 0)] - c[b]))) / atr
S["broke_prev_day_level"] = np.where(side == 1, c[b] > pdh[b], c[b] < pdl[b])
# HH/HL vs LH/LL from the last two confirmed pivot highs and lows (M3)
ph_val = np.where(ser["phBar"] >= 0, h[np.maximum(ser["phBar"], 0)], np.nan); pl_val = np.where(ser["plBar"] >= 0, l[np.maximum(ser["plBar"], 0)], np.nan)
def prev_distinct(vals, bars):
    """value of the pivot before the current one (the previous distinct pivot bar)."""
    out = np.full(len(vals), np.nan); last_bar = -1; last_val = np.nan; prev_val = np.nan
    for i in range(len(vals)):
        if bars[i] != last_bar:
            prev_val, last_val, last_bar = last_val, vals[i], bars[i]
        out[i] = prev_val
    return out
ph_prev = prev_distinct(ph_val, ser["phBar"]); pl_prev = prev_distinct(pl_val, ser["plBar"])
hh = ph_val[b] > ph_prev[b]; hl = pl_val[b] > pl_prev[b]; lh = ph_val[b] < ph_prev[b]; ll = pl_val[b] < pl_prev[b]
S["m3_structure"] = np.select([hh & hl, lh & ll], ["HH/HL", "LH/LL"], "mixed")
S["m3_structure_aligned"] = np.where(side == 1, hh & hl, lh & ll)
# M15 structure and the broken-level-retest hypothesis
m15 = E.resample(m1, 15); s15 = E.compute_series(m15, E.CoreParams())
t15 = m15["time"].astype("int64").to_numpy() // 10**9 + 900
k15 = np.searchsorted(t15, S["close_time"].to_numpy(), side="right") - 1; k15c = np.maximum(k15, 0)
h15, l15, c15 = s15["h"], s15["l"], s15["c"]
ph15 = np.where(s15["phBar"] >= 0, h15[np.maximum(s15["phBar"], 0)], np.nan); pl15 = np.where(s15["plBar"] >= 0, l15[np.maximum(s15["plBar"], 0)], np.nan)
ph15p = prev_distinct(ph15, s15["phBar"]); pl15p = prev_distinct(pl15, s15["plBar"])
S["m15_structure_aligned"] = np.where(side == 1, (ph15[k15c] > ph15p[k15c]) & (pl15[k15c] > pl15p[k15c]), (ph15[k15c] < ph15p[k15c]) & (pl15[k15c] < pl15p[k15c]))
S["m15_structure_against"] = np.where(side == 1, (ph15[k15c] < ph15p[k15c]) & (pl15[k15c] < pl15p[k15c]), (ph15[k15c] > ph15p[k15c]) & (pl15[k15c] > pl15p[k15c]))
# level broken in the last 8 M15 bars: for buys the previous M15 pivot high was exceeded by an M15 close; retest = price now within 1 ATR above it
atr15 = s15["atr"]
def broke_recent(kc, lookback=8):
    out = np.zeros(len(kc), bool); lvl = np.full(len(kc), np.nan)
    for i, k in enumerate(kc):
        if k < lookback + 5: continue
        if side[i] == 1:
            level = ph15[k - lookback]
            if not np.isnan(level) and (c15[k - lookback + 1:k + 1] > level).any() and c15[k] > level:
                out[i] = True; lvl[i] = level
        else:
            level = pl15[k - lookback]
            if not np.isnan(level) and (c15[k - lookback + 1:k + 1] < level).any() and c15[k] < level:
                out[i] = True; lvl[i] = level
    return out, lvl
brk, lvl = broke_recent(k15c)
S["m15_level_broken"] = brk
S["retest_of_broken_level"] = brk & (np.abs(c[b] - lvl) <= 1.0 * atr)
# reversal context: large prior move against the signal direction on M15 (>= 3 ATR15 over the last 20 M15 bars)
mv = np.array([(c15[k] - c15[max(k - 20, 0)]) / atr15[k] if not np.isnan(atr15[k]) and atr15[k] > 0 else np.nan for k in k15c])
S["prior_move_against_atr15"] = -mv * side                                   # + = the last 20 M15 bars moved against the new signal direction
S["reclaim"] = np.where(side == 1, c[b] > pl15[k15c], c[b] < ph15[k15c])      # price back beyond the last M15 pivot in the signal direction
S["nearest_pivot_dist"] = np.minimum(np.abs(c[b] - ph_val[b]), np.abs(c[b] - pl_val[b])) / atr
print(f"structure features done ({time.time()-T0:.0f}s)", flush=True)

# ------------------------------------------------------------------ Phase 5: outcomes with the real stop (R = pivot/purple distance), net of spread
def scan(k_entry, fill, use_spread, sd, unit, levels=LEV, H=H_M1):
    N = len(k_entry); Lv = np.array(levels)
    t_fav = np.full((N, len(levels)), H, dtype=np.int32); t_adv = np.full((N, len(levels)), H, dtype=np.int32); endp = np.full(N, np.nan); valid = np.zeros(N, bool)
    for i in range(N):
        k = int(k_entry[i])
        if k < 0 or k + 2 >= len(m1_t) or math.isnan(unit[i]) or unit[i] <= 0 or math.isnan(fill[i]): continue
        e = min(k + H, len(m1_t)); hh_ = m1_h[k:e]; ll_ = m1_l[k:e]; s_ = spr[k:e] if use_spread else 0.0
        fav = (hh_ - fill[i]) if sd[i] == 1 else (fill[i] - (ll_ + s_)); adv = (fill[i] - ll_) if sd[i] == 1 else ((hh_ + s_) - fill[i])
        cf = np.maximum.accumulate(fav); ca = np.maximum.accumulate(adv); lv = Lv * unit[i]
        tf = np.searchsorted(cf, lv, side="left"); ta = np.searchsorted(ca, lv, side="left"); m = len(cf)
        t_fav[i] = np.where(tf < m, tf, H); t_adv[i] = np.where(ta < m, ta, H)
        last = e - 1; endp[i] = (m1_c[last] - fill[i]) if sd[i] == 1 else (fill[i] - (m1_c[last] + (spr[last] if use_spread else 0.0))); valid[i] = True
    return dict(t_fav=t_fav, t_adv=t_adv, endp=endp, valid=valid)
def fills(k_entry, sd, use_spread):
    f = m1_o[np.clip(k_entry, 0, len(m1_o) - 1)].copy()
    return np.where(sd == 1, f + spr[np.clip(k_entry, 0, len(spr) - 1)], f) if use_spread else f
resR = scan(k0, fills(k0, side, True), True, side, risk)
resR_g = scan(k0, fills(k0, side, False), False, side, risk)
i05, i1, i2 = 0, 1, 2
tf05, tf1, tf2, ta1 = resR["t_fav"][:, i05], resR["t_fav"][:, i1], resR["t_fav"][:, i2], resR["t_adv"][:, i1]
bucket = np.where(~resR["valid"], "invalid", np.where(tf2 < ta1, "A", np.where(tf1 < ta1, "B", np.where(tf05 < ta1, "C", "D"))))
S["bucket"] = bucket
# net outcome in R for the strategy's own shape (1R stop, 2R target) and for 1R/1R
def outcome(res, iS, iT, unit):
    tf, ta = res["t_fav"][:, iT], res["t_adv"][:, iS]
    hit = (tf < ta) & (tf < H_M1); stopped = (ta <= tf) & (ta < H_M1)
    r = np.where(hit, LEV[iT] / LEV[iS], np.where(stopped, -1.0, res["endp"] / (LEV[iS] * unit)))
    return np.where(res["valid"], r, np.nan), hit
S["r12n"], S["hit12"] = outcome(resR, i1, i2, risk); S["r11n"], S["hit11n"] = outcome(resR, i1, i1, risk); S["r12g"], _ = outcome(resR_g, i1, i2, risk)
S["t_05R"] = np.where(tf05 < H_M1, tf05, np.nan); S["t_1R"] = np.where(tf1 < H_M1, tf1, np.nan); S["t_2R"] = np.where(tf2 < H_M1, tf2, np.nan); S["t_m1R"] = np.where(ta1 < H_M1, ta1, np.nan)
ta05 = resR["t_adv"][:, i05]
S["half_first"] = np.where(resR["valid"], np.where(tf05 < ta05, "+0.5R first", np.where(ta05 < tf05, "-0.5R first", "neither")), "invalid")
S["risk_atr"] = risk / atr
OUT = dict(n=int(n), generated=str(pd.Timestamp.now())[:16])
V = S[S.bucket != "invalid"].copy()
OUT["buckets"] = {per: {k: int(v) for k, v in V[V.period == per].bucket.value_counts().items()} for per in ("DEV", "VAL", "OOS")}
OUT["buckets_all"] = {k: int(v) for k, v in V.bucket.value_counts().items()}
OUT["bucket_r"] = {k: dict(n=int(len(g)), r12_net=round(float(g.r12n.mean()), 3), r12_gross=round(float(g.r12g.mean()), 3), median_stop_atr=round(float(g.risk_atr.median()), 2), median_min_to_1R=round(float(g.t_1R.median()), 0) if g.t_1R.notna().any() else None, median_min_to_m1R=round(float(g.t_m1R.median()), 0) if g.t_m1R.notna().any() else None) for k, g in V.groupby("bucket")}
OUT["overall"] = {per: dict(n=int(len(g)), r12_net=round(float(g.r12n.mean()), 3), r12_gross=round(float(g.r12g.mean()), 3), hit_2R=round(float(g.hit12.mean()), 3), r11_net=round(float(g.r11n.mean()), 3)) for per, g in V.groupby("period")}
print("buckets:", OUT["buckets_all"], flush=True)

# ------------------------------------------------------------------ Phase 9: timing
def qd(s): s = s.dropna(); return {str(q): round(float(s.quantile(q)), 0) for q in (0.25, 0.5, 0.75)} if len(s) else {}
OUT["timing"] = {k: dict(n=int(len(g)), min_to_05R=qd(g.t_05R), min_to_1R=qd(g.t_1R), min_to_2R=qd(g.t_2R), min_to_m1R=qd(g.t_m1R)) for k, g in V.groupby("bucket")}
win = V[V.bucket.isin(["A", "B"])]; lose = V[V.bucket == "D"]
OUT["half_first"] = dict(winners_half_first=round(float((win.half_first == "+0.5R first").mean()), 3), losers_half_first=round(float((lose.half_first == "+0.5R first").mean()), 3),
                         all_half_first=round(float((V.half_first == "+0.5R first").mean()), 3), all_neg_half_first=round(float((V.half_first == "-0.5R first").mean()), 3),
                         by_period={per: dict(plus=round(float((g.half_first == "+0.5R first").mean()), 3), minus=round(float((g.half_first == "-0.5R first").mean()), 3)) for per, g in V.groupby("period")})

# ------------------------------------------------------------------ Phase 5/6: what separates A/B from D
NEWF = {"prev_day_high_dist": "distance to the previous day's high, in ATR, signed toward the trade", "prev_day_low_dist": "distance from the previous day's low", "day_high_dist": "distance to today's high so far", "day_low_dist": "distance from today's low so far",
        "ahead_level_dist": "nearest day-level ahead / ATR", "behind_level_dist": "nearest day-level behind / ATR", "broke_prev_day_level": "closed beyond the previous day's high/low", "m3_structure": "M3 pivots: HH/HL, LH/LL or mixed",
        "m3_structure_aligned": "M3 structure agrees with the signal", "m15_structure_aligned": "M15 structure agrees", "m15_structure_against": "M15 structure against", "m15_level_broken": "M15 pivot level broken in the last 8 M15 bars",
        "retest_of_broken_level": "broken M15 level AND price within 1 ATR of it (retest)", "prior_move_against_atr15": "M15 move against the signal over 20 bars, in ATR15", "reclaim": "price beyond the last M15 pivot in the signal direction", "nearest_pivot_dist": "distance to the nearest M3 pivot / ATR", "risk_atr": "the strategy's stop / ATR"}
OLDF = ["atr_ratio", "atr_slope", "range_ratio", "adx", "adx_slope", "ema_sep", "ema50_slope", "px_vs_ema50", "dist_ema", "htf15_aligned", "htf60_aligned", "ema15_aligned", "opp_ago", "flips_10", "flips_20", "dist_prev_sig", "minutes_since_prev", "purple_dist", "close_loc", "body_ratio", "opp_candles5", "room_ahead", "room_behind", "swing_dist", "vol_ratio", "box_m1", "box_m3", "ea_pass", "cost_over_reward", "session", "dow", "prev_outcome", "prev_same_dir", "bbw_atr", "prev_range_ratio"]
FEATS = OLDF + list(NEWF)
sep_rows = []; bucket_rows = []
for f in FEATS:
    v = V[f]
    if v.dtype == object or v.dtype == bool or f in ("dow", "session", "m3_structure", "prev_outcome"):
        bk = v.astype(str)
    else:
        vv = v.astype(float); ok = ~vv.isna()
        try: bins = pd.qcut(vv[ok], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
        except ValueError: continue
        bk = pd.Series("nan", index=V.index); bk[ok] = bins.astype(str)
    d = pd.DataFrame(dict(b=bk, good=V.bucket.isin(["A", "B"]), bad=V.bucket == "D", r=V.r12n, per=V.period, yr=V.year)); d = d[d.b != "nan"]
    g = d.groupby("b")
    t = g.agg(n=("r", "size"), good=("good", "mean"), bad=("bad", "mean"), exp=("r", "mean")).reset_index()
    for per in ("DEV", "VAL", "OOS"):
        t[f"exp_{per}"] = d[d.per == per].groupby("b").r.mean().reindex(t.b).to_numpy(); t[f"n_{per}"] = d[d.per == per].groupby("b").r.size().reindex(t.b).fillna(0).astype(int).to_numpy()
    for _, r in t.iterrows():
        bucket_rows.append(dict(feature=f, bucket=r.b, n=int(r.n), share_AB=round(float(r.good), 3), share_D=round(float(r.bad), 3), exp12_net=round(float(r.exp), 3), **{f"exp_{per}": (round(float(r[f'exp_{per}']), 3) if not np.isnan(r[f'exp_{per}']) else None) for per in ("DEV", "VAL", "OOS")}, **{f"n_{per}": int(r[f"n_{per}"]) for per in ("DEV", "VAL", "OOS")}))
    if len(t) >= 2:
        best = t.loc[t.exp.idxmax()]; worst = t.loc[t.exp.idxmin()]
        holds = sum(1 for per in ("DEV", "VAL", "OOS") if not np.isnan(best[f"exp_{per}"]) and not np.isnan(worst[f"exp_{per}"]) and best[f"exp_{per}"] > worst[f"exp_{per}"])
        pos = sum(1 for per in ("DEV", "VAL", "OOS") if not np.isnan(best[f"exp_{per}"]) and best[f"exp_{per}"] > 0)
        sep_rows.append(dict(feature=f, new=f in NEWF, description=NEWF.get(f, ""), best=best.b, best_n=int(best.n), best_AB=round(float(best.good), 3), best_D=round(float(best.bad), 3), best_exp=round(float(best.exp), 3), worst=worst.b, worst_AB=round(float(worst.good), 3), worst_D=round(float(worst.bad), 3), worst_exp=round(float(worst.exp), 3),
                             AB_separation=round(float(best.good - worst.good), 3), order_holds=holds, best_positive=pos, best_DEV=round(float(best.exp_DEV), 3) if not np.isnan(best.exp_DEV) else None, best_VAL=round(float(best.exp_VAL), 3) if not np.isnan(best.exp_VAL) else None, best_OOS=round(float(best.exp_OOS), 3) if not np.isnan(best.exp_OOS) else None))
SEP = pd.DataFrame(sep_rows).sort_values(["order_holds", "AB_separation"], ascending=[False, False]); SEP.to_csv("results/edge/separation.csv", index=False); pd.DataFrame(bucket_rows).to_csv("results/edge/buckets.csv", index=False)
OUT["separation"] = SEP.to_dict("records"); OUT["feature_buckets"] = bucket_rows
print("separation done", flush=True)

# ------------------------------------------------------------------ Phase 5 multivariate: can any combination predict A/B vs D?
ML = {}
try:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    num = [f for f in FEATS if f not in ("session", "dow", "m3_structure", "prev_outcome")]
    X = V[num].astype(float).copy()
    for cat in ("session", "m3_structure", "prev_outcome"):
        X = pd.concat([X, pd.get_dummies(V[cat].astype(str), prefix=cat).astype(float)], axis=1)
    X["dow"] = V["dow"].astype(float)
    y_cls = V.bucket.isin(["A", "B"]).astype(int); mask_cls = V.bucket.isin(["A", "B", "D"])
    tr_ = (V.period == "DEV").to_numpy(); va_ = (V.period == "VAL").to_numpy(); te_ = (V.period == "OOS").to_numpy()
    clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0, early_stopping=False, random_state=7)
    clf.fit(X[tr_ & mask_cls], y_cls[tr_ & mask_cls])
    for nm, mk in (("DEV", tr_), ("VAL", va_), ("OOS", te_)):
        mm = mk & mask_cls.to_numpy(); p = clf.predict_proba(X[mm])[:, 1]
        ML[f"auc_{nm}"] = round(float(roc_auc_score(y_cls[mm], p)), 3)
    # decile expectancy of the predicted probability, all signals of the period, net R (1R/2R)
    dec = {}
    for nm, mk in (("DEV", tr_), ("VAL", va_), ("OOS", te_)):
        p = clf.predict_proba(X[mk])[:, 1]; r = V.r12n.to_numpy()[mk]; q = pd.qcut(p, 10, labels=False, duplicates="drop")
        dec[nm] = [dict(decile=int(d_ + 1), n=int((q == d_).sum()), exp12_net=round(float(np.nanmean(r[q == d_])), 3)) for d_ in sorted(set(q))]
    ML["deciles"] = dec
    # top-decile rule fixed on DEV probabilities, applied unchanged later
    thr = float(np.quantile(clf.predict_proba(X[tr_])[:, 1], 0.9))
    for nm, mk in (("DEV", tr_), ("VAL", va_), ("OOS", te_)):
        p = clf.predict_proba(X[mk])[:, 1]; sel = p >= thr; r = V.r12n.to_numpy()[mk]
        ML[f"top10_{nm}"] = dict(n=int(sel.sum()), exp12_net=round(float(np.nanmean(r[sel])), 3) if sel.any() else None, exp12_gross=round(float(np.nanmean(V.r12g.to_numpy()[mk][sel])), 3) if sel.any() else None)
    # permutation importance on VAL (top 12)
    base_auc = ML["auc_VAL"]; imps = []
    Xv = X[va_ & mask_cls.to_numpy()]; yv = y_cls[va_ & mask_cls.to_numpy()]; rng = np.random.default_rng(3)
    for col in X.columns:
        Xp = Xv.copy(); Xp[col] = rng.permutation(Xp[col].to_numpy()); imps.append((col, round(base_auc - float(roc_auc_score(yv, clf.predict_proba(Xp)[:, 1])), 4)))
    ML["importance_VAL"] = sorted(imps, key=lambda x: -x[1])[:12]
    # a linear model as a sanity check
    Xz = ((X - X[tr_].mean()) / (X[tr_].std() + 1e-9)).fillna(0.0)      # missing = at the training mean
    lr = LogisticRegression(max_iter=2000, C=0.1).fit(Xz[tr_ & mask_cls], y_cls[tr_ & mask_cls])
    ML["logit_auc"] = {nm: round(float(roc_auc_score(y_cls[mk & mask_cls.to_numpy()], lr.predict_proba(Xz[mk & mask_cls.to_numpy()])[:, 1])), 3) for nm, mk in (("DEV", tr_), ("VAL", va_), ("OOS", te_))}
    S["ml_p"] = np.nan; S.loc[V.index, "ml_p"] = clf.predict_proba(X)[:, 1]; ML["thr_top10_DEV"] = round(thr, 4)
    print("ML:", {k: v for k, v in ML.items() if k not in ("deciles", "importance_VAL")}, flush=True)
except Exception as ex:
    ML["error"] = str(ex); print("ML skipped:", ex, flush=True)
OUT["ml"] = ML

# ------------------------------------------------------------------ Phase 7: trend continuation vs reversal (structural definitions)
cont = S.htf15_aligned.astype(bool) & S.htf60_aligned.astype(bool) & S.m15_structure_aligned.astype(bool) & S.reclaim.astype(bool)
rev = (~S.htf15_aligned.astype(bool)) & (~S.htf60_aligned.astype(bool)) & (S.prior_move_against_atr15 >= 3) & S.reclaim.astype(bool)
S["model"] = np.select([cont, rev], ["A trend continuation", "B reversal"], "neither")
def split(col, frame=None):
    d = (frame if frame is not None else S); d = d[d.bucket != "invalid"]
    rows = []
    for k, g in d.groupby(col):
        row = dict(group=str(k), n=int(len(g)), win_2R=round(float(g.hit12.mean()), 3), share_AB=round(float(g.bucket.isin(["A", "B"]).mean()), 3), share_D=round(float((g.bucket == "D").mean()), 3), avg_r_net=round(float(g.r12n.mean()), 3), avg_r_gross=round(float(g.r12g.mean()), 3),
                   pf=round(float(g.r12n[g.r12n > 0].sum() / max(1e-9, -g.r12n[g.r12n < 0].sum())), 2), median_min_to_1R=round(float(g.t_1R.median()), 0) if g.t_1R.notna().any() else None, median_min_to_m1R=round(float(g.t_m1R.median()), 0) if g.t_m1R.notna().any() else None)
        for per in ("DEV", "VAL", "OOS"):
            gg = g[g.period == per]; row[f"n_{per}"] = int(len(gg)); row[f"exp_{per}"] = round(float(gg.r12n.mean()), 3) if len(gg) else None; row[f"pf_{per}"] = round(float(gg.r12n[gg.r12n > 0].sum() / max(1e-9, -gg.r12n[gg.r12n < 0].sum())), 2) if len(gg) else None
        row["years_positive"] = int((g.groupby("year").r12n.mean() > 0).sum()); rows.append(row)
    return rows
OUT["trend_vs_reversal"] = split("model")
OUT["structure_m3"] = split("m3_structure"); OUT["retest"] = split("retest_of_broken_level"); OUT["broke_prev_day"] = split("broke_prev_day_level"); OUT["m15_level_broken"] = split("m15_level_broken")
S["hyp_break_retest"] = S.m15_level_broken.astype(bool) & S.retest_of_broken_level.astype(bool) & S.htf15_aligned.astype(bool)
OUT["hyp_break_retest"] = split("hyp_break_retest")
print("phase 7 done", flush=True)

# ------------------------------------------------------------------ Phase 8: entry mechanisms with the real stop (levels from the entry, R = original stop distance)
def entry_stats(name, k_entry, fill, taken):
    res = scan(k_entry, fill, True, side, risk)
    r12, h12 = outcome(res, i1, i2, risk); r11, _ = outcome(res, i1, i1, risk)
    row = dict(entry=name, taken=round(float(taken.mean()), 3))
    for nm, mk in (("ALL", np.ones(n, bool)), ("DEV", (S.period == "DEV").to_numpy()), ("VAL", (S.period == "VAL").to_numpy()), ("OOS", (S.period == "OOS").to_numpy())):
        m = taken & mk & res["valid"]; rr = r12[m]; rr = rr[~np.isnan(rr)]
        row[f"n_{nm}"] = int(len(rr)); row[f"win2R_{nm}"] = round(float(np.mean(h12[m])), 3) if m.any() else None; row[f"exp12_{nm}"] = round(float(rr.mean()), 3) if len(rr) else None
        row[f"pf_{nm}"] = round(float(rr[rr > 0].sum() / max(1e-9, -rr[rr < 0].sum())), 2) if len(rr) else None; row[f"exp11_{nm}"] = round(float(np.nanmean(r11[m])), 3) if m.any() else None
    return row
TIM = [entry_stats("1 immediate (next M1 open)", k0, fills(k0, side, True), np.ones(n, bool))]
nb = np.minimum(b + 1, len(c) - 1); mom = np.where(side == 1, c[nb] > o[nb], c[nb] < o[nb]); k4 = k0 + 3
TIM.append(entry_stats("4 momentum continuation (next M3 candle closes in the direction)", k4, fills(k4, side, True), mom))
kB = np.full(n, -1); fB = np.full(n, np.nan); kR = np.full(n, -1); fR = np.full(n, np.nan); kP = np.full(n, -1); fP = np.full(n, np.nan)
pur = S["purple"].to_numpy()
for i in range(n):
    k = int(k0[i]); a = atr[i]
    if k + 31 >= len(m1_t) or math.isnan(a): continue
    hh_ = m1_h[k:k + 30]; ll_ = m1_l[k:k + 30]; cc_ = m1_c[k:k + 30]
    if side[i] == 1:
        bo = h[b[i]]; j = np.argmax(hh_ > bo) if (hh_ > bo).any() else -1
        if j >= 0: kB[i] = k + j; fB[i] = bo + spr[k + j]
        # retest: bid low within 0.25 ATR of the purple line, then an M1 close back above the signal close (rejection)
        near = ll_ <= pur[i] + 0.25 * a
        if near.any():
            j0 = int(np.argmax(near)); rec = np.where(cc_[j0:] > c[b[i]])[0]
            if len(rec): kR[i] = k + j0 + int(rec[0]) + 1; fR[i] = m1_o[kR[i]] + spr[kR[i]] if kR[i] < len(m1_o) else np.nan
        # pullback + reclaim: an M1 close below the signal close, then an M1 close back above it
        below = np.where(cc_ < c[b[i]])[0]
        if len(below):
            j0 = int(below[0]); rec = np.where(cc_[j0:] > c[b[i]])[0]
            if len(rec): kP[i] = k + j0 + int(rec[0]) + 1; fP[i] = m1_o[kP[i]] + spr[kP[i]] if kP[i] < len(m1_o) else np.nan
    else:
        bo = l[b[i]]; j = np.argmax(ll_ < bo) if (ll_ < bo).any() else -1
        if j >= 0: kB[i] = k + j; fB[i] = bo
        near = hh_ >= pur[i] - 0.25 * a
        if near.any():
            j0 = int(np.argmax(near)); rec = np.where(cc_[j0:] < c[b[i]])[0]
            if len(rec): kR[i] = k + j0 + int(rec[0]) + 1; fR[i] = m1_o[kR[i]] if kR[i] < len(m1_o) else np.nan
        above = np.where(cc_ > c[b[i]])[0]
        if len(above):
            j0 = int(above[0]); rec = np.where(cc_[j0:] < c[b[i]])[0]
            if len(rec): kP[i] = k + j0 + int(rec[0]) + 1; fP[i] = m1_o[kP[i]] if kP[i] < len(m1_o) else np.nan
TIM.append(entry_stats("2 breakout of the flip candle (within 30 min)", kB, fB, kB >= 0))
TIM.append(entry_stats("3 retest of the purple line + rejection close (within 30 min)", kR, fR, kR >= 0))
TIM.append(entry_stats("5 pullback below the flip close + reclaim (within 30 min)", kP, fP, kP >= 0))
OUT["entries"] = TIM
print("phase 8 done", flush=True)

# ------------------------------------------------------------------ Acceptance gates for candidates, with the real engine (baseline management) against the controls
CANDS = {
    "hyp_break_retest": S.hyp_break_retest.astype(bool).to_numpy(),
    "trend_continuation": (S.model == "A trend continuation").to_numpy(),
    "reversal": (S.model == "B reversal").to_numpy(),
    "m3+m15 structure aligned": (S.m3_structure_aligned.astype(bool) & S.m15_structure_aligned.astype(bool)).to_numpy(),
    "broke_prev_day_level": S.broke_prev_day_level.astype(bool).to_numpy(),
}
if "ml_p" in S and S.ml_p.notna().any():
    CANDS["ML top decile (fixed on DEV)"] = (S.ml_p >= ML.get("thr_top10_DEV", 1.0)).to_numpy()
# add the best-bucket rule of any feature whose best bucket is positive in DEV and VAL
for r in sep_rows:
    if r["best_DEV"] is not None and r["best_VAL"] is not None and r["best_DEV"] > 0 and r["best_VAL"] > 0 and r["best_n"] >= 300:
        f = r["feature"]; v = V[f]
        if f in ("dow", "session", "m3_structure", "prev_outcome") or v.dtype == object or v.dtype == bool:
            mk = (S[f].astype(str) == r["best"]).to_numpy()
        else:
            vv = S[f].astype(float); ok = ~vv.isna(); bins = pd.qcut(vv[ok], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop").astype(str); mk = pd.Series(False, index=S.index); mk[ok] = (bins == r["best"]).to_numpy(); mk = mk.to_numpy()
        CANDS[f"{f} = {r['best']}"] = mk
BASEKW = dict(min_volume_ratio=1.2, purple_activation_pts=360, protection_activation_pts=900, lock_pts=180, min_improve_pts=9)
LPV1 = dict(BASEKW, max_spread_atr=0.5, max_cost_to_reward=0.10, daily_loss_pct=2.0, consec_reduce_at=2, consec_pause_at=3, consec_stop_day_at=4, min_signal_distance_atr=2.0, entry_confirm_bars=2, max_attempts_per_dir=2, reset_atr=1.0, large_candle_lock=True, lock_activation_r=1.0, lock_level_r=0.25, one_to_one_gap_r=0.75, lock2_activation_r=1.5, lock2_level_r=0.75)
sigE = sig0.reset_index(drop=True).copy()
assert len(sigE) == len(S) and (sigE["bar"].to_numpy() == S["bar"].to_numpy()).all()
rr3 = np.stack([(h[np.maximum(b - i, 0)] - l[np.maximum(b - i, 0)]) / atr for i in range(3)], axis=1).max(axis=1); sigE["large_candle_lock"] = rr3 > 2.0; sigE["chop_static"] = 0
def engine(mask, kw, spread_mult=1.0, slip=0.0):
    tr = E.simulate(m1, sigE[mask] if mask is not None else sigE, ser, 3, E.MomentumEAParams(name="c", slippage_pts=slip, **kw), spread * spread_mult, T_A, T_B)
    out = {}
    for per, (a_, b_) in PERIODS.items():
        m = short_metrics(tr[(tr.entry_time >= a_) & (tr.entry_time < b_)]) if len(tr) else short_metrics(tr); out[per] = dict(n=m["n"], net=round(m["net"], 0), pf=round(m["pf"], 2), exp=round(m["exp"], 2), dd=round(m["dd"], 0))
    m = short_metrics(tr); out["ALL"] = dict(n=m["n"], net=round(m["net"], 0), pf=round(m["pf"], 2), exp=round(m["exp"], 2), dd=round(m["dd"], 0))
    return out
ACC = []
controls = {"CONTROL raw TWK (baseline)": (None, BASEKW), "CONTROL Loss Prevention v1": (None, LPV1)}
for name, (mk, kw) in controls.items():
    ACC.append(dict(candidate=name, kind="control", signals=int(n if mk is None else mk.sum()), **{f"{per}_{k}": v for per, d in engine(mk, kw).items() for k, v in d.items()}))
for name, mk in CANDS.items():
    if mk.sum() < 200: continue
    row = dict(candidate=name, kind="candidate", signals=int(mk.sum()))
    res = engine(mk, BASEKW); row.update({f"{per}_{k}": v for per, d in res.items() for k, v in d.items()})
    res2 = engine(mk, LPV1); row.update({f"LPV1_{per}_pf": d["pf"] for per, d in res2.items()}); row.update({f"LPV1_{per}_net": d["net"] for per, d in res2.items()})
    row["gate_pf_all_periods"] = all(res[p]["pf"] > 1 for p in ("DEV", "VAL", "OOS"))
    if row["gate_pf_all_periods"]:
        row["spread_x1.25_pf_OOS"] = engine(mk, BASEKW, 1.25)["OOS"]["pf"]; row["spread_x1.5_pf_OOS"] = engine(mk, BASEKW, 1.5)["OOS"]["pf"]; row["slip2_pf_OOS"] = engine(mk, BASEKW, 1.0, 2.0)["OOS"]["pf"]
    ACC.append(row)
    print(f"candidate {name:40s} signals={mk.sum():6d} PF DEV/VAL/OOS = {res['DEV']['pf']}/{res['VAL']['pf']}/{res['OOS']['pf']}  net {res['ALL']['net']}", flush=True)
OUT["acceptance"] = ACC; OUT["candidates_tested"] = list(CANDS)
S.to_csv("results/edge/signals_M3_edge.csv", index=False)
json.dump(OUT, open("results/edge/edge_lab.json", "w"), indent=1, default=lambda x: float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
print(f"edge lab done ({time.time()-T0:.0f}s)")
