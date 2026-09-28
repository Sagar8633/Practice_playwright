"""Write FINAL_REPORT.md (20 sections, Part 12) from results/report_data.json."""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "results", "report_data.json")))
PT = pd.DataFrame(D["period_tables"])
PBN = {"A_pingpong": "A ping-pong", "B1_pullback": "B1 breakout+pullback", "B2_immediate": "B2 breakout at close"}


def md(df, fmt="{:.3f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else fmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def pt(pb, cost, period):
    return PT[(PT.playbook == pb) & (PT.cost == cost) & (PT.period == period)].iloc[0]


def ptable(pb, cost):
    t = PT[(PT.playbook == pb) & (PT.cost == cost)][["period", "n", "win_rate", "avg_win", "avg_loss", "pf", "expectancy", "total_r",
                                                      "max_dd_r", "max_loss_streak", "median_hold_h", "avg_rr", "mfe_r", "mae_r", "ci_lo", "ci_hi"]]
    return md(t)


def exp_table(name, pbs=None, cols=("variant", "playbook", "period", "n", "win_rate", "expectancy", "pf", "total_r", "max_dd_r", "median_hold_h")):
    e = pd.DataFrame(D["experiments"][name])
    e = e[e.period != "ALL"]
    if pbs:
        e = e[e.playbook.isin(pbs)]
    return md(e[list(cols)])


def stage_table(pb):
    s = pd.DataFrame(D["stages"])
    s = s[(s.playbook == pb) & (s.period != "ALL")][["stage", "label", "cost", "period", "n", "win_rate", "expectancy", "pf", "total_r", "max_dd_r", "ci_lo", "ci_hi"]]
    return md(s)


A = pt("A_pingpong", "real", "ALL"); Ai = pt("A_pingpong", "ideal", "ALL")
B1 = pt("B1_pullback", "real", "ALL"); B1i = pt("B1_pullback", "ideal", "ALL")
B2 = pt("B2_immediate", "real", "ALL"); B2i = pt("B2_immediate", "ideal", "ALL")
S = D["structure_stats"]; F = D["A_facts"]
tax_A = pd.DataFrame(D["taxonomy_A_pingpong"]); tax_B1 = pd.DataFrame(D["taxonomy_B1_pullback"]); tax_B2 = pd.DataFrame(D["taxonomy_B2_immediate"])
filt_A = pd.DataFrame(D["filters_A_pingpong"]); filt_B1 = pd.DataFrame(D["filters_B1_pullback"]); filt_B2 = pd.DataFrame(D["filters_B2_immediate"])
wf = pd.DataFrame(D["walk_forward"])
sy = pd.DataFrame(D["stages_yearly"])
costs_A = pd.DataFrame(D["costs"]["A_pingpong"]); costs_B1 = pd.DataFrame(D["costs"]["B1_pullback"])
comb = pd.DataFrame(D["combined"])
sess = {pb: pd.DataFrame(D[f"by_session_{pb}"]) for pb in PBN}
stype_side = {pb: pd.DataFrame(D[f"by_stype_side_{pb}"]) for pb in PBN}
byyear = {pb: pd.DataFrame(D[f"by_year_{pb}"]) for pb in PBN}
va = pd.DataFrame(D["experiments"]["va_source_sensitivity"]); vad = pd.DataFrame(D["experiments"]["va_level_differences"])


def tax_md(t):
    t = t[["category", "trades_flagged", "losses", "loss_pct", "avg_loss", "max_loss", "total_loss", "share_of_total_loss", "max_consec", "dd_window_contribution"]]
    return md(t, "{:.2f}")


def filt_md(f):
    f = f[f.period != "ALL"][["filter", "period", "n_before", "exp_before", "pf_before", "n_after", "exp_after", "pf_after", "removed", "removed_mean_r", "survives"]]
    return md(f)


def yearly_pivot(pb):
    s = sy[sy.playbook == pb].pivot_table(index=["stage", "label"], columns="year", values="expectancy").reset_index()
    return md(s)


def ex_md(rows):
    if not rows:
        return "(none)"
    df = pd.DataFrame(rows)[["entry_time", "session", "stype", "side", "entry_type", "entry", "stop", "target", "exit", "rr_actual", "r_net", "exit_reason", "hold_h", "mfe_r", "mae_r", "imp_size_atr", "width_atr", "loss_category"]]
    return md(df, "{:.2f}")


def surv(f):
    s = f[f.period == "ALL"][["filter", "survives", "n_before", "exp_before", "n_after", "exp_after", "removed_mean_r"]]
    return md(s)


txt = f"""# Patrick Nill PBD counter-trend framework on XAUUSD: baseline test and loss study

Run date: 2026-09-26. Data: Sep 2021 to 25 Sep 2026 (60 of 61 months). All figures are in R
(multiples of the planned risk per trade). "Real" = XM spread, 0.10 USD/oz slippage, 1-minute
execution delay, XM swap; "ideal" = signal-bar close fill with zero costs.

**Headline.** Under the pre-registered objective rules, the framework has no positive expectancy on
XAUUSD in any of the three chronological periods, with or without costs. Ideal execution is
approximately flat ({Ai.expectancy:+.3f}R per trade for ping-pong, {B1i.expectancy:+.3f}R for breakout+pullback,
{B2i.expectancy:+.3f}R for breakout-at-close); realistic execution turns that into {A.expectancy:+.3f}R,
{B1.expectancy:+.3f}R and {B2.expectancy:+.3f}R (profit factors {A.pf:.2f}, {B1.pf:.2f}, {B2.pf:.2f}).
The 95% bootstrap interval of the mean trade excludes zero on the negative side for every playbook.
The mechanism is measurable: ping-pong trades lose to continuation of the impulse
({float(tax_A.set_index('category').loc['trend_continuation_against','share_of_total_loss']):.0f}% of ping-pong loss),
breakout trades lose to false breakouts ({float(tax_B1.set_index('category').loc['false_breakout','share_of_total_loss']):.0f}% of pullback-playbook loss),
and the objective ranges are far smaller and shorter-lived than the multi-day swings the source describes
(median hold {A.median_hold_h:.1f} h, {F['hold_le_4h_share']*100:.0f}% of trades closed within 4 h). No adaptation tested is
positive in the development period; the two that are positive in validation and out-of-sample
(confirmed-breakout entry with 1.5 ATR stops, and ping-pong in the London/New York overlap) owe their sign
to 2025 alone. **No Gold Strategy Specification is issued.** Section 20 states what the data does and does not support.

---

## 1. Strategy explanation

The source (Patrick Nill, "Counter-Trend Swing Trading") is a discretionary method built on the PBD
model of Market Profile shapes. A **P structure** is a large upward impulse followed by a consolidation
that forms above the origin of the impulse; a **B structure** is the mirror after a downward impulse.
(The source does not define the D element; in Market Profile usage D is the balanced, bell-shaped day.)
The impulse itself is never traded. The 15-minute chart frames the impulse and the range; the weekly
Market Profile Value Area High and Low (VAH/VAL) are the reference zones, and a setup that lines up
with them is considered "significantly stronger". Once price reaches a marked zone the trader drops to
footprint and order-flow charts for the entry.

Two playbooks: (1) **range ping-pong**, buy near the range low and sell near the range high until the
range breaks; (2) **breakout / pullback**, wait for a decisive break of the range, preferably for a
pullback to the broken edge, and enter in the direction of the resumed move. Targets sit back near the
origin of the initial impulse; the stop is fixed before entry, over, inside or above the zone. Risk is
at most 1% of equity per trade. Published expectations for the method: 50-60% win rate, holds of 4 hours
to 3 days (average about one day), losing streaks of 10-20 called normal, any drawdown above 20% rejected,
no trading during high-impact news.

## 2. Exact objective rules

Machine-readable version: `spec/pbd_xauusd_rules.json` (also `results/deliverables/01_rule_specification.json`).
Every parameter below was fixed before the first backtest and is the **baseline**; every later variant
changes one parameter.

**Impulse (definition A, primary "atr").** Window of N = 8 M15 bars (2 h). Net move |close[i] - close[i-8]|
>= 3.5 x ATR14 measured before the window, efficiency ratio (net / sum of absolute close changes) >= 0.6,
no data gap inside the window. Alternatives tested: 98th percentile of trailing-30-day 8-bar moves,
range expansion (window range >= 3 x trailing median), and >= 5 consecutive same-direction closes with
>= 2 ATR net. Origin = lowest low (P) / highest high (B) inside 4N bars before the window, accepted only if
the path from it never retraced more than half of itself; otherwise the window's own extreme. The extreme
keeps updating while price makes new highs/lows. Abandon if a close retraces more than 61.8% of the impulse
or if no range forms within 24 bars of the extreme.

**Consolidation range (B, C).** The last 8 bars, starting at or after the extreme bar, must form a box with
width <= 0.6 x impulse, width >= 0.5 x pre-impulse ATR, |close_end - close_start| <= 0.5 x width, and the box
must sit in the terminal 61.8% of the impulse. Range high = highest high, range low = lowest low of those
8 bars; both are frozen. A touch = a bar entering the 20%-of-width zone at a boundary (consecutive bars count
once). The structure expires after 288 bars (3 days).

**Ping-pong (playbook A).** Long when a bar's low enters the lower 20% zone and the bar closes back above the
range low but not above the midpoint (a rejection close = the Version-A proxy for order-flow confirmation);
short is the mirror. Stop = boundary -/+ 0.5 ATR14. Target = 0.9 x width toward the opposite boundary.
A new signal on the same side needs a close >= 30% of width away first. Ping-pong stops when a valid breakout occurs.

**Breakout / pullback (playbook B1, D, E).** Breakout = M15 close beyond a boundary by >= 0.25 ATR. Pullback =
within 16 bars a bar reaches the boundary +/- 0.25 ATR and closes on the breakout side; entry after that bar.
A close back inside the range by > 0.25 ATR is a failed breakout (structure returns to RANGE). Stop =
beyond min/max(pullback extreme, boundary) by 0.5 ATR. Target = impulse origin for a counter-impulse break,
1 x width measured move for a continuation break. B2 = the same breakout entered at the breakout close.

**Weekly VAH/VAL (F).** Week = Sunday 21:00 UTC to Sunday 21:00 UTC. Bins of 0.025% of price (0.10 USD floor).
Volume of every bar spread uniformly over the bins it touches. 70% value area expanded two bins at a time
from the POC toward the heavier side. Volume source: Dukascopy traded volume on M1 (primary), XM tick volume
and TPO count (sensitivity). The **previous completed week's** levels are used for the whole current week;
the developing current-week VA is recorded as a sensitivity variant. No look-ahead anywhere: every decision
at bar i uses bars <= i, and fills happen on the M1 bar after the signal bar closes.

**Management.** One position at a time, max hold 72 h, 1% risk per trade.

## 3. Data used

| Item | Value |
|---|---|
| M1 bars (Dukascopy bid, UTC) | {D['data']['m1_bars']:,} from {D['data']['start']} to {D['data']['end']} |
| M15 bars | {D['data']['m15_bars']:,} in {D['data']['months']} months (July 2024 missing: Dukascopy returned HTTP 429 on every attempt) |
| Volume | Dukascopy traded volume = REAL volume from one ECN venue. NOT COMEX futures volume. NOT footprint data. |
| Tick volume | XM MT5 tick volume, M15, from 18 Jul 2022 (used only for the VA sensitivity) |
| Spread | XM GOLD per-M15-bar spread, converted from server time (Europe/Athens); {D['data']['spread_filled_share']*100:.1f}% of bars filled with the monthly median (mostly before Jul 2022, at 0.25 USD) |
| Sessions | DST-aware from London / New York / Tokyo local clocks |
| News | No calendar file available offline. Proxy: weekday 08:30 ET and 10:00 ET slots, FOMC 14:00 ET on published decision days, plus ex-post "shock bar" (M15 range > 3 ATR) for loss labelling only |
| Split | DEV Sep 2021 - Dec 2023, VAL Jan 2024 - Mar 2025, OOS Apr 2025 - Sep 2026 (fixed before any result) |

**Version A vs Version B.** Only Version A (price + market profile + available volume) could be built.
Version B needs bid/ask footprint or COMEX order-flow data, which the dataset does not contain. Tick volume
and Dukascopy volume were not used as a stand-in for footprint confirmation; where a volume proxy is used
(loss label "bad_orderflow_proxy", filter "weak_orderflow_proxy", breakout confirmation "volume") it is labelled as a proxy.

## 4. Gold market assumptions

* XM GOLD contract: 100 oz per lot, 0.01 lot = 1 oz, digits 2. Swap long -0.8684 / short +0.1979 USD per oz per night, Wednesday x3.
* Median M15 ATR14 rose from {F['atr_median_by_year']['2021']:.2f} USD (2021) to {F['atr_median_by_year']['2026']:.2f} USD (2026) while the spread stayed at 0.25-0.40 USD,
  so the spread as a share of the median ping-pong stop fell from {F['spread_r_median_by_year']['2021']*100:.0f}% to {F['spread_r_median_by_year']['2026']*100:.0f}%.
  Every year-by-year comparison must be read against this regime change.
* Weekend gaps are real: the worst baseline trade lost {F['worst_r']:.1f}R (long into a Sunday open); {F['n_below_minus2']} trades lost more than 2R, together {F['sum_below_minus2']:.0f}R.
* Sunday 22:00/23:00 UTC open and the CME maintenance hour produce off-hours bars that carry wide spreads; these are in the data as delivered.

## 5. Baseline results (original framework, pre-registered parameters)

Structures: {S['impulses_detected']:,} impulses detected, {S['ranges_confirmed']:,} ranges confirmed (about {S['ranges_per_month']} per month),
{S['abandoned_retrace']} abandoned because price retraced more than 61.8% before a range formed. Median impulse
{S['imp_size_atr_q10_50_90'][1]} pre-impulse ATR ({S['imp_size_atr_q10_50_90'][0]}-{S['imp_size_atr_q10_50_90'][2]} for the 10th-90th percentile) over {S['imp_bars_q10_50_90'][1]:.0f} bars;
median range width {S['width_atr_q10_50_90'][1]} ATR; median range life {S['range_life_bars_q10_50_90'][1]:.0f} bars (about 6 h). Outcomes of confirmed ranges: {S['outcomes']}.
{S['failed_bo_per_range']} failed breakouts per range; {S['touches_hi_mean']} / {S['touches_lo_mean']} touches of the high / low.

Signals proposed: {D['signals']}. With one position at a time the taken trades are below.

**Combined A + B1 (one position across both playbooks), realistic costs:**

{md(comb[["period","n","win_rate","expectancy","pf","total_r","max_dd_r","max_loss_streak","ci_lo","ci_hi"]])}

The holding-time distribution is the first structural finding: median {A.median_hold_h:.1f} h, {F['hold_le_4h_share']*100:.0f}% of trades
closed within 4 h and {F['hold_ge_24h_share']*100:.1f}% held 24 h or more, against the source's 4 h to 3 days. The objective 15-minute
impulse-and-box definition finds intraday structures ({S['range_life_bars_q10_50_90'][1]:.0f}-bar median life), not multi-day swings.
Longer confirmation windows (12-24 bars) were tested in section 10 and are worse.

## 6. Ping-pong results (playbook A)

Realistic execution:

{ptable("A_pingpong", "real")}

Ideal execution:

{ptable("A_pingpong", "ideal")}

Median planned reward/risk {F['rr_median']:.2f}; median stop {F['risk_atr_median']:.2f} ATR. Win rate {A.win_rate*100:.1f}% against the 50-60% the source expects.
MFE {A.mfe_r:.2f}R and MAE {A.mae_r:.2f}R on average: the typical trade goes as far against as for.

By session (real):

{md(sess["A_pingpong"])}

By structure and side (real):

{md(stype_side["A_pingpong"])}

By year (real):

{md(byyear["A_pingpong"])}

Behaviour: ping-pong is a high-frequency, short-hold, low-R:R playbook here. Its losses are dominated by the
impulse resuming through the range (section 8), and its sign by session: only the London/New York overlap is
close to flat.

## 7. Breakout / pullback results (playbook B1, plus B2)

B1 realistic:

{ptable("B1_pullback", "real")}

B1 ideal:

{ptable("B1_pullback", "ideal")}

B2 (entry at the breakout close) realistic:

{ptable("B2_immediate", "real")}

B2 ideal:

{ptable("B2_immediate", "ideal")}

By session (B1 real):

{md(sess["B1_pullback"])}

By session (B2 real):

{md(sess["B2_immediate"])}

By structure and side (B1 real):

{md(stype_side["B1_pullback"])}

Behaviour: the pullback playbook has the lowest win rate ({B1.win_rate*100:.1f}%) and the highest planned R:R
({B1.avg_rr:.1f}) because counter-impulse breaks target the impulse origin. Waiting for the pullback did not
beat entering at the breakout close (B2 {B2.expectancy:+.3f}R vs B1 {B1.expectancy:+.3f}R real). Breakout losses are false
breakouts: price closes back inside the range within 8 bars.

## 8. Loss taxonomy

Every losing trade carries all matching labels; the primary category is the first match in a fixed
priority order (news/shock first, then false breakout, trend continuation, ...). Definitions are in
`results/baseline/label_rules.json`. "trades_flagged" counts winners and losers carrying the label,
"losses" the losing trades whose primary category it is.

Ping-pong (A, real):

{tax_md(tax_A)}

Breakout + pullback (B1, real):

{tax_md(tax_B1)}

Breakout at close (B2, real):

{tax_md(tax_B2)}

Reading: for ping-pong the single largest bucket is **trend continuation against the counter-trend side**
(short in a P / long in a B, stopped as the impulse resumed), then **news/shock bars** and **poor VAH/VAL
location**. For both breakout playbooks the bucket is **false breakout**. "Stop too tight" (a stop twice as far
would have reached the target) is a small bucket, which matters for section 10: wider stops help through the
cost ratio, not through avoiding wick-outs. "Bad footprint confirmation" cannot be evaluated (no footprint data);
the volume proxy row is labelled as such.

## 9. No-trade conditions

Each filter removes the flagged signals; before/after metrics per period. "survives" = expectancy AND profit
factor both improve in DEV, in VAL and in OOS (the retention rule was fixed before running). Note that every
"after" column is still negative.

Ping-pong (A):

{surv(filt_A)}

Breakout + pullback (B1):

{surv(filt_B1)}

Breakout at close (B2):

{surv(filt_B2)}

Full per-period tables: `results/deliverables/12_no_trade_filters_*.csv`. What the data supports as NO-TRADE:

* **Impulse larger than 15 pre-impulse ATR** (exhausted move): removed trades average -0.40 to -0.54R; survives all three periods in every playbook.
* **Spread above 15% of the stop distance** (cost gate): survives for A and B2; removed trades average -0.36 / -0.59R.
* **Off-hours or volume below half the 20-bar average** (low liquidity): survives for B1, DEV+VAL for B2.
* **Asia session for breakout pullbacks** (win rate {float(sess['B1_pullback'].set_index('group').loc['asia','win_rate'])*100:.0f}%) and the **New York afternoon for ping-pong** ({float(sess['A_pingpong'].set_index('group').loc['newyork','expectancy']):+.2f}R) are the worst sessions in every period.
* Filters that do **not** help: VAH/VAL proximity in any form (section 10), the news-slot proxy, the volatility percentile, range width, mid-range entry, touches count.

## 10. Gold-specific adaptations (one variable at a time)

All tables: DEV / VAL / OOS rows, realistic costs. Full CSVs in `results/deliverables/11_experiment_*.csv`.

**Impulse definition (Part 3A).** Four definitions, none positive anywhere; the percentile and range-expansion
definitions produce fewer, longer trades with the same sign.

{exp_table("impulse_definition")}

**Impulse threshold and window:** see `11_experiment_impulse_k.csv` and `11_experiment_impulse_N.csv` (k 2.5-5.0 and N 4-16 all negative; k = 5 gives VAL -0.01R for ping-pong on 226 trades and DEV -0.29R).

**Experiment 1 - stop methodology.** Monotone: wider stops lose less, never gain. The 0.25-ATR stop is destroyed by
slippage and gaps on stops of a few cents (DEV -1.9R per trade). Win rate reaches 56-60% at 2 ATR, matching the source's
claim, while expectancy stays negative.

{exp_table("stop_pingpong")}

{exp_table("stop_breakout")}

**Experiment 2 - range definition.** Shorter confirmation windows (4 bars) are less bad for ping-pong in every period and
turn B1 positive in OOS only (DEV worse), so they are not robust. Longer windows (12-24 bars, closer to the source's
multi-hour boxes) are worse everywhere.

{exp_table("range_min_bars")}

**Experiment 3 - session filter.** The London/New York overlap is the least bad window for every playbook; ping-pong
in the overlap is positive in VAL (+0.03R) and OOS (+0.07R) on 65 and 91 trades, negative in DEV (-0.22R).

{exp_table("session_filter")}

**Experiment 4 - volatility filter.** No band improves all three periods.

{exp_table("volatility_filter")}

**Experiment 5 - breakout confirmation.** Requiring both a large bar (>= 1.5 ATR) and volume (>= 1.5x) on the breakout
raises the win rate of B2 to 39-52% and makes VAL/OOS positive (+0.09 / +0.06R) with DEV still negative (-0.20R).
Penetration of 1.0 ATR has the same profile. For B1 no confirmation variant is positive anywhere.

{exp_table("breakout_confirmation")}

{exp_table("breakout_penetration")}

**Pullback depth / window, ping-pong target and zone, max hold:** `11_experiment_pullback_depth.csv`, `..._pullback_window.csv`,
`..._target_pingpong.csv`, `..._zone_pingpong.csv`, `..._max_hold.csv`. None changes the sign.

**VAH/VAL proximity and volume source.** Requiring the traded boundary to be within 1 or 2 ATR of the previous week's
VAH or VAL makes results worse for every volume source; the developing current-week VA is the least bad variant and still
negative. Level differences between sources are small (Dukascopy vs tick VAH: {float(vad.iloc[0].median_abs_diff_usd):.2f} USD median), so the volume
source is not the reason.

{md(va[va.period != "ALL"][["playbook","variant","period","n","expectancy","pf"]])}

{md(vad, "{:.2f}")}

**Touch count (ping-pong):** `11_experiment_max_touches.csv`; fewer prior touches is marginally better, not a sign change.

## 11. Robustness tests

**Parameter grids** (`11_robustness_grid_*.csv`): impulse k x confirmation bars and stop x zone for A; impulse k x bars and
stop x pullback depth for B1. No cell is positive in DEV. The only positive cells are B1 with a 4-bar window in OOS
(+0.06 to +0.12R) and ping-pong with a 2-ATR stop in VAL (+0.002R). The least-bad region is broad and monotone
(wider stops, wider zones, shorter windows), which is the opposite of a knife-edge, but it is a region of smaller losses.

**Staged combination** (pre-specified, one change per stage, OOS read once at the end; `13_staged_adaptations.csv`):

Ping-pong:

{stage_table("A_pingpong")}

Breakout + pullback:

{stage_table("B1_pullback")}

Breakout at close:

{stage_table("B2_immediate")}

Year-by-year expectancy of each stage (real):

{yearly_pivot("A_pingpong")}

{yearly_pivot("B1_pullback")}

{yearly_pivot("B2_immediate")}

The best stage (B2, stop 1.5 ATR + confirmed breakout + 0.5 ATR penetration) is -0.07R in DEV, +0.06R in VAL and +0.08R in
OOS; every confidence interval contains zero, and the year table shows the sign comes from 2025 (+0.26R) with 2021, 2023,
2024 and 2026 negative. That is a regime result, not a robust edge.

## 12. Walk-forward results

For each test year the candidate with the best expectancy on all earlier years (>= 100 trades) is chosen and applied to
that year (`13_walk_forward.csv`). The chosen variant is always the wider stop; it loses less than the baseline in every
test year and is positive in one (ping-pong 2024, +0.02R).

{md(wf)}

## 13. Out-of-sample results (Apr 2025 - Sep 2026, never used for selection)

{md(PT[PT.period == "OOS"][["playbook","cost","n","win_rate","expectancy","pf","total_r","max_dd_r","max_loss_streak","ci_lo","ci_hi"]])}

Baseline OOS: negative under real costs for all three playbooks; B2 ideal is the closest to flat (-0.011R). The staged
adaptations reach +0.06 to +0.08R in OOS for B2 and -0.09 to -0.14R for A and B1 (section 11).

## 14. Transaction-cost sensitivity

Ping-pong:

{md(costs_A[costs_A.period == "ALL"][["variant","n","expectancy","pf","total_r","spread_r"]])}

Breakout + pullback:

{md(costs_B1[costs_B1.period == "ALL"][["variant","n","expectancy","pf","total_r","spread_r"]])}

The spread alone costs about 0.08-0.09R per trade, slippage 0.05R, swap 0.02R, a 5-minute delay another 0.05R for ping-pong.
Doubling the spread doubles the damage; halving it does not restore the sign. An ECN commission of 7 USD per lot adds 0.02R.

## 15. Maximum drawdown

Realistic execution, fixed 1R per trade: A {A.max_dd_r:.0f}R, B1 {B1.max_dd_r:.0f}R, B2 {B2.max_dd_r:.0f}R, combined A+B1 {float(comb.set_index('period').loc['ALL','max_dd_r']):.0f}R.
Compounding at 1% risk from 10,000 USD the equity ends at {A.end_equity_1pct*100:.0f}% (A), {B1.end_equity_1pct*100:.0f}% (B1), {B2.end_equity_1pct*100:.0f}% (B2) of the start,
with maximum drawdowns of {A.max_dd_pct_1pct:.0f}%, {B1.max_dd_pct_1pct:.0f}% and {B2.max_dd_pct_1pct:.0f}%. Even ideal execution breaches the source's 20% drawdown limit
({Ai.max_dd_pct_1pct:.0f}%, {B1i.max_dd_pct_1pct:.0f}%, {B2i.max_dd_pct_1pct:.0f}%). Equity and drawdown curves: `06_07_equity_drawdown_*.csv` and the HTML report.

## 16. Losing streak analysis

Maximum consecutive losses: A {A.max_loss_streak:.0f}, B1 {B1.max_loss_streak:.0f}, B2 {B2.max_loss_streak:.0f}. The source calls 10-20 normal; the observed streaks are
inside that band, so the streaks are not the diagnostic. The diagnostic is the ratio: at a 36% win rate a planned 1.4 R:R needs
a 42% win rate to break even before costs. Wider stops raise the win rate to 50-60% and cut the streaks to 6-9 but lower the
average win, and the product stays negative.

## 17. Failure examples (ping-pong, realistic)

Worst losses:

{ex_md(D['examples_A']['worst_losses'])}

Randomly drawn losses:

{ex_md(D['examples_A']['typical_losses'])}

Breakout + pullback, worst losses:

{ex_md(D['examples_B1']['worst_losses'])}

## 18. Successful examples

Ping-pong, best trades:

{ex_md(D['examples_A']['best_wins'])}

Ping-pong, randomly drawn wins:

{ex_md(D['examples_A']['typical_wins'])}

Breakout + pullback, best trades:

{ex_md(D['examples_B1']['best_wins'])}

The best trades are counter-impulse breakouts that reached the impulse origin (3-9R) and ping-pong entries just after a
failed breakout. They are rare: the 99th percentile trade is about +3R.

## 19. Limitations

* The discretionary parts (what "well-defined range", "decisive break", "confirmation" mean) were replaced by one objective
  rule set. A different but equally defensible rule set could behave differently; the sensitivity grids cover the
  neighbourhood of the chosen rules, not every reading of the method.
* No footprint or COMEX order-flow data (Version B untested). The order-flow confirmation step could be the source of the
  method's edge; that cannot be tested here, and the Dukascopy volume proxy carried no information.
* News: proxy slots, not an actual calendar. July 2024 missing. Spread before July 2022 is a constant estimate.
* Bar-path execution: the M1 path is used for stops and targets with a stop-first rule; ticks would place some fills differently.
* The holding-time mismatch (hours vs days) means the test covers the 15-minute structures the rules find, not the
  multi-day swings in the source's examples; longer confirmation windows were tested and were worse, but a daily-scale
  version of the framework (H1/H4 impulses) was outside the brief and remains untested.
* Multiple comparisons: about 180 variants were run. The pre-registered retention rule and the untouched OOS period limit,
  but do not remove, selection effects; the staged results in section 11 should be read with that in mind.

## 20. Final conclusion

Under what measurable conditions does the framework work on XAUUSD, and when should it not trade?

* **It does not show positive expectancy in any period under the original rules**, with costs ({A.expectancy:+.2f} / {B1.expectancy:+.2f} / {B2.expectancy:+.2f}R)
  or without ({Ai.expectancy:+.2f} / {B1i.expectancy:+.2f} / {B2i.expectancy:+.2f}R). The entry logic is roughly a coin flip at the planned geometry; costs decide the sign.
* **Least-bad conditions, consistent across DEV, VAL and OOS:** stops of 1.5-2 ATR (never tighter than 1 ATR), the London/New York
  overlap, impulses no larger than 15 pre-impulse ATR, spread below 15% of the stop, and, for breakouts, a confirmation bar with
  range >= 1.5 ATR and volume >= 1.5x average entered at the close. These reduce the loss from about -0.22R to about -0.07R (DEV)
  and to +0.06/+0.08R in VAL/OOS for B2 only; the positive years are 2025 for every playbook.
* **No-trade conditions supported by the data:** impulse > 15 ATR; stop < 1 ATR or spread > 15% of the stop; off-hours and
  low-volume bars; Asia session for breakout pullbacks; New York afternoon for ping-pong; a range confirmed over 12 or more bars.
* **Conditions that did not matter:** alignment with the weekly VAH/VAL (any source, any tolerance), the news-slot proxy,
  volatility percentile, range width, touch count, pullback depth, target fraction.
* **Verdict:** the evidence does not support a Gold Strategy Specification. The framework's measurable part is not profitable on
  XAUUSD over 2021-2026; the unmeasurable part (footprint/order-flow confirmation) is where any edge would have to live, and it
  needs a different dataset to test.

Files: `results/deliverables/` (69 files: rule spec, dataset pointer, all signals and structures, trade-by-trade CSVs for each
playbook and cost model, loss classification and taxonomy, equity/drawdown, monthly, session, P/B, filters, every experiment,
grids, walk-forward, staged adaptations, OOS results). Code: `pbd/` (data, profile, structure, engine, analysis) and the run scripts.
"""

with open(os.path.join(ROOT, "FINAL_REPORT.md"), "w", encoding="utf-8") as f:
    f.write(txt)
print("FINAL_REPORT.md written,", len(txt), "chars")
