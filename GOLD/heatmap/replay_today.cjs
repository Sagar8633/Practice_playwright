// Replays today's candles through the page's signal rules: what did they see at each 5-minute close?
//   node replay_today.cjs 12      (hours to look back, default 10)
// Same engine code as the page; walls and zero gamma are rebuilt at each moment from the current options chain.
const fs = require('fs');
const heat = __dirname + '/';
const E = require(heat + 'gex_engine.js');
const data = JSON.parse(fs.readFileSync(heat + 'gex_data.js', 'utf8').replace(/^window\.GEX_DATA = /, '').replace(/;\s*$/, ''));
const hours = +process.argv[2] || 10;
const ist = t => new Date(t).toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' });
async function klines(interval, limit) {
  const r = await fetch(`https://fapi.binance.com/fapi/v1/klines?symbol=XAUUSDT&interval=${interval}&limit=${limit}`);      // the page's feed since 6 Nov 2026
  return (await r.json()).map(k => ({ t: k[0], o: +k[1], h: +k[2], l: +k[3], c: +k[4], v: +k[5], bv: +k[9] }));
}
(async () => {
  const [k1, k30, ref] = await Promise.all([klines('1m', 1500), klines('30m', 300), fetch('https://api.gold-api.com/price/XAU').then(r => r.json())]);
  const basis = k1[k1.length - 1].c - ref.price, px = p => (p - basis).toFixed(1);
  console.log(`now ${ist(Date.now())} IST | XAUUSDT ${k1[k1.length - 1].c} - XAUUSD ${ref.price} (gold-api, ${ref.updatedAtReadable}) = basis ${basis.toFixed(2)} | options data fetched ${ist(data.fetchedAt)} IST`);
  const from = Date.now() - hours * 3600e3, count = {}, rows = [];
  for (let i = 300; i < k1.length; i++) {
    const now = k1[i].t;
    if (now % 300e3 || now < from) continue;
    const m1 = k1.slice(0, i), price = m1[m1.length - 1].c, f = 1 / E.ozPerShare(now), spot = (price - basis) / f;
    const exps = E.expiries(data, now), near = new Set([exps[0].exp]), all = E.table(data, spot, now, null), t0 = E.table(data, spot, now, near);
    const w0 = E.wallsOi(t0.rows.filter(r => Math.abs(r.k / spot - 1) <= 0.08), 1), wa = E.walls(all.rows.filter(r => Math.abs(r.k / spot - 1) <= 0.08), 3), flip = E.gammaFlip(data, spot, now, near);
    const d = exps[0].dte + 'DTE', p = k => k * f + basis, lines = [];
    if (w0.puts[0]) lines.push({ side: 'support', p: p(w0.puts[0].k), w: 25, name: 'Put Wall ' + d });
    wa.puts.forEach((w, j) => lines.push({ side: 'support', p: p(w.k), w: 15, name: 'PW' + (j + 1) }));
    if (w0.calls[0]) lines.push({ side: 'resistance', p: p(w0.calls[0].k), w: 25, name: 'Call Wall ' + d });
    wa.calls.forEach((w, j) => lines.push({ side: 'resistance', p: p(w.k), w: 15, name: 'CW' + (j + 1) }));
    let buy = 0, vol = 0;
    for (const k of m1.slice(-15)) { buy += k.bv; vol += k.v; }
    const zones = E.tradeZones(k30.filter(k => k.t + 1800e3 <= now).slice(-299));
    const inp = E.inputs({ c5: E.aggregate(m1, 300e3), price, zones, lines: [], flip: null, profile: E.profile(m1, E.sessionStart(now), 0.5),
                           closes30: k30.filter(k => k.t + 1800e3 <= now).map(k => k.c), tape: vol ? (2 * buy - vol) / vol : 0 });
    const s = E.signal(inp);
    count[s.state] = (count[s.state] || 0) + 1;
    rows.push({ now, price, s, inp, flip: flip ? p(flip) : null, w0, f });
  }
  console.log(`5-minute closes checked in the last ${hours} h: ${rows.length} ->`, JSON.stringify(count));
  console.log('\nConfirmed setups (a candle closed back from a level):');
  for (const r of rows) {
    const s = r.s;
    if (s.entry === undefined) continue;
    console.log(`${ist(r.now)}  price ${px(r.price)}  ${s.state === 'skip' ? 'NO TRADE' : 'SIGNAL  '} ${s.side.toUpperCase().padEnd(4)} score ${String(s.score).padStart(2)}  ` +
                `stop ${px(s.stop)} target ${px(s.target)} (${s.targetName}) rr ${s.rr.toFixed(1)}  ${s.note || ''}\n         ` + s.reasons.map(q => `${q.pts >= 0 ? '+' : ''}${q.pts} ${q.text}`).join(' | '));
  }
  // the day's swing high and low in the window: what was there, and what did the rules say around it
  for (const [name, pick] of [['HIGH', (a, b) => (b.price > a.price ? b : a)], ['LOW', (a, b) => (b.price < a.price ? b : a)]]) {
    const top = rows.reduce(pick), k = rows.indexOf(top);
    console.log(`\nAround the ${name} of the window (${ist(top.now)} IST, ${px(top.price)}):`);
    console.log('  resistances: ' + top.inp.resistances.map(z => `${z.name} ${px(z.lo)}-${px(z.hi)}`).join('; '));
    console.log('  supports:    ' + top.inp.supports.map(z => `${z.name} ${px(z.lo)}-${px(z.hi)}`).join('; '));
    console.log(`  zero gamma ${top.flip ? px(top.flip) : 'none'} | 30m trend ${top.inp.trend} | regime ${top.inp.regime}`);
    for (const r of rows.slice(Math.max(0, k - 2), k + 5)) {
      const c = r.inp.c5[r.inp.c5.length - 1];
      console.log(`  ${ist(r.now)} candle o ${px(c.o)} h ${px(c.h)} l ${px(c.l)} c ${px(c.c)} -> ${r.s.state}${r.s.side ? ' ' + r.s.side : ''}${r.s.levels ? ' at ' + r.s.levels.join(' + ') : ''}${r.s.note ? ' (' + r.s.note + ')' : ''}`);
    }
  }
})();
