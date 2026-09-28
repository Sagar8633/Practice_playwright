"""finalize_reports.py - append the verdict / findings sections (numbers pulled from
results/baseline_stats.json and results/trade_log.csv) to the two reports."""
import json

import numpy as np
import pandas as pd

S = json.load(open("results/baseline_stats.json"))
T = pd.read_csv("results/trade_log.csv")
T = T[T.exit_reason.isin(["SL", "TP"])]
A = S["all"]
lp = pd.read_csv("results/loss_patterns.csv")


def row(fam, bucket):
    r = lp[(lp.family == fam) & (lp.bucket == bucket)]
    return r.iloc[0] if len(r) else None


# net R by risk quartile (cost matters most on tiny stops)
T["risk_q"] = pd.qcut(T.risk_pts, 4, labels=["smallest 25%", "25-50%", "50-75%", "largest 25%"])
rq = T.groupby("risk_q", observed=True).agg(n=("result_R", "size"), risk=("risk_pts", "median"), win_rate=("win_loss", lambda s: (s == "WIN").mean()),
                                            gross_R=("result_R", "sum"), cost_R=("cost_R", "mean"), net_R=("net_R", "sum"))
fb = row("False breakout (close back inside within 3 bars)", "yes")
ir = row("Immediate reversal (-0.5R within 15 min)", "yes")
pdh_long = row("Side x rectangle type", "long PDH")
hvn = row("Rectangle type", "HVN")
tp_out = row("Target beyond the prior day's High/Low", "yes")
tp_in = row("Target beyond the prior day's High/Low", "no")
room36 = row("Room to prior day High/Low (R)", "3-6R")
lowvol = row("Volatility regime (ATR14 / its 7-day median)", "0.28 to 0.81")
same_bar = row("Tap on the confirmation candle itself", "same bar")
early_bar = row("Tap on the confirmation candle itself", "earlier bar")
asia_short = row("Side x session", "short Asia 00-07 UTC")
y = S["by_year"]
sh = S["shadow"]
base = sh["baseline (rerun)"]


def shrow(name):
    s = sh[name]
    return (f"| {name} | {s['n']} | {100 * s['win_rate']:.1f}% | {s['total_R']:+.1f} | {s['avg_R']:+.3f} | {s['net_R']:+.1f} | "
            f"{s['n'] - base['n']:+d} trades, {s['avg_R'] - base['avg_R']:+.3f}R/trade vs baseline |")


# ---------------------------------------------------------------- baseline verdict
B = []
w = B.append
w("\n## Verdict\n")
w(f"- Gross: {A['n']:,} trades, {100 * A['win_rate']:.1f}% winners against a 25.0% break-even, {A['total_R']:+.1f}R "
  f"({A['avg_R']:+.3f}R per trade), profit factor {A['pf']:.2f}, worst drawdown {A['max_dd_R']:.0f}R, longest losing run {A['max_loss_streak']}.")
w(f"- Net of one spread per trade (median cost {S['cost']['median_cost_R']:.2f}R): {A['net_R']:+.1f}R "
  f"({A['avg_net_R']:+.3f}R per trade). The strategy is break-even before costs and loses after them.")
w(f"- The result is one year: 2025 made {y['2025']['total_R']:+.1f}R; the other four years together made "
  f"{sum(v['total_R'] for k, v in y.items() if k != '2025'):+.1f}R over {sum(v['n'] for k, v in y.items() if k != '2025'):,} trades.")
w(f"- Long vs short: {100 * S['by_side']['long']['win_rate']:.1f}% / {100 * S['by_side']['short']['win_rate']:.1f}%, "
  f"{S['by_side']['long']['total_R']:+.1f}R / {S['by_side']['short']['total_R']:+.1f}R. Not a significant difference.")
w(f"- Rectangle types: the volume rectangles (HVN) are flat ({hvn.n} trades, {100 * hvn.win_rate:.1f}%, {hvn.sum_R:+.1f}R); "
  f"the previous Day High rectangle traded long is the only slice with a positive result ({pdh_long.n} trades, "
  f"{100 * pdh_long.win_rate:.1f}%, {pdh_long.sum_R:+.1f}R, z {pdh_long.z_vs_rest:+.1f}).")
