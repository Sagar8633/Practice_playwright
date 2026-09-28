"""Builds results/nyao/nyao_report.html (the artifact page) from the lab outputs."""
import base64, json, os, html
import numpy as np
import pandas as pd

OUT = "results/nyao"
runs = pd.read_csv(f"{OUT}/nyao_runs.csv"); runs2 = pd.read_csv(f"{OUT}/nyao_runs2.csv")
comp = pd.read_csv(f"{OUT}/component_tests.csv"); buck = pd.read_csv(f"{OUT}/baseline_by_nyao_score.csv"); tbt = pd.read_csv(f"{OUT}/trade_by_trade_summary.csv")
cal = json.load(open(f"{OUT}/tick_calibration.json")); mc = json.load(open(f"{OUT}/monte_carlo.json")); lab = json.load(open(f"{OUT}/lab.json"))
inv = pd.read_csv(f"{OUT}/STRATEGY_INVENTORY.csv")

def img(name):
    b = open(f"{OUT}/charts/{name}", "rb").read()
    return "data:image/png;base64," + base64.b64encode(b).decode()

def esc(x): return html.escape(str(x))
def f0(x): return "" if pd.isna(x) else f"{x:,.0f}"
def f2(x): return "" if pd.isna(x) else f"{x:.2f}"
def pct(x): return "" if pd.isna(x) else f"{x*100:.0f}%"

def table(headers, rows, cls=""):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{c}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'

def sign(v, s):
    return f'<span class="neg">{s}</span>' if v < 0 else f'<span class="pos">{s}</span>'

# ---------------------------------------------------------------- tables
core = runs[runs.group == "core"]
core_rows = []
label = {"default_M1_hedge_calib": "M1, hedge on (as shipped)", "default_M1_nohedge_calib": "M1, hedge off", "default_M5_hedge_calib": "M5, hedge on",
         "default_M5_nohedge_calib": "M5, hedge off", "default_M3_hedge_calib": "M3, hedge on", "default_M3_nohedge_calib": "M3, hedge off"}
for r in core.itertuples():
    core_rows.append([label[r.run], f0(r.trades), pct(r.win), f2(r.pf), sign(r.exp, f2(r.exp)), f"{f0(r.DEV_net)} / {f2(r.DEV_pf)}", f"{f0(r.VAL_net)} / {f2(r.VAL_pf)}", f"{f0(r.OOS_net)} / {f2(r.OOS_pf)}", f"ruin, ${f0(r.cont_final)}" if r.cont_stopped else f"${f0(r.cont_final)}"])
core_tbl = table(["Default profile, tick-calibrated", "Trades", "Win", "PF", "Exp/trade", "DEV net / PF", "VAL", "OOS", "5 y continuous"], core_rows)

prof = runs[runs.group.isin(["profiles", "deposit"])]
plabel = {"safe_M1_calib": "safe M1 (no hedge, threshold 6, 0.5% stop)", "safe_M5_calib": "safe M5", "balanced_M1_calib": "balanced M1", "balanced_M5_calib": "balanced M5",
          "aggressive_M1_calib": "aggressive M1 (0.03 lot, threshold 3.5)", "aggressive_M5_calib": "aggressive M5", "default_M1_hedge_calib_dep200": "default M1 on $200 (stop $2)", "default_M5_hedge_calib_dep200": "default M5 on $200"}
prof_rows = [[plabel[r.run], f0(r.trades), pct(r.win), f2(r.pf), sign(r.exp, f2(r.exp)), f0(r.DEV_net), f0(r.VAL_net), f0(r.OOS_net), f"${f0(r.cont_final)}" + (" (stopped)" if r.cont_stopped else "")] for r in prof.itertuples()]
prof_tbl = table(["Other profiles and the $200 account", "Trades", "Win", "PF", "Exp/trade", "DEV net", "VAL net", "OOS net", "5 y final"], prof_rows)

bounds = runs[runs.group == "bounds"]
b_rows = []
for r in bounds.itertuples():
    nm = r.run.replace("default_", "").replace("_", " ")
    b_rows.append([nm, f0(r.trades), pct(r.win), f2(r.pf), f0(r.DEV_net), f0(r.VAL_net), f0(r.OOS_net), (f"${f0(r.cont_final)}" if not pd.isna(r.cont_final) else "")])
