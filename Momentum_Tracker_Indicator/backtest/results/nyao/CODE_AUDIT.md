# Nyao Scalper v43: what the source actually does (Step 3 and Step 14 of the brief)

Read from `nyao_scalper.mq5` (5,867 lines, BSD-3-Clause, github.com/elrizwiraswara/nyao_scalper_mt5) and the five
`settings/*.set` profiles. The README was not used for any of this.

## Entry

| Item | What the code does |
|---|---|
| Evaluation moment | Once per new bar, on its first tick (`EnableNewBarEntryOnly`). The "current candle" in the blend is therefore a one-tick candle (open = high = low = close). |
| Indicators | EMA 5 and EMA 12 (close), RSI 8, ATR 8, all on the chart timeframe. No higher timeframe, no volume, no VWAP, no ADX. |
| Trend score (max 3) | +1.5 if EMA5 > EMA12 (buy) and +1.5 if EMA5 is above its value 3 bars earlier. |
| Momentum score (max 3) | +1.0 if RSI in (50, 80), +0.5 if RSI > 60, +1.5 if the candle body is larger than the 10-bar average body; the sum is multiplied by 1 + impulse, where impulse = (0.5 x body / avg body + 0.3 x range / avg range + 0.2 x consecutive same-colour candles / 3) / 2, capped at 1. |
| Chop score (max 2) | ATR / 10-bar average ATR: > 1.0 gives 2, > 0.8 gives 1, else 0. |
| Volatility bonus (max 1) | +1 if ATR ratio > 1.2. |
| Peak bonus (max 1) | +1 if the close is above the highest high of candles 1-5 (buy). |
| Wick penalty | minus (upper wick / max(body, 1.5 x avg body)) for a buy. |
| Dead-market gate | Score forced to 0 if ATR ratio < 0.6. |
| Smoothing | Final = 0.6 x (2 x score of candle 1 + score of candle 2) / 3 + 0.4 x score of the forming candle. |
| Threshold | 4.5 (default), 6.0 (safe), 3.5 (aggressive); +1.0 per consecutive bar that already opened a trade in that direction (max +3); +2.0 while equity is 3% or more below its peak; minus 1.5 per losing open position in the same direction. Buy and sell are scored separately and the higher one is taken. |
| Other entry conditions | 1 trade per candle; no opposite trade on the same candle; hard block when 2 losing same-direction positions are open; 3-bar cooldown after 3 consecutive losses; new same-direction entry must be 750 points ($7.50) away from the last one while one is open; no entry if spread > 0.25 x ATR; max 8 open positions; no entry if 2 positions are losing; news filter (MT5 calendar, 30 min each side); 30 min before the weekly close. |
| Session restriction | Off by default (`EnableTradingHours=false`). |

## Exit

| Item | What the code does |
|---|---|
| Initial stop | 1% of account equity, converted to points for the lot (`SLInputType=INPUT_PERCENT`, `SLValue=1.0`): $10 = 1,000 points at 0.01 lot on a $1,000 account, $2 = 200 points on a $200 account. The stop depends on the account size, not on the market. |
| Take profit | Off by default. The optional R:R mode uses 1.5 x ATR stop and 1.5R target. |
| Trailing stop | Dollar distance `TrailingDistanceValue=0.20` per position (= 20 points at 0.01 lot), plus or minus 0.2 x (current score minus entry score), floored at $0.02. Only once open profit is at least $0.75. The stop is also floored at a break-even lock = entry + spread + $0.50, so the first valid trailing stop appears when the trade is about 82-101 points in profit and sits 0-20 points below the price. |
| Break-even on spread | After 2 grace bars, once profit exceeds 1.5 x the spread cost (about $0.50), the stop moves to the entry price. |
| Partial close | 25% / 50% / 100% when the score drops to 75% / 50% / 25% of the entry score. At 0.01 lot this never fires: 25% of 0.01 rounds up to the minimum lot and would leave nothing, so the code skips it. It only acts on the 0.03-0.05 dynamic lots. |
| Health close | Every tick after the grace period a health score is computed from EMA alignment and separation (40%), RSI zone (25%), adverse excursion in ATR (25%) and a 20-bar swing break (10%). Below 0.5 the stop is tightened to 2 x ATR x health ratio; below 0.4 the position is closed at market and a re-entry in the same direction is attempted immediately if the score is still 75% of the entry score. |
| Profit-offset stop | After 3 consecutive wins closed while a position is losing, its stop is tightened by the accumulated profit. |
| Basket stop | Closes every non-chain position when the floating loss of non-chain positions exceeds 8% of equity, then pauses 5 minutes. Active hedge-chain legs are excluded. |
| Equity pause | Trading pauses (5 min, x1.5 each time, max 120) when equity falls 30% below the last peak; the peak is then reset to the balance. |
| Stop of the EA | Equity below $20: close everything and stop. |

