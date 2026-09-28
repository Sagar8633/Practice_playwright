# $200 account analysis

Broker facts (XM Global MT5 GOLD, read from the terminal on 2026-09-26): min lot 0.01 = 1 oz, so $1.00 of gold = $1.00 P&L; the EA cannot size below 0.01 lot. Margin per 0.01 lot at 1:1000 = $4.29 (at $4,286 gold), stop-out at 20% margin level, i.e. only when equity is under ~$0.90. Margin call and stop-out are therefore irrelevant for this EA; the account dies by losses long before margin matters.

| TF | trades | median risk $ | p90 risk $ | max risk $ | median risk % of $200 | p90 % | share risk > 1% | > 5% | > 20% | min account for 1% rule (median trade) | (p90 trade) | worst loss $ | max consec losses | worst streak $ | MC p(ruin) shuffle | MC p(ruin) bootstrap | MC DD p95 | historical first ruin | swap % of gross |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1 | 54900 | 2.1 | 6.8 | 111.84 | 1.0 | 3.4 | 0.525 | 0.046 | 0.002 | $210 | $680 | -42.94 | 45 | -128.19 | 1.0 | 1.0 | 30297.92 | 2020-09-11 | -0.5 |
| M5 | 12320 | 4.36 | 15.97 | 196.6 | 2.2 | 8.0 | 0.861 | 0.203 | 0.015 | $436 | $1597 | -74.38 | 38 | -177.22 | 1.0 | 1.0 | 5321.25 | 2020-10-05 | -2.5 |
| M15 | 4559 | 8.17 | 29.44 | 380.85 | 4.1 | 14.7 | 0.977 | 0.411 | 0.051 | $817 | $2944 | -79.84 | 51 | -281.21 | 1.0 | 0.9633 | 1796.87 | 2021-04-14 | -22.6 |
| D1 | 85 | 91.96 | 224.87 | 424.9 | 46.0 | 112.4 | 1.0 | 1.0 | 0.906 | $9196 | $22487 | -111.65 | 8 | -111.65 | 0.018 | 0.0817 | 222.53 | never | -30.0 |

## The EA exactly as provided on $200 (UseSLPercentFilter = true, 1%)

| TF | cost | trades taken | blocked by the 1% rule | net $ | PF | max DD $ | end balance |
|---|---|---:|---:|---:|---:|---:|---:|
| M1 | A_low | 702 | 440778.0 | -193.49 | 0.401 | 193.49 | 6.51 |
| M1 | B_real | 349 | 442883.0 | -196.36 | 0.186 | 196.36 | 3.64 |
| M1 | C_stress | 172 | 443968.0 | -196.46 | 0.053 | 196.46 | 3.54 |
| M5 | A_low | 867 | 81903.0 | -160.38 | 0.734 | 183.6 | 39.62 |
| M5 | B_real | 469 | 84304.0 | -170.36 | 0.577 | 170.36 | 29.64 |
| M5 | C_stress | 182 | 86067.0 | -175.74 | 0.267 | 175.74 | 24.26 |
| M15 | A_low | 289 | 28542.0 | -45.91 | 0.838 | 68.09 | 154.09 |
| M15 | B_real | 166 | 29219.0 | -83.52 | 0.557 | 83.52 | 116.48 |
| M15 | C_stress | 81 | 29730.0 | -115.12 | 0.084 | 115.12 | 84.88 |
| D1 | A_low | 0 | 370.0 | 0.0 | nan | 0.0 | 200.0 |
| D1 | B_real | 0 | 370.0 | 0.0 | nan | 0.0 | 200.0 |
| D1 | C_stress | 0 | 370.0 | 0.0 | nan | 0.0 | 200.0 |

## The strategy exposed to $200 (filter off, fixed 0.01 lot)

| TF | cost | trades | net $ | PF | max DD $ | ruin | end balance |
|---|---|---:|---:|---:|---:|---|---:|
| M1 | A_low | 668 | -198.5 | 0.618 | 198.5 | False | 1.5 |
| M1 | B_real | 284 | -199.25 | 0.356 | 199.25 | False | 0.75 |
| M1 | C_stress | 132 | -198.98 | 0.143 | 198.98 | False | 1.02 |
| M5 | A_low | 356 | -198.5 | 0.643 | 203.93 | False | 1.5 |
| M5 | B_real | 185 | -199.04 | 0.462 | 201.7 | False | 0.96 |
| M5 | C_stress | 143 | -200.29 | 0.408 | 200.56 | True | -0.29 |
| M15 | A_low | 607 | -198.81 | 0.84 | 227.33 | False | 1.19 |
| M15 | B_real | 404 | -199.83 | 0.783 | 199.83 | True | 0.17 |
| M15 | C_stress | 119 | -200.42 | 0.45 | 200.42 | True | -0.42 |
| D1 | A_low | 85 | 894.51 | 5.022 | 150.17 | False | 1094.51 |
| D1 | B_real | 85 | 619.14 | 2.946 | 179.4 | False | 819.14 |
| D1 | C_stress | 38 | -199.94 | 0.376 | 206.96 | True | 0.06 |