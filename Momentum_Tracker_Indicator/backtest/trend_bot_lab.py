"""Trend-following on gold, daily bars, 2003-2026, frozen canonical rules from the literature, XM costs.
Rules (no parameter search, all reported):
  R1 Turtle S1: 20-day Donchian entry, 10-day opposite exit, 2 x ATR(20) stop, 1% risk        (Faith / Dennis)
  R2 Turtle S2: 55-day entry, 20-day exit, same stop and risk
  R3 SMA 50/200 crossover, always in the market, 10% vol target                                    (classic)
  R4 Time-series momentum, sign of the 1/3/6/12-month return, monthly, 10% vol target               (Moskowitz-Ooi-Pedersen 2012)
  R5 Faber 10-month SMA, long or flat, 1x notional, monthly                                        (Faber 2007)
  Long-only and short-only splits of R1/R2/R3; buy-and-hold and random-direction controls.
Execution: decisions at the daily close, fills at the next open (ask = bid + spread for buys), stops on the bid/ask
intraday with gap fills at the open. Spread: XM median by year (0.32 before 2024, 0.36, 0.38, 0.51). Swap: XM GOLD
today as a fraction of notional per night (long -0.020%, short +0.005%, Wednesday triple), applied at every price level ("current swap"), or none.
Sizing: fractional ounces for strategy quality; "XM" mode rounds down to whole ounces (0.01 lot) from $10,000.
Protocol frozen before the run: DEV 2003-2013, VAL 2014-2019, OOS 2020-2026. Retention: after costs with current
swap, positive CAGR in all three periods, PF > 1.1 in each, max drawdown < 40%, and above the random control.
"""
import json, math, os, time
import numpy as np, pandas as pd

os.makedirs("results/trend", exist_ok=True); T0 = time.time()
D = pd.read_csv("data/xauusd_d1_bid.csv"); D["time"] = pd.to_datetime(D.timestamp, unit="ms"); D = D.reset_index(drop=True)
o, h, l, c = (D[k].to_numpy(float) for k in ("open", "high", "low", "close")); n = len(D); t = D.time; yr = t.dt.year.to_numpy(); wd = t.dt.weekday.to_numpy()
SPREAD = np.array([{2024: 0.36, 2025: 0.38, 2026: 0.51}.get(y, 0.32) for y in yr])
SWAP_L, SWAP_S = -0.8684 / 4300.0, 0.1979 / 4300.0     # XM GOLD swap today as a fraction of notional per night (long -0.020%, short +0.005%), applied at every price level
PERIODS = {"DEV 2003-2013": ("2003-01-01", "2014-01-01"), "VAL 2014-2019": ("2014-01-01", "2020-01-01"), "OOS 2020-2026": ("2020-01-01", "2027-01-01")}
S = pd.Series
prev_c = np.roll(c, 1); prev_c[0] = c[0]
tr_ = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c))); atr20 = S(tr_).ewm(alpha=1 / 20, adjust=False).mean().to_numpy()
def roll_max(x, k): return S(x).rolling(k).max().shift(1).to_numpy()
def roll_min(x, k): return S(x).rolling(k).min().shift(1).to_numpy()
HH = {k: roll_max(h, k) for k in (10, 20, 55)}; LL = {k: roll_min(l, k) for k in (10, 20, 55)}
sma50, sma200 = S(c).rolling(50).mean().to_numpy(), S(c).rolling(200).mean().to_numpy()
lr = np.diff(np.log(c), prepend=np.log(c[0])); vol20 = S(lr).rolling(20).std().to_numpy() * math.sqrt(252)
month_end = (S(t.dt.month).shift(-1) != t.dt.month).to_numpy()
mret = {m: (c / S(c).shift(21 * m).to_numpy() - 1) for m in (1, 3, 6, 12)}

def new_state(start): return dict(eq=start, pos=0, oz=0.0, entry=0.0, stop=np.nan, t_in=None, curve=np.zeros(n), trades=[], swap=0.0, spread=0.0, skipped=0)

def open_pos(st, i, d, oz, frac):
    if not frac: oz = math.floor(oz)
    if oz <= 0: st["skipped"] += 1; return
    px = o[i] + SPREAD[i] if d == 1 else o[i]                     # ask for a buy, bid for a sell
    st.update(pos=d, oz=oz, entry=px, t_in=i); st["spread"] += SPREAD[i] * oz
def close_pos(st, i, px, why):
    d, oz = st["pos"], st["oz"]; pnl = (px - st["entry"]) * oz if d == 1 else (st["entry"] - px) * oz
    st["eq"] += pnl; st["trades"].append(dict(t_in=t[st["t_in"]], t_out=t[i], side="L" if d == 1 else "S", pnl=pnl, days=i - st["t_in"], why=why))
    st.update(pos=0, oz=0.0, stop=np.nan)
def night(st, i, swap_on):
    if st["pos"] != 0 and swap_on:
        s = st["oz"] * c[i] * (SWAP_L if st["pos"] == 1 else SWAP_S) * (3 if wd[i] == 2 else 1); st["eq"] += s; st["swap"] += s
