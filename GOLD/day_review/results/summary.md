# Day review: does price do the same thing around the POC every day?

Generated 2026-11-22T15:10 UTC by day_study.cjs. Tests and decision rule: README.md (written before the run).

## What the days look like

| data | days | POC at the close within 2 $ of the Asia POC | outside the value area at London (08:30 NY) | of those, back inside by the close | close (17:00 NY) inside the value area | POC shifts per day |
|---|---:|---:|---:|---:|---:|---:|
| BIN screenshot days | 20 | 35 % | 35 % | 14 % | 50 % | 7.3 |
| BIN all (Dec 2025 - Nov 2026) | 246 | 26 % | 30 % | 44 % | 61 % | 7.4 |
| DUKA (Sep 2021 - Sep 2026) | 1286 | 35 % | 41 % | 36 % | 55 % | 4.4 |

### Races (target and stop the same distance away; 50 % = no edge)

| test | data | days / trades | target first | z | R per trade before costs | after 0.25 $ | after 0.80 $ | avg distance $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| T1 asia: AWAY from the POC (trend day), price outside the value area | DUKA all | 499 | 55.3 % (268 / 485) | 2.3 | +0.102 | +0.045 | -0.080 | 10.1 |
| T1 asia: AWAY from the POC (trend day), price outside the value area | DUKA DEV | 294 | 54.5 % (158 / 290) | 1.5 | +0.087 | +0.010 | -0.160 | 4.5 |
| T1 asia: AWAY from the POC (trend day), price outside the value area | DUKA VAL | 142 | 54.0 % (74 / 137) | 0.9 | +0.084 | +0.049 | -0.028 | 13.1 |
| T1 asia: AWAY from the POC (trend day), price outside the value area | DUKA OOS | 63 | 62.1 % (36 / 58) | 1.8 | +0.217 | +0.204 | +0.174 | 29.1 |
| T1 asia: AWAY from the POC (trend day), price outside the value area | BIN unseen | 66 | 63.3 % (38 / 60) | 2.1 | +0.234 | +0.222 | +0.194 | 29.4 |
| T1 asia: AWAY from the POC (trend day), price outside the value area | BIN seen (20 screenshot days) | 6 | 66.7 % (4 / 6) | 0.8 | +0.333 | +0.313 | +0.270 | 16.9 |
| T1 asia: toward the POC, price inside the value area | DUKA all | 418 | 50.5 % (209 / 414) | 0.2 | +0.011 | -0.102 | -0.353 | 5.4 |
| T1 asia: toward the POC, price inside the value area | DUKA DEV | 242 | 50.0 % (120 / 240) | 0.0 | +0.001 | -0.158 | -0.507 | 2.4 |
| T1 asia: toward the POC, price inside the value area | DUKA VAL | 128 | 53.5 % (68 / 127) | 0.8 | +0.073 | +0.013 | -0.119 | 8.4 |
| T1 asia: toward the POC, price inside the value area | DUKA OOS | 48 | 44.7 % (21 / 47) | -0.7 | -0.100 | -0.131 | -0.199 | 12.2 |
| T1 asia: toward the POC, price inside the value area | BIN unseen | 92 | 46.2 % (42 / 91) | -0.7 | -0.072 | -0.102 | -0.168 | 12.7 |
| T1 asia: toward the POC, price inside the value area | BIN seen (20 screenshot days) | 8 | 25.0 % (2 / 8) | -1.4 | -0.500 | -0.538 | -0.620 | 9.4 |
| T1 asia: toward the POC, price outside the value area | DUKA all | 499 | 44.3 % (215 / 485) | -2.5 | -0.110 | -0.167 | -0.293 | 10.1 |
| T1 asia: toward the POC, price outside the value area | DUKA DEV | 294 | 44.8 % (130 / 290) | -1.8 | -0.100 | -0.177 | -0.347 | 4.5 |
| T1 asia: toward the POC, price outside the value area | DUKA VAL | 142 | 46.0 % (63 / 137) | -0.9 | -0.084 | -0.119 | -0.196 | 13.1 |
| T1 asia: toward the POC, price outside the value area | DUKA OOS | 63 | 37.9 % (22 / 58) | -1.8 | -0.217 | -0.230 | -0.260 | 29.1 |
| T1 asia: toward the POC, price outside the value area | BIN unseen | 66 | 36.7 % (22 / 60) | -2.1 | -0.234 | -0.247 | -0.275 | 29.4 |
| T1 asia: toward the POC, price outside the value area | BIN seen (20 screenshot days) | 6 | 33.3 % (2 / 6) | -0.8 | -0.333 | -0.353 | -0.397 | 16.9 |
| T1 london: AWAY from the POC (trend day), price outside the value area | DUKA all | 452 | 52.9 % (208 / 393) | 1.2 | +0.051 | +0.008 | -0.088 | 11.3 |
| T1 london: AWAY from the POC (trend day), price outside the value area | DUKA DEV | 268 | 52.8 % (124 / 235) | 0.8 | +0.053 | -0.004 | -0.128 | 6.1 |
| T1 london: AWAY from the POC (trend day), price outside the value area | DUKA VAL | 136 | 53.1 % (60 / 113) | 0.7 | +0.043 | +0.015 | -0.046 | 17.0 |
| T1 london: AWAY from the POC (trend day), price outside the value area | DUKA OOS | 48 | 53.3 % (24 / 45) | 0.4 | +0.063 | +0.048 | +0.016 | 24.2 |
| T1 london: AWAY from the POC (trend day), price outside the value area | BIN unseen | 56 | 51.0 % (25 / 49) | 0.1 | +0.002 | -0.016 | -0.055 | 27.1 |
| T1 london: AWAY from the POC (trend day), price outside the value area | BIN seen (20 screenshot days) | 5 | 100.0 % (4 / 4) | 2.0 | +0.912 | +0.896 | +0.861 | 19.6 |
| T1 london: toward the POC, price inside the value area | DUKA all | 479 | 48.8 % (228 / 467) | -0.5 | -0.024 | -0.115 | -0.317 | 5.8 |
| T1 london: toward the POC, price inside the value area | DUKA DEV | 280 | 47.1 % (129 / 274) | -1.0 | -0.061 | -0.185 | -0.458 | 3.1 |
| T1 london: toward the POC, price inside the value area | DUKA VAL | 149 | 51.7 % (76 / 147) | 0.4 | +0.035 | -0.020 | -0.140 | 7.5 |
| T1 london: toward the POC, price inside the value area | DUKA OOS | 50 | 50.0 % (23 / 46) | 0.0 | +0.013 | -0.011 | -0.062 | 15.7 |
| T1 london: toward the POC, price inside the value area | BIN unseen | 97 | 39.4 % (37 / 94) | -2.1 | -0.197 | -0.223 | -0.279 | 14.8 |
| T1 london: toward the POC, price inside the value area | BIN seen (20 screenshot days) | 9 | 55.6 % (5 / 9) | 0.3 | +0.111 | +0.083 | +0.022 | 9.9 |
| T1 london: toward the POC, price outside the value area | DUKA all | 452 | 45.5 % (179 / 393) | -1.8 | -0.078 | -0.121 | -0.217 | 11.3 |
| T1 london: toward the POC, price outside the value area | DUKA DEV | 268 | 45.1 % (106 / 235) | -1.5 | -0.090 | -0.147 | -0.271 | 6.1 |
| T1 london: toward the POC, price outside the value area | DUKA VAL | 136 | 46.0 % (52 / 113) | -0.8 | -0.058 | -0.085 | -0.146 | 17.0 |
| T1 london: toward the POC, price outside the value area | DUKA OOS | 48 | 46.7 % (21 / 45) | -0.4 | -0.063 | -0.078 | -0.110 | 24.2 |
| T1 london: toward the POC, price outside the value area | BIN unseen | 56 | 49.0 % (24 / 49) | -0.1 | -0.002 | -0.020 | -0.059 | 27.1 |
| T1 london: toward the POC, price outside the value area | BIN seen (20 screenshot days) | 5 | 0.0 % (0 / 4) | -2.0 | -0.912 | -0.928 | -0.964 | 19.6 |
| T3 asia: toward yesterday's POC | DUKA all | 791 | 50.0 % (368 / 736) | 0.0 | +0.003 | -0.053 | -0.178 | 11.5 |
| T3 asia: toward yesterday's POC | DUKA DEV | 449 | 53.1 % (228 / 429) | 1.3 | +0.063 | -0.017 | -0.192 | 5.6 |
| T3 asia: toward yesterday's POC | DUKA VAL | 247 | 46.2 % (102 / 221) | -1.1 | -0.067 | -0.098 | -0.165 | 16.1 |
| T3 asia: toward yesterday's POC | DUKA OOS | 95 | 44.2 % (38 / 86) | -1.1 | -0.093 | -0.109 | -0.144 | 27.9 |
| T3 asia: toward yesterday's POC | BIN unseen | 139 | 44.8 % (52 / 116) | -1.1 | -0.081 | -0.098 | -0.134 | 27.2 |
| T3 asia: toward yesterday's POC | BIN seen (20 screenshot days) | 10 | 44.4 % (4 / 9) | -0.3 | -0.098 | -0.114 | -0.150 | 22.6 |
| T4 london: with the POC move since Asia | DUKA all | 558 | 48.2 % (266 / 552) | -0.9 | -0.038 | -0.085 | -0.189 | 9.2 |
| T4 london: with the POC move since Asia | DUKA DEV | 298 | 44.7 % (132 / 295) | -1.8 | -0.104 | -0.172 | -0.322 | 4.1 |
| T4 london: with the POC move since Asia | DUKA VAL | 169 | 50.3 % (84 / 167) | 0.1 | +0.002 | -0.027 | -0.091 | 12.7 |
| T4 london: with the POC move since Asia | DUKA OOS | 91 | 55.6 % (50 / 90) | 1.1 | +0.106 | +0.092 | +0.061 | 19.3 |
| T4 london: with the POC move since Asia | BIN unseen | 138 | 58.5 % (79 / 135) | 2.0 | +0.168 | +0.154 | +0.123 | 21.5 |
| T4 london: with the POC move since Asia | BIN seen (20 screenshot days) | 12 | 41.7 % (5 / 12) | -0.6 | -0.167 | -0.182 | -0.217 | 17.3 |
| T5 POC shift: with the shift | DUKA all | 5515 | 51.8 % (2063 / 3983) | 2.3 | +0.025 | -0.009 | -0.082 | 13.4 |
| T5 POC shift: with the shift | DUKA DEV | 2077 | 51.9 % (742 / 1430) | 1.4 | +0.027 | -0.029 | -0.153 | 5.2 |
| T5 POC shift: with the shift | DUKA VAL | 2185 | 50.9 % (817 / 1605) | 0.7 | +0.008 | -0.016 | -0.068 | 16.0 |
| T5 POC shift: with the shift | DUKA OOS | 1253 | 53.2 % (504 / 948) | 1.9 | +0.051 | +0.038 | +0.010 | 22.5 |
| T5 POC shift: with the shift | BIN unseen | 1623 | 53.1 % (642 / 1209) | 2.2 | +0.043 | +0.030 | +0.001 | 24.8 |
| T5 POC shift: with the shift | BIN seen (20 screenshot days) | 144 | 50.4 % (57 / 113) | 0.1 | +0.003 | -0.011 | -0.042 | 18.5 |
| T6 80 % rule: back into yesterday's value area, toward its far side | DUKA all | 337 | 51.9 % (122 / 235) | 0.6 | +0.029 | -0.002 | -0.070 | 19.7 |
| T6 80 % rule: back into yesterday's value area, toward its far side | DUKA DEV | 202 | 50.3 % (72 / 143) | 0.1 | -0.006 | -0.046 | -0.134 | 11.0 |
| T6 80 % rule: back into yesterday's value area, toward its far side | DUKA VAL | 96 | 49.2 % (32 / 65) | -0.1 | +0.003 | -0.016 | -0.058 | 27.8 |
| T6 80 % rule: back into yesterday's value area, toward its far side | DUKA OOS | 39 | 66.7 % (18 / 27) | 1.7 | +0.271 | +0.260 | +0.235 | 45.0 |
| T6 80 % rule: back into yesterday's value area, toward its far side | BIN unseen | 52 | 47.4 % (18 / 38) | -0.3 | -0.003 | -0.013 | -0.036 | 45.6 |
| T6 80 % rule: back into yesterday's value area, toward its far side | BIN seen (20 screenshot days) | 8 | 40.0 % (2 / 5) | -0.4 | -0.083 | -0.100 | -0.138 | 34.2 |

Runtime 8 s. Per-day numbers: days_binance.csv, days_dukascopy.csv; every trade: trades_*.csv.
