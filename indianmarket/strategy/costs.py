"""Indian index-futures cost model for the SimpleSMA18Bot research (NIFTY 50 / NIFTY BANK).

The engine works in index points per unit and already applies the bid/ask spread and the per-side slippage of a scenario
through the fills. Everything that depends on turnover (statutory and exchange charges, brokerage) is added here per trade.

Scenarios (all assumptions are explicit; change them here and re-run):
  A gross     spread 0, slippage 0, no charges                           -> "does the signal make points at all?"
  B realistic spread and slippage of a liquid futures contract + charges -> the number to judge tradability on
  C stress    3x slippage, wider spread, charges x1.25                   -> execution degradation

Charges (NSE index futures, discount broker, rates in force since 1 Oct 2024, applied to the whole period):
  brokerage Rs 20 per executed order (entry, exit and every partial exit count as orders)
  STT 0.02% of the SELL-side notional
  NSE transaction charge 0.00173% of the notional on both sides
  SEBI turnover fee 0.0001% (Rs 10 per crore) on both sides
  stamp duty 0.002% of the BUY-side notional
  GST 18% on brokerage + transaction charge + SEBI fee
Lot sizes are the contract multipliers used to turn points into rupees; results are reported per unit and per lot, so a
later lot-size revision only rescales the rupee columns (and the Rs 40 of brokerage per lot).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TICK = 0.05
INSTR = {
    "nifty50": dict(name="NIFTY 50", lot=75, capital_per_lot=250000.0,
                    B=dict(spread_pts=0.10, slip_pts=0.5), C=dict(spread_pts=0.20, slip_pts=1.5)),
    "banknifty": dict(name="NIFTY BANK", lot=35, capital_per_lot=250000.0,
                      B=dict(spread_pts=0.30, slip_pts=1.5), C=dict(spread_pts=0.60, slip_pts=4.5)),
}
CHARGES = dict(brokerage_per_order=20.0, stt_sell=0.0002, exchange=0.0000173, sebi=0.000001, stamp_buy=0.00002, gst=0.18)
SCENARIOS = ("A", "B", "C")


def engine_costs(instr: str, scenario: str) -> dict:
    """Params fields for the engine: spread and slippage in ticks."""
    if scenario == "A":
        return dict(spread_fixed_pts=0.0, slippage_pts=0.0)
    c = INSTR[instr][scenario]
    return dict(spread_fixed_pts=round(c["spread_pts"] / TICK, 6), slippage_pts=round(c["slip_pts"] / TICK, 6))


def fees_per_lot(entry: np.ndarray, exit_: np.ndarray, side: np.ndarray, lot: int, n_orders: int = 2, mult: float = 1.0) -> np.ndarray:
    """Rupees of charges for one round trip of one lot (entry and exit legs)."""
    buy_px = np.where(side == 1, entry, exit_); sell_px = np.where(side == 1, exit_, entry)
    buy_n = buy_px * lot; sell_n = sell_px * lot
    brok = CHARGES["brokerage_per_order"] * n_orders
    stt = CHARGES["stt_sell"] * sell_n
    exch = CHARGES["exchange"] * (buy_n + sell_n)
    sebi = CHARGES["sebi"] * (buy_n + sell_n)
    stamp = CHARGES["stamp_buy"] * buy_n
    gst = CHARGES["gst"] * (brok + exch + sebi)
    return (brok + stt + exch + sebi + stamp + gst) * mult


def apply_costs(tr: pd.DataFrame, instr: str, scenario: str) -> pd.DataFrame:
    """Add rupee columns per lot. `pts` from the engine already contains spread and slippage of the scenario."""
    tr = tr.copy(); lot = INSTR[instr]["lot"]
    if len(tr) == 0:
        for c in ("fees_rs", "fees_pts", "pts_net", "rs_gross", "rs_net", "r_net"):
            tr[c] = pd.Series(dtype=float)
        return tr
    if scenario == "A":
        tr["fees_rs"] = 0.0
    else:
        tr["fees_rs"] = fees_per_lot(tr["entry"].to_numpy(), tr["exit"].to_numpy(), tr["side"].to_numpy(), lot, 2, 1.25 if scenario == "C" else 1.0)
    tr["fees_pts"] = tr["fees_rs"] / lot
    tr["pts_net"] = tr["pts"] - tr["fees_pts"]
    tr["rs_gross"] = tr["pts"] * lot
    tr["rs_net"] = tr["pts_net"] * lot
    risk_pts = tr["risk_usd"] / tr["lots"]                    # engine risk in points per unit
    tr["r_net"] = np.where(risk_pts > 0, tr["pts_net"] / risk_pts, np.nan)
    return tr


def describe() -> str:
    lines = ["| Scenario | NIFTY 50 | NIFTY BANK |", "|---|---|---|",
             "| A gross | spread 0, slippage 0, no charges | same |"]
    for sc in ("B", "C"):
        a = INSTR["nifty50"][sc]; b = INSTR["banknifty"][sc]
        lines.append(f"| {sc} {'realistic' if sc == 'B' else 'stress'} | spread {a['spread_pts']} pts, slippage {a['slip_pts']} pts/side, charges{' x1.25' if sc == 'C' else ''} | spread {b['spread_pts']} pts, slippage {b['slip_pts']} pts/side, charges{' x1.25' if sc == 'C' else ''} |")
    for k, v in INSTR.items():
        px = 24000.0 if k == "nifty50" else 54000.0
        f = float(fees_per_lot(np.array([px]), np.array([px]), np.array([1]), v["lot"])[0])
        lines.append(f"\nCharges per round trip at {v['name']} = {px:,.0f}: Rs {f:,.0f} per lot of {v['lot']} = {f / v['lot']:.2f} index points.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
