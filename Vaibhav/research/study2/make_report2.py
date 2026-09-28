"""Assemble study2/STUDY2_REPORT.md from study2/results/*.json. Narrative lives in study2/narrative2.json (written after reading the numbers)."""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import common as C

R = os.path.join(HERE, "results")
J = lambda n: json.load(open(os.path.join(R, n), encoding="utf-8")) if os.path.exists(os.path.join(R, n)) else {}
N = json.load(open(os.path.join(HERE, "narrative2.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "narrative2.json")) else {}
A = J("partA_baseline.json"); AL = J("partA_labs.json"); AW = J("partA_walkforward.json"); B = J("partB_baseline_sessions.json"); S = J("partB_sma.json")
TF6 = ["M1", "M5", "M15", "H1", "H4", "D1"]


def f(x, d=2):
    if x is None: return "-"
    if isinstance(x, float):
        if np.isnan(x) or np.isinf(x): return "-"
        return f"{x:.{d}f}"
    return str(x)


def table(rows, hdr):
    out = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] + ["---:"] * (len(hdr) - 1)) + "|"]
    for r in rows: out.append("| " + " | ".join(f(x) for x in r) + " |")
    return out + [""]


L = ["# Study 2: H1 and H4, session-wise P/L, the 2023-2026 window, and the SMA choice", "",
     "Prepared 2026-09-26 as a separate study; the first study's results are untouched. Same engine, data, costs and rules (see `../README.md`). Money per 0.01 lot.", "",
     "## 1. Summary", "", N.get("summary", "_(pending)_"), ""]

# ---------------------------------------------------------------- Part A
L += ["## 2. H1 and H4 through the first study's pipeline (Sep 2020 - Sep 2026)", "", N.get("partA", ""), "", "### Baseline", ""]
rows = []
for tf in ("H1", "H4"):
    for view in ("strategy", "ea_200", "ea_200_nofilt"):
        for cost in ("A_low", "B_real", "C_stress"):
            m = A[tf]["baseline"][view][cost]
            rows.append([tf, view, cost, m["trades"], m["net_profit"], m.get("profit_factor"), m.get("win_rate"), m.get("max_dd_usd"), m.get("end_balance"), m.get("ruin"), m.get("blocked_sl_pct"), m.get("avg_risk_usd")])
L += table(rows, ["TF", "view", "cost", "trades", "net $", "PF", "win %", "maxDD $", "end bal $", "ruin", "blocked by 1%", "avg risk $"])
for tf in ("H1", "H4"):
    m = A[tf]["baseline"]["strategy"]["B_real"]
    L += [f"{tf} strategy view, realistic costs: DEV {m['DEV']['net_profit']} ({f(m['DEV'].get('expectancy_r'), 3)} R), VAL {m['VAL']['net_profit']} ({f(m['VAL'].get('expectancy_r'), 3)} R), OOS {m['OOS']['net_profit']} ({f(m['OOS'].get('expectancy_r'), 3)} R); worst intrabar ordering {A[tf]['baseline']['strategy']['B_real_worst']['net_profit']}; exit mix {m.get('exit_mix')}.",
          "By year: " + "; ".join(f"{y}: {v['net']} (PF {v['pf']}, {v['trades']} tr)" for y, v in A[tf]["by_year"].items()), ""]
    ta = A[tf].get("trade_analysis", {})
    if ta:
        o = ta["overall"]
        L += [f"Giveback: summed best profit {o['total_mfe']} vs realized {o['realized']}; avg giveback {o['avg_giveback']}, median {o['median_giveback_pct']}% of best, worst {o['worst_giveback']}. Profitable->loss (>= $2): {ta['p2l']['2usd']['trades']} trades = {ta['p2l']['2usd']['share_of_losers']:.0%} of losers, {ta['p2l']['2usd']['given_up']} given up. By exit: " + "; ".join(f"{k}: {v['trades']} tr, net {v['net']}, avg best {v['avg_mfe']}" for k, v in ta["by_exit"].items()) + ".",
              "Loss categories: " + "; ".join(f"{k}: {v['share']}% ({v['trades']} tr)" for k, v in ta["loss_categories"].items()), ""]
