"""Quality lab: which sweeps are worth taking? Runs on results/trades_all.csv from run_multitf.py.

Adds higher-timeframe context (1h / 4h EMA-50 trend at the entry bar), tests pre-declared filter
combinations, and reports quarter-by-quarter consistency. Discipline: a candidate must be net positive in
CONTROL (2024-09-25..2025-09-25) and in TEST (2025-09-25..2026-09-25) with >= 30 trades in each.
"""
import os
import numpy as np
import pandas as pd
import liq_engine as E
from run_multitf import TEST, CTRL, TFS, slice_period

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def htf_trend(m1: pd.DataFrame, minutes: int, span: int = 50) -> pd.DataFrame:
    d = E.resample(m1, minutes)
    ema = d.close.ewm(span=span, adjust=False).mean()
    # trend known at the CLOSE of bar i -> valid from time[i] + minutes
    return pd.DataFrame({"time": d.time + pd.Timedelta(minutes=minutes), "trend": np.sign(d.close - ema).astype(int)})


def attach_htf(T: pd.DataFrame, m1: pd.DataFrame) -> pd.DataFrame:
    T = T.sort_values("time").reset_index(drop=True)
    T["time"] = pd.to_datetime(T["time"])
    for nm, mins in (("h1", 60), ("h4", 240)):
        tr = htf_trend(m1, mins).sort_values("time")
        T = pd.merge_asof(T, tr.rename(columns={"trend": f"trend_{nm}"}), on="time", direction="backward")
    T["with_h1"] = T.side == T.trend_h1
    T["with_h4"] = T.side == T.trend_h4
    T["against_h4"] = T.side == -T.trend_h4
    return T


def evaluate(T: pd.DataFrame, label: str, rows: list, tf: str, rr: float):
    mc = E.metrics(slice_period(T, *CTRL)); mt = E.metrics(slice_period(T, *TEST))
    rows.append(dict(tf=tf, rr=rr, combo=label, n_ctrl=mc.get("n", 0), exp_ctrl=mc.get("expR", np.nan), pf_ctrl=mc.get("pf", np.nan),
                     n_test=mt.get("n", 0), exp_test=mt.get("expR", np.nan), pf_test=mt.get("pf", np.nan), ci_lo_test=mt.get("ci_lo", np.nan),
                     win_test=mt.get("win", np.nan), dd_test=mt.get("maxdd_R", np.nan), tot_test=mt.get("totalR", np.nan)))


def main():
    T = pd.read_csv(os.path.join(OUT, "trades_all.csv"), parse_dates=["time"])
    m1 = E.load_m1("2024-09-01", "2026-09-26")
    T = attach_htf(T, m1)
    T["is_key"] = T.kind.isin(list(E.KEY_KINDS))
    T["is_eq"] = T.kind.isin(["EQH", "EQL"])
    T["swing"] = ~(T.is_key | T.is_eq)
    T["same_bar"] = T.bars_held == 1
    T["deep"] = T.depth_atr >= 0.3
    T["lon_ny"] = T.session.isin(["london", "overlap", "newyork"])
    T["overlap"] = T.session == "overlap"
    T["session_key"] = T.kind.isin(["ASIA-H", "ASIA-L", "LON-H", "LON-L"])
    T["daily_key"] = T.kind.isin(["PDH", "PDL", "PWH", "PWL"])
    T.to_csv(os.path.join(OUT, "trades_with_context.csv"), index=False)

    COMBOS = {
        "all": None,
        "with_h4": ["with_h4"], "against_h4": ["against_h4"], "with_h1": ["with_h1"],
        "key": ["is_key"], "key+with_h4": ["is_key", "with_h4"], "key+lon_ny": ["is_key", "lon_ny"],
        "daily_key": ["daily_key"], "daily_key+with_h4": ["daily_key", "with_h4"],
        "session_key": ["session_key"], "session_key+lon_ny": ["session_key", "lon_ny"],
        "eq": ["is_eq"], "eq+with_h4": ["is_eq", "with_h4"],
        "same_bar+deep": ["same_bar", "deep"], "same_bar+deep+with_h4": ["same_bar", "deep", "with_h4"],
        "lon_ny+with_h4": ["lon_ny", "with_h4"], "overlap+with_h4": ["overlap", "with_h4"],
        "key+same_bar": ["is_key", "same_bar"], "key+deep": ["is_key", "deep"],
    }
    rows = []
    for tf in TFS:
        for rr in (1.0, 1.5, 2.0, 3.0):
            base = T[(T.tf == tf) & (T.rr == rr)]
            if base.empty: continue
            for name, conds in COMBOS.items():
                sub = base
                for c in (conds or []):
                    sub = sub[sub[c]]
                evaluate(sub, name, rows, tf, rr)
    F = pd.DataFrame(rows)
    F.to_csv(os.path.join(OUT, "quality_combos.csv"), index=False)
    F["retained"] = (F.exp_ctrl > 0) & (F.exp_test > 0) & (F.n_ctrl >= 30) & (F.n_test >= 30)
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 200)
    print("==== RETAINED combos: net positive in CONTROL and TEST, >= 30 trades each ====")
    R = F[F.retained].sort_values(["exp_test"], ascending=False)
    cols = ["tf", "rr", "combo", "n_ctrl", "exp_ctrl", "pf_ctrl", "n_test", "exp_test", "pf_test", "ci_lo_test", "win_test", "dd_test", "tot_test"]
    print(R[cols].round(3).to_string(index=False) if len(R) else "NONE")
    print("\n==== TEST-year top 20 regardless of control ====")
    print(F.sort_values("exp_test", ascending=False).head(20)[cols].round(3).to_string(index=False))

    # quarter-by-quarter consistency for the top retained rows (or top test rows if none retained)
    pick = (R if len(R) else F.sort_values("exp_test", ascending=False)).head(6)
    print("\n==== quarter by quarter (net R sum / trades) for the top candidates ====")
    for r in pick.itertuples():
        sub = T[(T.tf == r.tf) & (T.rr == r.rr)]
        for c in (COMBOS[r.combo] or []):
            sub = sub[sub[c]]
        q = sub.groupby(sub.time.dt.to_period("Q")).R.agg(["sum", "count", "mean"]).round(2)
        print(f"\n{r.tf} rr={r.rr} {r.combo}")
        print(q.T.to_string())

    # directional information test: gross first-passage symmetric? (rr=1, all trades)
    print("\n==== does a sweep predict direction? gross win rate at 1R:1R by timeframe (50% = coin flip) ====")
    g = T[T.rr == 1.0].groupby("tf").apply(lambda s: pd.Series({"n": len(s), "gross_win": (s.gross_R > 0).mean(), "gross_expR": s.gross_R.mean(),
                                                                "mfe>=1R": (s.mfe_R >= 1).mean(), "mae>=1R": (s.mae_R >= 1).mean()}))
    print(g.reindex(TFS).round(3).to_string())


if __name__ == "__main__":
    main()
