#!/bin/bash
# aline_overnight.sh -- self-healing driver for the A-line waveform FEASIBILITY
# pipeline (vitaldb_aki/analysis/aline_feasibility.py: EXTRACT then SCREEN).
# Resumable (EXTRACT skips caseids already in aline_sample.csv; SCREEN is
# idempotent), single-instance, progress-aware. Own lock so it coexists with the
# other overnight drivers (map_extract_overnight.sh, discovery_overnight.sh).
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/aline.log
LOCK=vitaldb_aki/cache/aline.lock
SAMPLE=vitaldb_aki/cache/aline_sample.csv
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

# Single instance: bail if a live watchdog already holds the lock.
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "aline watchdog start pid=$$"

# DONE when the SCREEN stage has written its final marker.
done_marker(){ [ -f vitaldb_aki/cache/_aline_done.json ]; }
run_pid(){ pgrep -f "python3 vitaldb_aki/analysis/aline_feasibility.py" | head -1; }

while ! done_marker; do
  pid=$(run_pid)
  if [ -z "$pid" ]; then
    nohup python3 vitaldb_aki/analysis/aline_feasibility.py >> "$LOG" 2>&1 &
    say "launched aline_feasibility (was not running)"
    sleep 45
  else
    # Progress-aware hang detector: CPU time AND (log + sample CSV) line growth
    # must both stall over 240s before we conclude the job is hung.
    p1=$(cat "$LOG" "$SAMPLE" 2>/dev/null | wc -l)
    t1=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    sleep 240
    p2=$(cat "$LOG" "$SAMPLE" 2>/dev/null | wc -l)
    t2=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$t1" ] && [ "$t1" = "$t2" ] && [ "$p1" = "$p2" ]; then
      say "aline_feasibility HUNG (no cpu + no aline.log/aline_sample.csv growth 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
    fi
  fi
done
say "ALINE FEASIBILITY COMPLETE (_aline_done.json present)"
