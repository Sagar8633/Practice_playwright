# SRK Swing Alerts — every NSE F&O stock, 15m, bullish + bearish

Two ways to get the same signal, both free. Use either or both.

| | **A. TradingView** | **B. Local watcher** |
|---|---|---|
| Where the alert appears | **phone push + any signed-in device** — the alert lives on your account, not a machine | Windows notification on **this PC only** |
| Coverage | 40 stocks per script | **all 212 F&O stocks at once** |
| Cost | free, but limited by your alert quota | free, no quota, ever |
| Needs TradingView open? | no (alerts run on their servers) | no |
| Needs your PC on? | no | **yes** |
| Reaches your phone? | **yes** | no |
| Alerts expire? | yes on free plans | never |

**A is the one that reaches your phone** — its alerts live on your TradingView
account, so they fire whether or not this PC is on. **B** never expires and
covers every symbol, but only notifies the machine it runs on.

Run both: A on your phone for the names you trade, B on the PC as the
never-expiring backstop across the full list. They use the identical rule.

```
deploy_helper.py                  copy-paste helper for loading (A) into TradingView
pine/srk_swing_scanner_b1..b6     all 212 names, 40 per script, b1 = busiest
run_watcher.bat                   double-click to start (B)
watch.py                          the watcher CLI
verify.py                         offline check that the rule matches your chart
rank_universe.py                  reorders fno_symbols.txt by traded value
generate_scanners.py              rebuilds pine/ from fno_symbols.txt
fno_symbols.txt                   the 212-name F&O universe, in turnover order
data/signals.csv                  every signal ever raised
```

---

## The rule

On **closed 15-minute candles**, per symbol:

| | |
|---|---|
| **BULLISH** | EMA stack flips to Red(5) > Green(10) > Blue(20), straight from the bearish stack, ADX(14) > 20 |
| **BEARISH** | EMA stack flips to Blue(20) > Green(10) > Red(5), straight from the bullish stack, ADX(14) > 20 |
| **SL** | low of the candle *before* the flip (bullish) / its high (bearish) |

That produces about **18 alerts a day across all 212 stocks** — measured over 7
real sessions, not guessed. See *Tuning* below for how that number was chosen and
how to move it.

---

## A. TradingView alerts

### Why several scripts instead of one

Two hard limits collide:

1. **Pine allows 40 `request.security()` calls per script.** One script watches
   at most 40 symbols. No plan lifts this — it is a Pine limit.
2. **An alert attaches to a script, not a symbol.** Normally that means 212
   stocks = 212 alerts, which no plan below Premium allows.

The scanner sidesteps (2) by calling `alert()` from inside the script with a
message it builds itself. **One alert covers all 40 symbols in that script**, and
names whichever fired:

```
SRK Swing 15m - 2 signal(s)
BULLISH  IDFCFIRSTB  @ 84.86  | SL 84.56  | ADX 24.4
BEARISH  TATASTEEL   @ 168.20 | SL 169.05 | ADX 31.7
```

So the full F&O list costs **6 alerts**, not 212.

### What a free (Basic) account can do

Two different quotas bite:

- **Indicators per chart** — Basic allows 2. At most 2 scanner scripts can be
  *visible* on one chart: 80 symbols of live panel.
- **Active alerts** — Basic allows only a handful. Check the Alerts panel; it
  shows `used / total`. Each script needs exactly 1.

The useful part: **an alert keeps running after you remove the indicator from the
chart** — TradingView stores a copy of the script inside the alert. So:

1. Add `b1` to the chart → create its alert → remove `b1` from the chart.
2. Add `b2` → create its alert → remove `b2`. Repeat to your quota.

Verify with one alert before relying on it; if your plan behaves differently the
alert will show as inactive in the Alerts panel.

**Which 40 go in which script matters.** `fno_symbols.txt` is sorted by average
daily traded value (`rank_universe.py`), so `b1` holds the 40 busiest F&O stocks
and each later batch matters less. Coverage then degrades gracefully at whatever
quota you have — 3 alerts still gets you the 120 most-traded names, not an
arbitrary alphabetical slice.

**At 5 alerts (free plan): deploy b1–b5.** That is 200 of 212 names — the hard
ceiling, since Pine caps a script at 40 symbols. Only `b6` is left out: the 12
thinnest names plus the four indices, which sort last because Yahoo reports no
volume for them. If you want NIFTY and BANKNIFTY covered, move them to the top of
`fno_symbols.txt` and re-run `python generate_scanners.py`.

Free-plan alerts also expire and need re-creating. That expiry is the reason
option **B** exists — it is the part that cannot silently stop.

### Setup

