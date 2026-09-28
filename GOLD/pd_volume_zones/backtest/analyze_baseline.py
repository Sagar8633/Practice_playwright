"""
analyze_baseline.py - statistics, loss-pattern analysis and what-if diagnostics
for the PD VolZones baseline run (results/trade_log_raw.csv from run_baseline).

Writes:
  results/trade_log.csv          full trade log (requested columns first)
  results/baseline_stats.json    every number used in the reports
  results/loss_patterns.csv      one row per condition bucket
  BASELINE_TEST_REPORT.md, LOSS_PATTERN_REPORT.md
"""
import json
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import pdvz_engine as E

R = "results"
DATA = "../../../Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_*.csv"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def stats(df):
    if len(df) == 0:
        return dict(n=0)
    r = df.result_R.values
    w = r > 0
    gp = r[r > 0].sum()
    gl = -r[r < 0].sum()
    cum = np.cumsum(r)
    dd = float((np.maximum.accumulate(cum) - cum).max()) if len(cum) else 0.0
    streak = best = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return dict(n=int(len(df)), wins=int(w.sum()), losses=int((~w).sum()), win_rate=float(w.mean()),
                total_R=float(r.sum()), avg_R=float(r.mean()), pf=float(gp / gl) if gl > 0 else float("inf"),
                max_dd_R=dd, max_loss_streak=int(best), net_R=float(df.net_R.sum()), avg_net_R=float(df.net_R.mean()),
                avg_mfe_R=float(df.mfe_R.mean()), avg_mae_R=float(df.mae_R.mean()),
                median_risk=float(df.risk_pts.median()), median_minutes=float(df.minutes_held.median()))


def ztest(w1, n1, w2, n2):
    if n1 == 0 or n2 == 0:
        return np.nan
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (p1 - p2) / se if se > 0 else np.nan


def cond_rows(df, family, labels, note=""):
    """labels: a Series of bucket labels aligned with df."""
    rows = []
    tot_loss = int((df.result_R <= 0).sum())
    tot_neg = float(df.result_R[df.result_R < 0].sum())
    base_loss_rate = tot_loss / len(df)
    for lab in pd.unique(labels.dropna()):
        m = (labels == lab).values
        sub = df[m]
        rest = df[~m]
        n = len(sub)
        if n == 0:
            continue
        losses = int((sub.result_R <= 0).sum())
        wins = n - losses
        neg = float(sub.result_R[sub.result_R < 0].sum())
        gp = float(sub.result_R[sub.result_R > 0].sum())
        rows.append(dict(
            family=family, bucket=str(lab), n=n, wins=wins, losses=losses, win_rate=wins / n, loss_rate=losses / n,
            lift=(losses / n) / base_loss_rate if base_loss_rate > 0 else np.nan,
            avg_R=float(sub.result_R.mean()), sum_R=float(sub.result_R.sum()), avg_net_R=float(sub.net_R.mean()),
            pf=gp / -neg if neg < 0 else float("inf"),
            share_of_losses=losses / tot_loss if tot_loss else np.nan,
            share_of_neg_R=neg / tot_neg if tot_neg else np.nan,
            z_vs_rest=ztest(wins, n, int((rest.result_R > 0).sum()), len(rest)),
            avg_mfe_R=float(sub.mfe_R.mean()), note=note))
    return rows


def qbucket(s, q=4, fmt="{:.2f}"):
    try:
        cats = pd.qcut(s, q, duplicates="drop")
    except ValueError:
        return s.astype(str)
    return cats.apply(lambda iv: f"{fmt.format(iv.left)} to {fmt.format(iv.right)}" if isinstance(iv, pd.Interval) else "na")


def md_table(df, cols, fmts=None, index=False):
    fmts = fmts or {}
    head = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in fmts:
                cells.append(fmts[c].format(v) if not (isinstance(v, float) and math.isnan(v)) else "")
            elif isinstance(v, float):
                cells.append("" if math.isnan(v) else (f"{v:.2f}" if abs(v) < 1000 else f"{v:,.0f}"))
            else:
                cells.append(str(v))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def fmt_stats_row(name, s):
    if s.get("n", 0) == 0:
        return f"| {name} | 0 | | | | | | | | |\n"
    return (f"| {name} | {s['n']} | {s['wins']} / {s['losses']} | {100 * s['win_rate']:.1f}% | {s['total_R']:+.1f} | "
            f"{s['avg_R']:+.3f} | {s['pf']:.2f} | {s['max_dd_R']:.1f} | {s['max_loss_streak']} | {s['net_R']:+.1f} |\n")


