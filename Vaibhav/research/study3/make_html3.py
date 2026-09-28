"""Build study3/report3.html, the visual version of H4_REPORT.md. Reuses the first report's CSS and chart helpers."""
import json, os, sys
from dataclasses import replace
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import sma18_engine as E
import common as C

R = json.load(open(os.path.join(HERE, "results", "study3.json"), encoding="utf-8"))
N = json.load(open(os.path.join(HERE, "narrative3.json"), encoding="utf-8"))
RES = os.path.join(HERE, "results")


def weekly(tr, start=None, end=None):
    if len(tr) == 0: return {"t": [], "v": []}
    tr = tr.sort_values("time_out"); cum = tr["pnl"].cumsum().to_numpy(); tout = tr["time_out"].to_numpy()
    grid = pd.date_range(pd.Timestamp(start) if start else tr["time_out"].min().normalize(), pd.Timestamp(end) if end else tr["time_out"].max(), freq="W")
    idx = np.searchsorted(tout, grid.to_numpy(), side="right") - 1
    vals = np.where(idx >= 0, cum[np.clip(idx, 0, None)], 0.0)
    return {"t": [d.strftime("%Y-%m-%d") for d in grid], "v": [round(float(x), 2) for x in vals]}


def clean(x):
    if isinstance(x, float) and (np.isnan(x) or np.isinf(x)): return None
    return x


CFG = {"Untouched EA": ("untouched", {}), "E19 as tested": ("e19", dict(thr_mode=1, protection=4, be_enable=True, be_trigger_pts=100, prot_start_mode=1, prot_start_pts=500, trail_start_pts=200, trail_dist_pts=100, trail_step_pts=10)),
       "Final (chosen exit + helpful filters)": ("final", R["final"]["params"])}
D = {"narrative": N, "stage0": R["stage0"], "stage1": R["stage1"], "stage2": R["stage2"], "stage3": R["stage3"], "stage4": R["stage4"], "stage5": R["stage5"], "stage6": {}, "sensitivity": R["sensitivity"], "final": R["final"], "equity6": {}, "equity23": {}}
for nm, (fn, kw) in CFG.items():
    tr = pd.read_csv(os.path.join(RES, f"trades_{fn}.csv"), parse_dates=["time_in", "time_out"])
    D["equity6"][nm] = weekly(tr, C.DATA_START, C.DATA_END)
    p = E.Params(tf_minutes=240, path="h1", start=C.D1_START, end=C.DATA_END, start_balance=100000.0, margin_check=False, use_sl_pct=False, **C.COST["B_real"], **kw)
    tr23, st = E.run(p); D["equity23"][nm] = weekly(tr23, C.D1_START, C.DATA_END)
    D["stage6"][nm] = R["stage6"][nm]
# heat tables cleaned of NaN
for k in ("heat", "heat_minexp"):
    D["stage1"][k] = {be: [[clean(v) for v in row] for row in rows] for be, rows in D["stage1"][k].items()}

t1 = open(os.path.join(ROOT, "report_template.html"), encoding="utf-8").read()
style = t1[t1.index("<style>"): t1.index("</style>") + len("</style>")]
helpers = t1[t1.index('const TFS = ["M1","M5","M15","D1"];'): t1.index("// ------------------------------------------------------------------ build the page")]
fonts = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">'


def para(key):
    return "".join(f"<p>{p.strip()}</p>" for p in N.get(key, "").split("\n\n") if p.strip())


