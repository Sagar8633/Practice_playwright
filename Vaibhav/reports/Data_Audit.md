# GOLD data audit

Source: Dukascopy XAUUSD bid candles (dukascopy-node), UTC, 3-decimal prices, traded volume (not tick count). Broker reference: XM Global MT5 GOLD (digits 2, point 0.01, contract 100 oz, 0.01 lot = 1 oz).

## Primary dataset: M1

| Item | Value |
|---|---|
| Start (UTC) | 2020-09-01 00:00:00 |
| End (UTC) | 2026-09-25 13:37:00 |
| Start / end (server time) | 2020-09-01 03:00:00 / 2026-09-25 16:37:00 |
| Raw rows | 2,151,947 |
| Duplicate timestamps dropped | 0 |
| Flat zero-volume rows dropped | 0 |
| Final rows | 2,151,947 |
| high < low | 0 |
| open outside [low, high] | 0 |
| close outside [low, high] | 0 |
| non-positive prices | 0 |
| NaN rows | 0 |
| misaligned timestamps | 0 |
| weekend gaps | 327 |
| intraweek gaps (any missing minute) | 1,638 |
| intraweek gaps >= 1 h | 1269 |
| one-bar moves > 1% | 26 |
| one-bar moves > 3% | 0 |
| moves > 20x median bar range | 116 |

Transformations: prices rounded to 0.01 (XM GOLD point); Dukascopy supplies 3 decimals; UTC -> XM server time (EET: UTC+2, UTC+3 in EU summer time). No gap filling, no bar synthesis.

### Largest intraweek gaps (M1)

| From (UTC) | To (UTC) | Hours |
|---|---|---:|
| 2020-12-24 18:44:00 | 2020-12-27 23:00:00 | 76.3 |
| 2020-12-31 21:59:00 | 2021-01-03 23:00:00 | 73.0 |
| 2021-04-01 20:59:00 | 2021-04-04 22:00:00 | 73.0 |
| 2021-12-23 21:58:00 | 2021-12-26 23:00:00 | 73.0 |
| 2022-04-14 20:58:00 | 2022-04-17 22:00:00 | 73.0 |
| 2020-11-27 18:44:00 | 2020-11-29 23:00:00 | 52.3 |
| 2021-11-26 18:43:00 | 2021-11-28 23:00:00 | 52.3 |
| 2021-11-25 17:58:00 | 2021-11-25 23:18:00 | 5.3 |
| 2020-09-07 16:59:00 | 2020-09-07 22:00:00 | 5.0 |
| 2020-11-26 17:59:00 | 2020-11-26 23:00:00 | 5.0 |
| 2021-01-18 17:59:00 | 2021-01-18 23:00:00 | 5.0 |
| 2021-02-15 17:59:00 | 2021-02-15 23:00:00 | 5.0 |
| 2021-05-31 16:59:00 | 2021-05-31 22:00:00 | 5.0 |
| 2021-07-05 16:59:00 | 2021-07-05 22:00:00 | 5.0 |
| 2021-09-06 16:59:00 | 2021-09-06 22:00:00 | 5.0 |

### Bars per month (M1)

| Month | Bars |
|---|---:|
| 2020-09 | 30,116 |
| 2020-10 | 30,239 |
| 2020-11 | 28,601 |
| 2020-12 | 30,098 |
| 2021-01 | 27,419 |
| 2021-02 | 27,359 |
| 2021-03 | 31,797 |
| 2021-04 | 28,855 |
| 2021-05 | 28,857 |
| 2021-06 | 30,358 |
| 2021-07 | 30,000 |
| 2021-08 | 30,469 |
| 2021-09 | 30,119 |
| 2021-10 | 28,974 |
| 2021-11 | 29,845 |
| 2021-12 | 30,294 |
| 2022-01 | 28,799 |
| 2022-02 | 27,448 |
| 2022-03 | 31,799 |
| 2022-04 | 27,477 |
| 2022-05 | 30,327 |
| 2022-06 | 30,209 |
| 2022-07 | 28,827 |
| 2022-08 | 31,734 |
| 2022-09 | 30,089 |
| 2022-10 | 29,082 |
| 2022-11 | 29,935 |
| 2022-12 | 28,907 |
| 2023-01 | 28,794 |
| 2023-02 | 27,443 |
| 2023-03 | 31,673 |
| 2023-04 | 26,328 |
| 2023-05 | 31,583 |
| 2023-06 | 30,075 |
| 2023-07 | 28,919 |
| 2023-08 | 31,674 |
| 2023-09 | 28,658 |
| 2023-10 | 30,464 |
| 2023-11 | 29,824 |
| 2023-12 | 27,534 |
| 2024-01 | 30,268 |
| 2024-02 | 28,808 |
| 2024-03 | 27,649 |
| 2024-04 | 30,359 |
| 2024-05 | 31,463 |
| 2024-06 | 27,567 |
| 2024-07 | 31,587 |
| 2024-08 | 30,240 |
| 2024-09 | 28,945 |
| 2024-10 | 31,671 |
| 2024-11 | 28,572 |
| 2024-12 | 28,763 |
| 2025-01 | 30,197 |
| 2025-02 | 27,440 |
| 2025-03 | 29,073 |
| 2025-04 | 28,950 |
| 2025-05 | 30,087 |
| 2025-06 | 28,949 |
| 2025-07 | 31,499 |
| 2025-08 | 28,971 |
| 2025-09 | 30,209 |
| 2025-10 | 31,620 |
| 2025-11 | 27,358 |
| 2025-12 | 30,062 |
| 2026-01 | 28,828 |
| 2026-02 | 27,430 |
| 2026-03 | 30,476 |
| 2026-04 | 28,977 |
| 2026-05 | 28,827 |
| 2026-06 | 30,119 |
| 2026-07 | 31,379 |
| 2026-08 | 29,100 |
| 2026-09 | 25,502 |

