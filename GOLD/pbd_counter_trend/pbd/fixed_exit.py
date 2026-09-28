"""Fixed-distance exit model requested on 2026-09-26:

  entry  = the framework's confirmation signal (unchanged: same structures, same signals)
  stop   = entry -/+ sl_usd            (default 8 USD per oz, "strict")
  target = entry +/- tp_usd            (default 24 USD per oz, "strict")
  breakeven: once the trade is be_trigger_usd (default 8) in favour, the stop moves to the
             entry price (+/- be_offset_usd, default 0 = "cost to cost") and the trade waits
             for the target; no further trailing.
  lots   = fixed 0.02 lot = 2 oz -> USD P&L = 2 * per-oz P&L.

Path rules (M1 bid bars, same conventions as engine.simulate):
  * long favourable excursion = high - entry; short = entry - (low + spread) because a short
    exits at the ask.
  * Inside one M1 bar the order of touches is unknown.  Conservative rules:
      - original stop and target in the same bar          -> stop first
      - breakeven trigger and original stop in the same bar -> stop first (the bar spans the
        whole risk range; the +trigger is assumed to come after the stop)
      - trigger bar also reaches the target                -> target (it cannot reach +24
        without passing +8, and the stop was not touched)
      - trigger bar's close is back at/behind breakeven    -> breakeven hit in that bar
        (heuristic; counted in `be_same_bar`)
      - after the trigger bar: breakeven stop and target in the same bar -> breakeven first
  * A bar that opens beyond the active stop fills at its open (gap-through).
  * Optional time stop (time_stop_h=None means strict: hold until stop, breakeven or target).
  * A data gap > 60 h closes the trade at the last bar before it ("data_gap").
"""
import numpy as np
import pandas as pd

from .engine import Path, _nights, SWAP_LONG, SWAP_SHORT

FIXED = dict(sl_usd=8.0, tp_usd=24.0, be_trigger_usd=8.0, be_offset_usd=0.0, lots=0.02, time_stop_h=None)
OZ_PER_LOT = 100.0


