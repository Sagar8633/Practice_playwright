//+------------------------------------------------------------------+
//|                                           SimpleSMA18Bot_v13.mq5 |
//|                     Version 1.40                                 |
//|                                                                  |
//|  v1.40 fixes the eight live-trading defects found in the v12     |
//|  line-by-line audit. Two of them were regressions introduced by  |
//|  v12 itself and are marked (REGRESSION).                         |
//|                                                                  |
//|  C1 (REGRESSION) SafeModifyPositionSL clamped an out-of-range    |
//|     stop to bid-1pt instead of rejecting it, producing a         |
//|     guaranteed stop-out right after a sharp adverse move.        |
//|     Now: reject, and optionally close at market, because a       |
//|     breached protection level means "get out", not "stop at 1pt".|
//|  C2 (REGRESSION) A chart timeframe change rebuilt the magic and  |
//|     orphaned the open position. Now detected in OnInit, warned    |
//|     loudly, new entries blocked, with an explicit adopt option.  |
//|  C3 A failed close retried every tick forever. Now a per-ticket  |
//|     backoff latch with escalating delay and a one-shot alert.    |
//|  C4 Freeze level was never read. Now cached and honoured, and a  |
//|     cancel that is refused is retried later instead of dropped.  |
//|  H5 Weekend pending-cancel never fired above M15 because it sat  |
//|     behind the new-bar gate. Now evaluated every tick.           |
//|  H6 UseDailyLossLimit only blocked new entries and was never     |
//|     even reached while a trade was open. Now checked every tick  |
//|     with a selectable action.                                    |
//|  H7 AutoTrading off silently stopped all management. Now warns   |
//|     on the transition, both ways.                                |
//|  H8 Exit signals failed open when CopyBuffer failed. Indicator   |
//|     reads now carry a last-known-good value and a staleness cap. |
//|                                                                  |
//|  Plus the medium items: per-position consecutive-loss counting,  |
//|  cached account guards, int32-safe magic, report only on real    |
//|  removal, volume epsilon, dead field removed.                    |
//|                                                                  |
//|  BEST-APPROACH ADDITIONS (driven by the Apr-Jul 2026 baseline:   |
//|  77.3%% win rate, payoff 0.26, PF 0.90, net -133.93):            |
//|   * R-multiple levels. Break-even, protection, partial and trail |
//|     can key off the trade's OWN initial risk instead of a fixed  |
//|     point count. This is what stops winners being strangled at   |
//|     +$4 while losers run to -$56.                                |
//|   * MaxLossMode defaults to CAP_TIGHTER, so the loss cap is a    |
//|     real broker-side stop for the whole trade instead of a       |
//|     one-candle rule that leaked on 30%% of losers.               |
//|   * Equity drawdown guard alongside the daily loss guard.        |
//|                                                                  |
//|  Hardened rewrite of SimpleSMA18Bot.mq5.                         |
//|                                                                  |
//|  ========== TIMEFRAME INDEPENDENCE (the headline change) ======= |
//|  * The `TimeFrame` input is GONE. The EA always works on the     |
//|    timeframe of the chart it is attached to (_Period). You can   |
//|    no longer attach it to an M15 chart and secretly run D1       |
//|    logic; the chart you look at is always the chart it trades.   |
//|  * The magic number is derived from _Period, so an M15 instance  |
//|    and a D1 instance carry different magics automatically.       |
//|  * EVERY position/order lookup, modify, close and partial close  |
//|    is filtered by that magic and addressed BY TICKET. There is   |
//|    not one PositionSelect(_Symbol) or PositionClose(_Symbol)     |
//|    left in this file. An M15 instance physically cannot read,    |
//|    move or close the D1 instance's trade, your manual trade, or  |
//|    another EA's trade.                                           |
//|  * Optional ATR-scaled levels, so "500 points" stops meaning two |
//|    completely different things on M15 vs D1.                     |
//|                                                                  |
//|  ================= FIXES vs SimpleSMA18Bot.mq5 ================= |
//|  #1  Pending-SL ratchet can no longer creep toward entry: hard   |
//|      floor at max(MinStopPoints, broker stops level).            |
//|  #1b Pending orders now expire (MaxPendingBars) + weekend flat.  |
//|  #2  Magic-scoped, ticket-addressed trade ops everywhere.        |
//|  #3  Dead code implemented and wired up: partial close, failed-  |
//|      breakout exit. Genuinely unused helpers deleted.            |
//|  #4  TradeAllSessions removed (it silently voided the filter).   |
//|  #5  Buy-stop entry is spread-adjusted; max-spread filter added. |
//|  #6  Swing search returns 0.0 on failure -> the trade is SKIPPED |
//|      instead of falling back to low[1] and building a suicide    |
//|      stop during exactly the trends the strategy wants.          |
//|  #7  Buy and sell sides managed independently (no early return). |
//|  #8  All trade ops check ResultRetcode() and retry.              |
//|  #9  Volume average excludes the bar it is testing.              |
//|  #10 Runtime sanity check of point inputs against ATR.           |
//|  #11 SL% filter called once per entry, not twice.                |
//|  #12 Break-even and protection resolved into ONE stop decision,  |
//|      with the winning reason logged.                             |
//|  #13 Swing values cached per bar (was ~400 iLow() calls / tick). |
//|  #14 Consistent boundary comparisons between entry/exit logic.   |
//|  +   Daily loss cap, consecutive-loss cap, free-margin check,    |
//|      lot-step validation, fill-mode detection, slippage control. |
//+------------------------------------------------------------------+
#property copyright "SimpleSMA18Bot"
#property version   "1.30"

#include <Trade/Trade.mqh>

CTrade trade;

//==================================================================
//                             ENUMS
//==================================================================

enum ENUM_PROTECTION_MODE
{
   PROTECTION_NONE       = 0,   // None
   PROTECTION_SWING      = 1,   // Swing structure
   PROTECTION_CHANDELIER = 2,   // Chandelier (ATR)
   PROTECTION_TRAILING   = 3    // Fixed trailing
};

enum ENUM_PROTECTION_START
{
   START_IMMEDIATELY  = 0,      // Immediately
   START_AFTER_POINTS = 1       // After N points of profit
};

//  Ported from SimpleSMA18Bot_v11 so the two versions can be
//  compared on identical rules. v11's copies were symbol-scoped and
//  used the bar the EA happened to notice the fill on; these use the
//  tracked ticket and the real entry bar.
enum ENUM_FOLLOW_MODE
{
   FOLLOW_OFF           = 0,    // Off - no follow-through exit
   FOLLOW_NEXT_VS_ENTRY = 1,    // 1st candle after entry must break the entry candle high/low
   FOLLOW_ANY_STALL     = 2,    // Close on first candle that fails to make a new high/low
   FOLLOW_VS_TRIGGER    = 3     // Next candle must exceed the breakout trigger level
};

enum ENUM_DAILY_LOSS_ACTION
{
   DAILY_BLOCK_NEW        = 0,  // Block new entries only
   DAILY_BLOCK_AND_CANCEL = 1,  // Block new entries + cancel pending orders
   DAILY_FLATTEN          = 2   // Block, cancel, and close open positions
};

enum ENUM_MAXLOSS_MODE
{
   MAXLOSS_OFF            = 0,  // Off - SL = swing only
   MAXLOSS_CAP_TIGHTER    = 1,  // SL = tighter of swing vs entry +/- MaxLossPoints
   MAXLOSS_REPLACE_SWING  = 2,  // SL = entry +/- MaxLossPoints (ignore swing)
   MAXLOSS_EXIT_RULE_ONLY = 3   // Cap loss at MaxLossPoints only inside the follow-through window
};

//==================================================================
//                            INPUTS
//==================================================================

input group           "=== Strategy ==="
input double LotSize                    = 0.01;
input int    FastMAPeriod               = 18;
input int    TrendMAPeriod              = 200;
input bool   UseVolumeFilter            = true;
input int    VolumeMAPeriod             = 20;
input int    SwingStrength              = 2;
input int    SwingSearchBars            = 100;
input int    EntryBufferPoints          = 10;

input group           "=== Pending order handling ==="
input bool   RatchetPendingSL           = true;   // tighten pending SL as structure moves
input int    MinStopPoints              = 150;    // HARD floor on stop distance  (fix #1)
input int    MaxPendingBars             = 5;      // cancel pending after N bars (0 = never)
input bool   CancelPendingBeforeWeekend = true;
input bool   AddSpreadToBuyEntry        = true;   // buy stops trigger on ASK     (fix #5)

input group           "=== Break-even ==="
input bool   EnableBreakEven            = true;
input int    BreakEvenTriggerPoints     = 500;
input int    BreakEvenOffsetPoints      = 10;

input group           "=== Profit protection ==="
input ENUM_PROTECTION_MODE  ProtectionMode      = PROTECTION_SWING;
input ENUM_PROTECTION_START ProtectionStartMode = START_AFTER_POINTS;
input int    ProtectionStartPoints      = 500;
input int    SwingBufferPoints          = 50;
input int    ChandelierLookback         = 22;
input int    ATRPeriod                  = 22;
input double ATRMultiplier              = 3.0;
input int    TrailingStartPoints        = 1000;
input int    TrailingDistancePoints     = 500;
input int    TrailingStepPoints         = 50;

input group           "=== ATR-scaled levels (removes TF dependency) ==="
input bool   UseATRScaledLevels         = false;  // ignore the *Points inputs, use ATR multiples
input double ATRBreakEvenMult           = 1.0;
input double ATRProtectionStartMult     = 1.0;
input double ATRTrailStartMult          = 2.0;
input double ATRTrailDistanceMult       = 1.0;
input double ATRMinStopMult             = 0.5;
input double ATRMaxLossMult             = 1.5;
input double ATRPartialTriggerMult      = 2.0;
input double ATRMaxLossCapMult          = 3.0;

input group           "=== R-multiple levels (best approach: scale to the trade's own risk) ==="
//  With this on, every trigger is a multiple of THIS trade's initial
//  risk (entry - stop) instead of a fixed point count. It is the only
//  basis that is simultaneously timeframe-, symbol- and volatility-
//  independent, and it is the direct fix for the baseline's problem:
//  winners capped near +$4 while losers ran past -$50.
//  Precedence: R-multiple > ATR-scaled > fixed points.
input bool   UseRMultipleLevels         = false;
input double RBreakEvenMult             = 1.0;
input double RProtectionStartMult       = 1.0;
input double RTrailStartMult            = 2.0;
input double RTrailDistanceMult         = 1.0;
input double RPartialTriggerMult        = 1.5;
//  Note: there is deliberately no R-multiple for the minimum stop or
//  the max-loss cap. Both DEFINE the initial risk, so expressing them
//  as a multiple of it would be circular.

input group           "=== Follow-through exit + points max-loss (from v11) ==="
input ENUM_FOLLOW_MODE  FollowMode      = FOLLOW_OFF;
//  Baseline evidence: MAXLOSS_EXIT_RULE_ONLY only caps the loss during
//  the first post-entry candle, and 17 of 56 EA-logic exits blew past
//  the intended -$20 as a result. CAP_TIGHTER puts the cap in the
//  broker-side stop for the whole trade life, where it cannot leak.
input ENUM_MAXLOSS_MODE MaxLossMode     = MAXLOSS_CAP_TIGHTER;
input int               MaxLossPoints   = 1500;

input group           "=== Partial close ==="
input bool   EnablePartialClose         = false;
input int    PartialCloseTriggerPoints  = 1000;
input double PartialClosePercent        = 50.0;

input group           "=== Failed breakout exit ==="
input bool   UseFailedBreakoutExit      = false;
input int    FailedBreakoutBars         = 2;
input int    BreakoutRetestBufferPoints = 20;

input group           "=== Stop safety (C1) ==="
input bool   CloseOnBreachedProtection  = true;   // protection level already passed => close, never a 1pt stop
input int    MinTrailDistancePoints     = 0;      // 0 = use the broker minimum

input group           "=== Timeframe isolation (C2) ==="
input bool   AdoptOrphanTimeframePositions = false;  // manage positions left by another timeframe instance
input bool   BlockEntriesWhileOrphaned     = true;

input group           "=== Risk filters ==="
input bool   UseRiskFilter              = false;  // hard points stop
input int    MaximumLossPoints          = 300;
input bool   UseSLPercentFilter         = true;
input double MaximumSLPercent           = 1.0;
input bool   UseMaxSpreadFilter         = true;
input int    MaxSpreadPoints            = 60;

input group           "=== Account guards ==="
input bool   UseDailyLossLimit          = true;
input double MaxDailyLossPercent        = 3.0;
input ENUM_DAILY_LOSS_ACTION DailyLossAction = DAILY_BLOCK_AND_CANCEL;
input bool   UseEquityDrawdownGuard     = false;
input double MaxEquityDrawdownPercent   = 10.0;
input bool   UseConsecutiveLossLimit    = false;
input int    MaxConsecutiveLosses       = 5;
input double MinFreeMarginPercent       = 20.0;

input group           "=== Session filter ==="
input bool   UseSessionFilter           = false;  // OFF = trade all sessions   (fix #4)
input bool   TradeSydney                = false;
input bool   TradeTokyo                 = false;
input bool   TradeLondon                = true;
input bool   TradeNewYork               = true;

