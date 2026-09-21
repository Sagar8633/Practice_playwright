//+------------------------------------------------------------------+
//|                                                  LiquiditySweepEA|
//|                         Version 1.0 - Signal Monitor             |
//+------------------------------------------------------------------+
#property copyright "Liquidity Sweep EA"
#property version   "1.10"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//--------------------------- Inputs --------------------------------
//input double LotSize = 0.01;
//
//input double MinimumSweepDistance = 1.00;
//
//input double SL_Buffer_Price = 0.50;
//input double WickBodyRatio = 1.5;
//input double MinWickPercent = 35.0;
//
//input double RiskReward = 2.5;
//input int StopLossBuffer = 20;
//
//enum StopLossMode
//{
//   SL_MANIPULATION = 0,
//   SL_REFERENCE = 1
//};
//
//input StopLossMode StopMode = SL_MANIPULATION;
//
//input double MinimumBodySize = 1.00;
//
//input double MaxStopDistance = 15.0;
//
//input ulong MagicNumber = 260706;
//
//input bool CloseOnOppositeSignal = true;

input double LotSize = 0.01;

input int StopLossBuffer = 20;

input double WickBodyRatio = 1.5;
input double MinWickPercent = 35.0;

input double BuyCloseStrength = 0.75;
input double SellCloseStrength = 0.25;

input double RiskReward = 2.5;

enum StopLossMode
{
   SL_MANIPULATION = 0,
   SL_REFERENCE = 1
};

input StopLossMode StopMode = SL_MANIPULATION;

input double MinimumSweepDistance = 1.00;

input double MinimumBodySize = 1.00;

input double MaximumRangeMultiplier = 2.0;

input double MinimumReclaimPercent = 25.0;

input double MaxStopDistance = 15.0;

input ulong MagicNumber = 260706;

input bool CloseOnOppositeSignal = true;

input bool DebugMode = true;

input int MinimumSignalScore = 75;

//==================================================
// Signal Mode
//==================================================
enum ENUM_SIGNAL_MODE
{
   CLASSIC = 0,
   FILTERED = 1
};

input ENUM_SIGNAL_MODE SignalMode = FILTERED;

//==================================================
// Enable / Disable Filters
//==================================================
input bool UseLiquiditySweepFilter = true;
input bool UseCloseInsideFilter    = true;
input bool UseCandleSizeFilter     = true;
input bool UseBodyFilter           = true;
input bool UseWickFilter           = true;
input bool UsePreviousRangeFilter  = true;

// Score Weights
input int ScoreSweepDistance = 20;
input int ScoreBody = 15;
input int ScoreWick = 20;
input int ScoreCloseStrength = 20;
input int ScoreRange = 10;
input int ScoreReclaim = 15;

input bool UseGapFilter = true;

input double MaximumGap = 0.50;

input double MaximumEntryDistance = 2.00;





//---------------------- Global Variables ---------------------------

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+

//========================== Globals =========================
datetime LastTradeSignalBar = 0;
datetime LastH4BarTime = 0;


enum SignalType
{
   SIGNAL_NONE = 0,
   SIGNAL_BUY,
   SIGNAL_SELL
};
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   Print("Liquidity Sweep EA Started");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("Liquidity Sweep EA Removed");
}

//+------------------------------------------------------------------+
//| Returns TRUE only once for every new H4 candle                   |
//+------------------------------------------------------------------+
bool IsNewH4Bar()
{
   datetime currentBar=iTime(_Symbol,PERIOD_H4,0);

   if(currentBar!=LastH4BarTime)
   {
      LastH4BarTime=currentBar;
      return(true);
   }

   return(false);
}

//+------------------------------------------------------------------+
//| Check Liquidity Sweep Signal                                     |
//+------------------------------------------------------------------+
//int CalculateSignalScore(
//   bool bodyLargeEnough,
//   bool rangeAcceptable,
//   bool wickValid,
//   bool closeValid,
//   double reclaimPercent,
//   double sweepDistance)
//{
//   int score = 0;
//
//   // Sweep
//   if(sweepDistance >= MinimumSweepDistance)
//      score += ScoreSweepDistance;
//
//   // Body
//   if(bodyLargeEnough)
//      score += ScoreBody;
//
//   // Candle Range
//   if(rangeAcceptable)
//      score += ScoreRange;
//
//   // Wick
//   if(wickValid)
//      score += ScoreWick;
//
//   // Close Strength
//   if(closeValid)
//      score += ScoreCloseStrength;
//
//   // Reclaim
//   if(reclaimPercent >= MinimumReclaimPercent)
//      score += ScoreReclaim;
//
//   return score;
//}

