//+------------------------------------------------------------------+
//|                                                     ICE_Core.mqh |
//|  SECTION 0 equivalent: inputs, shared series, helpers, sessions,  |
//|  the delta PROXY, HTF bias and the warmup gate.                   |
//|                                                                   |
//|  BAR CONVENTION - the single most important thing in this file.   |
//|  Every accessor below is indexed so that i = 0 is the LAST CLOSED |
//|  BAR, never the forming one. Internally that is MT5 shift i+1.    |
//|  The EA evaluates once per new bar, so i = 0 here is exactly what |
//|  Pine calls a confirmed bar. That is what makes the two builds    |
//|  comparable signal-for-signal.                                    |
//|                                                                   |
//|  PROXY CONTRACT. MT5 exposes a real order book (MarketBookAdd)    |
//|  but the STRATEGY TESTER DOES NOT REPLAY IT, so no backtest can   |
//|  ever see a real iceberg. `volume` on an XAUUSD CFD is TICK COUNT |
//|  exactly as on TradingView. Everything derived from it is a       |
//|  PROXY. Nothing in this EA claims real order flow.                |
//+------------------------------------------------------------------+
#property strict
#include "ICE_Types.mqh"

//==================== INPUTS - CORE ================================
input group "0 - Core"
input int    InpAtrLen        = 14;      // ATR length (one ATR for the whole EA)
input int    InpPivotLeft     = 5;       // Pivot LEFT legs (costs zero delay)
input int    InpPivotRight    = 3;       // Pivot RIGHT legs = THE SIGNAL LATENCY
input double InpMinScore      = 75.0;    // Min setup score 0-100 (1M 80 / 5M 75 / 15M 70)
input int    InpMagic         = 20260921;// Magic number

input group "0 - Volume & Delta Proxy"
input int             InpRvolLen   = 50;             // Relative-volume baseline (bars)
input bool            InpVolTod    = true;           // Normalise volume by time of day
input ENUM_ICE_DELTA  InpDeltaMode = ICE_DELTA_CLV;  // Delta proxy estimator
input double          InpWickWeight= 1.5;            // Wick weight lambda (1.0 == plain CLV)

input group "0 - Risk & Cost"
input double InpSpreadUsd = 0.25;   // Typical spread USD/oz (0 = read live from broker)
input double InpSlipUsd   = 0.10;   // Slippage per side USD/oz
input double InpRiskPct   = 0.50;   // Risk per trade (% of equity)
input double InpRrMin     = 2.0;    // Minimum NET R:R (gate on TP2)
input double InpMaxSpread = 0.60;   // Reject signals when live spread exceeds this (USD)

input group "0 - Session"
input ENUM_ICE_SESSMODE InpSessMode = ICE_SESS_LDN_NY; // Active sessions
input int               InpSessEdge = 5;               // Session edge trim (minutes)

input group "0 - Higher-Timeframe Bias"
input ENUM_TIMEFRAMES   InpHtfTf    = PERIOD_CURRENT; // HTF (PERIOD_CURRENT = auto map)
input ENUM_ICE_HTFMODE  InpHtfMode  = ICE_HTF_SOFT;   // HTF bias mode
input int               InpHtfEmaLen= 50;             // HTF EMA length
input double            InpHtfDeadAtr = 0.25;         // HTF neutral dead zone (x HTF ATR)

//==================== SHARED STATE =================================
int      g_hAtr   = INVALID_HANDLE;
int      g_hAdx   = INVALID_HANDLE;
int      g_hHtfMa = INVALID_HANDLE;
int      g_hHtfAtr= INVALID_HANDLE;

double   g_atr      = 0.0;   // ATR of the last CLOSED bar
double   g_atrPrev  = 0.0;
double   g_aRef     = 0.0;   // ATR floored at one spread - THE scale unit
double   g_costRt   = 0.0;   // round-turn cost, USD/oz
double   g_spreadUsd= 0.0;   // effective spread in USD/oz
int      g_barCount = 0;     // monotonic count of closed bars processed
datetime g_lastBar  = 0;

double   g_ratio    = 0.0;   // delta proxy ratio in [-1,+1]
double   g_deltaProxy = 0.0;
double   g_buyPressure = 0.5;
double   g_sellPressure= 0.5;
double   g_rvol     = 0.0;   // <0 means "unknown" (no usable volume feed)
bool     g_hasVol   = false;
double   g_cvd      = 0.0;
int      g_cvdEpoch = 0;