STATS_HEAD = ("| Slice | Trades | W / L | Win rate | Total R | Avg R | PF | Max DD (R) | Longest losing streak | Net R (spread) |\n"
              "|---|---|---|---|---|---|---|---|---|---|\n")


# ----------------------------------------------------------------------------
# load
# ----------------------------------------------------------------------------
tr = pd.read_csv(f"{R}/trade_log_raw.csv")
sk = pd.read_csv(f"{R}/skipped_log_raw.csv")
info = json.load(open(f"{R}/run_info.json"))
valid = tr[tr.exit_reason.isin(["SL", "TP"])].copy().reset_index(drop=True)
excluded = len(tr) - len(valid)
valid["loss"] = valid.result_R <= 0
valid["win_loss"] = np.where(valid.result_R > 0, "WIN", "LOSS")
valid["rect_high"] = valid.zone_top
valid["rect_low"] = valid.zone_bot

# ----------------------------------------------------------------------------
# trade log with the requested columns first
# ----------------------------------------------------------------------------
first = ["time_ist", "time_utc", "side", "rect_high", "rect_low", "poc", "entry", "sl", "tp", "risk_pts", "result_R",
         "win_loss", "mfe_R", "mae_R", "exit_time_utc", "exit_price", "exit_reason", "minutes_held", "net_R", "cost_R",
         "zone_kind"]
rest_cols = [c for c in valid.columns if c not in first + ["loss", "zone_top", "zone_bot", "win", "taken"]]
valid[first + rest_cols].to_csv(f"{R}/trade_log.csv", index=False)

# ----------------------------------------------------------------------------
# headline + slices
# ----------------------------------------------------------------------------
S = dict(info=info, excluded=excluded, all=stats(valid))
S["by_side"] = {k: stats(g) for k, g in valid.groupby("side")}
S["by_kind"] = {k: stats(g) for k, g in valid.groupby("zone_kind")}
S["by_year"] = {int(k): stats(g) for k, g in valid.groupby("year")}
S["by_month"] = {k: stats(g) for k, g in valid.groupby("month")}
S["by_session"] = {k: stats(g) for k, g in valid.groupby("session")}
S["by_side_kind"] = {f"{a} {b}": stats(g) for (a, b), g in valid.groupby(["side", "zone_kind"])}
S["by_side_session"] = {f"{a} {b}": stats(g) for (a, b), g in valid.groupby(["side", "session"])}
S["exit_reasons"] = valid.exit_reason.value_counts().to_dict()

# target curve from MFE: a target of X R is hit iff MFE >= X (MFE is measured before the exit)
S["target_curve"] = {}
for X in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
    hit = valid.mfe_R >= X
    S["target_curve"][str(X)] = dict(hit_rate=float(hit.mean()), exp_R=float(hit.mean() * X - (1 - hit.mean()) * 1.0),
                                     exp_R_per_risk=float((hit.mean() * X - (1 - hit.mean())) ))
S["mfe_dist"] = {f"mfe>={X}": float((valid.mfe_R >= X).mean()) for X in (0.25, 0.5, 1, 1.5, 2, 2.5, 3)}
S["loser_mfe_dist"] = {f"mfe>={X}": float((valid[valid.loss].mfe_R >= X).mean()) for X in (0.25, 0.5, 1, 1.5, 2, 2.5)}
S["winner_mae_dist"] = {f"mae>={X}": float((valid[~valid.loss].mae_R >= X).mean()) for X in (0.25, 0.5, 0.75)}
S["time_to_loss"] = dict(median_minutes=float(valid[valid.loss].minutes_held.median()),
                         within_15min=float((valid[valid.loss].minutes_held <= 15).mean()),
                         within_30min=float((valid[valid.loss].minutes_held <= 30).mean()),
                         within_60min=float((valid[valid.loss].minutes_held <= 60).mean()))
S["time_to_win"] = dict(median_minutes=float(valid[~valid.loss].minutes_held.median()))
S["cost"] = dict(median_cost_R=float(valid.cost_R.median()), mean_cost_R=float(valid.cost_R.mean()),
                 spread_by_year=E.SPREAD_BY_YEAR)

