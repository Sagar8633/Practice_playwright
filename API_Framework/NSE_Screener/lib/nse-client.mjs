// NSE session handling: launch a (headed) browser, warm up cookies, fetch JSON.

import { chromium } from 'playwright';
import { CFG, BASE, WARMUP_URL } from '../config.mjs';
import { log } from './util.mjs';

export async function launchSession() {
  const browser = await chromium.launch({
    headless: CFG.HEADLESS,
    args: [
      '--disable-http2',                       // NSE+headless throws ERR_HTTP2_PROTOCOL_ERROR otherwise
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--disable-features=IsolateOrigins,site-per-process',
    ],
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1366, height: 768 },
    locale: 'en-IN',
  });
  const page = await context.newPage();
  // Drop heavy assets: we only need the Akamai/session cookies from the HTML response.
  await page.route(/\.(png|jpe?g|gif|svg|webp|woff2?|ttf|mp4|css)(\?|$)/i, r => r.abort());

  log('Warming up session (establishing NSE cookies)...');
  await page.goto(BASE, { waitUntil: 'commit', timeout: 60_000 });
  await page.waitForTimeout(4000);

  return { browser, context, page };
}

export async function getJson(context, url, page, tries = 3) {
  for (let i = 1; i <= tries; i++) {
    const resp = await context.request.get(url, {
      headers: {
        accept: 'application/json, text/plain, */*',
        referer: WARMUP_URL,
        'x-requested-with': 'XMLHttpRequest',
      },
      timeout: 45_000,
    });
    const ct = resp.headers()['content-type'] || '';
    if (resp.ok() && ct.includes('json')) return resp.json();
    // bot-blocked or stale cookie -> re-warm and retry
    log(`  [retry ${i}/${tries}] ${url} -> ${resp.status()} (${ct.slice(0, 30)})`);
    await page.goto(BASE, { waitUntil: 'commit' });
    await page.waitForTimeout(1500 * i);
  }
  throw new Error(`Could not fetch JSON from ${url} after ${tries} tries (NSE likely blocked the session).`);
}
