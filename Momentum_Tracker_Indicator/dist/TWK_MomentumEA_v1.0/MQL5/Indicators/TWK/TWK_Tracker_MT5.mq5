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
//+------------------------------------------------------------------+
#property copyright "trade_with_kareena"
#property version   "1.00"
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

input group "Smart Trail / Signals (TWK_Tracker.pine)"
input double             InpStMult    = 1.5;   // Smart Trail multiplier
input int                InpStATR     = 10;    // Smart Trail ATR length
input int                InpPivLen    = 5;     // Pivot strength (bars each side)
input double             InpRR        = 2.0;   // Reward : Risk
input int                InpVolLen    = 20;    // Volume sum length (bars)
input ENUM_TWK_PIVOT_TIE InpPivotTie  = TWK_TIE_LEFT_EQUAL_OK; // Pivot tie rule
input group "ADX (TWK_Flow.pine)"
input int                InpDiLen     = 14;    // ADX DI length
input int                InpAdxSmooth = 14;    // ADX smoothing
input group "Diagnostics"
input int                InpCalcBars  = 5000;  // Bars to calculate
input bool               InpExportCSV = true;  // Export closed bars to CSV (Common\Files)
input int                InpExportBars = 3000; // Bars to export

double BufTrail[], BufLong[], BufShort[], BufSL[], BufTP[];
double BufBv1[], BufSv1[], BufBv3[], BufSv3[], BufAdx[], BufDir[], BufRisk[];

TwkParams g_p;
datetime  g_lastBar = 0;

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
   IndicatorSetString(INDICATOR_SHORTNAME, "TWK Tracker MT5");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   return INIT_SUCCEEDED;
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
   if(rates_total < 300)
      return 0;
   if(prev_calculated > 0 && time[rates_total - 1] == g_lastBar)
      return rates_total;                          // recalc once per new bar only

   const int last = rates_total - 2;               // last CLOSED bar
   const int n    = MathMin(InpCalcBars, last + 1);
   const int off  = last - n + 1;

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
   for(int i = 0; i < rates_total; i++)
     {
      BufTrail[i] = BufLong[i] = BufShort[i] = BufSL[i] = BufTP[i] = EMPTY_VALUE;
      BufBv1[i] = BufSv1[i] = BufBv3[i] = BufSv3[i] = BufAdx[i] = BufDir[i] = BufRisk[i] = EMPTY_VALUE;
     }
   for(int j = 0; j < n; j++)
     {
      const int i = off + j;
      BufTrail[i] = s.st[j];
      BufDir[i]   = s.dir[j];
      BufAdx[i]   = s.adx[j];
      if(s.longSig[j])  BufLong[i]  = low[i];
      if(s.shortSig[j]) BufShort[i] = high[i];
      BufSL[i]   = s.sl[j];
      BufTP[i]   = s.tp[j];
      BufRisk[i] = s.risk[j];
      if(_Period == PERIOD_M1)
        {
         BufBv1[i] = s.bv[j];
         BufSv1[i] = s.sv[j];
        }
     }
   bool rowsOk = true;
   if(_Period != PERIOD_M1)
      rowsOk &= AlignRow(PERIOD_M1, time, off, last, chartSec, BufBv1, BufSv1);
   rowsOk &= AlignRow(PERIOD_M3, time, off, last, chartSec, BufBv3, BufSv3);
   if(!rowsOk)
      return 0;                                    // HTF history still loading, retry

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
