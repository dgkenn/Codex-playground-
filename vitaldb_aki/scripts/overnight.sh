#!/bin/bash
# overnight.sh -- self-healing orchestrator so the VitalDB study completes
# unattended overnight despite container restarts and network hangs.
#
# Idempotent + single-instance (lock). Safe to invoke repeatedly (e.g. from a
# cron every 15 min): if already running it exits; if the prior run died it
# takes over and resumes (run_all + per-module extraction are both resumable).
#
# Phase 1 (guaranteed): run_all.py -> 8-module matrix -> harness -> multitask ->
#   hypotension -> consolidate, self-healing run_all on death OR cpu-stall hang.
# Phase 2: phenotype discovery, then refresh RESULTS.md.
set -u
cd /home/user/Codex-playground-/ || exit 1
LOG=vitaldb_aki/cache/overnight.log
LOCK=vitaldb_aki/cache/overnight.lock
mkdir -p vitaldb_aki/cache
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

# single instance
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
say "watchdog start pid=$$"

phase1_done(){
  local cons hc
  cons=$(python3 -c "import json;print(json.load(open('vitaldb_aki/cache/run_all_status.json')).get('consolidate'))" 2>/dev/null)
  hc=$(ls vitaldb_aki/cache/incremental_value_*.json 2>/dev/null | wc -l)
  [ "$cons" = "done" ] && [ "$hc" -ge 16 ]
}

run_all_pid(){ pgrep -f "python3 vitaldb_aki/run_all.py" | head -1; }

# ---- Phase 1: drive run_all to completion, self-healing ----
while ! phase1_done; do
  pid=$(run_all_pid)
  if [ -z "$pid" ]; then
    rm -f vitaldb_aki/cache/run_all.lock
    nohup python3 vitaldb_aki/run_all.py --workers 12 >> vitaldb_aki/cache/run_all.log 2>&1 &
    say "launched run_all (was not running)"
    sleep 45
  else
    # progress-aware hang detector: only kill if the process burns no CPU AND
    # writes nothing over the window. Network-bound extraction blocks on socket
    # I/O (cputime barely advances) while still flushing each finished case to a
    # _featcache/*.partial -- so the line-count of run_all.log + the .partial
    # files is the real liveness signal. cputime-only (the old check) false-killed
    # healthy slow downloads; the 150s/track download deadline already bounds true
    # dead sockets, so a hang now means BOTH no CPU and no new rows.
    prog1=$(cat vitaldb_aki/cache/run_all.log vitaldb_aki/cache/_featcache/*.partial 2>/dev/null | wc -l)
    t1=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    sleep 240
    prog2=$(cat vitaldb_aki/cache/run_all.log vitaldb_aki/cache/_featcache/*.partial 2>/dev/null | wc -l)
    t2=$(ps -o cputime= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$t1" ] && [ "$t1" = "$t2" ] && [ "$prog1" = "$prog2" ]; then
      say "run_all HUNG (no cpu + no log/partial progress 240s) -> kill+restart"
      kill -9 "$pid" 2>/dev/null
      rm -f vitaldb_aki/cache/run_all.lock
    fi
  fi
done
say "Phase 1 complete (matrix+harness+multitask+hypotension)"

# ---- Phase 2: phenotype discovery, then refresh the consolidated report ----
if [ ! -f vitaldb_aki/cache/phenotypes_results.json ]; then
  python3 -c "import sys;sys.path.insert(0,'.');from common.config import load_yaml;from vitaldb_aki.analysis.phenotypes import run_phenotype_analysis as r;r(load_yaml('vitaldb_aki/config.yaml'))" >> "$LOG" 2>&1 \
    && say "phenotype discovery done" || say "phenotype discovery FAILED (non-fatal)"
fi
python3 vitaldb_aki/run_all.py --force consolidate >> vitaldb_aki/cache/run_all.log 2>&1 && say "RESULTS.md refreshed (incl phenotypes)"

# ---- commit results docs so they survive a container reclaim ----
git add vitaldb_aki/docs/RESULTS.md vitaldb_aki/docs/PHENOTYPES.md vitaldb_aki/docs/PER_ORGAN_RESULTS.md 2>/dev/null
git commit -q -m "vitaldb_aki: overnight run results (auto-committed by watchdog)" 2>/dev/null \
  && git push origin claude/heedb-eeg-phenotype-discovery-2mnwzx >/dev/null 2>&1 && say "results committed+pushed"
say "OVERNIGHT WRAP-UP COMPLETE"
