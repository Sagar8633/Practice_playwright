"""Phase 15: post-release microstructure transition. Tick timeline around 15:30 server in 14 bands, the empirical
spread-normalisation curve, the price-discovery curve, the information value of direction after normalisation
(unconditional and conditioned on five shock states), and continuation versus reversal of the first clean move.
Development = 2025 only; 2026 files are never read here. Executable outcomes use ask for buys / bid for sells;
mid is diagnostic only. Functions are importable; `python post_release_ticks.py` runs the study.
"""
import json, math, os, time
import numpy as np, pandas as pd
import release_straddle_ticks as R          # load_day, atr_from_ticks, all_days

OUT = "results/phase15"; os.makedirs(OUT, exist_ok=True)
BANDS = [(0, 100), (100, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, 30000), (30000, 60000), (60000, 120000), (120000, 300000), (300000, 600000), (600000, 900000), (900000, 1800000)]
BAND_LABEL = ["0-100 ms", "100-250 ms", "250-500 ms", "0.5-1 s", "1-2 s", "2-5 s", "5-10 s", "10-30 s", "30-60 s", "1-2 min", "2-5 min", "5-10 min", "10-15 min", "15-30 min"]
DAYS = [d for d in R.all_days() if d.year == 2025]
CONTROL_TIMES = ((16, 30), (17, 15))       # same-day windows with a normal spread and no scheduled US release

def day_ms(day, hh, mm): return pd.Timestamp(day.date()).value // 10**6 + (hh * 3600 + mm * 60) * 1000

def event_frame(t, day, t_event=None, minutes=60):
    """Ticks from t_event for `minutes`, with the pre-event normal spread (30 to 5 minutes before) and the day's ATR."""
    t0 = day_ms(day, 15, 30) if t_event is None else t_event
    atr, _ = R.atr_from_ticks(t, day)
    pre = t[(t.ts >= t0 - 30 * 60000) & (t.ts < t0 - 5 * 60000)]
    if len(pre) < 100 or np.isnan(atr) or atr <= 0: return None
    normal = float((pre.ask - pre.bid).median())
    ref_row = t[t.ts <= t0].iloc[-1]
    w = t[(t.ts >= t0) & (t.ts < t0 + minutes * 60000)].reset_index(drop=True)
    if len(w) < 100: return None
    w["rel"] = w.ts - t0; w["mid"] = (w.bid + w.ask) / 2; w["sp"] = w.ask - w.bid
    return dict(t0=t0, atr=atr, normal=normal, ref_mid=(ref_row.bid + ref_row.ask) / 2, ref_bid=ref_row.bid, ref_ask=ref_row.ask, w=w)

def band_stats(ev):
    w, atr, normal, ref = ev["w"], ev["atr"], ev["normal"], ev["ref_mid"]; rows = []
    mid = w.mid.to_numpy(); rel = w.rel.to_numpy(); sp = w.sp.to_numpy(); bid = w.bid.to_numpy(); ask = w.ask.to_numpy()
    dmid = np.sign(np.diff(mid))
    for (a, b), lab in zip(BANDS, BAND_LABEL):
        m = (rel >= a) & (rel < b); n = int(m.sum())
        row = dict(band=lab, ticks=n, ticks_per_s=n / ((b - a) / 1000))
        if n == 0: rows.append(row); continue
        i0 = np.argmax(m); i1 = len(m) - 1 - np.argmax(m[::-1])
        row.update(spread_med_rel=float(np.median(sp[m]) / normal), spread_max_rel=float(sp[m].max() / normal), spread_p90_rel=float(np.percentile(sp[m], 90) / normal),
                   mid_ret_atr=float((mid[i1] - mid[i0]) / atr), bid_ret_atr=float((bid[i1] - bid[i0]) / atr), ask_ret_atr=float((ask[i1] - ask[i0]) / atr),
                   range_atr=float((mid[m].max() - mid[m].min()) / atr), disp_end_atr=float((mid[i1] - ref) / atr), max_disp_atr=float(np.abs(mid[:i1 + 1] - ref).max() / atr),
                   rv_atr=float(np.sqrt(np.sum(np.diff(mid[m]) ** 2)) / atr) if n > 1 else 0.0)
        d = dmid[max(i0 - 1, 0):i1]; d = d[d != 0]
        row["tick_imbalance"] = float(d.sum() / len(d)) if len(d) else 0.0
        run = best = 0; last = 0
        for x in d:
            run = run + 1 if x == last else 1; last = x; best = max(best, run)
        row["max_consec_ticks"] = int(best)
        md = np.abs(mid[:i1 + 1] - ref).max(); row["retracement"] = float((md - abs(mid[i1] - ref)) / md) if md > 0 else 0.0
        rows.append(row)
    return rows

