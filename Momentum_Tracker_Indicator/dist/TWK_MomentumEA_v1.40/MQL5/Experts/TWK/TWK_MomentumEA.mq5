//+------------------------------------------------------------------+
//| TWK_MomentumEA.mq5                                               |
//| Momentum Tracker EA - execution + risk layer for TWK Tracker.    |
//|                                                                  |
//| ============================================================     |
//| MOMENTUM TRACKER EA - CORE RULES                                 |
//|                                                                  |
//| 1. Momentum Tracker determines trade direction.                  |
//| 2. LONG = BUY candidate.                                         |
//| 3. SHORT = SELL candidate.                                       |
//| 4. Never independently generate BUY/SELL.                        |
//| 5. BUY requires LONG + volume + M1 + M3 + ADX + valid SL.        |
//| 6. SELL requires SHORT + volume + M1 + M3 + ADX + valid SL.      |
//| 7. Initial SL comes from Momentum Tracker (pivot). With no       |
//|    pivot, or on a quick re-flip (pivot older than the opposite   |
//|    signal a few bars back): HardSL_<TF> points (0 = purple line) |
//|    or skip, per ReFlipAction. The old pivot is never used there. |
//| 8. Do NOT hardcode 5-point initial SL.                           |
//| 9. Profit >= 2 -> Purple-line trailing.                          |
//| 10. Profit >= 5 -> Lock profit.                                  |
//| 11. After +5 -> 1:1 trailing.                                    |
//| 12. SL can NEVER become less protective.                         |
//| 13. Purple line is management only, not an entry signal.         |
//| 14. Do not guess Pine/indicator values.                          |
//| 15. Missing required data means NO TRADE.                        |
//| 16. Prevent duplicate entries.                                   |
//| 17. Recover existing positions after restart.                    |
//| 18. Respect broker execution constraints.                        |
//| ============================================================     |
//|                                                                  |
//| Indicator values come from TWK_Core.mqh, an exact port of        |
//| TWK_Tracker.pine / TWK_Flow.pine validated bar-for-bar against   |
//| TradingView (see PHASE2_VALIDATION.md). No iCustom buffers.      |
//|                                                                  |
//| ALL DISTANCES ARE BROKER POINTS (_Point). No currency amounts:   |
//| on XAUUSD with 2 digits, 200 points = 2.00 price move.           |
//|                                                                  |
//| DEMO FIRST: by default the EA refuses to open trades on a REAL   |
//| account. To go live, set AccountGuard = Demo and Real AND type   |
//| I ACCEPT REAL RISK into RealTradingConfirmation.                 |
//+------------------------------------------------------------------+
#property copyright "trade_with_kareena"
#property version   "1.40"
#property description "Executes TWK Tracker LONG/SHORT signals with volume, M1/M3 box and ADX filters,"
#property description "indicator SL/TP, +2 purple trailing, +5 profit lock and 1:1 trailing. Demo-only by default."

#include <Trade\Trade.mqh>
#include "TWK_Core.mqh"

// The chart Tracker (purple line, LONG/SHORT arrows, SL/TP boxes) is compiled INTO this .ex5, so the
// EA alone is the whole package: the Strategy Tester shows it on the test chart like any indicator
// the EA creates. Compile Indicators\TWK\TWK_Tracker_MT5.mq5 before this file.
#resource "\\Indicators\\TWK\\TWK_Tracker_MT5.ex5"
#define TWK_TRACKER_RES  "::Indicators\\TWK\\TWK_Tracker_MT5.ex5"
#define TWK_TRACKER_NAME "TWK Tracker (EA)"          // INDICATOR_SHORTNAME of the EA's own copy
#define TWK_TRADE_PREFIX "TWKTRD_"                  // trade boxes drawn by the EA itself

//--- enums -----------------------------------------------------------
enum ENUM_ACCOUNT_GUARD
  {
   GUARD_DEMO_ONLY     = 0, // Demo only (real account = signals only, no orders)
   GUARD_DEMO_AND_REAL = 1  // Demo and Real (also needs the confirmation text)
  };
enum ENUM_LOT_MODE      { FIXED = 0, RISK_PERCENT = 1 };
enum ENUM_EMERGENCY     { RETRY_SL = 0, CLOSE_POSITION = 1, DISABLE_NEW_ENTRIES = 2 };
enum ENUM_EA_STATE
  {
   WAITING_FOR_SIGNAL, SIGNAL_DETECTED, VALIDATING_FILTERS, READY_TO_EXECUTE,
   POSITION_OPEN_INITIAL_SL, PURPLE_TRAILING, PROFIT_LOCKED, ONE_TO_ONE_TRAILING, EXITED
  };
enum ENUM_SL_SOURCE { SRC_INITIAL = 0, SRC_PURPLE = 1, SRC_LOCK = 2, SRC_ONE_TO_ONE = 3, SRC_MANUAL = 4 };

#define REAL_CONFIRM_TEXT "I ACCEPT REAL RISK"

//--- inputs ----------------------------------------------------------
input group "=== ACCOUNT SAFETY (demo first) ==="
input ENUM_ACCOUNT_GUARD AccountGuard           = GUARD_DEMO_ONLY; // Where new trades are allowed
input string             RealTradingConfirmation = "";             // Type: I ACCEPT REAL RISK (real only)
input double             RealAccountMaxLot       = 0.01;           // Hard lot cap on a REAL account

input group "=== SIGNAL ==="
input ENUM_TIMEFRAMES    SignalTimeframe     = PERIOD_M1; // Signal timeframe (independent of chart)
input bool               TradeOnClosedCandle = true;      // Evaluate confirmed candles only
input bool               OneTradePerSignal   = true;      // One entry per signal bar
input int                CalcBars            = 2000;      // Bars used for indicator calculation

input group "=== TRACKER (must match the TradingView inputs) ==="
input double             TrailMultiplier = 1.5;  // Smart Trail multiplier
input int                TrailATRLength  = 10;   // Smart Trail ATR length
input int                PivotStrength   = 5;    // Pivot strength (bars each side)
input double             RewardRisk      = 2.0;  // Reward : Risk (indicator TP)
input int                VolumeLength    = 20;   // Buying/Selling volume length (bars)
input ENUM_TWK_PIVOT_TIE PivotTieRule    = TWK_TIE_LEFT_EQUAL_OK; // Pivot tie rule

input group "=== VOLUME ==="
input double             MinimumVolumeRatio = 1.50; // 1m: own side >= opposite x ratio

input group "=== BOX ==="
input bool               RequireM1Box = true; // 1m row must agree (Positive BUY / Negative SELL)
input bool               RequireM3Box = true; // 3m row must agree (completed 3m bars)

input group "=== ADX ==="
input int                ADXPeriod    = 14;   // ADX DI length
input int                ADXSmoothing = 14;   // ADX smoothing
input double             ADXMinimum   = 20.0; // ADX must be strictly greater

input group "=== STOP LOSS ==="
input bool               UseIndicatorSL     = true;  // Initial SL = Tracker SL
input bool               EnableFallbackSL   = false; // Fallback SL if Tracker SL invalid
input int                FallbackSLPoints   = 500;   // Fallback SL distance (points)

input group "=== HARD SL (no pivot, or quick re-flip) - by signal timeframe ==="
input int                HardSL_M1    = 500; // M1 signals: hard SL points (0 = purple line)
input int                HardSL_M3    = 0;   // M3 signals: hard SL points (0 = purple line)
input int                HardSL_M5    = 0;   // M5 signals: hard SL points (0 = purple line)
input int                HardSL_M15   = 0;   // M15 signals: hard SL points (0 = purple line)
input int                HardSL_M30   = 0;   // M30 signals: hard SL points (0 = purple line)
input int                HardSL_H1    = 0;   // H1 signals: hard SL points (0 = purple line)
input int                HardSL_H4    = 0;   // H4 signals: hard SL points (0 = purple line)
input int                HardSL_Other = 0;   // Other signal TFs: hard SL points (0 = purple line)

input group "=== QUICK RE-FLIP (signal soon after an opposite signal) ==="
input ENUM_TWK_REFLIP    ReFlipAction  = TWK_REFLIP_HARD_SL; // Pivot older than the opposite signal: hard SL / skip / keep / purple
input int                ReFlipMinutes = 15;                 // Opposite signal at most this many minutes back (0 = off)

input group "=== TAKE PROFIT ==="
input bool               UseIndicatorTP     = true;  // TP = Tracker TP (captured at entry)
input bool               EnableFallbackTP   = false; // Fallback TP if Tracker TP invalid
input int                FallbackTPPoints   = 1000;  // Fallback TP distance (points)
input bool               RejectIfTPInvalid  = true;  // No trade if TP invalid and no fallback

input group "=== TRAILING ==="
input bool               EnablePurpleLineTrailing   = true; // Stage 1: trail on purple line
input int                PurpleTrailActivationPoints      = 200; // Stage 1 activation (profit, points)
input int                ProfitProtectionActivationPoints = 500; // Stage 2 activation (profit, points)
input int                ProfitLockPoints                 = 100; // Stage 2 locked profit (points)
input bool               EnableOneToOneTrailing     = true; // After Stage 2: 1:1 trailing
input int                MinSLImprovementPoints     = 5;    // Min SL move per modification (points)

input group "=== POSITION SIZE ==="
input ENUM_LOT_MODE      LotSizingMode        = FIXED; // FIXED or RISK_PERCENT
input double             LotSize              = 0.01;  // Fixed lot size
input double             RiskPercent          = 0.50;  // % of balance risked to initial SL
input double             MaxLotSize           = 0.10;  // Never trade more than this
input bool               OnePositionPerSymbol = true;  // No stacking

input group "=== EXECUTION ==="
input bool               EnableSpreadFilter = true;     // Reject entry on wide spread
input int                MaxSpreadPoints    = 0;        // Max spread (points). 0 = auto
input double             SpreadAutoMultiplier = 2.0;    // Auto: x median spread of last 1000 bars
input int                MaxDeviation       = 50;       // Max slippage (broker points)
input int                MaxRetries         = 3;        // Order/modify retries
input ulong              MagicNumber        = 26092401; // Magic number
input string             TradeComment       = "TWK";    // Order comment

input group "=== OPPOSITE SIGNAL ==="
input bool               CloseOnOppositeSignal   = false; // Close position on opposite signal
input bool               ReverseOnOppositeSignal = false; // Close and reverse

