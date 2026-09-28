"""Shared runner: detect structures -> simulate a playbook under a cost model."""
import json
import os
import numpy as np
import pandas as pd

from .data import build, CACHE, SPLITS
from .structure import detect, prepare, BASELINE
from .engine import Path, simulate, summarize, COSTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
PLAYBOOKS = {"A_pingpong": ["pingpong"], "B1_pullback": ["breakout_pullback"], "B2_immediate": ["breakout_immediate"]}

_cache = {}


def load_all():
    if "m1" not in _cache:
        m1, _ = build()
        m15 = pd.read_pickle(os.path.join(CACHE, "m15_va.pkl"))
        _cache["m1"] = m1; _cache["m15"] = m15; _cache["path"] = Path(m1)
    return _cache["m1"], _cache["m15"], _cache["path"]


def run(P: dict = None, playbook: str = "A_pingpong", cost: str = "real", m15=None, signal_filter=None,
        one_position: bool = True):
    m1, m15_all, path = load_all()
    m15 = m15_all if m15 is None else m15
    P = {**BASELINE, **(P or {})}
    key = json.dumps({k: P[k] for k in P if k not in ("max_hold_bars",)}, sort_keys=True)
    if key not in _cache:
        if len(_cache) > 40:
            for k in [k for k in _cache if k.startswith("{")][:20]:
                _cache.pop(k)
        st, sg, _ = detect(m15, P)
        _cache[key] = (st, sg)
    st, sg = _cache[key]
    if signal_filter is not None:
        sg = sg[signal_filter(sg)]
    tr = simulate(sg, path, m15, COSTS[cost], P, one_position=one_position, playbook=PLAYBOOKS[playbook])
    return st, sg, tr


def period_table(tr: pd.DataFrame, col="r_net"):
    rows = []
    for name, _, _ in SPLITS:
        s = summarize(tr[tr["period"] == name], col)
        s["period"] = name
        rows.append(s)
    s = summarize(tr, col); s["period"] = "ALL"; rows.append(s)
    cols = ["period", "n", "win_rate", "expectancy", "pf", "total_r", "max_dd_r", "max_loss_streak", "ci_lo", "ci_hi"]
    return pd.DataFrame(rows)[[c for c in cols if c in rows[0] or c == "period"]]


def fmt(df: pd.DataFrame) -> str:
    return df.to_string(index=False, float_format=lambda x: f"{x:.3f}")