for lab, title in (("filters", "Entry filters"), ("sl", "Stops"), ("exits", "Exits")):
    L += [f"### {title} (H1 / H4)", ""]
    for tf in ("H1", "H4"):
        d = AL[tf][lab]; b = d["base"]; rows = []
        for v, r in d["rows"].items():
            a = r["metrics"]["ALL"]; m = r["metrics"]
            rows.append([v, a["trades"], a["net_profit"], a.get("profit_factor"), a["max_dd_usd"], a.get("expectancy_r"), f(m["DEV"].get("expectancy_r"), 3), f(m["VAL"].get("expectancy_r"), 3), f(m["OOS"].get("expectancy_r"), 3), r["class"]])
        L += [f"**{tf}** (base: {b['ALL']['trades']} trades, net {b['ALL']['net_profit']}, exp R DEV/VAL/OOS {f(b['DEV'].get('expectancy_r'), 3)} / {f(b['VAL'].get('expectancy_r'), 3)} / {f(b['OOS'].get('expectancy_r'), 3)})", ""] + table(rows, ["variant", "trades", "net $", "PF", "maxDD $", "exp R", "DEV R", "VAL R", "OOS R", "class"])
L += ["### Walk-forward (H1 / H4)", ""]
for tf in ("H1", "H4"):
    w = AW[tf]; a = w["audit"]
    rows = [[x["fold"], f"{x['train'][0][:7]}..{x['train'][1][:7]}", f"{x['test'][0][:7]}..{x['test'][1][:7]}", x.get("train_best"), f(x.get("train_best_R", [None])[0], 3) if x.get("train_best_R") else "-", f(x.get("train_best_R", [None, None])[1], 3) if x.get("train_best_R") else "-", f(x.get("train_best_R", [None, None, None])[2], 3) if x.get("train_best_R") else "-", x.get("passes_val"), x.get("selected") or "none passes", f(x["selected_test"][1]) if x.get("selected_test") else "-", x["ea_test_net"], x["share_positive_test"]] for x in w["folds"]]
    L += [f"**{tf}**: {a['configs']} configurations; positive in DEV, VAL and OOS: {a['pos3']}; share positive DEV {a['share_dev']}, VAL {a['share_val']}, OOS {a['share_oos']}.", ""] + table(rows, ["fold", "train", "test", "train-best", "train R", "val R", "test R", "passes val", "selected", "selected test net $", "EA test net $", "share positive in test"])
    if a["robust"]:
        L += ["Configurations positive in all three splits (top by OOS expectancy):", ""] + table([[r["config"], f(r["dev_expR"], 3), f(r["val_expR"], 3), f(r["oos_expR"], 3), r["oos_net"], r["all_net"], r["all_pf"], r["all_dd"], r["all_trades"]] for r in a["robust"]], ["config", "DEV R", "VAL R", "OOS R", "OOS net $", "all net $", "all PF", "all DD $", "trades"])
    c = w.get("candidate")
    if c:
        L += [f"Candidate `{c['config']}`: sensitivity (value: all-period exp R (net) | OOS exp R):", ""]
        for pn, rr in c["sensitivity"].items(): L.append(f"- {pn}: " + ", ".join(f"{r['value']}: {f(r['all_expR'], 3)} ({r['all_net']}) | {f(r['oos_expR'], 3)}" for r in rr))
        mc = c["mc_200"]; L += ["", f"Monte Carlo at $200: p(ruin) {mc['shuffle']['p_ruin']} / {mc['bootstrap']['p_ruin']}, DD p95 {mc['shuffle']['dd_p95']}, end p05/median/p95 {mc['bootstrap']['end_p05']} / {mc['bootstrap']['end_median']} / {mc['bootstrap']['end_p95']}; median stop {f(c['median_risk'])}.", ""]

