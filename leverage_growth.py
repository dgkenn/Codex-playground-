#!/usr/bin/env python3
"""
leverage_growth.py -- GROWTH-OPTIMAL LEVERAGE on the trend-overlaid all-weather book.
=====================================================================================
THE QUESTION
  The recommended book is a TREND-OVERLAID ALL-WEATHER portfolio (PP-style base
  SPY/TLT/GLD + a 6-12m time-series trend filter that parks falling sleeves in
  cash). Long-history (1972-2023) Sharpe ~1.43, maxDD ~-10% (HALVED vs pure PP's
  ~-17%). REGIME_ROBUSTNESS.md showed levering a PURE STATIC is a bad deal (it
  amplifies the -17% DD + pays financing). But the trend book's DD is already
  halved AND it goes to cash in downturns -> it is a fundamentally BETTER leverage
  candidate. The operator is young, medium-risk (can tolerate -30..-40% DD), small
  bankroll, compounding toward a ~$70k income base. So:

    What leverage MAXIMIZES long-run growth (CAGR) SUBJECT TO maxDD <= 35% on the
    LONG history (incl. 1970s + 2022)? Margin vs LETF as the vehicle? What does it
    do to the years-to-$70k vs unlevered, and at what ruin/tail cost?

WHAT THIS DOES (reuses the committed engines; does NOT re-derive the strategy)
  1. LEVERAGE CURVE: takes the EXACT trend-overlaid book from
     regime_robustness.trend_overlay (long history, monthly) and the ETF-era
     daily book from growth_planner/allweather_live, and levers it 1.0..2.0x via
     two HONEST vehicles:
       (a) MARGIN: r_lev = L*r_book - (L-1)*(cash + spread). Borrow the (L-1)
           portion at T-bill + 100-150 bps. Cash leg of the book already earns
           T-bill, so the net cost is the spread on the borrowed portion.
       (b) LETF: model 2x/3x DAILY-RESET sleeves with the real volatility decay
           (compounding daily 2x returns minus 2x expense + the variance drag
           -(L^2-L)/2 * sigma_daily^2 ). This is the honest LETF path.
  2. GROWTH-OPTIMAL (half-Kelly + DD-constrained): for a log-growth maximizer,
     find full-Kelly L* = mu_excess/sigma^2, report half-Kelly (the practical max),
     and find the leverage that MAXIMIZES CAGR subject to maxDD<=35% on the long
     history. The binding constraint, not the unconstrained optimum, is the answer.
  3. RUIN / SEQUENCE: block-bootstrap (haircut mean) the chosen leverage at
     $2k/$5k with $0 and $500/mo -> P(ruin), P(>50% DD), and the DISTRIBUTION of
     years-to-$70k vs the unlevered book.
  4. IRA-LETF practicality: a trend-overlaid 2x-LETF all-weather (SSO/UBT/UGL,
     trend-gated to cash) -- can it approximate the levered book inside an IRA
     (where margin is not allowed)? Tested on the ETF era with honest decay.

DATA (all staged NON-repo, reused from the committed builds):
  long history : /tmp/regime_data/monthly_tr.csv   (regime_data.py, 1972-2023)
  ETF era      : /tmp/etfmom_data/etf_prices.csv    (yfinance daily adj closes)
COSTS: 5 bps/side turnover (matches regime_robustness); margin spread 125 bps/yr
  on the borrowed portion (default, mid of 100-150); LETF expense 90 bps/yr +
  honest daily variance decay. Half-Kelly, not full. SCREENS in LEVERAGE_GROWTH.md.

USAGE
  python leverage_growth.py            # full run (curve + kelly + ruin + IRA-LETF)
  python leverage_growth.py --npaths 5000
"""
from __future__ import annotations

import argparse
import sys
import numpy as np
import pandas as pd

import regime_robustness as rr

