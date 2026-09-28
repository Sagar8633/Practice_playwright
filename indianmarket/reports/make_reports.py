"""Final reports: NIFTY50_FINAL_REPORT.md, BANKNIFTY_FINAL_REPORT.md, INDIAN_MARKET_FINAL_REPORT.md and README.md,
assembled from the saved results (baseline_metrics.json, cost_tables.json, regime_tables.json, sweeps.json, variants.json)
and the narrative in reports/narrative.json (written after reading the results; every number in it is quoted from the tables)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO, engine_in as E

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: json.load(open(os.path.join(ROOT, *p))) if os.path.exists(os.path.join(ROOT, *p)) else None
BASE = J("backtests", "baseline_metrics.json"); COSTS = J("experiments", "cost_tables.json"); REG = J("experiments", "sessions", "regime_tables.json")
SWP = J("experiments", "timeframe", "sweeps.json"); VAR = J("experiments", "filters", "variants.json")
NAR = J("reports", "narrative.json") or {}
CANDIDATES = {"nifty50": (15, 30, 60, 120, 240), "banknifty": (15, 30, 60)}
money = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.0f}"


def load_trades(instr, cfg, tf, sc="B"):
    f = os.path.join(ROOT, "backtests", instr, f"{cfg}_{C.TF_NAME[tf]}_{sc}_trades.csv.gz")
    return pd.read_csv(f, parse_dates=["time_in", "time_out"]) if os.path.exists(f) else None


def tf_table(instr, cfg):
    rows = []
    for tf in C.TFS:
        b = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|B"); a = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|A"); c = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|C")
        if not b: continue
        m = b["metrics"]; s = b["splits"]
        rows.append({"TF": C.TF_NAME[tf], "trades": m["trades"], "gross A": a["metrics"]["net_pts"], "net B": m["net_pts"], "net C": c["metrics"]["net_pts"], "PF B": m["pf"], "win %": m["win_rate"],
                     "exp pts": m["exp_pts"], "exp R": m["exp_r"], "median R": m.get("median_r"), "max DD": m["max_dd_pts"], "Sharpe(m)": m["sharpe_m"], "top-5 share %": m.get("top5_trades_share"),
                     "TRAIN": s["TRAIN"]["net_pts"], "VAL": s["VAL"]["net_pts"], "OOS": s["OOS"]["net_pts"], "OOS PF": s["OOS"].get("pf"), "verdict": b["verdict"]})
    return pd.DataFrame(rows)


def yearly_table(instr, cfg, tfs):
    rows = []
    for tf in tfs:
        b = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|B")
        if not b: continue
        for y in b["yearly"]:
            rows.append({"TF": C.TF_NAME[tf], "year": y["year"], "trades": y["trades"], "win %": y["win_rate"], "PF": y["pf"], "exp pts": y["exp_pts"], "exp R": y["exp_r"], "net pts": y["net_pts"], "net R": y["net_r"], "max DD pts": y["max_dd_pts"]})
    return pd.DataFrame(rows)


def quality_block(instr, cfg, tf):
    tr = load_trades(instr, cfg, tf)
    if tr is None or len(tr) == 0: return ""
    m = C.summarize(tr, instr, C.DATA_START, C.DATA_END); lot = CO.INSTR[instr]["lot"]; cap = CO.INSTR[instr]["capital_per_lot"]
    mc = E.monte_carlo(tr["rs_net"].to_numpy(), cap, n=3000, ruin_level=0.5 * cap)
    lines = [f"**{C.TF_NAME[tf]} {cfg}: trade quality** ({m['trades']} trades)\n",
             f"- Expectancy {m['exp_pts']} pts ({m['exp_r']} R), median R {m.get('median_r')}, R percentiles p05 {m.get('r_p05')} / p25 {m.get('r_p25')} / p75 {m.get('r_p75')} / p95 {m.get('r_p95')}; {m.get('r_ge_1')}% of trades >= +1R, {m.get('r_le_m1')}% <= -1R.",
             f"- Concentration: the top 10% of trades contribute {m.get('top10pct_share')}% of the net result, the best 5 trades {m.get('top5_trades_share')}%; net without the best 5 trades = {m.get('net_ex_top5_pts')} pts.",
             f"- Longest losing streak {m['max_consec_losses']}, max drawdown {m['max_dd_pts']} pts = Rs {money(m['max_dd_rs'])} per lot ({m.get('max_dd_pct_cap')}% of Rs {cap:,.0f}), longest drawdown {m.get('dd_duration_days')} days; recovery factor {m.get('recovery_factor')}.",
             f"- Per lot of {lot}: net Rs {money(m['net_rs'])} over {m['months']} months, CAGR on Rs {cap:,.0f} = {m.get('cagr_pct')}%, monthly Sharpe {m['sharpe_m']}, Sortino {m.get('sortino_m')}, positive months {m.get('pos_months_pct')}%; t-stat of the mean trade {m.get('t_stat')}, 95% CI of the expectancy [{m.get('exp_ci95_lo')}, {m.get('exp_ci95_hi')}] pts.",
             f"- Long {m['long_trades']} trades / {m['long_net_pts']} pts, short {m['short_trades']} / {m['short_net_pts']} pts. Exits: {m['exit_mix']}. Average hold {m['avg_hold_min']:.0f} min, {m['trades_per_month']} trades per month."]
    if mc:
        s = mc["shuffle"]
        lines.append(f"- Monte Carlo (3,000 trade-order shuffles, one lot on Rs {cap:,.0f}): median drawdown Rs {money(s['dd_median'])}, 95th pct Rs {money(s['dd_p95'])}, probability of losing half the capital {s['p_ruin']:.1%}, probability of ending below the start {s['p_end_below_start']:.1%}.")
    return "\n".join(lines) + "\n"


def regime_block(instr, cfg, tf):
    key = f"{instr}|{cfg}|{C.TF_NAME[tf]}"
    if not REG or key not in REG: return ""
    out = [f"**{C.TF_NAME[tf]} {cfg}: by market condition** (net pts / trades / PF)\n"]
    for name in ("trend", "volatility", "session phase of entry", "opening gap of the entry day", "trade outcome type"):
        g = REG[key].get(name)
        if not g: continue
        col = list(g[0].keys())[0]
        out.append(f"- {name}: " + "; ".join(f"{r[col]} {money(r['net_pts'])}/{r['trades']}/{r['pf']:.2f}" if isinstance(r["pf"], (int, float)) and r["pf"] < 1e6 else f"{r[col]} {money(r['net_pts'])}/{r['trades']}" for r in g))
    return "\n".join(out) + "\n"


def sweep_block(instr, cfg, tf):
    key = f"{instr}|{cfg}|{C.TF_NAME[tf]}"
    if not SWP or key not in SWP["ma_grid"]: return ""
    g = SWP["ma_grid"][key]; ex = SWP["exit_grid"].get(key, {}); wf = SWP["wf"].get(key, [])
    tr_pos = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30)
    both = sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and (v["VAL"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
    ex_pos = sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0); ex_both = sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0)
    b = g.get("18/200", {}); s = [f"**{C.TF_NAME[tf]} {cfg}: parameter robustness and walk-forward**\n",
         f"- MA grid (10 fast x 6 trend = {len(g)} cells): {tr_pos} positive on TRAIN with >= 30 trades, {both} of them also positive on VAL and OOS. 18/200 itself: TRAIN {b.get('TRAIN', [None, None])[1]} / VAL {b.get('VAL', [None, None])[1]} / OOS {b.get('OOS', [None, None])[1]} pts per trade.",
         f"- Exit grid ({len(ex)} cells): {ex_pos} positive on TRAIN, {ex_both} also positive on OOS."]
    if wf:
        won = sum(1 for r in wf if r["test net (chosen)"] > r["test net (18/200)"]); tot_sel = sum(r["test net (chosen)"] for r in wf); tot_b = sum(r["test net (18/200)"] for r in wf)
        s.append(f"- Walk-forward ({len(wf)} folds, best TRAIN pair re-chosen each fold): chosen pairs {', '.join(r['chosen fast/trend'] for r in wf)}; test-month net {money(tot_sel)} pts versus {money(tot_b)} pts for the fixed 18/200; the re-optimised pair beat 18/200 in {won}/{len(wf)} folds.")
    return "\n".join(s) + "\n"


def variants_block(instr, cfg, tf):
    if not VAR: return ""
    rows = [(k.split("|")[-1], v) for k, v in VAR["variants"].items() if k.startswith(f"{instr}|{cfg}|{C.TF_NAME[tf]}|")]
    if not rows: return ""
    helpful = [f"{vid} {v['label']} (net {money(v['metrics']['net_pts'])}, OOS {money(v['splits']['OOS']['net_pts'])})" for vid, v in rows if v["vs_base"] == "helpful"]
    harmful = [vid for vid, v in rows if v["vs_base"] == "harmful"]
    robust = [f"{vid} (net {money(v['metrics']['net_pts'])}, OOS {money(v['splits']['OOS']['net_pts'])})" for vid, v in rows if v["verdict"] == "robust"]
    mt = [(k.split("|")[2], v) for k, v in VAR["mtf"].items() if k.startswith(f"{instr}|{cfg}|") and v["entry"] == C.TF_NAME[tf]]
    mt_help = [f"{mid} HTF {v['htf']} {k.split('|')[-1] if False else ''}(net {money(v['metrics']['net_pts'])}, OOS {money(v['splits']['OOS']['net_pts'])})" for mid, v in mt if v["vs_base"] == "helpful"]
    return (f"**{C.TF_NAME[tf]} {cfg}: variants** ({len(rows)} filters, {len(mt)} HTF gates)\n\n- Helpful in all three splits: {'; '.join(helpful) if helpful else 'none'}.\n- Harmful (worse expectancy in 2+ splits): {', '.join(harmful) if harmful else 'none'}.\n"
            f"- Variants that pass the robust rule: {'; '.join(robust) if robust else 'none'}.\n- HTF gates helpful in all splits: {'; '.join(mt_help) if mt_help else 'none'}.\n")


def instrument_report(instr):
    nm = CO.INSTR[instr]["name"]; nar = NAR.get(instr, {})
    L = [f"# {nm}: final report (SimpleSMA18Bot logic, 3 Jan 2022 to 26 Sep 2026)\n", nar.get("summary", ""), "\n## 1. Setup\n",
         f"Data: Upstox 1-minute index candles (IST, 09:15-15:29, 1,174 sessions) cross-checked against the official NSE daily series; daily official history 2007-2026 for the long D1 test. See data/DATA_AUDIT.md. "
         f"Costs: scenario A gross, B realistic (spread {CO.INSTR[instr]['B']['spread_pts']} pts, slippage {CO.INSTR[instr]['B']['slip_pts']} pts per side, all statutory charges and Rs 20 brokerage per order), C stress. Money unit: index points per unit; one futures lot = {CO.INSTR[instr]['lot']} units; capital per lot for percentages Rs {CO.INSTR[instr]['capital_per_lot']:,.0f}. "
         "Configurations: AS-IS (v1.00 rules, 1 point = 1 tick) and FINAL_H4 (the ATR-scaled exit stack selected in the gold study). The volume filter cannot be evaluated on an index and is off in both.\n",
         "Splits fixed before the runs: TRAIN 2022-01-03..2024-08-31, VAL 2024-09-01..2025-08-31, OOS 2025-09-01..2026-09-26. Verdict rule: robust = positive expectancy and PF > 1 after B costs in all three splits with >= 30 trades each.\n"]
    for cfg in C.CONFIGS:
        L.append(f"\n## 2{'a' if cfg == 'ASIS' else 'b'}. Every timeframe, {cfg} (scenario B unless stated)\n"); L.append(C.md_table(tf_table(instr, cfg)))
    L.append("\n## 3. Year by year (scenario B, candidate timeframes)\n")
    for cfg in C.CONFIGS:
        L.append(f"\n**{cfg}**\n"); L.append(C.md_table(yearly_table(instr, cfg, CANDIDATES[instr])))
    dl = {k: v for k, v in BASE["daily_long"].items() if k.startswith(instr)}
    L.append("\n## 4. D1 on the official daily history 2010-2026\n")
    rows = [{"config": k.split("|")[1], "scenario": k.split("|")[2], "trades": v["metrics"]["trades"], "net pts": v["metrics"]["net_pts"], "PF": v["metrics"]["pf"], "exp R": v["metrics"]["exp_r"], "max DD pts": v["metrics"]["max_dd_pts"],
             "years > 0": f"{sum(1 for y in v['by_year'].values() if y[1] > 0)}/{len(v['by_year'])}", "by year (net)": ", ".join(f"{y}: {vv[1]:.0f}" for y, vv in v["by_year"].items())} for k, v in dl.items()]
    L.append(C.md_table(pd.DataFrame(rows)))
    L.append("\n## 5. Trade quality, market conditions, robustness and variants of the candidate timeframes\n")
    for cfg in C.CONFIGS:
        for tf in CANDIDATES[instr]:
            b = BASE["runs"].get(f"{instr}|{cfg}|{C.TF_NAME[tf]}|B")
            if not b or b["metrics"]["net_pts"] <= 0: continue
            L.append(f"\n### {C.TF_NAME[tf]} {cfg} (verdict {b['verdict']})\n"); L.append(quality_block(instr, cfg, tf)); L.append(regime_block(instr, cfg, tf)); L.append(sweep_block(instr, cfg, tf)); L.append(variants_block(instr, cfg, tf))
    L.append("\n## 6. Cost sensitivity\n")
    if COSTS:
        rows = [r for r in COSTS["gross_to_net"] if r["instrument"] == instr and r["tf"] in ("15m", "30m", "1h", "2h", "4h")]
        L.append(C.md_table(pd.DataFrame(rows).drop(columns=["instrument"])))
        sl = [r for r in COSTS["slippage"] if r["instrument"] == instr]
        if sl:
            L.append("\nSlippage per side varied (B charges kept), net points:\n"); L.append(C.md_table(pd.DataFrame(sl).drop(columns=["instrument"])))
    L.append("\n## 7. Answers\n"); L.append(nar.get("answers", ""))
    L.append("\n## 8. Files\n- backtests/" + instr + "/: every run's trade list (config_TF_scenario_trades.csv.gz)\n- research/timeframe_analysis.md, cost_analysis.md, regime_analysis.md, robustness_analysis.md, walk_forward_analysis.md, variants_mtf_analysis.md, experiment_log.csv\n")
    return "\n".join(L)


for instr in C.INSTRUMENTS:
    open(os.path.join(HERE, f"{'NIFTY50' if instr == 'nifty50' else 'BANKNIFTY'}_FINAL_REPORT.md"), "w", encoding="utf-8").write(instrument_report(instr))

# ---------------------------------------------------------------- combined report
nar = NAR.get("combined", {})
L = ["# Indian market final report: SimpleSMA18Bot on NIFTY 50 and NIFTY BANK (2022-2026)\n", nar.get("summary", ""), "\n## Comparison\n"]
rows = []
for instr in C.INSTRUMENTS:
    best = NAR.get(instr, {}).get("best")
    cfg, tfn = (best or "FINAL_H4/15m").split("/"); tf = [k for k, v in C.TF_NAME.items() if v == tfn][0]
    b = BASE["runs"][f"{instr}|{cfg}|{tfn}|B"]; m = b["metrics"]; s = b["splits"]; a = BASE["runs"][f"{instr}|{cfg}|{tfn}|A"]["metrics"]
    yr = b["yearly"]; pos_years = sum(1 for y in yr if y["net_pts"] > 0)
    rows.append({"metric": "best stable timeframe (config)", instr: f"{tfn} ({cfg}), verdict {b['verdict']}"})
    for k, v in [("total trades", m["trades"]), ("win rate %", m["win_rate"]), ("profit factor (B)", m["pf"]), ("expectancy pts / R", f"{m['exp_pts']} / {m['exp_r']}"), ("net R", m["net_r"]), ("net pts (B)", m["net_pts"]),
                 ("max DD pts (% of capital)", f"{m['max_dd_pts']} ({m.get('max_dd_pct_cap')}%)"), ("monthly Sharpe", m["sharpe_m"]), ("cost impact: gross A -> net B pts", f"{a['net_pts']} -> {m['net_pts']}"),
                 ("yearly consistency", f"{pos_years}/{len(yr)} years positive"), ("out-of-sample (2025-09..2026-09)", f"net {s['OOS']['net_pts']} pts, PF {s['OOS'].get('pf')}, {s['OOS']['trades']} trades"), ("top-5 trades share of net %", m.get("top5_trades_share"))]:
        rows.append({"metric": k, instr: v})
cmp = pd.DataFrame(rows).groupby("metric", sort=False).first().reset_index().rename(columns={"nifty50": "NIFTY 50", "banknifty": "NIFTY BANK"})
L.append(C.md_table(cmp))
if REG:
    L.append("\n## Why the two indices differ\n"); ch = pd.DataFrame(REG["characteristics"]).set_index("instrument").T.reset_index().rename(columns={"index": "metric"}); L.append(C.md_table(ch)); L.append("\n" + nar.get("why_differ", ""))
L.append("\n## Answers to the twelve questions\n"); L.append(nar.get("answers", ""))
L.append("\n## Method and reproducibility\n- Engine: strategy/engine_in.py (the gold research engine with the market model swapped; exact v1.00 rule port), strategy/costs.py, strategy/common_in.py.\n- Data: data/DATA_AUDIT.md.\n- Runs: backtests/run_baseline.py, experiments/run_cost_analysis.py, experiments/sessions/run_regime_session.py, experiments/timeframe/run_sweeps_wf.py, experiments/filters/run_variants.py, reports/make_reports.py.\n- Every run is logged in research/experiment_log.csv; every trade list is saved under backtests/.\n")
open(os.path.join(HERE, "INDIAN_MARKET_FINAL_REPORT.md"), "w", encoding="utf-8").write("\n".join(L))
print("reports written")
