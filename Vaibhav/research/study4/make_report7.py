"""Report 7: verification of the MT5 tester results (user's terminal, GOLD on XMGlobal-MT5 2; another machine's
GOLD.i# report on XMGlobal-MT5 7) against the research engine, and the v2.11 fix."""
import json, os, shutil
import pandas as pd, sma18_engine as E, common as C

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); VAIB = os.path.dirname(ROOT); REP = os.path.join(VAIB, "reports")
S = "C:/Users/samja/AppData/Local/Temp/claude/d--Practice-Playwright/8ddb4bca-06dc-4cfc-bedf-0da60028424b/scratchpad"
P = json.load(open(os.path.join(ROOT, "study3", "results", "study3.json")))["final"]["params"]
V210 = dict(tf_minutes=240, margin_check=True, use_sl_pct=False, lots=0.01, partial_min_mode=0, partial_pct=50.0, sizing=3, base_balance=500.0, max_lots=0.10,
            partial_enable=True, partial_per01=50.0, partial_min_usd=100.0, ploss_enable=True, ploss_per01=50.0, ploss_min_usd=100.0, ploss_pct=50.0, **P)
CH = dict(protection=2, prot_start_mode=0)

# ---- cost grid with drawdowns
grid = []
for prot_nm, prot in [("Trailing (your default)", {}), ("Chandelier", CH)]:
    for cost_nm, cost in [("XM GOLD: spread model + 10 pt slippage + swap", C.COST["B_real"]),
                          ("same spread and slippage, swap = 0", {**C.COST["B_real"], "swap": False}),
                          ("25 pt spread, no slippage, no swap", C.COST["A_low"])]:
        p = E.Params(start="2023-01-01", end="2026-09-26", start_balance=200.0, **{**V210, **cost, **prot}); tr, st = E.run(p)
        y = tr.groupby(tr.time_out.dt.year).pnl.sum(); steps = tr.groupby("lots").time_in.min()
        grid.append(dict(prot=prot_nm, cost=cost_nm, end=st["final_balance"], pos=int((tr.reason < 14).sum()), swap=tr.swap.sum(),
                         dd_b=st["maxdd_balance"], dd_e=st["maxdd_equity"], y=y, l002=steps.get(0.02), l005=steps.get(0.05), l010=steps.get(0.10)))

U = pd.read_csv(f"{S}/tester_positions_2026.csv", parse_dates=["t_in", "t_out"])
O = pd.read_csv(f"{S}/other_tester_positions_2023.csv", parse_dates=["t_in", "t_out"])
Oy = O.groupby(O.t_out.dt.year).agg(pnl=("pnl", "sum"), n=("pnl", "size"), maxlot=("lots_in", "max"), bal=("bal", "last"))
Ech = grid[3]; Ech0 = grid[4]


def d(t):
    return "never" if t is None or pd.isna(t) else str(t)[:10]


def money(x):
    return f"${x:,.0f}"


L = []
L.append("# Report 7: Tester verification, 27 Sep 2026\n")
L.append("Question answered: your MT5 tester figures ($4,798 / $1,892 / $100 / $95 / $1,598), the other machine's report "
         "ReportTester-318754366.xlsx ($9,066, 2023-2026) and the research engine disagree. Which is right, what is wrong, "
         "what is the root cause, and which protection mode is effective.\n")
L.append("Short answer: nothing is miscalculated. The three sources price the same strategy under different costs and data. "
         "The other machine ran GOLD.i# on XMGlobal-MT5 7 with **zero swap on all 391 deals**; the engine reproduces its level "
         "only when swap is switched off. Your terminal runs GOLD on XMGlobal-MT5 2 with swap, and lands within 1-12% of the "
         "engine. One real EA bug was found in your log and fixed in v2.11: partial-close requests rejected at the Monday "
         "01:00 open were never retried.\n")

L.append("## 1. The three sources\n")
L.append("| Source | Symbol / server | Data | Costs | Protection | Lots |\n|---|---|---|---|---|---|")
L.append("| Your tester (journal + agent log of 27 Sep) | GOLD, XMGlobal-MT5 2 | generated ticks from M1, 200 ms delay | "
         "XM spread, swap charged (about -$54 over Jan-Sep 2026) | TRAILING (ProtectionMode=3) | linear, base $500, MaxLot 0.10 |")
