"""live_multi.py -- run the validated maker (live_trader, which by default IS the micro_gate edge:
model_filter anchored on the microprice pulls the side the book is tipping) across ALL active crypto
Up/Down markets at once -- the BREADTH lever (rebate volume is the P&L driver; corr(pnl,#markets)=+0.59).
Launches one live_trader process per {btc,eth,sol,xrp}x{15m,5m}.

DRY-RUN by default (each child prints intended orders, places nothing). To go live, every child needs
--live AND I_UNDERSTAND_REAL_MONEY=yes in the environment -- pass --live here and export the env on a
funded, co-located box (DEPLOY.md). Extra args after '--' are forwarded to each live_trader.

    python live_multi.py                 # DRY-RUN all 8 markets, micro_gate on
    python live_multi.py -- --max-notional 25 --cap 50      # forward args
    I_UNDERSTAND_REAL_MONEY=yes python live_multi.py --live -- --max-notional 25   # LIVE (your box)
"""
import subprocess
import sys
import time

MARKETS = [("btc", 15), ("eth", 15), ("sol", 15), ("xrp", 15), ("btc", 5), ("eth", 5)]


def main():
    live = "--live" in sys.argv
    fwd = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    procs = []
    for asset, tmin in MARKETS:
        cmd = [sys.executable, "-u", "live_trader.py", "--asset", asset, "--tenor-min", str(tmin)]
        if live:
            cmd.append("--live")           # child still self-guards on I_UNDERSTAND_REAL_MONEY
        cmd += fwd
        procs.append((f"{asset}-{tmin}m", subprocess.Popen(cmd)))
        print(f"launched {asset}-{tmin}m ({'LIVE' if live else 'DRY'})", flush=True)
        time.sleep(1)
    print(f"{len(procs)} maker instances running (micro_gate edge, breadth). Ctrl-C to stop all.", flush=True)
    try:
        for name, p in procs:
            p.wait(); print(f"exited {name} rc={p.returncode}")
    except KeyboardInterrupt:
        for _, p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
