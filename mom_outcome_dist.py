"""FORWARD OUTCOME DISTRIBUTION for the locked long-only crypto momentum sleeve.

Does NOT re-optimize. Regenerates the LOCKED strategy weekly return series
(MOM_LONGONLY.md 78d934e + MOM_LO_RISK.md 03d714c: top-15 deep USD-spot, risk-adj
10d momentum, hold top-3 EW, weekly, partial 0.7, BTC>=100dMA gate->cash, 40bps RT,
statically scaled c=0.57 -> ~40% target vol) by reusing mlo_backtest / mlo_risk.

Then characterizes the FORWARD OUTCOME DISTRIBUTION via:
  - BLOCK BOOTSTRAP (moving-block, preserves autocorrelation & vol-clustering)
  - parametric Monte-Carlo cross-check (Student-t fat tails, fitted to data)
over 1/2/3 yr horizons, at RAW and HAIRCUT (35% mean reduction) return means.

Outputs: terminal-wealth percentiles ($1k/$10k), drawdown distribution,
time-underwater / time-to-recovery, P(loss)/P(<cash)/P(<BTC), sizing guideline.

Survivorship/decay caveat: backtest universe = listed Coinbase/Kraken pairs (dead
alts missing -> UP bias). We HAIRCUT the historical mean ~35% for forward realism.
Past distribution != future; crypto could structurally decay.
"""
import numpy as np
import pandas as pd
import mlo_backtest as mb
import mlo_risk as mr

RNG = np.random.default_rng(20260614)
HOLD = 7
PPY = 365.0 / HOLD          # ~52.14 weekly periods/yr
SCALE = 0.57                # static downsize -> ~40% target vol (locked)
HAIRCUT = 0.35              # forward mean discount for survivorship/decay
N_PATHS = 20000
HORIZONS = {"1yr": 52, "2yr": 104, "3yr": 156}
DD_THRESH = [0.20, 0.30, 0.40, 0.50]
PCTL = [5, 25, 50, 75, 95]


# ---------------------------------------------------------------- return series
def build_series():
    px, vol = mb.load_spot()
    pool = list(px.columns)
    bt = mr.backtest_risk(px, vol, lb=10, top_n=15, k=3, cost_bps=40,
                          partial=0.7, gate_ma=100, univ_pool=pool)
    strat = (bt["net"] * SCALE).rename("strat")          # locked scaled weekly net
    # benchmark: BTC buy-and-hold on the SAME weekly grid
    btc = mb.asset_buyhold(px, sym="BTC", hold_days=HOLD)["net"].rename("btc")
    df = pd.concat([strat, btc], axis=1).dropna(subset=["strat"])
    return df, px


# --------------------------------------------------------------- bootstrap core
def moving_block_indices(n_src, n_out, block):
    """Draw moving-block bootstrap row indices (overlapping blocks)."""
    n_blocks = int(np.ceil(n_out / block))
    starts = RNG.integers(0, n_src - block + 1, size=n_blocks)
    idx = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:n_out]
    return idx


def block_bootstrap_paths(rets, n_periods, n_paths, block, demean=0.0):
    """Return array [n_paths, n_periods] of weekly returns via moving-block bootstrap.
       demean: subtract this from every sampled return (used for mean haircut)."""
    src = rets.values
    n_src = len(src)
    out = np.empty((n_paths, n_periods))
    for p in range(n_paths):
        out[p] = src[moving_block_indices(n_src, n_periods, block)]
    return out - demean


def parametric_paths(rets, n_periods, n_paths, demean=0.0):
    """Student-t Monte-Carlo cross-check: iid draws (NO vol-cluster), fat tails.
       df is set from the empirical excess kurtosis (df = 6/kurt + 4, capped to
       [3,30]); location/scale are MOMENT-MATCHED to the empirical mean & sd, so the
       only difference vs the block bootstrap is the loss of autocorrelation /
       vol-clustering. (A free scipy t.fit on this skewed series collapses to a
       degenerate df, so we pin df from kurtosis instead.)"""
    from scipy import stats as ss
    mu, sd = rets.mean(), rets.std()
    k = max(rets.kurtosis(), 0.5)              # excess kurtosis
    dfree = float(np.clip(6.0 / k + 4.0, 3.0, 30.0))
    t_sd = np.sqrt(dfree / (dfree - 2.0))      # std of standard t
    scale = sd / t_sd                          # match empirical sd
    z = ss.t.rvs(dfree, size=(n_paths, n_periods), random_state=RNG)
    draws = mu + scale * z                     # match empirical mean
    return draws - demean


