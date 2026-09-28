"""Nyao research variants (run after nyao_lab.py, sequentially: the machine cannot hold two runs in memory).

The shipped EA stops itself at $20 equity, so a five-year run ends within months and the mechanics cannot be
characterised over the whole history. These variants keep the EA's logic but hold the stop at a fixed $10 per 0.01
lot (the same $ stop the shipped profile has at $1,000 equity), disable the ruin stop and the drawdown pause, and
report the calibrated trailing reading over the full five years, so loss patterns and regimes can be read on the
whole sample. They are research readings, not the EA as shipped.
Outputs: results/nyao/nyao_runs2.csv, trades in results/nyao/trades/
"""
import json, os, sys, time
from dataclasses import replace
import numpy as np
import pandas as pd
import twk_engine as E
import nyao_engine as N

T0 = time.time()
OUT = "results/nyao"; os.makedirs(f"{OUT}/trades", exist_ok=True)
SET_DIR = os.environ.get("NYAO_SET_DIR", "results/nyao/settings")
m1 = pd.read_csv("data/XAUUSD_M1_servertime_full.csv.gz", parse_dates=["time"])
spread = np.array([E.year_spread_model()[y] for y in m1.time.dt.year.to_numpy()], float)
END = pd.Timestamp("2026-09-25 00:00")
PERIODS = {"DEV": (pd.Timestamp("2021-09-01"), pd.Timestamp("2024-01-01")), "VAL": (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), "OOS": (pd.Timestamp("2025-01-01"), END)}
def ts(x): return int(pd.Timestamp(x).timestamp())
cal = json.load(open(f"{OUT}/tick_calibration.json"))
LAM_T = max(0.0, min(1.0, cal["by_reason_bar"]["TRAIL"]["lambda_mean"])); LAM_S = max(0.0, min(1.0, cal["by_reason_bar"]["SL_trail"]["lambda_mean"]))
D = N.load_set(os.path.join(SET_DIR, "default.set"), name="default")
FIX = dict(SLInputType=N.INPUT_DOLLAR, SLValue=10.0, MinimumEquity=0.0, MinEquityPercent=0.0, EnableBasketStop=False, EnableDynamicLots=False,
           trail_mode="calib", trail_lambda=LAM_T, trail_lambda_sl=LAM_S, deposit=1000.0)
ROWS = []

def short(tr):
    if tr is None or not len(tr):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, exp=0.0, dd=0.0, spread=0.0, gross=0.0)
    pnl = tr.pnl.to_numpy(float); w = pnl[pnl > 0.005]; lo = pnl[pnl < -0.005]
    eq = np.cumsum(pnl); peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    sp = float((tr.spread_pts * 0.01 * tr.lot * 100.0).sum())
    return dict(n=int(len(pnl)), net=float(pnl.sum()), pf=float(w.sum() / -lo.sum()) if lo.sum() < 0 else float("inf"), win=float((pnl > 0).mean()), exp=float(pnl.mean()),
                dd=float((peak - eq).max()), spread=sp, gross=float(pnl.sum() + sp))

def run(name, tf, P, group, desc):
    P = replace(P, name=name)
    pre = N.get_pre(m1, tf, P)
    tr = N.simulate(m1, pre, P, spread, ts(PERIODS["DEV"][0]), ts(END))
    tr.to_csv(f"{OUT}/trades/{name}.csv", index=False)
    m = short(tr); st = tr.attrs["stats"]
    row = dict(run=name, group=group, desc=desc, tf=tf, hedge=P.EnableHedgeChain, trades=m["n"], win=round(m["win"], 3), pf=round(m["pf"], 2), exp=round(m["exp"], 2), net=round(m["net"], 0),
               gross_before_spread=round(m["gross"], 0), spread_cost=round(m["spread"], 0), max_dd=round(m["dd"], 0), chains=st["chains_started"], hedges=st["hedges_opened"], health_closes=st["health_closes"])
    for pn, (a, b) in PERIODS.items():
        s = tr[(tr.entry_time >= a) & (tr.entry_time < b)]; mm = short(s)
        row[f"{pn}_n"] = mm["n"]; row[f"{pn}_net"] = round(mm["net"], 0); row[f"{pn}_pf"] = round(mm["pf"], 2); row[f"{pn}_exp"] = round(mm["exp"], 2); row[f"{pn}_gross"] = round(mm["gross"], 0)
    row["exit_reasons"] = json.dumps(tr.exit_reason.value_counts().head(8).to_dict()) if len(tr) else "{}"
    ROWS.append(row)
    print(f"{name:34s} n={m['n']:6d} PF={m['pf']:5.2f} win={m['win']:.2f} exp={m['exp']:6.2f} net={m['net']:8.0f} gross={m['gross']:8.0f} spread={m['spread']:7.0f} | " + " ".join(f"{pn} {row[pn+'_net']:.0f}/{row[pn+'_pf']:.2f}" for pn in PERIODS) + f" ({time.time()-T0:.0f}s)", flush=True)
    return tr

for tf in (1, 5, 3):
    run(f"fixed_M{tf}_nohedge", tf, replace(D, EnableHedgeChain=False, **FIX), "fixed", "EA logic, fixed $10 stop, no ruin stop, hedge off, calibrated trailing")
    run(f"fixed_M{tf}_hedge", tf, replace(D, **FIX), "fixed", "EA logic, fixed $10 stop, no ruin stop, hedge on, calibrated trailing")
# what carries the loss: switch the management layers off one at a time (M5, hedge off)
B = replace(D, EnableHedgeChain=False, **FIX)
run("fixed_M5_no_trailing", 5, replace(B, EnableTrailing=False), "ablation", "trailing off (stop $10, health/partial/BE stay)")
run("fixed_M5_no_lossmgmt", 5, replace(B, EnableLossManagement=False), "ablation", "loss management off (health close, BE on spread, tighten, re-entry)")
run("fixed_M5_no_reentry", 5, replace(B, EnableVirtualSLReentry=False), "ablation", "virtual-SL re-entry off")
run("fixed_M5_no_dampening", 5, replace(B, EnableSignalDampening=False), "ablation", "signal dampening off (cooldown, losing-position penalty, drawdown gate)")
run("fixed_M5_trail_1usd", 5, replace(B, TrailingDistanceValue=1.0), "ablation", "trailing distance $1 per 0.01 lot (100 points)")
run("fixed_M5_trail_3usd", 5, replace(B, TrailingDistanceValue=3.0, MinBreakEvenProfit=1.5), "ablation", "trailing distance $3, activation $2.25")
run("fixed_M5_trail_atr", 5, replace(B, EnableTrailing=False, EnableRiskReward=True, RRRiskMode=1, RRAtrMultiplier=1.5, RiskRewardRatio=1.5), "ablation", "no trailing, SL 1.5 ATR, TP 1.5R, management on")
run("fixed_M5_hedge_onlychain", 5, replace(D, EnableTrailing=False, EnableLossManagement=False, **FIX), "ablation", "hedge chain with trailing and loss management off (chain mechanics alone)")
pd.DataFrame(ROWS).to_csv(f"{OUT}/nyao_runs2.csv", index=False)
print(f"done ({time.time()-T0:.0f}s)")
