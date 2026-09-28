"""Builds edge_discovery_report.html from results/edge/edge_lab.json and narrative_edge.json."""
import html, json, math, os
import pandas as pd

L = json.load(open("results/edge/edge_lab.json"))
N = json.load(open("results/edge/narrative_edge.json")) if os.path.exists("results/edge/narrative_edge.json") else {}

def esc(x): return html.escape(str(x))
def num(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def pct(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    return f"{x*100:.{d}f}%"
def money(x):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    return ("-$" if x < 0 else "$") + f"{abs(x):,.0f}"
def cls(x): return "" if x is None or (isinstance(x, float) and math.isnan(x)) else ("neg" if x < 0 else "pos")
def R(x): return (num(x, 3), cls(x))
def PF(x): return (num(x, 2), "" if x is None else ("pos" if x > 1 else "neg"))
def para(k):
    v = N.get(k, "")
    if isinstance(v, list): return "".join(f"<p>{x}</p>" for x in v)
    return f"<p>{v}</p>" if v else ""
def bullets(k):
    v = N.get(k, [])
    return "<ul>" + "".join(f"<li>{x}</li>" for x in v) + "</ul>" if v else ""
def section(title, body, sub=None, id_=None):
    return f"<section id='{id_ or ''}'><h2>{esc(title)}</h2>" + (f"<p class='sub'>{sub}</p>" if sub else "") + body + "</section>"
def table(cols, rows, caption=None):
    out = ["<div class='scroll'><table>"]
    if caption: out.append(f"<caption>{esc(caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th class='{'l' if i == 0 else ''}'>{esc(c)}</th>" for i, c in enumerate(cols)) + "</tr></thead><tbody>")
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            text, klass = (esc(v[0]), v[1]) if isinstance(v, tuple) else (esc(v), "")
            if i == 0: klass = ("l " + klass).strip()
            cells.append(f"<td class='{klass}'>{text}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)

# ---- phase 5 buckets
BA = L["buckets_all"]; tot = sum(BA.values())
bk_rows = [[k, {"A": "reached +2R before -1R", "B": "reached +1R, not +2R", "C": "reached +0.5R, then stopped", "D": "never reached +0.5R"}[k], f"{BA.get(k, 0):,}", f"{BA.get(k, 0)/tot*100:.1f}%"] + [f"{L['buckets'][p].get(k, 0):,} ({L['buckets'][p].get(k, 0)/max(1, sum(L['buckets'][p].values()))*100:.0f}%)" for p in ("DEV", "VAL", "OOS")] +
           [R(L["bucket_r"][k]["r12_gross"]), R(L["bucket_r"][k]["r12_net"]), num(L["bucket_r"][k]["median_stop_atr"], 2), L["bucket_r"][k]["median_min_to_1R"] or "", L["bucket_r"][k]["median_min_to_m1R"] or ""] for k in ("A", "B", "C", "D") if k in BA]
bk_tbl = table(["Bucket", "Definition", "Signals", "Share", "DEV", "VAL", "OOS", "Gross R (1R/2R)", "Net R", "Median stop / ATR", "Median min to +1R", "Median min to -1R"], bk_rows,
               f"{L['n']:,} raw M3 flips; R = the strategy's own stop (pivot, or purple line), entry at the next M1 open, spread applied, 10-hour path.")
ov_rows = [[p, f"{v['n']:,}", pct(v["hit_2R"]), R(v["r12_gross"]), R(v["r12_net"]), R(v["r11_net"])] for p, v in L["overall"].items()]
ov_tbl = table(["Period", "Signals", "Reached +2R before -1R", "Gross R (1R/2R)", "Net R (1R/2R)", "Net R (1R/1R)"], ov_rows)

# ---- phase 9 timing
tm_rows = [[k, f"{v['n']:,}"] + [f"{d.get('0.25', '')} / {d.get('0.5', '')} / {d.get('0.75', '')}" if d else "" for d in (v["min_to_05R"], v["min_to_1R"], v["min_to_2R"], v["min_to_m1R"])] for k, v in L["timing"].items()]
tm_tbl = table(["Bucket", "n", "Minutes to +0.5R (p25 / p50 / p75)", "to +1R", "to +2R", "to -1R"], tm_rows, "Time from entry to each level, one-minute resolution.")
hf = L["half_first"]
hf_txt = f"<p>Which came first, +0.5R or -0.5R? Winners (A and B): +0.5R first in {pct(hf['winners_half_first'], 0)} of cases. Immediate losers (D): {pct(hf['losers_half_first'], 0)}. All signals: +0.5R first {pct(hf['all_half_first'], 0)}, -0.5R first {pct(hf['all_neg_half_first'], 0)}; by period " + ", ".join(f"{p}: {pct(v['plus'], 0)} vs {pct(v['minus'], 0)}" for p, v in hf["by_period"].items()) + ".</p>"

# ---- separation
SEP = pd.DataFrame(L["separation"])
sep_rows = [[("NEW " if r.new else "") + r.feature, r.description if r.new else "", r.best, f"{int(r.best_n):,}", pct(r.best_AB, 0), pct(r.best_D, 0), R(r.best_exp), r.worst, pct(r.worst_AB, 0), pct(r.worst_D, 0), R(r.worst_exp), f"{int(r.order_holds)} / 3", f"{int(r.best_positive)} / 3", R(r.best_DEV), R(r.best_VAL), R(r.best_OOS)] for r in SEP.itertuples()]
sep_tbl = table(["Feature", "New in phase 6", "Best bucket", "n", "A+B share", "D share", "Net R", "Worst bucket", "A+B", "D", "Net R", "Order holds (periods)", "Best positive (periods)", "Best DEV", "Best VAL", "Best OOS"], sep_rows,
                "Per quintile (or category): share of A/B outcomes, share of D outcomes, net expectancy of the 1R/2R shape. A feature separates winners from immediate losers only if the order holds in DEV, VAL and OOS.")
BK = pd.DataFrame(L["feature_buckets"])
def bucket_tbl(f):
    d = BK[BK.feature == f]
    return table([f, "n", "A+B share", "D share", "Net R", "DEV", "VAL", "OOS"], [[r.bucket, f"{int(r.n):,}", pct(r.share_AB, 0), pct(r.share_D, 0), R(r.exp12_net), R(r.exp_DEV), R(r.exp_VAL), R(r.exp_OOS)] for r in d.itertuples()])
detail = "".join(f"<h3>{esc(f)}</h3>" + bucket_tbl(f) for f in list(SEP.head(6).feature) + [f for f in ("retest_of_broken_level", "m3_structure", "prior_move_against_atr15", "risk_atr", "broke_prev_day_level") if f not in list(SEP.head(6).feature)] if (BK.feature == f).any())

# ---- ML
ML = L.get("ml", {})
ml_html = ""
if "auc_DEV" in ML:
    ml_html += table(["Model", "AUC DEV (train)", "AUC VAL", "AUC OOS"], [["Gradient boosting, depth 3, 300 trees", num(ML["auc_DEV"]), num(ML["auc_VAL"]), num(ML["auc_OOS"])], ["Logistic regression (sanity check)", num(ML["logit_auc"]["DEV"]), num(ML["logit_auc"]["VAL"]), num(ML["logit_auc"]["OOS"])]],
                     "Target: A or B versus D (C excluded), all 52 entry-time features. 0.5 = no information. Training on DEV only.")
    dec = ML["deciles"]
    ml_html += table(["Predicted-probability decile"] + [f"{p} n / net R" for p in ("DEV", "VAL", "OOS")], [[f"decile {i+1}"] + [f"{dec[p][i]['n']:,} / " + num(dec[p][i]['exp12_net']) if i < len(dec[p]) else "" for p in ("DEV", "VAL", "OOS")] for i in range(10)],
                     "Net expectancy (1R/2R) by decile of the model's probability. Decile 10 = the signals the model likes most.")
    ml_html += table(["Top-decile rule (threshold fixed on DEV)", "n", "Net R", "Gross R"], [[p, f"{ML[f'top10_{p}']['n']:,}", R(ML[f"top10_{p}"]["exp12_net"]), R(ML[f"top10_{p}"]["exp12_gross"])] for p in ("DEV", "VAL", "OOS")])
    ml_html += table(["Feature (permutation importance on VAL)", "AUC drop when shuffled"], [[f, num(v, 4)] for f, v in ML["importance_VAL"]])
else:
    ml_html = f"<p>Multivariate model not run: {esc(ML.get('error', 'scikit-learn unavailable'))}.</p>"

# ---- phase 7 / structure splits
def split_tbl(key, label):
    rows = [[r["group"], f"{r['n']:,}", pct(r["win_2R"]), pct(r["share_AB"], 0), pct(r["share_D"], 0), R(r["avg_r_gross"]), R(r["avg_r_net"]), PF(r["pf"]), f"{r['n_DEV']:,}", PF(r["pf_DEV"]), f"{r['n_VAL']:,}", PF(r["pf_VAL"]), f"{r['n_OOS']:,}", PF(r["pf_OOS"]), r["median_min_to_1R"] or "", r["median_min_to_m1R"] or "", r["years_positive"]] for r in L[key]]
    return table([label, "n", "Reached +2R", "A+B", "D", "Gross R", "Net R", "PF", "DEV n", "PF", "VAL n", "PF", "OOS n", "PF", "Min to +1R", "Min to -1R", "Years positive (of 6)"], rows)
p7 = ("<h3>Model A trend continuation versus Model B reversal</h3>" + split_tbl("trend_vs_reversal", "Model") + para("p7") +
      "<h3>M3 pivot structure</h3>" + split_tbl("structure_m3", "Structure") + "<h3>The break-and-retest hypothesis</h3>" + split_tbl("hyp_break_retest", "M15 level broken, retested within 1 ATR, HTF aligned") +
      split_tbl("retest", "Retest of a broken M15 level") + split_tbl("m15_level_broken", "M15 level broken in the last 8 bars") + split_tbl("broke_prev_day", "Closed beyond the previous day's high/low") + para("p6"))

# ---- phase 8 entries
en_rows = [[t["entry"], pct(t["taken"], 0)] + [x for p in ("ALL", "DEV", "VAL", "OOS") for x in (f"{t[f'n_{p}']:,}", pct(t[f"win2R_{p}"]), R(t[f"exp12_{p}"]), PF(t[f"pf_{p}"]))] for t in L["entries"]]
en_tbl = table(["Entry mechanism", "Signals taken"] + [f"{p} {k}" for p in ("ALL", "DEV", "VAL", "OOS") for k in ("n", "reached 2R", "net R", "PF")], en_rows,
               "Stop = the original stop distance from the new entry, target 2R, spread applied. Retest and pullback entries are limit-style fills at the level.")

# ---- acceptance
AC = L["acceptance"]
ac_rows = []
for a in AC:
    ac_rows.append([a["candidate"], a["kind"], f"{a['signals']:,}"] + [x for p in ("DEV", "VAL", "OOS", "ALL") for x in (f"{a[f'{p}_n']:,}", money(a[f"{p}_net"]), PF(a[f"{p}_pf"]))] +
                   [("PASS", "pos") if a.get("gate_pf_all_periods") else ("fail", "neg") if a["kind"] == "candidate" else "", a.get("spread_x1.25_pf_OOS", ""), a.get("spread_x1.5_pf_OOS", ""), a.get("slip2_pf_OOS", ""), f"{a.get('LPV1_DEV_pf', '')} / {a.get('LPV1_VAL_pf', '')} / {a.get('LPV1_OOS_pf', '')}" if a["kind"] == "candidate" else ""])
ac_tbl = table(["Candidate", "Kind", "Signals"] + [f"{p} {k}" for p in ("DEV", "VAL", "OOS", "ALL") for k in ("trades", "net", "PF")] + ["Gate: PF > 1 in all three", "PF OOS at 1.25x spread", "at 1.5x spread", "with 2 pts slippage", "PF under Loss Prevention v1 (DEV / VAL / OOS)"], ac_rows,
               "Every candidate run through the real engine with the baseline management, fixed 0.02 lot, against the two controls. Robustness columns are only computed for candidates that pass the profit-factor gate.")

page = f"""<title>TWK Edge Discovery</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1140px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} td.l,th.l{{text-align:left;white-space:normal;min-width:150px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} .decision{{font-size:22px;font-weight:700;margin:8px 0}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, TWK M3 flips, phases 5 to 9</p>
<h1>TWK Edge Discovery</h1>
<p class="lede">What separates the flips that reached +2R from the ones that never reached +0.5R, at the moment of entry. Structure, trend versus reversal, entry mechanisms and timing, each held to the same rule: development, validation and out of sample must agree. Generated {esc(L['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{i}. {t}</a>" for i, t in enumerate(["Verdict", "Phase 5 outcomes", "What separates A/B from D", "Any combination? (model)", "Phase 6-7 structure, trend vs reversal", "Phase 8 entries", "Phase 9 timing", "Acceptance gates vs controls", "Phases 10-12", "Method"], 1))}</div>
<div class="verdict"><p class="k">Result of phases 5 to 9</p><p class="decision">{esc(N.get('decision', ''))}</p>{para('decision_text')}</div>
{section('1. Verdict by phase', bullets('by_phase'), None, 's1')}
{section('2. Phase 5: outcome buckets with the real stop', bk_tbl + ov_tbl + para('p5'), None, 's2')}
{section('3. What separates A/B from D at entry', sep_tbl + detail + para('sep'), 'Univariate, every feature old and new, ranked by stability.', 's3')}
{section('4. Can any combination separate them?', ml_html + para('ml'), 'A gradient-boosted classifier on all entry-time features, trained on development only.', 's4')}
{section('5. Phases 6 and 7: structure, trend continuation versus reversal', p7, None, 's5')}
{section('6. Phase 8: entry mechanisms', en_tbl + para('p8'), None, 's6')}
{section('7. Phase 9: MFE / MAE timing', tm_tbl + hf_txt + para('p9'), None, 's7')}
{section('8. Acceptance gates against the controls', ac_tbl + para('acceptance'), 'PF above 1 in development, validation and out of sample; then spread 1.25x and 1.5x, slippage, and the Loss Prevention v1 management.', 's8')}
{section('9. Phases 10 to 12', bullets('next'), 'What needs your data, and what the new entry model would be built from if it existed.', 's9')}
{section('10. Method and limits', bullets('method'), None, 's10')}
</div>
"""
open("edge_discovery_report.html", "w", encoding="utf-8").write(page)
print("edge_discovery_report.html written", len(page))
