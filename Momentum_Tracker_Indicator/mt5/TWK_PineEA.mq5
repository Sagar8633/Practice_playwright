//+------------------------------------------------------------------+
//| TWK_PineEA.mq5                                                   |
//| Simple "Pine trades" robot for the TWK Tracker.                  |
//|                                                                  |
//| Every purple-line flip (Smart Trail LONG/SHORT) is a trade:      |
//|  - the open trade in the other direction is closed at the flip   |
//|    (ReverseOnFlip), and a new trade opens in the new direction;  |
//|  - SL = last confirmed pivot (5 bars each side), or the purple   |
//|    line when there is none; TP = RewardRisk x that risk. These   |
//|    are the exact TWK_Tracker.pine / TWK_Strategy.pine levels,    |
//|    from the signal-bar close; the order goes at the next bar.    |
//|  - trailing: once the trade is in profit the SL follows the     |
//|    purple line; at +LockTriggerPoints (1000) the SL locks       |
//|    +LockProfitPoints (900). The SL never loosens. The trade     |
//|    ends at SL, TP or the next flip.                             |
//|                                                                  |
//| No filters: every flip is traded (volume, boxes, ADX, spread and |
//| the hard-SL rules belong to TWK_MomentumEA only).                |
//|                                                                  |
//| The chart Tracker (purple line, arrows, SL/TP boxes) is compiled |
//| in, so the Strategy Tester shows it. Compile                     |
//| Indicators\TWK\TWK_Tracker_MT5.mq5 before this file.             |
//|                                                                  |
//| DEMO FIRST: new trades on a REAL account need AccountGuard =     |
//| Demo and Real AND "I ACCEPT REAL RISK" typed in                  |
//| RealTradingConfirmation.                                         |
//+------------------------------------------------------------------+
#property copyright "trade_with_kareena"
#property version   "1.20"
#property description "TWK Tracker Pine trades: every purple-line flip closes the old trade and opens the new direction."
#property description "SL = Pine pivot stop, TP = RewardRisk x risk, purple-line trail and profit lock. No filters. Demo-only by default."

#include <Trade\Trade.mqh>
#include "TWK_Core.mqh"

#resource "\\Indicators\\TWK\\TWK_Tracker_MT5.ex5"
#define TWK_TRACKER_RES  "::Indicators\\TWK\\TWK_Tracker_MT5.ex5"
#define TWK_TRACKER_NAME "TWK Tracker (EA)"
#define REAL_CONFIRM_TEXT "I ACCEPT REAL RISK"

enum ENUM_ACCOUNT_GUARD
  {
   GUARD_DEMO_ONLY     = 0, // Demo only (real account = signals only, no orders)
   GUARD_DEMO_AND_REAL = 1  // Demo and Real (also needs the confirmation text)
  };

input group "=== ACCOUNT SAFETY (demo first) ==="
input ENUM_ACCOUNT_GUARD AccountGuard           = GUARD_DEMO_ONLY; // Where new trades are allowed
input string             RealTradingConfirmation = "";             // Type: I ACCEPT REAL RISK (real only)
input double             RealAccountMaxLot       = 0.01;           // Hard lot cap on a REAL account

input group "=== PINE TRADES ==="
input ENUM_TIMEFRAMES    SignalTimeframe = PERIOD_M1; // Signal timeframe (independent of chart)
input double             RewardRisk      = 2.0;       // Reward : Risk (TP = this x stop distance)
input bool               ReverseOnFlip   = true;      // Flip closes the open trade and opens the new side (off = Pine: only when flat)

input group "=== TRAILING ==="
input bool               EnablePurpleTrail      = true; // Once in profit, the SL follows the purple line
input int                PurpleTrailStartPoints = 0;    // Profit (points) before the purple trail starts (0 = as soon as in profit)
input int                LockTriggerPoints      = 1000; // At this profit (points)... (0 = no lock)
input int                LockProfitPoints       = 900;  // ...the SL locks this much profit (points)
input int                MinSLStepPoints        = 5;    // Smallest SL move sent to the broker (points)

input group "=== TRACKER (must match the TradingView inputs) ==="
input double             TrailMultiplier = 1.5;  // Smart Trail multiplier
input int                TrailATRLength  = 10;   // Smart Trail ATR length
input int                PivotStrength   = 5;    // Pivot strength (bars each side)

