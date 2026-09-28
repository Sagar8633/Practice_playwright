"""PHASE 1 (entry validation, one filter at a time, original exits kept) and PHASE 2 (progressive combinations).

Strategy view: fixed 0.01 lot, nominal balance, no SL% filter, realistic costs (B_real). Each variant is run once over the
full 6 years; DEV / VAL / OOS metrics are taken from the time slices of that run (fixed lots make trades independent of
the balance path). Classification rule (declared before running):
  Helpful  : expectancy_r and PF both improve vs base in DEV *and* VAL *and* OOS, with >= 30 trades in each split
  Harmful  : expectancy_r worse than base in at least two of the three splits, or trades removed > 95%
  Neutral  : everything else
"""
import json, os, time
from dataclasses import replace

import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

OUT = os.path.join(C.RES, "filters"); os.makedirs(OUT, exist_ok=True)
t0 = time.time()
TFS = [1, 5, 15, 1440]
H = lambda a, b: tuple(range(a, b))
VARIANTS = {
    "F01 volume filter OFF": dict(use_volume=False),
    "F02 MA200 trend filter OFF": dict(use_trend=False),
    "F03 1-bar confirmation": dict(confirm_bars=1),
    "F04 3-bar confirmation": dict(confirm_bars=3),
    "F05 ADX>=25": dict(use_adx=True, adx_min=25.0),
    "F06 ADX>=20": dict(use_adx=True, adx_min=20.0),
    "F07 ADX>=30": dict(use_adx=True, adx_min=30.0),
    "F08 ADX>=25 rising(3)": dict(use_adx=True, adx_min=25.0, adx_rising=True),
    "F09 ADX>=25 consecutive rise(3)": dict(use_adx=True, adx_min=25.0, adx_consecutive=True),
    "F10 session London 8-17": dict(use_session=True, session_hours=H(8, 17)),
    "F11 session New York 13-22": dict(use_session=True, session_hours=H(13, 22)),
    "F12 session London+NY 8-22": dict(use_session=True, session_hours=H(8, 22)),
    "F13 session Tokyo 0-9": dict(use_session=True, session_hours=H(0, 9)),
    "F14 session overlap 13-17": dict(use_session=True, session_hours=H(13, 17)),
    "F15 pending expires 1 bar": dict(pending_max_bars=1),
    "F16 pending expires 3 bars": dict(pending_max_bars=3),
    "F17 pending invalidation OFF": dict(pending_invalidate=False),
    "F18 entry buffer 0": dict(entry_buffer_pts=0),
    "F19 entry buffer 50": dict(entry_buffer_pts=50),
    "F20 volatility ATR ratio >= 1.0": dict(use_vol_filter=True, vol_filter_min=1.0),
    "F21 volatility ATR ratio <= 1.5": dict(use_vol_filter=True, vol_filter_max=1.5),
    "F22 volatility ATR ratio 0.8-1.5": dict(use_vol_filter=True, vol_filter_min=0.8, vol_filter_max=1.5),
    "F23 max spread 40 pts": dict(max_spread_pts=40.0),
    "F24 MA18 slope over 3 bars": dict(slope_filter_bars=3),
    "F25 not extended |close-MA18| <= 1 ATR": dict(max_dist_atr=1.0),
    "F26 not extended |close-MA18| <= 2 ATR": dict(max_dist_atr=2.0),
}
SKIP_D1 = {"F10", "F11", "F12", "F13", "F14", "F23"}
from common import evaluate, classify, KEYS


