# GitHub scalping-bot research: the one reproducible strategy, tested on your XAUUSD data

Date: 26 September 2026. Data: XAUUSD M1, Dukascopy, 1 Sep 2021 to 25 Sep 2026 (60 months, 1,766,192 bars), XM server time,
XM spread by year (32-51 points), XM swap. BASELINE: your TWK MomentumEA M3 preset at 0.02 lot. Candidate: Nyao Scalper MT5
v43 (github.com/elrizwiraswara/nyao_scalper_mt5), ported rule for rule into `nyao_engine.py` and run at its own defaults.
Deliverables are listed at the end.

## Verdict

The github.com/topics/scalping-bot collection contains one genuine, inspectable gold EA. Reproduced on your data under
its own default profile it loses the whole account in every period tested, on every timeframe, with and without its hedge
chain, and the loss survives every parameter change tried. Its entry signal has zero gross expectancy before spread, like
your own TWK flip. Its published appeal rests on a $0.20 trailing stop whose behaviour bar-based backtests cannot see;
a replay on 575 hours of real ticks shows the trailing exits land at the activation level, which turns a bar-level profit of
+$0.43 per trade into a real -$0.37. Nothing in it improves BASELINE: gating your signals by the Nyao score makes them
worse, and the two systems trade almost disjoint sets of bars.

The full brief (24 steps) was applied to the one candidate that could be reproduced; the other 19 repositories fail at
Step 1-3 (no source, no strategy, or exchange-specific crypto logic) and are documented in the inventory.

## 1. Inventory and classification (Steps 1-2)

20 repositories were listed on the topic page on 26 Sep 2026. `results/nyao/STRATEGY_INVENTORY.csv` has every field the
brief asked for. Summary:

| Category | Count | Repositories | Why |
|---|---|---|---|
| A. Directly relevant | 1 | nyao_scalper_mt5 (MQL5, 179 stars, full source, XAUUSD M1/M5 target) | Only repo with a complete, compilable gold EA |
| B. Adaptable | 0 | | |
| C. Research-interesting | 2 | BotScalpingTwinRange (PSAR + Twin Range Filter, Binance), edison-smart-levels (Bybit S/R levels) | Indicator-filter and level logic of the kind your filter lab and PD Volume Zones bot already rejected; no backtester or exchange-specific data |
| D. Not relevant | 17 | 3 identical "Forex-Scalping-EA-MT5-MT1" clones + MT5-Risk-Management-EA (Windows Forms template farm, README badges point at torvalds/linux), NeuroScalper-AI and MultiVenueScalper (README-only), barbotine (code not in repo, paid site), 3 Hyperliquid bots, 2 Binance bots, Polymarket, KORStockScan (Korean equities), ArkoRisk (risk manager), Algo-Trader-Toolkit, QuantumTius (60-line stub that mixes MQL4 calls into .mq5 and cannot compile) | |

## 2. What Nyao actually does (Step 3)

Read from the 5,867-line source, not the README. Full detail with the dangerous-mechanism flags and the look-ahead audit is in
`results/nyao/CODE_AUDIT.md`. In short:

* Entry: a 0-10 score per direction from EMA 5/12 alignment and slope (3), RSI 8 zones and body momentum times an impulse
  factor (3), ATR 8 / 10-bar ATR ratio (2, plus 1 above 1.2), a 5-bar breakout (1), minus a wick penalty; scored on the two
  last closed candles (weights 2:1) and blended 60/40 with the forming candle. Evaluated once per bar at its first tick.
  Threshold 4.5, raised by consecutive entries and by drawdown, lowered by losing open positions. No higher timeframe,
  no session filter (off by default), spread gate at 0.25 x ATR, max 8 positions, 1 per candle, $7.50 duplicate distance.
* Stop: 1% of equity, converted to points at the position's lot: $10 = 1,000 points at 0.01 lot on $1,000, $2 on $200.
* Exit: a $0.20 trailing stop (20 points at 0.01 lot) that engages once open profit reaches $0.75 and is floored at
  entry + spread + $0.50; break-even at entry after about $0.50; a per-tick "health" score (EMA alignment, RSI, adverse ATR,
  swing break) that tightens the stop below 0.5 and closes at market below 0.4, then re-enters immediately if the score is
  still 75% of the entry score; partial closes on score decay (inert at 0.01 lot).