bool     g_inAsia = false, g_inLondon = false, g_inNy = false, g_inOverlap = false;
bool     g_sessOk = false;
double   g_sessQual = 0.0;
double   g_sessOpenPx = 0.0;
int      g_lastOpenBar = -1;
bool     g_newDay = false, g_newWeek = false;

int      g_htfBias = 0;      // -1 / 0 / +1
bool     g_htfReady= false;
bool     g_warmupOk= false;

double   g_todBase[48];      // per-half-hour tick-volume baselines

//==================== BAR ACCESSORS (i = 0 is LAST CLOSED) =========
double   IceOpen (const int i) { return(iOpen (_Symbol, PERIOD_CURRENT, i + 1)); }
double   IceHigh (const int i) { return(iHigh (_Symbol, PERIOD_CURRENT, i + 1)); }
double   IceLow  (const int i) { return(iLow  (_Symbol, PERIOD_CURRENT, i + 1)); }
double   IceClose(const int i) { return(iClose(_Symbol, PERIOD_CURRENT, i + 1)); }
long     IceVol  (const int i) { return(iVolume(_Symbol, PERIOD_CURRENT, i + 1)); }
datetime IceTime (const int i) { return(iTime (_Symbol, PERIOD_CURRENT, i + 1)); }
int      IceBars()             { return(iBars (_Symbol, PERIOD_CURRENT)); }

//==================== UNIVERSAL HELPERS ============================
//--- EMPTY_VALUE is this port's `na`. MQL5 doubles have no na, so every
//--- "unknown" is EMPTY_VALUE and every consumer must test IceNa() rather
//--- than silently treating it as zero - substituting 0 for unknown is what
//--- turns a missing reading into a confident wrong answer.
bool   IceNa(const double x)   { return(x == EMPTY_VALUE || !MathIsValidNumber(x)); }
double IceClamp(const double x, const double lo, const double hi)
  { return(IceNa(x) ? EMPTY_VALUE : MathMax(lo, MathMin(hi, x))); }
double IceClamp01(const double x) { return(IceClamp(x, 0.0, 1.0)); }

//--- THE ramp. hi <= lo is a CONFIGURATION ERROR and returns EMPTY_VALUE so
//--- the gate reading it fails - never 1.0, which would hand a module a free
//--- full sub-score for a misconfigured threshold.
double IceRamp(const double x, const double lo, const double hi)
  {
   if(IceNa(x) || hi <= lo) return(EMPTY_VALUE);
   return(IceClamp01((x - lo) / (hi - lo)));
  }

int IceSgnDead(const double x, const double dz)
  { if(IceNa(x)) return(0); return(x > dz ? 1 : (x < -dz ? -1 : 0)); }

//--- THE tolerance primitive. Every "is this close enough to be the same
//--- price?" test goes through this. NOTHING in this EA is denominated in
//--- points or ticks: _Point is 0.01 on most XAUUSD feeds and 0.001 on
//--- others, so a point-denominated tolerance mis-scales 10x per broker.
double IceTol(const double mult) { return(MathMax(mult * g_aRef, g_spreadUsd)); }

string IcePx(const double p)
  { return(IceNa(p) ? "n/a" : DoubleToString(p, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS))); }

double IceBarRange(const int i)
  { return(MathMax(IceHigh(i) - IceLow(i), SymbolInfoDouble(_Symbol, SYMBOL_POINT))); }
double IceBodyTop(const int i) { return(MathMax(IceOpen(i), IceClose(i))); }
double IceBodyBot(const int i) { return(MathMin(IceOpen(i), IceClose(i))); }

//--- DIRECTION CONVENTION: dir = +1 LONG/bullish, dir = -1 SHORT.
//--- These two are the ONLY direction-dependent primitives in the EA, which
//--- is what makes long/short symmetry structural rather than something a
//--- reviewer has to verify by eye.
double IceWickFrac(const int dir, const int i)
  {
   double r = IceBarRange(i);
   return(dir > 0 ? (IceBodyBot(i) - IceLow(i)) / r : (IceHigh(i) - IceBodyTop(i)) / r);
  }
double IceCloseLoc(const int dir, const int i)
  {
   double r = IceBarRange(i);
   return(dir > 0 ? (IceClose(i) - IceLow(i)) / r : (IceHigh(i) - IceClose(i)) / r);
  }
//--- Identity: IceCloseLoc(1,i) + IceCloseLoc(-1,i) == 1 on every bar.

