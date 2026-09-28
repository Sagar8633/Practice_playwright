"""Download NIFTY 50 and NIFTY BANK index candles from the Upstox public historical-candle API (no login needed).

1-minute candles are served one calendar month per request (v2 endpoint) and exist from January 2022;
daily candles come from the v3 endpoint in yearly chunks. Raw JSON is kept per request (resumable),
then assembled into one CSV per index and interval with IST timestamps. Nothing is filled or interpolated.

Usage: python fetch_upstox.py            (fetch what is missing, then assemble)
       python fetch_upstox.py assemble   (assemble only)
"""
import json, os, sys, time
from datetime import date
import pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw"); os.makedirs(RAW, exist_ok=True)
INDICES = {"nifty50": "NSE_INDEX|Nifty 50", "banknifty": "NSE_INDEX|Nifty Bank"}
FIRST_MONTH = (2022, 1); LAST_DAY = date(2026, 9, 26)
HEAD = {"Accept": "application/json", "User-Agent": "indianmarket-research/1.0"}


def get(url, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, headers=HEAD, timeout=60)
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    return d["data"]["candles"]
            print("  retry", k + 1, r.status_code, r.text[:120])
        except Exception as e:  # noqa: BLE001
            print("  retry", k + 1, repr(e)[:120])
        time.sleep(2.0 * (k + 1))
    raise RuntimeError("failed: " + url)


def month_ends(y0, m0):
    y, m = y0, m0
    while date(y, m, 1) <= LAST_DAY:
        nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
        a = date(y, m, 1); b = min(nxt - pd.Timedelta(days=1), LAST_DAY)
        yield a, b
        y, m = nxt.year, nxt.month


def fetch_all():
    for name, key in INDICES.items():
        d = os.path.join(RAW, name); os.makedirs(d, exist_ok=True); k = requests.utils.quote(key, safe="")
        for a, b in month_ends(*FIRST_MONTH):
            f = os.path.join(d, f"1minute_{a:%Y-%m}.json")
            if os.path.exists(f):
                continue
            c = get(f"https://api.upstox.com/v2/historical-candle/{k}/1minute/{b:%Y-%m-%d}/{a:%Y-%m-%d}")
            json.dump(c, open(f, "w")); print(name, "1minute", f"{a:%Y-%m}", len(c), "candles"); time.sleep(0.4)
        for y in range(2007, LAST_DAY.year + 1):
            f = os.path.join(d, f"days_{y}.json")
            if os.path.exists(f) and y < LAST_DAY.year:
                continue
            b = LAST_DAY if y == LAST_DAY.year else date(y, 12, 31)
            c = get(f"https://api.upstox.com/v3/historical-candle/{k}/days/1/{b:%Y-%m-%d}/{y}-01-01")
            json.dump(c, open(f, "w")); print(name, "days", y, len(c), "candles"); time.sleep(0.4)


def assemble():
    summary = {}
    for name in INDICES:
        d = os.path.join(RAW, name); out = os.path.join(ROOT, "data", name); os.makedirs(out, exist_ok=True)
        for interval, pat in [("1min", "1minute_"), ("daily", "days_")]:
            rows = []
            for f in sorted(os.listdir(d)):
                if f.startswith(pat):
                    rows.extend(json.load(open(os.path.join(d, f))))
            df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume", "oi"])
            df["time"] = pd.to_datetime(df["time"].str.slice(0, 19))  # IST wall-clock, offset dropped (+05:30 everywhere)
            n0 = len(df); df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
            df.to_csv(os.path.join(out, f"{name}_{interval}_upstox.csv.gz"), index=False, compression="gzip")
            summary[f"{name}_{interval}"] = dict(rows=len(df), duplicates_dropped=n0 - len(df), first=str(df.time.min()), last=str(df.time.max()),
                                                 days=int(df.time.dt.normalize().nunique()), volume_nonzero=int((df.volume > 0).sum()))
            print(name, interval, summary[f"{name}_{interval}"])
    json.dump(summary, open(os.path.join(ROOT, "data", "upstox_download_summary.json"), "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "assemble":
        fetch_all()
    assemble()
