//+------------------------------------------------------------------+
//|                                           SmaCrossPullbackEA.mq5 |
//|                                                                  |
//|  20 SMA / 200 SMA crossover + pullback + confirmation strategy.   |
//|                                                                  |
//|  Sequence enforced exactly as specified:                          |
//|     crossover -> pullback to 20 SMA -> confirmation candle        |
//|     -> stop entry beyond the confirmation candle -> 1:2 RR        |
//|                                                                  |
//|  A crossover alone NEVER produces an entry.                       |
//+------------------------------------------------------------------+
#property copyright "SMA Cross Pullback"
#property version   "1.00"
#property description "20/200 SMA crossover with mandatory pullback and confirmation. 1:2 RR."
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//==================================================================
//  ENUMS
//==================================================================
enum ENUM_SL_MODE
{
   SL_CONFIRMATION_CANDLE = 0, // Beyond the confirmation candle's far side
   SL_PULLBACK_SWING      = 1, // Beyond the pullback swing extreme
   SL_SMA200              = 2, // Beyond the 200 SMA
   SL_FIXED_POINTS        = 3  // Fixed distance in points
};

enum ENUM_SIZING_MODE
{
   SIZING_FIXED_LOT = 0, // Always LotSize
   SIZING_RISK_PCT  = 1  // Size from RiskPercent and stop distance
};

enum ENUM_SETUP_STATE
{
   STATE_IDLE      = 0, // No crossover in play
   STATE_CROSSED   = 1, // Crossover seen, waiting for pullback
   STATE_PULLBACK  = 2, // Pullback done, waiting for confirmation
   STATE_ARMED     = 3  // Confirmation done, stop order working
};

//==================================================================
//  INPUTS
//==================================================================
input group "=== Chart / indicators ==="
input ENUM_TIMEFRAMES WorkTimeframe   = PERIOD_M5;
input int             FastPeriod      = 20;
input int             SlowPeriod      = 200;
input ENUM_MA_METHOD  MaMethod        = MODE_SMA;
input ENUM_APPLIED_PRICE MaPrice      = PRICE_CLOSE;

input group "=== Sequence rules ==="
input int    MaxBarsAfterCross   = 60;   // Setup expires this many bars after the crossover
input double PullbackTolerance   = 0.0;  // Extra distance (price units) that still counts as reaching the 20 SMA
input bool   RequirePullbackTouch = true; // TRUE: bar must actually reach the 20 SMA; FALSE: tolerance only
input bool   ConfirmNeedsCloseBeyondFast = true; // Confirmation candle must also close on the trade side of the 20 SMA
input bool   InvalidateOnOppositeCross   = true; // An opposite crossover cancels the whole setup
input bool   AllowReArmAfterLoss         = true; // Same crossover may produce another setup after a stop-out

input group "=== Entry ==="
input int  EntryBufferPoints   = 10;  // Stop order this far beyond the confirmation candle
input int  PendingExpiryBars   = 6;   // Delete the unfilled stop order after this many bars
input bool OnePositionAtATime  = true;

input group "=== Stop loss (NOT defined by the source spec - choose one) ==="
input ENUM_SL_MODE StopLossMode    = SL_CONFIRMATION_CANDLE;
input int          SLBufferPoints  = 10;   // Extra distance beyond the chosen anchor
input int          FixedSLPoints   = 300;  // Used only when StopLossMode = SL_FIXED_POINTS
input double       MinStopDistance = 0.0;  // Price units. 0 = no minimum
input double       MaxStopDistance = 0.0;  // Price units. 0 = no maximum

input group "=== Target ==="
input double RiskReward = 2.0;  // 1:2 as specified

input group "=== Position sizing ==="
input ENUM_SIZING_MODE SizingMode          = SIZING_FIXED_LOT;
input double           LotSize             = 0.01;
input double           RiskPercent         = 0.50;
input bool             AllowMinLotFallback = false;

