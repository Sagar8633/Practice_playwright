"""Shared helpers: experiment log, period splits, regime tagging, result saving."""
from __future__ import annotations

import csv, json, os, time
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

import sma18_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
LOG = os.path.join(RES, "experiment_log.csv")
LOG_COLS = ["exp_id", "date", "phase", "hypothesis", "timeframe", "dataset", "period", "cost_scenario", "parameters", "filters", "exit_logic",
            "trades", "profit_factor", "net_profit", "max_dd_usd", "max_dd_pct", "win_rate", "expectancy", "expectancy_r", "giveback_avg",
            "profit_to_loss_2usd", "oos_result", "conclusion"]

TF_NAME = {1: "M1", 5: "M5", 15: "M15", 60: "H1", 240: "H4", 1440: "D1"}
DATA_START = "2020-09-01"
DATA_END = "2026-09-26"
D1_START = "2003-05-05"

# Development / validation / out-of-sample split for the 6-year M1-based datasets (declared before any result was seen)
SPLITS = {"DEV": ("2020-09-01", "2023-09-01"), "VAL": ("2023-09-01", "2025-01-01"), "OOS": ("2025-01-01", "2026-09-26")}
# Rolling walk-forward folds: 2 years train, 1 year validate, 1 year test
WF_FOLDS = [{"train": ("2020-09-01", "2022-09-01"), "val": ("2022-09-01", "2023-09-01"), "test": ("2023-09-01", "2024-09-01")},
            {"train": ("2021-09-01", "2023-09-01"), "val": ("2023-09-01", "2024-09-01"), "test": ("2024-09-01", "2025-09-01")},
            {"train": ("2022-09-01", "2024-09-01"), "val": ("2024-09-01", "2025-09-01"), "test": ("2025-09-01", "2026-09-26")}]

COST = {
    "A_low": dict(spread_fixed_pts=25.0, slippage_pts=0.0, swap=False),
    "B_real": dict(spread_fixed_pts=-1.0, spread_mult=1.0, slippage_pts=10.0, swap=True),
    "C_stress": dict(spread_fixed_pts=-1.0, spread_mult=1.5, slippage_pts=30.0, swap=True),
}


def _next_id(phase: str) -> str:
    n = 0
    if os.path.exists(LOG):
        with open(LOG, newline="", encoding="utf-8") as f:
            n = sum(1 for _ in csv.DictReader(f))
    return f"{phase}-{n + 1:04d}"


def log_experiment(phase: str, hypothesis: str, p: E.Params, m: dict, cost: str, period: str, filters: str = "", exit_logic: str = "",
                   oos_result: str = "", conclusion: str = "", dataset: str = "Dukascopy XAUUSD M1 bid, server time") -> str:
    new = not os.path.exists(LOG)
    eid = _next_id(phase)
    row = {"exp_id": eid, "date": time.strftime("%Y-%m-%d %H:%M"), "phase": phase, "hypothesis": hypothesis, "timeframe": TF_NAME.get(p.tf_minutes, str(p.tf_minutes)),
           "dataset": dataset, "period": period, "cost_scenario": cost, "parameters": json.dumps(nondefault(p)), "filters": filters, "exit_logic": exit_logic,
           "trades": m.get("trades"), "profit_factor": m.get("profit_factor"), "net_profit": m.get("net_profit"), "max_dd_usd": m.get("max_dd_usd"),
           "max_dd_pct": m.get("max_dd_pct"), "win_rate": m.get("win_rate"), "expectancy": m.get("expectancy"), "expectancy_r": m.get("expectancy_r"),
           "giveback_avg": m.get("giveback_avg"), "profit_to_loss_2usd": m.get("profit_to_loss_2usd"), "oos_result": oos_result, "conclusion": conclusion}
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new:
            w.writeheader()
        w.writerow(row)
    return eid


def nondefault(p: E.Params) -> dict:
    d0 = asdict(E.Params()); d = asdict(p)
    return {k: v for k, v in d.items() if d0.get(k) != v and k not in ("start", "end", "path")}


def exit_desc(p: E.Params) -> str:
    parts = []
    if p.be_enable: parts.append(f"BE@{p.be_trigger_pts}+{p.be_offset_pts}")
    names = {1: f"swing(buf {p.swing_buffer_pts})", 2: f"chandelier({p.chand_lookback},{p.atr_period}x{p.atr_mult})", 4: f"trail({p.trail_start_pts}/{p.trail_dist_pts}/{p.trail_step_pts})",
             8: f"atrTrail({p.atr_trail_mult}x, start {p.trail_start_pts})", 16: f"twk3stage({p.twk_act_pts}/{p.twk_prot_pts}/{p.twk_lock_pts}/{p.twk_gap_pts})", 32: f"lock({p.lock_trigger_pts}->{p.lock_level_pts})"}
    for bit, nm in names.items():
        if p.protection & bit:
            parts.append(nm + ("" if bit == 16 else (" immediate" if p.prot_start_mode == 0 else f" after {p.prot_start_pts}")))
    if p.ma_exit: parts.append("MA18 close exit")
    if p.use_risk_filter: parts.append(f"riskFilter {p.max_loss_pts}")
    if p.time_exit_bars: parts.append(f"timeExit {p.time_exit_bars} bars")
    if p.thr_mode == 1: parts.append("[thresholds in 0.01 ATR]")
    if p.thr_mode == 2: parts.append("[thresholds in 0.01 R]")
    return " + ".join(parts) if parts else "SL only"


