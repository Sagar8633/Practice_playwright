"""Hold-out for the BREAK-continuation result on years never looked at (2020-09 .. 2024-09-25), with long/short split."""
import numpy as np, pandas as pd
import liq_engine as E
from run_multitf import max_bars_for
from quality_lab import attach_htf
from lab2 import simulate_generic

m1 = E.load_m1("2020-09-01", "2024-09-26")
YEARS = [("2020-09-25", "2021-09-25"), ("2021-09-25", "2022-09-25"), ("2022-09-25", "2023-09-25"), ("2023-09-25", "2024-09-25")]
rows = []
for tf in ["15m", "1h", "4h", "1d"]:
    m = E.TF_MIN[tf]; d = E.resample(m1, m)
    P = dict(E.DEFAULT); P["asiaOn"] = P["lonOn"] = m <= 30; P["pdOn"] = m <= 240
    ev = E.detect_events(d, P)
    for rr in (1.0, 1.5, 2.0, 3.0):
        T = attach_htf(simulate_generic(ev, m1, m, rr=rr, max_bars=max_bars_for(tf), mode="break"), m1)
        if T.empty: continue
        lon_ny = T.session.isin(["london", "overlap", "newyork"]).values
        filt = {"all": np.ones(len(T), bool), "with_h4": T.with_h4.values, "lon_ny+with_h4": (lon_ny & T.with_h4.values),
                "long": (T.side == 1).values, "short": (T.side == -1).values, "with_h4&long": (T.with_h4 & (T.side == 1)).values,
                "with_h4&short": (T.with_h4 & (T.side == -1)).values}
        for name, mk in filt.items():
            x = T[mk]
            for a, b in YEARS:
                y = x[(x.time >= a) & (x.time < b)]; mt = E.metrics(y)
                rows.append(dict(tf=tf, rr=rr, filt=name, year=a[:4] + "-" + b[2:4], n=mt.get("n", 0), expR=round(mt.get("expR", np.nan), 3), pf=round(mt.get("pf", np.nan), 2)))
            mt = E.metrics(x)
            rows.append(dict(tf=tf, rr=rr, filt=name, year="ALL 4y", n=mt.get("n", 0), expR=round(mt.get("expR", np.nan), 3), pf=round(mt.get("pf", np.nan), 2)))
    print(tf, "done", flush=True)
F = pd.DataFrame(rows); F.to_csv("results/holdout2_breaks_2020_2024.csv", index=False)
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500)
for name in ["all", "with_h4", "lon_ny+with_h4", "long", "short", "with_h4&long", "with_h4&short"]:
    print(f"\n==== BREAK {name}: net expectancy R (n) by hold-out year ====")
    x = F[F.filt == name]
    piv = x.pivot(index=["tf", "rr"], columns="year", values="expR"); nn = x.pivot(index=["tf", "rr"], columns="year", values="n")
    print(piv.astype(str).add(" (").add(nn.astype(str)).add(")").to_string())
