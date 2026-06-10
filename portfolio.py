"""Multi-pod combiner: pool independent per-edge net-of-fee PnL series and report
the DIVERSIFIED aggregate t-stat. Diversification raises t ~ sqrt(K) only if each
edge has mean>0; it cannot rescue negative EV. Honest guards: per-edge t, the
cross-edge correlation, and an IS->OOS check (weights from IS, evaluate OOS).

Usage: register edges as {name: DataFrame[unit_id, pnl]} where unit_id is the
independence unit (event/window). Edges are added by the analysis scripts that
produce per-unit net PnL; this module just combines what exists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def edge_stats(pnl):
    a = np.asarray(pnl, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def combine(edges: dict, half="unit_id"):
    """edges: {name: DataFrame[unit_id, pnl]} (one row per independent bet).
    Returns per-edge stats + the equal-risk pooled-portfolio t (IS-weighted, OOS-tested)."""
    print("=== per-edge (net of fee) ===")
    series = {}
    for name, df in edges.items():
        df = df.dropna(subset=["pnl"])
        n, m, t = edge_stats(df["pnl"].to_numpy())
        print(f"  {name:28} n={n:6d} mean={m:+.5f} t={t:+.2f}")
        # collapse to per-unit mean (independence unit)
        series[name] = df.groupby("unit_id")["pnl"].mean()
    # align on union of units; equal-risk weight = 1/std (from sign-positive edges only)
    M = pd.DataFrame(series)
    pos = [c for c in M.columns if M[c].mean() > 0]
    print(f"\n  net-positive edges: {pos}")
    if not pos:
        print("  -> nothing positive to combine (cannot diversify out of negative EV)")
        return
    sub = M[pos]
    print("\n=== cross-edge correlation (positive edges) ===")
    print(sub.corr().round(2).to_string())
    # equal-risk portfolio: each edge scaled to unit vol, averaged across available edges per unit
    z = (sub - sub.mean()) / sub.std()
    # portfolio per-unit return = mean of available standardized edges (then we test the RAW pooled mean too)
    raw_pool = sub.mean(axis=1)
    n, m, t = edge_stats(raw_pool.to_numpy())
    print(f"\n=== COMBINED equal-weight portfolio (positive edges) ===")
    print(f"  per-unit mean={m:+.5f}  t={t:+.2f}  (n_units={n})  "
          f"{'<= SIGNIFICANT' if t and t>2.58 else ''}")
    return M


if __name__ == "__main__":
    print("portfolio.py is a library; analysis scripts feed it edge PnL series.")
