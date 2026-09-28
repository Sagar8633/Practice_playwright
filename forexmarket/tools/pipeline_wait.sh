#!/bin/bash
# As each instrument finishes downloading, prepare its data and run its baseline grid.
cd /d/Practice_Playwright/forexmarket
LOG=data/duka/fetch_all5.log
for i in eurusd gbpusd usdjpy audusd usdcad usdchf nzdusd xagusd btcusd lightcmdusd; do
  until grep -q "^$i DONE" "$LOG" 2>/dev/null; do sleep 60; done
  echo "=== $i data complete $(date)"; 
  python tools/prep_data.py $i 2>&1 | grep -v Deprecation
  python backtests/run_baseline.py $i 2>&1 | grep -v Deprecation | grep -E "\|B |D1 2015|written"
  echo "=== $i baseline done $(date)"
done
python tools/make_data_audit.py
echo PIPELINE_DONE
