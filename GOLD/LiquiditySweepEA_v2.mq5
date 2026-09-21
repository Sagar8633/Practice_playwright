//+------------------------------------------------------------------+
//|                                             LiquiditySweepEA_v2  |
//|   Hardened rebuild of LiquiditySweepEA v1.10                     |
//|                                                                  |
//|   Same trading idea as v1: H4 liquidity sweep + reclaim.         |
//|   Rebuilt for capital protection, broker safety and              |
//|   backtest/live parity.                                          |
//+------------------------------------------------------------------+
#property copyright "Liquidity Sweep EA"
#property version   "2.00"
#property description "H4 liquidity sweep + reclaim, with hard risk controls."
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//==================================================================
//  ENUMS
//==================================================================
enum StopLossMode
{
   SL_MANIPULATION = 0,  // Behind the sweep (manipulation) extreme
   SL_REFERENCE    = 1   // Behind the reference candle extreme
};

enum ENUM_SIGNAL_MODE
{
   CLASSIC  = 0,         // Sweep + reclaim + close strength only
   FILTERED = 1          // All enabled filters
};

enum ENUM_SIZING_MODE
{
   SIZING_FIXED_LOT = 0, // Always LotSize
   SIZING_RISK_PCT  = 1  // Size from RiskPercent and stop distance
};

enum SignalType
{
   SIGNAL_NONE = 0,
   SIGNAL_BUY  = 1,
   SIGNAL_SELL = 2
};

enum ENUM_ENTRY_RESULT
{
   ENTRY_ABORT  = 0,     // Give up on this signal
   ENTRY_RETRY  = 1,     // Transient block, try again next tick
   ENTRY_OPENED = 2      // Position opened
};

//==================================================================
//  INPUTS
//==================================================================
input group "=== Market / timing ==="
input ENUM_TIMEFRAMES TradeTimeframe          = PERIOD_H4;
input int             PendingValiditySeconds  = 900;   // How long after bar open an entry may still fire
input bool            UseSessionFilter        = false;
input int             SessionStartHour        = 1;     // Server time, inclusive
input int             SessionEndHour          = 22;    // Server time, exclusive
input bool            BlockFridayLateEntries  = true;  // No new trades late Friday

input group "=== Signal: core structure ==="
input ENUM_SIGNAL_MODE SignalMode             = FILTERED;
input bool             StrictMode             = true;  // TRUE = every enabled filter is a hard gate
input double           MinimumSweepDistance   = 1.00;
input double           MinimumReclaimPercent  = 25.0;
input double           BuyCloseStrength       = 0.75;
input double           SellCloseStrength      = 0.25;

input group "=== Signal: candle quality filters ==="
input bool   UseLiquiditySweepFilter = true;
input bool   UseCloseInsideFilter    = true;
input bool   UseBodyFilter           = true;
input bool   UseWickFilter           = true;
input bool   UsePreviousRangeFilter  = true;
input bool   UseReclaimFilter        = true;
input bool   UseCandleSizeFilter     = true;   // v1 declared this but never used it
input double MinimumBodySize         = 1.00;
input double WickBodyRatio           = 1.5;
input double MinWickPercent          = 35.0;
input double MaximumRangeMultiplier  = 2.0;
input double MinimumCandleRange      = 1.00;
input double MaximumCandleRange      = 40.00;

input group "=== Signal: scoring (only used when StrictMode = false) ==="
input int ScoreSweepDistance   = 20;
input int ScoreBody            = 15;
input int ScoreWick            = 20;
input int ScoreCloseStrength   = 20;
input int ScoreRange           = 10;
input int ScoreReclaim         = 15;
input int MinimumSignalPercent = 75;   // % of the ENABLED weight, not an absolute score

input group "=== Entry quality ==="
input double MaximumEntryDistance = 2.00;  // Max distance from signal close to fill price
input bool   UseGapFilter         = true;  // v1 declared this but never used it
input double MaximumGap           = 0.50;  // Max gap between signal close and new bar open
input double MaxSpreadPrice       = 0.50;  // Reject entry if spread wider than this

input group "=== Stops and targets ==="
input StopLossMode StopMode         = SL_MANIPULATION;
input int          StopLossBuffer   = 20;    // In points
input double       MinStopDistance  = 1.00;  // Price units - rejects degenerate stops
input double       MaxStopDistance  = 15.00; // Price units
input double       RiskReward       = 2.5;
input bool         SpreadAwareStops = true;  // Widen SELL stop calc by the spread

