# -*- coding: utf-8 -*-
"""Builds the portfolio review PDF."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, Image, PageBreak,
                                KeepTogether, NextPageTemplate)
import matplotlib
import data

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "img")
OUTDIR = os.path.join(HERE, "out")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "Portfolio_Deep_Analysis_2026-09-23.pdf")

# ------------------------------- fonts --------------------------------------
FDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DJ", os.path.join(FDIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DJB", os.path.join(FDIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DJI", os.path.join(FDIR, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJB", italic="DJI")

# ------------------------------- palette ------------------------------------
INK      = colors.HexColor("#0b0b0b")
INK2     = colors.HexColor("#52514e")
MUTED    = colors.HexColor("#898781")
RULE     = colors.HexColor("#e1e0d9")
SURFACE  = colors.HexColor("#fcfcfb")
PLANE    = colors.HexColor("#f9f9f7")
BLUE     = colors.HexColor("#2a78d6")
BLUE_BG  = colors.HexColor("#eaf2fd")
ORANGE   = colors.HexColor("#eb6834")
GOOD     = colors.HexColor("#0ca30c")
WARN     = colors.HexColor("#fab219")
CRIT     = colors.HexColor("#d03b3b")
GOOD_TXT = colors.HexColor("#006300")

R = RUPEE = "\u20b9"
ARROW = "\u2192"

# ------------------------------- styles -------------------------------------
def S(name, size, leading=None, font="DJ", color=INK, space_before=0,
      space_after=0, align=TA_LEFT, left=0, right=0):
    return ParagraphStyle(name, fontName=font, fontSize=size,
                          leading=leading or size * 1.42, textColor=color,
                          spaceBefore=space_before, spaceAfter=space_after,
                          alignment=align, leftIndent=left, rightIndent=right)

ST = {
    "h1":      S("h1", 19, 24, "DJB", INK, 0, 7),
    "h2":      S("h2", 12.5, 16, "DJB", INK, 15, 6),
    "h3":      S("h3", 10, 13, "DJB", INK, 10, 3),
    "body":    S("body", 8.9, 13.2, "DJ", INK2, 0, 6),
    "bodyt":   S("bodyt", 8.9, 13.2, "DJ", INK2, 0, 3),
    "lead":    S("lead", 10.2, 15, "DJ", INK2, 0, 8),
    "small":   S("small", 7.6, 11, "DJ", MUTED, 0, 4),
    "cap":     S("cap", 7.6, 11, "DJI", MUTED, 3, 9),
    "kicker":  S("kicker", 8.5, 12, "DJB", BLUE, 0, 3),
    "cover_t": S("cover_t", 30, 35, "DJB", INK, 0, 8),
    "cover_s": S("cover_s", 12.5, 17, "DJ", INK2, 0, 5),
    "th":      S("th", 7.0, 9, "DJB", INK, 0, 0),
    "thr":     S("thr", 7.0, 9, "DJB", INK, 0, 0, TA_RIGHT),
    "td":      S("td", 7.0, 9.2, "DJ", INK2, 0, 0),
    "tdb":     S("tdb", 7.0, 9.2, "DJB", INK, 0, 0),
    "tdr":     S("tdr", 7.0, 9.2, "DJ", INK2, 0, 0, TA_RIGHT),
    "tdrb":    S("tdrb", 7.0, 9.2, "DJB", INK, 0, 0, TA_RIGHT),
    "tdc":     S("tdc", 7.0, 9.2, "DJ", INK2, 0, 0, TA_CENTER),
    "note":    S("note", 7.6, 11, "DJ", INK2, 0, 0),
}

def P(txt, st="body"):
    return Paragraph(txt, ST[st])

def money(v, dec=0):
    """Rupee amount with the sign OUTSIDE the symbol: -Rs 11,407, not Rs -11,407."""
    sign = "-" if v < 0 else ""
    return sign + R + "{:,.{}f}".format(abs(v), dec)

# ------------------------------ page furniture -------------------------------
PW, PH = A4
LM = RM = 17 * mm
TM = 16 * mm
BM = 16 * mm
CW = PW - LM - RM          # ~ 476 pt content width

TITLE = "Portfolio Deep Analysis"
SUBT = "Equity & ETF holdings reviewed against an 8-10 year objective"


def on_page(canv, doc):
    canv.saveState()
    canv.setFillColor(SURFACE)
    canv.rect(0, 0, PW, PH, stroke=0, fill=1)
    if doc.page > 1:
        canv.setFont("DJ", 7)
        canv.setFillColor(MUTED)
        canv.drawString(LM, BM - 16, TITLE + "  \u00b7  " + data.MARKET["asof"])
        canv.drawRightString(PW - RM, BM - 16, str(doc.page))
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.6)
        canv.line(LM, BM - 8, PW - RM, BM - 8)
    canv.restoreState()


def on_cover(canv, doc):
    canv.saveState()
    canv.setFillColor(SURFACE)
    canv.rect(0, 0, PW, PH, stroke=0, fill=1)
    canv.setFillColor(BLUE)
    canv.rect(0, PH - 11 * mm, PW, 11 * mm, stroke=0, fill=1)
    canv.setFillColor(PLANE)
    canv.rect(0, 0, PW, 26 * mm, stroke=0, fill=1)
    canv.setFont("DJ", 7.6)
    canv.setFillColor(MUTED)
    canv.drawString(LM, 15 * mm,
                    "Prepared for the account holder  \u00b7  For personal planning use  \u00b7  "
                    "Not investment advice")
    canv.drawString(LM, 10.5 * mm,
                    "Prices and fundamentals as at " + data.MARKET["asof"] +
                    ".  Sources listed in the appendix.")
    canv.restoreState()


# ------------------------------ components -----------------------------------
def rule(space_before=4, space_after=6, color=RULE):
    t = Table([[""]], colWidths=[CW], rowHeights=[0.7])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return [Spacer(1, space_before), t, Spacer(1, space_after)]


def callout(title, body, accent=BLUE, bg=BLUE_BG):
    inner = [[P("<font face='DJB' color='#0b0b0b'>" + title + "</font>", "bodyt")],
             [P(body, "bodyt")]]
    t = Table(inner, colWidths=[CW - 20])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0), ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))
    outer = Table([[t]], colWidths=[CW])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return outer


def figure(name, width=CW, caption=None):
    from PIL import Image as PILImage
    p = os.path.join(IMG, name)
    try:
        iw, ih = PILImage.open(p).size
    except Exception:
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(p).getSize()
    img = Image(p, width=width, height=width * ih / float(iw))
    out = [img]
    if caption:
        out.append(P(caption, "cap"))
    return out


def bullets(items, style="body", gap=3.0):
    flow = []
    for it in items:
        t = Table([[P("\u25aa", "bodyt"), P(it, "bodyt")]], colWidths=[11, CW - 11])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow += [t, Spacer(1, gap)]
    return flow


def base_table_style(head_bg=PLANE, fs=7.0):
    return [
        ("FONTNAME", (0, 0), (-1, -1), "DJ"),
        ("FONTSIZE", (0, 0), (-1, -1), fs),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK2),
        ("BACKGROUND", (0, 0), (-1, 0), head_bg),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#c3c2b7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SURFACE, PLANE]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
