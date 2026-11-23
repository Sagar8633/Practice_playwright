#!/usr/bin/env node
// Does price behave the same way around the POC / value area day after day? Tests written down BEFORE they were
// run (README.md, "Tests"), on the page's own rules (GexEngine.profilePath, the Days tab's numbers).
//   node day_study.cjs fetch     download / top up Binance XAUUSDT 1-minute candles since Dec 2025 (data/, git-ignored)
//   node --max-old-space-size=6000 day_study.cjs    run every test on both data sets -> results/
// Data sets:
//   BIN  Binance XAUUSDT futures 1m, Dec 2025 - Nov 2026: exactly what the page uses, real buy/sell volume.
//        The 20 days in the screenshots (26 Oct - 20 Nov 2026) are reported apart ("seen"), the rest is "unseen".
//   DUKA Dukascopy XAUUSD 1m, Sep 2021 - Sep 2026 (the file of the earlier studies, its own volume): none of it
//        was looked at for this study, so it decides.
// Every test is a race: from the price at a moment of the day, which comes first, a target or a stop the same
// distance on the other side. With no edge the target comes first half of the time. A target-first share p
// means 2p - 1 of the risk per trade before costs (1 : 1), minus the cost (0.25 or 0.80 $) over the distance.
'use strict';
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const E = require('../heatmap/gex_engine.js');

const HERE = __dirname, DATA = path.join(HERE, 'data'), OUT = path.join(HERE, 'results');
const BIN = path.join(DATA, 'XAUUSDT_1m_binance.json.gz');
const DUKA = path.join(HERE, '..', '..', 'Momentum_Tracker_Indicator', 'backtest', 'data', 'XAUUSD_M1_servertime_full.csv.gz');
const PERIODS = [['DEV', '2021-09-01', '2024-09-01'], ['VAL', '2024-09-01', '2026-03-01'], ['OOS', '2026-03-01', '2026-12-01']];
const SEEN = ['2026-10-26', '2026-11-21'];           // trade dates of the screenshots
const COSTS = [0, 0.25, 0.8];
const STEP = 0.5, MIN_D = 2;                         // the page's profile rows and POC-shift size on gold

// ------------------------------------------------------------------ gold hours (as the page, since 22 Nov 2026)
const offMemo = new Map();
const nyOff = t => { const k = Math.floor(t / 36e5); let v = offMemo.get(k); if (v === undefined) { v = E.nyOffsetHours(k * 36e5); offMemo.set(k, v); } return v; };
function closedAt(t) {
  const ny = new Date(t + nyOff(t) * 36e5), wd = ny.getUTCDay(), h = ny.getUTCHours();
  return wd === 6 || (wd === 5 && h >= 17) || (wd === 0 && h < 18) || h === 17;
}
const nyWall = (start, hh, mm) => {                  // hh:mm New York on the trade date of the day that starts at `start`
  const mid = start + 12 * 36e5, ny = new Date(mid + nyOff(mid) * 36e5), wall = Date.UTC(ny.getUTCFullYear(), ny.getUTCMonth(), ny.getUTCDate(), hh, mm);
  let t = wall - nyOff(wall) * 36e5; t = wall - nyOff(t) * 36e5; return t;
};
const tradeDate = start => { const mid = start + 12 * 36e5; return new Date(mid + nyOff(mid) * 36e5).toISOString().slice(0, 10); };

