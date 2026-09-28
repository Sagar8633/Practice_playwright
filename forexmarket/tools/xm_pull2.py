"""XM pull: M1 and M15 bars by position with decreasing request sizes (the terminal refuses requests beyond its bar limit),
H1 where missing, and the full symbol specifications. Output in data/xm/: xm_<SYM>_<TF>.csv.gz and xm_symbol_specs.json."""
import json, os, time
import MetaTrader5 as mt5, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(HERE), "data", "xm")
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "SILVER", "BTCUSD", "OILCash", "GOLD"]
assert mt5.initialize(), mt5.last_error()
specs = {}
for s in SYMS:
    mt5.symbol_select(s, True); time.sleep(0.5)
    i = mt5.symbol_info(s)._asdict(); specs[s] = {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in i.items()}
    for tf, name in [(mt5.TIMEFRAME_M1, "M1"), (mt5.TIMEFRAME_M15, "M15"), (mt5.TIMEFRAME_H1, "H1")]:
        f = os.path.join(OUT, f"xm_{s}_{name}.csv.gz")
        if os.path.exists(f) and os.path.getsize(f) > 100000:
            continue
        r = None
        for count in (60000, 30000, 15000, 8000, 3000):
            r = mt5.copy_rates_from_pos(s, tf, 0, count)
            if r is not None and len(r) > 0:
                break
            time.sleep(1.0)
        if r is None or len(r) == 0:
            print(s, name, "NO DATA", mt5.last_error(), flush=True); continue
        df = pd.DataFrame(r); df["time"] = pd.to_datetime(df["time"], unit="s")
        df.to_csv(f, index=False, compression="gzip")
        print(f"{s} {name}: {len(df)} bars {df.time.min()} .. {df.time.max()} median spread {df.spread.median():.0f} pts", flush=True)
json.dump(specs, open(os.path.join(OUT, "xm_symbol_specs.json"), "w"), indent=1, default=str)
mt5.shutdown(); print("DONE2")
