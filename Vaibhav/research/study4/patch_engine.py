"""One-off patch: tiered lot sizing (sizing=2) and a scaled partial exit in sma18_engine.py. Keeps a backup."""
import os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "sma18_engine.py")
if not os.path.exists(ENG + ".bak_prepartial"):
    shutil.copy(ENG, ENG + ".bak_prepartial")
s = open(ENG, encoding="utf-8").read()
if "partial_min_mode" in s:
    print("already patched"); sys.exit(0)


def sub(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


sub("    max_lots: float = 1.0\n",
    "    max_lots: float = 1.0\n"
    "    base_balance: float = 200.0        # sizing 2: balance of the first tier; the lot doubles each time the balance doubles\n"
    "    partial_enable: bool = False       # partial exit at a floating-profit target that scales with the lot tier\n"
    "    partial_profit_usd: float = 100.0  # trigger at tiers 0 and 1\n"
    "    partial_doubles: bool = True       # from tier 2 the trigger doubles with each tier (200, 400, ...)\n"
    "    partial_pct: float = 50.0          # share of the position volume to close\n"
    "    partial_min_mode: int = 0          # 0 = skip when the share is below the minimum lot, 1 = close the whole position\n")
sub('"lock_level_pts", "k_start", "k_end", "use_vol_filter", "vol_filter_min", "vol_filter_max", "max_spread_pts", "slope_filter_bars", "max_dist_atr"]',
    '"lock_level_pts", "k_start", "k_end", "use_vol_filter", "vol_filter_min", "vol_filter_max", "max_spread_pts", "slope_filter_bars", "max_dist_atr",\n'
    '      "base_balance", "partial_enable", "partial_profit_usd", "partial_doubles", "partial_pct", "partial_min_mode"]')
sub("    use_volf = P[59] > 0.5; volf_min = P[60]; volf_max = P[61]; max_spread = P[62] * POINT; slope_bars = int(P[63]); max_dist = P[64]\n",
    "    use_volf = P[59] > 0.5; volf_min = P[60]; volf_max = P[61]; max_spread = P[62] * POINT; slope_bars = int(P[63]); max_dist = P[64]\n"
    "    base_bal = P[65]; partial_on = P[66] > 0.5; partial_usd = P[67]; partial_dbl = P[68] > 0.5; partial_pct = P[69]; partial_min = int(P[70])\n")
sub("    slip_tot = 0.0; stage = 0; max_sl = 0.0; unit = POINT; margin = 0.0; risk_px = 0.0\n",
    "    slip_tot = 0.0; stage = 0; max_sl = 0.0; unit = POINT; margin = 0.0; risk_px = 0.0\n    ptier = 0; tier = 0; partial_done = False\n")
sub("""                        L = lots0
                        if sizing == 1 and dist > 0:
                            L = math.floor((balance * risk_pct / 100.0) / (dist * CONTRACT) / 0.01) * 0.01
                            if L < 0.01: L = 0.01
                            if L > max_lots: L = max_lots
""", """                        L = lots0; ptier = 0
                        if sizing == 1 and dist > 0:
                            L = math.floor((balance * risk_pct / 100.0) / (dist * CONTRACT) / 0.01) * 0.01
                            if L < 0.01: L = 0.01
                            if L > max_lots: L = max_lots
                        elif sizing == 2:
                            bb = balance
                            while bb >= 2.0 * base_bal and ptier < 30:
                                bb = bb / 2.0; ptier += 1
                            if balance < base_bal: ptier = 0
                            L = lots0 * (2.0 ** ptier)
                            if L > max_lots: L = max_lots
                            L = math.floor(L / 0.01 + 1e-9) * 0.01
                            if L < 0.01: L = 0.01
""")
sub("                    k_in = k; j_in = tfj[k]; k_best = k; k_worst = k; pos_swap = 0.0; be_flag = 0.0; prot_flag = 0.0; slip_tot = slip; stage = 0\n",
    "                    k_in = k; j_in = tfj[k]; k_best = k; k_worst = k; pos_swap = 0.0; be_flag = 0.0; prot_flag = 0.0; slip_tot = slip; stage = 0\n"
    "                    tier = ptier; partial_done = False\n")
sub("            # 3. stop moves: break-even, then protection (tighten only)\n", """            # 2b. partial exit at a floating-profit target that scales with the lot tier (study 4)
            if partial_on and not partial_done:
                trig = partial_usd * ((2.0 ** (tier - 1)) if (partial_dbl and tier >= 2) else 1.0)
                if pos == 1:
                    pxt = entry + trig / (CONTRACT * lots); reached = h[k] >= pxt; fillp = o[k] if o[k] >= pxt else pxt
                else:
                    pxt = entry - trig / (CONTRACT * lots); reached = (l[k] + sp) <= pxt; fillp = (o[k] + sp) if (o[k] + sp) <= pxt else pxt
                if reached:
                    cv = math.floor(lots * partial_pct / 100.0 / 0.01 + 1e-9) * 0.01
                    if cv < 0.01 and partial_min == 1:
                        cv = lots
                    if cv < 0.01:
                        partial_done = True
                    else:
                        px = (fillp - slip) if pos == 1 else (fillp + slip)
                        pnl = ((px - entry) if pos == 1 else (entry - px)) * CONTRACT * cv
                        balance += pnl
                        out[ntr, C_KIN] = k_in; out[ntr, C_KOUT] = k; out[ntr, C_SIDE] = pos; out[ntr, C_ENTRY] = entry; out[ntr, C_EXIT] = px
                        out[ntr, C_ISL] = isl; out[ntr, C_SLX] = sl; out[ntr, C_LOTS] = cv; out[ntr, C_PNL] = pnl; out[ntr, C_SWAP] = 0.0
                        out[ntr, C_MFE] = (best - entry) if pos == 1 else (entry - best); out[ntr, C_MAE] = (entry - worst) if pos == 1 else (worst - entry)
                        out[ntr, C_KMFE] = k_best; out[ntr, C_REASON] = 14; out[ntr, C_JIN] = j_in; out[ntr, C_JPEND] = pend_j; out[ntr, C_RISK] = risk_usd
                        out[ntr, C_BAL] = balance; out[ntr, C_SPR] = spr_in; out[ntr, C_ATR] = atr_in; out[ntr, C_ADX] = adx_in; out[ntr, C_SLSRC] = sl_src
                        out[ntr, C_KPEND] = pend_k; out[ntr, C_BE] = be_flag; out[ntr, C_PROT] = prot_flag; out[ntr, C_MINEQ] = balance - pnl
                        out[ntr, C_SLIP] = slip_tot + slip; out[ntr, C_MAXSL] = max_sl; out[ntr, C_KMAE] = k_worst; out[ntr, C_PENDPX] = pend_px; out[ntr, C_PENDSL0] = pend_sl0
                        out[ntr, C_STAGE] = tier
                        ntr += 1
                        partial_done = True
                        if balance > max_bal: max_bal = balance
                        if cv >= lots - 1e-9:
                            pos = 0
                            continue
                        lots = lots - cv
            # 3. stop moves: break-even, then protection (tighten only)
""")
sub('11: "time_exit", 12: "stop_out", 13: "SL_lock"}', '11: "time_exit", 12: "stop_out", 13: "SL_lock", 14: "partial_close"}')
open(ENG, "w", encoding="utf-8").write(s)
print("engine patched")