input group "=== PROTECTION ==="
input ENUM_EMERGENCY     EmergencyProtectionMode = CLOSE_POSITION; // If SL cannot be placed
input bool               RespectManualSL         = true;           // Keep manual SL changes

input group "=== CHART (drawn by the EA itself, live and in the Strategy Tester) ==="
input bool               ShowTrackerOnChart = true; // Purple line, LONG/SHORT arrows and SL/TP boxes on the chart
input int                ChartTrackerBars   = 50000; // History drawn when the chart opens (0 = all); new bars are added after
input int                ChartBoxHistory    = 300;   // Live: signals that keep their box (a test keeps every box)

input group "=== DIAGNOSTICS ==="
input bool               DebugIndicatorMode   = true; // Log indicator values every bar
input bool               ShowDebugPanel       = true; // Chart panel (display only)
input bool               ExportDiagnosticsCSV = true; // Export per-bar CSV on start (live only)
input int                ExportBars           = 3000; // Bars in diagnostics CSV
input bool               WriteTradeLog        = true; // Per-trade CSV in Common\Files

input group "=== STRATEGY TESTER (ignored in live trading) ==="
input int                TesterSliceDays  = 0;     // Tester: slice length in days (0 = off)
input int                TesterSliceIndex = 0;     // Tester: slice number (optimize 0..N-1 step 1)
input bool               TesterDebugLog   = false; // Tester: write the per-bar [BAR] lines (slow)

//--- globals ---------------------------------------------------------
CTrade        g_trade;
CTwkEngine    g_engine;
int           g_trackerHandle = INVALID_HANDLE;   // chart Tracker (display only, never read by the EA)
TwkParams     g_p;
TwkSnapshot   g_snap;            // last closed-bar snapshot
bool          g_snapValid = false;
datetime      g_lastBarTime = 0;
datetime      g_lastIntrabarEval = 0;
bool          g_entriesDisabled = false;
bool          g_realBlocked = false;
ENUM_EA_STATE g_state = WAITING_FOR_SIGNAL;
string        g_lastReject = "";
string        g_prefix;          // GlobalVariable prefix
datetime      g_lastModifyFail = 0;
bool          g_exportPending = false;
int           g_exportTries = 0;

// session statistics (exit breakdown)
int    g_exitCount[6];           // 0 initial,1 purple,2 lock,3 1:1,4 manual,5 TP
int    g_exitOther = 0;
string g_exitNames[7] = {"Initial SL", "Purple-line SL", "Profit-lock SL", "1:1 trailing SL", "Manual SL", "Indicator TP", "Other/Manual exit"};

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double Pts(const double points) { return points * _Point; }   // broker points -> price distance
int    ToPts(const double dist) { return (int)MathRound(dist / _Point); }

double g_maxSpreadPts = 0;       // active spread limit in points (fixed or auto)
datetime g_spreadCalcBar = 0;

// Auto spread limit: SpreadAutoMultiplier x median bar spread of the last 1000 closed bars.
// Same rule on every symbol, so one configuration fits any symbol.
void UpdateSpreadLimit()
  {
   if(MaxSpreadPoints > 0)
     {
      g_maxSpreadPts = MaxSpreadPoints;
      return;
     }
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int n = CopyRates(_Symbol, SignalTimeframe, 1, 1000, r);
   if(n < 50)
      return;                                    // keep previous value until history loads
   int sp[];
   ArrayResize(sp, n);
   int valid = 0;
   for(int i = 0; i < n; i++)
      if(r[i].spread > 0)
         sp[valid++] = r[i].spread;
   if(valid < 50)
      return;
   ArrayResize(sp, valid);
   ArraySort(sp);
   const double median = (valid % 2 == 1) ? sp[valid / 2] : (sp[valid / 2 - 1] + sp[valid / 2]) / 2.0;
   const double limit  = MathCeil(median * SpreadAutoMultiplier);
   if(MathAbs(limit - g_maxSpreadPts) >= 1)
      Log("SPREAD", StringFormat("auto limit %.0f pts (median %.1f pts x %.1f over %d bars)", limit, median, SpreadAutoMultiplier, valid));
   g_maxSpreadPts = limit;
  }

double TickSize()
  {
   const double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return ts > 0 ? ts : _Point;
  }

double NormPrice(const double p)
  {
   const double ts = TickSize();
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

string P(const double v) { return TwkIsNa(v) ? "n/a" : DoubleToString(v, _Digits); }

string StateText(const ENUM_EA_STATE s)
  {
   switch(s)
     {
      case WAITING_FOR_SIGNAL:       return "WAITING_FOR_SIGNAL";
      case SIGNAL_DETECTED:          return "SIGNAL_DETECTED";
      case VALIDATING_FILTERS:       return "VALIDATING_FILTERS";
      case READY_TO_EXECUTE:         return "READY_TO_EXECUTE";
      case POSITION_OPEN_INITIAL_SL: return "POSITION_OPEN_INITIAL_SL";
      case PURPLE_TRAILING:          return "PURPLE_TRAILING";
      case PROFIT_LOCKED:            return "PROFIT_LOCKED";
      case ONE_TO_ONE_TRAILING:      return "ONE_TO_ONE_TRAILING";
      default:                       return "EXITED";
     }
  }

string GvName(const ulong posId, const string key) { return StringFormat("%s.%I64u.%s", g_prefix, posId, key); }
double GvGet(const string name, const double def) { return GlobalVariableCheck(name) ? GlobalVariableGet(name) : def; }
// State changes are rare (entry, stage change, SL move), so flush each one to disk:
// a terminal crash must not lose the stage or the consumed-signal marker.
void   GvSet(const string name, const double v)
  {
   GlobalVariableSet(name, v);
   if(!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
      GlobalVariablesFlush();
  }
string SignalGv() { return StringFormat("%s.%s.lastsig", g_prefix, _Symbol); }

void Log(const string tag, const string msg) { PrintFormat("[%s] %s", tag, msg); }

//+------------------------------------------------------------------+
//| Account guard: demo first                                        |
//+------------------------------------------------------------------+
bool IsTester() { return (bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION); }

//+------------------------------------------------------------------+
//| Strategy Tester speed-ups (never active in live trading)         |
//| * Fast mode: in a non-visual test nobody sees the chart panel,   |
//|   so it is not rebuilt on every simulated tick/second.           |
//| * Slices: one backtest runs on ONE core by design. To use every  |
//|   core, run an optimization over TesterSliceIndex: each pass     |
//|   trades only its own TesterSliceDays window, lets its last      |
//|   trade finish, then stops. tools/merge_tester_slices.py joins   |
//|   the per-slice trade CSVs into one report.                      |
//+------------------------------------------------------------------+
bool     g_fastTester = false;
bool     g_sliceOn = false;
datetime g_sliceStart = 0, g_sliceEnd = 0;
bool     g_sliceEntriesClosed = false;

// Returns false when this tick must be ignored (before the slice). Stops the pass after the
// slice once no EA position is left open.
bool SliceAllowsTick()
  {
   if(!g_sliceOn)
      return true;
   const datetime now = TimeCurrent();
   if(g_sliceStart == 0)
     {
      // Anchor on the first tick of the test (day start), not on OnInit's clock, so every
      // pass of the optimization computes the same slice grid.
      const datetime testDay = now - (now % 86400);
      g_sliceStart = testDay + (datetime)((long)TesterSliceIndex * TesterSliceDays * 86400);
      g_sliceEnd   = g_sliceStart + (datetime)((long)TesterSliceDays * 86400);
      PrintFormat("[SLICE] #%d: trades %s .. %s (%d days), then stops once flat",
                  TesterSliceIndex, TimeToString(g_sliceStart, TIME_DATE | TIME_MINUTES),
                  TimeToString(g_sliceEnd, TIME_DATE | TIME_MINUTES), TesterSliceDays);
     }
   if(now < g_sliceStart)
      return false;
   if(now >= g_sliceEnd)
     {
      g_sliceEntriesClosed = true;
      long dir;
      if(CountOwnPositions(dir) == 0)
        {
         TesterStop();
         return false;
        }
     }
   return true;
  }

string AccountModeText()
  {
   switch((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE))
     {
      case ACCOUNT_TRADE_MODE_DEMO:    return "DEMO";
      case ACCOUNT_TRADE_MODE_CONTEST: return "CONTEST";
      default:                         return "REAL";
     }
  }

bool NewEntriesAllowedOnThisAccount(string &why)
  {
   if(IsTester())
      return true;
   const ENUM_ACCOUNT_TRADE_MODE m = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(m == ACCOUNT_TRADE_MODE_DEMO || m == ACCOUNT_TRADE_MODE_CONTEST)
      return true;
   if(AccountGuard != GUARD_DEMO_AND_REAL)
     {
      why = "REAL account and AccountGuard = Demo only";
      return false;
     }
   if(RealTradingConfirmation != REAL_CONFIRM_TEXT)
     {
      why = "REAL account: RealTradingConfirmation must be exactly '" + REAL_CONFIRM_TEXT + "'";
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Trading permission                                               |
//+------------------------------------------------------------------+
bool CheckTradingPermission(string &why)
  {
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))       { why = "terminal not connected"; return false; }
   if(!IsTester() && !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) { why = "Algo Trading button is OFF in the terminal"; return false; }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))             { why = "'Allow Algo Trading' is off in the EA properties"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))      { why = "broker disabled expert trading on this account"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))     { why = "trading disabled for this account (investor login?)"; return false; }
   const long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(mode != SYMBOL_TRADE_MODE_FULL)                 { why = "symbol trade mode is not FULL (market closed or restricted)"; return false; }
   return true;
  }

