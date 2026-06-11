#!/usr/bin/env bash
# Overnight DATA-GATHERING run: shadow collector (no money, all variants) + live Kelly bot
# (ruin-proof caps). Both auto-restart across windows/crashes until DEADLINE. The live loop STOPS
# permanently if the sticky loss-limit sentinel appears (a -$LOSS kill must not silently re-arm).
set -u
cd "$(dirname "$0")"
HOURS="${1:-10}"
DEADLINE=$(( $(date +%s) + HOURS*3600 ))
OUT=overnight_data; mkdir -p "$OUT"
export KALSHI_API_KEY_ID="${KALSHI_API_KEY_ID:?set in env}"
export KALSHI_PRIVATE_KEY_PATH="${KALSHI_PRIVATE_KEY_PATH:?set in env}"

# --- shadow collector loop (risk-free; the primary data engine) ---
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    python -u kalshi_collect.py 3000 "$OUT" "ov$(date +%H%M)" >> "$OUT/collect.log" 2>&1
    sleep 3
  done ) &
echo "shadow collector loop started (pid $!)"

# --- live Kelly bot loop (real money, ruin-capped) ---
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if [ -f .kalshi_killed_btc15m ]; then
      echo "$(date -u +%H:%MZ) LOSS-LIMIT SENTINEL present -> live trading halted (manual reset to resume)" >> "$OUT/trader.log"
      break
    fi
    I_UNDERSTAND_REAL_MONEY=yes python -u kalshi_trader.py --asset btc --live \
      --size-mode flat --post 1 --max-notional 5 --loss-limit 6 --max-rungs 1 \
      --duration 3300 >> "$OUT/trader.log" 2>&1
    sleep 3
  done
  echo "$(date -u +%H:%MZ) live loop ended" >> "$OUT/trader.log" ) &
echo "live Kelly bot loop started (pid $!)"
echo "overnight run armed for ${HOURS}h; data -> $OUT/  (caps: post 1, max-notional \$5, loss-limit \$3 sticky)"