//==================== TIMEZONE / DST ===============================
//--- MQL5 has NO timezone database. TradingView resolved each session in its
//--- own IANA zone; here the offsets are computed by hand from the published
//--- rules, because getting this wrong silently shifts every session window
//--- by an hour for ~8 months of the year and the sessions stop matching the
//--- Pine build. Base clock is TimeGMT().
datetime IceNthDow(const int yr, const int mon, const int dow, const int nth)
  {
   MqlDateTime t; t.year = yr; t.mon = mon; t.day = 1;
   t.hour = 0; t.min = 0; t.sec = 0;
   datetime first = StructToTime(t);
   MqlDateTime f;  TimeToStruct(first, f);
   int delta = (dow - f.day_of_week + 7) % 7;
   if(nth > 0) return(first + (datetime)((delta + (nth - 1) * 7) * 86400));
   //--- nth < 0 : the LAST such weekday in the month
   int dim = 31;
   while(true)
     {
      MqlDateTime c; c.year = yr; c.mon = mon; c.day = dim;
      c.hour = 0; c.min = 0; c.sec = 0;
      datetime cd = StructToTime(c);
      MqlDateTime v; TimeToStruct(cd, v);
      if(v.mon == mon) break;
      dim--;
     }
   MqlDateTime L; L.year = yr; L.mon = mon; L.day = dim;
   L.hour = 0; L.min = 0; L.sec = 0;
   datetime last = StructToTime(L);
   MqlDateTime lv; TimeToStruct(last, lv);
   int back = (lv.day_of_week - dow + 7) % 7;
   return(last - (datetime)(back * 86400));
  }

//--- EU: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC
bool IceEuDst(const datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc, t);
   datetime s = IceNthDow(t.year, 3,  0, -1) + 3600;
   datetime e = IceNthDow(t.year, 10, 0, -1) + 3600;
   return(utc >= s && utc < e);
  }
//--- US: 2nd Sunday of March 02:00 local (07:00 UTC) -> 1st Sunday of Nov
//---     02:00 local (06:00 UTC while still on DST)
bool IceUsDst(const datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc, t);
   datetime s = IceNthDow(t.year, 3,  0,  2) + 7 * 3600;
   datetime e = IceNthDow(t.year, 11, 0,  1) + 6 * 3600;
   return(utc >= s && utc < e);
  }

//--- minutes past midnight in the given local zone
int IceLocalMin(const datetime utc, const int offsetSec)
  {
   MqlDateTime t; TimeToStruct(utc + (datetime)offsetSec, t);
   return(t.hour * 60 + t.min);
  }
int IceLocalDow(const datetime utc, const int offsetSec)
  {
   MqlDateTime t; TimeToStruct(utc + (datetime)offsetSec, t);
   return(t.day_of_week);
  }

//==================== SESSION EVALUATION ===========================
void IceUpdateSessions(const datetime barUtc)
  {
   //--- London is GMT (UTC+0) in winter and BST (UTC+1) in summer.
   //--- New York is EST (UTC-5) in winter and EDT (UTC-4) in summer.
   //--- Tokyo never observes DST. The EU and US switch on DIFFERENT dates,
   //--- so for roughly four weeks a year the overlap widens by an hour -
   //--- computing each zone separately is what gets those weeks right.
   int offLdn = (IceEuDst(barUtc) ?  3600 : 0);
   int offNy  = (IceUsDst(barUtc) ? -4 : -5) * 3600;
   int offTok = 9 * 3600;

   int dLdn = IceLocalDow(barUtc, offLdn);
   int dNy  = IceLocalDow(barUtc, offNy);
   int dTok = IceLocalDow(barUtc, offTok);
   bool wkLdn = (dLdn >= 1 && dLdn <= 5);
   bool wkNy  = (dNy  >= 1 && dNy  <= 5);
   bool wkTok = (dTok >= 1 && dTok <= 5);

   int mLdn = IceLocalMin(barUtc, offLdn);
   int mNy  = IceLocalMin(barUtc, offNy);
   int mTok = IceLocalMin(barUtc, offTok);

   g_inAsia    = wkTok && mTok >=  9 * 60 && mTok < 15 * 60;          // 09:00-15:00 Tokyo
   g_inLondon  = wkLdn && mLdn >=  8 * 60 && mLdn < 16 * 60 + 30;     // 08:00-16:30 London
   g_inNy      = wkNy  && mNy  >=  8 * 60 && mNy  < 17 * 60;          // 08:00-17:00 New York
   g_inOverlap = g_inLondon && g_inNy;

   bool sel = false;
   switch(InpSessMode)
     {
      case ICE_SESS_OFF:     sel = true; break;
      case ICE_SESS_OVERLAP: sel = g_inOverlap; break;
      case ICE_SESS_ALL:     sel = (g_inAsia || g_inLondon || g_inNy); break;
      default:               sel = (g_inLondon || g_inNy); break;
     }

   //--- Session QUALITY: direction-free, 0..1, the ONLY session number the
   //--- score reads. 0.00 outside every session is deliberate - that window
   //--- is the thinnest tape of the day and carries the largest penalty.
   g_sessQual = g_inOverlap ? 1.00 : ((g_inLondon || g_inNy) ? 0.80 : (g_inAsia ? 0.35 : 0.00));

   g_sessOk = sel;
  }

