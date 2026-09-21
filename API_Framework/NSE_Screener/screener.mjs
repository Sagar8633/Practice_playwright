// ----------------------------------------------------------------------------
// NSE Weekly Insider-Buying Screener  --  run this file.
//
//   node screener.mjs            -> last 7 days
//   node screener.mjs --days 14  -> custom window
//
// Output: an HTML report in ./reports/ for that week's findings.
// See README.md for what is and isn't filtered, and the headed-browser note.
// ----------------------------------------------------------------------------

import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { CFG, PIT_LIST, SHP_MASTER, CATEGORY_RE } from './config.mjs';
import { launchSession, getJson } from './lib/nse-client.mjs';
import { parseAllFilings } from './lib/ixbrl.mjs';
import { buildPromoterMap, enrichShareholding } from './lib/shareholding.mjs';
import { renderHtml } from './lib/report.mjs';
import { log, asArray, withinWindow, argNum, rsToCr, nowStamp } from './lib/util.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(HERE, 'reports');
const windowDays = Math.min(argNum('--days', CFG.WINDOW_DAYS), CFG.MAX_WINDOW_DAYS);

(async () => {
  const { browser, context, page } = await launchSession();
  try {
    log('Fetching PIT filing list...');
    const pitAll = asArray(await getJson(context, PIT_LIST, page));
    const filings = pitAll.filter(f => withinWindow(f.broadcastDateTime, windowDays));
    log(`  ${pitAll.length} total filings, ${filings.length} within last ${windowDays} day(s).`);

    log('Fetching shareholding master (for total promoter %)...');
    const promoterMeta = buildPromoterMap(asArray(await getJson(context, SHP_MASTER, page)));
    log(`  promoter holding known for ${promoterMeta.size} symbols.`);

    log(`Parsing ${filings.length} iXBRL filings (concurrency ${CFG.PARSE_CONCURRENCY})...`);
    const allRows = await parseAllFilings(context, filings);
    log(`  extracted ${allRows.length} transaction rows.`);

    // --------------------------- apply criteria -----------------------------
    const matches = [];
    for (const r of allRows) {
      if (CFG.REQUIRE_PROMOTER_CATEGORY && !CATEGORY_RE.test(r.category)) continue;
      if (r.txnType.toLowerCase() !== 'buy') continue;
      if (CFG.REQUIRE_MARKET_PURCHASE && !/market\s*purchase/i.test(r.mode)) continue;
      if (r.value < CFG.MIN_VALUE_RS) continue;
      if (CFG.REQUIRE_PCT_INCREASE && !(r.postPct > r.priorPct)) continue;

      const totalPromoter = promoterMeta.get(r.symbol)?.pct;
      // total-promoter>50% is applied when known; unknown is flagged, not dropped.
      if (totalPromoter != null && totalPromoter <= CFG.MIN_TOTAL_PROMOTER_PCT) continue;

      matches.push({ ...r, totalPromoter });
    }

    // Dedupe identical transactions reported across original+revised filings.
    const seen = new Set();
    let deduped = matches.filter(r => {
      const k = `${r.symbol}|${r.name}|${r.qty}|${r.value}|${r.priorPct}|${r.postPct}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });

    // Enrich the (small) shortlist with promoter pledge % and FII % from XBRL, then filter.
    await enrichShareholding(context, deduped, promoterMeta);
    const before = deduped.length;
    deduped = deduped.filter(r => {
      if (CFG.REQUIRE_ZERO_PLEDGE && r.pledgePct != null && r.pledgePct > CFG.MAX_PLEDGE_PCT) return false;
      if (CFG.MIN_FII_PCT != null && r.fiiPct != null && r.fiiPct < CFG.MIN_FII_PCT) return false;
      return true;
    });
    deduped.sort((a, b) => b.value - a.value);
    log(`MATCHES: ${deduped.length} (dropped ${before - deduped.length} on pledge/FII) promoter market-buys >= ${rsToCr(CFG.MIN_VALUE_RS)} with rising %.`);

    mkdirSync(OUT_DIR, { recursive: true });
    const stamp = nowStamp();
    const outFile = join(OUT_DIR, `nse-insider-screener-${stamp}.html`);
    writeFileSync(outFile, renderHtml(deduped, {
      stamp, windowDays, filingCount: filings.length, rowCount: allRows.length,
    }));
    log(`\nReport written: ${outFile}`);
  } catch (err) {
    console.error('\n[FATAL]', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
