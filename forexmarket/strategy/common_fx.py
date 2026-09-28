"""Shared plumbing for the multi-instrument study: instrument specs (from XM), cost scenarios, USD conversion, splits, metrics,
regimes, gates and the experiment log. Money unit: USD per 0.01 lot (the minimum XM lot)."""
from __future__ import annotations

import csv, json, math, os
from datetime import date

import numpy as np
import pandas as pd

import engine_fx as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, "research"); os.makedirs(RESEARCH, exist_ok=True)
LOG = os.path.join(RESEARCH, "experiment_log.csv")
XMSYM = {"eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY", "audusd": "AUDUSD", "usdcad": "USDCAD", "usdchf": "USDCHF", "nzdusd": "NZDUSD",
         "xagusd": "SILVER", "btcusd": "BTCUSD", "lightcmdusd": "OILCash"}
NAME = {"eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY", "audusd": "AUDUSD", "usdcad": "USDCAD", "usdchf": "USDCHF", "nzdusd": "NZDUSD",
        "xagusd": "Silver (XAGUSD)", "btcusd": "Bitcoin (BTCUSD)", "lightcmdusd": "US Oil (WTI)"}
INSTRUMENTS = tuple(XMSYM)
# slippage per side in points for scenario B / C (XM market and stop orders in liquid hours; C = fast market)
SLIP = {"eurusd": (3, 10), "gbpusd": (3, 10), "usdjpy": (3, 10), "audusd": (3, 10), "usdcad": (3, 10), "usdchf": (3, 10), "nzdusd": (3, 10),
        "xagusd": (5, 15), "btcusd": (300, 1000), "lightcmdusd": (3, 10)}
TFS = (1, 3, 5, 10, 15, 30, 60, 120, 240, 1440)
TF_NAME = {1: "1m", 3: "3m", 5: "5m", 10: "10m", 15: "15m", 30: "30m", 60: "1h", 120: "2h", 240: "4h", 1440: "D1"}
DATA_START, DATA_END = "2021-09-01", "2026-09-26"
YEARS = (2021, 2022, 2023, 2024, 2025, 2026)
SPLITS = {"TRAIN": ("2021-09-01", "2024-08-31"), "VAL": ("2024-09-01", "2025-08-31"), "OOS": ("2025-09-01", "2026-09-26")}
WF_FOLDS = [(("2021-09-01", "2023-08-31"), ("2023-09-01", "2024-02-29")), (("2022-03-01", "2024-02-29"), ("2024-03-01", "2024-08-31")),
            (("2022-09-01", "2024-08-31"), ("2024-09-01", "2025-02-28")), (("2023-03-01", "2025-02-28"), ("2025-03-01", "2025-08-31")),
            (("2023-09-01", "2025-08-31"), ("2025-09-01", "2026-02-28")), (("2024-03-01", "2026-02-28"), ("2026-03-01", "2026-09-26"))]
CAPITAL_PER_001 = 1000.0           # USD notional capital per 0.01 lot for drawdown % and CAGR (an assumption, stated in every report)

ASIS = dict(fast=18, trend=200, use_volume=True, swing_strength=2, swing_search=100, entry_buffer_pts=10, be_enable=True, be_trigger_pts=500, be_offset_pts=10,
            protection=1, prot_start_mode=1, prot_start_pts=500, swing_buffer_pts=50, ma_exit=True, use_sl_pct=False, thr_mode=0)
FINAL_H4 = dict(fast=18, trend=200, use_volume=True, swing_strength=2, swing_search=100, entry_buffer_pts=0, be_enable=True, be_trigger_pts=200, be_offset_pts=10,
                protection=4, prot_start_mode=0, prot_start_pts=0, trail_start_pts=500, trail_dist_pts=50, trail_step_pts=10, atr_period=22, ma_exit=True, use_sl_pct=False, thr_mode=1)
CONFIGS = {"ASIS": ASIS, "FINAL_H4": FINAL_H4}

_SPECS = None


def specs(instr: str) -> dict:
    """Instrument parameters for the engine from XM's symbol specification."""
    global _SPECS
    if _SPECS is None:
        _SPECS = json.load(open(os.path.join(ROOT, "data", "xm", "xm_symbol_specs.json")))
    s = _SPECS[XMSYM[instr]]
    d = dict(point=float(s["point"]), contract=float(s["trade_contract_size"]), swap_long_pts=float(s["swap_long"]), swap_short_pts=float(s["swap_short"]),
             swap3day=(-1 if instr == "btcusd" else 2), swap_daily=(instr == "btcusd"), digits=int(s["digits"]), quote=s["currency_profit"], swap_mode=int(s["swap_mode"]))
    if d["swap_mode"] != 1:          # OILCash: swap in another mode with 0/0 -> none
        d["swap_long_pts"] = 0.0; d["swap_short_pts"] = 0.0
    return d


