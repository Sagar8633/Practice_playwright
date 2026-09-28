"""Assemble study3/H4_REPORT.md from results/study3.json (narrative in narrative3.json)."""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
R = json.load(open(os.path.join(HERE, "results", "study3.json"), encoding="utf-8"))
N = json.load(open(os.path.join(HERE, "narrative3.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "narrative3.json")) else {}


def f(x, d=2):
    if x is None: return "-"
    if isinstance(x, float):
        if np.isnan(x) or np.isinf(x): return "-"
        return f"{x:.{d}f}"
    return str(x)


def tbl(rows, hdr):
    o = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] + ["---:"] * (len(hdr) - 1)) + "|"]
    for r in rows: o.append("| " + " | ".join(f(x) for x in r) + " |")
    return o + [""]


def splits(rec):
    return [f"{rec['DEV'][0]} / {f(rec['DEV'][1], 3)}", f"{rec['VAL'][0]} / {f(rec['VAL'][1], 3)}", f"{rec['OOS'][0]} / {f(rec['OOS'][1], 3)}"]


atr = lambda v: f"{v/100:.2f} ATR"
L = ["# Study 3: H4 only, from the E19 exit stack to a final configuration", "", "Same engine, data (Sep 2020 - Sep 2026, XM costs, 0.01 lot) and splits as studies 1 and 2 (DEV Sep 2020 - Aug 2023, VAL Sep 2023 - Dec 2024, OOS Jan 2025 - Sep 2026). "
     "ATR units: the break-even trigger and the trailing start / distance / step are multiples of ATR(22) measured on the last completed bar when the trade opened.", "",
     "## 1. Summary", "", N.get("summary", "_(pending)_"), "",
     "## 2. Stage 0: what E19 actually was", "", N.get("stage0", ""), ""]
L += tbl([[k, v["trades"], v["net"], v["pf"], v["dd"], v["win"], f(v["expR"], 3), *splits(v), v["giveback"], v["p2l"]] for k, v in R["stage0"].items()], ["configuration", "trades", "net $", "PF", "maxDD $", "win %", "exp R", "DEV net / R", "VAL net / R", "OOS net / R", "giveback avg $", "P->L >$2"])
s1 = R["stage1"]
L += ["## 3. Stage 1: the exit parameter grid", "", N.get("stage1", ""), "", f"{s1['grid_size']} settings (break-even 0/0.5/1/1.5/2 ATR x trailing start 1-6 ATR x distance 0.5-2 ATR, step 0.1 ATR): {s1['pos3']} positive in all three splits; share positive DEV {s1['share_pos_dev']}, VAL {s1['share_pos_val']}, OOS {s1['share_pos_oos']}. Chosen (highest weakest-split expectancy among settings positive in all splits with >= 40 DEV trades): {R['stage1']['chosen']}.", "",
      "Top settings positive in all three splits (nb = one-step neighbours also positive in all splits):", ""]
L += tbl([[f"BE {atr(r['be']) if r['be'] else 'off'}", atr(r["start"]), atr(r["dist"]), r["trades"], r["net"], r["pf"], r["dd"], *splits(r), f(r["min_expR"], 3), f"{int(r['nb_pos'])}/{int(r['nb_tot'])}"] for r in s1["top"]], ["break-even", "trail start", "trail distance", "trades", "net $", "PF", "maxDD $", "DEV net / R", "VAL net / R", "OOS net / R", "weakest exp R", "nb"])
L += ["Highest net over the six years, regardless of split consistency:", ""]
L += tbl([[f"BE {atr(r['be']) if r['be'] else 'off'}", atr(r["start"]), atr(r["dist"]), r["trades"], r["net"], r["pf"], r["dd"], *splits(r), "yes" if r["pos3"] else "no"] for r in s1["best_net"]], ["break-even", "trail start", "trail distance", "trades", "net $", "PF", "maxDD $", "DEV net / R", "VAL net / R", "OOS net / R", "positive in all splits"])
ax = s1["axes"]
for be in ax["BE"]:
    L += [f"Net $ heat table, break-even {atr(be) if be else 'off'} (rows = trailing start, columns = trailing distance):", ""]
    L += tbl([[atr(st)] + [f(v, 0) for v in row] for st, row in zip(ax["START"], s1["heat"][str(be)])], ["start \\ distance"] + [atr(d) for d in ax["DIST"]])
