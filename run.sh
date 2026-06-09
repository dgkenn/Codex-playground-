#!/usr/bin/env bash
# Free-tier launcher / go-live harness.
# Usage: ./run.sh setup|preflight|paper|dryrun|pilot|live|reconcile|report
set -e
cd "$(dirname "$0")"
act(){ . .venv/bin/activate 2>/dev/null || true; }
envload(){ [ -f .env ] && set -a && . ./.env && set +a || true; }
case "${1:-}" in
  setup)     bash deploy/setup.sh;;
  # GATE before any money: runs every safety check -> one GO/NO-GO verdict (see go_live.py).
  preflight) act; exec python -u go_live.py "${@:2}";;
  # READ-ONLY paper sim (no keys).
  paper)     act; envload; \
             exec python -u paper_trader_ws.py --duration "${2:-86400}" --cap "${CAP:-50}" --post "${POST:-20}" --skew "${SKEW:-0.25}";;
  # DRY-RUN on this box: discovers markets, places NOTHING (proves plumbing + colo + guards).
  dryrun)    act; envload; exec python -u live_trader.py --presign --duration "${2:-120}" "${@:3}";;
  # TINY LIVE pilot: arms real orders (needs I_UNDERSTAND_REAL_MONEY=yes in .env). Small caps + kill-switch.
  pilot)     act; envload; \
             exec python -u live_trader.py --live --presign --max-notional "${MAX_NOTIONAL:-25}" \
                  --loss-limit "${LOSS_LIMIT:-5}" --duration "${2:-7200}" "${@:3}";;
  # ESCAPE HATCH: pass-through any live_trader args (add --live to arm).
  live)      act; envload; exec python -u live_trader.py "${@:2}";;
  # The real go/no-go AFTER a pilot: live fills/rebate/markout vs paper, as a t-stat.
  reconcile) act; exec python -u pilot_reconcile.py "${@:2}";;
  report)    act; exec python audit_report.py;;
  *) echo "usage: ./run.sh setup|preflight|paper [secs]|dryrun [secs]|pilot [secs]|live [args]|reconcile|report";;
esac
