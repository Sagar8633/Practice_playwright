# -*- coding: utf-8 -*-
"""Verified verdicts: independent re-derivation + adversarial challenge, 23-Sep-2026."""

VERDICT = {
    'BEL'         : 'KEEP',
    'BLEL'        : 'KEEP',
    'CDSL'        : 'KEEP',
    'GROWW'       : 'KEEP',
    'GUJENERGY'   : 'KEEP',
    'HDFCBANK'    : 'KEEP',
    'IREDA'       : 'KEEP',
    'JPPOWER'     : 'KEEP',
    'JUNIORBEES'  : 'KEEP',
    'NSE'         : 'KEEP',
    'SBIFUNDS'    : 'KEEP',
    'TCS'         : 'KEEP',
    'CGPOWER'     : 'TRIM',
    'SETFGOLD'    : 'TRIM',
    'INDOMIM'     : 'TRIM',
    'JSWINFRA'    : 'TRIM',
    'SILVERBEES'  : 'TRIM',
    'AFIL'        : 'EXIT',
    'BAJAJHFL'    : 'EXIT',
    'BSE'         : 'EXIT',
    'COCHINSHIP'  : 'EXIT',
    'HINDCOPPER'  : 'EXIT',
    'LEAPIND'     : 'EXIT',
    'MOSCHIP'     : 'EXIT',
    'WEBELSOLAR'  : 'EXIT',
    'ZENTEC'      : 'EXIT',
}

REASON = {
    'AFIL'        : 'Cheap because ROE is only 11%; June-quarter revenue and profit both fell sequentially.',
    'BAJAJHFL'    : 'Promoter must sell 11.7% of the company by 2029; you pay 3.1x book for 12% returns.',
    'BEL'         : 'Q1 FY27 revenue +25%, receivables improved 176 to 140 days; the 12% growth figure is stale.',
    'BLEL'        : 'The 5% growth figure is stale; latest quarter shows sales up 19%, profit up 25%.',
    'BSE'         : "Costlier than the NSE you now own, on a Sensex franchise roughly 5% of NSE's turnover.",
    'CDSL'        : 'Capital-light duopoly, 24.5% ROE, 51% margins; 60x is rich but growth genuinely justifies a 3% holding.',
    'CGPOWER'     : "Backlog +45% and semiconductor capex inflate the P/E; cut size, don't abandon a quality franchise.",
    'COCHINSHIP'  : '59% of profit is interest income, EPS falling, yet 53x reported means ~130x core earnings.',
    'GROWW'       : 'Q1 FY27 profit nearly doubled while the market fell - the cyclical-peak trim thesis is factually wrong.',
    'GUJENERGY'   : 'Below book value, 11x earnings, 3.75% yield just hiked 53%, and Morbi volumes up sevenfold.',
    'HDFCBANK'    : 'Cheapest quality you own: 14.4x earnings, 1.89x book, improving NPAs, 15% loan growth.',
    'HINDCOPPER'  : '43x earnings and 15x book on profits that just doubled at the copper cycle peak.',
    'INDOMIM'     : '24% of portfolio in a 2-month-old stock at 96x; anchor lock-in unlocks 26 Oct.',
    'IREDA'       : "Bad-loan 'rise' is a quarterly blip; year-on-year NPAs fell and profit rose 37%.",
    'JPPOWER'     : 'Adani paid ₹18.19/share vs ₹16.04 today; IBC withdrawal agreed but not yet formal',
    'JSWINFRA'    : 'Great port, priced for FY30 already: 7x book for 13.6% ROCE, with equity dilution coming.',
    'JUNIORBEES'  : 'Only index exposure, at 19x versus a 22.7x five-year median, against 24% single-stock concentration.',
    'LEAPIND'     : 'Rs1,467 Cr debt earning 8.3% on capital, below its borrowing cost, priced at 112x.',
    'MOSCHIP'     : 'Q1 FY27 revenue fell 14% year-on-year - the growth that excused 127x earnings has stopped.',
    'NSE'         : 'Near-monopoly exchange at ~41x earnings, cheaper than BSE at 47x; 3.4% weight is right-sized.',
    'SBIFUNDS'    : "India's largest AMC, 23% profit growth, ~37x - keep on merit, not because it slipped below IPO price.",
    'SETFGOLD'    : 'Would become your single biggest holding after the selling; same metals logic as silver.',
    'SILVERBEES'  : "Silver's solar demand is falling 30%; metals already 17.3% of a portfolio holding 1.5% index.",
    'TCS'         : '14x earnings, 52% ROE, 3% dividend, $40bn order wins - the multiple broke, not the business.',
    'WEBELSOLAR'  : 'Promoter pledged 89% of a 29.7% stake, now pledging more on margin calls; peak-cycle margins.',
    'ZENTEC'      : '10.7% ROE at 8x book and 83x earnings, with promoters selling down.',
}

