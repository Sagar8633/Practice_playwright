"""Builds signal_edge_report.html from results/signal/signal_lab.json and results/signal/narrative_signal.json."""
import html, json, math, os
import pandas as pd

L = json.load(open("results/signal/signal_lab.json"))
N = json.load(open("results/signal/narrative_signal.json")) if os.path.exists("results/signal/narrative_signal.json") else {}

def esc(x): return html.escape(str(x))
def num(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def pct(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    return f"{x*100:.{d}f}%"
def cls(x): return "" if x is None else ("neg" if x < 0 else "pos")
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
def R(x): return (num(x, 3), cls(x))

# ---- directional + grid
dir_rows = [[f"{g['stop']} ATR", pct(g["gross_hit"]), R(g["gross_exp_r"]), num(g["gross_pf"], 2), pct(g["net_hit"]), R(g["net_exp_r"]), num(g["net_pf"], 2), pct(g["be_hit_rate"]),
             R(g["net_exp_DEV"]), R(g["net_exp_VAL"]), R(g["net_exp_OOS"])] for g in L["directional"]]
dir_tbl = table(["X (stop = target)", "Gross hit", "Gross exp (R)", "Gross PF", "Net hit", "Net exp (R)", "Net PF", "Break-even hit", "Net exp DEV", "Net exp VAL", "Net exp OOS"], dir_rows,
                f"Did price reach +X before -X from the entry? {L['n_signals']:,} raw M3 flips, entry at the next M1 open (ask for buys), exits at bid/ask, 10-hour horizon, worst case inside a bar. R = X. A coin flip nets 0 gross and about -spread net.")
grid = pd.DataFrame(L["grid"])
piv = grid.pivot(index="stop", columns="target", values="net_exp_r")
grid_rows = [[f"stop {s} ATR"] + [R(piv.loc[s, t]) for t in piv.columns] for s in piv.index]
grid_tbl = table(["Net expectancy (R)"] + [f"target {t} ATR" for t in piv.columns], grid_rows, "Hindsight grid: every stop/target pair after spread. R = the stop distance.")
pivh = grid.pivot(index="stop", columns="target", values="net_hit")
grid_h = table(["Net hit rate"] + [f"target {t} ATR" for t in pivh.columns], [[f"stop {s} ATR"] + [pct(pivh.loc[s, t]) for t in pivh.columns] for s in pivh.index])
pivd = grid.pivot(index="stop", columns="target", values="net_exp_DEV"); pivv = grid.pivot(index="stop", columns="target", values="net_exp_VAL"); pivo = grid.pivot(index="stop", columns="target", values="net_exp_OOS")
grid_p = table(["Net exp (R) by period"] + [f"target {t}" for t in pivd.columns], [[f"stop {s} ATR, {per}"] + [R(pp.loc[s, t]) for t in pp.columns] for s in pivd.index for per, pp in (("DEV", pivd), ("VAL", pivv), ("OOS", pivo))])
byy = pd.DataFrame(L["by_year"])
byy_rows = [[f"stop {r.stop} / target {r.target}", r.year, f"{int(r.net_n):,}", pct(r.net_hit), R(r.gross_exp_r), R(r.net_exp_r), num(r.net_pf, 2)] for r in byy.itertuples()]
byy_tbl = table(["Shape", "Year", "Signals", "Net hit", "Gross exp (R)", "Net exp (R)", "Net PF"], byy_rows, "The same test year by year.")
xtf_rows = [[r["tf"], f"{r['stop']}/{r['target']}", f"{r['n']:,}", pct(r["gross_hit"]), R(r["gross_exp_r"]), pct(r["net_hit"]), R(r["net_exp_r"]), R(r["net_exp_DEV"]), R(r["net_exp_VAL"]), R(r["net_exp_OOS"])] for r in L["cross_tf"]]
xtf_tbl = table(["Signal TF", "Stop/target (ATR)", "Signals", "Gross hit", "Gross exp", "Net hit", "Net exp", "DEV", "VAL", "OOS"], xtf_rows, "The same directional test on the raw flips of the other timeframes.")

# ---- excursions / classes / min move
hz_rows = [[f"{h['horizon_m3_bars']} bars", num(h["mfe_atr_median"], 2), num(h["mfe_atr_p75"], 2), num(h["mae_atr_median"], 2), num(h["mae_atr_p75"], 2), pct(h["share_mfe_gt_mae"]), R(h["mfe_minus_mae_mean"])] for h in L["horizons"]]
hz_tbl = table(["Horizon (M3 bars)", "MFE median (ATR)", "MFE p75", "MAE median (ATR)", "MAE p75", "Signals with MFE > MAE", "Mean MFE - MAE (ATR)"], hz_rows, "Gross excursions from the entry, in ATR of the signal timeframe. A signal with direction shows MFE above MAE.")
sp = L["spread_in_atr"]
cls_rows = [[f"{c['stop_atr']} ATR"] + [f"{c[k]:,} ({c[k+'_pct']}%)" for k in ("strong_winner", "moderate_winner", "neutral", "moderate_loser", "strong_loser")] for c in L["classes"]]
cls_tbl = table(["Stop used", "Strong winner (+2 before stop)", "Moderate winner (+1 before stop)", "Neutral", "Moderate loser (stop before +0.5)", "Strong loser (stop before +0.25)"], cls_rows, "Outcome classes from the forward path after spread, for three stop definitions.")
mm_rows = [[f"{m['stop_atr']} / {m['target_atr']}", pct(m["gross_hit"]), pct(m["net_hit"]), pct(m["breakeven_hit_needed"]), (pct(m["margin"]), cls(m["margin"])), R(m["net_exp_r"]), pct(m["req_hit_for_plus025R"]), pct(m["req_hit_for_plus05R"])] for m in L["min_move"]]
mm_tbl = table(["Stop / target (ATR)", "Gross hit", "Net hit", "Hit needed to break even", "Margin", "Net exp (R)", "Hit needed for +0.25R", "Hit needed for +0.5R"], mm_rows,
               f"Break-even hit rate = (stop + spread) / (stop + target), with the median spread of {sp['median']} ATR (p25 {sp['p25']}, p75 {sp['p75']}; by year " + ", ".join(f"{y}: {v}" for y, v in sp["by_year"].items()) + ").")
sp20 = L["mfe20_in_spreads"]
sp20_txt = "<p>Best excursion within 20 bars measured in spreads: " + ", ".join(f"{k.replace('share_ge_', 'at least ').replace('x', ' x')} spread: {pct(v, 0)}" for k, v in sp20.items()) + " of signals.</p>"

# ---- features
FR = pd.DataFrame(L["feature_ranking"])
FR = FR[FR.feature != "class_1atr"]            # the outcome label is diagnostic, not a feature
L["good_components"] = [c for c in L["good_components"] if c["feature"] != "class_1atr"]
L["good_candidates"] = [c for c in L["good_candidates"] if not c["rule"].startswith("class_1atr")]
fr_rows = [[r.feature, r.description, r.best_bucket, f"{int(r.best_n):,}", R(r.best_exp11), r.worst_bucket, R(r.worst_exp11), R(r.separation), f"{int(r.order_holds_in_periods)} / 3", f"{int(r.best_positive_in_periods)} / 3", R(r.best_DEV), R(r.best_VAL), R(r.best_OOS)] for r in FR.itertuples()]
fr_tbl = table(["Feature", "What it is", "Best bucket", "n", "Best exp (R)", "Worst bucket", "Worst exp (R)", "Separation", "Order holds (periods)", "Best bucket positive (periods)", "Best DEV", "Best VAL", "Best OOS"], fr_rows,
               "Net expectancy of the 1 ATR / 1 ATR test per quintile (or category). Ranked by how many periods keep the same best-versus-worst order, then by separation. A feature is evidence only if the order holds in all three periods.")
BK = pd.DataFrame(L["feature_buckets"])
def bucket_tbl(f):
    d = BK[BK.feature == f]
    rows = [[r.bucket, f"{int(r.n):,}", pct(r.hit), R(r.exp11), R(r.exp12), R(r.exp11_DEV), R(r.exp11_VAL), R(r.exp11_OOS), f"{int(r.years_positive)} / {int(r.years)}"] for r in d.itertuples()]
    return table([f, "n", "Hit 1x1", "Exp 1x1 (R)", "Exp 1x2 (R)", "DEV", "VAL", "OOS", "Years positive"], rows)
top_feats = [f for f in FR.head(8).feature] + [f for f in ("ea_pass", "purple_dist", "opp_ago", "htf15_aligned", "session", "prev_outcome") if f not in FR.head(8).feature.tolist()]
feat_detail = "".join(f"<h3>{esc(f)}: {esc(FR[FR.feature == f].description.iloc[0]) if (FR.feature == f).any() else ''}</h3>" + bucket_tbl(f) for f in top_feats if (BK.feature == f).any())

def split_tbl(key, label):
    rows = [[r["group"], f"{r['n']:,}", pct(r["hit"]), R(r["exp11_gross"]), R(r["exp11"]), R(r["exp12"]), f"{r['n_DEV']:,}", R(r["exp11_DEV"]), f"{r['n_VAL']:,}", R(r["exp11_VAL"]), f"{r['n_OOS']:,}", R(r["exp11_OOS"]), r["years_positive"]] for r in L[key]]
    return table([label, "n", "Hit 1x1", "Gross exp 1x1", "Net exp 1x1", "Net exp 1x2", "DEV n", "DEV exp", "VAL n", "VAL exp", "OOS n", "OOS exp", "Years positive (of 6)"], rows)
splits = ("<h3>Continuation versus reversal (M15 and H1 Supertrend)</h3>" + split_tbl("cont_rev", "Class") + para("ev_contrev") +
          "<h3>Price structure</h3>" + split_tbl("structure", "Structure") + "<h3>Entry location</h3>" + split_tbl("location", "Location") + para("ev_location") +
          "<h3>Trend and volatility regime</h3>" + split_tbl("regime", "Regime (ADX / ATR ratio)") + split_tbl("vol_regime", "Volatility state") + para("ev_regime") +
          "<h3>Shipped EA filters, session, previous signal</h3>" + split_tbl("ea_pass", "Passes the EA filters") + split_tbl("session", "Session") + split_tbl("prev_outcome", "Previous raw signal"))

tm_rows = [[t["entry"], pct(t["taken"], 0), f"{t['n_ALL']:,}", pct(t["hit11_ALL"]), R(t["exp11_ALL"]), R(t["exp12_ALL"]), R(t["exp11_DEV"]), R(t["exp11_VAL"]), R(t["exp11_OOS"])] for t in L["timing"]]
tm_tbl = table(["Entry model", "Signals taken", "n", "Hit 1x1", "Net exp 1x1 (R)", "Net exp 1x2 (R)", "DEV 1x1", "VAL 1x1", "OOS 1x1"], tm_rows, "Same signals, different entry timing; stops and targets measured from the actual entry, after spread.")
pp_rows = [[p["path"], f"{p['n']:,}", f"{p['pct']}%", R(p["exp11"])] for p in L["pullback_paths"]]
pp_tbl = table(["What price did after the immediate entry", "n", "Share", "Net exp 1x1 (R)"], pp_rows)

comp = L["good_components"]
comp_rows = [[c["feature"], c["bucket"], f"{c['n']:,}", R(c["exp11"]), R(c["exp11_DEV"]), R(c["exp11_VAL"]), R(c["exp11_OOS"]), f"{c['years_positive']} / {c['years']}"] for c in comp]
comp_tbl = table(["Feature", "Bucket", "n", "Net exp 1x1", "DEV", "VAL", "OOS", "Years positive"], comp_rows, "Buckets whose net 1x1 expectancy is positive in DEV and in VAL with at least 200 / 100 signals. These are the only admissible GOOD_SIGNAL components.") if comp else "<p><strong>No feature bucket has positive net expectancy in both selection periods.</strong> There is nothing admissible to build GOOD_SIGNAL from.</p>"
gc_rows = [[c["rule"], f"{c['n']:,}", R(c["exp11_gross"]), R(c["exp11"]), f"{c['n_DEV']:,}", R(c["exp11_DEV"]), f"{c['n_VAL']:,}", R(c["exp11_VAL"]), f"{c['n_OOS']:,}", R(c["exp11_OOS"]), R(c["exp12_OOS"]), c["years_positive"]] for c in L["good_candidates"] + L["predefined"]]
gc_tbl = table(["Definition", "n", "Gross exp 1x1", "Net exp 1x1", "DEV n", "DEV", "VAL n", "VAL", "OOS n", "OOS 1x1", "OOS 1x2", "Years positive (of 6)"], gc_rows,
               "Top rows: the admissible components and their conjunction. Bottom rows: definitions stated in advance from the phase-1 findings and the manual-trading hypotheses, not searched.")
wf = L["walk_forward_years"]
years = sorted({k for w in wf for k in w if k != "rule"})
wf_rows = [[w["rule"]] + [(f"{w[y][0]:+.3f} ({w[y][1]:,})", cls(w[y][0])) if y in w else "" for y in years] for w in wf]
wf_tbl = table(["Definition"] + years, wf_rows, "Net 1x1 expectancy (R) and signal count per calendar year.")

page = f"""<title>TWK Signal Edge</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:36px 20px 80px}}
h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}}
.sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}}
.verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}}
td.l,th.l{{text-align:left;white-space:normal;min-width:140px}} tbody tr:last-child td{{border-bottom:none}} td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}}
.decision{{font-size:22px;font-weight:700;margin:8px 0}} .note{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 18px;color:var(--ink2);font-size:13.5px;max-width:85ch}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, raw Supertrend flip, no trade management</p>
<h1>TWK Signal Edge</h1>
<p class="lede">Does the flip itself predict direction? {L['n_signals']:,} raw M3 signals from Sep 2021 to Sep 2026, each followed on one-minute bars for ten hours after entry, with XM's spread. Generated {esc(L['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{i}. {t}</a>" for i, t in enumerate(["Raw edge?", "Where it works", "Where it fails", "What separates good signals", "Entry model", "Exit model", "Cost model", "Manual vs bot", "Out of sample", "Decision", "Method"], 1))}</div>
<div class="verdict"><p class="k">Final decision</p><p class="decision">{esc(N.get('decision', ''))}</p>{para('decision_text')}</div>

{section('1. Does the raw signal have an edge?', f"<p class='decision'>{esc(N.get('q1', ''))}</p>" + para('q1_text') + dir_tbl + hz_tbl + cls_tbl + byy_tbl + xtf_tbl, 'Measured before any stop, trail or filter: first passage to +X before -X, excursions by horizon, outcome classes, year by year, and the same test on M1, M5 and M15.', 's1')}
{section('2. What market conditions does it work in?', para('q2') + splits, 'Every split reported gross and net, by period, with the number of positive years.', 's2')}
{section('3. What market conditions does it fail in?', bullets('q3'), None, 's3')}
{section('4. What distinguishes good signals?', para('q4') + fr_tbl + feat_detail, 'Ranked by evidence: the best-versus-worst bucket order must hold in DEV, VAL and OOS to count.', 's4')}
{section('5. Entry model', tm_tbl + pp_tbl + para('q5'), 'Immediate, confirmation-bar, delayed, pullback and breakout entries on the same signals.', 's5')}
{section('6. Exit model', grid_tbl + grid_h + grid_p + para('q6'), 'The hindsight grid: which stop/target shapes have any expectancy once the entry is fixed.', 's6')}
{section('7. Transaction-cost model', mm_tbl + sp20_txt + para('q7'), None, 's7')}
{section('8. Manual versus automated', bullets('q8') + "<h3>Questionnaire</h3>" + bullets('questionnaire'), 'What the bot cannot see, and the questions that would turn your process into rules.', 's8')}
{section('9. Out-of-sample results', comp_tbl + gc_tbl + wf_tbl + para('q9'), 'GOOD_SIGNAL search restricted to components positive in both selection periods; predefined hypotheses shown alongside.', 's9')}
{section('10. Final decision', f"<p class='decision'>{esc(N.get('decision', ''))}</p>" + para('q10'), None, 's10')}
{section('11. Method and limits', bullets('method'), None, 's11')}
</div>
"""
open("signal_edge_report.html", "w", encoding="utf-8").write(page)
print("signal_edge_report.html written", len(page))
