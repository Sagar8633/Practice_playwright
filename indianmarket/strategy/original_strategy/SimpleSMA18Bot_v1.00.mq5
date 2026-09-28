//+------------------------------------------------------------------+
//|                                               SimpleSMA18Bot.mq5 |
//|                     Version 1.00                                 |
//+------------------------------------------------------------------+


#include <Trade/Trade.mqh>

CTrade trade;

//======================== INPUTS ===================================

input ENUM_TIMEFRAMES TimeFrame = PERIOD_D1;

input double LotSize = 0.01;

input int FastMAPeriod = 18;
input int TrendMAPeriod = 200;
input int VolumeMAPeriod = 20;

input int SwingStrength = 2;
input int EntryBufferPoints = 10;

//================ TRADE MANAGEMENT ====================

input bool EnableBreakEven = true;
input int BreakEvenTriggerPoints = 500;
input int BreakEvenOffsetPoints = 10;

//================ SESSION FILTER =====================

input bool UseSessionFilter = false;
input bool TradeAllSessions = true;

input bool TradeSydney  = false;
input bool TradeTokyo   = false;
input bool TradeLondon  = false;
input bool TradeNewYork = false;

//================ ADX FILTER =====================

input bool   UseADXFilter              = false;

input int    ADXPeriod                 = 14;

input double MinimumADX                = 25.0;

input bool   RequireRisingADX          = false;

input int    ADXLookbackBars           = 3;

input bool   RequireConsecutiveADXRise = false;

//================ FAILED BREAKOUT EXIT =====================

input bool UseFailedBreakoutExit = false;

input int FailedBreakoutBars = 2;

input bool UseBreakoutRetest = false;

input double BreakoutRetestBufferPoints = 20;

//================ PROFIT PROTECTION ===================

enum ENUM_PROTECTION_MODE
{
   PROTECTION_NONE = 0,
   PROTECTION_SWING = 1,
   PROTECTION_CHANDELIER = 2,
   PROTECTION_TRAILING = 3
};

enum ENUM_PROTECTION_START
{
   START_IMMEDIATELY = 0,
   START_AFTER_POINTS = 1
};

input ENUM_PROTECTION_MODE ProtectionMode = PROTECTION_SWING;

input ENUM_PROTECTION_START ProtectionStartMode = START_AFTER_POINTS;

input int ProtectionStartPoints = 500;;


// Swing Protection

input int SwingBufferPoints = 50;


// Chandelier

input int ChandelierLookback = 22;

input int ATRPeriod = 22;
input double ATRMultiplier = 3.0;


// Fixed Trailing

input int TrailingStartPoints = 1000;
input int TrailingDistancePoints = 500;
input int TrailingStepPoints = 50;

//================ EMERGENCY LOSS FILTER =====================

input bool UseRiskFilter = false;

input double MaximumLossPoints = 300;

//================ SL PERCENTAGE RISK FILTER =================

input bool   UseSLPercentFilter = true;
input double MaximumSLPercent   = 1.0;

// Partial Close

input bool EnablePartialClose = false;
input int PartialCloseTriggerPoints = 1000;
input double PartialClosePercent = 50.0;

//================ GENERAL ====================

input ulong MagicNumber = 12345;

//======================== GLOBALS ==================================

int FastMAHandle;
int TrendMAHandle;
int ATRHandle;
int ADXHandle;
ulong CurrentMagicNumber = 0;
datetime LastBarTime = 0;
bool PartialClosed = false;

//================ TRADE STATE =====================

double EntryBreakoutPrice = 0.0;

datetime EntryTime = 0;

datetime EntryBarTime = 0;

bool EntryIsBuy = false;

//+------------------------------------------------------------------+
//| Build unique Magic Number for each timeframe                     |
//+------------------------------------------------------------------+
ulong GetTimeFrameMagic()
{
   switch(TimeFrame)
   {
      case PERIOD_M1:   return MagicNumber * 100 + 1;
      case PERIOD_M5:   return MagicNumber * 100 + 5;
      case PERIOD_M15:  return MagicNumber * 100 + 15;
      case PERIOD_M30:  return MagicNumber * 100 + 30;
      case PERIOD_H1:   return MagicNumber * 100 + 60;
      case PERIOD_H4:   return MagicNumber * 100 + 61;
      case PERIOD_D1:   return MagicNumber * 100 + 62;

      default:
         return MagicNumber * 100;
   }
}

//+------------------------------------------------------------------+
//| Expert Initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   CurrentMagicNumber = GetTimeFrameMagic();

trade.SetExpertMagicNumber(CurrentMagicNumber);