body = f"""
<div class="wrap">
<header class="top">
  <div class="eyebrow">SimpleSMA18Bot v1.00 on XAUUSD · study 3 · H4 only · 26 Sep 2026</div>
  <h1>From the E19 exit stack to the final H4 configuration</h1>
  <p class="lead">Same engine, data (Sep 2020 to Sep 2026, XM costs, 0.01 lot) and splits as the first two studies. The exit levels are in ATR units: multiples of ATR(22) measured on the last completed bar when the trade opened. Every chart has a table view; hover for the numbers.</p>
  <div class="chips" id="chips"></div>
</header>
<nav class="toc" aria-label="Sections"><ul>
<li><a href="#summary">Summary</a></li><li><a href="#stage0">What E19 was</a></li><li><a href="#stage1">Exit grid</a></li><li><a href="#stage2">Filters</a></li><li><a href="#stage4">Stops</a></li><li><a href="#stage5">MA periods</a></li><li><a href="#stage6">Final and robustness</a></li><li><a href="#sens">Sensitivity</a></li><li><a href="#ea">EA changes</a></li>
</ul></nav>
<main>
<section id="summary"><div class="sec-head"><div class="eyebrow">The answer first</div><h2>Break-even at 2 ATR, then a trail that starts late</h2></div><div class="tiles" id="sumTiles"></div>{para("summary")}</section>
<section id="stage0"><div class="sec-head"><div class="eyebrow">Stage 0</div><h2>What E19 actually was</h2></div>{para("stage0")}<div class="grid-2" id="s0"></div></section>
<section id="stage1"><div class="sec-head"><div class="eyebrow">Stage 1 · 150 settings</div><h2>The exit parameter grid</h2><p class="lead">Break-even trigger x trailing start x trailing distance, all in ATR. Heat tables show the six-year net; blue positive, red negative. The selection rule was declared before running: highest weakest-split expectancy among settings positive in DEV, VAL and OOS with at least 40 development trades.</p></div>{para("stage1")}<div class="grid-2" id="s1charts"></div><div id="s1heat"></div><div id="s1tables"></div></section>
<section id="stage2"><div class="sec-head"><div class="eyebrow">Stage 2 and 3 · entry filters</div><h2>Filters on the chosen exit</h2><p class="lead">Cells: change in expectancy per unit of risk versus the chosen exit without filters, per split. Orange bar = no filter.</p></div>{para("stage2")}{para("stage3")}<div class="grid-2" id="s2charts"></div><div id="s2tables"></div></section>
<section id="stage4"><div class="sec-head"><div class="eyebrow">Stage 4</div><h2>Stops on the chosen exit</h2></div>{para("stage4")}<div id="s4"></div></section>
<section id="stage5"><div class="sec-head"><div class="eyebrow">Stage 5 · sensitivity, not selection</div><h2>Fast and trend SMA on the chosen exit</h2></div>{para("stage5")}<div id="s5"></div></section>
<section id="stage6"><div class="sec-head"><div class="eyebrow">Stage 6</div><h2>Final configuration and robustness</h2></div>{para("stage6")}<div class="grid-2" id="s6eq"></div><div class="grid-2" id="s6year"></div><div id="s6tables"></div><div class="tiles" id="mcTiles"></div></section>
<section id="sens"><div class="sec-head"><div class="eyebrow">Sensitivity</div><h2>One parameter at a time around the final values</h2><p class="lead">Blue = all-period expectancy per unit of risk; orange = the weakest of the three splits. A point above zero on the orange line means the setting is positive in every split.</p></div>{para("sensitivity")}<div class="grid" id="sensGrid"></div></section>
<section id="ea"><div class="sec-head"><div class="eyebrow">The code</div><h2>What changed in SimpleSMA18Bot_H4.mq5</h2></div>{para("ea")}
  <div class="card"><div class="cap"><div><h4>New inputs (defaults = the final configuration)</h4></div></div><pre style="margin:0;white-space:pre-wrap;font-family:'IBM Plex Mono',ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.5">input ENUM_TIMEFRAMES TimeFrame = PERIOD_H4;
input int EntryBufferPoints = 0;
input ENUM_PROTECTION_MODE ProtectionMode = PROTECTION_TRAILING;
input ENUM_PROTECTION_START ProtectionStartMode = START_IMMEDIATELY;

input bool   UseATRScaledLevels     = true;
input double ATRBreakEvenMult       = 2.00;   // break-even trigger in ATR
input double ATRProtectionStartMult = 0.0;    // unused while ProtectionStartMode = START_IMMEDIATELY
input double ATRTrailStartMult      = 5.00;   // trailing starts at this profit in ATR
input double ATRTrailDistanceMult   = 0.50;   // trailing distance in ATR (0.5 to 2 all inside the plateau)
input double ATRTrailStepMult       = 0.10;   // minimum stop improvement in ATR

double EntryATR = 0.0;   // ATR(ATRPeriod) of the last completed bar when the position was opened

double LevelPoints(int fixedPoints, double atrMult)
{{
   if(!UseATRScaledLevels || EntryATR <= 0.0 || atrMult < 0.0)
      return (double)fixedPoints;
   return atrMult * EntryATR / _Point;
}}</pre></div>
  <p class="note">Files: <code>Vaibhav/SimpleSMA18Bot_H4.mq5</code> and <code>.ex5</code> (compiled, 0 errors), study details in <code>research/study3/H4_REPORT.md</code>, every run in <code>results/experiment_log.csv</code> (phases S3-*).</p></section>
</main>
</div>
"""

