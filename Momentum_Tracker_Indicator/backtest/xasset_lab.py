"""Report C: does information in other markets change the odds of gold's next move?
Lead/lag at 1..60 bars, shock response, divergence, regime-conditional shocks, on H1 (5 years) and M15 (12 months),
with a monetisation test (gold 1 ATR stop / 2 ATR target after a shock in X, net of XM spread).
All series are XM bars in server time; gold = XM GOLD H1 / M15 exports.
"""
import json, os, glob, math
import numpy as np, pandas as pd
import twk_engine as E

os.makedirs("results/phase13", exist_ok=True)
PER = {"DEV": (pd.Timestamp("2021-09-01"), pd.Timestamp("2024-01-01")), "VAL": (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), "OOS": (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-26"))}
def load(path):
    d = pd.read_csv(path, parse_dates=["time"]).drop_duplicates("time").set_index("time").sort_index()
    return d[["open", "high", "low", "close", "tick_volume", "spread"]]
def period_of(idx):
    return np.select([idx < PER["DEV"][1], idx < PER["VAL"][1]], ["DEV", "VAL"], "OOS")

def analyse(tf, gold_path, assets, horizons, split_dates=None):
    g = load(gold_path); g["ret"] = np.log(g.close).diff()
    g["atr"] = E.rma(E.true_range(g.high.to_numpy(float), g.low.to_numpy(float), g.close.to_numpy(float), True), 14)
    out = []
    for name, path in assets.items():
        if not os.path.exists(path): continue
        x = load(path); x["ret"] = np.log(x.close).diff()
        j = g.join(x[["ret", "close"]], rsuffix="_x", how="inner")
        j = j[j.index >= "2021-09-01"]
        if len(j) < 500: continue
        j["sig_x"] = j.ret_x.rolling(100, min_periods=50).std()
        per = period_of(j.index) if split_dates is None else np.where(j.index < split_dates, "FIRST", "SECOND")
        rows = []
        for k in horizons:
            fwd = np.log(j.close).shift(-k) - np.log(j.close)           # gold's forward k-bar log return
            fwd_atr = (j.close.shift(-k) - j.close) / j.atr                # in ATR units
            for lag_name, xr in (("X(t) -> gold(t+1..t+k)", j.ret_x), ("X(t-2..t) -> gold", j.ret_x.rolling(3).sum())):
                for p in (["DEV", "VAL", "OOS"] if split_dates is None else ["FIRST", "SECOND"]):
                    m = (per == p) & xr.notna() & fwd.notna()
                    if m.sum() < 200: continue
                    rho = pd.Series(xr[m]).rank().corr(pd.Series(fwd[m]).rank())
                    shock = m & (xr.abs() > 2 * j.sig_x)
                    up = shock & (xr > 0); dn = shock & (xr < 0)
                    rows.append(dict(asset=name, tf=tf, lag=lag_name, k=k, period=p, n=int(m.sum()), spearman=round(float(rho), 4),
                                     shock_n=int(shock.sum()), gold_after_X_up_atr=round(float(fwd_atr[up].mean()), 3) if up.sum() >= 20 else None, gold_after_X_down_atr=round(float(fwd_atr[dn].mean()), 3) if dn.sum() >= 20 else None,
                                     shock_hit_same_dir=round(float(((np.sign(fwd[shock]) == np.sign(xr[shock])).mean())), 3) if shock.sum() >= 20 else None))
        out += rows
    return pd.DataFrame(out)

H1 = {"SILVER": "data/xasset/SILVER_H1.csv.gz", "EURUSD": "data/xasset/EURUSD_H1.csv.gz", "USDJPY": "data/xasset/USDJPY_H1.csv.gz", "US500": "data/xasset/US500Cash_H1.csv.gz",
      "US100": "data/xasset/US100Cash_H1.csv.gz", "OIL": "data/xasset/OILCash_H1.csv.gz", "BTCUSD": "data/xasset/BTCUSD_H1.csv.gz", "XPTUSD": "data/xasset/XPTUSD_H1.csv.gz"}
M15 = {"SILVER": "data/xasset/SILVER_M15.csv.gz", "EURUSD": "data/xasset/EURUSD_M15.csv.gz", "USDJPY": "data/xasset/USDJPY_M15.csv.gz", "US500": "data/xasset/US500Cash_M15.csv.gz"}
R1 = analyse("H1", "data/xm_GOLD_H1.csv.gz", H1, [1, 3, 5, 10, 15, 30, 60])
R15 = analyse("M15", "data/xm_GOLD_M15.csv.gz", M15, [1, 3, 5, 10, 15, 30, 60], split_dates=pd.Timestamp("2026-03-15"))
R = pd.concat([R1, R15], ignore_index=True); R.to_csv("results/phase13/xasset_leadlag.csv", index=False)

# monetisation: after a shock in X, trade gold in the implied direction (sign map) with 1 ATR stop / 2 ATR target, net of spread, H1
SIGN = {"SILVER": 1, "XPTUSD": 1, "EURUSD": 1, "USDJPY": -1, "US500": 0, "US100": 0, "OIL": 0, "BTCUSD": 0}   # 0 = test both, decided on DEV sign
g = load("data/xm_GOLD_H1.csv.gz"); g["atr"] = E.rma(E.true_range(g.high.to_numpy(float), g.low.to_numpy(float), g.close.to_numpy(float), True), 14)
gh, gl, gc, go, gs, gatr = (g[k].to_numpy(float) for k in ("high", "low", "close", "open", "spread", "atr")); gt = g.index
def trade(i, side, S=1.0, T=2.0, H=48):
    """enter at next H1 open, stop S ATR, target T ATR, worst case inside a bar; returns R."""
    if i + 2 >= len(gc) or np.isnan(gatr[i]) or gatr[i] <= 0: return np.nan
    spr = gs[i + 1] * 0.01; fill = go[i + 1] + (spr if side == 1 else 0); u = gatr[i]
    for j in range(i + 1, min(i + 1 + H, len(gc))):
        if side == 1:
            if gl[j] <= fill - S * u: return -1.0
            if gh[j] >= fill + T * u: return T / S
        else:
            if gh[j] + spr >= fill + S * u: return -1.0
            if gl[j] + spr <= fill - T * u: return T / S
    j = min(i + H, len(gc) - 1); return ((gc[j] - fill) if side == 1 else (fill - gc[j] - spr)) / (S * u)
mon = []
for name, path in H1.items():
    if not os.path.exists(path): continue
    x = load(path); x["ret"] = np.log(x.close).diff(); x["sig"] = x.ret.rolling(100, min_periods=50).std()
    j = g.join(x[["ret", "sig"]].rename(columns={"ret": "ret_x", "sig": "sig_x"}), how="inner"); j = j[j.index >= "2021-09-01"]
    shock = j[(j.ret_x.abs() > 2 * j.sig_x)]
    pos = {ts: k for k, ts in enumerate(gt)}
    for sgn_name, sgn in (("with sign map", SIGN[name] if SIGN[name] != 0 else 1), ("against", -(SIGN[name] if SIGN[name] != 0 else 1))):
        rs = []; pers = []
        for ts, r in shock.iterrows():
            i = pos.get(ts)
            if i is None: continue
            side = sgn * (1 if r.ret_x > 0 else -1); rs.append(trade(i, side)); pers.append(period_of(pd.DatetimeIndex([ts]))[0])
        rs = np.array(rs, float); pers = np.array(pers)
        row = dict(asset=name, rule=sgn_name, n=int(np.isfinite(rs).sum()))
        for p in ("DEV", "VAL", "OOS"):
            m = (pers == p) & np.isfinite(rs); rr = rs[m]
            row[f"{p}_n"] = int(m.sum()); row[f"{p}_exp"] = round(float(rr.mean()), 3) if len(rr) else None; row[f"{p}_pf"] = round(float(rr[rr > 0].sum() / max(1e-9, -rr[rr < 0].sum())), 2) if len(rr) else None
        mon.append(row)
M = pd.DataFrame(mon); M.to_csv("results/phase13/xasset_monetisation.csv", index=False)
json.dump(dict(leadlag=R.to_dict("records"), monetisation=mon), open("results/phase13/xasset.json", "w"), indent=1, default=float)
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)
print("LEAD/LAG H1, k=1 and k=5, per period:"); print(R1[(R1.k.isin([1, 5])) & (R1.lag.str.startswith("X(t) ->"))][["asset", "k", "period", "n", "spearman", "shock_n", "gold_after_X_up_atr", "gold_after_X_down_atr", "shock_hit_same_dir"]].to_string(index=False))
print("\nstrongest |spearman| rows (H1):"); print(R1.reindex(R1.spearman.abs().sort_values(ascending=False).index).head(15)[["asset", "lag", "k", "period", "n", "spearman"]].to_string(index=False))
if len(R15): print("\nM15 (12 months), k=1,3,5:"); print(R15[(R15.k.isin([1, 3, 5])) & (R15.lag.str.startswith("X(t) ->"))][["asset", "k", "period", "n", "spearman", "shock_n", "gold_after_X_up_atr", "gold_after_X_down_atr"]].to_string(index=False))
print("\nMONETISATION (H1 shocks, 1 ATR / 2 ATR, net):"); print(M.to_string(index=False))
