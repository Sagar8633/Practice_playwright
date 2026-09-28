//+------------------------------------------------------------------+
//| GoldTrend_D1.mq5                                                  |
//| Daily Donchian breakout trend follower for GOLD (Turtle rules).   |
//| Entry: yesterday's close above the highest high of the EntryDays  |
//| days before it. Exit: yesterday's close below the lowest low of   |
//| the ExitDays days before it, or the 2 x ATR(20) stop.             |
//| Sizing: RiskPct of equity per trade, rounded down to the lot step.|
//| Research: backtest/trend_bot_lab.py, 2003-2026, XM costs.         |
//| Long only by default: shorts lost in every period tested.         |
//| Trades only on demo accounts unless AllowRealAccount is true.     |
//+------------------------------------------------------------------+
#property copyright "TWK research, 2026"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input int    EntryDays        = 55;      // Donchian entry length in days (20 = Turtle S1, 55 = Turtle S2)
input int    ExitDays         = 20;      // opposite-channel exit length in days (10 for S1, 20 for S2)
input int    ATRPeriod        = 20;      // ATR period (days)
input double StopATR          = 2.0;     // initial stop distance in ATRs
input double RiskPct          = 1.0;     // percent of equity risked per trade
input bool   AllowLong        = true;
input bool   AllowShort       = false;   // shorts: PF 0.34 / 0.90 / 0.27 in the three research periods
input bool   AllowRealAccount = false;   // safety: false = trade only on demo accounts
input int    SlippagePoints   = 50;
input long   Magic            = 20260926;

CTrade   trade;
int      hATR    = INVALID_HANDLE;
datetime lastBar = 0;

int OnInit()
{
   if(EntryDays < 5 || ExitDays < 2 || ATRPeriod < 2 || StopATR <= 0 || RiskPct <= 0) return INIT_PARAMETERS_INCORRECT;
   hATR = iATR(_Symbol, PERIOD_D1, ATRPeriod);
   if(hATR == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(Magic);
   trade.SetDeviationInPoints(SlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("GoldTrend_D1: %s entry %d / exit %d days, stop %.1f ATR(%d), risk %.2f%%, long %s, short %s, real account %s",
               _Symbol, EntryDays, ExitDays, StopATR, ATRPeriod, RiskPct, AllowLong ? "on" : "off", AllowShort ? "on" : "off", AllowRealAccount ? "ALLOWED" : "blocked");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { if(hATR != INVALID_HANDLE) IndicatorRelease(hATR); }

bool DemoGuard()
{
   if(AllowRealAccount) return true;
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO || AccountInfoInteger(ACCOUNT_LOGIN) == 450160565)
   {
      static datetime warned = 0;
      if(TimeCurrent() - warned > 3600) { Print("GoldTrend_D1: not a demo account and AllowRealAccount=false, no trading"); warned = TimeCurrent(); }
      return false;
   }
   return true;
}

// lots for a stop distance in price, RiskPct of equity, rounded down to the volume step; 0 if below the minimum lot
double LotsForRisk(double stopDist)
{
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || stopDist <= 0) return 0;
   double lossPerLot = stopDist / tickSize * tickVal;
   double lots = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPct / 100.0 / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lots = MathFloor(lots / step) * step;
   if(lots < minL) return 0;
   return MathMin(lots, maxL);
}

void OnTick()
{
   datetime bt = iTime(_Symbol, PERIOD_D1, 0);
   if(bt == 0 || bt == lastBar) return;          // act once, on the first tick of each new daily bar
   lastBar = bt;
   if(!DemoGuard()) return;
   if(Bars(_Symbol, PERIOD_D1) < EntryDays + ATRPeriod + 3) return;

   double atr[];
   if(CopyBuffer(hATR, 0, 1, 1, atr) != 1 || atr[0] <= 0) return;
   double closePrev = iClose(_Symbol, PERIOD_D1, 1);                      // the bar that just closed
   double hhIn  = iHigh(_Symbol, PERIOD_D1, iHighest(_Symbol, PERIOD_D1, MODE_HIGH, EntryDays, 2));   // the EntryDays days before it
   double llIn  = iLow (_Symbol, PERIOD_D1, iLowest (_Symbol, PERIOD_D1, MODE_LOW,  EntryDays, 2));
   double hhOut = iHigh(_Symbol, PERIOD_D1, iHighest(_Symbol, PERIOD_D1, MODE_HIGH, ExitDays, 2));
   double llOut = iLow (_Symbol, PERIOD_D1, iLowest (_Symbol, PERIOD_D1, MODE_LOW,  ExitDays, 2));

   // manage the open position (one at a time)
   bool haveLong = false, haveShort = false; ulong ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) haveLong = true; else haveShort = true;
      ticket = tk;
   }
   if(haveLong && closePrev < llOut)  { if(trade.PositionClose(ticket)) { PrintFormat("exit long: close %.2f < %d-day low %.2f", closePrev, ExitDays, llOut); haveLong = false; } }
   if(haveShort && closePrev > hhOut) { if(trade.PositionClose(ticket)) { PrintFormat("exit short: close %.2f > %d-day high %.2f", closePrev, ExitDays, hhOut); haveShort = false; } }
   if(haveLong || haveShort) return;

   int dir = 0;
   if(AllowLong && closePrev > hhIn) dir = 1;
   else if(AllowShort && closePrev < llIn) dir = -1;
   if(dir == 0) return;

   double stopDist = StopATR * atr[0];
   double lots = LotsForRisk(stopDist);
   if(lots <= 0) { PrintFormat("GoldTrend_D1: account too small: risk %.2f%% of %.2f cannot cover the minimum lot at a %.2f stop", RiskPct, AccountInfoDouble(ACCOUNT_EQUITY), stopDist); return; }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(dir == 1)
   {
      double sl = NormalizeDouble(ask - stopDist, _Digits);
      if(trade.Buy(lots, _Symbol, ask, sl, 0.0, "GoldTrend L")) PrintFormat("buy %.2f lots at %.2f, stop %.2f (close %.2f > %d-day high %.2f)", lots, ask, sl, closePrev, EntryDays, hhIn);
      else PrintFormat("buy failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   }
   else
   {
      double sl = NormalizeDouble(bid + stopDist, _Digits);
      if(trade.Sell(lots, _Symbol, bid, sl, 0.0, "GoldTrend S")) PrintFormat("sell %.2f lots at %.2f, stop %.2f", lots, bid, sl);
      else PrintFormat("sell failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   }
}
//+------------------------------------------------------------------+
