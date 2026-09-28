"""Separate test: Volume Profile + order-flow ("order book") combination on XAUUSD.

Honest scope note
  XM's MT5 stores NO historical depth-of-market for GOLD, and CFD brokers' DOM is synthetic anyway.
  A 5-year backtest of a real order-book rule is therefore impossible for this instrument. What this
  test uses instead:
    * Volume profile: REAL, built every day from M1 volume spread across each bar's range
      (bin = 0.01% of price). Previous-day POC / value-area high (VAH) / value-area low (VAL), 70% VA.
    * Order-flow proxy: aggressor delta = (up-bar volume - down-bar volume) / total over the last
      20 M1 bars, in [-1, +1]. This is the closest thing to "book pressure" that exists in the history.
  Both a rotation (fade the value-area edge) and an acceptance (breakout through the edge) playbook are
  tested, each with and without the order-flow gate, so the gate's contribution is measurable.

Rules (mechanical)
  rotation  LONG : bar low <= VAL, bar close > VAL, close < POC, today's open inside yesterday's VA,
                   [delta >= +thr]. SL = min(bar low, VAL) - 0.5 x ATR15. TP = POC. Skip if TP/SL < 0.8.
            SHORT: mirror at VAH.
  acceptance LONG: close crosses above VAH (prev close <= VAH), [delta >= +thr].
                   SL = VAH - 0.5 x ATR15. TP = VAH + (VAH - VAL). SHORT: mirror.
  Exits: SL / TP (SL first inside a bar), or the session close (last M1 bar of the day). One trade at a
  time. Entry at the next M1 open (+spread for buys). Same XM spread model as the TWK tests.
"""
import json, os, sys, time
import numpy as np
import pandas as pd
import twk_engine as E

POINT = 0.01


def daily_profiles(m1: pd.DataFrame, bin_pct=0.0001, va=0.70) -> pd.DataFrame:
    day = m1["time"].dt.floor("D")
    rows = []
    lo_a = m1["low"].to_numpy(float); hi_a = m1["high"].to_numpy(float)
    v_a = m1["tick_volume"].to_numpy(float); c_a = m1["close"].to_numpy(float); o_a = m1["open"].to_numpy(float)
    for d, idx in m1.groupby(day).indices.items():
        lo = lo_a[idx].min(); hi = hi_a[idx].max()
        if hi <= lo or len(idx) < 300:
            continue
        binw = max(0.01, round(float(np.median(c_a[idx])) * bin_pct, 2))
        nb = int((hi - lo) / binw) + 1
        hist = np.zeros(nb)
        L = ((lo_a[idx] - lo) / binw).astype(int); H = ((hi_a[idx] - lo) / binw).astype(int)
        for a, b, v in zip(L, H, v_a[idx]):
            hist[a:b + 1] += v / (b - a + 1)
        poc_i = int(hist.argmax())
        total = hist.sum(); acc = hist[poc_i]; a = b = poc_i
        while acc < va * total:
            left = hist[a - 1] if a > 0 else -1.0
            right = hist[b + 1] if b < nb - 1 else -1.0
            if left < 0 and right < 0:
                break
            if right >= left:
                b += 1; acc += hist[b]
            else:
                a -= 1; acc += hist[a]
        rows.append(dict(date=d, poc=lo + (poc_i + 0.5) * binw, vah=lo + (b + 1) * binw, val=lo + a * binw,
                         day_high=hi, day_low=lo, day_open=o_a[idx[0]], day_close=c_a[idx[-1]], volume=total,
                         va_width=(b - a + 1) * binw))
    return pd.DataFrame(rows).set_index("date")


