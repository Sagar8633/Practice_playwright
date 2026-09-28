"""
pdvz_engine.py - Python replica of GOLD/pd_volume_zones/PD_VolumeZones_Strategy.pine
for offline testing on the Dukascopy XAUUSD M1 data in
Momentum_Tracker_Indicator/backtest/data/duka_chunks (UTC, traded volume).

V1 rules (all defaults; the frozen baseline):
  * "day"   = calendar day in Asia/Kolkata (UTC+5:30), like the TradingView chart.
  * profile = fixed-range volume profile of the LAST COMPLETED day (>= 8 h of bars)
              built from the chart-timeframe (5-min) bars: 40 bins, no smoothing,
              peak window 2, prominence >= 0.20, share >= 0.25 of the biggest bin,
              extension 0.75, half-height <= 1 bin, separation >= 3 bins,
              max 4 internal zones, boundary rectangles of 2 bins at PDH and PDL,
              POC = highest-volume bin of the rectangle.
  * LONG    = bar range crosses a POC (this bar or one of the previous 11),
              green candle closes above the rectangle top -> buy at that close,
              SL = rectangle bottom, TP = entry + 3 x (entry - SL).
  * SHORT   = mirror.
  * one position at a time, one entry per rectangle (per day), nearest rectangle wins
    when several qualify on the same candle.
Exits are resolved on the M1 path (TradingView's own emulator only sees 5-min OHLC).

V2 research switches (each defaults to "off" = V1 behaviour; see v2_lab.py):
  fb_exit_closes / fb_window   exit at the n-th 5-min close back inside the rectangle
                               within the first `fb_window` bars after entry
  confirm_bars                 2 = a second consecutive close beyond the edge is needed
                               before entering (a close back inside invalidates the setup)
  min_risk_usd / min_risk_atr  skip setups whose stop is smaller than this
  target_rule / target_margin_R  "beyond_pdhl": the 3R target must lie beyond the prior
                               day's High (longs) / Low (shorts), by >= margin x risk
  vol_filter / vol_low_pct / vol_high_pct / vol_window   skip when ATR14's percentile
                               rank over the trailing window is below/above the limits
  tap_timing                   "any" (V1), "same_only", "earlier_only"
  session_filter               set of allowed session names (None = all)
"""
import glob
import math

import numpy as np
import pandas as pd

DEFAULTS = dict(
    n_bins=40, smooth=1, min_prom=0.20, min_share=0.25, peak_win=2, extend_thr=0.75,
    max_half=1, min_sep=3, max_zones=4, edge_zones=True, edge_bins=2, poc_mode="peak",
    min_hours=8.0, tap_valid=12, rr=3.0, sl_buf=0.0, max_per_zone=1, trade_edge=True,
    tf_min=5, tz_offset_min=330, max_stale_days=4, max_gap_days=3,
    # diagnostic switches for shadow runs only; the baseline keeps all four at their default
    require_tap=True, require_colour=True, allow_long=True, allow_short=True,
    simulate_skipped=True,
    # ---- V2 research switches (all off = V1) ----
    fb_exit_closes=0, fb_window=3, confirm_bars=1,
    min_risk_usd=0.0, min_risk_atr=0.0,
    target_rule="none", target_margin_R=0.0,
    vol_filter="none", vol_low_pct=20, vol_high_pct=90, vol_window=2016,
    tap_timing="any", session_filter=None,
    # V3: a callable rec -> bool evaluated on the pre-entry feature record; False blocks the setup
    entry_filter=None,
    # V4: an exit specification for exit_sim.walk (None = the V1 fixed SL / 3R target walk)
    exit_spec=None,
    # fixed-dollar stop instead of the rectangle edge (0 = rectangle edge); the target stays rr x that distance
    fixed_sl_usd=0.0,
)

# assumed one-way cost per trade in USD/oz (spread), by year - used ONLY for the
# "net R" column, never for the entry/exit logic
SPREAD_BY_YEAR = {2021: 0.25, 2022: 0.25, 2023: 0.30, 2024: 0.35, 2025: 0.40, 2026: 0.50}

VOL_WINDOWS = (2016, 8640)  # 7 and 30 days of 5-min bars


# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
# The 39 monthly chunks that were on disk when the V1 baseline was frozen (25-Sep-2026).
# Every V1/V2/V3 comparison is pinned to this list; more months appeared in the folder later.
V1_MONTHS = ["2021-09", "2022-04", "2022-08", "2022-10", "2022-11", "2022-12", "2023-02", "2023-03", "2023-04", "2023-06",
             "2023-07", "2023-09", "2023-10", "2023-11", "2023-12", "2024-02", "2024-05", "2024-06", "2024-08", "2024-12",
             "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11",
             "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
CHUNK_DIR = "../../../Momentum_Tracker_Indicator/backtest/data/duka_chunks"


def v1_chunk_files(chunk_dir=CHUNK_DIR):
    return [f"{chunk_dir}/bid_{m}.csv" for m in V1_MONTHS]


def load_m1(chunk_glob):
    """chunk_glob: a glob pattern or an explicit list of files."""
    parts = []
    files = list(chunk_glob) if isinstance(chunk_glob, (list, tuple)) else sorted(glob.glob(chunk_glob))
    for f in files:
        d = pd.read_csv(f)
        if len(d):
            parts.append(d)
    df = pd.concat(parts, ignore_index=True).rename(columns={"timestamp": "t"})
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df = df[(df["volume"] > 0) | (df["high"] > df["low"])].reset_index(drop=True)
    return df[["t", "open", "high", "low", "close", "volume"]]


def to_bars(m1, tf_min):
    ms = tf_min * 60000
    key = (m1["t"] // ms) * ms
    g = m1.groupby(key, sort=True)
    bars = pd.DataFrame({
        "t": np.array(list(g.groups.keys()), dtype=np.int64),
        "open": g["open"].first().values,
        "high": g["high"].max().values,
        "low": g["low"].min().values,
        "close": g["close"].last().values,
        "volume": g["volume"].sum().values,
    })
    return bars


def atr_wilder(h, l, c, n=14):
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    tr = np.concatenate([[h[0] - l[0]], tr])
    out = np.full(len(tr), np.nan)
    a = np.nanmean(tr[:n])
    out[n - 1] = a
    for i in range(n, len(tr)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def prepare(m1, tf_min=5, tz_offset_min=330):
    """Everything that does not depend on the strategy parameters, computed once."""
    bars = to_bars(m1, tf_min)
    t = bars["t"].values
    o, h, l, c, v = (bars[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
    atr = atr_wilder(h, l, c, 14)
    s = pd.Series(atr)
    atr_med = s.rolling(2000, min_periods=200).median().values
    atr_pct = {w: s.rolling(w, min_periods=200).rank(pct=True).values for w in VOL_WINDOWS}
    return dict(
        tf_min=tf_min, tz_offset_min=tz_offset_min, t=t, o=o, h=h, l=l, c=c, v=v,
        day=(t + tz_offset_min * 60000) // 86400000, atr=atr, atr_med=atr_med, atr_pct=atr_pct,
        m1t=m1["t"].values, m1o=m1["open"].values.astype(float), m1h=m1["high"].values.astype(float),
        m1l=m1["low"].values.astype(float), m1c=m1["close"].values.astype(float), n_m1=len(m1),
    )


# ----------------------------------------------------------------------------
# profile maths - direct ports of the Pine functions
# ----------------------------------------------------------------------------
def profile(hi, lo, vol, p_low, bin_size, n):
    prof = np.zeros(n)
    for bh, bl, bq in zip(hi, lo, vol):
        if not (bq > 0) or math.isnan(bh) or math.isnan(bl):
            continue
        b0 = max(0, min(n - 1, int(math.floor((bl - p_low) / bin_size))))
        b1 = max(0, min(n - 1, int(math.floor((bh - p_low) / bin_size))))
        if b1 <= b0:
            prof[b0] += bq
        else:
            span = bh - bl
            for j in range(b0, b1 + 1):
                lo_j = p_low + j * bin_size
                hi_j = lo_j + bin_size
                ov = min(bh, hi_j) - max(bl, lo_j)
                if ov > 0:
                    prof[j] += bq * ov / span
    return prof


def smooth(v, w):
    n = len(v)
    out = v.copy()
    half = w // 2
    if half > 0 and n > 0:
        for i in range(n):
            a, b = max(0, i - half), min(n - 1, i + half)
            out[i] = v[a:b + 1].mean()
    return out


def is_peak(v, i, w):
    n = len(v)
    pv = v[i]
    if not pv > 0:
        return False
    for j in range(max(0, i - w), min(n - 1, i + w) + 1):
        if j != i:
            q = v[j]
            if q > pv or (q == pv and j < i):
                return False
    return True


def prominence(v, i):
    n = len(v)
    pv = v[i]
    min_l = pv
    j = i - 1
    while j >= 0 and v[j] <= pv:
        min_l = min(min_l, v[j])
        j -= 1
    min_r = pv
    j = i + 1
    while j < n and v[j] <= pv:
        min_r = min(min_r, v[j])
        j += 1
    return pv - max(min_l, min_r)


def extend(v, i, thr, max_h):
    n = len(v)
    lim = thr * v[i]
    lo = hi = i
    while lo > 0 and i - lo < max_h and v[lo - 1] >= lim:
        lo -= 1
    while hi < n - 1 and hi - i < max_h and v[hi + 1] >= lim:
        hi += 1
    return lo, hi


def argmax_range(v, a, b):
    best, bv = a, v[a]
    for j in range(a + 1, b + 1):
        if v[j] > bv:
            bv, best = v[j], j
    return best


def build_zones(hi, lo, vol, p):
    p_high, p_low = float(np.max(hi)), float(np.min(lo))
    rng = p_high - p_low
    if not rng > 0:
        return None
    n = p["n_bins"]
    bs = rng / n
    raw = profile(hi, lo, vol, p_low, bs, n)
    sv = smooth(raw, p["smooth"])
    max_v = sv.max()
    tot = raw.sum()
    edge = p["edge_bins"] if p["edge_zones"] else 0
    cands = []
    if max_v > 0 and n - 1 - edge >= edge:
        for i in range(edge, n - edge):
            if is_peak(sv, i, p["peak_win"]):
                pv = sv[i]
                prom = prominence(sv, i)
                if pv / max_v >= p["min_share"] and prom / pv >= p["min_prom"]:
                    el, eh = extend(sv, i, p["extend_thr"], p["max_half"])
                    cands.append((i, max(el, edge), min(eh, n - 1 - edge), pv, prom / pv, pv / max_v))
    sel = []
    used = [False] * len(cands)
    for _ in range(len(cands)):
        best, best_v = -1, -1.0
        for ci, cd in enumerate(cands):
            if not used[ci] and cd[3] > best_v:
                best_v, best = cd[3], ci
        used[best] = True
        i, l, h, pv, prom_rel, share_peak = cands[best]
        ok = True
        for (si, sl_, sh, _a, _b) in sel:
            gap = max(sl_ - h, l - sh) - 1
            if gap < p["min_sep"]:
                ok = False
        if ok and len(sel) < p["max_zones"]:
            sel.append((i, l, h, prom_rel, share_peak))

    def poc_of(top, bot, pk):
        return (top + bot) / 2 if p["poc_mode"] == "mid" else p_low + (pk + 0.5) * bs

    zones = []
    if p["edge_zones"] and p["edge_bins"] < n:
        hi_lo = n - p["edge_bins"]
        pk = argmax_range(sv, hi_lo, n - 1)
        top, bot = p_high, p_low + hi_lo * bs
        zones.append(dict(top=top, bot=bot, poc=poc_of(top, bot, pk), kind="PDH", peak=pk,
                          share=raw[hi_lo:n].sum() / tot if tot > 0 else 0, prom_rel=np.nan, peak_share=np.nan))
        pk = argmax_range(sv, 0, p["edge_bins"] - 1)
        top, bot = p_low + p["edge_bins"] * bs, p_low
        zones.append(dict(top=top, bot=bot, poc=poc_of(top, bot, pk), kind="PDL", peak=pk,
                          share=raw[0:p["edge_bins"]].sum() / tot if tot > 0 else 0, prom_rel=np.nan, peak_share=np.nan))
    for (pk, l, h, prom_rel, share_peak) in sel:
        bot, top = p_low + l * bs, p_low + (h + 1) * bs
        zones.append(dict(top=top, bot=bot, poc=poc_of(top, bot, pk), kind="HVN", peak=pk,
                          share=raw[l:h + 1].sum() / tot if tot > 0 else 0, prom_rel=prom_rel, peak_share=share_peak))
    return dict(zones=zones, pdh=p_high, pdl=p_low, bin_size=bs, raw=raw, sv=sv, day_range=rng)


# ----------------------------------------------------------------------------
# exit resolution on the M1 path
# ----------------------------------------------------------------------------
def simulate_exit(side, entry, sl, tp, j0, D, max_gap_ms, mg=None):
    """Walk M1 bars from j0. Inside a bar the path is open -> nearer extreme ->
    farther extreme -> close (TradingView's emulator assumption).
    mg (optional) = dict(i=entry bar index, top, bot, closes=n, window=k): exit at the
    n-th 5-min close back inside the rectangle within the first k bars after entry."""
    m1t, m1o, m1h, m1l, m1c = D["m1t"], D["m1o"], D["m1h"], D["m1l"], D["m1c"]
    t5, c5, tf_ms = D["t"], D["c"], D["tf_min"] * 60000
    n5 = len(t5)
    sgn = 1.0 if side == "long" else -1.0
    risk = (entry - sl) * sgn
    tp_dist = (tp - entry) * sgn
    mfe = 0.0
    mae = 0.0
    t_mae05 = None
    t_mfe1 = None
    prev_t = None
    j = j0
    n = len(m1t)
    q = mg["i"] if mg else -1          # last 5-min bar known to be complete
    inside_count = 0

    def fav(px):
        return (px - entry) * sgn

    def done(exit_t, exit_px, reason, bars):
        return dict(exit_t=exit_t, exit_px=exit_px, reason=reason, mfe=mfe, mae=mae, bars=bars,
                    t_mae05=t_mae05, t_mfe1=t_mfe1)

    while j < n:
        tj = m1t[j]
        if prev_t is not None and tj - prev_t > max_gap_ms:
            return done(prev_t, m1c[j - 1], "data_gap", j - j0)
        # ---- 5-min bars completed before this M1 bar: failed-breakout management
        if mg is not None:
            while q + 1 < n5 and t5[q + 1] <= tj:
                q += 1
                qc = q - 1                       # the bar that just completed
                if qc > mg["i"] and qc - mg["i"] <= mg["window"]:
                    inside = c5[qc] <= mg["top"] if side == "long" else c5[qc] >= mg["bot"]
                    if inside:
                        inside_count += 1
                        if inside_count >= mg["closes"]:
                            return done(t5[qc] + tf_ms, c5[qc], "FB", j - j0)
        o_, h_, l_, c_ = m1o[j], m1h[j], m1l[j], m1c[j]
        # gap through a level at the open
        if fav(o_) <= -risk:
            mae = max(mae, -fav(o_))
            if t_mae05 is None:
                t_mae05 = tj
            return done(tj, o_, "SL", j - j0 + 1)
        if fav(o_) >= tp_dist:
            mfe = max(mfe, fav(o_))
            if t_mfe1 is None:
                t_mfe1 = tj
            return done(tj, o_, "TP", j - j0 + 1)
        path = [o_, h_, l_, c_] if (h_ - o_) <= (o_ - l_) else [o_, l_, h_, c_]
        for a, b in zip(path[:-1], path[1:]):
            if b == a:
                continue
            if fav(b) > fav(a):
                if fav(b) >= tp_dist:
                    mfe = max(mfe, tp_dist)
                    if t_mfe1 is None and mfe >= risk:
                        t_mfe1 = tj
                    return done(tj, tp, "TP", j - j0 + 1)
                mfe = max(mfe, fav(b))
                if t_mfe1 is None and mfe >= risk:
                    t_mfe1 = tj
            else:
                if fav(b) <= -risk:
                    mae = max(mae, risk)
                    if t_mae05 is None:
                        t_mae05 = tj
                    return done(tj, sl, "SL", j - j0 + 1)
                mae = max(mae, -fav(b))
                if t_mae05 is None and mae >= 0.5 * risk:
                    t_mae05 = tj
        prev_t = tj
        j += 1
    return done(m1t[-1], m1c[-1], "end_of_data", n - j0)


# ----------------------------------------------------------------------------
# the strategy
# ----------------------------------------------------------------------------
def session_of(hour_utc):
    if hour_utc < 7:
        return "Asia 00-07 UTC"
    if hour_utc < 12:
        return "London 07-12 UTC"
    if hour_utc < 16:
        return "Overlap 12-16 UTC"
    if hour_utc < 21:
        return "New York 16-21 UTC"
    return "Close 21-24 UTC"


def run(data, params=None, verbose=True):
    p = dict(DEFAULTS)
    if params:
        p.update(params)
    D = data if isinstance(data, dict) else prepare(data, p["tf_min"], p["tz_offset_min"])
    tf_ms = D["tf_min"] * 60000
    t, o, h, l, c, v, day = D["t"], D["o"], D["h"], D["l"], D["c"], D["v"], D["day"]
    atr, atr_med = D["atr"], D["atr_med"]
    atr_pct = D["atr_pct"].get(p["vol_window"]) if p["vol_filter"] != "none" else None
    m1t = D["m1t"]
    max_gap_ms = p["max_gap_days"] * 86400000

    zones = None
    acc_hi, acc_lo, acc_vol = [], [], []
    acc_day = None
    acc_bars = 0
    days_skipped_short = 0
    days_built = 0
    stale_days = set()
    trades, skipped = [], []
    blocked = dict(min_risk=0, target=0, vol=0, session=0, tap_timing=0, reconfirm_invalidated=0, entry_filter=0)
    pos_exit_t = -1  # ms of the M1 bar in which the open position exited
    prior_R = np.nan
    trades_today = 0
    today = None
    day_start_bar = 0
    N = len(t)

    for i in range(N):
        d = day[i]
        if acc_day is not None and d != acc_day:
            hours = acc_bars * D["tf_min"] / 60.0
            if hours >= p["min_hours"] and acc_bars > 0:
                z = build_zones(np.array(acc_hi), np.array(acc_lo), np.array(acc_vol), p)
                if z is not None:
                    days_built += 1
                    zl = []
                    for zz in z["zones"]:
                        zz = dict(zz)
                        zz.update(tap_bar=-1, trades=0, taps=0, tap_hi=np.nan, tap_lo=np.nan, tap_close=np.nan,
                                  pend_side=None, pend_bar=-1,
                                  # V3 pre-entry interaction state (never affects the V1 signal)
                                  ep_active=False, ep_start=-1, ep_touches=0, ep_inside=0, ep_taps=0, ep_min=np.nan,
                                  ep_max=np.nan, ep_rej=0, ep_prev_pos=None, touches_today=0, inside_today=0,
                                  above_run=False, below_run=False, failed_up=0, failed_down=0, poc_side=0,
                                  poc_cross_bars=[])
                        zl.append(zz)
                    zones = dict(built_day=acc_day, pdh=z["pdh"], pdl=z["pdl"], day_range=z["day_range"],
                                 bin_size=z["bin_size"], zlist=zl, profile_bars=acc_bars)
            else:
                days_skipped_short += 1
            acc_hi, acc_lo, acc_vol = [], [], []
            acc_bars = 0
        if acc_day != d:
            acc_day = d
        acc_hi.append(h[i])
        acc_lo.append(l[i])
        acc_vol.append(v[i])
        acc_bars += 1
        if today != d:
            today = d
            trades_today = 0
            day_start_bar = i

        if zones is None:
            continue
        if d - zones["built_day"] > p["max_stale_days"]:
            stale_days.add(int(d))
            continue

        flat = pos_exit_t < t[i] + tf_ms
        sig = None
        for k, z in enumerate(zones["zlist"]):
            prior_tap = z["tap_bar"]                   # last tap on an EARLIER bar
            tapped_now = l[i] <= z["poc"] <= h[i]
            if tapped_now:
                z["tap_bar"] = i
                z["taps"] += 1
                z["tap_hi"], z["tap_lo"], z["tap_close"] = h[i], l[i], c[i]
            # ---- V3 interaction bookkeeping (uses only bars <= i; never touches the signal) ----
            zh_ = z["top"] - z["bot"]
            overlap = h[i] >= z["bot"] and l[i] <= z["top"]
            inside_close = z["bot"] <= c[i] <= z["top"]
            if l[i] > z["top"] + zh_ or h[i] < z["bot"] - zh_:
                z["ep_active"] = False
            if overlap and not z["ep_active"]:
                z.update(ep_active=True, ep_start=i, ep_touches=0, ep_inside=0, ep_taps=0, ep_min=l[i], ep_max=h[i],
                         ep_rej=0, ep_prev_pos=None)
            if z["ep_active"]:
                if overlap:
                    z["ep_touches"] += 1
                if inside_close:
                    z["ep_inside"] += 1
                if tapped_now:
                    z["ep_taps"] += 1
                z["ep_min"] = min(z["ep_min"], l[i])
                z["ep_max"] = max(z["ep_max"], h[i])
                pos_now = "in" if inside_close else ("above" if c[i] > z["top"] else "below")
                if z["ep_prev_pos"] is not None and z["ep_prev_pos"] != "in" and pos_now == "in":
                    z["ep_rej"] += 1
                z["ep_prev_pos"] = pos_now
            if overlap:
                z["touches_today"] += 1
            if inside_close:
                z["inside_today"] += 1
            if c[i] > z["top"]:
                z["above_run"] = True
            elif z["above_run"]:
                z["failed_up"] += 1
                z["above_run"] = False
            if c[i] < z["bot"]:
                z["below_run"] = True
            elif z["below_run"]:
                z["failed_down"] += 1
                z["below_run"] = False
            side_now = 1 if c[i] > z["poc"] else -1
            if z["poc_side"] != 0 and side_now != z["poc_side"]:
                z["poc_cross_bars"].append(i)
            z["poc_side"] = side_now
            if p["tap_timing"] == "same_only":
                has_tap = tapped_now
            elif p["tap_timing"] == "earlier_only":
                has_tap = prior_tap >= 0 and i - prior_tap < p["tap_valid"]
            else:
                has_tap = z["tap_bar"] >= 0 and i - z["tap_bar"] < p["tap_valid"]
            if not p["require_tap"]:
                has_tap = True
            can_use = (p["trade_edge"] or z["kind"] == "HVN") and z["trades"] < p["max_per_zone"]
            green = c[i] > o[i] or not p["require_colour"]
            red = c[i] < o[i] or not p["require_colour"]
            v1_long = has_tap and can_use and p["allow_long"] and green and c[i] > z["top"]
            v1_short = has_tap and can_use and p["allow_short"] and red and c[i] < z["bot"]
            if p["confirm_bars"] <= 1:
                side_here = "long" if v1_long else "short" if v1_short else None
            else:
                side_here = None
                if z["pend_bar"] == i - 1 and can_use:
                    beyond = c[i] > z["top"] if z["pend_side"] == "long" else c[i] < z["bot"]
                    if beyond:
                        side_here = z["pend_side"]
                    else:
                        blocked["reconfirm_invalidated"] += 1
                    z["pend_bar"], z["pend_side"] = -1, None
                if side_here is None and (v1_long or v1_short):
                    z["pend_side"], z["pend_bar"] = ("long" if v1_long else "short"), i
            if side_here == "long":
                if sig is None or z["top"] > sig[1]["top"]:
                    sig = ("long", z, k)
            elif side_here == "short":
                if sig is None or z["bot"] < sig[1]["bot"]:
                    sig = ("short", z, k)
        if sig is None:
            continue
        side, z, k = sig
        sgn = 1.0 if side == "long" else -1.0
        sl = z["bot"] - p["sl_buf"] if side == "long" else z["top"] + p["sl_buf"]
        entry = c[i]
        if p["fixed_sl_usd"] > 0:
            sl = entry - sgn * p["fixed_sl_usd"]
        risk = (entry - sl) * sgn
        if not risk > 0:
            continue
        tp = entry + sgn * p["rr"] * risk
        atr_i = atr[i - 1] if i > 0 and not math.isnan(atr[i - 1]) else np.nan
        ts_utc = pd.Timestamp(t[i], unit="ms")
        sess = session_of(ts_utc.hour)
        # ---- V2 filters (the rectangle is NOT consumed by a filtered setup) --------
        if p["min_risk_usd"] > 0 and risk < p["min_risk_usd"]:
            blocked["min_risk"] += 1
            continue
        if p["min_risk_atr"] > 0 and (math.isnan(atr_i) or risk < p["min_risk_atr"] * atr_i):
            blocked["min_risk"] += 1
            continue
        if p["target_rule"] != "none":
            beyond_by = (tp - zones["pdh"]) if side == "long" else (zones["pdl"] - tp)
            if beyond_by < p["target_margin_R"] * risk:
                blocked["target"] += 1
                continue
        if p["vol_filter"] != "none":
            pr = atr_pct[i - 1] if i > 0 else np.nan
            if math.isnan(pr) or pr < p["vol_low_pct"] / 100.0 or \
                    (p["vol_filter"] == "avoid_low_high" and pr > p["vol_high_pct"] / 100.0):
                blocked["vol"] += 1
                continue
        if p["session_filter"] is not None and sess not in p["session_filter"]:
            blocked["session"] += 1
            continue
        zh = z["top"] - z["bot"]
        # ---- features known at signal time ---------------------------------
        others = [zz for kk, zz in enumerate(zones["zlist"]) if kk != k]
        if others:
            gaps = [max(zz["bot"] - z["top"], z["bot"] - zz["top"]) for zz in others]
            nearest_gap = min(gaps)
        else:
            nearest_gap = np.nan
        tap_depth = (z["poc"] - z["tap_lo"]) / zh if side == "long" else (z["tap_hi"] - z["poc"]) / zh
        tap_closed_inside = z["bot"] <= z["tap_close"] <= z["top"]
        conf_range = h[i] - l[i]
        conf_body = abs(c[i] - o[i])
        conf_ext = (c[i] - z["top"]) / zh if side == "long" else (z["bot"] - c[i]) / zh
        dist_poc = (entry - z["poc"]) * sgn
        room_pdhl = (zones["pdh"] - entry) / risk if side == "long" else (entry - zones["pdl"]) / risk
        tp_beyond_pdhl = tp > zones["pdh"] if side == "long" else tp < zones["pdl"]
        ts_ist = ts_utc + pd.Timedelta(minutes=D["tz_offset_min"])
        rank_by_price = sorted(range(len(zones["zlist"])), key=lambda kk: zones["zlist"][kk]["poc"]).index(k)
        rec = dict(
            time_ist=ts_ist.strftime("%Y-%m-%d %H:%M"), time_utc=ts_utc.strftime("%Y-%m-%d %H:%M"), t_ms=int(t[i]),
            year=ts_ist.year, month=ts_ist.strftime("%Y-%m"), dow=ts_ist.strftime("%a"),
            hour_ist=ts_ist.hour, hour_utc=ts_utc.hour, session=sess,
            side=side, zone_kind=z["kind"], zone_top=z["top"], zone_bot=z["bot"], poc=z["poc"],
            zone_height=zh, day_range=zones["day_range"], zone_h_pct_range=zh / zones["day_range"],
            zone_share=z["share"], zone_prom_rel=z["prom_rel"], zone_peak_share=z["peak_share"],
            poc_pos_in_zone=(z["poc"] - z["bot"]) / zh,
            n_zones=len(zones["zlist"]), zone_rank_by_price=rank_by_price, nearest_gap_pts=nearest_gap,
            nearest_gap_zh=nearest_gap / zh if not math.isnan(nearest_gap) else np.nan,
            taps=z["taps"], first_touch=z["taps"] == 1, bars_since_tap=i - z["tap_bar"],
            tap_depth_zh=tap_depth, tap_closed_inside=tap_closed_inside,
            conf_range=conf_range, conf_body=conf_body, conf_range_zh=conf_range / zh,
            conf_range_atr=conf_range / atr_i if atr_i and atr_i > 0 else np.nan,
            conf_ext_zh=conf_ext, conf_body_pct=conf_body / conf_range if conf_range > 0 else np.nan,
            entry=entry, sl=sl, tp=tp, risk_pts=risk, risk_zh=risk / zh,
            risk_atr=risk / atr_i if atr_i and atr_i > 0 else np.nan, atr14=atr_i,
            atr_rel=atr_i / atr_med[i - 1] if i > 0 and atr_med[i - 1] and atr_med[i - 1] > 0 else np.nan,
            atr_pct7=D["atr_pct"][2016][i - 1] if i > 0 else np.nan,
            entry_dist_poc_pts=dist_poc, entry_dist_poc_zh=dist_poc / zh, entry_dist_poc_R=dist_poc / risk,
            pdh=zones["pdh"], pdl=zones["pdl"], room_to_pdhl_R=room_pdhl, tp_beyond_pdhl=tp_beyond_pdhl,
            prior_trades_today=trades_today, prior_R=prior_R,
        )
        # ---- V3 pre-entry features (bars <= i only) ---------------------------
        rng_i = conf_range if conf_range > 0 else np.nan
        a_ = atr_i if atr_i and atr_i > 0 else np.nan
        ep_bars = i - z["ep_start"] + 1 if z["ep_active"] else 0
        pen_depth = ((z["top"] - z["ep_min"]) if side == "long" else (z["ep_max"] - z["bot"])) / zh if z["ep_active"] else np.nan
        failed_same = z["failed_up"] if side == "long" else z["failed_down"]
        failed_opp = z["failed_down"] if side == "long" else z["failed_up"]
        poc_crosses_12 = sum(1 for b in z["poc_cross_bars"] if b >= i - 11)
        if pen_depth >= 1.0:
            poc_type = "E deep cross"
        elif z["taps"] >= 3:
            poc_type = "D multiple taps"
        elif z["ep_rej"] >= 1:
            poc_type = "B reject-return"
        elif z["ep_inside"] >= 3:
            poc_type = "C several bars inside"
        elif (i - z["tap_bar"]) == 0 and ep_bars <= 2:
            poc_type = "A touch and go"
        else:
            poc_type = "other"
        # confirmation candle anatomy in the trade direction
        close_pos = ((c[i] - l[i]) if side == "long" else (h[i] - c[i])) / rng_i if rng_i else np.nan
        wick_against = ((h[i] - max(o[i], c[i])) if side == "long" else (min(o[i], c[i]) - l[i])) / rng_i if rng_i else np.nan
        wick_with = ((min(o[i], c[i]) - l[i]) if side == "long" else (h[i] - max(o[i], c[i]))) / rng_i if rng_i else np.nan
        # momentum / structure before the confirmation candle (bars i-1 and earlier)
        def cs(k1, k2):
            return (c[i - k1] - c[i - k2]) * sgn / a_ if i - k2 >= 0 and a_ else np.nan
        prev_same = ((c[i - 1] > o[i - 1]) if side == "long" else (c[i - 1] < o[i - 1])) if i >= 1 else False
        same5 = sum(1 for q in range(max(0, i - 5), i) if ((c[q] > o[q]) if side == "long" else (c[q] < o[q])))
        alt6 = sum(1 for q in range(max(1, i - 6), i) if (c[q] > o[q]) != (c[q - 1] > o[q - 1]))
        if i >= 20:
            struct20 = ((max(h[i - 20:i]) - c[i]) if side == "long" else (c[i] - min(l[i - 20:i]))) / a_ if a_ else np.nan
        else:
            struct20 = np.nan
        if i >= 50:
            struct50 = ((max(h[i - 50:i]) - c[i]) if side == "long" else (c[i] - min(l[i - 50:i]))) / a_ if a_ else np.nan
        else:
            struct50 = np.nan
        approach_speed = abs(c[i - 1] - c[i - 6]) / a_ if i >= 6 and a_ else np.nan
        # location and opposing structure
        pr_ = zones["pdh"] - zones["pdl"]
        opp = None
        for zz in others:
            if side == "long" and zz["bot"] > entry and (opp is None or zz["bot"] < opp):
                opp = zz["bot"]
            if side == "short" and zz["top"] < entry and (opp is None or zz["top"] > opp):
                opp = zz["top"]
        opp_gap_R = ((opp - entry) if side == "long" else (entry - opp)) / risk if opp is not None else np.nan
        rec.update(
            tap_close_dist_poc_zh=(z["tap_close"] - z["poc"]) * sgn / zh, pen_depth_zh=pen_depth,
            ep_bars=ep_bars, ep_inside=z["ep_inside"], ep_touches=z["ep_touches"], ep_taps=z["ep_taps"], ep_rej=z["ep_rej"],
            touches_today=z["touches_today"], inside_today=z["inside_today"], failed_same=failed_same, failed_opp=failed_opp,
            poc_crosses_12=poc_crosses_12, poc_type=poc_type,
            conf_close_pos=close_pos, conf_wick_against_pct=wick_against, conf_wick_with_pct=wick_with,
            conf_body_atr=conf_body / a_ if a_ else np.nan, conf_ext_atr=(conf_ext * zh) / a_ if a_ else np.nan,
            zone_height_atr=zh / a_ if a_ else np.nan,
            prev_same_dir=prev_same, mom3_atr=cs(1, 4), mom5_atr=cs(1, 6), same_dir_last5=same5, alternations6=alt6,
            trend20_atr=cs(1, 21), struct20_atr=struct20, struct50_atr=struct50, approach_speed_atr=approach_speed,
            bars_into_day=i - day_start_bar, atr_pct30=D["atr_pct"][8640][i - 1] if i > 0 else np.nan,
            zone_pos_range=(z["poc"] - zones["pdl"]) / pr_ if pr_ > 0 else np.nan,
            dist_pdh_zh=(zones["pdh"] - z["top"]) / zh, dist_pdl_zh=(z["bot"] - zones["pdl"]) / zh,
            opp_gap_R=opp_gap_R, tp_clear=(opp is None) or (opp_gap_R > p["rr"]),
        )
        if p["entry_filter"] is not None and not p["entry_filter"](rec):
            blocked["entry_filter"] += 1
            continue
        # ---- outcome ---------------------------------------------------------
        j0 = int(np.searchsorted(m1t, t[i] + tf_ms))
        mg = None
        if p["fb_exit_closes"] > 0:
            mg = dict(i=i, top=z["top"], bot=z["bot"], closes=p["fb_exit_closes"], window=p["fb_window"])
        if flat or p["simulate_skipped"]:
            if p["exit_spec"] is not None:
                import exit_sim
                xw = exit_sim.walk(side, entry, sl, risk, j0, i, D, p["exit_spec"], max_gap_ms, atr=atr_i)
                ex = dict(exit_t=xw["exit_t"], exit_px=entry + sgn * xw["R"] * risk, reason=xw["reason"],
                          mfe=xw["mfe"] * risk, mae=xw["mae"] * risk, bars=xw["bars"], t_mae05=None, t_mfe1=None)
            else:
                ex = simulate_exit(side, entry, sl, tp, j0, D, max_gap_ms, mg)
            R = (ex["exit_px"] - entry) * sgn / risk
            fb = False
            for q in range(i + 1, min(N, i + 4)):
                if t[q] > ex["exit_t"]:
                    break
                if (side == "long" and c[q] <= z["top"]) or (side == "short" and c[q] >= z["bot"]):
                    fb = True
                    break
            spread = SPREAD_BY_YEAR.get(ts_ist.year, 0.4)
            rec.update(
                exit_time_utc=pd.Timestamp(ex["exit_t"], unit="ms").strftime("%Y-%m-%d %H:%M"),
                exit_price=ex["exit_px"], exit_reason=ex["reason"], result_R=R,
                win=R > 0, mfe_R=ex["mfe"] / risk, mae_R=ex["mae"] / risk, minutes_held=ex["bars"],
                min_to_mae05=(ex["t_mae05"] - t[i]) / 60000 if ex["t_mae05"] is not None else np.nan,
                min_to_mfe1=(ex["t_mfe1"] - t[i]) / 60000 if ex["t_mfe1"] is not None else np.nan,
                false_breakout_3bars=fb, cost_R=spread / risk, net_R=R - spread / risk, taken=flat,
            )
        if flat:
            z["trades"] += 1
            z["tap_bar"] = -1
            pos_exit_t = ex["exit_t"]
            trades.append(rec)
            prior_R = R
            trades_today += 1
        else:
            skipped.append(rec)

    info = dict(days_built=days_built, days_skipped_short=days_skipped_short, stale_days=len(stale_days),
                bars=N, m1_bars=D["n_m1"], first=str(pd.Timestamp(t[0], unit="ms")), last=str(pd.Timestamp(t[-1], unit="ms")),
                blocked=blocked, skipped_signals=len(skipped))
    if verbose:
        print(info)
    return pd.DataFrame(trades), pd.DataFrame(skipped), info