Print("Current Magic Number = ", CurrentMagicNumber);

   FastMAHandle = iMA(
      _Symbol,
      TimeFrame,
      FastMAPeriod,
      0,
      MODE_SMA,
      PRICE_CLOSE);

   TrendMAHandle = iMA(
      _Symbol,
      TimeFrame,
      TrendMAPeriod,
      0,
      MODE_SMA,
      PRICE_CLOSE);

   if(FastMAHandle == INVALID_HANDLE)
      return(INIT_FAILED);

   if(TrendMAHandle == INVALID_HANDLE)
      return(INIT_FAILED);
      
   //---------------- Show Moving Averages on Chart ----------------//

if(!ChartIndicatorAdd(0,0,FastMAHandle))
   Print("Failed to add Fast SMA to chart. Error = ",GetLastError());

if(!ChartIndicatorAdd(0,0,TrendMAHandle))
   Print("Failed to add Trend SMA to chart. Error = ",GetLastError());
      
   ATRHandle = iATR(_Symbol, TimeFrame, ATRPeriod);

if(ATRHandle == INVALID_HANDLE)
   return(INIT_FAILED);
   
   ADXHandle = iADX(_Symbol, TimeFrame, ADXPeriod);

if(ADXHandle == INVALID_HANDLE)
   return(INIT_FAILED);
   
   

   Print("SimpleSMA18Bot initialized successfully.");

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert Deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ChartIndicatorDelete(0,0,"Moving Average");

   if(FastMAHandle != INVALID_HANDLE)
      IndicatorRelease(FastMAHandle);

   if(TrendMAHandle != INVALID_HANDLE)
      IndicatorRelease(TrendMAHandle);

   if(ATRHandle != INVALID_HANDLE)
      IndicatorRelease(ATRHandle);
      
   if(ADXHandle != INVALID_HANDLE)
   IndicatorRelease(ADXHandle);
}

//+------------------------------------------------------------------+
//| Returns TRUE when a new candle forms                             |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime time[];

   if(CopyTime(_Symbol, TimeFrame, 0, 1, time) <= 0)
      return false;

   if(time[0] != LastBarTime)
   {
      LastBarTime = time[0];
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Get SMA Value                                                    |
//+------------------------------------------------------------------+
double GetMAValue(int handle, int shift)
{
   double buffer[];

   if(CopyBuffer(handle, 0, shift, 1, buffer) <= 0)
      return 0;

   return buffer[0];
}

//+------------------------------------------------------------------+
//| Get ATR Value                                                    |
//+------------------------------------------------------------------+
double GetATRValue(int shift)
{
   double atr[];

   if(CopyBuffer(ATRHandle,0,shift,1,atr)<=0)
      return 0;

   return atr[0];
}

//+------------------------------------------------------------------+
//| Get ADX Value                                                    |
//+------------------------------------------------------------------+
double GetADXValue(int shift)
{
   double value[];

   ArraySetAsSeries(value,true);

   if(CopyBuffer(ADXHandle,0,shift,1,value) <= 0)
      return 0.0;

   return value[0];
}

bool IsADXAboveThreshold()
{
   return (GetADXValue(1) >= MinimumADX);
}

bool IsADXRising()
{
   return (GetADXValue(1) >
           GetADXValue(ADXLookbackBars + 1));
}

bool IsADXConsecutivelyRising()
{
   for(int i=1;i<=ADXLookbackBars;i++)
   {
      if(GetADXValue(i) <= GetADXValue(i+1))
         return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| ADX Trend Filter                                                 |
//+------------------------------------------------------------------+
bool PassADXFilter()
{
   if(!UseADXFilter)
      return true;

   if(!IsADXAboveThreshold())
      return false;

   if(RequireConsecutiveADXRise)
      return IsADXConsecutivelyRising();

   if(RequireRisingADX)
      return IsADXRising();

   return true;
}


//+------------------------------------------------------------------+
//| Trading Session Filter                                           |
//+------------------------------------------------------------------+
bool IsTradingSession()
{
   if(!UseSessionFilter)
      return true;

   if(TradeAllSessions)
      return true;

   MqlDateTime tm;
   TimeToStruct(TimeCurrent(), tm);

   int hour = tm.hour;

   // Broker time session definitions
   // (Adjust once if your broker uses a different server time.)

   bool Sydney  = (hour >= 22 || hour < 7);
   bool Tokyo   = (hour >= 0  && hour < 9);
   bool London  = (hour >= 8  && hour < 17);
   bool NewYork = (hour >= 13 && hour < 22);

   if(TradeSydney  && Sydney)
      return true;

   if(TradeTokyo && Tokyo)
      return true;

   if(TradeLondon && London)
      return true;

   if(TradeNewYork && NewYork)
      return true;

   return false;
}

//+------------------------------------------------------------------+
//| Calculate Average Volume                                         |
//+------------------------------------------------------------------+
double GetAverageVolume(int period)
{
   long total = 0;

   for(int i = 1; i <= period; i++)
      total += iVolume(_Symbol, TimeFrame, i);

   return (double)total / period;
}

//+------------------------------------------------------------------+
//| Find Previous Confirmed Swing Low                               |
//+------------------------------------------------------------------+
double GetSwingLow()
{
   int start = SwingStrength + 1;
   int end   = 100;

   for(int bar = start; bar <= end; bar++)
   {
      double low = iLow(_Symbol, TimeFrame, bar);

      bool swing = true;

      // Left side
      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iLow(_Symbol, TimeFrame, bar + i) <= low)
         {
            swing = false;
            break;
         }
      }

      if(!swing)
         continue;

      // Right side
      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iLow(_Symbol, TimeFrame, bar - i) <= low)
         {
            swing = false;
            break;
         }
      }

      if(swing)
         return low;
   }

   return iLow(_Symbol, TimeFrame, 1);
}

