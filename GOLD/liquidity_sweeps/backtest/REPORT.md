# XAU Liquidity Map + Sweeps: which timeframe gives quality trades?

Date: 26 Sep 2026. Data: Dukascopy XAUUSD M1 bid, XM server time, Sep 2020 to 25 Sep 2026 (every month 24k-32k bars, no gaps).
Costs: XM spread model by year and hour (about 0.51 USD in 2026) plus 0.10 USD slippage per trade.

## Short answer

**No timeframe produces "clear and sure-shot" trades from this indicator on its own.** Over the last 12 months
(25 Sep 2025 to 25 Sep 2026) the sweep-reversal trade loses money net of costs on 1m, 3m, 5m, 15m, 30m, 1h and 4h.
It is positive on 1d, but on only 27 trades, and it was negative on 1d in the year before. Before costs the sweep has
no directional information at all: the gross win rate at 1:1 is 47-49% on every timeframe, and price reaches 1R
against the trade more often than 1R in its favour.

The indicator is still a correct map of where liquidity sits and when it is taken. What the data says is that
"liquidity taken" is not, by itself, a reason to enter.

## What was tested

1. The Pine logic was replicated in Python (`liq_engine.py`) bar for bar: pivots 10/10, equal highs/lows merged at
   the extreme within 0.15 ATR, previous day/week high/low on the New York day, Asia and London session highs/lows
   (on 30m and below), min penetration 0.10 ATR, reclaim buffer 0.03 ATR, 3-bar window, 2 closes = break.
2. Every SWEEP was traded as a reversal: long after a sell-side sweep, short after a buy-side sweep, entry at the
   close of the reclaim bar, stop beyond the wick plus 0.10 ATR, target 1R / 1.5R / 2R / 3R, exit on the M1 path,
   time exit after 10-60 bars depending on the timeframe.
3. Two years were run first: TEST = the last 12 months, CONTROL = the 12 months before. Filters were screened on
   CONTROL and confirmed on TEST. Anything that survived was then run on four more untouched years (2020-2024).
4. 159,904 simulated trades in the two-year runs, plus about 45,000 more in the hold-out runs.

## Result 1: sweep reversal, all sweeps, last 12 months (net R per trade)

| TF  | trades | 1R     | 1.5R   | 2R     | 3R     | gross at 2R | cost (share of risk) |
|-----|--------|--------|--------|--------|--------|-------------|----------------------|
| 1m  | 10,071 | -0.353 | -0.327 | -0.311 | -0.295 | +0.037      | 0.348 |
| 3m  | 3,946  | -0.189 | -0.168 | -0.155 | -0.144 | +0.022      | 0.177 |
| 5m  | 2,587  | -0.125 | -0.120 | -0.122 | -0.087 | +0.005      | 0.127 |
| 15m | 1,247  | -0.141 | -0.119 | -0.132 | -0.151 | -0.064      | 0.067 |
| 30m | 890    | -0.138 | -0.147 | -0.158 | -0.168 | -0.108      | 0.050 |
| 1h  | 337    | -0.107 | -0.163 | -0.164 | -0.202 | -0.131      | 0.034 |
| 4h  | 207    | -0.002 | -0.051 | -0.039 | +0.030 | -0.021      | 0.018 |
| 1d  | 27     | +0.054 | +0.184 | +0.275 | +0.374 | +0.283      | 0.008 |

The year before (CONTROL) is worse on every row: 1m -0.72, 5m -0.31, 15m -0.19, 1h -0.26, 4h -0.22, 1d -0.24 at 2R.
On 15m, 30m and 1h the six-year picture is the same: every single year negative, average -0.10 to -0.23R.

Reading the table: on 1m the spread alone eats 35% of a typical stop, so 1m can never work. 3m and 5m are a coin
flip before costs and a loser after. 15m to 1h lose even before costs. 4h is flat. 1d is too few trades to mean
anything and did not repeat.

## Result 2: does a sweep predict direction? (gross, 1R:1R)

