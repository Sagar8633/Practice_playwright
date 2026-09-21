import { chromium, firefox, webkit } from 'playwright';

const PAGES = [
  { name: 'Home',     url: 'https://www.i2vsys.com/' },
  { name: 'Why i2V',  url: 'https://www.i2vsys.com/why-choose-i2v/' },
  { name: 'Products', url: 'https://www.i2vsys.com/products/' },
  { name: 'Contact',  url: 'https://www.i2vsys.com/contact-us/' },
];

const ENGINES = [
  { name: 'Chromium', launcher: chromium },
  { name: 'Firefox',  launcher: firefox },
  { name: 'WebKit',   launcher: webkit },
];

function collect() {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const res = performance.getEntriesByType('resource');
  let transfer = 0;
  res.forEach(r => transfer += r.transferSize || 0);
  const doc = document.documentElement;
  return {
    ttfb: Math.round((nav.responseStart || 0) - (nav.requestStart || 0)),
    load: Math.round(nav.loadEventEnd || 0),
    resources: res.length,
    transferMB: +(transfer / 1048576).toFixed(2),
    horizScroll: doc.scrollWidth > doc.clientWidth,
    scrollW: doc.scrollWidth,
    viewportW: doc.clientWidth
  };
}

const results = [];

for (const eng of ENGINES) {
  let browser;
  try {
    browser = await eng.launcher.launch();
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    for (const p of PAGES) {
      const page = await ctx.newPage();
      const errors = [];
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 120)); });
      page.on('pageerror', e => errors.push('PAGEERROR: ' + String(e).slice(0, 120)));
      let status = null;
      try {
        const resp = await page.goto(p.url, { waitUntil: 'load', timeout: 60000 });
        status = resp ? resp.status() : null;
        await page.waitForTimeout(2500);
        const m = await page.evaluate(collect);
        results.push({ engine: eng.name, page: p.name, status, errors: errors.length, errorSamples: errors.slice(0, 3), ...m });
      } catch (e) {
        results.push({ engine: eng.name, page: p.name, status, error: String(e).slice(0, 150), errors: errors.length });
      }
      await page.close();
    }
    await browser.close();
  } catch (e) {
    results.push({ engine: eng.name, fatal: String(e).slice(0, 200) });
    if (browser) await browser.close().catch(() => {});
  }
}

console.log(JSON.stringify(results, null, 2));
