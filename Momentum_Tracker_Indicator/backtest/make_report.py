"""Builds report.html from results/summary.json + results/vp_summary.json."""
import json, html, math
import numpy as np
import pandas as pd

S = json.load(open("results/summary.json"))
V = json.load(open("results/vp_summary.json")) if __import__("os").path.exists("results/vp_summary.json") else {"runs": []}
runs = S["runs"]; vruns = V["runs"]; regime = S["regime"]

# ------------------------------------------------------------------ helpers
def esc(x): return html.escape(str(x))
def money(x, d=0):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "n/a"
    s = f"{abs(x):,.{d}f}"
    return ("-$" if x < 0 else "$") + s
def pct(x, d=0): return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x*100:.{d}f}%"
def num(x, d=2): return "n/a" if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else f"{x:.{d}f}"
def find(bot, tf, win):
    for r in runs + vruns:
        if r["bot"] == bot and r["tf"] == tf and r["window"] == win: return r
    return None
def cls_net(x): return "neg" if (x or 0) < 0 else "pos"

def run_table(rows, cols=None, caption=None):
    cols = cols or [("bot", "Bot"), ("tf", "TF"), ("signals", "Signals"), ("trades", "Trades"), ("net", "Net $ (0.02 lot)"),
                    ("profit_factor", "PF"), ("win_rate", "Win"), ("avg_r", "Avg R"), ("max_dd", "Max DD"),
                    ("median_risk_px", "Median stop"), ("ci", "95% CI of mean trade"), ("p_profit", "P(profit)")]
    out = ["<div class='scroll'><table>"]
    if caption: out.append(f"<caption>{esc(caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th class='{'l' if k in ('bot',) else ''}'>{esc(h)}</th>" for k, h in cols) + "</tr></thead><tbody>")
    for r in rows:
        tds = []
        for k, _ in cols:
            if k == "bot": tds.append(f"<td class='l'>{esc(r['bot'])}</td>")
            elif k == "tf": tds.append(f"<td>M{r['tf']}</td>")
            elif k in ("signals", "trades"): tds.append(f"<td>{r.get(k, 0):,}</td>")
            elif k == "net": tds.append(f"<td class='{cls_net(r.get('net'))}'>{money(r.get('net'))}</td>")
            elif k == "profit_factor": tds.append(f"<td>{num(r.get('profit_factor'))}</td>")
            elif k == "win_rate": tds.append(f"<td>{pct(r.get('win_rate'))}</td>")
            elif k == "avg_r": tds.append(f"<td class='{cls_net(r.get('avg_r'))}'>{num(r.get('avg_r'))}</td>")
            elif k == "max_dd": tds.append(f"<td>{money(r.get('max_dd'))}</td>")
            elif k == "median_risk_px": tds.append(f"<td>{money(r.get('median_risk_px'), 2)}</td>")
            elif k == "ci": tds.append(f"<td>{money(r.get('ci_low'), 2)} to {money(r.get('ci_high'), 2)}</td>")
            elif k == "p_profit": tds.append(f"<td>{pct(r.get('p_profit'))}</td>")
            elif k == "avg_hold_min": tds.append(f"<td>{num(r.get('median_hold_min'), 0)} min</td>")
            elif k == "swap": tds.append(f"<td>{money(r.get('swap_total'))}</td>")
            elif k == "exits":
                ex = r.get("exit_reasons", {}) or {}
                tot = max(1, sum(ex.values()))
                keys = [("SL", "initial SL"), ("SL_gap", "gap"), ("TP", "TP"), ("flip", "flip"), ("opposite", "opposite"),
                        ("SL_purple", "purple"), ("SL_trail_purple", "purple"), ("SL_one_to_one", "1:1"), ("SL_trail_one_to_one", "1:1"),
                        ("SL_lock", "lock"), ("SL_trail_lock", "lock"), ("session_end", "session end")]
                agg = {}
                for k2, lab in keys: agg[lab] = agg.get(lab, 0) + ex.get(k2, 0)
                tds.append("<td class='l small'>" + ", ".join(f"{lab} {v/tot*100:.0f}%" for lab, v in agg.items() if v) + "</td>")
            else: tds.append(f"<td>{esc(r.get(k, ''))}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)

# ------------------------------------------------------------------ SVG charts
def line_chart(series, width=960, height=300, y_label="Cumulative P&L, $ at 0.02 lot", id_="c"):
    """series: list of (label, [(date_str, value)], color_var)"""
    pad_l, pad_r, pad_t, pad_b = 64, 120, 16, 34
    xs_all = [pd.Timestamp(d) for _, pts, _ in series for d, _ in pts]
    ys_all = [v for _, pts, _ in series for _, v in pts]
    if not xs_all: return ""
    x0, x1 = min(xs_all), max(xs_all)
    y0, y1 = min(0, min(ys_all)), max(0, max(ys_all))
    if y1 == y0: y1 = y0 + 1
    span = y1 - y0; y0 -= span * 0.05; y1 += span * 0.05
    W = width - pad_l - pad_r; H = height - pad_t - pad_b
    def X(t): return pad_l + (t - x0).total_seconds() / max(1, (x1 - x0).total_seconds()) * W
    def Y(v): return pad_t + (y1 - v) / (y1 - y0) * H
    # nice y ticks
    raw = (y1 - y0) / 5; mag = 10 ** math.floor(math.log10(raw)); step = mag * (1 if raw / mag < 1.5 else 2 if raw / mag < 3.5 else 5)
    ticks = np.arange(math.ceil(y0 / step) * step, y1, step)
    g = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' aria-labelledby='{id_}t' class='chart'><title id='{id_}t'>{esc(y_label)}</title>"]
    for tv in ticks:
        g.append(f"<line x1='{pad_l}' x2='{width-pad_r}' y1='{Y(tv):.1f}' y2='{Y(tv):.1f}' class='grid'/>")
        g.append(f"<text x='{pad_l-8}' y='{Y(tv)+4:.1f}' text-anchor='end' class='tick'>{money(tv)}</text>")
    g.append(f"<line x1='{pad_l}' x2='{width-pad_r}' y1='{Y(0):.1f}' y2='{Y(0):.1f}' class='baseline'/>")
    # x ticks: years (or months if < 1 year)
    if (x1 - x0).days > 400:
        for y in range(x0.year, x1.year + 1):
            t = pd.Timestamp(y, 1, 1)
            if x0 <= t <= x1: g.append(f"<text x='{X(t):.1f}' y='{height-12}' text-anchor='middle' class='tick'>{y}</text>")
    else:
        t = pd.Timestamp(x0.year, x0.month, 1)
        while t <= x1:
            if t >= x0: g.append(f"<text x='{X(t):.1f}' y='{height-12}' text-anchor='middle' class='tick'>{t.strftime('%b')}</text>")
            t = t + pd.DateOffset(months=1)
    for label, pts, col in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(pd.Timestamp(dt)):.1f},{Y(v):.1f}" for i, (dt, v) in enumerate(pts))
        g.append(f"<path d='{d}' fill='none' stroke='var({col})' stroke-width='2' stroke-linejoin='round'/>")
        dt, v = pts[-1]
        g.append(f"<circle cx='{X(pd.Timestamp(dt)):.1f}' cy='{Y(v):.1f}' r='4' fill='var({col})' stroke='var(--surface)' stroke-width='2'/>")
        g.append(f"<text x='{X(pd.Timestamp(dt))+8:.1f}' y='{Y(v)+4:.1f}' class='lbl'>{esc(label)} {money(v)}</text>")
    g.append("</svg>")
    return "\n".join(g)