int CalculateSignalScore(
   bool bodyLargeEnough,
   bool rangeAcceptable,
   bool wickValid,
   bool closeValid,
   double reclaimPercent,
   double sweepDistance)
{
   int score = 0;

   bool useBody     = UseBodyFilter;
   bool useRange    = UsePreviousRangeFilter;
   bool useWick     = UseWickFilter;
   bool useClose    = UseCloseInsideFilter;
   bool useSweep    = UseLiquiditySweepFilter;

   if(SignalMode == CLASSIC)
   {
      useBody  = false;
      useRange = false;
      useWick  = false;

      // Keep the core strategy alive
      useClose = true;
      useSweep = true;
   }

   // Sweep
   if(!useSweep || sweepDistance >= MinimumSweepDistance)
      score += ScoreSweepDistance;

   // Body
   if(!useBody || bodyLargeEnough)
      score += ScoreBody;

   // Candle Range
   if(!useRange || rangeAcceptable)
      score += ScoreRange;

   // Wick
   if(!useWick || wickValid)
      score += ScoreWick;

   // Close
   if(!useClose || closeValid)
      score += ScoreCloseStrength;

   // Reclaim
   if(reclaimPercent >= MinimumReclaimPercent)
      score += ScoreReclaim;

   return score;
}

SignalType CheckSignal()
{
   //================ Candle Data ================
   double prevHigh = iHigh(_Symbol, PERIOD_H4, 2);
   double prevLow  = iLow(_Symbol, PERIOD_H4, 2);

   double sigHigh  = iHigh(_Symbol, PERIOD_H4, 1);
   double sigLow   = iLow(_Symbol, PERIOD_H4, 1);
   double sigOpen  = iOpen(_Symbol, PERIOD_H4, 1);
   double sigClose = iClose(_Symbol, PERIOD_H4, 1);

   //================ Candle Measurements ================
   double body = MathAbs(sigClose - sigOpen);

   double candleRange = sigHigh - sigLow;
   double previousRange = prevHigh - prevLow;

   bool rangeAcceptable = true;

   if(previousRange > 0)
      rangeAcceptable = (candleRange <= previousRange * MaximumRangeMultiplier);

   double lowerWick = MathMin(sigOpen, sigClose) - sigLow;
   double upperWick = sigHigh - MathMax(sigOpen, sigClose);

   double lowerWickPercent = 0.0;
   double upperWickPercent = 0.0;

   if(candleRange > 0)
   {
      lowerWickPercent = (lowerWick / candleRange) * 100.0;
      upperWickPercent = (upperWick / candleRange) * 100.0;
   }

   double closePosition = 0.0;

   if(candleRange > 0)
      closePosition = (sigClose - sigLow) / candleRange;

   //================ Sweep Detection ================
   bool brokeLow  = (sigLow  <= (prevLow  - MinimumSweepDistance));
   bool brokeHigh = (sigHigh >= (prevHigh + MinimumSweepDistance));

   if(brokeLow && brokeHigh)
      return SIGNAL_NONE;

   //================ Body Filter ================
   bool bodyLargeEnough = (body >= MinimumBodySize);

   //================ Reclaim Calculation ================
   double reclaimPercent = 0.0;

   if(previousRange > 0)
   {
      if(brokeLow)
         reclaimPercent = ((sigClose - prevLow) / previousRange) * 100.0;

      if(brokeHigh)
         reclaimPercent = ((prevHigh - sigClose) / previousRange) * 100.0;
   }

//================ Score Conditions ================

// BUY
bool wickValidBuy =
      body > 0 &&
      (lowerWick / body) >= WickBodyRatio &&
      lowerWickPercent >= MinWickPercent;

bool closeValidBuy =
      closePosition >= BuyCloseStrength;

// SELL
bool wickValidSell =
      body > 0 &&
      (upperWick / body) >= WickBodyRatio &&
      upperWickPercent >= MinWickPercent;

bool closeValidSell =
      closePosition <= SellCloseStrength;

// Calculate Scores
int buyScore = CalculateSignalScore(
      bodyLargeEnough,
      rangeAcceptable,
      wickValidBuy,
      closeValidBuy,
      reclaimPercent,
      prevLow - sigLow);

int sellScore = CalculateSignalScore(
      bodyLargeEnough,
      rangeAcceptable,
      wickValidSell,
      closeValidSell,
      reclaimPercent,
      sigHigh - prevHigh);

   //================ BUY =========================
//================ BUY =========================
//if(brokeLow &&
//   sigClose > prevLow &&
//   bodyLargeEnough &&
//   rangeAcceptable &&
//   body > 0 &&
//   (lowerWick / body) >= WickBodyRatio &&
//   lowerWickPercent >= MinWickPercent &&
//   closePosition >= BuyCloseStrength)

//if(brokeLow &&
//   sigClose > prevLow &&
//   buyScore >= MinimumSignalScore)
//{
//   PrintSignalDebug(
//      "BUY SIGNAL",
//      prevLow - sigLow,
//      body,
//      lowerWickPercent,
//      upperWickPercent,
//      closePosition,
//      reclaimPercent,
//      buyScore);
//
//   return SIGNAL_BUY;
//}


int requiredScore = MinimumSignalScore;

if(SignalMode == CLASSIC)
{
   requiredScore =
      ScoreSweepDistance +
      ScoreCloseStrength +
      ScoreReclaim;
}

if(brokeLow &&
   sigClose > prevLow &&
   buyScore >= requiredScore)
{
   PrintSignalDebug(
      "BUY SIGNAL",
      prevLow - sigLow,
      body,
      lowerWickPercent,
      upperWickPercent,
      closePosition,
      reclaimPercent,
      buyScore);

   return SIGNAL_BUY;
}

   //================ SELL ========================
//================ SELL ========================
//if(brokeHigh &&
//   sigClose < prevHigh &&
//   bodyLargeEnough &&
//   rangeAcceptable &&
//   body > 0 &&
//   (upperWick / body) >= WickBodyRatio &&
//   upperWickPercent >= MinWickPercent &&
//   closePosition <= SellCloseStrength)

if(brokeHigh &&
   sigClose < prevHigh &&
   sellScore >= requiredScore)
{
   PrintSignalDebug(
      "SELL SIGNAL",
      sigHigh - prevHigh,
      body,
      lowerWickPercent,
      upperWickPercent,
      closePosition,
      reclaimPercent,
      sellScore);

   return SIGNAL_SELL;
}

   return SIGNAL_NONE;
}

