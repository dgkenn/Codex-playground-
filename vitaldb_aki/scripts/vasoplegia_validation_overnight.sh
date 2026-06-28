#!/bin/bash
# vasoplegia_validation_overnight.sh -- self-healing driver for the WAVEFORM-vs-
# MEASURED-SVRI validation pipeline (vitaldb_aki/analysis/
# vasoplegia_validation_extract.py EXTRACT, then vasoplegia_validation_screen).
# Resumable (EXTRACT skips caseids already in vasoplegia_validation.csv; SCREEN is
# idempotent), single-instance, progress-aware. Own lock so it coexists with the
# other overnight drivers (aline_overnight.sh, discovery_overnight.sh, ...).
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/vaso_val.log
LOCK=vitaldb_aki/cache/vaso_val.lock
SAMPLE=vitaldb_aki/cache/vasoplegia_validation.csv
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

# Single instance: bail if a live watchdog already holds the lock.
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "vaso_val watchdog start pid=$$"

# DONE when the EXTRACT stage has written its final marker.
done_marker(){ [ -f vitaldb_aki/cache/_vasoplegia_validation_done.json ]; }
run_pid(){ pgrep -f "python3 vitaldb_aki/analysis/vasoplegia_validation_extract.py" | head -1; }

while ! done_marker; do
  pid=$(run_pid)
  if [ -z "$pid" ]; then
    nohup python3 vitaldb_aki/analysis/vasoplegia_validation_extract.py >> "$LOG" 2>&1 &
    say "launched vasoplegia_validation_extract (was not running)"
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
      say "vasoplegia_validation_extract HUNG (no cpu + no vaso_val.log/vasoplegia_validation.csv growth 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
    fi
  fi
done
say "VASOPLEGIA VALIDATION EXTRACT COMPLETE (_vasoplegia_validation_done.json present)"

# EXTRACT done -> run the SCREEN once (idempotent; writes results JSON + MD).
say "running vasoplegia_validation_screen"
nohup python3 -m vitaldb_aki.analysis.vasoplegia_validation_screen >> "$LOG" 2>&1
say "vasoplegia_validation_screen finished"
