"""Data pipeline for the PBD counter-trend study on XAUUSD.

Sources
-------
* Dukascopy M1 BID bars with Dukascopy traded volume (UTC), monthly CSV chunks.
  Volume = volume matched on Dukascopy's own ECN.  It is NOT COMEX futures volume and
  it is NOT a footprint (no bid/ask split).  Treated as "real volume from one venue".
* XM GOLD M15 bars (broker server time = Europe/Athens) with per-bar spread in points
  (1 pt = 0.01 USD) and MT5 tick volume.  Used for spread and for the tick-volume
  sensitivity variant of the weekly value area.
"""
import glob
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUKA_GLOB = "D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_*.csv"
XM_M15 = "D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/xm_GOLD_M15.csv.gz"
CACHE = os.path.join(ROOT, "data")

# Chronological split (pre-registered before any result was looked at)
SPLITS = [("DEV", "2021-09-01", "2024-01-01"),
          ("VAL", "2024-01-01", "2025-04-01"),
          ("OOS", "2025-04-01", "2026-10-01")]

# FOMC decision days (statement 14:00 ET).  From the Fed's published calendars.
FOMC_DAYS = """2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16""".split()


def period_of(times: pd.Series) -> pd.Series:
    out = pd.Series(["NONE"] * len(times), index=times.index, dtype=object)
    for name, a, b in SPLITS:
        m = (times >= pd.Timestamp(a)) & (times < pd.Timestamp(b))
        out[m] = name
    return out


# ----------------------------------------------------------------------------- loading
def load_duka_m1() -> pd.DataFrame:
    parts = []
    for f in sorted(glob.glob(DUKA_GLOB)):
        d = pd.read_csv(f)
        if len(d):
            parts.append(d)
    df = pd.concat(parts, ignore_index=True).rename(columns={"timestamp": "t"})
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    df = df[(df["volume"] > 0) | (df["high"] > df["low"])].reset_index(drop=True)
    return df[["time", "open", "high", "low", "close", "volume"]]


def resample(m1: pd.DataFrame, minutes: int = 15) -> pd.DataFrame:
    secs = m1["time"].astype("int64") // 10**9
    key = (secs // (minutes * 60)) * (minutes * 60)
    g = m1.groupby(key, sort=True)
    out = pd.DataFrame({
        "time": pd.to_datetime(g["time"].first().index, unit="s"),
        "open": g["open"].first().values,
        "high": g["high"].max().values,
        "low": g["low"].min().values,
        "close": g["close"].last().values,
        "volume": g["volume"].sum().values,
        "n_m1": g["close"].size().values,
    })
    # index of the first M1 bar of each M15 bar and of the first M1 bar AFTER the M15 bar
    starts = np.searchsorted(m1["time"].values, out["time"].values, side="left")
    ends = np.searchsorted(m1["time"].values, (out["time"] + pd.Timedelta(minutes=minutes)).values, side="left")
    out["m1_start"] = starts
    out["m1_next"] = ends
    return out


def load_xm_m15_utc() -> pd.DataFrame:
    xm = pd.read_csv(XM_M15)
    t = pd.to_datetime(xm["time"]).dt.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="NaT")
    xm["time"] = t.dt.tz_convert("UTC").dt.tz_localize(None)
    xm = xm.dropna(subset=["time"]).sort_values("time")
    xm["spread_usd"] = xm["spread"] * 0.01
    return xm[["time", "spread_usd", "tick_volume", "open", "high", "low", "close"]].rename(
        columns={"open": "xm_open", "high": "xm_high", "low": "xm_low", "close": "xm_close"})


def attach_spread(m15: pd.DataFrame, xm: pd.DataFrame) -> pd.DataFrame:
    """Per-bar XM spread (USD).  Missing bars: monthly median; before XM history: median of
    the first three XM months (Jul-Sep 2022, 0.25 USD)."""
    df = pd.merge_asof(m15.sort_values("time"), xm[["time", "spread_usd", "tick_volume"]].sort_values("time"),
                       on="time", direction="nearest", tolerance=pd.Timedelta(minutes=15))
    month = df["time"].dt.to_period("M")
    med = df.groupby(month)["spread_usd"].median()
    first_med = xm.loc[xm["time"] < "2022-10-01", "spread_usd"].median()
    fill = month.map(med).fillna(first_med)
    df["spread_filled"] = df["spread_usd"].isna()
    df["spread_usd"] = df["spread_usd"].fillna(fill)
    df["tick_volume"] = df["tick_volume"].fillna(0.0)
    return df


