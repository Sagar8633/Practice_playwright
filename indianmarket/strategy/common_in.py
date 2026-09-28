"""Shared research plumbing for the Indian-market study: windows, splits, metrics, regimes, gates, experiment log."""
from __future__ import annotations

import csv, json, math, os
from datetime import date

import numpy as np
import pandas as pd

import engine_in as E
import costs as CO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, "research"); os.makedirs(RESEARCH, exist_ok=True)
LOG = os.path.join(RESEARCH, "experiment_log.csv")

INSTRUMENTS = ("nifty50", "banknifty")
TFS = (1, 3, 5, 10, 15, 30, 60, 120, 240, 375)
TF_NAME = {1: "1m", 3: "3m", 5: "5m", 10: "10m", 15: "15m", 30: "30m", 60: "1h", 120: "2h", 240: "4h", 375: "D1"}
DATA_START, DATA_END = "2022-01-03", "2026-09-26"
YEARS = (2022, 2023, 2024, 2025, 2026)
# research structure of the brief: years 1-3 training, year 4 validation, year 5 out-of-sample (the intraday history is 4.7 years)
SPLITS = {"TRAIN": ("2022-01-03", "2024-08-31"), "VAL": ("2024-09-01", "2025-08-31"), "OOS": ("2025-09-01", "2026-09-26")}
# rolling walk-forward: 24 months of training, the next 6 months traded
WF_FOLDS = [(("2022-01-03", "2023-12-31"), ("2024-01-01", "2024-06-30")), (("2022-07-01", "2024-06-30"), ("2024-07-01", "2024-12-31")),
            (("2023-01-01", "2024-12-31"), ("2025-01-01", "2025-06-30")), (("2023-07-01", "2025-06-30"), ("2025-07-01", "2025-12-31")),
            (("2024-01-01", "2025-12-31"), ("2026-01-01", "2026-09-26"))]
SESSION_SLOTS = {"opening": (0, 1), "morning": tuple(range(2, 9)), "midday": tuple(range(9, 17)), "afternoon": tuple(range(17, 23)), "closing": (23, 24)}

# the two configurations "we developed": the literal v1.00 rules and the ATR-scaled final H4 exit stack from the gold study
ASIS = dict(fast=18, trend=200, use_volume=False, swing_strength=2, swing_search=100, entry_buffer_pts=10, be_enable=True, be_trigger_pts=500, be_offset_pts=10,
            protection=1, prot_start_mode=1, prot_start_pts=500, swing_buffer_pts=50, ma_exit=True, use_sl_pct=False, thr_mode=0)
FINAL_H4 = dict(fast=18, trend=200, use_volume=False, swing_strength=2, swing_search=100, entry_buffer_pts=0, be_enable=True, be_trigger_pts=200, be_offset_pts=10,
                protection=4, prot_start_mode=0, prot_start_pts=0, trail_start_pts=500, trail_dist_pts=50, trail_step_pts=10, atr_period=22, ma_exit=True, use_sl_pct=False, thr_mode=1)
CONFIGS = {"ASIS": ASIS, "FINAL_H4": FINAL_H4}


def months_between(a: str, b: str) -> float:
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.4375


def run(instr: str, tf: int, cfg: dict, scenario: str = "B", start: str = DATA_START, end: str = DATA_END, path: str | None = None, **over):
    """Engine run + cost columns. Returns (trades, stats)."""
    p = E.Params(tf_minutes=tf, path=path or instr, start=start, end=end, **{**cfg, **CO.engine_costs(instr, scenario), **over})
    allow = over.pop("_allow", None)
    tr, st = E.run(p, allow_buy=None if allow is None else allow[0], allow_sell=None if allow is None else allow[1])
    return CO.apply_costs(tr, instr, scenario), st


def run_allow(instr, tf, cfg, allow_buy, allow_sell, scenario="B", start=DATA_START, end=DATA_END, path=None, **over):
    p = E.Params(tf_minutes=tf, path=path or instr, start=start, end=end, **{**cfg, **CO.engine_costs(instr, scenario), **over})
    tr, st = E.run(p, allow_buy=allow_buy, allow_sell=allow_sell)
    return CO.apply_costs(tr, instr, scenario), st


