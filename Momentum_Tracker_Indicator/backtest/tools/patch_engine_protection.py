"""One-off patch: adds the loss-prevention layer to twk_engine.py (run from the backtest folder)."""
src = open('twk_engine.py', encoding='utf-8').read()
assert "max_spread_atr" not in src, "already patched"

# ---------- 1. new params
src = src.replace('''    slippage_pts: float = 0.0            # adverse slippage on market fills and stop exits (not on TP limits)''',
'''    slippage_pts: float = 0.0            # adverse slippage on market fills and stop exits (not on TP limits)
    # ---- loss-prevention layer (2026-09-25): every option off by default
    max_spread_atr: float = 0.0          # NO_TRADE if spread / ATR > this
    max_cost_to_reward: float = 0.0      # NO_TRADE if spread / (RR x stop) > this
    vol_elevated_ratio: float = 0.0      # ATR ratio above this: risk budget x vol_elevated_risk_mult
    vol_elevated_risk_mult: float = 0.5
    vol_extreme_ratio: float = 0.0       # ATR ratio above this: NO_TRADE
    large_candle_lock: bool = False      # NO_TRADE while row["large_candle_lock"] is set (computed outside)
    min_signal_distance_atr: float = 0.0 # anti-flip: NO_TRADE if |close - previous signal close| < this x ATR
    entry_confirm_bars: int = 0          # anti-flip: enter only if the direction still holds N signal bars later
    chop_lock_score: int = 0             # NO_TRADE if row["chop_static"] + (last trade lost) >= this
    max_attempts_per_dir: int = 0        # after N consecutive losses in a direction, block it until a reset
    reset_atr: float = 1.0               # reset: a newer confirmed pivot AND a move >= this x ATR from the last losing entry
    lock2_activation_r: float = -1.0     # second protection stage (e.g. +1.5R -> lock +0.75R)
    lock2_level_r: float = 0.0
    health_exit_min: int = 0             # trade-health exit: age >= this AND profit < health_exit_below_r AND signal weakening
    health_exit_below_r: float = 0.0
    sizing: str = "fixed"                # "fixed" (lots) or "risk" (equity x risk_pct / stop)
    start_equity: float = 1000.0
    risk_pct: float = 0.5
    max_lot: float = 0.10
    max_stop_risk_pct: float = 2.0       # NO_TRADE if the minimum lot would risk more than this
    daily_loss_pct: float = 0.0          # no new trades for the day after this loss (0 = off)
    consec_reduce_at: int = 0            # halve the risk budget from this many consecutive losses
    consec_pause_at: int = 0             # pause pause_minutes from this many consecutive losses
    pause_minutes: int = 60
    consec_stop_day_at: int = 0          # stop for the day from this many consecutive losses''')

# ---------- 2. state + decisions + equity
src = src.replace('''    last_exit = {"t": None, "side": 0, "px": None, "loss": False}
    slip = (getattr(bot, "slippage_pts", 0.0) or 0.0) * POINT
''', '''    last_exit = {"t": None, "side": 0, "px": None, "loss": False}
    slip = (getattr(bot, "slippage_pts", 0.0) or 0.0) * POINT
    decisions = []                       # (sig index, m1 index, decision, reason)
    eq = {"equity": getattr(bot, "start_equity", 1000.0), "day": None, "day_start": None, "day_pnl": 0.0, "consec": 0, "pause_until": 0, "stop_day": None}
    dir_losses = {1: 0, -1: 0}           # consecutive losses per direction
    dir_last_loss = {1: None, -1: None}  # (sig_bar, entry price) of the last losing trade per direction
    adx_arr = series_for_mgmt.get("adx")
    adx_now = (np.where(last_tf >= 0, adx_arr[np.maximum(last_tf, 0)], NAN).tolist()) if adx_arr is not None else None
''')
src = src.replace('''        pnl_px = (price - pos["entry"]) if side == 1 else (pos["entry"] - price)
        t_out = at_time if at_time is not None else t[k]
        last_exit.update(t=t_out, side=side, px=price, loss=(pnl_px * mult) < 0)''',
'''        pnl_px = (price - pos["entry"]) if side == 1 else (pos["entry"] - price)
        t_out = at_time if at_time is not None else t[k]
        mult = pos.get("mult", lots * 100.0)
        last_exit.update(t=t_out, side=side, px=price, loss=(pnl_px * mult) < 0)
        pnl_total = pnl_px * mult + _swap_nights(pos["t_in"], t_out) * (SWAP_LONG_PTS if side == 1 else SWAP_SHORT_PTS) * POINT * mult
        eq["equity"] += pnl_total; eq["day_pnl"] += pnl_total
        if pnl_total < 0:
            eq["consec"] += 1; dir_losses[side] += 1; dir_last_loss[side] = (pos.get("sig_bar", -1), pos["entry"])
            if bot_consec_pause and eq["consec"] >= bot_consec_pause:
                eq["pause_until"] = max(eq["pause_until"], t_out + getattr(bot, "pause_minutes", 60) * 60)
            if bot_consec_stop and eq["consec"] >= bot_consec_stop:
                eq["stop_day"] = t_out // 86400
        else:
            eq["consec"] = 0; dir_losses[side] = 0''')
