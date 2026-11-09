#!/usr/bin/env node
/* Records heatmap columns (order book + tape, 1 column/s) to gzip NDJSON, one file per hour,
 * so sessions can be replayed in gold_heatmap.html ("Load recording").
 *
 *   node record.cjs                         # Binance Futures PAXGUSDT, 1 s columns, agg 0.10
 *   node record.cjs --feed bybit --symbol XAUTUSDT --agg 0.25 --column 500 --out D:\rec
 *   node record.cjs --seconds 3600                # stop by itself after an hour
 *
 * Needs node >= 22 (built-in WebSocket + fetch). Ctrl+C stops it cleanly.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
require('./engine.js');
const { BookEngine, FeedClient, FEEDS, serializeColumn } = globalThis.HeatmapEngine;

const args = Object.fromEntries(process.argv.slice(2).map((a, i, arr) => a.startsWith('--') ? [a.slice(2), arr[i + 1]] : null).filter(Boolean));
const feedKey = args.feed || 'binance_fut';
if (!FEEDS[feedKey]) { console.error('feed must be one of ' + Object.keys(FEEDS).join(', ')); process.exit(2); }
const symbol = (args.symbol || FEEDS[feedKey].symbol).toUpperCase();
const aggTick = +(args.agg || 0.1), columnMs = +(args.column || 1000);
const outDir = path.resolve(args.out || path.join(__dirname, 'recordings'));
fs.mkdirSync(outDir, { recursive: true });

const engine = new BookEngine({ tick: FEEDS[feedKey].tick, aggTick, columnMs, halfRange: 400, maxColumns: 600 });
const client = new FeedClient(feedKey, symbol, engine, {
  onState: (s, x) => console.log(new Date().toISOString(), 'feed', s, x || ''),
  onLog: m => console.log(new Date().toISOString(), m),
});

let gz = null, file = null, hour = null, lines = 0;
function openFile(now) {
  const d = new Date(now), stamp = d.toISOString().slice(0, 13).replace(/[-T]/g, '').replace(/(\d{8})(\d{2})/, '$1_$2');
  file = path.join(outDir, `${feedKey}_${symbol}_${stamp}.ndjson.gz`);
  gz = zlib.createGzip({ level: 6 });
  gz.pipe(fs.createWriteStream(file, { flags: 'a' }));
  gz.write(JSON.stringify({ header: 1, feed: feedKey, symbol, tick: engine.tick, aggTick: engine.aggTick, columnMs, started: d.toISOString() }) + '\n');
  hour = d.getUTCHours(); lines = 0;
  console.log(new Date().toISOString(), 'writing', file);
}
function closeFile() { if (gz) { gz.end(); gz = null; } }

const timer = setInterval(() => {
  if (!engine.synced) return;
  const now = Date.now();
  const col = engine.tickColumn(now);
  if (!col) return;
  if (!gz || new Date(now).getUTCHours() !== hour) { closeFile(); openFile(now); }
  gz.write(JSON.stringify(serializeColumn(col)) + '\n');
  if (++lines % 30 === 0) gz.flush();          // a crash loses at most 30 columns
  if (lines % 300 === 0) {
    const m = engine.metrics(now);
    console.log(new Date().toISOString(), `${lines} columns, price ${engine.lastPrice}, levels ${engine.bids.size}/${engine.asks.size}, ` +
      `updates ${engine.stats.updates}, trades ${engine.stats.trades}, resyncs ${engine.stats.resyncs}` +
      (m ? `, bias ${m.bias} ${m.score.toFixed(2)}` : ''));
  }
}, columnMs);

function shutdown() { console.log('\nstopping'); clearInterval(timer); client.stop(); closeFile(); setTimeout(() => process.exit(0), 500); }
process.on('SIGINT', shutdown); process.on('SIGTERM', shutdown);
if (args.seconds) setTimeout(shutdown, +args.seconds * 1000);     // --seconds N: timed run
client.start();
