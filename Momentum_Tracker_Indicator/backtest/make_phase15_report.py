"""Builds phase15_report.html from results/phase15/{summary.json, candidates.json, momentum.json, narrative_phase15.json}."""
import html, json, math, os
import pandas as pd

OUT = "results/phase15"
S = json.load(open(f"{OUT}/summary.json")); C = json.load(open(f"{OUT}/candidates.json")); M = json.load(open(f"{OUT}/momentum.json"))
N = json.load(open(f"{OUT}/narrative_phase15.json")) if os.path.exists(f"{OUT}/narrative_phase15.json") else {}

def esc(x): return html.escape(str(x))
def isnan(x): return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
def num(x, d=3): return "n/a" if isnan(x) else f"{x:.{d}f}"
def sgn(x, d=2): return "n/a" if isnan(x) else f"{x:+.{d}f}"
def pct(x, d=0): return "n/a" if isnan(x) else f"{x*100:.{d}f}%"
def cls(x): return "" if isnan(x) else ("neg" if x < 0 else "pos")
def R(x, d=2): return (sgn(x, d), cls(x))
def ci(r): return f"{num(r['ci_lo'], 2)}-{num(r['ci_hi'], 2)}"
def para(k):
    v = N.get(k, "")
    return "".join(f"<p>{x}</p>" for x in v) if isinstance(v, list) else (f"<p>{v}</p>" if v else "")
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

# ---------- SVG charts ----------
def lx(t): return math.log10(1 + t)
def svg_lines(series, xs, xlabels, ylim, yticks, ylabel, title, fmt=lambda v: f"{v:.2f}", W=880, H=300):
    ml, mr, mt, mb = 52, 110, 28, 44; pw, ph = W - ml - mr, H - mt - mb
    x0, x1 = lx(xs[0]), lx(xs[-1]); X = lambda t: ml + (lx(t) - x0) / (x1 - x0) * pw; Y = lambda v: mt + (1 - (v - ylim[0]) / (ylim[1] - ylim[0])) * ph
    o = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='{esc(title)}' style='width:100%;height:auto;max-width:{W}px'>"]
    o.append(f"<text x='{ml}' y='16' class='ct'>{esc(title)}</text>")
    for v in yticks: o.append(f"<line x1='{ml}' x2='{W-mr}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='grid'/><text x='{ml-8}' y='{Y(v)+4:.1f}' class='tk' text-anchor='end'>{fmt(v)}</text>")
    for t, lab in zip(xs, xlabels):
        if lab: o.append(f"<text x='{X(t):.1f}' y='{H-mb+18}' class='tk' text-anchor='middle'>{esc(lab)}</text>")
    o.append(f"<text x='{ml}' y='{H-6}' class='tk'>{esc(ylabel)}; time after 15:30:00, log scale</text>")
    for lab, vals, color, dash in series:
        pts = [(X(t), Y(v)) for t, v in zip(xs, vals) if not isnan(v)]
        dash_attr = "stroke-dasharray='6 4'" if dash else ""; pstr = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
        o.append(f"<polyline points='{pstr}' fill='none' stroke='{color}' stroke-width='2' {dash_attr}/>")
        for (a, b), t, v in zip(pts, [t for t, v in zip(xs, vals) if not isnan(v)], [v for v in vals if not isnan(v)]):
            o.append(f"<circle cx='{a:.1f}' cy='{b:.1f}' r='4' fill='{color}' stroke='var(--surface)' stroke-width='2'><title>{esc(lab)} at {t:g} s: {fmt(v)}</title></circle>")
        o.append(f"<text x='{pts[-1][0]+8:.1f}' y='{pts[-1][1]+4:.1f}' class='lbl' fill='{color}'>{esc(lab)}</text>")
    o.append("</svg>"); return "".join(o)

