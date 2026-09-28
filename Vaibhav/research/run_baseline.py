"""STEP 5: untouched baseline of SimpleSMA18Bot v1.00 on M1 / M5 / M15 / D1.

Views
  strategy      fixed 0.01 lot, no SL% filter, nominal $100,000 balance, no margin effects -> what the rules do, in $ per 0.01 lot
  ea_200        the EA exactly as provided on a $200 account (UseSLPercentFilter=true, MaximumSLPercent=1, LotSize 0.01, margin/stop-out)
  ea_200_nofilt $200 account, SL% filter off (the strategy exposed to the account)
Cost scenarios A_low / B_real / C_stress (see common.COST). Path assumption 'path' (main) and 'worst' (sensitivity).
"""
import json, os, sys, time
from dataclasses import replace

import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "baseline"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()

VIEWS = {"strategy": dict(start_balance=100000.0, margin_check=False, use_sl_pct=False),
         "ea_200": dict(start_balance=200.0, margin_check=True, use_sl_pct=True),
         "ea_200_nofilt": dict(start_balance=200.0, margin_check=True, use_sl_pct=False)}
PERIODS = {1: [("6y", "m1", C.DATA_START, C.DATA_END)], 5: [("6y", "m1", C.DATA_START, C.DATA_END)], 15: [("6y", "m1", C.DATA_START, C.DATA_END)],
           1440: [("6y", "m1", C.DATA_START, C.DATA_END), ("23y_h1path", "h1", C.D1_START, C.DATA_END), ("6y_h1path", "h1", C.DATA_START, C.DATA_END)]}

summary = {}
for tf, plist in PERIODS.items():
    name = C.TF_NAME[tf]
    summary[name] = {}
    for per, path, a, b in plist:
        summary[name][per] = {}
        months = E.months_between(a, b)
        for view, vkw in VIEWS.items():
            summary[name][per][view] = {}
            for cost, ckw in C.COST.items():
                for tm, tmname in ((0, "path"), (1, "worst")):
                    if tm == 1 and (view != "strategy" or cost != "B_real"):
                        continue
                    p = E.Params(tf_minutes=tf, path=path, start=a, end=b, trail_mode=tm, **vkw, **ckw)
                    tr, st = E.run(p)
                    m = E.metrics(tr, st, p.start_balance, months)
                    m["path_mode"] = tmname
                    key = cost if tm == 0 else cost + "_worst"
                    summary[name][per][view][key] = m
                    if tm == 0 and (view == "strategy" or cost == "B_real"):
                        tr2 = C.tag_regimes(tr)
                        tr2.to_csv(os.path.join(OUT, f"trades_{name}_{per}_{view}_{cost}.csv"), index=False)
                    if tm == 0:
                        C.log_experiment("P0-baseline", f"Untouched EA baseline ({view} view)", p, m, cost, f"{a}..{b} ({per})",
                                         filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                                         conclusion=f"net {m['net_profit']} PF {m['profit_factor']} WR {m['win_rate']} DD {m['max_dd_usd']} trades {m['trades']}")
                    print(f"{name:3} {per:11} {view:14} {key:14} trades {m['trades']:5} net {m['net_profit']:10.2f} PF {m['profit_factor']!s:>6} WR {m['win_rate']!s:>5} DD {m['max_dd_usd']:8.2f} ruin {m.get('ruin')} ({time.time()-t0:.0f}s)", flush=True)

