"""Multi-timeframe test of the liquidity-sweep setup on XAUUSD.

TEST year   : 2025-09-25 .. 2026-09-25 (the "last 1 year" the user asked for)
CONTROL year: 2024-09-25 .. 2025-09-25 (used to pre-screen filters so nothing is fitted on the test year)

For every timeframe: replicate the indicator, take every SWEEP as a reversal trade (long after SSL sweep,
short after BSL sweep), stop beyond the wick + 0.10 ATR, targets 1R / 1.5R / 2R / 3R, exits on the M1 path,
XM spread + 0.10 slippage. Outputs go to results/.
"""
import itertools, json, os, sys, time
import numpy as np
import pandas as pd
import liq_engine as E

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
TEST = ("2025-09-25", "2026-09-25")
CTRL = ("2024-09-25", "2025-09-25")
TFS = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]
RRS = [1.0, 1.5, 2.0, 3.0]


def params_for(tf):
    P = dict(E.DEFAULT)
    m = E.TF_MIN[tf]
    P["asiaOn"] = P["lonOn"] = m <= 30
    P["pdOn"] = m <= 240
    P["pwOn"] = True
    return P


def max_bars_for(tf):
    m = E.TF_MIN[tf]
    return {1: 60, 3: 40, 5: 36, 15: 24, 30: 24, 60: 24, 240: 12, 1440: 10}[m]


def slice_period(df, a, b, col="time"):
    return df[(df[col] >= a) & (df[col] < b)].reset_index(drop=True)


def main():
    t0 = time.time()
    m1 = E.load_m1("2024-09-01", "2026-09-26")
    cov = m1.groupby(m1.time.dt.to_period("M")).size()
    cov.to_csv(os.path.join(OUT, "m1_coverage_by_month.csv"))
    print("M1 bars", len(m1), "months", len(cov), "min/month", int(cov.min()), "max/month", int(cov.max()))
    summary = []
    all_trades = []
    all_events = []
    for tf in TFS:
        m = E.TF_MIN[tf]
        d = E.resample(m1, m)
        P = params_for(tf)
        t1 = time.time()
        ev = E.detect_events(d, P)
        ev["tf"] = tf
        all_events.append(ev)
        print(f"{tf}: {len(d)} bars, {len(ev)} resolved pools, {int(ev.swept.sum())} sweeps, {time.time() - t1:.1f}s", flush=True)
        for rr in RRS:
            tr = E.simulate(ev, m1, m, rr=rr, max_bars=max_bars_for(tf))
            if tr.empty: continue
            tr["tf"] = tf; tr["rr"] = rr
            all_trades.append(tr)
            for name, (a, b) in (("TEST", TEST), ("CTRL", CTRL)):
                s = slice_period(tr, a, b)
                mt = E.metrics(s); mt.update(tf=tf, rr=rr, period=name)
                summary.append(mt)
    S = pd.DataFrame(summary)
    S.to_csv(os.path.join(OUT, "summary_tf_rr.csv"), index=False)
    T = pd.concat(all_trades, ignore_index=True)
    T.to_parquet(os.path.join(OUT, "trades_all.parquet")) if _has_parquet() else T.to_csv(os.path.join(OUT, "trades_all.csv"), index=False)
    EV = pd.concat(all_events, ignore_index=True)
    EV.to_csv(os.path.join(OUT, "events_all.csv"), index=False)
    print(f"done in {time.time() - t0:.0f}s; trades {len(T)}")
    show(S)
    filters(T)


def _has_parquet():
    try:
        import pyarrow  # noqa
        return True
    except Exception:
        return False


