#!/usr/bin/env bash
# THE LIGHT SWITCH for the live bot.  ./live_switch.sh on | off | status
#
# Flips the LIVE_SWITCH file (one word: on|off) and pushes it. The durable live-trade GitHub
# Actions workflow (.github/workflows/live.yml) and the local supervisor both read this file every
# cycle, so toggling it is the ONLY thing you do to start/stop live trading -- no Claude prompt
# needed. A loss-limit trip flips it OFF automatically (sticky); turning it back ON is deliberate
# and also clears the kill sentinel so you get a clean start.
set -u
cd "$(dirname "$0")"
BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo claude/polymarket-bot-live-ready-vw7ut5)"
ASSET="${ASSET:-btc}"
cur() { tr -d '[:space:]' < LIVE_SWITCH 2>/dev/null || echo off; }
case "${1:-status}" in
  on|ON)
    echo on > LIVE_SWITCH
    rm -f ".kalshi_killed_${ASSET}15m"          # re-arm: clear any sticky loss-limit kill
    msg="live switch -> ON" ;;
  off|OFF)
    echo off > LIVE_SWITCH
    msg="live switch -> OFF" ;;
  status)
    echo "live switch: $(cur)"
    [ -f ".kalshi_killed_${ASSET}15m" ] && echo "  (kill sentinel present -> trading halted until you run: $0 on)"
    exit 0 ;;
  *) echo "usage: $0 on|off|status"; exit 2 ;;
esac
git add LIVE_SWITCH                      # sentinel is gitignored; never staged (would break add)
git commit -q -m "$msg" || { echo "nothing to commit (already $(cur))"; exit 0; }
for i in 1 2 3 4; do
  git push -u origin "$BR" && { echo "$msg (pushed to $BR)"; exit 0; }
  # non-fast-forward (branch moved while we were checked out, e.g. inside a GHA run) -> rebase
  git pull --rebase origin "$BR" 2>/dev/null || true
  sleep $((2 ** i))
done
echo "$msg locally, but push failed -- re-run when network recovers" >&2; exit 1
