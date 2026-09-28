"""Loss taxonomy, no-trade filters, session / monthly / structure breakdowns."""
import numpy as np
import pandas as pd

from .engine import summarize, drawdown_r, max_streak
from .data import SPLITS

# ------------------------------------------------------------------ loss taxonomy
# Every label is a measurable condition on the recorded trade row.  Primary category =
# first matching label in PRIORITY.  All matching labels are also kept (multi-label).
PRIORITY = [
    "news_driven", "false_breakout", "trend_continuation_against", "range_invalidated_before_entry",
    "stop_too_tight", "range_too_narrow", "range_too_wide", "entry_too_late", "middle_of_range_entry",
    "multiple_failed_tests", "impulse_exhausted", "impulse_not_strong_enough", "poor_vah_val_location",
    "high_volatility", "low_volatility", "failed_pullback", "breakout_without_continuation",
    "stop_too_wide", "bad_orderflow_proxy", "other",
]
LABEL_RULES = {
    "false_breakout": "breakout trade; an M15 close came back inside the range within 8 bars of entry",
    "range_too_narrow": "range width < 1.5 x ATR14 at entry, or spread > 20% of the stop distance",
    "range_too_wide": "range width > 5 x ATR14 at entry",
    "impulse_not_strong_enough": "impulse size below the 20th percentile of all traded impulses (in pre-impulse ATR)",
    "impulse_exhausted": "impulse took >= 24 bars (6 h) from origin to extreme, or efficiency ratio < 0.5",
    "poor_vah_val_location": "traded boundary more than 3 ATR from both the weekly VAH and VAL",
    "middle_of_range_entry": "fill between 35% and 65% of the range height",
    "entry_too_late": "ping-pong: fill > 35% of width from the boundary; breakout: close penetration > 1 ATR",
    "breakout_without_continuation": "breakout trade stopped with MFE between 0.25R and 1R",
    "failed_pullback": "pullback entry stopped with MFE < 0.25R (no continuation attempt)",
    "trend_continuation_against": "ping-pong trade against the impulse direction, stopped, and the exit bar closed beyond the range on the impulse side",
    "news_driven": "exit bar (or entry bar) inside the 08:30/10:00 ET or FOMC slot proxy, or a shock bar (range > 3 ATR) during the trade",
    "high_volatility": "ATR14 percentile over the trailing 60 days >= 0.90 at entry",
    "low_volatility": "ATR14 percentile over the trailing 60 days <= 0.10 at entry",
    "bad_orderflow_proxy": "PROXY ONLY: signal-bar Dukascopy volume < 0.7 x 20-bar average (no footprint data exists)",
    "multiple_failed_tests": "traded boundary already touched >= 3 times (ping-pong) or a breakout already failed on this range",
    "range_invalidated_before_entry": "stopped within one M15 bar of the fill and that bar closed outside the range",
    "stop_too_tight": "a stop twice as far would have reached the original target; stop < 1 ATR",
    "stop_too_wide": "stop distance > 2.5 ATR or > 75% of the range height",
    "other": "no rule matched",
}