## Risk

| Item | What the code does |
|---|---|
| Lot | 0.01 base; +0.01 per 5% equity drop from peak (max +0.02) when the entry score is 8 or more, capped 0.05. Lots are increased in drawdown. |
| Hedge chain (default ON) | When a position is 1.5 ATR under water and the opposite score is at least 4.5, its stop is removed and an opposite position is opened, sized so that a 1 ATR move recovers 100% of the loss: lot = older lot + loss / (100 x ATR), at least older + 0.01, at most 0.10. The hedge has no stop. If the hedge itself loses and the older leg recovers to zero, the older leg is closed and a bigger reverse hedge is opened (up to 2 levels); at the level cap half of the deepest hedge is closed and a new cycle starts from the rest (up to 3 cycles); then the chain is released to normal management with no stop. `HedgeMaxChainLossUSD` and `HedgeMaxChainLossPct` default to 0 = no cap. The basket stop excludes chain legs. So an active chain has no loss limit of any kind other than the $20 account floor. |
| Maximum positions | 8 (12 aggressive, 3 safe). |
| Daily loss protection | None. The protections are peak-equity based. |
| Martingale / grid / averaging | The hedge chain is a rolling martingale (the author labels it "MARTINGALE - high risk" in the input comment). Dynamic lots add size in drawdown. There is no grid and no same-direction averaging. |

## Dangerous mechanisms (explicit flags)

1. **Hedge chain with no loss cap**: naked legs, root stop cleared, excluded from the basket stop, loss caps off by default, lots up to 10x the base.
2. **Lot size increases in drawdown** (dynamic lots).
3. **Stop distance set by account size**: a $200 account trades with a $2 stop on an instrument whose 1-minute range in 2026 is $2-8; a growing account widens its own stop.
4. **A $0.20 trailing stop on a $2,000-4,500 instrument**: the trailing distance equals one or two ticks of gold. Its behaviour cannot be seen on bar data (see the calibration section of the report).
5. **Immediate re-entry after a health close** in the same direction at the same price.

## Look-ahead / repainting audit (Step 14)

| Check | Result | Why |
|---|---|---|
| Future candle access | PASS | All buffers are read from index 0 (forming) and 1+ (closed); no negative shifts, no future bars. |
| Future high/low usage | PASS | The peak bonus uses candles 1-5, the swing check uses candles 2-19, all in the past. |
| Repainting | PASS with a quirk | Signals are computed once per bar at its first tick, so they do not change afterwards. The quirk: the 40% weight given to "the current candle" is applied to a one-tick candle, so at the decision moment that term carries only the trend and ATR components and never the body, impulse, peak or wick components the author designed it for. |
| Data leakage | PASS | No external data except the MT5 calendar for the news filter. |
| Signal timing | PASS | Entry at the open of the bar after the closed candles it scores. |
| Intrabar assumptions | FAIL under bar-based testing | The $0.20 trailing stop, the break-even lock at +$0.82-1.01 and the per-tick health close all act inside a single M1 bar. A backtest in "1 minute OHLC" or "Open prices only" modelling sees the bar extreme before the retrace and reports the optimistic bound. Only "Every tick based on real ticks" (or a tick replay, as done here) shows the real exits. |
| Unrealistic execution | FAIL | Positions are opened at market with `deviation=10` and closed at market by the health logic; the code assumes the trailing stop is honoured 20 points below the running maximum. With a 32-51 point spread and a 1-3 point tick on gold, that is not an assumption a broker fill will honour. |
| Reproducibility | PASS | The port in `nyao_engine.py` reproduces every decision rule above; the news filter is the only rule not reproduced (no calendar data). |

## Not reproducible here

* The MT5 economic-calendar news filter (the Strategy Tester has no calendar either; a proxy that blocks 15:15-16:00 server time is tested instead).
* Broker-specific `SYMBOL_TRADE_STOPS_LEVEL` and freeze levels (XM GOLD has 0; assumed 0).
* Commission (XM GOLD has none on the standard account; assumed 0).
