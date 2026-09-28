"""Backtest of SimpleSMA18Bot_H4_Final with its defaults ($200 start, tiered lots from BaseBalance 500, MaxLot 0.20,
partial exit with SKIP at the minimum lot, 1% gate off) and the graph page (report5.html)."""
import json, os, sys, time
from dataclasses import replace
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import sma18_engine as E
import common as C

OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
P = json.load(open(os.path.join(ROOT, "study3", "results", "study3.json")))["final"]["params"]
FINAL = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, sizing=3, base_balance=500.0, lots=0.01, max_lots=0.20, partial_enable=True, partial_min_mode=0, partial_per01=50.0, partial_min_usd=100.0, partial_pct=50.0, ploss_enable=True, ploss_per01=50.0, ploss_min_usd=100.0, ploss_pct=50.0, **C.COST["B_real"], **P)
PREV = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, sizing=2, base_balance=500.0, lots=0.01, max_lots=0.20, partial_enable=True, partial_min_mode=0, partial_profit_usd=100.0, partial_doubles=True, partial_pct=50.0, **C.COST["B_real"], **P)
FIXED = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, sizing=0, lots=0.01, **C.COST["B_real"], **P)


def weekly(tr, start_balance, start, end):
    tr = tr.sort_values("time_out"); cum = (start_balance + tr["pnl"].cumsum()).to_numpy(); tout = tr["time_out"].to_numpy()
    grid = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="W"); idx = np.searchsorted(tout, grid.to_numpy(), side="right") - 1
    vals = np.where(idx >= 0, cum[np.clip(idx, 0, None)], start_balance)
    return {"t": [d.strftime("%Y-%m-%d") for d in grid], "v": [round(float(x), 2) for x in vals]}


def acc(tr, st, sb=200.0):
    bal = sb + tr.pnl.cumsum(); peak = np.maximum.accumulate(np.concatenate([[sb], bal.to_numpy()])); dd = peak[1:] - bal.to_numpy(); ddp = dd / peak[1:]
    pos = tr[tr.reason != 14]
    d = {"end": round(st["final_balance"], 2), "growth": round(st["final_balance"] / sb, 2), "net": round(float(tr.pnl.sum()), 2), "dd_usd": round(float(dd.max()), 2), "dd_pct": round(100 * float(ddp.max()), 1), "max_lot": float(tr.lots.max()), "worst": round(float(tr.pnl.min()), 2), "best": round(float(tr.pnl.max()), 2),
         "positions": int(len(pos)), "partials": int((tr.reason == 14).sum()), "win_rate": round(100 * float((pos.pnl > 0).mean()), 1), "ruin": bool(st["ruin"]), "peak": round(float(peak.max()), 2),
         "pf": round(float(tr.loc[tr.pnl > 0, "pnl"].sum() / max(-tr.loc[tr.pnl < 0, "pnl"].sum(), 1e-9)), 2)}
    cl = ml = 0
    for x in pos.pnl: cl = cl + 1 if x < 0 else 0; ml = max(ml, cl)
    d["max_consec_losses"] = ml
    return d


R = {"windows": {}, "equity": {}, "by_year": {}, "start_years": {}, "lot_timeline": {}, "trades_last12m": []}
for w, (a, b) in {"6y": (C.DATA_START, C.DATA_END), "2023-26": ("2023-01-01", "2026-09-26"), "2025-01..2026-09": ("2025-01-01", "2026-09-26"), "last12m": ("2025-09-26", "2026-09-26")}.items():
    R["windows"][w] = {}; R["equity"][w] = {}
    for nm, kw in (("v2.10 defaults: linear lots (0.01 per $500), profit + loss partials", FINAL), ("v2.00 defaults: doubling lots, profit partial only", PREV), ("Fixed 0.01 lot (reference)", FIXED)):
        p = E.Params(start=a, end=b, start_balance=200.0, **kw); tr, st = E.run(p); R["windows"][w][nm] = acc(tr, st); R["equity"][w][nm] = weekly(tr, 200.0, a, b)
        tr.to_csv(os.path.join(OUT, f"final_trades_{w}_{'v21' if kw is FINAL else ('v20' if kw is PREV else 'fixed')}.csv"), index=False)
        if w == "6y":
            tr["year"] = tr.time_out.dt.year; R["by_year"][nm] = {int(y): round(float(v), 2) for y, v in tr.groupby("year").pnl.sum().items()}
            if kw is FINAL:
                R["lot_timeline"] = [{"lot": float(l), "first_used": str(tr[tr.lots >= l - 1e-9].time_in.min())[:10], "balance_then": round(float(200 + tr[tr.time_in < tr[tr.lots >= l - 1e-9].time_in.min()].pnl.sum()), 2)} for l in sorted(tr.lots.unique())]
        if w == "last12m" and kw is FINAL:
            R["trades_last12m"] = tr[["time_in", "time_out", "side", "lots", "entry", "isl", "exit", "exit_reason", "pnl", "balance"]].round(2).assign(time_in=lambda d: d.time_in.astype(str), time_out=lambda d: d.time_out.astype(str)).to_dict("records")
        C.log_experiment("S4-final-EA-defaults", f"{nm} [{w}]", p, E.metrics(tr, st, 200.0, E.months_between(a, b)), "B_real", w, exit_logic=C.exit_desc(p), conclusion=f"end {R['windows'][w][nm]['end']} DD {R['windows'][w][nm]['dd_pct']}% max lot {R['windows'][w][nm]['max_lot']}")
        print(w, nm[:30], R["windows"][w][nm], flush=True)
