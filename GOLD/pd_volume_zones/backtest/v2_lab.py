"""
v2_lab.py - controlled V2 experiments against the frozen V1 baseline.

Every experiment is a small set of variants of ONE switch of pdvz_engine (defaults = V1).
Each variant is scored overall, on a chronological Development / Validation / Out-of-sample
split (60/20/20 of the V1 trades), and per year. The selection rule for the combination
test is written down here before any result is seen:

  candidate = a non-V1 variant of E1-E5 whose average NET R per trade beats V1 in BOTH the
              Development and the Validation period, and whose Development trade count is at
              least 40% of V1's (no suspicious reduction). Out-of-sample is never looked at
              for selection. Candidates are ranked by the SMALLER of their two improvements
              (the stability, not the size), at most one per experiment, top 3 kept.
  combination = all pairs and the triple of those candidates, evaluated DEV / VAL / OOS.
  walk-forward = for each test year 2023..2026 the same selection is redone on the years
              before it (per-year metrics of the single-switch runs), and the resulting
              combination is evaluated on that year only.

Outputs: results/v2/variants.csv, results/v2/v2_lab.json, V2_RESEARCH_REPORT.md
"""
import itertools
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import pdvz_engine as E

DATA = "../../../Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_*.csv"
OUT = "results/v2"
os.makedirs(OUT, exist_ok=True)
SESSIONS = ["Asia 00-07 UTC", "London 07-12 UTC", "Overlap 12-16 UTC", "New York 16-21 UTC", "Close 21-24 UTC"]

EXPERIMENTS = {
    "E1 Failed-breakout protection": [
        ("V1", {}),
        ("exit at the 1st close back inside the rectangle (first 3 bars)", dict(fb_exit_closes=1, fb_window=3)),
        ("exit at the 2nd close back inside the rectangle (first 3 bars)", dict(fb_exit_closes=2, fb_window=3)),
        ("exit at the 1st close back inside the rectangle (first 6 bars)", dict(fb_exit_closes=1, fb_window=6)),
        ("re-confirmation: a 2nd consecutive close beyond the edge before entry", dict(confirm_bars=2)),
    ],
    "E2 Minimum stop (cost viability)": [
        ("V1 (no minimum)", {}),
        ("minimum stop 2 USD", dict(min_risk_usd=2.0)),
        ("minimum stop 3 USD", dict(min_risk_usd=3.0)),
        ("minimum stop 4 USD", dict(min_risk_usd=4.0)),
        ("minimum stop 5 USD", dict(min_risk_usd=5.0)),
        ("minimum stop 0.5 x ATR14", dict(min_risk_atr=0.5)),
        ("minimum stop 1.0 x ATR14", dict(min_risk_atr=1.0)),
        ("minimum stop 1.5 x ATR14", dict(min_risk_atr=1.5)),
    ],
    "E3 Target location": [
        ("A: V1 (3R target anywhere)", {}),
        ("B: 3R target must lie beyond the prior-day High (long) / Low (short)", dict(target_rule="beyond_pdhl")),
        ("C: ... beyond it by at least 0.5R", dict(target_rule="beyond_pdhl", target_margin_R=0.5)),
        ("C: ... beyond it by at least 1.0R", dict(target_rule="beyond_pdhl", target_margin_R=1.0)),
    ],
    "E4 Volatility regime": [
        ("V1 (no filter)", {}),
        ("avoid low: ATR14 below its 20th percentile of the last 7 days", dict(vol_filter="avoid_low", vol_low_pct=20)),
        ("avoid low and high: below 20th or above 90th percentile (7 days)", dict(vol_filter="avoid_low_high", vol_low_pct=20, vol_high_pct=90)),
        ("robustness: below 10th percentile", dict(vol_filter="avoid_low", vol_low_pct=10)),
        ("robustness: below 30th percentile", dict(vol_filter="avoid_low", vol_low_pct=30)),
        ("robustness: below 20th percentile of the last 30 days", dict(vol_filter="avoid_low", vol_low_pct=20, vol_window=8640)),
    ],
    "E5 POC tap timing": [
        ("A: tap on the confirmation candle itself only", dict(tap_timing="same_only")),
        ("B: POC touched at least one candle before the confirmation", dict(tap_timing="earlier_only")),
        ("C: either (V1)", {}),
    ],
    "E6 Sessions (information only, not a selection candidate)": [
        ("V1 (all sessions)", {}),
    ] + [(f"exclude {s}", dict(session_filter=set(SESSIONS) - {s})) for s in SESSIONS],
}