input group           "=== ADX filter ==="
input bool   UseADXFilter               = false;
input int    ADXPeriod                  = 14;
input double MinimumADX                 = 25.0;
input bool   RequireRisingADX           = false;
input int    ADXLookbackBars            = 3;
input bool   RequireConsecutiveADXRise  = false;

input group           "=== Execution ==="
input int    SlippagePoints             = 30;
input int    MaxTradeRetries            = 3;
input int    MaxIndicatorStaleTicks     = 20;     // H8: how long a cached indicator value may be reused
input ulong  MagicNumber                = 12345;
input bool   VerboseLog                 = true;
input bool   ShowIndicatorsOnChart      = true;

input group           "=== Trade study export ==="
input bool   WriteTradeCSV              = true;
input bool   AppendRunStampToCSV        = true;   // keeps every run instead of overwriting

//==================================================================
//                            GLOBALS
//==================================================================

ENUM_TIMEFRAMES WorkTF       = PERIOD_CURRENT;   // == _Period, never an input
ulong           CurrentMagic = 0;

int FastMAHandle  = INVALID_HANDLE;
int TrendMAHandle = INVALID_HANDLE;
int ATRHandle     = INVALID_HANDLE;
int ADXHandle     = INVALID_HANDLE;

datetime LastBarTime = 0;

// --- per-bar swing cache (fix #13) ---
datetime SwingCacheTime  = 0;
double   CachedSwingLow  = 0.0;
double   CachedSwingHigh = 0.0;

// --- pending order age tracking (fix #1b) ---
datetime PendingPlacedBarTime = 0;

// --- tracked position state (fix #15) ---
ulong    TrackedTicket       = 0;
datetime TrackedEntryBarTime = 0;
double   TrackedEntryPrice   = 0.0;
bool     TrackedIsBuy        = false;
bool     TrackedPartialDone  = false;

// --- follow-through window state (ported from v11) ---
double   FT_EntryHigh    = 0.0;
double   FT_EntryLow     = 0.0;
bool     FT_EntryCaptured = false;
bool     FT_WindowOpen    = false;
datetime FT_LastBar       = 0;

// --- study counters, incremented by the EA itself ---
int CntMA18Exit   = 0;   // closed by the fast-MA cross exit
int CntNoFollow   = 0;   // closed by the no-follow-through rule
int CntMaxLoss    = 0;   // closed by the points max-loss window cap
int CntPartial    = 0;   // partial closes performed
int CntFailedBO   = 0;   // closed by the failed-breakout exit
int CntEmergency  = 0;   // closed by the emergency risk filter

// --- initial risk of the tracked trade, for R-multiple levels ---
double   TrackedInitialRisk = 0.0;   // price distance entry -> original SL

// --- C3: per-ticket close-failure backoff ---
ulong    CloseFailTicket   = 0;
int      CloseFailCount    = 0;
datetime CloseFailNextTry  = 0;
bool     CloseFailAlerted  = false;

// --- C4: a cancel that the broker refused, to retry on later ticks ---
ulong    PendingCancelTicket = 0;
string   PendingCancelReason = "";

// --- C2: orphaned position left behind by another timeframe ---
bool     OrphanDetected = false;
bool     OrphanWarned   = false;
string   OrphanNote     = "";

// --- H7: AutoTrading transition tracking ---
bool     TradingWasAllowed = true;
bool     TradingStateKnown = false;

// --- H8: last-known-good indicator values + staleness ---
double LastGoodFastMA[3];
double LastGoodTrendMA[3];
double LastGoodATR = 0.0;
int    StaleFastMA  = 0;
int    StaleTrendMA = 0;
int    StaleATR     = 0;

// --- guard caches (medium #10) ---
datetime GuardCacheBar     = 0;
double   CachedTodayPL     = 0.0;
int      CachedConsecLoss  = 0;
double   EquityPeak        = 0.0;
bool     GuardCacheDirty   = true;
bool     DailyLimitLatched = false;
datetime DailyLimitDay     = 0;

// --- cached symbol properties ---
double SymVolMin     = 0.0;
double SymVolMax     = 0.0;
double SymVolStep    = 0.0;
int    SymVolDigits  = 2;
long   SymStopsLevel  = 0;
long   SymFreezeLevel = 0;               // C4
bool   AccountIsHedging = false;

// --- one-shot runtime validation ---
bool SanityChecked = false;

//==================================================================
//                            LOGGING
//==================================================================

string Tag()
{
   return "[" + EnumToString(WorkTF) + "/" + IntegerToString((long)CurrentMagic) + "] ";
}

void Log(const string msg)
{
   if(VerboseLog)
      Print(Tag(), msg);
}

void LogAlways(const string msg)
{
   Print(Tag(), msg);
}

//==================================================================
//                     TIMEFRAME-DERIVED MAGIC
//==================================================================
//  Each chart timeframe gets its own magic number, so instances on
//  different timeframes are fully independent bots.
//
//  v12 used MagicNumber*100000 + minutes, which overflows int32 once
//  MagicNumber exceeds 21474 - and some bridges silently truncate the
//  magic to 32 bits. v13 uses a compact 2-digit timeframe index so
//  the result stays small: M15 -> MagicNumber*100 + 5.
//------------------------------------------------------------------
int TimeframeIndex(const ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return 1;
      case PERIOD_M2:  return 2;
      case PERIOD_M3:  return 3;
      case PERIOD_M4:  return 4;
      case PERIOD_M5:  return 5;
      case PERIOD_M6:  return 6;
      case PERIOD_M10: return 7;
      case PERIOD_M12: return 8;
      case PERIOD_M15: return 9;
      case PERIOD_M20: return 10;
      case PERIOD_M30: return 11;
      case PERIOD_H1:  return 12;
      case PERIOD_H2:  return 13;
      case PERIOD_H3:  return 14;
      case PERIOD_H4:  return 15;
      case PERIOD_H6:  return 16;
      case PERIOD_H8:  return 17;
      case PERIOD_H12: return 18;
      case PERIOD_D1:  return 19;
      case PERIOD_W1:  return 20;
      case PERIOD_MN1: return 21;
      default:         return 0;
   }
}

ulong BuildMagicFor(const ENUM_TIMEFRAMES tf)
{
   return (MagicNumber * 100) + (ulong)TimeframeIndex(tf);
}

ulong BuildMagic()
{
   return BuildMagicFor(WorkTF);
}

// True when this magic belongs to this EA family on ANY timeframe.
bool IsFamilyMagic(const ulong m)
{
   return (m / 100 == MagicNumber && (m % 100) <= 21);
}

//==================================================================
//                        INIT / DEINIT
//==================================================================

int OnInit()
{
   //--- lock the working timeframe to the chart. No input, no mixing.
   WorkTF       = (ENUM_TIMEFRAMES)Period();
   CurrentMagic = BuildMagic();

   //--- cache symbol properties once
   SymVolMin      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   SymVolMax      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   SymVolStep     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   SymStopsLevel  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   SymFreezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);   // C4

   AccountIsHedging =
      ((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)
       == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);

   if(SymVolStep      >= 1.0)  SymVolDigits = 0;
   else if(SymVolStep >= 0.1)  SymVolDigits = 1;
   else if(SymVolStep >= 0.01) SymVolDigits = 2;
   else                        SymVolDigits = 3;

   //--- lot size validation
   if(SymVolStep <= 0.0 || SymVolMin <= 0.0)
   {
      LogAlways("INIT FAILED: broker returned invalid volume limits.");
      return(INIT_FAILED);
   }

   if(LotSize < SymVolMin - 1e-9 || LotSize > SymVolMax + 1e-9)
   {
      LogAlways("INIT FAILED: LotSize " + DoubleToString(LotSize, 3) +
                " outside broker range " + DoubleToString(SymVolMin, 3) +
                " .. " + DoubleToString(SymVolMax, 3));
      return(INIT_FAILED);
   }

   double steps = LotSize / SymVolStep;
   if(MathAbs(steps - MathRound(steps)) > 0.001)
   {
      LogAlways("INIT FAILED: LotSize " + DoubleToString(LotSize, 3) +
                " is not a multiple of volume step " + DoubleToString(SymVolStep, 3));
      return(INIT_FAILED);
   }

   //--- period validation
   if(FastMAPeriod <= 0 || TrendMAPeriod <= 0 || ATRPeriod <= 0 ||
      ADXPeriod <= 0 || SwingStrength <= 0 || SwingSearchBars <= SwingStrength * 2)
   {
      LogAlways("INIT FAILED: invalid period inputs.");
      return(INIT_FAILED);
   }

   if(UseVolumeFilter && VolumeMAPeriod <= 0)
   {
      LogAlways("INIT FAILED: VolumeMAPeriod must be > 0 when the volume filter is on.");
      return(INIT_FAILED);
   }

   if(FastMAPeriod >= TrendMAPeriod)
      LogAlways("WARNING: FastMAPeriod >= TrendMAPeriod. The trend filter will rarely agree.");

   //--- trade object
   trade.SetExpertMagicNumber(CurrentMagic);
   trade.SetDeviationInPoints((ulong)MathMax(1, SlippagePoints));
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   //--- indicator handles (all on WorkTF == chart period)
   FastMAHandle  = iMA(_Symbol, WorkTF, FastMAPeriod,  0, MODE_SMA, PRICE_CLOSE);
   TrendMAHandle = iMA(_Symbol, WorkTF, TrendMAPeriod, 0, MODE_SMA, PRICE_CLOSE);
   ATRHandle     = iATR(_Symbol, WorkTF, ATRPeriod);
   ADXHandle     = iADX(_Symbol, WorkTF, ADXPeriod);

   if(FastMAHandle  == INVALID_HANDLE || TrendMAHandle == INVALID_HANDLE ||
      ATRHandle     == INVALID_HANDLE || ADXHandle     == INVALID_HANDLE)
   {
      LogAlways("INIT FAILED: could not create one or more indicator handles.");
      ReleaseHandles();                      // no handle leak on the failure path
      return(INIT_FAILED);
   }

   //--- chart decoration (skipped during optimisation)
   if(ShowIndicatorsOnChart && !MQLInfoInteger(MQL_OPTIMIZATION))
   {
      ChartIndicatorAdd(0, 0, FastMAHandle);
      ChartIndicatorAdd(0, 0, TrendMAHandle);
   }

   //--- reset per-run state (OnInit also runs after a parameter change)
   ArrayInitialize(LastGoodFastMA,  0.0);
   ArrayInitialize(LastGoodTrendMA, 0.0);
   LastGoodATR       = 0.0;
   StaleFastMA       = 0;
   StaleTrendMA      = 0;
   StaleATR          = 0;
   CloseFailTicket   = 0;
   CloseFailCount    = 0;
   CloseFailNextTry  = 0;
   CloseFailAlerted  = false;
   OrphanWarned      = false;
   PendingCancelTicket = 0;
   TradingStateKnown = false;
   GuardCacheBar     = 0;
   DailyLimitLatched = false;
   EquityPeak        = AccountInfoDouble(ACCOUNT_EQUITY);

   //--- C2: look for positions/orders this EA family left on another timeframe
   ScanForOrphans();

   LogAlways("SimpleSMA18Bot v1.40 initialised on " + _Symbol +
             " " + EnumToString(WorkTF) +
             " | magic " + IntegerToString((long)CurrentMagic) +
             " | hedging=" + (AccountIsHedging ? "yes" : "no") +
             " | stopsLevel=" + IntegerToString(SymStopsLevel) +
             "pts freeze=" + IntegerToString(SymFreezeLevel) + "pts");

   return(INIT_SUCCEEDED);
}

//==================================================================
//        C2: ORPHANS LEFT BEHIND BY A TIMEFRAME CHANGE
//==================================================================
//  Changing the chart timeframe reruns OnInit with a new magic, so a
//  position opened by the previous timeframe becomes invisible to
//  every FindMy* call and runs with no management at all. v12 had no
//  guard for this. Detect it, say so loudly, and keep saying so.
//------------------------------------------------------------------
void ScanForOrphans()
{
   OrphanDetected = false;
   OrphanNote     = "";

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      ulong m = (ulong)PositionGetInteger(POSITION_MAGIC);

      if(m == CurrentMagic)  continue;      // ours
      if(!IsFamilyMagic(m))  continue;      // someone else's entirely

      OrphanDetected = true;
      OrphanNote     = "position #" + IntegerToString((long)ticket) +
                       " magic " + IntegerToString((long)m);
      break;
   }

   if(!OrphanDetected)
   {
      for(int i = OrdersTotal() - 1; i >= 0; i--)
      {
         ulong ticket = OrderGetTicket(i);

         if(ticket == 0) continue;
         if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;

         ulong m = (ulong)OrderGetInteger(ORDER_MAGIC);

         if(m == CurrentMagic) continue;
         if(!IsFamilyMagic(m)) continue;

         OrphanDetected = true;
         OrphanNote     = "pending #" + IntegerToString((long)ticket) +
                          " magic " + IntegerToString((long)m);
         break;
      }
   }

   if(!OrphanDetected)
   {
      if(OrphanWarned)
      {
         OrphanWarned = false;
         LogAlways("Orphaned trade from another timeframe is gone - entries re-enabled.");
      }
      return;
   }

   if(OrphanWarned)
      return;                        // already said this; do not spam every bar

   OrphanWarned = true;

   if(AdoptOrphanTimeframePositions)
   {
      LogAlways("ORPHAN ADOPTED: " + OrphanNote +
                " - this instance will now manage it (AdoptOrphanTimeframePositions=true).");
   }
   else
   {
      LogAlways("*** ORPHANED TRADE FROM ANOTHER TIMEFRAME: " + OrphanNote + " ***");
      LogAlways("*** It is NOT being managed by this instance: no break-even, no trail, no exit. ***");
      LogAlways("*** Reattach on its original timeframe, close it by hand, or set ***");
      LogAlways("*** AdoptOrphanTimeframePositions=true. New entries are blocked meanwhile. ***");
   }
}