//+------------------------------------------------------------------+
//| Find Previous Confirmed Swing High                              |
//+------------------------------------------------------------------+
double GetSwingHigh()
{
   int start = SwingStrength + 1;
   int end   = 100;

   for(int bar = start; bar <= end; bar++)
   {
      double high = iHigh(_Symbol, TimeFrame, bar);

      bool swing = true;

      // Left side
      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iHigh(_Symbol, TimeFrame, bar + i) >= high)
         {
            swing = false;
            break;
         }
      }

      if(!swing)
         continue;

      // Right side
      for(int i = 1; i <= SwingStrength; i++)
      {
         if(iHigh(_Symbol, TimeFrame, bar - i) >= high)
         {
            swing = false;
            break;
         }
      }

      if(swing)
         return high;
   }

   return iHigh(_Symbol, TimeFrame, 1);
}

//+------------------------------------------------------------------+
//| Stop distance in points                                          |
//+------------------------------------------------------------------+
double GetStopDistancePoints(double entry,double sl)
{
   return MathAbs(entry-sl)/_Point;
}

//+------------------------------------------------------------------+
//| Potential money loss                                             |
//+------------------------------------------------------------------+
double GetPotentialMoneyLoss(double entry,double sl,double lots)
{
   double tickValue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);

   if(tickSize<=0.0)
      return 0.0;

   double distance = MathAbs(entry-sl);

   return (distance/tickSize)*tickValue*lots;
}

//+------------------------------------------------------------------+
//| Update Pending BUY Stop Loss                                     |
//+------------------------------------------------------------------+
void UpdatePendingBuySL()
{
   if(!PendingBuyExists())
      return;

   double newSL = GetSwingLow();

   ulong ticket = 0;

   for(int i=0;i<OrdersTotal();i++)
   {
      ticket = OrderGetTicket(i);

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL)!=_Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC)!=CurrentMagicNumber)
         continue;

      if(OrderGetInteger(ORDER_TYPE)!=ORDER_TYPE_BUY_STOP)
         continue;

      double entry = OrderGetDouble(ORDER_PRICE_OPEN);
      double oldSL = OrderGetDouble(ORDER_SL);
      double tp    = OrderGetDouble(ORDER_TP);

      // Only tighten the stop
    if(newSL > oldSL)
{
   if(trade.OrderModify(
      ticket,
      entry,
      newSL,
      tp,
      ORDER_TIME_GTC,
      0))
   {
      Print("BUY STOP SL Updated");
   }
}
      break;
   }
}

//+------------------------------------------------------------------+
//| Update Pending SELL Stop Loss                                    |
//+------------------------------------------------------------------+
void UpdatePendingSellSL()
{
   if(!PendingSellExists())
      return;

   double newSL = GetSwingHigh();

   ulong ticket = 0;

   for(int i=0;i<OrdersTotal();i++)
   {
      ticket = OrderGetTicket(i);

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL)!=_Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC)!=CurrentMagicNumber)
         continue;

      if(OrderGetInteger(ORDER_TYPE)!=ORDER_TYPE_SELL_STOP)
         continue;

      double entry = OrderGetDouble(ORDER_PRICE_OPEN);
      double oldSL = OrderGetDouble(ORDER_SL);
      double tp    = OrderGetDouble(ORDER_TP);

      // Only tighten the stop
 if(newSL < oldSL)
{
     if(trade.OrderModify(
      ticket,
      entry,
      newSL,
      tp,
      ORDER_TIME_GTC,
      0))
   {
      Print("SELL STOP SL Updated");
   }
}

      break;
   }
}

