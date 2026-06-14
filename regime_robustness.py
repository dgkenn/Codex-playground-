#!/usr/bin/env python3
"""
REGIME-ROBUSTNESS of the static recommendation, on a 1972-2023 long-history reconstruction.
============================================================================================
Does the Permanent-Portfolio / risk-parity edge survive the regimes the ETF-era (post-2007)
sample never saw -- the 1970s stagflation bear, the 1970s-1981 RISING-RATE bond bear (the
static's kryptonite), 1994, 2008, and 2022 (stocks AND bonds down together)?  And does a
simple TIME-SERIES TREND overlay -- which can rotate OUT of falling bonds/stocks into cash,
the spirit of the project's active book, computable on the long series -- materially improve
regime-robustness?

Monthly TOTAL-RETURN series from regime_data.py (Shiller S&P TR + reconstructed Treasury TR
from GS10/GS30 yields + datahub gold + Ken French RF cash). See REGIME_ROBUSTNESS.md for the
full source/method/caveat statement.  All static logic mirrors the committed static_allocation.py
(fixed-weight monthly rebalance with cost on turnover; inverse-vol risk parity), at MONTHLY
frequency on the long series.  COSTS: 5 bps/side on rebalance turnover (>= the committed 3 bps,
to be conservative on the higher-turnover trend overlay).
"""
import numpy as np
import pandas as pd

TR_CSV = "/tmp/regime_data/monthly_tr.csv"
COST_BPS = 5.0          # bps/side on rebalance turnover (conservative vs committed 3 bps)
MPY = 12                # months/yr

# building blocks present in the long series
RISK_ASSETS = ["STOCKS", "UST10", "UST30", "GOLD"]


# ----------------------------- stats -----------------------------------------
def stats(net):
    net = net.dropna()
    if len(net) < 24:
        return dict(CAGR=np.nan, Sharpe=np.nan, vol=np.nan, maxDD=np.nan, worst_yr=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / MPY
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = net.std() * np.sqrt(MPY)
    sharpe = net.mean() / net.std() * np.sqrt(MPY) if net.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + net).groupby(net.index.year).prod() - 1
    return dict(CAGR=cagr, Sharpe=sharpe, vol=vol, maxDD=dd, worst_yr=yr.min(), n=len(net))


def sharpe_excess(net, cash):
    """Sharpe on EXCESS return over cash (the honest risk-adjusted metric)."""
    ex = (net - cash).dropna()
    if len(ex) < 24 or ex.std() == 0:
        return np.nan
    return ex.mean() / ex.std() * np.sqrt(MPY)


# ----------------------------- portfolios ------------------------------------
def fixed_weight(tr, weights, cost_bps=COST_BPS):
    """Fixed-weight, monthly rebalance to target, cost on turnover. Mirrors static_allocation.py."""
    cols = list(weights.keys())
    R = tr[cols].fillna(0.0).values
    tgt = np.array([weights[c] for c in cols], float)
    tgt = tgt / tgt.sum()
    w = tgt.copy()
    out = np.empty(len(tr))
    for i in range(len(tr)):
        out[i] = float(np.dot(w, R[i]))
        w = w * (1 + R[i])
        s = w.sum()
        if s != 0:
            w = w / s
        # monthly rebalance every step
        turnover = np.abs(tgt - w).sum()
        out[i] -= turnover * cost_bps / 1e4
        w = tgt.copy()
    return pd.Series(out, index=tr.index)


def inverse_vol(tr, assets, vol_win=12, cost_bps=COST_BPS):
    """Risk-parity-lite: monthly inverse-vol weights, rebalanced monthly. Mirrors static_allocation.py."""
    R = tr[assets]
    vol = R.rolling(vol_win).std() * np.sqrt(MPY)
    iv = 1.0 / vol.replace(0, np.nan)
    W = iv.div(iv.sum(axis=1), axis=0)
    W = W.shift(1)  # use last month's weights this month
    port = (W * R).sum(axis=1)
    turnover = W.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * cost_bps / 1e4
    return (port - cost).dropna()


def trend_overlay(tr, assets, cash_col="CASH", lookback=12, cost_bps=COST_BPS, weights=None):
    """TIME-SERIES (absolute) momentum overlay -- the active book's spirit on the long series.
    Each asset is held only when its trailing `lookback`-month total return > 0 (trend up),
    else that sleeve goes to CASH.  Base weights `weights` (default equal across assets);
    when an asset is OFF, its weight parks in cash.  Monthly rebalance, cost on turnover.
    This is the regime-adaptive candidate: it can rotate OUT of falling bonds/stocks.
    """
    if weights is None:
        weights = {a: 1.0 / len(assets) for a in assets}
    base = pd.Series(weights)
    base = base / base.sum()
    # signal: trailing lookback-month cumulative return > 0, applied with a 1-month lag
    cum = (1 + tr[assets]).rolling(lookback).apply(np.prod, raw=True) - 1
    sig = (cum > 0).astype(float).shift(1).fillna(0.0)  # 1=on, 0=off (lagged, no lookahead)
    # weight on each asset = base if on else 0; remainder -> cash
    Wassets = sig.mul(base, axis=1)
    Wcash = 1.0 - Wassets.sum(axis=1)
    R = tr[assets]
    cashr = tr[cash_col]
    port = (Wassets * R).sum(axis=1) + Wcash * cashr
    # turnover across all sleeves (asset legs + cash leg)
    full = Wassets.copy()
    full["CASH"] = Wcash
    turnover = full.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * cost_bps / 1e4
    return (port - cost).dropna()


