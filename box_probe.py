"""Box-premium probe: the complete-set (UP+DOWN settle to exactly $1) as a direction-free candidate.

There are TWO box premiums and they are NOT the same edge -- the original version of this probe
conflated them, which overstated the opportunity. Be precise about who pays the spread:

  MAKER box (rest on both legs, get LIFTED/HIT there):
    - rest SELL both -> you receive ask_up + ask_dn ; spread_sell = ask_up+ask_dn - 1
    - rest BUY  both -> you pay    bid_up + bid_dn ; spread_buy  = 1 - (bid_up+bid_dn)
    In a 1-tick market this is ~+1 tick mechanically (asks sit a tick above mids that sum to ~1).
    It is just the round-trip MM SPREAD, and it is risk-free ONLY if BOTH legs fill -- if one fills
    you are left holding a directional leg (legging risk). i.e. this is the maker edge we already
    study (rebate + spread, bound by queue + adverse selection), re-expressed. Not new, not free.

  TAKER box (CROSS into both legs right now -> genuinely risk-free / direction-free / fee-free):
    - take SELL both (hit the bids) -> you receive bid_up + bid_dn ; free_sell = bid_up+bid_dn - 1
    - take BUY  both (lift the asks) -> you pay    ask_up + ask_dn ; free_buy  = 1 - (ask_up+ask_dn)
    >0 here = free money even crossing the spread as a taker. The literature says this is competed
    away in liquid 15m crypto (sub-100ms bots; the dynamic taker fee was added to kill it). This
    probe measures whether ANY such instant exists, and how big/long-lived. python box_probe.py [s]
"""
import sys, time
import requests
import numpy as np
from live_trader import active_market, book

DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 150


def _stats(name, a):
    if len(a) == 0:
        print(f"  {name}: no samples"); return
    a = np.array(a)
    print(f"  {name}: mean={a.mean():+.4f} median={np.median(a):+.4f} "
          f"%>0={100*(a>0).mean():.0f}% %>1c={100*(a>0.01).mean():.0f}% max={a.max():+.4f}")


def main():
    sess = requests.Session()
    mk = active_market(sess)
    if not mk:
        print("no active market"); return
    up, dn = mk["up"], mk["down"]
    print(f"probing box on {mk['ws']} for {DUR}s (tick={mk['tick']})...")
    mk_sell, mk_buy, tk_sell, tk_buy, spreads = [], [], [], [], []
    t0 = time.time()
    while time.time() - t0 < DUR:
        bbu, bau, _, _ = book(sess, up); bbd, bad, _, _ = book(sess, dn)
        if bau and bad:
            mk_sell.append(bau + bad - 1.0)      # MAKER rest-sell-both spread (~+1 tick)
            tk_buy.append(1.0 - (bau + bad))     # TAKER lift-both: free only if ask_up+ask_dn < 1
        if bbu and bbd:
            mk_buy.append(1.0 - (bbu + bbd))     # MAKER rest-buy-both spread (~+1 tick)
            tk_sell.append(bbu + bbd - 1.0)      # TAKER hit-both: free only if bid_up+bid_dn > 1
        if bau and bbu:
            spreads.append(bau - bbu)
        time.sleep(1)
    n = max(len(mk_sell), len(mk_buy))
    print(f"\nsamples: {n}  median spread={np.median(spreads) if spreads else float('nan'):.4f}")
    print("MAKER box (= the round-trip MM spread; risk-free ONLY if both legs fill -> legging risk):")
    _stats("rest-sell-both (ask_up+ask_dn-1)", mk_sell)
    _stats("rest-buy-both  (1-bid_up-bid_dn)", mk_buy)
    print("TAKER box (genuinely risk-free/direction-free/fee-free if >0 -- the real free arb):")
    _stats("hit-both  (bid_up+bid_dn-1)", tk_sell)
    _stats("lift-both (1-ask_up-ask_dn)", tk_buy)
    tk = np.array(tk_sell + tk_buy)
    free = 100 * (tk > 0).mean() if len(tk) else float("nan")
    print(f"\nRead: MAKER box ~ +1 tick = the spread we already harvest (not new, not free). The TAKER box "
          f"is the only genuinely free line; it was >0 in {free:.0f}% of samples here. Persistent >0 => a "
          f"real standing free arb; ~0 => the market is efficient at the touch and the box collapses to MM.")


if __name__ == "__main__":
    main()