def build_signals(m1: pd.DataFrame, tf: int, prof: pd.DataFrame, mode: str, use_of: bool, of_thr: float,
                  m1_delta: np.ndarray, m1_t: np.ndarray, atr15_t: np.ndarray, atr15_v: np.ndarray) -> pd.DataFrame:
    bars = E.resample(m1, tf)
    t_open = (bars["time"].astype("int64") // 10**9).to_numpy()
    close_t = t_open + tf * 60
    date = bars["time"].dt.floor("D")
    prev = prof.shift(1)                      # yesterday's levels on today's rows
    lv = prev.reindex(date)
    today = prof.reindex(date)
    poc = lv["poc"].to_numpy(); vah = lv["vah"].to_numpy(); val = lv["val"].to_numpy()
    d_open = today["day_open"].to_numpy()
    o = bars["open"].to_numpy(float); h = bars["high"].to_numpy(float); l = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = np.nan
    # order-flow delta of the last completed M1 bar at the signal close
    k1 = np.searchsorted(m1_t + 60, close_t, side="right") - 1
    delta = np.where(k1 >= 0, m1_delta[np.maximum(k1, 0)], np.nan)
    ka = np.searchsorted(atr15_t + 900, close_t, side="right") - 1
    atr = np.where(ka >= 0, atr15_v[np.maximum(ka, 0)], np.nan)
    ok = ~np.isnan(poc) & ~np.isnan(atr) & ~np.isnan(delta)
    open_in_va = (d_open >= val) & (d_open <= vah)
    rows = []
    if mode == "rotation":
        lg = ok & open_in_va & (l <= val) & (c > val) & (c < poc)
        sh = ok & open_in_va & (h >= vah) & (c < vah) & (c > poc)
        if use_of:
            lg &= delta >= of_thr; sh &= delta <= -of_thr
        for i in np.where(lg)[0]:
            sl = min(l[i], val[i]) - 0.5 * atr[i]; tp = poc[i]
            rows.append(dict(bar=i, close_time=close_t[i], time=bars["time"].iloc[i], side=1, entry=c[i], sl=sl, tp=tp, delta=delta[i]))
        for i in np.where(sh)[0]:
            sl = max(h[i], vah[i]) + 0.5 * atr[i]; tp = poc[i]
            rows.append(dict(bar=i, close_time=close_t[i], time=bars["time"].iloc[i], side=-1, entry=c[i], sl=sl, tp=tp, delta=delta[i]))
    else:
        lg = ok & (c > vah) & (pc <= vah)
        sh = ok & (c < val) & (pc >= val)
        if use_of:
            lg &= delta >= of_thr; sh &= delta <= -of_thr
        for i in np.where(lg)[0]:
            sl = vah[i] - 0.5 * atr[i]; tp = vah[i] + (vah[i] - val[i])
            rows.append(dict(bar=i, close_time=close_t[i], time=bars["time"].iloc[i], side=1, entry=c[i], sl=sl, tp=tp, delta=delta[i]))
        for i in np.where(sh)[0]:
            sl = val[i] + 0.5 * atr[i]; tp = val[i] - (vah[i] - val[i])
            rows.append(dict(bar=i, close_time=close_t[i], time=bars["time"].iloc[i], side=-1, entry=c[i], sl=sl, tp=tp, delta=delta[i]))
    sig = pd.DataFrame(rows)
    if len(sig):
        sig = sig.sort_values("close_time").reset_index(drop=True)
        risk = np.abs(sig["entry"] - sig["sl"]); rew = np.abs(sig["tp"] - sig["entry"])
        sig = sig[(risk > 0) & (rew / risk >= 0.8)].reset_index(drop=True)
    return sig


def simulate_fixed(m1: pd.DataFrame, sig: pd.DataFrame, spread_pts: np.ndarray, t_start: int, t_end: int, lots=0.02) -> pd.DataFrame:
    t = (m1["time"].astype("int64") // 10**9).to_numpy()
    o = m1["open"].to_numpy(float).tolist(); h = m1["high"].to_numpy(float).tolist()
    l = m1["low"].to_numpy(float).tolist(); c = m1["close"].to_numpy(float).tolist()
    spr = (spread_pts * POINT).tolist()
    day = (t // 86400)
    n = len(t)
    mult = lots * 100.0
    sig = sig[(sig["close_time"] >= t_start) & (sig["close_time"] < t_end)].reset_index(drop=True)
    act = np.searchsorted(t, sig["close_time"].to_numpy(), side="left")
    rows = sig.to_dict("records")
    trades = []
    pos = None
    j = 0
    k = int(np.searchsorted(t, t_start)); k_end = int(np.searchsorted(t, t_end))

    def close_pos(k, price, reason):
        nonlocal pos
        s = pos["side"]
        pnl_px = (price - pos["entry"]) if s == 1 else (pos["entry"] - price)
        trades.append(dict(entry_time=pd.Timestamp(pos["t_in"], unit="s"), exit_time=pd.Timestamp(t[k], unit="s"),
                           side="BUY" if s == 1 else "SELL", entry=pos["entry"], exit=price, initial_sl=pos["sl"], tp=pos["tp"],
                           risk=abs(pos["entry"] - pos["sl"]), pnl_px=pnl_px, pnl=pnl_px * mult, swap=0.0,
                           r_multiple=pnl_px / abs(pos["entry"] - pos["sl"]), exit_reason=reason, delta=pos["delta"],
                           bars=k - pos["k_in"]))
        pos = None

    warm_until = -1
    while k < k_end:
        if k > 0 and t[k] - t[k - 1] > 3 * 86400:
            warm_until = k + 300
        if k < warm_until:
            while j < len(act) and act[j] <= k:
                j += 1
        if pos is not None and day[k] != pos["day"]:
            # session close: exit at the previous bar's close
            kk = k - 1
            close_pos(kk, c[kk] if pos["side"] == 1 else c[kk] + spr[kk], "session_end")
        # entries scheduled at this bar's open
        while j < len(act) and act[j] <= k:
            if act[j] == k and pos is None:
                r = rows[j]
                bid = o[k]; ask = bid + spr[k]
                if r["side"] == 1 and r["sl"] < bid and r["tp"] > ask:
                    pos = dict(side=1, entry=ask, sl=r["sl"], tp=r["tp"], t_in=t[k], k_in=k, day=day[k], delta=r["delta"])
                elif r["side"] == -1 and r["sl"] > ask and r["tp"] < bid:
                    pos = dict(side=-1, entry=bid, sl=r["sl"], tp=r["tp"], t_in=t[k], k_in=k, day=day[k], delta=r["delta"])
            j += 1
        if pos is not None:
            s = pos["side"]
            if s == 1:
                if l[k] <= pos["sl"]:
                    close_pos(k, min(pos["sl"], o[k]), "SL")
                elif h[k] >= pos["tp"]:
                    close_pos(k, max(pos["tp"], o[k]) if o[k] > pos["tp"] else pos["tp"], "TP")
            else:
                hi = h[k] + spr[k]; lo = l[k] + spr[k]
                if hi >= pos["sl"]:
                    close_pos(k, max(pos["sl"], o[k] + spr[k]), "SL")
                elif lo <= pos["tp"]:
                    close_pos(k, pos["tp"], "TP")
        k += 1
    if pos is not None:
        kk = k_end - 1
        close_pos(kk, c[kk] if pos["side"] == 1 else c[kk] + spr[kk], "end_of_test")
    return pd.DataFrame(trades)


def main():
    t0 = time.time()
    m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
    years = m1["time"].dt.year.to_numpy()
    spread = np.array([E.year_spread_model()[y] for y in years], float)
    prof = daily_profiles(m1)
    prof.to_csv("results/vp_daily_profiles.csv")
    print(f"profiles: {len(prof)} days ({time.time()-t0:.0f}s)", flush=True)
    bv, sv = E.up_down_volume(m1["open"].to_numpy(float), m1["close"].to_numpy(float), m1["tick_volume"].to_numpy(float), 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        m1_delta = np.where(np.isnan(bv) | np.isnan(sv), np.nan, (bv - sv) / np.maximum(bv + sv, 1e-9))
    m1_t = (m1["time"].astype("int64") // 10**9).to_numpy()
    m15 = E.resample(m1, 15)
    atr15 = E.rma(E.true_range(m15["high"].to_numpy(float), m15["low"].to_numpy(float), m15["close"].to_numpy(float), True), 14)
    atr15_t = (m15["time"].astype("int64") // 10**9).to_numpy()
    END = pd.Timestamp("2026-09-25 00:00")
    WINDOWS = {"6m": (END - pd.DateOffset(months=6), END), "5y": (END - pd.DateOffset(years=5), END)}
    out = []
    for mode in ("rotation", "acceptance"):
        for use_of in (False, True):
            for tf in (1, 5, 15):
                sig = build_signals(m1, tf, prof, mode, use_of, 0.2, m1_delta, m1_t, atr15_t, atr15)
                for win, (a, b) in WINDOWS.items():
                    tr = simulate_fixed(m1, sig, spread, int(a.timestamp()), int(b.timestamp()))
                    label = f"VP_{mode}_{'OF' if use_of else 'noOF'}"
                    fn = f"results/trades_{label}_M{tf}_{win}.csv"
                    tr.to_csv(fn, index=False)
                    m = E.metrics(tr) if len(tr) else dict(trades=0)
                    row = dict(bot=label, tf=tf, window=win, signals=int(((sig.close_time >= a.timestamp()) & (sig.close_time < b.timestamp())).sum()), file=fn, **m)
                    if len(tr):
                        tr["year"] = tr["entry_time"].dt.year
                        row["by_year"] = {int(y): dict(trades=int(len(g)), net=round(float(g.pnl.sum()), 2),
                                                        pf=round(float(g.pnl[g.pnl > 0].sum() / max(1e-9, -g.pnl[g.pnl < 0].sum())), 2),
                                                        win=round(float((g.pnl > 0).mean()), 3), avg_r=round(float(g.r_multiple.mean()), 3),
                                                        med_risk=round(float(g.risk.median()), 2)) for y, g in tr.groupby("year")}
                        step = max(1, len(tr) // 400)
                        row["equity"] = [round(float(x), 2) for x in tr.pnl.cumsum().to_numpy()[::step]]
                        row["equity_time"] = [str(x)[:10] for x in tr.exit_time.to_numpy()[::step]]
                    out.append(row)
                    print(f"{label:24s} M{tf:<2d} {win}: sig={row['signals']:5d} trades={m.get('trades',0):5d} net=${m.get('net',0):9.2f} "
                          f"PF={m.get('profit_factor',0):.2f} win={m.get('win_rate',0)*100:4.0f}% avgR={m.get('avg_r',float('nan')):.2f} "
                          f"maxDD=${m.get('max_dd',0):.0f} medRisk=${m.get('median_risk_px',0):.2f}", flush=True)
    json.dump(dict(runs=out, generated=str(pd.Timestamp.now())[:16]), open("results/vp_summary.json", "w"), indent=1, default=float)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
