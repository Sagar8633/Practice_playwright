"""Weekly Market/Volume Profile value area for XAUUSD.

Definition (pre-registered)
---------------------------
* Week            : Sunday 21:00 UTC -> next Sunday 21:00 UTC (gold's trading week).
* Price bins      : width = round(0.00025 * first close of the week, 2), floored at 0.10 USD
                    (about 0.45 USD at 1,800, 1.10 USD at 4,500) so the bin count is regime-neutral.
* Volume source   : "duka" = Dukascopy traded volume on M1 bars (primary, "real volume from one venue"),
                    "tick" = XM MT5 tick volume on M15 bars (sensitivity),
                    "tpo"  = time-price-opportunity count on M15 bars (classic Market Profile).
* Distribution    : a bar's volume is spread uniformly over every bin its [low, high] touches.
* Value area      : 70% of the week's volume around the POC, expanded two bins at a time toward
                    the side with more volume (CBOT method).  VAH = top edge of the highest bin
                    in the area, VAL = bottom edge of the lowest bin.
* Usage           : PREVIOUS COMPLETED week's VAH/VAL/POC are the reference levels for the whole of
                    the current week (no look-ahead).  The developing current-week VA is also
                    recorded per bar (computed from bars up to and including that bar) as a
                    sensitivity variant.
"""
import numpy as np
import pandas as pd


def _bin_width(px: float) -> float:
    return max(0.10, round(0.00025 * px, 2))


def _value_area(vol: np.ndarray, pct: float = 0.70):
    n = len(vol)
    total = vol.sum()
    if total <= 0 or n == 0:
        return None
    poc = int(np.argmax(vol))
    lo = hi = poc
    acc = vol[poc]
    target = pct * total
    while acc < target:
        up = -1.0
        dn = -1.0
        if hi + 1 < n:
            up = vol[hi + 1] + (vol[hi + 2] if hi + 2 < n else 0.0)
        if lo - 1 >= 0:
            dn = vol[lo - 1] + (vol[lo - 2] if lo - 2 >= 0 else 0.0)
        if up < 0 and dn < 0:
            break
        if up >= dn:
            step = 2 if hi + 2 < n else 1
            acc += vol[hi + 1:hi + 1 + step].sum()
            hi += step
        else:
            step = 2 if lo - 2 >= 0 else 1
            acc += vol[lo - step:lo].sum()
            lo -= step
    return poc, lo, hi


def _profile_diff(lows, highs, vols, p0, bw, nb):
    """Uniform distribution of each bar's volume over the bins it spans, via a difference array."""
    b_lo = np.clip(((lows - p0) / bw).astype(int), 0, nb - 1)
    b_hi = np.clip(((highs - p0) / bw).astype(int), 0, nb - 1)
    per = vols / (b_hi - b_lo + 1)
    d = np.zeros(nb + 1)
    np.add.at(d, b_lo, per)
    np.add.at(d, b_hi + 1, -per)
    return np.cumsum(d)[:nb]


def weekly_profiles(m1: pd.DataFrame, m15: pd.DataFrame, source: str = "duka", va_pct: float = 0.70) -> pd.DataFrame:
    if source == "duka":
        src = m1[["time", "high", "low", "volume"]].copy()
        sh = src["time"] + pd.Timedelta(hours=3)
        src["week"] = (sh - pd.to_timedelta(sh.dt.dayofweek, unit="D")).dt.normalize()
        src["v"] = src["volume"].values
    else:
        src = m15[["time", "high", "low", "week", "tick_volume"]].copy()
        src["v"] = src["tick_volume"].values if source == "tick" else 1.0
    rows = []
    min_rows = 3 * 1440 * 0.6 if source == "duka" else 3 * 96   # at least ~3 trading days
    for wk, g in src.groupby("week", sort=True):
        if len(g) < min_rows:
            continue
        lo = g["low"].values; hi = g["high"].values; v = g["v"].values.astype(float)
        p0 = float(lo.min()); p1 = float(hi.max())
        bw = _bin_width(float(g["high"].values[0]))
        nb = int((p1 - p0) / bw) + 1
        vol = _profile_diff(lo, hi, v, p0, bw, nb)
        va = _value_area(vol, va_pct)
        if va is None:
            continue
        poc, blo, bhi = va
        rows.append(dict(week=wk, poc=p0 + (poc + 0.5) * bw, val=p0 + blo * bw, vah=p0 + (bhi + 1) * bw,
                         whigh=p1, wlow=p0, total=float(v.sum()), bins=nb, bw=bw,
                         hours=float(len(g)) * (1 / 60 if source == "duka" else 0.25)))
    return pd.DataFrame(rows)


