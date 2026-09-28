"""True hold-out for the New-York-session candidate: years never looked at (2020-09 .. 2024-09-25)."""
import numpy as np, pandas as pd
import liq_engine as E
from run_multitf import max_bars_for
from quality_lab import attach_htf

m1 = E.load_m1("2020-09-01", "2024-09-26")
cov = m1.groupby(m1.time.dt.to_period("M")).size()
print("coverage bars/month: min", int(cov.min()), "median", int(cov.median()), "months<20000:", list(cov[cov < 20000].index.astype(str)))
YEARS = [("2020-09-25", "2021-09-25"), ("2021-09-25", "2022-09-25"), ("2022-09-25", "2023-09-25"), ("2023-09-25", "2024-09-25")]
rows = []
for tf in ["15m", "30m", "1h"]:
    m = E.TF_MIN[tf]; d = E.resample(m1, m)
    P = dict(E.DEFAULT); P["asiaOn"] = P["lonOn"] = m <= 30; P["pdOn"] = True
    ev = E.detect_events(d, P)
    for rr in (1.0, 1.5, 2.0, 3.0):
        T = attach_htf(E.simulate(ev, m1, m, rr=rr, max_bars=max_bars_for(tf)), m1)
        filt = {"all": np.ones(len(T), bool), "newyork": (T.session == "newyork").values, "newyork+with_h4": ((T.session == "newyork") & T.with_h4).values,
                "ny_hours_11-16+with_h4": ((T.ny_h >= 11) & (T.ny_h < 16) & T.with_h4).values, "lon_ny+with_h4": (T.session.isin(["london", "overlap", "newyork"]) & T.with_h4).values}
        for name, mk in filt.items():
            x = T[mk]
            for a, b in YEARS:
                y = x[(x.time >= a) & (x.time < b)]
                mt = E.metrics(y)
                rows.append(dict(tf=tf, rr=rr, filt=name, year=a[:4] + "-" + b[2:4], n=mt.get("n", 0), expR=round(mt.get("expR", np.nan), 3), pf=round(mt.get("pf", np.nan), 2)))
            mt = E.metrics(x)
            rows.append(dict(tf=tf, rr=rr, filt=name, year="ALL 4y", n=mt.get("n", 0), expR=round(mt.get("expR", np.nan), 3), pf=round(mt.get("pf", np.nan), 2)))
    print(tf, "done", flush=True)
F = pd.DataFrame(rows)
F.to_csv("results/holdout_2020_2024.csv", index=False)
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 400)
for name in ["newyork+with_h4", "ny_hours_11-16+with_h4", "lon_ny+with_h4", "newyork", "all"]:
    print(f"\n==== {name}: net expectancy R (n) by hold-out year ====")
    x = F[F.filt == name]
    piv = x.pivot(index=["tf", "rr"], columns="year", values="expR")
    nn = x.pivot(index=["tf", "rr"], columns="year", values="n")
    print(piv.astype(str).add(" (").add(nn.astype(str)).add(")").to_string())
