# SimpleSMA18Bot research reports (26 Sep 2026)

| File | What it is |
|---|---|
| Report1_Backtest_M1_M5_M15_D1.html | Visual report 1: untouched EA on M1/M5/M15/D1, $200 account, D1 over 23 years, profit giveback, filters, stops, exits, walk-forward, candidate, EA changes (open in a browser; needs internet for the chart library) |
| Report1_Backtest_M1_M5_M15_D1.md | The same study as text with all tables |
| Report2_H1_H4_Sessions_SMA_2023-2026.html | Visual report 2: H1 and H4 through the same pipeline, profit by session/hour/weekday, the EA's session filter, the 2023-2026 window, and the fast/trend SMA sweep |
| Report2_H1_H4_Sessions_SMA_2023-2026.md | The same study as text |
| Report3_H4_Final_Config.html | Visual report 3: the H4 study with equity curves, exit-grid heat tables, filters, stops, MA map, walk-forward, sensitivity and Monte Carlo (needs internet for the chart library) |
| Report3_H4_Final_Config.md | Study 3: H4 only, from the E19 exit stack to the final configuration (exit grid, filters, stops, MA sensitivity, walk-forward, 2003-2026 check, Monte Carlo) and the EA changes |
| SimpleSMA18Bot_H4.mq5 / .ex5 | The updated EA (v1.00 + ATR-scaled levels, H4 defaults), compiled with 0 errors; the working copy is one folder up next to the original |
| Report4_H4_Dynamic_Lots_Partial.md | Study 4: tiered lot sizing ($200 -> 0.01, doubling with the balance) and the scaled partial exit, validated on $200 accounts; verdict and safer settings |
| SimpleSMA18Bot_H4_Dynamic.mq5 / .ex5 | The H4 EA plus dynamic lots and partial exit (inputs UseDynamicLots, BaseBalance, BaseLot, MaxLot, EnablePartialExit, PartialProfitBaseUSD, PartialProfitDoubles, PartialExitPercent, PartialAtMinLot); compiled with 0 errors |
| Report5_H4_Final_EA_Backtest.html | Backtest of SimpleSMA18Bot_H4_Final with its shipped defaults from $200 (balance curves, yearly net, start-year sensitivity, lot tiers, Monte Carlo, last-12-month deals) |
| SimpleSMA18Bot_H4_Final.mq5 / .ex5 | The final EA v2.11 (v2.10 plus: a partial-close request the server rejects, e.g. "market closed" at the Monday 01:00 open, is retried after PartialRetrySeconds instead of being marked done): all filters kept and configurable; lots from the balance with LotMode LOT_LINEAR (0.01 per $500: 0.01, 0.02, 0.03 ...; LOT_DOUBLING selectable), MaxLot 0.20; profit-side partial exit (50% at $50 per 0.01 lot, floor $100) and loss-side partial exit (50% at a $50-per-0.01-lot floating loss, floor $100), PartialAtMinLot SKIP, 1% gate off; compiled with 0 errors |
| Report6_H4_Final_EA_v2.10_Backtest.html | Backtest of v2.10 from $200 (six years, 2023-2026, 1 Jan 2025 to 25 Sep 2026, last 12 months) against the doubling version and a fixed lot |
| Report7_Tester_Verification.md | 27 Sep 2026: your MT5 tester figures and the other machine's ReportTester-318754366.xlsx (GOLD.i#, swap 0 on every deal, $9,066) checked against the engine window by window; cost grid (swap / spread / protection mode); the Monday-open partial-close bug found in the tester log and fixed in v2.11; root causes ranked |
| Report7_*.csv | Your 13:47 tester run paired into positions, the other machine's 180 positions, and the engine's deals for 2023-2026 (Chandelier and trailing) |
| EA_Component_Map.md | What the EA code does, input by input, with the tick-flow diagram |
| Data_Audit.md | Data sources, gaps, broker comparison, spread model |
| experiment_log.csv | Every backtest run (about 1,000 rows): parameters, filters, exit logic, results, conclusion |
| research_tables.xlsx | All tables and the trade-level data of report 1 as a workbook |

Online copies: report 1 https://claude.ai/artifact/M9AofE6MLzRJUq5rk8NxEN, report 2 https://claude.ai/artifact/WDDbTWshhHdBXPDbc5kHgm (private links).
Engine, data and scripts: ../research/ (see its README.md).
