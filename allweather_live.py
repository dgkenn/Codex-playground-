#!/usr/bin/env python3
"""
allweather_live.py -- LIVE / PAPER harness for the project's FINAL recommendation:
a TREND-OVERLAID ALL-WEATHER PORTFOLIO for a US retail small bankroll.

This is the deployable build of the locked verdict (PROJECT_VERDICT.md e85e2af,
REGIME_ROBUSTNESS.md 959984e, INCOME_500_REALITY.md 945f828). It does NOT
re-derive anything. It REUSES the committed component engines:

  data + cash leg : etf_momentum_live.fetch_prices / cash_index  (yfinance, BIL)
  momentum sleeve : etf_momentum_live.compute_target   (LOCKED ETF risk-adj mom)
  trend overlay   : the 6-12m TIME-SERIES trend rule validated in
                    regime_robustness.trend_overlay / trend_following.ts_signal
                    -- hold each risk sleeve only if its own trailing trend is up,
                    else that sleeve's weight -> BIL cash.
  crypto sleeve   : the 200d-SMA trend-time-IBIT rule (BTC_TREND_TIMING.md),
                    same shape as final_portfolio.compute_crypto_target.

THE PORTFOLIO (two configs, ONE engine)
---------------------------------------
CONSERVATIVE (default, --mode conservative): Permanent-Portfolio-style base
  SPY / TLT / GLD / BIL at 25% each, with a 12-month time-series TREND filter on
  each RISK sleeve (SPY/TLT/GLD). A sleeve is held only if its trailing 12m total
  return > 0; otherwise that 25% parks in BIL cash. This is exactly the
  "PP + Trend overlay" candidate (REGIME_ROBUSTNESS.md full-sample Sharpe ~1.43,
  maxDD ~-10%, 2022 -13%->-5%). Cash sleeve is always cash. Lazy, regime-robust.

GROWTH (--growth): a MEDIUM-RISK growth tilt for a SMALL account compounding
  TOWARD the base (phase 1: contribute, do NOT withdraw). Same trend gate, but
  it OVERWEIGHTS the trend-gated equity/momentum sleeves and underweights bonds:
    - trend-gated EQUITY (SPY)                         32%
    - trend-gated MOMENTUM satellite (compute_target)  18%  (cross-asset ETF mom)
    - trend-gated long Treasuries (TLT)                18%
    - trend-gated GOLD (GLD)                            12%
    - trend-timed CRYPTO (IBIT, 200d SMA)             <=5%
    - permanent CASH floor (BIL)                        15%  (truncates fast-crash tail)
  Anything whose trend is down parks in BIL. VALIDATED ~13-18%/yr with -30-40% DD
  (see the validation in ALLWEATHER_DEPLOY.md / `--validate` in growth_planner).
  This is NOT levered, NOT a buy-and-hold-crypto bet: every risk sleeve is
  trend-gated, so the deep crashes are truncated to cash.

WHAT IT DOES
  (a) fetch current daily dividend-adjusted prices via yfinance (cache fallback);
  (b) compute THIS month's target allocation for the chosen config (each sleeve
      ON only if above its 6-12m trend, else -> BIL);
  (c) print a clean rebalance report: current vs target weights + the trades
      ($ and ~whole shares) to place;
  (d) --paper-track: append/update a dated JSONL record (idempotent per
      (mode, month)) so a real FORWARD paper track accrues.

PAPER ONLY. No brokerage API, no orders, no secrets. You read the report and
place the trades manually (see ALLWEATHER_DEPLOY.md runbook). Degrades
gracefully if yfinance is unreachable (falls back to cache; never writes a bogus
paper row off stale data).

USAGE
  python allweather_live.py                          # conservative, $5k
  python allweather_live.py --growth --capital 5000  # growth tilt
  python allweather_live.py --capital 25000 --lookback 12
  python allweather_live.py --growth --paper-track
  python allweather_live.py --holdings holdings.json # supply CURRENT positions

  --holdings is a JSON map {"SPY": 1200.0, "GLD": 800.0, "CASH": 500.0} of
  CURRENT dollar values per ticker (CASH = uninvested/BIL). If omitted, current
  = all cash (so the first run shows full first-month BUYs).

Window for all cited stats: long-history 1972-2023 (regime_robustness.py) for
the conservative core; ETF-era validation 2007-06..2026-06 (growth_planner.py
--validate) for the growth tilt. Costs: 5 bps/side on rebalance turnover (the
conservative reuse) / 10 bps round-trip in the growth backtest (conservative).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import datetime as dt

import numpy as np
import pandas as pd

# ---- reuse the LOCKED live data + momentum engine (do NOT edit it) ----------
from etf_momentum_live import (
    fetch_prices, compute_target, cash_index,
    CORE_UNIVERSE, CASH_TICKER, REGIME_ASSET,
)

TRADING_DAYS = 252
PARTIAL = 0.34                      # ~1/3 toward target each month (damps whipsaw)
DEFAULT_LOOKBACK_M = 12            # 12-month time-series trend (mid of the 6-12m band)
CRYPTO_MA = 200                    # 200-day SMA for the IBIT trend timer
CASH = "CASH"

# ---------------------------------------------------------------------------
# The two LOCKED config shapes. Base weights of each RISK sleeve; whatever is
# trend-OFF parks in BIL. 'MOM' is the cross-asset ETF-momentum satellite (its
# own internal gates already apply); 'IBIT' is the trend-timed crypto sleeve.
# ---------------------------------------------------------------------------
CONSERVATIVE = {
    "name": "conservative (trend-overlaid Permanent Portfolio)",
    "sleeves": {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25},   # + 0.25 BIL always cash
    "always_cash": 0.25,
    "mom": 0.0,
    "ibit": 0.0,
    "exp_return": "Sharpe ~1.4, CAGR ~10%, maxDD ~-10% (1972-2023)",
}
GROWTH = {
    "name": "growth tilt (small-account compounder)",
    # Medium-risk shape VALIDATED in growth_planner.py --validate to sit in the
    # -30..-40% maxDD band (full-sample DD ~-40% incl. the COVID gap; recent-5y
    # ~-29%), CAGR ~13% full / ~18% recent, Sharpe ~0.76/0.91. Overweights the
    # trend-gated equity + ETF-momentum satellite, keeps a 15% permanent cash
    # floor that truncates the fast-crash tail, less bonds than the PP core.
    "sleeves": {"SPY": 0.32, "TLT": 0.18, "GLD": 0.12},   # less bonds, more equity
    "always_cash": 0.15,    # permanent cash floor -> caps the COVID-type tail
    "mom": 0.18,        # trend-gated cross-asset ETF-momentum satellite
    "ibit": 0.05,       # trend-timed crypto sleeve (200d SMA), capped at 5%
    "exp_return": "~13-18%/yr, maxDD ~-30-40% (ETF-era validation)",
}

DEFAULT_CACHE = "/tmp/aw_data/live_prices.csv"
DEFAULT_TRACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "allweather_paper_track.jsonl")


# ---------------------------------------------------------------------------
# Trend signal: trailing `lookback_m`-month total return > 0  (the locked rule).
# Computed on daily adjusted prices; same spirit as regime_robustness.trend_overlay
# and trend_following.ts_signal(mode="trend").
# ---------------------------------------------------------------------------
def sleeve_trend_up(px, ticker, asof, lookback_m=DEFAULT_LOOKBACK_M):
    """Return (on: bool, total_ret, last, ref) for a single sleeve's TS-trend.
    ON  iff the trailing lookback_m-month total return is > 0 (trend up).
    """
    if ticker not in px.columns:
        return dict(on=False, ret=np.nan, last=np.nan, ref=np.nan,
                    reason="no price history")
    s = px[ticker].loc[:asof].dropna()
    days = int(round(lookback_m / 12 * TRADING_DAYS))
    if len(s) < days + 1:
        return dict(on=False, ret=np.nan, last=float(s.iloc[-1]) if len(s) else np.nan,
                    ref=np.nan, reason=f"<{lookback_m}m history")
    last = float(s.iloc[-1])
    ref = float(s.iloc[-(days + 1)])
    ret = last / ref - 1.0
    on = bool(ret > 0.0)
    return dict(on=on, ret=ret, last=last, ref=ref,
                reason=f"{lookback_m}m trend {'UP' if on else 'DOWN'} ({ret*100:+.1f}%)")


def crypto_trend_up(px, asof, ticker="IBIT", ma=CRYPTO_MA):
    """200d-SMA trend timer for the crypto sleeve (BTC_TREND_TIMING.md rule)."""
    if ticker not in px.columns:
        return dict(on=False, last=np.nan, ma=np.nan, reason="no IBIT history yet")
    s = px[ticker].loc[:asof].dropna()
    if len(s) < ma:
        return dict(on=False, last=float(s.iloc[-1]) if len(s) else np.nan, ma=np.nan,
                    reason=f"<{ma}d IBIT history -> CASH")
    ma_val = float(s.tail(ma).mean())
    last = float(s.iloc[-1])
    on = bool(last > ma_val)
    return dict(on=on, last=last, ma=ma_val,
                reason=("ABOVE 200d SMA -> HOLD" if on else "BELOW 200d SMA -> CASH"))


# ---------------------------------------------------------------------------
# Assemble the target allocation for the chosen config.
# ---------------------------------------------------------------------------
def assemble(px, config, asof=None, lookback_m=DEFAULT_LOOKBACK_M):
    """Return (alloc dict ticker->weight summing to ~1, detail dict).
    Each risk sleeve is held at its base weight only if trend-UP; else -> BIL.
    """
    if asof is None:
        asof = px.index[-1]
    asof = pd.Timestamp(asof)
    alloc = {}
    detail = {"sleeves": {}, "lookback_m": lookback_m}

    def add(t, w):
        if abs(w) < 1e-12:
            return
        alloc[t] = alloc.get(t, 0.0) + w

    cash_w = config["always_cash"]

    # --- simple trend-gated sleeves (SPY/TLT/GLD) ---------------------------
    for t, w in config["sleeves"].items():
        tr = sleeve_trend_up(px, t, asof, lookback_m)
        detail["sleeves"][t] = dict(weight=w, on=tr["on"], ret=tr["ret"],
                                    reason=tr["reason"])
        if tr["on"]:
            add(t, w)
        else:
            cash_w += w   # falling sleeve parks in cash

    # --- momentum satellite (its own internal gates apply) ------------------
    if config["mom"] > 0:
        momw = config["mom"]
        # gate the WHOLE momentum sleeve on SPY trend too? No -- compute_target
        # already has a SPY>200d regime gate + per-ETF dual filter; trust it.
        mom = compute_target(px, list(CORE_UNIVERSE), asof=asof)
        for t, w in mom["weights"].items():
            add(t, momw * w)
        # the momentum sleeve's own residual cash -> BIL
        add(CASH_TICKER, momw * mom.get("cash_weight", 0.0))
        detail["mom"] = dict(weight=momw, picks=mom["picks"],
                             regime_on=mom["regime_on"], reason=mom["reason"])

    # --- crypto sleeve (trend-timed IBIT, capped) ---------------------------
    if config["ibit"] > 0:
        cw = config["ibit"]
        ci = crypto_trend_up(px, asof)
        detail["crypto"] = dict(weight=cw, on=ci["on"], reason=ci["reason"],
                               last=ci.get("last"), ma=ci.get("ma"))
        if ci["on"]:
            add("IBIT", cw)
        else:
            cash_w += cw

    # everything parked -> BIL cash
    add(CASH_TICKER, cash_w)

    # normalize tiny float drift; BIL absorbs the residual
    s = sum(alloc.values())
    if abs(1.0 - s) > 1e-9:
        add(CASH_TICKER, 1.0 - s)
    detail["mode"] = config["name"]
    return alloc, detail


# ---------------------------------------------------------------------------
# Current holdings + partial-rebalance trade list (mirrors etf_momentum_live).
# ---------------------------------------------------------------------------
def load_holdings(path, tickers):
    cur = {t: 0.0 for t in tickers}
    cur[CASH] = 0.0
    if path and os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        for k, v in data.items():
            cur[k] = cur.get(k, 0.0) + float(v)
    return cur


def build_rebalance(alloc, current_dollars, last_prices, partial=PARTIAL, capital=None):
    """current vs target vs partial-step weights and the trades to place.
    BIL is the cash leg; map a CASH holdings key onto BIL for comparison.
    """
    cur = dict(current_dollars)
    # fold a generic CASH holding into BIL (the cash instrument)
    if cur.get(CASH, 0.0):
        cur[CASH_TICKER] = cur.get(CASH_TICKER, 0.0) + cur.pop(CASH)
    total = sum(cur.values())
    if total <= 0 and capital and capital > 0:
        cur = {CASH_TICKER: float(capital)}
        total = float(capital)
    if total <= 0:
        total = 0.0

    all_t = sorted(set(list(alloc) + list(cur)))
    cur_w = {t: (cur.get(t, 0.0) / total if total > 0 else 0.0) for t in all_t}
    step_w = {t: cur_w[t] + partial * (alloc.get(t, 0.0) - cur_w[t]) for t in all_t}

    rows = []
    for t in all_t:
        c_d = cur.get(t, 0.0)
        step_d = step_w[t] * total
        trade_d = step_d - c_d
        px = last_prices.get(t, np.nan)
        shares = (trade_d / px) if (px and not np.isnan(px)) else np.nan
        rows.append(dict(ticker=t, cur_w=cur_w[t], tgt_w=alloc.get(t, 0.0),
                         step_w=step_w[t], cur_d=c_d, step_d=step_d,
                         trade_d=trade_d, price=px, shares=shares))
    return dict(total=total, rows=rows, partial=partial)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt_pct(x):
    return f"{x*100:6.1f}%" if x == x else "   n/a"


def print_report(alloc, detail, rebal, capital, source, asof, mode_flag):
    print("=" * 76)
    print("  TREND-OVERLAID ALL-WEATHER -- LIVE TARGET (LOCKED CONFIG, PAPER ONLY)")
    print("=" * 76)
    print(f"  data source     : {source}")
    print(f"  as-of (last bar): {pd.Timestamp(asof).strftime('%Y-%m-%d')}")
    print(f"  config          : {detail['mode']}")
    print(f"  trend rule      : hold each risk sleeve only if its trailing "
          f"{detail['lookback_m']}m total return > 0, else -> BIL cash")
    print("-" * 76)
    print("  SLEEVE TREND GATES:")
    for t, d in detail["sleeves"].items():
        state = "ON  (hold)" if d["on"] else "OFF (-> cash)"
        r = f"{d['ret']*100:+.1f}%" if d["ret"] == d["ret"] else "n/a"
        print(f"    {t:<6} base {d['weight']*100:4.0f}%  {state:<13} "
              f"{detail['lookback_m']}m ret {r}")
    if "mom" in detail:
        m = detail["mom"]
        print(f"    MOM    base {m['weight']*100:4.0f}%  "
              f"regime {'ON' if m['regime_on'] else 'OFF (cash)'}; "
              f"picks={m['picks'] or 'CASH'}")
    if "crypto" in detail:
        c = detail["crypto"]
        state = "ON  (hold)" if c["on"] else "OFF (-> cash)"
        print(f"    IBIT   base {c['weight']*100:4.0f}%  {state:<13} {c['reason']}")
    print("-" * 76)
    print("  TARGET ALLOCATION:")
    print(f"    {'INSTRUMENT':<10}{'WEIGHT':>10}{'$ TARGET':>16}")
    for t, w in sorted(alloc.items(), key=lambda kv: -kv[1]):
        if abs(w) < 5e-4:
            continue
        tag = "  (cash)" if t == CASH_TICKER else ""
        print(f"    {t:<10}{fmt_pct(w):>10}{('$'+format(w*capital, ',.0f')):>16}{tag}")
    tot = sum(w for w in alloc.values() if abs(w) >= 5e-4)
    print(f"    {'TOTAL':<10}{fmt_pct(tot):>10}{('$'+format(tot*capital, ',.0f')):>16}")
    print("-" * 76)
    print(f"  PARTIAL-REBALANCE TRADES (move ~{int(rebal['partial']*100)}% toward "
          f"target this month), capital ${capital:,.0f}")
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
        print("    (no trades -- supplied holdings already near the partial step)")
    print("-" * 76)
    print("  NOTE: PAPER ONLY. Place these trades manually in your brokerage.")
    if mode_flag == "growth":
        print("  GROWTH tilt: phase-1 COMPOUNDER -- contribute monthly, do NOT")
        print("  withdraw. Hold the momentum/IBIT sleeves in an IRA/Roth (churn ->")
        print("  short-term-gains tax in taxable). At ~$70k switch to --conservative.")
    else:
        print("  CONSERVATIVE: tax-efficient PP core; fine in taxable or IRA.")
    print("  Use a fractional-share, commission-free broker so a 10-25% sleeve")
    print("  isn't dwarfed by one whole share at small size.")
    print("=" * 76)


# ---------------------------------------------------------------------------
# Paper track (JSONL) -- idempotent per (mode, month). Forward paper equity is a
# clean full-rebalance record of the SIGNAL (not partial-rebalance path).
# ---------------------------------------------------------------------------
def paper_track(track_path, alloc, detail, last_prices, capital, mode_flag, asof):
    month_key = pd.Timestamp(asof).strftime("%Y-%m")
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

    same = [r for r in rows if r.get("mode") == mode_flag]
    prior = same[-1] if same else None
    if prior is None:
        equity = float(capital)
        period_ret = 0.0
    else:
        pw = prior.get("weights", {})
        pp = prior.get("prices", {})
        period_ret = 0.0
        for t, w in pw.items():
            p0, p1 = pp.get(t), last_prices.get(t)
            if p0 and p1 and p0 > 0:
                period_ret += w * (p1 / p0 - 1.0)
        equity = float(prior["paper_equity"]) * (1.0 + period_ret)

    wkeep = {t: round(w, 4) for t, w in alloc.items() if abs(w) >= 5e-4}
    pxkeep = {t: round(float(last_prices[t]), 4) for t in wkeep
              if t in last_prices and last_prices[t] == last_prices[t]}
    record = dict(
        date=pd.Timestamp(asof).strftime("%Y-%m-%d"),
        run_ts=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        mode=mode_flag,
        lookback_m=detail["lookback_m"],
        weights=wkeep,
        prices=pxkeep,
        sleeve_gates={t: bool(d["on"]) for t, d in detail["sleeves"].items()},
        crypto_on=(detail.get("crypto") or {}).get("on"),
        mom_picks=(detail.get("mom") or {}).get("picks"),
        period_return=round(period_ret, 6),
        paper_equity=round(equity, 2),
    )
    kept = [r for r in rows
            if not (r.get("mode") == mode_flag
                    and str(r.get("date", "")).startswith(month_key))]
    kept.append(record)
    kept.sort(key=lambda r: (r.get("mode", ""), r.get("date", "")))
    with open(track_path, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    return record


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Live/paper harness for the trend-overlaid all-weather portfolio.")
    ap.add_argument("--growth", action="store_true",
                    help="use the medium-risk GROWTH tilt (overweight trend-gated "
                         "equity/momentum + <=10%% trend-timed IBIT, less bonds)")
    ap.add_argument("--capital", type=float, default=5000.0,
                    help="account capital in $ for the trade report (default 5000)")
    ap.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK_M,
                    help="trend lookback in MONTHS (6-12 band; default 12)")
    ap.add_argument("--holdings", type=str, default=None,
                    help="JSON file of current $ holdings {ticker: dollars, CASH: dollars}")
    ap.add_argument("--paper-track", action="store_true",
                    help="append/update a dated record in the paper-track JSONL")
    ap.add_argument("--track-file", type=str, default=DEFAULT_TRACK)
    ap.add_argument("--cache", type=str, default=DEFAULT_CACHE)
    args = ap.parse_args(argv)

    config = GROWTH if args.growth else CONSERVATIVE
    mode_flag = "growth" if args.growth else "conservative"

    # universe: PP sleeves + cash + (momentum universe + IBIT for growth)
    need = set(["SPY", "TLT", "GLD", CASH_TICKER, REGIME_ASSET])
    if config["mom"] > 0:
        need |= set(CORE_UNIVERSE)
    if config["ibit"] > 0:
        need.add("IBIT")
    need = sorted(need)

    try:
        px, source = fetch_prices(need, cache_path=args.cache)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    print(f"[data] source={source}  range={px.index.min().date()}.."
          f"{px.index.max().date()}  cols={px.shape[1]}", file=sys.stderr)

    asof = px.index[-1]
    last_prices = {t: float(px[t].dropna().iloc[-1])
                   for t in px.columns if px[t].notna().any()}

    alloc, detail = assemble(px, config, asof=asof, lookback_m=args.lookback)
    all_tickers = sorted(set(list(alloc) + ["SPY", "TLT", "GLD", CASH_TICKER]))
    current = load_holdings(args.holdings, all_tickers)
    rebal = build_rebalance(alloc, current, last_prices, capital=args.capital)
    print_report(alloc, detail, rebal, args.capital, source, asof, mode_flag)

    if args.paper_track:
        if source != "yfinance":
            print("[warn] not writing paper-track: prices came from cache, not a "
                  "fresh fetch (avoids a bogus dated record).", file=sys.stderr)
        else:
            rec = paper_track(args.track_file, alloc, detail, last_prices,
                              args.capital, mode_flag, asof)
            print(f"[paper-track] appended {rec['date']} ({mode_flag}): equity "
                  f"${rec['paper_equity']:,.2f}, period_ret "
                  f"{rec['period_return']*100:+.2f}% -> {args.track_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