input group "=== Position sizing ==="
input ENUM_SIZING_MODE SizingMode           = SIZING_RISK_PCT;
input double           LotSize              = 0.01;  // Used when SizingMode = SIZING_FIXED_LOT
input double           RiskPercent          = 0.50;  // % of lower of balance/equity per trade
input bool             AllowMinLotFallback  = false; // TRUE = trade min lot even if it exceeds RiskPercent

input group "=== Loss control (the circuit breakers) ==="
input bool   UseDailyLossLimit      = true;
input double MaxDailyLossPercent    = 2.0;   // Realized loss today, % of day-start balance
input bool   UseDailyDrawdownLimit  = true;
input double MaxDailyDrawdownPct    = 3.0;   // Equity drop from day-start equity
input bool   UseConsecutiveLossStop = true;
input int    MaxConsecutiveLosses   = 3;     // Pause for rest of day after N losses
input int    MaxTradesPerDay        = 2;     // 0 = unlimited

input group "=== Trade management ==="
input bool   UseBreakEven        = true;
input double BreakEvenTriggerR   = 1.0;   // Move to BE once this many R in profit
input int    BreakEvenOffsetPts  = 20;    // Points beyond entry, to cover costs
input bool   UsePartialClose     = true;
input double PartialCloseR       = 1.0;
input double PartialClosePercent = 50.0;
input bool   UseTrailingStop     = true;
input double TrailStartR         = 1.5;
input double TrailDistanceR      = 1.0;

input group "=== Execution / misc ==="
input ulong  MagicNumber           = 260706;
input ulong  SlippagePoints        = 50;
input bool   CloseOnOppositeSignal = true;
input bool   DebugMode             = true;

//==================================================================
//  GLOBALS
//==================================================================
datetime   g_lastBarTime     = 0;
datetime   g_pendingBarTime  = 0;
datetime   g_pendingTime     = 0;
SignalType g_pendingSignal   = SIGNAL_NONE;
bool       g_closeRequested  = false;

datetime g_dayStamp        = 0;
double   g_dayStartBalance = 0.0;
double   g_dayStartEquity  = 0.0;

ulong  g_posTicket      = 0;
double g_posEntry       = 0.0;
double g_posInitialRisk = 0.0;
bool   g_bePlaced       = false;
bool   g_partialDone    = false;

//==================================================================
//  SYMBOL / BROKER HELPERS
//==================================================================
double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tick <= 0.0)
      return NormalizeDouble(price, _Digits);

   return NormalizeDouble(MathRound(price / tick) * tick, _Digits);
}

double NormalizeVolume(double volume)
{
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(vstep <= 0.0)
      vstep = 0.01;

   double v = NormalizeDouble(MathFloor(volume / vstep) * vstep, 2);

   if(v > vmax)
      v = vmax;

   if(v < vmin)
      return 0.0;

   return v;
}

// Broker minimum distance between price and SL/TP, in price units.
double BrokerStopDistance()
{
   long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freez = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   long worst = (stops > freez) ? stops : freez;

   return (double)worst * _Point;
}

bool TradingEnvironmentOK(string &reason)
{
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      reason = "Terminal: AutoTrading disabled";
      return false;
   }

   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      reason = "EA: trading not allowed on this chart";
      return false;
   }

   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      reason = "Account: EA trading disabled by broker";
      return false;
   }

   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
   {
      reason = "Account: trading disabled";
      return false;
   }

   return true;
}

bool HistoryReady()
{
   if(Bars(_Symbol, TradeTimeframe) < 10)
      return false;

   if(iTime(_Symbol, TradeTimeframe, 2) == 0)
      return false;

   if(iHigh(_Symbol, TradeTimeframe, 2) <= 0.0 || iHigh(_Symbol, TradeTimeframe, 1) <= 0.0)
      return false;

   return true;
}

//==================================================================
//  POSITION HELPERS - all scoped to OUR magic and symbol
//==================================================================
ulong GetOurPositionTicket()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      return ticket;
   }

   return 0;
}

int GetOurPositionType()
{
   ulong ticket = GetOurPositionTicket();

   if(ticket == 0)
      return 0;

   if(!PositionSelectByTicket(ticket))
      return 0;

   long type = PositionGetInteger(POSITION_TYPE);

   if(type == POSITION_TYPE_BUY)
      return 1;

   if(type == POSITION_TYPE_SELL)
      return -1;

   return 0;
}

bool CloseOurPosition()
{
   ulong ticket = GetOurPositionTicket();

   if(ticket == 0)
      return true;

   if(trade.PositionClose(ticket))
      return true;

   Print("Close request failed. retcode=", trade.ResultRetcode(),
         " (", trade.ResultRetcodeDescription(), ")");

   return false;
}

//==================================================================
//  DAY STATE / LOSS CONTROL
//==================================================================
datetime TodayStart()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;

   return StructToTime(dt);
}

