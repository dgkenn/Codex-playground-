#!/usr/bin/env python3
"""
ETF momentum SMALL-BANKROLL execution realism.

The deployable winner (ETF_DEPLOY.md, commit 1cf9cef) is backtested with
CONTINUOUS FRACTIONAL weights. At $1k a 20% slot is ~$200, but one share of
MTUM is ~$324 and SPY ~$742 -- you literally cannot hold a whole share in some
slots. Whole-share rounding -> cash drag + weight distortion the idealized
backtest ignores.

This module reuses the EXACT signal/gate math of etf_momentum.py but drives a
REAL dollar portfolio:
  * SIGNALS + idealized fractional backtest use ADJUSTED (total-return) prices.
  * Whole-share rounding uses RAW share prices (actual price per share you pay).
  * The dollar engine compounds an actual share-count portfolio; on each monthly
    rebalance it partial-steps (p=0.34) toward target weights, then rounds to the
    chosen execution mode (whole / fractional / greedy), pays costs, and parks
    the residual in cash (BIL).

Costs: commission-free ETFs + 3 bps/side of traded notional (same as the locked
backtest). No per-trade ticket fee (commission-free brokers).
"""
import numpy as np
import pandas as pd

ADJ = "/tmp/etfsmall_data/adj_prices.csv"
RAW = "/tmp/etfsmall_data/raw_prices.csv"
COST_BPS = 3.0
TBILL_ANN = 0.02
TRADING_DAYS = 252

# ---- locked universe (mirrors etf_momentum_live.py CORE_UNIVERSE) ----------
SECTORS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
STYLE = ["SPY", "QQQ", "IWM", "MTUM"]
INTL = ["EFA", "EEM", "EWJ", "EWZ", "EWG", "EWU", "FXI", "VGK"]
ASSETS = ["TLT", "IEF", "GLD", "DBC", "USO", "VNQ", "UUP", "SLV", "HYG", "LQD"]
CORE_UNIVERSE = sorted(set(SECTORS + STYLE + INTL + ASSETS))
CASH_TICKER = "BIL"
REGIME_ASSET = "SPY"

# cheaper-ETF substitution map for the small-account universe tweak.
# swap the highest-priced members for lower-priced ~equivalents.
CHEAP_SUBS = {
    "SPY": "SPLG",   # S&P500   742 -> 87
    "QQQ": "QQQ",    # keep (QQQM would be cheaper but not fetched; QQQ stays)
    "GLD": "IAU",    # gold     387 -> 79
    "MTUM": "MTUM",  # momentum 324 (no cheap clone in set; keep)
    "IWM": "IWM",    # small    293 (keep)
    "EFA": "SCHF",   # intl dev 105 -> 28
    "EEM": "VWO",    # emer mkt  68 -> 60 (modest)
    "VNQ": "VNQ",
    "LQD": "LQD",
}


def load(path):
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


def cash_series(px, idx):
    if CASH_TICKER in px and px[CASH_TICKER].notna().sum() > 250:
        c = px[CASH_TICKER].reindex(idx).ffill()
        first = c.first_valid_index()
        daily = (1 + TBILL_ANN) ** (1 / TRADING_DAYS)
        pre = c.copy()
        if first is not None:
            base = c.loc[first]
            mask = c.index < first
            n = mask.sum()
            if n > 0:
                factors = daily ** -np.arange(n, 0, -1)
                pre.loc[mask] = base * factors
        return pre.ffill().bfill()
    daily = (1 + TBILL_ANN) ** (1 / TRADING_DAYS)
    return pd.Series(daily ** np.arange(len(idx)), index=idx)


def risk_adj_momentum(px, asof, lookback_days):
    window = px.loc[:asof].tail(lookback_days + 1)
    if len(window) < lookback_days * 0.8:
        return pd.Series(dtype=float)
    rets = np.log(window).diff().dropna(how="all")
    total = np.log(window.iloc[-1] / window.iloc[0])
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    score = total / vol.replace(0, np.nan)
    valid = window.notna().sum() >= lookback_days * 0.8
    return score[valid].dropna()


def abs_momentum(px, asof, lookback_days, cash):
    window = px.loc[:asof].tail(lookback_days + 1)
    cwin = cash.loc[:asof].tail(lookback_days + 1)
    if len(window) < lookback_days * 0.8:
        return pd.Series(dtype=float)
    asset_ret = window.iloc[-1] / window.iloc[0] - 1
    cash_ret = cwin.iloc[-1] / cwin.iloc[0] - 1
    return asset_ret - cash_ret


