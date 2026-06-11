#!/usr/bin/env bash
# ALWAYS-ON supervisor for a PERSISTENT host (an always-free VM like Oracle Cloud us-east).
# This is the local twin of .github/workflows/live.yml: it honors the SAME LIVE_SWITCH file, runs
# the fully-wired bot when on, idles when off, restarts on crash, keeps the collector up, and pulls
# the latest branch each cycle so strategy changes propagate automatically. Single-instance.
#
#   start once:  nohup ./live_supervisor.sh >/dev/null 2>&1 &
#   control:     ./live_switch.sh on | off    (or edit the LIVE_SWITCH file)
#
# Needs creds in the environment (or /root/.kalshi/env): KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY_PATH.
set -u
cd "$(dirname "$0")"
ASSET="${ASSET:-btc}"
[ -f /root/.kalshi/env ] && . /root/.kalshi/env
mkdir -p overnight_data
exec 9> overnight_data/.live_supervisor.lock
flock -n 9 || { echo "live_supervisor already running"; exit 0; }
echo "$(date -u +%FT%TZ) live_supervisor up (pid $$)" >> overnight_data/trader.log

# keep the risk-free collector alive independently of the switch
pgrep -f "collect_forever.sh" >/dev/null 2>&1 || nohup ./collect_forever.sh >/dev/null 2>&1 &

BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
while true; do
  git pull -q origin "$BR" 2>/dev/null || true          # pick up strategy/config changes
  sw=$(tr -d '[:space:]' < LIVE_SWITCH 2>/dev/null || echo off)
  if [ "$sw" = "on" ] && [ ! -f ".kalshi_killed_${ASSET}15m" ]; then
    I_UNDERSTAND_REAL_MONEY=yes python -u kalshi_trader.py --asset "$ASSET" --live \
      --size-mode kelly --post 1 --max-notional 5 --loss-limit 6 --max-rungs 2 \
      --duration 3300 >> overnight_data/trader.log 2>&1 || true
  else
    sleep 30                                            # switch off / killed -> idle, re-check
  fi
  sleep 3
done