void RefreshDayState()
{
   datetime today = TodayStart();

   if(today == g_dayStamp)
      return;

   g_dayStamp        = today;
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dayStartEquity  = AccountInfoDouble(ACCOUNT_EQUITY);

   if(DebugMode)
      Print("New trading day. Start balance=", DoubleToString(g_dayStartBalance, 2),
            " equity=", DoubleToString(g_dayStartEquity, 2));
}

// Realized P/L today for our magic on this symbol.
double RealizedPLToday()
{
   double pl = 0.0;

   if(!HistorySelect(TodayStart(), TimeCurrent() + 60))
      return 0.0;

   int total = HistoryDealsTotal();

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0)
         continue;

      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
         continue;

      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicNumber)
         continue;

      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);

      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
         continue;

      pl += HistoryDealGetDouble(deal, DEAL_PROFIT)
          + HistoryDealGetDouble(deal, DEAL_SWAP)
          + HistoryDealGetDouble(deal, DEAL_COMMISSION);
   }

   return pl;
}

int TradesOpenedToday()
{
   int count = 0;

   if(!HistorySelect(TodayStart(), TimeCurrent() + 60))
      return 0;

   int total = HistoryDealsTotal();

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0)
         continue;

      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
         continue;

      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicNumber)
         continue;

      if(HistoryDealGetInteger(deal, DEAL_ENTRY) == DEAL_ENTRY_IN)
         count++;
   }

   return count;
}

int ConsecutiveLossesToday()
{
   int losses = 0;

   if(!HistorySelect(TodayStart(), TimeCurrent() + 60))
      return 0;

   int total = HistoryDealsTotal();

   for(int i = total - 1; i >= 0; i--)
   {
      ulong deal = HistoryDealGetTicket(i);

      if(deal == 0)
         continue;

      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
         continue;

      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicNumber)
         continue;

      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);

      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
         continue;

      double pl = HistoryDealGetDouble(deal, DEAL_PROFIT)
                + HistoryDealGetDouble(deal, DEAL_SWAP)
                + HistoryDealGetDouble(deal, DEAL_COMMISSION);

      if(pl < 0.0)
         losses++;
      else
         break;
   }

   return losses;
}

bool InSession()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return false;

   if(BlockFridayLateEntries && dt.day_of_week == 5 && dt.hour >= (SessionEndHour - 4))
      return false;

   if(!UseSessionFilter)
      return true;

   if(SessionStartHour <= SessionEndHour)
      return (dt.hour >= SessionStartHour && dt.hour < SessionEndHour);

   // Wrapping session (e.g. 22 -> 6)
   return (dt.hour >= SessionStartHour || dt.hour < SessionEndHour);
}

bool RiskGuardBlocked(string &reason)
{
   RefreshDayState();

   if(UseDailyLossLimit && g_dayStartBalance > 0.0)
   {
      double pl    = RealizedPLToday();
      double limit = -(g_dayStartBalance * MaxDailyLossPercent / 100.0);

      if(pl <= limit)
      {
         reason = StringFormat("Daily loss limit hit. Realized=%.2f limit=%.2f", pl, limit);
         return true;
      }
   }

   if(UseDailyDrawdownLimit && g_dayStartEquity > 0.0)
   {
      double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
      double drop = (g_dayStartEquity - eq) / g_dayStartEquity * 100.0;

      if(drop >= MaxDailyDrawdownPct)
      {
         reason = StringFormat("Daily drawdown limit hit. Drop=%.2f%% limit=%.2f%%",
                               drop, MaxDailyDrawdownPct);
         return true;
      }
   }

   if(UseConsecutiveLossStop && MaxConsecutiveLosses > 0)
   {
      int losses = ConsecutiveLossesToday();

      if(losses >= MaxConsecutiveLosses)
      {
         reason = StringFormat("Consecutive loss stop. %d losses today", losses);
         return true;
      }
   }

   if(MaxTradesPerDay > 0)
   {
      int trades = TradesOpenedToday();

      if(trades >= MaxTradesPerDay)
      {
         reason = StringFormat("Max trades per day reached (%d)", trades);
         return true;
      }
   }

   if(!InSession())
   {
      reason = "Outside allowed trading session";
      return true;
   }

   return false;
}

