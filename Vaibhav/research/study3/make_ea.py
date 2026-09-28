"""Generate Vaibhav/SimpleSMA18Bot_H4.mq5 from the original v1.00 source: adds ATR-scaled break-even / protection /
trailing levels (captured from ATR(ATRPeriod) at entry, exactly as the backtest engine's thr_mode 1) and sets the
defaults to the configuration selected in study 3 (results/study3.json). Then compiles it with MetaEditor."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT)
SRC = os.path.join(VAIB, "SimpleSMA18Bot.mq5"); DST = os.path.join(VAIB, "SimpleSMA18Bot_H4.mq5")
R = json.load(open(os.path.join(HERE, "results", "study3.json"), encoding="utf-8"))
P = R["final"]["params"]
be_on = bool(P.get("be_enable", True)); be_mult = P.get("be_trigger_pts", 100) / 100.0
start_mult = P.get("trail_start_pts", 200) / 100.0; dist_mult = P.get("trail_dist_pts", 100) / 100.0; step_mult = P.get("trail_step_pts", 10) / 100.0
prot_immediate = P.get("prot_start_mode", 0) == 0
use_adx = bool(P.get("use_adx", False)); adx_min = P.get("adx_min", 25.0); adx_rising = bool(P.get("adx_rising", False)); adx_consec = bool(P.get("adx_consecutive", False))
use_session = bool(P.get("use_session", False)); hours = set(P.get("session_hours", ()))
sess_flags = {"TradeSydney": bool(hours & set(list(range(22, 24)) + list(range(0, 7)))) and use_session, "TradeTokyo": bool(hours & set(range(0, 9))) and use_session and hours == set(range(0, 9)), "TradeLondon": use_session and set(range(8, 17)) <= hours, "TradeNewYork": use_session and set(range(13, 22)) <= hours}
fast = P.get("fast", 18); trend = P.get("trend", 200); vol_filter = bool(P.get("use_vol_filter", False)); vol_min = P.get("vol_filter_min", 1.0)
fin = R["stage6"].get("Final (chosen exit + helpful filters)", {}).get("all", {})
s = open(SRC, encoding="utf-8", errors="replace").read()


def sub(old, new, count=1):
    global s
    assert old in s, old[:60]
    s = s.replace(old, new, count)


# ---- header
sub("//|                                               SimpleSMA18Bot.mq5 |\n//|                     Version 1.00                                 |",
    "//|                                            SimpleSMA18Bot_H4.mq5 |\n//|                     Version 1.00-H4 (study 3, 26 Sep 2026)       |\n"
    "//|  Changes versus v1.00 (only what the H4 backtests support):      |\n"
    "//|   * ATR-scaled break-even / protection-start / trailing levels:   |\n"
    "//|     each level = multiplier x ATR(ATRPeriod) captured at entry    |\n"
    "//|     (UseATRScaledLevels). Point inputs are used when it is off.   |\n"
    "//|   * Defaults set to the selected H4 configuration:               |\n"
    f"//|     TimeFrame H4, ProtectionMode TRAILING started immediately,    |\n"
    f"//|     BE {'%.2f' % be_mult} ATR{'' if be_on else ' (off)'}, trail start {'%.2f' % start_mult} ATR, distance {'%.2f' % dist_mult} ATR, step {'%.2f' % step_mult} ATR,\n"
    f"//|     ADX filter {'ON >= %g' % adx_min if use_adx else 'off'}, session filter {'ON' if use_session else 'off'}, MA {fast}/{trend}, EntryBufferPoints {int(P.get('entry_buffer_pts', 10))}.\n"
    f"//|     Backtest 2020-09..2026-09, 0.01 lot, XM costs: net {fin.get('net')} PF {fin.get('pf')} maxDD {fin.get('dd')} ({fin.get('trades')} trades).\n"
    "//|   * Everything else (entries, swing stop, MA18 exit, 1% gate,    |\n"
    "//|     fixed 0.01 lot) is unchanged. See research/study3/H4_REPORT.md |")
# ---- defaults
sub("input ENUM_TIMEFRAMES TimeFrame = PERIOD_D1;", "input ENUM_TIMEFRAMES TimeFrame = PERIOD_H4;")
sub("input int FastMAPeriod = 18;", f"input int FastMAPeriod = {fast};")
sub("input int TrendMAPeriod = 200;", f"input int TrendMAPeriod = {trend};")
sub("input int EntryBufferPoints = 10;", f"input int EntryBufferPoints = {int(P.get('entry_buffer_pts', 10))};")
sub("input bool EnableBreakEven = true;", f"input bool EnableBreakEven = {'true' if be_on else 'false'};")
sub("input ENUM_PROTECTION_MODE ProtectionMode = PROTECTION_SWING;", "input ENUM_PROTECTION_MODE ProtectionMode = PROTECTION_TRAILING;")
sub("input ENUM_PROTECTION_START ProtectionStartMode = START_AFTER_POINTS;", f"input ENUM_PROTECTION_START ProtectionStartMode = {'START_IMMEDIATELY' if prot_immediate else 'START_AFTER_POINTS'};")
sub("input bool   UseADXFilter              = false;", f"input bool   UseADXFilter              = {'true' if use_adx else 'false'};")
sub("input double MinimumADX                = 25.0;", f"input double MinimumADX                = {adx_min};")
sub("input bool   RequireRisingADX          = false;", f"input bool   RequireRisingADX          = {'true' if adx_rising else 'false'};")
sub("input bool   RequireConsecutiveADXRise = false;", f"input bool   RequireConsecutiveADXRise = {'true' if adx_consec else 'false'};")
sub("input bool UseSessionFilter = false;\ninput bool TradeAllSessions = true;", f"input bool UseSessionFilter = {'true' if use_session else 'false'};\ninput bool TradeAllSessions = {'false' if use_session else 'true'};")
for k, v in sess_flags.items():
    sub(f"input bool {k}", f"input bool {k}")
    s = re.sub(rf"input bool {k}\s*=\s*(true|false);", f"input bool {k} = {'true' if v else 'false'};", s)
# ---- new inputs after the fixed trailing block
sub("input int TrailingStepPoints = 50;",
    "input int TrailingStepPoints = 50;\n\n//================ ATR-SCALED LEVELS (study 3) =====================\n"
    "// When true, the break-even trigger, protection start and trailing start/distance/step are\n"
    "// multiplier x ATR(ATRPeriod) measured on the last completed bar when the position was opened.\n"
    "// The *Points inputs above are ignored while this is on (BreakEvenOffsetPoints stays in points).\n\n"
    "input bool   UseATRScaledLevels     = true;\n"
    f"input double ATRBreakEvenMult       = {be_mult:.2f};   // break-even trigger in ATR\n"
    "input double ATRProtectionStartMult = 0.0;    // protection start in ATR (0 = immediately, when ProtectionStartMode = START_IMMEDIATELY it is unused)\n"
    f"input double ATRTrailStartMult      = {start_mult:.2f};   // trailing starts at this profit in ATR\n"
    f"input double ATRTrailDistanceMult   = {dist_mult:.2f};   // trailing distance in ATR\n"
    f"input double ATRTrailStepMult       = {step_mult:.2f};   // minimum stop improvement in ATR\n")
if vol_filter:
    pass  # no such input in v1.00; documented in the report as a limitation if the study selected it
# ---- globals
sub("bool EntryIsBuy = false;", "bool EntryIsBuy = false;\n\ndouble EntryATR = 0.0;   // ATR(ATRPeriod) of the last completed bar when the position was opened (study 3)")
# ---- helper after GetATRValue
sub("//+------------------------------------------------------------------+\n//| Get ADX Value                                                    |",
    "//+------------------------------------------------------------------+\n//| Level in points: fixed points, or multiplier x entry ATR (study 3)|\n//+------------------------------------------------------------------+\n"
    "double LevelPoints(int fixedPoints, double atrMult)\n{\n   if(!UseATRScaledLevels || EntryATR <= 0.0 || atrMult < 0.0)\n      return (double)fixedPoints;\n\n   return atrMult * EntryATR / _Point;\n}\n\n"
    "//+------------------------------------------------------------------+\n//| Get ADX Value                                                    |")
# ---- capture the ATR at entry
sub("   EntryIsBuy =\n      (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);\n\n   TradeInitialized = true;",
    "   EntryIsBuy =\n      (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);\n\n   EntryATR = GetATRValue(1);   // study 3: fixed for the life of the trade\n\n   TradeInitialized = true;")
# ---- break-even
sub("   if(profitPoints < BreakEvenTriggerPoints)\n      return;", "   if(profitPoints < LevelPoints(BreakEvenTriggerPoints, ATRBreakEvenMult))\n      return;")
# ---- protection start
sub("   return(profitPoints >= ProtectionStartPoints);", "   return(profitPoints >= LevelPoints(ProtectionStartPoints, ATRProtectionStartMult));")
# ---- trailing (buy and sell branches)
sub("      double desiredSL =\n         bid - TrailingDistancePoints * _Point;", "      double desiredSL =\n         bid - LevelPoints(TrailingDistancePoints, ATRTrailDistanceMult) * _Point;")
sub("      double desiredSL =\n         ask + TrailingDistancePoints * _Point;", "      double desiredSL =\n         ask + LevelPoints(TrailingDistancePoints, ATRTrailDistanceMult) * _Point;")
s = s.replace("            < TrailingStartPoints)\n         return;", "            < LevelPoints(TrailingStartPoints, ATRTrailStartMult))\n         return;")
assert s.count("LevelPoints(TrailingStartPoints") == 2, "trailing start not patched twice"
s = s.replace("desiredSL-currentSL >= TrailingStepPoints*_Point)", "desiredSL-currentSL >= LevelPoints(TrailingStepPoints, ATRTrailStepMult)*_Point)")
s = s.replace("currentSL-desiredSL >= TrailingStepPoints*_Point)", "currentSL-desiredSL >= LevelPoints(TrailingStepPoints, ATRTrailStepMult)*_Point)")
assert s.count("LevelPoints(TrailingStepPoints") == 2, "trailing step not patched twice"
# ---- startup print
sub('   Print("SimpleSMA18Bot initialized successfully.");',
    '   Print("SimpleSMA18Bot_H4 initialized. ATR-scaled levels = ", UseATRScaledLevels,\n         " | BE ", ATRBreakEvenMult, " ATR | trail start ", ATRTrailStartMult, " ATR, distance ", ATRTrailDistanceMult, " ATR, step ", ATRTrailStepMult, " ATR");')
with open(DST, "w", encoding="utf-8") as f:
    f.write(s)
print("written", DST)
# ---- compile with MetaEditor (headless)
ME = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"
inc = r"C:\Users\samja\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"
log = os.path.join(HERE, "results", "compile.log")
if os.path.exists(ME):
    subprocess.run([ME, f"/compile:{DST}", f"/include:{inc}", f"/log:{log}"], timeout=180)
    if os.path.exists(log):
        txt = open(log, encoding="utf-16", errors="replace").read()
        print(txt[-1500:])
    print("ex5 present:", os.path.exists(DST.replace(".mq5", ".ex5")))
else:
    print("MetaEditor not found; compile in MetaEditor manually")
