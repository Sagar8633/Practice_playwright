"""Aggregates results/phase14/events.csv, plateau_dev.csv, tick_audit.csv into summary.json (the tables of the Phase 14 report)."""
import json, math
import numpy as np, pandas as pd

OUT = "results/phase14"
E = pd.read_csv(f"{OUT}/events.csv"); P = pd.read_csv(f"{OUT}/plateau_dev.csv"); Q = pd.read_csv(f"{OUT}/tick_audit.csv")
E["period"] = np.where(pd.to_datetime(E.day).dt.year == 2025, "DEV 2025", "OOS 2026")
E["grp"] = np.select([E.weekday == 3, E.weekday == 4], ["Thursday", "Friday"], "Mon-Wed")
traded_status = ["TARGET_HIT", "STOP_HIT", "TIMEOUT"]

def block(g):
    """Per-group metrics on one scenario's rows."""
    n = len(g); tr = g[g.status.isin(traded_status)]; amb = int((g.status == "AMBIGUOUS_EXECUTION").sum()); di = int((g.status == "DATA_INSUFFICIENT").sum())
    pnl = tr.pnl_atr.dropna(); gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    gross = tr.gross_mid_atr.dropna()
    return dict(n=int(n), data_insufficient=di, ambiguous=amb, trigger_rate=float(len(tr) / max(1, n - di - amb)), up_first=float((tr["first"] == "up").mean()) if len(tr) else np.nan, down_first=float((tr["first"] == "down").mean()) if len(tr) else np.nan,
                both_touched=float(tr.both_touched.astype(float).mean()) if len(tr) else np.nan, both_executed=float(tr.both_executed.astype(float).mean()) if len(tr) else np.nan,
                target=float((tr.status == "TARGET_HIT").mean()) if len(tr) else np.nan, stop=float((tr.status == "STOP_HIT").mean()) if len(tr) else np.nan, timeout=float((tr.status == "TIMEOUT").mean()) if len(tr) else np.nan,
                gross=float(gross.mean()) if len(gross) else np.nan, net=float(pnl.mean()) if len(pnl) else np.nan, pf=float(gp / gl) if gl > 0 else (9.99 if gp > 0 else np.nan),
                mfe_med=float(tr.mfe_atr.median()) if len(tr) else np.nan, mae_med=float(tr.mae_atr.median()) if len(tr) else np.nan, cost_share=float(1 - pnl.mean() / gross.mean()) if len(gross) and gross.mean() > 0 else np.nan,
                spread_driven=float(tr.spread_driven.astype(float).mean()) if len(tr) and "spread_driven" in tr else np.nan, t_trigger_med_ms=float(tr.t_trigger_ms.median()) if len(tr) else np.nan)

S = dict(generated=str(pd.Timestamp.now())[:16])
S["audit"] = dict(days=int(len(Q)), ticks_total=int(Q.ticks.sum()), dup_timestamps_share=round(float(Q.dup_ts.sum() / max(1, Q.ticks.sum())), 4), bid_gt_ask=int(Q.bid_gt_ask.sum()), zero_or_neg_spread=int(Q.zero_or_neg_spread.sum()),
                  spread_median_usd=round(float(Q.spread_med.median()), 3), spread_p99_usd=round(float(Q.spread_p99.median()), 3), spread_max_usd=round(float(Q.spread_max.max()), 3), max_gap_s_median=round(float(Q.max_gap_s.median()), 1),
                  ticks_in_1530_minute_median=int(Q.ticks_1530_1531.median()), price_decimals=int(Q.price_decimals.max()), timezone="Dukascopy UTC ms, shifted to XM server time (EET, EU DST) per day", symbol="XAUUSD spot (Dukascopy), 1 lot = 1 oz quotes; sizes in millions of units",
                  days_missing_event_hour=int((E[E.scenario == "B"].status == "DATA_INSUFFICIENT").sum()))
B = E[(E.scenario == "B")]
S["by_group"] = []
for per in ("DEV 2025", "OOS 2026"):
    for grp in ("Thursday", "Friday", "Mon-Wed", "All"):
        g = B[(B.period == per) & ((B.grp == grp) if grp != "All" else True)]
        if len(g) == 0: continue
        S["by_group"].append(dict(group=f"{per} {grp}", **block(g)))
