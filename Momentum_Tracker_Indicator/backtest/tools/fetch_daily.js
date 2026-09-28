// Dukascopy XAUUSD bid candles, daily and 4-hour, full history, into ../data/. usage: node fetch_daily.js
const { getHistoricalRates } = require("dukascopy-node"); const fs = require("fs");
(async () => {
  for (const [tf, from] of [["d1", "2003-01-01"], ["h4", "2003-01-01"]]) {
    for (let attempt = 1; attempt <= 5; attempt++) {
      try {
        const csv = await getHistoricalRates({ instrument: "xauusd", dates: { from: new Date(from), to: new Date("2026-09-26") }, timeframe: tf, priceType: "bid", format: "csv", volumes: true, ignoreFlats: true, batchSize: 2, pauseBetweenBatchesMs: 1500 });
        fs.writeFileSync(`../data/xauusd_${tf}_bid.csv`, csv); console.log(tf, "rows", csv.split("\n").length - 1); break;
      } catch (e) { console.log(tf, "attempt", attempt, String(e).slice(0, 80)); await new Promise(r => setTimeout(r, 30000 * attempt)); }
    }
  }
})();
