# Momentum Tracker EA: Phase 1 Pine Script Analysis

Date: 2026-09-24
Status: **Phase 1 complete. Waiting for confirmation before Phase 2.**

## 0. Sources analysed

| File | Role | Used by EA? |
|---|---|---|
| `TWK_Tracker.pine` ("trade_with_kareena Tracker", short title **TWK Tracker**) | Overlay: MTF volume table, R-Factor, Smart Trail (purple line), LONG/SHORT labels, pivot dots, 1:2 position box | **Yes. This is the source of truth.** |
| `TWK_Flow.pine` ("TWK Flow") | Bottom pane: Momentum Flow oscillator + **ADX** | ADX only |
| `TWK_Strategy.pine` | Strategy Tester version of the same entry/SL/TP rule | Cross-check only |
| `Momentum_Tracker.pine` | Older version (close-in-range volume split) | **No.** Superseded |

The TradingView-deployed Tracker (`.playwright-mcp/tv_final_sagar96.json`) was diffed against the local file.
With comments and tooltips removed, **the logic is identical**.

---

## 1. Pine Script architecture (TWK Tracker)

```
OHLCV (chart TF)
 ├─ f_tf(tf) × 9 TFs ─ request.security ─► bV, sV, score ─► table rows 1m…1D
 ├─ R-Factor (RSI, vol ratio, NIFTY RS, vol ROC, MFI) ─► table rows 10-15  (display only)
 ├─ ta.supertrend(1.5, 10) ─► stVal (PURPLE LINE), stDir
 │      └─ stDir flip ─► longSig / shortSig  (LONG / SHORT labels + alerts)
 ├─ ta.pivotlow/high(5,5) ─► lastPL / lastPH (purple DOTS; also the SL source)
 ├─ volume ≥ 1.8×SMA20 ─► footprint bubbles (display only)
 └─ on signal: entry=close, sl=pivot or stVal, tp=entry±2·risk ─► red/green position BOX
```

Default inputs that affect the EA: `stMult=1.5`, `stATR=10`, `pivLen=5`, `rr=2.0`, `volLen=20`, `sigConfirm=false`.

---

## 2. LONG logic

```pine
[stVal, stDir] = ta.supertrend(1.5, 10)
bullFlip = stDir < 0 and stDir[1] >= 0          // direction -1 = uptrend
longSig  = bullFlip and (not sigConfirm or rFactor > 0)   // sigConfirm=false by default
```

**LONG = the bar where the Supertrend(1.5, 10) flips from down to up.**
R-Factor is not part of the signal by default.
The signal is a one-bar event, so "NEW LONG" is naturally distinct from "SAME LONG".

## 3. SHORT logic

```pine
bearFlip = stDir > 0 and stDir[1] <= 0
shortSig = bearFlip and (not sigConfirm or rFactor < 0)
```

**SHORT = the bar where the Supertrend flips from up to down.**

### Exact `ta.supertrend` algorithm (TradingView reference implementation)

```
src = hl2 ; atr = RMA(TrueRange, 10)          // ta.atr = ta.rma(ta.tr(true), len)
upper = src + 1.5*atr ; lower = src - 1.5*atr
lower = (lower > prevLower or close[1] < prevLower) ? lower : prevLower
upper = (upper < prevUpper or close[1] > prevUpper) ? upper : prevUpper
if na(atr[1])                dir = 1
else if prevST == prevUpper  dir = close > upper ? -1 : 1
else                         dir = close < lower ? 1 : -1
stVal = dir == -1 ? lower : upper
```

RMA seed: the first value is the SMA of the first `len` values, then `rma = (prev*(len-1) + x)/len`.
This is fully deterministic, so MQL5 can reproduce it exactly **from identical OHLC data**.

---

## 4. Initial SL calculation

```pine
lastPL = most recent confirmed ta.pivotlow(low, 5, 5)
lastPH = most recent confirmed ta.pivothigh(high, 5, 5)
LONG : sl = (lastPL exists and lastPL < close) ? lastPL : stVal
SHORT: sl = (lastPH exists and lastPH > close) ? lastPH : stVal
risk = LONG ? close - sl : sl - close
if risk > 0 → position box drawn;  else → NO box (the LONG/SHORT label is still drawn)
```

- The SL is the **last confirmed swing low/high**, falling back to the purple line.
- A pivot is confirmed 5 bars **after** the swing bar, so `lastPL` holds only information already available. There is no look-ahead.
- **EA rule:** if Pine's `risk <= 0`, there is no box and so **no trade**. A LONG label alone is not enough.