def svg_bars(cats, vals, dots, ylabel, title, baseline=1.0, W=880, H=300):
    ml, mr, mt, mb = 52, 20, 28, 58; pw, ph = W - ml - mr, H - mt - mb; n = len(cats); ymax = max(max(vals), max(dots)) * 1.1
    Y = lambda v: mt + (1 - v / ymax) * ph; bw = pw / n
    o = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='{esc(title)}' style='width:100%;height:auto;max-width:{W}px'>", f"<text x='{ml}' y='16' class='ct'>{esc(title)}</text>"]
    for v in [1, 2, 3]:
        if v < ymax: o.append(f"<line x1='{ml}' x2='{W-mr}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='grid'/><text x='{ml-8}' y='{Y(v)+4:.1f}' class='tk' text-anchor='end'>{v}x</text>")
    for i, (c, v, d) in enumerate(zip(cats, vals, dots)):
        x = ml + i * bw + bw * 0.18; w = bw * 0.64
        o.append(f"<rect x='{x:.1f}' y='{Y(v):.1f}' width='{w:.1f}' height='{Y(0)-Y(v):.1f}' rx='3' fill='var(--s1)'><title>{esc(c)}: median spread {v:.2f}x normal, 90th percentile {d:.2f}x</title></rect>")
        o.append(f"<circle cx='{x+w/2:.1f}' cy='{Y(d):.1f}' r='4' fill='var(--s2)' stroke='var(--surface)' stroke-width='2'><title>{esc(c)}: 90th percentile {d:.2f}x</title></circle>")
        o.append(f"<text x='{x+w/2:.1f}' y='{H-mb+14}' class='tk' text-anchor='end' transform='rotate(-35 {x+w/2:.1f} {H-mb+14})'>{esc(c)}</text>")
    o.append(f"<line x1='{ml}' x2='{W-mr}' y1='{Y(baseline):.1f}' y2='{Y(baseline):.1f}' stroke='var(--ink2)' stroke-dasharray='4 4'/>")
    o.append(f"<text x='{W-mr}' y='{Y(baseline)-6:.1f}' class='tk' text-anchor='end'>normal spread</text>")
    o.append(f"<text x='{ml}' y='{H-4}' class='tk'>{esc(ylabel)}. Bars: median; dots: 90th percentile.</text></svg>"); return "".join(o)

bc = [r for r in S["band_curve"] if r["group"] == "All"]
chart_spread = svg_bars([r["band"] for r in bc], [r["spread_med_rel"] for r in bc], [r["spread_p90_rel"] for r in bc], "Spread relative to the pre-release normal, by band", "Spread after the release, 95 events, 2025 Thursday/Friday")
nc = S["norm_curve"]; xs = [max(r["t_s"], 0.5) for r in nc]; xl = [("0" if r["t_s"] == 0 else (f"{r['t_s']}s" if r["t_s"] < 60 else f"{r['t_s']//60}m")) if r["t_s"] in (0, 1, 5, 20, 60, 180, 600, 1800) else "" for r in nc]
chart_norm = svg_lines([("below 2x", [r["share_2x"] for r in nc], "var(--s1)", False), ("below 1.5x", [r["share_15x"] for r in nc], "var(--s2)", False), ("below 1.25x", [r["share_125x"] for r in nc], "var(--ink)", True)], xs, xl, (0, 1), [0, .25, .5, .75, 1], "Share of events whose spread has normalised", "Spread normalisation curve (sustained 5 s below the multiple)", fmt=lambda v: f"{v*100:.0f}%")
dc = S["discovery"]; xs2 = [r["t_ms"] / 1000 for r in dc]; xl2 = ["1s", "5s", "30s", "1m", "5m", "15m", "30m"]
chart_disc = svg_lines([("median |move| from 15:30 ref, ATR", [r["abs_disp_med_atr"] for r in dc], "var(--s1)", False), ("share of the 30-min move", [r["share_of_30m_move"] for r in dc], "var(--s2)", True)], xs2, xl2, (0, 1.6), [0, .5, 1, 1.5], "ATR units (blue) and share (orange)", "Price discovery curve", W=880)
chart_sign = svg_lines([("same sign as the 30-min move", [r["same_sign_as_30m"] for r in dc], "var(--ink)", False)], xs2, xl2, (0.4, 1.0), [.5, .75, 1], "Share of events", "Sign agreement with the 30-minute displacement (overlapping, see text)", fmt=lambda v: f"{v*100:.0f}%")

