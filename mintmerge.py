"""ROADMAP #1 (new list): mint/merge -- the instrument's NATIVE collateral primitive, and the
capacity lever, with NO model risk.

To quote BOTH sides you SPLIT $1 of USDC collateral into 1 Up + 1 Down (mint a complete set)
and sell them into the book; the overround (Up_px+Down_px > $1) is the edge. When both legs
accumulate, a matched Up+Down pair is a COMPLETE SET worth exactly $1 at resolution -- you can
MERGE it back to $1 of collateral immediately instead of (a) holding it tying up capital or
(b) crossing the spread to flatten. Two capacity payoffs: free collateral to quote more size,
and never pay the spread to flatten the matched part.

This quantifies the collateral mint/merge frees in the deployed BTC skewed sim:
  collateral WITHOUT merge = peak gross legs held = max_t (|up_inv| + |dn_inv|)
  collateral WITH merge    = peak UNMATCHED only  = max_t |up_inv - dn_inv| = peak |net delta|
Since the maker is ~delta-neutral (skew), |net| << gross, so merge frees most of the capital ->
a direct multiple on quotable size (= on captured volume = on P&L, the binding constraint).

    python mintmerge.py
"""
from __future__ import annotations

import numpy as np

from fv_analysis import load_trades
from hedge_sim import replay


def main():
    allt = load_trades().sort_values(["win", "t_ms"])
    cols = {c: allt[c].to_numpy() for c in ("win", "tok", "side", "price", "size", "t_ms")}
    wa = allt.win.to_numpy(); o = np.arange(len(wa))
    bounds = {w: (o[wa == w][0], o[wa == w][-1] + 1) for w in np.unique(wa)}

    for cap in [50, 100, 200]:
        gross_peaks, net_peaks, ratios = [], [], []
        for w, (a, b) in bounds.items():
            g = {k: cols[k][a:b] for k in cols}
            _, _, ts, ups, dns, _, _ = replay(g, cap, skew_frac=0.25)
            up = np.abs(np.asarray(ups)); dn = np.abs(np.asarray(dns))
            gross = (up + dn)                                   # both legs held (no merge)
            net = np.abs(np.asarray(ups) - np.asarray(dns))    # unmatched (merge the rest)
            gp = gross.max() if len(gross) else 0.0
            npk = net.max() if len(net) else 0.0
            gross_peaks.append(gp); net_peaks.append(npk)
            if gp > 0:
                ratios.append(1 - npk / gp)
        gp = np.mean(gross_peaks); npk = np.mean(net_peaks); fr = np.mean(ratios)
        print(f"cap={cap:>3}: collateral/window if you never merge ~ cumulative gross legs "
              f"${gp:7.0f};  WITH continuous merge, bounded by peak |net delta| ${npk:5.0f} "
              f"(= the cap). merge holds collateral FLAT vs turnover.")
    print("\nHONEST framing (not a clean 'Nx size' multiple -- the gross figure is a sim artifact of "
          "letting inventory grow unbounded): the real claim is that mint/merge makes collateral a "
          "function of NET DELTA (~$cap), not of cumulative gross flow. Without it, a maker churning "
          "this turnover would need collateral that scales with volume; with it, ~$cap covers any "
          "turnover. That is what makes quoting at scale feasible on fixed capital -- it's REQUIRED "
          "for the live build, not an optional optimization, and it has no model risk (CTF "
          "split/merge, exact $1 conservation). Wired into live_trader as split_to_quote / "
          "merge_matched.")


if __name__ == "__main__":
    main()