// ------------------------------------------------------------------ data
async function fetchBinance() {
  fs.mkdirSync(DATA, { recursive: true });
  let rows = fs.existsSync(BIN) ? JSON.parse(zlib.gunzipSync(fs.readFileSync(BIN))) : [];
  let s = rows.length ? rows[rows.length - 1][0] + 60e3 : Date.UTC(2025, 11, 11);
  const end = Math.floor(Date.now() / 60e3) * 60e3 - 60e3;
  let n = 0;
  while (s < end) {
    const r = await fetch(`https://fapi.binance.com/fapi/v1/klines?symbol=XAUUSDT&interval=1m&startTime=${s}&limit=1500`);
    if (!r.ok) throw new Error('Binance HTTP ' + r.status);
    const j = await r.json();
    if (!j.length) break;
    for (const k of j) if (k[0] < end) rows.push([k[0], +k[1], +k[2], +k[3], +k[4], +k[5], +k[9]]);
    s = j[j.length - 1][0] + 60e3;
    if (++n % 25 === 0) process.stdout.write(`  ${new Date(s).toISOString().slice(0, 10)} (${rows.length} minutes)\n`);
    await new Promise(res => setTimeout(res, 350));  // about 1,700 weight a minute, under Binance's 2,400
  }
  fs.writeFileSync(BIN, zlib.gzipSync(JSON.stringify(rows)));
  console.log(`Binance: ${rows.length} minutes up to ${new Date(rows[rows.length - 1][0]).toISOString()}`);
}
function loadBinance() {
  return JSON.parse(zlib.gunzipSync(fs.readFileSync(BIN))).filter(r => !closedAt(r[0])).map(r => ({ t: r[0], o: r[1], h: r[2], l: r[3], c: r[4], v: r[5], bv: r[6] }));
}
// Dukascopy file: broker server time (Europe/Athens), one offset per calendar day (switches when gold is closed).
const athens = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens', hour: '2-digit', hour12: false });
function loadDuka() {
  const lines = zlib.gunzipSync(fs.readFileSync(DUKA)).toString('latin1').split('\n'), base = new Map(), out = [];
  for (let k = 1; k < lines.length; k++) {
    const p = lines[k].split(',');
    if (p.length < 6) continue;
    const key = p[0].slice(0, 10);
    let b = base.get(key);
    if (b === undefined) { const noon = Date.UTC(+key.slice(0, 4), +key.slice(5, 7) - 1, +key.slice(8, 10), 10); b = noon - 10 * 3600e3 - (+athens.format(new Date(noon)) % 24 - 10) * 3600e3; base.set(key, b); }
    const t = b + (+p[0].slice(11, 13)) * 3600e3 + (+p[0].slice(14, 16)) * 60e3, v = +p[5];
    if (!closedAt(t)) out.push({ t, o: +p[1], h: +p[2], l: +p[3], c: +p[4], v, bv: v / 2 });
  }
  return out;
}

// ------------------------------------------------------------------ days
// One trading day = 18:00 to 18:00 New York. Its profile path is the page's (profilePath), with the three check
// times of the Days tab. ATR = mean true range of the last 14 one-hour candles closed by the moment in question.
function buildDays(c) {
  const h1 = E.aggregate(c, 3600e3), tr = h1.map((k, i) => (i ? Math.max(k.h - k.l, Math.abs(k.h - h1[i - 1].c), Math.abs(k.l - h1[i - 1].c)) : k.h - k.l));
  const atrAt = t => {                               // hourly candles that closed by t
    let lo = 0, hi = h1.length - 1, r = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (h1[m].t + 3600e3 <= t) { r = m; lo = m + 1; } else hi = m - 1; }
    if (r < 14) return 0;
    let s = 0; for (let i = r - 13; i <= r; i++) s += tr[i]; return s / 14;
  };
  const days = [], sessMemo = new Map();
  const sessionOf = t => { const k = Math.floor(t / 36e5); let s = sessMemo.get(k); if (s === undefined) sessMemo.set(k, s = E.sessionStart(t)); return s; };
  let i = 0;
  while (i < c.length) {
    const start = sessionOf(c[i].t);
    let j = i;
    while (j < c.length && sessionOf(c[j].t) === start) j++;
    const rows = c.slice(i, j), date = tradeDate(start);
    if (rows.length >= 900) {                        // a full day (about 1,380 minutes); short holiday sessions are left out
      const at = { asia: nyWall(start, 3, 0), london: nyWall(start, 8, 30), close: nyWall(start, 17, 0) };
      const path = E.profilePath(rows, start, start + 30 * 36e5, STEP, { minD: MIN_D, at });
      days.push({ start, date, i0: i, i1: j, at, path, atr: { asia: atrAt(at.asia), london: atrAt(at.london), open: atrAt(start + 60e3) } });
    }
    i = j;
  }
  return { c, days, atrAt };
}