* Hedge chain, on by default: at 1.5 ATR under water with an opposite score of 4.5, the stop is removed and an opposite,
  larger, stop-less position is opened, sized to recover the loss within 1 ATR; rolls and reseeds up to 2 levels x 3 cycles;
  lot cap 0.10; the chain-loss caps default to 0 and the basket stop excludes chain legs.
* Lots increase in drawdown (0.01 to 0.05). Equity pause at -30% from peak; the EA stops itself at $20.

## 3. Test environment (Steps 4-7)

* Same M1 bid bars, spread, swap, timezone and execution rules for BASELINE and Nyao. Ask = bid + spread; buys fill at ask.
* Entries at the open of the signal bar; stops checked before targets inside a bar; gaps fill at the open; management at
  every M1 close (the EA manages every tick; M1 is the finest resolution the 5-year set has).
* Splits: DEV 2021-09..2023-12, VAL 2024, OOS 2025-01..2026-09-25, the same as your filter lab. Every Nyao config is run
  separately per period from the deposit, so a ruin in DEV does not empty VAL; the shipped configs are also run
  continuously over five years.
* Deposit $1,000 (the lab's notional account) and $200 (your account). Nyao's own sizing (0.01 base lot, 1% stop) is used
  because its stop is defined by the account; BASELINE keeps its fixed 0.02 lot as in every earlier report.
* Not reproduced: the MT5 calendar news filter (the Strategy Tester has no calendar either); a proxy that blocks
  15:15-16:00 server is tested instead.
* Port validation: the engine reproduces every rule listed in the audit; the trailing stop is validated on ticks (next
  section). All scripts and the EA source are in the repository (list at the end).

## 4. The trailing stop and the tick calibration (Steps 5 and 14, the key finding)

Nyao trails 20 points behind the bid on an instrument whose one-minute range was $0.50-1.00 in 2021 and $2-8 in 2026. A bar
cannot say whether gold retraced 20 points before it reached the bar's high. The engine therefore reports two bounds:
"path" (the extreme was reached first, exit at extreme minus 20 points) and "worst" (the first 20-point reversal came right
after the stop engaged, exit at the activation level). Then 4,991 trades that fall inside your existing Dukascopy tick sample
(2025, Thursdays and Fridays, server 14:00-19:59, 575 hours) were replayed tick by tick with the EA's per-tick trailing and
break-even rules.

| Reading | Mean P&L per trade (USD at 0.01 lot) | Win rate | Trailing exits only |
|---|---:|---:|---:|
| Bar engine, path bound | +0.43 | 79.9% | +2.00 |
| Tick replay | -0.37 | 75.3% | +0.95 |
| Activation level (pessimistic bound) | +0.89 | | +0.89 |

The tick exit sits at the activation level: median position between the bounds 0.00, mean 0.05 for same-bar trailing exits
and 0.085 for trailed stops hit later; 54% of exits are within 10% of the pessimistic bound and 68% within 5 points of the
activation price. Median time from entry to activation 43 s, median hold 50 s. On the whole sample the bar engine says
+$2,144 and the ticks say -$1,860. The pessimistic bound is essentially the truth for this stop, and the two measured
factors (0.05 and 0.085) are used for every "calibrated" run below. Chart: `results/nyao/charts/tick_calibration.png`.

What this means for the EA's own claims: an MT5 Strategy Tester run in "1 minute OHLC" or "Open prices only" modelling
generates the bar's high before its close and will show the path bound (profit factor 1.3-1.4 on this data). Only "Every
tick based on real ticks" shows the real exits. The author publishes no backtest and warns that tester results only mean
something when they mirror live conditions; on this stop, that warning is the whole story.

## 5. Results: the shipped profiles, tick-calibrated (Steps 8, 15)

Per period from $1,000, default profile. "Final" is the period-end balance; $20 is the EA's own stop-trading floor.

| Run | Trades | Win | PF | Exp/trade | DEV net / PF / final | VAL | OOS | Continuous 5y |
|---|---:|---:|---:|---:|---|---|---|---|
| M1, hedge on (as shipped) | 3,170 | 50% | 0.61 | -0.93 | -980 / 0.66 / 20 | -980 / 0.48 / 20 | -980 / 0.66 / 20 | ruin 9 Mar 2022 after 1,160 trades |
| M1, hedge off | 6,098 | 58% | 0.57 | -0.48 | -980 / 0.56 / 20 | -980 / 0.58 / 20 | -980 / 0.58 / 20 | ruin 13 Jul 2022 |
| M5, hedge on | 4,774 | 57% | 0.73 | -0.62 | -980 / 0.73 / 20 | -980 / 0.79 / 20 | -980 / 0.58 / 20 | ruin 9 Mar 2022 |
| M5, hedge off | 6,780 | 60% | 0.60 | -0.43 | -980 / 0.59 / 20 | -980 / 0.60 / 20 | -980 / 0.60 / 20 | ruin 6 Apr 2022 |
| M3, hedge on | 4,146 | 56% | 0.68 | -0.71 | -980 / 0.67 / 20 | -980 / 0.64 / 20 | -981 / 0.71 / 19 | ruin |
| M3, hedge off | 6,787 | 60% | 0.59 | -0.43 | -981 / 0.62 / 19 | -980 / 0.59 / 20 | -980 / 0.57 / 20 | ruin |
| safe profile M1 (hedge off, threshold 6, 0.5% stop) | 1,316 | 71% | 0.66 | -0.37 | -96 / 0.65 | -94 / 0.60 | -302 / 0.68 | -296, final 704, DD 30% |
| safe profile M5 | 1,584 | 75% | 0.75 | -0.25 | -108 / 0.73 | -73 / 0.75 | -217 / 0.76 | -295, final 705, DD 30% |
| balanced M1 / M5 | 5,289 / 6,288 | 57% | 0.70 / 0.69 | -0.53 / -0.47 | ruin | -859 / ruin | ruin | ruin |
| aggressive M1 / M5 (0.03 lot, threshold 3.5) | 853 / 1,213 | 44% / 41% | 0.57 / 0.61 | -3.54 / -2.43 | ruin | ruin | ruin | ruin within months |
| default M1 on $200 (stop = $2) | 1,197 | 28% | 0.41 | -0.45 | -180 / 0.47 | -180 / 0.40 | -180 / 0.33 | ruin |
| default M5 on $200 | 1,324 | 30% | 0.44 | -0.41 | -180 | -180 | -180 | ruin |

Gross before spread (sum of the three period runs): M1 hedge -$999, M1 no hedge -$186, M5 no hedge +$64, M3 no hedge
+$32; spread paid $1,941-3,004. The system is flat to slightly negative before costs and pays 2-3x its deposit in spread
per year of trading. Exit mix in the shipped M1 run until ruin: 350 trailing exits, 342 initial-stop hits, 141 trailed
stops hit later, 68 chain covers, 45 health closes; 71 chains started, 124 hedge legs, largest single loss $138.

The hedge chain does not rescue anything: with it on, PF is a little higher (0.61-0.73 vs 0.57-0.60) because covered chains
book paired exits, but the average loss doubles (-4.9 to -5.4 vs -2.8) and the largest losses reach -$393 on a $1,000 account.

Bounds, for the record (`results/nyao/nyao_runs.csv`): the path bound with hedge off is PF 1.27-1.42 and ends five years at
$19,009 (M5) or $49,657 (M1), almost all of it in 2025-26 when gold's M1 bars became large enough for "high minus 20
points" to be worth $2-10 per trade; the same bound with the hedge on still ruins (PF 0.91-0.94). The pessimistic bound
ruins everywhere (PF 0.63-0.75). Charts: `results/nyao/charts/equity_readings_M1.png`, `equity_readings_M5.png`.

## 6. Cost sensitivity (Step 9)

Default profile, hedge off, calibrated, M1 / M5. PF at normal cost 0.57 / 0.60.

| Scenario | M1 PF | M5 PF | Note |
|---|---:|---:|---|
| Spread x1.25 | 0.57 | 0.58 | |
| Spread x1.5 | 0.56 | 0.52 | |
| Spread x2.0 | 0.47 | 0.47 | the 0.25 x ATR spread gate blocks more entries, so DEV loses less in dollars but not per trade |
| Slippage 5 points on entries and stop exits | 0.49 | 0.51 | |
| Slippage 10 points | 0.42 | 0.45 | |
| Hedge on, spread x1.5 | 0.70 | | |
| Hedge on, slippage 5 points | 0.58 | | |

There is nothing to degrade: the strategy is below break-even at zero extra cost. Every scenario ruins every period.

## 7. Entry quality: is the score a signal? (Steps 13, 23)

The management layer was switched off and the EA's own R:R mode used instead (stop 1.5 x ATR of the last closed candle,
target 1.5R, one position at a time, no trailing, no health close, no hedge, fixed 0.01 lot). This isolates the entry.

