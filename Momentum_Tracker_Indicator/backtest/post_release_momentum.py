"""Phase 15, step 3 (development 2025 only): delayed momentum after the release. At each delay band the direction is the
sign of the displacement from the pre-release reference (ignored below 0.1 ATR); entry at the executable quote (ask for
a buy, bid for a sell), hold 5/15/30/60 minutes, exit at the executable quote, no stop; a second version stops at a
1-ATR executable loss. Controls: the same rule at 16:30 and 17:15 with the direction read from the preceding 60 s.
Retention rule, declared before the run: a cell counts only if net > 0 at one spread with |t| >= 2 AND both
neighbouring delay bands at the same hold are also positive (a plateau, not a peak). Nothing here touches 2026.
"""
import json, math, os, time
import numpy as np, pandas as pd
import release_straddle_ticks as R
from post_release_ticks import DAYS, OUT, CONTROL_TIMES, day_ms, event_frame, normalisation_times

HOLDS = (5, 15, 30, 60); START_ORDER = ["15 s", "30 s", "60 s", "90 s", "120 s", "t_norm 1.5x", "t_norm 1.25x"]

def run(w, i, ref, atr, hold_min, sp_mult=1.0, stop_atr=None):
    rel = w.rel.to_numpy(); mid = w.mid.to_numpy(); half = (w.ask.to_numpy() - w.bid.to_numpy()) / 2 * sp_mult; bid = mid - half; ask = mid + half
    d = np.sign(mid[i] - ref)
    if abs(mid[i] - ref) < 0.1 * atr or d == 0: return None
    j = int(np.searchsorted(rel, rel[i] + hold_min * 60000)) - 1
    if j <= i: return None
    if d > 0:
        fill = ask[i]; path = bid[i:j + 1]
        if stop_atr is not None:
            s = path <= fill - stop_atr * atr
            if s.any(): j = i + int(np.argmax(s)); return dict(dir=1, gross=float((mid[j] - mid[i]) / atr), net=float((bid[j] - fill) / atr), stopped=True)
        return dict(dir=1, gross=float((mid[j] - mid[i]) / atr), net=float((bid[j] - fill) / atr), stopped=False)
    fill = bid[i]; path = ask[i:j + 1]
    if stop_atr is not None:
        s = path >= fill + stop_atr * atr
        if s.any(): j = i + int(np.argmax(s)); return dict(dir=-1, gross=float((mid[i] - mid[j]) / atr), net=float((fill - ask[j]) / atr), stopped=True)
    return dict(dir=-1, gross=float((mid[i] - mid[j]) / atr), net=float((fill - ask[j]) / atr), stopped=False)

