# -*- coding: utf-8 -*-
"""Portfolio dataset as of 23-Sep-2026. Prices/fundamentals verified from
screener.in + broker screenshots supplied by the investor."""

# acct: A = broker showing Qty/Avg/MktVal ; B = app showing Qty x ATP / LTP
# pe/pb/roe/roce = latest reported (screener.in, 23-Sep-2026)
# kind: EQ = direct equity, ETF = exchange traded fund, PRE = pre-listing/IPO
HOLDINGS = [
    # ticker, name, acct, qty, avg, ltp, sector, kind, pe, pb, roe, roce, promoter, flag
    # INDOMIM P/B derived: book = equity 48 Cr + reserves 2,771 Cr on 48 Cr shares
    ("INDOMIM","Indo-MIM","B",81,909.87,1251.90,"Precision Manufacturing","EQ",96.0,21.3,23.4,25.0,77.65,"amber"),
    ("SETFGOLD","SBI Gold ETF","A",421,120.22,128.64,"Precious Metals","ETF",None,None,None,None,None,"green"),
    ("CGPOWER","CG Power & Ind.","A",27,892.13,895.00,"Capital Goods","EQ",111.0,17.7,20.5,26.7,56.36,"amber"),
    ("ZENTEC","Zen Technologies","A",14,1788.44,1672.30,"Defence","EQ",83.0,7.99,10.7,16.2,48.51,"red"),
    ("SILVERBEES","Nippon Silver ETF","A",85,227.53,220.26,"Precious Metals","ETF",None,None,None,None,None,"amber"),
    ("MOSCHIP","MosChip Tech.","A",90,214.71,207.32,"Technology / Semis","EQ",127.0,9.84,11.0,11.0,39.31,"red"),
    ("HINDCOPPER","Hindustan Copper","A",30,533.85,513.00,"Metals & Mining","EQ",41.0,14.8,32.9,42.4,66.14,"amber"),
    ("TCS","Tata Consultancy","A",7,2308.11,2089.60,"Technology / Semis","EQ",14.1,7.05,51.8,63.0,71.77,"green"),
    ("NSE","Natl. Stock Exchange","A",8,1785.00,1785.00,"Capital Markets","PRE",None,None,None,None,None,"green"),
    ("COCHINSHIP","Cochin Shipyard","B",10,1492.62,1370.00,"Defence","EQ",53.1,6.14,12.5,16.2,67.92,"amber"),
    ("CDSL","Central Depository","B",10,1364.08,1351.10,"Capital Markets","EQ",59.9,14.4,24.5,32.0,15.00,"green"),
    ("BSE","BSE Ltd","B",4,3425.67,3270.70,"Capital Markets","EQ",47.1,20.0,46.0,60.0,None,"green"),
    ("BAJAJHFL","Bajaj Housing Fin.","B",120,92.54,83.52,"Lending & Banks","EQ",25.8,3.09,12.0,None,86.70,"amber"),
    ("IREDA","IREDA","A",90,132.07,111.00,"Lending & Banks","EQ",15.9,2.26,16.0,8.69,72.00,"amber"),
    ("GUJENERGY","Gujarat Energy","B",40,245.47,237.32,"Energy & Power","EQ",11.4,0.89,10.2,11.7,38.94,"green"),
    ("BLEL","Behari Lal Engg.","B",20,462.01,469.60,"Metals & Mining","EQ",29.0,6.8,23.6,30.9,70.84,"green"),
    ("HDFCBANK","HDFC Bank","A",12,711.22,737.25,"Lending & Banks","EQ",14.4,1.89,13.6,None,None,"green"),
    ("BEL","Bharat Electronics","B",20,413.20,396.05,"Defence","EQ",47.2,12.1,27.4,36.4,51.14,"green"),
    ("LEAPIND","Leap India","B",51,144.22,148.62,"Logistics & Infra","EQ",112.0,None,6.32,8.34,55.64,"red"),
    ("WEBELSOLAR","Websol Energy","A",90,83.80,73.93,"Energy & Power","EQ",10.2,5.10,67.0,63.2,29.72,"red"),
    ("JUNIORBEES","Nifty Next 50 ETF","B",8,792.16,784.54,"Diversified ETF","ETF",None,None,None,None,None,"green"),
    ("SBIFUNDS","SBI Funds Mgmt.","A",10,559.55,551.35,"Capital Markets","EQ",None,None,None,None,None,"amber"),
    ("JSWINFRA","JSW Infrastructure","B",15,348.57,363.60,"Logistics & Infra","EQ",54.6,7.02,15.3,13.6,73.93,"amber"),
    ("GROWW","Groww (Billionbrains)","B",20,197.44,188.63,"Capital Markets","EQ",48.5,12.3,28.8,37.3,27.14,"amber"),
    ("JPPOWER","Jaiprakash Power","B",200,17.61,16.04,"Energy & Power","EQ",None,None,None,None,None,"red"),
    ("AFIL","Akme Fintrade","B",100,10.11,8.22,"Lending & Banks","EQ",9.64,None,None,None,None,"red"),
]

COLS = ("ticker","name","acct","qty","avg","ltp","sector","kind",
        "pe","pb","roe","roce","promoter","flag")

def rows():
    out = []
    for h in HOLDINGS:
        d = dict(zip(COLS, h))
        d["invested"] = d["qty"] * d["avg"]
        d["value"]    = d["qty"] * d["ltp"]
        d["pnl"]      = d["value"] - d["invested"]
        d["pnl_pct"]  = 100.0 * d["pnl"] / d["invested"]
        out.append(d)
    total = sum(r["value"] for r in out)
    for r in out:
        r["weight"] = 100.0 * r["value"] / total
    return sorted(out, key=lambda r: -r["value"])

MARKET = {
    "nifty": 23346.40,
    "nifty_ytd": -13.67,
    "nifty_pe": 19.74,
    "nifty_pe_10yr_avg": 23.31,
    "nifty_pb": 2.82,
    "nifty_div_yield": 1.21,
    "asof": "23 September 2026",
}
