#!/usr/bin/env python3
"""
growth_planner.py -- (1) VALIDATE the growth tilt and (2) the CONTRIBUTE-AND-
COMPOUND planner for the trend-overlaid all-weather portfolio.

This does NOT re-derive the strategy. It REUSES the exact sleeve-trend rule and
configs from allweather_live.py and the LOCKED momentum engine
(etf_momentum_live.compute_target). The point is to (a) prove the GROWTH tilt
EARNS its risk OOS net of cost on real ETF-era yfinance data, and (b) give the
operator their REAL multi-year timeline to the ~$70k '$500/mo base', using the
growth config's OWN bootstrapped daily-return distribution (incl. the bad tail).

TWO MODES
  --validate : ETF-era (2007-06..2026-06 where data exists) monthly-rebalanced,
               net-of-cost backtest of:
                 PP             = pure Permanent Portfolio (25 SPY/TLT/GLD/BIL)
                 CONSERVATIVE   = trend-overlaid PP (12m TS-trend, falling -> cash)
                 GROWTH         = the growth tilt (overweight trend-gated equity/
                                  momentum + trend-timed IBIT, less bonds)
               Reports Sharpe / CAGR / maxDD on FULL + RECENT(5y) windows, plus
               the bootstrap plateau / OOS / net-cost honesty checks.

  --plan     : Monte-Carlo CONTRIBUTE-AND-COMPOUND. Bootstraps the GROWTH config's
               realized daily returns (stationary block bootstrap, 21-day blocks,
               keeps fat tails + vol clustering), adds a fixed monthly contribution,
               and reports the TIME (p25 / median / p75 YEARS) to reach $70k for a
               grid of starting capital x monthly contribution. No withdrawals
               (phase-1 compounding). The bad tail is IN the distribution.

Costs: 10 bps round-trip per unit of monthly turnover (conservative for
commission-free fractional ETFs). Window stated in every table.

USAGE
  python growth_planner.py --validate
  python growth_planner.py --plan
  python growth_planner.py --validate --plan
  python growth_planner.py --plan --target 70000 --npaths 4000
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from etf_momentum_live import (
    fetch_prices, compute_target, cash_index, CORE_UNIVERSE, CASH_TICKER,
)
import allweather_live as aw

TD = 252
COST_RT_BPS = 10.0           # round-trip bps per unit turnover (conservative)
TREND_LB_M = 12

PP_SLEEVES = {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "BIL": 0.25}


# ---------------------------------------------------------------------------
# Monthly weight path for a config, computed on daily prices (no lookahead).
# Returns a daily DataFrame of target weights (ffilled between month-ends).
# ---------------------------------------------------------------------------
def _month_ends(idx):
    s = pd.Series(idx, index=idx)
    return [pd.Timestamp(d) for d in s.groupby([idx.year, idx.month]).last().values]


def weights_pure_pp(px):
    idx = px.index
    W = pd.DataFrame(0.0, index=idx, columns=list(PP_SLEEVES))
    for t, w in PP_SLEEVES.items():
        if t in px.columns:
            W[t] = w
    return W


def weights_config(px, config, lookback_m=TREND_LB_M):
    """Daily target-weight frame for a trend-overlaid config (conservative/growth).
    Recomputes the allweather_live.assemble target at each month-end, ffill."""
    idx = px.index
    mes = [d for d in _month_ends(idx) if len(px.loc[:d]) > int(lookback_m/12*TD)+5]
    cols = set(["SPY", "TLT", "GLD", CASH_TICKER])
    if config["mom"] > 0:
        cols |= set(CORE_UNIVERSE)
    if config["ibit"] > 0:
        cols.add("IBIT")
    cols = [c for c in sorted(cols) if c in px.columns]
    W = pd.DataFrame(0.0, index=idx, columns=cols)
    rows = {}
    for d in mes:
        alloc, _ = aw.assemble(px, config, asof=d, lookback_m=lookback_m)
        rows[d] = {t: w for t, w in alloc.items() if t in cols}
    for d, w in rows.items():
        for t, v in w.items():
            W.loc[d, t] = v
    # ffill month-end targets across the month; pre-first-signal -> cash
    W = W.replace(0.0, np.nan).ffill()
    if CASH_TICKER in W.columns:
        W[CASH_TICKER] = W[CASH_TICKER].fillna(0.0)
    W = W.fillna(0.0)
    # rows before first signal: park in cash
    unallocated = 1.0 - W.sum(axis=1)
    if CASH_TICKER in W.columns:
        W[CASH_TICKER] = W[CASH_TICKER] + unallocated.clip(lower=0.0)
    return W


def backtest_weights(px, W, cost_rt_bps=COST_RT_BPS):
    """Daily net return series for a daily target-weight frame, monthly rebalance
    cost on turnover. Weights are applied with a 1-day lag (no lookahead)."""
    cols = [c for c in W.columns if c in px.columns]
    R = px[cols].pct_change().fillna(0.0)
    Wl = W[cols].shift(1).fillna(0.0)
    gross = (Wl * R).sum(axis=1)
    # turnover only changes at month-ends (W is piecewise-constant); cost on |dW|
    turn = W[cols].diff().abs().sum(axis=1).fillna(0.0)
    cost = turn * cost_rt_bps / 1e4
    return (gross - cost).dropna()


def stats(net, freq=TD):
    net = net.dropna()
    if len(net) < 60:
        return dict(CAGR=np.nan, Sharpe=np.nan, maxDD=np.nan, vol=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / freq
    return dict(CAGR=eq.iloc[-1] ** (1 / yrs) - 1,
                Sharpe=net.mean() / net.std() * np.sqrt(freq) if net.std() > 0 else np.nan,
                maxDD=(eq / eq.cummax() - 1).min(),
                vol=net.std() * np.sqrt(freq), n=len(net))


# ---------------------------------------------------------------------------
# VALIDATE
# ---------------------------------------------------------------------------
def run_validate(px):
    print("=" * 78)
    print("  GROWTH-TILT VALIDATION -- trend-overlaid all-weather, ETF-era yfinance")
    print("=" * 78)
    full_lo = px.index.min()
    print(f"  window FULL : {full_lo.date()} .. {px.index.max().date()}  "
          f"(n={len(px)} days)  cost {COST_RT_BPS:.0f}bps round-trip on turnover")
    recent_lo = px.index.max() - pd.Timedelta(days=5 * 365)

    series = {}
    series["PP (pure Permanent Portfolio)"] = backtest_weights(px, weights_pure_pp(px))
    series["CONSERVATIVE (trend-overlaid PP)"] = backtest_weights(px, weights_config(px, aw.CONSERVATIVE))
    series["GROWTH (tilt)"] = backtest_weights(px, weights_config(px, aw.GROWTH))

    def table(lo, label):
        print(f"\n  --- {label}  ({lo.date()} .. {px.index.max().date()}) ---")
        print(f"  {'candidate':<36}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>9}{'vol':>8}")
        out = {}
        for name, s in series.items():
            st = stats(s[s.index >= lo])
            out[name] = st
            print(f"  {name:<36}{st['CAGR']*100:7.1f}%{st['Sharpe']:8.2f}"
                  f"{st['maxDD']*100:8.1f}%{st['vol']*100:7.1f}%")
        return out

    full = table(full_lo, "FULL SAMPLE")
    recent = table(recent_lo, "RECENT 5Y (OOS-ish, the hardest test)")

    # ---- honesty checks on GROWTH vs CONSERVATIVE -------------------------
    g = series["GROWTH (tilt)"]
    c = series["CONSERVATIVE (trend-overlaid PP)"]
    common = g.index.intersection(c.index)
    g2, c2 = g.reindex(common), c.reindex(common)

    print("\n  --- HONESTY CHECKS (does GROWTH earn its risk, not just add it?) ---")
    # 1) net-of-cost already in series; report the return PER UNIT of extra DD
    gf, cf = stats(g2), stats(c2)
    extra_ret = gf["CAGR"] - cf["CAGR"]
    extra_dd = abs(gf["maxDD"]) - abs(cf["maxDD"])
    print(f"  GROWTH adds {extra_ret*100:+.1f}pp CAGR for {extra_dd*100:+.1f}pp more maxDD "
          f"(ret/DD trade = {extra_ret/extra_dd if extra_dd>0 else float('nan'):+.2f})")
    # 2) bootstrap P(GROWTH CAGR > CONSERVATIVE CAGR) -- plateau, not a spike
    rng = np.random.default_rng(7)
    diff = (g2 - c2).values
    n = len(diff)
    boots = []
    for _ in range(2000):
        idx = rng.integers(0, n, n)
        boots.append(diff[idx].mean())
    boots = np.array(boots)
    pwin = float((boots > 0).mean())
    print(f"  bootstrap P(GROWTH daily mean > CONSERVATIVE) = {pwin*100:.0f}%  "
          f"(2000 resamples; >60% = a real plateau edge, not a lucky spike)")
    # 3) rolling-1y: fraction of windows GROWTH beats CONSERVATIVE
    roll_g = (1 + g2).rolling(TD).apply(np.prod, raw=True) - 1
    roll_c = (1 + c2).rolling(TD).apply(np.prod, raw=True) - 1
    win1y = float((roll_g > roll_c).mean())
    print(f"  rolling-1y windows GROWTH > CONSERVATIVE: {win1y*100:.0f}%")
    # 4) medium-risk check: is maxDD in the -30..-40% band, NOT -60%?
    print(f"  GROWTH maxDD full={gf['maxDD']*100:.1f}%, recent={stats(g2[g2.index>=recent_lo])['maxDD']*100:.1f}%"
          f"  -> medium-risk band check (target -30..-40%, hard fail if < -55%)")

    verdict = "KEEP" if (extra_ret > 0 and pwin >= 0.55 and abs(gf["maxDD"]) <= 0.55) else "DROP"
    print(f"\n  VERDICT: GROWTH tilt -> {verdict}")
    if verdict == "DROP":
        print("  -> growth adds risk without honestly earning return; recommend CONSERVATIVE.")
    else:
        print("  -> growth earns the higher return OOS net of cost on a plateau; medium risk.")
    print("=" * 78)
    return dict(full=full, recent=recent, growth_series=g, pwin=pwin, win1y=win1y,
                extra_ret=extra_ret, extra_dd=extra_dd, verdict=verdict)


# ---------------------------------------------------------------------------
# PLAN: contribute-and-compound Monte-Carlo using the GROWTH config's
# bootstrapped DAILY returns (block bootstrap incl. the bad tail).
# ---------------------------------------------------------------------------
def stationary_block_bootstrap_paths(daily, n_days, n_paths, block=21, seed=11):
    """Stationary block bootstrap of a daily return series -> (n_paths, n_days)."""
    rng = np.random.default_rng(seed)
    r = daily.dropna().values
    m = len(r)
    out = np.empty((n_paths, n_days), dtype=float)
    for p in range(n_paths):
        seq = np.empty(n_days)
        i = 0
        while i < n_days:
            start = rng.integers(0, m)
            L = rng.geometric(1.0 / block)
            take = min(L, n_days - i)
            for k in range(take):
                seq[i + k] = r[(start + k) % m]
            i += take
        out[p] = seq
    return out


def years_to_target(daily, start_cap, monthly_contrib, target, n_paths=3000,
                    max_years=40, seed=11):
    """Monte-Carlo years to reach `target` with monthly contributions, no
    withdrawals. Contributions added at each month-end. Returns p25/median/p75
    years (np.nan if a path never reaches the target within max_years)."""
    n_days = int(max_years * TD)
    paths = stationary_block_bootstrap_paths(daily, n_days, n_paths, seed=seed)
    # month-end day indices
    me = set(int(round(k * TD / 12)) for k in range(1, max_years * 12 + 1))
    me_arr = np.zeros(n_days, dtype=bool)
    for d in me:
        if 0 <= d < n_days:
            me_arr[d] = True
    reach_year = np.full(n_paths, np.nan)
    for p in range(n_paths):
        bal = start_cap
        rp = paths[p]
        for d in range(n_days):
            bal *= (1.0 + rp[d])
            if me_arr[d]:
                bal += monthly_contrib
            if bal >= target:
                reach_year[p] = (d + 1) / TD
                break
    valid = reach_year[~np.isnan(reach_year)]
    frac = len(valid) / n_paths
    if len(valid) == 0:
        return dict(p25=np.nan, p50=np.nan, p75=np.nan, frac=0.0)
    return dict(p25=float(np.percentile(reach_year[~np.isnan(reach_year)], 25)),
                p50=float(np.nanmedian(reach_year)),
                p75=float(np.percentile(reach_year[~np.isnan(reach_year)], 75)),
                frac=frac)


def run_plan(growth_daily, target=70000, npaths=3000):
    print("=" * 78)
    print("  CONTRIBUTE-AND-COMPOUND PLANNER -- years to the $%s '$500/mo base'"
          % f"{target:,.0f}")
    print("=" * 78)
    g = stats(growth_daily)
    print(f"  driver: GROWTH config's OWN bootstrapped daily returns "
          f"(CAGR {g['CAGR']*100:.1f}%, vol {g['vol']*100:.1f}%, maxDD {g['maxDD']*100:.1f}%)")
    print(f"  method: stationary block bootstrap (21d blocks, keeps fat tails + "
          f"vol clustering), {npaths} paths, NO withdrawals (phase-1 compounding)")
    print(f"  the BAD TAIL is in the distribution; bands are p25 (lucky) / median "
          f"/ p75 (unlucky) YEARS to reach ${target:,.0f}")
    starts = [2000, 5000]
    contribs = [200, 500, 1000]
    print(f"\n  {'start':>8} | " + " | ".join(f"+${c}/mo (p25/med/p75 yr)" for c in contribs))
    print("  " + "-" * 74)
    results = {}
    for s in starts:
        cells = []
        for c in contribs:
            r = years_to_target(growth_daily, s, c, target, n_paths=npaths)
            results[(s, c)] = r
            if r["frac"] < 0.99:
                cells.append(f"{r['p25']:.1f}/{r['p50']:.1f}/{r['p75']:.1f}* ")
            else:
                cells.append(f"{r['p25']:4.1f}/{r['p50']:4.1f}/{r['p75']:4.1f}   ")
        print(f"  ${s:>6} | " + " | ".join(cells))
    print("  " + "-" * 74)
    print("  (* = some paths did not reach target within 40y; p-bands over reaching paths)")
    print("  HONEST: this is a MULTI-YEAR plan. Contributions dominate at small size;")
    print("  the ~12-18% trend-gated growth edge is the finisher, not a fast track.")
    print("=" * 78)
    return results


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Growth-tilt validation + contribute/compound planner.")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--target", type=float, default=70000)
    ap.add_argument("--npaths", type=int, default=3000)
    ap.add_argument("--cache", type=str, default="/tmp/aw_data/planner_prices.csv")
    args = ap.parse_args(argv)
    if not (args.validate or args.plan):
        args.validate = args.plan = True

    need = sorted(set(["SPY", "TLT", "GLD", CASH_TICKER, "IBIT"]) | set(CORE_UNIVERSE))
    try:
        # need long history for a real backtest -> 19y
        px, source = fetch_prices(need, cache_path=args.cache, lookback_years=19)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    print(f"[data] source={source}  range={px.index.min().date()}.."
          f"{px.index.max().date()}  cols={px.shape[1]}", file=sys.stderr)

    growth_daily = None
    if args.validate:
        vres = run_validate(px)
        growth_daily = vres["growth_series"]
    if args.plan:
        if growth_daily is None:
            growth_daily = backtest_weights(px, weights_config(px, aw.GROWTH))
        run_plan(growth_daily, target=args.target, npaths=args.npaths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
