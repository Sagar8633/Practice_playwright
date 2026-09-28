"""One-off: adds the phase 16 (daily trend-following) block to build_master_ledger.py and the trend scripts to README.md."""
s = open("build_master_ledger.py", encoding="utf-8").read()
block = r'''
# phase 16 daily trend-following (Dukascopy D1 2003-2026, XM costs incl. long swap at today's rate)
if os.path.exists("results/trend/trend_lab.json"):
    TL = json.load(open("results/trend/trend_lab.json")); TK = "Dukascopy XAUUSD daily bid 2003-2026 (7,378 days)"; TX = "fills at the next daily open (ask for buys), stops on the daily low/high with gap fills, spread 0.32-0.51, swap long -0.020%/night short +0.005%, 1% risk or 10% vol target"
    for r in TL:
        sw = r.get("swap", {}); f = lambda p, k, d=3: (f"{sw[p][k]:.{d}f}" if p in sw and sw[p].get(k) is not None else "")
        st = "CONTROL" if r["rule"].startswith("C") else ("CANDIDATE" if r.get("retained") else "REJECT")
        add("daily OHLC, 23 years", r["rule"], "slow trend-following (published family)", TK, sw.get("full", {}).get("trades", ""), f"CAGR {f('DEV 2003-2013','cagr')} PF {f('DEV 2003-2013','pf',2)} DD {f('DEV 2003-2013','max_dd',2)}", f"CAGR {f('VAL 2014-2019','cagr')} PF {f('VAL 2014-2019','pf',2)} DD {f('VAL 2014-2019','max_dd',2)}", f"CAGR {f('OOS 2020-2026','cagr')} PF {f('OOS 2020-2026','pf',2)} DD {f('OOS 2020-2026','max_dd',2)}", "XM spread by year + today's swap at every price level", TX, st,
            "positive CAGR, PF > 1.1, DD < 40% in DEV, VAL and OOS and above the random control; low single digits a year at 1% risk" if st == "CANDIDATE" else ("control" if st == "CONTROL" else "fails at least one period after costs (mostly VAL 2014-2019, when gold was flat, or shorts)"), "P16")
'''
marker = 'os.makedirs("results/ledger", exist_ok=True)'
if "# phase 16 daily trend-following" not in s:
    s = s.replace(marker, block + marker); open("build_master_ledger.py", "w", encoding="utf-8").write(s)
r = open("README.md", encoding="utf-8").read()
rows = ("| `tools/fetch_daily.js` | Dukascopy XAUUSD daily and 4-hour bid candles, full history, into `data/xauusd_{d1,h4}_bid.csv`. |\n"
        "| `trend_bot_lab.py` | Phase 16: frozen trend-following rules on daily gold 2003-2026 (Turtle 20/10 and 55/20, SMA 50/200, time-series momentum 1/3/6/12 months, Faber 10-month SMA, long/short splits, buy-and-hold and random controls) with XM spread and the long swap; DEV 2003-2013 / VAL 2014-2019 / OOS 2020-2026 (`results/trend/`). |\n"
        "| `trend_bot_followup.py` | Risk scaling 1-3%, both Turtle systems on split capital, minimum account for the 0.01-lot step, gold's own yearly return net of swap (`results/trend/followup.json`). |\n"
        "| `make_trend_report.py` | Builds `trend_report.html` (page \"Gold Trend Bot\"). The EA is `../mt5/GoldTrend_D1.mq5` (demo-only by default). |\n")
if "trend_bot_lab.py" not in r:
    r = r.replace("| `tools/regression.py` |", rows + "| `tools/regression.py` |"); open("README.md", "w", encoding="utf-8").write(r)
print("patched")