input group "=== ORDERS ==="
input double             LotSize      = 0.01;      // Fixed lot size
input int                MaxDeviation = 50;        // Max slippage (broker points)
input ulong              MagicNumber  = 26092501;  // Magic number (own one: do not share with TWK_MomentumEA)
input string             TradeComment = "TWK Pine"; // Order comment

input group "=== CHART ==="
input bool               ShowTrackerOnChart = true;  // Purple line, arrows and SL/TP boxes on the chart (also in the tester)
input int                ChartTrackerBars   = 50000; // History drawn when the chart opens (0 = all)
input int                ChartBoxHistory    = 300;   // Live: signals that keep their box (a test keeps every box)
input bool               WriteTradeLog      = true;  // Per-trade CSV in Common\Files

//--- state
CTrade      g_trade;
CTwkEngine  g_engine;
TwkParams   g_p;
datetime    g_lastBarTime   = 0;
int         g_trackerHandle = INVALID_HANDLE;
int         g_nSL = 0, g_nTP = 0, g_nFlip = 0, g_nOther = 0;
double      g_purple = EMPTY_VALUE;    // purple line of the last closed signal bar
int         g_stDir  = 0;              // -1 = line below price (a BUY stop), +1 = above (a SELL stop)
datetime    g_lastModifyFail = 0;

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
bool   IsTester() { return (bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION); }
void   Log(const string tag, const string msg) { PrintFormat("[%s] %s", tag, msg); }
string P(const double v) { return TwkIsNa(v) ? "n/a" : DoubleToString(v, _Digits); }
double Pts(const double points) { return points * _Point; }
int    ToPts(const double dist) { return (int)MathRound(dist / _Point); }
string SigGv() { return StringFormat("TWKPINE.%I64u.%s.lastsig", MagicNumber, _Symbol); }
ENUM_TIMEFRAMES SignalTF() { return (SignalTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : SignalTimeframe; }

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

string AccountModeText()
  {
   switch((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE))
     {
      case ACCOUNT_TRADE_MODE_DEMO:    return "DEMO";
      case ACCOUNT_TRADE_MODE_CONTEST: return "CONTEST";
      default:                         return "REAL";
     }
  }

// Demo guard and terminal permissions: these are safety checks, not trade filters
bool EntriesAllowed(string &why)
  {
   if(!IsTester())
     {
      const ENUM_ACCOUNT_TRADE_MODE m = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
      if(m != ACCOUNT_TRADE_MODE_DEMO && m != ACCOUNT_TRADE_MODE_CONTEST)
        {
         if(AccountGuard != GUARD_DEMO_AND_REAL) { why = "REAL account and AccountGuard = Demo only"; return false; }
         if(RealTradingConfirmation != REAL_CONFIRM_TEXT)
           { why = "REAL account: RealTradingConfirmation must be exactly '" + REAL_CONFIRM_TEXT + "'"; return false; }
        }
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) { why = "Algo Trading button is OFF in the terminal"; return false; }
     }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))         { why = "'Allow Algo Trading' is off in the EA properties"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))  { why = "broker disabled expert trading on this account"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) { why = "trading disabled for this account (investor login?)"; return false; }
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) { why = "symbol trade mode is not FULL"; return false; }
   return true;
  }

//+------------------------------------------------------------------+
//| Stops: the exact Pine levels                                     |
//+------------------------------------------------------------------+
bool TradeStops(const bool isBuy, const TwkSnapshot &s, double &sl, double &tp, string &src, string &why)
  {
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   //--- Pine: SL = last pivot (or the purple line), TP = close +/- RewardRisk x risk; no trade if risk <= 0
   sl  = s.sl;
   tp  = s.tp;
   src = s.slFromPivot ? "pivot" : "purple line, no pivot";
   if(TwkIsNa(s.risk) || s.risk <= 0 || TwkIsNa(sl) || TwkIsNa(tp))
     {
      why = StringFormat("Pine skips this flip: stop %s is not on the protective side", P(s.sl));
      return false;
     }
   sl = NormPrice(sl);
   tp = NormPrice(tp);
   //--- the order must be placeable at the live price (after a gap the pivot can already be crossed)
   const double stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(isBuy ? !(sl < bid - stops) : !(sl > ask + stops))
     { why = StringFormat("price %s is already past the SL %s", P(isBuy ? bid : ask), P(sl)); return false; }
   if(isBuy ? !(tp > ask + stops) : !(tp < bid - stops))
     { why = StringFormat("price %s is already past the TP %s", P(isBuy ? ask : bid), P(tp)); return false; }
   return true;
  }

