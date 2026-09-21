// Fetches and parses the per-filing iXBRL transaction tables.

import { CFG, MODE_KEYWORDS } from '../config.mjs';
import { log } from './util.mjs';

export async function parseAllFilings(context, filings) {
  const queue = [...filings.entries()];
  const results = [];
  const workers = Array.from({ length: CFG.PARSE_CONCURRENCY }, async () => {
    const page = await context.newPage();
    while (queue.length) {
      const [idx, f] = queue.shift();
      const url = f.ixbrl || f.xmlFileName;
      if (!url || !/\.html?$/i.test(url)) continue; // need the human-readable iXBRL
      try {
        const html = await (await context.request.get(url, { timeout: 45_000 })).text();
        const clean = html
          .replace(/<script[\s\S]*?<\/script>/gi, '')
          .replace(/<link[^>]*>/gi, '');
        await page.setContent(clean, { waitUntil: 'domcontentloaded', timeout: 30_000 });
        const rows = await page.evaluate(parseTableInPage, { modes: MODE_KEYWORDS });
        for (const row of rows) {
          results.push({
            companyName: f.companyName,
            symbol: f.symbol,
            broadcast: f.broadcastDateTime,
            regulation: f.regulation,
            filingUrl: url,
            ...row,
          });
        }
      } catch (e) {
        log(`  [skip] ${f.symbol} (${idx}) parse failed: ${e.message}`);
      }
    }
    await page.close();
  });
  await Promise.all(workers);
  return results;
}

// Runs inside the page DOM. Token-based extraction so it survives the slight
// column shifts between Regulation 7(1) and 7(2) filing forms.
function parseTableInPage({ modes }) {
  const num = s => Number(String(s || '').replace(/[, ]/g, '').replace(/%/g, '')) || 0;
  const out = [];
  for (const tr of document.querySelectorAll('table tr')) {
    const cells = [...tr.querySelectorAll('td,th')].map(td => (td.innerText || '').trim());
    if (cells.length < 12 || !/^\d+$/.test(cells[0])) continue; // data rows start with Sr.No

    const txnIdx = cells.findIndex(c => /^(buy|sell)$/i.test(c));
    if (txnIdx < 4) continue;

    const txnType = cells[txnIdx];
    const value = num(cells[txnIdx - 1]);     // Value of security (Rs.)
    const qty = num(cells[txnIdx - 2]);       // securities acquired/disposed
    const priorPct = num(cells[txnIdx - 3]);  // % held prior
    const postPct = num(cells[txnIdx + 2]);   // % held post

    // category keyword sits among the early descriptor cells
    let category = '';
    for (let i = 1; i <= txnIdx - 4 && i < cells.length; i++) {
      if (/promoter|director|key managerial|kmp|designated|relative|trust|cfo|ceo|chief/i.test(cells[i])) {
        category = cells[i];
        break;
      }
    }
    const name = cells[3] && !/promoter|director/i.test(cells[3]) ? cells[3]
      : (cells[4] || cells[3] || '');

    // mode keyword sits after the transaction columns
    let mode = '';
    for (let i = txnIdx + 3; i < cells.length; i++) {
      const hit = modes.find(m => cells[i].toLowerCase() === m.toLowerCase());
      if (hit) { mode = cells[i]; break; }
    }
    if (!mode) { // looser contains-match fallback
      for (let i = txnIdx + 3; i < cells.length; i++) {
        const hit = modes.find(m => cells[i].toLowerCase().includes(m.toLowerCase()));
        if (hit) { mode = cells[i]; break; }
      }
    }

    out.push({ category, name, qty, value, priorPct, postPct, txnType, mode });
  }
  return out;
}