L.append("| Other machine (ReportTester-318754366.xlsx) | GOLD.i#, XMGlobal-MT5 7 | 30% real ticks | "
         "**swap 0 and commission 0 on every deal** | CHANDELIER (ProtectionMode=2) | linear, base $500, MaxLot 0.10 |")
L.append("| Research engine (sma18_engine.py) | Dukascopy XAUUSD M1, XM server time | M1 intrabar path | "
         "XM spread model by year and hour, 10 pt slippage, swap long -86.84 / short +19.79 pts, triple Wednesday | both, run separately | same |\n")

L.append("## 2. Your figures, one by one\n")
L.append("| Your figure | What the log says it was | Engine, same window and settings | Verdict |\n|---|---|---|---|")
L.append("| $4,798 (1 Jan 2023 - 25 Sep 2026, trailing) | run at 13:38, v2.10 build, MaxLot 0.10 | $5,450 (MaxLot 0.10), $4,846 (MaxLot 0.20) | "
         "consistent: -12% / -1%; the gap is feed and the Monday bug (section 5) |")
L.append("| $1,598 \"last year\" | the only run with a surviving log (13:47): **1 Jan 2026 - 26 Sep 2026**, ProtectionMode=3 TRAILING, MaxLot 0.10, "
         "final balance 1598.58 | $2,147 (trailing), $1,939 (Chandelier) | window mislabelled: this is this year, not last year; "
         "3 partial closes lost to the Monday bug (about -$80 plus compounding); rest is feed |")
L.append("| $1,892 \"last year\" | no run with that window exists in today's journal; equals the engine's previous doubling build on the tester's "
         "Last-year preset (26 Sep 2025 - 26 Sep 2026): $1,890.48 | v2.10 on that preset: $2,706 trailing / $3,075 Chandelier | "
         "figure belongs to the earlier LOT_DOUBLING build or another terminal |")
L.append("| $100 / $95 \"last month\" (trailing / Chandelier) | runs at 13:45 and 13:46: 1 - 26 Sep 2026 | $132 / $138 (3 positions; the testers had 4, "
         "the 14 Sep short is missing on Dukascopy volume) | consistent: September is a losing month in every source, the $30 gap is one extra trade and fills |\n")
L.append("Journal windows used today (all visual mode): 2026-01-01 to 09-26 (six runs), 2026-09-01 to 09-26 (six), 2025-01-01 to 09-25 (five, the first "
         "three before the v2.10 build was copied at 13:05), 2024-01-01 and 2020-01-01 to 09-26, 2023-01-01 to 09-25. The tester's Last year preset "
         "is the previous 12 months, not the calendar year.\n")

L.append("## 3. The other machine's report against the engine\n")
L.append("Deals paired into 180 positions (391 deals). Every deal has swap 0.00 and commission 0.00: a swap-free symbol or account. Below, the same "
         "window in the engine with Chandelier, once with XM swap and once with swap 0.\n")
L.append("| Year | Other machine: net | positions | max lot | balance | Engine Chandelier, XM swap | Engine Chandelier, swap 0 |\n|---|---|---|---|---|---|---|")
for yr in [2023, 2024, 2025, 2026]:
    L.append(f"| {yr} | {money(Oy.loc[yr, 'pnl'])} | {int(Oy.loc[yr, 'n'])} | {Oy.loc[yr, 'maxlot']:.2f} | {money(Oy.loc[yr, 'bal'])} | "
             f"{money(Ech['y'].get(yr, 0))} | {money(Ech0['y'].get(yr, 0))} |")
L.append(f"| **Total** | **{money(O.pnl.sum())}** (ends $9,266) | 180 | 0.10 | | **{money(Ech['end'] - 200)}** (ends {money(Ech['end'])}) | "
         f"**{money(Ech0['end'] - 200)}** (ends {money(Ech0['end'])}) |\n")
