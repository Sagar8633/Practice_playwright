# Phase 2: Pine vs MT5 validation

Date: 2026-09-24. Chart: OANDA:XAUUSD 1m, account `sagar96jadhav12`, TWK Tracker v2.0 (default inputs).

## Deliverables

| File | Purpose |
|---|---|
| `TWK_Core.mqh` | Exact MQL5 port: RMA, ATR, `ta.supertrend`, pivots, up/down volume, `ta.dmi`, signal/SL/TP, completed-HTF alignment, `CTwkEngine` snapshot |
| `TWK_Tracker_MT5.mq5` | Diagnostic indicator (closed bars only): purple line, LONG/SHORT arrows, Data Window values, CSV export. **Compiles with 0 errors, 0 warnings.** |
| `tools/twk_core.py` | Line-for-line Python mirror of `TWK_Core.mqh` |
| `tools/compare_tv.py` | Leg 1: Pine (live TV values) vs the Python port on TV bars |
| `tools/compare_mt5.py` | Leg 2: MQL5 CSV vs the Python port on MT5 bars |

The two legs together prove **Pine == MQL5 on identical bars**, without needing a paid TradingView export.

## Leg 1 result: Pine == port ✅

TV values were read straight from the chart's TWK Tracker study through TradingView's JS chart model (`dataSources()` → study `data()` rows + `graphics()._primitivesCollection`).

| Check | Result |
|---|---|
| Smart Trail (purple), 188 bars after warm-up | max abs error **6.0e-7** (float noise), 0 bars > 1e-6 |
| LONG / SHORT flags | **0 mismatches** (18 signals) |
| Pivot high/low dots | **0 mismatches** |
| Current box (SHORT, bar 06:28 UTC) | TV entry 4281.71 / SL 4286.725 / TP 4271.68 = port **exactly** |
| Your screenshot LONG | SL **4280.697**, reproduced (bar 05:46 UTC) |
| Spec example LONG | entry **4282.670**, SL **4280.175**, TP **4287.660**, reproduced (bar 06:01 UTC) |
| 3m table row | TV 17.69K / 16.07K = port 17,687 / 16,070 |
| 1m table row | TV 4.51K / 6.07K = port 4,507 / 6,071 (captured in the same instant) |

Observations:
- The port converges to TV after about **117 bars** from a cold start. The EA uses 2000 bars.
- The live table **includes the forming bar**. The EA uses bar[1] (closed), which equals Pine's value on that bar once it closes.
- Pivot tie rule: all three tie modes gave identical results because this sample contained no equal highs/lows. The default `TWK_TIE_LEFT_EQUAL_OK` stays **unverified until a tie occurs** in a later sample.

### Full filter outcome on the 18 signals (03:46 to 06:28 UTC)

Rules: 1m volume ratio ≥ 1.5, M1 box, M3 box (completed 3m bars only), ADX > 20, and a valid Pine box.

| UTC | Side | Vol ratio | M1 | M3 | ADX | Result |
|---|---|---|---|---|---|---|
| 03:46 | LONG | 0.41 | n | n | 19.2 | |
| 03:52 | SHORT | 1.97 | Y | Y | 18.8 | ADX fails |
| 03:56 | LONG | 1.40 | Y | n | 17.1 | |
| 04:02 | SHORT | 1.25 | Y | Y | 13.1 | |
| 04:15 | LONG | 0.91 | n | n | 11.4 | |
| 04:24 | SHORT | 0.78 | n | n | 21.6 | |
| 04:31 | LONG | 1.54 | Y | n | 22.4 | M3 fails |
| 04:42 | SHORT | 0.99 | n | n | 26.2 | |
| **04:47** | **LONG** | **1.52** | **Y** | **Y** | **21.9** | **TRADE** |
| 05:06 | SHORT | 0.70 | n | n | 38.5 | |
| 05:20 | LONG | 0.99 | n | n | 29.0 | |
| **05:31** | **SHORT** | **1.60** | **Y** | **Y** | **20.2** | **TRADE** |
| 05:46 | LONG | 0.67 | n | n | 23.7 | |
| 05:54 | SHORT | 1.31 | Y | Y | 20.4 | |
| 06:01 | LONG | 1.03 | Y | n | 21.4 | |
| 06:15 | SHORT | 1.39 | Y | Y | 14.8 | |
| 06:18 | LONG | 1.04 | Y | n | 13.8 | |
| 06:28 | SHORT | 1.30 | Y | n | 10.7 | |

**2 of 18 signals pass all filters.** This is one small sample and says nothing yet about profitability.

## Leg 2 result: MQL5 == port ✅ (2026-09-24, XM demo 169426800)

The EA exported `TWK_diag_GOLD_M1.csv` and `TWK_diag_BTCUSD_M1.csv` on start. `compare_mt5.py` (300 warm-up rows skipped):

| Symbol | Bars compared | purple | dir | signal | SL | TP | bv1/sv1 | ADX |
|---|---|---|---|---|---|---|---|---|
| GOLD M1 | 2700 (09-22 11:35 → 09-24 10:36) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BTCUSD M1 | 2700 (09-22 13:37 → 09-24 10:36) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

With Leg 1, this gives **Pine == Python == MQL5** on identical bars.

## Leg 2: how to re-run

1. In MT5 (XMGlobal-MT5 20), open an **XAUUSD M1** chart. Attach **Indicators → TWK → TWK_Tracker_MT5**.
2. The Experts log prints `[DIAG] exported N closed bars to Common\Files\TWK_diag_XAUUSD_M1.csv`.
   Use the symbol name your broker shows, e.g. `XAUUSD` or `GOLD`.
3. Run:
   ```
   python tools/compare_mt5.py "%APPDATA%/MetaQuotes/Terminal/Common/Files/TWK_diag_XAUUSD_M1.csv"
   ```
   Expect `0 mismatches` on every line.

## Known, accepted differences (live broker vs TradingView)

- XM's XAUUSD prices and tick volume are a **different feed** from OANDA. On the same minute, the purple line, flip timing and volume totals will differ slightly between the TV chart and MT5. That difference comes from the data, not the code.
