//+------------------------------------------------------------------+
//| GexSignalTrader.mq5                                              |
//| Places the trades that the Gold GEX page (gold_gex.html) signals |
//+------------------------------------------------------------------+
#property version   "1.00"
#property description "Trades the BUY / SELL signals of gold_gex.html on the chart's symbol."
#property description "The local agent (gex_agent.cjs) writes each signal to Common\\Files\\gex_signal.txt;"
#property description "this EA reads that file once a second, places the trade with stop and target,"
#property description "and reports back in gex_status.txt. Demo accounts only unless InpAllowReal is set."
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

#define SIGNAL_FILE "gex_signal.txt"     // id;BUY|SELL;entry;stop;target;score;sent (UTC seconds)
#define STATUS_FILE "gex_status.txt"     // id;state;time (UTC seconds);message
#define ALIVE_FILE  "gex_ea.txt"         // time (UTC seconds);demo|real;server;symbol;balance;algo 1|0;dryrun 1|0

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
   long id;
   string p[];
   if(ReadSignal(id, p) && id != g_lastId)
     {
      g_lastId = id;
      GlobalVariableSet(g_gv, (double)id);
     }
   EventSetTimer(1);
   Heartbeat();
   Report(g_lastId, "ready", StringFormat("EA ready on %s, %s account%s", _Symbol, IsDemo() ? "demo" : "REAL",
          (!IsDemo() && !InpAllowReal) ? ": trading refused (real account)" : (InpDryRun ? ", dry run: no orders" : "")), false);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   FileDelete(ALIVE_FILE, FILE_COMMON);   // the page then shows that the EA is no longer attached
  }

void OnTick() { }

void OnTimer()
  {
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
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
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
   string what = StringFormat("%s signal (score %s)", p[1], p[5]);

   if((p[1] != "BUY" && p[1] != "SELL") || slDist <= 0 || tpDist <= 0)
     { Report(id, "rejected", what + ": the signal line is not valid", true); return; }
   if(age > InpMaxSignalAge || age < -60)
     { Report(id, "ignored", StringFormat("%s ignored: it is %I64d s old (limit %d s)", what, age, InpMaxSignalAge), true); return; }
   if(!IsDemo() && !InpAllowReal)
     { Report(id, "refused", what + " not traded: this is a real account", true); return; }
   if(!AlgoOn() && !InpDryRun)
     { Report(id, "refused", what + " not traded: Algo Trading is switched off in MT5", true); return; }
   ulong open;
   if(HavePosition(open))
     { Report(id, "skipped", what + " skipped: a GEX trade is already open", true); return; }
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t) || t.bid <= 0 || t.ask <= 0)
     { Report(id, "rejected", what + " not traded: no price for " + _Symbol, true); return; }
   if(t.ask - t.bid > InpMaxSpread)
     { Report(id, "skipped", StringFormat("%s skipped: spread %.2f is above %.2f", what, t.ask - t.bid, InpMaxSpread), true); return; }

   // The page gives distances, not broker prices: keep the same stop and target distance from where this
   // broker is now. A buy closes on the bid, a sell closes on the ask, so each side is measured from that price.
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double ref = buy ? t.bid : t.ask;
   double sl = NormalizeDouble(buy ? ref - slDist : ref + slDist, digits), tp = NormalizeDouble(buy ? ref + tpDist : ref - tpDist, digits);
   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(slDist < minDist || tpDist < minDist)
     { Report(id, "rejected", StringFormat("%s not traded: stop or target is closer than the broker allows (%.2f)", what, minDist), true); return; }
   string note = "";
   double lots = Lots(slDist, note);
   string plan = StringFormat("%s %.2f lots, stop %s, target %s%s", p[1], lots, DoubleToString(sl, digits), DoubleToString(tp, digits), note);

   if(InpDryRun)
     { Report(id, "dryrun", "Dry run, no order placed: " + plan, true); return; }
   string comment = "GEX " + p[1] + " s" + p[5];
   bool ok = buy ? g_trade.Buy(lots, _Symbol, 0, sl, tp, comment) : g_trade.Sell(lots, _Symbol, 0, sl, tp, comment);
   uint code = g_trade.ResultRetcode();
   if(ok && (code == TRADE_RETCODE_DONE || code == TRADE_RETCODE_PLACED || code == TRADE_RETCODE_DONE_PARTIAL))
      Report(id, "placed", StringFormat("%s at %s", plan, DoubleToString(g_trade.ResultPrice(), digits)), true);
   else
      Report(id, "failed", StringFormat("%s order failed: %s (code %u)", what, g_trade.ResultRetcodeDescription(), code), true);
  }

// The page closes an idea after 4 hours; so does this.
void CheckTimeLimit()
  {
   ulong ticket;
   if(InpCloseHours <= 0 || !HavePosition(ticket))
      return;
   if(TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) < (long)(InpCloseHours * 3600))
      return;
   if(!g_trade.PositionClose(ticket))
      Print("GEX: could not close ", ticket, " at the time limit: ", g_trade.ResultRetcodeDescription());
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
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN && HistoryDealGetInteger(d, DEAL_MAGIC) == InpMagic)
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
      why = (closedBy == InpMagic) ? "time limit" : StringFormat("closed by ANOTHER EA (magic %I64d)", closedBy);
   Report(g_lastId, "closed", StringFormat("trade closed at %s, %s: %+.2f %s", DoubleToString(price, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
          why, money, AccountInfoString(ACCOUNT_CURRENCY)), true);
  }
//+------------------------------------------------------------------+