//+------------------------------------------------------------------+
//| Positions                                                        |
//+------------------------------------------------------------------+
// Closes this EA's positions on the other side of the new signal. Returns false if one stays open.
bool CloseOpposite(const bool isBuy)
  {
   bool ok = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      const bool posBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      if(posBuy == isBuy)
         continue;
      if(g_trade.PositionClose(t, MaxDeviation))
         Log("CLOSE", StringFormat("#%I64u %s closed on the opposite flip", t, posBuy ? "BUY" : "SELL"));
      else
        {
         Log("CLOSE FAILED", StringFormat("#%I64u retcode=%u %s", t, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         ok = false;
        }
     }
   return ok;
  }

// Counts this EA's open positions: total, and on the side of `isBuy`
int OwnPositions(const bool isBuy, int &sameSide)
  {
   int total = 0;
   sameSide = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      total++;
      if((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) == isBuy)
         sameSide++;
     }
   return total;
  }

double TradeLots(const double price, const bool isBuy, string &why)
  {
   const double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lots = LotSize;
   if(!IsTester() && AccountModeText() == "REAL")
      lots = MathMin(lots, RealAccountMaxLot);
   lots = MathMin(lots, vmax);
   if(step > 0)
      lots = MathFloor(lots / step + 1e-9) * step;
   if(lots < vmin - 1e-12) { why = StringFormat("lot below broker minimum %.2f", vmin); return 0; }
   double margin = 0;
   if(!OrderCalcMargin(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, price, margin))
     { why = "cannot calculate margin"; return 0; }
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     { why = StringFormat("insufficient margin: need %.2f, free %.2f", margin, AccountInfoDouble(ACCOUNT_MARGIN_FREE)); return 0; }
   return NormalizeDouble(lots, 8);
  }

void OpenTrade(const bool isBuy, const double sl, const double tp, const string src)
  {
   string why;
   const double px   = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double lots = TradeLots(px, isBuy, why);
   if(lots <= 0) { Log("NO ENTRY", why); return; }
   Log("ENTRY", StringFormat("%s %.2f lots  req=%s  SL=%s (%s)  TP=%s  RR 1:%.1f", isBuy ? "BUY" : "SELL", lots, P(px), P(sl), src, P(tp), RewardRisk));
   for(int attempt = 1; attempt <= 3; attempt++)
     {
      const double p  = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      const bool   ok = isBuy ? g_trade.Buy(lots, _Symbol, p, sl, tp, TradeComment) : g_trade.Sell(lots, _Symbol, p, sl, tp, TradeComment);
      const uint   rc = g_trade.ResultRetcode();
      if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         const double fill = g_trade.ResultPrice() > 0 ? g_trade.ResultPrice() : p;
         Log("FILL", StringFormat("%s %.2f @ %s  SL=%s  TP=%s  risk=%s  reward=%s", isBuy ? "BUY" : "SELL", lots, P(fill), P(sl), P(tp),
                                  DoubleToString(MathAbs(fill - sl), _Digits), DoubleToString(MathAbs(tp - fill), _Digits)));
         return;
        }
      Log("ORDER", StringFormat("attempt %d failed: retcode=%u %s", attempt, rc, g_trade.ResultRetcodeDescription()));
      if(rc != TRADE_RETCODE_REQUOTE && rc != TRADE_RETCODE_PRICE_CHANGED && rc != TRADE_RETCODE_PRICE_OFF && rc != TRADE_RETCODE_TIMEOUT)
         return;
      Sleep(300);
     }
  }