| Run | Trades | Win | Net PF | DEV / VAL / OOS PF | Gross per trade before spread (DEV / VAL / OOS) |
|---|---:|---:|---:|---|---|
| M1, RR 1.5 | 6,653 | 34.7% | 0.81 | 0.75 / 0.81 / 0.85 | -0.14 / -0.02 / +0.03 |
| M5, RR 1.5 | 7,180 | 35.6% | 0.85 | 0.79 / 0.85 / 0.89 | -0.15 / -0.01 / +0.03 |
| M3, RR 1.5 | 8,685 | 36.0% | 0.86 | 0.85 / 0.84 / 0.88 | |
| M5, RR 1.0 | 8,732 | 45.1% | 0.85 | 0.80 / 0.85 / 0.89 | |
| M5, RR 2.0 | 7,792 | 30.1% | 0.88 | 0.88 / 0.88 / 0.87 | |
| M5, RR 1.5, threshold 6 | 3,972 | 37.9% | 0.95 | 0.87 / 0.87 / 0.99 | +0.02 / +0.04 / +0.36 |
| M5, RR 1.5, closed candles only (blend 0) | 7,025 | 35.9% | 0.84 | 0.80 / 0.79 / 0.89 | |

Break-even win rate at 1.5R is 40%; the score achieves 35-36%. Gross expectancy before spread is -$0.04 per trade on
7,180 trades: the entry is a coin flip, the same result your signal lab found for the TWK flip (gross hit rate 43-50%, MFE =
MAE). The one non-zero reading is threshold 6 on M5: gross +$0.19 per trade, driven by OOS (+$0.36 on 1,921 trades, about
+0.03R on a $12 stop) with DEV and VAL at +$0.02-0.04. It never covers the spread (net -$0.30 DEV, -$0.32 VAL, -$0.08 OOS)
and the DEV/VAL values are inside noise; it is recorded under "weak evidence" below, not as an edge.

