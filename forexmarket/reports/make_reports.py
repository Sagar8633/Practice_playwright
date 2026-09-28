"""Final reports: one per instrument (reports/<INSTR>_FINAL_REPORT.md) and the combined FOREX_CFD_FINAL_REPORT.md with the
cross-instrument comparison, assembled from the saved results and reports/narrative.json (written after reading the results)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: json.load(open(os.path.join(ROOT, *p))) if os.path.exists(os.path.join(ROOT, *p)) else None
BASE = J("backtests", "baseline_metrics.json"); COSTS = J("experiments", "cost_tables.json"); REG = J("experiments", "regime_tables.json"); SWP = J("experiments", "sweeps.json"); VAR = J("experiments", "variants.json")
NAR = J("reports", "narrative.json") or {}
INSTR = [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in BASE["runs"])]
money = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.2f}"


def load_trades(instr, cfg, tf, sc="B"):
    f = os.path.join(ROOT, "backtests", instr, f"{cfg}_{C.TF_NAME[tf]}_{sc}_trades.csv.gz"); return pd.read_csv(f, parse_dates=["time_in", "time_out"]) if os.path.exists(f) else None


def tf_table(instr, cfg):
    rows = []
    for tf in C.TFS:
        b = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|B"); a = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|A"); c = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|C")
        if not b: continue
        m = b["metrics"]; s = b["splits"]
        rows.append({"TF": C.TF_NAME[tf], "trades": m["trades"], "gross A $": a["metrics"]["net_usd"], "net B $": m["net_usd"], "net C $": c["metrics"]["net_usd"], "PF B": m["pf"], "win %": m["win_rate"], "exp $": m["exp_usd"], "exp R": m["exp_r"],
                     "max DD $": m["max_dd_usd"], "Sharpe(m)": m["sharpe_m"], "top-5 %": m.get("top5_trades_share"), "TRAIN": s["TRAIN"]["net_usd"], "VAL": s["VAL"]["net_usd"], "OOS": s["OOS"]["net_usd"], "verdict": b["verdict"]})
    return pd.DataFrame(rows)


def candidates(instr):
    out = []
    for cfg in C.CONFIGS:
        for tf in C.TFS:
            b = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|B")
            if b and b["metrics"]["net_usd"] > 0 and b["metrics"]["trades"] >= 50: out.append((cfg, tf, b))
    return sorted(out, key=lambda x: -x[2]["metrics"]["net_usd"])[:6]


def quality_block(instr, cfg, tf):
    tr = load_trades(instr, cfg, tf)
    if tr is None or len(tr) == 0: return ""
    m = C.summarize(tr, instr, C.DATA_START, C.DATA_END); cap = C.CAPITAL_PER_001; mc = E.monte_carlo(tr["usd"].to_numpy(), cap, n=3000, ruin_level=0.5 * cap)
    s = [f"- Expectancy ${m['exp_usd']} ({m['exp_r']} R), median R {m.get('median_r')}, R p05/p25/p75/p95 {m.get('r_p05')}/{m.get('r_p25')}/{m.get('r_p75')}/{m.get('r_p95')}; {m.get('r_ge_1')}% of trades >= +1R, {m.get('r_le_m1')}% <= -1R.",
         f"- Concentration: top 10% of trades = {m.get('top10pct_share')}% of net, best 5 trades = {m.get('top5_trades_share')}%; net without the best 5 = ${m.get('net_ex_top5_usd')}.",
         f"- Longest losing streak {m['max_consec_losses']}; max drawdown ${m['max_dd_usd']} ({m.get('max_dd_pct_cap')}% of $1,000 per 0.01 lot), longest drawdown {m.get('dd_duration_days')} days; recovery factor {m.get('recovery_factor')}; swap paid ${-m['swap_usd']:.2f}.",
         f"- Monthly Sharpe {m['sharpe_m']}, Sortino {m.get('sortino_m')}, positive months {m.get('pos_months_pct')}%, CAGR on $1,000 = {m.get('cagr_pct')}%; t-stat {m.get('t_stat')}, 95% CI of expectancy [{m.get('exp_ci95_lo')}, {m.get('exp_ci95_hi')}] $.",
         f"- Long {m['long_trades']} / ${m['long_net_usd']}, short {m['short_trades']} / ${m['short_net_usd']}. Exits {m['exit_mix']}. Avg hold {m['avg_hold_min']:.0f} min, {m['trades_per_month']} trades/month."]
    if mc: s.append(f"- Monte Carlo (3,000 shuffles on $1,000): median DD ${mc['shuffle']['dd_median']}, p95 ${mc['shuffle']['dd_p95']}, P(lose half) {mc['shuffle']['p_ruin']:.1%}.")
    return "\n".join(s) + "\n"


def regime_block(instr, cfg, tf):
    key = f"{instr}|{cfg}|{C.TF_NAME[tf]}"
    if not REG or key not in REG: return ""
    out = []
    for name in ("trend", "volatility", "session of entry", "weekday", "direction", "trade outcome type"):
        g = REG[key].get(name)
        if not g: continue
        col = list(g[0].keys())[0]; out.append(f"- {name}: " + "; ".join(f"{r[col]} ${r['net_usd']:,.0f}/{r['trades']}" for r in g))
    return "\n".join(out) + "\n"


def sweep_block(instr, cfg, tf):
    key = f"{instr}|{cfg}|{C.TF_NAME[tf]}"
    if not SWP or key not in SWP["ma_grid"]: return ""
    g = SWP["ma_grid"][key]; ex = SWP["exit_grid"].get(key, {}); wf = SWP["wf"].get(key, [])
    tr_pos = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30)
    both = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and (v["VAL"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
    s = [f"- MA grid: {tr_pos}/{len(g)} cells positive on TRAIN, {both} also on VAL and OOS. Exit grid: {sum(1 for v in ex.values() if (v['TRAIN'][1] or 0) > 0)}/{len(ex)} TRAIN-positive, {sum(1 for v in ex.values() if (v['TRAIN'][1] or 0) > 0 and (v['OOS'][1] or 0) > 0)} also OOS."]
    if wf:
        won = sum(1 for r in wf if r["test net (chosen) $"] > r["test net (18/200) $"]); s.append(f"- Walk-forward: re-optimised pairs ${sum(r['test net (chosen) $'] for r in wf):,.2f} vs fixed 18/200 ${sum(r['test net (18/200) $'] for r in wf):,.2f} on the test months; chosen beat fixed in {won}/{len(wf)} folds.")
    return "\n".join(s) + "\n"


def variants_block(instr, cfg, tf):
    if not VAR: return ""
    rows = [(k.split("|")[-1], v) for k, v in VAR["variants"].items() if k.startswith(f"{instr}|{cfg}|{C.TF_NAME[tf]}|")]
    if not rows: return ""
    helpful = [f"{vid} {v['label']} (net ${v['metrics']['net_usd']}, OOS ${v['splits']['OOS']['net_usd']})" for vid, v in rows if v["vs_base"] == "helpful"]
    harmful = [vid for vid, v in rows if v["vs_base"] == "harmful"]
    mt = [(k.split("|")[2], v) for k, v in VAR["mtf"].items() if k.startswith(f"{instr}|{cfg}|") and v["entry"] == C.TF_NAME[tf]]
    mt_help = [f"{mid} HTF {v['htf']} (net ${v['metrics']['net_usd']}, OOS ${v['splits']['OOS']['net_usd']})" for mid, v in mt if v["vs_base"] == "helpful"]
    return f"- Variants helpful in all splits: {'; '.join(helpful) if helpful else 'none'}. Harmful: {', '.join(harmful) if harmful else 'none'}. HTF gates helpful: {'; '.join(mt_help) if mt_help else 'none'}.\n"


def instrument_report(instr):
    nm = C.NAME[instr]; nar = NAR.get(instr, {}); sp = C.specs(instr)
    L = [f"# {nm}: final report (SimpleSMA18Bot logic, Sep 2021 to Sep 2026)\n", nar.get("summary", ""), "\n## 1. Setup\n",
         f"Data: Dukascopy 1-minute bid candles with volume in XM server time (see data/DATA_AUDIT.md), Dukascopy H1 2015-2021 for the long D1 path. XM symbol {C.XMSYM[instr]}: point {sp['point']}, contract {sp['contract']:,.0f}, "
         f"quote currency {sp['quote']}, swap long/short {sp['swap_long_pts']}/{sp['swap_short_pts']} points per night. Costs: A gross, B realistic (XM spread by server hour and year, slippage {C.SLIP[instr][0]} pts per side, swap), C stress (1.5x spread, {C.SLIP[instr][1]} pts slippage). "
         "Money: USD per 0.01 lot; percentages on $1,000 per 0.01 lot. Splits: TRAIN 2021-09..2024-08, VAL 2024-09..2025-08, OOS 2025-09..2026-09; robust = positive expectancy and PF > 1 after B costs in all three with >= 30 trades each.\n"]
    for cfg in C.CONFIGS:
        L.append(f"\n## 2{'a' if cfg == 'ASIS' else 'b'}. Every timeframe, {cfg}\n"); L.append(C.md_table(tf_table(instr, cfg)))
        L.append("\nYear by year (net B $ / trades):\n"); yrows = []
        for tf in C.TFS:
            kb = f"{instr}|{cfg}|{C.TF_NAME[tf]}|B"
            if kb in BASE["runs"]: yrows.append({"TF": C.TF_NAME[tf], **{str(y["year"]): f"{y['net_usd']:.0f} / {y['trades']}" for y in BASE["runs"][kb]["yearly"]}})
        L.append(C.md_table(pd.DataFrame(yrows)))
    dl = {k: v for k, v in BASE["daily_long"].items() if k.startswith(instr + "|")}
    if dl:
        L.append("\n## 3. D1 on the long hourly path 2015-2026\n")
        L.append(C.md_table(pd.DataFrame([{"config": k.split("|")[1], "scenario": k.split("|")[2], "trades": v["metrics"]["trades"], "net $": v["metrics"]["net_usd"], "PF": v["metrics"]["pf"], "exp R": v["metrics"]["exp_r"], "max DD $": v["metrics"]["max_dd_usd"],
                                          "years > 0": f"{sum(1 for y in v['by_year'].values() if y[1] > 0)}/{len(v['by_year'])}", "by year": ", ".join(f"{y}: {vv[1]:.0f}" for y, vv in v["by_year"].items())} for k, v in dl.items()])))
    L.append("\n## 4. Candidate timeframes: quality, conditions, robustness, variants\n")
    for cfg, tf, b in candidates(instr):
        L.append(f"\n### {C.TF_NAME[tf]} {cfg} (verdict {b['verdict']}, net ${b['metrics']['net_usd']}, PF {b['metrics']['pf']})\n"); L.append(quality_block(instr, cfg, tf)); L.append(regime_block(instr, cfg, tf)); L.append(sweep_block(instr, cfg, tf)); L.append(variants_block(instr, cfg, tf))
    if not candidates(instr): L.append("No timeframe is positive after realistic costs with at least 60 trades.\n")
    if COSTS:
        L.append("\n## 5. Costs\n"); rows = [r for r in COSTS["gross_to_net"] if r["instrument"] == instr and r["tf"] in ("15m", "30m", "1h", "2h", "4h", "D1")]
        if rows: L.append(C.md_table(pd.DataFrame(rows).drop(columns=["instrument"]), "{:,.3f}"))
        sl = [r for r in COSTS["slippage"] if r["instrument"] == instr]
        if sl: L.append("\nSlippage sweep (USD per 0.01 lot):\n"); L.append(C.md_table(pd.DataFrame(sl).drop(columns=["instrument"])))
    L.append("\n## 6. Answers\n"); L.append(nar.get("answers", "(pending)")); L.append(f"\n## 7. Files\n- backtests/{instr}/: every trade list\n- research/*.md, research/experiment_log.csv\n")
    return "\n".join(L)


for instr in INSTR:
    open(os.path.join(HERE, f"{C.XMSYM[instr]}_FINAL_REPORT.md"), "w", encoding="utf-8").write(instrument_report(instr))
nar = NAR.get("combined", {})
L = ["# Forex majors, silver, bitcoin and oil: final report (SimpleSMA18Bot, Sep 2021 to Sep 2026)\n", nar.get("summary", ""), "\n## Comparison: best after-cost timeframe per instrument (scenario B, USD per 0.01 lot)\n"]
rows = []
for instr in INSTR:
    c = candidates(instr)
    if not c:
        rows.append({"instrument": C.NAME[instr], "best TF (config)": "none positive", "trades": "", "PF": "", "exp R": "", "net $": "", "max DD $": "", "years > 0": "", "OOS $": "", "verdict": "negative"}); continue
    best = NAR.get(instr, {}).get("best")
    if best:
        cfg, tfn = best.split("/"); b = BASE["runs"][f"{instr}|{cfg}|{tfn}|B"]; tf = [k for k, v in C.TF_NAME.items() if v == tfn][0]
    else:
        cfg, tf, b = c[0]; tfn = C.TF_NAME[tf]
    m = b["metrics"]; s = b["splits"]; yr = b["yearly"]
    rows.append({"instrument": C.NAME[instr], "best TF (config)": f"{tfn} ({cfg})", "trades": m["trades"], "PF": m["pf"], "exp R": m["exp_r"], "net $": m["net_usd"], "max DD $": m["max_dd_usd"], "years > 0": f"{sum(1 for y in yr if y['net_usd'] > 0)}/{len(yr)}",
                 "OOS $": s["OOS"]["net_usd"], "t-stat": m.get("t_stat"), "top-5 %": m.get("top5_trades_share"), "verdict": b["verdict"]})
L.append(C.md_table(pd.DataFrame(rows)))
L.append("\n## Robust-rule count per instrument (of 20 baseline B runs each)\n")
L.append(C.md_table(pd.DataFrame([{"instrument": C.NAME[i], "robust": sum(1 for k, v in BASE["runs"].items() if k.startswith(i + "|") and k.endswith("|B") and v["verdict"] == "robust"),
                                   "unstable": sum(1 for k, v in BASE["runs"].items() if k.startswith(i + "|") and k.endswith("|B") and v["verdict"] == "unstable"),
                                   "negative": sum(1 for k, v in BASE["runs"].items() if k.startswith(i + "|") and k.endswith("|B") and v["verdict"] == "negative")} for i in INSTR])))
if REG: L.append("\n## Instrument characteristics\n"); L.append(C.md_table(pd.DataFrame(REG["characteristics"]).set_index("instrument").T.reset_index().rename(columns={"index": "metric"}), "{:,.3f}"))
L.append("\n## Answers\n"); L.append(nar.get("answers", "(pending)"))
L.append("\n## Method and reproducibility\n- strategy/engine_fx.py (gold engine generalised), strategy/common_fx.py; data via tools/fetch_duka.js, tools/xm_pull2.py, tools/prep_data.py; runs via backtests/run_baseline.py and experiments/*.py; every run in research/experiment_log.csv, every trade list under backtests/.\n")
open(os.path.join(HERE, "FOREX_CFD_FINAL_REPORT.md"), "w", encoding="utf-8").write("\n".join(L)); print("reports written for", INSTR)