L += ["## 4. Stage 2: entry filters on the chosen exit", "", N.get("stage2", ""), ""]
b = R["stage2"]["base"]
L += [f"Base (chosen exit, no filter): {b['trades']} trades, net {b['net']}, PF {b['pf']}, maxDD {b['dd']}, exp R DEV/VAL/OOS {f(b['DEV'][1], 3)} / {f(b['VAL'][1], 3)} / {f(b['OOS'][1], 3)}.", ""]
L += tbl([[k, v["trades"], v["net"], v["pf"], v["dd"], f(v["expR"], 3), f(v["dev"], 3), f(v["val"], 3), f(v["oos"], 3), v["dev_net"], v["val_net"], v["oos_net"], v["cls"]] for k, v in R["stage2"]["rows"].items()], ["filter", "trades", "net $", "PF", "maxDD $", "exp R", "DEV R", "VAL R", "OOS R", "DEV net", "VAL net", "OOS net", "class"])
L += ["## 5. Stage 3: combinations of the helpful filters", "", N.get("stage3", ""), ""]
L += tbl([[r["filters"], r["trades"], r["net"], r["pf"], r["dd"], *splits(r), r["cls"]] for r in R["stage3"]], ["stack", "trades", "net $", "PF", "maxDD $", "DEV net / R", "VAL net / R", "OOS net / R", "class"]) if R["stage3"] else ["No individually helpful filter with an EA input, nothing to combine.", ""]
L += ["## 6. Stage 4: stops on the chosen exit", "", N.get("stage4", ""), ""]
L += tbl([[k, v["trades"], f(v["median_risk"]), v["net"], v["pf"], v["dd"], *splits(v), v["cls"]] for k, v in R["stage4"].items()], ["stop", "trades", "median risk $", "net $", "PF", "maxDD $", "DEV net / R", "VAL net / R", "OOS net / R", "class"])
L += ["## 7. Stage 5: MA periods on the chosen exit (sensitivity)", "", N.get("stage5", ""), ""]
L += tbl([[k, v["trades"], v["net"], v["pf"], v["dd"], *splits(v), "yes" if v["pos3"] else "no"] for k, v in R["stage5"].items()], ["fast/trend", "trades", "net $", "PF", "maxDD $", "DEV net / R", "VAL net / R", "OOS net / R", "positive in all splits"])
L += ["## 8. Stage 6: final configuration and robustness", "", N.get("stage6", ""), "", f"Final parameters (engine units): `{json.dumps(R['final']['params'])}`; filters added from stage 3: {R['final']['from_combo']}.", ""]
rows = []
for k, d in R["stage6"].items():
    a = d["all"]
    rows.append([k, a["trades"], a["net"], a["pf"], a["dd"], a["win"], f(a["expR"], 3), *splits(a), d["cost"]["A_low"], d["cost"]["C_stress"], d["worst_path"], f(d["median_risk"]), f"{d['mc_200']['bootstrap']['p_ruin']:.3f}", f"{d['mc_100x']['bootstrap']['p_ruin']:.3f}"])
L += tbl(rows, ["configuration", "trades", "net $", "PF", "maxDD $", "win %", "exp R", "DEV net / R", "VAL net / R", "OOS net / R", "low cost $", "stress $", "worst ordering $", "median stop $", "MC p(ruin) $200", "MC p(ruin) 100x stop"])
L += ["Walk-forward folds (train / validate / test net $):", ""]
L += tbl([[k] + [f"{fo['train'][0]} / {fo['val'][0]} / {fo['test'][0]}" for fo in d["folds"]] for k, d in R["stage6"].items()], ["configuration", "fold 1 (test 2023-24)", "fold 2 (test 2024-25)", "fold 3 (test 2025-26)"])
L += ["By year:", ""]
years = sorted({y for d in R["stage6"].values() for y in d["by_year"]})
L += tbl([[k] + [d["by_year"].get(y, d["by_year"].get(str(y), "-")) for y in years] for k, d in R["stage6"].items()], ["configuration"] + [str(y) for y in years])
L += ["2003-2026 on the hourly intrabar path (H4 bars from H1 before Sep 2020; coarser than the M1 path, so treat as a regime check, not a precise number):", ""]
L += tbl([[k, h["trades"], h["net"], h["pf"], h["dd"], f(h["expR"], 3), h["pos_years"], h["worst_year"], *[f"{h['windows'][w][0]} / {f(h['windows'][w][1], 3)} / {h['windows'][w][2]}" for w in ("2003-2012", "2012-2020", "2020-2026")], f"{h['mc_200']['bootstrap']['p_ruin']:.3f}"] for k, d in R["stage6"].items() for h in [d["h1path_2003_2026"]]], ["configuration", "trades", "net $", "PF", "maxDD $", "exp R", "positive years", "worst year $", "2003-2012 net / R / trades", "2012-2020", "2020-2026", "MC p(ruin) $200"])
L += ["By session and side (six years, net $ / trades):", ""]
L += tbl([[k, *[f"{d['by_session'].get(s_, {}).get('net', '-')} / {d['by_session'].get(s_, {}).get('trades', '-')}" for s_ in ("Asia", "London", "London/NY", "NewYork", "Sydney")], f"{d['by_side'].get('1', d['by_side'].get(1, {})).get('net', '-')} / {d['by_side'].get('-1', d['by_side'].get(-1, {})).get('net', '-')}", f"{d['window_2023_26'][0]} / PF {f(d['window_2023_26'][3])}"] for k, d in R["stage6"].items()], ["configuration", "Asia", "London", "London/NY", "New York", "Sydney", "long / short net $", "2023-2026 net"])
L += ["## 9. Sensitivity of the final configuration", "", N.get("sensitivity", ""), ""]
for pn, rows in R["sensitivity"].items():
    L.append(f"- **{pn}**: " + ", ".join(f"{r['value']}: net {r['net']} (PF {f(r['pf'])}, exp {f(r['expR'], 3)}, DEV/VAL/OOS {f(r['DEV'], 3)}/{f(r['VAL'], 3)}/{f(r['OOS'], 3)}{', all +' if r['pos3'] else ''})" for r in rows))
L += ["", "## 10. The EA changes", "", N.get("ea", ""), ""]
with open(os.path.join(HERE, "H4_REPORT.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L))
print("H4_REPORT.md written", len(L), "lines")
