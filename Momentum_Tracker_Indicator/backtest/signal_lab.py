"""Phase 2: does the raw Supertrend flip contain a profitable subset? Signal-level study, no trade management.

Every M3 flip (26,963) gets features known at its close, then its forward path on M1 bars: first-passage
times to +L and -L (L in ATR units) with the real spread, MFE/MAE at 1..50 M3-bar horizons, and the
outcome of every stop/target pair. Everything is reported by DEV / VAL / OOS and by year.
"""
import json, math, os, time
os.environ["LAB_SKIP_RUNS"] = "1"
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
import twk_engine as E
from filter_lab import m1, sig, ser, spread, PERIODS, END

T0 = time.time()
os.makedirs("results/signal", exist_ok=True)
sig = sig.reset_index(drop=True).copy()
n = len(sig)
LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
HORIZ_M3 = [1, 3, 5, 10, 20, 30, 50]
H_M1 = 600                                   # scan horizon: 10 hours of M1 bars

# ------------------------------------------------------------------ extra features at the signal close
b = sig["bar"].to_numpy()
o, h, l, c = ser["o"], ser["h"], ser["l"], ser["c"]
atr = sig["atr"].to_numpy()
ema20 = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
ema50 = pd.Series(c).ewm(span=50, adjust=False).mean().to_numpy()
side = sig["side"].to_numpy()
sig["ema_sep"] = (ema20[b] - ema50[b]) / atr * side                       # + = fast above slow in the signal direction
sig["ema50_slope"] = (ema50[b] - ema50[np.maximum(b - 5, 0)]) / atr * side
sig["px_vs_ema50"] = (c[b] - ema50[b]) / atr * side
sig["atr_slope"] = (ser["atr"][b] - ser["atr"][np.maximum(b - 10, 0)]) / atr
sig["prev_range_ratio"] = (h[np.maximum(b - 1, 0)] - l[np.maximum(b - 1, 0)]) / atr
hw = sliding_window_view(h, 50); lw = sliding_window_view(l, 50)
hi50 = np.full(len(c), np.nan); lo50 = np.full(len(c), np.nan)
hi50[50:] = hw[:-1].max(axis=1); lo50[50:] = lw[:-1].min(axis=1)           # previous 50 bars, excluding the current
sig["room_ahead"] = np.where(side == 1, (hi50[b] - c[b]), (c[b] - lo50[b])) / atr      # distance to the 50-bar extreme in the trade direction (<0 = breakout)
sig["room_behind"] = np.where(side == 1, (c[b] - lo50[b]), (hi50[b] - c[b])) / atr     # distance from the 50-bar extreme behind the trade
rng = np.maximum(h[b] - l[b], 1e-9)
sig["close_loc"] = np.where(side == 1, (c[b] - l[b]) / rng, (h[b] - c[b]) / rng)       # 1 = closed at the extreme in the signal direction
sig["body_ratio"] = np.abs(c[b] - o[b]) / rng
sig["purple_dist"] = np.abs(c[b] - sig["purple"].to_numpy()) / atr
sig["vol_ratio"] = np.where(side == 1, sig.bv1 / np.maximum(sig.sv1, 1e-9), sig.sv1 / np.maximum(sig.bv1, 1e-9))
sig["box_m1"] = np.where(side == 1, sig.bv1 > sig.sv1, sig.sv1 > sig.bv1)
sig["box_m3"] = np.where(side == 1, sig.bv3 > sig.sv3, sig.sv3 > sig.bv3)
sig["ea_pass"] = (sig.vol_ratio >= 1.2) & sig.box_m1 & sig.box_m3 & (sig.adx > 20)
sig["minutes_since_prev"] = sig["close_time"].diff() / 60
sig["session"] = pd.cut(sig.hour, [-1, 1, 9, 14, 19, 23], labels=["late_00-02", "asia_02-10", "london_10-15", "overlap_15-20", "ny_20-24"])
sig["year"] = pd.to_datetime(sig.time).dt.year
sig["period"] = np.select([(pd.to_datetime(sig.time) < PERIODS["DEV"][1]), (pd.to_datetime(sig.time) < PERIODS["VAL"][1])], ["DEV", "VAL"], "OOS")
# pivot distance in ATR (structure stop size)
sig["pivot_dist"] = np.where(sig.sl_pivot, sig.risk / atr, np.nan)
# swing proximity: distance to the last confirmed pivot in the direction of the stop
sig["swing_dist"] = np.where(side == 1, (c[b] - ser["lastPL"][b]), (ser["lastPH"][b] - c[b])) / atr
print(f"features done: {n} signals ({time.time()-T0:.0f}s)", flush=True)

