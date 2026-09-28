"""Tick calibration of the Nyao trailing stop.

The bar engine can only bound a $0.20 trailing stop inside an M1 bar ("path" = the bar extreme was reached first,
"worst" = the first 20-point reversal came right after activation). This script replays every non-chain trade that
falls inside the Dukascopy tick sample (data/ticks: 2025, Thu/Fri, server 14:00-19:59) tick by tick with the EA's
own per-tick trailing / break-even rules and records where the real exit lands.

Outputs: results/nyao/tick_calibration.csv (one row per replayed trade) and tick_calibration.json (summary).
"""
import glob, json, os, sys, time
from dataclasses import replace
import numpy as np
import pandas as pd
import twk_engine as E
import nyao_engine as N

T0 = time.time()
os.makedirs("results/nyao", exist_ok=True)
SET_DIR = os.environ.get("NYAO_SET_DIR", "results/nyao/settings")
DATA = "data/XAUUSD_M1_servertime_full.csv.gz"

m1 = pd.read_csv(DATA, parse_dates=["time"])
spread = np.array([E.year_spread_model()[y] for y in m1.time.dt.year.to_numpy()], float)
t_m1 = (m1["time"].astype("int64") // 10**9).to_numpy()
P0 = N.load_set(os.path.join(SET_DIR, "default.set"), name="default")
P0 = replace(P0, EnableHedgeChain=False)            # independent trades for the calibration
A = int(pd.Timestamp("2025-01-01").timestamp()); B = int(pd.Timestamp("2026-01-01").timestamp())

# ---------------------------------------------------------------- tick sample coverage (server time)
def eu_dst_utc(ts: pd.Timestamp) -> bool:
    y = ts.year
    mar = pd.Timestamp(y, 3, 31); mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
    octo = pd.Timestamp(y, 10, 31); octo -= pd.Timedelta(days=(octo.weekday() + 1) % 7)
    return (ts >= mar + pd.Timedelta(hours=1)) and (ts < octo + pd.Timedelta(hours=1))

files = sorted(glob.glob("data/ticks/xauusd_*utc.csv"))
by_day = {}
for f in files:
    b = os.path.basename(f)                     # xauusd_YYYY-MM-DD_HHutc.csv
    day = b[7:17]; hh = int(b[18:20])
    utc = pd.Timestamp(day) + pd.Timedelta(hours=hh)
    off = 3 if eu_dst_utc(utc) else 2
    srv = utc + pd.Timedelta(hours=off)
    by_day.setdefault(srv.strftime("%Y-%m-%d"), []).append((int(srv.timestamp()), f, off))
for d in by_day:
    by_day[d].sort()
print(f"tick sample: {len(files)} hour files over {len(by_day)} server days ({time.time()-T0:.0f}s)", flush=True)

# contiguous covered ranges per day
ranges = []
for d, lst in by_day.items():
    start = lst[0][0]; prev = start; fl = [lst[0][1]]; off = lst[0][2]
    for s, f, o in lst[1:]:
        if s == prev + 3600:
            prev = s; fl.append(f)
        else:
            ranges.append((start, prev + 3600, fl, off)); start = s; prev = s; fl = [f]; off = o
    ranges.append((start, prev + 3600, fl, off))
print(f"contiguous ranges: {len(ranges)}, hours {sum((b - a) // 3600 for a, b, _, _ in ranges)}", flush=True)

# ---------------------------------------------------------------- bar-engine trades (path mode) for 2025 on M1 and M5
rows = []
summary = {}
for tf in (1, 5):
    pre = N.get_pre(m1, tf, P0)
    P = replace(P0, name=f"default_nohedge_M{tf}")
    tr = N.simulate(m1, pre, P, spread, A, B)
    tr["entry_ts"] = tr.entry_time.astype("int64") // 10**9
    tr["exit_ts"] = tr.exit_time.astype("int64") // 10**9
    print(f"M{tf}: {len(tr)} trades in 2025 (path), net {tr.pnl.sum():.0f}, exits {tr.exit_reason.value_counts().head(6).to_dict()} ({time.time()-T0:.0f}s)", flush=True)
    mg_b = pre["mg_buy"]; mg_s = pre["mg_sell"]; k_of = pre["k_of"]; tf_time = pre["tf_time"]
    n_rep = 0; n_unres = 0
    for (ra, rb, fl, off) in ranges:
        sub = tr[(tr.entry_ts >= ra) & (tr.entry_ts < rb - 600) & (~tr.chain) & (tr.via != "hedge")]
        if not len(sub):
            continue
        # load ticks for the range, convert to server ms, round to XM's 0.01
        parts = [pd.read_csv(f, usecols=["timestamp", "askPrice", "bidPrice"]) for f in fl]
        tk = pd.concat(parts, ignore_index=True)
        tk = tk[(tk.bidPrice > 0) & (tk.askPrice > 0)]
        ts = (tk.timestamp.to_numpy(np.int64) + off * 3600 * 1000)
        bid = np.round(tk.bidPrice.to_numpy(float), 2); askr = np.round(tk.askPrice.to_numpy(float), 2)
        order = np.argsort(ts, kind="stable"); ts = ts[order]; bid = bid[order]; askr = askr[order]
        dspread = float(np.median(askr - bid))
        tsl = ts.tolist(); bl = bid.tolist()
        for r in sub.itertuples():
            side = 1 if r.side == "BUY" else -1
            lot = r.lot; entry = r.entry; sl = r.initial_sl; spr = r.spread_pts * 0.01
            be = (entry + spr + (0.5 / lot) * 0.01) if side == 1 else (entry - spr - (0.5 / lot) * 0.01)
            spread_cost = spr * lot * 100.0
            k_open = int(r.k_open)
            grace_end = tf_time[min(k_open + P.HealthGraceBars, len(tf_time) - 1)]
            reason_bar = r.exit_reason
            if reason_bar in ("SL_tight", "SL_be", "SL_offset", "SL_offset_be", "PARTIAL_L1", "PARTIAL_L2"):
                continue
            limit_ts = r.exit_ts if reason_bar in ("HEALTH", "BASKET", "END", "MIN_EQUITY", "PARTIAL_L3", "MAX_TRIGGERS") else None
            i0 = int(np.searchsorted(ts, r.entry_ts * 1000))
            if i0 >= len(ts):
                continue
            be_locked = False; exit_px = None; reason_tick = None; act_ts = None; first_sl_after_act = None
            i = i0
            while i < len(tsl):
                t_ms = tsl[i]; b_ = bl[i]; a_ = b_ + spr
                tsec = t_ms // 1000
                if limit_ts is not None and tsec >= limit_ts:
                    exit_px = b_ if side == 1 else a_; reason_tick = reason_bar; break
                if tsec >= rb:
                    break
                if sl:
                    if side == 1 and b_ <= sl:
                        exit_px = b_; reason_tick = "SL_trail" if act_ts else "SL"; break
                    if side == -1 and a_ >= sl:
                        exit_px = a_; reason_tick = "SL_trail" if act_ts else "SL"; break
                # per-tick trailing (ManageTrailingTPSL)
                kt = int(np.searchsorted(t_m1, tsec, side="right") - 1)          # M1 bar containing the tick
                sc = (mg_b[kt - 1] if side == 1 else mg_s[kt - 1]) if kt >= 1 else 0.0
                delta = (sc - r.score0) if r.score0 > 0 else 0.0
                dist_usd = max(P.TrailingDistanceValue + delta * P.TrailingValueMultiplier, P.TrailingValueMultiplier * 0.1)
                dist_px = (dist_usd / lot) * 0.01
                profit = (b_ - entry) * lot * 100.0 if side == 1 else (entry - a_) * lot * 100.0
                if profit >= P.MinBreakEvenProfit * P.ProfitThresholdMultiplier:
                    if side == 1:
                        calc = b_ - dist_px
                        if calc < be: calc = be
                        if (sl == 0 or calc > sl) and calc < b_:
                            sl = round(calc, 2)
                            if act_ts is None: act_ts = tsec; first_sl_after_act = sl
                    else:
                        calc = a_ + dist_px
                        if calc > be: calc = be
                        if (sl == 0 or calc < sl) and calc > a_:
                            sl = round(calc, 2)
                            if act_ts is None: act_ts = tsec; first_sl_after_act = sl
                # break-even on spread after the grace period (ManageLosingPositions step 1)
                if tsec >= grace_end and not be_locked and profit > spread_cost * P.BreakEvenSpreadMultiplier:
                    if side == 1 and entry < b_ and (sl == 0 or entry > sl):
                        sl = entry; be_locked = True
                    elif side == -1 and entry > a_ and (sl == 0 or entry < sl):
                        sl = entry; be_locked = True
                i += 1
            if exit_px is None:
                n_unres += 1; continue
            pnl_px = (exit_px - entry) if side == 1 else (entry - exit_px)
            pnl_tick = pnl_px * lot * 100.0
            pnl_be = ((be - entry) if side == 1 else (entry - be)) * lot * 100.0
            rows.append(dict(tf=tf, id=r.id, entry_time=r.entry_time, side=r.side, lot=lot, entry=entry, exit_bar=r.exit, exit_tick=exit_px,
                             reason_bar=reason_bar, reason_tick=reason_tick, pnl_bar=r.pnl - r.swap, pnl_tick=pnl_tick, pnl_be=pnl_be,
                             hold_bar_min=r.bars, hold_tick_s=(tsl[i] // 1000 - r.entry_ts) if i < len(tsl) else None,
                             activated=act_ts is not None, secs_to_activation=(act_ts - r.entry_ts) if act_ts else None,
                             max_fav_bar=r.max_fav, score0=r.score0, duka_spread=dspread, day=pd.Timestamp(ra, unit="s").strftime("%Y-%m-%d")))
            n_rep += 1
    print(f"M{tf}: replayed {n_rep} trades, unresolved {n_unres} ({time.time()-T0:.0f}s)", flush=True)

df = pd.DataFrame(rows)
df.to_csv("results/nyao/tick_calibration.csv", index=False)

def summ(d):
    if not len(d):
        return {}
    out = dict(n=int(len(d)), pnl_bar_mean=round(float(d.pnl_bar.mean()), 3), pnl_tick_mean=round(float(d.pnl_tick.mean()), 3), pnl_be_mean=round(float(d.pnl_be.mean()), 3),
               win_bar=round(float((d.pnl_bar > 0).mean()), 3), win_tick=round(float((d.pnl_tick > 0).mean()), 3),
               reasons_tick=d.reason_tick.value_counts().to_dict())
    tt = d[d.reason_bar.isin(["TRAIL", "SL_trail"])]
    if len(tt):
        lam = (tt.pnl_tick - tt.pnl_be) / (tt.pnl_bar - tt.pnl_be).where((tt.pnl_bar - tt.pnl_be).abs() > 1e-9)
        out.update(trail_n=int(len(tt)), trail_pnl_bar=round(float(tt.pnl_bar.mean()), 3), trail_pnl_tick=round(float(tt.pnl_tick.mean()), 3), trail_pnl_be=round(float(tt.pnl_be.mean()), 3),
                   lambda_median=round(float(lam.median()), 3), lambda_mean=round(float(lam.clip(-1, 2).mean()), 3),
                   lambda_share_below_0_1=round(float((lam < 0.1).mean()), 3), lambda_share_above_0_5=round(float((lam > 0.5).mean()), 3),
                   tick_exit_within_be_plus_5pts=round(float(((tt.pnl_tick - tt.pnl_be) <= 0.05 * tt.lot * 100).mean()), 3),
                   secs_to_activation_median=float(tt.secs_to_activation.median()) if tt.secs_to_activation.notna().any() else None,
                   hold_tick_s_median=float(tt.hold_tick_s.median()))
    return out

summary = dict(generated=str(pd.Timestamp.now())[:16], n_rows=int(len(df)), duka_spread_median=round(float(df.duka_spread.median()), 3) if len(df) else None,
               all=summ(df), M1=summ(df[df.tf == 1]), M5=summ(df[df.tf == 5]),
               by_reason_bar={k: summ(g) for k, g in df.groupby("reason_bar")},
               by_side={k: summ(g) for k, g in df.groupby("side")})
json.dump(summary, open("results/nyao/tick_calibration.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in summary.items() if k in ("n_rows", "duka_spread_median", "all", "M1", "M5")}, indent=1, default=str))
print(f"done ({time.time()-T0:.0f}s)")
