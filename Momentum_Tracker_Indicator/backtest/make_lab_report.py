"""Builds filter_lab_report.html from results/lab/lab.json, ab_table.csv, cost_gate_by_tf.csv and narrative_lab.json."""
import html, json, math, os
import pandas as pd

L = json.load(open("results/lab/lab.json"))
AB = pd.read_csv("results/lab/ab_table.csv")
COST = pd.read_csv("results/lab/cost_gate_by_tf.csv")
N = json.load(open("results/lab/narrative_lab.json")) if os.path.exists("results/lab/narrative_lab.json") else {}

def esc(x): return html.escape(str(x))
def money(x, d=0):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return ("-$" if x < 0 else "$") + f"{abs(x):,.{d}f}"
def num(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def cls(x): return "neg" if (x or 0) < 0 else "pos"
def para(k):
    v = N.get(k, "")
    if isinstance(v, list): return "".join(f"<p>{x}</p>" for x in v)
    return f"<p>{v}</p>" if v else ""
def bullets(k):
    v = N.get(k, [])
    return "<ul>" + "".join(f"<li>{x}</li>" for x in v) + "</ul>" if v else ""
def section(title, body, sub=None, id_=None):
    return f"<section id='{id_ or ''}'><h2>{esc(title)}</h2>" + (f"<p class='sub'>{sub}</p>" if sub else "") + body + "</section>"
def table(cols, rows, caption=None):
    out = ["<div class='scroll'><table>"]
    if caption: out.append(f"<caption>{esc(caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th class='{'l' if i == 0 else ''}'>{esc(c)}</th>" for i, c in enumerate(cols)) + "</tr></thead><tbody>")
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            if isinstance(v, tuple):
                text, klass = esc(v[0]), v[1]
            else:
                text, klass = esc(v), ""
            if i == 0:
                klass = ("l " + klass).strip()
            cells.append(f"<td class='{klass}'>{text}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)
def m(x, d=0): return (money(x, d), cls(x))

# ---------------- evidence tables
ba = L["before_after"]
def ba_table():
    keys = [("trades", "Trades", lambda v: f"{v:,}"), ("win_rate", "Win rate", lambda v: f"{v*100:.0f}%"), ("gross_profit", "Gross profit", money), ("gross_loss", "Gross loss", money),
            ("net", "Net profit", money), ("spread_cost", "Spread cost", money), ("gross_before_costs", "Gross before costs", money), ("pf", "Profit factor", num),
            ("expectancy", "Expectancy / trade", lambda v: money(v, 2)), ("max_dd", "Max drawdown", money), ("avg_win", "Avg winner", lambda v: money(v, 2)),
            ("avg_loss", "Avg loser", lambda v: money(v, 2)), ("max_consec_losses", "Consecutive losses", str), ("avg_r", "Avg R", lambda v: num(v, 3))]
    rows = []
    for k, lab, f in keys:
        r = [lab]
        for per in ("DEV", "VAL", "OOS", "ALL"):
            b, c = ba[per]["baseline"][k], ba[per]["combined"][k]
            r.append((f(b), cls(b) if k in ("net", "expectancy", "gross_before_costs", "avg_r") else ""))
            r.append((f(c), cls(c) if k in ("net", "expectancy", "gross_before_costs", "avg_r") else ""))
        rows.append(r)
    return table(["Metric", "DEV base", "DEV filtered", "VAL base", "VAL filtered", "OOS base", "OOS filtered", "ALL base", "ALL filtered"], rows,
                 "DEV = Sep 2021 to Dec 2023 (selection), VAL = 2024 (selection), OOS = Jan 2025 to Sep 2026 (never used for selection). Dollars at 0.02 lot.")

cost_rows = [[r.tf, r.year, f"{r.signals:,}", money(r.median_stop, 2), f"{r.median_cost_over_reward*100:.1f}%", f"{r.share_cost_over_10pct*100:.0f}%", f"{r.share_cost_over_5pct*100:.0f}%"] for r in COST.itertuples()]
cost_tbl = table(["TF", "Year", "Signals", "Median stop", "Median spread / target", "Signals over 10%", "Signals over 5%"], cost_rows,
                 "Spread divided by the 1:2 target distance at the signal close. A 40%-win system with a 1:2 target has a gross margin of about 20% of the target; a cost ratio above 10% takes half of it.")

tag_rows = [[t["tag"], t["rule"], f"{t['trades']:,}", m(t["gross_loss"]), f"{t['pct_total_loss']:.0f}%", m(t["avg_loss"], 2)] for t in L["loss_tags"]]
tag_rows.append(["OTHER (no tag)", "", f"{L['loss_tags_other']['trades']:,}", m(L["loss_tags_other"]["gross_loss"]), "", ""])
tag_tbl = table(["Loss tag", "Rule", "Losing trades", "Gross loss", "% of total loss", "Avg loss"], tag_rows, L["loss_tags_note"])

re_rows = [[k.replace("_", " "), f"{v['trades']:,}", m(v["net"]), m(v["exp"], 2), f"{v['win']*100:.0f}%"] for k, v in L["reentry_direction"].items()]
re_tbl = table(["Entry context", "Trades", "Net", "Expectancy", "Win rate"], re_rows, "Baseline trades grouped by what happened just before them.")

mm = L["mfe_mae"]
def qrow(lbl, d): return [lbl] + [num(d[k]) for k in ("0.25", "0.5", "0.75", "0.9")]
mfe_tbl = table(["Distribution (in R)", "p25", "p50", "p75", "p90"], [qrow("Winners: worst drawdown before winning (MAE)", mm["winners_mae_r"]), qrow("Winners: best point reached (MFE)", mm["winners_mfe_r"]),
                                                                    qrow("Losers: best point reached (MFE)", mm["losers_mfe_r"]), qrow("Losers: worst point (MAE)", mm["losers_mae_r"])],
                f"{mm['winners_share_mae_below_0_5']*100:.0f}% of winners never went more than 0.5R against; {mm['losers_share_mfe_above_0_5']*100:.0f}% of losers were up 0.5R or more first, {mm['losers_share_mfe_above_1']*100:.0f}% were up 1R or more.")
exit_rows = [[k, f"{v['n']:,}", num(v["mfe_r_median"]), num(v["mae_r_median"]), m(v["pnl"])] for k, v in sorted(mm["by_exit"].items(), key=lambda kv: kv[1]["pnl"])]
exit_tbl = table(["Exit type", "Trades", "Median MFE (R)", "Median MAE (R)", "Net"], exit_rows, "Baseline exits.")

prot_rows = [[f"+{p['reached_r']}R", f"{p['trades']:,}", f"{p['pct_of_all']}%", f"{p['ended_loser']:,} ({p['ended_loser_pct']}%)", f"{p['ended_at_or_below_be']:,}", f"{p['reached_tp']:,}", num(p["avg_r_after"]), m(p["net"])] for p in L["profit_protection"]]
prot_tbl = table(["Reached", "Trades", "% of all", "Ended as losers", "Ended at or below BE", "Reached TP", "Avg R at exit", "Net"], prot_rows, "Of the trades that reached each open-profit level, how they finished.")

dur_rows = [[d["bucket"] + " min", f"{d['trades']:,}", m(d["net"]), m(d["exp"], 2), f"{d['win']*100:.0f}%"] for d in L["duration"]]
dur_tbl = table(["Duration", "Trades", "Net", "Expectancy", "Win rate"], dur_rows)
tx_rows = [[f"{t['after_min']} min", f"< {t['below_r']}R", f"{t['trades']:,}", m(t["eventual_net"]), m(t["eventual_exp"], 2), f"{t['eventual_win']*100:.0f}%", m(t["others_exp"], 2), m(t["pnl_if_closed_then"])] for t in L["time_exit_derivation"]]
tx_tbl = table(["Still open after", "Open profit", "Trades", "Eventual net", "Eventual expectancy", "Eventual win rate", "Expectancy of the others", "P&L if closed at that point"], tx_rows,
               "Derivation of a time exit: trades still open after X minutes with less than Y R of open profit, and what they went on to do.")

htf_rows = [[h["htf"], h["period"], "aligned" if h["aligned"] else "against", f"{h['trades']:,}", m(h["exp"], 2), m(h["net"]), num(h["pf"])] for h in L["htf"]]
htf_tbl = table(["Higher timeframe", "Period", "Signal vs HTF", "Trades", "Expectancy", "Net", "PF"], htf_rows, "The same signal split by whether the higher timeframe agreed.")

hs = L["hours"]; hsa = L["hours_sign_agreement"]
hour_rows = [[f"{h['hour']:02d}:00", h["DEV_n"], m(h["DEV_exp"], 2), h["VAL_n"], m(h["VAL_exp"], 2), h["OOS_n"], m(h["OOS_exp"], 2)] for h in hs]
hour_tbl = table(["Hour (server)", "DEV n", "DEV exp", "VAL n", "VAL exp", "OOS n", "OOS exp"], hour_rows,
                 f"Sign of the hourly expectancy agrees DEV vs VAL in {hsa['dev_val']*100:.0f}% of hours (correlation {hsa['corr_dev_val']}), VAL vs OOS in {hsa['val_oos']*100:.0f}% (correlation {hsa['corr_val_oos']}).")

sf_rows = [[f["feature"], f"{f['DEV_with_n']:,}", m(f["DEV_lift"], 2), f"{f['VAL_with_n']:,}", m(f["VAL_lift"], 2), f"{f['OOS_with_n']:,}", m(f["OOS_lift"], 2), "kept" if f["kept"] else "dropped"] for f in L["score_features"]]
sf_tbl = table(["Feature", "DEV n with", "DEV lift", "VAL n with", "VAL lift", "OOS n with", "OOS lift", "Decision"], sf_rows,
               "Lift = expectancy with the feature minus expectancy without it. A feature is kept only if its lift is positive in DEV and in VAL with at least 100 trades. Kept: " + (", ".join(L["score_kept"]) or "none") + ".")

# ---------------- A/B table
AB["retain_txt"] = AB.apply(lambda r: "retained" if r.retain else ("OOS only" if r.pass_OOS and not r.retain else "rejected"), axis=1)
ab_rows = []
for r in AB.sort_values(["group", "name"]).itertuples():
    ab_rows.append([r.name, r.group, r.rule, f"{int(r.DEV_n):,}", m(r.DEV_net), num(r.DEV_pf), m(r.DEV_exp, 2), f"{int(r.VAL_n):,}", m(r.VAL_net), num(r.VAL_pf), m(r.VAL_exp, 2),
                    f"{int(r.OOS_n):,}", m(r.OOS_net), num(r.OOS_pf), m(r.OOS_exp, 2), f"{int(r.DEV_win_removed)} / {int(r.DEV_loss_removed)}", (r.retain_txt, {"retained": "pos", "rejected": "neg", "OOS only": ""}[r.retain_txt])])
ab_tbl = table(["Test", "Group", "Rule", "DEV n", "DEV net", "PF", "Exp", "VAL n", "VAL net", "PF", "Exp", "OOS n", "OOS net", "PF", "Exp", "DEV winners / losers removed", "Decision"], ab_rows,
               "Every candidate on its own against the baseline. Retained = higher expectancy and profit factor, no worse drawdown, and a larger share of losers than winners removed, in BOTH DEV and VAL. OOS was never used to select.")
n_ret = int(AB.retain.sum()) - (1 if AB[AB.name == "BASELINE"].retain.any() else 0)
n_oos_only = int(((~AB.retain) & AB.pass_OOS).sum())

prog_rows = [[p["step"], p["added"], f"{p['DEV_n']:,}", m(p["DEV_net"]), num(p["DEV_pf"]), f"{p['VAL_n']:,}", m(p["VAL_net"]), num(p["VAL_pf"]), f"{p['OOS_n']:,}", m(p["OOS_net"]), num(p["OOS_pf"])] for p in L["progressive"]]
prog_tbl = table(["Step", "Filter added", "DEV n", "DEV net", "PF", "VAL n", "VAL net", "PF", "OOS n", "OOS net", "PF"], prog_rows, "Retained filters added one at a time (one per group, in validation-expectancy order).")

wf_rows = [[w["window"], ", ".join(w["members"]) or "nothing retained (= baseline)", f"{w['test_n']:,}", m(w["test_net"]), num(w["test_pf"]), m(w["test_exp"], 2), f"{w['base_n']:,}", m(w["base_net"]), num(w["base_pf"])] for w in L["walk_forward"]]
wf_tbl = table(["Window", "Filters selected on the training years", "Test trades", "Test net", "Test PF", "Test expectancy", "Baseline trades", "Baseline net", "Baseline PF"], wf_rows,
               "The selection rule is re-run on each training window with no knowledge of the test year; the selected set is then applied to the test year.")

rob_rows = [[r["variant"]] + [x for per in ("DEV", "VAL", "OOS", "ALL") for x in (f"{r[f'{per}_n']:,}", m(r[f"{per}_net"]), num(r[f"{per}_pf"]))] for r in L["robustness"]]
rob_tbl = table(["Variant of the combined configuration", "DEV n", "net", "PF", "VAL n", "net", "PF", "OOS n", "net", "PF", "ALL n", "net", "PF"], rob_rows)
mc = L["monte_carlo"]
mc_txt = f"<p>Trade-order Monte Carlo on the combined configuration ({mc['trades']:,} trades, net {money(mc['net'])} at 0.02 lot): maximum drawdown 5th / 50th / 95th percentile {money(mc['dd_p5'])} / {money(mc['dd_p50'])} / {money(mc['dd_p95'])}. Bootstrap probability that a re-sample of these trades ends positive: {mc['bootstrap_p_profit']*100:.0f}%.</p>"

sz_rows = [[s["config"], str(s["risk_pct"]) + ("%" if not isinstance(s["risk_pct"], str) else ""), f"{s['trades']:,}", f"{s['skipped']:,}", money(s["final"]), m(s["ret_pct"], 1), f"{s['max_dd_pct']}%", "yes" if s["ruin"] else "no"] for s in L["sizing"]]
sz_tbl = table(["Trades from", "Risk per trade", "Trades taken", "Skipped by risk rules", "Final equity from $1,000", "Return", "Max DD", "Ruin (< 20%)"], sz_rows,
               "Risk-based sizing replayed on the same trade lists: lot = equity x risk% / (stop x $1 per oz per 0.01 lot), min 0.01, max 0.10; skip if 0.01 lot would risk more than 2% or after a 3% daily loss or 5 losses in a row.")

members = L["combined_members"]; kw = L["combined_kw"]
final_cfg = "<ul>" + "".join(f"<li><strong>{esc(g)}</strong>: {esc(n)}</li>" for g, n in members.items()) + "</ul>" if members else "<p>No filter passed the retention rule in both selection periods.</p>"

ex_b = L["baseline_exits"]; ex_c = L["combined_exits"]
exits_rows = [[k, f"{ex_b.get(k, 0):,}", f"{ex_c.get(k, 0):,}"] for k in sorted(set(ex_b) | set(ex_c), key=lambda k: -ex_b.get(k, 0))]
exits_tbl = table(["Exit type", "Baseline", "Combined"], exits_rows)

page = f"""<title>TWK Filter Lab</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--base:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--good:#0ca30c;--goodtext:#006300;--warn:#fab219;--crit:#d03b3b;--critbg:rgba(208,59,59,.08);--goodbg:rgba(12,163,12,.08)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c;--critbg:rgba(208,59,59,.16);--goodbg:rgba(12,163,12,.16)}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c;--critbg:rgba(208,59,59,.16);--goodbg:rgba(12,163,12,.16)}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:36px 20px 80px}}
h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}}
h2{{font-size:20px;margin:44px 0 6px;letter-spacing:-.01em}} h3{{font-size:16px;margin:26px 0 6px}}
.sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.toc a:focus-visible{{outline:2px solid var(--s1)}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}}
.verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--crit);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page);position:sticky;top:0}}
td.l,th.l{{text-align:left;white-space:normal;min-width:120px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}}
pre{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;overflow-x:auto;font:12.5px/1.5 ui-monospace,Consolas,monospace;max-width:100%}}
code{{font-family:ui-monospace,Consolas,monospace;font-size:.92em;background:var(--surface);border:1px solid var(--ring);padding:0 5px;border-radius:4px}}
.flow{{display:grid;gap:6px;max-width:520px}} .flow div{{background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:8px 12px;font-size:13.5px}} .flow div.gate{{border-left:4px solid var(--s2)}} .flow div.act{{border-left:4px solid var(--s1)}}
.note{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 18px;color:var(--ink2);font-size:13.5px;max-width:85ch}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, TWK Tracker signal, M3</p>
<h1>TWK Filter Lab</h1>
<p class="lede">Why the automated version of the strategy loses, which filters fix which loss, and what survives out of sample. Signal generation is untouched; everything tested sits after it. Generated {esc(L['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{i}. {t}</a>" for i, t in enumerate(["Architecture", "Loss mechanisms", "Evidence", "Filters", "Entry flow", "Exit flow", "Risk model", "A/B results", "Walk-forward", "Robustness", "Recommendation", "Code changes", "Telemetry", "Missing data", "Manual vs bot"], 1))}</div>
<div class="verdict"><p class="k">Bottom line</p>{para('bottom_line')}</div>

{section('1. Current strategy architecture', para('architecture') + "<pre>" + esc(N.get('architecture_pre', '')) + "</pre>", id_='s1')}
{section('2. Exact loss mechanisms', bullets('mechanisms'), 'Ranked by how much of the loss they explain. Evidence for each is in section 3.', 's2')}
{section('3. Evidence', "<h3>3.1 Transaction cost versus the move being traded</h3>" + cost_tbl + para('ev_cost') +
          "<h3>3.2 Loss tags on the baseline losers</h3>" + tag_tbl + para('ev_tags') +
          "<h3>3.3 Re-entry after a loss: same direction versus opposite</h3>" + re_tbl + para('ev_reentry') +
          "<h3>3.4 MFE / MAE</h3>" + mfe_tbl + exit_tbl + para('ev_mfe') +
          "<h3>3.5 Profit protection</h3>" + prot_tbl + para('ev_prot') +
          "<h3>3.6 Duration and a data-derived time exit</h3>" + dur_tbl + tx_tbl + para('ev_time') +
          "<h3>3.7 Higher-timeframe alignment</h3>" + htf_tbl + para('ev_htf') +
          "<h3>3.8 Time of day, stability across periods</h3>" + hour_tbl + para('ev_hours') +
          "<h3>3.9 Entry-score features</h3>" + sf_tbl + para('ev_score'), None, 's3')}
{section('4. Proposed filters', bullets('filters') + "<h3>Rejected filters and why</h3>" + bullets('rejected'), 'Only what the data supports. Each keeps its parameters configurable; none is a fixed threshold.', 's4')}
{section('5. Entry decision flow', "<div class='flow'>" + "".join(f"<div class='{c}'>{t}</div>" for c, t in N.get('entry_flow', [])) + "</div>" + para('entry_flow_note'), None, 's5')}
{section('6. Exit decision flow', "<div class='flow'>" + "".join(f"<div class='{c}'>{t}</div>" for c, t in N.get('exit_flow', [])) + "</div>" + para('exit_flow_note'), None, 's6')}
{section('7. Risk-management model', sz_tbl + bullets('risk_model'), 'Sizing replayed on the same trades. It changes how fast you lose or win, never the sign.', 's7')}
{section('8. Backtest and A/B results', ba_table() + exits_tbl + "<h3>Progressive build</h3>" + prog_tbl + "<h3>Every candidate</h3>" + f"<p>{n_ret} candidates retained by the rule, {n_oos_only} improved only out of sample (regime effects, rejected), {len(AB) - 1 - n_ret - n_oos_only} rejected outright.</p>" + ab_tbl, None, 's8')}
{section('9. Walk-forward results', wf_tbl + para('walk_forward'), None, 's9')}
{section('10. Robustness', rob_tbl + mc_txt + para('robustness'), None, 's10')}
{section('11. Final recommended configuration', final_cfg + para('recommendation'), None, 's11')}
{section('12. Exact code changes required', para('code_intro') + "<pre>" + esc(N.get('code_pre', '')) + "</pre>", 'TWK_MomentumEA.mq5 and TWK_Core.mqh. Inputs first, then where each rule goes.', 's12')}
{section('13. Logging and telemetry', bullets('telemetry'), 'What to log per signal and per trade so the next analysis needs no guesswork.', 's13')}
{section('14. Missing data', bullets('missing'), 'Things this study could not test honestly.', 's14')}
{section('15. Manual trading versus the bot', bullets('manual'), 'What you may be doing by eye that the bot does not. Each line is a testable rule once you answer it.', 's15')}
</div>
"""
open("filter_lab_report.html", "w", encoding="utf-8").write(page)
print("filter_lab_report.html written", len(page))