bounds_tbl = table(["Bounds (for the record)", "Trades", "Win", "PF", "DEV net", "VAL net", "OOS net", "5 y final"], b_rows)

cost = runs[runs.group == "cost"]
cost_rows = [[r.desc + (" (hedge on)" if "hedge" in r.run else "") + f" [{r.run.split('_')[1]}]", f0(r.trades), f2(r.pf), sign(r.exp, f2(r.exp)), f2(r.DEV_pf), f2(r.VAL_pf), f2(r.OOS_pf)] for r in cost.itertuples()]
cost_tbl = table(["Cost scenario (hedge off unless noted)", "Trades", "PF", "Exp/trade", "DEV PF", "VAL PF", "OOS PF"], cost_rows)

entry = runs[runs.group == "entry"]
e_rows = [[r.run.replace("entryonly_", "").replace("_", " ") + ": " + r.desc, f0(r.trades), pct(r.win), f2(r.pf), f2(r.DEV_pf), f2(r.VAL_pf), f2(r.OOS_pf), f2(r.avg_win), f2(r.avg_loss)] for r in entry.itertuples()]
entry_tbl = table(["Entry-only mode", "Trades", "Win", "PF", "DEV PF", "VAL PF", "OOS PF", "Avg win", "Avg loss"], e_rows)

pert = runs[runs.group.isin(["perturb", "session"])]
p_rows = [[r.desc, f0(r.trades), f2(r.pf), sign(r.DEV_exp, f2(r.DEV_exp)), sign(r.VAL_exp, f2(r.VAL_exp)), sign(r.OOS_exp, f2(r.OOS_exp))] for r in pert.itertuples()]
pert_tbl = table(["Perturbation (M5, hedge off)", "Trades", "PF", "DEV exp", "VAL exp", "OOS exp"], p_rows)

fx = runs2
fx_rows = [[r.desc if r.group == "ablation" else r.run.replace("fixed_", "").replace("_", ", "), f0(r.trades), pct(r.win), f2(r.pf), sign(r.net, f0(r.net)), sign(r.gross_before_spread, f0(r.gross_before_spread)), f0(r.spread_cost), f"{f2(r.DEV_pf)} / {f2(r.VAL_pf)} / {f2(r.OOS_pf)}"] for r in fx.itertuples()]
fx_tbl = table(["Fixed $10 stop, no ruin stop, 5 y continuous", "Trades", "Win", "PF", "Net", "Gross before spread", "Spread paid", "DEV / VAL / OOS PF"], fx_rows)

c_rows = [[r.run, f0(r.signals_kept), f0(r.trades), sign(r.net, f0(r.net)), f2(r.pf), f2(r.DEV_pf), f2(r.VAL_pf), f2(r.OOS_pf), ("" if pd.isna(r.passes_dev_val) else ("yes" if r.passes_dev_val else "no"))] for r in comp.itertuples()]
comp_tbl = table(["Gate on BASELINE signals", "Signals kept", "Trades", "Net", "PF", "DEV PF", "VAL PF", "OOS PF", "Better in DEV and VAL"], c_rows)
bk_rows = [[r.bucket, f0(r.n), sign(r.exp, f2(r.exp)), pct(r.win), f2(r.DEV_exp) if not pd.isna(r.DEV_exp) else "", f2(r.VAL_exp) if not pd.isna(r.VAL_exp) else "", f2(r.OOS_exp) if not pd.isna(r.OOS_exp) else ""] for r in buck.itertuples()]
bk_tbl = table(["Nyao score at entry", "BASELINE trades", "Exp/trade (0.02 lot)", "Win", "DEV exp", "VAL exp", "OOS exp"], bk_rows)
t_rows = [[r.category.split("_", 1)[0] + ". " + r.category.split("_", 1)[1].replace("_", " "), f0(r.n), f0(r.base_pnl) if r.base_pnl else "", f0(r.nyao_pnl) if r.nyao_pnl else ""] for r in tbt.itertuples()]
tbt_tbl = table(["Trade-by-trade category", "Trades", "BASELINE P&L", "Nyao P&L"], t_rows)
mc_rows = [[k.replace("_", " "), f0(v["trades_per_year"]), f"{v['mean_trade']:.2f} ({v['ci95'][0]:.2f} to {v['ci95'][1]:.2f})", f"{v['yearly_pnl_p5_p50_p95'][0]:,} / {v['yearly_pnl_p5_p50_p95'][1]:,} / {v['yearly_pnl_p5_p50_p95'][2]:,}", f"{v['p_losing_year']:.3f}", f"{v['rolling_12m_negative_share']*100:.0f}% of {v['rolling_12m_windows']}", f"{v['real_max_dd']:,}"] for k, v in mc.items()]
mc_tbl = table(["Monte Carlo", "Trades / year", "Mean trade (95% CI)", "Yearly P&L p5 / p50 / p95", "P(losing year)", "Negative 12-month windows", "Max DD"], mc_rows)
inv_counts = inv.category.value_counts().to_dict()
inv_rows = [[r.repository, r.language, f0(r.stars), r.category, r.reason] for r in inv.sort_values(["category", "stars"], ascending=[True, False]).itertuples()]
inv_tbl = table(["Repository", "Language", "Stars", "Category", "Why"], inv_rows, cls="small")

