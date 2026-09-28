"""Lab 2: entry / level-quality variants that a discretionary liquidity trader would ask about.

  A. retest entry  : after the sweep bar closes, limit order AT the swept level, valid N bars, same stop/target
  B. swing length  : 20/20 and 30/30 pivots (fewer, bigger pools) on 5m, 15m, 1h
  C. continuation  : trade BREAK events in the break direction (acceptance beyond the pool)
  D. HTF confluence: 5m / 15m sweeps of a level that is ALSO a pending 1h or 4h pool at that moment
Same discipline: CONTROL year first, TEST year second, >= 30 trades in each, net of XM costs.
"""
import os
import numpy as np
import pandas as pd
import liq_engine as E
from run_multitf import TEST, CTRL, slice_period, max_bars_for
from quality_lab import attach_htf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def simulate_generic(ev, m1, tf_min, rr=2.0, stop_pad_atr=0.10, max_bars=24, slippage=0.10, mode="sweep",
                     retest_bars=6, break_stop_atr=0.25):
    """mode='sweep': market entry at the close of the reclaim bar (as liq_engine.simulate).
       mode='retest': limit entry at the swept level within retest_bars TF bars; stop/target as sweep mode.
       mode='break' : continuation entry at the close of the break bar; stop = level -/+ break_stop_atr*ATR."""
    if ev.empty: return pd.DataFrame()
    sel = ev[~ev.swept] if mode == "break" else ev[ev.swept]
    t1 = m1.time.values; h1 = m1.high.values; l1 = m1.low.values; c1 = m1.close.values
    rows = []
    for r in sel.itertuples():
        atr = r.atr if r.atr == r.atr else np.nan
        if atr != atr: continue
        if mode == "break":
            side = r.side
            entry = r.close
            stop = r.level - side * break_stop_atr * atr
        else:
            side = -r.side
            entry = r.level if mode == "retest" else r.close
            stop = r.extreme - side * stop_pad_atr * atr
        risk = (entry - stop) * side
        if risk <= 0: continue
        target = entry + side * rr * risk
        t_start = np.datetime64(r.time) + np.timedelta64(tf_min, "m")
        i0 = np.searchsorted(t1, t_start)
        if i0 >= len(t1): continue
        if mode == "retest":
            iw = np.searchsorted(t1, t_start + np.timedelta64(tf_min * retest_bars, "m"))
            seg_l = l1[i0:iw]; seg_h = h1[i0:iw]
            touch = np.nonzero(seg_l <= entry)[0] if side == 1 else np.nonzero(seg_h >= entry)[0]
            # if the target would be reached before the retest, the trade is simply missed
            if len(touch) == 0: continue
            i0 = i0 + touch[0]
            # same-bar stop-through on the fill bar: conservative loss
            if (side == 1 and l1[i0] <= stop) or (side == -1 and h1[i0] >= stop):
                k = i0; ex = stop; how = "stop"
                rows.append(_row(r, side, entry, stop, target, risk, ex, how, k, i0, h1, l1, slippage, atr)); continue
        i1 = np.searchsorted(t1, t1[i0] + np.timedelta64(tf_min * max_bars, "m"))
        hh = h1[i0:i1]; ll = l1[i0:i1]
        if side == 1:
            hit_t = np.nonzero(hh >= target)[0]; hit_s = np.nonzero(ll <= stop)[0]
        else:
            hit_t = np.nonzero(ll <= target)[0]; hit_s = np.nonzero(hh >= stop)[0]
        kt = hit_t[0] if len(hit_t) else 10**9
        ks = hit_s[0] if len(hit_s) else 10**9
        if kt == ks == 10**9:
            k = max(i1 - 1, i0); ex = c1[min(k, len(c1) - 1)]; how = "time"
        elif ks <= kt:
            k = i0 + ks; ex = stop; how = "stop"
        else:
            k = i0 + kt; ex = target; how = "target"
        rows.append(_row(r, side, entry, stop, target, risk, ex, how, k, i0, h1, l1, slippage, atr))
    return pd.DataFrame(rows)


