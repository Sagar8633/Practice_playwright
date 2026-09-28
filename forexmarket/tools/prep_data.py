"""Build the engine's path arrays per instrument, in XM server time:
  m1_server.npz   from Dukascopy monthly M1 (preferred) or the fallback folder data/alt (FXCM / Binance), UTC -> server time
  m15_server.npz  from XM's own M15 bars (data/xm/xm_<SYM>_M15_full.csv.gz, ~Sep 2022 onward, spread + tick volume)
  h1_server.npz   from XM's own H1 bars (2015 onward) - the long D1/H4 path
plus audit.json, and the spread model per instrument = XM H1 median spread by year x server hour (data/xm/spread_models.json).
Usage: python prep_data.py [instrument ...]"""
import glob, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DUKA = os.path.join(ROOT, "data", "duka"); ALT = os.path.join(ROOT, "data", "alt"); XM = os.path.join(ROOT, "data", "xm")
XMSYM = {"eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY", "audusd": "AUDUSD", "usdcad": "USDCAD", "usdchf": "USDCHF", "nzdusd": "NZDUSD",
         "xagusd": "SILVER", "btcusd": "BTCUSD", "lightcmdusd": "OILCash"}
MONTHS = [(y, m) for y in range(2021, 2027) for m in range(1, 13) if not (y == 2021 and m < 9) and not (y == 2026 and m > 9)]


def eu_dst(ts: pd.Series) -> np.ndarray:
    y = ts.dt.year; out = np.zeros(len(ts), bool)
    for yy in y.unique():
        mar = pd.Timestamp(yy, 3, 31); mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
        octo = pd.Timestamp(yy, 10, 31); octo -= pd.Timedelta(days=(octo.weekday() + 1) % 7)
        m = (y == yy).to_numpy(); out[m] = ((ts[m] >= mar + pd.Timedelta(hours=1)) & (ts[m] < octo + pd.Timedelta(hours=1))).to_numpy()
    return out


def to_server(utc: pd.Series) -> pd.Series:
    return utc + pd.to_timedelta(np.where(eu_dst(utc), 3, 2), unit="h")


