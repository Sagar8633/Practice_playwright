"""Builds loss_prevention_report.html from results/protection/protection.json and narrative_protection.json."""
import html, json, math, os
import pandas as pd

P = json.load(open("results/protection/protection.json"))
N = json.load(open("results/protection/narrative_protection.json")) if os.path.exists("results/protection/narrative_protection.json") else {}
REP = pd.DataFrame(P["report"]); ATTR = P["attribution"]; CHOP = P["chop"]; EQ = P["equity"]; CFG = P["cfg"]

def esc(x): return html.escape(str(x))
def money(x, d=0):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return ("-$" if x < 0 else "$") + f"{abs(x):,.{d}f}"
def num(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "n/a"
    return f"{x:.{d}f}"
def cls(x): return "" if x is None else ("neg" if x < 0 else "pos")
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
            text, klass = (esc(v[0]), v[1]) if isinstance(v, tuple) else (esc(v), "")
            if i == 0: klass = ("l " + klass).strip()
            cells.append(f"<td class='{klass}'>{text}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)
def M(x, d=0): return (money(x, d), cls(x))

base = REP[REP.run == "BASELINE"].iloc[0]
# ---- 3. loss prevention report: baseline vs each run (transposed metrics)
METRICS = [("trades", "Trades", lambda v: f"{int(v):,}"), ("gross_before_spread", "Gross P&L before spread", money), ("spread", "Spread paid", money), ("net", "Net P&L", money),
           ("win_rate", "Win rate", lambda v: f"{v*100:.1f}%"), ("avg_loss", "Avg loss", lambda v: money(v, 2)), ("avg_win", "Avg winner", lambda v: money(v, 2)), ("pf", "Profit factor", num),
           ("expectancy", "Expectancy / trade", lambda v: money(v, 2)), ("max_dd", "Max drawdown", money), ("consec_losses", "Max consecutive losses", lambda v: f"{int(v)}"),
           ("rapid_flips", "Rapid-flip trades (<= 5 bars after the opposite)", lambda v: f"{int(v):,}"), ("initial_sl_hits", "Initial-stop hits", lambda v: f"{int(v):,}"),
           ("post_loss_trades", "Entries <= 15 min after a loss", lambda v: f"{int(v):,}"), ("high_vol_trades", "Trades at ATR > 1.5x median", lambda v: f"{int(v):,}"),
           ("profit_to_loss_reversals", "Up >= 0.5R then lost", lambda v: f"{int(v):,}"), ("margin_or_risk_rejections", "Risk-gate rejections", lambda v: f"{int(v):,}")]
def lp_table(run_names, caption):
    cols = ["Metric"] + [n.replace("_", " ") for n in run_names]
    rows = []
    for key, label, f in METRICS:
        r = [label]
        for n in run_names:
            v = REP[REP.run == n].iloc[0].get(key)
            r.append((f(v), cls(v) if key in ("net", "gross_before_spread", "expectancy") else "") if v is not None and not (isinstance(v, float) and math.isnan(v)) else "n/a")
        rows.append(r)
    return table(cols, rows, caption)
levels = {"L1 hard safety": [], "L2 anti-flip": [], "L3 environment": [], "L4 management": [], "stack": [], "risk view": []}
for r in REP.itertuples():
    if r.level in levels: levels[r.level].append(r.run)
lp_tables = "".join(f"<h3>{esc(lv)}</h3>" + lp_table(["BASELINE"] + names, f"Baseline versus each {lv} protection. Fixed 0.02 lot; equity limits track a notional $1,000.") for lv, names in levels.items() if names and lv not in ("stack", "risk view"))
stack_tbl = lp_table(["BASELINE"] + levels["stack"], "The development sequence: each phase added on top of the previous one.")
# per-period for the stack
per_rows = [[r.run.replace("_", " "), r.desc] + [x for per in ("DEV", "VAL", "OOS") for x in (f"{int(getattr(r, per+'_n')):,}", M(getattr(r, per + "_net")), num(getattr(r, per + "_pf")), M(getattr(r, per + "_exp"), 2), money(getattr(r, per + "_dd")))] for r in REP[REP.run.isin(["BASELINE"] + levels["stack"])].itertuples()]
per_tbl = table(["Run", "What", "DEV n", "net", "PF", "exp", "DD", "VAL n", "net", "PF", "exp", "DD", "OOS n", "net", "PF", "exp", "DD"], per_rows, "Development Sep 2021 to 2023, validation 2024, out-of-sample 2025 to Sep 2026. Nothing was tuned on any period; the settings come from the phase-1 and phase-2 evidence tables.")
# ---- 4. attribution
at_rows = [[a["run"].replace("_", " "), f"{a['blocked']:,}", f"{a['would_have_won']:,}", f"{a['would_have_lost']:,}", M(a["loss_prevented"]), M(-a["profit_sacrificed"]), M(a["net_benefit_blocked"]), f"{a['new_trades']:,}", M(a["new_trades_pnl"]), f"{a['common_trades']:,}", M(a["management_delta"]), M(a["total_delta"])] for a in ATTR]
at_tbl = table(["Run", "Blocked", "Would have won", "Would have lost", "Loss prevented", "Profit sacrificed", "Net benefit of blocking", "New trades let in", "Their P&L", "Common trades", "Management delta on common trades", "Total delta vs baseline"], at_rows,
               "Every baseline trade that the protected run did not take is a blocked trade; its baseline P&L is what would have happened. Blocking frees the slot for later signals (new trades). Management changes alter the P&L of the trades both runs took.")
full = next((a for a in ATTR if a["run"] == "STACK_1234"), None)
pr_tbl = table(["Reason tag", "Blocked", "Would have won", "Would have lost", "Loss prevented", "Profit sacrificed", "Net benefit"], [[p["reason"], f"{p['blocked']:,}", f"{p['would_have_won']:,}", f"{p['would_have_lost']:,}", M(p["loss_prevented"]), M(-p["profit_sacrificed"]), M(p["net_benefit"])] for p in full["per_reason"]], "Full stack: which gate blocked what, and whether it was worth it.") if full else ""
# ---- 6. chop
chop_tbl = table(["Chop score at entry", "Baseline trades", "Expectancy", "Win rate", "Starts a 3-loss streak", "DEV exp", "VAL exp", "OOS exp"], [[c["score"], f"{c['trades']:,}", M(c["exp"], 2), f"{c['win']*100:.0f}%", f"{c['starts_3_loss_streak']*100:.0f}%", M(c["DEV_exp"], 2), M(c["VAL_exp"], 2), M(c["OOS_exp"], 2)] for c in CHOP],
                 "Score = recent flip + previous trade lost + two opposite signals in 10 bars + ATR below 0.8x median + price inside the 50-bar range + flat EMA50 + ADX below 20, on the baseline's own trades.")
# ---- 7. equity
eq_rows = [[n.replace("_", " "), money(EQ[n]["final"]), (f"{EQ[n]['ret_pct']:+.1f}%", cls(EQ[n]["ret_pct"])), f"{EQ[n]['max_dd_pct']}%", "yes" if EQ[n]["ruin"] else "no", money(EQ[n].get("min_equity", 0)), EQ[n].get("lots_median", "0.02"), EQ[n].get("lots_max", "0.02")] for n in EQ]
eq_tbl = table(["Run", "Final equity from $1,000", "Return", "Max drawdown", "Ruin (< 20%)", "Lowest equity", "Median lot", "Max lot"], eq_rows, "Fixed 0.02 lot versus 0.5% risk sizing with the elevated-volatility and streak reductions.")
# ---- NO_TRADE distribution for the full stack
cfg_rows = [[n.replace("_", " "), CFG[n]["level"], CFG[n]["desc"], ", ".join(f"{k}={v}" for k, v in CFG[n]["kw"].items())] for n in CFG]
cfg_tbl = table(["Run", "Level", "Rule", "Engine settings"], cfg_rows)

page = f"""<title>TWK Loss Prevention</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b;--warn:#7a5200}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c;--warn:#fab219}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c;--warn:#fab219}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:85ch;padding-left:20px}} li{{margin:6px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--s2);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--s2);margin:0 0 6px;font-weight:700}} .verdict p{{margin:6px 0;font-size:16px}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}} caption{{text-align:left;padding:10px 12px 4px;color:var(--ink2);font-size:12px;caption-side:top}}
th,td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} td.l,th.l{{text-align:left;white-space:normal;min-width:150px}} tbody tr:last-child td{{border-bottom:none}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} pre{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;overflow-x:auto;font:12.5px/1.5 ui-monospace,Consolas,monospace}}
.flow{{display:grid;gap:6px;max-width:560px}} .flow div{{background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:8px 12px;font-size:13.5px}} .flow div.gate{{border-left:4px solid var(--s2)}} .flow div.act{{border-left:4px solid var(--s1)}} .flow div.lvl{{border-left:4px solid var(--goodtext)}}
code{{font-family:ui-monospace,Consolas,monospace;font-size:.92em;background:var(--surface);border:1px solid var(--ring);padding:0 5px;border-radius:4px}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, TWK M3 preset, loss-prevention layer</p>
<h1>TWK Loss Prevention</h1>
<p class="lede">The signal has no edge (phase 2). This page asks the only remaining useful question: with a permission system around it, does it lose less when wrong and keep what it gets when right? Every layer is measured alone and in sequence, with the counterfactual for every blocked trade. Generated {esc(P['generated'])}.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{i}. {t}</a>" for i, t in enumerate(["Bottom line", "Losses and their guards", "Permission system", "Each layer alone", "Losses prevented", "Development sequence", "Chop score", "Equity with risk sizing", "What to enable", "Settings", "Untested and telemetry"], 1))}</div>
<div class="verdict"><p class="k">Bottom line</p>{para('bottom_line')}</div>
{section('1. Losses and their guards', table(["Loss", "Guard", "Measured effect"], N.get('loss_guard_rows', [])), 'Your table, with the measured column filled in from this run.', 's1')}
{section('2. Trade permission system', "<div class='flow'>" + "".join(f"<div class='{c}'>{t}</div>" for c, t in N.get('flow', [])) + "</div>" + para('flow_note'), 'The signal proposes; every gate can answer NO_TRADE with a reason tag that is logged and counted.', 's2')}
{section('3. Each protection alone', lp_tables, 'The Loss Prevention Report format you asked for, one column per protection.', 's3')}
{section('4. Losses prevented', at_tbl + (("<h3>Full stack, by reason</h3>" + pr_tbl) if pr_tbl else "") + para('attribution'), 'For every blocked trade: what it would have done.', 's4')}
{section('5. Development sequence', stack_tbl + per_tbl + para('sequence'), 'Phase 1 risk, Phase 2 anti-flip, Phase 3 environment, Phase 4 management, cumulatively, by period.', 's5')}
{section('6. Chop score', chop_tbl + para('chop'), 'Not optimised: does the score line up with losing sequences on the baseline trades?', 's6')}
{section('7. Equity with risk sizing', eq_tbl + para('equity'), None, 's7')}
{section('8. What to enable', bullets('enable'), 'Three levels: hard safety, loss reduction, experimental.', 's8')}
{section('9. Settings of every run', cfg_tbl, 'Engine parameter names map one to one onto the MQL5 inputs listed in the phase-1 report.', 's9')}
{section('10. Untested, and the telemetry that would test it', bullets('untested'), None, 's10')}
</div>
"""
open("loss_prevention_report.html", "w", encoding="utf-8").write(page)
print("loss_prevention_report.html written", len(page))