src = src.replace('''            risk=abs(pos["entry"] - pos["isl"]), pnl_px=pnl_px, pnl=pnl_px * mult + swap, swap=swap,''',
'''            risk=abs(pos["entry"] - pos["isl"]), pnl_px=pnl_px, pnl=pnl_px * mult + swap, swap=swap, lot=round(mult / 100.0, 2), equity=round(eq["equity"], 2),''')

# ---------- 3. try_open: reasons, gates, sizing
start = src.index('    def try_open(k, row):'); end = src.index('    # data holes (missing months)')
block = src[start:end]
tags = ["SESSION", "COOLDOWN", "REENTRY_DISTANCE", "NO_STOP", "NO_VOLUME_DATA", "VOLUME_RATIO", "M1_BOX", "NO_M3_DATA", "M3_BOX", "ADX", "VOLUME_RATIO_M3",
        "NO_STOP", "NO_ATR", "STOP_TOO_WIDE", "PRICE_PAST_LEVEL", "PRICE_PAST_LEVEL", "RAPID_FLIP_SKIP", "NO_STOP", "NO_STOP", "PRICE_PAST_LEVEL", "PRICE_PAST_LEVEL", "STOP_TOO_WIDE", "PRICE_PAST_LEVEL", "PRICE_PAST_LEVEL"]
n_ret = block.count("return False")
assert n_ret == len(tags), (n_ret, len(tags))
for tg in tags:
    block = block.replace("return False", 'return "%s"' % tg, 1)
block = block.replace("return True", "return None")
block = block.replace('''    def try_open(k, row):
        """Entry at the open of M1 bar k. Returns True if a position was opened."""''',
'''    def size_position(k, row):
        """Sets pos["mult"] ($ per $1 move). Fixed lots, or equity x risk% / stop with the volatility and streak reductions."""
        nonlocal pos
        if is_pine or getattr(bot, "sizing", "fixed") != "risk":
            pos["mult"] = lots * 100.0
            pos["adx_entry"] = row.get("adx", NAN)
            return None
        risk_px = abs(pos["entry"] - pos["isl"])
        budget = eq["equity"] * bot.risk_pct / 100.0
        ar = row.get("atr_ratio", NAN)
        if bot.vol_elevated_ratio > 0 and not math.isnan(ar) and ar > bot.vol_elevated_ratio:
            budget *= bot.vol_elevated_risk_mult
        if getattr(bot, "consec_reduce_at", 0) > 0 and eq["consec"] >= bot.consec_reduce_at:
            budget *= 0.5
        if risk_px <= 0:
            pos = None; return "NO_STOP"
        lot = math.floor(budget / risk_px) * 0.01              # 0.01 lot = 1 oz = $1 per $1
        if lot < 0.01 or risk_px * 1.0 > eq["equity"] * bot.max_stop_risk_pct / 100.0:
            pos = None; return "RISK_MIN_LOT"
        lot = min(lot, bot.max_lot)
        pos["mult"] = lot * 100.0
        pos["adx_entry"] = row.get("adx", NAN)
        return None

    def try_open(k, row):
        """Entry at the open of M1 bar k. Returns None if a position was opened, else the NO_TRADE reason."""''')
