//+------------------------------------------------------------------+
//| GexSignalTrader.mq5                                              |
//| Places TWK-only trades from the Gold GEX page (gold_gex.html)    |
//+------------------------------------------------------------------+
#property version   "1.08"
#property description "Trades only qualifying TWK 15m signals of gold_gex.html on the chart's symbol."
#property description "The local agent (gex_agent.cjs) writes each signal to Common\\Files\\gex_signal.txt;"
#property description "this EA reads that file once a second, refuses all non-TWK signals, places TWK trades with stop and target,"
#property description "and reports back in gex_status.txt. TWK 15m signals require ADX > 20 and exactly 0.01 lots."
#property description "Demo accounts only unless InpAllowReal is set."
#include <Trade\Trade.mqh>

input double InpRiskPercent  = 1.0;      // Risk per trade, % of balance (used when Fixed lots = 0)
input double InpFixedLots    = 0.0;      // Fixed lots (0 = size from the risk %)
input double InpMaxLots      = 1.0;      // Never trade more than this many lots
input int    InpMaxSignalAge = 120;      // Ignore a signal older than this many seconds
input double InpMaxSpread    = 1.0;      // Skip when the spread is above this (price units, USD per oz)
input double InpCloseHours   = 4.0;      // Close the trade at the market after this many hours
input bool   InpDryRun       = false;    // true = report what it would do, place no order
input bool   InpAllowReal    = false;    // false = refuse to trade on a real account
input bool   InpPush         = true;     // Also send a push notification to the MT5 phone app
input long   InpMagic        = 20261106; // Magic number of this EA's trades

#define SIGNAL_FILE "gex_signal.txt"     // id;BUY|SELL;entry;stop;target;score;sent[;lots;source;adx] (UTC seconds)
#define STATUS_FILE "gex_status.txt"     // id;state;time (UTC seconds);message
#define ALIVE_FILE  "gex_ea.txt"         // time (UTC seconds);demo|real;server;symbol;balance;algo 1|0;dryrun 1|0
#define PRICE_FILE  "gex_price.txt"      // time (UTC seconds);symbol;bid;ask;seconds since the last tick;server   every second
                                         // (version 1.08, 25 Nov 2026: accept TWK 15m orders only)

CTrade   g_trade;
long     g_lastId = 0;                   // id of the last signal this EA has dealt with
string   g_gv;                           // terminal global variable that keeps g_lastId across restarts
datetime g_alive = 0;

//+------------------------------------------------------------------+
bool IsDemo() { return (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO; }
bool AlgoOn() { return TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED); }

void WriteLine(const string file, const string line)
  {
   int h = FileOpen(file, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, line + "\r\n");
   FileClose(h);
  }

// One line for the agent and the page, the Experts log, and for anything that matters a popup and a push.
void Report(const long id, const string state, const string text, const bool loud)
  {
   WriteLine(STATUS_FILE, StringFormat("%I64d;%s;%I64d;%s", id, state, (long)TimeGMT(), text));
   Print("GEX ", state, ": ", text);
   if(!loud)
      return;
   Alert("GEX ", _Symbol, ": ", text);
   if(InpPush && TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      SendNotification("GEX " + _Symbol + ": " + text);
  }

void Heartbeat()
  {
   g_alive = TimeLocal();
   WriteLine(ALIVE_FILE, StringFormat("%I64d;%s;%s;%s;%.2f;%d;%d", (long)TimeGMT(), IsDemo() ? "demo" : "real",
             AccountInfoString(ACCOUNT_SERVER), _Symbol, AccountInfoDouble(ACCOUNT_BALANCE), AlgoOn() ? 1 : 0, InpDryRun ? 1 : 0));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_gv = "GEX_last_id_" + IntegerToString(InpMagic);
   if(GlobalVariableCheck(g_gv))
      g_lastId = (long)GlobalVariableGet(g_gv);
   // a signal file left from earlier must not be traded when the EA starts
   long id, ignoredId = 0;
   string p[];
   if(ReadSignal(id, p) && id != g_lastId)
     {
      g_lastId = id;
      GlobalVariableSet(g_gv, (double)id);
      ignoredId = id;
     }
   EventSetTimer(1);
   Heartbeat();
   Report(0, "ready", StringFormat("EA ready on %s, %s account%s", _Symbol, IsDemo() ? "demo" : "REAL",
          (!IsDemo() && !InpAllowReal) ? ": trading refused (real account)" : (InpDryRun ? ", dry run: no orders" : "")), false);
   if(ignoredId > 0)
      Report(ignoredId, "ignored", "signal already pending when the EA started; ignored to avoid a late entry", false);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   FileDelete(ALIVE_FILE, FILE_COMMON);   // the page then shows that the EA is no longer attached
   FileDelete(PRICE_FILE, FILE_COMMON);   // and goes back to its own price reference
  }

void OnTick() { }

// The broker's current bid and ask for the page: it moves its candles (Binance futures) to this price level, so
// the price on the page is the price on this chart. Tick age tells the page when the market is not moving.
void WritePrice()
  {
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t) || t.bid <= 0)
      return;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   long age = (long)(TimeTradeServer() - t.time);
   WriteLine(PRICE_FILE, StringFormat("%I64d;%s;%s;%s;%I64d;%s", (long)TimeGMT(), _Symbol, DoubleToString(t.bid, digits),
             DoubleToString(t.ask, digits), age < 0 ? 0 : age, AccountInfoString(ACCOUNT_SERVER)));
  }