| TF | sweeps | gross win rate | reached +1R first | reached -1R first |
|----|--------|----------------|-------------------|-------------------|
| 1m | 20,750 | 48.8% | 51.5% | 50.8% |
| 5m | 5,419  | 48.2% | 47.9% | 50.6% |
| 15m | 2,586 | 46.8% | 44.0% | 51.4% |
| 1h | 716    | 47.6% | 42.3% | 50.3% |
| 4h | 446    | 46.6% | 40.1% | 46.6% |
| 1d | 57     | 47.4% | 40.4% | 49.1% |

A coin flip everywhere. On the higher timeframes the reversal is slightly less likely than continuation.

## Result 3: quality filters (pool type, session, depth, speed, trend)

Screened on CONTROL, confirmed on TEST, then checked on 2020-2024:

- Pool type: previous-day and previous-week sweeps are the WORST reversal trades (PDH -0.20 to -0.56R, PDL -0.16 to
  -0.32R). Equal highs/lows, session highs/lows and swings are all negative. Nothing positive in both years.
- Session: New York afternoon sweeps looked good in the last year (15m/30m/1h, +0.10 to +0.47R with the 4h trend)
  and passed the CONTROL check. On the four earlier years the same rule is negative in 3 of 4 years
  (30m: -0.13, -0.10, +0.01, -0.04). It was a fit to the last year.
- Depth, same-bar reclaim, level age, stop width, direction: none positive in both years.
- Limit entry on the retest of the level: worse than market entry on every timeframe (the fills are biased toward
  the trades that keep going against you).
- Longer swings (20/20, 30/30): fewer trades, same sign.
- 5m/15m sweeps that coincide with a pending 1h or 4h pool (11-23% of sweeps): still negative.

## Result 4: the break (acceptance) traded as continuation

The one thing that was positive in both recent years with hundreds of trades: when price closes THROUGH a pool and
holds, trade the continuation on 1h or 4h in the direction of the 4h trend (4h at 3R: +0.27R CONTROL, +0.42R TEST,
155-161 trades, profit factor 1.6-1.8). Split by side it is almost all LONG breaks (4h long +0.37 to +0.55R,
shorts flat or negative), which is what a gold bull market looks like. On the untouched years 2020-2024 the same
rule is negative in 3 of 4 years (4h all: -0.09, -0.09, -0.09, +0.15R; 1h: -0.02, -0.09, -0.23, -0.01R).
It is the trend of the last three years, not an edge of the pattern.

## What "quality not quantity" means here

Fewer trades did not make better trades. Every filter that reduced the count also reduced the sample to the point
where a good-looking number was noise, and every one of them failed when checked on years it had not seen.
The honest ranking of timeframes for this setup is:

1. 4h and 1d: the map is cleanest and costs are negligible, but there is no directional edge to trade and 1d gives
   about 2 trades a month.
2. 1h and 15m: negative before costs. Do not trade sweeps here.
3. 5m and 3m: zero before costs, negative after. Do not trade.
4. 1m: cannot work at XM spreads.

## How to use the indicator anyway

- As context only: know where the stops are (equal highs/lows, PDH/PDL, session extremes) and when they were taken.
- Combine it with an independent reason to trade (your own read of order flow, a news schedule, a manual log of
  what you actually see at the moment of the sweep). The earlier TWK and SMA18 studies reached the same conclusion:
  bar data alone has not produced a net-positive rule on gold for this account's costs.
- If you want to test a discretionary version, keep a log of the sweeps you WOULD take with the reason, for
  50-100 events, and run them through `liq_engine.simulate`. That is the only dataset that has not been tested.

## Files

- `liq_engine.py` replica + simulator, `run_multitf.py` two-year grid, `quality_lab.py` filters and HTF trend,
  `lab2.py` retest / swing length / breaks / HTF confluence, `holdout.py` and `holdout2.py` the 2020-2024 checks.
- `results/summary_tf_rr.csv`, `results/quality_combos.csv`, `results/lab2_results.csv`,
  `results/holdout_2020_2024.csv`, `results/holdout2_breaks_2020_2024.csv`, `results/trades_with_context.csv`
  (every simulated trade with session, pool type, depth and 1h/4h trend), logs in `results/*.log`.
