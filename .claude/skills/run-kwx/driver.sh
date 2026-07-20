#!/usr/bin/env bash
# driver.sh -- operator smoke/驱动 harness for the K-WX Kalshi weather bot.
# Every subcommand is READ-ONLY / paper-safe: no orders, no state mutation, no log writes
# that matter (see the near-miss pollution gotcha in SKILL.md). Run from the repo root.
#
#   ./.claude/skills/run-kwx/driver.sh smoke     # full health pass (default)
#   ./.claude/skills/run-kwx/driver.sh status    # goal/stage/gate one-pager
#   ./.claude/skills/run-kwx/driver.sh model     # capacity model, full scenario tables
#   ./.claude/skills/run-kwx/driver.sh feed      # which obs cascade the runner would boot + live probe
#   ./.claude/skills/run-kwx/driver.sh digest    # compose the daily digest text (no send)
#   ./.claude/skills/run-kwx/driver.sh trial     # synoptic detection-latency trial evidence so far
#   ./.claude/skills/run-kwx/driver.sh studies   # reproduce all committed study verdicts from their data
set -uo pipefail
cd "$(dirname "$0")/../../.."   # repo root, wherever the skill was invoked from

cmd="${1:-smoke}"
fail=0
run() { echo "== $* =="; "$@" || { echo "^^ FAILED: $*"; fail=1; }; echo; }

case "$cmd" in
  status)
    run python kwx_goal_status.py
    ;;
  model)
    run python wx_path_to_4k.py
    ;;
  feed)
    # kwx_runner prints its feed-cascade provenance line on ANY invocation, then usage.
    echo "== runner feed provenance =="; python kwx_runner.py usage 2>/dev/null | head -1
    echo; echo "== live synoptic probe (needs token; falls back gracefully) =="
    python synoptic_feed.py probe KDEN,KMIA 2>&1 | head -12
    ;;
  digest)
    run python -c "import kwx_daily_digest as D; print(D.compose())"
    ;;
  trial)
    run python wx_synoptic_trial.py --report
    ;;
  studies)
    run python wx_maker_deep_study.py --selftest
    echo "== early-lock study reproduction (header) =="; python wx_earlylock_deep_study.py | head -20; echo
    run python kwx_goal_status.py
    ;;
  smoke)
    run python kwx_selftest.py
    run python kwx_goal_status.py
    echo "== feed provenance =="; python kwx_runner.py usage 2>/dev/null | head -1; echo
    run python wx_maker_deep_study.py --selftest
    echo "== capacity model (tail) =="; python wx_path_to_4k.py | tail -6; echo
    # local-run pollution check: local invocations must never leave rows in the bot-owned logs
    if ! git diff --quiet kwx_near_miss.jsonl 2>/dev/null; then
      echo "WARNING: local run polluted kwx_near_miss.jsonl -- run: git checkout -- kwx_near_miss.jsonl"
      fail=1
    fi
    ;;
  *)
    echo "usage: driver.sh [smoke|status|model|feed|digest|trial|studies]"; exit 2;;
esac
exit $fail
