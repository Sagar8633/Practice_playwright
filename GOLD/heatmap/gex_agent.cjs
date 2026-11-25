#!/usr/bin/env node
// Local bridge between gold_gex.html and MetaTrader 5 (the GexSignalTrader EA).
//   node gex_agent.cjs                bridge, plus the options download every 5 minutes
//   node gex_agent.cjs --no-fetch     bridge only
//   node gex_agent.cjs --test         disabled: this bridge accepts TWK 15m setup signals only
// The page POSTs each qualifying TWK 15m signal to http://127.0.0.1:8791/signal. The agent writes it to the MT5 common files
// folder, where the EA reads it once a second, and passes the EA's answer back to the page (GET /status).
// Only the page can use the agent: every request needs the token in gex_agent_info.js, a local file that
// other web sites cannot read. The agent places no orders itself; the EA does, and only on a demo account.
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const { spawn } = require('child_process');

const PORT = 8791;
const COMMON = process.env.GEX_COMMON_DIR || path.join(process.env.APPDATA || '', 'MetaQuotes', 'Terminal', 'Common', 'Files');
const SIGNAL = path.join(COMMON, 'gex_signal.txt');      // id;BUY|SELL;entry;stop;target;score;sent[;lots;source;adx] (UTC seconds)
const STATUS = path.join(COMMON, 'gex_status.txt');      // id;state;time (UTC seconds);message      written by the EA
const ALIVE = path.join(COMMON, 'gex_ea.txt');           // time;demo|real;server;symbol;balance;algo;dryrun   written by the EA every 5 s
const PRICE = path.join(COMMON, 'gex_price.txt');        // time;symbol;bid;ask;tick age (s);server            written by the EA (1.01+) every second
const INFO = path.join(__dirname, 'gex_agent_info.js');  // port and token for the page
const JOURNAL = path.join(__dirname, 'mt5_signals.log');
const token = crypto.randomBytes(16).toString('hex');
const sent = new Set();                                  // ids already passed to MT5
const clock = () => new Date().toLocaleTimeString();
const read = file => { try { return fs.readFileSync(file, 'latin1').trim(); } catch (e) { return ''; } };

