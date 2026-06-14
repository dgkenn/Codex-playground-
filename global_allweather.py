#!/usr/bin/env python3
"""
global_allweather.py -- robustness test of TWO untested refinements to the project's
CORE deployable base (the trend-overlaid all-weather / Permanent-Portfolio book in
allweather_live.py, CONSERVATIVE config):

  (1) GLOBAL DIVERSIFICATION: does broadening the US-only PP base (SPY/TLT/GLD/BIL)
      into a global all-weather book -- ex-US + EM equity, TIPS + broad commodities
      real-asset sleeve, intermediate vs long Treasuries, intl bonds -- improve
      risk-adjusted return / robustness, BOTH WITH the trend overlay?
  (2) REBALANCE MECHANICS on the chosen base: monthly vs quarterly vs annual cadence,
      and no-trade bands (rebalance a sleeve only when it drifts > X% RELATIVE from
      target). Turnover / cost / tax-churn vs Sharpe / DD.

METHOD. Reuses the LOCKED trend-overlay rule from regime_robustness.trend_overlay /
allweather_live.sleeve_trend_up: hold each RISK sleeve only when its own trailing
`lookback`-month total return > 0 (signal lagged 1 month, no look-ahead); else that
sleeve's weight parks in BIL cash. Daily div-adjusted prices via yfinance, resampled
to a monthly TR matrix; trend + rebalance run at MONTHLY granularity (cadence/band
applied on top). This is the ETF-era sample (2007->2026) -- it INCLUDES the 2008 GFC,
the 2011-12 ex-US/EM/commodity leadership tail, 2015-16, COVID 2020, and the 2022
stock+bond drawdown, plus the recent-5y holdout. It does NOT include the full 1970s
(no ETFs); the 1970s case for gold+cash is already made in regime_robustness.py on the
1972 reconstruction, which has no investable ex-US/EM/commodity proxies.

COSTS: 3 bps/side on rebalance turnover (the committed live cost; regime_robustness
used a conservative 5 bps). Turnover is reported separately so the tax-churn argument
for taxable accounts is explicit.

SCREENS (honesty): full-sample + recent-5y holdout; plateau across band widths (not a
spike); US-vs-global judged on the FULL ETF sample incl. the 2008/2011/2022 episodes
where US did NOT dominate -- not just the 2013-2021 US melt-up. Honest if simple US PP
wins (simplicity has value: fewer tickers, lower tracking-error-to-a-known-book).
"""
from __future__ import annotations
import os, json, sys
import numpy as np
import pandas as pd

DATA = "/tmp/global_data"
PX_CSV = os.path.join(DATA, "daily_px.csv")
COST_BPS = 3.0          # bps/side on turnover (the committed live cost)
MPY = 12
TRADING_DAYS = 252
START = "2007-01-01"
END = "2026-06-14"
RECENT_YEARS = 5
LOOKBACK_M = 12         # locked 12m time-series trend (mid of the 6-12m band)

# the full ETF universe we may pull from
UNIVERSE = ["SPY", "VEA", "VWO", "TLT", "IEF", "GLD", "TIP", "DBC", "BNDX", "BIL"]


# --------------------------------------------------------------------------- data
def fetch():
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(PX_CSV):
        px = pd.read_csv(PX_CSV, index_col=0, parse_dates=True)
        if set(UNIVERSE).issubset(px.columns):
            return px[UNIVERSE]
    import yfinance as yf
    raw = yf.download(UNIVERSE, start=START, end=END, auto_adjust=True, progress=False)
    px = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    px = px[UNIVERSE].dropna(how="all")
    px.to_csv(PX_CSV)
    return px


def monthly_tr(px):
    """Daily adj-close -> month-end TR matrix (pct change of month-end levels)."""
    me = px.resample("ME").last()
    tr = me.pct_change()
    return tr, me


# ----------------------------------------------------------------- trend overlay
def trend_signal(me, assets, lookback=LOOKBACK_M):
    """LOCKED rule: trailing `lookback`-month total return > 0, lagged 1 month.
    Computed on month-end levels (matches sleeve_trend_up's daily-level ratio)."""
    ratio = me[assets] / me[assets].shift(lookback) - 1.0
    sig = (ratio > 0).astype(float).shift(1)   # lag -> no look-ahead
    return sig


def overlay_weights(me, base_weights, lookback=LOOKBACK_M):
    """Target weight matrix from the trend overlay: each sleeve at its base weight
    when trend-UP, else 0 (its weight parks in cash). Returns (Wassets, Wcash, sig)
    where Wassets cols = base assets, Wcash = the BIL parking weight."""
    assets = list(base_weights.keys())
    base = pd.Series(base_weights, dtype=float)
    base = base / base.sum()
    sig = trend_signal(me, assets, lookback)
    Wassets = sig.mul(base, axis=1)
    Wcash = (1.0 - Wassets.sum(axis=1)).clip(lower=0.0)
    return Wassets, Wcash