def main():
    T0 = time.time(); ROWS = []
    for n_, day in enumerate(DAYS):
        t, err = R.load_day(day)
        if t is None: continue
        ev = event_frame(t, day, minutes=65)
        if ev is None: continue
        w = ev["w"]; rel = w.rel.to_numpy(); atr = ev["atr"]; ref = ev["ref_mid"]; grp = "Thursday" if day.weekday() == 3 else "Friday"; nt = normalisation_times(ev)
        starts = {"15 s": 15000, "30 s": 30000, "60 s": 60000, "90 s": 90000, "120 s": 120000, "t_norm 1.5x": nt["t_norm_1.5"], "t_norm 1.25x": nt["t_norm_1.25"]}
        for name, ms in starts.items():
            if ms is None or ms >= 25 * 60000: continue
            i = int(np.searchsorted(rel, ms))
            for h in HOLDS:
                for c in (0.0, 1.0, 1.5, 2.0):
                    r = run(w, i, ref, atr, h, c)
                    if r: ROWS.append(dict(day=str(day.date()), grp=grp, start=name, hold=h, cost=c, variant="no stop", **r))
                r = run(w, i, ref, atr, h, 1.0, stop_atr=1.0)
                if r: ROWS.append(dict(day=str(day.date()), grp=grp, start=name, hold=h, cost=1.0, variant="stop 1 ATR", **r))
        for hh, mm in CONTROL_TIMES:
            evc = event_frame(t, day, t_event=day_ms(day, hh, mm), minutes=65)
            if evc is None: continue
            wc = evc["w"]; relc = wc.rel.to_numpy(); i = int(np.searchsorted(relc, 60000)); cname = f"CONTROL {hh:02d}:{mm:02d}"
            for h in HOLDS:
                for c in (0.0, 1.0):
                    r = run(wc, i, evc["ref_mid"], evc["atr"], h, c)
                    if r: ROWS.append(dict(day=str(day.date()), grp=cname, start="control +60 s", hold=h, cost=c, variant="no stop", **r))
                r = run(wc, i, evc["ref_mid"], evc["atr"], h, 1.0, stop_atr=1.0)
                if r: ROWS.append(dict(day=str(day.date()), grp=cname, start="control +60 s", hold=h, cost=1.0, variant="stop 1 ATR", **r))
        if (n_ + 1) % 20 == 0: print(f"  {n_+1}/{len(DAYS)} ({time.time()-T0:.0f}s)", flush=True)
    D = pd.DataFrame(ROWS); D.to_csv(f"{OUT}/momentum_trades.csv", index=False)
    def agg(g):
        w_ = g[g.net > 0].net.sum(); l_ = -g[g.net < 0].net.sum(); se = float(g.net.std() / math.sqrt(len(g))) if len(g) > 1 else np.nan
        return dict(n=int(len(g)), long_share=float((g.dir == 1).mean()), hit=float((g.net > 0).mean()), gross=float(g.gross.mean()), net=float(g.net.mean()), se=se, t=float(g.net.mean() / se) if se and se > 0 else np.nan, pf=float(w_ / l_) if l_ > 0 else np.nan, stopped=float(g.stopped.mean()))
    E = D[~D.grp.str.startswith("CONTROL")]; C = D[D.grp.str.startswith("CONTROL")]
    S = dict(generated=str(pd.Timestamp.now())[:16], retention_rule="net > 0 at cost 1.0 with |t| >= 2 and both neighbouring delay bands positive at the same hold")
    S["grid"] = [dict(start=s, hold=h, cost=c, variant=v, **agg(g)) for (s, h, c, v), g in E.groupby(["start", "hold", "cost", "variant"])]
    S["by_group"] = [dict(grp=gr, start=s, hold=h, **agg(g)) for (gr, s, h), g in E[(E.cost == 1.0) & (E.variant == "no stop")].groupby(["grp", "start", "hold"])]
    S["controls"] = [dict(hold=h, cost=c, variant=v, **agg(g)) for (h, c, v), g in C.groupby(["hold", "cost", "variant"])]
    # retention check on the no-stop, cost 1.0 grid
    G = pd.DataFrame(S["grid"]); G1 = G[(G.cost == 1.0) & (G.variant == "no stop")].set_index(["start", "hold"])
    kept = []
    for h in HOLDS:
        for k, s in enumerate(START_ORDER[:5]):       # the timed bands form the plateau axis; t_norm rows are reported but have no neighbours
            if (s, h) not in G1.index: continue
            r = G1.loc[(s, h)]; nb = [START_ORDER[k - 1] if k > 0 else None, START_ORDER[k + 1] if k < 4 else None]
            nb_ok = all((x is None) or ((x, h) in G1.index and G1.loc[(x, h)].net > 0) for x in nb)
            if r.net > 0 and abs(r.t) >= 2 and nb_ok: kept.append(dict(start=s, hold=h, net=float(r.net), t=float(r.t)))
    S["retained"] = kept
    json.dump(S, open(f"{OUT}/momentum.json", "w"), indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else (float(x) if isinstance(x, np.floating) else (int(x) if isinstance(x, np.integer) else (bool(x) if isinstance(x, np.bool_) else str(x)))))
    pd.set_option("display.width", 250)
    print("\nDELAYED MOMENTUM, net ATR per trade at one spread, no stop (rows: delay band, cols: hold min):")
    print(G1.reset_index().pivot_table(index="start", columns="hold", values="net").reindex(START_ORDER).round(3).to_string())
    print("\nt-statistics:"); print(G1.reset_index().pivot_table(index="start", columns="hold", values="t").reindex(START_ORDER).round(2).to_string())
    print("\ngross (mid to mid):"); print(G[(G.cost == 0.0)].pivot_table(index="start", columns="hold", values="net").reindex(START_ORDER).round(3).to_string())
    print("\nwith a 1-ATR stop:"); print(G[(G.variant == "stop 1 ATR")].pivot_table(index="start", columns="hold", values="net").reindex(START_ORDER).round(3).to_string())
    print("\nCONTROLS:"); print(pd.DataFrame(S["controls"]).round(3).to_string(index=False))
    print("\nRETAINED:", kept); print(f"done ({time.time()-T0:.0f}s)")

if __name__ == "__main__":
    main()