//==================================================================
//  SIGNAL
//==================================================================
void PrintSignalDebug(string label, double sweepDistance, double body,
                      double lowerWickPct, double upperWickPct,
                      double closePosition, double reclaimPct,
                      int score, int required, int totalWeight)
{
   if(!DebugMode)
      return;

   Print("========================================");
   Print(label, "   (", (StrictMode ? "STRICT" : "SCORED"), " / ",
         (SignalMode == CLASSIC ? "CLASSIC" : "FILTERED"), ")");
   Print("----------------------------------------");
   Print("Sweep Distance : ", DoubleToString(sweepDistance, 2));
   Print("Body Size      : ", DoubleToString(body, 2));
   Print("Lower Wick %   : ", DoubleToString(lowerWickPct, 1));
   Print("Upper Wick %   : ", DoubleToString(upperWickPct, 1));
   Print("Close Position : ", DoubleToString(closePosition, 2));
   Print("Reclaim %      : ", DoubleToString(reclaimPct, 1));
   Print("Score          : ", score, " / ", totalWeight, "  (required ", required, ")");
   Print("========================================");
}

// Evaluates one direction. Returns true if the setup qualifies.
bool EvaluateDirection(bool sweepOK, bool bodyOK, bool rangeOK, bool sizeOK,
                       bool wickOK, bool closeOK, bool reclaimOK,
                       int &score, int &required, int &totalWeight)
{
   bool useSweep   = UseLiquiditySweepFilter;
   bool useBody    = UseBodyFilter;
   bool useRange   = UsePreviousRangeFilter;
   bool useSize    = UseCandleSizeFilter;
   bool useWick    = UseWickFilter;
   bool useClose   = UseCloseInsideFilter;
   bool useReclaim = UseReclaimFilter;

   if(SignalMode == CLASSIC)
   {
      // Core structure only. These are genuinely switched OFF, so they no
      // longer contribute weight to either side of the threshold.
      useBody  = false;
      useRange = false;
      useSize  = false;
      useWick  = false;

      useSweep   = true;
      useClose   = true;
      useReclaim = true;
   }

   score       = 0;
   totalWeight = 0;
   required    = 0;

   // ---- Strict mode: every enabled filter is a hard gate (v1's original intent)
   if(StrictMode)
   {
      if(useSweep   && !sweepOK)   return false;
      if(useBody    && !bodyOK)    return false;
      if(useRange   && !rangeOK)   return false;
      if(useSize    && !sizeOK)    return false;
      if(useWick    && !wickOK)    return false;
      if(useClose   && !closeOK)   return false;
      if(useReclaim && !reclaimOK) return false;

      return true;
   }

   // ---- Scored mode: a disabled filter drops out of BOTH score and weight,
   //      so turning a filter off is neutral instead of making entry easier.
   if(useSweep)   { totalWeight += ScoreSweepDistance; if(sweepOK)   score += ScoreSweepDistance; }
   if(useBody)    { totalWeight += ScoreBody;          if(bodyOK)    score += ScoreBody; }
   if(useRange)   { totalWeight += ScoreRange;         if(rangeOK)   score += ScoreRange; }
   if(useWick)    { totalWeight += ScoreWick;          if(wickOK)    score += ScoreWick; }
   if(useClose)   { totalWeight += ScoreCloseStrength; if(closeOK)   score += ScoreCloseStrength; }
   if(useReclaim) { totalWeight += ScoreReclaim;       if(reclaimOK) score += ScoreReclaim; }

   // Candle size stays a hard gate - it is a sanity check, not a quality score.
   if(useSize && !sizeOK)
   {
      required = totalWeight + 1;
      return false;
   }

   if(totalWeight <= 0)
      return false;

   required = (int)MathCeil(totalWeight * (double)MinimumSignalPercent / 100.0);

   return (score >= required);
}

