"""Phase 15, step 2 (development 2025 only): Track B (does the post-normalisation window carry more realised movement
than a same-day control?), and the two-sided executable candidates that the brief allows without a directional
premise: an OCO breakout placed after the release (delay bands 0-120 s and the empirical normalisation time) and the
delayed breakout of the first-minute shock range. Fills at the triggering quote (Phase 14 Scenario A, the most
favourable), stop = the opposite trigger, horizon 30 minutes, exits at the last executable quote. Cost scenarios
scale the half-spread around the mid: 0 (mid to mid, diagnostic), 1, 1.25, 1.5, 2. The pullback candidate is not
built: its precondition (continuation of the first clean move > 50% on mid) failed in step 1.
"""
import json, math, os, time
import numpy as np, pandas as pd
import release_straddle_ticks as R
from post_release_ticks import DAYS, OUT, CONTROL_TIMES, day_ms, event_frame, normalisation_times

KS = (0.25, 0.5, 0.75); TS = (0.75, 1.0, 1.5); STARTS = ("0 s", "15 s", "30 s", "60 s", "120 s", "t_norm 1.5x", "t_norm 1.25x"); COSTS = (0.0, 1.0, 1.25, 1.5, 2.0); H_MS = 30 * 60000

def quotes(w, sp_mult):
    mid = w.mid.to_numpy(); half = (w.ask.to_numpy() - w.bid.to_numpy()) / 2 * sp_mult
    return w.rel.to_numpy(), mid, mid - half, mid + half

def oco(w, i_start, atr, k, T, sp_mult=1.0, levels=None, H=H_MS):
    rel, mid, bid, ask = quotes(w, sp_mult)
    end = np.searchsorted(rel, rel[i_start] + H)
    if end - i_start < 2: return dict(outcome="no_data", net=0.0, side=0)
    m0 = mid[i_start]; up_lvl, dn_lvl = (m0 + k * atr, m0 - k * atr) if levels is None else levels
    a = ask[i_start:end]; b = bid[i_start:end]
    hu = a >= up_lvl; hd = b <= dn_lvl
    iu = int(np.argmax(hu)) if hu.any() else 10**9; idn = int(np.argmax(hd)) if hd.any() else 10**9
    if iu == 10**9 and idn == 10**9: return dict(outcome="no_trigger", net=0.0, side=0)
    if iu == idn: return dict(outcome="both_same_tick", net=float(-(a[iu] - dn_lvl) / atr), side=0, t_trigger=int(rel[i_start + iu] - rel[i_start]))
    if iu < idn:
        fill = a[iu]; bb = b[iu:]; tg = bb >= fill + T * atr; sl = bb <= dn_lvl
        it = int(np.argmax(tg)) if tg.any() else 10**9; isl = int(np.argmax(sl)) if sl.any() else 10**9
        if it == 10**9 and isl == 10**9: return dict(outcome="timeout", net=float((bb[-1] - fill) / atr), side=1, t_trigger=int(rel[i_start + iu] - rel[i_start]))
        if it < isl: return dict(outcome="target", net=float((bb[it] - fill) / atr), side=1, t_trigger=int(rel[i_start + iu] - rel[i_start]))
        return dict(outcome="stop", net=float((bb[isl] - fill) / atr), side=1, t_trigger=int(rel[i_start + iu] - rel[i_start]))
    fill = b[idn]; aa = a[idn:]; tg = aa <= fill - T * atr; sl = aa >= up_lvl
    it = int(np.argmax(tg)) if tg.any() else 10**9; isl = int(np.argmax(sl)) if sl.any() else 10**9
    if it == 10**9 and isl == 10**9: return dict(outcome="timeout", net=float((fill - aa[-1]) / atr), side=-1, t_trigger=int(rel[i_start + idn] - rel[i_start]))
    if it < isl: return dict(outcome="target", net=float((fill - aa[it]) / atr), side=-1, t_trigger=int(rel[i_start + idn] - rel[i_start]))
    return dict(outcome="stop", net=float((fill - aa[isl]) / atr), side=-1, t_trigger=int(rel[i_start + idn] - rel[i_start]))

def either_side(w, i_start, atr, X, H=H_MS):
    """Time (ms) until |mid - mid0| >= X ATR within H, or None."""
    rel = w.rel.to_numpy(); mid = w.mid.to_numpy(); end = np.searchsorted(rel, rel[i_start] + H)
    hit = np.abs(mid[i_start:end] - mid[i_start]) >= X * atr
    return int(rel[i_start + int(np.argmax(hit))] - rel[i_start]) if hit.any() else None