//+------------------------------------------------------------------+
//| Check if a BUY position already exists                           |
//+------------------------------------------------------------------+
bool BuyPositionExists()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if(PositionGetInteger(POSITION_MAGIC)!=CurrentMagicNumber)
         continue;

      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check Sell Position Exists                                       |
//+------------------------------------------------------------------+
bool SellPositionExists()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);

      if(ticket==0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL)!=_Symbol)
         continue;

      if(PositionGetInteger(POSITION_MAGIC)!=CurrentMagicNumber)
         continue;

      if(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Any Open Position?                                               |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   return (BuyPositionExists() || SellPositionExists());
}

//+------------------------------------------------------------------+
//| Any Pending Order?                                               |
//+------------------------------------------------------------------+
bool HasPendingOrder()
{
   return (PendingBuyExists() || PendingSellExists());
}

//+------------------------------------------------------------------+
//| Check Buy Entry Conditions                                      |
//+------------------------------------------------------------------+
bool BuySignal()
{
   //=====================================================
   // SMA VALUES - COMPLETED CANDLES ONLY
   //=====================================================

   double ma18_1  = GetMAValue(FastMAHandle, 1);
   double ma18_2  = GetMAValue(FastMAHandle, 2);

   double ma200_1 = GetMAValue(TrendMAHandle, 1);
   double ma200_2 = GetMAValue(TrendMAHandle, 2);

   double close1 = iClose(_Symbol, TimeFrame, 1);
   double close2 = iClose(_Symbol, TimeFrame, 2);

   //=====================================================
   // 18 SMA MUST BE ABOVE 200 SMA
   //=====================================================

   if(ma18_1 <= ma200_1)
      return false;

   if(ma18_2 <= ma200_2)
      return false;

   //=====================================================
   // TWO CONSECUTIVE CANDLES ABOVE 18 SMA
   //=====================================================

   if(close1 <= ma18_1)
      return false;

   if(close2 <= ma18_2)
      return false;

   //=====================================================
   // TWO CONSECUTIVE CANDLES ABOVE 200 SMA
   //=====================================================

   if(close1 <= ma200_1)
      return false;

   if(close2 <= ma200_2)
      return false;

   //=====================================================
   // VOLUME CONFIRMATION
   //=====================================================

   long currentVolume = iVolume(_Symbol, TimeFrame, 1);
   double avgVolume = GetAverageVolume(VolumeMAPeriod);

   if(currentVolume <= avgVolume)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Check Sell Entry Conditions                                     |
//+------------------------------------------------------------------+
bool SellSignal()
{
   //=====================================================
   // SMA VALUES - COMPLETED CANDLES ONLY
   //=====================================================

   double ma18_1  = GetMAValue(FastMAHandle, 1);
   double ma18_2  = GetMAValue(FastMAHandle, 2);

   double ma200_1 = GetMAValue(TrendMAHandle, 1);
   double ma200_2 = GetMAValue(TrendMAHandle, 2);

   double close1 = iClose(_Symbol, TimeFrame, 1);
   double close2 = iClose(_Symbol, TimeFrame, 2);

   //=====================================================
   // 18 SMA MUST BE BELOW 200 SMA
   //=====================================================

   if(ma18_1 >= ma200_1)
      return false;

   if(ma18_2 >= ma200_2)
      return false;

   //=====================================================
   // TWO CONSECUTIVE CANDLES BELOW 18 SMA
   //=====================================================

   if(close1 >= ma18_1)
      return false;

   if(close2 >= ma18_2)
      return false;

   //=====================================================
   // TWO CONSECUTIVE CANDLES BELOW 200 SMA
   //=====================================================

   if(close1 >= ma200_1)
      return false;

   if(close2 >= ma200_2)
      return false;

   //=====================================================
   // VOLUME CONFIRMATION
   //=====================================================

   long currentVolume = iVolume(_Symbol, TimeFrame, 1);
   double avgVolume = GetAverageVolume(VolumeMAPeriod);

   if(currentVolume <= avgVolume)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Buy Pending Order Invalidation                                   |
//+------------------------------------------------------------------+
bool PendingBuyInvalidated()
{
   double ma18 = GetMAValue(FastMAHandle,1);
   double close = iClose(_Symbol,TimeFrame,1);

   return (close < ma18);
}

//+------------------------------------------------------------------+
//| Sell Pending Order Invalidation                                  |
//+------------------------------------------------------------------+
bool PendingSellInvalidated()
{
   double ma18 = GetMAValue(FastMAHandle,1);
   double close = iClose(_Symbol,TimeFrame,1);

   return (close > ma18);
}

//+------------------------------------------------------------------+
//| Check if Buy Stop already exists                                 |
//+------------------------------------------------------------------+
bool PendingBuyExists()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);

      if(ticket == 0)
         continue;

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC)!=CurrentMagicNumber)
         continue;

      if(OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if Sell Stop already exists                                |
//+------------------------------------------------------------------+
bool PendingSellExists()
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong ticket=OrderGetTicket(i);

      if(ticket==0)
         continue;

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL)!=_Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC)!=CurrentMagicNumber)
         continue;

      if(OrderGetInteger(ORDER_TYPE)==ORDER_TYPE_SELL_STOP)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Cancel Buy Stop                                                  |
