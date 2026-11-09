# Gold liquidity heatmap (ATAS / Bookmap style) on free live data

`gold_heatmap.html` draws the order-book heatmap, trade bubbles, candles, delta/CVD and a
bias panel for gold, live, from free exchange feeds. `record.cjs` records sessions for replay.
No install: the page is one file plus `engine.js`, the recorder needs node 22+.

## What the ATAS heatmap actually is

ATAS ("Heatmap" / DOM levels), Bookmap and Jigsaw all draw the same thing:

| Element | Data | Meaning |
|---|---|---|
| Heat colour | Level-2 order book: resting **limit** orders per price, sampled over time | Where passive liquidity sits. Bright = big resting size. A bright horizontal band that holds is a "wall"; one that vanishes as price gets close was pulled (spoof-like); one that keeps refilling while trades hit it is an iceberg |
| Bubbles / cluster | Tape (time & sales): executed **market** orders with aggressor side | Who is hitting the book. Big sells into a bid wall that does not break = absorption |
| Delta / CVD | buy volume − sell volume per bar, cumulative | Aggression trend. Price rising while CVD falls = buyers absorbing sellers (or short covering) |
| Footprint | buy × sell volume per price per bar | Imbalances (diagonal ratio ≥ 3:1) and stacked imbalances |

The logic is not secret, the **data** is: it needs a real order book. Spot gold (XAUUSD at a
forex broker) has no central book. The MT5/cTrader "depth of market" is a few synthetic
liquidity-provider levels, useless for this. The real gold book is COMEX GC futures on CME, and
CME Level-2 data is paid (ATAS, Bookmap, Sierra and Rithmic/CQG all charge for it).

## Free sources used here

| Feed | Instrument | Why it works | Limits |
|---|---|---|---|
| **Binance Futures `PAXGUSDT`** (default) | perpetual on PAX Gold, tracks spot gold | full depth diff stream, ~190k trades/day (~$87M), CORS open, no key | crypto market makers, not COMEX; funding/basis moves it a few $ from XAUUSD |
| Binance Spot `PAXGUSDT` | PAX Gold token | 5000-level snapshot + diff stream | thinner than the perp |
| Bybit `XAUTUSDT` perp | perpetual on Tether Gold | 200 levels per side + tape over one socket | fewer levels |

All three are tokenised gold: price follows XAUUSD within arbitrage (≈0.1–0.3 %), so the
**price action and tape** are usable for gold bias. The **walls** are those of crypto
market makers; treat them as the liquidity of this venue, not of COMEX.

Other free/cheap routes:
- **Bookmap** free plan ("Digital") shows a real heatmap on crypto feeds (Binance, Bybit, ...)
  — the same PAXG/XAUT markets, with Bookmap's own rendering.
- **ATAS** has a 14-day trial; its crypto connections (Binance/Bybit/OKX) work on it.
- **COMEX GC Level-2** cheapest legit route: a futures prop-firm evaluation (Rithmic or
  Tradovate data included, ≈ $50/month) connected to ATAS/Bookmap/Jigsaw, or Sierra Chart with
  the Denali feed. Nothing free exists for CME L2.

Binance note: the futures `@aggTrade` stream stayed silent for PAXGUSDT on 2026-10-20 while
`@trade` delivered, so the futures feed uses `@trade` (liquidation fills are skipped).

## Run

```
start gold_heatmap.html          # any Chromium/Edge/Firefox; it connects on load
node record.cjs                  # record Binance Futures PAXGUSDT, 1 s columns, 0.10 $ rows
node record.cjs --feed bybit --symbol XAUTUSDT --agg 0.25 --column 500 --seconds 3600
```

Recordings go to `recordings\<feed>_<symbol>_<UTC yyyymmdd_hh>.ndjson.gz`, one file per hour
(~3–4 MB/h). Open them with **Load recording** in the page (slider, play, speed).
**Save** downloads what is on screen in the same format.

## Start here: the Key levels panel (left side)

The panel is the plain-language view; the heatmap behind it is the raw data.