# ----------------------------------------------------------------------------------------------------------------
# Metrics (points per unit, rupees per lot, R multiples)
# ----------------------------------------------------------------------------------------------------------------

def _streaks(x):
    cw = cl = mw = ml = 0
    for v in x:
        if v > 0: cw += 1; cl = 0
        elif v < 0: cl += 1; cw = 0
        else: cw = cl = 0
        mw = max(mw, cw); ml = max(ml, cl)
    return mw, ml


def _dd(series: np.ndarray):
    """max drawdown of a cumulative series and its longest peak-to-recovery stretch (in observations)."""
    peak = np.maximum.accumulate(np.concatenate([[0.0], series]))[1:]
    dd = peak - series
    # duration: longest run of dd > 0
    best = cur = 0
    for v in dd:
        cur = cur + 1 if v > 0 else 0
        best = max(best, cur)
    return float(dd.max()) if len(dd) else 0.0, best


def summarize(tr: pd.DataFrame, instr: str, start: str, end: str) -> dict:
    """Full metric set of the brief for one trade list (costed)."""
    lot = CO.INSTR[instr]["lot"]; cap = CO.INSTR[instr]["capital_per_lot"]
    months = months_between(start, end); yrs = months / 12.0
    m = {"trades": int(len(tr)), "months": round(months, 2)}
    if len(tr) == 0:
        m.update(net_pts=0.0, net_rs=0.0, pf=float("nan"), win_rate=float("nan"), exp_pts=float("nan"), exp_r=float("nan"), net_r=0.0, max_dd_pts=0.0, max_dd_rs=0.0, sharpe_m=float("nan"))
        return m
    pts = tr["pts_net"].to_numpy(); rs = tr["rs_net"].to_numpy(); r = tr["r_net"].to_numpy(); gross = tr["pts"].to_numpy()
    w = pts[pts > 0]; l = pts[pts < 0]
    m.update(wins=int(len(w)), losses=int(len(l)), win_rate=round(100.0 * len(w) / len(pts), 1),
             avg_win_pts=round(float(w.mean()), 2) if len(w) else 0.0, avg_loss_pts=round(float(l.mean()), 2) if len(l) else 0.0,
             payoff=round(float(abs(w.mean() / l.mean())), 3) if len(w) and len(l) else float("nan"),
             pf=round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else float("inf"),
             gross_pts=round(float(gross.sum()), 1), fees_pts=round(float(tr["fees_pts"].sum()), 1), net_pts=round(float(pts.sum()), 1),
             gross_profit_pts=round(float(w.sum()), 1), gross_loss_pts=round(float(l.sum()), 1),
             net_rs=round(float(rs.sum()), 0), exp_pts=round(float(pts.mean()), 3), exp_rs=round(float(rs.mean()), 1),
             exp_r=round(float(np.nanmean(r)), 4), median_r=round(float(np.nanmedian(r)), 4), net_r=round(float(np.nansum(r)), 2),
             largest_win_pts=round(float(pts.max()), 1), largest_loss_pts=round(float(pts.min()), 1))
    mw, ml = _streaks(pts); m["max_consec_wins"] = mw; m["max_consec_losses"] = ml
    cum = np.cumsum(pts); dd, ddn = _dd(cum); m["max_dd_pts"] = round(dd, 1); m["max_dd_rs"] = round(dd * lot, 0); m["max_dd_pct_cap"] = round(100.0 * dd * lot / cap, 1)
    m["dd_duration_trades"] = int(ddn)
    # drawdown duration in calendar days from the equity by trade close time
    eq = pd.Series(np.cumsum(rs), index=tr["time_out"].to_numpy()); pk = eq.cummax(); under = eq < pk
    if under.any():
        runs = (~under).cumsum(); spans = eq[under].groupby(runs[under]).apply(lambda s: (s.index.max() - s.index.min()).days)
        m["dd_duration_days"] = int(spans.max())
    else:
        m["dd_duration_days"] = 0
    m["recovery_factor"] = round(float(pts.sum() / dd), 2) if dd > 0 else float("inf")
    # R distribution and concentration
    rr = r[~np.isnan(r)]
    if len(rr):
        q = np.percentile(rr, [5, 25, 50, 75, 95]); m["r_p05"], m["r_p25"], m["r_p50"], m["r_p75"], m["r_p95"] = [round(float(x), 3) for x in q]
        m["r_ge_1"] = round(100.0 * float((rr >= 1).mean()), 1); m["r_le_m1"] = round(100.0 * float((rr <= -1).mean()), 1)
    srt = np.sort(pts)[::-1]; tot = pts.sum(); top10 = max(1, int(math.ceil(0.1 * len(pts))))
    m["top10pct_share"] = round(100.0 * float(srt[:top10].sum() / tot), 1) if tot > 0 else float("nan")
    m["top5_trades_share"] = round(100.0 * float(srt[:5].sum() / tot), 1) if tot > 0 else float("nan")
    m["net_ex_top5_pts"] = round(float(tot - srt[:5].sum()), 1)
    # time-based: monthly rupee P&L per lot on the stated capital
    mon = pd.Series(rs, index=tr["time_out"].to_numpy()).resample("MS").sum()
    idx = pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end), freq="MS"); mon = mon.reindex(idx, fill_value=0.0)
    ret = mon / cap
    m["sharpe_m"] = round(float(ret.mean() / ret.std(ddof=1) * math.sqrt(12)), 2) if len(ret) > 1 and ret.std(ddof=1) > 0 else float("nan")
    dn = ret[ret < 0]
    m["sortino_m"] = round(float(ret.mean() / math.sqrt((dn ** 2).sum() / len(ret)) * math.sqrt(12)), 2) if len(dn) and (dn ** 2).sum() > 0 else float("inf") if ret.mean() > 0 else float("nan")
    m["cagr_pct"] = round(100.0 * ((1 + rs.sum() / cap) ** (1 / yrs) - 1), 1) if yrs > 0 and rs.sum() > -cap else -100.0
    m["trades_per_month"] = round(len(tr) / months, 2); m["trades_per_day"] = round(len(tr) / (months * 20.8), 3)
    m["pos_months_pct"] = round(100.0 * float((mon > 0).mean()), 1)
    if len(pts) > 1:
        m["t_stat"] = round(float(pts.mean() / (pts.std(ddof=1) / math.sqrt(len(pts)))), 2)
        rng = np.random.default_rng(7); bs = np.array([rng.choice(pts, len(pts)).mean() for _ in range(2000)])
        m["exp_ci95_lo"], m["exp_ci95_hi"] = round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)
    m["exit_mix"] = {k: int(v) for k, v in tr["exit_reason"].value_counts().items()}
    m["long_trades"] = int((tr.side == 1).sum()); m["long_net_pts"] = round(float(pts[tr.side.to_numpy() == 1].sum()), 1)
    m["short_trades"] = int((tr.side == -1).sum()); m["short_net_pts"] = round(float(pts[tr.side.to_numpy() == -1].sum()), 1)
    m["avg_hold_min"] = round(float(tr["hold_min"].mean()), 1); m["median_hold_min"] = round(float(tr["hold_min"].median()), 1)
    m["avg_risk_pts"] = round(float((tr["risk_usd"] / tr["lots"]).mean()), 1)
    return m


