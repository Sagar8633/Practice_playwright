// i2vsys.com automated audit harness
// Usage: node i2v-audit.mjs <mode>
//   modes: engines | links | responsive | throttle | forms
import { chromium, firefox, webkit, devices, request } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = 'https://www.i2vsys.com';
const OUT = 'd:/Practice_Playwright/i2v/out';
const SHOTS = path.join(OUT, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });

const PAGES = {
  'Home': '/',
  'Why-i2V (About)': '/why-choose-i2v/',
  'Products': '/products/',
  'Industries (Solutions)': '/industries-we-serve/',
  'Contact-Us': '/contact-us/',
  'Product-VMS': '/products/video-management-software/',
};
const EXTRA_PAGES = {
  'Careers': '/career/',
  'Blogs-News': '/newsroom-blog/',
  'Resources': '/resource-center/',
  'Our-Partners': '/our-partners/',
};

const METRICS_JS = `() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paint = performance.getEntriesByType('paint');
  const fcp = (paint.find(p => p.name === 'first-contentful-paint') || {}).startTime || null;
  const res = performance.getEntriesByType('resource').map(r => ({
    name: r.name, type: r.initiatorType, dur: Math.round(r.duration), size: r.transferSize || 0
  }));
  res.sort((a,b) => b.dur - a.dur);
  const imgs = Array.from(document.images).map(i => ({
    src: i.currentSrc || i.src, alt: i.getAttribute('alt'),
    complete: i.complete, nW: i.naturalWidth, nH: i.naturalHeight
  }));
  return {
    ttfb: nav.responseStart ? Math.round(nav.responseStart) : null,
    domContentLoaded: nav.domContentLoadedEventEnd ? Math.round(nav.domContentLoadedEventEnd) : null,
    loadEvent: nav.loadEventEnd ? Math.round(nav.loadEventEnd) : null,
    duration: nav.duration ? Math.round(nav.duration) : null,
    transferKB: Math.round(res.reduce((s,r)=>s+r.size,0)/1024),
    fcp: fcp ? Math.round(fcp) : null,
    resourceCount: res.length,
    slowest: res.slice(0,8),
    title: document.title,
    h1: (document.querySelector('h1')||{}).innerText || null,
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
    images: { total: imgs.length,
      missingAlt: imgs.filter(i => i.alt === null || i.alt.trim() === '').length,
      broken: imgs.filter(i => i.complete && i.nW === 0).map(i=>i.src) },
    linkCount: document.querySelectorAll('a[href]').length,
  };
}`;

async function auditPage(page, name, url) {
  const consoleErrors = [], pageErrors = [], failedReq = [], badResponses = [];
  const onConsole = m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0,300)); };
  const onPageErr = e => pageErrors.push(String(e).slice(0,300));
  const onFailed = r => failedReq.push({ url: r.url().slice(0,200), err: r.failure()?.errorText });
  const onResp = r => { if (r.status() >= 400) badResponses.push({ url: r.url().slice(0,200), status: r.status() }); };
  page.on('console', onConsole); page.on('pageerror', onPageErr);
  page.on('requestfailed', onFailed); page.on('response', onResp);
  let navStatus = null, navError = null;
  const t0 = Date.now();
  try {
    const resp = await page.goto(BASE + url, { waitUntil: 'load', timeout: 45000 });
    navStatus = resp ? resp.status() : null;
    await page.waitForTimeout(2500);
  } catch (e) { navError = String(e).split('\n')[0]; }
  const wallMs = Date.now() - t0;
  let metrics = {};
  try { metrics = await page.evaluate(`(${METRICS_JS})()`); } catch (e) { metrics = { evalError: String(e).slice(0,200) }; }
  page.off('console', onConsole); page.off('pageerror', onPageErr);
  page.off('requestfailed', onFailed); page.off('response', onResp);
  return { name, url, navStatus, navError, wallMs, metrics,
    consoleErrors, pageErrors, failedReq: failedReq.slice(0,15), badResponses: badResponses.slice(0,15) };
}

