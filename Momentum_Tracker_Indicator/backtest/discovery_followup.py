"""Follow-up on the gross asymmetries found by the discovery engine: does a wider unit or longer hold clear the spread?
Protocol: DEV decides; VAL and OOS are printed as confirmation only."""
import json, math
import numpy as np, pandas as pd
import discovery_engine as DE

d5 = DE.base_frame(5); EV5 = DE.events(d5)
d3, EV3 = DE.twk_events()
CASES = [("H21 Asian open: first 30 min direction -> continuation", "with", d5, 5, EV5),
         ("H19 exhaustion climax after >= 4 ATR move", "against", d5, 5, EV5),
         ("H27 STATE trend -> exhaustion (fade)", "against", d5, 5, EV5),
         ("H04 first expansion after low-vol regime", "against", d5, 5, EV5),
         ("H08 Asian range sweep + rejection in London", "against", d5, 5, EV5),
         ("H09 London range break in NY (15-19h)", "with", d5, 5, EV5),
         ("H22 TWK flip (contrarian = against)", "against", d3, 3, EV3)]
SH = [(1.0, 1.0), (1.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.5, 2.0)]
rows = []
for name, direction, d, tfm, EV in CASES:
    ev = EV[name].drop_duplicates("i").sort_values("i").reset_index(drop=True)
    i = ev["i"].to_numpy(); side = ev["side"].to_numpy() * (1 if direction == "with" else -1)
    t_ev = d["t"].to_numpy()[i]; unit = d["atr"].to_numpy()[i]
    times = pd.to_datetime(t_ev, unit="s"); per = np.select([times < DE.PERIODS["DEV"][1], times < DE.PERIODS["VAL"][1]], ["DEV", "VAL"], "OOS")
    for H in (100, 300):
        for cm in (0.0, 1.0, 1.5):
            res = DE.scan_events(t_ev, side, unit, H, tfm, cm)
            for S, T in SH:
                if S not in DE.LEV or T not in DE.LEV: continue
                r, hit, st = DE.shape_r(res, S, T)
                row = dict(hypothesis=name, direction=direction, horizon_bars=H, cost=("gross" if cm == 0 else f"x{cm}"), shape=f"{S}x{T}")
                for p in ("DEV", "VAL", "OOS"):
                    rr = r[per == p]; rr = rr[~np.isnan(rr)]; row[f"{p}_n"] = int(len(rr)); row[f"{p}_exp"] = round(float(rr.mean()), 3) if len(rr) else None
                    row[f"{p}_pf"] = round(float(rr[rr > 0].sum() / max(1e-9, -rr[rr < 0].sum())), 2) if len(rr) else None
                rows.append(row)
        # end-of-horizon P&L in ATR (no stop, no target): pure drift after the event
        res = DE.scan_events(t_ev, side, unit, H, tfm, 1.0); resg = DE.scan_events(t_ev, side, unit, H, tfm, 0.0)
        for p in ("DEV", "VAL", "OOS"):
            m = (per == p) & res["valid"]
            rows.append(dict(hypothesis=name, direction=direction, horizon_bars=H, cost="drift net", shape="hold to horizon", **{f"{p}_n": int(m.sum()), f"{p}_exp": round(float(np.nanmean(res["endp"][m])), 3), f"{p}_pf": None}))
            rows.append(dict(hypothesis=name, direction=direction, horizon_bars=H, cost="drift gross", shape="hold to horizon", **{f"{p}_n": int(m.sum()), f"{p}_exp": round(float(np.nanmean(resg["endp"][m])), 3), f"{p}_pf": None}))
F = pd.DataFrame(rows); F.to_csv("results/discovery/followup.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
for name, *_ in CASES:
    sub = F[(F.hypothesis == name) & (F.cost.isin(["gross", "x1.0", "drift gross", "drift net"]))]
    print("\n==", name); print(sub[["direction", "horizon_bars", "cost", "shape", "DEV_n", "DEV_exp", "DEV_pf", "VAL_n", "VAL_exp", "VAL_pf", "OOS_n", "OOS_exp", "OOS_pf"]].to_string(index=False))
# anything net-positive in DEV with n >= 200?
win = F[(F.cost == "x1.0") & (F.DEV_exp > 0) & (F.DEV_n >= 200)]
print("\nNET-POSITIVE IN DEV (x1.0 cost, n>=200):"); print(win[["hypothesis", "direction", "horizon_bars", "shape", "DEV_n", "DEV_exp", "DEV_pf", "VAL_exp", "VAL_pf", "OOS_exp", "OOS_pf"]].to_string(index=False) if len(win) else "none")
