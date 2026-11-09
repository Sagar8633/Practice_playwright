/* Gold liquidity heatmap engine (ATAS / Bookmap style).
 *
 * Order book (L2) + tape (trades)  ->  time x price columns  ->  bias metrics.
 * Plain script: the browser loads it with <script src>, node with require().
 *
 * Model
 *   - Prices are integer tick indexes (price / exchange tick). Heat rows are
 *     "buckets" of aggMult ticks (aggTick = aggMult * tick), like ATAS "tick aggregation".
 *   - Every columnMs a Column is cut: resting bid/ask size per bucket in a window of
 *     +-halfRange buckets around mid, plus the trades of that interval (footprint per
 *     bucket, buy/sell volume, OHLC in ticks) and the running cumulative delta (CVD).
 *   - metrics() turns the live book + recent tape into a bias score with reasons.
 */
(function (root) {
'use strict';

class Ring {
  constructor(n) { this.n = n; this.a = new Array(n); this.len = 0; this.head = 0; }
  push(x) { this.a[(this.head + this.len) % this.n] = x; if (this.len < this.n) this.len++; else this.head = (this.head + 1) % this.n; }
  get(i) { return this.a[(this.head + i) % this.n]; }
  last() { return this.len ? this.get(this.len - 1) : undefined; }
  clear() { this.len = 0; this.head = 0; }
  toArray() { const o = new Array(this.len); for (let i = 0; i < this.len; i++) o[i] = this.get(i); return o; }
}

function median(arr) {
  if (!arr.length) return 0;
  const s = arr.slice().sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

class BookEngine {
  constructor(opts) {
    this.tick = opts.tick;                       // exchange price tick, e.g. 0.01
    this.halfRange = opts.halfRange || 400;      // buckets kept each side of mid per column
    this.columnMs = opts.columnMs || 1000;
    this.columns = new Ring(opts.maxColumns || 3600);
    this.setAggregation(opts.aggTick || 0.1);
    this.bids = new Map();                       // tickIdx -> qty
    this.asks = new Map();
    this.synced = false;
    this.cvd = 0;
    this.lastPrice = NaN;
    this.lastTick = 0;
    this.bb = 0; this.ba = 0;                    // best bid / ask tick (from the last column)
    this.trades = [];                            // since the last column: {t, k, q, side}
    this.recentTrades = new Ring(50000);         // for metrics
    this.stats = { updates: 0, trades: 0, resyncs: 0 };
    this.cur = null;                             // OHLC (ticks) of the column in progress
  }

  setAggregation(aggTick) {
    this.aggMult = Math.max(1, Math.round(aggTick / this.tick));
    this.aggTick = this.aggMult * this.tick;
  }
  toTick(p) { return Math.round(p / this.tick); }
  bucketOf(k) { return Math.floor(k / this.aggMult); }
  bucketLow(b) { return b * this.aggMult * this.tick; }          // lower price edge of a bucket
  bucketMid(b) { return (b + 0.5) * this.aggMult * this.tick; }

  // ------------------------------------------------------------ book
  applySnapshot(bids, asks) {
    this.bids.clear(); this.asks.clear();
    this._apply(this.bids, bids); this._apply(this.asks, asks);
    this.synced = true;
  }
  applyDelta(bids, asks) {
    this._apply(this.bids, bids); this._apply(this.asks, asks);
    this.stats.updates++;
  }
  _apply(map, levels) {
    for (let i = 0; i < levels.length; i++) {
      const q = +levels[i][1], k = this.toTick(+levels[i][0]);
      if (q > 0) map.set(k, q); else map.delete(k);
    }
  }
  reset() { this.bids.clear(); this.asks.clear(); this.synced = false; this.stats.resyncs++; }

  best() {
    let bb = -Infinity, ba = Infinity;
    for (const k of this.bids.keys()) if (k > bb) bb = k;
    for (const k of this.asks.keys()) if (k < ba) ba = k;
    return [bb, ba];
  }

  // ------------------------------------------------------------ tape
  addTrade(t, price, qty, side) {
    const k = this.toTick(price);
    this.lastPrice = price; this.lastTick = k;
    this.cvd += side === 'buy' ? qty : -qty;
    this.stats.trades++;
    const tr = { t, k, q: qty, side };
    this.trades.push(tr); this.recentTrades.push(tr);
    const c = this.cur || (this.cur = { o: k, h: k, l: k, c: k });
    c.c = k; if (k > c.h) c.h = k; if (k < c.l) c.l = k;
  }

  // ------------------------------------------------------------ columns
  /** Cut a column at time `now`. Returns null while the book is empty. */
  tickColumn(now) {
    const [bb, ba] = this.best();
    if (!isFinite(bb) || !isFinite(ba)) return null;
    this.bb = bb; this.ba = ba;
    const midB = this.bucketOf(Math.round((bb + ba) / 2));
    const base = midB - this.halfRange, W = 2 * this.halfRange + 1;
    const bidQ = new Float32Array(W), askQ = new Float32Array(W);
    for (const [k, q] of this.bids) { const i = this.bucketOf(k) - base; if (i >= 0 && i < W) bidQ[i] += q; }
    for (const [k, q] of this.asks) { const i = this.bucketOf(k) - base; if (i >= 0 && i < W) askQ[i] += q; }
    let buy = 0, sell = 0;
    const fp = new Map();                              // bucket -> [buyVol, sellVol]
    for (const tr of this.trades) {
      const b = this.bucketOf(tr.k);
      let e = fp.get(b); if (!e) fp.set(b, e = [0, 0]);
      if (tr.side === 'buy') { e[0] += tr.q; buy += tr.q; } else { e[1] += tr.q; sell += tr.q; }
    }
    const c = this.cur;
    const col = { t: now, base, W, bidQ, askQ, bb, ba, buy, sell, delta: buy - sell, cvd: this.cvd, fp,
                  trades: this.trades, o: c ? c.o : null, h: c ? c.h : null, l: c ? c.l : null, c: c ? c.c : null };
    this.trades = []; this.cur = null;
    this.columns.push(col);
    return col;
  }

  static qtyAt(col, bucket, side) {
    const i = bucket - col.base;
    if (i < 0 || i >= col.W) return 0;
    return side === 'bid' ? col.bidQ[i] : col.askQ[i];
  }

  // ------------------------------------------------------------ key levels
  /**
   * The biggest resting-liquidity levels on each side of the price, for humans:
   * the book is clustered into price bands of `widthUsd` within +-rangePct of
   * mid; the `topN` largest bands per side are returned nearest-first with
   *   price (size-weighted), low/high (band edges), size, ratio (vs the median band),
   *   distUsd/distPct, heldS (seconds the band has kept >= 50% of its current size),
   *   trend ('growing' | 'shrinking' | 'steady' | 'new' vs ~60 s ago).
   * asks = sell orders above price (resistance), bids = buy orders below (support).
   */
  keyLevels(cfg) {
    cfg = cfg || {};
    const widthUsd = cfg.widthUsd ?? 0.5, rangePct = cfg.rangePct ?? 1.0, topN = cfg.topN ?? 5;
    const tick = this.tick, bb = this.bb, ba = this.ba;
    if (!bb || !ba) return null;
    const mid = (bb + ba) / 2 * tick;
    const lw = Math.max(this.aggTick, Math.round(widthUsd / this.aggTick) * this.aggTick);
    const lwTicks = Math.round(lw / tick);
    const range = mid * rangePct / 100;
    const gather = (map, below) => {
      const out = new Map();
      for (const [k, q] of map) {
        const p = k * tick;
        if ((below ? mid - p : p - mid) > range) continue;
        const c = Math.floor(k / lwTicks);
        let e = out.get(c); if (!e) out.set(c, e = { size: 0, w: 0 });
        e.size += q; e.w += q * p;
      }
      return out;
    };
    const bidC = gather(this.bids, true), askC = gather(this.asks, false);
    const med = median([...bidC.values(), ...askC.values()].map(e => e.size)) || 1e-9;
    const build = (cmap, side) => {
      const arr = [];
      for (const [c, e] of cmap) arr.push({ side, cLo: c, cHi: c, low: c * lw, high: (c + 1) * lw, price: e.w / e.size, size: e.size, w: e.w });
      arr.sort((a, b) => b.size - a.size);
      // the biggest bands; neighbouring bands are one wall, so merge them into a zone
      const top = arr.slice(0, topN + 2).sort((a, b) => a.cLo - b.cLo);
      const zones = [];
      for (const x of top) {
        const z = zones[zones.length - 1];
        if (z && x.cLo === z.cHi + 1) { z.cHi = x.cHi; z.high = x.high; z.size += x.size; z.w += x.w; z.price = z.w / z.size; }
        else zones.push(x);
      }
      zones.sort((a, b) => b.size - a.size);
      const out = zones.slice(0, topN);
      out.forEach((x, i) => {
        x.rank = i + 1; x.ratio = x.size / med / (x.cHi - x.cLo + 1);   // vs a normal band of the same width
        x.distUsd = Math.abs(x.price - mid); x.distPct = x.distUsd / mid * 100;
        Object.assign(x, this._levelHistory(x, side, lwTicks));
        delete x.w;
      });
      out.sort((a, b) => a.distUsd - b.distUsd);
      return out;
    };
    return { mid, widthUsd: lw, median: med, asks: build(askC, 'ask'), bids: build(bidC, 'bid') };
  }

  _levelHistory(x, side, lwTicks) {
    const n = this.columns.len;
    if (!n) return { heldS: 0, trend: 'new', sizeAgo: null };
    const bLo = Math.floor((x.cLo * lwTicks) / this.aggMult), bHi = Math.floor(((x.cHi + 1) * lwTicks - 1) / this.aggMult);
    const sizeIn = col => {
      const arr = side === 'bid' ? col.bidQ : col.askQ; let s = 0;
      for (let b = bLo; b <= bHi; b++) { const i = b - col.base; if (i >= 0 && i < col.W) s += arr[i]; }
      return s;
    };
    const half = x.size * 0.5; let first = null;
    for (let i = n - 1; i >= 0; i--) { const col = this.columns.get(i); if (sizeIn(col) < half) break; first = col.t; }
    const heldS = first != null ? (this.columns.get(n - 1).t - first) / 1000 : 0;
    const back = Math.min(n - 1, Math.round(60000 / this.columnMs));
    const sizeAgo = back > 0 ? sizeIn(this.columns.get(n - 1 - back)) : null;
    const trend = sizeAgo == null ? 'new' : x.size > sizeAgo * 1.25 ? 'growing' : x.size < sizeAgo * 0.75 ? 'shrinking' : 'steady';
    return { heldS, trend, sizeAgo };
  }

  // ------------------------------------------------------------ bias
  /**
   * Bias from the live book and the recent tape. Heuristic, not a backtested edge.
   *   imbNear/imbWide : (bid - ask) / (bid + ask) resting size within +-nearPct / widePct of price
   *   r1 / r5         : (buy - sell) / (buy + sell) traded volume over the last 1 / 5 minutes
   *   wallAbove/Below : largest aggregated level within widePct, flagged when >= wallMult x median level,
   *                     "pulled" when it lost >= 50% in the last 10 s (spoof-like)
   *   absorption      : one bucket in the last 2 min took >= absMult x the average bucket volume while
   *                     price is still within 3 buckets of it; the dominant aggressor side was absorbed
   */
  metrics(now, cfg) {
    cfg = cfg || {};
    const nearPct = cfg.nearPct ?? 0.05, widePct = cfg.widePct ?? 0.25, wallMult = cfg.wallMult ?? 8;
    const absMult = cfg.absMult ?? 3, tick = this.tick;
    const bb = this.bb, ba = this.ba;
    if (!bb || !ba) return null;
    const mid = (bb + ba) / 2 * tick;
    const nearT = Math.max(1, Math.round(mid * nearPct / 100 / tick));
    const wideT = Math.max(nearT, Math.round(mid * widePct / 100 / tick));

    let bidNear = 0, askNear = 0, bidWide = 0, askWide = 0;
    const bidB = new Map(), askB = new Map();
    for (const [k, q] of this.bids) {
      const d = bb - k; if (d > wideT) continue;
      bidWide += q; if (d <= nearT) bidNear += q;
      const b = this.bucketOf(k); bidB.set(b, (bidB.get(b) || 0) + q);
    }
    for (const [k, q] of this.asks) {
      const d = k - ba; if (d > wideT) continue;
      askWide += q; if (d <= nearT) askNear += q;
      const b = this.bucketOf(k); askB.set(b, (askB.get(b) || 0) + q);
    }
    const imbNear = bidNear + askNear ? (bidNear - askNear) / (bidNear + askNear) : 0;
    const imbWide = bidWide + askWide ? (bidWide - askWide) / (bidWide + askWide) : 0;

    const allLevels = [...bidB.values(), ...askB.values()];
    const med = median(allLevels) || 1e-9;
    const wall = (map, side) => {
      let best = null;
      for (const [b, q] of map) if (!best || q > best.qty) best = { bucket: b, qty: q };
      if (!best) return null;
      const price = this.bucketMid(best.bucket);
      const ratio = best.qty / med;
      const distUsd = Math.abs(price - mid);
      let pulled = false, prevQty = null;
      const n = this.columns.len, back = Math.round(10000 / this.columnMs);
      if (n > back) {
        prevQty = BookEngine.qtyAt(this.columns.get(n - 1 - back), best.bucket, side);
        pulled = prevQty > 0 && best.qty < prevQty * 0.5 && prevQty >= wallMult * med;
      }
      return { price, qty: best.qty, ratio, distUsd, distPct: distUsd / mid * 100, isWall: ratio >= wallMult, pulled, prevQty };
    };
    const wallBelow = wall(bidB, 'bid'), wallAbove = wall(askB, 'ask');

    let buy1 = 0, sell1 = 0, buy5 = 0, sell5 = 0;
    const rt = this.recentTrades;
    for (let i = rt.len - 1; i >= 0; i--) {
      const tr = rt.get(i); const age = now - tr.t;
      if (age > 300000) break;
      if (tr.side === 'buy') { buy5 += tr.q; if (age <= 60000) buy1 += tr.q; }
      else { sell5 += tr.q; if (age <= 60000) sell1 += tr.q; }
    }
    const r1 = buy1 + sell1 ? (buy1 - sell1) / (buy1 + sell1) : 0;
    const r5 = buy5 + sell5 ? (buy5 - sell5) / (buy5 + sell5) : 0;

    // absorption over the last 2 minutes of columns
    let absorption = null;
    {
      const vol = new Map(); let total = 0;
      const n = this.columns.len, back = Math.min(n, Math.round(120000 / this.columnMs));
      for (let i = n - back; i < n; i++) {
        const col = this.columns.get(i);
        for (const [b, e] of col.fp) { const v = vol.get(b) || [0, 0]; v[0] += e[0]; v[1] += e[1]; vol.set(b, v); total += e[0] + e[1]; }
      }
      if (vol.size >= 3) {
        let top = null;
        for (const [b, v] of vol) if (!top || v[0] + v[1] > top.v) top = { b, v: v[0] + v[1], buy: v[0], sell: v[1] };
        const avg = total / vol.size;
        const curB = this.bucketOf(this.lastTick || Math.round((bb + ba) / 2));
        if (top && top.v >= absMult * avg && Math.abs(curB - top.b) <= 3) {
          const buyShare = top.buy / top.v;
          const side = buyShare >= 0.6 ? 'buyers' : buyShare <= 0.4 ? 'sellers' : null;
          if (side) absorption = { price: this.bucketMid(top.b), volume: top.v, side, bias: side === 'sellers' ? 'bullish' : 'bearish' };
        }
      }
    }

    const reasons = [];
    let s = 0.30 * imbNear + 0.20 * imbWide + 0.30 * r5 + 0.20 * r1;
    reasons.push(`book near ${fmtSigned(imbNear)}`, `book wide ${fmtSigned(imbWide)}`, `tape 5m ${fmtSigned(r5)}`, `tape 1m ${fmtSigned(r1)}`);
    if (wallAbove && wallAbove.isWall && wallAbove.distPct <= 0.1) {
      if (wallAbove.pulled) { s += 0.10; reasons.push(`ask wall ${wallAbove.price.toFixed(2)} PULLED (${fmt(wallAbove.prevQty)}->${fmt(wallAbove.qty)})`); }
      else { s -= 0.15; reasons.push(`ask wall ${wallAbove.price.toFixed(2)} x${wallAbove.ratio.toFixed(0)} ${wallAbove.distPct.toFixed(2)}% above`); }
    }
    if (wallBelow && wallBelow.isWall && wallBelow.distPct <= 0.1) {
      if (wallBelow.pulled) { s -= 0.10; reasons.push(`bid wall ${wallBelow.price.toFixed(2)} PULLED (${fmt(wallBelow.prevQty)}->${fmt(wallBelow.qty)})`); }
      else { s += 0.15; reasons.push(`bid wall ${wallBelow.price.toFixed(2)} x${wallBelow.ratio.toFixed(0)} ${wallBelow.distPct.toFixed(2)}% below`); }
    }
    if (absorption) { s += absorption.bias === 'bullish' ? 0.2 : -0.2; reasons.push(`${absorption.side} absorbed @${absorption.price.toFixed(2)} (${fmt(absorption.volume)})`); }
    s = Math.max(-1, Math.min(1, s));
    const bias = s >= 0.25 ? 'BULLISH' : s <= -0.25 ? 'BEARISH' : 'NEUTRAL';
    return { score: s, bias, reasons, imbNear, imbWide, r1, r5, buy1, sell1, buy5, sell5,
             wallAbove, wallBelow, absorption, mid, spread: (ba - bb) * tick, bidNear, askNear, bidWide, askWide };
  }
}

function fmt(x) { return x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2); }
function fmtSigned(x) { return (x >= 0 ? '+' : '') + x.toFixed(2); }

// ------------------------------------------------------------------ feeds
const FEEDS = {
  binance_fut: {
    name: 'Binance Futures', kind: 'binance', futures: true, symbol: 'PAXGUSDT', tick: 0.01,
    // @trade, not @aggTrade: the futures aggTrade stream stayed silent for PAXGUSDT (checked 2026-10-20)
    ws: s => `wss://fstream.binance.com/stream?streams=${s.toLowerCase()}@depth@100ms/${s.toLowerCase()}@trade`,
    snapshot: s => `https://fapi.binance.com/fapi/v1/depth?symbol=${s}&limit=1000`,
  },
  binance_spot: {
    name: 'Binance Spot', kind: 'binance', futures: false, symbol: 'PAXGUSDT', tick: 0.01,
    ws: s => `wss://stream.binance.com:9443/stream?streams=${s.toLowerCase()}@depth@100ms/${s.toLowerCase()}@aggTrade`,
    snapshot: s => `https://api.binance.com/api/v3/depth?symbol=${s}&limit=5000`,
  },
  bybit: {
    name: 'Bybit Perp', kind: 'bybit', symbol: 'XAUTUSDT', tick: 0.01,
    ws: () => 'wss://stream.bybit.com/v5/public/linear',
    topics: s => [`orderbook.200.${s}`, `publicTrade.${s}`],
  },
};

/**
 * Connects a feed to a BookEngine: Binance diff-depth sync (REST snapshot + buffered
 * deltas with update-id checks) or Bybit (snapshot + delta over the socket).
 * Needs globalThis.WebSocket and fetch (browser, or node >= 22).
 */
class FeedClient {
  constructor(feedKey, symbol, engine, hooks) {
    this.feed = FEEDS[feedKey]; this.symbol = symbol || this.feed.symbol;
    this.engine = engine; this.hooks = hooks || {};
    this.ws = null; this.closed = false; this.attempt = 0;
    this.buffer = []; this.lastU = null; this.snapshotId = null;
    this.state = 'idle'; this.lastEventTime = 0; this.latencyMs = 0;
    this.pingTimer = null;
  }
  setState(s, extra) { this.state = s; if (this.hooks.onState) this.hooks.onState(s, extra); }
  log(...a) { if (this.hooks.onLog) this.hooks.onLog(a.join(' ')); }

  start() {
    this.closed = false; this.engine.reset(); this.buffer = []; this.lastU = null;
    this.setState('connecting');
    const WS = root.WebSocket;
    const ws = this.ws = new WS(this.feed.ws(this.symbol));
    ws.onopen = () => {
      this.attempt = 0; this.setState('open');
      if (this.feed.kind === 'bybit') {
        ws.send(JSON.stringify({ op: 'subscribe', args: this.feed.topics(this.symbol) }));
        this.pingTimer = setInterval(() => { try { ws.send(JSON.stringify({ op: 'ping' })); } catch (e) { /* closing */ } }, 20000);
      } else {
        this.fetchSnapshot();
      }
    };
    ws.onmessage = ev => this.onMessage(JSON.parse(ev.data));
    ws.onerror = () => this.log('websocket error');
    ws.onclose = () => { clearInterval(this.pingTimer); if (!this.closed) this.reconnect(); };
  }
  stop() { this.closed = true; clearInterval(this.pingTimer); if (this.ws) try { this.ws.close(); } catch (e) { /* ignore */ } this.setState('stopped'); }
  reconnect() {
    const delay = Math.min(30000, 1000 * Math.pow(2, this.attempt++));
    this.setState('reconnecting', delay);
    setTimeout(() => { if (!this.closed) this.start(); }, delay);
  }

  async fetchSnapshot() {
    this.setState('snapshot');
    try {
      const r = await root.fetch(this.feed.snapshot(this.symbol));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const snap = await r.json();
      this.snapshotId = snap.lastUpdateId;
      this.engine.applySnapshot(snap.bids, snap.asks);
      this.lastU = null;
      const pending = this.buffer; this.buffer = null;
      for (const d of pending) if (!this.applyBinance(d)) return;   // applyBinance resyncs on a gap
      this.setState('live');
    } catch (e) {
      this.log('snapshot failed: ' + e.message);
      setTimeout(() => { if (!this.closed && this.ws && this.ws.readyState === 1) { this.buffer = []; this.fetchSnapshot(); } }, 2000);
    }
  }

  onMessage(m) {
    const eng = this.engine;
    if (this.feed.kind === 'binance') {
      const d = m.data; if (!d) return;
      if (d.e === 'aggTrade' || d.e === 'trade') {
        if (d.X && d.X !== 'MARKET') return;          // futures @trade: skip liquidations/ADL/insurance fills
        this.lastEventTime = d.T; this.latencyMs = Date.now() - d.E;
        eng.addTrade(d.T, +d.p, +d.q, d.m ? 'sell' : 'buy');
        if (this.hooks.onTrade) this.hooks.onTrade();
      } else if (d.e === 'depthUpdate') {
        this.latencyMs = Date.now() - d.E;
        if (this.buffer) { this.buffer.push(d); return; }   // waiting for the snapshot
        this.applyBinance(d);
      }
    } else if (this.feed.kind === 'bybit') {
      if (!m.topic) return;
      if (m.topic.startsWith('orderbook')) {
        this.latencyMs = Date.now() - m.ts;
        if (m.type === 'snapshot' || m.data.u === 1) { eng.applySnapshot(m.data.b, m.data.a); this.lastU = m.data.u; this.setState('live'); }
        else if (eng.synced) {
          if (this.lastU !== null && m.data.u <= this.lastU) return;   // stale
          eng.applyDelta(m.data.b, m.data.a); this.lastU = m.data.u;
        }
      } else if (m.topic.startsWith('publicTrade')) {
        for (const t of m.data) { this.lastEventTime = t.T; eng.addTrade(t.T, +t.p, +t.v, t.S === 'Buy' ? 'buy' : 'sell'); }
        if (this.hooks.onTrade) this.hooks.onTrade();
      }
    }
  }

  /** Binance diff-depth bookkeeping. Returns false after triggering a resync. */
  applyBinance(d) {
    const fut = this.feed.futures;
    if (this.lastU === null) {                      // first event after the snapshot
      const L = this.snapshotId;
      if (fut ? d.u < L : d.u <= L) return true;      // older than the snapshot: drop
      const ok = fut ? (d.U <= L && d.u >= L) : (d.U <= L + 1 && d.u >= L + 1);
      if (!ok) { this.log(`first event does not bracket the snapshot (U=${d.U} u=${d.u} L=${L}); resync`); this.resync(); return false; }
    } else {
      const ok = fut ? d.pu === this.lastU : d.U === this.lastU + 1;
      if (!ok) { this.log(`update gap (prev ${this.lastU}, got ${fut ? d.pu : d.U}); resync`); this.resync(); return false; }
    }
    this.engine.applyDelta(d.b, d.a); this.lastU = d.u;
    return true;
  }
  resync() { this.engine.reset(); this.buffer = []; this.lastU = null; this.fetchSnapshot(); }
}

// ------------------------------------------------------------------ serialization (recorder / replay)
function serializeColumn(col) {
  const nz = arr => { const o = []; for (let i = 0; i < arr.length; i++) if (arr[i] > 0) o.push(i, +arr[i].toFixed(4)); return o; };
  const fp = []; for (const [b, e] of col.fp) fp.push(b, +e[0].toFixed(4), +e[1].toFixed(4));
  const tr = col.trades.map(x => [x.t, x.k, x.q, x.side === 'buy' ? 1 : 0]);
  return [col.t, col.base, col.W, nz(col.bidQ), nz(col.askQ), col.bb, col.ba, +col.buy.toFixed(4), +col.sell.toFixed(4),
          +col.cvd.toFixed(4), col.o, col.h, col.l, col.c, fp, tr];
}
function parseColumn(a) {
  const [t, base, W, bz, az, bb, ba, buy, sell, cvd, o, h, l, c, fpa, tra] = a;
  const bidQ = new Float32Array(W), askQ = new Float32Array(W);
  for (let i = 0; i < bz.length; i += 2) bidQ[bz[i]] = bz[i + 1];
  for (let i = 0; i < az.length; i += 2) askQ[az[i]] = az[i + 1];
  const fp = new Map(); for (let i = 0; i < fpa.length; i += 3) fp.set(fpa[i], [fpa[i + 1], fpa[i + 2]]);
  const trades = tra.map(x => ({ t: x[0], k: x[1], q: x[2], side: x[3] ? 'buy' : 'sell' }));
  return { t, base, W, bidQ, askQ, bb, ba, buy, sell, delta: buy - sell, cvd, o, h, l, c, fp, trades };
}

root.HeatmapEngine = { Ring, BookEngine, FeedClient, FEEDS, serializeColumn, parseColumn, median };
})(typeof globalThis !== 'undefined' ? globalThis : this);