async function runEngines() {
  const engines = { chromium, firefox, webkit };
  const results = {};
  for (const [eng, launcher] of Object.entries(engines)) {
    console.error(`\n### ENGINE: ${eng}`);
    const browser = await launcher.launch();
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    results[eng] = [];
    for (const [name, url] of Object.entries(PAGES)) {
      const page = await ctx.newPage();
      const r = await auditPage(page, name, url);
      console.error(`  ${eng} ${name}: status=${r.navStatus} wall=${r.wallMs}ms load=${r.metrics.loadEvent} fcp=${r.metrics.fcp} consoleErr=${r.consoleErrors.length} 404s=${r.badResponses.length}`);
      if (eng === 'chromium') await page.screenshot({ path: path.join(SHOTS, `desktop-${name}.png`), fullPage: false }).catch(()=>{});
      results[eng].push(r);
      await page.close();
    }
    await browser.close();
  }
  fs.writeFileSync(path.join(OUT, 'engines.json'), JSON.stringify(results, null, 2));
  console.error('\nWROTE engines.json');
}

async function runLinks() {
  // Gather links from all primary + extra pages, then check each unique link.
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const all = new Set();
  const pageMap = {};
  for (const [name, url] of Object.entries({ ...PAGES, ...EXTRA_PAGES })) {
    try {
      await page.goto(BASE + url, { waitUntil: 'load', timeout: 45000 });
      await page.waitForTimeout(1500);
      const hrefs = await page.evaluate(() => Array.from(document.querySelectorAll('a[href]'))
        .map(a => a.href).filter(h => h.startsWith('http')));
      pageMap[name] = hrefs.length;
      hrefs.forEach(h => all.add(h.split('#')[0]));
      console.error(`  collected ${hrefs.length} links from ${name}`);
    } catch (e) { console.error(`  FAIL collect ${name}: ${String(e).split('\n')[0]}`); }
  }
  await browser.close();
  const links = [...all].filter(Boolean);
  console.error(`\nChecking ${links.length} unique links...`);
  const rc = await request.newContext({ ignoreHTTPSErrors: true, timeout: 30000 });
  const checked = [];
  for (const link of links) {
    let status = null, err = null, method = 'HEAD';
    try {
      let resp = await rc.head(link, { maxRedirects: 5 });
      status = resp.status();
      if (status === 405 || status === 403 || status === 501) { method = 'GET'; resp = await rc.get(link, { maxRedirects: 5 }); status = resp.status(); }
    } catch (e) { err = String(e).split('\n')[0].slice(0,160); }
    const internal = link.includes('i2vsys.com');
    checked.push({ link, status, err, internal, method });
    if ((status && status >= 400) || err) console.error(`  BAD ${status||err} ${link}`);
  }
  await rc.dispose();
  fs.writeFileSync(path.join(OUT, 'links.json'), JSON.stringify({ pageMap, total: links.length, checked }, null, 2));
  console.error(`\nWROTE links.json — ${checked.filter(c=>(c.status&&c.status>=400)||c.err).length} problem links`);
}

async function runResponsive() {
  const profiles = [
    { name: 'iPhone-15-Pro', device: devices['iPhone 15 Pro'] },
    { name: 'Pixel-7', device: devices['Pixel 7'] },
    { name: 'iPad-Pro-11', device: devices['iPad Pro 11'] },
    { name: 'Galaxy-Tab', device: devices['Galaxy Tab S4'] },
  ];
  const targets = { Home: '/', Products: '/products/', Contact: '/contact-us/' };
  const browser = await chromium.launch();
  const results = [];
  for (const p of profiles) {
    for (const orient of ['portrait', 'landscape']) {
      const base = p.device;
      const vp = orient === 'landscape'
        ? { width: base.viewport.height, height: base.viewport.width }
        : base.viewport;
      const ctx = await browser.newContext({ ...base, viewport: vp });
      for (const [tname, url] of Object.entries(targets)) {
        const page = await ctx.newPage();
        let data = {};
        try {
          await page.goto(BASE + url, { waitUntil: 'load', timeout: 45000 });
          await page.waitForTimeout(2000);
          data = await page.evaluate(() => {
            const hamburger = document.querySelector(
              '.menu-toggle,.hamburger,.navbar-toggler,[class*="mobile-menu"],[class*="menu-icon"],button[aria-label*="enu" i]');
            return {
              scrollW: document.documentElement.scrollWidth,
              innerW: window.innerWidth,
              horizontalScroll: document.documentElement.scrollWidth > window.innerWidth + 2,
              hamburgerFound: !!hamburger,
              bodyFont: parseFloat(getComputedStyle(document.body).fontSize),
            };
          });
          if (orient === 'portrait' && tname === 'Home')
            await page.screenshot({ path: path.join(SHOTS, `mobile-${p.name}.png`), fullPage: false }).catch(()=>{});
        } catch (e) { data = { error: String(e).split('\n')[0] }; }
        results.push({ device: p.name, orient, page: tname, vp, ...data });
        console.error(`  ${p.name} ${orient} ${tname}: hScroll=${data.horizontalScroll} hamburger=${data.hamburgerFound} font=${data.bodyFont}`);
        await page.close();
      }
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'responsive.json'), JSON.stringify(results, null, 2));
  console.error('\nWROTE responsive.json');
}