SignalType CheckSignal()
{
   double prevHigh = iHigh(_Symbol, TradeTimeframe, 2);
   double prevLow  = iLow (_Symbol, TradeTimeframe, 2);

   double sigHigh  = iHigh (_Symbol, TradeTimeframe, 1);
   double sigLow   = iLow  (_Symbol, TradeTimeframe, 1);
   double sigOpen  = iOpen (_Symbol, TradeTimeframe, 1);
   double sigClose = iClose(_Symbol, TradeTimeframe, 1);

   if(prevHigh <= 0.0 || sigHigh <= 0.0)
      return SIGNAL_NONE;

   double body          = MathAbs(sigClose - sigOpen);
   double candleRange   = sigHigh - sigLow;
   double previousRange = prevHigh - prevLow;

   if(candleRange <= 0.0)
      return SIGNAL_NONE;

   bool rangeAcceptable = true;

   if(previousRange > 0.0)
      rangeAcceptable = (candleRange <= previousRange * MaximumRangeMultiplier);

   bool sizeAcceptable = (candleRange >= MinimumCandleRange &&
                          candleRange <= MaximumCandleRange);

   double lowerWick = MathMin(sigOpen, sigClose) - sigLow;
   double upperWick = sigHigh - MathMax(sigOpen, sigClose);

   double lowerWickPct = (lowerWick / candleRange) * 100.0;
   double upperWickPct = (upperWick / candleRange) * 100.0;

   double closePosition = (sigClose - sigLow) / candleRange;

   bool brokeLow  = (sigLow  <= (prevLow  - MinimumSweepDistance));
   bool brokeHigh = (sigHigh >= (prevHigh + MinimumSweepDistance));

   // Sweeping both sides is not a directional signal.
   if(brokeLow && brokeHigh)
      return SIGNAL_NONE;

   if(!brokeLow && !brokeHigh)
      return SIGNAL_NONE;

   bool bodyLargeEnough = (body >= MinimumBodySize);

   double reclaimPct = 0.0;

   if(previousRange > 0.0)
   {
      if(brokeLow)
         reclaimPct = ((sigClose - prevLow) / previousRange) * 100.0;

      if(brokeHigh)
         reclaimPct = ((prevHigh - sigClose) / previousRange) * 100.0;
   }

   bool reclaimOK = (reclaimPct >= MinimumReclaimPercent);

   int score = 0, required = 0, totalWeight = 0;

   //---------------- BUY ----------------
   if(brokeLow && sigClose > prevLow)
   {
      double sweepDistance = prevLow - sigLow;

      bool sweepOK = (sweepDistance >= MinimumSweepDistance);

      bool wickOK = (body > 0.0 &&
                     (lowerWick / body) >= WickBodyRatio &&
                     lowerWickPct >= MinWickPercent);

      bool closeOK = (closePosition >= BuyCloseStrength);

      if(EvaluateDirection(sweepOK, bodyLargeEnough, rangeAcceptable,
                           sizeAcceptable, wickOK, closeOK, reclaimOK,
                           score, required, totalWeight))
      {
         PrintSignalDebug("BUY SIGNAL", sweepDistance, body, lowerWickPct,
                          upperWickPct, closePosition, reclaimPct,
                          score, required, totalWeight);
         return SIGNAL_BUY;
      }
   }

   //---------------- SELL ----------------
   if(brokeHigh && sigClose < prevHigh)
   {
      double sweepDistance = sigHigh - prevHigh;

      bool sweepOK = (sweepDistance >= MinimumSweepDistance);

      bool wickOK = (body > 0.0 &&
                     (upperWick / body) >= WickBodyRatio &&
                     upperWickPct >= MinWickPercent);

      bool closeOK = (closePosition <= SellCloseStrength);

      if(EvaluateDirection(sweepOK, bodyLargeEnough, rangeAcceptable,
                           sizeAcceptable, wickOK, closeOK, reclaimOK,
                           score, required, totalWeight))
      {
         PrintSignalDebug("SELL SIGNAL", sweepDistance, body, lowerWickPct,
                          upperWickPct, closePosition, reclaimPct,
                          score, required, totalWeight);
         return SIGNAL_SELL;
      }
   }

   return SIGNAL_NONE;
}

//==================================================================
//  SIZING
//==================================================================
double CalcLots(double riskDistance)
{
   if(SizingMode == SIZING_FIXED_LOT)
      return NormalizeVolume(LotSize);

   if(riskDistance <= 0.0)
      return 0.0;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0.0 || tickSize <= 0.0)
   {
      Print("Sizing fallback: tick value/size unavailable, using LotSize");
      return NormalizeVolume(LotSize);
   }

   // Conservative base: whichever of balance/equity is lower.
   double base = MathMin(AccountInfoDouble(ACCOUNT_BALANCE),
                         AccountInfoDouble(ACCOUNT_EQUITY));

   double riskMoney   = base * RiskPercent / 100.0;
   double moneyPerLot = (riskDistance / tickSize) * tickValue;

   if(moneyPerLot <= 0.0)
      return 0.0;

   double lots = NormalizeVolume(riskMoney / moneyPerLot);

   if(lots <= 0.0 && AllowMinLotFallback)
   {
      double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double cost = vmin * moneyPerLot;

      Print("Risk-based lot below broker minimum. Falling back to ", vmin,
            " which risks ", DoubleToString(cost, 2),
            " vs budget ", DoubleToString(riskMoney, 2));

      return NormalizeVolume(vmin);
   }

   return lots;
}

