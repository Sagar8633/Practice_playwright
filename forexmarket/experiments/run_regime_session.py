"""Market-condition breakdown of the baseline scenario-B trades: trend and volatility regime, trading session (server hour),
weekday, weekend gap, direction, outcome type; plus instrument characteristics. Writes research/regime_analysis.md and
experiments/regime_tables.json."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_fx as C, engine_fx as E

HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.join(ROOT, "backtests")
R = json.load(open(os.path.join(BT, "baseline_metrics.json")))["runs"]
INSTR = [i for i in C.INSTRUMENTS if any(k.startswith(i + "|") for k in R)]
SHOW_TFS = (15, 30, 60, 120, 240, 1440); OUT = {}


def grp(tt, col, order=None):
    g = tt.groupby(col, observed=True)["usd"].agg(trades="size", net_usd="sum", exp_usd="mean")
    g["win_pct"] = tt.groupby(col, observed=True)["usd"].apply(lambda x: 100.0 * (x > 0).mean())
    g["pf"] = tt.groupby(col, observed=True)["usd"].apply(lambda x: x[x > 0].sum() / max(1e-9, -x[x < 0].sum()))
    g["exp_r"] = tt.groupby(col, observed=True)["r_usd"].mean()
    if order is not None: g = g.reindex([o for o in order if o in g.index])
    return g.round(3).reset_index()


L = ["# Market-condition analysis (baseline trades, scenario B)\n",
     "Tags known before the trade: trend = 63-day return of the previous close divided by its volatility scale (strong > 1, weak 0.3-1, sideways |z| < 0.3); volatility = 20-day realised volatility of the previous close ranked in the instrument's own history "
     "(low < p25, normal, high > p75, extreme > p95); session = XM server hour of entry (Asia 0-7, London 8-12, London/NY 13-16, New York 17-21, Sydney 22-23); weekend gap = Monday open vs Friday close in ATR(14) units. "
     "A 'failed breakout' is a losing trade whose best excursion never reached 0.3 R.\n", "## 1. Instrument characteristics, Sep 2021 to Sep 2026\n"]
rows = []
for i in INSTR:
    tags = C.regime_tags(i); d = C.daily_frame(i); d = d[d.index >= C.DATA_START]; tg = tags[tags.index >= C.DATA_START]
    lr = np.log(d.close / d.close.shift(1)).dropna(); prev_h = d.high.shift(1); prev_l = d.low.shift(1)
    brk_up = d.high > prev_h; ft_up = brk_up & (d.close > prev_h); brk_dn = d.low < prev_l; ft_dn = brk_dn & (d.close < prev_l)
    rows.append({"instrument": C.NAME[i], "median daily range %": round(float(((d.high - d.low) / d.close.shift(1) * 100).median()), 3), "median ATR14 %": round(float((tg.atr14 / tg.prev_close * 100).median()), 3),
                 "annualised vol % (median rv20)": round(float(tg.rv20.median()), 1), "daily autocorr lag1": round(float(lr.autocorr(1)), 3), "weekly return autocorr": round(float(lr.rolling(5).sum().dropna().autocorr(1)), 3),
                 "variance ratio 5d": round(float(lr.rolling(5).sum().var() / (5 * lr.var())), 2), "days breaking prev high %": round(float(brk_up.mean() * 100), 1), "follow-through %": round(float(ft_up.sum() / max(1, brk_up.sum()) * 100), 1),
                 "days breaking prev low %": round(float(brk_dn.mean() * 100), 1), "follow-through (down) %": round(float(ft_dn.sum() / max(1, brk_dn.sum()) * 100), 1),
                 "trend days bull/side/bear": f"{int(tg.trend.isin(['strong_bull','weak_bull']).sum())}/{int((tg.trend=='sideways').sum())}/{int(tg.trend.isin(['strong_bear','weak_bear']).sum())}",
                 "vol days low/normal/high/extreme": "/".join(str(int((tg.vol == v).sum())) for v in ("low", "normal", "high", "extreme")), "sessions": int(len(d))})
L.append(C.md_table(pd.DataFrame(rows).set_index("instrument").T.reset_index().rename(columns={"index": "metric"}), "{:,.3f}")); OUT["characteristics"] = rows
for i in INSTR:
    tags = C.regime_tags(i)
    for cfg in C.CONFIGS:
        L.append(f"\n## {C.NAME[i]}: {cfg}\n")
        for tf in SHOW_TFS:
            f = os.path.join(BT, i, f"{cfg}_{C.TF_NAME[tf]}_B_trades.csv.gz")
            if not os.path.exists(f): continue
            tr = pd.read_csv(f, parse_dates=["time_in", "time_out"])
            if len(tr) == 0: continue
            tt = C.tag_trades(tr, tags)
            tt["gap_class"] = np.where(tt.weekday == "Mon", pd.cut(tt.gap_atr.abs(), [-np.inf, 0.25, 1.0, np.inf], labels=["Mon small gap", "Mon medium gap", "Mon large gap"]).astype(str), "Tue-Fri")
            mfe_r = tt["mfe_usd"] / tt["risk_usd"].replace(0, np.nan)
            tt["outcome"] = np.where((tt.usd < 0) & (mfe_r < 0.3), "failed breakout (loss, MFE < 0.3R)", np.where(tt.usd < 0, "loss after progress", np.where(tt.r_usd >= 1, "win >= 1R", "small win")))
            tt["direction"] = tt.side.map({1: "long", -1: "short"})
            L.append(f"\n### {C.TF_NAME[tf]} ({len(tt)} trades, net ${tt.usd.sum():,.2f})\n")
            blocks = [("trend", grp(tt, "trend", ["strong_bull", "weak_bull", "sideways", "weak_bear", "strong_bear"])), ("volatility", grp(tt, "vol", ["low", "normal", "high", "extreme"])),
                      ("session of entry", grp(tt, "session", ["Asia", "London", "London/NY", "NewYork", "Sydney"])), ("weekday", grp(tt, "weekday", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])),
                      ("weekend gap", grp(tt, "gap_class")), ("direction", grp(tt, "direction")), ("trade outcome type", grp(tt, "outcome"))]
            OUT[f"{i}|{cfg}|{C.TF_NAME[tf]}"] = {name: g.to_dict("records") for name, g in blocks}
            for name, g in blocks:
                if name == "session of entry" and tf >= 1440: continue
                L.append(f"**{name}**\n\n" + C.md_table(g, "{:,.3f}") + "\n")
json.dump(OUT, open(os.path.join(HERE, "regime_tables.json"), "w"), indent=1, default=str)
open(os.path.join(ROOT, "research", "regime_analysis.md"), "w", encoding="utf-8").write("\n".join(L)); print("written research/regime_analysis.md")