def add_prev_week_levels(m15: pd.DataFrame, prof: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Attach the previous completed week's levels to every bar of the following week."""
    p = prof.copy()
    p["week_next"] = p["week"] + pd.Timedelta(days=7)
    cols = {"vah": f"vah_{suffix}", "val": f"val_{suffix}", "poc": f"poc_{suffix}",
            "whigh": f"whigh_{suffix}", "wlow": f"wlow_{suffix}"}
    p = p[["week_next"] + list(cols)].rename(columns=cols)
    return m15.merge(p, left_on="week", right_on="week_next", how="left").drop(columns=["week_next"])


def developing_va(m15: pd.DataFrame, m1: pd.DataFrame, va_pct: float = 0.70):
    """Current-week value area recomputed at every M15 bar close from Dukascopy M1 volume
    (only bars up to and including the current one).  Returns arrays vah_dev, val_dev, poc_dev."""
    n = len(m15)
    vah = np.full(n, np.nan); val = np.full(n, np.nan); poc = np.full(n, np.nan)
    m1_lo = m1["low"].values; m1_hi = m1["high"].values; m1_v = m1["volume"].values.astype(float)
    weeks = m15["week"].values
    m1s = m15["m1_start"].values; m1n = m15["m1_next"].values
    i = 0
    while i < n:
        wk = weeks[i]
        j = i
        while j < n and weeks[j] == wk:
            j += 1
        # week bars i..j-1; fixed grid from the week's first close, wide enough for the week
        a = m1s[i]; b = m1n[j - 1]
        if b <= a:
            i = j
            continue
        p0 = float(m1_lo[a:b].min()) - 1.0
        p1 = float(m1_hi[a:b].max()) + 1.0
        bw = _bin_width(float(m1_hi[a]))
        nb = int((p1 - p0) / bw) + 2
        d = np.zeros(nb + 1)
        for k in range(i, j):
            s, e = m1s[k], m1n[k]
            if e > s:
                lo = m1_lo[s:e]; hi = m1_hi[s:e]; v = m1_v[s:e]
                b_lo = np.clip(((lo - p0) / bw).astype(int), 0, nb - 1)
                b_hi = np.clip(((hi - p0) / bw).astype(int), 0, nb - 1)
                per = v / (b_hi - b_lo + 1)
                np.add.at(d, b_lo, per)
                np.add.at(d, b_hi + 1, -per)
            vol = np.cumsum(d)[:nb]
            va = _value_area(vol, va_pct)
            if va is not None:
                pc, blo, bhi = va
                poc[k] = p0 + (pc + 0.5) * bw
                val[k] = p0 + blo * bw
                vah[k] = p0 + (bhi + 1) * bw
        i = j
    return vah, val, poc


def add_value_areas(m1: pd.DataFrame, m15: pd.DataFrame) -> pd.DataFrame:
    out = m15.copy()
    profs = {}
    for src in ("duka", "tick", "tpo"):
        prof = weekly_profiles(m1, m15, src)
        profs[src] = prof
        out = add_prev_week_levels(out, prof, src)
    vah, val, poc = developing_va(m15, m1)
    out["vah_dev"] = vah; out["val_dev"] = val; out["poc_dev"] = poc
    # primary aliases
    out["vah"] = out["vah_duka"]; out["val"] = out["val_duka"]; out["poc"] = out["poc_duka"]
    return out, profs


if __name__ == "__main__":
    import os, time as _t
    from pbd.data import build, CACHE
    t0 = _t.time()
    m1, m15 = build()
    out, profs = add_value_areas(m1, m15)
    out.to_pickle(os.path.join(CACHE, "m15_va.pkl"))
    for k, p in profs.items():
        p.to_csv(os.path.join(CACHE, f"weekly_profile_{k}.csv"), index=False)
    print("weeks:", {k: len(p) for k, p in profs.items()})
    print(out[["time", "close", "vah", "val", "poc", "vah_tick", "val_tick", "vah_tpo", "val_tpo", "vah_dev", "val_dev"]].dropna().tail(3).to_string())
    d = out.dropna(subset=["vah", "vah_tick", "vah_tpo"])
    print("VAH duka vs tick median abs diff (USD):", (d["vah"] - d["vah_tick"]).abs().median().round(2),
          "| duka vs tpo:", (d["vah"] - d["vah_tpo"]).abs().median().round(2))
    print("VA width / weekly range median:", ((d["vah"] - d["val"]) / (d["whigh_duka"] - d["wlow_duka"])).median().round(3))
    print("bars with prev-week VA:", out["vah"].notna().mean().round(3))
    print("%.1fs" % (_t.time() - t0))
