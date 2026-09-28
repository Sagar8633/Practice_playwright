"""Loss-prevention layer: the development sequence (risk -> anti-flip -> environment -> management), each protection
alone and cumulatively, with the counterfactual accounting for every blocked trade.

Units: the attribution runs use fixed 0.02 lot so dollars are comparable with every earlier report; equity-based
limits (daily loss, streaks) still track a notional $1,000 account. The final stack is also run with risk sizing.
"""
import json, math, os, time
os.environ["LAB_SKIP_RUNS"] = "1"
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
import twk_engine as E
from filter_lab import m1, sig, ser, spread, PERIODS, END, T_A, T_B, short_metrics

T0 = time.time()
os.makedirs("results/protection", exist_ok=True)
TF = 3
sig = sig.reset_index(drop=True).copy()
b = sig["bar"].to_numpy(); h, l, c = ser["h"], ser["l"], ser["c"]
atr = sig["atr"].to_numpy()
# environment columns the engine reads from the row
rr3 = np.stack([(h[np.maximum(b - i, 0)] - l[np.maximum(b - i, 0)]) / atr for i in range(3)], axis=1).max(axis=1)
sig["large_candle_lock"] = rr3 > 2.0
ema50 = pd.Series(c).ewm(span=50, adjust=False).mean().to_numpy()
ema50_slope = np.abs(ema50[b] - ema50[np.maximum(b - 5, 0)]) / atr
hw = sliding_window_view(h, 50); lw = sliding_window_view(l, 50)
hi50 = np.full(len(c), np.nan); lo50 = np.full(len(c), np.nan); hi50[50:] = hw[:-1].max(axis=1); lo50[50:] = lw[:-1].min(axis=1)
inside = (c[b] < hi50[b] - 0.5 * atr) & (c[b] > lo50[b] + 0.5 * atr)
sig["chop_static"] = (((sig.opp_ago >= 0) & (sig.opp_ago <= 5)).astype(int) + (sig.flips_10 >= 2).astype(int) + (sig.atr_ratio < 0.8).astype(int)
                      + inside.astype(int) + (ema50_slope < 0.1).astype(int) + (sig.adx < 20).astype(int))
print(f"signals {len(sig)}, large-candle locks {int(sig.large_candle_lock.sum())}, chop_static mean {sig.chop_static.mean():.2f} ({time.time()-T0:.0f}s)", flush=True)

BASE = dict(min_volume_ratio=1.2, purple_activation_pts=360, protection_activation_pts=900, lock_pts=180, min_improve_pts=9)
def bot(name, **kw):
    d = dict(BASE); d.update(kw); return E.MomentumEAParams(name=name, **d)

RUNS, DEC, CFG = {}, {}, {}
def run(name, level, desc, **kw):
    tr = E.simulate(m1, sig, ser, TF, bot(name, **kw), spread, T_A, T_B)
    d = tr.attrs["decisions"]
    RUNS[name] = tr; DEC[name] = d; CFG[name] = dict(level=level, desc=desc, kw={k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}, final_equity=tr.attrs["final_equity"])
    m = short_metrics(tr)
    print(f"{name:32s} n={m['n']:5d} net={m['net']:8.0f} PF={m['pf']:.2f} exp={m['exp']:6.2f} dd={m['dd']:6.0f} | NO_TRADE reasons: {d[d.decision=='NO_TRADE'].reason.value_counts().head(4).to_dict()}  ({time.time()-T0:.0f}s)", flush=True)
    return tr