//+------------------------------------------------------------------+
void CancelPendingBuy()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);

      if(ticket == 0)
         continue;

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC) != CurrentMagicNumber)
   continue;

      if(OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP)
      {
         if(trade.OrderDelete(ticket))
            Print("Pending Buy Stop cancelled.");
         else
            Print("Failed to cancel pending order.");
      }
   }
}

//+------------------------------------------------------------------+
//| Cancel Sell Stop                                                 |
//+------------------------------------------------------------------+
void CancelPendingSell()
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong ticket=OrderGetTicket(i);

      if(ticket==0)
         continue;

      if(!OrderSelect(ticket))
         continue;

      if(OrderGetString(ORDER_SYMBOL)!=_Symbol)
         continue;

      if(OrderGetInteger(ORDER_MAGIC) != CurrentMagicNumber)
         continue;

      if(OrderGetInteger(ORDER_TYPE)==ORDER_TYPE_SELL_STOP)
         {
            if(trade.OrderDelete(ticket))
               Print("Pending Sell Stop cancelled.");
            else
               Print("Failed to cancel Sell Stop.");
         }
   }
}

//+------------------------------------------------------------------+
//| Check if proposed SL is within account percentage limit          |
//+------------------------------------------------------------------+
bool PassSLPercentFilter(ENUM_ORDER_TYPE orderType,
                         double entryPrice,
                         double stopLossPrice)
{
   if(!UseSLPercentFilter)
      return true;

   if(MaximumSLPercent <= 0)
      return true;

   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   double maximumAllowedLoss =
      accountBalance * MaximumSLPercent / 100.0;

   double estimatedLoss = 0.0;

   if(!OrderCalcProfit(
         orderType,
         _Symbol,
         LotSize,
         entryPrice,
         stopLossPrice,
         estimatedLoss))
   {
      Print("SL Percent Filter: OrderCalcProfit failed. Error = ",
            GetLastError());

      return false;
   }

   estimatedLoss = MathAbs(estimatedLoss);

   Print("SL Risk Check | Entry=",
         DoubleToString(entryPrice,_Digits),
         " SL=",
         DoubleToString(stopLossPrice,_Digits),
         " Estimated Loss=",
         DoubleToString(estimatedLoss,2),
         " Maximum Loss=",
         DoubleToString(maximumAllowedLoss,2));

   if(estimatedLoss > maximumAllowedLoss)
   {
      Print("TRADE BLOCKED | SL loss ",
            DoubleToString(estimatedLoss,2),
            " exceeds maximum allowed ",
            DoubleToString(maximumAllowedLoss,2));

      return false;
   }

   return true;
}
//+------------------------------------------------------------------+
//| Place Buy Stop                                                   |
//+------------------------------------------------------------------+
bool PlaceBuyStop()
{
   if(BuyPositionExists())
      return false;

   if(PendingBuyExists())
      return false;

   double entry = iHigh(_Symbol, TimeFrame, 1) +
               EntryBufferPoints * _Point;

double sl = GetSwingLow();

if(!PassSLPercentFilter(
      ORDER_TYPE_BUY,
      entry,
      sl))
{
   return false;
}

//=====================================================
// SL PERCENTAGE RISK FILTER
//=====================================================

if(!PassSLPercentFilter(
      ORDER_TYPE_BUY,
      entry,
      sl))
{
   return false;
}

trade.SetExpertMagicNumber(CurrentMagicNumber);

   bool result = trade.BuyStop(
      LotSize,
      entry,
      _Symbol,
      sl,
      0,
      ORDER_TIME_GTC,
      0,
      "SMA18 Entry"
   );

   if(result)
      Print("Buy Stop placed @ ", DoubleToString(entry, _Digits));
   else
      Print("Buy Stop failed. Error = ", GetLastError());

   return result;
}