input group "=== Loss control ==="
input bool   UseDailyLossLimit      = false;
input double MaxDailyLossPercent    = 2.0;
input bool   UseConsecutiveLossStop = false;
input int    MaxConsecutiveLosses   = 3;
input int    MaxTradesPerDay        = 0;    // 0 = unlimited

input group "=== Session ==="
input bool UseSessionFilter   = false;
input int  SessionStartHour   = 0;   // Server time, inclusive
input int  SessionEndHour     = 24;  // Server time, exclusive
input bool CloseAtSessionEnd  = false; // Intraday: flatten when the session closes

input group "=== Execution ==="
input ulong MagicNumber    = 202020;
input ulong SlippagePoints = 30;
input double MaxSpreadPrice = 0.0;  // 0 = no spread gate
input bool  ShowPanel      = true;
input bool  DebugMode      = true;

//==================================================================
//  GLOBALS
//==================================================================
int g_hFast = INVALID_HANDLE;
int g_hSlow = INVALID_HANDLE;

datetime g_lastBarTime = 0;

ENUM_SETUP_STATE g_state   = STATE_IDLE;
int      g_dir             = 0;    // 1 = long setup, -1 = short setup
datetime g_crossBarTime    = 0;
int      g_barsSinceCross  = 0;

double   g_pullbackExtreme = 0.0;  // lowest low (long) / highest high (short) during pullback
double   g_confHigh        = 0.0;
double   g_confLow         = 0.0;
datetime g_confBarTime     = 0;

ulong    g_pendingTicket   = 0;
int      g_pendingAgeBars  = 0;

// Panel values
double   g_panelEntry = 0.0, g_panelSL = 0.0, g_panelTP = 0.0;
string   g_panelStatus = "NO TRADE";

datetime g_dayStamp        = 0;
double   g_dayStartBalance = 0.0;

//==================================================================
//  SMALL HELPERS
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

   double v = NormalizeDouble(MathFloor(volume / vstep + 1e-8) * vstep, 2);

   if(v > vmax)
      v = vmax;

   if(v < vmin)
      return 0.0;

   return v;
}

double BrokerStopDistance()
{
   long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freez = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   long worst = (stops > freez) ? stops : freez;

   return (double)worst * _Point;
}

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
}

bool InSession()
{
   if(!UseSessionFilter)
      return true;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   if(SessionStartHour <= SessionEndHour)
      return (dt.hour >= SessionStartHour && dt.hour < SessionEndHour);

   return (dt.hour >= SessionStartHour || dt.hour < SessionEndHour);
}

//==================================================================
//  POSITION / ORDER HELPERS - scoped to our magic and symbol
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

ulong GetOurPendingTicket()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);

      if(ticket == 0)
         continue;

      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;

      if((ulong)OrderGetInteger(ORDER_MAGIC) != MagicNumber)
         continue;

      return ticket;
   }

   return 0;
}

void CancelOurPending()
{
   ulong ticket = GetOurPendingTicket();

   if(ticket == 0)
   {
      g_pendingTicket = 0;
      return;
   }

   if(trade.OrderDelete(ticket))
   {
      if(DebugMode)
         Print("Pending order ", ticket, " deleted.");
   }
   else
   {
      Print("Pending delete failed. retcode=", trade.ResultRetcode(),
            " (", trade.ResultRetcodeDescription(), ")");
   }

   g_pendingTicket  = 0;
   g_pendingAgeBars = 0;
}

//==================================================================
//  LOSS CONTROL
//==================================================================
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

