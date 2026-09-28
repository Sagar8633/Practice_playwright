"""Builds the permanent Edge Hypothesis Ledger (results/ledger/edge_hypothesis_ledger.csv) from every study so far:
phase 2 signal edge, phase 5-9 candidates, phase 12 discovery ledger and follow-up, phase 13 range/straddle and cross-asset.
Columns: ID, source, phenomenon, mechanism, dataset, n, dev, val, oos, cost_model, execution, status, reason.
"""
import json, os, glob
import pandas as pd

rows = []
def add(src, phen, mech, dataset, n, dev, val, oos, cost, execu, status, reason, phase):
    rows.append(dict(ID=f"{phase}-{len(rows)+1:03d}", information_source=src, phenomenon=phen, mechanism=mech, dataset=dataset, sample_size=n, development=dev, validation=val, out_of_sample=oos,
                     cost_model=cost, execution_assumptions=execu, status=status, reason=reason, phase=phase))
COST = "XM median spread by year (32-51 pts), no commission, no slippage"; EXEC = "entry at next M1 open (ask for buys), bar-level paths, ties = stop"
DS = "Dukascopy XAUUSD M1 -> server time, Sep 2021-Sep 2026 (39/61 months)"
# phase 2 / 5-9 (signal-level)
if os.path.exists("results/signal/signal_lab.json"):
    L = json.load(open("results/signal/signal_lab.json"))
    for g in L["directional"]:
        add("XAUUSD OHLC", f"TWK Supertrend flip, +/-{g['stop']} ATR first passage", "indicator flip predicts direction", DS, L["n_signals"], f"net {g['net_exp_DEV']}R", f"net {g['net_exp_VAL']}R", f"net {g['net_exp_OOS']}R", COST, EXEC, "REJECT", f"gross hit {g['gross_hit']} (coin flip), net PF {g['net_pf']}", "P2")
    for t in L["timing"]:
        add("XAUUSD OHLC", f"TWK flip, entry: {t['entry']}", "entry timing changes the odds", DS, t["n_ALL"], f"{t['exp11_DEV']}R", f"{t['exp11_VAL']}R", f"{t['exp11_OOS']}R", COST, EXEC, "REJECT", "within 0.02R of immediate entry", "P2")
if os.path.exists("results/edge/edge_lab.json"):
    L = json.load(open("results/edge/edge_lab.json"))
    for a in L["acceptance"]:
        st = "CONTROL" if a["kind"] == "control" else ("CANDIDATE" if a.get("gate_pf_all_periods") else "REJECT")
        add("XAUUSD OHLC + structure", a["candidate"], "structure / regime / model conditions the flip", DS, a["signals"], f"PF {a['DEV_pf']}", f"PF {a['VAL_pf']}", f"PF {a['OOS_pf']}", COST, EXEC + ", shipped M3 management, 0.02 lot", st, "" if st != "REJECT" else "PF < 1 in a selection period", "P5-9")
    ml = L.get("ml", {})
    if "auc_OOS" in ml: add("XAUUSD OHLC, 52 features", "gradient-boosted classifier A/B vs D", "any combination of entry-time features predicts the outcome", DS, 20000, f"AUC {ml['auc_DEV']}", f"AUC {ml['auc_VAL']}", f"AUC {ml['auc_OOS']}", COST, "top decile fixed on DEV", "REJECT", "OOS AUC 0.54, top decile negative in VAL and OOS", "P5-9")
# phase 12 discovery ledger
if os.path.exists("results/discovery/ledger.csv"):
    D = pd.read_csv("results/discovery/ledger.csv")
    for r in D.to_dict("records"):
        f = lambda p, k: r.get(f"{p}_1.0x2.0_{k}")
        add("XAUUSD OHLC events", f"{r['hypothesis']} ({r['direction']})", r["family"], DS + f", {r['tf']}", r["n"], f"net {f('DEV','exp')}R PF {f('DEV','pf')}", f"net {f('VAL','exp')}R PF {f('VAL','pf')}", f"net {f('OOS','exp')}R PF {f('OOS','pf')}", COST, EXEC, r["status"],
            "fails DEV after costs" if r["status"] == "REJECT" else ("too few events" if r["status"] == "DATA_INSUFFICIENT" else ""), "P12")
