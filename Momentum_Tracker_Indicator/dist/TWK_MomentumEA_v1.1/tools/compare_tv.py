"""Leg 1 of validation: Pine (live TradingView values) vs twk_core.py on the SAME TradingView bars.

Input: JSON dump taken from the chart's TWK Tracker study via the TradingView JS model:
  bars[i] = [time, open, high, low, close, volume]
  rows[i] = [time, SmartTrail, color, PH dot, color, PL dot, color, LONG alert, SHORT alert]
Pivot dots are stored on the CONFIRMATION bar (offset=-5 is applied only when drawing).

usage: python compare_tv.py <dump.json> [warmup_bars] [tie_mode]
"""
import json
import sys
from datetime import datetime, timezone

import twk_core as core

path = sys.argv[1]
warm = int(sys.argv[2]) if len(sys.argv) > 2 else 120
tie = int(sys.argv[3]) if len(sys.argv) > 3 else core.TIE_LEFT_EQUAL_OK

raw = json.load(open(path, encoding='utf-8'))
d = json.loads(raw) if isinstance(raw, str) else raw
bars, rows = d['bars'], d['rows']
t = [b[0] for b in bars]
o, h, l, c, v = ([b[k] for b in bars] for k in range(1, 6))
s = core.compute_series(o, h, l, c, v, tie=tie)


def ts(i):
    return datetime.fromtimestamp(t[i], timezone.utc).strftime('%m-%d %H:%M')


n = len(bars)
last_closed = n - 2          # bar n-1 is still forming on TradingView
st_err, sig_bad, piv_bad, checked = [], [], [], 0
first_match = None
for i in range(n - 1):
    tv_st = rows[i][1]
    if tv_st is None or s['st'][i] is None:
        continue
    err = abs(tv_st - s['st'][i])
    if err < 1e-6 and first_match is None:
        first_match = i
    if i < warm:
        continue
    checked += 1
    st_err.append(err)
    tv_long, tv_short = rows[i][7] == 1, rows[i][8] == 1
    if tv_long != s['long'][i] or tv_short != s['short'][i]:
        sig_bad.append((ts(i), 'TV', tv_long, tv_short, 'PY', s['long'][i], s['short'][i]))
    if i <= last_closed and ((rows[i][3] == 1) != (s['ph'][i] is not None) or (rows[i][5] == 1) != (s['pl'][i] is not None)):
        piv_bad.append((ts(i), 'TV ph/pl', rows[i][3], rows[i][5], 'PY', s['ph'][i], s['pl'][i]))

print(f'bars={n}  compared from bar {warm} ({ts(warm)}) to {ts(n - 2)}: {checked} bars   tie_mode={tie}')
print(f'first bar where Smart Trail matched to 1e-6: {first_match} ({ts(first_match) if first_match is not None else "-"})')
print(f'Smart Trail  max|err| = {max(st_err):.9f}   bars with err>1e-6: {sum(e > 1e-6 for e in st_err)}')
print(f'LONG/SHORT flags mismatched: {len(sig_bad)}')
for x in sig_bad[:10]:
    print('   ', x)
print(f'Pivot dots mismatched: {len(piv_bad)}')
for x in piv_bad[:10]:
    print('   ', x)

sigs = [i for i in range(warm, n - 1) if s['long'][i] or s['short'][i]]
print('\nsignals (python):')
for i in sigs:
    kind = 'LONG ' if s['long'][i] else 'SHORT'
    sl, tp, rk = s['sl'][i], s['tp'][i], s['risk'][i]
    print(f'  [{i}] {ts(i)} {kind} entry={c[i]:.3f} SL={sl:.3f} TP={"-" if tp is None else f"{tp:.3f}"} risk={rk:.3f}'
          f'  1m bV={s["bv"][i]:.0f} sV={s["sv"][i]:.0f} ADX={s["adx"][i]:.2f}')

if 'box' in d:
    print('\nTradingView current position box:', d['box'])