void ReleaseHandles()
{
   if(FastMAHandle  != INVALID_HANDLE) { IndicatorRelease(FastMAHandle);  FastMAHandle  = INVALID_HANDLE; }
   if(TrendMAHandle != INVALID_HANDLE) { IndicatorRelease(TrendMAHandle); TrendMAHandle = INVALID_HANDLE; }
   if(ATRHandle     != INVALID_HANDLE) { IndicatorRelease(ATRHandle);     ATRHandle     = INVALID_HANDLE; }
   if(ADXHandle     != INVALID_HANDLE) { IndicatorRelease(ADXHandle);     ADXHandle     = INVALID_HANDLE; }
}

void OnDeinit(const int reason)
{
   //  v12 exported on EVERY deinit reason, so a parameter tweak or a
   //  chart timeframe change silently wrote another timestamped CSV.
   //  Only report when the EA is actually going away, or the tester
   //  run has ended.
   bool realEnd = (reason == REASON_REMOVE     ||
                   reason == REASON_CHARTCLOSE ||
                   reason == REASON_CLOSE      ||
                   reason == REASON_PROGRAM    ||
                   MQLInfoInteger(MQL_TESTER));

   if(realEnd)
      ReportAndExport();              // study summary + CSV

   if(ShowIndicatorsOnChart && !MQLInfoInteger(MQL_OPTIMIZATION))
   {
      // The old code deleted by a hardcoded name and removed only the
      // first match. Enumerate instead so BOTH MAs actually go.
      for(int i = ChartIndicatorsTotal(0, 0) - 1; i >= 0; i--)
      {
         string name = ChartIndicatorName(0, 0, i);

         if(StringFind(name, "MA(") == 0 || StringFind(name, "Moving Average") == 0)
            ChartIndicatorDelete(0, 0, name);
      }
   }

   ReleaseHandles();
   Comment("");
}

//==================================================================
//                       SYMBOL / MATH HELPERS
//==================================================================

double CurrentBid() { return SymbolInfoDouble(_Symbol, SYMBOL_BID); }
double CurrentAsk() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK); }

long CurrentSpreadPoints()
{
   double ask = CurrentAsk();
   double bid = CurrentBid();

   if(ask <= 0.0 || bid <= 0.0)
      return (long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);

   return (long)MathRound((ask - bid) / _Point);
}

// Smallest stop distance the broker will accept, in price terms.
double BrokerMinDistance()
{
   long lvl = SymStopsLevel;

   if(lvl <= 0)
      lvl = 1;

   return (double)lvl * _Point;
}

double NormalizeVolume(double vol)
{
   if(SymVolStep <= 0.0)
      return 0.0;

   vol = MathFloor(vol / SymVolStep + 1e-8) * SymVolStep;
   vol = NormalizeDouble(vol, SymVolDigits);

   if(vol < SymVolMin - 1e-9)
      return 0.0;

   if(vol > SymVolMax)
      vol = SymVolMax;

   return vol;
}

//==================================================================
//                          BAR HELPERS
//==================================================================

bool IsNewBar()
{
   datetime t = iTime(_Symbol, WorkTF, 0);

   if(t == 0)
      return false;

   if(t != LastBarTime)
   {
      LastBarTime = t;
      return true;
   }

   return false;
}

bool EnoughHistory()
{
   int need = TrendMAPeriod + SwingSearchBars + SwingStrength + 5;

   return (Bars(_Symbol, WorkTF) >= need);
}

//==================================================================
//                      INDICATOR ACCESSORS
//==================================================================

//  H8: v12 returned 0.0 on a failed CopyBuffer, and the exit signals
//  read that as "no cross", so a transient indicator failure - routine
//  right after a reconnect - silently suppressed the exit. Now a read
//  failure reuses the last known good value for a bounded number of
//  reads and shouts once it runs out.
double GetMAValue(const int handle, const int shift)
{
   double buf[];

   bool isFast = (handle == FastMAHandle);
   int  idx    = (shift >= 0 && shift <= 2) ? shift : 0;

   if(CopyBuffer(handle, 0, shift, 1, buf) > 0 && buf[0] > 0.0)
   {
      if(isFast) { LastGoodFastMA[idx]  = buf[0]; StaleFastMA  = 0; }
      else       { LastGoodTrendMA[idx] = buf[0]; StaleTrendMA = 0; }

      return buf[0];
   }

   if(isFast) StaleFastMA++; else StaleTrendMA++;

   int    stale  = isFast ? StaleFastMA : StaleTrendMA;
   double cached = isFast ? LastGoodFastMA[idx] : LastGoodTrendMA[idx];

   if(cached > 0.0 && stale <= MaxIndicatorStaleTicks)
      return cached;

   if(stale == MaxIndicatorStaleTicks + 1)
      LogAlways("*** MA DATA UNAVAILABLE for " + IntegerToString(stale) +
                " reads - exits cannot be evaluated. Check the connection. ***");

   return 0.0;
}

double GetATRValue(const int shift)
{
   double buf[];

   if(CopyBuffer(ATRHandle, 0, shift, 1, buf) > 0 && buf[0] > 0.0)
   {
      LastGoodATR = buf[0];
      StaleATR    = 0;
      return buf[0];
   }

   StaleATR++;

   if(LastGoodATR > 0.0 && StaleATR <= MaxIndicatorStaleTicks)
      return LastGoodATR;

   return 0.0;
}

double GetADXValue(const int shift)
{
   double buf[];

   if(CopyBuffer(ADXHandle, 0, shift, 1, buf) <= 0)
      return 0.0;

   return buf[0];
}

// fix #9: average bars 2..period+1 so the bar being tested is not
// part of the average it is compared against.
double GetAverageVolume(const int period)
{
   if(period <= 0)
      return 0.0;

   long total = 0;

   for(int i = 2; i <= period + 1; i++)
      total += iVolume(_Symbol, WorkTF, i);

   return (double)total / (double)period;
}

//==================================================================
//                   ATR-SCALED LEVEL RESOLUTION
//==================================================================
//  Every distance below is returned in PRICE terms. When
//  UseATRScaledLevels is on, the fixed *Points inputs are ignored
//  and the level becomes a multiple of ATR, which is what actually
//  makes the settings timeframe-independent.
//------------------------------------------------------------------

//  Precedence: R-multiple > ATR-scaled > fixed points.
//  rMult <= 0 means "this level has no meaningful R basis".
double ScaledDistance(const double rMult, const double atrMult, const int fallbackPoints)
{
   if(UseRMultipleLevels && rMult > 0.0 && TrackedInitialRisk > 0.0)
      return TrackedInitialRisk * rMult;

   if(UseATRScaledLevels)
   {
      double atr = GetATRValue(1);

      if(atr > 0.0)
         return atr * atrMult;

      if(LastGoodATR > 0.0)            // medium #11: do not silently jump to points
         return LastGoodATR * atrMult;
   }

   return (double)fallbackPoints * _Point;
}

double BreakEvenTriggerDistance()  { return ScaledDistance(RBreakEvenMult,       ATRBreakEvenMult,       BreakEvenTriggerPoints);    }
double ProtectionStartDistance()   { return ScaledDistance(RProtectionStartMult, ATRProtectionStartMult, ProtectionStartPoints);     }
double TrailingStartDistance()     { return ScaledDistance(RTrailStartMult,      ATRTrailStartMult,      TrailingStartPoints);       }
double TrailingDistance()          { return ScaledDistance(RTrailDistanceMult,   ATRTrailDistanceMult,   TrailingDistancePoints);    }
double PartialTriggerDistance()    { return ScaledDistance(RPartialTriggerMult,  ATRPartialTriggerMult,  PartialCloseTriggerPoints); }

// These two DEFINE the initial risk, so they never use an R basis.
double MaximumLossDistance()       { return ScaledDistance(0.0, ATRMaxLossMult,    MaximumLossPoints); }
double MaxLossCapDistance()        { return ScaledDistance(0.0, ATRMaxLossCapMult, MaxLossPoints);     }

// fix #1: the hard floor a stop may never come inside of.
double MinimumStopDistance()
{
   double strategyMin = ScaledDistance(0.0, ATRMinStopMult, MinStopPoints);

   return MathMax(strategyMin, BrokerMinDistance());
}

//==================================================================
//                       SWING DETECTION
//==================================================================
//  fix #6: returns 0.0 when no confirmed swing exists. The caller
//  must skip the trade. The old code fell back to low[1]/high[1],
//  which produced a sub-$1 stop precisely during strong trends.
//  fix #13: results cached per bar.
//------------------------------------------------------------------

double FindSwingLow()
{
   int start = SwingStrength + 1;
   int end   = SwingSearchBars;

   for(int bar = start; bar <= end; bar++)
   {
      double low   = iLow(_Symbol, WorkTF, bar);
      bool   swing = true;

      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iLow(_Symbol, WorkTF, bar + i) <= low)
         {
            swing = false;
            break;
         }
      }

      if(!swing)
         continue;

      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iLow(_Symbol, WorkTF, bar - i) <= low)
         {
            swing = false;
            break;
         }
      }

      if(swing)
         return low;
   }

   return 0.0;                       // no fallback. On purpose.
}

double FindSwingHigh()
{
   int start = SwingStrength + 1;
   int end   = SwingSearchBars;

   for(int bar = start; bar <= end; bar++)
   {
      double high  = iHigh(_Symbol, WorkTF, bar);
      bool   swing = true;

      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iHigh(_Symbol, WorkTF, bar + i) >= high)
         {
            swing = false;
            break;
         }
      }

      if(!swing)
         continue;

      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iHigh(_Symbol, WorkTF, bar - i) >= high)
         {
            swing = false;
            break;
         }
      }

      if(swing)
         return high;
   }

   return 0.0;                       // no fallback. On purpose.
}

void RefreshSwingCache()
{
   datetime t = iTime(_Symbol, WorkTF, 0);

   if(t == 0 || t == SwingCacheTime)
      return;

   SwingCacheTime  = t;
   CachedSwingLow  = FindSwingLow();
   CachedSwingHigh = FindSwingHigh();
}

double GetSwingLow()  { RefreshSwingCache(); return CachedSwingLow;  }
double GetSwingHigh() { RefreshSwingCache(); return CachedSwingHigh; }

//==================================================================
//              MAGIC-SCOPED POSITION / ORDER LOOKUP
//==================================================================
//  fix #2. Nothing in this EA ever touches a position or order that
//  does not carry CurrentMagic on this exact symbol.
//------------------------------------------------------------------

//  C2: when the user opts in, this instance also claims positions
//  left behind by the same EA on another timeframe.
bool MagicMatches(const ulong m)
{
   if(m == CurrentMagic)
      return true;

   return (AdoptOrphanTimeframePositions && IsFamilyMagic(m));
}

ulong FindMyPosition(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if(!MagicMatches((ulong)PositionGetInteger(POSITION_MAGIC)))
         continue;

      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
         continue;

      return ticket;
   }

   return 0;
}

ulong FindMyAnyPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if(!MagicMatches((ulong)PositionGetInteger(POSITION_MAGIC)))
         continue;

      return ticket;
   }

   return 0;
}

ulong FindMyOrder(const ENUM_ORDER_TYPE type)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);

      if(ticket == 0)
         continue;

      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;

      if(!MagicMatches((ulong)OrderGetInteger(ORDER_MAGIC)))
         continue;

      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) != type)
         continue;

      return ticket;
   }

   return 0;
}

//==================================================================
//                     SAFE TRADE OPERATIONS
//==================================================================
//  fix #8. Every send checks the retcode and retries transient
//  failures. Nothing is fire-and-forget any more.
//------------------------------------------------------------------

//==================================================================
//                  C4: FREEZE LEVEL AWARENESS
//==================================================================
//  Inside SYMBOL_TRADE_FREEZE_LEVEL a broker refuses to modify or
//  delete a pending order. v12 never read this value, treated the
//  refusal as permanent, and gave up - so an order you tried to
//  cancel got filled anyway. That is worst exactly when price is
//  racing at the trigger.
//------------------------------------------------------------------
double FreezeDistance()
{
   if(SymFreezeLevel <= 0)
      return 0.0;

   return (double)SymFreezeLevel * _Point;
}

bool PendingIsFrozen(const double orderPrice, const bool isBuySide)
{
   double fz = FreezeDistance();

   if(fz <= 0.0)
      return false;

   double ref = isBuySide ? CurrentAsk() : CurrentBid();

   return (MathAbs(orderPrice - ref) <= fz);
}