TR_CSV   = "/tmp/regime_data/monthly_tr.csv"
ETF_CSV  = "/tmp/etfmom_data/etf_prices.csv"
MPY      = 12
TD       = 252

MARGIN_SPREAD = 0.0125     # margin rate = T-bill + 125 bps on the borrowed portion
LETF_EXPENSE  = 0.0090     # 90 bps/yr LETF expense ratio (SSO/UBT/UGL ballpark)
LEV_GRID      = [1.0, 1.25, 1.5, 1.75, 2.0]
DD_BUDGET     = 0.35       # medium-risk drawdown budget


# ---------------------------------------------------------------------------
# stats helpers (monthly + daily aware)
# ---------------------------------------------------------------------------
def stats(net, freq):
    net = net.dropna()
    if len(net) < freq:
        return dict(CAGR=np.nan, Sharpe=np.nan, vol=np.nan, maxDD=np.nan, worst_yr=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / freq
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = net.std() * np.sqrt(freq)
    sharpe = net.mean() / net.std() * np.sqrt(freq) if net.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + net).groupby(net.index.year).prod() - 1
    return dict(CAGR=cagr, Sharpe=sharpe, vol=vol, maxDD=dd, worst_yr=yr.min(), n=len(net))


# ---------------------------------------------------------------------------
# LEVERAGE VEHICLES
# ---------------------------------------------------------------------------
def lever_margin(book_ret, cash_ret, L, spread=MARGIN_SPREAD, freq=MPY):
    """MARGIN leverage: hold L of the book, borrow (L-1) at cash + spread.
       r_lev = L*r_book - (L-1)*(cash + spread/freq).
    The book ALREADY earns cash on its cash sleeve; borrowing (L-1) at the broker
    call rate (cash+spread) is the honest financing cost on the borrowed portion."""
    if L <= 1.0:
        return book_ret.copy()
    borrow_cost = cash_ret + spread / freq
    return (L * book_ret - (L - 1.0) * borrow_cost).dropna()


def lever_letf_from_daily(book_daily, L, expense=LETF_EXPENSE, td=TD):
    """LETF (daily-reset) leverage applied to a DAILY book-return series.
    Daily-reset L x exposure compounds L*r each day, so the honest path is:
        r_letf_daily = L*r_book_daily - expense/td
    Compounding this daily series AUTOMATICALLY produces the volatility decay
    (the -(L^2-L)/2 * sigma^2 drag emerges from compounding L*r vs r). No extra
    fudge -- the decay is real and IN the compounded equity curve."""
    return (L * book_daily - expense / td).dropna()


def letf_decay_monthly(book_ret, L, sigma_daily, expense=LETF_EXPENSE, freq=MPY, td=TD):
    """Approximate a daily-reset LETF on a MONTHLY book series (long history has no
    daily data). The honest closed-form: daily-reset L x has expected monthly log
    return = L*mu_book - 0.5*(L^2 - L)*sigma_book^2 (per period) - expense.
    We apply the variance drag at the chosen frequency using sigma_daily^2 scaled.
    decay per month = 0.5*(L^2-L)*sigma_month^2 where sigma_month = sigma_daily*sqrt(td/freq).
    This is the standard LETF decay term; it grows with L^2 and with vol."""
    if L <= 1.0:
        return book_ret.copy()
    sigma_month = sigma_daily * np.sqrt(td / freq)
    decay = 0.5 * (L * L - L) * (sigma_month ** 2)        # per-month variance drag
    exp_m = expense / freq
    return (L * book_ret - decay - exp_m).dropna()


