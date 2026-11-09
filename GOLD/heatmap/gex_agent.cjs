#!/usr/bin/env node
// Local bridge between gold_gex.html and MetaTrader 5 (the GexSignalTrader EA).
//   node gex_agent.cjs                bridge, plus the options download every 5 minutes
//   node gex_agent.cjs --no-fetch     bridge only
//   node gex_agent.cjs --test buy     write one test signal (5 $ stop, 10 $ target) for the EA and exit; also: sell
// The page POSTs each new signal to http://127.0.0.1:8791/signal. The agent writes it to the MT5 common files
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
const SIGNAL = path.join(COMMON, 'gex_signal.txt');      // id;BUY|SELL;entry;stop;target;score;sent (UTC seconds)
const STATUS = path.join(COMMON, 'gex_status.txt');      // id;state;time (UTC seconds);message      written by the EA
const ALIVE = path.join(COMMON, 'gex_ea.txt');           // time;demo|real;server;symbol;balance;algo;dryrun   written by the EA every 5 s
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
  const line = [t, side, entry.toFixed(2), stop.toFixed(2), target.toFixed(2), Math.round(+s.score || 0), Math.floor(Date.now() / 1000)].join(';');
  fs.writeFileSync(SIGNAL + '.tmp', line + '\r\n');
  fs.renameSync(SIGNAL + '.tmp', SIGNAL);                // the EA never sees a half-written line
  sent.add(t);
  fs.appendFileSync(JOURNAL, new Date().toISOString() + ' ' + line + '\n');
  console.log(`${clock()}  signal -> MT5: ${side} entry ${entry.toFixed(2)} stop ${stop.toFixed(2)} target ${target.toFixed(2)} score ${s.score || 0}`);
  return '';
}
const testSignal = side => ({ t: Date.now(), side, entry: 1000, stop: side === 'sell' ? 1005 : 995, target: side === 'sell' ? 990 : 1010, score: 0 });

// ------------------------------------------------------------------ one test signal from the command line
const args = process.argv.slice(2), ti = args.indexOf('--test');
if (ti >= 0) {
  const side = (args[ti + 1] || 'buy').toLowerCase(), ea = eaState();
  console.log(ea.alive ? `EA is attached: ${ea.mode} account, ${ea.symbol}, Algo Trading ${ea.algo ? 'on' : 'OFF'}${ea.dryrun ? ', dry run' : ''}` : 'EA is not attached in MT5: the signal will be ignored');
  const err = writeSignal(testSignal(side === 'sell' ? 'sell' : 'buy'));
  if (err) { console.error('not written: ' + err); process.exit(1); }
  const id = [...sent][0];
  const wait = setInterval(() => { const st = lastStatus(); if (st && st.id === id) { console.log('EA answered: ' + st.text); clearInterval(wait); process.exit(0); } }, 500);
  setTimeout(() => { console.log('no answer from the EA within 15 s'); process.exit(2); }, 15000);
  return;
}

// ------------------------------------------------------------------ bridge
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  const reply = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type' }); res.end(JSON.stringify(obj)); };
  if (req.method === 'OPTIONS') return reply(204, {});
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
      const err = writeSignal(s.test ? testSignal(s.test === 'sell' ? 'sell' : 'buy') : s);
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
