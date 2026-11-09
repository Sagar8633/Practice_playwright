// Gamma exposure (GEX), supply/demand zones and volume profile for gold_gex.html.
// Pure functions, no DOM: loaded by the page as window.GexEngine and by Node (gex_test.cjs) through require().
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GexEngine = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const YEAR = 365 * 864e5;
  const MIN_T = 30 * 60e3;                    // gamma of an expiring option explodes; never use less than 30 min
  const GLD_START = Date.UTC(2004, 10, 18);   // GLD started at 0.1 oz per share and pays a 0.40 % yearly fee in gold

  // Ounces of gold behind one GLD share. 1 / ozPerShare = the factor that turns a GLD price into a gold price.
  // Checked 5 Nov 2026: GLD closed 375.49 with gold near 4100 -> 10.92; the formula gives 10.920.
  function ozPerShare(ms) { return 0.1 * Math.pow(1 - 0.004, (ms - GLD_START) / (365.25 * 864e5)); }

  // Hours to add to UTC to get New York wall-clock time (-4 or -5).
  function nyOffsetHours(ms) {
    const h = +new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }).format(new Date(ms)) % 24;
    let d = h - new Date(ms).getUTCHours();
    if (d > 12) d -= 24;
    if (d < -12) d += 24;
    return d;
  }
  const closes = new Map();
  // 'YYMMDD' -> UTC ms of that day's 16:00 New York close, when the options expire.
  function nyClose(exp) {
    if (!closes.has(exp)) {
      const y = 2000 + +exp.slice(0, 2), m = +exp.slice(2, 4) - 1, d = +exp.slice(4, 6);
      closes.set(exp, Date.UTC(y, m, d, 16 - nyOffsetHours(Date.UTC(y, m, d, 21))));
    }
    return closes.get(exp);
  }
  function years(exp, now) { const left = nyClose(exp) - now; return left > 0 ? Math.max(left, MIN_T) / YEAR : 0; }
  // Calendar days from today (New York date) to the expiry date.
  function dte(exp, now) {
    const ny = new Date(now + nyOffsetHours(now) * 36e5);
    const today = Date.UTC(ny.getUTCFullYear(), ny.getUTCMonth(), ny.getUTCDate());
    return Math.round((Date.UTC(2000 + +exp.slice(0, 2), +exp.slice(2, 4) - 1, +exp.slice(4, 6)) - today) / 864e5);
  }
  // Most recent 18:00 New York: the start of the gold trading day.
  function sessionStart(now) {
    const off = nyOffsetHours(now), ny = new Date(now + off * 36e5);
    let start = Date.UTC(ny.getUTCFullYear(), ny.getUTCMonth(), ny.getUTCDate(), 18) - off * 36e5;
    if (start > now) start -= 864e5;
    return start;
  }

  // Black-Scholes gamma, interest rate taken as 0.
  function bsGamma(S, K, iv, T) {
    if (!(iv > 0) || !(T > 0) || !(S > 0) || !(K > 0)) return 0;
    const sd = iv * Math.sqrt(T), d1 = (Math.log(S / K) + 0.5 * iv * iv * T) / sd;
    return Math.exp(-0.5 * d1 * d1) / (2.5066282746310002 * S * sd);
  }

  // data.contracts rows: [expiry 'YYMMDD', type 0 = call / 1 = put, strike, iv, open interest, volume, cboe gamma]
  // Expiries that are still alive, nearest first.
  function expiries(data, now) {
    const seen = new Set(), out = [];
    for (const c of data.contracts) {
      if (seen.has(c[0])) continue;
      seen.add(c[0]);
      if (nyClose(c[0]) > now) out.push({ exp: c[0], close: nyClose(c[0]), dte: dte(c[0], now) });
    }
    return out.sort((a, b) => a.close - b.close);
  }

  // Per strike: call and put gamma exposure in dollars per 1 % move of the underlying, open interest and volume.
  // Gamma is recomputed at `spot` from each contract's implied volatility, so the bars follow the live price.
  // exps: Set of expiry codes, or null for every live expiry.
  function table(data, spot, now, exps) {
    const m = new Map();
    let count = 0;
    for (const [exp, type, k, iv, oi, vol] of data.contracts) {
      if (exps && !exps.has(exp)) continue;
      const T = years(exp, now);
      if (!(T > 0)) continue;
      const g = oi > 0 ? bsGamma(spot, k, Math.min(iv, 3), T) * oi * spot * spot : 0;   // x 100 shares x 1 % = x 1
      let r = m.get(k);
      if (!r) m.set(k, r = { k, cg: 0, pg: 0, coi: 0, poi: 0, cvol: 0, pvol: 0 });
      if (type === 0) { r.cg += g; r.coi += oi; r.cvol += vol; } else { r.pg += g; r.poi += oi; r.pvol += vol; }
      if (oi > 0) count++;
    }
    return { rows: [...m.values()].sort((a, b) => a.k - b.k), count };
  }

  // Walls by net gamma (calls minus puts): call walls are the largest positive strikes, put walls the largest
  // negative ones, so a wall is always the biggest green or red bar and one strike is never both.
  function walls(rows, n) {
    const net = rows.map(r => ({ k: r.k, v: r.cg - r.pg }));
    return { calls: net.filter(w => w.v > 0).sort((a, b) => b.v - a.v).slice(0, n),
             puts: net.filter(w => w.v < 0).sort((a, b) => a.v - b.v).slice(0, n) };
  }

  // Walls by net open interest (calls minus puts), for the nearest expiry. Gamma of an option that expires
  // within hours is a narrow spike at the current price, so a gamma-ranked wall just follows price around
  // (seen 6 Nov 2026: "Call Wall 0DTE" slid from 4095 to 4028 with the market). Open interest is fixed for the
  // day, so these walls stay where the positions are.
  function wallsOi(rows, n) {
    const net = rows.map(r => ({ k: r.k, v: r.coi - r.poi }));
    return { calls: net.filter(w => w.v > 0).sort((a, b) => b.v - a.v).slice(0, n),
             puts: net.filter(w => w.v < 0).sort((a, b) => a.v - b.v).slice(0, n) };
  }

  // Price where total net gamma (calls minus puts) changes sign, found by re-pricing every contract at
  // hypothetical spots within +/- span of the current one. Returns the crossing nearest to spot, or null.
  function gammaFlip(data, spot, now, exps, span, steps) {
    span = span || 0.08; steps = steps || 320;
    const list = [];
    for (const [exp, type, k, iv, oi] of data.contracts) {
      if (!(oi > 0) || !(iv > 0) || (exps && !exps.has(exp))) continue;
      const T = years(exp, now);
      if (T > 0) list.push([k, Math.min(iv, 3), T, type === 0 ? oi : -oi]);
    }
    let best = null, prevS = 0, prevV = 0;
    for (let i = 0; i <= steps; i++) {
      const s = spot * (1 - span + 2 * span * i / steps);
      let v = 0;
      for (const [k, iv, T, q] of list) v += q * bsGamma(s, k, iv, T);
      v *= s * s;
      if (i && v !== prevV && (v > 0) !== (prevV > 0)) {
        const x = prevS + (s - prevS) * (0 - prevV) / (v - prevV);
        if (best === null || Math.abs(x - spot) < Math.abs(best - spot)) best = x;
      }
      prevS = s; prevV = v;
    }
    return best;
  }

  // Supply and demand zones from closed candles [{t, o, h, l, c}], oldest first.
  // An impulse is a candle whose body is at least `impulse` x ATR(14) and that closes beyond the base candle.
  // The base is the last candle against the move (or a small one) within 3 candles before it:
  // demand = base low to base body top, supply = base body bottom to base high.
  // A zone exists only after the impulse candle has closed, and dies when a candle closes through its far side.
  function zones(c, opt) {
    const k = (opt && opt.impulse) || 1.2, n = c.length, out = [], atrs = new Array(n);
    let atr = 0;
    for (let i = 0; i < n; i++) {
      const tr = i ? Math.max(c[i].h - c[i].l, Math.abs(c[i].h - c[i - 1].c), Math.abs(c[i].l - c[i - 1].c)) : c[i].h - c[i].l;
      atr = i < 14 ? (atr * i + tr) / (i + 1) : (atr * 13 + tr) / 14;
      atrs[i] = atr;
    }
    for (let i = 15; i < n; i++) {
      const a = atrs[i - 1], body = c[i].c - c[i].o;
      if (!(a > 0) || Math.abs(body) < k * a) continue;
      const up = body > 0;
      let b = -1;
      for (let j = i - 1; j >= i - 3; j--) {
        const bj = c[j].c - c[j].o;
        if ((up ? bj <= 0 : bj >= 0) || Math.abs(bj) < 0.3 * a) { b = j; break; }
        if (Math.abs(bj) >= k * a) break;          // the candle before is itself an impulse: same move, no new base
      }
      if (b < 0 || (up ? c[i].c <= c[b].h : c[i].c >= c[b].l)) continue;
      let top = up ? Math.max(c[b].o, c[b].c) : c[b].h, bottom = up ? c[b].l : Math.min(c[b].o, c[b].c);
      if (top - bottom < 0.15 * a) { if (up) top = bottom + 0.15 * a; else bottom = top - 0.15 * a; }
      const z = { type: up ? 'demand' : 'supply', t: c[b].t, confirmed: c[i].t, top, bottom, tested: false, broken: false };
      for (let j = i + 1; j < n && !z.broken; j++) {
        if (up) { if (c[j].c < bottom) z.broken = true; else if (c[j].l <= top) z.tested = true; }
        else if (c[j].c > top) z.broken = true; else if (c[j].h >= bottom) z.tested = true;
      }
      out.push(z);
    }
    const live = out.filter(z => !z.broken);
    // a newer zone replaces an older overlapping one of the same type
    return live.filter((z, i) => !live.some((y, j) => j > i && y.type === z.type && y.bottom < z.top && y.top > z.bottom));
  }

  // Swing-candle boxes from closed candles [{t, o, h, l, c}], oldest first. The candle that made a swing high
  // (its high above the two candles before it and the `confirm` candles after it) is a sell zone ('supply'),
  // the candle that made a swing low a buy zone ('demand'). The box is that candle's range, at most `cap` x
  // ATR(14) measured from the extreme. It exists only after the confirming candle has closed. It turns
  // "tested" when price has left it and come back, and is dropped when a candle closes through its far side.
  // Same output shape as zones().
  function boxes(c, opt) {
    const K = (opt && opt.confirm) || 1, cap = (opt && opt.cap) || 1, n = c.length, out = [], atrs = new Array(n);
    let atr = 0;
    for (let i = 0; i < n; i++) {
      const tr = i ? Math.max(c[i].h - c[i].l, Math.abs(c[i].h - c[i - 1].c), Math.abs(c[i].l - c[i - 1].c)) : c[i].h - c[i].l;
      atr = i < 14 ? (atr * i + tr) / (i + 1) : (atr * 13 + tr) / 14;
      atrs[i] = atr;
    }
    for (let p = 14; p + K < n; p++) {
      const P = c[p], a = atrs[p - 1];
      if (!(a > 0)) continue;
      let high = P.h > c[p - 1].h && P.h > c[p - 2].h, low = P.l < c[p - 1].l && P.l < c[p - 2].l;
      for (let j = p + 1; j <= p + K; j++) { if (c[j].h >= P.h) high = false; if (c[j].l <= P.l) low = false; }
      for (const up of [false, true]) {
        if (up ? !low : !high) continue;
        let top = up ? Math.min(P.h, P.l + cap * a) : P.h, bottom = up ? P.l : Math.max(P.l, P.h - cap * a);
        if (top - bottom < 0.15 * a) { if (up) top = bottom + 0.15 * a; else bottom = top - 0.15 * a; }
        const z = { type: up ? 'demand' : 'supply', t: P.t, confirmed: c[p + K].t, top, bottom, tested: false, broken: false };
        let left = false;                                      // price has moved fully away from the box
        for (let j = p + K + 1; j < n && !z.broken; j++) {
          if (up) { if (c[j].c < bottom) z.broken = true; else if (c[j].l > top) left = true; else if (left) z.tested = true; }
          else if (c[j].c > top) z.broken = true; else if (c[j].h < bottom) left = true; else if (left) z.tested = true;
        }
        out.push(z);
      }
    }
    const live = out.filter(z => !z.broken);
    return live.filter((z, i) => !live.some((y, j) => j > i && y.type === z.type && y.bottom < z.top && y.top > z.bottom));
  }

  // The buy / sell zones the page suggests: swing boxes of the closed 30-minute candles and of the 1-hour
  // candles built from them. Where a 1-hour box overlaps a 30-minute box of the same kind, the tighter
  // 30-minute box is kept and marked '30m & 1h'. Each zone carries tf = '30m' | '1h' | '30m & 1h'.
  // A box is at most half an ATR tall, measured from the swing's extreme: on a quiet day that is the whole
  // swing candle, on a wild day it keeps the zone narrow enough to put a stop behind.
  function tradeZones(c30, opt) {
    if (!c30.length) return [];
    opt = Object.assign({ cap: 0.5 }, opt);
    const h = aggregate(c30, 3600e3);
    if (c30[c30.length - 1].t % 3600e3 < 1800e3) h.pop();        // that hour has not closed yet
    const out = boxes(c30, opt).map(z => Object.assign(z, { tf: '30m' }));
    for (const z of boxes(h, opt)) {
      const hit = out.filter(y => y.type === z.type && y.bottom < z.top && y.top > z.bottom);
      if (hit.length) hit.forEach(y => { y.tf = '30m & 1h'; }); else out.push(Object.assign(z, { tf: '1h' }));
    }
    return out.sort((x, y) => x.t - y.t);
  }

  // Absorption areas from closed 1-minute candles [{t, o, h, l, c, v, bv}] (bv = volume bought at the ask,
  // so v - bv was sold at the bid). "One side attacked hard and price did not go their way."
  // Checked at every closed minute over the last `span` minutes (default 5):
  //   (1) effort    volume of the window is at least `mult` x the median volume of such windows over the
  //                 `hist` minutes before it (default 1.5 x, 120 minutes),
  //   (2) one side  |buying - selling| is at least `delta` of that volume (default 15 %),
  //   (3) no result the window closed in the half of its range away from the attack.
  // Net selling that ends in the upper half = buyers absorbed it (kind 'buy', area = lower half of the window's
  // range). Net buying that ends in the lower half = sellers absorbed it (kind 'sell', area = upper half).
  // Hits of the same kind that overlap within `join` ms are one area. An area is dropped when a later candle
  // closes beyond its far side (the absorbing side gave way) and after `life` ms.
  // Returned: [{kind, t (start of the first window), born (close of the first window), last, top, bottom,
  //             vol, share (signed delta / volume of the strongest window), ratio (volume / normal), n}]
  function absorption(c, opt) {
    const o = opt || {}, span = o.span || 5, hist = o.hist || 120, mult = o.mult || 1.5, dmin = o.delta || 0.15;
    const join = o.join || 30 * 60e3, life = o.life || 8 * 3600e3, n = c.length, out = [];
    if (n < span + hist) return out;
    const V = new Float64Array(n + 1), B = new Float64Array(n + 1), W = new Float64Array(n);
    for (let i = 0; i < n; i++) { V[i + 1] = V[i] + (c[i].v || 0); B[i + 1] = B[i] + (c[i].bv || 0); }
    for (let i = span - 1; i < n; i++) W[i] = V[i + 1] - V[i + 1 - span];      // volume of the window that ends at candle i
    const buf = new Float64Array(hist);
    for (let i = span - 1 + hist; i < n; i++) {
      const v = W[i];
      if (!(v > 0)) continue;
      const share = (2 * (B[i + 1] - B[i + 1 - span]) - v) / v;
      if (Math.abs(share) < dmin) continue;
      let hi = -Infinity, lo = Infinity;
      for (let j = i - span + 1; j <= i; j++) { if (c[j].h > hi) hi = c[j].h; if (c[j].l < lo) lo = c[j].l; }
      const range = hi - lo;
      if (!(range > 0)) continue;
      const pos = (c[i].c - lo) / range, buy = share < 0;                       // sellers attacked: buyers may have absorbed it
      if (buy ? pos < 0.5 : pos > 0.5) continue;
      for (let j = 0; j < hist; j++) buf[j] = W[i - 1 - j];
      const sorted = Array.from(buf).sort((x, y) => x - y), med = (sorted[(hist >> 1) - 1] + sorted[hist >> 1]) / 2;
      if (!(med > 0) || v < mult * med) continue;
      const mid = (hi + lo) / 2, top = buy ? mid : hi, bottom = buy ? lo : mid, kind = buy ? 'buy' : 'sell', t = c[i].t;
      const prev = out.find(x => x.kind === kind && t - x.last <= join && x.bottom < top && x.top > bottom);
      if (prev) {
        prev.top = Math.max(prev.top, top); prev.bottom = Math.min(prev.bottom, bottom); prev.last = t; prev.n++; prev.i = i;
        if (v / med > prev.ratio) { prev.ratio = v / med; prev.vol = v; prev.share = share; }
      } else out.push({ kind, t: c[i - span + 1].t, born: t + 60e3, last: t, top, bottom, vol: v, share, ratio: v / med, n: 1, i });
    }
    const end = c[n - 1].t;
    for (const a of out) {
      for (let j = a.i + 1; j < n; j++) if (a.kind === 'buy' ? c[j].c < a.bottom : c[j].c > a.top) { a.broken = true; break; }
      delete a.i;
    }
    return o.all ? out : out.filter(a => !a.broken && end - a.last <= life);
  }

  // Volume by price from candles [{t, l, h, v, bv}] (bv = taker-buy volume) since `from`, in `step`-dollar rows.
  // A candle's volume is spread evenly over its low-high range. POC = busiest row; value area = 70 % of volume around it.
  function profile(c, from, step) {
    const bins = new Map();
    let total = 0;
    for (const k of c) {
      if (k.t < from || !(k.v > 0)) continue;
      const b0 = Math.floor(k.l / step), b1 = Math.floor(k.h / step), share = k.v / (b1 - b0 + 1), buy = k.bv / k.v;
      for (let b = b0; b <= b1; b++) {
        let e = bins.get(b);
        if (!e) bins.set(b, e = { buy: 0, sell: 0 });
        e.buy += share * buy; e.sell += share * (1 - buy);
      }
      total += k.v;
    }
    const rows = [...bins.entries()].sort((a, b) => a[0] - b[0]).map(([b, e]) => ({ p: b * step, buy: e.buy, sell: e.sell, v: e.buy + e.sell }));
    if (!rows.length) return null;
    let pi = 0;
    rows.forEach((r, i) => { if (r.v > rows[pi].v) pi = i; });
    let lo = pi, hi = pi, acc = rows[pi].v;
    while (acc < 0.7 * total && (lo > 0 || hi < rows.length - 1)) {
      const up = hi < rows.length - 1 ? rows[hi + 1].v : -1, dn = lo > 0 ? rows[lo - 1].v : -1;
      acc += up >= dn ? rows[++hi].v : rows[--lo].v;
    }
    return { rows, step, from, total, max: rows[pi].v, poc: rows[pi].p + step / 2, vah: rows[hi].p + step, val: rows[lo].p };
  }

  // 1-minute candles -> candles of `ms` length. The last one may still be forming.
  function aggregate(c, ms) {
    const out = [];
    for (const k of c) {
      const t = Math.floor(k.t / ms) * ms, last = out[out.length - 1];
      if (last && last.t === t) { last.h = Math.max(last.h, k.h); last.l = Math.min(last.l, k.l); last.c = k.c; last.v += k.v; last.bv += k.bv; }
      else out.push({ t, o: k.o, h: k.h, l: k.l, c: k.c, v: k.v, bv: k.bv });
    }
    return out;
  }
  function atrLast(c, n) {
    let atr = 0;
    for (let i = 0; i < c.length; i++) {
      const tr = i ? Math.max(c[i].h - c[i].l, Math.abs(c[i].h - c[i - 1].c), Math.abs(c[i].l - c[i - 1].c)) : c[i].h - c[i].l;
      atr = i < n ? (atr * i + tr) / (i + 1) : (atr * (n - 1) + tr) / n;
    }
    return atr;
  }
  function ema(v, n) {
    const k = 2 / (n + 1), out = [v[0]];
    for (let i = 1; i < v.length; i++) out.push(out[i - 1] + k * (v[i] - out[i - 1]));
    return out;
  }

  // One side of the setup check: buy at support (up = true) or sell at resistance.
  // Score = points for every condition that agrees, 0-100. It counts agreement; it is not a win rate.
  //   level(s) reached   up to 45   sum of the weights of the levels the last two candles reached
  //   gamma regime       +15 / -10  above zero gamma moves into levels tend to fade, below it levels break more often
  //   30-minute trend    +10 / -10  with or against the trade
  //   tape               +10 / -5   buying or selling in the last 15 minutes
  //   rejection candle   +10 / +5   closed in the far 25 % / 40 % of its range, away from the level
  //   reward vs risk     +10 / +5   target at least 2 x / 1.5 x the stop distance
  function setup(up, inp, a) {
    const c = inp.c5, k = c[c.length - 1], p = c[c.length - 2], side = up ? 'buy' : 'sell';
    const ext = up ? Math.min(k.l, p.l) : Math.max(k.h, p.h);                 // how far the last two candles reached
    const bands = up ? inp.supports : inp.resistances;
    const hit = bands.filter(z => up ? ext <= z.hi && k.c >= z.lo && ext >= z.lo - 2 * a : ext >= z.lo && k.c <= z.hi && ext <= z.hi + 2 * a);
    if (!hit.length) {
      const near = bands.filter(z => inp.price <= z.hi + 0.2 * a && inp.price >= z.lo - 0.2 * a);
      return near.length ? { side, state: 'watch', levels: near.map(z => z.name), reasons: [], score: 0 } : null;
    }
    const reasons = [], add = (pts, text) => reasons.push({ pts, text });
    const total = () => Math.max(0, Math.min(100, reasons.reduce((s, r) => s + r.pts, 0)));
    add(Math.min(45, hit.reduce((s, z) => s + z.w, 0)), `${up ? 'At support' : 'At resistance'}: ${hit.map(z => z.name).join(' + ')}`);
    if (inp.regime) add(inp.regime > 0 ? 15 : -10, inp.regime > 0 ? 'Above zero gamma: moves into levels tend to fade' : 'Below zero gamma: levels break more often');
    if (inp.trend) add((inp.trend > 0) === up ? 10 : -10, `30-minute trend is ${inp.trend > 0 ? 'up' : 'down'}`);
    if (Math.abs(inp.tape) >= 0.08) add((inp.tape > 0) === up ? 10 : -5, `Last 15 minutes: more ${inp.tape > 0 ? 'buying' : 'selling'}`);
    const range = k.h - k.l, pos = range > 0 ? (up ? k.c - k.l : k.h - k.c) / range : 0;
    if (!((up ? k.c > k.o : k.c < k.o) && pos >= 0.6 && range >= 0.5 * a))
      return { side, state: 'watch', levels: hit.map(z => z.name), reasons, score: total() };
    add(pos >= 0.75 ? 10 : 5, `5-minute candle closed back ${up ? 'up' : 'down'} from the level`);
    // stop beyond the candle extreme, or beyond the level's far edge when that is close by
    let base = ext;
    for (const z of hit) {
      const far = up ? z.lo : z.hi;
      if (up ? far < base && base - far <= 1.5 * a : far > base && far - base <= 1.5 * a) base = far;
    }
    const entry = k.c, stop = up ? base - 0.3 * a : base + 0.3 * a, risk = Math.abs(entry - stop);
    // target = the nearest level in the way; a level closer than 0.3 x risk counts as the same area
    const ahead = (up ? inp.resistances.map(z => ({ p: z.lo, name: z.name })) : inp.supports.map(z => ({ p: z.hi, name: z.name })))
      .concat(inp.magnets || []).filter(t => up ? t.p > entry + 0.3 * risk : t.p < entry - 0.3 * risk).sort((x, y) => up ? x.p - y.p : y.p - x.p);
    const tgt = ahead[0] || { p: up ? entry + 2 * risk : entry - 2 * risk, name: 'twice the risk, no level ahead' };
    const rr = Math.abs(tgt.p - entry) / risk;
    if (rr >= 1.5) add(rr >= 2 ? 10 : 5, `Reward is ${rr.toFixed(1)} x the risk`);
    const score = total();
    let state = side, note = '';
    if (rr < 1.2) { state = 'skip'; note = `not worth it: the target (${tgt.name}) is only ${rr.toFixed(1)} x the risk away`; }
    else if (risk > 4 * a) { state = 'skip'; note = 'not worth it: the stop would be too far away'; }
    else if (score < 55) { state = 'skip'; note = `weak setup: score ${score}, a signal needs 55`; }
    return { side, state, note, score, reasons, entry, stop, target: tgt.p, targetName: tgt.name, rr, t: k.t };
  }

  // Turns what is on screen into the input of signal(). Used by gold_gex.html and by the backtest
  // (GOLD/gex_signals), so both judge a setup the same way. All prices are candle prices.
  // q: { c5, price, zones, lines: [{side: 'support' | 'resistance', p, w, name}], flip, profile, closes30, tape,
  //      tolMin }  tolMin = the smallest half-width of a level band, 1.5 $ (gold) when left out; other instruments
  //                pass the same share of their price, and two lines closer than tolMin / 30 count as one level.
  function inputs(q) {
    const tolMin = q.tolMin > 0 ? q.tolMin : 1.5;
    const tol = Math.max(tolMin, 0.25 * atrLast(q.c5, 14)), sup = [], res = [], magnets = [];
    for (const z of q.zones || []) (z.type === 'demand' ? sup : res).push({ lo: z.bottom, hi: z.top, w: z.tested ? 18 : 30, zone: z,
      name: (z.tf ? `${z.type === 'demand' ? 'BUY' : 'SELL'} zone ${z.tf}` : `30m ${z.type} zone`) + (z.tested ? ' (tested)' : '') });
    const line = (arr, p, w, name) => {                        // a single price becomes a band of +/- tol
      const e = arr.find(x => x.p !== undefined && Math.abs(x.p - p) < tolMin / 30);
      if (e) { e.w = Math.max(e.w, w); e.name += ' / ' + name; } else arr.push({ lo: p - tol, hi: p + tol, p, w, name });
    };
    for (const w of q.lines || []) line(w.side === 'support' ? sup : res, w.p, w.w, w.name);
    let regime = 0;
    if (q.flip) { magnets.push({ p: q.flip, name: 'Zero Gamma' }); regime = q.price > q.flip ? 1 : -1; }
    if (q.profile) {
      line(sup, q.profile.val, 12, 'value area low'); line(res, q.profile.vah, 12, 'value area high');
      magnets.push({ p: q.profile.poc, name: 'POC' });
    }
    // 30-minute trend: last closed candle against its 20-candle average, and that average rising or falling
    const c = q.closes30 || [], e = c.length > 25 ? ema(c, 20) : null, n = c.length - 1;
    const trend = !e ? 0 : c[n] > e[n] && e[n] > e[n - 3] ? 1 : c[n] < e[n] && e[n] < e[n - 3] ? -1 : 0;
    return { c5: q.c5, price: q.price, supports: sup, resistances: res, magnets, regime, trend, tape: q.tape || 0 };
  }

  // Trade idea from CLOSED 5-minute candles and the levels on screen.
  // inp: { c5, price, supports / resistances: [{lo, hi, w, name}], magnets: [{p, name}], regime, trend, tape }
  // state: 'buy' / 'sell' (confirmed and worth it), 'skip' (confirmed but not worth it), 'watch' (at a level,
  // no rejection candle yet), 'none'. t = start of the trigger candle; the idea exists from that candle's close.
  function signal(inp) {
    if (!inp.c5 || inp.c5.length < 20) return { state: 'none' };
    const a = atrLast(inp.c5, 14), rank = { buy: 3, sell: 3, skip: 2, watch: 1 };
    const found = [setup(true, inp, a), setup(false, inp, a)].filter(Boolean).sort((x, y) => rank[y.state] - rank[x.state] || y.score - x.score);
    return found[0] || { state: 'none' };
  }

  return { ozPerShare, nyOffsetHours, nyClose, years, dte, sessionStart, bsGamma, expiries, table, walls, wallsOi, gammaFlip, zones, boxes,
           tradeZones, absorption, profile, aggregate, atrLast, ema, inputs, signal };
});
