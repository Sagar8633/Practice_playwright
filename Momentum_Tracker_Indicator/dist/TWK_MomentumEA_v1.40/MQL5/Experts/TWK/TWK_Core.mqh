//+------------------------------------------------------------------+
//| TWK_Core.mqh                                                     |
//| Exact MQL5 port of the calculations in TWK_Tracker.pine that the |
//| Momentum Tracker EA depends on. Shared by the EA and by the      |
//| diagnostic indicator, so both always compute identical values.   |
//|                                                                  |
//| Pine source of truth:                                            |
//|   TWK_Tracker.pine  - supertrend, flip signals, pivots, SL/TP,   |
//|                       up/down-bar volume sums (1m, 3m rows)      |
//|   TWK_Flow.pine     - ta.dmi(14,14) ADX                          |
//|                                                                  |
//| Conventions                                                      |
//|   * All arrays are CHRONOLOGICAL: index 0 = oldest bar.          |
//|   * Pine `na` is represented by TWK_NA (EMPTY_VALUE).            |
//|   * `volume` = MT5 tick_volume (OANDA/TV volume is tick volume). |
//+------------------------------------------------------------------+
#property strict

#ifndef TWK_CORE_MQH
#define TWK_CORE_MQH

#define TWK_NA EMPTY_VALUE

bool TwkIsNa(const double v) { return (v == EMPTY_VALUE || !MathIsValidNumber(v)); }

//--- Pine ta.pivotlow/high tie handling is undocumented; verified in Phase 2
enum ENUM_TWK_PIVOT_TIE
  {
   TWK_TIE_LEFT_EQUAL_OK  = 0, // left bars may equal the pivot, right bars must be strictly beyond
   TWK_TIE_STRICT         = 1, // every other bar strictly beyond the pivot
   TWK_TIE_RIGHT_EQUAL_OK = 2  // right bars may equal the pivot, left bars strictly beyond
  };

//--- Pine inputs used by the EA (defaults = TWK_Tracker.pine defaults)
struct TwkParams
  {
   double            stMult;     // Smart Trail multiplier (1.5)
   int               stATR;      // Smart Trail ATR length (10)
   int               pivLen;     // pivot strength each side (5)
   double            rr;         // reward:risk (2.0)
   int               volLen;     // up/down volume sum length (20)
   int               diLen;      // ADX DI length (14)  - TWK_Flow
   int               adxSmooth;  // ADX smoothing (14)  - TWK_Flow
   ENUM_TWK_PIVOT_TIE pivotTie;
   int               reflipBars; // quick re-flip window in bars (0 = off; not a Pine input)
  };

//--- What the EA does with a quick re-flip (see TwkComputeSeries). Shared by the EA and the Tracker.
enum ENUM_TWK_REFLIP
  {
   TWK_REFLIP_HARD_SL    = 0, // Hard SL (never the old pivot)
   TWK_REFLIP_SKIP       = 1, // Skip the trade
   TWK_REFLIP_KEEP_PIVOT = 2, // Keep the old pivot (v1.30 behaviour)
   TWK_REFLIP_PURPLE     = 3  // Purple line (never the old pivot)
  };

void TwkDefaultParams(TwkParams &p)
  {
   p.stMult    = 1.5;
   p.stATR     = 10;
   p.pivLen    = 5;
   p.rr        = 2.0;
   p.volLen    = 20;
   p.diLen     = 14;
   p.adxSmooth = 14;
   p.pivotTie  = TWK_TIE_LEFT_EQUAL_OK;
   p.reflipBars = 0;
  }

//+------------------------------------------------------------------+
//| Pine primitives                                                  |
//+------------------------------------------------------------------+
// ta.sma: na unless the last `len` values are all valid
void TwkSma(const double &src[], const int n, const int len, double &out[])
  {
   ArrayResize(out, n);
   for(int i = 0; i < n; i++)
     {
      out[i] = TWK_NA;
      if(i < len - 1)
         continue;
      double s = 0.0;
      bool ok = true;
      for(int k = i - len + 1; k <= i; k++)
        {
         if(TwkIsNa(src[k])) { ok = false; break; }
         s += src[k];
        }
      if(ok)
         out[i] = s / len;
     }
  }

