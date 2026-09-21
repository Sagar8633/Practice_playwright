# Realtime Momentum Tracker [Flow]

An **original** Pine Script (v6) indicator that reproduces the visible behaviour of a
multi-timeframe buying/selling **volume momentum** table plus a realtime **Momentum Flow**
oscillator.

> ⚠️ This is **not** a copy of any protected/invite-only script. TradingView never exposes
> the source code of protected indicators, so this is a clean-room implementation built from
> the publicly visible *behaviour* (the per-timeframe Buying/Selling Volume + BUY/SELL table).

## What it does

1. **Multi-timeframe momentum table** (1m, 3m, 5m, 15m, 30m, 1h, 4h, 1D)
   - Splits each timeframe's volume into **Buying Volume** vs **Selling Volume**
     using where the close sits inside the bar's range (intrabar pressure estimate).
   - Prints **Positive (BUY)** / **Negative (SELL)** per timeframe.
   - Optional *volume-strength* weighting amplifies timeframes where volume is
     bursting above its 20-period average.

2. **Momentum Flow oscillator** (own pane)
   - Aggregates all timeframe scores into one smoothed flow value.
   - Histogram + line, colored green/red; fades when momentum weakens.
   - Triangle markers + alerts on zero-line cross (BULLISH / BEARISH flips).

## How to install on TradingView

1. Open your chart → **Pine Editor** (bottom panel).
2. Delete the template, paste the contents of `Momentum_Tracker.pine`.
3. Click **Save**, then **Add to chart**.
4. Adjust inputs (table position, flow smoothing length, colors) via the gear icon.

## Why it's "high speed / realtime"

- All math is per-bar and recalculates on every realtime tick.
- `request.security(..., lookahead_off)` is used so higher-timeframe values update
  live without repainting future data.

## Tuning notes

- **Flow smoothing length** — lower = faster/twitchier, higher = smoother.
- **Use volume strength** — turn off for a pure directional read; on for burst emphasis.
- The buying/selling split is an *estimate* (TradingView free data has no true bid/ask
  tick volume). For tick-accurate splits you'd need a data feed with up/down tick volume.

## File

- `Momentum_Tracker.pine` — the indicator source.
