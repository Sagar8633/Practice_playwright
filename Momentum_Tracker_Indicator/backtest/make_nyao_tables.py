"""Builds the tables (results/nyao/TABLES.md), the brief's CSV deliverables and the charts (results/nyao/charts/) from
the outputs of nyao_tick_calibration.py, nyao_lab.py and nyao_lab2.py."""
import json, os, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import twk_engine as E

OUT = "results/nyao"; CH = f"{OUT}/charts"; os.makedirs(CH, exist_ok=True)
runs = pd.read_csv(f"{OUT}/nyao_runs.csv")
runs2 = pd.read_csv(f"{OUT}/nyao_runs2.csv") if os.path.exists(f"{OUT}/nyao_runs2.csv") else pd.DataFrame()
comp = pd.read_csv(f"{OUT}/component_tests.csv")
buck = pd.read_csv(f"{OUT}/baseline_by_nyao_score.csv")
tbt = pd.read_csv(f"{OUT}/trade_by_trade_summary.csv")
lab = json.load(open(f"{OUT}/lab.json"))
cal = json.load(open(f"{OUT}/tick_calibration.json"))
calib = pd.read_csv(f"{OUT}/tick_calibration.csv")
PER = {k: (pd.Timestamp(a), pd.Timestamp(b)) for k, (a, b) in lab["periods"].items()}
md = []
def H(t): md.append(f"\n## {t}\n")
def T(df, cols=None, index=False):
    d = df if cols is None else df[[c for c in cols if c in df.columns]]
    md.append(d.to_markdown(index=index, floatfmt=".2f") if hasattr(d, "to_markdown") else d.to_string(index=index))
    md.append("")
def fmt_runs(df, extra=()):
    cols = ["run", "trades", "win", "pf", "exp", "DEV_net", "DEV_pf", "VAL_net", "VAL_pf", "OOS_net", "OOS_pf", "DEV_final", "VAL_final", "OOS_final"] + list(extra)
    return df[[c for c in cols if c in df.columns]]

# ------------------------------------------------------------------ 1 calibration
H("Tick calibration of the $0.20 trailing stop (2025, Thu/Fri, server 14:00-19:59, 575 hours of Dukascopy ticks)")
a = cal["all"]
md.append(f"Replayed trades: {a['n']} (M1 {cal['M1']['n']}, M5 {cal['M5']['n']}). Mean P&L per trade: bar-optimistic {a['pnl_bar_mean']:+.2f}, tick {a['pnl_tick_mean']:+.2f}, first-activation level {a['pnl_be_mean']:+.2f} USD at 0.01 lot.")
md.append(f"Trailing exits ({a['trail_n']}): bar {a['trail_pnl_bar']:+.2f}, tick {a['trail_pnl_tick']:+.2f}, activation level {a['trail_pnl_be']:+.2f}. Position of the tick exit between the bounds (lambda): median {a['lambda_median']:.2f}, mean {a['lambda_mean']:.2f}; {a['lambda_share_below_0_1']*100:.0f}% of exits within 10% of the pessimistic bound, {a['tick_exit_within_be_plus_5pts']*100:.0f}% within 5 points of the activation level. Median time to activation {a['secs_to_activation_median']:.0f} s, median hold {a['hold_tick_s_median']:.0f} s.")
md.append("")
rows = []
for k, v in cal["by_reason_bar"].items():
    rows.append(dict(bar_exit_reason=k, n=v["n"], pnl_bar=v["pnl_bar_mean"], pnl_tick=v["pnl_tick_mean"], win_bar=v["win_bar"], win_tick=v["win_tick"], lambda_mean=v.get("lambda_mean"), tick_reasons=json.dumps(v["reasons_tick"])))
