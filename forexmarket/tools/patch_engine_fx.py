"""Generalise the gold engine to any XM instrument: point size, contract size, swap points and the triple-swap weekday become
run parameters; the path loader takes an instrument key and an optional session rule; the spread model is per instrument
(data/xm/spread_models.json: {instrument: {year: [24 hourly medians in points]}}); allow_buy/allow_sell gates as in the Indian
port. Run once on strategy/engine_fx.py (a copy of Vaibhav/research/sma18_engine.py)."""
import os, re

ENG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy", "engine_fx.py")
s = open(ENG, encoding="utf-8").read()
if "swap3day" in s:
    print("already patched"); raise SystemExit


def sub(old, new, count=1):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, count)


# ---------------------------------------------------------------- header
s = s.replace(s[: s.index("from __future__")], '''"""Multi-instrument port of the SimpleSMA18Bot research engine (XM Global MT5 symbols: forex majors, SILVER, BTCUSD, OILCash).

Same simulation core as ../../Vaibhav/research/sma18_engine.py (exact v1.00 rule port validated against the MT5 tester in the gold study).
Changes: point size, contract size, swap points and the triple-swap weekday are parameters (Params.point / contract / swap_long_pts /
swap_short_pts / swap3day); the path loader takes an instrument key (data/<instrument>/m1_server.npz, built by tools/prep_data.py in
XM server time) and an optional session rule; the spread model is per instrument and per year x server hour, built from XM's own bars;
allow_buy / allow_sell arrays gate setups per signal bar for experiment filters. Money is in the QUOTE currency of the instrument for
`lots` lots (e.g. 0.01 lot of EURUSD = 1,000 EUR: 1 pip = 0.10 USD); common_fx.py converts to USD where the quote currency is not USD.
"""
''')
# ---------------------------------------------------------------- constants / params
sub('HERE = os.path.dirname(os.path.abspath(__file__))\nDATA = os.path.join(HERE, "data")\nPOINT = 0.01\nCONTRACT = 100.0',
    'HERE = os.path.dirname(os.path.abspath(__file__))\nDATA = os.path.join(os.path.dirname(HERE), "data")\nPOINT = 0.01      # default only; the run uses Params.point\nCONTRACT = 100.0  # default only; the run uses Params.contract')
sub('    tf_minutes: int = 1440\n    lots: float = 0.01\n', '    tf_minutes: int = 1440\n    lots: float = 0.01\n    point: float = 0.00001            # instrument point (MT5 semantics)\n    contract: float = 100000.0        # units per 1.00 lot\n    swap_long_pts: float = 0.0        # XM swap in points per night\n    swap_short_pts: float = 0.0\n    swap3day: int = 2                 # weekday (Mon=0) whose rollover charges 3 nights; -1 = never\n    swap_daily: bool = False          # charge swap at every calendar-day change incl. weekends (crypto)\n')
sub('    path: str = "m1"                   # "m1" | "h1"\n', '    path: str = "eurusd"               # instrument key (data/<key>/m1_server.npz); "<key>_h1" for the long hourly path\n')
sub('    session_hours: tuple = ()          # allowed server hours; empty with use_session = block everything (EA TradeAllSessions=false, all false)',
    '    session_hours: tuple = ()          # allowed server hours (0-23); empty with use_session = block everything')
# ---------------------------------------------------------------- P vector: add point, contract, swap3day, swap_daily
sub('"partial_per01", "partial_min_usd", "ploss_enable", "ploss_per01", "ploss_min_usd", "ploss_pct"]',
    '"partial_per01", "partial_min_usd", "ploss_enable", "ploss_per01", "ploss_min_usd", "ploss_pct", "point", "contract", "swap3day", "swap_daily"]')
sub("    partial_per01 = P[71]; partial_min_usd = P[72]; ploss_on = P[73] > 0.5; ploss_per01 = P[74]; ploss_min_usd = P[75]; ploss_pct = P[76]\n",
    "    partial_per01 = P[71]; partial_min_usd = P[72]; ploss_on = P[73] > 0.5; ploss_per01 = P[74]; ploss_min_usd = P[75]; ploss_pct = P[76]\n"
    "    point = P[77]; contract = P[78]; swap3day = int(P[79]); swap_daily = P[80] > 0.5\n")