bool CheckSpread(string &why)
  {
   if(!EnableSpreadFilter)
      return true;
   if(g_maxSpreadPts <= 0)
     {
      why = "spread limit unavailable (auto spread needs history)";
      return false;
     }
   const int spread = ToPts(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(spread > g_maxSpreadPts)
     {
      why = StringFormat("spread %d pts > max %.0f pts", spread, g_maxSpreadPts);
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Position helpers (only our magic + symbol)                       |
//+------------------------------------------------------------------+
int CountOwnPositions(long &dirOut)
  {
   int c = 0;
   dirOut = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      c++;
      dirOut = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
     }
   return c;
  }

bool CloseOwnPositions(const string why)
  {
   bool ok = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      if(!g_trade.PositionClose(t, MaxDeviation))
        {
         Log("CLOSE FAILED", StringFormat("#%I64u %s retcode=%u", t, why, g_trade.ResultRetcode()));
         ok = false;
        }
      else
         Log("CLOSE", StringFormat("#%I64u %s", t, why));
     }
   return ok;
  }

//+------------------------------------------------------------------+
//| Signal lifecycle                                                 |
//+------------------------------------------------------------------+
bool IsDuplicateSignal(const datetime barTime)
  {
   if(!OneTradePerSignal)
      return false;
   return (datetime)(long)GvGet(SignalGv(), 0) == barTime;
  }

void MarkSignalConsumed(const datetime barTime) { GvSet(SignalGv(), (double)(long)barTime); }

//+------------------------------------------------------------------+
//| Filters                                                          |
//+------------------------------------------------------------------+
bool CalculateVolumeRatio(const bool isBuy, const TwkSnapshot &s, double &ratio, string &why)
  {
   const double own = isBuy ? s.bv1 : s.sv1;
   const double opp = isBuy ? s.sv1 : s.bv1;
   if(TwkIsNa(own) || TwkIsNa(opp)) { why = "Volume data unavailable"; ratio = 0; return false; }
   if(own <= 0 && opp <= 0)         { why = "Volume data unavailable (both zero)"; ratio = 0; return false; }
   ratio = (opp <= 0) ? DBL_MAX : own / opp;
   if(ratio + 1e-12 < MinimumVolumeRatio)
     {
      why = StringFormat("Volume ratio %.2f below %.2f", ratio, MinimumVolumeRatio);
      return false;
     }
   return true;
  }

bool BoxValid(const bool isBuy, const double bv, const double sv)
  {
   if(TwkIsNa(bv) || TwkIsNa(sv))
      return false;
   return isBuy ? (bv > sv) : (sv > bv);
  }

// Hard SL distance for the signal timeframe: used when the Tracker finds no confirmed pivot on the
// protective side, and on a quick re-flip (ReFlipAction = hard SL). 0 = the purple line instead.
ENUM_TIMEFRAMES ResolvedSignalTF() { return (SignalTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : SignalTimeframe; }

// Quick re-flip window in bars of the signal timeframe: ReFlipMinutes, at least 1 bar (M1 15, M3 5)
int ReFlipBarsForTF()
  {
   if(ReFlipMinutes <= 0)
      return 0;
   return MathMax(1, (int)MathRound(ReFlipMinutes * 60.0 / PeriodSeconds(ResolvedSignalTF())));
  }

int HardSLPoints()
  {
   switch(ResolvedSignalTF())
     {
      case PERIOD_M1:  return HardSL_M1;
      case PERIOD_M3:  return HardSL_M3;
      case PERIOD_M5:  return HardSL_M5;
      case PERIOD_M15: return HardSL_M15;
      case PERIOD_M30: return HardSL_M30;
      case PERIOD_H1:  return HardSL_H1;
      case PERIOD_H4:  return HardSL_H4;
      default:         return HardSL_Other;
     }
  }

// Initial SL candidate from the Tracker (or fallback). Validated later against the live price.
// `src` names where the stop came from, for the journal.
bool ValidateIndicatorSL(const bool isBuy, const TwkSnapshot &s, double &sl, string &src, string &why)
  {
   sl = 0;
   src = "";
   const bool indicatorOk = UseIndicatorSL && !TwkIsNa(s.sl) && s.sl > 0 && !TwkIsNa(s.risk) && s.risk > 0;
   if(indicatorOk)
     {
      sl = s.sl;
      src = s.slFromPivot ? "pivot" : "purple line, no pivot";
      return true;
     }
   if(EnableFallbackSL)
     {
      const double ref = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl = isBuy ? ref - Pts(FallbackSLPoints) : ref + Pts(FallbackSLPoints);
      src = StringFormat("fallback %d pts", FallbackSLPoints);
      Log("SL", "Tracker SL invalid - using FALLBACK SL " + P(sl));
      return true;
     }
   why = TwkIsNa(s.sl) ? "Indicator SL unavailable" : StringFormat("Indicator SL invalid (sl=%s risk=%s)", P(s.sl), P(s.risk));
   return false;
  }

bool ValidateIndicatorTP(const bool isBuy, const TwkSnapshot &s, double &tp, string &why)
  {
   tp = 0;
   if(UseIndicatorTP && !TwkIsNa(s.tp) && s.tp > 0)
     {
      tp = s.tp;
      return true;
     }
   if(EnableFallbackTP)
     {
      const double ref = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      tp = isBuy ? ref + Pts(FallbackTPPoints) : ref - Pts(FallbackTPPoints);
      Log("TP", "Tracker TP invalid - using FALLBACK TP " + P(tp));
      return true;
     }
   if(!UseIndicatorTP)
      return true;                           // user chose no TP
   why = "Indicator TP unavailable";
   return !RejectIfTPInvalid;
  }

// Final price-side + broker stop-level check against the LIVE price
bool ValidateStopsAtPrice(const bool isBuy, const double sl, const double tp, string &why)
  {
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   const double entry = isBuy ? ask : bid;
   const double ref   = isBuy ? bid : ask;         // SL/TP are checked against the closing price
   if(isBuy)
     {
      if(sl >= entry)            { why = StringFormat("SL %s not below entry %s", P(sl), P(entry)); return false; }
      if(ref - sl < stops)       { why = StringFormat("SL %s inside broker stop level (%s)", P(sl), DoubleToString(stops, _Digits)); return false; }
      if(tp > 0 && tp <= entry)  { why = StringFormat("TP %s not above entry %s", P(tp), P(entry)); return false; }
      if(tp > 0 && tp - ref < stops) { why = StringFormat("TP %s inside broker stop level", P(tp)); return false; }
     }
   else
     {
      if(sl <= entry)            { why = StringFormat("SL %s not above entry %s", P(sl), P(entry)); return false; }
      if(sl - ref < stops)       { why = StringFormat("SL %s inside broker stop level (%s)", P(sl), DoubleToString(stops, _Digits)); return false; }
      if(tp > 0 && tp >= entry)  { why = StringFormat("TP %s not below entry %s", P(tp), P(entry)); return false; }
      if(tp > 0 && ref - tp < stops) { why = StringFormat("TP %s inside broker stop level", P(tp)); return false; }
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Lot size                                                         |
//+------------------------------------------------------------------+
double NormalizeLot(double lots)
  {
   const double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathMin(lots, MaxLotSize);
   if(!IsTester() && AccountModeText() == "REAL")
      lots = MathMin(lots, RealAccountMaxLot);
   lots = MathMin(lots, vmax);
   if(vstep > 0)
      lots = MathFloor(lots / vstep + 1e-9) * vstep;
   if(lots < vmin - 1e-12)
      return 0;
   return NormalizeDouble(lots, 8);
  }

double CalculateLot(const bool isBuy, const double entry, const double sl, string &why)
  {
   double lots = LotSize;
   if(LotSizingMode == RISK_PERCENT)
     {
      double lossPerLot = 0;
      if(!OrderCalcProfit(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, 1.0, entry, sl, lossPerLot) || lossPerLot >= 0)
        {
         why = "cannot calculate risk per lot";
         return 0;
        }
      lots = AccountInfoDouble(ACCOUNT_BALANCE) * RiskPercent / 100.0 / MathAbs(lossPerLot);
     }
   lots = NormalizeLot(lots);
   if(lots <= 0)
     {
      why = StringFormat("lot below broker minimum %.2f (MaxLotSize/risk too small)", SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
      return 0;
     }
   double margin = 0;
   if(!OrderCalcMargin(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, entry, margin))
     {
      why = "cannot calculate margin";
      return 0;
     }
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      why = StringFormat("insufficient margin: need %.2f, free %.2f", margin, AccountInfoDouble(ACCOUNT_MARGIN_FREE));
      return 0;
     }
   return lots;
  }

//+------------------------------------------------------------------+
//| Entry decision                                                   |
//+------------------------------------------------------------------+
void Reject(const string reason)
  {
   g_lastReject = reason;
   g_state = WAITING_FOR_SIGNAL;
   Log("ENTRY REJECTED", reason);
  }

bool ValidateConditions(const bool isBuy, const TwkSnapshot &s, double &sl, double &tp)
  {
   string why;
   double ratio;
   const bool volOk = CalculateVolumeRatio(isBuy, s, ratio, why);
   Log("VOLUME", StringFormat("Buy=%.0f Sell=%.0f Ratio=%s %s", s.bv1, s.sv1,
                              ratio == DBL_MAX ? "inf" : DoubleToString(ratio, 2), volOk ? "PASS" : "FAIL"));
   if(!volOk) { Reject(why); return false; }

   const bool m1 = BoxValid(isBuy, s.bv1, s.sv1);
   Log("M1 BOX", StringFormat("Buy=%.0f Sell=%.0f %s", s.bv1, s.sv1, m1 ? "PASS" : "FAIL"));
   if(RequireM1Box && !m1) { Reject("M1 Box invalid (1m row " + (s.bv1 > s.sv1 ? "Positive" : s.bv1 < s.sv1 ? "Negative" : "Neutral") + ")"); return false; }

   if(TwkIsNa(s.bv3) || TwkIsNa(s.sv3)) { Reject("M3 Box unavailable"); return false; }
   const bool m3 = BoxValid(isBuy, s.bv3, s.sv3);
   Log("M3 BOX", StringFormat("Buy=%.0f Sell=%.0f (3m bar %s) %s", s.bv3, s.sv3, TimeToString(s.m3BarTime, TIME_MINUTES), m3 ? "PASS" : "FAIL"));
   if(RequireM3Box && !m3) { Reject("M3 Box invalid (3m row " + (s.bv3 > s.sv3 ? "Positive" : s.bv3 < s.sv3 ? "Negative" : "Neutral") + ")"); return false; }

   if(TwkIsNa(s.adx)) { Reject("ADX unavailable"); return false; }
   const bool adxOk = s.adx > ADXMinimum;
   Log("ADX", StringFormat("%.2f %s", s.adx, adxOk ? "PASS" : "FAIL"));
   if(!adxOk) { Reject(StringFormat("ADX %.2f not above %.2f", s.adx, ADXMinimum)); return false; }

   //--- quick re-flip: the pivot is older than the opposite signal a few bars back, so it sits behind
   //    the whole previous leg (the $27-41 stops of 2 Sep). That pivot is never used: skip the trade,
   //    or use the hard SL below.
   const bool reflip = UseIndicatorSL && s.reFlip && ReFlipBarsForTF() > 0 && ReFlipAction != TWK_REFLIP_KEEP_PIVOT;
   if(reflip && ReFlipAction == TWK_REFLIP_SKIP)
     {
      Reject(StringFormat("quick re-flip: opposite signal %d bars ago, pivot SL %s is older - trade skipped", s.oppAgo, P(s.sl)));
      return false;
     }

   //--- hard SL (no pivot, or a quick re-flip): fixed distance from the live entry price; TP keeps the
   //    1:RewardRisk shape. A distance not wider than spread + stop level would put the stop at or past
   //    the price it triggers on, so the purple line is used instead.
   if(UseIndicatorSL && (!s.slFromPivot || reflip))
     {
      const string why0   = reflip ? StringFormat("quick re-flip %d bars, old pivot %s not used", s.oppAgo, P(s.sl)) : "no pivot";
      const int    hardPts = (reflip && ReFlipAction == TWK_REFLIP_PURPLE) ? 0 : HardSLPoints();
      const double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      const double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      const int    minPts = ToPts(ask - bid) + (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      if(hardPts > minPts)
        {
         const double ref = isBuy ? ask : bid;
         sl = isBuy ? ref - Pts(hardPts) : ref + Pts(hardPts);
         Log("SL", StringFormat("%s VALID (%s: hard %d pts)", P(sl), why0, hardPts));
         if(UseIndicatorTP)
            tp = isBuy ? ref + RewardRisk * Pts(hardPts) : ref - RewardRisk * Pts(hardPts);
         else if(!ValidateIndicatorTP(isBuy, s, tp, why)) { Reject(why); return false; }
         Log("TP", (tp > 0 ? P(tp) : "none") + " VALID");
         return true;
        }
      if(hardPts > 0)
         Log("SL", StringFormat("%s: hard %d pts is not wider than spread + stop level (%d pts) - using the purple line",
                                why0, hardPts, minPts));
      if(reflip)
        {
         //--- purple-line stop from the signal close, TP = RewardRisk x that risk (Pine's formula)
         const double risk = isBuy ? s.close - s.purple : s.purple - s.close;
         if(TwkIsNa(s.purple) || risk <= 0)
           { Reject(StringFormat("quick re-flip: purple line %s not on the protective side - trade skipped", P(s.purple))); return false; }
         sl = s.purple;
         Log("SL", StringFormat("%s VALID (%s: purple line)", P(sl), why0));
         if(UseIndicatorTP)
            tp = isBuy ? s.close + RewardRisk * risk : s.close - RewardRisk * risk;
         else if(!ValidateIndicatorTP(isBuy, s, tp, why)) { Reject(why); return false; }
         Log("TP", (tp > 0 ? P(tp) : "none") + " VALID");
         return true;
        }
      // no pivot and no usable hard distance: the Tracker SL below is already the purple line
     }

   string src;
   if(!ValidateIndicatorSL(isBuy, s, sl, src, why)) { Reject(why); return false; }
   Log("SL", StringFormat("%s VALID (%s)", P(sl), src));
   if(!ValidateIndicatorTP(isBuy, s, tp, why)) { Reject(why); return false; }
   Log("TP", (tp > 0 ? P(tp) : "none") + " VALID");
   return true;
  }

void ProcessSignal(const TwkSnapshot &s)
  {
   if(s.signal == TWK_SIG_NONE || g_sliceEntriesClosed)
      return;
   const bool isBuy = (s.signal == TWK_SIG_LONG);
   if(IsDuplicateSignal(s.barTime))
      return;                                   // SAME LONG / SAME SHORT
   g_state = SIGNAL_DETECTED;
   Log("MOMENTUM", StringFormat("NEW %s on %s bar %s  close=%s purple=%s",
                                isBuy ? "LONG" : "SHORT", EnumToString(SignalTimeframe),
                                TimeToString(s.barTime, TIME_DATE | TIME_MINUTES), P(s.close), P(s.purple)));
   if(TradeOnClosedCandle)
      MarkSignalConsumed(s.barTime);            // confirmed signal: evaluated exactly once

   //--- opposite / existing position
   long dir;
   const int own = CountOwnPositions(dir);
   if(own > 0)
     {
      const bool opposite = (dir == 1 && !isBuy) || (dir == -1 && isBuy);
      if(opposite && (ReverseOnOppositeSignal || CloseOnOppositeSignal))
        {
         if(!CloseOwnPositions("opposite signal"))
           { Reject("could not close opposite position"); return; }
         if(!ReverseOnOppositeSignal)
           { g_state = WAITING_FOR_SIGNAL; return; }
        }
      else if(OnePositionPerSymbol)
        {
         Reject(opposite ? "opposite signal - existing position kept (Close/Reverse disabled)"
                         : "position already open (OnePositionPerSymbol)");
         return;
        }
     }

   g_state = VALIDATING_FILTERS;
   string why;
   if(g_entriesDisabled)                          { Reject("new entries disabled by emergency policy"); return; }
   if(!NewEntriesAllowedOnThisAccount(why))       { Reject(why); return; }
   if(!CheckTradingPermission(why))               { Reject(why); return; }

   double sl, tp;
   if(!ValidateConditions(isBuy, s, sl, tp))
      return;
   if(!CheckSpread(why))                          { Reject(why); return; }

   sl = NormPrice(sl);
   tp = (tp > 0) ? NormPrice(tp) : 0;
   if(!ValidateStopsAtPrice(isBuy, sl, tp, why)) { Reject(why); return; }

   g_state = READY_TO_EXECUTE;
   if(isBuy) ExecuteBuy(s, sl, tp);
   else      ExecuteSell(s, sl, tp);
  }

//+------------------------------------------------------------------+
//| Execution                                                        |
//+------------------------------------------------------------------+
bool IsRetryable(const uint rc)
  {
   return rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED || rc == TRADE_RETCODE_PRICE_OFF
          || rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION || rc == TRADE_RETCODE_TOO_MANY_REQUESTS;
  }

bool FindOwnPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && (ulong)PositionGetInteger(POSITION_MAGIC) == MagicNumber)
        { ticket = t; return true; }
     }
   return false;
  }

void ExecuteBuy(const TwkSnapshot &s, const double sl, const double tp)  { Execute(true, s, sl, tp); }
void ExecuteSell(const TwkSnapshot &s, const double sl, const double tp) { Execute(false, s, sl, tp); }

void Execute(const bool isBuy, const TwkSnapshot &s, const double sl, const double tp)
  {
   string why;
   const double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double lots = CalculateLot(isBuy, px, sl, why);
   if(lots <= 0) { Reject(why); return; }

   Log("ENTRY", StringFormat("%s %.2f lots  req=%s  SL=%s  TP=%s  (%s account)", isBuy ? "BUY" : "SELL",
                             lots, P(px), P(sl), tp > 0 ? P(tp) : "none", IsTester() ? "TESTER" : AccountModeText()));
   bool sent = false;
   for(int attempt = 1; attempt <= MathMax(1, MaxRetries); attempt++)
     {
      ulong existing;
      if(attempt > 1 && FindOwnPosition(existing)) { sent = true; break; }   // a timed-out order did fill
      const double p = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(!ValidateStopsAtPrice(isBuy, sl, tp, why)) { Reject("price moved: " + why); return; }
      const bool ok = isBuy ? g_trade.Buy(lots, _Symbol, p, sl, tp, TradeComment)
                            : g_trade.Sell(lots, _Symbol, p, sl, tp, TradeComment);
      const uint rc = g_trade.ResultRetcode();
      if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         if(rc == TRADE_RETCODE_DONE_PARTIAL)
            Log("FILL", StringFormat("PARTIAL fill %.2f of %.2f", g_trade.ResultVolume(), lots));
         sent = true;
         break;
        }
      Log("ORDER", StringFormat("attempt %d failed: retcode=%u %s", attempt, rc, g_trade.ResultRetcodeDescription()));
      if(!IsRetryable(rc))
        { Reject(StringFormat("broker rejected order (%u %s)", rc, g_trade.ResultRetcodeDescription())); return; }
      Sleep(300);                                // then re-read the live price
     }
   if(!sent) { Reject("order not filled after retries"); return; }

   //--- verify the actual position; never assume
   ulong ticket = 0;
   for(int k = 0; k < 10 && !FindOwnPosition(ticket); k++)
      Sleep(100);
   if(ticket == 0 || !PositionSelectByTicket(ticket))
     {
      Log("FILL", "order reported done but position not found yet - will be picked up by management");
      return;
     }
   const ulong  posId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   const double fill  = PositionGetDouble(POSITION_PRICE_OPEN);
   const double aSL   = PositionGetDouble(POSITION_SL);
   const double aTP   = PositionGetDouble(POSITION_TP);
   const double vol   = PositionGetDouble(POSITION_VOLUME);
   const double risk  = MathAbs(fill - sl);
   const double rew   = tp > 0 ? MathAbs(tp - fill) : 0;
   Log("FILL", StringFormat("#%I64u %s %.2f @ %s  SL=%s  TP=%s", ticket, isBuy ? "BUY" : "SELL", vol, P(fill), P(aSL), P(aTP)));
   Log("RISK", StringFormat("InitialRisk=%s PotentialReward=%s InitialRR=%s", DoubleToString(risk, _Digits),
                            DoubleToString(rew, _Digits), risk > 0 && rew > 0 ? DoubleToString(rew / risk, 2) : "n/a"));

   GvSet(GvName(posId, "stage"), 0);
   GvSet(GvName(posId, "src"), SRC_INITIAL);
   GvSet(GvName(posId, "isl"), sl);
   GvSet(GvName(posId, "tp"), tp);
   GvSet(GvName(posId, "msl"), aSL > 0 ? aSL : sl);
   GvSet(GvName(posId, "sig"), (double)(long)s.barTime);
   MarkSignalConsumed(s.barTime);
   g_state = POSITION_OPEN_INITIAL_SL;
   TradeBoxOpen(posId, isBuy, fill, aSL > 0 ? aSL : sl);

   if(aSL <= 0)
      EnsureProtection(ticket, isBuy, sl, tp);
  }

//+------------------------------------------------------------------+
//| Emergency protection: position without SL                       |
//+------------------------------------------------------------------+
bool EnsureProtection(const ulong ticket, const bool isBuy, const double sl, const double tp)
  {
   for(int k = 1; k <= MathMax(1, MaxRetries); k++)
     {
      if(g_trade.PositionModify(ticket, sl, tp))
        {
         Log("PROTECTION", StringFormat("#%I64u SL %s applied on retry %d", ticket, P(sl), k));
         return true;
        }
      Log("PROTECTION", StringFormat("#%I64u SL retry %d failed: %u %s", ticket, k, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      Sleep(300);
     }
   ApplyEmergency(ticket);
   return false;
  }

// EmergencyProtectionMode for a position that cannot be protected by an SL.
// Called every tick while the condition lasts, so logging is throttled.
void ApplyEmergency(const ulong ticket)
  {
   static datetime lastLog = 0;
   const bool logNow = (TimeCurrent() - lastLog >= 60);
   if(logNow)
      lastLog = TimeCurrent();
   switch(EmergencyProtectionMode)
     {
      case CLOSE_POSITION:
         if(logNow)
            Log("EMERGENCY", StringFormat("#%I64u cannot place SL - CLOSING position", ticket));
         if(!g_trade.PositionClose(ticket, MaxDeviation) && logNow)
            Log("EMERGENCY", StringFormat("#%I64u close failed: %u %s - retrying every tick", ticket,
                                          g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         break;
      case DISABLE_NEW_ENTRIES:
         if(logNow)
            Log("EMERGENCY", StringFormat("#%I64u cannot place SL - new entries DISABLED, will keep retrying", ticket));
         g_entriesDisabled = true;
         break;
      default:
         if(logNow)
            Log("EMERGENCY", StringFormat("#%I64u cannot place SL - will keep retrying every tick", ticket));
     }
  }

//+------------------------------------------------------------------+
//| Trade management                                                 |
//+------------------------------------------------------------------+
// Purple line usable for this position? It must be on the protective side of price.
bool ReadPurpleLine(const bool isBuy, double &purple)
  {
   purple = 0;
   if(!g_snapValid || TwkIsNa(g_snap.purple))
      return false;
   if(isBuy && g_snap.stDir != -1)   // trail flipped above price -> not a BUY stop
      return false;
   if(!isBuy && g_snap.stDir != 1)
      return false;
   purple = g_snap.purple;
   return true;
  }

bool StopIsLegal(const bool isBuy, const double sl, const double bid, const double ask)
  {
   const double stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   return isBuy ? (sl < bid - stops) : (sl > ask + stops);
  }

bool FrozenNow(const bool isBuy, const double curSL, const double curTP, const double bid, const double ask)
  {
   const double freeze = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL) * _Point;
   if(freeze <= 0)
      return false;
   const double ref = isBuy ? bid : ask;
   if(curSL > 0 && MathAbs(ref - curSL) <= freeze) return true;
   if(curTP > 0 && MathAbs(curTP - ref) <= freeze) return true;
   return false;
  }

// Accept `c` if it is more protective than `best` and legal; log (once per bar) when the
// broker stop level blocks a tighter stop, so a silent non-trail is visible in the journal.
void ConsiderCandidate(const bool isBuy, const ulong ticket, const double c, const ENUM_SL_SOURCE src, const string name,
                       const double bid, const double ask, double &best, ENUM_SL_SOURCE &bestSrc, string &bestWhy)
  {
   if(!(isBuy ? c > best : c < best))
      return;
   if(!StopIsLegal(isBuy, c, bid, ask))
     {
      static datetime lastLogBar = 0;
      const datetime bar = iTime(_Symbol, SignalTimeframe, 0);
      if(bar != lastLogBar)
        {
         lastLogBar = bar;
         Log("STOP LEVEL", StringFormat("#%I64u %s %s blocked: closer than broker stop level %d pts to price",
                                        ticket, name, P(c), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)));
        }
      return;
     }
   best = c;
   bestSrc = src;
   bestWhy = name;
  }

bool ModifyStopLoss(const ulong ticket, const ulong posId, const double newSL, const double tp, const ENUM_SL_SOURCE src, const string why)
  {
   if(TimeCurrent() - g_lastModifyFail < 2)
      return false;
   if(!g_trade.PositionModify(ticket, newSL, tp))
     {
      g_lastModifyFail = TimeCurrent();
      Log("MODIFY FAILED", StringFormat("#%I64u SL->%s (%s) retcode=%u %s", ticket, P(newSL), why, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
     }
   GvSet(GvName(posId, "msl"), newSL);
   GvSet(GvName(posId, "src"), src);
   Log(why, StringFormat("#%I64u SL=%s", ticket, P(newSL)));
   TradeSlMoved(posId, newSL);
   return true;
  }

void ManagePosition(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   const bool   isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   const ulong  posId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double curSL = PositionGetDouble(POSITION_SL);
   const double curTP = PositionGetDouble(POSITION_TP);
   const double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
      return;
   const double tick = TickSize();
   InitPositionState(ticket);                      // positions found after a restart or a delayed fill

   //--- no SL at all -> restore the most protective legal stop, else emergency policy
   if(curSL <= 0)
     {
      const double lastSL = GvGet(GvName(posId, "msl"), 0);   // last SL the EA managed (never loosen)
      const double initSL = GvGet(GvName(posId, "isl"), 0);
      double target = 0;
      if(lastSL > 0 && StopIsLegal(isBuy, lastSL, bid, ask))
         target = lastSL;
      else if(initSL > 0 && StopIsLegal(isBuy, initSL, bid, ask))
         target = initSL;
      if(target > 0)
        {
         if(EnsureProtection(ticket, isBuy, target, curTP))
            GvSet(GvName(posId, "msl"), target);
        }
      else
         ApplyEmergency(ticket);                   // stop unknown or already crossed
      return;
     }

   //--- manual SL change detection
   const double msl = GvGet(GvName(posId, "msl"), curSL);
   if(MathAbs(curSL - msl) > tick / 2)
     {
      const bool tighter = isBuy ? curSL > msl : curSL < msl;
      if(RespectManualSL || tighter)
        {
         Log("MANUAL SL", StringFormat("#%I64u SL changed %s -> %s, kept", ticket, P(msl), P(curSL)));
         GvSet(GvName(posId, "msl"), curSL);
         GvSet(GvName(posId, "src"), SRC_MANUAL);
        }
      else if(StopIsLegal(isBuy, msl, bid, ask))
        {
         ModifyStopLoss(ticket, posId, msl, curTP, (ENUM_SL_SOURCE)(int)GvGet(GvName(posId, "src"), SRC_INITIAL), "RESTORE SL");
         return;
        }
     }

   //--- stage (never decreases; recovered from SL position after restart)
   const double profit = isBuy ? bid - entry : entry - ask;
   int stage = (int)GvGet(GvName(posId, "stage"), 0);
   const bool slLocked = isBuy ? curSL >= entry + Pts(ProfitLockPoints) - tick : curSL <= entry - Pts(ProfitLockPoints) + tick;
   if(slLocked || profit >= Pts(ProfitProtectionActivationPoints) - _Point / 2)
      stage = MathMax(stage, 2);
   else if(profit >= Pts(PurpleTrailActivationPoints) - _Point / 2)
      stage = MathMax(stage, 1);
   const int oldStage = (int)GvGet(GvName(posId, "stage"), 0);
   if(stage != oldStage)
     {
      Log(stage == 1 ? "STAGE 1" : "STAGE 2", StringFormat("#%I64u Profit=%d pts -> %s", ticket, ToPts(profit),
                                                           stage == 1 ? "purple-line trailing active" : "profit lock active"));
      GvSet(GvName(posId, "stage"), stage);
     }
   g_state = stage == 0 ? POSITION_OPEN_INITIAL_SL : stage == 1 ? PURPLE_TRAILING
             : (EnableOneToOneTrailing ? ONE_TO_ONE_TRAILING : PROFIT_LOCKED);
   if(stage == 0)
      return;
   if(FrozenNow(isBuy, curSL, curTP, bid, ask))
      return;

   //--- protective candidates
   double best = curSL;
   ENUM_SL_SOURCE bestSrc = SRC_INITIAL;
   string bestWhy = "";
   double purple;
   if(EnablePurpleLineTrailing && ReadPurpleLine(isBuy, purple))
      ConsiderCandidate(isBuy, ticket, NormPrice(purple), SRC_PURPLE, "PURPLE TRAIL", bid, ask, best, bestSrc, bestWhy);
   if(stage >= 2)
     {
      const double lock = NormPrice(isBuy ? entry + Pts(ProfitLockPoints) : entry - Pts(ProfitLockPoints));
      ConsiderCandidate(isBuy, ticket, lock, SRC_LOCK, "PROFIT LOCK", bid, ask, best, bestSrc, bestWhy);
      if(EnableOneToOneTrailing)
        {
         const double gap = Pts(ProfitProtectionActivationPoints - ProfitLockPoints);
         const double oto = NormPrice(isBuy ? bid - gap : ask + gap);
         ConsiderCandidate(isBuy, ticket, oto, SRC_ONE_TO_ONE, "1:1 TRAIL", bid, ask, best, bestSrc, bestWhy);
        }
     }
   if(bestWhy == "")
      return;
   //--- avoid a modification on every tick; the profit lock is always applied at once
   const double improvement = MathAbs(best - curSL);
   if(bestSrc != SRC_LOCK && improvement < Pts(MinSLImprovementPoints) - _Point / 2)
      return;
   ModifyStopLoss(ticket, posId, best, curTP, bestSrc,
                  StringFormat("%s Profit=%d pts", bestWhy, ToPts(profit)));
  }

void ManageOpenPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      ManagePosition(t);
     }
  }

//+------------------------------------------------------------------+
//| Restart recovery                                                 |
//+------------------------------------------------------------------+
// Rebuilds missing management state for an EA position (after a crash that lost the
// GlobalVariables, or when the fill was confirmed late). The initial SL is taken from the
// opening order, because the EA always sends the SL with the order. If the live SL is already
// tighter than that, the trade was being trailed, so it resumes at stage >= 1 instead of 0.
// Stage 2 is re-derived by ManagePosition from the SL sitting at or beyond the profit lock.
void InitPositionState(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   const ulong posId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   if(GlobalVariableCheck(GvName(posId, "isl")) && GlobalVariableCheck(GvName(posId, "msl")))
      return;
   const bool   isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   const double sl    = PositionGetDouble(POSITION_SL);
   const double tp    = PositionGetDouble(POSITION_TP);
   double openSL = 0;
   if(HistorySelectByPosition(posId))
      for(int d = 0; d < HistoryDealsTotal(); d++)
        {
         const ulong dt = HistoryDealGetTicket(d);
         if(HistoryDealGetInteger(dt, DEAL_ENTRY) != DEAL_ENTRY_IN)
            continue;
         const ulong ord = (ulong)HistoryDealGetInteger(dt, DEAL_ORDER);
         if(HistoryOrderSelect(ord))
            openSL = HistoryOrderGetDouble(ord, ORDER_SL);
        }
   PositionSelectByTicket(ticket);                 // keep the position selected for callers
   const double tick = TickSize();
   const bool trailed = sl > 0 && openSL > 0 && (isBuy ? sl > openSL + tick / 2 : sl < openSL - tick / 2);
   if(!GlobalVariableCheck(GvName(posId, "isl")))
     {
      GvSet(GvName(posId, "isl"), openSL > 0 ? openSL : sl);
      GvSet(GvName(posId, "tp"), tp);
      GvSet(GvName(posId, "stage"), trailed ? 1 : 0);
      GvSet(GvName(posId, "src"), trailed ? SRC_PURPLE : SRC_INITIAL);
     }
   if(!GlobalVariableCheck(GvName(posId, "msl")))
      GvSet(GvName(posId, "msl"), sl);
   Log("STATE", StringFormat("#%I64u state rebuilt: initial SL %s (from opening order: %s), current SL %s, stage %d",
                             ticket, P(GvGet(GvName(posId, "isl"), 0)), openSL > 0 ? "yes" : "no", P(sl),
                             (int)GvGet(GvName(posId, "stage"), 0)));
  }

void RecoverExistingPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      InitPositionState(t);
      const ulong posId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      const double sl = PositionGetDouble(POSITION_SL);
      Log("RECOVERY", StringFormat("#%I64u %s %.2f @ %s SL=%s TP=%s stage=%d - management resumed",
                                   t, PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL",
                                   PositionGetDouble(POSITION_VOLUME), P(PositionGetDouble(POSITION_PRICE_OPEN)), P(sl),
                                   P(PositionGetDouble(POSITION_TP)), (int)GvGet(GvName(posId, "stage"), 0)));
      ManagePosition(t);                          // tighten immediately if price moved while offline
     }
  }

//+------------------------------------------------------------------+
//| Closed-trade bookkeeping                                          |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber || HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   const long entryType = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entryType != DEAL_ENTRY_OUT && entryType != DEAL_ENTRY_OUT_BY)
      return;
   const ulong posId = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   if(PositionSelectByTicket(posId))
      return;                                        // partial close, position still open

   const long   reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   const int    src    = (int)GvGet(GvName(posId, "src"), SRC_INITIAL);
   int bucket;
   if(reason == DEAL_REASON_TP)      bucket = 5;
   else if(reason == DEAL_REASON_SL) bucket = src;
   else                              bucket = 6;
   if(bucket == 6) g_exitOther++; else g_exitCount[bucket]++;

   const double exitPx = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   const double pnl    = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   Log("EXIT", StringFormat("position %I64u closed @ %s  P/L=%.2f  reason=%s", posId, P(exitPx), pnl, g_exitNames[bucket]));
   g_state = EXITED;

   if(WriteTradeLog)
      AppendTradeLog(posId, exitPx, pnl, g_exitNames[bucket]);
   TradeBoxClose(posId, exitPx, pnl, g_exitNames[bucket]);
   string keys[] = {"stage", "src", "isl", "tp", "msl", "sig", "dir", "fill", "t0", "seg", "segn"};
   for(int k = 0; k < ArraySize(keys); k++)
      GlobalVariableDel(GvName(posId, keys[k]));
  }

