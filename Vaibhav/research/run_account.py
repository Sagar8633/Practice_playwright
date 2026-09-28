"""STEP 21 / section 21: $200 account analysis. Separates strategy performance from account survivability.

Facts from the XM Global MT5 terminal (2026-09-26): GOLD digits 2, contract 100, volume_min 0.01, volume_step 0.01,
leverage 1:1000, margin per 0.01 lot = price * 100 * 0.01 / 1000 (= $4.29 at $4,286), stop-out at 20% margin level,
swap long -86.84 / short +19.79 points per night (x3 Wednesday), no commission.
"""
import os
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "account"); os.makedirs(OUT, exist_ok=True)
BASE = os.path.join(C.RES, "baseline")
LEVERAGE = 1000.0; STOP_OUT = 0.20; MARGIN_CALL = 0.50
res = {"broker": {"symbol": "GOLD (XM Global MT5)", "min_lot": 0.01, "lot_step": 0.01, "contract_oz_per_lot": 100, "usd_per_usd_move_per_0.01_lot": 1.0,
                  "leverage": LEVERAGE, "margin_per_0.01_lot_at_4286": round(4286 * 100 * 0.01 / LEVERAGE, 2), "margin_per_0.01_lot_at_2000": round(2000 * 100 * 0.01 / LEVERAGE, 2),
                  "stop_out_level": STOP_OUT, "margin_call_level": MARGIN_CALL, "swap_long_usd_per_night_0.01": round(-86.84 * 0.01 * 100 * 0.01, 3), "swap_short_usd_per_night_0.01": round(19.79 * 0.01 * 100 * 0.01, 3)}}

