"""Python replica of XAU_Liquidity_Sweeps.pine + trade simulation on the M1 path.

Data: Vaibhav/research/data/m1_server.npz (Dukascopy XAUUSD M1 bid, XM server time = Europe/Athens).
Costs: XM spread model (points by year x server hour) + slippage, both in USD per oz.

The indicator logic mirrors the Pine file bar for bar:
  * swings via pivot(L, R) confirmed R bars late, EQ clustering at the extreme within a tolerance
  * PDH/PDL and PWH/PWL on the New York calendar day/week, Asia/London/NY previous-session H/L
  * sweep state machine: penetration >= minPen -> candidate; close back inside by > buf within
    `window` bars = SWEPT; `accept` closes beyond = BREAK; window expiry resolves by last close side.
"""
import json, os
import numpy as np
import pandas as pd

ROOT = "D:/Practice_Playwright"
M1_NPZ = f"{ROOT}/Vaibhav/research/data/m1_server.npz"
SPREAD_JSON = f"{ROOT}/Vaibhav/research/data/spread_model.json"

TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


# ------------------------------------------------------------------ time helpers
def _last_sunday(y, m):
    d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
    return d - pd.Timedelta(days=(d.weekday() + 1) % 7)


def server_to_utc(server: pd.Series) -> pd.Series:
    """XM server time (EET/EEST) -> naive UTC."""
    out = server.copy()
    for y in server.dt.year.unique():
        a = _last_sunday(y, 3) + pd.Timedelta(hours=3)   # 01:00 UTC = 03:00 EET
        b = _last_sunday(y, 10) + pd.Timedelta(hours=4)  # 01:00 UTC = 04:00 EEST
        m = server.dt.year == y
        dst = (server[m] >= a) & (server[m] < b)
        out[m] = server[m] - pd.to_timedelta(np.where(dst, 3, 2), unit="h")
    return out


def load_m1(start="2024-09-01", end="2026-09-26") -> pd.DataFrame:
    z = np.load(M1_NPZ)
    t = pd.to_datetime(z["t"], unit="s")
    df = pd.DataFrame({"time": t, "open": z["o"], "high": z["h"], "low": z["l"], "close": z["c"], "vol": z["v"]})
    df = df[(df.time >= start) & (df.time < end)].reset_index(drop=True)
    df["utc"] = server_to_utc(df["time"])
    return df


def resample(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if minutes == 1:
        d = m1.copy()
    else:
        rule = "1D" if minutes == 1440 else f"{minutes}min"
        g = m1.set_index("time").resample(rule, label="left", closed="left")
        d = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "vol": "sum"}).dropna().reset_index()
        d["utc"] = server_to_utc(d["time"])
    u = d["utc"].dt.tz_localize("UTC")
    ny = u.dt.tz_convert("America/New_York")
    lon = u.dt.tz_convert("Europe/London")
    tok = u.dt.tz_convert("Asia/Tokyo")
    d["ny_h"] = (ny.dt.hour + ny.dt.minute / 60).values
    d["ny_day"] = (ny.dt.year * 10000 + ny.dt.month * 100 + ny.dt.day).values
    iso = ny.dt.isocalendar()
    d["ny_week"] = (iso.year * 100 + iso.week).values
    lh = (lon.dt.hour + lon.dt.minute / 60).values
    th = (tok.dt.hour + tok.dt.minute / 60).values
    nh = d["ny_h"].values
    d["in_asia"] = (th >= 9) & (th < 15)
    d["in_lon"] = (lh >= 8) & (lh < 16.5)
    d["in_ny"] = (nh >= 8) & (nh < 17)
    d["session"] = np.where(d.in_lon & d.in_ny, "overlap", np.where(d.in_lon, "london", np.where(d.in_ny, "newyork", np.where(d.in_asia, "asia", "off"))))
    d["atr"] = atr_wilder(d.high.values, d.low.values, d.close.values, 14)
    d["server_hour"] = d["time"].dt.hour.values
    d["year"] = d["time"].dt.year.values
    return d


def atr_wilder(h, l, c, n=14):
    tr = np.empty(len(h)); tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    a = np.full(len(h), np.nan)
    if len(h) >= n:
        a[n - 1] = tr[:n].mean()
        for i in range(n, len(h)):
            a[i] = (a[i - 1] * (n - 1) + tr[i]) / n
    return a


