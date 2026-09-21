#!/usr/bin/env python3
"""Cross-check the Pine scanner's rule against real 15m candles, offline.

The scanner lives in Pine and alerts inside TradingView - this script exists
only to answer "is the rule I generated the same rule the chart is drawing?".
It recomputes the identical EMA/ADX logic on Yahoo's 15m bars and prints every
signal it finds, so the timestamps and prices can be eyeballed against the
triangles on the TradingView chart before any alert is trusted with money.

Usage:
    python verify.py IDFCFIRSTB
    python verify.py RELIANCE TCS --days 10 --adx 20
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from srk.data import FeedError, YahooFeed          # noqa: E402
from srk.indicators import dmi, ema                # noqa: E402
from srk.universe import tradingview_symbol, yahoo_symbol  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))     # India never observes DST


def signals(candles, *, fast=5, mid=10, slow=20, adx_len=14, adx_thr=20.0,
            alternate=True, require_opposite=False, cooldown=0):
    """Every SRK swing signal in the series, oldest first.

    Mirrors srk() in the Pine scanner exactly: the stack must FLIP on this bar
    (it was not aligned on the previous one) and ADX must confirm.
    """
    close, high, low = candles.closes, candles.highs, candles.lows
    r, g, b = ema(close, fast), ema(close, mid), ema(close, slow)
    _p, _m, adx = dmi(high, low, close, adx_len, adx_len)

    def stack(i):
        if r[i] is None or g[i] is None or b[i] is None:
            return None
        if r[i] > g[i] > b[i]:
            return 1
        if b[i] > g[i] > r[i]:
            return -1
        return 0

    out = []
    last_dir, last_bar = 0, -10 ** 9
    for i in range(1, len(close)):
        now, prev = stack(i), stack(i - 1)
        if now is None or prev is None or adx[i] is None:
            continue
        if now == 0 or now == prev or adx[i] <= adx_thr:
            continue
        if require_opposite and prev != -now:
            continue
        if alternate and now == last_dir:
            continue
        if i - last_bar < cooldown:
            continue
        last_dir, last_bar = now, i
        out.append({
            "time": datetime.fromtimestamp(candles.times[i], IST),
            "direction": "BULLISH" if now == 1 else "BEARISH",
            "close": close[i],
            "sl": low[i - 1] if now == 1 else high[i - 1],
            "adx": adx[i],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbols", nargs="+", help="NSE symbols, e.g. IDFCFIRSTB RELIANCE")
    ap.add_argument("--days", type=int, default=10, help="lookback window (max 60 for 15m)")
    ap.add_argument("--interval", default="15m")
    ap.add_argument("--adx", type=float, default=20.0)
    ap.add_argument("--loose", action="store_true",
                    help="also accept flips through a tangled ribbon")
    ap.add_argument("--all-flips", action="store_true",
                    help="loosest: also repeat in the same direction")
    ap.add_argument("--cooldown", type=int, default=0,
                    help="minimum bars between signals")
    args = ap.parse_args()

    feed = YahooFeed(lookback=f"{args.days}d", interval=args.interval, workers=4)
    total = 0

    for raw in args.symbols:
        symbol = raw.upper()
        try:
            candles = feed.fetch(symbol, yahoo_symbol(symbol))
        except FeedError as exc:
            print(f"{symbol:<12} no data - {exc}")
            continue

        found = signals(candles, adx_thr=args.adx,
                        alternate=not args.all_flips,
                        require_opposite=not (args.loose or args.all_flips),
                        cooldown=args.cooldown)
        first = datetime.fromtimestamp(candles.times[0], IST)
        last = datetime.fromtimestamp(candles.times[-1], IST)
        print(f"\n{symbol}  ({tradingview_symbol(symbol)})  {len(candles)} closed "
              f"{args.interval} bars, {first:%d-%b %H:%M} -> {last:%d-%b %H:%M}")
        if not found:
            print("  no signals in this window")
            continue
        for s in found:
            print(f"  {s['time']:%d-%b %H:%M}  {s['direction']:<8} "
                  f"close {s['close']:>9.2f}   SL {s['sl']:>9.2f}   ADX {s['adx']:>5.1f}")
        total += len(found)

    print(f"\n{total} signal(s). Compare these bar times with the triangles on the "
          f"TradingView {args.interval} chart - they should line up exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
