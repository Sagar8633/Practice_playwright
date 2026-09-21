"""15-minute OHLC candles for NSE symbols, from Yahoo Finance's chart API.

Why Yahoo and not the broker feed: this scanner has to sweep ~200 F&O
underlyings every 15 minutes, unattended, with no daily login ritual. Yahoo's
chart endpoint needs no key and no token, serves NSE 15m bars, and one HTTP
call per symbol per cycle is well inside what it tolerates when throttled.

The one rule that matters here: never hand a forming bar to the signal engine.
TradingView plots its triangle when the bar CLOSES, so a scanner that reads the
in-progress bar will flag crossovers that un-cross before the candle ends.
`fetch` drops the last bar unless it is provably closed.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests

log = logging.getLogger("srk.data")

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600, "1h": 3600}


@dataclass
class Candles:
    """Closed OHLC bars for one symbol, oldest first."""
    symbol: str
    yahoo_symbol: str
    times: List[int]          # bar START, epoch seconds UTC
    opens: List[float]
    highs: List[float]
    lows: List[float]
    closes: List[float]
    volumes: List[float]

    def __len__(self) -> int:
        return len(self.closes)


class FeedError(Exception):
    pass


class YahooFeed:
    def __init__(self, *, lookback: str = "10d", interval: str = "15m",
                 timeout: int = 20, retries: int = 3, workers: int = 6,
                 pause: float = 0.0):
        self.lookback = lookback
        self.interval = interval
        self.timeout = timeout
        self.retries = max(1, retries)
        self.workers = max(1, workers)
        self.pause = pause
        self._local = None
        self._session_lock_free_sessions: Dict[int, requests.Session] = {}

    # A Session per worker thread: requests.Session is not thread-safe, but a
    # per-thread one still gives us connection reuse across ~200 symbols.
    def _session(self) -> requests.Session:
        import threading
        key = threading.get_ident()
        sess = self._session_lock_free_sessions.get(key)
        if sess is None:
            sess = requests.Session()
            sess.headers.update(HEADERS)
            self._session_lock_free_sessions[key] = sess
        return sess

    def fetch(self, symbol: str, yahoo_symbol: str,
              now: Optional[float] = None) -> Candles:
        """One symbol's closed bars. Raises FeedError if Yahoo gives nothing usable."""
        from urllib.parse import quote

        url = CHART_URL.format(symbol=quote(yahoo_symbol, safe=""))
        params = {"interval": self.interval, "range": self.lookback,
                  "includePrePost": "false"}
        payload = self._get_json(url, params, yahoo_symbol)

        chart = payload.get("chart") or {}
        if chart.get("error"):
            raise FeedError(f"{yahoo_symbol}: {chart['error'].get('description', chart['error'])}")
        results = chart.get("result") or []
        if not results:
            raise FeedError(f"{yahoo_symbol}: empty result")

        res = results[0]
        stamps = res.get("timestamp") or []
        quotes = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        o, h, l, c = (quotes.get(k) or [] for k in ("open", "high", "low", "close"))
        v = quotes.get("volume") or [0] * len(stamps)
        if not stamps or not c:
            raise FeedError(f"{yahoo_symbol}: no candles in response")

        bar_secs = INTERVAL_SECONDS.get(self.interval, 900)
        cutoff = (time.time() if now is None else now) - bar_secs
        times, oo, hh, ll, cc, vv = [], [], [], [], [], []
        for i, ts in enumerate(stamps):
            if i >= len(c):
                break
            row = (o[i] if i < len(o) else None, h[i] if i < len(h) else None,
                   l[i] if i < len(l) else None, c[i])
            if any(x is None for x in row):
                continue                      # Yahoo pads halted/illiquid bars with nulls
            if ts > cutoff:
                continue                      # still forming - TradingView has not plotted it
            times.append(int(ts))
            oo.append(float(row[0])); hh.append(float(row[1]))
            ll.append(float(row[2])); cc.append(float(row[3]))
            vv.append(float(v[i] or 0) if i < len(v) else 0.0)

        if not cc:
            raise FeedError(f"{yahoo_symbol}: no closed bars")
        return Candles(symbol, yahoo_symbol, times, oo, hh, ll, cc, vv)

    def _get_json(self, url: str, params: dict, label: str) -> dict:
        delay = 1.0
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                resp = self._session().get(url, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 502, 503, 504):
                    last = FeedError(f"{label}: HTTP {resp.status_code}")
                    time.sleep(delay); delay *= 2
                    continue
                raise FeedError(f"{label}: HTTP {resp.status_code}")
            except requests.RequestException as exc:
                last = exc
                time.sleep(delay); delay *= 2
        raise FeedError(f"{label}: {last}")

    def fetch_many(self, pairs: Iterable[Tuple[str, str]],
                   now: Optional[float] = None,
                   ) -> Tuple[Dict[str, Candles], Dict[str, str]]:
        """Fetch concurrently. Returns (candles_by_symbol, errors_by_symbol).

        Failures are collected, never raised - one delisted ticker must not
        stop the other 200 from being scanned.
        """
        pairs = list(pairs)
        ok: Dict[str, Candles] = {}
        bad: Dict[str, str] = {}

        def job(pair: Tuple[str, str]):
            symbol, yahoo = pair
            if self.pause:
                time.sleep(self.pause)
            try:
                return symbol, self.fetch(symbol, yahoo, now=now), None
            except Exception as exc:            # noqa: BLE001 - reported, not raised
                return symbol, None, str(exc)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for symbol, candles, err in pool.map(job, pairs):
                if candles is not None:
                    ok[symbol] = candles
                else:
                    bad[symbol] = err or "unknown error"
        if bad:
            log.warning("%d/%d symbols returned no data (e.g. %s)", len(bad), len(pairs),
                        ", ".join(list(bad)[:5]))
        return ok, bad