w("\n### Cost by stop size (why break-even gross becomes a loss)\n")
w("| Risk quartile | Trades | Median risk (USD) | Win rate | Gross R | Avg cost (R) | Net R |\n|---|---|---|---|---|---|---|")
for k, r in rq.iterrows():
    w(f"| {k} | {r.n} | {r.risk:.2f} | {100 * r.win_rate:.1f}% | {r.gross_R:+.1f} | {r.cost_R:.2f} | {r.net_R:+.1f} |")
w("")
open("BASELINE_TEST_REPORT.md", "a", encoding="utf-8").write("\n".join(B))

# ---------------------------------------------------------------- loss-pattern findings
L = []
w = L.append
w("\n## Findings\n")
w("### A. What is working\n")
w(f"- The mechanics: every loss is exactly -1R and every win exactly +3R (stop at the rectangle edge, target at 3R), the entry "
  f"is the confirmation close, and the zone engine reproduces the reference chart's density (median 3 internal rectangles, ~2 USD tall).")
w(f"- The gross expectancy is not negative: {100 * A['win_rate']:.1f}% winners vs 25.0% needed, {A['avg_R']:+.3f}R per trade. "
  f"The rules do not destroy money by themselves; they just do not make any before costs.")
w(f"- Breakouts that continue beyond the previous day's range: setups whose 3R target lies beyond the prior Day High/Low win "
  f"{100 * tp_out.win_rate:.1f}% ({tp_out.n} trades, {tp_out.sum_R:+.1f}R) against {100 * tp_in.win_rate:.1f}% ({tp_in.n} trades, "
  f"{tp_in.sum_R:+.1f}R) when the target sits inside yesterday's range (z {tp_out.z_vs_rest:+.1f}). Long entries from the prior "
  f"Day High rectangle are the best single slice ({pdh_long.n} trades, {100 * pdh_long.win_rate:.1f}%, {pdh_long.sum_R:+.1f}R).")
w(f"- A tap that happened on an EARLIER bar than the confirmation candle wins {100 * early_bar.win_rate:.1f}% ({early_bar.n} trades) "
  f"vs {100 * same_bar.win_rate:.1f}% when the tap and the breakout are the same candle ({same_bar.n} trades, {same_bar.sum_R:+.1f}R). "
  f"Suggestive (z {early_bar.z_vs_rest:+.1f}), not proven.\n")
w("### B. Where exactly the money is lost\n")
w(f"- Right after entry. {fb.n} of {A['n']} entries ({100 * fb.n / A['n']:.0f}%) close back inside the rectangle within 3 bars; "
  f"they win {100 * fb.win_rate:.1f}% and hold {100 * fb.share_of_losses:.0f}% of all losses ({fb.sum_R:+.0f}R). "
  f"{ir.n} entries ({100 * ir.n / A['n']:.0f}%) are 0.5R under water within 15 minutes and win {100 * ir.win_rate:.1f}%. "
  f"Half of all losers are stopped within {S['time_to_loss']['median_minutes']:.0f} minutes; "
  f"{100 * S['time_to_loss']['within_30min']:.0f}% within 30 minutes. The 'confirmation close' does not confirm anything.")
w(f"- In the spread. Median stop {A['median_risk']:.2f} USD against a 0.25-0.50 USD spread = {S['cost']['median_cost_R']:.2f}R per trade; "
  f"the smallest-stop quartile pays {rq.iloc[0].cost_R:.2f}R per trade and turns {rq.iloc[0].gross_R:+.1f}R gross into {rq.iloc[0].net_R:+.1f}R net.")
w(f"- In the volume rectangles themselves: {hvn.n} HVN trades ({100 * hvn.n / A['n']:.0f}% of all) return {hvn.sum_R:+.1f}R. "
  f"Rectangle height, volume share, prominence, distance to the next rectangle and number of rectangles show no relation to the outcome "
  f"(all |z| < 2). The profile machinery is not adding information over a plain horizontal level.")
w(f"- In 2024 ({y['2024']['n']} trades, {100 * y['2024']['win_rate']:.1f}%, {y['2024']['total_R']:+.1f}R) and 2026 so far "
  f"({y['2026']['n']} trades, {y['2026']['total_R']:+.1f}R).")
w(f"- Shorts in the Asian session ({asia_short.n} trades, {100 * asia_short.win_rate:.1f}%, {asia_short.sum_R:+.1f}R) and "
  f"low-volatility regimes (ATR14 below 0.81x its 7-day median: {lowvol.n} trades, {100 * lowvol.win_rate:.1f}%, {lowvol.sum_R:+.1f}R, z {lowvol.z_vs_rest:+.1f}).\n")
