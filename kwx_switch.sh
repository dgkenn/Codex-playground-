#!/usr/bin/env bash
# The light switch for the LIVE weather bot (the $10 canary). ./kwx_switch.sh on | off | status
# Flips KWX_SWITCH (one word: on|off) and pushes it. The kwx-live.yml GitHub Actions workflow reads it
# every run, so toggling this file is the ONLY thing needed to start/stop live weather trading.
# A circuit-breaker/kill (.kwx_halt) is independent and blocks orders regardless.
set -u
cd "$(dirname "$0")"
BR="${BRANCH:-claude/coding-bot-ab-test-results-ffmhxw}"
case "${1:-status}" in
  on|ON)   echo on  > KWX_SWITCH; rm -f .kwx_halt; msg="KWX live switch -> ON (\$10 canary)";;
  off|OFF) echo off > KWX_SWITCH;                  msg="KWX live switch -> OFF";;
  status)  echo "KWX_SWITCH = $(tr -d '[:space:]' < KWX_SWITCH 2>/dev/null || echo off)"; exit 0;;
  *) echo "usage: kwx_switch.sh on|off|status"; exit 1;;
esac
git add KWX_SWITCH .kwx_halt 2>/dev/null
git commit -q -m "$msg" && git push origin "HEAD:$BR" 2>&1 | tail -1
echo "$msg"
