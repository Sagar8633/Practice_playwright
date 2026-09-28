"""STEPS 6-8 / sections 10, 11, 27, 28: baseline trade analysis.

Inputs: results/baseline/trades_{TF}_{period}_strategy_B_real.csv (untouched EA, 0.01 lot, realistic costs).
Outputs (results/trade_analysis/):
  giveback_{TF}.json / giveback_tables.md       profit giveback overall, by direction, session, regime, year
  p2l_{TF}_{threshold}.csv                       profitable -> loss reversal reports (every trade, full detail)
  p2l_summary.json                               counts / damage per threshold and timeframe
  loss_categories_{TF}.csv, loss_summary.json    top losing trades categorised, share of total losses per category
  trade_level_{TF}.csv                           full trade-level dataset (section 27) with indicator state, regime, post-exit excursion
"""
import json, os
import numpy as np
import pandas as pd

import sma18_engine as E
import common as C

BASE = os.path.join(C.RES, "baseline"); OUT = os.path.join(C.RES, "trade_analysis"); os.makedirs(OUT, exist_ok=True)
SETS = [("M1", 1, "6y", "m1"), ("M5", 5, "6y", "m1"), ("M15", 15, "6y", "m1"), ("D1", 1440, "6y", "m1"), ("D1_23y", 1440, "23y_h1path", "h1")]
THRESH_USD = [1, 2, 5, 10]; THRESH_R = [1, 2, 3]


