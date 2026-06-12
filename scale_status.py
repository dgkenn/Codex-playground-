"""scale_status.py -- Stage-A ($10->$100) gate dashboard. Compact, read-only.
Prints each pre-registered SCALE_GATE.md Stage-A condition with live status: PASS/FAIL/PENDING.
Run daily: python scale_status.py
"""
import json, os, datetime, glob
from collections import defaultdict

AUD = "window_audit_btc15m.jsonl"
LEDGER = "box_policy_ledger_btc.jsonl"
SENT = ".kalshi_killed_btc15m"

def main():
    rows = []
    if os.path.exists(AUD):
        rows = [json.loads(l) for l in open(AUD) if l.strip()]
    days = defaultdict(lambda: [0.0, 0])
    for r in rows:
        d = datetime.datetime.utcfromtimestamp(r["ws"]).strftime("%Y-%m-%d")
        days[d][0] += r["pnl"]; days[d][1] += 1
    ds = sorted(days)
    # consecutive green days (>=20 windows traded) ending today
    streak = 0
    for d in reversed(ds):
        pnl, n = days[d]
        if pnl > 0 and n >= 20:
            streak += 1
        else:
            break
    unp = sum(1 for r in rows if r.get("unpaired", 0) > 0)
    unp_rate = unp / len(rows) if rows else float("nan")
    led_n = sum(1 for _ in open(LEDGER)) if os.path.exists(LEDGER) else 0
    killed = os.path.exists(SENT)

    print("== STAGE-A ($100) GATE STATUS ==", datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    print(f"per-day: " + "  ".join(f"{d[5:]}:{days[d][0]:+.0f}c/{days[d][1]}w" for d in ds[-8:]))
    g1 = streak >= 7
    print(f"[{'PASS' if g1 else 'PEND'}] 1. 7 consec green days (>=20w/day): streak={streak}/7")
    g2 = len(rows) >= 150 and unp_rate < 0.30
    print(f"[{'PASS' if g2 else 'PEND'}] 2. unpaired<30% over >=150w: {unp_rate:.0%} over {len(rows)}w"
          f" ({'rate OK, need windows' if unp_rate < 0.30 and len(rows) < 150 else ''})")
    g3 = not killed
    print(f"[{'PASS' if g3 else 'FAIL'}] 3. no kill trips (sentinel {'PRESENT' if killed else 'absent'})"
          f" -- 7-day lookback is manual: check Telegram kill alerts")
    g4 = led_n >= 300
    print(f"[{'PEND' if not g4 else 'PASS'}] 4. A/B trial past bar: ledger {led_n}/300 windows"
          f" (candidates: t02 t=2.79@100w, t36 OOS 3x backtest)")
    print(f"\nDEPLOY PREP: --guard-yes-spread is CODED (default OFF). When gate 4 clears with t02/t36,")
    print(f"arm via live_loop.sh: add --guard-yes-spread 0.02 -- nothing else changes.")
    print(f"NEXT BLOCKER: " + ("fund to $100 + Stage-A transition!" if g1 and g2 and g3 and g4 else
          "accumulate clean days + ledger windows (collectors must run 24/7; GHA secrets enable the cloud loop)."))

if __name__ == "__main__":
    main()
