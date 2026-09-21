// Renders the screener matches into a self-contained HTML report.

import { CFG } from '../config.mjs';
import { rsToCr, esc } from './util.mjs';

const pct1 = v => v == null ? null : `${Number(v).toFixed(2)}%`;

export function renderHtml(rows, meta) {
  const screenerLink = sym => `https://www.screener.in/company/${encodeURIComponent(sym)}/consolidated/`;
  const body = rows.length ? rows.map((r, i) => {
    const delta = (r.postPct - r.priorPct).toFixed(2);
    const totProm = r.totalPromoter == null
      ? `<span class="flag">unknown</span>`
      : `${r.totalPromoter.toFixed(2)}%`;
    // pledge: null means we couldn't read the XBRL; 0 is the "good" (unpledged) case.
    const pledge = r.pledgePct == null
      ? `<span class="flag">n/a</span>`
      : `<span class="${r.pledgePct <= CFG.MAX_PLEDGE_PCT ? 'ok' : 'bad'}">${pct1(r.pledgePct)}</span>`;
    const fii = r.fiiPct == null ? `<span class="flag">n/a</span>` : pct1(r.fiiPct);
    // debt is not published in NSE's insider/shareholding feeds -> always null here.
    const debt = `<span class="flag">null</span><br><a href="${screenerLink(r.symbol)}" target="_blank">verify</a>`;
    return `<tr>
      <td>${i + 1}</td>
      <td><b>${esc(r.companyName)}</b><br><span class="sym">${esc(r.symbol)}</span></td>
      <td>${esc(r.name)}<br><span class="cat">${esc(r.category)}</span></td>
      <td class="ok">${esc(r.mode)}</td>
      <td class="num">${r.qty.toLocaleString('en-IN')}</td>
      <td class="num val">${rsToCr(r.value)}</td>
      <td class="num">${r.priorPct}%</td>
      <td class="num">${r.postPct}%</td>
      <td class="num up">+${delta}%</td>
      <td class="num">${totProm}</td>
      <td class="num">${debt}</td>
      <td class="num">${pledge}</td>
      <td class="num">${fii}</td>
      <td>${esc(r.broadcast)}<br><a href="${esc(r.filingUrl)}" target="_blank">filing</a></td>
    </tr>`;
  }).join('') : `<tr><td colspan="14" class="empty">No promoter market-buys matched the criteria in this window.</td></tr>`;

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>NSE Insider Screener — ${esc(meta.stamp)}</title>
<style>
  body{font:14px/1.5 system-ui,Segoe UI,Arial;margin:0;background:#0f1115;color:#e6e6e6}
  header{padding:22px 28px;background:#161a22;border-bottom:2px solid #2a7}
  h1{margin:0 0 4px;font-size:20px}
  .meta{color:#9aa4b2;font-size:13px}
  .crit{padding:14px 28px;color:#c8d0da;font-size:13px;background:#12151c}
  .crit b{color:#7fdca0}
  .note{color:#e0b35a}
  table{border-collapse:collapse;width:100%;font-size:13px}
  th,td{padding:8px 10px;border-bottom:1px solid #232733;text-align:left;vertical-align:top}
  th{position:sticky;top:0;background:#1c2230;color:#bcd;z-index:1}
  tr:hover td{background:#171b24}
  .num{text-align:right;font-variant-numeric:tabular-nums}
  .val{color:#7fdca0;font-weight:600}
  .up{color:#7fdca0}.ok{color:#7fdca0}
  .bad{color:#e06a6a;font-weight:600}
  .sym{color:#6cf;font-size:12px}.cat{color:#9aa4b2;font-size:12px}
  .flag{color:#e0b35a}
  .empty{text-align:center;color:#9aa4b2;padding:40px}
  a{color:#6cf}
</style></head><body>
<header>
  <h1>NSE Weekly Insider-Buying Screener</h1>
  <div class="meta">Generated ${esc(meta.stamp)} &middot; ${rows.length} matches from ${meta.filingCount} filings (${meta.rowCount} transactions parsed) &middot; window: last ${meta.windowDays} day(s)</div>
</header>
<div class="crit">
  Hard filters applied: <b>category = Promoter/Promoter&nbsp;Group</b> &middot; <b>transaction = Buy</b> &middot;
  <b>mode = Market&nbsp;Purchase</b> &middot; <b>value &ge; ${rsToCr(CFG.MIN_VALUE_RS)}</b> &middot;
  <b>post% &gt; prior%</b> &middot; <b>total promoter &gt; ${CFG.MIN_TOTAL_PROMOTER_PCT}%</b> (when known)
  ${CFG.REQUIRE_ZERO_PLEDGE ? `&middot; <b>promoter pledge &le; ${CFG.MAX_PLEDGE_PCT}%</b>` : ''}
  ${CFG.MIN_FII_PCT != null ? `&middot; <b>FII &ge; ${CFG.MIN_FII_PCT}%</b>` : ''}.
  <br>Pledge % &amp; FII % are read live from the quarterly shareholding-pattern XBRL.
  <span class="note">Debt is not published in NSE's filings feed (shown as null); the per-row "verify" link opens screener.in to confirm debt-free.</span>
</div>
<table>
<thead><tr>
  <th>#</th><th>Company</th><th>Acquirer</th><th>Mode</th><th>Qty</th><th>Value</th>
  <th>Prior%</th><th>Post%</th><th>&Delta;%</th><th>Tot.Prom%</th>
  <th>Debt</th><th>Pledge%</th><th>FII%</th><th>Filed / Source</th>
</tr></thead>
<tbody>${body}</tbody>
</table>
</body></html>`;
}