def normalisation_times(ev, mults=(2.0, 1.5, 1.25), sustain_ms=5000):
    """First time after which the rolling 1-s median spread stays below m x normal for sustain_ms (250 ms grid, 30 min)."""
    w = ev["w"]; normal = ev["normal"]; rel = w.rel.to_numpy(); sp = w.sp.to_numpy(); out = {}
    grid = np.arange(0, 30 * 60000, 250); med = np.full(len(grid), np.nan)
    idx = np.searchsorted(rel, grid); idx2 = np.searchsorted(rel, grid + 1000)
    for g in range(len(grid)):
        if idx2[g] > idx[g]: med[g] = np.median(sp[idx[g]:idx2[g]])
    med = pd.Series(med).ffill().to_numpy()
    for m in mults:
        ok = med < m * normal; need = sustain_ms // 250; tn = None; run = 0
        for g in range(len(ok)):
            run = run + 1 if ok[g] else 0
            if run >= need: tn = int(grid[g - need + 1]); break
        out[f"t_norm_{m}"] = tn
    return out

def first_passage(w, i_start, atr, X, horizon_ms, side, executable=True):
    """From tick i_start: +1 if +X ATR is reached before -X ATR within the horizon, -1 if the reverse, 0 if neither.
    Executable: a long enters at the ask and is measured on the bid (mirror for a short). Diagnostic: mid to mid."""
    rel = w.rel.to_numpy(); bid = w.bid.to_numpy(); ask = w.ask.to_numpy(); mid = w.mid.to_numpy()
    end = np.searchsorted(rel, rel[i_start] + horizon_ms)
    if executable:
        if side == 1: fill = ask[i_start]; up = bid[i_start:end] >= fill + X * atr; dn = bid[i_start:end] <= fill - X * atr
        else: fill = bid[i_start]; up = ask[i_start:end] <= fill - X * atr; dn = ask[i_start:end] >= fill + X * atr
    else:
        m0 = mid[i_start]; up = (mid[i_start:end] - m0) * side >= X * atr; dn = (mid[i_start:end] - m0) * side <= -X * atr
    iu = np.argmax(up) if up.any() else 10**9; idn = np.argmax(dn) if dn.any() else 10**9
    if iu == 10**9 and idn == 10**9: return 0
    return 1 if iu < idn else -1

def mfe_mae(w, i_start, atr, horizon_ms, side):
    rel = w.rel.to_numpy(); mid = w.mid.to_numpy(); end = np.searchsorted(rel, rel[i_start] + horizon_ms)
    x = (mid[i_start:end] - mid[i_start]) * side / atr
    return float(x.max()), float(x.min()), float(x[-1])

def shock_states(ev, i_norm):
    """Five candidate directional states measured in the shock, all sign-valued (0 = undefined)."""
    w = ev["w"]; rel = w.rel.to_numpy(); mid = w.mid.to_numpy(); bid = w.bid.to_numpy(); ask = w.ask.to_numpy(); atr = ev["atr"]; ref = ev["ref_mid"]
    def imb(a, b):
        m = (rel >= a) & (rel < b); d = np.sign(np.diff(mid[m])) if m.sum() > 1 else np.array([]); d = d[d != 0]
        return int(np.sign(d.sum())) if len(d) else 0
    j5 = np.searchsorted(rel, 5000) - 1
    disp_n = (mid[i_norm] - ref) / atr
    side_shift = ((ask[j5] - ask[0]) - (bid[j5] - bid[0])) if j5 >= 0 else 0.0   # ask moved more than bid: the offer was pulled
    return dict(s_disp=int(np.sign(disp_n)) if abs(disp_n) >= 0.1 else 0, s_ret5=int(np.sign(mid[j5] - ref)) if j5 >= 0 and abs(mid[j5] - ref) >= 0.05 * atr else 0,
                s_imb5=imb(0, 5000), s_imb30=imb(5000, 30000), s_side=int(np.sign(side_shift)) if abs(side_shift) >= 0.02 * atr else 0, disp_at_norm_atr=float(disp_n))