# skipped setups (position already open): hypothetical outcome, independent simulation
skv = sk[sk.exit_reason.isin(["SL", "TP"])].copy()
S["skipped"] = dict(n=int(len(skv)), win_rate=float((skv.result_R > 0).mean()) if len(skv) else np.nan,
                    avg_R=float(skv.result_R.mean()) if len(skv) else np.nan,
                    n_distinct_zone_bar=int(len(skv.drop_duplicates(["time_ist", "poc"]))) if len(skv) else 0)

# ----------------------------------------------------------------------------
# loss-pattern conditions
# ----------------------------------------------------------------------------
v = valid
rows = []
rows += cond_rows(v, "Side", v.side)
rows += cond_rows(v, "Rectangle type", v.zone_kind)
rows += cond_rows(v, "Session (UTC)", v.session)
rows += cond_rows(v, "Hour (IST)", v.hour_ist.astype(int).map(lambda x: f"{x:02d}"))
rows += cond_rows(v, "Day of week", v.dow)
rows += cond_rows(v, "False breakout (close back inside within 3 bars)", v.false_breakout_3bars.map({True: "yes", False: "no"}),
                  "post-hoc pattern, not known at entry")
rows += cond_rows(v, "Immediate reversal (-0.5R within 15 min)", (v.min_to_mae05 <= 15).map({True: "yes", False: "no"}),
                  "post-hoc pattern")
rows += cond_rows(v, "Tap on the confirmation candle itself", (v.bars_since_tap == 0).map({True: "same bar", False: "earlier bar"}))
rows += cond_rows(v, "Bars between tap and confirmation", pd.cut(v.bars_since_tap, [-1, 0, 2, 5, 11], labels=["0", "1-2", "3-5", "6-11"]).astype(str))
rows += cond_rows(v, "Touch count on the rectangle today", pd.cut(v.taps, [0, 1, 2, 4, 1000], labels=["1 (first touch)", "2", "3-4", "5+"]).astype(str))
rows += cond_rows(v, "Weak tap (wick past POC < 10% of rectangle)", (v.tap_depth_zh < 0.10).map({True: "weak", False: "deep"}))
rows += cond_rows(v, "Tap depth past POC (rectangle heights)", qbucket(v.tap_depth_zh))
rows += cond_rows(v, "Tap candle closed inside the rectangle", v.tap_closed_inside.map({True: "yes", False: "no"}))
rows += cond_rows(v, "Rectangle height (USD)", qbucket(v.zone_height))
rows += cond_rows(v, "Rectangle height (% of prior day range)", qbucket(100 * v.zone_h_pct_range, fmt="{:.1f}"))
rows += cond_rows(v, "Confirmation candle range / ATR14", qbucket(v.conf_range_atr))
rows += cond_rows(v, "Confirmation candle range / rectangle height", qbucket(v.conf_range_zh))
rows += cond_rows(v, "Large confirmation candle (range > 2 ATR)", (v.conf_range_atr > 2).map({True: "yes", False: "no"}))
rows += cond_rows(v, "Confirmation body / range", qbucket(v.conf_body_pct))
rows += cond_rows(v, "Close beyond the rectangle edge (rectangle heights)", qbucket(v.conf_ext_zh))
rows += cond_rows(v, "Entry distance from POC (rectangle heights)", qbucket(v.entry_dist_poc_zh))
rows += cond_rows(v, "Entry distance from POC (R)", qbucket(v.entry_dist_poc_R))
rows += cond_rows(v, "Risk in USD", qbucket(v.risk_pts))
rows += cond_rows(v, "Risk / ATR14", qbucket(v.risk_atr))
rows += cond_rows(v, "Volatility regime (ATR14 / its 7-day median)", qbucket(v.atr_rel))
rows += cond_rows(v, "High volatility (ATR > 1.5x median)", (v.atr_rel > 1.5).map({True: "yes", False: "no"}))
rows += cond_rows(v, "Nearest other rectangle (gap in rectangle heights)", qbucket(v.nearest_gap_zh))
rows += cond_rows(v, "Rectangles too close (gap < 1 rectangle height)", (v.nearest_gap_zh < 1).map({True: "yes", False: "no"}))
rows += cond_rows(v, "Rectangles on the day", v.n_zones.astype(int).astype(str))
rows += cond_rows(v, "Rectangle volume share of the day", qbucket(100 * v.zone_share, fmt="{:.1f}"))
rows += cond_rows(v, "Target beyond the prior day's High/Low", v.tp_beyond_pdhl.map({True: "yes", False: "no"}))
rows += cond_rows(v, "Room to prior day High/Low (R)", pd.cut(v.room_to_pdhl_R, [-1e9, 0, 1.5, 3, 6, 1e9],
                                                             labels=["past it already", "0-1.5R", "1.5-3R", "3-6R", ">6R"]).astype(str))
