// Fetch missing/extra Dukascopy XAUUSD M1 months (2024-07, 2020-09..2021-08) then H1 2003-2021, one request at a time.
const { getHistoricRates } = require('dukascopy-node');
const fs = require('fs'); const path = require('path');
const outDir = 'D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_chunks';
const months = [[2024, 7]];
for (let m = 9; m <= 12; m++) months.push([2020, m]);
for (let m = 1; m <= 8; m++) months.push([2021, m]);
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  for (const [y, m] of months) {
    const f = path.join(outDir, `bid_${y}-${String(m).padStart(2, '0')}.csv`);
    if (fs.existsSync(f) && fs.statSync(f).size > 1000) { console.log('skip', f); continue; }
    const from = new Date(Date.UTC(y, m - 1, 1)); const to = new Date(Date.UTC(y, m, 1));
    for (let attempt = 1; attempt <= 6; attempt++) {
      try {
        const t0 = Date.now();
        const csv = await getHistoricRates({ instrument: 'xauusd', dates: { from, to }, timeframe: 'm1', priceType: 'bid', volumes: true,
          format: 'csv', useCache: false, batchSize: 4, pauseBetweenBatchesMs: 2000, retryCount: 6, pauseBetweenRetriesMs: 5000, ignoreFlats: true });
        const n = csv.split('\n').length - 1;
        if (n < 1000) throw new Error('too few rows ' + n);
        fs.writeFileSync(f, csv);
        console.log(`${y}-${m}: ${n} rows, ${((Date.now() - t0) / 1000).toFixed(0)}s`); break;
      } catch (e) { console.log(`${y}-${m} attempt ${attempt} failed: ${String(e).slice(0, 160)}`); await sleep(60000 * attempt); }
    }
  }
  // H1 full history per year, for server-time D1 construction before Sep 2021
  const h1Dir = 'D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_h1';
  fs.mkdirSync(h1Dir, { recursive: true });
  for (let y = 2003; y <= 2021; y++) {
    const f = path.join(h1Dir, `bid_h1_${y}.csv`);
    if (fs.existsSync(f) && fs.statSync(f).size > 1000) { console.log('skip', f); continue; }
    for (let attempt = 1; attempt <= 6; attempt++) {
      try {
        const csv = await getHistoricRates({ instrument: 'xauusd', dates: { from: new Date(Date.UTC(y, 0, 1)), to: new Date(Date.UTC(y + 1, 0, 1)) }, timeframe: 'h1', priceType: 'bid', volumes: true,
          format: 'csv', useCache: false, batchSize: 4, pauseBetweenBatchesMs: 2000, retryCount: 6, pauseBetweenRetriesMs: 5000, ignoreFlats: true });
        const n = csv.split('\n').length - 1;
        if (n < 100) throw new Error('too few rows ' + n);
        fs.writeFileSync(f, csv); console.log(`H1 ${y}: ${n} rows`); break;
      } catch (e) { console.log(`H1 ${y} attempt ${attempt} failed: ${String(e).slice(0, 160)}`); await sleep(60000 * attempt); }
    }
  }
  console.log('ALL DONE');
})();
