# Patrick Nill PBD counter-trend framework on XAUUSD: baseline test and loss study

Run date: 2026-09-26. Data: Sep 2021 to 25 Sep 2026 (60 of 61 months). All figures are in R
(multiples of the planned risk per trade). "Real" = XM spread, 0.10 USD/oz slippage, 1-minute
execution delay, XM swap; "ideal" = signal-bar close fill with zero costs.

**Headline.** Under the pre-registered objective rules, the framework has no positive expectancy on
XAUUSD in any of the three chronological periods, with or without costs. Ideal execution is
approximately flat (-0.056R per trade for ping-pong, -0.075R for breakout+pullback,
-0.034R for breakout-at-close); realistic execution turns that into -0.215R,
-0.244R and -0.208R (profit factors 0.69, 0.69, 0.72).
The 95% bootstrap interval of the mean trade excludes zero on the negative side for every playbook.
The mechanism is measurable: ping-pong trades lose to continuation of the impulse
(27% of ping-pong loss),
breakout trades lose to false breakouts (62% of pullback-playbook loss),
and the objective ranges are far smaller and shorter-lived than the multi-day swings the source describes
(median hold 0.9 h, 84% of trades closed within 4 h). No adaptation tested is
positive in the development period; the two that are positive in validation and out-of-sample
(confirmed-breakout entry with 1.5 ATR stops, and ping-pong in the London/New York overlap) owe their sign
to 2025 alone. **No Gold Strategy Specification is issued.** Section 20 states what the data does and does not support.

---

## 1. Strategy explanation

The source (Patrick Nill, "Counter-Trend Swing Trading") is a discretionary method built on the PBD
model of Market Profile shapes. A **P structure** is a large upward impulse followed by a consolidation
that forms above the origin of the impulse; a **B structure** is the mirror after a downward impulse.
(The source does not define the D element; in Market Profile usage D is the balanced, bell-shaped day.)
The impulse itself is never traded. The 15-minute chart frames the impulse and the range; the weekly
Market Profile Value Area High and Low (VAH/VAL) are the reference zones, and a setup that lines up
with them is considered "significantly stronger". Once price reaches a marked zone the trader drops to
footprint and order-flow charts for the entry.

Two playbooks: (1) **range ping-pong**, buy near the range low and sell near the range high until the
range breaks; (2) **breakout / pullback**, wait for a decisive break of the range, preferably for a
pullback to the broken edge, and enter in the direction of the resumed move. Targets sit back near the
origin of the initial impulse; the stop is fixed before entry, over, inside or above the zone. Risk is
at most 1% of equity per trade. Published expectations for the method: 50-60% win rate, holds of 4 hours
to 3 days (average about one day), losing streaks of 10-20 called normal, any drawdown above 20% rejected,
no trading during high-impact news.

## 2. Exact objective rules

Machine-readable version: `spec/pbd_xauusd_rules.json` (also `results/deliverables/01_rule_specification.json`).
Every parameter below was fixed before the first backtest and is the **baseline**; every later variant
changes one parameter.

**Impulse (definition A, primary "atr").** Window of N = 8 M15 bars (2 h). Net move |close[i] - close[i-8]|
>= 3.5 x ATR14 measured before the window, efficiency ratio (net / sum of absolute close changes) >= 0.6,
no data gap inside the window. Alternatives tested: 98th percentile of trailing-30-day 8-bar moves,
range expansion (window range >= 3 x trailing median), and >= 5 consecutive same-direction closes with
>= 2 ATR net. Origin = lowest low (P) / highest high (B) inside 4N bars before the window, accepted only if
the path from it never retraced more than half of itself; otherwise the window's own extreme. The extreme
keeps updating while price makes new highs/lows. Abandon if a close retraces more than 61.8% of the impulse
or if no range forms within 24 bars of the extreme.

**Consolidation range (B, C).** The last 8 bars, starting at or after the extreme bar, must form a box with
width <= 0.6 x impulse, width >= 0.5 x pre-impulse ATR, |close_end - close_start| <= 0.5 x width, and the box
must sit in the terminal 61.8% of the impulse. Range high = highest high, range low = lowest low of those
8 bars; both are frozen. A touch = a bar entering the 20%-of-width zone at a boundary (consecutive bars count
once). The structure expires after 288 bars (3 days).

**Ping-pong (playbook A).** Long when a bar's low enters the lower 20% zone and the bar closes back above the
range low but not above the midpoint (a rejection close = the Version-A proxy for order-flow confirmation);
short is the mirror. Stop = boundary -/+ 0.5 ATR14. Target = 0.9 x width toward the opposite boundary.
A new signal on the same side needs a close >= 30% of width away first. Ping-pong stops when a valid breakout occurs.

**Breakout / pullback (playbook B1, D, E).** Breakout = M15 close beyond a boundary by >= 0.25 ATR. Pullback =
within 16 bars a bar reaches the boundary +/- 0.25 ATR and closes on the breakout side; entry after that bar.
A close back inside the range by > 0.25 ATR is a failed breakout (structure returns to RANGE). Stop =
beyond min/max(pullback extreme, boundary) by 0.5 ATR. Target = impulse origin for a counter-impulse break,
1 x width measured move for a continuation break. B2 = the same breakout entered at the breakout close.

**Weekly VAH/VAL (F).** Week = Sunday 21:00 UTC to Sunday 21:00 UTC. Bins of 0.025% of price (0.10 USD floor).
Volume of every bar spread uniformly over the bins it touches. 70% value area expanded two bins at a time
from the POC toward the heavier side. Volume source: Dukascopy traded volume on M1 (primary), XM tick volume
and TPO count (sensitivity). The **previous completed week's** levels are used for the whole current week;
the developing current-week VA is recorded as a sensitivity variant. No look-ahead anywhere: every decision
at bar i uses bars <= i, and fills happen on the M1 bar after the signal bar closes.

**Management.** One position at a time, max hold 72 h, 1% risk per trade.

## 3. Data used

| Item | Value |
|---|---|
| M1 bars (Dukascopy bid, UTC) | 1,766,192 from 2021-09-01 00:00:00 to 2026-09-25 13:30:00 |
| M15 bars | 117,788 in 60 months (July 2024 missing: Dukascopy returned HTTP 429 on every attempt) |
| Volume | Dukascopy traded volume = REAL volume from one ECN venue. NOT COMEX futures volume. NOT footprint data. |
| Tick volume | XM MT5 tick volume, M15, from 18 Jul 2022 (used only for the VA sensitivity) |
| Spread | XM GOLD per-M15-bar spread, converted from server time (Europe/Athens); 17.7% of bars filled with the monthly median (mostly before Jul 2022, at 0.25 USD) |
| Sessions | DST-aware from London / New York / Tokyo local clocks |
| News | No calendar file available offline. Proxy: weekday 08:30 ET and 10:00 ET slots, FOMC 14:00 ET on published decision days, plus ex-post "shock bar" (M15 range > 3 ATR) for loss labelling only |
| Split | DEV Sep 2021 - Dec 2023, VAL Jan 2024 - Mar 2025, OOS Apr 2025 - Sep 2026 (fixed before any result) |

**Version A vs Version B.** Only Version A (price + market profile + available volume) could be built.
Version B needs bid/ask footprint or COMEX order-flow data, which the dataset does not contain. Tick volume
and Dukascopy volume were not used as a stand-in for footprint confirmation; where a volume proxy is used
(loss label "bad_orderflow_proxy", filter "weak_orderflow_proxy", breakout confirmation "volume") it is labelled as a proxy.

## 4. Gold market assumptions

* XM GOLD contract: 100 oz per lot, 0.01 lot = 1 oz, digits 2. Swap long -0.8684 / short +0.1979 USD per oz per night, Wednesday x3.
* Median M15 ATR14 rose from 1.95 USD (2021) to 10.11 USD (2026) while the spread stayed at 0.25-0.40 USD,
  so the spread as a share of the median ping-pong stop fell from 10% to 4%.
  Every year-by-year comparison must be read against this regime change.
* Weekend gaps are real: the worst baseline trade lost -6.9R (long into a Sunday open); 9 trades lost more than 2R, together -32R.
* Sunday 22:00/23:00 UTC open and the CME maintenance hour produce off-hours bars that carry wide spreads; these are in the data as delivered.

## 5. Baseline results (original framework, pre-registered parameters)

Structures: 1,810 impulses detected, 1,205 ranges confirmed (about 20.1 per month),
604 abandoned because price retraced more than 61.8% before a range formed. Median impulse
7.818 pre-impulse ATR (5.236-14.825 for the 10th-90th percentile) over 11 bars;
median range width 2.933 ATR; median range life 23 bars (about 6 h). Outcomes of confirmed ranges: {'breakout_traded': 997, 'no_pullback': 208}.
0.266 failed breakouts per range; 1.456 / 1.493 touches of the high / low.

Signals proposed: {'pingpong': 3833, 'breakout_immediate': 1525, 'breakout_pullback': 997}. With one position at a time the taken trades are below.

**Combined A + B1 (one position across both playbooks), realistic costs:**

| period | n | win_rate | expectancy | pf | total_r | max_dd_r | max_loss_streak | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|
| DEV | 1191 | 0.337 | -0.236 | 0.674 | -281.113 | -291.812 | 16 | -0.319 | -0.151 |
| VAL | 562 | 0.327 | -0.226 | 0.679 | -126.828 | -139.483 | 21 | -0.336 | -0.116 |
| OOS | 740 | 0.331 | -0.192 | 0.730 | -142.243 | -149.915 | 11 | -0.299 | -0.087 |
| ALL | 2493 | 0.333 | -0.221 | 0.692 | -550.184 | -567.270 | 21 | -0.276 | -0.165 |

The holding-time distribution is the first structural finding: median 0.9 h, 84% of trades
closed within 4 h and 2.8% held 24 h or more, against the source's 4 h to 3 days. The objective 15-minute
impulse-and-box definition finds intraday structures (23-bar median life), not multi-day swings.
Longer confirmation windows (12-24 bars) were tested in section 10 and are worse.

## 6. Ping-pong results (playbook A)

Realistic execution:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 800 | 0.352 | 1.172 | -1.085 | 0.588 | -0.289 | -231.518 | -238.824 | 10 | 0.900 | 1.713 | 0.743 | 0.945 | -0.370 | -0.210 |
| VAL | 371 | 0.372 | 1.328 | -1.035 | 0.760 | -0.156 | -57.804 | -64.651 | 14 | 1.000 | 1.713 | 0.838 | 0.879 | -0.281 | -0.016 |
| OOS | 490 | 0.361 | 1.497 | -1.064 | 0.796 | -0.139 | -67.935 | -71.571 | 18 | 0.900 | 1.930 | 0.945 | 0.933 | -0.266 | 0.000 |
| ALL | 1661 | 0.359 | 1.305 | -1.068 | 0.686 | -0.215 | -357.256 | -361.484 | 18 | 0.933 | 1.777 | 0.824 | 0.927 | -0.274 | -0.153 |

Ideal execution:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 808 | 0.374 | 1.459 | -1.009 | 0.863 | -0.087 | -70.040 | -86.872 | 11 | 0.967 | 1.801 | 1.004 | 0.908 | -0.170 | -0.004 |
| VAL | 377 | 0.395 | 1.598 | -1.000 | 1.044 | 0.027 | 10.141 | -25.188 | 12 | 1.067 | 1.884 | 1.080 | 0.864 | -0.109 | 0.174 |
| OOS | 502 | 0.367 | 1.613 | -1.042 | 0.896 | -0.069 | -34.590 | -45.777 | 18 | 0.892 | 1.898 | 1.047 | 0.910 | -0.210 | 0.068 |
| ALL | 1687 | 0.376 | 1.536 | -1.017 | 0.912 | -0.056 | -94.489 | -103.250 | 18 | 0.967 | 1.848 | 1.034 | 0.899 | -0.122 | 0.013 |

Median planned reward/risk 1.39; median stop 1.16 ATR. Win rate 35.9% against the 50-60% the source expects.
MFE 0.82R and MAE 0.93R on average: the typical trade goes as far against as for.

