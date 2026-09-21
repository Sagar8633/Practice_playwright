#!/usr/bin/env bash
# Compile the ICEburg EA with MetaEditor's command-line compiler and print only
# what matters.
#
# Two traps this wrapper exists to absorb:
#   1. MetaEditor returns exit code 1 even on a CLEAN compile, so the exit status
#      is useless - the LOG is the source of truth.
#   2. The log is written as UTF-16LE with a BOM, so cat/grep produce garbage
#      until it is converted.
set -u

ME="/c/Program Files/MetaTrader 5/MetaEditor64.exe"
DIR="D:\\Practice_Playwright\\xau_iceberg\\mt5"
SRC="${1:-ICEburg.mq5}"
LOG_WIN="$DIR\\compile.log"
LOG_NIX="/d/Practice_Playwright/xau_iceberg/mt5/compile.log"

rm -f "$LOG_NIX"
"$ME" /compile:"$DIR\\$SRC" /log:"$LOG_WIN" >/dev/null 2>&1

# give the editor a moment to flush the log
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$LOG_NIX" ] && break; sleep 1; done
if [ ! -s "$LOG_NIX" ]; then echo "no log produced - is the path right?"; exit 2; fi

TXT=$(iconv -f UTF-16LE -t UTF-8 "$LOG_NIX" 2>/dev/null || cat "$LOG_NIX")

echo "$TXT" | grep -E ": (error|warning) [0-9]+:" | sed 's/^[[:space:]]*//' | head -60
echo "----"
echo "$TXT" | grep -E "^Result:" | tail -1
