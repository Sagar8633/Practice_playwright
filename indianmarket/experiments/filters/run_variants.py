"""Strategy variants, one experiment ID each, on the candidate timeframes (scenario B): the EA's own ADX filter, session-phase
filters, gap filters, ATR-volatility filters, slope / distance filters, regime gates, direction-only, pending expiry,
confirmation window, and higher-timeframe confirmation (MTF). Every variant is judged by the same split rule as the baseline
(TRAIN / VAL / OOS) and compared with its baseline. Writes research/variants_mtf_analysis.md and experiments/filters/variants.json."""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO, engine_in as E

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = {"nifty50": (15, 30, 60, 120, 240), "banknifty": (15, 30, 60)}
VARIANTS = [
    ("V01", "ADX(14) >= 25 (EA filter)", dict(use_adx=True, adx_min=25.0), None),
    ("V02", "ADX(14) >= 20", dict(use_adx=True, adx_min=20.0), None),
    ("V03", "no entries in the opening phase (before 09:45)", dict(use_session=True, session_slots=tuple(range(2, 25))), None),
    ("V04", "entries only 09:45-13:29 (morning + midday)", dict(use_session=True, session_slots=tuple(range(2, 17))), None),
    ("V05", "no entries in the closing phase (after 15:00)", dict(use_session=True, session_slots=tuple(range(0, 23))), None),
    ("V06", "no entries in the first hour (before 10:15)", dict(use_session=True, session_slots=tuple(range(4, 25))), None),
    ("V07", "skip sessions with |gap| > 0.5%", {}, ("gap_max", 0.5)),
    ("V08", "only sessions with |gap| <= 0.25%", {}, ("gap_max", 0.25)),
    ("V09", "ATR(22) / SMA100(ATR) >= 1.0 (expanding volatility)", dict(use_vol_filter=True, vol_filter_min=1.0), None),
    ("V10", "ATR(22) / SMA100(ATR) <= 1.5 (no extreme volatility)", dict(use_vol_filter=True, vol_filter_min=0.0, vol_filter_max=1.5), None),
    ("V11", "MA18 slope filter over 3 bars", dict(slope_filter_bars=3), None),
    ("V12", "no entry when |close - MA18| > 2 ATR", dict(max_dist_atr=2.0), None),
    ("V13", "trend-regime gate: no sideways sessions (63-day return within +-2%)", {}, ("regime", "no_sideways")),
    ("V14", "regime-aligned direction: longs on bull sessions, shorts on bear sessions", {}, ("regime", "aligned")),
    ("V15", "long only", {}, ("dir", 1)),
    ("V16", "short only", {}, ("dir", -1)),
    ("V17", "pending order expires after 3 bars", dict(pending_max_bars=3), None),
    ("V18", "confirmation window 1 bar (instead of 2)", dict(confirm_bars=1), None),
    ("V19", "confirmation window 3 bars", dict(confirm_bars=3), None),
    ("V20", "no sessions of high/extreme realised volatility", {}, ("regime", "vol_low_normal")),
]
MTF = [("M01", 5, 15), ("M02", 5, 60), ("M03", 15, 60), ("M04", 15, 240), ("M05", 15, 375), ("M06", 60, 240), ("M07", 60, 375), ("M08", 30, 375), ("M09", 30, 60)]
OUT = {"variants": {}, "mtf": {}}


def gates(instr, tf, kind, arg, tags):
    if kind == "gap_max":
        ok = tags.index[tags["gap_pct"].abs() <= arg]; return C.day_gate(instr, tf, ok)
    if kind == "regime":
        if arg == "no_sideways":
            ok = tags.index[tags["trend"] != "sideways"]; return C.day_gate(instr, tf, ok)
        if arg == "vol_low_normal":
            ok = tags.index[tags["vol"].isin(["low", "normal"])]; return C.day_gate(instr, tf, ok)
        if arg == "aligned":
            up, _ = C.day_gate(instr, tf, tags.index[tags["trend"].isin(["weak_bull", "strong_bull"])])
            _, dn = C.day_gate(instr, tf, tags.index[tags["trend"].isin(["weak_bear", "strong_bear"])]); return up, dn
    if kind == "dir":
        pth = E.load_path(instr); n = E.build_tf(pth, tf)["n"]; one = np.ones(n, dtype=np.int64); zero = np.zeros(n, dtype=np.int64)
        return (one, zero) if arg == 1 else (zero, one)
    raise ValueError(kind)


