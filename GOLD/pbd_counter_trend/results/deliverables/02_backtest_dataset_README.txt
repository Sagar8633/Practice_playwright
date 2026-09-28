Backtest dataset
================
M1 bid bars with Dukascopy volume: Momentum_Tracker_Indicator/backtest/data/duka_chunks/bid_YYYY-MM.csv (UTC ms)
M1 cache: GOLD/pbd_counter_trend/data/m1.pkl (pandas)
M15 bars with XM spread, tick volume, ATR, sessions, news proxy, weekly VA (three volume sources + developing):
  GOLD/pbd_counter_trend/data/m15_va.pkl
Weekly profiles: GOLD/pbd_counter_trend/data/weekly_profile_{duka,tick,tpo}.csv
XM M15 source with spread column: Momentum_Tracker_Indicator/backtest/data/xm_GOLD_M15.csv.gz (server time = Europe/Athens)
Missing month: July 2024 (Dukascopy rate-limited every attempt).
