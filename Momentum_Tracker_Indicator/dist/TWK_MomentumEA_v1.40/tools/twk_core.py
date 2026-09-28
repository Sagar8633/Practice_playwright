"""Line-for-line Python mirror of TWK_Core.mqh.

Used for the two-legged Pine-vs-MT5 validation:
  1. Pine == this port, on TradingView bars (compare_tv.py)
  2. this port == MQL5, on MT5 bars from the TWK_Tracker_MT5 CSV (compare_mt5.py)
Keep every formula identical to TWK_Core.mqh.
"""
NA = None

TIE_LEFT_EQUAL_OK, TIE_STRICT, TIE_RIGHT_EQUAL_OK = 0, 1, 2


def sma(src, length):
    out = [NA] * len(src)
    for i in range(length - 1, len(src)):
        w = src[i - length + 1:i + 1]
        if all(v is not NA for v in w):
            out[i] = sum(w) / length
    return out


def rma(src, length):
    s = sma(src, length)
    out = [NA] * len(src)
    a = 1.0 / length
    for i in range(len(src)):
        prev = out[i - 1] if i > 0 else NA
        if prev is NA:
            out[i] = s[i]
        else:
            out[i] = NA if src[i] is NA else a * src[i] + (1 - a) * prev
    return out


def true_range(o, h, l, c, handle_na):
    out = []
    for i in range(len(c)):
        if i == 0:
            out.append(h[0] - l[0] if handle_na else NA)
        else:
            pc = c[i - 1]
            out.append(max(h[i] - l[i], abs(h[i] - pc), abs(l[i] - pc)))
    return out


def supertrend(o, h, l, c, factor, atr_len):
    atr = rma(true_range(o, h, l, c, True), atr_len)
    n = len(c)
    st, d_ = [NA] * n, [1] * n
    lower_prev = upper_prev = NA
    for i in range(n):
        src = (h[i] + l[i]) / 2.0
        upper = lower = NA
        if atr[i] is not NA:
            upper = src + factor * atr[i]
            lower = src - factor * atr[i]
            pl = 0.0 if lower_prev is NA else lower_prev
            pu = 0.0 if upper_prev is NA else upper_prev
            c1 = c[i - 1] if i > 0 else NA
            lower = lower if (lower > pl or (c1 is not NA and c1 < pl)) else pl
            upper = upper if (upper < pu or (c1 is not NA and c1 > pu)) else pu
        atr_prev_na = i == 0 or atr[i - 1] is NA
        prev_st = st[i - 1] if i > 0 else NA
        if atr_prev_na:
            d = 1
        elif prev_st is not NA and prev_st == upper_prev:
            d = -1 if c[i] > upper else 1
        else:
            d = 1 if c[i] < lower else -1
        d_[i] = d
        st[i] = NA if atr[i] is NA else (lower if d == -1 else upper)
        lower_prev, upper_prev = lower, upper
    return st, d_


def pivot_at(h, l, i, L, R, is_high, tie):
    c = i - R
    if c - L < 0:
        return NA
    src = h if is_high else l
    pv = src[c]

    def breaks(v, equal_ok):
        if is_high:
            return v > pv if equal_ok else v >= pv
        return v < pv if equal_ok else v <= pv

    for k in range(1, L + 1):
        if breaks(src[c - k], tie == TIE_LEFT_EQUAL_OK):
            return NA
    for k in range(1, R + 1):
        if breaks(src[c + k], tie == TIE_RIGHT_EQUAL_OK):
            return NA
    return pv


def up_down_volume(o, c, v, length):
    n = len(c)
    bv, sv = [NA] * n, [NA] * n
    b = s = 0.0
    for i in range(n):
        b += v[i] if c[i] > o[i] else 0.0
        s += v[i] if c[i] < o[i] else 0.0
        if i >= length:
            j = i - length
            b -= v[j] if c[j] > o[j] else 0.0
            s -= v[j] if c[j] < o[j] else 0.0
        if i >= length - 1:
            bv[i], sv[i] = b, s
    return bv, sv


def dmi(o, h, l, c, di_len, adx_len):
    n = len(c)
    pdm, mdm = [NA] * n, [NA] * n
    for i in range(1, n):
        up = h[i] - h[i - 1]
        down = l[i - 1] - l[i]
        pdm[i] = up if (up > down and up > 0) else 0.0
        mdm[i] = down if (down > up and down > 0) else 0.0
    trur = rma(true_range(o, h, l, c, False), di_len)
    rp, rm = rma(pdm, di_len), rma(mdm, di_len)
    plus, minus, dx = [NA] * n, [NA] * n, [NA] * n
    lp = lm = NA
    for i in range(n):
        p = m = NA
        if trur[i] is not NA and trur[i] != 0:
            if rp[i] is not NA:
                p = 100 * rp[i] / trur[i]
            if rm[i] is not NA:
                m = 100 * rm[i] / trur[i]
        if p is NA:
            p = lp
        else:
            lp = p
        if m is NA:
            m = lm
        else:
            lm = m
        plus[i], minus[i] = p, m
        if p is not NA and m is not NA:
            ssum = p + m
            dx[i] = abs(p - m) / (1 if ssum == 0 else ssum)
    sm = rma(dx, adx_len)
    return plus, minus, [NA if x is NA else 100 * x for x in sm]


def compute_series(o, h, l, c, v, st_mult=1.5, st_atr=10, piv_len=5, rr=2.0,
                   vol_len=20, di_len=14, adx_smooth=14, tie=TIE_LEFT_EQUAL_OK):
    n = len(c)
    st, d = supertrend(o, h, l, c, st_mult, st_atr)
    bv, sv = up_down_volume(o, c, v, vol_len)
    plus, minus, adx = dmi(o, h, l, c, di_len, adx_smooth)
    out = dict(st=st, dir=d, bv=bv, sv=sv, adx=adx, plus=plus, minus=minus,
               long=[False] * n, short=[False] * n, lastPL=[NA] * n, lastPH=[NA] * n,
               pl=[NA] * n, ph=[NA] * n, sl=[NA] * n, tp=[NA] * n, risk=[NA] * n)
    lpl = lph = NA
    for i in range(n):
        out['long'][i] = i > 0 and d[i] < 0 and d[i - 1] >= 0
        out['short'][i] = i > 0 and d[i] > 0 and d[i - 1] <= 0
        pl = pivot_at(h, l, i, piv_len, piv_len, False, tie)
        ph = pivot_at(h, l, i, piv_len, piv_len, True, tie)
        out['pl'][i], out['ph'][i] = pl, ph
        if pl is not NA:
            lpl = pl
        if ph is not NA:
            lph = ph
        out['lastPL'][i], out['lastPH'][i] = lpl, lph
        if out['long'][i] or out['short'][i]:
            is_l = out['long'][i]
            e = c[i]
            if is_l:
                sl = lpl if (lpl is not NA and lpl < e) else st[i]
            else:
                sl = lph if (lph is not NA and lph > e) else st[i]
            if sl is NA:
                continue
            risk = e - sl if is_l else sl - e
            out['sl'][i], out['risk'][i] = sl, risk
            if risk > 0:
                out['tp'][i] = e + rr * risk if is_l else e - rr * risk
    return out
