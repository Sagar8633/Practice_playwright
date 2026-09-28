"""TWK backtest engine: exact port of TWK_Core.mqh signal maths + bar-by-bar simulation of the two EAs.

Data model
  * All bars are BID bars (as MT5 stores them). Ask = bid + spread.
  * Signals are computed on the signal timeframe (M1/M5/M15). Trade management (SL/TP hits,
    trailing) is simulated on M1 bars, which is the finest resolution we have without ticks.
  * Inside one M1 bar the order of events is unknown, so the conservative rule is used:
    a stop-loss hit is checked before a take-profit hit. Ambiguous bars are counted.
  * Trailing stops move at the END of each M1 bar using the bar's extreme (high for a buy) for
    "profit reached" checks. If a freshly trailed stop is above the bar close (buy), the price
    retreated through it inside the bar, and the trade exits at that stop.

Money
  * GOLD on XM: digits 2, point 0.01, contract 100 -> 0.01 lot = 1 oz = $1 per $1.00 move.
  * Swap: XM GOLD swap_long -86.84 pts, swap_short +19.79 pts per night, x3 on Wednesday.
"""
from __future__ import annotations

import glob
import json
import math
import os
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

NAN = float("nan")

# --------------------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------------------

def load_duka(chunk_glob: str) -> pd.DataFrame:
    """Dukascopy monthly CSVs (timestamp ms UTC, open, high, low, close, volume) -> M1 bid bars.
    Prices are rounded to 2 decimals to match XM's 0.01 point."""
    parts = []
    for f in sorted(glob.glob(chunk_glob)):
        d = pd.read_csv(f)
        if len(d):
            parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df = df.rename(columns={"timestamp": "t"})
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].round(2)
    # drop zero-range zero-volume flats that survive (weekend prints)
    df = df[(df["volume"] > 0) | (df["high"] > df["low"])].reset_index(drop=True)
    df["tick_volume"] = df["volume"]
    return df[["time", "open", "high", "low", "close", "tick_volume"]]


def load_xm(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]


def resample(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """MT5-style bars: bar time = floor(time / minutes). Volume = sum of tick volume."""
    if minutes == 1:
        return m1.reset_index(drop=True)
    secs = m1["time"].astype("int64") // 10**9
    key = (secs // (minutes * 60)) * (minutes * 60)
    g = m1.groupby(key, sort=True)
    out = pd.DataFrame({
        "time": pd.to_datetime(g["time"].first().index, unit="s"),
        "open": g["open"].first().values,
        "high": g["high"].max().values,
        "low": g["low"].min().values,
        "close": g["close"].last().values,
        "tick_volume": g["tick_volume"].sum().values,
    })
    if "spread" in m1.columns:
        out["spread"] = g["spread"].last().values
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Pine primitives (vectorised; identical results to TWK_Core.mqh)
# --------------------------------------------------------------------------------------

def rma(src: np.ndarray, n: int) -> np.ndarray:
    """ta.rma: SMA seed on the first full window of valid values, then alpha=1/n recursion."""
    s = pd.Series(src)
    sma = s.rolling(n, min_periods=n).mean().to_numpy()
    out = np.full(len(src), NAN)
    valid = np.where(~np.isnan(sma))[0]
    if len(valid) == 0:
        return out
    f = valid[0]
    x = src[f:].astype(float).copy()
    x[0] = sma[f]
    out[f:] = pd.Series(x).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()
    return out


def true_range(h, l, c, handle_na: bool) -> np.ndarray:
    n = len(c)
    tr = np.empty(n)
    pc = np.roll(c, 1)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - pc[1:]), np.abs(l[1:] - pc[1:])))
    tr[0] = (h[0] - l[0]) if handle_na else NAN
    return tr


def supertrend(h, l, c, factor: float, atr_len: int):
    """TradingView ta.supertrend. dir -1 = uptrend (line below price), +1 = downtrend."""
    atr = rma(true_range(h, l, c, True), atr_len)
    n = len(c)
    st = np.full(n, NAN)
    d_ = np.ones(n, dtype=np.int8)
    hl2 = ((h + l) / 2.0).tolist()
    atr_l = atr.tolist()
    c_l = c.tolist()
    lower_prev = upper_prev = NAN
    prev_st = NAN
    for i in range(n):
        a = atr_l[i]
        upper = lower = NAN
        if not math.isnan(a):
            src = hl2[i]
            upper = src + factor * a
            lower = src - factor * a
            pl = 0.0 if math.isnan(lower_prev) else lower_prev
            pu = 0.0 if math.isnan(upper_prev) else upper_prev
            if i > 0:
                c1 = c_l[i - 1]
                lower = lower if (lower > pl or c1 < pl) else pl
                upper = upper if (upper < pu or c1 > pu) else pu
            else:
                lower = lower if lower > pl else pl
                upper = upper if upper < pu else pu
        atr_prev_na = (i == 0) or math.isnan(atr_l[i - 1])
        if atr_prev_na:
            d = 1
        elif (not math.isnan(prev_st)) and prev_st == upper_prev:
            d = -1 if c_l[i] > upper else 1
        else:
            d = 1 if c_l[i] < lower else -1
        d_[i] = d
        cur = NAN if math.isnan(a) else (lower if d == -1 else upper)
        st[i] = cur
        prev_st = cur
        lower_prev, upper_prev = lower, upper
    return st, d_


def pivots(h, l, L: int, R: int):
    """ta.pivothigh/pivotlow with TWK_TIE_LEFT_EQUAL_OK. Returns (confirmed-at-index arrays):
    lastPL[i], lastPH[i] = value of the latest pivot confirmed at or before bar i (nan if none),
    plBar[i], phBar[i]   = bar index the pivot sits on (-1 if none)."""
    n = len(h)
    lastPL = np.full(n, NAN); lastPH = np.full(n, NAN)
    plBar = np.full(n, -1, dtype=np.int64); phBar = np.full(n, -1, dtype=np.int64)
    if n < L + R + 1:
        return lastPL, lastPH, plBar, phBar
    # candidate c in [L, n-1-R]
    lw = sliding_window_view(l, L)      # lw[j] = l[j..j+L-1]
    hw = sliding_window_view(h, L)
    rw_l = sliding_window_view(l, R)
    rw_h = sliding_window_view(h, R)
    cs = np.arange(L, n - R)
    left_min = lw[cs - L].min(axis=1); right_min = rw_l[cs + 1].min(axis=1)
    left_max = hw[cs - L].max(axis=1); right_max = rw_h[cs + 1].max(axis=1)
    is_pl = (left_min >= l[cs]) & (right_min > l[cs])
    is_ph = (left_max <= h[cs]) & (right_max < h[cs])
    conf = cs + R
    idx_pl = np.full(n, -1, dtype=np.int64); idx_ph = np.full(n, -1, dtype=np.int64)
    idx_pl[conf[is_pl]] = cs[is_pl]
    idx_ph[conf[is_ph]] = cs[is_ph]
    plBar = np.maximum.accumulate(idx_pl)
    phBar = np.maximum.accumulate(idx_ph)
    m = plBar >= 0
    lastPL[m] = l[plBar[m]]
    m = phBar >= 0
    lastPH[m] = h[phBar[m]]
    return lastPL, lastPH, plBar, phBar


