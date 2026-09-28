"""Regression checks for twk_engine after edits (run from the backtest folder)."""
import numpy as np, pandas as pd, twk_engine as E
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
spread = np.array([E.year_spread_model()[y] for y in m1.time.dt.year.to_numpy()], float)
p = E.CoreParams(); m3 = E.resample(m1, 3)
END = pd.Timestamp("2026-09-25"); a = int((END - pd.DateOffset(years=5)).timestamp()); b = int(END.timestamp())
m5 = E.resample(m1, 5); ser5 = E.compute_series(m5, p); sig5 = E.signal_table(m5, ser5, 5, m1, m3, p, 3)
tr = E.simulate(m1, sig5, ser5, 5, E.MomentumEAParams(), spread, a, b); print("M5 regression:", len(tr), round(tr.pnl.sum(), 2), "(expect 2847, -3381.80)")
ser3 = E.compute_series(m3, p); sig3 = E.signal_table(m3, ser3, 3, m1, m3, p, 5)
bot = E.MomentumEAParams(min_volume_ratio=1.5, initial_sl="purple", purple_trail_always=True, protection_activation_pts=10**8, one_to_one=False)
tr = E.simulate(m1, sig3, ser3, 3, bot, spread, a, b); print("M3 scenario regression:", len(tr), round(tr.pnl.sum(), 2), "(expect 2488, -1384.64)")
base = E.MomentumEAParams(min_volume_ratio=1.2, purple_activation_pts=360, protection_activation_pts=900, lock_pts=180, min_improve_pts=9)
tr = E.simulate(m1, sig3, ser3, 3, base, spread, a, b); print("M3 baseline regression:", len(tr), round(tr.pnl.sum(), 2), "(expect 3399, -2762)")
d = tr.attrs.get("decisions")
if d is not None:
    print("decisions:", d.decision.value_counts().to_dict()); print("reasons:", d.reason.value_counts().head(12).to_dict())
pine = E.simulate(m1, sig3, ser3, 3, E.PineEAParams(), spread, a, b); print("Pine M3 5y:", len(pine), round(pine.pnl.sum(), 2))
