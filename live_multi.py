"""live_multi.py -- run the validated maker (live_trader, which by default IS the micro_gate edge:
model_filter anchored on the microprice pulls the side the book is tipping) across ALL active crypto
Up/Down markets at once -- the BREADTH lever (rebate volume is the P&L driver; corr(pnl,#markets)=+0.59).
Launches one live_trader process per {btc,eth,sol,xrp}x{15m,5m}.

DRY-RUN by default (each child prints intended orders, places nothing). To go live, every child needs
--live AND I_UNDERSTAND_REAL_MONEY=yes in the environment -- pass --live here and export the env on a
funded, co-located box (DEPLOY.md). Extra args after '--' are forwarded to each live_trader.

    python live_multi.py                 # DRY-RUN all markets, micro_gate on
    python live_multi.py -- --max-notional 25 --cap 50      # forward args
    I_UNDERSTAND_REAL_MONEY=yes python live_multi.py --live -- --max-notional 25   # LIVE (your box)

Capital weighting (INSIGHTS_4DAY #2: BTC's net/win is ~3x the others; XRP barely pays): the venue
minimum order size (~5 shares) makes a sub-5 --post unplaceable, so per-asset weighting is expressed
through --max-rungs (ladder DEPTH), not clip size -- BTC rests a full ladder, XRP a single rung.
"""
import os
import subprocess
import sys
import time

import notify

MARKETS = [("btc", 15), ("eth", 15), ("sol", 15), ("xrp", 15), ("btc", 5), ("eth", 5)]

# Per-asset ladder-depth weights (BTC-heavy). Tune from leaderboard/metrics per-asset as data grows.
RUNGS = {"btc": 5, "eth": 2, "sol": 2, "xrp": 1}
MAX_RESTARTS = 5          # per child, per session -- beyond this, alert and leave it down


def _spawn(asset, tmin, live, fwd, user_rungs):
    cmd = [sys.executable, "-u", "live_trader.py", "--asset", asset, "--tenor-min", str(tmin)]
    if not user_rungs:
        cmd += ["--max-rungs", str(RUNGS.get(asset, 2))]   # BTC-weighted ladder depth
    if live:
        cmd.append("--live")           # child still self-guards on I_UNDERSTAND_REAL_MONEY
    cmd += fwd
    env = dict(os.environ)
    # Children share one API key: a per-child startup cancel_all would nuke the siblings' fresh
    # orders. The parent does ONE venue-wide cancel_all below; children skip theirs.
    env["PMKIT_SKIP_STARTUP_CANCEL"] = "1"
    return subprocess.Popen(cmd, env=env)


def _startup_cancel_all(live):
    """One venue-wide cancel_all before any child quotes: clears every leftover from a prior run
    (a SIGKILL'd child never ran its dead-man). Fail-closed: refuse to launch live if it fails."""
    if not live:
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from live_trader import make_client
    try:
        make_client().cancel_all()
        print("[startup] venue cancel_all: cleared any stale orders from a prior run", flush=True)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"startup cancel_all FAILED ({type(e).__name__}: {str(e)[:120]}) -- "
                         "refusing to launch live on top of unknown resting orders")


def main():
    live = "--live" in sys.argv and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if "--live" in sys.argv and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. DRY-RUN.", flush=True)
    fwd = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    user_rungs = "--max-rungs" in fwd               # respect an explicit depth; otherwise weight it
    _startup_cancel_all(live)
    procs = {}                                       # name -> {"p": Popen, "restarts": int}
    for asset, tmin in MARKETS:
        name = f"{asset}-{tmin}m"
        procs[name] = {"p": _spawn(asset, tmin, live, fwd, user_rungs),
                       "asset": asset, "tmin": tmin, "restarts": 0}
        print(f"launched {name} ({'LIVE' if live else 'DRY'}) "
              f"rungs={'user' if user_rungs else RUNGS.get(asset, 2)}", flush=True)
        time.sleep(1)
    print(f"{len(procs)} maker instances running (micro_gate edge, breadth). Ctrl-C to stop all.", flush=True)
    # SUPERVISE: a crashed child = a market silently unquoted (and, live, possibly un-flattened --
    # its own dead-man handles clean signals; a hard crash is what the restart + alert covers).
    try:
        while True:
            for name, st in procs.items():
                rc = st["p"].poll()
                if rc is None:
                    continue
                if st["restarts"] >= MAX_RESTARTS:
                    continue                          # already alerted; leave it down
                st["restarts"] += 1
                msg = f"[pmkit] child {name} exited rc={rc}; restart {st['restarts']}/{MAX_RESTARTS}"
                print(msg, flush=True); notify.alert(msg)
                if st["restarts"] >= MAX_RESTARTS:
                    notify.alert(f"[pmkit] child {name} hit restart cap -- LEAVING DOWN, investigate")
                    continue
                time.sleep(2 * st["restarts"])        # backoff before respawn
                st["p"] = _spawn(st["asset"], st["tmin"], live, fwd, user_rungs)
            time.sleep(2)
    except KeyboardInterrupt:
        print("stopping all children...", flush=True)
        for st in procs.values():
            if st["p"].poll() is None:
                st["p"].terminate()                   # SIGTERM -> each child's dead-man cancels its book
        deadline = time.time() + 20
        for name, st in procs.items():
            try:
                st["p"].wait(timeout=max(deadline - time.time(), 1))
            except subprocess.TimeoutExpired:
                print(f"  {name} did not exit in time; killing", flush=True)
                st["p"].kill()
        print("all children stopped.", flush=True)


if __name__ == "__main__":
    main()
