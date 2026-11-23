# Day review: is there a daily POC / value-area pattern to trade?

Asked 22 Nov 2026: take a full-day screenshot of each of the last 30 days on the GEX page, find what the days
have in common (price under the POC, coming from a sell zone, ...), something that could become a signal.

## Files

| file | what |
|---|---|
| `shots.py` | full-day screenshots of every trading day the page holds -> `screens/YYYY-MM-DD.png`, 2-day strips, 4-day sheets |
| `day_study.cjs` | `node day_study.cjs fetch` downloads Binance minutes (git-ignored `data/`); `node --max-old-space-size=6000 day_study.cjs` runs the tests below |
| `results/summary.md` | the numbers; `days_*.csv` one row per day, `trades_*.csv` one row per race |

## What the 20 screenshots showed (26 Oct - 20 Nov 2026, looked at before any test)

- Two kinds of day. **Balance days** (26 Oct, 3 Nov, 6 Nov, 13 Nov, 16-17 Nov): price crosses the POC again and
  again and closes near it. **Trend days** (30 Oct, 4 Nov, 10-12 Nov, 18-20 Nov): the POC is set in Asia /
  London and then stays put while price leaves the value area in the New York session and does not come back
  that day (12 Nov: POC 3980.7 from 13:30 to the close, price 100 $ under it).
- The big POC shifts come late, after most of the move (30 Oct: -91 $ at 22:07; 4 Nov: +110 $ at 16:55): the
  POC follows price, it does not lead it.
- Most buy / sell zones are closed through within hours, as in the earlier box study.
- Read by eye, where price stood against the value area at 13:30 (Asia) said little about the rest of the day:
  6 of 10 checked days went the "wrong" way. 20 days cannot settle it, so the ideas were turned into tests.

## Tests (written down before the first run)

Every test is a race from the price at one moment: does a target come before a stop at the same distance on
the other side? With no edge the target comes first 50 % of the time; p = target first means 2p - 1 of the risk
per trade before costs. Costs 0.25 $ and 0.80 $ per trade (as in every earlier study). One candle touching both
= stop. Neither by 17:00 New York = closed at the last price. POC, VAH and VAL at a moment use only the minutes
closed by then (the page's `profilePath`, checked for look-ahead in `gex_test.cjs`). ATR = mean range of the last
14 one-hour candles. Distances under 0.25 ATR (already at the level) or over 3 ATR are skipped.

| test | moment | direction | target / stop |
|---|---|---|---|
| T1 (4 variants) | Asia 03:00 and London 08:30 New York, price inside or outside the developing value area | toward the developing POC | POC / same distance away |
| T3 | Asia 03:00 | toward yesterday's final POC | that POC / same distance away |
| T4 | London 08:30, when the POC moved 2 $ or more since Asia | with the POC move | 1 ATR / 1 ATR |
| T5 | each POC shift the page announces (2 $, held 2 minutes), before 15:00 NY | with the shift | 1 ATR / 1 ATR, 4 hours at most |
| T6 | the "80 % rule": opened outside yesterday's value area, then two 30-minute closes in a row inside it (before 12:00 NY) | toward the far side of yesterday's value area | that side / same distance away |

T1 "outside" read the other way round (betting price keeps away from the POC) is the trend-day idea: it has an
edge exactly when T1 "outside" is clearly under 50 %.

**Decision rule.** A test is a candidate for a signal only if, on the Dukascopy file (5 years, not looked at for
this study): target first above 50 % (or clearly below, for the reverse trade) in all three periods DEV / VAL /
OOS, |z| >= 3 over all of it (several tests are run at once), the trade still earns after 0.80 $, and the
unseen Binance days lean the same way. Anything else is reported as no edge.

## Findings (first run, 22 Nov 2026; numbers in results/summary.md)

Data: 246 Binance days (Dec 2025 - Nov 2026, the page's own feed) and 1,286 Dukascopy days (Sep 2021 - Sep 2026).

**No test passes the decision rule. None of these POC / value-area patterns is a signal to automate.**

| idea | what happened (Dukascopy 5 years; Binance unseen days) |
|---|---|
| POC as a magnet inside the day (T1 inside) | 50.5 % at Asia, 48.8 % at London; Binance 46 % / 39 %. Price goes back to the POC no more often than to any price the same distance away |
| fade back to the POC when price is outside the value area (T1 outside) | 44.3 % at Asia (z -2.5), 45.5 % at London. Fading a trend day loses: on 5 years -0.29 R per trade after 0.80 $ |
| the same, the other way round: go with the trend day (Asia) | 55.3 % (z 2.3), 54-55 % in DEV and VAL, 62 % in OOS, 63 % on Binance. Before costs +0.10 R; after 0.80 $ -0.08 R over 5 years (stops were 4.5 $ in 2021-24, so the cost ate it), +0.17 / +0.19 R in 2026 when stops were about 29 $. Below the bar (z < 3 with about 16 tests run): the only lean worth a forward test, not proof |
| yesterday's POC as a magnet (T3) | 50.0 % |
| POC moved Asia -> London, go with it (T4) | 48.2 % (DEV 44.7 %, OOS 55.6 %): flips with the period |
| POC shift banner, go with the shift (T5) | 51.8 % over 3,983 races, all periods 51-53 %: real but tiny, -0.08 R after 0.80 $ (races overlap within a day, so z 2.3 overstates it) |
| the "80 % rule" (T6) | 51.9 %: nowhere near 80 % |

What the days look like (no trade): the POC ends the day more than 2 $ from where it stood at the end of Asia on
65-74 % of days; at London 30-41 % of days are already outside the value area and only 36-44 % of those get back
inside by the close; 55-61 % of days close inside their value area. That is the balance-day / trend-day split
seen in the screenshots, but which kind of day it will be is not known in advance from the POC or the value area.

Practical reading: do not fade price back to the POC when it is already outside the value area; the POC lags
moves rather than predicting them. The screenshot month (26 Oct - 20 Nov 2026, gold -600 $) was one long
down-trend, which is why "sell below the value area" looked good on those days.

## Limits

- GEX (option) levels cannot be tested: there is no history of the option chain (only the snapshot the page
  happens to have), and GLD's levels did not match the paid COMEX tool (6 Nov 2026).
- Dukascopy volume is that broker's own, not exchange volume, so its POC can sit a little away from Binance's.
- Binance minutes start on 11 Dec 2025 (when the gold future started).