//+------------------------------------------------------------------+
//| One flip = one decision                                          |
//+------------------------------------------------------------------+
void ProcessSignal(const TwkSnapshot &s)
  {
   if((datetime)(long)(GlobalVariableCheck(SigGv()) ? GlobalVariableGet(SigGv()) : 0) == s.barTime)
      return;                                        // this flip was already handled
   GlobalVariableSet(SigGv(), (double)(long)s.barTime);
   const bool isBuy = (s.signal == TWK_SIG_LONG);
   Log("FLIP", StringFormat("%s on %s bar %s  close=%s  purple=%s", isBuy ? "LONG" : "SHORT", EnumToString(SignalTF()),
                            TimeToString(s.barTime, TIME_DATE | TIME_MINUTES), P(s.close), P(s.purple)));

   //--- the trade in the other direction ends at the flip
   int same = 0;
   if(OwnPositions(isBuy, same) > same)
     {
      if(!ReverseOnFlip)
        { Log("NO ENTRY", "trade open and ReverseOnFlip = false (Pine: enter only when flat)"); return; }
      if(!CloseOpposite(isBuy))
         return;                                     // never hold both sides
     }
   if(same > 0)
     { Log("NO ENTRY", "already in a trade in this direction"); return; }

   //--- the new trade
   string why;
   if(!EntriesAllowed(why)) { Log("NO ENTRY", why); return; }
   double sl, tp;
   string src;
   if(!TradeStops(isBuy, s, sl, tp, src, why)) { Log("NO ENTRY", why); return; }
   OpenTrade(isBuy, sl, tp, src);
  }

//+------------------------------------------------------------------+
//| Trailing: the purple line once in profit, then the profit lock   |
//+------------------------------------------------------------------+
string TrailGv(const ulong posId) { return StringFormat("TWKPINE.%I64u.%I64u.trail", MagicNumber, posId); }

void ManageTrailing()
  {
   if(!EnablePurpleTrail && LockTriggerPoints <= 0)
      return;
   if(TimeCurrent() - g_lastModifyFail < 2)
      return;                                        // the broker refused a moment ago
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
      return;
   const double stops  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   const double freeze = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL) * _Point;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      const bool   isBuy  = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      const double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      const double curSL  = PositionGetDouble(POSITION_SL);
      const double curTP  = PositionGetDouble(POSITION_TP);
      const ulong  posId  = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      const double profit = isBuy ? bid - entry : entry - ask;
      if(profit <= 0)
         continue;                                   // trail only once price has moved our way
      const double ref = isBuy ? bid : ask;
      if(freeze > 0 && ((curSL > 0 && MathAbs(ref - curSL) <= freeze) || (curTP > 0 && MathAbs(curTP - ref) <= freeze)))
         continue;                                   // broker freeze level: no change allowed now
      double best = curSL;
      string why  = "";
      int    src  = 0;
      //--- 1. the purple line, on the protective side of this trade
      if(EnablePurpleTrail && profit >= Pts(PurpleTrailStartPoints) && !TwkIsNa(g_purple) && g_stDir == (isBuy ? -1 : 1))
        {
         const double c = NormPrice(g_purple);
         if(best <= 0 || (isBuy ? c > best : c < best))
           { best = c; why = "purple line"; src = 1; }
        }
      //--- 2. the lock: at +LockTriggerPoints the SL goes to +LockProfitPoints
      if(LockTriggerPoints > 0 && profit >= Pts(LockTriggerPoints) - _Point / 2)
        {
         const double c = NormPrice(isBuy ? entry + Pts(LockProfitPoints) : entry - Pts(LockProfitPoints));
         if(best <= 0 || (isBuy ? c > best : c < best))
           { best = c; why = StringFormat("lock +%d pts", LockProfitPoints); src = 2; }
        }
      if(src == 0)
         continue;                                   // nothing tighter than the current SL
      if(isBuy ? !(best < bid - stops) : !(best > ask + stops))
         continue;                                   // too close to price for the broker: next tick
      if(curSL > 0 && src != 2 && MathAbs(best - curSL) < Pts(MinSLStepPoints) - _Point / 2)
         continue;                                   // tiny purple step: wait for a bigger one
      if(!g_trade.PositionModify(t, best, curTP))
        {
         g_lastModifyFail = TimeCurrent();
         Log("TRAIL FAILED", StringFormat("#%I64u SL -> %s (%s) retcode=%u %s", t, P(best), why,
                                          g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         continue;
        }
      Log("TRAIL", StringFormat("#%I64u SL %s -> %s (%s), profit %d pts", t, P(curSL), P(best), why, ToPts(profit)));
      const double prev = GlobalVariableCheck(TrailGv(posId)) ? GlobalVariableGet(TrailGv(posId)) : 0;
      GlobalVariableSet(TrailGv(posId), MathMax(prev, src));
     }
  }