# ---------------------------------------------------------------- inline SVG charts
def bar_chart_h(items, title, vmin, vmax, unit="USD per trade at 0.01 lot", w=640):
    """items: list of (label, value, colorvar)"""
    n = len(items); rowh = 34; top = 30; h = top + n * rowh + 36; left = 250; right = 24
    scale = (w - left - right) / (vmax - vmin); x0 = left + (0 - vmin) * scale
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" class="chart">']
    out.append(f'<text x="0" y="16" class="ct">{esc(title)}</text>')
    out.append(f'<line x1="{x0:.1f}" y1="{top}" x2="{x0:.1f}" y2="{h-30}" class="axis"/>')
    for i, (lab_, v, col) in enumerate(items):
        y = top + i * rowh + 6; x1 = left + (min(v, 0) - vmin) * scale; bw = abs(v) * scale
        out.append(f'<rect x="{x1:.1f}" y="{y}" width="{max(bw,1):.1f}" height="22" rx="3" fill="var({col})"><title>{esc(lab_)}: {v:+.2f}</title></rect>')
        out.append(f'<text x="{left-8}" y="{y+16}" text-anchor="end" class="cl">{esc(lab_)}</text>')
        tx = (x1 + bw + 6) if v >= 0 else (x1 - 6); anchor = "start" if v >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{y+16}" text-anchor="{anchor}" class="cv">{v:+.2f}</text>')
    out.append(f'<text x="{left}" y="{h-8}" class="cl">{esc(unit)}</text>')
    out.append("</svg>")
    return "".join(out)

a = cal["all"]
svg_cal = bar_chart_h([("all replayed trades: bar-optimistic bound", a["pnl_bar_mean"], "--s1"), ("all replayed trades: tick replay", a["pnl_tick_mean"], "--s2"),
                       ("trailing exits: bar-optimistic bound", a["trail_pnl_bar"], "--s1"), ("trailing exits: tick replay", a["trail_pnl_tick"], "--s2"), ("trailing exits: activation level (pessimistic bound)", a["trail_pnl_be"], "--s3")],
                      "Mean P&L per trade, 4,991 trades replayed on real ticks (2025)", -0.6, 2.3)

def grouped_pf(df, names, labels_, title, w=720):
    groups = ["DEV", "VAL", "OOS"]; cols = ["--s1", "--s2", "--s3"]
    n = len(names); gw = 120; left = 60; top = 34; ph = 150; h = top + ph + 70
    w = left + n * gw + 20
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" class="chart"><text x="0" y="16" class="ct">{esc(title)}</text>']
    ymax = 1.6
    def y(v): return top + ph - min(v, ymax) / ymax * ph
    for g in (0.5, 1.0, 1.5):
        out.append(f'<line x1="{left}" y1="{y(g):.1f}" x2="{w-10}" y2="{y(g):.1f}" class="{"ref" if g == 1.0 else "grid"}"/><text x="{left-6}" y="{y(g)+4:.1f}" text-anchor="end" class="cl">{g:.1f}</text>')
    for i, nm in enumerate(names):
        r = df[df.run == nm].iloc[0]
        for j, per in enumerate(groups):
            v = float(r[f"{per}_pf"]); x = left + i * gw + 14 + j * 30
            out.append(f'<rect x="{x}" y="{y(v):.1f}" width="26" height="{top+ph-y(v):.1f}" rx="3" fill="var({cols[j]})"><title>{esc(labels_[i])}, {per}: PF {v:.2f}</title></rect>')
        out.append(f'<text x="{left + i*gw + 58}" y="{top+ph+18}" text-anchor="middle" class="cl">{esc(labels_[i])}</text>')
    lx = left
    for j, per in enumerate(groups):
        out.append(f'<rect x="{lx}" y="{h-18}" width="12" height="12" rx="2" fill="var({cols[j]})"/><text x="{lx+16}" y="{h-8}" class="cl">{per}</text>'); lx += 70
    out.append(f'<text x="{w-10}" y="{h-8}" text-anchor="end" class="cl">profit factor, 1.0 = break-even</text></svg>')
    return "".join(out)

