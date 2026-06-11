#!/usr/bin/env bash
# Persist live telemetry to the durable `live-state` branch, date-partitioned, so the clean/long/rich
# live dataset survives the ephemeral container (the gap that made the 24h failure-audit hard).
# Append-only files: per-fill fees+features, markout curves, per-window audit (outcome+box/unpaired),
# live metrics. Called on a loop by the supervisor (~10 min). Safe to run anywhere with the repo+remote.
set -u
cd "$(dirname "$0")"
ASSET="${ASSET:-btc}"
FILES="kalshi_fees_${ASSET}15m.jsonl kalshi_markout.jsonl window_audit_${ASSET}15m.jsonl live_metrics_kalshi_${ASSET}15m.jsonl"
have=0; for f in $FILES; do [ -f "$f" ] && have=1; done
[ "$have" = 1 ] || exit 0
day=$(date -u +%Y-%m-%d)
git config user.name  "live-bot" 2>/dev/null || true
git config user.email "live-bot@users.noreply.github.com" 2>/dev/null || true
rm -rf /tmp/lwt 2>/dev/null
if git fetch -q --depth=1 origin live-state 2>/dev/null; then
  git worktree add -q --detach /tmp/lwt origin/live-state 2>/dev/null && ( cd /tmp/lwt && git checkout -q -B live-state )
else
  git worktree add -q --detach /tmp/lwt HEAD 2>/dev/null && ( cd /tmp/lwt && git checkout -q --orphan live-state \
    && git rm -rq --cached . 2>/dev/null; find /tmp/lwt -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + )
fi
[ -d /tmp/lwt ] || exit 0
mkdir -p "/tmp/lwt/live_state/$day"
for f in $FILES; do [ -f "$f" ] && cp -f "$f" "/tmp/lwt/live_state/$day/"; done
cd /tmp/lwt && git add live_state
if git commit -q -m "live telemetry $day $(date -u +%H:%MZ)" 2>/dev/null; then
  for i in 1 2 3; do
    git push -q origin HEAD:live-state && break
    git fetch -q --depth=1 origin live-state && git rebase -q origin/live-state 2>/dev/null || true
    sleep 2
  done
fi
cd - >/dev/null 2>&1 || true
git worktree remove -f /tmp/lwt 2>/dev/null || true
