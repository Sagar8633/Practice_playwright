// Browser-side port of the user's trade_with_kareena Tracker Pine v6 indicator.
// The GEX page supplies its own candles; the unavailable NSE:NIFTY benchmark is scored as neutral (0),
// matching the Pine script's fallback for an invalid benchmark symbol.
(function (global) {
  'use strict';

  const BUY = '#26a69a', SELL = '#ef5350', TRAIL = '#7e57c2';
  const MTF = [['1m', 60e3], ['3m', 180e3], ['5m', 300e3], ['15m', 900e3], ['30m', 1800e3],
    ['1h', 3600e3], ['2h', 7200e3], ['4h', 14400e3], ['1D', 86400e3]];
  const finite = Number.isFinite;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function sma(values, len) {
    const out = new Array(values.length).fill(NaN);
    let sum = 0, count = 0;
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (finite(v)) { sum += v; count++; }
      const old = i - len;
      if (old >= 0 && finite(values[old])) { sum -= values[old]; count--; }
      if (count === len) out[i] = sum / len;
    }
    return out;
  }

  // Pine ta.rma seed and Wilder recurrence, skipping unavailable source values.
  function rma(values, len) {
    const out = new Array(values.length).fill(NaN);
    let sum = 0, count = 0, prev = NaN;
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (!finite(v)) continue;
      if (count < len) {
        sum += v; count++;
        if (count === len) out[i] = prev = sum / len;
      } else out[i] = prev = (prev * (len - 1) + v) / len;
    }
    return out;
  }

  function atr(c, len) {
    const tr = c.map((k, i) => i === 0 ? k.h - k.l : Math.max(k.h - k.l, Math.abs(k.h - c[i - 1].c), Math.abs(k.l - c[i - 1].c)));
    return rma(tr, len);
  }

  // TradingView-style Wilder ADX from ta.dmi(14, 14), used by the 15-minute MT5 entry filter.
  function adx(c, diLen = 14, smoothLen = 14) {
    const tr = new Array(c.length).fill(NaN), plusDm = new Array(c.length).fill(NaN), minusDm = new Array(c.length).fill(NaN);
    for (let i = 0; i < c.length; i++) {
      if (i === 0) { tr[i] = c[i].h - c[i].l; continue; }
      const up = c[i].h - c[i - 1].h, down = c[i - 1].l - c[i].l;
      tr[i] = Math.max(c[i].h - c[i].l, Math.abs(c[i].h - c[i - 1].c), Math.abs(c[i].l - c[i - 1].c));
      plusDm[i] = up > down && up > 0 ? up : 0;
      minusDm[i] = down > up && down > 0 ? down : 0;
    }
    const trRma = rma(tr, diLen), plusRma = rma(plusDm, diLen), minusRma = rma(minusDm, diLen);
    const dx = new Array(c.length).fill(NaN);
    for (let i = 0; i < c.length; i++) {
      if (!finite(trRma[i]) || !finite(plusRma[i]) || !finite(minusRma[i]) || trRma[i] <= 0) continue;
      const plusDi = 100 * plusRma[i] / trRma[i], minusDi = 100 * minusRma[i] / trRma[i], sum = plusDi + minusDi;
      dx[i] = sum === 0 ? 0 : 100 * Math.abs(plusDi - minusDi) / sum;
    }
    return rma(dx, smoothLen);
  }

  function rsi(c, len) {
    const up = new Array(c.length).fill(NaN), down = new Array(c.length).fill(NaN);
    for (let i = 1; i < c.length; i++) {
      const ch = c[i].c - c[i - 1].c;
      up[i] = Math.max(ch, 0); down[i] = Math.max(-ch, 0);
    }
    const au = rma(up, len), ad = rma(down, len), out = new Array(c.length).fill(NaN);
    for (let i = 0; i < c.length; i++) {
      if (!finite(au[i]) || !finite(ad[i])) continue;
      out[i] = ad[i] === 0 ? 100 : au[i] === 0 ? 0 : 100 - 100 / (1 + au[i] / ad[i]);
    }
    return out;
  }

  function mfi(c, len) {
    const pos = new Float64Array(c.length), neg = new Float64Array(c.length), out = new Array(c.length).fill(NaN);
    for (let i = 1; i < c.length; i++) {
      const p = (c[i].h + c[i].l + c[i].c) / 3, prev = (c[i - 1].h + c[i - 1].l + c[i - 1].c) / 3;
      const flow = p * (c[i].v || 0);
      if (p > prev) pos[i] = flow; else if (p < prev) neg[i] = flow;
    }
    let ps = 0, ns = 0;
    for (let i = 0; i < c.length; i++) {
      ps += pos[i]; ns += neg[i];
      if (i >= len) { ps -= pos[i - len]; ns -= neg[i - len]; }
      if (i >= len) out[i] = ns === 0 ? (ps === 0 ? 50 : 100) : ps === 0 ? 0 : 100 - 100 / (1 + ps / ns);
    }
    return out;
  }

  function supertrend(c, factor, len) {
    const a = atr(c, len), value = new Array(c.length).fill(NaN), dir = new Array(c.length).fill(0);
    const upper = new Array(c.length).fill(NaN), lower = new Array(c.length).fill(NaN);
    for (let i = 0; i < c.length; i++) {
      if (!finite(a[i])) continue;
      const mid = (c[i].h + c[i].l) / 2;
      let u = mid + factor * a[i], l = mid - factor * a[i];
      if (i > 0 && finite(upper[i - 1]) && finite(lower[i - 1])) {
        if (!(u < upper[i - 1] || c[i - 1].c > upper[i - 1])) u = upper[i - 1];
        if (!(l > lower[i - 1] || c[i - 1].c < lower[i - 1])) l = lower[i - 1];
      }
      upper[i] = u; lower[i] = l;
      if (i === 0 || !finite(a[i - 1])) dir[i] = 1;
      else if (dir[i - 1] > 0) dir[i] = c[i].c > u ? -1 : 1;
      else dir[i] = c[i].c < l ? 1 : -1;
      value[i] = dir[i] < 0 ? l : u;
    }
    return { value, dir };
  }

  function pivots(c, len) {
    const high = new Array(c.length).fill(NaN), low = new Array(c.length).fill(NaN);
    const highConfirmed = new Array(c.length).fill(NaN), lowConfirmed = new Array(c.length).fill(NaN);
    for (let p = len; p < c.length - len; p++) {
      let isHigh = true, isLow = true;
      for (let j = p - len; j <= p + len; j++) {
        if (j === p) continue;
        if (c[j].h >= c[p].h) isHigh = false;
        if (c[j].l <= c[p].l) isLow = false;
        if (!isHigh && !isLow) break;
      }
      if (isHigh) { high[p] = c[p].h; highConfirmed[p + len] = c[p].h; }
      if (isLow) { low[p] = c[p].l; lowConfirmed[p + len] = c[p].l; }
    }
    return { high, low, highConfirmed, lowConfirmed };
  }

  function chartSeries(c) {
    const n = c.length, rLen = 14, volLen = 20;
    const vols = c.map(k => k.v || 0), volAvg = sma(vols, volLen), rVolAvg = sma(vols, rLen);
    const r = rsi(c, rLen), flow = mfi(c, rLen), st = supertrend(c, 1.5, 10), pv = pivots(c, 5), adx14 = adx(c, 14, 14);
    const priceMom = new Array(n).fill(NaN), volScore = new Array(n).fill(NaN), oiScore = new Array(n).fill(NaN),
      sectorScore = new Array(n).fill(0), smartScore = new Array(n).fill(NaN), rFactor = new Array(n).fill(NaN);
    for (let i = 0; i < n; i++) {
      if (finite(r[i])) priceMom[i] = (r[i] - 50) / 50 * 20;
      if (finite(rVolAvg[i])) volScore[i] = clamp(vols[i] / Math.max(rVolAvg[i], 1) - 1, -1, 1) * 20;
      if (finite(rVolAvg[i]) && i >= rLen && finite(rVolAvg[i - rLen])) {
        const roc = rVolAvg[i - rLen] === 0 ? NaN : (rVolAvg[i] / rVolAvg[i - rLen] - 1) * 100;
        if (finite(roc)) oiScore[i] = clamp(roc / 100, -1, 1) * 20;
      }
      if (finite(flow[i])) smartScore[i] = (flow[i] - 50) / 50 * 20;
      if (finite(priceMom[i]) && finite(volScore[i]) && finite(oiScore[i]) && finite(smartScore[i]))
        rFactor[i] = priceMom[i] + volScore[i] + sectorScore[i] + oiScore[i] + smartScore[i];
    }
    const long = new Array(n).fill(false), short = new Array(n).fill(false);
    let lastPL = NaN, lastPH = NaN, position = null;
    for (let i = 0; i < n; i++) {
      if (finite(pv.lowConfirmed[i])) lastPL = pv.lowConfirmed[i];
      if (finite(pv.highConfirmed[i])) lastPH = pv.highConfirmed[i];
      const bull = i > 0 && st.dir[i] < 0 && st.dir[i - 1] >= 0;
      const bear = i > 0 && st.dir[i] > 0 && st.dir[i - 1] <= 0;
      long[i] = bull;
      short[i] = bear;
      if (!bull && !bear) continue;
      const isLong = bull, entry = c[i].c;
      const stop = isLong ? (finite(lastPL) && lastPL < entry ? lastPL : st.value[i])
        : (finite(lastPH) && lastPH > entry ? lastPH : st.value[i]);
      const risk = isLong ? entry - stop : stop - entry;
      if (!(risk > 0)) continue;
      const target = isLong ? entry + 2 * risk : entry - 2 * risk;
      position = { i, isLong, entry, stop, target, rr: 2, end: i + 24 };
    }
    return { c, volAvg, rFactor, priceMom, volScore, sectorScore, oiScore, smartScore, st, adx: adx14, pivots: pv, long, short, position };
  }

  function aggregate(m1, ms) {
    const out = [];
    for (const k of m1) {
      const t = Math.floor(k.t / ms) * ms, last = out[out.length - 1];
      if (last && last.t === t) {
        last.h = Math.max(last.h, k.h); last.l = Math.min(last.l, k.l); last.c = k.c; last.v += k.v || 0;
      } else out.push({ t, o: k.o, h: k.h, l: k.l, c: k.c, v: k.v || 0 });
    }
    return out;
  }

  function mtfTable(m1, volLen) {
    return MTF.map(([label, ms]) => {
      const candles = aggregate(m1, ms);
      if (candles.length < volLen) return { label, buy: NaN, sell: NaN, score: NaN };
      let buy = 0, sell = 0;
      for (const k of candles.slice(-volLen)) {
        if (k.c > k.o) buy += k.v;
        else if (k.c < k.o) sell += k.v;
      }
      const score = (buy - sell) / Math.max(buy + sell, 1);
      return { label, buy, sell, score };
    });
  }

  function formatVol(v) {
    if (!finite(v)) return '--';
    const a = Math.abs(v), trim = n => n.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
    return a >= 1e9 ? trim(v / 1e9) + 'B' : a >= 1e6 ? trim(v / 1e6) + 'M' : a >= 1e3 ? trim(v / 1e3) + 'K' : trim(v);
  }
  const signed1 = v => finite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}` : '--';
  const resultText = s => !finite(s) ? '--' : s > 0 ? 'BUY' : s < 0 ? 'SELL' : 'FLAT';
  const rowColor = (s, alpha) => !finite(s) || s === 0 ? 'rgba(128,128,128,.6)' : s > 0 ? `rgba(38,166,154,${alpha})` : `rgba(239,83,80,${alpha})`;

  function currentSummary(data) {
    const i = data.rFactor.length - 1, v = arr => finite(arr[i]) ? arr[i] : NaN, r = v(data.rFactor);
    return {
      r,
      bias: !finite(r) ? 'LOADING' : r > 33 ? 'STRONG BUY' : r > 0 ? 'BUY' : r < -33 ? 'STRONG SELL' : r < 0 ? 'SELL' : 'NEUTRAL',
      parts: [
        ['Price Mom.', v(data.priceMom)], ['Volume', v(data.volScore)], ['Sector', v(data.sectorScore)],
        ['OI Proxy', v(data.oiScore)], ['Money Flow', v(data.smartScore)],
      ],
    };
  }

  function updateTable(root, data, light, version) {
    if (!root || root.dataset.version === String(version)) return;
    root.dataset.version = String(version);
    const table = document.createElement('table'), body = document.createElement('tbody'), summary = currentSummary(data);
    const addRow = (cells, bg, options) => {
      const tr = document.createElement('tr');
      for (const cell of cells) {
        const td = document.createElement(options && options.header ? 'th' : 'td');
        td.textContent = cell.text;
        if (cell.span) td.colSpan = cell.span;
        if (cell.align) td.style.textAlign = cell.align;
        if (bg && !(options && options.header)) td.style.backgroundColor = bg;
        tr.appendChild(td);
      }
      body.appendChild(tr);
    };
    addRow([{ text: 'TF' }, { text: 'Buy Vol' }, { text: 'Sell Vol' }, { text: 'Bias' }], null, { header: true });
    for (const row of data.mtf) addRow([
      { text: row.label }, { text: formatVol(row.buy), align: 'right' }, { text: formatVol(row.sell), align: 'right' }, { text: resultText(row.score) },
    ], rowColor(row.score, 0.85));
    addRow([{ text: 'R-FACTOR' }, { text: finite(summary.r) ? summary.r.toFixed(1) : '--', align: 'right' }, { text: 'BIAS' }, { text: summary.bias }], rowColor(summary.r, 0.85));
    for (const [name, score] of summary.parts) addRow([{ text: name }, { text: signed1(score), span: 3, align: 'right' }], rowColor(score, 0.85));
    table.appendChild(body);
    root.replaceChildren(table);
    const note = document.createElement('div');
    note.className = 'twk-note';
    note.textContent = 'NIFTY unavailable (Sector = 0). OI proxy uses volume change, not open interest.';
    root.appendChild(note);
    root.title = 'Port of trade_with_kareena Tracker. Values use this page’s candle feed.';
  }

  function label(ctx, x, y, text, color, align) {
    ctx.save(); ctx.font = '600 10px system-ui, "Segoe UI", sans-serif'; ctx.textAlign = align || 'center'; ctx.textBaseline = 'middle';
    const w = ctx.measureText(text).width + 10, h = 16;
    const left = align === 'right' ? x - w : align === 'left' ? x : x - w / 2;
    ctx.fillStyle = color; ctx.fillRect(left, y - h / 2, w, h);
    ctx.fillStyle = '#fff'; ctx.fillText(text, align === 'right' ? x - 5 : align === 'left' ? x + 5 : x, y);
    ctx.restore();
  }

  function drawPosition(ctx, p, input) {
    const x0 = input.xOf(p.i), x1 = Math.min(input.right, input.xOf(Math.max(p.end, input.last)));
    if (x1 <= 0 || x0 >= input.right || x1 <= x0) return;
    const yEntry = input.yOf(p.entry - input.basis), yStop = input.yOf(p.stop - input.basis), yTarget = input.yOf(p.target - input.basis);
    const x = Math.max(0, x0), w = Math.max(1, x1 - x);
    const rTop = Math.min(yEntry, yTarget), rBottom = Math.max(yEntry, yTarget);
    const sTop = Math.min(yEntry, yStop), sBottom = Math.max(yEntry, yStop);
    ctx.fillStyle = 'rgba(38,166,154,.24)'; ctx.fillRect(x, rTop, w, Math.max(1, rBottom - rTop));
    ctx.strokeStyle = 'rgba(38,166,154,.85)'; ctx.lineWidth = 1; ctx.strokeRect(x + .5, rTop + .5, Math.max(1, w - 1), Math.max(1, rBottom - rTop - 1));
    ctx.fillStyle = 'rgba(239,83,80,.24)'; ctx.fillRect(x, sTop, w, Math.max(1, sBottom - sTop));
    ctx.strokeStyle = 'rgba(239,83,80,.85)'; ctx.strokeRect(x + .5, sTop + .5, Math.max(1, w - 1), Math.max(1, sBottom - sTop - 1));
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(x, yEntry); ctx.lineTo(x1, yEntry); ctx.stroke(); ctx.setLineDash([]);
    const dec = input.dec === undefined ? 2 : input.dec, side = p.isLong ? 'LONG' : 'SHORT';
    label(ctx, x1 - 3, yTarget, `TP ${p.target.toFixed(dec)}`, BUY, 'right');
    label(ctx, x1 - 3, yStop, `SL ${p.stop.toFixed(dec)}`, SELL, 'right');
    label(ctx, x1 - 3, yEntry, `${side} @ ${p.entry.toFixed(dec)} (1:2)`, '#565d6b', 'right');
  }

  function draw(ctx, data, input) {
    if (!data || !input.c.length) return;
    const c = input.c, first = Math.max(0, input.first), last = Math.min(input.last, c.length - 1), cw = input.cw;
    ctx.save();

    // Smart Trail, with a break at each trend flip like plot.style_linebr.
    ctx.strokeStyle = TRAIL; ctx.lineWidth = 2; ctx.beginPath();
    let started = false, prevDir = 0;
    for (let i = Math.max(0, first - 1); i <= last; i++) {
      const value = data.st.value[i], direction = data.st.dir[i];
      if (!finite(value) || !direction) { started = false; prevDir = 0; continue; }
      const x = input.xOf(i), y = input.yOf(value - input.basis);
      if (!started || direction !== prevDir) { if (started) ctx.stroke(); ctx.beginPath(); ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
      prevDir = direction;
    }
    if (started) ctx.stroke();

    // High relative-volume footprint bubbles, sized by volume / 20-bar average.
    for (let i = first; i <= last; i++) {
      const avg = data.volAvg[i], volume = c[i].v || 0;
      if (!finite(avg) || !(avg > 0)) continue;
      const ratio = volume / Math.max(avg, 1);
      if (ratio < 1.8) continue;
      const radius = ratio > 4 ? 13 : ratio > 3 ? 11 : ratio > 2 ? 9 : 7;
      const x = input.xOf(i), y = input.yOf(((c[i].h + c[i].l + c[i].c) / 3) - input.basis);
      ctx.fillStyle = c[i].c >= c[i].o ? 'rgba(38,166,154,.9)' : 'rgba(239,83,80,.9)';
      ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = '600 8px system-ui, "Segoe UI", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(formatVol(volume), x, y);
    }

    // Smart Trail direction flips.
    for (let i = first; i <= last; i++) {
      if (!data.long[i] && !data.short[i]) continue;
      const up = data.long[i], x = input.xOf(i), y = up ? input.yOf(c[i].l - input.basis) + 18 : input.yOf(c[i].h - input.basis) - 18;
      label(ctx, x, y, up ? 'LONG' : 'SHORT', up ? BUY : SELL);
    }

    if (data.position) drawPosition(ctx, data.position, input);
    ctx.restore();
  }

  global.TWKTracker = {
    chartSeries,
    mtfTable: m1 => mtfTable(m1, 20),
    updateTable,
    draw,
  };
})(window);
