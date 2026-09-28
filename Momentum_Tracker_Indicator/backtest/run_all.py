"""Runs every bot x timeframe x window and writes results/trades_*.csv + results/summary.json.

usage: python run_all.py [--quick]      (--quick skips the fix-candidate variants)
"""
import json, os, sys, time
import numpy as np
import pandas as pd
import twk_engine as E

os.makedirs("results", exist_ok=True)
QUICK = "--quick" in sys.argv
t0 = time.time()
m1 = E.load_duka("data/duka_chunks/bid_*.csv")


def eu_dst(ts: pd.Series) -> np.ndarray:
    """True where EU summer time applies (last Sunday of March -> last Sunday of October, 01:00 UTC)."""
    y = ts.dt.year
    out = np.zeros(len(ts), bool)
    for yy in y.unique():
        mar = pd.Timestamp(yy, 3, 31)
        mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
        octo = pd.Timestamp(yy, 10, 31)
        octo -= pd.Timedelta(days=(octo.weekday() + 1) % 7)
        m = (y == yy).to_numpy()
        out[m] = ((ts[m] >= mar + pd.Timedelta(hours=1)) & (ts[m] < octo + pd.Timedelta(hours=1))).to_numpy()
    return out


# Dukascopy is UTC; XM server time is EET (UTC+2, UTC+3 in EU summer time)
m1["time"] = m1["time"] + pd.to_timedelta(np.where(eu_dst(m1["time"]), 3, 2), unit="h")
m1 = m1.drop_duplicates("time").sort_values("time").reset_index(drop=True)
years = m1["time"].dt.year.to_numpy()
spread = np.array([E.year_spread_model()[y] for y in years], float)
m1.to_csv("data/XAUUSD_M1_servertime.csv.gz", index=False, compression="gzip")
print(f"M1 bars {len(m1)}  {m1.time.iloc[0]} .. {m1.time.iloc[-1]}  ({time.time()-t0:.0f}s)", flush=True)

p = E.CoreParams()
m3 = E.resample(m1, 3)
END = pd.Timestamp("2026-09-25 00:00")
WINDOWS = {"6m": (END - pd.DateOffset(months=6), END), "5y": (END - pd.DateOffset(years=5), END)}
TFS = [1, 5, 15]

# vol-adaptive scale: lagged 30-day median of the daily-median M1 ATR(10), relative to the Sep-2026 level
atr_m1 = E.rma(E.true_range(m1["high"].to_numpy(float), m1["low"].to_numpy(float), m1["close"].to_numpy(float), True), 10)
daily = pd.Series(atr_m1, index=m1["time"]).resample("1D").median().dropna()
roll = daily.rolling(30, min_periods=10).median().shift(1)
ref = daily[daily.index >= "2026-08-25"].median()
scale_daily = (roll / ref).clip(lower=0.15, upper=3.0).ffill().bfill()
vol_scale = scale_daily.reindex(m1["time"].dt.floor("D")).ffill().bfill().to_numpy()

series_cache = {}


def get_series(tf, reflip_bars):
    key = (tf, reflip_bars)
    if key not in series_cache:
        bars = E.resample(m1, tf)
        ser = E.compute_series(bars, p)
        sig = E.signal_table(bars, ser, tf, m1, m3, p, reflip_bars)
        series_cache[key] = (bars, ser, sig)
    return series_cache[key]


def reflip_bars_for(tf, minutes):
    return max(1, round(minutes * 60 / (tf * 60))) if minutes > 0 else 0


BOTS = {
    "PineEA": lambda: E.PineEAParams(),
    "MomentumEA": lambda: E.MomentumEAParams(),
}
VARIANTS = {  # fix candidates, 5y window only
    "MomentumEA_volscaled": lambda: E.MomentumEAParams(name="MomentumEA_volscaled", vol_scale=True),
    "MomentumEA_ratio1.5": lambda: E.MomentumEAParams(name="MomentumEA_ratio1.5", min_volume_ratio=1.5),
    "MomentumEA_session15-20": lambda: E.MomentumEAParams(name="MomentumEA_session15-20", entry_hours=(15, 20)),
    "MomentumEA_reverse": lambda: E.MomentumEAParams(name="MomentumEA_reverse", close_on_opposite=True, reverse_on_opposite=True),
    "MomentumEA_nofilters": lambda: E.MomentumEAParams(name="MomentumEA_nofilters", min_volume_ratio=0.0001, require_m1_box=False, require_m3_box=False, adx_min=-1),
    "MomentumEA_worstpath": lambda: E.MomentumEAParams(name="MomentumEA_worstpath", trail_mode="worst"),
    "MomentumEA_volscaled_worst": lambda: E.MomentumEAParams(name="MomentumEA_volscaled_worst", vol_scale=True, trail_mode="worst"),
    "PineEA_noreverse": lambda: E.PineEAParams(name="PineEA_noreverse", reverse_on_flip=False),
    "PineStrategy_pure": lambda: E.PineEAParams(name="PineStrategy_pure", reverse_on_flip=False, purple_trail=False, lock_trigger_pts=0),
    "PineEA_session15-20": lambda: E.PineEAParams(name="PineEA_session15-20", entry_hours=(15, 20)),
}

