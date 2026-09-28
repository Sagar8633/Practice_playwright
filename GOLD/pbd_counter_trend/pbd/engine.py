"""Trade simulation on the Dukascopy M1 bid path.

Execution models
----------------
ideal : fill at the signal bar's close, zero spread / slippage / commission / swap.
real  : fill at the open of the M1 bar that starts `delay_m1` minutes after the signal
        M15 bar closed, at the XM spread of the signal bar (long pays the ask), plus
        `slip` USD/oz slippage on every market fill (entries, stops, time exits; targets
        are limit orders and fill at price), commission per oz round trip, XM GOLD swap
        per night held (long -0.8684, short +0.1979 USD/oz, Wednesday x3).
Path rules
----------
* Stops and targets are checked on every M1 bar from the fill bar onward.  If both are
  touched inside the same M1 bar the STOP is assumed to have filled first.
* A bar that opens beyond the stop fills at its open (gap-through).
* Time stop after `max_hold_bars` M15 bars (72 h) at the next M1 open.
* A data gap longer than 60 h (missing month) closes the trade at the last bar before
  the gap, reason "data_gap".
* Shorts: ask = bid + spread, so a short's stop is hit on high + spread and its target
  on low + spread.
"""
import numpy as np
import pandas as pd

COSTS = {
    "ideal": dict(spread_mode="zero", slip=0.0, comm_oz=0.0, swap=False, delay_m1=0, fill="signal_close"),
    "real": dict(spread_mode="xm", slip=0.10, comm_oz=0.0, swap=True, delay_m1=1, fill="next_open"),
}
SWAP_LONG, SWAP_SHORT = -0.8684, 0.1979   # USD per oz per night, XM GOLD (Sep 2026)


class Path:
    def __init__(self, m1: pd.DataFrame):
        self.t = m1["time"].values.astype("datetime64[ns]")
        self.ti = self.t.astype("int64") // 10**9
        self.o = m1["open"].values.astype(float)
        self.h = m1["high"].values.astype(float)
        self.l = m1["low"].values.astype(float)
        self.c = m1["close"].values.astype(float)
        d = np.diff(self.ti, prepend=self.ti[0])
        self.gap60 = d > 60 * 3600
        self.n = len(self.t)

    def first_gap(self, a, b):
        g = self.gap60[a + 1:b]
        if g.any():
            return a + 1 + int(np.argmax(g))
        return -1

    def index_at_or_after(self, ts_sec):
        return int(np.searchsorted(self.ti, ts_sec, side="left"))


def _nights(t_in, t_out):
    """Number of swap nights crossed between two UTC datetimes (rollover 21:30 UTC),
    Wednesday counted three times, weekend rollovers not charged separately."""
    t_in = pd.Timestamp(t_in); t_out = pd.Timestamp(t_out)
    roll = t_in.normalize() + pd.Timedelta(hours=21, minutes=30)
    if roll <= t_in:
        roll += pd.Timedelta(days=1)
    n = 0
    while roll < t_out:
        if roll.dayofweek < 5:
            n += 3 if roll.dayofweek == 2 else 1
        roll += pd.Timedelta(days=1)
    return n


