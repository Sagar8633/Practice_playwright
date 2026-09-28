"""Nyao Scalper test lab: the EA reproduced in nyao_engine.py against the TWK M3 baseline on the same five years of
XAUUSD M1 bars (Dukascopy, XM server time, XM spread by year, XM swap).

Runs (each config is simulated separately per period, every period starting at the deposit, so DEV / VAL / OOS are
not distorted by compounding or by an earlier ruin; the shipped configs are also run continuously over five years):
  * profiles default / safe / balanced / aggressive on M1, M5 (author's targets) and M3 (the baseline's timeframe)
  * hedge chain on (shipped) and off; trailing bounds path / worst and the tick-calibrated estimate
  * deposit $1,000 (lab standard) and $200 (the user's account)
  * cost sensitivity: spread x1.25 / x1.5 / x2, slippage 5 / 10 points
  * parameter perturbation: entry threshold, EMA periods, RSI, ATR, candle blend
  * entry-only mode: the EA's own R:R stop (1.5 ATR, TP 1.5R), no trailing / loss management / hedge
  * component tests on the baseline: the Nyao score as an entry gate on the TWK M3 signals
Outputs: results/nyao/*.csv, results/nyao/lab.json, results/nyao/trades/*.csv
"""
import json, math, os, sys, time
from dataclasses import replace, asdict
import numpy as np
import pandas as pd
import twk_engine as E
import nyao_engine as N

T0 = time.time()
OUT = "results/nyao"; os.makedirs(OUT, exist_ok=True); os.makedirs(f"{OUT}/trades", exist_ok=True)
SET_DIR = os.environ.get("NYAO_SET_DIR", "results/nyao/settings")
QUICK = "--quick" in sys.argv

m1 = pd.read_csv("data/XAUUSD_M1_servertime_full.csv.gz", parse_dates=["time"])
years = m1["time"].dt.year.to_numpy()
spread = np.array([E.year_spread_model()[y] for y in years], float)
END = pd.Timestamp("2026-09-25 00:00")
PERIODS = {"DEV": (pd.Timestamp("2021-09-01"), pd.Timestamp("2024-01-01")),
           "VAL": (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
           "OOS": (pd.Timestamp("2025-01-01"), END)}
def ts(x): return int(pd.Timestamp(x).timestamp())
T_A, T_B = ts(PERIODS["DEV"][0]), ts(END)
print(f"M1 bars {len(m1)} {m1.time.iloc[0]} .. {m1.time.iloc[-1]} ({time.time()-T0:.0f}s)", flush=True)

# tick calibration factors
LAM_T, LAM_S = 1.0, 1.0
cal = {}
if os.path.exists(f"{OUT}/tick_calibration.json"):
    cal = json.load(open(f"{OUT}/tick_calibration.json"))
    br = cal.get("by_reason_bar", {})
    if "TRAIL" in br and br["TRAIL"].get("lambda_mean") is not None:
        LAM_T = max(0.0, min(1.0, float(br["TRAIL"]["lambda_mean"])))
    if "SL_trail" in br and br["SL_trail"].get("lambda_mean") is not None:
        LAM_S = max(0.0, min(1.0, float(br["SL_trail"]["lambda_mean"])))
print(f"tick calibration lambdas: TRAIL {LAM_T:.3f}, SL_trail {LAM_S:.3f}", flush=True)

PROFILES = {n: N.load_set(os.path.join(SET_DIR, f"{n}.set"), name=n) for n in ("default", "safe", "balanced", "aggressive")}

# ---------------------------------------------------------------- metrics
def short(tr: pd.DataFrame, deposit=1000.0) -> dict:
    if tr is None or not len(tr):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, exp=0.0, dd=0.0, dd_pct=0.0, avg_win=0.0, avg_loss=0.0, mcl=0, max_loss=0.0, max_win=0.0, ruin=False, final=deposit, gross_profit=0.0, gross_loss=0.0, spread_cost=0.0, r_mean=NAN_)
    pnl = tr.pnl.to_numpy(float)
    w = pnl[pnl > 0.005]; lo = pnl[pnl < -0.005]
    eq = deposit + np.cumsum(pnl); peak = np.maximum.accumulate(np.concatenate([[deposit], eq]))[1:]
    dd = peak - eq
    cl = mcl = 0
    for x in pnl:
        if x < -0.005: cl += 1; mcl = max(mcl, cl)
        elif x > 0.005: cl = 0
    r = tr.r_multiple.to_numpy(float); r = r[~np.isnan(r)]
    spread_cost = float((tr.spread_pts * 0.01 * tr.lot * 100.0).sum())
    return dict(n=int(len(pnl)), net=float(pnl.sum()), pf=float(w.sum() / -lo.sum()) if lo.sum() < 0 else float("inf"), win=float((pnl > 0).mean()),
                exp=float(pnl.mean()), dd=float(dd.max()), dd_pct=float((dd / peak).max() * 100), avg_win=float(w.mean()) if len(w) else 0.0,
                avg_loss=float(lo.mean()) if len(lo) else 0.0, mcl=int(mcl), max_loss=float(pnl.min()), max_win=float(pnl.max()),
                ruin=bool(eq.min() <= deposit * 0.02), final=float(eq[-1]), gross_profit=float(w.sum()), gross_loss=float(-lo.sum()),
                spread_cost=spread_cost, r_mean=float(r.mean()) if len(r) else NAN_)
