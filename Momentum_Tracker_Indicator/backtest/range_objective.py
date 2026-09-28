"""Report F: can volatility / range be predicted, and can that be monetised without direction?
1. For every event family: realised range of the next N bars in ATR versus the unconditional distribution (ratio of medians,
   AUC of event-vs-random), by period.  2. Time-of-day range profile and its stability.  3. A symmetric OCO straddle
   (buy stop + sell stop at +/- a ATR, target T ATR from the trigger, stop = the other trigger) after the most
   range-predictive events, net of spread, versus the same straddle at random bars.
"""
import json, math, os
import numpy as np, pandas as pd
import discovery_engine as DE

os.makedirs("results/phase13", exist_ok=True)
d5 = DE.base_frame(5); EV = DE.events(d5)
h, l, c, atr = (d5[k].to_numpy(float) for k in ("high", "low", "close", "atr"))
t5 = d5["t"].to_numpy(); n = len(d5)
times = pd.to_datetime(d5["time"]); per = np.select([times < DE.PERIODS["DEV"][1], times < DE.PERIODS["VAL"][1]], ["DEV", "VAL"], "OOS")
from numpy.lib.stride_tricks import sliding_window_view
def fwd_range(N):
    out = np.full(n, np.nan)
    hw = sliding_window_view(h, N); lw = sliding_window_view(l, N)
    out[: n - N] = (hw[1:].max(axis=1) - lw[1:].min(axis=1)) / atr[: n - N]
    return out
FR = {N: fwd_range(N) for N in (10, 20, 50)}
def auc(a, b, rng=np.random.default_rng(5)):
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 30 or len(b) < 30: return np.nan
    bs = rng.choice(b, size=min(len(b), 20000), replace=False); as_ = rng.choice(a, size=min(len(a), 20000), replace=False)
    return float(np.mean(as_[:, None] > bs[None, :][:, :2000]))
rows = []
for name, ev in EV.items():
    if ev is None or len(ev) < 100: continue
    i = ev["i"].to_numpy()
    for N in (10, 20, 50):
        base = FR[N]; x = base[i]
        row = dict(event=name, N=N, n=int(len(i)), ratio_all=round(float(np.nanmedian(x) / np.nanmedian(base)), 3), auc_all=round(auc(x, base), 3))
        for p in ("DEV", "VAL", "OOS"):
            m = per[i] == p; row[f"ratio_{p}"] = round(float(np.nanmedian(x[m]) / np.nanmedian(base[per == p])), 3) if m.sum() >= 30 else None
        rows.append(row)
R = pd.DataFrame(rows); R.to_csv("results/phase13/range_predictability.csv", index=False)
# time of day profile of the 20-bar forward range
hour = d5["hour"].to_numpy(); prof = []
for hr in range(24):
    m = hour == hr; row = dict(hour=hr, median_fwd20_atr=round(float(np.nanmedian(FR[20][m])), 3))
    for p in ("DEV", "VAL", "OOS"): row[f"{p}"] = round(float(np.nanmedian(FR[20][m & (per == p)])), 3)
    prof.append(row)
# straddle monetisation
m1_t, m1_o, m1_h, m1_l, SPR = DE.m1_t, DE.m1_o, DE.m1_h, DE.m1_l, DE.SPR
def straddle(idx, a, T, H=250):
    """OCO at +/- a ATR from the event close; target T ATR beyond the trigger; stop at the other trigger. Returns P&L in ATR (net)."""
    out = np.full(len(idx), np.nan); amb = 0
    for q, i in enumerate(idx):
        k = int(np.searchsorted(m1_t, t5[i] + 300, side="left")); u = atr[i]
        if k + 3 >= len(m1_t) or np.isnan(u) or u <= 0: continue
        e = min(k + H, len(m1_t)); hh = m1_h[k:e]; ll = m1_l[k:e]; sp = SPR[k:e]
        U = c[i] + a * u; D = c[i] - a * u
        ju = np.argmax(hh + sp >= U) if (hh + sp >= U).any() else 10**9; jd = np.argmax(ll <= D) if (ll <= D).any() else 10**9
        if ju == 10**9 and jd == 10**9: out[q] = 0.0; continue                # never triggered: no trade
        if ju == jd: amb += 1; continue                                       # both in one minute: unresolvable at bar level
        if ju < jd:                                                             # long triggered
            fill = U + sp[ju]; tgt = fill + T * u; j = ju
            while j < len(hh):
                if ll[j] <= D: out[q] = (D - fill) / u; break
                if hh[j] >= tgt: out[q] = T; break
                j += 1
            else: out[q] = (hh[-1] * 0 + (m1_o[e - 1] - fill)) / u
        else:                                                                   # short triggered
            fill = D; tgt = fill - T * u; j = jd
            while j < len(hh):
                if hh[j] + sp[j] >= U: out[q] = (fill - U - sp[j]) / u; break
                if ll[j] + sp[j] <= tgt: out[q] = T; break
                j += 1
            else: out[q] = (fill - (m1_o[e - 1] + sp[e - 1 - k])) / u
    return out, amb
top = R[R.N == 20].sort_values("auc_all", ascending=False).head(6).event.tolist()
rng = np.random.default_rng(11); rand_idx = np.sort(rng.choice(np.arange(100, n - 300), size=8000, replace=False))
strad = []
for a, T in ((0.25, 0.75), (0.5, 1.5), (1.0, 2.0)):
    pr, amb = straddle(rand_idx, a, T)
    row = dict(event="RANDOM BARS (baseline)", a=a, T=T, n=int(np.isfinite(pr).sum()), ambiguous=amb, exp_all=round(float(np.nanmean(pr)), 3), share_triggered=round(float(np.nanmean(pr != 0)), 3))
    for p in ("DEV", "VAL", "OOS"): m = per[rand_idx] == p; row[f"exp_{p}"] = round(float(np.nanmean(pr[m])), 3)
    strad.append(row)
    for name in top:
        i = EV[name]["i"].to_numpy(); pe, amb = straddle(i, a, T)
        row = dict(event=name, a=a, T=T, n=int(np.isfinite(pe).sum()), ambiguous=amb, exp_all=round(float(np.nanmean(pe)), 3), share_triggered=round(float(np.nanmean(pe != 0)), 3))
        for p in ("DEV", "VAL", "OOS"): m = per[i] == p; row[f"exp_{p}"] = round(float(np.nanmean(pe[m])), 3) if m.sum() >= 30 else None
        strad.append(row)
S = pd.DataFrame(strad); S.to_csv("results/phase13/straddle.csv", index=False)
json.dump(dict(range=rows, profile=prof, straddle=strad, top_events=top), open("results/phase13/range_objective.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print("RANGE PREDICTABILITY (N=20), sorted by AUC:"); print(R[R.N == 20].sort_values("auc_all", ascending=False)[["event", "n", "ratio_all", "auc_all", "ratio_DEV", "ratio_VAL", "ratio_OOS"]].to_string(index=False))
print("\nTIME OF DAY (median 20-bar forward range / ATR):"); print(pd.DataFrame(prof).to_string(index=False))
print("\nSTRADDLE (net, ATR units):"); print(S.to_string(index=False))
