@echo off
rem Gold GEX view: download the GLD option chain, open the page, then run the agent.
rem The agent refreshes the options data every 5 minutes and passes signals to MetaTrader 5 (when "MT5 on").
rem Close this window to stop both; the page keeps showing the last download.
cd /d "%~dp0"
node gex_fetch.cjs
start "" "gold_gex.html"
node gex_agent.cjs
