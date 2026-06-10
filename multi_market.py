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
import signal
import subprocess
import sys
import time

# (asset, tenor_min) -- all exist & open (verified via Gamma probe 2026-06-10; doge/bnb/hype trade
# up/down at both tenors too). The 4x15m core remains the CLEAN cross-asset comparison (same tenor,
# shared resolution windows -> breadth_net_corr.py measures the true cross-asset net correlation).
# 5m tenors + the 3 extra assets are the cheapest n-multiplier there is: ~3.4x more windows/day for
# the same runner (processes are I/O-bound; gzip keeps the volume sane). WINDOW_S scales per-tenor
# in shadow_compare, and every spot feed is per-asset, so 5m/alt data is clean by construction.
MARKETS = [("btc", 15), ("eth", 15), ("sol", 15), ("xrp", 15),
           ("btc", 5), ("eth", 5), ("sol", 5), ("xrp", 5),
           ("doge", 15), ("bnb", 15), ("hype", 15)]


MIN_RESTART_S = 120        # don't relaunch a market with <2min left (a fresh window won't settle)
MAX_RESTARTS = 5           # per market -> bounded; a crash-looping market won't spin forever
POLL_S = 30                # supervisor poll cadence


def launch(asset, tmin, dur, out_dir, base, attempt):
    # tag stays STABLE across restarts (same base) so a market's window files accumulate into one set;
    # shadow_compare appends, so a relaunch continues the same data stream seamlessly.
    tag = f"{asset}{tmin}m_{base}"                     # unique per market+run -> no file collisions
    cmd = [sys.executable, "-u", "shadow_compare.py", "--duration", str(int(dur)),
           "--asset", asset, "--tenor-min", str(tmin), "--out-dir", out_dir, "--tag", tag]
    p = subprocess.Popen(cmd)
    print(f"{'relaunched' if attempt else 'launched'} {asset}-{tmin}m  tag={tag}  "
          f"dur={int(dur)}s{f' (attempt {attempt+1})' if attempt else ''}", flush=True)
    return p


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 2940
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    base = sys.argv[3] if len(sys.argv) > 3 else str(int(time.time()))
    deadline = time.time() + dur
    state = {}                                         # name -> {proc, asset, tmin, restarts}

    # SIGNAL FORWARDING (audit #2b): the workflow's `timeout` sends SIGTERM to THIS process only;
    # children used to be orphaned mid-drain and their unsettled windows silently lost. Forward TERM
    # and give each child a moment to write its tombstones before we exit.
    def _term(_sig, _frm):
        print("SIGTERM -> forwarding to children (tombstone drain)", flush=True)
        for st in state.values():
            if st["proc"].poll() is None:
                st["proc"].terminate()
        t0 = time.time()
        for st in state.values():
            try:
                st["proc"].wait(timeout=max(1, 25 - (time.time() - t0)))
            except subprocess.TimeoutExpired:
                st["proc"].kill()
        sys.exit(143)
    signal.signal(signal.SIGTERM, _term)
    for asset, tmin in MARKETS:
        name = f"{asset}-{tmin}m"
        state[name] = {"proc": launch(asset, tmin, dur, out_dir, base, 0),
                       "asset": asset, "tmin": tmin, "restarts": 0}
        time.sleep(1)                                  # stagger market discovery a touch
    print(f"{len(state)} markets running for {dur}s (supervised) ...", flush=True)

    # SUPERVISOR: poll for dead children; relaunch any that exit while meaningful time remains, so a
    # single crashed market never silently drops out of the multi-hour capture. Bounded by MAX_RESTARTS.
    while time.time() < deadline:
        time.sleep(POLL_S)
        remaining = deadline - time.time()
        for name, st in state.items():
            p = st["proc"]
            if p.poll() is None:
                continue                               # still running
            if remaining < MIN_RESTART_S:
                continue                               # too little left to bother
            if st["restarts"] >= MAX_RESTARTS:
                print(f"!! {name} exited rc={p.returncode}; restart cap reached, leaving down", flush=True)
                continue
            st["restarts"] += 1
            print(f"!! {name} exited rc={p.returncode} with {int(remaining)}s left -> relaunching", flush=True)
            st["proc"] = launch(st["asset"], st["tmin"], remaining, out_dir, base, st["restarts"])

    rc = 0
    for name, st in state.items():                     # window passed: let each finish its final settle
        st["proc"].wait()
        print(f"done {name} rc={st['proc'].returncode} (restarts={st['restarts']})", flush=True)
        rc = rc or st["proc"].returncode
    sys.exit(rc)


if __name__ == "__main__":
    main()
