"""Generate Vaibhav/SimpleSMA18Bot_H4_Final.mq5: the dynamic-lot H4 EA stripped of the filters and modes the tests did
not keep (session filter, ADX filter, emergency loss filter, failed-breakout exit, swing / Chandelier protection modes,
dead partial-close inputs), with the recommended defaults: BaseBalance 500, MaxLot 0.20, PartialAtMinLot SKIP."""
import os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT)
SRC = os.path.join(VAIB, "SimpleSMA18Bot_H4_Dynamic.mq5"); DST = os.path.join(VAIB, "SimpleSMA18Bot_H4_Final.mq5")
s = open(SRC, encoding="utf-8").read()


def sub(old, new, count=1, must=True):
    global s
    if must:
        assert old in s, old[:80]
    s = s.replace(old, new, count)


def remove_function(signature_start):
    """Remove a top-level function (its 3-line comment box included) by the start of its signature line."""
    global s
    i = s.index(signature_start)
    # walk back over the comment box
    box = s.rfind("//+------------------------------------------------------------------+\n//|", 0, i)
    if box != -1 and s[box:i].count("\n") <= 4:
        i = box
    j = s.index("\n}\n", s.index("{", s.index(signature_start))) + 3
    s = s[:i] + s[j:]


def remove_block(start, end):
    global s
    i = s.index(start); j = s.index(end, i) + len(end)
    s = s[:i] + s[j:]


# ---- header
sub("//|                                    SimpleSMA18Bot_H4_Dynamic.mq5 |\n//|          Version 1.00-H4-Dyn (study 4, 27 Sep 2026)              |",
    "//|                                      SimpleSMA18Bot_H4_Final.mq5 |\n//|          Version 2.00-H4 (study 4 final, 27 Sep 2026)            |\n"
    "//|  Clean build of the configuration the six-year H4 tests kept:    |\n"
    "//|   entry 18/200 SMA + volume, stop order at the bar high/low,     |\n"
    "//|   swing stop, ATR-scaled break-even and trailing, MA18 exit,     |\n"
    "//|   tiered lots from the balance, one partial exit per position.   |\n"
    "//|  Removed (tested, not kept): session filter, ADX filter,         |\n"
    "//|   emergency loss filter, failed-breakout exit, swing and         |\n"
    "//|   Chandelier protection modes, old partial-close inputs.         |\n"
    "//|  Defaults = recommended: BaseBalance 500 (lot doubles at 1,000,  |\n"
    "//|   2,000, ...), MaxLot 0.20, PartialAtMinLot SKIP, 1% gate off.   |")
# ---- inputs to remove
remove_block("//================ SESSION FILTER =====================", "input bool TradeNewYork = false;\n")
remove_block("//================ ADX FILTER =====================", "input bool   RequireConsecutiveADXRise = false;\n")
remove_block("//================ FAILED BREAKOUT EXIT =====================", "input double BreakoutRetestBufferPoints = 20;\n")
remove_block("//================ EMERGENCY LOSS FILTER =====================", "input double MaximumLossPoints = 300;\n")
remove_block("// Partial Close\n", "input double PartialClosePercent = 50.0;\n")
# protection modes -> trailing only
sub("""enum ENUM_PROTECTION_MODE
{
   PROTECTION_NONE = 0,
   PROTECTION_SWING = 1,
   PROTECTION_CHANDELIER = 2,
   PROTECTION_TRAILING = 3
};
""", """enum ENUM_PROTECTION_MODE
{
   PROTECTION_NONE = 0,       // stop-loss, break-even and MA18 exit only
   PROTECTION_TRAILING = 3    // trailing stop (ATR-scaled by default)
};
""")
remove_block("// Swing Protection\n", "input int SwingBufferPoints = 50;\n")
remove_block("// Chandelier\n", "input double ATRMultiplier = 3.0;\n")
sub("input int ATRPeriod = 22;\n", "", must=False)
sub("// Fixed Trailing\n", "// ATR period used by the ATR-scaled levels\n\ninput int ATRPeriod = 22;\n\n// Fixed Trailing (used only when UseATRScaledLevels = false)\n")
# ---- recommended defaults
sub("input double MaxLot                = 1.00;", "input double MaxLot                = 0.20;")
sub("input double BaseBalance           = 200.0;", "input double BaseBalance           = 500.0;")
# ---- globals
sub("int ADXHandle;\n", "")
sub("bool PartialClosed = false;\n", "")
remove_block("//================ TRADE STATE =====================", "bool EntryIsBuy = false;\n")
# ---- OnInit / OnDeinit
remove_block("   ADXHandle = iADX(_Symbol, TimeFrame, ADXPeriod);", "   return(INIT_FAILED);\n   \n")
sub("   if(ADXHandle != INVALID_HANDLE)\n   IndicatorRelease(ADXHandle);\n", "")
# ---- functions to remove
for sig in ("double GetADXValue(int shift)", "bool IsADXAboveThreshold()", "bool IsADXRising()", "bool IsADXConsecutivelyRising()", "bool PassADXFilter()", "bool IsTradingSession()",
            "void ManageSwingProtection()", "void ManageChandelierProtection()", "void ManageRiskFilter()", "void ManageFailedBreakoutExit()"):
    remove_function(sig)
# ---- protection manager
sub("""   switch(ProtectionMode)
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
   }""", """   if(ProtectionMode == PROTECTION_TRAILING)
      ManageTrailingProtection();""")
# ---- ManageOpenPositions: drop the risk filter calls
s = s.replace("   // Emergency Risk Filter\n   ManageRiskFilter();\n\n   // Trade may already be closed\n   if(!PositionSelect(_Symbol))\n      return;\n\n   ManagePartialExit();", "   ManagePartialExit();")
assert s.count("ManagePartialExit();") == 2
# ---- UpdateTradeState: keep only the ATR / tier capture
sub("""   EntryTime = (datetime)PositionGetInteger(POSITION_TIME);

   EntryBarTime = iTime(_Symbol, TimeFrame, 0);

   EntryBreakoutPrice =
      PositionGetDouble(POSITION_PRICE_OPEN);

   EntryIsBuy =
      (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);

   EntryATR = GetATRValue(1);""", "   EntryATR = GetATRValue(1);")
# ---- OnTick: drop session and ADX gates
remove_block("//=====================================================\n// Session Filter", "   Comment(\"ADX Filter : Weak Trend\");\n   return;\n}\n")
# ---- tidy: remove stray "input" references to removed enums in the CurrentMagic etc. (none) and double blank lines
s = re.sub(r"\n{4,}", "\n\n\n", s)
with open(DST, "w", encoding="utf-8") as f:
    f.write(s)
print("written", DST, len(s.splitlines()), "lines")
ME = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"; inc = r"C:\Users\samja\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"; log = os.path.join(HERE, "results", "compile_final.log")
subprocess.run([ME, f"/compile:{DST}", f"/include:{inc}", f"/log:{log}"], timeout=180)
txt = open(log, encoding="utf-16", errors="replace").read()
errs = [l for l in txt.splitlines() if "error" in l.lower() or "warning" in l.lower()]
print("\n".join(errs[-15:])); print("ex5 present:", os.path.exists(DST.replace(".mq5", ".ex5")))