// ta.rma: sum := na(sum[1]) ? ta.sma(src,len) : alpha*src + (1-alpha)*nz(sum[1])
void TwkRma(const double &src[], const int n, const int len, double &out[])
  {
   double sma[];
   TwkSma(src, n, len, sma);
   ArrayResize(out, n);
   const double alpha = 1.0 / len;
   for(int i = 0; i < n; i++)
     {
      const double prev = (i > 0) ? out[i - 1] : TWK_NA;
      if(TwkIsNa(prev))
         out[i] = sma[i];
      else
         out[i] = TwkIsNa(src[i]) ? TWK_NA : alpha * src[i] + (1.0 - alpha) * prev;
     }
  }

// ta.tr(handle_na): with handle_na=true the first bar is high-low, else na
void TwkTrueRange(const MqlRates &r[], const int n, const bool handleNa, double &out[])
  {
   ArrayResize(out, n);
   for(int i = 0; i < n; i++)
     {
      if(i == 0)
        {
         out[i] = handleNa ? r[i].high - r[i].low : TWK_NA;
         continue;
        }
      const double pc = r[i - 1].close;
      out[i] = MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - pc), MathAbs(r[i].low - pc)));
     }
  }

//+------------------------------------------------------------------+
//| ta.supertrend(factor, atrPeriod) - TradingView reference impl.   |
//| dir: -1 = uptrend (line below price), +1 = downtrend.            |
//| st  = the purple "Smart Trail" line.                             |
//+------------------------------------------------------------------+
void TwkSupertrend(const MqlRates &r[], const int n, const double factor, const int atrLen,
                   double &st[], int &dir[])
  {
   double tr[], atr[];
   TwkTrueRange(r, n, true, tr);          // ta.atr uses ta.tr(true)
   TwkRma(tr, n, atrLen, atr);

   ArrayResize(st, n);
   ArrayResize(dir, n);
   double lowerPrevFinal = TWK_NA, upperPrevFinal = TWK_NA;

   for(int i = 0; i < n; i++)
     {
      const double src = (r[i].high + r[i].low) / 2.0;   // hl2
      double upper = TWK_NA, lower = TWK_NA;
      if(!TwkIsNa(atr[i]))
        {
         upper = src + factor * atr[i];
         lower = src - factor * atr[i];
         const double prevLower = TwkIsNa(lowerPrevFinal) ? 0.0 : lowerPrevFinal;   // nz()
         const double prevUpper = TwkIsNa(upperPrevFinal) ? 0.0 : upperPrevFinal;
         const double close1    = (i > 0) ? r[i - 1].close : TWK_NA;
         const bool   c1Valid   = !TwkIsNa(close1);
         lower = (lower > prevLower || (c1Valid && close1 < prevLower)) ? lower : prevLower;
         upper = (upper < prevUpper || (c1Valid && close1 > prevUpper)) ? upper : prevUpper;
        }

      const bool   atrPrevNa = (i == 0) || TwkIsNa(atr[i - 1]);
      const double prevST    = (i > 0) ? st[i - 1] : TWK_NA;
      int d;
      if(atrPrevNa)
         d = 1;
      else if(!TwkIsNa(prevST) && prevST == upperPrevFinal)
         d = (r[i].close > upper) ? -1 : 1;
      else
         d = (r[i].close < lower) ? 1 : -1;

      dir[i] = d;
      st[i]  = TwkIsNa(atr[i]) ? TWK_NA : (d == -1 ? lower : upper);
      lowerPrevFinal = lower;
      upperPrevFinal = upper;
     }
  }