## 8. Parameter robustness (Step 16)

Default profile, M5, hedge off, calibrated; expectancy per trade DEV / VAL / OOS (all runs ruin all periods):

| Setting | Exp DEV / VAL / OOS |
|---|---|
| threshold 3.5 / 4.0 / 4.5 (default) / 5.0 / 5.5 / 6.0 | -0.42/-0.39/-0.37, -0.42/-0.41/-0.44, -0.43 (default), -0.45/-0.52/-0.49, -0.46/-0.46/-0.55, -0.77/-0.62/-0.98 |
| EMA 4/10, 6/14, 8/21 | -0.47/-0.45/-0.44, -0.42/-0.41/-0.40, -0.38/-0.41/-0.45 |
| RSI 6 / 10 / 14 | -0.47/-0.43/-0.42, -0.42/-0.44/-0.47, -0.46/-0.43/-0.49 |
| ATR 6 / 10 / 14 | -0.47/-0.44/-0.47, -0.41/-0.40/-0.44, -0.40/-0.37/-0.45 |
| forming-candle blend 0.0 / 0.6 | -0.53/-0.56/-0.60, -0.32/-0.35/-0.33 |
| trailing distance $0.50 / $1 / $2 | -0.41/-0.40/-0.43, -0.37/-0.44/-0.46, -0.47/-0.56/-0.56 |
| London only / NY only / Asia only | -0.45/-0.19/-0.39, -0.40/-0.43/-0.39, -0.51/-0.53/-0.42 |
| news proxy, no entries 15:15-16:00 (M5 / M1) | -0.41/-0.40/-0.42, -0.48/-0.48/-0.51 |

Classification: there is no profitable region to overfit. The result is uniformly negative across 25 perturbations and three
periods, so the overfit-risk question does not arise; what the table establishes is that the loss is structural (spread paid on
a 50-second trade with a coin-flip entry), not a tuning accident. Chart: `results/nyao/charts/perturbation_M5.png`.

## 9. Component tests on BASELINE (Steps 20-21)

The Nyao smoothed score was computed at the exact moment BASELINE enters (the open of the bar after the M3 signal) and
used as a gate on the TWK signals; everything else in BASELINE unchanged. Retention rule as in the filter lab: better
expectancy and PF than BASELINE in both DEV and VAL.