def label_losses(tr: pd.DataFrame, m15: pd.DataFrame) -> pd.DataFrame:
    t = tr[tr["taken"] == True].copy()
    c = m15["close"].values; hi = m15["high"].values; lo = m15["low"].values
    news = m15["news"].values; shock = m15["shock"].fillna(False).values.astype(bool)
    q20 = t["imp_size_atr"].quantile(0.20)
    flags = {k: np.zeros(len(t), bool) for k in PRIORITY}
    rows = list(t.itertuples(index=False))
    for k, s in enumerate(rows):
        i = int(s.i); xi = int(s.exit_i) if s.exit_i == s.exit_i else i
        bo = s.entry_type != "pingpong"
        stopped = s.exit_reason == "stop"
        # news / shock
        win = slice(i, max(i, xi) + 1)
        flags["news_driven"][k] = bool(news[i] or news[min(xi, len(news) - 1)] or shock[win].any())
        # false breakout
        if bo:
            e = min(i + 9, len(c))
            seg = c[i + 1:e]
            inside = ((seg < s.rh) & (seg > s.rl)).any() if len(seg) else False
            flags["false_breakout"][k] = bool(inside and stopped)
            flags["failed_pullback"][k] = bool(s.entry_type == "breakout_pullback" and stopped and s.mfe_r < 0.25)
            flags["breakout_without_continuation"][k] = bool(stopped and 0.25 <= s.mfe_r < 1.0)
            flags["entry_too_late"][k] = bool(s.bo_close_pen_atr == s.bo_close_pen_atr and s.bo_close_pen_atr > 1.0)
            flags["multiple_failed_tests"][k] = bool(s.failed_bo >= 1)
        else:
            against = (s.stype == "P" and s.side == "short") or (s.stype == "B" and s.side == "long")
            xc = c[min(xi, len(c) - 1)]
            beyond = (xc > s.rh) if s.stype == "P" else (xc < s.rl)
            flags["trend_continuation_against"][k] = bool(against and stopped and beyond)
            dist_b = abs(s.entry - s.boundary) / s.width if s.width > 0 else 0
            flags["entry_too_late"][k] = bool(dist_b > 0.35)
            flags["multiple_failed_tests"][k] = bool(s.touches_side >= 3)
            if stopped and xi <= i + 1:
                flags["range_invalidated_before_entry"][k] = bool(c[min(xi, len(c) - 1)] > s.rh or c[min(xi, len(c) - 1)] < s.rl)
        flags["range_too_narrow"][k] = bool(s.width_atr < 1.5 or (s.spread_usd / s.risk_usd > 0.20 if s.risk_usd > 0 else False))
        flags["range_too_wide"][k] = bool(s.width_atr > 5.0)
        flags["impulse_not_strong_enough"][k] = bool(s.imp_size_atr < q20)
        flags["impulse_exhausted"][k] = bool(s.imp_bars >= 24 or s.imp_er < 0.5)
        dv = min(abs(s.dist_vah_atr), abs(s.dist_val_atr)) if s.dist_vah_atr == s.dist_vah_atr else np.nan
        flags["poor_vah_val_location"][k] = bool(dv == dv and dv > 3.0)
        flags["middle_of_range_entry"][k] = bool(0.35 < s.pos_in_range < 0.65)
        flags["high_volatility"][k] = bool(s.atr_pct == s.atr_pct and s.atr_pct >= 0.90)
        flags["low_volatility"][k] = bool(s.atr_pct == s.atr_pct and s.atr_pct <= 0.10)
        flags["bad_orderflow_proxy"][k] = bool(s.vol_rel == s.vol_rel and s.vol_rel < 0.7)
        flags["stop_too_tight"][k] = bool(stopped and s.won_with_2x_stop == True and s.risk_usd < 1.0 * s.atr14)
        flags["stop_too_wide"][k] = bool(s.risk_usd > 2.5 * s.atr14 or (s.width > 0 and s.risk_usd > 0.75 * s.width))
    for k in PRIORITY:
        t["f_" + k] = flags[k]
    prim = np.array(["other"] * len(t), dtype=object)
    assigned = np.zeros(len(t), bool)
    for k in PRIORITY[:-1]:
        m = flags[k] & ~assigned
        prim[m] = k
        assigned |= m
    t["loss_category"] = prim
    t["loss_flags"] = ["|".join(k for k in PRIORITY[:-1] if flags[k][j]) for j in range(len(t))]
    return t