Run the helper — it serves a page with a Copy button per script and the exact
click-path for the alert dialog:

```
python deploy_helper.py
```

Or do it by hand:

1. TradingView → **Pine Editor** → **Open → New indicator** → paste all of
   `pine/srk_swing_scanner_b1.pine` → **Save** → **Add to chart**.
2. Put the chart on the **15m** timeframe.
3. `Alt+A` to add an alert:
   - **Condition** → `SRK Swing Scanner B1 (15m)`
   - dropdown below it → **Any alert() function call**
   - **Notifications** tab → tick **Notify on app** (this is the mobile push),
     plus **Show popup** and **Play sound** for the desktop browser
   - leave the message box alone — the script writes it
   - **Expiration** → as far out as your plan allows
4. **Create.** That one alert now watches 40 symbols.

### Where the alert actually arrives

TradingView alerts run on **TradingView's servers and belong to your account,
not to a device**. Create the alert once, from anywhere, and it reaches every
place you are signed in:

| Channel | Works on free plan | Needs |
|---|---|---|
| **Phone push** | yes | TradingView mobile app installed, signed into the same account, *Notify on app* ticked, and OS notification permission granted to the app |
| Browser popup + sound | yes | a TradingView tab open on that machine |
| Email | yes | *Send email* ticked |
| Webhook | no — paid tiers | — |

So **your PC can be off, your laptop closed, and the phone still buzzes** with
the stock name in the message. That is the reason to run (A) even though (B)
covers more symbols: (B) is Windows-only and dies with the machine.

Tick *Notify on app*, then wait for the first real signal (or temporarily set
*ADX threshold* to 0 on one script to force one) and confirm the phone buzzes
before relying on it.

Repeat for `b2`…`b6` as your quota allows. If TradingView complains the script
takes too long, regenerate smaller ones: `python generate_scanners.py --per-script 20`.

**These alerts are live-only by construction.** TradingView ignores `alert()` on
historical bars, and the script additionally gates on `barstate.isconfirmed` with
`alert.freq_once_per_bar_close`, so nothing fires until a real 15m candle closes
while the alert is active. Creating an alert never replays the past.

The *chart* still draws past triangles and the panel still shows every symbol's
current trend — that is display, not alerts. To strip the history off the chart,
untick **Draw signals on this chart's own symbol** in the indicator settings.

---

## B. Local watcher — no quota, all 212 stocks

```
run_watcher.bat                    double-click; leave the window open
```

or from a terminal:

```
python watch.py                    # all 212 names, live, until you stop it
python watch.py --once             # one sweep now
python watch.py --test-alert       # prove notifications work on this PC
python watch.py --only IDFCFIRSTB RELIANCE
```

A full sweep of all 212 symbols takes **~9 seconds**, so it comfortably finishes
inside every 15-minute bar. Candles come from Yahoo's public chart API — no
login, no key, no token to refresh each morning.

Each signal raises its own Windows notification naming the stock:

```
BULLISH  IDFCFIRSTB
15m @ 84.86   SL 84.56   ADX 24.4
bar 02-Sep 10:30   NSE:IDFCFIRSTB
```

Everything also lands in `data/signals.csv`.

### Why it does not miss or repeat signals

- Each sweep re-checks the **last 4 closed bars**, not just the newest one. If
  Yahoo publishes a bar late, the next sweep still catches it.
- Every signal is keyed by `(symbol, direction, bar time)` in
  `data/seen_signals.json`, so a re-checked bar — or a restart — never notifies
  twice.
- It only ever reads **closed** bars. A forming candle can un-cross before it
  ends; TradingView does not plot those, and neither does this.
- It never announces a bar that closed before the watcher started — see below.

### Live only — history never alerts

The watcher announces a signal **only if that bar closed while it was running**.
Start it at 11:00 and the 10:45 signal stays silent, however loud it was.

Two guards, whichever is stricter:

- **Launch time.** Every bar that had already closed when you started is marked
  as seen and skipped. This is what stops a mid-session start from dumping the
  morning on you, and a 09:30 start from replaying yesterday.
- **45 minutes** (`--max-age`). Once the watch has been up a while, this keeps a
  late-published bar announceable while still refusing a stale one.

The comparison uses the bar's **close**, not its open — a 10:00 candle is only
decided at 10:15, and that instant is what "live" means.

Measured against a real session that produced 16 signals on bars closing
14:30–15:30:

| Watcher started | Alerts raised |
|---|---|
| 15:20 | **5** — only the bar closing 15:30 |
| 14:50 | **12** — bars closing 15:00, 15:15, 15:30 |
| 09:00 | **16** — the whole session was live |
| after hours, default settings | **0** |
| `--catch-up` | 16 — deliberately replays the window |

