"""Strategy variants (one change each) and higher-timeframe gates on the candidate timeframes of each instrument, scenario B, judged
by the split rule against the baseline. Writes research/variants_mtf_analysis.md and experiments/variants.json."""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

HERE = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(ROOT, "backtests", "baseline_metrics.json")))["runs"]
INSTR = sys.argv[1:] or [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in R)]
LONDON_NY = tuple(range(8, 22)); NO_ASIA = tuple(range(7, 24))
VARIANTS = [("V01", "ADX(14) >= 25 (EA filter)", dict(use_adx=True, adx_min=25.0), None), ("V02", "ADX(14) >= 20", dict(use_adx=True, adx_min=20.0), None),
            ("V03", "no volume filter", dict(use_volume=False), None), ("V04", "entries 08:00-21:59 server (London + New York)", dict(use_session=True, session_hours=LONDON_NY), None),
            ("V05", "entries 13:00-16:59 server (London/NY overlap)", dict(use_session=True, session_hours=(13, 14, 15, 16)), None), ("V06", "no entries 00:00-06:59 server (Asia)", dict(use_session=True, session_hours=NO_ASIA), None),
            ("V07", "no entries on Monday before 08:00 (weekend gap)", {}, ("mon_open",)), ("V08", "ATR(22)/SMA100(ATR) >= 1.0", dict(use_vol_filter=True, vol_filter_min=1.0), None),
            ("V09", "ATR(22)/SMA100(ATR) <= 1.5", dict(use_vol_filter=True, vol_filter_min=0.0, vol_filter_max=1.5), None), ("V10", "MA18 slope filter over 3 bars", dict(slope_filter_bars=3), None),
            ("V11", "no entry when |close - MA18| > 2 ATR", dict(max_dist_atr=2.0), None), ("V12", "trend-regime gate: no sideways days", {}, ("regime", "no_sideways")),
            ("V13", "regime-aligned direction", {}, ("regime", "aligned")), ("V14", "long only", {}, ("dir", 1)), ("V15", "short only", {}, ("dir", -1)),
            ("V16", "pending order expires after 3 bars", dict(pending_max_bars=3), None), ("V17", "confirmation window 1 bar", dict(confirm_bars=1), None), ("V18", "confirmation window 3 bars", dict(confirm_bars=3), None),
            ("V19", "no high/extreme volatility days", {}, ("regime", "vol_low_normal")), ("V20", "max spread filter: no setup when spread > 2x model median", {}, ("spread",))]
MTF = [("M01", 5, 15), ("M02", 5, 60), ("M03", 15, 60), ("M04", 15, 240), ("M05", 15, 1440), ("M06", 60, 240), ("M07", 60, 1440), ("M08", 30, 1440), ("M09", 240, 1440)]
VF = os.path.join(HERE, "variants.json"); OUT = json.load(open(VF)) if os.path.exists(VF) else {"variants": {}, "mtf": {}}


