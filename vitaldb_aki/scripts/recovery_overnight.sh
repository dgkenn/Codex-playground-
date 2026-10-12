#!/bin/bash
# recovery_overnight.sh -- self-healing driver for the raw-MAP recovery-velocity
# extraction (analysis/recovery_velocity_extract.py: streams Solar8000/ART_MBP for
# the hypotensive cohort, computes post-nadir recovery slope/tau, purges each track).
# Resumable (skips caseids already in recovery_velocity.csv), single-instance,
# progress-aware. Own lock so it coexists with discovery/aline/map watchdogs. On
# EXTRACT completion it runs the screen once to produce docs/RECOVERY_VELOCITY.md.
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/recovery.log
LOCK=vitaldb_aki/cache/recovery.lock
CSV=vitaldb_aki/cache/recovery_velocity.csv
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "recovery watchdog start pid=$$"

extract_done(){ [ -f vitaldb_aki/cache/_recovery_velocity_done.json ]; }
screen_done(){ [ -f vitaldb_aki/cache/_recovery_velocity_screen_done.json ]; }
run_pid(){ pgrep -f "python3 vitaldb_aki/analysis/recovery_velocity_extract.py" | head -1; }

# Stage 1: extraction (the long, download-bound pole), with hang detection.
while ! extract_done; do
  pid=$(run_pid)
  if [ -z "$pid" ]; then
    nohup python3 vitaldb_aki/analysis/recovery_velocity_extract.py >> "$LOG" 2>&1 &
    say "launched recovery_velocity_extract (was not running)"
    sleep 45
  else
    p1=$(cat "$LOG" "$CSV" 2>/dev/null | wc -l)
    t1=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    sleep 240
    p2=$(cat "$LOG" "$CSV" 2>/dev/null | wc -l)
    t2=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$t1" ] && [ "$t1" = "$t2" ] && [ "$p1" = "$p2" ]; then
      say "recovery_velocity_extract HUNG (no cpu + no progress 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
    fi
  fi
done
say "RECOVERY EXTRACT COMPLETE (recovery_velocity.csv ready)"

# Stage 2: the screen (fast, CPU-only) -- run once.
if ! screen_done; then
  say "running recovery_velocity_screen"
  nohup python3 -m vitaldb_aki.analysis.recovery_velocity_screen >> "$LOG" 2>&1
  say "RECOVERY SCREEN COMPLETE (docs/RECOVERY_VELOCITY.md ready)"
fi