block = block.replace('''        if not is_pine:
            # ---- filter lab: post-loss cooldown / re-entry distance''',
'''        if not is_pine:
            # ---- loss-prevention layer: hard safety and environment gates
            if getattr(bot, "daily_loss_pct", 0) > 0 and eq["day_start"] and eq["day_pnl"] <= -eq["day_start"] * bot.daily_loss_pct / 100:
                return "DAILY_LOSS_LIMIT"
            if eq["stop_day"] is not None and t[k] // 86400 == eq["stop_day"]:
                return "CONSEC_LOSS_STOP_DAY"
            if t[k] < eq["pause_until"]:
                return "CONSEC_LOSS_PAUSE"
            a_ = row.get("atr", NAN)
            if bot.max_spread_atr > 0 and not math.isnan(a_) and a_ > 0 and spr[k] / a_ > bot.max_spread_atr:
                return "SPREAD_VS_ATR"
            if bot.max_cost_to_reward > 0 and row.get("risk", 0) > 0 and spr[k] / (bot.rr * row["risk"]) > bot.max_cost_to_reward:
                return "SPREAD_VS_REWARD"
            ar = row.get("atr_ratio", NAN)
            if bot.vol_extreme_ratio > 0 and not math.isnan(ar) and ar > bot.vol_extreme_ratio:
                return "VOL_EXTREME"
            if bot.large_candle_lock and bool(row.get("large_candle_lock", False)):
                return "LARGE_CANDLE"
            if bot.min_signal_distance_atr > 0:
                dps = row.get("dist_prev_sig", NAN)
                if not math.isnan(dps) and dps < bot.min_signal_distance_atr:
                    return "SIGNAL_DISTANCE"
            if bot.chop_lock_score > 0:
                sc = int(row.get("chop_static", 0)) + (1 if (last_exit["t"] is not None and last_exit["loss"]) else 0)
                if sc >= bot.chop_lock_score:
                    return "CHOP_LOCK"
            if bot.max_attempts_per_dir > 0 and dir_losses[side] >= bot.max_attempts_per_dir:
                ll = dir_last_loss[side]
                reset = ll is not None and int(row.get("piv_bar", -1)) > ll[0] and not math.isnan(a_) and abs(row["entry"] - ll[1]) >= bot.reset_atr * a_
                if not reset:
                    return "MAX_ATTEMPTS_DIR"
                dir_losses[side] = 0
            # ---- filter lab: post-loss cooldown / re-entry distance''')
block = block.replace('''        pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=0, src=src,
                   reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
        return None''', '''        pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=0, src=src,
                   reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
        return size_position(k, row)''')
block = block.replace('''                pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=1 if bot.purple_trail_always else 0,
                           src=bot.initial_sl, reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
                return None''', '''                pos = dict(side=side, entry=fill, isl=sl, sl=sl, tp=tp, t_in=t[k], k_in=k, stage=1 if bot.purple_trail_always else 0,
                           src=bot.initial_sl, reflip=bool(row["reflip"]), mfe=0.0, mae=0.0, sig_time=row["time"], scale=scale, **extra)
                return size_position(k, row)''')
assert block.count("size_position(k, row)") == 3, block.count("size_position(k, row)")
src = src[:start] + block + src[end:]
src = src.replace('''    def size_position(k, row):''', '''    bot_consec_pause = getattr(bot, "consec_pause_at", 0) if not is_pine else 0
    bot_consec_stop = getattr(bot, "consec_stop_day_at", 0) if not is_pine else 0

    def size_position(k, row):''', 1)

# ---------- 4. signal processing: decisions, confirmation, day bookkeeping
src = src.replace('''        # --- 2. signal processing at the open of this bar
        if k in sig_at:
            for j in sig_at[k]:
                row = sig_rows[j]
                if not is_pine and bot.stale_rule and (t[k] - row["close_time"]) > tf_sec:
                    continue''', '''        # --- day bookkeeping (server day)
        dk = t[k] // 86400
        if eq["day"] != dk:
            eq["day"] = dk; eq["day_start"] = eq["equity"]; eq["day_pnl"] = 0.0
        # --- pending confirmed entry (anti-flip: the direction must still hold N signal bars later)
        if pending_entry is not None and k >= pending_entry[0]:
            pk, prow, pj = pending_entry; pending_entry = None
            need = -1 if prow["side"] == 1 else 1
            if dir_now[k] != need:
                decisions.append((pj, k, "NO_TRADE", "CONFIRM_FAILED"))
            elif pos is not None:
                decisions.append((pj, k, "NO_TRADE", "POSITION_OPEN"))
            else:
                r_ = try_open(k, prow)
                decisions.append((pj, k, "TRADE" if r_ is None else "NO_TRADE", r_ or "ENTERED_CONFIRMED"))
        # --- 2. signal processing at the open of this bar
        if k in sig_at:
            for j in sig_at[k]:
                row = sig_rows[j]
                if not is_pine and bot.stale_rule and (t[k] - row["close_time"]) > tf_sec:
                    decisions.append((j, k, "NO_TRADE", "STALE")); continue''')
