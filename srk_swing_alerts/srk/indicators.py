"""Pine-exact indicator maths in plain Python - no pandas, no numpy.

Every function here mirrors the TradingView built-in of the same name. That
matters more than elegance: an alert that fires on a bar the chart does not
mark is worse than no alert at all, so the seeding rules (SMA seed, Wilder
smoothing, first-bar true range) are reproduced exactly rather than
approximated with a plain recursive EMA.

Series are plain lists aligned to the input bars. Warm-up positions hold
``None`` - the same thing Pine shows as ``na`` - so callers must never assume
index 0 has a value.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

Series = List[Optional[float]]


def sma(values: Sequence[float], length: int) -> Series:
    """Simple moving average, ``na`` until ``length`` bars exist."""
    out: Series = [None] * len(values)
    if length <= 0:
        return out
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= length:
            running -= values[i - length]
        if i >= length - 1:
            out[i] = running / length
    return out


def ema(values: Sequence[float], length: int) -> Series:
    """Pine ``ta.ema``: SMA seed over the first `length` bars, then alpha=2/(len+1).

    TradingView does NOT start the recursion from the first close; it starts
    from the SMA of the first `length` closes. Skipping that seed shifts every
    subsequent value slightly, which is enough to move a crossover bar.
    """
    out: Series = [None] * len(values)
    if length <= 0 or len(values) < length:
        return out
    alpha = 2.0 / (length + 1.0)
    prev = sum(values[:length]) / length
    out[length - 1] = prev
    for i in range(length, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def rma(values: Sequence[float], length: int) -> Series:
    """Pine ``ta.rma`` (Wilder's smoothing): SMA seed, then alpha=1/len."""
    out: Series = [None] * len(values)
    if length <= 0 or len(values) < length:
        return out
    alpha = 1.0 / length
    prev = sum(values[:length]) / length
    out[length - 1] = prev
    for i in range(length, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def true_range(highs: Sequence[float], lows: Sequence[float],
               closes: Sequence[float]) -> List[float]:
    """Pine ``ta.tr``: on bar 0 there is no previous close, so TR = high - low."""
    out: List[float] = []
    for i in range(len(highs)):
        if i == 0:
            out.append(highs[i] - lows[i])
            continue
        pc = closes[i - 1]
        out.append(max(highs[i] - lows[i], abs(highs[i] - pc), abs(lows[i] - pc)))
    return out


def dmi(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        di_length: int = 14, adx_length: int = 14) -> Tuple[Series, Series, Series]:
    """Pine ``ta.dmi(diLen, adxLen)`` -> (+DI, -DI, ADX).

    Directional movement uses raw bar-to-bar change (not true range) and the
    "only the larger move counts" rule; both DM streams and TR are then
    Wilder-smoothed before the ratio is taken.
    """
    n = len(highs)
    plus_dm: List[float] = [0.0] * n
    minus_dm: List[float] = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0

    tr_rma = rma(true_range(highs, lows, closes), di_length)
    plus_rma = rma(plus_dm, di_length)
    minus_rma = rma(minus_dm, di_length)

    plus_di: Series = [None] * n
    minus_di: Series = [None] * n
    dx: List[float] = []
    dx_index: List[int] = []

    for i in range(n):
        tr_v, p_v, m_v = tr_rma[i], plus_rma[i], minus_rma[i]
        if tr_v is None or p_v is None or m_v is None or tr_v == 0:
            continue
        p = 100.0 * p_v / tr_v
        m = 100.0 * m_v / tr_v
        plus_di[i] = p
        minus_di[i] = m
        total = p + m
        dx.append(100.0 * abs(p - m) / (total if total != 0 else 1.0))
        dx_index.append(i)

    adx: Series = [None] * n
    smoothed = rma(dx, adx_length)
    for slot, value in zip(dx_index, smoothed):
        adx[slot] = value
    return plus_di, minus_di, adx