def candidates(instr, cfg_name):
    c = [(tf, R[f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B"]["metrics"]) for tf in C.TFS if f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|B" in R]
    c = [(tf, m) for tf, m in c if m["net_usd"] > 0 and m["trades"] >= 50]
    return [tf for tf, m in sorted(c, key=lambda x: -x[1]["net_usd"])[:4]]


def gates(instr, tf, gate, tags):
    kind = gate[0]
    if kind == "regime":
        arg = gate[1]
        if arg == "no_sideways": ok = tags.index[tags["trend"] != "sideways"]; return C.day_gate(instr, tf, ok)
        if arg == "vol_low_normal": ok = tags.index[tags["vol"].isin(["low", "normal"])]; return C.day_gate(instr, tf, ok)
        up, _ = C.day_gate(instr, tf, tags.index[tags["trend"].isin(["weak_bull", "strong_bull"])]); _, dn = C.day_gate(instr, tf, tags.index[tags["trend"].isin(["weak_bear", "strong_bear"])]); return up, dn
    pth = E.load_path(C.default_path(instr, tf)[0]); tfb = E.build_tf(pth, tf); n = tfb["n"]
    if kind == "dir":
        one = np.ones(n, dtype=np.int64); zero = np.zeros(n, dtype=np.int64); return (one, zero) if gate[1] == 1 else (zero, one)
    if kind == "mon_open":
        t = pd.to_datetime(tfb["t"], unit="s"); ok = ~((t.weekday == 0) & (t.hour < 8)); a = np.asarray(ok, dtype=np.int64); return a, a.copy()
    if kind == "spread":
        m = E.spread_model(instr); t = pd.to_datetime(tfb["t"], unit="s"); sp = m[np.clip(t.year.to_numpy() - 2000, 0, 39), t.hour.to_numpy()]; med = np.median(m[26]); a = (sp <= 2 * med).astype(np.int64); return a, a.copy()
    raise ValueError(kind)


def judge(tr, instr):
    sm = C.split_metrics(tr, instr); m = C.summarize(tr, instr, C.DATA_START, C.DATA_END); return m, sm, C.classify(sm)


def tag(m, sm, mb, smb):
    helpful = all(sm[k].get("exp_usd", -1) > smb[k].get("exp_usd", -1) for k in C.SPLITS) and m["trades"] >= 30
    harmful = sum(1 for k in C.SPLITS if sm[k].get("exp_usd", 0) < smb[k].get("exp_usd", 0)) >= 2
    return "helpful" if helpful else ("harmful" if harmful else "mixed")


n = 0; L = ["# Strategy variants and higher-timeframe confirmation (scenario B, candidate timeframes)\n", "One change per row versus the baseline of the same instrument / config / timeframe. 'helpful' = better expectancy in TRAIN, VAL and OOS; 'harmful' = worse in two or more splits. USD per 0.01 lot.\n"]
for instr in INSTR:
    E._PATH_CACHE.clear(); E._TF_CACHE.clear(); E._IND_CACHE.clear(); tags = C.regime_tags(instr); base = {}
    for cfg_name, cfg in C.CONFIGS.items():
        for tf in candidates(instr, cfg_name):
            trb, _ = C.run(instr, tf, cfg, "B"); mb, smb, vb = judge(trb, instr); base[(cfg_name, tf)] = (mb, smb, vb); rows = []
            for vid, label, over, gate in VARIANTS:
                if gate is None: tr, st = C.run(instr, tf, cfg, "B", **over)
                else: tr, st = C.run(instr, tf, cfg, "B", allow=gates(instr, tf, gate, tags))
                m, sm, v = judge(tr, instr); tg = tag(m, sm, mb, smb)
                rows.append({"id": vid, "variant": label, "trades": m["trades"], "net $": m["net_usd"], "d net $": round(m["net_usd"] - mb["net_usd"], 2), "PF": m["pf"], "exp R": m["exp_r"], "max DD $": m["max_dd_usd"], "TRAIN": sm["TRAIN"]["net_usd"], "VAL": sm["VAL"]["net_usd"], "OOS": sm["OOS"]["net_usd"], "verdict": v, "vs base": tg})
                OUT["variants"][f"{instr}|{cfg_name}|{C.TF_NAME[tf]}|{vid}"] = {"label": label, "metrics": {k: v_ for k, v_ in m.items() if k not in ("exit_mix", "stats")}, "splits": sm, "verdict": v, "vs_base": tg}; n += 1
                C.log_experiment(f"{vid}-{instr}-{n:03d}", instr, tf, cfg_name, {**cfg, **over, "gate": gate}, label, (C.DATA_START, C.DATA_END), "B", m, sm, tg, f"net {m['net_usd']} vs base {mb['net_usd']}; OOS {sm['OOS']['net_usd']} vs {smb['OOS']['net_usd']}")
            L.append(f"\n## {C.NAME[instr]} {C.TF_NAME[tf]} {cfg_name} (baseline {mb['trades']} trades, net ${mb['net_usd']:,.2f}, PF {mb['pf']}, TRAIN {smb['TRAIN']['net_usd']:,.0f} / VAL {smb['VAL']['net_usd']:,.0f} / OOS {smb['OOS']['net_usd']:,.0f}, {vb})\n"); L.append(C.md_table(pd.DataFrame(rows)))
            print(f"{instr} {cfg_name} {C.TF_NAME[tf]}: helpful {[r['id'] for r in rows if r['vs base'] == 'helpful']}", flush=True); E._IND_CACHE.clear()
        rows = []
        for mid, lo, hi in MTF:
            if (cfg_name, lo) not in base:
                if f"{instr}|{cfg_name}|{C.TF_NAME[lo]}|B" not in R or R[f"{instr}|{cfg_name}|{C.TF_NAME[lo]}|B"]["metrics"]["net_usd"] <= 0: continue
                trb, _ = C.run(instr, lo, cfg, "B"); base[(cfg_name, lo)] = judge(trb, instr)
            mb, smb, vb = base[(cfg_name, lo)]
            for mode in ("ma", "close"):
                tr, st = C.run(instr, lo, cfg, "B", allow=C.htf_gate(instr, lo, hi, mode=mode)); m, sm, v = judge(tr, instr); tg = tag(m, sm, mb, smb)
                rows.append({"id": f"{mid}{'c' if mode == 'close' else ''}", "entry": C.TF_NAME[lo], "HTF": C.TF_NAME[hi], "trades": m["trades"], "base trades": mb["trades"], "net $": m["net_usd"], "base net $": mb["net_usd"], "PF": m["pf"], "exp R": m["exp_r"], "TRAIN": sm["TRAIN"]["net_usd"], "VAL": sm["VAL"]["net_usd"], "OOS": sm["OOS"]["net_usd"], "verdict": v, "vs base": tg})
                OUT["mtf"][f"{instr}|{cfg_name}|{mid}|{mode}"] = {"entry": C.TF_NAME[lo], "htf": C.TF_NAME[hi], "metrics": {k: v_ for k, v_ in m.items() if k not in ("exit_mix", "stats")}, "splits": sm, "verdict": v, "vs_base": tg}; n += 1
                C.log_experiment(f"{mid}{mode[0]}-{instr}-{n:03d}", instr, lo, cfg_name, {**cfg, "htf": C.TF_NAME[hi], "mode": mode}, f"HTF {C.TF_NAME[hi]} gate ({mode})", (C.DATA_START, C.DATA_END), "B", m, sm, tg, f"net {m['net_usd']} vs base {mb['net_usd']}")
        if rows: L.append(f"\n## {C.NAME[instr]} {cfg_name}: higher-timeframe gates\n"); L.append(C.md_table(pd.DataFrame(rows)))
        E._IND_CACHE.clear()
    json.dump(OUT, open(VF, "w"), indent=1, default=str)
open(os.path.join(ROOT, "research", "variants_mtf_analysis.md"), "w", encoding="utf-8").write("\n".join(L)); print("written research/variants_mtf_analysis.md")