def up_down_volume(o, c, v, length: int):
    up = np.where(c > o, v, 0.0); dn = np.where(c < o, v, 0.0)
    cu = np.concatenate([[0.0], np.cumsum(up)]); cd = np.concatenate([[0.0], np.cumsum(dn)])
    n = len(c)
    bv = np.full(n, NAN); sv = np.full(n, NAN)
    i = np.arange(length - 1, n)
    bv[i] = cu[i + 1] - cu[i + 1 - length]
    sv[i] = cd[i + 1] - cd[i + 1 - length]
    return bv, sv


def dmi(h, l, c, di_len: int, adx_len: int):
    n = len(c)
    up = np.empty(n); down = np.empty(n)
    up[0] = down[0] = NAN
    up[1:] = h[1:] - h[:-1]; down[1:] = l[:-1] - l[1:]
    pdm = np.where((up > down) & (up > 0), up, 0.0); pdm[0] = NAN
    mdm = np.where((down > up) & (down > 0), down, 0.0); mdm[0] = NAN
    trur = rma(true_range(h, l, c, False), di_len)
    rp = rma(pdm, di_len); rm = rma(mdm, di_len)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus = np.where((~np.isnan(trur)) & (trur != 0), 100.0 * rp / trur, NAN)
        minus = np.where((~np.isnan(trur)) & (trur != 0), 100.0 * rm / trur, NAN)
    plus = pd.Series(plus).ffill().to_numpy(); minus = pd.Series(minus).ffill().to_numpy()
    s = plus + minus
    dx = np.where(np.isnan(plus) | np.isnan(minus), NAN, np.abs(plus - minus) / np.where(s == 0, 1.0, s))
    adx = 100.0 * rma(dx, adx_len)
    return plus, minus, adx


# --------------------------------------------------------------------------------------
# Signal series on the signal timeframe
# --------------------------------------------------------------------------------------

@dataclass
class CoreParams:
    st_mult: float = 1.5
    st_atr: int = 10
    piv_len: int = 5
    rr: float = 2.0
    vol_len: int = 20
    di_len: int = 14
    adx_smooth: int = 14


def compute_series(bars: pd.DataFrame, p: CoreParams) -> dict:
    o = bars["open"].to_numpy(float); h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    v = bars["tick_volume"].to_numpy(float)
    st, d = supertrend(h, l, c, p.st_mult, p.st_atr)
    lastPL, lastPH, plBar, phBar = pivots(h, l, p.piv_len, p.piv_len)
    bv, sv = up_down_volume(o, c, v, p.vol_len)
    plus, minus, adx = dmi(h, l, c, p.di_len, p.adx_smooth)
    d32 = d.astype(np.int32)
    long_sig = np.zeros(len(c), bool); short_sig = np.zeros(len(c), bool)
    long_sig[1:] = (d32[1:] < 0) & (d32[:-1] >= 0)
    short_sig[1:] = (d32[1:] > 0) & (d32[:-1] <= 0)
    atr = rma(true_range(h, l, c, True), p.st_atr)
    return dict(st=st, dir=d32, lastPL=lastPL, lastPH=lastPH, plBar=plBar, phBar=phBar,
                bv=bv, sv=sv, adx=adx, long=long_sig, short=short_sig, atr=atr,
                o=o, h=h, l=l, c=c, time=bars["time"].to_numpy())


