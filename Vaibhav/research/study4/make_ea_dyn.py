"""Generate Vaibhav/SimpleSMA18Bot_H4_Dynamic.mq5 from SimpleSMA18Bot_H4.mq5: tiered lot sizing from the balance and a
partial exit at a floating-profit target that scales with the tier. Compiles with MetaEditor."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT)
SRC = os.path.join(VAIB, "SimpleSMA18Bot_H4.mq5"); DST = os.path.join(VAIB, "SimpleSMA18Bot_H4_Dynamic.mq5")
s = open(SRC, encoding="utf-8").read()


def sub(old, new, count=1):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, count)


# ---- header
sub("//|                                            SimpleSMA18Bot_H4.mq5 |\n//|                     Version 1.00-H4 (study 3, 26 Sep 2026)       |",
    "//|                                    SimpleSMA18Bot_H4_Dynamic.mq5 |\n//|          Version 1.00-H4-Dyn (study 4, 27 Sep 2026)              |\n"
    "//|  Adds to SimpleSMA18Bot_H4:                                      |\n"
    "//|   * Tiered lot sizing from the CURRENT balance (UseDynamicLots): |\n"
    "//|     lot = BaseLot x 2^floor(log2(balance / BaseBalance)),        |\n"
    "//|     never below BaseLot, capped at MaxLot, re-evaluated at every |\n"
    "//|     order (so it steps down again when the balance falls).       |\n"
    "//|   * Partial exit once per position (EnablePartialClose): when    |\n"
    "//|     the floating profit reaches PartialProfitBaseUSD (tiers 0-1),|\n"
    "//|     doubling from tier 2 (200, 400, ...), close                  |\n"
    "//|     PartialClosePercent of the volume. At the broker minimum lot |\n"
    "//|     a 50% share cannot be closed: PartialAtMinLot decides (SKIP  |\n"
    "//|     or CLOSE_ALL). Works for BUY and SELL.                       |\n"
    "//|   * UseSLPercentFilter default false (a $200 account cannot pass |\n"
    "//|     the 1% rule at 0.01 lot on H4). See research/study4.          |")
# ---- inputs: after the ATR-scaled block
sub("input double ATRTrailStepMult       = 0.10;   // minimum stop improvement in ATR\n",
    "input double ATRTrailStepMult       = 0.10;   // minimum stop improvement in ATR\n\n"
    "//================ DYNAMIC LOT SIZE (study 4) ========================\n\n"
    "enum ENUM_PARTIAL_MIN_LOT\n{\n   PARTIAL_SKIP      = 0,   // skip the partial close when the share is below the minimum lot\n   PARTIAL_CLOSE_ALL = 1    // close the whole position instead\n};\n\n"
    "input bool   UseDynamicLots        = true;    // lot from the balance tier; false = fixed LotSize\n"
    "input double BaseBalance           = 200.0;   // balance of the first tier\n"
    "input double BaseLot               = 0.01;    // lot at the first tier (doubles each time the balance doubles)\n"
    "input double MaxLot                = 1.00;    // cap for the tiered lot\n\n"
    "//================ PARTIAL EXIT (study 4) ============================\n\n"
    "input bool   EnablePartialExit     = true;\n"
    "input double PartialProfitBaseUSD  = 100.0;   // floating profit that triggers the partial close at tiers 0 and 1\n"
    "input bool   PartialProfitDoubles  = true;    // from tier 2 the trigger doubles with each tier (200, 400, ...)\n"
    "input double PartialExitPercent    = 50.0;    // share of the position volume to close\n"
    "input ENUM_PARTIAL_MIN_LOT PartialAtMinLot = PARTIAL_SKIP;\n")
# ---- default gate off for this variant
sub("input bool   UseSLPercentFilter = true;", "input bool   UseSLPercentFilter = false;")
# ---- globals
sub("double EntryATR = 0.0;", "double EntryATR = 0.0;\nint    EntryTier = 0;        // lot tier of the open position (study 4)\nbool   PartialDone = false;  // partial exit already taken for this position (study 4)")
# ---- helper functions before Get ADX Value block
sub("//+------------------------------------------------------------------+\n//| Get ADX Value                                                    |",
    "//+------------------------------------------------------------------+\n//| Balance tier: 0 below 2 x BaseBalance, +1 each doubling (study 4)|\n//+------------------------------------------------------------------+\n"
    "int BalanceTier(double balance)\n{\n   if(BaseBalance <= 0.0 || balance < 2.0 * BaseBalance)\n      return 0;\n\n   int tier = 0;\n   double b = balance;\n\n   while(b >= 2.0 * BaseBalance && tier < 30)\n   {\n      b /= 2.0;\n      tier++;\n   }\n\n   return tier;\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Normalise a volume to the broker's step and limits               |\n//+------------------------------------------------------------------+\n"
    "double NormalizeLot(double lot)\n{\n   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);\n   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);\n   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);\n\n   if(vstep > 0.0)\n      lot = MathFloor(lot / vstep + 1e-9) * vstep;\n\n   if(lot < vmin) lot = vmin;\n   if(lot > vmax) lot = vmax;\n\n   return NormalizeDouble(lot, 2);\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Lot for the tier                                                 |\n//+------------------------------------------------------------------+\n"
    "double TierLot(int tier)\n{\n   double lot = BaseLot * MathPow(2.0, tier);\n\n   if(lot > MaxLot)\n      lot = MaxLot;\n\n   if(lot < BaseLot)\n      lot = BaseLot;\n\n   return NormalizeLot(lot);\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Lot to use now (dynamic from the balance, or the fixed input)   |\n//+------------------------------------------------------------------+\n"
    "double CurrentLot()\n{\n   if(!UseDynamicLots)\n      return NormalizeLot(LotSize);\n\n   return TierLot(BalanceTier(AccountInfoDouble(ACCOUNT_BALANCE)));\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Tier implied by an open position's volume                        |\n//+------------------------------------------------------------------+\n"
    "int TierFromVolume(double volume)\n{\n   if(BaseLot <= 0.0 || volume <= BaseLot)\n      return 0;\n\n   int tier = (int)MathRound(MathLog(volume / BaseLot) / MathLog(2.0));\n\n   return (tier < 0) ? 0 : tier;\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Floating-profit trigger of the partial exit for a tier          |\n//+------------------------------------------------------------------+\n"
    "double PartialTriggerUSD(int tier)\n{\n   if(PartialProfitDoubles && tier >= 2)\n      return PartialProfitBaseUSD * MathPow(2.0, tier - 1);\n\n   return PartialProfitBaseUSD;\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Get ADX Value                                                    |")
# ---- use CurrentLot() in the SL% filter and the order placement
sub("   if(!OrderCalcProfit(\n         orderType,\n         _Symbol,\n         LotSize,", "   if(!OrderCalcProfit(\n         orderType,\n         _Symbol,\n         CurrentLot(),")
sub("   bool result = trade.BuyStop(\n      LotSize,", "   bool result = trade.BuyStop(\n      CurrentLot(),")
sub("   bool result=trade.SellStop(\n      LotSize,", "   bool result=trade.SellStop(\n      CurrentLot(),")
# ---- partial exit manager, inserted before the Break-even manager
sub("//+------------------------------------------------------------------+\n//| Break-even                                                       |",
    "//+------------------------------------------------------------------+\n//| Partial exit at the tier's floating-profit target (study 4)      |\n//+------------------------------------------------------------------+\n"
    "void ManagePartialExit()\n{\n   if(!EnablePartialExit || PartialDone)\n      return;\n\n   if(!PositionSelect(_Symbol))\n      return;\n\n"
    "   double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);\n   double volume = PositionGetDouble(POSITION_VOLUME);\n   int    tier   = TierFromVolume(volume);\n   double target = PartialTriggerUSD(tier);\n\n"
    "   if(profit < target)\n      return;\n\n"
    "   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);\n   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);\n   double share = volume * PartialExitPercent / 100.0;\n\n"
    "   if(vstep > 0.0)\n      share = MathFloor(share / vstep + 1e-9) * vstep;\n\n"
    "   ulong ticket = PositionGetInteger(POSITION_TICKET);\n\n"
    "   if(share < vmin || volume - share < vmin)\n   {\n      // the share (or the remainder) is below the broker minimum\n      if(PartialAtMinLot == PARTIAL_CLOSE_ALL)\n      {\n         if(trade.PositionClose(ticket))\n            Print(\"Partial exit: whole position closed at target \", DoubleToString(target, 2), \" (share below minimum lot)\");\n      }\n      else\n         Print(\"Partial exit skipped: 50% of \", DoubleToString(volume, 2), \" lot is below the minimum lot\");\n\n      PartialDone = true;\n      return;\n   }\n\n"
    "   if(trade.PositionClosePartial(ticket, NormalizeDouble(share, 2)))\n   {\n      Print(\"Partial exit: closed \", DoubleToString(share, 2), \" of \", DoubleToString(volume, 2), \" lot at floating profit \", DoubleToString(profit, 2), \" (tier \", tier, \", target \", DoubleToString(target, 2), \")\");\n      PartialDone = true;\n   }\n   else\n      Print(\"Partial exit failed. Error = \", GetLastError());\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Break-even                                                       |")
# ---- call it in both branches of ManageOpenPositions (after the risk filter, before the MA exit check)
s = s.replace("   // Trade may already be closed\n   if(!PositionSelect(_Symbol))\n      return;\n\n   if(ExitSignal())", "   // Trade may already be closed\n   if(!PositionSelect(_Symbol))\n      return;\n\n   ManagePartialExit();\n\n   if(!PositionSelect(_Symbol))\n      return;\n\n   if(ExitSignal())")
s = s.replace("   // Trade may already be closed\n   if(!PositionSelect(_Symbol))\n      return;\n\n   if(SellExitSignal())", "   // Trade may already be closed\n   if(!PositionSelect(_Symbol))\n      return;\n\n   ManagePartialExit();\n\n   if(!PositionSelect(_Symbol))\n      return;\n\n   if(SellExitSignal())")
assert s.count("ManagePartialExit();") == 2, "partial exit not wired into both branches"
# ---- reset the flag when a new position is initialised
sub("   EntryATR = GetATRValue(1);   // study 3: fixed for the life of the trade", "   EntryATR = GetATRValue(1);   // study 3: fixed for the life of the trade\n   EntryTier = TierFromVolume(PositionGetDouble(POSITION_VOLUME));\n   PartialDone = false;")
# ---- init print
sub('   Print("SimpleSMA18Bot_H4 initialized. ATR-scaled levels = ", UseATRScaledLevels,',
    '   Print("Dynamic lots = ", UseDynamicLots, " | base ", BaseBalance, " USD -> ", BaseLot, " lot, x2 per doubling, cap ", MaxLot,\n         " | balance now ", AccountInfoDouble(ACCOUNT_BALANCE), " -> tier ", BalanceTier(AccountInfoDouble(ACCOUNT_BALANCE)), ", lot ", CurrentLot(),\n         " | partial exit ", EnablePartialExit, " at ", PartialProfitBaseUSD, " USD (x2 from tier 2), ", PartialExitPercent, "%");\n   Print("SimpleSMA18Bot_H4 initialized. ATR-scaled levels = ", UseATRScaledLevels,')
with open(DST, "w", encoding="utf-8") as f:
    f.write(s)
print("written", DST)
ME = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"; inc = r"C:\Users\samja\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"; log = os.path.join(HERE, "results", "compile.log")
os.makedirs(os.path.dirname(log), exist_ok=True)
subprocess.run([ME, f"/compile:{DST}", f"/include:{inc}", f"/log:{log}"], timeout=180)
txt = open(log, encoding="utf-16", errors="replace").read(); print(txt[-700:]); print("ex5 present:", os.path.exists(DST.replace(".mq5", ".ex5")))