// Aggregated by position so a partial exit cannot reset the streak.
int ConsecutiveLossesToday()
{
   if(!HistorySelect(TodayStart(), TimeCurrent() + 60))
      return 0;

   ulong    ids[];
   double   pls[];
   datetime closed[];
   int      n = 0;

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

      ulong  posid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      double pl    = HistoryDealGetDouble(deal, DEAL_PROFIT)
                   + HistoryDealGetDouble(deal, DEAL_SWAP)
                   + HistoryDealGetDouble(deal, DEAL_COMMISSION);
      datetime t   = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);

      int found = -1;

      for(int k = 0; k < n; k++)
      {
         if(ids[k] == posid)
         {
            found = k;
            break;
         }
      }

      if(found >= 0)
      {
         pls[found] += pl;

         if(t > closed[found])
            closed[found] = t;
      }
      else
      {
         ArrayResize(ids, n + 1);
         ArrayResize(pls, n + 1);
         ArrayResize(closed, n + 1);

         ids[n]    = posid;
         pls[n]    = pl;
         closed[n] = t;
         n++;
      }
   }

   if(n <= 0)
      return 0;

   bool used[];
   ArrayResize(used, n);

   for(int k = 0; k < n; k++)
      used[k] = false;

   int losses = 0;

   for(int step = 0; step < n; step++)
   {
      int newest = -1;

      for(int k = 0; k < n; k++)
      {
         if(used[k])
            continue;

         if(newest < 0 || closed[k] > closed[newest])
            newest = k;
      }

      if(newest < 0)
         break;

      used[newest] = true;

      if(pls[newest] < 0.0)
         losses++;
      else
         break;
   }

   return losses;
}

bool TradingHalted(string &reason)
{
   RefreshDayState();

   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      reason = "AutoTrading disabled";
      return true;
   }

   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      reason = "EA trading not allowed";
      return true;
   }

   if(UseDailyLossLimit && g_dayStartBalance > 0.0)
   {
      double pl    = RealizedPLToday();
      double limit = -(g_dayStartBalance * MaxDailyLossPercent / 100.0);

      if(pl <= limit)
      {
         reason = StringFormat("Daily loss limit hit (%.2f)", pl);
         return true;
      }
   }

   if(UseConsecutiveLossStop && MaxConsecutiveLosses > 0)
   {
      int losses = ConsecutiveLossesToday();

      if(losses >= MaxConsecutiveLosses)
      {
         reason = StringFormat("Consecutive loss stop (%d)", losses);
         return true;
      }
   }

   if(MaxTradesPerDay > 0 && TradesOpenedToday() >= MaxTradesPerDay)
   {
      reason = "Max trades per day reached";
      return true;
   }

   if(!InSession())
   {
      reason = "Outside session";
      return true;
   }

   return false;
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
      return NormalizeVolume(LotSize);

   double base = MathMin(AccountInfoDouble(ACCOUNT_BALANCE),
                         AccountInfoDouble(ACCOUNT_EQUITY));

   double riskMoney   = base * RiskPercent / 100.0;
   double moneyPerLot = (riskDistance / tickSize) * tickValue;

   if(moneyPerLot <= 0.0)
      return 0.0;

   double lots = NormalizeVolume(riskMoney / moneyPerLot);

   if(lots <= 0.0 && AllowMinLotFallback)
      return NormalizeVolume(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));

   return lots;
}

//==================================================================
//  INDICATOR ACCESS
//==================================================================
bool ReadMAs(double &fast[], double &slow[], int count)
{
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);

   if(CopyBuffer(g_hFast, 0, 0, count, fast) != count)
      return false;

   if(CopyBuffer(g_hSlow, 0, 0, count, slow) != count)
      return false;

   return true;
}

//==================================================================
//  STATE MACHINE RESET
//==================================================================
void ResetSetup(string why)
{
   if(DebugMode && g_state != STATE_IDLE)
      Print("Setup reset: ", why);

   if(g_state == STATE_ARMED)
      CancelOurPending();

   g_state           = STATE_IDLE;
   g_dir             = 0;
   g_crossBarTime    = 0;
   g_barsSinceCross  = 0;
   g_pullbackExtreme = 0.0;
   g_confHigh        = 0.0;
   g_confLow         = 0.0;
   g_confBarTime     = 0;
   g_pendingAgeBars  = 0;

   g_panelEntry  = 0.0;
   g_panelSL     = 0.0;
   g_panelTP     = 0.0;
}