//+------------------------------------------------------------------+
//| Exit log                                                         |
//+------------------------------------------------------------------+
string TradeLogName()
  {
   return StringFormat("TWK_pine_trades_%s_%I64u%s.csv", _Symbol, MagicNumber, IsTester() ? "_tester" : "");
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber || HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   const long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return;
   const long   reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   const ulong  pid    = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   const int    trail  = GlobalVariableCheck(TrailGv(pid)) ? (int)GlobalVariableGet(TrailGv(pid)) : 0;
   GlobalVariableDel(TrailGv(pid));
   const string why    = reason == DEAL_REASON_SL ? (trail == 2 ? "SL (locked profit)" : trail == 1 ? "SL (purple trail)" : "SL")
                       : reason == DEAL_REASON_TP ? "TP" : reason == DEAL_REASON_EXPERT ? "flip" : "other";
   if(reason == DEAL_REASON_SL) g_nSL++; else if(reason == DEAL_REASON_TP) g_nTP++; else if(reason == DEAL_REASON_EXPERT) g_nFlip++; else g_nOther++;
   const ulong  posId  = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   const double exitPx = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   const double pnl    = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   Log("EXIT", StringFormat("position %I64u closed @ %s  P/L=%.2f  reason=%s", posId, P(exitPx), pnl, why));
   if(!WriteTradeLog)
      return;
   //--- entry side, time, price and initial SL/TP from the opening deal and its order
   double inPx = 0, sl0 = 0, tp0 = 0, vol = 0;
   datetime inT = 0;
   long side = -1;
   if(HistorySelectByPosition(posId))
      for(int i = 0; i < HistoryDealsTotal(); i++)
        {
         const ulong d = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN)
            continue;
         inPx = HistoryDealGetDouble(d, DEAL_PRICE);
         vol  = HistoryDealGetDouble(d, DEAL_VOLUME);
         inT  = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         side = HistoryDealGetInteger(d, DEAL_TYPE);
         const ulong ord = (ulong)HistoryDealGetInteger(d, DEAL_ORDER);
         if(HistoryOrderSelect(ord))
           {
            sl0 = HistoryOrderGetDouble(ord, ORDER_SL);
            tp0 = HistoryOrderGetDouble(ord, ORDER_TP);
           }
        }
   const string name   = TradeLogName();
   const bool   exists = FileIsExist(name, FILE_COMMON);
   const int    h      = FileOpen(name, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   if(!exists)
      FileWrite(h, "position", "side", "volume", "open_time", "close_time", "entry", "initial_sl", "tp", "risk", "reward", "exit", "pnl", "exit_reason");
   FileWrite(h, (string)posId, side == DEAL_TYPE_BUY ? "BUY" : "SELL", DoubleToString(vol, 2),
             TimeToString(inT, TIME_DATE | TIME_SECONDS), TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
             P(inPx), P(sl0), P(tp0), DoubleToString(MathAbs(inPx - sl0), _Digits), DoubleToString(MathAbs(tp0 - inPx), _Digits),
             P(exitPx), DoubleToString(pnl, 2), why);
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Chart Tracker (display only)                                     |
//+------------------------------------------------------------------+
void AttachTracker()
  {
   if(!ShowTrackerOnChart || MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   if(!IsTester() && SignalTF() != (ENUM_TIMEFRAMES)_Period)
     {
      Log("CHART", StringFormat("signals are %s but this chart is %s - attach the EA to a %s chart to see the Tracker",
                                EnumToString(SignalTF()), EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(SignalTF())));
      return;
     }
   // exact input order of TWK_Tracker_MT5.mq5 (23 inputs, no `input group` lines)
   g_trackerHandle = iCustom(_Symbol, SignalTF(), TWK_TRACKER_RES,
                             TrailMultiplier, TrailATRLength, PivotStrength, RewardRisk, 20, TWK_TIE_LEFT_EQUAL_OK,
                             14, 14, ChartTrackerBars <= 0 ? 0 : MathMax(ChartTrackerBars, 300), false, 3000,
                             true, 24, MathMax(1, ChartBoxHistory),
                             0, 0, TWK_REFLIP_KEEP_PIVOT,                  // pure Pine stops
                             IsTester() ? TimeCurrent() : (datetime)0, "TWKPE_",
                             0.0, true, true, 20.0);                        // no filters: every box drawn alike
   if(g_trackerHandle == INVALID_HANDLE)
     {
      Log("CHART", StringFormat("Tracker not loaded (err %d) - trading is not affected", GetLastError()));
      return;
     }
   if(IsTester())
     {
      if(SignalTF() != (ENUM_TIMEFRAMES)_Period)
         PrintFormat("*** CHART: SignalTimeframe is %s but the tester Period is %s. Set the tester Period to %s to see the "
                     "purple line and boxes on the test chart. Trading is not affected. ***",
                     EnumToString(SignalTF()), EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(SignalTF()));
      return;                                        // the tester draws indicators the EA creates
     }
   if(!ChartIndicatorAdd(0, 0, g_trackerHandle))
      Log("CHART", StringFormat("Tracker not added to the chart (err %d) - trading is not affected", GetLastError()));
  }

void DetachTracker()
  {
   if(g_trackerHandle == INVALID_HANDLE || IsTester())
      return;                                        // the tester keeps it for the chart it opens after the test
   ChartIndicatorDelete(0, 0, TWK_TRACKER_NAME);
   IndicatorRelease(g_trackerHandle);
   g_trackerHandle = INVALID_HANDLE;
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(RewardRisk <= 0 || LotSize <= 0 || PurpleTrailStartPoints < 0 || LockTriggerPoints < 0 || LockProfitPoints < 0 || MinSLStepPoints < 0
      || (LockTriggerPoints > 0 && LockProfitPoints >= LockTriggerPoints))
     {
      Print("Invalid inputs: RewardRisk and LotSize must be > 0; points >= 0; "
            "LockProfitPoints must be below LockTriggerPoints");
      return INIT_PARAMETERS_INCORRECT;
     }
   TwkDefaultParams(g_p);
   g_p.stMult     = TrailMultiplier;
   g_p.stATR      = TrailATRLength;
   g_p.pivLen     = PivotStrength;
   g_p.rr         = RewardRisk;
   g_engine.Init(_Symbol, SignalTF(), 2000, g_p);

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(MaxDeviation);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetAsyncMode(false);
   if(IsTester() && WriteTradeLog)
      FileDelete(TradeLogName(), FILE_COMMON);       // a fresh trade CSV per test run

   PrintFormat("TWK Pine EA started on %s | account %I64d (%s) | signal TF %s | lot %.2f", _Symbol, AccountInfoInteger(ACCOUNT_LOGIN),
               IsTester() ? "TESTER" : AccountModeText(), EnumToString(SignalTF()), LotSize);
   PrintFormat("[CONFIG] Pine trades, no filters: SL = pivot (purple line if none), TP = RR 1:%.1f | reverse on flip %s | trail %s",
               RewardRisk, ReverseOnFlip ? "ON" : "OFF (enter only when flat)",
               StringFormat("%s, lock %s", EnablePurpleTrail ? StringFormat("purple line from +%d pts", PurpleTrailStartPoints) : "no purple",
                            LockTriggerPoints > 0 ? StringFormat("+%d pts at +%d pts", LockProfitPoints, LockTriggerPoints) : "off"));
   string why;
   if(!IsTester() && !EntriesAllowed(why))
      Print("*** SAFETY: ", why, ". The EA shows signals but will NOT open trades. ***");
   AttachTracker();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   PrintFormat("TWK Pine EA exits: SL %d | TP %d | closed on flip %d | other %d", g_nSL, g_nTP, g_nFlip, g_nOther);
   DetachTracker();
  }

void OnTick()
  {
   ManageTrailing();                                 // every tick: protection never waits for a new bar
   const datetime barTime = iTime(_Symbol, SignalTF(), 0);
   if(barTime == 0 || barTime == g_lastBarTime)
      return;                                        // decide once per closed signal bar, like Pine
   TwkSeries   series;
   TwkSnapshot s;
   if(!g_engine.Evaluate(1, s, series))
     {
      static string lastErr = "";
      if(s.error != lastErr)
         Log("DATA", "indicator not ready: " + s.error + " - retrying");
      lastErr = s.error;
      return;                                        // retry on the next tick
     }
   g_lastBarTime = barTime;
   g_purple = s.purple;                              // the purple line just moved to the new closed bar
   g_stDir  = s.stDir;
   if(s.signal != TWK_SIG_NONE)
      ProcessSignal(s);
   else
      ManageTrailing();
  }
