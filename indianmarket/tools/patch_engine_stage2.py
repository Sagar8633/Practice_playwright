"""Stage 2 of the gold-engine port: data loader, session-anchored bars, fixed spread, 15-minute session slots,
allow_buy/allow_sell gates, tick rounding, Indian session names. Run once; asserts fail loudly if a target string is gone."""
import os

ENG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy", "engine_in.py")
s = open(ENG, encoding="utf-8").read()
if "def session_of_minute" in s:
    print("already patched"); raise SystemExit


def sub(old, new, count=1):
    global s
    assert s.count(old) >= 1, old[:90]
    s = s.replace(old, new, count)


# ---------------------------------------------------------------- data loader
old_load = s[s.index("def load_path("): s.index("def spread_model(")]
new_load = '''def load_path(kind: str = "nifty50") -> dict:
    """Path bars in IST. kind 'nifty50' / 'banknifty': 1-minute candles restricted to 09:15-15:29 (pre-open 09:07 prints, the
    15:30/15:31 closing prints and the evening Muhurat sessions are dropped and counted). kind '*_daily': one bar per session
    from the daily file (2007-), stamped at 09:15. The 'hour' array holds the 15-minute session slot (0..24) for the session filter."""
    if kind in _PATH_CACHE:
        return _PATH_CACHE[kind]
    daily = kind.endswith("_daily"); base = kind.replace("_daily", "")
    npz = os.path.join(DATA, base, f"{kind}_path.npz")
    if os.path.exists(npz):
        z = np.load(npz); d = {k: z[k] for k in z.files}
    else:
        df = pd.read_csv(os.path.join(DATA, base, f"{base}_{'daily' if daily else '1min'}_upstox.csv.gz"), parse_dates=["time"])
        df = df.drop_duplicates("time").sort_values("time")
        t = df["time"].to_numpy().astype("datetime64[s]").astype(np.int64)
        if daily:
            t = (t // 86400) * 86400 + SESSION_OPEN_MIN * 60
            keep = np.ones(len(t), dtype=bool)
        else:
            mod = (t % 86400) // 60
            keep = (mod >= SESSION_OPEN_MIN) & (mod < SESSION_CLOSE_MIN)
        d = {"t": t[keep], "o": df["open"].to_numpy(np.float64)[keep], "h": df["high"].to_numpy(np.float64)[keep],
             "l": df["low"].to_numpy(np.float64)[keep], "c": df["close"].to_numpy(np.float64)[keep], "v": df["volume"].to_numpy(np.float64)[keep],
             "dropped_out_of_session": np.array(int((~keep).sum()))}
        np.savez(npz, **d)
    d["t"] = d["t"].astype(np.int64)
    mod = (d["t"] % 86400) // 60
    d["hour"] = np.clip((mod - SESSION_OPEN_MIN) // 15, 0, NSLOT - 1).astype(np.int64)
    d["day"] = (d["t"] // 86400).astype(np.int64)
    d["wday"] = ((d["day"] + 3) % 7).astype(np.int64)     # Monday = 0
    d["year"] = pd.to_datetime(d["t"], unit="s").year.to_numpy().astype(np.int64)
    d["dropped_out_of_session"] = int(d["dropped_out_of_session"])
    _PATH_CACHE[kind] = d
    return d


'''
s = s.replace(old_load, new_load)
# ---------------------------------------------------------------- spread model -> fixed
old_spr = s[s.index("def spread_model("): s.index("def build_tf(")]
s = s.replace(old_spr, "")
old_arr = s[s.index("def _spread_array("): s.index("def run(")]
s = s.replace(old_arr, '''def _spread_array(path: dict, p: Params) -> np.ndarray:
    """Fixed futures bid/ask spread in ticks (the index print is treated as the bid)."""
    return np.full(len(path["t"]), (max(p.spread_fixed_pts, 0.0) * p.spread_mult + p.spread_add_pts) * POINT, dtype=np.float64)


''')
# ---------------------------------------------------------------- session-anchored signal bars
sub('''    t = path["t"]
    bucket = (t // (tf_minutes * 60)) * (tf_minutes * 60)
''', '''    t = path["t"]
    day = t // 86400; mod = (t % 86400) // 60
    if tf_minutes >= 375:      # one bar per session
        bucket = day * 86400 + SESSION_OPEN_MIN * 60
    else:                      # anchored at 09:15: 60m bars are 09:15, 10:15 ... 15:15 (the last one is a 15-minute stub)
        bucket = day * 86400 + (SESSION_OPEN_MIN + ((mod - SESSION_OPEN_MIN) // tf_minutes) * tf_minutes) * 60
''')
sub('''    tf["hour"] = ((tf["t"] % 86400) // 3600).astype(np.int64)
    _TF_CACHE[key] = tf''', '''    tf["hour"] = np.clip((((tf["t"] % 86400) // 60) - SESSION_OPEN_MIN) // 15, 0, NSLOT - 1).astype(np.int64)
    _TF_CACHE[key] = tf''')
