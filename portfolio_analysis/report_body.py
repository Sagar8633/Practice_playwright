# -*- coding: utf-8 -*-
"""Content + assembly for the portfolio review PDF."""
from build_report import *          # styles, palette, helpers, OUT, CW
import data

ROWS = data.rows()
TOT_VAL = sum(r["value"] for r in ROWS)
TOT_INV = sum(r["invested"] for r in ROWS)
TOT_PNL = TOT_VAL - TOT_INV
M = data.MARKET
BY = {r["ticker"]: r for r in ROWS}

WIN = ("INDOMIM", "SETFGOLD")
WIN_PNL = sum(BY[t]["pnl"] for t in WIN)
REST = [r for r in ROWS if r["ticker"] not in WIN]
REST_PNL = sum(r["pnl"] for r in REST)
REST_INV = sum(r["invested"] for r in REST)

EQ = [r for r in ROWS if r["pe"]]
EQ_VAL = sum(r["value"] for r in EQ)
BLENDED_PE = EQ_VAL / sum(r["value"] / r["pe"] for r in EQ)


# ============================== VERDICTS ====================================
# ticker: (verdict, target weight %, rationale)
V = {
"INDOMIM": ("TRIM HARD", 9.0,
    "Genuinely good business - ROE 23.4%, ROCE 25%, promoter 77.7% - but listed only on "
    "30 Jul 2026 and already 24% of everything owned. At 96x earnings against a 15% "
    "three-year sales CAGR, the multiple is doing the work, not the company. Booking "
    "roughly two-thirds of the gain de-risks the whole portfolio in one trade."),
"SETFGOLD": ("HOLD", 10.0,
    "The insurance leg, and the only position that worked while equities fell. Gold is a "
    "hedge, not a compounder: keep it, do not let it drift above ~10%."),
"CGPOWER": ("TRIM", 3.0,
    "Excellent operator - near debt-free, ROCE 26.7%, order backlog up 45% to "
    + R + "17,333 Cr, Murugappa parentage. The problem is 111x earnings and 17.7x book. "
    "Even 20% EPS growth for a decade with a still-generous 35x exit returns only ~7%/yr."),
"ZENTEC": ("EXIT", 0.0,
    "83x earnings on earnings that are falling: FY26 revenue " + R + "688 Cr vs "
    + R + "974 Cr (-29%), PAT " + R + "218 Cr vs " + R + "299 Cr (-27%). Order book of "
    + R + "1,336 Cr is under 2x revenue - thin for defence. Promoters cut 8.94% in three "
    "years. Expensive plus shrinking plus insiders selling is the wrong combination."),
"SILVERBEES": ("TRIM", 2.5,
    "Bought near the top and down 3.2%. Silver is the high-beta version of an allocation "
    "that is already oversized. Gold plus silver is 17.3% of the portfolio."),
"MOSCHIP": ("EXIT", 0.0,
    "The worst risk/reward in the book: 127x earnings for an 11% ROE and 11% ROCE. FY26 "
    "profit grew just 5.5% (" + R + "35 Cr) on 25% revenue growth - the turnkey-ASIC shift "
    "is eating margins. Promoter holding 39.3% and falling. The India semiconductor story "
    "is real; this is not the vehicle for it."),
"HINDCOPPER": ("TRIM", 2.0,
    "FY26 profit nearly doubled to " + R + "921 Cr on the copper cycle. That is price, not "
    "compounding. 14.8x book for a state-owned miner is a peak-cycle multiple on peak-cycle "
    "margins - the classic point to reduce, not add."),
"TCS": ("ADD", 6.0,
    "14.1x earnings, 51.8% ROE, 63% ROCE and a 3.1% dividend yield after a 50%+ drawdown "
    "from the 2024 peak. AI disruption is a genuine risk, but at this multiple a lot of it "
    "is already priced. Highest quality asset in the portfolio at the lowest relative price."),
"NSE": ("HOLD", 3.0,
    "Not a loss - the -100% on screen is a pre-listing display artefact. Allotted in the "
    "IPO at " + R + "1,785 (band " + R + "1,700-1,785, 5.7x subscribed); listing 24 Sep 2026 "
    "with a grey-market premium near " + R + "42. A genuine franchise; hold it after listing."),
"COCHINSHIP": ("TRIM", 2.0,
    R + "423 Cr of the " + R + "717 Cr FY26 profit is other income - nearly 59%. Core "
    "shipbuilding earnings are much thinner than the headline, and EPS actually fell from "
    + R + "31.45 to " + R + "27.24. The " + R + "21,900 Cr order book is real, but 53x is "
    "not the price for it."),
"CDSL": ("HOLD", 3.0,
    "Outstanding economics - 24.5% ROE, 32% ROCE, 51% operating margin, near debt-free, "
    "structurally geared to every new demat account in India. Simply not cheap at 60x and "
    "14.4x book. Hold what is owned; do not add here."),
"BSE": ("HOLD", 3.0,
    "46% ROE and 60% ROCE with a 69% five-year profit CAGR is a rare franchise. At 47x and "
    "20x book it is priced for continued derivatives growth - a regulatory-sensitive "
    "assumption. Hold, do not add."),
"BAJAJHFL": ("HOLD", 2.0,
    "Strong parentage and 23% AUM growth, but ROE is only 12% and it trades at 3.09x book. "
    "Jefferies' own target is " + R + "92 against " + R + "83.5 - limited room. A fine "
    "business at a full price."),
"IREDA": ("HOLD", 2.0,
    "Cheapest-looking lender here at 15.9x and 2.26x book with 16% ROE and a government-"
    "mandated green lending runway. But gross NPAs rose to 3.76% from 3.49% in one quarter "
    "and interest coverage is flagged as low. Hold; do not average down until asset quality "
    "stops deteriorating."),
"GUJENERGY": ("HOLD / SMALL ADD", 3.0,
    "The only holding below book value: 0.89x book, 11.4x earnings, 3.75% dividend yield. "
    "Post-restructuring GSPC entity spanning city gas, trading, E&P and renewables. Caveats "
    "are real - 10.2% ROE and promoter holding cut to 38.94% in the reorganisation - but the "
    "downside is protected by the price in a way nothing else here is."),
"BLEL": ("HOLD", 2.0,
    "Quietly the best small-cap in the book: 23.6% ROE, 30.9% ROCE, only " + R + "18 Cr of "
    "debt, promoter 70.8%. The catch is 5% revenue growth at 29x earnings, and a "
    + R + "1,986 Cr market cap means thin liquidity. Cap it at 2%."),
"HDFCBANK": ("ADD", 8.0,
    "The highest-conviction addition. 14.4x earnings, 1.89x book, gross NPA 1.12%, cost-to-"
    "income improved to 38%, consensus target " + R + "1,156 against " + R + "737. NIM "
    "compression to 3.50% is the reason it is cheap and the reason it recovers as high-cost "
    "borrowings roll off. India's largest private bank at a decade-low multiple."),
"BEL": ("HOLD / SMALL ADD", 3.0,
    "27.4% ROE, 36.4% ROCE, near debt-free, 88% defence revenue, sitting near its 52-week "
    "low. 47x is not cheap, but this is the quality end of the defence basket - unlike Zen. "
    "Watch the working-capital stretch: debtor days at 170."),
"LEAPIND": ("EXIT", 0.0,
    "112x earnings for an 8.3% ROCE and " + R + "1,467 Cr of borrowings, with interest "
    "coverage flagged as low. Asset-pooling is capital-hungry and returns are thin. Listed "
    "14 Aug 2026 and currently +3% - exit into that strength."),
"WEBELSOLAR": ("EXIT", 0.0,
    "10.2x earnings looks like a bargain and is the single biggest trap here: promoters hold "
    "just 29.7% and 89.4% of that stake is pledged. A 67% ROE is cycle-peak economics in a "
    "solar-cell market facing global overcapacity. Cheap plus pledged plus commoditising is "
    "a value trap, not value."),
"JUNIORBEES": ("ADD", 12.0,
    "The only broad-market exposure in a 26-stock portfolio, and it is 1.5%. This is where "
    "the proceeds from the exits should go first - it is the piece that makes an 8-10 year "
    "horizon survivable without constant monitoring."),
"SBIFUNDS": ("HOLD", 1.5,
    "IPO'd July 2026 and trading slightly below the implied issue price. An asset manager is "
    "a leveraged bet on the same retail-investing trend already owned via NSE, BSE, CDSL and "
    "Groww. Keep it small."),
"JSWINFRA": ("HOLD", 1.5,
    "Real growth runway - 170 MTPA to a planned 400 MTPA by FY30, 40% five-year profit CAGR. "
    "But 54.6x and 7x book with ROCE of only 13.6% means the expansion is already in the "
    "price. Hold the existing position."),
"GROWW": ("HOLD", 1.0,
    "28.8% ROE, 37.3% ROCE, 59% operating margin, almost no debt - a very good business at "
    "48.5x. Fair-value estimates cluster near " + R + "164 against " + R + "189 today. Small "
    "position; leave it alone."),
"JPPOWER": ("EXIT", 0.0,
    "Still working through insolvency resolution. Adani Power is acquiring 24% and the NARCL "
    "settlement is in motion - that is an event-driven trade, not a ten-year holding. It "
    "spiked to " + R + "22.48 in May and is " + R + "16.04 now. Take the position off."),
"AFIL": ("EXIT", 0.0,
    "A " + R + "822 position in a " + R + "407 Cr micro-cap NBFC, down 18.7%. Too small to "
    "change any outcome and too small to justify tracking. Housekeeping."),
}

