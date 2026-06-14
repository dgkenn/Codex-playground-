#!/usr/bin/env python3
"""
etf_momentum_live.py — LIVE / PAPER harness for the WINNING strategy of this
project: cross-asset ETF risk-adjusted momentum (the deployable risk-premium
edge for a US retail small bankroll).

This script does NOT re-optimize anything. It REUSES the LOCKED config validated
in ETF_MOMENTUM.md (commit e3e2d57) and the engine in etf_momentum.py:

  LOCKED CONFIG
  -------------
  - Universe: ~30 liquid cross-asset ETFs (US sectors XLK/XLE/XLF/XLV/XLI/XLY/
    XLP/XLU/XLB; style SPY/QQQ/IWM/MTUM; intl/country EFA/EEM/EWJ/EWZ/EWG/EWU/
    FXI/VGK; bonds TLT/IEF; gold GLD; commodities DBC/USO; REIT VNQ; dollar UUP;
    plus SLV/HYG/LQD). Cash leg = BIL (1-3mo T-bill ETF).
  - Signal: risk-adjusted momentum = (trailing 6-month total return) / (trailing
    annualized vol), computed cross-sectionally, ranked.
  - Hold: top K=5 equal-weight; remainder in BIL (cash).
  - Gates: (a) DUAL / absolute filter — only hold a ranked ETF if its 6-month
    total return beats cash; (b) SPY > 200-day MA regime gate — if SPY is below
    its 200d MA, go 100% cash.
  - Rebalance: MONTHLY, PARTIAL (move ~1/3, p=0.34, of the way toward target
    each month) to damp turnover/whipsaw.
  - Optional crypto-proxy members (IBIT/MSTR/COIN/GBTC) via --crypto-proxy.

WHAT THIS SCRIPT DOES
  (a) Fetches current daily dividend-adjusted ETF history via yfinance.
  (b) Computes the LOCKED-config TARGET portfolio for THIS month (which tickers,
      what weights, or "GO TO CASH" if the regime/absolute gate says so).
  (c) Prints a clean rebalance report: current vs target weights and the ~1/3
      partial-rebalance trades to place (in $ and approx whole shares).
  (d) --paper-track mode: appends a dated record (date, holdings, weights, gate
      state, paper equity) to a JSONL so a real forward PAPER track accumulates
      each run. Idempotent per (mode, month, universe): re-running in the same
      month overwrites that month's row rather than duplicating it.

IT IS PAPER ONLY. No brokerage API, no real orders, no secrets. The operator
reads the report and places trades manually (see ETF_DEPLOY.md runbook).

If yfinance is unreachable, the script DEGRADES GRACEFULLY: it tells you so,
falls back to a cached price file if one exists, and exits non-zero without
writing a bogus paper record.

USAGE
  python etf_momentum_live.py                       # base universe, $1k, dry report
  python etf_momentum_live.py --crypto-proxy        # include crypto-proxy members
  python etf_momentum_live.py --capital 10000       # size the trade report to $10k
  python etf_momentum_live.py --paper-track         # also append to the JSONL track
  python etf_momentum_live.py --holdings holdings.json   # supply your CURRENT positions

  --holdings is a JSON map {"XLK": 210.0, "GLD": 195.0, "CASH": 600.0} of CURRENT
  dollar values per ticker (CASH = uninvested/BIL). If omitted, current = all cash.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import datetime as dt

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# LOCKED CONFIG (do NOT re-optimize; mirrors etf_momentum.py / ETF_MOMENTUM.md)
# ---------------------------------------------------------------------------
SECTORS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
STYLE = ["SPY", "QQQ", "IWM", "MTUM"]
INTL = ["EFA", "EEM", "EWJ", "EWZ", "EWG", "EWU", "FXI", "VGK"]
ASSETS = ["TLT", "IEF", "GLD", "DBC", "USO", "VNQ", "UUP", "SLV", "HYG", "LQD"]
CRYPTO_PROXY = ["IBIT", "MSTR", "COIN", "GBTC"]
CASH_TICKER = "BIL"          # 1-3 month T-bill ETF = the cash leg
REGIME_ASSET = "SPY"

CORE_UNIVERSE = sorted(set(SECTORS + STYLE + INTL + ASSETS))

# locked hyper-parameters
LOOKBACK_DAYS = 126          # ~6 months of trading days
K = 5                        # top-K equal weight
REGIME_MA = 200              # SPY > 200d MA regime gate
PARTIAL = 0.34               # ~1/3 toward target each rebalance
TRADING_DAYS = 252

DEFAULT_CACHE = "/tmp/etfdep_data/live_prices.csv"
DEFAULT_TRACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "etf_paper_track.jsonl")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch_prices(tickers, cache_path=DEFAULT_CACHE, lookback_years=3):
    """Fetch daily dividend-adjusted closes via yfinance.

    Returns (px_df, source) where source in {"yfinance", "cache"}.
    Raises RuntimeError if neither yfinance nor a cache is usable.
    """
    tickers = sorted(set(tickers))
    px = None
    try:
        import yfinance as yf
        period = f"{lookback_years + 1}y"   # pad so 6m lookback always full
        raw = yf.download(tickers, period=period, auto_adjust=True,
                          progress=False, threads=True)
        if raw is not None and len(raw) > 0:
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
            if isinstance(close, pd.Series):
                close = close.to_frame(tickers[0])
            close = close.dropna(how="all").sort_index()
            # need a meaningful amount of history for the 200d/126d windows
            if len(close) >= REGIME_MA + 10:
                px = close
    except Exception as e:  # network / parse / import — degrade gracefully
        print(f"[warn] yfinance fetch failed: {e!r}", file=sys.stderr)

    if px is not None:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            px.to_csv(cache_path)
        except Exception:
            pass
        return px, "yfinance"

    # --- graceful degradation: fall back to cache ---------------------------
    if os.path.exists(cache_path):
        print(f"[warn] yfinance unreachable; falling back to cached prices at "
              f"{cache_path}", file=sys.stderr)
        cached = pd.read_csv(cache_path, index_col=0, parse_dates=True).sort_index()
        return cached, "cache"

    raise RuntimeError(
        "yfinance is unreachable and no cached price file exists at "
        f"{cache_path}. Cannot compute a target portfolio. Try again when "
        "Yahoo is reachable.")


def cash_index(px):
    """Daily T-bill total-return index from BIL; flat 2%/yr synthetic if absent."""
    if CASH_TICKER in px.columns and px[CASH_TICKER].notna().sum() > 60:
        return px[CASH_TICKER].ffill().bfill()
    daily = (1 + 0.02) ** (1 / TRADING_DAYS)
    return pd.Series(daily ** np.arange(len(px.index)), index=px.index)


# ---------------------------------------------------------------------------
# Signal / gates (identical math to etf_momentum.py)
# ---------------------------------------------------------------------------
def risk_adj_momentum(px, asof, lookback_days=LOOKBACK_DAYS):
    window = px.loc[:asof].tail(lookback_days + 1)
    if len(window) < lookback_days * 0.8:
        return pd.Series(dtype=float)
    rets = np.log(window).diff().dropna(how="all")
    total = np.log(window.iloc[-1] / window.iloc[0])
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    score = total / vol.replace(0, np.nan)
    valid = window.notna().sum() >= lookback_days * 0.8
    return score[valid].dropna()


def abs_momentum_vs_cash(px, asof, cash, lookback_days=LOOKBACK_DAYS):
    window = px.loc[:asof].tail(lookback_days + 1)
    cwin = cash.loc[:asof].tail(lookback_days + 1)
    if len(window) < lookback_days * 0.8:
        return pd.Series(dtype=float)
    asset_ret = window.iloc[-1] / window.iloc[0] - 1
    cash_ret = cwin.iloc[-1] / cwin.iloc[0] - 1
    return asset_ret - cash_ret


def regime_on(px, asof, ma=REGIME_MA):
    ra = px[REGIME_ASSET].loc[:asof].dropna()
    if len(ra) < ma:
        return False, np.nan, np.nan
    ma_val = ra.tail(ma).mean()
    return bool(ra.iloc[-1] > ma_val), float(ra.iloc[-1]), float(ma_val)


def compute_target(px, universe, asof=None):
    """Return the LOCKED-config target portfolio as a dict.

    Keys: weights (ticker->weight summing to <=1; remainder is CASH), picks,
    scores, regime fields, reason.
    """
    if asof is None:
        asof = px.index[-1]
    asof = pd.Timestamp(asof)
    cash = cash_index(px)
    avail = [t for t in universe if t in px.columns]
    sub = px[avail]

    risk_state, spy_last, spy_ma = regime_on(px, asof)
    weights = {t: 0.0 for t in avail}

    if not risk_state:
        return dict(asof=asof, weights=weights, picks=[], scores={},
                    regime_on=False, spy_last=spy_last, spy_ma=spy_ma,
                    cash_weight=1.0,
                    reason="REGIME GATE OFF: SPY below its 200-day MA -> 100% CASH")

    score = risk_adj_momentum(sub, asof).dropna()
    am = abs_momentum_vs_cash(sub, asof, cash)
    # DUAL / absolute filter: keep only ETFs whose 6m return beats cash
    score = score[am.reindex(score.index) > 0]
    score = score.sort_values(ascending=False)
    picks = score.head(K).index.tolist()

    if not picks:
        return dict(asof=asof, weights=weights, picks=[],
                    scores=score.round(4).to_dict(),
                    regime_on=True, spy_last=spy_last, spy_ma=spy_ma,
                    cash_weight=1.0,
                    reason="ABSOLUTE FILTER: nothing beats cash -> 100% CASH")

    w = 1.0 / len(picks)
    for t in picks:
        weights[t] = w
    return dict(asof=asof, weights=weights, picks=picks,
                scores=score.head(K).round(4).to_dict(),
                regime_on=True, spy_last=spy_last, spy_ma=spy_ma,
                cash_weight=1.0 - sum(weights.values()),
                reason=f"RISK-ON: hold top {len(picks)} by 6m risk-adj momentum")


# ---------------------------------------------------------------------------
# Partial-rebalance trade list
# ---------------------------------------------------------------------------
def load_holdings(path, universe):
    """Load current $ holdings; default = all cash."""
    cur = {t: 0.0 for t in universe}
    cur["CASH"] = 0.0
    if path and os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        for k, v in data.items():
            cur[k] = cur.get(k, 0.0) + float(v)
    return cur


def build_rebalance(target, current_dollars, last_prices, partial=PARTIAL,
                    capital=None):
    """Compute current vs target vs partial-step weights and the trades to place.

    current_dollars: dict ticker-> $ (CASH key allowed).
    If holdings sum to ~0 (fresh start), `capital` seeds the dollar base and is
    treated as all-cash, so the partial step produces real first-month BUYs.
    Returns a structured dict for printing + the partial target weights.
    """
    total = sum(current_dollars.values())
    if total <= 0 and capital and capital > 0:
        # fresh start: all cash, so partial step buys ~partial*target this month
        current_dollars = dict(current_dollars)
        current_dollars["CASH"] = float(capital)
        total = float(capital)
    if total <= 0:
        total = 0.0
    tgt_w = target["weights"]
    all_tickers = sorted(set(list(tgt_w) + [k for k in current_dollars if k != "CASH"]))

    cur_w = {}
    for t in all_tickers:
        cur_w[t] = (current_dollars.get(t, 0.0) / total) if total > 0 else 0.0

    # partial step: move PARTIAL of the way from current to target weight
    step_w = {}
    for t in all_tickers:
        c = cur_w.get(t, 0.0)
        g = tgt_w.get(t, 0.0)
        step_w[t] = c + partial * (g - c)

    rows = []
    for t in all_tickers:
        c_d = current_dollars.get(t, 0.0)
        step_d = step_w[t] * total
        trade_d = step_d - c_d
        px = last_prices.get(t, np.nan)
        shares = (trade_d / px) if (px and not np.isnan(px)) else np.nan
        rows.append(dict(ticker=t, cur_w=cur_w.get(t, 0.0), tgt_w=tgt_w.get(t, 0.0),
                         step_w=step_w[t], cur_d=c_d, step_d=step_d,
                         trade_d=trade_d, price=px, shares=shares))
    cash_step = 1.0 - sum(step_w.values())
    return dict(total=total, rows=rows, cash_cur=current_dollars.get("CASH", 0.0),
                cash_step_w=cash_step, partial=partial, step_w=step_w)


# ---------------------------------------------------------------------------
# Paper track (JSONL)
# ---------------------------------------------------------------------------
def paper_track(track_path, target, last_prices, capital, universe_tag, crypto):
    """Append/update a dated paper-track record. Idempotent per (month,tag).

    Paper equity model: a pure paper portfolio that ACTUALLY rebalances FULLY to
    the target each month (the track is a clean forward record of the signal, not
    of partial-rebalance path-dependence). Equity compounds from the prior row's
    equity using realized returns since the prior run, applied to the prior row's
    target weights. First run seeds equity = capital.
    """
    month_key = pd.Timestamp(target["asof"]).strftime("%Y-%m")
    rows = []
    if os.path.exists(track_path):
        with open(track_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    same_tag = [r for r in rows if r.get("universe") == universe_tag]
    prior = same_tag[-1] if same_tag else None

    # compute equity
    if prior is None:
        equity = float(capital)
        period_ret = 0.0
    else:
        # realized return of PRIOR target weights since prior run
        prior_w = prior.get("weights", {})
        prior_px = prior.get("prices", {})
        period_ret = 0.0
        invested = 0.0
        for t, w in prior_w.items():
            p0 = prior_px.get(t)
            p1 = last_prices.get(t)
            if p0 and p1 and p0 > 0:
                period_ret += w * (p1 / p0 - 1.0)
                invested += w
        # remainder treated as cash (~0 over the short gap; conservative)
        equity = float(prior["paper_equity"]) * (1.0 + period_ret)

    record = dict(
        date=pd.Timestamp(target["asof"]).strftime("%Y-%m-%d"),
        run_ts=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        universe=universe_tag,
        crypto_proxy=bool(crypto),
        regime_on=target["regime_on"],
        spy_last=round(target["spy_last"], 2) if target["spy_last"] == target["spy_last"] else None,
        spy_ma200=round(target["spy_ma"], 2) if target["spy_ma"] == target["spy_ma"] else None,
        reason=target["reason"],
        holdings=target["picks"],
        weights={t: round(w, 4) for t, w in target["weights"].items() if w > 0},
        cash_weight=round(target["cash_weight"], 4),
        prices={t: round(float(last_prices[t]), 4)
                for t in target["picks"] + [REGIME_ASSET, CASH_TICKER]
                if t in last_prices and last_prices[t] == last_prices[t]},
        period_return=round(period_ret, 6),
        paper_equity=round(equity, 2),
    )

    # idempotent: drop any existing row for same (month, tag), keep the rest
    kept = [r for r in rows
            if not (r.get("universe") == universe_tag
                    and str(r.get("date", "")).startswith(month_key))]
    kept.append(record)
    kept.sort(key=lambda r: (r.get("universe", ""), r.get("date", "")))

    with open(track_path, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    return record


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt_pct(x):
    return f"{x*100:6.1f}%" if x == x else "   n/a"


def print_report(target, rebal, capital, universe_tag, source, asof):
    print("=" * 74)
    print("  ETF CROSS-ASSET MOMENTUM — LIVE TARGET (LOCKED CONFIG, PAPER ONLY)")
    print("=" * 74)
    print(f"  data source     : {source}")
    print(f"  as-of (last bar): {pd.Timestamp(asof).strftime('%Y-%m-%d')}")
    print(f"  universe        : {universe_tag}")
    print(f"  config          : 6m risk-adj momentum, top K={K} EW, DUAL+SPY>200d, "
          f"partial p={PARTIAL}")
    sl, sm = target["spy_last"], target["spy_ma"]
    gate = "ON (risk-on)" if target["regime_on"] else "OFF -> CASH"
    print(f"  SPY 200d gate   : {gate}   (SPY {sl:.2f} vs 200d MA {sm:.2f})"
          if sl == sl else f"  SPY 200d gate   : {gate}")
    print(f"  decision        : {target['reason']}")
    print("-" * 74)

    if target["picks"]:
        print("  TARGET PORTFOLIO (top-K by 6m risk-adj momentum):")
        print(f"    {'ticker':<8}{'weight':>10}{'mom score':>12}")
        for t in target["picks"]:
            print(f"    {t:<8}{fmt_pct(target['weights'][t]):>10}"
                  f"{target['scores'].get(t, float('nan')):>12.3f}")
        print(f"    {'CASH':<8}{fmt_pct(target['cash_weight']):>10}")
    else:
        print("  TARGET PORTFOLIO: 100% CASH (BIL / T-bills)")
    print("-" * 74)

    print(f"  PARTIAL-REBALANCE TRADES (move ~{int(PARTIAL*100)}% toward target "
          f"this month), capital ${capital:,.0f}")
    print(f"    current value of supplied holdings: ${rebal['total']:,.2f}")
    print(f"    {'ticker':<8}{'cur w':>8}{'tgt w':>8}{'step w':>8}"
          f"{'trade $':>11}{'~shares':>9}{'price':>9}")
    any_trade = False
    for r in sorted(rebal["rows"], key=lambda x: -abs(x["trade_d"])):
        if abs(r["trade_d"]) < 0.5 and r["cur_w"] == 0 and r["tgt_w"] == 0:
            continue
        act = ""
        if abs(r["trade_d"]) >= 0.5:
            any_trade = True
            act = "BUY " if r["trade_d"] > 0 else "SELL"
        sh = f"{r['shares']:+.1f}" if r["shares"] == r["shares"] else "n/a"
        pr = f"{r['price']:.2f}" if r["price"] == r["price"] else "n/a"
        print(f"    {r['ticker']:<8}{fmt_pct(r['cur_w']):>8}{fmt_pct(r['tgt_w']):>8}"
              f"{fmt_pct(r['step_w']):>8}{r['trade_d']:>+10.2f} {act:<4}"
              f"{sh:>8}{pr:>9}")
    if not any_trade:
        print("    (no trades — supplied holdings already near the partial step)")
    print(f"    CASH target after step: {fmt_pct(rebal['cash_step_w'])}")
    print("-" * 74)
    print("  NOTE: PAPER ONLY. Place these trades manually in your brokerage.")
    print("  Whole-share practicality at $1k: round to whole shares or use a")
    print("  fractional-share broker; rounding noise is small at K=5.")
    print("=" * 74)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Live/paper harness for cross-asset ETF momentum (locked config).")
    ap.add_argument("--crypto-proxy", action="store_true",
                    help="include crypto-proxy ETFs (IBIT/MSTR/COIN/GBTC) as members")
    ap.add_argument("--capital", type=float, default=1000.0,
                    help="account capital in $ for the trade report (default 1000)")
    ap.add_argument("--holdings", type=str, default=None,
                    help="JSON file of current $ holdings {ticker: dollars, CASH: dollars}")
    ap.add_argument("--paper-track", action="store_true",
                    help="append/update a dated record in the paper-track JSONL")
    ap.add_argument("--track-file", type=str, default=DEFAULT_TRACK,
                    help=f"paper-track JSONL path (default {DEFAULT_TRACK})")
    ap.add_argument("--cache", type=str, default=DEFAULT_CACHE,
                    help="price cache CSV path (fallback if yfinance is down)")
    args = ap.parse_args(argv)

    universe = list(CORE_UNIVERSE) + (CRYPTO_PROXY if args.crypto_proxy else [])
    universe_tag = "core+crypto" if args.crypto_proxy else "core"
    need = sorted(set(universe + [REGIME_ASSET, CASH_TICKER]))

    try:
        px, source = fetch_prices(need, cache_path=args.cache)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    asof = px.index[-1]
    last_prices = {t: float(px[t].dropna().iloc[-1])
                   for t in px.columns if px[t].notna().any()}

    target = compute_target(px, universe, asof=asof)
    current = load_holdings(args.holdings, universe)
    rebal = build_rebalance(target, current, last_prices, capital=args.capital)
    print_report(target, rebal, args.capital, universe_tag, source, asof)

    if args.paper_track:
        if source != "yfinance":
            print("[warn] not writing paper-track: prices came from cache, not a "
                  "fresh fetch (avoids a bogus dated record).", file=sys.stderr)
        else:
            rec = paper_track(args.track_file, target, last_prices,
                              args.capital, universe_tag, args.crypto_proxy)
            print(f"[paper-track] appended {rec['date']} ({universe_tag}): "
                  f"equity ${rec['paper_equity']:,.2f}, period_ret "
                  f"{rec['period_return']*100:+.2f}%, holdings "
                  f"{rec['holdings'] or 'CASH'} -> {args.track_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