# ----------------------------- candidate set ---------------------------------
def build_candidates(tr):
    c = {}
    # PERMANENT PORTFOLIO: 25% each stocks / long-bond / gold / cash  (PP uses the LONG bond)
    c["Permanent Portfolio"] = fixed_weight(tr, {"STOCKS": .25, "UST30": .25, "GOLD": .25, "CASH": .25})
    # 60/40 stocks / 10y Treasuries
    c["60/40"] = fixed_weight(tr, {"STOCKS": .60, "UST10": .40})
    # Risk-parity-lite (inverse-vol) over stocks/10y/30y/gold
    c["Risk-Parity (inv-vol)"] = inverse_vol(tr, ["STOCKS", "UST10", "UST30", "GOLD"])
    # 100% stocks reference
    c["100% Stocks"] = tr["STOCKS"].copy()
    # ---- TREND overlays (the active book's spirit; regime-adaptive) ----
    # Trend overlay on the PP sleeves: hold each of stocks/long-bond/gold only when trend up, else cash
    c["PP + Trend overlay"] = trend_overlay(
        tr, ["STOCKS", "UST30", "GOLD"], lookback=12,
        weights={"STOCKS": 1/3, "UST30": 1/3, "GOLD": 1/3})
    # Trend overlay on a 4-asset all-weather set incl 10y
    c["Trend (4-asset)"] = trend_overlay(
        tr, ["STOCKS", "UST10", "UST30", "GOLD"], lookback=12)
    # Risk-parity WITH a trend filter: inv-vol weights, but zero any asset whose 12m trend is down
    c["Risk-Parity + Trend filter"] = risk_parity_trend(tr, ["STOCKS", "UST10", "UST30", "GOLD"])
    return c


def risk_parity_trend(tr, assets, vol_win=12, lookback=12, cost_bps=COST_BPS, cash_col="CASH"):
    """Inverse-vol weights, but an asset is set to ZERO (parked in cash) when its 12m trend is
    down. The de-risking variant of risk parity -- can shed falling bonds in a rising-rate regime."""
    R = tr[assets]
    vol = R.rolling(vol_win).std() * np.sqrt(MPY)
    iv = 1.0 / vol.replace(0, np.nan)
    cum = (1 + R).rolling(lookback).apply(np.prod, raw=True) - 1
    on = (cum > 0).astype(float)
    iv_on = iv * on
    W = iv_on.div(iv_on.sum(axis=1).replace(0, np.nan), axis=0)  # renormalize among ON assets
    # if ALL off, hold cash (W all nan -> 0, remainder to cash)
    W = W.shift(1)
    Wsum = W.sum(axis=1)
    cashw = (1.0 - Wsum).clip(lower=0.0)
    port = (W * R).sum(axis=1) + cashw * tr[cash_col]
    full = W.fillna(0.0).copy()
    full["CASH"] = cashw
    turnover = full.diff().abs().sum(axis=1).fillna(0.0)
    return (port - turnover * cost_bps / 1e4).dropna()


# ----------------------------- regimes ---------------------------------------
REGIMES = {
    "(a) 1970s stagflation+bear 1973-1974": ("1973-01", "1974-12"),
    "(a') full 1970s 1972-1979": ("1972-01", "1979-12"),
    "(b) bond BEAR / rising rates 1972-1981": ("1972-01", "1981-09"),
    "(c) 1994 bond crash": ("1994-01", "1994-12"),
    "(d) 2008 GFC": ("2007-11", "2009-02"),
    "(e) 2022 stocks+bonds DOWN": ("2022-01", "2022-12"),
    "BOND BULL 2007-2024 (the tailwind)": ("2007-01", "2023-06"),
    "FULL 1972-2023": ("1972-01", "2023-06"),
}


def window(s, lo, hi):
    return s[(s.index >= pd.Timestamp(lo)) & (s.index <= pd.Timestamp(hi))]


def period_total(net):
    net = net.dropna()
    if len(net) == 0:
        return np.nan
    return (1 + net).prod() - 1


def period_maxdd(net):
    net = net.dropna()
    if len(net) == 0:
        return np.nan
    eq = (1 + net).cumprod()
    return (eq / eq.cummax() - 1).min()