//==================== VOLUME / RVOL ================================
void IceUpdateVolume()
  {
   long v = IceVol(0);
   if(!g_hasVol && v > 0) g_hasVol = true;
   if(!g_hasVol) { g_rvol = -1.0; return; }          // -1 == unknown

   //--- flat baseline
   double sum = 0.0; int n = 0;
   for(int i = 0; i < InpRvolLen && i < IceBars() - 2; i++) { sum += (double)IceVol(i); n++; }
   double flat = (n > 0 && sum > 0.0) ? (double)v / (sum / n) : -1.0;

   if(!InpVolTod) { g_rvol = flat; return; }

   //--- time-of-day baseline. XAUUSD tick volume has a 5-10x diurnal profile,
   //--- so a flat volume/SMA is a session clock wearing a participation
   //--- costume. Each half-hour slot keeps its own EWMA.
   MqlDateTime t; TimeToStruct(IceTime(0), t);
   int slot = (t.hour * 2 + (t.min >= 30 ? 1 : 0)) % 48;
   double ref = g_todBase[slot];
   double out = (ref > 0.0) ? (double)v / ref : flat;
   g_todBase[slot] = (ref <= 0.0) ? (double)v : ref + 0.05 * ((double)v - ref);
   g_rvol = out;
  }

//==================== DELTA PROXY ==================================
//--- Gap-aware. trHi/trLo reduce IDENTICALLY to H/L when there is no gap and
//--- attribute the gap to a side when there is one (gold gaps at the Sunday
//--- open and the 17:00 NY rollover).
void IceUpdateDelta(const double realTickRatio)
  {
   double prevC = IceClose(1);
   double hi = IceHigh(0), lo = IceLow(0), op = IceOpen(0), cl = IceClose(0);
   double trHi = MathMax(hi, prevC);
   double trLo = MathMin(lo, prevC);
   double trRn = trHi - trLo;

   double rClv  = (trRn > 0.0) ? (2.0 * cl - trHi - trLo) / trRn : EMPTY_VALUE;
   double uWick = trHi - IceBodyTop(0);
   double dWick = IceBodyBot(0) - trLo;
   double bUp   = MathMax(cl - op, 0.0) + InpWickWeight * dWick;
   double bDn   = MathMax(op - cl, 0.0) + InpWickWeight * uWick;
   double rWk   = ((bUp + bDn) > 0.0) ? (bUp - bDn) / (bUp + bDn) : EMPTY_VALUE;

   static double rTick = 0.0;
   if(cl > prevC)      rTick =  1.0;
   else if(cl < prevC) rTick = -1.0;
   else if(cl > op)    rTick =  1.0;
   else if(cl < op)    rTick = -1.0;

   double sel;
   switch(InpDeltaMode)
     {
      case ICE_DELTA_WICK: sel = rWk;   break;
      case ICE_DELTA_TICK: sel = rTick; break;
      case ICE_DELTA_REAL: sel = realTickRatio; break;   // supplied by the caller
      default:             sel = rClv;  break;
     }
   if(IceNa(sel)) sel = rTick;

   g_ratio        = IceClamp(sel, -1.0, 1.0);
   double effVol  = g_hasVol ? (double)IceVol(0) : 1.0;
   g_deltaProxy   = g_ratio * effVol;
   g_buyPressure  = (1.0 + g_ratio) / 2.0;
   g_sellPressure = (1.0 - g_ratio) / 2.0;   // b + s == 1 EXACTLY, by construction
  }

