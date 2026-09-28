"""Filter lab: root-cause and A/B study of entry/exit filters on the TWK M3 strategy (shipped M3 preset).

Design
  * SIGNAL GENERATION is untouched (TWK_Core port). Every candidate is either a pre-filter on the signal
    table (context known at the signal close) or a management option in the simulator.
  * Each candidate is simulated ONCE over the full history and its trades are split into
    DEV (2021-09 .. 2023-12), VAL (2024) and OOS (2025-01 .. 2026-09). Selection uses DEV and VAL only.
  * A filter is retained only if, in BOTH DEV and VAL, it raises expectancy and profit factor, does not
    raise max drawdown, and removes a larger share of losers than of winners.
Outputs: results/lab/*.csv, results/lab/lab.json
"""
import json, math, os, time
import numpy as np
import pandas as pd
import twk_engine as E

os.makedirs("results/lab", exist_ok=True)
T0 = time.time()
TF = 3
LOTS = 0.02

# ------------------------------------------------------------------ data + signal context
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
years = m1["time"].dt.year.to_numpy()
spread = np.array([E.year_spread_model()[y] for y in years], float)
p = E.CoreParams()
m3 = E.resample(m1, 3)
ser = E.compute_series(m3, p)
sig = E.signal_table(m3, ser, TF, m1, m3, p, 5).reset_index(drop=True)
m15 = E.resample(m1, 15); ser15 = E.compute_series(m15, p)
h1 = E.resample(m1, 60); ser60 = E.compute_series(h1, p)
print(f"signals {len(sig)}  ({time.time()-T0:.0f}s)", flush=True)

# --- features at the signal close (no look-ahead)
bar = sig["bar"].to_numpy()
flip = (ser["long"] | ser["short"]).astype(int)
cum = np.concatenate([[0], np.cumsum(flip)])
for N in (5, 10, 20, 30):
    sig[f"flips_{N}"] = cum[bar + 1] - cum[np.maximum(bar + 1 - N, 0)] - 1        # other flips in the last N bars (excluding this one)
adx_s = ser["adx"]
sig["adx_slope"] = adx_s[bar] - adx_s[np.maximum(bar - 5, 0)]
h, l, c = ser["h"], ser["l"], ser["c"]
sig["range_ratio"] = (h[bar] - l[bar]) / sig["atr"]
ema20 = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
sig["dist_ema"] = np.abs(c[bar] - ema20[bar]) / sig["atr"]
sd20 = pd.Series(c).rolling(20).std().to_numpy()
sig["bbw_atr"] = 4 * sd20[bar] / sig["atr"]
# ATR regime: lagged 30-day median of the daily median M3 ATR
atr_daily = pd.Series(ser["atr"], index=m3["time"]).resample("1D").median().dropna()
atr_ref = atr_daily.rolling(30, min_periods=10).median().shift(1)
sig["atr_ratio"] = sig["atr"].to_numpy() / atr_ref.reindex(pd.to_datetime(sig["time"]).dt.floor("D")).ffill().bfill().to_numpy()
# consecutive opposite-colour candles before the signal bar (last 5 bars)
o = ser["o"]
up = (c > o).astype(int)
opp_cnt = np.zeros(len(sig), int)
for j, (b, s) in enumerate(zip(bar, sig["side"])):
    w = up[max(0, b - 5):b]
    opp_cnt[j] = int((w == 0).sum()) if s == 1 else int((w == 1).sum())
sig["opp_candles5"] = opp_cnt
# previous signal distance
prev_entry = sig["entry"].shift(1)
sig["dist_prev_sig"] = np.abs(sig["entry"] - prev_entry) / sig["atr"]
# HTF context: direction of the last CLOSED M15 / H1 bar at the signal close
def htf_dir(series_htf, htf_minutes):
    tt = series_htf["time"].astype("datetime64[s]").astype("int64") + htf_minutes * 60
    k = np.searchsorted(tt, sig["close_time"].to_numpy(), side="right") - 1
    d = np.where(k >= 0, series_htf["dir"][np.maximum(k, 0)], 0)
    return d