def simulate(signals: pd.DataFrame, path: Path, m15: pd.DataFrame, cost: dict, P: dict,
             one_position: bool = True, playbook=None) -> pd.DataFrame:
    sg = signals if playbook is None else signals[signals["entry_type"].isin(playbook)]
    sg = sg.sort_values(["time", "i"]).reset_index(drop=True)
    m1_next = m15["m1_next"].values
    m15_ti = m15["time"].values.astype("datetime64[ns]").astype("int64") // 10**9
    hold_sec = int(P["max_hold_bars"]) * 15 * 60
    out = []
    busy_until = -1
    for s in sg.itertuples(index=False):
        d = s._asdict()
        i = int(d["i"])
        sig_sec = int(m15_ti[i])
        if one_position and sig_sec < busy_until:
            d.update(taken=False, skip_reason="in_trade"); out.append(d); continue
        sgn = 1.0 if d["side"] == "long" else -1.0
        spread = float(d["spread_usd"]) if cost["spread_mode"] == "xm" else 0.0
        slip = cost["slip"]
        if cost["fill"] == "signal_close":
            j0 = int(m1_next[i])                 # path starts at the first bar AFTER the signal bar
            if j0 >= path.n:
                d.update(taken=False, skip_reason="data_end"); out.append(d); continue
            entry = float(d["ref_price"]) + (spread if sgn > 0 else 0.0)
            fill_sec = sig_sec + 15 * 60
        else:
            j0 = int(m1_next[i]) + int(cost["delay_m1"])
            if j0 >= path.n:
                d.update(taken=False, skip_reason="data_end"); out.append(d); continue
            if path.ti[j0] - (sig_sec + 15 * 60) > 3600:
                d.update(taken=False, skip_reason="no_fill_gap"); out.append(d); continue
            entry = path.o[j0] + (spread + slip if sgn > 0 else -slip)
            fill_sec = int(path.ti[j0])
        stop = float(d["stop"]); target = float(d["target"])
        risk = (entry - stop) * sgn
        if risk <= 0 or (target - entry) * sgn <= 0:
            d.update(taken=False, skip_reason="bad_geometry"); out.append(d); continue
        j_end = path.index_at_or_after(fill_sec + hold_sec)
        j_end = min(j_end, path.n - 1)
        if j_end <= j0:
            d.update(taken=False, skip_reason="data_end"); out.append(d); continue
        jg = path.first_gap(j0, j_end)
        j_lim = jg if jg > 0 else j_end          # exclusive limit for stop/target search
        hs = path.h[j0:j_lim] + (spread if sgn < 0 else 0.0)   # ask highs for shorts
        ls = path.l[j0:j_lim] + (spread if sgn < 0 else 0.0)
        os_ = path.o[j0:j_lim] + (spread if sgn < 0 else 0.0)
        if sgn > 0:
            stop_hit = path.l[j0:j_lim] <= stop
            tp_hit = path.h[j0:j_lim] >= target
        else:
            stop_hit = hs >= stop
            tp_hit = ls <= target
        js = int(np.argmax(stop_hit)) if stop_hit.any() else -1
        jt = int(np.argmax(tp_hit)) if tp_hit.any() else -1
        if js >= 0 and (jt < 0 or js <= jt):
            jx = j0 + js
            px = stop
            op = os_[js]
            if (sgn > 0 and op < stop) or (sgn < 0 and op > stop):
                px = op                                   # gap through the stop
            exit_px = px - sgn * slip
            reason = "stop"
        elif jt >= 0:
            jx = j0 + jt
            px = target
            op = os_[jt]
            if (sgn > 0 and op > target) or (sgn < 0 and op < target):
                px = op                                   # gap through the target
            exit_px = px
            reason = "target"
        elif jg > 0:
            jx = jg - 1
            exit_px = path.c[jx] + (spread if sgn < 0 else 0.0) - sgn * slip
            reason = "data_gap"
        else:
            jx = j_end
            exit_px = path.o[jx] + (spread if sgn < 0 else 0.0) - sgn * slip
            reason = "time" if jx < path.n - 1 else "data_end"
        # excursions on the bid path between fill and exit (inclusive)
        seg_h = path.h[j0:jx + 1]; seg_l = path.l[j0:jx + 1]
        if sgn > 0:
            mfe = float(seg_h.max() - entry); mae = float(entry - seg_l.min())
        else:
            mfe = float(entry - (seg_l.min() + spread)); mae = float((seg_h.max() + spread) - entry)
        r_gross = (exit_px - entry) * sgn / risk
        comm_r = cost["comm_oz"] / risk
        nights = _nights(pd.Timestamp(fill_sec, unit="s"), pd.Timestamp(int(path.ti[jx]), unit="s")) if cost["swap"] else 0
        swap_oz = nights * (SWAP_LONG if sgn > 0 else SWAP_SHORT)
        swap_r = swap_oz / risk
        r_net = r_gross - comm_r + swap_r
        # would a stop twice as far have won?  (for the "stop too tight" label)
        won2 = np.nan
        if reason == "stop":
            stop2 = entry - sgn * 2 * risk
            if sgn > 0:
                sh2 = path.l[j0:j_lim] <= stop2
            else:
                sh2 = hs >= stop2
            js2 = int(np.argmax(sh2)) if sh2.any() else 10**9
            won2 = bool(jt >= 0 and jt < js2)
        d.update(taken=True, skip_reason="", entry_time=pd.Timestamp(fill_sec, unit="s"),
                 exit_time=pd.Timestamp(int(path.ti[jx]), unit="s"), entry=entry, exit=exit_px,
                 risk_usd=risk, reward_usd=(target - entry) * sgn, rr_actual=(target - entry) * sgn / risk,
                 exit_reason=reason, r_gross=r_gross, r_net=r_net, comm_r=comm_r, swap_r=swap_r,
                 spread_r=spread / risk, nights=nights, mfe_r=mfe / risk, mae_r=mae / risk,
                 hold_h=(int(path.ti[jx]) - fill_sec) / 3600.0, bars_m1=jx - j0 + 1,
                 won_with_2x_stop=won2, win=r_net > 0,
                 exit_i=int(np.searchsorted(m15_ti, int(path.ti[jx]), side="right") - 1))
        out.append(d)
        busy_until = int(path.ti[jx])
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- metrics
def drawdown_r(r: np.ndarray):
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(np.r_[0.0, eq])[1:]
    dd = eq - peak
    return eq, dd