T(pd.DataFrame(rows))
# chart
tt = calib[calib.reason_bar.isin(["TRAIL", "SL_trail"])]
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].scatter(tt.pnl_bar, tt.pnl_tick, s=4, alpha=0.35, color="#2a6f97")
lim = (min(tt.pnl_bar.min(), tt.pnl_tick.min()) - 0.5, tt.pnl_bar.quantile(0.995) + 0.5)
ax[0].plot(lim, lim, color="#999", lw=1, ls="--", label="tick = bar (path bound)")
ax[0].axhline(tt.pnl_be.median(), color="#c1121f", lw=1, ls=":", label=f"activation level (median {tt.pnl_be.median():.2f})")
ax[0].set_xlim(lim); ax[0].set_ylim(lim[0], 4)
ax[0].set_xlabel("bar-engine P&L per trade, USD at 0.01 lot (path bound)"); ax[0].set_ylabel("tick-replay P&L"); ax[0].legend(fontsize=8); ax[0].set_title("Trailing exits: bar bound vs tick truth")
lam = ((tt.pnl_tick - tt.pnl_be) / (tt.pnl_bar - tt.pnl_be)).replace([np.inf, -np.inf], np.nan).dropna().clip(-1, 2)
ax[1].hist(lam, bins=60, color="#2a6f97"); ax[1].axvline(0, color="#c1121f", ls=":"); ax[1].axvline(1, color="#999", ls="--")
ax[1].set_xlabel("lambda: 0 = pessimistic bound, 1 = optimistic bound"); ax[1].set_title(f"Where the tick exit lands (median {lam.median():.2f}, mean {lam.mean():.2f})")
fig.tight_layout(); fig.savefig(f"{CH}/tick_calibration.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------------ 2 core runs
H("Shipped default profile, per period from $1,000 (DEV 2021-09..2023, VAL 2024, OOS 2025..2026-09-25) and continuous five years")
core = runs[runs.group.isin(["core", "bounds"])].copy()
core["reading"] = core.run.str.rsplit("_", n=1).str[-1]
T(fmt_runs(core, extra=("cont_final", "cont_ruin", "cont_trades", "cont_pf")))
H("Other profiles and the $200 account (calibrated trailing)")
T(fmt_runs(runs[runs.group.isin(["profiles", "deposit"])], extra=("cont_final", "cont_ruin", "cont_trades")))
H("Cost sensitivity (default profile, hedge off, calibrated trailing)")
T(fmt_runs(runs[runs.group == "cost"]))
H("Entry-only mode: Nyao score entry with the EA's own R:R stop (1.5 ATR, TP 1.5R), one position, no trailing / health / hedge")
T(fmt_runs(runs[runs.group == "entry"], extra=("avg_win", "avg_loss")))
H("Parameter perturbation (default profile, M5, hedge off, calibrated trailing)")
T(fmt_runs(runs[runs.group == "perturb"]))
H("Sessions and the news-filter proxy (M5, hedge off)")
T(fmt_runs(runs[runs.group == "session"]))

# ------------------------------------------------------------------ 3 baseline + components
H("BASELINE (TWK M3 preset, fixed 0.02 lot) and the Nyao score as an entry gate on the baseline's signals")
T(comp, ["run", "desc", "signals_kept", "signals_total", "trades", "net", "pf", "exp", "win", "max_dd", "DEV_net", "DEV_pf", "VAL_net", "VAL_pf", "OOS_net", "OOS_pf", "passes_dev_val"])
H("Baseline trades bucketed by the Nyao score in the trade direction at entry")
T(buck)
H("Trade-by-trade: BASELINE vs Nyao M3 (calibrated, hedge off), matched on the entry M3 bar and direction")
T(tbt)

# ------------------------------------------------------------------ 4 research variants (fixed stop, no ruin stop)
if len(runs2):
    H("Research variants: EA logic with a fixed $10 stop, no ruin stop, no drawdown pause, calibrated trailing, five years continuous")
    T(runs2, ["run", "desc", "trades", "win", "pf", "exp", "net", "gross_before_spread", "spread_cost", "max_dd", "DEV_net", "DEV_pf", "VAL_net", "VAL_pf", "OOS_net", "OOS_pf", "chains", "hedges", "health_closes"])

# ------------------------------------------------------------------ 5 regimes and loss patterns on the fixed-stop M5 / M1 runs
def load_tr(name):
    f = f"{OUT}/trades/{name}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["entry_time", "exit_time"])
    return d if len(d) else None
m1 = pd.read_csv("data/XAUUSD_M1_servertime_full.csv.gz", parse_dates=["time"])
h1 = E.resample(m1, 60); ema50 = pd.Series(h1.close).ewm(span=50, adjust=False).mean().to_numpy(); t_h1 = (h1.time.astype("int64") // 10**9).to_numpy()
m5 = E.resample(m1, 5)
atr5 = pd.Series(E.true_range(m5.high.to_numpy(float), m5.low.to_numpy(float), m5.close.to_numpy(float), True)).rolling(8).mean()
atr_ref = pd.Series(atr5.to_numpy(), index=m5.time).resample("1D").median().rolling(30, min_periods=10).median().shift(1)
def tag(d):
    d = d.copy()
    d["hour"] = d.entry_time.dt.hour
    d["session"] = pd.cut(d.hour, [-1, 9, 14, 18, 23], labels=["Asia 00-09", "London 10-14", "NY/overlap 15-18", "NY late 19-23"])
    d["year"] = d.entry_time.dt.year
    d["period"] = np.select([(d.entry_time >= a) & (d.entry_time < b) for a, b in PER.values()], list(PER.keys()), "n/a")
    k = np.searchsorted(t_h1 + 3600, d.entry_time.astype("int64").to_numpy() // 10**9, side="right") - 1
    slope = np.where(k >= 3, ema50[np.maximum(k, 0)] - ema50[np.maximum(k - 3, 0)], 0.0)
    d["h1_trend"] = np.where(slope > 0, "up", np.where(slope < 0, "down", "flat"))
    d["with_trend"] = np.where(d.side == "BUY", d.h1_trend == "up", d.h1_trend == "down")
    ref = atr_ref.reindex(d.entry_time.dt.floor("D")).ffill().bfill().to_numpy()
    d["vol_ratio"] = d.atr / ref
    d["vol_regime"] = pd.cut(d.vol_ratio, [0, 0.8, 1.25, 99], labels=["low", "normal", "high"])
    d["loser"] = d.pnl < 0
    d["hedge_leg"] = d.via == "hedge"
    return d
def regime_tables(d, title):
    H(title)
    for col in ("period", "year", "session", "with_trend", "vol_regime", "side", "via", "exit_reason"):
        g = d.groupby(col, observed=True).agg(n=("pnl", "size"), net=("pnl", "sum"), exp=("pnl", "mean"), win=("loser", lambda x: 1 - x.mean()), avg_hold_min=("bars", "mean")).round(2).reset_index()
        md.append(f"**by {col}**\n"); T(g)
    # session x period
    g = d.pivot_table(index="session", columns="period", values="pnl", aggfunc=["count", "mean"], observed=True).round(2)
    md.append("**session x period (count, mean P&L per trade)**\n"); md.append(g.to_markdown(floatfmt=".2f")); md.append("")
def loss_patterns(d, title):
    H(title)
    L = d[d.loser]; W = d[~d.loser]
    rows = [
        ("losing trades", len(L), f"{len(L)/len(d)*100:.1f}% of trades"),
        ("total loss", round(L.pnl.sum()), "USD"),
        ("loss from hedge legs", round(L[L.hedge_leg].pnl.sum()) if L.hedge_leg.any() else 0, f"{(L.hedge_leg.mean()*100):.1f}% of losers are hedge legs"),
        ("median loser size", round(L.pnl.median(), 2), "USD"), ("median winner size", round(W.pnl.median(), 2), "USD"),
        ("top-10 losses share of total loss", f"{L.pnl.sort_values().head(10).sum()/L.pnl.sum()*100:.1f}%", ""),
        ("losers entered against the H1 EMA50 slope", f"{(~L.with_trend).mean()*100:.1f}%", f"winners: {(~W.with_trend).mean()*100:.1f}%"),
        ("losers in high-volatility regime", f"{(L.vol_regime=='high').mean()*100:.1f}%", f"winners: {(W.vol_regime=='high').mean()*100:.1f}%"),
        ("losers in NY/overlap 15-18", f"{(L.session=='NY/overlap 15-18').mean()*100:.1f}%", f"winners: {(W.session=='NY/overlap 15-18').mean()*100:.1f}%"),
        ("losers that were >= 0.5R in profit first (reversal)", f"{((L.max_fav >= 0.5*L.risk_px) & L.risk_px.notna()).mean()*100:.1f}%", ""),
        ("median hold, losers / winners (min)", f"{L.bars.median():.0f} / {W.bars.median():.0f}", ""),
        ("losers by exit reason", json.dumps(L.exit_reason.value_counts().head(6).to_dict()), ""),
        ("consecutive-loss streak, max", int(max((len(list(g)) for k, g in __import__('itertools').groupby(d.loser.tolist()) if k), default=0)), ""),
    ]
    T(pd.DataFrame(rows, columns=["pattern", "value", "note"]))
    # hourly
    g = d.groupby("hour").agg(n=("pnl", "size"), exp=("pnl", "mean"), win=("loser", lambda x: 1 - x.mean())).round(2).reset_index()
    md.append("**by entry hour (server time)**\n"); T(g)

fx5 = load_tr("fixed_M5_nohedge"); fx1 = load_tr("fixed_M1_nohedge"); fx5h = load_tr("fixed_M5_hedge")
for nm, d in (("fixed_M5_nohedge", fx5), ("fixed_M1_nohedge", fx1), ("fixed_M5_hedge", fx5h)):
    if d is not None:
        dd = tag(d)
        regime_tables(dd, f"Regimes: {nm} (fixed $10 stop, five years)")
        loss_patterns(dd, f"Loss patterns: {nm}")
        dd.to_csv(f"{OUT}/trades/{nm}_tagged.csv", index=False)

# ------------------------------------------------------------------ 6 STRATEGY_COMPARISON.csv (the brief's table)
def cont_row(name, label, cost_rob, overfit):
    r = runs[runs.run == name]
    if not len(r):
        return None
    r = r.iloc[0]
    f = f"{OUT}/trades/{name}_continuous.csv"
    d = pd.read_csv(f, parse_dates=["entry_time", "exit_time"]) if os.path.exists(f) else None
    if d is None or not len(d):
        return None
    pnl = d.pnl.to_numpy(); eq = 1000 + np.cumsum(pnl); peak = np.maximum.accumulate(np.concatenate([[1000.0], eq]))[1:]; dd = (peak - eq).max()
    w = pnl[pnl > 0]; lo = pnl[pnl < 0]
    return dict(Strategy=label, Trades=len(pnl), Win_pct=round((pnl > 0).mean() * 100, 1), PF=round(w.sum() / -lo.sum(), 2) if lo.sum() < 0 else None, Expectancy=round(pnl.mean(), 2),
                Net_PL=round(pnl.sum(), 0), Max_DD=round(dd, 0), Recovery=round(pnl.sum() / dd, 2) if dd > 0 else None, OOS_PF=r["OOS_pf"], Cost_Robustness=cost_rob, Overfit_Risk=overfit,
                DEV_PF=r["DEV_pf"], VAL_PF=r["VAL_pf"], ruin=bool(r.get("cont_ruin", False)))
b = lab["baseline"]; bp = b["periods"]
btr = pd.read_csv(f"{OUT}/trades/BASELINE_M3.csv")
bpnl = btr.pnl.to_numpy(); beq = 1000 + np.cumsum(bpnl); bpeak = np.maximum.accumulate(np.concatenate([[1000.0], beq]))[1:]; bdd = (bpeak - beq).max()
rows = [dict(Strategy="BASELINE TWK M3 (0.02 lot)", Trades=len(bpnl), Win_pct=round((bpnl > 0).mean() * 100, 1), PF=round(b["pf"], 2), Expectancy=round(bpnl.mean(), 2), Net_PL=round(bpnl.sum(), 0),
             Max_DD=round(bdd, 0), Recovery=round(bpnl.sum() / bdd, 2) if bdd > 0 else None, OOS_PF=round(bp["OOS"]["pf"], 2), Cost_Robustness="fails at normal cost (flat before spread)", Overfit_Risk="n/a (not optimised here)",
             DEV_PF=round(bp["DEV"]["pf"], 2), VAL_PF=round(bp["VAL"]["pf"], 2), ruin=False)]
for name, label in (("default_M1_hedge_calib", "Nyao default M1, hedge on (shipped), tick-calibrated"), ("default_M1_nohedge_calib", "Nyao default M1, hedge off, tick-calibrated"),
                    ("default_M5_hedge_calib", "Nyao default M5, hedge on, tick-calibrated"), ("default_M5_nohedge_calib", "Nyao default M5, hedge off, tick-calibrated"),
                    ("default_M3_hedge_calib", "Nyao default M3, hedge on, tick-calibrated"), ("default_M1_hedge_path", "Nyao default M1, hedge on, BAR-OPTIMISTIC bound"), ("default_M5_nohedge_path", "Nyao default M5, hedge off, BAR-OPTIMISTIC bound"),
                    ("safe_M5_calib", "Nyao safe profile M5"), ("aggressive_M1_calib", "Nyao aggressive profile M1")):
    rr = cont_row(name, label, "fails at normal cost", "n/a: negative at every setting")
    if rr: rows.append(rr)
for name in ("entryonly_M1_rr1.5", "entryonly_M5_rr1.5", "entryonly_M3_rr1.5"):
    r = runs[runs.run == name]
    if len(r):
        r = r.iloc[0]; d = pd.read_csv(f"{OUT}/trades/{name}.csv")
        pnl = d.pnl.to_numpy(); w = pnl[pnl > 0]; lo = pnl[pnl < 0]
        rows.append(dict(Strategy=f"Nyao entry only ({name.split('_')[1]}, SL 1.5 ATR, TP 1.5R)", Trades=len(pnl), Win_pct=round((pnl > 0).mean() * 100, 1), PF=round(w.sum() / -lo.sum(), 2), Expectancy=round(pnl.mean(), 2),
                         Net_PL=round(pnl.sum(), 0), Max_DD=None, Recovery=None, OOS_PF=r["OOS_pf"], Cost_Robustness="fails at normal cost", Overfit_Risk="low sensitivity, negative everywhere", DEV_PF=r["DEV_pf"], VAL_PF=r["VAL_pf"], ruin=None))
if len(runs2):
    for name in ("fixed_M1_nohedge", "fixed_M5_nohedge", "fixed_M5_hedge"):
        r = runs2[runs2.run == name]
        if len(r):
            r = r.iloc[0]
            rows.append(dict(Strategy=f"Nyao research: {name} (fixed $10 stop, no ruin stop)", Trades=int(r.trades), Win_pct=round(r.win * 100, 1), PF=r.pf, Expectancy=r.exp, Net_PL=r.net, Max_DD=r.max_dd,
                             Recovery=round(r.net / r.max_dd, 2) if r.max_dd else None, OOS_PF=r["OOS_pf"], Cost_Robustness=f"gross before spread {r.gross_before_spread:+.0f}, spread {r.spread_cost:.0f}", Overfit_Risk="n/a", DEV_PF=r["DEV_pf"], VAL_PF=r["VAL_pf"], ruin=None))
pd.DataFrame(rows).to_csv(f"{OUT}/STRATEGY_COMPARISON.csv", index=False)
H("STRATEGY_COMPARISON (continuous five years from $1,000 unless noted)")
T(pd.DataFrame(rows))
# component results csv
c2 = comp.copy(); c2["source"] = "Nyao score gate on the TWK M3 baseline"
if len(runs2):
    ab = runs2[runs2.group == "ablation"].copy(); ab["source"] = "Nyao management layers switched off one at a time (fixed-stop M5)"
    c2 = pd.concat([c2, ab.rename(columns={"trades": "trades", "net": "net"})], ignore_index=True)
c2.to_csv(f"{OUT}/COMPONENT_TEST_RESULTS.csv", index=False)

# ------------------------------------------------------------------ 7 charts
def equity_chart(tf):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for name, col, ls in ((f"default_M{tf}_hedge_path", "#adb5bd", "--"), (f"default_M{tf}_nohedge_path", "#6c757d", "--"),
                          (f"default_M{tf}_hedge_calib", "#c1121f", "-"), (f"default_M{tf}_nohedge_calib", "#2a6f97", "-"),
                          (f"default_M{tf}_hedge_worst", "#f4a261", ":"), (f"default_M{tf}_nohedge_worst", "#e9c46a", ":")):
        f = f"{OUT}/trades/{name}_continuous.csv"
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f, parse_dates=["exit_time"])
        if not len(d):
            continue
        eq = 1000 + d.pnl.cumsum()
        ax.plot(d.exit_time, eq, color=col, ls=ls, lw=1.4, label=f"{name.split('_', 2)[2].replace('_', ' ')}: final {eq.iloc[-1]:,.0f}")
    ax.axhline(1000, color="#999", lw=0.8); ax.axhline(20, color="#c1121f", lw=0.6, ls=":")
    ax.set_yscale("symlog", linthresh=1000); ax.set_ylim(bottom=0); ax.set_ylabel("balance, USD (symlog)"); ax.set_title(f"Nyao default M{tf}, five years from $1,000. Dashed = bar-optimistic bound, solid = tick-calibrated, dotted = pessimistic", fontsize=10)
    ax.legend(fontsize=8, loc="upper left"); fig.tight_layout(); fig.savefig(f"{CH}/equity_readings_M{tf}.png", dpi=130); plt.close(fig)
for tf in (1, 5):
    equity_chart(tf)

def week_chart(d_nyao, d_base, start, days, fname, title):
    a = pd.Timestamp(start); b = a + pd.Timedelta(days=days)
    w = m1[(m1.time >= a) & (m1.time < b)]
    if not len(w):
        return
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 2]))
    for ax, d, lab_ in ((axes[0], d_nyao, "Nyao (fixed-stop research run, hedge off)"), (axes[1], d_base, "BASELINE TWK M3")):
        ax.plot(w.time, w.close, color="#444", lw=0.7)
        if d is not None:
            s = d[(d.entry_time >= a) & (d.entry_time < b)]
            for r in s.itertuples():
                col = "#2a9d8f" if r.pnl > 0 else "#c1121f"
                ax.plot([r.entry_time, r.exit_time], [r.entry, r.exit], color=col, lw=1.0, alpha=0.8)
                ax.scatter([r.entry_time], [r.entry], marker="^" if r.side == "BUY" else "v", color="#1d3557" if r.side == "BUY" else "#e76f51", s=22, zorder=3)
                ax.scatter([r.exit_time], [r.exit], marker="x", color=col, s=18, zorder=3)
            n = len(s); ax.set_title(f"{lab_}: {n} trades, net {s.pnl.sum():+.0f} USD, win {((s.pnl > 0).mean()*100 if n else 0):.0f}%  (triangle = entry, x = exit, green/red = win/loss)", fontsize=10)
        ax.grid(alpha=0.2)
    fig.suptitle(title); fig.tight_layout(); fig.savefig(f"{CH}/{fname}", dpi=120); plt.close(fig)