void OnTimer()
  {
   WritePrice();
   if(TimeLocal() - g_alive >= 5)
      Heartbeat();
   CheckSignal();
   CheckTimeLimit();
  }

//+------------------------------------------------------------------+
bool ReadSignal(long &id, string &p[])
  {
   int h = FileOpen(SIGNAL_FILE, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
      return false;                       // no signal has been written yet
   string line = FileReadString(h);
   FileClose(h);
   if(StringSplit(line, ';', p) < 7)
      return false;
   id = StringToInteger(p[0]);
   return id > 0;
  }

bool HavePosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ticket = PositionGetTicket(i);
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && (magic == InpMagic || magic == InpMagic + 1))
         return true;
     }
   return false;
  }

// Lots from the risk %: the loss at the stop, for one lot, in account currency.
double Lots(const double slDist, string &note)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double maxLot = MathMin(InpMaxLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
   double lots = InpFixedLots;
   if(lots <= 0)
     {
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double lossPerLot = (tickSize > 0) ? slDist / tickSize * tickValue : 0;
      lots = (lossPerLot > 0) ? AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0 / lossPerLot : minLot;
     }
   if(step > 0)
      lots = MathFloor(lots / step + 1e-9) * step;
   if(lots < minLot)
     {
      lots = minLot;
      note = " (smallest lot: risk is above the set %)";
     }
   return NormalizeDouble(MathMin(maxLot, lots), 2);
  }