# ------------------------------------------------------------------ per-year breakdown (strategy view, realistic costs)
years = {}
for tf in (1, 5, 15, 1440):
    name = C.TF_NAME[tf]
    per = "6y"
    tr = pd.read_csv(os.path.join(OUT, f"trades_{name}_{per}_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    if len(tr) == 0:
        continue
    tr["year"] = tr["time_out"].dt.year
    g = tr.groupby("year")
    yt = pd.DataFrame({"trades": g.size(), "net": g["pnl"].sum().round(2), "pf": g["pnl"].apply(lambda s: round(s[s > 0].sum() / max(-s[s < 0].sum(), 1e-9), 2)),
                       "win_rate": g["pnl"].apply(lambda s: round(100 * (s > 0).mean(), 1)), "avg_risk": g["risk_usd"].mean().round(2),
                       "giveback_avg": g["giveback_usd"].mean().round(2), "p2l_2usd": g.apply(lambda x: int(((x["mfe_usd"] >= 2) & (x["pnl"] < 0)).sum()))})
    yt.to_csv(os.path.join(OUT, f"by_year_{name}.csv"))
    years[name] = yt.to_dict("index")
summary["by_year"] = years

# ------------------------------------------------------------------ D1: 23-year per-year table and the "3x in 1.5 years" window scan
tr = pd.read_csv(os.path.join(OUT, "trades_D1_23y_h1path_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
tr["year"] = tr["time_out"].dt.year
g = tr.groupby("year")
yt = pd.DataFrame({"trades": g.size(), "net": g["pnl"].sum().round(2), "pf": g["pnl"].apply(lambda s: round(s[s > 0].sum() / max(-s[s < 0].sum(), 1e-9), 2)),
                   "win_rate": g["pnl"].apply(lambda s: round(100 * (s > 0).mean(), 1)), "avg_risk": g["risk_usd"].mean().round(2), "exits_be": g["exit_reason"].apply(lambda s: int((s == "SL_breakeven").sum()))})
yt.to_csv(os.path.join(OUT, "by_year_D1_23y.csv"))
summary["D1_23y_by_year"] = yt.to_dict("index")


def window_scan(tr: pd.DataFrame, months: int = 18, start_balance: float = 200.0) -> dict:
    """Best / worst / median growth of a fixed-lot $200 account over every rolling window of `months` (stepping 1 month)."""
    if len(tr) == 0:
        return {}
    tr = tr.sort_values("time_out")
    starts = pd.date_range(tr["time_in"].min().normalize().replace(day=1), tr["time_out"].max() - pd.DateOffset(months=months), freq="MS")
    rows = []
    for s in starts:
        e = s + pd.DateOffset(months=months)
        w = tr[(tr["time_in"] >= s) & (tr["time_out"] < e)]
        net = float(w["pnl"].sum())
        bal = start_balance + w["pnl"].cumsum()
        peak = np.maximum.accumulate(np.concatenate([[start_balance], bal.to_numpy()]))[1:] if len(w) else np.array([start_balance])
        dd = float((peak - bal.to_numpy()).max()) if len(w) else 0.0
        rows.append({"start": str(s.date()), "end": str(e.date()), "trades": int(len(w)), "net": round(net, 2), "growth_x": round((start_balance + net) / start_balance, 2), "max_dd": round(dd, 2), "min_balance": round(float(min(start_balance, (start_balance + w["pnl"].cumsum()).min())) if len(w) else start_balance, 2)})
    d = pd.DataFrame(rows)
    return {"windows": int(len(d)), "best": d.loc[d["growth_x"].idxmax()].to_dict(), "worst": d.loc[d["growth_x"].idxmin()].to_dict(), "median_growth_x": float(d["growth_x"].median()),
            "share_windows_ge_3x": round(float((d["growth_x"] >= 3).mean()), 3), "share_windows_losing": round(float((d["growth_x"] < 1).mean()), 3),
            "share_windows_ruined": round(float((d["min_balance"] <= 0).mean()), 3), "table": rows}


scan = {}
for per in ("6y", "23y_h1path"):
    trd = pd.read_csv(os.path.join(OUT, f"trades_D1_{per}_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    scan[per] = window_scan(trd, 18)
    pd.DataFrame(scan[per]["table"]).to_csv(os.path.join(OUT, f"d1_window18m_{per}.csv"), index=False)
    scan[per].pop("table")
summary["D1_18month_window_scan"] = scan

C.save_json(summary, "baseline/summary.json")

# ------------------------------------------------------------------ markdown
L = ["# Baseline: SimpleSMA18Bot v1.00 untouched", "", f"Data: Dukascopy XAUUSD M1 bid in XM server time, {C.DATA_START} to {C.DATA_END} (M1/M5/M15/D1); D1 also 2003-05 to 2026-09 on an H1 intrabar path. "
     "Money per 0.01 lot (1 oz): $1 of price = $1. Costs: A_low = 25-pt spread, no slippage, no swap; B_real = XM spread by year x hour (M1-equivalent), 10-pt slippage, XM swap; "
     "C_stress = 1.5x spread, 30-pt slippage, swap.", ""]


def table(rows, cols, hdr):
    L.append("| " + " | ".join(hdr) + " |"); L.append("|" + "|".join(["---"] + ["---:"] * (len(hdr) - 1)) + "|")
    for r in rows:
        L.append("| " + " | ".join(str(x) for x in r) + " |")
    L.append("")


for name in ("M1", "M5", "M15", "D1"):
    for per in summary[name]:
        L.append(f"## {name} ({per})"); L.append("")
        rows = []
        for view in VIEWS:
            for cost, m in summary[name][per][view].items():
                rows.append([view, cost, m["trades"], m["net_profit"], m.get("profit_factor"), m.get("win_rate"), m.get("expectancy"), m.get("max_dd_usd"), m.get("max_dd_pct"),
                             m.get("end_balance"), m.get("ruin"), m.get("avg_risk_usd"), m.get("blocked_sl_pct"), m.get("giveback_avg"), m.get("profit_to_loss_2usd")])
        table(rows, None, ["view", "cost", "trades", "net $", "PF", "win %", "exp $", "maxDD $", "maxDD %", "end bal", "ruin", "avg risk $", "blocked SL%", "giveback avg", "P->L >$2"])
        m = summary[name][per]["strategy"]["B_real"]
        L.append(f"Exit mix (strategy, B_real): {m.get('exit_mix')}; pending placed {m.get('pending_placed')}, cancelled {m.get('pending_cancelled')}, filled {m.get('filled')}, "
                 f"rejected as invalid price {m.get('rejected_invalid_price')}; SL hit rate {m.get('sl_hit_rate')}%; avg hold {m.get('avg_hold_min')} min; "
                 f"avg MFE ${m.get('avg_mfe_usd')} / MAE ${m.get('avg_mae_usd')}; t-stat {m.get('t_stat')}; 95% CI of mean trade {m.get('mean_trade_ci95')}; swap total {m.get('swap_total')}.")
        L.append("")
L.append("## By year (strategy view, B_real)"); L.append("")
for name, yt in years.items():
    L.append(f"### {name}"); L.append("")
    table([[y] + [v[c] for c in ("trades", "net", "pf", "win_rate", "avg_risk", "giveback_avg", "p2l_2usd")] for y, v in yt.items()], None, ["year", "trades", "net $", "PF", "win %", "avg risk $", "giveback avg $", "P->L >$2"])
L.append("### D1 2003-2026 (H1 path)"); L.append("")
table([[y] + [v[c] for c in ("trades", "net", "pf", "win_rate", "avg_risk", "exits_be")] for y, v in summary["D1_23y_by_year"].items()], None, ["year", "trades", "net $", "PF", "win %", "avg risk $", "BE exits"])
L.append("## D1: rolling 18-month windows, $200 fixed 0.01 lot (strategy view, B_real)"); L.append("")
for per, s in scan.items():
    L.append(f"- {per}: {s['windows']} windows; best {s['best']['growth_x']}x ({s['best']['start']} to {s['best']['end']}, net ${s['best']['net']}, DD ${s['best']['max_dd']}); worst {s['worst']['growth_x']}x ({s['worst']['start']}, net ${s['worst']['net']}); median {s['median_growth_x']}x; share >= 3x: {s['share_windows_ge_3x']}; share losing: {s['share_windows_losing']}; share ruined: {s['share_windows_ruined']}")
with open(os.path.join(OUT, "BASELINE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