L.append(f"Lot steps: the other machine reached 0.02 on {d(O[O.lots_in >= 0.02].t_in.min())}, 0.05 on {d(O[O.lots_in >= 0.05].t_in.min())} and 0.10 on "
         f"{d(O[O.lots_in >= 0.10].t_in.min())}; the engine with XM swap reached 0.02 on {d(Ech['l002'])}, 0.05 on {d(Ech['l005'])} and 0.10 {d(Ech['l010'])}; "
         f"with swap 0 it reached 0.02 on {d(Ech0['l002'])}, 0.05 on {d(Ech0['l005'])} and 0.10 on {d(Ech0['l010'])}. Swap paid directly is only about "
         "$330 at these lots, but every dollar lost early delays the next lot step, so 2026 is traded at 0.03-0.05 lot instead of 0.10 and the final "
         "gap is about $3,000.\n")
L.append("87% of the other machine's profit ($7,934 of $9,066) is 2026 at 0.05-0.10 lot; 2023 made $76 and 2024 $315 at 0.01 lot. Largest single loss "
         "-$701 (4-6 May 2026, 0.10 lot), equity drawdown 31%. The regime caveat of every earlier report stands.\n")
L.append("Feed agreement: 165 of the 180 positions have an engine counterpart with the same side within 36 h; the median entry-price gap is $0.16 "
         "(90th percentile $12) and the median entry-time gap 40 s. The 15 unmatched positions are small losers taken on one feed only (volume filter) "
         "plus four 2026 entries the engine took on a neighbouring bar.\n")

L.append("## 4. Cost grid: what each assumption is worth (engine, 1 Jan 2023 - 26 Sep 2026, $200, linear lots, MaxLot 0.10)\n")
L.append("| Protection | Costs | End balance | Positions | Swap paid | Max balance DD | Max equity DD | 2023 | 2024 | 2025 | 2026 |\n|---|---|---|---|---|---|---|---|---|---|---|")
for g in grid:
    L.append(f"| {g['prot']} | {g['cost']} | {money(g['end'])} | {g['pos']} | {money(g['swap'])} | {money(g['dd_b'])} | {money(g['dd_e'])} | "
             f"{money(g['y'].get(2023, 0))} | {money(g['y'].get(2024, 0))} | {money(g['y'].get(2025, 0))} | {money(g['y'].get(2026, 0))} |")
L.append("\nReading: swap is worth about $2,000 (trailing) to $3,200 (Chandelier) of end balance; a 25-point spread with no slippage adds another "
         "$500-1,250. The other machine's $9,066 sits between the swap-0 and the low-cost rows, as expected for a symbol with no swap and a tighter "
         "spread on real ticks. At 0.01 lot (2023-2025) trailing and Chandelier earn about the same ($824 vs $752 with XM costs); the 2023-2026 "
         "difference between them is which one happened to reach the bigger lot first in 2026.\n")

L.append("## 5. EA bug found in your log and fixed (v2.11)\n")
L.append("Your 13:47 run shows three partial-close requests answered `[Market closed]` by the XM server: 2 Mar 2026 01:00:03 (profit-side, 0.01 of "
         "0.02 lot), 11 May 2026 01:00:00 (loss-side, 0.01 of 0.02) and 27 Jul 2026 01:00:02 (loss-side, 0.02 of 0.04). GOLD quotes start at 01:00 "
         "on Monday but the server accepts market orders only a few minutes later (your log shows fills from 01:03). v2.10 set the done flag before "
         "sending, so the partial was never retried; the break-even modify at 01:00:28 failed the same way but has no flag and went through later.\n")
L.append("Cost in that run: about $50 on 2 Mar (the 0.01 lot that should have been closed at +$50 was later closed at break-even), $8 on 11 May and "
         "$22 on 27 Jul, plus the compounding of those $80 through the lot steps. The engine allowed those fills, so this is one of the reasons it "
         "is above your tester on every window.\n")
L.append("Fix in `SimpleSMA18Bot_H4_Final.mq5` v2.11 (compiled 0 errors, copied to `MQL5\\Experts\\4HR\\` and to this folder): `DoPartialClose` "
         "returns done / skipped / retry; a rejected request sets `NextPartialRetry = TimeCurrent() + PartialRetrySeconds` (new input, default 60 s) "
         "and the flag is set only after the server accepts; the reject reason and retcode are printed. Re-run the tester with the new build before "
         "comparing again.\n")