//+------------------------------------------------------------------+
//| ta.pivotlow / ta.pivothigh evaluated on bar i (confirmation bar). |
//| The candidate is bar i-R. Returns TWK_NA if not a pivot.          |
//+------------------------------------------------------------------+
double TwkPivotAt(const MqlRates &r[], const int i, const int L, const int R,
                  const bool isHigh, const ENUM_TWK_PIVOT_TIE tie)
  {
   const int c = i - R;
   if(c - L < 0)
      return TWK_NA;
   const double pv = isHigh ? r[c].high : r[c].low;
   for(int k = 1; k <= L; k++)
     {
      const double v = isHigh ? r[c - k].high : r[c - k].low;
      const bool equalOk = (tie == TWK_TIE_LEFT_EQUAL_OK);
      if(isHigh ? (equalOk ? v > pv : v >= pv) : (equalOk ? v < pv : v <= pv))
         return TWK_NA;
     }
   for(int k = 1; k <= R; k++)
     {
      const double v = isHigh ? r[c + k].high : r[c + k].low;
      const bool equalOk = (tie == TWK_TIE_RIGHT_EQUAL_OK);
      if(isHigh ? (equalOk ? v > pv : v >= pv) : (equalOk ? v < pv : v <= pv))
         return TWK_NA;
     }
   return pv;
  }

//+------------------------------------------------------------------+
//| math.sum(close > open ? volume : 0, len) and the < counterpart    |
//+------------------------------------------------------------------+
void TwkUpDownVolume(const MqlRates &r[], const int n, const int len, double &bv[], double &sv[])
  {
   ArrayResize(bv, n);
   ArrayResize(sv, n);
   double b = 0.0, s = 0.0;
   for(int i = 0; i < n; i++)
     {
      const double v = (double)r[i].tick_volume;
      b += (r[i].close > r[i].open) ? v : 0.0;
      s += (r[i].close < r[i].open) ? v : 0.0;
      if(i >= len)
        {
         const double vo = (double)r[i - len].tick_volume;
         b -= (r[i - len].close > r[i - len].open) ? vo : 0.0;
         s -= (r[i - len].close < r[i - len].open) ? vo : 0.0;
        }
      bv[i] = (i >= len - 1) ? b : TWK_NA;
      sv[i] = (i >= len - 1) ? s : TWK_NA;
     }
  }

//+------------------------------------------------------------------+
//| ta.dmi(diLen, adxSmoothing) - TradingView reference impl.         |
//+------------------------------------------------------------------+
void TwkDmi(const MqlRates &r[], const int n, const int diLen, const int adxLen,
            double &plusDI[], double &minusDI[], double &adx[])
  {
   double pdm[], mdm[], tr[];
   ArrayResize(pdm, n);
   ArrayResize(mdm, n);
   for(int i = 0; i < n; i++)
     {
      if(i == 0) { pdm[i] = TWK_NA; mdm[i] = TWK_NA; continue; }
      const double up   = r[i].high - r[i - 1].high;
      const double down = r[i - 1].low - r[i].low;
      pdm[i] = (up > down && up > 0) ? up : 0.0;
      mdm[i] = (down > up && down > 0) ? down : 0.0;
     }
   TwkTrueRange(r, n, false, tr);          // ta.dmi uses ta.tr (na on first bar)

   double trur[], rp[], rm[];
   TwkRma(tr, n, diLen, trur);
   TwkRma(pdm, n, diLen, rp);
   TwkRma(mdm, n, diLen, rm);

   ArrayResize(plusDI, n);
   ArrayResize(minusDI, n);
   double dx[];
   ArrayResize(dx, n);
   double lastP = TWK_NA, lastM = TWK_NA;   // fixnan()
   for(int i = 0; i < n; i++)
     {
      double p = TWK_NA, m = TWK_NA;
      if(!TwkIsNa(trur[i]) && trur[i] != 0.0)
        {
         if(!TwkIsNa(rp[i])) p = 100.0 * rp[i] / trur[i];
         if(!TwkIsNa(rm[i])) m = 100.0 * rm[i] / trur[i];
        }
      if(TwkIsNa(p)) p = lastP; else lastP = p;
      if(TwkIsNa(m)) m = lastM; else lastM = m;
      plusDI[i]  = p;
      minusDI[i] = m;
      if(TwkIsNa(p) || TwkIsNa(m))
         dx[i] = TWK_NA;
      else
        {
         const double sum = p + m;
         dx[i] = MathAbs(p - m) / (sum == 0.0 ? 1.0 : sum);
        }
     }
   double sm[];
   TwkRma(dx, n, adxLen, sm);
   ArrayResize(adx, n);
   for(int i = 0; i < n; i++)
      adx[i] = TwkIsNa(sm[i]) ? TWK_NA : 100.0 * sm[i];
  }

