"""PBD structure detection on M15 bars: impulse -> consolidation range -> playbooks.

Everything discretionary in the source strategy is replaced by a measurable rule.  The
rules are parameters of `BASELINE` (pre-registered, not tuned) and every alternative
tested later is a single-parameter change from it.

State machine (one structure at a time, no look-ahead: every decision at bar i uses only
bars <= i):

  IDLE      scan for an impulse window ending at bar i (definition = P["imp_def"]).
  IMPULSE   track the extreme; abandon on deep retrace or if no range forms within
            imp_max_wait bars of the extreme; confirm a range when the last rng_min_bars
            bars form a box that satisfies the width / drift / location rules.
  RANGE     boundaries frozen at confirmation.  Emit ping-pong signals; detect breakouts;
            expire after rng_max_bars.
  BREAKOUT  wait for a pullback to the broken boundary (emit breakout_pullback signal),
            or a failed breakout (back to RANGE), or expiry (no pullback -> IDLE).

Signals are proposals; the engine decides whether a position can be taken.
"""
import numpy as np
import pandas as pd

BASELINE = dict(
    # ---- impulse (A)
    imp_def="atr",          # atr | pct | rangeexp | consec
    imp_N=8,                # window length in M15 bars (2 h)
    imp_k=3.5,              # |net move| >= imp_k * ATR14 measured before the window
    imp_eff=0.6,            # efficiency ratio |net| / sum|dc| over the window
    imp_pct=0.98,           # pct def: |net| >= trailing-30-day 98th percentile of |net|
    imp_rexp=3.0,           # rangeexp def: window range >= imp_rexp * trailing-30-day median window range
    imp_consec=5,           # consec def: >= 5 same-direction closes AND |net| >= 2 ATR
    imp_lookback_origin=4,  # origin search: lowest low within imp_lookback_origin * N bars
    imp_max_wait=24,        # bars after the extreme in which a range must form (6 h)
    imp_max_retrace=0.618,  # abandon if close retraces more than this share of the impulse
    # ---- consolidation range (B, C)
    rng_min_bars=8,         # minimum bars in the confirmation window (2 h)
    rng_max_width_imp=0.6,  # width <= 0.6 * impulse size
    rng_min_width_atr=0.5,  # width >= 0.5 * pre-impulse ATR
    rng_max_drift=0.5,      # |close_end - close_start| <= 0.5 * width across the window
    rng_max_bars=288,       # structure expires after 3 days in the range
    # ---- ping-pong playbook
    zone=0.20,              # entry zone = 20% of width from a boundary
    pp_rearm=0.30,          # a new signal on the same side needs a close >= 30% of width away first
    pp_stop_atr=0.5,        # stop beyond the boundary, in ATR14 at signal time
    pp_target=0.9,          # target = boundary + 0.9 * width (just inside the opposite boundary)
    # ---- breakout / pullback playbook (D, E)
    bo_pen_atr=0.25,        # breakout = close beyond the boundary by >= 0.25 ATR
    bo_conf="close",        # close | bigbar (bar range >= 1.5 ATR) | volume (vol_rel >= 1.5) | both
    pb_bars=16,             # pullback must arrive within 16 bars (4 h)
    pb_depth_atr=0.25,      # pullback: bar reaches boundary +/- 0.25 ATR
    pb_fail_atr=0.25,       # close back inside the range by > 0.25 ATR = failed breakout
    bo_stop_atr=0.5,        # stop = beyond min(pullback extreme, boundary) by 0.5 ATR
    bo_mm=1.0,              # continuation target = boundary + 1.0 * width (measured move)
    # ---- management
    max_hold_bars=288,      # 3 days (source: 4 h to 3 days)
)


def prepare(m15: pd.DataFrame, N: int) -> dict:
    """Arrays and rolling references needed by the detector (all trailing, no look-ahead)."""
    c = m15["close"].values.astype(float)
    net = pd.Series(c).diff(N).abs()
    d = {}
    d["net_pct98"] = net.rolling(2880, min_periods=960).quantile(0.98).values
    rng = pd.Series(m15["high"].values).rolling(N).max() - pd.Series(m15["low"].values).rolling(N).min()
    d["rng_med30"] = rng.rolling(2880, min_periods=960).median().values
    tdiff = m15["time"].diff().dt.total_seconds().fillna(0).values / 60.0
    d["gap"] = tdiff > 120           # gap of more than 2 h before this bar
    return d