//==================================================================
//             C3: CLOSE-FAILURE BACKOFF (per ticket)
//==================================================================
//  v12 gave up after 3 attempts, but ManagePosition called it again
//  on the very next tick - dozens of sends per second on a hard
//  failure. Now each ticket gets an escalating backoff and one alert.
//------------------------------------------------------------------
void ResetCloseFailure(const ulong ticket)
{
   if(CloseFailTicket != ticket)
      return;

   CloseFailTicket  = 0;
   CloseFailCount   = 0;
   CloseFailNextTry = 0;
   CloseFailAlerted = false;
}

void RegisterCloseFailure(const ulong ticket, const uint rc, const string reason)
{
   if(CloseFailTicket != ticket)
   {
      CloseFailTicket  = ticket;
      CloseFailCount   = 0;
      CloseFailAlerted = false;
   }

   CloseFailCount++;

   int delay = 1;
   if(CloseFailCount >= 2) delay = 5;
   if(CloseFailCount >= 4) delay = 30;
   if(CloseFailCount >= 6) delay = 60;

   CloseFailNextTry = TimeCurrent() + delay;

   if(!CloseFailAlerted && CloseFailCount >= 3)
   {
      CloseFailAlerted = true;

      LogAlways("*** CANNOT CLOSE #" + IntegerToString((long)ticket) +
                " after " + IntegerToString(CloseFailCount) +
                " attempts (rc=" + IntegerToString((int)rc) +
                "). Backing off " + IntegerToString(delay) +
                "s. THE POSITION IS STILL OPEN: " + reason + " ***");

      if(!MQLInfoInteger(MQL_TESTER))
         Alert("SMA18 v13 ", _Symbol, ": cannot close #", ticket, " rc=", rc);
   }
}

bool IsRetryableRetcode(const uint rc)
{
   return (rc == TRADE_RETCODE_REQUOTE          ||
           rc == TRADE_RETCODE_PRICE_CHANGED    ||
           rc == TRADE_RETCODE_PRICE_OFF        ||
           rc == TRADE_RETCODE_TIMEOUT          ||
           rc == TRADE_RETCODE_CONNECTION       ||
           rc == TRADE_RETCODE_TOO_MANY_REQUESTS);
}

void PauseBetweenRetries()
{
   if(!MQLInfoInteger(MQL_TESTER))
      Sleep(200);
}

bool SafeClosePosition(const ulong ticket, const string reason)
{
   if(ticket == 0)
      return false;

   //--- C3: honour the backoff for a ticket that keeps refusing
   if(ticket == CloseFailTicket && CloseFailNextTry > 0 && TimeCurrent() < CloseFailNextTry)
      return false;

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(!PositionSelectByTicket(ticket))
         return false;                          // already gone

      if(trade.PositionClose(ticket, (ulong)MathMax(1, SlippagePoints)))
      {
         LogAlways("CLOSED #" + IntegerToString((long)ticket) + " : " + reason);
         ResetCloseFailure(ticket);
         return true;
      }

      uint rc = trade.ResultRetcode();

      Log("Close #" + IntegerToString((long)ticket) +
          " attempt " + IntegerToString(attempt) +
          " failed rc=" + IntegerToString((int)rc) +
          " (" + trade.ResultRetcodeDescription() + ") : " + reason);

      if(!IsRetryableRetcode(rc))
      {
         RegisterCloseFailure(ticket, rc, reason);
         return false;
      }

      PauseBetweenRetries();
   }

   RegisterCloseFailure(ticket, trade.ResultRetcode(), reason);

   return false;
}

bool SafeClosePartial(const ulong ticket, const double volume, const string reason)
{
   if(ticket == 0 || volume <= 0.0)
      return false;

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(!PositionSelectByTicket(ticket))
         return false;

      if(trade.PositionClosePartial(ticket, volume, (ulong)MathMax(1, SlippagePoints)))
      {
         LogAlways("PARTIAL CLOSE #" + IntegerToString((long)ticket) +
                   " vol=" + DoubleToString(volume, SymVolDigits) + " : " + reason);
         return true;
      }

      uint rc = trade.ResultRetcode();

      LogAlways("Partial close #" + IntegerToString((long)ticket) +
                " attempt " + IntegerToString(attempt) +
                " FAILED rc=" + IntegerToString((int)rc) +
                " (" + trade.ResultRetcodeDescription() + ")");

      if(!IsRetryableRetcode(rc))
         return false;

      PauseBetweenRetries();
   }

   return false;
}

//  Tighten-only stop modification, clamped to the broker's minimum
//  distance and never placed on the wrong side of price.
bool SafeModifyPositionSL(const ulong ticket, double newSL, const string reason)
{
   if(ticket == 0 || newSL <= 0.0)
      return false;

   if(!PositionSelectByTicket(ticket))
      return false;

   bool   isBuy = ((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   double curSL = PositionGetDouble(POSITION_SL);
   double tp    = PositionGetDouble(POSITION_TP);

   double bid = CurrentBid();
   double ask = CurrentAsk();

   newSL = NormalizeDouble(newSL, _Digits);

   //--- C1 (REGRESSION FIX).
   //  A requested stop on the wrong side of price means the protection
   //  level has ALREADY been breached - typically after a move of more
   //  than ATRMultiplier x ATR against us, when ChandelierStop returns
   //  a level above the bid. v12 clamped that to bid - 1 point, which
   //  guarantees a stop-out on the very next tick at the worst moment.
   //  The correct response is to get out, or to do nothing - never to
   //  invent a one-point stop.
   if((isBuy && newSL >= bid) || (!isBuy && newSL <= ask))
   {
      if(CloseOnBreachedProtection)
      {
         LogAlways("Protection level " + DoubleToString(newSL, _Digits) +
                   " is already breached by price - closing rather than setting a 1pt stop [" +
                   reason + "]");

         SafeClosePosition(ticket, "protection breached (" + reason + ")");
      }
      else
      {
         Log("Protection level " + DoubleToString(newSL, _Digits) +
             " already breached - stop NOT moved [" + reason + "]");
      }

      return false;
   }

   //--- clamp only out to the legal floor, and only from the safe side
   double floorD = MathMax(BrokerMinDistance(),
                           (double)MinTrailDistancePoints * _Point);

   if(isBuy)
   {
      if(bid - newSL < floorD)
         newSL = NormalizeDouble(bid - floorD, _Digits);
   }
   else
   {
      if(newSL - ask < floorD)
         newSL = NormalizeDouble(ask + floorD, _Digits);
   }

   //--- if the clamp pushed it through price, abandon the move
   if(isBuy  && newSL >= bid) return false;
   if(!isBuy && newSL <= ask) return false;

   //--- tighten only
   if(curSL > 0.0)
   {
      if(isBuy  && newSL <= curSL + _Point * 0.5) return false;
      if(!isBuy && newSL >= curSL - _Point * 0.5) return false;
   }

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(trade.PositionModify(ticket, newSL, tp))
      {
         Log("SL #" + IntegerToString((long)ticket) +
             " -> " + DoubleToString(newSL, _Digits) + "  [" + reason + "]");
         return true;
      }

      uint rc = trade.ResultRetcode();

      if(!IsRetryableRetcode(rc))
      {
         Log("SL modify #" + IntegerToString((long)ticket) +
             " rejected rc=" + IntegerToString((int)rc) +
             " (" + trade.ResultRetcodeDescription() + ")");
         return false;
      }

      PauseBetweenRetries();
   }

   return false;
}

bool SafeDeleteOrder(const ulong ticket, const string reason)
{
   if(ticket == 0)
      return false;

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(trade.OrderDelete(ticket))
      {
         Log("Pending #" + IntegerToString((long)ticket) + " cancelled : " + reason);
         PendingPlacedBarTime = 0;
         PendingCancelTicket  = 0;
         return true;
      }

      uint rc = trade.ResultRetcode();

      if(!IsRetryableRetcode(rc))
      {
         //--- C4: usually the freeze level. Do NOT give up - remember
         //  it and retry every tick, or the order we wanted cancelled
         //  simply fills.
         PendingCancelTicket = ticket;
         PendingCancelReason = reason;

         LogAlways("Cancel #" + IntegerToString((long)ticket) +
                   " refused rc=" + IntegerToString((int)rc) +
                   " (" + trade.ResultRetcodeDescription() +
                   ") - will retry every tick until it clears");
         return false;
      }

      PauseBetweenRetries();
   }

   return false;
}

//==================================================================
//                       POSITION READ HELPERS
//==================================================================

double PositionProfitDistance(const ulong ticket, const bool isBuy)
{
   if(!PositionSelectByTicket(ticket))
      return 0.0;

   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double cur  = isBuy ? CurrentBid() : CurrentAsk();

   return isBuy ? (cur - open) : (open - cur);
}

//==================================================================
//                            FILTERS
//==================================================================

bool PassSpreadFilter()
{
   if(!UseMaxSpreadFilter)
      return true;

   long spread = CurrentSpreadPoints();

   if(spread > MaxSpreadPoints)
   {
      Log("Blocked: spread " + IntegerToString(spread) +
          " > MaxSpreadPoints " + IntegerToString(MaxSpreadPoints));
      return false;
   }

   return true;
}

// fix #4: one flag. UseSessionFilter off means every session.
bool IsTradingSession()
{
   if(!UseSessionFilter)
      return true;

   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);

   int hour = tm.hour;

   bool sydney  = (hour >= 22 || hour <  7);
   bool tokyo   = (hour >=  0 && hour <  9);
   bool london  = (hour >=  8 && hour < 17);
   bool newyork = (hour >= 13 && hour < 22);

   if(TradeSydney  && sydney)  return true;
   if(TradeTokyo   && tokyo)   return true;
   if(TradeLondon  && london)  return true;
   if(TradeNewYork && newyork) return true;

   return false;
}

bool IsADXRising()
{
   return (GetADXValue(1) > GetADXValue(ADXLookbackBars + 1));
}

bool IsADXConsecutivelyRising()
{
   for(int i = 1; i <= ADXLookbackBars; i++)
   {
      if(GetADXValue(i) <= GetADXValue(i + 1))
         return false;
   }

   return true;
}

bool PassADXFilter()
{
   if(!UseADXFilter)
      return true;

   if(GetADXValue(1) < MinimumADX)
      return false;

   if(RequireConsecutiveADXRise)
      return IsADXConsecutivelyRising();

   if(RequireRisingADX)
      return IsADXRising();

   return true;
}

// fix #11: this is called exactly once per entry attempt.
bool PassSLPercentFilter(const ENUM_ORDER_TYPE orderType,
                         const double entryPrice,
                         const double stopLossPrice)
{
   if(!UseSLPercentFilter || MaximumSLPercent <= 0.0)
      return true;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double maxLoss = balance * MaximumSLPercent / 100.0;

   double estimated = 0.0;

   if(!OrderCalcProfit(orderType, _Symbol, LotSize, entryPrice, stopLossPrice, estimated))
   {
      LogAlways("SL% filter: OrderCalcProfit failed, err=" + IntegerToString(GetLastError()));
      return false;
   }

   estimated = MathAbs(estimated);

   if(estimated > maxLoss)
   {
      Log("Blocked: SL risk " + DoubleToString(estimated, 2) +
          " > allowed " + DoubleToString(maxLoss, 2));
      return false;
   }

   return true;
}

bool PassMarginCheck(const ENUM_ORDER_TYPE orderType, const double price)
{
   double margin = 0.0;

   if(!OrderCalcMargin(orderType, _Symbol, LotSize, price, margin))
      return true;                       // cannot compute, do not block

   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);

   if(margin > freeMargin)
   {
      LogAlways("Blocked: required margin " + DoubleToString(margin, 2) +
                " > free margin " + DoubleToString(freeMargin, 2));
      return false;
   }

   if(equity > 0.0 && MinFreeMarginPercent > 0.0)
   {
      double remainingPct = (freeMargin - margin) / equity * 100.0;

      if(remainingPct < MinFreeMarginPercent)
      {
         LogAlways("Blocked: free margin would fall to " +
                   DoubleToString(remainingPct, 1) + "% (min " +
                   DoubleToString(MinFreeMarginPercent, 1) + "%)");
         return false;
      }
   }

   return true;
}

//==================================================================
//                       ACCOUNT-LEVEL GUARDS
//==================================================================

double TodayRealisedProfit()
{
   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);

   tm.hour = 0;
   tm.min  = 0;
   tm.sec  = 0;

   datetime dayStart = StructToTime(tm);

   if(!HistorySelect(dayStart, TimeCurrent() + 1))
      return 0.0;

   double sum = 0.0;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0)
         continue;

      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
         continue;

      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != CurrentMagic)
         continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);

      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
         continue;

      sum += HistoryDealGetDouble(deal, DEAL_PROFIT)
           + HistoryDealGetDouble(deal, DEAL_SWAP)
           + HistoryDealGetDouble(deal, DEAL_COMMISSION);
   }

   return sum;
}