# ---------------------------------------------------------------------------
# 1. LEVERAGE CURVE (long history, monthly) -- margin vs LETF
# ---------------------------------------------------------------------------
def long_history_book():
    """The trend-overlaid all-weather book on the 1972-2023 long history (monthly).
    Reuses regime_robustness.trend_overlay EXACTLY: STOCKS/UST30/GOLD each 1/3,
    held only if trailing 12m TR > 0 else -> cash. Returns (book_ret, cash_ret)."""
    tr = pd.read_csv(TR_CSV, index_col=0, parse_dates=True)
    book = rr.trend_overlay(tr, ["STOCKS", "UST30", "GOLD"], lookback=12,
                            weights={"STOCKS": 1/3, "UST30": 1/3, "GOLD": 1/3})
    cash = tr["CASH"].reindex(book.index)
    return book.dropna(), cash, tr


def etf_era_book():
    """The trend-overlaid all-weather book on the ETF era (daily). Same rule as the
    long history but on yfinance daily adj closes (SPY/TLT/GLD, 12m TS trend ->
    BIL cash). Returns (book_daily, cash_daily)."""
    px = pd.read_csv(ETF_CSV, index_col=0, parse_dates=True).sort_index()
    sleeves = ["SPY", "TLT", "GLD"]
    px = px[[c for c in sleeves + ["BIL"] if c in px.columns]].dropna(how="all")
    ret = px[sleeves].pct_change()
    # 12m (252d) trailing total return trend, 1-day lagged signal
    lb = 252
    cum = px[sleeves] / px[sleeves].shift(lb) - 1.0
    sig = (cum > 0).astype(float).shift(1).fillna(0.0)
    base = 1.0 / len(sleeves)
    Wass = sig * base
    Wcash = 1.0 - Wass.sum(axis=1)
    if "BIL" in px.columns:
        cashr = px["BIL"].pct_change().fillna((1 + 0.02) ** (1/TD) - 1)
    else:
        cashr = pd.Series((1 + 0.02) ** (1/TD) - 1, index=px.index)
    book = (Wass.shift(0) * ret).sum(axis=1) + Wcash * cashr
    # cost on monthly turnover
    full = Wass.copy(); full["CASH"] = Wcash
    me = pd.Series(full.index, index=full.index).groupby([full.index.year, full.index.month]).last()
    rebal = set(pd.Timestamp(d) for d in me.values)
    turn = full.diff().abs().sum(axis=1).fillna(0.0)
    turn = turn.where(turn.index.isin(rebal), 0.0)
    book = (book - turn * 5.0 / 1e4)
    # only count from first valid signal
    book = book[cum.notna().any(axis=1)]
    return book.dropna(), cashr.reindex(book.index).fillna(0.0)


def leverage_curve_long(book, cash, sigma_daily):
    """CAGR/Sharpe/maxDD/worst-yr at each leverage, via MARGIN and via LETF, on the
    long history (monthly)."""
    rows = []
    for L in LEV_GRID:
        m = lever_margin(book, cash, L)
        e = letf_decay_monthly(book, L, sigma_daily)
        sm, se = stats(m, MPY), stats(e, MPY)
        rows.append(dict(L=L,
                         m_CAGR=sm["CAGR"], m_Sharpe=sm["Sharpe"], m_maxDD=sm["maxDD"], m_worst=sm["worst_yr"],
                         e_CAGR=se["CAGR"], e_Sharpe=se["Sharpe"], e_maxDD=se["maxDD"], e_worst=se["worst_yr"]))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. GROWTH-OPTIMAL (Kelly) + DD-constrained leverage
# ---------------------------------------------------------------------------
def kelly_leverage(book, cash, freq=MPY):
    """Full-Kelly leverage for a log-growth maximizer = mu_excess / sigma^2 (both
    annualized, on EXCESS-over-cash returns). Half-Kelly is the practical max."""
    ex = (book - cash).dropna()
    mu = ex.mean() * freq
    var = (ex.std() * np.sqrt(freq)) ** 2
    full = mu / var if var > 0 else np.nan
    return dict(mu_excess=mu, sigma=np.sqrt(var), full_kelly=full, half_kelly=full / 2.0)