//+------------------------------------------------------------------+
//| Full per-bar Tracker series on the signal timeframe.              |
//+------------------------------------------------------------------+
struct TwkSeries
  {
   int               n;
   MqlRates          rates[];
   double            st[];       // purple line
   int               dir[];
   bool              longSig[];
   bool              shortSig[];
   double            lastPL[];   // as updated on that bar
   double            lastPH[];
   double            sl[];       // Pine position SL on signal bars, else TWK_NA
   double            tp[];
   double            risk[];     // Pine risk (may be <= 0 -> Pine draws no box)
   bool              slPivot[];  // SL came from a confirmed pivot (false = purple-line fallback)
   bool              reFlip[];   // quick re-flip: the SL pivot is older than a recent opposite signal
   int               oppAgo[];   // bars since the previous opposite signal (-1 = none in the window)
   int               pivBar[];   // bar index of the pivot the SL would use (-1 = none)
   double            bv[];       // Buying volume of this TF (up-bar sum)
   double            sv[];       // Selling volume
   double            adx[];
   double            plusDI[];
   double            minusDI[];
  };

void TwkComputeSeries(const MqlRates &src[], const int n, const TwkParams &p, TwkSeries &s)
  {
   s.n = n;
   ArrayResize(s.rates, n);
   for(int i = 0; i < n; i++)
      s.rates[i] = src[i];

   TwkSupertrend(s.rates, n, p.stMult, p.stATR, s.st, s.dir);
   TwkUpDownVolume(s.rates, n, p.volLen, s.bv, s.sv);
   TwkDmi(s.rates, n, p.diLen, p.adxSmooth, s.plusDI, s.minusDI, s.adx);

   ArrayResize(s.longSig, n);
   ArrayResize(s.shortSig, n);
   ArrayResize(s.lastPL, n);
   ArrayResize(s.lastPH, n);
   ArrayResize(s.sl, n);
   ArrayResize(s.tp, n);
   ArrayResize(s.risk, n);
   ArrayResize(s.slPivot, n);
   ArrayResize(s.reFlip, n);
   ArrayResize(s.oppAgo, n);
   ArrayResize(s.pivBar, n);

   double lpl = TWK_NA, lph = TWK_NA;
   int    lplBar = -1, lphBar = -1;              // the bar the last confirmed pivot low / high sits on
   int    lastLong = -1, lastShort = -1;         // bar of the latest LONG / SHORT signal
   for(int i = 0; i < n; i++)
     {
      // bullFlip = stDir < 0 and stDir[1] >= 0 ; bearFlip = stDir > 0 and stDir[1] <= 0
      s.longSig[i]  = (i > 0) && s.dir[i] < 0 && s.dir[i - 1] >= 0;
      s.shortSig[i] = (i > 0) && s.dir[i] > 0 && s.dir[i - 1] <= 0;

      const double pl = TwkPivotAt(s.rates, i, p.pivLen, p.pivLen, false, p.pivotTie);
      const double ph = TwkPivotAt(s.rates, i, p.pivLen, p.pivLen, true,  p.pivotTie);
      if(!TwkIsNa(pl)) { lpl = pl; lplBar = i - p.pivLen; }
      if(!TwkIsNa(ph)) { lph = ph; lphBar = i - p.pivLen; }
      s.lastPL[i] = lpl;
      s.lastPH[i] = lph;

      s.sl[i] = TWK_NA;
      s.tp[i] = TWK_NA;
      s.risk[i] = TWK_NA;
      s.slPivot[i] = false;
      s.reFlip[i]  = false;
      s.oppAgo[i]  = -1;
      s.pivBar[i]  = -1;
      if(s.longSig[i] || s.shortSig[i])
        {
         const bool   isL   = s.longSig[i];
         const double entry = s.rates[i].close;
         const bool   pivOk = isL ? (!TwkIsNa(lpl) && lpl < entry) : (!TwkIsNa(lph) && lph > entry);
         const double sl    = pivOk ? (isL ? lpl : lph) : s.st[i];
         s.slPivot[i] = pivOk;
         // Quick re-flip: the opposite signal came at most reflipBars bars ago and the SL pivot is
         // older than it. The swing between the two signals needs pivLen more bars to confirm, so the
         // stop reaches back behind the whole previous leg (e.g. a $40 stop). The SL value stays the
         // Pine one; the EA decides what to do with the flag.
         const int opp = isL ? lastShort : lastLong;
         s.pivBar[i] = pivOk ? (isL ? lplBar : lphBar) : -1;
         s.oppAgo[i] = (opp >= 0) ? i - opp : -1;
         s.reFlip[i] = pivOk && p.reflipBars > 0 && opp >= 0 && i - opp <= p.reflipBars
                       && (isL ? lplBar : lphBar) < opp;
         if(isL) lastLong = i; else lastShort = i;
         if(TwkIsNa(sl))
            continue;
         const double risk = isL ? entry - sl : sl - entry;
         s.sl[i]   = sl;
         s.risk[i] = risk;
         if(risk > 0)
            s.tp[i] = isL ? entry + p.rr * risk : entry - p.rr * risk;
        }
     }
  }