def signal_table(tf_bars: pd.DataFrame, series: dict, tf_minutes: int, m1_bars: pd.DataFrame,
                 m3_bars: pd.DataFrame, p: CoreParams, reflip_bars: int) -> pd.DataFrame:
    """One row per LONG/SHORT signal bar with everything both EAs read from the Tracker."""
    idx = np.where(series["long"] | series["short"])[0]
    tf_sec = tf_minutes * 60
    t_open = (tf_bars["time"].astype("int64") // 10**9).to_numpy()
    close_t = t_open[idx] + tf_sec
    # M1 row = last completed M1 bar at the signal close (the M1 bar opening at close-60, or earlier)
    m1_t = (m1_bars["time"].astype("int64") // 10**9).to_numpy()
    if tf_minutes == 1:
        bv1 = series["bv"][idx]; sv1 = series["sv"][idx]
    else:
        m1s = compute_m1_rows(m1_bars, p)
        k1 = np.searchsorted(m1_t + 60, close_t, side="right") - 1
        bv1 = np.where(k1 >= 0, m1s[0][np.maximum(k1, 0)], NAN)
        sv1 = np.where(k1 >= 0, m1s[1][np.maximum(k1, 0)], NAN)
    m3_t = (m3_bars["time"].astype("int64") // 10**9).to_numpy()
    b3, s3 = up_down_volume(m3_bars["open"].to_numpy(float), m3_bars["close"].to_numpy(float),
                            m3_bars["tick_volume"].to_numpy(float), p.vol_len)
    k3 = np.searchsorted(m3_t + 180, close_t, side="right") - 1
    bv3 = np.where(k3 >= 0, b3[np.maximum(k3, 0)], NAN)
    sv3 = np.where(k3 >= 0, s3[np.maximum(k3, 0)], NAN)

    rows = []
    last_long = last_short = -1
    for j, i in enumerate(idx):
        is_l = bool(series["long"][i])
        entry = series["c"][i]
        lpl, lph = series["lastPL"][i], series["lastPH"][i]
        piv_ok = (not math.isnan(lpl) and lpl < entry) if is_l else (not math.isnan(lph) and lph > entry)
        st = series["st"][i]
        sl = (lpl if is_l else lph) if piv_ok else st
        piv_bar = int(series["plBar"][i] if is_l else series["phBar"][i]) if piv_ok else -1
        opp = last_short if is_l else last_long
        opp_ago = (i - opp) if opp >= 0 else -1
        reflip = piv_ok and reflip_bars > 0 and opp >= 0 and (i - opp) <= reflip_bars and piv_bar < opp
        if is_l:
            last_long = i
        else:
            last_short = i
        risk = (entry - sl) if is_l else (sl - entry)
        tp = NAN
        if not math.isnan(sl) and risk > 0:
            tp = entry + p.rr * risk if is_l else entry - p.rr * risk
        rows.append(dict(bar=i, time=series["time"][i], close_time=close_t[j], side=1 if is_l else -1,
                         entry=entry, purple=st, sl=sl, tp=tp, risk=risk, sl_pivot=piv_ok, piv_bar=piv_bar,
                         reflip=bool(reflip), opp_ago=opp_ago, bv1=bv1[j], sv1=sv1[j], bv3=bv3[j], sv3=sv3[j],
                         adx=series["adx"][i], atr=series["atr"][i]))
    return pd.DataFrame(rows)


_m1_rows_cache: dict = {}


def compute_m1_rows(m1_bars: pd.DataFrame, p: CoreParams):
    key = (id(m1_bars), p.vol_len)
    if key not in _m1_rows_cache:
        _m1_rows_cache[key] = up_down_volume(m1_bars["open"].to_numpy(float), m1_bars["close"].to_numpy(float),
                                             m1_bars["tick_volume"].to_numpy(float), p.vol_len)
    return _m1_rows_cache[key]


# --------------------------------------------------------------------------------------
# EA parameter sets (defaults = the shipped GOLD presets)
# --------------------------------------------------------------------------------------

@dataclass
class PineEAParams:
    name: str = "PineEA"
    rr: float = 2.0
    reverse_on_flip: bool = True
    purple_trail: bool = True
    purple_start_pts: int = 0
    lock_trigger_pts: int = 1000
    lock_profit_pts: int = 900
    min_sl_step_pts: int = 5
    lots: float = 0.02
    entry_hours: tuple | None = None     # (start_hour, end_hour_exclusive) server time; None = always


@dataclass
class MomentumEAParams:
    name: str = "MomentumEA"
    rr: float = 2.0
    min_volume_ratio: float = 1.2        # live XM demo chart value (preset)
    require_m1_box: bool = True
    require_m3_box: bool = True
    adx_min: float = 20.0
    hard_sl_pts: dict = field(default_factory=lambda: {1: 500, 3: 0, 5: 0, 15: 0})
    reflip_action: str = "HARD_SL"       # HARD_SL / SKIP / KEEP_PIVOT / PURPLE
    reflip_minutes: int = 15
    purple_activation_pts: int = 200
    protection_activation_pts: int = 500
    lock_pts: int = 100
    one_to_one: bool = True
    min_improve_pts: int = 5
    one_position: bool = True
    close_on_opposite: bool = False
    reverse_on_opposite: bool = False
    stale_rule: bool = True
    lots: float = 0.02
    # scale every *point* distance by this per-signal factor (vol-adaptive variant); 1.0 = fixed
    vol_scale: bool = False
    entry_hours: tuple | None = None
    trail_mode: str = "path"             # "path" (extreme-first only on against-bars) or "worst" (any bar)
    # scenario options (2026-09-25 user request)
    initial_sl: str = "pivot"            # "pivot" (EA rule: pivot, hard SL, re-flip) or "purple" (purple line from the first tick)
    use_tp: bool = True                  # False = no take-profit, the trail is the only exit
    purple_trail_always: bool = False    # True = trail the purple line from bar 1 regardless of profit
    min_volume_ratio_m3: float = 0.0     # own/opposite ratio required on the M3 row too (0 = off)
    fixed_sl_pts: float = 0.0            # initial_sl "fixed": SL = fill -/+ this many points (no structure)
    tp_pts: float = 0.0                  # > 0: TP = fill +/- this many points (overrides rr x risk)
    # ---- filter lab (2026-09-25): every option off by default = shipped behaviour
    cooldown_min_after_loss: int = 0     # minutes without a new entry after a losing trade
    cooldown_bars_after_loss: int = 0    # signal-TF bars without a new entry after a losing trade
    cooldown_mode: str = "all"           # "all" | "same" | "opposite": which direction (vs the losing trade) is blocked
    reentry_atr_mult: float = 0.0        # no entry unless |price - last exit| >= mult x ATR(signal TF)
    atr_stop_mult: float = 0.0           # initial_sl "atr": SL = mult x ATR; "hybrid": max(structure, mult x ATR)
    atr_stop_cap: float = 0.0            # reject the trade if the stop distance > cap x ATR (0 = off)
    trail_activation_r: float = -1.0     # purple trail once profit >= r x initial risk (>= 0 overrides points)
    lock_activation_r: float = -1.0      # stage-2 (lock + 1:1) once profit >= r x initial risk
    lock_level_r: float = 0.0            # stage-2 lock at r x initial risk
    one_to_one_gap_r: float = 0.0        # 1:1 trail gap in R (0 = keep the points gap)
    breakeven_r: float = -1.0            # at profit >= r x risk move SL to entry +/- (spread + buffer)
    breakeven_buffer_pts: int = 0
    time_exit_min: int = 0               # close at bar close if the trade is older than this ...
    time_exit_below_r: float = 0.0       # ... and its open profit is below this many R
    opposite_confirm_bars: int = 0       # Model B: close on the opposite signal only if it persists N signal bars
    opposite_min_adx: float = 0.0        # Model D: close on the opposite signal only if ADX at that signal > this
    slippage_pts: float = 0.0            # adverse slippage on market fills and stop exits (not on TP limits)
    # ---- loss-prevention layer (2026-09-25): every option off by default
    max_spread_atr: float = 0.0          # NO_TRADE if spread / ATR > this
    max_cost_to_reward: float = 0.0      # NO_TRADE if spread / (RR x stop) > this
    vol_elevated_ratio: float = 0.0      # ATR ratio above this: risk budget x vol_elevated_risk_mult
    vol_elevated_risk_mult: float = 0.5
    vol_extreme_ratio: float = 0.0       # ATR ratio above this: NO_TRADE
    large_candle_lock: bool = False      # NO_TRADE while row["large_candle_lock"] is set (computed outside)
    min_signal_distance_atr: float = 0.0 # anti-flip: NO_TRADE if |close - previous signal close| < this x ATR
    entry_confirm_bars: int = 0          # anti-flip: enter only if the direction still holds N signal bars later
    chop_lock_score: int = 0             # NO_TRADE if row["chop_static"] + (last trade lost) >= this
    max_attempts_per_dir: int = 0        # after N consecutive losses in a direction, block it until a reset
    reset_atr: float = 1.0               # reset: a newer confirmed pivot AND a move >= this x ATR from the last losing entry
    lock2_activation_r: float = -1.0     # second protection stage (e.g. +1.5R -> lock +0.75R)
    lock2_level_r: float = 0.0
    health_exit_min: int = 0             # trade-health exit: age >= this AND profit < health_exit_below_r AND signal weakening
    health_exit_below_r: float = 0.0
    sizing: str = "fixed"                # "fixed" (lots) or "risk" (equity x risk_pct / stop)
    start_equity: float = 1000.0
    risk_pct: float = 0.5
    max_lot: float = 0.10
    max_stop_risk_pct: float = 2.0       # NO_TRADE if the minimum lot would risk more than this
    daily_loss_pct: float = 0.0          # no new trades for the day after this loss (0 = off)
    consec_reduce_at: int = 0            # halve the risk budget from this many consecutive losses
    consec_pause_at: int = 0             # pause pause_minutes from this many consecutive losses
    pause_minutes: int = 60
    consec_stop_day_at: int = 0          # stop for the day from this many consecutive losses


# --------------------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------------------

POINT = 0.01
SWAP_LONG_PTS = -86.84
SWAP_SHORT_PTS = 19.79
ROLLOVER_UTC_HOUR = 21           # XM server midnight (GMT+3) ~ 21:00 UTC in summer


def _swap_nights(t_in: int, t_out: int) -> float:
    """Number of swap charges between two UTC epoch seconds, Wednesday counted x3."""
    if t_out <= t_in:
        return 0.0
    first = (t_in // 86400) * 86400 + ROLLOVER_UTC_HOUR * 3600
    if first <= t_in:
        first += 86400
    n = 0.0
    t = first
    while t < t_out:
        wd = ((t // 86400) + 4) % 7       # 1970-01-01 was Thursday (=4 with Mon=0)
        n += 3.0 if wd == 2 else 1.0
        t += 86400
    return n


def simulate(m1: pd.DataFrame, sig: pd.DataFrame, series_for_mgmt: dict, tf_minutes: int,
             bot: PineEAParams | MomentumEAParams, spread_pts: np.ndarray, t_start: int, t_end: int,
             vol_scale_arr: np.ndarray | None = None) -> pd.DataFrame:
    """Bar-by-bar simulation on M1 bars between t_start and t_end (epoch s)."""
    is_pine = isinstance(bot, PineEAParams)
    t = (m1["time"].astype("int64") // 10**9).to_numpy()
    o = m1["open"].to_numpy(float).tolist(); h = m1["high"].to_numpy(float).tolist()
    l = m1["low"].to_numpy(float).tolist(); c = m1["close"].to_numpy(float).tolist()
    spr = (spread_pts * POINT).tolist()
    n = len(t)
    k0 = int(np.searchsorted(t, t_start)); k1 = int(np.searchsorted(t, t_end))
    tf_sec = tf_minutes * 60

    # signal -> M1 action index (first M1 bar at/after the signal close)
    sig = sig[(sig["close_time"] >= t_start) & (sig["close_time"] < t_end)]
    orig_index = sig.index.to_numpy()           # decisions are reported against the caller's signal-table index
    sig = sig.reset_index(drop=True)
    act = np.searchsorted(t, sig["close_time"].to_numpy(), side="left")
    sig_at = {}
    for j, k in enumerate(act):
        if k < n:
            sig_at.setdefault(int(k), []).append(j)
    sig_rows = sig.to_dict("records")

    # purple/dir of the last CLOSED signal bar as of each M1 bar's open
    tf_t = (series_for_mgmt["time"].astype("datetime64[s]").astype("int64"))
    tf_close = tf_t + tf_sec
    last_tf = np.searchsorted(tf_close, t, side="right") - 1
    st_arr = series_for_mgmt["st"]; dir_arr = series_for_mgmt["dir"]
    purple_now = np.where(last_tf >= 0, st_arr[np.maximum(last_tf, 0)], NAN).tolist()
    dir_now = np.where(last_tf >= 0, dir_arr[np.maximum(last_tf, 0)], 0).tolist()
    vs = vol_scale_arr.tolist() if vol_scale_arr is not None else None

    lots = bot.lots
    mult = lots * 100.0                      # $ per $1.00 price move
    trades = []
    pos = None                               # dict
    ambiguous = 0
    reflip_bars = 0
    if not is_pine:
        reflip_bars = max(1, round(bot.reflip_minutes * 60 / tf_sec)) if bot.reflip_minutes > 0 else 0
        hard_pts = bot.hard_sl_pts.get(tf_minutes, 0)

    last_exit = {"t": None, "side": 0, "px": None, "loss": False}
    slip = (getattr(bot, "slippage_pts", 0.0) or 0.0) * POINT
    decisions = []                       # (sig index, m1 index, decision, reason)
    eq = {"equity": getattr(bot, "start_equity", 1000.0), "day": None, "day_start": None, "day_pnl": 0.0, "consec": 0, "pause_until": 0, "stop_day": None}
    dir_losses = {1: 0, -1: 0}           # consecutive losses per direction
    dir_last_loss = {1: None, -1: None}  # (sig_bar, entry price) of the last losing trade per direction
    adx_arr = series_for_mgmt.get("adx")
    adx_now = (np.where(last_tf >= 0, adx_arr[np.maximum(last_tf, 0)], NAN).tolist()) if adx_arr is not None else None

    def close_pos(k, price, reason, at_time=None):
        nonlocal pos
        side = pos["side"]
        if slip > 0 and reason != "TP":                      # market/stop exits fill worse, limit TPs do not
            price = price - slip if side == 1 else price + slip
        pnl_px = (price - pos["entry"]) if side == 1 else (pos["entry"] - price)
        t_out = at_time if at_time is not None else t[k]
        mult = pos.get("mult", lots * 100.0)
        last_exit.update(t=t_out, side=side, px=price, loss=(pnl_px * mult) < 0)
        pnl_total = pnl_px * mult + _swap_nights(pos["t_in"], t_out) * (SWAP_LONG_PTS if side == 1 else SWAP_SHORT_PTS) * POINT * mult
        eq["equity"] += pnl_total; eq["day_pnl"] += pnl_total
        if pnl_total < 0:
            eq["consec"] += 1; dir_losses[side] += 1; dir_last_loss[side] = (pos.get("sig_bar", -1), pos["entry"])
            if bot_consec_pause and eq["consec"] >= bot_consec_pause:
                eq["pause_until"] = max(eq["pause_until"], t_out + getattr(bot, "pause_minutes", 60) * 60)
            if bot_consec_stop and eq["consec"] >= bot_consec_stop:
                eq["stop_day"] = t_out // 86400
        else:
            eq["consec"] = 0; dir_losses[side] = 0
        nights = _swap_nights(pos["t_in"], t_out)
        swap = nights * (SWAP_LONG_PTS if side == 1 else SWAP_SHORT_PTS) * POINT * mult
        trades.append(dict(
            entry_time=pd.Timestamp(pos["t_in"], unit="s"), exit_time=pd.Timestamp(t_out, unit="s"),
            side="BUY" if side == 1 else "SELL", entry=pos["entry"], exit=price, initial_sl=pos["isl"], tp=pos["tp"],
            risk=abs(pos["entry"] - pos["isl"]), pnl_px=pnl_px, pnl=pnl_px * mult + swap, swap=swap, lot=round(mult / 100.0, 2), equity=round(eq["equity"], 2),
            r_multiple=(pnl_px / abs(pos["entry"] - pos["isl"])) if pos["isl"] else NAN,
            exit_reason=(("SL_" + pos["src_trail"]) if (reason == "SL" and pos.get("src_trail")) else reason),
            stage=pos["stage"], sl_source=pos["src"], reflip=pos["reflip"],
            bars=k - pos["k_in"], max_fav=pos["mfe"], max_adv=pos["mae"], sig_time=pos["sig_time"],
            atr=pos.get("atr", NAN), spread=pos.get("spread", NAN), adx=pos.get("adx", NAN), opp_ago=pos.get("opp_ago", -1),
            sig_bar=pos.get("sig_bar", -1)))
        pos = None

    bot_consec_pause = getattr(bot, "consec_pause_at", 0) if not is_pine else 0
    bot_consec_stop = getattr(bot, "consec_stop_day_at", 0) if not is_pine else 0

    def size_position(k, row):
        """Sets pos["mult"] ($ per $1 move). Fixed lots, or equity x risk% / stop with the volatility and streak reductions."""
        nonlocal pos
        if is_pine or getattr(bot, "sizing", "fixed") != "risk":
            pos["mult"] = lots * 100.0
            pos["adx_entry"] = row.get("adx", NAN)
            return None
        risk_px = abs(pos["entry"] - pos["isl"])
        budget = eq["equity"] * bot.risk_pct / 100.0
        ar = row.get("atr_ratio", NAN)
        if bot.vol_elevated_ratio > 0 and not math.isnan(ar) and ar > bot.vol_elevated_ratio:
            budget *= bot.vol_elevated_risk_mult
        if getattr(bot, "consec_reduce_at", 0) > 0 and eq["consec"] >= bot.consec_reduce_at:
            budget *= 0.5
        if risk_px <= 0:
            pos = None; return "NO_STOP"
        lot = math.floor(budget / risk_px) * 0.01              # 0.01 lot = 1 oz = $1 per $1
        if lot < 0.01 or risk_px * 1.0 > eq["equity"] * bot.max_stop_risk_pct / 100.0:
            pos = None; return "RISK_MIN_LOT"
        lot = min(lot, bot.max_lot)
        pos["mult"] = lot * 100.0
        pos["adx_entry"] = row.get("adx", NAN)
        return None

    def try_open(k, row):
        """Entry at the open of M1 bar k. Returns None if a position was opened, else the NO_TRADE reason."""
        nonlocal pos
        side = row["side"]
        if bot.entry_hours is not None:
            hr = (t[k] % 86400) // 3600
            if not (bot.entry_hours[0] <= hr < bot.entry_hours[1]):
                return "SESSION"
        bid = o[k]; ask = bid + spr[k]
        fill = (ask + slip) if side == 1 else (bid - slip)
        scale = 1.0
        if not is_pine and bot.vol_scale and vs is not None:
            scale = vs[k]
        if not is_pine:
            # ---- loss-prevention layer: hard safety and environment gates
            if getattr(bot, "daily_loss_pct", 0) > 0:
                # risk mode: % of the day's starting equity; fixed-lot attribution runs: % of the notional start
                ref = eq["day_start"] if (getattr(bot, "sizing", "fixed") == "risk" and eq["day_start"]) else getattr(bot, "start_equity", 1000.0)
                if ref > 0 and eq["day_pnl"] <= -ref * bot.daily_loss_pct / 100:
                    return "DAILY_LOSS_LIMIT"
            if eq["stop_day"] is not None and t[k] // 86400 == eq["stop_day"]:
                return "CONSEC_LOSS_STOP_DAY"
            if t[k] < eq["pause_until"]:
                return "CONSEC_LOSS_PAUSE"
            a_ = row.get("atr", NAN)
            if bot.max_spread_atr > 0 and not math.isnan(a_) and a_ > 0 and spr[k] / a_ > bot.max_spread_atr:
                return "SPREAD_VS_ATR"
            if bot.max_cost_to_reward > 0 and row.get("risk", 0) > 0 and spr[k] / (bot.rr * row["risk"]) > bot.max_cost_to_reward:
                return "SPREAD_VS_REWARD"
            ar = row.get("atr_ratio", NAN)
            if bot.vol_extreme_ratio > 0 and not math.isnan(ar) and ar > bot.vol_extreme_ratio:
                return "VOL_EXTREME"
            if bot.large_candle_lock and bool(row.get("large_candle_lock", False)):
                return "LARGE_CANDLE"
            if bot.min_signal_distance_atr > 0:
                dps = row.get("dist_prev_sig", NAN)
                if not math.isnan(dps) and dps < bot.min_signal_distance_atr:
                    return "SIGNAL_DISTANCE"
            if bot.chop_lock_score > 0:
                sc = int(row.get("chop_static", 0)) + (1 if (last_exit["t"] is not None and last_exit["loss"]) else 0)
                if sc >= bot.chop_lock_score:
                    return "CHOP_LOCK"
            if bot.max_attempts_per_dir > 0 and dir_losses[side] >= bot.max_attempts_per_dir:
                ll = dir_last_loss[side]
                reset = ll is not None and int(row.get("piv_bar", -1)) > ll[0] and not math.isnan(a_) and abs(row["entry"] - ll[1]) >= bot.reset_atr * a_
                if not reset:
                    return "MAX_ATTEMPTS_DIR"
                dir_losses[side] = 0
            # ---- filter lab: post-loss cooldown / re-entry distance
            if last_exit["t"] is not None and last_exit["loss"] and (bot.cooldown_min_after_loss > 0 or bot.cooldown_bars_after_loss > 0):
                blocked = (bot.cooldown_mode == "all" or (bot.cooldown_mode == "same" and side == last_exit["side"])
                           or (bot.cooldown_mode == "opposite" and side != last_exit["side"]))
                if blocked:
                    wait = max(bot.cooldown_min_after_loss * 60, bot.cooldown_bars_after_loss * tf_sec)
                    if t[k] - last_exit["t"] < wait:
                        return "COOLDOWN"
            if bot.reentry_atr_mult > 0 and last_exit["px"] is not None:
                a = row.get("atr", NAN)
                if not math.isnan(a) and abs(fill - last_exit["px"]) < bot.reentry_atr_mult * a:
                    return "REENTRY_DISTANCE"
        extra = dict(atr=row.get("atr", NAN), spread=spr[k], adx=row.get("adx", NAN), opp_ago=row.get("opp_ago", -1), sig_bar=row.get("bar", -1))
        if is_pine:
            sl, tp, risk = row["sl"], row["tp"], row["risk"]
            if math.isnan(sl) or math.isnan(tp) or risk <= 0:
                return "NO_STOP"
            src = "pivot" if row["sl_pivot"] else "purple"
        else:
            # filters
            own = row["bv1"] if side == 1 else row["sv1"]; opp = row["sv1"] if side == 1 else row["bv1"]
            if math.isnan(own) or math.isnan(opp) or (own <= 0 and opp <= 0):
                return "NO_VOLUME_DATA"
            ratio = float("inf") if opp <= 0 else own / opp
            if ratio + 1e-12 < bot.min_volume_ratio:
                return "VOLUME_RATIO"
            if bot.require_m1_box and not (row["bv1"] > row["sv1"] if side == 1 else row["sv1"] > row["bv1"]):
                return "M1_BOX"
            if math.isnan(row["bv3"]) or math.isnan(row["sv3"]):
                return "NO_M3_DATA"
            if bot.require_m3_box and not (row["bv3"] > row["sv3"] if side == 1 else row["sv3"] > row["bv3"]):
                return "M3_BOX"
            if math.isnan(row["adx"]) or not (row["adx"] > bot.adx_min):
                return "ADX"
            if bot.min_volume_ratio_m3 > 0:
                own3 = row["bv3"] if side == 1 else row["sv3"]; opp3 = row["sv3"] if side == 1 else row["bv3"]
                r3 = float("inf") if opp3 <= 0 else own3 / opp3
                if r3 + 1e-12 < bot.min_volume_ratio_m3:
                    return "VOLUME_RATIO_M3"
            if bot.initial_sl in ("purple", "atr", "hybrid", "fixed"):
                pur = row["purple"]
                a = row.get("atr", NAN)
                risk_pur = (row["entry"] - pur) if side == 1 else (pur - row["entry"])
                if bot.initial_sl == "fixed":
                    risk = bot.fixed_sl_pts * POINT
                    if risk <= 0:
                        return "NO_STOP"
                elif bot.initial_sl == "purple":
                    if math.isnan(pur) or risk_pur <= 0:
                        return "NO_STOP"
                    risk = risk_pur
                else:
                    if math.isnan(a) or a <= 0:
                        return "NO_ATR"
                    d_atr = bot.atr_stop_mult * a
                    if bot.initial_sl == "atr":
                        risk = d_atr
                    else:                                    # hybrid: structure (pivot, else purple) but never tighter than the ATR floor
                        structure = row["risk"] if (row["sl_pivot"] and row["risk"] > 0) else risk_pur
                        risk = max(structure if structure > 0 else 0.0, d_atr)
                if bot.atr_stop_cap > 0 and not math.isnan(a) and risk > bot.atr_stop_cap * a:
                    return "STOP_TOO_WIDE"
                if bot.initial_sl == "fixed":                # levels from the fill price, fixed distances
                    sl = fill - risk if side == 1 else fill + risk
                    if bot.tp_pts > 0:
                        tp = fill + bot.tp_pts * POINT if side == 1 else fill - bot.tp_pts * POINT
                    else:
                        tp = (fill + bot.rr * risk if side == 1 else fill - bot.rr * risk) if bot.use_tp else (1e9 if side == 1 else -1e9)
                else:
                    sl = row["entry"] - risk if side == 1 else row["entry"] + risk
                    tp = (row["entry"] + bot.rr * risk if side == 1 else row["entry"] - bot.rr * risk) if bot.use_tp else (1e9 if side == 1 else -1e9)
                if side == 1 and (sl >= ask or tp <= ask):
                    return "PRICE_PAST_LEVEL"
                if side == -1 and (sl <= bid or tp >= bid):
                    return "PRICE_PAST_LEVEL"
                pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=1 if bot.purple_trail_always else 0,
                           src=bot.initial_sl, reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
                return size_position(k, row)
            reflip = row["reflip"] and reflip_bars > 0 and bot.reflip_action != "KEEP_PIVOT"
            if reflip and bot.reflip_action == "SKIP":
                return "RAPID_FLIP_SKIP"
            sl = tp = NAN; src = ""
            if (not row["sl_pivot"]) or reflip:
                hp = 0 if (reflip and bot.reflip_action == "PURPLE") else hard_pts
                hp_scaled = hp * scale
                min_pts = spr[k] / POINT
                if hp_scaled > min_pts:
                    ref = ask if side == 1 else bid
                    sl = ref - hp_scaled * POINT if side == 1 else ref + hp_scaled * POINT
                    tp = ref + bot.rr * hp_scaled * POINT if side == 1 else ref - bot.rr * hp_scaled * POINT
                    src = "hard_sl"
                elif reflip:
                    risk = (row["entry"] - row["purple"]) if side == 1 else (row["purple"] - row["entry"])
                    if math.isnan(row["purple"]) or risk <= 0:
                        return "NO_STOP"
                    sl = row["purple"]; tp = row["entry"] + bot.rr * risk if side == 1 else row["entry"] - bot.rr * risk
                    src = "purple_reflip"
            if math.isnan(sl):
                if math.isnan(row["sl"]) or row["risk"] <= 0:
                    return "NO_STOP"
                sl, tp = row["sl"], row["tp"]
                src = "pivot" if row["sl_pivot"] else "purple"
            # ValidateStopsAtPrice (stops level 0)
            if side == 1 and (sl >= ask or tp <= ask):
                return "PRICE_PAST_LEVEL"
            if side == -1 and (sl <= bid or tp >= bid):
                return "PRICE_PAST_LEVEL"
            if bot.atr_stop_cap > 0:
                a = row.get("atr", NAN)
                if not math.isnan(a) and abs(fill - sl) > bot.atr_stop_cap * a:
                    return "STOP_TOO_WIDE"
        if is_pine:
            # TradeStops: order must be placeable at the live price
            if side == 1 and not (sl < bid and tp > ask):
                return "PRICE_PAST_LEVEL"
            if side == -1 and not (sl > ask and tp < bid):
                return "PRICE_PAST_LEVEL"
        pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=0, src=src,
                   reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
        return size_position(k, row)

    # data holes (missing months): close anything open at the hole and ignore signals in the warm-up after it
    HOLE = 3 * 86400
    warm_until = -1
    pending_entry = None
    k = k0
    while k < k1:
        if k > 0 and t[k] - t[k - 1] > HOLE:
            if pos is not None:
                close_pos(k - 1, c[k - 1] if pos["side"] == 1 else c[k - 1] + spr[k - 1], "data_gap", at_time=t[k - 1])
            warm_until = k + 300
        if k < warm_until and k in sig_at:
            for j in sig_at[k]:
                decisions.append((j, k, "NO_TRADE", "DATA_WARMUP"))
            k += 1
            continue
        # --- 0. Model B: a pending opposite-signal close, confirmed if the direction persisted
        if pos is not None and pos.get("pending_k") is not None and k >= pos["pending_k"]:
            if dir_now[k] == pos["pending_dir"]:
                bid = o[k]; ask = bid + spr[k]
                close_pos(k, bid if pos["side"] == 1 else ask, "opposite_confirmed")
            else:
                pos["pending_k"] = None
        # --- 1. gap exit at the open for an existing position
        if pos is not None:
            s = pos["side"]; bid = o[k]; ask = bid + spr[k]
            if s == 1:
                if bid <= pos["sl"]:
                    close_pos(k, bid, "SL_gap" if bid < pos["sl"] else "SL");
                elif bid >= pos["tp"]:
                    close_pos(k, bid, "TP")
            else:
                if ask >= pos["sl"]:
                    close_pos(k, ask, "SL_gap" if ask > pos["sl"] else "SL")
                elif ask <= pos["tp"]:
                    close_pos(k, ask, "TP")
        # --- day bookkeeping (server day)
        dk = t[k] // 86400
        if eq["day"] != dk:
            eq["day"] = dk; eq["day_start"] = eq["equity"]; eq["day_pnl"] = 0.0
        # --- pending confirmed entry (anti-flip: the direction must still hold N signal bars later)
        if pending_entry is not None and k >= pending_entry[0]:
            pk, prow, pj = pending_entry; pending_entry = None
            need = -1 if prow["side"] == 1 else 1
            if dir_now[k] != need:
                decisions.append((pj, k, "NO_TRADE", "CONFIRM_FAILED"))
            elif pos is not None:
                decisions.append((pj, k, "NO_TRADE", "POSITION_OPEN"))
            else:
                r_ = try_open(k, prow)
                decisions.append((pj, k, "TRADE" if r_ is None else "NO_TRADE", r_ or "ENTERED_CONFIRMED"))
        # --- 2. signal processing at the open of this bar
        if k in sig_at:
            for j in sig_at[k]:
                row = sig_rows[j]
                if not is_pine and bot.stale_rule and (t[k] - row["close_time"]) > tf_sec:
                    decisions.append((j, k, "NO_TRADE", "STALE")); continue
                if pos is not None:
                    opposite = pos["side"] != row["side"]
                    if is_pine:
                        if opposite:
                            if not bot.reverse_on_flip:
                                decisions.append((j, k, "NO_TRADE", "POSITION_OPEN")); continue
                            bid = o[k]; ask = bid + spr[k]
                            close_pos(k, bid if pos["side"] == 1 else ask, "flip")
                        else:
                            continue
                    else:
                        if opposite and (bot.reverse_on_opposite or bot.close_on_opposite):
                            if bot.opposite_min_adx > 0 and not (row["adx"] > bot.opposite_min_adx):
                                continue                              # Model D: weak opposite signal, keep the trade
                            if bot.opposite_confirm_bars > 0:         # Model B: wait for the opposite direction to persist
                                pos["pending_k"] = k + bot.opposite_confirm_bars * tf_minutes
                                pos["pending_dir"] = -1 if row["side"] == 1 else 1
                                continue
                            bid = o[k]; ask = bid + spr[k]
                            close_pos(k, bid if pos["side"] == 1 else ask, "opposite")
                            if not bot.reverse_on_opposite:
                                continue
                        elif bot.one_position:
                            decisions.append((j, k, "NO_TRADE", "POSITION_OPEN")); continue
                if pos is None:
                    if not is_pine and getattr(bot, "entry_confirm_bars", 0) > 0:
                        pending_entry = (k + bot.entry_confirm_bars * tf_minutes, row, j)
                        decisions.append((j, k, "PENDING", "CONFIRMATION"))
                        continue
                    r_ = try_open(k, row)
                    decisions.append((j, k, "TRADE" if r_ is None else "NO_TRADE", r_ or "ENTERED"))
        # --- 3. intrabar exits for the open position (SL before TP)
        if pos is not None:
            s = pos["side"]; sl = pos["sl"]; tp = pos["tp"]
            if s == 1:
                lo, hi = l[k], h[k]
                hit_sl = lo <= sl; hit_tp = hi >= tp
                if hit_sl and hit_tp:
                    ambiguous += 1
                if hit_sl:
                    close_pos(k, sl, "SL")
                elif hit_tp:
                    close_pos(k, tp, "TP")
                else:
                    pos["mfe"] = max(pos["mfe"], hi - pos["entry"]); pos["mae"] = max(pos["mae"], pos["entry"] - lo)
            else:
                lo, hi = l[k] + spr[k], h[k] + spr[k]         # ask
                hit_sl = hi >= sl; hit_tp = lo <= tp
                if hit_sl and hit_tp:
                    ambiguous += 1
                if hit_sl:
                    close_pos(k, sl, "SL")
                elif hit_tp:
                    close_pos(k, tp, "TP")
                else:
                    pos["mfe"] = max(pos["mfe"], pos["entry"] - lo); pos["mae"] = max(pos["mae"], hi - pos["entry"])
        # --- 4. trailing at the end of the bar
        if pos is not None:
            s = pos["side"]; e = pos["entry"]; cur = pos["sl"]
            scale = pos["scale"]
            if s == 1:
                best_px = h[k]; close_px = c[k]; profit = best_px - e
            else:
                best_px = l[k] + spr[k]; close_px = c[k] + spr[k]; profit = e - best_px
            best = cur; why = None
            pn = purple_now[k]; dn = dir_now[k]
            if is_pine:
                if profit > 0:
                    if bot.purple_trail and profit >= bot.purple_start_pts * POINT and not math.isnan(pn) and dn == (-1 if s == 1 else 1):
                        cnd = round(pn, 2)
                        if (cnd > best) if s == 1 else (cnd < best):
                            if abs(cnd - cur) >= bot.min_sl_step_pts * POINT - POINT / 2:
                                best = cnd; why = "purple"
                    if bot.lock_trigger_pts > 0 and profit >= bot.lock_trigger_pts * POINT - POINT / 2:
                        cnd = round(e + bot.lock_profit_pts * POINT, 2) if s == 1 else round(e - bot.lock_profit_pts * POINT, 2)
                        if (cnd > best) if s == 1 else (cnd < best):
                            best = cnd; why = "lock"
            else:
                pa = bot.purple_activation_pts * scale * POINT
                pp = bot.protection_activation_pts * scale * POINT
                lk = bot.lock_pts * scale * POINT
                risk0 = abs(e - pos["isl"])
                if bot.trail_activation_r >= 0:
                    pa = bot.trail_activation_r * risk0
                if bot.lock_activation_r >= 0:
                    pp = bot.lock_activation_r * risk0
                    lk = bot.lock_level_r * risk0
                # ---- trade-health exit: age + no performance + signal weakening (direction flipped or ADX below entry)
                if getattr(bot, "health_exit_min", 0) > 0 and (t[k] + 60 - pos["t_in"]) >= bot.health_exit_min * 60:
                    cur_profit = (c[k] - e) if s == 1 else (e - (c[k] + spr[k]))
                    weak = (dn != (-1 if s == 1 else 1)) or (adx_now is not None and not math.isnan(adx_now[k]) and not math.isnan(pos.get("adx_entry", NAN)) and adx_now[k] < pos["adx_entry"])
                    if cur_profit < bot.health_exit_below_r * risk0 and weak:
                        close_pos(k, c[k] if s == 1 else c[k] + spr[k], "health_exit")
                        k += 1
                        continue
                # ---- time exit: old trade that never went anywhere
                if bot.time_exit_min > 0 and (t[k] + 60 - pos["t_in"]) >= bot.time_exit_min * 60:
                    cur_profit = (c[k] - e) if s == 1 else (e - (c[k] + spr[k]))
                    if cur_profit < bot.time_exit_below_r * risk0:
                        close_pos(k, c[k] if s == 1 else c[k] + spr[k], "time_exit")
                        k += 1
                        continue
                stage = pos["stage"]
                if profit >= pp - POINT / 2:
                    stage = max(stage, 2)
                elif profit >= pa - POINT / 2 or bot.purple_trail_always:
                    stage = max(stage, 1)
                pos["stage"] = stage
                if stage >= 1:
                    if not math.isnan(pn) and dn == (-1 if s == 1 else 1):
                        cnd = round(pn, 2)
                        if (cnd > best) if s == 1 else (cnd < best):
                            best = cnd; why = "purple"
                    if stage >= 2:
                        cnd = round(e + lk, 2) if s == 1 else round(e - lk, 2)
                        if (cnd > best) if s == 1 else (cnd < best):
                            best = cnd; why = "lock"
                        if bot.one_to_one:
                            gap = (bot.one_to_one_gap_r * risk0) if bot.one_to_one_gap_r > 0 else (pp - lk)
                            cnd = round(best_px - gap, 2) if s == 1 else round(best_px + gap, 2)
                            if (cnd > best) if s == 1 else (cnd < best):
                                best = cnd; why = "one_to_one"
                if getattr(bot, "lock2_activation_r", -1) >= 0 and profit >= bot.lock2_activation_r * risk0 - POINT / 2:
                    cnd = round(e + bot.lock2_level_r * risk0, 2) if s == 1 else round(e - bot.lock2_level_r * risk0, 2)
                    if (cnd > best) if s == 1 else (cnd < best):
                        best = cnd; why = "lock"
                if bot.breakeven_r >= 0 and profit >= bot.breakeven_r * risk0 - POINT / 2:
                    buf = spr[k] + bot.breakeven_buffer_pts * POINT
                    cnd = round(e + buf, 2) if s == 1 else round(e - buf, 2)
                    if (cnd > best) if s == 1 else (cnd < best):
                        best = cnd; why = "breakeven"
                if why is not None and why not in ("lock", "breakeven") and abs(best - cur) < bot.min_improve_pts * POINT - POINT / 2:
                    why = None; best = cur
            if why is not None and best != cur:
                # The stop moved during this bar. Did price come back through it before the close?
                # Path assumption: a bar that closes against the trade went extreme-first
                # (buy: open -> high -> low -> close), so its low tests the new stop.
                pos["sl"] = best
                pos["src_trail"] = why
                if pos["stage"] == 0:
                    pos["stage"] = 1
                against = (c[k] < o[k]) if s == 1 else (c[k] > o[k])
                if getattr(bot, "trail_mode", "path") == "worst":
                    against = True
                if s == 1:
                    hit = close_px < best or (against and l[k] <= best)
                else:
                    hit = close_px > best or (against and h[k] + spr[k] >= best)
                if hit:
                    close_pos(k, best, "SL_trail_" + why)
        k += 1
    if pos is not None:
        s = pos["side"]; kk = k1 - 1
        close_pos(kk, c[kk] if s == 1 else c[kk] + spr[kk], "end_of_test")
    df = pd.DataFrame(trades)
    df.attrs["ambiguous_bars"] = ambiguous
    df.attrs["decisions"] = pd.DataFrame([(int(orig_index[j]), kk, d_, r_) for j, kk, d_, r_ in decisions], columns=["sig", "k", "decision", "reason"])
    df.attrs["final_equity"] = eq["equity"]
    return df


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------

def metrics(tr: pd.DataFrame, deposit: float = 1000.0, seed: int = 7) -> dict:
    if tr is None or len(tr) == 0:
        return dict(trades=0)
    pnl = tr["pnl"].to_numpy(float)
    wins = pnl[pnl > 0.005]; losses = pnl[pnl < -0.005]
    gp = wins.sum(); gl = -losses.sum()
    eq = deposit + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[deposit], eq]))
    dd = peak[1:] - eq
    ddp = dd / peak[1:]
    # streaks
    cl = mcl = cw = mcw = 0
    for x in pnl:
        if x < -0.005:
            cl += 1; cw = 0
        elif x > 0.005:
            cw += 1; cl = 0
        mcl = max(mcl, cl); mcw = max(mcw, cw)
    rng = np.random.default_rng(seed)
    n_boot = 2000
    if len(pnl) * n_boot <= 40_000_000:
        boots = rng.choice(pnl, size=(n_boot, len(pnl)), replace=True).mean(axis=1)
    else:
        boots = np.array([rng.choice(pnl, size=len(pnl), replace=True).mean() for _ in range(300)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    r = tr["r_multiple"].to_numpy(float)
    r = r[~np.isnan(r)]
    reasons = tr["exit_reason"].value_counts().to_dict()
    hold = (tr["exit_time"] - tr["entry_time"]).dt.total_seconds() / 60.0
    return dict(
        trades=int(len(pnl)), wins=int(len(wins)), losses=int(len(losses)),
        win_rate=float(len(wins) / len(pnl)), net=float(pnl.sum()), gross_profit=float(gp), gross_loss=float(gl),
        profit_factor=float(gp / gl) if gl > 0 else float("inf"), avg_trade=float(pnl.mean()),
        avg_win=float(wins.mean()) if len(wins) else 0.0, avg_loss=float(losses.mean()) if len(losses) else 0.0,
        max_dd=float(dd.max()), max_dd_pct=float(ddp.max() * 100), max_consec_losses=mcl, max_consec_wins=mcw,
        ci_low=float(lo), ci_high=float(hi), p_profit=float((boots > 0).mean()),
        avg_r=float(r.mean()) if len(r) else NAN, sum_r=float(r.sum()) if len(r) else NAN,
        median_risk_px=float(tr["risk"].median()), p90_risk_px=float(tr["risk"].quantile(0.9)),
        max_loss=float(pnl.min()), max_win=float(pnl.max()), top3_share=float(np.sort(pnl)[-3:].sum() / pnl.sum()) if pnl.sum() > 0 else NAN,
        avg_hold_min=float(hold.mean()), median_hold_min=float(hold.median()),
        swap_total=float(tr["swap"].sum()), exit_reasons=reasons, ambiguous_bars=int(tr.attrs.get("ambiguous_bars", 0)),
        ruin_200=bool((200 + np.cumsum(pnl)).min() <= 0), ruin_1000=bool((1000 + np.cumsum(pnl)).min() <= 0),
        min_equity_from_1000=float((1000 + np.cumsum(pnl)).min()),
    )


def year_spread_model() -> dict:
    """XM GOLD spread in points by year, M1-equivalent (M15 close-spread medians x 1.28 = M1/M15 ratio in 2026)."""
    m15 = {2021: 25, 2022: 25, 2023: 25, 2024: 28, 2025: 30, 2026: 40}
    return {y: round(v * 1.28) for y, v in m15.items()}
