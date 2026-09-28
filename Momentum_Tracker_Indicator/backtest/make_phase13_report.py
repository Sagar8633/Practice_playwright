"""Builds phase13_report.html (Reports A-G) from results/phase13/*.json, the master ledger and narrative_phase13.json."""
import html, json, math, os
import pandas as pd

A = json.load(open("results/phase13/data_audit.json"))
RO = json.load(open("results/phase13/range_objective.json"))
X = json.load(open("results/phase13/xasset.json")) if os.path.exists("results/phase13/xasset.json") else {"leadlag": [], "monetisation": []}
LED = pd.read_csv("results/ledger/edge_hypothesis_ledger.csv") if os.path.exists("results/ledger/edge_hypothesis_ledger.csv") else pd.DataFrame()
N = json.load(open("results/phase13/narrative_phase13.json")) if os.path.exists("results/phase13/narrative_phase13.json") else {}

def esc(x): return html.escape(str(x))
def num(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def cls(x): return "" if x is None or (isinstance(x, float) and math.isnan(x)) else ("neg" if x < 0 else "pos")
def R(x, d=3): return (num(x, d), cls(x))
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

# Report A: edge source map (narrative rows)
map_tbl = table(["Information source", "Available here", "Resolution", "Potential mechanism", "Tested", "Result / what it needs"], N.get("source_map", []))
# audit
cov = A["coverage_by_year"]
audit_tbl = table(["Check", "Result"], [
    ["Bars, span", f"{A['bars']:,} M1 bars, {A['start'][:10]} to {A['end'][:10]}"], ["Duplicates / non-monotonic timestamps", f"{A['duplicates']} / {A['non_monotonic']}"], ["OHLC inconsistencies", str(A["ohlc_inconsistent"])],
    ["Zero-range bars, zero-volume bars", f"{A['zero_range_bars_pct']}%, {A['zero_volume_bars_pct']}%"], ["Bars with range above $50", f"{A['bars_range_gt_50usd']} (max ${A['max_range']:.0f} at {A['max_range_time'][:16]})"],
    ["Intra-day gaps 1 min to 1 h / 1 h to 1 day", f"{A['gaps_gt_1min_lt_1h']} / {A['gaps_1h_to_1d']}"], ["Weekend gaps / holes over 4 days", f"{A['weekend_gaps_1d_to_4d']} / {A['holes_gt_4d']}"],
    ["Months present", f"{A['months_present']} of 61; thin months: {', '.join(f'{k} ({v} bars)' for k, v in A['thin_months'].items())}"],
    ["Coverage by year", ", ".join(f"{y}: {v['approx_share_of_full_year']*100:.0f}%" for y, v in cov.items())],
    ["Monday first bar hour (server)", ", ".join(f"{h}:00 x{n}" for h, n in A["monday_first_bar_hours"].items())], ["Friday last bar hour (server)", ", ".join(f"{h}:00 x{n}" for h, n in A["friday_last_bar_hours"].items())],
    ["XM spread on the overlap (3 months of M1)", f"median {A['xm_m1_overlap']['spread_median_pts']:.0f} pts, p95 {A['xm_m1_overlap']['spread_p95']:.0f}, p99 {A['xm_m1_overlap']['spread_p99']:.0f}, max {A['xm_m1_overlap']['max_spread']}; above 2x median in {A['xm_m1_overlap']['share_spread_gt_2x_median']*100:.2f}% of minutes"],
    ["Dukascopy vs XM closes on the overlap", f"{A['dk_vs_xm']['matched_bars']:,} matched minutes, median difference ${A['dk_vs_xm']['close_diff_median_usd']}, p95 ${A['dk_vs_xm']['close_diff_p95']}; {A['dk_vs_xm']['xm_bars_missing_in_dk']} XM minutes absent from Dukascopy"],
], "Data quality audit of the five-year M1 dataset and the broker overlap.")
holes_tbl = table(["Hole start", "Hole end", "Days"], [[h["start"], h["end"], h["days"]] for h in A["holes"]], "Missing windows (downloader rate limit); nothing was interpolated.")
# Report F
rr = pd.DataFrame(RO["range"]); rr20 = rr[rr.N == 20].sort_values("auc_all", ascending=False)
range_tbl = table(["Event", "Events", "Range ratio (next 20 bars / unconditional)", "AUC event vs random", "DEV", "VAL", "OOS"], [[r.event, f"{int(r.n):,}", num(r.ratio_all, 2), num(r.auc_all, 2), num(r.ratio_DEV, 2), num(r.ratio_VAL, 2), num(r.ratio_OOS, 2)] for r in rr20.itertuples()],
                  "Median realised range of the next 20 M5 bars in ATR after each event, relative to all bars. AUC 0.5 = no information about volatility.")
prof = RO["profile"]; prof_tbl = table(["Hour (server)", "Median 20-bar range / ATR", "DEV", "VAL", "OOS"], [[f"{p['hour']:02d}:00", num(p["median_fwd20_atr"], 2), num(p["DEV"], 2), num(p["VAL"], 2), num(p["OOS"], 2)] for p in prof], "Deterministic volatility by hour: 14:00 to 15:59 server (7:00 to 8:59 New York) carries the largest ranges.")
st = pd.DataFrame(RO["straddle"])
strad_tbl = table(["After", "Trigger a (ATR)", "Target T (ATR)", "Resolved", "Unresolved (both triggers in one minute)", "Net exp all (ATR)", "DEV", "VAL", "OOS"], [[r.event, r.a, r.T, f"{int(r.n):,}", f"{int(r.ambiguous):,}", R(r.exp_all), R(r.exp_DEV), R(r.exp_VAL), R(r.exp_OOS)] for r in st.itertuples()],
                  "OCO straddle: buy stop at close + a ATR and sell stop at close - a ATR, target T ATR beyond the trigger, stop at the other trigger, spread paid on entry and exit, 250-minute horizon. Random bars are the baseline.")
# Report C
LL = pd.DataFrame(X["leadlag"]); ll_tbl = ""
if len(LL):
    sub = LL[(LL.lag.str.startswith("X(t) ->")) & (LL.k.isin([1, 3, 5, 15, 60]))]
    ll_tbl = table(["Asset", "TF", "k bars ahead", "Period", "n", "Spearman(X return, gold next-k return)", "2-sigma shocks", "Gold after X up (ATR)", "Gold after X down (ATR)", "Gold same direction as shock"], [[r.asset, r.tf, r.k, r.period, f"{int(r.n):,}", R(r.spearman, 4), r.shock_n, R(r.gold_after_X_up_atr), R(r.gold_after_X_down_atr), num(r.shock_hit_same_dir, 3)] for r in sub.itertuples()],
                   "Lead/lag: does asset X's bar-t return predict gold's return over the next k bars? Shock rows: gold's mean next-k move in ATR after a 2-sigma hourly move in X.")
MO = pd.DataFrame(X["monetisation"]); mo_tbl = table(["Asset", "Rule", "n", "DEV n", "DEV exp (R)", "PF", "VAL n", "VAL exp", "PF", "OOS n", "OOS exp", "PF"], [[r.asset, r.rule, r.n, r.DEV_n, R(r.DEV_exp), num(r.DEV_pf, 2), r.VAL_n, R(r.VAL_exp), num(r.VAL_pf, 2), r.OOS_n, R(r.OOS_exp), num(r.OOS_pf, 2)] for r in MO.itertuples()],
                                                     "Trade gold after a 2-sigma hourly shock in X, 1 ATR stop / 2 ATR target, next-open entry, XM H1 spread.") if len(MO) else "<p>No cross-asset monetisation rows.</p>"
# ledger summary
led_tbl = ""
if len(LED):
    led_tbl = table(["Phase", "Entries", "Status counts"], [[p, len(g), ", ".join(f"{k}: {v}" for k, v in g.status.value_counts().items())] for p, g in LED.groupby("phase")], f"Master Edge Hypothesis Ledger: {len(LED)} entries in results/ledger/edge_hypothesis_ledger.csv.")
road_tbl = table(["Rank", "Experiment", "Information value", "Data cost", "Complexity", "Overfitting risk", "OOS validation", "Verdict"], N.get("roadmap_rows", []))

page = f"""<title>XAUUSD Information Gap</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1160px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--s2);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--s2);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:6px 9px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} td.l,th.l{{text-align:left;white-space:normal;min-width:160px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} .decision{{font-size:20px;font-weight:700;margin:8px 0}} code{{font-family:ui-monospace,Consolas,monospace;font-size:.92em;background:var(--surface);border:1px solid var(--ring);padding:0 5px;border-radius:4px}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, phase 13, information gap</p>
<h1>XAUUSD Information Gap</h1>
<p class="lede">Can an edge exist only in information the five-year bar dataset does not contain, and what is the cheapest way to get it? Reports A to G, with the experiments that could run today already run. Generated {esc(str(pd.Timestamp.now())[:16])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{t}</a>" for i, t in enumerate(["Next experiment", "A Edge source map", "Data audit", "B Manual edge", "C Cross-asset", "D Macro / news", "E Tick / microstructure", "F Alternative objective", "G Roadmap", "Ledger", "Stop condition"], 1))}</div>
<div class="verdict"><p class="k">The single next experiment</p><p class="decision">{esc(N.get('next_experiment', ''))}</p>{para('next_text')}</div>
{section('Report A: Edge source map', map_tbl + para('a_text'), None, 's1')}
{section('Data quality audit', audit_tbl + holes_tbl + bullets('audit_effects'), 'Which conclusions the missing data could affect.', 's2')}
{section('Report B: Manual edge experiment', bullets('b_fields') + "<h3>Tests</h3>" + bullets('b_tests'), 'Exact fields and how they will be tested.', 's3')}
{section('Report C: Cross-asset experiment', para('c_intro') + ll_tbl + mo_tbl + para('c_text') + "<h3>Full design (what the data here could not cover)</h3>" + bullets('c_design'), None, 's4')}
{section('Report D: Macro and news experiment', bullets('d_data') + "<h3>Tests</h3>" + bullets('d_tests') + para('d_text'), None, 's5')}
{section('Report E: Tick and microstructure experiment', bullets('e_data') + "<h3>Tests</h3>" + bullets('e_tests'), None, 's6')}
{section('Report F: Alternative objective, volatility instead of direction', range_tbl + prof_tbl + strad_tbl + para('f_text'), 'Run today on the existing data.', 's7')}
{section('Report G: Research roadmap', road_tbl + para('g_text'), 'Ranked by information value, data cost, complexity, overfitting risk and OOS validation.', 's8')}
{section('Edge hypothesis ledger', led_tbl + para('ledger_text'), None, 's9')}
{section('Stop condition', bullets('stop'), None, 's10')}
</div>
"""
open("phase13_report.html", "w", encoding="utf-8").write(page)
print("phase13_report.html written", len(page))