def year_bars(bots, years, width=960, height=260, id_="b"):
    """bots: list of (label, {year: net}, color_var)"""
    pad_l, pad_r, pad_t, pad_b = 64, 16, 16, 34
    vals = [v for _, d, _ in bots for v in d.values()]
    if not vals: return ""
    y0, y1 = min(0, min(vals)), max(0, max(vals))
    if y1 == y0: y1 = y0 + 1
    span = y1 - y0; y0 -= span * 0.05; y1 += span * 0.08
    W = width - pad_l - pad_r; H = height - pad_t - pad_b
    def Y(v): return pad_t + (y1 - v) / (y1 - y0) * H
    raw = (y1 - y0) / 5; mag = 10 ** math.floor(math.log10(raw)); step = mag * (1 if raw / mag < 1.5 else 2 if raw / mag < 3.5 else 5)
    ticks = np.arange(math.ceil(y0 / step) * step, y1, step)
    g = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' class='chart'>"]
    for tv in ticks:
        g.append(f"<line x1='{pad_l}' x2='{width-pad_r}' y1='{Y(tv):.1f}' y2='{Y(tv):.1f}' class='grid'/>")
        g.append(f"<text x='{pad_l-8}' y='{Y(tv)+4:.1f}' text-anchor='end' class='tick'>{money(tv)}</text>")
    g.append(f"<line x1='{pad_l}' x2='{width-pad_r}' y1='{Y(0):.1f}' y2='{Y(0):.1f}' class='baseline'/>")
    gw = W / len(years); bw = min(28, (gw - 12) / len(bots))
    for i, y in enumerate(years):
        cx = pad_l + gw * (i + 0.5)
        g.append(f"<text x='{cx:.1f}' y='{height-12}' text-anchor='middle' class='tick'>{y}</text>")
        for j, (label, d, col) in enumerate(bots):
            v = d.get(y)
            if v is None: continue
            x = cx - bw * len(bots) / 2 + j * bw + 1
            top, bot = (Y(v), Y(0)) if v >= 0 else (Y(0), Y(v))
            g.append(f"<rect x='{x:.1f}' y='{top:.1f}' width='{bw-2:.1f}' height='{max(1, bot-top):.1f}' rx='3' fill='var({col})'><title>{esc(label)} {y}: {money(v)}</title></rect>")
    g.append("</svg>")
    legend = "".join(f"<span class='leg'><i style='background:var({col})'></i>{esc(l)}</span>" for l, _, col in bots)
    return "\n".join(g) + f"<div class='legend'>{legend}</div>"