def pivots(x, L, R, high=True):
    """Return array p where p[i] = pivot price confirmed at bar i (pivot bar i-R), else nan. Strict on both sides."""
    n = len(x); out = np.full(n, np.nan)
    for i in range(L + R, n):
        c = i - R; v = x[c]
        if high:
            if v > x[c - L:c].max() and v > x[c + 1:i + 1].max(): out[i] = v
        else:
            if v < x[c - L:c].min() and v < x[c + 1:i + 1].min(): out[i] = v
    return out


# ------------------------------------------------------------------ indicator replica
KEY_KINDS = {"PDH", "PDL", "PWH", "PWL", "ASIA-H", "ASIA-L", "LON-H", "LON-L", "NY-H", "NY-L"}

DEFAULT = dict(swL=10, swR=10, maxSide=8, maxAge=600, eqOn=True, tolMode="ATR", tolUsd=0.5, tolAtr=0.15,
               pdOn=True, pwOn=True, asiaOn=True, lonOn=True, nyOn=False,
               minPen=0.10, buf=0.03, penMode="ATR", window=3, accept=2)


def detect_events(d: pd.DataFrame, P: dict) -> pd.DataFrame:
    """Run the pool registry + sweep state machine over TF bars. Returns one row per resolved pool."""
    h, l, c = d.high.values, d.low.values, d.close.values
    atr = d.atr.values
    ph = pivots(h, P["swL"], P["swR"], True)
    pl = pivots(l, P["swL"], P["swR"], False)
    ny_day, ny_week = d.ny_day.values, d.ny_week.values
    in_a, in_l, in_n = d.in_asia.values, d.in_lon.values, d.in_ny.values
    n = len(d)
    pools = []   # dicts: price, side, kind, touches, startBar, state, penBar, extreme, closesBeyond
    events = []
    dHi = dLo = wHi = wLo = np.nan
    aHi = aLo = lHi = lLo = nHi = nLo = np.nan

    def tol(i):
        return P["tolUsd"] if P["tolMode"] == "USD" else P["tolAtr"] * (atr[i] if not np.isnan(atr[i]) else P["tolUsd"])

    def pen_thr(i):
        a = atr[i] if not np.isnan(atr[i]) else 1.0
        if P["penMode"] == "USD": return P["minPen"], P["buf"]
        return P["minPen"] * a, P["buf"] * a

    def drop_kind(kind):
        pools[:] = [p for p in pools if not (p["kind"] == kind and p["state"] == 0)]

    def count_side(side):
        return sum(1 for p in pools if p["side"] == side and p["state"] == 0 and p["kind"] not in KEY_KINDS)

    def evict_oldest(side):
        cand = [p for p in pools if p["side"] == side and p["state"] == 0 and p["kind"] not in KEY_KINDS]
        if cand:
            pools.remove(min(cand, key=lambda p: p["startBar"]))

    def create(price, side, kind, startBar):
        pools.append(dict(price=price, side=side, kind=kind, touches=1, startBar=startBar, state=0, penBar=-1, extreme=np.nan, closesBeyond=0))

    def add_swing(price, side, startBar, i):
        if P["eqOn"]:
            t = tol(i)
            for p in pools:
                if p["side"] == side and p["state"] == 0 and p["kind"] not in KEY_KINDS and abs(p["price"] - price) <= t:
                    p["price"] = max(p["price"], price) if side == 1 else min(p["price"], price)
                    p["touches"] += 1
                    p["kind"] = "EQH" if side == 1 else "EQL"
                    return
        while count_side(side) >= P["maxSide"]:
            evict_oldest(side)
        create(price, side, "SH" if side == 1 else "SL", startBar)

    for i in range(n):
        # ---- calendar / session extremes (published on the boundary bar)
        pdh = pdl = pwh = pwl = ash = asl = lnh = lnl = nyh = nyl = np.nan
        newDay = i > 0 and ny_day[i] != ny_day[i - 1]
        newWeek = i > 0 and ny_week[i] != ny_week[i - 1]
        if newDay: pdh, pdl, dHi, dLo = dHi, dLo, h[i], l[i]
        else: dHi, dLo = np.fmax(dHi, h[i]), np.fmin(dLo, l[i])
        if newWeek: pwh, pwl, wHi, wLo = wHi, wLo, h[i], l[i]
        else: wHi, wLo = np.fmax(wHi, h[i]), np.fmin(wLo, l[i])
        aEnd = i > 0 and in_a[i - 1] and not in_a[i]
        lEnd = i > 0 and in_l[i - 1] and not in_l[i]
        nEnd = i > 0 and in_n[i - 1] and not in_n[i]
        if aEnd: ash, asl, aHi, aLo = aHi, aLo, np.nan, np.nan
        elif in_a[i]: aHi, aLo = np.fmax(aHi, h[i]), np.fmin(aLo, l[i])
        if lEnd: lnh, lnl, lHi, lLo = lHi, lLo, np.nan, np.nan
        elif in_l[i]: lHi, lLo = np.fmax(lHi, h[i]), np.fmin(lLo, l[i])
        if nEnd: nyh, nyl, nHi, nLo = nHi, nLo, np.nan, np.nan
        elif in_n[i]: nHi, nLo = np.fmax(nHi, h[i]), np.fmin(nLo, l[i])

        # ---- 1. swings
        if not np.isnan(ph[i]): add_swing(ph[i], 1, i - P["swR"], i)
        if not np.isnan(pl[i]): add_swing(pl[i], -1, i - P["swR"], i)
        # ---- 2. key levels
        for on, bnd, hi, lo, kh, kl in ((P["pdOn"], newDay, pdh, pdl, "PDH", "PDL"), (P["pwOn"], newWeek, pwh, pwl, "PWH", "PWL"),
                                        (P["asiaOn"], aEnd, ash, asl, "ASIA-H", "ASIA-L"), (P["lonOn"], lEnd, lnh, lnl, "LON-H", "LON-L"),
                                        (P["nyOn"], nEnd, nyh, nyl, "NY-H", "NY-L")):
            if on and bnd and not np.isnan(hi) and not np.isnan(lo):
                drop_kind(kh); create(hi, 1, kh, i); drop_kind(kl); create(lo, -1, kl, i)
        # ---- 3. state machine
        minPen, buf = pen_thr(i)
        keep = []
        for p in pools:
            dsg = p["side"]
            probe = h[i] if dsg == 1 else l[i]
            pen = (probe - p["price"]) * dsg
            resolved = False
            if p["state"] == 0 and pen >= minPen:
                p["state"] = 1; p["penBar"] = i; p["extreme"] = probe; p["closesBeyond"] = 0
            if p["state"] == 1:
                p["extreme"] = max(p["extreme"], h[i]) if dsg == 1 else min(p["extreme"], l[i])
                closeBeyond = (c[i] - p["price"]) * dsg > buf
                closeInside = (p["price"] - c[i]) * dsg > buf
                if closeBeyond: p["closesBeyond"] += 1
                age = i - p["penBar"] + 1
                newState = 0
                if closeInside: newState = 2
                elif p["closesBeyond"] >= P["accept"]: newState = 3
                elif age >= P["window"]: newState = 3 if (c[i] - p["price"]) * dsg > 0 else 2
                if newState:
                    resolved = True
                    events.append(dict(bar=i, time=d.time.values[i], side=dsg, kind=p["kind"], touches=p["touches"], level=p["price"],
                                       extreme=p["extreme"], depth=abs(p["extreme"] - p["price"]), depth_atr=abs(p["extreme"] - p["price"]) / atr[i] if atr[i] > 0 else np.nan,
                                       bars_held=age, close=c[i], atr=atr[i], swept=(newState == 2), session=d.session.values[i], ny_h=d.ny_h.values[i],
                                       age_bars=i - p["startBar"], level_start=p["startBar"]))
            if not resolved:
                if p["state"] == 0 and i - p["startBar"] > P["maxAge"]: continue
                keep.append(p)
        pools[:] = keep
    ev = pd.DataFrame(events)
    return ev