# ---------------------------------------------------------------- Part B
L += ["## 3. The 2023-2026 window, all six timeframes", "", N.get("partB", ""), "", "### Baseline 2023-01-01 to 2026-09-26 (IS = 2023-24, OOS = 2025-26)", ""]
rows = []
for tf in TF6:
    for view in ("strategy", "ea_200", "ea_200_nofilt"):
        for cost in ("A_low", "B_real", "C_stress"):
            m = B["baseline"][tf][view][cost]
            rows.append([tf, view, cost, m["trades"], m["net_profit"], m.get("profit_factor"), m.get("win_rate"), m.get("max_dd_usd"), m.get("end_balance"), m.get("ruin"), m.get("blocked_sl_pct")])
L += table(rows, ["TF", "view", "cost", "trades", "net $", "PF", "win %", "maxDD $", "end bal $", "ruin", "blocked by 1%"])
L += ["Strategy view, realistic costs, by year and by split:", ""]
L += table([[tf, *[f"{B['baseline'][tf]['strategy']['B_real']['by_year'].get(str(y), B['baseline'][tf]['strategy']['B_real']['by_year'].get(y, {})).get('net', '-')}" for y in (2023, 2024, 2025, 2026)], B["baseline"][tf]["strategy"]["B_real"]["splits"]["IS"]["net_profit"], f(B["baseline"][tf]["strategy"]["B_real"]["splits"]["IS"].get("expectancy_r"), 3), B["baseline"][tf]["strategy"]["B_real"]["splits"]["OOS"]["net_profit"], f(B["baseline"][tf]["strategy"]["B_real"]["splits"]["OOS"].get("expectancy_r"), 3)] for tf in TF6], ["TF", "2023", "2024", "2025", "2026", "IS net $", "IS exp R", "OOS net $", "OOS exp R"])

L += ["## 4. Session-wise profit and loss (by fill time, server hours)", "", N.get("sessions", ""), "", "Non-overlapping sessions: Asia 0-8, London 8-13, London/NY 13-17, New York 17-22, Sydney 22-24.", ""]
rows = []
for tf in TF6:
    for s, v in B["sessions"][tf]["by_session"].items():
        rows.append([tf, s, v["trades"], v["net"], v["pf"], v["win_rate"], v["expectancy"], v["avg_mfe"], v["giveback_avg"], v["p2l_2usd"]])
L += table(rows, ["TF", "session", "trades", "net $", "PF", "win %", "exp $", "avg best $", "avg giveback $", "P->L >$2"])
L += ["The EA's own (overlapping) session windows, same trades counted in every window they fall in:", ""]
rows = []
for tf in TF6:
    for s, v in B["sessions"][tf]["ea_sessions_overlapping"].items():
        rows.append([tf, s, v["trades"], v["net"], v["pf"], v["win_rate"], v["expectancy"]])
L += table(rows, ["TF", "EA session", "trades", "net $", "PF", "win %", "exp $"])
L += ["Net $ by hour of fill (server time):", ""]
hours = list(range(24))
L += table([[tf] + [B["sessions"][tf]["by_hour"].get(str(h), B["sessions"][tf]["by_hour"].get(h, {})).get("net", "-") for h in hours] for tf in TF6], ["TF"] + [str(h) for h in hours])
L += ["Net $ by weekday of fill (0 = Monday):", ""]
L += table([[tf] + [B["sessions"][tf]["by_weekday"].get(str(d), B["sessions"][tf]["by_weekday"].get(d, {})).get("net", "-") for d in range(5)] for tf in TF6], ["TF", "Mon", "Tue", "Wed", "Thu", "Fri"])
L += ["### The EA's session filter switched on (UseSessionFilter with each window), 2023-2026", "", N.get("session_filters", ""), ""]
rows = []
for tf in TF6:
    for s, m in B["session_filters"][tf].items():
        rows.append([tf, s, m["trades"], m["net_profit"], m.get("profit_factor"), m["max_dd_usd"], m.get("expectancy_r"), m["splits"]["IS"]["net_profit"], m["splits"]["OOS"]["net_profit"], f(m["splits"]["OOS"].get("expectancy_r"), 3)])
