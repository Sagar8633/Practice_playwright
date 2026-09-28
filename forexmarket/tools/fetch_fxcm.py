"""Fallback minute data for the forex majors from FXCM's public candle archive (candledata.fxcorporate.com, weekly gz files,
UTC timestamps, bid and ask OHLC, no volume). Writes data/alt/<instrument>/m1_YYYY-MM.csv in the Dukascopy layout
(timestamp ms UTC, open, high, low, close, volume=0) plus data/alt/<instrument>/spread_sample.csv (median ask-bid by hour).
Usage: python fetch_fxcm.py [instrument ...]"""
import gzip, io, os, sys, time
import numpy as np, pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(HERE), "data", "alt")
SYM = {"eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY", "audusd": "AUDUSD", "usdcad": "USDCAD", "usdchf": "USDCHF", "nzdusd": "NZDUSD"}
START, END = pd.Timestamp("2021-08-29"), pd.Timestamp("2026-09-27")
S = requests.Session()


def week_files(instr):
    """Every ISO-like FXCM week (year, week) from START to END; FXCM numbers weeks by the Sunday open."""
    out = []; d = START
    while d <= END:
        y, w = d.isocalendar()[0], d.isocalendar()[1]
        # FXCM uses the week number of the Friday close day within the calendar year of that Friday
        fri = d + pd.Timedelta(days=5); out.append((fri.year, int(fri.strftime("%U")) + 0, d)); d += pd.Timedelta(days=7)
    return out


def fetch(instr):
    sym = SYM[instr]; d = os.path.join(OUT, instr); os.makedirs(d, exist_ok=True)
    frames = []; missing = []
    for y in range(2021, 2027):
        for w in range(1, 54):
            url = f"https://candledata.fxcorporate.com/m1/{sym}/{y}/{w}.csv.gz"
            for attempt in range(3):
                try:
                    r = S.get(url, timeout=60)
                    break
                except Exception as e:  # noqa: BLE001
                    time.sleep(5); r = None
            if r is None or r.status_code != 200:
                if r is not None and r.status_code == 404:
                    missing.append(f"{y}-w{w}")
                continue
            df = pd.read_csv(io.BytesIO(gzip.decompress(r.content)))
            df["t"] = pd.to_datetime(df["DateTime"], format="%m/%d/%Y %H:%M:%S.%f")
            frames.append(df); time.sleep(0.2)
        print(instr, y, "weeks fetched so far", len(frames), flush=True)
    if not frames:
        print(instr, "no data"); return
    a = pd.concat(frames, ignore_index=True).drop_duplicates("t").sort_values("t")
    a = a[(a.t >= "2021-09-01") & (a.t < "2026-09-27")]
    a["spread_pts"] = (a.AskClose - a.BidClose)
    sp = a.groupby(a.t.dt.hour)["spread_pts"].median(); sp.to_csv(os.path.join(d, "spread_sample.csv"), header=["ask_minus_bid_median"])
    for (y, m), g in a.groupby([a.t.dt.year, a.t.dt.month]):
        out = pd.DataFrame({"timestamp": (g.t.astype("int64") // 10**6).to_numpy(), "open": g.BidOpen.to_numpy(), "high": g.BidHigh.to_numpy(), "low": g.BidLow.to_numpy(), "close": g.BidClose.to_numpy(), "volume": 0})
        out.to_csv(os.path.join(d, f"m1_{y}-{m:02d}.csv"), index=False)
    print(instr, "DONE rows", len(a), "first", a.t.min(), "last", a.t.max(), "missing week files:", missing[:40], flush=True)


if __name__ == "__main__":
    for instr in (sys.argv[1:] or list(SYM)):
        fetch(instr)
    print("ALL DONE")