# inside _sim: POINT -> point, CONTRACT -> contract (only within the function body)
a = s.index("def _sim("); b = s.index("# ----------------------------------------------------------------------------------------------------------------\n# Runner")
body = s[a:b]
body = re.sub(r"\bPOINT\b", "point", body); body = re.sub(r"\bCONTRACT\b", "contract", body)
# swap rule: triple on swap3day, weekend-aware when not daily
body = body.replace("        if pos != 0 and day[k] != last_day and swap_on:\n            nights = 3.0 if wday[k - 1] == 2 else 1.0\n",
                    "        if pos != 0 and day[k] != last_day and swap_on:\n            nights = 3.0 if (swap3day >= 0 and wday[k - 1] == swap3day) else 1.0\n            if swap_daily:\n                nights = float(day[k] - last_day)\n")
# tick rounding
body = body.replace("                        s0 = round(s0 * 100.0) / 100.0\n", "                        s0 = round(s0 / point) * point\n")
body = body.replace("                cand = round(cand * 100.0) / 100.0\n", "                cand = round(cand / point) * point\n")
# lot granularity (0.01) unchanged; allow gates
body = body.replace("         tf_h, tf_l, tf_c, tf_v, ma_f, ma_t, volavg, swl, swh, atr, atr_sl, adx, chhi, chlo, st_line, st_dir, atr_ratio,\n         P, sess, out, stats):",
                    "         tf_h, tf_l, tf_c, tf_v, ma_f, ma_t, volavg, swl, swh, atr, atr_sl, adx, chhi, chlo, st_line, st_dir, atr_ratio,\n         allow_buy, allow_sell, P, sess, out, stats):")
body = body.replace('''                    if slope_bars > 0:
                        if not (ma_f[j] > ma_f[j - slope_bars]): buy = False
                        if not (ma_f[j] < ma_f[j - slope_bars]): sell = False
                    side = 1 if buy else (-1 if sell else 0)''', '''                    if slope_bars > 0:
                        if not (ma_f[j] > ma_f[j - slope_bars]): buy = False
                        if not (ma_f[j] < ma_f[j - slope_bars]): sell = False
                    if (buy and allow_buy[j] == 0) or (sell and allow_sell[j] == 0):
                        stats[S_BLK_TREND] += 1
                        if allow_buy[j] == 0: buy = False
                        if allow_sell[j] == 0: sell = False
                    side = 1 if buy else (-1 if sell else 0)''')