//+------------------------------------------------------------------+
//| Index of the last HTF bar that is COMPLETE at time `closeTime`.   |
//| Matches request.security(..., lookahead_off) on historical bars.  |
//| htf[] chronological. Returns -1 if none.                          |
//+------------------------------------------------------------------+
int TwkLastCompletedHtf(const MqlRates &htf[], const int n, const int htfSeconds, const datetime closeTime)
  {
   int lo = 0, hi = n - 1, ans = -1;
   while(lo <= hi)
     {
      const int mid = (lo + hi) / 2;
      if(htf[mid].time + htfSeconds <= closeTime) { ans = mid; lo = mid + 1; }
      else hi = mid - 1;
     }
   return ans;
  }

//+------------------------------------------------------------------+
//| Snapshot of everything the EA needs for ONE closed signal bar.    |
//+------------------------------------------------------------------+
enum ENUM_TWK_SIGNAL { TWK_SIG_NONE = 0, TWK_SIG_LONG = 1, TWK_SIG_SHORT = -1 };

struct TwkSnapshot
  {
   bool              ok;           // all data loaded
   string            error;        // why not ok
   datetime          barTime;      // signal-bar open time
   double            close;        // Pine entry
   ENUM_TWK_SIGNAL   signal;
   double            purple;       // stVal on the bar
   int               stDir;
   double            sl, tp, risk;
   bool              slFromPivot;  // false: no confirmed pivot on the protective side (sl = purple)
   bool              reFlip;       // quick re-flip (see TwkComputeSeries)
   int               oppAgo;       // bars since the previous opposite signal (-1 = none)
   double            bv1, sv1;     // 1m row
   double            bv3, sv3;     // 3m row (last completed M3 bar)
   datetime          m3BarTime;
   double            adx;
  };

//+------------------------------------------------------------------+
//| Loads data and evaluates bar `shift` (1 = last closed) of the     |
//| signal TF. Volume rows always come from M1 and M3, like Pine's   |
//| f_tf("1") / f_tf("3"), independent of the signal timeframe.       |
//+------------------------------------------------------------------+
class CTwkEngine
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_bars;
   TwkParams         m_p;

   bool              Load(const ENUM_TIMEFRAMES tf, const int count, MqlRates &out[], string &err)
     {
      ArraySetAsSeries(out, false);
      ResetLastError();
      const int got = CopyRates(m_symbol, tf, 0, count, out);
      if(got <= 0)
        {
         err = StringFormat("CopyRates %s %s failed (err %d)", m_symbol, EnumToString(tf), GetLastError());
         return false;
        }
      if(got < MathMin(count, 200))
        {
         err = StringFormat("History not ready: %s %d/%d bars", EnumToString(tf), got, count);
         return false;
        }
      return true;
     }

