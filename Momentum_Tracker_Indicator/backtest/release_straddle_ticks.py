"""Phase 14: tick-level reconstruction of the frozen 15:30 release straddle (see results/phase14/frozen_spec.json).

usage: python release_straddle_ticks.py            (reads data/ticks/*.csv; writes results/phase14/*)
"""
import glob, json, math, os, sys, time
import numpy as np, pandas as pd

T0 = time.time()
TICK_DIR = "data/ticks"; OUT = "results/phase14"; os.makedirs(OUT, exist_ok=True)
SPEC = json.load(open(f"{OUT}/frozen_spec.json"))
A_TRIG, T_TGT, H_MIN = 0.25, 0.75, 250
XM_SPREAD = 0.51

# ------------------------------------------------------------------ helpers
def last_sunday(y, m):
    d = pd.Timestamp(year=y, month=m + 1, day=1) - pd.Timedelta(days=1)
    return d - pd.Timedelta(days=(d.weekday() + 1) % 7)
def server_offset_hours(day):
    y = day.year; a = last_sunday(y, 3) + pd.Timedelta(hours=1); b = last_sunday(y, 10) + pd.Timedelta(hours=1)
    return 3 if (day >= a and day < b) else 2
def load_day(day):
    """All tick files of a server day -> DataFrame in server time (ms). Returns None if any of the 6 hourly files is missing."""
    off = server_offset_hours(day); base = 11 if off == 3 else 12
    frames = []; have = []
    for h in range(base, base + 6):
        f = f"{TICK_DIR}/xauusd_{day.strftime('%Y-%m-%d')}_{h:02d}utc.csv"
        if not os.path.exists(f): continue
        try: d = pd.read_csv(f)
        except Exception as e: return None, f"unreadable {os.path.basename(f)}: {e}"
        if len(d): frames.append(d); have.append(h)
    if (base + 1) not in have: return None, "missing the event hour"
    if not frames: return None, "empty files"
    t = pd.concat(frames, ignore_index=True)
    t = t.rename(columns={"timestamp": "ts", "askPrice": "ask", "bidPrice": "bid", "askVolume": "askv", "bidVolume": "bidv"})
    t["ts"] = t["ts"].astype("int64") + off * 3600 * 1000            # server-time epoch ms
    t = t.sort_values("ts", kind="stable").reset_index(drop=True)
    return t, None