_D = None


def _init():
    global _D
    _D = E.prepare(E.load_m1(E.v1_chunk_files()))


def _run(args):
    name, params = args
    p = dict(simulate_skipped=False)
    p.update(params)
    tr, _, info = E.run(_D, p, verbose=False)
    tr = tr[tr.exit_reason.isin(["SL", "TP", "FB"])].reset_index(drop=True)
    return name, tr, info


def run_jobs(jobs):
    """Sequential by default (each run is ~3 s); WORKERS=n in the environment enables a process pool."""
    workers = int(os.environ.get("WORKERS", "1"))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
            yield from ex.map(_run, jobs)
    else:
        if _D is None:
            _init()
        for job in jobs:
            yield _run(job)


def metrics(tr):
    if len(tr) == 0:
        return dict(n=0, wr=np.nan, gross=0.0, net=0.0, avg=np.nan, avg_net=np.nan, pf=np.nan, dd=0.0, dd_net=0.0)
    r = tr.result_R.values
    net = tr.net_R.values
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    cum = np.cumsum(r)
    cumn = np.cumsum(net)
    return dict(n=int(len(r)), wr=float((r > 0).mean()), gross=float(r.sum()), net=float(net.sum()), avg=float(r.mean()),
                avg_net=float(net.mean()), pf=float(gp / gl) if gl > 0 else float("inf"),
                dd=float((np.maximum.accumulate(cum) - cum).max()), dd_net=float((np.maximum.accumulate(cumn) - cumn).max()))


def score(tr, cuts):
    tr = tr.copy()
    tr["period"] = np.where(tr.t_ms < cuts[0], "DEV", np.where(tr.t_ms < cuts[1], "VAL", "OOS"))
    out = dict(all=metrics(tr))
    for per in ("DEV", "VAL", "OOS"):
        out[per] = metrics(tr[tr.period == per])
    out["years"] = {int(y): metrics(g) for y, g in tr.groupby("year")}
    return out, tr


def f(x, spec):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) else ""
    return spec.format(x)


def row_main(label, m, v1=None):
    d = f"{m['avg_net'] - v1['avg_net']:+.3f}" if v1 and m["n"] else ""
    return (f"| {label} | {m['n']} | {f(m['wr'], '{:.1%}')} | {f(m['gross'], '{:+.1f}')} | {f(m['net'], '{:+.1f}')} | "
            f"{f(m['avg'], '{:+.3f}')} | {f(m['avg_net'], '{:+.3f}')} | {f(m['pf'], '{:.2f}')} | {f(m['dd'], '{:.0f}')} | {d} |")


HEAD_MAIN = ("| Variant | Trades | Win rate | Gross R | Net R | Avg R | Avg net R | PF | Max DD (R) | Avg net R vs V1 |\n"
             "|---|---|---|---|---|---|---|---|---|---|")


def row_periods(label, s):
    cells = [label]
    for per in ("DEV", "VAL", "OOS"):
        m = s[per]
        cells.append(f"{m['n']} / {f(m['wr'], '{:.0%}')} / {f(m['net'], '{:+.0f}')} / {f(m['avg_net'], '{:+.3f}')}")
    return "| " + " | ".join(cells) + " |"


HEAD_PER = ("| Variant | Development (n / win / net R / avg net R) | Validation | Out-of-sample |\n|---|---|---|---|")


def row_years(label, s, years):
    cells = [label] + [(f"{s['years'][y]['n']} / {f(s['years'][y]['avg_net'], '{:+.3f}')}" if y in s["years"] else "-") for y in years]
    return "| " + " | ".join(cells) + " |"


def spearman(x, y):
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    if len(x) < 20:
        return np.nan, np.nan, len(x)
    try:
        from scipy.stats import spearmanr
        r, p = spearmanr(x, y)
        return float(r), float(p), len(x)
    except Exception:
        rx = pd.Series(x).rank().values
        ry = pd.Series(y).rank().values
        r = float(np.corrcoef(rx, ry)[0, 1])
        return r, np.nan, len(x)


