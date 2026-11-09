#!/usr/bin/env node
// Checks for gex_engine.js. Run after gex_fetch.cjs:  node gex_test.cjs
'use strict';
const fs = require('fs');
const path = require('path');
const E = require('./gex_engine.js');

let failed = 0;
function check(name, ok, detail) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  - ' + detail : ''}`);
  if (!ok) failed++;
}

// ---- synthetic checks (no data file needed)
const factor = 1 / E.ozPerShare(Date.UTC(2026, 10, 5));
check('GLD -> gold factor on 5 Nov 2026 is 10.92', Math.abs(factor - 10.92) < 0.01, factor.toFixed(3));
check('16:00 New York in November is 21:00 UTC', new Date(E.nyClose('261106')).getUTCHours() === 21);
check('16:00 New York in July is 20:00 UTC', new Date(E.nyClose('260706')).getUTCHours() === 20);
check('days to expiry', E.dte('261106', Date.UTC(2026, 10, 6, 8)) === 0 && E.dte('261109', Date.UTC(2026, 10, 6, 8)) === 3);
check('session starts 18:00 New York the day before', E.sessionStart(Date.UTC(2026, 10, 6, 8)) === Date.UTC(2026, 10, 5, 23));
check('gamma peaks at the money', E.bsGamma(100, 100, 0.2, 0.01) > E.bsGamma(100, 103, 0.2, 0.01) && E.bsGamma(100, 0, 0.2, 0.01) === 0);

// one put-heavy strike below and one call-heavy strike above: net gamma must flip between them
const now = E.nyClose('261105');
const toy = { contracts: [['261106', 1, 95, 0.2, 1000, 0, 0], ['261106', 0, 105, 0.2, 1000, 0, 0]] };
const flip = E.gammaFlip(toy, 100, now, null);
check('gamma flip between a put strike and a call strike', flip > 95 && flip < 105, flip && flip.toFixed(2));
const t = E.table(toy, 100, now, null);
check('table: calls and puts kept apart per strike', t.rows.length === 2 && t.rows[0].pg > 0 && t.rows[0].cg === 0 && t.rows[1].cg > 0);
const tw = E.walls(t.rows, 3);
check('walls: call wall = biggest positive net strike, put wall = biggest negative',
      tw.calls.length === 1 && tw.calls[0].k === 105 && tw.puts.length === 1 && tw.puts[0].k === 95 && tw.puts[0].v < 0);

// 30 quiet candles, a small down candle, then a strong up candle: one demand zone on the down candle
const quiet = [];
for (let i = 0; i < 30; i++) quiet.push({ t: i, o: 100, h: 100.6, l: 99.4, c: i % 2 ? 100.2 : 99.8 });
const base = { t: 30, o: 100, h: 100.2, l: 99.2, c: 99.5 }, impulse = { t: 31, o: 99.5, h: 103.2, l: 99.4, c: 103 };
let z = E.zones(quiet.concat([base, impulse]));
check('demand zone on the last down candle before an up impulse',
      z.length === 1 && z[0].type === 'demand' && z[0].bottom === 99.2 && z[0].top === 100 && !z[0].tested, JSON.stringify(z[0]));
z = E.zones(quiet.concat([base, impulse, { t: 32, o: 103, h: 103.1, l: 99.8, c: 102 }]));
check('a candle dipping into the zone marks it tested', z.length === 1 && z[0].tested);
z = E.zones(quiet.concat([base, impulse, { t: 32, o: 103, h: 103.1, l: 98.5, c: 98.9 }]));
check('a close below the zone removes it', !z.some(x => x.type === 'demand'));

// ---- swing boxes (the page's buy / sell zones): 20 quiet candles, a candle that makes a high, then a lower one
const flat = [];
for (let i = 0; i < 20; i++) flat.push({ t: i, o: 100, h: 100.5, l: 99.5, c: i % 2 ? 100.1 : 99.9 });
const peak = { t: 20, o: 100, h: 103, l: 99.8, c: 102.5 }, lower = { t: 21, o: 102.5, h: 102.6, l: 100.5, c: 100.8 };
let bx = E.boxes(flat.concat([peak]));
check('swing box: nothing until the next candle has closed lower', bx.length === 0);
bx = E.boxes(flat.concat([peak, lower]));
check('swing box: sell zone on the swing-high candle, one ATR tall at most',
      bx.length === 1 && bx[0].type === 'supply' && bx[0].top === 103 && Math.abs(bx[0].bottom - 102) < 1e-9 && !bx[0].tested && bx[0].confirmed === 21, JSON.stringify(bx[0]));