//  medium #9: v12 counted every closing DEAL, so each partial close
//  inflated the streak. Aggregate by position id first.
int ConsecutiveLosses()
{
   datetime from = TimeCurrent() - 30 * 24 * 60 * 60;   // bounded window

   if(!HistorySelect(from, TimeCurrent() + 1))
      return 0;

   int total = HistoryDealsTotal();

   if(total <= 0)
      return 0;

   ulong    ids[];
   double   pls[];
   datetime tms[];

   ArrayResize(ids, total);
   ArrayResize(pls, total);
   ArrayResize(tms, total);

   int n = 0;

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0) continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol) continue;
      if(!MagicMatches((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC))) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);

      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;

      ulong    pid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      datetime t   = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);

      double pl = HistoryDealGetDouble(deal, DEAL_PROFIT)
                + HistoryDealGetDouble(deal, DEAL_SWAP)
                + HistoryDealGetDouble(deal, DEAL_COMMISSION);

      int found = -1;

      for(int k = 0; k < n; k++)
      {
         if(ids[k] == pid) { found = k; break; }
      }

      if(found >= 0)
      {
         pls[found] += pl;
         if(t > tms[found]) tms[found] = t;
      }
      else
      {
         ids[n] = pid;
         pls[n] = pl;
         tms[n] = t;
         n++;
      }
   }

   //--- walk whole trades newest-first
   int count = 0;

   for(;;)
   {
      int newest = -1;

      for(int k = 0; k < n; k++)
      {
         if(tms[k] != 0 && (newest < 0 || tms[k] > tms[newest]))
            newest = k;
      }

      if(newest < 0)
         break;

      if(pls[newest] < 0.0)
      {
         count++;
         tms[newest] = 0;
      }
      else
         break;
   }

   return count;
}

//  Floating P/L of this instance's own open positions.
double OpenPositionsProfit()
{
   double sum = 0.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(!MagicMatches((ulong)PositionGetInteger(POSITION_MAGIC))) continue;

      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   return sum;
}

//  medium #10: v12 ran two full HistorySelect sweeps on every bar.
void RefreshGuardCache()
{
   datetime bar = iTime(_Symbol, WorkTF, 0);

   if(!GuardCacheDirty && bar == GuardCacheBar)
      return;

   GuardCacheBar   = bar;
   GuardCacheDirty = false;

   CachedTodayPL    = TodayRealisedProfit();
   CachedConsecLoss = UseConsecutiveLossLimit ? ConsecutiveLosses() : 0;
}

//==================================================================
//        H6: THE DAILY LOSS LIMIT NOW ACTUALLY LIMITS THE LOSS
//==================================================================
//  v12 only blocked new entries, and the check sat AFTER the
//  open-position early return in OnTick, so while a trade was live
//  it was never even evaluated. It also ignored floating P/L.
//------------------------------------------------------------------
bool DailyLossLimitHit()
{
   if(!UseDailyLossLimit || MaxDailyLossPercent <= 0.0)
      return false;

   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);
   tm.hour = 0; tm.min = 0; tm.sec = 0;

   datetime day = StructToTime(tm);

   if(day != DailyLimitDay)
   {
      DailyLimitDay     = day;
      DailyLimitLatched = false;
   }

   if(DailyLimitLatched)
      return true;

   RefreshGuardCache();

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double limit   = -(balance * MaxDailyLossPercent / 100.0);
   double today   = CachedTodayPL + OpenPositionsProfit();   // realised + floating

   if(today <= limit)
   {
      DailyLimitLatched = true;

      LogAlways("*** DAILY LOSS LIMIT HIT: " + DoubleToString(today, 2) +
                " vs limit " + DoubleToString(limit, 2) +
                " - action: " + EnumToString(DailyLossAction) + " ***");
      return true;
   }

   return false;
}

bool EquityDrawdownHit()
{
   if(!UseEquityDrawdownGuard || MaxEquityDrawdownPercent <= 0.0)
      return false;

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   if(eq > EquityPeak)
      EquityPeak = eq;

   if(EquityPeak <= 0.0)
      return false;

   double dd = (EquityPeak - eq) / EquityPeak * 100.0;

   if(dd >= MaxEquityDrawdownPercent)
   {
      LogAlways("*** EQUITY DRAWDOWN " + DoubleToString(dd, 2) +
                "% >= limit " + DoubleToString(MaxEquityDrawdownPercent, 2) + "% ***");
      return true;
   }

   return false;
}

//  Runs EVERY tick. Returns true when new entries must be blocked.
bool EnforceRiskShutdown()
{
   bool daily  = DailyLossLimitHit();
   bool equity = EquityDrawdownHit();

   if(!daily && !equity)
      return false;

   string why = daily ? "daily loss limit" : "equity drawdown limit";

   Comment(Tag() + "HALTED: " + why);

   ENUM_DAILY_LOSS_ACTION act = DailyLossAction;

   if(equity && act == DAILY_BLOCK_NEW)
      act = DAILY_BLOCK_AND_CANCEL;          // an equity stop must at least pull pendings

   if(act == DAILY_BLOCK_AND_CANCEL || act == DAILY_FLATTEN)
   {
      ulong b = FindMyOrder(ORDER_TYPE_BUY_STOP);
      if(b != 0) SafeDeleteOrder(b, why);

      ulong sp = FindMyOrder(ORDER_TYPE_SELL_STOP);
      if(sp != 0) SafeDeleteOrder(sp, why);
   }

   if(act == DAILY_FLATTEN)
   {
      ulong bp = FindMyPosition(POSITION_TYPE_BUY);
      if(bp != 0) SafeClosePosition(bp, why);

      ulong sl = FindMyPosition(POSITION_TYPE_SELL);
      if(sl != 0) SafeClosePosition(sl, why);
   }

   return true;
}

//  Entry-time guards only. The daily/equity shutdown is handled by
//  EnforceRiskShutdown(), which runs every tick regardless of state.
bool PassAccountGuards()
{
   if(OrphanDetected && !AdoptOrphanTimeframePositions && BlockEntriesWhileOrphaned)
   {
      Comment(Tag() + "BLOCKED: orphaned trade from another timeframe (" + OrphanNote + ")");
      return false;
   }

   if(UseConsecutiveLossLimit && MaxConsecutiveLosses > 0)
   {
      RefreshGuardCache();

      if(CachedConsecLoss >= MaxConsecutiveLosses)
      {
         Comment(Tag() + "CONSECUTIVE LOSS LIMIT: " + IntegerToString(CachedConsecLoss));
         return false;
      }
   }

   return true;
}

//  H7: v12 returned silently, so all management stopped with no
//  warning at all. Announce both transitions.
bool TradingAllowedWithNotice()
{
   bool ok = TradingAllowed();

   if(!TradingStateKnown)
   {
      TradingStateKnown = true;
      TradingWasAllowed = ok;

      if(!ok)
         LogAlways("*** AUTOTRADING IS OFF - this EA will not manage anything. ***");
   }
   else if(ok != TradingWasAllowed)
   {
      TradingWasAllowed = ok;

      if(ok)
         LogAlways("AutoTrading re-enabled - management resumed.");
      else
         LogAlways("*** AUTOTRADING DISABLED - break-even, trailing and exits are NOT running. "
                   "Any open position now relies on its broker stop alone. ***");
   }

   if(!ok)
      Comment(Tag() + "AUTOTRADING OFF - nothing is being managed");

   return ok;
}

bool TradingAllowed()
{
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return false;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))           return false;
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))    return false;
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))   return false;

   return true;
}

//==================================================================
//                     RUNTIME SANITY CHECK (fix #10)
//==================================================================
//  Point-based inputs are meaningless without knowing the symbol.
//  Once ATR is available, compare them against real volatility and
//  shout if they are nonsense for this symbol/timeframe pair.
//------------------------------------------------------------------

void RuntimeSanityCheck()
{
   if(SanityChecked)
      return;

   double atr = GetATRValue(1);

   if(atr <= 0.0)
      return;                        // not ready yet, try next bar

   SanityChecked = true;

   double atrPoints = atr / _Point;

   LogAlways("Sanity: ATR(" + IntegerToString(ATRPeriod) + ") = " +
             DoubleToString(atrPoints, 0) + " points (" +
             DoubleToString(atr, _Digits) + " price) on " +
             EnumToString(WorkTF));

   if(UseATRScaledLevels)
   {
      LogAlways("Sanity: ATR-scaled levels ON, fixed point inputs ignored.");
      return;
   }

   if(EnableBreakEven && (double)BreakEvenTriggerPoints < atrPoints * 0.10)
      LogAlways("WARNING: BreakEvenTriggerPoints (" + IntegerToString(BreakEvenTriggerPoints) +
                ") is under 10% of ATR. Break-even will fire almost instantly on this " +
                "timeframe. Consider UseATRScaledLevels=true.");

   if((double)MinStopPoints > atrPoints * 5.0)
      LogAlways("WARNING: MinStopPoints (" + IntegerToString(MinStopPoints) +
                ") is over 5x ATR. Most setups will be rejected.");

   if(UseRiskFilter && (double)MaximumLossPoints < atrPoints * 0.25)
      LogAlways("WARNING: MaximumLossPoints (" + IntegerToString(MaximumLossPoints) +
                ") is under 25% of ATR. The emergency stop will fire on normal noise.");

   if(UseMaxSpreadFilter)
   {
      long spread = CurrentSpreadPoints();

      if(spread > 0 && (double)EntryBufferPoints < (double)spread)
         LogAlways("NOTE: EntryBufferPoints (" + IntegerToString(EntryBufferPoints) +
                   ") is smaller than the current spread (" + IntegerToString(spread) +
                   "). AddSpreadToBuyEntry=" + (AddSpreadToBuyEntry ? "true" : "false"));
   }
}

//==================================================================
//                           SIGNALS
//==================================================================

bool BuySignal()
{
   double ma18_1  = GetMAValue(FastMAHandle,  1);
   double ma18_2  = GetMAValue(FastMAHandle,  2);
   double ma200_1 = GetMAValue(TrendMAHandle, 1);
   double ma200_2 = GetMAValue(TrendMAHandle, 2);

   if(ma18_1 <= 0.0 || ma18_2 <= 0.0 || ma200_1 <= 0.0 || ma200_2 <= 0.0)
      return false;

   double close1 = iClose(_Symbol, WorkTF, 1);
   double close2 = iClose(_Symbol, WorkTF, 2);

   //--- 18 SMA above 200 SMA on both bars
   if(ma18_1 <= ma200_1) return false;
   if(ma18_2 <= ma200_2) return false;

   //--- two consecutive closes above both SMAs
   if(close1 <= ma18_1)  return false;
   if(close2 <= ma18_2)  return false;
   if(close1 <= ma200_1) return false;
   if(close2 <= ma200_2) return false;

   //--- volume confirmation
   if(UseVolumeFilter)
   {
      double avg = GetAverageVolume(VolumeMAPeriod);

      if(avg <= 0.0)
         return false;

      if((double)iVolume(_Symbol, WorkTF, 1) <= avg)
         return false;
   }

   return true;
}

bool SellSignal()
{
   double ma18_1  = GetMAValue(FastMAHandle,  1);
   double ma18_2  = GetMAValue(FastMAHandle,  2);
   double ma200_1 = GetMAValue(TrendMAHandle, 1);
   double ma200_2 = GetMAValue(TrendMAHandle, 2);

   if(ma18_1 <= 0.0 || ma18_2 <= 0.0 || ma200_1 <= 0.0 || ma200_2 <= 0.0)
      return false;

   double close1 = iClose(_Symbol, WorkTF, 1);
   double close2 = iClose(_Symbol, WorkTF, 2);

   if(ma18_1 >= ma200_1) return false;
   if(ma18_2 >= ma200_2) return false;

   if(close1 >= ma18_1)  return false;
   if(close2 >= ma18_2)  return false;
   if(close1 >= ma200_1) return false;
   if(close2 >= ma200_2) return false;

   if(UseVolumeFilter)
   {
      double avg = GetAverageVolume(VolumeMAPeriod);

      if(avg <= 0.0)
         return false;

      if((double)iVolume(_Symbol, WorkTF, 1) <= avg)
         return false;
   }

   return true;
}

// fix #14: exits and pending-invalidation now use the same boundary.
bool BuyExitSignal()
{
   double ma18  = NormalizeDouble(GetMAValue(FastMAHandle, 1), _Digits);
   double close = NormalizeDouble(iClose(_Symbol, WorkTF, 1), _Digits);

   if(ma18 <= 0.0)
      return false;

   return (close < ma18);
}

bool SellExitSignal()
{
   double ma18  = NormalizeDouble(GetMAValue(FastMAHandle, 1), _Digits);
   double close = NormalizeDouble(iClose(_Symbol, WorkTF, 1), _Digits);

   if(ma18 <= 0.0)
      return false;

   return (close > ma18);
}

// A pending buy is dead once price closes back under the fast MA,
// or once the trend filter itself flips.
bool PendingBuyInvalidated()
{
   double ma18  = GetMAValue(FastMAHandle,  1);
   double ma200 = GetMAValue(TrendMAHandle, 1);
   double close = iClose(_Symbol, WorkTF, 1);

   if(ma18 <= 0.0 || ma200 <= 0.0)
      return false;

   if(close < ma18)   return true;
   if(ma18  < ma200)  return true;          // trend filter flipped

   return false;
}