_PX: dict = {}


def median_price(instr: str) -> float:
    """Median close of the instrument's hourly history (to express quote-currency amounts in USD)."""
    if instr not in _PX:
        f = os.path.join(ROOT, "data", instr, "h1_server.npz"); _PX[instr] = float(np.median(np.load(f)["c"])) if os.path.exists(f) else 1.0
    return _PX[instr]


def usd_per_point_001(instr: str) -> float:
    """USD value of one point for 0.01 lot (quote currency converted at the median price for USD-base pairs)."""
    sp = specs(instr); v = sp["point"] * sp["contract"] * 0.01
    return v / median_price(instr) if sp["quote"] != "USD" else v


def engine_costs(instr: str, scenario: str) -> dict:
    if scenario == "A":
        return dict(spread_fixed_pts=0.0, slippage_pts=0.0, swap=False)
    if scenario == "B":
        return dict(spread_fixed_pts=-1.0, spread_mult=1.0, slippage_pts=float(SLIP[instr][0]), swap=True)
    return dict(spread_fixed_pts=-1.0, spread_mult=1.5, slippage_pts=float(SLIP[instr][1]), swap=True)


def months_between(a: str, b: str) -> float:
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.4375


def to_usd(tr: pd.DataFrame, instr: str) -> pd.DataFrame:
    """Engine money is in the quote currency; convert USD-base pairs (USDJPY/USDCAD/USDCHF) at the exit price."""
    tr = tr.copy(); q = specs(instr)["quote"]
    fx = 1.0 / tr["exit"] if q != "USD" else 1.0
    for c in ("pnl", "swap", "risk_usd", "mfe_usd", "mae_usd", "gross_usd", "giveback_usd", "slip_usd", "min_equity"):
        if c in tr:
            tr[c] = tr[c] * fx
    tr["usd"] = tr["pnl"]            # USD per `lots` lots (0.01)
    tr["r_usd"] = np.where(tr["risk_usd"] > 0, tr["pnl"] / tr["risk_usd"], np.nan)
    return tr


_HASVOL: dict = {}


def has_volume(instr: str) -> bool:
    if instr not in _HASVOL:
        f = os.path.join(ROOT, "data", instr, "audit.json")
        _HASVOL[instr] = bool(json.load(open(f)).get("has_volume", True)) if os.path.exists(f) else True
    return _HASVOL[instr]


def default_path(instr: str, tf: int):
    """Minute path when the instrument has >= 48 months of it; otherwise XM's 15-minute path for 15m and up; None below 15m."""
    aud = os.path.join(ROOT, "data", instr, "audit.json"); months = json.load(open(aud)).get("m1_months_present", 0) if os.path.exists(aud) else 0
    if os.path.exists(os.path.join(ROOT, "data", instr, "m1_server.npz")) and months >= 48:
        return instr, DATA_START
    f = os.path.join(ROOT, "data", instr, "m15_server.npz")
    if tf >= 15 and os.path.exists(f):
        t0 = pd.Timestamp(np.load(f)["t"][0], unit="s"); return instr + "_m15", str(max(t0.normalize(), pd.Timestamp(DATA_START)))[:10]
    return None, None


def run(instr: str, tf: int, cfg: dict, scenario: str = "B", start: str = DATA_START, end: str = DATA_END, path: str | None = None, allow=None, **over):
    sp = specs(instr); ep = {k: sp[k] for k in ("point", "contract", "swap_long_pts", "swap_short_pts", "swap3day", "swap_daily")}
    if path is None:
        path, pstart = default_path(instr, tf)
        if path is None:
            raise FileNotFoundError(f"{instr}: no path for {tf}-minute bars")
        if pstart and pd.Timestamp(pstart) > pd.Timestamp(start):
            start = pstart
    if not has_volume(instr):
        over = {**over, "use_volume": False}      # no volume in the data (histdata): the EA volume filter cannot be evaluated
    p = E.Params(tf_minutes=tf, path=path or instr, start=start, end=end, lots=0.01, margin_check=False, start_balance=1e9, **{**ep, **cfg, **engine_costs(instr, scenario), **over})
    tr, st = E.run(p, allow_buy=None if allow is None else allow[0], allow_sell=None if allow is None else allow[1])
    return to_usd(tr, instr), st


# ----------------------------------------------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------------------------------------------