function eaState() {
  const p = read(ALIVE).split(';');
  if (p.length < 7) return { alive: false };
  const age = Math.round(Date.now() / 1000 - +p[0]);
  return { alive: age <= 20, age, mode: p[1], server: p[2], symbol: p[3], balance: +p[4], algo: p[5] === '1', dryrun: p[6] === '1' };
}
// The broker's bid / ask from the EA. fresh = the EA wrote it in the last 10 s (it is attached and running).
function priceState() {
  const p = read(PRICE).split(';');
  if (p.length < 5 || !(+p[2] > 0)) return { ok: false };
  const age = Math.round(Date.now() / 1000 - +p[0]);
  return { ok: age <= 10, age, time: +p[0] * 1000, symbol: p[1], bid: +p[2], ask: +p[3], tickAge: +p[4], server: p[5] || '' };
}
// Spot gold from Swissquote's public quote feed (the one its web site shows): real time, a broker's price like
// OANDA's on TradingView. Measured 23 Nov 2026: gold-api.com, the page's own reference, ran 1-3 $ away from it
// and updates only every 30 s. The browser cannot read Swissquote (no CORS header), so the agent fetches it,
// at most once every 2 s, and passes the tightest spread's bid and ask on.
const SPOT = { at: 0, q: null, busy: null };
function swissquote() {
  if (SPOT.q && Date.now() - SPOT.at < 2000) return Promise.resolve(SPOT.q);
  if (!SPOT.busy) SPOT.busy = (async () => {
    try {
      const r = await fetch('https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD', { signal: AbortSignal.timeout(4000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json(), all = j.flatMap(x => x.spreadProfilePrices.map(p => ({ ...p, ts: x.ts }))).filter(p => p.bid > 0 && p.ask > p.bid);
      const p = all.sort((a, b) => (a.ask - a.bid) - (b.ask - b.bid))[0];
      SPOT.q = p ? { ok: true, source: 'Swissquote', bid: p.bid, ask: p.ask, time: p.ts } : { ok: false, error: 'no quote' };
    } catch (e) { SPOT.q = { ok: false, error: e.message }; }
    SPOT.at = Date.now(); SPOT.busy = null;
    return SPOT.q;
  })();
  return SPOT.busy;
}
function lastStatus() {
  const p = read(STATUS).split(';');
  return p.length < 4 ? null : { id: +p[0], state: p[1], time: +p[2] * 1000, text: p.slice(3).join(';') };
}
// One signal for the EA. Returns an error text, or '' when written.
function writeSignal(s) {
  const side = String(s.side).toUpperCase(), n = [s.t, s.entry, s.stop, s.target].map(Number);
  if (!n.every(Number.isFinite) || (side !== 'BUY' && side !== 'SELL')) return 'not a valid signal';
  const [t, entry, stop, target] = n;
  if (side === 'BUY' ? !(stop < entry && entry < target) : !(target < entry && entry < stop)) return 'stop and target are on the wrong side of the entry';
  if (sent.has(t)) return 'duplicate';
  if (!fs.existsSync(COMMON)) return 'MT5 common files folder not found: ' + COMMON;
  const source = String(s.source || '').replace(/[;\r\n]/g, ' ').slice(0, 24);
  const adx = s.adx === undefined ? NaN : Number(s.adx);
  if (source !== 'TWK 15m') return 'TWK-only mode: GEX and test orders are disabled';
  if (!(Number.isFinite(adx) && adx > 20)) return 'TWK signal requires 15-minute ADX above 20';
  let fields = [t, side, entry.toFixed(2), stop.toFixed(2), target.toFixed(2), Math.round(+s.score || 0), Math.floor(Date.now() / 1000)];
  if (s.lots !== undefined || source) {
    const lots = Number(s.lots || 0);
    if (!Number.isFinite(lots) || lots < 0) return 'invalid signal lot size';
    if (Math.abs(lots - 0.01) > 1e-9) return 'TWK signals must use exactly 0.01 lots';
    fields = fields.concat([lots > 0 ? lots.toFixed(2) : '0', source]);
    if (s.adx !== undefined) fields.push(adx.toFixed(2));
  }
  const line = fields.join(';');
  fs.writeFileSync(SIGNAL + '.tmp', line + '\r\n');
  fs.renameSync(SIGNAL + '.tmp', SIGNAL);                // the EA never sees a half-written line
  sent.add(t);
  fs.appendFileSync(JOURNAL, new Date().toISOString() + ' ' + line + '\n');
  console.log(`${clock()}  signal -> MT5: ${side}${s.lots > 0 ? ` ${Number(s.lots).toFixed(2)} lots` : ''}${source ? ` ${source}` : ''}${Number.isFinite(adx) ? ` ADX ${adx.toFixed(1)}` : ''} entry ${entry.toFixed(2)} stop ${stop.toFixed(2)} target ${target.toFixed(2)} score ${s.score || 0}`);
  return '';
}
// ------------------------------------------------------------------ one test signal from the command line
const args = process.argv.slice(2), ti = args.indexOf('--test');
if (ti >= 0) {
  console.error('TWK-only mode: test orders are disabled; only qualified TWK 15m setup signals are accepted.');
  process.exit(1);
}

// ------------------------------------------------------------------ bridge
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  const reply = (code, obj) => {
    res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type',
                          'Access-Control-Allow-Private-Network': 'true' });   // lets the hosted page ask this PC (Chrome's local network check)
    res.end(JSON.stringify(obj));
  };
  if (req.method === 'OPTIONS') return reply(204, {});
  // the broker price (MT5) and Swissquote's spot: read-only and harmless, so no token, and the hosted page (which
  // has no token) can use them too
  if (req.method === 'GET' && url.pathname === '/price') { swissquote().then(spot => reply(200, Object.assign(priceState(), { spot }))); return; }
  if (req.method === 'GET' && url.pathname === '/status') {
    if (url.searchParams.get('token') !== token) return reply(403, { error: 'wrong token' });
    return reply(200, { ea: eaState(), last: lastStatus() });
  }
  if (req.method === 'POST' && url.pathname === '/signal') {
    let body = '';
    req.on('data', d => { body += d; if (body.length > 4096) req.destroy(); });
    req.on('end', () => {
      let s;
      try { s = JSON.parse(body); } catch (e) { return reply(400, { error: 'not JSON' }); }
      if (s.token !== token) return reply(403, { error: 'wrong token' });
      if (s.test) return reply(403, { error: 'TWK-only mode: test orders are disabled' });
      const err = writeSignal(s);
      reply(err && err !== 'duplicate' ? 400 : 200, err ? { ok: err === 'duplicate', error: err } : { ok: true });
    });
    return;
  }
  reply(404, { error: 'not found' });
});
server.on('error', e => { console.error(e.code === 'EADDRINUSE' ? `Port ${PORT} is in use: the agent is probably already running.` : e.message); process.exit(1); });
server.listen(PORT, '127.0.0.1', () => {
  fs.writeFileSync(INFO, `window.GEX_AGENT = ${JSON.stringify({ port: PORT, token, started: Date.now() })};\n`);
  console.log(`${clock()}  agent ready on 127.0.0.1:${PORT}; MT5 folder: ${COMMON}${fs.existsSync(COMMON) ? '' : '  (NOT FOUND)'}`);
  const ea = eaState();
  console.log(ea.alive ? `${clock()}  EA attached: ${ea.mode} account on ${ea.server}, ${ea.symbol}` : `${clock()}  EA not attached yet: drag GexSignalTrader onto the gold chart in MT5`);
});

// say what the EA reports, and when it comes or goes
let seen = read(STATUS), wasAlive = eaState().alive;
setInterval(() => {
  const now = read(STATUS), ea = eaState();
  if (now && now !== seen) { seen = now; const st = lastStatus(); if (st) console.log(`${clock()}  MT5: ${st.text}`); }
  if (ea.alive !== wasAlive) { wasAlive = ea.alive; console.log(`${clock()}  EA ${ea.alive ? `attached: ${ea.mode} account, ${ea.symbol}` : 'is no longer attached'}`); }
}, 2000);

// the options download, so one window keeps everything running
let fetcher = null;
if (!args.includes('--no-fetch')) fetcher = spawn(process.execPath, [path.join(__dirname, 'gex_fetch.cjs'), '--watch', '5'], { stdio: 'inherit' });
function stop() {
  try { fs.unlinkSync(INFO); } catch (e) { /* already gone */ }
  if (fetcher) fetcher.kill();
  process.exit(0);
}
process.on('SIGINT', stop); process.on('SIGTERM', stop); process.on('SIGHUP', stop);
