# XAU Liquidity Map + Sweeps (Pine v6)

One overlay indicator for OANDA:XAUUSD that answers two questions live on the chart:

1. **Where is liquidity still pending?** Dashed lines mark every unswept pool:
   - `SH` / `SL` confirmed swing highs and lows (buy-side / sell-side liquidity)
   - `EQH x2` / `EQL x3` equal highs / lows clustered within a USD (or ATR) tolerance, drawn at the extreme, thicker
   - `PDH PDL PWH PWL` previous calendar day / week high and low (New York day, not the feed's 17:00 daily bar)
   - `ASIA-H/L`, `LON-H/L`, `NY-H/L` previous session high and low, each session in its own timezone
2. **Who just took it?** The bar that resolves a pool prints one of two events:
   - **SWEPT** (triangle + shaded box from the level to the wick extreme). Price pushed beyond the
     level by at least `Min penetration`, then closed back inside within the `Reclaim window`.
     BSL swept = buyers' stops were run above, bearish raid. SSL swept = bullish raid.
   - **BREAK** (grey x). Price closed beyond the level `Closes beyond = break` times, acceptance not a raid.

The top-right table shows the count of pending pools above and below, the nearest one on each side
with its distance in USD from the last price, `TESTING NOW` when the live bar is inside a pool,
and the last sweep with its age in bars.

## Files
- `XAU_Liquidity_Sweeps.pine` the indicator (497 lines, compiles clean on Pine v6)
- It is saved in BOTH TradingView accounts (patilkareena208 and sagar96jadhav12) as **Sagar_Liquidity**
  (script id `USER;0e3b205587aa455785ad9b277ffeb7c0`). Open Pine Editor > Open > that name > Add to chart.
  To use it on the patilkareena208 account paste the file into a new indicator there.

## Non-repainting rules
- A swing needs `Swing confirmation` closed bars after it, so it appears late but never disappears.
- Every state change runs on confirmed bars only. The live bar can only show `TESTING NOW`.
- Every tolerance is in USD per ounce. OANDA gold ticks at 0.001, MT5 at 0.01, so never use ticks.

## Defaults and tuning (XAUUSD)
| Timeframe | Swing L/R | EQ tol | Min pen | Buffer | Window |
|-----------|-----------|--------|---------|--------|--------|
| 1m        | 10 / 10   | 0.30   | 0.10    | 0.03   | 3      |
| 5m (default) | 10 / 10 | 0.50  | 0.20    | 0.05   | 3      |
| 15m       | 10 / 10   | 1.00   | 0.40    | 0.10   | 3      |
| 1h        | 8 / 8     | 2.00   | 0.80    | 0.20   | 2      |

Or set `Tolerance mode = ATR` and the EQ clustering scales itself. Too many sweeps: raise `Min penetration`.
Sweeps printing on real breakouts: lower `Closes beyond = break` to 1.

## Alerts
Five `alertcondition`s plus a dynamic `alert()` message are built in. TradingView Basic plan allows
zero indicator alerts (confirmed 18 Sep 2026), so they only work on Essential or above.
