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
  python kwx_paper_gate.py --max-seconds N # loop, but exit cleanly after ~N s wall-clock (CI leg mode:
                                           # honors the runner's adaptive 5s/20s near-strike cadence
                                           # instead of a flat bash `--once; sleep 30` loop)
"""
import os, sys, time, json, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "kwx_gate_status.txt")
HEARTBEAT = os.path.join(HERE, ".kwx_heartbeat")
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


def _beat():
    """Write the liveness heartbeat (.kwx_heartbeat, UTC ISO ts) once per poll cycle.

    WHY from python, not the workflow: the old bash wrapper loop (`--once; date -u > .kwx_heartbeat;
    sleep 30`) was the only thing beating -- once the workflow calls the python loop directly, a wedged
    runner would otherwise look alive forever. Beating here means the kwx-watchdog stales out exactly
    when polling actually stops. Best-effort: a disk hiccup must never kill the trading loop itself.
    """
    try:
        with open(HEARTBEAT, "w") as fh:
            fh.write(dt.datetime.now(tz=dt.timezone.utc).isoformat() + "\n")
    except OSError:
        pass


def cycle(verbose=True):
    import kwx_runner as R
    import kwx_forward as F
    locks, sleep_s = R.poll_once(verbose=verbose)
    _beat()   # --once (cron) mode beats too, so the watchdog sees cron legs as alive
    F.settle()
    m = _report_metrics()
    lines = _write_status(m, len(locks), sleep_s)
    if verbose:
        print("\n".join(lines))
    return sleep_s


def _parse_argv(argv):
    """LENIENT flag parse: unknown flags are ignored, bad values fall back to defaults -- never crash.

    WHY not argparse: this script and the workflow that invokes it live on DIFFERENT branches (code on
    the bot branch, .github/workflows on main) and deploy independently. If the workflow side merges
    first and passes a flag this side doesn't know yet (or vice versa), argparse's exit-on-unknown
    would crash every leg and take the live bot down. Ignoring what we don't understand fails SAFE:
    worst case we run in the old mode, and the job-level timeout still bounds the leg.
    """
    once = "--once" in argv
    max_seconds = None
    for i, a in enumerate(argv):
        val = None
        if a == "--max-seconds" and i + 1 < len(argv):
            val = argv[i + 1]
        elif a.startswith("--max-seconds="):
            val = a.split("=", 1)[1]
        if val is not None:
            try:
                max_seconds = max(1, int(float(val)))
            except ValueError:
                print(f"!! ignoring unparseable --max-seconds value {val!r} (running unbounded)")
    return once, max_seconds


def _startup_label():
    """Derive the startup banner's mode label from the ACTUAL exec gate (kalshi_exec.KalshiExec.live),
    instead of a hardcoded "PAPER/dry-run" string. The hardcoded label used to print regardless of
    KWX_LIVE/creds -- an operator doing a live-canary health check could see "PAPER/dry-run" while the
    bot was actually placing live orders. live == (KWX_LIVE=1 AND usable creds), exactly the same gate
    kalshi_exec.buy_yes/buy_no use, so this can never disagree with what the runner actually does."""
    try:
        import kalshi_exec as KE
        ex = KE.KalshiExec()
    except Exception as e:
        # Can't even construct the exec gate -- fall back to the raw env var so we never claim PAPER
        # while KWX_LIVE=1 is set (that's the exact misleading failure mode this fixes).
        live_env = os.environ.get("KWX_LIVE") == "1"
        return f"*** LIVE (unconfirmed; gate probe failed: {e}) ***" if live_env else "PAPER/dry-run"
    if not ex.live:
        return "PAPER/dry-run"
    try:
        default = KE._runner_default_bankroll()
        eff = KE.effective_bankroll(default, exec_client=ex)
        return f"*** LIVE *** (effective bankroll ${eff:.2f})"
    except Exception:
        return "*** LIVE *** (effective bankroll unavailable)"


def main():
    once, max_seconds = _parse_argv(sys.argv[1:])
    if once:
        cycle()
        return
    bound = f" (bounded to ~{max_seconds}s)" if max_seconds else ""
    print(f"K-WX paper gate running ({_startup_label()}){bound}. Status -> kwx_gate_status.txt. Ctrl-C to stop.")
    # --max-seconds: wall-clock bound so a CI job leg can run the adaptive loop directly (honoring the
    # 5s/20s near-strike cadence) and still hand back control before the job-level timeout kills it.
    deadline = (time.time() + max_seconds) if max_seconds else None
    last_settle = 0.0
    while True:
        if deadline is not None and time.time() >= deadline:
            print(f"--max-seconds {max_seconds} reached -> exiting cleanly")
            return
        import kwx_runner as R
        locks, sleep_s = R.poll_once(verbose=False)
        _beat()   # once per poll cycle, so watchdog staleness == polling actually stopped
        now = time.time()
        if now - last_settle >= SETTLE_EVERY_S:
            import kwx_forward as F
            F.settle()
            m = _report_metrics()
            _write_status(m, len(locks), sleep_s)
            last_settle = now
        nap = max(3, sleep_s)
        if deadline is not None:
            # never oversleep past the deadline: clamp so we wake right at the bound and exit
            # (instead of burning up to a full 15-min far-from-strike interval past it)
            nap = max(3, min(nap, deadline - time.time()))
        time.sleep(nap)


if __name__ == "__main__":
    main()