// Live: TWK_trades_<sym>_<magic>.csv (appends forever). Tester: ..._tester.csv, or ..._tester_sNN.csv
// per slice so parallel optimization agents never write to the same file.
string TradeLogName()
  {
   if(!IsTester())
      return StringFormat("TWK_trades_%s_%I64u.csv", _Symbol, MagicNumber);
   if(g_sliceOn)
      return StringFormat("TWK_trades_%s_%I64u_tester_s%02d.csv", _Symbol, MagicNumber, TesterSliceIndex);
   return StringFormat("TWK_trades_%s_%I64u_tester.csv", _Symbol, MagicNumber);
  }

void AppendTradeLog(const ulong posId, const double exitPx, const double pnl, const string reason)
  {
   double entry = 0, vol = 0;
   datetime openT = 0;
   long type = -1;
   if(HistorySelectByPosition(posId))
      for(int i = 0; i < HistoryDealsTotal(); i++)
        {
         const ulong d = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
           {
            entry = HistoryDealGetDouble(d, DEAL_PRICE);
            vol   = HistoryDealGetDouble(d, DEAL_VOLUME);
            openT = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
            type  = HistoryDealGetInteger(d, DEAL_TYPE);
           }
        }
   const double isl  = GvGet(GvName(posId, "isl"), 0);
   const double tp   = GvGet(GvName(posId, "tp"), 0);
   const double risk = (isl > 0 && entry > 0) ? MathAbs(entry - isl) : 0;
   const double rew  = (tp > 0 && entry > 0) ? MathAbs(tp - entry) : 0;
   const string name = TradeLogName();
   const bool exists = FileIsExist(name, FILE_COMMON);
   const int h = FileOpen(name, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   if(!exists)
      FileWrite(h, "position", "account", "side", "volume", "open_time", "close_time", "entry", "initial_sl", "tp",
                "initial_risk", "potential_reward", "initial_rr", "exit", "pnl", "exit_reason", "stage");
   FileWrite(h, (string)posId, IsTester() ? "TESTER" : AccountModeText(), type == DEAL_TYPE_BUY ? "BUY" : "SELL",
             DoubleToString(vol, 2), TimeToString(openT, TIME_DATE | TIME_SECONDS), TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
             P(entry), P(isl), P(tp), DoubleToString(risk, _Digits), DoubleToString(rew, _Digits),
             risk > 0 && rew > 0 ? DoubleToString(rew / risk, 2) : "", P(exitPx), DoubleToString(pnl, 2), reason,
             (string)(int)GvGet(GvName(posId, "stage"), 0));
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Performance statistics (tester + on removal)                     |
//+------------------------------------------------------------------+
void PrintStatistics()
  {
   if(!HistorySelect(0, TimeCurrent() + 86400))
      return;
   int total = 0, buys = 0, sells = 0, wins = 0, losses = 0, be = 0, cw = 0, cl = 0, maxCW = 0, maxCL = 0;
   double gp = 0, gl = 0, net = 0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      const ulong d = HistoryDealGetTicket(i);
      if((ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)
         continue;
      const long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY)
         continue;
      const double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      total++;
      // the closing deal of a BUY is a SELL deal
      if(HistoryDealGetInteger(d, DEAL_TYPE) == DEAL_TYPE_SELL) buys++; else sells++;
      net += p;
      if(p > 0.005)       { wins++; gp += p; cw++; cl = 0; maxCW = MathMax(maxCW, cw); }
      else if(p < -0.005) { losses++; gl += p; cl++; cw = 0; maxCL = MathMax(maxCL, cl); }
      else                { be++; }
     }
   Print("==================== TWK EA STATISTICS ====================");
   PrintFormat("Total trades %d | BUY %d | SELL %d | Win %d | Loss %d | Break-even %d", total, buys, sells, wins, losses, be);
   PrintFormat("Win rate %.1f%% | Net %.2f | Gross profit %.2f | Gross loss %.2f | Profit factor %s",
               total > 0 ? 100.0 * wins / total : 0, net, gp, gl, gl < 0 ? DoubleToString(gp / -gl, 2) : "n/a");
   PrintFormat("Average trade %.2f | Average winner %.2f | Average loser %.2f | Max consecutive wins %d / losses %d",
               total > 0 ? net / total : 0, wins > 0 ? gp / wins : 0, losses > 0 ? gl / losses : 0, maxCW, maxCL);
   if(IsTester())
      PrintFormat("Max drawdown %.2f%% (equity)", TesterStatistics(STAT_EQUITY_DDREL_PERCENT));
   string br = "Exit breakdown (this session):";
   for(int k = 0; k < 6; k++)
      br += StringFormat(" %s=%d |", g_exitNames[k], g_exitCount[k]);
   br += StringFormat(" %s=%d", g_exitNames[6], g_exitOther);
   Print(br);
   Print("Per-trade initial risk / reward / R:R are in the TWK_trades CSV (Common\\Files).");
  }

double OnTester()
  {
   PrintStatistics();
   const double pf = TesterStatistics(STAT_PROFIT_FACTOR);
   return pf;
  }

//+------------------------------------------------------------------+
//| Debug panel + per-bar log                                        |
//+------------------------------------------------------------------+
void LogTradeDecision(const TwkSnapshot &s)
  {
   if(!DebugIndicatorMode || (IsTester() && !TesterDebugLog))
      return;
   Log("BAR", StringFormat("%s sig=%s purple=%s dir=%d SL=%s TP=%s 1m B/S=%.0f/%.0f 3m B/S=%.0f/%.0f ADX=%.2f state=%s",
                           TimeToString(s.barTime, TIME_DATE | TIME_MINUTES), TwkSignalText(s.signal), P(s.purple), s.stDir,
                           P(s.sl), P(s.tp), s.bv1, s.sv1, s.bv3, s.sv3, s.adx, StateText(g_state)));
  }

void UpdatePanel()
  {
   if(!ShowDebugPanel || g_fastTester)
      return;
   static uint lastPaint = 0;                      // repaint at most 4x per second
   const uint nowMs = GetTickCount();
   if(lastPaint != 0 && nowMs - lastPaint < 250)
      return;
   lastPaint = nowMs;
   string guard;
   const bool entriesOk = NewEntriesAllowedOnThisAccount(guard);
   string t = StringFormat("TWK Momentum EA  |  %s account %I64d  |  %s\n", IsTester() ? "TESTER" : AccountModeText(),
                           AccountInfoInteger(ACCOUNT_LOGIN), entriesOk ? "NEW TRADES: ON" : "NEW TRADES: OFF (" + guard + ")");
   t += StringFormat("Lot: %s %.2f (max %.2f)  Magic %I64u\n", LotSizingMode == FIXED ? "FIXED" : "RISK%", LotSizingMode == FIXED ? LotSize : RiskPercent, MaxLotSize, MagicNumber);
   t += StringFormat("Spread: %d pts (max %.0f%s)   Trail: purple at +%d pts, lock +%d at +%d pts, then 1:1\n",
                     ToPts(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)), g_maxSpreadPts,
                     MaxSpreadPoints > 0 ? "" : " auto", PurpleTrailActivationPoints, ProfitLockPoints, ProfitProtectionActivationPoints);
   if(g_snapValid)
     {
      double r = 0;
      string w;
      const bool isBuy = g_snap.stDir == -1;
      CalculateVolumeRatio(g_snap.signal == TWK_SIG_SHORT ? false : (g_snap.signal == TWK_SIG_LONG ? true : isBuy), g_snap, r, w);
      t += StringFormat("Bar %s  Momentum Signal: %s   Trail: %s\n", TimeToString(g_snap.barTime, TIME_MINUTES), TwkSignalText(g_snap.signal), g_snap.stDir == -1 ? "UP" : "DOWN");
      t += StringFormat("Buy Volume: %.0f  Sell Volume: %.0f  Ratio: %s %s\n", g_snap.bv1, g_snap.sv1, r == DBL_MAX ? "inf" : DoubleToString(r, 2), r >= MinimumVolumeRatio ? "PASS" : "FAIL");
      t += StringFormat("M1 Box: %s   M3 Box: %s   ADX: %.1f %s\n",
                        g_snap.bv1 > g_snap.sv1 ? "BUY" : g_snap.bv1 < g_snap.sv1 ? "SELL" : "NEUTRAL",
                        g_snap.bv3 > g_snap.sv3 ? "BUY" : g_snap.bv3 < g_snap.sv3 ? "SELL" : "NEUTRAL", g_snap.adx, g_snap.adx > ADXMinimum ? "PASS" : "FAIL");
      t += StringFormat("Indicator SL: %s  TP: %s  Purple Line: %s\n", P(g_snap.sl), P(g_snap.tp), P(g_snap.purple));
     }
   else
      t += "Indicator: waiting for data\n";
   t += "Stage: " + StateText(g_state) + "\n";
   if(g_lastReject != "")
      t += "Last reject: " + g_lastReject + "\n";
   Comment(t);
  }

