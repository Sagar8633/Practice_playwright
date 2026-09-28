# SimpleSMA18Bot_H4 final configuration: windows for a manual tester check

Engine run (Dukascopy prices in XM server time, XM spread by hour, 10-point slippage, XM swap, fixed 0.01 lot, no 1% gate, deposit irrelevant). Each window starts flat on its first day, with indicators warmed on the bars before it, which is how the MT5 tester behaves. Money per 0.01 lot (1 oz).

| Window | Trades | Net $ | Gross win / loss $ | PF | Win % | Max DD $ | Longs / shorts net $ | Exits |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Last 12 months, 26 Sep 2025 to 25 Sep 2026 | 51 | +1,758.58 | +2,981 / -1,223 | 2.44 | 51.0 | 304.26 | +1,087 / +671 | 26 MA18, 13 trailing, 6 break-even, 5 initial stop, 1 open at end |
| Calendar 2025 | 52 | +678.75 | +1,506 / -827 | 1.82 | 42.3 | 271.43 | +947 / -268 | 26 MA18, 14 trailing, 8 break-even, 4 initial stop |
| Last month, 26 Aug to 25 Sep 2026 | 3 | -67.77 | +10 / -78 | 0.13 | 33.3 | 78.23 | -78 / +10 | 2 MA18, 1 open at end |

Last 12 months by month (net $): 2025-09 -1 · 2025-10 +2 · 2025-11 +6 · 2025-12 +252 · 2026-01 +770 · 2026-02 +58 · 2026-03 +431 · 2026-04 +16 · 2026-05 +56 · 2026-06 +400 · 2026-07 -304 · 2026-08 +139 · 2026-09 -68.

Trade lists (order time, fill time, exit time, side, entry, initial stop, exit, exit reason, P&L, swap, best unrealized profit, cumulative): `H4_final_last12m_trades.csv`, `H4_final_2025_trades.csv`, `H4_final_lastmonth_trades.csv`, `H4_final_sep2026_trades.csv` in this folder.

## Last month, all trades

| Order placed | Filled | Closed | Side | Entry | Initial SL | Exit | Exit reason | P&L $ | Best profit $ |
|---|---|---|---|---:|---:|---:|---|---:|---:|
| 2026-09-03 12:00 | 2026-09-03 14:57 | 2026-09-04 16:00 | BUY | 4443.56 | 4282.04 | 4393.26 | MA18 close exit | -51.17 | 67.08 |
| 2026-09-10 01:00 | 2026-09-10 06:00 | 2026-09-10 12:00 | BUY | 4421.52 | 4374.46 | 4394.46 | MA18 close exit | -27.06 | 13.59 |
| 2026-09-23 16:00 | 2026-09-23 16:42 | open at data end (25 Sep 16:37) | SELL | 4294.36 | 4370.96 | 4284.69 | still open | +10.46 | 49.93 |

## How to reproduce in the MT5 Strategy Tester

- Expert: `SimpleSMA18Bot_H4.ex5` (defaults already set: H4, trailing protection started immediately, ATR-scaled levels 2.0 / 5.0 / 0.5 / 0.1, EntryBufferPoints 0, ADX and session filters off).
- Symbol GOLD, period H4, model "Every tick based on real ticks" (or "Every tick"), dates as in the table, leverage 1:1000.
- Deposit: use at least $20,000 or set `UseSLPercentFilter = false`, otherwise the 1% gate blocks most trades (with the gate on, a $3,000 deposit took 6 of the 51 trades in the last 12 months and a $200 deposit took none). The strategy figures above are the gate-off view at 0.01 lot.
- Expect the same trade dates and directions; fills and exits a few cents apart; small P&L differences from the spread (XM's live spread vs the hourly model), from slippage (the engine charges 10 points on every execution, the tester charges none unless you set a delay), and from swap rounding. A trade that the engine shows as the last one may still be open in the tester at the end date.
- If a trade is missing in the tester, the usual cause is a buy stop placed inside the spread ("invalid price" in the journal) or a pending order the tester filled on a different tick; compare the order-placed time first, then the fill.