//==================================================================
//  STOP LOSS
//  The source specification does NOT define an SL rule. Rather than
//  invent one silently, StopLossMode exposes the candidates.
//==================================================================
double ComputeStopLoss(bool isLong, double entry)
{
   double buffer = SLBufferPoints * _Point;
   double anchor = 0.0;

   switch(StopLossMode)
   {
      case SL_CONFIRMATION_CANDLE:
         anchor = isLong ? g_confLow : g_confHigh;
         break;

      case SL_PULLBACK_SWING:
         anchor = g_pullbackExtreme;
         break;

      case SL_SMA200:
      {
         double slow[];
         ArraySetAsSeries(slow, true);

         if(CopyBuffer(g_hSlow, 0, 0, 2, slow) != 2)
            return 0.0;

         anchor = slow[1];
         break;
      }

      case SL_FIXED_POINTS:
         return NormalizePrice(isLong ? (entry - FixedSLPoints * _Point)
                                      : (entry + FixedSLPoints * _Point));
   }

   if(anchor <= 0.0)
      return 0.0;

   return NormalizePrice(isLong ? (anchor - buffer) : (anchor + buffer));
}

//==================================================================
//  PLACE THE STOP ORDER
//==================================================================
bool ArmEntry(bool isLong)
{
   string reason = "";

   if(TradingHalted(reason))
   {
      if(DebugMode)
         Print("Not arming - ", reason);
      return false;
   }

   if(OnePositionAtATime && GetOurPositionTicket() != 0)
   {
      if(DebugMode)
         Print("Not arming - a position is already open.");
      return false;
   }

   if(MaxSpreadPrice > 0.0)
   {
      double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                    - SymbolInfoDouble(_Symbol, SYMBOL_BID);

      if(spread > MaxSpreadPrice)
      {
         if(DebugMode)
            Print("Not arming - spread ", DoubleToString(spread, _Digits), " too wide.");
         return false;
      }
   }

   double buffer = EntryBufferPoints * _Point;

   double entry = NormalizePrice(isLong ? (g_confHigh + buffer)
                                        : (g_confLow  - buffer));

   double sl = ComputeStopLoss(isLong, entry);

   if(sl <= 0.0)
   {
      Print("Not arming - stop loss could not be computed.");
      return false;
   }

   double risk = isLong ? (entry - sl) : (sl - entry);

   if(risk <= 0.0)
   {
      Print("Not arming - stop is on the wrong side of entry (risk=",
            DoubleToString(risk, _Digits), ").");
      return false;
   }

   if(MinStopDistance > 0.0 && risk < MinStopDistance)
   {
      if(DebugMode)
         Print("Not arming - stop distance ", DoubleToString(risk, _Digits), " below minimum.");
      return false;
   }

   if(MaxStopDistance > 0.0 && risk > MaxStopDistance)
   {
      if(DebugMode)
         Print("Not arming - stop distance ", DoubleToString(risk, _Digits), " above maximum.");
      return false;
   }

   double minDist = BrokerStopDistance();
   double ref     = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                           : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // A stop order must sit beyond the market by at least the broker distance.
   if(minDist > 0.0 && MathAbs(entry - ref) < minDist)
   {
      if(DebugMode)
         Print("Not arming - entry too close to market for a stop order.");
      return false;
   }

   if(minDist > 0.0 && risk < minDist)
   {
      if(DebugMode)
         Print("Not arming - stop closer than the broker minimum.");
      return false;
   }

   double tp = NormalizePrice(isLong ? (entry + risk * RiskReward)
                                     : (entry - risk * RiskReward));

   double lots = CalcLots(risk);

   if(lots <= 0.0)
   {
      Print("Not arming - computed lot size is 0 for a ",
            DoubleToString(risk, _Digits), " stop.");
      return false;
   }

   datetime expiry = 0;
   ENUM_ORDER_TYPE_TIME tt = ORDER_TIME_GTC;

   bool ok = isLong
      ? trade.BuyStop (lots, entry, _Symbol, sl, tp, tt, expiry, "SMAX LONG")
      : trade.SellStop(lots, entry, _Symbol, sl, tp, tt, expiry, "SMAX SHORT");

   if(!ok)
   {
      Print((isLong ? "BuyStop" : "SellStop"), " failed. retcode=", trade.ResultRetcode(),
            " (", trade.ResultRetcodeDescription(), ")");
      return false;
   }

   g_pendingTicket  = GetOurPendingTicket();
   g_pendingAgeBars = 0;

   g_panelEntry = entry;
   g_panelSL    = sl;
   g_panelTP    = tp;

   Print((isLong ? "LONG" : "SHORT"), " armed | entry=", DoubleToString(entry, _Digits),
         " SL=", DoubleToString(sl, _Digits),
         " TP=", DoubleToString(tp, _Digits),
         " risk=", DoubleToString(risk, _Digits),
         " lots=", DoubleToString(lots, 2));

   return true;
}