def yearly(tr: pd.DataFrame, instr: str) -> pd.DataFrame:
    rows = []
    for y in YEARS:
        s = tr[tr.time_out.dt.year == y]
        a, b = f"{y}-01-01", (f"{y}-12-31" if y < 2026 else DATA_END)
        mm = summarize(s, instr, a, b)
        rows.append({"year": y, "trades": mm["trades"], "win_rate": mm.get("win_rate"), "pf": mm.get("pf"), "exp_pts": mm.get("exp_pts"), "exp_r": mm.get("exp_r"),
                     "net_pts": mm.get("net_pts"), "net_r": mm.get("net_r"), "max_dd_pts": mm.get("max_dd_pts"), "net_rs": mm.get("net_rs")})
    return pd.DataFrame(rows)


def monthly(tr: pd.DataFrame) -> pd.Series:
    return tr.groupby(tr.time_out.dt.to_period("M"))["pts_net"].sum()


def slice_trades(tr: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    return tr[(tr.time_in >= pd.Timestamp(a)) & (tr.time_in <= pd.Timestamp(b) + pd.Timedelta(days=1))]


def split_metrics(tr: pd.DataFrame, instr: str) -> dict:
    return {k: summarize(slice_trades(tr, a, b), instr, a, b) for k, (a, b) in SPLITS.items()}


def classify(sm: dict, min_trades: int = 30) -> str:
    """Verdict rule fixed before looking at results: positive expectancy after costs (scenario B) in TRAIN, VAL and OOS
    with at least `min_trades` trades in each, and PF > 1 in each -> 'robust'; positive overall but not in every split -> 'unstable';
    otherwise 'negative'."""
    ok = all(v["trades"] >= min_trades and v.get("exp_pts", 0) > 0 and v.get("pf", 0) > 1.0 for v in sm.values())
    tot = sum(v.get("net_pts", 0) for v in sm.values())
    if ok:
        return "robust"
    return "unstable" if tot > 0 else "negative"


# ----------------------------------------------------------------------------------------------------------------
# Regimes, gaps, higher-timeframe gates
# ----------------------------------------------------------------------------------------------------------------

def daily_frame(instr: str) -> pd.DataFrame:
    """Daily bars built from the 1-minute path (2022-) merged with the Upstox daily file before 2022, for regime tags."""
    d = pd.read_csv(os.path.join(ROOT, "data", instr, f"{instr}_daily_upstox.csv.gz"), parse_dates=["time"])
    d["date"] = d["time"].dt.normalize(); d = d.drop_duplicates("date").set_index("date")[["open", "high", "low", "close"]].sort_index()
    return d


def regime_tags(instr: str) -> pd.DataFrame:
    """Per session (known at the previous close, so usable at that session's open):
    trend = 63-session return of the previous close (strong_bull > +8%, weak_bull +2..+8, sideways -2..+2, weak_bear -8..-2, strong_bear < -8);
    vol = 20-session realised volatility (annualised) ranked within 2015-2026 (low < p25, normal, high > p75, extreme > p95);
    gap = today's open vs previous close in % and in ATR(14) units (uses the open, known at 09:15)."""
    d = daily_frame(instr)
    c = d["close"]; prev = c.shift(1)
    ret63 = (prev / c.shift(64) - 1) * 100
    lr = np.log(c / prev); rv = lr.rolling(20).std() * math.sqrt(252) * 100; rv_prev = rv.shift(1)
    ref = rv_prev[(rv_prev.index >= "2015-01-01")]
    p25, p75, p95 = np.nanpercentile(ref, [25, 75, 95])
    tr_ = np.maximum(d["high"] - d["low"], np.maximum((d["high"] - prev).abs(), (d["low"] - prev).abs())); atr14 = tr_.rolling(14).mean().shift(1)
    gap_pct = (d["open"] / prev - 1) * 100; gap_atr = (d["open"] - prev) / atr14
    trend = pd.cut(ret63, [-np.inf, -8, -2, 2, 8, np.inf], labels=["strong_bear", "weak_bear", "sideways", "weak_bull", "strong_bull"]).astype(str)
    vol = pd.cut(rv_prev, [-np.inf, p25, p75, p95, np.inf], labels=["low", "normal", "high", "extreme"]).astype(str)
    out = pd.DataFrame({"trend": trend, "vol": vol, "ret63": ret63, "rv20": rv_prev, "gap_pct": gap_pct, "gap_atr": gap_atr, "atr14": atr14,
                        "prev_high": d["high"].shift(1), "prev_low": d["low"].shift(1), "prev_close": prev, "range_pct": (d["high"] - d["low"]) / prev * 100})
    out.attrs["vol_cuts"] = (float(p25), float(p75), float(p95))
    return out


def tag_trades(tr: pd.DataFrame, tags: pd.DataFrame) -> pd.DataFrame:
    t = tr.copy(); key = t["time_in"].dt.normalize()
    for col in ("trend", "vol", "gap_pct", "gap_atr", "range_pct"):
        t[col] = key.map(tags[col])
    t["gap_class"] = pd.cut(t["gap_pct"].abs(), [-np.inf, 0.25, 0.75, np.inf], labels=["small", "medium", "large"]).astype(str)
    t["gap_dir"] = np.sign(t["gap_pct"]).map({1.0: "up", -1.0: "down", 0.0: "flat"})
    return t


def htf_gate(instr: str, tf_entry: int, tf_htf: int, fast: int = 18, trend: int = 200, mode: str = "ma", path: str | None = None):
    """allow_buy / allow_sell per entry bar from the last COMPLETED higher-timeframe bar at the decision moment.
    mode 'ma': MA_fast > MA_trend on the HTF (buy) / < (sell). mode 'close': close > MA_fast too."""
    pth = E.load_path(path or instr); lo = E.build_tf(pth, tf_entry); hi = E.build_tf(pth, tf_htf)
    ma_f = E.sma(hi["c"], fast); ma_t = E.sma(hi["c"], trend)
    # decision moment for entry bar j = start of bar j+1 (first path bar of the next signal bar)
    dec = np.append(lo["t"][1:], lo["t"][-1] + 1)
    idx = np.searchsorted(hi["t"], dec, side="right") - 1 - 1        # bar containing the moment, minus one = last completed
    ok = idx >= 0
    up = np.zeros(lo["n"], dtype=np.int64); dn = np.zeros(lo["n"], dtype=np.int64)
    ii = np.clip(idx, 0, hi["n"] - 1)
    cond_up = (ma_f[ii] > ma_t[ii]) & ok; cond_dn = (ma_f[ii] < ma_t[ii]) & ok
    if mode == "close":
        cond_up &= hi["c"][ii] > ma_f[ii]; cond_dn &= hi["c"][ii] < ma_f[ii]
    up[np.nan_to_num(cond_up.astype(float)) > 0] = 1; dn[np.nan_to_num(cond_dn.astype(float)) > 0] = 1
    return up, dn


def day_gate(instr: str, tf_entry: int, allowed_dates: pd.DatetimeIndex, path: str | None = None):
    """allow arrays that permit setups only on the listed sessions (regime / gap experiments)."""
    pth = E.load_path(path or instr); lo = E.build_tf(pth, tf_entry)
    days = pd.to_datetime(lo["t"], unit="s").normalize()
    ok = np.asarray(days.isin(allowed_dates), dtype=np.int64)
    return ok, ok.copy()


# ----------------------------------------------------------------------------------------------------------------
# Experiment log
# ----------------------------------------------------------------------------------------------------------------

LOG_COLS = ["experiment_id", "date", "instrument", "timeframe", "config", "parameters", "filters", "data_period", "scenario", "trades", "win_rate", "pf",
            "expectancy_pts", "expectancy_r", "net_pts", "net_r", "max_dd_pts", "sharpe_m", "train_net_pts", "val_net_pts", "oos_net_pts", "oos_pf", "verdict", "decision", "reason"]


def log_experiment(exp_id: str, instr: str, tf: int, config: str, params: dict, filters: str, period: tuple, scenario: str, m: dict, sm: dict | None,
                   decision: str, reason: str):
    new = not os.path.exists(LOG)
    row = {"experiment_id": exp_id, "date": date.today().isoformat(), "instrument": instr, "timeframe": TF_NAME.get(tf, str(tf)), "config": config,
           "parameters": json.dumps(params, sort_keys=True, default=str), "filters": filters, "data_period": f"{period[0]}..{period[1]}", "scenario": scenario,
           "trades": m.get("trades"), "win_rate": m.get("win_rate"), "pf": m.get("pf"), "expectancy_pts": m.get("exp_pts"), "expectancy_r": m.get("exp_r"),
           "net_pts": m.get("net_pts"), "net_r": m.get("net_r"), "max_dd_pts": m.get("max_dd_pts"), "sharpe_m": m.get("sharpe_m"),
           "train_net_pts": sm["TRAIN"].get("net_pts") if sm else None, "val_net_pts": sm["VAL"].get("net_pts") if sm else None,
           "oos_net_pts": sm["OOS"].get("net_pts") if sm else None, "oos_pf": sm["OOS"].get("pf") if sm else None,
           "verdict": classify(sm) if sm else "", "decision": decision, "reason": reason}
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append("" if math.isnan(v) else (floatfmt.format(v) if abs(v) < 1e6 else f"{v:.3g}"))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)