def filter_desc(p: E.Params) -> str:
    parts = [f"MA{p.fast}/{p.trend}" if p.use_trend else f"MA{p.fast} only", f"{p.confirm_bars}-bar confirm"]
    if p.use_volume: parts.append(f"volume>SMA{p.vol_period}")
    if p.use_adx: parts.append(f"ADX>={p.adx_min}" + (" rising" if p.adx_rising else "") + (" consecutive" if p.adx_consecutive else ""))
    if p.use_session: parts.append("hours " + ",".join(map(str, p.session_hours)))
    if p.use_sl_pct: parts.append(f"SL<={p.max_sl_pct}% balance")
    sl = {0: "swing SL", 1: f"ATR SL {p.sl_atr_mult}x", 2: f"swing SL capped {p.sl_cap_pts}", 3: f"swing SL floor {p.sl_floor_atr} ATR", 4: f"swing SL clamp [{p.sl_floor_atr},{p.sl_atr_mult}] ATR",
          5: "MA18 SL", 6: f"fixed SL {p.sl_cap_pts}", 7: f"swing - {p.sl_atr_mult} ATR"}[p.sl_mode]
    parts.append(sl)
    if p.min_sl_pts: parts.append(f"minSL {p.min_sl_pts}")
    if p.pending_max_bars: parts.append(f"pending expires {p.pending_max_bars} bars")
    if not p.pending_invalidate: parts.append("no pending invalidation")
    return ", ".join(parts)


def run_period(p: E.Params, start: str, end: str, cost: str = "B_real") -> tuple[pd.DataFrame, dict, dict]:
    q = replace(p, start=start, end=end, **COST[cost])
    tr, st = E.run(q)
    m = E.metrics(tr, st, q.start_balance, E.months_between(start, end))
    return tr, st, m


def run_splits(p: E.Params, cost: str = "B_real", splits: dict | None = None) -> dict:
    out = {}
    for name, (a, b) in (splits or SPLITS).items():
        _, _, m = run_period(p, a, b, cost)
        out[name] = m
    return out


def metrics_from_trades(tr: pd.DataFrame, start_balance: float, months: float | None = None) -> dict:
    """Metrics for a time slice of a fixed-lot run (trades do not depend on the balance in the strategy view)."""
    st = {"final_balance": start_balance + float(tr["pnl"].sum()) if len(tr) else start_balance, "maxdd_equity": 0.0, "min_balance": start_balance, "ruin": 0.0}
    if len(tr):
        bal_before = start_balance + tr["pnl"].cumsum() - tr["pnl"]
        eq_min = bal_before - tr["mae_usd"]
        peak = np.maximum.accumulate(np.concatenate([[start_balance], (start_balance + tr["pnl"].cumsum()).to_numpy()]))[1:]
        st["maxdd_equity"] = float((peak - eq_min.to_numpy()).max()); st["min_balance"] = float((start_balance + tr["pnl"].cumsum()).min())
    return E.metrics(tr, st, start_balance, months)