def mark(st, i):
    u = 0.0
    if st["pos"] == 1: u = (c[i] - st["entry"]) * st["oz"]
    elif st["pos"] == -1: u = (st["entry"] - (c[i] + SPREAD[i])) * st["oz"]
    st["curve"][i] = st["eq"] + u

def breakout(n_in, n_out, stop_mult=2.0, risk=0.01, longs=True, shorts=True, swap_on=True, start=10000.0, frac=True, rng=None):
    st = new_state(start); pend_open = 0; pend_close = False
    for i in range(1, n):
        if pend_close and st["pos"] != 0: close_pos(st, i, o[i] if st["pos"] == 1 else o[i] + SPREAD[i], "exit_rule")
        pend_close = False
        if pend_open != 0 and st["pos"] == 0 and not np.isnan(atr20[i - 1]):
            d = pend_open; risk_px = stop_mult * atr20[i - 1]
            open_pos(st, i, d, st["eq"] * risk / risk_px, frac)
            if st["pos"] != 0: st["stop"] = st["entry"] - risk_px if d == 1 else st["entry"] + risk_px
        pend_open = 0
        if st["pos"] == 1 and l[i] <= st["stop"]: close_pos(st, i, min(o[i], st["stop"]), "stop")
        elif st["pos"] == -1 and h[i] + SPREAD[i] >= st["stop"]: close_pos(st, i, max(o[i] + SPREAD[i], st["stop"]), "stop")
        night(st, i, swap_on); mark(st, i)
        if st["pos"] == 1 and c[i] < LL[n_out][i]: pend_close = True
        if st["pos"] == -1 and c[i] > HH[n_out][i]: pend_close = True
        if st["pos"] == 0 or pend_close:
            sig = 1 if c[i] > HH[n_in][i] else (-1 if c[i] < LL[n_in][i] else 0)
            if sig != 0 and rng is not None: sig = rng.choice([-1, 1])
            if sig == 1 and longs: pend_open = 1
            elif sig == -1 and shorts: pend_open = -1
    return st

def state_rule(target, lev, swap_on=True, start=10000.0, frac=True, monthly=False):
    """target[i] in {-1,0,1} decided at close i; lev[i] = notional / equity; changes applied at the next open."""
    st = new_state(start); want = 0
    for i in range(1, n):
        if want != st["pos"]:
            if st["pos"] != 0: close_pos(st, i, o[i] if st["pos"] == 1 else o[i] + SPREAD[i], "signal")
            if want != 0 and not np.isnan(lev[i - 1]): open_pos(st, i, want, st["eq"] * lev[i - 1] / o[i], frac)
        night(st, i, swap_on); mark(st, i)
        if (not monthly) or month_end[i]:
            tg = target[i]
            if not np.isnan(tg): want = int(tg)
    return st

def stats(st, a, b):
    m = (t >= a) & (t < b) & (st["curve"] > 0); cv = st["curve"][m]
    if len(cv) < 30: return dict(n_days=int(m.sum()))
    r = np.diff(cv) / cv[:-1]; years = len(cv) / 252; dd = float(((np.maximum.accumulate(cv) - cv) / np.maximum.accumulate(cv)).max())
    tr = pd.DataFrame([x for x in st["trades"] if a <= str(x["t_in"])[:10] < b])
    out = dict(cagr=float((cv[-1] / cv[0]) ** (1 / years) - 1), vol=float(r.std() * math.sqrt(252)), sharpe=float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0, max_dd=dd, trades=int(len(tr)))
    if len(tr):
        w = tr[tr.pnl > 0].pnl.sum(); ls = -tr[tr.pnl <= 0].pnl.sum()
        out.update(win_rate=float((tr.pnl > 0).mean()), pf=float(w / ls) if ls > 0 else float("inf"), avg_days=float(tr.days.mean()), net_long=float(tr[tr.side == "L"].pnl.sum()), net_short=float(tr[tr.side == "S"].pnl.sum()), net=float(tr.pnl.sum()))
    return out

def evaluate(name, fn, **kw):
    row = dict(rule=name)
    for swap_on, tag in ((True, "swap"), (False, "noswap")):
        st = fn(swap_on=swap_on, **kw); row[tag] = {p: stats(st, a, b) for p, (a, b) in PERIODS.items()}; row[tag]["full"] = stats(st, "2003-01-01", "2027-01-01")
        row[tag]["swap_paid"] = float(st["swap"]); row[tag]["spread_paid"] = float(st["spread"])
        if swap_on:
            cv = st["curve"]; yrs = {}
            for y in range(2003, 2027):
                m = (yr == y) & (cv > 0)
                if m.sum() > 20: yrs[y] = float(cv[m][-1] / cv[m][0] - 1)
            row["by_year"] = yrs; row["curve"] = cv
    stx = fn(swap_on=True, frac=False, **kw); row["xm_rounded"] = {p: stats(stx, a, b) for p, (a, b) in PERIODS.items()}; row["xm_rounded"]["skipped"] = stx["skipped"]; row["xm_rounded"]["full"] = stats(stx, "2003-01-01", "2027-01-01")
    return row