svg_pf = grouped_pf(runs, ["default_M1_hedge_calib", "default_M1_nohedge_calib", "default_M5_hedge_calib", "default_M5_nohedge_calib", "default_M3_hedge_calib", "default_M3_nohedge_calib"],
                    ["M1 hedge", "M1 no hedge", "M5 hedge", "M5 no hedge", "M3 hedge", "M3 no hedge"], "Profit factor by period, default profile, tick-calibrated (each period from $1,000)")

def spread_chart(df, names, labels_, title):
    left = 60; top = 34; ph = 160; gw = 150; w = left + len(names) * gw + 20; h = top + ph + 70
    vals = [(float(df[df.run == n].iloc[0].gross_before_spread), float(df[df.run == n].iloc[0].spread_cost), float(df[df.run == n].iloc[0].net)) for n in names]
    vmax = max(abs(v) for t in vals for v in t) * 1.05; vmin = -vmax
    def y(v): return top + ph / 2 - v / vmax * ph / 2
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" class="chart"><text x="0" y="16" class="ct">{esc(title)}</text>']
    for g in (-15000, 0, 15000):
        if abs(g) < vmax:
            out.append(f'<line x1="{left}" y1="{y(g):.1f}" x2="{w-10}" y2="{y(g):.1f}" class="{"ref" if g == 0 else "grid"}"/><text x="{left-6}" y="{y(g)+4:.1f}" text-anchor="end" class="cl">{g/1000:.0f}k</text>')
    cols = ["--s3", "--s1", "--s2"]; nm3 = ["gross before spread", "spread paid", "net"]
    for i, (lab_, t) in enumerate(zip(labels_, vals)):
        for j, v in enumerate(t):
            x = left + i * gw + 14 + j * 40; y0 = y(max(v, 0)); hh = abs(v) / vmax * ph / 2
            out.append(f'<rect x="{x}" y="{y0:.1f}" width="34" height="{max(hh,1):.1f}" rx="3" fill="var({cols[j]})"><title>{esc(lab_)}: {nm3[j]} {v:+,.0f}</title></rect>')
        out.append(f'<text x="{left + i*gw + 74}" y="{top+ph+18}" text-anchor="middle" class="cl">{esc(lab_)}</text>')
    lx = left
    for j in range(3):
        out.append(f'<rect x="{lx}" y="{h-18}" width="12" height="12" rx="2" fill="var({cols[j]})"/><text x="{lx+16}" y="{h-8}" class="cl">{nm3[j]}</text>'); lx += 150
    out.append("</svg>")
    return "".join(out)
svg_spread = spread_chart(runs2, ["fixed_M1_nohedge", "fixed_M5_nohedge", "fixed_M3_nohedge"], ["M1, hedge off", "M5, hedge off", "M3, hedge off"], "Five years at a fixed $10 stop: flat before spread, the spread is the loss (USD, 0.01 lot)")

base = lab["baseline"]; bp = base["periods"]