# ------------------------------------------------------ rebalance engine (cadence+band)
def run_book(tr, me, base_weights, cash_col="BIL", lookback=LOOKBACK_M,
             cadence="M", band=0.0, cost_bps=COST_BPS):
    """Simulate the trend-overlaid book with a given rebalance CADENCE and no-trade BAND.

    target each month = overlay_weights (trend-gated base) ; the cash residual -> BIL.
    HELD weights drift with returns. We only TRADE a sleeve toward target on a rebalance
    date AND when |held - target| / target > band (RELATIVE drift band; for the cash leg
    we use an absolute-ish |held-target|>band*cash_target floor). Between trades weights
    just drift. Cost = turnover * cost_bps/1e4 charged the month a trade happens.

    cadence: 'M' monthly, 'Q' quarterly (Jan/Apr/Jul/Oct month-ends), 'A' annual (Dec).
    band: relative no-trade band (0.0 = always rebalance to target on cadence dates).
    Returns dict(net=Series, turnover=Series, n_trades, ann_turnover, ...).
    """
    assets = list(base_weights.keys())
    cols = assets + [cash_col]
    Wa, Wc = overlay_weights(me, base_weights, lookback)
    # full target matrix incl cash leg, on the monthly index
    tgt = Wa.copy()
    tgt[cash_col] = Wc
    tgt = tgt.reindex(columns=cols).fillna(0.0)

    R = tr.reindex(columns=cols).fillna(0.0)
    idx = me.index

    def is_rebal(ts):
        if cadence == "M":
            return True
        if cadence == "Q":
            return ts.month in (1, 4, 7, 10)
        if cadence == "A":
            return ts.month == 12
        raise ValueError(cadence)

    held = None
    net = pd.Series(0.0, index=idx)
    turn = pd.Series(0.0, index=idx)
    n_trades = 0
    valid_start = tgt.dropna().index.min()

    for i, ts in enumerate(idx):
        if ts < valid_start or tgt.loc[ts].isna().any():
            net.loc[ts] = np.nan
            continue
        t = tgt.loc[ts].values
        if held is None:
            held = t.copy()              # first investable month: set to target
            turnover = np.abs(t).sum()
            n_trades += 1
        else:
            do = is_rebal(ts)
            if do:
                drift = np.abs(held - t)
                # relative band vs target (cash leg: vs its own target, floored)
                denom = np.where(t > 1e-6, t, 1.0)
                rel = drift / denom
                trade_mask = rel > band
                if trade_mask.any():
                    new = held.copy()
                    new[trade_mask] = t[trade_mask]
                    # renormalize so weights sum to 1 (residual into cash leg)
                    s = new.sum()
                    if s > 0:
                        new = new / s
                    turnover = np.abs(new - held).sum()
                    held = new
                    n_trades += 1
                else:
                    turnover = 0.0
            else:
                turnover = 0.0
        # accrue this month's return on the held weights, charge cost
        r = float(np.dot(held, R.loc[ts].values))
        net.loc[ts] = r - turnover * cost_bps / 1e4
        turn.loc[ts] = turnover
        # drift the held weights by this month's returns
        held = held * (1.0 + R.loc[ts].values)
        s = held.sum()
        if s > 0:
            held = held / s

    net = net.dropna()
    turn = turn.reindex(net.index).fillna(0.0)
    yrs = len(net) / MPY
    ann_turn = turn.sum() / yrs if yrs > 0 else np.nan
    return dict(net=net, turnover=turn, n_trades=n_trades,
                ann_turnover=ann_turn, n=len(net))


# ----------------------------------------------------------------------- stats
def stats(net, cash=None):
    net = net.dropna()
    if len(net) < 24:
        return dict(CAGR=np.nan, Sharpe=np.nan, Sh_ex=np.nan, vol=np.nan,
                    maxDD=np.nan, worst_yr=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / MPY
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = net.std() * np.sqrt(MPY)
    sharpe = net.mean() / net.std() * np.sqrt(MPY) if net.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + net).groupby(net.index.year).prod() - 1
    out = dict(CAGR=cagr, Sharpe=sharpe, vol=vol, maxDD=dd,
               worst_yr=yr.min(), n=len(net))
    if cash is not None:
        ex = (net - cash.reindex(net.index)).dropna()
        out["Sh_ex"] = (ex.mean() / ex.std() * np.sqrt(MPY)) if ex.std() > 0 else np.nan
    return out