# ------------------------------------------------------------------ baseline and the layers, each alone
run("BASELINE", "baseline", "shipped M3 preset, fixed 0.02 lot")
# Level 1: hard safety
run("L1_spread_atr0.5", "L1 hard safety", "NO_TRADE if spread > 0.5 x ATR", max_spread_atr=0.5)
run("L1_spread_atr0.35", "L1 hard safety", "NO_TRADE if spread > 0.35 x ATR", max_spread_atr=0.35)
run("L1_cost_reward0.10", "L1 hard safety", "NO_TRADE if spread > 10% of the 2R target", max_cost_to_reward=0.10)
run("L1_daily_loss2", "L1 hard safety", "no new trades after a 2% daily loss", daily_loss_pct=2.0)
run("L1_streak_2half_3pause_4stop", "L1 hard safety", "2 losses: half risk (sizing only), 3: pause 60 min, 4: stop for the day", consec_reduce_at=2, consec_pause_at=3, pause_minutes=60, consec_stop_day_at=4)
run("L1_ALL", "L1 hard safety", "spread 0.5 ATR + cost 10% + daily 2% + streak ladder", max_spread_atr=0.5, max_cost_to_reward=0.10, daily_loss_pct=2.0, consec_reduce_at=2, consec_pause_at=3, consec_stop_day_at=4)
# Level 2: stop the destructive behaviour
run("L2_confirm1", "L2 anti-flip", "enter only if the direction still holds 1 bar later", entry_confirm_bars=1)
run("L2_confirm2", "L2 anti-flip", "enter only if the direction still holds 2 bars later", entry_confirm_bars=2)
run("L2_distance2atr", "L2 anti-flip", "NO_TRADE if < 2 ATR from the previous signal", min_signal_distance_atr=2.0)
run("L2_attempts2_reset1atr", "L2 anti-flip", "after 2 losses in a direction, block it until a newer pivot and a 1 ATR move", max_attempts_per_dir=2, reset_atr=1.0)
run("L2_ALL", "L2 anti-flip", "confirm 1 bar + 2 ATR distance + 2 attempts per direction", entry_confirm_bars=1, min_signal_distance_atr=2.0, max_attempts_per_dir=2, reset_atr=1.0)
# Level 3: bad environments
run("L3_large_candle", "L3 environment", "NO_TRADE if any of the last 3 bars > 2 ATR", large_candle_lock=True)
run("L3_vol_extreme1.5", "L3 environment", "NO_TRADE if ATR > 1.5 x its 30-day median", vol_extreme_ratio=1.5)
run("L3_chop_score4", "L3 environment", "NO_TRADE if chop score >= 4 of 7", chop_lock_score=4)
run("L3_chop_score5", "L3 environment", "NO_TRADE if chop score >= 5 of 7", chop_lock_score=5)
run("L3_ALL", "L3 environment", "large candle + extreme vol + chop >= 4", large_candle_lock=True, vol_extreme_ratio=1.5, chop_lock_score=4)
# Level 4: trade management
run("L4_locks_1R_1.5R", "L4 management", "+1R lock +0.25R, +1.5R lock +0.75R (from the MFE/MAE tables)", lock_activation_r=1.0, lock_level_r=0.25, one_to_one_gap_r=0.75, lock2_activation_r=1.5, lock2_level_r=0.75)
run("L4_hybrid_stop", "L4 management", "SL = max(structure, 1 ATR), NO_TRADE if > 4 ATR", initial_sl="hybrid", atr_stop_mult=1.0, atr_stop_cap=4.0)
run("L4_health_30m", "L4 management", "exit after 30 min if < 0R and the signal weakened", health_exit_min=30, health_exit_below_r=0.0)
run("L4_ALL", "L4 management", "locks + hybrid stop + health exit", lock_activation_r=1.0, lock_level_r=0.25, one_to_one_gap_r=0.75, lock2_activation_r=1.5, lock2_level_r=0.75, initial_sl="hybrid", atr_stop_mult=1.0, atr_stop_cap=4.0, health_exit_min=30, health_exit_below_r=0.0)
# cumulative stack
S1 = dict(max_spread_atr=0.5, max_cost_to_reward=0.10, daily_loss_pct=2.0, consec_reduce_at=2, consec_pause_at=3, consec_stop_day_at=4)
S2 = dict(S1, entry_confirm_bars=1, min_signal_distance_atr=2.0, max_attempts_per_dir=2, reset_atr=1.0)
S3 = dict(S2, large_candle_lock=True, vol_extreme_ratio=1.5, chop_lock_score=4)
S4 = dict(S3, lock_activation_r=1.0, lock_level_r=0.25, one_to_one_gap_r=0.75, lock2_activation_r=1.5, lock2_level_r=0.75, initial_sl="hybrid", atr_stop_mult=1.0, atr_stop_cap=4.0, health_exit_min=30, health_exit_below_r=0.0)
run("STACK_1", "stack", "Phase 1", **S1); run("STACK_12", "stack", "Phase 1+2", **S2); run("STACK_123", "stack", "Phase 1+2+3", **S3); run("STACK_1234", "stack", "Phase 1+2+3+4 (full)", **S4)
# evidence-based selection: keep what helped in DEV, VAL and OOS; drop what hurt out of sample
REC = dict(S1, min_signal_distance_atr=2.0, entry_confirm_bars=2, max_attempts_per_dir=2, reset_atr=1.0, large_candle_lock=True,
           lock_activation_r=1.0, lock_level_r=0.25, one_to_one_gap_r=0.75, lock2_activation_r=1.5, lock2_level_r=0.75)
