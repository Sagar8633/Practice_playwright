#!/usr/bin/env python3
"""Reorder the F&O list by traded value, so batch 1 is the batch worth having.

A free TradingView account holds only a handful of alerts, and each scanner
script costs one. Splitting 212 names alphabetically means alert #1 covers
360ONE..CAMS - an arbitrary slice. Splitting them by turnover means alert #1
covers the 40 most-traded F&O stocks, #2 the next 40, and coverage degrades
gracefully at whatever quota you actually have.

Turnover is averaged over whole sessions (close x volume, summed per day, then
averaged) rather than taken from one day, so a single news-driven spike does not
promote an otherwise illiquid name.

    python rank_universe.py            # rewrite fno_symbols.txt in rank order
    python rank_universe.py --dry-run  # just show the ranking
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from srk.data import YahooFeed                                # noqa: E402
from srk.scanner import IST, now_ist                          # noqa: E402
from srk.universe import build_pairs, load_symbols, write_symbols  # noqa: E402

ROOT = Path(__file__).resolve().parent


def average_daily_turnover(candles) -> float:
    """Mean rupee turnover per session. 0.0 when volume is missing entirely."""
    per_day: dict = defaultdict(float)
    for ts, close, vol in zip(candles.times, candles.closes, candles.volumes):
        per_day[datetime.fromtimestamp(ts, IST).date()] += close * vol
    full = [v for v in per_day.values() if v > 0]
    return sum(full) / len(full) if full else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=str(ROOT / "fno_symbols.txt"))
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true", help="print, do not rewrite")
    args = ap.parse_args()

    path = Path(args.symbols)
    symbols = load_symbols(path)
    feed = YahooFeed(lookback=f"{args.days}d", interval="15m", workers=args.workers)
    print(f"Fetching {len(symbols)} symbols to measure turnover...")
    candles, bad = feed.fetch_many(build_pairs(symbols))

    ranked = sorted(((average_daily_turnover(c), s) for s, c in candles.items()),
                    reverse=True)
    novol = [s for t, s in ranked if t == 0.0]
    ranked = [(t, s) for t, s in ranked if t > 0.0]

    print(f"\n{'#':>4}  {'SYMBOL':<14} {'avg daily turnover':>20}")
    print("-" * 42)
    for i, (turnover, sym) in enumerate(ranked, start=1):
        if i <= 15 or i % 40 == 0 or i > len(ranked) - 5:
            print(f"{i:>4}  {sym:<14} {turnover / 1e7:>17.1f} Cr")
        elif i == 16:
            print(f"{'':>4}  {'...':<14}")

    if novol:
        print(f"\n{len(novol)} symbol(s) reported no volume, appended last: "
              f"{', '.join(novol)}")
    if bad:
        print(f"{len(bad)} symbol(s) returned no data, appended last: "
              f"{', '.join(bad)}")

    order = [s for _t, s in ranked] + novol + [s for s in symbols if s in bad]

    print(f"\nBatches of 40, in this order:")
    for n in range(0, len(order), 40):
        chunk = order[n:n + 40]
        print(f"  b{n // 40 + 1}: {chunk[0]} .. {chunk[-1]}   ({len(chunk)} names)")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    write_symbols(path, order,
                  f"Ordered by average daily turnover, {now_ist():%d-%b-%Y}. "
                  f"Batch 1 = most traded.")
    print(f"\nRewrote {path} in turnover order. "
          f"Now run: python generate_scanners.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