//==================================================================
//  THE SEQUENCE
//  Evaluated once per closed bar. Bar 1 is the last closed bar.
//==================================================================
void EvaluateSequence()
{
   double fast[], slow[];

   if(!ReadMAs(fast, slow, 4))
   {
      if(DebugMode)
         Print("Indicator data not ready.");
      return;
   }

   double f1 = fast[1], f2 = fast[2];
   double s1 = slow[1], s2 = slow[2];

   double high1 = iHigh (_Symbol, WorkTimeframe, 1);
   double low1  = iLow  (_Symbol, WorkTimeframe, 1);
   double open1 = iOpen (_Symbol, WorkTimeframe, 1);
   double close1= iClose(_Symbol, WorkTimeframe, 1);

   if(high1 <= 0.0 || f1 <= 0.0 || s1 <= 0.0)
      return;

   //---------------- Step 2: crossover detection -------------------
   bool bullCross = (f2 <= s2 && f1 > s1);
   bool bearCross = (f2 >= s2 && f1 < s1);

   if(bullCross || bearCross)
   {
      int newDir = bullCross ? 1 : -1;

      if(g_state != STATE_IDLE && g_dir != newDir && InvalidateOnOppositeCross)
         ResetSetup("opposite crossover");
      else if(g_state != STATE_IDLE)
         ResetSetup("fresh crossover");

      g_dir            = newDir;
      g_state          = STATE_CROSSED;
      g_crossBarTime   = iTime(_Symbol, WorkTimeframe, 1);
      g_barsSinceCross = 0;

      g_pullbackExtreme = newDir == 1 ? low1 : high1;

      Print(bullCross ? "Bullish crossover (20 above 200). Waiting for pullback."
                      : "Bearish crossover (20 below 200). Waiting for pullback.");
      return;
   }

   if(g_state == STATE_IDLE)
      return;

   g_barsSinceCross++;

   if(MaxBarsAfterCross > 0 && g_barsSinceCross > MaxBarsAfterCross)
   {
      ResetSetup("setup expired without completing the sequence");
      return;
   }

   //---- Invalidate if the MAs have reverted while we waited
   if(InvalidateOnOppositeCross)
   {
      if(g_dir == 1 && f1 < s1)
      {
         ResetSetup("20 SMA fell back below the 200 SMA");
         return;
      }

      if(g_dir == -1 && f1 > s1)
      {
         ResetSetup("20 SMA rose back above the 200 SMA");
         return;
      }
   }

   bool isLong = (g_dir == 1);

   //---------------- Step 4/5: pullback toward the 20 SMA ----------
   if(g_state == STATE_CROSSED)
   {
      bool reached = false;

      if(isLong)
      {
         // Touch required: the bar's low must actually reach the 20 SMA.
         // Otherwise coming within PullbackTolerance of it is enough.
         reached = RequirePullbackTouch ? (low1 <= f1)
                                        : (low1 <= f1 + PullbackTolerance);

         if(low1 < g_pullbackExtreme || g_pullbackExtreme <= 0.0)
            g_pullbackExtreme = low1;
      }
      else
      {
         reached = RequirePullbackTouch ? (high1 >= f1)
                                        : (high1 >= f1 - PullbackTolerance);

         if(high1 > g_pullbackExtreme || g_pullbackExtreme <= 0.0)
            g_pullbackExtreme = high1;
      }

      if(reached)
      {
         g_state = STATE_PULLBACK;

         // Seed the swing with this bar's extreme.
         g_pullbackExtreme = isLong ? low1 : high1;

         if(DebugMode)
            Print("Pullback to the 20 SMA confirmed. Waiting for a confirmation candle.");
      }

      return;
   }

   //---------------- Step 6: confirmation candle ------------------
   if(g_state == STATE_PULLBACK)
   {
      // Keep tracking the swing extreme while we wait.
      if(isLong)
      {
         if(low1 < g_pullbackExtreme)
            g_pullbackExtreme = low1;
      }
      else
      {
         if(high1 > g_pullbackExtreme)
            g_pullbackExtreme = high1;
      }

      bool directional = isLong ? (close1 > open1) : (close1 < open1);

      bool beyondFast = true;

      if(ConfirmNeedsCloseBeyondFast)
         beyondFast = isLong ? (close1 > f1) : (close1 < f1);

      if(directional && beyondFast)
      {
         g_confHigh    = high1;
         g_confLow     = low1;
         g_confBarTime = iTime(_Symbol, WorkTimeframe, 1);

         if(ArmEntry(isLong))
         {
            g_state = STATE_ARMED;
            Print("Confirmation candle accepted. Stop order working.");
         }
         else
         {
            // Stay in PULLBACK and let a later candle confirm instead.
            if(DebugMode)
               Print("Confirmation seen but the order could not be armed. Still waiting.");
         }
      }

      return;
   }

   //---------------- Armed: age out an unfilled order --------------
   if(g_state == STATE_ARMED)
   {
      if(GetOurPositionTicket() != 0)
      {
         // Filled. The SL/TP ride with the position; the setup is done.
         ResetSetup("entry filled");
         return;
      }

      if(GetOurPendingTicket() == 0)
      {
         ResetSetup("pending order no longer exists");
         return;
      }

      g_pendingAgeBars++;

      if(PendingExpiryBars > 0 && g_pendingAgeBars > PendingExpiryBars)
      {
         ResetSetup("stop order expired unfilled");

         if(AllowReArmAfterLoss)
         {
            // The crossover itself may still be valid; resume hunting a pullback.
            g_dir            = isLong ? 1 : -1;
            g_state          = STATE_CROSSED;
            g_barsSinceCross = 0;
            g_crossBarTime   = iTime(_Symbol, WorkTimeframe, 1);
         }
      }
   }
}