//+------------------------------------------------------------------+
//| Indicator refresh                                                |
//+------------------------------------------------------------------+
bool RefreshClosedBar()
  {
   static string lastErr = "";
   TwkSeries series;
   TwkSnapshot s;
   if(!g_engine.Evaluate(1, s, series))
     {
      if(s.error != lastErr)
         Log("DATA", "indicator not ready: " + s.error + " - NO TRADE until data is complete");
      lastErr = s.error;
      g_snapValid = false;
      return false;
     }
   lastErr = "";
   g_snap = s;
   g_snapValid = true;
   return true;
  }

//+------------------------------------------------------------------+
//| Standard handlers                                                |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(ADXMinimum < 0 || MinimumVolumeRatio <= 0 || LotSize <= 0 || MaxLotSize <= 0 || PurpleTrailActivationPoints <= 0
      || ProfitProtectionActivationPoints <= ProfitLockPoints || ProfitLockPoints < 0 || MaxSpreadPoints < 0
      || SpreadAutoMultiplier <= 0 || MinSLImprovementPoints < 0)
     {
      Print("Invalid inputs: check volume ratio, lot sizes and trailing distances");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(HardSL_M1 < 0 || HardSL_M3 < 0 || HardSL_M5 < 0 || HardSL_M15 < 0 || HardSL_M30 < 0
      || HardSL_H1 < 0 || HardSL_H4 < 0 || HardSL_Other < 0 || ReFlipMinutes < 0)
     {
      Print("Invalid inputs: HardSL points and ReFlipMinutes cannot be negative (0 = purple line / off)");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(ReverseOnOppositeSignal && !OnePositionPerSymbol)
      Print("Note: ReverseOnOppositeSignal is used with OnePositionPerSymbol=false");

   g_prefix = StringFormat("TWK.%I64u", MagicNumber);
   TwkDefaultParams(g_p);
   g_p.stMult    = TrailMultiplier;
   g_p.stATR     = TrailATRLength;
   g_p.pivLen    = PivotStrength;
   g_p.rr        = RewardRisk;
   g_p.volLen    = VolumeLength;
   g_p.diLen     = ADXPeriod;
   g_p.adxSmooth = ADXSmoothing;
   g_p.pivotTie  = PivotTieRule;
   g_p.reflipBars = ReFlipBarsForTF();
   g_engine.Init(_Symbol, SignalTimeframe, CalcBars, g_p);
   AttachTracker();

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(MaxDeviation);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetAsyncMode(false);
   ArrayInitialize(g_exitCount, 0);

   string why;
   g_realBlocked = !NewEntriesAllowedOnThisAccount(why);
   PrintFormat("TWK Momentum EA started on %s | account %I64d (%s) | server %s | signal TF %s | lot %s %.2f",
               _Symbol, AccountInfoInteger(ACCOUNT_LOGIN), IsTester() ? "TESTER" : AccountModeText(),
               AccountInfoString(ACCOUNT_SERVER), EnumToString(SignalTimeframe),
               LotSizingMode == FIXED ? "FIXED" : "RISK%", LotSizingMode == FIXED ? LotSize : RiskPercent);
   if(g_realBlocked)
      Print("*** SAFETY: ", why, ". The EA will show signals and manage its own existing positions, but will NOT open trades. ***");
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      Print("Note: netting account - manual trades on this symbol merge with EA positions.");

   //--- Strategy Tester speed-ups (no effect in live trading)
   g_fastTester = IsTester() && !MQLInfoInteger(MQL_VISUAL_MODE);
   g_sliceOn = IsTester() && TesterSliceDays > 0;
   if(g_sliceOn)
     {
      if(TesterSliceIndex < 0)
        {
         Print("Invalid inputs: TesterSliceIndex must be >= 0");
         return INIT_PARAMETERS_INCORRECT;
        }
      g_sliceStart = 0;                                       // window is set on the first tick
      g_sliceEnd   = 0;
     }
   else if(!IsTester() && TesterSliceDays > 0)
      Print("Note: TesterSliceDays is ignored outside the Strategy Tester");
   if(IsTester() && WriteTradeLog)
      FileDelete(TradeLogName(), FILE_COMMON);               // a fresh trade CSV per test run

   LogSymbolSpecs();
   UpdateSpreadLimit();
   RecoverExistingPosition();
   g_exportPending = ExportDiagnosticsCSV && !IsTester();
   TryExportDiagnostics();
   if(!g_fastTester)
      EventSetTimer(1);                                      // panel + data retries (live / visual test)
   return INIT_SUCCEEDED;
  }

void LogSymbolSpecs()
  {
   PrintFormat("[SYMBOL] %s digits=%d point=%s tick=%s contract=%.2f stops=%d pts freeze=%d pts vol min/step/max=%.2f/%.2f/%.2f spread now=%d pts",
               _Symbol, _Digits, DoubleToString(_Point, _Digits), DoubleToString(TickSize(), _Digits),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
               ToPts(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)));
   PrintFormat("[PERMISSION] terminal AlgoTrading=%s  EA AllowAlgoTrading=%s  account expert trading=%s  symbol trade mode=%d",
               TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ON" : "OFF", MQLInfoInteger(MQL_TRADE_ALLOWED) ? "ON" : "OFF",
               AccountInfoInteger(ACCOUNT_TRADE_EXPERT) ? "ON" : "OFF", (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE));
   PrintFormat("[CONFIG] trail: purple at +%d pts, lock +%d pts at +%d pts, 1:1 gap %d pts | fallback SL/TP %s/%s | spread max %s | hard SL %s | re-flip %s",
               PurpleTrailActivationPoints, ProfitLockPoints, ProfitProtectionActivationPoints,
               ProfitProtectionActivationPoints - ProfitLockPoints,
               EnableFallbackSL ? (string)FallbackSLPoints + " pts" : "off", EnableFallbackTP ? (string)FallbackTPPoints + " pts" : "off",
               MaxSpreadPoints > 0 ? (string)MaxSpreadPoints + " pts" : StringFormat("auto (%.1fx median)", SpreadAutoMultiplier),
               HardSLPoints() > 0 ? StringFormat("%d pts (%s)", HardSLPoints(), EnumToString(ResolvedSignalTF())) : "purple line",
               ReFlipBarsForTF() <= 0 || ReFlipAction == TWK_REFLIP_KEEP_PIVOT ? "off (old pivot kept)"
               : StringFormat("%s within %d min (%d bars)", ReFlipAction == TWK_REFLIP_SKIP ? "skip"
                              : ReFlipAction == TWK_REFLIP_PURPLE ? "purple line" : "hard SL", ReFlipMinutes, ReFlipBarsForTF()));
  }