L.append("## 6. Why the numbers differ: root causes ranked\n")
L.append("1. **Swap.** The other machine's symbol charges none; GOLD on your server and the engine charge about -$87 per lot-night long. Worth "
         "$2,000-3,200 of the 2023-2026 end balance through the lot steps. This is the whole story of $9,066 versus $4,800-5,400.")
L.append("2. **Spread and slippage.** GOLD.i# on real ticks fills tighter than the engine's XM spread model plus 10 points; worth another $500-1,250.")
L.append("3. **Data feed.** Three feeds (XM server 2, XM server 7, Dukascopy) agree on about 85-90% of the signal bars; the rest are volume-filter "
         "decisions on tick volume that differs by broker, moving 3-5 entries a year to a neighbouring bar and adding or removing 3-4 small trades a "
         "year (for example the 14 Sep 2026 short exists on both XM servers but not on Dukascopy).")
L.append("4. **Protection mode.** Trailing versus Chandelier is a wash at 0.01 lot; whichever reaches the larger lot first in 2026 ends higher. Under "
         "XM costs the engine has trailing ahead ($5,347 vs $4,361), swap-free it has Chandelier ahead ($7,524 vs $7,316). Not a robust difference.")
L.append("5. **The Monday partial-close bug** (about $80 plus compounding per 2026 run): fixed in v2.11.")
L.append("6. **Window labels.** The $1,598 run is 1 Jan - 26 Sep 2026, not last year; the $1,892 figure is the earlier doubling build on the Last-year preset.\n")

L.append("## 7. Which is effective, and what to do\n")
L.append("- The other machine's report is a correct simulation of a **swap-free** account on GOLD.i# with real-tick fills. It is only achievable live "
         "on such an account; on a standard GOLD account with swap, expect the $4,400-5,400 class of result for 2023-2026 from $200, exactly as your "
         "own tester and the engine show.")
L.append("- Keep TRAILING as the default on a swap-charging account (it ends higher in the engine under XM costs); on a swap-free account either mode "
         "is fine and Chandelier was marginally better. Neither mode changes the 0.01-lot expectancy.")
L.append("- If your live account is swap-free, use the engine's swap = 0 rows (section 4) as the expectation, not the $9,066 report: that report also "
         "enjoyed the tighter GOLD.i# spread and reached 0.10 lot in March 2026 with a 31% equity drawdown.")
L.append("- Use v2.11 for every further tester run. Compare like with like: same window, same MaxLot (0.10 here), same protection, and read the "
         "deposit and swap columns of the report before comparing balances.\n")

L.append("## 8. Files\n")
L.append("- `Report7_tester_positions_2026.csv`: your 13:47 run paired into 41 positions (from the agent log).")
L.append("- `Report7_other_machine_positions_2023-2026.csv`: the other machine's 391 deals paired into 180 positions.")
L.append("- `Report7_engine_trades_2023-2026_chandelier.csv`, `..._trailing.csv`: engine deals for the same window with XM costs.")
L.append("- `SimpleSMA18Bot_H4_Final.mq5 / .ex5`: v2.11.")
L.append("- Logs read: `Terminal\\...\\Tester\\logs\\20260927.log` (journal) and `Tester\\...\\Agent-127.0.0.1-3001\\logs\\20260927.log` (agent, "
         "UTF-16; only the last run survives because the agent log is cleaned at each start).")
open(os.path.join(REP, "Report7_Tester_Verification.md"), "w", encoding="utf-8").write("\n".join(L))
for src, dst in [("tester_positions_2026.csv", "Report7_tester_positions_2026.csv"),
                 ("other_tester_positions_2023.csv", "Report7_other_machine_positions_2023-2026.csv"),
                 ("engine_trades_2023_chandelier.csv", "Report7_engine_trades_2023-2026_chandelier.csv"),
                 ("engine_trades_2023_trailing.csv", "Report7_engine_trades_2023-2026_trailing.csv")]:
    shutil.copy(os.path.join(S, src), os.path.join(REP, dst))
print("report written", len("\n".join(L)), "chars")
print(pd.DataFrame([{k: (round(v, 2) if isinstance(v, float) else v) for k, v in g.items() if k != "y"} for g in grid]).to_string())
