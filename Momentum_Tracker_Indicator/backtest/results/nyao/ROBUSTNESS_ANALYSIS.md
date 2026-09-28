# Robustness analysis: Nyao Scalper on XAUUSD (Steps 9, 15, 16, 17 of the brief)

All numbers in USD at 0.01 lot unless noted. Sources: `nyao_runs.csv` (per-period runs of the shipped logic),
`nyao_runs2.csv` (fixed-stop research runs), `monte_carlo.json`, `tick_calibration.json`.

## 1. Out-of-sample structure (Step 15)

Every configuration is simulated separately in DEV (2021-09..2023-12), VAL (2024) and OOS (2025-01..2026-09-25), each
from the deposit. No parameter was fitted: the EA is run at its author's defaults and its four published profiles, then
perturbed around them. There is therefore no in-sample/out-of-sample gap to report; there is only the sign of the result
in each period, and it is negative in all of them for every run (69 runs of the shipped logic, 14 research runs).

Walk-forward reading on the fixed-stop research runs (five years continuous, 12-month rolling windows on the real trade
sequence): 50 of 50 windows negative on M5 (best -$720, worst -$5,137) and 50 of 50 on M1 (best -$364, worst -$15,231).
Entry-only mode (Nyao score + 1.5 ATR stop, 1.5R target): 34 of 38 windows negative, best window $0.

## 2. Parameter perturbation (Step 16)

Default profile, M5, hedge off, tick-calibrated; expectancy per trade DEV / VAL / OOS. Default: -0.43 / -0.43 / -0.43.

| Parameter | Values tried | Expectancy range (all periods) | Best |
|---|---|---|---|
| entry threshold | 3.5, 4.0, 5.0, 5.5, 6.0 | -0.37 to -0.98 | 3.5 (-0.42/-0.39/-0.37); 6.0 is the worst (-0.77/-0.62/-0.98) |
| EMA fast/slow | 4/10, 6/14, 8/21 | -0.38 to -0.47 | 8/21 in DEV (-0.38), worse in OOS |
| RSI period | 6, 10, 14 | -0.42 to -0.49 | none |
| ATR period | 6, 10, 14 | -0.37 to -0.47 | 14 in VAL (-0.37), -0.45 OOS |
| forming-candle blend | 0.0, 0.6 | -0.53/-0.56/-0.60, -0.32/-0.35/-0.33 | 0.6 is the least bad setting found; still ruins every period |
| trailing distance per 0.01 lot | $0.50, $1, $2 | -0.40 to -0.56 | none; wider trails lose more |
| session | London only, NY only, Asia only | -0.19 (London VAL) to -0.53 (Asia VAL) | London the least bad; negative in all periods |
| news proxy (no entries 15:15-16:00) | M5, M1 | -0.41/-0.40/-0.42, -0.48/-0.48/-0.51 | no effect |

Fixed-stop ablations (M5, five years, each layer switched off alone; net / gross before spread):

| Variant | Trades | PF | Net | Gross | Spread |
|---|---:|---:|---:|---:|---:|
| EA logic, fixed $10 stop (reference) | 28,754 | 0.69 | -10,601 | +801 | 11,402 |
| trailing off | 17,323 | 0.79 | -8,259 | -1,328 | 6,931 |
| loss management off (health close, BE, tighten, re-entry) | 27,155 | 0.70 | -10,431 | +409 | 10,840 |
| virtual-SL re-entry off | 28,425 | 0.69 | -10,368 | +912 | 11,280 |
| signal dampening off (cooldown, penalty, drawdown gate) | 71,536 | 0.70 | -25,046 | +4,041 | 29,087 |
| trailing distance $1 | 27,633 | 0.73 | -9,331 | +1,674 | 11,005 |
| trailing distance $3, activation $2.25 | 22,450 | 0.74 | -11,104 | -2,064 | 9,040 |
| no trailing, stop 1.5 ATR, target 1.5R, management on | 20,871 | 0.83 | -7,826 | +434 | 8,260 |
| hedge chain with trailing and loss management off | 28 | 0.06 | -94,341 | -94,295 | 45 |

Reading: every layer of the EA is roughly neutral before costs (gross between -$2,064 and +$4,041 over five years, on a
spread bill of $7,000-29,000). Removing the dampening triples the trade count and the spread bill while the gross stays
near zero: the signal generates trades, not information. The chain alone, with nothing else closing positions, has no
floor.

