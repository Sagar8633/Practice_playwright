# SimpleSMA18Bot v1.00 — component map (from reading `Vaibhav/SimpleSMA18Bot.mq5`, 1,767 lines)

The file is byte-identical to `bot/SimpleSMA18Bot.mq5`. The MT5 terminal also holds v11 (FollowMode / MaxLossMode), v12 and v13 (Chandelier from tick one, MaxLoss cap, MinStopPoints, pending expiry, ATR/R-scaled levels, account guards). Those are *not* the EA under study; v13 is only used to reproduce the D1 tester claim.

## Inputs that matter (defaults)

| Group | Input | Default | Effect |
|---|---|---|---|
| Timeframe | `TimeFrame` | D1 | signal timeframe; magic number = 12345*100 + TF code |
| Size | `LotSize` | 0.01 | **fixed lot, no risk-% sizing** |
| Entry | `FastMAPeriod` / `TrendMAPeriod` | 18 / 200 | SMA(close) on the signal TF |
| Entry | `VolumeMAPeriod` | 20 | volume[1] > SMA20(volume) over bars 1..20 (tick volume on MT5) |
| Entry | `SwingStrength` / search | 2 / 100 bars | last confirmed swing low/high, shifts 3..100, fallback low[1]/high[1] |
| Entry | `EntryBufferPoints` | 10 | buy stop at high[1] + $0.10; sell stop at low[1] - $0.10 |
| Break-even | `EnableBreakEven`, trigger, offset | on, 500, 10 | at +$5.00 floating (bid vs fill) SL -> fill + $0.10 |
| Protection | `ProtectionMode` | SWING (1) | NONE / SWING / CHANDELIER / TRAILING |
| Protection | `ProtectionStartMode`, `ProtectionStartPoints` | after points, 500 | protection updates only while floating profit >= $5.00 |
| Swing | `SwingBufferPoints` | 50 | SL = swing low - $0.50 (tighten only) |
| Chandelier | lookback / ATR / mult | 22 / 22 / 3.0 | SL = highest high(1..22) - 3 x ATR(22) |
| Trailing | start / distance / step | 1000 / 500 / 50 | from +$10: SL = bid - $5.00, moved in >= $0.50 steps |
| Risk filter | `UseRiskFilter`, `MaximumLossPoints` | off, 300 | market close when adverse move >= $3.00 |
| SL % filter | `UseSLPercentFilter`, `MaximumSLPercent` | **on, 1.0** | block the setup if the swing-stop loss at LotSize > 1% of balance |
| Session | `UseSessionFilter` ... | off | server-hour windows Sydney 22-07, Tokyo 0-9, London 8-17, NY 13-22 |
| ADX | `UseADXFilter`, period, min, rising, consecutive | off, 14, 25, off, off | iADX (MT5 EMA version) on bar 1 |
| Failed breakout | `UseFailedBreakoutExit` ... | off | **dead code: `ManageFailedBreakoutExit()` is never called** |
| Partial close | `EnablePartialClose` ... | off | **dead code: inputs are never read** |

## Tick flow (OnTick)

```mermaid
flowchart TD
    T[OnTick] --> U[UpdateTradeState]
    U --> M{position?}
    M -- yes --> RF[Risk filter: adverse >= MaximumLossPoints -> market close]
    RF --> X{close[1] crossed MA18[1]?}
    X -- yes --> CL[Market close: MA18 exit]
    X -- no --> BE[Break-even: floating >= 500 pts -> SL = fill +/- 10 pts]
    BE --> PA{floating >= ProtectionStartPoints?}
    PA -- yes --> PR[Protection: SWING / CHANDELIER / TRAILING, tighten only]
    PA -- no --> NB
    PR --> NB
    CL --> NB
    M -- no --> NB{new signal bar?}
    NB -- no --> END[return]
    NB -- yes --> P{pending order?}
    P -- yes --> PS[Ratchet pending SL to newest swing] --> PI{close[1] crossed MA18[1]?}
    PI -- yes --> CANCEL[Cancel pending] --> END
    PI -- no --> END
    P -- no --> HO{position open?}
    HO -- yes --> END
    HO -- no --> SF[Session filter] --> AF[ADX filter] --> SIG{Buy / Sell signal?}
    SIG -- buy --> BS[Buy stop @ high[1]+10 pts, SL = swing low, SL% filter, must be above ASK]
    SIG -- sell --> SS[Sell stop @ low[1]-10 pts, SL = swing high, SL% filter, must be below BID]
    SIG -- none --> END
```

## Entry logic (evaluated once per new signal bar on completed bars 1 and 2)

Buy: MA18[1] > MA200[1] and MA18[2] > MA200[2]; close[1] > MA18[1] and close[2] > MA18[2]; close[1] > MA200[1] and close[2] > MA200[2]; volume[1] > SMA20(volume). Sell is the mirror.
Then a **stop order** at high[1] + buffer with SL at the last confirmed swing low. The order has no expiry: it is cancelled only when a completed bar closes below MA18, and its SL is ratcheted to each newer swing low. MT5 rejects a buy stop that is not above the ask, so on M1 (spread 40-50 pts vs 10-pt buffer) roughly 40% of setups fail with "invalid price" and are retried on the next bar.

## Exit logic (tick level)

1. Risk filter (off by default).
2. MA18 exit: on the first tick of a new bar, if the completed bar closed on the wrong side of MA18 -> market close.
3. Break-even at +500 pts to fill +10 pts (tighten only). **On D1 the daily range is $30-$100, so this triggers on the entry day in most trades and becomes the dominant exit (70 of 85 exits in 2020-2026).**
4. Protection, only while floating profit >= 500 pts: swing low - 50 pts (default), Chandelier, or fixed trailing. Swing protection can only tighten once a *new* swing forms above the break-even level, which on D1 takes many days.
5. Initial swing stop (hit in 1% of D1 trades, 11-17% on M1-M15).

## Dependencies that shape the results

* `LotSize` is fixed and the SL% filter compares the swing-stop loss at that lot with 1% of balance: on $200 any stop wider than $2.00 is blocked, i.e. every D1 setup and ~90% of M15 setups. The "1% risk" is a *gate*, not position sizing.
* Break-even, protection start and trailing thresholds are in points and do not scale with timeframe or volatility (500 pts is 5x the M1 ATR in 2021 and 0.1x the D1 ATR in 2026).
* Protection is tighten-only and cannot loosen, so the break-even stop set at +$0.10 is the floor for the rest of the trade.
* One pending order or one position at a time; no re-entry logic; no time exit; no TP.
* `PassSLPercentFilter` is called twice per order (harmless), `EntryBreakoutPrice`/`EntryIsBuy` are set but only used by the dead failed-breakout code.
