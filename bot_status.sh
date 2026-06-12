#!/usr/bin/env bash
# One-command health/control audit: instance counts MUST be loops<=1, traders<=1.
cd "$(dirname "$0")"
L=$(pgrep -fc "bash .*live_loop.sh" 2>/dev/null || echo 0)
T=$(pgrep -fc "python -u kalshi_trader.py" 2>/dev/null || echo 0)
echo "loops=$L traders=$T switch=$(cat LIVE_SWITCH 2>/dev/null) sentinel=$([ -f .kalshi_killed_btc15m ] && echo TRIPPED || echo clear)"
[ "$L" -le 1 ] && [ "$T" -le 1 ] && echo "OK: single-instance invariant holds" || echo "VIOLATION: multiple instances -- kill by PID and restart via ./live_loop.sh"
python3 -c "
import json
rows=[json.loads(l) for l in open('window_audit_btc15m.jsonl') if l.strip()][-3:]
import time
for r in rows: print('  recent:', time.strftime('%H:%M', time.gmtime(r['ws'])), f\"{r['pnl']*100:+.0f}c unpaired={r['unpaired']:.0f}\")" 2>/dev/null
