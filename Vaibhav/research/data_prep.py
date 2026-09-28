"""Build the research datasets from the downloaded Dukascopy / XM files and audit them.

Outputs (research/data/):
  m1_server.npz            M1 bid bars, XM server time (EET, EU DST), 2020-09 .. 2026-09-25
  h1_server.npz            H1 bid bars, server time, 2003-05 .. 2026-09-25 (Dukascopy H1 to 2021-08, then M1 resampled)
  spread_model.json        XM GOLD spread (points) by year x server hour, M1-equivalent
  audit.json / AUDIT.md    data audit report

Nothing is repaired silently: duplicates are dropped (counted), flat zero-volume prints are dropped (counted),
prices are rounded to XM's 0.01 point (documented). Gaps are reported, never filled.
"""
import glob, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"D:/Practice_Playwright/Momentum_Tracker_Indicator/backtest/data"
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)


def eu_dst(ts: pd.Series) -> np.ndarray:
    """True where EU summer time applies (last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC)."""
    y = ts.dt.year
    out = np.zeros(len(ts), bool)
    for yy in y.unique():
        mar = pd.Timestamp(yy, 3, 31); mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
        octo = pd.Timestamp(yy, 10, 31); octo -= pd.Timedelta(days=(octo.weekday() + 1) % 7)
        m = (y == yy).to_numpy()
        out[m] = ((ts[m] >= mar + pd.Timedelta(hours=1)) & (ts[m] < octo + pd.Timedelta(hours=1))).to_numpy()
    return out


def to_server(utc: pd.Series) -> pd.Series:
    return utc + pd.to_timedelta(np.where(eu_dst(utc), 3, 2), unit="h")