bx = E.boxes(flat.concat([peak, lower, { t: 22, o: 100.8, h: 102.2, l: 100.6, c: 101 }]));
check('swing box: price that never left the box does not count as a test', bx.length === 1 && !bx[0].tested);
bx = E.boxes(flat.concat([peak, lower, { t: 22, o: 100.8, h: 101.2, l: 100, c: 100.5 }, { t: 23, o: 100.5, h: 102.3, l: 100.4, c: 101 }]));
check('swing box: leaving and coming back marks it tested', bx.length === 1 && bx[0].tested);
bx = E.boxes(flat.concat([peak, lower, { t: 22, o: 100.8, h: 103.6, l: 100.7, c: 103.4 }]));
check('swing box: a close above the box removes it', !bx.some(x => x.type === 'supply'));

// 30-minute candles: the same shape. The 1-hour box only joins once its own next hour has closed.
const M30 = 1800e3, half = (i, k) => Object.assign({ v: 1, bv: 0.5 }, k, { t: i * M30 }), c30 = [];
for (let i = 0; i < 40; i++) c30.push(half(i, { o: 100, h: 100.5, l: 99.5, c: i % 2 ? 100.1 : 99.9 }));
c30.push(half(40, peak), half(41, lower), half(42, { o: 100.8, h: 101, l: 100.2, c: 100.6 }));
let tz = E.tradeZones(c30);
check('trade zones: 30m sell zone, half an ATR tall, while the next hour is still open',
      tz.length === 1 && tz[0].tf === '30m' && tz[0].top === 103 && Math.abs(tz[0].bottom - 102.5) < 1e-9, JSON.stringify(tz[0]));
tz = E.tradeZones(c30.concat([half(43, { o: 100.6, h: 100.9, l: 100.3, c: 100.5 })]));
check('trade zones: the 1h swing box on the same high is merged into it', tz.length === 1 && tz[0].tf === '30m & 1h' && tz[0].type === 'supply', JSON.stringify(tz.map(x => x.tf)));
const named = E.inputs({ c5: c30, price: 100, zones: tz, lines: [], flip: null, profile: null, closes30: [], tape: 0 });
check('trade zones are named SELL / BUY zone for the guide', named.resistances.length === 1 && named.resistances[0].name === 'SELL zone 30m & 1h', named.resistances.map(r => r.name).join());

// ---- absorption: 130 quiet minutes, then 5 minutes of heavy selling that ends back near the top of its range
const mins = [], quietMin = i => ({ t: i * 60e3, o: 100, h: 100.2, l: 99.8, c: 100, v: 10, bv: 5 });
for (let i = 0; i < 130; i++) mins.push(quietMin(i));
const sold = [[100, 100, 99.4, 99.5], [99.5, 99.6, 99, 99.2], [99.2, 99.8, 99.1, 99.7], [99.7, 100, 99.6, 99.9], [99.9, 100.1, 99.8, 100]]
  .map(([o, h, l, c], i) => ({ t: (130 + i) * 60e3, o, h, l, c, v: 40, bv: 10 }));
let ab = E.absorption(mins.concat(sold));
check('absorption: heavy selling that price did not follow = buyers absorbed, at the low of the move',
      ab.length === 1 && ab[0].kind === 'buy' && ab[0].bottom === 99 && ab[0].top > 99.5 && ab[0].top < 99.65 && ab[0].share < -0.3 && ab[0].ratio > 2, JSON.stringify(ab[0]));
ab = E.absorption(mins.concat(sold, [{ t: 135 * 60e3, o: 100, h: 100, l: 98.5, c: 98.8, v: 10, bv: 5 }]));
check('absorption: a close below the area removes it', ab.length === 0);
const fell = sold.map((k, i) => ({ t: k.t, o: 100 - i * 0.3, h: 100.05 - i * 0.3, l: 99.6 - i * 0.3, c: 99.7 - i * 0.3, v: 40, bv: 10 }));
check('absorption: heavy selling that price did follow is not absorption', E.absorption(mins.concat(fell)).length === 0);
const bought = sold.map(k => ({ t: k.t, o: 200 - k.o, h: 200 - k.l, l: 200 - k.h, c: 200 - k.c, v: 40, bv: 30 }));
ab = E.absorption(mins.concat(bought));
check('absorption: mirror case, heavy buying that fails = sellers absorbed, at the high', ab.length === 1 && ab[0].kind === 'sell' && ab[0].top === 101 && ab[0].share > 0.3, JSON.stringify(ab[0]));
check('absorption: quiet candles give nothing', E.absorption(mins).length === 0);