def _streaks(x):
    cw = cl = mw = ml = 0
    for v in x:
        if v > 0: cw += 1; cl = 0
        elif v < 0: cl += 1; cw = 0
        else: cw = cl = 0
        mw = max(mw, cw); ml = max(ml, cl)
    return mw, ml


def summarize(tr: pd.DataFrame, instr: str, start: str, end: str) -> dict:
    cap = CAPITAL_PER_001; months = months_between(start, end); yrs = months / 12.0
    m = {"trades": int(len(tr)), "months": round(months, 2)}
    if len(tr) == 0:
        m.update(net_usd=0.0, pf=float("nan"), win_rate=float("nan"), exp_usd=float("nan"), exp_r=float("nan"), net_r=0.0, max_dd_usd=0.0, sharpe_m=float("nan"))
        return m
    usd = tr["usd"].to_numpy(); r = tr["r_usd"].to_numpy(); w = usd[usd > 0]; l = usd[usd < 0]
    m.update(wins=int(len(w)), losses=int(len(l)), win_rate=round(100.0 * len(w) / len(usd), 1), avg_win_usd=round(float(w.mean()), 3) if len(w) else 0.0, avg_loss_usd=round(float(l.mean()), 3) if len(l) else 0.0,
             payoff=round(float(abs(w.mean() / l.mean())), 3) if len(w) and len(l) else float("nan"), pf=round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else float("inf"),
             gross_profit_usd=round(float(w.sum()), 2), gross_loss_usd=round(float(l.sum()), 2), net_usd=round(float(usd.sum()), 2), swap_usd=round(float(tr["swap"].sum()), 2),
             exp_usd=round(float(usd.mean()), 4), exp_r=round(float(np.nanmean(r)), 4), median_r=round(float(np.nanmedian(r)), 4), net_r=round(float(np.nansum(r)), 2),
             largest_win_usd=round(float(usd.max()), 2), largest_loss_usd=round(float(usd.min()), 2))
    mw, ml = _streaks(usd); m["max_consec_wins"] = mw; m["max_consec_losses"] = ml
    cum = np.cumsum(usd); peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]; dd = peak - cum
    m["max_dd_usd"] = round(float(dd.max()), 2); m["max_dd_pct_cap"] = round(100.0 * float(dd.max()) / cap, 1)
    eq = pd.Series(cum, index=tr["time_out"].to_numpy()); pk = eq.cummax(); under = eq < pk
    m["dd_duration_days"] = int(eq[under].groupby((~under).cumsum()[under]).apply(lambda s_: (s_.index.max() - s_.index.min()).days).max()) if under.any() else 0
    m["recovery_factor"] = round(float(usd.sum() / dd.max()), 2) if dd.max() > 0 else float("inf")
    rr = r[~np.isnan(r)]
    if len(rr):
        q = np.percentile(rr, [5, 25, 50, 75, 95]); m["r_p05"], m["r_p25"], m["r_p50"], m["r_p75"], m["r_p95"] = [round(float(x), 3) for x in q]
        m["r_ge_1"] = round(100.0 * float((rr >= 1).mean()), 1); m["r_le_m1"] = round(100.0 * float((rr <= -1).mean()), 1)
    srt = np.sort(usd)[::-1]; tot = usd.sum(); top10 = max(1, int(math.ceil(0.1 * len(usd))))
    m["top10pct_share"] = round(100.0 * float(srt[:top10].sum() / tot), 1) if tot > 0 else float("nan"); m["top5_trades_share"] = round(100.0 * float(srt[:5].sum() / tot), 1) if tot > 0 else float("nan")
    m["net_ex_top5_usd"] = round(float(tot - srt[:5].sum()), 2)
    mon = pd.Series(usd, index=tr["time_out"].to_numpy()).resample("MS").sum(); idx = pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end), freq="MS"); mon = mon.reindex(idx, fill_value=0.0); ret = mon / cap
    m["sharpe_m"] = round(float(ret.mean() / ret.std(ddof=1) * math.sqrt(12)), 2) if len(ret) > 1 and ret.std(ddof=1) > 0 else float("nan")
    dn = ret[ret < 0]; m["sortino_m"] = round(float(ret.mean() / math.sqrt((dn ** 2).sum() / len(ret)) * math.sqrt(12)), 2) if len(dn) and (dn ** 2).sum() > 0 else (float("inf") if ret.mean() > 0 else float("nan"))
    m["cagr_pct"] = round(100.0 * ((1 + usd.sum() / cap) ** (1 / yrs) - 1), 1) if yrs > 0 and usd.sum() > -cap else -100.0
    m["trades_per_month"] = round(len(tr) / months, 2); m["pos_months_pct"] = round(100.0 * float((mon > 0).mean()), 1)
    if len(usd) > 1:
        m["t_stat"] = round(float(usd.mean() / (usd.std(ddof=1) / math.sqrt(len(usd)))), 2)
        rng = np.random.default_rng(7); bs = np.array([rng.choice(usd, len(usd)).mean() for _ in range(2000)]); m["exp_ci95_lo"], m["exp_ci95_hi"] = round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)
    m["exit_mix"] = {k: int(v) for k, v in tr["exit_reason"].value_counts().items()}
    m["long_trades"] = int((tr.side == 1).sum()); m["long_net_usd"] = round(float(usd[tr.side.to_numpy() == 1].sum()), 2)
    m["short_trades"] = int((tr.side == -1).sum()); m["short_net_usd"] = round(float(usd[tr.side.to_numpy() == -1].sum()), 2)
    m["avg_hold_min"] = round(float(tr["hold_min"].mean()), 1); m["median_hold_min"] = round(float(tr["hold_min"].median()), 1); m["avg_risk_usd"] = round(float(tr["risk_usd"].mean()), 3)
    return m


