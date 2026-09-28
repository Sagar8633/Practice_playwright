# The strategy under test, exactly as ported

Source: `SimpleSMA18Bot_v1.00.mq5` (copy in this folder), the EA developed and tested on gold. `engine_in.py` is the gold research
engine (an exact rule port, validated against the MT5 tester in the gold study) with only the market model changed.

## Rules (unchanged)

Signal timeframe bars; decisions on the first tick after a bar completes, using the completed bar (shift 1) and the one before (shift 2).

Buy setup: SMA18 > SMA200 on bars 1 and 2; close > SMA18 on bars 1 and 2; close > SMA200 on bars 1 and 2; volume[1] > SMA20(volume).
Sell setup: the mirror. One pending order or one position at a time.

Entry: buy stop at high[1] + EntryBufferPoints, sell stop at low[1] - EntryBufferPoints. Initial stop at the last confirmed swing low / high
(strength 2, searched over the last 100 bars, fallback low[1] / high[1]). The pending order never expires; it is cancelled when a completed bar
closes through SMA18, and its stop is ratcheted to each newer swing. MT5 validity: a buy stop must sit above the ask, a sell stop below the bid.

Exits, tick level: (1) MA18 exit: at a new bar, if the completed bar closed on the wrong side of SMA18, close at market. (2) Break-even at
+BreakEvenTriggerPoints floating to fill +/- BreakEvenOffsetPoints (tighten only). (3) Protection while floating profit >= ProtectionStartPoints:
SWING (swing low - SwingBufferPoints), CHANDELIER (highest high(22) - 3 ATR(22)) or TRAILING (from TrailingStart, distance, step). (4) Initial stop.
No take profit, no time exit, no re-entry logic. The 1% stop-loss gate (UseSLPercentFilter) is an account rule, not a signal rule; it is off here
because results are reported per unit.

## What had to change for an Indian index, and how it is documented

| Item | Gold | Indian index | Why |
|---|---|---|---|
| Volume filter | tick volume from MT5 | **cannot be evaluated**: NSE index candles carry no volume; the filter is off in every run | data limitation, stated in every report |
| "Point" | $0.01 | 0.05 (NSE index tick) | MT5 semantics: a point is the minimum price increment |
| Session | 01:00-23:59 server time, 5 days | 09:15-15:29 IST, holidays and special sessions as traded | market hours |
| Signal bars | UTC-anchored | anchored at the 09:15 open (1h bars: 09:15, 10:15 ... 15:15 stub) | Indian charting convention |
| Costs | XM spread model, slippage, swap | futures spread and slippage per side at every fill; STT, exchange, SEBI, stamp, brokerage and GST per round trip (costs.py); no swap | futures carry no overnight financing |
| Money unit | USD per 0.01 lot | index points per unit; rupees = points x lot size (NIFTY 75, BANKNIFTY 35) | lot-size revisions only rescale |

## The two configurations run everywhere

| Input | AS-IS (v1.00 defaults, ticks) | FINAL_H4 (gold study selection, ATR-scaled) |
|---|---|---|
| SMA fast / trend / volume MA | 18 / 200 / (20, off) | 18 / 200 / (20, off) |
| Swing strength / search | 2 / 100 | 2 / 100 |
| Entry buffer | 10 ticks = 0.5 index pt | 0 |
| Break-even trigger / offset | 500 ticks = 25 pts / 10 ticks = 0.5 pt | 2.00 ATR(22) / 10 hundredths = 0.10 ATR |
| Protection | SWING from +25 pts, swing buffer 50 ticks = 2.5 pts | TRAILING from +5.00 ATR, distance 0.50 ATR, step 0.10 ATR, active immediately |
| MA18 exit | on | on |
| Initial stop | swing | swing |

Interpretation of AS-IS on an index: the break-even trigger of 25 index points is 0.1% of NIFTY (about 0.05% of BANKNIFTY), so on intraday
timeframes most trades are moved to break-even within their first bars, as the gold D1 study also found for the 500-point trigger. That is
the strategy as written; the ATR-scaled configuration removes the scale problem and is reported alongside, never instead.
