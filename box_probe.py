"""Box-premium probe: a NON-microprice, NON-rebate, direction-free candidate edge.

A complete set (UP + DOWN) settles to exactly $1. So:
  - SELL both legs -> you receive ask_up + ask_dn ; if that SUM > 1 you locked (sum-1)/set RISK-FREE.
  - BUY  both legs -> you pay bid_up + bid_dn ; if that SUM < 1 you locked (1-sum)/set risk-free.
Maker fee = 0, so a maker capturing this pays nothing. This probe samples both books live and
measures how often / how much the box is mispriced -- i.e. the size of the opportunity (capture is
then an execution / two-leg-fill problem). python box_probe.py [seconds]
"""
import sys, time
import requests
import numpy as np
from live_trader import active_market, book

DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 150


def main():
    sess = requests.Session()
    mk = active_market(sess)
    if not mk:
        print("no active market"); return
    up, dn = mk["up"], mk["down"]
    print(f"probing box on {mk['ws']} for {DUR}s (tick={mk['tick']})...")
    sell_prem, buy_prem, spreads = [], [], []
    t0 = time.time()
    while time.time() - t0 < DUR:
        bbu, bau, _, _ = book(sess, up); bbd, bad, _, _ = book(sess, dn)
        if bau and bad:
            sell_prem.append(bau + bad - 1.0)            # sell both -> receive asks ; >0 = free gross/set
        if bbu and bbd:
            buy_prem.append(1.0 - (bbu + bbd))           # buy both -> pay bids ; >0 = free gross/set
        if bau and bbu:
            spreads.append(bau - bbu)
        time.sleep(1)
    sp = np.array(sell_prem); bp = np.array(buy_prem)
    print(f"\nsamples: {len(sp)}  median spread={np.median(spreads):.4f}")
    print("SELL-both box premium (ask_up+ask_dn - 1):")
    print(f"  mean={sp.mean():+.4f}  median={np.median(sp):+.4f}  %>0={100*(sp>0).mean():.0f}%  %>1c={100*(sp>0.01).mean():.0f}%  max={sp.max():+.4f}")
    print("BUY-both box premium (1 - bid_up-bid_dn):")
    print(f"  mean={bp.mean():+.4f}  median={np.median(bp):+.4f}  %>0={100*(bp>0).mean():.0f}%  %>1c={100*(bp>0.01).mean():.0f}%  max={bp.max():+.4f}")
    cap = max(sp.max(), bp.max())
    print(f"\nRead: a positive box premium that appears (even briefly) is RISK-FREE gross if both legs fill.")
    print(f"best instantaneous box edge seen = {cap:+.4f}/set. Persistent >0 mean => a real standing edge;")
    print(f"only-occasional spikes => an execution/latency capture (be the one who legs both first).")


if __name__ == "__main__":
    main()