# ------------------------------------------------------------------ forward scan on M1
m1_t = (m1["time"].astype("int64") // 10**9).to_numpy()
m1_o = m1["open"].to_numpy(float); m1_h = m1["high"].to_numpy(float); m1_l = m1["low"].to_numpy(float); m1_c = m1["close"].to_numpy(float)
spr = spread * 0.01
k0_all = np.searchsorted(m1_t, sig["close_time"].to_numpy(), side="left")
HZ_M1 = [x * 3 for x in HORIZ_M3]

def scan(k_entry, fill, use_spread, sd, a):
    """First-passage times (in M1 bars) to +L/-L (L x ATR), MFE/MAE at horizons, end P&L. Returns dict of arrays."""
    N = len(k_entry)
    t_fav = np.full((N, len(LEVELS)), H_M1, dtype=np.int32); t_adv = np.full((N, len(LEVELS)), H_M1, dtype=np.int32)
    mfe = np.full((N, len(HZ_M1)), np.nan); mae = np.full((N, len(HZ_M1)), np.nan); endp = np.full(N, np.nan); valid = np.zeros(N, bool)
    Lv = np.array(LEVELS)
    for i in range(N):
        k = int(k_entry[i])
        if k < 0 or k + 2 >= len(m1_t) or math.isnan(a[i]) or a[i] <= 0 or math.isnan(fill[i]):
            continue
        e = k + H_M1
        hh = m1_h[k:e]; ll = m1_l[k:e]; s = spr[k:e] if use_spread else 0.0
        if sd[i] == 1:
            fav = hh - fill[i]; adv = fill[i] - ll
        else:
            fav = fill[i] - (ll + s); adv = (hh + s) - fill[i]
        cf = np.maximum.accumulate(fav); ca = np.maximum.accumulate(adv)
        lv = Lv * a[i]
        tf = np.searchsorted(cf, lv, side="left"); ta = np.searchsorted(ca, lv, side="left")
        m = len(cf)
        t_fav[i] = np.where(tf < m, tf, H_M1); t_adv[i] = np.where(ta < m, ta, H_M1)
        for j, hz in enumerate(HZ_M1):
            if hz - 1 < m:
                mfe[i, j] = cf[hz - 1]; mae[i, j] = ca[hz - 1]
        last = min(e, len(m1_t)) - 1
        endp[i] = (m1_c[last] - fill[i]) if sd[i] == 1 else (fill[i] - (m1_c[last] + (spr[last] if use_spread else 0.0)))
        valid[i] = True
    return dict(t_fav=t_fav, t_adv=t_adv, mfe=mfe, mae=mae, endp=endp, valid=valid)

def fills_for(k_entry, sd, use_spread):
    f = m1_o[np.clip(k_entry, 0, len(m1_o) - 1)].copy()
    if use_spread:
        f = np.where(sd == 1, f + spr[np.clip(k_entry, 0, len(spr) - 1)], f)
    return f

gross = scan(k0_all, fills_for(k0_all, side, False), False, side, atr)
net = scan(k0_all, fills_for(k0_all, side, True), True, side, atr)
print(f"forward scan done ({time.time()-T0:.0f}s)", flush=True)

def outcome_R(res, S, T, a):
    """Per-signal result in R (R = S x ATR) for stop S and target T (ATR units): +T/S, -1, or the end P&L."""
    iS, iT = LEVELS.index(S), LEVELS.index(T)
    tf, ta = res["t_fav"][:, iT], res["t_adv"][:, iS]
    hit = (tf < ta) & (tf < H_M1)
    stopped = (ta <= tf) & (ta < H_M1)
    r = np.where(hit, T / S, np.where(stopped, -1.0, res["endp"] / (S * a)))
    r = np.where(res["valid"], r, np.nan)
    return r, hit, stopped

def stats(r, hit, stopped, mask=None):
    if mask is not None:
        r, hit, stopped = r[mask], hit[mask], stopped[mask]
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(n=0)
    gp = r[r > 0].sum(); gl = -r[r < 0].sum()
    return dict(n=int(len(r)), hit=round(float(np.mean(hit[~np.isnan(hit.astype(float))])) if len(hit) else 0, 3), stopped=round(float(np.mean(stopped)), 3),
                exp_r=round(float(r.mean()), 3), pf=round(float(gp / gl), 2) if gl > 0 else float("inf"), median_r=round(float(np.median(r)), 3))

OUT = {"n_signals": int(n), "generated": str(pd.Timestamp.now())[:16]}
per = sig["period"].to_numpy(); yr = sig["year"].to_numpy()

# ------------------------------------------------------------------ 6 + 16: directional test and hindsight grid
grid = []
for S in LEVELS[:6]:
    for T in LEVELS[:6]:
        rg, hg, sg = outcome_R(gross, S, T, atr); rn, hn, sn = outcome_R(net, S, T, atr)
        row = dict(stop=S, target=T, be_hit_rate=round(S / (S + T), 3))
        for nm, (r, hh, ss) in (("gross", (rg, hg, sg)), ("net", (rn, hn, sn))):
            st = stats(r, hh, ss); row[f"{nm}_hit"] = st.get("hit"); row[f"{nm}_exp_r"] = st.get("exp_r"); row[f"{nm}_pf"] = st.get("pf")
        for p_ in ("DEV", "VAL", "OOS"):
            st = stats(rn, hn, sn, per == p_); row[f"net_exp_{p_}"] = st.get("exp_r"); row[f"net_hit_{p_}"] = st.get("hit"); row[f"n_{p_}"] = st.get("n")
        grid.append(row)
OUT["grid"] = grid
# directional (S = T = X)
OUT["directional"] = [g for g in grid if g["stop"] == g["target"]]
# by year for the 1x1 and 1x2 shapes
byy = []
for (S, T) in ((1.0, 1.0), (1.0, 2.0), (0.5, 1.0)):
    rn, hn, sn = outcome_R(net, S, T, atr); rg, hg, sg = outcome_R(gross, S, T, atr)
    for y in sorted(set(yr)):
        m = yr == y
        byy.append(dict(stop=S, target=T, year=int(y), **{f"net_{k}": v for k, v in stats(rn, hn, sn, m).items()}, gross_exp_r=stats(rg, hg, sg, m).get("exp_r")))
OUT["by_year"] = byy
print("directional test done", flush=True)

# ------------------------------------------------------------------ 2/3: excursion horizons + classification
hz_rows = []
for j, hz in enumerate(HORIZ_M3):
    fe = gross["mfe"][:, j] / atr; ae = gross["mae"][:, j] / atr; ok = ~np.isnan(fe)
    hz_rows.append(dict(horizon_m3_bars=hz, mfe_atr_median=round(float(np.nanmedian(fe)), 3), mfe_atr_p75=round(float(np.nanpercentile(fe[ok], 75)), 3),
                        mae_atr_median=round(float(np.nanmedian(ae)), 3), mae_atr_p75=round(float(np.nanpercentile(ae[ok], 75)), 3),
                        share_mfe_gt_mae=round(float(np.mean(fe[ok] > ae[ok])), 3), mfe_minus_mae_mean=round(float(np.nanmean(fe - ae)), 3)))
OUT["horizons"] = hz_rows
spread_atr = (sig.spread_px.to_numpy() / atr)
OUT["spread_in_atr"] = dict(median=round(float(np.nanmedian(spread_atr)), 3), p25=round(float(np.nanpercentile(spread_atr, 25)), 3), p75=round(float(np.nanpercentile(spread_atr, 75)), 3),
                            by_year={int(y): round(float(np.nanmedian(spread_atr[yr == y])), 3) for y in sorted(set(yr))})
fe20 = gross["mfe"][:, HORIZ_M3.index(20)]
sp_units = fe20 / sig.spread_px.to_numpy()
OUT["mfe20_in_spreads"] = {f"share_ge_{k}x": round(float(np.nanmean(sp_units >= k)), 3) for k in (2, 3, 5, 10, 20)}
cls_rows = []
for S in (0.5, 1.0, 1.5):
    iS = LEVELS.index(S)
    ta = net["t_adv"][:, iS]
    def tf(L): return net["t_fav"][:, LEVELS.index(L)]
    lab = np.where(tf(2.0) < ta, "strong_winner", np.where(tf(1.0) < ta, "moderate_winner", np.where(ta < tf(0.25), "strong_loser", np.where(ta < tf(0.5), "moderate_loser", "neutral"))))
    lab = np.where(net["valid"], lab, "invalid")
    counts = pd.Series(lab).value_counts()
    cls_rows.append(dict(stop_atr=S, **{k: int(counts.get(k, 0)) for k in ("strong_winner", "moderate_winner", "neutral", "moderate_loser", "strong_loser")},
                         **{f"{k}_pct": round(float(counts.get(k, 0) / net["valid"].sum() * 100), 1) for k in ("strong_winner", "moderate_winner", "neutral", "moderate_loser", "strong_loser")}))
    if S == 1.0:
        sig["class_1atr"] = lab
OUT["classes"] = cls_rows

# ------------------------------------------------------------------ 4/8/9/10/12: feature separation, by bucket and by period
r11, h11, s11 = outcome_R(net, 1.0, 1.0, atr); r12, h12, s12 = outcome_R(net, 1.0, 2.0, atr); r11g, _, _ = outcome_R(gross, 1.0, 1.0, atr)
sig["r11"] = r11; sig["r12"] = r12; sig["r11_gross"] = r11g; sig["hit11"] = h11
# previous raw signal outcome (1x1, net)
sig["prev_r11"] = sig["r11"].shift(1); sig["prev_outcome"] = np.where(sig.prev_r11 > 0, "prev_win", np.where(sig.prev_r11 < 0, "prev_loss", "prev_flat"))
sig["prev_same_dir"] = sig["side"] == sig["side"].shift(1)

FEATURES = {
    # volatility
    "atr_ratio": ("q", "ATR / 30-day median"), "atr_slope": ("q", "ATR change over 10 bars / ATR"), "range_ratio": ("q", "signal bar range / ATR"), "prev_range_ratio": ("q", "previous bar range / ATR"),
    "bbw_atr": ("q", "Bollinger width / ATR"),
    # trend
    "adx": ("q", "ADX(14)"), "adx_slope": ("q", "ADX change over 5 bars"), "ema_sep": ("q", "(EMA20 - EMA50) / ATR in the signal direction"), "ema50_slope": ("q", "EMA50 slope / ATR in the signal direction"),
    "px_vs_ema50": ("q", "(close - EMA50) / ATR in the signal direction"), "dist_ema": ("q", "|close - EMA20| / ATR"),
    "htf15_aligned": ("b", "M15 Supertrend agrees"), "htf60_aligned": ("b", "H1 Supertrend agrees"), "ema15_aligned": ("b", "M15 EMA50 slope agrees"),
    # signal behaviour / strength
    "opp_ago": ("q", "bars since the opposite flip (signal age of the previous leg)"), "flips_10": ("q", "other flips in the last 10 bars"), "flips_20": ("q", "other flips in the last 20 bars"),
    "dist_prev_sig": ("q", "|close - previous signal close| / ATR (extent of the previous leg)"), "minutes_since_prev": ("q", "minutes since the previous signal"),
    "purple_dist": ("q", "|close - purple line| / ATR at the flip (penetration)"), "close_loc": ("q", "close location inside the signal bar (1 = at the extreme)"), "body_ratio": ("q", "body / range of the signal bar"),
    "opp_candles5": ("q", "candles against the signal in the last 5"),
    # price structure
    "room_ahead": ("q", "distance to the 50-bar extreme ahead / ATR (negative = breakout)"), "room_behind": ("q", "distance from the 50-bar extreme behind / ATR"),
    "swing_dist": ("q", "distance to the last confirmed pivot behind / ATR"), "pivot_dist": ("q", "structure stop size / ATR (when a pivot exists)"),
    # EA filters
    "vol_ratio": ("q", "M1 up/down volume ratio in the signal direction"), "box_m1": ("b", "M1 box agrees"), "box_m3": ("b", "M3 box agrees"), "ea_pass": ("b", "passes all shipped EA filters"),
    # cost / context
    "cost_over_reward": ("q", "spread / (2 x stop)"), "session": ("c", "session (server time)"), "dow": ("c", "day of week (0 = Monday)"), "prev_outcome": ("c", "previous raw signal outcome (1x1 net)"),
    "prev_same_dir": ("b", "same direction as the previous signal"), "class_1atr": ("c", "outcome class (diagnostic only)"),
}
feat_rows = []
bucket_rows = []
for f, (kind, desc) in FEATURES.items():
    v = sig[f]
    if kind == "q":
        vv = v.astype(float)
        ok = ~vv.isna()
        try:
            bins = pd.qcut(vv[ok], 5, labels=["Q1 low", "Q2", "Q3", "Q4", "Q5 high"], duplicates="drop")
        except ValueError:
            continue
        bucket = pd.Series(np.nan, index=sig.index, dtype=object); bucket[ok] = bins.astype(str)
    else:
        bucket = v.astype(str)
    d = pd.DataFrame(dict(b=bucket, r=sig.r11, r2=sig.r12, hit=sig.hit11, per=sig.period, yr=sig.year))
    d = d[~d.r.isna() & ~d.b.isna() & (d.b != "nan")]
    g = d.groupby("b")
    tbl = g.agg(n=("r", "size"), hit=("hit", "mean"), exp11=("r", "mean"), exp12=("r2", "mean")).reset_index()
    for p_ in ("DEV", "VAL", "OOS"):
        tbl[f"exp11_{p_}"] = d[d.per == p_].groupby("b").r.mean().reindex(tbl.b).to_numpy()
        tbl[f"n_{p_}"] = d[d.per == p_].groupby("b").r.size().reindex(tbl.b).fillna(0).astype(int).to_numpy()
    yrs = sorted(d.yr.unique())
    ytab = d.groupby(["b", "yr"]).r.mean().unstack()
    for _, r in tbl.iterrows():
        bucket_rows.append(dict(feature=f, bucket=r.b, n=int(r.n), hit=round(float(r.hit), 3), exp11=round(float(r.exp11), 3), exp12=round(float(r.exp12), 3),
                                **{f"exp11_{p_}": (round(float(r[f'exp11_{p_}']), 3) if not np.isnan(r[f'exp11_{p_}']) else None) for p_ in ("DEV", "VAL", "OOS")},
                                **{f"n_{p_}": int(r[f"n_{p_}"]) for p_ in ("DEV", "VAL", "OOS")},
                                years_positive=int((ytab.loc[r.b] > 0).sum()) if r.b in ytab.index else 0, years=len(yrs)))
    # separation: best bucket minus worst bucket, and does the ordering hold across periods?
    if len(tbl) >= 2:
        best = tbl.loc[tbl.exp11.idxmax()]; worst = tbl.loc[tbl.exp11.idxmin()]
        agree = sum(1 for p_ in ("DEV", "VAL", "OOS") if not np.isnan(best[f"exp11_{p_}"]) and not np.isnan(worst[f"exp11_{p_}"]) and best[f"exp11_{p_}"] > worst[f"exp11_{p_}"])
        pos_all = sum(1 for p_ in ("DEV", "VAL", "OOS") if not np.isnan(best[f"exp11_{p_}"]) and best[f"exp11_{p_}"] > 0)
        feat_rows.append(dict(feature=f, description=desc, kind=kind, best_bucket=best.b, best_exp11=round(float(best.exp11), 3), best_n=int(best.n), worst_bucket=worst.b, worst_exp11=round(float(worst.exp11), 3),
                              separation=round(float(best.exp11 - worst.exp11), 3), order_holds_in_periods=agree, best_positive_in_periods=pos_all,
                              best_DEV=round(float(best.exp11_DEV), 3) if not np.isnan(best.exp11_DEV) else None, best_VAL=round(float(best.exp11_VAL), 3) if not np.isnan(best.exp11_VAL) else None,
                              best_OOS=round(float(best.exp11_OOS), 3) if not np.isnan(best.exp11_OOS) else None))
FR = pd.DataFrame(feat_rows).sort_values(["order_holds_in_periods", "separation"], ascending=[False, False])
FR.to_csv("results/signal/feature_ranking.csv", index=False)
pd.DataFrame(bucket_rows).to_csv("results/signal/feature_buckets.csv", index=False)
OUT["feature_ranking"] = FR.to_dict("records"); OUT["feature_buckets"] = bucket_rows
print("features ranked", flush=True)

# ------------------------------------------------------------------ 10/12: continuation vs reversal, regimes, entry location
sig["cont_rev"] = np.where(sig.htf15_aligned & sig.htf60_aligned, "continuation (M15+H1 agree)", np.where(~sig.htf15_aligned & ~sig.htf60_aligned, "reversal (both against)", "mixed"))
sig["structure"] = np.where(sig.room_ahead < 0, "range breakout", np.where(sig.room_behind <= 0.5, "range fade (at the edge behind)", np.where(sig.room_ahead <= 0.5, "into the edge ahead", "inside range")))
trend = np.where(sig.adx >= 30, "strong trend", np.where(sig.adx >= 20, "weak trend", "range"))
vol = np.where(sig.atr_ratio >= 1.3, "high vol", np.where(sig.atr_ratio <= 0.8, "low vol", "normal vol"))
volmove = np.where(sig.atr_slope > 0.1, "expanding", np.where(sig.atr_slope < -0.1, "contracting", "flat"))
sig["regime"] = pd.Series(trend) + " / " + pd.Series(vol)
sig["vol_regime"] = pd.Series(vol) + " / " + pd.Series(volmove)
sig["location"] = np.select([sig.room_ahead < 0, sig.swing_dist <= 0.5, sig.room_behind <= 0.5, sig.range_ratio > 2, sig.dist_ema <= 0.5, sig.dist_ema >= 2.5],
                            ["after breakout", "at the swing pivot", "at the range edge behind", "after a large candle", "at the EMA20", "far from the EMA20"], "middle of range")
def split_table(col):
    rows = []
    d = sig[~sig.r11.isna()]
    for k, g in d.groupby(col):
        row = dict(group=str(k), n=int(len(g)), hit=round(float(g.hit11.mean()), 3), exp11=round(float(g.r11.mean()), 3), exp12=round(float(g.r12.mean()), 3), exp11_gross=round(float(g.r11_gross.mean()), 3))
        for p_ in ("DEV", "VAL", "OOS"):
            gg = g[g.period == p_]; row[f"n_{p_}"] = int(len(gg)); row[f"exp11_{p_}"] = round(float(gg.r11.mean()), 3) if len(gg) else None
        row["years_positive"] = int((g.groupby("year").r11.mean() > 0).sum()); rows.append(row)
    return rows
OUT["cont_rev"] = split_table("cont_rev"); OUT["structure"] = split_table("structure"); OUT["regime"] = split_table("regime"); OUT["vol_regime"] = split_table("vol_regime"); OUT["location"] = split_table("location")
OUT["ea_pass"] = split_table("ea_pass"); OUT["session"] = split_table("session"); OUT["prev_outcome"] = split_table("prev_outcome")
print("splits done", flush=True)

# ------------------------------------------------------------------ 5/11: entry timing
timing = []
def timing_row(name, k_entry, fill, taken_mask):
    res = scan(k_entry, fill, True, side, atr)
    r1, h1, s1 = outcome_R(res, 1.0, 1.0, atr); r2, h2, s2 = outcome_R(res, 1.0, 2.0, atr)
    row = dict(entry=name, taken=round(float(taken_mask.mean()), 3))
    for p_ in ("ALL", "DEV", "VAL", "OOS"):
        m = taken_mask & ((per == p_) if p_ != "ALL" else True)
        st1 = stats(r1, h1, s1, m); st2 = stats(r2, h2, s2, m)
        row[f"n_{p_}"] = st1.get("n"); row[f"hit11_{p_}"] = st1.get("hit"); row[f"exp11_{p_}"] = st1.get("exp_r"); row[f"exp12_{p_}"] = st2.get("exp_r")
    timing.append(row)
timing_row("A immediate (next M1 open)", k0_all, fills_for(k0_all, side, True), np.ones(n, bool))
# B confirmation: next M3 bar closes in the signal direction
nb = np.minimum(b + 1, len(c) - 1)
confirm = np.where(side == 1, c[nb] > o[nb], c[nb] < o[nb])
kB = k0_all + 3
timing_row("B confirmation bar (enter after the next M3 bar closes in the direction)", kB, fills_for(kB, side, True), confirm)
for nbars in (1, 2, 3, 5):
    kD = k0_all + 3 * nbars
    timing_row(f"E delayed +{nbars} M3 bar(s)", kD, fills_for(kD, side, True), np.ones(n, bool))
# C pullback: within 5 M3 bars price touches fill - 0.5 ATR (buy) -> limit fill there
kC = np.full(n, -1); fC = np.full(n, np.nan)
kX = np.full(n, -1); fX = np.full(n, np.nan)
for i in range(n):
    k = int(k0_all[i]); a = atr[i]
    if k + 16 >= len(m1_t) or math.isnan(a):
        continue
    f0 = m1_o[k] + (spr[k] if side[i] == 1 else 0.0)
    hh = m1_h[k:k + 15]; ll = m1_l[k:k + 15]
    if side[i] == 1:
        lvl = f0 - 0.5 * a; j = np.argmax(ll <= lvl) if (ll <= lvl).any() else -1
        if j >= 0: kC[i] = k + j; fC[i] = lvl + spr[k + j]
        bo = h[b[i]] + 0.0; j2 = np.argmax(hh > bo) if (hh > bo).any() else -1
        if j2 >= 0: kX[i] = k + j2; fX[i] = bo + spr[k + j2]
    else:
        lvl = f0 + 0.5 * a; j = np.argmax(hh >= lvl) if (hh >= lvl).any() else -1
        if j >= 0: kC[i] = k + j; fC[i] = lvl
        bo = l[b[i]]; j2 = np.argmax(ll < bo) if (ll < bo).any() else -1
        if j2 >= 0: kX[i] = k + j2; fX[i] = bo
timing_row("C pullback 0.5 ATR within 5 bars (limit)", kC, fC, kC >= 0)
timing_row("D breakout of the signal bar within 5 bars (stop order)", kX, fX, kX >= 0)
OUT["timing"] = timing
# pullback path classification on immediate entries
i05, i1 = LEVELS.index(0.5), LEVELS.index(1.0)
tf05, ta05, tf1, ta1 = net["t_fav"][:, i05], net["t_adv"][:, i05], net["t_fav"][:, i1], net["t_adv"][:, i1]
path = np.where(tf05 < ta05, "immediate move in favour (0.5 ATR first)", np.where((ta05 < tf05) & (tf1 < ta1), "pullback 0.5 ATR then continuation to +1 ATR", np.where(ta05 < tf05, "pullback then failure", "no 0.5 ATR move in 10 h")))
pc = pd.Series(path[net["valid"]]).value_counts()
OUT["pullback_paths"] = [dict(path=k, n=int(v), pct=round(float(v / net["valid"].sum() * 100), 1), exp11=round(float(np.nanmean(r11[net["valid"]][path[net["valid"]] == k])), 3)) for k, v in pc.items()]
print("timing done", flush=True)

# ------------------------------------------------------------------ 7/15: minimum profitable move
mpm = []
med_spread_atr = float(np.nanmedian(spread_atr))
for S in (0.5, 1.0, 1.5):
    for T in (0.5, 1.0, 1.5, 2.0):
        rn, hn, sn = outcome_R(net, S, T, atr); rg, hg, sg = outcome_R(gross, S, T, atr)
        p = float(np.nanmean(hg[gross["valid"]])); pn = float(np.nanmean(hn[net["valid"]]))
        be = (S + med_spread_atr) / (S + T)
        mpm.append(dict(stop_atr=S, target_atr=T, gross_hit=round(p, 3), net_hit=round(pn, 3), breakeven_hit_needed=round(be, 3), margin=round(pn - be, 3),
                        net_exp_r=round(float(np.nanmean(rn)), 3), req_hit_for_plus025R=round((S + med_spread_atr + 0.25 * S) / (S + T), 3), req_hit_for_plus05R=round((S + med_spread_atr + 0.5 * S) / (S + T), 3)))
OUT["min_move"] = mpm

# ------------------------------------------------------------------ 17/18: GOOD_SIGNAL candidates and walk-forward
cands = []
d = sig[~sig.r11.isna()].copy()
def eval_mask(mask, label):
    row = dict(rule=label)
    for p_ in ("DEV", "VAL", "OOS"):
        g = d[mask & (d.period == p_)]; row[f"n_{p_}"] = int(len(g)); row[f"exp11_{p_}"] = round(float(g.r11.mean()), 3) if len(g) else None; row[f"exp12_{p_}"] = round(float(g.r12.mean()), 3) if len(g) else None
        row[f"hit_{p_}"] = round(float(g.hit11.mean()), 3) if len(g) else None
    g = d[mask]; row["n"] = int(len(g)); row["exp11"] = round(float(g.r11.mean()), 3) if len(g) else None; row["years_positive"] = int((g.groupby("year").r11.mean() > 0).sum()) if len(g) else 0
    row["exp11_gross"] = round(float(g.r11_gross.mean()), 3) if len(g) else None
    return row
# components: every feature bucket whose 1x1 net expectancy is positive in DEV AND VAL with >= 200 trades in each
BR = pd.DataFrame(bucket_rows)
comp = BR[(BR.exp11_DEV.astype(float) > 0) & (BR.exp11_VAL.astype(float) > 0) & (BR.n_DEV >= 200) & (BR.n_VAL >= 100)]
OUT["good_components"] = comp.to_dict("records")
# evaluate each component alone, then their conjunction (if any)
masks = []
for _, r in comp.iterrows():
    f = r.feature; kind = FEATURES[f][0]
    if kind == "q":
        vv = sig[f].astype(float); ok = ~vv.isna()
        bins = pd.qcut(vv[ok], 5, labels=["Q1 low", "Q2", "Q3", "Q4", "Q5 high"], duplicates="drop").astype(str)
        mk = pd.Series(False, index=sig.index); mk[ok] = (bins == r.bucket).to_numpy()
    else:
        mk = sig[f].astype(str) == r.bucket
    mk = mk.reindex(d.index).fillna(False).to_numpy()
    masks.append((f"{f} = {r.bucket}", mk))
    cands.append(eval_mask(mk, f"{f} = {r.bucket}"))
if masks:
    allm = np.ones(len(d), bool)
    for _, mk in masks:
        allm &= mk
    cands.append(eval_mask(allm, "ALL components together"))
OUT["good_candidates"] = cands
# also the obvious manual-style definitions, stated in advance (not searched)
pre = {
    "EA filters pass": (d.ea_pass.astype(bool)).to_numpy(),
    "signal age >= 10 bars AND leg >= 2 ATR": ((d.opp_ago >= 10) | (d.opp_ago < 0)).to_numpy() & (d.dist_prev_sig >= 2).to_numpy(),
    "continuation (M15+H1 agree) AND strong trend (ADX >= 30)": (d.cont_rev == "continuation (M15+H1 agree)").to_numpy() & (d.adx >= 30).to_numpy(),
    "reversal (both against) AND range (ADX < 20)": (d.cont_rev == "reversal (both against)").to_numpy() & (d.adx < 20).to_numpy(),
    "breakout of the 50-bar range": (d.room_ahead < 0).to_numpy(),
    "at the swing pivot (<= 0.5 ATR) with a small structure stop (<= 1 ATR)": (d.swing_dist <= 0.5).to_numpy() & (d.pivot_dist <= 1.0).to_numpy(),
    "normal vol AND weak/strong trend AND not a re-flip (age >= 5)": (d.atr_ratio.between(0.8, 1.5)).to_numpy() & (d.adx >= 20).to_numpy() & ((d.opp_ago >= 5) | (d.opp_ago < 0)).to_numpy(),
}
OUT["predefined"] = [eval_mask(mk, k) for k, mk in pre.items()]
# walk-forward on the conjunction and on the predefined sets: expectancy per year
wf = []
for k, mk in list(pre.items()) + ([("ALL components together", allm)] if masks else []):
    g = d[mk]
    wf.append(dict(rule=k, **{str(int(y)): (round(float(gg.r11.mean()), 3), int(len(gg))) for y, gg in g.groupby("year")}))
OUT["walk_forward_years"] = wf
print("good-signal search done", flush=True)

# ------------------------------------------------------------------ cross-timeframe directional check (raw flips, 1 ATR / 1 ATR)
xtf = []
m3b = E.resample(m1, 3)
for tf in (1, 5, 15):
    bars = E.resample(m1, tf); s2 = E.compute_series(bars, E.CoreParams()); st = E.signal_table(bars, s2, tf, m1, m3b, E.CoreParams(), 0).reset_index(drop=True)
    kk = np.searchsorted(m1_t, st["close_time"].to_numpy(), side="left"); sd2 = st["side"].to_numpy(); a2 = st["atr"].to_numpy()
    resg = scan(kk, fills_for(kk, sd2, False), False, sd2, a2); resn = scan(kk, fills_for(kk, sd2, True), True, sd2, a2)
    per2 = np.select([(pd.to_datetime(st.time) < PERIODS["DEV"][1]), (pd.to_datetime(st.time) < PERIODS["VAL"][1])], ["DEV", "VAL"], "OOS")
    for S, T in ((1.0, 1.0), (1.0, 2.0)):
        rg, hg, sg = outcome_R(resg, S, T, a2); rn, hn, sn = outcome_R(resn, S, T, a2)
        row = dict(tf=f"M{tf}", stop=S, target=T, n=int(resn["valid"].sum()), gross_hit=stats(rg, hg, sg).get("hit"), gross_exp_r=stats(rg, hg, sg).get("exp_r"), net_hit=stats(rn, hn, sn).get("hit"), net_exp_r=stats(rn, hn, sn).get("exp_r"))
        for p_ in ("DEV", "VAL", "OOS"):
            row[f"net_exp_{p_}"] = stats(rn, hn, sn, per2 == p_).get("exp_r")
        xtf.append(row)
for S, T in ((1.0, 1.0), (1.0, 2.0)):
    rg, hg, sg = outcome_R(gross, S, T, atr); rn, hn, sn = outcome_R(net, S, T, atr)
    row = dict(tf="M3", stop=S, target=T, n=int(net["valid"].sum()), gross_hit=stats(rg, hg, sg).get("hit"), gross_exp_r=stats(rg, hg, sg).get("exp_r"), net_hit=stats(rn, hn, sn).get("hit"), net_exp_r=stats(rn, hn, sn).get("exp_r"))
    for p_ in ("DEV", "VAL", "OOS"):
        row[f"net_exp_{p_}"] = stats(rn, hn, sn, per == p_).get("exp_r")
    xtf.append(row)
OUT["cross_tf"] = xtf

sig.to_csv("results/signal/signals_M3_full.csv", index=False)
json.dump(OUT, open("results/signal/signal_lab.json", "w"), indent=1, default=lambda x: float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
print(f"signal lab done ({time.time()-T0:.0f}s)")