CSS = """
:root{color-scheme:light;--bg:#f3f5f8;--surface:#ffffff;--ink:#171b21;--muted:#5c6573;--line:#d5dae2;--accent:#2a78d6;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--bad:#c9353f;--good:#1f8f5f;--tile:#e9eef6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#12151a;--surface:#1a1e25;--ink:#edf0f4;--muted:#a5adb8;--line:#2c323c;--accent:#3987e5;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--bad:#e66767;--good:#2fb37d;--tile:#20262f}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#12151a;--surface:#1a1e25;--ink:#edf0f4;--muted:#a5adb8;--line:#2c323c;--accent:#3987e5;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--bad:#e66767;--good:#2fb37d;--tile:#20262f}
body{background:var(--bg);color:var(--ink);font-family:"Source Sans 3","Segoe UI",system-ui,sans-serif;font-size:16px;line-height:1.5;margin:0}
.wrap{max-width:960px;margin:0 auto;padding-block:32px 64px;padding-inline:20px}
h1,h2,h3{font-family:"Archivo","Segoe UI",system-ui,sans-serif;text-wrap:balance;line-height:1.15;margin:0}
h1{font-size:clamp(28px,4.5vw,42px);font-weight:700;letter-spacing:-0.01em}
h2{font-size:22px;font-weight:700;margin-top:48px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:17px;font-weight:600;margin-top:24px}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted)}
p{max-width:70ch;margin:12px 0}
.lead{font-size:18px;max-width:72ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:24px 0}
.tile{background:var(--tile);border-radius:8px;padding:14px 16px}
.tile .n{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}
.tile .l{color:var(--muted);font-size:13px;margin-top:2px}
.neg{color:var(--bad)}.pos{color:var(--good)}
.tw{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:180px}
th{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;font-weight:500;color:var(--muted);letter-spacing:0.02em;position:sticky;top:0;background:var(--surface)}
tbody tr:last-child td{border-bottom:none}
table.small{font-size:13px}table.small td:last-child{white-space:normal;text-align:left;min-width:280px}
figure{margin:20px 0;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px}
figure img{max-width:100%;display:block;border-radius:3px}
figcaption{color:var(--muted);font-size:13px;margin-top:8px;max-width:80ch}
.chart{width:100%;height:auto;max-width:760px;display:block}
.chart .ct{font-family:"Archivo",system-ui,sans-serif;font-size:14px;font-weight:600;fill:var(--ink)}
.chart .cl{font-size:12px;fill:var(--muted)}.chart .cv{font-family:"IBM Plex Mono",monospace;font-size:12px;fill:var(--ink)}
.chart .axis{stroke:var(--muted);stroke-width:1}.chart .grid{stroke:var(--line);stroke-width:1}.chart .ref{stroke:var(--muted);stroke-width:1}
ul{padding-left:20px;max-width:78ch}li{margin:6px 0}
.verdict{background:var(--surface);border-left:4px solid var(--bad);border-radius:0 6px 6px 0;padding:14px 18px;margin:20px 0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.files li{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px}
a{color:var(--accent)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

page = f"""<title>Nyao Scalper Autopsy</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<div class="eyebrow">GitHub scalping-bot research, 26 September 2026</div>
<h1>Nyao Scalper Autopsy</h1>
<p class="lead">The github.com/topics/scalping-bot collection holds one genuine gold EA. It was ported rule for rule, run on your five years of XAUUSD M1 data with XM costs, calibrated on real ticks and compared with the TWK M3 baseline. It loses the account in every period, and the thing that made it look good on bars is a 20-point trailing stop that ticks show never pays.</p>

<div class="tiles">
<div class="tile"><div class="n">12 / 12</div><div class="l">period runs of the default profile that end at the EA's $20 floor (M1, M5, M3; hedge on and off)</div></div>
<div class="tile"><div class="n neg">-0.37</div><div class="l">USD per trade on real ticks, versus +0.43 on the bar-optimistic reading (4,991 replayed trades)</div></div>
<div class="tile"><div class="n">0.57 to 0.73</div><div class="l">profit factor of the shipped profiles, tick-calibrated; BASELINE 0.80 on the same 60 months</div></div>
<div class="tile"><div class="n">0 of 34</div><div class="l">perturbations and ablations with a positive period; the loss is structural</div></div>
</div>

<div class="verdict"><strong>Verdict.</strong> Nothing in this collection improves your strategy. The Nyao entry is a coin flip before spread (win 35% against a 40% break-even at 1.5R), its exit design cuts winners at about $1 after three minutes and holds losers to a $5-10 close, its hedge chain has no loss cap by design, and its score used as a gate makes BASELINE worse. The one transferable finding is a method: any stop or trail smaller than the instrument's minute range has to be tested on ticks, and the tick sample you already have is enough to do it.</div>