NAN_ = float("nan")

def sharpe_sortino(tr: pd.DataFrame, deposit=1000.0):
    if tr is None or not len(tr):
        return NAN_, NAN_
    d = tr.set_index("exit_time").pnl.resample("1D").sum()
    d = d[d.index.dayofweek < 5]
    if d.std() == 0 or len(d) < 20:
        return NAN_, NAN_
    r = d / deposit
    sh = float(r.mean() / r.std() * math.sqrt(252))
    neg = r[r < 0]
    so = float(r.mean() / neg.std() * math.sqrt(252)) if len(neg) > 2 and neg.std() > 0 else NAN_
    return sh, so

RUNS = {}      # name -> dict(cfg, trades (all periods concatenated with 'period'), per-period metrics, continuous metrics)
ROWS = []

def run_config(name, tf, P, periods=("DEV", "VAL", "OOS"), continuous=False, group="", desc="", save=True):
    P = replace(P, name=name)
    pre = N.get_pre(m1, tf, P)
    parts = []; per = {}
    for per_name in periods:
        a, b = PERIODS[per_name]
        tr = N.simulate(m1, pre, P, spread, ts(a), ts(min(b, END)))
        tr["period"] = per_name
        st = tr.attrs["stats"]; stopped = tr.attrs["stopped"]
        m = short(tr, P.deposit); m["stopped"] = bool(stopped); m["chains"] = st["chains_started"]; m["hedges"] = st["hedges_opened"]
        m["health_closes"] = st["health_closes"]; m["blocked_spread"] = st["blocked_spread"]; m["entries_evaluated"] = st["entries_evaluated"]
        m["days"] = float((min(b, END) - a).days)
        per[per_name] = m
        parts.append(tr)
    allt = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    cont = None
    if continuous:
        trc = N.simulate(m1, pre, P, spread, T_A, T_B)
        cont = short(trc, P.deposit); cont["stopped"] = bool(trc.attrs["stopped"]); cont["stats"] = trc.attrs["stats"]
        sh, so = sharpe_sortino(trc, P.deposit); cont["sharpe"] = sh; cont["sortino"] = so
        if save:
            trc.to_csv(f"{OUT}/trades/{name}_continuous.csv", index=False)
        cont["exit_reasons"] = trc.exit_reason.value_counts().to_dict() if len(trc) else {}
    if save:
        allt.to_csv(f"{OUT}/trades/{name}.csv", index=False)
    tot = short(allt, P.deposit) if len(allt) else short(None)
    row = dict(run=name, group=group, desc=desc, tf=tf, profile=P.name, hedge=P.EnableHedgeChain, trail_mode=P.trail_mode, deposit=P.deposit,
               trades=tot["n"], win=round(tot["win"], 3), pf=round(tot["pf"], 2), exp=round(tot["exp"], 2), net_sum_periods=round(tot["net"], 0),
               avg_win=round(tot["avg_win"], 2), avg_loss=round(tot["avg_loss"], 2), max_loss=round(tot["max_loss"], 1), consec_losses=tot["mcl"], spread_cost=round(tot["spread_cost"], 0))
    for pn in ("DEV", "VAL", "OOS"):
        mm = per.get(pn, short(None))
        row[f"{pn}_n"] = mm["n"]; row[f"{pn}_net"] = round(mm["net"], 0); row[f"{pn}_pf"] = round(mm["pf"], 2); row[f"{pn}_exp"] = round(mm["exp"], 2)
        row[f"{pn}_dd_pct"] = round(mm["dd_pct"], 1); row[f"{pn}_final"] = round(mm["final"], 0); row[f"{pn}_ruin"] = mm["ruin"]; row[f"{pn}_stopped"] = mm.get("stopped", False)
    if cont:
        row.update(cont_net=round(cont["net"], 0), cont_final=round(cont["final"], 0), cont_pf=round(cont["pf"], 2), cont_dd_pct=round(cont["dd_pct"], 1), cont_ruin=cont["ruin"],
                   cont_stopped=cont["stopped"], cont_sharpe=round(cont["sharpe"], 2) if cont["sharpe"] == cont["sharpe"] else None, cont_trades=cont["n"])
    RUNS[name] = dict(cfg=dict(tf=tf, group=group, desc=desc, params={k: v for k, v in asdict(P).items() if v != getattr(N.NyaoParams(), k, None) or k in ("EnableHedgeChain", "trail_mode", "deposit")}),
                      per=per, cont=cont, row=row)
    ROWS.append(row)
    print(f"{name:36s} n={tot['n']:6d} PF={tot['pf']:5.2f} win={tot['win']:.2f} exp={tot['exp']:7.2f} | DEV {per.get('DEV', {}).get('net', 0):8.0f} VAL {per.get('VAL', {}).get('net', 0):8.0f} OOS {per.get('OOS', {}).get('net', 0):8.0f}"
          + (f" | cont final {cont['final']:8.0f} ruin={cont['ruin']}" if cont else "") + f"  ({time.time()-T0:.0f}s)", flush=True)
    return allt

