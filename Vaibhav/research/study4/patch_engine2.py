"""Engine patch 2: linear lot progression (sizing=3: lot = base_lot x floor(balance / base_balance)), per-lot partial
profit target (partial_per01 x lots/0.01 with a floor), and a loss-side partial exit (reason 15)."""
import os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ENG = os.path.join(ROOT, "sma18_engine.py")
s = open(ENG, encoding="utf-8").read()
if "ploss_enable" in s:
    print("already patched"); sys.exit(0)
shutil.copy(ENG, ENG + ".bak_prepatch2")


def sub(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


sub("    partial_min_mode: int = 0          # 0 = skip when the share is below the minimum lot, 1 = close the whole position\n",
    "    partial_min_mode: int = 0          # 0 = skip when the share is below the minimum lot, 1 = close the whole position\n"
    "    partial_per01: float = 0.0         # > 0: profit target = max(partial_min_usd, partial_per01 x lots / 0.01) instead of the tier rule\n"
    "    partial_min_usd: float = 100.0\n"
    "    ploss_enable: bool = False         # loss-side partial exit, once per position\n"
    "    ploss_per01: float = 50.0          # loss target = max(ploss_min_usd, ploss_per01 x lots / 0.01)\n"
    "    ploss_min_usd: float = 100.0\n"
    "    ploss_pct: float = 50.0\n")
sub('"base_balance", "partial_enable", "partial_profit_usd", "partial_doubles", "partial_pct", "partial_min_mode"]',
    '"base_balance", "partial_enable", "partial_profit_usd", "partial_doubles", "partial_pct", "partial_min_mode",\n      "partial_per01", "partial_min_usd", "ploss_enable", "ploss_per01", "ploss_min_usd", "ploss_pct"]')
sub("    base_bal = P[65]; partial_on = P[66] > 0.5; partial_usd = P[67]; partial_dbl = P[68] > 0.5; partial_pct = P[69]; partial_min = int(P[70])\n",
    "    base_bal = P[65]; partial_on = P[66] > 0.5; partial_usd = P[67]; partial_dbl = P[68] > 0.5; partial_pct = P[69]; partial_min = int(P[70])\n"
    "    partial_per01 = P[71]; partial_min_usd = P[72]; ploss_on = P[73] > 0.5; ploss_per01 = P[74]; ploss_min_usd = P[75]; ploss_pct = P[76]\n")
sub("    ptier = 0; tier = 0; partial_done = False\n", "    ptier = 0; tier = 0; partial_done = False; ploss_done = False\n")
# linear sizing mode
sub("""                        elif sizing == 2:
                            bb = balance
                            while bb >= 2.0 * base_bal and ptier < 30:
                                bb = bb / 2.0; ptier += 1
                            if balance < base_bal: ptier = 0
                            L = lots0 * (2.0 ** ptier)
                            if L > max_lots: L = max_lots
                            L = math.floor(L / 0.01 + 1e-9) * 0.01
                            if L < 0.01: L = 0.01
""", """                        elif sizing == 2:
                            bb = balance
                            while bb >= 2.0 * base_bal and ptier < 30:
                                bb = bb / 2.0; ptier += 1
                            if balance < base_bal: ptier = 0
                            L = lots0 * (2.0 ** ptier)
                            if L > max_lots: L = max_lots
                            L = math.floor(L / 0.01 + 1e-9) * 0.01
                            if L < 0.01: L = 0.01
                        elif sizing == 3:
                            steps = math.floor(balance / base_bal + 1e-9) if base_bal > 0 else 1
                            if steps < 1: steps = 1
                            L = lots0 * steps
                            if L > max_lots: L = max_lots
                            L = math.floor(L / 0.01 + 1e-9) * 0.01
                            if L < 0.01: L = 0.01
                            ptier = int(round(L / lots0)) - 1
""")
sub("                    tier = ptier; partial_done = False\n", "                    tier = ptier; partial_done = False; ploss_done = False\n")
# profit target: per-lot rule when partial_per01 > 0; loss-side partial before it
sub("""            # 2b. partial exit at a floating-profit target that scales with the lot tier (study 4)
            if partial_on and not partial_done:
                trig = partial_usd * ((2.0 ** (tier - 1)) if (partial_dbl and tier >= 2) else 1.0)
""", """            # 2a. loss-side partial exit (study 4b): close a share when the floating loss reaches the per-lot target
            if ploss_on and not ploss_done:
                ltrig = max(ploss_min_usd, ploss_per01 * lots / 0.01)
                if pos == 1:
                    pxl = entry - ltrig / (CONTRACT * lots); lreached = l[k] <= pxl; lfill = o[k] if o[k] <= pxl else pxl
                else:
                    pxl = entry + ltrig / (CONTRACT * lots); lreached = (h[k] + sp) >= pxl; lfill = (o[k] + sp) if (o[k] + sp) >= pxl else pxl
                if lreached:
                    cv = math.floor(lots * ploss_pct / 100.0 / 0.01 + 1e-9) * 0.01
                    if cv < 0.01 and partial_min == 1:
                        cv = lots
                    if cv < 0.01:
                        ploss_done = True
                    else:
                        px = (lfill - slip) if pos == 1 else (lfill + slip)
                        pnl = ((px - entry) if pos == 1 else (entry - px)) * CONTRACT * cv
                        balance += pnl
                        out[ntr, C_KIN] = k_in; out[ntr, C_KOUT] = k; out[ntr, C_SIDE] = pos; out[ntr, C_ENTRY] = entry; out[ntr, C_EXIT] = px
                        out[ntr, C_ISL] = isl; out[ntr, C_SLX] = sl; out[ntr, C_LOTS] = cv; out[ntr, C_PNL] = pnl; out[ntr, C_SWAP] = 0.0
                        out[ntr, C_MFE] = (best - entry) if pos == 1 else (entry - best); out[ntr, C_MAE] = (entry - worst) if pos == 1 else (worst - entry)
                        out[ntr, C_KMFE] = k_best; out[ntr, C_REASON] = 15; out[ntr, C_JIN] = j_in; out[ntr, C_JPEND] = pend_j; out[ntr, C_RISK] = risk_usd
                        out[ntr, C_BAL] = balance; out[ntr, C_SPR] = spr_in; out[ntr, C_ATR] = atr_in; out[ntr, C_ADX] = adx_in; out[ntr, C_SLSRC] = sl_src
                        out[ntr, C_KPEND] = pend_k; out[ntr, C_BE] = be_flag; out[ntr, C_PROT] = prot_flag; out[ntr, C_MINEQ] = balance - pnl
                        out[ntr, C_SLIP] = slip_tot + slip; out[ntr, C_MAXSL] = max_sl; out[ntr, C_KMAE] = k_worst; out[ntr, C_PENDPX] = pend_px; out[ntr, C_PENDSL0] = pend_sl0
                        out[ntr, C_STAGE] = tier
                        ntr += 1
                        ploss_done = True
                        if balance < min_bal: min_bal = balance
                        if max_bal - balance > maxdd_bal: maxdd_bal = max_bal - balance
                        if balance <= 0.0: ruin = True
                        if cv >= lots - 1e-9:
                            pos = 0
                            continue
                        lots = lots - cv
            # 2b. partial exit at a floating-profit target that scales with the lot tier (study 4)
            if partial_on and not partial_done:
                if partial_per01 > 0:
                    trig = max(partial_min_usd, partial_per01 * lots / 0.01)
                else:
                    trig = partial_usd * ((2.0 ** (tier - 1)) if (partial_dbl and tier >= 2) else 1.0)
""")
sub('13: "SL_lock", 14: "partial_close"}', '13: "SL_lock", 14: "partial_close", 15: "partial_loss"}')
open(ENG, "w", encoding="utf-8").write(s); print("engine patched (v2)")