By session (real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| asia | 433 | 0.381 | -0.186 | 0.715 | -80.471 | -83.049 | 0.733 |
| london | 364 | 0.357 | -0.230 | 0.657 | -83.702 | -87.091 | 0.733 |
| newyork | 519 | 0.318 | -0.296 | 0.610 | -153.505 | -157.097 | 2.183 |
| offhours | 109 | 0.358 | -0.245 | 0.632 | -26.663 | -27.421 | 1.333 |
| overlap | 236 | 0.415 | -0.055 | 0.910 | -12.916 | -28.880 | 0.383 |

By structure and side (real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| B_long | 322 | 0.348 | -0.284 | 0.605 | -91.520 | -91.520 | 0.908 |
| B_short | 442 | 0.342 | -0.194 | 0.719 | -85.801 | -102.674 | 0.992 |
| P_long | 485 | 0.379 | -0.224 | 0.664 | -108.764 | -108.764 | 1.017 |
| P_short | 412 | 0.364 | -0.173 | 0.742 | -71.170 | -87.480 | 0.808 |

By year (real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| 2021.000 | 106.000 | 0.292 | -0.473 | 0.414 | -50.106 | -50.698 | 1.208 |
| 2022.000 | 351.000 | 0.345 | -0.287 | 0.589 | -100.702 | -100.702 | 0.900 |
| 2023.000 | 343.000 | 0.379 | -0.235 | 0.651 | -80.709 | -87.601 | 0.850 |
| 2024.000 | 287.000 | 0.383 | -0.132 | 0.794 | -37.825 | -53.540 | 1.117 |
| 2025.000 | 334.000 | 0.347 | -0.166 | 0.759 | -55.469 | -76.069 | 0.867 |
| 2026.000 | 240.000 | 0.371 | -0.135 | 0.798 | -32.444 | -56.650 | 0.900 |

Behaviour: ping-pong is a high-frequency, short-hold, low-R:R playbook here. Its losses are dominated by the
impulse resuming through the range (section 8), and its sign by session: only the London/New York overlap is
close to flat.

## 7. Breakout / pullback results (playbook B1, plus B2)

B1 realistic:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 455 | 0.281 | 2.122 | -1.099 | 0.756 | -0.193 | -87.801 | -102.718 | 21 | 1.050 | 4.053 | 1.228 | 0.996 | -0.362 | -0.021 |
| VAL | 212 | 0.250 | 1.997 | -1.076 | 0.619 | -0.308 | -65.202 | -71.697 | 14 | 1.217 | 3.635 | 1.007 | 0.982 | -0.510 | -0.098 |
| OOS | 278 | 0.273 | 1.798 | -1.059 | 0.639 | -0.278 | -77.171 | -84.636 | 11 | 0.992 | 3.404 | 1.041 | 0.966 | -0.461 | -0.092 |
| ALL | 945 | 0.272 | 2.000 | -1.082 | 0.691 | -0.244 | -230.175 | -251.158 | 21 | 1.033 | 3.768 | 1.123 | 0.984 | -0.347 | -0.134 |

B1 ideal:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 463 | 0.309 | 2.265 | -1.003 | 1.009 | 0.006 | 2.910 | -54.088 | 21 | 1.067 | 4.085 | 1.521 | 0.928 | -0.165 | 0.183 |
| VAL | 215 | 0.260 | 2.342 | -1.021 | 0.808 | -0.145 | -31.129 | -39.637 | 15 | 1.350 | 3.655 | 1.303 | 0.969 | -0.388 | 0.096 |
| OOS | 282 | 0.287 | 2.029 | -1.035 | 0.790 | -0.155 | -43.716 | -53.759 | 11 | 1.017 | 3.430 | 1.233 | 0.941 | -0.343 | 0.037 |
| ALL | 960 | 0.292 | 2.212 | -1.017 | 0.896 | -0.075 | -71.936 | -136.911 | 21 | 1.083 | 3.796 | 1.388 | 0.941 | -0.180 | 0.046 |

B2 (entry at the breakout close) realistic:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 668 | 0.287 | 1.703 | -1.065 | 0.645 | -0.269 | -179.747 | -183.663 | 14 | 0.767 | 3.670 | 1.033 | 0.963 | -0.381 | -0.161 |
| VAL | 314 | 0.290 | 1.876 | -1.074 | 0.713 | -0.219 | -68.743 | -77.182 | 16 | 0.817 | 3.415 | 1.029 | 0.948 | -0.386 | -0.054 |
| OOS | 437 | 0.332 | 1.802 | -1.052 | 0.850 | -0.105 | -45.974 | -61.018 | 12 | 0.800 | 3.378 | 1.185 | 0.924 | -0.258 | 0.052 |
| ALL | 1419 | 0.302 | 1.773 | -1.063 | 0.720 | -0.208 | -294.464 | -294.464 | 16 | 0.800 | 3.524 | 1.079 | 0.948 | -0.286 | -0.124 |

B2 ideal:

| period | n | win_rate | avg_win | avg_loss | pf | expectancy | total_r | max_dd_r | max_loss_streak | median_hold_h | avg_rr | mfe_r | mae_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV | 677 | 0.307 | 2.150 | -1.000 | 0.954 | -0.032 | -21.649 | -46.745 | 15 | 0.933 | 3.724 | 1.391 | 0.937 | -0.169 | 0.106 |
| VAL | 326 | 0.301 | 2.126 | -1.013 | 0.902 | -0.069 | -22.619 | -40.897 | 14 | 0.925 | 3.312 | 1.290 | 0.950 | -0.254 | 0.129 |
| OOS | 441 | 0.333 | 2.034 | -1.033 | 0.984 | -0.011 | -4.788 | -30.944 | 13 | 0.983 | 3.243 | 1.307 | 0.901 | -0.166 | 0.148 |
| ALL | 1444 | 0.314 | 2.107 | -1.013 | 0.951 | -0.034 | -49.057 | -68.549 | 15 | 0.933 | 3.484 | 1.343 | 0.929 | -0.123 | 0.059 |

By session (B1 real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| asia | 307 | 0.199 | -0.248 | 0.705 | -76.004 | -105.837 | 1.033 |
| london | 202 | 0.307 | -0.196 | 0.740 | -39.593 | -51.032 | 0.758 |
| newyork | 199 | 0.236 | -0.351 | 0.594 | -69.935 | -77.359 | 2.400 |
| offhours | 66 | 0.197 | -0.280 | 0.661 | -18.511 | -21.695 | 1.683 |
| overlap | 171 | 0.433 | -0.153 | 0.757 | -26.132 | -39.902 | 0.417 |

By session (B2 real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| asia | 475 | 0.246 | -0.255 | 0.678 | -120.897 | -121.920 | 0.800 |
| london | 297 | 0.303 | -0.267 | 0.641 | -79.284 | -93.004 | 0.667 |
| newyork | 303 | 0.284 | -0.246 | 0.691 | -74.444 | -77.790 | 2.167 |
| offhours | 91 | 0.253 | -0.223 | 0.714 | -20.310 | -30.948 | 1.583 |
| overlap | 253 | 0.443 | 0.002 | 1.003 | 0.470 | -18.630 | 0.317 |

By structure and side (B1 real):

| group | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|
| B_long | 253 | 0.225 | -0.265 | 0.694 | -67.020 | -77.983 | 1.467 |
| B_short | 199 | 0.387 | 0.016 | 1.026 | 3.173 | -22.173 | 0.733 |
| P_long | 223 | 0.332 | -0.214 | 0.703 | -47.790 | -58.226 | 1.000 |
| P_short | 270 | 0.181 | -0.439 | 0.507 | -118.537 | -132.101 | 1.050 |

Behaviour: the pullback playbook has the lowest win rate (27.2%) and the highest planned R:R
(3.8) because counter-impulse breaks target the impulse origin. Waiting for the pullback did not
beat entering at the breakout close (B2 -0.208R vs B1 -0.244R real). Breakout losses are false
breakouts: price closes back inside the range within 8 bars.

## 8. Loss taxonomy

Every losing trade carries all matching labels; the primary category is the first match in a fixed
priority order (news/shock first, then false breakout, trend continuation, ...). Definitions are in
`results/baseline/label_rules.json`. "trades_flagged" counts winners and losers carrying the label,
"losses" the losing trades whose primary category it is.

Ping-pong (A, real):

| category | trades_flagged | losses | loss_pct | avg_loss | max_loss | total_loss | share_of_total_loss | max_consec | dd_window_contribution |
|---|---|---|---|---|---|---|---|---|---|
| news_driven | 341 | 201 | 58.94 | -1.10 | -6.93 | -220.69 | 19.43 | 9 | -215.64 |
| false_breakout | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| trend_continuation_against | 377 | 291 | 100.00 | -1.05 | -1.93 | -306.07 | 26.94 | 377 | -297.98 |
| range_invalidated_before_entry | 178 | 76 | 100.00 | -1.05 | -1.14 | -79.47 | 7.00 | 178 | -74.31 |
| stop_too_tight | 65 | 37 | 100.00 | -1.06 | -1.35 | -39.19 | 3.45 | 65 | -39.19 |
| range_too_narrow | 129 | 32 | 68.22 | -1.29 | -5.76 | -41.15 | 3.62 | 16 | -41.15 |
| range_too_wide | 40 | 15 | 70.00 | -1.03 | -1.06 | -15.48 | 1.36 | 10 | -15.48 |
| entry_too_late | 506 | 112 | 48.22 | -1.03 | -2.09 | -114.83 | 10.11 | 8 | -113.82 |
| middle_of_range_entry | 335 | 7 | 47.46 | -0.99 | -1.03 | -6.96 | 0.61 | 8 | -6.96 |
| multiple_failed_tests | 238 | 30 | 69.33 | -1.05 | -1.32 | -31.51 | 2.77 | 16 | -29.49 |
| impulse_exhausted | 192 | 34 | 73.96 | -1.05 | -1.55 | -35.83 | 3.15 | 13 | -33.75 |
| impulse_not_strong_enough | 329 | 44 | 56.23 | -1.06 | -1.91 | -46.68 | 4.11 | 9 | -44.65 |
| poor_vah_val_location | 1186 | 122 | 64.17 | -1.09 | -3.34 | -132.75 | 11.69 | 16 | -130.75 |
| high_volatility | 260 | 17 | 65.00 | -1.01 | -1.16 | -17.10 | 1.51 | 14 | -15.08 |
| low_volatility | 121 | 1 | 63.64 | -1.05 | -1.05 | -1.05 | 0.09 | 7 | -1.05 |
| failed_pullback | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| breakout_without_continuation | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| stop_too_wide | 123 | 0 | 37.40 | 0.00 | 0.00 | 0.00 | -0.00 | 6 | 0.00 |
| bad_orderflow_proxy | 621 | 26 | 66.99 | -1.02 | -1.83 | -26.51 | 2.33 | 11 | -25.52 |
| other | 32 | 19 | 59.38 | -1.09 | -1.79 | -20.77 | 1.83 | 5 | -20.77 |

Breakout + pullback (B1, real):

| category | trades_flagged | losses | loss_pct | avg_loss | max_loss | total_loss | share_of_total_loss | max_consec | dd_window_contribution |
|---|---|---|---|---|---|---|---|---|---|
| news_driven | 282 | 160 | 56.74 | -1.15 | -8.08 | -183.56 | 24.66 | 8 | -158.22 |
| false_breakout | 540 | 434 | 100.00 | -1.06 | -3.86 | -460.24 | 61.84 | 540 | -405.21 |
| trend_continuation_against | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| range_invalidated_before_entry | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| stop_too_tight | 42 | 2 | 100.00 | -1.05 | -1.05 | -2.09 | 0.28 | 42 | -1.05 |
| range_too_narrow | 95 | 8 | 71.58 | -1.02 | -1.09 | -8.15 | 1.10 | 15 | -4.96 |
| range_too_wide | 57 | 7 | 82.46 | -1.05 | -1.07 | -7.32 | 0.98 | 25 | -7.32 |
| entry_too_late | 153 | 11 | 75.16 | -1.07 | -1.36 | -11.75 | 1.58 | 14 | -8.66 |
| middle_of_range_entry | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| multiple_failed_tests | 199 | 14 | 68.84 | -1.06 | -1.26 | -14.80 | 1.99 | 12 | -11.67 |
| impulse_exhausted | 102 | 8 | 87.25 | -1.02 | -1.05 | -8.13 | 1.09 | 18 | -6.06 |
| impulse_not_strong_enough | 189 | 6 | 67.72 | -1.07 | -1.26 | -6.41 | 0.86 | 14 | -5.16 |
| poor_vah_val_location | 682 | 22 | 72.73 | -1.07 | -1.82 | -23.60 | 3.17 | 20 | -23.60 |
| high_volatility | 103 | 0 | 63.11 | 0.00 | 0.00 | 0.00 | -0.00 | 9 | 0.00 |
| low_volatility | 81 | 1 | 85.19 | -1.05 | -1.05 | -1.05 | 0.14 | 19 | -1.05 |
| failed_pullback | 269 | 2 | 100.00 | -1.04 | -1.05 | -2.07 | 0.28 | 269 | -2.07 |
| breakout_without_continuation | 257 | 4 | 100.00 | -1.04 | -1.16 | -4.16 | 0.56 | 257 | -4.16 |
| stop_too_wide | 156 | 0 | 46.79 | 0.00 | 0.00 | 0.00 | -0.00 | 5 | 0.00 |
| bad_orderflow_proxy | 251 | 6 | 80.48 | -1.30 | -2.38 | -7.78 | 1.05 | 12 | -5.40 |
| other | 3 | 3 | 100.00 | -1.05 | -1.05 | -3.14 | 0.42 | 3 | -2.09 |

Breakout at close (B2, real):

| category | trades_flagged | losses | loss_pct | avg_loss | max_loss | total_loss | share_of_total_loss | max_consec | dd_window_contribution |
|---|---|---|---|---|---|---|---|---|---|
| news_driven | 477 | 269 | 56.39 | -1.07 | -7.60 | -288.34 | 27.37 | 9 | -287.30 |
| false_breakout | 757 | 577 | 100.00 | -1.06 | -4.08 | -609.34 | 57.84 | 757 | -609.34 |
| trend_continuation_against | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| range_invalidated_before_entry | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| stop_too_tight | 64 | 6 | 100.00 | -1.12 | -1.44 | -6.71 | 0.64 | 64 | -6.71 |
| range_too_narrow | 128 | 4 | 68.75 | -1.04 | -1.09 | -4.16 | 0.40 | 14 | -4.16 |
| range_too_wide | 82 | 7 | 78.05 | -1.03 | -1.06 | -7.24 | 0.69 | 25 | -7.24 |
| entry_too_late | 245 | 28 | 55.10 | -1.05 | -1.34 | -29.36 | 2.79 | 7 | -29.36 |
| middle_of_range_entry | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| multiple_failed_tests | 288 | 19 | 66.32 | -1.04 | -1.16 | -19.84 | 1.88 | 12 | -19.84 |
| impulse_exhausted | 166 | 7 | 84.34 | -1.02 | -1.05 | -7.11 | 0.67 | 17 | -7.11 |
| impulse_not_strong_enough | 284 | 10 | 63.73 | -1.09 | -1.63 | -10.92 | 1.04 | 11 | -10.92 |
| poor_vah_val_location | 1035 | 40 | 69.37 | -1.10 | -1.79 | -43.88 | 4.17 | 25 | -43.88 |
| high_volatility | 171 | 2 | 61.40 | -1.07 | -1.16 | -2.15 | 0.20 | 11 | -2.15 |
| low_volatility | 125 | 1 | 79.20 | -1.06 | -1.06 | -1.06 | 0.10 | 21 | -1.06 |
| failed_pullback | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | -0.00 | 0 | 0.00 |
| breakout_without_continuation | 338 | 7 | 100.00 | -1.22 | -1.80 | -8.53 | 0.81 | 338 | -8.53 |
| stop_too_wide | 229 | 1 | 41.92 | -1.05 | -1.05 | -1.05 | 0.10 | 5 | -1.05 |
| bad_orderflow_proxy | 282 | 5 | 77.30 | -1.10 | -1.44 | -5.48 | 0.52 | 12 | -5.48 |
| other | 14 | 8 | 57.14 | -1.03 | -1.24 | -8.27 | 0.78 | 3 | -8.27 |

Reading: for ping-pong the single largest bucket is **trend continuation against the counter-trend side**
(short in a P / long in a B, stopped as the impulse resumed), then **news/shock bars** and **poor VAH/VAL
location**. For both breakout playbooks the bucket is **false breakout**. "Stop too tight" (a stop twice as far
would have reached the target) is a small bucket, which matters for section 10: wider stops help through the
cost ratio, not through avoiding wick-outs. "Bad footprint confirmation" cannot be evaluated (no footprint data);
the volume proxy row is labelled as such.

## 9. No-trade conditions

Each filter removes the flagged signals; before/after metrics per period. "survives" = expectancy AND profit
factor both improve in DEV, in VAL and in OOS (the retention rule was fixed before running). Note that every
"after" column is still negative.

Ping-pong (A):

| filter | survives | n_before | exp_before | n_after | exp_after | removed_mean_r |
|---|---|---|---|---|---|---|
| impulse_too_small | no | 1661 | -0.215 | 1548 | -0.231 | 0.001 |
| impulse_too_large | DEV+VAL+OOS | 1661 | -0.215 | 1501 | -0.195 | -0.399 |
| range_too_narrow | no | 1661 | -0.215 | 1608 | -0.217 | -0.146 |
| range_too_wide | DEV+VAL only | 1661 | -0.215 | 1621 | -0.215 | -0.211 |
| poor_symmetry | no | 1661 | -0.215 | 965 | -0.256 | -0.159 |
| middle_of_range | no | 1661 | -0.215 | 1326 | -0.241 | -0.113 |
| va_too_far | DEV+VAL only | 1661 | -0.215 | 475 | -0.210 | -0.217 |
| va_inside_range | no | 1661 | -0.215 | 1661 | -0.215 |  |
| too_many_tests | DEV only | 1661 | -0.215 | 1423 | -0.190 | -0.366 |
| breakout_extended | no | 1661 | -0.215 | 1661 | -0.215 |  |
| breakout_bar_too_large | no | 1661 | -0.215 | 1661 | -0.215 |  |
| abnormal_volatility | no | 1661 | -0.215 | 1401 | -0.235 | -0.110 |
| news_slot | no | 1661 | -0.215 | 1516 | -0.227 | -0.095 |
| low_liquidity | no | 1661 | -0.215 | 1311 | -0.201 | -0.268 |
| weak_orderflow_proxy | DEV+VAL+OOS | 1661 | -0.215 | 871 | -0.167 | -0.269 |
| unfavourable_rr | no | 1661 | -0.215 | 1161 | -0.252 | -0.129 |
| target_too_close | no | 1661 | -0.215 | 1429 | -0.222 | -0.170 |
| stop_too_large | no | 1661 | -0.215 | 1282 | -0.221 | -0.194 |
| unclear_boundary | no | 1661 | -0.215 | 463 | -0.240 | -0.206 |
| cost_gate | DEV+VAL+OOS | 1661 | -0.215 | 1455 | -0.195 | -0.356 |

Breakout + pullback (B1):

| filter | survives | n_before | exp_before | n_after | exp_after | removed_mean_r |
|---|---|---|---|---|---|---|
| impulse_too_small | DEV only | 945 | -0.244 | 888 | -0.234 | -0.390 |
| impulse_too_large | DEV+VAL+OOS | 945 | -0.244 | 850 | -0.220 | -0.455 |
| range_too_narrow | no | 945 | -0.244 | 896 | -0.255 | -0.035 |
| range_too_wide | no | 945 | -0.244 | 888 | -0.262 | 0.045 |
| poor_symmetry | no | 945 | -0.244 | 537 | -0.219 | -0.276 |
| middle_of_range | no | 945 | -0.244 | 945 | -0.244 |  |
| va_too_far | no | 945 | -0.244 | 263 | -0.344 | -0.205 |
| va_inside_range | no | 945 | -0.244 | 945 | -0.244 |  |
| too_many_tests | no | 945 | -0.244 | 914 | -0.241 | -0.325 |
| breakout_extended | DEV only | 945 | -0.244 | 792 | -0.226 | -0.333 |
| breakout_bar_too_large | DEV only | 945 | -0.244 | 877 | -0.257 | -0.067 |
| abnormal_volatility | no | 945 | -0.244 | 843 | -0.267 | -0.053 |
| news_slot | no | 945 | -0.244 | 834 | -0.272 | -0.031 |
| low_liquidity | DEV+VAL+OOS | 945 | -0.244 | 792 | -0.206 | -0.438 |
| weak_orderflow_proxy | DEV only | 945 | -0.244 | 621 | -0.209 | -0.310 |
| unfavourable_rr | DEV only | 945 | -0.244 | 781 | -0.252 | -0.204 |
| target_too_close | DEV only | 945 | -0.244 | 870 | -0.256 | -0.098 |
| stop_too_large | DEV+VAL only | 945 | -0.244 | 705 | -0.240 | -0.254 |
| unclear_boundary | DEV only | 945 | -0.244 | 199 | -0.187 | -0.259 |
| cost_gate | no | 945 | -0.244 | 799 | -0.227 | -0.335 |

Breakout at close (B2):

| filter | survives | n_before | exp_before | n_after | exp_after | removed_mean_r |
|---|---|---|---|---|---|---|
| impulse_too_small | DEV only | 1419 | -0.208 | 1325 | -0.197 | -0.352 |
| impulse_too_large | DEV+VAL+OOS | 1419 | -0.208 | 1273 | -0.170 | -0.536 |
| range_too_narrow | no | 1419 | -0.208 | 1357 | -0.221 | 0.092 |
| range_too_wide | DEV only | 1419 | -0.208 | 1337 | -0.218 | -0.029 |
| poor_symmetry | no | 1419 | -0.208 | 815 | -0.201 | -0.216 |
| middle_of_range | no | 1419 | -0.208 | 1419 | -0.208 |  |
| va_too_far | DEV only | 1419 | -0.208 | 384 | -0.256 | -0.189 |
| va_inside_range | no | 1419 | -0.208 | 1419 | -0.208 |  |
| too_many_tests | no | 1419 | -0.208 | 1368 | -0.214 | -0.047 |
| breakout_extended | DEV only | 1419 | -0.208 | 1174 | -0.220 | -0.148 |
| breakout_bar_too_large | DEV only | 1419 | -0.208 | 1303 | -0.216 | -0.108 |
| abnormal_volatility | no | 1419 | -0.208 | 1248 | -0.241 | 0.037 |
| news_slot | no | 1419 | -0.208 | 1239 | -0.240 | 0.016 |
| low_liquidity | DEV+VAL only | 1419 | -0.208 | 1224 | -0.192 | -0.306 |
| weak_orderflow_proxy | DEV+VAL only | 1419 | -0.208 | 1041 | -0.166 | -0.321 |
| unfavourable_rr | no | 1419 | -0.208 | 1158 | -0.232 | -0.101 |
| target_too_close | no | 1419 | -0.208 | 1284 | -0.226 | -0.028 |
| stop_too_large | no | 1419 | -0.208 | 1069 | -0.245 | -0.093 |
| unclear_boundary | DEV only | 1419 | -0.208 | 288 | -0.173 | -0.216 |
| cost_gate | DEV+VAL+OOS | 1419 | -0.208 | 1226 | -0.148 | -0.585 |

Full per-period tables: `results/deliverables/12_no_trade_filters_*.csv`. What the data supports as NO-TRADE:

* **Impulse larger than 15 pre-impulse ATR** (exhausted move): removed trades average -0.40 to -0.54R; survives all three periods in every playbook.
* **Spread above 15% of the stop distance** (cost gate): survives for A and B2; removed trades average -0.36 / -0.59R.
* **Off-hours or volume below half the 20-bar average** (low liquidity): survives for B1, DEV+VAL for B2.
* **Asia session for breakout pullbacks** (win rate 20%) and the **New York afternoon for ping-pong** (-0.30R) are the worst sessions in every period.
* Filters that do **not** help: VAH/VAL proximity in any form (section 10), the news-slot proxy, the volatility percentile, range width, mid-range entry, touches count.

## 10. Gold-specific adaptations (one variable at a time)

All tables: DEV / VAL / OOS rows, realistic costs. Full CSVs in `results/deliverables/11_experiment_*.csv`.

**Impulse definition (Part 3A).** Four definitions, none positive anywhere; the percentile and range-expansion
definitions produce fewer, longer trades with the same sign.

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| imp_def=atr | A_pingpong | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | 0.900 |
| imp_def=atr | A_pingpong | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | 1.000 |
| imp_def=atr | A_pingpong | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 0.900 |
| imp_def=atr | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| imp_def=atr | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| imp_def=atr | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| imp_def=pct | A_pingpong | DEV | 293 | 0.324 | -0.313 | 0.574 | -91.682 | -94.325 | 1.667 |
| imp_def=pct | A_pingpong | VAL | 127 | 0.386 | -0.126 | 0.802 | -15.951 | -25.322 | 1.767 |
| imp_def=pct | A_pingpong | OOS | 180 | 0.361 | -0.083 | 0.877 | -14.864 | -25.887 | 1.342 |
| imp_def=pct | B1_pullback | DEV | 176 | 0.199 | -0.267 | 0.692 | -47.042 | -63.831 | 1.808 |
| imp_def=pct | B1_pullback | VAL | 72 | 0.236 | -0.111 | 0.868 | -8.020 | -17.997 | 2.217 |
| imp_def=pct | B1_pullback | OOS | 100 | 0.200 | -0.424 | 0.528 | -42.403 | -47.394 | 1.133 |
| imp_def=rangeexp | A_pingpong | DEV | 347 | 0.329 | -0.284 | 0.609 | -98.689 | -101.810 | 1.483 |
| imp_def=rangeexp | A_pingpong | VAL | 122 | 0.361 | -0.152 | 0.764 | -18.589 | -28.379 | 1.825 |
| imp_def=rangeexp | A_pingpong | OOS | 168 | 0.363 | -0.027 | 0.960 | -4.539 | -17.017 | 1.267 |
| imp_def=rangeexp | B1_pullback | DEV | 198 | 0.222 | -0.206 | 0.755 | -40.799 | -55.500 | 1.658 |
| imp_def=rangeexp | B1_pullback | VAL | 73 | 0.233 | -0.113 | 0.860 | -8.246 | -20.352 | 2.117 |
| imp_def=rangeexp | B1_pullback | OOS | 97 | 0.175 | -0.516 | 0.441 | -50.049 | -56.052 | 1.167 |
| imp_def=consec | A_pingpong | DEV | 595 | 0.380 | -0.240 | 0.650 | -142.732 | -147.514 | 0.800 |
| imp_def=consec | A_pingpong | VAL | 270 | 0.370 | -0.164 | 0.747 | -44.286 | -52.880 | 1.042 |
| imp_def=consec | A_pingpong | OOS | 353 | 0.343 | -0.175 | 0.740 | -61.808 | -69.553 | 0.867 |
| imp_def=consec | B1_pullback | DEV | 343 | 0.248 | -0.374 | 0.550 | -128.242 | -132.256 | 0.867 |
| imp_def=consec | B1_pullback | VAL | 160 | 0.269 | -0.291 | 0.640 | -46.513 | -50.165 | 1.000 |
| imp_def=consec | B1_pullback | OOS | 219 | 0.324 | -0.184 | 0.738 | -40.294 | -41.331 | 0.833 |

**Impulse threshold and window:** see `11_experiment_impulse_k.csv` and `11_experiment_impulse_N.csv` (k 2.5-5.0 and N 4-16 all negative; k = 5 gives VAL -0.01R for ping-pong on 226 trades and DEV -0.29R).

**Experiment 1 - stop methodology.** Monotone: wider stops lose less, never gain. The 0.25-ATR stop is destroyed by
slippage and gaps on stops of a few cents (DEV -1.9R per trade). Win rate reaches 56-60% at 2 ATR, matching the source's
claim, while expectancy stays negative.

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| pp_stop_atr=0.25 | A_pingpong | DEV | 867 | 0.308 | -1.895 | 0.192 | -1643.371 | -1647.518 | 0.683 |
| pp_stop_atr=0.25 | A_pingpong | VAL | 406 | 0.323 | -0.199 | 0.724 | -80.603 | -91.694 | 0.733 |
| pp_stop_atr=0.25 | A_pingpong | OOS | 535 | 0.303 | -0.192 | 0.743 | -102.505 | -116.863 | 0.633 |
| pp_stop_atr=0.5 | A_pingpong | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | 0.900 |
| pp_stop_atr=0.5 | A_pingpong | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | 1.000 |
| pp_stop_atr=0.5 | A_pingpong | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 0.900 |
| pp_stop_atr=1.0 | A_pingpong | DEV | 732 | 0.432 | -0.219 | 0.631 | -160.563 | -168.459 | 1.433 |
| pp_stop_atr=1.0 | A_pingpong | VAL | 342 | 0.453 | -0.159 | 0.727 | -54.435 | -57.345 | 1.517 |
| pp_stop_atr=1.0 | A_pingpong | OOS | 449 | 0.428 | -0.157 | 0.740 | -70.490 | -71.207 | 1.383 |
| pp_stop_atr=1.5 | A_pingpong | DEV | 705 | 0.498 | -0.177 | 0.658 | -124.586 | -130.109 | 2.000 |
| pp_stop_atr=1.5 | A_pingpong | VAL | 336 | 0.539 | -0.071 | 0.848 | -23.707 | -25.371 | 1.992 |
| pp_stop_atr=1.5 | A_pingpong | OOS | 434 | 0.509 | -0.082 | 0.839 | -35.661 | -36.234 | 2.050 |
| pp_stop_atr=2.0 | A_pingpong | DEV | 693 | 0.560 | -0.130 | 0.705 | -90.427 | -96.328 | 2.483 |
| pp_stop_atr=2.0 | A_pingpong | VAL | 329 | 0.605 | -0.023 | 0.941 | -7.601 | -17.186 | 2.333 |
| pp_stop_atr=2.0 | A_pingpong | OOS | 429 | 0.562 | -0.078 | 0.827 | -33.633 | -35.959 | 2.450 |

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| bo_stop_atr=0.25 | B1_pullback | DEV | 454 | 0.225 | -0.319 | 0.624 | -145.039 | -153.871 | 0.567 |
| bo_stop_atr=0.25 | B1_pullback | VAL | 210 | 0.214 | -0.318 | 0.623 | -66.800 | -74.172 | 0.592 |
| bo_stop_atr=0.25 | B1_pullback | OOS | 279 | 0.237 | -0.317 | 0.603 | -88.422 | -89.253 | 0.567 |
| bo_stop_atr=0.5 | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| bo_stop_atr=0.5 | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| bo_stop_atr=0.5 | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| bo_stop_atr=1.0 | B1_pullback | DEV | 450 | 0.362 | -0.099 | 0.852 | -44.638 | -62.490 | 1.883 |
| bo_stop_atr=1.0 | B1_pullback | VAL | 209 | 0.344 | -0.164 | 0.763 | -34.234 | -48.642 | 1.833 |
| bo_stop_atr=1.0 | B1_pullback | OOS | 273 | 0.359 | -0.122 | 0.817 | -33.385 | -40.847 | 1.817 |
| bo_stop_atr=1.5 | B1_pullback | DEV | 441 | 0.422 | -0.067 | 0.889 | -29.372 | -54.538 | 2.750 |
| bo_stop_atr=1.5 | B1_pullback | VAL | 205 | 0.405 | -0.106 | 0.829 | -21.666 | -33.692 | 2.600 |
| bo_stop_atr=1.5 | B1_pullback | OOS | 270 | 0.411 | -0.086 | 0.859 | -23.166 | -36.088 | 2.617 |

**Experiment 2 - range definition.** Shorter confirmation windows (4 bars) are less bad for ping-pong in every period and
turn B1 positive in OOS only (DEV worse), so they are not robust. Longer windows (12-24 bars, closer to the source's
multi-hour boxes) are worse everywhere.

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| rng_min_bars=4 | A_pingpong | DEV | 1017 | 0.425 | -0.171 | 0.719 | -174.351 | -186.222 | 0.600 |
| rng_min_bars=4 | A_pingpong | VAL | 495 | 0.426 | -0.083 | 0.862 | -41.236 | -45.248 | 0.617 |
| rng_min_bars=4 | A_pingpong | OOS | 608 | 0.436 | -0.035 | 0.939 | -21.419 | -58.932 | 0.733 |
| rng_min_bars=4 | B1_pullback | DEV | 581 | 0.318 | -0.254 | 0.659 | -147.488 | -148.287 | 0.883 |
| rng_min_bars=4 | B1_pullback | VAL | 308 | 0.331 | -0.116 | 0.835 | -35.872 | -44.006 | 0.992 |
| rng_min_bars=4 | B1_pullback | OOS | 374 | 0.353 | 0.122 | 1.184 | 45.642 | -29.199 | 1.008 |
| rng_min_bars=8 | A_pingpong | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | 0.900 |
| rng_min_bars=8 | A_pingpong | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | 1.000 |
| rng_min_bars=8 | A_pingpong | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 0.900 |
| rng_min_bars=8 | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| rng_min_bars=8 | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| rng_min_bars=8 | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| rng_min_bars=12 | A_pingpong | DEV | 628 | 0.320 | -0.311 | 0.578 | -195.030 | -197.687 | 1.217 |
| rng_min_bars=12 | A_pingpong | VAL | 286 | 0.311 | -0.239 | 0.669 | -68.364 | -71.021 | 1.175 |
| rng_min_bars=12 | A_pingpong | OOS | 379 | 0.309 | -0.221 | 0.694 | -83.838 | -83.847 | 1.167 |
| rng_min_bars=12 | B1_pullback | DEV | 365 | 0.233 | -0.288 | 0.651 | -105.096 | -112.566 | 1.100 |
| rng_min_bars=12 | B1_pullback | VAL | 178 | 0.230 | -0.376 | 0.544 | -66.992 | -72.409 | 0.992 |
| rng_min_bars=12 | B1_pullback | OOS | 231 | 0.268 | -0.085 | 0.890 | -19.601 | -34.478 | 1.067 |
| rng_min_bars=16 | A_pingpong | DEV | 496 | 0.308 | -0.318 | 0.572 | -157.633 | -162.696 | 1.425 |
| rng_min_bars=16 | A_pingpong | VAL | 224 | 0.304 | -0.193 | 0.734 | -43.325 | -44.513 | 1.533 |
| rng_min_bars=16 | A_pingpong | OOS | 326 | 0.319 | -0.185 | 0.741 | -60.281 | -68.697 | 1.275 |
| rng_min_bars=16 | B1_pullback | DEV | 298 | 0.211 | -0.338 | 0.609 | -100.796 | -109.294 | 1.167 |
| rng_min_bars=16 | B1_pullback | VAL | 139 | 0.216 | -0.358 | 0.571 | -49.753 | -54.127 | 1.017 |
| rng_min_bars=16 | B1_pullback | OOS | 200 | 0.240 | -0.185 | 0.781 | -36.967 | -47.466 | 1.075 |
| rng_min_bars=24 | A_pingpong | DEV | 319 | 0.276 | -0.327 | 0.582 | -104.190 | -109.799 | 1.600 |
| rng_min_bars=24 | A_pingpong | VAL | 149 | 0.275 | -0.262 | 0.653 | -39.065 | -42.335 | 1.400 |
| rng_min_bars=24 | A_pingpong | OOS | 200 | 0.315 | -0.177 | 0.754 | -35.345 | -45.980 | 1.175 |
| rng_min_bars=24 | B1_pullback | DEV | 193 | 0.181 | -0.341 | 0.610 | -65.762 | -72.398 | 1.050 |
| rng_min_bars=24 | B1_pullback | VAL | 75 | 0.253 | -0.099 | 0.871 | -7.411 | -30.144 | 0.883 |
| rng_min_bars=24 | B1_pullback | OOS | 123 | 0.252 | -0.255 | 0.685 | -31.397 | -35.950 | 1.217 |

**Experiment 3 - session filter.** The London/New York overlap is the least bad window for every playbook; ping-pong
in the overlap is positive in VAL (+0.03R) and OOS (+0.07R) on 65 and 91 trades, negative in DEV (-0.22R).

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| A_all_sessions | A_pingpong | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | 0.900 |
| A_all_sessions | A_pingpong | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | 1.000 |
| A_all_sessions | A_pingpong | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 0.900 |
| A_all_sessions | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| A_all_sessions | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| A_all_sessions | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| B_london_only | A_pingpong | DEV | 196 | 0.357 | -0.260 | 0.618 | -50.947 | -58.634 | 0.667 |
| B_london_only | A_pingpong | VAL | 105 | 0.343 | -0.162 | 0.761 | -17.023 | -25.778 | 0.800 |
| B_london_only | A_pingpong | OOS | 119 | 0.378 | -0.161 | 0.745 | -19.135 | -23.406 | 0.983 |
| B_london_only | B1_pullback | DEV | 103 | 0.340 | -0.061 | 0.915 | -6.259 | -22.263 | 0.633 |
| B_london_only | B1_pullback | VAL | 43 | 0.233 | -0.367 | 0.540 | -15.783 | -22.921 | 0.683 |
| B_london_only | B1_pullback | OOS | 61 | 0.311 | -0.270 | 0.655 | -16.462 | -18.217 | 0.850 |
| C_newyork_only | A_pingpong | DEV | 276 | 0.304 | -0.368 | 0.527 | -101.456 | -103.032 | 2.242 |
| C_newyork_only | A_pingpong | VAL | 129 | 0.333 | -0.226 | 0.671 | -29.175 | -36.545 | 2.317 |
| C_newyork_only | A_pingpong | OOS | 154 | 0.325 | -0.214 | 0.727 | -32.988 | -34.629 | 1.742 |
| C_newyork_only | B1_pullback | DEV | 105 | 0.257 | -0.222 | 0.733 | -23.327 | -34.806 | 2.500 |
| C_newyork_only | B1_pullback | VAL | 43 | 0.186 | -0.525 | 0.467 | -22.592 | -25.046 | 3.383 |
| C_newyork_only | B1_pullback | OOS | 55 | 0.273 | -0.365 | 0.544 | -20.096 | -21.609 | 1.350 |
| D_london_plus_ny | A_pingpong | DEV | 560 | 0.343 | -0.305 | 0.572 | -170.934 | -178.424 | 0.983 |
| D_london_plus_ny | A_pingpong | VAL | 277 | 0.365 | -0.135 | 0.794 | -37.395 | -50.273 | 1.067 |
| D_london_plus_ny | A_pingpong | OOS | 333 | 0.354 | -0.144 | 0.794 | -47.983 | -51.375 | 1.083 |
| D_london_plus_ny | B1_pullback | DEV | 285 | 0.340 | -0.149 | 0.800 | -42.364 | -54.462 | 0.883 |
| D_london_plus_ny | B1_pullback | VAL | 135 | 0.289 | -0.363 | 0.535 | -48.983 | -56.531 | 1.017 |
| D_london_plus_ny | B1_pullback | OOS | 158 | 0.304 | -0.311 | 0.591 | -49.152 | -52.527 | 0.892 |
| E_overlap_only | A_pingpong | DEV | 139 | 0.396 | -0.223 | 0.649 | -30.947 | -33.067 | 0.283 |
| E_overlap_only | A_pingpong | VAL | 65 | 0.462 | 0.033 | 1.060 | 2.170 | -16.130 | 0.367 |
| E_overlap_only | A_pingpong | OOS | 91 | 0.396 | 0.073 | 1.120 | 6.683 | -14.909 | 0.383 |
| E_overlap_only | B1_pullback | DEV | 78 | 0.462 | -0.114 | 0.826 | -8.894 | -18.209 | 0.425 |
| E_overlap_only | B1_pullback | VAL | 50 | 0.420 | -0.241 | 0.600 | -12.043 | -12.453 | 0.350 |
| E_overlap_only | B1_pullback | OOS | 45 | 0.378 | -0.161 | 0.745 | -7.239 | -11.693 | 0.500 |
| F_asia_only | A_pingpong | DEV | 291 | 0.361 | -0.252 | 0.634 | -73.249 | -75.162 | 0.833 |
| F_asia_only | A_pingpong | VAL | 126 | 0.365 | -0.246 | 0.639 | -30.996 | -33.155 | 0.783 |
| F_asia_only | A_pingpong | OOS | 175 | 0.337 | -0.194 | 0.712 | -33.884 | -41.517 | 0.733 |
| F_asia_only | B1_pullback | DEV | 154 | 0.188 | -0.217 | 0.748 | -33.490 | -53.060 | 1.150 |
| F_asia_only | B1_pullback | VAL | 64 | 0.172 | -0.278 | 0.679 | -17.770 | -23.065 | 0.900 |
| F_asia_only | B1_pullback | OOS | 93 | 0.226 | -0.312 | 0.605 | -28.978 | -38.175 | 0.967 |
| G_no_offhours | A_pingpong | DEV | 771 | 0.358 | -0.279 | 0.601 | -214.735 | -223.634 | 0.867 |
| G_no_offhours | A_pingpong | VAL | 363 | 0.375 | -0.157 | 0.757 | -57.027 | -63.874 | 0.917 |
| G_no_offhours | A_pingpong | OOS | 468 | 0.357 | -0.142 | 0.793 | -66.523 | -70.418 | 0.883 |
| G_no_offhours | B1_pullback | DEV | 435 | 0.290 | -0.165 | 0.790 | -71.648 | -94.837 | 1.000 |
| G_no_offhours | B1_pullback | VAL | 195 | 0.256 | -0.321 | 0.600 | -62.565 | -70.113 | 1.000 |
| G_no_offhours | B1_pullback | OOS | 250 | 0.272 | -0.314 | 0.594 | -78.473 | -86.955 | 0.925 |

**Experiment 4 - volatility filter.** No band improves all three periods.

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| no_filter | A_pingpong | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | 0.900 |
| no_filter | A_pingpong | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | 1.000 |
| no_filter | A_pingpong | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 0.900 |
| no_filter | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| no_filter | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| no_filter | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| atr_pct<0.9 | A_pingpong | DEV | 722 | 0.348 | -0.305 | 0.571 | -220.200 | -226.484 | 0.925 |
| atr_pct<0.9 | A_pingpong | VAL | 323 | 0.387 | -0.145 | 0.774 | -46.869 | -47.475 | 0.917 |
| atr_pct<0.9 | A_pingpong | OOS | 420 | 0.362 | -0.190 | 0.723 | -79.732 | -85.932 | 0.892 |
| atr_pct<0.9 | B1_pullback | DEV | 412 | 0.265 | -0.241 | 0.703 | -99.298 | -106.680 | 1.050 |
| atr_pct<0.9 | B1_pullback | VAL | 191 | 0.230 | -0.338 | 0.594 | -64.577 | -70.662 | 1.100 |
| atr_pct<0.9 | B1_pullback | OOS | 239 | 0.276 | -0.266 | 0.650 | -63.590 | -67.086 | 0.900 |
| atr_pct<0.8 | A_pingpong | DEV | 634 | 0.349 | -0.303 | 0.575 | -192.178 | -194.217 | 0.983 |
| atr_pct<0.8 | A_pingpong | VAL | 288 | 0.382 | -0.182 | 0.722 | -52.300 | -52.300 | 0.900 |
| atr_pct<0.8 | A_pingpong | OOS | 362 | 0.370 | -0.181 | 0.735 | -65.460 | -74.387 | 0.892 |
| atr_pct<0.8 | B1_pullback | DEV | 357 | 0.258 | -0.251 | 0.693 | -89.749 | -96.182 | 1.033 |
| atr_pct<0.8 | B1_pullback | VAL | 162 | 0.222 | -0.386 | 0.542 | -62.562 | -68.647 | 0.950 |
| atr_pct<0.8 | B1_pullback | OOS | 203 | 0.291 | -0.200 | 0.724 | -40.579 | -53.800 | 0.833 |
| atr_pct>0.2 | A_pingpong | DEV | 681 | 0.345 | -0.293 | 0.589 | -199.244 | -205.959 | 0.983 |
| atr_pct>0.2 | A_pingpong | VAL | 332 | 0.373 | -0.132 | 0.796 | -43.746 | -50.593 | 1.058 |
| atr_pct>0.2 | A_pingpong | OOS | 417 | 0.376 | -0.097 | 0.850 | -40.553 | -46.272 | 0.900 |
| atr_pct>0.2 | B1_pullback | DEV | 369 | 0.290 | -0.221 | 0.719 | -81.365 | -85.377 | 1.033 |
| atr_pct>0.2 | B1_pullback | VAL | 182 | 0.275 | -0.233 | 0.703 | -42.321 | -48.816 | 1.258 |
| atr_pct>0.2 | B1_pullback | OOS | 229 | 0.293 | -0.224 | 0.703 | -51.336 | -60.140 | 1.000 |
| 0.2<atr_pct<0.8 | A_pingpong | DEV | 517 | 0.342 | -0.306 | 0.578 | -157.960 | -159.999 | 1.050 |
| 0.2<atr_pct<0.8 | A_pingpong | VAL | 247 | 0.389 | -0.139 | 0.782 | -34.309 | -34.309 | 0.950 |
| 0.2<atr_pct<0.8 | A_pingpong | OOS | 289 | 0.394 | -0.132 | 0.795 | -38.078 | -48.752 | 0.883 |
| 0.2<atr_pct<0.8 | B1_pullback | DEV | 278 | 0.266 | -0.278 | 0.659 | -77.257 | -80.952 | 1.017 |
| 0.2<atr_pct<0.8 | B1_pullback | VAL | 132 | 0.250 | -0.301 | 0.633 | -39.681 | -45.766 | 1.017 |
| 0.2<atr_pct<0.8 | B1_pullback | OOS | 154 | 0.325 | -0.096 | 0.861 | -14.744 | -32.159 | 0.825 |

**Experiment 5 - breakout confirmation.** Requiring both a large bar (>= 1.5 ATR) and volume (>= 1.5x) on the breakout
raises the win rate of B2 to 39-52% and makes VAL/OOS positive (+0.09 / +0.06R) with DEV still negative (-0.20R).
Penetration of 1.0 ATR has the same profile. For B1 no confirmation variant is positive anywhere.

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| bo_conf=close | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| bo_conf=close | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| bo_conf=close | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| bo_conf=close | B2_immediate | DEV | 668 | 0.287 | -0.269 | 0.645 | -179.747 | -183.663 | 0.767 |
| bo_conf=close | B2_immediate | VAL | 314 | 0.290 | -0.219 | 0.713 | -68.743 | -77.182 | 0.817 |
| bo_conf=close | B2_immediate | OOS | 437 | 0.332 | -0.105 | 0.850 | -45.974 | -61.018 | 0.800 |
| bo_conf=bigbar | B1_pullback | DEV | 307 | 0.293 | -0.159 | 0.786 | -48.796 | -51.972 | 0.833 |
| bo_conf=bigbar | B1_pullback | VAL | 151 | 0.325 | -0.238 | 0.674 | -35.950 | -51.920 | 0.683 |
| bo_conf=bigbar | B1_pullback | OOS | 203 | 0.291 | -0.286 | 0.606 | -57.998 | -63.973 | 0.783 |
| bo_conf=bigbar | B2_immediate | DEV | 523 | 0.348 | -0.266 | 0.609 | -139.162 | -139.162 | 0.817 |
| bo_conf=bigbar | B2_immediate | VAL | 264 | 0.402 | -0.095 | 0.847 | -24.976 | -49.133 | 0.833 |
| bo_conf=bigbar | B2_immediate | OOS | 342 | 0.468 | 0.031 | 1.056 | 10.432 | -25.408 | 0.875 |
| bo_conf=volume | B1_pullback | DEV | 309 | 0.288 | -0.265 | 0.649 | -81.955 | -86.503 | 0.600 |
| bo_conf=volume | B1_pullback | VAL | 151 | 0.311 | -0.170 | 0.764 | -25.621 | -27.979 | 0.617 |
| bo_conf=volume | B1_pullback | OOS | 175 | 0.280 | -0.265 | 0.637 | -46.410 | -60.821 | 0.750 |
| bo_conf=volume | B2_immediate | DEV | 517 | 0.346 | -0.213 | 0.687 | -110.268 | -119.286 | 0.700 |
| bo_conf=volume | B2_immediate | VAL | 262 | 0.424 | -0.040 | 0.933 | -10.405 | -22.552 | 0.742 |
| bo_conf=volume | B2_immediate | OOS | 318 | 0.462 | 0.037 | 1.067 | 11.832 | -34.527 | 0.900 |
| bo_conf=both | B1_pullback | DEV | 228 | 0.285 | -0.226 | 0.699 | -51.636 | -57.278 | 0.742 |
| bo_conf=both | B1_pullback | VAL | 111 | 0.414 | -0.106 | 0.839 | -11.796 | -30.864 | 0.650 |
| bo_conf=both | B1_pullback | OOS | 148 | 0.284 | -0.252 | 0.653 | -37.354 | -43.623 | 0.650 |
| bo_conf=both | B2_immediate | DEV | 409 | 0.389 | -0.203 | 0.679 | -83.103 | -88.981 | 0.750 |
| bo_conf=both | B2_immediate | VAL | 205 | 0.512 | 0.088 | 1.174 | 18.136 | -17.130 | 0.617 |
| bo_conf=both | B2_immediate | OOS | 261 | 0.517 | 0.062 | 1.127 | 16.191 | -26.757 | 0.783 |

| variant | playbook | period | n | win_rate | expectancy | pf | total_r | max_dd_r | median_hold_h |
|---|---|---|---|---|---|---|---|---|---|
| bo_pen_atr=0.0 | B1_pullback | DEV | 500 | 0.278 | -0.244 | 0.691 | -122.036 | -135.111 | 1.050 |
| bo_pen_atr=0.0 | B1_pullback | VAL | 234 | 0.252 | -0.309 | 0.609 | -72.320 | -85.772 | 1.017 |
| bo_pen_atr=0.0 | B1_pullback | OOS | 326 | 0.294 | -0.101 | 0.861 | -32.817 | -70.607 | 1.158 |
| bo_pen_atr=0.0 | B2_immediate | DEV | 780 | 0.227 | -0.331 | 0.612 | -258.331 | -260.713 | 0.567 |
| bo_pen_atr=0.0 | B2_immediate | VAL | 339 | 0.251 | -0.209 | 0.740 | -71.011 | -80.023 | 0.683 |
| bo_pen_atr=0.0 | B2_immediate | OOS | 489 | 0.260 | -0.020 | 0.974 | -9.805 | -69.433 | 0.700 |
| bo_pen_atr=0.25 | B1_pullback | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | 1.050 |
| bo_pen_atr=0.25 | B1_pullback | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | 1.217 |
| bo_pen_atr=0.25 | B1_pullback | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 0.992 |
| bo_pen_atr=0.25 | B2_immediate | DEV | 668 | 0.287 | -0.269 | 0.645 | -179.747 | -183.663 | 0.767 |
| bo_pen_atr=0.25 | B2_immediate | VAL | 314 | 0.290 | -0.219 | 0.713 | -68.743 | -77.182 | 0.817 |
| bo_pen_atr=0.25 | B2_immediate | OOS | 437 | 0.332 | -0.105 | 0.850 | -45.974 | -61.018 | 0.800 |
| bo_pen_atr=0.5 | B1_pullback | DEV | 412 | 0.284 | -0.157 | 0.801 | -64.728 | -74.581 | 0.867 |
| bo_pen_atr=0.5 | B1_pullback | VAL | 180 | 0.289 | -0.194 | 0.744 | -34.894 | -49.825 | 0.867 |
| bo_pen_atr=0.5 | B1_pullback | OOS | 237 | 0.249 | -0.340 | 0.564 | -80.653 | -87.814 | 0.850 |
| bo_pen_atr=0.5 | B2_immediate | DEV | 610 | 0.334 | -0.240 | 0.656 | -146.640 | -149.187 | 0.992 |
| bo_pen_atr=0.5 | B2_immediate | VAL | 281 | 0.356 | -0.157 | 0.771 | -44.043 | -51.933 | 1.133 |
| bo_pen_atr=0.5 | B2_immediate | OOS | 381 | 0.407 | -0.014 | 0.978 | -5.264 | -26.232 | 1.100 |
| bo_pen_atr=1.0 | B1_pullback | DEV | 298 | 0.272 | -0.236 | 0.699 | -70.388 | -71.032 | 0.658 |
| bo_pen_atr=1.0 | B1_pullback | VAL | 122 | 0.238 | -0.301 | 0.644 | -36.674 | -58.207 | 0.633 |
| bo_pen_atr=1.0 | B1_pullback | OOS | 185 | 0.222 | -0.363 | 0.541 | -67.115 | -70.778 | 0.783 |
| bo_pen_atr=1.0 | B2_immediate | DEV | 477 | 0.421 | -0.152 | 0.746 | -72.472 | -74.059 | 1.367 |
| bo_pen_atr=1.0 | B2_immediate | VAL | 235 | 0.485 | -0.080 | 0.851 | -18.854 | -29.477 | 1.283 |
| bo_pen_atr=1.0 | B2_immediate | OOS | 319 | 0.498 | -0.021 | 0.959 | -6.600 | -35.383 | 1.333 |

**Pullback depth / window, ping-pong target and zone, max hold:** `11_experiment_pullback_depth.csv`, `..._pullback_window.csv`,
`..._target_pingpong.csv`, `..._zone_pingpong.csv`, `..._max_hold.csv`. None changes the sign.

**VAH/VAL proximity and volume source.** Requiring the traded boundary to be within 1 or 2 ATR of the previous week's
VAH or VAL makes results worse for every volume source; the developing current-week VA is the least bad variant and still
negative. Level differences between sources are small (Dukascopy vs tick VAH: 1.00 USD median), so the volume
source is not the reason.

| playbook | variant | period | n | expectancy | pf |
|---|---|---|---|---|---|
| A_pingpong | no_filter | DEV | 800 | -0.289 | 0.588 |
| A_pingpong | no_filter | VAL | 371 | -0.156 | 0.760 |
| A_pingpong | no_filter | OOS | 490 | -0.139 | 0.796 |
| A_pingpong | duka_prev_week_within_1.0ATR | DEV | 103 | -0.173 | 0.740 |
| A_pingpong | duka_prev_week_within_1.0ATR | VAL | 45 | -0.582 | 0.297 |
| A_pingpong | duka_prev_week_within_1.0ATR | OOS | 45 | -0.137 | 0.791 |
| A_pingpong | duka_prev_week_within_2.0ATR | DEV | 184 | -0.250 | 0.636 |
| A_pingpong | duka_prev_week_within_2.0ATR | VAL | 90 | -0.244 | 0.645 |
| A_pingpong | duka_prev_week_within_2.0ATR | OOS | 100 | -0.303 | 0.601 |
| A_pingpong | tick_prev_week_within_1.0ATR | DEV | 56 | -0.155 | 0.761 |
| A_pingpong | tick_prev_week_within_1.0ATR | VAL | 45 | -0.548 | 0.320 |
| A_pingpong | tick_prev_week_within_1.0ATR | OOS | 50 | -0.218 | 0.666 |
| A_pingpong | tick_prev_week_within_2.0ATR | DEV | 104 | -0.334 | 0.548 |
| A_pingpong | tick_prev_week_within_2.0ATR | VAL | 89 | -0.154 | 0.767 |
| A_pingpong | tick_prev_week_within_2.0ATR | OOS | 94 | -0.297 | 0.599 |
| A_pingpong | tpo_prev_week_within_1.0ATR | DEV | 95 | -0.294 | 0.579 |
| A_pingpong | tpo_prev_week_within_1.0ATR | VAL | 50 | -0.292 | 0.575 |
| A_pingpong | tpo_prev_week_within_1.0ATR | OOS | 64 | -0.297 | 0.604 |
| A_pingpong | tpo_prev_week_within_2.0ATR | DEV | 163 | -0.215 | 0.675 |
| A_pingpong | tpo_prev_week_within_2.0ATR | VAL | 83 | -0.221 | 0.683 |
| A_pingpong | tpo_prev_week_within_2.0ATR | OOS | 107 | -0.350 | 0.547 |
| A_pingpong | duka_developing_within_1.0ATR | DEV | 280 | -0.255 | 0.633 |
| A_pingpong | duka_developing_within_1.0ATR | VAL | 139 | -0.146 | 0.772 |
| A_pingpong | duka_developing_within_1.0ATR | OOS | 191 | -0.117 | 0.819 |
| A_pingpong | duka_developing_within_2.0ATR | DEV | 459 | -0.289 | 0.591 |
| A_pingpong | duka_developing_within_2.0ATR | VAL | 218 | -0.128 | 0.799 |
| A_pingpong | duka_developing_within_2.0ATR | OOS | 285 | -0.151 | 0.768 |
| B1_pullback | no_filter | DEV | 455 | -0.193 | 0.756 |
| B1_pullback | no_filter | VAL | 212 | -0.308 | 0.619 |
| B1_pullback | no_filter | OOS | 278 | -0.278 | 0.639 |
| B1_pullback | duka_prev_week_within_1.0ATR | DEV | 46 | -0.187 | 0.775 |
| B1_pullback | duka_prev_week_within_1.0ATR | VAL | 22 | -0.607 | 0.295 |
| B1_pullback | duka_prev_week_within_1.0ATR | OOS | 24 | -0.570 | 0.386 |
| B1_pullback | duka_prev_week_within_2.0ATR | DEV | 84 | -0.219 | 0.737 |
| B1_pullback | duka_prev_week_within_2.0ATR | VAL | 42 | -0.474 | 0.393 |
| B1_pullback | duka_prev_week_within_2.0ATR | OOS | 47 | -0.520 | 0.367 |
| B1_pullback | tick_prev_week_within_1.0ATR | DEV | 25 | -0.668 | 0.245 |
| B1_pullback | tick_prev_week_within_1.0ATR | VAL | 25 | -0.320 | 0.619 |
| B1_pullback | tick_prev_week_within_1.0ATR | OOS | 23 | -0.598 | 0.254 |
| B1_pullback | tick_prev_week_within_2.0ATR | DEV | 51 | -0.582 | 0.383 |
| B1_pullback | tick_prev_week_within_2.0ATR | VAL | 46 | -0.321 | 0.579 |
| B1_pullback | tick_prev_week_within_2.0ATR | OOS | 45 | -0.382 | 0.517 |
| B1_pullback | tpo_prev_week_within_1.0ATR | DEV | 43 | -0.071 | 0.929 |
| B1_pullback | tpo_prev_week_within_1.0ATR | VAL | 18 | -0.649 | 0.253 |
| B1_pullback | tpo_prev_week_within_1.0ATR | OOS | 26 | -0.418 | 0.491 |
| B1_pullback | tpo_prev_week_within_2.0ATR | DEV | 83 | -0.249 | 0.730 |
| B1_pullback | tpo_prev_week_within_2.0ATR | VAL | 37 | -0.496 | 0.383 |
| B1_pullback | tpo_prev_week_within_2.0ATR | OOS | 53 | -0.339 | 0.569 |
| B1_pullback | duka_developing_within_1.0ATR | DEV | 137 | -0.104 | 0.866 |
| B1_pullback | duka_developing_within_1.0ATR | VAL | 62 | -0.403 | 0.523 |
| B1_pullback | duka_developing_within_1.0ATR | OOS | 81 | -0.070 | 0.906 |
| B1_pullback | duka_developing_within_2.0ATR | DEV | 249 | -0.080 | 0.893 |
| B1_pullback | duka_developing_within_2.0ATR | VAL | 118 | -0.342 | 0.591 |
| B1_pullback | duka_developing_within_2.0ATR | OOS | 133 | -0.160 | 0.783 |

| pair | median_abs_diff_usd | median_abs_diff_atr |
|---|---|---|
| duka-tick VAH | 1.00 | 0.29 |
| duka-tick VAL | 1.25 | 0.34 |
| duka-tpo VAH | 2.28 | 0.63 |
| duka-tpo VAL | 2.30 | 0.63 |
| prev-week vs developing VAH (end of week) | 27.31 | 8.94 |

**Touch count (ping-pong):** `11_experiment_max_touches.csv`; fewer prior touches is marginally better, not a sign change.

## 11. Robustness tests

**Parameter grids** (`11_robustness_grid_*.csv`): impulse k x confirmation bars and stop x zone for A; impulse k x bars and
stop x pullback depth for B1. No cell is positive in DEV. The only positive cells are B1 with a 4-bar window in OOS
(+0.06 to +0.12R) and ping-pong with a 2-ATR stop in VAL (+0.002R). The least-bad region is broad and monotone
(wider stops, wider zones, shorter windows), which is the opposite of a knife-edge, but it is a region of smaller losses.

**Staged combination** (pre-specified, one change per stage, OOS read once at the end; `13_staged_adaptations.csv`):

Ping-pong:

| stage | label | cost | period | n | win_rate | expectancy | pf | total_r | max_dd_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | baseline | real | DEV | 800 | 0.352 | -0.289 | 0.588 | -231.518 | -238.824 | -0.370 | -0.210 |
| 0 | baseline | real | VAL | 371 | 0.372 | -0.156 | 0.760 | -57.804 | -64.651 | -0.281 | -0.016 |
| 0 | baseline | real | OOS | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | -0.266 | 0.000 |
| 0 | baseline | ideal | DEV | 808 | 0.374 | -0.087 | 0.863 | -70.040 | -86.872 | -0.170 | -0.004 |
| 0 | baseline | ideal | VAL | 377 | 0.395 | 0.027 | 1.044 | 10.141 | -25.188 | -0.109 | 0.174 |
| 0 | baseline | ideal | OOS | 502 | 0.367 | -0.069 | 0.896 | -34.590 | -45.777 | -0.210 | 0.068 |
| 1 | +stop 1.5 ATR | real | DEV | 705 | 0.498 | -0.177 | 0.658 | -124.586 | -130.109 | -0.236 | -0.111 |
| 1 | +stop 1.5 ATR | real | VAL | 336 | 0.539 | -0.071 | 0.848 | -23.707 | -25.371 | -0.167 | 0.022 |
| 1 | +stop 1.5 ATR | real | OOS | 434 | 0.509 | -0.082 | 0.839 | -35.661 | -36.234 | -0.184 | 0.017 |
| 1 | +stop 1.5 ATR | ideal | DEV | 726 | 0.519 | -0.077 | 0.839 | -56.093 | -73.618 | -0.145 | -0.008 |
| 1 | +stop 1.5 ATR | ideal | VAL | 343 | 0.566 | 0.033 | 1.075 | 11.222 | -13.478 | -0.067 | 0.132 |
| 1 | +stop 1.5 ATR | ideal | OOS | 443 | 0.521 | -0.049 | 0.900 | -21.860 | -24.112 | -0.145 | 0.040 |
| 2 | +overlap+london session | real | DEV | 276 | 0.500 | -0.172 | 0.666 | -47.374 | -54.321 | -0.274 | -0.063 |
| 2 | +overlap+london session | real | VAL | 138 | 0.572 | -0.002 | 0.995 | -0.323 | -7.540 | -0.163 | 0.150 |
| 2 | +overlap+london session | real | OOS | 171 | 0.515 | -0.118 | 0.759 | -20.184 | -22.667 | -0.260 | 0.022 |
| 2 | +overlap+london session | ideal | DEV | 281 | 0.523 | -0.077 | 0.839 | -21.619 | -33.198 | -0.184 | 0.028 |
| 2 | +overlap+london session | ideal | VAL | 142 | 0.585 | 0.064 | 1.153 | 9.022 | -6.236 | -0.083 | 0.221 |
| 2 | +overlap+london session | ideal | OOS | 173 | 0.532 | -0.061 | 0.870 | -10.519 | -15.634 | -0.200 | 0.070 |
| 3 | +cost gate spread<=15% stop | real | DEV | 276 | 0.500 | -0.172 | 0.666 | -47.374 | -54.321 | -0.274 | -0.063 |
| 3 | +cost gate spread<=15% stop | real | VAL | 138 | 0.572 | -0.002 | 0.995 | -0.323 | -7.540 | -0.163 | 0.150 |
| 3 | +cost gate spread<=15% stop | real | OOS | 171 | 0.515 | -0.118 | 0.759 | -20.184 | -22.667 | -0.260 | 0.022 |
| 3 | +cost gate spread<=15% stop | ideal | DEV | 281 | 0.523 | -0.077 | 0.839 | -21.619 | -33.198 | -0.184 | 0.028 |
| 3 | +cost gate spread<=15% stop | ideal | VAL | 142 | 0.585 | 0.064 | 1.153 | 9.022 | -6.236 | -0.083 | 0.221 |
| 3 | +cost gate spread<=15% stop | ideal | OOS | 173 | 0.532 | -0.061 | 0.870 | -10.519 | -15.634 | -0.200 | 0.070 |
| 4 | +impulse <= 15 ATR | real | DEV | 251 | 0.502 | -0.181 | 0.647 | -45.325 | -49.526 | -0.296 | -0.071 |
| 4 | +impulse <= 15 ATR | real | VAL | 127 | 0.598 | 0.034 | 1.083 | 4.290 | -6.867 | -0.123 | 0.195 |
| 4 | +impulse <= 15 ATR | real | OOS | 155 | 0.503 | -0.142 | 0.717 | -21.986 | -22.683 | -0.286 | 0.000 |
| 4 | +impulse <= 15 ATR | ideal | DEV | 256 | 0.527 | -0.074 | 0.843 | -18.987 | -26.911 | -0.187 | 0.032 |
| 4 | +impulse <= 15 ATR | ideal | VAL | 131 | 0.611 | 0.105 | 1.270 | 13.745 | -4.732 | -0.060 | 0.256 |
| 4 | +impulse <= 15 ATR | ideal | OOS | 157 | 0.522 | -0.087 | 0.818 | -13.640 | -16.388 | -0.224 | 0.046 |

Breakout + pullback:

| stage | label | cost | period | n | win_rate | expectancy | pf | total_r | max_dd_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | baseline | real | DEV | 455 | 0.281 | -0.193 | 0.756 | -87.801 | -102.718 | -0.362 | -0.021 |
| 0 | baseline | real | VAL | 212 | 0.250 | -0.308 | 0.619 | -65.202 | -71.697 | -0.510 | -0.098 |
| 0 | baseline | real | OOS | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | -0.461 | -0.092 |
| 0 | baseline | ideal | DEV | 463 | 0.309 | 0.006 | 1.009 | 2.910 | -54.088 | -0.165 | 0.183 |
| 0 | baseline | ideal | VAL | 215 | 0.260 | -0.145 | 0.808 | -31.129 | -39.637 | -0.388 | 0.096 |
| 0 | baseline | ideal | OOS | 282 | 0.287 | -0.155 | 0.790 | -43.716 | -53.759 | -0.343 | 0.037 |
| 1 | +stop 1.5 ATR | real | DEV | 441 | 0.422 | -0.067 | 0.889 | -29.372 | -54.538 | -0.188 | 0.059 |
| 1 | +stop 1.5 ATR | real | VAL | 205 | 0.405 | -0.106 | 0.829 | -21.666 | -33.692 | -0.283 | 0.072 |
| 1 | +stop 1.5 ATR | real | OOS | 270 | 0.411 | -0.086 | 0.859 | -23.166 | -36.088 | -0.246 | 0.073 |
| 1 | +stop 1.5 ATR | ideal | DEV | 449 | 0.443 | 0.040 | 1.072 | 17.940 | -23.247 | -0.083 | 0.173 |
| 1 | +stop 1.5 ATR | ideal | VAL | 208 | 0.404 | -0.058 | 0.903 | -12.061 | -28.485 | -0.224 | 0.115 |
| 1 | +stop 1.5 ATR | ideal | OOS | 273 | 0.418 | -0.047 | 0.921 | -12.823 | -28.388 | -0.204 | 0.116 |
| 2 | +breakout conf: big bar AND volume | real | DEV | 224 | 0.433 | -0.121 | 0.792 | -27.202 | -43.303 | -0.271 | 0.037 |
| 2 | +breakout conf: big bar AND volume | real | VAL | 111 | 0.532 | 0.016 | 1.032 | 1.729 | -16.530 | -0.197 | 0.218 |
| 2 | +breakout conf: big bar AND volume | real | OOS | 146 | 0.418 | -0.151 | 0.744 | -21.995 | -32.588 | -0.337 | 0.036 |
| 2 | +breakout conf: big bar AND volume | ideal | DEV | 228 | 0.443 | -0.051 | 0.908 | -11.677 | -32.260 | -0.206 | 0.122 |
| 2 | +breakout conf: big bar AND volume | ideal | VAL | 110 | 0.536 | 0.084 | 1.180 | 9.191 | -13.413 | -0.134 | 0.299 |
| 2 | +breakout conf: big bar AND volume | ideal | OOS | 147 | 0.422 | -0.133 | 0.771 | -19.536 | -30.469 | -0.314 | 0.057 |
| 3 | +no offhours / low volume | real | DEV | 219 | 0.434 | -0.118 | 0.798 | -25.837 | -42.972 | -0.286 | 0.040 |
| 3 | +no offhours / low volume | real | VAL | 105 | 0.533 | 0.011 | 1.022 | 1.110 | -17.149 | -0.191 | 0.227 |
| 3 | +no offhours / low volume | real | OOS | 143 | 0.427 | -0.133 | 0.771 | -18.975 | -29.569 | -0.331 | 0.068 |
| 3 | +no offhours / low volume | ideal | DEV | 223 | 0.444 | -0.049 | 0.913 | -10.822 | -33.405 | -0.200 | 0.121 |
| 3 | +no offhours / low volume | ideal | VAL | 103 | 0.534 | 0.086 | 1.184 | 8.841 | -12.098 | -0.142 | 0.298 |
| 3 | +no offhours / low volume | ideal | OOS | 144 | 0.431 | -0.115 | 0.799 | -16.536 | -27.469 | -0.294 | 0.091 |
| 4 | +impulse <= 15 ATR | real | DEV | 197 | 0.447 | -0.101 | 0.822 | -19.988 | -36.461 | -0.263 | 0.060 |
| 4 | +impulse <= 15 ATR | real | VAL | 97 | 0.567 | 0.072 | 1.161 | 6.966 | -13.165 | -0.146 | 0.284 |
| 4 | +impulse <= 15 ATR | real | OOS | 132 | 0.455 | -0.088 | 0.841 | -11.555 | -21.284 | -0.278 | 0.120 |
| 4 | +impulse <= 15 ATR | ideal | DEV | 201 | 0.458 | -0.038 | 0.931 | -7.557 | -31.789 | -0.209 | 0.135 |
| 4 | +impulse <= 15 ATR | ideal | VAL | 96 | 0.562 | 0.145 | 1.332 | 13.944 | -9.585 | -0.084 | 0.377 |
| 4 | +impulse <= 15 ATR | ideal | OOS | 133 | 0.459 | -0.069 | 0.873 | -9.171 | -19.535 | -0.254 | 0.126 |

Breakout at close:

| stage | label | cost | period | n | win_rate | expectancy | pf | total_r | max_dd_r | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | baseline | real | DEV | 668 | 0.287 | -0.269 | 0.645 | -179.747 | -183.663 | -0.381 | -0.161 |
| 0 | baseline | real | VAL | 314 | 0.290 | -0.219 | 0.713 | -68.743 | -77.182 | -0.386 | -0.054 |
| 0 | baseline | real | OOS | 437 | 0.332 | -0.105 | 0.850 | -45.974 | -61.018 | -0.258 | 0.052 |
| 0 | baseline | ideal | DEV | 677 | 0.307 | -0.032 | 0.954 | -21.649 | -46.745 | -0.169 | 0.106 |
| 0 | baseline | ideal | VAL | 326 | 0.301 | -0.069 | 0.902 | -22.619 | -40.897 | -0.254 | 0.129 |
| 0 | baseline | ideal | OOS | 441 | 0.333 | -0.011 | 0.984 | -4.788 | -30.944 | -0.166 | 0.148 |
| 1 | +stop 1.5 ATR | real | DEV | 612 | 0.422 | -0.138 | 0.770 | -84.371 | -102.923 | -0.229 | -0.039 |
| 1 | +stop 1.5 ATR | real | VAL | 279 | 0.444 | -0.049 | 0.915 | -13.742 | -34.594 | -0.186 | 0.093 |
| 1 | +stop 1.5 ATR | real | OOS | 383 | 0.467 | 0.018 | 1.034 | 7.080 | -22.437 | -0.107 | 0.154 |
| 1 | +stop 1.5 ATR | ideal | DEV | 614 | 0.440 | -0.016 | 0.972 | -9.539 | -43.942 | -0.124 | 0.081 |
| 1 | +stop 1.5 ATR | ideal | VAL | 287 | 0.453 | 0.017 | 1.032 | 4.999 | -26.381 | -0.129 | 0.160 |
| 1 | +stop 1.5 ATR | ideal | OOS | 384 | 0.469 | 0.056 | 1.105 | 21.695 | -19.200 | -0.074 | 0.185 |
| 2 | +breakout conf: big bar AND volume | real | DEV | 397 | 0.489 | -0.115 | 0.779 | -45.645 | -54.558 | -0.227 | -0.010 |
| 2 | +breakout conf: big bar AND volume | real | VAL | 195 | 0.621 | 0.112 | 1.287 | 21.767 | -12.118 | -0.042 | 0.277 |
| 2 | +breakout conf: big bar AND volume | real | OOS | 249 | 0.598 | 0.073 | 1.181 | 18.124 | -16.331 | -0.057 | 0.211 |
| 2 | +breakout conf: big bar AND volume | ideal | DEV | 407 | 0.521 | -0.034 | 0.930 | -13.653 | -24.630 | -0.140 | 0.082 |
| 2 | +breakout conf: big bar AND volume | ideal | VAL | 200 | 0.645 | 0.202 | 1.569 | 40.388 | -9.375 | 0.049 | 0.365 |
| 2 | +breakout conf: big bar AND volume | ideal | OOS | 251 | 0.606 | 0.092 | 1.236 | 23.103 | -16.324 | -0.038 | 0.236 |
| 3 | +penetration 0.5 ATR | real | DEV | 365 | 0.529 | -0.070 | 0.853 | -25.686 | -34.573 | -0.179 | 0.029 |
| 3 | +penetration 0.5 ATR | real | VAL | 181 | 0.613 | 0.063 | 1.158 | 11.370 | -14.622 | -0.088 | 0.229 |
| 3 | +penetration 0.5 ATR | real | OOS | 233 | 0.627 | 0.077 | 1.205 | 17.857 | -13.095 | -0.047 | 0.209 |
| 3 | +penetration 0.5 ATR | ideal | DEV | 376 | 0.564 | 0.007 | 1.016 | 2.692 | -17.620 | -0.097 | 0.125 |
| 3 | +penetration 0.5 ATR | ideal | VAL | 187 | 0.642 | 0.129 | 1.360 | 24.122 | -10.346 | -0.015 | 0.287 |
| 3 | +penetration 0.5 ATR | ideal | OOS | 238 | 0.639 | 0.089 | 1.249 | 21.164 | -12.864 | -0.031 | 0.213 |
| 4 | +cost gate spread<=15% stop | real | DEV | 365 | 0.529 | -0.070 | 0.853 | -25.686 | -34.573 | -0.179 | 0.029 |
| 4 | +cost gate spread<=15% stop | real | VAL | 181 | 0.613 | 0.063 | 1.158 | 11.370 | -14.622 | -0.088 | 0.229 |
| 4 | +cost gate spread<=15% stop | real | OOS | 233 | 0.627 | 0.077 | 1.205 | 17.857 | -13.095 | -0.047 | 0.209 |
| 4 | +cost gate spread<=15% stop | ideal | DEV | 376 | 0.564 | 0.007 | 1.016 | 2.692 | -17.620 | -0.097 | 0.125 |
| 4 | +cost gate spread<=15% stop | ideal | VAL | 187 | 0.642 | 0.129 | 1.360 | 24.122 | -10.346 | -0.015 | 0.287 |
| 4 | +cost gate spread<=15% stop | ideal | OOS | 238 | 0.639 | 0.089 | 1.249 | 21.164 | -12.864 | -0.031 | 0.213 |

Year-by-year expectancy of each stage (real):

| stage | label | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 0 | baseline | -0.473 | -0.287 | -0.235 | -0.132 | -0.166 | -0.135 |
| 1 | +stop 1.5 ATR | -0.103 | -0.173 | -0.201 | -0.032 | -0.116 | -0.078 |
| 2 | +overlap+london session | -0.121 | -0.192 | -0.164 | -0.015 | -0.064 | -0.136 |
| 3 | +cost gate spread<=15% stop | -0.121 | -0.192 | -0.164 | -0.015 | -0.064 | -0.136 |
| 4 | +impulse <= 15 ATR | -0.231 | -0.168 | -0.179 | 0.020 | -0.050 | -0.191 |

| stage | label | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 0 | baseline | 0.113 | -0.082 | -0.405 | -0.320 | -0.260 | -0.299 |
| 1 | +stop 1.5 ATR | -0.009 | -0.017 | -0.139 | -0.134 | -0.067 | -0.085 |
| 2 | +breakout conf: big bar AND volume | -0.352 | -0.077 | -0.089 | -0.120 | 0.096 | -0.237 |
| 3 | +no offhours / low volume | -0.331 | -0.077 | -0.089 | -0.135 | 0.121 | -0.226 |
| 4 | +impulse <= 15 ATR | -0.370 | 0.004 | -0.120 | -0.089 | 0.202 | -0.200 |

| stage | label | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 0 | baseline | -0.215 | -0.208 | -0.352 | -0.223 | -0.053 | -0.213 |
| 1 | +stop 1.5 ATR | -0.099 | -0.134 | -0.155 | -0.098 | 0.069 | -0.019 |
| 2 | +breakout conf: big bar AND volume | -0.272 | -0.047 | -0.123 | 0.010 | 0.290 | -0.049 |
| 3 | +penetration 0.5 ATR | -0.287 | 0.006 | -0.063 | -0.040 | 0.260 | -0.021 |
| 4 | +cost gate spread<=15% stop | -0.287 | 0.006 | -0.063 | -0.040 | 0.260 | -0.021 |

The best stage (B2, stop 1.5 ATR + confirmed breakout + 0.5 ATR penetration) is -0.07R in DEV, +0.06R in VAL and +0.08R in
OOS; every confidence interval contains zero, and the year table shows the sign comes from 2025 (+0.26R) with 2021, 2023,
2024 and 2026 negative. That is a regime result, not a robust edge.

## 12. Walk-forward results

For each test year the candidate with the best expectancy on all earlier years (>= 100 trades) is chosen and applied to
that year (`13_walk_forward.csv`). The chosen variant is always the wider stop; it loses less than the baseline in every
test year and is positive in one (ping-pong 2024, +0.02R).

| playbook | test_year | chosen | train_expectancy | train_n | test_n | test_expectancy | test_pf | baseline_test_n | baseline_test_expectancy |
|---|---|---|---|---|---|---|---|---|---|
| A_pingpong | 2023 | stop2.0 | -0.106 | 388 | 305 | -0.162 | 0.642 | 343 | -0.235 |
| A_pingpong | 2024 | stop2.0 | -0.130 | 693 | 254 | 0.022 | 1.059 | 287 | -0.132 |
| A_pingpong | 2025 | stop2.0 | -0.090 | 947 | 291 | -0.117 | 0.752 | 334 | -0.166 |
| A_pingpong | 2026 | stop2.0 | -0.096 | 1238 | 213 | -0.059 | 0.865 | 240 | -0.135 |
| B1_pullback | 2023 | stop1.0 | 0.002 | 261 | 189 | -0.239 | 0.658 | 192 | -0.405 |
| B1_pullback | 2024 | stop1.5 | -0.067 | 441 | 160 | -0.134 | 0.784 | 164 | -0.320 |
| B1_pullback | 2025 | stop1.5 | -0.085 | 601 | 186 | -0.067 | 0.886 | 192 | -0.260 |
| B1_pullback | 2026 | stop1.5 | -0.080 | 787 | 129 | -0.085 | 0.868 | 134 | -0.299 |

## 13. Out-of-sample results (Apr 2025 - Sep 2026, never used for selection)

| playbook | cost | n | win_rate | expectancy | pf | total_r | max_dd_r | max_loss_streak | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|
| A_pingpong | ideal | 502 | 0.367 | -0.069 | 0.896 | -34.590 | -45.777 | 18 | -0.210 | 0.068 |
| A_pingpong | real | 490 | 0.361 | -0.139 | 0.796 | -67.935 | -71.571 | 18 | -0.266 | 0.000 |
| B1_pullback | ideal | 282 | 0.287 | -0.155 | 0.790 | -43.716 | -53.759 | 11 | -0.343 | 0.037 |
| B1_pullback | real | 278 | 0.273 | -0.278 | 0.639 | -77.171 | -84.636 | 11 | -0.461 | -0.092 |
| B2_immediate | ideal | 441 | 0.333 | -0.011 | 0.984 | -4.788 | -30.944 | 13 | -0.166 | 0.148 |
| B2_immediate | real | 437 | 0.332 | -0.105 | 0.850 | -45.974 | -61.018 | 12 | -0.258 | 0.052 |

Baseline OOS: negative under real costs for all three playbooks; B2 ideal is the closest to flat (-0.011R). The staged
adaptations reach +0.06 to +0.08R in OOS for B2 and -0.09 to -0.14R for A and B1 (section 11).

## 14. Transaction-cost sensitivity

Ping-pong:

| variant | n | expectancy | pf | total_r | spread_r |
|---|---|---|---|---|---|
| ideal | 1687 | -0.056 | 0.912 | -94.489 | 0.000 |
| spread_only | 1679 | -0.139 | 0.785 | -234.003 | 0.091 |
| real_slip0 | 1660 | -0.164 | 0.751 | -272.663 | 0.096 |
| real | 1661 | -0.215 | 0.686 | -357.256 | 0.092 |
| real_slip0.2 | 1660 | -0.257 | 0.634 | -426.858 | 0.087 |
| real_ecn_comm | 1661 | -0.239 | 0.659 | -396.336 | 0.092 |
| real_delay5 | 1628 | -0.267 | 0.632 | -434.903 | 0.123 |
| real_spread_x0.5 | 1667 | -0.180 | 0.735 | -299.630 | 0.048 |
| real_spread_x1.5 | 1667 | -0.244 | 0.646 | -406.637 | 0.135 |
| real_spread_x2.0 | 1671 | -0.282 | 0.598 | -470.752 | 0.179 |

Breakout + pullback:

| variant | n | expectancy | pf | total_r | spread_r |
|---|---|---|---|---|---|
| ideal | 960 | -0.075 | 0.896 | -71.936 | 0.000 |
| spread_only | 956 | -0.159 | 0.783 | -151.779 | 0.092 |
| real_slip0 | 944 | -0.184 | 0.757 | -173.514 | 0.104 |
| real | 945 | -0.244 | 0.691 | -230.175 | 0.099 |
| real_slip0.2 | 944 | -0.288 | 0.643 | -271.670 | 0.091 |
| real_ecn_comm | 945 | -0.269 | 0.667 | -254.149 | 0.099 |
| real_delay5 | 938 | -0.245 | 0.689 | -229.342 | 0.108 |
| real_spread_x0.5 | 944 | -0.208 | 0.734 | -196.064 | 0.051 |
| real_spread_x1.5 | 944 | -0.292 | 0.634 | -275.420 | 0.145 |
| real_spread_x2.0 | 942 | -0.344 | 0.575 | -323.969 | 0.189 |

The spread alone costs about 0.08-0.09R per trade, slippage 0.05R, swap 0.02R, a 5-minute delay another 0.05R for ping-pong.
Doubling the spread doubles the damage; halving it does not restore the sign. An ECN commission of 7 USD per lot adds 0.02R.

## 15. Maximum drawdown

Realistic execution, fixed 1R per trade: A -361R, B1 -251R, B2 -294R, combined A+B1 -567R.
Compounding at 1% risk from 10,000 USD the equity ends at 2% (A), 9% (B1), 4% (B2) of the start,
with maximum drawdowns of -98%, -93% and -96%. Even ideal execution breaches the source's 20% drawdown limit
(-69%, -77%, -56%). Equity and drawdown curves: `06_07_equity_drawdown_*.csv` and the HTML report.

## 16. Losing streak analysis

Maximum consecutive losses: A 18, B1 21, B2 16. The source calls 10-20 normal; the observed streaks are
inside that band, so the streaks are not the diagnostic. The diagnostic is the ratio: at a 36% win rate a planned 1.4 R:R needs
a 42% win rate to break even before costs. Wider stops raise the win rate to 50-60% and cut the streaks to 6-9 but lower the
average win, and the product stays negative.

## 17. Failure examples (ping-pong, realistic)

Worst losses:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-07-25 20:31:00 | newyork | B | long | pingpong | 3337.45 | 3334.35 | 3339.65 | 3316.84 | 0.71 | -6.93 | stop | 49.48 | 0.47 | 6.62 | 19.11 | 1.63 | news_driven |
| 2021-10-28 06:31:00 | asia | P | short | pingpong | 1803.81 | 1803.89 | 1798.74 | 1804.26 | 64.86 | -5.76 | stop | 0.00 | 0.90 | 6.14 | 6.72 | 3.21 | range_too_narrow |
| 2026-01-02 21:46:00 | newyork | B | short | pingpong | 4329.03 | 4335.27 | 4318.39 | 4361.39 | 1.71 | -5.19 | stop | 49.23 | -0.07 | 5.18 | 14.72 | 2.00 | news_driven |
| 2023-06-23 19:16:00 | newyork | B | short | pingpong | 1920.90 | 1922.16 | 1918.16 | 1925.30 | 2.18 | -3.34 | stop | 50.73 | 1.40 | 3.64 | 7.84 | 1.68 | poor_vah_val_location |

Randomly drawn losses:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-06-19 13:16:00 | overlap | P | long | pingpong | 3367.34 | 3361.38 | 3374.14 | 3361.28 | 1.14 | -1.02 | stop | 0.22 | 0.15 | 1.02 | 5.13 | 2.45 | news_driven |
| 2024-12-27 13:16:00 | overlap | B | long | pingpong | 2626.16 | 2621.97 | 2630.58 | 2621.87 | 1.05 | -1.02 | stop | 0.07 | 0.24 | 1.07 | 7.61 | 3.18 | news_driven |
| 2022-05-02 20:01:00 | newyork | B | long | pingpong | 1862.00 | 1860.14 | 1869.28 | 1860.04 | 3.91 | -1.52 | stop | 5.67 | 2.69 | 1.00 | 11.74 | 2.91 | trend_continuation_against |
| 2024-12-04 19:01:00 | newyork | P | long | pingpong | 2648.00 | 2645.16 | 2655.99 | 2645.06 | 2.80 | -1.95 | stop | 7.15 | 2.57 | 1.01 | 7.62 | 2.93 | poor_vah_val_location |

Breakout + pullback, worst losses:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-11-30 14:16:00 | overlap | P | short | breakout_pullback | 1759.43 | 1759.48 | 1752.77 | 1759.88 | 119.52 | -8.08 | stop | 0.00 | 4.83 | 14.91 | 8.16 | 1.80 | news_driven |
| 2025-05-09 07:46:00 | london | B | long | breakout_pullback | 3327.43 | 3318.31 | 3362.64 | 3271.70 | 3.86 | -6.20 | stop | 62.23 | 2.18 | 6.10 | 9.29 | 2.56 | news_driven |
| 2024-12-06 19:46:00 | newyork | P | short | breakout_pullback | 2633.48 | 2636.90 | 2614.39 | 2646.90 | 5.58 | -3.86 | stop | 51.23 | 0.66 | 4.31 | 8.45 | 2.66 | false_breakout |
| 2025-04-04 20:31:00 | newyork | B | long | breakout_pullback | 3038.39 | 3029.88 | 3136.43 | 3006.66 | 11.51 | -3.83 | stop | 49.48 | 0.15 | 3.73 | 13.50 | 2.07 | news_driven |

## 18. Successful examples

Ping-pong, best trades:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-10-14 13:31:00 | overlap | B | long | pingpong | 4107.85 | 4104.26 | 4141.41 | 4141.41 | 9.37 | 9.37 | target | 2.03 | 9.39 | 0.33 | 11.91 | 3.01 | poor_vah_val_location |
| 2025-06-20 19:46:00 | newyork | P | long | pingpong | 3365.82 | 3363.26 | 3373.34 | 3390.70 | 2.93 | 9.35 | target | 50.23 | 12.01 | 0.52 | 7.92 | 2.63 | news_driven |
| 2025-10-22 14:46:00 | overlap | B | long | pingpong | 4020.12 | 4010.74 | 4078.69 | 4078.69 | 6.24 | 6.24 | target | 3.82 | 6.53 | 0.99 | 9.24 | 2.62 | news_driven |
| 2025-11-19 14:31:00 | overlap | P | long | pingpong | 4104.34 | 4102.06 | 4117.64 | 4117.64 | 5.81 | 5.81 | target | 0.38 | 5.97 | 0.26 | 5.49 | 1.51 | news_driven |

Ping-pong, randomly drawn wins:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-06-20 19:46:00 | newyork | P | long | pingpong | 3365.82 | 3363.26 | 3373.34 | 3390.70 | 2.93 | 9.35 | target | 50.23 | 12.01 | 0.52 | 7.92 | 2.63 | news_driven |
| 2022-11-11 14:31:00 | overlap | P | short | pingpong | 1760.75 | 1765.76 | 1756.34 | 1756.34 | 0.88 | 0.88 | target | 0.20 | 0.97 | 0.26 | 6.78 | 2.87 | entry_too_late |
| 2022-10-05 14:16:00 | overlap | B | long | pingpong | 1705.30 | 1701.07 | 1712.04 | 1712.04 | 1.59 | 1.59 | target | 3.17 | 1.62 | 0.60 | 11.19 | 2.50 | news_driven |
| 2024-10-29 05:16:00 | asia | P | short | pingpong | 2755.66 | 2758.42 | 2749.34 | 2749.34 | 2.28 | 2.28 | target | 0.82 | 2.31 | 0.13 | 9.32 | 3.49 | poor_vah_val_location |

Breakout + pullback, best trades:

| entry_time | session | stype | side | entry_type | entry | stop | target | exit | rr_actual | r_net | exit_reason | hold_h | mfe_r | mae_r | imp_size_atr | width_atr | loss_category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-10-17 01:01:00 | asia | B | long | breakout_pullback | 1647.22 | 1645.80 | 1663.86 | 1663.86 | 11.66 | 11.66 | target | 11.35 | 13.03 | 0.30 | 6.76 | 3.65 | news_driven |
| 2024-08-22 23:01:00 | offhours | B | long | breakout_pullback | 2485.23 | 2483.20 | 2504.05 | 2504.05 | 9.26 | 9.26 | target | 14.98 | 11.25 | 0.20 | 10.57 | 5.75 | news_driven |
| 2022-08-17 10:46:00 | london | B | short | breakout_pullback | 1772.49 | 1774.05 | 1759.31 | 1759.31 | 8.44 | 8.82 | target | 28.92 | 8.77 | 0.88 | 20.97 | 8.03 | news_driven |
| 2022-07-13 19:16:00 | newyork | P | short | breakout_pullback | 1734.09 | 1737.54 | 1706.95 | 1706.95 | 7.86 | 8.03 | target | 17.75 | 7.94 | 0.68 | 11.79 | 2.56 | news_driven |

The best trades are counter-impulse breakouts that reached the impulse origin (3-9R) and ping-pong entries just after a
failed breakout. They are rare: the 99th percentile trade is about +3R.

## 19. Limitations

* The discretionary parts (what "well-defined range", "decisive break", "confirmation" mean) were replaced by one objective
  rule set. A different but equally defensible rule set could behave differently; the sensitivity grids cover the
  neighbourhood of the chosen rules, not every reading of the method.
* No footprint or COMEX order-flow data (Version B untested). The order-flow confirmation step could be the source of the
  method's edge; that cannot be tested here, and the Dukascopy volume proxy carried no information.
* News: proxy slots, not an actual calendar. July 2024 missing. Spread before July 2022 is a constant estimate.
* Bar-path execution: the M1 path is used for stops and targets with a stop-first rule; ticks would place some fills differently.
* The holding-time mismatch (hours vs days) means the test covers the 15-minute structures the rules find, not the
  multi-day swings in the source's examples; longer confirmation windows were tested and were worse, but a daily-scale
  version of the framework (H1/H4 impulses) was outside the brief and remains untested.
* Multiple comparisons: about 180 variants were run. The pre-registered retention rule and the untouched OOS period limit,
  but do not remove, selection effects; the staged results in section 11 should be read with that in mind.

## 20. Final conclusion

Under what measurable conditions does the framework work on XAUUSD, and when should it not trade?

* **It does not show positive expectancy in any period under the original rules**, with costs (-0.22 / -0.24 / -0.21R)
  or without (-0.06 / -0.07 / -0.03R). The entry logic is roughly a coin flip at the planned geometry; costs decide the sign.
* **Least-bad conditions, consistent across DEV, VAL and OOS:** stops of 1.5-2 ATR (never tighter than 1 ATR), the London/New York
  overlap, impulses no larger than 15 pre-impulse ATR, spread below 15% of the stop, and, for breakouts, a confirmation bar with
  range >= 1.5 ATR and volume >= 1.5x average entered at the close. These reduce the loss from about -0.22R to about -0.07R (DEV)
  and to +0.06/+0.08R in VAL/OOS for B2 only; the positive years are 2025 for every playbook.
* **No-trade conditions supported by the data:** impulse > 15 ATR; stop < 1 ATR or spread > 15% of the stop; off-hours and
  low-volume bars; Asia session for breakout pullbacks; New York afternoon for ping-pong; a range confirmed over 12 or more bars.
* **Conditions that did not matter:** alignment with the weekly VAH/VAL (any source, any tolerance), the news-slot proxy,
  volatility percentile, range width, touch count, pullback depth, target fraction.
* **Verdict:** the evidence does not support a Gold Strategy Specification. The framework's measurable part is not profitable on
  XAUUSD over 2021-2026; the unmeasurable part (footprint/order-flow confirmation) is where any edge would have to live, and it
  needs a different dataset to test.

Files: `results/deliverables/` (69 files: rule spec, dataset pointer, all signals and structures, trade-by-trade CSVs for each
playbook and cost model, loss classification and taxonomy, equity/drawdown, monthly, session, P/B, filters, every experiment,
grids, walk-forward, staged adaptations, OOS results). Code: `pbd/` (data, profile, structure, engine, analysis) and the run scripts.