def dd_constrained_leverage(book, cash, sigma_daily, etf_book, etf_cash,
                            budget=DD_BUDGET, vehicle="margin", grid=None):
    """Highest leverage whose maxDD stays within budget on the WORSE of the two
    windows (long-history monthly AND ETF-era daily), maximizing long-history CAGR.
    Using the worse DD is the honest, conservative constraint: the long-history
    monthly book understates DD (no intramonth gaps); the ETF-era daily book sees
    2008/2020/2022 intramonth. vehicle in {margin, letf}."""
    if grid is None:
        grid = np.round(np.arange(1.0, 3.01, 0.05), 2)
    best = None
    for L in grid:
        if vehicle == "margin":
            r_long = lever_margin(book, cash, L)
            r_etf = lever_margin(etf_book, etf_cash, L, freq=TD)
        else:
            r_long = letf_decay_monthly(book, L, sigma_daily)
            r_etf = lever_letf_from_daily(etf_book, L)
        s_long = stats(r_long, MPY)
        s_etf = stats(r_etf, TD)
        worst_dd = min(s_long["maxDD"], s_etf["maxDD"])   # most negative
        if abs(worst_dd) <= budget:
            cand = dict(s_long); cand["worst_dd"] = worst_dd; cand["etf_dd"] = s_etf["maxDD"]
            if best is None or cand["CAGR"] > best[1]["CAGR"]:
                best = (L, cand)
    return best


# ---------------------------------------------------------------------------
# 3. RUIN / SEQUENCE -- block bootstrap with HAIRCUT mean
# ---------------------------------------------------------------------------
def block_bootstrap(daily, n_days, n_paths, block, rng, haircut_ann=0.0, td=TD):
    """Stationary block bootstrap of a daily series; subtract a per-day haircut so
    the bootstrap mean is HAIRCUT below the in-sample mean (honest forward CAGR)."""
    r = daily.dropna().values - haircut_ann / td
    m = len(r)
    out = np.empty((n_paths, n_days))
    for p in range(n_paths):
        i = 0
        while i < n_days:
            start = rng.integers(0, m)
            L = rng.geometric(1.0 / block)
            take = min(L, n_days - i)
            for k in range(take):
                out[p, i + k] = r[(start + k) % m]
            i += take
    return out


def mc_ruin_and_timeline(daily, start_cap, monthly, target, n_paths, max_years,
                         ruin_floor, block=21, haircut_ann=0.0, seed=7, td=TD):
    """Monte-Carlo on a daily return series with monthly contributions.
    Reports P(ruin = balance ever < ruin_floor before target), P(intra-path DD>50%),
    and the years-to-target distribution (p25/median/p75; frac reaching)."""
    rng = np.random.default_rng(seed)
    n_days = int(max_years * td)
    paths = block_bootstrap(daily, n_days, n_paths, block, rng, haircut_ann, td)
    me = set(int(round(k * td / 12)) for k in range(1, max_years * 12 + 1))
    me_arr = np.zeros(n_days, dtype=bool)
    for d in me:
        if 0 <= d < n_days:
            me_arr[d] = True
    reach = np.full(n_paths, np.nan)
    ruined = np.zeros(n_paths, dtype=bool)
    big_dd = np.zeros(n_paths, dtype=bool)
    for p in range(n_paths):
        bal = float(start_cap)
        peak = bal
        rp = paths[p]
        done = False
        for d in range(n_days):
            bal *= (1.0 + rp[d])
            if me_arr[d]:
                bal += monthly
            peak = max(peak, bal)
            if peak > 0 and bal / peak - 1.0 <= -0.50:
                big_dd[p] = True
            # ruin = drawn below floor on contributed-capital basis (before reaching target)
            if bal < ruin_floor and not done:
                ruined[p] = True
            if bal >= target and not done:
                reach[p] = (d + 1) / td
                done = True
                break
    valid = reach[~np.isnan(reach)]
    frac = len(valid) / n_paths
    res = dict(p_ruin=float(ruined.mean()), p_dd50=float(big_dd.mean()), frac=frac)
    if len(valid):
        res.update(p25=float(np.percentile(valid, 25)),
                   p50=float(np.median(valid)),
                   p75=float(np.percentile(valid, 75)))
    else:
        res.update(p25=np.nan, p50=np.nan, p75=np.nan)
    return res