async function runThrottle() {
  // Chromium CDP network emulation (Fast 3G / Slow 3G / 4G-ish)
  const conditions = {
    'Slow-3G': { downloadThroughput: 400*1024/8, uploadThroughput: 400*1024/8, latency: 400 },
    'Fast-3G': { downloadThroughput: 1.6*1024*1024/8, uploadThroughput: 750*1024/8, latency: 150 },
    '4G': { downloadThroughput: 9*1024*1024/8, uploadThroughput: 9*1024*1024/8, latency: 60 },
  };
  const results = [];
  for (const [label, cond] of Object.entries(conditions)) {
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    const client = await ctx.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', { offline: false, ...cond });
    const t0 = Date.now();
    let load = null, fcp = null;
    try {
      await page.goto(BASE + '/', { waitUntil: 'load', timeout: 90000 });
      const m = await page.evaluate(() => {
        const nav = performance.getEntriesByType('navigation')[0]||{};
        const p = performance.getEntriesByType('paint').find(x=>x.name==='first-contentful-paint');
        return { load: Math.round(nav.loadEventEnd), fcp: p?Math.round(p.startTime):null };
      });
      load = m.load; fcp = m.fcp;
    } catch (e) { load = 'timeout/'+String(e).split('\n')[0].slice(0,60); }
    const wall = Date.now() - t0;
    results.push({ label, wallMs: wall, loadEvent: load, fcp });
    console.error(`  ${label}: wall=${wall}ms load=${load} fcp=${fcp}`);
    await browser.close();
  }
  fs.writeFileSync(path.join(OUT, 'throttle.json'), JSON.stringify(results, null, 2));
  console.error('\nWROTE throttle.json');
}

async function runForms() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  const out = { contact: {} };
  await page.goto(BASE + '/contact-us/', { waitUntil: 'load', timeout: 45000 });
  await page.waitForTimeout(2000);
  // Inventory forms
  out.contact.inventory = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('form')).map((f,i) => ({
      idx: i, action: f.action, method: f.method,
      fields: Array.from(f.querySelectorAll('input,textarea,select')).map(el => ({
        tag: el.tagName.toLowerCase(), type: el.type||null, name: el.name||null,
        required: el.required, placeholder: el.placeholder||null,
        inputmode: el.getAttribute('inputmode'), autocomplete: el.getAttribute('autocomplete')
      })),
      hasSubmit: !!f.querySelector('[type=submit],button')
    }));
  });
  console.error('  forms found:', out.contact.inventory.length);
  // Empty submit test (validation)
  try {
    const form = page.locator('form').first();
    const submit = form.locator('[type=submit], button[type=submit], button').first();
    await submit.click({ timeout: 5000 });
    await page.waitForTimeout(1500);
    out.contact.emptySubmit = await page.evaluate(() => {
      const invalid = Array.from(document.querySelectorAll('input,textarea,select')).filter(el => !el.checkValidity());
      const visibleErrs = Array.from(document.querySelectorAll('[class*="error" i],[class*="invalid" i],.wpcf7-not-valid-tip,[role=alert]'))
        .map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,10);
      return { browserInvalidCount: invalid.length,
        firstInvalid: invalid[0] ? (invalid[0].name||invalid[0].type) : null,
        visibleErrors: visibleErrs };
    });
    console.error('  emptySubmit:', JSON.stringify(out.contact.emptySubmit));
  } catch (e) { out.contact.emptySubmit = { error: String(e).split('\n')[0] }; }
  // Invalid email test
  try {
    const emailField = page.locator('input[type=email], input[name*="mail" i]').first();
    if (await emailField.count()) {
      await emailField.fill('not-an-email');
      out.contact.invalidEmail = await emailField.evaluate(el => ({ valid: el.checkValidity(), msg: el.validationMessage }));
      console.error('  invalidEmail:', JSON.stringify(out.contact.invalidEmail));
    }
  } catch (e) { out.contact.invalidEmail = { error: String(e).split('\n')[0] }; }
  await page.screenshot({ path: path.join(SHOTS, 'contact-form.png'), fullPage: true }).catch(()=>{});
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'forms.json'), JSON.stringify(out, null, 2));
  console.error('\nWROTE forms.json');
}

