"""Fallback minute data from histdata.com (free ASCII M1 bid quotes, EST = UTC-5 without DST, no volume) for the forex majors,
silver and WTI while Dukascopy rate-limits this machine. Writes data/alt/<instrument>/m1_YYYY-MM.csv in the Dukascopy column
layout (timestamp ms UTC, open, high, low, close, volume=0). Usage: python fetch_histdata.py [pair ...]"""
import io, os, re, sys, time, zipfile
import pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(HERE), "data", "alt")
PAIRS = {"eurusd": "eurusd", "gbpusd": "gbpusd", "usdjpy": "usdjpy", "audusd": "audusd", "usdcad": "usdcad", "usdchf": "usdchf", "nzdusd": "nzdusd", "xagusd": "xagusd", "lightcmdusd": "wtiusd"}
MONTHS = [(y, m) for y in range(2021, 2027) for m in range(1, 13) if not (y == 2021 and m < 9) and not (y == 2026 and m > 9)]
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"})


def fetch_month(pair, y, m):
    page = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair}/{y}/{m}"
    r = S.get(page, timeout=60); r.raise_for_status()
    form = {}
    for name in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair"):
        mm = re.search(r'id="%s"[^>]*value="([^"]*)"' % name, r.text) or re.search(r'name="%s"[^>]*value="([^"]*)"' % name, r.text)
        if not mm:
            raise RuntimeError(f"form field {name} missing (month not published?)")
        form[name] = mm.group(1)
    z = S.post("https://www.histdata.com/get.php", data=form, headers={"Referer": page, "Origin": "https://www.histdata.com"}, timeout=180); z.raise_for_status()
    if not z.content[:2] == b"PK":
        raise RuntimeError("not a zip: " + z.text[:120])
    zf = zipfile.ZipFile(io.BytesIO(z.content)); name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    df = pd.read_csv(zf.open(name), sep=";", header=None, names=["t", "open", "high", "low", "close", "volume"])
    t = pd.to_datetime(df["t"], format="%Y%m%d %H%M%S") + pd.Timedelta(hours=5)      # EST (fixed UTC-5) -> UTC
    return pd.DataFrame({"timestamp": (t.astype("int64") // 10**6), "open": df.open, "high": df.high, "low": df.low, "close": df.close, "volume": 0})


if __name__ == "__main__":
    todo = sys.argv[1:] or list(PAIRS)
    for instr in todo:
        pair = PAIRS[instr]; d = os.path.join(OUT, instr); os.makedirs(d, exist_ok=True)
        for y, m in MONTHS:
            f = os.path.join(d, f"m1_{y}-{m:02d}.csv")
            if os.path.exists(f) and os.path.getsize(f) > 1000:
                continue
            for attempt in range(4):
                try:
                    df = fetch_month(pair, y, m); df.to_csv(f, index=False); print(f"{instr} {y}-{m:02d}: {len(df)} rows", flush=True); break
                except Exception as e:  # noqa: BLE001
                    msg = str(e)
                    print(f"{instr} {y}-{m:02d} attempt {attempt + 1} failed: {msg[:120]}", flush=True)
                    if "missing" in msg:
                        break
                    time.sleep(20 * (attempt + 1))
            time.sleep(1.5)
        print(instr, "DONE", flush=True)
    print("ALL DONE")