results = {}; rows = []
for tf in TFS:
    name = C.TF_NAME[tf]
    base_p = E.Params(tf_minutes=tf, start=C.DATA_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"])
    base, base_tr = evaluate(base_p)
    results[name] = {"BASE": {"metrics": base, "class": "base"}}
    for k, m in base.items():
        rows.append({"tf": name, "variant": "BASE", "period": k, **{kk: m.get(kk) for kk in KEYS}, "class": "base"})
    for vname, kw in VARIANTS.items():
        if tf == 1440 and vname[:3] in SKIP_D1:
            continue
        p = replace(base_p, **kw)
        var, tr = evaluate(p)
        cls = classify(base, var)
        results[name][vname] = {"metrics": var, "class": cls, "params": kw}
        for k, m in var.items():
            rows.append({"tf": name, "variant": vname, "period": k, **{kk: m.get(kk) for kk in KEYS}, "class": cls,
                         "d_trades": m["trades"] - base[k]["trades"], "d_pf": None if m.get("profit_factor") is None or base[k].get("profit_factor") is None else round(m["profit_factor"] - base[k]["profit_factor"], 3),
                         "d_net": round(m["net_profit"] - base[k]["net_profit"], 2), "d_wr": None if m.get("win_rate") is None or base[k].get("win_rate") is None else round(m["win_rate"] - base[k]["win_rate"], 1),
                         "d_dd": round(m["max_dd_usd"] - base[k]["max_dd_usd"], 2), "d_exp": None if m.get("expectancy") is None or base[k].get("expectancy") is None else round(m["expectancy"] - base[k]["expectancy"], 3)})
        C.log_experiment("P1-filters", vname, p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                         oos_result=f"OOS net {var['OOS']['net_profit']} PF {var['OOS'].get('profit_factor')} expR {var['OOS'].get('expectancy_r')}", conclusion=cls)
        a = var["ALL"]
        print(f"{name:3} {vname:40} trades {a['trades']:6} net {a['net_profit']:10.2f} PF {a.get('profit_factor')!s:>6} expR {a.get('expectancy_r')!s:>7} | DEV {var['DEV'].get('expectancy_r')!s:>7} VAL {var['VAL'].get('expectancy_r')!s:>7} OOS {var['OOS'].get('expectancy_r')!s:>7} -> {cls} ({time.time()-t0:.0f}s)", flush=True)

    # ------------------------------------------------------------ PHASE 2: progressive combinations of the helpful filters (ordered by DEV gain)
    helpful = [(v, r) for v, r in results[name].items() if r["class"] == "Helpful"]
    helpful.sort(key=lambda x: -(x[1]["metrics"]["DEV"].get("expectancy_r") or -9))
    combo_rows = []; stacked = {}
    for i, (vname, r) in enumerate(helpful):
        for kk, vv in r["params"].items():
            if kk in stacked and kk == "session_hours":
                stacked[kk] = tuple(sorted(set(stacked[kk]) & set(vv)))
            else:
                stacked[kk] = vv
        p = replace(base_p, **stacked)
        var, tr = evaluate(p)
        cls = classify(base, var)
        label = " + ".join(v[:3] for v, _ in helpful[: i + 1])
        combo_rows.append({"test": f"C{i+1:02d}", "filters": label, **{k: var["ALL"].get(k) for k in ("trades", "profit_factor", "win_rate", "net_profit", "max_dd_usd", "expectancy", "expectancy_r")},
                           "DEV_expR": var["DEV"].get("expectancy_r"), "VAL_expR": var["VAL"].get("expectancy_r"), "OOS_expR": var["OOS"].get("expectancy_r"), "OOS_net": var["OOS"]["net_profit"], "OOS_pf": var["OOS"].get("profit_factor"), "class": cls})
        C.log_experiment("P2-filter-combos", f"stack {label}", p, var["ALL"], "B_real", "6y", filters=C.filter_desc(p), exit_logic=C.exit_desc(p),
                         oos_result=f"OOS net {var['OOS']['net_profit']} PF {var['OOS'].get('profit_factor')}", conclusion=cls)
        if i + 1 >= 6:
            break
    results[name]["COMBOS"] = combo_rows
    print(name, "helpful filters:", [v for v, _ in helpful], flush=True)

tab = pd.DataFrame(rows); tab.to_csv(os.path.join(OUT, "filter_table.csv"), index=False)
C.save_json(results, "filters/summary.json")

# ------------------------------------------------------------ markdown
L = ["# Phase 1: entry filters one at a time (original exits kept) and Phase 2: combinations", "",
     "Strategy view (0.01 lot, realistic costs). Splits: DEV 2020-09..2023-08, VAL 2023-09..2024-12, OOS 2025-01..2026-09. "
     "Helpful = expectancy/R and PF improve in DEV, VAL and OOS with >= 30 trades each; Harmful = worse expectancy/R in >= 2 splits.", ""]
for name in results:
    L += [f"## {name}", "", "| variant | trades | removed | PF | dPF | win % | dWR | net $ | dNet | maxDD $ | dDD | exp $ | dExp | exp R DEV | VAL | OOS | class |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    b = results[name]["BASE"]["metrics"]
    L.append(f"| BASE | {b['ALL']['trades']} | | {b['ALL'].get('profit_factor')} | | {b['ALL'].get('win_rate')} | | {b['ALL']['net_profit']} | | {b['ALL']['max_dd_usd']} | | {b['ALL'].get('expectancy')} | | {b['DEV'].get('expectancy_r')} | {b['VAL'].get('expectancy_r')} | {b['OOS'].get('expectancy_r')} | base |")
    for vname, r in results[name].items():
        if vname in ("BASE", "COMBOS"):
            continue
        a = r["metrics"]["ALL"]; m = r["metrics"]
        L.append(f"| {vname} | {a['trades']} | {b['ALL']['trades'] - a['trades']} | {a.get('profit_factor')} | {None if a.get('profit_factor') is None or b['ALL'].get('profit_factor') is None else round(a['profit_factor'] - b['ALL']['profit_factor'], 3)} | {a.get('win_rate')} | "
                 f"{None if a.get('win_rate') is None or b['ALL'].get('win_rate') is None else round(a['win_rate'] - b['ALL']['win_rate'], 1)} | {a['net_profit']} | {round(a['net_profit'] - b['ALL']['net_profit'], 2)} | {a['max_dd_usd']} | {round(a['max_dd_usd'] - b['ALL']['max_dd_usd'], 2)} | "
                 f"{a.get('expectancy')} | {None if a.get('expectancy') is None or b['ALL'].get('expectancy') is None else round(a['expectancy'] - b['ALL']['expectancy'], 3)} | {m['DEV'].get('expectancy_r')} | {m['VAL'].get('expectancy_r')} | {m['OOS'].get('expectancy_r')} | {r['class']} |")
    L.append("")
    L += ["### Phase 2 combinations", "", "| Test | Filters | Trades | PF | Win Rate | Net Profit | Max DD | Expectancy | exp R DEV/VAL/OOS | OOS net | OOS PF | class |", "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|"]
    for c in results[name]["COMBOS"]:
        L.append(f"| {c['test']} | {c['filters']} | {c['trades']} | {c['profit_factor']} | {c['win_rate']} | {c['net_profit']} | {c['max_dd_usd']} | {c['expectancy']} | {c['DEV_expR']}/{c['VAL_expR']}/{c['OOS_expR']} | {c['OOS_net']} | {c['OOS_pf']} | {c['class']} |")
    if not results[name]["COMBOS"]:
        L.append("| - | no individually helpful filter on this timeframe, nothing to combine | | | | | | | | | | |")
    L.append("")
with open(os.path.join(OUT, "FILTERS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done", round(time.time() - t0), "s")