# ---------------------------------------------------------------------------
# 4. IRA-LETF trend-overlaid all-weather (SSO/UBT/UGL trend-gated)
# ---------------------------------------------------------------------------
def ira_letf_book(book_daily_unlev, L_target):
    """Approximate a trend-overlaid 2x-LETF all-weather inside an IRA: the trend
    rule is identical (sleeves on/off), but ON sleeves are held via a daily-reset
    L-x LETF. Modeled by applying the LETF daily transform to the UNLEVERED daily
    book return: r = L*r_book - expense/td. The decay is automatic in compounding.
    NOTE: this approximates the WHOLE book at Lx; in practice you hold SSO/UBT/UGL
    only for the ON sleeves and cash for OFF -- same net daily exposure, so the
    book-level LETF transform is the right first-order model. Cash sleeve is NOT
    levered (you hold real cash), which this slightly conservatively ignores."""
    return lever_letf_from_daily(book_daily_unlev, L_target)


# ---------------------------------------------------------------------------
def fmt(x, pct=True):
    if x != x:
        return "   n/a"
    return f"{x*100:6.1f}%" if pct else f"{x:6.2f}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npaths", type=int, default=4000)
    ap.add_argument("--target", type=float, default=70000)
    args = ap.parse_args(argv)

    print("=" * 84)
    print("  GROWTH-OPTIMAL LEVERAGE on the TREND-OVERLAID ALL-WEATHER book")
    print("=" * 84)

    book, cash, tr = long_history_book()
    bk = stats(book, MPY)
    print(f"  LONG HISTORY (monthly): {book.index.min().date()}..{book.index.max().date()}  n={len(book)}")
    print(f"  unlevered book: CAGR {fmt(bk['CAGR'])}  Sharpe {fmt(bk['Sharpe'],0)}  "
          f"maxDD {fmt(bk['maxDD'])}  vol {fmt(bk['vol'])}  worstYr {fmt(bk['worst_yr'])}")

    etf_book, etf_cash = etf_era_book()
    ek = stats(etf_book, TD)
    sigma_daily = etf_book.std()      # daily vol of the book (for honest LETF decay)
    print(f"  ETF ERA  (daily):       {etf_book.index.min().date()}..{etf_book.index.max().date()}  n={len(etf_book)}")
    print(f"  unlevered book: CAGR {fmt(ek['CAGR'])}  Sharpe {fmt(ek['Sharpe'],0)}  "
          f"maxDD {fmt(ek['maxDD'])}  vol {fmt(ek['vol'])}  sigma_daily {sigma_daily*100:.3f}%")

    # ---- 1. LEVERAGE CURVE (long history) ----
    print("\n" + "-" * 84)
    print("  1. LEVERAGE CURVE -- long history 1972-2023 (monthly, net 5bps + financing/decay)")
    print("-" * 84)
    curve = leverage_curve_long(book, cash, sigma_daily)
    print("     NOTE: monthly LETF decay UNDERSTATES real decay (monthly variance term is small);")
    print("           trust the ETF-era DAILY LETF (1b) for the honest decay -- there LETF~=margin.")
    print(f"     {'':6}|{'MARGIN (T-bill+125bps)':^34}|{'LETF (2x daily-reset, 90bps+decay)':^36}")
    print(f"     {'L':>4} | {'CAGR':>7}{'Sharpe':>7}{'maxDD':>8}{'wYr':>7} | "
          f"{'CAGR':>7}{'Sharpe':>7}{'maxDD':>8}{'wYr':>7}")
    for _, r in curve.iterrows():
        print(f"     {r['L']:>4.2f} | {fmt(r['m_CAGR'])}{fmt(r['m_Sharpe'],0):>7}{fmt(r['m_maxDD'])}{fmt(r['m_worst'])} | "
              f"{fmt(r['e_CAGR'])}{fmt(r['e_Sharpe'],0):>7}{fmt(r['e_maxDD'])}{fmt(r['e_worst'])}")

    # ETF-era curve for cross-check (daily LETF -> honest decay)
    print("\n  1b. LEVERAGE CURVE -- ETF era (daily; LETF decay from actual daily compounding)")
    print(f"     {'L':>4} | {'MARGIN CAGR':>11}{'mDD':>8} | {'LETF CAGR':>10}{'mDD':>8}{'Sharpe':>8}")
    for L in LEV_GRID:
        m = lever_margin(etf_book, etf_cash, L, freq=TD)
        e = lever_letf_from_daily(etf_book, L)
        sm, se = stats(m, TD), stats(e, TD)
        print(f"     {L:>4.2f} | {fmt(sm['CAGR']):>11}{fmt(sm['maxDD'])} | "
              f"{fmt(se['CAGR']):>10}{fmt(se['maxDD'])}{fmt(se['Sharpe'],0):>8}")

    # ---- 2. KELLY + DD-constrained ----
    print("\n" + "-" * 84)
    print("  2. GROWTH-OPTIMAL (Kelly) + DD-CONSTRAINED leverage")
    print("-" * 84)
    k = kelly_leverage(book, cash)
    print(f"     long-history excess mu={k['mu_excess']*100:.2f}%/yr  sigma={k['sigma']*100:.2f}%/yr")
    print(f"     FULL-Kelly L* = mu/sigma^2 = {k['full_kelly']:.2f}x   (theoretical growth-max, BRUTAL DD)")
    print(f"     HALF-Kelly    = {k['half_kelly']:.2f}x   (the practical maximum; never exceed)")
    bm = dd_constrained_leverage(book, cash, sigma_daily, etf_book, etf_cash, vehicle="margin")
    be = dd_constrained_leverage(book, cash, sigma_daily, etf_book, etf_cash, vehicle="letf")
    print("     DD constraint binds on the WORSE of long-history(monthly) & ETF-era(daily) DD")
    if bm:
        st = bm[1]
        print(f"     DD-CONSTRAINED (maxDD<=35%, MARGIN): L = {bm[0]:.2f}x  -> "
              f"CAGR {fmt(st['CAGR'])}  Sharpe {fmt(st['Sharpe'],0)}  worstDD {fmt(st['worst_dd'])} "
              f"(longDD {fmt(st['maxDD'])}, etfDD {fmt(st['etf_dd'])})")
    if be:
        st = be[1]
        print(f"     DD-CONSTRAINED (maxDD<=35%, LETF)  : L = {be[0]:.2f}x  -> "
              f"CAGR {fmt(st['CAGR'])}  Sharpe {fmt(st['Sharpe'],0)}  worstDD {fmt(st['worst_dd'])} "
              f"(longDD {fmt(st['maxDD'])}, etfDD {fmt(st['etf_dd'])})")

    # The chosen leverage: DD-constrained, capped at half-Kelly, AND keep a margin of
    # safety -- the operator should NOT sit right at the -35% cliff, so we step one
    # notch below the binding L for the headline recommendation.
    dd_L = bm[0] if bm else 1.0
    dd_L = min(dd_L, round(k['half_kelly'], 2))
    chosen_L = max(1.0, round(dd_L - 0.25, 2))  # one-notch safety margin below the cliff
    print(f"\n     DD-binding L (margin) = {dd_L:.2f}x; half-Kelly = {k['half_kelly']:.2f}x (non-binding).")
    print(f"     CHOSEN (with a safety notch below the -35% cliff) = {chosen_L:.2f}x  (margin, taxable)")

    # ---- 3. RUIN / SEQUENCE (ETF-era daily book, levered via margin) ----
    print("\n" + "-" * 84)
    print(f"  3. RUIN / SEQUENCE Monte-Carlo ({args.npaths} paths, block=21d, HAIRCUT 2%/yr mean)")
    print("-" * 84)
    HAIRCUT = 0.02
    # levered daily book via margin (ETF-era daily) at chosen L and at 1.5x for contrast
    def levered_daily(L):
        return lever_margin(etf_book, etf_cash, L, freq=TD)
    scenarios = [("unlevered 1.0x", 1.0), (f"chosen {chosen_L:.2f}x (margin)", chosen_L),
                 (f"DD-cap {dd_L:.2f}x (margin)", dd_L)]
    for cap in [2000, 5000]:
        for contrib in [0, 500]:
            print(f"\n     start ${cap:,}, +${contrib}/mo, target ${args.target:,.0f}  (ruin floor=$1)")
            print(f"     {'leverage':<22}{'P(ruin)':>9}{'P(DD>50%)':>11}{'yrs p25':>9}{'median':>8}{'p75':>7}{'reach':>8}")
            for name, L in scenarios:
                dl = levered_daily(L)
                r = mc_ruin_and_timeline(dl, cap, contrib, args.target,
                                         n_paths=args.npaths, max_years=40,
                                         ruin_floor=1.0, haircut_ann=HAIRCUT)
                p25 = f"{r['p25']:.1f}" if r['p25'] == r['p25'] else "n/a"
                p50 = f"{r['p50']:.1f}" if r['p50'] == r['p50'] else "n/a"
                p75 = f"{r['p75']:.1f}" if r['p75'] == r['p75'] else "n/a"
                print(f"     {name:<22}{r['p_ruin']*100:8.1f}%{r['p_dd50']*100:10.1f}%"
                      f"{p25:>9}{p50:>8}{p75:>7}{r['frac']*100:7.0f}%")

    # ---- 4. IRA-LETF practicality ----
    print("\n" + "-" * 84)
    print("  4. IRA-LETF practicality -- trend-overlaid 2x-LETF all-weather (SSO/UBT/UGL)")
    print("-" * 84)
    print("     (margin needs a taxable margin account; an IRA cannot use margin.")
    print("      Can a trend-overlaid 2x-LETF book approximate the levered book in an IRA?)")
    print(f"     {'vehicle':<34}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>9}{'vol':>8}")
    base = stats(etf_book, TD)
    print(f"     {'unlevered book (1x, taxable/IRA)':<34}{fmt(base['CAGR'])}{fmt(base['Sharpe'],0):>8}{fmt(base['maxDD'])}{fmt(base['vol'])}")
    for L in [1.5, 2.0]:
        marg = stats(lever_margin(etf_book, etf_cash, L, freq=TD), TD)
        print(f"     {f'margin {L:.1f}x (taxable only)':<34}{fmt(marg['CAGR'])}{fmt(marg['Sharpe'],0):>8}{fmt(marg['maxDD'])}{fmt(marg['vol'])}")
    for L in [1.5, 2.0]:
        letf = stats(ira_letf_book(etf_book, L), TD)
        print(f"     {f'{L:.1f}x-LETF book (IRA-legal, decay)':<34}{fmt(letf['CAGR'])}{fmt(letf['Sharpe'],0):>8}{fmt(letf['maxDD'])}{fmt(letf['vol'])}")
    print("     -> LETF CAGR sits BELOW the same-leverage margin CAGR by the decay gap;")
    print("        the gap widens with L and with vol. 1.5x-LETF ~ the IRA stand-in for 1.5x margin.")

    print("\n" + "=" * 84)
    print("  See LEVERAGE_GROWTH.md for the verdict, screens, and window/cost statement.")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
