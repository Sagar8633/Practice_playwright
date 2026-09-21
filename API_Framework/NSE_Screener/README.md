# NSE Weekly Insider-Buying Screener

Finds **promoter market-purchase buys** filed with NSE in a given week, where the
promoter's holding **increased**, the deal was **≥ ₹1 crore**, and the company's
**total promoter holding is above 50%**. Outputs a self-contained HTML report.

## Run it

```bash
cd API_Framework/NSE_Screener

node screener.mjs            # default: last 7 days
node screener.mjs --days 5   # last 5 days
node screener.mjs --days 10  # last 10 days
node screener.mjs --days 30  # last 30 days (max)
```

The time window is fully configurable via `--days N` (capped at
`CFG.MAX_WINDOW_DAYS`, default 30). Change the default in `config.mjs`.

A Chromium window opens (this is required — see note below), the script fetches
and parses the filings, then writes the report to:

```
reports/nse-insider-screener-<date>_<time>.html
```

Open that file in any browser. No `npm install` needed — it reuses the Playwright
already installed in `API_Framework/node_modules`.

## Folder layout

```
NSE_Screener/
  screener.mjs        <- run this (orchestrator)
  config.mjs          <- all tunable thresholds & endpoints
  lib/
    nse-client.mjs    <- launches browser, warms cookies, fetches JSON
    ixbrl.mjs         <- downloads & parses each filing's iXBRL detail table
    report.mjs        <- promoter-% join + HTML rendering
    util.mjs          <- dates, formatting, helpers
  reports/            <- generated HTML reports land here
```

## What it filters (hard criteria — all from NSE data)

| Filter | Source |
|---|---|
| Category = Promoter / Promoter Group | filing iXBRL "Category of person" |
| Transaction = Buy | filing iXBRL "Transaction type" |
| Mode = Market Purchase (no gift/ESOP/off-market/sale) | filing iXBRL "Mode of acquisition" |
| Value ≥ ₹1 crore | filing iXBRL "Value of security" |
| Promoter % increased (post > prior) | filing iXBRL holding before/after |
| Total promoter holding > 50% | `corporate-share-holdings-master` (quarterly) |
| Promoter pledge ≤ 0% (unpledged) | shareholding-pattern XBRL (quarterly) |
| FII ≥ N% (optional, off by default) | shareholding-pattern XBRL (quarterly) |

Tune any of these in **`config.mjs`** (`CFG`):

- `REQUIRE_ZERO_PLEDGE` / `MAX_PLEDGE_PCT` — pledge filter (0 = must be unpledged).
- `MIN_FII_PCT` — `null` shows FII% without filtering; set a number to require it.

## Enrichment columns (real data, pulled per matched stock)

After the insider filters, each shortlisted stock's quarterly
shareholding-pattern XBRL is fetched once to populate:

- **Pledge%** — promoter shares pledged/encumbered (`0.00%` = clean).
- **FII%** — foreign-institution holding (`InstitutionsForeign`).

## What stays a manual "verify" column

- **Debt** — NSE's insider/shareholding feeds do **not** carry a debt figure, so
  this column shows `null` with a screener.in link to confirm debt-free by hand.
- **FII *increase*** — would need quarter-over-quarter comparison (two XBRLs per
  stock); currently the report shows the FII% *level*, not its change.

## Important: why a visible browser opens

NSE's Akamai bot-protection **blocks headless Chromium** (connection reset /
HTTP2 errors). A normal (headed) browser works reliably, so `CFG.HEADLESS` is
`false`. For an unattended weekly run, schedule it with Windows Task Scheduler —
the window will appear briefly and close itself.

## Notes

- `niftyindices.com` carries index data only (constituents / levels) — it has no
  insider or shareholding filings, so it is not a data source here.
- Data endpoints used are documented in `config.mjs`.
cd API_Framework/NSE_Screener
node screener.mjs --days 5     # or 7 / 10 / 30