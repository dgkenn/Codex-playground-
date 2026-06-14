#!/usr/bin/env python3
"""
etf_outcome_dist.py — block-bootstrap outcome distribution + sizing for the
LOCKED cross-asset ETF momentum strategy (ETF_MOMENTUM.md). Reuses the validated
engine in etf_momentum.py; does NOT re-optimize.

Method:
  1. Run the locked-config backtest (DUAL+regime, 6m, K=5, partial=0.34) on the
     full sample to get the daily NET return series; aggregate to MONTHLY.
  2. HAIRCUT the historical monthly mean by ~30% (forward realism: published
     edge decay + live slippage). Keep the full vol/shape (fat tails preserved).
  3. STATIONARY BLOCK BOOTSTRAP of the monthly series (block ~6 months) to
     preserve autocorrelation / vol-clustering. 20k paths over 12/24/36 months.
  4. Report terminal-wealth p5/p25/median/p75/p95 at $1k and $10k; P(maxDD>20/30%);
     time-underwater distribution; P(below starting capital at 2yr);
     P(underperform SPY over 2yr). Base AND crypto-proxy variants.
  5. SIZING: translate "size small" into %-of-net-worth at a stated risk tolerance
     so a 1-in-20 (p5) path is a tolerable $ loss.

Run: python3 etf_outcome_dist.py   (prints a report; data from /tmp/etfmom_data)
"""
import numpy as np
import pandas as pd

from etf_momentum import (load_prices, backtest, buyhold, CORE_UNIVERSE,
                          CRYPTO_PROXY)

HAIRCUT = 0.30           # shave 30% off the historical mean for forward realism
BLOCK = 6                # ~6-month blocks (months) for the stationary bootstrap
N_PATHS = 20000
HORIZONS = {"1yr": 12, "2yr": 24, "3yr": 36}
RNG = np.random.default_rng(20260614)
FULL_START = "2000-06-01"
CRYPTO_START = "2016-01-01"   # crypto-proxy variant only has history from 2016


def monthly_returns(net_daily):
    """Aggregate a daily net-return series to monthly compounded returns."""
    eq = (1 + net_daily).cumprod()
    m = eq.resample("ME").last()
    mret = m.pct_change().dropna()
    return mret


def haircut_series(mret, haircut=HAIRCUT):
    """Subtract `haircut` * historical mean from every month (shifts mean down,
    preserves vol and higher moments / fat tails)."""
    shift = haircut * mret.mean()
    return mret - shift


def stationary_block_bootstrap(mret, n_months, n_paths=N_PATHS, mean_block=BLOCK):
    """Stationary bootstrap (Politis-Romano): geometric block lengths with mean
    `mean_block`, wrapping. Returns an (n_paths, n_months) array of monthly rets."""
    x = mret.values
    n = len(x)
    p = 1.0 / mean_block
    out = np.empty((n_paths, n_months))
    for i in range(n_paths):
        t = 0
        while t < n_months:
            start = RNG.integers(0, n)
            # geometric block length >=1
            L = RNG.geometric(p)
            for j in range(L):
                if t >= n_months:
                    break
                out[i, t] = x[(start + j) % n]
                t += 1
    return out


def path_stats(paths):
    """Given (n_paths, n_months) monthly rets, return wealth multiple and the
    in-path max drawdown + time-underwater (months) for each path."""
    eq = np.cumprod(1 + paths, axis=1)
    eq = np.concatenate([np.ones((eq.shape[0], 1)), eq], axis=1)  # start at 1.0
    running_max = np.maximum.accumulate(eq, axis=1)
    dd = eq / running_max - 1.0
    maxdd = dd.min(axis=1)
    underwater = (dd < -1e-9).sum(axis=1)            # months spent below a prior peak
    terminal = eq[:, -1]
    return terminal, maxdd, underwater


def pct(a, q):
    return float(np.percentile(a, q))


def describe(mret_hc, label, spy_monthly=None):
    print("\n" + "=" * 78)
    print(f"  OUTCOME DISTRIBUTION — {label}")
    print(f"  (haircut {int(HAIRCUT*100)}% of mean; stationary block bootstrap, "
          f"block~{BLOCK}mo, {N_PATHS:,} paths)")
    print("=" * 78)
    ann_mean = (1 + mret_hc.mean())**12 - 1
    ann_vol = mret_hc.std() * np.sqrt(12)
    sharpe = ann_mean / ann_vol if ann_vol else float("nan")
    print(f"  post-haircut: ann.mean {ann_mean*100:.1f}%  ann.vol {ann_vol*100:.1f}%  "
          f"Sharpe(0%rf) {sharpe:.2f}   (n={len(mret_hc)} months)")

    for hname, months in HORIZONS.items():
        paths = stationary_block_bootstrap(mret_hc, months)
        terminal, maxdd, underwater = path_stats(paths)
        print(f"\n  --- {hname} ({months} months) ---")
        for cap in (1000, 10000):
            ps = {q: cap * pct(terminal, q) for q in (5, 25, 50, 75, 95)}
            print(f"    terminal wealth @ ${cap:>6,}: "
                  f"p5 ${ps[5]:>8,.0f} | p25 ${ps[25]:>8,.0f} | "
                  f"median ${ps[50]:>8,.0f} | p75 ${ps[75]:>8,.0f} | "
                  f"p95 ${ps[95]:>9,.0f}")
        p_dd20 = float((maxdd < -0.20).mean())
        p_dd30 = float((maxdd < -0.30).mean())
        print(f"    P(maxDD > 20%): {p_dd20*100:5.1f}%   "
              f"P(maxDD > 30%): {p_dd30*100:5.1f}%")
        uw = underwater / months
        print(f"    time underwater (frac of horizon): "
              f"median {pct(uw,50)*100:4.0f}% | p75 {pct(uw,75)*100:4.0f}% | "
              f"p95 {pct(uw,95)*100:4.0f}%")
        if hname == "2yr":
            p_below = float((terminal < 1.0).mean())
            print(f"    P(below starting capital at 2yr): {p_below*100:.1f}%")
            if spy_monthly is not None and len(spy_monthly) > months:
                spy_paths = stationary_block_bootstrap(spy_monthly, months)
                spy_term, _, _ = path_stats(spy_paths)
                # paired comparison via independent draws (both bootstrapped)
                p_under = float((terminal < spy_term).mean())
                print(f"    P(underperform SPY over 2yr, both bootstrapped): "
                      f"{p_under*100:.1f}%")
    return terminal  # last horizon's terminal (3yr) unused by caller