// ------------------------------------------------------------------ the race
// From the first candle that starts at or after t, until `end`: does price reach `target` before `stop`?
// One candle touching both = stop (as in every earlier study). Neither by `end` = closed at the last price.
function race(c, from, t, end, entry, target, stop) {
  const up = target > entry, D = Math.abs(target - entry);
  let i = from;
  while (i < c.length && c[i].t < t) i++;
  let last = entry;
  for (; i < c.length && c[i].t < end; i++) {
    const k = c[i], hitT = up ? k.h >= target : k.l <= target, hitS = up ? k.l <= stop : k.h >= stop;
    if (hitS && hitT) return { res: 'both', r: -1, D };          // counted as a stop, whichever way the trade is read
    if (hitS) return { res: 'stop', r: -1, D };
    if (hitT) return { res: 'target', r: 1, D };
    last = k.c;
  }
  return { res: 'none', r: (up ? last - entry : entry - last) / D, D };
}

// ------------------------------------------------------------------ tests (README.md "Tests" lists the same ones)
function runTests(set) {
  const { c, days } = set, out = [];
  const add = (test, d, r) => out.push(Object.assign({ test, date: d.date }, r));
  for (let k = 0; k < days.length; k++) {
    const d = days[k], P = d.path, prev = k > 0 && days[k - 1].start >= d.start - 4 * 864e5 ? days[k - 1] : null;
    const close = d.at.close;
    // T1 POC magnet at Asia / London: toward the developing POC, stop the same distance away; split by where
    // price is (inside the value area, or outside it)
    for (const when of ['asia', 'london']) {
      const a = P.at[when], atr = d.atr[when];
      if (!a || !(atr > 0)) continue;
      const dist = Math.abs(a.px - a.poc), where = a.px > a.vah ? 'outside' : a.px < a.val ? 'outside' : 'inside';
      if (dist < 0.25 * atr || dist > 3 * atr) continue;
      add(`T1 ${when}: toward the POC, price ${where} the value area`, d, race(c, d.i0, a.t, close, a.px, a.poc, a.px + (a.px - a.poc)));
    }
    // T3 yesterday's POC at Asia: toward it, stop the same distance away
    if (prev && prev.path.final) {
      const a = P.at.asia, atr = d.atr.asia, poc = prev.path.final.poc;
      if (a && atr > 0) {
        const dist = Math.abs(a.px - poc);
        if (dist >= 0.25 * atr && dist <= 3 * atr) add('T3 asia: toward yesterday\'s POC', d, race(c, d.i0, a.t, close, a.px, poc, a.px + (a.px - poc)));
      }
    }
    // T4 POC migration: POC moved 2 $ or more from Asia to London -> go with it at London, 1 ATR target and stop
    {
      const a = P.at.asia, b = P.at.london, atr = d.atr.london;
      if (a && b && atr > 0 && Math.abs(b.poc - a.poc) >= MIN_D) {
        const s = Math.sign(b.poc - a.poc);
        add('T4 london: with the POC move since Asia', d, race(c, d.i0, b.t, close, b.px, b.px + s * atr, b.px - s * atr));
      }
    }
    // T5 POC shift events (the banner): with the shift, 1 ATR target and stop, at most 4 hours, before 15:00 NY
    for (const s of P.shifts) {
      if (s.t > nyWall(d.start, 15, 0)) continue;
      const atr = set.atrAt(s.t);
      if (!(atr > 0)) continue;
      let i = d.i0; while (i < d.i1 && c[i].t + 60e3 < s.t) i++;
      const px = c[Math.min(i, d.i1 - 1)].c, dir = Math.sign(s.to - s.from);
      add('T5 POC shift: with the shift', d, race(c, d.i0, s.t, Math.min(close, s.t + 4 * 36e5), px, px + dir * atr, px - dir * atr));
    }
    // T6 the "80 % rule": the day opens outside yesterday's value area, then two 30-minute candles in a row close
    // inside it (before 12:00 NY) -> toward the far side of yesterday's value area, stop the same distance away
    if (prev && prev.path.final) {
      const { vah, val } = prev.path.final, rows = c.slice(d.i0, d.i1), o = rows[0].o;
      if (o > vah || o < val) {
        const c30 = E.aggregate(rows, 1800e3), limit = nyWall(d.start, 12, 0);
        for (let m = 1; m < c30.length; m++) {
          if (c30[m].t + 1800e3 > limit) break;
          const inside = k => k.c < vah && k.c > val;
          if (inside(c30[m]) && inside(c30[m - 1])) {
            const t = c30[m].t + 1800e3, px = c30[m].c, far = o > vah ? val : vah;
            add('T6 80 % rule: back into yesterday\'s value area, toward its far side', d, race(c, d.i0, t, close, px, far, px + (px - far)));
            break;
          }
        }
      }
    }
  }
  return out;
}