# ------------------------------------------------------------------ content blocks
base6 = [r for r in runs if r["window"] == "6m" and r["bot"] in ("PineEA", "MomentumEA")]
base5 = [r for r in runs if r["window"] == "5y" and r["bot"] in ("PineEA", "MomentumEA")]
variants = [r for r in runs if r["window"] == "5y" and r["bot"] not in ("PineEA", "MomentumEA")]
worst = {tf: find("MomentumEA_worstpath", tf, "5y") for tf in (1, 5, 15)}

eq_series = []
for r in base5:
    if r.get("equity"):
        col = "--s1" if r["bot"] == "PineEA" else "--s2"
        eq_series.append((f"{r['bot']} M{r['tf']}", list(zip(r["equity_time"], r["equity"])), col))
charts_eq = {}
for tf in (1, 5, 15):
    ss = [s for s in eq_series if s[0].endswith(f" M{tf}")]
    charts_eq[tf] = line_chart(ss, id_=f"eq{tf}")

years = sorted({int(y) for r in base5 for y in (r.get("by_year") or {}).keys()})
charts_year = {}
for tf in (1, 5, 15):
    bots = []
    for r in base5:
        if r["tf"] == tf and r.get("by_year"):
            bots.append((r["bot"], {int(y): v["net"] for y, v in r["by_year"].items()}, "--s1" if r["bot"] == "PineEA" else "--s2"))
    charts_year[tf] = year_bars(bots, years, id_=f"yb{tf}")

