@echo off
rem Gold GEX view: download the GLD option chain, open the page, then run the agent.
rem The agent refreshes options data every 5 minutes and accepts TWK 15m setup orders only.
rem Close this window to stop both; the page keeps showing the last download.
cd /d "%~dp0"
node gex_fetch.cjs
start "" "gold_gex.html"
node gex_agent.cjs