//+------------------------------------------------------------------+
//| Expert Tick                                                      |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Check if a position exists                                       |
//+------------------------------------------------------------------+
bool PositionExists()
{
   return PositionSelect(_Symbol);
}

//+------------------------------------------------------------------+
//| Open BUY                                                         |
//+------------------------------------------------------------------+
void OpenBuy(double signalLow)
{
   if(PositionExists())
      return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   double signalClose = iClose(_Symbol, PERIOD_H4, 1);

double entryDistance = MathAbs(ask - signalClose);

if(entryDistance > MaximumEntryDistance)
{
   Print("BUY skipped - Entry too far from signal candle. Distance = ",
         DoubleToString(entryDistance,2));
   return;
}

   double manipulationLow = iLow(_Symbol, PERIOD_H4, 1);
double referenceLow    = iLow(_Symbol, PERIOD_H4, 2);

double sl;

if(StopMode == SL_MANIPULATION)
   sl = manipulationLow - (StopLossBuffer * _Point);
else
   sl = referenceLow - (StopLossBuffer * _Point);
   double risk = ask - sl;
   
   if(risk > MaxStopDistance)
{
   Print("BUY skipped - Stop Distance = ", risk,
         " exceeds MaxStopDistance = ", MaxStopDistance);
   return;
}

   double tp = ask + (risk * RiskReward);

   if(trade.Buy(LotSize, _Symbol, ask, sl, tp, "LS BUY"))
      Print("BUY OPENED | Entry:", ask, " SL:", sl, " TP:", tp);
   else
      Print("BUY FAILED : ", GetLastError());
}

