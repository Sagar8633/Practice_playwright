"""Follow-up to trend_bot_lab.py for the two retained rules (Turtle 20/10 and 55/20, long only): linear risk scaling
(2%, 3% per trade), the two systems run side by side on split capital, the minimum account for XM's 0.01-lot step,
and gold's own yearly return with and without the long swap, for the control. Writes results/trend/followup.json."""
import contextlib, io, json, math
import numpy as np, pandas as pd
with contextlib.redirect_stdout(io.StringIO()):
    import trend_bot_lab as L

out = dict(scaled=[], xm=[], gold_by_year={}, combined={})
for risk in (0.01, 0.02, 0.03):
    for name, n_in, n_out in (("Turtle 20/10 long only", 20, 10), ("Turtle 55/20 long only", 55, 20)):
        st = L.breakout(n_in, n_out, shorts=False, risk=risk, swap_on=True)
        row = dict(rule=name, risk=risk, periods={p: L.stats(st, a, b) for p, (a, b) in L.PERIODS.items()}, full=L.stats(st, "2003-01-01", "2027-01-01"))
        cv = st["curve"]; row["by_year"] = {int(y): float(cv[(L.yr == y) & (cv > 0)][-1] / cv[(L.yr == y) & (cv > 0)][0] - 1) for y in range(2003, 2027) if ((L.yr == y) & (cv > 0)).sum() > 20}
        row["swap_paid"] = st["swap"]; row["spread_paid"] = st["spread"]; row["final_equity_from_10k"] = float(cv[cv > 0][-1])
        out["scaled"].append(row)
        # two systems on split capital: half the equity each, same risk per trade on its half
        if name.startswith("Turtle 55"):
            s1 = L.breakout(20, 10, shorts=False, risk=risk, swap_on=True, start=5000.0); s2 = L.breakout(55, 20, shorts=False, risk=risk, swap_on=True, start=5000.0)
            comb = dict(curve=s1["curve"] + s2["curve"], trades=s1["trades"] + s2["trades"])
            out["combined"][str(risk)] = {p: L.stats(comb, a, b) for p, (a, b) in L.PERIODS.items()}; out["combined"][str(risk)]["full"] = L.stats(comb, "2003-01-01", "2027-01-01")
# minimum account: XM rounds to whole ounces (0.01 lot); risk per ounce = 2 x ATR20
atr_now = float(L.atr20[-1]); atr_2026 = float(np.median(L.atr20[L.yr == 2026]))
out["min_account"] = dict(atr20_now=atr_now, risk_per_oz_now=2 * atr_now, atr20_median_2026=atr_2026, needed_for_1pct=2 * atr_2026 / 0.01, needed_for_2pct=2 * atr_2026 / 0.02, needed_for_3pct=2 * atr_2026 / 0.03)
for start in (2000.0, 5000.0, 10000.0, 20000.0, 50000.0):
    for risk in (0.01, 0.02):
        st = L.breakout(55, 20, shorts=False, risk=risk, swap_on=True, start=start, frac=False)
        f = L.stats(st, "2020-01-01", "2027-01-01"); out["xm"].append(dict(start=start, risk=risk, skipped_trades=st["skipped"], oos_cagr=f.get("cagr"), oos_trades=f.get("trades"), oos_dd=f.get("max_dd")))
# gold itself, per year, and net of the long swap at today's rate (7.4% a year)
for y in range(2003, 2027):
    m = L.yr == y
    if m.sum() > 20: out["gold_by_year"][y] = dict(price=float(L.c[m][-1] / L.c[m][0] - 1), net_of_swap=float(L.c[m][-1] / L.c[m][0] - 1 - 0.0202 * 365 / 100 * (m.sum() / 252)))
out["gold_full"] = dict(cagr=float((L.c[-1] / L.c[0]) ** (252 / len(L.c)) - 1), max_dd=float(((np.maximum.accumulate(L.c) - L.c) / np.maximum.accumulate(L.c)).max()))
json.dump(out, open("results/trend/followup.json", "w"), indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else (float(x) if isinstance(x, (np.floating, np.integer)) else str(x)))
pd.set_option("display.width", 250)
rows = [dict(rule=r["rule"], risk=r["risk"], period=p[:3], cagr=s.get("cagr"), dd=s.get("max_dd"), pf=s.get("pf"), sharpe=s.get("sharpe"), trades=s.get("trades"), win=s.get("win_rate")) for r in out["scaled"] for p, s in r["periods"].items()]
T = pd.DataFrame(rows)
for k in ("cagr", "dd", "pf", "sharpe"):
    print(f"\n{k}:"); print(T.pivot_table(index=["rule", "risk"], columns="period", values=k, sort=False).round(3).to_string())
print("\nBY YEAR (%), 55/20 long only:"); print(pd.DataFrame({f"{r['risk']*100:.0f}% risk": {y: round(v * 100, 1) for y, v in r["by_year"].items()} for r in out["scaled"] if r["rule"].startswith("Turtle 55")}).T.to_string())
print("\nfinal equity from $10k (2003-2026):", {f"{r['rule']} {r['risk']*100:.0f}%": round(r["final_equity_from_10k"]) for r in out["scaled"]})
print("\nCOMBINED (both systems, half capital each):"); print(pd.DataFrame({k: {p: round(v[p].get("cagr", float("nan")), 3) for p in list(L.PERIODS) + ["full"]} for k, v in out["combined"].items()}).T.to_string())
print("\nMIN ACCOUNT:", {k: round(v, 1) for k, v in out["min_account"].items()}); print(pd.DataFrame(out["xm"]).round(3).to_string(index=False))
print("\nGOLD by year (price %, net of swap %):", {y: (round(v["price"] * 100), round(v["net_of_swap"] * 100)) for y, v in out["gold_by_year"].items()}); print("gold full:", out["gold_full"])
