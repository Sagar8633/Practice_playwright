"""Build study2/report2.html (visual version of STUDY2_REPORT.md). Reuses the first report's CSS and chart helpers."""
import json, os, re, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import common as C

R = os.path.join(HERE, "results")
J = lambda n: json.load(open(os.path.join(R, n), encoding="utf-8")) if os.path.exists(os.path.join(R, n)) else {}
N = json.load(open(os.path.join(HERE, "narrative2.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "narrative2.json")) else {}
A = J("partA_baseline.json"); AL = J("partA_labs.json"); AW = J("partA_walkforward.json"); B = J("partB_baseline_sessions.json"); S = J("partB_sma.json")
TF6 = ["M1", "M5", "M15", "H1", "H4", "D1"]


def weekly(tr, start_balance=0.0, start=None, end=None):
    if len(tr) == 0: return {"t": [], "v": []}
    tr = tr.sort_values("time_out"); cum = (start_balance + tr["pnl"].cumsum()).to_numpy(); tout = tr["time_out"].to_numpy()
    grid = pd.date_range(pd.Timestamp(start) if start else tr["time_out"].min().normalize(), pd.Timestamp(end) if end else tr["time_out"].max(), freq="W")
    idx = np.searchsorted(tout, grid.to_numpy(), side="right") - 1
    vals = np.where(idx >= 0, cum[np.clip(idx, 0, None)], start_balance)
    return {"t": [d.strftime("%Y-%m-%d") for d in grid], "v": [round(float(x), 2) for x in vals]}


def lab_rows(d):
    rows = []
    for v, r in d["rows"].items():
        m = r["metrics"]
        rows.append({"name": v, "trades": m["ALL"]["trades"], "net": m["ALL"]["net_profit"], "pf": m["ALL"].get("profit_factor"), "dd": m["ALL"]["max_dd_usd"], "expR": m["ALL"].get("expectancy_r"), "dev": m["DEV"].get("expectancy_r"), "val": m["VAL"].get("expectancy_r"), "oos": m["OOS"].get("expectancy_r"), "cls": r["class"], "risk": r.get("median_risk_usd"), "slhit": m["ALL"].get("sl_hit_rate"), "giveback": m["ALL"].get("giveback_avg"), "p2l": m["ALL"].get("profit_to_loss_2usd")})
    b = d["base"]
    return {"rows": rows, "base": {"trades": b["ALL"]["trades"], "net": b["ALL"]["net_profit"], "pf": b["ALL"].get("profit_factor"), "dev": b["DEV"].get("expectancy_r"), "val": b["VAL"].get("expectancy_r"), "oos": b["OOS"].get("expectancy_r"), "expR": b["ALL"].get("expectancy_r")}}


D = {"narrative": N, "partA": {}, "labs": {}, "wf": {}, "b": {"baseline": {}, "equity": {}, "sessions": {}, "sfilters": {}}, "sma": {}}
for tf in ("H1", "H4"):
    a = A[tf]; tr = pd.read_csv(os.path.join(R, f"trades_{tf}_6y_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    D["partA"][tf] = {"cost": {c: a["baseline"]["strategy"][c]["net_profit"] for c in ("A_low", "B_real", "C_stress")}, "worst": a["baseline"]["strategy"]["B_real_worst"]["net_profit"],
                      "m": {k: a["baseline"]["strategy"]["B_real"].get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "win_rate", "expectancy_r", "giveback_avg", "profit_to_loss_2usd", "exit_mix", "avg_hold_min")},
                      "splits": {k: (a["baseline"]["strategy"]["B_real"][k]["net_profit"], a["baseline"]["strategy"]["B_real"][k].get("expectancy_r")) for k in ("DEV", "VAL", "OOS")},
                      "views": {v: {k: a["baseline"][v]["B_real"].get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "end_balance", "blocked_sl_pct", "ruin")} for v in ("strategy", "ea_200", "ea_200_nofilt")},
                      "equity": weekly(tr, 0.0, C.DATA_START, C.DATA_END), "byYear": a["by_year"], "ta": a.get("trade_analysis", {})}
    D["labs"][tf] = {k: lab_rows(AL[tf][k]) for k in ("filters", "sl", "exits")}
    D["wf"][tf] = AW[tf]
for tf in TF6:
    m = B["baseline"][tf]["strategy"]["B_real"]
    D["b"]["baseline"][tf] = {"m": {k: m.get(k) for k in ("trades", "net_profit", "profit_factor", "max_dd_usd", "win_rate", "expectancy_r", "giveback_avg", "profit_to_loss_2usd")}, "splits": {k: (m["splits"][k]["net_profit"], m["splits"][k].get("expectancy_r"), m["splits"][k]["trades"]) for k in ("IS", "OOS")}, "by_year": m["by_year"],
                              "cost": {c: B["baseline"][tf]["strategy"][c]["net_profit"] for c in ("A_low", "B_real", "C_stress")}, "views": {v: {k: B["baseline"][tf][v]["B_real"].get(k) for k in ("trades", "net_profit", "end_balance", "blocked_sl_pct", "ruin")} for v in ("ea_200", "ea_200_nofilt")}}
    tr = pd.read_csv(os.path.join(R, f"trades_{tf}_2023_26_strategy_B_real.csv"), parse_dates=["time_in", "time_out"])
    D["b"]["equity"][tf] = weekly(tr, 0.0, "2023-01-01", "2026-09-26")
    s = B["sessions"][tf]
    D["b"]["sessions"][tf] = {"by_session": s["by_session"], "by_hour": {str(k): v for k, v in s["by_hour"].items()}, "by_weekday": {str(k): v for k, v in s["by_weekday"].items()}, "ea": s["ea_sessions_overlapping"], "by_side": {str(k): v for k, v in s["by_side"].items()}}
    D["b"]["sfilters"][tf] = {k: {"trades": v["trades"], "net": v["net_profit"], "pf": v.get("profit_factor"), "dd": v["max_dd_usd"], "expR": v.get("expectancy_r"), "IS": v["splits"]["IS"]["net_profit"], "OOS": v["splits"]["OOS"]["net_profit"], "OOS_expR": v["splits"]["OOS"].get("expectancy_r")} for k, v in B["session_filters"][tf].items()}
    sm = S[tf]
    ent = {"fast": list(sm["fast"].values()), "trend": [{"key": k, **v} for k, v in sm["trend"].items()], "pairs": [{"key": k, **v} for k, v in sm["pairs"].items()], "fast_improved": list(sm.get("fast_improved", {}).values()), "best_fast_IS": sm.get("best_fast_IS"), "recommended": sm.get("recommended", [])}
    eq = {"18/200": D["b"]["equity"][tf]}
    pb = os.path.join(R, f"trades_{tf}_2023_26_bestsma.csv")
    if os.path.exists(pb) and ent["recommended"]:
        tb = pd.read_csv(pb, parse_dates=["time_out"]); r0 = ent["recommended"][0]
        eq[f"{r0['fast']}/{r0['trend']} (top ranked)"] = weekly(tb, 0.0, "2023-01-01", "2026-09-26")
    ent["equity"] = eq
    D["sma"][tf] = ent

# ------------------------------------------------------------------ compose the page from the first template's CSS + JS helpers
t1 = open(os.path.join(ROOT, "report_template.html"), encoding="utf-8").read()
style = t1[t1.index("<style>"): t1.index("</style>") + len("</style>")]
helpers = t1[t1.index('const TFS = ["M1","M5","M15","D1"];'): t1.index("// ------------------------------------------------------------------ build the page")]
fonts = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">'


def para(key):
    txt = N.get(key, "")
    return "".join(f"<p>{p.strip()}</p>" for p in txt.split("\n\n") if p.strip())


body = f"""
<div class="wrap">
<header class="top">
  <div class="eyebrow">SimpleSMA18Bot v1.00 on XAUUSD · study 2 · 26 Sep 2026</div>
  <h1>H1 and H4, the trading sessions, the last three years, and which SMA</h1>
  <p class="lead">A second, separate study with the same engine, data and costs as the first report. Part one runs H1 and H4 through the same pipeline (six years, filters, stops, exits, walk-forward). Part two narrows to 2023 to 2026 for all six timeframes: profit by session, the EA's session filter, and a staged sweep of the fast and trend SMAs. Money is per 0.01 lot (1 oz).</p>
  <div class="chips" id="chips"></div>
</header>
<nav class="toc" aria-label="Sections"><ul>
<li><a href="#summary">Summary</a></li><li><a href="#h1h4">H1 and H4</a></li><li><a href="#labs">Filters, stops, exits</a></li><li><a href="#wf">Walk-forward</a></li><li><a href="#window">2023-2026</a></li><li><a href="#sessions">Sessions</a></li><li><a href="#sfilters">Session filter</a></li><li><a href="#sma">SMA sweep</a></li><li><a href="#reco">Recommendation</a></li>
</ul></nav>
<main>
<section id="summary"><div class="sec-head"><div class="eyebrow">The answer first</div><h2>What changed and what did not</h2></div><div class="tiles" id="sumTiles"></div>{para("summary")}</section>
<section id="h1h4"><div class="sec-head"><div class="eyebrow">Part one · H1 and H4, Sep 2020 to Sep 2026</div><h2>H1 and H4 through the first study's pipeline</h2></div>{para("partA")}
  <div class="grid-2" id="aCost"></div><div class="grid-2" id="aEquity"></div><div class="grid-2" id="aYear"></div><div id="aViews"></div><div class="grid-2" id="aTA"></div><div class="grid-2" id="aLoss"></div></section>
<section id="labs"><div class="sec-head"><div class="eyebrow">Part one · the labs</div><h2>Filters, stops and exits on H1 and H4</h2><p class="lead">Cells: change in expectancy per unit of risk versus the untouched EA in each split (blue better, red worse). Orange bar = the shipped exit stack.</p></div><div class="grid-2" id="aExitBars"></div><div id="aLabTables"></div></section>
<section id="wf"><div class="sec-head"><div class="eyebrow">Part one · robustness</div><h2>Walk-forward on H1 and H4</h2></div><div class="grid-2" id="wfTop"></div><div id="wfFolds"></div><div class="grid" id="wfSens"></div><div class="tiles" id="wfTiles"></div></section>
<section id="window"><div class="sec-head"><div class="eyebrow">Part two · 1 Jan 2023 to 26 Sep 2026</div><h2>The last three years, all six timeframes</h2><p class="lead">In-sample = 2023 and 2024, out-of-sample = 2025 to Sep 2026. Untouched EA, strategy view, realistic costs.</p></div>{para("partB")}
  <div class="grid-2" id="bTop"></div><div class="grid-3" id="bEquity"></div><div id="bViews"></div></section>
<section id="sessions"><div class="sec-head"><div class="eyebrow">Part two · sessions</div><h2>Profit and loss by session, hour and weekday</h2><p class="lead">By the time the order filled, server time. Non-overlapping sessions: Asia 0-8, London 8-13, London/NY 13-17, New York 17-22, Sydney 22-24.</p></div>{para("sessions")}
  <div class="grid-3" id="sSess"></div><div class="grid-3" id="sHour"></div><div class="grid-3" id="sWeek"></div><div id="sEA"></div></section>
<section id="sfilters"><div class="sec-head"><div class="eyebrow">Part two · the EA's UseSessionFilter</div><h2>Switching the session filter on</h2><p class="lead">The filter blocks new setups outside the window (it acts at the signal bar, so on D1 it decides whether the 01:00 signal is allowed at all).</p></div>{para("session_filters")}
  <div class="grid-3" id="sfBars"></div><div id="sfTable"></div></section>
<section id="sma"><div class="sec-head"><div class="eyebrow">Part two · which SMA</div><h2>Fast SMA, trend SMA and the popular pairs</h2><p class="lead">The fast average also drives the MA exit and the pending-order cancel, so a change to it is a change to the whole strategy. Rule declared before running: a setting is a candidate only if expectancy per unit of risk is positive both in 2023-24 and in 2025-26 with enough trades; ranking by the weaker of the two.</p></div>{para("sma")}
  <div class="grid-2" id="smaFast"></div><div class="grid-2" id="smaImproved"></div><div class="grid-2" id="smaEquity"></div><div id="smaTables"></div></section>
<section id="reco"><div class="sec-head"><div class="eyebrow">Recommendation</div><h2>What to use, and what not to</h2></div>{para("recommendation")}
  <p class="note">Files: <code>study2/STUDY2_REPORT.md</code>, <code>study2/results/*.json</code>, trade lists <code>study2/results/trades_*.csv</code>, every run in <code>results/experiment_log.csv</code> (phases S2A-* and S2B-*).</p></section>
</main>
</div>
"""

build = r"""
(function build() {
  const D = DATA; const t0 = T(); const TF6 = ["M1","M5","M15","H1","H4","D1"]; const H = ["H1","H4"];
  $('#chips').append(...['Part one: Sep 2020 to Sep 2026, DEV / VAL / OOS as in study 1', 'Part two: 1 Jan 2023 to 26 Sep 2026, IS 2023-24 / OOS 2025-26', 'Fixed 0.01 lot, XM spread by hour, 10-pt slippage, swap'].map(s => txt('span', 'chip', s)));
  // summary tiles: H1/H4 six years + all six 2023-26
  H.forEach(tf => { const m = D.partA[tf].m; const tile = el('div', 'tile'); tile.appendChild(el('div', 'lab', `<b style="font-size:15px;color:var(--ink)">${tf}</b> · six years, net per 0.01 lot`)); tile.appendChild(txt('div', 'val', fmt$(m.net_profit))); tile.appendChild(el('div', 'sub', `PF <b>${fmtN(m.profit_factor, 2)}</b> · max DD <b>${fmt$(m.max_dd_usd)}</b> · <b>${fmtN(m.trades)}</b> trades · DEV/VAL/OOS ${fmt$(D.partA[tf].splits.DEV[0])} / ${fmt$(D.partA[tf].splits.VAL[0])} / ${fmt$(D.partA[tf].splits.OOS[0])}`)); $('#sumTiles').appendChild(tile); });
  TF6.forEach(tf => { const b = D.b.baseline[tf]; const tile = el('div', 'tile'); tile.appendChild(el('div', 'lab', `<b style="font-size:15px;color:var(--ink)">${tf}</b> · 2023 to 2026`)); tile.appendChild(txt('div', 'val small', fmt$(b.m.net_profit))); tile.appendChild(el('div', 'sub', `PF <b>${fmtN(b.m.profit_factor, 2)}</b> · IS ${fmt$(b.splits.IS[0])} · OOS ${fmt$(b.splits.OOS[0])} · ${fmtN(b.m.trades)} trades`)); $('#sumTiles').appendChild(tile); });

  // Part A
  H.forEach(tf => { const c = D.partA[tf].cost; card('#aCost', {title: `${tf}: net by cost scenario, 2020-2026`, height: 'short', build: t => barCfg(t, {labels: ['Low cost', 'Realistic', 'Stress'], datasets: [{label: 'net', data: [c.A_low, c.B_real, c.C_stress], color: t.s1}]}), table: {head: ['scenario', 'net $'], rows: [['Low cost', c.A_low], ['Realistic', c.B_real], ['Stress', c.C_stress]]}}); });
  H.forEach(tf => { const e = D.partA[tf].equity; card('#aEquity', {title: `${tf}: cumulative profit, realistic costs`, sub: `Worst intrabar ordering: ${fmt$(D.partA[tf].worst)}`, build: t => lineCfg(t, {labels: e.t, datasets: [{label: 'cumulative $', data: e.v, color: t.s1}], area: true}), table: {head: ['week', 'cumulative $'], rows: e.t.map((d, i) => [d, e.v[i]])}}); });
  H.forEach(tf => { const y = D.partA[tf].byYear; const ys = Object.keys(y); card('#aYear', {title: `${tf}: net by year`, height: 'short', build: t => barCfg(t, {labels: ys, datasets: [{label: 'net', data: ys.map(k => y[k].net), color: t.s1, notes: ys.map(k => `PF ${fmtN(y[k].pf, 2)}, ${y[k].trades} trades`)}]}), table: {head: ['year', 'net $', 'PF', 'trades'], rows: ys.map(k => [k, y[k].net, y[k].pf, y[k].trades])}}); });
  tableCard('#aViews', {title: 'H1 and H4 on $200 (realistic costs, six years)', head: ['TF', 'view', 'trades', 'net $', 'PF', 'max DD $', 'end balance $', 'blocked by 1%', 'ruined'], rows: H.flatMap(tf => Object.entries(D.partA[tf].views).map(([v, m]) => [tf, v, m.trades, m.net_profit, m.profit_factor, m.max_dd_usd, m.end_balance, m.blocked_sl_pct, m.ruin ? 'yes' : 'no'])), opts: {numCols: [2, 3, 4, 5, 6, 7]}});
  H.forEach(tf => { const ta = D.partA[tf].ta; if (!ta.by_exit) return; const rows = Object.entries(ta.by_exit).map(([k, v]) => [k, v.trades, v.net, v.avg_mfe, v.giveback_avg, v.p2l_2usd]); tableCard('#aTA', {title: `${tf}: giveback by exit`, sub: `Summed best profit ${fmt$(ta.overall.total_mfe)} vs realized ${fmt$(ta.overall.realized)}; ${ta.p2l['2usd'].trades} profitable-to-loss trades (>$2) = ${fmtPct(ta.p2l['2usd'].share_of_losers)} of losers`, head: ['exit', 'trades', 'net $', 'avg best $', 'avg giveback $', 'P->L >$2'], rows, opts: {numCols: [1, 2, 3, 4, 5]}}); });
  H.forEach(tf => { const ta = D.partA[tf].ta; if (!ta.loss_categories) return; const L = Object.entries(ta.loss_categories).map(([k, v]) => ({cat: k, ...v})).sort((a, b) => b.share - a.share); card('#aLoss', {title: `${tf}: share of total loss by category`, height: 'tall', build: t => barCfg(t, {labels: L.map(x => splitLabel(x.cat.replace(/^\d+ /, ''), 20)), datasets: [{label: 'share of loss', data: L.map(x => x.share), color: t.s1, notes: L.map(x => `${x.trades} trades, ${fmt$(x.loss)}`)}], horizontal: true, valFmt: v => fmtN(v) + '%'}), table: {head: ['category', 'trades', 'loss $', 'share %'], rows: L.map(x => [x.cat, x.trades, x.loss, x.share])}}); });
  function labTable(host, tf, lab, title, sub, extra) {
    const b = lab.base; const scale = Math.max(0.05, ...lab.rows.map(r => Math.max(Math.abs((r.dev ?? 0) - b.dev), Math.abs((r.val ?? 0) - b.val), Math.abs((r.oos ?? 0) - b.oos))));
    const head = ['variant', 'trades', 'net $', 'PF', ...(extra ? extra.head : []), 'Δ exp R DEV', 'Δ VAL', 'Δ OOS', 'class']; const rows = []; let baseRow = null;
    if (!lab.rows.some(r => r.cls === 'base')) { baseRow = 0; rows.push(['untouched EA', b.trades, b.net, b.pf, ...(extra ? extra.base : []), heatCell(0, scale), heatCell(0, scale), heatCell(0, scale), pill('base')]); }
    lab.rows.forEach(r => { if (r.cls === 'base') baseRow = rows.length; rows.push([r.name, r.trades, r.net, r.pf, ...(extra ? extra.row(r) : []), heatCell(r.cls === 'base' ? 0 : (r.dev ?? NaN) - b.dev, scale), heatCell(r.cls === 'base' ? 0 : (r.val ?? NaN) - b.val, scale), heatCell(r.cls === 'base' ? 0 : (r.oos ?? NaN) - b.oos, scale), pill(r.cls)]); });
    tableCard(host, {title, sub, head, rows, opts: {numCols: [1, 2, 3], baseRow, dec: {3: 2}}});
  }
  H.forEach(tf => { const x = D.labs[tf].exits; const sorted = x.rows.slice().sort((a, b) => b.net - a.net); card('#aExitBars', {title: `${tf}: net $ by exit stack, six years`, sub: 'Sorted; orange = shipped EA stack (E01)', height: 'xl', build: t => barCfg(t, {labels: sorted.map(r => splitLabel(r.name.replace(/^E\d+ /, ''), 30)), datasets: [{label: 'net $', data: sorted.map(r => r.net), color: sorted.map(r => r.name.startsWith('E01') ? t.s2 : t.s1), notes: sorted.map(r => `PF ${fmtN(r.pf, 2)}, DD ${fmt$(r.dd)}, ${fmtN(r.trades)} trades`)}], horizontal: true}), table: {head: ['exit stack', 'trades', 'net $', 'PF', 'max DD $'], rows: sorted.map(r => [r.name, r.trades, r.net, r.pf, r.dd])}}); });
  H.forEach(tf => { const f = D.labs[tf].filters; labTable('#aLabTables', tf, f, `${tf}: entry filters one at a time`, `Base: ${fmtN(f.base.trades)} trades, net ${fmt$(f.base.net)}, expectancy ${fmtN(f.base.dev, 3)} / ${fmtN(f.base.val, 3)} / ${fmtN(f.base.oos, 3)} R`); labTable('#aLabTables', tf, D.labs[tf].sl, `${tf}: stop-loss variants`, '', {head: ['median risk $', 'SL hit %'], base: ['', ''], row: r => [r.risk, r.slhit]}); labTable('#aLabTables', tf, D.labs[tf].exits, `${tf}: exit stacks`, '', {head: ['giveback avg $', 'P->L >$2'], base: ['', ''], row: r => [r.giveback, r.p2l]}); });

  // walk-forward
  card('#wfTop', {title: 'Share of grid configurations that are net positive, by split', build: t => barCfg(t, {labels: H, datasets: [{label: 'DEV 2020-23', data: H.map(tf => 100 * D.wf[tf].audit.share_dev), color: t.s1}, {label: 'VAL 2023-24', data: H.map(tf => 100 * D.wf[tf].audit.share_val), color: t.s2}, {label: 'OOS 2025-26', data: H.map(tf => 100 * D.wf[tf].audit.share_oos), color: t.s3}], valFmt: v => fmtN(v) + '%'}), table: {head: ['TF', 'configs', 'positive DEV', 'positive VAL', 'positive OOS', 'positive in all three'], rows: H.map(tf => [tf, D.wf[tf].audit.configs, D.wf[tf].audit.share_dev, D.wf[tf].audit.share_val, D.wf[tf].audit.share_oos, D.wf[tf].audit.pos3])}});
  tableCard('#wfTop', {title: 'Configurations positive in DEV, VAL and OOS (top by OOS expectancy)', head: ['TF', 'config', 'DEV R', 'VAL R', 'OOS R', 'OOS net $', 'all net $', 'all PF', 'all DD $', 'trades'], rows: H.flatMap(tf => D.wf[tf].audit.robust.slice(0, 6).map(r => [tf, r.config, r.dev_expR, r.val_expR, r.oos_expR, r.oos_net, r.all_net, r.all_pf, r.all_dd, r.all_trades])), opts: {numCols: [2, 3, 4, 5, 6, 7, 8, 9], dec: {2: 3, 3: 3, 4: 3}}});
  H.forEach(tf => { tableCard('#wfFolds', {title: `${tf}: three yearly folds`, head: ['fold', 'train', 'test', 'train-best', 'train R', 'val R', 'test R', 'passes val', 'selected (val-gated)', 'selected test net $', 'untouched EA test net $', 'share positive in test'], rows: D.wf[tf].folds.map(x => [x.fold, {html: `${x.train[0].slice(0, 7)} to ${x.train[1].slice(0, 7)}`, style: 'white-space:nowrap'}, {html: `${x.test[0].slice(0, 7)} to ${x.test[1].slice(0, 7)}`, style: 'white-space:nowrap'}, x.train_best, x.train_best_R ? x.train_best_R[0] : null, x.train_best_R ? x.train_best_R[1] : null, x.train_best_R ? x.train_best_R[2] : null, x.passes_val ? 'yes' : 'no', x.selected || 'none passes', x.selected_test ? x.selected_test[1] : null, x.ea_test_net, x.share_positive_test]), opts: {numCols: [4, 5, 6, 9, 10, 11], dec: {4: 3, 5: 3, 6: 3}}}); });
  H.forEach(tf => { const c = D.wf[tf].candidate; if (!c) return; Object.entries(c.sensitivity).forEach(([p, rows]) => { card('#wfSens', {title: `${tf} candidate: ${p}`, sub: c.config, height: 'short', build: t => lineCfg(t, {labels: rows.map(r => String(r.value)), datasets: [{label: 'all 6 years', data: rows.map(r => r.all_expR), color: t.s1, points: true, notes: rows.map(r => `net ${fmt$(r.all_net)}, ${r.trades} trades`)}, {label: 'OOS 2025-26', data: rows.map(r => r.oos_expR), color: t.s2, points: true}], valFmt: v => fmtN(v, 2), catLimit: 6}), table: {head: [p, 'all expR', 'all net $', 'OOS expR', 'trades'], rows: rows.map(r => [r.value, r.all_expR, r.all_net, r.oos_expR, r.trades])}}); });
    const mc = c.mc_200; [[`${tf} candidate: ruin probability at $200`, fmtPct(mc.bootstrap.p_ruin, 1), `${c.config}; shuffle ${fmtPct(mc.shuffle.p_ruin, 1)}; DD p95 ${fmt$(mc.shuffle.dd_p95)}`], [`${tf} candidate: ending balance from $200`, fmt$(mc.bootstrap.end_median), `median; p05 to p95 ${fmt$(mc.bootstrap.end_p05)} to ${fmt$(mc.bootstrap.end_p95)}; median stop ${fmt$(c.median_risk)}`]].forEach(([l, v, s]) => { const tile = el('div', 'tile'); tile.appendChild(txt('div', 'lab', l)); tile.appendChild(txt('div', 'val small', v)); tile.appendChild(txt('div', 'sub', s)); $('#wfTiles').appendChild(tile); }); });

  // Part B window
  card('#bTop', {title: 'Net 2023-2026 by timeframe, in-sample vs out-of-sample', sub: 'IS = 2023-24, OOS = 2025 to Sep 2026; untouched EA, realistic costs', build: t => barCfg(t, {labels: TF6, datasets: [{label: 'IS 2023-24', data: TF6.map(tf => D.b.baseline[tf].splits.IS[0]), color: t.s1, notes: TF6.map(tf => `${D.b.baseline[tf].splits.IS[2]} trades, exp ${fmtN(D.b.baseline[tf].splits.IS[1], 3)} R`)}, {label: 'OOS 2025-26', data: TF6.map(tf => D.b.baseline[tf].splits.OOS[0]), color: t.s2, notes: TF6.map(tf => `${D.b.baseline[tf].splits.OOS[2]} trades, exp ${fmtN(D.b.baseline[tf].splits.OOS[1], 3)} R`)}]}), table: {head: ['TF', 'IS net $', 'IS exp R', 'IS trades', 'OOS net $', 'OOS exp R', 'OOS trades'], rows: TF6.map(tf => [tf, D.b.baseline[tf].splits.IS[0], D.b.baseline[tf].splits.IS[1], D.b.baseline[tf].splits.IS[2], D.b.baseline[tf].splits.OOS[0], D.b.baseline[tf].splits.OOS[1], D.b.baseline[tf].splits.OOS[2]])}});
  card('#bTop', {title: 'Net by year, 2023-2026', build: t => barCfg(t, {labels: ['2023', '2024', '2025', '2026'], datasets: TF6.slice(2).map((tf, i) => ({label: tf, data: ['2023', '2024', '2025', '2026'].map(y => (D.b.baseline[tf].by_year[y] || {}).net ?? 0), color: [t.s1, t.s2, t.s3, t.gray][i]}))}), table: {head: ['TF', '2023', '2024', '2025', '2026'], rows: TF6.map(tf => [tf, ...['2023', '2024', '2025', '2026'].map(y => (D.b.baseline[tf].by_year[y] || {}).net)])}});
  TF6.forEach(tf => { const e = D.b.equity[tf]; card('#bEquity', {title: `${tf}: cumulative profit 2023-2026`, height: 'short', build: t => lineCfg(t, {labels: e.t, datasets: [{label: 'cumulative $', data: e.v, color: t.s1}], area: true, catLimit: 5}), table: {head: ['week', 'cumulative $'], rows: e.t.map((d, i) => [d, e.v[i]])}}); });
  tableCard('#bViews', {title: 'The $200 account, 2023-2026 (realistic costs)', sub: 'As shipped (1% gate on) and with the gate off', head: ['TF', 'gate on: trades', 'blocked', 'net $', 'end $', 'gate off: trades', 'net $', 'end $', 'ruined'], rows: TF6.map(tf => { const a = D.b.baseline[tf].views.ea_200, b = D.b.baseline[tf].views.ea_200_nofilt; return [tf, a.trades, a.blocked_sl_pct, a.net_profit, a.end_balance, b.trades, b.net_profit, b.end_balance, b.ruin ? 'yes' : 'no']; }), opts: {numCols: [1, 2, 3, 4, 5, 6, 7]}});

  // sessions
  const SESS = ['Asia', 'London', 'London/NY', 'NewYork', 'Sydney'];
  TF6.forEach(tf => { const s = D.b.sessions[tf].by_session; card('#sSess', {title: `${tf}: net by session of fill`, height: 'short', build: t => barCfg(t, {labels: SESS, datasets: [{label: 'net $', data: SESS.map(k => (s[k] || {}).net ?? 0), color: t.s1, notes: SESS.map(k => s[k] ? `${s[k].trades} trades, PF ${fmtN(s[k].pf, 2)}, win ${fmtN(s[k].win_rate, 1)}%` : 'no trades')}]}), table: {head: ['session', 'trades', 'net $', 'PF', 'win %', 'exp $', 'avg giveback $', 'P->L >$2'], rows: SESS.map(k => [k, ...(s[k] ? [s[k].trades, s[k].net, s[k].pf, s[k].win_rate, s[k].expectancy, s[k].giveback_avg, s[k].p2l_2usd] : [0, 0, null, null, null, null, null])])}}); });
  TF6.forEach(tf => { const h = D.b.sessions[tf].by_hour; const hs = [...Array(24).keys()]; card('#sHour', {title: `${tf}: net by hour of fill`, height: 'short', build: t => barCfg(t, {labels: hs.map(String), datasets: [{label: 'net $', data: hs.map(k => (h[String(k)] || {}).net ?? 0), color: t.s1, notes: hs.map(k => h[String(k)] ? `${h[String(k)].trades} trades` : '')}], catLimit: 24}), table: {head: ['hour', 'trades', 'net $', 'PF'], rows: hs.map(k => [k, (h[String(k)] || {}).trades ?? 0, (h[String(k)] || {}).net ?? 0, (h[String(k)] || {}).pf])}}); });
  const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  TF6.forEach(tf => { const w = D.b.sessions[tf].by_weekday; card('#sWeek', {title: `${tf}: net by weekday of fill`, height: 'short', build: t => barCfg(t, {labels: WD, datasets: [{label: 'net $', data: WD.map((_, i) => (w[String(i)] || {}).net ?? 0), color: t.s1, notes: WD.map((_, i) => w[String(i)] ? `${w[String(i)].trades} trades, PF ${fmtN(w[String(i)].pf, 2)}` : '')}]}), table: {head: ['weekday', 'trades', 'net $', 'PF'], rows: WD.map((d, i) => [d, (w[String(i)] || {}).trades ?? 0, (w[String(i)] || {}).net ?? 0, (w[String(i)] || {}).pf])}}); });
  tableCard('#sEA', {title: "The EA's own overlapping session windows (a 14:00 fill counts in both London and New York)", head: ['TF', 'Sydney 22-07', 'Tokyo 0-9', 'London 8-17', 'New York 13-22'], rows: TF6.map(tf => [tf, ...['Sydney 22-07', 'Tokyo 0-9', 'London 8-17', 'New York 13-22'].map(k => { const v = D.b.sessions[tf].ea[k]; return v ? `${fmt$(v.net)} (${v.trades} tr, PF ${fmtN(v.pf, 2)})` : '-'; })])});

  // session filters
  TF6.forEach(tf => { const sf = D.b.sfilters[tf]; const keys = Object.keys(sf); card('#sfBars', {title: `${tf}: net 2023-2026 with each session filter`, sub: 'first bar = filter off', height: 'tall', build: t => barCfg(t, {labels: keys.map(k => splitLabel(k, 16)), datasets: [{label: 'net $', data: keys.map(k => sf[k].net), color: keys.map(k => k.startsWith('BASE') ? t.s2 : t.s1), notes: keys.map(k => `${sf[k].trades} trades, PF ${fmtN(sf[k].pf, 2)}, IS ${fmt$(sf[k].IS)}, OOS ${fmt$(sf[k].OOS)}`)}], horizontal: true}), table: {head: ['filter', 'trades', 'net $', 'PF', 'max DD $', 'IS net $', 'OOS net $', 'OOS exp R'], rows: keys.map(k => [k, sf[k].trades, sf[k].net, sf[k].pf, sf[k].dd, sf[k].IS, sf[k].OOS, sf[k].OOS_expR])}}); });
  tableCard('#sfTable', {title: 'Session filter results, all timeframes', head: ['TF', 'filter', 'trades', 'net $', 'PF', 'max DD $', 'exp R', 'IS net $', 'OOS net $', 'OOS exp R'], rows: TF6.flatMap(tf => Object.entries(D.b.sfilters[tf]).map(([k, v]) => [tf, k, v.trades, v.net, v.pf, v.dd, v.expR, v.IS, v.OOS, v.OOS_expR])), opts: {numCols: [2, 3, 4, 5, 6, 7, 8, 9], dec: {6: 3, 9: 3}}});

  // SMA
  TF6.forEach(tf => { const f = D.sma[tf].fast; card('#smaFast', {title: `${tf}: fast SMA sweep (trend 200), expectancy per unit of risk`, sub: `Best in-sample fast: ${D.sma[tf].best_fast_IS}; shipped value 18`, build: t => lineCfg(t, {labels: f.map(r => String(r.fast)), datasets: [{label: 'IS 2023-24', data: f.map(r => r.IS_expR), color: t.s1, points: true, notes: f.map(r => `IS net ${fmt$(r.IS_net)}, ${r.IS_trades} trades`)}, {label: 'OOS 2025-26', data: f.map(r => r.OOS_expR), color: t.s2, points: true, notes: f.map(r => `OOS net ${fmt$(r.OOS_net)}, ${r.OOS_trades} trades`)}], valFmt: v => fmtN(v, 2), catLimit: 13}), table: {head: ['fast', 'trades', 'net $', 'PF', 'max DD $', 'IS net $', 'IS exp R', 'OOS net $', 'OOS exp R'], rows: f.map(r => [r.fast, r.trades, r.net, r.pf, r.dd, r.IS_net, r.IS_expR, r.OOS_net, r.OOS_expR]), opts: {dec: {6: 3, 8: 3}}}}); });
  TF6.forEach(tf => { const f = D.sma[tf].fast_improved; if (!f || !f.length) return; card('#smaImproved', {title: `${tf}: fast SMA with the improved exit (ADX 25 + Chandelier from tick one)`, sub: 'Same sweep, the exit stack recommended by study 1 for D1', build: t => lineCfg(t, {labels: f.map(r => String(r.fast)), datasets: [{label: 'IS 2023-24', data: f.map(r => r.IS_expR), color: t.s1, points: true, notes: f.map(r => `IS net ${fmt$(r.IS_net)}`)}, {label: 'OOS 2025-26', data: f.map(r => r.OOS_expR), color: t.s2, points: true, notes: f.map(r => `OOS net ${fmt$(r.OOS_net)}`)}], valFmt: v => fmtN(v, 2), catLimit: 13}), table: {head: ['fast', 'trades', 'net $', 'PF', 'max DD $', 'IS net $', 'IS exp R', 'OOS net $', 'OOS exp R'], rows: f.map(r => [r.fast, r.trades, r.net, r.pf, r.dd, r.IS_net, r.IS_expR, r.OOS_net, r.OOS_expR]), opts: {dec: {6: 3, 8: 3}}}}); });
  TF6.forEach(tf => { const eq = D.sma[tf].equity; const names = Object.keys(eq); if (names.length < 2) return; card('#smaEquity', {title: `${tf}: shipped 18/200 vs the top-ranked SMA setting, 2023-2026`, sub: 'Cumulative $ per 0.01 lot, realistic costs', build: t => lineCfg(t, {labels: eq[names[0]].t, datasets: names.map((n, i) => ({label: n, data: eq[n].v, color: [t.s1, t.s2][i]})), catLimit: 6}), table: {head: ['week', ...names], rows: eq[names[0]].t.map((d, i) => [d, ...names.map(n => eq[n].v[i])])}}); });
  TF6.forEach(tf => { const s = D.sma[tf]; tableCard('#smaTables', {title: `${tf}: trend SMA sweep and popular pairs`, sub: `Trend sweep with fast 18 and fast ${s.best_fast_IS} (best IS)`, head: ['fast/trend', 'trades', 'net $', 'PF', 'max DD $', 'exp R', 'IS net $', 'IS exp R', 'OOS net $', 'OOS exp R'], rows: [...s.trend, ...s.pairs].map(r => [r.key, r.trades, r.net, r.pf, r.dd, r.expR, r.IS_net, r.IS_expR, r.OOS_net, r.OOS_expR]), opts: {numCols: [1, 2, 3, 4, 5, 6, 7, 8, 9], dec: {5: 3, 7: 3, 9: 3}}});
    const rec = s.recommended; tableCard('#smaTables', {title: `${tf}: settings positive in both IS and OOS (ranked by the weaker expectancy)`, sub: rec.length ? 'neighbours = adjacent fast values that are also positive out of sample' : 'none', head: ['fast/trend', 'trades', 'net $', 'PF', 'max DD $', 'IS exp R', 'OOS exp R', 'neighbours +OOS'], rows: rec.map(r => [`${r.fast}/${r.trend}`, r.trades, r.net, r.pf, r.dd, r.IS_expR, r.OOS_expR, r.neighbours_positive_OOS ? `${r.neighbours_positive_OOS[0]}/${r.neighbours_positive_OOS[1]}` : '-']), opts: {numCols: [1, 2, 3, 4, 5, 6], dec: {5: 3, 6: 3}}}); });

  renderAll();
  const mq = window.matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
"""

page = "<title>SMA18 Gold Sessions and SMA Sweep</title>\n" + fonts + "\n" + style + "\n" + body + '\n<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>\n<script>\nconst DATA = ' + json.dumps(D, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else (o.item() if hasattr(o, "item") else str(o))) + ";\n" + helpers + build + "\n</script>\n"
with open(os.path.join(HERE, "report2.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("report2.html written", len(page) // 1024, "KB")
