#!/usr/bin/env node
// Downloads the GLD option chain (CBOE delayed quotes, free, about 15 min behind) and writes gex_data.js,
// which gold_gex.html loads with a <script> tag so the page still works when opened as a file.
//   node gex_fetch.cjs              one download
//   node gex_fetch.cjs --watch 5    download again every 5 minutes (Ctrl+C to stop)
//   node gex_fetch.cjs --symbol IAU another ticker (the page's gold conversion is built for GLD)
'use strict';
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf('--' + name);
  if (i < 0) return fallback;
  return args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : true;
}
const SYMBOL = String(opt('symbol', 'GLD')).toUpperCase();
const WATCH = opt('watch', false);
const OUT = path.join(__dirname, 'gex_data.js');

async function once() {
  const res = await fetch(`https://cdn.cboe.com/api/global/delayed_quotes/options/${SYMBOL}.json`, { redirect: 'follow' });
  if (!res.ok) throw new Error(`CBOE answered HTTP ${res.status}`);
  const json = await res.json(), d = json.data;
  const contracts = [];
  for (const o of d.options) {
    const m = /^[A-Z]+(\d{6})([CP])(\d{8})$/.exec(o.option);       // GLD261106C00375000
    const oi = o.open_interest || 0, vol = o.volume || 0;
    if (!m || (!oi && !vol)) continue;
    contracts.push([m[1], m[2] === 'C' ? 0 : 1, +m[3] / 1000, +(+o.iv || 0).toFixed(4), oi, vol, +(+o.gamma || 0).toFixed(5)]);
  }
  if (!contracts.length) throw new Error('CBOE returned no contracts with open interest');
  const data = { symbol: d.symbol, spot: d.current_price, lastTradeTime: d.last_trade_time, timestamp: json.timestamp,
                 fetchedAt: Date.now(), contracts };
  fs.writeFileSync(OUT + '.tmp', 'window.GEX_DATA = ' + JSON.stringify(data) + ';\n');
  fs.renameSync(OUT + '.tmp', OUT);                                // the page never sees a half-written file
  const expiries = new Set(contracts.map(c => c[0])).size;
  console.log(`${new Date().toLocaleTimeString()}  ${data.symbol} ${data.spot}  ${contracts.length} contracts, ${expiries} expiries` +
              `  (CBOE time ${data.timestamp} UTC)  -> ${path.basename(OUT)}`);
}

(async () => {
  const minutes = WATCH === true ? 5 : Math.max(1, +WATCH || 0);
  for (;;) {
    try { await once(); } catch (e) { console.error(`${new Date().toLocaleTimeString()}  download failed: ${e.message}`); if (!WATCH) process.exit(1); }
    if (!WATCH) break;
    await new Promise(r => setTimeout(r, minutes * 60e3));
  }
})();