# ---------- tables ----------
es = S["event_stats"]
data_rows = [["Days on disk (2025 Thursday/Friday)", S["days"]], ["Events reconstructed", S["ok"]], ["Excluded", "; ".join(f"{r['day']}: {r['reason']}" for r in S["insufficient"]) or "none"], ["Economic calendar", S["calendar"]], ["Monday to Wednesday", "not downloaded; no curve"],
             ["Normal spread (15:00-15:25 median)", f"${es['normal_spread_usd_med']:.2f} = {es['normal_spread_atr']:.2f} ATR (ATR median ${es['atr_med']:.2f})"], ["Spread on the first tick at or after 15:30:00", f"{es['spread_at_event_rel_med']:.2f}x normal (median)"], ["Spread maximum in the first hour", f"{es['spread_max_rel_med']:.2f}x normal (median)"],
             ["Spread at the 1.5x normalisation tick", f"{es['spread_at_norm_rel_med']:.2f}x normal = {es['spread_at_norm_rel_med']*es['normal_spread_atr']:.2f} ATR"], ["|displacement| at 30 min", f"{es['abs_disp30_atr_med']:.2f} ATR median; max within 30 min {es['max_abs_disp30_med']:.2f} ATR"], ["Out-of-sample 2026", "not read"]]
band_tbl = table(["Band", "Ticks/s", "Spread med", "Spread p90", "Spread max", "Range / ATR", "|return| / ATR", "Max |disp| / ATR", "Retracement", "|tick imbalance|", "Max run", "Realised vol / ATR"],
                 [[r["band"], num(r["ticks_per_s"], 1), f"{r['spread_med_rel']:.2f}x", f"{r['spread_p90_rel']:.2f}x", f"{r['spread_max_rel']:.2f}x", num(r["range_atr"]), num(r["abs_mid_ret_atr"]), num(r["max_disp_atr"]), num(r["retracement"], 2), num(r["imbalance_abs"], 2), num(r["consec"], 0), num(r["rv_atr"])] for r in bc], "Medians across the 95 events; spreads relative to the pre-release normal; max |disp| is cumulative from the 15:30 reference.")