def _row(r, side, entry, stop, target, risk, ex, how, k, i0, h1, l1, slippage, atr):
    gross = (ex - entry) * side
    seg_h = h1[i0:k + 1]; seg_l = l1[i0:k + 1]
    mfe = (seg_h.max() - entry) if side == 1 else (entry - seg_l.min())
    mae = (entry - seg_l.min()) if side == 1 else (seg_h.max() - entry)
    ts = pd.Timestamp(r.time)
    cost = E.spread_usd(ts.year, ts.hour) + slippage
    net = gross - cost
    return dict(time=r.time, side=side, kind=r.kind, touches=r.touches, level=r.level, entry=entry, stop=stop, target=target, risk=risk,
                risk_atr=risk / atr, exit=ex, how=how, gross=gross, cost=cost, net=net, R=net / risk, gross_R=gross / risk,
                mfe_R=mfe / risk, mae_R=mae / risk, hold_min=k - i0 + 1, depth_atr=r.depth_atr, bars_held=r.bars_held,
                session=r.session, ny_h=r.ny_h, age_bars=r.age_bars)


def ev_row(rows, label, tf, rr, T):
    mc = E.metrics(slice_period(T, *CTRL)); mt = E.metrics(slice_period(T, *TEST))
    rows.append(dict(lab=label, tf=tf, rr=rr, n_ctrl=mc.get("n", 0), exp_ctrl=mc.get("expR", np.nan), pf_ctrl=mc.get("pf", np.nan),
                     n_test=mt.get("n", 0), exp_test=mt.get("expR", np.nan), pf_test=mt.get("pf", np.nan), ci_lo_test=mt.get("ci_lo", np.nan),
                     win_test=mt.get("win", np.nan), gross_test=mt.get("gross_expR", np.nan), gross_ctrl=mc.get("gross_expR", np.nan)))


def with_filters(T, m1):
    """Attach HTF trend + session flags for sub-selection."""
    if T.empty: return T
    T = attach_htf(T, m1)
    T["lon_ny"] = T.session.isin(["london", "overlap", "newyork"])
    T["is_key"] = T.kind.isin(list(E.KEY_KINDS))
    return T


def pending_intervals(m1, tf, P):
    """(create_time, resolve_time, price, side) for every resolved pool on a HTF."""
    d = E.resample(m1, E.TF_MIN[tf])
    ev = E.detect_events(d, P)
    times = d.time.values
    create_bar = np.where(ev.kind.isin(list(E.KEY_KINDS)), ev.level_start, ev.level_start + P["swR"]).astype(int)
    return pd.DataFrame({"t0": times[create_bar], "t1": times[ev.bar.values], "price": ev.level.values, "side": ev.side.values})


def confluent(T, iv, tol_atr=0.25):
    """Flag LTF trades whose swept level matches a HTF pool pending at that time (same side)."""
    flags = np.zeros(len(T), bool)
    t0 = iv.t0.values; t1 = iv.t1.values; pr = iv.price.values; sd = iv.side.values
    for i, r in enumerate(T.itertuples()):
        t = np.datetime64(r.time)
        tol = tol_atr * (r.risk / r.risk_atr) if r.risk_atr else 0.5
        m = (t0 <= t) & (t1 >= t) & (sd == -r.side) & (np.abs(pr - r.level) <= tol)
        flags[i] = m.any()
    return flags