sig["dir15"] = htf_dir(ser15, 15); sig["dir60"] = htf_dir(ser60, 60)
sig["htf15_aligned"] = np.where(sig["side"] == 1, sig["dir15"] == -1, sig["dir15"] == 1)
sig["htf60_aligned"] = np.where(sig["side"] == 1, sig["dir60"] == -1, sig["dir60"] == 1)
ema50_15 = pd.Series(ser15["c"]).ewm(span=50, adjust=False).mean().to_numpy()
tt15 = ser15["time"].astype("datetime64[s]").astype("int64") + 900
k15 = np.searchsorted(tt15, sig["close_time"].to_numpy(), side="right") - 1
slope15 = np.where(k15 >= 3, ema50_15[np.maximum(k15, 0)] - ema50_15[np.maximum(k15 - 3, 0)], 0)
sig["ema15_aligned"] = np.where(sig["side"] == 1, slope15 > 0, slope15 < 0)
# cost context
sig["spread_px"] = np.array([E.year_spread_model()[y] for y in pd.to_datetime(sig["time"]).dt.year]) * 0.01
sig["cost_over_reward"] = sig["spread_px"] / (2.0 * sig["risk"].where(sig["risk"] > 0))
sig["cost_over_stop"] = sig["spread_px"] / sig["risk"].where(sig["risk"] > 0)
sig["hour"] = pd.to_datetime(sig["time"]).dt.hour
sig["dow"] = pd.to_datetime(sig["time"]).dt.dayofweek
sig.to_csv("results/lab/signals_M3_features.csv", index=False)