norm_tbl = table(["Group", "Threshold", "Events", "Already below at 15:30:00", "Never within 30 min", "p25", "Median", "p75", "p90"], [[r["group"], f"{r['mult']}x", r["n"], r["already_at_t0"], r["never_within_30min"], f"{num(r['p25_s'],1)} s", f"{num(r['p50_s'],1)} s", f"{num(r['p75_s'],1)} s", f"{num(r['p90_s'],1)} s"] for r in S["normalisation"]], "Time until the rolling 1-s median spread stays below the multiple of normal for 5 seconds.")
disc_tbl = table(["Time after 15:30", "Median |displacement| / ATR", "Share of the 30-min move", "Same sign as the 30-min displacement"], [[xl2[i], num(r["abs_disp_med_atr"]), pct(r["share_of_30m_move"]), pct(r["same_sign_as_30m"])] for i, r in enumerate(dc)])
inf = [r for r in S["information"] if r["horizon_min"] in (5, 15, 30, 60)]
inf_tbl = table(["X (ATR)", "Horizon", "Side", "Events", "Mid: +X before -X", "95% interval", "Executable: +X before -X", "Resolved (exec)"], [[r["X"], f"{r['horizon_min']} min", "long" if r["side"] == 1 else "short", r["n"], num(r["hit_mid"], 2), ci(r), num(r["hit_exec"], 2), pct(r["resolved_exec"])] for r in inf], "From the 1.5x normalisation time. Executable: a long fills at the ask and wins when the bid reaches ask + X (mirror for a short).")
inc_tbl = table(["X (ATR)", "Horizon", "Side", "Windows", "Mid: +X before -X", "95% interval", "Executable: +X before -X"], [[r["X"], f"{r['horizon_min']} min", "long" if r["side"] == 1 else "short", r["n"], num(r["hit_mid"], 2), ci(r), num(r["hit_exec"], 2)] for r in S["information_controls"]], "Same test at 16:30 and 17:15 on the same days (no release).")
st = [r for r in S["states"] if r["horizon_min"] in (15, 30) and r["X"] in (0.5, 1.0)]
names = {"s_disp": "displacement at normalisation (>= 0.1 ATR)", "s_ret5": "5-second return (>= 0.05 ATR)", "s_imb5": "tick imbalance 0-5 s", "s_imb30": "tick imbalance 5-30 s", "s_side": "which side of the quote moved (0-5 s)"}
st_tbl = table(["State (direction)", "X", "Horizon", "Events", "Mid hit", "95% interval", "Executable hit", "Mean MFE", "Mean MAE", "Mean close"], [[names[r["state"]], r["X"], f"{r['horizon_min']} min", r["n"], num(r["hit_mid"], 2), ci(r), num(r["hit_exec"], 2), num(r["mfe"], 2), num(r["mae"], 2), R(r["close"])] for r in st], "Outcomes in the state's direction from the 1.5x normalisation time; MFE/MAE/close on mid in ATR.")
co_tbl = table(["Horizon", "X", "Events", "Up first", "Mid continuation", "95% interval", "Executable continuation", "Mean MFE", "Mean MAE", "Mean close"], [[f"{r['horizon_min']} min", r["X"], r["n"], pct(r["up_first"]), num(r["cont_mid"], 2), ci(r), num(r["cont_exec"], 2), num(r["mfe"], 2), num(r["mae"], 2), R(r["close"])] for r in S["continuation"]], "First clean move = displacement of at least 0.1 ATR at the 1.5x normalisation time (55 of 95 events).")
tb_tbl = table(["Start", "X (ATR)", "Windows", "Reached within 30 min", "Median time", "p75 time"], [[r["start"], r["X"], r["n"], pct(r["reached_30min"]), f"{num(r['t_med_s'],0)} s", f"{num(r['t_p75_s'],0)} s"] for r in C["trackb"]], "Time until |mid move| >= X ATR from the start tick.")
tbr_tbl = table(["Start", "Windows", "30-min range / ATR (median)", "p25", "p75"], [[r["start"], r["n"], num(r["range_30min_med_atr"], 2), num(r["range_p25"], 2), num(r["range_p75"], 2)] for r in C["trackb_range"]])
om = pd.DataFrame(C["oco_matrix"]); starts = ["0 s", "15 s", "30 s", "60 s", "120 s", "t_norm 1.5x", "t_norm 1.25x"]; cells = [(k, T) for k in (0.25, 0.5, 0.75) for T in (0.75, 1.0, 1.5)]
oco_rows = []
for s in starts:
    g = om[om.start == s].set_index(["k", "T"])
    oco_rows.append([s] + [R(float(g.loc[c, "net"])) if c in g.index else "n/a" for c in cells])