Classification: **not an overfitting question**. There is no profitable neighbourhood in parameter space to have been
selected from; 25 perturbations and 9 ablations are negative in every period. The result is robustly negative.

## 3. Cost sensitivity (Step 9)

Shipped logic, calibrated, hedge off, PF at normal cost 0.57 (M1) / 0.60 (M5): spread x1.25 -> 0.57 / 0.58, x1.5 -> 0.56 /
0.52, x2 -> 0.47 / 0.47; slippage 5 points -> 0.49 / 0.51, 10 points -> 0.42 / 0.45. Hedge on (M1): spread x1.5 -> 0.70,
slippage 5 points -> 0.58. Fixed-stop runs with 3 points of slippage per trade: M5 net -10,601 -> -11,464; M1 -19,665 ->
-20,920; spread x1.25: -13,452 and -24,220.

The strategy does not survive its normal cost, so cost degradation only changes the speed of ruin. The one direction
that helps in dollars is a larger spread on M1 (DEV -563 at x2 versus -981 at x1) because the 0.25 x ATR spread gate then
blocks most entries; per trade it is still worse.

## 4. Monte Carlo (Step 17)

Bootstrap of the trade population (2,000 resamples per statistic), shuffled sequences (300) and rolling windows on the
fixed-stop research runs and the entry-only run:

| Run | Trades / year | Mean trade, 95% CI | P(mean > 0) | Yearly P&L p5 / p50 / p95 | P(losing year) | Real max DD | Shuffled max DD p5-p95 |
|---|---:|---|---:|---|---:|---:|---|
| fixed-stop M5, hedge off | 5,676 | -0.37 (-0.40 to -0.33) | 0.000 | -2,468 / -2,094 / -1,688 | 1.000 | 10,623 | 10,605-10,662 |
| fixed-stop M1, hedge off | 8,254 | -0.47 (-0.50 to -0.44) | 0.000 | -4,392 / -3,897 / -3,425 | 1.000 | 19,690 | 19,667-19,711 |
| fixed-stop M5, hedge on | 5,815 | -0.69 (-0.90 to -0.46) | 0.000 | -6,357 / -4,041 / -1,530 | 0.996 | 20,402 | 20,237-21,332 |
| entry-only M5 (1.5 ATR stop, 1.5R) | 1,776 | -0.39 (-0.52 to -0.27) | 0.000 | -1,078 / -682 / -301 | 0.998 | 2,819 | 2,810-2,986 |

The shuffled drawdown equals the real drawdown because the equity curve is a straight line down: the sequence does not
matter, the mean does. Execution perturbation (delayed entries, extra slippage, wider spread) can only move the mean further
below zero; the calibrated trailing assumption is the one execution variable that could move it up, and section 5 covers it.

## 5. Sensitivity to the trailing-stop assumption

The bar engine's optimistic bound assumes the bar's extreme was reached before any 20-point retrace; the pessimistic bound
assumes the retrace came at activation. On 3,905 tick-replayed trailing exits the tick exit sits at the pessimistic bound
(median lambda 0.00, mean 0.05; 54% within 10% of the bound, 13% above 0.5). The calibrated runs use lambda 0.05 (same-bar
exits) and 0.085 (trailed stops hit later). If the whole distribution were shifted to lambda 1.0 the hedge-off default would
show PF 1.27-1.42 and the hedge-on default would still ruin (PF 0.91-0.94). No intermediate lambda was searched for a
break-even point because the measured distribution does not support one: 68% of the replayed exits are within 5 points of
the activation price, a one-tick event on gold.

The calibration sample is 2025, Thursdays and Fridays, 14:00-19:59 server time (the tick hours already on disk from
phase 14). It is the most active part of the day, where the trail activates most often; quiet hours were not replayed.
A 20-point retrace after a 82-point advance is at least as likely in a quiet market, so the calibrated reading is, if
anything, generous to the EA there.

## 6. What would change the conclusion

* A tick replay of the whole history showing lambda above about 0.5 on average. The sample says 0.05.
* A broker with a spread under 15 points on gold. XM's 2026 median is 51.
* A change in the EA that replaces the $0.20 trail with a structure-based exit. That is a different strategy, and its entry
  (section 7 of the main report) is a coin flip before costs, so the change would move the result from "ruin" to
  "loses the spread", as your own TWK signal does.