L += table(rows, ["TF", "session filter", "trades", "net $", "PF", "maxDD $", "exp R", "IS net $", "OOS net $", "OOS exp R"])

L += ["## 5. SMA sweeps, 2023-2026 (IS 2023-24 / OOS 2025-26)", "", N.get("sma", ""), "", "Changing the fast SMA also changes the MA exit and the pending-order invalidation, which use the same average. Trend SMA stays 200 in the fast sweep.", ""]
for tf in TF6:
    s = S[tf]
    L += [f"### {tf}", "", "Fast SMA (trend 200):", ""]
    L += table([[r["fast"], r["trades"], r["net"], r["pf"], r["dd"], r["win"], f(r["expR"], 3), r["IS_net"], f(r["IS_expR"], 3), r["OOS_net"], f(r["OOS_expR"], 3), r["giveback"]] for r in s["fast"].values()], ["fast", "trades", "net $", "PF", "maxDD $", "win %", "exp R", "IS net $", "IS exp R", "OOS net $", "OOS exp R", "giveback avg $"])
    L += [f"Trend SMA (fast 18, and fast {s['best_fast_IS']} = best IS):", ""]
    L += table([[k, r["trades"], r["net"], r["pf"], r["dd"], f(r["expR"], 3), r["IS_net"], f(r["IS_expR"], 3), r["OOS_net"], f(r["OOS_expR"], 3)] for k, r in s["trend"].items()], ["fast/trend", "trades", "net $", "PF", "maxDD $", "exp R", "IS net $", "IS exp R", "OOS net $", "OOS exp R"])
    L += ["Popular pairs:", ""]
    L += table([[k, r["trades"], r["net"], r["pf"], r["dd"], f(r["expR"], 3), r["IS_net"], f(r["IS_expR"], 3), r["OOS_net"], f(r["OOS_expR"], 3)] for k, r in s["pairs"].items()], ["fast/trend", "trades", "net $", "PF", "maxDD $", "exp R", "IS net $", "IS exp R", "OOS net $", "OOS exp R"])
    if s.get("fast_improved"):
        L += ["Fast SMA with the improved exit (ADX 25 + Chandelier from the first tick), trend 200:", ""]
        L += table([[r["fast"], r["trades"], r["net"], r["pf"], r["dd"], f(r["expR"], 3), r["IS_net"], f(r["IS_expR"], 3), r["OOS_net"], f(r["OOS_expR"], 3)] for r in s["fast_improved"].values()], ["fast", "trades", "net $", "PF", "maxDD $", "exp R", "IS net $", "IS exp R", "OOS net $", "OOS exp R"])
    rec = s.get("recommended", [])
    L += ["Configurations positive in both IS and OOS with enough trades, ranked by the weaker of the two expectancies (neighbours = adjacent fast values also positive OOS):", ""]
    L += table([[f"{r['fast']}/{r['trend']}", r["trades"], r["net"], r["pf"], r["dd"], f(r["IS_expR"], 3), f(r["OOS_expR"], 3), f"{r['neighbours_positive_OOS'][0]}/{r['neighbours_positive_OOS'][1]}" if r.get("neighbours_positive_OOS") else "-"] for r in rec], ["fast/trend", "trades", "net $", "PF", "maxDD $", "IS exp R", "OOS exp R", "neighbours +OOS"]) if rec else ["None.", ""]

L += ["## 6. Recommendation", "", N.get("recommendation", ""), ""]
with open(os.path.join(HERE, "STUDY2_REPORT.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L))
print("STUDY2_REPORT.md written", len(L), "lines")