# --------------------------------------------------------------- path analytics
def path_metrics(weekly):
    """weekly: [n_paths, n_periods] -> dict of arrays over paths."""
    n_paths, n = weekly.shape
    eq = np.cumprod(1.0 + weekly, axis=1)          # equity multiple (start=1)
    eq = np.concatenate([np.ones((n_paths, 1)), eq], axis=1)  # prepend t0=1
    run_max = np.maximum.accumulate(eq, axis=1)
    dd = eq / run_max - 1.0
    max_dd = dd.min(axis=1)                          # most negative per path (<=0)
    terminal = eq[:, -1]
    cagr = terminal ** (PPY / n) - 1.0

    # time underwater: fraction of periods with dd < -1% (i.e. below a prior peak)
    underwater = (dd < -0.01)
    tuw_frac = underwater.mean(axis=1)
    # longest underwater run (weeks) per path
    longest_uw = np.zeros(n_paths)
    for i in range(n_paths):
        u = underwater[i]
        if not u.any():
            continue
        # run-length of consecutive True
        best = cur = 0
        for v in u:
            cur = cur + 1 if v else 0
            if cur > best:
                best = cur
        longest_uw[i] = best
    return dict(terminal=terminal, cagr=cagr, max_dd=max_dd,
                tuw_frac=tuw_frac, longest_uw_wk=longest_uw)


def pctile(a, ps=PCTL):
    return {f"p{p}": float(np.percentile(a, p)) for p in ps}


# ------------------------------------------------------------------- main study
def run():
    df, px = build_series()
    strat = df["strat"]
    btc = df["btc"]
    n_obs = len(strat)
    raw_mu = strat.mean()
    raw_sd = strat.std()
    haircut_mu = raw_mu * (1 - HAIRCUT)
    demean_for_haircut = raw_mu - haircut_mu       # shift to apply
    btc_mu = btc.mean()

    print("=" * 78)
    print("LOCKED STRATEGY WEEKLY RETURN SERIES (scaled c=0.57)")
    print("=" * 78)
    print(f"n weekly obs = {n_obs}  span {strat.index.min().date()} .. {strat.index.max().date()}")
    print(f"weekly mean(raw)={raw_mu:.4f}  sd={raw_sd:.4f}  "
          f"ann_ret(raw)={raw_mu*PPY:.1%}  ann_vol={raw_sd*np.sqrt(PPY):.1%}  "
          f"FULL Sharpe={raw_mu/raw_sd*np.sqrt(PPY):.2f}")
    print(f"weekly mean(HAIRCUT -{HAIRCUT:.0%})={haircut_mu:.4f}  "
          f"ann_ret(haircut)={haircut_mu*PPY:.1%}  "
          f"Sharpe(haircut)={haircut_mu/raw_sd*np.sqrt(PPY):.2f}")
    print(f"BTC buy-hold weekly mean={btc_mu:.4f} ann_ret={btc_mu*PPY:.1%}")
    eq = (1 + strat).cumprod()
    print(f"in-sample full maxDD = {(eq/eq.cummax()-1).min():.1%}")
    print(f"skew={strat.skew():.2f}  kurtosis(excess)={strat.kurtosis():.2f}  "
          f"min wk={strat.min():.1%}  max wk={strat.max():.1%}")

    # autocorrelation -> motivates block bootstrap; choose block ~ sqrt(n) ~ 20wk
    ac1 = strat.autocorr(1)
    abs_ac1 = strat.abs().autocorr(1)  # vol clustering proxy
    print(f"lag-1 autocorr(ret)={ac1:.3f}  lag-1 autocorr(|ret|)={abs_ac1:.3f} "
          f"(vol-clustering -> use block bootstrap)")
    BLOCK = 13   # ~1 quarter of weeks; preserves vol-cluster runs
    print(f"BLOCK length = {BLOCK} weeks (~1 quarter); paths={N_PATHS}")

    results = {}
    for label, mu_shift in [("RAW", 0.0), ("HAIRCUT", demean_for_haircut)]:
        results[label] = {}
        for hname, nper in HORIZONS.items():
            bb = block_bootstrap_paths(strat, nper, N_PATHS, BLOCK, demean=mu_shift)
            pm = path_metrics(bb)
            # parametric cross-check (same mean shift)
            par = parametric_paths(strat, nper, N_PATHS, demean=mu_shift)
            pm_par = path_metrics(par)

            # P(below cash) == P(terminal < 1)
            p_loss = float((pm["terminal"] < 1.0).mean())
            # P(below BTC buy-hold) -> bootstrap BTC over same horizon, paired
            btc_bb = block_bootstrap_paths(btc, nper, N_PATHS, BLOCK, demean=0.0)
            btc_term = np.cumprod(1 + btc_bb, axis=1)[:, -1]
            p_below_btc = float((pm["terminal"] < btc_term).mean())

            results[label][hname] = dict(
                terminal_pctl=pctile(pm["terminal"]),
                cagr_pctl=pctile(pm["cagr"]),
                maxdd_pctl=pctile(pm["max_dd"]),
                exp_maxdd=float(pm["max_dd"].mean()),
                p_dd={t: float((pm["max_dd"] <= -t).mean()) for t in DD_THRESH},
                tuw_frac_pctl=pctile(pm["tuw_frac"]),
                longest_uw_pctl=pctile(pm["longest_uw_wk"]),
                p_loss=p_loss,
                p_below_btc=p_below_btc,
                # parametric cross-check on the key numbers (iid-t, NO vol-cluster)
                par_terminal_median=float(np.percentile(pm_par["terminal"], 50)),
                par_p_dd30=float((pm_par["max_dd"] <= -0.30).mean()),
                par_exp_maxdd=float(pm_par["max_dd"].mean()),
            )
    return df, results, dict(raw_mu=raw_mu, raw_sd=raw_sd, haircut_mu=haircut_mu,
                             btc_mu=btc_mu, n_obs=n_obs, block=BLOCK,
                             span=(strat.index.min(), strat.index.max()),
                             skew=strat.skew(), kurt=strat.kurtosis(),
                             ac1=ac1, abs_ac1=abs_ac1)