// Diagnostics CSV for the Pine-vs-MT5 check. History is often still loading right after a
// terminal start, so retry for up to ~2 minutes instead of giving up on the first attempt.
void TryExportDiagnostics()
  {
   if(!g_exportPending)
      return;
   string err;
   const string fn = StringFormat("TWK_diag_%s_%s.csv", _Symbol, StringSubstr(EnumToString(SignalTimeframe), 7));
   if(TwkExportDiagnostics(_Symbol, SignalTimeframe, CalcBars + ExportBars, ExportBars, g_p, fn, err))
     {
      PrintFormat("[DIAG] exported %d closed bars to Common\\Files\\%s", ExportBars, fn);
      g_exportPending = false;
      return;
     }
   if(++g_exportTries >= 12)
     {
      Print("[DIAG] export skipped: ", err);
      g_exportPending = false;
     }
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(!IsTester())
      PrintStatistics();
   DetachTracker();
   if(reason == REASON_REMOVE && !IsTester())
      ObjectsDeleteAll(0, TWK_TRADE_PREFIX);         // the EA was taken off the chart: tidy up
   Comment("");
  }

//+------------------------------------------------------------------+
//| Chart Tracker: display only. Signals, SL and TP always come from |
//| the EA's own engine; a failure here never blocks trading.        |
//+------------------------------------------------------------------+
void AttachTracker()
  {
   if(!ShowTrackerOnChart || MQLInfoInteger(MQL_OPTIMIZATION))
      return;                                        // optimization passes never show a chart
   if(!IsTester() && ResolvedSignalTF() != (ENUM_TIMEFRAMES)_Period)
     {
      Log("CHART", StringFormat("signals are %s but this chart is %s - attach the EA to a %s chart to see the Tracker",
                                EnumToString(ResolvedSignalTF()), EnumToString((ENUM_TIMEFRAMES)_Period),
                                EnumToString(ResolvedSignalTF())));
      return;                                        // display only: nothing to draw on this chart
     }
   // parameters in the exact input order of TWK_Tracker_MT5.mq5 (which has no `input group` lines)
   g_trackerHandle = iCustom(_Symbol, ResolvedSignalTF(), TWK_TRACKER_RES,
                             TrailMultiplier, TrailATRLength, PivotStrength, RewardRisk, VolumeLength, PivotTieRule,
                             ADXPeriod, ADXSmoothing, ChartTrackerBars <= 0 ? 0 : MathMax(ChartTrackerBars, 300), false, ExportBars,
                             true, 24, MathMax(1, ChartBoxHistory), UseIndicatorSL ? HardSLPoints() : 0,
                             UseIndicatorSL ? ReFlipBarsForTF() : 0, ReFlipAction,
                             IsTester() ? TimeCurrent() : (datetime)0, "TWKEA_",
                             MinimumVolumeRatio, RequireM1Box, RequireM3Box, ADXMinimum);
   if(g_trackerHandle == INVALID_HANDLE)
     {
      Log("CHART", StringFormat("Tracker not loaded (err %d) - trading is not affected", GetLastError()));
      return;
     }
   if(IsTester())
     {
      // the tester draws indicators created by the EA, but on the test chart only for its own period
      if(ResolvedSignalTF() != (ENUM_TIMEFRAMES)_Period)
         PrintFormat("*** CHART: SignalTimeframe is %s but the tester Period is %s. Set the tester Period to %s to see the "
                     "purple line, arrows and SL/TP boxes on the test chart. Trading is not affected. ***",
                     EnumToString(ResolvedSignalTF()), EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(ResolvedSignalTF()));
      return;
     }
   if(!ChartIndicatorAdd(0, 0, g_trackerHandle))
      Log("CHART", StringFormat("Tracker not added to the chart (err %d) - trading is not affected", GetLastError()));
  }