if os.path.exists("results/discovery/followup.csv"):
    F = pd.read_csv("results/discovery/followup.csv"); F = F[F.cost == "x1.0"]
    for r in F.to_dict("records"):
        add("XAUUSD OHLC events", f"{r['hypothesis']} ({r['direction']}), shape {r['shape']}, hold {r['horizon_bars']}", "wider unit / longer hold clears the spread", DS, r["DEV_n"], f"net {r['DEV_exp']}R", f"net {r['VAL_exp']}R", f"net {r['OOS_exp']}R", COST, EXEC, "REJECT" if (r["DEV_exp"] or 0) <= 0 else "WEAK", "DEV net <= 0", "P12f")
# phase 13 range / straddle
if os.path.exists("results/phase13/range_objective.json"):
    Rj = json.load(open("results/phase13/range_objective.json"))
    for r in Rj["straddle"]:
        add("XAUUSD OHLC events", f"straddle after {r['event']} (a={r['a']}, T={r['T']})", "range prediction monetised without direction", DS, r["n"], f"net {r['exp_DEV']} ATR", f"net {r['exp_VAL']} ATR", f"net {r['exp_OOS']} ATR", COST, "OCO stop orders at +/- a ATR, exits at bid/ask", "REJECT" if (r["exp_DEV"] or 0) <= 0 else "WEAK", "DEV net <= 0" if (r["exp_DEV"] or 0) <= 0 else "", "P13F")
# phase 13 cross-asset
if os.path.exists("results/phase13/xasset.json"):
    X = json.load(open("results/phase13/xasset.json"))
    for r in X["monetisation"]:
        ok = all((r.get(f"{p}_exp") or -1) > 0 for p in ("DEV", "VAL", "OOS"))
        add(f"cross-asset: {r['asset']} (XM H1)", f"gold after a 2-sigma hourly shock in {r['asset']}, {r['rule']}", "other-market information leads gold", "XM H1 2021-2026 (XM GOLD H1 + asset H1)", r["n"], f"net {r['DEV_exp']}R PF {r['DEV_pf']}", f"net {r['VAL_exp']}R PF {r['VAL_pf']}", f"net {r['OOS_exp']}R PF {r['OOS_pf']}", "XM H1 spread per bar", "entry at next H1 open, 1 ATR stop / 2 ATR target, 48-bar hold", "CANDIDATE" if ok else "REJECT", "" if ok else "not positive in all periods", "P13C")
# untestable sources
for src, phen, need in (("economic calendar", "surprise -> direction / volatility", "event list with actual, forecast, previous, timestamp"), ("tick data / bid-ask", "microstructure imbalance -> +0.1 to +0.5R", "Dukascopy ticks (free) or broker ticks"),
                        ("order book", "order-flow persistence", "not available for CFDs"), ("manual trades", "human selection has information", "100-trade log with skipped signals")):
    add(src, phen, "information absent from OHLC", "not available", 0, "", "", "", "", "", "DATA_INSUFFICIENT", f"needs: {need}", "P13")

