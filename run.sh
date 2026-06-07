#!/usr/bin/env bash
# Free-tier launcher. Usage: ./run.sh setup|paper|live|report
set -e
cd "$(dirname "$0")"
case "${1:-}" in
  setup)  python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && echo "setup done";;
  paper)  . .venv/bin/activate && [ -f .env ] && set -a && . ./.env && set +a; \
          exec python -u paper_trader_ws.py --duration "${2:-86400}" --cap "${CAP:-50}" --post "${POST:-20}" --skew "${SKEW:-0.25}";;
  live)   . .venv/bin/activate && set -a && . ./.env && set +a; \
          exec python -u live_trader.py "${@:2}";;       # add --live to arm (needs I_UNDERSTAND_REAL_MONEY=yes)
  report) . .venv/bin/activate && exec python audit_report.py;;
  *) echo "usage: ./run.sh setup|paper [secs]|live [--live ...]|report";;
esac