void DetachTracker()
  {
   if(g_trackerHandle == INVALID_HANDLE)
      return;
   if(IsTester())
      return;                                        // keep it for the chart the tester opens after the test
   ChartIndicatorDelete(0, 0, TWK_TRACKER_NAME);
   IndicatorRelease(g_trackerHandle);
   g_trackerHandle = INVALID_HANDLE;
  }

//+------------------------------------------------------------------+
//| Trade boxes: each real position from its fill to its exit, with  |
//| the initial SL (red outline), TP (green outline) and the SL as   |
//| it trails (orange steps). Drawn live and in visual tests; a fast |
//| (non-visual) test cannot show objects, so it skips them.         |
//+------------------------------------------------------------------+
bool   TradeBoxesOn()                  { return ShowTrackerOnChart && !g_fastTester; }
string TradeBase(const ulong posId)    { return TWK_TRADE_PREFIX + (string)posId; }
string TradeSeg(const ulong posId, const int k) { return TradeBase(posId) + "_P" + (string)k; }

void TradeRect(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
               const color c, const string tip)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
         return;
      ObjectSetInteger(0, name, OBJPROP_COLOR, c);
      ObjectSetInteger(0, name, OBJPROP_FILL, false);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void TradeSlSegment(const string name, const datetime t1, const datetime t2, const double price)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price))
         return;
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrOrange);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_TOOLTIP, "SL " + P(price));
     }
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
  }

