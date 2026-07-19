#!/usr/bin/env python3
"""wx_capacity_probe.py -- is DEPTH_CAP=25 right? Measure ACTUAL fillable depth on live Kalshi weather books.

The capacity ceiling (~$750/mo free) is set almost entirely by DEPTH_CAP=25 -- the assumed max contracts a
single fire's book can absorb without moving the price. That was a Tier-1 estimate ("books 5-100ct"); it is
THE lever on the monthly ceiling, so it's worth measuring against real order books. This samples today's live
KXHIGH/KXLOWT ladders and, for each active rung, reads the public order book to report how many contracts sit
at the ask within our MAX_PAY_CENTS (98c) -- i.e. how many we could actually buy right now without walking the
book. Aggregated, that says whether 25 is conservative, about right, or optimistic.

PROPOSE-ONLY: reads public market data only. No auth, no orders.
"""
import json, os, ssl, statistics as st, urllib.request
import kwx_runner as R

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"


def _get(url, to=20):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def orderbook_ask_depth(ticker, max_pay_c=98):
    """Contracts available to BUY YES at <= max_pay_c cents (sum of yes-ask levels within the cap).
    Kalshi orderbook: {'orderbook': {'yes': [[price_c, size], ...], 'no': [[price_c, size], ...]}} where the
    'no' side at price p implies a YES ask at (100-p). We report fillable YES contracts at ask <= cap."""
    try:
        ob = _get(f"{KBASE}/markets/{ticker}/orderbook")["orderbook"]
    except Exception:
        return None
    depth = 0
    # YES buyers lift the NO resting orders: a NO bid at price q = a YES ask at (100 - q).
    for lvl in (ob.get("no") or []):
        q, size = int(lvl[0]), int(lvl[1])
        yes_ask = 100 - q
        if yes_ask <= max_pay_c:
            depth += size
    return depth


def retro():
    """Retrospective depth-proxy read from the backtest (available any hour, unlike the live probe which needs
    active US markets). volume_at_exec / oi_at_exec sit at each lock moment. CAVEAT: traded volume + open
    interest are NOT resting-ask depth -- they bound liquidity but don't pin the fillable number; the live
    probe is the definitive measure. Still, they answer the shape: are the fires our FREE feed catches on
    thin/quiet rungs (DEPTH_CAP~right) or deep ones (headroom)?"""
    import json, statistics as st
    raw = json.load(open(os.path.join(HERE, "_trackA_results_raw.json")))
    caught_vol, caught_oi = [], []
    for r in raw:
        c = r["cells"].get("1_3")
        if not c or not c.get("fired") or not c.get("exec_price") or c["exec_price"] >= 0.99:
            continue
        g = c.get("decay_gap_by_min", {}).get("10")   # catchable on the free/MADIS feed (~10 min)?
        if g is None or (1 - g) >= 0.99:
            continue
        caught_vol.append(c.get("volume_at_exec") or 0)
        caught_oi.append(c.get("oi_at_exec") or 0)
    if not caught_vol:
        print("no caught fires"); return
    pc = lambda a, q: sorted(a)[min(len(a) - 1, int(q * len(a)))]
    n = len(caught_vol)
    print(f"RETROSPECTIVE depth proxy | {n} fires catchable at ~10min (free feed)")
    print(f"  volume_at_exec (traded):  median {st.median(caught_vol):.0f}  p75 {pc(caught_vol,.75):.0f}  p90 {pc(caught_vol,.90):.0f}")
    print(f"  oi_at_exec (open interest): median {st.median(caught_oi):.0f}  p90 {pc(caught_oi,.90):.0f}")
    print(f"  share of caught fires with volume_at_exec < DEPTH_CAP({R.DEPTH_CAP}): "
          f"{100*sum(1 for v in caught_vol if v < R.DEPTH_CAP)/n:.0f}%")
    print("  read: the free feed catches thin/quiet rungs (low traded volume) -> DEPTH_CAP~25 is likely near-right\n"
          "  for them, NOT obviously conservative. The depth headroom lives in the DEEP/fast fires that need\n"
          "  Synoptic; so Synoptic likely compounds -- more fires AND deeper fills. Live probe confirms the number.")


def main():
    import sys
    if "--retro" in sys.argv:
        retro(); return
    mkts = R.active_market_days()
    print(f"sampling live Kalshi weather books | {len(mkts)} city-market-days today | DEPTH_CAP(assumed)={R.DEPTH_CAP}\n")
    depths = []
    n_rungs = 0
    per_city = {}
    for series, ev, station, offset, lst_date, kind in mkts:
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        city_depths = []
        for rr in rungs:
            ask = rr.get("yes_ask_c")
            if not ask or ask > R.MAX_PAY_CENTS:
                continue
            d = orderbook_ask_depth(rr["ticker"])
            if d is None:
                continue
            n_rungs += 1
            depths.append(d)
            city_depths.append(d)
        if city_depths:
            per_city[station] = (len(city_depths), st.median(city_depths))
    if not depths:
        print("no active tradeable rungs found right now (markets may be pre-open or fully repriced).")
        return
    depths.sort()
    p = lambda q: depths[min(len(depths) - 1, int(q * len(depths)))]
    print(f"tradeable rungs sampled: {n_rungs}")
    print(f"fillable YES depth at ask<=98c (contracts): median {st.median(depths):.0f}  "
          f"mean {st.mean(depths):.0f}  p25 {p(0.25):.0f}  p75 {p(0.75):.0f}  p90 {p(0.90):.0f}  max {max(depths)}")
    below = sum(1 for d in depths if d < R.DEPTH_CAP) / len(depths)
    print(f"share of rungs with depth < DEPTH_CAP(25): {100*below:.0f}%  "
          f"(if high, 25 rarely binds -> ceiling is depth-real; if low, 25 is conservative -> ceiling could rise)")
    print("\nper-station median fillable depth (rungs):")
    for stn, (n, med) in sorted(per_city.items(), key=lambda kv: -kv[1][1]):
        print(f"  {stn:>6}: median {med:>4.0f}ct over {n} rungs")
    print("\nread: DEPTH_CAP should sit near the median fillable depth of the rungs we actually fire on. If the "
          "measured median >> 25, raise DEPTH_CAP (ceiling rises); if << 25, the ceiling is even lower than modeled.")


if __name__ == "__main__":
    main()
