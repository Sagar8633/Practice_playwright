const { getHistoricRates } = require('dukascopy-node');
const fs = require('fs');
const out = 'D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_2024-07.csv';
(async () => {
  const parts = [];
  const bounds = [[1,8],[8,15],[15,22],[22,29],[29,32]];
  for (const [a,b] of bounds) {
    const from = new Date(Date.UTC(2024,6,a)); const to = new Date(Date.UTC(2024,6,Math.min(b,32)));
    let ok=false;
    for (let attempt=1; attempt<=6 && !ok; attempt++) {
      try {
        const csv = await getHistoricRates({ instrument:'xauusd', dates:{from,to}, timeframe:'m1', priceType:'bid', volumes:true, format:'csv', useCache:false, batchSize:2, pauseBetweenBatchesMs:2500, retryCount:3, pauseBetweenRetriesMs:4000, ignoreFlats:true });
        const lines = csv.trim().split('\n'); console.log(`days ${a}-${b}: ${lines.length-1} rows`);
        parts.push(parts.length ? lines.slice(1).join('\n') : lines.join('\n')); ok=true;
      } catch(e) { console.log(`days ${a}-${b} attempt ${attempt} failed: ${String(e).slice(0,100)}`); await new Promise(r=>setTimeout(r, 30000*attempt)); }
    }
    if (!ok) { console.log('GIVE UP'); process.exit(1); }
  }
  fs.writeFileSync(out, parts.join('\n') + '\n'); console.log('WROTE', out);
})();