| Gate | Signals kept | Trades | Net | PF | DEV PF | VAL PF | OOS PF | Passes DEV+VAL |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BASELINE (60 months, 0.02 lot) | 42,289 | 5,354 | -4,888 | 0.80 | 0.65 | 0.66 | 0.94 | |
| Nyao score in trade direction >= 4.5 (the EA's threshold) | 34,065 | 4,721 | -5,026 | 0.77 | 0.63 | 0.66 | 0.89 | no |
| score >= 6.0 | 17,230 | 2,917 | -3,036 | 0.78 | 0.66 | 0.68 | 0.88 | yes, by 0.01-0.02, then worse OOS |
| score >= 3.0 | 41,122 | 5,256 | -4,927 | 0.80 | 0.65 | 0.66 | 0.92 | no |
| score in direction > opposite score | 34,463 | 4,904 | -5,108 | 0.78 | 0.64 | 0.64 | 0.90 | no |
| block when opposite score >= 4.5 | 31,613 | 4,592 | -4,203 | 0.80 | 0.64 | 0.69 | 0.93 | no (DEV worse) |
| dead-market gate only | 42,233 | 5,350 | -4,808 | 0.80 | 0.65 | 0.66 | 0.94 | removes 56 signals, no effect |
| inverse: keep only score < 4.5 | 8,224 | 804 | -100 | 0.97 | 0.71 | 0.57 | 1.34 | no (VAL worse) |

BASELINE trades bucketed by the Nyao score at entry (expectancy per trade, 0.02 lot): 3.5-4.5: -0.13 (n 498); 4.5-5.5:
-0.79 (1,064); 5.5-6.5: -1.39 (1,859); 6.5-10: -0.81 (1,718). The higher the Nyao momentum score, the worse the TWK trade in
DEV (-0.83, -1.50, -1.18, -1.09 across the four buckets). A momentum confirmation on top of a momentum flip selects the late
entries. No gate is adopted.

## 10. Trade-by-trade comparison (Step 22)

BASELINE (5,354 trades) against Nyao M3 hedge-off calibrated (6,787 trades across the three period runs), matched on the
entry M3 bar and direction (`results/nyao/TRADE_BY_TRADE_COMPARISON.csv`):

| Category | Trades | BASELINE P&L | Nyao P&L |
|---|---:|---:|---:|
| A. BASELINE takes, Nyao avoids | 5,214 | -4,797 | |
| B. Nyao takes, BASELINE avoids | 6,646 | | -2,889 |
| C. both take, both win | 49 | +513 | +53 |
| D. both take, both lose | 38 | -401 | -120 |
| E. BASELINE loses, Nyao wins | 39 | -351 | +43 |
| F. Nyao loses, BASELINE wins | 15 | +132 | -28 |

Only 141 of 5,354 BASELINE trades (2.6%) coincide with a Nyao entry. The reason is mechanical: TWK fires on a Supertrend
flip with volume confirmation, at most a few times a day; Nyao fires whenever EMA 5/12, RSI 8 and the candle body agree,
about 70 times a day on M1 and 25 on M5 in the path-bound runs, and its $7.50 duplicate rule, not its signal, spaces them.
The overlap is too small to say anything about E and F beyond noise (39 and 15 trades). There is no shared decision to
transfer.

## 11. The whole history at a fixed stop, ablation, regimes and loss patterns (Steps 10-12, 17, 18, 20)

The shipped EA stops itself within months, so to read regimes over all five years the research runs in `nyao_lab2.py`
keep every rule but hold the stop at a fixed $10 per 0.01 lot and switch off the ruin stop and the drawdown pause.

| Run (five years continuous, calibrated) | Trades | Win | PF | Net | Gross before spread | Spread paid | DEV / VAL / OOS PF |
|---|---:|---:|---:|---:|---:|---:|---|
| M1, hedge off | 41,816 | 75% | 0.65 | -19,665 | -1,444 | 18,221 | 0.69 / 0.70 / 0.64 |
| M1, hedge on | 41,366 | 77% | 0.78 | -45,387 | -12,305 | 33,082 | 0.78 / 0.89 / 0.77 |
| M5, hedge off | 28,754 | 78% | 0.69 | -10,601 | +801 | 11,402 | 0.69 / 0.69 / 0.69 |
| M5, hedge on | 29,460 | 78% | 0.81 | -20,188 | -986 | 19,203 | 0.80 / 0.87 / 0.80 |
| M3, hedge off | 34,529 | 77% | 0.68 | -13,340 | +840 | 14,180 | 0.70 / 0.72 / 0.68 |
| M3, hedge on | 35,027 | 78% | 0.80 | -28,594 | -4,066 | 24,528 | 0.80 / 0.86 / 0.79 |

Before spread the system is flat (gross -$1,444 to +$840 on 29,000-42,000 trades); it pays 11-18 times the deposit in spread
over five years. Switching its layers off one at a time (M5, hedge off) moves the gross between -$2,064 and +$4,041 and
never the sign of the net: trailing off -8,259, loss management off -10,431, re-entry off -10,368, dampening off -25,046 on
71,536 trades, trail $1 -9,331, trail $3 -11,104, ATR stop with 1.5R target -7,826. The hedge chain with every other exit off
loses $94,341 on 28 closed trades: it has no floor. Detail in `results/nyao/ROBUSTNESS_ANALYSIS.md`.

Where it loses (fixed-stop M5, expectancy per trade): every session (Asia -0.37, London -0.40, NY overlap -0.30, NY late
-0.49), every hour (best 05:00 at -0.12), every year (-0.29 to -0.33 in 2021-25, -0.54 in 2026 when the spread reached
51 points), with the H1 trend and against it alike (-0.37 / -0.37), in low / normal / high volatility (-0.50 / -0.38 /
-0.35). Losers and winners have the same share of counter-trend, high-volatility and NY-session entries, so no pre-entry
condition separates them. What separates them is the exit design: 79% of trades are cut at about +$1 after a median 3
minutes, 21% are held a median 21 minutes to a health close (-$4.37 average, 59% of the loss) or the stop (-$10, 40%).
Monte Carlo: probability of a losing year 1.00, all 50 rolling 12-month windows negative, mean trade -0.37 with a 95%
interval of -0.40 to -0.33. Detail in `results/nyao/LOSS_PATTERN_ANALYSIS.md`.

Visual test (`results/nyao/charts/week_*.png`, `day_2026-01-07_M1.png`): entries sit at the end of each impulse because every
score term measures a move already made; winners are one to three candles long; losers are the entries at the last impulse
before a turn, held through the reversal; 199 trades in one OOS week against BASELINE's 26, 64 in one day against 7.

## 12. Look-ahead and repainting audit (Step 14)

PASS on future access, future high/low, data leakage and signal timing. FAIL on intrabar assumptions and realistic execution:
the $0.20 trail, the +$0.82 break-even lock and the per-tick health close all act inside one M1 bar, so any bar-based test
(including the MT5 tester's OHLC and open-price modes) reports the optimistic bound. One quirk: the 40% weight the author
gives the forming candle is applied, at the decision tick, to a one-tick candle that has no body, range, breakout or wick, so
that term carries only trend and ATR. Detail in `results/nyao/CODE_AUDIT.md`.

## 13. Final conclusions (the brief's format)

**Strong evidence**

* The Nyao Scalper default profile loses the account on this data: 12 of 12 period runs from $1,000 end at the EA's $20
  floor, on M1, M5 and M3, hedge on and off; the continuous run is ruined by March-July 2022. PF 0.57-0.73.
* The loss is structural, not a parameter accident: 25 perturbations of threshold, EMA, RSI, ATR, blend, trailing distance
  and session are negative in all three periods.
* The $0.20 trailing stop exits at its activation level on real ticks (median lambda 0.00 on 3,905 trailing exits). The
  bar-level profit of the EA is a modelling artifact worth about +$0.80 per trade, which is the whole difference between
  "PF 1.3-1.4, $19,000-50,000 in five years" and ruin.
* The Nyao score gate does not improve BASELINE; the EA's own threshold (4.5) makes BASELINE worse in every period.

**Weak evidence**

* Entry-only, threshold 6 on M5: gross before spread +$0.02 / +$0.04 / +$0.36 per trade in DEV / VAL / OOS, net negative in
  all three. Same order of magnitude as the gross asymmetries your discovery ledger already rejected; not tradeable.
* The safe profile (no hedge, threshold 6, 0.5% stop, 3 positions) does not ruin: -30% over five years at PF 0.66-0.75.
  It loses more slowly, not less surely.

**Failed approaches**

* Every shipped profile (default, balanced, aggressive) on every timeframe; the $200 account (28-30% win rate with a $2 stop);
  every cost scenario; the hedge chain (larger average loss, largest single loss -$393 on $1,000, no cap by design).

**Important loss patterns**

* Spread: 32-51 points on a trade whose target profit is 82-101 points and whose median life is 50 seconds. Spread paid equals
  2-3x the deposit per year.
* The account-defined stop: 1% of equity in dollars regardless of ATR, so a shrinking account gets a tighter stop and a growing
  one a looser stop; on $200 the stop is under one M1 range.
* Immediate same-direction re-entry after a health close, and lot increases in drawdown.
* Detailed conditions (sessions, trend alignment, volatility regime, exit reasons, streaks) in LOSS_PATTERN_ANALYSIS.md.

**Useful components**

* None transferable. The dead-market gate (ATR ratio >= 0.6) removes 56 of 42,289 TWK signals and changes nothing; the
  score, the health close, the break-even-on-spread, the cooldown and the drawdown gate are all in the family your filter and
  protection labs already tested and found to carry no information after costs.
* The one idea worth keeping is methodological: any stop or trail smaller than the instrument's typical minute range must
  be tested on ticks, and the tick sample you already have is enough to calibrate it.

**Baseline weaknesses (relative to Nyao)**

* BASELINE is also negative on the same 60 months: -$4,888 at 0.02 lot, PF 0.80 (DEV 0.65, VAL 0.66, OOS 0.94). It shares
  Nyao's core defect, a coin-flip entry paying spread, at a lower frequency.

**Baseline strengths (relative to Nyao)**

* Structural stop (pivot or purple line) instead of an account-defined one; a profit-protection scheme that does not sit
  inside the spread; 4-8x fewer trades, so 4-8x less spread; no martingale; it takes five years to lose what Nyao loses in
  seven months at half the lot size.

**Unproven**

* The MT5 news filter (no calendar data); the proxy block of 15:15-16:00 changed nothing.
* Tick calibration covers 2025 Thu/Fri 14:00-19:59 server only (the sample on disk). Quiet-hour behaviour of the trail was
  not measured on ticks; the pessimistic bound still applies since a 20-point retrace is a one-tick event at any hour.
* The two category-C crypto repositories were not reproduced (no backtester, exchange-specific data).

## Files

| File | Content |
|---|---|
| `GITHUB_SCALPING_RESEARCH.md` | this report |
| `results/nyao/STRATEGY_INVENTORY.csv` | the 20 repositories with every field of Step 1 and the category of Step 2 |
| `results/nyao/CODE_AUDIT.md` | Step 3 mechanics, dangerous-mechanism flags, Step 14 audit |
| `results/nyao/STRATEGY_COMPARISON.csv` | the Step 19 table |
| `results/nyao/COMPONENT_TEST_RESULTS.csv` | Step 20 gates on BASELINE plus the Nyao management ablation |
| `results/nyao/TRADE_BY_TRADE_COMPARISON.csv`, `trade_by_trade_summary.csv` | Step 22 |
| `results/nyao/LOSS_PATTERN_ANALYSIS.md`, `ROBUSTNESS_ANALYSIS.md` | Steps 10-12, 16-17 |
| `results/nyao/TABLES.md` | every table the scripts produce, including regime and session breakdowns |
| `results/nyao/nyao_runs.csv`, `nyao_runs2.csv`, `lab.json`, `regimes.json` | run-level results |
| `results/nyao/tick_calibration.csv`, `tick_calibration.json` | the 4,991 tick-replayed trades |
| `results/nyao/monte_carlo.json` | Step 17 bootstrap, shuffled drawdown, rolling windows, execution perturbation |
| `results/nyao/trades/*.csv` | every trade of every run (entry, exit, stop, P&L, R, reason, score, chain flags, MFE/MAE) |
| `results/nyao/charts/` | calibration, equity readings, perturbation, entry-only, sessions, chart weeks with trades |
| `results/nyao/source/nyao_scalper_v43.mq5`, `results/nyao/settings/*.set` | the EA and its five profiles as tested |
| `nyao_engine.py`, `nyao_tick_calibration.py`, `nyao_lab.py`, `nyao_lab2.py`, `make_nyao_tables.py` | reproducible backtests: run in this order (about 25 minutes; one at a time, the machine cannot hold two) |
| `data/XAUUSD_M1_servertime_full.csv.gz` | the 60-month M1 file built from all Dukascopy chunks (the earlier labs used the 39-month file) |
