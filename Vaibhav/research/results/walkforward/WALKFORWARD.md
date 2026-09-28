# Walk-forward, sensitivity, Monte Carlo and overfitting audit

Grid: 5 filters x 3 stops x 8 exits = 120 configurations per timeframe (96 on D1). Folds: train 2 y -> validate 1 y -> test 1 y, rolled yearly from Sep 2020. Strategy view, 0.01 lot, realistic costs. Selection = best train expectancy/R (min trades), gated by validation expectancy/R > 0; test window never used for selection.

## M1

| fold | train | val | test | configs | train-best config | train R | val R | test R | passes val | selected (val-gated) | selected test R | selected test net $ | untouched EA test net $ | share of configs positive in test |
|---|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2022-09..2023-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.244 | -0.248 | -0.223 | False | none passes |  |  | -4183.03 | 0.0 |
| 2 | 2021-09..2023-09 | 2023-09..2024-09 | 2024-09..2025-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.257 | -0.223 | -0.151 | False | none passes |  |  | -5495.54 | 0.0 |
| 3 | 2022-09..2024-09 | 2024-09..2025-09 | 2025-09..2026-09 | 120 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | -0.236 | -0.151 | -0.054 | False | none passes |  |  | -6374.91 | 0.0 |

Overfitting audit (DEV -> VAL -> OOS): 120 configurations tested; positive in all three splits: 0; share positive DEV 0.0, VAL 0.0, OOS 0.0. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE', 'dev_expR': np.float64(-0.245), 'dev_pf': np.float64(0.424), 'val_expR': np.float64(-0.211), 'oos_expR': np.float64(-0.085), 'oos_net': np.float64(-2761.64), 'oos_pf': np.float64(0.82)}.

No configuration is positive in DEV, VAL and OOS on this timeframe.

## M5

| fold | train | val | test | configs | train-best config | train R | val R | test R | passes val | selected (val-gated) | selected test R | selected test net $ | untouched EA test net $ | share of configs positive in test |
|---|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2022-09..2023-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | -0.121 | -0.095 | -0.124 | False | none passes |  |  | -923.22 | 0.0 |
| 2 | 2021-09..2023-09 | 2023-09..2024-09 | 2024-09..2025-09 | 120 | vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA | -0.1 | -0.124 | -0.048 | False | none passes |  |  | -648.13 | 0.0 |
| 3 | 2022-09..2024-09 | 2024-09..2025-09 | 2025-09..2026-09 | 120 | NY 13-22 | swing3 | E09 ATRtrail2+BE | -0.099 | -0.054 | -0.017 | False | none passes |  |  | -17.31 | 0.867 |

Overfitting audit (DEV -> VAL -> OOS): 120 configurations tested; positive in all three splits: 0; share positive DEV 0.0, VAL 0.0, OOS 0.642. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E16 Chand+BE noMA', 'dev_expR': np.float64(-0.112), 'dev_pf': np.float64(0.709), 'val_expR': np.float64(-0.099), 'oos_expR': np.float64(-0.021), 'oos_net': np.float64(51.96), 'oos_pf': np.float64(1.009)}.

No configuration is positive in DEV, VAL and OOS on this timeframe.

## M15

| fold | train | val | test | configs | train-best config | train R | val R | test R | passes val | selected (val-gated) | selected test R | selected test net $ | untouched EA test net $ | share of configs positive in test |
|---|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2022-09..2023-09 | 2023-09..2024-09 | 120 | vol>=1+ADX>=25 | swing3 | E04 Trail+BE | 0.014 | -0.057 | 0.004 | False | none passes |  |  | -139.14 | 0.333 |
| 2 | 2021-09..2023-09 | 2023-09..2024-09 | 2024-09..2025-09 | 120 | vol>=1 | swing3 | E13 TWK | -0.021 | -0.006 | -0.054 | False | vol>=1+ADX>=25 | swing3 | E13 TWK | -0.051 | -275.5 | -212.38 | 0.15 |
| 3 | 2022-09..2024-09 | 2024-09..2025-09 | 2025-09..2026-09 | 120 | vol>=1+ADX>=25 | ATR3 | E00 SL+MA18 | 0.009 | -0.053 | 0.107 | False | none | swing3 | E16 Chand+BE noMA | 0.022 | 524.77 | 448.95 | 0.942 |

Overfitting audit (DEV -> VAL -> OOS): 120 configurations tested; positive in all three splits: 0; share positive DEV 0.0, VAL 0.283, OOS 0.908. Best in-sample: {'config': 'vol>=1+ADX>=25 | swing3 | E04 Trail+BE', 'dev_expR': np.float64(-0.01), 'dev_pf': np.float64(0.874), 'val_expR': np.float64(-0.006), 'oos_expR': np.float64(-0.014), 'oos_net': np.float64(247.37), 'oos_pf': np.float64(1.082)}.

No configuration is positive in DEV, VAL and OOS on this timeframe.

## D1

| fold | train | val | test | configs | train-best config | train R | val R | test R | passes val | selected (val-gated) | selected test R | selected test net $ | untouched EA test net $ | share of configs positive in test |
|---|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| 1 | 2020-09..2022-09 | 2022-09..2023-09 | 2023-09..2024-09 | 96 | ADX>=25 | ATR3 | E09 ATRtrail2+BE | 0.165 | -0.046 | 0.248 | False | ADX>=25 | swing | E03 Chand+BE | 0.183 | 140.6 | -32.36 | 0.74 |
| 2 | 2021-09..2023-09 | 2023-09..2024-09 | 2024-09..2025-09 | 96 | none | ATR3 | E00 SL+MA18 | 0.073 | -0.12 | -0.002 | False | none | swing | E00 SL+MA18 | 0.01 | -58.27 | 138.02 | 0.604 |
| 3 | 2022-09..2024-09 | 2024-09..2025-09 | 2025-09..2026-09 | 96 | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | 0.119 | 0.159 | 0.219 | True | vol>=1+ADX>=25 | swing3 | E09 ATRtrail2+BE | 0.219 | 792.32 | 479.47 | 0.75 |

