# Study 4: tiered lot sizing and scaled partial exit on the final H4 configuration

Implemented in `SimpleSMA18Bot_H4_Dynamic.mq5` (compiled, 0 errors) and in the backtest engine, then validated on Sep 2020 - Sep 2026, 2023-2026 and the last 12 months, all as full $200 account simulations (balance-dependent lots, margin, stop-out, XM costs). The final H4 exit and entry rules from study 3 are unchanged.

## 1. The rules as implemented

| Rule | Implementation | EA input |
|---|---|---|
| Lot from balance | lot = BaseLot x 2^floor(log2(balance / BaseBalance)); below BaseBalance the lot stays at BaseLot; capped at MaxLot; normalised to the broker step | `UseDynamicLots`, `BaseBalance` (200), `BaseLot` (0.01), `MaxLot` (1.00) |
| Re-evaluation | at every order from the *current* balance, so the lot steps down when the balance falls | automatic |
| Partial exit | once per position, when floating profit (incl. swap) reaches the tier target: tiers 0 and 1 = PartialProfitBaseUSD, from tier 2 doubling (200, 400, 800 ...) | `EnablePartialExit`, `PartialProfitBaseUSD` (100), `PartialProfitDoubles` (true) |
| Partial size | PartialExitPercent of the position volume, rounded down to the lot step | `PartialExitPercent` (50) |
| Minimum-lot case | at 0.01 lot a 50% share (0.005) cannot be traded on XM (min 0.01, step 0.01): `PARTIAL_SKIP` leaves the position to the normal exits, `PARTIAL_CLOSE_ALL` closes the whole position at the target | `PartialAtMinLot` |
| Buy and sell | profit and target are in account currency, so both sides use the same code; the engine test below has 128 shorts and 178 longs | - |
| 1% gate | default off in this variant (a $200 account cannot pass it on H4); the input still exists | `UseSLPercentFilter = false` |

Tier table with the defaults: $200-399 -> 0.01 lot, target $100 (share 0.005: skip or close all); $400-799 -> 0.02, target $100, closes 0.01; $800-1,599 -> 0.04, target $200, closes 0.02; $1,600-3,199 -> 0.08, target $400, closes 0.04; and so on, capped at MaxLot.

## 2. Validation, $200 start, final H4 configuration

| Variant | Window | End balance | Growth | Max DD (peak to trough) | Max lot | Worst single deal | Partials | Ruined |
|---|---|---:|---:|---:|---:|---:|---:|---|
| A fixed 0.01 lot | 6y | $2,730 | 13.7x | $304 (80.7%) | 0.01 | -$173 | 0 | no |
| B tiers, no partial | 6y | $30,218 | 151x | $57,105 (80.7%) | 2.56 | -$19,075 | 0 | no |
| C tiers + partial, skip at 0.01 | 6y | $8,123 | 40.6x | $12,751 (81.7%) | 0.64 | -$4,769 | 53 | no |
| D tiers + partial, close all at 0.01 | 6y | $9,316 | 46.6x | $17,519 (81.9%) | 1.28 | -$9,537 | 56 | no |
| E as C, MaxLot 0.20 | 6y | $8,147 | 40.7x | $6,419 (81.7%) | 0.20 | -$2,100 | 46 | no |
| A fixed 0.01 lot | 2023-26 | $2,622 | 13.1x | $304 (49%) | 0.01 | -$173 | 0 | no |
| B tiers, no partial | 2023-26 | $0 | 0x | 100% | 0.04 | -$691 | 0 | **yes** |
| C tiers + partial, skip | 2023-26 | $9,362 | 46.8x | $17,519 (68%) | 1.28 | -$9,537 | 47 | no |
| D tiers + partial, close all | 2023-26 | $9,496 | 47.5x | $20,880 (71%) | 1.28 | -$9,537 | 48 | no |
| A fixed 0.01 lot | last 12 months | $1,959 | 9.8x | $304 (59%) | 0.01 | -$173 | 0 | no |
| B, C, D, E (any tiered variant) | last 12 months | $0 | 0x | 100% | 0.02 | -$345 | 0-3 | **yes** |

What happens in the last 12 months: the first four trades take $200 to $486 by mid-October 2025, the balance crosses $400, the next order is 0.02 lot, and the 17 Oct loss (-$173 per 0.01 lot) becomes -$345 and empties the account. The same mechanism ruins variant B when started in January 2023 and variant C when started in January 2024.

Start-date sensitivity ($200 started on 1 January of each year, run to 25 Sep 2026; end balance, max DD %, ruined):

| Variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| A fixed 0.01 | $2,744 / 77% | $2,786 / 46% | $2,622 / 49% | $2,459 / 72% | $2,377 / 36% | $1,699 / 16% |
| B tiers, no partial | $34,744 / 77% | $34,744 / 77% | **ruined** | $17,018 / 77% | $17,020 / 77% | $7,525 / 67% |
| C tiers + partial, skip | $8,127 / 82% | $8,125 / 82% | $9,362 / 68% | **ruined** | $4,705 / 81% | $2,374 / 67% |
| D tiers + partial, close all | $9,323 / 82% | $9,318 / 82% | $9,496 / 71% | $4,748 / 78% | $4,697 / 80% | $3,976 / 65% |

Trade-order Monte Carlo with compounding (the tier rule applied to 5,000 shuffled / resampled orderings of the fixed-lot trade outcomes, no partials):

| Tier base | p(ruin) | End balance p05 / median / p95 | Drawdown median / p95 |
|---|---:|---:|---:|
| $200 (as specified) | 22% shuffle, 27% bootstrap | ruined / $13,898 / $46,302 | 88% / 98.5% |
| $500 (doubles at $1,000) | 18% | ruined / $5,839 / $7,857 | 59% / 97.7% |
| $1,000 (doubles at $2,000) | 18% | ruined / $3,159 / $3,430 | 53% / 97.7% |
| $2,000 (fixed 0.01 in practice) | 18% | ruined / $2,730 / $2,730 | 53% / 97.3% |

The 18% floor is the $200 account itself: an H4 stop is $41 to $330 per 0.01 lot, so a normal losing run empties $200 whatever the tier rule does. The extra 4 to 9 points of ruin probability and the 88% median drawdown come from doubling the lot while a single stop is still up to 165% of the tier's floor balance.

Higher first-tier balance, same code, same windows ($200 start, partial skip):

| BaseBalance | 6y end | Max lot | Worst deal | Last 12 months | Ruined start years (of 6) |
|---|---:|---:|---:|---:|---:|
| $200 | $8,123 | 0.64 | -$4,769 | ruined | 1 |
| $500 | $3,525 | 0.08 | -$840 | $1,890 | 0 |
| $1,000 | $2,820 | 0.02 | -$210 | $1,877 | 0 |
| $2,000 | $2,730 | 0.01 | -$173 | $1,959 | 0 |

## 3. What the partial exit does

At tier 0 (0.01 lot) the 50% share is not tradable, so with `PARTIAL_SKIP` the partial exit never fires on a $200-399 account; with `PARTIAL_CLOSE_ALL` it is a $100 take-profit, which lowers the fixed-lot six-year result from $2,730 to $2,156 (the strategy's profit comes from the trades that run 5 ATR and further; a $100 cap on a 0.01-lot position is a $100 move in gold, which the trailing stop would otherwise ride). At tiers 1 and above the 50% close halves the exposure to the runners: variant C ends at $8,123 against $30,218 without partials, with a maximum lot of 0.64 instead of 2.56 and a worst deal of -$4,769 instead of -$19,075. The partial exit therefore trades growth for a smaller worst case; it does not remove the ruin risk that the doubling creates, because the loss that ruins the account happens right after the tier steps up, before any partial can be taken.

## 4. Verdict and settings

- The rules are implemented exactly as specified and configurable; they work mechanically (tier up and down from the balance, partial size and target scale with the tier, buy and sell).
- As specified on a $200 account they are not safe: 22 to 27% ruin probability, 88% median drawdown, and the last 12 months and two of six start years end at zero. The cause is structural: the tier floor ($200 per 0.01 lot) is smaller than one H4 stop.
- Same EA, safer settings: `BaseBalance = 500` (doubling at $1,000, $2,000, ...) keeps every start year and the last 12 months alive with a worst deal of -$840 and a maximum lot of 0.08; `BaseBalance = 1000` is nearly the fixed-lot result. `MaxLot` 0.20 caps the worst case without changing the six-year result much. Keep `PartialAtMinLot = PARTIAL_SKIP` unless a $100 take-profit at 0.01 lot is wanted.
- The 18% ruin floor of a $200 account on H4 remains whatever the sizing rule; the report of study 3 stands: about $3,000 (or an XM Micro account) for the 1% rule.

## 5. Tester notes

Symbol GOLD, H4, every tick, deposit $200, leverage 1:1000, `SimpleSMA18Bot_H4_Dynamic.ex5` with its defaults. The journal prints the tier and lot at start, every partial exit ("Partial exit: closed 0.01 of 0.02 lot at floating profit 100.xx (tier 1, target 100.00)") and every skip at the minimum lot. The engine's trade lists for each variant are in `research/study4/results/trades_*.csv`.
