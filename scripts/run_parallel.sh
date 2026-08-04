#!/usr/bin/env bash
# scripts/run_parallel.sh — launch N shard workers + the resource monitor on one box.
#
# Usage:
#   ./scripts/run_parallel.sh [NUM_WORKERS]
#
# Environment overrides (all optional):
#   NUM_WORKERS  number of parallel shards      (default: 16, or $1)
#   OUT          output directory               (default: artifacts)
#   LIMIT        --limit passed to run_shard.py (default: 0 = full run)
#   AWS_PROFILE  AWS profile for S3 access      (default: physionet)
#   INTERVAL     monitor sampling interval (s)  (default: 30)
#
# Example:
#   AWS_PROFILE=physionet OUT=artifacts ./scripts/run_parallel.sh 16
#
# Resumable: re-running this script is safe — workers skip already-completed
# recording IDs (tracked in $OUT/pass1_done_wKK.txt per shard).

set -u

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_WORKERS=${1:-${NUM_WORKERS:-16}}
OUT=${OUT:-artifacts}
LIMIT=${LIMIT:-0}
AWS_PROFILE=${AWS_PROFILE:-physionet}
INTERVAL=${INTERVAL:-30}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo "============================================================"
echo "  EEG Pass-1 overnight run"
echo "  Workers    : $NUM_WORKERS"
echo "  Output dir : $OUT"
echo "  AWS profile: $AWS_PROFILE"
echo "  Limit      : ${LIMIT} (0 = full run)"
echo "  Monitor    : $OUT/logs/monitor.log"
echo ""
echo "  RESUMABLE — re-running this script is safe."
echo "  Already-completed recordings are skipped automatically."
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Prepare output + log dirs; remove any stale stop sentinel
# ---------------------------------------------------------------------------
mkdir -p "$OUT/logs"
rm -f "$OUT/STOP_MONITOR"

# ---------------------------------------------------------------------------
# Start the monitor in the background
# ---------------------------------------------------------------------------
echo "[launcher] starting monitor (interval=${INTERVAL}s) ..."
python3 "$SCRIPT_DIR/monitor_usage.py" \
    --out "$OUT" \
    --workers "$NUM_WORKERS" \
    --interval "$INTERVAL" \
    >> "$OUT/logs/monitor.log" 2>&1 &
MONITOR_PID=$!
echo "[launcher] monitor PID: $MONITOR_PID  (log: $OUT/logs/monitor.log)"
echo ""

# ---------------------------------------------------------------------------
# Launch all shard workers
# ---------------------------------------------------------------------------
WORKER_PIDS=()

echo "[launcher] launching $NUM_WORKERS workers ..."
for k in $(seq 0 $((NUM_WORKERS - 1))); do
    KK=$(printf "%02d" "$k")
    LOG="$OUT/logs/shard_${KK}.log"
    AWS_PROFILE="$AWS_PROFILE" nohup python3 "$SCRIPT_DIR/run_shard.py" \
        --shard "$k" \
        --num-shards "$NUM_WORKERS" \
        --out "$OUT" \
        --limit "$LIMIT" \
        >> "$LOG" 2>&1 &
    PID=$!
    WORKER_PIDS+=("$PID")
    echo "  shard $KK  PID=$PID  log=$LOG"
done

echo ""
echo "[launcher] all $NUM_WORKERS workers started. Waiting for completion ..."
echo "  To watch progress:  tail -f $OUT/logs/monitor.log"
echo "  To watch a worker:  tail -f $OUT/logs/shard_00.log"
echo ""

# ---------------------------------------------------------------------------
# Wait for all workers
# ---------------------------------------------------------------------------
for PID in "${WORKER_PIDS[@]}"; do
    wait "$PID" || true   # individual failures don't abort the wait
done

echo ""
echo "[launcher] all worker processes have exited."

# ---------------------------------------------------------------------------
# Stop the monitor
# ---------------------------------------------------------------------------
touch "$OUT/STOP_MONITOR"
echo "[launcher] STOP_MONITOR written — monitor will exit on next sample."

# Give the monitor a moment to flush its final CSV row
sleep 2

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
DONE_COUNT=0
TOTAL_ROWS=0
for f in "$OUT"/pass1_done_w*.txt; do
    [ -f "$f" ] || continue
    LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
    DONE_COUNT=$((DONE_COUNT + LINES))
done

# Count embedding rows (jsonl only; parquet skipped in bash for simplicity)
for f in "$OUT"/embeddings/*.jsonl; do
    [ -f "$f" ] || continue
    LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
    TOTAL_ROWS=$((TOTAL_ROWS + LINES))
done

echo ""
echo "============================================================"
echo "  Run complete."
echo "  Completed recording IDs : $DONE_COUNT"
echo "  Embedding rows (jsonl)  : $TOTAL_ROWS"
echo ""
echo "  To inspect:"
echo "    tail -f $OUT/logs/monitor.log"
echo "    tail -f $OUT/logs/shard_00.log"
echo ""
echo "  Next steps:"
echo "    python3 cli.py phase1 --tables $OUT"
echo "============================================================"
