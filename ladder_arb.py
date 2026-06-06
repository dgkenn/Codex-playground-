"""A: strike-ladder arbitrage on BTC 'above $K' hourly markets.

For digital options, P(>K) must be monotone DECREASING in K. So across strikes at
the same instant, a lower strike's YES must be priced >= a higher strike's YES.
Pure riskless arb (vertical spread) if you can BUY the low-strike YES and SELL the
high-strike YES for a CREDIT:  ask(K_low) < bid(K_high)  ->  payoff 1{>Klow}-1{>Khigh} >= 0
acquired for negative cost. We measure: (a) MID non-monotonicity (mispricing
signal), (b) crossable ask/bid inversions (pure arb), pre- and post-fee (2 legs).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share

MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6}
OFFSETS_MIN = [50, 40, 30, 20, 10, 5]   # sample before expiry


def expiry_utc(slug):
    m = re.search(r"on-([a-z]+)-(\d+)-(\d+)-(\d+)(am|pm)-et", slug)
    if not m:
        return None
    mon, day, yr, hh, ap = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
    if ap == "am":
        hh = 0 if hh == 12 else hh
    else:
        hh = 12 if hh == 12 else hh + 12
    et = datetime(yr, MONTHS[mon], day, hh, tzinfo=timezone.utc)
    return int(et.timestamp()) + 4 * 3600   # EDT = UTC-4 -> UTC = ET + 4h


def main():
    con = duckdb.connect()
    lad = pd.read_parquet("ladder_markets.parquet")
    lad["expiry_ts"] = lad["expiry"].map(expiry_utc)
    lad = lad.dropna(subset=["expiry_ts"])
    # build (expiry, strike, asset, t) grid
    rows = []
    for _, r in lad.iterrows():
        for off in OFFSETS_MIN:
            rows.append((r.expiry, r.strike, r.yes_asset, int(r.expiry_ts - off * 60) * 1000, off))
    g = pd.DataFrame(rows, columns=["expiry", "strike", "asset", "t_ms", "off"])
    tg = g.rename(columns={"asset": "asset_id"})[["asset_id", "t_ms"]].copy()
    tg["r"] = np.arange(len(tg))
    con.register("tg", tg)
    q = con.execute("""SELECT tg.r, CAST(b.best_bid AS DOUBLE) bid, CAST(b.best_ask AS DOUBLE) ask
        FROM tg ASOF LEFT JOIN read_parquet('ladder_book.parquet') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    g["bid"] = q["bid"].to_numpy(); g["ask"] = q["ask"].to_numpy()
    g["mid"] = (g["bid"] + g["ask"]) / 2
    g = g.dropna(subset=["bid", "ask"])
    g = g[(g["bid"] > 0) & (g["ask"] < 1)]

    n_snap = 0; mono_viol = 0; arb_ct = 0; arb_edge = []; arb_edge_net = []
    for (exp, off), grp in g.groupby(["expiry", "off"]):
        grp = grp.sort_values("strike")
        if len(grp) < 3:
            continue
        n_snap += 1
        mid = grp["mid"].to_numpy(); ask = grp["ask"].to_numpy(); bid = grp["bid"].to_numpy()
        # mid non-monotonicity: any higher strike with higher mid
        if np.any(np.diff(mid) > 1e-9):
            mono_viol += 1
        # crossable inversion: exists i<j with ask_i < bid_j (low strike ask below high strike bid)
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                edge = bid[j] - ask[i]          # credit from buy(i)/sell(j), payoff>=0
                if edge > 0:
                    arb_ct += 1
                    fee = fee_per_share(ask[i], 1000.0) + fee_per_share(bid[j], 1000.0)
                    arb_edge.append(edge); arb_edge_net.append(edge - fee)

    print(f"=== A: strike-ladder arbitrage ===")
    print(f"  snapshots (expiry x offset, >=3 strikes): {n_snap}")
    print(f"  MID non-monotonic snapshots: {mono_viol} ({mono_viol/max(n_snap,1):.1%})")
    print(f"  crossable ask/bid inversions (pure arb pre-fee): {arb_ct}")
    if arb_edge:
        ae = np.array(arb_edge); an = np.array(arb_edge_net)
        print(f"    pre-fee edge: mean={ae.mean():+.4f} max={ae.max():+.4f}")
        print(f"    POST-fee (2 legs @10%): profitable={int((an>0).sum())} "
              f"mean={an.mean():+.4f} max={an.max():+.4f} "
              f"-> {'ARB EDGE' if (an>0).sum()>0 else 'none after fees'}")
    else:
        print("    no crossable inversions at all -> ladder internally consistent")


if __name__ == "__main__":
    main()