void CheckSignal()
  {
   long id;
   string p[];
   if(!ReadSignal(id, p) || id == g_lastId)
      return;
   g_lastId = id;                         // every signal is dealt with once, whatever the outcome
   GlobalVariableSet(g_gv, (double)id);

   bool   buy = (p[1] == "BUY");
   double entry = StringToDouble(p[2]), stop = StringToDouble(p[3]), target = StringToDouble(p[4]);
   double slDist = MathAbs(entry - stop), tpDist = MathAbs(target - entry);
   long   age = (long)TimeGMT() - StringToInteger(p[6]);
   string source = ArraySize(p) > 8 ? p[8] : "";
   bool   twk = (source == "TWK 15m");
   double requestedLots = ArraySize(p) > 7 ? StringToDouble(p[7]) : 0;
   double signalAdx = ArraySize(p) > 9 ? StringToDouble(p[9]) : 0;
   string what = StringFormat("%s %s signal (score %s)", source == "" ? "GEX" : source, p[1], p[5]);

   if(source != "TWK 15m")
     { Report(id, "refused", what + " not traded: TWK-only mode", true); return; }
   if((p[1] != "BUY" && p[1] != "SELL") || slDist <= 0 || tpDist <= 0)
     { Report(id, "rejected", what + ": the signal line is not valid", true); return; }
   if(age > InpMaxSignalAge || age < -60)
     { Report(id, "ignored", StringFormat("%s ignored: it is %I64d s old (limit %d s)", what, age, InpMaxSignalAge), true); return; }
   if(!IsDemo() && !InpAllowReal)
     { Report(id, "refused", what + " not traded: this is a real account", true); return; }
   if(twk && MathAbs(requestedLots - 0.01) > 0.0000001)
     { Report(id, "rejected", what + ": TWK orders require exactly 0.01 lots", true); return; }
   if(twk && !(signalAdx > 20.0))
     { Report(id, "rejected", StringFormat("%s not traded: 15-minute ADX %.2f must be above 20", what, signalAdx), true); return; }
   if(!AlgoOn() && !InpDryRun)
     { Report(id, "refused", what + " not traded: Algo Trading is switched off in MT5", true); return; }
   ulong reverseTickets[];
   int  reverseCount = 0;
   bool sameTwkPosition = false, otherEaPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(magic != InpMagic && magic != InpMagic + 1)
        {
         otherEaPosition = true;                 // do not net a TWK reversal against a manual or other EA position
         continue;
        }
      if(twk && magic == InpMagic + 1)
        {
         ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         bool sameSide = (buy && posType == POSITION_TYPE_BUY) || (!buy && posType == POSITION_TYPE_SELL);
         if(sameSide)
            sameTwkPosition = true;
         else
           {
            ArrayResize(reverseTickets, reverseCount + 1);
            reverseTickets[reverseCount++] = ticket;
           }
        }
      else
         otherEaPosition = true;
     }
   if(sameTwkPosition)
     { Report(id, "skipped", what + " skipped: a TWK position is already open in this direction", true); return; }
   if(otherEaPosition)
     { Report(id, "skipped", what + " skipped: a non-TWK position is already open on this symbol", true); return; }
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t) || t.bid <= 0 || t.ask <= 0)
     { Report(id, "rejected", what + " not traded: no price for " + _Symbol, true); return; }
   if(t.ask - t.bid > InpMaxSpread)
     { Report(id, "skipped", StringFormat("%s skipped: spread %.2f is above %.2f", what, t.ask - t.bid, InpMaxSpread), true); return; }

   // The page gives stop/target distances. Anchor them to the entry side of the quote (ask for a buy, bid for a
   // sell); anchoring a buy to bid would add the spread to its risk and reduce the requested reward/risk ratio.
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double ref = buy ? t.ask : t.bid;
   double sl = NormalizeDouble(buy ? ref - slDist : ref + slDist, digits), tp = NormalizeDouble(buy ? ref + tpDist : ref - tpDist, digits);
   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(slDist < minDist || tpDist < minDist)
     { Report(id, "rejected", StringFormat("%s not traded: stop or target is closer than the broker allows (%.2f)", what, minDist), true); return; }
   string note = "";
   double lots = requestedLots > 0 ? requestedLots : Lots(slDist, note);
   if(requestedLots > 0)
     {
      double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), maxLot = MathMin(InpMaxLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double stepsFromMin = (step > 0 ? (lots - minLot) / step : 0);
      if(lots < minLot - 0.0000001 || lots > maxLot + 0.0000001 || step <= 0 || MathAbs(stepsFromMin - MathRound(stepsFromMin)) > 0.0001)
        { Report(id, "rejected", StringFormat("%s not traded: requested %.2f lots is not supported by this symbol (min %.2f, step %.2f, max %.2f)", what, lots, minLot, step, maxLot), true); return; }
     }
   string plan = StringFormat("%s %.2f lots, stop %s, target %s%s", p[1], lots, DoubleToString(sl, digits), DoubleToString(tp, digits), note);

   if(InpDryRun)
     { Report(id, "dryrun", "Dry run, no order placed: " + (reverseCount > 0 ? "would close the opposite TWK position and reverse; " : "") + plan, true); return; }
   for(int i = reverseCount - 1; i >= 0; i--)
     {
      ulong ticket = reverseTickets[i];
      if(!PositionSelectByTicket(ticket))
         continue;
      g_trade.SetExpertMagicNumber(InpMagic + 1);
      bool closeOk = g_trade.PositionClose(ticket);
      uint closeCode = g_trade.ResultRetcode();
      string closeError = g_trade.ResultRetcodeDescription();
      if(!closeOk || closeCode != TRADE_RETCODE_DONE)
        {
         g_trade.SetExpertMagicNumber(InpMagic);
         Report(id, "failed", StringFormat("%s flip not entered: could not close the existing TWK position #%I64u: %s (code %u)",
                what, ticket, closeError, closeCode), true);
         return;
        }
     }
   ulong remainingPosition;
   if(reverseCount > 0 && HavePosition(remainingPosition))
     {
      g_trade.SetExpertMagicNumber(InpMagic);
      Report(id, "failed", what + " flip not entered: an existing GEX/TWK position remains open after the close request", true);
      return;
     }
   string comment = (source == "" ? "GEX" : source) + " " + p[1] + " s" + p[5];
   long orderMagic = twk ? InpMagic + 1 : InpMagic;
   g_trade.SetExpertMagicNumber(orderMagic);
   bool ok = buy ? g_trade.Buy(lots, _Symbol, 0, sl, tp, comment) : g_trade.Sell(lots, _Symbol, 0, sl, tp, comment);
   uint code = g_trade.ResultRetcode();
   double fill = g_trade.ResultPrice();
   if(ok && (code == TRADE_RETCODE_DONE || code == TRADE_RETCODE_PLACED || code == TRADE_RETCODE_DONE_PARTIAL))
     {
      // Market execution can slip from the quote used above. Re-anchor the bracket to the actual fill so a
      // The signal's requested risk/reward stays intact in the position MT5 displays; initial protective SL/TP were sent with it.
      if(fill <= 0)
         fill = ref;
      double filledSl = NormalizeDouble(buy ? fill - slDist : fill + slDist, digits);
      double filledTp = NormalizeDouble(buy ? fill + tpDist : fill - tpDist, digits);
      ulong positionTicket = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong candidate = PositionGetTicket(i);
         if(candidate > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == orderMagic)
           { positionTicket = candidate; break; }
        }
      bool adjusted = false;
      uint adjustCode = 0;
      string adjustError = "the filled position was not found";
      if(positionTicket > 0)
        {
         adjusted = g_trade.PositionModify(positionTicket, filledSl, filledTp);
         adjustCode = g_trade.ResultRetcode();
         adjustError = g_trade.ResultRetcodeDescription();
        }
      g_trade.SetExpertMagicNumber(InpMagic);
      if(adjusted && (adjustCode == TRADE_RETCODE_DONE || adjustCode == TRADE_RETCODE_NO_CHANGES))
         Report(id, "placed", StringFormat("%s %.2f lots, stop %s, target %s at %s (SL/TP adjusted to fill)%s", p[1], lots,
                DoubleToString(filledSl, digits), DoubleToString(filledTp, digits), DoubleToString(fill, digits),
                reverseCount > 0 ? "; reversed the existing TWK position" : ""), true);
      else
         Report(id, "placed", StringFormat("%s %.2f lots at %s; protective stop %s and target %s remain; post-fill SL/TP adjustment failed: %s%s",
                p[1], lots, DoubleToString(fill, digits), DoubleToString(sl, digits), DoubleToString(tp, digits), adjustError,
                reverseCount > 0 ? "; reversed the existing TWK position" : ""), true);
      return;
     }
   g_trade.SetExpertMagicNumber(InpMagic);
   string failure = StringFormat("%s order failed: %s (code %u)", what, g_trade.ResultRetcodeDescription(), code);
   if(reverseCount > 0)
      failure += "; the previous TWK position was closed before this order was sent";
   Report(id, "failed", failure, true);
  }

