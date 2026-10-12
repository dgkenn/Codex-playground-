#!/usr/bin/env bash
# Bound the cost of a container rollback: commit and push in-flight extraction output on a timer.
#
# WHY THIS EXISTS. This container has now rolled the working tree AND `.git` back to the SAME commit
# (93f1723) twice in one session, killing every background job and deleting every uncommitted file.
# Catalogue rule 38 says the remote is the only durable store here and that pushing after every artifact
# boundary is what makes it survivable. For a two-hour extraction, "every artifact boundary" is too
# coarse -- the second rollback cost ~40 minutes of fetching that had already completed.
#
# This loop narrows the exposure to one interval. It is deliberately the dumbest thing that works:
#   * it stages ONLY the paths it is given, so it can never sweep up a half-written source file or a
#     document mid-edit;
#   * it commits only when `git diff --cached --quiet` says something actually changed, so a stalled
#     extraction does not fill the history with empty commits;
#   * it pulls with --rebase before pushing, so a commit made by hand in the same window is not clobbered;
#   * it exits on its own when no matching extractor process is left, so it cannot outlive the job.
#
# Usage:  scripts/checkpoint_loop.sh <seconds> <process-pattern> <path> [path...]
#   scripts/checkpoint_loop.sh 300 vitaldb_ventilation_probe bsde/results/vitaldb_vent_probe.s*.csv
set -u

INTERVAL="${1:?interval in seconds}"; shift
PATTERN="${1:?process pattern to watch}"; shift
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "[checkpoint] every ${INTERVAL}s on branch ${BRANCH} while '${PATTERN}' is alive; paths: $*"

while true; do
    sleep "$INTERVAL"

    git add -- "$@" 2>/dev/null
    if git diff --cached --quiet 2>/dev/null; then
        alive=$(ps -eo args | grep -c "[${PATTERN:0:1}]${PATTERN:1}")
        [ "$alive" -eq 0 ] && { echo "[checkpoint] no '${PATTERN}' process left and nothing staged; exiting"; break; }
        continue
    fi

    n=$(cat "$@" 2>/dev/null | wc -l)
    git commit -q -m "Checkpoint ${PATTERN} at ${n} rows (automatic, bounds rollback loss)" \
        -m "Committed by scripts/checkpoint_loop.sh. The container has rolled this tree back to an old
commit twice today; the remote is the only durable store (catalogue rule 38)." 2>/dev/null

    git pull --rebase -q origin "$BRANCH" 2>/dev/null
    if git push -q origin "$BRANCH" 2>/dev/null; then
        echo "[checkpoint] pushed at ${n} rows"
    else
        echo "[checkpoint] push FAILED at ${n} rows; will retry next interval"
    fi

    alive=$(ps -eo args | grep -c "[${PATTERN:0:1}]${PATTERN:1}")
    [ "$alive" -eq 0 ] && { echo "[checkpoint] '${PATTERN}' finished; final state pushed; exiting"; break; }
done