def target_weights(adj, universe, d, lookback_days, K, dual, regime,
                   regime_ma, cash):
    """LOCKED-config target weight vector (Series over universe) as of date d."""
    if regime:
        ra = adj[REGIME_ASSET].loc[:d].dropna()
        risk_on = len(ra) >= regime_ma and ra.iloc[-1] > ra.tail(regime_ma).mean()
    else:
        risk_on = True
    target = pd.Series(0.0, index=universe)
    if not risk_on:
        return target
    score = risk_adj_momentum(adj[universe], d, lookback_days).dropna()
    if dual:
        am = abs_momentum(adj[universe], d, lookback_days, cash)
        score = score[am.reindex(score.index) > 0]
    score = score.sort_values(ascending=False)
    picks = score.head(K).index.tolist()
    if picks:
        target[picks] = 1.0 / len(picks)
    return target


def stats(net, freq=TRADING_DAYS):
    net = net.dropna()
    if len(net) < 30:
        return dict(CAGR=np.nan, Sharpe=np.nan, maxDD=np.nan, vol=np.nan, n=len(net))
    eq = (1 + net).cumprod()
    yrs = len(net) / freq
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sharpe = net.mean() / net.std() * np.sqrt(freq) if net.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(CAGR=cagr, Sharpe=sharpe, maxDD=dd, vol=net.std() * np.sqrt(freq),
                n=len(net))


def equity_stats(eq, freq=TRADING_DAYS):
    """Stats from an equity curve (Series indexed by date)."""
    eq = eq.dropna()
    if len(eq) < 30:
        return dict(CAGR=np.nan, Sharpe=np.nan, maxDD=np.nan, vol=np.nan, n=len(eq))
    ret = eq.pct_change().dropna()
    yrs = len(eq) / freq
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(freq) if ret.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(CAGR=cagr, Sharpe=sharpe, maxDD=dd, vol=ret.std() * np.sqrt(freq),
                n=len(eq))


def rebal_dates_for(idx, day_of_month=None):
    """Monthly rebalance dates.

    day_of_month=None -> month-END (the locked default).
    day_of_month=k    -> the first trading day on/after the k-th of each month.
    """
    s = pd.Series(idx, index=idx)
    if day_of_month is None:
        me = s.groupby([idx.year, idx.month]).last()
        return list(pd.to_datetime(me.values))
    out = []
    for (y, m), grp in s.groupby([idx.year, idx.month]):
        cand = grp[grp.index.day >= day_of_month]
        out.append(cand.iloc[0] if len(cand) else grp.iloc[-1])
    return list(pd.to_datetime(out))