def load(files):
    parts = [pd.read_csv(f) for f in files]
    df = pd.concat([p for p in parts if len(p)], ignore_index=True)
    df["time_utc"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    return df


def audit(df, step_s, label, tcol="time_utc"):
    a = {"label": label, "rows": int(len(df)), "first": str(df[tcol].min()), "last": str(df[tcol].max())}
    a["duplicates"] = int(df.duplicated(tcol).sum()); a["zero_volume_rows"] = int((df.volume <= 0).sum())
    bad = (df.high < df.low) | (df.high < df.open) | (df.high < df.close) | (df.low > df.open) | (df.low > df.close); a["ohlc_violations"] = int(bad.sum())
    a["nonpositive_prices"] = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    d = df[tcol].diff().dt.total_seconds().dropna(); gaps = d[(d > step_s) & (d < 40 * 3600)]
    a["intraweek_gaps_gt_step"] = int(len(gaps)); a["intraweek_gap_hours_total"] = float((gaps.sum() - len(gaps) * step_s) / 3600)
    a["largest_intraweek_gap_h"] = float(gaps.max() / 3600) if len(gaps) else 0.0
    big = d[d >= 40 * 3600]; a["gaps_over_40h"] = [str(df[tcol].iloc[i - 1])[:10] + ".." + str(df[tcol].iloc[i])[:10] for i in big.index[:12]] if len(big) else []
    r = (df.close / df.close.shift(1) - 1).abs(); a["max_abs_1bar_return_pct"] = float(r.max() * 100); a["bars_ret_gt_2pct"] = int((r > 0.02).sum())
    a["weekend_bars"] = int((df[tcol].dt.weekday >= 5).sum())
    return a


def savez(path, t, o, h, l, c, v, dt_):
    np.savez_compressed(path, t=(t.astype("int64") // 10**9).to_numpy(), o=o.to_numpy(dt_), h=h.to_numpy(dt_), l=l.to_numpy(dt_), c=c.to_numpy(dt_), v=v.to_numpy(dt_))


def pick_source(instr):
    cands = []
    for name, base in (("dukascopy", DUKA), ("fallback", ALT)):
        fs = sorted(glob.glob(os.path.join(base, instr, "m1_*.csv"))); fs = [f for f in fs if os.path.getsize(f) > 1000]
        cands.append((len(fs), 1 if name == "dukascopy" else 0, name, fs))
    cands.sort(reverse=True)
    return cands[0][2], cands[0][3]


def prep(instr):
    sym = XMSYM[instr]; out = os.path.join(ROOT, "data", instr); os.makedirs(out, exist_ok=True); dt_ = np.float64 if instr == "btcusd" else np.float32
    source, files = pick_source(instr)
    have = {os.path.basename(f)[3:10] for f in files}; missing = [f"{y}-{m:02d}" for y, m in MONTHS if f"{y}-{m:02d}" not in have]
    rep = {"instrument": instr, "xm_symbol": sym, "m1_source": source if files else "none", "m1_months_present": len(have), "m1_months_missing": missing}
    m1 = None
    if files:
        m1 = load(files).drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)
        rep["m1"] = audit(m1, 60, f"{source} {instr} M1 bid (UTC)"); rep["has_volume"] = bool((m1.volume > 0).mean() > 0.5)
        flat = (m1.high == m1.low) & (m1.volume <= 0); rep["m1"]["flat_zero_volume_dropped"] = int(flat.sum()); m1 = m1[~flat]
        m1["time"] = to_server(m1["time_utc"])
        savez(os.path.join(out, "m1_server.npz"), m1["time"], m1.open, m1.high, m1.low, m1.close, m1.volume, dt_)
        rep["m1"]["server_first"] = str(m1.time.iloc[0]); rep["m1"]["server_last"] = str(m1.time.iloc[-1]); rep["m1"]["weeks"] = int(m1.time.dt.to_period("W").nunique())
    # ---- XM M15 path (server time already)
    f15 = os.path.join(XM, f"xm_{sym}_M15_full.csv.gz")
    if os.path.exists(f15):
        x = pd.read_csv(f15, parse_dates=["time"]).drop_duplicates("time").sort_values("time")
        rep["m15"] = audit(x.rename(columns={"tick_volume": "volume"}), 900, f"XM {sym} M15 (server time)", "time")
        savez(os.path.join(out, "m15_server.npz"), x["time"], x.open, x.high, x.low, x.close, x.tick_volume, dt_)
        rep["m15"]["median_spread_pts"] = float(x.spread.median())
    # ---- XM H1 long path
    fh = os.path.join(XM, f"xm_{sym}_H1_full.csv.gz")
    if os.path.exists(fh):
        x = pd.read_csv(fh, parse_dates=["time"]).drop_duplicates("time").sort_values("time")
        rep["h1"] = audit(x.rename(columns={"tick_volume": "volume"}), 3600, f"XM {sym} H1 (server time)", "time")
        savez(os.path.join(out, "h1_server.npz"), x["time"], x.open, x.high, x.low, x.close, x.tick_volume, dt_)
        # spread model: median spread by year x server hour from XM H1 (real broker spread, every hour of every year)
        x["year"] = x.time.dt.year; x["hour"] = x.time.dt.hour; piv = x.pivot_table(index="year", columns="hour", values="spread", aggfunc="median").reindex(columns=range(24)).ffill(axis=1).bfill(axis=1)
        model = {str(int(y)): [float(v) for v in piv.loc[y].to_numpy()] for y in piv.index}
        if instr == "lightcmdusd":      # XM's OILCash H1 bars report spread 0; use the M15 spread column (3 pts) and the M1 sample (5 pts): take 4 points flat
            model = {y: [4.0] * 24 for y in model}
        allm = json.load(open(os.path.join(XM, "spread_models.json"))) if os.path.exists(os.path.join(XM, "spread_models.json")) else {}
        allm[instr] = model; json.dump(allm, open(os.path.join(XM, "spread_models.json"), "w"), indent=1)
        rep["spread_model_2026_median_pts"] = float(np.median(model[max(model)]))
        rep["xm_h1_median_spread_by_year"] = {y: round(float(np.median(v)), 1) for y, v in model.items()}
    # ---- XM vs M1 cross-check on the M1 overlap (XM M1 sample of ~70 days)
    f1 = os.path.join(XM, f"xm_{sym}_M1.csv.gz"); rep["xm"] = {}
    if m1 is not None and os.path.exists(f1):
        point = float(json.load(open(os.path.join(XM, "xm_symbol_specs.json")))[sym]["point"])
        x = pd.read_csv(f1, parse_dates=["time"]); j = x.set_index("time")[["close", "high", "low"]].join(m1.set_index("time")[["close", "high", "low"]], rsuffix="_src", how="inner")
        if len(j):
            rep["xm"] = {"m1_overlap_bars": int(len(j)), "close_diff_median_pts": round(float(((j.close - j.close_src).abs() / point).median()), 2), "close_diff_p99_pts": round(float(((j.close - j.close_src).abs() / point).quantile(.99)), 2),
                         "high_diff_p99_pts": round(float(((j.high - j.high_src).abs() / point).quantile(.99)), 2), "low_diff_p99_pts": round(float(((j.low - j.low_src).abs() / point).quantile(.99)), 2)}
        xd = x.groupby(x.time.dt.normalize()).time.agg(["min", "max"]); rep["xm"]["typical_first_bar"] = str(xd["min"].dt.strftime("%H:%M").mode().iloc[0]); rep["xm"]["typical_last_bar"] = str(xd["max"].dt.strftime("%H:%M").mode().iloc[0])
    json.dump(rep, open(os.path.join(out, "audit.json"), "w"), indent=1, default=str)
    return rep


if __name__ == "__main__":
    todo = sys.argv[1:] or list(XMSYM)
    for instr in todo:
        r = prep(instr)
        print(instr, "| m1", r["m1_source"], r["m1_months_present"], "months, missing", r["m1_months_missing"][:6], "| m15", r.get("m15", {}).get("first", "")[:10], "| h1", r.get("h1", {}).get("first", "")[:10], "| spread 2026", r.get("spread_model_2026_median_pts"), "| xm vs m1", r.get("xm", {}).get("close_diff_median_pts"), flush=True)