bool PendingSellInvalidated()
{
   double ma18  = GetMAValue(FastMAHandle,  1);
   double ma200 = GetMAValue(TrendMAHandle, 1);
   double close = iClose(_Symbol, WorkTF, 1);

   if(ma18 <= 0.0 || ma200 <= 0.0)
      return false;

   if(close > ma18)   return true;
   if(ma18  > ma200)  return true;

   return false;
}

//==================================================================
//                   POINTS MAX-LOSS STOP SHAPING
//==================================================================
//  v11's MaxLossMode, applied where the initial stop is built.
//  Returns the stop to actually use, or 0.0 if the trade should be
//  skipped. `swingSL` may be 0.0 when no swing was found - which is
//  fine in REPLACE_SWING mode, because the swing is not needed.
//------------------------------------------------------------------
double ApplyMaxLossToStop(const double entry, const double swingSL, const bool isBuy)
{
   //--- modes that do not reshape the entry stop
   if(MaxLossMode == MAXLOSS_OFF || MaxLossMode == MAXLOSS_EXIT_RULE_ONLY)
      return swingSL;

   if(MaxLossPoints <= 0)
      return swingSL;

   double cap    = MaxLossCapDistance();
   double capSL  = isBuy ? (entry - cap) : (entry + cap);

   if(MaxLossMode == MAXLOSS_REPLACE_SWING)
      return NormalizeDouble(capSL, _Digits);

   //--- MAXLOSS_CAP_TIGHTER: whichever of the two risks less
   if(swingSL <= 0.0)
      return NormalizeDouble(capSL, _Digits);

   double tighter = isBuy ? MathMax(swingSL, capSL) : MathMin(swingSL, capSL);

   return NormalizeDouble(tighter, _Digits);
}

// In REPLACE_SWING mode a missing swing is not a reason to skip.
bool SwingRequiredForEntry()
{
   return (MaxLossMode != MAXLOSS_REPLACE_SWING || MaxLossPoints <= 0);
}

//==================================================================
//                        ENTRY PLACEMENT
//==================================================================

bool PlaceBuyStop()
{
   if(FindMyPosition(POSITION_TYPE_BUY) != 0) return false;
   if(FindMyOrder(ORDER_TYPE_BUY_STOP)  != 0) return false;

   //--- fix #6: no swing, no trade (unless MaxLossMode replaces it)
   double sl = GetSwingLow();

   if(sl <= 0.0 && SwingRequiredForEntry())
   {
      Log("BUY skipped: no confirmed swing low within " +
          IntegerToString(SwingSearchBars) + " bars.");
      return false;
   }

   //--- fix #5: a buy stop triggers on ASK, but bars are built from BID
   double entry = iHigh(_Symbol, WorkTF, 1) + (double)EntryBufferPoints * _Point;

   if(AddSpreadToBuyEntry)
      entry += (double)CurrentSpreadPoints() * _Point;

   entry = NormalizeDouble(entry, _Digits);

   //--- v11 MaxLossMode shaping
   sl = ApplyMaxLossToStop(entry, sl, true);

   if(sl <= 0.0)
   {
      Log("BUY skipped: no usable stop level.");
      return false;
   }

   sl = NormalizeDouble(sl, _Digits);

   if(sl >= entry)
   {
      Log("BUY skipped: swing low " + DoubleToString(sl, _Digits) +
          " is not below entry " + DoubleToString(entry, _Digits));
      return false;
   }

   //--- fix #1: enforce the hard minimum stop distance
   double minStop = MinimumStopDistance();

   if(entry - sl < minStop)
   {
      Log("BUY skipped: stop distance " +
          DoubleToString((entry - sl) / _Point, 0) + " pts is under the floor of " +
          DoubleToString(minStop / _Point, 0) + " pts");
      return false;
   }

   //--- the pending price must sit far enough above the market
   double ask = CurrentAsk();

   if(entry - ask < BrokerMinDistance())
   {
      entry = NormalizeDouble(ask + BrokerMinDistance(), _Digits);

      if(entry - sl < minStop)
      {
         Log("BUY skipped: price already past the breakout level.");
         return false;
      }
   }

   if(!PassSLPercentFilter(ORDER_TYPE_BUY, entry, sl)) return false;
   if(!PassMarginCheck(ORDER_TYPE_BUY, entry))         return false;

   bool ok = trade.BuyStop(LotSize, entry, _Symbol, sl, 0.0,
                           ORDER_TIME_GTC, 0, "SMA18 v12 BUY");

   if(ok)
   {
      PendingPlacedBarTime = iTime(_Symbol, WorkTF, 0);

      LogAlways("BUY STOP @ " + DoubleToString(entry, _Digits) +
                "  SL " + DoubleToString(sl, _Digits) +
                "  (" + DoubleToString((entry - sl) / _Point, 0) + " pts)");
   }
   else
   {
      LogAlways("BUY STOP failed rc=" + IntegerToString((int)trade.ResultRetcode()) +
                " (" + trade.ResultRetcodeDescription() + ")");
   }

   return ok;
}

bool PlaceSellStop()
{
   if(FindMyPosition(POSITION_TYPE_SELL) != 0) return false;
   if(FindMyOrder(ORDER_TYPE_SELL_STOP)  != 0) return false;

   double sl = GetSwingHigh();

   if(sl <= 0.0 && SwingRequiredForEntry())
   {
      Log("SELL skipped: no confirmed swing high within " +
          IntegerToString(SwingSearchBars) + " bars.");
      return false;
   }

   // sell stops trigger on BID, which is what bars are built from,
   // so no spread adjustment is needed on this side.
   double entry = iLow(_Symbol, WorkTF, 1) - (double)EntryBufferPoints * _Point;

   entry = NormalizeDouble(entry, _Digits);

   //--- v11 MaxLossMode shaping
   sl = ApplyMaxLossToStop(entry, sl, false);

   if(sl <= 0.0)
   {
      Log("SELL skipped: no usable stop level.");
      return false;
   }

   sl = NormalizeDouble(sl, _Digits);

   if(sl <= entry)
   {
      Log("SELL skipped: swing high " + DoubleToString(sl, _Digits) +
          " is not above entry " + DoubleToString(entry, _Digits));
      return false;
   }

   double minStop = MinimumStopDistance();

   if(sl - entry < minStop)
   {
      Log("SELL skipped: stop distance " +
          DoubleToString((sl - entry) / _Point, 0) + " pts is under the floor of " +
          DoubleToString(minStop / _Point, 0) + " pts");
      return false;
   }

   double bid = CurrentBid();

   if(bid - entry < BrokerMinDistance())
   {
      entry = NormalizeDouble(bid - BrokerMinDistance(), _Digits);

      if(sl - entry < minStop)
      {
         Log("SELL skipped: price already past the breakout level.");
         return false;
      }
   }

   if(!PassSLPercentFilter(ORDER_TYPE_SELL, entry, sl)) return false;
   if(!PassMarginCheck(ORDER_TYPE_SELL, entry))         return false;

   bool ok = trade.SellStop(LotSize, entry, _Symbol, sl, 0.0,
                            ORDER_TIME_GTC, 0, "SMA18 v12 SELL");

   if(ok)
   {
      PendingPlacedBarTime = iTime(_Symbol, WorkTF, 0);

      LogAlways("SELL STOP @ " + DoubleToString(entry, _Digits) +
                "  SL " + DoubleToString(sl, _Digits) +
                "  (" + DoubleToString((sl - entry) / _Point, 0) + " pts)");
   }
   else
   {
      LogAlways("SELL STOP failed rc=" + IntegerToString((int)trade.ResultRetcode()) +
                " (" + trade.ResultRetcodeDescription() + ")");
   }

   return ok;
}

//==================================================================
//                    PENDING ORDER MANAGEMENT
//==================================================================

//  Recover the pending order's age after a terminal/EA restart,
//  otherwise MaxPendingBars would silently never fire on an order
//  that was placed before this run started.
void EnsurePendingAgeKnown(const ulong ticket)
{
   if(PendingPlacedBarTime != 0)
      return;

   if(!OrderSelect(ticket))
      return;

   datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
   int      shift = iBarShift(_Symbol, WorkTF, setup, false);

   if(shift < 0)
      shift = 0;

   PendingPlacedBarTime = iTime(_Symbol, WorkTF, shift);

   Log("Recovered pending #" + IntegerToString((long)ticket) +
       " placed on bar " + TimeToString(PendingPlacedBarTime));
}

bool PendingIsStale()
{
   if(MaxPendingBars <= 0)
      return false;

   if(PendingPlacedBarTime == 0)
      return false;

   int barsSince = iBarShift(_Symbol, WorkTF, PendingPlacedBarTime, false);

   return (barsSince > MaxPendingBars);
}

bool WeekendIsClose()
{
   if(!CancelPendingBeforeWeekend)
      return false;

   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);

   return (tm.day_of_week == 5 && tm.hour >= 20);
}

//  fix #1: the ratchet now has a floor. It can tighten the stop as
//  structure improves, but it can NEVER bring the stop closer to
//  entry than MinimumStopDistance(). The old code had no floor and
//  would happily fill you with a 20-point stop after a long wait.
void ManagePendingBuy(const ulong ticket)
{
   EnsurePendingAgeKnown(ticket);

   if(WeekendIsClose())
   {
      SafeDeleteOrder(ticket, "weekend");
      return;
   }

   if(PendingIsStale())
   {
      SafeDeleteOrder(ticket, "expired after " + IntegerToString(MaxPendingBars) + " bars");
      return;
   }

   if(PendingBuyInvalidated())
   {
      SafeDeleteOrder(ticket, "setup invalidated");
      return;
   }

   if(!RatchetPendingSL)
      return;

   if(!OrderSelect(ticket))
      return;

   double entry = OrderGetDouble(ORDER_PRICE_OPEN);
   double oldSL = OrderGetDouble(ORDER_SL);
   double tp    = OrderGetDouble(ORDER_TP);

   double newSL = GetSwingLow();

   if(newSL <= 0.0)
      return;

   newSL = NormalizeDouble(newSL, _Digits);

   //--- THE FLOOR. Never let the stop come inside this.
   if(PendingIsFrozen(entry, true))    // C4
      return;

   double floorSL = NormalizeDouble(entry - MinimumStopDistance(), _Digits);

   if(newSL > floorSL)
      return;                         // proposed stop is too tight, leave it alone

   if(newSL <= oldSL + _Point * 0.5)
      return;                         // not an improvement

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(trade.OrderModify(ticket, entry, newSL, tp, ORDER_TIME_GTC, 0))
      {
         Log("Pending BUY SL -> " + DoubleToString(newSL, _Digits) +
             "  (" + DoubleToString((entry - newSL) / _Point, 0) + " pts)");
         return;
      }

      if(!IsRetryableRetcode(trade.ResultRetcode()))
         return;

      PauseBetweenRetries();
   }
}

void ManagePendingSell(const ulong ticket)
{
   EnsurePendingAgeKnown(ticket);

   if(WeekendIsClose())
   {
      SafeDeleteOrder(ticket, "weekend");
      return;
   }

   if(PendingIsStale())
   {
      SafeDeleteOrder(ticket, "expired after " + IntegerToString(MaxPendingBars) + " bars");
      return;
   }

   if(PendingSellInvalidated())
   {
      SafeDeleteOrder(ticket, "setup invalidated");
      return;
   }

   if(!RatchetPendingSL)
      return;

   if(!OrderSelect(ticket))
      return;

   double entry = OrderGetDouble(ORDER_PRICE_OPEN);
   double oldSL = OrderGetDouble(ORDER_SL);
   double tp    = OrderGetDouble(ORDER_TP);

   double newSL = GetSwingHigh();

   if(newSL <= 0.0)
      return;

   newSL = NormalizeDouble(newSL, _Digits);

   if(PendingIsFrozen(entry, false))   // C4
      return;

   double floorSL = NormalizeDouble(entry + MinimumStopDistance(), _Digits);

   if(newSL < floorSL)
      return;                         // too tight

   if(oldSL > 0.0 && newSL >= oldSL - _Point * 0.5)
      return;                         // not an improvement

   for(int attempt = 1; attempt <= MathMax(1, MaxTradeRetries); attempt++)
   {
      if(trade.OrderModify(ticket, entry, newSL, tp, ORDER_TIME_GTC, 0))
      {
         Log("Pending SELL SL -> " + DoubleToString(newSL, _Digits) +
             "  (" + DoubleToString((newSL - entry) / _Point, 0) + " pts)");
         return;
      }

      if(!IsRetryableRetcode(trade.ResultRetcode()))
         return;

      PauseBetweenRetries();
   }
}