def simulate_dollar(adj, raw, universe, capital, mode="whole",
                    lookback_days=126, K=5, dual=True, regime=True,
                    regime_ma=200, partial=0.34, cost_bps=COST_BPS,
                    start="2000-06-01", end=None, rebal_day=None):
    """Drive a REAL dollar share-count portfolio.

    mode:
      'fractional' -> fractional shares allowed (== idealized weights, the ideal).
      'whole'      -> round each slot to whole shares (truncate), residual -> cash.
      'greedy'     -> hold-what-fits: after whole-share buy, sweep leftover cash
                      into the single highest-ranked affordable pick (1 more share).
    Returns (equity_series, diag) where diag has cash-drag / distortion metrics.
    """
    need = sorted(set(universe + [REGIME_ASSET, CASH_TICKER]))
    adj = adj[[c for c in need if c in adj.columns]].copy()
    raw_px = raw.reindex(adj.index).ffill()
    idx = adj.index
    cash = cash_series(adj, idx)
    cash_daily_ret = cash.pct_change().fillna(0.0)

    rdates = rebal_dates_for(idx, rebal_day)
    rdates = [d for d in rdates if (start is None or d >= pd.Timestamp(start))
              and (end is None or d <= pd.Timestamp(end))]
    rset = set(rdates)

    # --- numpy views of the hot arrays (universe order) -------------------
    rawA = raw_px[universe].to_numpy(dtype=float)        # [days, n]
    adjA = adj[universe].to_numpy(dtype=float)
    rawA = np.where(np.isnan(rawA), 0.0, rawA)
    cashret = cash_daily_ret.to_numpy(dtype=float)
    n = len(universe)
    uidx = {t: j for j, t in enumerate(universe)}

    # portfolio state: shares per ticker + cash dollars
    shares = {t: 0.0 for t in universe}
    sh = np.zeros(n)
    cash_usd = float(capital)

    eq_curve = {}
    cash_drag_log = []      # cash weight just after each rebalance
    distort_log = []        # L1 weight distortion vs ideal target at rebalance

    # for ideal target weight ladder we need the partial-stepped TARGET path
    ideal_w = pd.Series(0.0, index=universe)   # the continuous partial-stepped weight

    start_i = idx.get_indexer([pd.Timestamp(start)], method="bfill")[0] if start else 0
    for i in range(start_i, len(idx)):
        d = idx[i]
        # mark-to-market with TODAY's raw prices (share count * price + cash)
        # use raw price for share value (what you'd liquidate at); total-return
        # captured because dividends are reinvested as cash on ex-date? -> we add
        # dividend cash via adjusted/raw ratio drift. Simpler+honest: value shares
        # at adjusted-relative growth. We instead value at raw price and credit
        # dividends as cash (see below). To stay consistent w/ the TR backtest we
        # value shares using adjusted prices scaled to share count at cost basis
        # is complex; instead we run the dollar engine on RAW prices and ADD the
        # dividend yield as cash. Approximation note in the doc.
        pxrow = rawA[i]
        port_val = cash_usd + float(sh @ pxrow)
        eq_curve[d] = port_val

        # accrue dividends daily: adjusted return minus raw return = dividend drip
        if i > start_i:
            p0r, p1r = rawA[i - 1], pxrow
            p0a, p1a = adjA[i - 1], adjA[i]
            with np.errstate(divide="ignore", invalid="ignore"):
                tr = np.where(p0a > 0, p1a / p0a - 1.0, 0.0)
                pr = np.where(p0r > 0, p1r / p0r - 1.0, 0.0)
            div = np.nan_to_num(tr - pr)
            div = np.clip(div, 0.0, None)
            cash_usd += float((sh * p0r * div).sum())
            cash_usd *= (1.0 + cashret[i])

        if d in rset:
            tgt = target_weights(adj, universe, d, lookback_days, K, dual,
                                  regime, regime_ma, cash)
            # partial step of the IDEAL continuous weights
            ideal_w = ideal_w + partial * (tgt - ideal_w)
            ideal_w = ideal_w.clip(lower=0.0)

            port_val = cash_usd + sum(shares[t] * raw_px[t].iloc[i]
                                      for t in universe
                                      if raw_px[t].iloc[i] == raw_px[t].iloc[i])
            desired_d = {t: ideal_w[t] * port_val for t in universe}

            # --- execute toward desired_d in the chosen mode ---
            prices = {t: raw_px[t].iloc[i] for t in universe}
            new_shares = dict(shares)
            traded_notional = 0.0

            if mode == "fractional":
                for t in universe:
                    p = prices[t]
                    if p != p or p <= 0:
                        continue
                    tgt_sh = desired_d[t] / p
                    traded_notional += abs(tgt_sh - shares[t]) * p
                    new_shares[t] = tgt_sh
            else:
                # whole-share: SELLs first (free cash), then BUYs truncating
                for t in universe:
                    p = prices[t]
                    if p != p or p <= 0:
                        continue
                    tgt_sh = np.floor(desired_d[t] / p + 1e-9)
                    if tgt_sh < shares[t]:  # selling (incl. to-zero)
                        traded_notional += abs(tgt_sh - shares[t]) * p
                        new_shares[t] = tgt_sh
                # recompute available cash after sells
                cash_after = port_val - sum(new_shares[t] * prices[t]
                                            for t in universe
                                            if prices[t] == prices[t])
                # BUYs in rank order of desired weight (largest first)
                order = sorted(universe, key=lambda t: -ideal_w[t])
                for t in order:
                    p = prices[t]
                    if p != p or p <= 0 or ideal_w[t] <= 0:
                        continue
                    want = np.floor(desired_d[t] / p + 1e-9)
                    add = want - new_shares[t]
                    if add > 0:
                        afford = np.floor(cash_after / p + 1e-9)
                        add = min(add, afford)
                        if add > 0:
                            new_shares[t] += add
                            cash_after -= add * p
                            traded_notional += add * p
                if mode == "greedy":
                    # hold-what-fits: sweep leftover cash into top affordable picks
                    for t in order:
                        p = prices[t]
                        if p != p or p <= 0 or ideal_w[t] <= 0:
                            continue
                        while cash_after >= p:
                            new_shares[t] += 1
                            cash_after -= p
                            traded_notional += p

            shares = new_shares
            sh = np.array([shares[t] for t in universe])  # resync numpy view
            invested = sum(shares[t] * prices[t] for t in universe
                           if prices[t] == prices[t])
            cash_usd = port_val - invested
            # pay cost on traded notional
            cost = traded_notional * cost_bps / 1e4
            cash_usd -= cost

            # diagnostics (only when risk-on / something targeted)
            if tgt.sum() > 0:
                cash_w = cash_usd / port_val if port_val > 0 else 0.0
                cash_drag_log.append((d, cash_w))
                actual_w = pd.Series({t: shares[t] * prices[t] / port_val
                                      for t in universe})
                # distortion vs the partial-stepped ideal weights
                dist = (actual_w - ideal_w).abs().sum()
                distort_log.append((d, dist))

    eq = pd.Series(eq_curve).sort_index()
    diag = dict(
        avg_cash_drag=np.mean([c for _, c in cash_drag_log]) if cash_drag_log else np.nan,
        avg_distortion=np.mean([c for _, c in distort_log]) if distort_log else np.nan,
        n_rebal=len(rdates),
    )
    return eq, diag