def sizing_block(mret_hc, label, historical_maxdd, nw_examples=(50000, 200000)):
    """Translate worst-case loss into a %-of-net-worth guideline.

    We size off the MORE CONSERVATIVE of: the bootstrap p5 (1-in-20) intra-path
    drawdown over 2yr, and the documented HISTORICAL full-sample maxDD. A 2yr
    window rarely contains the full 26yr historical crash, so using the bootstrap
    p5 alone would understate tail risk; the historical maxDD is the honest floor.
    """
    paths = stationary_block_bootstrap(mret_hc, 24)
    terminal, maxdd, _ = path_stats(paths)
    p5_term = pct(terminal, 5)
    p5_loss = max(0.0, 1.0 - p5_term)
    p5_dd = -pct(maxdd, 5)
    # size off the worst of bootstrap-p5-DD and historical maxDD (honest tail)
    risk_dd = max(p5_dd, historical_maxdd)
    print("\n" + "-" * 78)
    print(f"  SIZING — {label}")
    print("-" * 78)
    print(f"  1-in-20 (p5) 2yr terminal multiple : {p5_term:.2f}  "
          f"=> {p5_loss*100:.0f}% loss on the allocated sleeve at 2yr")
    print(f"  1-in-20 (p5) bootstrap 2yr drawdown: {p5_dd*100:.0f}%")
    print(f"  historical full-sample max drawdown: {historical_maxdd*100:.0f}%")
    print(f"  -> SIZE off the worst case: a {risk_dd*100:.0f}% peak-to-trough "
          f"loss on the allocated sleeve.")
    print(f"  Guideline: if you can stomach losing T% of NET WORTH at the bottom "
          f"of a bad run,")
    print(f"      allocation %NW = T% / {risk_dd*100:.0f}%  (e.g. tolerate 5% NW "
          f"loss -> allocate {5/(risk_dd*100)*100:.0f}% of NW)")
    for nw in nw_examples:
        for tol in (0.05, 0.10):
            L = tol * nw
            A = min(L / risk_dd, nw) if risk_dd > 0 else nw
            print(f"      net worth ${nw:>7,}, tolerate {int(tol*100)}% NW loss "
                  f"(${L:,.0f}) -> allocate ${A:,.0f} ({A/nw*100:.0f}% of NW)")
    return p5_loss, risk_dd


def main():
    px = load_prices()

    # --- BASE: locked config, full sample ---
    net_base, _ = backtest(px, CORE_UNIVERSE, lookback_days=126, K=5,
                           risk_adj=True, dual=True, regime=True, partial=0.34,
                           start=FULL_START)
    mret_base = monthly_returns(net_base)
    mret_base_hc = haircut_series(mret_base)

    spy_m = monthly_returns(buyhold(px, "SPY", start=FULL_START))

    print("#" * 78)
    print("#  ETF CROSS-ASSET MOMENTUM — FORWARD OUTCOME DISTRIBUTION (LOCKED CFG)")
    print("#  base config: DUAL+regime, 6m, K=5, partial=0.34, net of 3bps/side")
    print("#" * 78)

    describe(mret_base_hc, "BASE (core ~30 ETFs), full-sample monthly", spy_m)
    sizing_block(mret_base_hc, "BASE", historical_maxdd=0.18)

    # --- CRYPTO-PROXY variant: 2016+ only (that is when proxies exist) ---
    net_cp, _ = backtest(px, CORE_UNIVERSE + CRYPTO_PROXY, lookback_days=126, K=5,
                         risk_adj=True, dual=True, regime=True, partial=0.34,
                         start=CRYPTO_START)
    mret_cp = monthly_returns(net_cp)
    mret_cp_hc = haircut_series(mret_cp)
    spy_m_recent = monthly_returns(buyhold(px, "SPY", start=CRYPTO_START))

    describe(mret_cp_hc, "CRYPTO-PROXY (core + IBIT/MSTR/COIN/GBTC), 2016+ monthly "
                         "[SHORT HISTORY]", spy_m_recent)
    sizing_block(mret_cp_hc, "CRYPTO-PROXY", historical_maxdd=0.18)

    print("\n" + "#" * 78)
    print("#  NOTE: crypto-proxy stats use 2016+ only (proxies have short history) "
          "and\n#  inherit a fat upside; treat the crypto numbers as SUGGESTIVE.")
    print("#" * 78)


if __name__ == "__main__":
    main()