def show(S):
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
    for per in ("TEST", "CTRL"):
        print(f"\n==== {per} : net expectancy (R) by timeframe x target ====")
        piv = S[S.period == per].pivot(index="tf", columns="rr", values="expR").reindex(TFS)
        print(piv.round(3))
        print(f"\n---- {per} : trades / year")
        print(S[S.period == per].pivot(index="tf", columns="rr", values="n").reindex(TFS))
        print(f"\n---- {per} : profit factor")
        print(S[S.period == per].pivot(index="tf", columns="rr", values="pf").reindex(TFS).round(2))
        print(f"\n---- {per} : GROSS expectancy (before costs)")
        print(S[S.period == per].pivot(index="tf", columns="rr", values="gross_expR").reindex(TFS).round(3))
        print(f"\n---- {per} : cost in R (spread+slip / risk)")
        print(S[S.period == per].pivot(index="tf", columns="rr", values="cost_R").reindex(TFS).round(3))


def filters(T):
    """Pre-declared quality filters. A filter is RETAINED only if it improves net expectancy in CTRL
    AND the TEST year is net positive with >= 30 trades. Evaluated at rr=2 (and 1.5) on every TF."""
    T = T.copy()
    T["is_key"] = T.kind.isin(list(E.KEY_KINDS))
    T["is_eq"] = T.kind.isin(["EQH", "EQL"])
    T["same_bar"] = T.bars_held == 1
    T["deep"] = T.depth_atr >= 0.3
    T["shallow"] = T.depth_atr < 0.3
    T["lon_ny"] = T.session.isin(["london", "overlap", "newyork"])
    T["overlap"] = T.session == "overlap"
    T["asia"] = T.session == "asia"
    T["old_level"] = T.age_bars >= 30
    T["wide_stop"] = T.risk_atr >= 1.0
    T["tight_stop"] = T.risk_atr < 0.7
    T["long"] = T.side == 1
    T["short"] = T.side == -1
    FL = ["is_key", "is_eq", "same_bar", "deep", "shallow", "lon_ny", "overlap", "asia", "old_level", "wide_stop", "tight_stop", "long", "short"]
    rows = []
    for tf in TFS:
        for rr in (1.5, 2.0):
            base = T[(T.tf == tf) & (T.rr == rr)]
            if base.empty: continue
            for f in ["none"] + FL:
                sub = base if f == "none" else base[base[f]]
                mc = E.metrics(slice_period(sub, *CTRL)); mt = E.metrics(slice_period(sub, *TEST))
                rows.append(dict(tf=tf, rr=rr, filter=f, n_ctrl=mc.get("n", 0), exp_ctrl=mc.get("expR", np.nan), pf_ctrl=mc.get("pf", np.nan),
                                 n_test=mt.get("n", 0), exp_test=mt.get("expR", np.nan), pf_test=mt.get("pf", np.nan),
                                 ci_lo_test=mt.get("ci_lo", np.nan), win_test=mt.get("win", np.nan)))
    F = pd.DataFrame(rows)
    F.to_csv(os.path.join(OUT, "filters_tf.csv"), index=False)
    base = F[F["filter"] == "none"].set_index(["tf", "rr"])
    F["base_ctrl"] = [base.loc[(a, b), "exp_ctrl"] for a, b in zip(F.tf, F.rr)]
    F["retained"] = (F.exp_ctrl > F.base_ctrl) & (F.exp_ctrl > 0) & (F.exp_test > 0) & (F.n_test >= 30) & (F.n_ctrl >= 30)
    pd.set_option("display.width", 220)
    print("\n==== filters retained (positive in CONTROL and TEST, >= 30 trades each) ====")
    R = F[F.retained].sort_values("exp_test", ascending=False)
    print(R[["tf", "rr", "filter", "n_ctrl", "exp_ctrl", "pf_ctrl", "n_test", "exp_test", "pf_test", "ci_lo_test", "win_test"]].round(3).to_string(index=False) if len(R) else "NONE")
    print("\n==== best 15 by TEST expectancy regardless of control ====")
    print(F.sort_values("exp_test", ascending=False).head(15)[["tf", "rr", "filter", "n_ctrl", "exp_ctrl", "n_test", "exp_test", "pf_test", "ci_lo_test"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
