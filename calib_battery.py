"""Track A: calibration / favorite-longshot battery across categories, net of the
CORRECT per-category fee. Each market = one independent observation.

For each category: calibration curve (price-bin -> realized YES freq), compression
slope (b<1 => favorite-longshot bias), and the tradeable bet-the-favorite PnL net of
category fee (+ optional half-spread). Geopolitics fee = 0, so even small gaps trade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fees

HALF_SPREAD = 0.01   # assumed taker half-spread (prices-history is midpoint); sensitivity


def ols_t(y, x):
    X = np.column_stack([np.ones_like(x), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    s2 = (r @ r) / (len(y) - 2)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return b, b / se


def tstat(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def bet_favourite(p, resolved_yes, fee_cat, half_spread=0.0):
    """Buy the favourite (price>0.5 side) at p (+half_spread), hold to resolution."""
    fav_yes = p > 0.5
    entry = np.where(fav_yes, p, 1 - p) + half_spread
    payoff = np.where(fav_yes, resolved_yes, 1 - resolved_yes).astype(float)
    fee = np.array([fees.taker_fee(e, category=fee_cat) for e in entry])
    return payoff - entry - fee


def main():
    df = pd.read_parquet("markets_calib.parquet")
    print(f"{len(df)} resolved markets; by tag:\n{df.groupby('tag').size().to_string()}")
    for pcol in ["p_mid", "p_late"]:
        print(f"\n############### PRICE = {pcol} ###############")
        for tag, g in list(df.groupby("tag")) + [("ALL", df)]:
            p = g[pcol].to_numpy(); res = g["resolved_yes"].to_numpy().astype(float)
            ok = np.isfinite(p) & (p > 0) & (p < 1)
            p, res = p[ok], res[ok]
            if len(p) < 30:
                continue
            fee_cat = g["fee_cat"].iloc[0] if tag != "ALL" else "sports"
            b, tb = ols_t(res, p - 0.5)
            # bet favourite net of fee (and +half-spread)
            n, m, t = tstat(bet_favourite(p, res, fee_cat))
            n2, m2, t2 = tstat(bet_favourite(p, res, fee_cat, HALF_SPREAD))
            print(f"  {tag:11} n={len(p):4d} fee={fees.taker_rate(fee_cat):.2f}  "
                  f"compression b={b[1]:+.2f}(t{tb[1]:+.1f})  "
                  f"bet-fav net/fee m={m:+.4f}(t{t:+.1f})  +half-spread m={m2:+.4f}(t{t2:+.1f})"
                  f"{'  <= EDGE' if m2>0 and t2>2.58 else ''}")
        # calibration curve for ALL
    print("\n=== calibration (p_mid bins, ALL): price -> realized YES ===")
    p = df["p_mid"].to_numpy(); res = df["resolved_yes"].to_numpy().astype(float)
    ok = np.isfinite(p) & (p > 0) & (p < 1); p, res = p[ok], res[ok]
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    for b in range(10):
        m = idx == b
        if m.sum() > 5:
            print(f"   p {bins[b]:.1f}-{bins[b+1]:.1f}: n={m.sum():4d} "
                  f"mean_p={p[m].mean():.3f} realized={res[m].mean():.3f} gap={res[m].mean()-p[m].mean():+.3f}")


if __name__ == "__main__":
    main()