//==================================================================
//        H5 + C4: PENDING UPKEEP THAT CANNOT WAIT FOR A NEW BAR
//==================================================================
//  v12 did the weekend cancel inside the IsNewBar() gate. On D1 there
//  is no new bar between Friday 20:00 and the close, so the order
//  survived into the Monday gap - precisely what the option exists to
//  prevent. This runs every tick instead.
//------------------------------------------------------------------
void ManagePendingIntrabar()
{
   //--- C4: retry a cancel the broker refused (freeze level etc.)
   if(PendingCancelTicket != 0)
   {
      ulong t = PendingCancelTicket;

      if(!OrderSelect(t))
      {
         PendingCancelTicket = 0;            // it filled or is already gone
      }
      else
      {
         PendingCancelTicket = 0;            // SafeDeleteOrder re-latches on failure
         SafeDeleteOrder(t, PendingCancelReason);
      }
   }

   if(!WeekendIsClose())
      return;

   ulong b = FindMyOrder(ORDER_TYPE_BUY_STOP);
   if(b != 0) SafeDeleteOrder(b, "weekend");

   ulong sp = FindMyOrder(ORDER_TYPE_SELL_STOP);
   if(sp != 0) SafeDeleteOrder(sp, "weekend");
}

//==================================================================
//                      STOP-LEVEL CANDIDATES
//==================================================================

double BreakEvenStopPrice(const ulong ticket, const bool isBuy)
{
   if(!EnableBreakEven)
      return 0.0;

   if(PositionProfitDistance(ticket, isBuy) < BreakEvenTriggerDistance())
      return 0.0;

   if(!PositionSelectByTicket(ticket))
      return 0.0;

   double open   = PositionGetDouble(POSITION_PRICE_OPEN);
   double offset = (double)BreakEvenOffsetPoints * _Point;

   return isBuy ? (open + offset) : (open - offset);
}

bool ProtectionShouldRun(const ulong ticket, const bool isBuy)
{
   if(ProtectionMode == PROTECTION_NONE)
      return false;

   if(ProtectionStartMode == START_IMMEDIATELY)
      return true;

   return (PositionProfitDistance(ticket, isBuy) >= ProtectionStartDistance());
}

double SwingProtectionStop(const bool isBuy)
{
   double buffer = (double)SwingBufferPoints * _Point;

   if(isBuy)
   {
      double sw = GetSwingLow();
      return (sw > 0.0) ? (sw - buffer) : 0.0;
   }

   double sw = GetSwingHigh();
   return (sw > 0.0) ? (sw + buffer) : 0.0;
}

double ChandelierStop(const bool isBuy)
{
   double atr = GetATRValue(1);

   if(atr <= 0.0)
      return 0.0;

   if(isBuy)
   {
      double highest = iHigh(_Symbol, WorkTF, 1);

      for(int i = 2; i <= ChandelierLookback; i++)
      {
         double h = iHigh(_Symbol, WorkTF, i);

         if(h > highest)
            highest = h;
      }

      return highest - atr * ATRMultiplier;
   }

   double lowest = iLow(_Symbol, WorkTF, 1);

   for(int i = 2; i <= ChandelierLookback; i++)
   {
      double l = iLow(_Symbol, WorkTF, i);

      if(l < lowest)
         lowest = l;
   }

   return lowest + atr * ATRMultiplier;
}

double FixedTrailingStop(const ulong ticket, const bool isBuy)
{
   if(PositionProfitDistance(ticket, isBuy) < TrailingStartDistance())
      return 0.0;

   if(!PositionSelectByTicket(ticket))
      return 0.0;

   double curSL = PositionGetDouble(POSITION_SL);
   double dist  = TrailingDistance();
   double step  = (double)TrailingStepPoints * _Point;

   if(isBuy)
   {
      double desired = CurrentBid() - dist;

      if(curSL > 0.0 && desired - curSL < step)
         return 0.0;                         // respect the step size

      return desired;
   }

   double desired = CurrentAsk() + dist;

   if(curSL > 0.0 && curSL - desired < step)
      return 0.0;

   return desired;
}

double ProtectionStopPrice(const ulong ticket, const bool isBuy)
{
   if(!ProtectionShouldRun(ticket, isBuy))
      return 0.0;

   switch(ProtectionMode)
   {
      case PROTECTION_SWING:      return SwingProtectionStop(isBuy);
      case PROTECTION_CHANDELIER: return ChandelierStop(isBuy);
      case PROTECTION_TRAILING:   return FixedTrailingStop(ticket, isBuy);
      default:                    return 0.0;
   }
}

string ProtectionName()
{
   switch(ProtectionMode)
   {
      case PROTECTION_SWING:      return "Swing";
      case PROTECTION_CHANDELIER: return "Chandelier";
      case PROTECTION_TRAILING:   return "Trailing";
      default:                    return "None";
   }
}

//  fix #12: break-even and protection used to be two separate
//  ModifyStopLoss calls fighting over the same stop, with no way to
//  tell from the log which one won. Now they are resolved into one
//  decision and the winner is named.
void ApplyStopManagement(const ulong ticket, const bool isBuy)
{
   double be = BreakEvenStopPrice(ticket, isBuy);
   double pr = ProtectionStopPrice(ticket, isBuy);

   double best   = 0.0;
   string reason = "";

   if(be > 0.0)
   {
      best   = be;
      reason = "BreakEven";
   }

   if(pr > 0.0)
   {
      bool tighter = (best <= 0.0) || (isBuy ? (pr > best) : (pr < best));

      if(tighter)
      {
         best   = pr;
         reason = ProtectionName();
      }
   }

   if(best <= 0.0)
      return;

   SafeModifyPositionSL(ticket, best, reason);
}

//==================================================================
//                      POSITION MANAGEMENT
//==================================================================

// returns true if the position was closed
bool ManageRiskFilter(const ulong ticket, const bool isBuy)
{
   if(!UseRiskFilter)
      return false;

   //--- do not let a spread blow-out trigger the emergency exit
   if(UseMaxSpreadFilter && CurrentSpreadPoints() > MaxSpreadPoints)
      return false;

   double adverse = -PositionProfitDistance(ticket, isBuy);

   if(adverse < MaximumLossDistance())
      return false;

   if(SafeClosePosition(ticket,
         "emergency stop at " + DoubleToString(adverse / _Point, 0) + " pts"))
   {
      CntEmergency++;
      return true;
   }

   return false;
}

// fix #3: this exists AND is called now.
bool ManageFailedBreakoutExit(const ulong ticket, const bool isBuy)
{
   if(!UseFailedBreakoutExit)
      return false;

   if(ticket != TrackedTicket || TrackedEntryBarTime == 0)
      return false;

   int barsSince = iBarShift(_Symbol, WorkTF, TrackedEntryBarTime, false);

   if(barsSince < 1 || barsSince > FailedBreakoutBars)
      return false;

   double close1 = iClose(_Symbol, WorkTF, 1);
   double buffer = (double)BreakoutRetestBufferPoints * _Point;

   if(isBuy && close1 < TrackedEntryPrice - buffer)
   {
      if(SafeClosePosition(ticket, "failed BUY breakout")) { CntFailedBO++; return true; }
   }

   if(!isBuy && close1 > TrackedEntryPrice + buffer)
   {
      if(SafeClosePosition(ticket, "failed SELL breakout")) { CntFailedBO++; return true; }
   }

   return false;
}

// fix #3: partial close was three inputs and zero lines of code.
void ManagePartialClose(const ulong ticket, const bool isBuy)
{
   if(!EnablePartialClose)
      return;

   if(ticket != TrackedTicket || TrackedPartialDone)
      return;

   if(PartialClosePercent <= 0.0 || PartialClosePercent >= 100.0)
      return;

   if(PositionProfitDistance(ticket, isBuy) < PartialTriggerDistance())
      return;

   if(!PositionSelectByTicket(ticket))
      return;

   double volume   = PositionGetDouble(POSITION_VOLUME);
   double closeVol = NormalizeVolume(volume * PartialClosePercent / 100.0);

   if(closeVol <= 0.0)
      return;

   //--- the remainder must still be a legal volume
   if(volume - closeVol < SymVolMin - 1e-9)
   {
      Log("Partial close skipped: remainder would be below the minimum volume.");
      TrackedPartialDone = true;               // do not retry every tick
      return;
   }

   if(SafeClosePartial(ticket, closeVol, DoubleToString(PartialClosePercent, 0) + "%"))
   {
      TrackedPartialDone = true;
      CntPartial++;
   }
}

//==================================================================
//                  FOLLOW-THROUGH EXIT (from v11)
//==================================================================
//  Differences from v11's version, all of them deliberate:
//   * ticket-scoped, so it cannot act on another instance's trade
//   * anchors on the REAL entry bar (iBarShift), not on whichever
//     bar the EA happened to notice the fill on
//   * the points max-loss cap is spread-guarded, so a news spread
//     blow-out cannot fake an adverse move and force the exit
//   * if the EA was attached after the window already passed, the
//     rule stands down instead of evaluating stale candles
//  Returns true when the position was closed.
//------------------------------------------------------------------
bool ManageFollowThrough(const ulong ticket, const bool isBuy)
{
   if(ticket != TrackedTicket)
      return false;

   //--- MAXLOSS_EXIT_RULE_ONLY: cap the loss inside the window only
   if(MaxLossMode == MAXLOSS_EXIT_RULE_ONLY && FT_WindowOpen && MaxLossPoints > 0)
   {
      bool spreadOK = !(UseMaxSpreadFilter && CurrentSpreadPoints() > MaxSpreadPoints);

      if(spreadOK)
      {
         double adverse = -PositionProfitDistance(ticket, isBuy);

         if(adverse >= MaxLossCapDistance())
         {
            if(SafeClosePosition(ticket, "points max-loss cap at " +
                                 DoubleToString(adverse / _Point, 0) + " pts"))
            {
               CntMaxLoss++;
               FT_WindowOpen = false;
               return true;
            }
         }
      }
   }

   if(FollowMode == FOLLOW_OFF)
      return false;

   //--- own new-bar detection, independent of the main IsNewBar()
   datetime curBar = iTime(_Symbol, WorkTF, 0);

   if(curBar == 0 || curBar == FT_LastBar)
      return false;

   FT_LastBar = curBar;

   //--- capture the entry candle once it has completed
   if(!FT_EntryCaptured)
   {
      if(TrackedEntryBarTime == 0)
         return false;

      int entryShift = iBarShift(_Symbol, WorkTF, TrackedEntryBarTime, false);

      if(entryShift < 1)
         return false;                     // entry bar is still forming

      FT_EntryHigh     = iHigh(_Symbol, WorkTF, entryShift);
      FT_EntryLow      = iLow(_Symbol,  WorkTF, entryShift);
      FT_EntryCaptured = true;

      if(entryShift > 1)
      {
         // we were attached after the decision candle already closed
         FT_WindowOpen = false;
         Log("Follow-through window already passed at attach time; rule stands down.");
      }

      return false;                        // evaluate on the NEXT bar
   }

   //--- FOLLOW_ANY_STALL keeps checking every bar
   if(FollowMode == FOLLOW_ANY_STALL)
   {
      bool made = isBuy
                  ? (iHigh(_Symbol, WorkTF, 1) > iHigh(_Symbol, WorkTF, 2))
                  : (iLow(_Symbol,  WorkTF, 1) < iLow(_Symbol,  WorkTF, 2));

      FT_WindowOpen = false;

      if(!made && SafeClosePosition(ticket, "no follow-through (stall)"))
      {
         CntNoFollow++;
         return true;
      }

      return false;
    }

   //--- NEXT_VS_ENTRY / VS_TRIGGER: only the first candle after entry
   if(FT_WindowOpen)
   {
      double ref = (FollowMode == FOLLOW_VS_TRIGGER)
                   ? TrackedEntryPrice
                   : (isBuy ? FT_EntryHigh : FT_EntryLow);

      bool followed = isBuy
                      ? (iHigh(_Symbol, WorkTF, 1) > ref)
                      : (iLow(_Symbol,  WorkTF, 1) < ref);

      FT_WindowOpen = false;

      if(!followed && SafeClosePosition(ticket, "no follow-through vs " +
                                        DoubleToString(ref, _Digits)))
      {
         CntNoFollow++;
         return true;
      }
   }

   return false;
}

//  fix #7: buy and sell are managed independently. The old code
//  returned out of the whole function after the buy branch, so on a
//  hedging account a simultaneous sell got no management at all.
void ManagePosition(const ulong ticket, const bool isBuy)
{
   if(ticket == 0)
      return;

   if(!PositionSelectByTicket(ticket))
      return;

   //--- 1. hard emergency stop
   if(ManageRiskFilter(ticket, isBuy))
      return;

   //--- 2. follow-through window + points max-loss cap (v11 rules)
   if(ManageFollowThrough(ticket, isBuy))
      return;

   //--- 3. failed breakout window
   if(ManageFailedBreakoutExit(ticket, isBuy))
      return;

   //--- 4. structural exit on the fast MA
   if(isBuy ? BuyExitSignal() : SellExitSignal())
   {
      if(SafeClosePosition(ticket, "SMA" + IntegerToString(FastMAPeriod) + " exit"))
         CntMA18Exit++;

      return;
   }

   //--- 5. scale out
   ManagePartialClose(ticket, isBuy);

   //--- 6. one unified stop decision
   ApplyStopManagement(ticket, isBuy);
}

//==================================================================
//                      TRACKED STATE UPDATE
//==================================================================