def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)

def main():
    T0 = time.time(); print(f"{len(DAYS)} development days (2025)", flush=True)
    EVENTS, BANDROWS, INFO, CONT, STATE = [], [], [], [], []
    for n_, day in enumerate(DAYS):
        t, err = R.load_day(day)
        if t is None: EVENTS.append(dict(day=str(day.date()), status="DATA_INSUFFICIENT", reason=err)); continue
        ev = event_frame(t, day)
        if ev is None: EVENTS.append(dict(day=str(day.date()), status="DATA_INSUFFICIENT", reason="pre-window or event window too thin")); continue
        w = ev["w"]; grp = "Thursday" if day.weekday() == 3 else "Friday"
        for row in band_stats(ev): BANDROWS.append(dict(day=str(day.date()), grp=grp, **row))
        nt = normalisation_times(ev)
        mid = w.mid.to_numpy(); rel = w.rel.to_numpy(); ref = ev["ref_mid"]; atr = ev["atr"]
        disp30 = mid[np.searchsorted(rel, 1800000) - 1] - ref if rel[-1] >= 1800000 else np.nan
        pd_rows = {}
        for ms in (1000, 5000, 30000, 60000, 300000, 900000, 1800000):
            j = np.searchsorted(rel, ms) - 1
            if j >= 0:
                d = mid[j] - ref; pd_rows[f"disp_{ms}"] = d / atr; pd_rows[f"same_sign_30m_{ms}"] = float(np.sign(d) == np.sign(disp30)) if not np.isnan(disp30) and d != 0 else np.nan
        rec = dict(day=str(day.date()), grp=grp, status="OK", atr=atr, normal_spread=ev["normal"], spread_at_event_rel=float(w.sp.iloc[0] / ev["normal"]), spread_max_rel=float(w.sp.max() / ev["normal"]),
                   disp30_atr=float(disp30 / atr) if not np.isnan(disp30) else np.nan, max_abs_disp30_atr=float(np.abs(mid[rel < 1800000] - ref).max() / atr), **nt, **pd_rows)
        tn = nt.get("t_norm_1.5")
        if tn is not None and tn < 25 * 60000:
            i_n = np.searchsorted(rel, tn); st = shock_states(ev, i_n); rec.update(st); rec["spread_at_norm_rel"] = float(w.sp.iloc[i_n] / ev["normal"])
            for X in (0.25, 0.5, 1.0):
                for hz in (1, 5, 15, 30, 60):
                    for side in (1, -1):
                        INFO.append(dict(day=str(day.date()), grp=grp, t_norm_ms=tn, X=X, horizon_min=hz, side=side, exec=first_passage(w, i_n, atr, X, hz * 60000, side, True), mid=first_passage(w, i_n, atr, X, hz * 60000, side, False)))
            for name in ("s_disp", "s_ret5", "s_imb5", "s_imb30", "s_side"):
                s = st[name]
                if s == 0: continue
                for hz in (5, 15, 30, 60):
                    f, a, c = mfe_mae(w, i_n, atr, hz * 60000, s)
                    for X in (0.25, 0.5, 1.0):
                        STATE.append(dict(day=str(day.date()), grp=grp, state=name, dir=s, horizon_min=hz, X=X, mid=first_passage(w, i_n, atr, X, hz * 60000, s, False), exec=first_passage(w, i_n, atr, X, hz * 60000, s, True), mfe=f, mae=a, close=c))
            if st["s_disp"] != 0:
                for hz in (5, 15, 30, 60):
                    f, a, c = mfe_mae(w, i_n, atr, hz * 60000, st["s_disp"])
                    for X in (0.25, 0.5):
                        CONT.append(dict(day=str(day.date()), grp=grp, first_dir=st["s_disp"], disp_at_norm_atr=st["disp_at_norm_atr"], horizon_min=hz, X=X, cont_mid=first_passage(w, i_n, atr, X, hz * 60000, st["s_disp"], False), cont_exec=first_passage(w, i_n, atr, X, hz * 60000, st["s_disp"], True), mfe=f, mae=a, close=c))
        EVENTS.append(rec)
        for hh, mm in CONTROL_TIMES:
            evc = event_frame(t, day, t_event=day_ms(day, hh, mm))
            if evc is None: continue
            wc = evc["w"]; i_n = 0
            for X in (0.25, 0.5, 1.0):
                for hz in (5, 15, 30):
                    for side in (1, -1):
                        INFO.append(dict(day=str(day.date()), grp=f"CONTROL {hh:02d}:{mm:02d}", t_norm_ms=0, X=X, horizon_min=hz, side=side, exec=first_passage(wc, i_n, evc["atr"], X, hz * 60000, side, True), mid=first_passage(wc, i_n, evc["atr"], X, hz * 60000, side, False)))
        if (n_ + 1) % 20 == 0: print(f"  {n_+1}/{len(DAYS)} ({time.time()-T0:.0f}s)", flush=True)

    EV = pd.DataFrame(EVENTS); BR = pd.DataFrame(BANDROWS); IN = pd.DataFrame(INFO); CO = pd.DataFrame(CONT); ST = pd.DataFrame(STATE)
    EV.to_csv(f"{OUT}/events.csv", index=False); BR.to_csv(f"{OUT}/bands.csv", index=False); IN.to_csv(f"{OUT}/information.csv", index=False); CO.to_csv(f"{OUT}/continuation.csv", index=False); ST.to_csv(f"{OUT}/states.csv", index=False)
    S = dict(generated=str(pd.Timestamp.now())[:16], days=int(len(DAYS)), ok=int((EV.status == "OK").sum()), insufficient=EV[EV.status != "OK"][["day", "reason"]].to_dict("records"), calendar="unavailable: weekday is a proxy, not an event identity")
    ok = EV[EV.status == "OK"]
    S["band_curve"] = []
    for grp in ("Thursday", "Friday", "All"):
        g = BR if grp == "All" else BR[BR.grp == grp]
        for lab in BAND_LABEL:
            b = g[g.band == lab]
            if len(b) == 0: continue
            S["band_curve"].append(dict(group=grp, band=lab, n=int(len(b)), ticks_med=float(b.ticks.median()), ticks_per_s=float(b.ticks_per_s.median()), spread_med_rel=float(b.spread_med_rel.median()), spread_max_rel=float(b.spread_max_rel.median()), spread_p90_rel=float(b.spread_p90_rel.median()),
                                        range_atr=float(b.range_atr.median()), abs_mid_ret_atr=float(b.mid_ret_atr.abs().median()), max_disp_atr=float(b.max_disp_atr.median()), retracement=float(b.retracement.median()), imbalance_abs=float(b.tick_imbalance.abs().median()), consec=float(b.max_consec_ticks.median()), rv_atr=float(b.rv_atr.median())))
    S["normalisation"] = []
    for grp in ("Thursday", "Friday", "All"):
        g = ok if grp == "All" else ok[ok.grp == grp]
        for m in (2.0, 1.5, 1.25):
            v = pd.to_numeric(g[f"t_norm_{m}"], errors="coerce") / 1000
            S["normalisation"].append(dict(group=grp, mult=m, n=int(len(g)), never_within_30min=int(v.isna().sum()), already_at_t0=int((v == 0).sum()), p25_s=float(v.quantile(.25)) if v.notna().any() else None, p50_s=float(v.median()) if v.notna().any() else None, p75_s=float(v.quantile(.75)) if v.notna().any() else None, p90_s=float(v.quantile(.9)) if v.notna().any() else None))
    S["norm_curve"] = []   # share of events normalised by elapsed time
    v15 = pd.to_numeric(ok["t_norm_1.5"], errors="coerce"); v2 = pd.to_numeric(ok["t_norm_2.0"], errors="coerce"); v125 = pd.to_numeric(ok["t_norm_1.25"], errors="coerce")
    for s in (0, 1, 2, 5, 10, 20, 30, 45, 60, 90, 120, 180, 300, 600, 900, 1800):
        S["norm_curve"].append(dict(t_s=s, share_2x=float((v2 <= s * 1000).mean()), share_15x=float((v15 <= s * 1000).mean()), share_125x=float((v125 <= s * 1000).mean())))
    S["event_stats"] = dict(spread_at_event_rel_med=float(ok.spread_at_event_rel.median()), spread_max_rel_med=float(ok.spread_max_rel.median()), normal_spread_usd_med=float(ok.normal_spread.median()), atr_med=float(ok.atr.median()), normal_spread_atr=float((ok.normal_spread / ok.atr).median()),
                            spread_at_norm_rel_med=float(ok.spread_at_norm_rel.median()), abs_disp30_atr_med=float(ok.disp30_atr.abs().median()), max_abs_disp30_med=float(ok.max_abs_disp30_atr.median()), disp_at_norm_abs_med=float(ok.disp_at_norm_atr.abs().median()))
    S["discovery"] = [dict(t_ms=ms, abs_disp_med_atr=float(ok[f"disp_{ms}"].abs().median()), share_of_30m_move=float((ok[f"disp_{ms}"].abs() / ok.disp30_atr.abs().replace(0, np.nan)).median()), same_sign_as_30m=float(ok[f"same_sign_30m_{ms}"].mean())) for ms in (1000, 5000, 30000, 60000, 300000, 900000, 1800000) if f"disp_{ms}" in ok]
    def hit_table(df, keys):
        rows = []
        for k, g in df.groupby(keys):
            ge = g[g["exec"] != 0]; gm = g[g["mid"] != 0]; lo, hi = wilson(int((gm["mid"] == 1).sum()), len(gm))
            rows.append(dict(**dict(zip(keys, k if isinstance(k, tuple) else (k,))), n=int(len(g)), hit_exec=float((ge["exec"] == 1).mean()) if len(ge) else np.nan, resolved_exec=float(len(ge) / len(g)), hit_mid=float((gm["mid"] == 1).mean()) if len(gm) else np.nan, ci_lo=lo, ci_hi=hi,
                             **({"mfe": float(g.mfe.mean()), "mae": float(g.mae.mean()), "close": float(g.close.mean())} if "mfe" in g else {})))
        return rows
    S["information"] = hit_table(IN[~IN.grp.str.startswith("CONTROL")], ["X", "horizon_min", "side"])
    S["information_by_group"] = hit_table(IN[~IN.grp.str.startswith("CONTROL")], ["grp", "X", "horizon_min", "side"])
    S["information_controls"] = hit_table(IN[IN.grp.str.startswith("CONTROL")], ["X", "horizon_min", "side"])
    S["states"] = hit_table(ST, ["state", "X", "horizon_min"]) if len(ST) else []
    S["states_by_group"] = hit_table(ST, ["grp", "state", "X", "horizon_min"]) if len(ST) else []
    S["continuation"] = []
    for (hz, X), g in CO.groupby(["horizon_min", "X"]):
        gm = g[g.cont_mid != 0]; ge = g[g.cont_exec != 0]; lo, hi = wilson(int((gm.cont_mid == 1).sum()), len(gm))
        S["continuation"].append(dict(horizon_min=hz, X=X, n=int(len(g)), up_first=float((g.first_dir == 1).mean()), cont_mid=float((gm.cont_mid == 1).mean()) if len(gm) else np.nan, ci_lo=lo, ci_hi=hi, cont_exec=float((ge.cont_exec == 1).mean()) if len(ge) else np.nan, resolved=float(len(gm) / len(g)),
                                      disp_at_norm_med=float(g.disp_at_norm_atr.abs().median()), mfe=float(g.mfe.mean()), mae=float(g.mae.mean()), close=float(g.close.mean())))
    json.dump(S, open(f"{OUT}/summary.json", "w"), indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else (float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x)))))
    pd.set_option("display.width", 250)
    print("\nEVENT STATS:", {k: round(v, 3) for k, v in S["event_stats"].items()})
    print("\nNORMALISATION TIMES (s):"); print(pd.DataFrame(S["normalisation"]).round(1).to_string(index=False))
    print("\nDISCOVERY:"); print(pd.DataFrame(S["discovery"]).round(3).to_string(index=False))
    print("\nSTATES (mid hit rate in the state's direction from the 1.5x normalisation time):")
    st = pd.DataFrame(S["states"]); print(st[st.X.isin([0.5, 1.0]) & st.horizon_min.isin([15, 30])].round(3).to_string(index=False))
    print("\nCONTINUATION:"); print(pd.DataFrame(S["continuation"]).round(3).to_string(index=False))
    print(f"done ({time.time()-T0:.0f}s)")

if __name__ == "__main__":
    main()