run("RECOMMENDED", "stack", "Level 1 + distance 2 ATR + confirm 2 bars + 2 attempts per direction + large-candle lock + R locks (no vol ban, chop lock, hybrid stop or health exit)", **REC)
# risk-sized equity view (0.5% of equity per trade, elevated vol halves the budget)
run("RISK_baseline", "risk view", "baseline with 0.5% risk sizing from $1,000", sizing="risk", risk_pct=0.5)
run("RISK_full", "risk view", "full stack with 0.5% risk sizing, elevated vol (1.25x) halves the budget", sizing="risk", risk_pct=0.5, vol_elevated_ratio=1.25, **S4)
run("RISK_recommended", "risk view", "recommended stack with 0.5% risk sizing, elevated vol (1.25x) halves the budget", sizing="risk", risk_pct=0.5, vol_elevated_ratio=1.25, **REC)
pd.to_pickle(dict(RUNS=RUNS, DEC=DEC, CFG=CFG), "results/protection/runs.pkl")

# ------------------------------------------------------------------ loss-prevention report per run
base = RUNS["BASELINE"]
sig_bar_of = sig["bar"].to_numpy()
def enrich(tr):
    d = tr.copy()
    d["hold_min"] = (d.exit_time - d.entry_time).dt.total_seconds() / 60
    d["post_loss_15"] = (d.pnl.shift(1) < 0) & ((d.entry_time - d.exit_time.shift(1)).dt.total_seconds() / 60 <= 15)
    d["rapid_flip"] = (d.opp_ago >= 0) & (d.opp_ago <= 5)
    d["atr_ratio"] = d.sig_bar.map(sig.set_index("bar").atr_ratio)
    d["reversal"] = (d.pnl < 0) & (d.max_fav >= 0.5 * d.risk)
    return d
def report_row(name, tr, dec):
    d = enrich(tr) if len(tr) else tr
    m = short_metrics(tr)
    r = dict(run=name, level=CFG[name]["level"], desc=CFG[name]["desc"], trades=m["n"], gross_before_spread=round(m["gross_ex"], 0), spread=round(m["spread"], 0), net=round(m["net"], 0),
             win_rate=round(m["wins"] / max(1, m["n"]), 3), avg_loss=round(m["avg_loss"], 2), avg_win=round(m["avg_win"], 2), pf=round(m["pf"], 2), max_dd=round(m["dd"], 0), consec_losses=m["mcl"],
             expectancy=round(m["exp"], 2), final_equity=round(CFG[name]["final_equity"], 0))
    if len(tr):
        r.update(rapid_flips=int(d.rapid_flip.sum()), initial_sl_hits=int(d.exit_reason.isin(["SL", "SL_gap"]).sum()), post_loss_trades=int(d.post_loss_15.sum()),
                 high_vol_trades=int((d.atr_ratio > 1.5).sum()), profit_to_loss_reversals=int(d.reversal.sum()))
    r["margin_or_risk_rejections"] = int((dec.reason == "RISK_MIN_LOT").sum())
    for per in ("DEV", "VAL", "OOS"):
        a, bb = PERIODS[per]; mm = short_metrics(tr[(tr.entry_time >= a) & (tr.entry_time < bb)]) if len(tr) else short_metrics(tr)
        r[f"{per}_n"] = mm["n"]; r[f"{per}_net"] = round(mm["net"], 0); r[f"{per}_pf"] = round(mm["pf"], 2); r[f"{per}_exp"] = round(mm["exp"], 2); r[f"{per}_dd"] = round(mm["dd"], 0)
    return r
rows = [report_row(n, t, DEC[n]) for n, t in RUNS.items()]
REP = pd.DataFrame(rows); REP.to_csv("results/protection/loss_prevention_report.csv", index=False)

