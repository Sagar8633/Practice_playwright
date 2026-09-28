// Phase 14: download Dukascopy XAUUSD ticks for the hours around 15:30 XM server time on selected weekdays.
// usage: node fetch_ticks.js <from YYYY-MM-DD> <to YYYY-MM-DD> <weekdays e.g. 4,5> <outDir>
const { getHistoricRates } = require('dukascopy-node');
const fs = require('fs'); const path = require('path');
const [from, to, wdArg, outDir] = process.argv.slice(2);
const weekdays = wdArg.split(',').map(Number);           // JS: 0=Sun ... 4=Thu, 5=Fri
fs.mkdirSync(outDir, { recursive: true });
function lastSunday(y, m) { const d = new Date(Date.UTC(y, m + 1, 0)); d.setUTCDate(d.getUTCDate() - d.getUTCDay()); return d; }
function summer(d) { const y = d.getUTCFullYear(); const a = lastSunday(y, 2), b = lastSunday(y, 9); a.setUTCHours(1); b.setUTCHours(1); return d >= a && d < b; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const start = new Date(from + 'T00:00:00Z'), end = new Date(to + 'T00:00:00Z');
  let n = 0, ok = 0, fail = 0;
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    if (!weekdays.includes(d.getUTCDay())) continue;
    const base = summer(d) ? 11 : 12;                     // server 14:00-19:59 -> UTC 11-16 (summer) or 12-17 (winter)
    for (let h = base + 1; h < base + 4; h++) {
      const day = d.toISOString().slice(0, 10); const f = path.join(outDir, `xauusd_${day}_${String(h).padStart(2, '0')}utc.csv`);
      if (fs.existsSync(f) && fs.statSync(f).size > 100) continue;
      const a = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), h)); const b = new Date(a.getTime() + 3600 * 1000);
      n++;
      for (let attempt = 1; attempt <= 6; attempt++) {
        try {
          const csv = await getHistoricRates({ instrument: 'xauusd', dates: { from: a, to: b }, timeframe: 'tick', format: 'csv', volumes: true, useCache: false, ignoreFlats: false, batchSize: 1, pauseBetweenBatchesMs: 300, retryCount: 2, pauseBetweenRetriesMs: 800 });
          fs.writeFileSync(f, csv); ok++;
          if (ok % 25 === 0) console.log(`${new Date().toISOString().slice(11, 19)} ok=${ok} fail=${fail} last=${day} ${h}utc rows=${csv.split('\n').length - 1}`);
          break;
        } catch (e) {
          const msg = String(e).slice(0, 100);
          if (attempt === 6) { fail++; console.log(`FAIL ${day} ${h}utc: ${msg}`); }
          else { console.log(`backoff ${day} ${h}utc attempt ${attempt}: ${msg.slice(0, 60)}`); await sleep(msg.includes("429") ? 120000 : 5000 * attempt); }
        }
      }
      await sleep(1200);
    }
  }
  console.log(`DONE requested=${n} ok=${ok} fail=${fail}`);
})();
