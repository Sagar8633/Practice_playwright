// ----------------------------------------------------------------------------
// Tunable configuration for the NSE weekly insider-buying screener.
// Edit thresholds here; nothing else in the codebase hard-codes them.
// ----------------------------------------------------------------------------

export const CFG = {
  WINDOW_DAYS: 7,                       // "this week" = last N days of filings. Override per run: --days N
  MAX_WINDOW_DAYS: 30,                  // hard cap on --days (NSE feed only spans recent filings)
  MIN_VALUE_RS: 1_00_00_000,            // >= 1 crore (Indian numbering)
  MIN_TOTAL_PROMOTER_PCT: 50,           // total promoter+group holding must exceed this
  REQUIRE_MARKET_PURCHASE: true,        // only "Market Purchase" mode (no gift/ESOP/off-market)
  REQUIRE_PROMOTER_CATEGORY: true,      // acquirer must be promoter / promoter group
  REQUIRE_PCT_INCREASE: true,           // post% > prior% (promoter % went up)

  // Enrichment from the quarterly shareholding-pattern XBRL (fetched only for matched stocks):
  REQUIRE_ZERO_PLEDGE: true,            // drop stocks whose promoter pledge % exceeds MAX_PLEDGE_PCT
  MAX_PLEDGE_PCT: 0,                    // "0% pledged" => null/zero. Raise (e.g. 0.5) to allow a small pledge.
  MIN_FII_PCT: null,                    // null = show FII% but don't filter. Set a number to require FII >= it.

  PARSE_CONCURRENCY: 4,                 // how many iXBRL / XBRL files to fetch at once
  HEADLESS: false,                      // NSE's Akamai blocks headless chromium; headed works (see README)
};

export const BASE = 'https://www.nseindia.com';
export const WARMUP_URL = `${BASE}/companies-listing/corporate-filings-insider-trading`;
export const PIT_LIST = `${BASE}/api/corporates-pit-gg?index=equities`;
export const SHP_MASTER = `${BASE}/api/corporate-share-holdings-master?index=equities`;

// Modes that appear in the "Mode of acquisition / disposal" column of iXBRL filings.
export const MODE_KEYWORDS = ['Market Purchase', 'Market Sale', 'Off Market', 'Off-Market',
  'Gift', 'ESOP', 'Inter-se Transfer', 'Inter-se', 'Pledge', 'Invocation',
  'Revocation', 'Encumbrance', 'Preferential', 'Rights', 'Bonus', 'Conversion',
  'Allotment', 'Buyback', 'Public', 'Tender'];

// Acquirer categories we keep (the promoter thesis).
export const CATEGORY_RE = /promoter|promoter group/i;
