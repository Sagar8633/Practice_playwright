const { getHistoricRates } = require('dukascopy-node');
const fs = require('fs'); const path = require('path');
const outDir = 'D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_chunks';
fs.mkdirSync(outDir, { recursive: true });
const months = [];
for (let y = 2021; y <= 2026; y++) for (let m = 1; m <= 12; m++) {
  if (y === 2021 && m < 9) continue; if (y === 2026 && m > 9) continue; months.push([y, m]);
}
months.reverse();
(async () => {
  for (const [y, m] of months) {
    const f = path.join(outDir, `bid_${y}-${String(m).padStart(2, '0')}.csv`);
    if (fs.existsSync(f) && fs.statSync(f).size > 1000) { console.log('skip', f); continue; }
    const from = new Date(Date.UTC(y, m - 1, 1)); const to = new Date(Date.UTC(y, m, 1));
    for (let attempt = 1; attempt <= 8; attempt++) {
      try {
        const t0 = Date.now();
        const csv = await getHistoricRates({ instrument: 'xauusd', dates: { from, to: to > new Date() ? new Date() : to }, timeframe: 'm1', priceType: 'bid', volumes: true,
          format: 'csv', useCache: true, cacheFolderPath: './.dukascopy-cache', batchSize: 2, pauseBetweenBatchesMs: 2500, retryCount: 8, pauseBetweenRetriesMs: 6000, ignoreFlats: true });
        fs.writeFileSync(f, csv);
        console.log(`${y}-${m}: ${csv.split('\n').length - 1} rows, ${((Date.now() - t0) / 1000).toFixed(0)}s`); break;
      } catch (e) { console.log(`${y}-${m} attempt ${attempt} failed: ${String(e).slice(0, 160)}`); await new Promise(r => setTimeout(r, 90000)); }
    }
  }
  console.log('ALL DONE');
})();
