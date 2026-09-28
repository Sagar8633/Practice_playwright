"""SimpleSMA18Bot_H4_Final.mq5 v2.1: linear lot progression (LotMode LOT_LINEAR: BaseLot per BaseBalance of balance,
0.01 -> 0.02 -> 0.03 ...; LOT_DOUBLING kept), per-lot partial-profit target, and a loss-side partial exit."""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT)
DST = os.path.join(VAIB, "SimpleSMA18Bot_H4_Final.mq5")
s = open(DST, encoding="utf-8").read()
if "LOT_LINEAR" in s:
    print("already v2.1"); raise SystemExit


def sub(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


sub("//|                                      SimpleSMA18Bot_H4_Final.mq5 |\n//|          Version 2.00-H4 (study 4 final, 27 Sep 2026)            |",
    "//|                                      SimpleSMA18Bot_H4_Final.mq5 |\n//|          Version 2.10-H4 (27 Sep 2026)                           |\n"
    "//|  v2.10: LotMode LOT_LINEAR (lot = BaseLot x floor(balance /      |\n"
    "//|   BaseBalance): 0.01, 0.02, 0.03 ... one step per BaseBalance)   |\n"
    "//|   with LOT_DOUBLING still selectable; partial-profit target =    |\n"
    "//|   max(PartialProfitMinUSD, PartialProfitPerLot01 x lot / 0.01)   |\n"
    "//|   (0.02 -> $100, 0.04 -> $200, same as before); NEW loss-side    |\n"
    "//|   partial exit: when the floating loss reaches                   |\n"
    "//|   max(PartialLossMinUSD, PartialLossPerLot01 x lot / 0.01), close|\n"
    "//|   PartialLossPercent of the volume, once per position.           |")
# ---- inputs: lot mode + per-lot partial targets + loss partial
sub("input bool   UseDynamicLots        = true;    // lot from the balance tier; false = fixed LotSize\n",
    "enum ENUM_LOT_MODE\n{\n   LOT_DOUBLING = 0,   // lot doubles each time the balance doubles (0.01, 0.02, 0.04, 0.08 ...)\n   LOT_LINEAR   = 1    // one BaseLot step per BaseBalance of balance (0.01, 0.02, 0.03, 0.04 ...)\n};\n\n"
    "input bool   UseDynamicLots        = true;    // lot from the balance; false = fixed LotSize\ninput ENUM_LOT_MODE LotMode       = LOT_LINEAR;\n")
sub("input double PartialProfitBaseUSD  = 100.0;   // floating profit that triggers the partial close at tiers 0 and 1\ninput bool   PartialProfitDoubles  = true;    // from tier 2 the trigger doubles with each tier (200, 400, ...)\n",
    "input double PartialProfitPerLot01 = 50.0;    // floating profit per 0.01 lot that triggers the partial close (0.02 -> $100, 0.04 -> $200)\ninput double PartialProfitMinUSD   = 100.0;   // floor of the trigger (so a 0.01-lot position uses $100)\n")
sub("input ENUM_PARTIAL_MIN_LOT PartialAtMinLot = PARTIAL_SKIP;\n",
    "input ENUM_PARTIAL_MIN_LOT PartialAtMinLot = PARTIAL_SKIP;\n\n//================ LOSS-SIDE PARTIAL EXIT (v2.10) ===================\n\n"
    "input bool   EnablePartialLossExit = true;\ninput double PartialLossPerLot01   = 50.0;    // floating loss per 0.01 lot that triggers the partial close\ninput double PartialLossMinUSD     = 100.0;   // floor of the trigger\ninput double PartialLossPercent    = 50.0;    // share of the position volume to close\n")
# ---- globals
sub("bool   PartialDone = false;  // partial exit already taken for this position (study 4)", "bool   PartialDone = false;  // profit-side partial exit already taken for this position (study 4)\nbool   PartialLossDone = false;  // loss-side partial exit already taken (v2.10)")
# ---- lot functions
sub("double TierLot(int tier)\n{\n   double lot = BaseLot * MathPow(2.0, tier);\n",
    "double TierLot(int tier)\n{\n   double lot = (LotMode == LOT_LINEAR) ? BaseLot * (tier + 1) : BaseLot * MathPow(2.0, tier);\n")
sub("double CurrentLot()\n{\n   if(!UseDynamicLots)\n      return NormalizeLot(LotSize);\n\n   return TierLot(BalanceTier(AccountInfoDouble(ACCOUNT_BALANCE)));\n}",
    "double CurrentLot()\n{\n   if(!UseDynamicLots)\n      return NormalizeLot(LotSize);\n\n   double balance = AccountInfoDouble(ACCOUNT_BALANCE);\n\n   if(LotMode == LOT_LINEAR)\n   {\n      int steps = (BaseBalance > 0.0) ? (int)MathFloor(balance / BaseBalance + 1e-9) : 1;\n\n      if(steps < 1)\n         steps = 1;\n\n      return TierLot(steps - 1);\n   }\n\n   return TierLot(BalanceTier(balance));\n}")
sub("int TierFromVolume(double volume)\n{\n   if(BaseLot <= 0.0 || volume <= BaseLot)\n      return 0;\n\n   int tier = (int)MathRound(MathLog(volume / BaseLot) / MathLog(2.0));\n",
    "int TierFromVolume(double volume)\n{\n   if(BaseLot <= 0.0 || volume <= BaseLot)\n      return 0;\n\n   int tier = (LotMode == LOT_LINEAR) ? (int)MathRound(volume / BaseLot) - 1 : (int)MathRound(MathLog(volume / BaseLot) / MathLog(2.0));\n")
# ---- targets per lot
sub("double PartialTriggerUSD(int tier)\n{\n   if(PartialProfitDoubles && tier >= 2)\n      return PartialProfitBaseUSD * MathPow(2.0, tier - 1);\n\n   return PartialProfitBaseUSD;\n}",
    "double PartialTriggerUSD(double volume)\n{\n   return MathMax(PartialProfitMinUSD, PartialProfitPerLot01 * volume / 0.01);\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Floating-loss trigger of the loss-side partial exit (v2.10)      |\n//+------------------------------------------------------------------+\n"
    "double PartialLossTriggerUSD(double volume)\n{\n   return MathMax(PartialLossMinUSD, PartialLossPerLot01 * volume / 0.01);\n}")
# ---- partial exit manager: both sides
old_mgr = s[s.index("void ManagePartialExit()"): s.index("//+------------------------------------------------------------------+\n//| Break-even")]
new_mgr = r'''void ManagePartialExit()
{
   if(!PositionSelect(_Symbol))
      return;

   double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   double volume = PositionGetDouble(POSITION_VOLUME);
   ulong  ticket = PositionGetInteger(POSITION_TICKET);
   int    tier   = TierFromVolume(volume);

   //---- loss side first: a bar can reach both levels, the adverse one is the conservative reading
   if(EnablePartialLossExit && !PartialLossDone && profit <= -PartialLossTriggerUSD(volume))
   {
      PartialLossDone = true;
      DoPartialClose(ticket, volume, PartialLossPercent, profit, tier, "loss-side");

      if(!PositionSelect(_Symbol))
         return;

      volume = PositionGetDouble(POSITION_VOLUME);
      profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   //---- profit side
   if(EnablePartialExit && !PartialDone && profit >= PartialTriggerUSD(volume))
   {
      PartialDone = true;
      DoPartialClose(ticket, volume, PartialExitPercent, profit, tier, "profit-side");
   }
}

//+------------------------------------------------------------------+
//| Close a share of the position (or all of it at the minimum lot)  |
//+------------------------------------------------------------------+
void DoPartialClose(ulong ticket, double volume, double percent, double profit, int tier, string which)
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
            Print("Partial exit (", which, "): whole position closed at floating ", DoubleToString(profit, 2), " (share below minimum lot)");
      }
      else
         Print("Partial exit (", which, ") skipped: ", DoubleToString(percent, 0), "% of ", DoubleToString(volume, 2), " lot is below the minimum lot");

      return;
   }

   if(trade.PositionClosePartial(ticket, NormalizeDouble(share, 2)))
      Print("Partial exit (", which, "): closed ", DoubleToString(share, 2), " of ", DoubleToString(volume, 2), " lot at floating ", DoubleToString(profit, 2), " (tier ", tier, ")");
   else
      Print("Partial exit (", which, ") failed. Error = ", GetLastError());
}

'''
s = s.replace(old_mgr, new_mgr)
# ---- reset both flags on a new position
sub("   EntryTier = TierFromVolume(PositionGetDouble(POSITION_VOLUME));\n   PartialDone = false;", "   EntryTier = TierFromVolume(PositionGetDouble(POSITION_VOLUME));\n   PartialDone = false;\n   PartialLossDone = false;")
# ---- init print
sub('" | partial exit ", EnablePartialExit, " at ", PartialProfitBaseUSD, " USD (x2 from tier 2), ", PartialExitPercent, "%");',
    '" | lot mode ", (LotMode == LOT_LINEAR ? "LINEAR" : "DOUBLING"), " | partial exit ", EnablePartialExit, " at ", PartialProfitPerLot01, " USD per 0.01 lot (min ", PartialProfitMinUSD, "), ", PartialExitPercent,\n         "% | loss-side partial ", EnablePartialLossExit, " at ", PartialLossPerLot01, " USD per 0.01 lot (min ", PartialLossMinUSD, "), ", PartialLossPercent, "%");')
old_h = "//|     the floating profit reaches PartialProfitBaseUSD (tiers 0-1),|\n//|     doubling from tier 2 (200, 400, ...), close                  |"
new_h = "//|     the floating profit reaches PartialProfitPerLot01 x lot/0.01 |\n//|     (floor PartialProfitMinUSD), close                            |"
s = s.replace(old_h, new_h)
assert "PartialProfitBaseUSD *" not in s and "PartialProfitDoubles &&" not in s
open(DST, "w", encoding="utf-8").write(s); print("written v2.10", len(s.splitlines()), "lines")
ME = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"; inc = r"C:\Users\samja\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"; log = os.path.join(HERE, "results", "compile_v21.log")
subprocess.run([ME, f"/compile:{DST}", f"/include:{inc}", f"/log:{log}"], timeout=180)
txt = open(log, encoding="utf-16", errors="replace").read(); print("\n".join(l for l in txt.splitlines() if "error" in l.lower() or "warning" in l.lower() or "Result" in l)[-1200:]); print("ex5 present:", os.path.exists(DST.replace(".mq5", ".ex5")))