build = r"""
(function build() {
  const D = DATA; const t0 = T();
  const CFGS = Object.keys(D.stage6); const COLS = [t0.s1, t0.s2, t0.s3];
  const atr = v => (v / 100).toFixed(2) + ' ATR';
  $('#chips').append(...['H4, Sep 2020 to Sep 2026, DEV / VAL / OOS as declared', '150-setting exit grid, 28 filters, 14 stops, 24 MA pairs, 8 sensitivity sweeps', 'EA compiled with 0 errors'].map(s => txt('span', 'chip', s)));
  CFGS.forEach(nm => { const a = D.stage6[nm].all; const tile = el('div', 'tile'); tile.appendChild(el('div', 'lab', `<b style="font-size:15px;color:var(--ink)">${nm}</b> · six years`)); tile.appendChild(txt('div', 'val', fmt$(a.net))); tile.appendChild(el('div', 'sub', `PF <b>${fmtN(a.pf, 2)}</b> · max DD <b>${fmt$(a.dd)}</b> · <b>${a.trades}</b> trades · DEV/VAL/OOS ${fmt$(a.DEV[0])} / ${fmt$(a.VAL[0])} / ${fmt$(a.OOS[0])}`)); $('#sumTiles').appendChild(tile); });

  // stage 0
  const s0 = Object.entries(D.stage0);
  card('#s0', {title: 'Three readings of the exit stack, six-year net', build: t => barCfg(t, {labels: s0.map(([k]) => splitLabel(k, 26)), datasets: [{label: 'net $', data: s0.map(([, v]) => v.net), color: t.s1, notes: s0.map(([, v]) => `PF ${fmtN(v.pf, 2)}, DD ${fmt$(v.dd)}, ${v.trades} trades`)}], horizontal: true}), table: {head: ['configuration', 'trades', 'net $', 'PF', 'max DD $'], rows: s0.map(([k, v]) => [k, v.trades, v.net, v.pf, v.dd])}});
  card('#s0', {title: 'The same three by split', build: t => barCfg(t, {labels: s0.map(([k]) => splitLabel(k, 26)), datasets: [{label: 'DEV 2020-23', data: s0.map(([, v]) => v.DEV[0]), color: t.s1}, {label: 'VAL 2023-24', data: s0.map(([, v]) => v.VAL[0]), color: t.s2}, {label: 'OOS 2025-26', data: s0.map(([, v]) => v.OOS[0]), color: t.s3}], horizontal: true}), table: {head: ['configuration', 'DEV net $', 'VAL net $', 'OOS net $'], rows: s0.map(([k, v]) => [k, v.DEV[0], v.VAL[0], v.OOS[0]])}});

  // stage 1
  const s1 = D.stage1; const ax = s1.axes;
  const avgByStart = be => ax.START.map((st, i) => { const row = s1.heat[String(be)][i]; return row.reduce((a, b) => a + b, 0) / row.length; });
  card('#s1charts', {title: 'Average six-year net by trailing start (over the five distances)', sub: 'The late start is the ingredient', build: t => lineCfg(t, {labels: ax.START.map(atr), datasets: [{label: 'break-even 1 ATR', data: avgByStart(100), color: t.s1, points: true}, {label: 'break-even 2 ATR', data: avgByStart(200), color: t.s2, points: true}, {label: 'break-even off', data: avgByStart(0), color: t.s3, points: true}], catLimit: 6}), table: {head: ['trailing start', 'BE 1 ATR', 'BE 2 ATR', 'BE off'], rows: ax.START.map((st, i) => [atr(st), avgByStart(100)[i], avgByStart(200)[i], avgByStart(0)[i]])}});
  card('#s1charts', {title: 'Six-year net by trailing distance at a 5-ATR start', sub: 'A plateau: every distance from 0.5 to 2 ATR is close', build: t => barCfg(t, {labels: ax.DIST.map(atr), datasets: [{label: 'break-even 1 ATR', data: s1.heat['100'][4], color: t.s1}, {label: 'break-even 2 ATR', data: s1.heat['200'][4], color: t.s2}]}), table: {head: ['distance', 'BE 1 ATR', 'BE 2 ATR'], rows: ax.DIST.map((d, i) => [atr(d), s1.heat['100'][4][i], s1.heat['200'][4][i]])}});
  const scale = Math.max(...Object.values(s1.heat).flat(2).map(Math.abs));
  ax.BE.forEach(be => { const rows = ax.START.map((st, i) => [atr(st), ...ax.DIST.map((d, j) => heatCell(s1.heat[String(be)][i][j], scale, 0))]); tableCard('#s1heat', {title: `Net $ with break-even ${be ? atr(be) : 'off'}`, sub: 'rows = trailing start, columns = trailing distance', head: ['start \\ distance', ...ax.DIST.map(atr)], rows}); });
  tableCard('#s1tables', {title: 'Settings positive in all three splits, ranked by the weakest split', sub: 'nb = one-step neighbours also positive in all splits', head: ['break-even', 'trail start', 'distance', 'trades', 'net $', 'PF', 'max DD $', 'DEV net / R', 'VAL net / R', 'OOS net / R', 'weakest R', 'nb'], rows: s1.top.map(r => [r.be ? atr(r.be) : 'off', atr(r.start), atr(r.dist), r.trades, r.net, r.pf, r.dd, `${fmt$(r.DEV[0])} / ${fmtN(r.DEV[1], 3)}`, `${fmt$(r.VAL[0])} / ${fmtN(r.VAL[1], 3)}`, `${fmt$(r.OOS[0])} / ${fmtN(r.OOS[1], 3)}`, fmtN(r.min_expR, 3), `${r.nb_pos}/${r.nb_tot}`]), opts: {numCols: [3, 4, 5, 6]}});

  // stage 2
  const rows2 = Object.entries(D.stage2.rows); const b2 = D.stage2.base;
  const sorted2 = rows2.filter(([k, v]) => !k.startsWith('F27') && !k.startsWith('F28')).slice().sort((a, b) => b[1].net - a[1].net);
  card('#s2charts', {title: 'Six-year net with each filter, sorted', sub: 'orange = the chosen exit without any filter', height: 'xl', wide: true, build: t => barCfg(t, {labels: [['no filter (base)'], ...sorted2.map(([k]) => splitLabel(k.replace(/^F\d+ /, ''), 28))], datasets: [{label: 'net $', data: [b2.net, ...sorted2.map(([, v]) => v.net)], color: [t.s2, ...sorted2.map(() => t.s1)], notes: ['', ...sorted2.map(([, v]) => `PF ${fmtN(v.pf, 2)}, DD ${fmt$(v.dd)}, ${v.trades} trades`)]}], horizontal: true}), table: {head: ['filter', 'trades', 'net $', 'PF', 'max DD $'], rows: [['no filter (base)', b2.trades, b2.net, b2.pf, b2.dd], ...sorted2.map(([k, v]) => [k, v.trades, v.net, v.pf, v.dd])]}});
  const sc2 = Math.max(0.05, ...rows2.map(([, v]) => Math.max(Math.abs((v.dev ?? 0) - b2.DEV[1]), Math.abs((v.val ?? 0) - b2.VAL[1]), Math.abs((v.oos ?? 0) - b2.OOS[1]))));
  tableCard('#s2tables', {title: 'Filters one at a time on the chosen exit', sub: `Base: ${b2.trades} trades, net ${fmt$(b2.net)}, expectancy ${fmtN(b2.DEV[1], 3)} / ${fmtN(b2.VAL[1], 3)} / ${fmtN(b2.OOS[1], 3)} R in DEV / VAL / OOS`, head: ['filter', 'trades', 'net $', 'PF', 'max DD $', 'Δ exp R DEV', 'Δ VAL', 'Δ OOS', 'class'], rows: [['no filter (base)', b2.trades, b2.net, b2.pf, b2.dd, heatCell(0, sc2), heatCell(0, sc2), heatCell(0, sc2), pill('base')], ...rows2.map(([k, v]) => [k, v.trades, v.net, v.pf, v.dd, heatCell((v.dev ?? NaN) - b2.DEV[1], sc2), heatCell((v.val ?? NaN) - b2.VAL[1], sc2), heatCell((v.oos ?? NaN) - b2.OOS[1], sc2), pill(v.cls)])], opts: {numCols: [1, 2, 3, 4], baseRow: 0}});

  // stage 4 stops
  const s4 = Object.entries(D.stage4); const b4 = s4.find(([k]) => k.startsWith('A '))[1];
  const sc4 = Math.max(0.05, ...s4.map(([, v]) => Math.max(Math.abs((v.DEV[1] ?? 0) - b4.DEV[1]), Math.abs((v.VAL[1] ?? 0) - b4.VAL[1]), Math.abs((v.OOS[1] ?? 0) - b4.OOS[1]))));
  tableCard('#s4', {title: 'Stop variants on the chosen exit', head: ['stop', 'trades', 'median risk $', 'net $', 'PF', 'max DD $', 'Δ exp R DEV', 'Δ VAL', 'Δ OOS', 'class'], rows: s4.map(([k, v]) => [k, v.trades, v.median_risk, v.net, v.pf, v.dd, heatCell(v.cls === 'base' ? 0 : v.DEV[1] - b4.DEV[1], sc4), heatCell(v.cls === 'base' ? 0 : v.VAL[1] - b4.VAL[1], sc4), heatCell(v.cls === 'base' ? 0 : v.OOS[1] - b4.OOS[1], sc4), pill(v.cls)]), opts: {numCols: [1, 2, 3, 4, 5], baseRow: 0}});

  // stage 5 MA map
  const s5 = D.stage5; const fasts = [...new Set(Object.keys(s5).map(k => +k.split('/')[0]))].sort((a, b) => a - b); const trends = [...new Set(Object.keys(s5).map(k => +k.split('/')[1]))].sort((a, b) => a - b);
  const sc5 = Math.max(...Object.values(s5).map(v => Math.abs(v.net)));
  tableCard('#s5', {title: 'Six-year net by fast (rows) and trend (columns) SMA on the chosen exit', sub: 'bold = positive in all three splits; 18/200 is the row used', head: ['fast \\ trend', ...trends.map(String)], rows: fasts.map(f => [String(f), ...trends.map(tr => { const v = s5[`${f}/${tr}`]; const c = heatCell(v.net, sc5, 0); if (v.pos3) c.html = `<b>${c.html}</b>`; return c; })])});

  // stage 6
  const e6 = D.equity6; const e23 = D.equity23;
  card('#s6eq', {title: 'Cumulative profit 2020-2026, one-minute path', sub: 'Realistic costs, $ per 0.01 lot', height: 'tall', build: t => lineCfg(t, {labels: e6[CFGS[0]].t, datasets: CFGS.map((n, i) => ({label: n, data: e6[n].v, color: COLS[i]})), catLimit: 8}), table: {head: ['week', ...CFGS], rows: e6[CFGS[0]].t.map((d, i) => [d, ...CFGS.map(n => e6[n].v[i])])}});
  card('#s6eq', {title: 'Cumulative profit 2003-2026, hourly path', sub: 'H4 bars from H1 before Sep 2020: a regime check, not a precise number', height: 'tall', build: t => lineCfg(t, {labels: e23[CFGS[0]].t, datasets: CFGS.map((n, i) => ({label: n, data: e23[n].v, color: COLS[i]})), catLimit: 7}), table: {head: ['week', ...CFGS], rows: e23[CFGS[0]].t.map((d, i) => [d, ...CFGS.map(n => e23[n].v[i])])}});
  const years6 = [...new Set(CFGS.flatMap(n => Object.keys(D.stage6[n].by_year)))].sort();
  card('#s6year', {title: 'Net by year, 2020-2026', build: t => barCfg(t, {labels: years6, datasets: CFGS.map((n, i) => ({label: n, data: years6.map(y => D.stage6[n].by_year[y] ?? 0), color: COLS[i]}))}), table: {head: ['year', ...CFGS], rows: years6.map(y => [y, ...CFGS.map(n => D.stage6[n].by_year[y])])}});
  const years23 = [...new Set(CFGS.flatMap(n => Object.keys(D.stage6[n].h1path_2003_2026.by_year)))].sort();
  card('#s6year', {title: 'Net by year, 2003-2026 (hourly path)', build: t => barCfg(t, {labels: years23, datasets: CFGS.map((n, i) => ({label: n, data: years23.map(y => D.stage6[n].h1path_2003_2026.by_year[y] ?? 0), color: COLS[i]})), catLimit: 24}), table: {head: ['year', ...CFGS], rows: years23.map(y => [y, ...CFGS.map(n => D.stage6[n].h1path_2003_2026.by_year[y])])}});
  tableCard('#s6tables', {title: 'Robustness summary', head: ['configuration', 'trades', 'net $', 'PF', 'max DD $', 'win %', 'exp R', 'low cost $', 'stress $', 'worst ordering $', 'median stop $', '2023-26 net $', 'MC p(ruin) $200', 'MC p(ruin) 100x stop'], rows: CFGS.map(n => { const d = D.stage6[n]; const a = d.all; return [n, a.trades, a.net, a.pf, a.dd, a.win, a.expR, d.cost.A_low, d.cost.C_stress, d.worst_path, d.median_risk, d.window_2023_26[0], d.mc_200.bootstrap.p_ruin, d.mc_100x.bootstrap.p_ruin]; }), opts: {numCols: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], dec: {6: 3, 12: 3, 13: 3}}});
  tableCard('#s6tables', {title: 'Walk-forward folds: train / validate / test net $', head: ['configuration', 'fold 1 (test 2023-24)', 'fold 2 (test 2024-25)', 'fold 3 (test 2025-26)'], rows: CFGS.map(n => [n, ...D.stage6[n].folds.map(f => `${fmt$(f.train[0])} / ${fmt$(f.val[0])} / ${fmt$(f.test[0])}`)])});
  tableCard('#s6tables', {title: '2003-2026 on the hourly path', head: ['configuration', 'trades', 'net $', 'PF', 'max DD $', 'positive years', 'worst year $', '2003-2012 net / R', '2012-2020', '2020-2026', 'MC p(ruin) $200'], rows: CFGS.map(n => { const h = D.stage6[n].h1path_2003_2026; return [n, h.trades, h.net, h.pf, h.dd, h.pos_years, h.worst_year, ...['2003-2012', '2012-2020', '2020-2026'].map(w => `${fmt$(h.windows[w][0])} / ${fmtN(h.windows[w][1], 3)}`), h.mc_200.bootstrap.p_ruin]; }), opts: {numCols: [1, 2, 3, 4, 6, 10], dec: {10: 3}}});
  const SESS = ['Asia', 'London', 'London/NY', 'NewYork', 'Sydney'];
  tableCard('#s6tables', {title: 'By session of fill and by side, six years (net $ / trades)', head: ['configuration', ...SESS, 'longs', 'shorts'], rows: CFGS.map(n => { const d = D.stage6[n]; return [n, ...SESS.map(s => d.by_session[s] ? `${fmt$(d.by_session[s].net)} / ${d.by_session[s].trades}` : '-'), `${fmt$((d.by_side['1'] || {}).net)} / ${(d.by_side['1'] || {}).trades}`, `${fmt$((d.by_side['-1'] || {}).net)} / ${(d.by_side['-1'] || {}).trades}`]; })});
  const fd = D.stage6['Final (chosen exit + helpful filters)'];
  [['Final: ruin probability at $200', fmtPct(fd.mc_200.bootstrap.p_ruin, 1), `bootstrap of the six-year trade list; 95th-percentile drawdown ${fmt$(fd.mc_200.shuffle.dd_p95)}`], ['Final: ending balance from $200', fmt$(fd.mc_200.bootstrap.end_median), `median; p05 to p95 ${fmt$(fd.mc_200.bootstrap.end_p05)} to ${fmt$(fd.mc_200.bootstrap.end_p95)}`], ['Balance the 1% rule needs', fmt$(100 * fd.median_risk), `100 x the median stop (${fmt$(fd.median_risk)}); ruin probability there ${fmtPct(fd.mc_100x.bootstrap.p_ruin, 1)}`], ['Final: 2003-2026 ruin at $200', fmtPct(fd.h1path_2003_2026.mc_200.bootstrap.p_ruin, 1), 'with the 23-year trade list (17 flat years before 2020)']].forEach(([l, v, s]) => { const tile = el('div', 'tile'); tile.appendChild(txt('div', 'lab', l)); tile.appendChild(txt('div', 'val small', v)); tile.appendChild(txt('div', 'sub', s)); $('#mcTiles').appendChild(tile); });

  // sensitivity
  const labelOf = {be_trigger_pts: 'break-even trigger (ATR)', trail_start_pts: 'trailing start (ATR)', trail_dist_pts: 'trailing distance (ATR)', trail_step_pts: 'trailing step (ATR)', atr_period: 'ATR period', fast: 'fast SMA', trend: 'trend SMA'};
  Object.entries(D.sensitivity).forEach(([p, rows]) => { const isAtr = p.endsWith('_pts'); const lab = r => isAtr ? (r.value / 100).toFixed(2) : String(r.value); const mins = rows.map(r => Math.min(r.DEV ?? 9, r.VAL ?? 9, r.OOS ?? 9));
    card('#sensGrid', {title: labelOf[p] || p, height: 'short', build: t => lineCfg(t, {labels: rows.map(lab), datasets: [{label: 'all 6 years, exp R', data: rows.map(r => r.expR), color: t.s1, points: true, notes: rows.map(r => `net ${fmt$(r.net)}, PF ${fmtN(r.pf, 2)}, ${r.trades} trades`)}, {label: 'weakest split, exp R', data: mins, color: t.s2, points: true}], valFmt: v => fmtN(v, 2), catLimit: 8}), table: {head: [labelOf[p] || p, 'net $', 'PF', 'max DD $', 'exp R', 'DEV R', 'VAL R', 'OOS R', 'positive in all splits'], rows: rows.map(r => [lab(r), r.net, r.pf, r.dd, r.expR, r.DEV, r.VAL, r.OOS, r.pos3 ? 'yes' : 'no']), opts: {dec: {4: 3, 5: 3, 6: 3, 7: 3}}}}); });

  renderAll();
  const mq = window.matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
"""
page = "<title>SMA18 Gold H4 Final Config</title>\n" + fonts + "\n" + style + "\n" + body + '\n<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>\n<script>\nconst DATA = ' + json.dumps(D, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else (o.item() if hasattr(o, "item") else str(o))) + ";\n" + helpers + build + "\n</script>\n"
with open(os.path.join(HERE, "report3.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("report3.html written", len(page) // 1024, "KB")