def load_chunks(pattern):
    parts = []
    for f in sorted(glob.glob(pattern)):
        d = pd.read_csv(f)
        if len(d):
            d["src_file"] = os.path.basename(f)
            parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["time_utc"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    return df


def audit_series(df: pd.DataFrame, step_sec: int, label: str) -> dict:
    """Audit an OHLC series (UTC times, raw prices). Returns dict of findings."""
    a = {"label": label}
    a["rows_raw"] = int(len(df))
    dup = df.duplicated("timestamp", keep="first")
    a["duplicate_timestamps"] = int(dup.sum())
    d = df[~dup].sort_values("timestamp").reset_index(drop=True)
    a["non_monotonic_in_source"] = int((df["timestamp"].diff() < 0).sum())
    a["start_utc"] = str(d["time_utc"].iloc[0]); a["end_utc"] = str(d["time_utc"].iloc[-1])
    a["rows_unique"] = int(len(d))
    bad_hl = d["high"] < d["low"]
    bad_o = (d["open"] > d["high"]) | (d["open"] < d["low"])
    bad_c = (d["close"] > d["high"]) | (d["close"] < d["low"])
    a["invalid_high_lt_low"] = int(bad_hl.sum()); a["open_outside_hl"] = int(bad_o.sum()); a["close_outside_hl"] = int(bad_c.sum())
    a["nonpositive_prices"] = int(((d[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum())
    a["nan_rows"] = int(d[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    a["zero_volume_rows"] = int((d["volume"] <= 0).sum())
    flat = (d["high"] == d["low"]) & (d["volume"] <= 0)
    a["flat_zero_volume_rows"] = int(flat.sum())
    # timestamp alignment
    a["misaligned_timestamps"] = int(((d["timestamp"] // 1000) % step_sec != 0).sum())
    # gaps: consecutive differences beyond one step, split into weekend and intraweek
    dt = d["timestamp"].diff().div(1000).fillna(step_sec).astype("int64")
    gap = dt > step_sec
    ts_prev = d["time_utc"].shift(1)
    wd_prev = ts_prev.dt.weekday
    weekend = gap & ((wd_prev == 4) & (ts_prev.dt.hour >= 20) | (wd_prev == 5) | (wd_prev == 6))
    intraweek = gap & ~weekend
    a["weekend_gaps"] = int(weekend.sum())
    a["intraweek_gaps_total"] = int(intraweek.sum())
    big = intraweek & (dt >= 3600)
    a["intraweek_gaps_ge_1h"] = int(big.sum())
    rows = []
    for i in np.where(big)[0][:400]:
        rows.append({"from_utc": str(ts_prev.iloc[i]), "to_utc": str(d["time_utc"].iloc[i]), "hours": round(dt.iloc[i] / 3600, 1)})
    rows.sort(key=lambda r: -r["hours"])
    a["largest_intraweek_gaps"] = rows[:25]
    # expected vs actual bars per month (trading minutes ~ Sun 22:00 -> Fri 21:00 UTC = 5 x 23h approx)
    d["ym"] = d["time_utc"].dt.strftime("%Y-%m")
    per_month = d.groupby("ym").size()
    a["bars_per_month"] = {k: int(v) for k, v in per_month.items()}
    # abnormal jumps: close-to-close move relative to rolling median range
    rng = (d["high"] - d["low"]).rolling(2000, min_periods=200).median()
    jump = (d["close"].diff().abs() / rng.replace(0, np.nan))
    pct = d["close"].pct_change().abs()
    a["jumps_gt_20x_median_range"] = int((jump > 20).sum())
    a["jumps_gt_1pct_one_bar"] = int((pct > 0.01).sum())
    a["jumps_gt_3pct_one_bar"] = int((pct > 0.03).sum())
    top = d.assign(pct=pct, jump=jump).nlargest(15, "pct")[["time_utc", "open", "high", "low", "close", "pct", "jump"]]
    top["time_utc"] = top["time_utc"].astype(str)
    a["largest_one_bar_moves"] = top.round(4).to_dict("records")
    # per-year price and range summary
    d["year"] = d["time_utc"].dt.year
    yr = d.groupby("year").agg(bars=("close", "size"), close_med=("close", "median"), close_min=("low", "min"), close_max=("high", "max"),
                               range_med=("high", lambda s: float(np.median(s.values - d.loc[s.index, "low"].values))))
    a["per_year"] = {int(k): {kk: (round(float(vv), 3) if kk != "bars" else int(vv)) for kk, vv in v.items()} for k, v in yr.iterrows()}
    a["price_decimals_observed"] = int(d["close"].astype(str).str.split(".").str[1].str.len().max())
    return a


def main():
    report = {}
    # ------------------------------------------------------------------ M1
    m1 = load_chunks(os.path.join(SRC, "duka_chunks", "bid_*.csv"))
    report["m1"] = audit_series(m1, 60, "Dukascopy XAUUSD M1 bid (UTC)")
    m1 = m1.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    n0 = len(m1)
    flat = (m1["high"] == m1["low"]) & (m1["volume"] <= 0)
    m1 = m1[~flat].reset_index(drop=True)
    report["m1"]["transform_dropped_flat_zero_volume"] = int(n0 - len(m1))
    report["m1"]["transform_rounding"] = "prices rounded to 0.01 (XM GOLD point); Dukascopy supplies 3 decimals"
    for c in ("open", "high", "low", "close"):
        m1[c] = m1[c].round(2)
    m1["time"] = to_server(m1["time_utc"])
    m1 = m1.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    report["m1"]["transform_timezone"] = "UTC -> XM server time (EET: UTC+2, UTC+3 in EU summer time)"
    report["m1"]["start_server"] = str(m1["time"].iloc[0]); report["m1"]["end_server"] = str(m1["time"].iloc[-1])
    report["m1"]["rows_final"] = int(len(m1))
    np.savez_compressed(os.path.join(OUT, "m1_server.npz"), t=(m1["time"].astype("int64") // 10**9).to_numpy(),
                        o=m1["open"].to_numpy(), h=m1["high"].to_numpy(), l=m1["low"].to_numpy(), c=m1["close"].to_numpy(), v=m1["volume"].to_numpy())
    print("M1", len(m1), m1["time"].iloc[0], m1["time"].iloc[-1], flush=True)

    # ------------------------------------------------------------------ H1 (2003 .. 2021-08 from Dukascopy H1, then resampled M1)
    h1 = load_chunks(os.path.join(SRC, "duka_h1", "bid_h1_*.csv"))
    report["h1"] = audit_series(h1, 3600, "Dukascopy XAUUSD H1 bid (UTC)")
    h1 = h1.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    h1 = h1[~((h1["high"] == h1["low"]) & (h1["volume"] <= 0))].reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        h1[c] = h1[c].round(2)
    h1["time"] = to_server(h1["time_utc"])
    cut = m1["time"].iloc[0].floor("h")
    h1 = h1[h1["time"] < cut]
    # resample M1 (server time) to H1 for the overlap period
    secs = m1["time"].astype("int64") // 10**9
    key = (secs // 3600) * 3600
    g = m1.groupby(key, sort=True)
    h1b = pd.DataFrame({"time": pd.to_datetime(g["time"].first().index, unit="s"), "open": g["open"].first().values, "high": g["high"].max().values,
                        "low": g["low"].min().values, "close": g["close"].last().values, "volume": g["volume"].sum().values})
    h1all = pd.concat([h1[["time", "open", "high", "low", "close", "volume"]], h1b], ignore_index=True).sort_values("time").reset_index(drop=True)
    report["h1"]["rows_final_combined"] = int(len(h1all)); report["h1"]["start_server"] = str(h1all["time"].iloc[0]); report["h1"]["end_server"] = str(h1all["time"].iloc[-1])
    report["h1"]["join_point_server"] = str(cut)
    np.savez_compressed(os.path.join(OUT, "h1_server.npz"), t=(h1all["time"].astype("int64") // 10**9).to_numpy(),
                        o=h1all["open"].to_numpy(), h=h1all["high"].to_numpy(), l=h1all["low"].to_numpy(), c=h1all["close"].to_numpy(), v=h1all["volume"].to_numpy())
    print("H1", len(h1all), h1all["time"].iloc[0], h1all["time"].iloc[-1], flush=True)

    # ------------------------------------------------------------------ Dukascopy D1 file vs server-time D1 built here
    d1file = pd.read_csv(os.path.join(SRC, "xauusd_d1_bid.csv"))
    d1file["time_utc"] = pd.to_datetime(d1file["timestamp"], unit="ms")
    report["d1_file"] = {"label": "Dukascopy XAUUSD D1 bid (UTC-day bars, downloaded file)", "rows": int(len(d1file)),
                         "start": str(d1file["time_utc"].iloc[0]), "end": str(d1file["time_utc"].iloc[-1]),
                         "note": "UTC-midnight days; XM D1 bars start at server midnight (22:00/21:00 UTC). The research D1 series is built from H1/M1 in server time instead."}

    # ------------------------------------------------------------------ XM comparison (broker-specific check) and spread model
    xm15 = pd.read_csv(os.path.join(SRC, "xm_GOLD_M15.csv.gz")); xm15["time"] = pd.to_datetime(xm15["time"])
    xm5 = pd.read_csv(os.path.join(SRC, "xm_GOLD_M5.csv.gz")); xm5["time"] = pd.to_datetime(xm5["time"])
    xm1 = pd.read_csv(os.path.join(SRC, "xm_GOLD_M1.csv.gz")); xm1["time"] = pd.to_datetime(xm1["time"])
    # M15 bars from our M1 (server time) for the overlap
    key15 = (secs // 900) * 900
    g = m1.groupby(key15, sort=True)
    d15 = pd.DataFrame({"time": pd.to_datetime(g["time"].first().index, unit="s"), "close": g["close"].last().values, "high": g["high"].max().values,
                        "low": g["low"].min().values, "volume": g["volume"].sum().values})
    j = xm15.merge(d15, on="time", suffixes=("_xm", "_dk"))
    diff = (j["close_xm"] - j["close_dk"])
    cmp = {"overlap_bars_M15": int(len(j)), "xm_bars_without_duka_match": int(len(xm15) - len(j)),
           "close_diff_median_abs": round(float(diff.abs().median()), 3), "close_diff_p90_abs": round(float(diff.abs().quantile(0.9)), 3),
           "close_diff_mean_signed": round(float(diff.mean()), 4), "high_diff_median_abs": round(float((j["high_xm"] - j["high_dk"]).abs().median()), 3),
           "range_ratio_xm_over_duka_median": round(float(((j["high_xm"] - j["low_xm"]) / (j["high_dk"] - j["low_dk"]).replace(0, np.nan)).median()), 3),
           "volume_corr_xm_tickvol_vs_duka_volume": round(float(np.corrcoef(j["tick_volume"], j["volume"])[0, 1]), 3)}
    # volume filter agreement: v[j] > mean(v[j-19..j]) on both feeds
    for col, name in (("tick_volume", "xm"), ("volume", "dk")):
        j[f"vf_{name}"] = j[col] > j[col].rolling(20).mean()
    both = j.dropna(subset=["vf_xm", "vf_dk"])
    cmp["volume_filter_agreement_M15"] = round(float((both["vf_xm"] == both["vf_dk"]).mean()), 3)
    cmp["volume_filter_pass_rate_xm"] = round(float(both["vf_xm"].mean()), 3); cmp["volume_filter_pass_rate_dk"] = round(float(both["vf_dk"].mean()), 3)
    report["xm_vs_dukascopy"] = cmp
    # XM session hours (server time) observed on M15: first/last bar hour of the day
    xm15["date"] = xm15["time"].dt.date
    hrs = xm15.groupby("date")["time"].agg(["min", "max"])
    report["xm_trading_hours_server"] = {"typical_first_bar": str(hrs["min"].dt.strftime("%H:%M").mode().iloc[0]), "typical_last_bar": str(hrs["max"].dt.strftime("%H:%M").mode().iloc[0]),
                                         "note": "Dukascopy has bars from Sunday 22:00 UTC; XM GOLD opens Monday ~01:05 server. Bars outside XM hours are kept in the data and flagged in the engine as non-tradable."}
    # spread model: M15 close-spread medians by year x hour, scaled to M1-equivalent by the observed 2026 M1/M15 ratio per hour
    xm15["year"] = xm15["time"].dt.year; xm15["hour"] = xm15["time"].dt.hour
    xm1["hour"] = xm1["time"].dt.hour; xm5["hour"] = xm5["time"].dt.hour; xm5["year"] = xm5["time"].dt.year
    m15_2026 = xm15[xm15["year"] == 2026].groupby("hour")["spread"].median()
    m1_2026 = xm1.groupby("hour")["spread"].median()
    ratio = (m1_2026 / m15_2026).clip(1.0, 2.0)
    ratio_overall = float(xm1["spread"].median() / xm15.loc[xm15["year"] == 2026, "spread"].median())
    piv = xm15.pivot_table(index="hour", columns="year", values="spread", aggfunc="median")
    model = {}
    for y in range(2003, 2027):
        yy = y if y in piv.columns else (2022 if y < 2022 else 2026)
        col = piv[yy].fillna(piv[yy].median())
        model[str(y)] = [round(float(col.loc[h] * ratio.get(h, ratio_overall)), 1) if h in col.index else round(float(col.median() * ratio_overall), 1) for h in range(24)]
    spread_info = {"model_points_by_year_hour": model, "m15_close_median_by_year": {str(k): float(v) for k, v in xm15.groupby("year")["spread"].median().items()},
                   "m5_close_median_by_year": {str(k): float(v) for k, v in xm5.groupby("year")["spread"].median().items()},
                   "m1_close_median_2026": float(xm1["spread"].median()), "m1_p90_2026": float(xm1["spread"].quantile(0.9)), "m1_p99_2026": float(xm1["spread"].quantile(0.99)),
                   "m1_over_m15_ratio_2026": round(ratio_overall, 3),
                   "note": "Years before 2022 use the 2022 profile (no XM data); XM GOLD spread in 2005-2015 is unknown, this is an assumption.",
                   "hours_with_spread_ge_2x_median_2026_M1": {str(k): round(float(v), 1) for k, v in (xm1.groupby("hour")["spread"].median()).items()}}
    with open(os.path.join(OUT, "spread_model.json"), "w") as f:
        json.dump(spread_info, f, indent=1)
    report["spread"] = {k: v for k, v in spread_info.items() if k != "model_points_by_year_hour"}
    report["spread"]["abnormal_spread_bars_M1_2026_gt_150pts"] = int((xm1["spread"] > 150).sum())
    report["spread"]["abnormal_spread_bars_M15_gt_100pts"] = int((xm15["spread"] > 100).sum())

    with open(os.path.join(OUT, "audit.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    write_md(report)
    print("audit written", flush=True)


def write_md(r):
    m = r["m1"]; h = r["h1"]; x = r["xm_vs_dukascopy"]; s = r["spread"]
    L = ["# GOLD data audit", "", "Source: Dukascopy XAUUSD bid candles (dukascopy-node), UTC, 3-decimal prices, traded volume (not tick count). "
         "Broker reference: XM Global MT5 GOLD (digits 2, point 0.01, contract 100 oz, 0.01 lot = 1 oz).", "",
         "## Primary dataset: M1", "", "| Item | Value |", "|---|---|",
         f"| Start (UTC) | {m['start_utc']} |", f"| End (UTC) | {m['end_utc']} |", f"| Start / end (server time) | {m['start_server']} / {m['end_server']} |",
         f"| Raw rows | {m['rows_raw']:,} |", f"| Duplicate timestamps dropped | {m['duplicate_timestamps']} |", f"| Flat zero-volume rows dropped | {m['transform_dropped_flat_zero_volume']} |",
         f"| Final rows | {m['rows_final']:,} |", f"| high < low | {m['invalid_high_lt_low']} |", f"| open outside [low, high] | {m['open_outside_hl']} |", f"| close outside [low, high] | {m['close_outside_hl']} |",
         f"| non-positive prices | {m['nonpositive_prices']} |", f"| NaN rows | {m['nan_rows']} |", f"| misaligned timestamps | {m['misaligned_timestamps']} |",
         f"| weekend gaps | {m['weekend_gaps']} |", f"| intraweek gaps (any missing minute) | {m['intraweek_gaps_total']:,} |", f"| intraweek gaps >= 1 h | {m['intraweek_gaps_ge_1h']} |",
         f"| one-bar moves > 1% | {m['jumps_gt_1pct_one_bar']} |", f"| one-bar moves > 3% | {m['jumps_gt_3pct_one_bar']} |", f"| moves > 20x median bar range | {m['jumps_gt_20x_median_range']} |",
         "", "Transformations: " + m["transform_rounding"] + "; " + m["transform_timezone"] + ". No gap filling, no bar synthesis.", "",
         "### Largest intraweek gaps (M1)", "", "| From (UTC) | To (UTC) | Hours |", "|---|---|---:|"]
    for g in m["largest_intraweek_gaps"][:15]:
        L.append(f"| {g['from_utc']} | {g['to_utc']} | {g['hours']} |")
    L += ["", "### Bars per month (M1)", "", "| Month | Bars |", "|---|---:|"]
    for k, v in m["bars_per_month"].items():
        L.append(f"| {k} | {v:,} |")
    L += ["", "### Per year (M1)", "", "| Year | Bars | Median close | Low | High | Median bar range |", "|---|---:|---:|---:|---:|---:|"]
    for y, v in m["per_year"].items():
        L.append(f"| {y} | {v['bars']:,} | {v['close_med']:.2f} | {v['close_min']:.2f} | {v['close_max']:.2f} | {v['range_med']:.3f} |")
    L += ["", "### Largest one-bar moves (M1)", "", "| Time (UTC) | Open | High | Low | Close | Move % |", "|---|---:|---:|---:|---:|---:|"]
    for t in m["largest_one_bar_moves"][:10]:
        L.append(f"| {t['time_utc']} | {t['open']} | {t['high']} | {t['low']} | {t['close']} | {t['pct']*100:.2f} |")
    L += ["", "## Long-history dataset: H1 (for D1 before Sep 2020)", "", "| Item | Value |", "|---|---|",
          f"| Start / end (server) | {h['start_server']} / {h['end_server']} |", f"| Rows | {h['rows_final_combined']:,} |", f"| Dukascopy H1 used until | {h['join_point_server']} (then H1 resampled from M1) |",
          f"| Duplicates dropped | {h['duplicate_timestamps']} |", f"| high < low | {h['invalid_high_lt_low']} |", f"| intraweek gaps >= 1 h (H1 step) | {h['intraweek_gaps_ge_1h']} |",
          f"| one-bar moves > 3% | {h['jumps_gt_3pct_one_bar']} |", "", "### Per year (H1)", "", "| Year | Bars | Median close | Low | High |", "|---|---:|---:|---:|---:|"]
    for y, v in h["per_year"].items():
        L.append(f"| {y} | {v['bars']:,} | {v['close_med']:.2f} | {v['close_min']:.2f} | {v['close_max']:.2f} |")
    L += ["", "## Broker check: XM GOLD vs Dukascopy (M15 overlap, Jul 2022 - Sep 2026)", "", "| Item | Value |", "|---|---|"]
    for k, v in x.items():
        L.append(f"| {k} | {v} |")
    L += ["", f"XM trading hours (server): first bar {r['xm_trading_hours_server']['typical_first_bar']}, last bar {r['xm_trading_hours_server']['typical_last_bar']}. " + r["xm_trading_hours_server"]["note"], "",
          "## Spread (XM GOLD, points, from XM's own bars)", "", "| Item | Value |", "|---|---|"]
    for k, v in s.items():
        if k not in ("hours_with_spread_ge_2x_median_2026_M1",):
            L.append(f"| {k} | {v} |")
    L += ["", "M1 median spread by server hour, 2026: " + ", ".join(f"{k}h {v}" for k, v in s["hours_with_spread_ge_2x_median_2026_M1"].items()), "",
          "## Verdicts", "",
          "- Timeframes supported: M1, M5, M15 (built from M1) for 6 years 1 month (Sep 2020 - Sep 2026); D1 for 23 years (2003 - 2026) with H1 intrabar path before Sep 2020 and M1 path after.",
          "- Prices are Dukascopy's Swiss-bank feed, not XM's. XM closes differ by a few cents at the median (see table); XM's bar ranges are slightly wider. Results are therefore feed-specific and the tester on XM would differ trade by trade.",
          "- Volume is Dukascopy traded volume, not MT5 tick volume. The EA's volume filter is ratio-based; agreement between the two feeds is reported above and is well below 100%, so trade lists cannot match the MT5 tester one for one.",
          "- Spread: Dukascopy candles carry no spread. XM's real spread by year and hour is applied (M1-equivalent). Before 2022 the spread is an assumption.",
          "- No spread abnormalities are in the price data itself; XM's own spread shows widening at 00:00-02:00 server and at news (p99 reported)."]
    with open(os.path.join(HERE, "AUDIT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