summary = []


def run(label, win, tf, bot):
    t1 = time.time()
    rb = reflip_bars_for(tf, bot.reflip_minutes) if isinstance(bot, E.MomentumEAParams) else 0
    bars, ser, sig = get_series(tf, rb)
    a, b = WINDOWS[win]
    tr = E.simulate(m1, sig, ser, tf, bot, spread, int(a.timestamp()), int(b.timestamp()), vol_scale_arr=vol_scale)
    fn = f"results/trades_{label}_M{tf}_{win}.csv"
    tr.to_csv(fn, index=False)
    m = E.metrics(tr)
    n_sig = int(((sig.close_time >= a.timestamp()) & (sig.close_time < b.timestamp())).sum())
    row = dict(bot=label, tf=tf, window=win, signals=n_sig, file=fn, **m)
    if len(tr):
        tr["year"] = tr["entry_time"].dt.year
        row["by_year"] = {int(y): dict(trades=int(len(g)), net=round(float(g.pnl.sum()), 2),
                                        pf=round(float(g.pnl[g.pnl > 0].sum() / max(1e-9, -g.pnl[g.pnl < 0].sum())), 2),
                                        win=round(float((g.pnl > 0).mean()), 3), avg_r=round(float(g.r_multiple.mean()), 3),
                                        med_risk=round(float(g.risk.median()), 2))
                          for y, g in tr.groupby("year")}
        tr["half"] = tr["entry_time"].dt.year.astype(str) + "H" + ((tr["entry_time"].dt.month > 6).astype(int) + 1).astype(str)
        row["by_half"] = {h: round(float(g.pnl.sum()), 2) for h, g in tr.groupby("half")}
        tr["hour"] = tr["entry_time"].dt.hour
        row["by_hour"] = {int(h): round(float(g.pnl.sum()), 2) for h, g in tr.groupby("hour")}
        step = max(1, len(tr) // 400)
        row["equity"] = [round(float(x), 2) for x in tr.pnl.cumsum().to_numpy()[::step]]
        row["equity_time"] = [str(x)[:10] for x in tr.exit_time.to_numpy()[::step]]
    summary.append(row)
    print(f"{label:26s} M{tf:<2d} {win}: sig={n_sig:6d} trades={m.get('trades',0):5d} net=${m.get('net',0):9.2f} "
          f"PF={m.get('profit_factor',0):.2f} win={m.get('win_rate',0)*100:4.0f}% avgR={m.get('avg_r',float('nan')):.2f} "
          f"maxDD=${m.get('max_dd',0):.0f} medRisk=${m.get('median_risk_px',0):.2f} ({time.time()-t1:.0f}s)", flush=True)


for win in ("6m", "5y"):
    for tf in TFS:
        for label, mk in BOTS.items():
            run(label, win, tf, mk())
if not QUICK:
    for tf in TFS:
        for label, mk in VARIANTS.items():
            run(label, "5y", tf, mk())

reg = []
for y, g in m1.groupby(m1["time"].dt.year):
    a = pd.Series(atr_m1[g.index])
    reg.append(dict(year=int(y), bars=int(len(g)), median_close=round(float(g.close.median()), 0),
                    m1_atr10_median=round(float(a.median()), 3), m1_range_median=round(float((g.high - g.low).median()), 3),
                    spread_pts=E.year_spread_model()[int(y)], atr_pts=round(float(a.median()) / 0.01)))
json.dump(dict(runs=summary, regime=reg, generated=str(pd.Timestamp.now())[:16],
               data=dict(bars=int(len(m1)), start=str(m1.time.iloc[0]), end=str(m1.time.iloc[-1]))),
          open("results/summary.json", "w"), indent=1, default=float)
print("regime:", reg)
print(f"done in {time.time()-t0:.0f}s")