//==================================================================
//  ENTRY
//==================================================================
ENUM_ENTRY_RESULT TryOpen(bool isBuy)
{
   string blockReason = "";

   if(!TradingEnvironmentOK(blockReason))
   {
      Print("Entry blocked - ", blockReason);
      return ENTRY_RETRY;
   }

   if(RiskGuardBlocked(blockReason))
   {
      Print("Entry blocked - ", blockReason);
      return ENTRY_ABORT;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(ask <= 0.0 || bid <= 0.0)
      return ENTRY_RETRY;

   double spread = ask - bid;

   if(spread > MaxSpreadPrice)
   {
      Print("Entry blocked - spread ", DoubleToString(spread, 2),
            " exceeds MaxSpreadPrice ", DoubleToString(MaxSpreadPrice, 2));
      return ENTRY_RETRY;
   }

   double signalClose = iClose(_Symbol, TradeTimeframe, 1);
   double barOpen     = iOpen (_Symbol, TradeTimeframe, 0);
   double entryPrice  = isBuy ? ask : bid;

   if(UseGapFilter && barOpen > 0.0)
   {
      double gap = MathAbs(barOpen - signalClose);

      if(gap > MaximumGap)
      {
         Print("Entry blocked - opening gap ", DoubleToString(gap, 2),
               " exceeds MaximumGap ", DoubleToString(MaximumGap, 2));
         return ENTRY_ABORT;
      }
   }

   double entryDistance = MathAbs(entryPrice - signalClose);

   if(entryDistance > MaximumEntryDistance)
   {
      Print("Entry blocked - price ", DoubleToString(entryDistance, 2),
            " away from signal close (max ", DoubleToString(MaximumEntryDistance, 2), ")");
      return ENTRY_RETRY;
   }

   //---- Stop placement
   double manipulation = isBuy ? iLow (_Symbol, TradeTimeframe, 1)
                               : iHigh(_Symbol, TradeTimeframe, 1);

   double reference    = isBuy ? iLow (_Symbol, TradeTimeframe, 2)
                               : iHigh(_Symbol, TradeTimeframe, 2);

   double anchor = (StopMode == SL_MANIPULATION) ? manipulation : reference;
   double buffer = StopLossBuffer * _Point;

   // A SELL is closed at ask, so its true stop sits a spread higher.
   if(SpreadAwareStops && !isBuy)
      buffer += spread;

   double sl = NormalizePrice(isBuy ? (anchor - buffer) : (anchor + buffer));

   //---- Risk validation. v1 never checked for a non-positive stop distance,
   //     which on a gap-through produced an inverted TP.
   double risk = isBuy ? (entryPrice - sl) : (sl - entryPrice);

   if(risk <= 0.0)
   {
      Print("Entry aborted - stop is on the wrong side of price (risk=",
            DoubleToString(risk, 2), "). Price gapped through the level.");
      return ENTRY_ABORT;
   }

   if(risk < MinStopDistance)
   {
      Print("Entry aborted - stop distance ", DoubleToString(risk, 2),
            " below MinStopDistance ", DoubleToString(MinStopDistance, 2));
      return ENTRY_ABORT;
   }

   if(risk > MaxStopDistance)
   {
      Print("Entry aborted - stop distance ", DoubleToString(risk, 2),
            " exceeds MaxStopDistance ", DoubleToString(MaxStopDistance, 2));
      return ENTRY_ABORT;
   }

   double minDist = BrokerStopDistance();

   if(minDist > 0.0 && risk < minDist)
   {
      Print("Entry aborted - stop closer than broker minimum (",
            DoubleToString(minDist, 2), ")");
      return ENTRY_ABORT;
   }

   double tp = NormalizePrice(isBuy ? (entryPrice + risk * RiskReward)
                                    : (entryPrice - risk * RiskReward));

   if(minDist > 0.0 && MathAbs(tp - entryPrice) < minDist)
   {
      Print("Entry aborted - target closer than broker minimum");
      return ENTRY_ABORT;
   }

   //---- Sizing
   double lots = CalcLots(risk);

   if(lots <= 0.0)
   {
      Print("Entry aborted - computed lot size is 0 (risk budget too small for a ",
            DoubleToString(risk, 2), " stop). Raise RiskPercent or fund the account.");
      return ENTRY_ABORT;
   }

   //---- Margin check
   double marginNeeded = 0.0;
   ENUM_ORDER_TYPE otype = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;

   if(OrderCalcMargin(otype, _Symbol, lots, entryPrice, marginNeeded))
   {
      if(marginNeeded > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      {
         Print("Entry aborted - insufficient free margin. Need ",
               DoubleToString(marginNeeded, 2));
         return ENTRY_ABORT;
      }
   }

   //---- Send. price 0.0 = fill at current market, avoids stale-price rejects.
   bool ok = isBuy ? trade.Buy (lots, _Symbol, 0.0, sl, tp, "LS BUY")
                   : trade.Sell(lots, _Symbol, 0.0, sl, tp, "LS SELL");

   if(!ok)
   {
      Print((isBuy ? "BUY" : "SELL"), " FAILED. retcode=", trade.ResultRetcode(),
            " (", trade.ResultRetcodeDescription(), ")");
      return ENTRY_RETRY;
   }

   double filled = trade.ResultPrice();

   if(filled <= 0.0)
      filled = entryPrice;

   g_posTicket      = GetOurPositionTicket();
   g_posEntry       = filled;
   g_posInitialRisk = isBuy ? (filled - sl) : (sl - filled);
   g_bePlaced       = false;
   g_partialDone    = false;

   Print((isBuy ? "BUY" : "SELL"), " OPENED | lots=", DoubleToString(lots, 2),
         " entry=", DoubleToString(filled, _Digits),
         " SL=", DoubleToString(sl, _Digits),
         " TP=", DoubleToString(tp, _Digits),
         " risk=", DoubleToString(g_posInitialRisk, 2),
         " spread=", DoubleToString(spread, 2));

   return ENTRY_OPENED;
}

//==================================================================
//  TRADE MANAGEMENT - break-even, partial, trail
//==================================================================
void ManageOpenPosition()
{
   ulong ticket = GetOurPositionTicket();

   if(ticket == 0)
   {
      g_posTicket      = 0;
      g_posInitialRisk = 0.0;
      g_bePlaced       = false;
      g_partialDone    = false;
      return;
   }

   if(!PositionSelectByTicket(ticket))
      return;

   bool   isBuy  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   double volume = PositionGetDouble(POSITION_VOLUME);

   // Rebuild risk after a restart / reattach.
   if(g_posInitialRisk <= 0.0)
   {
      if(sl > 0.0)
         g_posInitialRisk = isBuy ? (entry - sl) : (sl - entry);

      if(g_posInitialRisk <= 0.0)
         return;

      g_posEntry  = entry;
      g_posTicket = ticket;
   }

   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                        : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   double moved     = isBuy ? (price - entry) : (entry - price);
   double rMultiple = moved / g_posInitialRisk;
   double minDist   = BrokerStopDistance();

   //---- Partial close
   if(UsePartialClose && !g_partialDone && rMultiple >= PartialCloseR)
   {
      double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

      if(vstep <= 0.0)
         vstep = 0.01;

      double closeVol = NormalizeDouble(
         MathFloor((volume * PartialClosePercent / 100.0) / vstep) * vstep, 2);

      if(closeVol >= vmin && (volume - closeVol) >= vmin)
      {
         if(trade.PositionClosePartial(ticket, closeVol))
         {
            g_partialDone = true;
            Print("Partial close ", DoubleToString(closeVol, 2), " lots at ",
                  DoubleToString(rMultiple, 2), "R");
         }
         else
         {
            Print("Partial close failed. retcode=", trade.ResultRetcode());
         }
      }
      else
      {
         // Not enough volume to split - skip permanently rather than retry every tick.
         g_partialDone = true;
      }

      if(!PositionSelectByTicket(ticket))
         return;

      volume = PositionGetDouble(POSITION_VOLUME);
      sl     = PositionGetDouble(POSITION_SL);
      tp     = PositionGetDouble(POSITION_TP);
   }

   //---- Break-even
   if(UseBreakEven && !g_bePlaced && rMultiple >= BreakEvenTriggerR)
   {
      double offset = BreakEvenOffsetPts * _Point;
      double beSL   = NormalizePrice(isBuy ? (entry + offset) : (entry - offset));

      bool improves = isBuy ? (beSL > sl) : (beSL < sl || sl == 0.0);
      bool legal    = (MathAbs(price - beSL) >= minDist);

      if(improves && legal)
      {
         if(trade.PositionModify(ticket, beSL, tp))
         {
            g_bePlaced = true;
            sl = beSL;
            Print("Stop moved to break-even+", BreakEvenOffsetPts, "pts at ",
                  DoubleToString(rMultiple, 2), "R");
         }
         else
         {
            Print("Break-even modify failed. retcode=", trade.ResultRetcode());
         }
      }
   }

   //---- Trailing stop
   if(UseTrailingStop && rMultiple >= TrailStartR)
   {
      double trailDist = g_posInitialRisk * TrailDistanceR;
      double newSL     = NormalizePrice(isBuy ? (price - trailDist) : (price + trailDist));

      bool improves = isBuy ? (newSL > sl) : (newSL < sl || sl == 0.0);
      bool legal    = (MathAbs(price - newSL) >= minDist);

      if(improves && legal)
      {
         if(!trade.PositionModify(ticket, newSL, tp))
            Print("Trail modify failed. retcode=", trade.ResultRetcode());
      }
   }
}

//==================================================================
//  PENDING ENTRY STATE MACHINE
//  v1 closed the opposite position and opened the new one in the same
//  tick. Live, PositionClose is asynchronous, so the new entry was
//  silently skipped by its own PositionExists() guard. Here the intent
//  is held and retried until the account is actually flat.
//==================================================================
void ClearPending()
{
   g_pendingSignal  = SIGNAL_NONE;
   g_pendingTime    = 0;
   g_closeRequested = false;
}

void ProcessPendingEntry()
{
   if(g_pendingSignal == SIGNAL_NONE)
      return;

   if(TimeCurrent() - g_pendingTime > PendingValiditySeconds)
   {
      Print("Pending signal expired without a fill.");
      ClearPending();
      return;
   }

   int p = GetOurPositionType();

   if((p ==  1 && g_pendingSignal == SIGNAL_BUY) ||
      (p == -1 && g_pendingSignal == SIGNAL_SELL))
   {
      ClearPending();   // already in the right direction
      return;
   }

   if(p != 0)
   {
      if(!CloseOnOppositeSignal)
      {
         Print("Opposite position open and CloseOnOppositeSignal is false - skipping.");
         ClearPending();
         return;
      }

      if(!g_closeRequested)
      {
         Print("Closing opposite position before reversing.");
         g_closeRequested = CloseOurPosition();
      }

      return;   // wait until genuinely flat, then retry next tick
   }

   g_closeRequested = false;

   ENUM_ENTRY_RESULT res = TryOpen(g_pendingSignal == SIGNAL_BUY);

   if(res == ENTRY_RETRY)
      return;

   ClearPending();
}

//==================================================================
//  BAR DETECTION
//==================================================================
bool IsNewSignalBar()
{
   datetime cur = iTime(_Symbol, TradeTimeframe, 0);

   if(cur == 0)
      return false;

   // First call after attach: adopt the current bar without trading it,
   // so the EA never fires on a signal candle that closed hours ago.
   if(g_lastBarTime == 0)
   {
      g_lastBarTime = cur;
      return false;
   }

   if(cur != g_lastBarTime)
   {
      g_lastBarTime = cur;
      return true;
   }

   return false;
}

//==================================================================
//  LIFECYCLE
//==================================================================
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(SlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   if(RiskReward <= 0.0)
   {
      Print("RiskReward must be > 0");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(MinStopDistance >= MaxStopDistance)
   {
      Print("MinStopDistance must be below MaxStopDistance");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(SizingMode == SIZING_RISK_PCT && RiskPercent <= 0.0)
   {
      Print("RiskPercent must be > 0 when using risk-based sizing");
      return INIT_PARAMETERS_INCORRECT;
   }

   RefreshDayState();

   // Adopt an existing position (e.g. after a terminal restart)
   ulong ticket = GetOurPositionTicket();

   if(ticket > 0 && PositionSelectByTicket(ticket))
   {
      g_posTicket = ticket;
      g_posEntry  = PositionGetDouble(POSITION_PRICE_OPEN);

      double sl  = PositionGetDouble(POSITION_SL);
      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);

      if(sl > 0.0)
         g_posInitialRisk = isBuy ? (g_posEntry - sl) : (sl - g_posEntry);

      Print("Adopted existing position ", ticket,
            " risk=", DoubleToString(g_posInitialRisk, 2));
   }

   Print("Liquidity Sweep EA v2 started on ", _Symbol,
         " TF=", EnumToString(TradeTimeframe),
         " mode=", (StrictMode ? "STRICT" : "SCORED"),
         " sizing=", (SizingMode == SIZING_RISK_PCT ? "RISK%" : "FIXED"));

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Print("Liquidity Sweep EA v2 removed. reason=", reason);
}

void OnTick()
{
   // Runs every tick - management must be responsive.
   ManageOpenPosition();
   ProcessPendingEntry();

   if(!IsNewSignalBar())
      return;   // no per-tick logging: v1 printed on every tick

   if(!HistoryReady())
   {
      Print("History not ready for ", _Symbol, " - skipping this bar.");
      return;
   }

   datetime signalBar = iTime(_Symbol, TradeTimeframe, 1);

   if(signalBar == g_pendingBarTime)
      return;

   SignalType signal = CheckSignal();

   if(signal == SIGNAL_NONE)
   {
      if(DebugMode)
         Print("No signal on bar ", TimeToString(signalBar));
      return;
   }

   string reason = "";

   if(RiskGuardBlocked(reason))
   {
      Print("Signal found but trading is halted - ", reason);
      return;
   }

   g_pendingSignal  = signal;
   g_pendingBarTime = signalBar;
   g_pendingTime    = TimeCurrent();
   g_closeRequested = false;

   ProcessPendingEntry();
}
//+------------------------------------------------------------------+