# ------------------------------------------------------------------ periods
END = pd.Timestamp("2026-09-25 00:00")
START = END - pd.DateOffset(years=5)
PERIODS = {"DEV": (pd.Timestamp("2021-09-01"), pd.Timestamp("2024-01-01")),
           "VAL": (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
           "OOS": (pd.Timestamp("2025-01-01"), END)}
T_A, T_B = int(START.timestamp()), int(END.timestamp())

def pm(tr):
    """Per-period metrics."""
    out = {}
    for name, (a, b) in PERIODS.items():
        d = tr[(tr.entry_time >= a) & (tr.entry_time < b)] if len(tr) else tr
        out[name] = short_metrics(d)
    out["ALL"] = short_metrics(tr)
    return out

def short_metrics(d):
    if d is None or len(d) == 0:
        return dict(n=0, wins=0, losses=0, net=0.0, gp=0.0, gl=0.0, pf=0.0, exp=0.0, dd=0.0, avg_win=0.0, avg_loss=0.0, mcl=0, spread=0.0, gross_ex=0.0, avg_r=0.0)
    pnl = d.pnl.to_numpy(float)
    w = pnl[pnl > 0.005]; ls = pnl[pnl < -0.005]
    eq = np.cumsum(pnl); peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    cl = mcl = 0
    for x in pnl:
        cl = cl + 1 if x < -0.005 else 0; mcl = max(mcl, cl)
    sp = float((d.spread * 2 * LOTS * 100).sum()) if "spread" in d else 0.0
    return dict(n=int(len(pnl)), wins=int(len(w)), losses=int(len(ls)), net=float(pnl.sum()), gp=float(w.sum()), gl=float(-ls.sum()),
                pf=float(w.sum() / -ls.sum()) if len(ls) and ls.sum() < 0 else float("inf"), exp=float(pnl.mean()),
                dd=float((peak - eq).max()), avg_win=float(w.mean()) if len(w) else 0.0, avg_loss=float(ls.mean()) if len(ls) else 0.0,
                mcl=int(mcl), spread=sp, gross_ex=float(pnl.sum() + sp - d.swap.sum()), avg_r=float(d.r_multiple.mean()))

# ------------------------------------------------------------------ baseline
BASE = dict(min_volume_ratio=1.2, purple_activation_pts=360, protection_activation_pts=900, lock_pts=180, min_improve_pts=9)
def bot(name, **kw):
    d = dict(BASE); d.update(kw); return E.MomentumEAParams(name=name, **d)

RUNS = {}       # name -> trades
META = {}       # name -> dict(group, rule, params)
def run(name, group, rule, b=None, mask=None, **kw):
    b = b or bot(name, **kw)
    s = sig if mask is None else sig[mask]
    tr = E.simulate(m1, s, ser, TF, b, spread, T_A, T_B)
    RUNS[name] = tr
    META[name] = dict(group=group, rule=rule)
    m = pm(tr)
    print(f"{name:34s} DEV n={m['DEV']['n']:5d} net={m['DEV']['net']:7.0f} PF={m['DEV']['pf']:.2f} | VAL n={m['VAL']['n']:4d} net={m['VAL']['net']:6.0f} PF={m['VAL']['pf']:.2f} | "
          f"OOS n={m['OOS']['n']:4d} net={m['OOS']['net']:6.0f} PF={m['OOS']['pf']:.2f}  ({time.time()-T0:.0f}s)", flush=True)
    return tr

base_tr = run("BASELINE", "baseline", "shipped M3 preset: ratio 1.2, boxes, ADX 20, pivot/purple stop, trail 360/900/180, hold through opposite")
base_tr.to_csv("results/lab/trades_BASELINE.csv", index=False)

SKIP = os.environ.get("LAB_SKIP_RUNS") == "1"
if not SKIP:
    # ------------------------------------------------------------------ TEST 1: cost gate
    for thr in (0.05, 0.10, 0.15, 0.20):
        run(f"cost_reward<={thr}", "T1 cost", f"spread / (RR x stop) <= {thr}", mask=(sig.cost_over_reward <= thr).to_numpy())
    for thr in (0.10, 0.20, 0.30):
        run(f"cost_stop<={thr}", "T1 cost", f"spread / stop <= {thr}", mask=(sig.cost_over_stop <= thr).to_numpy())

    # ------------------------------------------------------------------ TEST 2: cooldown / re-entry
    for mins in (1, 3, 5, 10, 15, 20, 30):
        for mode in ("all", "same", "opposite"):
            run(f"cool_{mins}m_{mode}", "T2 cooldown", f"no {mode} entry for {mins} min after a loss", cooldown_min_after_loss=mins, cooldown_mode=mode)
    for nb in (1, 2, 3, 5, 10):
        run(f"cool_{nb}bars", "T2 cooldown", f"no entry for {nb} closed M3 bars after a loss", cooldown_bars_after_loss=nb)
    for x in (0.5, 1.0, 2.0):
        run(f"reentry_dist>={x}atr", "T2 cooldown", f"|price - last exit| >= {x} x ATR", reentry_atr_mult=x)
    for n in (3, 5, 10, 20):
        run(f"opp_signal_age>={n}", "T2 cooldown", f"previous opposite signal at least {n} bars old (signal reset)", mask=((sig.opp_ago < 0) | (sig.opp_ago >= n)).to_numpy())

    # ------------------------------------------------------------------ TEST 3: chop / regime
    for N, X in ((10, 1), (10, 2), (10, 3), (20, 2), (20, 3), (20, 4), (30, 4), (30, 6)):
        run(f"flips_{N}<={X}", "T3/T4 chop", f"at most {X} other flips in the last {N} bars", mask=(sig[f"flips_{N}"] <= X).to_numpy())
    for lo in (0.7, 0.9, 1.1):
        run(f"atr_ratio>={lo}", "T3 chop", f"ATR >= {lo} x its 30-day median", mask=(sig.atr_ratio >= lo).to_numpy())
    for hi in (1.5, 2.0):
        run(f"atr_ratio<={hi}", "T3 chop", f"ATR <= {hi} x its 30-day median", mask=(sig.atr_ratio <= hi).to_numpy())
    for a in (25, 30):
        run(f"adx>{a}", "T3 chop", f"ADX > {a}", mask=(sig.adx > a).to_numpy())
    run("adx_rising", "T3 chop", "ADX higher than 5 bars ago", mask=(sig.adx_slope > 0).to_numpy())
    for x in (1.0, 1.5):
        run(f"bbw_atr>={x}", "T3 chop", f"Bollinger width >= {x} x ATR", mask=(sig.bbw_atr >= x).to_numpy())
    for x in (2, 3):
        run(f"opp_candles5<={x}", "T3 chop", f"at most {x} of the last 5 candles against the signal", mask=(sig.opp_candles5 <= x).to_numpy())
    for x in (1.0, 2.0):
        run(f"dist_prev_sig>={x}", "T4 chop", f"price >= {x} x ATR from the previous signal", mask=(sig.dist_prev_sig >= x).to_numpy())

    # ------------------------------------------------------------------ TEST 4: volatility-aware stop
    for k in (1.0, 1.5, 2.0, 3.0):
        run(f"stop_atr{k}", "T5 stop", f"SL = {k} x ATR from the signal close", initial_sl="atr", atr_stop_mult=k)
    for fl, cap in ((0.75, 3.0), (1.0, 3.0), (1.0, 4.0), (1.5, 4.0)):
        run(f"stop_hybrid{fl}_cap{cap}", "T5 stop", f"SL = max(structure, {fl} x ATR), skip if > {cap} x ATR", initial_sl="hybrid", atr_stop_mult=fl, atr_stop_cap=cap)
    for cap in (2.0, 3.0, 4.0):
        run(f"stop_pivot_cap{cap}", "T5 stop", f"shipped stop, skip if > {cap} x ATR", atr_stop_cap=cap)
    run("stop_purple", "T5 stop", "SL = purple line from the first tick", initial_sl="purple")

    # ------------------------------------------------------------------ TEST 5: opposite signal models
    run("rev_reverse", "T10 reversal", "close AND reverse on the opposite signal (your tester setting)", close_on_opposite=True, reverse_on_opposite=True)
    run("rev_modelA_close", "T10 reversal", "Model A: close on the opposite signal, never reverse", close_on_opposite=True)
    for n in (1, 2, 3):
        run(f"rev_modelB_confirm{n}", "T10 reversal", f"Model B: close only if the opposite direction persists {n} bars", close_on_opposite=True, opposite_confirm_bars=n)
    for a in (25, 30):
        run(f"rev_modelD_adx{a}", "T10 reversal", f"Model D: close only if the opposite signal's ADX > {a}", close_on_opposite=True, opposite_min_adx=a)

    # ------------------------------------------------------------------ TEST 7: HTF
    run("htf15", "T9 HTF", "M15 Supertrend direction agrees", mask=sig.htf15_aligned.to_numpy())
    run("htf60", "T9 HTF", "H1 Supertrend direction agrees", mask=sig.htf60_aligned.to_numpy())
    run("htf15_and_60", "T9 HTF", "M15 and H1 agree", mask=(sig.htf15_aligned & sig.htf60_aligned).to_numpy())
    run("ema50_m15", "T9 HTF", "M15 EMA50 slope agrees", mask=sig.ema15_aligned.to_numpy())
    run("htf15_conflict", "T9 HTF", "ONLY trades where M15 disagrees (control)", mask=(~sig.htf15_aligned).to_numpy())

    # ------------------------------------------------------------------ TEST 7b: overextension
    for x in (2.0, 3.0):
        run(f"range_ratio<={x}", "T7 overext", f"signal bar range <= {x} x ATR", mask=(sig.range_ratio <= x).to_numpy())
    for x in (2.0, 3.0):
        run(f"dist_ema<={x}", "T7 overext", f"|close - EMA20| <= {x} x ATR", mask=(sig.dist_ema <= x).to_numpy())

    # ------------------------------------------------------------------ TEST 9: trailing / BE / time exit
    for r in (0.25, 0.5, 0.75, 1.0, 1.25):
        run(f"trail_at{r}R", "T12 trailing", f"purple trail from +{r}R (instead of +360 pts)", trail_activation_r=r)
    for r in (0.5, 0.75, 1.0):
        run(f"be_at{r}R", "T12 trailing", f"break-even + costs at +{r}R", breakeven_r=r)
    for ra, rl in ((1.0, 0.25), (1.5, 0.5), (2.0, 0.5)):
        run(f"lock_{ra}R_keep{rl}R", "T13 protection", f"at +{ra}R lock +{rl}R and trail 1:1 with a {ra-rl}R gap", lock_activation_r=ra, lock_level_r=rl, one_to_one_gap_r=ra - rl)
    for mins, r in ((15, 0.0), (30, 0.0), (60, 0.0), (30, 0.25), (60, 0.25)):
        run(f"timeexit_{mins}m_below{r}R", "T14 time exit", f"close after {mins} min if profit < {r}R", time_exit_min=mins, time_exit_below_r=r)

    # ------------------------------------------------------------------ TEST 15: sessions (server time)
    SESS = {"asia_02-10": (2, 10), "london_10-15": (10, 15), "overlap_15-20": (15, 20), "ny_20-24": (20, 24), "london+ny_10-20": (10, 20)}
    for name, hrs in SESS.items():
        run(f"session_{name}", "T15 session", f"entries only {hrs[0]:02d}:00-{hrs[1]:02d}:00 server time", entry_hours=hrs)

else:
    RUNS.update(pd.read_pickle("results/lab/runs.pkl")); META.update(json.load(open("results/lab/meta.json")))
if not SKIP:
    json.dump(META, open("results/lab/meta.json", "w"), indent=1)
    pd.to_pickle(RUNS, "results/lab/runs.pkl")
    print(f"single-filter runs done: {len(RUNS)} ({time.time()-T0:.0f}s)", flush=True)
