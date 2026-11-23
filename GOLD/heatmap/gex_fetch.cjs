#!/usr/bin/env node
// Downloads the GLD option chain (CBOE delayed quotes, free, about 15 min behind) and writes gex_data.js,
// which gold_gex.html loads with a <script> tag so the page still works when opened as a file.
//   node gex_fetch.cjs              one download
//   node gex_fetch.cjs --watch 5    download again every 5 minutes (Ctrl+C to stop)
//   node gex_fetch.cjs --file X     convert a chain saved from the browser (CBOE's GLD.json) instead
//   node gex_fetch.cjs --symbol IAU another ticker (the page's gold conversion is built for GLD)
//
// Since about 10 Nov 2026 CBOE puts Cloudflare's bot check in front of this file ("Attention Required!",
// HTTP 403 or no answer to scripts). That check is not worked around. A person can still open
//   https://cdn.cboe.com/api/global/delayed_quotes/options/GLD.json
// in the browser and save it (Ctrl+S); with --watch, a GLD*.json saved in the Downloads folder (or next to this
// script) in the last 36 hours is picked up within 30 seconds. Open interest changes once a day, and the page
// recomputes gamma at the live price, so one save a day is enough. While CBOE blocks it, the direct download is
// tried only every 6 hours (it used to try every 5 minutes).
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf('--' + name);
  if (i < 0) return fallback;
  return args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : true;
}
const SYMBOL = String(opt('symbol', 'GLD')).toUpperCase();
const WATCH = opt('watch', false);
const FILE = opt('file', '');
const OUT = path.join(__dirname, 'gex_data.js');
const STATUS = path.join(__dirname, 'gex_fetch_status.js');
const URL_ = `https://cdn.cboe.com/api/global/delayed_quotes/options/${SYMBOL}.json`;
const clock = () => new Date().toLocaleTimeString();
// Each attempt writes gex_fetch_status.js (git-ignored), so the page can say why its option data is old.
const note = s => { try { fs.writeFileSync(STATUS, 'window.GEX_FETCH = ' + JSON.stringify(Object.assign(s, { at: Date.now(), url: URL_ })) + ';\n'); } catch (e) { /* not important */ } };

// CBOE's JSON -> gex_data.js. from = where it came from (for the log).
function convert(json, from) {
  const d = json && json.data;
  if (!d || !Array.isArray(d.options)) throw new Error('not a CBOE option chain');
  const contracts = [];
  for (const o of d.options) {
    const m = /^[A-Z]+(\d{6})([CP])(\d{8})$/.exec(o.option);       // GLD261106C00375000
    const oi = o.open_interest || 0, vol = o.volume || 0;
    if (!m || (!oi && !vol)) continue;
    contracts.push([m[1], m[2] === 'C' ? 0 : 1, +m[3] / 1000, +(+o.iv || 0).toFixed(4), oi, vol, +(+o.gamma || 0).toFixed(5)]);
  }
  if (!contracts.length) throw new Error('CBOE returned no contracts with open interest');
  const data = { symbol: d.symbol, spot: d.current_price, lastTradeTime: d.last_trade_time, timestamp: json.timestamp,
                 fetchedAt: Date.now(), source: from, contracts };
  fs.writeFileSync(OUT + '.tmp', 'window.GEX_DATA = ' + JSON.stringify(data) + ';\n');
  fs.renameSync(OUT + '.tmp', OUT);                                // the page never sees a half-written file
  const expiries = new Set(contracts.map(c => c[0])).size;
  console.log(`${clock()}  ${data.symbol} ${data.spot}  ${contracts.length} contracts, ${expiries} expiries  (CBOE time ${data.timestamp} UTC, ${from})  -> ${path.basename(OUT)}`);
  return data;
}
async function download() {
  const res = await fetch(URL_, { redirect: 'follow', signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error(`CBOE answered HTTP ${res.status}`);
  return convert(await res.json(), 'download');
}
// The CBOE time stamp of the chain the page has now ('' when none).
function current() {
  try { return JSON.parse(fs.readFileSync(OUT, 'utf8').replace(/^window\.GEX_DATA = /, '').replace(/;\s*$/, '')).timestamp || ''; } catch (e) { return ''; }
}
// Newest GLD*.json saved in the last 36 hours, in Downloads or next to this script.
function savedFile() {
  const dirs = [path.join(os.homedir(), 'Downloads'), __dirname], re = new RegExp(`^${SYMBOL}.*\\.json$`, 'i');
  let best = null;
  for (const dir of dirs) {
    let names = [];
    try { names = fs.readdirSync(dir); } catch (e) { continue; }
    for (const n of names) {
      if (!re.test(n)) continue;
      const f = path.join(dir, n), st = fs.statSync(f);
      if (Date.now() - st.mtimeMs < 36 * 3600e3 && (!best || st.mtimeMs > best.t)) best = { f, t: st.mtimeMs };
    }
  }
  return best;
}
let seenFile = 0;
function trySaved() {
  const s = savedFile();
  if (!s || s.t <= seenFile) return false;
  seenFile = s.t;
  try {
    const json = JSON.parse(fs.readFileSync(s.f, 'utf8'));
    if (json.timestamp && current() && json.timestamp <= current()) return false;   // not newer than what the page has
    convert(json, 'saved file ' + path.basename(s.f));
    note({ ok: true, via: 'file' });
    return true;
  } catch (e) { console.error(`${clock()}  ${path.basename(s.f)} is not usable: ${e.message}`); return false; }
}

(async () => {
  if (FILE) {
    try { convert(JSON.parse(fs.readFileSync(FILE, 'utf8')), 'file ' + path.basename(FILE)); note({ ok: true, via: 'file' }); }
    catch (e) { console.error(`${clock()}  ${FILE}: ${e.message}`); process.exit(1); }
    return;
  }
  const minutes = WATCH === true ? 5 : Math.max(1, +WATCH || 0);
  let blocked = 0, said = 0, nextTry = 0;
  const attempt = async () => {
    try {
      await download(); note({ ok: true, via: 'download' });
      if (blocked) console.log(`${clock()}  options download works again`);
      blocked = 0;
    } catch (e) {
      const bot = /403|fetch failed|aborted|timeout/i.test(e.message);
      note({ ok: false, error: e.message, bot });
      if (!blocked || Date.now() - said > 6 * 3600e3) {
        console.error(`${clock()}  options download ${blocked ? 'still failing' : 'failed'}: ${e.message}` +
          (bot ? `\n          CBOE blocks scripts (Cloudflare bot check). For the GEX bars: open ${URL_} in your browser and save it` +
                 ` (Ctrl+S) to Downloads; this window picks it up within 30 s. Prices, candles, zones and MT5 are not affected.` : ''));
        said = Date.now();
      }
      blocked++;
      if (!WATCH) process.exit(1);
    }
    nextTry = Date.now() + (blocked ? 6 * 3600e3 : minutes * 60e3);   // blocked: ask CBOE again in 6 hours, not every 5 minutes
  };
  if (!WATCH) { if (!trySaved()) await attempt(); return; }
  if (!trySaved()) await attempt();
  for (;;) {
    await new Promise(r => setTimeout(r, 30e3));
    if (trySaved()) continue;
    if (Date.now() >= nextTry) await attempt();
  }
})();
