# Loss pattern analysis: Nyao Scalper on XAUUSD (Steps 10-13 and 18 of the brief)

Built on the fixed-stop research runs (`nyao_lab2.py`: the EA's logic with a fixed $10 stop per 0.01 lot, no ruin stop,
no drawdown pause, tick-calibrated trailing) so that all 60 months are covered. The shipped configuration stops itself at
$20 equity within 6-10 months of any start, which leaves too few trades per regime to read. Trade-level tables with every
breakdown are in `TABLES.md`; the tagged trade files are `trades/fixed_M5_nohedge_tagged.csv` and
`trades/fixed_M1_nohedge_tagged.csv`.

## 1. The shape of the loss

Fixed-stop M5, hedge off, 28,754 trades over five years, net -$10,601, gross before spread +$801, spread paid $11,402.

| Exit reason | Trades | Mean P&L | Total | Share of all losses |
|---|---:|---:|---:|---:|
| Trailing exit inside the bar (TRAIL) | 16,390 | +0.98 | +16,092 | |
| Trailed stop hit on a later bar (SL_trail) | 5,269 | +1.23 | +6,487 | |
| Gap through the stop, mostly the trailed one (SL_gap) | 655 | +1.40 | +918 | |
| Break-even stop at entry (SL_be) | 434 | -0.01 | -4 | |
| Health-decay close at market (HEALTH) | 4,590 | -4.37 | -20,047 | 59% |
| Initial $10 stop (SL) | 1,385 | -10.00 | -13,852 | 40% |
| Health-tightened stop (SL_tight) | 31 | -6.26 | -194 | 1% |

79% of trades win about $1 and 21% lose $5-10. Break-even at that payoff needs an 84% win rate. Winners are cut after a
median 3 minutes at the activation level of the trailing stop (entry + spread + $0.50); losers are held a median 21 minutes
until the health score decays or the $10 stop is hit. The loss is diffuse, not a tail: the ten largest losses are 0.4% of
the total, the longest losing streak is 7 (M5) and 9 (M1). The "cooldown after three losses" and the drawdown gate therefore
rarely trigger and change nothing.

On M1 the same picture with more trades: 41,816 trades, net -$19,665, gross -$1,444, spread $18,221; 7,952 of 9,994 losers
are health closes; median hold 6 minutes for losers, 2 for winners.

With the hedge chain on (M5): 30% of the losers are hedge legs and they carry $77,448 of the $107,719 gross loss. The median
loser doubles from -$4.88 to -$10.00: a chain converts a $5 health-close loss into a covered pair whose recovery leg is closed
at the recovery floor and whose root is closed at its full loss. The chain's own mechanics with every other exit switched
off (`fixed_M5_hedge_onlychain`) lose $94,341 on 28 closed trades, because nothing in the chain has a cap.

## 2. Where the losses happen (Step 10)

Fixed-stop M5, hedge off, expectancy per trade in USD at 0.01 lot:

| Regime | Trades | Exp/trade | Win rate | Note |
|---|---:|---:|---:|---|
| DEV 2021-09..2023 / VAL 2024 / OOS 2025-26 | 7,680 / 4,366 / 16,708 | -0.30 / -0.33 / -0.41 | 74% / 76% / 82% | trade count doubles in 2025-26 as gold's ranges grow; win rate rises, loss per trade rises faster |
| 2021 / 2022 / 2023 / 2024 / 2025 / 2026 | 943 / 3,864 / 2,873 / 4,366 / 8,833 / 7,875 | -0.29 / -0.30 / -0.29 / -0.33 / -0.30 / -0.54 | | 2026 is the worst year: spread 51 points, 7,875 trades in nine months |
| Asia 00-09 / London 10-14 / NY overlap 15-18 / NY late 19-23 (server) | 9,614 / 6,193 / 9,342 / 3,605 | -0.37 / -0.40 / -0.30 / -0.49 | 79 / 77 / 81 / 76% | no session is positive in any period (session x period table in TABLES.md; best cell London VAL -0.14, worst NY late OOS -0.51) |
| with the H1 EMA50 slope / against it | 15,022 / 13,732 | -0.37 / -0.37 | 79 / 79% | the higher-timeframe trend carries no information for this entry |
| volatility low / normal / high (ATR vs 30-day median) | 2,483 / 8,047 / 18,224 | -0.50 / -0.38 / -0.35 | 79 / 78 / 79% | quiet markets are worst (spread is a larger share of the range); the dead-market gate at 0.6 does not remove them |
| BUY / SELL | 13,856 / 14,898 | -0.34 / -0.40 | 79 / 79% | |
| signal entries / virtual-SL re-entries | 28,384 / 370 | -0.37 / -0.56 | 79 / 65% | the re-entry after a health close is the worst entry type |
| entry hour, worst / best | 01:00 -0.70, 20:00 -0.60, 13:00 -0.54 / 05:00 -0.12, 04:00 -0.19, 06:00 -0.21 | | | every hour negative |

Major news periods: the calendar filter is not reproducible; blocking 15:15-16:00 server (the 8:30 New York releases) left
the expectancy unchanged (-0.41 vs -0.43 on M5). The 15:00 hour is in fact one of the least bad (-0.29) because the trailing
stop activates more often in a fast market.