def yearly(tr: pd.DataFrame, instr: str) -> pd.DataFrame:
    rows = []
    for y in YEARS:
        s_ = tr[tr.time_out.dt.year == y] if len(tr) else tr; a, b = (DATA_START if y == 2021 else f"{y}-01-01"), (f"{y}-12-31" if y < 2026 else DATA_END)
        mm = summarize(s_, instr, a, b)
        rows.append({"year": y, "trades": mm["trades"], "win_rate": mm.get("win_rate"), "pf": mm.get("pf"), "exp_usd": mm.get("exp_usd"), "exp_r": mm.get("exp_r"), "net_usd": mm.get("net_usd"), "net_r": mm.get("net_r"), "max_dd_usd": mm.get("max_dd_usd")})
    return pd.DataFrame(rows)


def slice_trades(tr, a, b):
    if len(tr) == 0 or "time_in" not in tr:
        return tr.iloc[0:0]
    return tr[(tr.time_in >= pd.Timestamp(a)) & (tr.time_in <= pd.Timestamp(b) + pd.Timedelta(days=1))]


def split_metrics(tr, instr):
    return {k: summarize(slice_trades(tr, a, b), instr, a, b) for k, (a, b) in SPLITS.items()}


def classify(sm: dict, min_trades: int = 30) -> str:
    ok = all(v["trades"] >= min_trades and v.get("exp_usd", 0) > 0 and v.get("pf", 0) > 1.0 for v in sm.values())
    tot = sum(v.get("net_usd", 0) for v in sm.values())
    return "robust" if ok else ("unstable" if tot > 0 else "negative")


# ----------------------------------------------------------------------------------------------------------------
# Regimes and gates (server-time days)
# ----------------------------------------------------------------------------------------------------------------

def daily_frame(instr: str) -> pd.DataFrame:
    pth = E.load_path(instr + "_h1") if os.path.exists(os.path.join(ROOT, "data", instr, "h1_server.npz")) else E.load_path(instr)
    d = pd.DataFrame({"t": pd.to_datetime(pth["t"], unit="s"), "o": pth["o"], "h": pth["h"], "l": pth["l"], "c": pth["c"]}); d["date"] = d.t.dt.normalize()
    g = d.groupby("date").agg(open=("o", "first"), high=("h", "max"), low=("l", "min"), close=("c", "last"))
    return g[g.index.weekday < 6] if instr != "btcusd" else g


def regime_tags(instr: str) -> pd.DataFrame:
    """Per server day, known at the previous close: trend = 63-day return divided by its volatility-implied scale (z: strong > 1, weak 0.3-1,
    sideways |z| < 0.3); vol = 20-day realised volatility ranked within the instrument's own history (low < p25, normal, high > p75, extreme > p95)."""
    d = daily_frame(instr); c = d["close"]; prev = c.shift(1)
    lr = np.log(c / prev); rv = lr.rolling(20).std() * math.sqrt(252); rv_prev = rv.shift(1)
    ret63 = prev / c.shift(64) - 1; z = ret63 / (rv_prev * math.sqrt(63 / 252))
    ref = rv_prev.dropna(); p25, p75, p95 = np.nanpercentile(ref, [25, 75, 95])
    tr_ = np.maximum(d["high"] - d["low"], np.maximum((d["high"] - prev).abs(), (d["low"] - prev).abs())); atr14 = tr_.rolling(14).mean().shift(1)
    gap = (d["open"] - prev) / atr14
    trend = pd.cut(z, [-np.inf, -1, -0.3, 0.3, 1, np.inf], labels=["strong_bear", "weak_bear", "sideways", "weak_bull", "strong_bull"]).astype(str)
    vol = pd.cut(rv_prev, [-np.inf, p25, p75, p95, np.inf], labels=["low", "normal", "high", "extreme"]).astype(str)
    out = pd.DataFrame({"trend": trend, "vol": vol, "z63": z, "rv20": rv_prev * 100, "gap_atr": gap, "atr14": atr14, "prev_close": prev, "range_pct": (d["high"] - d["low"]) / prev * 100})
    out.attrs["vol_cuts"] = (float(p25) * 100, float(p75) * 100, float(p95) * 100)
    return out