def year_table(tf):
    rows = ["<div class='scroll'><table><thead><tr><th class='l'>Year</th><th>Gold (median)</th><th>M1 ATR(10)</th><th>Spread</th>"]
    for r in base5:
        if r["tf"] == tf: rows.append(f"<th>{esc(r['bot'])} net</th><th>PF</th><th>trades</th><th>median stop</th>")
    rows.append("</tr></thead><tbody>")
    for reg in regime:
        y = reg["year"]
        tds = [f"<td class='l'>{y}</td><td>${reg['median_close']:,.0f}</td><td>${reg['m1_atr10_median']:.2f} ({reg['atr_pts']} pts)</td><td>{reg['spread_pts']} pts</td>"]
        for r in base5:
            if r["tf"] == tf:
                v = (r.get("by_year") or {}).get(str(y)) or (r.get("by_year") or {}).get(y)
                if v: tds.append(f"<td class='{cls_net(v['net'])}'>{money(v['net'])}</td><td>{num(v['pf'])}</td><td>{v['trades']:,}</td><td>{money(v['med_risk'], 2)}</td>")
                else: tds.append("<td>n/a</td><td></td><td></td><td></td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    rows.append("</tbody></table></div>")
    return "\n".join(rows)

# spread cost share
def spread_share(r):
    if not r or not r.get("trades"): return ""
    tf = r["tf"]; yr = 2026
    spr = next((g["spread_pts"] for g in regime if g["year"] == yr), 51)
    cost = r["trades"] * spr * 0.01 * 2  # $ at 0.02 lot per round trip = spread x 1 oz x 2
    return money(cost)

NARR = json.load(open("results/narrative.json")) if __import__("os").path.exists("results/narrative.json") else {}

def section(title, body, sub=None):
    return f"<section><h2>{esc(title)}</h2>" + (f"<p class='sub'>{sub}</p>" if sub else "") + body + "</section>"

def para(k, default=""):
    v = NARR.get(k, default)
    if isinstance(v, list): return "".join(f"<p>{x}</p>" for x in v)
    return f"<p>{v}</p>" if v else ""

def bullets(k):
    v = NARR.get(k, [])
    return "<ul>" + "".join(f"<li>{x}</li>" for x in v) + "</ul>" if v else ""

vp_rows = [r for r in vruns]
vp_tbl = run_table(vp_rows, cols=[("bot", "Playbook"), ("tf", "TF"), ("window", "Window"), ("signals", "Setups"), ("trades", "Trades"), ("net", "Net $ (0.02 lot)"),
                                  ("profit_factor", "PF"), ("win_rate", "Win"), ("avg_r", "Avg R"), ("max_dd", "Max DD"), ("ci", "95% CI of mean trade"), ("p_profit", "P(profit)")]) if vp_rows else "<p>Volume-profile run not available.</p>"

data = S["data"]
n_bars = data["bars"]

# ------------------------------------------------------------------ M3 purple-line scenario (user request)
SC = json.load(open("results/scenario_m3_summary.json")) if __import__("os").path.exists("results/scenario_m3_summary.json") else None
scn_html = ""
if SC:
    ex = SC["exact"]
    rows = ["<div class='scroll'><table><thead><tr><th class='l'>Reading</th><th>Window</th><th>Trades</th><th>Net $ (0.02 lot)</th><th>PF</th><th>Win</th><th>Avg R</th><th>Max DD</th><th class='l'>By year</th></tr></thead><tbody>"]
    for r in ex:
        by = r.get("by_year") or {}
        bys = ", ".join(f"{y}: <span class='{cls_net(v)}'>{money(v)}</span>" for y, v in by.items())
        rows.append(f"<tr><td class='l'>{esc(r['bot'])}</td><td>{esc(r['window'])}</td><td>{r.get('trades',0):,}</td><td class='{cls_net(r.get('net'))}'>{money(r.get('net'))}</td>"
                    f"<td>{num(r.get('profit_factor'))}</td><td>{pct(r.get('win_rate'))}</td><td class='{cls_net(r.get('avg_r'))}'>{num(r.get('avg_r'))}</td><td>{money(r.get('max_dd'))}</td><td class='l small'>{bys}</td></tr>")
    rows.append("</tbody></table></div>")
    g = pd.DataFrame(SC["grid"])
    n_is = int((g.is_net > 0).sum()); n_oos = int((g.oos_net > 0).sum()); n_both = int(((g.is_net > 0) & (g.oos_net > 0)).sum())
    n_all = int(((g.is_net > 0) & (g.oos_net > 0) & (g.m6_net > 0)).sum())
    tiles = f"""<div class='tiles'>
<div class='tile'><p class='lab'>Configurations tested</p><p class='val'>{len(g)}</p><p class='s'>ratio x ADX x target x session x exit</p></div>
<div class='tile'><p class='lab'>Profitable 2021 to 2024</p><p class='val {'pos' if n_is else 'neg'}'>{n_is}</p><p class='s'>in-sample</p></div>
<div class='tile'><p class='lab'>Profitable 2025 to 2026</p><p class='val {'pos' if n_oos else 'neg'}'>{n_oos}</p><p class='s'>out of sample</p></div>
<div class='tile'><p class='lab'>Profitable in both and in the last 6 months</p><p class='val {'pos' if n_all else 'neg'}'>{n_all}</p><p class='s'>{n_both} in both periods</p></div></div>"""
    top = g.sort_values("oos_net", ascending=False).head(10)
    gt = ["<div class='scroll'><table><caption>Top 10 by 2025-2026 result, with the same settings in 2021-2024 and in the last 6 months</caption><thead><tr><th class='l'>Setting</th><th>2021-24 net</th><th>PF</th><th>n</th><th>2025-26 net</th><th>PF</th><th>n</th><th>95% CI of mean trade (2025-26)</th><th>Last 6m net</th><th>PF</th></tr></thead><tbody>"]
    for _, r in top.iterrows():
        gt.append(f"<tr><td class='l'>{esc(r['name'])}</td><td class='{cls_net(r.is_net)}'>{money(r.is_net)}</td><td>{num(r.is_pf)}</td><td>{int(r.is_n):,}</td>"
                  f"<td class='{cls_net(r.oos_net)}'>{money(r.oos_net)}</td><td>{num(r.oos_pf)}</td><td>{int(r.oos_n):,}</td><td>{money(r.oos_ci_low,2)} to {money(r.oos_ci_high,2)}</td>"
                  f"<td class='{cls_net(r.m6_net)}'>{money(r.m6_net)}</td><td>{num(r.m6_pf)}</td></tr>")
    gt.append("</tbody></table></div>")
    scn_html = section("Requested scenario: M3, ratio 1.5, both boxes, ADX 20, stop on the purple line and trailed",
                       "\n".join(rows) + para("scenario_exact") + tiles + "\n".join(gt) + para("scenario_grid"),
                       "Entry at the flip close per Pine, filled at the next bar. Stop = purple line from the first tick, moved to the new purple line on every closed M3 bar, never loosened. Readings: ratio on the M1 row only (as the EA does) or on both rows; with the 1:2 target or with no target; hold through the opposite flip or close on it.")

page = f"""<title>TWK Gold Bots Verdict</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--base:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#0ca30c;--goodtext:#006300;--warn:#fab219;--crit:#d03b3b;--critbg:rgba(208,59,59,.08);--goodbg:rgba(12,163,12,.08);--warnbg:rgba(250,178,25,.14)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--goodtext:#0ca30c;--critbg:rgba(208,59,59,.16);--goodbg:rgba(12,163,12,.16);--warnbg:rgba(250,178,25,.16)}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--goodtext:#0ca30c;--critbg:rgba(208,59,59,.16);--goodbg:rgba(12,163,12,.16);--warnbg:rgba(250,178,25,.16)}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding-block:0}}
.wrap{{max-width:1080px;margin:0 auto;padding:36px 20px 80px}}
h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:70ch;margin:0 0 18px}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px}}
.chip{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink2);font-variant-numeric:tabular-nums}}
.chip b{{color:var(--ink);font-weight:600}}
h2{{font-size:20px;margin:44px 0 6px;letter-spacing:-.01em}}
.sub{{color:var(--ink2);margin:0 0 14px;max-width:80ch}}
p{{max-width:76ch}}
ul{{max-width:80ch;padding-left:20px}} li{{margin:6px 0}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}}
.verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}}
.verdict p{{margin:6px 0;font-size:16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:0 0 8px}}
.tile{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}}
.tile .lab{{font-size:12px;color:var(--ink2);margin:0 0 6px}}
.tile .val{{font-size:26px;font-weight:600;line-height:1.05}}
.tile .val.neg{{color:var(--crit)}} .tile .val.pos{{color:var(--goodtext)}}
.tile .s{{font-size:12px;color:var(--ink2);margin-top:6px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}}
caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px}}
th,td{{padding:9px 11px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}}
th{{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}}
td.l,th.l{{text-align:left}} td.small{{font-size:12px;white-space:normal;min-width:220px;color:var(--ink2)}}
tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}}
.chart{{display:block;background:var(--surface);border:1px solid var(--ring);border-radius:10px;margin:8px 0 4px}}
.grid{{stroke:var(--grid);stroke-width:1}} .baseline{{stroke:var(--base);stroke-width:1}}
.tick{{fill:var(--muted);font-size:11px;font-family:system-ui,sans-serif}} .lbl{{fill:var(--ink2);font-size:11.5px;font-family:system-ui,sans-serif}}
.legend{{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--ink2);margin:6px 0 16px}}
.leg i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.pill{{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;letter-spacing:.04em}}
.pill.bad{{background:var(--critbg);color:var(--crit)}} .pill.warn{{background:var(--warnbg);color:#7a5200}} .pill.ok{{background:var(--goodbg);color:var(--goodtext)}}
:root[data-theme="dark"] .pill.warn{{color:var(--warn)}} @media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .pill.warn{{color:var(--warn)}}}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.note{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 18px;color:var(--ink2);font-size:13.5px}}
.tabs{{display:flex;gap:6px;margin:10px 0 0}} .tabs button{{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--ring);background:var(--surface);color:var(--ink);border-radius:8px;cursor:pointer}}
.tabs button[aria-selected="true"]{{background:var(--ink);color:var(--page);border-color:var(--ink)}} .tabs button:focus-visible{{outline:2px solid var(--s1);outline-offset:2px}}
code{{font-family:ui-monospace,Consolas,monospace;font-size:.92em;background:var(--surface);border:1px solid var(--ring);padding:0 5px;border-radius:4px}}
@media (prefers-reduced-motion:no-preference){{.tabs button{{transition:background .15s}}}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD backtest report</p>
<h1>TWK Gold Bots Verdict</h1>
<p class="lede">Both TWK robots (the raw Pine flip bot and the filtered Momentum EA) replayed on {n_bars:,} one-minute gold bars from {data['start'][:10]} to {data['end'][:10]}, on 1, 5 and 15-minute signals, with XM's spread and swap. Plus a separate volume-profile and order-flow test.</p>
<div class="chips"><span class="chip">Data <b>Dukascopy XAUUSD M1 bid</b>, rounded to XM's 0.01 point</span><span class="chip">Costs <b>XM spread by year</b> + swap</span><span class="chip">Size <b>0.02 lot</b> (your live setting)</span><span class="chip">Tie rule <b>SL before TP</b> inside a bar</span><span class="chip">Generated {esc(S['generated'])}</span></div>

<div class="verdict"><p class="k">Verdict</p>{para('verdict')}</div>

{section('Last 6 months (25 Mar to 25 Sep 2026)', run_table(base6) + para('six_months'), 'Every bot, every timeframe, same window. Net is in dollars at 0.02 lot; divide by 2 for 0.01 lot.')}

{section('Five years (Sep 2021 to Sep 2026)', run_table(base5) + para('five_years'), 'The same rules over the whole history. Cumulative P&amp;L by timeframe below.')}
<h3>Cumulative P&amp;L, 5 years, M1 signals</h3>{charts_eq[1]}
<h3>M5 signals</h3>{charts_eq[5]}
<h3>M15 signals</h3>{charts_eq[15]}

{section('What changed in five years, and why it matters', year_table(15) + charts_year[15] + para('regime'), 'Gold went from about $1,750 to $4,500 and the size of a one-minute bar grew five-fold. Every distance in the bots is a fixed number of points.')}
<h3>Year by year, M1 signals</h3>{charts_year[1]}{year_table(1)}
<h3>Year by year, M5 signals</h3>{charts_year[5]}{year_table(5)}

{section('Why they lose', bullets('why') + run_table(base5, cols=[('bot','Bot'),('tf','TF'),('trades','Trades'),('exits','How trades ended'),('avg_hold_min','Median hold'),('swap','Swap paid'),('median_risk_px','Median stop')]), 'The mechanics behind the numbers.')}

{section('Fixes tested (5 years)', run_table(variants + [w for w in worst.values() if w and w not in variants]) + para('fixes'), 'Each row changes one thing against the shipped settings. A fix that only works on one timeframe or one year is not a fix.')}

{scn_html}

{section('Separate test: volume profile + order flow', vp_tbl + para('vp'), 'Previous-day value area (POC, VAH, VAL from real M1 volume) with an aggressor-delta gate as the only order-flow data that exists historically. XM keeps no historical order book for GOLD, so a true DOM test is impossible for anyone.')}

{section('Method, validation and limits', bullets('method'), 'What the numbers can and cannot tell you.')}
</div>
"""
open("report.html", "w", encoding="utf-8").write(page)
print("report.html written", len(page))