Overfitting audit (DEV -> VAL -> OOS): 96 configurations tested; positive in all three splits: 19; share positive DEV 0.302, VAL 0.604, OOS 0.792. Best in-sample: {'config': 'none | ATR3 | E20 R-BE1R+swing1R', 'dev_expR': np.float64(0.052), 'dev_pf': np.float64(0.81), 'val_expR': np.float64(-0.061), 'oos_expR': np.float64(0.302), 'oos_net': np.float64(219.36), 'oos_pf': np.float64(1.39)}.

Configurations positive in DEV, VAL and OOS (top by OOS expectancy/R):

| config | DEV R | VAL R | OOS R | OOS net $ | OOS PF | all net $ | all PF | all DD $ | trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ADX>=25 | ATR3 | E03 Chand+BE | 0.047 | 0.092 | 0.469 | 1407.66 | 86.315 | 1574.52 | 11.747 | 64.67 | 62 |
| ADX>=25 | swing | E03 Chand+BE | 0.042 | 0.083 | 0.45 | 1407.66 | 86.315 | 1574.52 | 11.747 | 64.67 | 62 |
| ADX>=25 | ATR3 | E16 Chand+BE noMA | 0.013 | 0.152 | 0.45 | 1371.72 | 84.137 | 1550.76 | 11.274 | 73.43 | 59 |
| ADX>=25 | swing | E09 ATRtrail2+BE | 0.041 | 0.153 | 0.435 | 1528.47 | 10.2 | 1818.19 | 5.98 | 154.85 | 70 |
| ADX>=25 | ATR3 | E09 ATRtrail2+BE | 0.038 | 0.173 | 0.428 | 1528.47 | 10.2 | 1818.19 | 5.98 | 154.85 | 70 |
| ADX>=25 | swing | E16 Chand+BE noMA | 0.013 | 0.131 | 0.404 | 1371.72 | 84.137 | 1550.76 | 11.274 | 73.43 | 59 |
| none | swing | E09 ATRtrail2+BE | -0.005 | 0.102 | 0.337 | 1529.33 | 10.254 | 1735.82 | 4.348 | 154.85 | 93 |
| none | ATR3 | E09 ATRtrail2+BE | 0.007 | 0.101 | 0.332 | 1529.33 | 10.254 | 1729.6 | 4.296 | 154.85 | 93 |
| ADX>=25 | swing3 | E03 Chand+BE | 0.033 | 0.019 | 0.321 | 1407.66 | 86.315 | 1574.52 | 11.747 | 64.67 | 62 |
| ADX>=25 | swing3 | E16 Chand+BE noMA | 0.008 | 0.051 | 0.312 | 1371.72 | 84.137 | 1550.76 | 11.274 | 73.43 | 59 |

### Sensitivity around ADX>=25 | ATR3 | E03 Chand+BE

| parameter | values -> all-period expectancy R (net $) | OOS expectancy R |
|---|---|---|
| atr_mult | 1.5: 0.08 (973.59), 2.25: 0.235 (1630.38), 3.0: 0.21 (1574.52), 3.75: 0.184 (1351.61), 4.5: 0.176 (1230.47) | 0.154, 0.479, 0.469, 0.41, 0.365 |
| chand_lookback | 11: 0.212 (1592.73), 16: 0.214 (1602.67), 22: 0.21 (1574.52), 28: 0.231 (1677.08), 33: 0.225 (1521.4) | 0.469, 0.469, 0.469, 0.471, 0.448 |
| be_trigger_pts | 300: 0.114 (917.52), 400: 0.127 (900.37), 500: 0.21 (1574.52), 600: 0.203 (1521.33), 700: 0.234 (1552.16) | 0.323, 0.335, 0.469, 0.469, 0.467 |
| sl_atr_mult | 2.25: 0.271 (1578.84), 2.625: 0.234 (1574.52), 3.0: 0.21 (1574.52), 3.375: 0.193 (1574.52), 3.75: 0.179 (1574.52) | 0.595, 0.519, 0.469, 0.43, 0.399 |
| adx_min | 20: 0.151 (1491.1), 22.5: 0.19 (1540.29), 25: 0.21 (1574.52), 27.5: 0.203 (1519.59), 30: 0.229 (1563.38) | 0.383, 0.398, 0.469, 0.545, 0.577 |
| fast | 14: 0.19 (1544.19), 16: 0.216 (1603.94), 18: 0.21 (1574.52), 20: 0.153 (948.5), 22: 0.145 (909.81) | 0.439, 0.439, 0.469, 0.289, 0.281 |
| trend | 150: 0.2 (1546.16), 175: 0.216 (1576.92), 200: 0.21 (1574.52), 225: 0.204 (1529.15), 250: 0.241 (1574.68) | 0.413, 0.43, 0.469, 0.491, 0.607 |

Monte Carlo (trade-order shuffle / bootstrap) at $200: p(ruin) 0.0 / 0.0016, DD p95 $104.62, ending balance p05-median-p95 $471.19 / $1691.33 / $3354.19; at 100x median risk ($8674): p(ruin) 0.0, DD p95 $104.62.