//==================== HTF BIAS (non-repainting) ====================
//--- Only CLOSED higher-timeframe bars are read (shift >= 1), which is the
//--- MT5 equivalent of Pine's lookahead_on + [1] pair. Staleness is therefore
//--- in [0, one HTF period), never negative, and never a future leak.
ENUM_TIMEFRAMES IceHtfResolve()
  {
   if(InpHtfTf != PERIOD_CURRENT) return(InpHtfTf);
   int s = PeriodSeconds(PERIOD_CURRENT);
   if(s <= 60)   return(PERIOD_M15);
   if(s <= 300)  return(PERIOD_H1);
   if(s <= 900)  return(PERIOD_H4);
   if(s <= 3600) return(PERIOD_D1);
   return(PERIOD_W1);
  }

void IceUpdateHtf()
  {
   g_htfReady = false;
   g_htfBias  = 0;
   ENUM_TIMEFRAMES tf = IceHtfResolve();
   if(PeriodSeconds(tf) <= PeriodSeconds(PERIOD_CURRENT)) return;   // hard guard

   double ma[1], at[1];
   if(g_hHtfMa == INVALID_HANDLE || g_hHtfAtr == INVALID_HANDLE) return;
   if(CopyBuffer(g_hHtfMa, 0, 1, 1, ma) != 1) return;
   if(CopyBuffer(g_hHtfAtr, 0, 1, 1, at) != 1) return;

   //--- structural leg from the last closed HTF bars
   double h1 = EMPTY_VALUE, h2 = EMPTY_VALUE, l1 = EMPTY_VALUE, l2 = EMPTY_VALUE;
   int found = 0;
   for(int i = 3; i < 60 && found < 2; i++)
     {
      double hh = iHigh(_Symbol, tf, i), hl = iHigh(_Symbol, tf, i + 1), hr = iHigh(_Symbol, tf, i - 1);
      if(hh > hl && hh > hr) { if(IceNa(h1)) h1 = hh; else if(IceNa(h2)) { h2 = hh; found++; } }
     }
   found = 0;
   for(int i = 3; i < 60 && found < 2; i++)
     {
      double ll = iLow(_Symbol, tf, i), lp = iLow(_Symbol, tf, i + 1), ln = iLow(_Symbol, tf, i - 1);
      if(ll < lp && ll < ln) { if(IceNa(l1)) l1 = ll; else if(IceNa(l2)) { l2 = ll; found++; } }
     }
   if(IceNa(h1) || IceNa(h2) || IceNa(l1) || IceNa(l2)) return;

   int bSt = 0;
   if(h1 > h2 && l1 > l2)      bSt =  1;
   else if(h1 < h2 && l1 < l2) bSt = -1;

   //--- The EMA source is SIDE ONLY. "slope AND side must agree" is a
   //--- tautology: both are positive multiples of (close - ema[1]).
   double hc = iClose(_Symbol, tf, 1);
   int    bEma = IceSgnDead(hc - ma[0], InpHtfDeadAtr * at[0]);
   g_htfBias  = (bSt != 0 && bSt == bEma) ? bSt : 0;
   g_htfReady = true;
  }

bool IceHtfAllow(const int dir)
  {
   if(InpHtfMode == ICE_HTF_OFF || InpHtfMode == ICE_HTF_SOFT) return(true);
   if(!g_htfReady) return(InpHtfMode == ICE_HTF_BLOCK);   // unknown fails OPEN for
                                                          // soft-block, CLOSED for require
   if(InpHtfMode == ICE_HTF_BLOCK) return(g_htfBias == 0 || g_htfBias == dir);
   return(g_htfBias == dir);
  }
//--- Unknown bias is 0.0 for BOTH sides, so missing data can never hand one
//--- direction a bonus and its mirror an equal penalty.
double IceHtfScalar(const int dir)
  {
   if(!g_htfReady || g_htfBias == 0) return(0.0);
   return(g_htfBias == dir ? 1.0 : -1.0);
  }