//==================================================================
//  STATUS PANEL - the Step 9 readout from the specification
//==================================================================
void UpdatePanel()
{
   if(!ShowPanel)
      return;

   double fast[], slow[];

   if(!ReadMAs(fast, slow, 3))
      return;

   string dir   = (g_dir == 1) ? "LONG" : (g_dir == -1 ? "SHORT" : "-");
   string cross = (g_dir == 1) ? "Bullish" : (g_dir == -1 ? "Bearish" : "None");

   string pull = (g_state == STATE_PULLBACK || g_state == STATE_ARMED) ? "YES" : "NO";
   string conf = (g_state == STATE_ARMED) ? "YES" : "NO";

   string status;

   if(GetOurPositionTicket() != 0)
      status = "IN TRADE";
   else if(g_state == STATE_ARMED)
      status = "ENTER";
   else if(g_state == STATE_CROSSED || g_state == STATE_PULLBACK)
      status = "WAIT";
   else
      status = "NO TRADE";

   string note = "";

   if(g_state == STATE_IDLE)
      note = "NO TRADE - No valid SMA crossover.";
   else if(g_state == STATE_CROSSED)
      note = "WAIT - Waiting for pullback to 20 SMA.";
   else if(g_state == STATE_PULLBACK)
      note = "WAIT - Waiting for confirmation candle.";
   else if(g_state == STATE_ARMED)
      note = "ENTER - Stop order working.";

   string txt = StringFormat(
      "20/200 SMA CROSSOVER PULLBACK\n"
      "-------------------------------\n"
      "Direction    : %s\n"
      "Timeframe    : %s\n"
      "20 SMA       : %s\n"
      "200 SMA      : %s\n"
      "Crossover    : %s\n"
      "Pullback     : %s\n"
      "Confirmation : %s\n"
      "Entry        : %s\n"
      "Stop Loss    : %s\n"
      "Target       : %s\n"
      "Risk:Reward  : 1:%s\n"
      "Trade Status : %s\n"
      "-------------------------------\n"
      "%s",
      dir,
      EnumToString(WorkTimeframe),
      DoubleToString(fast[1], _Digits),
      DoubleToString(slow[1], _Digits),
      cross,
      pull,
      conf,
      g_panelEntry > 0.0 ? DoubleToString(g_panelEntry, _Digits) : "-",
      g_panelSL    > 0.0 ? DoubleToString(g_panelSL,    _Digits) : "-",
      g_panelTP    > 0.0 ? DoubleToString(g_panelTP,    _Digits) : "-",
      DoubleToString(RiskReward, 1),
      status,
      note);

   Comment(txt);
}