rows += cond_rows(v, "Prior day range (USD)", qbucket(v.day_range))
rows += cond_rows(v, "Trades already taken today", pd.cut(v.prior_trades_today, [-1, 0, 1, 2, 100], labels=["0 (first)", "1", "2", "3+"]).astype(str))
rows += cond_rows(v, "Previous trade result", pd.Series(np.where(v.prior_R.isna(), "none", np.where(v.prior_R > 0, "win", "loss")), index=v.index))
rows += cond_rows(v, "Year", v.year.astype(str))
rows += cond_rows(v, "Side x rectangle type", v.side + " " + v.zone_kind)
rows += cond_rows(v, "Side x session", v.side + " " + v.session)
rows += cond_rows(v, "Rectangle type x session", v.zone_kind + " " + v.session)
rows += cond_rows(v, "Side x first touch", v.side + " " + np.where(v.first_touch, "first touch", "repeat"))
rows += cond_rows(v, "Session x volatility", v.session + " " + np.where(v.atr_rel > 1.5, "high vol", "normal"))
LP = pd.DataFrame(rows)
LP.to_csv(f"{R}/loss_patterns.csv", index=False)

# ----------------------------------------------------------------------------
# what-if diagnostics (shadow runs; the baseline itself is untouched)
# ----------------------------------------------------------------------------
print("loading data for shadow runs ...")
m1 = E.load_m1(E.v1_chunk_files())
shadow = {}


def shadow_run(name, **kw):
    t, _, _ = E.run(m1, kw, verbose=False)
    t = t[t.exit_reason.isin(["SL", "TP"])]
    shadow[name] = stats(t)
    shadow[name]["params"] = kw
    print(f"  {name}: n={len(t)} WR={100 * shadow[name]['win_rate']:.1f}% total={shadow[name]['total_R']:+.1f}R avg={shadow[name]['avg_R']:+.3f}")
    return t


shadow_run("baseline (rerun)")
shadow_run("no POC-tap requirement", require_tap=False)
shadow_run("tap must be on the confirmation candle", tap_valid=1)
shadow_run("tap valid all day", tap_valid=100000)
shadow_run("no candle-colour requirement", require_colour=False)
shadow_run("unlimited trades per rectangle", max_per_zone=99)
shadow_run("HVN rectangles only (no PDH/PDL)", trade_edge=False)
shadow_run("longs only", allow_short=False)
shadow_run("shorts only", allow_long=False)
S["shadow"] = shadow

json.dump(S, open(f"{R}/baseline_stats.json", "w"), indent=1, default=float)

# ----------------------------------------------------------------------------
# BASELINE TEST REPORT
# ----------------------------------------------------------------------------
A = S["all"]
lines = []
w = lines.append
w("# Baseline Test Report - Previous-Day Volume Zones strategy on XAUUSD 5-min\n")
w(f"Data: Dukascopy XAUUSD M1, {info['first'][:10]} to {info['last'][:10]} UTC, {info['m1_bars']:,} M1 bars aggregated to "
  f"{info['bars']:,} five-minute bars. 39 of 61 calendar months are present (the gaps are missing downloads, "
  f"not market closures). {info['days_built']} daily profiles were built; {info['days_skipped_short']} short days "
  f"(Saturday stubs, holidays) kept the previous zones; {info['stale_days']} trading days were skipped because the "
  f"last profile was older than 4 days (a data gap).\n")
w("Rules under test, exactly as specified and as coded in `PD_VolumeZones_Strategy.pine` with its default inputs:\n")
w("- Day = calendar day in Asia/Kolkata. Profile = fixed-range volume profile of the previous completed day, 40 bins, "
  "rectangles = protruding high-volume bins (prominence >= 0.20, >= 25% of the biggest bin, up to 3 bins tall), "
  "max 4 internal rectangles plus a 2-bin rectangle at the prior Day High and Day Low. POC = highest-volume bin.")