//+------------------------------------------------------------------+
//| Place Sell Stop                                                  |
//+------------------------------------------------------------------+
bool PlaceSellStop()
{
   if(SellPositionExists())
      return false;

   if(PendingSellExists())
      return false;

   double entry=iLow(_Symbol,TimeFrame,1)-
             EntryBufferPoints*_Point;

double sl=GetSwingHigh();

if(!PassSLPercentFilter(
      ORDER_TYPE_SELL,
      entry,
      sl))
{
   return false;
}

//=====================================================
// SL PERCENTAGE RISK FILTER
//=====================================================

if(!PassSLPercentFilter(
      ORDER_TYPE_SELL,
      entry,
      sl))
{
   return false;
}

trade.SetExpertMagicNumber(CurrentMagicNumber);

   bool result=trade.SellStop(
      LotSize,
      entry,
      _Symbol,
      sl,
      0,
      ORDER_TIME_GTC,
      0,
      "SMA18 Sell"
   );

   if(result)
      Print("Sell Stop placed @ ",DoubleToString(entry,_Digits));
   else
      Print("Sell Stop failed. Error=",GetLastError());

   return result;
}

//+------------------------------------------------------------------+
//| Close Buy Position                                               |
//+------------------------------------------------------------------+
void CloseBuyPosition()
{
   for(int i = PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket==0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL)!=_Symbol)
         continue;

      if(PositionGetInteger(POSITION_MAGIC)!=CurrentMagicNumber)
         continue;

      if(PositionGetInteger(POSITION_TYPE)!=POSITION_TYPE_BUY)
         continue;

      if(trade.PositionClose(ticket))
         Print("BUY Position Closed.");
      else
         Print("Failed to close BUY. Error ",GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Close Sell Position                                              |
//+------------------------------------------------------------------+
void CloseSellPosition()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);

      if(ticket==0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL)!=_Symbol)
         continue;

      if(PositionGetInteger(POSITION_MAGIC)!=CurrentMagicNumber)
         continue;

      if(PositionGetInteger(POSITION_TYPE)!=POSITION_TYPE_SELL)
         continue;

      if(trade.PositionClose(ticket))
         Print("SELL Position Closed.");
      else
         Print("Failed to close SELL. Error ",GetLastError());
   }
}



//+------------------------------------------------------------------+
//| BUY Exit                                                         |
//+------------------------------------------------------------------+
bool ExitSignal()
{
   double ma18  = NormalizeDouble(GetMAValue(FastMAHandle,1),_Digits);
   double close = NormalizeDouble(iClose(_Symbol,TimeFrame,1),_Digits);

   return (close <= ma18);
}


//+------------------------------------------------------------------+
//| SELL Exit                                                        |
//+------------------------------------------------------------------+
bool SellExitSignal()
{
   double ma18  = NormalizeDouble(GetMAValue(FastMAHandle,1), _Digits);
   double close = NormalizeDouble(iClose(_Symbol,TimeFrame,1), _Digits);

   return (close >= ma18);
}

//+------------------------------------------------------------------+
//| Modify Stop Loss                                                 |
//+------------------------------------------------------------------+
bool ModifyStopLoss(double newSL)
{
   if(!PositionSelect(_Symbol))
      return false;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double currentSL = PositionGetDouble(POSITION_SL);
   double tp        = PositionGetDouble(POSITION_TP);

   newSL = NormalizeDouble(newSL,_Digits);

   // BUY
   if(type == POSITION_TYPE_BUY)
   {
      if(currentSL == 0 || newSL > currentSL)
      {
         return trade.PositionModify(_Symbol,newSL,tp);
      }
   }

   // SELL
   if(type == POSITION_TYPE_SELL)
   {
      if(currentSL == 0 || newSL < currentSL)
      {
         return trade.PositionModify(_Symbol,newSL,tp);
      }
   }

   return false;
}


//+------------------------------------------------------------------+
//| Swing Protection                                                 |
//+------------------------------------------------------------------+
void ManageSwingProtection()
{
   if(!PositionSelect(_Symbol))
      return;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   // BUY
   if(type == POSITION_TYPE_BUY)
   {
      double swingLow = GetSwingLow();

      double newSL =
         swingLow - SwingBufferPoints * _Point;

      ModifyStopLoss(newSL);
   }

   // SELL
   if(type == POSITION_TYPE_SELL)
   {
      double swingHigh = GetSwingHigh();

      double newSL =
         swingHigh + SwingBufferPoints * _Point;

      ModifyStopLoss(newSL);
   }
}

