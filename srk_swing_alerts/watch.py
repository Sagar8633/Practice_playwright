#!/usr/bin/env python3
"""Watch every NSE F&O stock on the 15m chart and notify the moment a signal prints.

The free, unlimited alternative to TradingView alerts: no plan quota, no alert
expiry, no symbol cap, nothing leaving this PC. Each signal raises a Windows
notification naming the stock, and everything is appended to data/signals.csv.

    python watch.py                     # all 213 F&O names, live, forever
    python watch.py --once              # one sweep now, then exit
    python watch.py --top 40            # just the 40 most-traded names
    python watch.py --once --ignore-market-hours --adx 30
    python watch.py --test-alert        # prove notifications work on this PC
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from srk.alerts import Notifier, toast                       # noqa: E402
from srk.data import YahooFeed                               # noqa: E402
from srk.scanner import Scanner, SignalState, market_is_open, now_ist  # noqa: E402
from srk.universe import load_symbols, validate, write_symbols  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=str(ROOT / "fno_symbols.txt"))
    ap.add_argument("--top", type=int, default=0, metavar="N",
                    help="scan only the N most-traded names (fno_symbols.txt is "
                         "kept in turnover order by rank_universe.py)")
    ap.add_argument("--only", nargs="+", metavar="SYM",
                    help="scan just these symbols")

    ap.add_argument("--timeframe", type=int, default=15, help="bar size in minutes")
    ap.add_argument("--adx", type=float, default=20.0, help="ADX threshold")
    ap.add_argument("--loose", action="store_true",
                    help="also accept flips through a tangled ribbon (~18/day -> ~121/day)")
    ap.add_argument("--all-flips", action="store_true",
                    help="loosest: also repeat in the same direction")
    ap.add_argument("--cooldown", type=int, default=0,
                    help="minimum bars between signals on one symbol")

    ap.add_argument("--once", action="store_true", help="one sweep, then exit")
    ap.add_argument("--cycles", type=int, default=0, help="stop after N sweeps")
    ap.add_argument("--ignore-market-hours", action="store_true")
    ap.add_argument("--delay", type=int, default=90,
                    help="seconds to wait after a bar closes before scanning")
    ap.add_argument("--recheck-bars", type=int, default=4,
                    help="how many recently closed bars each sweep re-examines")
    ap.add_argument("--max-age", type=int, default=45, metavar="MIN",
                    help="ceiling on how late a bar may be published and still "
                         "count as live")
    ap.add_argument("--catch-up", action="store_true",
                    help="on start, also announce bars that closed before launch "
                         "(default: live only - history stays silent)")
    ap.add_argument("--workers", type=int, default=6, help="concurrent fetches")

    ap.add_argument("--no-toast", action="store_true", help="console and CSV only")
    ap.add_argument("--test-alert", action="store_true",
                    help="fire a sample notification and exit")
    ap.add_argument("--validate", action="store_true",
                    help="check every symbol resolves, report the ones that do not")
    ap.add_argument("--write", action="store_true",
                    help="with --validate, rewrite the symbol file without the dead ones")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S")

    if args.test_alert:
        ok = toast("BULLISH  IDFCFIRSTB",
                   ["15m @ 84.86   SL 84.56   ADX 24.4",
                    "bar 02-Sep 10:30   NSE:IDFCFIRSTB"])
        print("Notification sent - check the action centre." if ok else
              "Notification FAILED. Check Settings > System > Notifications is on.")
        return 0 if ok else 1

    symbols_path = Path(args.symbols)
    symbols = [s.upper() for s in args.only] if args.only else load_symbols(symbols_path)
    if args.top > 0:
        symbols = symbols[:args.top]

    if args.validate:
        feed = YahooFeed(lookback="5d", interval=f"{args.timeframe}m", workers=args.workers)
        print(f"Checking {len(symbols)} symbols against the feed...")
        working, bad = validate(symbols, feed)
        print(f"\n{len(working)} OK, {len(bad)} with no data:")
        for sym, reason in sorted(bad.items()):
            print(f"  {sym:<14} {reason}")
        if bad and args.write:
            write_symbols(symbols_path, working,
                          f"Validated {now_ist():%d-%b-%Y}; {len(bad)} dead symbol(s) removed.")
            print(f"\nRewrote {symbols_path} with {len(working)} working symbols.")
        elif bad:
            print("\nRe-run with --write to drop them from the file.")
        return 0

    notifier = Notifier(ROOT / "data" / "signals.csv", use_toast=not args.no_toast)
    state = SignalState(ROOT / "data" / "seen_signals.json")
    scanner = Scanner(
        symbols, notifier, state,
        adx_thr=args.adx,
        alternate=not args.all_flips,
        require_opposite=not (args.loose or args.all_flips),
        cooldown=args.cooldown,
        recheck_bars=args.recheck_bars,
        max_age_minutes=args.max_age,
        bar_minutes=args.timeframe,
        feed=YahooFeed(lookback="10d", interval=f"{args.timeframe}m",
                       workers=args.workers),
    )

    if args.once or args.cycles == 1:
        if not (args.ignore_market_hours or market_is_open()):
            print(f"Market is closed ({now_ist():%a %H:%M} IST). Scanning anyway - "
                  f"signals will be from the last session.")
        print(f"Scanning {len(symbols)} symbols...")
        found = scanner.scan_once(catch_up=True)
        notifier.emit(found)
        if not found:
            print("  no new signals (already-announced bars are skipped).")
        return 0

    if args.catch_up:
        # Nothing counts as history, so the first sweep announces the recent window.
        scanner.watching_since = now_ist() - timedelta(days=365)
    try:
        scanner.run(bar_minutes=args.timeframe, delay=args.delay,
                    ignore_market_hours=args.ignore_market_hours,
                    cycles=args.cycles)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