D = PROFILES["default"]
CAL = dict(trail_mode="calib", trail_lambda=LAM_T, trail_lambda_sl=LAM_S)
SKIP = "--skip-runs" in sys.argv
if SKIP:
    _pk = pd.read_pickle(f"{OUT}/runs.pkl"); RUNS.update(_pk["RUNS"]); ROWS.extend(_pk["ROWS"])
    _rc = run_config
    def run_config(name, *a, **k):
        return None

# ================================================================ 1. shipped configuration, three trailing readings
for tf in (1, 5, 3):
    for hedge in (True, False):
        tag = "hedge" if hedge else "nohedge"
        run_config(f"default_M{tf}_{tag}_calib", tf, replace(D, EnableHedgeChain=hedge, **CAL), continuous=True, group="core", desc=f"default profile, M{tf}, hedge chain {'on' if hedge else 'off'}, tick-calibrated trailing")
        if not QUICK:
            run_config(f"default_M{tf}_{tag}_path", tf, replace(D, EnableHedgeChain=hedge, trail_mode="path"), continuous=(tf != 3), group="bounds", desc="optimistic bar bound (extreme reached first)")
            run_config(f"default_M{tf}_{tag}_worst", tf, replace(D, EnableHedgeChain=hedge, trail_mode="worst"), continuous=(tf != 3), group="bounds", desc="pessimistic bar bound (reversal right after activation)")