//+------------------------------------------------------------------+
//| Fixed Trailing Stop                                              |
//+------------------------------------------------------------------+
void ManageTrailingProtection()
{
   if(!PositionSelect(_Symbol))
      return;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double currentSL = PositionGetDouble(POSITION_SL);

   if(type == POSITION_TYPE_BUY)
   {
      double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);

      double desiredSL =
         bid - TrailingDistancePoints * _Point;

      if((bid - PositionGetDouble(POSITION_PRICE_OPEN))/_Point
            < TrailingStartPoints)
         return;

      if(currentSL==0 ||
         desiredSL-currentSL >= TrailingStepPoints*_Point)
      {
         ModifyStopLoss(desiredSL);
      }
   }

   else if(type == POSITION_TYPE_SELL)
   {
      double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);

      double desiredSL =
         ask + TrailingDistancePoints * _Point;

      if((PositionGetDouble(POSITION_PRICE_OPEN)-ask)/_Point
            < TrailingStartPoints)
         return;

      if(currentSL==0 ||
         currentSL-desiredSL >= TrailingStepPoints*_Point)
      {
         ModifyStopLoss(desiredSL);
      }
   }
}

//+------------------------------------------------------------------+
//| Chandelier Exit                                                  |
//+------------------------------------------------------------------+
void ManageChandelierProtection()
{
   if(!PositionSelect(_Symbol))
      return;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double atr = GetATRValue(1);

   if(atr<=0)
      return;

   //================ BUY ========================

   if(type==POSITION_TYPE_BUY)
   {
      double highest=iHigh(_Symbol,TimeFrame,1);

      for(int i=2;i<=ChandelierLookback;i++)
      {
         double h=iHigh(_Symbol,TimeFrame,i);

         if(h>highest)
            highest=h;
      }

      double newSL=highest-(atr*ATRMultiplier);

      ModifyStopLoss(newSL);
   }

   //================ SELL =======================

   else if(type==POSITION_TYPE_SELL)
   {
      double lowest=iLow(_Symbol,TimeFrame,1);

      for(int i=2;i<=ChandelierLookback;i++)
      {
         double l=iLow(_Symbol,TimeFrame,i);

         if(l<lowest)
            lowest=l;
      }

      double newSL=lowest+(atr*ATRMultiplier);

      ModifyStopLoss(newSL);
   }
}

//+------------------------------------------------------------------+
//| Profit Protection Manager                                        |
//+------------------------------------------------------------------+
void ManageProtection()
{
   if(!ProtectionActive())
      return;

   switch(ProtectionMode)
   {
      case PROTECTION_NONE:
         break;

      case PROTECTION_SWING:
         ManageSwingProtection();
         break;

      case PROTECTION_CHANDELIER:
         ManageChandelierProtection();
         break;

      case PROTECTION_TRAILING:
         ManageTrailingProtection();
         break;
   }
}

//+------------------------------------------------------------------+
//| Break-even                                                       |
//+------------------------------------------------------------------+
void ManageBreakEven()
{
   if(!EnableBreakEven)
      return;

   if(!PositionSelect(_Symbol))
      return;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   double currentSL = PositionGetDouble(POSITION_SL);

   double currentPrice =
      (type == POSITION_TYPE_BUY)
      ? SymbolInfoDouble(_Symbol,SYMBOL_BID)
      : SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   double profitPoints;

   if(type == POSITION_TYPE_BUY)
      profitPoints = (currentPrice-openPrice)/_Point;
   else
      profitPoints = (openPrice-currentPrice)/_Point;

   if(profitPoints < BreakEvenTriggerPoints)
      return;

   double newSL;

   if(type == POSITION_TYPE_BUY)
      newSL = openPrice + BreakEvenOffsetPoints*_Point;
   else
      newSL = openPrice - BreakEvenOffsetPoints*_Point;

   ModifyStopLoss(newSL);
}

//+------------------------------------------------------------------+
//| Emergency Loss Filter                                            |
//+------------------------------------------------------------------+
void ManageRiskFilter()
{
   if(!UseRiskFilter)
      return;

   if(!PositionSelect(_Symbol))
      return;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double entry = PositionGetDouble(POSITION_PRICE_OPEN);

   double lossPoints = 0.0;

   //================ BUY =========================
   if(type == POSITION_TYPE_BUY)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      // Only calculate adverse movement
      if(bid < entry)
         lossPoints = (entry - bid) / _Point;
   }

   //================ SELL ========================
   else
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      // Only calculate adverse movement
      if(ask > entry)
         lossPoints = (ask - entry) / _Point;
   }

   if(lossPoints >= MaximumLossPoints)
   {
      Print("Emergency Risk Filter closed position. Loss = ",
            DoubleToString(lossPoints,1),
            " points");

      trade.PositionClose(_Symbol);
   }
}