def main():
    m1 = E.load_m1("2024-09-01", "2026-09-26")
    rows = []
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 300)

    # ---- A. retest entry + C. breaks, on 5m / 15m / 1h / 4h with default params
    cache = {}
    for tf in ["5m", "15m", "1h", "4h"]:
        m = E.TF_MIN[tf]; d = E.resample(m1, m); P = dict(E.DEFAULT); P["asiaOn"] = P["lonOn"] = m <= 30; P["pdOn"] = m <= 240
        ev = E.detect_events(d, P); cache[tf] = ev
        for rr in (1.0, 1.5, 2.0, 3.0):
            for mode in ("retest", "break"):
                T = with_filters(simulate_generic(ev, m1, m, rr=rr, max_bars=max_bars_for(tf), mode=mode), m1)
                if T.empty: continue
                ev_row(rows, f"{mode}:all", tf, rr, T)
                ev_row(rows, f"{mode}:with_h4", tf, rr, T[T.with_h4])
                ev_row(rows, f"{mode}:lon_ny+with_h4", tf, rr, T[T.with_h4 & T.lon_ny])
                ev_row(rows, f"{mode}:key", tf, rr, T[T.is_key])
        print(tf, "A/C done", flush=True)

    # ---- B. swing length grid
    for tf in ["5m", "15m", "1h"]:
        m = E.TF_MIN[tf]; d = E.resample(m1, m)
        for L in (20, 30):
            P = dict(E.DEFAULT); P.update(swL=L, swR=L); P["asiaOn"] = P["lonOn"] = m <= 30; P["pdOn"] = m <= 240
            ev = E.detect_events(d, P)
            for rr in (1.0, 1.5, 2.0, 3.0):
                T = with_filters(E.simulate(ev, m1, m, rr=rr, max_bars=max_bars_for(tf)), m1)
                if T.empty: continue
                ev_row(rows, f"swing{L}:all", tf, rr, T)
                ev_row(rows, f"swing{L}:with_h4", tf, rr, T[T.with_h4])
                ev_row(rows, f"swing{L}:lon_ny+with_h4", tf, rr, T[T.with_h4 & T.lon_ny])
        print(tf, "B done", flush=True)

    # ---- D. HTF confluence for 5m / 15m sweeps
    P1 = dict(E.DEFAULT); P1["asiaOn"] = P1["lonOn"] = False
    iv_1h = pending_intervals(m1, "1h", P1)
    iv_4h = pending_intervals(m1, "4h", P1)
    for tf in ["5m", "15m"]:
        m = E.TF_MIN[tf]; ev = cache[tf]
        for rr in (1.0, 1.5, 2.0, 3.0):
            T = with_filters(E.simulate(ev, m1, m, rr=rr, max_bars=max_bars_for(tf)), m1)
            T["conf_1h"] = confluent(T, iv_1h); T["conf_4h"] = confluent(T, iv_4h)
            ev_row(rows, "conf1h", tf, rr, T[T.conf_1h])
            ev_row(rows, "conf4h", tf, rr, T[T.conf_4h])
            ev_row(rows, "conf1h+with_h4", tf, rr, T[T.conf_1h & T.with_h4])
            ev_row(rows, "conf1h+lon_ny+with_h4", tf, rr, T[T.conf_1h & T.with_h4 & T.lon_ny])
            ev_row(rows, "conf4h+lon_ny+with_h4", tf, rr, T[T.conf_4h & T.with_h4 & T.lon_ny])
            if rr == 2.0: print(tf, "confluent share 1h/4h:", round(T.conf_1h.mean(), 3), round(T.conf_4h.mean(), 3), flush=True)
    F = pd.DataFrame(rows)
    F.to_csv(os.path.join(OUT, "lab2_results.csv"), index=False)
    F["retained"] = (F.exp_ctrl > 0) & (F.exp_test > 0) & (F.n_ctrl >= 30) & (F.n_test >= 30)
    cols = ["lab", "tf", "rr", "n_ctrl", "exp_ctrl", "pf_ctrl", "n_test", "exp_test", "pf_test", "ci_lo_test", "win_test", "gross_ctrl", "gross_test"]
    print("\n==== LAB2 retained (positive in CONTROL and TEST, >= 30 each) ====")
    R = F[F.retained].sort_values("exp_test", ascending=False)
    print(R[cols].round(3).to_string(index=False) if len(R) else "NONE")
    print("\n==== LAB2 all-trade rows (no sub-filter) ====")
    print(F[F.lab.str.endswith(":all") | F.lab.isin(["conf1h", "conf4h"])][cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
