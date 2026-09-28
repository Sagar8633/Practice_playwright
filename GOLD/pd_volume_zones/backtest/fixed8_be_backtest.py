"""
fixed8_be_backtest.py - the user's rule of 26-Sep-2026 on all data on disk:
  same V1 entries (POC tap + confirmation close), stop = entry -/+ 8 USD, target = entry +/- 24 USD,
  once the trade is +8 USD in profit the stop moves to entry ("cost to cost"), then wait for the target.
  0.02 lot on XM GOLD = 2 oz, so 16 USD risk and 48 USD target per trade. One position at a time.
Execution: the V4 conservative M1 walker (stop checked before target inside a candle, the break-even
move applies from the candle after +8 USD was reached, gaps fill at the open). Costs: one spread per
trade (0.25-0.50 USD/oz by year, as in V1-V4), shown separately.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import exit_sim as X
import pdvz_engine as E

OZ = 2.0  # 0.02 lot
SL_USD = 8.0
RR = 3.0
OUT = "results/fixed8"
os.makedirs(OUT, exist_ok=True)


def metrics(tr):
    R = tr.result_R.values
    net = tr.net_R.values
    risk = tr.risk_pts.values
    usd = R * risk * OZ
    usd_net = net * risk * OZ
    gp, gl = R[R > 0].sum(), -R[R < 0].sum()
    cum = np.cumsum(usd_net)
    streak = best = 0
    for x in R:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return dict(n=int(len(R)), wins=int((R > 0).sum()), be=int((abs(R) < 1e-9).sum()), losses=int((R < 0).sum()),
                wr=float((R > 0).mean()), gross_R=float(R.sum()), net_R=float(net.sum()), avg_net_R=float(net.mean()),
                pf=float(gp / gl) if gl > 0 else float("inf"), gross_usd=float(usd.sum()), cost_usd=float((usd - usd_net).sum()),
                net_usd=float(usd_net.sum()), max_dd_usd=float((np.maximum.accumulate(cum) - cum).max()) if len(cum) else 0.0,
                longest_losing=int(best), median_hold_min=float(tr.minutes_held.median()) if len(tr) else np.nan)


def main():
    files = sorted(f for f in os.listdir(E.CHUNK_DIR) if f.startswith("bid_"))
    D = E.prepare(E.load_m1([f"{E.CHUNK_DIR}/{f}" for f in files]))
    base = dict(simulate_skipped=False, fixed_sl_usd=SL_USD, rr=RR)
    runs = {
        "Rule: 8 USD stop, 24 USD target, stop to entry at +8 USD": dict(base, exit_spec=dict(target_R=3.0, be=(1.0, 0.0))),
        "Same without the break-even move": dict(base, exit_spec=dict(target_R=3.0)),
        "V1 rule for reference (rectangle stop, 3R)": dict(simulate_skipped=False),
    }
    out = {}
    trades = {}
    for name, p in runs.items():
        tr, _, info = E.run(D, p, verbose=False)
        tr = tr[tr.exit_reason.isin(["SL", "TP", "TSL"])].reset_index(drop=True)
        trades[name] = tr
        m = metrics(tr)
        m["years"] = {int(y): metrics(g) for y, g in tr.groupby("year")}
        last12 = tr[tr.t_ms >= tr.t_ms.max() - 365 * 86400000]
        m["last_12m"] = metrics(last12)
        m["exits"] = tr.exit_reason.value_counts().to_dict()
        out[name] = m
        print(f"{name[:58]:58s} n={m['n']} wr={m['wr']:.1%} netR={m['net_R']:+.1f} netUSD={m['net_usd']:+.0f} dd={m['max_dd_usd']:.0f}")
    main_tr = trades["Rule: 8 USD stop, 24 USD target, stop to entry at +8 USD"]
    main_tr.to_csv(f"{OUT}/trade_log_fixed8_be.csv", index=False)
    # break-even decomposition on the no-BE entries (independent trades)
    nb = trades["Same without the break-even move"]
    tf_ms = D["tf_min"] * 60000
    killed = saved = 0
    for r in nb.itertuples():
        i5 = int(np.searchsorted(D["t"], r.t_ms))
        j0 = int(np.searchsorted(D["m1t"], r.t_ms + tf_ms))
        w = X.walk(r.side, r.entry, r.sl, r.risk_pts, j0, i5, D, dict(target_R=3.0, be=(1.0, 0.0)), atr=r.atr14)
        if r.result_R > 0 and w["R"] <= 0.001:
            killed += 1
        elif r.result_R < 0 and w["R"] >= -0.001:
            saved += 1
    out["be_decomposition"] = dict(killed_winners=killed, saved_losers=saved, net_effect_R=saved * 1.0 - killed * 3.0)
    json.dump(out, open(f"{OUT}/summary.json", "w"), indent=1, default=str)

    # ---- report
    first = str(pd.Timestamp(D["t"][0], unit="ms").date())
    last = str(pd.Timestamp(D["t"][-1], unit="ms").date())
    L = []
    w = L.append
    w("# Backtest - fixed 8 USD stop, 24 USD target, stop to entry at +8 USD, 0.02 lot\n")
    w(f"Data: all {len(files)} monthly Dukascopy XAUUSD M1 files on disk, {first} to {last} (UTC), 5-min entries as in V1 "
      "(previous-day rectangles, POC tap, confirmation close). Only the stop and target changed: stop = entry -/+ 8 USD, target = "
      "entry +/- 24 USD, and once price is 8 USD in profit the stop moves to the entry price. One position at a time. 0.02 lot = 2 oz, so "
      "one full loss = -16 USD, one target = +48 USD. Costs = one spread per trade (0.25-0.50 USD/oz by year, x 2 oz), shown separately.\n")
    w("Execution rule: the stop is checked before the target inside every 1-minute candle; the break-even move is applied from the candle "
      "after +8 USD was reached; gaps fill at the open (the most conservative reading of the data).\n")
    w("| Variant | Trades | Wins / BE / Losses | Win rate | Gross R | Net R | Avg net R | PF | Gross USD | Spread USD | Net USD | Max DD USD | Longest losing run | Median hold (min) |\n"
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, m in out.items():
        if name == "be_decomposition":
            continue
        w(f"| {name} | {m['n']} | {m['wins']} / {m['be']} / {m['losses']} | {m['wr']:.1%} | {m['gross_R']:+.1f} | {m['net_R']:+.1f} | {m['avg_net_R']:+.3f} | "
          f"{m['pf']:.2f} | {m['gross_usd']:+,.0f} | {m['cost_usd']:,.0f} | {m['net_usd']:+,.0f} | {m['max_dd_usd']:,.0f} | {m['longest_losing']} | {m['median_hold_min']:.0f} |")
    w("")
    main = out["Rule: 8 USD stop, 24 USD target, stop to entry at +8 USD"]
    w("## The rule, year by year\n")
    w("| Year | Trades | Win rate | Break-even exits | Net R | Net USD | Max DD USD |\n|---|---|---|---|---|---|---|")
    for y, m in main["years"].items():
        w(f"| {y} | {m['n']} | {m['wr']:.1%} | {m['be']} | {m['net_R']:+.1f} | {m['net_usd']:+,.0f} | {m['max_dd_usd']:,.0f} |")
    m = main["last_12m"]
    w(f"| last 12 months | {m['n']} | {m['wr']:.1%} | {m['be']} | {m['net_R']:+.1f} | {m['net_usd']:+,.0f} | {m['max_dd_usd']:,.0f} |")
    w("")
    w("## Year by year for the two comparison variants (net USD)\n")
    w("| Year | Same without break-even | V1 rectangle stop, 3R |\n|---|---|---|")
    for y in main["years"]:
        a = out["Same without the break-even move"]["years"].get(y, {})
        b = out["V1 rule for reference (rectangle stop, 3R)"]["years"].get(y, {})
        w(f"| {y} | {a.get('net_usd', 0):+,.0f} ({a.get('n', 0)} trades) | {b.get('net_usd', 0):+,.0f} ({b.get('n', 0)} trades) |")
    w("")
    d = out["be_decomposition"]
    w(f"Break-even effect (same entries, independent trades): the move to entry saved {d['saved_losers']} trades that would have lost 16 USD and "
      f"killed {d['killed_winners']} trades that would have reached +48 USD; net {d['net_effect_R']:+.0f}R = {d['net_effect_R'] * SL_USD * OZ:+,.0f} USD before costs.\n")
    w("Exit reasons for the rule: " + ", ".join(f"{k} {v}" for k, v in main["exits"].items()) + " (TSL = stopped at entry after the break-even move).\n")
    open("FIXED_8USD_BE_BACKTEST.md", "w", encoding="utf-8").write("\n".join(L))
    print("report written")


if __name__ == "__main__":
    main()