# ----------------------------------------------------------------------------- indicators
def atr_wilder(h, l, c, n=14):
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) < n:
        return out
    a = tr[:n].mean()
    out[n - 1] = a
    k = 1.0 / n
    for i in range(n, len(tr)):
        a = a + k * (tr[i] - a)
        out[i] = a
    return out


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["atr14"] = atr_wilder(df["high"], df["low"], df["close"], 14)
    # daily-ish ATR reference: 96 bars = 1 day of M15
    df["atr96"] = atr_wilder(df["high"], df["low"], df["close"], 96)
    df["range"] = df["high"] - df["low"]
    # ATR percentile over trailing 60 trading days (5760 bars)
    a = df["atr14"]
    df["atr_pct60d"] = a.rolling(5760, min_periods=960).rank(pct=True)
    df["vol_avg20"] = df["volume"].rolling(20, min_periods=5).mean()
    df["vol_rel"] = df["volume"] / df["vol_avg20"]
    return df


# ----------------------------------------------------------------------------- calendar
def add_sessions(df: pd.DataFrame) -> pd.DataFrame:
    t = df["time"].dt.tz_localize("UTC")
    lon = t.dt.tz_convert("Europe/London")
    ny = t.dt.tz_convert("America/New_York")
    tok = t.dt.tz_convert("Asia/Tokyo")
    lon_h = lon.dt.hour + lon.dt.minute / 60
    ny_h = ny.dt.hour + ny.dt.minute / 60
    tok_h = tok.dt.hour + tok.dt.minute / 60
    in_lon = (lon_h >= 8) & (lon_h < 16.5)
    in_ny = (ny_h >= 8) & (ny_h < 17)
    in_tok = (tok_h >= 9) & (tok_h < 17)
    s = np.where(in_lon & in_ny, "overlap",
        np.where(in_lon, "london",
        np.where(in_ny, "newyork",
        np.where(in_tok, "asia", "offhours"))))
    df["session"] = s
    df["ny_hour"] = ny_h.values
    df["ny_date"] = ny.dt.strftime("%Y-%m-%d").values
    df["dow"] = df["time"].dt.dayofweek
    # Gold trading week: Sunday 21:00 UTC -> next Sunday 21:00 UTC.  Shift by +3h so the
    # week key is the Monday 00:00 of the shifted clock.
    sh = df["time"] + pd.Timedelta(hours=3)
    df["week"] = (sh - pd.to_timedelta(sh.dt.dayofweek, unit="D")).dt.normalize()
    # ---- news proxy (no calendar file available offline).
    # 08:30 ET slot on weekdays (NFP, CPI, PPI, retail sales, GDP, jobless claims),
    # 10:00 ET slot (ISM, UMich, home sales), FOMC 14:00 ET on decision days.
    wd = ny.dt.dayofweek < 5
    slot0830 = wd & (ny_h >= 8.25) & (ny_h < 9.25)
    slot1000 = wd & (ny_h >= 9.75) & (ny_h < 10.75)
    fomc = df["ny_date"].isin(FOMC_DAYS) & (ny_h >= 13.75) & (ny_h < 15.5)
    df["news_slot"] = np.where(fomc, "fomc", np.where(slot0830, "us0830", np.where(slot1000, "us1000", "")))
    df["news"] = df["news_slot"] != ""
    # shock bar: realised range > 3x ATR (ex-post label for loss analysis only)
    df["shock"] = df["range"] > 3.0 * df["atr14"].shift(1)
    return df


# ----------------------------------------------------------------------------- build
def build(force: bool = False):
    os.makedirs(CACHE, exist_ok=True)
    fm1 = os.path.join(CACHE, "m1.pkl")
    fm15 = os.path.join(CACHE, "m15.pkl")
    if not force and os.path.exists(fm1) and os.path.exists(fm15):
        return pd.read_pickle(fm1), pd.read_pickle(fm15)
    m1 = load_duka_m1()
    m15 = resample(m1, 15)
    xm = load_xm_m15_utc()
    m15 = attach_spread(m15, xm)
    m15 = add_indicators(m15)
    m15 = add_sessions(m15)
    m15["period"] = period_of(m15["time"])
    m1.to_pickle(fm1)
    m15.to_pickle(fm15)
    return m1, m15


if __name__ == "__main__":
    import time as _t
    t0 = _t.time()
    m1, m15 = build(force=True)
    print("M1 bars", len(m1), m1["time"].min(), "->", m1["time"].max())
    print("M15 bars", len(m15))
    print(m15[["time", "open", "high", "low", "close", "volume", "spread_usd", "atr14", "session", "week", "period"]].tail(3))
    print("spread filled share", m15["spread_filled"].mean().round(3))
    print("session counts", m15["session"].value_counts().to_dict())
    print("period counts", m15["period"].value_counts().to_dict())
    print("news share", m15["news"].mean().round(3))
    print("months present:", m15["time"].dt.to_period("M").nunique())
    print("%.1fs" % (_t.time() - t0))