# phase 14 tick-level release straddle (frozen spec, Dukascopy ticks, DEV 2025 Thu/Fri)
if os.path.exists("results/phase14/summary.json"):
    P = json.load(open("results/phase14/summary.json")); TK = "Dukascopy XAUUSD ticks, 15:00-18:00 server, Thu/Fri 2025 (102 days)"; TX = "stop orders trigger on ask (buy) / bid (sell), fill = worse of trigger tick and +250 ms, 250 ms cancel latency"
    for r in P["by_group"]:
        if r["group"].startswith("DEV"):
            add("tick bid/ask at the 15:30 release", f"OCO stop straddle 0.25/0.75 ATR at 15:30:00, {r['group'][9:]}", "range expansion monetised by symmetric stops", TK, r["n"], f"net {r['net']:.2f} ATR PF {r['pf']:.2f}, gross {r['gross']:.2f}", "", "not consulted (rejected on DEV)", "Dukascopy spread as quoted + XM overlay", TX, "REJECT", f"the spread at the release puts the trigger inside the quote; {r['spread_driven']*100:.0f}% spread-driven triggers, median fill {r['t_trigger_med_ms']:.0f} ms", "P14")
    for r in P["plateau"]:
        add("tick bid/ask at the 15:30 release", f"straddle plateau: {r['kind']} = {r['value']}", "sensitivity of the frozen straddle", TK, r["n"], f"net {r['net']:.2f} ATR PF {r['pf']:.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT", "negative on development at every value; delayed start least negative at +120 s", "P14")
    for r in P["controls"]:
        add("tick bid/ask, random same-day time", r["control"], "control", TK, r["n"], f"net {r['net']:.2f} ATR PF {r['pf']:.2f}", "", "", "Dukascopy spread as quoted", TX, "CONTROL", "the release straddle loses five times more than a random same-day straddle", "P14")
