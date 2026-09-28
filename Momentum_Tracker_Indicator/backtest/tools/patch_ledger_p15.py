"""One-off: adds the phase 14 and phase 15 blocks to build_master_ledger.py and the phase 15 rows to README.md (already applied; kept for reference)."""
import io
s = open("build_master_ledger.py", encoding="utf-8").read()
block = r'''
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
'''
marker = 'os.makedirs("results/ledger", exist_ok=True)'
if "# phase 15 post-release transition" not in s:
    s = s.replace(marker, block + marker); open("build_master_ledger.py", "w", encoding="utf-8").write(s)
r = open("README.md", encoding="utf-8").read()
rows = ("| `post_release_ticks.py` | Phase 15: tick timeline after the 15:30 release in 14 bands, spread-normalisation times (2x/1.5x/1.25x, sustained 5 s), price-discovery curve, information value after normalisation (unconditional, five shock states, continuation), same-day controls. Development 2025 only; writes `results/phase15/summary.json` and CSVs. |\n"
        "| `post_release_candidates.py` | Phase 15 step 2: Track B (time to a 0.5-2 ATR move and 30-min range versus controls), OCO breakout after the release over delay bands and the normalisation time, cost scenarios, shock-range breakout, controls (`results/phase15/candidates.json`). |\n"
        "| `post_release_momentum.py` | Phase 15 step 3: delayed momentum by delay band and hold with a pre-declared plateau retention rule (`results/phase15/momentum.json`). |\n"
        "| `make_phase15_report.py` | Builds `phase15_report.html` from `results/phase15/*.json` and `narrative_phase15.json`. |\n")
if "post_release_ticks.py" not in r:
    r = r.replace("| `tools/regression.py` |", rows + "| `tools/regression.py` |"); open("README.md", "w", encoding="utf-8").write(r)
print("patched")