# ================================================================ 2. other profiles, $200 account
if not QUICK:
    for prof in ("safe", "balanced", "aggressive"):
        Pp = PROFILES[prof]
        for tf in (1, 5):
            run_config(f"{prof}_M{tf}_calib", tf, replace(Pp, **CAL), continuous=True, group="profiles", desc=f"{prof} profile as shipped (hedge {'on' if Pp.EnableHedgeChain else 'off'})")
    run_config("default_M1_hedge_calib_dep200", 1, replace(D, deposit=200.0, **CAL), continuous=True, group="deposit", desc="default profile on a $200 account (stop = 1% of $200 = $2 at 0.01 lot)")
    run_config("default_M5_hedge_calib_dep200", 5, replace(D, deposit=200.0, **CAL), continuous=True, group="deposit", desc="default profile on a $200 account")

# ================================================================ 3. cost sensitivity (default, hedge off, calibrated)
base_cost = replace(D, EnableHedgeChain=False, **CAL)
if not QUICK:
    for tf in (1, 5):
        for sm in (1.25, 1.5, 2.0):
            run_config(f"cost_M{tf}_spread_x{sm}", tf, replace(base_cost, spread_mult=sm), group="cost", desc=f"spread x{sm}")
        for sl_ in (5.0, 10.0):
            run_config(f"cost_M{tf}_slip_{int(sl_)}pts", tf, replace(base_cost, slippage_pts=sl_), group="cost", desc=f"{int(sl_)} points slippage on entries and stop exits")
    run_config("cost_M1_hedge_spread_x1.5", 1, replace(D, spread_mult=1.5, **CAL), group="cost", desc="hedge on, spread x1.5")
    run_config("cost_M1_hedge_slip_5pts", 1, replace(D, slippage_pts=5.0, **CAL), group="cost", desc="hedge on, 5 points slippage")

# ================================================================ 4. entry-only mode (the EA's own R:R stop, no management)
RR = dict(EnableRiskReward=True, RRRiskMode=1, RRAtrMultiplier=1.5, RiskRewardRatio=1.5, EnableTrailing=False, EnableLossManagement=False,
          EnableHedgeChain=False, EnableDynamicLots=False, one_position=True, trail_mode="path")
for tf in (1, 5, 3):
    run_config(f"entryonly_M{tf}_rr1.5", tf, replace(D, **RR), group="entry", desc="Nyao entry only: SL 1.5 ATR, TP 1.5R, one position, no trailing/health/hedge")
if not QUICK:
    run_config("entryonly_M5_rr1.0", 5, replace(D, **dict(RR, RiskRewardRatio=1.0)), group="entry", desc="SL 1.5 ATR, TP 1R")
    run_config("entryonly_M5_rr2.0", 5, replace(D, **dict(RR, RiskRewardRatio=2.0)), group="entry", desc="SL 1.5 ATR, TP 2R")
    run_config("entryonly_M5_rr1.5_thr6", 5, replace(D, **dict(RR, MinBuySignalScore=6.0, MinSellSignalScore=6.0)), group="entry", desc="threshold 6.0")
    run_config("entryonly_M5_rr1.5_blend0", 5, replace(D, **dict(RR, CurrentCandleBlend=0.0)), group="entry", desc="closed candles only (no forming-candle blend)")