# ------------------------------------------------------------------ counterfactual accounting vs the baseline
def attribution(name):
    tr = RUNS[name]; dec = DEC[name]
    if name == "BASELINE" or not len(tr):
        return None
    bset = base.set_index("sig_bar"); pset = tr.set_index("sig_bar")
    blocked = bset.index.difference(pset.index); new = pset.index.difference(bset.index); common = bset.index.intersection(pset.index)
    # reason for each blocked signal: the last non-pending decision on that signal
    dd = dec[dec.decision != "PENDING"].copy(); dd["sig_bar"] = sig_bar_of[dd.sig.to_numpy()]
    last = dd.groupby("sig_bar").reason.last()
    bl = bset.loc[blocked]; bl = bl.assign(reason=last.reindex(bl.index).fillna("UNKNOWN"))
    per_reason = []
    for rsn, g in bl.groupby("reason"):
        per_reason.append(dict(reason=rsn, blocked=int(len(g)), would_have_won=int((g.pnl > 0).sum()), would_have_lost=int((g.pnl < 0).sum()),
                               loss_prevented=round(float(-g.pnl[g.pnl < 0].sum()), 0), profit_sacrificed=round(float(g.pnl[g.pnl > 0].sum()), 0), net_benefit=round(float(-g.pnl.sum()), 0)))
    nw = pset.loc[new]; cm_b = bset.loc[common]; cm_p = pset.loc[common]
    return dict(run=name, blocked=int(len(bl)), would_have_won=int((bl.pnl > 0).sum()), would_have_lost=int((bl.pnl < 0).sum()),
                loss_prevented=round(float(-bl.pnl[bl.pnl < 0].sum()), 0), profit_sacrificed=round(float(bl.pnl[bl.pnl > 0].sum()), 0), net_benefit_blocked=round(float(-bl.pnl.sum()), 0),
                new_trades=int(len(nw)), new_trades_pnl=round(float(nw.pnl.sum()), 0), common_trades=int(len(common)), management_delta=round(float(cm_p.pnl.sum() - cm_b.pnl.sum()), 0),
                total_delta=round(float(tr.pnl.sum() - base.pnl.sum()), 0), per_reason=sorted(per_reason, key=lambda x: -x["net_benefit"]))
ATTR = [a for a in (attribution(n) for n in RUNS) if a]
pd.DataFrame([{k: v for k, v in a.items() if k != "per_reason"} for a in ATTR]).to_csv("results/protection/attribution.csv", index=False)

# ------------------------------------------------------------------ CHOP score: does it correspond to losing sequences? (baseline trades, not optimised)
bd = base.copy(); bd["chop_static"] = bd.sig_bar.map(sig.set_index("bar").chop_static); bd["prev_loss"] = (bd.pnl.shift(1) < 0).astype(int); bd["chop"] = bd.chop_static + bd.prev_loss
bd["next_loss"] = (bd.pnl.shift(-1) < 0); bd["streak3"] = (bd.pnl < 0) & (bd.pnl.shift(-1) < 0) & (bd.pnl.shift(-2) < 0)
chop = [dict(score=int(s), trades=int(len(g)), exp=round(float(g.pnl.mean()), 2), win=round(float((g.pnl > 0).mean()), 3), starts_3_loss_streak=round(float(g.streak3.mean()), 3),
             **{f"{per}_exp": (round(float(g[(g.entry_time >= PERIODS[per][0]) & (g.entry_time < PERIODS[per][1])].pnl.mean()), 2) if len(g[(g.entry_time >= PERIODS[per][0]) & (g.entry_time < PERIODS[per][1])]) else None) for per in ("DEV", "VAL", "OOS")})
        for s, g in bd.groupby("chop")]

# ------------------------------------------------------------------ equity view
def equity_stats(tr, start=1000.0):
    if not len(tr): return dict(final=start, ret_pct=0, max_dd_pct=0, ruin=False)
    eqc = start + tr.pnl.cumsum().to_numpy(); peak = np.maximum.accumulate(np.concatenate([[start], eqc]))[1:]
    return dict(final=round(float(eqc[-1]), 0), ret_pct=round(float(eqc[-1] / start - 1) * 100, 1), max_dd_pct=round(float(((peak - eqc) / peak).max() * 100), 1), ruin=bool(eqc.min() <= start * 0.2), min_equity=round(float(eqc.min()), 0))
EQ = {n: equity_stats(RUNS[n]) for n in ("BASELINE", "STACK_1234", "RECOMMENDED", "RISK_baseline", "RISK_full", "RISK_recommended")}
for n in ("RISK_baseline", "RISK_full", "RISK_recommended"):
    t = RUNS[n]; EQ[n]["lots_median"] = round(float(t.lot.median()), 3) if len(t) else 0; EQ[n]["lots_max"] = round(float(t.lot.max()), 2) if len(t) else 0

json.dump(dict(report=rows, attribution=ATTR, chop=chop, equity=EQ, cfg=CFG, generated=str(pd.Timestamp.now())[:16]), open("results/protection/protection.json", "w"), indent=1,
          default=lambda x: float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
print(REP[["run", "trades", "gross_before_spread", "spread", "net", "pf", "max_dd", "consec_losses", "DEV_net", "VAL_net", "OOS_net"]].to_string(index=False))
print("\nATTRIBUTION:"); print(pd.DataFrame([{k: v for k, v in a.items() if k != "per_reason"} for a in ATTR]).to_string(index=False))
print("\nCHOP:"); print(pd.DataFrame(chop).to_string(index=False))
print("\nEQUITY:", json.dumps(EQ, indent=0))
print(f"done ({time.time()-T0:.0f}s)")