### Per year (M1)

| Year | Bars | Median close | Low | High | Median bar range |
|---|---:|---:|---:|---:|---:|
| 2020 | 119,054 | 1888.76 | 1764.24 | 1992.30 | 0.483 |
| 2021 | 354,346 | 1793.64 | 1670.49 | 1959.22 | 0.390 |
| 2022 | 354,633 | 1804.51 | 1614.71 | 2070.36 | 0.435 |
| 2023 | 352,969 | 1945.01 | 1804.59 | 2145.14 | 0.370 |
| 2024 | 355,892 | 2380.78 | 1984.09 | 2790.01 | 0.550 |
| 2025 | 354,415 | 3344.72 | 2614.36 | 4549.72 | 1.050 |
| 2026 | 260,638 | 4525.64 | 3941.53 | 5596.81 | 2.060 |

### Largest one-bar moves (M1)

| Time (UTC) | Open | High | Low | Close | Move % |
|---|---:|---:|---:|---:|---:|
| 2021-08-08 22:57:00 | 1715.958 | 1717.033 | 1670.488 | 1670.488 | 2.65 |
| 2026-01-29 15:27:00 | 5257.385 | 5260.258 | 5126.138 | 5132.298 | 2.37 |
| 2025-04-22 22:00:00 | 3349.515 | 3349.515 | 3312.625 | 3319.835 | 1.78 |
| 2022-02-27 23:00:00 | 1919.206 | 1930.948 | 1918.283 | 1921.303 | 1.74 |
| 2026-04-12 22:00:00 | 4634.998 | 4670.725 | 4634.998 | 4670.135 | 1.62 |
| 2026-02-01 23:06:00 | 4817.598 | 4817.598 | 4817.598 | 4817.598 | 1.58 |
| 2026-09-04 12:30:00 | 4470.485 | 4471.305 | 4389.145 | 4401.645 | 1.57 |
| 2025-05-11 22:00:00 | 3271.805 | 3272.975 | 3271.805 | 3272.975 | 1.52 |
| 2026-02-02 01:10:00 | 4653.955 | 4658.965 | 4583.098 | 4584.335 | 1.50 |
| 2026-07-14 12:30:00 | 4029.605 | 4089.025 | 4028.915 | 4084.175 | 1.35 |

## Long-history dataset: H1 (for D1 before Sep 2020)

| Item | Value |
|---|---|
| Start / end (server) | 2003-05-05 03:00:00 / 2026-09-25 16:00:00 |
| Rows | 141,378 |
| Dukascopy H1 used until | 2020-09-01 03:00:00 (then H1 resampled from M1) |
| Duplicates dropped | 0 |
| high < low | 0 |
| intraweek gaps >= 1 h (H1 step) | 1531 |
| one-bar moves > 3% | 12 |

### Per year (H1)