// GEX ideas close after four hours. TWK positions are managed by their stop or target.
void CheckTimeLimit()
  {
   if(InpCloseHours <= 0)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;                         // TWK trades remain open until their stop or target is hit
      if(TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) < (long)(InpCloseHours * 3600))
         continue;
      g_trade.SetExpertMagicNumber(InpMagic);
      if(!g_trade.PositionClose(ticket))
         Print("GEX: could not close ", ticket, " at the time limit: ", g_trade.ResultRetcodeDescription());
     }
  }

// Was this position opened by this EA? The closing deal cannot tell: it carries the magic number of
// whoever closed it (0 when closed by hand, another EA's number when another EA closed it).
bool OpenedByThisEA(const long positionId)
  {
   if(!HistorySelectByPosition(positionId))
      return false;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      long magic = HistoryDealGetInteger(d, DEAL_MAGIC);
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN && (magic == InpMagic || magic == InpMagic + 1))
         return true;
     }
   return false;
  }

// A closing deal of one of this EA's trades: report how it ended and who closed it.
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol || (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT)
      return;
   // read the closing deal first: looking up the position's history below changes the selected history
   long   positionId = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID), closedBy = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double money = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   ENUM_DEAL_REASON reason = (ENUM_DEAL_REASON)HistoryDealGetInteger(trans.deal, DEAL_REASON);
   if(!OpenedByThisEA(positionId))
      return;
   string why = (reason == DEAL_REASON_TP) ? "target hit" : (reason == DEAL_REASON_SL) ? "stop hit" : "closed by hand";
   if(reason == DEAL_REASON_EXPERT)
      why = (closedBy == InpMagic || closedBy == InpMagic + 1) ? "time limit" : StringFormat("closed by ANOTHER EA (magic %I64d)", closedBy);
   Report(g_lastId, "closed", StringFormat("trade closed at %s, %s: %+.2f %s", DoubleToString(price, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
          why, money, AccountInfoString(ACCOUNT_CURRENCY)), true);
  }
//+------------------------------------------------------------------+
