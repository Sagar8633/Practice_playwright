const { chromium } = require('D:/Practice_Playwright/GOLD/pbd_counter_trend/duka_fetch/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Users/samja/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe' });
  const page = await browser.newPage({ viewport: { width: 400, height: 900 } });
  await page.goto('file:///D:/Practice_Playwright/GOLD/pbd_counter_trend/report.html');
  await page.waitForTimeout(1000);
  const bad = await page.evaluate(() => { const out=[]; document.querySelectorAll('body *').forEach(e=>{ const r=e.getBoundingClientRect(); if(r.right>402 && !e.closest('.tbl') && !e.closest('nav.toc') && e.tagName!=='TBODY'){ out.push(e.tagName+'.'+(e.className&&e.className.baseVal!==undefined?e.className.baseVal:e.className)+' right='+Math.round(r.right)+' w='+Math.round(r.width)); } }); return out.slice(0,25); });
  console.log(bad.join('\n'));
  await browser.close();
})();