def tag_trades(tr: pd.DataFrame, tags: pd.DataFrame) -> pd.DataFrame:
    t = tr.copy(); key = t["time_in"].dt.normalize()
    for col in ("trend", "vol", "gap_atr", "rv20"):
        t[col] = key.map(tags[col])
    t["weekday"] = t["time_in"].dt.day_name().str.slice(0, 3)
    return t


def htf_gate(instr: str, tf_entry: int, tf_htf: int, fast: int = 18, trend: int = 200, mode: str = "ma"):
    pth = E.load_path(default_path(instr, tf_entry)[0]); lo = E.build_tf(pth, tf_entry); hi = E.build_tf(pth, tf_htf)
    ma_f = E.sma(hi["c"], fast); ma_t = E.sma(hi["c"], trend)
    dec = np.append(lo["t"][1:], lo["t"][-1] + 1); idx = np.searchsorted(hi["t"], dec, side="right") - 2; ok = idx >= 0; ii = np.clip(idx, 0, hi["n"] - 1)
    up = (ma_f[ii] > ma_t[ii]) & ok; dn = (ma_f[ii] < ma_t[ii]) & ok
    if mode == "close":
        up &= hi["c"][ii] > ma_f[ii]; dn &= hi["c"][ii] < ma_f[ii]
    return np.nan_to_num(up.astype(float)).astype(np.int64), np.nan_to_num(dn.astype(float)).astype(np.int64)


def day_gate(instr: str, tf_entry: int, allowed_dates: pd.DatetimeIndex):
    pth = E.load_path(default_path(instr, tf_entry)[0]); lo = E.build_tf(pth, tf_entry); days = pd.to_datetime(lo["t"], unit="s").normalize()
    ok = np.asarray(days.isin(allowed_dates), dtype=np.int64); return ok, ok.copy()


# ----------------------------------------------------------------------------------------------------------------
# Experiment log and tables
# ----------------------------------------------------------------------------------------------------------------

LOG_COLS = ["experiment_id", "date", "instrument", "timeframe", "config", "parameters", "filters", "data_period", "scenario", "trades", "win_rate", "pf", "expectancy_usd", "expectancy_r",
            "net_usd", "net_r", "max_dd_usd", "sharpe_m", "train_net_usd", "val_net_usd", "oos_net_usd", "oos_pf", "verdict", "decision", "reason"]


def log_experiment(exp_id, instr, tf, config, params, filters, period, scenario, m, sm, decision, reason):
    new = not os.path.exists(LOG)
    row = {"experiment_id": exp_id, "date": date.today().isoformat(), "instrument": instr, "timeframe": TF_NAME.get(tf, str(tf)), "config": config, "parameters": json.dumps(params, sort_keys=True, default=str),
           "filters": filters, "data_period": f"{period[0]}..{period[1]}", "scenario": scenario, "trades": m.get("trades"), "win_rate": m.get("win_rate"), "pf": m.get("pf"), "expectancy_usd": m.get("exp_usd"),
           "expectancy_r": m.get("exp_r"), "net_usd": m.get("net_usd"), "net_r": m.get("net_r"), "max_dd_usd": m.get("max_dd_usd"), "sharpe_m": m.get("sharpe_m"),
           "train_net_usd": sm["TRAIN"].get("net_usd") if sm else None, "val_net_usd": sm["VAL"].get("net_usd") if sm else None, "oos_net_usd": sm["OOS"].get("net_usd") if sm else None,
           "oos_pf": sm["OOS"].get("pf") if sm else None, "verdict": classify(sm) if sm else "", "decision": decision, "reason": reason}
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new: w.writeheader()
        w.writerow(row)


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    cols = list(df.columns); out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(("" if math.isnan(v) else (floatfmt.format(v) if abs(v) < 1e6 else f"{v:.3g}")) if isinstance(v, float) else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)