string TradeTip(const ulong posId, const string tail)
  {
   const double fill = GvGet(GvName(posId, "fill"), 0);
   const double isl  = GvGet(GvName(posId, "isl"), 0);
   return StringFormat("#%I64u %s @ %s\nInitial SL %s = %s away\nTP %s%s", posId,
                       GvGet(GvName(posId, "dir"), 1) > 0 ? "BUY" : "SELL", P(fill), P(isl),
                       DoubleToString(MathAbs(fill - isl), _Digits), P(GvGet(GvName(posId, "tp"), 0)), tail);
  }

// Redraw a trade's boxes and stretch its current SL step up to time t
void TradeBoxUpdate(const ulong posId, const datetime t, const string tail)
  {
   const datetime t0 = (datetime)(long)GvGet(GvName(posId, "t0"), 0);
   if(t0 <= 0)
      return;                                        // opened before this EA session: not drawn
   const string   base = TradeBase(posId);
   const double   fill = GvGet(GvName(posId, "fill"), 0);
   const double   isl  = GvGet(GvName(posId, "isl"), 0);
   const double   tp   = GvGet(GvName(posId, "tp"), 0);
   const datetime t2   = MathMax(t, t0);
   const string   tip  = TradeTip(posId, tail);
   if(isl > 0) TradeRect(base + "_S", t0, fill, t2, isl, clrTomato, tip);
   if(tp > 0)  TradeRect(base + "_T", t0, fill, t2, tp, clrMediumSeaGreen, tip);
   const string seg = TradeSeg(posId, (int)GvGet(GvName(posId, "segn"), 0));
   if(ObjectFind(0, seg) >= 0)
      ObjectSetInteger(0, seg, OBJPROP_TIME, 1, t2);
  }

void TradeBoxOpen(const ulong posId, const bool isBuy, const double fill, const double sl)
  {
   if(!TradeBoxesOn())
      return;
   const datetime t = TimeCurrent();
   GvSet(GvName(posId, "dir"), isBuy ? 1 : -1);
   GvSet(GvName(posId, "fill"), fill);
   GvSet(GvName(posId, "t0"), (double)(long)t);
   GvSet(GvName(posId, "seg"), (double)(long)t);
   GvSet(GvName(posId, "segn"), 0);
   TradeSlSegment(TradeSeg(posId, 0), t, t, sl);
   TradeBoxUpdate(posId, t, "\nopen");
  }

void TradeSlMoved(const ulong posId, const double newSL)
  {
   if(!TradeBoxesOn() || GvGet(GvName(posId, "t0"), 0) <= 0)
      return;
   const datetime t   = TimeCurrent();
   const int      k   = (int)GvGet(GvName(posId, "segn"), 0);
   const string   cur = TradeSeg(posId, k);
   if(t <= (datetime)(long)GvGet(GvName(posId, "seg"), 0) && ObjectFind(0, cur) >= 0)
     {
      // several moves in the same second: one step at the newest level
      ObjectSetDouble(0, cur, OBJPROP_PRICE, 0, newSL);
      ObjectSetDouble(0, cur, OBJPROP_PRICE, 1, newSL);
      ObjectSetString(0, cur, OBJPROP_TOOLTIP, "SL " + P(newSL));
      return;
     }
   if(ObjectFind(0, cur) >= 0)
      ObjectSetInteger(0, cur, OBJPROP_TIME, 1, t);  // the old level ends here
   GvSet(GvName(posId, "segn"), k + 1);
   GvSet(GvName(posId, "seg"), (double)(long)t);
   TradeSlSegment(TradeSeg(posId, k + 1), t, t, newSL);
  }

void TradeBoxesExtend()
  {
   if(!TradeBoxesOn())
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      TradeBoxUpdate((ulong)PositionGetInteger(POSITION_IDENTIFIER), TimeCurrent(), "\nopen");
     }
  }

void TradeBoxClose(const ulong posId, const double exitPx, const double pnl, const string reason)
  {
   if(!TradeBoxesOn() || GvGet(GvName(posId, "t0"), 0) <= 0)
      return;
   const datetime t = TimeCurrent();
   TradeBoxUpdate(posId, t, StringFormat("\nclosed @ %s  P/L %.2f  (%s)", P(exitPx), pnl, reason));
   const string name = TradeBase(posId) + "_X";
   if(ObjectFind(0, name) < 0 && ObjectCreate(0, name, OBJ_TEXT, 0, t, exitPx))
     {
      ObjectSetString(0, name, OBJPROP_TEXT, StringFormat("%+.2f", pnl));
      ObjectSetInteger(0, name, OBJPROP_COLOR, pnl >= 0 ? clrMediumSeaGreen : clrTomato);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("#%I64u closed @ %s, P/L %.2f (%s)", posId, P(exitPx), pnl, reason));
     }
  }

void OnTimer()
  {
   // keeps the panel alive and retries data loading when no ticks arrive
   if(!g_snapValid)
      RefreshClosedBar();
   if(g_maxSpreadPts <= 0)
      UpdateSpreadLimit();
   static int timerCount = 0;
   if(g_exportPending && ++timerCount % 10 == 0)
      TryExportDiagnostics();
   UpdatePanel();
  }

void OnTick()
  {
   //--- 0. tester slice window (always true in live trading)
   if(!SliceAllowsTick())
      return;

   //--- 1. management first: protection never waits for signals
   ManageOpenPositions();

   //--- 2. new closed bar on the signal timeframe
   const datetime barTime = iTime(_Symbol, SignalTimeframe, 0);
   if(barTime == 0)
      return;
   if(barTime != g_lastBarTime)
     {
      if(RefreshClosedBar())
        {
         g_lastBarTime = barTime;
         UpdateSpreadLimit();
         LogTradeDecision(g_snap);
         if(TradeOnClosedCandle)
           {
            // Only trade a signal whose bar closed within the last signal-TF period. After a
            // session break, weekend or feed gap the first tick would otherwise trade a signal
            // hours old at a gapped price, with the Tracker's SL/TP no longer meaningful.
            const int      tfSec    = PeriodSeconds(SignalTimeframe);
            const datetime sigClose = g_snap.barTime + tfSec;
            if(TimeCurrent() - sigClose <= tfSec)
               ProcessSignal(g_snap);
            else if(g_snap.signal != TWK_SIG_NONE && !IsDuplicateSignal(g_snap.barTime))
              {
               Log("STALE", StringFormat("%s signal on bar %s closed %d s ago (session break / feed gap) - NOT traded",
                                         TwkSignalText(g_snap.signal), TimeToString(g_snap.barTime, TIME_DATE | TIME_MINUTES),
                                         (int)(TimeCurrent() - sigClose)));
               MarkSignalConsumed(g_snap.barTime);
              }
           }
         ManageOpenPositions();                     // purple line just updated
         TradeBoxesExtend();
        }
     }

   //--- 3. optional intrabar signals (forming bar, may repaint)
   if(!TradeOnClosedCandle && TimeCurrent() - g_lastIntrabarEval >= 1)
     {
      g_lastIntrabarEval = TimeCurrent();
      TwkSeries series;
      TwkSnapshot live;
      static datetime lastRejectBar = 0;
      static datetime lastRejectAt  = 0;
      if(g_engine.Evaluate(0, live, series) && live.signal != TWK_SIG_NONE
         && !(live.barTime == lastRejectBar && TimeCurrent() - lastRejectAt < 10))
        {
         ProcessSignal(live);
         lastRejectBar = live.barTime;              // re-check the same forming bar at most every 10 s
         lastRejectAt  = TimeCurrent();
        }
     }
   UpdatePanel();
  }
//+------------------------------------------------------------------+