- **Price now** — the exchange price, and what it is in XAUUSD terms.
- **Sell orders above price (resistance)** — the biggest clusters of resting sell orders within 1 % above
  the price, nearest first. Each row: price (size-weighted centre), the band it covers, size in ounces,
  how many times a normal band it is, distance, **held** (how long the wall has stood at ≥ half its size)
  and **trend** (growing / shrinking vs 60 s ago). ★ marks the biggest one.
- **Buy orders below price (support)** — the same for resting buy orders.
- **What it means right now** — the nearest and biggest walls on each side, whether the book near price is
  buy- or sell-heavy, what the tape did in the last 5 minutes, pulled walls, absorption and the bias.
- **band $** — width of one price band (0.25 / 0.5 / 1 / 2 $). Neighbouring big bands are merged into one zone.
- **Level bands** on the chart draw the same zones as red (sell) / green (buy) bands with the exact price
  and size, so you can see whether price is heading into a wall.

How to read a wall: a big, long-held, growing wall tends to slow or reject price; a wall that shrinks or
vanishes as price approaches was pulled (spoof-like) and often gets run through. Walls are the liquidity of
this exchange, not of COMEX — treat them as a map of where the venue's market makers sit.

## Why the price is not the same as your MT5 chart

The feeds are tokenised gold (PAXG, XAUT), which trade at a **basis** of a few dollars to spot XAUUSD — the
basis moves slowly with funding and arbitrage (observed +0.5 to +15 $). The page fetches spot XAUUSD from
gold-api.com every 15 s (free, no key) and shows the basis. Press **XAUUSD** under "show prices as" and
every price on the page (axis, levels, tooltips) is shown with the basis removed, so levels line up with
your MT5 chart. If gold-api is down or you prefer your broker's quote, type your MT5 XAUUSD price and
press **Use**; **Auto** goes back to gold-api. Broker quotes also differ from each other by a dollar or
two (spread/markup), so expect ±1 $.

## Reading the page

- Heat: rows = price buckets (**Agg $**), columns = **Column** interval. Colour = log of resting
  size relative to the 98th percentile of the visible window; **Heat** slider = gain. Bid and
  ask liquidity use the same scale (the price line separates them).
- Right ladder: the live book, bars per bucket; **walls** (≥ 8 × the median level) are drawn
  bright with their size and as dashed lines across the chart (red ask, green bid, yellow =
  pulled in the last 10 s).
- Bubbles: trades ≥ **Bubbles** (auto = 95th percentile of the last 10 min). Green = buyer
  aggressor, red = seller aggressor; size ∝ √quantity.
- Candles: **Bars** seconds, built from the tape (hidden when nothing traded).
- Bottom: delta per column (bars) and CVD (yellow line) for the visible window.
- Hover: price bucket, resting bid/ask in that cell, what traded there and the column delta.
- Wheel = price zoom, Shift+wheel = time zoom, drag = pan (switches **Follow** off),
  double-click = follow again. **Footprint** prints sell×buy per cell once cells are large enough.

## Bias score (heuristic — not a backtested edge)

Recomputed every column from the live book and the last 5 minutes of tape:

```
score = 0.30·imbNear + 0.20·imbWide + 0.30·tape5m + 0.20·tape1m
        −0.15 ask wall within 0.10 % above   (+0.10 if that wall was just pulled)
        +0.15 bid wall within 0.10 % below   (−0.10 if pulled)
        ±0.20 absorption (one bucket in the last 2 min took ≥ 3× the average volume,
              price still within 3 buckets of it; sellers absorbed = +, buyers absorbed = −)
imb  = (bid − ask) / (bid + ask) resting size within ±0.05 % (near) / ±0.25 % (wide)
tape = (buy − sell) / (buy + sell) traded volume in the window
BULLISH ≥ +0.25, BEARISH ≤ −0.25, else NEUTRAL; the reasons are listed next to the badge.
```

Use it as a reading aid for the picture, not as a signal. Nothing here has been backtested;
building a signal would need weeks of recordings (`record.cjs`) and the same look-ahead
discipline as the other GOLD studies.

## Files

- `gold_heatmap.html` — the page (UI, rendering, replay)
- `engine.js` — book + tape engine, feed clients (Binance diff-depth sync, Bybit), bias, serialisation
- `record.cjs` — recorder

