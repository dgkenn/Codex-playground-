"""Per-category Polymarket fee + rebate model (V2 schedule, docs 2026).

fee_usdc_per_share = feeRate * p * (1-p)   (symmetric around 0.5; crypto p=0.5 -> 0.0175)
Makers are never charged (maker fee = 0) and earn a category rebate (~20-25% of the
taker fees their liquidity generates). Takers earn a tiered rebate by 30-day volume.

NOTE on the data discrepancy: the CLOB market object and the archive both report
taker_base_fee = 1000 bps (0.10) for the April-2026 15-min crypto markets, while the
current docs list crypto taker = 0.07. The maker_base_fee=1000 contradicts "makers
never charged", so those are nominal/legacy fields; the V2 effective rates below are
authoritative. We treat 0.07 as primary and expose 0.10 as a conservative sensitivity.
"""
from __future__ import annotations

import numpy as np

# V2 taker fee rate by category (fraction)
TAKER_RATE = {
    "crypto": 0.07, "sports": 0.03, "finance": 0.04, "politics": 0.04,
    "tech": 0.04, "mentions": 0.04, "economics": 0.05, "culture": 0.05,
    "weather": 0.05, "other": 0.05, "geopolitics": 0.0, "world": 0.0,
}
MAKER_REBATE_SHARE = {"crypto": 0.20}  # 25% for everything else
DATA_OBSERVED_RATE = 0.10              # what the CLOB/archive field reports for 15m crypto

# Taker rebate tiers: 30-day weighted-volume threshold -> fraction of fee returned
TAKER_REBATE_TIERS = [(0, 0.0), (2_000, 0.03), (20_000, 0.08), (200_000, 0.18),
                      (1_000_000, 0.32), (4_000_000, 0.44), (10_000_000, 0.50)]


def taker_rate(category):
    return TAKER_RATE.get((category or "other").lower(), 0.05)


def taker_fee(price, category="crypto", rate=None, taker_rebate=0.0):
    """USDC fee per share for a taker (>=0). `rate` overrides the category rate
    (e.g. 0.10 for the conservative data-observed band). `taker_rebate` in [0,1]."""
    r = taker_rate(category) if rate is None else rate
    price = np.asarray(price, dtype=float)
    f = r * price * (1.0 - price) * (1.0 - taker_rebate)
    return float(f) if f.ndim == 0 else f


def maker_fee(price, category="crypto"):
    """Makers are never charged."""
    price = np.asarray(price, dtype=float)
    z = np.zeros_like(price)
    return float(z) if z.ndim == 0 else z


def maker_rebate(price, category="crypto", rate=None):
    """Per-matched-share maker rebate ~= rebate_share * taker_fee_generated."""
    r = taker_rate(category) if rate is None else rate
    share = MAKER_REBATE_SHARE.get((category or "other").lower(), 0.25)
    price = np.asarray(price, dtype=float)
    f = share * r * price * (1.0 - price)
    return float(f) if f.ndim == 0 else f


def taker_rebate_for_volume(vol_30d):
    reb = 0.0
    for thr, r in TAKER_REBATE_TIERS:
        if vol_30d >= thr:
            reb = r
    return reb


if __name__ == "__main__":
    # unit check vs docs fee tables (per 100 shares)
    for cat, exp in [("crypto", 1.75), ("sports", 0.75), ("politics", 1.00),
                     ("economics", 1.25), ("geopolitics", 0.0)]:
        got = taker_fee(0.5, cat) * 100
        print(f"{cat:11} p=0.5 -> ${got:.2f}/100sh (docs ${exp:.2f})  "
              f"{'OK' if abs(got-exp) < 0.01 else 'MISMATCH'}")
    print("conservative crypto (0.10):", taker_fee(0.5, rate=0.10) * 100, "/100sh")