public:
                     CTwkEngine() : m_symbol(_Symbol), m_tf(PERIOD_M1), m_bars(2000) { TwkDefaultParams(m_p); }
   void              Init(const string symbol, const ENUM_TIMEFRAMES tf, const int bars, const TwkParams &p)
     {
      m_symbol = symbol;
      m_tf = tf;
      m_bars = MathMax(bars, 300);
      m_p = p;
     }

   bool              Evaluate(const int shift, TwkSnapshot &snap, TwkSeries &sig)
     {
      ZeroMemory(snap);
      snap.ok = false;
      snap.signal = TWK_SIG_NONE;

      MqlRates r[];
      if(!Load(m_tf, m_bars, r, snap.error))
         return false;
      const int n = ArraySize(r);
      const int i = n - 1 - shift;
      if(i < 1) { snap.error = "Not enough bars for shift"; return false; }

      TwkComputeSeries(r, n, m_p, sig);

      snap.barTime = r[i].time;
      snap.close   = r[i].close;
      snap.purple  = sig.st[i];
      snap.stDir   = sig.dir[i];
      snap.signal  = sig.longSig[i] ? TWK_SIG_LONG : (sig.shortSig[i] ? TWK_SIG_SHORT : TWK_SIG_NONE);
      snap.sl      = sig.sl[i];
      snap.tp      = sig.tp[i];
      snap.risk    = sig.risk[i];
      snap.slFromPivot = sig.slPivot[i];
      snap.reFlip      = sig.reFlip[i];
      snap.oppAgo      = sig.oppAgo[i];
      snap.adx     = sig.adx[i];

      const datetime barClose = r[i].time + PeriodSeconds(m_tf);

      //--- 1m row
      if(m_tf == PERIOD_M1)
        {
         snap.bv1 = sig.bv[i];
         snap.sv1 = sig.sv[i];
        }
      else if(!RowAt(PERIOD_M1, barClose, snap.bv1, snap.sv1, snap.m3BarTime, snap.error))
         return false;

      //--- 3m row (completed M3 bars only)
      if(!RowAt(PERIOD_M3, barClose, snap.bv3, snap.sv3, snap.m3BarTime, snap.error))
         return false;

      if(TwkIsNa(snap.purple) || TwkIsNa(snap.adx) || TwkIsNa(snap.bv1) || TwkIsNa(snap.sv1)
         || TwkIsNa(snap.bv3) || TwkIsNa(snap.sv3))
        {
         snap.error = "Indicator warm-up incomplete (NA values)";
         return false;
        }
      snap.ok = true;
      return true;
     }

   // Buying/selling volume row of `tf` as of `closeTime` (last completed bar of tf)
   bool              RowAt(const ENUM_TIMEFRAMES tf, const datetime closeTime,
                           double &bv, double &sv, datetime &barTime, string &err)
     {
      bv = TWK_NA;
      sv = TWK_NA;
      MqlRates h[];
      const int need = m_p.volLen + 50;
      if(!Load(tf, need, h, err))
         return false;
      const int n = ArraySize(h);
      double b[], s[];
      TwkUpDownVolume(h, n, m_p.volLen, b, s);
      const int k = TwkLastCompletedHtf(h, n, PeriodSeconds(tf), closeTime);
      if(k < 0) { err = StringFormat("No completed %s bar at %s", EnumToString(tf), TimeToString(closeTime)); return false; }
      bv = b[k];
      sv = s[k];
      barTime = h[k].time;
      return true;
     }
  };