w("- LONG: a bar's range crosses the POC (that bar or one of the previous 11), then a green 5-min candle closes above the "
  "rectangle top. Entry = that close. SL = rectangle bottom. TP = entry + 3 x (entry - SL). SHORT is the mirror.")
w("- One position at a time, one entry per rectangle per day, no SL/TP changes, no session filter.")
w("- Exits are resolved on the M1 path (open, nearer extreme, farther extreme, close). Gaps through a level fill at the open.")
w(f"- Costs: the headline numbers are GROSS (no spread, like the TradingView tester by default). The 'Net R' column "
  f"subtracts one spread per trade, assumed per year as {E.SPREAD_BY_YEAR} USD; median cost = {S['cost']['median_cost_R']:.2f}R per trade.")
w(f"- {excluded} trades were excluded because their exit ran into a data gap or the end of the data.\n")
w("## Headline\n")
w(STATS_HEAD + fmt_stats_row("All trades", A))
w(f"\nBreak-even win rate for a 1:3 trade is 25.0%. The realised win rate is {100 * A['win_rate']:.1f}%, so the gross edge is "
  f"{A['avg_R']:+.3f}R per trade; after the assumed spread it is {A['avg_net_R']:+.3f}R per trade.\n")
w("Exit reasons: " + ", ".join(f"{k} {vv}" for k, vv in S["exit_reasons"].items()) + ".\n")
w("## Long vs short\n")
w(STATS_HEAD + "".join(fmt_stats_row(k, s) for k, s in S["by_side"].items()))
w("\n## Rectangle type\n")
w(STATS_HEAD + "".join(fmt_stats_row(k, s) for k, s in S["by_kind"].items()))
w("\n## Side x rectangle type\n")
w(STATS_HEAD + "".join(fmt_stats_row(k, s) for k, s in S["by_side_kind"].items()))
w("\n## Session (UTC)\n")
w(STATS_HEAD + "".join(fmt_stats_row(k, s) for k, s in S["by_session"].items()))
w("\n## Year by year\n")
w(STATS_HEAD + "".join(fmt_stats_row(str(k), s) for k, s in S["by_year"].items()))
w("\n## Month by month\n")
w(STATS_HEAD + "".join(fmt_stats_row(k, s) for k, s in S["by_month"].items()))
w("\n## Excursions and timing\n")
w(f"- Average MFE {A['avg_mfe_R']:.2f}R, average MAE {A['avg_mae_R']:.2f}R. Median hold {A['median_minutes']:.0f} min "
  f"(losers {S['time_to_loss']['median_minutes']:.0f} min, winners {S['time_to_win']['median_minutes']:.0f} min).")
w(f"- Losers stopped within 15 min: {100 * S['time_to_loss']['within_15min']:.0f}%, within 30 min: "
  f"{100 * S['time_to_loss']['within_30min']:.0f}%, within 60 min: {100 * S['time_to_loss']['within_60min']:.0f}%.")
w("- Share of ALL trades whose MFE reached at least: " + ", ".join(f"{k.split('>=')[1]}R {100 * vv:.0f}%" for k, vv in S["mfe_dist"].items()) + ".")
w("- Share of LOSING trades that were first in profit by at least: " + ", ".join(f"{k.split('>=')[1]}R {100 * vv:.0f}%" for k, vv in S["loser_mfe_dist"].items()) + ".")
w("- Share of WINNING trades that first went against by at least: " + ", ".join(f"{k.split('>=')[1]}R {100 * vv:.0f}%" for k, vv in S["winner_mae_dist"].items()) + ".\n")
w("Target curve (same entries and stop, target moved; computed from MFE, so it is exact for this trade set):\n")
w("| Target | Hit rate | Expectancy (R per trade) |\n|---|---|---|")
for X, d in S["target_curve"].items():
    w(f"| {X}R | {100 * d['hit_rate']:.1f}% | {d['exp_R']:+.3f} |")
w("\n## Setups skipped because a position was already open\n")
w(f"{S['skipped']['n']:,} setup signals fired while a trade was open (a rectangle re-fires on every new tap, so this is "
  f"inflated; {S['skipped']['n_distinct_zone_bar']:,} distinct). Simulated independently they would have had a win rate of "
  f"{100 * S['skipped']['win_rate']:.1f}% and {S['skipped']['avg_R']:+.3f}R per trade.\n")
open("BASELINE_TEST_REPORT.md", "w", encoding="utf-8").write("\n".join(lines))

