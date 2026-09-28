"""Builds phase14_report.html from results/phase14/{events.csv, plateau_dev.csv, tick_audit.csv, summary.json, narrative_phase14.json}."""
import html, json, math, os
import pandas as pd

OUT = "results/phase14"
S = json.load(open(f"{OUT}/summary.json"))
N = json.load(open(f"{OUT}/narrative_phase14.json")) if os.path.exists(f"{OUT}/narrative_phase14.json") else {}
SPEC = json.load(open(f"{OUT}/frozen_spec.json"))

def esc(x): return html.escape(str(x))
def num(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def pct(x, d=0):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    return f"{x*100:.{d}f}%"
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

def block_table(rows, caption):
    cols = ["Group", "Events", "Triggered", "Up first", "Down first", "Both touched", "Both executed", "Target", "Stop", "Timeout", "Ambiguous", "Gross ATR/event", "Net ATR/event", "PF", "MFE med", "MAE med", "Cost share of gross"]
    body = [[r["group"], r["n"], pct(r["trigger_rate"]), pct(r["up_first"]), pct(r["down_first"]), pct(r["both_touched"]), pct(r["both_executed"]), pct(r["target"]), pct(r["stop"]), pct(r["timeout"]), r["ambiguous"], R(r["gross"]), R(r["net"]), num(r["pf"], 2), num(r["mfe_med"], 2), num(r["mae_med"], 2), pct(r["cost_share"])] for r in rows]
    return table(cols, body, caption)

spec_rows = [[k, v] for k, v in SPEC["orders"].items()] + [[k, v] for k, v in SPEC["costs"].items()]
spec_tbl = table(["Frozen item", "Definition"], spec_rows, f"Frozen {SPEC['frozen_at']}.")
aud = S["audit"]
audit_tbl = table(["Check", "Result"], [[k, v] for k, v in aud.items()], "Tick data quality over all downloaded days.")
main_tbl = block_table(S["by_group"], "Frozen configuration, Scenario B fills (worse of trigger tick and 250 ms later), 250 ms cancellation latency. Development = 2025, out of sample = 2026.")
scen_tbl = table(["Scenario", "Period", "Days", "Events traded", "Net ATR/event", "PF", "Gross ATR/event"], [[r["scenario"], r["period"], r["days"], r["traded"], R(r["net"]), num(r["pf"], 2), R(r["gross"])] for r in S["by_scenario"]], "Fill scenarios A (trigger tick), B (250 ms), C (worst within 1 s), B with the XM spread overlay; cancellation latency 0 / 250 / 1000 ms on Scenario A.")
first_tbl = table(["Period", "Weekday group", "Triggered", "Up first", "Net after up-first", "Net after down-first", "Same-direction continuation from first touch"], [[r["period"], r["group"], r["n"], pct(r["up_first"]), R(r["net_up"]), R(r["net_down"]), pct(r["cont"])] for r in S["first_touch"]], "Directional versus volatility information: if up-first is near 50% and the outcome after either side is similar, the edge is volatility-only.")
win_tbl = table(["Time to first trigger", "Events", "Net ATR/event", "PF", "Target rate"], [[r["bucket"], r["n"], R(r["net"]), num(r["pf"], 2), pct(r["target"])] for r in S["windows"]], "Where in the release window the trigger happens, and how those trades end (Scenario B, all Thu/Fri, 2025 and 2026 pooled for counts).")
tox_tbl = table(["First-minute type", "Events", "Share", "Net ATR/event", "Target rate", "Median first-minute range / ATR", "Median spread max / ATR"], [[r["type"], r["n"], pct(r["share"]), R(r["net"]), pct(r["target"]), num(r["range_med"], 2), num(r["spmax_med"], 3)] for r in S["toxicity"]], "Type 1 clean single trigger, 2 immediate overshoot (target or stop inside 60 s), 3 both sides touched, 4 spread-driven trigger (ask crosses while mid does not), 5 no trigger.")
plat = pd.DataFrame(S["plateau"])
plat_tbl = "".join(f"<h3>{k}</h3>" + table(["Value", "Events", "Net ATR/event (Thu/Fri 2025)", "PF", "Target rate"], [[r["value"], r["n"], R(r["net"]), num(r["pf"], 2), pct(r["target"])] for r in plat[plat.kind == k].to_dict("records")]) for k in ("trigger", "target", "horizon"))
ctrl_tbl = table(["Control", "Period", "Events", "Net ATR/event", "PF"], [[r["control"], r["period"], r["n"], R(r["net"]), num(r["pf"], 2)] for r in S["controls"]], "Same straddle rules at random same-day timestamps (Scenario B).")
conc = S["concentration"]
conc_tbl = table(["Concentration check", "Result"], [[k, v] for k, v in conc.items()], "No single event, day, week or outlier may carry the result.")
cost_tbl = table(["Period", "Gross (mid to mid) ATR/event", "Net Scenario A", "Net Scenario B", "Net with XM overlay", "Cost share of gross (B)"], [[r["period"], R(r["gross"]), R(r["netA"]), R(r["netB"]), R(r["netXM"]), pct(r["share"])] for r in S["cost"]], "Does the edge survive spread? Costs above 80% of gross = FRAGILE.")

page = f"""<title>Release Straddle Ticks</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1160px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:6px 9px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} td.l,th.l{{text-align:left;white-space:normal;min-width:160px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} .decision{{font-size:22px;font-weight:700;margin:8px 0}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, phase 14, tick-level release straddle</p>
<h1>Release Straddle Ticks</h1>
<p class="lede">Is the 15:30 server (08:30 New York) range expansion monetisable after real bid/ask, trigger ordering, cancellation latency and fill delay? Dukascopy ticks, frozen configuration, development 2025, out of sample 2026 read once. Generated {esc(S['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{t}</a>" for i, t in enumerate(["Classification", "Frozen spec", "Tick audit", "Results by weekday", "Fill scenarios and latency", "First touch", "Window width", "First-minute toxicity", "Plateaus (2025 only)", "Controls", "Concentration", "Cost survival", "Next step"], 1))}</div>
<div class="verdict"><p class="k">Classification</p><p class="decision">{esc(N.get('classification', ''))}</p>{para('classification_text')}</div>
{section('1. Frozen specification', spec_tbl + para('spec_note'), None, 's1')}
{section('2. Tick data audit', audit_tbl + bullets('audit_notes'), None, 's2')}
{section('3. Results by weekday group', main_tbl + para('by_group'), 'Thursday, Friday, Monday to Wednesday if downloaded, and all; 2025 and 2026 separately.', 's3')}
{section('4. Fill scenarios and cancellation latency', scen_tbl + para('scenarios'), None, 's4')}
{section('5. First touch: direction or volatility?', first_tbl + para('first_touch'), None, 's5')}
{section('6. Release-window width', win_tbl + para('windows'), None, 's6')}
{section('7. First-minute toxicity', tox_tbl + para('toxicity'), None, 's7')}
{section('8. Plateaus, development only (2025, Thu/Fri, Scenario B)', plat_tbl + para('plateau'), 'Read for a plateau, not a peak; 2026 never entered these tables.', 's8')}
{section('9. Controls', ctrl_tbl + para('controls'), None, 's9')}
{section('10. Concentration', conc_tbl, None, 's10')}
{section('11. Does the edge survive spread?', cost_tbl + para('cost'), None, 's11')}
{section('12. Next step', bullets('next'), None, 's12')}
</div>
"""
open("phase14_report.html", "w", encoding="utf-8").write(page)
print("phase14_report.html written", len(page))
