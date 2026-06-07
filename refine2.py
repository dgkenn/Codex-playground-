"""Further refinements of the inventory-capped 2-sided maker, on historical data.

R-A price-regime filter: quote only when token price is near 0.5 (rebate ~ p(1-p) is
    maximal there, and decided/extreme moments are the most toxic). By PRICE, not time.
R-B inventory skew: start quoting only the inventory-reducing side once |delta| exceeds
    skew_frac*cap (lean to flatten earlier than the hard cap).
Reuses refine_maker.load(); reports GROSS(no rebate)/NET(+rebate), IS/OOS, $, maxDD.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import refine_maker as rm
import fees

REBATE_RATE = 0.07


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def sim2(allt, res, cap, price_band=0.5, skew_frac=1.0):
    out = []
    for win, g in allt.groupby("win"):
        delta = up_inv = dn_inv = cash = reb = 0.0
        for tok, side, price, size, tau in g[["tok", "side", "price", "size", "tau"]].to_numpy():
            if abs(price - 0.5) > price_band:        # R-A: only quote near 0.5
                continue
            d_per = (-1.0 if (tok == "U") == (side == "BUY") else 1.0)
            # R-B inventory skew: if leaning past skew_frac*cap, only quote the reducing side
            if abs(delta) >= skew_frac * cap and (delta * d_per) > 0:
                continue
            fill = size
            if abs(delta + d_per * fill) > cap:
                room = max(0.0, cap - abs(delta)) if (delta + d_per * fill) * d_per > 0 else fill
                fill = min(fill, room)
            if fill <= 0:
                continue
            sells = (side == "BUY")
            cash += (price if sells else -price) * fill
            if tok == "U":
                up_inv += (-fill if sells else fill)
            else:
                dn_inv += (-fill if sells else fill)
            delta += d_per * fill
            reb += fees.maker_rebate(price, rate=REBATE_RATE) * fill
        r = res[win]
        out.append((win, cash + up_inv * r + dn_inv * (1 - r), reb, g["size"].sum()))
    d = pd.DataFrame(out, columns=["unit_id", "gross", "rebate", "vol"])
    d = d[d["vol"] > 0]
    d["ps_gross"] = d["gross"] / d["vol"]; d["ps_net"] = (d["gross"] + d["rebate"]) / d["vol"]
    return d


def report(name, d):
    mid = np.median(d["unit_id"])
    _, mg, tg = clt(d.ps_gross.to_numpy()); _, mn, tn = clt(d.ps_net.to_numpy())
    _, _, to = clt(d[d.unit_id >= mid].ps_net.to_numpy())
    seq = (d.sort_values("unit_id").gross + d.sort_values("unit_id").rebate).to_numpy()
    cum = np.cumsum(seq); dd = np.max(np.maximum.accumulate(cum) - cum) if len(seq) else 0
    print(f"  {name:30} GROSS t={tg:+5.2f}({mg:+.5f}) | NET t={tn:+5.2f} OOS={to:+5.2f} ps={mn:+.5f} "
          f"| $tot={seq.sum():+,.0f} maxDD=${dd:,.0f}")


def main():
    allt, res = rm.load()
    print(f"trades={len(allt)} windows={allt['win'].nunique()}\n")
    print("R-A price-regime filter (cap=20, quote only |price-0.5|<band):")
    for band in [0.5, 0.4, 0.3, 0.2, 0.15, 0.1]:
        report(f"band={band}", sim2(allt, res, cap=20, price_band=band))
    print("\nR-B inventory skew (cap=20, band=0.4, skew at frac*cap):")
    for sf in [1.0, 0.75, 0.5, 0.25]:
        report(f"skew_frac={sf}", sim2(allt, res, cap=20, price_band=0.4, skew_frac=sf))
    print("\nCombined best-guess (cap=20, band=0.35, skew=0.5):")
    report("combo", sim2(allt, res, cap=20, price_band=0.35, skew_frac=0.5))


if __name__ == "__main__":
    main()
