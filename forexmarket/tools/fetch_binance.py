"""Bitcoin fallback: Binance spot BTCUSDT 1-minute klines (public REST, no key) Sep 2021 .. Sep 2026 -> data/alt/btcusd/m1_YYYY-MM.csv
in the Dukascopy layout (timestamp ms UTC, open, high, low, close, volume = base volume)."""
import os, time
import pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(HERE), "data", "alt", "btcusd"); os.makedirs(OUT, exist_ok=True)
MONTHS = [(y, m) for y in range(2021, 2027) for m in range(1, 13) if not (y == 2021 and m < 9) and not (y == 2026 and m > 9)]
S = requests.Session()
for y, m in MONTHS:
    f = os.path.join(OUT, f"m1_{y}-{m:02d}.csv")
    if os.path.exists(f) and os.path.getsize(f) > 1000:
        continue
    a = int(pd.Timestamp(y, m, 1).timestamp() * 1000); b = int(pd.Timestamp(y + (m == 12), 1 if m == 12 else m + 1, 1).timestamp() * 1000)
    rows = []; cur = a
    while cur < b:
        for attempt in range(6):
            try:
                r = S.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "1m", "startTime": cur, "endTime": b - 1, "limit": 1000}, timeout=60)
                if r.status_code == 429 or r.status_code == 418:
                    time.sleep(60); continue
                r.raise_for_status(); k = r.json(); break
            except Exception as e:  # noqa: BLE001
                print("retry", attempt, str(e)[:100], flush=True); time.sleep(5 * (attempt + 1)); k = None
        if not k:
            break
        rows += [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in k]
        cur = k[-1][0] + 60000
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).drop_duplicates("timestamp")
    df.to_csv(f, index=False); print(f"btcusd {y}-{m:02d}: {len(df)} rows", flush=True)
print("btcusd DONE"); print("ALL DONE")