S["by_scenario"] = []
for sc, lab in (("A", "A trigger tick"), ("B", "B 250 ms fill delay"), ("C", "C worst within 1 s"), ("A_lat0", "A, 0 ms cancel latency"), ("A_lat1000", "A, 1000 ms cancel latency")):
    for per in ("DEV 2025", "OOS 2026"):
        g = E[(E.scenario == sc) & (E.period == per)]
        if len(g) == 0: continue
        b = block(g); S["by_scenario"].append(dict(scenario=lab, period=per, days=int(len(g)), traded=int(len(g[g.status.isin(traded_status)])), net=b["net"], pf=b["pf"], gross=b["gross"]))
    # XM overlay on B: add (0.51 - dukascopy spread at trigger) per round trip when positive
if len(B):
    for per in ("DEV 2025", "OOS 2026"):
        g = B[(B.period == per) & B.status.isin(traded_status)].copy()
        if len(g) == 0: continue
        extra = np.maximum(0.51 - g.spread_at_trigger, 0) / g.atr
        S["by_scenario"].append(dict(scenario="B + XM spread overlay", period=per, days=int(len(B[B.period == per])), traded=int(len(g)), net=float((g.pnl_atr - extra).mean()), pf=np.nan, gross=float(g.gross_mid_atr.mean())))
S["first_touch"] = []
for per in ("DEV 2025", "OOS 2026"):
    for grp in ("Thursday", "Friday", "All"):
        g = B[(B.period == per) & ((B.grp == grp) if grp != "All" else True) & B.status.isin(traded_status)]
        if len(g) < 5: continue
        up = g[g["first"] == "up"]; dn = g[g["first"] == "down"]
        S["first_touch"].append(dict(period=per, group=grp, n=int(len(g)), up_first=float((g["first"] == "up").mean()), net_up=float(up.pnl_atr.mean()) if len(up) else np.nan, net_down=float(dn.pnl_atr.mean()) if len(dn) else np.nan, cont=float((g.status == "TARGET_HIT").mean())))
bins = [-1, 1000, 5000, 10000, 30000, 60000, 300000, 900000, 1800000, 10**9]; labels = ["0-1 s", "1-5 s", "5-10 s", "10-30 s", "30-60 s", "1-5 min", "5-15 min", "15-30 min", "> 30 min"]
tb = B[B.status.isin(traded_status)].copy(); tb["bucket"] = pd.cut(tb.t_trigger_ms, bins, labels=labels)
S["windows"] = [dict(bucket=str(k), n=int(len(g)), net=float(g.pnl_atr.mean()), pf=float(g.pnl_atr[g.pnl_atr > 0].sum() / max(1e-9, -g.pnl_atr[g.pnl_atr < 0].sum())), target=float((g.status == "TARGET_HIT").mean())) for k, g in tb.groupby("bucket", observed=True)]
# toxicity types on scenario B, all days
def tox_type(r):
    if r.status == "NO_TRADE": return "5 no trigger"
    if r.status == "AMBIGUOUS_EXECUTION" or bool(r.both_touched) and r.status in traded_status and (r.t_exit_ms or 0) <= 60000 and r.status == "STOP_HIT": return "3 both sides touched (stop inside 60 s)"
    if bool(r.get("spread_driven", False)): return "4 spread-driven trigger"
    if r.status in ("TARGET_HIT", "STOP_HIT") and (r.t_exit_ms or 0) <= 60000: return "2 immediate overshoot (resolved inside 60 s)"
    if r.status in traded_status: return "1 clean trigger"
    return "0 data insufficient"