## Gold GEX view (`gold_gex.html`)

A second page: candles with a guide panel on the left (enter or not, buy and sell zones, price alerts),
absorption areas, a session volume profile and, for gold, the GLD options gamma picture next to the price
scale. Since 7 Nov 2026 the list at the top left switches the instrument: gold, Bitcoin, Ether, Solana,
XRP, EUR/USD, GBP/USD, AUD/USD, USD/CAD, USD/CHF (see "Instruments" below).
Double-click `start_gex.bat`, or:

```
node gex_fetch.cjs              # download the options chain once (writes gex_data.js)
node gex_fetch.cjs --watch 5    # keep it fresh every 5 minutes
```

then open `gold_gex.html`. `node gex_test.cjs` runs the engine checks.

### Read first: what this page is not (found 6 Nov 2026)

The page was built to look like a paid gold GEX tool. It cannot reproduce that tool's levels or signals:

- **The option levels are GLD's, not gold's.** Paid tools use COMEX gold-futures options, which are not
  free. On 6 Nov, around 14:10 IST, such a tool showed Put Wall 0DTE 4090, Zero Gamma 4070 and mostly
  put-heavy strikes near the price. GLD at the same time was call-heavy at every strike from 4030 to 4106,
  its strongest call strike sat at 4095, and its large put positions were at 3986 and below. The two maps
  disagree in sign, not just in strike spacing.
- **A GLD "0DTE wall" is not a well-defined level.** Ranked by live gamma it followed the price (4150 → 4095
  → 4030 through the day, because gamma of an option expiring within hours is a spike at the price). Ranked
  by open interest within 8 % it sat at 4237 and 3768. No definition gives a level worth trading.
- **So signals and MT5 trades do not use option levels at all** (since 6 Nov, 20:00 IST). The lines are drawn
  as context and every label starts with "GLD".
- **The zones copy the tool's boxes as far as we can tell** (since 6 Nov, evening). Its 30-minute supply box
  that day, 4076-4081.25, was the 30-minute candle that made the swing high; the page's sell zone from the
  same rule shows 4075.3-4080.7. What triggers the tool's signal arrows is still unknown.
- **The price is not the broker's.** Candles are Binance XAUUSDT futures (gold perpetual) moved to spot gold
  by the difference to the gold-api.com price, which was 6 to 8 $ through 6 Nov. The feed before that,
  PAXGUSDT, drifted from 7 to 13 $ the same day. The spot reference is a 30-second snapshot and can run a
  minute or two behind in a fast move, so the page uses the 5-minute median of the difference. Expect prices
  within a dollar or two of MT5 in quiet trading and more in fast moves. The exact fix, not built: feed the
  page from MT5's own candles through the EA.
- **Why no alert on 6 Nov:** 144 five-minute closes, 13 confirmed setups, all at value-area edges only,
  scores 12-37; a signal needs 55. `node replay_today.cjs 12` shows the same list for the last 12 hours of any day.

### Instruments (list at the top left, since 7 Nov 2026)

| Instrument | Candles and volume | Price shown | Notes |
|---|---|---|---|
| Gold (XAUUSD) | Binance XAUUSDT futures | moved to spot gold (gold-api.com), 5-minute median of the difference | as before; the only one with option bars and the MT5 bridge |
| Bitcoin, Ether, Solana, XRP | Binance BTCUSDT / ETHUSDT / SOLUSDT / XRPUSDT futures (buy / sell volume included) | moved to Coinbase's USD market (BTC-USD etc.), same median rule | 7 Nov: BTC futures sat 60-70 $ above Coinbase, SOL 0.10 $ |
| EUR/USD, GBP/USD, AUD/USD, USD/CAD, USD/CHF | Kraken's fiat markets (real EUR/USD etc.) | as traded, no shift | small market next to interbank: a few pips off a broker at times, spiky at weekends; no buy / sell split (no absorption areas, neutral tape); only the last 12 hours of 1-minute candles; polled every 3 s (Kraken allows about one request a second) |

- Changing the instrument reloads the page. Zones, ideas, alerts and the price shift are kept per
  instrument (gold keeps its old storage keys, so nothing of the gold setup moved).
