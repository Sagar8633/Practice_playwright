"""PHASE 4 (STEPS 12-16, sections 12, 22, 26): exit / protection research. Original entries and the original swing stop
are kept; the protection stack changes. Strategy view, realistic costs, DEV/VAL/OOS slices.

"Previous trailing-SL strategy" = the TWK MomentumEA 3-stage trail used in the user's earlier gold bot
(+200 pts: trail the Supertrend(1.5,10) line; +500 pts: lock +100 and trail 1:1 with a 400-pt gap). It is tested as
E13/E14 (with and without the MA18 exit) = "Current Entry + Previous Trailing Logic" hybrids.
"""
import os, time
from dataclasses import replace
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C
from common import evaluate, classify, KEYS

OUT = os.path.join(C.RES, "exits"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
TFS = [1, 5, 15, 1440]
BE = dict(be_enable=True); NOBE = dict(be_enable=False)
VARIANTS = {
    "E00 SL only + MA18 exit (no BE, no protection)": dict(protection=0, be_enable=False),
    "E01 EA default: BE + swing after 500 + MA18": dict(),
    "E02 Chandelier(22,3.0) after 500 + BE + MA18": dict(protection=2),
    "E03 Chandelier immediate + BE + MA18 (v13)": dict(protection=2, prot_start_mode=0),
    "E04 Trailing 1000/500/50 + BE + MA18": dict(protection=4),
    "E05 BE only + MA18": dict(protection=0),
    "E06 Trailing 1000/500/50 without BE + MA18": dict(protection=4, be_enable=False),
    "E07 Chandelier + Trailing + BE + MA18": dict(protection=6, prot_start_mode=0),
    "E08 Swing immediate + BE + MA18": dict(prot_start_mode=0),
    "E09 ATR trail 2.0x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=2.0),
    "E10 ATR trail 3.0x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=3.0),
    "E11 ATR trail 1.5x immediate + BE + MA18": dict(protection=8, prot_start_mode=0, trail_start_pts=0, atr_trail_mult=1.5),
    "E12 ATR trail 2.0x after 500 + BE + MA18": dict(protection=8, prot_start_mode=1, trail_start_pts=0, atr_trail_mult=2.0),
    "E13 TWK 3-stage trail (previous strategy) + MA18, no BE": dict(protection=16, be_enable=False),
    "E14 TWK 3-stage trail alone (no MA18 exit, no BE)": dict(protection=16, be_enable=False, ma_exit=False),
    "E15 EA default without MA18 exit": dict(ma_exit=False),
    "E16 Chandelier immediate without MA18 exit + BE": dict(protection=2, prot_start_mode=0, ma_exit=False),
    "E17 Swing after 500 + MA18, no BE": dict(be_enable=False),
    "E18 ATR-scaled: BE 1 ATR, swing after 1 ATR, MA18": dict(thr_mode=1, be_trigger_pts=100, prot_start_pts=100),
    "E19 ATR-scaled: BE 1 ATR + trailing start 2 ATR dist 1 ATR + MA18": dict(thr_mode=1, protection=4, be_trigger_pts=100, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10),
    "E20 R-scaled: BE 1R, swing after 1R, MA18": dict(thr_mode=2, be_trigger_pts=100, prot_start_pts=100),
    "E21 R-scaled: BE 1R + trailing start 2R dist 1R + MA18": dict(thr_mode=2, protection=4, be_trigger_pts=100, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10),
    "E22 Chandelier(22,2.0) immediate + BE + MA18": dict(protection=2, prot_start_mode=0, atr_mult=2.0),
    "E23 Chandelier(22,4.0) immediate + BE + MA18": dict(protection=2, prot_start_mode=0, atr_mult=4.0),
    "E24 R-lock: +1R lock +0.5R, swing, MA18, no BE": dict(thr_mode=2, protection=33, lock_trigger_pts=100, lock_level_pts=50, prot_start_pts=100, be_enable=False),
    "E25 Chandelier immediate, no BE, no MA18 (pure chandelier)": dict(protection=2, prot_start_mode=0, be_enable=False, ma_exit=False),
    "E26 Trailing 1000/500/50, no BE, no MA18 (pure trailing)": dict(protection=4, be_enable=False, ma_exit=False),
    "E27 BE 1000/10 + swing after 500 + MA18": dict(be_trigger_pts=1000),
    "E28 BE 2000/10 + swing after 500 + MA18": dict(be_trigger_pts=2000),
    "E29 time exit 5 bars (not in profit) + EA default": dict(time_exit_bars=5),
}
GB = ("giveback_avg", "profit_to_loss_2usd", "profit_to_loss_1r", "avg_win", "avg_loss", "avg_mfe_usd", "avg_hold_min")

results = {}; rows = []
for tf in TFS:
    name = C.TF_NAME[tf]
    base_p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
    results[name] = {}
    base = None
    for vname, kw in VARIANTS.items():
        p = replace(base_p, **kw)
        var, tr = evaluate(p)
        if vname.startswith("E01"):
            base = var
        results[name][vname] = {"metrics": var, "params": kw}
        for k, m in var.items():
            rows.append({"tf": name, "variant": vname, "period": k, **{kk: m.get(kk) for kk in KEYS}, **{kk: m.get(kk) for kk in GB}, "exit_mix": m.get("exit_mix")})
        a = var["ALL"]
        print(f"{name:3} {vname:62} trades {a['trades']:6} net {a['net_profit']:10.2f} PF {a.get('profit_factor')!s:>6} expR {a.get('expectancy_r')!s:>7} DD {a['max_dd_usd']:9.2f} gb {a.get('giveback_avg')!s:>6} P2L {a.get('profit_to_loss_2usd')!s:>5} | DEV {var['DEV'].get('expectancy_r')!s:>7} VAL {var['VAL'].get('expectancy_r')!s:>7} OOS {var['OOS'].get('expectancy_r')!s:>7} ({time.time()-t0:.0f}s)", flush=True)
    for vname, r in results[name].items():
        r["class"] = "base" if vname.startswith("E01") else classify(base, r["metrics"])
        p = replace(base_p, **r["params"])
        C.log_experiment("P4-exits", vname, p, r["metrics"]["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                         oos_result=f"OOS net {r['metrics']['OOS']['net_profit']} PF {r['metrics']['OOS'].get('profit_factor')} expR {r['metrics']['OOS'].get('expectancy_r')}", conclusion=r["class"])

pd.DataFrame(rows).to_csv(os.path.join(OUT, "exit_table.csv"), index=False)
C.save_json(results, "exits/summary.json")

# ------------------------------------------------------------ markdown: section 26 table, section 12 table, section 22 comparison
L = ["# Phase 4: exit / protection research (original entries and swing stop kept)", "", "Strategy view, 0.01 lot, realistic costs. Every variant across M1/M5/M15/D1 with DEV/VAL/OOS expectancy in R.", "",
     "## Section 26: exit comparison table", "", "| Timeframe | Exit method | Net $ | PF | Max DD $ | Win % | Avg trade $ | Avg win $ | Avg loss $ | Giveback avg $ | P->L >$2 | P->L >=1R | exp R DEV/VAL/OOS | class |",
     "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
for name in results:
    for vname, r in results[name].items():
        a = r["metrics"]["ALL"]; m = r["metrics"]
        L.append(f"| {name} | {vname} | {a['net_profit']} | {a.get('profit_factor')} | {a['max_dd_usd']} | {a.get('win_rate')} | {a.get('expectancy')} | {a.get('avg_win')} | {a.get('avg_loss')} | {a.get('giveback_avg')} | {a.get('profit_to_loss_2usd')} | {a.get('profit_to_loss_1r')} | {m['DEV'].get('expectancy_r')}/{m['VAL'].get('expectancy_r')}/{m['OOS'].get('expectancy_r')} | {r['class']} |")
L += ["", "## Section 12: Chandelier vs trailing vs break-even vs hybrid (net $ / PF / maxDD / win % / exp R / giveback / P->L>$2)", "",
      "| Timeframe | Chandelier (E03) | Trailing (E04) | Break-even only (E05) | Chandelier + Trailing (E07) | Swing (EA, E01) | TWK previous trail (E13) | ATR trail 2x (E09) |", "|---|---|---|---|---|---|---|---|"]


def cell(m):
    a = m["ALL"]
    return f"{a['net_profit']} / {a.get('profit_factor')} / {a['max_dd_usd']} / {a.get('win_rate')} / {a.get('expectancy_r')} / {a.get('giveback_avg')} / {a.get('profit_to_loss_2usd')}"


for name in results:
    r = results[name]
    keys = [k for k in r if k.startswith(("E03", "E04", "E05", "E07", "E01", "E13", "E09"))]
    order = {k[:3]: k for k in keys}
    L.append(f"| {name} | " + " | ".join(cell(r[order[c]]["metrics"]) for c in ("E03", "E04", "E05", "E07", "E01", "E13", "E09")) + " |")
L += ["", "## Section 22: current EA vs previous trailing strategy vs hybrids", "", "| Timeframe | Current EA (E01) | Current entry + previous TWK trail (E13) | TWK trail alone (E14) | Current entry + Chandelier (E03) | ATR-adaptive exit (E19) | R-adaptive exit (E21) |", "|---|---|---|---|---|---|---|"]
for name in results:
    r = results[name]; order = {k[:3]: k for k in r}
    L.append(f"| {name} | " + " | ".join(cell(r[order[c]]["metrics"]) for c in ("E01", "E13", "E14", "E03", "E19", "E21")) + " |")
L.append(""); L.append("Cell format: net $ / PF / max DD $ / win % / expectancy R / average giveback $ / profitable->loss trades (>$2).")
with open(os.path.join(OUT, "EXITS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
