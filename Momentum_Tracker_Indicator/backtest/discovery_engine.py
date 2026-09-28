"""Phase 12: edge discovery engine. Events -> forward outcome distribution -> ledger, with the anti-overfitting protocol.

Everything is measured on the event timeframe's own ATR(14): P(+X before -X) for several X, MFE/MAE at several
horizons, expectancy and profit factor after XM's spread, split DEV / VAL / OOS and by year. Hypotheses are
defined once with their default parameters (no threshold search) and go into a permanent ledger with a status.
"""
import json, math, os, time
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
import twk_engine as E

T0 = time.time()
os.makedirs("results/discovery", exist_ok=True)
POINT = 0.01
PERIODS = {"DEV": (pd.Timestamp("2021-09-01"), pd.Timestamp("2024-01-01")), "VAL": (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), "OOS": (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-25"))}
SHAPES = [(0.25, 0.25), (0.5, 0.5), (1.0, 1.0), (1.0, 2.0)]        # (stop, target) in ATR units
LEV = sorted({x for s in SHAPES for x in s})                      # 0.25, 0.5, 1.0, 2.0
HORIZ = [5, 10, 20, 30, 50, 100]                                  # event-TF bars

# ------------------------------------------------------------------ data
m1 = pd.read_csv("data/XAUUSD_M1_servertime.csv.gz", parse_dates=["time"])
m1_t = (m1["time"].astype("int64") // 10**9).to_numpy(); m1_o = m1["open"].to_numpy(float); m1_h = m1["high"].to_numpy(float); m1_l = m1["low"].to_numpy(float); m1_c = m1["close"].to_numpy(float)
spread_pts = np.array([E.year_spread_model()[y] for y in m1["time"].dt.year.to_numpy()], float); SPR = spread_pts * POINT

def base_frame(tf):
    d = E.resample(m1, tf).reset_index(drop=True)
    o, h, l, c, v = (d[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume"))
    d["atr"] = E.rma(E.true_range(h, l, c, True), 14)
    d["rng"] = h - l; d["body"] = c - o; d["dir"] = np.sign(c - o)
    d["t"] = d["time"].astype("int64") // 10**9
    d["hour"] = d["time"].dt.hour; d["day"] = d["time"].dt.floor("D"); d["year"] = d["time"].dt.year
    d["session"] = pd.cut(d["hour"], [-1, 0, 9, 14, 19, 23], labels=["rollover", "asia", "london", "overlap", "ny"]).astype(str)
    d["vol_ma20"] = pd.Series(v).rolling(20).mean().to_numpy()
    d["sma20"] = pd.Series(c).rolling(20).mean().to_numpy(); d["std20"] = pd.Series(c).rolling(20).std().to_numpy()
    d["bbw_atr"] = 4 * d["std20"] / d["atr"]
    d["atr_pct100"] = pd.Series(d["atr"]).rolling(100).rank(pct=True).to_numpy()
    d["bbw_pct100"] = pd.Series(d["bbw_atr"]).rolling(100).rank(pct=True).to_numpy()
    hw = sliding_window_view(h, 20); lw = sliding_window_view(l, 20)
    d["hi20"] = np.concatenate([np.full(20, np.nan), hw[:-1].max(axis=1)]); d["lo20"] = np.concatenate([np.full(20, np.nan), lw[:-1].min(axis=1)])
    # daily context
    g = d.groupby("day")
    d["day_hi"] = g["high"].cummax().to_numpy(); d["day_lo"] = g["low"].cummin().to_numpy()
    dh = g["high"].max(); dl = g["low"].min(); dc = g["close"].last()
    days = pd.Series(sorted(d["day"].unique())); prev = dict(zip(days, days.shift(1)))
    pdm = d["day"].map(prev)
    d["pdh"] = pdm.map(dh).to_numpy(); d["pdl"] = pdm.map(dl).to_numpy(); d["pdc"] = pdm.map(dc).to_numpy()
    d["datr"] = pdm.map((dh - dl).rolling(14).mean()).to_numpy()
    pv = (c * v); d["vwap"] = (pd.Series(pv).groupby(d["day"]).cumsum() / pd.Series(v).groupby(d["day"]).cumsum().replace(0, np.nan)).to_numpy()
    # session ranges (server time): asia 01-09, london 10-14, ny 15-23; opening ranges 10:00-10:14 and 15:00-15:14
    for nm, (a, b) in {"asia": (1, 9), "london": (10, 14)}.items():
        m = (d["hour"] >= a) & (d["hour"] <= b)
        sh = d[m].groupby("day")["high"].max(); sl = d[m].groupby("day")["low"].min()
        d[f"{nm}_hi"] = d["day"].map(sh).to_numpy(); d[f"{nm}_lo"] = d["day"].map(sl).to_numpy()
    for nm, hr in {"or_london": 10, "or_ny": 15}.items():
        m = (d["hour"] == hr) & (d["time"].dt.minute < 15)
        d[f"{nm}_hi"] = d["day"].map(d[m].groupby("day")["high"].max()).to_numpy(); d[f"{nm}_lo"] = d["day"].map(d[m].groupby("day")["low"].min()).to_numpy()
    # pivots (5 bars) for equal highs/lows
    _, _, plBar, phBar = E.pivots(h, l, 5, 5)
    d["ph_val"] = np.where(phBar >= 0, h[np.maximum(phBar, 0)], np.nan); d["pl_val"] = np.where(plBar >= 0, l[np.maximum(plBar, 0)], np.nan)
    def prev_distinct(vals, bars):
        out = np.full(len(vals), np.nan); lb = -1; lv = np.nan; pv_ = np.nan
        for i in range(len(vals)):
            if bars[i] != lb: pv_, lv, lb = lv, vals[i], bars[i]
            out[i] = pv_
        return out
    d["ph_prev"] = prev_distinct(d["ph_val"].to_numpy(), phBar); d["pl_prev"] = prev_distinct(d["pl_val"].to_numpy(), plBar)
    # consecutive same-direction candles
    dr = d["dir"].to_numpy(); run = np.zeros(len(dr), int)
    for i in range(1, len(dr)):
        run[i] = run[i - 1] + 1 if dr[i] != 0 and dr[i] == dr[i - 1] else (1 if dr[i] != 0 else 0)
    d["run"] = run
    # 30-bar move in ATR and 3-bar move
    d["mv30"] = (c - np.roll(c, 30)) / d["atr"]; d.loc[:30, "mv30"] = np.nan
    d["mv3"] = (c - np.roll(c, 3)) / d["atr"]; d.loc[:3, "mv3"] = np.nan
    # states
    comp = d["bbw_pct100"] <= 0.2
    expn = (d["rng"] >= 2 * d["atr"]) | (d["atr"] / pd.Series(d["atr"]).shift(10) >= 1.3)
    _, _, adx = E.dmi(h, l, c, 14, 14); d["adx"] = adx
    trend = (d["mv30"].abs() >= 3) & (d["adx"] >= 25)
    climax = (d["rng"] >= 2 * d["atr"]) & (v >= 2 * d["vol_ma20"])
    d["state"] = np.select([comp, trend & climax, trend, expn], ["COMPRESSION", "EXHAUSTION", "TREND", "EXPANSION"], "RANGE")
    return d

# ------------------------------------------------------------------ outcome measurement
def scan_events(t_event, side, unit, H_bars, tf_min, cost_mult=1.0):
    """Entry at the next M1 open after the event bar close. Returns first-passage times (M1 bars) to +/-L x unit, MFE/MAE at horizons, end pnl."""
    k0 = np.searchsorted(m1_t, t_event + tf_min * 60, side="left")
    N = len(k0); H = H_bars * tf_min; Lv = np.array(LEV)
    t_fav = np.full((N, len(LEV)), H, np.int32); t_adv = np.full((N, len(LEV)), H, np.int32); endp = np.full(N, np.nan); valid = np.zeros(N, bool)
    mfe = np.full((N, len(HORIZ)), np.nan); mae = np.full((N, len(HORIZ)), np.nan); hz = [x * tf_min for x in HORIZ]
    spr = SPR * cost_mult
    for i in range(N):
        k = int(k0[i]); u = unit[i]
        if k < 1 or k + 3 >= len(m1_t) or math.isnan(u) or u <= 0: continue
        e = min(k + H, len(m1_t)); hh = m1_h[k:e]; ll = m1_l[k:e]; s = spr[k:e]
        fill = m1_o[k] + (spr[k] if side[i] == 1 else 0.0)
        fav = (hh - fill) if side[i] == 1 else (fill - (ll + s)); adv = (fill - ll) if side[i] == 1 else ((hh + s) - fill)
        cf = np.maximum.accumulate(fav); ca = np.maximum.accumulate(adv); lv = Lv * u; m = len(cf)
        tf = np.searchsorted(cf, lv, side="left"); ta = np.searchsorted(ca, lv, side="left")
        t_fav[i] = np.where(tf < m, tf, H); t_adv[i] = np.where(ta < m, ta, H)
        for j, x in enumerate(hz):
            if x - 1 < m: mfe[i, j] = cf[x - 1] / u; mae[i, j] = ca[x - 1] / u
        last = e - 1; endp[i] = ((m1_c[last] - fill) if side[i] == 1 else (fill - (m1_c[last] + spr[last]))) / u; valid[i] = True
    return dict(t_fav=t_fav, t_adv=t_adv, endp=endp, valid=valid, mfe=mfe, mae=mae, H=H)

def shape_r(res, S, T):
    iS, iT = LEV.index(S), LEV.index(T); tf, ta = res["t_fav"][:, iT], res["t_adv"][:, iS]
    hit = (tf < ta) & (tf < res["H"]); stopped = (ta <= tf) & (ta < res["H"])
    r = np.where(hit, T / S, np.where(stopped, -1.0, res["endp"] / S)); return np.where(res["valid"], r, np.nan), hit, stopped

def bootstrap_ci(r, n_boot=1000, seed=1):
    r = r[~np.isnan(r)]
    if len(r) < 20: return (np.nan, np.nan)
    rng = np.random.default_rng(seed); b = rng.choice(r, size=(n_boot, len(r)), replace=True).mean(axis=1); return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))

def period_metrics(res, resg, mask):
    out = {}
    for (S, T) in SHAPES:
        r, hit, st = shape_r(res, S, T); rg, hg, _ = shape_r(resg, S, T)
        rr = r[mask]; rr = rr[~np.isnan(rr)]; hh = hit[mask & res["valid"]]; hgg = hg[mask & resg["valid"]]
        key = f"{S}x{T}"
        if len(rr) == 0: out[key] = dict(n=0); continue
        gp = rr[rr > 0].sum(); gl = -rr[rr < 0].sum(); p = float(hh.mean()); pg = float(hgg.mean())
        z = (pg - 0.5) / math.sqrt(0.25 / max(1, len(hgg))) if S == T else (pg - S / (S + T)) / math.sqrt(pg * (1 - pg) / max(1, len(hgg)) + 1e-12)
        lo, hi = bootstrap_ci(rr)
        out[key] = dict(n=int(len(rr)), hit_net=round(p, 3), hit_gross=round(pg, 3), exp_net=round(float(rr.mean()), 3), exp_gross=round(float(np.nanmean(rg[mask])), 3),
                        pf=round(float(gp / gl), 2) if gl > 0 else 9.99, z_gross=round(float(z), 2), ci_lo=round(lo, 3), ci_hi=round(hi, 3))
    mf = res["mfe"][mask]; ma = res["mae"][mask]
    out["mfe_mae"] = {str(h): dict(mfe_med=round(float(np.nanmedian(mf[:, j])), 3), mae_med=round(float(np.nanmedian(ma[:, j])), 3), share_mfe_gt=round(float(np.nanmean(mf[:, j] > ma[:, j])), 3)) for j, h in enumerate(HORIZ) if np.isfinite(mf[:, j]).any()}
    return out

# ------------------------------------------------------------------ ledger
LEDGER = []
def evaluate(name, family, description, ev, d, tf_min, direction="with", params=None, H_bars=100, primary="1.0x2.0", diag_only=False):
    """ev: DataFrame with columns i (event-TF bar index), side (+1/-1), first (bool). Evaluates with and against the event direction."""
    if ev is None or len(ev) == 0:
        LEDGER.append(dict(hypothesis=name, family=family, description=description, direction=direction, params=json.dumps(params or {}), n=0, status="DATA_INSUFFICIENT")); return None
    ev = ev.drop_duplicates("i").sort_values("i").reset_index(drop=True)
    i = ev["i"].to_numpy(); side = ev["side"].to_numpy() * (1 if direction == "with" else -1)
    t_ev = d["t"].to_numpy()[i]; unit = d["atr"].to_numpy()[i]
    res = scan_events(t_ev, side, unit, H_bars, tf_min, 1.0); resg = scan_events(t_ev, side, unit, H_bars, tf_min, 0.0)
    times = pd.to_datetime(t_ev, unit="s"); per = np.select([times < PERIODS["DEV"][1], times < PERIODS["VAL"][1]], ["DEV", "VAL"], "OOS")
    M = {p: period_metrics(res, resg, per == p) for p in ("DEV", "VAL", "OOS")}; M["ALL"] = period_metrics(res, resg, np.ones(len(i), bool))
    r, hit, _ = shape_r(res, *[float(x) for x in primary.split("x")])
    years = pd.Series(times).dt.year.to_numpy(); by_year = {int(y): dict(n=int((years == y).sum()), exp=round(float(np.nanmean(r[years == y])), 3)) for y in sorted(set(years)) if (years == y).sum() >= 20}
    row = dict(hypothesis=name, family=family, description=description, direction=direction, params=json.dumps(params or {}), tf=f"M{tf_min}", n=int(res["valid"].sum()),
               first_share=round(float(ev["first"].mean()), 2) if "first" in ev else None, by_year=by_year, metrics=M, r_primary=r, side=side, times=times, ev=ev)
    # status by the protocol on the primary shape
    def g(p, k): return M[p].get(primary, {}).get(k)
    n_dev, n_val, n_oos = (M[p].get(primary, {}).get("n", 0) for p in ("DEV", "VAL", "OOS"))
    if n_dev < 200 or n_val < 50 or n_oos < 100: status = "DATA_INSUFFICIENT"
    elif not (g("DEV", "exp_net") > 0 and g("DEV", "pf") > 1.0): status = "REJECT"
    elif not (g("VAL", "exp_net") > 0 and g("VAL", "pf") > 1.0 and g("OOS", "exp_net") > 0 and g("OOS", "pf") > 1.0): status = "WEAK"
    else: status = "CANDIDATE"
    # the alternative shape may pass where the primary does not: record the best-passing shape too
    passing = [k for k in (f"{S}x{T}" for S, T in SHAPES) if all(M[p].get(k, {}).get("exp_net", -1) > 0 and M[p].get(k, {}).get("pf", 0) > 1 for p in ("DEV", "VAL", "OOS")) and M["DEV"][k]["n"] >= 200]
    row["passing_shapes"] = passing; row["status"] = status if not (passing and status != "CANDIDATE") else "CANDIDATE(alt shape)"
    if diag_only: row["status"] = "DIAGNOSTIC"
    LEDGER.append(row)
    print(f"{name:42s} {direction:7s} n={row['n']:6d} | DEV {n_dev:5d} exp={g('DEV','exp_net')} PF={g('DEV','pf')} z={g('DEV','z_gross')} | VAL {n_val:4d} exp={g('VAL','exp_net')} PF={g('VAL','pf')} | OOS {n_oos:5d} exp={g('OOS','exp_net')} PF={g('OOS','pf')} | {row['status']} ({time.time()-T0:.0f}s)", flush=True)
    return row

def first_flag(d, idx):
    """True for the first event of its server day."""
    days = d["day"].to_numpy()[idx]; seen = set(); out = []
    for dd in days:
        out.append(dd not in seen); seen.add(dd)
    return np.array(out)

def mk(d, idx, side):
    idx = np.asarray(idx, int); side = np.asarray(side)
    return pd.DataFrame(dict(i=idx, side=side, first=first_flag(d, idx)))

# ------------------------------------------------------------------ event generators (M5 unless noted)
def events(d):
    o, h, l, c, v = (d[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume")); atr = d["atr"].to_numpy(); n = len(d)
    hour = d["hour"].to_numpy(); rng = d["rng"].to_numpy(); dr = d["dir"].to_numpy(); vol_ma = d["vol_ma20"].to_numpy()
    hi20, lo20 = d["hi20"].to_numpy(), d["lo20"].to_numpy(); pdh, pdl, pdc, datr = d["pdh"].to_numpy(), d["pdl"].to_numpy(), d["pdc"].to_numpy(), d["datr"].to_numpy()
    EV = {}
    # A. volatility
    compressed = pd.Series(d["bbw_pct100"] <= 0.2).rolling(10).min().to_numpy() == 1
    up = compressed & (c > hi20); dn = compressed & (c < lo20)
    EV["H01 compression -> range break"] = mk(d, np.where(up | dn)[0], np.where(up, 1, -1)[np.where(up | dn)[0]])
    shock = rng >= 3 * atr
    EV["H02/H03 volatility shock bar (>= 3 ATR)"] = mk(d, np.where(shock & (dr != 0))[0], dr[shock & (dr != 0)])
    lowvol = pd.Series(d["atr_pct100"] <= 0.2).rolling(20).min().to_numpy() == 1
    fe = np.zeros(n, bool); fe[1:] = lowvol[:-1] & (rng[1:] > 2 * atr[1:])
    EV["H04 first expansion after low-vol regime"] = mk(d, np.where(fe & (dr != 0))[0], dr[fe & (dr != 0)])
    # B. liquidity / range
    sw_hi = (h > pdh) & (c < pdh); sw_lo = (l < pdl) & (c > pdl)
    EV["H05 previous-day high/low sweep + rejection"] = mk(d, np.where(sw_hi | sw_lo)[0], np.where(sw_hi, -1, 1)[np.where(sw_hi | sw_lo)[0]])
    pc = np.roll(c, 1); br_hi = (c > pdh) & (pc <= pdh); br_lo = (c < pdl) & (pc >= pdl)
    EV["H06 previous-day high/low break (close beyond)"] = mk(d, np.where(br_hi | br_lo)[0], np.where(br_hi, 1, -1)[np.where(br_hi | br_lo)[0]])
    ah, al = d["asia_hi"].to_numpy(), d["asia_lo"].to_numpy(); lon = (hour >= 10) & (hour <= 12)
    ab_hi = lon & (c > ah) & (pc <= ah); ab_lo = lon & (c < al) & (pc >= al)
    EV["H07 Asian range break in London (10-12h)"] = mk(d, np.where(ab_hi | ab_lo)[0], np.where(ab_hi, 1, -1)[np.where(ab_hi | ab_lo)[0]])
    lon2 = (hour >= 10) & (hour <= 14); as_hi = lon2 & (h > ah) & (c < ah); as_lo = lon2 & (l < al) & (c > al)
    EV["H08 Asian range sweep + rejection in London"] = mk(d, np.where(as_hi | as_lo)[0], np.where(as_hi, -1, 1)[np.where(as_hi | as_lo)[0]])
    lh, ll_ = d["london_hi"].to_numpy(), d["london_lo"].to_numpy(); ny = (hour >= 15) & (hour <= 19)
    lb_hi = ny & (c > lh) & (pc <= lh); lb_lo = ny & (c < ll_) & (pc >= ll_)
    EV["H09 London range break in NY (15-19h)"] = mk(d, np.where(lb_hi | lb_lo)[0], np.where(lb_hi, 1, -1)[np.where(lb_hi | lb_lo)[0]])
    for nm, hr in (("London", 10), ("NY", 15)):
        oh, ol = d[f"or_{'london' if nm == 'London' else 'ny'}_hi"].to_numpy(), d[f"or_{'london' if nm == 'London' else 'ny'}_lo"].to_numpy()
        win = ((hour == hr) & (d["time"].dt.minute.to_numpy() >= 15)) | (hour == hr + 1)
        ob_hi = win & (c > oh) & (pc <= oh); ob_lo = win & (c < ol) & (pc >= ol)
        EV[f"H10 {nm} opening-range (15 min) break"] = mk(d, np.where(ob_hi | ob_lo)[0], np.where(ob_hi, 1, -1)[np.where(ob_hi | ob_lo)[0]])
    phv, php, plv, plp = d["ph_val"].to_numpy(), d["ph_prev"].to_numpy(), d["pl_val"].to_numpy(), d["pl_prev"].to_numpy()
    eqh = np.abs(phv - php) <= 0.15 * atr; eql = np.abs(plv - plp) <= 0.15 * atr
    eh_sw = eqh & (h > np.maximum(phv, php)) & (c < np.maximum(phv, php)); el_sw = eql & (l < np.minimum(plv, plp)) & (c > np.minimum(plv, plp))
    EV["H11 equal highs/lows sweep + rejection"] = mk(d, np.where(eh_sw | el_sw)[0], np.where(eh_sw, -1, 1)[np.where(eh_sw | el_sw)[0]])
    # C. mean reversion (side = toward the mean)
    vw = d["vwap"].to_numpy(); disp = (c - vw) / atr
    EV["H12 VWAP displacement >= 3 ATR"] = mk(d, np.where(np.abs(disp) >= 3)[0], np.where(disp > 0, -1, 1)[np.abs(disp) >= 3])
    z = (c - d["sma20"].to_numpy()) / d["std20"].to_numpy()
    EV["H13 20-bar z-score >= 3"] = mk(d, np.where(np.abs(z) >= 3)[0], np.where(z > 0, -1, 1)[np.abs(z) >= 3])
    gap = (c - pdc) / datr; g_ev = np.abs(gap) >= 1.5
    g_first = g_ev & ~np.roll(g_ev, 1)
    EV["H14 displacement from previous close >= 1.5 daily ATR (first)"] = mk(d, np.where(g_first)[0], np.where(gap > 0, -1, 1)[g_first])
    # D. momentum
    run = d["run"].to_numpy(); r5 = (run == 5)
    EV["H15 five consecutive candles"] = mk(d, np.where(r5)[0], dr[r5])
    mv3 = d["mv3"].to_numpy(); dispv = (np.abs(mv3) >= 2) & (v >= 1.5 * vol_ma)
    # sequence: displacement -> retrace >= 38% within 10 bars -> reclaim of the displacement extreme
    idxs = []; sides = []
    for i in np.where(dispv)[0]:
        s = 1 if mv3[i] > 0 else -1; ext = h[i] if s == 1 else l[i]; start = c[i - 3]; size = abs(ext - start)
        if size <= 0 or i + 25 >= n: continue
        retr = False
        for j in range(i + 1, i + 11):
            if (s == 1 and l[j] <= ext - 0.38 * size) or (s == -1 and h[j] >= ext + 0.38 * size): retr = True
            if retr and ((s == 1 and c[j] > ext) or (s == -1 and c[j] < ext)): idxs.append(j); sides.append(s); break
    EV["H16 SEQ displacement -> 38% retrace -> reclaim"] = mk(d, idxs, sides) if idxs else None
    # sequence: prev-day break -> retest holds
    idxs = []; sides = []
    for i in np.where(br_hi | br_lo)[0]:
        s = 1 if br_hi[i] else -1; lvl = pdh[i] if s == 1 else pdl[i]
        for j in range(i + 1, min(i + 11, n)):
            if s == 1 and l[j] <= lvl + 0.25 * atr[j] and c[j] > lvl: idxs.append(j); sides.append(1); break
            if s == -1 and h[j] >= lvl - 0.25 * atr[j] and c[j] < lvl: idxs.append(j); sides.append(-1); break
            if (s == 1 and c[j] < lvl) or (s == -1 and c[j] > lvl): break
    EV["H17 SEQ prev-day break -> retest holds"] = mk(d, idxs, sides) if idxs else None
    # E. reversal / exhaustion
    dhi, dlo = d["day_hi"].to_numpy(), d["day_lo"].to_numpy()
    uw = (h - np.maximum(o, c)) / np.maximum(rng, 1e-9); lw = (np.minimum(o, c) - l) / np.maximum(rng, 1e-9)
    wr_hi = (h >= dhi) & (uw >= 0.6) & (rng >= atr); wr_lo = (l <= dlo) & (lw >= 0.6) & (rng >= atr)
    EV["H18 long wick rejection at the day's extreme"] = mk(d, np.where(wr_hi | wr_lo)[0], np.where(wr_hi, -1, 1)[np.where(wr_hi | wr_lo)[0]])
    mv30 = d["mv30"].to_numpy(); clim = (np.abs(mv30) >= 4) & (rng >= 2 * atr) & (v >= 2 * vol_ma) & (np.sign(mv30) == dr)
    EV["H19 exhaustion climax after >= 4 ATR move"] = mk(d, np.where(clim)[0], -dr[clim])
    # triple touch of the day's high/low without a close beyond (3rd touch)
    idxs = []; sides = []
    days = d["day"].to_numpy(); cnt_h = 0; cnt_l = 0; cur = None
    for i in range(1, n):
        if days[i] != cur: cur = days[i]; cnt_h = 0; cnt_l = 0
        if h[i] >= dhi[i - 1] - 0.25 * atr[i] and c[i] < dhi[i - 1] and h[i - 1] < dhi[i - 1] - 0.25 * atr[i]:
            cnt_h += 1
            if cnt_h == 3: idxs.append(i); sides.append(-1)
        if l[i] <= dlo[i - 1] + 0.25 * atr[i] and c[i] > dlo[i - 1] and l[i - 1] > dlo[i - 1] + 0.25 * atr[i]:
            cnt_l += 1
            if cnt_l == 3: idxs.append(i); sides.append(1)
    EV["H20 third touch of the day's extreme (fade)"] = mk(d, idxs, sides) if idxs else None
    # F. time of day: first 30 minutes' direction at the London and NY opens, and the first Asian hour
    mins = d["time"].dt.minute.to_numpy()
    for nm, hr, m0 in (("London open", 10, 25), ("NY open", 15, 25), ("Asian open", 1, 55)):
        sel = np.where((hour == hr) & (mins == m0))[0]
        s = []
        for i in sel:
            j0 = i - (m0 // 5)
            s.append(np.sign(c[i] - o[j0]) if j0 >= 0 else 0)
        s = np.array(s); keep = s != 0
        EV[f"H21 {nm}: first 30 min direction -> continuation"] = mk(d, sel[keep], s[keep])
    # state transitions
    st = d["state"].to_numpy(); ps = np.roll(st, 1)
    ce = (ps == "COMPRESSION") & (st == "EXPANSION") & (dr != 0)
    EV["H25 STATE compression -> expansion"] = mk(d, np.where(ce)[0], dr[ce])
    er = np.zeros(n, bool); side_er = np.zeros(n)
    for i in np.where((ps == "EXPANSION") | (st == "EXPANSION"))[0]:
        if st[i] == "EXPANSION" and i + 3 < n and dr[i] != 0:
            s = dr[i]
            for j in range(i + 1, i + 4):
                if (s == 1 and c[j] < c[i] - 0.38 * rng[i]) or (s == -1 and c[j] > c[i] + 0.38 * rng[i]): er[j] = True; side_er[j] = s; break
    EV["H26 STATE expansion -> retracement (continuation)"] = mk(d, np.where(er)[0], side_er[er])
    te = (ps == "TREND") & (st == "EXHAUSTION")
    EV["H27 STATE trend -> exhaustion (fade)"] = mk(d, np.where(te)[0], -np.sign(mv30[te]))
    bf = np.zeros(n, bool); side_bf = np.zeros(n)
    for i in np.where(br_hi | br_lo)[0]:
        s = 1 if br_hi[i] else -1; lvl = pdh[i] if s == 1 else pdl[i]
        for j in range(i + 1, min(i + 4, n)):
            if (s == 1 and c[j] < lvl) or (s == -1 and c[j] > lvl): bf[j] = True; side_bf[j] = -s; break
    EV["H28 STATE breakout -> failure within 3 bars (reversal)"] = mk(d, np.where(bf)[0], side_bf[bf])
    return EV

# ------------------------------------------------------------------ TWK hypotheses (M3 flips)
def twk_events():
    S = pd.read_csv("results/signal/signals_M3_full.csv", parse_dates=["time"])
    d3 = E.resample(m1, 3).reset_index(drop=True); d3["t"] = d3["time"].astype("int64") // 10**9; d3["day"] = d3["time"].dt.floor("D")
    h3, l3, c3 = d3["high"].to_numpy(float), d3["low"].to_numpy(float), d3["close"].to_numpy(float)
    d3["atr"] = E.rma(E.true_range(h3, l3, c3, True), 14)
    bar = S["bar"].to_numpy(); side = S["side"].to_numpy()
    out = {"H22 TWK flip (contrarian = against)": mk(d3, bar, side)}
    # sequence: flip -> adverse 0.5 ATR -> reclaim of the flip close (with)
    atr3 = d3["atr"].to_numpy(); idxs = []; sides = []
    for i, s in zip(bar, side):
        if i + 21 >= len(c3) or np.isnan(atr3[i]): continue
        adv = False
        for j in range(i + 1, i + 21):
            if (s == 1 and l3[j] <= c3[i] - 0.5 * atr3[i]) or (s == -1 and h3[j] >= c3[i] + 0.5 * atr3[i]): adv = True
            if adv and ((s == 1 and c3[j] > c3[i]) or (s == -1 and c3[j] < c3[i])): idxs.append(j); sides.append(s); break
    out["H23 SEQ TWK flip -> adverse 0.5 ATR -> reclaim"] = mk(d3, idxs, sides)
    # first flip of the day vs later
    ev = mk(d3, bar, side); out["H24 TWK first flip of the day"] = ev[ev["first"]].reset_index(drop=True)
    return d3, out


if __name__ == "__main__":
    # ------------------------------------------------------------------ run
    d5 = base_frame(5); EV5 = events(d5); print(f"M5 frame {len(d5)} bars, {len(EV5)} event families ({time.time()-T0:.0f}s)", flush=True)
    for name, ev in EV5.items():
        fam = name.split()[0]
        for direction in ("with", "against"):
            evaluate(name, fam, name, ev, d5, 5, direction)
        if ev is not None and len(ev) and ev["first"].sum() >= 100:
            evaluate(name + " [FIRST of day]", fam, name, ev[ev["first"]].reset_index(drop=True), d5, 5, "with")
            evaluate(name + " [LATER in day]", fam, name, ev[~ev["first"]].reset_index(drop=True), d5, 5, "with")
    d3, EV3 = twk_events()
    evaluate("H22 TWK flip (contrarian = against)", "H22", "TWK M3 flip traded against its direction", EV3["H22 TWK flip (contrarian = against)"], d3, 3, "against")
    evaluate("H23 SEQ TWK flip -> adverse 0.5 ATR -> reclaim", "H23", "TWK flip, price goes 0.5 ATR against, then reclaims the flip close: trade with the flip", EV3["H23 SEQ TWK flip -> adverse 0.5 ATR -> reclaim"], d3, 3, "with")
    evaluate("H24 TWK first flip of the day", "H24", "only the first TWK flip of each server day", EV3["H24 TWK first flip of the day"], d3, 3, "with")
    evaluate("H24 TWK first flip of the day", "H24", "only the first TWK flip of each server day, against", EV3["H24 TWK first flip of the day"], d3, 3, "against")
    # M15 cross-check for the families that reached WEAK or better on M5
    d15 = base_frame(15); EV15 = events(d15)
    promising = {r["hypothesis"] for r in LEDGER if r.get("status") in ("WEAK", "CANDIDATE", "CANDIDATE(alt shape)")}
    for name, ev in EV15.items():
        if name in promising or any(name == p.split(" [")[0] for p in promising):
            for direction in ("with", "against"):
                evaluate(name + " [M15]", name.split()[0], name, ev, d15, 15, direction)

    # ------------------------------------------------------------------ robustness for anything WEAK or better (primary shape or passing shape)
    def robustness(row):
        r = row["r_primary"]; ev = row["ev"]; t = row["times"]; sd = row["side"]; out = {}
        ok = ~np.isnan(r)
        df = pd.DataFrame(dict(r=r[ok], t=t[ok], side=sd[ok]))
        df["month"] = df.t.dt.to_period("M").astype(str); df["hour"] = df.t.dt.hour
        df["session"] = pd.cut(df.hour, [-1, 0, 9, 14, 19, 23], labels=["rollover", "asia", "london", "overlap", "ny"]).astype(str)
        net = df.r.sum()
        out["net_R"] = round(float(net), 1)
        if net > 0:
            out["max_month_share"] = round(float(df.groupby("month").r.sum().max() / net), 2); out["max_trade_share"] = round(float(df.r.max() / net), 2)
            out["max_session_share"] = round(float(df.groupby("session").r.sum().max() / net), 2)
        out["by_direction"] = {("BUY" if s == 1 else "SELL"): dict(n=int(len(g)), exp=round(float(g.r.mean()), 3)) for s, g in df.groupby("side")}
        out["by_session"] = {k: dict(n=int(len(g)), exp=round(float(g.r.mean()), 3)) for k, g in df.groupby("session")}
        out["years_positive"] = int(sum(1 for y, v in row["by_year"].items() if v["exp"] > 0)); out["years"] = len(row["by_year"])
        return out
    tfmin = {"M5": 5, "M3": 3, "M15": 15}
    for row in LEDGER:
        if row.get("status") in ("WEAK", "CANDIDATE", "CANDIDATE(alt shape)"):
            row["robustness"] = robustness(row)
            # cost sensitivity on the primary/passing shape
            shape = row["passing_shapes"][0] if row["passing_shapes"] else "1.0x2.0"; S_, T_ = (float(x) for x in shape.split("x"))
            d = d15 if row["tf"] == "M15" else (d3 if row["tf"] == "M3" else d5); i = row["ev"]["i"].to_numpy(); cs = {}
            for cm in (1.25, 1.5, 2.0):
                res = scan_events(d["t"].to_numpy()[i], row["side"], d["atr"].to_numpy()[i], 100, tfmin[row["tf"]], cm)
                rr, _, _ = shape_r(res, S_, T_); per = np.select([row["times"] < PERIODS["DEV"][1], row["times"] < PERIODS["VAL"][1]], ["DEV", "VAL"], "OOS")
                cs[f"x{cm}"] = {p: round(float(np.nanmean(rr[per == p])), 3) for p in ("DEV", "VAL", "OOS")}
            row["cost_sensitivity"] = cs; row["cost_shape"] = shape

    # ------------------------------------------------------------------ write the ledger
    rows = []
    for r in LEDGER:
        M = r.get("metrics", {}); pr = {}
        for p in ("DEV", "VAL", "OOS"):
            for k in ("1.0x1.0", "1.0x2.0", "0.5x0.5", "0.25x0.25"):
                m = M.get(p, {}).get(k, {})
                pr[f"{p}_{k}_n"] = m.get("n"); pr[f"{p}_{k}_exp"] = m.get("exp_net"); pr[f"{p}_{k}_pf"] = m.get("pf"); pr[f"{p}_{k}_hit"] = m.get("hit_net"); pr[f"{p}_{k}_z"] = m.get("z_gross"); pr[f"{p}_{k}_gross"] = m.get("exp_gross")
        rows.append(dict(hypothesis=r["hypothesis"], family=r["family"], direction=r["direction"], tf=r.get("tf"), n=r.get("n", 0), status=r.get("status"), passing=",".join(r.get("passing_shapes", [])), first_share=r.get("first_share"), **pr,
                         by_year=json.dumps(r.get("by_year", {})), robustness=json.dumps(r.get("robustness", {})), cost=json.dumps(r.get("cost_sensitivity", {}))))
    LED = pd.DataFrame(rows); LED.to_csv("results/discovery/ledger.csv", index=False)
    json.dump(dict(ledger=rows, mfe_mae={r["hypothesis"] + " | " + r["direction"]: r["metrics"]["ALL"].get("mfe_mae") for r in LEDGER if "metrics" in r},
                   state_counts={k: int(v) for k, v in d5["state"].value_counts().items()}, generated=str(pd.Timestamp.now())[:16], n_hypotheses=len(rows)),
              open("results/discovery/discovery.json", "w"), indent=1, default=lambda x: float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
    print("\nSTATUS COUNTS:", LED.status.value_counts().to_dict())
    print(LED[LED.status.isin(["WEAK", "CANDIDATE", "CANDIDATE(alt shape)"])][["hypothesis", "direction", "tf", "n", "status", "passing", "DEV_1.0x2.0_exp", "VAL_1.0x2.0_exp", "OOS_1.0x2.0_exp"]].to_string(index=False))
    print(f"discovery done ({time.time()-T0:.0f}s)")
