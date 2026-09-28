"""Builds discovery_report.html from results/discovery/discovery.json and narrative_discovery.json."""
import html, json, math, os
import pandas as pd

D = json.load(open("results/discovery/discovery.json"))
N = json.load(open("results/discovery/narrative_discovery.json")) if os.path.exists("results/discovery/narrative_discovery.json") else {}
LED = pd.DataFrame(D["ledger"])

def esc(x): return html.escape(str(x))
def num(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def pct(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    return f"{x*100:.{d}f}%"
def cls(x): return "" if x is None or (isinstance(x, float) and math.isnan(x)) else ("neg" if x < 0 else "pos")
def R(x): return (num(x, 3), cls(x))
def PF(x): return (num(x, 2), "" if x is None or (isinstance(x, float) and math.isnan(x)) else ("pos" if x > 1 else "neg"))
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
def status_cell(s):
    return (s, {"CANDIDATE": "pos", "CANDIDATE(alt shape)": "pos", "WEAK": "", "REJECT": "neg", "DATA_INSUFFICIENT": "", "DIAGNOSTIC": ""}.get(s, ""))

# ---- the ledger, primary shape (1R stop / 2R target) and the directional shape (1x1)
def ledger_table(df, caption, shape="1.0x2.0"):
    rows = []
    for r in df.to_dict("records"):
        def g(p, k):
            v = r.get(f"{p}_{shape}_{k}")
            return None if v is None or (isinstance(v, float) and math.isnan(v)) else v
        rows.append([r["hypothesis"], r["direction"], r["tf"], f"{int(r['n']):,}"] + [x for p in ("DEV", "VAL", "OOS") for x in (f"{int(g(p, 'n') or 0):,}", pct(g(p, "hit")), R(g(p, "gross")), R(g(p, "exp")), PF(g(p, "pf")), num(g(p, "z"), 1))] + [status_cell(r["status"]), r["passing"] if isinstance(r["passing"], str) else ""])
    return table(["Hypothesis", "Traded", "TF", "Events"] + [f"{p} {k}" for p in ("DEV", "VAL", "OOS") for k in ("n", "hit", "gross R", "net R", "PF", "z")] + ["Status", "Other passing shape"], rows, caption)
main = LED[~LED.hypothesis.str.contains(r"\[FIRST|\[LATER|\[M15", regex=True)]
first = LED[LED.hypothesis.str.contains(r"\[FIRST|\[LATER", regex=True)]
m15 = LED[LED.hypothesis.str.contains(r"\[M15", regex=True)]
led_main = ledger_table(main, "Every hypothesis, traded with and against its event direction. Shape: 1 ATR stop, 2 ATR target, entry at the next M1 open, XM spread. z = z-score of the gross hit rate against its break-even (50% for symmetric shapes).")
led_11 = ledger_table(main, "The same events on the pure directional shape: 1 ATR stop, 1 ATR target. z is the hit rate against 50%.", "1.0x1.0")
led_first = ledger_table(first, "First occurrence of the day versus later occurrences, traded with the event.") if len(first) else ""
led_m15 = ledger_table(m15, "M15 cross-check of the families that reached WEAK or better on M5.") if len(m15) else ""
counts = LED.status.value_counts().to_dict()
count_tbl = table(["Status", "Rows"], [[k, v] for k, v in counts.items()], f"{D['n_hypotheses']} ledger rows (hypothesis x direction x variant).")

# ---- survivors detail
surv = LED[LED.status.isin(["WEAK", "CANDIDATE", "CANDIDATE(alt shape)"])]
sv_rows = []
for r in surv.itertuples():
    rb = json.loads(r.robustness) if r.robustness else {}; cs = json.loads(r.cost) if r.cost else {}; by = json.loads(r.by_year) if r.by_year else {}
    sv_rows.append([r.hypothesis, r.direction, r.tf, status_cell(r.status), r.passing or "1.0x2.0", f"{rb.get('years_positive', '')} / {rb.get('years', '')}", ", ".join(f"{y}: {v['exp']:+.2f} ({v['n']})" for y, v in by.items()),
                    rb.get("max_month_share", ""), rb.get("max_trade_share", ""), rb.get("max_session_share", ""), "; ".join(f"{k} {v['exp']:+.3f} ({v['n']})" for k, v in rb.get("by_direction", {}).items()),
                    "; ".join(f"{k} {v['exp']:+.3f} ({v['n']})" for k, v in rb.get("by_session", {}).items()), "; ".join(f"{k}: " + "/".join(f"{v[p]:+.3f}" for p in ("DEV", "VAL", "OOS")) for k, v in cs.items())])
sv_tbl = table(["Hypothesis", "Traded", "TF", "Status", "Shape", "Years positive", "Net R by year (n)", "Max month share of net", "Max trade share", "Max session share", "By direction", "By session", "Cost stress DEV/VAL/OOS (x1.25; x1.5; x2)"], sv_rows,
               "Robustness protocol for every row that was not rejected in development.") if len(sv_rows) else "<p>No hypothesis reached the robustness stage.</p>"

# ---- MFE/MAE asymmetry table (with direction, 20-bar horizon)
mm_rows = []
for k, v in D["mfe_mae"].items():
    if v and "20" in v and k.endswith("| with"):
        mm_rows.append([k.replace(" | with", ""), num(v["5"]["mfe_med"], 2) if "5" in v else "", num(v["5"]["mae_med"], 2) if "5" in v else "", num(v["20"]["mfe_med"], 2), num(v["20"]["mae_med"], 2), pct(v["20"]["share_mfe_gt"], 0), num(v["100"]["mfe_med"], 2) if "100" in v else "", num(v["100"]["mae_med"], 2) if "100" in v else ""])
mm_tbl = table(["Event (traded with)", "MFE 5 bars (ATR)", "MAE 5", "MFE 20", "MAE 20", "MFE > MAE at 20", "MFE 100", "MAE 100"], mm_rows, "Median favourable and adverse excursions in event-TF ATR. Asymmetry shows as MFE above MAE and a share well away from 50%.")
st = D["state_counts"]; st_tbl = table(["State (M5 bars)", "Bars", "Share"], [[k, f"{v:,}", f"{v / sum(st.values()) * 100:.1f}%"] for k, v in sorted(st.items(), key=lambda kv: -kv[1])])

page = f"""<title>XAUUSD Discovery Ledger</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:6px 9px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} td.l,th.l{{text-align:left;white-space:normal;min-width:160px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} .decision{{font-size:22px;font-weight:700;margin:8px 0}} code{{font-family:ui-monospace,Consolas,monospace;font-size:.92em;background:var(--surface);border:1px solid var(--ring);padding:0 5px;border-radius:4px}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, phase 12, event-driven search</p>
<h1>XAUUSD Discovery Ledger</h1>
<p class="lede">Does any market event change the odds of the next move enough to pay the spread? {D['n_hypotheses']} ledger rows from 28 hypotheses across volatility, liquidity and range, mean reversion, momentum, exhaustion, time of day, state transitions, sequences and the TWK flip as a contrarian, sequence and state signal. Development discovers, validation confirms, out of sample is final. Generated {esc(D['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{i}. {t}</a>" for i, t in enumerate(["Result", "Protocol", "Ledger (1R/2R)", "Ledger (1R/1R)", "First vs later", "M15 cross-check", "Robustness of survivors", "Excursion asymmetry", "States", "What this rules out and what is left", "Method"], 1))}</div>
<div class="verdict"><p class="k">Result</p><p class="decision">{esc(N.get('decision', ''))}</p>{para('decision_text')}</div>
{section('1. Result by family', bullets('by_family') + count_tbl, None, 's1')}
{section('2. Protocol', bullets('protocol'), 'Fixed before the run; no threshold was searched.', 's2')}
{section('3. Ledger, primary shape (1 ATR stop, 2 ATR target)', led_main, None, 's3')}
{section('4. Ledger, directional shape (1 ATR stop, 1 ATR target)', led_11, 'The purest test of directional information: a hit rate above 50% gross.', 's4')}
{section('5. First occurrence of the day versus later', led_first, None, 's5')}
{section('6. M15 cross-check', led_m15 or "<p>No family reached the cross-check threshold on M5.</p>", None, 's6')}
{section('7. Robustness of everything not rejected', sv_tbl + para('robustness'), None, 's7')}
{section('8. Excursion asymmetry', mm_tbl + para('asymmetry'), 'MFE versus MAE by horizon, traded with the event.', 's8')}
{section('9. Market states', st_tbl + para('states'), None, 's9')}
{section('10. What this rules out, and what is left', bullets('left'), None, 's10')}
{section('11. Method and limits', bullets('method'), None, 's11')}
</div>
"""
open("discovery_report.html", "w", encoding="utf-8").write(page)
print("discovery_report.html written", len(page))