def taxonomy_table(lab: pd.DataFrame, col="r_net", primary=True) -> pd.DataFrame:
    t = lab.sort_values("entry_time").reset_index(drop=True)
    r = t[col].values
    eq, dd = drawdown_r(r)
    # max drawdown window
    trough = int(np.argmin(dd)); peak = int(np.argmax(eq[:trough + 1])) if trough > 0 else 0
    in_dd = np.zeros(len(t), bool); in_dd[peak + 1:trough + 1] = True
    total_loss = r[r <= 0].sum()
    rows = []
    for k in PRIORITY:
        flagged = t["f_" + k].values if k != "other" else (t["loss_category"].values == "other")
        if primary:
            losses = (t["loss_category"].values == k) & (r <= 0)
        else:
            losses = flagged & (r <= 0)
        n_flagged = int(flagged.sum())            # trades (winners and losers) carrying the label
        nl = int(losses.sum())
        lr = r[losses]
        # longest run of consecutive trades (in time order) that are losses of this category
        best = cur = 0
        for j in range(len(r)):
            if losses[j]:
                cur += 1; best = max(best, cur)
            else:
                cur = 0
        rows.append(dict(category=k, trades_flagged=n_flagged, losses=nl,
                         loss_pct=(int((flagged & (r <= 0)).sum()) / n_flagged * 100) if n_flagged else 0.0,
                         avg_loss=float(lr.mean()) if nl else 0.0, max_loss=float(lr.min()) if nl else 0.0,
                         total_loss=float(lr.sum()), share_of_total_loss=(lr.sum() / total_loss * 100) if total_loss < 0 else 0.0,
                         max_consec=best,
                         dd_window_contribution=float(r[losses & in_dd].sum()),
                         rule=LABEL_RULES.get(k, "")))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ no-trade filters
def _q(tr, col, q):
    return tr[col].quantile(q)


FILTERS = {
    # name: (description, predicate returning True for trades that the filter REMOVES)
    "impulse_too_small": ("impulse < 5 pre-impulse ATR", lambda t: t["imp_size_atr"] < 5),
    "impulse_too_large": ("impulse > 15 pre-impulse ATR", lambda t: t["imp_size_atr"] > 15),
    "range_too_narrow": ("width < 1.5 ATR14", lambda t: t["width_atr"] < 1.5),
    "range_too_wide": ("width > 5 ATR14", lambda t: t["width_atr"] > 5),
    "poor_symmetry": ("|drift| over the confirmation window > 30% of width", lambda t: t["rng_drift"].abs() > 0.30),
    "middle_of_range": ("fill between 35% and 65% of the range", lambda t: (t["pos_in_range"] > 0.35) & (t["pos_in_range"] < 0.65)),
    "va_too_far": ("boundary > 3 ATR from both weekly VAH and VAL", lambda t: np.minimum(t["dist_vah_atr"].abs(), t["dist_val_atr"].abs()) > 3),
    "va_inside_range": ("weekly VAH and VAL both inside the range", lambda t: t["va_inside"] == True),
    "too_many_tests": ("traded side already touched >= 3 times / breakout already failed", lambda t: t["touches_side"] >= 3),
    "breakout_extended": ("breakout close > 1 ATR beyond the boundary", lambda t: t["bo_close_pen_atr"] > 1.0),
    "breakout_bar_too_large": ("breakout bar range > 2.5 ATR", lambda t: t["bo_bar_range_atr"] > 2.5),
    "abnormal_volatility": ("ATR percentile (60 d) > 0.90", lambda t: t["atr_pct"] > 0.90),
    "news_slot": ("signal inside the 08:30 / 10:00 ET / FOMC slot proxy", lambda t: t["news_slot"] != ""),
    "low_liquidity": ("off-hours session or signal-bar volume < 50% of the 20-bar average", lambda t: (t["session"] == "offhours") | (t["vol_rel"] < 0.5)),
    "weak_orderflow_proxy": ("PROXY: signal-bar volume < 0.8 x 20-bar average", lambda t: t["vol_rel"] < 0.8),
    "unfavourable_rr": ("planned reward / risk < 1.0", lambda t: t["rr_actual"] < 1.0),
    "target_too_close": ("planned reward < 1 ATR14", lambda t: t["reward_usd"] < t["atr14"]),
    "stop_too_large": ("stop distance > 1.5 ATR14", lambda t: t["risk_usd"] > 1.5 * t["atr14"]),
    "unclear_boundary": ("fewer than 2 touches of the traded boundary before the signal", lambda t: t["touches_side"] < 2),
    "cost_gate": ("spread > 15% of the stop distance", lambda t: t["spread_usd"] / t["risk_usd"] > 0.15),
}


