"""Merge the per-slice trade CSVs of a sliced (multi-core) Strategy Tester optimization.

Each optimization pass with TesterSliceDays > 0 writes
  %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\TWK_trades_<SYMBOL>_<MAGIC>_tester_sNN.csv
This joins them in time order and prints the same statistics as the EA's report.

usage: python merge_tester_slices.py <SYMBOL> [deposit=10000] [magic=26092401]
"""
import csv
import glob
import os
import sys

symbol = sys.argv[1]
deposit = float(sys.argv[2]) if len(sys.argv) > 2 else 10000.0
magic = sys.argv[3] if len(sys.argv) > 3 else '26092401'
folder = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal', 'Common', 'Files')
files = sorted(glob.glob(os.path.join(folder, f'TWK_trades_{symbol}_{magic}_tester_s*.csv')))
if not files:
    sys.exit(f'No slice files TWK_trades_{symbol}_{magic}_tester_sNN.csv in {folder}')

trades = []
for f in files:
    with open(f, newline='') as fh:
        for r in csv.DictReader(fh):
            r['slice'] = os.path.basename(f)[-6:-4]
            trades.append(r)
trades.sort(key=lambda r: r['open_time'])

out = os.path.join(folder, f'TWK_trades_{symbol}_{magic}_tester_MERGED.csv')
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(trades[0].keys()) if trades else ['slice'])
    w.writeheader()
    w.writerows(trades)

pnl = [float(r['pnl']) for r in trades]
wins = [p for p in pnl if p > 0.005]
losses = [p for p in pnl if p < -0.005]
gp, gl = sum(wins), sum(losses)
equity = peak = deposit
max_dd = max_dd_pct = 0.0
cw = cl = max_cw = max_cl = 0
for p in pnl:
    equity += p
    peak = max(peak, equity)
    max_dd = max(max_dd, peak - equity)
    max_dd_pct = max(max_dd_pct, (peak - equity) / peak * 100 if peak > 0 else 0)
    if p > 0.005:
        cw, cl = cw + 1, 0
    elif p < -0.005:
        cl, cw = cl + 1, 0
    max_cw, max_cl = max(max_cw, cw), max(max_cl, cl)
rr = [float(r['initial_rr']) for r in trades if r.get('initial_rr')]
risk = [float(r['initial_risk']) for r in trades if r.get('initial_risk')]
reasons = {}
for r in trades:
    reasons[r['exit_reason']] = reasons.get(r['exit_reason'], 0) + 1
n = len(trades)

print(f'{len(files)} slices merged -> {out}')
if n:
    print(f'Period       {trades[0]["open_time"]} .. {trades[-1]["close_time"]}')
print(f'Trades       {n} | BUY {sum(r["side"] == "BUY" for r in trades)} | SELL {sum(r["side"] == "SELL" for r in trades)}')
print(f'Win/Loss/BE  {len(wins)} / {len(losses)} / {n - len(wins) - len(losses)} | win rate {100 * len(wins) / n if n else 0:.1f}%')
print(f'Net profit   {sum(pnl):.2f} | gross profit {gp:.2f} | gross loss {gl:.2f} | profit factor {gp / -gl if gl < 0 else float("nan"):.2f}')
print(f'Average      trade {sum(pnl) / n if n else 0:.2f} | winner {gp / len(wins) if wins else 0:.2f} | loser {gl / len(losses) if losses else 0:.2f}')
print(f'Drawdown     max {max_dd:.2f} ({max_dd_pct:.2f}% of peak, closed-trade equity from deposit {deposit:.0f})')
print(f'Streaks      max consecutive wins {max_cw} | losses {max_cl}')
if rr:
    print(f'Risk/reward  avg initial risk {sum(risk) / len(risk):.2f} | avg initial R:R {sum(rr) / len(rr):.2f}')
print('Exit reasons ' + ' | '.join(f'{k}={v}' for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
print('Note: slices start flat, so a trade that spans a slice boundary can overlap one opened by the next slice;')
print('      totals can differ slightly from one continuous backtest.')
