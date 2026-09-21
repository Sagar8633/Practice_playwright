"""The scan loop: every closed 15m bar, check every F&O name, alert once.

Two design choices carry the "foolproof" claim:

1. Each cycle re-checks the last few CLOSED bars, not just the newest one.
   Yahoo publishes a bar a minute or two after it closes, and sometimes later.
   Looking only at the newest bar would silently drop a signal whenever the
   feed lagged past the scan instant; looking back a few bars cannot.

2. Every signal is keyed by (symbol, direction, bar time) in a state file on
   disk. That key is what makes step 1 safe - a bar re-examined on the next
   cycle, or after a restart, never notifies twice.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .alerts import Notifier
from .data import YahooFeed
from .indicators import dmi, ema
from .universe import build_pairs, tradingview_symbol

log = logging.getLogger("srk.scanner")

IST = timezone(timedelta(hours=5, minutes=30))     # India never observes DST
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)


def now_ist() -> datetime:
    return datetime.now(IST)


def market_is_open(when: Optional[datetime] = None) -> bool:
    t = when or now_ist()
    if t.weekday() >= 5:                            # NSE trades Mon-Fri
        return False
    start = t.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    end = t.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)
    return start <= t <= end


def seconds_to_next_scan(bar_minutes: int, delay: int,
                         when: Optional[datetime] = None) -> float:
    """Sleep until `delay` seconds after the next bar boundary."""
    t = when or now_ist()
    minute_block = (t.minute // bar_minutes + 1) * bar_minutes
    boundary = t.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute_block)
    return max(5.0, (boundary + timedelta(seconds=delay) - t).total_seconds())


class SignalState:
    """Which (symbol, direction, bar) triples have already been announced."""

    def __init__(self, path: Path, keep_days: int = 3):
        self.path = path
        self.keep_days = keep_days
        self.seen: Dict[str, str] = {}
        if path.exists():
            try:
                self.seen = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                log.warning("state file %s unreadable - starting fresh", path)
        self._prune()

    def _prune(self) -> None:
        cutoff = (now_ist() - timedelta(days=self.keep_days)).date().isoformat()
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff}

    def is_new(self, key: str) -> bool:
        return key not in self.seen

    def mark(self, key: str, bar_date: str) -> None:
        self.seen[key] = bar_date

    def save(self) -> None:
        self._prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.seen, indent=0, sort_keys=True),
                             encoding="utf-8")


class Scanner:
    def __init__(self, symbols: List[str], notifier: Notifier, state: SignalState, *,
                 fast: int = 5, mid: int = 10, slow: int = 20,
                 adx_len: int = 14, adx_thr: float = 20.0,
                 alternate: bool = True, require_opposite: bool = False,
                 cooldown: int = 0, recheck_bars: int = 4,
                 max_age_minutes: int = 45, bar_minutes: int = 15,
                 feed: Optional[YahooFeed] = None):
        self.symbols = symbols
        self.notifier = notifier
        self.state = state
        self.fast, self.mid, self.slow = fast, mid, slow
        self.adx_len, self.adx_thr = adx_len, adx_thr
        self.alternate = alternate
        self.require_opposite = require_opposite
        self.cooldown = cooldown
        self.recheck_bars = recheck_bars
        self.max_age_minutes = max_age_minutes
        self.bar_minutes = bar_minutes
        # Set when run() begins. Bars that had already closed by then are
        # history, not alerts - see _cutoff().
        self.watching_since = None
        self.feed = feed or YahooFeed(lookback="10d", interval="15m", workers=6)

    def _signals_for(self, candles) -> List[dict]:
        """Same rule as srk() in the Pine scanner, evaluated over the series."""
        close, high, low = candles.closes, candles.highs, candles.lows
        r = ema(close, self.fast)
        g = ema(close, self.mid)
        b = ema(close, self.slow)
        _p, _m, adx = dmi(high, low, close, self.adx_len, self.adx_len)

        def stack(i):
            if r[i] is None or g[i] is None or b[i] is None:
                return None
            if r[i] > g[i] > b[i]:
                return 1
            if b[i] > g[i] > r[i]:
                return -1
            return 0

        out: List[dict] = []
        last_dir, last_bar = 0, -10 ** 9
        for i in range(1, len(close)):
            now, prev = stack(i), stack(i - 1)
            if now is None or prev is None or adx[i] is None:
                continue
            if now == 0 or now == prev or adx[i] <= self.adx_thr:
                continue
            if self.require_opposite and prev != -now:
                continue
            if self.alternate and now == last_dir:
                continue
            if i - last_bar < self.cooldown:
                continue
            last_dir, last_bar = now, i
            out.append({
                "symbol": candles.symbol,
                "bar_time": datetime.fromtimestamp(candles.times[i], IST),
                "direction": "BULLISH" if now == 1 else "BEARISH",
                "close": close[i],
                "sl": low[i - 1] if now == 1 else high[i - 1],
                "adx": adx[i],
                "tradingview": tradingview_symbol(candles.symbol),
            })
        return out

    def _cutoff(self):
        """Earliest bar-CLOSE time still worth announcing.

        Two guards, whichever is later:

        * `watching_since` - a bar that had already closed before you started
          the watcher is history. Without this, launching mid-session greets you
          with the previous hour's signals, and launching at 09:30 replays
          yesterday's last bars, because the recheck window reaches back that far.
        * `max_age_minutes` - once the watch has been up a while, this is what
          keeps a late-published bar announceable while still refusing a stale one.
        """
        by_age = now_ist() - timedelta(minutes=self.max_age_minutes)
        if self.watching_since is None:
            return by_age
        return max(by_age, self.watching_since)

    def scan_once(self, *, catch_up: bool = False) -> List[dict]:
        """One sweep of the whole universe. Returns only unannounced signals.

        `catch_up=True` drops both guards, so a manual sweep can show what the
        last session did. The live loop never does that.
        """
        started = time.time()
        pairs = build_pairs(self.symbols)
        candles, errors = self.feed.fetch_many(pairs)
        cutoff = None if catch_up else self._cutoff()
        bar_len = timedelta(minutes=self.bar_minutes)

        fresh: List[dict] = []
        stale = 0
        for symbol, series in candles.items():
            recent = set(series.times[-self.recheck_bars:])
            for sig in self._signals_for(series):
                if int(sig["bar_time"].timestamp()) not in recent:
                    continue                        # older than the recheck window
                key = f"{symbol}|{sig['direction']}|{sig['bar_time']:%Y-%m-%dT%H:%M}"
                if not self.state.is_new(key):
                    continue
                # Recorded either way: a bar consciously skipped as history must
                # not become "new" again on a later sweep.
                self.state.mark(key, sig["bar_time"].date().isoformat())
                # Compare the bar's CLOSE, not its open - a 10:00 bar is only
                # decided at 10:15, and that instant is what "live" means.
                if cutoff is not None and sig["bar_time"] + bar_len < cutoff:
                    stale += 1
                    continue
                fresh.append(sig)

        self.state.save()
        fresh.sort(key=lambda s: (s["bar_time"], s["symbol"]))
        log.info("scanned %d symbols in %.1fs (%d no-data) - %d new signal(s)%s",
                 len(candles), time.time() - started, len(errors), len(fresh),
                 f", {stale} skipped as history" if stale else "")
        return fresh

    def run(self, *, bar_minutes: int = 15, delay: int = 90,
            ignore_market_hours: bool = False, cycles: int = 0) -> None:
        done = 0
        self.bar_minutes = bar_minutes
        if self.watching_since is None:
            self.watching_since = now_ist()
        print(f"Watching {len(self.symbols)} F&O symbols on the {bar_minutes}m "
              f"timeframe, live from {self.watching_since:%H:%M}. Bars that closed "
              f"before that are history and stay silent. Ctrl+C to stop.")
        self.notifier.heartbeat(
            f"Live from {self.watching_since:%H:%M} - watching "
            f"{len(self.symbols)} F&O symbols on {bar_minutes}m.")

        while True:
            if ignore_market_hours or market_is_open():
                print(f"\n[{now_ist():%H:%M:%S}] scanning {len(self.symbols)} symbols...")
                try:
                    self.notifier.emit(self.scan_once())
                except Exception as exc:            # noqa: BLE001 - a bad cycle must not end the watch
                    log.error("scan cycle failed: %s", exc, exc_info=True)
                done += 1
                if cycles and done >= cycles:
                    return
            else:
                print(f"[{now_ist():%H:%M:%S}] market closed - idling", end="\r")

            time.sleep(seconds_to_next_scan(bar_minutes, delay))
