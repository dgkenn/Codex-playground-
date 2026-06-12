#!/usr/bin/env bash
# Supervised live loop -- THE one sanctioned way to run the local trader.
# CONTROL L0: single-instance flock. Two loops => two traders on one account => inventory
# breach (2026-06-12 |net|=-2 incident). The trader has its own lock (L1) and a venue-side
# foreign-order halt (L2); this is the outermost layer.
exec 9>/tmp/.live_loop.lock
flock -n 9 || { echo "another live_loop already running; exiting"; exit 0; }
cd "$(dirname "$0")"
set -a; . "$HOME/.kalshi/env"; set +a
export I_UNDERSTAND_REAL_MONEY=yes
while true; do
  sw=$(tr -d '[:space:]' < LIVE_SWITCH 2>/dev/null || echo off)
  if [ "$sw" != "on" ] || [ -f .kalshi_killed_btc15m ]; then
    echo "$(date -u +%H:%MZ) switch=$sw or sentinel -> idle"; sleep 20; continue
  fi
  if python kalshi_preflight.py --asset btc | tee /tmp/pf_loop.txt | grep -q "VERDICT: GO"; then
    python -u kalshi_trader.py --asset btc --live --size-mode flat \
      --post 1 --max-notional 5 --loss-limit 6 --max-rungs 1 --duration 3300 \
      --remote-switch-s 20 --qtime-mp-margin 0.006
  else
    echo "$(date -u +%H:%MZ) preflight NO-GO; retry in 60s"; sleep 60
  fi
  sleep 5
done
