"""Market-condition breakdown of the baseline trades (scenario B): trend and volatility regimes, session phase, gaps,
weekday, previous-day high/low interaction, breakout follow-through, consolidation; plus the instrument characteristics
that explain NIFTY 50 vs NIFTY BANK. Writes research/regime_analysis.md and experiments/sessions/regime_tables.json."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "strategy"))
import numpy as np, pandas as pd
import common_in as C, costs as CO, engine_in as E

HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.join(ROOT, "backtests")
SHOW_TFS = (5, 15, 30, 60, 120, 240, 375)
OUT = {}


def grp(tt: pd.DataFrame, col: str, order=None) -> pd.DataFrame:
    g = tt.groupby(col, observed=True)["pts_net"].agg(trades="size", net_pts="sum", exp_pts="mean")
    g["win_pct"] = tt.groupby(col, observed=True)["pts_net"].apply(lambda x: 100.0 * (x > 0).mean())
    g["pf"] = tt.groupby(col, observed=True)["pts_net"].apply(lambda x: x[x > 0].sum() / max(1e-9, -x[x < 0].sum()))
    g["exp_r"] = tt.groupby(col, observed=True)["r_net"].mean()
    if order is not None:
        g = g.reindex([o for o in order if o in g.index])
    return g.round(2).reset_index()


def load(instr, cfg, tf, sc="B"):
    f = os.path.join(BT, instr, f"{cfg}_{C.TF_NAME[tf]}_{sc}_trades.csv.gz")
    return pd.read_csv(f, parse_dates=["time_in", "time_out"]) if os.path.exists(f) else None


L = ["# Market-condition analysis (baseline trades, scenario B costs)\n",
     "Tags are known before the trade: trend = 63-session return of the previous close (strong bull > +8%, weak bull +2..+8, sideways -2..+2, weak bear -8..-2, strong bear < -8); "
     "volatility = 20-session realised volatility of the previous close ranked over 2015-2026 (low < 25th pct, normal, high > 75th, extreme > 95th); gap = session open vs previous close "
     "(small < 0.25%, medium 0.25-0.75%, large > 0.75%); session phase = entry time (opening 09:15-09:44, morning 09:45-11:29, midday 11:30-13:29, afternoon 13:30-14:59, closing 15:00-15:29); "
     "consolidation = previous 5-session average range below its 60-session median. A 'failed breakout' is a losing trade whose best excursion never reached 0.3 R.\n"]

# ---------------------------------------------------------------- instrument characteristics
L.append("## 1. Instrument characteristics, 2022-2026 (why the two indices behave differently)\n")
rows = []
for instr in C.INSTRUMENTS:
    tags = C.regime_tags(instr); d = C.daily_frame(instr); d = d[d.index >= "2022-01-03"]
    pth = E.load_path(instr); m1 = pd.DataFrame({"t": pd.to_datetime(pth["t"], unit="s"), "h": pth["h"], "l": pth["l"], "o": pth["o"], "c": pth["c"]}); m1["date"] = m1.t.dt.normalize(); m1["mod"] = m1.t.dt.hour * 60 + m1.t.dt.minute
    day = m1.groupby("date").agg(h=("h", "max"), l=("l", "min"), o=("o", "first"), c=("c", "last"))
    open15 = m1[m1["mod"] < 570].groupby("date").agg(h=("h", "max"), l=("l", "min"))
    share_open = ((open15.h - open15.l) / (day.h - day.l)).median() * 100
    lr = np.log(d.close / d.close.shift(1)).dropna()
    ac1 = lr.autocorr(1); ac5 = lr.rolling(5).sum().dropna().autocorr(1)
    vr5 = (lr.rolling(5).sum().var() / (5 * lr.var()))
    tg = tags[tags.index >= "2022-01-03"]
    prev_h = d.high.shift(1); prev_l = d.low.shift(1)
    brk_up = (d.high > prev_h); ft_up = brk_up & (d.close > prev_h); fail_up = brk_up & (d.close < prev_h)
    brk_dn = (d.low < prev_l); ft_dn = brk_dn & (d.close < prev_l); fail_dn = brk_dn & (d.close > prev_l)
    rows.append({"metric": "sessions", instr: int(len(d))} if False else None)
    rows.append({"instrument": CO.INSTR[instr]["name"], "median daily range %": round(float(((d.high - d.low) / d.close.shift(1) * 100).median()), 2), "median ATR14 %": round(float((tg.atr14 / tg.prev_close * 100).median()), 2),
                 "median |gap| %": round(float(tg.gap_pct.abs().median()), 3), "days |gap| > 0.5%": round(float((tg.gap_pct.abs() > 0.5).mean() * 100), 1), "days |gap| > 1%": round(float((tg.gap_pct.abs() > 1).mean() * 100), 1),
                 "first 15 min share of day range %": round(float(share_open), 1), "daily return autocorr lag1": round(float(ac1), 3), "weekly return autocorr": round(float(ac5), 3), "variance ratio 5d": round(float(vr5), 2),
                 "days breaking prev high %": round(float(brk_up.mean() * 100), 1), "of which close above (follow-through) %": round(float(ft_up.sum() / max(1, brk_up.sum()) * 100), 1),
                 "days breaking prev low %": round(float(brk_dn.mean() * 100), 1), "of which close below %": round(float(ft_dn.sum() / max(1, brk_dn.sum()) * 100), 1),
                 "trend regime days: bull/side/bear": f"{int(tg.trend.isin(['strong_bull','weak_bull']).sum())}/{int((tg.trend=='sideways').sum())}/{int(tg.trend.isin(['strong_bear','weak_bear']).sum())}",
                 "vol regime days: low/normal/high/extreme": "/".join(str(int((tg.vol == v).sum())) for v in ("low", "normal", "high", "extreme"))})
rows = [r for r in rows if r]
L.append(C.md_table(pd.DataFrame(rows).set_index("instrument").T.reset_index().rename(columns={"index": "metric"})))
OUT["characteristics"] = rows

# ---------------------------------------------------------------- breakdowns
for instr in C.INSTRUMENTS:
    tags = C.regime_tags(instr)
    rng = tags["range_pct"].shift(1).rolling(5).mean(); med60 = rng.rolling(60).median(); consol = (rng < med60)
    for cfg in C.CONFIGS:
        L.append(f"\n## {CO.INSTR[instr]['name']}: {cfg}\n")
        for tf in SHOW_TFS:
            tr = load(instr, cfg, tf)
            if tr is None or len(tr) == 0:
                continue
            tt = C.tag_trades(tr, tags); key = tt["time_in"].dt.normalize()
            tt["consolidation"] = key.map(consol).map({True: "consolidation", False: "expansion"})
            tt["weekday"] = tt["time_in"].dt.day_name().str.slice(0, 3)
            ph = key.map(tags["prev_high"]); pl = key.map(tags["prev_low"])
            tt["prev_day_level"] = np.where((tt.side == 1) & (tt.entry > ph), "long above prev high", np.where((tt.side == -1) & (tt.entry < pl), "short below prev low", "inside prev range"))
            mfe_r = tt["mfe_usd"] / tt["risk_usd"].replace(0, np.nan)
            tt["outcome"] = np.where((tt.pts_net < 0) & (mfe_r < 0.3), "failed breakout (loss, MFE < 0.3R)", np.where(tt.pts_net < 0, "loss after progress", np.where(tt.r_net >= 1, "win >= 1R", "small win")))
            tt["gap"] = tt["gap_class"].astype(str) + " " + tt["gap_dir"].astype(str)
            L.append(f"\n### {C.TF_NAME[tf]} ({len(tt)} trades, net {tt.pts_net.sum():,.0f} pts)\n")
            blocks = [("trend", grp(tt, "trend", ["strong_bull", "weak_bull", "sideways", "weak_bear", "strong_bear"])), ("volatility", grp(tt, "vol", ["low", "normal", "high", "extreme"])),
                      ("session phase of entry", grp(tt, "session", ["opening", "morning", "midday", "afternoon", "closing"])), ("opening gap of the entry day", grp(tt, "gap")),
                      ("weekday", grp(tt, "weekday", ["Mon", "Tue", "Wed", "Thu", "Fri"])), ("previous-day level", grp(tt, "prev_day_level")), ("consolidation vs expansion (prior 5 sessions)", grp(tt, "consolidation")),
                      ("trade outcome type", grp(tt, "outcome"))]
            OUT[f"{instr}|{cfg}|{C.TF_NAME[tf]}"] = {name: g.to_dict("records") for name, g in blocks}
            for name, g in blocks:
                if name in ("session phase of entry",) and tf >= 375:
                    continue
                L.append(f"**{name}**\n\n" + C.md_table(g) + "\n")
            # long vs short
            ls = tt.groupby("side")["pts_net"].agg(trades="size", net_pts="sum").round(1).rename(index={1: "long", -1: "short"}).reset_index()
            L.append("**direction**\n\n" + C.md_table(ls) + "\n")
json.dump(OUT, open(os.path.join(HERE, "regime_tables.json"), "w"), indent=1, default=str)
open(os.path.join(ROOT, "research", "regime_analysis.md"), "w", encoding="utf-8").write("\n".join(L))
print("written research/regime_analysis.md")
