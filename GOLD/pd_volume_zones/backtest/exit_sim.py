"""
exit_sim.py - conservative M1 path walker for exit-structure research (V4).

Execution rules (documented for STEP 9 of the brief):
  * The walk starts at the first M1 bar after the confirmation candle closes; entry = that close.
  * Inside an M1 bar the STOP is checked first against the stop level that was in force
    BEFORE the bar (adverse extreme vs stop). Only if the stop is not hit is the target /
    partial level checked against the favourable extreme. When both lie inside one bar the
    stop wins - the most conservative assumption.
  * A bar that opens beyond the stop or the target fills at the open (gap).
  * Every stop change (break-even, lock, trail) is computed at the bar's CLOSE from that
    bar's completed values and applies from the NEXT bar. Structure levels use completed
    5-min candles only; a swing is confirmed k candles after its centre.
  * MFE is not updated on the bar that stops the trade out (the stop is assumed to come
    first), MAE is. The ATR used by the ATR trail is the 5-min ATR14 at entry, fixed.
spec keys:
  target_R   float or None (None = no target, the walk ends at the stop / horizon)
  be         (trigger_R, level_R): once MFE >= trigger the stop is moved to entry + level_R x risk
  locks      [(trigger_R, level_R), ...]   same mechanism, several steps
  trail      None | {"kind": "atr", "mult": m, "activate_R": a}
                  | {"kind": "bar", "activate_R": a}      stop = low/high of the last completed 5-min candle
                  | {"kind": "swing", "activate_R": a, "k": k}   stop = last confirmed k-bar swing low/high
  partial    (fraction, R1): fraction of the position is booked at +R1, the rest runs to target/stop
"""
import numpy as np

LEVELS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
POST_LEVELS = (1.0, 1.5, 2.0)


def walk(side, entry, sl0, risk, j0, i5, D, spec, max_gap_ms=3 * 86400000, horizon_ms=None, atr=None):
    m1t, m1o, m1h, m1l, m1c = D["m1t"], D["m1o"], D["m1h"], D["m1l"], D["m1c"]
    t5, h5, l5, tf_ms = D["t"], D["h"], D["l"], D["tf_min"] * 60000
    n5, n = len(t5), len(m1t)
    long = side == "long"
    sgn = 1.0 if long else -1.0

    def R_of(px):
        return (px - entry) * sgn / risk

    def better(a, b):  # the more protective of two stop levels
        return max(a, b) if long else min(a, b)

    tgt = spec.get("target_R")
    be = spec.get("be")
    locks = spec.get("locks") or []
    trail = spec.get("trail")
    partial = spec.get("partial")
    cur_sl = sl0
    mfe = 0.0
    mae = 0.0
    first = {L: None for L in LEVELS}
    post_min = {L: None for L in POST_LEVELS}
    part_done = False
    part_R = 0.0
    frac_left = 1.0
    trail_on = False
    q = i5
    j = j0
    prev_t = None
    t_entry = t5[i5] + tf_ms
    if horizon_ms is None:
        horizon_ms = 10 ** 15
    exit_R = None
    reason = None
    exit_t = None
    while j < n:
        tj = m1t[j]
        if prev_t is not None and tj - prev_t > max_gap_ms:
            reason, exit_R, exit_t = "data_gap", R_of(m1c[j - 1]), prev_t
            break
        if tj - t_entry > horizon_ms:
            reason, exit_R, exit_t = "horizon", R_of(m1c[j - 1]), prev_t
            break
        # ---- completed 5-min candles -> structure trails (apply from this M1 bar on)
        while q + 1 < n5 and t5[q + 1] <= tj:
            q += 1
            qc = q - 1
            if trail_on and trail is not None and qc > i5:
                if trail["kind"] == "bar":
                    cur_sl = better(cur_sl, l5[qc] if long else h5[qc])
                elif trail["kind"] == "swing":
                    k = trail["k"]
                    ctr = qc - k
                    if ctr > i5 and ctr - k >= 0:
                        if long:
                            piv = l5[ctr] < l5[ctr - k:ctr].min() and l5[ctr] < l5[ctr + 1:qc + 1].min()
                            lvl = l5[ctr]
                        else:
                            piv = h5[ctr] > h5[ctr - k:ctr].max() and h5[ctr] > h5[ctr + 1:qc + 1].max()
                            lvl = h5[ctr]
                        if piv:
                            cur_sl = better(cur_sl, lvl)
        o_, h_, l_, c_ = m1o[j], m1h[j], m1l[j], m1c[j]
        adv = l_ if long else h_
        fav = h_ if long else l_
        # ---- stop first
        stop_hit = adv <= cur_sl if long else adv >= cur_sl
        if stop_hit:
            gapped = o_ <= cur_sl if long else o_ >= cur_sl
            px = o_ if gapped else cur_sl
            r = R_of(px)
            mae = max(mae, -min(r, 0.0))
            for L in POST_LEVELS:
                if post_min[L] is not None:
                    post_min[L] = min(post_min[L], r)
            exit_R, exit_t = r, tj
            reason = "SL" if cur_sl == sl0 else "TSL"
            break
        fav_R = R_of(fav)
        # ---- partial booking
        if partial is not None and not part_done and fav_R >= partial[1]:
            part_done = True
            part_R = partial[0] * partial[1]
            frac_left = 1.0 - partial[0]
        # ---- target
        if tgt is not None and fav_R >= tgt:
            gapped = R_of(o_) >= tgt
            r = R_of(o_) if gapped else tgt
            mfe = max(mfe, r)
            for L in LEVELS:
                if first[L] is None and r >= L:
                    first[L] = tj
            exit_R, exit_t, reason = r, tj, "TP"
            break
        # ---- no exit: excursions
        mfe = max(mfe, fav_R)
        mae = max(mae, -min(R_of(adv), 0.0))
        for L in LEVELS:
            if first[L] is None and fav_R >= L:
                first[L] = tj
        for L in POST_LEVELS:
            if post_min[L] is None:
                if fav_R >= L:
                    post_min[L] = L
            else:
                post_min[L] = min(post_min[L], R_of(adv))
        # ---- management at the close (applies from the next bar)
        if be is not None and mfe >= be[0]:
            cur_sl = better(cur_sl, entry + sgn * be[1] * risk)
        for trig, lvl in locks:
            if mfe >= trig:
                cur_sl = better(cur_sl, entry + sgn * lvl * risk)
        if trail is not None:
            if not trail_on and mfe >= trail["activate_R"]:
                trail_on = True
            if trail_on and trail["kind"] == "atr" and atr is not None and atr > 0:
                cur_sl = better(cur_sl, (entry + sgn * mfe * risk) - sgn * trail["mult"] * atr)
        prev_t = tj
        j += 1
    if reason is None:
        reason, exit_R, exit_t = "end_of_data", R_of(m1c[-1]), m1t[-1]
    total = part_R + frac_left * exit_R if part_done else exit_R
    return dict(R=total, exit_R_remainder=exit_R, reason=reason, exit_t=exit_t, mfe=mfe, mae=mae, first=first,
                post_min=post_min, partial_done=part_done, bars=j - j0 + 1)