| Year | Bars | Median close | Low | High |
|---|---:|---:|---:|---:|
| 2003 | 4,001 | 371.53 | 339.00 | 417.30 |
| 2004 | 6,225 | 405.75 | 370.63 | 456.48 |
| 2005 | 6,187 | 434.04 | 409.64 | 540.50 |
| 2006 | 6,192 | 611.42 | 514.95 | 730.05 |
| 2007 | 6,213 | 670.43 | 601.59 | 845.33 |
| 2008 | 6,236 | 883.16 | 682.00 | 1031.83 |
| 2009 | 6,212 | 947.43 | 801.83 | 1225.94 |
| 2010 | 6,210 | 1212.78 | 1044.70 | 1430.94 |
| 2011 | 6,165 | 1543.36 | 1308.23 | 1920.66 |
| 2012 | 6,161 | 1663.21 | 1526.92 | 1795.85 |
| 2013 | 6,049 | 1372.70 | 1180.27 | 1696.05 |
| 2014 | 6,047 | 1274.73 | 1131.55 | 1389.12 |
| 2015 | 5,988 | 1168.30 | 1046.23 | 1307.47 |
| 2016 | 5,927 | 1256.73 | 1061.73 | 1375.08 |
| 2017 | 5,912 | 1260.58 | 1146.04 | 1357.50 |
| 2018 | 5,906 | 1263.17 | 1160.17 | 1366.00 |
| 2019 | 5,910 | 1405.95 | 1266.19 | 1556.96 |
| 2020 | 5,927 | 1774.21 | 1451.15 | 2074.80 |
| 2021 | 5,907 | 1793.81 | 1670.49 | 1959.22 |

## Broker check: XM GOLD vs Dukascopy (M15 overlap, Jul 2022 - Sep 2026)

| Item | Value |
|---|---|
| overlap_bars_M15 | 98983 |
| xm_bars_without_duka_match | 17 |
| close_diff_median_abs | 0.05 |
| close_diff_p90_abs | 0.17 |
| close_diff_mean_signed | 0.0403 |
| high_diff_median_abs | 0.05 |
| range_ratio_xm_over_duka_median | 0.997 |
| volume_corr_xm_tickvol_vs_duka_volume | 0.584 |
| volume_filter_agreement_M15 | 0.821 |
| volume_filter_pass_rate_xm | 0.46 |
| volume_filter_pass_rate_dk | 0.434 |

XM trading hours (server): first bar 01:00, last bar 23:45. Dukascopy has bars from Sunday 22:00 UTC; XM GOLD opens Monday ~01:05 server. Bars outside XM hours are kept in the data and flagged in the engine as non-tradable.

## Spread (XM GOLD, points, from XM's own bars)

| Item | Value |
|---|---|
| m15_close_median_by_year | {'2022': 25.0, '2023': 25.0, '2024': 28.0, '2025': 30.0, '2026': 40.0} |
| m5_close_median_by_year | {'2025': 33.0, '2026': 45.0} |
| m1_close_median_2026 | 51.0 |
| m1_p90_2026 | 54.0 |
| m1_p99_2026 | 59.0 |
| m1_over_m15_ratio_2026 | 1.275 |
| note | Years before 2022 use the 2022 profile (no XM data); XM GOLD spread in 2005-2015 is unknown, this is an assumption. |
| abnormal_spread_bars_M1_2026_gt_150pts | 85 |
| abnormal_spread_bars_M15_gt_100pts | 9 |

M1 median spread by server hour, 2026: 1h 55.0, 2h 54.0, 3h 53.0, 4h 52.0, 5h 52.0, 6h 52.0, 7h 52.0, 8h 52.0, 9h 51.0, 10h 51.0, 11h 51.0, 12h 51.0, 13h 51.0, 14h 51.0, 15h 51.0, 16h 51.0, 17h 51.0, 18h 51.0, 19h 51.0, 20h 51.0, 21h 51.0, 22h 51.0, 23h 52.0

## Verdicts

- Timeframes supported: M1, M5, M15 (built from M1) for 6 years 1 month (Sep 2020 - Sep 2026); D1 for 23 years (2003 - 2026) with H1 intrabar path before Sep 2020 and M1 path after.
- Prices are Dukascopy's Swiss-bank feed, not XM's. XM closes differ by a few cents at the median (see table); XM's bar ranges are slightly wider. Results are therefore feed-specific and the tester on XM would differ trade by trade.
- Volume is Dukascopy traded volume, not MT5 tick volume. The EA's volume filter is ratio-based; agreement between the two feeds is reported above and is well below 100%, so trade lists cannot match the MT5 tester one for one.
- Spread: Dukascopy candles carry no spread. XM's real spread by year and hour is applied (M1-equivalent). Before 2022 the spread is an assumption.
- No spread abnormalities are in the price data itself; XM's own spread shows widening at 00:00-02:00 server and at news (p99 reported).