def simulate_fixed(signals: pd.DataFrame, path: Path, m15: pd.DataFrame, cost: dict, X: dict = None,
                   one_position: bool = True, playbook=None) -> pd.DataFrame:
    X = {**FIXED, **(X or {})}
    sl, tp, be_trig, be_off = float(X["sl_usd"]), float(X["tp_usd"]), X["be_trigger_usd"], float(X["be_offset_usd"])
    oz = float(X["lots"]) * OZ_PER_LOT
    sg = signals if playbook is None else signals[signals["entry_type"].isin(playbook)]
    sg = sg.sort_values(["time", "i"]).reset_index(drop=True)
    m1_next = m15["m1_next"].values
    m15_ti = m15["time"].values.astype("datetime64[ns]").astype("int64") // 10**9
    hold_sec = None if X["time_stop_h"] is None else int(float(X["time_stop_h"]) * 3600)
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
            j0 = int(m1_next[i])
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
        stop0 = entry - sgn * sl
        target = entry + sgn * tp
        be_px = entry + sgn * be_off
        j_end = path.n - 1 if hold_sec is None else min(path.index_at_or_after(fill_sec + hold_sec), path.n - 1)
        if j_end <= j0:
            d.update(taken=False, skip_reason="data_end"); out.append(d); continue
        jg = path.first_gap(j0, j_end)
        j_lim = jg if jg > 0 else j_end
        # ask-adjusted arrays for shorts (exit at the ask = bid + spread)
        adj = spread if sgn < 0 else 0.0
        hs = path.h[j0:j_lim] + adj
        ls = path.l[j0:j_lim] + adj
        os_ = path.o[j0:j_lim] + adj
        cs = path.c[j0:j_lim] + adj
        if sgn > 0:
            fav = hs - entry; adv = entry - ls
            stop_hit = ls <= stop0; tp_hit = hs >= target
        else:
            fav = entry - ls; adv = hs - entry
            stop_hit = hs >= stop0; tp_hit = ls <= target
        js = int(np.argmax(stop_hit)) if stop_hit.any() else 10**9
        jt = int(np.argmax(tp_hit)) if tp_hit.any() else 10**9
        jb = 10**9
        if be_trig is not None:
            trig = fav >= float(be_trig)
            if trig.any():
                jb = int(np.argmax(trig))
        be_same_bar = False
        be_armed = False
        reason = None; jx = None; exit_px = None
        # ---- phase 1: before/at the breakeven trigger
        first = min(js, jt, jb)
        if first == 10**9:
            pass  # neither stop, target nor trigger inside the path -> time/gap/data-end below
        elif js == first:                        # stop first (also when tied with trigger/target)
            jx = j0 + js; op = os_[js]
            px = stop0
            if (sgn > 0 and op < stop0) or (sgn < 0 and op > stop0):
                px = op
            exit_px = px - sgn * slip; reason = "stop"
        elif jt == first:                        # target reached before or in the trigger bar
            jx = j0 + jt; op = os_[jt]
            px = target
            if (sgn > 0 and op > target) or (sgn < 0 and op < target):
                px = op
            exit_px = px; reason = "target"
        else:                                    # breakeven trigger bar
            be_armed = True
            closes_behind = (sgn > 0 and cs[jb] <= be_px) or (sgn < 0 and cs[jb] >= be_px)
            if closes_behind:
                be_same_bar = True
                jx = j0 + jb; exit_px = be_px - sgn * slip; reason = "breakeven"
            else:
                # ---- phase 2: from the bar after the trigger, stop = breakeven
                k0 = jb + 1
                if sgn > 0:
                    be_hit = ls[k0:] <= be_px; tp2 = hs[k0:] >= target
                else:
                    be_hit = hs[k0:] >= be_px; tp2 = ls[k0:] <= target
                kb = int(np.argmax(be_hit)) if be_hit.any() else 10**9
                kt = int(np.argmax(tp2)) if tp2.any() else 10**9
                if kb <= kt and kb < 10**9:
                    jx = j0 + k0 + kb; op = os_[k0 + kb]
                    px = be_px
                    if (sgn > 0 and op < be_px) or (sgn < 0 and op > be_px):
                        px = op
                    exit_px = px - sgn * slip; reason = "breakeven"
                elif kt < 10**9:
                    jx = j0 + k0 + kt; op = os_[k0 + kt]
                    px = target
                    if (sgn > 0 and op > target) or (sgn < 0 and op < target):
                        px = op
                    exit_px = px; reason = "target"
        if reason is None:
            if jg > 0:
                jx = jg - 1; exit_px = cs[jx - j0] - sgn * slip; reason = "data_gap"
            else:
                jx = j_end
                exit_px = path.o[jx] + adj - sgn * slip
                reason = "time" if (hold_sec is not None and jx < path.n - 1) else "data_end"
        seg_fav = fav[:jx - j0 + 1]; seg_adv = adv[:jx - j0 + 1]
        mfe = float(seg_fav.max()); mae = float(seg_adv.max())
        pnl_oz = (exit_px - entry) * sgn - cost["comm_oz"]
        nights = _nights(pd.Timestamp(fill_sec, unit="s"), pd.Timestamp(int(path.ti[jx]), unit="s")) if cost["swap"] else 0
        swap_oz = nights * (SWAP_LONG if sgn > 0 else SWAP_SHORT)
        pnl_oz += swap_oz
        d.update(taken=True, skip_reason="", entry_time=pd.Timestamp(fill_sec, unit="s"),
                 exit_time=pd.Timestamp(int(path.ti[jx]), unit="s"), entry=entry, exit=exit_px,
                 stop=stop0, target=target, risk_usd=sl, reward_usd=tp, rr_actual=tp / sl,
                 exit_reason=reason, be_armed=be_armed, be_same_bar=be_same_bar,
                 pnl_oz=pnl_oz, pnl_usd=pnl_oz * oz, r_net=pnl_oz / sl, r_gross=((exit_px - entry) * sgn) / sl,
                 swap_r=swap_oz / sl, spread_r=spread / sl, nights=nights, mfe_usd=mfe, mae_usd=mae,
                 mfe_r=mfe / sl, mae_r=mae / sl, hold_h=(int(path.ti[jx]) - fill_sec) / 3600.0,
                 bars_m1=jx - j0 + 1, win=pnl_oz > 0,
                 exit_i=int(np.searchsorted(m15_ti, int(path.ti[jx]), side="right") - 1))
        out.append(d)
        busy_until = int(path.ti[jx])
    return pd.DataFrame(out)