- **USD/JPY, EUR/JPY and the other crosses are not offered**: on Kraken they traded 0-233 units in 12 hours
  (7 Nov), i.e. no candles. Binance has no forex at all. The free way to get them, and the broker's exact
  prices for everything, is the MT5-candle feed through the EA, which is not built.
- Rules are the same for every instrument. Gold's fixed dollar numbers (1.5 $ level bands, 0.5 $ value-area
  rows, "within 2 $ of a zone") become the same share of the price elsewhere; everything else (zone height,
  stops, targets) was already in ATR units. The stop-size check uses the broker contract size of the
  instrument (100 oz, 1 coin, 100,000 units) at 0.01 lot and converts USD/CAD and USD/CHF risk to USD;
  XM's crypto contract sizes are assumed to be 1 and the checklist says so.
- **Nothing has been backtested on the other instruments.** The rules were tested on 5 years of gold only
  (no edge there either, see below). On crypto and forex the guide is an untested checklist with alerts.
- **Thin-market prints are clipped.** Kraken's fiat pairs show single trades far from the market (7 Nov:
  EUR/USD 1.0808 while the market was at 1.11, USD/CAD 1.45, USD/CHF 0.859, GBP/USD 1.361; 20-90 × the ATR),
  which would become zones and inflate the ATR. A wick that reaches further beyond the candle's open / close
  than 3 × the 95th-percentile range of the series is cut there (3-9 of 720 thirty-minute candles, 0-5 of
  720 one-minute candles on 7 Nov; ATR unchanged). A move that closes at such a price is kept.
- Weekends: Kraken keeps trading fiat pairs thinly while brokers are closed; the status line says so.