# ------------------------------------------------------------------ costs
_SPREAD = None
def spread_usd(year: int, server_hour: int) -> float:
    global _SPREAD
    if _SPREAD is None:
        _SPREAD = json.load(open(SPREAD_JSON))["model_points_by_year_hour"]
    row = _SPREAD.get(str(year)) or _SPREAD[max(_SPREAD)]
    v = row[server_hour]
    if v is None or (isinstance(v, float) and np.isnan(v)):
        v = np.nanmedian([x for x in row if x is not None])
    return float(v) / 100.0


# ------------------------------------------------------------------ trade simulation on M1 path
def simulate(ev: pd.DataFrame, m1: pd.DataFrame, tf_min: int, rr: float = 2.0, stop_pad_atr: float = 0.10,
             max_bars: int = 24, slippage: float = 0.10, direction="reversal") -> pd.DataFrame:
    """Enter at the close of the resolving bar of every SWEEP. Long after SSL sweep, short after BSL sweep
    (direction='reversal'). Stop beyond the wick extreme by stop_pad_atr * ATR. Target = rr * risk.
    Exits are first-passage on the M1 path; time exit after max_bars TF bars at the close.
    Net P&L in USD per oz: gross - spread(entry hour) - slippage."""
    if ev.empty: return pd.DataFrame()
    sw = ev[ev.swept].reset_index(drop=True)
    t1 = m1.time.values; h1 = m1.high.values; l1 = m1.low.values; c1 = m1.close.values
    rows = []
    for r in sw.itertuples():
        side = -r.side if direction == "reversal" else r.side   # SSL swept (side -1) -> long (+1)
        entry = r.close
        pad = stop_pad_atr * r.atr if r.atr == r.atr else 0.0
        stop = (r.extreme - pad) if side == 1 else (r.extreme + pad)
        risk = abs(entry - stop)
        if risk <= 0 or risk != risk: continue
        target = entry + side * rr * risk
        t_entry = np.datetime64(r.time) + np.timedelta64(tf_min, "m")
        i0 = np.searchsorted(t1, t_entry)
        t_end = t_entry + np.timedelta64(tf_min * max_bars, "m")
        i1 = np.searchsorted(t1, t_end)
        if i0 >= len(t1): continue
        hh = h1[i0:i1]; ll = l1[i0:i1]
        if side == 1:
            hit_t = np.nonzero(hh >= target)[0]; hit_s = np.nonzero(ll <= stop)[0]
        else:
            hit_t = np.nonzero(ll <= target)[0]; hit_s = np.nonzero(hh >= stop)[0]
        kt = hit_t[0] if len(hit_t) else 10**9
        ks = hit_s[0] if len(hit_s) else 10**9
        if kt == ks == 10**9:
            k = max(i1 - 1, i0); ex = c1[min(k, len(c1) - 1)]; how = "time"
        elif ks <= kt:          # same-bar tie goes to the stop (conservative)
            k = i0 + ks; ex = stop; how = "stop"
        else:
            k = i0 + kt; ex = target; how = "target"
        gross = (ex - entry) * side
        # MFE / MAE within the hold
        seg_h = h1[i0:k + 1]; seg_l = l1[i0:k + 1]
        mfe = (seg_h.max() - entry) if side == 1 else (entry - seg_l.min())
        mae = (entry - seg_l.min()) if side == 1 else (seg_h.max() - entry)
        ts = pd.Timestamp(r.time)
        cost = spread_usd(ts.year, ts.hour) + slippage
        net = gross - cost
        rows.append(dict(time=r.time, side=side, kind=r.kind, touches=r.touches, level=r.level, entry=entry, stop=stop, target=target,
                         risk=risk, risk_atr=risk / r.atr if r.atr else np.nan, exit=ex, how=how, gross=gross, cost=cost, net=net,
                         R=net / risk, gross_R=gross / risk, mfe_R=mfe / risk, mae_R=mae / risk, hold_min=(k - i0 + 1),
                         depth_atr=r.depth_atr, bars_held=r.bars_held, session=r.session, ny_h=r.ny_h, age_bars=r.age_bars))
    return pd.DataFrame(rows)


def metrics(tr: pd.DataFrame) -> dict:
    if tr is None or tr.empty:
        return dict(n=0)
    R = tr.R.values
    wins = R > 0
    gp = R[wins].sum(); gl = -R[~wins].sum()
    eq = np.cumsum(R); dd = (np.maximum.accumulate(eq) - eq).max() if len(eq) else 0
    se = R.std(ddof=1) / np.sqrt(len(R)) if len(R) > 1 else np.nan
    return dict(n=int(len(R)), win=float(wins.mean()), expR=float(R.mean()), ci_lo=float(R.mean() - 1.96 * se) if se == se else np.nan,
                ci_hi=float(R.mean() + 1.96 * se) if se == se else np.nan, pf=float(gp / gl) if gl > 0 else np.inf,
                totalR=float(R.sum()), maxdd_R=float(dd), gross_expR=float(tr.gross_R.mean()), cost_R=float((tr.cost / tr.risk).mean()),
                med_risk=float(tr.risk.median()), med_hold_min=float(tr.hold_min.median()),
                mfe1=float((tr.mfe_R >= 1).mean()), mfe2=float((tr.mfe_R >= 2).mean()))