const pf = E.profile([{ t: 1, l: 100, h: 100.9, v: 10, bv: 6 }, { t: 2, l: 100, h: 102.9, v: 3, bv: 0 }], 0, 1);
check('profile: POC row, buy/sell split, value area', pf.poc === 100.5 && Math.abs(pf.rows[0].buy - 6) < 1e-9 &&
      Math.abs(pf.rows[0].sell - 5) < 1e-9 && pf.val === 100 && pf.vah === 101, `poc ${pf.poc} val ${pf.val} vah ${pf.vah}`);

// walls by open interest do not move when the price does; walls by gamma follow it when expiry is hours away
const chain = { contracts: [['261106', 0, 100, 0.2, 500, 0, 0], ['261106', 0, 110, 0.2, 3000, 0, 0], ['261106', 1, 90, 0.2, 2000, 0, 0], ['261106', 1, 100, 0.2, 100, 0, 0]] };
const late = E.nyClose('261106') - 2 * 3600e3;                 // two hours before expiry
const at = s => { const rows = E.table(chain, s, late, null).rows; return { oi: E.wallsOi(rows, 1), g: E.walls(rows, 1) }; };
check('walls by open interest stay put when price moves', at(100).oi.calls[0].k === 110 && at(109).oi.calls[0].k === 110 && at(100).oi.puts[0].k === 90 && at(109).oi.puts[0].k === 90);
check('walls by gamma follow the price near expiry (why they are not used for 0DTE)', at(100).g.calls[0].k === 100 && at(109).g.calls[0].k === 110);

// ---- signals: quiet 5-minute candles near 100, then a candle that dips into support and closes back up
const agg = E.aggregate([{ t: 0, o: 1, h: 2, l: 1, c: 2, v: 1, bv: 1 }, { t: 60e3, o: 2, h: 3, l: 0.5, c: 1, v: 2, bv: 0 }, { t: 300e3, o: 1, h: 1, l: 1, c: 1, v: 1, bv: 1 }], 300e3);
check('aggregate: 1m -> 5m', agg.length === 2 && agg[0].h === 3 && agg[0].l === 0.5 && agg[0].c === 1 && agg[0].v === 3 && agg[0].bv === 1);
const c5 = [];
for (let i = 0; i < 30; i++) c5.push({ t: i * 300e3, o: 100, h: 100.4, l: 99.6, c: i % 2 ? 100.1 : 99.9 });
const bounce = { t: 30 * 300e3, o: 99.6, h: 100.1, l: 99.1, c: 100.0 };
const support = [{ lo: 98.9, hi: 99.3, w: 30, name: 'demand' }], far = [{ lo: 103, hi: 103.5, w: 30, name: 'supply' }];
const inp = { c5: c5.concat([bounce]), price: 100, supports: support, resistances: far, magnets: [], regime: 1, trend: 1, tape: 0.2 };
let sg = E.signal(inp);
check('buy: bounce off support with room to the target', sg.state === 'buy' && sg.score === 85 && sg.entry === 100 && sg.target === 103 &&
      sg.stop < 98.9 && sg.rr > 2 && sg.t === bounce.t, `score ${sg.score}, stop ${sg.stop && sg.stop.toFixed(2)}, rr ${sg.rr && sg.rr.toFixed(1)}`);
sg = E.signal({ ...inp, resistances: [{ lo: 100.8, hi: 101.2, w: 30, name: 'supply' }] });
check('skip: target too close to be worth the risk', sg.state === 'skip' && /not worth it/.test(sg.note), sg.note);
sg = E.signal({ ...inp, regime: -1, trend: -1, tape: -0.2 });
check('skip: everything else against the trade', sg.state === 'skip' && sg.score < 55, `score ${sg.score}`);
sg = E.signal({ ...inp, c5: c5.concat([{ t: bounce.t, o: 99.8, h: 99.9, l: 99.1, c: 99.2 }]), price: 99.2 });
check('watch: at support but no candle has closed back up', sg.state === 'watch' && sg.side === 'buy', sg.state);
sg = E.signal({ ...inp, c5, price: 100 });
check('none: price between levels', sg.state === 'none');
const flipped = c5.map(k => ({ t: k.t, o: 200 - k.o, h: 200 - k.l, l: 200 - k.h, c: 200 - k.c }));
sg = E.signal({ c5: flipped.concat([{ t: bounce.t, o: 100.4, h: 100.9, l: 99.9, c: 100.0 }]), price: 100, supports: [{ lo: 96.5, hi: 97, w: 30, name: 'demand' }],
                resistances: [{ lo: 100.7, hi: 101.1, w: 30, name: 'supply' }], magnets: [], regime: 1, trend: -1, tape: -0.2 });