//+------------------------------------------------------------------+
//| Writes the per-bar diagnostics CSV (closed bars only) used by     |
//| tools/compare_mt5.py. Same columns as TWK_Tracker_MT5.            |
//+------------------------------------------------------------------+
string TwkFmt(const double v, const int d) { return TwkIsNa(v) ? "" : DoubleToString(v, d); }

bool TwkExportDiagnostics(const string symbol, const ENUM_TIMEFRAMES tf, const int calcBars,
                          const int exportBars, const TwkParams &p, const string fileName, string &err)
  {
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int n = CopyRates(symbol, tf, 1, calcBars, r);      // start at 1 = closed bars only
   if(n < 300) { err = StringFormat("only %d closed bars available", n); return false; }
   TwkSeries s;
   TwkComputeSeries(r, n, p, s);

   const int tfSec = PeriodSeconds(tf);
   MqlRates m1[], m3[];
   ArraySetAsSeries(m1, false);
   ArraySetAsSeries(m3, false);
   const int n1 = (tf == PERIOD_M1) ? 0 : CopyRates(symbol, PERIOD_M1, 0, (int)MathMin(100000, (double)n * tfSec / 60 + p.volLen + 50), m1);
   const int n3 = CopyRates(symbol, PERIOD_M3, 0, (int)MathMin(100000, (double)n * tfSec / 180 + p.volLen + 50), m3);
   if(n3 <= p.volLen || (tf != PERIOD_M1 && n1 <= p.volLen)) { err = "M1/M3 history not ready"; return false; }
   double b1[], s1[], b3[], s3[];
   if(tf != PERIOD_M1)
      TwkUpDownVolume(m1, n1, p.volLen, b1, s1);
   TwkUpDownVolume(m3, n3, p.volLen, b3, s3);

   const int h = FileOpen(fileName, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) { err = StringFormat("cannot open %s (err %d)", fileName, GetLastError()); return false; }
   FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "purple", "dir", "long", "short",
             "lastPL", "lastPH", "sl", "tp", "risk", "bv1", "sv1", "bv3", "sv3", "adx", "plusDI", "minusDI");
   const int d = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   for(int i = MathMax(0, n - exportBars); i < n; i++)
     {
      const datetime closeT = r[i].time + tfSec;
      double bv1 = s.bv[i], sv1 = s.sv[i];
      if(tf != PERIOD_M1)
        {
         const int k1 = TwkLastCompletedHtf(m1, n1, 60, closeT);
         bv1 = (k1 < 0) ? TWK_NA : b1[k1];
         sv1 = (k1 < 0) ? TWK_NA : s1[k1];
        }
      const int k3 = TwkLastCompletedHtf(m3, n3, 180, closeT);
      FileWrite(h, TimeToString(r[i].time, TIME_DATE | TIME_MINUTES),
                TwkFmt(r[i].open, d), TwkFmt(r[i].high, d), TwkFmt(r[i].low, d), TwkFmt(r[i].close, d),
                (string)r[i].tick_volume, TwkFmt(s.st[i], d), (string)s.dir[i],
                (string)(int)s.longSig[i], (string)(int)s.shortSig[i],
                TwkFmt(s.lastPL[i], d), TwkFmt(s.lastPH[i], d), TwkFmt(s.sl[i], d), TwkFmt(s.tp[i], d), TwkFmt(s.risk[i], d),
                TwkFmt(bv1, 0), TwkFmt(sv1, 0),
                k3 < 0 ? "" : TwkFmt(b3[k3], 0), k3 < 0 ? "" : TwkFmt(s3[k3], 0),
                TwkFmt(s.adx[i], 4), TwkFmt(s.plusDI[i], 4), TwkFmt(s.minusDI[i], 4));
     }
   FileClose(h);
   return true;
  }

string TwkSignalText(const ENUM_TWK_SIGNAL s)
  {
   return s == TWK_SIG_LONG ? "LONG" : (s == TWK_SIG_SHORT ? "SHORT" : "NONE");
  }

#endif // TWK_CORE_MQH