w("### C. Most frequent losing condition\n")
w(f"- Post-hoc (how): the failed breakout - price back inside the rectangle within 3 bars - is present in {100 * fb.share_of_losses:.0f}% of losses.")
w(f"- Pre-entry (when): 'tap and breakout on the same candle' ({same_bar.n} trades, {100 * same_bar.share_of_losses:.0f}% of losses, "
  f"win rate {100 * same_bar.win_rate:.1f}%) and 'target inside yesterday's range' ({tp_in.n} trades, {100 * tp_in.share_of_losses:.0f}% of losses, "
  f"{100 * tp_in.win_rate:.1f}%). Both are frequent mainly because the strategy trades there often (lift {same_bar.lift:.2f} and {tp_in.lift:.2f}); "
  f"neither is toxic on its own.\n")
w("### D. Condition contributing the most negative R\n")
w("- Every loss is -1R, so a bucket's negative R equals its loss count; the meaningful ranking is by NET result. The largest net-negative "
  "buckets with a plausible mechanism:")
w(f"  - target inside the prior day's range, 3-6R of room to the Day High/Low: {room36.n} trades, {100 * room36.win_rate:.1f}%, {room36.sum_R:+.1f}R (z {room36.z_vs_rest:+.1f});")
w(f"  - low-volatility regime: {lowvol.n} trades, {lowvol.sum_R:+.1f}R;")
w(f"  - 2024: {y['2024']['total_R']:+.1f}R; Asian-session shorts: {asia_short.sum_R:+.1f}R;")
w(f"  - the smallest-stop quartile after costs: {rq.iloc[0].net_R:+.1f}R net.")
w("- Quartile buckets that look bad but whose neighbours are fine (entry distance 0.54-0.68R, candle body 0.66-0.82) are non-monotonic "
  "and treated as noise.\n")
w("### E. Rules that appear unnecessary (shadow runs)\n")
w("| Variant | Trades | Win rate | Total R | Avg R | Net R | Delta |\n|---|---|---|---|---|---|---|")
for k in sh:
    w(shrow(k))
w("")
w("Read the deltas against the baseline row: a rule is 'doing nothing' when removing it leaves the win rate and the R per trade "
  "unchanged and only changes the trade count; it is 'protective' when removing it lowers the R per trade; it is 'harmful' when "
  "removing it raises the R per trade.\n")
w("### F. Gaps worth testing in Version 2\n")
w("1. Failed-breakout handling: exit when a bar closes back inside the rectangle (cut at a fraction of R instead of the full -1R), or "
  "require a second close beyond the edge / a retest that holds. This targets the mechanism behind half of all losses.")
w("2. Cost-aware selection: skip stops smaller than a minimum in USD or in ATR; the smallest-stop quartile is where the spread eats the result.")
w("3. Previous-day range as the target boundary: only take setups whose 3R target lies beyond the prior Day High/Low (or whose room is > 6R).")
w("4. Directional context: the only positive slice is long breakouts of the prior Day High; test a with-trend filter "
  "(prior day close vs open, price vs the prior day's POC) and PDH-long / PDL-short only.")
w("5. Volatility gate: skip when ATR14 is below 0.8x its 7-day median.")
w("6. Tap timing: require the POC tap at least one bar before the confirmation candle (the 'tap, hold, then break' pattern).")
w("7. Session: Asian-session shorts and the 15:00-17:00 IST hours are the weak spots; London open (14:00 IST) the strong one. Test a session window.")
w("8. Target: see the target curve in the baseline report - compare the expectancy at 1.5R/2R/3R with the same stop before deciding that 3R is right.")
w("9. Data: repeat on OANDA tick-volume profiles on TradingView (the rectangles differ from Dukascopy's) and with 1-min intrabar profiles.")
w("")
open("LOSS_PATTERN_REPORT.md", "a", encoding="utf-8").write("\n".join(L))
print("appended findings")
print(rq)
print(pd.DataFrame(sh).T[["n", "win_rate", "total_R", "avg_R", "net_R"]])
print("target curve:", {k: round(v["exp_R"], 3) for k, v in S["target_curve"].items()})
print("skipped:", S["skipped"], "| time_to_loss:", S["time_to_loss"])
