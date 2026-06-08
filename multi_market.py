"""multi_market.py -- run the shadow maker across multiple assets x tenors in PARALLEL (MAKEREDGE.md #5).

Breadth is a maker-edge expansion: the same code + the same in-region RTDS feed quote BTC/ETH/SOL/XRP at
15m and 5m simultaneously -> more rebate volume (rebate is a SHARE of the fee pool ∝ your filled volume,
and feeds the 30-day volume tier, #6), and diversified resolution risk across uncorrelated-ish outcomes.
Each market is an independent shadow_compare process writing UNIQUE tagged files, so aggregate_shadow.py /
hedge_value.py pick them all up. Per-asset breakdown via the `asset`/`tenor_min` fields now in each window.

    python multi_market.py [duration_s] [out_dir] [tag]
    # then: python aggregate_shadow.py     (pooled)  -- or filter by tag prefix per market

Resource note: each process holds a WS connection + 21 variants; the default 6 markets are fine on a
1-2 OCPU box. Trim MARKETS for a smaller box, or add the rest for full breadth.
"""
import subprocess
import sys
import time

# (asset, tenor_min) -- all exist & open (verified). The 4x15m set is the CLEAN cross-asset comparison:
# same tenor, shared resolution windows -> lets breadth_net_corr.py measure micro_gate's true per-window
# net correlation across assets (the real breadth Sharpe). 5m markets (btc/eth/sol/xrp 5m) available too;
# add them for max rebate volume once we've confirmed the 4x15m runs cleanly on the 2-core GHA runner.
MARKETS = [("btc", 15), ("eth", 15), ("sol", 15), ("xrp", 15)]


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 2940
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    base = sys.argv[3] if len(sys.argv) > 3 else str(int(time.time()))
    procs = []
    for asset, tmin in MARKETS:
        tag = f"{asset}{tmin}m_{base}"                 # unique per market+run -> no file collisions
        cmd = [sys.executable, "-u", "shadow_compare.py", "--duration", str(dur),
               "--asset", asset, "--tenor-min", str(tmin), "--out-dir", out_dir, "--tag", tag]
        procs.append((f"{asset}-{tmin}m", subprocess.Popen(cmd)))
        print(f"launched {asset}-{tmin}m  tag={tag}", flush=True)
        time.sleep(1)                                  # stagger market discovery a touch
    print(f"{len(procs)} markets running for {dur}s ...", flush=True)
    rc = 0
    for name, p in procs:
        p.wait()
        print(f"done {name} rc={p.returncode}", flush=True)
        rc = rc or p.returncode
    sys.exit(rc)


if __name__ == "__main__":
    main()
