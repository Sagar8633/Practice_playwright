"""Deploy TWK_MomentumEA to the XM DEMO terminal on one XAUUSD M1 chart.

Run ONLY while terminal64.exe is closed (the terminal rewrites the profile on exit).
The chart is opened by the terminal's documented [StartUp] config with a .set preset.
Then launch:  terminal64.exe /config:<ini written here>

usage: python deploy_demo.py <terminal data dir>
"""
import io
import os
import sys

DATA = sys.argv[1]
MQL5 = os.path.join(DATA, 'MQL5')
PRESET_NAME = 'TWK_Demo_05lot.set'
EA_REL = r'TWK\TWK_MomentumEA'
DEMO_LOGIN = 169426800            # XM DEMO (log: "demo account - hedging mode"); 450160565 is REAL
DEMO_SERVER = 'XMGlobal-MT5 2'

# Chart configuration. Distances are broker points.
INPUTS = [
    ('AccountGuard', '0'),                  # demo only
    ('RealTradingConfirmation', ''),
    ('RealAccountMaxLot', '0.01'),
    ('SignalTimeframe', '1'),               # PERIOD_M1
    ('TradeOnClosedCandle', 'true'),
    ('OneTradePerSignal', 'true'),
    ('CalcBars', '2000'),
    ('TrailMultiplier', '1.5'),
    ('TrailATRLength', '10'),
    ('PivotStrength', '5'),
    ('RewardRisk', '2.0'),
    ('VolumeLength', '20'),
    ('PivotTieRule', '0'),
    ('MinimumVolumeRatio', '1.5'),
    ('RequireM1Box', 'true'),
    ('RequireM3Box', 'true'),
    ('ADXPeriod', '14'),
    ('ADXSmoothing', '14'),
    ('ADXMinimum', '20.0'),
    ('UseIndicatorSL', 'true'),
    ('EnableFallbackSL', 'false'),
    ('FallbackSLPoints', '500'),
    ('UseIndicatorTP', 'true'),
    ('EnableFallbackTP', 'false'),
    ('FallbackTPPoints', '1000'),
    ('RejectIfTPInvalid', 'true'),
    ('EnablePurpleLineTrailing', 'true'),
    ('PurpleTrailActivationPoints', '200'),
    ('ProfitProtectionActivationPoints', '500'),
    ('ProfitLockPoints', '100'),
    ('EnableOneToOneTrailing', 'true'),
    ('MinSLImprovementPoints', '5'),
    ('LotSizingMode', '0'),                 # FIXED
    ('LotSize', '0.5'),
    ('RiskPercent', '0.5'),
    ('MaxLotSize', '0.5'),
    ('OnePositionPerSymbol', 'true'),
    ('EnableSpreadFilter', 'true'),
    ('MaxSpreadPoints', '0'),               # auto
    ('SpreadAutoMultiplier', '2.0'),
    ('MaxDeviation', '50'),
    ('MaxRetries', '3'),
    ('MagicNumber', '26092401'),
    ('TradeComment', 'TWK'),
    ('CloseOnOppositeSignal', 'false'),
    ('ReverseOnOppositeSignal', 'false'),
    ('EmergencyProtectionMode', '1'),       # CLOSE_POSITION
    ('RespectManualSL', 'true'),
    ('DebugIndicatorMode', 'true'),
    ('ShowDebugPanel', 'true'),
    ('ExportDiagnosticsCSV', 'true'),
    ('ExportBars', '3000'),
    ('WriteTradeLog', 'true'),
]


def main():
    # 1. preset for the [StartUp] chart (plain ASCII, same style as the existing presets)
    preset = os.path.join(MQL5, 'Presets', PRESET_NAME)
    with io.open(preset, 'w', encoding='ascii', newline='\n') as f:
        f.write(''.join(f'{k}={v}\n' for k, v in INPUTS))

    # 2. startup config: algo trading ON, XAUUSD M1 chart with the EA + preset
    ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tester', 'twk_live_demo.ini')
    ini = os.path.abspath(ini)
    with io.open(ini, 'w', encoding='utf-16', newline='\r\n') as f:
        f.write(f"""[Common]
Login={DEMO_LOGIN}
Server={DEMO_SERVER}
[Experts]
AllowLiveTrading=1
AllowDllImport=0
Enabled=1
Account=1
Profile=1
[StartUp]
Expert={EA_REL}
ExpertParameters={PRESET_NAME}
Symbol=XAUUSD
Period=M1
""")
    print('preset :', preset)
    print('config :', ini)


if __name__ == '__main__':
    main()