def fmt_money(mult, cap):
    return f"${mult*cap:,.0f}"


def print_report(results, meta):
    for label in ["RAW", "HAIRCUT"]:
        print("\n" + "#" * 78)
        print(f"# {label} MEAN  (block bootstrap, {N_PATHS} paths, block={meta['block']}wk)")
        print("#" * 78)
        for hname in HORIZONS:
            r = results[label][hname]
            print(f"\n--- {hname} ---")
            tp = r["terminal_pctl"]
            print("  TERMINAL WEALTH multiple:  "
                  + "  ".join(f"{k}={v:.2f}x" for k, v in tp.items()))
            print("    $1k  -> " + "  ".join(f"{k}={fmt_money(v,1000)}" for k, v in tp.items()))
            print("    $10k -> " + "  ".join(f"{k}={fmt_money(v,10000)}" for k, v in tp.items()))
            cp = r["cagr_pctl"]
            print("  CAGR:  " + "  ".join(f"{k}={v:+.0%}" for k, v in cp.items()))
            mp = r["maxdd_pctl"]
            print("  MAX DRAWDOWN pctl:  " + "  ".join(f"{k}={v:+.0%}" for k, v in mp.items())
                  + f"   E[maxDD]={r['exp_maxdd']:+.0%}")
            print("  P(maxDD worse than):  "
                  + "  ".join(f">{int(t*100)}%={r['p_dd'][t]:.0%}" for t in DD_THRESH))
            up = r["longest_uw_pctl"]
            print("  Longest UNDERWATER stretch (weeks):  "
                  + "  ".join(f"{k}={v:.0f}w" for k, v in up.items()))
            fp = r["tuw_frac_pctl"]
            print("  Fraction of time underwater:  "
                  + "  ".join(f"{k}={v:.0%}" for k, v in fp.items()))
            print(f"  P(below starting capital)={r['p_loss']:.0%}   "
                  f"P(below BTC buy-hold)={r['p_below_btc']:.0%}")
            print(f"  [parametric iid-t cross-check, NO vol-cluster] median terminal="
                  f"{r['par_terminal_median']:.2f}x  E[maxDD]={r['par_exp_maxdd']:+.0%}  "
                  f"P(DD>30%)={r['par_p_dd30']:.0%}")


if __name__ == "__main__":
    df, results, meta = run()
    print_report(results, meta)
    import json
    with open("/tmp/momdist_data/results.json", "w") as f:
        json.dump({k: {h: {kk: vv for kk, vv in d.items()}
                       for h, d in results[k].items()} for k in results},
                  f, indent=2, default=float)
    print("\nsaved /tmp/momdist_data/results.json")