//+------------------------------------------------------------------+
//| Failed Breakout Exit                                             |
//+------------------------------------------------------------------+
void ManageFailedBreakoutExit()
{
   if(!UseFailedBreakoutExit)
      return;

   if(!PositionSelect(_Symbol))
      return;

   // Only monitor for the first N completed bars
   int barsSinceEntry =
      iBarShift(_Symbol, TimeFrame, EntryBarTime);

   if(barsSinceEntry > FailedBreakoutBars)
      return;

   double close1 = iClose(_Symbol, TimeFrame, 1);

   //================ BUY =========================

   if(EntryIsBuy)
   {
      if(close1 <
         EntryBreakoutPrice -
         BreakoutRetestBufferPoints * _Point)
      {
         Print("Failed BUY Breakout");

         trade.PositionClose(_Symbol);

         return;
      }
   }

   //================ SELL ========================

   else
   {
      if(close1 >
         EntryBreakoutPrice +
         BreakoutRetestBufferPoints * _Point)
      {
         Print("Failed SELL Breakout");

         trade.PositionClose(_Symbol);

         return;
      }
   }
}

//+------------------------------------------------------------------+
//| Should protection be active?                                     |
//+------------------------------------------------------------------+
bool ProtectionActive()
{
   if(!PositionSelect(_Symbol))
      return false;

   if(ProtectionStartMode == START_IMMEDIATELY)
      return true;

   ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);

   double currentPrice =
      (type == POSITION_TYPE_BUY)
      ? SymbolInfoDouble(_Symbol,SYMBOL_BID)
      : SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   double profitPoints;

   if(type == POSITION_TYPE_BUY)
      profitPoints = (currentPrice-openPrice)/_Point;
   else
      profitPoints = (openPrice-currentPrice)/_Point;

   return(profitPoints >= ProtectionStartPoints);
}

//+------------------------------------------------------------------+
//| Manage Open Positions                                            |
//+------------------------------------------------------------------+


void ManageOpenPositions()
{
   //================ BUY =========================

 if(BuyPositionExists())
{
   // Emergency Risk Filter
   ManageRiskFilter();

   // Trade may already be closed
   if(!PositionSelect(_Symbol))
      return;

   if(ExitSignal())
   {
      CloseBuyPosition();
      return;
   }

   ManageBreakEven();

   ManageProtection();

   return;
}

   //================ SELL ========================

  if(SellPositionExists())
{
   // Emergency Risk Filter
   ManageRiskFilter();

   // Trade may already be closed
   if(!PositionSelect(_Symbol))
      return;

   if(SellExitSignal())
   {
      CloseSellPosition();
      return;
   }

   ManageBreakEven();

   ManageProtection();

   return;
}
}

//+------------------------------------------------------------------+
//| Initialize Trade State                                           |
//+------------------------------------------------------------------+
void UpdateTradeState()
{
   static bool TradeInitialized = false;

   // No position
   if(!PositionSelect(_Symbol))
   {
      TradeInitialized = false;
      return;
   }

   // Already initialized
   if(TradeInitialized)
      return;

   EntryTime = (datetime)PositionGetInteger(POSITION_TIME);

   EntryBarTime = iTime(_Symbol, TimeFrame, 0);

   EntryBreakoutPrice =
      PositionGetDouble(POSITION_PRICE_OPEN);

   EntryIsBuy =
      (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);

   TradeInitialized = true;

   Print("Trade State Initialized");
}


void OnTick()
{
//=====================================================
   // Update Trade State
   //=====================================================

   UpdateTradeState();

   //=====================================================
   // ALWAYS MANAGE OPEN POSITIONS
   //=====================================================

   ManageOpenPositions();

   //=====================================================
   // EVERYTHING BELOW NEEDS A NEW BAR
   //=====================================================

   if(!IsNewBar())
      return;

//=====================================================
// Pending BUY
//=====================================================

if(PendingBuyExists())
{
   UpdatePendingBuySL();

   if(PendingBuyInvalidated())
      CancelPendingBuy();

   return;
}
//=====================================================
// Pending SELL
//=====================================================

if(PendingSellExists())
{
   UpdatePendingSellSL();

   if(PendingSellInvalidated())
      CancelPendingSell();

   return;
}

//=====================================================
// Don't create new setups if a trade exists
//=====================================================

if(HasOpenPosition())
   return;

//=====================================================
// Session Filter
//=====================================================

if(!IsTradingSession())
{
   Comment("Session Filter : OFF HOURS");
   return;
}

//=====================================================
// ADX Filter
//=====================================================

if(!PassADXFilter())
{
   Comment("ADX Filter : Weak Trend");
   return;
}

//=====================================================
// New BUY
//=====================================================

if(BuySignal())
{
   PlaceBuyStop();
   return;
}

//=====================================================
// New SELL
//=====================================================

if(SellSignal())
{
   PlaceSellStop();
   return;
}
}