//+------------------------------------------------------------------+
//| Open SELL                                                        |
//+------------------------------------------------------------------+
void OpenSell(double signalHigh)
{
   if(PositionExists())
      return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   double signalClose = iClose(_Symbol, PERIOD_H4, 1);

double entryDistance = MathAbs(signalClose - bid);

if(entryDistance > MaximumEntryDistance)
{
   Print("SELL skipped - Entry too far from signal candle. Distance = ",
         DoubleToString(entryDistance,2));
   return;
}

   double manipulationHigh = iHigh(_Symbol, PERIOD_H4, 1);
double referenceHigh    = iHigh(_Symbol, PERIOD_H4, 2);

double sl;

if(StopMode == SL_MANIPULATION)
   sl = manipulationHigh + (StopLossBuffer * _Point);
else
   sl = referenceHigh + (StopLossBuffer * _Point);
   double risk = sl - bid;
   
   if(risk > MaxStopDistance)
{
   Print("SELL skipped - Stop Distance = ", risk,
         " exceeds MaxStopDistance = ", MaxStopDistance);
   return;
}

   double tp = bid - (risk * RiskReward);

   if(trade.Sell(LotSize, _Symbol, bid, sl, tp, "LS SELL"))
      Print("SELL OPENED | Entry:", bid, " SL:", sl, " TP:", tp);
   else
      Print("SELL FAILED : ", GetLastError());
}

int GetPositionType()
{
   if(!PositionSelect(_Symbol))
      return 0;

   long type = PositionGetInteger(POSITION_TYPE);

   if(type == POSITION_TYPE_BUY)  return 1;
   if(type == POSITION_TYPE_SELL) return -1;

   return 0;
}

void PrintSignalDebug(
   string signal,
   double sweepDistance,
   double body,
   double lowerWickPercent,
   double upperWickPercent,
   double closePosition,
   double reclaimPercent,
   int score)
{
   if(!DebugMode)
      return;

   Print("========================================");
   Print(signal);
   Print("----------------------------------------");
   Print("Sweep Distance : ", DoubleToString(sweepDistance,2));
   Print("Body Size      : ", DoubleToString(body,2));
   Print("Lower Wick %   : ", DoubleToString(lowerWickPercent,1));
   Print("Upper Wick %   : ", DoubleToString(upperWickPercent,1));
   Print("Close Position : ", DoubleToString(closePosition,2));
   Print("Reclaim %      : ", DoubleToString(reclaimPercent,1));
   Print("Signal Score   : ", score, "/", 
         ScoreSweepDistance +
         ScoreBody +
         ScoreWick +
         ScoreCloseStrength +
         ScoreRange +
         ScoreReclaim);
   Print("========================================");
}
void OnTick()
{
   if(!IsNewH4Bar())
   {
      Print("Waiting for new H4 candle...");
      return;
   }

   SignalType signal = CheckSignal();
datetime signalBarTime = iTime(_Symbol, PERIOD_H4, 1);
if(signalBarTime == LastTradeSignalBar)
{
   Print("Signal already traded on this candle");
   return;
}

   int pos = GetPositionType();

   Print("Signal checked. Result = ", signal);

   switch(signal)
   {
      case SIGNAL_BUY:
      {
         if(pos == 1)
         {
            Print("BUY already open");
            break;
         }

         if(pos == -1 && CloseOnOppositeSignal)
         {
            Print("Closing SELL before BUY");
            trade.PositionClose(_Symbol);
         }

         Print("BUY Signal detected");

         OpenBuy(iLow(_Symbol, PERIOD_H4, 1));
LastTradeSignalBar = signalBarTime;

         break;
      }

      case SIGNAL_SELL:
      {
         if(pos == -1)
         {
            Print("SELL already open");
            break;
         }

         if(pos == 1 && CloseOnOppositeSignal)
         {
            Print("Closing BUY before SELL");
            trade.PositionClose(_Symbol);
         }

         Print("SELL Signal detected");

         OpenSell(iHigh(_Symbol, PERIOD_H4, 1));
LastTradeSignalBar = signalBarTime;

         break;
      }

      default:
      {
         Print("No Signal");
         break;
      }
   }
}