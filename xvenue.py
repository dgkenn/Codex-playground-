"""xvenue.py -- Polymarket vs Kalshi on the SAME 15-min windows: divergence, lock-arb, lead-lag.

Both venues run btc-up-in-15-min on identical window grids (PM settles Chainlink/Binance, Kalshi
settles CF Benchmarks -- near-identical indices). Joining the two 1-min mid histories tests a class
the single-venue scans cannot see:
  1. SETTLEMENT AGREEMENT: do the two venues ever resolve the same window differently? (index basis
     risk = the tail risk of any cross-venue position)
  2. DIVERGENCE: |mid_PM - mid_K| distribution by minute -- is there anything to arb?
  3. LOCKED BOX: buy YES on the cheap venue + NO on the rich venue; profit = 1 - total cost when
     outcomes agree. Costs: both venues' taker fees (PM ~0.07*p(1-p)*scale via fees.py analog;
     Kalshi quadratic) + half-spreads. Frequency and size of net-positive locks.
  4. LEAD-LAG: does one venue's mid move predict the other's NEXT move? (the maker expression:
     fee-free skew on the lagging venue.)        python xvenue.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K_FEE = lambda p: 0.07 * p * (1 - p)            # Kalshi quadratic taker fee
PM_FEE = lambda p: 0.07 * p * (1 - p) * 3.0     # PM peak taker schedule (~3x at p=.5 -> ~5c) conservative
HALF = 0.005


def main():
    pm = pd.read_parquet("hist_btc15m.parquet").set_index("ws")
    ka = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
    common = sorted(set(pm.index) & set(ka.index))
    print(f"overlapping windows: {len(common)}")
    pm_m = np.stack(pm.loc[common].mid_path.to_numpy())
    ka_m = np.stack(ka.loc[common].mid_path.to_numpy())
    ka_b = np.stack(ka.loc[common].bid_path.to_numpy())
    ka_a = np.stack(ka.loc[common].ask_path.to_numpy())
    pm_r = pm.loc[common].res_up.to_numpy(float)
    ka_r = ka.loc[common].res_up.to_numpy(float)

    agree = float(np.mean(pm_r == ka_r))
    print(f"\n[1] settlement agreement: {agree*100:.2f}%  "
          f"({int(np.sum(pm_r != ka_r))} disagreements of {len(common)})")

    d = pm_m - ka_m
    with np.errstate(all="ignore"):
        print(f"\n[2] divergence |mid_PM - mid_K| by minute (mean / p90 / p99, cents):")
        for k in (2, 5, 8, 11, 13):
            x = np.abs(d[:, k]); x = x[~np.isnan(x)]
            if len(x) > 50:
                print(f"   min {k:>2}: {np.mean(x)*100:5.2f} / {np.percentile(x,90)*100:5.2f} / "
                      f"{np.percentile(x,99)*100:5.2f}  (n={len(x)})")

    # [3] locked box, scanned per minute: buy K YES at ask_K + buy PM NO at (1-mid_PM+HALF)
    #     or buy PM YES at (mid_PM+HALF) + buy K NO at (1-bid_K). Net of both fees.
    print(f"\n[3] locked-box opportunities (net of fees+spreads), per minute scanned:")
    locks = 0; tot = 0; pnl_sum = 0.0
    for k in range(2, 14):
        kb, kaa, pmm = ka_b[:, k], ka_a[:, k], pm_m[:, k]
        ok = ~(np.isnan(kb) | np.isnan(kaa) | np.isnan(pmm))
        # K cheap: buy K YES @ ask, buy PM NO @ 1-(pm_bid)=1-pmm+HALF
        cost1 = kaa + (1 - pmm + HALF) + K_FEE(kaa) + PM_FEE(1 - pmm)
        # PM cheap: buy PM YES @ pmm+HALF, buy K NO @ 1-kb
        cost2 = (pmm + HALF) + (1 - kb) + PM_FEE(pmm) + K_FEE(1 - kb)
        prof = np.maximum(1 - cost1, 1 - cost2)
        sel = ok & (prof > 0)
        locks += int(sel.sum()); tot += int(ok.sum())
        pnl_sum += float(prof[sel].sum())
    print(f"   net-positive locks: {locks}/{tot} minute-slots scanned "
          f"({100*locks/max(tot,1):.3f}%), total locked P&L if all taken: {pnl_sum*100:.1f}c")

    # [4] venue lead-lag: does the PM-K gap at minute k predict K's mid change k->k+1 (and vice versa)?
    print(f"\n[4] lead-lag (corr of gap_k with next-minute move):")
    dk = ka_m[:, 1:] - ka_m[:, :-1]
    dp = pm_m[:, 1:] - pm_m[:, :-1]
    gap = d[:, :-1]
    def cc(a, b):
        m = ~(np.isnan(a) | np.isnan(b))
        return np.corrcoef(a[m], b[m])[0, 1] if m.sum() > 100 else float("nan"), int(m.sum())
    c1, n1 = cc(gap.ravel(), dk.ravel())
    c2, n2 = cc(-gap.ravel(), dp.ravel())
    print(f"   gap -> K next move: corr {c1:+.3f} (n={n1})   [>0: K converges toward PM = PM leads]")
    print(f"   -gap -> PM next move: corr {c2:+.3f} (n={n2})  [>0: PM converges toward K = K leads]")


if __name__ == "__main__":
    main()