VCOL = {"EXIT": CRIT, "TRIM HARD": CRIT, "TRIM": WARN, "HOLD": INK2,
        "ADD": GOOD_TXT, "HOLD / SMALL ADD": GOOD_TXT}


# ============================== BUILD STORY =================================
def story():
    s = []

    # ------------------------------ COVER ------------------------------------
    s.append(Spacer(1, 44 * mm))
    s.append(P("PORTFOLIO REVIEW", "kicker"))
    s.append(P(TITLE, "cover_t"))
    s.append(P(SUBT, "cover_s"))
    s += rule(6, 14)

    hdr = [[P("<font face='DJB' size='7.4' color='#52514e'>TOTAL INVESTED</font>", "td"),
            P("<font face='DJB' size='7.4' color='#52514e'>MARKET VALUE</font>", "td"),
            P("<font face='DJB' size='7.4' color='#52514e'>UNREALISED P&amp;L</font>", "td"),
            P("<font face='DJB' size='7.4' color='#52514e'>HOLDINGS</font>", "td")],
           [P("<font face='DJB' size='15' color='#0b0b0b'>" + money(TOT_INV) + "</font>", "td"),
            P("<font face='DJB' size='15' color='#0b0b0b'>" + money(TOT_VAL) + "</font>", "td"),
            P("<font face='DJB' size='15' color='#006300'>+" + money(TOT_PNL) +
              "</font>  <font face='DJ' size='8' color='#52514e'>(+{:.2f}%)</font>".format(
                  100 * TOT_PNL / TOT_INV), "td"),
            P("<font face='DJB' size='15' color='#0b0b0b'>26</font>"
              "  <font face='DJ' size='8' color='#52514e'>across 2 accounts</font>", "td")]]
    t = Table(hdr, colWidths=[CW * .24, CW * .24, CW * .30, CW * .22])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                           ("TOPPADDING", (0, 0), (-1, 0), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                           ("TOPPADDING", (0, 1), (-1, 1), 0),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)
    s += rule(14, 16)

    s.append(callout(
        "The headline is misleading",
        "The portfolio shows +{:.2f}%. Strip out two positions - Indo-MIM and the gold ETF - "
        "and the remaining 24 holdings are <b>{}</b> on <b>{}</b> invested, a loss of "
        "{:.2f}%. Stock selection outside those two has not worked. That, and not the "
        "market's {:.1f}% fall this year, is what this report is about.".format(
            100 * TOT_PNL / TOT_INV, money(REST_PNL), money(REST_INV),
            100 * REST_PNL / REST_INV, abs(M["nifty_ytd"])),
        ORANGE, colors.HexColor("#fdefe9")))

    s.append(NextPageTemplate("main"))
    s.append(PageBreak())

    # -------------------------- EXECUTIVE SUMMARY ----------------------------
    s.append(P("Executive summary", "h1"))
    s.append(P(
        "This portfolio is not badly researched - almost every company in it is a "
        "defensible business, and several are excellent. The problem is structural, and it "
        "shows up in three numbers: <b>one position is 24% of the money</b>, the blended "
        "earnings multiple is <b>{:.0f}x against the index's {:.1f}x</b>, and the "
        "<b>broad-market allocation is 1.5%</b>. Over eight to ten years those three facts "
        "will matter far more than which defence stock or which semiconductor stock was "
        "picked.".format(BLENDED_PE, M["nifty_pe"]), "lead"))

    s.append(P("The six findings", "h2"))
    s += bullets([
        "<b>One stock is carrying everything.</b> Indo-MIM (+{}) and the gold ETF (+{}) "
        "together are +{}. The other 24 holdings lose {} between them. A single position "
        "bought eight weeks ago is the entire result.".format(
            money(BY["INDOMIM"]["pnl"]), money(BY["SETFGOLD"]["pnl"]), money(WIN_PNL),
            money(abs(REST_PNL))),

        "<b>Concentration is extreme at the top and pointless at the bottom.</b> The top two "
        "positions are 37.0% and the top five are 52.8%, while nine positions are under 2% "
        "each and together under 11%. The large holdings carry uncompensated single-stock "
        "risk; the small ones cannot move the result but still demand attention.",

        "<b>The portfolio is priced at roughly twice the market.</b> Blended P/E of "
        "{:.0f}x versus {:.1f}x for the Nifty 50 - an earnings yield of {:.2f}% against "
        "{:.2f}%. <b>{}</b> of the money, {:.1f}% of the portfolio, sits in five stocks "
        "trading above 80x earnings.".format(
            BLENDED_PE, M["nifty_pe"], 100 / BLENDED_PE, 100 / M["nifty_pe"],
            money(175220), 41.7),

        "<b>Six holdings carry problems that are structural, not cyclical.</b> Websol's "
        "promoters have pledged 89.4% of a 29.7% stake; Zen's revenue fell 29% while it "
        "trades at 83x; MosChip pairs 127x earnings with an 11% ROE; Leap India pairs 112x "
        "with 8.3% ROCE and heavy debt; Cochin Shipyard books 59% of profit as other income; "
        "JP Power is still in insolvency resolution.",

        "<b>There is almost no ballast.</b> Broad-index exposure is 1.5%, cash is nil, and "
        "17.3% sits in gold and silver - an oversized hedge doing the job that an index core "
        "should be doing. Eleven sector themes create an <i>appearance</i> of "
        "diversification that the position sizes contradict.",

        "<b>The NSE line is not a loss.</b> The -{} / -100% on screen is a pre-listing "
        "display artefact. Those shares were allotted in the IPO at {} and list on "
        "24 September 2026.".format(money(14280), money(1785)),
    ])

    s.append(P("What to do about it", "h2"))
    s.append(P(
        "Six positions to exit outright ({}, 14.4% of the portfolio), five to trim, and the "
        "proceeds - about <b>{}</b>, or 37% of the portfolio - redeployed into a broad-index "
        "core, into the three genuinely cheap quality names already owned, and into a cash "
        "reserve. The full plan is on page 12; the sequencing is on page 14.".format(
            money(60335), money(155981)), "body"))

    s.append(callout(
        "Why this matters more over 8-10 years, not less",
        "Over one or two years, a great story can carry a 100x multiple. Over ten years the "
        "multiple almost always normalises, and the arithmetic is unforgiving: CG Power "
        "growing earnings at 20% a year for a decade and still commanding 35x returns "
        "<b>6.9% a year</b>. TCS growing at 8% and re-rating only to 16x returns "
        "<b>12.4% a year</b> including dividends. The long horizon is exactly why the entry "
        "price cannot be waved away as a short-term concern."))

    s.append(PageBreak())

    # ---------------------------- HOLDINGS TABLE -----------------------------
    s.append(P("1.  The portfolio, consolidated", "h1"))
    s.append(P(
        "The two broker apps each show roughly half the money, so neither screen reveals "
        "that Indo-MIM is a quarter of everything. This is the combined view - the one that "
        "should drive every decision.", "lead"))

    head = ["Stock", "Company", "Qty", "Avg " + R, "Price " + R, "Invested " + R,
            "Value " + R, "P&amp;L " + R, "P&amp;L %", "Wt %"]
    tbl = [[P(h, "th" if i < 2 else "thr") for i, h in enumerate(head)]]
    for r in ROWS:
        gain = r["pnl"] >= 0
        col = "#006300" if gain else "#d03b3b"
        tbl.append([
            P("<font face='DJB'>" + r["ticker"] + "</font>", "td"),
            P(r["name"], "td"),
            P("{:,.0f}".format(r["qty"]), "tdr"),
            P("{:,.2f}".format(r["avg"]), "tdr"),
            P("{:,.2f}".format(r["ltp"]), "tdr"),
            P("{:,.0f}".format(r["invested"]), "tdr"),
            P("{:,.0f}".format(r["value"]), "tdr"),
            P("<font color='" + col + "'>{:+,.0f}</font>".format(r["pnl"]), "tdr"),
            P("<font color='" + col + "'>{:+.1f}</font>".format(r["pnl_pct"]), "tdr"),
            P("<font face='DJB'>{:.1f}</font>".format(r["weight"]), "tdr"),
        ])
    tbl.append([
        P("<font face='DJB'>TOTAL</font>", "td"), P("", "td"), P("", "tdr"), P("", "tdr"),
        P("", "tdr"),
        P("<font face='DJB'>{:,.0f}</font>".format(TOT_INV), "tdr"),
        P("<font face='DJB'>{:,.0f}</font>".format(TOT_VAL), "tdr"),
        P("<font face='DJB' color='#006300'>{:+,.0f}</font>".format(TOT_PNL), "tdr"),
        P("<font face='DJB' color='#006300'>{:+.1f}</font>".format(100 * TOT_PNL / TOT_INV), "tdr"),
        P("<font face='DJB'>100.0</font>", "tdr"),
    ])
    t = Table(tbl, colWidths=[64, 82, 26, 40, 42, 50, 50, 46, 32, 34], repeatRows=1)
    st = base_table_style()
    st += [("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#c3c2b7")),
           ("BACKGROUND", (0, -1), (-1, -1), PLANE)]
    t.setStyle(TableStyle(st))
    s.append(t)
    s.append(P(
        "NSE is carried at its " + R + "1,785 IPO allotment price; the broker screen shows "
        "0.00 because the stock had not yet listed on the date of capture. Every other price "
        "is the live quote on " + M["asof"] + ".", "cap"))

    s.append(PageBreak())

    # ------------------------------ CONCENTRATION ----------------------------
    s.append(P("2.  Concentration: the shape of the risk", "h1"))
    s += figure("weights.png", CW)
    s.append(P(
        "A 24% position is a decision that overrides every other decision in the portfolio. "
        "If Indo-MIM halves - entirely possible for a stock at 96x earnings that listed eight "
        "weeks ago - the portfolio loses 12% no matter how well the other 25 holdings do. "
        "Nothing else owned here can offset that.", "body"))
    s.append(P(
        "The opposite problem sits at the bottom. Akme Fintrade is " + R + "822. Even a "
        "double adds 0.2% to the portfolio. Nine positions are under 2% each, and together "
        "under 11% - they generate tracking work, brokerage and tax events out of all "
        "proportion to their ability to change the outcome.", "body"))
    s.append(callout(
        "A workable sizing rule for a 26-stock book",
        "No single stock above 8% of the portfolio; nothing below 2% unless it is being "
        "deliberately built up to a target over the next few months. Applied here, that means "
        "trimming two positions and closing or consolidating about nine.",
        BLUE, BLUE_BG))

    s.append(PageBreak())

    # -------------------------------- SECTORS --------------------------------
    s.append(P("3.  What is actually owned", "h1"))
    s += figure("sectors.png", CW)
    s.append(P(
        "Eleven themes look diversified. They are not, for two reasons. First, "
        "'Precision Manufacturing' is one stock. Second, the five capital-markets holdings - "
        "NSE, BSE, CDSL, Groww and SBI Funds - total 11.9% and are all the same bet: that "
        "Indian retail trading volumes keep rising. They will fall together in any market "
        "downturn or adverse regulatory move on derivatives.", "body"))

    alloc = [["Sleeve", "Now", "Target", "Action"],
             ["Broad-index ETFs", "1.5%", "22%", "Add about " + money(86153)],
             ["Quality compounders at fair prices", "9.7%", "24%", "Add about " + money(59900)],
             ["Thematic / high-multiple satellites", "71.4%", "32%", "Cut about " + money(165544)],
             ["Precious metals (gold + silver)", "17.4%", "12%", "Trim silver, about " + money(22473)],
             ["Cash / liquid reserve", "0.0%", "10%", "Build about " + money(42006)]]
    rowsx = [[P("<font face='DJB'>" + c + "</font>" if i == 0 else c,
                "td" if j == 0 or j == 3 else "tdc")
              for j, c in enumerate(row)] for i, row in enumerate(alloc)]
    t = Table(rowsx, colWidths=[180, 52, 52, 170])
    st = base_table_style()
    st += [("FONTNAME", (0, 1), (0, -1), "DJ")]
    t.setStyle(TableStyle(st))
    s.append(Spacer(1, 6))
    s.append(t)
    s.append(P(
        "'Quality compounders at fair prices' means the names already owned that are cheap "
        "on their own merits: TCS, HDFC Bank, Gujarat Energy and Bharat Electronics. No new "
        "research is required to execute this - it is a reallocation, not a rebuild.", "cap"))

    s.append(PageBreak())

    # ------------------------------ ATTRIBUTION ------------------------------
    s.append(P("4.  Where the money was actually made and lost", "h1"))
    s += figure("attribution.png", CW)
    s.append(P(
        "This is the most important chart in the report. Two positions produced <b>{}</b>. "
        "The other twenty-four lost <b>{}</b> between them - a {:.2f}% loss on {} of capital. "
        "Six of the ten largest losses are in the expensive thematic names: IREDA, Zen, TCS, "
        "Cochin Shipyard, Bajaj Housing and Websol.".format(
            money(WIN_PNL), money(abs(REST_PNL)), abs(100 * REST_PNL / REST_INV),
            money(REST_INV)), "body"))
    s.append(P(
        "The market explains part of this - the Nifty is down {:.1f}% in 2026 and has fallen "
        "for six consecutive weeks. But the market is not down 24%, and a portfolio bought at "
        "twice the market's multiple falls further than the market when multiples compress. "
        "That is what is happening here.".format(abs(M["nifty_ytd"])), "body"))

    s.append(PageBreak())

    # ------------------------------- VALUATION -------------------------------
    s.append(P("5.  Valuation: the central problem", "h1"))
    s += figure("valuation.png", CW)
    s.append(P(
        "The ideal position on this chart is upper-left - high returns on capital, modest "
        "price. Most of the portfolio's weight sits on the right. The two largest bubbles, "
        "Indo-MIM and CG Power, are good businesses at 96x and 111x. The two positions in "
        "the bottom-right corner, MosChip and Leap India, are expensive <i>and</i> low-return "
        "- there is no reading of the fundamentals that justifies those multiples.", "body"))

    band = [["Valuation band", "Value", "% of portfolio", "Holdings"],
            ["Above 80x  (extreme)", money(175220), "41.7%",
             "INDOMIM, CGPOWER, ZENTEC, MOSCHIP, LEAPIND"],
            ["50x - 80x  (very rich)", money(32665), "7.8%", "COCHINSHIP, CDSL, JSWINFRA"],
            ["30x - 50x  (rich)", money(40166), "9.6%", "HINDCOPPER, BSE, BEL, GROWW"],
            ["15x - 30x  (fair)", money(29404), "7.0%", "BAJAJHFL, IREDA, BLEL"],
            ["Below 15x  (cheap)", money(40443), "9.6%",
             "TCS, GUJENERGY, HDFCBANK, WEBELSOLAR, AFIL"]]
    rowsx = [[P("<font face='DJB'>" + c + "</font>" if i == 0 else c,
                "td" if j in (0, 3) else "tdc") for j, c in enumerate(row)]
             for i, row in enumerate(band)]
    t = Table(rowsx, colWidths=[112, 62, 68, 214])
    t.setStyle(TableStyle(base_table_style()))
    s.append(Spacer(1, 4))
    s.append(t)
    s.append(P(
        "The remaining 24.3% is in ETFs, the unlisted/newly-listed positions and JP Power, "
        "where a trailing P/E is not meaningful.", "cap"))

    s.append(PageBreak())

    # ------------------------------ DE-RATING --------------------------------
    s.append(P("6.  The arithmetic of a decade", "h1"))
    s.append(P(
        "A high multiple is not automatically a mistake - it is a claim that earnings will "
        "grow fast enough to justify it. Over ten years that claim becomes testable. The "
        "return to a holder is earnings growth multiplied by the change in the multiple, and "
        "the second term is usually negative for anything starting above 50x.", "lead"))
    s += figure("derating.png", CW)
    s.append(P(
        "Read the third column - 15% earnings growth every year for ten years, exiting at a "
        "still-above-market 30x. That is a <i>good</i> outcome for most companies. It returns "
        "-0.5% a year on MosChip, +0.9% on CG Power and +2.4% on Indo-MIM. The fourth column, "
        "10% growth and a 25x exit, is a realistic base case for a mature industrial - and it "
        "loses money in five of the twelve.", "body"))

    s.append(P("The same arithmetic on the cheap half", "h3"))
    cheap = [["Stock", "P/E now", "EPS +8%/yr\nexit 16x", "EPS +10%/yr\nexit 18x",
              "EPS +12%/yr\nexit 20x", "Dividend\nyield"],
             ["TCS", "14.1x", "+12.4%", "+15.8%", "+19.0%", "3.06%"],
             ["HDFCBANK", "14.4x", "+10.9%", "+14.2%", "+17.5%", "1.76%"],
             ["GUJENERGY", "11.4x", "+15.5%", "+18.9%", "+22.2%", "3.75%"],
             ["IREDA", "15.9x", "+9.3%", "+12.6%", "+15.8%", "1.22%"]]
    rowsx = [[P("<font face='DJB'>" + c.replace("\n", "<br/>") + "</font>" if i == 0
                else ("<font face='DJB'>" + c + "</font>" if j == 0 else c),
                "td" if j == 0 else "tdc") for j, c in enumerate(row)]
             for i, row in enumerate(cheap)]
    t = Table(rowsx, colWidths=[76, 56, 86, 86, 86, 66])
    t.setStyle(TableStyle(base_table_style()))
    s.append(t)
    s.append(P(
        "Returns include the dividend yield. A cheap stock growing slowly beats an expensive "
        "stock growing quickly, because the multiple moves in the holder's favour instead of "
        "against it. This is the single most important idea for an 8-10 year horizon.", "cap"))

    s.append(PageBreak())

    # ------------------------------- RED FLAGS -------------------------------
    s.append(P("7.  Red flags that are structural, not cyclical", "h1"))
    s.append(P(
        "A falling price is not a red flag - most of this portfolio is down because the market "
        "is down. These eight are different: the issue is in the company or the "
        "shareholding, and time does not fix it.", "lead"))

    flags = [
        ("WEBELSOLAR", "Promoter pledge", CRIT,
         "Promoters hold only 29.7% and have pledged 89.4% of it. If the lender sells, the "
         "stock has no floor and no controlling shareholder."),
        ("MOSCHIP", "Price vs returns", CRIT,
         "127x earnings against an 11% ROE and 11% ROCE. Promoter holding 39.3% and falling "
         "quarter after quarter."),
        ("ZENTEC", "Shrinking earnings", CRIT,
         "Revenue -29% and profit -27% in FY26, held at 83x. Promoters have cut 8.94% over "
         "three years. Order book under 2x annual revenue."),
        ("LEAPIND", "Leverage + price", CRIT,
         R + "1,467 Cr of borrowings, ROCE 8.3%, low interest coverage - at 112x earnings, "
         "seven weeks after listing."),
        ("COCHINSHIP", "Earnings quality", WARN,
         R + "423 Cr of " + R + "717 Cr FY26 profit is other income. Core operations earn far "
         "less than the headline suggests, and EPS fell year on year."),
        ("JPPOWER", "Insolvency process", WARN,
         "Still resolving under IBC. The Adani stake purchase and NARCL settlement are "
         "event-driven catalysts, not the basis for a ten-year holding."),
        ("IREDA", "Asset quality trend", WARN,
         "Gross NPAs rose to 3.76% from 3.49% in a single quarter. Provision cover improved to "
         "68.2%, but the direction of travel needs watching before adding."),
        ("GUJENERGY", "Ownership change", WARN,
         "Promoter holding fell to 38.94% in the May 2026 GSPC restructuring. The valuation is "
         "attractive; the governance change deserves monitoring."),
    ]
    rowsx = [[P("<font face='DJB'>Stock</font>", "td"),
              P("<font face='DJB'>Issue</font>", "td"),
              P("<font face='DJB'>Severity</font>", "tdc"),
              P("<font face='DJB'>What it means</font>", "td")]]
    for tk, issue, sev, why in flags:
        label = "SERIOUS" if sev == CRIT else "WATCH"
        mark = "●" if sev == CRIT else "▲"
        rowsx.append([
            P("<font face='DJB'>" + tk + "</font>", "td"),
            P(issue, "td"),
            P("<font color='" + sev.hexval()[2:].join(["#", ""]) + "'>" + mark +
              "</font> <font face='DJB' size='6.2'>" + label + "</font>", "tdc"),
            P(why, "td")])
    t = Table(rowsx, colWidths=[62, 74, 58, 262])
    t.setStyle(TableStyle(base_table_style()))
    s.append(t)
    s.append(P(
        "Severity is shown with a symbol and a word as well as colour, so the table survives "
        "black-and-white printing.", "cap"))

    s.append(PageBreak())

    # ------------------------------ SCORECARD --------------------------------
    s.append(P("8.  Stock-by-stock verdict", "h1"))
    s.append(P(
        "Every holding, in order of size, with the fundamentals that drove the call. "
        "Percentages in the 'Target' column are the recommended weight after restructuring.",
        "lead"))

    def scorecard(subset, first):
        rowsx = [[P("<font face='DJB'>Stock</font>", "td"),
                  P("<font face='DJB'>Wt</font>", "tdc"),
                  P("<font face='DJB'>P/E</font>", "tdc"),
                  P("<font face='DJB'>ROE</font>", "tdc"),
                  P("<font face='DJB'>Verdict</font>", "tdc"),
                  P("<font face='DJB'>Tgt</font>", "tdc"),
                  P("<font face='DJB'>Reasoning</font>", "td")]]
        for r in subset:
            verdict, tgt, why = V[r["ticker"]]
            vc = VCOL[verdict].hexval()[2:]
            rowsx.append([
                P("<font face='DJB'>" + r["ticker"] + "</font>", "td"),
                P("{:.1f}%".format(r["weight"]), "tdc"),
                P("{:.0f}x".format(r["pe"]) if r["pe"] else "—", "tdc"),
                P("{:.0f}%".format(r["roe"]) if r["roe"] else "—", "tdc"),
                P("<font face='DJB' size='6.2' color='#" + vc + "'>" +
                  verdict.replace(" / ", "<br/>") .replace(" HARD", "<br/>HARD") + "</font>", "tdc"),
                P("{:.1f}%".format(tgt) if tgt else "0", "tdc"),
                P(why, "td")])
        t = Table(rowsx, colWidths=[64, 30, 26, 28, 46, 34, 244], repeatRows=1)
        t.setStyle(TableStyle(base_table_style(fs=6.6)))
        return t

    s.append(scorecard(ROWS[:13], True))
    s.append(PageBreak())
    s.append(P("8.  Stock-by-stock verdict  <font size='9' color='#898781'>(continued)</font>", "h1"))
    s.append(scorecard(ROWS[13:], False))

    s.append(PageBreak())

    # ------------------------------ THE PLAN ---------------------------------
    s.append(P("9.  The 8-10 year plan", "h1"))
    s.append(P(
        "The objective over this horizon is not to pick the best stock. It is to make sure no "
        "single mistake can derail the outcome, and to own the compounding at a price that "
        "lets it show up in the return. Three moves do almost all of the work.", "lead"))

    s.append(P("Move 1 — Take the Indo-MIM win off the table", "h3"))
    s.append(P(
        "Sell roughly 50 of the 81 shares, leaving about 9% of the portfolio. That realises "
        "close to <b>" + money(63596) + "</b> at a 37.6% gain, and converts a concentrated "
        "bet on a two-month-old listing into the funding for everything else. Holding the "
        "remaining 31 shares keeps the upside if the business grows into its multiple.", "body"))

    s.append(P("Move 2 — Close the six structural problems", "h3"))
    s.append(P(
        "MosChip, Zen Technologies, Websol, Leap India, JP Power and Akme Fintrade together "
        "are <b>" + money(60335) + "</b>, 14.4% of the portfolio. None of them is a holding "
        "whose thesis improves with time: two have falling earnings, two have balance-sheet "
        "or pledge problems, one is in insolvency, one is too small to matter. Four are "
        "already at a loss, which makes the tax treatment straightforward.", "body"))

    s.append(P("Move 3 — Build the core that does not currently exist", "h3"))
    s.append(P(
        "Put the first <b>" + money(86153) + "</b> of proceeds into broad-index ETFs, taking "
        "that sleeve from 1.5% to 22%. Then add to HDFC Bank at 14.4x and 1.89x book, to TCS "
        "at 14.1x with a 3.1% yield, and to Gujarat Energy below book value. These are the "
        "three positions where the price already does the risk management.", "body"))

    s.append(Spacer(1, 4))
    s.append(callout(
        "What the restructured portfolio looks like",
        "22% broad index · 24% quality compounders bought below 20x · 32% thematic "
        "satellites, none above 8% · 12% precious metals · 10% cash. Blended P/E "
        "falls from roughly {:.0f}x to the low 20s, the largest single position drops from "
        "24% to 9%, and the number of holdings falls from 26 to about 19 - each one large "
        "enough to matter and small enough to survive being wrong.".format(BLENDED_PE)))

    s.append(PageBreak())

    # ----------------------------- PROJECTION --------------------------------
    s.append(P("10.  What this is worth in ten years", "h1"))
    s += figure("projection.png", CW)
    s.append(P(
        "The gap is not a forecast; it is the compounding consequence of the valuation and "
        "concentration facts already established. The current mix is modelled at 7% a year in "
        "the base case because a blended {:.0f}x multiple has to compress against earnings "
        "growth. The restructured mix is modelled at 11% because a low-20s multiple does "
        "not.".format(BLENDED_PE), "body"))

    s.append(P("Adding monthly contributions changes the picture entirely", "h3"))
    s.append(P(
        "On a " + money(TOT_VAL) + " corpus, restructuring is worth about " + money(366401) +
        " over ten years. A monthly contribution is worth considerably more than that, and "
        "the two compound together.", "body"))

    sip = [["Monthly SIP", "5 years", "8 years", "10 years"]]
    for amt in (5000, 10000, 15000, 25000):
        row = ["" + money(amt)]
        for yrs in (5, 8, 10):
            r_m = 0.11 / 12
            n = yrs * 12
            fv_sip = amt * (((1 + r_m) ** n - 1) / r_m)
            fv_corp = TOT_VAL * (1.11 ** yrs)
            row.append(money(fv_sip + fv_corp))
        sip.append(row)
    sip.append(["No SIP (corpus only)"] +
               [money(TOT_VAL * (1.11 ** y)) for y in (5, 8, 10)])
    rowsx = [[P("<font face='DJB'>" + c + "</font>" if i == 0 else
                ("<font face='DJB'>" + c + "</font>" if j == 0 else c),
                "td" if j == 0 else "tdc") for j, c in enumerate(row)]
             for i, row in enumerate(sip)]
    t = Table(rowsx, colWidths=[122, 118, 118, 118])
    st = base_table_style()
    st += [("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#c3c2b7"))]
    t.setStyle(TableStyle(st))
    s.append(t)
    s.append(P(
        "All figures assume the restructured portfolio's 11% base case, contributions at the "
        "start of each month, and no withdrawals. They are arithmetic on an assumed rate, not "
        "a promise - the assumed rate is the part that can be wrong.", "cap"))

    s.append(PageBreak())

    # ------------------------------ ACTION PLAN ------------------------------
    s.append(P("11.  Sequencing", "h1"))
    s.append(P(
        "Order matters. Do not sell everything in one session - the market is in its sixth "
        "consecutive weekly decline, and forced selling into weakness is how good plans "
        "produce bad prices.", "lead"))

    s.append(P("Within 30 days", "h3"))
    s += bullets([
        "Confirm the NSE listing on 24 September and decide on it as a <i>listed</i> holding, "
        "not a pre-listing line item.",
        "Exit Websol and JP Power first. The pledge risk and the insolvency process are the "
        "two positions where waiting has a genuine tail risk.",
        "Close Akme Fintrade. It is " + R + "822 and costs more attention than it can ever "
        "return.",
        "Sell the first tranche of Indo-MIM - about 25 of the 81 shares - and park the "
        "proceeds in a liquid fund. Do not deploy into equities on the same day.",
    ])

    s.append(P("Months 1 to 3", "h3"))
    s += bullets([
        "Complete the Indo-MIM trim to roughly 9%, staggered across several weeks.",
        "Exit MosChip, Zen Technologies and Leap India. None needs to be done on a single day.",
        "Begin the index core: deploy into Nifty 50 and Next 50 ETFs in four to six tranches "
        "rather than in one transaction.",
        "Trim CG Power to 3%, Hindustan Copper to 2%, Cochin Shipyard to 2% and the silver ETF "
        "to 2.5%.",
    ])

    s.append(P("Months 3 to 6", "h3"))
    s += bullets([
        "Add to HDFC Bank towards 8%, TCS towards 6% and Gujarat Energy towards 3%, buying on "
        "weakness rather than on a fixed date.",
        "Hold the remaining cash at about 10%. In a market down {:.1f}% for the year with the "
        "index P/E {:.1f}% below its ten-year average, dry powder is an asset, not a "
        "drag.".format(abs(M["nifty_ytd"]), 15.3),
        "Consolidate into one broker if practical. The two-account split is what hid the 24% "
        "concentration in the first place.",
    ])

    s.append(P("Ongoing discipline", "h3"))
    s += bullets([
        "Review quarterly against results, not against price. The questions are: did earnings "
        "grow, did the multiple change, did promoter holding or pledge change.",
        "Rebalance once a year. Trim anything above 8%; top up anything that has fallen below "
        "its target without the thesis breaking.",
        "Apply one rule before every new purchase: what has to be true for this to return 12% "
        "a year for ten years - and is the entry multiple already assuming it?",
    ])

    s.append(PageBreak())

    # ------------------------------ RISKS + APPENDIX -------------------------
    s.append(P("12.  Risks to this view, and sources", "h1"))
    s.append(P("Where this analysis could be wrong", "h3"))
    s += bullets([
        "<b>The expensive names may keep compounding.</b> CG Power, Indo-MIM, BSE and CDSL "
        "are high-quality businesses. If earnings grow at 25% for a decade and multiples hold, "
        "trimming them will look like a mistake. The recommendation trims rather than exits "
        "precisely because that outcome is possible.",
        "<b>TCS may be a value trap.</b> If AI genuinely compresses IT services revenue "
        "permanently, 14x is not cheap - it is a melting ice cube. The dividend yield and the "
        "balance sheet are the compensation for that risk, not a guarantee against it.",
        "<b>Gold may keep running.</b> Forecasts diverge sharply: J.P. Morgan sees $6,000/oz "
        "by end-2026, while the World Bank expects prices to <i>fall</i> to around $3,375 in "
        "2027. Trimming metals to 12% is a middle path, not a call on the metal.",
        "<b>The market may recover quickly.</b> At a P/E of {:.2f} against a ten-year average "
        "of {:.2f}, the index is not expensive. A fast rebound would reward staying fully "
        "invested and penalise holding 10% cash.".format(M["nifty_pe"], M["nifty_pe_10yr_avg"]),
        "<b>Taxes and costs are not modelled.</b> Short-term capital gains on the Indo-MIM "
        "trim will be material, since the position is under a year old. That cost is real and "
        "should be weighed against the concentration risk it removes - but it does not change "
        "the direction of the recommendation.",
    ])

    s.append(P("Basis of preparation", "h3"))
    s.append(P(
        "Holdings, quantities and average costs were read from the four broker screenshots "
        "provided. Prices, market caps, P/E, P/B, ROE, ROCE, promoter holdings, pledge data "
        "and FY25/FY26 financials were taken from screener.in company pages on " + M["asof"] +
        ", cross-checked against company results releases and broker research where "
        "available. Index levels and valuation come from published Nifty 50 data: index at "
        "{:,.0f}, P/E {:.2f}, P/B {:.2f}, dividend yield {:.2f}%, down {:.2f}% year to "
        "date.".format(M["nifty"], M["nifty_pe"], M["nifty_pb"], M["nifty_div_yield"],
                       abs(M["nifty_ytd"])), "body"))
    s.append(P(
        "Two P/B figures are derived rather than reported: Indo-MIM (from equity capital plus "
        "reserves) and Behari Lal Engineering (from EPS and ROE). The 10-year return tables "
        "are arithmetic on stated assumptions, not forecasts. The screenshots supplied did "
        "not show a complete holdings list for the second account - names between "
        "COCHINSHIP and GROWW alphabetically, and anything after LEAPIND, were not visible, "
        "so the true portfolio may be larger than the 26 positions analysed here.", "body"))

    s.append(Spacer(1, 6))
    s.append(callout(
        "Important",
        "This document was prepared for personal planning from a point-in-time snapshot. It "
        "is not investment advice and carries no regulatory status. Prices move, company "
        "fundamentals change between reporting dates, and the tax consequences of the "
        "recommended trades depend on individual circumstances. Verify current prices and "
        "consult a registered adviser before acting on any of it.",
        MUTED, PLANE))

    return s


def build():
    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=LM, rightMargin=RM,
                          topMargin=TM, bottomMargin=BM,
                          title="Portfolio Deep Analysis - 23 September 2026",
                          author="Portfolio review", subject=SUBT)
    frame = Frame(LM, BM, CW, PH - TM - BM, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover),
        PageTemplate(id="main", frames=[frame], onPage=on_page),
    ])
    doc.build(story())
    print("PDF written ->", OUT)
    print("pages:", doc.page)


if __name__ == "__main__":
    build()