<h2>1. Inventory</h2>
<p>20 repositories on the topic page on 26 Sep 2026. One is directly relevant (A), two are research-interesting crypto bots (C), seventeen are not relevant (D): a Windows Forms template farm with three identical "Forex-Scalping-EA" clones whose README badges point at the Linux kernel, two README-only shells, a landing page whose code is on a paid site, seven exchange-specific crypto bots, a Korean stock scanner, two tools, and a 60-line "XAU/USD scalper" that mixes MQL4 calls into an .mq5 file and cannot compile.</p>
{inv_tbl}

<h2>2. What Nyao actually does</h2>
<p>Read from the 5,867-line source, not the README. A 0-10 score per direction from EMA 5/12 alignment and slope, RSI 8 zones, candle body times an impulse factor, an ATR 8 chop ratio, a 5-bar breakout and a wick penalty, smoothed over two closed candles and blended 60/40 with the forming one; evaluated once per bar at its first tick (so the forming candle is one tick long). Threshold 4.5. Stop 1% of equity in dollars at the position's lot ($10 at 0.01 lot on $1,000, $2 on $200). Exit: a $0.20 trailing stop that engages at +$0.75 and is floored at entry + spread + $0.50; break-even after about $0.50; a per-tick health score that closes below 0.4 and re-enters immediately; partial closes that never fire at 0.01 lot. Hedge chain on by default: at 1.5 ATR under water with an opposite score of 4.5 the stop is removed and an opposite, larger, stop-less leg is opened, rolled and reseeded up to 2 levels and 3 cycles, lot cap 0.10, chain-loss caps 0, excluded from the basket stop. Lots increase in drawdown. Full audit with dangerous-mechanism flags and the look-ahead check is in <code>results/nyao/CODE_AUDIT.md</code>.</p>

<h2>3. The trailing stop and the tick calibration</h2>
<p>A bar cannot say whether gold retraced 20 points before it reached the bar's high. The engine reports two bounds; then every non-chain trade inside your Dukascopy tick sample (2025, Thursdays and Fridays, server 14:00-19:59, 575 hours) was replayed tick by tick with the EA's own trailing and break-even rules.</p>
<figure>{svg_cal}<figcaption>Trailing exits land at the activation level: median position between the bounds 0.00, mean 0.05; 68% of exits within 5 points of the activation price; median time to activation 43 s, median hold 50 s. On the whole sample the bar engine says +$2,144 and the ticks say -$1,860.</figcaption></figure>
<figure><img src="{img('tick_calibration.png')}" alt="Scatter of bar-engine versus tick-replay P&L per trade, and histogram of where the tick exit lands between the bounds"><figcaption>Left: each trailing exit, bar-bound P&L on the x-axis, tick truth on the y-axis. Whatever the bar promised, the tick exit sits on the activation line (dotted) or at the break-even stop (zero). Right: the distribution of the position between the bounds.</figcaption></figure>
<p>An MT5 Strategy Tester run in "1 minute OHLC" or "Open prices only" modelling generates the bar's high before its close and reports the optimistic bound (PF 1.3-1.4 on this data). Only "Every tick based on real ticks" shows the real exits. The author publishes no backtest and warns that tester results only mean something when they mirror live conditions.</p>

<h2>4. The shipped profiles, tick-calibrated</h2>
<p>Each period is run separately from $1,000 (DEV 2021-09..2023, VAL 2024, OOS 2025..2026-09-25), so a ruin in DEV does not empty VAL. $20 is the EA's own stop-trading floor.</p>
<figure>{svg_pf}</figure>
{core_tbl}
<p>Gross before spread over the three period runs: M1 hedge -$999, M1 no hedge -$186, M5 no hedge +$64, M3 no hedge +$32; spread paid $1,941-3,004. The hedge chain lifts the profit factor a little (covered chains book paired exits) and doubles the average loss; largest single losses -$138 (M1) and -$393 (M5) on a $1,000 account. The continuous runs are ruined by March-July 2022.</p>
{prof_tbl}
{bounds_tbl}
<figure><img src="{img('equity_readings_M5.png')}" alt="Five-year balance curves for the M5 default profile under the three trailing readings"><figcaption>M5 default profile, five years from $1,000. Dashed: the bar-optimistic bound, which ends at $19,009, almost all of it in 2025-26 when gold's one-minute bars became large enough for "high minus 20 points" to be worth $2-10 a trade. Solid: tick-calibrated, ruined in April 2022. Dotted: pessimistic bound, the same.</figcaption></figure>