# ================================================================ 5. parameter perturbation (default M5, hedge off, calibrated)
if not QUICK:
    pert = replace(D, EnableHedgeChain=False, **CAL)
    for thr in (3.5, 4.0, 5.0, 5.5, 6.0):
        run_config(f"pert_M5_thr{thr}", 5, replace(pert, MinBuySignalScore=thr, MinSellSignalScore=thr), group="perturb", desc=f"entry threshold {thr}")
    for f_, s_ in ((4, 10), (6, 14), (8, 21)):
        run_config(f"pert_M5_ema{f_}_{s_}", 5, replace(pert, EMAFastPeriod=f_, EMASlowPeriod=s_), group="perturb", desc=f"EMA {f_}/{s_}")
    for r_ in (6, 10, 14):
        run_config(f"pert_M5_rsi{r_}", 5, replace(pert, RSIPeriod=r_), group="perturb", desc=f"RSI {r_}")
    for a_ in (6, 10, 14):
        run_config(f"pert_M5_atr{a_}", 5, replace(pert, ATRPeriod=a_), group="perturb", desc=f"ATR {a_}")
    for bl in (0.0, 0.6):
        run_config(f"pert_M5_blend{bl}", 5, replace(pert, CurrentCandleBlend=bl), group="perturb", desc=f"forming-candle blend {bl}")
    for td in (0.5, 1.0, 2.0):
        run_config(f"pert_M5_trail{td}", 5, replace(pert, TrailingDistanceValue=td), group="perturb", desc=f"trailing distance ${td} per 0.01 lot")
    # session / news proxy
    run_config("sess_M5_london", 5, replace(pert, block_windows=((0, 10 * 60), (15 * 60, 24 * 60))), group="session", desc="entries 10:00-14:59 server only")
    run_config("sess_M5_ny", 5, replace(pert, block_windows=((0, 15 * 60), (23 * 60, 24 * 60))), group="session", desc="entries 15:00-22:59 server only")
    run_config("sess_M5_asia", 5, replace(pert, block_windows=((10 * 60, 24 * 60),)), group="session", desc="entries 00:00-09:59 server only")
    run_config("news_M5_block1515_1600", 5, replace(pert, block_windows=((15 * 60 + 15, 16 * 60),)), group="session", desc="news-filter proxy: no entries 15:15-16:00 server")
    run_config("news_M1_block1515_1600", 1, replace(pert, block_windows=((15 * 60 + 15, 16 * 60),)), group="session", desc="news-filter proxy: no entries 15:15-16:00 server")

pd.DataFrame(ROWS).to_csv(f"{OUT}/nyao_runs.csv", index=False)
pd.to_pickle(dict(RUNS=RUNS, ROWS=ROWS), f"{OUT}/runs.pkl")
print(f"nyao runs done ({time.time()-T0:.0f}s)", flush=True)

# ================================================================ 6. BASELINE (TWK M3 preset) and component tests
p = E.CoreParams()
m3 = E.resample(m1, 3)
ser3 = E.compute_series(m3, p)
sig3 = E.signal_table(m3, ser3, 3, m1, m3, p, 5).reset_index(drop=True)
BASE = E.MomentumEAParams(name="BASELINE", min_volume_ratio=1.2, purple_activation_pts=360, protection_activation_pts=900, lock_pts=180, min_improve_pts=9)
def base_metrics(tr):
    out = {}
    for pn, (a, b) in PERIODS.items():
        s = tr[(tr.entry_time >= a) & (tr.entry_time < b)]
        m = E.metrics(s) if len(s) else dict(trades=0)
        out[pn] = dict(n=int(len(s)), net=float(s.pnl.sum()) if len(s) else 0.0, pf=float(m.get("profit_factor", 0.0)) if len(s) else 0.0, exp=float(s.pnl.mean()) if len(s) else 0.0,
                       dd=float(m.get("max_dd", 0.0)) if len(s) else 0.0, win=float(m.get("win_rate", 0.0)) if len(s) else 0.0)
    return out
base_tr = E.simulate(m1, sig3, ser3, 3, BASE, spread, T_A, T_B)
base_tr.to_csv(f"{OUT}/trades/BASELINE_M3.csv", index=False)
BM = E.metrics(base_tr); BP = base_metrics(base_tr)
print(f"BASELINE M3 (0.02 lot): n={len(base_tr)} net={base_tr.pnl.sum():.0f} PF={BM['profit_factor']:.2f} | " + " ".join(f"{k} {v['net']:.0f}/{v['pf']:.2f}" for k, v in BP.items()) + f" ({time.time()-T0:.0f}s)", flush=True)

