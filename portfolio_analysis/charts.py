# -*- coding: utf-8 -*-
"""Charts for the portfolio review. Light surface only (print/PDF target)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter
import data

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(OUT, exist_ok=True)

# ---- validated palette (light surface, see dataviz/references/palette.md) ----
SURFACE = "#fcfcfb"
INK     = "#0b0b0b"
INK2    = "#52514e"
MUTED   = "#898781"
GRID    = "#e1e0d9"
AXIS    = "#c3c2b7"
S1      = "#2a78d6"   # categorical slot 1 - blue
S2      = "#eb6834"   # categorical slot 2 - orange
NEG     = "#e34948"   # diverging pole - red
BAND    = "#cde2fb"   # blue step 100

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": AXIS,
})

RUPEE = "₹"


def frame(ax, xgrid=True, ygrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(0.8)
    if xgrid:
        ax.xaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def titles(ax, head, sub):
    """Headline + subhead above the axes, no mathtext (keeps unicode safe)."""
    ax.set_title(head, fontsize=10.8, color=INK, loc="left", pad=24, weight="bold")
    ax.text(0.0, 1.022, sub, transform=ax.transAxes, fontsize=8.0,
            color=INK2, va="bottom", ha="left")


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=210, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)
    print("  wrote", name)


R = data.rows()
TOT = sum(r["value"] for r in R)


# ============================ 1. POSITION WEIGHTS ===========================
def chart_weights():
    rs = R[::-1]
    fig, ax = plt.subplots(figsize=(7.1, 6.4))
    y = list(range(len(rs)))
    ax.barh(y, [r["weight"] for r in rs], height=0.62, color=S1, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([r["ticker"] for r in rs], fontsize=7.6)
    for i, r in enumerate(rs):
        ax.text(r["weight"] + 0.35, i, "{:.1f}%".format(r["weight"]),
                va="center", fontsize=7.1, color=INK2)
    ax.set_xlim(0, 28)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: "{:.0f}%".format(v)))
    ax.set_xlabel("Share of portfolio market value")
    frame(ax)
    ax.axvline(5, color=AXIS, lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.text(5.3, 0.6, "5% sizing ceiling", fontsize=7, color=MUTED,
            rotation=90, va="bottom")
    titles(ax, "Two positions are 37% of the portfolio",
           "26 holdings. The bottom 9 together are under 11% - too small to matter, "
           "large enough to distract.")
    save(fig, "weights.png")


# ============================ 2. SECTOR EXPOSURE ============================
def chart_sectors():
    from collections import defaultdict
    s = defaultdict(float)
    for r in R:
        s[r["sector"]] += r["value"]
    items = sorted(s.items(), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7.1, 3.6))
    y = list(range(len(items)))
    ax.barh(y, [100 * v / TOT for _, v in items], height=0.6, color=S1, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([k for k, _ in items], fontsize=7.8)
    for i, (k, v) in enumerate(items):
        ax.text(100 * v / TOT + 0.4, i, "{:.1f}%".format(100 * v / TOT),
                va="center", fontsize=7.2, color=INK2)
    ax.set_xlim(0, 29)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: "{:.0f}%".format(v)))
    ax.set_xlabel("Share of portfolio market value")
    frame(ax)
    titles(ax, "Eleven themes, but one stock is an entire sector",
           "'Precision Manufacturing' is Indo-MIM on its own. Cyclicals and thematics "
           "dominate; broad-market exposure is 1.5%.")
    save(fig, "sectors.png")


# ============================ 3. P&L ATTRIBUTION ============================
def chart_attribution():
    rs = sorted(R, key=lambda r: r["pnl"])
    fig, ax = plt.subplots(figsize=(7.1, 6.4))
    y = list(range(len(rs)))
    cols = [S1 if r["pnl"] >= 0 else NEG for r in rs]
    ax.barh(y, [r["pnl"] for r in rs], height=0.62, color=cols, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([r["ticker"] for r in rs], fontsize=7.6)
    for i, r in enumerate(rs):
        off = 800 if r["pnl"] >= 0 else -800
        ha = "left" if r["pnl"] >= 0 else "right"
        ax.text(r["pnl"] + off, i, "{:+,.0f}".format(r["pnl"]),
                va="center", ha=ha, fontsize=7.1, color=INK2)
    ax.set_xlim(-5600, 33500)
    ax.axvline(0, color=AXIS, lw=1.0, zorder=4)
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda v, p: RUPEE + "{:,.0f}".format(v)))
    ax.set_xlabel("Unrealised profit / loss")
    frame(ax)
    h = [plt.Rectangle((0, 0), 1, 1, color=S1),
         plt.Rectangle((0, 0), 1, 1, color=NEG)]
    ax.legend(h, ["Gain", "Loss"], frameon=False, fontsize=7.6,
              loc="lower right", handlelength=1.1, labelspacing=0.35)
    titles(ax, "One stock is carrying the entire portfolio",
           "Indo-MIM and gold together are +" + RUPEE + "31,249. "
           "The other 24 holdings are -" + RUPEE + "11,407 combined.")
    save(fig, "attribution.png")


# ========================= 4. VALUATION vs QUALITY ==========================
def chart_valuation():
    pts = [r for r in R if r["pe"] and r["roe"]]
    fig, ax = plt.subplots(figsize=(7.1, 5.0))
    ax.axvspan(8, 19.74, color=BAND, alpha=0.45, zorder=0)
    ax.axvline(19.74, color=S1, lw=1.3, ls=(0, (5, 3)), zorder=2)
    ax.text(18.8, 72, "Nifty 50 P/E 19.7x", fontsize=7.4, color=S1,
            rotation=90, va="top", ha="right")
    ax.axhline(15, color=AXIS, lw=1.0, ls=(0, (3, 3)), zorder=1)
    ax.text(158, 15.8, "15% ROE", fontsize=7, color=MUTED, ha="right")
    for r in pts:
        ax.scatter(r["pe"], r["roe"], s=26 + r["weight"] * 46, color=S1,
                   alpha=0.72, edgecolor=SURFACE, linewidth=1.6, zorder=4)
    # (dx, dy, horizontal-alignment) - tuned by eye against the rendered plot
    lbl = {"INDOMIM": (22, 7, "left"), "CGPOWER": (12, 3, "left"),
           "MOSCHIP": (11, 1, "left"), "ZENTEC": (12, -3, "left"),
           "LEAPIND": (-8, -12, "right"), "TCS": (7, 2, "left"),
           "HDFCBANK": (-8, -4, "right"), "GUJENERGY": (-5, -13, "right"),
           "WEBELSOLAR": (7, 1, "left"), "HINDCOPPER": (-10, 8, "right"),
           "BSE": (6, 4, "left"), "CDSL": (8, 4, "left"),
           "BEL": (-7, -12, "right"), "GROWW": (7, 5, "left"),
           "COCHINSHIP": (-8, -12, "right"), "JSWINFRA": (7, 3, "left"),
           "IREDA": (8, 3, "left"), "BAJAJHFL": (6, -11, "left"),
           "BLEL": (7, 3, "left"), "AFIL": (7, 1, "left")}
    for r in pts:
        dx, dy, ha = lbl.get(r["ticker"], (6, 4, "left"))
        ax.annotate(r["ticker"], (r["pe"], r["roe"]), textcoords="offset points",
                    xytext=(dx, dy), fontsize=6.9, color=INK2, ha=ha)
    ax.set_xscale("log")
    ax.set_xticks([10, 15, 20, 30, 50, 80, 130])
    ax.set_xticklabels(["10x", "15x", "20x", "30x", "50x", "80x", "130x"])
    ax.set_xlim(8, 170)
    ax.set_ylim(0, 75)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: "{:.0f}%".format(v)))
    ax.set_xlabel("Price / Earnings  (log scale)")
    ax.set_ylabel("Return on Equity")
    frame(ax, xgrid=False, ygrid=True)
    titles(ax, "What is being paid, against what is being earned",
           "Bubble size = position weight. Shaded band = cheaper than the index. "
           "Ideal is upper-left; most weight sits far right.")
    save(fig, "valuation.png")


# ========================== 5. DE-RATING HEATMAP ============================
SCEN = [("EPS +25%/yr\nexit 40x", .25, 40), ("EPS +20%/yr\nexit 35x", .20, 35),
        ("EPS +15%/yr\nexit 30x", .15, 30), ("EPS +10%/yr\nexit 25x", .10, 25)]
# Only the names trading ABOVE the index multiple belong here: for these, a
# normalising P/E is a headwind. Running the same columns on a 14x stock would
# model a fantasy re-rating, so the cheap names are handled separately.
DERATE = [("MOSCHIP", 127), ("LEAPIND", 112), ("CGPOWER", 111), ("INDOMIM", 96),
          ("ZENTEC", 83), ("CDSL", 59.9), ("JSWINFRA", 54.6), ("COCHINSHIP", 53.1),
          ("BEL", 47.2), ("BSE", 47.1), ("HINDCOPPER", 41.0), ("BAJAJHFL", 25.8)]


def cagr(entry, g, exit_pe, yrs=10):
    return 100 * ((1 + g) * (exit_pe / entry) ** (1.0 / yrs) - 1)


def chart_derating():
    M = np.array([[cagr(pe, g, x) for _, g, x in SCEN] for _, pe in DERATE])
    fig, ax = plt.subplots(figsize=(7.1, 4.6))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "gainloss", [NEG, "#f0efec", S1])
    im = ax.imshow(M, cmap=cmap, vmin=-16, vmax=16, aspect="auto")
    ax.set_xticks(range(len(SCEN)))
    ax.set_xticklabels([s[0] for s in SCEN], fontsize=7.4)
    ax.set_yticks(range(len(DERATE)))
    ax.set_yticklabels(["{}   {:.0f}x today".format(t, pe) for t, pe in DERATE],
                       fontsize=7.4)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, "{:+.1f}%".format(v), ha="center", va="center",
                    fontsize=7.4, color="#ffffff" if abs(v) > 9.5 else INK)
    ax.set_xticks([x - .5 for x in range(1, len(SCEN))], minor=True)
    ax.set_yticks([y - .5 for y in range(1, len(DERATE))], minor=True)
    ax.grid(which="minor", color=SURFACE, lw=2)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.030, pad=0.02)
    cb.set_label("10-year annualised return", fontsize=7.4, color=INK2)
    cb.ax.tick_params(labelsize=7, length=0, colors=MUTED)
    cb.outline.set_visible(False)
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: "{:+.0f}%".format(v)))
    titles(ax, "The price paid decides the decade",
           "The 12 holdings priced above the index. 10-year annualised return if "
           "earnings grow as shown AND the multiple normalises. Arithmetic, not opinion.")
    save(fig, "derating.png")


# ========================== 6. 10-YEAR PROJECTION ===========================
def chart_projection():
    yrs = np.arange(0, 11)
    C = TOT
    cur_base, cur_bear, cur_bull, fix_base = .07, .03, .10, .11
    fig, ax = plt.subplots(figsize=(7.1, 4.6))
    ax.fill_between(yrs, C * (1 + cur_bear) ** yrs, C * (1 + cur_bull) ** yrs,
                    color=BAND, alpha=.55, zorder=1, lw=0)
    ax.plot(yrs, C * (1 + cur_base) ** yrs, color=S1, lw=2.0, zorder=3)
    ax.plot(yrs, C * (1 + fix_base) ** yrs, color=S2, lw=2.0, zorder=3)
    ax.scatter([10, 10], [C * 1.07 ** 10, C * 1.11 ** 10], s=34,
               color=[S1, S2], zorder=4, edgecolor=SURFACE, lw=1.5)
    ax.annotate("Restructured, base case  11%/yr\n" + RUPEE + "{:,.0f}".format(C * 1.11 ** 10),
                (10, C * 1.11 ** 10), textcoords="offset points", xytext=(-6, 12),
                ha="right", va="bottom", fontsize=8.0, color=S2, weight="bold")
    ax.annotate("Current mix, base case  7%/yr\n" + RUPEE + "{:,.0f}".format(C * 1.07 ** 10),
                (10, C * 1.07 ** 10), textcoords="offset points", xytext=(-6, -20),
                ha="right", va="top", fontsize=8.0, color=S1, weight="bold")
    ax.text(9.9, C * 1.10, "Shaded band = current mix, bear 3%/yr to bull 10%/yr",
            fontsize=7.4, color=INK2, va="center", ha="right")
    ax.set_xlim(0, 10.3)
    ax.set_ylim(C * 0.93, C * 1.11 ** 10 * 1.14)
    ax.set_xticks(range(0, 11))
    ax.set_xlabel("Years from today")
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, p: RUPEE + "{:.1f}L".format(v / 100000.0)))
    ax.set_ylabel("Portfolio value (no fresh money added)")
    frame(ax, xgrid=False, ygrid=True)
    titles(ax, "Restructuring's base case clears the current mix's best case",
           "Same " + RUPEE + "4.2 lakh starting corpus, no fresh money. The only "
           "difference is what is owned and at what entry multiple.")
    save(fig, "projection.png")


if __name__ == "__main__":
    print("generating charts ...")
    chart_weights()
    chart_sectors()
    chart_attribution()
    chart_valuation()
    chart_derating()
    chart_projection()
    print("done ->", OUT)