//==================== POSITION SIZING ==============================
//--- Derived from the SYMBOL, never a hardcoded 100 oz. Guards a zero or
//--- negative stop distance, honours the broker's volume step, and caps
//--- exposure at 50% margin utilisation - sizing to exactly 100% guarantees
//--- a margin call on the first adverse tick.
double IceLots(const double stopDistUsd)
  {
   if(stopDistUsd <= 0.0) return(0.0);
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSz <= 0.0) return(0.0);

   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double lossPerLot = (stopDistUsd / tickSz) * tickVal;
   if(lossPerLot <= 0.0) return(0.0);
   double lots = riskMoney / lossPerLot;

   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstp = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vstp > 0.0) lots = MathFloor(lots / vstp) * vstp;

   //--- margin cap at 50% utilisation
   double marginOne = 0.0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, 1.0,
                      SymbolInfoDouble(_Symbol, SYMBOL_ASK), marginOne) && marginOne > 0.0)
     {
      double cap = (AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.50) / marginOne;
      if(vstp > 0.0) cap = MathFloor(cap / vstp) * vstp;
      lots = MathMin(lots, cap);
     }
   lots = MathMax(vmin, MathMin(vmax, lots));
   return(lots);
  }

//==================== PER-BAR CORE UPDATE ==========================
bool IceCoreNewBar()
  {
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t == g_lastBar) return(false);
   g_lastBar = t;
   return(true);
  }

void IceCoreUpdate(const double realTickRatio)
  {
   g_barCount++;

   double a[2];
   if(g_hAtr != INVALID_HANDLE && CopyBuffer(g_hAtr, 0, 1, 2, a) == 2)
     { g_atr = a[1]; g_atrPrev = a[0]; }

   //--- effective spread: the live broker spread unless the user pinned one.
   double liveSpread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   g_spreadUsd = (InpSpreadUsd > 0.0) ? InpSpreadUsd
                                      : MathMax(liveSpread, SymbolInfoDouble(_Symbol, SYMBOL_POINT));
   g_aRef   = MathMax(g_atr, g_spreadUsd);
   g_costRt = g_spreadUsd + 2.0 * InpSlipUsd;

   datetime bt = IceTime(0);
   MqlDateTime td, tp;
   TimeToStruct(bt, td);
   TimeToStruct(IceTime(1), tp);
   g_newDay  = (td.day != tp.day);
   g_newWeek = (td.day_of_year / 7 != tp.day_of_year / 7) || (td.year != tp.year);

   bool wasIn = (g_inAsia || g_inLondon || g_inNy);
   IceUpdateSessions(bt);
   bool nowIn = (g_inAsia || g_inLondon || g_inNy);
   if(nowIn && !wasIn) { g_lastOpenBar = g_barCount; g_sessOpenPx = IceOpen(0); }
   if(g_sessOpenPx <= 0.0) g_sessOpenPx = IceOpen(0);

   //--- edge trim: bites on EVERY session open, not just the first of a run
   bool edgeOk = true;
   if(InpSessEdge > 0 && g_lastOpenBar >= 0)
      edgeOk = ((g_barCount - g_lastOpenBar) * PeriodSeconds(PERIOD_CURRENT) >= InpSessEdge * 60);
   g_sessOk = g_sessOk && edgeOk;

   IceUpdateVolume();
   IceUpdateDelta(realTickRatio);

   if(g_newDay) { g_cvdEpoch++; g_cvd = 0.0; }
   g_cvd += g_deltaProxy;

   IceUpdateHtf();

   g_warmupOk = (IceBars() > MathMax(InpRvolLen, InpAtrLen * 3) + InpPivotLeft + InpPivotRight + 5)
                && g_atr > 0.0;
  }

bool IceCoreInit()
  {
   ArrayInitialize(g_todBase, 0.0);
   g_hAtr = iATR(_Symbol, PERIOD_CURRENT, InpAtrLen);
   g_hAdx = iADX(_Symbol, PERIOD_CURRENT, 14);
   ENUM_TIMEFRAMES tf = IceHtfResolve();
   g_hHtfMa  = iMA (_Symbol, tf, InpHtfEmaLen, 0, MODE_EMA, PRICE_CLOSE);
   g_hHtfAtr = iATR(_Symbol, tf, InpAtrLen);
   return(g_hAtr != INVALID_HANDLE && g_hAdx != INVALID_HANDLE &&
          g_hHtfMa != INVALID_HANDLE && g_hHtfAtr != INVALID_HANDLE);
  }

void IceCoreDeinit()
  {
   if(g_hAtr    != INVALID_HANDLE) IndicatorRelease(g_hAtr);
   if(g_hAdx    != INVALID_HANDLE) IndicatorRelease(g_hAdx);
   if(g_hHtfMa  != INVALID_HANDLE) IndicatorRelease(g_hHtfMa);
   if(g_hHtfAtr != INVALID_HANDLE) IndicatorRelease(g_hHtfAtr);
  }
//+------------------------------------------------------------------+