void UpdateTrackedState()
{
   ulong ticket = FindMyAnyPosition();

   if(ticket == 0)
   {
      if(TrackedTicket != 0)
         GuardCacheDirty = true;          // a trade just closed: guards must recompute

      TrackedTicket       = 0;
      TrackedEntryBarTime = 0;
      TrackedEntryPrice   = 0.0;
      TrackedInitialRisk  = 0.0;
      TrackedPartialDone  = false;
      FT_WindowOpen       = false;
      FT_EntryCaptured    = false;
      return;
   }

   if(ticket == TrackedTicket)
      return;

   if(!PositionSelectByTicket(ticket))
      return;

   TrackedTicket      = ticket;
   TrackedIsBuy       = ((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   TrackedEntryPrice  = PositionGetDouble(POSITION_PRICE_OPEN);
   TrackedPartialDone = false;

   //--- capture the ORIGINAL risk before we start moving the stop.
   //  This is the unit for every R-multiple level.
   double initSL = PositionGetDouble(POSITION_SL);

   TrackedInitialRisk = (initSL > 0.0)
                        ? MathAbs(TrackedEntryPrice - initSL)
                        : 0.0;

   GuardCacheDirty = true;

   //--- resolve the ACTUAL entry bar, not "whatever bar we noticed it on"
   datetime entryTime = (datetime)PositionGetInteger(POSITION_TIME);
   int      shift     = iBarShift(_Symbol, WorkTF, entryTime, false);

   if(shift < 0)
      shift = 0;

   TrackedEntryBarTime  = iTime(_Symbol, WorkTF, shift);
   PendingPlacedBarTime = 0;

   //--- arm a fresh follow-through window for this position
   FT_EntryCaptured = false;
   FT_WindowOpen    = true;
   FT_EntryHigh     = 0.0;
   FT_EntryLow      = 0.0;
   FT_LastBar       = iTime(_Symbol, WorkTF, 0);

   LogAlways("Tracking #" + IntegerToString((long)ticket) +
             " " + (TrackedIsBuy ? "BUY" : "SELL") +
             " @ " + DoubleToString(TrackedEntryPrice, _Digits) +
             " entry bar " + TimeToString(TrackedEntryBarTime) +
             " | 1R = " + DoubleToString(TrackedInitialRisk / _Point, 0) + " pts");
}

//==================================================================
//                 END-OF-RUN TRADE STUDY + CSV EXPORT
//==================================================================
//  Ported from v11 with three corrections:
//   * v11 filtered history on the raw MagicNumber. v12's trades
//     carry the timeframe-derived magic, so it filters on that.
//   * v11 always wrote "SMA18_trades_<symbol>.csv", so every tester
//     run silently destroyed the previous one. The name now carries
//     the version, timeframe and magic, and optionally a run stamp,
//     so a v11 run and a v12 run can sit side by side.
//   * the covered date range is printed AND written, because a row
//     count means nothing without the span it came from.
//   * entry and exit deals are paired by POSITION_ID, so each row is
//     a whole trade rather than just a closing deal.
//------------------------------------------------------------------

string BuildCSVName()
{
   string name = "SMA18_v12_" + _Symbol + "_" +
                 StringSubstr(EnumToString(WorkTF), 7) + "_" +
                 IntegerToString((long)CurrentMagic);

   if(AppendRunStampToCSV)
   {
      MqlDateTime tm;
      TimeToStruct(TimeLocal(), tm);

      name += StringFormat("_%04d%02d%02d_%02d%02d%02d",
                           tm.year, tm.mon, tm.day, tm.hour, tm.min, tm.sec);
   }

   return name + ".csv";
}

void ReportAndExport()
{
   //--- never write thousands of files during an optimisation pass
   if(MQLInfoInteger(MQL_OPTIMIZATION))
      return;

   if(!HistorySelect(0, TimeCurrent() + 1))
      return;

   int total = HistoryDealsTotal();

   if(total <= 0)
      return;

   //--- pass 1: index the entry deals by position id
   ulong    posId[];
   datetime posInTime[];
   double   posInPrice[];

   ArrayResize(posId, total);
   ArrayResize(posInTime, total);
   ArrayResize(posInPrice, total);

   int inCount = 0;

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0) continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol) continue;
      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != CurrentMagic) continue;

      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;

      posId[inCount]      = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      posInTime[inCount]  = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      posInPrice[inCount] = HistoryDealGetDouble(deal, DEAL_PRICE);
      inCount++;
   }

   //--- open the CSV
   int    handle = INVALID_HANDLE;
   string fname  = BuildCSVName();

   if(WriteTradeCSV)
   {
      handle = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');

      if(handle != INVALID_HANDLE)
         FileWrite(handle, "idx", "position_id", "side",
                   "entry_time", "entry_price",
                   "exit_time", "exit_price",
                   "volume", "minutes_held", "profit", "cum_net", "exit_reason");
      else
         LogAlways("CSV export FAILED to open " + fname +
                   " err=" + IntegerToString(GetLastError()));
   }

   //--- pass 2: walk the exits
   int    exits = 0, wins = 0, losses = 0;
   int    slExits = 0, tpExits = 0, eaExits = 0;
   double grossProfit = 0.0, grossLoss = 0.0, cum = 0.0;
   double bestWin = 0.0, worstLoss = 0.0;
   int    idx = 0;

   datetime firstTime = 0, lastTime = 0;

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0) continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol) continue;
      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != CurrentMagic) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);

      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;

      double profit = HistoryDealGetDouble(deal, DEAL_PROFIT)
                    + HistoryDealGetDouble(deal, DEAL_SWAP)
                    + HistoryDealGetDouble(deal, DEAL_COMMISSION);

      double   vol    = HistoryDealGetDouble(deal, DEAL_VOLUME);
      double   price  = HistoryDealGetDouble(deal, DEAL_PRICE);
      long     dtype  = HistoryDealGetInteger(deal, DEAL_TYPE);
      long     reason = HistoryDealGetInteger(deal, DEAL_REASON);
      datetime ct     = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      ulong    pid    = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);

      if(firstTime == 0 || ct < firstTime) firstTime = ct;
      if(ct > lastTime)                    lastTime  = ct;

      exits++;
      cum += profit;

      if(profit > 0.0)
      {
         wins++;
         grossProfit += profit;
         if(profit > bestWin) bestWin = profit;
      }
      else
      {
         losses++;
         grossLoss += profit;
         if(profit < worstLoss) worstLoss = profit;
      }

      string rtxt;

      if(reason == DEAL_REASON_SL)      { rtxt = "StopLoss/Protection"; slExits++; }
      else if(reason == DEAL_REASON_TP) { rtxt = "TakeProfit";          tpExits++; }
      else                              { rtxt = "EA logic";            eaExits++; }

      if(handle == INVALID_HANDLE)
         continue;

      //--- pair with the entry deal
      datetime inTime  = 0;
      double   inPrice = 0.0;

      for(int k = 0; k < inCount; k++)
      {
         if(posId[k] == pid)
         {
            inTime  = posInTime[k];
            inPrice = posInPrice[k];
            break;
         }
      }

      // the closing deal type is the opposite of the position side
      string side = (dtype == DEAL_TYPE_BUY) ? "SELL" : "BUY";

      long minutesHeld = (inTime > 0) ? (long)((ct - inTime) / 60) : -1;

      idx++;

      FileWrite(handle, idx, IntegerToString((long)pid), side,
                (inTime > 0 ? TimeToString(inTime, TIME_DATE | TIME_MINUTES) : ""),
                (inPrice > 0.0 ? DoubleToString(inPrice, _Digits) : ""),
                TimeToString(ct, TIME_DATE | TIME_MINUTES),
                DoubleToString(price, _Digits),
                DoubleToString(vol, SymVolDigits),
                IntegerToString(minutesHeld),
                DoubleToString(profit, 2),
                DoubleToString(cum, 2),
                rtxt);
   }

   if(handle != INVALID_HANDLE)
      FileClose(handle);

   //--- summary
   double pf = (grossLoss != 0.0) ? grossProfit / MathAbs(grossLoss) : 0.0;
   double wr = (exits > 0)        ? 100.0 * wins / exits             : 0.0;

   Print("===== SimpleSMA18Bot v12 TRADE STUDY =====");
   PrintFormat("Symbol / timeframe      : %s %s  (magic %I64u)",
               _Symbol, EnumToString(WorkTF), CurrentMagic);
   PrintFormat("Covered range           : %s  ->  %s",
               (firstTime > 0 ? TimeToString(firstTime, TIME_DATE | TIME_MINUTES) : "n/a"),
               (lastTime  > 0 ? TimeToString(lastTime,  TIME_DATE | TIME_MINUTES) : "n/a"));
   PrintFormat("Positions opened        : %d", inCount);
   PrintFormat("Exits (incl. partials)  : %d", exits);
   PrintFormat("Wins / Losses           : %d / %d   (win%% %.1f)", wins, losses, wr);
   PrintFormat("Net profit              : %.2f", cum);
   PrintFormat("Gross profit / loss     : %.2f / %.2f   (PF %.2f)", grossProfit, grossLoss, pf);
   PrintFormat("Best win / Worst loss   : %.2f / %.2f", bestWin, worstLoss);
   Print("----- exit reason (from broker history) -----");
   PrintFormat("Closed by SL / Protection: %d", slExits);
   PrintFormat("Closed by TakeProfit     : %d", tpExits);
   PrintFormat("Closed by EA logic       : %d", eaExits);
   Print("----- EA counters (exact) -----");
   PrintFormat("Fast-MA cross exits      : %d", CntMA18Exit);
   PrintFormat("No-follow-through exits  : %d", CntNoFollow);
   PrintFormat("Points max-loss exits    : %d", CntMaxLoss);
   PrintFormat("Failed-breakout exits    : %d", CntFailedBO);
   PrintFormat("Emergency-filter exits   : %d", CntEmergency);
   PrintFormat("Partial closes           : %d", CntPartial);
   Print("----- settings fingerprint -----");
   PrintFormat("FollowMode=%s  MaxLossMode=%s  MaxLossPoints=%d",
               EnumToString(FollowMode), EnumToString(MaxLossMode), MaxLossPoints);
   PrintFormat("Protection=%s  ATRScaled=%s  MinStopPoints=%d  MaxPendingBars=%d",
               EnumToString(ProtectionMode),
               (UseATRScaledLevels ? "true" : "false"),
               MinStopPoints, MaxPendingBars);

   if(WriteTradeCSV)
      Print("CSV -> <Common>\\Files\\", fname);

   Print("==========================================");
}

//==================================================================
//                            ON TICK
//==================================================================

void OnTick()
{
   //=====================================================
   // H7: announce AutoTrading transitions instead of
   // silently doing nothing
   //=====================================================

   if(!TradingAllowedWithNotice())
      return;

   UpdateTrackedState();

   //=====================================================
   // H5 + C4: pending upkeep that must not wait for a bar
   //=====================================================

   ManagePendingIntrabar();

   //=====================================================
   // H6: daily / equity shutdown, evaluated EVERY tick and
   // regardless of whether a position is open
   //=====================================================

   bool halted = EnforceRiskShutdown();

   //=====================================================
   // ALWAYS MANAGE OPEN POSITIONS - BOTH SIDES
   //=====================================================

   ulong buyTicket  = FindMyPosition(POSITION_TYPE_BUY);
   ulong sellTicket = FindMyPosition(POSITION_TYPE_SELL);

   if(buyTicket  != 0) ManagePosition(buyTicket,  true);
   if(sellTicket != 0) ManagePosition(sellTicket, false);

   //=====================================================
   // EVERYTHING BELOW IS BAR-CLOSE ONLY
   //=====================================================

   if(!IsNewBar())
      return;

   if(!EnoughHistory())
   {
      Comment(Tag() + "warming up: need " +
              IntegerToString(TrendMAPeriod + SwingSearchBars + SwingStrength + 5) +
              " bars");
      return;
   }

   RuntimeSanityCheck();

   //--- C2: an orphan can appear or clear while we are running
   ScanForOrphans();

   //=====================================================
   // Pending order upkeep (bar-close part: ratchet + expiry)
   //=====================================================

   ulong buyStop  = FindMyOrder(ORDER_TYPE_BUY_STOP);
   ulong sellStop = FindMyOrder(ORDER_TYPE_SELL_STOP);

   if(buyStop != 0)
   {
      ManagePendingBuy(buyStop);
      return;
   }

   if(sellStop != 0)
   {
      ManagePendingSell(sellStop);
      return;
   }

   //=====================================================
   // No new setups while this instance holds a position
   //=====================================================

   if(FindMyAnyPosition() != 0)
      return;

   //=====================================================
   // Gates
   //=====================================================

   if(halted)
      return;                       // risk shutdown: no NEW setups

   if(!PassAccountGuards())
      return;

   if(!PassSpreadFilter())
   {
      Comment(Tag() + "spread too wide");
      return;
   }

   if(!IsTradingSession())
   {
      Comment(Tag() + "session filter: off hours");
      return;
   }

   if(!PassADXFilter())
   {
      Comment(Tag() + "ADX filter: weak trend");
      return;
   }

   Comment(Tag() + "armed");

   //=====================================================
   // New setups
   //=====================================================

   if(BuySignal())
   {
      PlaceBuyStop();
      return;
   }

   if(SellSignal())
   {
      PlaceSellStop();
      return;
   }
}
//+------------------------------------------------------------------+