def enrich(tr: pd.DataFrame, tf_minutes: int, path_kind: str) -> pd.DataFrame:
    """Indicator state at entry / at the MFE bar / at exit, post-exit excursion, drawdown after MFE."""
    path = E.load_path(path_kind); tf = E.build_tf(path, tf_minutes); ind = E.indicators(tf, E.Params(tf_minutes=tf_minutes))
    tfj = tf["tfj"]; h, l, c = path["h"], path["l"], path["c"]; spr = E._spread_array(path, E.Params())
    n = len(path["t"])
    out = tr.copy()
    j_out = tfj[out["k_out"].to_numpy()] - 1; j_mfe = tfj[out["k_mfe"].to_numpy()] - 1; j_in = out["j_in"].to_numpy() - 1
    for nm, jj in (("entry", j_in), ("mfe", j_mfe), ("exit", j_out)):
        jj = np.clip(jj, 0, tf["n"] - 1)
        out[f"close_vs_ma18_{nm}"] = np.round(tf["c"][jj] - ind["ma_f"][jj], 2)
        out[f"ma18_vs_ma200_{nm}"] = np.round(ind["ma_f"][jj] - ind["ma_t"][jj], 2)
        out[f"adx_{nm}"] = np.round(ind["adx"][jj], 1)
        out[f"atr_{nm}"] = np.round(ind["atr"][jj], 2)
        out[f"ma18_slope_{nm}"] = np.round(ind["ma_f"][jj] - ind["ma_f"][np.maximum(jj - 3, 0)], 2)
    # max drawdown after the MFE point (price units, adverse move from best to worst-after-best), and post-exit excursion (20 signal bars)
    side = out["side"].to_numpy(); k_mfe = out["k_mfe"].to_numpy(); k_out = out["k_out"].to_numpy(); entry = out["entry"].to_numpy()
    dd_after = np.zeros(len(out)); fav_after = np.zeros(len(out)); adv_after = np.zeros(len(out)); price_at_mfe = np.zeros(len(out))
    horizon = 20 * tf_minutes if path_kind == "m1" else max(20 * tf_minutes // 60, 20)
    for i in range(len(out)):
        a, b = k_mfe[i], k_out[i] + 1
        if side[i] == 1:
            best = h[a]; price_at_mfe[i] = best; dd_after[i] = best - l[a:b].min()
            e = k_out[i] + 1; f = min(e + horizon, n)
            if f > e: fav_after[i] = h[e:f].max() - out["exit"].iat[i]; adv_after[i] = out["exit"].iat[i] - l[e:f].min()
        else:
            best = l[a] + spr[a]; price_at_mfe[i] = best; dd_after[i] = (h[a:b] + spr[a:b]).max() - best
            e = k_out[i] + 1; f = min(e + horizon, n)
            if f > e: fav_after[i] = out["exit"].iat[i] - (l[e:f] + spr[e:f]).min(); adv_after[i] = (h[e:f] + spr[e:f]).max() - out["exit"].iat[i]
    out["max_fav_price"] = np.round(price_at_mfe, 2)
    out["dd_after_mfe_usd"] = np.round(dd_after * E.CONTRACT * out["lots"], 2)
    out["post_exit_fav_usd"] = np.round(fav_after * E.CONTRACT * out["lots"], 2)
    out["post_exit_adv_usd"] = np.round(adv_after * E.CONTRACT * out["lots"], 2)
    out["post_exit_fav_r"] = np.where(out["risk_usd"] > 0, out["post_exit_fav_usd"] / out["risk_usd"], np.nan).round(2)
    out["cost_usd"] = np.round((out["spread_entry"] + out["slip_usd"] * 0 + 0.10) * E.CONTRACT * out["lots"], 2)   # spread + 10-pt slippage per side
    out["gross_before_costs_usd"] = np.round(out["gross_usd"] + out["cost_usd"], 2)
    out["bar_range_atr_exit"] = np.round((h[k_out] - l[k_out]) / np.maximum(out["atr_exit"].to_numpy(), 1e-9), 2)
    out["exit_mechanism"] = out["exit_reason"]
    out["initial_tp"] = np.nan
    return out


def categorise_loss(r: pd.Series, med_risk: float, tf_minutes: int) -> str:
    """Priority rules (first match). Only for losing trades."""
    mfe_r = r["mfe_r"] if pd.notna(r["mfe_r"]) else 0.0
    if r["exit_reason"] == "stop_out": return "12 other (stop-out)"
    if abs(r["pnl"]) <= r["cost_usd"] * 1.0 and r["gross_before_costs_usd"] >= 0: return "11 spread/slippage (positive before costs)"
    if r["regime_big_move"] is True or r["bar_range_atr_exit"] >= 3.0 or r["regime_sharp_reversal"] is True: return "09 news/volatility event"
    if r["hour_in"] in (1, 2, 22, 23) and tf_minutes < 1440: return "10 low-liquidity hour"
    if r["exit_reason"] == "SL_initial" and r["risk_usd"] >= 2.0 * med_risk: return "04 excessive SL"
    if r["exit_reason"] in ("SL_breakeven", "SL_swing", "SL_chandelier", "SL_trailing", "SL_atr_trail", "SL_twk_trail", "SL_lock") and r["post_exit_fav_r"] >= 1.0: return "05 trailing/protection too tight"
    if mfe_r >= 1.0 and r["giveback_pct"] >= 60: return "06 trailing/protection too loose (gave back >60% of >=1R)"
    if r["bars_held"] <= 3 and r["exit_reason"] == "MA18_exit": return "03 whipsaw (MA18 exit within 3 bars)"
    if mfe_r < 0.25: return "01 bad entry (never reached 0.25R)"
    if mfe_r >= 0.5: return "02 correct entry, market reversal"
    return "12 other"


summary_gb = {}; p2l_summary = {}; loss_summary = {}
for name, tfm, per, pk in SETS:
    f = os.path.join(BASE, f"trades_{name.split('_')[0]}_{per}_strategy_B_real.csv")
    tr = pd.read_csv(f, parse_dates=["time_in", "time_out", "time_mfe", "time_pend"])
    if len(tr) == 0:
        continue
    tr = enrich(tr, tfm, pk)
    tr["direction"] = np.where(tr["side"] == 1, "long", "short"); tr["year"] = tr["time_out"].dt.year
    tr.to_csv(os.path.join(OUT, f"trade_level_{name}.csv"), index=False)
    # ---------------- giveback
    gb = {"overall": {"trades": int(len(tr)), "avg_giveback": round(float(tr["giveback_usd"].mean()), 2), "median_giveback": round(float(tr["giveback_usd"].median()), 2),
                      "worst_giveback": round(float(tr["giveback_usd"].max()), 2), "median_giveback_pct": round(float(tr["giveback_pct"].median()), 1),
                      "total_mfe": round(float(tr["mfe_usd"].sum()), 2), "total_realized": round(float(tr["pnl"].sum()), 2),
                      "share_trades_with_mfe_ge_1usd": round(float((tr["mfe_usd"] >= 1).mean()), 3),
                      "avg_dd_after_mfe": round(float(tr["dd_after_mfe_usd"].mean()), 2)}}
    for col in ("direction", "session", "regime", "exit_reason", "year"):
        g = tr.groupby(col)
        gb[col] = pd.DataFrame({"trades": g.size(), "net": g["pnl"].sum().round(2), "avg_mfe": g["mfe_usd"].mean().round(2), "avg_giveback": g["giveback_usd"].mean().round(2),
                                "median_giveback_pct": g["giveback_pct"].median().round(1), "worst_giveback": g["giveback_usd"].max().round(2),
                                "p2l_2usd": g.apply(lambda x: int(((x["mfe_usd"] >= 2) & (x["pnl"] < 0)).sum())),
                                "p2l_2usd_damage": g.apply(lambda x: round(float(x.loc[(x["mfe_usd"] >= 2) & (x["pnl"] < 0), "pnl"].sum()), 2))}).to_dict("index")
    summary_gb[name] = gb
    # ---------------- profitable -> loss reversals
    p2l_summary[name] = {}
    cols = ["time_pend", "time_in", "time_out", "direction", "entry", "isl", "risk_usd", "max_fav_price", "mfe_usd", "mfe_r", "time_mfe", "exit", "pnl", "r", "dd_after_mfe_usd",
            "exit_mechanism", "sl_exit", "max_sl", "be_hit", "giveback_usd", "giveback_pct", "close_vs_ma18_mfe", "ma18_vs_ma200_mfe", "adx_mfe", "ma18_slope_mfe",
            "close_vs_ma18_exit", "adx_exit", "bars_held", "hold_min", "session", "regime", "post_exit_fav_usd", "spread_entry"]
    for lab, mask in [(f"{t}usd", (tr["mfe_usd"] >= t) & (tr["pnl"] < 0)) for t in THRESH_USD] + [(f"{t}R", (tr["mfe_r"] >= t) & (tr["pnl"] < 0)) for t in THRESH_R]:
        sub = tr[mask].sort_values("mfe_usd", ascending=False)
        sub[cols].to_csv(os.path.join(OUT, f"p2l_{name}_{lab}.csv"), index=False)
        tot_loss = float(tr.loc[tr["pnl"] < 0, "pnl"].sum())
        p2l_summary[name][lab] = {"trades": int(len(sub)), "share_of_all_trades": round(float(mask.mean()), 4), "share_of_losers": round(float(len(sub) / max((tr["pnl"] < 0).sum(), 1)), 3),
                                  "realized_loss": round(float(sub["pnl"].sum()), 2), "unrealized_profit_given_up": round(float(sub["mfe_usd"].sum()), 2),
                                  "share_of_total_losses": round(float(sub["pnl"].sum() / tot_loss), 3) if tot_loss else 0.0,
                                  "avg_mfe": round(float(sub["mfe_usd"].mean()), 2) if len(sub) else 0.0, "avg_final": round(float(sub["pnl"].mean()), 2) if len(sub) else 0.0,
                                  "exit_mechanism_mix": {k: int(v) for k, v in sub["exit_mechanism"].value_counts().items()},
                                  "by_direction": {k: int(v) for k, v in sub["direction"].value_counts().items()},
                                  "by_session": {k: int(v) for k, v in sub["session"].value_counts().items()},
                                  "median_bars_from_mfe_to_exit": float(((sub["k_out"] - sub["k_mfe"])).median()) if len(sub) else 0.0,
                                  "median_close_vs_ma18_at_mfe": round(float(sub["close_vs_ma18_mfe"].median()), 2) if len(sub) else 0.0,
                                  "share_price_continued_favourably_after_exit_ge_1R": round(float((sub["post_exit_fav_r"] >= 1).mean()), 3) if len(sub) else 0.0}
    # ---------------- loss categories
    losers = tr[tr["pnl"] < 0].copy()
    med_risk = float(tr["risk_usd"].median())
    losers["category"] = losers.apply(lambda r: categorise_loss(r, med_risk, tfm), axis=1)
    tot = float(losers["pnl"].sum())
    cat = losers.groupby("category").agg(trades=("pnl", "size"), loss=("pnl", "sum"), avg_loss=("pnl", "mean"), avg_mfe=("mfe_usd", "mean"))
    cat["share_of_total_loss_pct"] = (100 * cat["loss"] / tot).round(1); cat = cat.round(2).sort_values("loss")
    cat.to_csv(os.path.join(OUT, f"loss_categories_{name}.csv"))
    loss_summary[name] = {"total_loss": round(tot, 2), "losing_trades": int(len(losers)), "categories": cat.to_dict("index"),
                          "top20_losses": losers.nsmallest(20, "pnl")[["time_in", "time_out", "direction", "entry", "isl", "exit", "pnl", "r", "mfe_usd", "mae_usd", "exit_mechanism", "category", "regime", "session", "bars_held"]].astype(str).to_dict("records")}
    print(name, "trades", len(tr), "giveback avg", gb["overall"]["avg_giveback"], "P->L>$2", p2l_summary[name]["2usd"]["trades"], "cats", len(cat), flush=True)

C.save_json(summary_gb, "trade_analysis/giveback.json"); C.save_json(p2l_summary, "trade_analysis/p2l_summary.json"); C.save_json(loss_summary, "trade_analysis/loss_summary.json")

# ---------------- markdown
L = ["# Trade analysis of the untouched EA (strategy view, 0.01 lot, realistic costs)", ""]
for name in summary_gb:
    g = summary_gb[name]; o = g["overall"]
    L += [f"## {name}", "", f"Trades {o['trades']}; total MFE ${o['total_mfe']} vs realized ${o['total_realized']}; average giveback ${o['avg_giveback']} (median ${o['median_giveback']}, worst ${o['worst_giveback']}); "
          f"median giveback {o['median_giveback_pct']}% of MFE; share of trades that were ever >= $1 in profit: {o['share_trades_with_mfe_ge_1usd']}.", ""]
    for col in ("direction", "session", "regime", "exit_reason"):
        L += [f"### Giveback by {col}", "", "| " + col + " | trades | net $ | avg MFE $ | avg giveback $ | median giveback % | worst $ | P->L >$2 | P->L damage $ |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for k, v in g[col].items():
            L.append(f"| {k} | {v['trades']} | {v['net']} | {v['avg_mfe']} | {v['avg_giveback']} | {v['median_giveback_pct']} | {v['worst_giveback']} | {v['p2l_2usd']} | {v['p2l_2usd_damage']} |")
        L.append("")
    L += ["### Profitable -> loss reversals", "", "| threshold | trades | share of losers | realized loss $ | profit given up $ | share of total losses | exit mechanism mix | continued >=1R after exit |", "|---|---:|---:|---:|---:|---:|---|---:|"]
    for lab, v in p2l_summary[name].items():
        L.append(f"| {lab} | {v['trades']} | {v['share_of_losers']} | {v['realized_loss']} | {v['unrealized_profit_given_up']} | {v['share_of_total_losses']} | {v['exit_mechanism_mix']} | {v['share_price_continued_favourably_after_exit_ge_1R']} |")
    L += ["", "### Loss categories (all losing trades, first matching rule)", "", "| category | trades | loss $ | avg loss $ | avg MFE $ | share of total loss % |", "|---|---:|---:|---:|---:|---:|"]
    for k, v in loss_summary[name]["categories"].items():
        L.append(f"| {k} | {v['trades']} | {v['loss']} | {v['avg_loss']} | {v['avg_mfe']} | {v['share_of_total_loss_pct']} |")
    L.append("")
with open(os.path.join(OUT, "TRADE_ANALYSIS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("done")
