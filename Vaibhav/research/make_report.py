"""Assemble FINAL_REPORT.md (section 34 structure), the final comparison tables (sections 25 / 26) and research_tables.xlsx
from the saved phase outputs. Narrative text lives in narrative.json (written by hand after the numbers were read)."""
import json, os
import numpy as np
import pandas as pd

import common as C

R = C.RES
HERE = C.HERE


def J(name):
    p = os.path.join(R, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def table(rows, hdr):
    out = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] + ["---:"] * (len(hdr) - 1)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(fmt(x) for x in r) + " |")
    return out + [""]


N = json.load(open(os.path.join(HERE, "narrative.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "narrative.json")) else {}
audit = json.load(open(os.path.join(HERE, "data", "audit.json")))
base = J("baseline/summary.json"); gb = J("trade_analysis/giveback.json"); p2l = J("trade_analysis/p2l_summary.json"); loss = J("trade_analysis/loss_summary.json")
filt = J("filters/summary.json"); sl = J("sl/summary.json"); ex = J("exits/summary.json"); d1v = J("d1_validation/summary.json"); ltf = J("ltf/summary.json")
wf = J("walkforward/summary.json"); acc = J("account/summary.json")
TFS = ["M1", "M5", "M15", "D1"]
L = ["# GOLD EA (SimpleSMA18Bot v1.00) — systematic multi-timeframe backtest report", "",
     f"Prepared 2026-09-26. Engine, data and every intermediate table are in `Vaibhav/research/` (see `README.md`). Experiment log: `results/experiment_log.csv` "
     f"({sum(1 for _ in open(C.LOG, encoding='utf-8')) - 1 if os.path.exists(C.LOG) else 0} runs).", ""]

# ------------------------------------------------------------------ 1 executive summary
L += ["## 1. Executive summary", "", N.get("executive", "_(narrative pending)_"), ""]

# ------------------------------------------------------------------ 2 data quality
m = audit["m1"]; h = audit["h1"]; x = audit["xm_vs_dukascopy"]; s = audit["spread"]
L += ["## 2. Data quality", "",
      f"Primary dataset: Dukascopy XAUUSD M1 bid, {m['start_server']} to {m['end_server']} server time ({m['rows_final']:,} bars, all 73 months present, {m['duplicate_timestamps']} duplicates, "
      f"{m['invalid_high_lt_low'] + m['open_outside_hl'] + m['close_outside_hl']} invalid OHLC rows, {m['nonpositive_prices']} non-positive prices, {m['weekend_gaps']} weekend gaps, {m['intraweek_gaps_ge_1h']} intraweek gaps >= 1 h of which nearly all are the daily 1-hour rollover break, "
      f"{m['jumps_gt_1pct_one_bar']} one-minute moves > 1%, none > 3%). Long history: Dukascopy H1 {h['start_server']} to {h['end_server']} ({h['rows_final_combined']:,} bars) for D1 before Sep 2020.",
      f"Broker check on the XM M15 overlap (Jul 2022 - Sep 2026, {x['overlap_bars_M15']:,} bars): median |close difference| ${x['close_diff_median_abs']}, p90 ${x['close_diff_p90_abs']}; XM ranges are {x['range_ratio_xm_over_duka_median']}x Dukascopy's; "
      f"volume-filter agreement between XM tick volume and Dukascopy traded volume {x['volume_filter_agreement_M15']:.0%} (pass rates {x['volume_filter_pass_rate_xm']:.0%} vs {x['volume_filter_pass_rate_dk']:.0%}). Prices are therefore feed-specific: the MT5 tester on XM would not reproduce this trade list one for one.",
      f"Spread: XM's own GOLD spread by year and server hour (M15 close medians {s['m15_close_median_by_year']}, M1 2026 median {s['m1_close_median_2026']} pts, p99 {s['m1_p99_2026']} pts) scaled to M1-equivalent; before 2022 the 2022 profile is assumed. "
      f"Transformations: prices rounded to 0.01, UTC shifted to XM server time (EET with EU DST), bars outside XM's 01:00-23:59 session dropped ({m.get('rows_final', 0) and ''}no gap filling, no synthetic bars). Full audit: `AUDIT.md`.", ""]

# ------------------------------------------------------------------ 3 EA map
L += ["## 3. EA components", "", N.get("ea_map", "See `EA_MAP.md` for the full component map and tick-flow diagram."), ""]

# ------------------------------------------------------------------ 4 baseline
L += ["## 4. Baseline results (untouched EA)", "", "Strategy view = fixed 0.01 lot, no SL% filter, nominal balance (what the rules do, in $ per 0.01 lot = per oz). Account views = $200 with the EA as provided (SL% filter on) and with the filter off.", ""]
rows = []
for tf in TFS:
    for view in ("strategy", "ea_200", "ea_200_nofilt"):
        for cost in ("A_low", "B_real", "C_stress"):
            mm = base[tf]["6y"][view][cost]
            rows.append([tf, view, cost, mm["trades"], mm["net_profit"], mm.get("profit_factor"), mm.get("win_rate"), mm.get("expectancy"), mm.get("max_dd_usd"), mm.get("max_dd_pct"), mm.get("end_balance"), mm.get("ruin"), mm.get("blocked_sl_pct"), mm.get("avg_risk_usd")])
L += table(rows, ["TF", "view", "cost", "trades", "net $", "PF", "win %", "exp $", "maxDD $", "maxDD %", "end bal $", "ruin", "blocked by 1% rule", "avg risk $"])
L += ["Path-assumption sensitivity (strategy, B_real, 'worst' intrabar ordering): " + "; ".join(f"{tf} {base[tf]['6y']['strategy']['B_real_worst']['net_profit']} vs {base[tf]['6y']['strategy']['B_real']['net_profit']}" for tf in TFS) + ". D1 2003-2026 on the H1 path: " +
      f"{base['D1']['23y_h1path']['strategy']['B_real']['net_profit']} net, PF {base['D1']['23y_h1path']['strategy']['B_real']['profit_factor']} ({base['D1']['23y_h1path']['strategy']['B_real']['trades']} trades); the same rules on the H1 path over 2020-2026 give {base['D1']['6y_h1path']['strategy']['B_real']['net_profit']} vs {base['D1']['6y']['strategy']['B_real']['net_profit']} on the M1 path (path-resolution error ~15%).", ""]
L += ["### By year (strategy view, realistic costs)", ""]
for tf in TFS:
    yt = base["by_year"].get(tf, {})
    L += [f"**{tf}**: " + "; ".join(f"{y}: {v['net']} (PF {v['pf']}, {v['trades']} tr)" for y, v in yt.items()), ""]
L += ["**D1 2003-2026**: " + "; ".join(f"{y}: {v['net']}" for y, v in base["D1_23y_by_year"].items()), ""]
sc = base["D1_18month_window_scan"]
L += [f"D1 rolling 18-month windows, $200 at 0.01 lot: 2020-2026 best {sc['6y']['best']['growth_x']}x ({sc['6y']['best']['start']}), median {sc['6y']['median_growth_x']}x, {sc['6y']['share_windows_ge_3x']:.0%} of windows >= 3x, {sc['6y']['share_windows_losing']:.0%} losing; "
      f"2003-2026: best {sc['23y_h1path']['best']['growth_x']}x ({sc['23y_h1path']['best']['start']}), median {sc['23y_h1path']['median_growth_x']}x, {sc['23y_h1path']['share_windows_ge_3x']:.0%} >= 3x, {sc['23y_h1path']['share_windows_losing']:.0%} losing, {sc['23y_h1path']['share_windows_ruined']:.0%} ruined.", ""]
L += [N.get("baseline", ""), ""]

# ------------------------------------------------------------------ 5 D1 validation
if d1v:
    L += ["## 5. D1 validation of the reported ~3x in ~1.5 years", "", N.get("d1", ""), ""]
    rows = [[r["config"], r["period"], r["cost"], r["trades"], r["net"], r["growth_x"], r["pf"], r["max_dd_usd"], r["blocked_sl_pct"]] for r in d1v["table"] if r["cost"] == "B_real"]
    L += table(rows, ["config", "period", "cost", "trades", "net $", "growth", "PF", "maxDD $", "blocked by 1%"])
    p23 = os.path.join(R, "d1_validation", "d1_exits_23y.csv")
    if os.path.exists(p23):
        d23 = pd.read_csv(p23)
        L += ["D1 exit variants over 2003-2026 (H1 path, realistic costs): net $ / expectancy R per 8-year window, positive years, and the total without 2025.", ""]
        L += table([[r["exit"], r["trades"], r["net"], r["pf"], r["dd"], r["expR"], f"{r['pos_years']}/{r['years']}", r["net_ex2025"], r["2003-2012"], r["2012-2020"], r["2020-2026"]] for _, r in d23.iterrows()],
                   ["exit", "trades", "net $", "PF", "maxDD $", "exp R", "positive years", "net ex-2025 $", "2003-2012", "2012-2020", "2020-2026"])
    rb = d1v["robustness_23y"]
    L += [f"2003-2026 (v1.00 rules, filter off, realistic costs): {rb['positive_years']} of {rb['total_years']} years positive; the top-5 trades are {rb['share_of_gross_profit_from_top5_trades']:.0%} of gross profit; net excluding 2025 = {rb['net_excluding_year'].get('2025')}. "
          f"By exit: swing-protection exits {rb['by_exit'].get('SL_swing', {}).get('net')} on {rb['by_exit'].get('SL_swing', {}).get('trades')} trades, break-even exits {rb['by_exit'].get('SL_breakeven', {}).get('net')} on {rb['by_exit'].get('SL_breakeven', {}).get('trades')}, MA18 exits {rb['by_exit'].get('MA18_exit', {}).get('net')} on {rb['by_exit'].get('MA18_exit', {}).get('trades')}.", ""]

# ------------------------------------------------------------------ 6 entry filters
L += ["## 6. Entry filter analysis (Phase 1 and 2)", "", N.get("filters", ""), ""]
for tf in TFS:
    if tf not in filt:
        continue
    b = filt[tf]["BASE"]["metrics"]
    rows = [["BASE", b["ALL"]["trades"], "", b["ALL"].get("profit_factor"), b["ALL"].get("win_rate"), b["ALL"]["net_profit"], b["ALL"]["max_dd_usd"], b["ALL"].get("expectancy_r"), b["DEV"].get("expectancy_r"), b["VAL"].get("expectancy_r"), b["OOS"].get("expectancy_r"), "base"]]
    for v, r in filt[tf].items():
        if v in ("BASE", "COMBOS"):
            continue
        a = r["metrics"]["ALL"]; mm = r["metrics"]
        rows.append([v, a["trades"], b["ALL"]["trades"] - a["trades"], a.get("profit_factor"), a.get("win_rate"), a["net_profit"], a["max_dd_usd"], a.get("expectancy_r"), mm["DEV"].get("expectancy_r"), mm["VAL"].get("expectancy_r"), mm["OOS"].get("expectancy_r"), r["class"]])
    L += [f"### {tf}", ""] + table(rows, ["filter", "trades", "removed", "PF", "win %", "net $", "maxDD $", "exp R", "DEV R", "VAL R", "OOS R", "class"])
    if filt[tf]["COMBOS"]:
        L += ["Progressive combinations of the individually helpful filters:", ""] + table([[c["test"], c["filters"], c["trades"], c["profit_factor"], c["win_rate"], c["net_profit"], c["max_dd_usd"], c["expectancy"], f"{c['DEV_expR']}/{c['VAL_expR']}/{c['OOS_expR']}", c["OOS_net"], c["class"]] for c in filt[tf]["COMBOS"]],
                                                                                     ["test", "filters", "trades", "PF", "win %", "net $", "maxDD $", "exp $", "exp R DEV/VAL/OOS", "OOS net $", "class"])
    else:
        L += ["No individually helpful filter on this timeframe, nothing to combine.", ""]

# ------------------------------------------------------------------ 7 stop loss
L += ["## 7. Stop-loss analysis (Phase 3)", "", N.get("sl", ""), ""]
for tf in TFS:
    if tf not in sl.get("variants", {}):
        continue
    e = sl["existing"][tf]
    L += [f"### {tf}", "", f"Existing swing stop: median {e['sl_distance_pts']['median']:.0f} pts = ${e['sl_distance_usd_per_0.01lot']['median']} per 0.01 lot ({e['sl_distance_in_atr']['median']} ATR; p10-p90 {e['sl_distance_pts']['p10']:.0f}-{e['sl_distance_pts']['p90']:.0f} pts), hit in {e['sl_hit_rate_pct']}% of trades = {e['initial_sl_share_of_losses_pct']}% of losses; "
          f"average loss ${e['loss_distribution']['avg']} ({e['avg_loss_r']} R), worst ${e['loss_distribution']['worst']}; MFE before a stop-out {e['mfe_before_sl_hit'].get('avg_r')} R; winners' MAE median {e['mae_before_win'].get('median_r')} R, p90 {e['mae_before_win'].get('p90_r')} R.", ""]
    rows = []
    for v, r in sl["variants"][tf].items():
        a = r["metrics"]["ALL"]; mm = r["metrics"]
        rows.append([v, a["trades"], r["median_risk_usd"], a.get("sl_hit_rate"), a.get("avg_loss"), a.get("profit_factor"), a["net_profit"], a["max_dd_usd"], a.get("expectancy_r"), mm["DEV"].get("expectancy_r"), mm["VAL"].get("expectancy_r"), mm["OOS"].get("expectancy_r"), r["class"]])
    L += table(rows, ["stop", "trades", "median risk $", "SL hit %", "avg loss $", "PF", "net $", "maxDD $", "exp R", "DEV R", "VAL R", "OOS R", "class"])

# ------------------------------------------------------------------ 8 exits
L += ["## 8. Exit analysis (Phase 4): Chandelier vs trailing vs break-even vs hybrids", "", N.get("exits", ""), ""]
for tf in TFS:
    if tf not in ex:
        continue
    rows = []
    for v, r in ex[tf].items():
        a = r["metrics"]["ALL"]; mm = r["metrics"]
        rows.append([v, a["trades"], a["net_profit"], a.get("profit_factor"), a["max_dd_usd"], a.get("win_rate"), a.get("expectancy"), a.get("avg_win"), a.get("avg_loss"), a.get("giveback_avg"), a.get("profit_to_loss_2usd"), a.get("profit_to_loss_1r"), f"{mm['DEV'].get('expectancy_r')}/{mm['VAL'].get('expectancy_r')}/{mm['OOS'].get('expectancy_r')}", r["class"]])
    L += [f"### {tf}", ""] + table(rows, ["exit method", "trades", "net $", "PF", "maxDD $", "win %", "avg trade $", "avg win $", "avg loss $", "giveback avg $", "P->L >$2", "P->L >=1R", "exp R DEV/VAL/OOS", "class"])
L += ["### Section 12 summary table (net $ / PF / max DD $ / win % / exp R / giveback $ / P->L >$2)", ""]
rows = []
for tf in TFS:
    if tf not in ex:
        continue
    o = {k[:3]: k for k in ex[tf]}
    cell = lambda c: (lambda a: f"{a['net_profit']} / {a.get('profit_factor')} / {a['max_dd_usd']} / {a.get('win_rate')} / {a.get('expectancy_r')} / {a.get('giveback_avg')} / {a.get('profit_to_loss_2usd')}")(ex[tf][o[c]]["metrics"]["ALL"])
    rows.append([tf, cell("E03"), cell("E04"), cell("E05"), cell("E07"), cell("E01"), cell("E13"), cell("E09")])
L += table(rows, ["TF", "Chandelier (E03)", "Trailing (E04)", "Break-even only (E05)", "Chandelier+Trailing (E07)", "Swing = EA (E01)", "Previous TWK trail (E13)", "ATR trail 2x (E09)"])
L += ["### Section 22: current EA vs previous trailing-SL strategy vs hybrids", ""]
rows = []
for tf in TFS:
    if tf not in ex:
        continue
    o = {k[:3]: k for k in ex[tf]}
    cell = lambda c: (lambda a: f"{a['net_profit']} / {a.get('profit_factor')} / {a['max_dd_usd']} / {a.get('expectancy_r')}")(ex[tf][o[c]]["metrics"]["ALL"])
    rows.append([tf, cell("E01"), cell("E13"), cell("E14"), cell("E03"), cell("E19"), cell("E21")])
L += table(rows, ["TF", "Current EA", "Current entry + previous TWK trail", "TWK trail alone", "Current entry + Chandelier", "ATR-adaptive exit", "R-adaptive exit"]) + ["Cell: net $ / PF / max DD $ / expectancy R.", ""]

# ------------------------------------------------------------------ 9 giveback + P->L
L += ["## 9. Profit giveback and profitable-to-loss reversals", "", N.get("giveback", ""), ""]
rows = []
for tf in list(gb.keys()):
    o = gb[tf]["overall"]
    rows.append([tf, o["trades"], o["total_mfe"], o["total_realized"], o["avg_giveback"], o["median_giveback"], o["worst_giveback"], o["median_giveback_pct"], o["share_trades_with_mfe_ge_1usd"], o["avg_dd_after_mfe"]])
L += table(rows, ["TF", "trades", "total MFE $", "realized $", "avg giveback $", "median $", "worst $", "median giveback % of MFE", "share ever >= $1", "avg DD after MFE $"])
L += ["Giveback by exit mechanism (trades / net $ / avg MFE $ / avg giveback $ / P->L >$2):", ""]
rows = []
for tf in gb:
    for k, v in gb[tf]["exit_reason"].items():
        rows.append([tf, k, v["trades"], v["net"], v["avg_mfe"], v["avg_giveback"], v["p2l_2usd"], v["p2l_2usd_damage"]])
L += table(rows, ["TF", "exit", "trades", "net $", "avg MFE $", "avg giveback $", "P->L >$2", "P->L damage $"])
L += ["Giveback by direction and session (net $ / avg giveback $ / P->L >$2):", ""]
rows = []
for tf in gb:
    parts = [f"{k}: {v['net']} / {v['avg_giveback']} / {v['p2l_2usd']}" for k, v in gb[tf]["direction"].items()] + [f"{k}: {v['net']} / {v['avg_giveback']} / {v['p2l_2usd']}" for k, v in gb[tf]["session"].items()]
    rows.append([tf, "; ".join(parts)])
L += table(rows, ["TF", "direction and session"])
L += ["Profitable -> loss reversals by threshold (count / share of losers / realized loss $ / profit given up $ / share of total losses / price continued >= 1R after exit):", ""]
rows = []
for tf in p2l:
    for th, v in p2l[tf].items():
        rows.append([tf, th, v["trades"], v["share_of_losers"], v["realized_loss"], v["unrealized_profit_given_up"], v["share_of_total_losses"], v["share_price_continued_favourably_after_exit_ge_1R"], json.dumps(v["exit_mechanism_mix"])])
L += table(rows, ["TF", "threshold", "trades", "share of losers", "realized loss $", "profit given up $", "share of losses", "continued >= 1R", "exit mix"])
L += ["Full per-trade reversal reports: `results/trade_analysis/p2l_{TF}_{threshold}.csv` (entry/exit time, direction, entry, initial SL, max favourable price, max unrealized profit and its time, exit, P&L, drawdown after MFE, exit mechanism, indicator state at the MFE bar and at exit).", ""]

# ------------------------------------------------------------------ 10 loss patterns
L += ["## 10. Loss pattern analysis", "", N.get("loss", ""), ""]
rows = []
for tf in loss:
    for k, v in loss[tf]["categories"].items():
        rows.append([tf, k, v["trades"], v["loss"], v["avg_loss"], v["avg_mfe"], v["share_of_total_loss_pct"]])
L += table(rows, ["TF", "category", "trades", "loss $", "avg loss $", "avg MFE $", "share of total loss %"])

# ------------------------------------------------------------------ 11 LTF
if ltf:
    L += ["## 11. Lower-timeframe noise study (M1 / M5 / M15)", "", N.get("ltf", ""), ""]
    keys = ["trades", "median_atr_usd", "median_spread_usd", "spread_pct_of_atr", "median_mfe_usd", "spread_pct_of_median_mfe", "median_risk_usd", "median_hold_min", "share_held_le_2_bars", "share_MA18_exit", "share_MA18_exit_losing", "share_never_in_profit_ge_spread",
            "share_next_trade_opposite_within_5_bars", "gross_before_spread_and_slippage", "spread_paid", "slippage_paid", "swap_paid"]
    L += table([[k] + [ltf[n].get(k) for n in ("M1", "M5", "M15")] for k in keys], ["item", "M1", "M5", "M15"])
    for n in ("M1", "M5", "M15"):
        best = max(ltf[n]["trailing_sweep"], key=lambda r: (r["expR"] or -9))
        L += [f"{n} trailing sweep (20 settings): best {best['trail_dist']}/{best['trail_start']} -> net {best['net']}, PF {best['pf']}, exp R {best['expR']}, OOS net {best['oos_net']}; time exits: " + ", ".join(f"{r['time_exit_bars']}b {r['net']}" for r in ltf[n]["time_exit_sweep"]) +
              "; volatility filter: " + ", ".join(f">={r['vol_min']} {r['net']} (OOS {r['oos_net']})" for r in ltf[n]["vol_filter_sweep"]) + ".", ""]

# ------------------------------------------------------------------ 12 walk-forward
if wf:
    L += ["## 12. Walk-forward, robustness and overfitting audit", "", N.get("walkforward", ""), ""]
    for tf in TFS:
        if tf not in wf:
            continue
        Rw = wf[tf]; a = Rw["audit"]
        rows = []
        for f in Rw["folds"]:
            tb = f.get("train_best", {}); sel = f.get("selected")
            rows.append([f["fold"], f"{f['train'][0][:7]}..{f['train'][1][:7]}", f"{f['test'][0][:7]}..{f['test'][1][:7]}", f["configs"], tb.get("config"), tb.get("train_expR"), tb.get("val_expR"), tb.get("test_expR"), f.get("train_best_passes_val"), sel["config"] if sel else "none passes", sel["test_expR"] if sel else "", sel["test_net"] if sel else "", f["ea_untouched"]["test_net"], f["share_positive_test"]])
        L += [f"### {tf}", ""] + table(rows, ["fold", "train", "test", "configs", "train-best", "train R", "val R", "test R", "passes val", "selected", "sel test R", "sel test net $", "EA test net $", "share configs positive in test"])
        L += [f"Overfitting audit: {a['configs_tested']} configurations; positive in DEV, VAL and OOS: {a['positive_all_three_splits']}; share positive DEV {a['share_positive_dev']}, VAL {a['share_positive_val']}, OOS {a['share_positive_oos']}. Best in-sample: {a['best_in_sample']}.", ""]
        if a["robust_candidates"]:
            L += ["Configurations positive in all three splits (top by OOS expectancy/R):", ""] + table([[r["config"], r["dev_expR"], r["val_expR"], r["oos_expR"], r["oos_net"], r["oos_pf"], r["all_net"], r["all_pf"], r["all_dd"], r["all_trades"]] for r in a["robust_candidates"]], ["config", "DEV R", "VAL R", "OOS R", "OOS net $", "OOS PF", "all net $", "all PF", "all DD $", "trades"])
        c = Rw.get("candidate")
        if c:
            L += [f"Sensitivity around `{c['config']}` (value: all-period exp R (net $) | OOS exp R):", ""]
            for pn, rr in c["sensitivity"].items():
                L.append(f"- {pn}: " + ", ".join(f"{r['value']}: {r['all_expR']} ({r['all_net']}) | {r['oos_expR']}" for r in rr))
            mc = c["monte_carlo"]
            L += ["", f"Monte Carlo at $200 (shuffle / bootstrap): p(ruin) {mc['at_200']['shuffle']['p_ruin']} / {mc['at_200']['bootstrap']['p_ruin']}, DD p95 ${mc['at_200']['shuffle']['dd_p95']}, ending balance p05 / median / p95 ${mc['at_200']['bootstrap']['end_p05']} / ${mc['at_200']['bootstrap']['end_median']} / ${mc['at_200']['bootstrap']['end_p95']}; at 100x median risk (${max(100 * mc['median_risk_usd'], 200):.0f}): p(ruin) {mc['at_100x_median_risk']['shuffle']['p_ruin']}, DD p95 ${mc['at_100x_median_risk']['shuffle']['dd_p95']}.", ""]
        elif "ea_monte_carlo_200" in Rw:
            mc = Rw["ea_monte_carlo_200"]
            L += [f"No robust candidate. Monte Carlo of the untouched EA at $200: p(ruin) {mc['shuffle']['p_ruin']} (shuffle) / {mc['bootstrap']['p_ruin']} (bootstrap).", ""]

# ------------------------------------------------------------------ 13 $200
if acc:
    L += ["## 13. $200 account analysis", "", N.get("account", ""), ""]
    rows = [[d["tf"], d["trades"], d["risk_usd_median"], d["risk_usd_p90"], d["risk_usd_max"], d["risk_pct_of_200_median"], d["share_trades_risk_gt_1pct_of_200"], f"${d['min_account_for_1pct_rule_median_trade']:.0f}", f"${d['min_account_for_1pct_rule_p90_trade']:.0f}", d["worst_single_loss_usd"], d["max_consecutive_losses"], d["losing_streak_usd"], d["mc_shuffle_p_ruin_200"], d["mc_bootstrap_p_ruin_200"], d["historical_first_ruin_date_200"]] for d in acc["per_timeframe"]]
    L += table(rows, ["TF", "trades", "median risk $", "p90 risk $", "max risk $", "median risk % of $200", "share > 1%", "min account (1% rule, median trade)", "(p90 trade)", "worst loss $", "max consec losses", "worst streak $", "MC p(ruin) shuffle", "bootstrap", "historical first ruin"])
    b = acc["broker"]
    L += [f"Broker constraints: min lot 0.01 = 1 oz; margin per 0.01 lot ${b['margin_per_0.01_lot_at_4286']} at 1:1000; stop-out at 20% margin level (equity below ~$0.90); swap long ${b['swap_long_usd_per_night_0.01']}/night, short +${b['swap_short_usd_per_night_0.01']}/night per 0.01 lot. Margin call and stop-out never bind before the account is lost to ordinary stops.", ""]

# ------------------------------------------------------------------ 14 final tables
L += ["## 14. Final comparison table (section 25)", "", N.get("final_table_note", ""), ""]
rows = []
hdr = ["Metric"] + [f"{tf} EA" for tf in TFS] + [f"{tf} candidate" for tf in TFS]
metrics = [("Total trades", "trades"), ("Win rate %", "win_rate"), ("Profit factor", "profit_factor"), ("Net profit $ (0.01 lot)", "net_profit"), ("CAGR % (from $200)", "cagr_pct"), ("Max drawdown $", "max_dd_usd"), ("Expectancy $", "expectancy"), ("Expectancy R", "expectancy_r"),
           ("Avg winner $", "avg_win"), ("Avg loser $", "avg_loss"), ("Max losing streak", "max_consec_losses"), ("Profit giveback avg $", "giveback_avg"), ("Profitable->loss (>$2)", "profit_to_loss_2usd"), ("Avg holding min", "avg_hold_min")]
cand_metrics = {}
import sma18_engine as E
from dataclasses import replace
YEARS = (pd.Timestamp(C.DATA_END) - pd.Timestamp(C.DATA_START)).days / 365.25
for tf in TFS:
    c = (wf.get(tf) or {}).get("candidate")
    if c:
        tfm = {"M1": 1, "M5": 5, "M15": 15, "D1": 1440}[tf]
        p = replace(E.Params(tf_minutes=tfm, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"]), **c["params"])
        tr, st = E.run(p)
        m = E.metrics(tr, st, 100000.0, E.months_between(C.DATA_START, C.DATA_END))
        m["config"] = c["config"]
        cand_metrics[tf] = m


def cagr200(net):
    end = 200.0 + float(net)
    return "ruin" if end <= 0 else round(100 * ((end / 200.0) ** (1 / YEARS) - 1), 1)


for label, key in metrics:
    if key == "cagr_pct":
        row = [label] + [cagr200(base[tf]["6y"]["strategy"]["B_real"]["net_profit"]) for tf in TFS] + [cagr200(cand_metrics[tf]["net_profit"]) if tf in cand_metrics else "-" for tf in TFS]
    else:
        row = [label] + [base[tf]["6y"]["strategy"]["B_real"].get(key) for tf in TFS] + [cand_metrics.get(tf, {}).get(key, "-") for tf in TFS]
    rows.append(row)
rows.append(["Robustness"] + [N.get("robustness_ea", {}).get(tf, "-") for tf in TFS] + [N.get("robustness_cand", {}).get(tf, "-") for tf in TFS])
rows.append(["Candidate config"] + ["untouched"] * 4 + [cand_metrics.get(tf, {}).get("config", "none identified") for tf in TFS])
L += table(rows, hdr)

# ------------------------------------------------------------------ 15 candidates
L += ["## 15. Final candidate configurations", "", N.get("candidates", ""), ""]
pc = os.path.join(R, "d1_validation", "d1_candidate_23y.csv")
if os.path.exists(pc):
    dc = pd.read_csv(pc)
    L += ["D1 candidate and its neighbours over 2003-2026 (H1 path, realistic costs; window cells = net $ / expectancy R / trades):", ""]
    L += table([[r["config"], r["trades"], r["net"], r["pf"], r["dd"], r["expR"], r["win"], r["pos_years"], r["net_ex2025"], r["2003-2012"], r["2012-2020"], r["2020-2026"], r["mc_p_ruin_200_bootstrap"]] for _, r in dc.iterrows()],
               ["config", "trades", "net $", "PF", "maxDD $", "exp R", "win %", "positive years", "net ex-2025 $", "2003-2012", "2012-2020", "2020-2026", "MC p(ruin) at $200"])
# ------------------------------------------------------------------ 16 failed experiments
L += ["## 16. Failed experiments", "", N.get("failed", ""), ""]
if os.path.exists(C.LOG):
    log = pd.read_csv(C.LOG)
    log["net_profit"] = pd.to_numeric(log["net_profit"], errors="coerce")
    fails = log[(log["conclusion"].astype(str).str.startswith("Harmful")) | (log["net_profit"] < 0)]
    L += [f"{len(fails)} of {len(log)} logged runs ended negative or classified Harmful. Rejected configurations by phase: " + ", ".join(f"{k}: {v}" for k, v in fails["phase"].value_counts().items()) + ". Full list with parameters and reasons: `results/experiment_log.csv` (columns conclusion / oos_result).", ""]
# ------------------------------------------------------------------ 17 EA changes
L += ["## 17. Recommended EA changes (only what the tests support)", "", N.get("ea_changes", ""), ""]
# ------------------------------------------------------------------ 18 methodology
L += ["## 18. Backtest methodology", "", N.get("methodology", ""), ""]

with open(os.path.join(HERE, "FINAL_REPORT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("FINAL_REPORT.md written", len(L), "lines")

# ------------------------------------------------------------------ Excel workbook
try:
    with pd.ExcelWriter(os.path.join(R, "research_tables.xlsx"), engine="openpyxl") as xw:
        if os.path.exists(C.LOG):
            pd.read_csv(C.LOG).to_excel(xw, "experiment_log", index=False)
        for nm, pth in (("filters", "filters/filter_table.csv"), ("stoploss", "sl/sl_table.csv"), ("exits", "exits/exit_table.csv"), ("d1_validation", "d1_validation/d1_validation_table.csv"), ("account", "account/account_table.csv")):
            p = os.path.join(R, pth)
            if os.path.exists(p):
                pd.read_csv(p).to_excel(xw, nm, index=False)
        for tf in TFS:
            p = os.path.join(R, "walkforward", f"grid_{tf}.csv")
            if os.path.exists(p):
                pd.read_csv(p).to_excel(xw, f"wf_grid_{tf}", index=False)
            p = os.path.join(R, "trade_analysis", f"trade_level_{tf}.csv")
            if os.path.exists(p):
                d = pd.read_csv(p)
                d.to_excel(xw, f"trades_{tf}", index=False)
    print("research_tables.xlsx written")
except Exception as e:
    print("xlsx skipped:", e)