<h2>5. Cost sensitivity</h2>
{cost_tbl}
<p>There is nothing to degrade: the strategy is below break-even at zero extra cost, and every scenario ruins every period.</p>

<h2>6. Entry quality</h2>
<p>Management off, the EA's own R:R mode on (stop 1.5 ATR of the last closed candle, target 1.5R, one position, fixed 0.01 lot). Break-even win rate at 1.5R is 40%.</p>
{entry_tbl}
<p>Gross before spread: -$0.04 per trade on 7,180 M5 trades, the same zero your signal lab found for the TWK flip. Threshold 6 on M5 is the one non-zero reading: gross +$0.02 / +$0.04 / +$0.36 per trade in DEV / VAL / OOS, never above the spread, and inside noise in DEV and VAL.</p>
<figure><img src="{img('entry_only.png')}" alt="Profit factor by period for the entry-only runs"></figure>

<h2>7. Parameter robustness</h2>
{pert_tbl}
<p>There is no profitable region to overfit: 25 perturbations of threshold, EMA, RSI, ATR, blend, trailing distance and session are negative in all three periods. What the table establishes is that the loss is structural, spread paid on a 50-second trade with a coin-flip entry.</p>
<figure><img src="{img('perturbation_M5.png')}" alt="Expectancy per trade by perturbation and period"></figure>

<h2>8. Five years at a fixed stop, and what each layer does</h2>
<p>The shipped EA stops itself within months, so to read the whole history the research runs keep every rule but hold the stop at $10 per 0.01 lot and switch off the ruin stop and the drawdown pause.</p>
<figure>{svg_spread}</figure>
{fx_tbl}
<p>Every layer is roughly neutral before costs. Removing the dampening triples the trade count and the spread bill while the gross stays near zero: the signal generates trades, not information. The chain with nothing else closing positions has no floor.</p>
{mc_tbl}

<h2>9. Where it loses</h2>
<p>Fixed-stop M5, expectancy per trade: every session (Asia -0.37, London -0.40, NY overlap -0.30, NY late -0.49), every hour (best 05:00 at -0.12), every year (-0.29 to -0.33 in 2021-25, -0.54 in 2026 with a 51-point spread), with the H1 trend and against it alike (-0.37 / -0.37), in low, normal and high volatility (-0.50 / -0.38 / -0.35). Losers and winners have the same share of counter-trend, high-volatility and NY entries, so no pre-entry condition separates them. What separates them is the exit design: 79% of trades are cut at about +$1 after a median 3 minutes; 21% are held a median 21 minutes to a health close (-$4.37 average, 59% of the loss) or the stop (-$10, 40%). Full breakdowns in <code>results/nyao/LOSS_PATTERN_ANALYSIS.md</code>.</p>
<figure><img src="{img('session_period_M5.png')}" alt="Mean P&L per trade by session and period"></figure>
<figure><img src="{img('week_2026-01-05_M5.png')}" alt="One week of January 2026 with Nyao and BASELINE trades on the same price"><figcaption>Visual test, 5-9 Jan 2026 (OOS). Nyao M5 above: 199 trades, entries at the end of each impulse because every score term measures a move already made; winners one to three candles long; losers at the last impulse before a turn, held through the reversal. BASELINE below: 26 trades in the same week.</figcaption></figure>
<figure><img src="{img('day_2026-01-07_M1.png')}" alt="One day, 7 January 2026, Nyao M1 versus BASELINE"><figcaption>7 Jan 2026 on M1: 64 Nyao trades against 7 BASELINE trades.</figcaption></figure>

<h2>10. The Nyao score as a component of BASELINE</h2>
<p>BASELINE on the same 60 months: {base['n']:,} trades, net {base['net']:,.0f} USD at 0.02 lot, PF {base['pf']:.2f} (DEV {bp['DEV']['pf']:.2f}, VAL {bp['VAL']['pf']:.2f}, OOS {bp['OOS']['pf']:.2f}). The Nyao smoothed score was computed at the exact moment BASELINE enters and used as a gate; retention rule as in the filter lab (better expectancy and PF in both DEV and VAL).</p>
{comp_tbl}
{bk_tbl}
<p>The higher the Nyao momentum score at entry, the worse the TWK trade in DEV: a momentum confirmation on top of a momentum flip selects the late entries. No gate is adopted.</p>
{tbt_tbl}
<p>Only 141 of 5,354 BASELINE trades coincide with a Nyao entry on the same M3 bar and direction. TWK fires on a Supertrend flip a few times a day; Nyao fires whenever EMA, RSI and body agree, 25-70 times a day. There is no shared decision to transfer, and the overlap categories are too small to read.</p>