# Nyao smoothed score at the baseline's entry moment (= the open of the bar after the M3 signal bar)
pre3 = N.get_pre(m1, 3, D)
kk = np.minimum(sig3["bar"].to_numpy() + 1, pre3["n_tf"] - 1)
sig3["nyao_buy"] = pre3["en_buy"][kk]; sig3["nyao_sell"] = pre3["en_sell"][kk]
sig3["nyao_same"] = np.where(sig3.side == 1, sig3.nyao_buy, sig3.nyao_sell)
sig3["nyao_opp"] = np.where(sig3.side == 1, sig3.nyao_sell, sig3.nyao_buy)
COMP = []
def comp(name, mask, desc):
    s = sig3[mask].reset_index(drop=True)
    tr = E.simulate(m1, s, ser3, 3, replace(BASE, name=name), spread, T_A, T_B)
    safe = name.replace(">=", "_ge").replace("<", "_lt").replace("+", "_")
    tr.to_csv(f"{OUT}/trades/{safe}.csv", index=False)
    pm = base_metrics(tr); m = E.metrics(tr) if len(tr) else dict(profit_factor=0)
    row = dict(run=name, desc=desc, signals_kept=int(mask.sum()), signals_total=int(len(sig3)), trades=int(len(tr)), net=round(float(tr.pnl.sum()), 0), pf=round(float(m["profit_factor"]), 2),
               exp=round(float(tr.pnl.mean()), 2) if len(tr) else 0.0, win=round(float(m.get("win_rate", 0)), 3), max_dd=round(float(m.get("max_dd", 0)), 0))
    for pn in ("DEV", "VAL", "OOS"):
        row[f"{pn}_n"] = pm[pn]["n"]; row[f"{pn}_net"] = round(pm[pn]["net"], 0); row[f"{pn}_pf"] = round(pm[pn]["pf"], 2); row[f"{pn}_exp"] = round(pm[pn]["exp"], 2)
    # retention rule from the filter lab: better expectancy AND PF than baseline in BOTH DEV and VAL
    row["passes_dev_val"] = bool(all(pm[pn]["exp"] > BP[pn]["exp"] and pm[pn]["pf"] > BP[pn]["pf"] for pn in ("DEV", "VAL"))) if name != "BASELINE" else None
    COMP.append(row)
    print(f"{name:34s} kept {int(mask.sum()):5d}/{len(sig3)} n={len(tr):5d} net={tr.pnl.sum():8.0f} PF={m['profit_factor']:.2f} | " + " ".join(f"{k} {v['net']:.0f}/{v['pf']:.2f}" for k, v in pm.items()) + f" pass={row['passes_dev_val']} ({time.time()-T0:.0f}s)", flush=True)
    return tr
all_mask = np.ones(len(sig3), bool)
comp("BASELINE", all_mask, "TWK M3 preset, fixed 0.02 lot, no Nyao gate")
comp("BASE+nyao_score>=4.5", (sig3.nyao_same >= 4.5).to_numpy(), "keep the TWK signal only if the Nyao score in its direction >= 4.5 (the EA's own threshold)")
comp("BASE+nyao_score>=6.0", (sig3.nyao_same >= 6.0).to_numpy(), "Nyao score >= 6.0 (safe profile threshold)")
comp("BASE+nyao_score>=3.0", (sig3.nyao_same >= 3.0).to_numpy(), "Nyao score >= 3.0")
comp("BASE+nyao_agrees", (sig3.nyao_same > sig3.nyao_opp).to_numpy(), "Nyao score in the signal direction > opposite score")
comp("BASE+nyao_opp<4.5", (sig3.nyao_opp < 4.5).to_numpy(), "block when the opposite Nyao score >= 4.5")
comp("BASE+nyao_alive", (sig3.nyao_same > 0).to_numpy(), "dead-market gate only (ATR ratio >= 0.6 and score > 0)")
comp("BASE+nyao_score<4.5", (sig3.nyao_same < 4.5).to_numpy(), "inverse: keep only signals the Nyao score rejects")
pd.DataFrame(COMP).to_csv(f"{OUT}/component_tests.csv", index=False)

