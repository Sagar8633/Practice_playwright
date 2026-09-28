//+------------------------------------------------------------------+
//| TWK_Tracker_MT5.mq5                                              |
//| Phase 2 diagnostic indicator for the Momentum Tracker EA.        |
//| Plots the purple Smart Trail line and LONG/SHORT flips computed  |
//| by TWK_Core.mqh (the same code the EA uses), shows the SL/TP,    |
//| 1m/3m volume rows and ADX in the Data Window, and exports every  |
//| closed bar to CSV for the Pine-vs-MT5 comparison.                |
//|                                                                  |
//| Closed bars only: the forming bar is left empty, so nothing on   |
//| this indicator repaints.                                         |
//|                                                                  |
//| v1.10: LONG/SHORT position boxes like TWK_Tracker.pine (green    |
//| TP zone, red SL zone, entry line; hover a box for its prices).   |
//| TWK_MomentumEA embeds this file as a resource and draws it on    |
//| its own chart, live and in the Strategy Tester.                  |
//| v1.20: boxes follow the EA's quick re-flip rule (hard SL / skip);|
//| drawn history is kept (a test keeps every box from its start).  |
//+------------------------------------------------------------------+
#property copyright "trade_with_kareena"
#property version   "1.20"
#property indicator_chart_window
#property indicator_buffers 12
#property indicator_plots   12

#property indicator_label1  "Smart Trail"
#property indicator_type1   DRAW_LINE
#property indicator_color1  C'126,87,194'
#property indicator_width1  2

#property indicator_label2  "LONG"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  C'38,166,154'
#property indicator_width2  2

#property indicator_label3  "SHORT"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  C'239,83,80'
#property indicator_width3  2

#property indicator_label4  "Signal SL"
#property indicator_type4   DRAW_NONE
#property indicator_label5  "Signal TP"
#property indicator_type5   DRAW_NONE
#property indicator_label6  "Buy Vol 1m"
#property indicator_type6   DRAW_NONE
#property indicator_label7  "Sell Vol 1m"
#property indicator_type7   DRAW_NONE
#property indicator_label8  "Buy Vol 3m"
#property indicator_type8   DRAW_NONE
#property indicator_label9  "Sell Vol 3m"
#property indicator_type9   DRAW_NONE
#property indicator_label10 "ADX"
#property indicator_type10  DRAW_NONE
#property indicator_label11 "Trail Dir"
#property indicator_type11  DRAW_NONE
#property indicator_label12 "Signal Risk"
#property indicator_type12  DRAW_NONE

#include "TWK_Core.mqh"

// No `input group` lines: TWK_MomentumEA passes these through iCustom() in this exact order, and
// MT5 counts each group line as a parameter there (undocumented), which would shift every value.
input double             InpStMult    = 1.5;   // Smart Trail multiplier
input int                InpStATR     = 10;    // Smart Trail ATR length
input int                InpPivLen    = 5;     // Pivot strength (bars each side)
input double             InpRR        = 2.0;   // Reward : Risk
input int                InpVolLen    = 20;    // Volume sum length (bars)
input ENUM_TWK_PIVOT_TIE InpPivotTie  = TWK_TIE_LEFT_EQUAL_OK; // Pivot tie rule
input int                InpDiLen     = 14;    // ADX DI length
input int                InpAdxSmooth = 14;    // ADX smoothing
input int                InpCalcBars  = 5000;  // Bars drawn on the first pass (0 = all); new bars are added after
input bool               InpExportCSV = true;  // Export closed bars to CSV (Common\Files)
input int                InpExportBars = 3000; // Bars to export
input bool               InpShowPositions   = true; // Draw LONG/SHORT position boxes (like TradingView)
input int                InpPosBars         = 24;   // Box width in bars (ends early at the next signal)
input int                InpPosHistory      = 200;  // Live: signals that keep their box (1 = latest only). A test keeps all
input int                InpHardSLPoints    = 0;    // Hard SL points: no pivot / quick re-flip (0 = purple line; the EA passes its own)
input int                InpReFlipBars      = 0;    // Quick re-flip window in bars (0 = off, like TradingView)
input ENUM_TWK_REFLIP    InpReFlipAction    = TWK_REFLIP_KEEP_PIVOT; // Quick re-flip: hard SL / skip / keep the old pivot / purple
input datetime           InpBoxesFrom       = 0;    // Strategy Tester: boxes only from this time (the EA passes the test start)
input string             InpObjPrefix       = "TWKPOS_"; // Object name prefix (the EA's own copy uses "TWKEA_")
input double             InpMinVolRatio     = 0;    // EA volume ratio filter (0 = filters unknown: every signal drawn alike)
input bool               InpRequireM1Box    = true; // EA M1 box filter
input bool               InpRequireM3Box    = true; // EA M3 box filter
input double             InpADXMinimum      = 20.0; // EA ADX filter (strictly greater)