// ------------------------------------------------------------------ what the days look like (no trade)
function describe(set) {
  const n = set.days.length, cnt = f => set.days.filter(f).length, pct = x => `${(100 * x / n).toFixed(0)} %`;
  const ok = set.days.filter(d => d.path.at.asia && d.path.at.london && d.path.at.close);
  const stuck = ok.filter(d => Math.abs(d.path.at.close.poc - d.path.at.asia.poc) < MIN_D).length;
  const insideClose = ok.filter(d => { const a = d.path.at.close; return a.px <= a.vah && a.px >= a.val; }).length;
  const back = ok.filter(d => { const a = d.path.at.london; if (a.px <= a.vah && a.px >= a.val) return false; const z = d.path.at.close; return (a.px > a.vah ? z.px <= a.vah : z.px >= a.val); }).length;
  const outLon = ok.filter(d => { const a = d.path.at.london; return a.px > a.vah || a.px < a.val; }).length;
  const shifts = set.days.reduce((s, d) => s + d.path.shifts.length, 0);
  return { n, ok: ok.length, stuck, insideClose, outLon, back, shifts, perDay: shifts / n, pct, cnt };
}

// ------------------------------------------------------------------ report
const z = (w, n) => (n ? (w - n / 2) / Math.sqrt(n / 4) : 0);
function stats(rows) {
  const n = rows.length, w = rows.filter(r => r.res === 'target').length, s = rows.filter(r => r.res === 'stop' || r.res === 'both').length;
  const gross = n ? rows.reduce((a, r) => a + r.r, 0) / n : 0, avgD = n ? rows.reduce((a, r) => a + r.D, 0) / n : 0;
  const net = COSTS.map(cost => (n ? rows.reduce((a, r) => a + r.r - cost / r.D, 0) / n : 0));
  return { n, w, s, none: n - w - s, p: w + s ? w / (w + s) : 0, z: z(w, w + s), gross, net, avgD };
}
const f2 = v => (v >= 0 ? '+' : '') + v.toFixed(3);
function table(title, groups) {
  let md = `\n### ${title}\n\n| test | data | days / trades | target first | z | R per trade before costs | after 0.25 $ | after 0.80 $ | avg distance $ |\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n`;
  for (const [test, list] of groups) for (const [name, rows] of list) {
    const s = stats(rows);
    md += `| ${test} | ${name} | ${s.n} | ${(100 * s.p).toFixed(1)} % (${s.w} / ${s.w + s.s}) | ${s.z.toFixed(1)} | ${f2(s.gross)} | ${f2(s.net[1])} | ${f2(s.net[2])} | ${s.avgD.toFixed(1)} |\n`;
  }
  return md;
}