## 5. TP calculation

```pine
tp = LONG ? entry + 2.0*risk : entry - 2.0*risk      // entry = close of signal bar
```

The TP is anchored to the **signal-bar close**, not the actual fill.
Recommendation: capture the Pine TP price exactly, and re-validate its side against the actual fill.

## 6. Purple line calculation

**Purple line = `stVal` (Supertrend 1.5 × ATR10 on hl2), colour #7e57c2.**

- In an uptrend it is the lower band, which only ratchets **up**. In a downtrend it is the upper band, which only ratchets **down**.
- ⚠ The **purple dots** (#9c27b0) are the pivot highs/lows, not the purple line. They are drawn with `offset=-5`, so each dot appears on the swing bar but only once 5 bars have passed.
- ⚠ When the Supertrend flips against an open trade, `stVal` jumps to the **other side of price**. For a BUY after a bearish flip, purple sits above Bid and cannot be used as a stop. The EA must treat that as "purple not usable" and keep the existing SL.

## 7. Buying volume calculation

```pine
bV = request.security(sym, tf, math.sum(close > open ? volume : 0, 20))
```

**Buying volume = the sum of `volume` over the last 20 bars of that TF where close > open (up bars).**

## 8. Selling volume calculation

```pine
sV = request.security(sym, tf, math.sum(close < open ? volume : 0, 20))
```

**Selling volume = the sum of `volume` over the last 20 down bars (close < open).**
Doji bars (close == open) count in neither total.
`score = (bV − sV) / max(bV + sV, 1)` → "Positive (BUY)" if > 0, "Negative (SELL)" if < 0.

⚠ This is **not** the close-in-range split used in the older `Momentum_Tracker.pine`.

⚠ `volume` on OANDA:XAUUSD is **tick volume** (the count of price updates).
MT5 `tick_volume` is therefore the conceptually correct equivalent, not a substitute.
However, a different broker feed produces **different numbers** (see §16).

## 9. M1 Box calculation, and 10. M3 Box calculation

**❗ There is no "M1 Box" or "M3 Box" in the Pine Script.**

The only `box` objects are the drawn reward/risk rectangles of the current position.
The spec requires M1 and M3 Box to be mandatory filters, so I will **not** invent them (spec §9).
Two plausible readings need your decision:

| Option | Meaning | M1 Box VALID for BUY when… | M3 Box VALID for BUY when… |
|---|---|---|---|
| **A: Table row** | The coloured 1m / 3m rows of the table | 1m row = Positive (BUY), i.e. `bV1 > sV1` | 3m row = Positive (BUY), i.e. `bV3 > sV3` |
| **B: Position box** | The red/green R:R box the Tracker draws | M1 Tracker drew a valid LONG box (risk > 0) | Tracker **on the M3 chart** is currently in a LONG box / uptrend (`stDir3 = -1`) |

Note on Option A: if the volume filter also uses the 1m row, the "M1 Box" check is already implied by `bV1 ≥ 1.5×sV1`.
That overlap is why the choice matters.

## 11. ADX integration

ADX is **not in the Tracker**. It comes from `TWK Flow`:

```pine
[diP, diM, adxVal] = ta.dmi(14, 14)     // chart timeframe
```

`ta.dmi` uses Wilder RMA for TR, +DM and −DM, and RMA smoothing for DX.
Pine's display threshold is 25; the EA spec uses **ADX > 20** (strict).

- ⚠ MT5 `iADX` uses a **different smoothing** and will not match Pine.
- `iADXWilder` is close but seeds differently. The EA will compute Wilder DMI in code (exact Pine formula) and use `iADXWilder` only as a cross-check.
- The value is read on the **closed** M1 bar.

## 12. MTF dependencies

| Value | TF | Pine call | Needed by EA |
|---|---|---|---|
| Signal, purple, pivots, SL, TP | chart TF (M1) | native | ✅ |
| Buying/selling volume | 1m (and 3m if Option A) | `request.security(..., gaps_off, lookahead_off)` | ✅ |
| ADX | chart TF (M1) | native (TWK Flow) | ✅ |
| 5m…1D rows, R-Factor, NIFTY benchmark, bubbles | various | | ❌ display only, not reproduced |

The spec says to use the configured timeframe (`SignalTimeframe=M1`) and not depend on the chart timeframe.
The EA reads M1/M3 series explicitly with `CopyRates`.

## 13. Repainting behaviour

| Component | Repaints? | Detail |
|---|---|---|
| LONG/SHORT flip | **Intrabar only** | Computed from the live `close`, so the label can appear and disappear during the bar. It is final at bar close. |
| Purple line (live bar) | Intrabar only | `hl2` and ATR move during the bar. The closed-bar value is final. |
| Pivot dots / `lastPL`, `lastPH` | No (lagged) | Confirmed 5 bars later. The dot is back-drawn with `offset=-5`, which looks predictive on history but is not. |
| SL / TP | Intrabar only | Derived from `close` and `stVal` of the signal bar |
| 1m volume row on M1 chart | Intrabar only | Same TF as the chart |
| **3m (and higher) rows** | **Yes: history ≠ realtime** | With `lookahead_off`, **historical** M1 bars show the last *completed* 3m bar. **Realtime** bars show the *developing* 3m bar. |

**Closed-candle mode removes all intrabar repaint.**
For the M3 values the EA will use **only completed M3 bars**. That matches Pine's *historical* output exactly and never uses future data.

## 14. Signal confirmation timing

Pine has no `barstate.isconfirmed` gating: signals are live and intrabar.

Recommended EA default (`TradeOnClosedCandle=true`):
1. On the first tick of a new M1 bar, evaluate bar `[1]` (just closed).
2. If `longSig[1]` or `shortSig[1]` fires, run the filters and enter at market.
3. Record the signal-bar open time. Each signal bar can trigger at most one entry (OneTradePerSignal), and this persists in a GlobalVariable across restarts.

The fill is approximately the next bar's open, which is close to the Pine `entry = close[1]`.

---

## 15. Pine → MQL5 mapping

| # | Pine component | Meaning | MT5 equivalent | Validation method |
|---|---|---|---|---|
| 1 | `longSig` = `stDir<0 and stDir[1]>=0` | Supertrend flip up | `TWK_Core::Supertrend()` on M1 closed bars, flip test on `[1]` vs `[2]` | Compare flip bar times vs TV export |
| 2 | `shortSig` | Supertrend flip down | same | same |
| 3 | `sl` (pivot or stVal) | Last confirmed pivot low/high, else purple | `TWK_Core::PivotLow/High(5,5)` tracking `lastPL/lastPH` + fallback | Compare SL price per signal |
| 4 | `tp = entry ± 2·risk` | 1:2 target from signal close | same formula, `entry = close[1]` | Compare TP price per signal |
| 5 | `stVal` | Purple line | Supertrend value, closed bar `[1]` | Compare per bar |
| 6 | `bV` (tf=1) | Σ up-bar volume, 20 bars | Σ `tick_volume` where close>open, M1 | Compare per bar (same feed only) |
| 7 | `sV` (tf=1) | Σ down-bar volume, 20 bars | Σ `tick_volume` where close<open, M1 | same |
| 8 | "M1 Box" | **Not in Pine: needs your definition** | Option A or B | TBD |
| 9 | "M3 Box" | **Not in Pine: needs your definition** | Option A or B on completed M3 bars | TBD |
| 10 | `ta.dmi(14,14)` ADX (TWK Flow) | Trend strength | Custom Wilder DMI (+ `iADXWilder` cross-check) | Compare per bar |

**No `iCustom` buffer indexes are guessed.** All values are calculated by one shared include (`TWK_Core.mqh`) that both the EA and a diagnostic indicator use.

---

## 16. What cannot be reproduced exactly

1. **Data feed.** TradingView OANDA:XAUUSD and your MT5 broker have different OHLC and **very different tick volume**.
   - The formulas can match 1:1, but live values (purple, SL, flip timing, volume totals) **will differ** between TV-on-OANDA and MT5-on-broker.
   - Exact validation needs identical input bars. Plan: export TV bars to CSV, import them into an MT5 **custom symbol**, run `TWK_Core` on it, then diff against the TV indicator values.
2. **Volume totals** will never match the TV table numerically on a live broker feed. Only the *logic* can match.
3. **Pivot tie-handling** (two equal lows inside the window) is undocumented in Pine. It will be verified empirically during Phase 2 validation.
4. **RMA warm-up.** Supertrend ATR and ADX are recursive, so the EA must load ≥ 500 bars of history for the values to converge.
5. **Realtime 3m row.** Pine's live developing-bar value cannot be reproduced without repaint. The EA uses completed M3 bars, which equals Pine's historical values.
6. **R-Factor Sector Strength** uses NSE:NIFTY, which is unavailable on MT5. It is not needed because it is not part of the signal.

---

## 17. Proposed MT5 architecture

```
Momentum_Tracker_Indicator/mt5/
  TWK_Core.mqh            pure calc: RMA, ATR, Supertrend, PivotLow/High, UpDownVolume, WilderADX
                          → struct TwkSnapshot {signal, stVal, stDir, sl, tp, risk, bV1, sV1,
                                                 bV3, sV3, m1Box, m3Box, adx, valid flags, reasons}
  TWK_Tracker_MT5.mq5     diagnostic indicator: plots purple line + LONG/SHORT arrows,
                          exports per-bar CSV for Pine-vs-MT5 diff (Phase 2)
  TWK_MomentumEA.mq5      EA shell: OnInit/OnTick/OnTradeTransaction, inputs, state machine
  TWK_Entry.mqh           signal lifecycle, filters (volume ratio, M1/M3 box, ADX, spread), SL/TP validation
  TWK_Exec.mqh            CTrade wrapper: retries, fill verification, stop/freeze levels, emergency policy
  TWK_Manage.mqh          Stage 0/1/2: purple trail, +5 lock, 1:1 trail, never-loosen, restart recovery
  TWK_Log.mqh             structured [MOMENTUM]/[VOLUME]/[ENTRY REJECTED]… logs + chart debug panel
  tools/compare_tv_mt5.py Phase 2: diff TV export vs MT5 export at identical timestamps
```

- State survives restarts from the actual position (entry, SL, magic) plus GlobalVariables (last signal time, stage).
- "Stage" is re-derived from the SL position relative to entry, so a protected trade can never reset to Stage 0.

---

## Worked example from the 2026-09-24 screenshot (XAUUSD M1)

The chart shows a **LONG** box with **SL 4280.697**.

1m row: Buy 4.44K vs Sell 5.62K (ratio 0.79); 3m row: Buy 6.67K vs Sell 13.38K.

Under the proposed filters, **this LONG would be rejected** (volume ratio < 1.5; the 1m/3m rows are Negative under Option A).

---

## Live-account verification (2026-09-24 12:04 IST)

- Account `sagar96jadhav12`, chart XAUUSD 1m (OANDA).
- "trade_with_kareena Tracker" v2.0 was pulled from pine-facade and is **byte-identical** to the earlier export, which is logic-identical to `TWK_Tracker.pine`.
- Inputs on the chart are the defaults: top_right, 20, 15, small, 14, NIFTY, 1.5, 10, 20, 1.8, 5, 2, 24.
- The only box-like elements on the chart are:
  - the red/green reward/risk position box;
  - the coloured **1m / 3m table rows**.
  Nothing else could be an "M1 Box" or "M3 Box", so **Option A (table rows) is the recommended reading.**
- Live example at 12:02 IST:
  - SHORT, entry 4281.710 (1:2), SL 4286.725.
  - 1m row: Buy 6.02K / Sell 6.31K → Negative (SELL). 3m row: Buy 18.78K / Sell 14.94K → Positive (BUY).
  - Under Option A this SHORT is **rejected**: the M3 box is BUY, and the volume ratio is 6.31 / 6.02 = 1.05, below 1.5.
- About 10 LONG/SHORT flips occurred between 10:00 and 12:00, so the filters will reject most signals. That is expected.

## Decisions confirmed (2026-09-24)

| Topic | Decision |
|---|---|
| M1 Box | 1m table row. BUY valid if `bV1 > sV1` (Positive); SELL valid if `sV1 > bV1` (Negative). |
| M3 Box | 3m table row, **completed M3 bars only**. BUY valid if `bV3 > sV3`; SELL valid if `sV3 > bV3`. |
| Volume filter | **1m row only**: BUY `bV1 ≥ 1.5·sV1`, SELL `sV1 ≥ 1.5·bV1`. |

## Decisions needed before Phase 2 (original list)

1. **M1 Box / M3 Box definition:** Option A (table rows) or Option B (M3 Tracker direction), or something else?
2. **Volume filter timeframe:** the 1m row only (`bV1 ≥ 1.5×sV1`), or both 1m and 3m?
3. **MT5 broker/symbol** for validation (so digits and stop levels are known). Can you export TV chart data (with a validation-plot copy of the Tracker) for the custom-symbol comparison?
