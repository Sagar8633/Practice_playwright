"""The scan list: which NSE F&O underlyings, and what Yahoo calls each one.

`fno_symbols.txt` holds NSE symbols (the names on TradingView). Yahoo mostly
just wants `SYMBOL.NS`, but indices and a handful of post-demerger / renamed
tickers do not follow that rule, so those live in OVERRIDES.

`validate()` exists because that mapping rots: NSE adds and drops F&O names
every few months. Running it prints exactly which symbols Yahoo cannot serve
instead of letting them fail silently every cycle.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

log = logging.getLogger("srk.universe")

# NSE name -> Yahoo ticker, for the cases where "<symbol>.NS" is wrong.
OVERRIDES: Dict[str, str] = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    "NIFTYNXT50": "^NSMIDCP",
    "SENSEX": "^BSESN",
    "BANKEX": "BSE-BANK.BO",
}

INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
                 "SENSEX", "BANKEX", "SENSEX50"}


def yahoo_symbol(nse_symbol: str) -> str:
    return OVERRIDES.get(nse_symbol.upper(), f"{nse_symbol.upper()}.NS")


# NSE name -> TradingView ticker, for the cases where "NSE:<symbol>" is wrong.
TV_OVERRIDES: Dict[str, str] = {
    "FINNIFTY": "NSE:CNXFINANCE",
    "MIDCPNIFTY": "NSE:NIFTY_MID_SELECT",
    "NIFTYNXT50": "NSE:NIFTY_NEXT_50",
    "SENSEX": "BSE:SENSEX",
    "BANKEX": "BSE:BANKEX",
    "SENSEX50": "BSE:SENSEX50",
}


def tradingview_symbol(nse_symbol: str) -> str:
    """NSE symbol -> the ticker Pine's request.security() expects.

    TradingView flattens every non-alphanumeric character in an NSE ticker to
    an underscore, so M&M is NSE:M_M and BAJAJ-AUTO is NSE:BAJAJ_AUTO. Feeding
    it the raw NSE name silently resolves to nothing and the slot goes dead.
    """
    sym = nse_symbol.upper()
    if sym in TV_OVERRIDES:
        return TV_OVERRIDES[sym]
    return "NSE:" + re.sub(r"[^A-Z0-9]", "_", sym)


def load_symbols(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing - it holds the F&O scan list, one NSE symbol per line."
        )
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().upper()
        if line and line not in out:
            out.append(line)
    return out


def build_pairs(symbols: List[str]) -> List[Tuple[str, str]]:
    return [(s, yahoo_symbol(s)) for s in symbols]


def validate(symbols: List[str], feed) -> Tuple[List[str], Dict[str, str]]:
    """Ping every symbol once. Returns (working, {symbol: reason})."""
    ok, bad = feed.fetch_many(build_pairs(symbols))
    working = [s for s in symbols if s in ok]
    return working, bad


def refresh_from_nse(path: Path, timeout: int = 30) -> List[str]:
    """Best-effort refresh of the F&O list straight from nseindia.com.

    NSE blocks plain API hits, so a browser-shaped session must warm cookies on
    the home page first. It still fails often (Cloudflare, IP reputation); the
    caller keeps the existing file when that happens rather than scanning an
    empty universe.
    """
    import requests

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/market-data/securities-available-for-trading",
    }
    sess = requests.Session()
    sess.headers.update(headers)
    sess.get("https://www.nseindia.com", timeout=timeout)
    sess.get("https://www.nseindia.com/market-data/securities-available-for-trading",
             timeout=timeout)
    resp = sess.get("https://www.nseindia.com/api/equity-stockIndices",
                    params={"index": "SECURITIES IN F&O"}, timeout=timeout)
    resp.raise_for_status()
    rows = resp.json().get("data") or []
    symbols = sorted({r["symbol"].upper() for r in rows if r.get("symbol")
                      and r["symbol"].upper() != "NIFTY 50"})
    if not symbols:
        raise RuntimeError("NSE returned an empty F&O list")
    return symbols


def write_symbols(path: Path, symbols: List[str], note: str) -> None:
    header = (
        "# NSE F&O underlyings scanned by the SRK swing scanner.\n"
        "# One NSE symbol per line. Lines starting with # are ignored.\n"
        f"# {note}\n"
        "# Refresh with:  python scan.py --refresh-universe\n"
        "# Drop symbols Yahoo cannot serve with:  python scan.py --validate --write\n\n"
    )
    path.write_text(header + "\n".join(symbols) + "\n", encoding="utf-8")
