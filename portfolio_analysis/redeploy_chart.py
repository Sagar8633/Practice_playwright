# -*- coding: utf-8 -*-
"""Where the freed-up money goes."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import data
import verdicts as VD

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, BLUE_L = "#2a78d6", "#86b6ef"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "text.color": INK})
R = "₹"

ROWS = {r["ticker"]: r for r in data.rows()}
TOT = sum(r["value"] for r in data.rows())


def flows():
    exits = sum(ROWS[t]["value"] for t in VD.VERDICT if VD.VERDICT[t] == "EXIT")
    trims = {}
    for t, tgt in VD.TARGET.items():
        trims[t] = ROWS[t]["value"] - tgt / 100.0 * TOT
    raised = exits + sum(trims.values())

    buys = []
    for tk, label, tgt, is_new in VD.REDEPLOY:
        target_val = tgt / 100.0 * TOT
        have = 0.0 if is_new else ROWS[tk]["value"]
        buys.append((tk, label, target_val - have, target_val, tgt, is_new))
    return exits, trims, raised, buys


def chart_redeploy():
    exits, trims, raised, buys = flows()
    fig, ax = plt.subplots(figsize=(10.4, 4.5))

    buys_sorted = sorted(buys, key=lambda b: -b[2])
    y = list(range(len(buys_sorted)))[::-1]
    for yy, b in zip(y, buys_sorted):
        col = BLUE if b[5] else BLUE_L
        ax.barh(yy, b[2], height=0.58, color=col, zorder=3)
        if b[2] > 70000:                      # keep long bars clear of the note column
            ax.text(b[2] - 1800, yy, R + "{:,.0f}".format(b[2]), va="center",
                    ha="right", fontsize=7.8, color="#ffffff", weight="bold", zorder=4)
        else:
            ax.text(b[2] + 1600, yy, R + "{:,.0f}".format(b[2]),
                    va="center", fontsize=7.8, color=INK2, weight="bold")
        ax.text(104000, yy,
                "takes it to {:.0f}% of the portfolio".format(b[4]),
                va="center", fontsize=7.6, color=MUTED)

    ax.set_yticks(y)
    ax.set_yticklabels([b[1] for b in buys_sorted], fontsize=8.4)
    ax.set_xlim(0, 152000)
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda v, p: "0" if v == 0 else R + "{:,.0f}k".format(v / 1000)))
    ax.xaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.set_xlabel("Amount to buy", color=INK2, fontsize=8.4)

    ax.set_title("Where the money goes", fontsize=14.5, color=INK,
                 loc="left", pad=30, weight="bold")
    ax.text(0, 1.020,
            "Selling the 9 exits frees " + R + "{:,.0f}".format(exits) +
            " and the 5 trims free " + R + "{:,.0f}".format(sum(trims.values())) +
            " — " + R + "{:,.0f}".format(raised) +
            " in total, {:.0f}% of the portfolio. Dark bars are new positions.".format(
                100 * raised / TOT),
            transform=ax.transAxes, fontsize=8.8, color=INK2, va="bottom")

    fig.savefig(os.path.join(OUT, "redeploy.png"), dpi=200,
                bbox_inches="tight", pad_inches=0.20)
    plt.close(fig)
    print("  wrote redeploy.png")


def chart_before_after():
    """Concentration and index exposure, before vs after."""
    exits, trims, raised, buys = flows()
    cats = ["Biggest single\nposition", "Broad index\nfunds", "Gold + silver", "Cash"]
    before = [24.1, 1.5, 17.3, 0.0]
    after = [23.0, 30.0, 11.5, 10.7]      # Nifty50 23% becomes the largest single line
    after[0] = 23.0

    fig, ax = plt.subplots(figsize=(10.4, 2.9))
    n = len(cats)
    idx = range(n)
    bw = 0.34
    ax.bar([i - bw / 2 for i in idx], before, bw, color=BLUE_L, zorder=3, label="Today")
    ax.bar([i + bw / 2 for i in idx], after, bw, color=BLUE, zorder=3, label="After the plan")
    for i, (b, a) in enumerate(zip(before, after)):
        ax.text(i - bw / 2, b + 0.7, "{:.1f}%".format(b), ha="center",
                fontsize=7.8, color=INK2)
        ax.text(i + bw / 2, a + 0.7, "{:.1f}%".format(a), ha="center",
                fontsize=7.8, color=INK2, weight="bold")
    ax.set_xticks(list(idx))
    ax.set_xticklabels(cats, fontsize=8.2)
    ax.set_ylim(0, 36)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: "{:.0f}%".format(v)))
    ax.yaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, colors=MUTED)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.legend(frameon=False, fontsize=8.0, loc="upper right",
              handlelength=1.1, labelspacing=0.35)
    ax.set_title("What actually changes", fontsize=12.5, color=INK,
                 loc="left", pad=22, weight="bold")
    ax.text(0, 1.035,
            "The biggest single position stays about the same size — but it becomes "
            "an index fund instead of a two-month-old stock.",
            transform=ax.transAxes, fontsize=8.4, color=INK2, va="bottom")
    fig.savefig(os.path.join(OUT, "before_after.png"), dpi=200,
                bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print("  wrote before_after.png")


if __name__ == "__main__":
    e, t, raised, buys = flows()
    print("exits raise   :", round(e))
    print("trims raise   :", round(sum(t.values())))
    print("total raised  :", round(raised), "= {:.1f}%".format(100 * raised / TOT))
    print("total deployed:", round(sum(b[2] for b in buys)))
    chart_redeploy()
    chart_before_after()