B2 = B.copy(); B2["tox"] = B2.apply(tox_type, axis=1)
S["toxicity"] = [dict(type=k, n=int(len(g)), share=float(len(g) / len(B2)), net=float(g.pnl_atr.mean()) if g.pnl_atr.notna().any() else np.nan, target=float((g.status == "TARGET_HIT").mean()), range_med=float((g.first_min_bid_range / g.atr).median()), spmax_med=float((g.spread_max_1min / g.atr).median())) for k, g in B2.groupby("tox")]
# plateaus (DEV only, Thu/Fri)
P["grp"] = np.select([P.weekday == 3, P.weekday == 4], ["Thursday", "Friday"], "Mon-Wed"); Pt = P[P.grp.isin(["Thursday", "Friday"]) & P.status.isin(traded_status)]
S["plateau"] = [dict(kind=k, value=v, n=int(len(g)), net=float(g.pnl_atr.mean()), pf=float(g.pnl_atr[g.pnl_atr > 0].sum() / max(1e-9, -g.pnl_atr[g.pnl_atr < 0].sum())), target=float((g.status == "TARGET_HIT").mean())) for (k, v), g in Pt.groupby(["kind", "value"])]
# controls
C = E[E.scenario == "CONTROL_random_same_day"]
S["controls"] = [dict(control="random same-day timestamp (15:20-19:00), same rules, Scenario B", period=per, n=int(len(g[g.status.isin(traded_status)])), net=float(g[g.status.isin(traded_status)].pnl_atr.mean()), pf=block(g)["pf"]) for per, g in C.groupby("period")]
S["controls"].append(dict(control="15:30 event, Mon-Wed (no weekly-release selection)", period="see by-group table", n=int(len(B[(B.grp == "Mon-Wed") & B.status.isin(traded_status)])), net=float(B[(B.grp == "Mon-Wed") & B.status.isin(traded_status)].pnl_atr.mean()) if (B.grp == "Mon-Wed").any() else np.nan, pf=np.nan))
# concentration (Thu/Fri, scenario B, both periods)
tf = B[B.grp.isin(["Thursday", "Friday"]) & B.status.isin(traded_status)].copy(); tf["week"] = pd.to_datetime(tf.day).dt.to_period("W").astype(str)
net = tf.pnl_atr.sum()
S["concentration"] = dict(events_traded=int(len(tf)), net_total_atr=round(float(net), 2), best_event=round(float(tf.pnl_atr.max()), 2), worst_event=round(float(tf.pnl_atr.min()), 2), share_of_events_positive=round(float((tf.pnl_atr > 0).mean()), 3),
                          net_without_best_5=round(float(net - tf.pnl_atr.nlargest(5).sum()), 2), net_without_worst_5=round(float(net - tf.pnl_atr.nsmallest(5).sum()), 2), best_week_share=("n/a (net <= 0)" if net <= 0 else round(float(tf.groupby("week").pnl_atr.sum().max() / net), 2)),
                          weeks_positive=f"{int((tf.groupby('week').pnl_atr.sum() > 0).sum())} of {tf.week.nunique()}")
# cost survival
S["cost"] = []
for per in ("DEV 2025", "OOS 2026"):
    a = E[(E.scenario == "A") & (E.period == per) & E.status.isin(traded_status)]; b = E[(E.scenario == "B") & (E.period == per) & E.status.isin(traded_status)]
    if len(b) == 0: continue
    extra = np.maximum(0.51 - b.spread_at_trigger, 0) / b.atr
    S["cost"].append(dict(period=per, gross=float(b.gross_mid_atr.mean()), netA=float(a.pnl_atr.mean()) if len(a) else np.nan, netB=float(b.pnl_atr.mean()), netXM=float((b.pnl_atr - extra).mean()), share=float(1 - b.pnl_atr.mean() / b.gross_mid_atr.mean()) if b.gross_mid_atr.mean() > 0 else np.nan))
json.dump(S, open(f"{OUT}/summary.json", "w"), indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else (float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x)))))
pd.set_option("display.width", 250)
print("BY GROUP (Scenario B):"); print(pd.DataFrame(S["by_group"])[["group", "n", "ambiguous", "trigger_rate", "up_first", "both_touched", "both_executed", "target", "stop", "timeout", "gross", "net", "pf", "spread_driven", "t_trigger_med_ms"]].round(3).to_string(index=False))
print("\nSCENARIOS:"); print(pd.DataFrame(S["by_scenario"]).round(3).to_string(index=False))
print("\nWINDOWS:"); print(pd.DataFrame(S["windows"]).round(3).to_string(index=False))
print("\nTOXICITY:"); print(pd.DataFrame(S["toxicity"]).round(3).to_string(index=False))
print("\nPLATEAU (DEV Thu/Fri):"); print(pd.DataFrame(S["plateau"]).round(3).to_string(index=False))
print("\nCONTROLS:"); print(pd.DataFrame(S["controls"]).round(3).to_string(index=False)); print("\nCONCENTRATION:", S["concentration"]); print("\nCOST:"); print(pd.DataFrame(S["cost"]).round(3).to_string(index=False)); print("\nAUDIT:", S["audit"])