rows = []
for name in ("M1", "M5", "M15", "D1"):
    tr = pd.read_csv(os.path.join(BASE, f"trades_{name}_6y_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    if len(tr) == 0:
        continue
    r = tr["risk_usd"]
    d = {"tf": name, "trades": int(len(tr)),
         "risk_usd_median": round(float(r.median()), 2), "risk_usd_p90": round(float(r.quantile(0.9)), 2), "risk_usd_max": round(float(r.max()), 2),
         "risk_pct_of_200_median": round(float(100 * r.median() / 200), 1), "risk_pct_of_200_p90": round(float(100 * r.quantile(0.9) / 200), 1),
         "share_trades_risk_gt_1pct_of_200": round(float((r > 2.0).mean()), 3), "share_trades_risk_gt_5pct_of_200": round(float((r > 10.0).mean()), 3), "share_trades_risk_gt_20pct_of_200": round(float((r > 40.0).mean()), 3),
         "min_account_for_1pct_rule_median_trade": round(float(100 * r.median()), 0), "min_account_for_1pct_rule_p90_trade": round(float(100 * r.quantile(0.9)), 0),
         "min_account_for_2pct_rule_median_trade": round(float(50 * r.median()), 0),
         "max_simultaneous_exposure": "1 position x 0.01 lot (EA allows one pending or one position at a time)",
         "margin_used_per_trade": round(float((tr["entry"] * 100 * 0.01 / LEVERAGE).median()), 2),
         "worst_single_loss_usd": round(float(tr["pnl"].min()), 2), "worst_loss_pct_of_200": round(float(-100 * tr["pnl"].min() / 200), 1),
         "max_consecutive_losses": None, "losing_streak_usd": None}
    pnl = tr["pnl"].to_numpy()
    cl = ml = 0; worst_streak = 0.0; cur = 0.0
    for x in pnl:
        if x < 0: cl += 1; cur += x
        else: cl = 0; cur = 0.0
        ml = max(ml, cl); worst_streak = min(worst_streak, cur)
    d["max_consecutive_losses"] = ml; d["losing_streak_usd"] = round(worst_streak, 2)
    mc = E.monte_carlo(pnl, 200.0, n=3000, seed=5)
    d["mc_shuffle_p_ruin_200"] = mc["shuffle"]["p_ruin"]; d["mc_bootstrap_p_ruin_200"] = mc["bootstrap"]["p_ruin"]
    d["mc_shuffle_dd_p95"] = mc["shuffle"]["dd_p95"]; d["mc_bootstrap_end_p05"] = mc["bootstrap"]["end_p05"]; d["mc_bootstrap_end_median"] = mc["bootstrap"]["end_median"]
    d["mc_p_dd_gt_50pct"] = mc["shuffle"]["p_dd_gt_50pct"]
    # historical sequence on $200 fixed lot: when does the balance first hit zero (if ever)?
    bal = 200 + tr["pnl"].cumsum()
    hit = bal[bal <= 0]
    d["historical_first_ruin_date_200"] = str(tr.loc[hit.index[0], "time_out"].date()) if len(hit) else "never"
    d["historical_min_balance_200"] = round(float(min(200, bal.min())), 2)
    # margin call / stop-out: equity <= 50% / 20% of the ~$4 margin -> only when the account is already almost gone
    d["stop_out_equity_threshold"] = round(STOP_OUT * d["margin_used_per_trade"], 2)
    d["swap_share_of_gross_pct"] = round(float(100 * tr["swap"].sum() / max(abs(tr["gross_usd"].sum()), 1e-9)), 1)
    rows.append(d)
tab = pd.DataFrame(rows); tab.to_csv(os.path.join(OUT, "account_table.csv"), index=False)
res["per_timeframe"] = rows

# ---- EA as provided (1% filter on) on $200: what it actually trades (from the baseline ea_200 view)
import json
with open(os.path.join(BASE, "summary.json")) as f:
    S = json.load(f)
res["ea_as_provided_on_200"] = {tf: {c: {k: S[tf]["6y"]["ea_200"][c].get(k) for k in ("trades", "net_profit", "blocked_sl_pct", "profit_factor", "max_dd_usd", "ruin", "end_balance")} for c in ("A_low", "B_real", "C_stress")} for tf in ("M1", "M5", "M15", "D1")}
res["strategy_on_200_no_filter"] = {tf: {c: {k: S[tf]["6y"]["ea_200_nofilt"][c].get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "ruin", "end_balance")} for c in ("A_low", "B_real", "C_stress")} for tf in ("M1", "M5", "M15", "D1")}
C.save_json(res, "account/summary.json")

L = ["# $200 account analysis", "", "Broker facts (XM Global MT5 GOLD, read from the terminal on 2026-09-26): min lot 0.01 = 1 oz, so $1.00 of gold = $1.00 P&L; the EA cannot size below 0.01 lot. "
     f"Margin per 0.01 lot at 1:1000 = ${res['broker']['margin_per_0.01_lot_at_4286']} (at $4,286 gold), stop-out at 20% margin level, i.e. only when equity is under ~$0.90. "
     "Margin call and stop-out are therefore irrelevant for this EA; the account dies by losses long before margin matters.", "",
     "| TF | trades | median risk $ | p90 risk $ | max risk $ | median risk % of $200 | p90 % | share risk > 1% | > 5% | > 20% | min account for 1% rule (median trade) | (p90 trade) | worst loss $ | max consec losses | worst streak $ | MC p(ruin) shuffle | MC p(ruin) bootstrap | MC DD p95 | historical first ruin | swap % of gross |",
     "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
for d in rows:
    L.append(f"| {d['tf']} | {d['trades']} | {d['risk_usd_median']} | {d['risk_usd_p90']} | {d['risk_usd_max']} | {d['risk_pct_of_200_median']} | {d['risk_pct_of_200_p90']} | {d['share_trades_risk_gt_1pct_of_200']} | {d['share_trades_risk_gt_5pct_of_200']} | {d['share_trades_risk_gt_20pct_of_200']} | ${d['min_account_for_1pct_rule_median_trade']:.0f} | ${d['min_account_for_1pct_rule_p90_trade']:.0f} | {d['worst_single_loss_usd']} | {d['max_consecutive_losses']} | {d['losing_streak_usd']} | {d['mc_shuffle_p_ruin_200']} | {d['mc_bootstrap_p_ruin_200']} | {d['mc_shuffle_dd_p95']} | {d['historical_first_ruin_date_200']} | {d['swap_share_of_gross_pct']} |")
L += ["", "## The EA exactly as provided on $200 (UseSLPercentFilter = true, 1%)", "", "| TF | cost | trades taken | blocked by the 1% rule | net $ | PF | max DD $ | end balance |", "|---|---|---:|---:|---:|---:|---:|---:|"]
for tf, cc in res["ea_as_provided_on_200"].items():
    for c, m in cc.items():
        L.append(f"| {tf} | {c} | {m['trades']} | {m['blocked_sl_pct']} | {m['net_profit']} | {m['profit_factor']} | {m['max_dd_usd']} | {m['end_balance']} |")
L += ["", "## The strategy exposed to $200 (filter off, fixed 0.01 lot)", "", "| TF | cost | trades | net $ | PF | max DD $ | ruin | end balance |", "|---|---|---:|---:|---:|---:|---|---:|"]
for tf, cc in res["strategy_on_200_no_filter"].items():
    for c, m in cc.items():
        L.append(f"| {tf} | {c} | {m['trades']} | {m['net_profit']} | {m['profit_factor']} | {m['max_dd_usd']} | {m['ruin']} | {m['end_balance']} |")
with open(os.path.join(OUT, "ACCOUNT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print(tab.to_string()); print("done")