# phase 15 post-release transition (DEV 2025 only)
if os.path.exists("results/phase15/summary.json"):
    P = json.load(open("results/phase15/summary.json")); TK = "Dukascopy XAUUSD ticks, Thu/Fri 2025 (95 events)"; TX = "entry at ask (buy) / bid (sell), exit at bid / ask, fills at the triggering quote, no latency"
    nm = {r["mult"]: r for r in P["normalisation"] if r["group"] == "All"}
    add("tick bid/ask after the 15:30 release", f"spread normalisation: 2x at {nm[2.0]['p50_s']:.0f} s, 1.5x at {nm[1.5]['p50_s']:.0f} s, 1.25x at {nm[1.25]['p50_s']:.0f} s (medians), 1.25x p90 {nm[1.25]['p90_s']:.0f} s", "the liquidity shock ends and a normal quote returns", TK, P["ok"], "measured", "", "not consulted", "", "", "PHENOMENON", "descriptive; Mon-Wed not downloaded; calendar unavailable so weekday is a proxy", "P15")
    for r in P["information"]:
        if r["X"] in (0.5, 1.0) and r["horizon_min"] == 30 and r["side"] == 1:
            add("tick bid/ask after normalisation", f"unconditional +{r['X']} before -{r['X']} ATR within 30 min from the 1.5x normalisation time (long side)", "direction after the shock", TK, r["n"], f"mid hit {r['hit_mid']:.2f} (CI {r['ci_lo']:.2f}-{r['ci_hi']:.2f}), executable hit {r['hit_exec']:.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT", "coin flip on mid; the executable race is lost to the spread", "P15")
    for r in P["states"]:
        if r["X"] == 0.5 and r["horizon_min"] == 30:
            add("tick bid/ask after normalisation", f"state {r['state']} predicts +0.5 before -0.5 ATR within 30 min", "shock microstructure carries direction", TK, r["n"], f"mid hit {r['hit_mid']:.2f} (CI {r['ci_lo']:.2f}-{r['ci_hi']:.2f}), executable {r['hit_exec']:.2f}, mean close {r['close']:+.2f} ATR", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT", "confidence interval contains 0.5; executable hit rate below 0.35", "P15")
    for r in P["continuation"]:
        if r["horizon_min"] == 30:
            add("tick bid/ask after normalisation", f"continuation of the first clean move, +/-{r['X']} ATR race, 30 min", "first move continues after the spread normalises", TK, r["n"], f"mid continuation {r['cont_mid']:.2f} (CI {r['ci_lo']:.2f}-{r['ci_hi']:.2f}), executable {r['cont_exec']:.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT", "below 0.5 on mid; reversal is not above 0.5 with confidence either", "P15")
if os.path.exists("results/phase15/candidates.json"):
    Cj = json.load(open("results/phase15/candidates.json")); TK = "Dukascopy XAUUSD ticks, Thu/Fri 2025 (95 events)"; TX = "OCO stops trigger on ask/bid, fill at the triggering quote, stop = opposite trigger, 30-min horizon, exit at the executable quote"
    for r in Cj["oco_matrix"]:
        add("tick bid/ask after the release", f"OCO breakout k={r['k']} T={r['T']} ATR placed at {r['start']}", "post-release volatility monetised two-sided", TK, r["n"], f"net {r['net']:+.2f} ATR (se {r['se']:.2f}) PF {r['pf']:.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT" if r["net"] <= 0 or r["net"] < 2 * r["se"] else "WEAK", "not positive with |t|>=2 at one spread; controls at the same rules are similar", "P15")
    for r in Cj["shock_breakout"]:
        if r["group"] == "events" and r["cost"] == 1.0:
            add("tick bid/ask after the release", f"breakout of the first-minute shock range, target {r['target_name']}", "the shock range as a structure level", TK, r["n"], f"net {r['net']:+.2f} ATR (se {r['se']:.2f}) PF {r['pf']:.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, "REJECT", "negative at one spread; controls with the same rule are also negative", "P15")
    tb = {(r["start"], r["X"]): r for r in Cj["trackb"]}
    add("tick mid after normalisation", f"Track B: time to a 1-ATR move, events {tb[('t_norm 1.5x', 1.0)]['t_med_s']:.0f} s vs controls {tb[('control', 1.0)]['t_med_s']:.0f} s; 30-min range equal", "excess realised volatility after the shock", TK, 95, "no excess after normalisation", "", "not consulted", "", "", "REJECT", "the release's volatility is spent inside the shock; after the quote normalises the window matches a same-day control", "P15")
    add("tick bid/ask after normalisation", "pullback into the shock range in the direction of the first move", "retracement entry", TK, 0, "", "", "", "", "", "REJECT", Cj["pullback"], "P15")
if os.path.exists("results/phase15/momentum.json"):
    Mj = json.load(open("results/phase15/momentum.json")); TK = "Dukascopy XAUUSD ticks, Thu/Fri 2025 (95 events)"; TX = "entry at ask/bid at the delay band, exit at bid/ask after the hold, no stop"
    kept = {(r["start"], r["hold"]) for r in Mj["retained"]}
    for r in Mj["grid"]:
        if r["cost"] == 1.0 and r["variant"] == "no stop":
            st = "CANDIDATE" if (r["start"], r["hold"]) in kept else "REJECT"
            add("tick bid/ask after the release", f"delayed momentum: direction of the displacement at {r['start']}, hold {r['hold']} min", "the shock direction persists", TK, r["n"], f"net {r['net']:+.2f} ATR (t {r['t']:.1f}) hit {r['hit']:.2f} gross {r['gross']:+.2f}", "", "not consulted", "Dukascopy spread as quoted", TX, st, "retention rule: |t|>=2 and both neighbouring delay bands positive" + ("; passed on development only, needs VAL/OOS" if st == "CANDIDATE" else "; not met, and the same rule at 16:30/17:15 controls gives the same numbers"), "P15")
    for r in Mj["controls"]:
        if r["cost"] == 1.0 and r["variant"] == "no stop":
            add("tick bid/ask, same-day 16:30 / 17:15", f"control: direction of the preceding 60 s, hold {r['hold']} min", "control", TK, r["n"], f"net {r['net']:+.2f} ATR (t {r['t']:.1f}) gross {r['gross']:+.2f}", "", "", "Dukascopy spread as quoted", TX, "CONTROL", "2025 US-session continuation exists at the same size without a release; not significant net", "P15")
os.makedirs("results/ledger", exist_ok=True)
L = pd.DataFrame(rows); L.to_csv("results/ledger/edge_hypothesis_ledger.csv", index=False)
print(len(L), "ledger entries"); print(L.status.value_counts().to_dict())
