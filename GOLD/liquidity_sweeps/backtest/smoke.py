import time
import liq_engine as E
t = time.time(); m1 = E.load_m1("2025-09-01", "2026-09-26")
print("m1", len(m1), m1.time.min(), m1.time.max(), round(time.time() - t, 1), "s")
d = E.resample(m1, 5); print("5m bars", len(d))
print(d[["time", "utc", "ny_h", "session", "atr"]].tail(3))
t = time.time(); ev = E.detect_events(d, E.DEFAULT)
print("events", len(ev), "swept", int(ev.swept.sum()), round(time.time() - t, 1), "s")
print(ev.kind.value_counts().head(12))
tr = E.simulate(ev, m1, 5); print(E.metrics(tr))
print(tr.how.value_counts())
