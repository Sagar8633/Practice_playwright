"""Render data/DATA_AUDIT.md from the per-instrument audit.json files written by prep_data.py."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ["eurusd", "gbpusd", "usdjpy", "audusd", "usdcad", "usdchf", "nzdusd", "xagusd", "btcusd", "lightcmdusd"]
NAME = {"eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY", "audusd": "AUDUSD", "usdcad": "USDCAD", "usdchf": "USDCHF", "nzdusd": "NZDUSD", "xagusd": "Silver (XM SILVER)", "btcusd": "Bitcoin (XM BTCUSD)", "lightcmdusd": "US Oil (XM OILCash)"}
SRC = {"dukascopy": "Dukascopy M1 bid (dukascopy-node)", "fallback": "FXCM candle archive (majors) / Binance BTCUSDT (bitcoin)", "none": "none available (Dukascopy rate-limited; no free alternative)"}
L = ["# Data audit: forex majors, silver, bitcoin, US oil (28 Sep 2026)\n",
     "Three path resolutions per instrument, all in XM server time (EET, UTC+2/+3):\n",
     "* **1-minute path** (timeframes 1m to D1): Dukascopy was the planned source, but its data feed rate-limited this machine (HTTP 429 for hours after three parallel downloaders were started). "
     "The seven majors therefore use FXCM's public minute archive (`candledata.fxcorporate.com`, UTC, bid OHLC, no volume, weekly files; holes: 2024 weeks 35 and 51-53, 2025 weeks 1-2 and 29-30, 2026 weeks 18-20 and 38-39 are absent, so June-July 2026 and late September 2026 are missing), bitcoin uses Binance BTCUSDT 1-minute klines (UTC, volume present, complete). Silver and oil have no free minute source and are tested from 15 minutes up.",
     "* **15-minute path** (timeframes 15m to D1 for silver and oil): XM's own M15 bars pulled from the terminal, about Sep 2022 (silver/oil: Jul 2022) to Sep 2026, with XM's spread and tick volume.",
     "* **Hourly path** (the long D1 test, 2015-2026): XM's own H1 bars for every symbol, with spread and tick volume. XM's H1 spread by year and server hour is also the spread model of every run.\n",
     "No bar is filled or interpolated. Timestamps: UTC sources converted with the EU-DST rule; XM bars are already in server time.\n",
     "| Instrument | 1-minute source | M1 months (missing) | M1 rows | Dups | OHLC errors | Intraweek gaps > 1 min (hours lost) | Gaps > 40 h | Volume in M1 | XM vs M1 close diff (pts, median / p99) | XM M15 from | XM H1 from | XM spread by year (pts) |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for k in ORDER:
    f = os.path.join(ROOT, "data", k, "audit.json")
    if not os.path.exists(f): continue
    a = json.load(open(f)); m = a.get("m1", {}); x = a.get("xm", {}); sp = a.get("xm_h1_median_spread_by_year", {})
    spy = ", ".join(f"{y}: {v}" for y, v in sp.items() if int(y) >= 2021)
    L.append(f"| {NAME[k]} | {SRC.get(a.get('m1_source'), a.get('m1_source'))} | {a.get('m1_months_present')} ({', '.join(a.get('m1_months_missing', [])) or 'none'}) | {m.get('rows', 0):,} | {m.get('duplicates', '')} | {m.get('ohlc_violations', '')} | "
             f"{m.get('intraweek_gaps_gt_step', '')} ({m.get('intraweek_gap_hours_total', 0):.0f}) | {len(m.get('gaps_over_40h', []))} | {'yes' if a.get('has_volume') else ('no' if m else '')} | {x.get('close_diff_median_pts', '')} / {x.get('close_diff_p99_pts', '')} | "
             f"{a.get('m15', {}).get('first', '')[:10]} | {a.get('h1', {}).get('first', '')[:10]} | {spy} |")
L.append("\n## Notes\n")
L.append("* Where the minute data carries no volume (FXCM), the EA's volume filter is switched off for those runs and the report says so; on the XM 15-minute and hourly paths and on Binance the filter runs on real (tick) volume, which is what the EA sees in MetaTrader.")
L.append("* Weekend bars exist only for bitcoin (24/7). Silver keeps XM's 01:00-23:58 metals session; forex and oil keep their sources' coverage.")
L.append("* XM's prices differ from the fallback feeds by a few points at the median (FX) and by a constant level of about $21 for bitcoin (BTCUSDT versus XM's USD contract); stop distances and the strategy's relative moves are unaffected.")
L.append("* Prices are float32 in the caches for forex, silver and oil (7 significant digits) and float64 for bitcoin.")
L.append("* Look-ahead: signals use completed bars only; fills, stops and trailing are evaluated on the next path bar's range. On the 15-minute and hourly paths the intrabar order of events inside a bar is unknown; the same conservative rules as in the gold study apply (existing stop first, then fills, then stop moves).")
open(os.path.join(ROOT, "data", "DATA_AUDIT.md"), "w", encoding="utf-8").write("\n".join(L)); print("written data/DATA_AUDIT.md")
