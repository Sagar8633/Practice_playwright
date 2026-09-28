"""HTML report for the forex / silver / bitcoin / oil study: Chart.js 4 (cdnjs), light/dark tokens, every chart with a table twin.
Reads backtests/baseline_metrics.json, experiments/*.json, the trade CSVs and reports/narrative.json; writes reports/report_forex.html."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: json.load(open(os.path.join(ROOT, *p))) if os.path.exists(os.path.join(ROOT, *p)) else None
BASE = J("backtests", "baseline_metrics.json"); COSTS = J("experiments", "cost_tables.json") or {}; REG = J("experiments", "regime_tables.json") or {}
SWP = J("experiments", "sweeps.json") or {}; VAR = J("experiments", "variants.json") or {}; NAR = J("reports", "narrative.json") or {}
INSTR = [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in BASE["runs"])]
TFN = [C.TF_NAME[t] for t in C.TFS]


def r2(x, d=2):
    if x is None: return None
    try:
        v = float(x)
    except Exception:
        return x
    return None if (math.isnan(v) or math.isinf(v)) else round(v, d)


def weekly(tr, start, end):
    if tr is None or len(tr) == 0: return {"t": [], "v": []}
    s = tr.set_index("time_out")["usd"].sort_index().resample("W").sum().cumsum()
    idx = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="W"); s = s.reindex(idx, method="ffill").fillna(0.0)
    return {"t": [d.strftime("%Y-%m-%d") for d in s.index], "v": [r2(v) for v in s.values]}


def load(instr, cfg, tfn, sc="B"):
    f = os.path.join(ROOT, "backtests", instr, f"{cfg}_{tfn}_{sc}_trades.csv.gz"); return pd.read_csv(f, parse_dates=["time_in", "time_out"]) if os.path.exists(f) else None


def best_of(instr):
    b = NAR.get(instr, {}).get("best")
    if b:
        cfg, tfn = b.split("/")
        if f"{instr}|{cfg}|{tfn}|B" in BASE["runs"]: return cfg, tfn
    c = [(k.split("|")[1], k.split("|")[2], v["metrics"]) for k, v in BASE["runs"].items() if k.startswith(instr + "|") and k.endswith("|B") and v["metrics"]["trades"] >= 50]
    c = [x for x in c if x[2]["net_usd"] > 0]
    if not c: return None
    c.sort(key=lambda x: -x[2]["net_usd"]); return c[0][0], c[0][1]


D = {"meta": {}, "instr": [], "heat": {}, "verdict": [], "spread": {}, "equity": {}, "byYear": {}, "cost": {}, "quality": {}, "regime": {}, "grid": {}, "wf": {}, "variants": {}, "mtf": {}, "compare": [], "narrative": NAR}
models = J("data", "xm", "spread_models.json") or {}
for i in INSTR:
    sp = C.specs(i); aud = J("data", i, "audit.json") or {}
    D["instr"].append({"key": i, "name": C.NAME[i], "xm": C.XMSYM[i], "point": sp["point"], "contract": sp["contract"], "quote": sp["quote"], "swap_long": sp["swap_long_pts"], "swap_short": sp["swap_short_pts"],
                       "spread_2026_pts": r2(np.median(models.get(i, {}).get("2026", [np.nan]))), "spread_usd_001": r2(np.median(models.get(i, {}).get("2026", [0])) * C.usd_per_point_001(i), 3),
                       "m1_rows": aud.get("m1", {}).get("rows"), "first": aud.get("m1", {}).get("server_first", "")[:10], "last": aud.get("m1", {}).get("server_last", "")[:10],
                       "xm_close_diff_pts": r2(aud.get("xm", {}).get("close_diff_median_pts")), "slip_b": C.SLIP[i][0], "slip_c": C.SLIP[i][1]})
    D["spread"][i] = [r2(v, 1) for v in models.get(i, {}).get("2026", [])]
    for cfg in C.CONFIGS:
        D["heat"][f"{i}|{cfg}"] = {tfn: (lambda v: {"net": v["metrics"]["net_usd"], "pf": r2(v["metrics"]["pf"]), "trades": v["metrics"]["trades"], "expR": r2(v["metrics"]["exp_r"], 3), "oos": v["splits"]["OOS"]["net_usd"], "verdict": v["verdict"]})(BASE["runs"][f"{i}|{cfg}|{tfn}|B"])
                                  for tfn in TFN if f"{i}|{cfg}|{tfn}|B" in BASE["runs"]}
    b = best_of(i)
    if b is None:
        D["verdict"].append({"name": C.NAME[i], "key": i, "tf": "none", "cfg": "", "net": None, "pf": None, "dd": None, "trades": 0, "win": None, "level": "critical", "label": "negative on every timeframe", "why": "no timeframe is positive after realistic costs with 60+ trades"})
        continue
    cfg, tfn = b; run = BASE["runs"][f"{i}|{cfg}|{tfn}|B"]; m = run["metrics"]; s = run["splits"]
    lvl = {"robust": "warning", "unstable": "serious", "negative": "critical"}[run["verdict"]]
    D["verdict"].append({"name": C.NAME[i], "key": i, "tf": tfn, "cfg": cfg, "net": m["net_usd"], "pf": r2(m["pf"]), "dd": m["max_dd_usd"], "trades": m["trades"], "win": m["win_rate"], "level": lvl, "label": run["verdict"],
                         "why": f"t-stat {m.get('t_stat')}, best 5 trades {m.get('top5_trades_share')}% of net, OOS ${s['OOS']['net_usd']}, years positive {sum(1 for y in run['yearly'] if y['net_usd'] > 0)}/{len(run['yearly'])}"})
    tr = load(i, cfg, tfn); D["equity"][i] = {"label": f"{tfn} {cfg}", **weekly(tr, C.DATA_START, C.DATA_END)}
    other = "FINAL_H4" if cfg == "ASIS" else "ASIS"
    if f"{i}|{other}|{tfn}|B" in BASE["runs"]:
        D["equity"][i]["other_label"] = f"{tfn} {other}"; D["equity"][i]["other"] = weekly(load(i, other, tfn), C.DATA_START, C.DATA_END)["v"]
    D["byYear"][i] = {"label": f"{tfn} {cfg}", "years": [y["year"] for y in run["yearly"]], "net": [y["net_usd"] for y in run["yearly"]], "pf": [r2(y["pf"]) for y in run["yearly"]], "trades": [y["trades"] for y in run["yearly"]]}
    D["cost"][i] = {"label": f"{tfn} {cfg}", "A": BASE["runs"][f"{i}|{cfg}|{tfn}|A"]["metrics"]["net_usd"], "B": m["net_usd"], "C": BASE["runs"][f"{i}|{cfg}|{tfn}|C"]["metrics"]["net_usd"], "swap": r2(-m["swap_usd"]),
                    "gross_profit": m["gross_profit_usd"], "gross_loss": m["gross_loss_usd"]}
    D["quality"][i] = {"label": f"{tfn} {cfg}", **{k: r2(m.get(k), 4) for k in ("exp_usd", "exp_r", "median_r", "r_p05", "r_p25", "r_p75", "r_p95", "r_ge_1", "r_le_m1", "top10pct_share", "top5_trades_share", "net_ex_top5_usd", "max_consec_losses", "max_dd_usd", "max_dd_pct_cap",
                                                                        "dd_duration_days", "recovery_factor", "sharpe_m", "sortino_m", "pos_months_pct", "cagr_pct", "t_stat", "exp_ci95_lo", "exp_ci95_hi", "win_rate", "payoff", "avg_hold_min", "trades_per_month")},
                       "long": [m["long_trades"], m["long_net_usd"]], "short": [m["short_trades"], m["short_net_usd"]], "exits": m["exit_mix"], "splits": {k: [v["trades"], v["net_usd"], r2(v.get("pf"))] for k, v in s.items()}}
    key = f"{i}|{cfg}|{tfn}"
    if key in REG: D["regime"][i] = {"label": f"{tfn} {cfg}", **{n: [{"k": list(r.values())[0], "trades": r["trades"], "net": r2(r["net_usd"]), "pf": r2(r["pf"])} for r in g] for n, g in REG[key].items()}}
    if key in SWP.get("ma_grid", {}):
        g = SWP["ma_grid"][key]; fasts = sorted({int(k.split("/")[0]) for k in g}); trends = sorted({int(k.split("/")[1]) for k in g})
        D["grid"][i] = {"label": f"{tfn} {cfg}", "fasts": fasts, "trends": trends, "train": [[r2(g[f"{f}/{t}"]["TRAIN"][1], 3) for t in trends] for f in fasts], "oos": [[r2(g[f"{f}/{t}"]["OOS"][1], 3) for t in trends] for f in fasts],
                        "ntrain": [[g[f"{f}/{t}"]["TRAIN"][0] for t in trends] for f in fasts],
                        "counts": [sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30), sum(1 for v in g.values() if v["TRAIN"][1] is not None and v["TRAIN"][1] > 0 and v["TRAIN"][0] >= 30 and (v["VAL"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0), len(g)]}
        ex = SWP["exit_grid"].get(key, {}); D["grid"][i]["exit"] = [sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0), sum(1 for v in ex.values() if (v["TRAIN"][1] or 0) > 0 and (v["OOS"][1] or 0) > 0), len(ex)]
    if key in SWP.get("wf", {}): D["wf"][i] = {"label": f"{tfn} {cfg}", "rows": SWP["wf"][key]}
    vr = [(k.split("|")[-1], v) for k, v in VAR.get("variants", {}).items() if k.startswith(key + "|")]
    if vr: D["variants"][i] = {"label": f"{tfn} {cfg}", "base": [m["trades"], m["net_usd"], r2(m["pf"]), s["TRAIN"]["net_usd"], s["VAL"]["net_usd"], s["OOS"]["net_usd"]],
                              "rows": [{"id": vid, "label": v["label"], "trades": v["metrics"]["trades"], "net": v["metrics"]["net_usd"], "pf": r2(v["metrics"]["pf"]), "train": v["splits"]["TRAIN"]["net_usd"], "val": v["splits"]["VAL"]["net_usd"], "oos": v["splits"]["OOS"]["net_usd"], "verdict": v["verdict"], "vs": v["vs_base"]} for vid, v in vr]}
    mt = [(k.split("|")[2], k.split("|")[3], v) for k, v in VAR.get("mtf", {}).items() if k.startswith(f"{i}|{cfg}|") and v["entry"] == tfn]
    if mt: D["mtf"][i] = [{"id": mid, "mode": mode, "htf": v["htf"], "trades": v["metrics"]["trades"], "net": v["metrics"]["net_usd"], "pf": r2(v["metrics"]["pf"]), "oos": v["splits"]["OOS"]["net_usd"], "vs": v["vs_base"]} for mid, mode, v in mt]
    D["compare"].append({"name": C.NAME[i], "tf": f"{tfn} ({cfg})", "trades": m["trades"], "pf": r2(m["pf"]), "expR": r2(m["exp_r"], 3), "net": m["net_usd"], "dd": m["max_dd_usd"], "years": f"{sum(1 for y in run['yearly'] if y['net_usd'] > 0)}/{len(run['yearly'])}", "oos": s["OOS"]["net_usd"], "t": m.get("t_stat"), "top5": m.get("top5_trades_share"), "verdict": run["verdict"],
                         "robust_runs": sum(1 for k, v in BASE["runs"].items() if k.startswith(i + "|") and k.endswith("|B") and v["verdict"] == "robust")})
dl = BASE.get("daily_long", {})
D["dlong"] = [{"name": C.NAME[k.split("|")[0]], "cfg": k.split("|")[1], "sc": k.split("|")[2], "trades": v["metrics"]["trades"], "net": v["metrics"]["net_usd"], "pf": r2(v["metrics"]["pf"]), "years": f"{sum(1 for y in v['by_year'].values() if y[1] > 0)}/{len(v['by_year'])}", "by": {str(y): r2(vv[1]) for y, vv in v["by_year"].items()}} for k, v in dl.items() if k.endswith("|B")]
D["meta"] = {"instruments": len(INSTR), "runs": sum(1 for _ in open(os.path.join(ROOT, "research", "experiment_log.csv"), encoding="utf-8")) - 1 if os.path.exists(os.path.join(ROOT, "research", "experiment_log.csv")) else 0,
             "start": C.DATA_START, "end": C.DATA_END, "splits": C.SPLITS, "characteristics": REG.get("characteristics", [])}

# ---------------------------------------------------------------- HTML
tpl = open(os.path.join("D:/Practice_Playwright/Vaibhav/research", "report_template.html"), encoding="utf-8").read()
css = tpl[tpl.index("<style>"): tpl.index("</style>") + 8]
helpers = tpl[tpl.index("const $ = (s, el=document)"): tpl.index("// ------------------------------------------------------------------ build the page")]
body = r'''
<div class="wrap">
<header class="top">
  <div class="eyebrow">SimpleSMA18Bot logic on forex majors, silver, bitcoin and US oil · research report · 28 Sep 2026</div>
  <h1>Does the 18/200 SMA breakout have an edge anywhere outside gold?</h1>
  <p class="lead">Ten XM instruments, five years of one-minute data (Sep 2021 to Sep 2026), every timeframe from 1 minute to daily, two configurations (the EA as written and the ATR-scaled exit stack chosen on gold), XM's own spreads and swaps. Money is USD per 0.01 lot, the minimum XM lot. Every chart has a table view.</p>
  <div class="chips" id="chips"></div>
</header>
<nav class="toc" aria-label="Sections"><ul>
<li><a href="#verdict">Verdict</a></li><li><a href="#heat">All timeframes</a></li><li><a href="#data">Data & costs</a></li><li><a href="#baseline">Best timeframes</a></li><li><a href="#quality">Trade quality</a></li><li><a href="#regime">Conditions</a></li><li><a href="#robust">Robustness</a></li><li><a href="#variants">Variants</a></li><li><a href="#dlong">D1 2015-2026</a></li><li><a href="#compare">Comparison</a></li><li><a href="#answers">Answers</a></li><li><a href="#method">Method</a></li>
</ul></nav>
<main>
<section id="verdict"><div class="sec-head"><div class="eyebrow">The answer first</div><h2 id="verdictH2"></h2><p class="lead" id="verdictLead"></p></div><div class="tiles" id="verdictTiles"></div></section>
<section id="heat"><div class="sec-head"><div class="eyebrow">Baseline grid</div><h2>Net result after realistic costs, every instrument and timeframe</h2><p class="lead">USD per 0.01 lot, Sep 2021 to Sep 2026. Blue = positive, red = negative; the marker shows the pre-set verdict (robust = positive expectancy and PF above 1 after costs in TRAIN, VAL and OOS with at least 30 trades each). Hover a cell in the table for PF, trades and the out-of-sample result.</p></div><div id="heatTables"></div></section>
<section id="data"><div class="sec-head"><div class="eyebrow">Data and assumptions</div><h2>Ten instruments, XM specifications, XM spreads</h2></div><div id="specTable"></div><div class="grid-2"><div id="spreadCard"></div><div class="card"><div class="cap"><div><h4>Cost scenarios used everywhere</h4><p>A and C bracket B.</p></div></div><div class="kv"><div>A gross</div><div>No spread, no slippage, no swap: does the signal make money at all?</div><div>B realistic</div><div>XM spread by server hour (median of XM M1 bars) scaled by year (XM H1/M15 medians), slippage per side (forex 3 pts, silver 5, bitcoin 300, oil 3), XM swap points per night with the Wednesday triple (bitcoin daily, oil none)</div><div>C stress</div><div>1.5x the spread, 3x the slippage, swap</div><div>Splits</div><div>TRAIN Sep 2021 to Aug 2024 · VAL Sep 2024 to Aug 2025 · OOS Sep 2025 to Sep 2026, fixed before any run</div><div>Configurations</div><div>AS-IS: v1.00 rules with each symbol's MT5 point (buffer 10 pts, break-even 500/10 pts, swing protection from 500 pts, volume filter on). FINAL_H4: the ATR-scaled exit stack selected on gold (BE 2 ATR, trailing from 5 ATR at 0.5 ATR, step 0.1 ATR, buffer 0)</div></div></div></div><div id="charTable"></div></section>
<section id="baseline"><div class="sec-head"><div class="eyebrow">Best after-cost timeframe per instrument</div><h2>Equity, cost scenarios and years</h2><p class="lead">For each instrument the timeframe and configuration with the largest net result after realistic costs (60+ trades). The orange line is the other configuration on the same timeframe.</p></div><h3>Cumulative profit, realistic costs</h3><div class="grid-2" id="equityGrid"></div><h3>Gross to net</h3><div class="grid" id="costGrid"></div><h3>Net by year</h3><div class="grid" id="yearGrid"></div></section>
<section id="quality"><div class="sec-head"><div class="eyebrow">Quality, not quantity</div><h2>Trade quality of the best timeframes</h2><p class="lead">Expectancy with its bootstrap confidence interval, R distribution, how much of the result the best five trades carry, drawdown and Monte Carlo.</p></div><div id="qualityTable"></div></section>
<section id="regime"><div class="sec-head"><div class="eyebrow">Market conditions</div><h2>Where the trades win and lose</h2><p class="lead">Net USD per 0.01 lot by trend regime, volatility regime, session of entry, weekday and outcome type for the best timeframe of each instrument. Tags are known before the trade.</p></div><div id="regimeTables"></div></section>
<section id="robust"><div class="sec-head"><div class="eyebrow">Overfitting check</div><h2>Parameter maps and walk-forward</h2><p class="lead">Fast x trend SMA map: expectancy per trade on TRAIN with the OOS value in brackets. A real edge is a broad blue region in both. Walk-forward re-chooses the best TRAIN pair every six months and compares it with the fixed 18/200.</p></div><div id="gridTables"></div><div id="wfTables"></div></section>
<section id="variants"><div class="sec-head"><div class="eyebrow">One change at a time</div><h2>Filters, sessions, regimes, higher-timeframe gates</h2><p class="lead">Helpful = better expectancy than the baseline in TRAIN, VAL and OOS; harmful = worse in two or more splits.</p></div><div id="variantTables"></div></section>
<section id="dlong"><div class="sec-head"><div class="eyebrow">Longer history</div><h2>D1 on the hourly path, 2015 to 2026</h2></div><div id="dlongTable"></div></section>
<section id="compare"><div class="sec-head"><div class="eyebrow">Side by side</div><h2>Instrument comparison</h2></div><div id="compareTable"></div></section>
<section id="answers"><div class="sec-head"><div class="eyebrow">The questions</div><h2>Answers</h2></div><div id="answers"></div></section>
<section id="method"><div class="sec-head"><div class="eyebrow">Method and files</div><h2>How the numbers were made</h2></div><ul class="tight">
<li>Engine: the gold research engine (exact port of the MQL5 v1.00 logic, validated against the MT5 tester) generalised to any instrument: point, contract, swap points and triple-swap day are parameters; it reproduces the gold study's numbers to the cent on the gold data.</li>
<li>Path: one-minute Dukascopy bid candles in XM server time; signals on completed bars, stops and fills on the next minute's range; MT5 order validity modelled; H1 2015-2021 for the long D1 test.</li>
<li>Costs: XM's own spread by hour and year, slippage per side, XM swap points, USD conversion at the exit price for USD-base pairs.</li>
<li>Every run is logged in research/experiment_log.csv; every trade list is in backtests/&lt;instrument&gt;/; the written reports are in reports/.</li></ul></section>
</main></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const DATA = __DATA__;
'''
build = r'''
(function build() {
  const D = DATA; const t0 = T(); const TFN = ["1m","3m","5m","10m","15m","30m","1h","2h","4h","D1"];
  $('#chips').append(...[`${D.meta.instruments} instruments`, `${D.meta.start} to ${D.meta.end}, one-minute data`, `${fmtN(D.meta.runs)} logged backtests`, 'XM Global MT5 specifications and spreads', 'USD per 0.01 lot'].map(s => txt('span', 'chip', s)));
  const nar = D.narrative.combined || {};
  $('#verdictH2').textContent = nar.headline || 'No statistically defensible edge on any of the ten instruments';
  $('#verdictLead').textContent = nar.summary || '';
  D.verdict.forEach(v => { const tile = el('div', 'tile'); tile.appendChild(el('div', 'lab', `<b style="font-size:15px;color:var(--ink)">${v.name}</b> · best after costs: ${v.tf} ${v.cfg}`)); tile.appendChild(txt('div', 'val', v.net == null ? '–' : fmt$(v.net)));
    tile.appendChild(el('div', 'sub', v.net == null ? 'negative on every timeframe' : `PF <b>${fmtN(v.pf, 2)}</b> · max DD <b>${fmt$(v.dd)}</b> · <b>${fmtN(v.trades)}</b> trades · win <b>${fmtN(v.win, 1)}%</b>`));
    const glyph = v.level === 'critical' ? '✕' : v.level === 'serious' ? '▲' : '!'; tile.appendChild(el('div', '', `<span class="pill ${v.level}">${glyph} ${v.label}</span>`)); tile.appendChild(txt('div', 'sub', v.why)); $('#verdictTiles').appendChild(tile); });
  // heat tables
  ['ASIS', 'FINAL_H4'].forEach(cfg => {
    const keys = D.instr.map(i => i.key); const scale = Math.max(1, ...keys.flatMap(k => TFN.map(tf => Math.abs((D.heat[`${k}|${cfg}`] || {})[tf]?.net ?? 0))));
    const rows = keys.map(k => { const h = D.heat[`${k}|${cfg}`] || {}; return [D.instr.find(i => i.key === k).name, ...TFN.map(tf => { const c = h[tf]; if (!c) return {html: '–', cls: 'num'}; const cell = heatCell(c.net, scale, 0); const mark = c.verdict === 'robust' ? ' ●' : c.verdict === 'unstable' ? ' ○' : ''; cell.html = `<span title="PF ${fmtN(c.pf, 2)}, ${fmtN(c.trades)} trades, exp ${fmtN(c.expR, 3)} R, OOS ${fmt$(c.oos)}">${fmt$(c.net)}${mark}</span>`; return cell; })]; });
    tableCard('#heatTables', {title: `${cfg}: net USD per 0.01 lot after realistic costs`, sub: '● passes the robust rule, ○ positive overall but not in every split', head: ['instrument', ...TFN], rows, wide: true});
  });
  // specs and spread
  tableCard('#specTable', {title: 'Instruments, XM contract specifications and data', sub: 'Spread = XM 2026 median by server hour; swap in points per night', head: ['instrument', 'XM symbol', 'point', 'contract', 'quote', 'swap long/short pts', 'median spread pts', '= $ per 0.01 lot', 'slippage B/C pts', 'M1 rows', 'first', 'last', 'XM vs Dukascopy close diff (pts)'],
    rows: D.instr.map(i => [i.name, i.xm, i.point, i.contract, i.quote, `${i.swap_long} / ${i.swap_short}`, i.spread_2026_pts, i.spread_usd_001, `${i.slip_b} / ${i.slip_c}`, i.m1_rows, i.first, i.last, i.xm_close_diff_pts]), opts: {numCols: [2, 3, 6, 7, 9, 12], dec: {2: 5, 7: 3}}, wide: true});
  const sk = D.instr.filter(i => (D.spread[i.key] || []).length === 24);
  card('#spreadCard', {title: 'XM spread by server hour, 2026, as a share of the daily median', sub: 'Every instrument normalised to its own median so the intraday shape is comparable', height: 'tall', build: t => lineCfg(t, {labels: Array.from({length: 24}, (_, h) => h + ':00'), datasets: sk.map((i, n) => { const s = D.spread[i.key]; const med = s.slice().sort((a, b) => a - b)[12] || 1; return {label: i.name, data: s.map(v => +(v / med).toFixed(2)), color: ['#2a78d6', '#eb6834', '#1baf7a', '#8a63d2', '#d6a12a', '#2ab5d6', '#d62a8a', '#6b8e23', '#ff7f50', '#708090'][n % 10], thin: true}; }), valFmt: v => fmtN(v, 2) + 'x', catLimit: 8}),
    table: {head: ['hour', ...sk.map(i => i.name + ' pts')], rows: Array.from({length: 24}, (_, h) => [h + ':00', ...sk.map(i => D.spread[i.key][h])])}});
  if (D.meta.characteristics && D.meta.characteristics.length) { const ch = D.meta.characteristics; const cols = Object.keys(ch[0]).filter(k => k !== 'instrument'); tableCard('#charTable', {title: 'Instrument characteristics, Sep 2021 to Sep 2026', sub: 'From the daily bars built in server time', head: ['metric', ...ch.map(c => c.instrument)], rows: cols.map(c => [c, ...ch.map(r => r[c])]), wide: true}); }
  // baseline per instrument
  D.instr.forEach(i => { const e = D.equity[i.key]; if (!e || !e.t.length) return; const ds = [{label: e.label, data: e.v, color: t0.s1}]; if (e.other) ds.push({label: e.other_label, data: e.other, color: t0.s2, thin: true});
    card('#equityGrid', {title: `${i.name}: cumulative profit, ${e.label}`, sub: 'Realistic costs, weekly, USD per 0.01 lot', build: t => lineCfg(t, {labels: e.t, datasets: ds.map((d, n) => ({...d, color: n ? t.s2 : t.s1})), area: true, catLimit: 7}), table: {head: ['week', e.label, ...(e.other ? [e.other_label] : [])], rows: e.t.map((d, n) => [d, e.v[n], ...(e.other ? [e.other[n]] : [])])}}); });
  D.instr.forEach(i => { const c = D.cost[i.key]; if (!c) return; card('#costGrid', {title: `${i.name}: ${c.label}`, sub: `gross A, realistic B, stress C; swap paid ${fmt$(c.swap, 2)}`, height: 'short', build: t => barCfg(t, {labels: ['A gross', 'B realistic', 'C stress'], datasets: [{label: 'net $', data: [c.A, c.B, c.C], color: [c.A, c.B, c.C].map(v => v >= 0 ? t.pos : t.neg)}]}), table: {head: ['scenario', 'net $'], rows: [['A gross', c.A], ['B realistic', c.B], ['C stress', c.C]]}}); });
  D.instr.forEach(i => { const y = D.byYear[i.key]; if (!y) return; card('#yearGrid', {title: `${i.name}: net by year, ${y.label}`, sub: 'Hover for PF and trades (2021 = Sep to Dec, 2026 = Jan to Sep)', height: 'short', build: t => barCfg(t, {labels: y.years.map(String), datasets: [{label: 'net $', data: y.net, color: y.net.map(v => v >= 0 ? t.pos : t.neg), notes: y.pf.map((p, n) => `PF ${fmtN(p, 2)}, ${fmtN(y.trades[n])} trades`)}]}), table: {head: ['year', 'net $', 'PF', 'trades'], rows: y.years.map((yy, n) => [yy, y.net[n], y.pf[n], y.trades[n]])}}); });
  // quality
  const qk = D.instr.filter(i => D.quality[i.key]);
  tableCard('#qualityTable', {title: 'Trade quality of the best after-cost timeframe per instrument', sub: 'Realistic costs; CI = 95% bootstrap interval of the mean trade; capital for % figures = $1,000 per 0.01 lot', head: ['instrument', 'TF', 'exp $', 'CI lo', 'CI hi', 't-stat', 'exp R', 'median R', 'R p05', 'R p95', '>= +1R %', '<= -1R %', 'top-5 share %', 'net ex top-5 $', 'max losing streak', 'max DD $', 'DD % cap', 'DD days', 'Sharpe(m)', 'positive months %', 'CAGR %', 'TRAIN $', 'VAL $', 'OOS $', 'long n / $', 'short n / $'],
    rows: qk.map(i => { const q = D.quality[i.key]; return [i.name, q.label, q.exp_usd, q.exp_ci95_lo, q.exp_ci95_hi, q.t_stat, q.exp_r, q.median_r, q.r_p05, q.r_p95, q.r_ge_1, q.r_le_m1, q.top5_trades_share, q.net_ex_top5_usd, q.max_consec_losses, q.max_dd_usd, q.max_dd_pct_cap, q.dd_duration_days, q.sharpe_m, q.pos_months_pct, q.cagr_pct, q.splits.TRAIN[1], q.splits.VAL[1], q.splits.OOS[1], `${q.long[0]} / ${fmt$(q.long[1])}`, `${q.short[0]} / ${fmt$(q.short[1])}`]; }), opts: {numCols: Array.from({length: 22}, (_, n) => n + 2), dec: {2: 3, 3: 3, 4: 3, 6: 3, 7: 3, 8: 2, 9: 2}}, wide: true});
  // regime
  D.instr.forEach(i => { const r = D.regime[i.key]; if (!r) return; const blocks = ['trend', 'volatility', 'session of entry', 'weekday', 'trade outcome type'].filter(b => r[b]); const scale = Math.max(1, ...blocks.flatMap(b => r[b].map(x => Math.abs(x.net))));
    const rows = []; blocks.forEach(b => r[b].forEach(x => rows.push([b, x.k, x.trades, heatCell(x.net, scale, 0), x.pf]))); tableCard('#regimeTables', {title: `${i.name}: ${r.label} by condition`, head: ['dimension', 'class', 'trades', 'net $', 'PF'], rows, opts: {numCols: [2, 4], dec: {4: 2}}}); });
  // grids and wf
  D.instr.forEach(i => { const g = D.grid[i.key]; if (!g) return; const scale = Math.max(0.01, ...g.train.flat().map(v => Math.abs(v ?? 0)));
    const rows = g.fasts.map((f, a) => [f, ...g.trends.map((t, b) => { const c = heatCell(g.train[a][b], scale, 2); c.html = `${fmtN(g.train[a][b], 2)}${g.ntrain[a][b] < 30 ? '*' : ''} <span style="color:var(--muted)">[${fmtN(g.oos[a][b], 2)}]</span>`; return c; })]);
    tableCard('#gridTables', {title: `${i.name}: fast x trend SMA, ${g.label}`, sub: `TRAIN expectancy $/trade [OOS]; ${g.counts[0]} of ${g.counts[2]} cells positive on TRAIN, ${g.counts[1]} also on VAL and OOS; exit grid ${g.exit[0]}/${g.exit[2]} TRAIN-positive, ${g.exit[1]} also OOS`, head: ['fast \\ trend', ...g.trends.map(String)], rows}); });
  D.instr.forEach(i => { const w = D.wf[i.key]; if (!w || !w.rows.length) return; const ts = w.rows.reduce((s, r) => s + r['test net (chosen) $'], 0), tb = w.rows.reduce((s, r) => s + r['test net (18/200) $'], 0);
    tableCard('#wfTables', {title: `${i.name}: walk-forward, ${w.label}`, sub: `All test months: re-optimised ${fmt$(ts, 2)} vs fixed 18/200 ${fmt$(tb, 2)}`, head: ['train', 'test', 'chosen fast/trend', 'train exp $', 'train trades', 'test trades', 'test net chosen $', 'test net 18/200 $'], rows: w.rows.map(r => [r.train, r.test, r['chosen fast/trend'], r['train exp $'], r['train trades'], r['test trades'], r['test net (chosen) $'], r['test net (18/200) $']]), opts: {numCols: [3, 4, 5, 6, 7], dec: {3: 3}}}); });
  // variants
  const vpill = s => ({html: `<span class="pill ${s === 'helpful' ? 'helpful' : s === 'harmful' ? 'harmful' : 'neutral'}">${s === 'helpful' ? '▲' : s === 'harmful' ? '▼' : '●'} ${s}</span>`});
  D.instr.forEach(i => { const v = D.variants[i.key]; if (!v) return; const b = v.base; const rows = [['baseline', `${v.label}`, b[0], b[1], b[2], b[3], b[4], b[5], '', {html: '<span class="pill base">■ base</span>'}], ...v.rows.map(r => [r.id, r.label, r.trades, r.net, r.pf, r.train, r.val, r.oos, r.verdict, vpill(r.vs)])];
    (D.mtf[i.key] || []).forEach(m => rows.push([m.id + (m.mode === 'close' ? 'c' : ''), `HTF ${m.htf} gate (${m.mode})`, m.trades, m.net, m.pf, '', '', m.oos, '', vpill(m.vs)]));
    tableCard('#variantTables', {title: `${i.name}: ${v.label}`, head: ['id', 'variant', 'trades', 'net $', 'PF', 'TRAIN', 'VAL', 'OOS', 'verdict', 'vs base'], rows, opts: {numCols: [2, 3, 4, 5, 6, 7], baseRow: 0, dec: {4: 2}}, wide: true}); });
  if (D.dlong.length) { const years = [...new Set(D.dlong.flatMap(r => Object.keys(r.by)))].sort(); tableCard('#dlongTable', {title: 'D1, realistic costs, 2015 to 2026 (Dukascopy H1 before Sep 2021, M1 after)', head: ['instrument', 'config', 'trades', 'net $', 'PF', 'years > 0', ...years], rows: D.dlong.map(r => [r.name, r.cfg, r.trades, r.net, r.pf, r.years, ...years.map(y => r.by[y] ?? '–')]), opts: {numCols: [2, 3, 4, ...years.map((_, n) => n + 6)], dec: {4: 2}}, wide: true}); }
  tableCard('#compareTable', {title: 'Best after-cost timeframe per instrument, realistic costs', head: ['instrument', 'best TF (config)', 'trades', 'PF', 'exp R', 'net $', 'max DD $', 'years > 0', 'OOS $', 't-stat', 'top-5 share %', 'verdict', 'robust runs / 20'], rows: D.compare.map(c => [c.name, c.tf, c.trades, c.pf, c.expR, c.net, c.dd, c.years, c.oos, c.t, c.top5, c.verdict, c.robust_runs]), opts: {numCols: [2, 3, 4, 5, 6, 8, 9, 10, 12], dec: {3: 2, 4: 3}}, wide: true});
  const ans = (nar.answers || '').split('\n').filter(Boolean); const ol = el('ol', 'changes'); ans.forEach(a => ol.appendChild(el('li', '', a.replace(/^\d+\.\s*/, '').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')))); $('#answers').appendChild(ol);
  if (nar.why_differ) $('#answers').appendChild(el('p', 'note', nar.why_differ));
  renderAll();
  const mq = window.matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
</script>
'''
html = "<title>SMA18 Forex CFD Study</title>\n" + tpl[tpl.index("<link rel=\"stylesheet\""): tpl.index("<style>")] + css + body + helpers + build
html = html.replace("__DATA__", json.dumps(D, default=lambda o: None if (isinstance(o, float) and (math.isnan(o) or math.isinf(o))) else str(o)))
out = os.path.join(HERE, "report_forex.html"); open(out, "w", encoding="utf-8").write(html); print("written", out, len(html) // 1024, "KB")