## 3. Repeated conditions that create losses (Step 12)

Checked on the loser population against the winner population. A condition counts as a pattern only if it separates the two.

| Candidate | Losers | Winners | Pattern? |
|---|---:|---:|---|
| entered against the H1 trend | 48.3% | 47.6% | no |
| high-volatility regime | 62.3% | 63.7% | no |
| NY overlap session | 29.3% | 33.3% | no |
| was at least 0.5R in profit first (reversal after a good start) | 0.4% | | no: losers never get near +$5 |
| median hold | 21 min | 3 min | yes, by construction: winners are cut at +$1, losers are held |
| exit reason | health close 76%, initial stop 23% | trailing exits 99% | yes, by construction |
| late entry (score confirmed after the move) | see the visual test | | yes |
| spread expansion | 2026 (51 points) is the worst year at -0.54 per trade | | yes: cost, not signal |
| overtrading / consecutive entries | 25-70 entries per day; the $7.50 duplicate rule and the 1-per-candle rule are the only spacing | | yes |
| false breakout, range market, low momentum, stop hunting, weak confirmation, poor RR | | | not separable from the rest: the payoff ratio (1:5) is fixed by the exit design, so every entry type loses the same way |

The one pattern that explains the loss is not a market condition at all. It is the exit design: a $0.20 trail that books
+$0.9 on the 79% of trades that move 82-101 points in the right direction first, against a $5-10 loss on the rest. No
pre-entry variable in the set (higher-timeframe trend, ATR regime, session, hour, side, score level, candle strength via the
score's own body and impulse terms) changes the 79/21 split enough to matter.

## 4. Entry quality: what was known before the losing trades (Step 13)

* Higher-timeframe trend (H1 EMA50 slope): identical loser share with and against. Not a filter.
* ATR regime: losers are slightly less frequent in high volatility, but expectancy is negative in every regime. The dead-market
  gate (ATR ratio < 0.6) is already in the EA and removes almost nothing.
* Session and hour: all negative; the best hour (05:00, -0.12) is still below zero. A session filter cannot turn this positive.
* Score level: on BASELINE's trades the Nyao score is inversely related to outcome (the 5.5-6.5 bucket is the worst, -1.39 per
  trade at 0.02 lot); in the entry-only runs threshold 6 raises gross expectancy from -0.04 to +0.19 per trade but still not
  above the spread. A higher threshold buys fewer, not better, trades.
* Distance from support/resistance, VWAP, volume profile, market structure: not part of the EA; your PD Volume Zones and
  discovery-ledger work already tested these on the same data with zero result, so they were not re-run here.
* Minimum reward-to-risk: the EA has none (TP off). With its own R:R mode (1.5 ATR stop, 1.5R target) the win rate is 35-36%
  against a 40% break-even. Not a fix.

Conclusion: no information available before the trade separates the losers. The trades lose because of what happens after
entry (the exit design) and because of what is paid at entry (spread on a 50-second trade).

## 5. Visual chart test (Step 18)

Charts in `charts/`: `week_2022-10-10_M5.png` (DEV), `week_2024-05-13_M5.png` (VAL), `week_2026-01-05_M5.png` (OOS),
`day_2026-01-07_M1.png`. Each shows the M1 closes with Nyao entries (triangles), exits (crosses), green for wins and red for
losses, and BASELINE on the same price below.

What the charts show, consistently across the three periods:

* Entries are late by construction. Every score component (EMA above EMA, EMA rising, RSI above 60, body larger than average,
  three same-colour candles, close above the last five highs) measures a move that has already happened, so the triangles sit
  at the end of each impulse, not its start. In the 5-9 Jan 2026 week the buys cluster on the way into the 4,500 top of
  7 Jan and the sells into the 4,413 low of 8 Jan.
* Winners are tiny and immediate: a green segment is one to three candles long and ends at the activation level. Losers are
  the trades placed at the last impulse before a turn; they are held through the reversal until the health score decays.
* The strategy chases price and overtrades: 199 trades in the OOS week (BASELINE: 26), 64 on 7 Jan 2026 alone (BASELINE: 7).
  Entries in ranges are as frequent as in trends because the score has no range detector; the ATR ratio term only measures
  whether the last 8 bars are bigger than the last 10.
* Neither system reads the structure: BASELINE's 26 trades in the same week net -$39 at 0.02 lot; its stop sits at a pivot and
  its trades last hours, so it loses more per trade and far less per day.

## 6. Loss patterns of the shipped configuration (for completeness)

In the shipped default the stop is 1% of equity, so as the account falls the stop tightens: at $500 it is $5 (half an M1
range in 2026), at $200 it is $2. On the $200 account the win rate falls to 28-30% and the average win equals the average
loss (about $1.07): the trailing stop can no longer activate before the stop is hit. The hedge chain then adds naked legs of
up to 0.10 lot. Largest single losses in the shipped runs: -$138 (M1) and -$393 (M5) on a $1,000 account; the continuous
runs are ruined by March-July 2022.