# score buckets on the baseline's own trades (does the Nyao score carry information about TWK outcomes?)
bt = base_tr.copy()
sb = sig3.set_index("bar")
bt["nyao_same"] = bt.sig_bar.map(sb.nyao_same); bt["nyao_opp"] = bt.sig_bar.map(sb.nyao_opp)
bt["bucket"] = pd.cut(bt.nyao_same, [-0.01, 2, 3.5, 4.5, 5.5, 6.5, 10.01], labels=["0-2", "2-3.5", "3.5-4.5", "4.5-5.5", "5.5-6.5", "6.5-10"])
BUCK = []
for b_, g in bt.groupby("bucket", observed=True):
    r = dict(bucket=str(b_), n=int(len(g)), exp=round(float(g.pnl.mean()), 2), win=round(float((g.pnl > 0).mean()), 3), r_mean=round(float(g.r_multiple.mean()), 3))
    for pn, (a, bb) in PERIODS.items():
        s = g[(g.entry_time >= a) & (g.entry_time < bb)]
        r[f"{pn}_n"] = int(len(s)); r[f"{pn}_exp"] = round(float(s.pnl.mean()), 2) if len(s) else None
    BUCK.append(r)
pd.DataFrame(BUCK).to_csv(f"{OUT}/baseline_by_nyao_score.csv", index=False)
print(pd.DataFrame(BUCK).to_string(index=False), flush=True)