def max_streak(win: np.ndarray, value=False):
    best = cur = 0
    for w in win:
        if w == value:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(tr: pd.DataFrame, col: str = "r_net") -> dict:
    t = tr[tr["taken"] == True] if "taken" in tr.columns else tr
    n = len(t)
    if n == 0:
        return dict(n=0)
    r = t[col].values.astype(float)
    wins = r[r > 0]; losses = r[r <= 0]
    eq, dd = drawdown_r(r)
    eq_pct = np.cumprod(1 + 0.01 * r)
    peak = np.maximum.accumulate(np.r_[1.0, eq_pct])[1:]
    dd_pct = (eq_pct / peak - 1).min() * 100
    rng = np.random.default_rng(0)
    boots = np.array([rng.choice(r, n, replace=True).mean() for _ in range(1000)])
    return dict(
        n=n, win_rate=float((r > 0).mean()), avg_win=float(wins.mean()) if len(wins) else 0.0,
        avg_loss=float(losses.mean()) if len(losses) else 0.0,
        pf=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf,
        expectancy=float(r.mean()), total_r=float(r.sum()), median_r=float(np.median(r)),
        ci_lo=float(np.percentile(boots, 2.5)), ci_hi=float(np.percentile(boots, 97.5)),
        max_dd_r=float(dd.min()), max_dd_pct_1pct=float(dd_pct), end_equity_1pct=float(eq_pct[-1]),
        max_loss_streak=max_streak(r > 0, False), max_win_streak=max_streak(r > 0, True),
        avg_hold_h=float(t["hold_h"].mean()), median_hold_h=float(t["hold_h"].median()),
        avg_rr_planned=float(t["rr_actual"].mean()), mfe_r=float(t["mfe_r"].mean()), mae_r=float(t["mae_r"].mean()),
        spread_r=float(t["spread_r"].mean()) if "spread_r" in t else 0.0,
        exits=t["exit_reason"].value_counts().to_dict(),
    )


def by_group(tr: pd.DataFrame, key, col="r_net"):
    t = tr[tr["taken"] == True]
    rows = []
    for k, g in t.groupby(key):
        r = g[col].values
        rows.append(dict(group=k, n=len(g), win_rate=(r > 0).mean(), expectancy=r.mean(), total_r=r.sum(),
                         pf=(r[r > 0].sum() / -r[r <= 0].sum()) if (r <= 0).any() and r[r <= 0].sum() < 0 else np.inf))
    return pd.DataFrame(rows)
