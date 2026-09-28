"""Writes the two presets of the release (GOLD x M1/M3) as MT5 writes them: UTF-16LE + BOM, CRLF.

M1 preset = the live XM demo chart of 2026-09-24/25.
M3 preset = same strategy, SignalTimeframe=3, point distances x1.8 (the Tracker's median stop on
M3 is 1.78x the M1 one on XM GOLD data: 397->705 pts), and its own MagicNumber so it can run
next to the M1 chart without sharing state.

usage: python make_presets.py <output MQL5\\Presets folder>
"""
import io
import os
import sys

OUT = sys.argv[1]

BASE = [
    ('AccountGuard', '0'), ('RealTradingConfirmation', ''), ('RealAccountMaxLot', None),
    ('SignalTimeframe', '1'), ('TradeOnClosedCandle', 'true'), ('OneTradePerSignal', 'true'), ('CalcBars', '2000'),
    ('TrailMultiplier', '1.5'), ('TrailATRLength', '10'), ('PivotStrength', '5'), ('RewardRisk', '2.0'),
    ('VolumeLength', '20'), ('PivotTieRule', '0'),
    ('MinimumVolumeRatio', None),
    ('RequireM1Box', 'true'), ('RequireM3Box', 'true'),
    ('ADXPeriod', '14'), ('ADXSmoothing', '14'), ('ADXMinimum', '20.0'),
    ('UseIndicatorSL', 'true'), ('EnableFallbackSL', 'false'), ('FallbackSLPoints', None),
    ('HardSL_M1', '500'), ('HardSL_M3', '0'), ('HardSL_M5', '0'), ('HardSL_M15', '0'), ('HardSL_M30', '0'),
    ('HardSL_H1', '0'), ('HardSL_H4', '0'), ('HardSL_Other', '0'),
    ('ReFlipAction', '0'), ('ReFlipMinutes', '15'),
    ('UseIndicatorTP', 'true'), ('EnableFallbackTP', 'false'), ('FallbackTPPoints', None), ('RejectIfTPInvalid', 'true'),
    ('EnablePurpleLineTrailing', 'true'), ('PurpleTrailActivationPoints', None), ('ProfitProtectionActivationPoints', None),
    ('ProfitLockPoints', None), ('EnableOneToOneTrailing', 'true'), ('MinSLImprovementPoints', None),
    ('LotSizingMode', '0'), ('LotSize', None), ('RiskPercent', '0.5'), ('MaxLotSize', None), ('OnePositionPerSymbol', 'true'),
    ('EnableSpreadFilter', 'true'), ('MaxSpreadPoints', '0'), ('SpreadAutoMultiplier', '2.0'), ('MaxDeviation', '50'),
    ('MaxRetries', '3'), ('MagicNumber', None), ('TradeComment', 'TWK'),
    ('CloseOnOppositeSignal', 'false'), ('ReverseOnOppositeSignal', 'false'),
    ('EmergencyProtectionMode', '1'), ('RespectManualSL', 'true'),
    ('ShowTrackerOnChart', 'true'), ('ChartTrackerBars', '50000'), ('ChartBoxHistory', '300'),
    ('DebugIndicatorMode', 'true'), ('ShowDebugPanel', 'true'), ('ExportDiagnosticsCSV', 'true'), ('ExportBars', '3000'),
    ('WriteTradeLog', 'true'),
    ('TesterSliceDays', '0'), ('TesterSliceIndex', '0'), ('TesterDebugLog', 'false'),
]

PRESETS = {
    'TWK_GOLD_M1_demo.set': (
        ['TWK Momentum EA v1.40 - GOLD / XAUUSD M1 (= live XM demo chart, account 169426800)',
         'Distances are broker points for digits=2 (point 0.01). Point 0.001 -> multiply every *Points value by 10.'],
        dict(RealAccountMaxLot='0.02', MinimumVolumeRatio='1.2', FallbackSLPoints='500', FallbackTPPoints='500',
             PurpleTrailActivationPoints='200', ProfitProtectionActivationPoints='500', ProfitLockPoints='100',
             MinSLImprovementPoints='5', LotSize='0.02', MaxLotSize='0.1', MagicNumber='26092401')),
    'TWK_GOLD_M3_demo.set': (
        ['TWK Momentum EA v1.40 - GOLD / XAUUSD, 3-minute signals',
         'Same as GOLD M1 with SignalTimeframe=M3 and point distances x1.8 (M3 stops are ~1.8x larger).',
         'Own MagicNumber 26092403 so it can run next to the M1 chart. Same lot => ~1.8x more money at risk per trade.'],
        dict(SignalTimeframe='3', RealAccountMaxLot='0.02', MinimumVolumeRatio='1.2', FallbackSLPoints='900', FallbackTPPoints='900',
             PurpleTrailActivationPoints='360', ProfitProtectionActivationPoints='900', ProfitLockPoints='180',
             MinSLImprovementPoints='9', LotSize='0.02', MaxLotSize='0.1', MagicNumber='26092403')),
}

os.makedirs(OUT, exist_ok=True)
for name, (comments, over) in PRESETS.items():
    lines = ['; ' + c for c in comments]
    for key, default in BASE:
        value = over.get(key, default)
        assert value is not None, (name, key)
        lines.append(f'{key}={value}')
    with io.open(os.path.join(OUT, name), 'w', encoding='utf-16', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'{name}: {len(lines) - len(comments)} inputs')

# ---- TWK_PineEA (simple Pine trades) -------------------------------------------------
PINE = [
    ('AccountGuard', '0'), ('RealTradingConfirmation', ''), ('RealAccountMaxLot', '0.02'),
    ('SignalTimeframe', '1'), ('RewardRisk', '2.0'), ('ReverseOnFlip', 'true'),
    ('EnablePurpleTrail', 'true'), ('PurpleTrailStartPoints', '0'), ('LockTriggerPoints', '1000'),
    ('LockProfitPoints', '900'), ('MinSLStepPoints', '5'),
    ('TrailMultiplier', '1.5'), ('TrailATRLength', '10'), ('PivotStrength', '5'),
    ('LotSize', '0.02'), ('MaxDeviation', '50'), ('MagicNumber', '26092501'), ('TradeComment', 'TWK Pine'),
    ('ShowTrackerOnChart', 'true'), ('ChartTrackerBars', '50000'), ('ChartBoxHistory', '300'), ('WriteTradeLog', 'true'),
]
pine_lines = ['; TWK Pine EA v1.20 - GOLD / XAUUSD M1: every purple-line flip closes and reverses; SL = Pine pivot, TP 1:2; trail purple, lock +900 at +1000',
              '; No filters. Distances in broker points for digits=2 (point 0.01).']
pine_lines += [f'{k}={v}' for k, v in PINE]
with io.open(os.path.join(OUT, 'TWK_Pine_GOLD_M1_demo.set'), 'w', encoding='utf-16', newline='\r\n') as f:
    f.write('\n'.join(pine_lines) + '\n')
print(f'TWK_Pine_GOLD_M1_demo.set: {len(PINE)} inputs')