# ================================================================ 7. trade-by-trade comparison, BASELINE vs Nyao M3 (calibrated, hedge off)
ny = pd.read_csv(f"{OUT}/trades/default_M3_nohedge_calib.csv", parse_dates=["entry_time", "exit_time"])
ny = ny[ny.via != "hedge"]
b = base_tr[["entry_time", "exit_time", "side", "pnl", "r_multiple", "exit_reason", "sig_bar"]].copy()
b["key"] = (b.entry_time.astype("int64") // 10**9 // 180)          # M3 bucket of the entry
ny["key"] = (ny.entry_time.astype("int64") // 10**9 // 180)
merged = b.merge(ny[["key", "side", "pnl", "exit_reason", "score0"]].rename(columns={"pnl": "pnl_nyao", "exit_reason": "exit_nyao"}), on=["key", "side"], how="outer", indicator=True)
def cat(r):
    if r["_merge"] == "left_only": return "A_baseline_only"
    if r["_merge"] == "right_only": return "B_nyao_only"
    bw = r.pnl > 0; nw = r.pnl_nyao > 0
    if bw and nw: return "C_both_win"
    if (not bw) and (not nw): return "D_both_lose"
    if (not bw) and nw: return "E_base_loses_nyao_wins"
    return "F_nyao_loses_base_wins"
merged["category"] = merged.apply(cat, axis=1)
TBT = merged.groupby("category").agg(n=("category", "size"), base_pnl=("pnl", "sum"), nyao_pnl=("pnl_nyao", "sum")).reset_index()
TBT.to_csv(f"{OUT}/trade_by_trade_summary.csv", index=False)
merged.drop(columns=["_merge"]).to_csv(f"{OUT}/TRADE_BY_TRADE_COMPARISON.csv", index=False)
print(TBT.to_string(index=False), flush=True)

# ================================================================ 8. regime / session / loss-pattern tables for the core runs
def tag_trades(tr):
    d = tr.copy()
    d["hour"] = d.entry_time.dt.hour
    d["session"] = pd.cut(d.hour, [-1, 9, 14, 18, 23], labels=["Asia 00-09", "London 10-14", "NY/overlap 15-18", "NY late 19-23"])
    d["year"] = d.entry_time.dt.year
    d["is_hedge"] = d.via == "hedge"
    d["loser"] = d.pnl < 0
    return d
h1 = E.resample(m1, 60); ema50 = pd.Series(h1.close).ewm(span=50, adjust=False).mean().to_numpy(); t_h1 = (h1.time.astype("int64") // 10**9).to_numpy()
atr_ref = pd.Series(pre3["tf_atr"], index=m3.time).resample("1D").median().rolling(30, min_periods=10).median().shift(1)
REG = {}
for name in ("default_M1_hedge_calib", "default_M5_hedge_calib", "default_M1_nohedge_calib", "default_M5_nohedge_calib"):
    tr = pd.read_csv(f"{OUT}/trades/{name}.csv", parse_dates=["entry_time", "exit_time"])
    if not len(tr):
        continue
    d = tag_trades(tr)
    k = np.searchsorted(t_h1 + 3600, d.entry_time.astype("int64").to_numpy() // 10**9, side="right") - 1
    slope = np.where(k >= 3, ema50[np.maximum(k, 0)] - ema50[np.maximum(k - 3, 0)], 0.0)
    d["htf_trend"] = np.where(slope > 0, "up", np.where(slope < 0, "down", "flat"))
    d["with_trend"] = np.where(d.side == "BUY", d.htf_trend == "up", d.htf_trend == "down")
    ref = atr_ref.reindex(d.entry_time.dt.floor("D")).ffill().bfill().to_numpy()
    d["vol_ratio"] = d.atr / ref
    d["vol_regime"] = pd.cut(d.vol_ratio, [0, 0.8, 1.25, 99], labels=["low", "normal", "high"])
    out = {}
    for col in ("session", "period", "year", "with_trend", "vol_regime", "exit_reason", "via", "side"):
        g = d.groupby(col, observed=True).agg(n=("pnl", "size"), net=("pnl", "sum"), exp=("pnl", "mean"), win=("loser", lambda x: 1 - x.mean()))
        out[col] = g.round(2).reset_index().astype(str).to_dict("records")
    # loss patterns
    L = d[d.loser]
    out["loss_patterns"] = dict(
        losers=int(len(L)), loser_share_hedge_legs=round(float(L.is_hedge.mean()), 3), loss_from_hedge_legs=round(float(L[L.is_hedge].pnl.sum()), 0), loss_total=round(float(L.pnl.sum()), 0),
        losers_in_NY=round(float((L.session == "NY/overlap 15-18").mean()), 3), losers_against_htf=round(float((~L.with_trend).mean()), 3),
        losers_high_vol=round(float((L.vol_regime == "high").mean()), 3), median_loser_hold_min=float(L.bars.median()), median_winner_hold_min=float(d[~d.loser].bars.median()),
        top10_losses_share=round(float(L.pnl.sort_values().head(10).sum() / L.pnl.sum()), 3) if len(L) else None,
        losers_reversal=round(float((L.max_fav >= 0.5 * L.risk_px).mean()), 3) if len(L) else None,
        exit_reasons_losers=L.exit_reason.value_counts().head(8).to_dict())
    REG[name] = out
json.dump(REG, open(f"{OUT}/regimes.json", "w"), indent=1, default=str)

json.dump(dict(generated=str(pd.Timestamp.now())[:16], lambdas=dict(trail=LAM_T, sl_trail=LAM_S), periods={k: [str(a), str(b)] for k, (a, b) in PERIODS.items()},
               baseline=dict(n=int(len(base_tr)), net=float(base_tr.pnl.sum()), pf=float(BM["profit_factor"]), periods=BP, metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in BM.items() if k != "exit_reasons"}),
               runs={k: v for k, v in RUNS.items()}, component=COMP, buckets=BUCK, trade_by_trade=TBT.to_dict("records"), calibration=cal),
          open(f"{OUT}/lab.json", "w"), indent=1, default=str)
print(f"done ({time.time()-T0:.0f}s)")