oco_tbl = table(["Placed at"] + [f"k={k} T={T}" for k, T in cells], oco_rows, "Net ATR per attempt at one spread, fills at the triggering quote, stop = opposite trigger, 30-min horizon. Standard errors 0.06-0.12.")
oc = pd.DataFrame(C["oco_cost"]).pivot_table(index=["k", "T"], columns="cost", values="net")
cost_tbl = table(["k / T", "Mid to mid", "1x spread", "1.25x", "1.5x", "2x"], [[f"k={k} T={T}"] + [R(float(oc.loc[(k, T), c])) for c in (0.0, 1.0, 1.25, 1.5, 2.0)] for k, T in cells], "OCO placed at the 1.5x normalisation time; the half-spread around the mid scaled by the multiplier.")
occ = pd.DataFrame(C["oco_controls"])
ctrl_tbl = table(["k / T", "Windows", "Mid to mid", "1x spread", "Target rate (1x)", "Stop rate (1x)", "PF (1x)"], [[f"k={k} T={T}", int(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 1.0)].n.iloc[0]), R(float(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 0.0)].net.iloc[0])), R(float(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 1.0)].net.iloc[0])), pct(float(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 1.0)].target.iloc[0])), pct(float(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 1.0)].stop.iloc[0])), num(float(occ[(occ.k == k) & (occ["T"] == T) & (occ.cost == 1.0)].pf.iloc[0]), 2)] for k, T in cells], "Same OCO at 16:30 and 17:15 on the same days.")
sb_tbl = table(["Group", "Target", "Spread", "Attempts", "Range width / ATR (median)", "Target rate", "Stop rate", "Net ATR", "SE", "PF"], [[r["group"], r["target_name"], f"{r['cost']}x", r["n"], num(r["width_med"], 2), pct(r["target"]), pct(r["stop"]), R(r["net"]), num(r["se"], 2), num(r["pf"], 2)] for r in C["shock_breakout"]], "Breakout of the first-minute mid range, placed at max(60 s, normalisation time); stop = the other side of the range.")
mg = pd.DataFrame(M["grid"]); m1 = mg[(mg.cost == 1.0) & (mg.variant == "no stop")].set_index(["start", "hold"]); m0 = mg[(mg.cost == 0.0)].set_index(["start", "hold"]); ms_ = mg[mg.variant == "stop 1 ATR"].set_index(["start", "hold"]); m125 = mg[(mg.cost == 1.5) & (mg.variant == "no stop")].set_index(["start", "hold"])
mstarts = ["15 s", "30 s", "60 s", "90 s", "120 s", "t_norm 1.5x", "t_norm 1.25x"]; holds = (5, 15, 30, 60)
def mrow(df, s, key="net"): return [R(float(df.loc[(s, h), key])) if (s, h) in df.index else "n/a" for h in holds]
mom_tbl = table(["Direction read at"] + [f"hold {h} min: net" for h in holds] + [f"t ({h})" for h in holds], [[s] + mrow(m1, s) + [num(float(m1.loc[(s, h), "t"]), 1) if (s, h) in m1.index else "n/a" for h in holds] for s in mstarts], "Net ATR per trade at one spread, no stop, with t-statistics. Retention rule: |t| >= 2 and both neighbouring delay bands positive at the same hold.")
mom2_tbl = table(["Direction read at"] + [f"mid to mid, {h} min" for h in holds] + [f"1-ATR stop, {h} min" for h in holds] + [f"1.5x spread, {h} min" for h in holds], [[s] + mrow(m0, s) + mrow(ms_, s) + mrow(m125, s) for s in mstarts])
mc = pd.DataFrame(M["controls"])
momc_tbl = table(["Hold", "Windows", "Mid to mid", "1x spread", "t (1x)", "Hit (1x)", "1-ATR stop"], [[f"{h} min", int(mc[(mc.hold == h) & (mc.cost == 1.0) & (mc.variant == "no stop")].n.iloc[0]), R(float(mc[(mc.hold == h) & (mc.cost == 0.0)].net.iloc[0])), R(float(mc[(mc.hold == h) & (mc.cost == 1.0) & (mc.variant == "no stop")].net.iloc[0])), num(float(mc[(mc.hold == h) & (mc.cost == 1.0) & (mc.variant == "no stop")].t.iloc[0]), 1), pct(float(mc[(mc.hold == h) & (mc.cost == 1.0) & (mc.variant == "no stop")].hit.iloc[0])), R(float(mc[(mc.hold == h) & (mc.variant == "stop 1 ATR")].net.iloc[0]))] for h in holds], "Same rule at 16:30 and 17:15: direction = sign of the preceding 60 s, entry 60 s after the window start.")
retained = M["retained"]
ret_txt = "<p><strong>Retained cells: none.</strong></p>" if not retained else "<p><strong>Retained on development (needs VAL/OOS):</strong> " + ", ".join(f"{r['start']} / {r['hold']} min ({r['net']:+.2f} ATR, t {r['t']:.1f})" for r in retained) + "</p>"
acc_tbl = table(["Acceptance criterion", "Result"], N.get("acceptance", []))

