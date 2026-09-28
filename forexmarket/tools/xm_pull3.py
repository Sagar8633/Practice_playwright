"""XM deep pull by date ranges: H1 in yearly chunks from 2015 (10+ years, all symbols) and M15 in 200-day chunks from mid-2022
(the terminal's M15 history starts around Sep 2022). Both carry XM's spread and tick volume. Output: data/xm/xm_<SYM>_H1_full.csv.gz,
xm_<SYM>_M15_full.csv.gz. Usage: python xm_pull3.py [SYM ...]"""
import os, sys, time
from datetime import datetime, timedelta
import MetaTrader5 as mt5, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(HERE), "data", "xm")
SYMS = sys.argv[1:] or ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "SILVER", "BTCUSD", "OILCash", "GOLD"]
assert mt5.initialize(), mt5.last_error()


def pull(sym, tf, a, b, step_days):
    frames = []; cur = a
    while cur < b:
        nxt = min(cur + timedelta(days=step_days), b); r = None
        for attempt in range(3):
            r = mt5.copy_rates_range(sym, tf, cur, nxt)
            if r is not None and len(r) > 0: break
            time.sleep(2 + 3 * attempt)
        if r is not None and len(r) > 0:
            frames.append(pd.DataFrame(r))
        cur = nxt; time.sleep(0.3)
    if not frames: return None
    df = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time"); df["time"] = pd.to_datetime(df["time"], unit="s"); return df


for s in SYMS:
    mt5.symbol_select(s, True); time.sleep(0.5)
    for tf, name, a, step in [(mt5.TIMEFRAME_H1, "H1", datetime(2015, 1, 1), 365), (mt5.TIMEFRAME_M15, "M15", datetime(2022, 6, 1), 120)]:
        f = os.path.join(OUT, f"xm_{s}_{name}_full.csv.gz")
        if os.path.exists(f) and os.path.getsize(f) > 100000:
            continue
        df = pull(s, tf, a, datetime(2026, 9, 28), step)
        if df is None:
            print(s, name, "NO DATA", flush=True); continue
        df.to_csv(f, index=False, compression="gzip")
        print(f"{s} {name}: {len(df)} bars {df.time.min()} .. {df.time.max()} median spread {df.spread.median():.0f} pts, tick volume median {df.tick_volume.median():.0f}", flush=True)
mt5.shutdown(); print("DONE3")
