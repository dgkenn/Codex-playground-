#!/bin/bash
# map_extract_overnight.sh -- self-healing driver for the MAP multi-threshold
# burden recompute (50..80). Resumable (the extractor skips caseids already in
# map_thresholds.csv), single-instance, progress-aware. Separate lock so it
# coexists with discovery_overnight.sh.
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/map_extract.log
LOCK=vitaldb_aki/cache/map_extract.lock
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "map-extract watchdog start pid=$$"

done_marker(){ [ -f vitaldb_aki/cache/_map_thresholds_done.json ]; }
run_pid(){ pgrep -f "python3 vitaldb_aki/analysis/map_threshold_extract.py" | head -1; }

while ! done_marker; do
  pid=$(run_pid)
  if [ -z "$pid" ]; then
    nohup python3 vitaldb_aki/analysis/map_threshold_extract.py >> "$LOG" 2>&1 &
    say "launched map_threshold_extract (was not running)"
    sleep 45
  else
    p1=$(cat "$LOG" vitaldb_aki/cache/map_thresholds.csv 2>/dev/null | wc -l)
    t1=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    sleep 240
    p2=$(cat "$LOG" vitaldb_aki/cache/map_thresholds.csv 2>/dev/null | wc -l)
    t2=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$t1" ] && [ "$t1" = "$t2" ] && [ "$p1" = "$p2" ]; then
      say "map_threshold_extract HUNG (no cpu + no progress 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
    fi
  fi
done
say "MAP THRESHOLDS COMPLETE (map_thresholds.csv ready)"