<h2>11. Conclusions</h2>
<div class="grid2">
<div><h3>Strong evidence</h3><ul><li>The default profile loses the account on this data in 12 of 12 period runs; the continuous run is ruined by mid-2022. PF 0.57-0.73.</li><li>The loss is structural: 25 perturbations and 9 ablations are negative in every period.</li><li>The $0.20 trail exits at its activation level on real ticks; the bar-level profit is a modelling artifact worth about $0.80 a trade, the whole difference between "PF 1.4" and ruin.</li><li>The score gate does not improve BASELINE; the EA's own threshold makes it worse in every period.</li></ul></div>
<div><h3>Weak evidence</h3><ul><li>Entry-only, threshold 6, M5: gross +$0.02 / +$0.04 / +$0.36 per trade by period, net negative in all three.</li><li>The safe profile does not ruin: -30% in five years at PF 0.66-0.75.</li></ul></div>
<div><h3>Failed approaches</h3><ul><li>Every shipped profile on every timeframe; the $200 account (28-30% win rate with a $2 stop); every cost scenario; the hedge chain.</li></ul></div>
<div><h3>Important loss patterns</h3><ul><li>Spread of 32-51 points on a trade whose target is 82-101 points and whose median life is 50 seconds; spread paid equals 2-3 times the deposit per year.</li><li>An account-defined stop that tightens as the account shrinks.</li><li>Immediate same-direction re-entry after a health close; lots increased in drawdown; a chain with no cap.</li></ul></div>
<div><h3>Useful components</h3><ul><li>None transferable. The dead-market gate removes 56 of 42,289 TWK signals and changes nothing; score, health close, break-even on spread, cooldown and drawdown gate are all in the family your filter and protection labs already found to carry no information after costs.</li><li>Method: tick-calibrate any sub-range stop before believing a bar backtest.</li></ul></div>
<div><h3>Baseline, relative to Nyao</h3><ul><li>Weakness: BASELINE is also negative on these 60 months (-$4,888 at 0.02 lot, PF 0.80); it shares the coin-flip entry paying spread, at lower frequency.</li><li>Strengths: a structural stop instead of an account-defined one, a profit-protection scheme that does not sit inside the spread, 4-8 times fewer trades, no martingale; it takes five years to lose what Nyao loses in seven months at half the lot size.</li></ul></div>
<div><h3>Unproven</h3><ul><li>The MT5 news filter (no calendar data; the 15:15-16:00 proxy changed nothing).</li><li>Tick calibration covers 2025 Thu/Fri 14:00-19:59 only; the pessimistic bound still applies at any hour since a 20-point retrace is a one-tick event.</li><li>The two category-C crypto repositories were not reproduced.</li></ul></div>
</div>

<h2>Files</h2>
<ul class="files">
<li>Momentum_Tracker_Indicator/backtest/GITHUB_SCALPING_RESEARCH.md (full report)</li>
<li>results/nyao/STRATEGY_INVENTORY.csv, CODE_AUDIT.md, STRATEGY_COMPARISON.csv, COMPONENT_TEST_RESULTS.csv, TRADE_BY_TRADE_COMPARISON.csv</li>
<li>results/nyao/LOSS_PATTERN_ANALYSIS.md, ROBUSTNESS_ANALYSIS.md, TABLES.md, monte_carlo.json, tick_calibration.csv</li>
<li>results/nyao/trades/*.csv (every trade of every run), charts/, source/nyao_scalper_v43.mq5, settings/*.set</li>
<li>nyao_engine.py, nyao_tick_calibration.py, nyao_lab.py, nyao_lab2.py, make_nyao_tables.py (run in this order, one at a time)</li>
</ul>
</div>
"""
open(f"{OUT}/nyao_report.html", "w", encoding="utf-8").write(page)
print("page bytes", os.path.getsize(f"{OUT}/nyao_report.html"))
