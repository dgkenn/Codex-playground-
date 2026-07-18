#!/usr/bin/env python3
"""kwx_paper_gate.py -- turnkey hands-off FORWARD PAPER GATE for K-WX (the last step before live).

One command runs the whole ~2-week validation: it drives the adaptive runner in PAPER (dry-run) around the
clock, periodically settles resolved paper fires against Kalshi, and reports whether LIVE == TESTED. This is
the gate that must pass before any capital: it turns "~5%/day in simulation" into "~5%/day confirmed on real
live fills." Ideal to run on a persistent host during the free-feed period (or the Synoptic trial window).

It NEVER trades real money: execution goes through kalshi_exec (DRY-RUN unless KWX_LIVE=1 + creds), and this
harness does not set that flag. It also honors the .kwx_halt kill switch.

What it does each loop:
  1. kwx_runner.poll_once()  -> detect locks, log intended (paper) fills, adaptive sleep
  2. every SETTLE_EVERY_S    -> kwx_forward.settle() + report(), write a one-glance status file
  3. writes kwx_gate_status.txt so you can check progress at any time

PASS criteria (from Phase-2 Track A deployable): win >= ~99%, EV/ct >= ~+0.12 (conservative vs +0.20 sim),
day-clustered t >= 3, n >= 30 settled fires. When all hold, the status file says READY-FOR-CANARY.

Usage:
  python kwx_paper_gate.py                 # run forever (Ctrl-C to stop); check kwx_gate_status.txt
  python kwx_paper_gate.py --once          # one poll + settle + report cycle (for cron/testing)
"""
import os, sys, time, json, argparse, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "kwx_gate_status.txt")
SETTLE_EVERY_S = 3600          # settle+report hourly
# PASS bar (deliberately conservative vs the +0.20 sim, so passing is a real signal)
PASS = {"win": 0.99, "ev": 0.12, "t": 3.0, "n": 30}


def _report_metrics():
    """Compute the forward paper stats (mirrors kwx_forward.report) as a dict for the gate decision."""
    import math, statistics as st
    from collections import defaultdict
    import kwx_forward as F
    rows = F._load_jsonl(F.SETTLED)
    if not rows:
        return None
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for r in rows if r["won"])
    n = len(rows)
    byday = defaultdict(list)
    for r in rows:
        byday[r.get("date", "?")].append(r["pnl"])
    dm = [st.mean(v) for v in byday.values()]
    t = (st.mean(dm) / (st.stdev(dm) / math.sqrt(len(dm)))) if len(dm) > 1 and st.stdev(dm) > 0 else float("nan")
    return {"n": n, "win": wins / n, "ev": st.mean(pnls), "t": t, "days": len(byday), "worst": min(pnls)}


def _write_status(m, last_poll_locks, next_sleep_s):
    lines = ["=== K-WX FORWARD PAPER GATE status ===",
             f"updated: {dt.datetime.now(tz=dt.timezone.utc).isoformat()}",
             f"last poll: {last_poll_locks} new paper locks; next poll in ~{int(next_sleep_s)}s",
             f"kill-switch (.kwx_halt): {'PRESENT -> halted' if os.path.exists(os.path.join(HERE,'.kwx_halt')) else 'off'}",
             ""]
    if not m:
        lines.append("no settled paper fires yet -- accruing. (bar: win>=99%, EV>=+0.12, t>=3, n>=30)")
    else:
        passed = (m["win"] >= PASS["win"] and m["ev"] >= PASS["ev"] and
                  (m["t"] >= PASS["t"] or m["t"] != m["t"]) and m["n"] >= PASS["n"])
        # note: t!=t is NaN guard (few days); require n and win/ev primarily
        verdict = ("READY-FOR-CANARY (live==tested)" if passed and m["n"] >= PASS["n"] and m["t"] >= PASS["t"]
                   else "ACCRUING (need n>=30 and t>=3)" if m["n"] < PASS["n"] or (m["t"] < PASS["t"])
                   else "REVIEW -- win/EV below bar (live may differ from tested)")
        lines += [
            f"settled fires : {m['n']}  over {m['days']} days",
            f"win rate      : {m['win']:.1%}   (bar {PASS['win']:.0%}, backtest ~99.6%)",
            f"EV/contract   : {m['ev']:+.3f}   (bar +{PASS['ev']:.2f}, backtest ~+0.20)",
            f"day-clustered t: {m['t']:.2f}   (bar {PASS['t']})",
            f"worst fire    : {m['worst']:+.3f}",
            "",
            f"VERDICT: {verdict}",
        ]
    open(STATUS, "w").write("\n".join(lines) + "\n")
    return lines


def cycle(verbose=True):
    import kwx_runner as R
    import kwx_forward as F
    locks, sleep_s = R.poll_once(verbose=verbose)
    F.settle()
    m = _report_metrics()
    lines = _write_status(m, len(locks), sleep_s)
    if verbose:
        print("\n".join(lines))
    return sleep_s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="one poll+settle+report cycle then exit (cron mode)")
    args = ap.parse_args()
    if args.once:
        cycle()
        return
    print("K-WX paper gate running (PAPER/dry-run). Status -> kwx_gate_status.txt. Ctrl-C to stop.")
    last_settle = 0.0
    while True:
        import kwx_runner as R
        locks, sleep_s = R.poll_once(verbose=False)
        now = time.time()
        if now - last_settle >= SETTLE_EVERY_S:
            import kwx_forward as F
            F.settle()
            m = _report_metrics()
            _write_status(m, len(locks), sleep_s)
            last_settle = now
        time.sleep(max(3, sleep_s))


if __name__ == "__main__":
    main()