COUNTER = {
    'AFIL'        : 'At roughly 1x book with profits more than doubled, exit costs may exceed any benefit on an Rs822 position.',
    'BAJAJHFL'    : 'Selling a 23%-growing lender with near-pristine asset quality at its 52-week low may simply lock in the derating.',
    'BEL'         : '47x earnings and 12x book leave a heavy multiple-compression drag even if execution stays excellent.',
    'BLEL'        : 'Twenty-nine times earnings on five weeks of listed history, with half the pre-IPO shares unlocking 14 November.',
    'BSE'         : "46% ROE, 60% ROCE and SEBI's interest in a viable second venue make BSE durably profitable.",
    'CDSL'        : 'SEBI sets depository fees by circular; at 60x and 14.4x book one fee cut halves it.',
    'CGPOWER'     : 'At 111x there is no margin of safety; a de-rating alone could halve it.',
    'COCHINSHIP'  : 'Rs21,900 Cr order book and new dry dock capacity could convert into a decade of genuine revenue growth.',
    'GROWW'       : "One SEBI move on derivatives could gut the F&O profit pool behind those 59% margins; Peak XV's Rs1,756 Cr sale signals more supply.",
    'GUJENERGY'   : 'A 10.2% return on equity sits below the cost of capital, so below-book pricing may be permanent.',
    'HDFCBANK'    : 'NII grew only 7% on 15.4% loan growth; NIM at post-merger low 3.26% may not bottom.',
    'HINDCOPPER'  : "India's only integrated copper miner; a tripling of mined volume by 2030 would make today's multiple look cheap.",
    'INDOMIM'     : 'Genuine global MIM leader, 23% ROE, 26% growth; trimming a winner early is how compounding dies.',
    'IREDA'       : 'PFC and REC give the same green-power tailwind at one times book, higher ROE and a 4% dividend.',
    'JPPOWER'     : 'Adani stopped at 24% to avoid an open offer; minority holders get no exit from a leveraged merchant-thermal generator.',
    'JSWINFRA'    : "Ports are irreplaceable quasi-monopoly assets; 2.2x capacity by FY30 could make today's 55x look cheap in hindsight.",
    'JUNIORBEES'  : 'Next 50 is a high-churn waiting-room index; its long-run total return has often lagged Nifty 50 with more volatility.',
    'LEAPIND'     : 'Asset-pooling is capex-heavy; early ROCE understates mature returns, and revenue is growing 56% a year.',
    'MOSCHIP'     : 'Milestone-based ASIC revenue is lumpy by design; the ISRO 28nm win signals real capability, not decline.',
    'NSE'         : 'GMP collapsed from Rs310 to Rs81 in three weeks; unlisted-holder supply could break the price post-listing.',
    'SBIFUNDS'    : 'AMC earnings track AUM; a long bear market plus another SEBI TER cut would stall the 23% growth.',
    'SETFGOLD'    : 'Gold compounds nothing; World Bank sees $3,375 by 2027, and equities should beat it over a decade.',
    'SILVERBEES'  : 'Silver hedges the very equity drawdown underway; trimming at a 3% loss risks selling the only diversifier.',
    'TCS'         : 'AI may deflate the headcount-billing model permanently, making 14x a trap on peak earnings, not a bargain.',
    'WEBELSOLAR'  : 'ALMM cell protection plus 1.35GW expansion at 10x earnings could triple profits before the cycle turns.',
    'ZENTEC'      : 'Order inflow re-accelerated: roughly Rs472 Cr won in Aug 2026, backlog converts from Q2 FY27.',
}


# Weight to trim down to, as % of today's portfolio value
TARGET = {
    'INDOMIM'   : 8.0,
    'SETFGOLD'  : 9.0,
    'CGPOWER'   : 3.0,
    'SILVERBEES': 2.5,
    'JSWINFRA'  : 0.7,
}

# Where the freed-up money goes. (ticker, label, target %, is_new)
REDEPLOY = [
    ('NIFTY50',    'Nifty 50 index fund  (new)', 23.0, True),
    ('HDFCBANK',   'HDFC Bank',                   9.0, False),
    ('TCS',        'TCS',                         8.0, False),
    ('JUNIORBEES', 'JuniorBees  (Next 50 ETF)',   7.0, False),
    ('GUJENERGY',  'Gujarat Energy',              3.0, False),
    ('CASH',       'Cash / liquid fund  (new)',  10.7, True),
]

# BEL was flagged as inconsistent with the HindCopper exit (47x vs 41x).
# Kept, because HindCopper's doubled profit is a copper-price cycle while BEL's
# growth is order-book backed - but capped, not added to.
BEL_NOTE = True