src = src.replace('''                        elif bot.one_position:
                            continue
                if pos is None:
                    try_open(k, row)''', '''                        elif bot.one_position:
                            decisions.append((j, k, "NO_TRADE", "POSITION_OPEN")); continue
                if pos is None:
                    if not is_pine and getattr(bot, "entry_confirm_bars", 0) > 0:
                        pending_entry = (k + bot.entry_confirm_bars * tf_minutes, row, j)
                        decisions.append((j, k, "PENDING", "CONFIRMATION"))
                        continue
                    r_ = try_open(k, row)
                    decisions.append((j, k, "TRADE" if r_ is None else "NO_TRADE", r_ or "ENTERED"))''')
src = src.replace('''    HOLE = 3 * 86400
    warm_until = -1
    k = k0''', '''    HOLE = 3 * 86400
    warm_until = -1
    pending_entry = None
    k = k0''')
src = src.replace('''        if k < warm_until and k in sig_at:
            k += 1
            continue''', '''        if k < warm_until and k in sig_at:
            for j in sig_at[k]:
                decisions.append((j, k, "NO_TRADE", "DATA_WARMUP"))
            k += 1
            continue''')
src = src.replace('''                    if is_pine:
                        if opposite:
                            if not bot.reverse_on_flip:
                                continue''', '''                    if is_pine:
                        if opposite:
                            if not bot.reverse_on_flip:
                                decisions.append((j, k, "NO_TRADE", "POSITION_OPEN")); continue''')

# ---------- 5. management: health exit + second lock stage
src = src.replace('''                # ---- time exit: old trade that never went anywhere
                if bot.time_exit_min > 0 and (t[k] + 60 - pos["t_in"]) >= bot.time_exit_min * 60:''',
'''                # ---- trade-health exit: age + no performance + signal weakening (direction flipped or ADX below entry)
                if getattr(bot, "health_exit_min", 0) > 0 and (t[k] + 60 - pos["t_in"]) >= bot.health_exit_min * 60:
                    cur_profit = (c[k] - e) if s == 1 else (e - (c[k] + spr[k]))
                    weak = (dn != (-1 if s == 1 else 1)) or (adx_now is not None and not math.isnan(adx_now[k]) and not math.isnan(pos.get("adx_entry", NAN)) and adx_now[k] < pos["adx_entry"])
                    if cur_profit < bot.health_exit_below_r * risk0 and weak:
                        close_pos(k, c[k] if s == 1 else c[k] + spr[k], "health_exit")
                        k += 1
                        continue
                # ---- time exit: old trade that never went anywhere
                if bot.time_exit_min > 0 and (t[k] + 60 - pos["t_in"]) >= bot.time_exit_min * 60:''')
src = src.replace('''                if bot.breakeven_r >= 0 and profit >= bot.breakeven_r * risk0 - POINT / 2:''',
'''                if getattr(bot, "lock2_activation_r", -1) >= 0 and profit >= bot.lock2_activation_r * risk0 - POINT / 2:
                    cnd = round(e + bot.lock2_level_r * risk0, 2) if s == 1 else round(e - bot.lock2_level_r * risk0, 2)
                    if (cnd > best) if s == 1 else (cnd < best):
                        best = cnd; why = "lock"
                if bot.breakeven_r >= 0 and profit >= bot.breakeven_r * risk0 - POINT / 2:''')

# ---------- 6. return decisions
src = src.replace('''    df = pd.DataFrame(trades)
    df.attrs["ambiguous_bars"] = ambiguous
    return df''', '''    df = pd.DataFrame(trades)
    df.attrs["ambiguous_bars"] = ambiguous
    df.attrs["decisions"] = pd.DataFrame(decisions, columns=["sig", "k", "decision", "reason"])
    df.attrs["final_equity"] = eq["equity"]
    return df''')
for must in ("size_position(k, row)", '"DAILY_LOSS_LIMIT"', '"CONFIRM_FAILED"', '"health_exit"', 'df.attrs["decisions"]', 'lock2_activation_r", -1) >= 0'):
    assert must in src, must
open('twk_engine.py', 'w', encoding='utf-8').write(src)
print("engine patched; tagged returns:", n_ret)