def slice_trades(tr: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    if len(tr) == 0:
        return tr
    return tr[(tr["time_in"] >= pd.Timestamp(a)) & (tr["time_in"] < pd.Timestamp(b))]


KEYS = ("trades", "net_profit", "profit_factor", "win_rate", "expectancy", "expectancy_r", "max_dd_usd", "giveback_avg", "profit_to_loss_2usd", "avg_hold_min")


def evaluate(p: E.Params) -> tuple[dict, pd.DataFrame]:
    """Run once over the full period; ALL + DEV/VAL/OOS metrics from time slices of the same trade list."""
    tr, st = E.run(p)
    res = {"ALL": E.metrics(tr, st, p.start_balance, E.months_between(p.start, p.end))}
    for nm, (a, b) in SPLITS.items():
        res[nm] = metrics_from_trades(slice_trades(tr, a, b), p.start_balance, E.months_between(a, b))
    return res, tr


def classify(base: dict, var: dict) -> str:
    """Declared before any result was seen. Helpful = expectancy/R and PF improve in DEV, VAL and OOS with >= 30 trades each;
    Harmful = worse expectancy/R in >= 2 splits or > 95% of trades removed; otherwise Neutral. A variant that is still a net
    loser over the full period is flagged '(still negative)' so 'helpful' is never read as 'profitable'."""
    better = worse = 0; enough = True
    for nm in ("DEV", "VAL", "OOS"):
        b, v = base[nm], var[nm]
        if v["trades"] < 30:
            enough = False
        vb = v.get("expectancy_r"); bb = b.get("expectancy_r"); vpf = v.get("profit_factor"); bpf = b.get("profit_factor")
        if vb is None or bb is None or np.isnan(vb) or np.isnan(bb):
            worse += 1; continue
        if vb > bb and (vpf or 0) > (bpf or 0):
            better += 1
        elif vb < bb:
            worse += 1
    if var["ALL"]["trades"] <= 0.05 * base["ALL"]["trades"]:
        return "Harmful (removes >95% of trades)"
    neg = " (still negative)" if var["ALL"]["net_profit"] < 0 else ""
    if better == 3 and enough:
        return "Helpful" + neg
    if worse >= 2:
        return "Harmful"
    return "Neutral" + neg


def brief(m: dict) -> dict:
    keys = ("trades", "net_profit", "profit_factor", "win_rate", "expectancy", "expectancy_r", "max_dd_usd", "max_dd_pct", "avg_win", "avg_loss", "max_consec_losses",
            "giveback_avg", "profit_to_loss_2usd", "profit_to_loss_1r", "avg_hold_min", "t_stat", "end_balance", "ruin")
    return {k: m.get(k) for k in keys}


def save_json(obj, name: str):
    with open(os.path.join(RES, name), "w") as f:
        json.dump(obj, f, indent=1, default=_default)


def _default(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, (np.ndarray,)): return o.tolist()
    if isinstance(o, float) and np.isnan(o): return None
    return str(o)


# ---------------------------------------------------------------------------------------------------- regimes
_REGIME = None


def regime_table() -> pd.DataFrame:
    """Daily regime labels from the D1 series (server-time days): trend strength (D1 ADX14), direction (MA18 vs MA200),
    volatility tercile (ATR14 / close, rolling 1y percentile), breakout / sharp-reversal days."""
    global _REGIME
    if _REGIME is not None:
        return _REGIME
    path = E.load_path("h1")
    tf = E.build_tf(path, 1440)
    h, l, c = tf["h"], tf["l"], tf["c"]
    d = pd.DataFrame({"day": tf["t"] // 86400, "close": c, "high": h, "low": l})
    d["adx"] = E.adx_mt5(h, l, c, 14)
    d["ma18"] = E.sma(c, 18); d["ma200"] = E.sma(c, 200)
    d["atr"] = E.atr_mt5(h, l, c, 14); d["atr_pct"] = d["atr"] / d["close"]
    d["vol_rank"] = d["atr_pct"].rolling(250, min_periods=60).rank(pct=True)
    d["trend"] = np.select([d["adx"] >= 25, d["adx"] >= 18], ["strong_trend", "weak_trend"], "range")
    d["direction"] = np.where(d["ma18"] > d["ma200"], "bull", "bear")
    d["vol"] = np.select([d["vol_rank"] >= 0.67, d["vol_rank"] <= 0.33], ["high_vol", "low_vol"], "mid_vol")
    rng20 = d["close"].rolling(20).max(); rng20l = d["close"].rolling(20).min()
    d["breakout"] = (d["close"] >= rng20.shift(1)) | (d["close"] <= rng20l.shift(1))
    ret = d["close"].pct_change()
    d["sharp_reversal"] = (ret.abs() >= 2 * d["atr_pct"]) & (np.sign(ret) != np.sign(ret.shift(1)))
    d["big_move"] = ret.abs() >= 0.02
    _REGIME = d.set_index("day")
    return _REGIME


def tag_regimes(tr: pd.DataFrame) -> pd.DataFrame:
    if len(tr) == 0:
        return tr
    r = regime_table()
    day = (tr["time_in"].astype("int64") // 10**9 // 86400) - 1   # regime known at the previous completed day
    tr = tr.copy()
    for col in ("trend", "direction", "vol", "breakout", "sharp_reversal", "big_move"):
        tr["regime_" + col] = r[col].reindex(day).to_numpy()
    tr["regime"] = tr["regime_trend"].astype(str) + "/" + tr["regime_vol"].astype(str)
    return tr


def by_group(tr: pd.DataFrame, col: str) -> pd.DataFrame:
    if len(tr) == 0:
        return pd.DataFrame()
    g = tr.groupby(col)
    out = pd.DataFrame({"trades": g.size(), "net": g["pnl"].sum().round(2), "win_rate": (100 * g["pnl"].apply(lambda s: (s > 0).mean())).round(1),
                        "expectancy": g["pnl"].mean().round(3), "pf": g["pnl"].apply(lambda s: s[s > 0].sum() / max(-s[s < 0].sum(), 1e-9)).round(2),
                        "avg_mfe": g["mfe_usd"].mean().round(2), "giveback_avg": g["giveback_usd"].mean().round(2),
                        "p2l_2usd": g.apply(lambda x: int(((x["mfe_usd"] >= 2) & (x["pnl"] < 0)).sum()))})
    return out
