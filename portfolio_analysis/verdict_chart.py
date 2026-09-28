# -*- coding: utf-8 -*-
"""KEEP / TRIM / EXIT verdict charts. Light surface, sized for A4 landscape."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import data
import verdicts as VD

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(OUT, exist_ok=True)

SURFACE = "#fcfcfb"
INK     = "#0b0b0b"
INK2    = "#52514e"
MUTED   = "#898781"
GRID    = "#e1e0d9"
AXIS    = "#c3c2b7"
# status palette - fixed, never themed; always paired with a word, never colour alone
KEEP_C  = "#0ca30c"
TRIM_C  = "#fab219"
EXIT_C  = "#d03b3b"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
})

RUPEE = "₹"
ORDER = ["KEEP", "TRIM", "EXIT"]
COLOR  = {"KEEP": KEEP_C, "TRIM": TRIM_C, "EXIT": EXIT_C}
TEXTC  = {"KEEP": "#006300", "TRIM": "#8a5d00", "EXIT": EXIT_C}
ONFILL = {"KEEP": "#ffffff", "TRIM": "#3d2900", "EXIT": "#ffffff"}
MARK   = {"KEEP": "●", "TRIM": "▲", "EXIT": "✕"}
HEAD   = {
    "KEEP": "KEEP  —  hold, or add to these",
    "TRIM": "TRIM  —  good business, wrong size or wrong price",
    "EXIT": "EXIT  —  sell out completely",
}

ROWS = {r["ticker"]: r for r in data.rows()}
TOT = sum(r["value"] for r in data.rows())


def group_for(v):
    items = [ROWS[t] for t in VD.VERDICT if VD.VERDICT[t] == v]
    items.sort(key=lambda r: -r["value"])
    return items


def money_in(v):
    return sum(r["value"] for r in group_for(v))


def chart(which, fname, headline, sub):
    groups = [(v, group_for(v)) for v in which]
    n_rows = sum(len(g[1]) for g in groups)
    total_slots = n_rows + len(groups) * 2

    fig_h = 0.315 * total_slots + 1.25
    fig, ax = plt.subplots(figsize=(10.4, fig_h))

    XMAX = 392000.0
    TEXT_X = 148000.0   # reason column
    CUT_X = 138000.0    # right edge of the "cut to x%" tag

    y = total_slots
    yticks, ylabels, tickcols = [], [], []

    for verdict, items in groups:
        amt = sum(r["value"] for r in items)
        if verdict == "EXIT":
            freed = amt
        elif verdict == "TRIM":
            freed = sum(r["value"] - VD.TARGET[r["ticker"]] / 100.0 * TOT for r in items)
        else:
            freed = 0.0
        ax.text(0, y + 0.20, MARK[verdict] + "  " + HEAD[verdict],
                fontsize=10.0, color=TEXTC[verdict], weight="bold", va="center")
        if verdict == "KEEP":
            tail = (RUPEE + "{:,.0f}".format(amt) +
                    "   ·   {:.1f}% of portfolio".format(100.0 * amt / TOT))
        else:
            tail = (RUPEE + "{:,.0f}".format(freed) + " to sell" +
                    "   ·   {:.1f}% of portfolio".format(100.0 * freed / TOT))
        ax.text(XMAX, y + 0.20,
                tail + "   ·   {} holding{}".format(len(items), "" if len(items) == 1 else "s"),
                fontsize=8.6, color=INK2, ha="right", va="center", weight="bold")
        y -= 1.20

        for r in items:
            ax.barh(y, r["value"], height=0.60, color=COLOR[verdict], zorder=3)
            if r["value"] > 70000:
                ax.text(r["value"] - 2600, y, RUPEE + "{:,.0f}".format(r["value"]),
                        va="center", ha="right", fontsize=7.2,
                        color=ONFILL[verdict], weight="bold", zorder=4)
            else:
                ax.text(r["value"] + 2600, y, RUPEE + "{:,.0f}".format(r["value"]),
                        va="center", fontsize=7.2, color=INK2)
            if verdict == "TRIM":
                ax.text(CUT_X, y,
                        "cut to {:.1f}%".format(VD.TARGET[r["ticker"]]),
                        va="center", ha="right", fontsize=7.4,
                        color=TEXTC[verdict], weight="bold")
            ax.text(TEXT_X, y, VD.REASON[r["ticker"]], va="center",
                    fontsize=8.0, color=INK2)
            yticks.append(y)
            ylabels.append(r["ticker"])
            tickcols.append(TEXTC[verdict])
            y -= 1.0
        y -= 0.80

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=8.0)
    for lbl, c in zip(ax.get_yticklabels(), tickcols):
        lbl.set_color(c)
        lbl.set_fontweight("bold")

    ax.set_xlim(0, XMAX)
    ax.set_ylim(-0.4, total_slots + 1.15)
    ax.axvline(112000, color=GRID, lw=0.9, zorder=1)
    ax.set_xticks([0, 25000, 50000, 75000, 100000])
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda v, p: "0" if v == 0 else RUPEE + "{:,.0f}k".format(v / 1000)))
    ax.xaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.set_xlabel("Money in the position today", color=INK2, fontsize=8.4)

    ax.set_title(headline, fontsize=14.5, color=INK, loc="left", pad=30, weight="bold")
    ax.text(0, 1.014, sub, transform=ax.transAxes, fontsize=8.8,
            color=INK2, va="bottom")

    fig.savefig(os.path.join(OUT, fname), dpi=200, bbox_inches="tight", pad_inches=0.20)
    plt.close(fig)
    print("  wrote", fname)


def chart_summary():
    fig, ax = plt.subplots(figsize=(10.4, 2.05))
    left = 0.0
    for v in ORDER:
        amt = money_in(v)
        ax.barh(0, amt, left=left, height=0.55, color=COLOR[v], zorder=3,
                edgecolor=SURFACE, linewidth=2.5)
        pct = 100.0 * amt / TOT
        ax.text(left + amt / 2.0, 0,
                "{}\n{:.0f}%   ·   {}".format(v, pct, RUPEE + "{:,.0f}".format(amt)),
                ha="center", va="center", fontsize=9.6, color=ONFILL[v], weight="bold")
        left += amt
    freed = money_in("EXIT") + sum(
        ROWS[t]["value"] - VD.TARGET[t] / 100.0 * TOT for t in VD.TARGET)
    ax.text(0, -0.62,
            "TRIM means keep a smaller slice, not sell it all.  "
            "Money actually sold across all three: " + RUPEE + "{:,.0f}".format(freed) +
            "  ({:.0f}% of the portfolio).".format(100.0 * freed / TOT),
            fontsize=8.6, color=INK2, va="center")
    ax.set_xlim(0, TOT)
    ax.set_ylim(-0.85, 0.45)
    ax.axis("off")
    fig.savefig(os.path.join(OUT, "verdict_summary.png"), dpi=200,
                bbox_inches="tight", pad_inches=0.10)
    plt.close(fig)
    print("  wrote verdict_summary.png")


if __name__ == "__main__":
    print("generating verdict charts ...")
    chart_summary()
    chart(["KEEP"], "verdicts_keep.png",
          "The {} holdings worth keeping".format(len(group_for("KEEP"))),
          "Bar length is how much money sits in each position. "
          "Every verdict was re-derived independently, then adversarially challenged.")
    chart(["TRIM", "EXIT"], "verdicts_sell.png",
          "The {} holdings to cut back or sell".format(
              len(group_for("TRIM")) + len(group_for("EXIT"))),
          "TRIM keeps a smaller position. EXIT sells out completely. "
          "Together they free up " + RUPEE + "{:,.0f}".format(
              money_in("EXIT") + sum(ROWS[t]["value"] - VD.TARGET[t] / 100.0 * TOT
                                     for t in VD.TARGET)) + " to redeploy.")
    print("done")
