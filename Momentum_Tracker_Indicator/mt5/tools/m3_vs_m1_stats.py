"""Compare Tracker behaviour on M1 vs M3 signal timeframes using MT5-exported M1 bars.

M3 bars are rebuilt from the M1 bars of the diagnostics CSV (XM builds its M3 bars from M1,
aligned to the day start, and 86400 is a multiple of 180, so floor(time/180) matches).
The 1m row on an M3 bar = the 1m up/down sums of the M1 bar closing with it (Pine lower-TF
request.security semantics); the 3m row = the M3 bar itself.

usage: python m3_vs_m1_stats.py <TWK_diag_<SYM>_M1.csv> [ratio] [warmup_bars]
"""
import csv
import statistics as st
import sys
from datetime import datetime

import twk_core as core

path = sys.argv[1]
ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
warm = int(sys.argv[3]) if len(sys.argv) > 3 else 300

rows = list(csv.DictReader(open(path)))
t = [int(datetime.strptime(r['time'], '%Y.%m.%d %H:%M').timestamp()) for r in rows]
o, h, l, c, v = ([float(r[k]) for r in rows] for k in ('open', 'high', 'low', 'close', 'tick_volume'))
b1, s1 = core.up_down_volume(o, c, v, 20)

# M3 aggregation
m3 = {}
for i in range(len(rows)):
    k = t[i] // 180 * 180
    a = m3.setdefault(k, [k, o[i], h[i], l[i], c[i], 0.0, i])
    a[2] = max(a[2], h[i]); a[3] = min(a[3], l[i]); a[4] = c[i]; a[5] += v[i]; a[6] = i   # a[6] = last M1 index
bars3 = [m3[k] for k in sorted(m3)]
# keep only complete 3m bars (3 M1 bars) so a missing minute does not distort the test
cnt = {}
for x in t:
    cnt[x // 180 * 180] = cnt.get(x // 180 * 180, 0) + 1
bars3 = [b for b in bars3 if cnt[b[0]] == 3]


def stats(name, O, H, L, C, V, row1):
    s = core.compute_series(O, H, L, C, V)
    n = len(C)
    sig = [i for i in range(warm, n) if s['long'][i] or s['short'][i]]
    risks = sorted(s['risk'][i] * 100 for i in sig if s['risk'][i] and s['risk'][i] > 0)
    passed = 0
    for i in sig:
        L_ = s['long'][i]
        bv, sv = row1(i, s)
        b3, s3 = (s['bv'][i], s['sv'][i]) if name == 'M3' else m3row(i)
        if None in (bv, sv, b3, s3) or s['adx'][i] is None or s['tp'][i] is None:
            continue
        own, opp = (bv, sv) if L_ else (sv, bv)
        ok = (opp == 0 and own > 0) or (opp > 0 and own / opp >= ratio)
        m1 = bv > sv if L_ else sv > bv
        m3ok = b3 > s3 if L_ else s3 > b3
        if ok and m1 and m3ok and s['adx'][i] > 20:
            passed += 1
    hours = (n - warm) * (1 if name == 'M1' else 3) / 60
    print(f'  {name}: {n - warm} bars ({hours:.0f} h) | signals {len(sig)} ({len(sig) / hours:.1f}/h) | pass all filters @ratio {ratio}: {passed} ({passed / hours * 24:.1f}/day)')
    print(f'      Tracker SL distance (points): p10 {risks[len(risks) // 10]:.0f} | median {st.median(risks):.0f} | p90 {risks[9 * len(risks) // 10]:.0f}')
    return st.median(risks)


# 3m row for M1 signal bars: last complete M3 bar closing at or before the M1 bar's close
O3, H3, L3, C3, V3 = ([b[k] for b in bars3] for k in range(1, 6))
b3s, s3s = core.up_down_volume(O3, C3, V3, 20)
close3 = [b[0] + 180 for b in bars3]


def m3row(i):
    close_t = t[i] + 60
    lo, hi, ans = 0, len(bars3) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if close3[mid] <= close_t:
            ans, lo = mid, mid + 1
        else:
            hi = mid - 1
    return (b3s[ans], s3s[ans]) if ans >= 0 else (None, None)


print(path)
med1 = stats('M1', o, h, l, c, v, lambda i, s: (s['bv'][i], s['sv'][i]))
med3 = stats('M3', O3, H3, L3, C3, V3, lambda i, s: (b1[bars3[i][6]], s1[bars3[i][6]]))
print(f'  median stop M3/M1 = {med3 / med1:.2f}x')
