#!/bin/bash
# discovery_overnight.sh -- self-healing driver for the EXPLORATORY discovery
# track (enriched matrix -> per-family screen -> enriched phenotypes). Separate
# from overnight.sh so it never touches the frozen confirmatory pipeline.
#
# Single-instance (own lock). Resumable: discovery_run.py reuses per-module
# _featcache, so an externally-killed process just resumes. Same progress-aware
# hang detector as overnight.sh (the container reaps processes ~every 15-30min).
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/discovery.log
LOCK=vitaldb_aki/cache/discovery.lock
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "discovery watchdog start pid=$$"

# The long pole is the enriched-matrix extraction. Drive discovery_run.py until
# that marker exists; the per-family screen + enriched clustering run afterward.
done_marker(){ [ -f vitaldb_aki/cache/_discovery_matrix_done.json ]; }
run_pid(){ pgrep -f "python3 vitaldb_aki/analysis/discovery_run.py" | head -1; }

while ! done_marker; do
  pid=$(run_pid)
  if [ -z "$pid" ]; then
    nohup python3 vitaldb_aki/analysis/discovery_run.py >> "$LOG" 2>&1 &
    say "launched discovery_run (was not running)"
    sleep 45
  else
    # progress-aware hang detector: only kill if no CPU AND no new log/partial rows.
    prog1=$(cat "$LOG" vitaldb_aki/cache/_featcache/*.partial 2>/dev/null | wc -l)
    t1=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    sleep 240
    prog2=$(cat "$LOG" vitaldb_aki/cache/_featcache/*.partial 2>/dev/null | wc -l)
    t2=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$t1" ] && [ "$t1" = "$t2" ] && [ "$prog1" = "$prog2" ]; then
      say "discovery_run HUNG (no cpu + no progress 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
    fi
  fi
done
say "ENRICHED MATRIX COMPLETE (feature_matrix_enriched.csv ready for the screen stage)"