# ---------------------------------------------------------------- allow arrays in the core
sub("         tf_h, tf_l, tf_c, tf_v, ma_f, ma_t, volavg, swl, swh, atr, atr_sl, adx, chhi, chlo, st_line, st_dir, atr_ratio,\n         P, sess, out, stats):",
    "         tf_h, tf_l, tf_c, tf_v, ma_f, ma_t, volavg, swl, swh, atr, atr_sl, adx, chhi, chlo, st_line, st_dir, atr_ratio,\n         allow_buy, allow_sell, P, sess, out, stats):")
sub('''                    if slope_bars > 0:
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
# ---------------------------------------------------------------- tick rounding of stops
sub("                        s0 = round(s0 * 100.0) / 100.0\n", "                        s0 = round(round(s0 / POINT) * POINT * 100.0) / 100.0\n")
sub("                cand = round(cand * 100.0) / 100.0\n", "                cand = round(round(cand / POINT) * POINT * 100.0) / 100.0\n")
# ---------------------------------------------------------------- runner
sub("def run(p: Params, verbose: bool = False) -> tuple[pd.DataFrame, dict]:\n    path = load_path(p.path)",
    "def run(p: Params, verbose: bool = False, allow_buy=None, allow_sell=None) -> tuple[pd.DataFrame, dict]:\n    \"\"\"allow_buy / allow_sell: optional int8 arrays with one flag per signal bar (1 = setup allowed) for experiment filters.\"\"\"\n    path = load_path(p.path)")
sub('    vec[PI["warmup"]] = warm; vec[PI["swap_long_pts"]] = -86.84; vec[PI["swap_short_pts"]] = 19.79',
    '    vec[PI["warmup"]] = warm; vec[PI["swap_long_pts"]] = 0.0; vec[PI["swap_short_pts"]] = 0.0')
sub('''    sess = np.zeros(24, dtype=np.int64)
    for h_ in p.session_hours:
        sess[h_] = 1''', '''    sess = np.zeros(NSLOT, dtype=np.int64)
    for h_ in p.session_slots:
        sess[h_] = 1
    ab = np.ones(tf["n"], dtype=np.int64) if allow_buy is None else np.asarray(allow_buy, dtype=np.int64)
    asl = np.ones(tf["n"], dtype=np.int64) if allow_sell is None else np.asarray(allow_sell, dtype=np.int64)
    assert len(ab) == tf["n"] and len(asl) == tf["n"], "allow arrays must have one entry per signal bar"''')
sub('''               ind["chhi"], ind["chlo"], ind["st_line"], ind["st_dir"], ind["atr_ratio"], vec, sess, out, stats)''',
    '''               ind["chhi"], ind["chlo"], ind["st_line"], ind["st_dir"], ind["atr_ratio"], ab, asl, vec, sess, out, stats)''')
sub('''        tr["hour_in"] = tr["time_in"].dt.hour
        tr["weekday_in"] = tr["time_in"].dt.weekday
        tr["session"] = tr["hour_in"].map(session_of_hour)''', '''        tr["hour_in"] = tr["time_in"].dt.hour
        tr["weekday_in"] = tr["time_in"].dt.weekday
        tr["minute_in"] = tr["time_in"].dt.hour * 60 + tr["time_in"].dt.minute
        tr["slot_in"] = ((tr["minute_in"] - SESSION_OPEN_MIN) // 15).clip(0, NSLOT - 1)
        tr["session"] = tr["minute_in"].map(session_of_minute)
        tr["date_in"] = tr["time_in"].dt.normalize()
        tr["pts"] = tr["pnl"] / tr["lots"]                      # index points per unit (the money unit of this engine)''')
old_sess = s[s.index("def session_of_hour("): s.index("# ----------------------------------------------------------------------------------------------------------------\n# Metrics")]
s = s.replace(old_sess, '''def session_of_minute(m: int) -> str:
    """Indian cash-session phases by minute of day: opening 09:15-09:44, morning 09:45-11:29, midday 11:30-13:29,
    afternoon 13:30-14:59, closing 15:00-15:29."""
    if m < 9 * 60 + 45: return "opening"
    if m < 11 * 60 + 30: return "morning"
    if m < 13 * 60 + 30: return "midday"
    if m < 15 * 60: return "afternoon"
    return "closing"


''')
assert "session_of_hour" not in s and "spread_model" not in s and "session_hours" not in s
open(ENG, "w", encoding="utf-8").write(s); print("stage 2 written", len(s.splitlines()), "lines")