async function runMisc() {
  const out = {};
  const browser = await chromium.launch();
  // --- Mobile menu open test ---
  const mctx = await browser.newContext({ ...devices['iPhone 15 Pro'] });
  const mp = await mctx.newPage();
  await mp.goto(BASE + '/', { waitUntil: 'load', timeout: 45000 });
  await mp.waitForTimeout(1500);
  out.mobileMenu = await mp.evaluate(() => {
    const btn = document.querySelector('header button, .menu-toggle, [class*="hamburger"], [class*="toggle"], svg + *');
    return { headerButtons: document.querySelectorAll('header button, header a[role=button]').length };
  });
  // Try clicking the first header button and see if nav links become visible
  try {
    const before = await mp.locator('nav a:visible, header a:visible').count();
    await mp.locator('header button, [aria-label*="menu" i], [class*="toggle"]').first().click({ timeout: 4000 });
    await mp.waitForTimeout(800);
    const after = await mp.locator('nav a:visible, header a:visible').count();
    out.mobileMenu.linksVisibleBefore = before;
    out.mobileMenu.linksVisibleAfter = after;
    out.mobileMenu.opened = after > before;
    await mp.screenshot({ path: path.join(SHOTS, 'mobile-menu-open.png') }).catch(()=>{});
  } catch (e) { out.mobileMenu.clickErr = String(e).split('\n')[0]; }
  await mctx.close();

  // --- Desktop a11y + nav + tel/mailto ---
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/contact-us/', { waitUntil: 'load', timeout: 45000 });
  await page.waitForTimeout(1500);
  out.contactLinks = await page.evaluate(() => ({
    tel: Array.from(document.querySelectorAll('a[href^="tel:"]')).map(a=>a.getAttribute('href')),
    mailto: Array.from(document.querySelectorAll('a[href^="mailto:"]')).map(a=>a.getAttribute('href')),
  }));
  // keyboard focus visibility: tab a few times, check focused element + outline
  const focusTrail = [];
  for (let i=0;i<6;i++){
    await page.keyboard.press('Tab');
    const f = await page.evaluate(() => {
      const el = document.activeElement;
      const s = getComputedStyle(el);
      return { tag: el.tagName, text: (el.innerText||el.value||el.getAttribute('aria-label')||'').slice(0,30),
        outline: s.outlineStyle+' '+s.outlineWidth, boxShadow: s.boxShadow!=='none' };
    });
    focusTrail.push(f);
  }
  out.keyboardFocus = focusTrail;
  // skip link / lang / landmarks
  await page.goto(BASE + '/', { waitUntil: 'load', timeout: 45000 });
  out.a11yLandmarks = await page.evaluate(() => ({
    htmlLang: document.documentElement.lang,
    h1Count: document.querySelectorAll('h1').length,
    skipLink: !!document.querySelector('a[href^="#"][class*="skip" i], a[href="#content"], a[href="#main"]'),
    nav: document.querySelectorAll('nav').length,
    main: document.querySelectorAll('main, [role=main]').length,
    headerEl: document.querySelectorAll('header').length,
    footerEl: document.querySelectorAll('footer').length,
    viewportMeta: (document.querySelector('meta[name=viewport]')||{}).content || null,
  }));
  // Active nav state on Products page
  await page.goto(BASE + '/products/', { waitUntil: 'load', timeout: 45000 });
  out.activeNav = await page.evaluate(() => {
    const cur = Array.from(document.querySelectorAll('nav a, header a')).filter(a =>
      a.getAttribute('aria-current') || /current|active/i.test(a.className) ||
      (a.href && a.href.replace(/\/$/,'') === location.href.replace(/\/$/,'')));
    return cur.slice(0,5).map(a => ({ text: (a.innerText||'').slice(0,30), cls: a.className.slice(0,60), ariaCurrent: a.getAttribute('aria-current') }));
  });
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'misc.json'), JSON.stringify(out, null, 2));
  console.error('WROTE misc.json\n', JSON.stringify(out, null, 2));
}

const mode = process.argv[2];
const map = { engines: runEngines, links: runLinks, responsive: runResponsive, throttle: runThrottle, forms: runForms, misc: runMisc };
if (!map[mode]) { console.error('Unknown mode:', mode, '— use', Object.keys(map).join('|')); process.exit(1); }
map[mode]().then(() => process.exit(0)).catch(e => { console.error('FATAL', e); process.exit(1); });