check('sell: mirror case at resistance', sg.state === 'sell' && sg.score === 85 && sg.stop > 101.1 && sg.target === 97, `score ${sg.score}`);

// ---- real chain: our gamma model against CBOE's own gamma at the CBOE close
const file = path.join(__dirname, 'gex_data.js');
if (!fs.existsSync(file)) {
  console.log('SKIP  real-chain checks: gex_data.js not found (run node gex_fetch.cjs)');
} else {
  const data = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^window\.GEX_DATA = /, '').replace(/;\s*$/, ''));
  const day = data.lastTradeTime.slice(2, 10).replace(/-/g, '');             // GLD's last trade date as YYMMDD
  const close = E.nyClose(day), exps = E.expiries(data, close).slice(0, 4);
  check('chain has live expiries', exps.length > 0, exps.map(e => `${e.exp} (${e.dte}d)`).join(', '));
  // CBOE's gamma is only comparable when every expiry was priced at the same moment. That holds for a file taken
  // after the US session has settled (20:00-04:00 New York): all greeks are as of the last close. In pre-market
  // and during the session CBOE refreshes expiries at different times (seen 6 Nov 2026, 09:23 New York: one
  // expiry as of now, one still as of yesterday's close, one with an inconsistent IV), so then it is information only.
  const stamp = Date.parse(data.timestamp.replace(' ', 'T') + 'Z');
  const nyHour = +new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }).format(new Date(stamp)) % 24;
  const settled = nyHour >= 20 || nyHour < 4;
  if (!settled) console.log(`INFO  file taken at ${nyHour}:00 New York, not settled data: gamma comparison is information only`);
  for (const e of exps) {
    const calls = data.contracts.filter(c => c[0] === e.exp && c[1] === 0 && c[6] > 0);
    if (!calls.length) continue;
    const atm = calls.reduce((a, b) => Math.abs(b[2] - data.spot) < Math.abs(a[2] - data.spot) ? b : a);
    const ours = E.bsGamma(data.spot, atm[2], atm[3], E.years(e.exp, close)), ratio = ours / atm[6];
    if (settled) check(`gamma model vs CBOE, ${e.exp} ${atm[2]} call`, ratio > 0.85 && ratio < 1.15, `ours ${ours.toFixed(4)} cboe ${atm[6]} (x${ratio.toFixed(2)})`);
    else {
      const live = E.bsGamma(data.spot, atm[2], atm[3], Math.max(E.nyClose(e.exp) - stamp, 60e3) / (365 * 864e5)) / atm[6];
      console.log(`INFO  ${e.exp} ${atm[2]} call: cboe ${atm[6]}, ours x${ratio.toFixed(2)} if priced at the last close, x${live.toFixed(2)} if priced at the file time`);
    }
  }
  const f = 1 / E.ozPerShare(close), near = new Set([exps[0].exp]);
  const t0 = E.table(data, data.spot, close, near), all = E.table(data, data.spot, close, null);
  const w0 = E.wallsOi(t0.rows.filter(r => Math.abs(r.k / data.spot - 1) <= 0.08), 1), wa = E.walls(all.rows, 3), zg = E.gammaFlip(data, data.spot, close, near);
  const gold = k => (k * f).toFixed(1);
  check('nearest expiry has a call wall and a put wall', w0.calls.length === 1 && w0.puts.length === 1);
  console.log(`      at the GLD close ${data.spot} = gold ${gold(data.spot)}:`);
  console.log(`      ${exps[0].dte}DTE call wall ${gold(w0.calls[0].k)}, put wall ${gold(w0.puts[0].k)}, zero gamma ${zg ? gold(zg) : 'none in range'}`);
  console.log(`      all expiries: call walls ${wa.calls.map(w => gold(w.k)).join(', ')}; put walls ${wa.puts.map(w => gold(w.k)).join(', ')}`);
  console.log(`      contracts with open interest: ${t0.count} nearest expiry, ${all.count} all`);
}
console.log(failed ? `\n${failed} check(s) failed` : '\nall checks passed');
process.exit(failed ? 1 : 0);
