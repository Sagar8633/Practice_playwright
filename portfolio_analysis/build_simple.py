# -*- coding: utf-8 -*-
"""Simple hold/sell chart report - A4 landscape."""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, Image, PageBreak)
from PIL import Image as PILImage
import matplotlib
import data
import verdicts as VD
import redeploy_chart as RC

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "img")
OUTDIR = os.environ.get("PF_OUTDIR", os.path.join(HERE, "out"))
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "Hold_or_Sell_Chart_Report.pdf")

FDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for n, f in (("DJ", "DejaVuSans.ttf"), ("DJB", "DejaVuSans-Bold.ttf"),
             ("DJI", "DejaVuSans-Oblique.ttf")):
    pdfmetrics.registerFont(TTFont(n, os.path.join(FDIR, f)))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJB", italic="DJI")

INK, INK2, MUTED = colors.HexColor("#0b0b0b"), colors.HexColor("#52514e"), colors.HexColor("#898781")
SURFACE, PLANE, RULE = colors.HexColor("#fcfcfb"), colors.HexColor("#f9f9f7"), colors.HexColor("#e1e0d9")
BLUE, BLUE_BG = colors.HexColor("#2a78d6"), colors.HexColor("#eaf2fd")
AMBER, AMBER_BG = colors.HexColor("#fab219"), colors.HexColor("#fdf4e0")
CRIT, GOOD_TXT = colors.HexColor("#d03b3b"), colors.HexColor("#006300")
R = "\u20b9"

PW, PH = landscape(A4)
LM = RM = 14 * mm
TM = 13 * mm
BM = 13 * mm
CW = PW - LM - RM
CH = PH - TM - BM

TITLE = "Hold or Sell"
ASOF = data.MARKET["asof"]
ROWS = {r["ticker"]: r for r in data.rows()}
TOT = sum(r["value"] for r in data.rows())


def S(n, sz, ld, f="DJ", c=INK2, sa=0, sb=0):
    return ParagraphStyle(n, fontName=f, fontSize=sz, leading=ld, textColor=c,
                          spaceAfter=sa, spaceBefore=sb, alignment=TA_LEFT)

ST = {
    "h1":   S("h1", 22, 26, "DJB", INK, 6),
    "h2":   S("h2", 13, 17, "DJB", INK, 5, 8),
    "sub":  S("sub", 10.2, 14.5, "DJ", INK2, 6),
    "body": S("body", 9.0, 13.0, "DJ", INK2, 5),
    "bt":   S("bt", 9.0, 13.0, "DJ", INK2, 0),
    "cap":  S("cap", 7.6, 10.5, "DJI", MUTED, 0, 3),
    "td":   S("td", 8.2, 11.5, "DJ", INK2, 0),
}


def P(t, s="body"):
    return Paragraph(t, ST[s])


def money(v):
    return ("-" if v < 0 else "") + R + "{:,.0f}".format(abs(v))


def fig(name, width=CW, max_h=None):
    """Scale to `width`, then shrink further if it would overflow the frame."""
    p = os.path.join(IMG, name)
    iw, ih = PILImage.open(p).size
    w = width
    h = w * ih / float(iw)
    cap = max_h if max_h is not None else CH
    if h > cap:
        w = w * cap / h
        h = cap
    im = Image(p, width=w, height=h)
    im.hAlign = "LEFT"
    return im


def on_page(canv, doc):
    canv.saveState()
    canv.setFillColor(SURFACE)
    canv.rect(0, 0, PW, PH, stroke=0, fill=1)
    canv.setFont("DJ", 7)
    canv.setFillColor(MUTED)
    canv.drawString(LM, BM - 13, TITLE + "  \u00b7  " + ASOF +
                    "  \u00b7  personal planning, not investment advice")
    canv.drawRightString(PW - RM, BM - 13, str(doc.page))
    canv.restoreState()


def callout(title, body, accent=BLUE, bg=BLUE_BG):
    inner = Table([[P("<font face='DJB' color='#0b0b0b'>" + title + "</font>", "bt")],
                   [Spacer(1, 3)], [P(body, "bt")]], colWidths=[CW - 24])
    inner.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    o = Table([[inner]], colWidths=[CW])
    o.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.6, accent),
                           ("LEFTPADDING", (0, 0), (-1, -1), 11),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                           ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return o