assert "point = P[77]" in body and "allow_buy[j]" in body and "swap_daily" in body
s = s[:a] + body + s[b:]
# ---------------------------------------------------------------- data loader
old_load = s[s.index("def load_path("): s.index("def spread_model(")]
new_load = '''SESSION_RULES = {"xagusd": (60, 24 * 60), "xauusd": (60, 24 * 60)}   # server minutes [open, close) kept; metals open 01:00 on XM


def load_path(kind: str = "eurusd") -> dict:
    """Path bars in XM server time from data/<instrument>/m1_server.npz (or h1_server.npz for '<instrument>_h1')."""
    if kind in _PATH_CACHE:
        return _PATH_CACHE[kind]
    instr = kind.replace("_h1", ""); fn = "h1_server.npz" if kind.endswith("_h1") else "m1_server.npz"
    z = np.load(os.path.join(DATA, instr, fn))
    t = z["t"].astype(np.int64)
    keep = np.ones(len(t), dtype=bool)
    if instr in SESSION_RULES and not kind.endswith("_h1"):
        o_, c_ = SESSION_RULES[instr]; mod = (t % 86400) // 60; keep = (mod >= o_) & (mod < c_)
    d = {"t": t[keep], "o": z["o"][keep].astype(np.float64), "h": z["h"][keep].astype(np.float64), "l": z["l"][keep].astype(np.float64),
         "c": z["c"][keep].astype(np.float64), "v": z["v"][keep].astype(np.float64)}
    d["hour"] = ((d["t"] % 86400) // 3600).astype(np.int64)
    d["day"] = (d["t"] // 86400).astype(np.int64)
    d["wday"] = ((d["day"] + 3) % 7).astype(np.int64)     # Monday = 0
    d["year"] = pd.to_datetime(d["t"], unit="s").year.to_numpy().astype(np.int64)
    d["dropped_out_of_session"] = int((~keep).sum()); d["instrument"] = instr
    _PATH_CACHE[kind] = d
    return d


'''
s = s.replace(old_load, new_load)
old_spr = s[s.index("def spread_model("): s.index("def build_tf(")]
s = s.replace(old_spr, '''_SPREADS: dict = {}


def spread_model(instr: str) -> np.ndarray:
    """spread[year-2000, hour] in points for one instrument, from data/xm/spread_models.json (XM's own bars)."""
    if instr not in _SPREADS:
        with open(os.path.join(DATA, "xm", "spread_models.json")) as f:
            m = json.load(f)[instr]
        years = sorted(int(y) for y in m); arr = np.zeros((40, 24))
        for y in range(2000, 2040):
            src = m.get(str(y)) or m[str(min(max(y, years[0]), years[-1]))]
            arr[y - 2000] = src
        _SPREADS[instr] = arr
    return _SPREADS[instr]


''')
old_arr = s[s.index("def _spread_array("): s.index("def run(")]
s = s.replace(old_arr, '''def _spread_array(path: dict, p: Params) -> np.ndarray:
    if p.spread_fixed_pts >= 0:
        sp = np.full(len(path["t"]), p.spread_fixed_pts, dtype=np.float64)
    else:
        m = spread_model(path["instrument"])
        sp = m[np.clip(path["year"] - 2000, 0, 39), path["hour"]]
    return (sp * p.spread_mult + p.spread_add_pts) * p.point


''')
# ---------------------------------------------------------------- runner
sub("def run(p: Params, verbose: bool = False) -> tuple[pd.DataFrame, dict]:\n    path = load_path(p.path)",
    "def run(p: Params, verbose: bool = False, allow_buy=None, allow_sell=None) -> tuple[pd.DataFrame, dict]:\n    path = load_path(p.path)")
sub('    vec[PI["warmup"]] = warm; vec[PI["swap_long_pts"]] = -86.84; vec[PI["swap_short_pts"]] = 19.79',
    '    vec[PI["warmup"]] = warm')
sub('''    sess = np.zeros(24, dtype=np.int64)
    for h_ in p.session_hours:
        sess[h_] = 1''', '''    sess = np.zeros(24, dtype=np.int64)
    for h_ in p.session_hours:
        sess[h_] = 1
    ab = np.ones(tf["n"], dtype=np.int64) if allow_buy is None else np.asarray(allow_buy, dtype=np.int64)
    asl = np.ones(tf["n"], dtype=np.int64) if allow_sell is None else np.asarray(allow_sell, dtype=np.int64)
    assert len(ab) == tf["n"] and len(asl) == tf["n"], "allow arrays must have one entry per signal bar"''')
sub('''               ind["chhi"], ind["chlo"], ind["st_line"], ind["st_dir"], ind["atr_ratio"], vec, sess, out, stats)''',
    '''               ind["chhi"], ind["chlo"], ind["st_line"], ind["st_dir"], ind["atr_ratio"], ab, asl, vec, sess, out, stats)''')
sub('''        tr["mfe_usd"] = tr["mfe_px"].clip(lower=0) * CONTRACT * tr["lots"]
        tr["mae_usd"] = tr["mae_px"].clip(lower=0) * CONTRACT * tr["lots"]''', '''        tr["mfe_usd"] = tr["mfe_px"].clip(lower=0) * p.contract * tr["lots"]
        tr["mae_usd"] = tr["mae_px"].clip(lower=0) * p.contract * tr["lots"]''')
assert "swap_long_pts\"]] = -86.84" not in s
open(ENG, "w", encoding="utf-8").write(s); print("engine_fx.py patched", len(s.splitlines()), "lines")
