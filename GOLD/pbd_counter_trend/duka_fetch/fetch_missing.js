const { getHistoricRates } = require('dukascopy-node');
const fs = require('fs'); const path = require('path');
const outDir = 'D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_chunks';
const months = [];
for (let y = 2021; y <= 2026; y++) for (let m = 1; m <= 12; m++) {
  if (y === 2021 && m < 9) continue; if (y === 2026 && m > 9) continue; months.push([y, m]);
}
(async () => {
  for (const [y, m] of months) {
    const f = path.join(outDir, `bid_${y}-${String(m).padStart(2, '0')}.csv`);
    if (fs.existsSync(f) && fs.statSync(f).size > 1000) { continue; }
    const from = new Date(Date.UTC(y, m - 1, 1)); const to = new Date(Date.UTC(y, m, 1));
    let ok = false;
    for (let attempt = 1; attempt <= 5 && !ok; attempt++) {
      try {
        const t0 = Date.now();
        const csv = await getHistoricRates({ instrument: 'xauusd', dates: { from, to: to > new Date() ? new Date() : to }, timeframe: 'm1', priceType: 'bid', volumes: true,
          format: 'csv', useCache: true, cacheFolderPath: './.dukascopy-cache', batchSize: 4, pauseBetweenBatchesMs: 700, retryCount: 6, pauseBetweenRetriesMs: 1500, ignoreFlats: true });
        const rows = csv.split('\n').length - 1;
        if (rows < 5000) throw new Error(`only ${rows} rows`);
        fs.writeFileSync(f, csv);
        console.log(`${y}-${m}: ${rows} rows, ${((Date.now() - t0) / 1000).toFixed(0)}s`); ok = true;
      } catch (e) { console.log(`${y}-${m} attempt ${attempt} failed: ${String(e).slice(0, 120)}`); await new Promise(r => setTimeout(r, 5000 * attempt)); }
    }
  }
  console.log('ALL DONE');
})();