# ----------------------------- correlation regime ----------------------------
def correlation_analysis(tr):
    """Rolling 36m stock-bond correlation, and each candidate's excess-Sharpe in POSITIVE vs
    NEGATIVE correlation months (the static's edge is structurally a neg-corr phenomenon)."""
    corr = tr["STOCKS"].rolling(36).corr(tr["UST10"])
    pos = corr > 0
    neg = corr <= 0
    cands = build_candidates(tr)
    rows = {}
    for name, net in cands.items():
        net = net.reindex(tr.index)
        cash = tr["CASH"]
        sp_pos = sharpe_excess(net[pos].dropna(), cash[pos])
        sp_neg = sharpe_excess(net[neg].dropna(), cash[neg])
        rows[name] = dict(Sharpe_posCorr=sp_pos, Sharpe_negCorr=sp_neg,
                          drop=(sp_neg - sp_pos))
    return corr, pd.DataFrame(rows).T, int(pos.sum()), int(neg.sum())


def decade_corr(tr):
    """Stock-bond correlation by decade -- shows the negative-corr 2000s/2010s vs positive 70s-90s."""
    out = {}
    for lo, hi, lab in [("1972-01","1979-12","1970s"),("1980-01","1989-12","1980s"),
                        ("1990-01","1999-12","1990s"),("2000-01","2009-12","2000s"),
                        ("2010-01","2019-12","2010s"),("2020-01","2023-06","2020s")]:
        s = window(tr["STOCKS"], lo, hi); b = window(tr["UST10"], lo, hi)
        out[lab] = round(s.corr(b), 2)
    return out


# ----------------------------- driver ----------------------------------------
def main():
    tr = pd.read_csv(TR_CSV, index_col=0, parse_dates=True)
    print("WINDOW", tr.index.min().date(), "->", tr.index.max().date(), "n=", len(tr))
    cands = build_candidates(tr)

    print("\n=== FULL-SAMPLE STATS (1972-2023, monthly, net 5bps/side) ===")
    print(f"{'candidate':30} {'CAGR':>7} {'Sharpe':>7} {'Sh_ex':>7} {'vol':>6} {'maxDD':>7} {'worstYr':>8}")
    for name, net in cands.items():
        st = stats(net)
        spx = sharpe_excess(net, tr["CASH"])
        print(f"{name:30} {st['CAGR']*100:6.1f}% {st['Sharpe']:7.2f} {spx:7.2f} "
              f"{st['vol']*100:5.1f}% {st['maxDD']*100:6.1f}% {st['worst_yr']*100:7.1f}%")

    print("\n=== PER-REGIME TOTAL RETURN (and maxDD) ===")
    hdr = f"{'regime':42}"
    for name in cands: hdr += f"{name[:14]:>15}"
    print(hdr)
    for rlab, (lo, hi) in REGIMES.items():
        line = f"{rlab:42}"
        for name, net in cands.items():
            t = period_total(window(net, lo, hi))
            line += f"{t*100:14.1f}%"
        print(line)
    print("\n  (maxDD within each regime)")
    for rlab, (lo, hi) in REGIMES.items():
        line = f"{rlab:42}"
        for name, net in cands.items():
            d = period_maxdd(window(net, lo, hi))
            line += f"{d*100:14.1f}%"
        print(line)

    print("\n=== STOCK-BOND CORRELATION BY DECADE (STOCKS vs UST10) ===")
    print(decade_corr(tr))

    print("\n=== EXCESS-SHARPE in POSITIVE vs NEGATIVE stock-bond-corr months (36m roll) ===")
    corr, cdf, npos, nneg = correlation_analysis(tr)
    print(f"  positive-corr months: {npos}   negative-corr months: {nneg}")
    print(f"{'candidate':30} {'Sh(pos)':>9} {'Sh(neg)':>9} {'neg-pos':>9}")
    for name, r in cdf.iterrows():
        print(f"{name:30} {r['Sharpe_posCorr']:9.2f} {r['Sharpe_negCorr']:9.2f} {r['drop']:9.2f}")

    # save machine-readable for the writeup
    summ = {}
    for name, net in cands.items():
        st = stats(net); st["Sharpe_excess"] = sharpe_excess(net, tr["CASH"])
        summ[name] = st
    pd.DataFrame(summ).T.to_csv("/tmp/regime_data/candidate_fullstats.csv")
    cdf.to_csv("/tmp/regime_data/candidate_corr_regime.csv")
    # per-regime table
    rt = {}
    for rlab,(lo,hi) in REGIMES.items():
        rt[rlab] = {name: period_total(window(net,lo,hi)) for name,net in cands.items()}
    pd.DataFrame(rt).T.to_csv("/tmp/regime_data/candidate_regime_returns.csv")
    print("\nsaved candidate_*.csv to /tmp/regime_data/")


if __name__ == "__main__":
    main()