def detect(m15: pd.DataFrame, P: dict = None, prep: dict = None):
    P = {**BASELINE, **(P or {})}
    N = int(P["imp_N"])
    if prep is None:
        prep = prepare(m15, N)
    o = m15["open"].values.tolist(); h = m15["high"].values.tolist()
    l = m15["low"].values.tolist(); c = m15["close"].values.tolist()
    atr = m15["atr14"].values.tolist()
    vol_rel = m15["vol_rel"].fillna(1.0).values.tolist()
    gap = prep["gap"].tolist()
    pct98 = prep["net_pct98"].tolist(); rmed = prep["rng_med30"].tolist()
    n = len(c)
    abs_dc = [0.0] + [abs(c[i] - c[i - 1]) for i in range(1, n)]
    cum_dc = np.cumsum(abs_dc).tolist()
    gap_cum = np.cumsum(np.asarray(gap, dtype=int)).tolist()

    structures = []
    signals = []
    state = "IDLE"
    S = None  # current structure dict

    def new_struct(i, direction, start, origin, origin_idx, extreme, ext_idx, atr_ref, er):
        return dict(sid=len(structures), stype="P" if direction > 0 else "B", imp_dir=direction,
                    imp_start=start, imp_detect=i, origin=origin, origin_idx=origin_idx,
                    extreme=extreme, ext_idx=ext_idx, atr_ref=atr_ref, imp_er=er,
                    rng_start=None, rng_confirm=None, rh=None, rl=None,
                    touches_hi=0, touches_lo=0, in_hi=False, in_lo=False,
                    armed_long=True, armed_short=True, failed_bo=0, breakouts=0,
                    pp_signals=0, bo_signals=0, outcome=None, end_idx=None,
                    bo_dir=0, bo_idx=None, bo_boundary=None, pb_extreme=None)

    def close_struct(S, i, outcome):
        S["outcome"] = outcome
        S["end_idx"] = i
        S["imp_size"] = abs(S["extreme"] - S["origin"])
        S["imp_bars"] = S["ext_idx"] - S["origin_idx"]
        if S["rh"] is not None:
            S["width"] = S["rh"] - S["rl"]
        structures.append(S)

    def impulse_at(i):
        """Return (direction, er) if an impulse window ends at bar i, else None."""
        if i < N + 20 or i - N < 0:
            return None
        if gap_cum[i] - gap_cum[i - N] > 0:      # a data gap inside the window
            return None
        a_pre = atr[i - N]
        if not (a_pre == a_pre) or a_pre <= 0:
            return None
        net = c[i] - c[i - N]
        path = cum_dc[i] - cum_dc[i - N]
        er = abs(net) / path if path > 0 else 0.0
        defn = P["imp_def"]
        ok = False
        if defn == "atr":
            ok = abs(net) >= P["imp_k"] * a_pre and er >= P["imp_eff"]
        elif defn == "pct":
            ref = pct98[i]
            ok = (ref == ref) and abs(net) >= ref and er >= P["imp_eff"]
        elif defn == "rangeexp":
            ref = rmed[i]
            wr = max(h[i - N + 1:i + 1]) - min(l[i - N + 1:i + 1])
            ok = (ref == ref) and wr >= P["imp_rexp"] * ref and er >= P["imp_eff"]
        elif defn == "consec":
            m = int(P["imp_consec"])
            if i - m < 0:
                return None
            sgn = 1 if c[i] > c[i - 1] else -1
            run = all((c[j] - c[j - 1]) * sgn > 0 for j in range(i - m + 1, i + 1))
            ok = run and abs(c[i] - c[i - m]) >= 2.0 * a_pre and (net * sgn > 0)
        if not ok:
            return None
        return (1 if net > 0 else -1), er

    for i in range(1, n):
        if state == "IDLE":
            r = impulse_at(i)
            if r is None:
                continue
            direction, er = r
            a_pre = atr[i - N]
            lb = max(0, i - P["imp_lookback_origin"] * N)
            if direction > 0:
                # origin: lowest low in the lookback, provided the path from it never retraced >50%
                w_lo = min(l[i - N:i + 1]); w_lo_idx = i - N + l[i - N:i + 1].index(w_lo)
                seg = l[lb:i + 1]; o_idx = lb + seg.index(min(seg))
                ext = max(h[o_idx:i + 1]); ext_idx = o_idx + h[o_idx:i + 1].index(ext)
                origin, origin_idx = l[o_idx], o_idx
                # retrace check on closes between origin and extreme
                ok = True
                if o_idx < w_lo_idx:
                    run_max = -1e18
                    for j in range(o_idx, ext_idx + 1):
                        run_max = max(run_max, h[j])
                        if run_max - l[j] > 0.5 * (run_max - origin) and run_max > origin:
                            ok = False
                            break
                if not ok:
                    origin, origin_idx = w_lo, w_lo_idx
                    ext = max(h[origin_idx:i + 1]); ext_idx = origin_idx + h[origin_idx:i + 1].index(ext)
            else:
                w_hi = max(h[i - N:i + 1]); w_hi_idx = i - N + h[i - N:i + 1].index(w_hi)
                seg = h[lb:i + 1]; o_idx = lb + seg.index(max(seg))
                ext = min(l[o_idx:i + 1]); ext_idx = o_idx + l[o_idx:i + 1].index(ext)
                origin, origin_idx = h[o_idx], o_idx
                ok = True
                if o_idx < w_hi_idx:
                    run_min = 1e18
                    for j in range(o_idx, ext_idx + 1):
                        run_min = min(run_min, l[j])
                        if h[j] - run_min > 0.5 * (origin - run_min) and run_min < origin:
                            ok = False
                            break
                if not ok:
                    origin, origin_idx = w_hi, w_hi_idx
                    ext = min(l[origin_idx:i + 1]); ext_idx = origin_idx + l[origin_idx:i + 1].index(ext)
            S = new_struct(i, direction, i - N, origin, origin_idx, ext, ext_idx, a_pre, er)
            state = "IMPULSE"
            continue

        if state == "IMPULSE":
            d = S["imp_dir"]
            if d > 0 and h[i] > S["extreme"]:
                S["extreme"], S["ext_idx"] = h[i], i
            elif d < 0 and l[i] < S["extreme"]:
                S["extreme"], S["ext_idx"] = l[i], i
            size = abs(S["extreme"] - S["origin"])
            retr = (S["extreme"] - c[i]) * d
            if size > 0 and retr > P["imp_max_retrace"] * size:
                close_struct(S, i, "abandoned_retrace"); state = "IDLE"; S = None
                continue
            if i - S["ext_idx"] > P["imp_max_wait"]:
                close_struct(S, i, "abandoned_no_range"); state = "IDLE"; S = None
                continue
            M = int(P["rng_min_bars"])
            if i - S["ext_idx"] + 1 < M:      # window must lie at/after the extreme bar
                continue
            ws = i - M + 1
            rh = max(h[ws:i + 1]); rl = min(l[ws:i + 1]); W = rh - rl
            a_ref = S["atr_ref"]
            drift = abs(c[i] - c[ws])
            if (W <= P["rng_max_width_imp"] * size and W >= P["rng_min_width_atr"] * a_ref
                    and drift <= P["rng_max_drift"] * W):
                # location: the box must sit in the impulse's terminal 61.8% (P above origin)
                if d > 0:
                    loc_ok = rl >= S["origin"] + (1 - P["imp_max_retrace"]) * size
                else:
                    loc_ok = rh <= S["origin"] - (1 - P["imp_max_retrace"]) * size
                if loc_ok:
                    S.update(rng_start=ws, rng_confirm=i, rh=rh, rl=rl, width=W,
                             drift=drift / W if W > 0 else np.nan,
                             retrace_at_confirm=((S["extreme"] - (rl if d > 0 else rh)) * d) / size if size > 0 else np.nan)
                    state = "RANGE"
            continue

        if state == "RANGE":
            rh, rl = S["rh"], S["rl"]; W = rh - rl; a = atr[i]
            # touches (clustered) and re-arming
            hi_zone = h[i] >= rh - P["zone"] * W
            lo_zone = l[i] <= rl + P["zone"] * W
            if hi_zone and not S["in_hi"]:
                S["touches_hi"] += 1
            if lo_zone and not S["in_lo"]:
                S["touches_lo"] += 1
            S["in_hi"], S["in_lo"] = hi_zone, lo_zone
            if c[i] >= rl + P["pp_rearm"] * W:
                S["armed_long"] = True
            if c[i] <= rh - P["pp_rearm"] * W:
                S["armed_short"] = True
            # breakout?
            bo = 0
            if c[i] > rh + P["bo_pen_atr"] * a:
                bo = 1
            elif c[i] < rl - P["bo_pen_atr"] * a:
                bo = -1
            if bo != 0:
                conf = P["bo_conf"]
                big = (h[i] - l[i]) >= 1.5 * a
                volc = vol_rel[i] >= 1.5
                ok = (conf == "close") or (conf == "bigbar" and big) or (conf == "volume" and volc) or (conf == "both" and big and volc)
                if ok:
                    S["breakouts"] += 1
                    S.update(bo_dir=bo, bo_idx=i, bo_boundary=rh if bo > 0 else rl, pb_extreme=None,
                             bo_bar_range_atr=(h[i] - l[i]) / a if a > 0 else np.nan, bo_vol_rel=vol_rel[i],
                             bo_close_pen_atr=((c[i] - rh) if bo > 0 else (rl - c[i])) / a if a > 0 else np.nan)
                    S["bo_signals"] += 1
                    signals.append(_signal(S, i, "breakout_immediate", "long" if bo > 0 else "short",
                                           c[i], _bo_stop(S, i, bo, c[i], a, P), _bo_target(S, bo, P), P, m15, a))
                    state = "BREAKOUT"
                    continue
            if i - S["rng_start"] > P["rng_max_bars"]:
                close_struct(S, i, "expired_range"); state = "IDLE"; S = None
                continue
            # ping-pong signals (rejection close inside the range after touching the zone)
            if lo_zone and c[i] > rl and c[i] <= rl + 0.5 * W and S["armed_long"]:
                S["armed_long"] = False
                S["pp_signals"] += 1
                stop = rl - P["pp_stop_atr"] * a
                target = rl + P["pp_target"] * W
                signals.append(_signal(S, i, "pingpong", "long", c[i], stop, target, P, m15, a))
            elif hi_zone and c[i] < rh and c[i] >= rh - 0.5 * W and S["armed_short"]:
                S["armed_short"] = False
                S["pp_signals"] += 1
                stop = rh + P["pp_stop_atr"] * a
                target = rh - P["pp_target"] * W
                signals.append(_signal(S, i, "pingpong", "short", c[i], stop, target, P, m15, a))
            continue

        if state == "BREAKOUT":
            bo = S["bo_dir"]; B = S["bo_boundary"]; a = atr[i]; W = S["rh"] - S["rl"]
            # failed breakout: close back inside by more than pb_fail_atr
            if (bo > 0 and c[i] < B - P["pb_fail_atr"] * a) or (bo < 0 and c[i] > B + P["pb_fail_atr"] * a):
                S["failed_bo"] += 1
                S["armed_long"] = S["armed_short"] = True
                S["in_hi"] = S["in_lo"] = False
                state = "RANGE"
                if i - S["rng_start"] > P["rng_max_bars"]:
                    close_struct(S, i, "expired_range"); state = "IDLE"; S = None
                continue
            if i - S["bo_idx"] > P["pb_bars"]:
                close_struct(S, i, "no_pullback"); state = "IDLE"; S = None
                continue
            # pullback to the boundary that holds (close on the breakout side)
            if bo > 0:
                reached = l[i] <= B + P["pb_depth_atr"] * a
                held = c[i] >= B
                S["pb_extreme"] = l[i] if S["pb_extreme"] is None else min(S["pb_extreme"], l[i])
            else:
                reached = h[i] >= B - P["pb_depth_atr"] * a
                held = c[i] <= B
                S["pb_extreme"] = h[i] if S["pb_extreme"] is None else max(S["pb_extreme"], h[i])
            if reached and held and i > S["bo_idx"]:
                S["bo_signals"] += 1
                sig = _signal(S, i, "breakout_pullback", "long" if bo > 0 else "short", c[i],
                              _bo_stop(S, i, bo, c[i], a, P), _bo_target(S, bo, P), P, m15, a)
                sig["pb_depth_atr"] = ((B - S["pb_extreme"]) if bo > 0 else (S["pb_extreme"] - B)) / a if a > 0 else np.nan
                sig["bars_since_bo"] = i - S["bo_idx"]
                signals.append(sig)
                close_struct(S, i, "breakout_traded"); state = "IDLE"; S = None
                continue
            continue

    if S is not None:
        close_struct(S, n - 1, "open_at_end")
    return pd.DataFrame(structures), pd.DataFrame(signals), P