| On screen | What it is |
|---|---|
| Bars on the right | GLD gamma exposure per strike, in $ per 1 % move. Green = calls outweigh puts, red = puts outweigh calls. Dropdown: net GEX, total GEX, call / put open interest (two bars per strike: green = call OI, red = put OI), net volume. `All` = every expiry, `0DTE` = the nearest expiry only |
| GLD Call Wall / Put Wall 0DTE (dashed) | Strike of the nearest expiry with the most call / put open interest (calls minus puts) within 3 % of the price; not drawn when there is none that close. Context only |
| GLD Zero Gamma 0DTE (blue) | Price where the nearest expiry's net gamma changes sign, found by re-pricing every contract at prices within ±8 %. Context only |
| GLD CW1-3 / PW1-3 (dotted) | Three biggest green / red strikes across all expiries, within 8 % of the price. Context only |
| Boxes | Buy and sell zones. Red = sell zone: the candle that made a swing high (its high above the two candles before and the one after) on the 30-minute or the 1-hour chart. Green = buy zone: the same at a swing low. At most half an ATR tall, measured from the swing's extreme. Pale once price has left the zone and come back; removed when a candle of its timeframe closes through it. `30m & 1h` = both timeframes mark the same swing |
| Thin bands | Absorption areas. Over 5 minutes the traded volume was at least 1.5 × normal, at least 15 % one-sided, and price still closed in the half of the range away from the attack. Blue = buyers absorbed, pink = sellers absorbed (the shown side is the inverse of the engine's internal kind, which is unchanged). From the buy / sell volume of Binance XAUUSDT futures. Removed when a 1-minute candle closes through the band, or after 8 hours. Shown, not scored |
| Orange dashed lines | Price alerts you set |
| Profile | Volume by price since 18:00 New York. Yellow = POC, purple = 70 % value area |

Everything follows the market while the page is open: candles, live price and the signal check every
second, gamma bars every 5 s (gamma is re-priced at the live price, so the bars and zero gamma move with
it), zones every minute.
Only open interest and implied volatility wait for the next `gex_fetch.cjs` download. Just before the US
open (about 09:00-09:30 New York) CBOE's file mixes fresh and stale values per expiry, so bar sizes are
rough then.

### Guide panel (left side, button `Guide`)

The box at the top says what to do now, from closed 5-minute candles, whatever timeframe the chart shows:

| Headline | Meaning |
|---|---|
| WAIT | Price is between zones. No trade |
| GETTING CLOSE | A zone is within one 5-minute ATR. Nothing to do yet |
| GET READY TO BUY / SELL | Price is at a zone or a value-area edge, but no candle has turned. No entry |
| BUY / SELL IDEA OPEN | A candle went into the level and closed back out in the far 40 % of its range, and the score is 55 or more. Entry, stop and target are listed. This is the only state that sounds the siren and is sent to MT5 |
| NO: SKIP THIS ONE | A candle turned, but the target is closer than 1.2 × the stop, the stop is too wide, or the score is under 55 |

- **Before you enter** is the same judgement as a checklist, each point with a tick or a cross: price at a
  zone, a 5-minute candle closed back out, target at least 1.5 × the stop, with or against the 30-minute
  trend, stop no wider than 3 % of the account at 0.01 lot (the balance comes from MT5 when it is connected,
  or click `change`), not a usual US data time (08:30 and 10:00 New York; it is a clock, not a calendar),
  and the score.
- **Sell zones above / buy zones below**: the three nearest of each, with distance, timeframe and whether
  price has been back to them. The nearest one shows a rough plan (entry at the near edge, stop 0.3 × ATR
  beyond the far edge, target at the next level in the way) and says when there is too little room.
  `+ alert` sets a price alert at the zone's near edge.
- **Score** = points for each condition that agrees: levels reached (zone 30, tested zone 18, value-area edge
  12; up to 45), 30-minute trend with the trade (+10, against −10), buying or selling in the last 15 minutes
  (+10 / −5), quality of the rejection candle (+10 / +5), reward at least 2 × / 1.5 × the risk (+10 / +5).
  The most a setup can reach is 85. Option levels and absorption are not counted.
- One idea at a time. An idea is stored at the close of its trigger candle and never edited; 1-minute candles
  then decide its result: target, stop (stop wins if one candle touches both) or timed out after 4 hours.
  The panel counts the finished ideas.

### Price alerts

Like a TradingView alert: a price, and the alarm rings once when gold gets there.

- Set one by typing a price in the guide, by holding Alt and clicking the chart, by right-clicking the chart,
  or with `+ alert` next to a zone or an absorption area. An orange dashed line marks it.
- Remove it with `remove` in the list, or right-click the line.
- It rings when the page's gold price crosses it in the direction it was set from (above the price = on the
  way up). The newest 1-minute candles are checked too, so a spike between two checks counts. A fast trill
  for 20 seconds, a banner and a flashing tab title, until the banner is clicked.
- Alerts are kept in the browser, so they survive a reload. One that has rung stays in the list for 12 hours.
- "Short tone when price reaches a zone" (on by default): a 4-second tone and a GET READY banner when price
  arrives at a zone or a value-area edge, at most once per level in 30 minutes.
- The page must be open in a visible window, and the price is the page's, not the broker's (see "Read first").
- **Alarm** (button in the top bar, on by default): a new BUY or SELL sounds a 30-second siren (high and
  fast for buy, low and slow for sell), shows a flashing banner with entry, stop and target, and flashes
  the tab title until the banner is clicked. A 3-second sound follows when the idea hits its target or stop.
  Browsers allow sound only after one click on the page: the button reads "Alarm: click to arm" until then.
  The page plays at full scale, so loudness is set by the PC volume. Keep the tab in its own visible window:
  a hidden tab is checked about once a minute, and a tab the browser has put to sleep is not checked at all.

### Trading the signals on an MT5 demo account

```
gold_gex.html --POST--> gex_agent.cjs --file--> GexSignalTrader EA in MT5 --> order on the demo account
              <--status--               <--file--
```

One-time setup in MetaTrader 5 (the account must already be logged in; no password is needed anywhere here):

