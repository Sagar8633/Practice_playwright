"""SimpleSMA18Bot_H4_Final.mq5 v2.11: a rejected partial-close request (XM rejects market orders with
"market closed" for the first minutes after the Monday 01:00 open) is retried after PartialRetrySeconds
instead of being marked done. The 27 Sep 2026 tester log lost three partial exits this way."""
import os, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT)
DST = os.path.join(VAIB, "SimpleSMA18Bot_H4_Final.mq5")
s = open(DST, encoding="utf-8").read()
if "PartialRetrySeconds" in s:
    print("already v2.11"); raise SystemExit
shutil.copy(DST, DST + ".bak_v210")


def sub(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


sub("//|          Version 2.10-H4 (27 Sep 2026)                           |\n",
    "//|          Version 2.11-H4 (27 Sep 2026)                           |\n"
    "//|  v2.11: a partial-close request rejected by the server (XM       |\n"
    "//|   answers 'market closed' for a few minutes after the Monday     |\n"
    "//|   01:00 open) is retried after PartialRetrySeconds instead of    |\n"
    "//|   being marked as done; the reject reason is printed.            |\n")
sub("input double PartialLossPercent    = 50.0;    // share of the position volume to close\n",
    "input double PartialLossPercent    = 50.0;    // share of the position volume to close\n"
    "input int    PartialRetrySeconds   = 60;      // v2.11: wait this long after a rejected partial-close request before retrying\n")
sub("bool   PartialLossDone = false;  // loss-side partial exit already taken (v2.10)",
    "bool   PartialLossDone = false;  // loss-side partial exit already taken (v2.10)\ndatetime NextPartialRetry = 0;   // v2.11: earliest time of the next partial-exit attempt after a rejected request")
old_mgr = s[s.index("void ManagePartialExit()"): s.index("//+------------------------------------------------------------------+\n//| Break-even")]
new_mgr = r'''#define PARTIAL_DONE     1   // request executed (a share, or the whole position, was closed)
#define PARTIAL_SKIPPED  0   // nothing to do for this position (share below the broker minimum lot)
#define PARTIAL_RETRY   -1   // request rejected by the server (e.g. "market closed" at the Monday open): try again later

void ManagePartialExit()
{
   if(!PositionSelect(_Symbol))
      return;

   if(NextPartialRetry > 0 && TimeCurrent() < NextPartialRetry)
      return;   // a previous request was rejected; wait PartialRetrySeconds before the next attempt

   double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   double volume = PositionGetDouble(POSITION_VOLUME);
   ulong  ticket = PositionGetInteger(POSITION_TICKET);
   int    tier   = TierFromVolume(volume);

   //---- loss side first: a bar can reach both levels, the adverse one is the conservative reading
   if(EnablePartialLossExit && !PartialLossDone && profit <= -PartialLossTriggerUSD(volume))
   {
      int rc = DoPartialClose(ticket, volume, PartialLossPercent, profit, tier, "loss-side");

      if(rc == PARTIAL_RETRY)
      {
         NextPartialRetry = TimeCurrent() + PartialRetrySeconds;
         return;
      }

      PartialLossDone  = true;   // executed, or skipped for good (share below the minimum lot)
      NextPartialRetry = 0;

      if(!PositionSelect(_Symbol))
         return;

      volume = PositionGetDouble(POSITION_VOLUME);
      profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   //---- profit side
   if(EnablePartialExit && !PartialDone && profit >= PartialTriggerUSD(volume))
   {
      int rc = DoPartialClose(ticket, volume, PartialExitPercent, profit, tier, "profit-side");

      if(rc == PARTIAL_RETRY)
      {
         NextPartialRetry = TimeCurrent() + PartialRetrySeconds;
         return;
      }

      PartialDone      = true;
      NextPartialRetry = 0;
   }
}

//+------------------------------------------------------------------+
//| Close a share of the position (or all of it at the minimum lot). |
//| Returns PARTIAL_DONE, PARTIAL_SKIPPED or PARTIAL_RETRY (v2.11).  |
//+------------------------------------------------------------------+
int DoPartialClose(ulong ticket, double volume, double percent, double profit, int tier, string which)
{
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double share = volume * percent / 100.0;

   if(vstep > 0.0)
      share = MathFloor(share / vstep + 1e-9) * vstep;

   if(share < vmin || volume - share < vmin)
   {
      // the share (or the remainder) is below the broker minimum
      if(PartialAtMinLot == PARTIAL_CLOSE_ALL)
      {
         if(trade.PositionClose(ticket))
         {
            Print("Partial exit (", which, "): whole position closed at floating ", DoubleToString(profit, 2), " (share below minimum lot)");
            return PARTIAL_DONE;
         }

         Print("Partial exit (", which, ") close-all request rejected: ", trade.ResultRetcodeDescription(), " (retcode ", trade.ResultRetcode(),
               ", error ", GetLastError(), "), retry in ", PartialRetrySeconds, " s");
         return PARTIAL_RETRY;
      }

      Print("Partial exit (", which, ") skipped: ", DoubleToString(percent, 0), "% of ", DoubleToString(volume, 2), " lot is below the minimum lot");
      return PARTIAL_SKIPPED;
   }

   if(trade.PositionClosePartial(ticket, NormalizeDouble(share, 2)))
   {
      Print("Partial exit (", which, "): closed ", DoubleToString(share, 2), " of ", DoubleToString(volume, 2), " lot at floating ", DoubleToString(profit, 2), " (tier ", tier, ")");
      return PARTIAL_DONE;
   }

   Print("Partial exit (", which, ") request rejected: ", trade.ResultRetcodeDescription(), " (retcode ", trade.ResultRetcode(),
         ", error ", GetLastError(), "), retry in ", PartialRetrySeconds, " s");
   return PARTIAL_RETRY;
}

'''
s = s.replace(old_mgr, new_mgr)
sub("   PartialDone = false;\n   PartialLossDone = false;", "   PartialDone = false;\n   PartialLossDone = false;\n   NextPartialRetry = 0;")
assert "void DoPartialClose" not in s and s.count("PartialRetrySeconds") >= 5
open(DST, "w", encoding="utf-8").write(s); print("written v2.11", len(s.splitlines()), "lines")
ME = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"; inc = r"C:\Users\samja\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"; log = os.path.join(HERE, "results", "compile_v211.log")
subprocess.run([ME, f"/compile:{DST}", f"/include:{inc}", f"/log:{log}"], timeout=180)
txt = open(log, encoding="utf-16", errors="replace").read(); print("\n".join(l for l in txt.splitlines() if "error" in l.lower() or "warning" in l.lower() or "Result" in l)[-1500:])
ex5 = DST.replace(".mq5", ".ex5"); print("ex5 present:", os.path.exists(ex5))
if os.path.exists(ex5) and "0 errors" in txt:
    for dstdir in [os.path.join(inc, "Experts", "4HR"), os.path.join(VAIB, "reports")]:
        if os.path.isdir(dstdir):
            shutil.copy(DST, dstdir); shutil.copy(ex5, dstdir); print("copied to", dstdir)
