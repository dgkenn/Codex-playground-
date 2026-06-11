#!/usr/bin/env bash
# ALWAYS-ON local shadow collector supervisor: no deadline, restarts kalshi_collect.py forever.
# (overnight_run.sh's collector loop dies with its HOURS deadline; this one only dies with the box.)
# The DURABLE always-on layer is GitHub Actions (collect.yml: self-chaining + cron backstop) --
# this local loop is the second, independent leg. Run: nohup ./collect_forever.sh & or via the
# session background runner. Idempotent-ish: refuses to start if another instance holds the lock.
set -u
cd "$(dirname "$0")"
OUT=overnight_data; mkdir -p "$OUT"
LOCK="$OUT/.collect_forever.lock"
exec 9>"$LOCK"
flock -n 9 || { echo "another collect_forever is running (lock $LOCK)"; exit 0; }
echo "$(date -u +%FT%TZ) collect_forever started (pid $$)" >> "$OUT/collect.log"
# cross-venue: Polymarket 5-min BTC up/down (slug-based discovery; continuous), parallel + restarting
( while true; do
    python -u pmkt_collect.py 3000 "$OUT" "pm$(date +%H%M)" >> "$OUT/pmkt.log" 2>&1
    sleep 3
  done ) &
while true; do
  python -u kalshi_collect.py 3000 "$OUT" "cf$(date +%H%M)" >> "$OUT/collect.log" 2>&1
  echo "$(date -u +%FT%TZ) collector exited rc=$?; restarting in 3s" >> "$OUT/collect.log"
  sleep 3
done