def window(s, lo, hi=None):
    s = s[s.index >= pd.Timestamp(lo)]
    if hi:
        s = s[s.index <= pd.Timestamp(hi)]
    return s


# ----------------------------------------------------------------- candidate books
def candidate_books():
    """Base (pre-trend) sleeve weights. Trend overlay parks falling sleeves in BIL,
    so 'always cash' is implicit (the un-allocated remainder + parked sleeves)."""
    books = {}
    # --- the CURRENT base: US-only Permanent Portfolio (25 each, 4th 25 always cash) ---
    books["US-PP (current)"] = {"SPY": .25, "TLT": .25, "GLD": .25}  # +25 BIL always cash
    # --- global EQUITY only: split the equity sleeve US/exUS/EM ---
    books["Global-equity"] = {"SPY": .125, "VEA": .075, "VWO": .05,
                              "TLT": .25, "GLD": .25}
    # --- real-asset sleeve: add TIPS + commodities, split the gold sleeve ---
    books["Global-real"] = {"SPY": .125, "VEA": .075, "VWO": .05,
                            "TLT": .25, "GLD": .125, "TIP": .075, "DBC": .05}
    # --- intermediate vs long Treasuries on the global book ---
    books["Global-IEF"] = {"SPY": .125, "VEA": .075, "VWO": .05,
                           "IEF": .25, "GLD": .125, "TIP": .075, "DBC": .05}
    # --- full global all-weather: global eq + (long+intl) bonds + real-asset sleeve ---
    books["Global-allweather"] = {"SPY": .10, "VEA": .075, "VWO": .05,
                                  "TLT": .15, "BNDX": .075, "GLD": .125,
                                  "TIP": .075, "DBC": .05}
    return books