RULES = []
RULES.append(evaluate("R1 Turtle 20/10 long+short", breakout, n_in=20, n_out=10))
RULES.append(evaluate("R1 Turtle 20/10 long only", breakout, n_in=20, n_out=10, shorts=False))
RULES.append(evaluate("R1 Turtle 20/10 short only", breakout, n_in=20, n_out=10, longs=False))
RULES.append(evaluate("R2 Turtle 55/20 long+short", breakout, n_in=55, n_out=20))
RULES.append(evaluate("R2 Turtle 55/20 long only", breakout, n_in=55, n_out=20, shorts=False))
lev_vt = np.minimum(0.10 / vol20, 3.0)
cross = np.where(np.isnan(sma200), np.nan, np.where(sma50 > sma200, 1, -1)); cross_l = np.where(np.isnan(sma200), np.nan, np.where(sma50 > sma200, 1, 0))
RULES.append(evaluate("R3 SMA 50/200 long+short, 10% vol target", state_rule, target=cross, lev=lev_vt))
RULES.append(evaluate("R3 SMA 50/200 long or flat, 10% vol target", state_rule, target=cross_l, lev=lev_vt))
for m in (1, 3, 6, 12):
    tg = np.where(np.isnan(mret[m]), np.nan, np.sign(mret[m])); RULES.append(evaluate(f"R4 TSMOM {m}-month, monthly, 10% vol target", state_rule, target=tg, lev=lev_vt, monthly=True))
sma10m = S(c).rolling(210).mean().to_numpy(); faber = np.where(np.isnan(sma10m), np.nan, np.where(c > sma10m, 1, 0))
RULES.append(evaluate("R5 Faber 10-month SMA long or flat, 1x", state_rule, target=faber, lev=np.ones(n), monthly=True))
RULES.append(evaluate("C1 buy and hold 1x", state_rule, target=np.ones(n), lev=np.ones(n)))
# random-direction control with R1 mechanics: mean over seeds
ctrl = []
for seed in range(50):
    st = breakout(20, 10, swap_on=True, rng=np.random.default_rng(seed)); ctrl.append({p: stats(st, a, b) for p, (a, b) in PERIODS.items()})
RULES.append(dict(rule="C2 random direction, R1 mechanics (mean of 50)", swap={p: {k: float(np.nanmean([x[p].get(k, np.nan) for x in ctrl])) for k in ("cagr", "sharpe", "max_dd", "pf", "trades", "win_rate")} for p in PERIODS}))

def keep(r):
    s = r.get("swap", {}); ok = all(p in s and s[p].get("cagr", -1) > 0 and s[p].get("pf", 0) > 1.1 and s[p].get("max_dd", 1) < 0.40 for p in PERIODS)
    ctl = RULES[-1]["swap"]; return ok and all(s[p]["cagr"] > ctl[p]["cagr"] for p in PERIODS)
for r in RULES[:-1]: r["retained"] = keep(r)
json.dump([{k: v for k, v in r.items() if k != "curve"} for r in RULES], open("results/trend/trend_lab.json", "w"), indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else float(x))
pd.DataFrame({r["rule"]: r["curve"] for r in RULES if "curve" in r}, index=t).to_csv("results/trend/curves.csv")
pd.set_option("display.width", 250)
rows = []
for r in RULES:
    for p in PERIODS:
        s = r["swap"][p]; rows.append(dict(rule=r["rule"], period=p[:3], cagr=s.get("cagr"), sharpe=s.get("sharpe"), dd=s.get("max_dd"), pf=s.get("pf"), trades=s.get("trades"), win=s.get("win_rate")))
T = pd.DataFrame(rows)
print("CAGR (current swap):"); print(T.pivot_table(index="rule", columns="period", values="cagr", sort=False).round(3).to_string())
print("\nMax drawdown:"); print(T.pivot_table(index="rule", columns="period", values="dd", sort=False).round(2).to_string())
print("\nProfit factor:"); print(T.pivot_table(index="rule", columns="period", values="pf", sort=False).round(2).to_string())
print("\nSharpe:"); print(T.pivot_table(index="rule", columns="period", values="sharpe", sort=False).round(2).to_string())
print("\nTrades:"); print(T.pivot_table(index="rule", columns="period", values="trades", sort=False).round(0).to_string())
print("\nRETAINED:", [r["rule"] for r in RULES if r.get("retained")])
print("\nno-swap CAGR OOS:", {r["rule"]: round(r["noswap"]["OOS 2020-2026"].get("cagr", float("nan")), 3) for r in RULES if "noswap" in r})
print("\nXM-rounded from $10k, full period CAGR / skipped:", {r["rule"]: (round(r["xm_rounded"]["full"].get("cagr", float("nan")), 3), r["xm_rounded"]["skipped"]) for r in RULES if "xm_rounded" in r})
print(f"done ({time.time()-T0:.0f}s)")