def _bo_stop(S, i, bo, px, a, P):
    B = S["bo_boundary"]
    pe = S["pb_extreme"]
    if bo > 0:
        ref = B if pe is None else min(pe, B)
        return ref - P["bo_stop_atr"] * a
    ref = B if pe is None else max(pe, B)
    return ref + P["bo_stop_atr"] * a


def _bo_target(S, bo, P):
    W = S["rh"] - S["rl"]
    if bo == S["imp_dir"]:               # continuation: measured move
        return S["bo_boundary"] + bo * P["bo_mm"] * W
    return S["origin"]                   # counter-impulse: back to the origin of the impulse


def _signal(S, i, etype, side, ref, stop, target, P, m15, a):
    W = S["rh"] - S["rl"]
    sgn = 1 if side == "long" else -1
    risk = (ref - stop) * sgn
    reward = (target - ref) * sgn
    row = m15.iloc[i]
    boundary = S["rl"] if (etype == "pingpong" and side == "long") else S["rh"] if etype == "pingpong" else S["bo_boundary"]
    vah, val, poc = row.get("vah", np.nan), row.get("val", np.nan), row.get("poc", np.nan)
    return dict(
        sid=S["sid"], i=i, time=row["time"], session=row["session"], news_slot=row["news_slot"],
        period=row["period"], stype=S["stype"], imp_dir=S["imp_dir"],
        imp_size=abs(S["extreme"] - S["origin"]), imp_size_atr=abs(S["extreme"] - S["origin"]) / S["atr_ref"],
        imp_bars=S["ext_idx"] - S["origin_idx"], imp_er=S["imp_er"], origin=S["origin"], extreme=S["extreme"],
        rng_start=S["rng_start"], rng_confirm=S["rng_confirm"], rng_age=i - S["rng_start"],
        rh=S["rh"], rl=S["rl"], width=W, width_atr=W / a if a > 0 else np.nan, width_over_imp=W / abs(S["extreme"] - S["origin"]),
        touches_hi=S["touches_hi"], touches_lo=S["touches_lo"], failed_bo=S["failed_bo"], breakouts=S["breakouts"],
        touches_side=(S["touches_lo"] if side == "long" else S["touches_hi"]) if etype == "pingpong" else S["breakouts"],
        rng_drift=S.get("drift", np.nan), retrace_at_confirm=S.get("retrace_at_confirm", np.nan),
        va_inside=bool((vah == vah) and (val == val) and S["rl"] < val and vah < S["rh"]),
        va_span_atr=(vah - val) / a if (a > 0 and vah == vah and val == val) else np.nan,
        pp_signals_before=S["pp_signals"], entry_type=etype, side=side, ref_price=ref, stop=stop, target=target,
        risk=risk, reward=reward, rr=reward / risk if risk > 0 else np.nan,
        pos_in_range=(ref - S["rl"]) / W if W > 0 else np.nan, boundary=boundary,
        atr14=a, atr_pct=row.get("atr_pct60d", np.nan), vol_rel=row.get("vol_rel", np.nan),
        spread_usd=row.get("spread_usd", np.nan), vah=vah, val=val, poc=poc,
        dist_vah_atr=(boundary - vah) / a if a > 0 else np.nan, dist_val_atr=(boundary - val) / a if a > 0 else np.nan,
        vah_dev=row.get("vah_dev", np.nan), val_dev=row.get("val_dev", np.nan),
        vah_tick=row.get("vah_tick", np.nan), val_tick=row.get("val_tick", np.nan),
        vah_tpo=row.get("vah_tpo", np.nan), val_tpo=row.get("val_tpo", np.nan),
        bo_relation=("continuation" if S["bo_dir"] == S["imp_dir"] else "counter") if etype != "pingpong" else "",
        bo_bar_range_atr=S.get("bo_bar_range_atr", np.nan) if etype != "pingpong" else np.nan,
        bo_vol_rel=S.get("bo_vol_rel", np.nan) if etype != "pingpong" else np.nan,
        bo_close_pen_atr=S.get("bo_close_pen_atr", np.nan) if etype != "pingpong" else np.nan,
        shock=bool(row.get("shock", False)),
    )