async function main() {
  if (process.argv[2] === 'fetch') return fetchBinance();
  if (!fs.existsSync(BIN)) { console.log('No Binance file yet: run  node day_study.cjs fetch'); process.exit(1); }
  fs.mkdirSync(OUT, { recursive: true });
  const t0 = Date.now();
  const bin = buildDays(loadBinance());
  console.log(`Binance: ${bin.days.length} days (${((Date.now() - t0) / 1e3).toFixed(0)} s)`);
  const duka = buildDays(loadDuka());
  console.log(`Dukascopy: ${duka.days.length} days (${((Date.now() - t0) / 1e3).toFixed(0)} s)`);
  const rb0 = runTests(bin), rd0 = runTests(duka);
  // T1 "outside" read the other way round (README): away from the POC, stop at the POC. A candle that touched both
  // stays a stop; everything else flips.
  const flip = rows => rows.filter(r => /T1 .*outside/.test(r.test)).map(r => Object.assign({}, r, {
    test: r.test.replace('toward the POC', 'AWAY from the POC (trend day)'), res: r.res === 'target' ? 'stop' : r.res === 'stop' ? 'target' : r.res, r: r.res === 'both' ? -1 : -r.r }));
  const rb = rb0.concat(flip(rb0)), rd = rd0.concat(flip(rd0));
  const seen = r => r.date >= SEEN[0] && r.date < SEEN[1], per = p => r => r.date >= p[1] && r.date < p[2];
  const tests = [...new Set(rd.map(r => r.test).concat(rb.map(r => r.test)))].sort();
  const groups = tests.map(t => [t, [
    ['DUKA all', rd.filter(r => r.test === t)],
    ...PERIODS.map(p => [`DUKA ${p[0]}`, rd.filter(r => r.test === t && per(p)(r))]),
    ['BIN unseen', rb.filter(r => r.test === t && !seen(r))],
    ['BIN seen (20 screenshot days)', rb.filter(r => r.test === t && seen(r))],
  ]]);
  // per-day file for the user's own research
  const csv = s => ['date,open,high,low,close_17ny,asia_poc,asia_vah,asia_val,asia_price,london_poc,london_vah,london_val,london_price,close_poc,close_vah,close_val,close_price,end_poc,poc_shifts,atr_1h_london']
    .concat(s.days.map(d => { const P = d.path, A = P.at, g = (x, k) => (x ? x[k].toFixed(2) : '');
      return [d.date, P.open, P.high, P.low, g(A.close, 'px'), g(A.asia, 'poc'), g(A.asia, 'vah'), g(A.asia, 'val'), g(A.asia, 'px'), g(A.london, 'poc'), g(A.london, 'vah'), g(A.london, 'val'), g(A.london, 'px'),
              g(A.close, 'poc'), g(A.close, 'vah'), g(A.close, 'val'), g(A.close, 'px'), P.final ? P.final.poc : '', P.shifts.length, d.atr.london.toFixed(2)].join(','); })).join('\n') + '\n';
  fs.writeFileSync(path.join(OUT, 'days_binance.csv'), csv(bin));
  fs.writeFileSync(path.join(OUT, 'days_dukascopy.csv'), csv(duka));
  const ev = rows => 'test,date,result,r,distance\n' + rows.map(r => `"${r.test}",${r.date},${r.res},${r.r.toFixed(3)},${r.D.toFixed(2)}`).join('\n') + '\n';
  fs.writeFileSync(path.join(OUT, 'trades_binance.csv'), ev(rb));
  fs.writeFileSync(path.join(OUT, 'trades_dukascopy.csv'), ev(rd));

  const db = describe(bin), dk = describe(duka), dseen = describe({ days: bin.days.filter(d => seen(d)) });
  const row = (name, x) => `| ${name} | ${x.n} | ${x.pct(x.stuck)} | ${x.pct(x.outLon)} | ${x.outLon ? (100 * x.back / x.outLon).toFixed(0) + ' %' : '-'} | ${x.pct(x.insideClose)} | ${x.perDay.toFixed(1)} |\n`;
  let md = `# Day review: does price do the same thing around the POC every day?\n\nGenerated ${new Date().toISOString().slice(0, 16)} UTC by day_study.cjs. Tests and decision rule: README.md (written before the run).\n`;
  md += `\n## What the days look like\n\n| data | days | POC at the close within 2 $ of the Asia POC | outside the value area at London (08:30 NY) | of those, back inside by the close | close (17:00 NY) inside the value area | POC shifts per day |\n|---|---:|---:|---:|---:|---:|---:|\n`;
  md += row('BIN screenshot days', dseen) + row('BIN all (Dec 2025 - Nov 2026)', db) + row('DUKA (Sep 2021 - Sep 2026)', dk);
  md += table('Races (target and stop the same distance away; 50 % = no edge)', groups);
  md += `\nRuntime ${((Date.now() - t0) / 1e3).toFixed(0)} s. Per-day numbers: days_binance.csv, days_dukascopy.csv; every trade: trades_*.csv.\n`;
  fs.writeFileSync(path.join(OUT, 'summary.md'), md);
  console.log(md);
}
main().catch(e => { console.error(e); process.exit(1); });
