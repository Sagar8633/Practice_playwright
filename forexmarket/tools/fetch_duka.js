// Dukascopy M1 bid candles (with volumes) per month, Sep 2021 .. Sep 2026, plus H1 per year 2015..2021 for the long D1/H4 path.
// Usage: node fetch_duka.js eurusd gbpusd ...   (resumable; ONE process only: parallel processes trigger HTTP 429)
const { getHistoricRates } = require('D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/tools/node_modules/dukascopy-node');
const fs = require('fs'); const path = require('path');
const ROOT = 'D:/Practice_Playwright/forexmarket/data/duka';
const instruments = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const months = [];
for (let y = 2021; y <= 2026; y++) for (let m = 1; m <= 12; m++) { if (y === 2021 && m < 9) continue; if (y === 2026 && m > 9) continue; months.push([y, m]); }

async function fetchOne(instr, f, from, to, timeframe, minRows) {
  for (let attempt = 1; attempt <= 400; attempt++) {
    try {
      const t0 = Date.now();
      const csv = await getHistoricRates({ instrument: instr, dates: { from, to }, timeframe, priceType: 'bid', volumes: true, format: 'csv', useCache: false,
        batchSize: 2, pauseBetweenBatchesMs: 3000, retryCount: 3, pauseBetweenRetriesMs: 8000, ignoreFlats: true });
      const n = csv.split(/\r?\n/).length - 1;
      if (n < minRows) throw new Error('too few rows ' + n);
      fs.writeFileSync(f, csv);
      console.log(instr + ' ' + path.basename(f) + ': ' + n + ' rows, ' + ((Date.now() - t0) / 1000).toFixed(0) + 's');
      await sleep(1500);
      return true;
    } catch (e) {
      const msg = String(e); const wait = msg.includes('429') ? 300000 : 30000;
      console.log(instr + ' ' + path.basename(f) + ' attempt ' + attempt + ' failed: ' + msg.slice(0, 120) + '; waiting ' + (wait / 1000) + 's');
      await sleep(wait);
    }
  }
  return false;
}

(async () => {
  for (const instr of instruments) {
    const dir = path.join(ROOT, instr); fs.mkdirSync(dir, { recursive: true });
    for (const [y, m] of months) {
      const f = path.join(dir, 'm1_' + y + '-' + String(m).padStart(2, '0') + '.csv');
      if (fs.existsSync(f) && fs.statSync(f).size > 1000) continue;
      const to = new Date(Date.UTC(y, m, 1)); const from = new Date(Date.UTC(y, m - 1, 1));
      await fetchOne(instr, f, from, to, 'm1', 500);
    }
    for (let y = 2015; y <= 2021; y++) {
      const f = path.join(dir, 'h1_' + y + '.csv');
      if (fs.existsSync(f) && fs.statSync(f).size > 1000) continue;
      await fetchOne(instr, f, new Date(Date.UTC(y, 0, 1)), new Date(Date.UTC(y + 1, 0, 1)), 'h1', 100);
    }
    console.log(instr + ' DONE');
  }
  console.log('ALL DONE');
})();