def judge(tr, instr):
    sm = C.split_metrics(tr, instr); m = C.summarize(tr, instr, C.DATA_START, C.DATA_END)
    return m, sm, C.classify(sm)


base = {}
L = ["# Strategy variants and higher-timeframe confirmation (scenario B costs, candidate timeframes)\n",
     "Each row is one experiment: the baseline configuration plus exactly one change. 'd net' = net points versus the baseline of the same instrument / config / timeframe. Verdict rule as in the baseline "
     "(robust = positive expectancy and PF > 1 after costs in TRAIN, VAL and OOS with >= 30 trades each). A variant is 'helpful' only if it improves expectancy in all three splits; improvements that appear in one split only are noise until proven otherwise.\n"]
n = 0
for instr, tfs in CANDIDATES.items():
    tags = C.regime_tags(instr)
    for cfg_name, cfg in C.CONFIGS.items():
        for tf in tfs:
            trb, _ = C.run(instr, tf, cfg, "B"); mb, smb, vb = judge(trb, instr); base[(instr, cfg_name, tf)] = (mb, smb, vb)
            rows = []
            for vid, label, over, gate in VARIANTS:
                t0 = time.time()
                if gate is None:
                    tr, st = C.run(instr, tf, cfg, "B", **over)
                else:
                    ab, asl = gates(instr, tf, gate[0], gate[1], tags); tr, st = C.run_allow(instr, tf, cfg, ab, asl, "B")
                m, sm, v = judge(tr, instr)
                helpful = all(sm[k].get("exp_pts", -1) > smb[k].get("exp_pts", -1) for k in C.SPLITS) and m["trades"] >= 30
                harmful = sum(1 for k in C.SPLITS if sm[k].get("exp_pts", 0) < smb[k].get("exp_pts", 0)) >= 2
                tag = "helpful" if helpful else ("harmful" if harmful else "mixed")
                rows.append({"id": vid, "variant": label, "trades": m["trades"], "net pts": m["net_pts"], "d net": round(m["net_pts"] - mb["net_pts"], 0), "PF": m["pf"], "exp pts": m["exp_pts"], "exp R": m["exp_r"],
                             "max DD": m["max_dd_pts"], "TRAIN": sm["TRAIN"]["net_pts"], "VAL": sm["VAL"]["net_pts"], "OOS": sm["OOS"]["net_pts"], "verdict": v, "vs base": tag})
                OUT["variants"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|{vid}"] = {"label": label, "metrics": {k: v_ for k, v_ in m.items() if k != "exit_mix"}, "splits": sm, "verdict": v, "vs_base": tag}
                n += 1
                C.log_experiment(f"{vid}-{n:03d}", instr, tf, cfg_name, {**cfg, **over, "gate": gate}, label, (C.DATA_START, C.DATA_END), "B", m, sm, tag,
                                 f"net {m['net_pts']} vs base {mb['net_pts']}; OOS {sm['OOS']['net_pts']} vs base {smb['OOS']['net_pts']}")
            L.append(f"\n## {CO.INSTR[instr]['name']} {C.TF_NAME[tf]} {cfg_name} (baseline: {mb['trades']} trades, net {mb['net_pts']:,.0f} pts, PF {mb['pf']}, TRAIN {smb['TRAIN']['net_pts']:,.0f} / VAL {smb['VAL']['net_pts']:,.0f} / OOS {smb['OOS']['net_pts']:,.0f}, {vb})\n")
            L.append(C.md_table(pd.DataFrame(rows)))
            print(f"{instr} {cfg_name} {C.TF_NAME[tf]}: variants done; helpful = {[r['id'] for r in rows if r['vs base'] == 'helpful']}", flush=True)
            E._IND_CACHE.clear()

# ---------------------------------------------------------------- MTF
L.append("\n# Higher-timeframe confirmation\n")
L.append("Entry timeframe signals are allowed only when the last completed bar of the higher timeframe has MA18 above MA200 (buy) / below (sell). 'close' mode also needs the HTF close on the right side of its MA18. "
         "The baseline for each row is the entry timeframe without the gate.\n")
for instr in C.INSTRUMENTS:
    for cfg_name, cfg in C.CONFIGS.items():
        rows = []
        for mid, lo, hi in MTF:
            if (instr, cfg_name, lo) in base:
                mb, smb, vb = base[(instr, cfg_name, lo)]
            else:
                trb, _ = C.run(instr, lo, cfg, "B"); mb, smb, vb = judge(trb, instr); base[(instr, cfg_name, lo)] = (mb, smb, vb)
            for mode in ("ma", "close"):
                ab, asl = C.htf_gate(instr, lo, hi, mode=mode); tr, st = C.run_allow(instr, lo, cfg, ab, asl, "B")
                m, sm, v = judge(tr, instr)
                helpful = all(sm[k].get("exp_pts", -1) > smb[k].get("exp_pts", -1) for k in C.SPLITS) and m["trades"] >= 30
                harmful = sum(1 for k in C.SPLITS if sm[k].get("exp_pts", 0) < smb[k].get("exp_pts", 0)) >= 2
                tag = "helpful" if helpful else ("harmful" if harmful else "mixed")
                rows.append({"id": f"{mid}{'c' if mode == 'close' else ''}", "entry": C.TF_NAME[lo], "HTF": C.TF_NAME[hi], "mode": mode, "trades": m["trades"], "base trades": mb["trades"], "net pts": m["net_pts"], "base net": mb["net_pts"],
                             "PF": m["pf"], "base PF": mb["pf"], "exp R": m["exp_r"], "max DD": m["max_dd_pts"], "TRAIN": sm["TRAIN"]["net_pts"], "VAL": sm["VAL"]["net_pts"], "OOS": sm["OOS"]["net_pts"], "verdict": v, "vs base": tag})
                OUT["mtf"][f"{instr}|{cfg_name}|{mid}|{mode}"] = {"entry": C.TF_NAME[lo], "htf": C.TF_NAME[hi], "metrics": {k: v_ for k, v_ in m.items() if k != "exit_mix"}, "splits": sm, "verdict": v, "vs_base": tag}
                n += 1
                C.log_experiment(f"{mid}{mode[0]}-{n:03d}", instr, lo, cfg_name, {**cfg, "htf": C.TF_NAME[hi], "mode": mode}, f"HTF {C.TF_NAME[hi]} trend gate ({mode})", (C.DATA_START, C.DATA_END), "B", m, sm, tag,
                                 f"net {m['net_pts']} vs base {mb['net_pts']}; OOS {sm['OOS']['net_pts']} vs base {smb['OOS']['net_pts']}")
        L.append(f"\n## {CO.INSTR[instr]['name']} {cfg_name}\n"); L.append(C.md_table(pd.DataFrame(rows)))
        print(f"{instr} {cfg_name}: MTF done; helpful = {[r['id'] for r in rows if r['vs base'] == 'helpful']}", flush=True)
        E._IND_CACHE.clear()
json.dump(OUT, open(os.path.join(HERE, "variants.json"), "w"), indent=1, default=str)
open(os.path.join(ROOT, "research", "variants_mtf_analysis.md"), "w", encoding="utf-8").write("\n".join(L))
print("written research/variants_mtf_analysis.md")