`python watch.py --once` also replays deliberately; that is what it is for. Only
`--catch-up` makes the *live loop* do it.

### Daily routine

**None.** Start it once and leave it; it handles the rest:

| | |
|---|---|
| Outside 09:15–15:30 IST, and weekends | idles, costs nothing |
| Next morning at 09:15 | wakes up and scans on its own |
| PC rebooted / watcher was off yesterday | picks up cleanly — see below |
| Yahoo publishes a bar late | next sweep catches it (4-bar recheck) |
| A sweep fails (wifi drop) | logged, loop continues |

The one thing worth knowing: each sweep re-examines the **last 4 closed bars**,
and at 09:30 three of those belong to *yesterday*. The live loop therefore
ignores any bar older than 45 minutes (`--max-age`), so a morning start never
greets you with a screenful of alerts for yesterday's prices. Verified: on a
fresh state file after hours, the live path raised **0** alerts while the manual
path found the session's 16.

That guard applies only to the live loop. `python watch.py --once` deliberately
catches up and shows you the last session in full.

### Starting it automatically

Task Scheduler → Create Task → Trigger *At log on* (or daily 09:10) → Action
*Start a program* → `d:\Practice_Playwright\srk_swing_alerts\run_watcher.bat`.
It idles outside 09:15–15:30 IST on weekdays, so leaving it running costs
nothing.

If notifications do not appear: Settings → System → Notifications must be on,
and Focus Assist / Do Not Disturb must be off.

---

## Tuning it to match your chart

**Read this before you trade it.** The bare stack-flip rule fires far more often
than the SRK indicator plots triangles — on IDFCFIRSTB 15m it gave 8 signals
between 26-Aug and 04-Sep where your chart showed 1. The EMA ribbon is confirmed
correct (5/10/20 reproduces the `87.57 / 87.35 / 86.88` on your status line); the
*filter around the flip* is what differs.

Measured across all 212 names over 7 sessions:

| Setting | Alerts/day | Per 15m bar |
|---|---:|---:|
| loose flip, ADX > 20 | 121 | 4.8 |
| loose flip, ADX > 30 | 44 | 1.8 |
| **require flip from opposite stack, ADX > 20  ← default** | **18** | **0.7** |
| require opposite, ADX > 25 | 9 | 0.4 |
| require opposite, ADX > 30 | 5 | 0.2 |

The default was picked because your screenshots show roughly one signal per stock
per 7–8 sessions, which across 212 stocks is ~25–30 a day — the same order as 18,
and nowhere near 121.

To move it, in the Pine **Noise filters** group, or on the watcher CLI:

| Want | Pine | Watcher |
|---|---|---|
| more signals | untick *Require a flip from the opposite stack* | `--loose` |
| most signals | also untick *Only alternate signals* | `--all-flips` |
| fewer signals | raise *ADX threshold* to 25–30 | `--adx 25` |
| space them out | raise *Minimum bars between signals* | `--cooldown 8` |

**To match the SRK arrows exactly**, the one thing that would settle it is the
indicator's own source: open it in Pine Editor → *Source code*, and paste it in.
Its signal condition can then be transplanted directly, and the guessing stops.

### Checking without waiting for the market

`verify.py` recomputes the identical rule on historical 15m candles and prints
every signal with its timestamp, so you can hold it against the chart:

```
python verify.py IDFCFIRSTB --days 14
python verify.py RELIANCE TCS SBIN --adx 25
```

It sends no alerts.

---

## Regenerating

Edit `fno_symbols.txt`, then:

```
python watch.py --validate --write           # drop symbols the feed cannot serve
python rank_universe.py                      # re-sort by traded value
python generate_scanners.py                  # rebuild pine/
python deploy_helper.py                      # rebuild + serve the copy page
python generate_scanners.py --per-script 20  # if a script times out on TradingView
python generate_scanners.py --timeframe 5    # a 5m variant
```

Run them in that order — validate, rank, generate, deploy.

The F&O list came from your broker scrip master
(`../option_chain_reader/data/scrip_master.json`); NSE revises it every few
months. It has been filtered to symbols Yahoo serves — `FOCIT` was dropped as a
404, so it is absent from the Pine batches too even though TradingView may carry
it. Add it back to `fno_symbols.txt` by hand if you want it on the TradingView
side.

Symbol names convert to TradingView form automatically: `M&M` → `NSE:M_M`,
`BAJAJ-AUTO` → `NSE:BAJAJ_AUTO`, `FINNIFTY` → `NSE:CNXFINANCE`.
