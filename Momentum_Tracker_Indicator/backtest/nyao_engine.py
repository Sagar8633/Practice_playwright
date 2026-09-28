"""nyao_engine.py: Python port of Nyao Scalper MT5 v43 (github.com/elrizwiraswara/nyao_scalper_mt5, BSD-3-Clause)
for the XAUUSD M1 dataset used by the TWK labs.

Everything below was read from nyao_scalper.mq5 (5,867 lines), not from the README.

Signal      ComputeRawScore: trend (EMA fast > slow + multi-bar slope), momentum (RSI zone + RSI trigger + body >
            average body, multiplied by an impulse factor built from body/range acceleration and candle continuity),
            chop (ATR / average ATR), volatility bonus, 5-bar peak breakout, wick-rejection penalty; clamped 0-10.
            The dead-market gate returns 0 when ATR / average ATR < MinVolRatioToTrade.
            GetSignalStrength: linearly weighted average of the last N closed candles' scores, blended with the score
            of the forming candle (CurrentCandleBlend).
Entry       Evaluated once per bar at its first tick (EnableNewBarEntryOnly), so the forming candle is a one-tick
            candle (open = high = low = close). BuySignal/SellSignal: threshold + consecutive-candle boost + drawdown
            gate, score minus a penalty per losing same-direction position; the higher of the two wins.
            CheckEntryConditions: one trade per candle, no opposite trade on the same candle, hard block at
            MaxLosingPositionsSameDir, cooldown after consecutive losses, duplicate-distance filter.
            IsAllowedToOpenPosition: pause states, losing positions < MaxHoldingLossPositions, open < MaxOpenOrders,
            spread <= MaxSpreadATRRatio x ATR (forming candle).
Sizing      BaseLotSize plus drawdown steps (CalculateDynamicLotSize). Stop = SLValue % of equity converted to points
            for the lot, TP off (default profile), or the independent R:R mode (ATR x mult, TP = RR x stop).
Exits       ManageTrailingTPSL: dollar trailing distance +/- adaptive score delta, profit gate, break-even lock at
            entry + spread + MinBreakEvenProfit; graduated hedge legs trail at HedgeTrailATR x ATR with a recovery
            floor. ManageLosingPositions: grace bars, break-even on spread, scaled partial close on signal decay,
            health-based stop tightening, profit-offset stop, health-decay full close + virtual-SL re-entry.
            CheckBasketStop, CheckEquityDrawdawn (pause), MinimumEquity (stop).
Hedge       ManageHedgeChains: rolling martingale. Starts at HedgeTriggerATR adverse with reverse-score confirmation,
            auto-sized recovery lot, covered / roll / reseed / release, naked legs, root stop cleared.
Not ported  MT5 economic-calendar news filter (the tester has no calendar either), Discord, dashboard, leverage
            pause, market-close session query (replaced by "no entries on Friday after 23:25 server time").

Execution model (same conventions as twk_engine)
  * Bid bars; ask = bid + spread (XM median by year). Buys fill at ask, sells at bid.
  * Inside an M1 bar a stop is checked before a target. Gaps fill at the open.
  * Entries at the open of the signal bar; management at every M1 bar close; trailing exits inside a bar are
    reported under two bounds: trail_mode="path" (the bar extreme was reached first, exit at the trailed stop) and
    trail_mode="worst" (the first reversal of the trailing distance happened right after activation: exit at
    max(bar low, the stop level active when trailing first engaged)). Ticks would sit between the two.
  * Partial closes do not feed the consecutive-loss counter (they never fire at 0.01 lot: 0.25 x 0.01 rounds to the
    minimum lot and leaves nothing, exactly as in the EA).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace, asdict

import numpy as np
import pandas as pd

import twk_engine as E

NAN = float("nan")
POINT = 0.01
VALUE_PER_POINT_PER_LOT = 1.0        # XM GOLD: contract 100 oz, tick 0.01 -> $1 per point per 1.0 lot
LOT_MIN, LOT_STEP = 0.01, 0.01
INPUT_DOLLAR, INPUT_PERCENT, INPUT_POINTS = 0, 1, 2


# --------------------------------------------------------------------------------------
# Parameters (names = EA inputs; defaults = settings/default.set)
# --------------------------------------------------------------------------------------

@dataclass
class NyaoParams:
    name: str = "nyao_default"
    # indicator
    DirectionalBodyLookback: int = 10
    EMAFastPeriod: int = 5
    EMASlowPeriod: int = 12
    SlopeLookback: int = 3
    RSIPeriod: int = 8
    ATRPeriod: int = 8
    ATRAvgLookback: int = 10
    MinVolRatioToTrade: float = 0.6
    ImpulseLookback: int = 3
    ImpulseBoostWeight: float = 1.0
    SignalSmoothingCandles: int = 2
    CurrentCandleBlend: float = 0.40
    RSIOverbought: int = 80
    RSIOversold: int = 20
    RSIMomentumBuy: int = 60
    RSIMomentumSell: int = 40
    # weights
    TrendWeight: float = 1.5
    SlopeWeight: float = 1.5
    MomentumBaseWeight: float = 1.0
    MomentumTriggerWeight: float = 0.5
    BodyMomentumWeight: float = 1.5
    ChopScoreHigh: float = 2.0
    ChopScoreMed: float = 1.0
    ChopScoreLow: float = 0.0
    VolatilityScoreHigh: float = 1.0
    VolatilityScoreLow: float = 0.0
    PeakScoreWeight: float = 1.0
    WickRejectionWeight: float = 1.0
    MinBodyRatio: float = 1.5
    # orders
    EnableBuyOrders: bool = True
    EnableSellOrders: bool = True
    EnableNewBarEntryOnly: bool = True
    EnableMaxSpreadFilter: bool = True
    MaxSpreadPoints: float = 0.0
    MaxSpreadATRRatio: float = 0.25
    BaseLotSize: float = 0.01
    MaxOpenOrders: int = 8
    MaxTradesPerCandle: int = 1
    ConsecutiveCandleThresholdBoost: float = 1.0
    MaxConsecutiveCandleBoosts: int = 3
    ZonePoints: float = 500.0
    BuyDuplicateMultiplier: float = 1.5
    SellDuplicateMultiplier: float = 1.5
    MinBreakEvenProfit: float = 0.5
    ProfitThresholdMultiplier: float = 1.5
    LossThresholdMultiplier: float = 2.0
    MinBuySignalScore: float = 4.5
    MinSellSignalScore: float = 4.5
    # dampening
    EnableSignalDampening: bool = True
    MaxLosingPositionsSameDir: int = 2
    LosingPosScorePenalty: float = 1.5
    DrawdownThresholdPct: float = 3.0
    DrawdownScoreBoost: float = 2.0
    ConsecutiveLossesBeforeCooldown: int = 3
    ConsecutiveLossCooldownBars: int = 3
    # loss management
    EnableLossManagement: bool = True
    MaxHoldingLossPositions: int = 2
    MinHealthScore: float = 0.40
    MaxAdverseATR: float = 1.5
    HealthTrendWeight: float = 0.40
    HealthRSIWeight: float = 0.25
    HealthATRWeight: float = 0.25
    HealthSwingWeight: float = 0.10
    HealthRSIBuyMin: float = 40.0
    HealthRSISellMax: float = 60.0
    HealthSwingLookback: int = 20
    HealthGraceBars: int = 2
    EnablePartialClose: bool = True
    PartialClose75Pct: float = 0.25
    PartialClose50Pct: float = 0.50
    PartialClose25Pct: float = 1.00
    EnableHealthSLTightening: bool = True
    SLTightenATRMultiplier: float = 2.0
    SLTightenMinHealthPct: float = 0.50
    EnableBreakEvenOnSpread: bool = True
    BreakEvenSpreadMultiplier: float = 1.5
    EnableVirtualSLReentry: bool = True
    ReentryRespectsNewBarGate: bool = False
    ReentryMinSignalPct: float = 0.75
    EnableProfitOffsetSL: bool = True
    ConsecutiveWinsRequired: int = 3
    MinOffsetProfit: float = 1.0
    # hedge chain
    EnableHedgeChain: bool = True
    HedgeTriggerATR: float = 1.5
    HedgeRequireSignal: bool = True
    HedgeMinSignalScore: float = 4.5
    HedgeAutoLot: bool = True
    HedgeRecoveryATR: float = 1.0
    HedgeLotMultiplier: float = 2.0
    HedgeMaxLot: float = 0.10
    HedgeRecoveryPct: float = 100.0
    HedgeRollMinProfit: float = 0.0
    HedgeCycleLevels: int = 2
    EnableHedgeCycleReset: bool = True
    HedgeCyclePartialPct: float = 50.0
    HedgeMaxCycles: int = 3
    HedgeMaxChainLossUSD: float = 0.0
    HedgeMaxChainLossPct: float = 0.0
    HedgeClearRootSL: bool = True
    HedgeTrailATR: float = 1.0
    # dynamic lots
    EnableDynamicLots: bool = True
    EquityDropPercent: float = 5.0
    MaxEquityDropLotSteps: int = 2
    MinSignalStrengthForLot: float = 8.0
    LotStepSize: float = 0.01
    MaxLotSize: float = 0.05
    # equity
    EnableBasketStop: bool = True
    MaxBasketLossPct: float = 8.0
    MinEquityPercent: float = 70.0
    MaxDrawdownFromPeak: float = 0.0
    PauseMinutes: int = 5
    PauseMinutesMultiplier: float = 1.5
    MaxPauseMinutes: int = 120
    MaxMinEquityTriggers: int = 0
    ResetOnNewPeak: bool = True
    TargetEquity: float = 0.0
    MinimumEquity: float = 20.0
    # TP / SL / RR
    EnableTakeProfit: bool = False
    TPInputType: int = INPUT_DOLLAR
    TPValue: float = 10.0
    EnableStopLoss: bool = True
    SLInputType: int = INPUT_PERCENT
    SLValue: float = 1.0
    EnableRiskReward: bool = False
    RRRiskMode: int = 1                  # 0 manual, 1 ATR
    RRRiskInputType: int = INPUT_POINTS
    RRRiskValue: float = 200.0
    RRAtrMultiplier: float = 1.5
    RiskRewardRatio: float = 1.5
    # trailing
    EnableTrailing: bool = True
    TrailingEnableBreakEvenLock: bool = True
    TrailingSLOnProfitableOnly: bool = True
    EnableAdaptiveTP: bool = True
    EnableAdaptiveSL: bool = True
    TSInputType: int = INPUT_DOLLAR
    TrailingDistanceValue: float = 0.20
    TrailingValueMultiplier: float = 0.20
    # robot
    EnableTradingHours: bool = False
    TradingStartTime: str = "00:00"
    TradingEndTime: str = "23:59"
    EnableMarketCloseFilter: bool = True
    MinutesBeforeClose: int = 30
    # ---- simulator-only options (not EA inputs)
    deposit: float = 1000.0
    trail_mode: str = "path"             # "path" | "worst" | "calib"
    trail_lambda: float = 1.0            # calib: TRAIL exit = worst + lambda x (path - worst)
    trail_lambda_sl: float = 1.0         # calib: a trailed stop hit later = first level + lambda x (stop - first level)
    spread_mult: float = 1.0
    slippage_pts: float = 0.0            # adverse points on market entries and stop exits
    block_windows: tuple = ()            # ((start_min, end_min), ...) server-time minutes of day with no new entries
    stop_level_pts: float = 0.0
    one_position: bool = False           # simulator switch: at most one open position (component tests)


SIGNAL_FIELDS = ("DirectionalBodyLookback", "EMAFastPeriod", "EMASlowPeriod", "SlopeLookback", "RSIPeriod", "ATRPeriod",
                 "ATRAvgLookback", "MinVolRatioToTrade", "ImpulseLookback", "ImpulseBoostWeight", "SignalSmoothingCandles",
                 "CurrentCandleBlend", "RSIOverbought", "RSIOversold", "RSIMomentumBuy", "RSIMomentumSell", "TrendWeight",
                 "SlopeWeight", "MomentumBaseWeight", "MomentumTriggerWeight", "BodyMomentumWeight", "ChopScoreHigh",
                 "ChopScoreMed", "ChopScoreLow", "VolatilityScoreHigh", "VolatilityScoreLow", "PeakScoreWeight",
                 "WickRejectionWeight", "MinBodyRatio", "HealthSwingLookback")


def signal_key(P: NyaoParams, tf: int) -> tuple:
    return (tf,) + tuple(getattr(P, f) for f in SIGNAL_FIELDS)


def load_set(path: str, base: NyaoParams | None = None, name: str | None = None) -> NyaoParams:
    """Read an MT5 .set profile (key=value lines) into NyaoParams."""
    P = base or NyaoParams()
    types = {f.name: f.type for f in fields(NyaoParams)}
    vals = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(";") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip(); v = v.strip()
            if k not in types:
                continue
            t = types[k]
            if t == "bool" or t is bool:
                vals[k] = v.lower() == "true"
            elif t == "int" or t is int:
                vals[k] = int(float(v))
            elif t == "float" or t is float:
                vals[k] = float(v)
            else:
                vals[k] = v
    P = replace(P, **vals)
    if name:
        P = replace(P, name=name)
    return P


# --------------------------------------------------------------------------------------
# Indicators (MT5 built-ins: EMA seeded with the first price; RSI Wilder; ATR = SMA of true range)
# --------------------------------------------------------------------------------------

def mt5_ema(c: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(c).ewm(alpha=2.0 / (n + 1), adjust=False).mean().to_numpy()


def mt5_rsi(c: np.ndarray, n: int):
    d = np.diff(c, prepend=NAN)
    pos = np.where(d > 0, d, 0.0); neg = np.where(d < 0, -d, 0.0)
    pos[0] = NAN; neg[0] = NAN
    ps = E.rma(pos, n); ns = E.rma(neg, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(ns != 0, 100.0 - 100.0 / (1.0 + ps / ns), np.where(ps != 0, 100.0, 50.0))
    rsi[np.isnan(ps)] = NAN
    return rsi, ps, ns


def mt5_atr(h, l, c, n: int):
    tr = E.true_range(h, l, c, True)
    atr = pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy()
    return atr, tr


def _roll(x: np.ndarray, n: int, how: str) -> np.ndarray:
    s = pd.Series(x).rolling(n, min_periods=n)
    return getattr(s, how)().to_numpy()


def _shift(x: np.ndarray, k: int, fill=NAN) -> np.ndarray:
    if k == 0:
        return x
    out = np.full(len(x), fill, dtype=float)
    out[k:] = x[:-k]
    return out


# --------------------------------------------------------------------------------------
# Score (vectorised ComputeRawScore)
# --------------------------------------------------------------------------------------

def _context(tf: dict, P: NyaoParams) -> dict:
    """Rolling context ending at each TF bar index e (bars e, e-1, ... are candles [1], [2], ... of the EA view)."""
    o, h, l, c, atr = tf["o"], tf["h"], tf["l"], tf["c"], tf["atr"]
    body = np.abs(c - o); rng = h - l
    L = P.DirectionalBodyLookback
    A = P.ATRAvgLookback
    ctx = dict(
        avg_body=_roll(body, L, "mean"), avg_rng=_roll(rng, L, "mean"),
        sum_atr_prev=_roll(atr, A - 1, "sum") if A > 1 else np.zeros(len(c)),
        ext_hi=_roll(h, 5, "max"), ext_lo=_roll(l, 5, "min"),
    )
    d = np.sign(c - o)                      # +1 bull, -1 bear, 0 doji
    ctx["dirs"] = [_shift(d, i, 0.0) for i in range(max(P.ImpulseLookback - 1, 0))]   # dirs[i] = direction of candle [1+i]
    return ctx


def _raw_score(P: NyaoParams, is_buy: bool, cur: dict, ctx: dict, e: np.ndarray, ema_f_prev: np.ndarray):
    """cur: forming/[0] candle arrays (o,h,l,c,atr,ema_f,ema_s,rsi); ctx indexed at e; returns score array."""
    o, h, l, c = cur["o"], cur["h"], cur["l"], cur["c"]
    atr0, ef, es, rsi = cur["atr"], cur["ema_f"], cur["ema_s"], cur["rsi"]
    ok = e >= 0
    ee = np.maximum(e, 0)
    avg_body = ctx["avg_body"][ee]; avg_rng = ctx["avg_rng"][ee]; sum_prev = ctx["sum_atr_prev"][ee]
    ext_hi = ctx["ext_hi"][ee]; ext_lo = ctx["ext_lo"][ee]
    # 1 trend
    aligned = (ef > es) if is_buy else (ef < es)
    slope = (ef > ema_f_prev) if is_buy else (ef < ema_f_prev)
    trend = np.minimum(np.where(aligned, P.TrendWeight, 0.0) + np.where(slope, P.SlopeWeight, 0.0), 3.0)
    # 2 momentum
    body = np.abs(c - o); rng = h - l
    if is_buy:
        base = (np.where((rsi > 50) & (rsi < P.RSIOverbought), P.MomentumBaseWeight, 0.0)
                + np.where(rsi > P.RSIMomentumBuy, P.MomentumTriggerWeight, 0.0))
    else:
        base = (np.where((rsi < 50) & (rsi > P.RSIOversold), P.MomentumBaseWeight, 0.0)
                + np.where(rsi < P.RSIMomentumSell, P.MomentumTriggerWeight, 0.0))
    base = base + np.where(body > avg_body, P.BodyMomentumWeight, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        body_acc = np.where(avg_body > 0, np.minimum(body / avg_body, 3.0), 0.0)
        rng_acc = np.where(avg_rng > 0, np.minimum(rng / avg_rng, 3.0), 0.0)
    d0 = (c > o) if is_buy else (c < o)
    cont = d0.astype(float)
    run = d0.astype(float)
    for i in range(P.ImpulseLookback - 1):
        di = ctx["dirs"][i][ee]
        same = (di > 0) if is_buy else (di < 0)
        run = run * same
        cont = cont + run
    cont = np.minimum(cont / max(P.ImpulseLookback, 1), 1.0)
    imp = np.clip((0.5 * body_acc + 0.3 * rng_acc + 0.2 * cont) / 2.0, 0.0, 1.0)
    momentum = np.minimum(base * (1.0 + P.ImpulseBoostWeight * imp), 3.0)
    # 3 chop / dead market
    avg_atr = (atr0 + sum_prev) / P.ATRAvgLookback
    with np.errstate(divide="ignore", invalid="ignore"):
        vol_ratio = np.where(avg_atr > 0, atr0 / avg_atr, 0.0)
    dead = (P.MinVolRatioToTrade > 0) & (vol_ratio > 0) & (vol_ratio < P.MinVolRatioToTrade)
    chop = np.minimum(np.where(vol_ratio > 1.0, P.ChopScoreHigh, np.where(vol_ratio > 0.8, P.ChopScoreMed, P.ChopScoreLow)), 2.0)
    # 4 peak / volatility
    vol = np.where(vol_ratio > 1.2, P.VolatilityScoreHigh, P.VolatilityScoreLow)
    peak = np.where((c > ext_hi) if is_buy else (c < ext_lo), P.PeakScoreWeight, 0.0)
    # 5 wick penalty
    upper = h - np.maximum(o, c); lower = np.minimum(o, c) - l
    safe_body = np.maximum(body, avg_body * P.MinBodyRatio)
    with np.errstate(divide="ignore", invalid="ignore"):
        rej = np.where(safe_body > 0, (upper if is_buy else lower) / safe_body, 0.0)
    pen = rej * P.WickRejectionWeight
    raw = np.clip(trend + momentum + chop + peak + vol - pen, 0.0, 10.0)
    raw = np.where(dead, 0.0, raw)
    raw = np.where(ok & ~np.isnan(raw), raw, 0.0)
    return raw, vol_ratio


def _smooth_base(closed: np.ndarray, e: np.ndarray, N: int) -> np.ndarray:
    """Weighted average of closed[e], closed[e-1], ..., closed[e-N+1] with weights N, N-1, ..., 1."""
    N = min(max(N, 1), 10)
    num = np.zeros(len(e)); den = 0.0
    for i in range(1, N + 1):
        idx = e - i + 1
        w = float(N - i + 1)
        num += w * np.where(idx >= 0, closed[np.maximum(idx, 0)], 0.0)
        den += w
    return num / den


def precompute(m1: pd.DataFrame, tf_minutes: int, P: NyaoParams) -> dict:
    """All signal / health arrays for one timeframe: per TF bar (entry at open) and per M1 bar (management at close)."""
    tf = E.resample(m1, tf_minutes)
    o = tf["open"].to_numpy(float); h = tf["high"].to_numpy(float); l = tf["low"].to_numpy(float); c = tf["close"].to_numpy(float)
    n_tf = len(c)
    ema_f = mt5_ema(c, P.EMAFastPeriod); ema_s = mt5_ema(c, P.EMASlowPeriod)
    rsi, ps, ns = mt5_rsi(c, P.RSIPeriod)
    atr, tr = mt5_atr(h, l, c, P.ATRPeriod)
    tfd = dict(o=o, h=h, l=l, c=c, atr=atr)
    ctx = _context(tfd, P)
    idx = np.arange(n_tf)
    S = P.SlopeLookback if P.SlopeLookback >= 1 else 1
    a_f = 2.0 / (P.EMAFastPeriod + 1); a_s = 2.0 / (P.EMASlowPeriod + 1); nR = P.RSIPeriod; nA = P.ATRPeriod

    # ---- closed-candle scores: candle [0] = bar k itself, context ends at k-1, slope vs EMA[k-S]
    cur = dict(o=o, h=h, l=l, c=c, atr=atr, ema_f=ema_f, ema_s=ema_s, rsi=rsi)
    e_closed = idx - 1
    prev_closed = _shift(ema_f, S)
    closed_buy, _ = _raw_score(P, True, cur, ctx, e_closed, prev_closed)
    closed_sell, _ = _raw_score(P, False, cur, ctx, e_closed, prev_closed)

    # ---- entry at the open of bar k: forming candle = one tick at open[k]; context ends at k-1
    def partial_indicators(pc, ph, pl, j):
        """Forming-candle indicator values given the last closed TF index j and partial OHLC."""
        jj = np.maximum(j, 0)
        cprev = c[jj]
        tr0 = np.maximum(ph, cprev) - np.minimum(pl, cprev)
        drop = _shift(tr, nA - 1)[jj]                     # tr[j-nA+1] leaves the window
        atr0 = atr[jj] + (tr0 - drop) / nA
        ef0 = a_f * pc + (1 - a_f) * ema_f[jj]
        es0 = a_s * pc + (1 - a_s) * ema_s[jj]
        d = pc - cprev
        p0 = (ps[jj] * (nR - 1) + np.maximum(d, 0)) / nR
        n0 = (ns[jj] * (nR - 1) + np.maximum(-d, 0)) / nR
        with np.errstate(divide="ignore", invalid="ignore"):
            rsi0 = np.where(n0 != 0, 100.0 - 100.0 / (1.0 + p0 / n0), np.where(p0 != 0, 100.0, 50.0))
        return dict(atr=atr0, ema_f=ef0, ema_s=es0, rsi=rsi0)

    pi = partial_indicators(o, o, o, idx - 1)
    cur_open = dict(o=o, h=o, l=o, c=o, **pi)
    prev_open = _shift(ema_f, S)                          # [1] = k-1 -> [S] = k-S
    open_buy, _ = _raw_score(P, True, cur_open, ctx, idx - 1, prev_open)
    open_sell, _ = _raw_score(P, False, cur_open, ctx, idx - 1, prev_open)
    N = P.SignalSmoothingCandles
    blend = min(max(P.CurrentCandleBlend, 0.0), 1.0)
    base_open = dict(buy=_smooth_base(closed_buy, idx - 1, N), sell=_smooth_base(closed_sell, idx - 1, N))
    en_buy = np.clip((1 - blend) * base_open["buy"] + blend * open_buy, 0, 10)
    en_sell = np.clip((1 - blend) * base_open["sell"] + blend * open_sell, 0, 10)
    warm = max(P.EMASlowPeriod, P.RSIPeriod, P.ATRPeriod) + P.ATRAvgLookback + P.DirectionalBodyLookback + 10
    en_buy[:warm] = 0; en_sell[:warm] = 0
    en_atr0 = pi["atr"]                                   # forming-candle ATR at the open (spread gate)
    en_atr_closed = _shift(atr, 1)                        # ATR of candle [1] (GetCurrentATR for the R:R stop)

    # ---- per-M1 arrays: forming TF candle at each M1 close
    t_m1 = (m1["time"].astype("int64") // 10**9).to_numpy()
    t_tf = (tf["time"].astype("int64") // 10**9).to_numpy()
    sec = tf_minutes * 60
    k_of = np.searchsorted(t_tf, (t_m1 // sec) * sec, side="right") - 1    # TF bar containing the M1 bar
    is_first = np.ones(len(t_m1), bool); is_first[1:] = k_of[1:] != k_of[:-1]
    j_of = k_of - 1
    m_o = m1["open"].to_numpy(float); m_h = m1["high"].to_numpy(float); m_l = m1["low"].to_numpy(float); m_c = m1["close"].to_numpy(float)
    if tf_minutes == 1:
        p_o, p_h, p_l = m_o, m_h, m_l
    else:
        g = pd.Series(k_of)
        p_o = pd.Series(m_o).groupby(g).transform("first").to_numpy()
        p_h = pd.Series(m_h).groupby(g).cummax().to_numpy()
        p_l = pd.Series(m_l).groupby(g).cummin().to_numpy()
    pm = partial_indicators(m_c, p_h, p_l, j_of)
    cur_m = dict(o=p_o, h=p_h, l=p_l, c=m_c, **pm)
    jj = np.maximum(j_of, 0)
    prev_m = _shift(ema_f, S - 1)[jj]                     # [1] = j -> [S] = j-S+1
    m_buy, _ = _raw_score(P, True, cur_m, ctx, j_of, prev_m)
    m_sell, _ = _raw_score(P, False, cur_m, ctx, j_of, prev_m)
    base_m = dict(buy=_smooth_base(closed_buy, j_of, N), sell=_smooth_base(closed_sell, j_of, N))
    mg_buy = np.clip((1 - blend) * base_m["buy"] + blend * m_buy, 0, 10)
    mg_sell = np.clip((1 - blend) * base_m["sell"] + blend * m_sell, 0, 10)
    # health inputs (blend closed [1] with forming [0]; ATR on the closed candle; swing over bars [2..lookback-1])
    hf = (1 - blend) * ema_f[jj] + blend * pm["ema_f"]
    hs = (1 - blend) * ema_s[jj] + blend * pm["ema_s"]
    hfp = _shift(ema_f, 1)[jj]
    hrsi = (1 - blend) * rsi[jj] + blend * pm["rsi"]
    hatr = atr[jj]
    sw = max(5, P.HealthSwingLookback)
    swlo = _shift(_roll(l, sw - 2, "min"), 2)[jj]
    swhi = _shift(_roll(h, sw - 2, "max"), 2)[jj]
    bad = j_of < warm
    for arr in (mg_buy, mg_sell):
        arr[bad] = 0.0
    return dict(tf_minutes=tf_minutes, n_tf=n_tf, tf_time=t_tf, en_buy=en_buy, en_sell=en_sell, en_atr0=en_atr0,
                en_atr_closed=en_atr_closed, closed_buy=closed_buy, closed_sell=closed_sell, tf_atr=atr,
                k_of=k_of, j_of=j_of, is_first=is_first, mg_buy=mg_buy, mg_sell=mg_sell, atr0=pm["atr"],
                hf=hf, hs=hs, hfp=hfp, hrsi=hrsi, hatr=hatr, swlo=swlo, swhi=swhi, warm=warm)


# --------------------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------------------

def _norm_vol(v: float) -> float:
    v = max(v, LOT_MIN)
    return round(round(v / LOT_STEP) * LOT_STEP, 2)


def simulate(m1: pd.DataFrame, pre: dict, P: NyaoParams, spread_pts: np.ndarray, t_start: int, t_end: int) -> pd.DataFrame:
    """Bar-by-bar simulation on M1 bars between t_start and t_end (epoch s, server time)."""
    tfm = pre["tf_minutes"]
    t = (m1["time"].astype("int64") // 10**9).to_numpy()
    n = len(t)
    k0 = int(np.searchsorted(t, t_start)); k1 = int(np.searchsorted(t, t_end))
    o = m1["open"].to_numpy(float).tolist(); h = m1["high"].to_numpy(float).tolist()
    l = m1["low"].to_numpy(float).tolist(); c = m1["close"].to_numpy(float).tolist()
    spr = (spread_pts * POINT * P.spread_mult).tolist()
    slip = P.slippage_pts * POINT
    tl = t.tolist()
    hours = pd.to_datetime(m1["time"]).dt
    mod = (hours.hour * 60 + hours.minute).to_numpy().tolist()
    dow = hours.dayofweek.to_numpy().tolist()
    k_of = pre["k_of"].tolist(); j_of = pre["j_of"].tolist(); is_first = pre["is_first"].tolist()
    en_buy = pre["en_buy"].tolist(); en_sell = pre["en_sell"].tolist(); en_atr0 = pre["en_atr0"].tolist(); en_atrc = pre["en_atr_closed"].tolist()
    mg_buy = pre["mg_buy"].tolist(); mg_sell = pre["mg_sell"].tolist(); atr0 = pre["atr0"].tolist()
    hf = pre["hf"].tolist(); hs = pre["hs"].tolist(); hfp = pre["hfp"].tolist(); hrsi = pre["hrsi"].tolist(); hatr = pre["hatr"].tolist()
    swlo = pre["swlo"].tolist(); swhi = pre["swhi"].tolist()
    tf_time = pre["tf_time"].tolist()
    tf_sec = tfm * 60
    warm_k = pre["warm"]

    # normalised health weights
    wsum = P.HealthTrendWeight + P.HealthRSIWeight + P.HealthATRWeight + P.HealthSwingWeight
    wT, wR, wA, wS = (P.HealthTrendWeight / wsum, P.HealthRSIWeight / wsum, P.HealthATRWeight / wsum, P.HealthSwingWeight / wsum) if wsum > 0 else (0.4, 0.25, 0.25, 0.1)
    stop_lvl = P.stop_level_pts * POINT
    windows = tuple(P.block_windows)

    balance = float(P.deposit)
    peak_eq = balance; last_peak = balance
    paused = False; pause_end = 0; pause_count = 0; trigger_count = 0
    stopped = False
    consec_loss = 0; cooldown_until = 0
    consec_buy_c = consec_sell_c = 0; buys_bar = sells_bar = 0
    last_buy_price = last_sell_price = 0.0; last_buy_time = last_sell_time = 0
    next_id = 1
    pos: list[dict] = []
    trades: list[dict] = []
    ambiguous = 0
    stats = dict(chains_started=0, hedges_opened=0, rolls=0, reseeds=0, released=0, covered=0, basket_stops=0, dd_pauses=0,
                 health_closes=0, reentries=0, be_locks=0, tightens=0, partials=0, blocked_spread=0, blocked_dup=0,
                 blocked_cooldown=0, blocked_losing=0, blocked_maxopen=0, entries_evaluated=0, dyn_lot_steps=0)

    def fpl(p, bid, ask):
        return (bid - p["entry"]) * p["lot"] * 100.0 if p["side"] == 1 else (p["entry"] - ask) * p["lot"] * 100.0

    def swap_usd(p, t_out):
        nights = E._swap_nights(p["t_in"], t_out)
        return nights * (E.SWAP_LONG_PTS if p["side"] == 1 else E.SWAP_SHORT_PTS) * POINT * p["lot"] * 100.0

    def record(p, price, t_out, reason, lot=None, full=True):
        nonlocal balance
        lot_c = p["lot"] if lot is None else lot
        pnl_px = (price - p["entry"]) if p["side"] == 1 else (p["entry"] - price)
        swap = swap_usd(p, t_out) if full else 0.0
        pnl = pnl_px * lot_c * 100.0 + swap
        balance += pnl
        risk_px = abs(p["entry"] - p["sl0"]) if p["sl0"] else NAN
        trades.append(dict(
            id=p["id"], entry_time=pd.Timestamp(p["t_in"], unit="s"), exit_time=pd.Timestamp(t_out, unit="s"),
            side="BUY" if p["side"] == 1 else "SELL", lot=lot_c, entry=p["entry"], exit=price, initial_sl=p["sl0"],
            risk_px=risk_px, risk_usd=risk_px * lot_c * 100.0 if risk_px == risk_px else NAN,
            pnl_px=pnl_px, pnl=pnl, swap=swap, r_multiple=(pnl_px / risk_px) if risk_px == risk_px and risk_px > 0 else NAN,
            exit_reason=reason, sl_kind=p["sl_kind"], score0=p["score0"], via=p["via"],
            chain=p["chain_ever"], level=p["level"], cycle=p["cycle"], graduated=p["graduated"],
            bars=(t_out - p["t_in"]) / 60.0, max_fav=p["mfe"], max_adv=p["mae"], k_open=p["k_open"],
            atr=p["atr_in"], spread_pts=p["spr_in"], hour=p["hour"], dow=p["dow"], equity_in=p["eq_in"], balance_out=balance,
            full=full,
        ))
        return pnl

    def close_full(p, price, t_out, reason):
        pnl = record(p, price, t_out, reason)
        pos.remove(p)
        process_closed(p, pnl, t_out)

    def process_closed(p, pnl, t_out):
        nonlocal consec_loss, cooldown_until
        if P.EnableSignalDampening:
            if pnl < 0:
                consec_loss += 1
                if P.ConsecutiveLossesBeforeCooldown > 0 and consec_loss >= P.ConsecutiveLossesBeforeCooldown:
                    kk = k_of[min(cur_t, n - 1)]
                    cooldown_until = tf_time[kk] + P.ConsecutiveLossCooldownBars * tf_sec
            else:
                consec_loss = 0
        if P.EnableProfitOffsetSL:
            for q in pos:
                if q is p or q["fpl"] >= 0:
                    continue
                if pnl > 0:
                    q["off_wins"] += 1; q["off_acc"] += pnl
                else:
                    q["off_wins"] = 0; q["off_acc"] = 0.0

    def count_losing():
        return sum(1 for q in pos if q["fpl"] < 0)

    def compute_hedge_lot(older_lot, older_loss, atr):
        lot = 0.0
        if P.HedgeAutoLot:
            pr = P.HedgeRecoveryPct / 100.0
            if pr <= 0:
                pr = 1.0
            target = P.HedgeRecoveryATR * atr
            if target > 0:
                money_per_lot = (target / POINT) * VALUE_PER_POINT_PER_LOT
                if money_per_lot > 0:
                    lot = pr * older_lot + pr * older_loss / money_per_lot
        if lot <= 0:
            lot = older_lot * P.HedgeLotMultiplier
        lot = max(lot, older_lot + LOT_STEP)
        if P.HedgeMaxLot > 0:
            lot = min(lot, P.HedgeMaxLot)
        return _norm_vol(lot)

    def new_pos(side, lot, price, sl, tp, score, tt, k, via, chain=0, level=0, anchor=0.0, cycle=0, eq_in=0.0, ti=None):
        nonlocal next_id
        p = dict(id=next_id, side=side, lot=lot, entry=price, sl=sl, sl0=sl, tp=tp, score0=score, t_in=tt, k_open=k, via=via,
                 be_locked=False, partial_level=0, chain=chain, chain_ever=chain != 0, level=level, anchor=anchor, cycle=cycle,
                 no_rehedge=False, graduated=False, lock_profit=0.0, off_wins=0, off_acc=0.0, sl_kind="initial" if sl else "none", first_level=0.0,
                 mfe=0.0, mae=0.0, fpl=0.0, atr_in=hatr[ti] if ti is not None else NAN, spr_in=spread_pts[ti] * P.spread_mult if ti is not None else NAN,
                 hour=mod[ti] // 60 if ti is not None else -1, dow=dow[ti] if ti is not None else -1, eq_in=eq_in)
        next_id += 1
        pos.append(p)
        return p

    def allowed_to_open(ti, atr_for_gate):
        if stopped or paused:
            return False
        if near_close(ti):
            return False
        if count_losing() >= P.MaxHoldingLossPositions:
            stats["blocked_losing"] += 1; return False
        if len(pos) >= P.MaxOpenOrders or (P.one_position and len(pos) >= 1):
            stats["blocked_maxopen"] += 1; return False
        if P.EnableMaxSpreadFilter:
            sp = spread_pts[ti] * P.spread_mult
            cap = P.MaxSpreadPoints
            if cap <= 0:
                cap = (atr_for_gate / POINT) * P.MaxSpreadATRRatio if atr_for_gate == atr_for_gate and atr_for_gate > 0 else 0
            if cap > 0 and sp > cap:
                stats["blocked_spread"] += 1; return False
        return True

    def near_close(ti):
        if not P.EnableMarketCloseFilter or P.MinutesBeforeClose <= 0:
            return False
        return dow[ti] == 4 and mod[ti] >= (23 * 60 + 55 - P.MinutesBeforeClose)

    def dyn_lot(score, equity, floating_all, ti):
        if not P.EnableDynamicLots:
            return P.BaseLotSize
        lot = P.BaseLotSize
        drop = ((peak_eq - equity) / peak_eq * 100.0) if peak_eq > 0 else 0.0
        in_cd = cooldown_until > 0 and tf_time[k_of[ti]] < cooldown_until
        bleeding = P.EnableBasketStop and floating_all < 0
        steps = 0
        if drop > 0 and P.EquityDropPercent > 0 and score >= P.MinSignalStrengthForLot and not in_cd and not bleeding:
            steps = int(drop / P.EquityDropPercent)
            if P.MaxEquityDropLotSteps > 0:
                steps = min(steps, P.MaxEquityDropLotSteps)
        if steps:
            stats["dyn_lot_steps"] += 1
        lot += steps * P.LotStepSize
        lot = min(max(lot, P.BaseLotSize), P.MaxLotSize)
        return _norm_vol(lot)

    def sl_tp_points(lot, equity, atr_closed):
        """(sl_pts, tp_pts) as the EA resolves them for this lot."""
        vpp = VALUE_PER_POINT_PER_LOT * lot
        if P.EnableRiskReward:
            if P.RRRiskMode == 1:
                slp = (atr_closed / POINT) * P.RRAtrMultiplier if atr_closed == atr_closed and atr_closed > 0 else 0.0
            else:
                slp = _to_points(P.RRRiskInputType, P.RRRiskValue, vpp, equity)
            tpp = slp * P.RiskRewardRatio if slp > 0 and P.RiskRewardRatio > 0 else 0.0
            return slp, tpp
        slp = _to_points(P.SLInputType, P.SLValue, vpp, equity) if P.EnableStopLoss else 0.0
        tpp = _to_points(P.TPInputType, P.TPValue, vpp, equity) if P.EnableTakeProfit else 0.0
        return slp, tpp

    def _to_points(itype, value, vpp, equity):
        if itype == INPUT_POINTS:
            return value
        if itype == INPUT_DOLLAR:
            return value / vpp if vpp > 0 else 0.0
        return (equity * value / 100.0) / vpp if vpp > 0 else 0.0

    def open_market(side, score, ti, bid, ask, via, equity, floating_all, atr_closed, tt, k):
        nonlocal buys_bar, sells_bar, last_buy_price, last_sell_price, last_buy_time, last_sell_time
        lot = dyn_lot(score, equity, floating_all, ti)
        price = (ask + slip) if side == 1 else (bid - slip)
        slp, tpp = sl_tp_points(lot, equity, atr_closed)
        sl = (price - slp * POINT) if (slp > 0 and side == 1) else ((price + slp * POINT) if slp > 0 else 0.0)
        tp = (price + tpp * POINT) if (tpp > 0 and side == 1) else ((price - tpp * POINT) if tpp > 0 else 0.0)
        p = new_pos(side, lot, round(price, 2), round(sl, 2) if sl else 0.0, round(tp, 2) if tp else 0.0, score, tt, k, via, eq_in=equity, ti=ti)
        if side == 1:
            buys_bar += 1; last_buy_price = price; last_buy_time = tt
        else:
            sells_bar += 1; last_sell_price = price; last_sell_time = tt
        return p

    def open_hedge(chain_id, prev_side, lot, level, anchor, cycle, bid, ask, tt, k, ti):
        side = -prev_side
        price = (ask + slip) if side == 1 else (bid - slip)
        p = new_pos(side, lot, round(price, 2), 0.0, 0.0, 0.0, tt, k, "hedge", chain=chain_id, level=level, anchor=anchor, cycle=cycle, eq_in=0.0, ti=ti)
        stats["hedges_opened"] += 1
        return p

    def graduate(p):
        p["chain"] = 0; p["level"] = 0; p["anchor"] = 0.0; p["cycle"] = 0; p["graduated"] = True; p["lock_profit"] = 0.0

    def release_chain(cid):
        for q in pos:
            if q["chain"] == cid:
                q["chain"] = 0; q["level"] = 0; q["anchor"] = 0.0; q["cycle"] = 0; q["no_rehedge"] = True; q["graduated"] = True
        stats["released"] += 1

    def health(p, ti, bid, ask):
        f, s, fp, r, a = hf[ti], hs[ti], hfp[ti], hrsi[ti], hatr[ti]
        buy = p["side"] == 1
        # trend
        aligned = (f > s) if buy else (f < s)
        if aligned:
            sep = min(1.0, abs(f - s) / (a * 0.5)) if a > 0 else 1.0
            slope_f = 0.7 if ((f <= fp) if buy else (f >= fp)) else 1.0
            ts = sep * slope_f
        else:
            ts = 0.0
        # rsi
        if buy:
            fl = P.HealthRSIBuyMin - 15.0
            rs = 1.0 if r >= P.HealthRSIBuyMin else ((r - fl) / (P.HealthRSIBuyMin - fl) if r > fl else 0.0)
        else:
            ce = P.HealthRSISellMax + 15.0
            rs = 1.0 if r <= P.HealthRSISellMax else ((ce - r) / (ce - P.HealthRSISellMax) if r < ce else 0.0)
        # adverse excursion
        cur = bid if buy else ask
        adverse = (p["entry"] - cur) if buy else (cur - p["entry"])
        at = 1.0
        if a > 0 and adverse > 0:
            at = max(0.0, 1.0 - (adverse / a) / P.MaxAdverseATR)
        # swing
        ss = 1.0
        if buy:
            if swlo[ti] == swlo[ti] and cur < swlo[ti]:
                ss = 0.0
        else:
            if swhi[ti] == swhi[ti] and cur > swhi[ti]:
                ss = 0.0
        return ts * wT + rs * wR + at * wA + ss * wS

    def try_reentry(side, score0, ti, bid, ask, tt, k, equity, floating_all):
        if score0 <= 0 or not P.EnableVirtualSLReentry:
            return
        if stopped or paused or near_close(ti):
            return
        if count_losing() >= P.MaxHoldingLossPositions or len(pos) >= P.MaxOpenOrders:
            return
        sc = mg_buy[ti] if side == 1 else mg_sell[ti]
        if sc >= score0 * P.ReentryMinSignalPct:
            if (side == 1 and not P.EnableBuyOrders) or (side == -1 and not P.EnableSellOrders):
                return
            if allowed_to_open(ti, atr0[ti]):
                open_market(side, sc, ti, bid, ask, "reentry", equity, floating_all, hatr[ti], tt, k)
                stats["reentries"] += 1

    cur_t = k0
    for ti in range(k0, k1):
        cur_t = ti
        if stopped and not pos:
            break
        tt = tl[ti]; bo = o[ti]; bh = h[ti]; bl = l[ti]; bc = c[ti]; sp = spr[ti]
        k = k_of[ti]
        if paused and tt >= pause_end:
            paused = False
        # ---------------------------------------------------------------- entries at the open of a new TF bar
        if is_first[ti]:
            consec_buy_c = consec_buy_c + 1 if buys_bar > 0 else 0
            consec_sell_c = consec_sell_c + 1 if sells_bar > 0 else 0
            buys_bar = 0; sells_bar = 0
            if not stopped and not paused and k >= warm_k and not near_close(ti) and not _blocked(mod[ti], windows):
                ask_o = bo + sp
                floating_all = 0.0
                for q in pos:
                    q["fpl"] = fpl(q, bo, ask_o)
                    floating_all += q["fpl"]
                equity = balance + floating_all
                stats["entries_evaluated"] += 1

                def signal(side):
                    buy = side == 1
                    if (buy and not P.EnableBuyOrders) or ((not buy) and not P.EnableSellOrders):
                        return 0.0
                    same_bar = buys_bar if buy else sells_bar
                    opp_bar = sells_bar if buy else buys_bar
                    if P.MaxTradesPerCandle > 0 and same_bar >= P.MaxTradesPerCandle:
                        return 0.0
                    if opp_bar > 0:
                        return 0.0
                    losing_same = sum(1 for q in pos if q["side"] == side and q["fpl"] < 0)
                    if P.EnableSignalDampening and losing_same >= P.MaxLosingPositionsSameDir:
                        stats["blocked_losing"] += 1; return 0.0
                    if P.EnableSignalDampening and cooldown_until > 0:
                        if tf_time[k] < cooldown_until:
                            stats["blocked_cooldown"] += 1; return 0.0
                    price = ask_o if buy else bo
                    last_price = last_buy_price if buy else last_sell_price
                    last_time = last_buy_time if buy else last_sell_time
                    if last_time > 0 and any(q["side"] == side for q in pos):
                        mind = P.ZonePoints * POINT * (P.BuyDuplicateMultiplier if buy else P.SellDuplicateMultiplier)
                        if abs(price - last_price) < mind:
                            stats["blocked_dup"] += 1; return 0.0
                    sc = en_buy[k] if buy else en_sell[k]
                    thr = P.MinBuySignalScore if buy else P.MinSellSignalScore
                    cc = consec_buy_c if buy else consec_sell_c
                    if cc > 0 and P.ConsecutiveCandleThresholdBoost > 0:
                        bc_ = cc if P.MaxConsecutiveCandleBoosts <= 0 else min(cc, P.MaxConsecutiveCandleBoosts)
                        thr += bc_ * P.ConsecutiveCandleThresholdBoost
                    if P.EnableSignalDampening:
                        if losing_same > 0:
                            sc -= losing_same * P.LosingPosScorePenalty
                        if peak_eq > 0 and (peak_eq - equity) / peak_eq * 100.0 >= P.DrawdownThresholdPct:
                            thr += P.DrawdownScoreBoost
                    return sc if sc >= thr else 0.0

                b = signal(1); s = signal(-1)
                if b > s or s > b:
                    side = 1 if b > s else -1
                    if allowed_to_open(ti, en_atr0[k]):
                        open_market(side, max(b, s), ti, bo, ask_o, "signal", equity, floating_all, en_atrc[k], tt, k)
            elif cooldown_until > 0 and tf_time[k] >= cooldown_until:
                cooldown_until = 0
        # ---------------------------------------------------------------- intrabar stop / target checks
        if pos:
            ask_h = bh + sp; ask_l = bl + sp; ask_o = bo + sp
            for p in list(pos):
                side = p["side"]; sl = p["sl"]; tp = p["tp"]
                hit_sl = hit_tp = False; px = 0.0
                if sl:
                    if side == 1 and bl <= sl:
                        hit_sl = True; px = (bo if bo <= sl else sl) - slip
                    elif side == -1 and ask_h >= sl:
                        hit_sl = True; px = (ask_o if ask_o >= sl else sl) + slip
                if tp and not hit_sl:
                    if side == 1 and bh >= tp:
                        hit_tp = True; px = bo if bo >= tp else tp
                    elif side == -1 and ask_l <= tp:
                        hit_tp = True; px = ask_o if ask_o <= tp else tp
                if tp and sl and hit_sl and ((side == 1 and bh >= tp) or (side == -1 and ask_l <= tp)):
                    ambiguous += 1
                # excursions
                fav = (bh - p["entry"]) if side == 1 else (p["entry"] - ask_l)
                adv = (p["entry"] - bl) if side == 1 else (ask_h - p["entry"])
                if fav > p["mfe"]: p["mfe"] = fav
                if adv > p["mae"]: p["mae"] = adv
                if hit_sl:
                    reason = "SL_gap" if ((side == 1 and bo <= sl) or (side == -1 and ask_o >= sl)) else ("SL" if p["sl_kind"] == "initial" else "SL_" + p["sl_kind"])
                    if P.trail_mode == "calib" and p["sl_kind"] == "trail" and p["first_level"] and reason == "SL_trail":
                        fl_ = p["first_level"]
                        px = fl_ + P.trail_lambda_sl * (sl - fl_)
                        px = (max(px, bl) if side == 1 else min(px, ask_h)) - (slip if side == 1 else -slip)
                    close_full(p, round(px, 2), tt + 60, reason)
                elif hit_tp:
                    close_full(p, round(px, 2), tt + 60, "TP")
        # ---------------------------------------------------------------- bar-close management
        t_close = tt + 60
        ask_c = bc + sp
        floating_all = 0.0; floating_basket = 0.0
        for q in pos:
            q["fpl"] = fpl(q, bc, ask_c)
            floating_all += q["fpl"]
            if q["chain"] == 0:
                floating_basket += q["fpl"]
        equity = balance + floating_all
        if equity > peak_eq:
            peak_eq = equity; last_peak = equity
            if P.ResetOnNewPeak:
                trigger_count = 0
            if paused:
                paused = False
        if not stopped and P.MinimumEquity > 0 and equity <= P.MinimumEquity:
            for p in list(pos):
                close_full(p, bc if p["side"] == 1 else ask_c, t_close, "MIN_EQUITY")
            stopped = True
        if not stopped and pos and P.MinEquityPercent > 0:
            dd_allowed = last_peak * ((100.0 - P.MinEquityPercent) / 100.0)
            if P.MaxDrawdownFromPeak > 0:
                dd_allowed = min(dd_allowed, P.MaxDrawdownFromPeak)
            if equity < last_peak - dd_allowed and not paused:
                trigger_count += 1
                if P.MaxMinEquityTriggers > 0 and trigger_count > P.MaxMinEquityTriggers:
                    for p in list(pos):
                        close_full(p, bc if p["side"] == 1 else ask_c, t_close, "MAX_TRIGGERS")
                    stopped = True
                else:
                    paused = True; pause_count += 1; stats["dd_pauses"] += 1
                    dur = P.PauseMinutes * (P.PauseMinutesMultiplier ** min(trigger_count - 1, 60))
                    if P.MaxPauseMinutes > 0:
                        dur = min(dur, P.MaxPauseMinutes)
                    pause_end = t_close + int(dur * 60)
                    last_peak = balance
            if P.EnableBasketStop and P.MaxBasketLossPct > 0 and equity > 0 and floating_basket < 0:
                if (-floating_basket / equity) * 100.0 >= P.MaxBasketLossPct:
                    for p in list(pos):
                        if p["chain"] == 0:
                            close_full(p, bc if p["side"] == 1 else ask_c, t_close, "BASKET")
                    stats["basket_stops"] += 1
                    if not paused:
                        paused = True
                        pause_end = t_close + int((min(P.PauseMinutes, P.MaxPauseMinutes) if P.MaxPauseMinutes > 0 else P.PauseMinutes) * 60)
        if stopped or not pos:
            continue
        atr = hatr[ti]
        # ---- hedge chains
        if P.EnableHedgeChain and atr == atr and atr > 0:
            chain_ids = []
            for q in pos:
                if q["chain"] and q["chain"] not in chain_ids:
                    chain_ids.append(q["chain"])
            for cid in chain_ids:
                legs = [q for q in pos if q["chain"] == cid]
                if not legs:
                    continue
                if len(legs) == 1:
                    graduate(legs[0]); continue
                older = min(legs, key=lambda q: q["level"]); hedge = max(legs, key=lambda q: q["level"])
                older_pl = older["fpl"]; hedge_pl = hedge["fpl"]; total = sum(q["fpl"] for q in legs)
                anchor = max((q["anchor"] for q in legs), default=0.0); cycle = hedge["cycle"]
                if older_pl < 0:
                    cover = (P.HedgeRecoveryPct / 100.0) * (-older_pl)
                    if hedge_pl >= cover:
                        close_full(older, bc if older["side"] == 1 else ask_c, t_close, "CHAIN_COVERED")
                        graduate(hedge); hedge["lock_profit"] = cover; stats["covered"] += 1
                        continue
                if hedge_pl < 0 and older_pl >= P.HedgeRollMinProfit:
                    level_ok = hedge["level"] < P.HedgeCycleLevels
                    new_lot = compute_hedge_lot(hedge["lot"], -hedge_pl, atr) if level_ok else 0.0
                    if level_ok and new_lot > hedge["lot"]:
                        close_full(older, bc if older["side"] == 1 else ask_c, t_close, "CHAIN_ROLL")
                        open_hedge(cid, hedge["side"], new_lot, hedge["level"] + 1, anchor, cycle, bc, ask_c, t_close, k, ti)
                        stats["rolls"] += 1
                        continue
                    cycles_left = P.HedgeMaxCycles <= 0 or cycle + 1 < P.HedgeMaxCycles
                    if P.EnableHedgeCycleReset and cycles_left:
                        # reseed: partial-close the hedge, close the older leg, hedge becomes the root of a new cycle
                        lot_h = hedge["lot"]
                        close_vol = math.floor((lot_h * P.HedgeCyclePartialPct / 100.0) / LOT_STEP) * LOT_STEP
                        remaining = lot_h - close_vol
                        if remaining < LOT_MIN:
                            close_vol = math.floor((lot_h - LOT_MIN) / LOT_STEP) * LOT_STEP; remaining = lot_h - close_vol
                        if close_vol < LOT_MIN - 1e-9 or remaining < LOT_MIN - 1e-9:
                            release_chain(cid); continue
                        record(hedge, bc if hedge["side"] == 1 else ask_c, t_close, "CHAIN_RESEED_PARTIAL", lot=round(close_vol, 2), full=False)
                        hedge["lot"] = round(remaining, 2)
                        close_full(older, bc if older["side"] == 1 else ask_c, t_close, "CHAIN_RESEED")
                        hedge["fpl"] = fpl(hedge, bc, ask_c)
                        new_anchor = -hedge["fpl"] if hedge["fpl"] < 0 else 0.01
                        hedge["chain"] = hedge["id"]; hedge["level"] = 0; hedge["anchor"] = new_anchor; hedge["cycle"] = cycle + 1
                        h_lot = compute_hedge_lot(hedge["lot"], new_anchor, atr)
                        if h_lot > hedge["lot"]:
                            open_hedge(hedge["id"], hedge["side"], h_lot, 1, new_anchor, cycle + 1, bc, ask_c, t_close, k, ti)
                        stats["reseeds"] += 1
                        continue
                    release_chain(cid); continue
                thr_usd = P.HedgeMaxChainLossUSD if P.HedgeMaxChainLossUSD > 0 else 0.0
                thr_pct = equity * P.HedgeMaxChainLossPct / 100.0 if P.HedgeMaxChainLossPct > 0 else 0.0
                thr = min(thr_usd, thr_pct) if (thr_usd > 0 and thr_pct > 0) else max(thr_usd, thr_pct)
                if thr > 0 and total <= -thr:
                    for q in legs:
                        close_full(q, bc if q["side"] == 1 else ask_c, t_close, "CHAIN_STOP")
            # phase B: start chains
            for p in list(pos):
                if p["chain"] or p["no_rehedge"] or p["fpl"] >= 0:
                    continue
                adverse = (p["entry"] - bc) if p["side"] == 1 else (ask_c - p["entry"])
                if adverse <= 0 or adverse / atr < P.HedgeTriggerATR:
                    continue
                if P.HedgeRequireSignal:
                    rev = mg_sell[ti] if p["side"] == 1 else mg_buy[ti]
                    if rev < P.HedgeMinSignalScore:
                        continue
                anchor = -p["fpl"]
                h_lot = compute_hedge_lot(p["lot"], anchor, atr)
                if h_lot <= p["lot"]:
                    continue
                p["chain"] = p["id"]; p["chain_ever"] = True; p["level"] = 0; p["anchor"] = anchor; p["cycle"] = 0; p["graduated"] = False; p["lock_profit"] = 0.0
                if P.HedgeClearRootSL and p["sl"]:
                    p["sl"] = 0.0; p["sl_kind"] = "cleared"
                open_hedge(p["id"], p["side"], h_lot, 1, anchor, 0, bc, ask_c, t_close, k, ti)
                stats["chains_started"] += 1
        # ---- trailing (skip active chain legs)
        if P.EnableTrailing:
            for p in list(pos):
                if p["chain"]:
                    continue
                side = p["side"]; lot = p["lot"]; entry = p["entry"]
                ref = bh if side == 1 else (bl + sp)                 # best price in the bar
                cur_px = bc if side == 1 else ask_c
                score = mg_buy[ti] if side == 1 else mg_sell[ti]
                delta = (score - p["score0"]) if p["score0"] > 0 else 0.0
                sl_adj = delta * P.TrailingValueMultiplier if (P.EnableAdaptiveSL and p["score0"] > 0) else 0.0
                profit_ref = (ref - entry) * lot * 100.0 if side == 1 else (entry - ref) * lot * 100.0
                threshold = P.MinBreakEvenProfit * P.ProfitThresholdMultiplier
                can = (P.MinBreakEvenProfit <= 0) or (not P.TrailingSLOnProfitableOnly) or profit_ref >= threshold
                new_sl = None
                prev_sl = p["sl"]
                if can:
                    dist_usd = max(P.TrailingDistanceValue + sl_adj, P.TrailingValueMultiplier * 0.1)
                    if p["graduated"] and P.HedgeTrailATR > 0 and atr == atr and atr > 0:
                        dist_px = P.HedgeTrailATR * atr
                    elif P.TSInputType == INPUT_POINTS:
                        dist_px = dist_usd * POINT
                    else:
                        dist_px = (dist_usd / (VALUE_PER_POINT_PER_LOT * lot)) * POINT
                    min_profit_px = (P.MinBreakEvenProfit / (VALUE_PER_POINT_PER_LOT * lot)) * POINT if P.MinBreakEvenProfit > 0 else 0.0
                    be = (entry + sp + min_profit_px) if side == 1 else (entry - sp - min_profit_px)
                    if side == 1:
                        if (ref - entry) >= dist_px:
                            calc = min(ref - dist_px, ref - stop_lvl)
                            if P.TrailingEnableBreakEvenLock and calc < be:
                                calc = be
                            if (prev_sl == 0 or calc > prev_sl) and calc < ref:
                                new_sl = calc
                    else:
                        if (entry - ref) >= dist_px:
                            calc = max(ref + dist_px, ref + stop_lvl)
                            if P.TrailingEnableBreakEvenLock and calc > be:
                                calc = be
                            if (prev_sl == 0 or calc < prev_sl) and calc > ref:
                                new_sl = calc
                    first_level = prev_sl if (prev_sl and p["sl_kind"] in ("trail", "hedge_lock")) else be
                else:
                    first_level = prev_sl if prev_sl else None
                if p["lock_profit"] > 0:
                    lock_px = (p["lock_profit"] / (VALUE_PER_POINT_PER_LOT * lot)) * POINT
                    base_sl = new_sl if new_sl is not None else prev_sl
                    if side == 1:
                        lp = entry + lock_px
                        if lp > base_sl and lp < bc:
                            new_sl = lp; p["sl_kind"] = "hedge_lock"
                    else:
                        lp = entry - lock_px
                        if (base_sl == 0 or lp < base_sl) and lp > ask_c:
                            new_sl = lp; p["sl_kind"] = "hedge_lock"
                if new_sl is None:
                    continue
                new_sl = round(new_sl, 2)
                if abs(new_sl - prev_sl) < POINT:
                    continue
                if p["sl_kind"] != "hedge_lock":
                    p["sl_kind"] = "trail"
                if not p["first_level"] and first_level is not None:
                    p["first_level"] = first_level
                p["sl"] = new_sl
                # did the price retreat through the trailed stop inside this bar?
                if side == 1 and new_sl > cur_px:
                    worst = max(bl, min(first_level, new_sl)) if first_level is not None else new_sl
                    if P.trail_mode == "worst":
                        px = worst
                    elif P.trail_mode == "calib":
                        px = worst + P.trail_lambda * (new_sl - worst)
                    else:
                        px = new_sl
                    close_full(p, round(px - slip, 2), t_close, "TRAIL")
                elif side == -1 and new_sl < cur_px:
                    worst = min(bh + sp, max(first_level, new_sl)) if first_level is not None else new_sl
                    if P.trail_mode == "worst":
                        px = worst
                    elif P.trail_mode == "calib":
                        px = worst + P.trail_lambda * (new_sl - worst)
                    else:
                        px = new_sl
                    close_full(p, round(px + slip, 2), t_close, "TRAIL")
        # ---- loss management (skip active chain legs)
        if P.EnableLossManagement and pos:
            k_forming = k
            for p in list(pos):
                if p["chain"]:
                    continue
                if P.HealthGraceBars > 0 and (k_forming - p["k_open"]) < P.HealthGraceBars:
                    continue
                side = p["side"]; lot = p["lot"]; entry = p["entry"]
                cur_px = bc if side == 1 else ask_c
                profit = p["fpl"] = fpl(p, bc, ask_c)
                hsc = health(p, ti, bc, ask_c)
                # 1 break-even on spread
                if P.EnableBreakEvenOnSpread and not p["be_locked"]:
                    spread_cost = sp * lot * 100.0
                    if profit > spread_cost * P.BreakEvenSpreadMultiplier:
                        be_sl = entry
                        ok = (be_sl < bc - stop_lvl and (p["sl"] == 0 or be_sl > p["sl"])) if side == 1 else (be_sl > ask_c + stop_lvl and (p["sl"] == 0 or be_sl < p["sl"]))
                        if ok:
                            p["sl"] = be_sl; p["be_locked"] = True; p["sl_kind"] = "be"; stats["be_locks"] += 1
                # 2 scaled partial close on signal decay
                if P.EnablePartialClose and p["score0"] > 0 and p["partial_level"] < 3:
                    score = mg_buy[ti] if side == 1 else mg_sell[ti]
                    ratio = score / p["score0"]
                    lvl = p["partial_level"]
                    if lvl == 0 and ratio <= 0.75:
                        cv = _norm_vol(lot * P.PartialClose75Pct); rem = lot - cv
                        if cv >= LOT_MIN and rem >= LOT_MIN - 1e-9:
                            record(p, cur_px, t_close, "PARTIAL_L1", lot=cv, full=False); p["lot"] = round(rem, 2); p["partial_level"] = 1; stats["partials"] += 1
                    elif lvl == 1 and ratio <= 0.50:
                        cv = _norm_vol(p["lot"] * P.PartialClose50Pct); rem = p["lot"] - cv
                        if cv >= LOT_MIN and rem >= LOT_MIN - 1e-9:
                            record(p, cur_px, t_close, "PARTIAL_L2", lot=cv, full=False); p["lot"] = round(rem, 2); p["partial_level"] = 2; stats["partials"] += 1
                    elif lvl == 2 and ratio <= 0.25:
                        p["partial_level"] = 3
                        close_full(p, cur_px, t_close, "PARTIAL_L3")
                        try_reentry(side, p["score0"], ti, bc, ask_c, t_close, k, equity, floating_all)
                        continue
                lot = p["lot"]
                # 3 health-based stop tightening
                if P.EnableHealthSLTightening and hsc < P.SLTightenMinHealthPct and atr == atr and atr > 0:
                    hr = max(hsc / P.SLTightenMinHealthPct, 0.1)
                    dist = atr * P.SLTightenATRMultiplier * hr
                    if side == 1:
                        ns_ = round(bc - dist, 2)
                        if p["be_locked"] and ns_ < entry:
                            ns_ = entry
                        if not (p["sl"] > 0 and ns_ <= p["sl"]) and ns_ < bc - stop_lvl:
                            p["sl"] = ns_; p["sl_kind"] = "tight"; stats["tightens"] += 1
                    else:
                        ns_ = round(ask_c + dist, 2)
                        if p["be_locked"] and ns_ > entry:
                            ns_ = entry
                        if not (p["sl"] > 0 and ns_ >= p["sl"]) and ns_ > ask_c + stop_lvl:
                            p["sl"] = ns_; p["sl_kind"] = "tight"; stats["tightens"] += 1
                # 4 profit-offset stop
                if (P.EnableProfitOffsetSL and profit < 0 and p["off_wins"] >= P.ConsecutiveWinsRequired
                        and p["off_acc"] >= P.MinOffsetProfit and p["sl0"] > 0):
                    orig_risk = abs(entry - p["sl0"]) / POINT * VALUE_PER_POINT_PER_LOT * lot
                    new_risk = orig_risk - p["off_acc"]
                    if 0 < new_risk < orig_risk:
                        dpx = (new_risk / (VALUE_PER_POINT_PER_LOT * lot)) * POINT
                        if side == 1:
                            ns_ = round(entry - dpx, 2)
                            if p["be_locked"] and ns_ < entry:
                                ns_ = entry
                            if not (p["sl"] > 0 and ns_ <= p["sl"]) and ns_ < bc - stop_lvl:
                                p["sl"] = ns_; p["sl_kind"] = "offset"
                        else:
                            ns_ = round(entry + dpx, 2)
                            if p["be_locked"] and ns_ > entry:
                                ns_ = entry
                            if not (p["sl"] > 0 and ns_ >= p["sl"]) and ns_ > ask_c + stop_lvl:
                                p["sl"] = ns_; p["sl_kind"] = "offset"
                    elif new_risk <= 0:
                        ok = (entry < bc - stop_lvl and (p["sl"] == 0 or entry > p["sl"])) if side == 1 else (entry > ask_c + stop_lvl and (p["sl"] == 0 or entry < p["sl"]))
                        if ok:
                            p["sl"] = entry; p["be_locked"] = True; p["sl_kind"] = "offset_be"
                # 5 health-decay close + virtual-SL re-entry
                if hsc < P.MinHealthScore:
                    close_full(p, cur_px, t_close, "HEALTH"); stats["health_closes"] += 1
                    try_reentry(side, p["score0"], ti, bc, ask_c, t_close, k, equity, floating_all)
    # end of data: close everything at the last close
    if pos:
        ti = min(k1, n) - 1
        for p in list(pos):
            close_full(p, c[ti] if p["side"] == 1 else c[ti] + spr[ti], tl[ti] + 60, "END")
    tr = pd.DataFrame(trades)
    if len(tr):
        tr = tr.sort_values(["exit_time", "id"]).reset_index(drop=True)
    tr.attrs["ambiguous_bars"] = ambiguous
    tr.attrs["final_balance"] = balance
    tr.attrs["stats"] = stats
    tr.attrs["stopped"] = stopped
    return tr


def _blocked(minute_of_day: int, windows) -> bool:
    for a, b in windows:
        if a <= minute_of_day < b:
            return True
    return False


# --------------------------------------------------------------------------------------
# Convenience
# --------------------------------------------------------------------------------------

_PRE_CACHE: dict = {}


def get_pre(m1: pd.DataFrame, tf: int, P: NyaoParams) -> dict:
    key = signal_key(P, tf)
    if key not in _PRE_CACHE:
        if len(_PRE_CACHE) >= 6:
            _PRE_CACHE.pop(next(iter(_PRE_CACHE)))
        _PRE_CACHE[key] = precompute(m1, tf, P)
    return _PRE_CACHE[key]


def run(m1: pd.DataFrame, spread: np.ndarray, tf: int, P: NyaoParams, t_start: int, t_end: int) -> pd.DataFrame:
    return simulate(m1, get_pre(m1, tf, P), P, spread, t_start, t_end)