def main():
    # ---------------------------------------------------------------- runs
    jobs = []
    seen = {}
    for exp, variants in EXPERIMENTS.items():
        for label, params in variants:
            key = json.dumps(params, sort_keys=True, default=list)
            if key not in seen:
                seen[key] = (exp, label)
                jobs.append((key, params))
    print(f"{len(jobs)} distinct runs ...")
    results = {}
    for key, tr, info in run_jobs(jobs):
        results[key] = (tr, info)
        print(f"  done: {seen[key][1][:60]:60s} n={len(tr)}")
    v1_key = json.dumps({}, sort_keys=True)
    v1_tr = results[v1_key][0]
    cuts = (float(np.quantile(v1_tr.t_ms, 0.6)), float(np.quantile(v1_tr.t_ms, 0.8)))
    cut_dates = [str(pd.Timestamp(c, unit="ms").date()) for c in cuts]
    years = sorted(v1_tr.year.unique().tolist())
    scored = {}
    for key, (tr, info) in results.items():
        s, trp = score(tr, cuts)
        s["info"] = dict(blocked=info["blocked"], skipped=info["skipped_signals"])
        scored[key] = s
        results[key] = (trp, info)
    V1 = scored[v1_key]
    assert V1["all"]["n"] > 0
    print("split cut dates:", cut_dates, "V1 per period:", {k: V1[k]["n"] for k in ("DEV", "VAL", "OOS")})

    # ---------------------------------------------------------------- variants table
    rows = []
    for exp, variants in EXPERIMENTS.items():
        for label, params in variants:
            key = json.dumps(params, sort_keys=True, default=list)
            s = scored[key]
            rec = dict(experiment=exp, variant=label, params=key)
            for per in ("all", "DEV", "VAL", "OOS"):
                for k2, v2 in s[per].items():
                    rec[f"{per}_{k2}"] = v2
            for y in years:
                rec[f"y{y}_n"] = s["years"].get(y, {}).get("n", 0)
                rec[f"y{y}_avg_net"] = s["years"].get(y, {}).get("avg_net", np.nan)
            rows.append(rec)
    VT = pd.DataFrame(rows)
    VT.to_csv(f"{OUT}/variants.csv", index=False)

    # ---------------------------------------------------------------- E7 zone quality (V1 trades)
    feats = [("zone_prom_rel", "Volume prominence (HVN rectangles only)"), ("zone_height", "Rectangle height (USD)"),
             ("zone_h_pct_range", "Rectangle height / prior-day range"), ("zone_share", "Volume share of the day"),
             ("poc_pos_in_zone", "POC position inside the rectangle (0 = bottom, 1 = top)"),
             ("nearest_gap_zh", "Distance to the nearest other rectangle (heights)"), ("taps", "Number of touches before entry")]
    e7 = []
    v1p = results[v1_key][0]
    for col, title in feats:
        x = v1p[col].astype(float)
        try:
            terc = pd.qcut(x, 3, labels=["low", "mid", "high"], duplicates="drop")
        except ValueError:
            terc = pd.Series(["all"] * len(x), index=x.index)
        rec = dict(feature=title, col=col)
        for per in ("DEV", "VAL", "OOS"):
            m = (v1p.period == per).values
            r, pval, n = spearman(x.values[m], v1p.result_R.values[m])
            rec[f"{per}_rho"], rec[f"{per}_p"], rec[f"{per}_n"] = r, pval, n
            for lab in ("low", "mid", "high", "all"):
                mm = m & (terc.values == lab)
                if mm.sum():
                    rec[f"{per}_{lab}"] = f"{mm.sum()} / {100 * (v1p.result_R.values[mm] > 0).mean():.0f}% / {v1p.net_R.values[mm].mean():+.3f}"
        e7.append(rec)
    ft = v1p.copy()
    ft["touch"] = np.where(ft.first_touch, "first touch", "repeat")
    e7_touch = ft.groupby(["period", "touch"]).agg(n=("result_R", "size"), wr=("result_R", lambda s: (s > 0).mean()), avg_net=("net_R", "mean")).reset_index()

    # ---------------------------------------------------------------- E6 sessions x year (V1)
    sy = v1p.groupby(["session", "year"]).agg(n=("result_R", "size"), avg_net=("net_R", "mean")).reset_index()
    sp = v1p.groupby(["session", "period"]).agg(n=("result_R", "size"), wr=("result_R", lambda s: (s > 0).mean()), avg_net=("net_R", "mean"), net=("net_R", "sum")).reset_index()

    # ---------------------------------------------------------------- combination candidates (pre-registered rule)
    cands = []
    for exp, variants in EXPERIMENTS.items():
        if exp.startswith("E6"):
            continue
        best = None
        for label, params in variants:
            if not params:
                continue
            key = json.dumps(params, sort_keys=True, default=list)
            s = scored[key]
            if s["DEV"]["n"] == 0 or s["VAL"]["n"] == 0:
                continue
            imp_dev = s["DEV"]["avg_net"] - V1["DEV"]["avg_net"]
            imp_val = s["VAL"]["avg_net"] - V1["VAL"]["avg_net"]
            ok = imp_dev > 0 and imp_val > 0 and s["DEV"]["n"] >= 0.4 * V1["DEV"]["n"]
            stab = min(imp_dev, imp_val)
            if ok and (best is None or stab > best["stability"]):
                best = dict(experiment=exp, variant=label, params=params, key=key, imp_dev=imp_dev, imp_val=imp_val, stability=stab)
        if best:
            cands.append(best)
    cands = sorted(cands, key=lambda c: -c["stability"])[:3]
    print("candidates:", [(c["experiment"][:2], c["variant"][:40], round(c["stability"], 3)) for c in cands])

    combos = []
    combo_jobs = []
    if len(cands) >= 2:
        for r_ in range(2, len(cands) + 1):
            for sub in itertools.combinations(range(len(cands)), r_):
                params = {}
                for ix in sub:
                    params.update(cands[ix]["params"])
                combo_jobs.append((" + ".join(f"{cands[ix]['experiment'][:2]}" for ix in sub), params, sub))
    # ---------------------------------------------------------------- walk-forward selection per test year
    wf_jobs = []
    wf_picks = {}
    for Y in [y for y in years if y >= 2023]:
        train = [y for y in years if y < Y]

        def train_avg(s):
            tot_n = sum(s["years"].get(y, {}).get("n", 0) for y in train)
            tot = sum(s["years"].get(y, {}).get("net", 0.0) for y in train)
            return (tot / tot_n if tot_n else np.nan), tot_n

        v1_tr_avg, v1_tr_n = train_avg(V1)
        picks = []
        for exp, variants in EXPERIMENTS.items():
            if exp.startswith("E6"):
                continue
            best = None
            for label, params in variants:
                if not params:
                    continue
                s = scored[json.dumps(params, sort_keys=True, default=list)]
                a, n_ = train_avg(s)
                if np.isnan(a) or n_ < 0.4 * v1_tr_n:
                    continue
                imp = a - v1_tr_avg
                if imp > 0 and (best is None or imp > best["imp"]):
                    best = dict(experiment=exp, variant=label, params=params, imp=imp)
            if best:
                picks.append(best)
        picks = sorted(picks, key=lambda c: -c["imp"])[:3]
        wf_picks[Y] = picks
        params = {}
        for c in picks:
            params.update(c["params"])
        wf_jobs.append((Y, params))
    extra = [(f"combo::{lab}", params) for lab, params, _ in combo_jobs] + [(f"wf::{Y}", params) for Y, params in wf_jobs]
    extra_res = {}
    for name, tr, info in run_jobs(extra):
        extra_res[name] = score(tr, cuts)[0]
        print(f"  done: {name} n={len(tr)}")
    for lab, params, sub in combo_jobs:
        s = extra_res[f"combo::{lab}"]
        combos.append(dict(label=lab, members=[cands[ix]["variant"] for ix in sub], params=params, score=s))
    wf_rows = []
    for Y, params in wf_jobs:
        s = extra_res[f"wf::{Y}"]
        wf_rows.append(dict(year=Y, picks=[f"{c['experiment'][:2]}: {c['variant']}" for c in wf_picks[Y]],
                            test=s["years"].get(Y, metrics(pd.DataFrame())), v1=V1["years"].get(Y, metrics(pd.DataFrame()))))

    # ---------------------------------------------------------------- report
    L = []
    w = L.append
    w("# V2 Research Report - can the V1 weaknesses be turned into a robust edge?\n")
    w(f"Same data, engine and costs as the baseline (Dukascopy XAUUSD M1 -> 5-min, 39 months between "
      f"{str(pd.Timestamp(v1_tr.t_ms.min(), unit='ms').date())} and {str(pd.Timestamp(v1_tr.t_ms.max(), unit='ms').date())}; "
      f"one spread per trade of {E.SPREAD_BY_YEAR}). V1 rules are frozen; every variant flips exactly one switch. "
      f"Metrics: gross R and net R (after spread); PF and max drawdown are on gross R.\n")
    w(f"Chronological split from the V1 trade list: Development = before {cut_dates[0]} ({V1['DEV']['n']} V1 trades), "
      f"Validation = {cut_dates[0]} to {cut_dates[1]} ({V1['VAL']['n']}), Out-of-sample = after {cut_dates[1]} ({V1['OOS']['n']}). "
      "Every variant runs over the whole history and is then sliced by these dates, so a filter that removes a trade can change "
      "which later setup the one-position rule lets through; the slices are exact, not approximations.\n")
    w("Selection rule for the combination (fixed before running): a variant qualifies when its average net R per trade beats V1 in "
      "BOTH Development and Validation and keeps at least 40% of V1's Development trades; ranked by the smaller of the two improvements; "
      "at most one per experiment; top 3. Out-of-sample is never used for selection.\n")
    w("## V1 reference\n")
    w(HEAD_MAIN)
    w(row_main("V1 baseline", V1["all"]))
    w("")
    w(HEAD_PER)
    w(row_periods("V1 baseline", V1))
    w("")
    for exp, variants in EXPERIMENTS.items():
        w(f"## {exp}\n")
        w(HEAD_MAIN)
        for label, params in variants:
            s = scored[json.dumps(params, sort_keys=True, default=list)]
            w(row_main(label, s["all"], V1["all"]))
        w("")
        w(HEAD_PER)
        for label, params in variants:
            s = scored[json.dumps(params, sort_keys=True, default=list)]
            w(row_periods(label, s))
        w("")
        w("| Variant | " + " | ".join(f"{y} (n / avg net R)" for y in years) + " |\n|---|" + "---|" * len(years))
        for label, params in variants:
            s = scored[json.dumps(params, sort_keys=True, default=list)]
            w(row_years(label, s, years))
        w("")
        if exp.startswith("E1"):
            for label, params in variants:
                s = scored[json.dumps(params, sort_keys=True, default=list)]
                tr = results[json.dumps(params, sort_keys=True, default=list)][0]
                if params:
                    ex_counts = tr.exit_reason.value_counts().to_dict()
                    fbr = tr[tr.exit_reason == "FB"].result_R
                    w(f"- {label}: exits {ex_counts}" + (f"; average FB exit {fbr.mean():+.2f}R (a full stop is -1R)" if len(fbr) else "") +
                      (f"; setups invalidated by a close back inside before entry: {s['info']['blocked']['reconfirm_invalidated']}" if params.get("confirm_bars", 1) > 1 else ""))
            w("")
        if exp.startswith(("E2", "E3", "E4")):
            for label, params in variants:
                s = scored[json.dumps(params, sort_keys=True, default=list)]
                if params:
                    b = {k: v for k, v in s["info"]["blocked"].items() if v}
                    w(f"- {label}: setups blocked {b}")
            w("")
    # E6 tables
    w("### E6 detail: V1 by session and year (n / avg net R)\n")
    w("| Session | " + " | ".join(str(y) for y in years) + " | DEV | VAL | OOS |\n|---|" + "---|" * (len(years) + 3))
    for s_ in SESSIONS:
        cells = [s_]
        for y in years:
            r = sy[(sy.session == s_) & (sy.year == y)]
            cells.append(f"{int(r.n.iloc[0])} / {r.avg_net.iloc[0]:+.3f}" if len(r) else "-")
        for per in ("DEV", "VAL", "OOS"):
            r = sp[(sp.session == s_) & (sp.period == per)]
            cells.append(f"{int(r.n.iloc[0])} / {r.avg_net.iloc[0]:+.3f}" if len(r) else "-")
        w("| " + " | ".join(cells) + " |")
    w("")
    w("## E7 Zone quality (V1 trades; terciles fixed on the whole sample; Spearman rank correlation of the feature with the trade's R)\n")
    w("| Feature | Period | rho (p) | n | low tercile (n / win / avg net R) | mid | high |\n|---|---|---|---|---|---|---|")
    for rec in e7:
        for per in ("DEV", "VAL", "OOS"):
            w(f"| {rec['feature']} | {per} | {f(rec[f'{per}_rho'], '{:+.3f}')} ({f(rec[f'{per}_p'], '{:.2f}')}) | {rec[f'{per}_n']} | "
              f"{rec.get(f'{per}_low', rec.get(f'{per}_all', ''))} | {rec.get(f'{per}_mid', '')} | {rec.get(f'{per}_high', '')} |")
    w("")
    w("First touch vs repeated touch (V1):\n")
    w("| Period | Touch | n | Win rate | Avg net R |\n|---|---|---|---|---|")
    for _, r in e7_touch.iterrows():
        w(f"| {r.period} | {r.touch} | {int(r.n)} | {r.wr:.1%} | {r.avg_net:+.3f} |")
    w("")
    # combination
    w("## Combination test\n")
    if not cands:
        w("No variant satisfied the pre-registered rule (better average net R than V1 in both Development and Validation with at "
          "least 40% of the trades). There is nothing to combine.\n")
    else:
        w("Candidates (rule above):\n")
        for c in cands:
            w(f"- {c['experiment']}: {c['variant']} (improvement in avg net R: DEV {c['imp_dev']:+.3f}, VAL {c['imp_val']:+.3f})")
        w("")
        w(HEAD_MAIN)
        w(row_main("V1 baseline", V1["all"]))
        for c in cands:
            w(row_main(f"{c['experiment'][:2]} alone: {c['variant']}", scored[c['key']]["all"], V1["all"]))
        for cb in combos:
            w(row_main(f"{cb['label']}: " + " + ".join(m[:35] for m in cb["members"]), cb["score"]["all"], V1["all"]))
        w("")
        w(HEAD_PER)
        w(row_periods("V1 baseline", V1))
        for c in cands:
            w(row_periods(f"{c['experiment'][:2]} alone", scored[c['key']]))
        for cb in combos:
            w(row_periods(cb["label"], cb["score"]))
        w("")
        w("| Variant | " + " | ".join(f"{y} (n / avg net R)" for y in years) + " |\n|---|" + "---|" * len(years))
        w(row_years("V1 baseline", V1, years))
        for cb in combos:
            w(row_years(cb["label"], cb["score"], years))
        w("")
    w("## Walk-forward (selection redone each year on the years before it, then applied to that year only)\n")
    w("| Test year | Switches picked on the prior years | V1 in that year (n / avg net R / net R) | Picked combination in that year |\n|---|---|---|---|")
    for r in wf_rows:
        w(f"| {r['year']} | {'; '.join(p[:70] for p in r['picks']) if r['picks'] else 'none qualified (V1 kept)'} | "
          f"{r['v1']['n']} / {f(r['v1']['avg_net'], '{:+.3f}')} / {f(r['v1']['net'], '{:+.1f}')} | "
          f"{r['test']['n']} / {f(r['test']['avg_net'], '{:+.3f}')} / {f(r['test']['net'], '{:+.1f}')} |")
    w("")
    open("V2_RESEARCH_REPORT.md", "w", encoding="utf-8").write("\n".join(L))
    json.dump(dict(cut_dates=cut_dates, V1=V1, scored={seen[k][1]: v for k, v in scored.items()}, candidates=cands,
                   combos=[dict(label=c["label"], members=c["members"], score=c["score"]) for c in combos],
                   walk_forward=wf_rows), open(f"{OUT}/v2_lab.json", "w"), indent=1, default=str)
    print("report written")


if __name__ == "__main__":
    main()
