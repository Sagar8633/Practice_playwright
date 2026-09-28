"""Weekly value-area sensitivity: does the volume source or the week choice change anything?

For each VA variant (Dukascopy volume, XM tick volume, TPO count, developing current week)
the same alignment filter is applied: the traded boundary lies within 1 ATR of the VAH or VAL.
Reports per-period expectancy for both playbooks, plus the raw level differences.
"""
import os
import numpy as np
import pandas as pd

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pbd.run import run, load_all, fmt
from pbd.engine import summarize
from pbd.data import SPLITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "experiments")
os.makedirs(OUT, exist_ok=True)


def main():
    m1, m15, path = load_all()
    rows = []
    variants = {
        "duka_prev_week": ("vah", "val"),
        "tick_prev_week": ("vah_tick", "val_tick"),
        "tpo_prev_week": ("vah_tpo", "val_tpo"),
        "duka_developing": ("vah_dev", "val_dev"),
    }
    for pb in ["A_pingpong", "B1_pullback"]:
        _, sg, tr0 = run(playbook=pb, cost="real")
        tk0 = tr0[tr0.taken == True]
        for period in [p[0] for p in SPLITS] + ["ALL"]:
            sel = tk0 if period == "ALL" else tk0[tk0.period == period]
            s = summarize(sel)
            rows.append(dict(playbook=pb, variant="no_filter", period=period, n=s.get("n", 0), expectancy=s.get("expectancy", np.nan), pf=s.get("pf", np.nan)))
        for name, (vh, vl) in variants.items():
            for tol in (1.0, 2.0):
                pred = lambda s, vh=vh, vl=vl, tol=tol: np.minimum((s["boundary"] - s[vh]).abs(), (s["boundary"] - s[vl]).abs()) <= tol * s["atr14"]
                _, _, tr = run(playbook=pb, cost="real", signal_filter=pred)
                tk = tr[tr.taken == True]
                for period in [p[0] for p in SPLITS] + ["ALL"]:
                    sel = tk if period == "ALL" else tk[tk.period == period]
                    s = summarize(sel)
                    rows.append(dict(playbook=pb, variant=f"{name}_within_{tol}ATR", period=period, n=s.get("n", 0),
                                     expectancy=s.get("expectancy", np.nan), pf=s.get("pf", np.nan)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "va_source_sensitivity.csv"), index=False)
    print(fmt(df))
    # level differences
    d = m15.dropna(subset=["vah", "vah_tick", "vah_tpo"])
    diff = pd.DataFrame({
        "pair": ["duka-tick VAH", "duka-tick VAL", "duka-tpo VAH", "duka-tpo VAL", "prev-week vs developing VAH (end of week)"],
        "median_abs_diff_usd": [(d.vah - d.vah_tick).abs().median(), (d.val - d.val_tick).abs().median(),
                                (d.vah - d.vah_tpo).abs().median(), (d.val - d.val_tpo).abs().median(),
                                (d.vah - d.vah_dev).abs().median()],
        "median_abs_diff_atr": [((d.vah - d.vah_tick).abs() / d.atr14).median(), ((d.val - d.val_tick).abs() / d.atr14).median(),
                                ((d.vah - d.vah_tpo).abs() / d.atr14).median(), ((d.val - d.val_tpo).abs() / d.atr14).median(),
                                ((d.vah - d.vah_dev).abs() / d.atr14).median()],
    })
    diff.to_csv(os.path.join(OUT, "va_level_differences.csv"), index=False)
    print(fmt(diff))


if __name__ == "__main__":
    main()