def _row(name, desc, period, before, after, removed_r):
    return dict(filter=name, description=desc, period=period,
                n_before=before.get("n", 0), exp_before=before.get("expectancy", np.nan), pf_before=before.get("pf", np.nan),
                dd_before=before.get("max_dd_r", np.nan),
                n_after=after.get("n", 0), exp_after=after.get("expectancy", np.nan), pf_after=after.get("pf", np.nan),
                dd_after=after.get("max_dd_r", np.nan), removed=before.get("n", 0) - after.get("n", 0),
                removed_mean_r=removed_r)


def filter_table(tr: pd.DataFrame, filters=None, col="r_net") -> pd.DataFrame:
    filters = filters or FILTERS
    t = tr[tr["taken"] == True].copy()
    rows = []
    for name, (desc, pred) in filters.items():
        m = pred(t).fillna(False).astype(bool)
        for period in [p[0] for p in SPLITS] + ["ALL"]:
            sel = t if period == "ALL" else t[t["period"] == period]
            mm = m.loc[sel.index]
            before = summarize(sel, col); after = summarize(sel[~mm], col)
            removed_r = float(sel.loc[mm, col].mean()) if mm.any() else np.nan
            rows.append(_row(name, desc, period, before, after, removed_r))
    df = pd.DataFrame(rows)
    # verdicts: improvement = expectancy and PF both higher after the filter
    v = {}
    for name in filters:
        d = df[df["filter"] == name].set_index("period")
        better = {p: bool(d.loc[p, "exp_after"] > d.loc[p, "exp_before"] and d.loc[p, "pf_after"] > d.loc[p, "pf_before"]) for p in ["DEV", "VAL", "OOS"]}
        v[name] = "DEV+VAL+OOS" if all(better.values()) else ("DEV+VAL only" if better["DEV"] and better["VAL"] else ("DEV only" if better["DEV"] else "no"))
    df["survives"] = df["filter"].map(v)
    return df


# ------------------------------------------------------------------ breakdowns
def breakdown(tr: pd.DataFrame, key, col="r_net") -> pd.DataFrame:
    t = tr[tr["taken"] == True]
    rows = []
    for k, g in t.groupby(key, sort=True):
        s = summarize(g, col)
        rows.append(dict(group=k, n=s["n"], win_rate=s.get("win_rate"), expectancy=s.get("expectancy"), pf=s.get("pf"),
                         total_r=s.get("total_r"), max_dd_r=s.get("max_dd_r"), median_hold_h=s.get("median_hold_h")))
    return pd.DataFrame(rows)


def monthly(tr: pd.DataFrame, col="r_net") -> pd.DataFrame:
    t = tr[tr["taken"] == True].copy()
    t["month"] = pd.to_datetime(t["entry_time"]).dt.to_period("M").astype(str)
    g = t.groupby("month")[col].agg(["count", "sum", "mean"]).reset_index()
    g.columns = ["month", "n", "total_r", "expectancy"]
    g["win_rate"] = t.groupby("month")[col].apply(lambda r: (r > 0).mean()).values
    return g


def equity_curve(tr: pd.DataFrame, col="r_net") -> pd.DataFrame:
    t = tr[tr["taken"] == True].sort_values("entry_time").reset_index(drop=True)
    r = t[col].values
    eq, dd = drawdown_r(r)
    eq1 = np.cumprod(1 + 0.01 * r) * 10000
    peak = np.maximum.accumulate(eq1)
    return pd.DataFrame({"entry_time": t["entry_time"], "r": r, "equity_r": eq, "drawdown_r": dd,
                         "equity_usd_1pct_10k": eq1, "drawdown_pct_1pct": (eq1 / peak - 1) * 100})