# ------------------------------------------------------------------ data quality
def audit_day(t, day):
    q = dict(day=str(day.date()), ticks=int(len(t)), dup_ts=int(t.ts.duplicated().sum()), bid_gt_ask=int((t.bid > t.ask).sum()), zero_or_neg_spread=int((t.ask - t.bid <= 0).sum()),
             spread_med=round(float((t.ask - t.bid).median()), 3), spread_p99=round(float((t.ask - t.bid).quantile(.99)), 3), spread_max=round(float((t.ask - t.bid).max()), 3),
             max_gap_s=round(float(t.ts.diff().max() / 1000), 1), ticks_1530_1531=int(((t.ts % 86400000) // 60000 == 15 * 60 + 30).sum()), price_decimals=int(max(len(str(x).split(".")[-1]) for x in t.bid.head(200).astype(str))))
    return q

# ------------------------------------------------------------------ M5 ATR from ticks (bid), 14:00 -> 15:25 bars = 17 bars; need 14 closed bars before 15:25 plus the 15:25 bar itself
_M1 = None
def m1_atr(day):
    """Fallback: M5 ATR(14) on the 15:25 bar and its close from the Dukascopy M1 dataset (server time)."""
    global _M1
    if _M1 is None:
        m = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"]); m = m[m.time >= "2024-12-01"]
        import twk_engine as E
        m5 = E.resample(m, 5).reset_index(drop=True); m5["atr"] = E.rma(E.true_range(m5.high.to_numpy(float), m5.low.to_numpy(float), m5.close.to_numpy(float), True), 14)
        _M1 = m5.set_index("time")
    ts = pd.Timestamp(day.date()) + pd.Timedelta(hours=15, minutes=25)
    if ts in _M1.index: r = _M1.loc[ts]; return float(r.atr), float(r.close)
    return np.nan, np.nan
def atr_from_ticks(t, day):
    day0 = pd.Timestamp(day.date()).value // 10**6                     # server midnight ms
    start = day0 + 14 * 3600 * 1000
    bars = []
    for k in range(18):                                                 # 14:00 .. 15:25 (18 bars)
        a = start + k * 300000; b = a + 300000
        w = t[(t.ts >= a) & (t.ts < b)]
        if len(w) == 0:
            atr, close = m1_atr(day)                                     # pre-event hour not downloaded: use the M1 dataset
            if np.isnan(atr): return np.nan, np.nan
            pre = t[t.ts <= day0 + (15 * 3600 + 30 * 60) * 1000]
            return atr, (float(pre.bid.iloc[-1]) if len(pre) else close)
        bars.append((w.bid.iloc[0], w.bid.max(), w.bid.min(), w.bid.iloc[-1]))
    o, h, l, c = (np.array(x) for x in zip(*bars))
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    for i in range(1, len(c)): tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    # Wilder RMA(14) seeded with the SMA of the first 14 true ranges (bars 0..13), then bars 14..17
    atr = tr[:14].mean()
    for i in range(14, len(tr)): atr = atr + (tr[i] - atr) / 14
    return float(atr), float(c[-1])                                     # ATR on the 15:25 bar, and its close = reference

# ------------------------------------------------------------------ the straddle on ticks
def run_event(t, day, a_trig=A_TRIG, T=T_TGT, H=H_MIN, latency_ms=250, fill_mode="A", start_offset_s=0):
    day0 = pd.Timestamp(day.date()).value // 10**6; t0 = day0 + (15 * 3600 + 30 * 60) * 1000 + start_offset_s * 1000
    atr, ref0 = atr_from_ticks(t, day)
    ref = ref0
    if start_offset_s > 0:
        pre = t[t.ts <= t0]
        ref = float(pre.bid.iloc[-1]) if len(pre) else np.nan          # delayed straddle: reference = bid at the delayed start
    res = dict(day=str(day.date()), weekday=day.weekday(), atr=atr, ref=ref)
    if np.isnan(atr) or atr <= 0 or np.isnan(ref): res.update(status="DATA_INSUFFICIENT", reason="no ATR bars"); return res
    w = t[(t.ts >= t0) & (t.ts < t0 + H * 60000)].reset_index(drop=True)
    if len(w) < 50: res.update(status="DATA_INSUFFICIENT", reason="too few ticks in window"); return res
    res["horizon_available_min"] = float((w.ts.iloc[-1] - t0) / 60000)
    ts, bid, ask = w.ts.to_numpy(), w.bid.to_numpy(), w.ask.to_numpy()
    U = ref + a_trig * atr; D = ref - a_trig * atr
    sp = ask - bid
    res.update(U=U, D=D, spread_ref=float(sp[0]), spread_med_1min=float(np.median(sp[ts < t0 + 60000])) if (ts < t0 + 60000).any() else np.nan, spread_max_1min=float(sp[ts < t0 + 60000].max()) if (ts < t0 + 60000).any() else np.nan,
               first_min_bid_range=float(bid[ts < t0 + 60000].max() - bid[ts < t0 + 60000].min()) if (ts < t0 + 60000).any() else np.nan, ticks_first_min=int((ts < t0 + 60000).sum()))
    iu = np.argmax(ask >= U) if (ask >= U).any() else -1; idn = np.argmax(bid <= D) if (bid <= D).any() else -1
    res.update(t_up_ms=int(ts[iu] - t0) if iu >= 0 else None, t_dn_ms=int(ts[idn] - t0) if idn >= 0 else None, both_touched=bool(iu >= 0 and idn >= 0))
    if iu < 0 and idn < 0: res.update(status="NO_TRADE", first="none", pnl_atr=0.0); return res
    if iu >= 0 and idn >= 0 and ts[iu] == ts[idn]: res.update(status="AMBIGUOUS_EXECUTION", first="tie"); return res
    side = 1 if (idn < 0 or (iu >= 0 and ts[iu] < ts[idn])) else -1
    i_tr = iu if side == 1 else idn; res.update(first="up" if side == 1 else "down", t_trigger_ms=int(ts[i_tr] - t0), spread_at_trigger=float(sp[i_tr]))
    mid_tr = (bid[i_tr] + ask[i_tr]) / 2
    res["spread_driven"] = bool((side == 1 and mid_tr < U) or (side == -1 and mid_tr > D))   # the quote crossed the level only because the spread widened
    # Case D: the other side triggers before the cancellation latency elapses
    i_other = idn if side == 1 else iu
    both_exec = i_other >= 0 and (ts[i_other] - ts[i_tr]) <= latency_ms
    res["both_executed"] = bool(both_exec)
    def fill_px(i, is_buy):
        """Scenario fills: A = triggering tick; B = worse of the triggering tick and the first tick >= 250 ms later; C = worst within 1000 ms."""
        px = ask if is_buy else bid
        if fill_mode == "A": return float(px[i])
        horizon = 250 if fill_mode == "B" else 1000
        j = np.searchsorted(ts, ts[i] + horizon, side="left"); j = min(j, len(ts) - 1)
        if fill_mode == "B": cand = [px[i], px[j]]
        else: cand = px[i:j + 1]
        return float(max(cand) if is_buy else min(cand))
    fill = fill_px(i_tr, side == 1)
    tgt = fill + T * atr if side == 1 else fill - T * atr
    stop = D if side == 1 else U
    # walk forward from the trigger
    mfe = mae = 0.0; exit_px = None; reason = None; i_exit = None
    for j in range(i_tr + 1, len(ts)):
        if side == 1:
            mfe = max(mfe, bid[j] - fill); mae = max(mae, fill - bid[j])
            if bid[j] <= stop: exit_px = float(bid[j]); reason = "STOP_HIT"; i_exit = j; break
            if bid[j] >= tgt: exit_px = float(bid[j]); reason = "TARGET_HIT"; i_exit = j; break
        else:
            mfe = max(mfe, fill - ask[j]); mae = max(mae, ask[j] - fill)
            if ask[j] >= stop: exit_px = float(ask[j]); reason = "STOP_HIT"; i_exit = j; break
            if ask[j] <= tgt: exit_px = float(ask[j]); reason = "TARGET_HIT"; i_exit = j; break
    if exit_px is None:
        i_exit = len(ts) - 1; exit_px = float(bid[i_exit] if side == 1 else ask[i_exit]); reason = "TIMEOUT"
    pnl = (exit_px - fill) if side == 1 else (fill - exit_px)
    # Case D cost: the second leg is closed at the first quote after the cancellation latency at its own spread (a round trip lost)
    if both_exec:
        j2 = min(np.searchsorted(ts, ts[i_tr] + latency_ms, side="left"), len(ts) - 1)
        pnl -= float(sp[j2])
    gross = ((bid[i_exit] + ask[i_exit]) / 2 - (bid[i_tr] + ask[i_tr]) / 2) * side
    res.update(status=reason, side=side, fill=fill, target=float(tgt), stop=float(stop), exit=exit_px, t_exit_ms=int(ts[i_exit] - t0), pnl_atr=float(pnl / atr), gross_mid_atr=float(gross / atr),
               mfe_atr=float(mfe / atr), mae_atr=float(mae / atr), spread_at_exit=float(sp[i_exit]), cost_atr=float((gross - pnl) / atr))
    return res

# ------------------------------------------------------------------ run over all downloaded days
def all_days():
    days = sorted({os.path.basename(f).split("_")[1] for f in glob.glob(f"{TICK_DIR}/xauusd_*utc.csv")})
    return [pd.Timestamp(d) for d in days]

def main():
    days = all_days(); print(f"{len(days)} days with tick files ({time.time()-T0:.0f}s)", flush=True)
    audits, base, plateau = [], [], []
    for n_, day in enumerate(days):
        t, err = load_day(day)
        if t is None:
            base.append(dict(day=str(day.date()), weekday=day.weekday(), status="DATA_INSUFFICIENT", reason=err)); continue
        audits.append(audit_day(t, day))
        for mode in ("A", "B", "C"):
            r = run_event(t, day, fill_mode=mode); r["scenario"] = mode; r["latency_ms"] = 250; base.append(r)
        # latency variants on scenario A
        for lat in (0, 1000):
            r = run_event(t, day, fill_mode="A", latency_ms=lat); r["scenario"] = f"A_lat{lat}"; r["latency_ms"] = lat; base.append(r)
        # DEV-only plateaus (2025): trigger, target, horizon; scenario B
        if day.year == 2025:
            for a in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
                r = run_event(t, day, a_trig=a, fill_mode="B"); plateau.append(dict(kind="trigger", value=a, **{k: r.get(k) for k in ("day", "weekday", "status", "pnl_atr", "gross_mid_atr")}))
            for T in (0.50, 0.75, 1.00, 1.25, 1.50):
                r = run_event(t, day, T=T, fill_mode="B"); plateau.append(dict(kind="target", value=T, **{k: r.get(k) for k in ("day", "weekday", "status", "pnl_atr", "gross_mid_atr")}))
            for H in (30, 60, 100, 150, 300):
                r = run_event(t, day, H=H, fill_mode="B"); plateau.append(dict(kind="horizon", value=H, **{k: r.get(k) for k in ("day", "weekday", "status", "pnl_atr", "gross_mid_atr")}))
            for so in (30, 60, 120, 300):
                r = run_event(t, day, fill_mode="B", start_offset_s=so); plateau.append(dict(kind="start_offset_s", value=so, **{k: r.get(k) for k in ("day", "weekday", "status", "pnl_atr", "gross_mid_atr")}))
        # controls: same-day random timestamps (two per day), scenario B, and Thu/Fri random
        rng = np.random.default_rng(int(day.value // 10**9) % 100000)
        day0 = pd.Timestamp(day.date()).value // 10**6
        for c_ in range(2):
            t_rand = day0 + int(rng.integers(14 * 3600 + 80 * 60, 19 * 3600)) * 1000        # between 15:20 and 19:00, excluding 15:25-15:35
            if abs(t_rand - (day0 + (15 * 3600 + 30 * 60) * 1000)) < 10 * 60000: continue
            # shift the tick frame so that t_rand plays the role of 15:30
            shift = (day0 + (15 * 3600 + 30 * 60) * 1000) - t_rand
            t2 = t.copy(); t2["ts"] = t2["ts"] + shift
            r = run_event(t2, day, fill_mode="B"); r["scenario"] = "CONTROL_random_same_day"; r["latency_ms"] = 250; r["t_random"] = str(pd.Timestamp(t_rand, unit="ms"))[11:19]; base.append(r)
        if (n_ + 1) % 25 == 0: print(f"  {n_+1}/{len(days)} days ({time.time()-T0:.0f}s)", flush=True)
    B = pd.DataFrame(base); B.to_csv(f"{OUT}/events.csv", index=False)
    P = pd.DataFrame(plateau); P.to_csv(f"{OUT}/plateau_dev.csv", index=False)
    Q = pd.DataFrame(audits); Q.to_csv(f"{OUT}/tick_audit.csv", index=False)
    print(f"events {len(B)} rows, plateau {len(P)} rows, audit {len(Q)} days ({time.time()-T0:.0f}s)")

if __name__ == "__main__":
    main()