for y in (2021, 2022, 2023, 2024, 2025, 2026):
    p = E.Params(start=f"{y}-01-01", end=C.DATA_END, start_balance=200.0, **FINAL); tr, st = E.run(p); R["start_years"][y] = acc(tr, st)
print("start years", {y: (v["end"], v["dd_pct"], v["max_lot"], v["ruin"]) for y, v in R["start_years"].items()})
# Monte Carlo with compounding on the fixed-lot outcomes (base 500, cap 0.20)
trf = pd.read_csv(os.path.join(OUT, "final_trades_6y_fixed.csv")); pnl01 = trf.pnl.to_numpy(); rng = np.random.default_rng(11)


def compound(seq, base=500.0, start=200.0, base_lot=0.01, max_lot=0.20):
    bal = start; peak = start; dd = 0.0
    for x in seq:
        steps = max(1, int(bal // base)); lot = min(base_lot * steps, max_lot); bal += x * (lot / 0.01)
        if bal <= 0: return bal, dd, True
        peak = max(peak, bal); dd = max(dd, (peak - bal) / peak)
    return bal, dd, False


res = [compound(rng.permutation(pnl01)) for _ in range(5000)]; ends = np.array([r[0] for r in res]); dds = np.array([r[1] for r in res])
R["mc"] = {"p_ruin": round(float(np.mean([r[2] for r in res])), 4), "end_p05": round(float(np.percentile(ends, 5)), 2), "end_median": round(float(np.median(ends)), 2), "end_p95": round(float(np.percentile(ends, 95)), 2), "dd_median_pct": round(100 * float(np.median(dds)), 1), "dd_p95_pct": round(100 * float(np.percentile(dds, 95)), 1)}
print("MC", R["mc"])
json.dump(R, open(os.path.join(OUT, "final_backtest_v21.json"), "w"), indent=1, default=C._default)

# ------------------------------------------------------------------ graph page (same chart system as the earlier reports)
t1 = open(os.path.join(ROOT, "report_template.html"), encoding="utf-8").read()
style = t1[t1.index("<style>"): t1.index("</style>") + len("</style>")]
helpers = t1[t1.index('const TFS = ["M1","M5","M15","D1"];'): t1.index("// ------------------------------------------------------------------ build the page")]
fonts = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">'
w6 = R["windows"]["6y"]; fin = w6["v2.10 defaults: linear lots (0.01 per $500), profit + loss partials"]; fix = w6["Fixed 0.01 lot (reference)"]
body = f"""
<div class="wrap">
<header class="top"><div class="eyebrow">SimpleSMA18Bot_H4_Final v2.10 · defaults as compiled · 27 Sep 2026</div>
<h1>The final H4 EA v2.10 from $200: linear lots and two-sided partial exits</h1>
<p class="lead">SimpleSMA18Bot_H4_Final.mq5 with the settings it ships with: 18/200 SMA entry with the volume rule, swing stop, break-even at 2 ATR, trailing at 0.5 ATR from 5 ATR of profit, MA18 exit, lots from the balance (0.01 per $500 of balance: 0.01 below $1,000, 0.02 from $1,000, 0.03 from $1,500 ..., capped at 0.20), one profit-side partial exit per position (50% at $50 per 0.01 lot, floor $100) and one loss-side partial exit (50% at a $50-per-0.01-lot floating loss, floor $100), 1% gate off. The v2.00 doubling defaults and a fixed 0.01 lot are shown for comparison. Same data and costs as every earlier report; $200 account with margin and stop-out simulated.</p>
<div class="chips" id="chips"></div></header>
<main>
<section id="summary"><div class="sec-head"><div class="eyebrow">The answer first</div><h2>Six years, three windows, every start year</h2></div><div class="tiles" id="tiles"></div>
<p>{{N_SUMMARY}}</p></section>
<section id="charts"><div class="grid-2" id="eq"></div><div class="grid-2" id="year"></div></section>
<section id="tables"><div id="tbl"></div></section>
<section id="notes"><div class="sec-head"><div class="eyebrow">Inputs</div><h2>What is left in the EA</h2></div>
<p class="note">All filters kept and configurable (session, ADX, emergency loss, failed breakout, swing / Chandelier modes), defaults off. Entry: FastMAPeriod 18, TrendMAPeriod 200, VolumeMAPeriod 20, SwingStrength 2, EntryBufferPoints 0. Exit: EnableBreakEven true, ProtectionMode TRAILING from the first tick, UseATRScaledLevels true with ATRBreakEvenMult 2.0, ATRTrailStartMult 5.0, ATRTrailDistanceMult 0.5, ATRTrailStepMult 0.1, ATRPeriod 22, BreakEvenOffsetPoints 10. Sizing: UseDynamicLots true, LotMode LOT_LINEAR, BaseBalance 500, BaseLot 0.01, MaxLot 0.20. Partial exits: EnablePartialExit true (PartialProfitPerLot01 50, PartialProfitMinUSD 100, PartialExitPercent 50), EnablePartialLossExit true (PartialLossPerLot01 50, PartialLossMinUSD 100, PartialLossPercent 50), PartialAtMinLot PARTIAL_SKIP. Safety: UseSLPercentFilter false (MaximumSLPercent 1.0 if switched on). Files: <code>Vaibhav/SimpleSMA18Bot_H4_Final.mq5 / .ex5</code>, trade lists in <code>research/study4/results/final_trades_*.csv</code>.</p></section>
</main></div>
"""
summary = (f"Six years from $200 the defaults end at ${fin['end']:,.0f} ({fin['growth']}x) against ${fix['end']:,.0f} for a fixed 0.01 lot, with a maximum lot of {fin['max_lot']:.2f}, a worst single deal of ${fin['worst']:,.0f} and a {fin['dd_pct']}% peak-to-trough drawdown (the drawdown is the 2020-2023 stretch, before the account had grown). "
           "Started on 1 January of any year from 2021 to 2026 the account survives (" + ", ".join("%s: $%s" % (y, format(v["end"], ",.0f")) for y, v in R["start_years"].items()) + "). The last 12 months end at $" + format(R["windows"]["last12m"]["v2.10 defaults: linear lots (0.01 per $500), profit + loss partials"]["end"], ",.0f") + ". "
           f"Trade-order Monte Carlo with this sizing: ruin probability {R['mc']['p_ruin']:.0%} (the $200-account floor), median end ${R['mc']['end_median']:,.0f}, median drawdown {R['mc']['dd_median_pct']}%. The same regime caveat as every earlier report applies: the profit is 2024-2026.")
body = body.replace("{N_SUMMARY}", summary)
build = r"""
(function build() {
  const D = DATA; const t0 = T(); const W = D.windows; const names = Object.keys(W['6y']);
  $('#chips').append(...['$200 start, margin and stop-out simulated', 'XM spread by hour, 10-pt slippage, swap', 'Sep 2020 to Sep 2026'].map(s => txt('span', 'chip', s)));
  [['6y', 'Sep 2020 to Sep 2026'], ['2023-26', 'Jan 2023 to Sep 2026'], ['2025-01..2026-09', '1 Jan 2025 to 25 Sep 2026'], ['last12m', 'last 12 months']].forEach(([w, lab]) => { const m = W[w][names[0]]; const tile = el('div', 'tile'); tile.appendChild(txt('div', 'lab', lab + ' · end balance from $200')); tile.appendChild(txt('div', 'val', fmt$(m.end))); tile.appendChild(el('div', 'sub', `${fmtN(m.growth, 1)}x · max DD <b>${fmtN(m.dd_pct, 1)}%</b> · max lot <b>${fmtN(m.max_lot, 2)}</b> · worst deal <b>${fmt$(m.worst)}</b> · ${m.positions} positions, ${m.partials} partial exits${m.ruin ? ' · RUINED' : ''}`)); $('#tiles').appendChild(tile); });
  const mc = D.mc; const tile = el('div', 'tile'); tile.appendChild(txt('div', 'lab', 'Trade-order Monte Carlo, 5,000 orderings')); tile.appendChild(txt('div', 'val', fmtPct(mc.p_ruin, 0) + ' ruin')); tile.appendChild(el('div', 'sub', `end balance p05 / median / p95 ${fmt$(mc.end_p05)} / ${fmt$(mc.end_median)} / ${fmt$(mc.end_p95)} · drawdown median ${fmtN(mc.dd_median_pct, 0)}%, p95 ${fmtN(mc.dd_p95_pct, 0)}%`)); $('#tiles').appendChild(tile);
  [['6y', 'Balance 2020-2026 from $200'], ['2023-26', 'Balance 2023-2026 from $200'], ['2025-01..2026-09', 'Balance 1 Jan 2025 to 25 Sep 2026 from $200'], ['last12m', 'Balance, last 12 months from $200']].forEach(([w, title]) => { const e = D.equity[w]; card('#eq', {title, sub: 'weekly samples, realistic costs', height: 'tall', build: t => lineCfg(t, {labels: e[names[0]].t, datasets: names.map((n, i) => ({label: n, data: e[n].v, color: [t.s1, t.s2, t.s3][i]})), catLimit: 8}), table: {head: ['week', ...names], rows: e[names[0]].t.map((d, i) => [d, ...names.map(n => e[n].v[i])])}}); });
  const ys = Object.keys(D.by_year[names[0]]);
  card('#year', {title: 'Net by year, $ (account view)', build: t => barCfg(t, {labels: ys, datasets: names.map((n, i) => ({label: n, data: ys.map(y => D.by_year[n][y] ?? 0), color: [t.s1, t.s2, t.s3][i]}))}), table: {head: ['year', ...names], rows: ys.map(y => [y, ...names.map(n => D.by_year[n][y])])}});
  const sy = D.start_years; const yk = Object.keys(sy);
  card('#year', {title: 'End balance by start year ($200 on 1 January, run to 25 Sep 2026)', build: t => barCfg(t, {labels: yk, datasets: [{label: 'end balance', data: yk.map(y => sy[y].end), color: t.s1, notes: yk.map(y => `max DD ${fmtN(sy[y].dd_pct, 1)}%, max lot ${fmtN(sy[y].max_lot, 2)}, ${sy[y].positions} positions`)}]}), table: {head: ['start year', 'end $', 'growth', 'max DD %', 'max lot', 'worst deal $', 'positions', 'ruined'], rows: yk.map(y => [y, sy[y].end, sy[y].growth, sy[y].dd_pct, sy[y].max_lot, sy[y].worst, sy[y].positions, sy[y].ruin ? 'yes' : 'no'])}});
  tableCard('#tbl', {title: 'Lot tiers reached (six years from $200)', head: ['lot', 'first used', 'balance at that time $'], rows: D.lot_timeline.map(r => [r.lot, r.first_used, r.balance_then])});
  tableCard('#tbl', {title: 'All windows', head: ['window', 'configuration', 'end $', 'growth', 'net $', 'PF', 'win % (positions)', 'max DD $', 'max DD %', 'max lot', 'worst deal $', 'best deal $', 'positions', 'partial exits', 'max consecutive losses', 'ruined'], rows: Object.entries(W).flatMap(([w, cfgs]) => Object.entries(cfgs).map(([n, m]) => [w, n, m.end, m.growth, m.net, m.pf, m.win_rate, m.dd_usd, m.dd_pct, m.max_lot, m.worst, m.best, m.positions, m.partials, m.max_consec_losses, m.ruin ? 'yes' : 'no'])), opts: {numCols: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]}});
  tableCard('#tbl', {title: 'Last 12 months, every deal (final defaults from $200)', head: ['filled', 'closed', 'side', 'lot', 'entry', 'initial SL', 'exit', 'reason', 'P&L $', 'balance after $'], rows: D.trades_last12m.map(r => [r.time_in, r.time_out, r.side === 1 ? 'BUY' : 'SELL', r.lots, r.entry, r.isl, r.exit, r.exit_reason, r.pnl, r.balance]), opts: {numCols: [3, 4, 5, 6, 8, 9]}});
  renderAll();
  const mq = window.matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
"""
page = "<title>SMA18 Gold H4 Final EA</title>\n" + fonts + "\n" + style + "\n" + body + '\n<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>\n<script>\nconst DATA = ' + json.dumps(R, default=C._default) + ";\n" + helpers + build + "\n</script>\n"
with open(os.path.join(HERE, "report6.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("report6.html written")