btr_d = pd.read_csv(f"{OUT}/trades/BASELINE_M3.csv", parse_dates=["entry_time", "exit_time"])
for start, fname, ttl in (("2026-01-05", "week_2026-01-05_M5.png", "One week, Jan 2026 (OOS): Nyao M5 vs BASELINE on the same XAUUSD M1 closes"),
                         ("2022-10-10", "week_2022-10-10_M5.png", "One week, Oct 2022 (DEV)"), ("2024-05-13", "week_2024-05-13_M5.png", "One week, May 2024 (VAL)")):
    week_chart(fx5, btr_d, start, 5, fname, ttl)
d1 = fx1
for start, fname, ttl in (("2026-01-07", "day_2026-01-07_M1.png", "One day, 7 Jan 2026: Nyao M1 (fixed stop) vs BASELINE"),):
    week_chart(d1, btr_d, start, 1, fname, ttl)

# perturbation chart
pt = runs[runs.group == "perturb"]
if len(pt):
    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(len(pt)); wdt = 0.27
    for i, pn in enumerate(("DEV", "VAL", "OOS")):
        ax.bar(x + (i - 1) * wdt, pt[f"{pn}_exp"], wdt, label=pn)
    ax.set_xticks(x); ax.set_xticklabels(pt.run.str.replace("pert_M5_", ""), rotation=45, ha="right", fontsize=8); ax.axhline(0, color="#333", lw=0.8)
    ax.set_ylabel("expectancy, USD per trade at 0.01 lot"); ax.set_title("Parameter perturbation, M5, hedge off, tick-calibrated: every setting is negative in every period"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{CH}/perturbation_M5.png", dpi=130); plt.close(fig)
# entry-only chart
en = runs[runs.group == "entry"]
if len(en):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    x = np.arange(len(en)); wdt = 0.27
    for i, pn in enumerate(("DEV", "VAL", "OOS")):
        ax.bar(x + (i - 1) * wdt, en[f"{pn}_pf"], wdt, label=pn)
    ax.axhline(1.0, color="#c1121f", lw=0.8, ls="--"); ax.set_xticks(x); ax.set_xticklabels(en.run.str.replace("entryonly_", ""), rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("profit factor"); ax.set_title("Entry-only mode (Nyao score + 1.5 ATR stop, R:R target): profit factor by period"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{CH}/entry_only.png", dpi=130); plt.close(fig)
# session x period heat for fixed M5
if fx5 is not None:
    dd = tag(fx5); g = dd.pivot_table(index="session", columns="period", values="pnl", aggfunc="mean", observed=True)[["DEV", "VAL", "OOS"]]
    fig, ax = plt.subplots(figsize=(6, 3.2)); im = ax.imshow(g.to_numpy(), cmap="RdYlGn", vmin=-1.5, vmax=1.5, aspect="auto")
    ax.set_xticks(range(3)); ax.set_xticklabels(g.columns); ax.set_yticks(range(len(g))); ax.set_yticklabels(g.index, fontsize=8)
    for i in range(len(g)):
        for j in range(3):
            ax.text(j, i, f"{g.iloc[i, j]:+.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Nyao M5 fixed-stop: mean P&L per trade by session and period"); fig.colorbar(im, ax=ax, fraction=0.04); fig.tight_layout(); fig.savefig(f"{CH}/session_period_M5.png", dpi=130); plt.close(fig)

open(f"{OUT}/TABLES.md", "w", encoding="utf-8").write("\n".join(md))
print("tables + charts written:", sorted(os.listdir(CH)))