# ----------------------------------------------------------------------- driver
def main():
    px = fetch()
    tr, me = monthly_tr(px)
    cash = tr["BIL"]
    print(f"WINDOW {me.index.min().date()} -> {me.index.max().date()}  "
          f"n_months={len(me)}  cols={list(px.columns)}")
    recent_lo = me.index.max() - pd.DateOffset(years=RECENT_YEARS)

    books = candidate_books()

    # ============ PART 1: GLOBAL vs US (trend-overlaid), monthly, no band ===========
    print("\n" + "=" * 92)
    print("PART 1  GLOBAL vs US-PP  (both TREND-OVERLAID, monthly rebalance, 3bps/side)")
    print("=" * 92)
    full_rows, rec_rows, books_net = {}, {}, {}
    for name, bw in books.items():
        res = run_book(tr, me, bw, cadence="M", band=0.0)
        net = res["net"]
        books_net[name] = net
        full_rows[name] = stats(net, cash) | {"ann_turn": res["ann_turnover"]}
        rec_rows[name] = stats(window(net, recent_lo), cash) | {"ann_turn": np.nan}

    def ptable(title, rows):
        print(f"\n  {title}")
        print(f"  {'book':22}{'CAGR':>7}{'Sharpe':>8}{'Sh_ex':>7}{'vol':>7}"
              f"{'maxDD':>8}{'worstYr':>9}{'annTurn':>9}")
        for n, st in rows.items():
            at = f"{st['ann_turn']*100:7.0f}%" if st.get('ann_turn')==st.get('ann_turn') else "    n/a"
            print(f"  {n:22}{st['CAGR']*100:6.1f}%{st['Sharpe']:8.2f}"
                  f"{st.get('Sh_ex',float('nan')):7.2f}{st['vol']*100:6.1f}%"
                  f"{st['maxDD']*100:7.1f}%{st['worst_yr']*100:8.1f}%{at:>9}")

    ptable(f"FULL SAMPLE {me.index.min().date()}..{me.index.max().date()}", full_rows)
    ptable(f"RECENT {RECENT_YEARS}y HOLDOUT (from {recent_lo.date()})", rec_rows)

    # per-episode total returns (where US did NOT dominate)
    EPISODES = {
        "2008 GFC (07-11..09-02)": ("2007-11", "2009-02"),
        "exUS/EM/cmdty lead 2009-2012": ("2009-03", "2012-12"),
        "US melt-up 2013-2021": ("2013-01", "2021-12"),
        "2022 stocks+bonds DOWN": ("2022-01", "2022-12"),
        f"recent {RECENT_YEARS}y": (recent_lo.strftime("%Y-%m"), None),
    }
    print("\n  PER-EPISODE TOTAL RETURN (honest US-vs-global across regimes)")
    hdr = f"  {'episode':30}"
    for n in books: hdr += f"{n[:13]:>14}"
    print(hdr)
    for lab, (lo, hi) in EPISODES.items():
        line = f"  {lab:30}"
        for n in books:
            seg = window(books_net[n], lo, hi).dropna()
            tot = (1 + seg).prod() - 1 if len(seg) else np.nan
            line += f"{tot*100:13.1f}%"
        print(line)

    # pick the base for Part 2: best full-sample Sharpe that also holds up recent,
    # but report so the verdict can prefer simplicity on a tie.
    rank = sorted(books, key=lambda n: -full_rows[n]["Sharpe"])
    print(f"\n  full-sample Sharpe rank: " +
          ", ".join(f"{n}={full_rows[n]['Sharpe']:.2f}" for n in rank))

    # ============ PART 2: REBALANCE MECHANICS (cadence x band) =====================
    print("\n" + "=" * 92)
    print("PART 2  REBALANCE MECHANICS -- cadence x no-trade band  (3bps/side)")
    print("=" * 92)
    # run on BOTH the US-PP base and the best global base, so the verdict is fair
    best_global = max(books, key=lambda n: full_rows[n]["Sharpe"] if n != "US-PP (current)" else -9)
    bases_for_p2 = {"US-PP (current)": books["US-PP (current)"],
                    best_global: books[best_global]}

    cadences = [("monthly", "M"), ("quarterly", "Q"), ("annual", "A")]
    bands = [0.0, 0.05, 0.10, 0.20]
    grid = {}
    for bname, bw in bases_for_p2.items():
        print(f"\n  --- BASE: {bname} ---")
        print(f"  {'cadence':10}{'band':>7}{'CAGR':>7}{'Sharpe':>8}{'maxDD':>8}"
              f"{'annTurn':>9}{'nTrades':>9}")
        for cad_lab, cad in cadences:
            for band in bands:
                res = run_book(tr, me, bw, cadence=cad, band=band)
                st = stats(res["net"], cash)
                grid[(bname, cad_lab, band)] = (st, res)
                print(f"  {cad_lab:10}{int(band*100):6d}%{st['CAGR']*100:6.1f}%"
                      f"{st['Sharpe']:8.2f}{st['maxDD']*100:7.1f}%"
                      f"{res['ann_turnover']*100:8.0f}%{res['n_trades']:9d}")

    # turnover/cost savings vs the monthly/no-band baseline, per base
    print("\n  TURNOVER / COST SAVINGS vs monthly-noband baseline (cost=annTurn*3bps)")
    for bname in bases_for_p2:
        base_res = grid[(bname, "monthly", 0.0)][1]
        base_turn = base_res["ann_turnover"]
        print(f"\n  base {bname}: monthly-noband annTurn={base_turn*100:.0f}%"
              f"  cost~{base_turn*COST_BPS/1e4*1e4:.0f}bps/yr")
        for (bn, cad, band), (st, res) in grid.items():
            if bn != bname:
                continue
            save = (base_turn - res["ann_turnover"]) / base_turn if base_turn else 0
            dsh = st["Sharpe"] - grid[(bname, "monthly", 0.0)][0]["Sharpe"]
            print(f"    {cad:10} band {int(band*100):3d}%  turn "
                  f"{res['ann_turnover']*100:5.0f}%  saved {save*100:5.0f}%  "
                  f"cost {res['ann_turnover']*COST_BPS:5.1f}bps/yr  dSharpe {dsh:+.2f}")

    # ---- save machine-readable summary for the writeup
    out = {
        "window": [str(me.index.min().date()), str(me.index.max().date())],
        "recent_lo": str(recent_lo.date()),
        "cost_bps": COST_BPS, "lookback_m": LOOKBACK_M,
        "full": {n: {k: (None if (isinstance(v,float) and v!=v) else round(float(v),4))
                     for k,v in s.items()} for n,s in full_rows.items()},
        "recent": {n: {k: (None if (isinstance(v,float) and v!=v) else round(float(v),4))
                       for k,v in s.items()} for n,s in rec_rows.items()},
        "best_global": best_global,
        "grid": {f"{b}|{c}|{int(bd*100)}": {
                    "CAGR": round(float(st["CAGR"]),4),
                    "Sharpe": round(float(st["Sharpe"]),4),
                    "maxDD": round(float(st["maxDD"]),4),
                    "ann_turn": round(float(res["ann_turnover"]),4),
                    "n_trades": res["n_trades"]}
                 for (b,c,bd),(st,res) in grid.items()},
    }
    with open(os.path.join(DATA, "summary.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nsaved {os.path.join(DATA,'summary.json')}")


if __name__ == "__main__":
    main()
