// Quarterly shareholding-pattern data: total promoter %, promoter pledge %, FII %.
// The master list gives one XBRL file per symbol; we parse it only for the
// handful of stocks that already passed the insider-buy filters.

import { CFG } from '../config.mjs';
import { log, parseNseDate } from './util.mjs';

// symbol -> { pct (promoter total %), xbrl (url), asOf }  using the latest filing.
export function buildPromoterMap(masterRows) {
  const m = new Map();
  for (const r of masterRows) {
    const pct = Number(r.pr_and_prgrp);
    if (!r.symbol || Number.isNaN(pct)) continue;
    const d = parseNseDate(r.date);
    const ms = d ? d.getTime() : 0;
    const prev = m.get(r.symbol);
    if (!prev || ms > prev.ms) m.set(r.symbol, { pct, xbrl: r.xbrl, asOf: r.date, ms });
  }
  return m;
}

// Parse one shareholding XBRL -> { pledgePct, fiiPct } (percentages, or null if absent).
function parseShpXbrl(xml) {
  // context id -> member local-names
  const ctx = {};
  for (const m of xml.matchAll(/<xbrli:context id="([^"]+)">([\s\S]*?)<\/xbrli:context>/g)) {
    ctx[m[1]] = [...m[2].matchAll(/explicitMember[^>]*>([^<]+)</g)].map(x => x[1].split(':').pop());
  }
  const facts = {};
  for (const f of xml.matchAll(/<in-bse-shp:([A-Za-z0-9]+) contextRef="([^"]+)"[^>]*>([^<]*)<\/in-bse-shp:[A-Za-z0-9]+>/g)) {
    (facts[f[1]] ||= []).push({ members: ctx[f[2]] || [], val: Number(f[3]) });
  }

  // promoter pledge %
  const pledges = (facts.EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares || [])
    .filter(x => x.members.some(m => /Promoter/i.test(m)) && !Number.isNaN(x.val));
  const pledgePct = pledges.length ? Math.max(...pledges.map(x => x.val)) : 0;

  // FII % = aggregate foreign institutions, else sum of FPI category I + II
  const shp = (facts.ShareholdingAsAPercentageOfTotalNumberOfShares || []).filter(x => !Number.isNaN(x.val));
  const agg = shp.find(x => x.members.some(m => /^InstitutionsForeign$|InstitutionsForeignMember/i.test(m)));
  let fiiPct;
  if (agg) {
    fiiPct = agg.val;
  } else {
    const cats = shp.filter(x => x.members.some(m => /ForeignPortfolioInvestor/i.test(m)));
    fiiPct = cats.length ? cats.reduce((s, x) => s + x.val, 0) : null;
  }
  return { pledgePct, fiiPct };
}

// Attach { pledgePct, fiiPct } to each match by fetching its shareholding XBRL once per symbol.
export async function enrichShareholding(context, matches, promoterMeta) {
  const symbols = [...new Set(matches.map(m => m.symbol))];
  const cache = new Map();
  const queue = [...symbols];
  log(`Enriching ${symbols.length} symbols with pledge % / FII % from shareholding XBRL...`);

  const workers = Array.from({ length: CFG.PARSE_CONCURRENCY }, async () => {
    while (queue.length) {
      const sym = queue.shift();
      const meta = promoterMeta.get(sym);
      if (!meta?.xbrl) { cache.set(sym, { pledgePct: null, fiiPct: null, shpAsOf: null }); continue; }
      try {
        const xml = await (await context.request.get(meta.xbrl, { timeout: 45_000 })).text();
        cache.set(sym, { ...parseShpXbrl(xml), shpAsOf: meta.asOf, shpUrl: meta.xbrl });
      } catch (e) {
        log(`  [skip] ${sym} shareholding XBRL failed: ${e.message}`);
        cache.set(sym, { pledgePct: null, fiiPct: null, shpAsOf: null });
      }
    }
  });
  await Promise.all(workers);

  for (const m of matches) Object.assign(m, cache.get(m.symbol));
  return matches;
}