def main():
    T0 = time.time(); TRADES, TRACKB = [], []
    for n_, day in enumerate(DAYS):
        t, err = R.load_day(day)
        if t is None: continue
        ev = event_frame(t, day)
        if ev is None: continue
        w = ev["w"]; rel = w.rel.to_numpy(); atr = ev["atr"]; grp = "Thursday" if day.weekday() == 3 else "Friday"; nt = normalisation_times(ev)
        starts = {"0 s": 0, "15 s": 15000, "30 s": 30000, "60 s": 60000, "120 s": 120000, "t_norm 1.5x": nt["t_norm_1.5"], "t_norm 1.25x": nt["t_norm_1.25"]}
        for name, ms in starts.items():
            if ms is None or ms >= 25 * 60000: continue
            i = int(np.searchsorted(rel, ms))
            for k in KS:
                for T in TS:
                    for c in (COSTS if name == "t_norm 1.5x" else (1.0,)):
                        TRADES.append(dict(day=str(day.date()), grp=grp, family="OCO after release", start=name, start_ms=ms, k=k, T=T, cost=c, **oco(w, i, atr, k, T, c)))
            if name in ("t_norm 1.5x", "0 s"):
                for X in (0.5, 1.0, 1.5, 2.0):
                    TRACKB.append(dict(day=str(day.date()), grp=grp, start=name, X=X, t_ms=either_side(w, i, atr, X)))
                mid = w.mid.to_numpy(); end = np.searchsorted(rel, ms + H_MS)
                TRACKB.append(dict(day=str(day.date()), grp=grp, start=name, X=0, t_ms=None, range_atr=float((mid[i:end].max() - mid[i:end].min()) / atr)))
        # delayed breakout of the first-minute shock range, placed at max(60 s, t_norm 1.5x)
        m60 = rel < 60000; hi, lo = w.mid.to_numpy()[m60].max(), w.mid.to_numpy()[m60].min(); width = (hi - lo) / atr
        ms = max(60000, nt["t_norm_1.5"] or 0)
        if ms < 25 * 60000:
            i = int(np.searchsorted(rel, ms))
            for tname, T in (("1R (range width)", width), ("0.75 ATR", 0.75), ("1.5 ATR", 1.5)):
                for c in (0.0, 1.0, 1.5):
                    TRADES.append(dict(day=str(day.date()), grp=grp, family="Shock-range breakout", start="max(60 s, t_norm)", start_ms=ms, k=width, T=T, cost=c, target_name=tname, **oco(w, i, atr, 0, T, c, levels=(hi, lo))))
        # controls: identical rules at 16:30 and 17:15 on the same day (no release, spread normal)
        for hh, mm in CONTROL_TIMES:
            evc = event_frame(t, day, t_event=day_ms(day, hh, mm))
            if evc is None: continue
            wc = evc["w"]; relc = wc.rel.to_numpy(); atrc = evc["atr"]; cname = f"CONTROL {hh:02d}:{mm:02d}"
            for k in KS:
                for T in TS:
                    for c in (0.0, 1.0):
                        TRADES.append(dict(day=str(day.date()), grp=cname, family="OCO after release", start="control", start_ms=0, k=k, T=T, cost=c, **oco(wc, 0, atrc, k, T, c)))
            for X in (0.5, 1.0, 1.5, 2.0):
                TRACKB.append(dict(day=str(day.date()), grp=cname, start="control", X=X, t_ms=either_side(wc, 0, atrc, X)))
            midc = wc.mid.to_numpy(); end = np.searchsorted(relc, H_MS)
            TRACKB.append(dict(day=str(day.date()), grp=cname, start="control", X=0, t_ms=None, range_atr=float((midc[:end].max() - midc[:end].min()) / atrc)))
            m60 = relc < 60000; hi, lo = midc[m60].max(), midc[m60].min(); width = (hi - lo) / atrc; i = int(np.searchsorted(relc, 60000))
            for tname, T in (("1R (range width)", width), ("0.75 ATR", 0.75), ("1.5 ATR", 1.5)):
                TRADES.append(dict(day=str(day.date()), grp=cname, family="Shock-range breakout", start="control", start_ms=60000, k=width, T=T, cost=1.0, target_name=tname, **oco(wc, i, atrc, 0, T, 1.0, levels=(hi, lo))))
        if (n_ + 1) % 20 == 0: print(f"  {n_+1}/{len(DAYS)} ({time.time()-T0:.0f}s)", flush=True)
    TR = pd.DataFrame(TRADES); TB = pd.DataFrame(TRACKB)
    TR.to_csv(f"{OUT}/candidate_trades.csv", index=False); TB.to_csv(f"{OUT}/trackb.csv", index=False)
    def agg(g):
        tr = g[g.side != 0]; w_ = tr[tr.net > 0].net.sum(); l_ = -tr[tr.net < 0].net.sum()
        return dict(n=int(len(g)), triggered=float((g.side != 0).mean()), target=float((g.outcome == "target").mean()), stop=float((g.outcome == "stop").mean()), timeout=float((g.outcome == "timeout").mean()), both_same_tick=float((g.outcome == "both_same_tick").mean()),
                    net=float(g.net.mean()), se=float(g.net.std() / math.sqrt(len(g))) if len(g) > 1 else np.nan, pf=float(w_ / l_) if l_ > 0 else np.nan, t_trigger_med_s=float(g.t_trigger.median() / 1000) if "t_trigger" in g and g.t_trigger.notna().any() else np.nan)
    S = dict(generated=str(pd.Timestamp.now())[:16])
    E = TR[(TR.family == "OCO after release") & ~TR.grp.str.startswith("CONTROL")]
    S["oco_matrix"] = [dict(start=s, k=k, T=T, **agg(g)) for (s, k, T), g in E[E.cost == 1.0].groupby(["start", "k", "T"])]
    S["oco_cost"] = [dict(k=k, T=T, cost=c, **agg(g)) for (k, T, c), g in E[E.start == "t_norm 1.5x"].groupby(["k", "T", "cost"])]
    S["oco_by_group"] = [dict(grp=gr, k=k, T=T, **agg(g)) for (gr, k, T), g in E[(E.cost == 1.0) & (E.start == "t_norm 1.5x")].groupby(["grp", "k", "T"])]
    C = TR[(TR.family == "OCO after release") & TR.grp.str.startswith("CONTROL")]
    S["oco_controls"] = [dict(k=k, T=T, cost=c, **agg(g)) for (k, T, c), g in C.groupby(["k", "T", "cost"])]
    Sh = TR[TR.family == "Shock-range breakout"]
    S["shock_breakout"] = [dict(group="events" if not gr.startswith("CONTROL") else "controls", target_name=tn, cost=c, width_med=float(g.k.median()), **agg(g)) for (gr, tn, c), g in Sh.assign(gr=np.where(Sh.grp.str.startswith("CONTROL"), "CONTROL", "events")).groupby(["gr", "target_name", "cost"])]
    S["trackb"] = []
    for (s, X), g in TB[TB.X > 0].groupby(["start", "X"]):
        v = pd.to_numeric(g.t_ms, errors="coerce") / 1000
        S["trackb"].append(dict(start=s, X=X, n=int(len(g)), reached_30min=float(v.notna().mean()), t_med_s=float(v.median()) if v.notna().any() else None, t_p75_s=float(v.quantile(.75)) if v.notna().any() else None))
    S["trackb_range"] = [dict(start=s, n=int(len(g)), range_30min_med_atr=float(g.range_atr.median()), range_p25=float(g.range_atr.quantile(.25)), range_p75=float(g.range_atr.quantile(.75))) for s, g in TB[TB.X == 0].groupby("start")]
    S["pullback"] = "not built: continuation of the first clean move was 45-49% on mid in step 1 (precondition > 50% failed)"
    json.dump(S, open(f"{OUT}/candidates.json", "w"), indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else (float(x) if isinstance(x, np.floating) else (int(x) if isinstance(x, np.integer) else str(x))))
    pd.set_option("display.width", 250)
    print("\nTRACK B: time to |move| >= X ATR (events from normalisation vs controls):"); print(pd.DataFrame(S["trackb"]).round(3).to_string(index=False)); print(pd.DataFrame(S["trackb_range"]).round(3).to_string(index=False))
    M = pd.DataFrame(S["oco_matrix"]); print("\nOCO NET ATR/attempt by start (rows) and k/T (cols):"); print(M.pivot_table(index="start", columns=["k", "T"], values="net").round(2).to_string())
    print("\nOCO CONTROLS:"); print(pd.DataFrame(S["oco_controls"]).round(3).to_string(index=False))
    print("\nOCO COST at t_norm 1.5x:"); print(pd.DataFrame(S["oco_cost"]).pivot_table(index=["k", "T"], columns="cost", values="net").round(2).to_string())
    print("\nSHOCK-RANGE BREAKOUT:"); print(pd.DataFrame(S["shock_breakout"]).round(3).to_string(index=False))
    print(f"done ({time.time()-T0:.0f}s)")

if __name__ == "__main__":
    main()