1. Navigator → Expert Advisors → GEX → drag **GexSignalTrader** onto the gold chart (GOLD, GOLD.i#, ...).
2. In its dialog tick "Allow Algo Trading", then make sure the **Algo Trading** button in the toolbar is green.
3. Phone alerts (optional): Tools → Options → Notifications, enter the MetaQuotes ID from the MT5 phone app.

Every session: run `start_gex.bat` (page + agent), then click **MT5** on the page so it reads "MT5 on".
The bottom of the guide panel then shows `MT5: ready, demo account, <symbol>, balance ...` and, after a signal, what the
EA did. "send a test trade" on that line places one small BUY (stop 5 $, target 10 $) to prove the chain.

- **What the EA does with a signal:** market order in the signal's direction, stop and target at the same
  distances as on the page, measured from the broker's own price (bid for a buy, ask for a sell). Lot size
  from `InpRiskPercent` (1 % of balance by default) or `InpFixedLots`. One GEX trade at a time. Closed at the
  market after `InpCloseHours` (4). MT5 popup + sound on every action, push to the phone if set up.
- **What it refuses:** a real account (unless `InpAllowReal`), a signal older than 120 s, a spread above
  `InpMaxSpread` (1.00), a second trade while one is open, Algo Trading off. `InpDryRun` reports what it
  would do without placing an order.
- **Safety:** the agent listens on 127.0.0.1 only and every request needs the token in `gex_agent_info.js`,
  which other web sites cannot read. The agent never places orders; it only writes
  `Common\Files\gex_signal.txt` (one line: `id;BUY|SELL;entry;stop;target;score;sent`). The EA answers in
  `gex_status.txt` and writes a heartbeat to `gex_ea.txt` every 5 s. Sent signals are logged in
  `mt5_signals.log`.
- Source: `mt5/GexSignalTrader.mq5` (copy in the terminal's `MQL5\Experts\GEX\`, compiled 0 errors).
  `node gex_agent.cjs --test buy` sends a test signal from the command line.

The score counts agreement. It is not a win probability.

**Backtests (6 Nov 2026, `../gex_signals/`):**

- The guide's BUY / SELL ideas with the current swing zones, on 5 years of 1-minute gold with this same
  engine code: 2,859 ideas (about 560 a year), −0.03 R per trade before costs, −0.17 R at a 0.25 $ cost,
  −0.47 R at 0.80 $. Negative in every period. A higher score did not mean a better trade.
- The first version's impulse zones gave the same picture with fewer ideas (572, +0.01 R before costs).
- Absorption areas on 90 days of XAUUSDT: trading with the absorbing side when an area appears made +0.05 R
  before costs (not significant) and −0.10 R at 0.25 $; trading the first return to the area lost 0.10 R
  even before costs. They are drawn as context and not scored.
- The options half (walls, zero gamma) has no free history and is not used by the guide.
Where the numbers come from:

- **Options: GLD (the gold ETF), from CBOE's free delayed quotes**, about 15 minutes behind; open interest
  changes once a day. COMEX gold-futures options, which paid GEX tools use, are not free. GLD strikes are
  about 10.9 $ apart in gold terms, and its positions are a different market's: they did not resemble a
  COMEX-based tool's levels on 6 Nov 2026 (see "Read first").
- **GLD → gold price:** one GLD share holds 0.1 oz less a 0.40 % yearly fee since Nov 2004, which gives
  10.920 × on 6 Nov 2026 (checked: GLD closed 375.49 with gold near 4100).
- **Gamma** is recomputed at the live gold price with Black-Scholes from each contract's implied volatility,
  so the bars move with price. Against CBOE's own gamma at the close the model is within 2 %.
- **Candles and volume:** Binance XAUUSDT futures (gold perpetual), shifted to spot gold with the
  gold-api.com price (5-minute median of the difference). The volume profile and the absorption areas are
  therefore that contract's volume, about 880,000 oz a day on 6 Nov, not COMEX volume. Crypto: the same
  from Binance futures, shifted to Coinbase. Forex: Kraken's fiat markets, no shift (see "Instruments").
The option lines, zones and profile are reading aids. The signal rules were backtested and showed no edge.

- `gold_gex.html` — the page
- `gex_engine.js` — gamma, walls, zero gamma, zones, volume profile (pure functions, also used by the test)
- `gex_fetch.cjs` — CBOE download → `gex_data.js` (generated, git-ignored)
- `gex_test.cjs` — checks, including the gamma model against CBOE's gamma
- `start_gex.bat` — download, open the page, keep refreshing