//==================================================================
//  BAR DETECTION
//==================================================================
bool IsNewBar()
{
   datetime cur = iTime(_Symbol, WorkTimeframe, 0);

   if(cur == 0)
      return false;

   if(g_lastBarTime == 0)
   {
      g_lastBarTime = cur;
      return false;   // never act on the bar we attached to
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
   if(FastPeriod >= SlowPeriod)
   {
      Print("FastPeriod must be below SlowPeriod.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(RiskReward <= 0.0)
   {
      Print("RiskReward must be above 0.");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_hFast = iMA(_Symbol, WorkTimeframe, FastPeriod, 0, MaMethod, MaPrice);
   g_hSlow = iMA(_Symbol, WorkTimeframe, SlowPeriod, 0, MaMethod, MaPrice);

   if(g_hFast == INVALID_HANDLE || g_hSlow == INVALID_HANDLE)
   {
      Print("Failed to create the moving average handles.");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(SlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   RefreshDayState();
   ResetSetup("init");

   Print("SMA Cross Pullback EA started on ", _Symbol,
         " TF=", EnumToString(WorkTimeframe),
         " ", FastPeriod, "/", SlowPeriod,
         " SL mode=", EnumToString(StopLossMode),
         " RR=1:", DoubleToString(RiskReward, 1));

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hFast != INVALID_HANDLE)
      IndicatorRelease(g_hFast);

   if(g_hSlow != INVALID_HANDLE)
      IndicatorRelease(g_hSlow);

   Comment("");

   Print("SMA Cross Pullback EA removed. reason=", reason);
}

void OnTick()
{
   // Intraday flatten, checked on every tick so it is not missed between bars.
   if(CloseAtSessionEnd && UseSessionFilter && !InSession())
   {
      ulong t = GetOurPositionTicket();

      if(t != 0)
      {
         Print("Session ended - flattening.");
         trade.PositionClose(t);
      }

      if(GetOurPendingTicket() != 0)
         CancelOurPending();
   }

   if(!IsNewBar())
   {
      UpdatePanel();
      return;
   }

   EvaluateSequence();
   UpdatePanel();
}
//+------------------------------------------------------------------+