# ----------------------------------------------------------------------------
# LOSS PATTERN REPORT
# ----------------------------------------------------------------------------
base_wr = A["win_rate"]
base_loss_rate = 1 - base_wr
tot_losses = A["losses"]
L = []
w = L.append
w("# Loss Pattern Report - Previous-Day Volume Zones strategy on XAUUSD 5-min\n")
w(f"Base: {A['n']:,} trades, {A['losses']:,} losses ({100 * base_loss_rate:.1f}%), {A['wins']:,} wins, total {A['total_R']:+.1f}R gross. "
  "Every loss is exactly -1R (stop at the rectangle edge) and every win +3R, so 'negative R contribution' of a bucket equals "
  "its number of losses; what separates buckets is the WIN RATE against the 25% break-even. 'Lift' = the bucket's loss rate "
  "divided by the overall loss rate (1.00 = no different). 'z' = two-proportion z-score of the bucket's win rate against all "
  "other trades; |z| >= 2 is the usual significance bar, and with 40+ buckets a few |z| of 2 appear by chance.\n")
w("## How to read the tables\n")
w("- Conditions known BEFORE entry can become filters. Conditions marked post-hoc (false breakout, immediate reversal) "
  "describe HOW trades lose, not what to filter on.\n")

fam_order = list(dict.fromkeys(LP.family))
cols = ["bucket", "n", "wins", "losses", "win_rate", "avg_R", "sum_R", "pf", "share_of_losses", "lift", "z_vs_rest"]
fm = {"win_rate": "{:.1%}", "avg_R": "{:+.3f}", "sum_R": "{:+.1f}", "pf": "{:.2f}", "share_of_losses": "{:.1%}", "lift": "{:.2f}", "z_vs_rest": "{:+.1f}"}
w("## All conditions\n")
for fam in fam_order:
    sub = LP[LP.family == fam]
    note = sub.note.iloc[0]
    w(f"### {fam}" + (f"  _({note})_" if note else "") + "\n")
    w(md_table(sub, cols, fm))

# ranked findings: pre-entry conditions only, buckets with n >= 60
pre = LP[~LP.family.str.contains("False breakout|Immediate reversal")]
big = pre[pre.n >= 60].copy()
worst = big.sort_values("avg_R").head(15)
best = big.sort_values("avg_R", ascending=False).head(15)
freq = big[big.lift > 1.05].sort_values("losses", ascending=False).head(12)
w("\n## Ranked findings\n")
w("### Most frequent losing conditions (loss rate above average, ranked by number of losses)\n")
w(md_table(freq, ["family", "bucket", "n", "losses", "share_of_losses", "win_rate", "lift", "sum_R", "z_vs_rest"],
           {"share_of_losses": "{:.1%}", "win_rate": "{:.1%}", "lift": "{:.2f}", "sum_R": "{:+.1f}", "z_vs_rest": "{:+.1f}"}))
w("\n### Buckets that lose the most money (lowest average R, n >= 60)\n")
w(md_table(worst, ["family", "bucket", "n", "win_rate", "avg_R", "sum_R", "z_vs_rest"], {"win_rate": "{:.1%}", "avg_R": "{:+.3f}", "sum_R": "{:+.1f}", "z_vs_rest": "{:+.1f}"}))
w("\n### Buckets that make the most money (highest average R, n >= 60)\n")
w(md_table(best, ["family", "bucket", "n", "win_rate", "avg_R", "sum_R", "z_vs_rest"], {"win_rate": "{:.1%}", "avg_R": "{:+.3f}", "sum_R": "{:+.1f}", "z_vs_rest": "{:+.1f}"}))

w("\n## What-if diagnostics (shadow runs - the baseline rules are NOT changed, these only measure what each rule does)\n")
w("| Variant | Trades | Win rate | Total R | Avg R | PF | Max DD (R) | Net R (spread) |\n|---|---|---|---|---|---|---|---|")
for k, s in S["shadow"].items():
    w(f"| {k} | {s['n']} | {100 * s['win_rate']:.1f}% | {s['total_R']:+.1f} | {s['avg_R']:+.3f} | {s['pf']:.2f} | {s['max_dd_R']:.1f} | {s['net_R']:+.1f} |")
w("")
open("LOSS_PATTERN_REPORT.md", "w", encoding="utf-8").write("\n".join(L))
print("reports written")
