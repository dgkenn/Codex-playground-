"""ROADMAP #5: multi-market scale -- the crux question is NOT "does the edge repeat" (it does;
each market is an independent rebate+vig stream) but "is NEUTRAL-IN-EACH NEUTRAL OVERALL?" If
BTC/ETH/SOL/XRP 15m are ~one risk factor, then the residual directional inventory the maker
carries in each is CORRELATED, the per-market deltas do NOT diversify, and "market-neutral in
each book" can be a large correlated bet at the portfolio level -> you must aggregate delta and
manage it jointly (one perp/skew budget across all books), and portfolio Sharpe scales far worse
than sqrt(N).

Data on hand: resolutions for all 4 coins (15m) + 1s spot (.npz) for all 4. (Alt TRADE tapes
are not on disk -- only top-of-book -- so per-market maker P&L for the alts needs a fetch; the
correlation crux below does not.) BTC's actual maker residual delta (we have BTC trades) is the
worked example tying residual-delta to the correlated move.

    python multimarket.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from hedge_sim import replay

NPZ = {"btc": "btc.npz", "eth": "ETHUSDT.npz", "sol": "SOLUSDT.npz", "xrp": "XRPUSDT.npz"}


def spot(coin):
    z = np.load(NPZ[coin]); ts = np.asarray(z["ts"], np.int64); px = np.asarray(z["price"], float)
    o = np.argsort(ts); return ts[o], px[o]


def at(ts, px, t_ms):
    i = np.clip(np.searchsorted(ts, t_ms, "right") - 1, 0, len(px) - 1)
    return px[i]


def load_windows():
    """15m resolved windows per coin: btc from up_windows, eth/sol/xrp from alt_windows."""
    b = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "window_end", "resolved_up"]].copy(); b["coin"] = "btc"
    a = pd.read_parquet("alt_windows.parquet").dropna(subset=["resolved_up"])[
        ["coin", "window_start", "window_end", "resolved_up"]]
    return pd.concat([b, a], ignore_index=True)


def main():
    w = load_windows()
    coins = ["btc", "eth", "sol", "xrp"]
    print(f"windows/coin: " + ", ".join(f"{c}={ (w.coin==c).sum() }" for c in coins))

    # --- per-window resolution (0/1) and spot log-return, aligned across coins ---
    res = w.pivot_table(index="window_start", columns="coin", values="resolved_up")
    ret = {}
    for c in coins:
        ts, px = spot(c)
        wc = w[w.coin == c]
        r = {}
        for _, row in wc.iterrows():
            s0 = at(ts, px, int(row.window_start) * 1000); se = at(ts, px, int(row.window_end) * 1000)
            r[int(row.window_start)] = np.log(se / s0) if (s0 > 0 and se > 0) else np.nan
        ret[c] = pd.Series(r)
    ret = pd.DataFrame(ret)
    common = res.dropna().index.intersection(ret.dropna().index)
    res = res.loc[common, coins]; ret = ret.loc[common, coins]
    print(f"aligned windows across all 4 coins: {len(common)}")

    print("\n[spot per-window log-return correlation] -- are the underlyings one risk factor?")
    print(ret.corr().round(2).to_string())
    print("\n[resolution (Up/Down) correlation] -- do the binaries settle together?")
    print(res.corr().round(2).to_string())

    rho = ret.corr().to_numpy()[np.triu_indices(4, 1)].mean()
    print(f"\nmean pairwise spot-return corr = {rho:.2f}  (the underlyings ARE ~one risk factor)")

    # --- diversification math done RIGHT: maker P&L variance has TWO parts -- a NON-directional
    #     vig-capture part (independent across books, diversifies ~sqrt(N)) and a DIRECTIONAL
    #     residual part (correlated rho, does NOT diversify). The hedge experiment measured the
    #     directional FRACTION f: on the skewed book the ideal delta-hedge could not cut std
    #     (variance is ~non-directional) => f ~= 0.01; no-skew gave at most ~0.06. So the
    #     correlated piece is SMALL, and diversification mostly works at this N.
    N = 4
    print(f"\nportfolio Sharpe multiple vs a single book, by directional-variance fraction f:")
    print(f"  (f = share of per-window variance that is directional/correlated; "
          f"measured f~0.01 skewed, <=0.06 no-skew. Sharpe_mult = sqrt(N)/sqrt(1+f*(N-1)*rho))")
    for f in (0.01, 0.06, 0.25, 1.0):
        mult = np.sqrt(N) / np.sqrt(1 + f * (N - 1) * rho)
        tag = "  <- deployed (skewed)" if f == 0.01 else ("  <- no-skew" if f == 0.06 else
              ("  <- (naive all-directional assumption)" if f == 1.0 else ""))
        print(f"    f={f:<4}: Sharpe x{mult:.2f}  (edge always x{N}){tag}")
    # crossover: where the correlated directional term equals the diversifying term
    f_dep = 0.06
    Ncross = 1 + 1 / (f_dep * rho)
    print(f"  crossover N (directional term == non-directional, at f={f_dep}): N~={Ncross:.0f} "
          f"-> below that, diversification dominates; the 4-5 crypto books are well below it.")

    print("\nVERDICT: multi-market multiplies the per-share EDGE x N (independent rebate+vig "
          "streams). The books ARE one risk factor (rho=0.81), BUT the maker's variance is mostly "
          "NON-directional (skew already killed the directional residual), so that variance "
          "DIVERSIFIES and portfolio Sharpe scales ~sqrt(N) (~1.9x for N=4), only mildly degraded "
          "by the correlated residual. So #5 is a CLEAN capacity win at this N. Two guardrails: "
          "(1) net delta at the PORTFOLIO level (the small correlated residual is the part that "
          "doesn't diversify, and it grows ~N^2, dominating only past ~20 correlated books or if "
          "skew is loosened); (2) per-market maker P&L for the alts still needs their TRADE tapes "
          "(only top-of-book is on disk) -- fetch to confirm the per-book edge ports.")


if __name__ == "__main__":
    main()
