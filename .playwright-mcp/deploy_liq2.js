async (page) => {
  const name = "Sagar_Liquidity";
  const p2 = await page.context().newPage();
  await p2.goto('http://127.0.0.1:8765/');
  const src = await p2.evaluate(() => fetch('/XAU_Liquidity_Sweeps.pine?t=' + Date.now()).then(r => r.text()));
  await p2.close();
  return await page.evaluate(async ([name, src]) => {
    const fd = new FormData();
    fd.append('source', src);
    const r = await fetch('https://pine-facade.tradingview.com/pine-facade/save/new?name=' + encodeURIComponent(name) + '&allow_overwrite=true', { method: 'POST', body: fd, credentials: 'include' });
    const t = await r.text();
    let j = null; try { j = JSON.parse(t) } catch (e) {}
    const errs = j && j.reason2 ? j.reason2.errors : null;
    const warns = j && j.reason2 ? j.reason2.warnings : (j && j.result && j.result.warnings) || null;
    return { origin: location.origin, status: r.status, srcLen: src.length, success: j && j.success,
      scriptIdPart: j && j.result && j.result.scriptIdPart, version: j && j.result && j.result.version,
      errors: errs, warnings: warns, raw: j ? undefined : t.slice(0, 400) };
  }, [name, src]);
}