double BufTrail[], BufLong[], BufShort[], BufSL[], BufTP[];
double BufBv1[], BufSv1[], BufBv3[], BufSv3[], BufAdx[], BufDir[], BufRisk[];

TwkParams g_p;
datetime  g_lastBar = 0;
string    g_prefix = "TWKPOS_";                   // object-name prefix of this instance
datetime  g_prevNewestSig = 0;                    // newest signal seen by the previous DrawPositions call
long      g_boxTimes[];                           // signal times that have a box (live history cap)

#define TWK_WARMUP    300                         // bars a window needs before it matches full history
#define TWK_INCR_BARS 2000                        // window of the per-bar update (= the EA's CalcBars)
color   g_colTP = C'18,84,76';                    // dark teal: drawn behind the candles, so no transparency needed
color   g_colSL = C'110,34,34';                   // dark red
color   g_colSkipTP = C'52,52,52';                // skipped quick re-flip: grey
color   g_colSkipSL = C'38,38,38';
color   g_colFiltTP = C'22,40,38';                // failed an entry filter: very dim
color   g_colFiltSL = C'44,26,26';

int OnInit()
  {
   TwkDefaultParams(g_p);
   g_p.stMult    = InpStMult;
   g_p.stATR     = InpStATR;
   g_p.pivLen    = InpPivLen;
   g_p.rr        = InpRR;
   g_p.volLen    = InpVolLen;
   g_p.diLen     = InpDiLen;
   g_p.adxSmooth = InpAdxSmooth;
   g_p.pivotTie  = InpPivotTie;
   g_p.reflipBars = InpReFlipBars;
   g_prefix = (InpObjPrefix == "") ? "TWKPOS_" : InpObjPrefix;

   SetIndexBuffer(0, BufTrail, INDICATOR_DATA);
   SetIndexBuffer(1, BufLong, INDICATOR_DATA);
   SetIndexBuffer(2, BufShort, INDICATOR_DATA);
   SetIndexBuffer(3, BufSL, INDICATOR_DATA);
   SetIndexBuffer(4, BufTP, INDICATOR_DATA);
   SetIndexBuffer(5, BufBv1, INDICATOR_DATA);
   SetIndexBuffer(6, BufSv1, INDICATOR_DATA);
   SetIndexBuffer(7, BufBv3, INDICATOR_DATA);
   SetIndexBuffer(8, BufSv3, INDICATOR_DATA);
   SetIndexBuffer(9, BufAdx, INDICATOR_DATA);
   SetIndexBuffer(10, BufDir, INDICATOR_DATA);
   SetIndexBuffer(11, BufRisk, INDICATOR_DATA);
   PlotIndexSetInteger(1, PLOT_ARROW, 233);
   PlotIndexSetInteger(2, PLOT_ARROW, 234);
   PlotIndexSetInteger(1, PLOT_ARROW_SHIFT, 15);
   PlotIndexSetInteger(2, PLOT_ARROW_SHIFT, -15);
   for(int k = 0; k < 12; k++)
      PlotIndexSetDouble(k, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   // the EA's own copy gets its own name, so removing the EA never removes a copy you attached yourself
   IndicatorSetString(INDICATOR_SHORTNAME, g_prefix == "TWKPOS_" ? "TWK Tracker MT5" : "TWK Tracker (EA)");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   ObjectsDeleteAll(0, g_prefix);
   ArrayFree(g_boxTimes);
   g_prevNewestSig = 0;
   g_lastBar = 0;
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(MQLInfoInteger(MQL_TESTER))
      return;                                        // keep the boxes on the test chart for inspection
   ObjectsDeleteAll(0, g_prefix);
  }

//--- spread + broker stop level the EA sees when it decides on signal bar j. It trades on the first
//    tick of bar j+1, so that bar's spread is the proxy (bar j's own for the newest signal).
int DecisionSpread(const TwkSeries &s, const int j)
  {
   const int sp = (j + 1 < s.n) ? s.rates[j + 1].spread : s.rates[j].spread;
   return sp + (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
  }


//--- SL/TP of signal bar j exactly as TWK_MomentumEA places them:
//    - the pivot stop;
//    - no pivot, or a quick re-flip with InpReFlipAction = hard SL: InpHardSLPoints from the close
//      (TP = RR x that), or the purple line when that is 0 or inside the spread. Never the old pivot
//      on a re-flip;
//    - a quick re-flip with InpReFlipAction = skip: `skipped` = true (drawn grey, not traded).
//    The EA measures from the live ask/bid and this from the bar close, so they differ by the spread.
bool SignalStops(const TwkSeries &s, const int j, const int spreadPts, double &sl, double &tp, string &src, bool &skipped)
  {
   sl      = s.sl[j];
   tp      = s.tp[j];
   src     = "";
   skipped = false;
   if(!s.longSig[j] && !s.shortSig[j])
      return false;
   const bool   isL    = s.longSig[j];
   const double entry  = s.rates[j].close;
   const bool   reflip = s.reFlip[j] && InpReFlipBars > 0 && InpReFlipAction != TWK_REFLIP_KEEP_PIVOT;
   const string tag    = reflip ? StringFormat("quick re-flip %d bars, old pivot %s not used", s.oppAgo[j],
                                               DoubleToString(s.sl[j], _Digits))
                                : "no pivot";
   if(reflip && InpReFlipAction == TWK_REFLIP_SKIP)
     {
      skipped = true;
      src = StringFormat("SKIPPED - quick re-flip %d bars (old pivot SL would be %s away)", s.oppAgo[j],
                         DoubleToString(MathAbs(entry - s.sl[j]), _Digits));
      return !TwkIsNa(sl) && !TwkIsNa(tp);
     }
   if(!s.slPivot[j] || reflip)
     {
      const int hard = (reflip && InpReFlipAction == TWK_REFLIP_PURPLE) ? 0 : InpHardSLPoints;
      if(hard > spreadPts)                                         // the EA uses purple inside the spread + stop level
        {
         const double d = hard * _Point;
         sl  = isL ? entry - d : entry + d;
         tp  = isL ? entry + InpRR * d : entry - InpRR * d;
         src = StringFormat("%s: hard %d pts", tag, hard);
         return true;
        }
      if(reflip)
        {
         const double risk = isL ? entry - s.st[j] : s.st[j] - entry;
         if(TwkIsNa(s.st[j]) || risk <= 0)
            return false;                                          // the EA rejects this signal
         sl  = s.st[j];
         tp  = isL ? entry + InpRR * risk : entry - InpRR * risk;
         src = tag + ": purple line";
         return true;
        }
     }
   src = s.slPivot[j] ? "pivot" : "purple line, no pivot";
   return !TwkIsNa(sl) && !TwkIsNa(tp) && !TwkIsNa(s.risk[j]) && s.risk[j] > 0;
  }

void UpsertRect(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
                const color c, const string tip)
  {
   if(ObjectFind(0, name) >= 0)
     {
      if((datetime)ObjectGetInteger(0, name, OBJPROP_TIME, 1) != t2)
         ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
      return;
     }
   if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
      return;
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);          // behind the candles
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void UpsertEntryLine(const string name, const datetime t1, const datetime t2, const double price, const string tip)
  {
   if(ObjectFind(0, name) >= 0)
     {
      if((datetime)ObjectGetInteger(0, name, OBJPROP_TIME, 1) != t2)
         ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
      return;
     }
   if(!ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price))
      return;
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void PutLabel(const string name, const datetime t, const double price, const string text, const color c)
  {
   if(ObjectFind(0, name) < 0 && !ObjectCreate(0, name, OBJ_TEXT, 0, t, price))
      return;
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void DeleteBox(const string base)
  {
   ObjectDelete(0, base + "_R");
   ObjectDelete(0, base + "_S");
   ObjectDelete(0, base + "_E");
  }

//--- The EA's entry filters on signal bar j (volume ratio, M1 box, M3 box, ADX), with the same
//    comparisons as TWK_MomentumEA. Returns "" when the signal passes. Not checked here: the spread,
//    an already open position, and account permissions. InpMinVolRatio = 0 (standalone) = unknown.
string FilterFail(const TwkSeries &s, const int j, const int i)
  {
   if(InpMinVolRatio <= 0)
      return "";
   const bool   isL = s.longSig[j];
   const double bv1 = BufBv1[i], sv1 = BufSv1[i];
   const double own = isL ? bv1 : sv1, opp = isL ? sv1 : bv1;
   if(TwkIsNa(own) || TwkIsNa(opp) || (own <= 0 && opp <= 0))
      return "volume data unavailable";
   const double ratio = (opp <= 0) ? DBL_MAX : own / opp;
   if(ratio + 1e-12 < InpMinVolRatio)
      return StringFormat("volume ratio %.2f below %.2f", ratio, InpMinVolRatio);
   if(InpRequireM1Box && !(isL ? bv1 > sv1 : sv1 > bv1))
      return "M1 box against the signal";
   const double bv3 = BufBv3[i], sv3 = BufSv3[i];
   if(TwkIsNa(bv3) || TwkIsNa(sv3))
      return "M3 box unavailable";
   if(InpRequireM3Box && !(isL ? bv3 > sv3 : sv3 > bv3))
      return "M3 box against the signal";
   if(TwkIsNa(s.adx[j]) || !(s.adx[j] > InpADXMinimum))
      return StringFormat("ADX %.2f not above %.2f", s.adx[j], InpADXMinimum);
   return "";
  }

//--- Pine-style LONG/SHORT boxes: green = entry..TP, red = entry..SL (grey = a quick re-flip the EA
//    skips), dashed entry line, prices in the tooltip. A box is created once, since closed bars never
//    change; only its right edge moves when the next signal arrives (the box ends there). Live, the
//    newest InpPosHistory boxes are kept; a Strategy Tester run keeps every box from InpBoxesFrom on.
void DrawPositions(const TwkSeries &s, const int n, const int off, const int from)
  {
   if(!InpShowPositions)
      return;
   int sig[];
   for(int j = MathMax(0, from); j < n; j++)
      if(s.longSig[j] || s.shortSig[j])
        {
         const int k = ArraySize(sig);
         ArrayResize(sig, k + 1, 512);
         sig[k] = j;
        }
   const int total = ArraySize(sig);
   if(total == 0)
      return;
   const bool keepAll = (bool)MQLInfoInteger(MQL_TESTER);
   const int  cap     = MathMax(1, InpPosHistory);
   const int  sec     = PeriodSeconds(_Period);
   const int  d       = _Digits;
   bool       added   = false;

   for(int k = total - 1; k >= 0; k--)
     {
      const int      j  = sig[k];
      const datetime t1 = s.rates[j].time;
      if(keepAll && InpBoxesFrom > 0 && t1 < InpBoxesFrom)
         break;                                      // before the test start
      if(!keepAll && k < total - cap)
         break;                                      // older than the live history cap
      const string base = g_prefix + (string)(long)t1;
      const bool   had  = ObjectFind(0, base + "_R") >= 0;
      if(had && k + 1 < total && s.rates[sig[k + 1]].time <= g_prevNewestSig)
         break;                                      // its successor was known last time: final
      double sl, tp;
      string src;
      bool   skipped;
      if(!SignalStops(s, j, DecisionSpread(s, j), sl, tp, src, skipped))
         continue;
      const bool   isL   = s.longSig[j];
      const double entry = s.rates[j].close;
      const string fail  = skipped ? "" : FilterFail(s, j, off + j);
      const bool   dim   = (fail != "");
      // right edge InpPosBars bars later (counted in bars, so the daily break and weekends are
      // skipped), or at the next signal if that comes first
      const int jEnd = j + MathMax(1, InpPosBars);
      datetime  t2   = (jEnd < n) ? s.rates[jEnd].time
                                  : s.rates[n - 1].time + (datetime)((long)(jEnd - (n - 1)) * sec);
      if(k + 1 < total && s.rates[sig[k + 1]].time < t2)
         t2 = s.rates[sig[k + 1]].time;
      const string piv = (s.pivBar[j] >= 0 && s.pivBar[j] < n)
                         ? StringFormat("\nPivot bar %s, %d bars before the signal",
                                        TimeToString(s.rates[s.pivBar[j]].time, TIME_DATE | TIME_MINUTES), j - s.pivBar[j])
                         : "";
      const string opp = (s.oppAgo[j] >= 0) ? StringFormat("\nPrevious opposite signal %d bars before", s.oppAgo[j]) : "";
      const string tip = StringFormat("%s%s @ %s (1:%.1f), measured from the signal close\nSL %s = %s away (%s)\nTP %s = %s away%s%s",
                                      skipped ? "NOT TRADED: " : dim ? "NOT TRADED (" + fail + "): " : "",
                                      isL ? "LONG" : "SHORT", DoubleToString(entry, d), InpRR,
                                      DoubleToString(sl, d), DoubleToString(MathAbs(entry - sl), d), src,
                                      DoubleToString(tp, d), DoubleToString(MathAbs(tp - entry), d), piv, opp);
      UpsertRect(base + "_R", t1, MathMax(entry, tp), t2, MathMin(entry, tp), skipped ? g_colSkipTP : dim ? g_colFiltTP : g_colTP, tip);
      UpsertRect(base + "_S", t1, MathMax(entry, sl), t2, MathMin(entry, sl), skipped ? g_colSkipSL : dim ? g_colFiltSL : g_colSL, tip);
      UpsertEntryLine(base + "_E", t1, t2, entry, tip);
      if(!had)
        {
         const int b = ArraySize(g_boxTimes);
         ArrayResize(g_boxTimes, b + 1, 512);
         g_boxTimes[b] = (long)t1;
         added = true;
        }
      if(k == total - 1)                             // price labels on the newest box only, like Pine
        {
         PutLabel(g_prefix + "LBL_E", t1, entry, StringFormat("%s%s @ %s (1:%.1f)", skipped ? "SKIPPED " : dim ? "FILTERED " : "",
                                                              isL ? "LONG" : "SHORT", DoubleToString(entry, d), InpRR), clrWhite);
         PutLabel(g_prefix + "LBL_T", t1, tp, "TP " + DoubleToString(tp, d), C'38,166,154');
         PutLabel(g_prefix + "LBL_S", t1, sl, "SL " + DoubleToString(sl, d), C'239,83,80');
        }
     }
   g_prevNewestSig = s.rates[sig[total - 1]].time;
   if(keepAll || !added)
      return;
   //--- live: keep only the newest InpPosHistory boxes
   ArraySort(g_boxTimes);
   const int extra = ArraySize(g_boxTimes) - cap;
   if(extra > 0)
     {
      for(int b = 0; b < extra; b++)
         DeleteBox(g_prefix + (string)g_boxTimes[b]);
      ArrayRemove(g_boxTimes, 0, extra);
     }
  }



//--- volume row of `tf` aligned to each chart bar's close (completed bars only)
bool AlignRow(const ENUM_TIMEFRAMES tf, const datetime &t[], const int from, const int to,
              const int chartSec, double &bOut[], double &sOut[])
  {
   MqlRates h[];
   ArraySetAsSeries(h, false);
   const int want = (int)MathMin(100000, (double)(to - from + 1) * chartSec / PeriodSeconds(tf) + g_p.volLen + 50);
   const int got = CopyRates(_Symbol, tf, 0, want, h);
   if(got <= g_p.volLen)
      return false;
   double b[], s[];
   TwkUpDownVolume(h, got, g_p.volLen, b, s);
   for(int i = from; i <= to; i++)
     {
      const int k = TwkLastCompletedHtf(h, got, PeriodSeconds(tf), t[i] + chartSec);
      bOut[i] = (k < 0) ? EMPTY_VALUE : b[k];
      sOut[i] = (k < 0) ? EMPTY_VALUE : s[k];
     }
   return true;
  }

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   if(rates_total < TWK_WARMUP)
      return 0;
   if(prev_calculated > 0 && time[rates_total - 1] == g_lastBar)
      return rates_total;                          // recalc once per new bar only

   //--- First pass: InpCalcBars bars (0 = all). Later passes recompute only a short window and write
   //    its converged part, so older bars keep their line, arrows and boxes instead of being erased.
   const bool full = (prev_calculated == 0 || g_lastBar == 0);
   const int  last = rates_total - 2;               // last CLOSED bar
   const int  want = full ? (InpCalcBars > 0 ? InpCalcBars : last + 1) : TWK_INCR_BARS;
   const int  n    = MathMin(want, last + 1);
   const int  off  = last - n + 1;
   const int  from = full ? 0 : MathMin(TWK_WARMUP, n - 1);

   MqlRates r[];
   ArrayResize(r, n);
   for(int i = 0; i < n; i++)
     {
      r[i].time        = time[off + i];
      r[i].open        = open[off + i];
      r[i].high        = high[off + i];
      r[i].low         = low[off + i];
      r[i].close       = close[off + i];
      r[i].tick_volume = tick_volume[off + i];
      r[i].real_volume = volume[off + i];
      r[i].spread      = spread[off + i];
     }
   TwkSeries s;
   TwkComputeSeries(r, n, g_p, s);

   const int chartSec = PeriodSeconds(_Period);
   if(full)
     {
      ArrayInitialize(BufTrail, EMPTY_VALUE); ArrayInitialize(BufLong, EMPTY_VALUE);  ArrayInitialize(BufShort, EMPTY_VALUE);
      ArrayInitialize(BufSL, EMPTY_VALUE);    ArrayInitialize(BufTP, EMPTY_VALUE);    ArrayInitialize(BufBv1, EMPTY_VALUE);
      ArrayInitialize(BufSv1, EMPTY_VALUE);   ArrayInitialize(BufBv3, EMPTY_VALUE);   ArrayInitialize(BufSv3, EMPTY_VALUE);
      ArrayInitialize(BufAdx, EMPTY_VALUE);   ArrayInitialize(BufDir, EMPTY_VALUE);   ArrayInitialize(BufRisk, EMPTY_VALUE);
      g_prevNewestSig = 0;                         // re-check every box after a (re)load
     }
   for(int i = last + 1; i < rates_total; i++)      // the forming bar stays empty: nothing repaints
     {
      BufTrail[i] = BufLong[i] = BufShort[i] = BufSL[i] = BufTP[i] = EMPTY_VALUE;
      BufBv1[i] = BufSv1[i] = BufBv3[i] = BufSv3[i] = BufAdx[i] = BufDir[i] = BufRisk[i] = EMPTY_VALUE;
     }
   for(int j = from; j < n; j++)
     {
      const int i = off + j;
      BufTrail[i] = s.st[j];
      BufDir[i]   = s.dir[j];
      BufAdx[i]   = s.adx[j];
      BufLong[i]  = s.longSig[j]  ? low[i]  : EMPTY_VALUE;
      BufShort[i] = s.shortSig[j] ? high[i] : EMPTY_VALUE;
      double dsl, dtp;
      string src;
      bool   skipped;
      const bool placed = SignalStops(s, j, DecisionSpread(s, j), dsl, dtp, src, skipped); // the stops the EA would place
      BufSL[i]   = skipped ? EMPTY_VALUE : placed ? dsl : s.sl[j];
      BufTP[i]   = skipped ? EMPTY_VALUE : placed ? dtp : s.tp[j];
      BufRisk[i] = skipped ? EMPTY_VALUE : placed ? MathAbs(s.rates[j].close - dsl) : s.risk[j];
      if(_Period == PERIOD_M1)
        {
         BufBv1[i] = s.bv[j];
         BufSv1[i] = s.sv[j];
        }
     }
   bool rowsOk = true;
   if(_Period != PERIOD_M1)
      rowsOk &= AlignRow(PERIOD_M1, time, off + from, last, chartSec, BufBv1, BufSv1);
   rowsOk &= AlignRow(PERIOD_M3, time, off + from, last, chartSec, BufBv3, BufSv3);
   if(!rowsOk)
      return 0;                                    // HTF history still loading, retry

   DrawPositions(s, n, off, full ? MathMin(TWK_WARMUP, n - 1) : from);   // no boxes on warm-up bars

   if(InpExportCSV && g_lastBar == 0)
      ExportCsv(s, off, last, time, chartSec);
   g_lastBar = time[rates_total - 1];
   return rates_total;
  }


string Fmt(const double v, const int d) { return TwkIsNa(v) ? "" : DoubleToString(v, d); }

void ExportCsv(const TwkSeries &s, const int off, const int last, const datetime &time[], const int chartSec)
  {
   const string name = StringFormat("TWK_diag_%s_%s.csv", _Symbol, StringSubstr(EnumToString(_Period), 7));
   const int h = FileOpen(name, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
     {
      PrintFormat("[DIAG] cannot open %s (err %d)", name, GetLastError());
      return;
     }
   FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "purple", "dir", "long", "short",
             "lastPL", "lastPH", "sl", "tp", "risk", "bv1", "sv1", "bv3", "sv3", "adx", "plusDI", "minusDI");
   const int d = _Digits;
   const int start = MathMax(off, last - InpExportBars + 1);
   for(int i = start; i <= last; i++)
     {
      const int j = i - off;
      FileWrite(h, TimeToString(time[i], TIME_DATE | TIME_MINUTES),
                Fmt(s.rates[j].open, d), Fmt(s.rates[j].high, d), Fmt(s.rates[j].low, d), Fmt(s.rates[j].close, d),
                (string)s.rates[j].tick_volume, Fmt(s.st[j], d), (string)s.dir[j],
                (string)(int)s.longSig[j], (string)(int)s.shortSig[j],
                Fmt(s.lastPL[j], d), Fmt(s.lastPH[j], d), Fmt(s.sl[j], d), Fmt(s.tp[j], d), Fmt(s.risk[j], d),
                Fmt(BufBv1[i], 0), Fmt(BufSv1[i], 0), Fmt(BufBv3[i], 0), Fmt(BufSv3[i], 0),
                Fmt(s.adx[j], 4), Fmt(s.plusDI[j], 4), Fmt(s.minusDI[j], 4));
     }
   FileClose(h);
   PrintFormat("[DIAG] exported %d closed bars to Common\\Files\\%s", last - start + 1, name);
  }
