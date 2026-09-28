"""Leg 2 of validation: MQL5 (TWK_Tracker_MT5 CSV export) vs twk_core.py on the SAME MT5 bars.

Together with compare_tv.py (Pine == twk_core.py on TradingView bars) this proves
Pine == MQL5 for identical input bars.

The CSV starts mid-history while MQL5 computed from an earlier start (InpCalcBars),
so the first `warmup` rows are skipped to let the recursive RMA/Supertrend state converge.
The 3m row is not recomputed here (it needs M3 bars); it is checked against the Pine rule
by construction in TwkLastCompletedHtf.

usage: python compare_mt5.py <TWK_diag_XAUUSD_M1.csv> [warmup_rows]
  CSV lives in %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files
"""
import csv
import sys

import twk_core as core

path = sys.argv[1]
warm = int(sys.argv[2]) if len(sys.argv) > 2 else 300

rows = list(csv.DictReader(open(path, encoding='ascii')))
f = lambda k: [float(r[k]) for r in rows]
o, h, l, c, v = f('open'), f('high'), f('low'), f('close'), f('tick_volume')
s = core.compute_series(o, h, l, c, v)


def num(x):
    return None if x == '' else float(x)


tol = 10 ** -(len(rows[0]['close'].split('.')[-1]) if '.' in rows[0]['close'] else 0)
checks = {'purple': 'st', 'sl': 'sl', 'tp': 'tp', 'bv1': 'bv', 'sv1': 'sv', 'adx': 'adx'}
bad = {k: [] for k in list(checks) + ['signal', 'dir']}
for i in range(warm, len(rows)):
    r = rows[i]
    for col, key in checks.items():
        a, b = num(r[col]), s[key][i]
        t = 1e-3 if col == 'adx' else (0.5 if col in ('bv1', 'sv1') else tol)
        if (a is None) != (b is None) or (a is not None and abs(a - b) > t):
            bad[col].append((r['time'], a, b))
    if int(r['long']) != s['long'][i] or int(r['short']) != s['short'][i]:
        bad['signal'].append((r['time'], r['long'], r['short'], s['long'][i], s['short'][i]))
    if int(r['dir']) != s['dir'][i]:
        bad['dir'].append((r['time'], r['dir'], s['dir'][i]))

n = len(rows) - warm
print(f'{path}\ncompared {n} bars ({rows[warm]["time"]} .. {rows[-1]["time"]}), price tol={tol}')
for k, lst in bad.items():
    print(f'  {k:7s} mismatches: {len(lst)}')
    for x in lst[:5]:
        print('     ', x)
sig = sum(1 for i in range(warm, len(rows)) if s['long'][i] or s['short'][i])
print(f'signals in window: {sig}')
sys.exit(1 if any(bad.values()) else 0)