toc = ["Classification", "Data", "Tick timeline", "Spread normalisation", "Price discovery", "Information value", "Shock states", "Continuation", "Track B", "OCO after the shock", "Shock-range breakout", "Delayed momentum", "Acceptance", "Controls", "Next"]
page = f"""<title>Post-Release Transition</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e1e0d9;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--goodtext:#006300;--crit:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--goodtext:#0ca30c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1160px;margin:0 auto;padding:36px 20px 80px}} h1{{font-size:clamp(26px,4vw,38px);line-height:1.1;margin:0 0 8px;text-wrap:balance}} .eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:0 0 10px}}
.lede{{color:var(--ink2);max-width:72ch;margin:0 0 18px}} h2{{font-size:20px;margin:44px 0 6px}} h3{{font-size:16px;margin:26px 0 6px}} .sub{{color:var(--ink2);margin:0 0 14px;max-width:85ch}} p{{max-width:80ch}} ul,ol{{max-width:80ch;padding-left:22px}} li{{margin:4px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .toc a{{font-size:12px;padding:4px 10px;border:1px solid var(--ring);border-radius:999px;background:var(--surface);color:var(--ink);text-decoration:none}}
.verdict{{border:1px solid var(--ring);border-left:5px solid var(--crit);background:var(--surface);border-radius:10px;padding:18px 22px;margin:0 0 26px}} .verdict .k{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink2);margin:0}}
.scroll{{overflow-x:auto;border:1px solid var(--ring);border-radius:10px;background:var(--surface);margin:10px 0 18px}} table{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}} caption{{caption-side:bottom;text-align:left;color:var(--ink2);font-size:12px;padding:8px 10px}}
th,td{{padding:6px 9px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}} th{{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2);font-weight:600;background:var(--page)}} th.l,td.l{{text-align:left}}
td.neg{{color:var(--crit);font-weight:600}} td.pos{{color:var(--goodtext);font-weight:600}} .decision{{font-size:22px;font-weight:700;margin:8px 0}}
.chart{{border:1px solid var(--ring);border-radius:10px;background:var(--surface);padding:12px 12px 6px;margin:10px 0 18px}} .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}}
svg .grid{{stroke:var(--grid)}} svg .tk{{font-size:11px;fill:var(--ink2)}} svg .ct{{font-size:13px;font-weight:600;fill:var(--ink)}} svg .lbl{{font-size:11px;font-weight:600}}
</style>
<div class="wrap">
<p class="eyebrow">XAUUSD, phase 15, post-release microstructure transition</p>
<h1>Post-Release Transition</h1>
<p class="lede">After the 15:30 server liquidity shock has passed, is there a measurable and executable transition into directional price discovery? Dukascopy ticks, 95 Thursday/Friday releases of 2025 (development only; 2026 untouched), executable quotes throughout.</p>
<div class="toc">{"".join(f"<a href='#s{i}'>{t}</a>" for i, t in enumerate(toc))}</div>
<div class="verdict" id="s0"><p class="k">Classification</p><p class="decision">{esc(N.get('classification', ''))}</p>{para('classification_text')}</div>
{section('1. Data', table(['Item', 'Value'], data_rows), None, 's1')}
{section('2. Tick timeline in 14 bands', f"<div class='chart'>{chart_spread}</div>" + band_tbl + para('timeline'), 'Every metric the brief listed, per band, median across events.', 's2')}
{section('3. Spread normalisation', f"<div class='chart'>{chart_norm}</div>" + norm_tbl + para('normalisation'), None, 's3')}
{section('4. Price discovery', f"<div class='charts'><div class='chart'>{chart_disc}</div><div class='chart'>{chart_sign}</div></div>" + disc_tbl + para('discovery'), None, 's4')}
{section('5. Information value after normalisation', inf_tbl + inc_tbl + para('information'), 'Unconditional race to +X before -X from the 1.5x normalisation time, both sides, mid (diagnostic) and executable.', 's5')}
{section('6. Shock states as direction', st_tbl + para('states'), None, 's6')}
{section('7. Continuation versus reversal of the first clean move', co_tbl + para('continuation'), None, 's7')}
{section('8. Track B: volatility after normalisation', tb_tbl + tbr_tbl + para('trackb'), None, 's8')}
{section('9. OCO breakout after the shock (development only)', oco_tbl + '<h3>Cost robustness at the normalisation time</h3>' + cost_tbl + '<h3>Controls</h3>' + ctrl_tbl + para('oco'), 'Delay bands 0-120 s and the empirical normalisation times; read for a plateau, not a peak.', 's9')}
{section('10. Shock-range breakout', sb_tbl + f"<p>Pullback candidate: {esc(C['pullback'])}.</p>", None, 's10')}
{section('11. Delayed momentum (development only)', mom_tbl + mom2_tbl + '<h3>Controls</h3>' + momc_tbl + ret_txt + para('momentum'), None, 's11')}
{section('12. Acceptance criteria', acc_tbl, None, 's12')}
{section('13. Controls', para('controls'), None, 's13')}
{section('14. Next step', bullets('next'), None, 's14')}
</div>
"""
open("phase15_report.html", "w", encoding="utf-8").write(page)
print("phase15_report.html written", len(page))