def story():
    s = []
    exits, trims, raised, buys = RC.flows()

    # ---------------------------- PAGE 1 ----------------------------
    s.append(P(TITLE, "h1"))
    s.append(P("Every holding sorted into one of three buckets, with the single "
               "reason that decides it. Prices and fundamentals as at " + ASOF + ".", "sub"))
    s.append(fig("verdict_summary.png"))
    s.append(Spacer(1, 6))
    s.append(fig("before_after.png", max_h=205))
    s.append(Spacer(1, 10))
    s.append(callout(
        "Read this before you sell anything",
        "Done all at once, this plan sells <b>" + money(raised) + " \u2014 51% of the "
        "portfolio</b> \u2014 into a market already down 13.7% this year and falling for six "
        "straight weeks. The stock-by-stock logic is sound, but the execution is not a "
        "single afternoon's work. Stage it over about six months, and never sell a position "
        "before you know what the money is buying.",
        AMBER, AMBER_BG))

    s.append(PageBreak())

    # ---------------------------- PAGE 2 ----------------------------
    s.append(fig("verdicts_keep.png"))

    s.append(PageBreak())

    # ---------------------------- PAGE 3 ----------------------------
    s.append(fig("verdicts_sell.png"))

    s.append(PageBreak())

    # ---------------------------- PAGE 4 ----------------------------
    s.append(fig("redeploy.png", max_h=360))
    s.append(Spacer(1, 12))
    s.append(callout(
        "One sentence to remember",
        "You do not own 26 businesses — you own one stock, one metal and 24 opinions. "
        "Halve the stock, cut the metal, put the money in the index: over ten years the "
        "price you paid decides your return far more than the story you bought.",
        BLUE, BLUE_BG))
    s.append(PageBreak())
    s.append(P("Do it in this order", "h1"))
    s.append(P("Order matters more than speed. Each step funds the next.", "sub"))

    steps = [
        ("1", "Halve Indo-MIM before 26 October",
         "The only dated catalyst on the page \u2014 the anchor lock-in expires and more "
         "stock hits the market. It is also the biggest position and the only one sitting "
         "on a real gain (+" + money(ROWS['INDOMIM']['pnl']) + "), so this sale is funded "
         "by profit rather than capitulation. Frees about " + money(
             ROWS['INDOMIM']['value'] - 8.0 / 100 * TOT) + ", more than the entire exit "
         "list is worth."),
        ("2", "Sell Websol this week",
         "Promoters hold 29.7% and have pledged 89.4% of it, and are pledging more on "
         "margin calls. It is the one holding with a live path to zero. The position is "
         "only " + money(ROWS['WEBELSOLAR']['value']) + ", but size is irrelevant when the "
         "risk is permanent loss rather than a drawdown."),
        ("3", "Clear the rest of the exit list over 2-3 months",
         "Zen, MosChip, Hindustan Copper, Cochin Shipyard, BSE, Bajaj Housing, Leap India "
         "and Akme. Spread across several sessions, not one. Seven of the nine are at a "
         "loss, so this also books roughly " + money(6700) + " of short-term capital loss "
         "that carries forward eight years."),
        ("4", "Build the index core with the proceeds",
         "About " + money(96613) + " into a Nifty 50 index fund and " + money(23128) +
         " more into JuniorBees, bought in four to six tranches. This is the piece that is "
         "missing today \u2014 index exposure goes from 1.5% to 30%, which is what makes an "
         "8-10 year horizon survivable without constant monitoring."),
        ("5", "Top up the three cheap quality names, then stop",
         "HDFC Bank at 1.89x book, TCS at 14x with a 3% dividend, Gujarat Energy below book "
         "value. Buy on weak days rather than on a fixed date, and hold the last ~11% in a "
         "liquid fund as dry powder."),
    ]
    rows = []
    for n, head, body in steps:
        rows.append([
            P("<font face='DJB' size='13' color='#2a78d6'>" + n + "</font>", "td"),
            Table([[P("<font face='DJB' color='#0b0b0b'>" + head + "</font>", "bt")],
                   [P(body, "td")]],
                  colWidths=[CW - 34],
                  style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, 0), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                                    ("TOPPADDING", (0, 1), (-1, 1), 0),
                                    ("BOTTOMPADDING", (0, 1), (-1, -1), 0)]))
        ])
    t = Table(rows, colWidths=[26, CW - 26])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [SURFACE, PLANE]),
    ]))
    s.append(t)

    s.append(Spacer(1, 8))
    s.append(callout(
        "One sentence to remember",
        "You do not own 26 businesses \u2014 you own one stock, one metal and 24 opinions. "
        "Halve the stock, cut the metal, put the money in the index: over ten years the "
        "price you paid decides your return far more than the story you bought.",
        BLUE, BLUE_BG))

    s.append(Spacer(1, 6))
    s.append(P(
        "Method: each verdict was re-derived from the verified fundamentals by an analyst "
        "working blind to the earlier report, then challenged by a second analyst told to "
        "refute it, then checked once more for consistency across the whole list. Six calls "
        "changed as a result, and two factual claims behind the changes (the Jaiprakash "
        "resolution status and the Bajaj Housing shareholding deadline) were verified "
        "separately. This is a point-in-time snapshot for personal planning, not investment "
        "advice \u2014 verify prices before acting.", "cap"))

    return s


def build():
    doc = BaseDocTemplate(OUT, pagesize=landscape(A4),
                          leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
                          title="Hold or Sell - portfolio verdicts, 23 September 2026",
                          author="Portfolio review")
    frame = Frame(LM, BM, CW, CH, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])
    doc.build(story())
    print("PDF ->", OUT)
    print("pages:", doc.page)


if __name__ == "__main__":
    build()
