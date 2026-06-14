#!/usr/bin/env python3
"""
final_portfolio.py -- THE single deployable portfolio for a US small bankroll.

This is the CAPSTONE deliverable. It does NOT re-optimize anything; it REUSES the
locked component engines validated elsewhere in this repo:

  static core   : Permanent Portfolio 25% SPY / 25% TLT / 25% GLD / 25% BIL
                  (static_allocation.py -- the honest near-zero-effort optimum)
  active sat. A : etf_momentum_live.compute_target (LOCKED ETF risk-adj momentum)
  active sat. B : trend_following engine logic (inverse-when-down TS-momentum)
  crypto (opt.) : btc_trend_timing -- 200d-SMA trend-timed IBIT, IRA, sized small

WHY THIS SHAPE (see FINAL_PORTFOLIO.md for the full evidence table):
  Pure Permanent Portfolio is the honest baseline: OOS Sharpe ~1.07, maxDD ~-17.6%,
  ~zero effort (4 ETFs, quarterly). The ONE overlay that clears the brutal bar net
  of effort is a STATIC-CORE + SMALL-ACTIVE-SATELLITE blend: 70% PP / 30% active
  book. Full 2007-06->2026-06: Sharpe 0.93->1.03, maxDD -17.6%->-11.9%.
  OOS 2016+: Sharpe 1.07->1.14, maxDD -17.6%->-11.9%. It beats BOTH pure static
  (Sharpe + DD) and pure active (Sharpe + DD), on a PLATEAU (80/20..60/40 all
  ~1.13 Sharpe with monotone-improving DD). The durable, repeatable win is the
  ~6 percentage-point shallower drawdown; the Sharpe bump is real but modest
  (bootstrap P(blend>PP)=63%, rolling-3y ~half the windows) -- so the honest
  framing is "same-or-better Sharpe with a much shallower crash".

  The active satellite earns its place because it is a genuine DIVERSIFIER to the
  bond/gold-heavy static, not a competitor: corr(active, TLT)=-0.08, beta to TLT
  =-0.05, and in the worst-5% PP days the active book's correlation to PP is only
  +0.26. The TF leg's occasional bond/gold SHORTS do NOT meaningfully fight the
  static's longs in aggregate.

EFFORT-VS-BENEFIT, STATED PLAINLY:
  * If you want zero ongoing work: hold the pure Permanent Portfolio, rebalance
    quarterly. That is a perfectly good, honest answer. (--mode static)
  * If you will reliably do ~15 min of monthly rebalancing: the 70/30 PP+active
    blend buys you a materially shallower drawdown for the same-or-better Sharpe.
    (--mode blend  [default])

Window for all stats: full 2007-06 -> 2026-06; OOS holdout 2016-01 -> 2026-06.
Costs: 3 bps/side on rebalance turnover (same model as every component).

PAPER ONLY. No brokerage API, no orders, no secrets. You read the report and
place trades manually. Degrades gracefully if yfinance is unreachable.

USAGE
  python final_portfolio.py                         # blend, $10k, this month's target
  python final_portfolio.py --capital 25000
  python final_portfolio.py --mode static           # pure Permanent Portfolio
  python final_portfolio.py --risk conservative|moderate|aggressive
  python final_portfolio.py --crypto                # add trend-timed IBIT sleeve (IRA)
  python final_portfolio.py --paper-track           # append a dated row to the JSONL track
"""
from __future__ import annotations
import argparse, json, os, sys
import datetime as dt
import numpy as np
import pandas as pd

# ---- reuse locked live momentum engine (sleeve A) --------------------------
from etf_momentum_live import (
    fetch_prices, compute_target, cash_index,
    CORE_UNIVERSE, CRYPTO_PROXY, CASH_TICKER,
)
# ---- reuse locked TF engine maps/params (sleeve B) -------------------------
from trend_following import (
    TF_UNIVERSE, INVERSE_MAP, LEVERAGED_INV, ts_signal, trailing_vol,
)

TD = 252
PARTIAL = 0.34
# ---- the recommended portfolio shape ---------------------------------------
PP_WEIGHTS = {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "BIL": 0.25}
CORE_FRACTION = 0.70          # 70% static core
SAT_FRACTION = 0.30           # 30% active satellite (= 70% momentum A + 30% TF B inside)
SAT_A_FRAC = 0.70             # within the satellite
SAT_B_FRAC = 0.30
TF_VOL_TARGET = 0.10
TF_LOOKBACK = 126
TF_MAX_LEV = 2.0

# risk-tolerance: fraction of investable net worth to put in this risky book.
# remainder is your own emergency cash / short T-bills outside this engine.
RISK_SIZING = {
    "conservative": 0.40,
    "moderate":     0.65,
    "aggressive":   0.85,
}
CRYPTO_SLEEVE_CAP = 0.05      # <=5% of the book, IRA, trend-timed, sized small

DEFAULT_CACHE = "/tmp/final_data/live_prices.csv"
DEFAULT_TRACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "final_paper_track.jsonl")


# ---------------------------------------------------------------------------
# Satellite B: live trend-following target (mirrors trend_following.backtest_tf
# for the LATEST date only; inverse-when-down, vol-targeted).
# ---------------------------------------------------------------------------
def compute_tf_target(px, asof=None, universe=TF_UNIVERSE,
                      lookback_days=TF_LOOKBACK, vol_target=TF_VOL_TARGET,
                      max_lev=TF_MAX_LEV):
    """Return dict of {instrument: weight} for sleeve B as of `asof`.
    Long the ETF if trend up; if trend down hold its mapped 1x-notional inverse
    (de-levered) where available, else cash. Whole sleeve scaled to target vol.
    Weights sum to <=1 across long+inverse+cash (cash = 1 - invested)."""
    if asof is None:
        asof = px.index[-1]
    asof = pd.Timestamp(asof)
    uni = [t for t in universe if t in px.columns]
    sig = ts_signal(px[uni], asof, lookback_days, mode="trend").reindex(uni).fillna(0.0)
    have = px[uni].loc[:asof].iloc[-1].notna()
    sig = sig.where(have, 0.0)
    n_active = int(have.sum())
    base = 1.0 / max(n_active, 1)
    vols = trailing_vol(px[uni], asof, 63).reindex(uni)
    active_vols = vols[have].dropna()
    if len(active_vols) > 0:
        sleeve_vol = base * np.sqrt((active_vols ** 2).sum())
        scaler = vol_target / sleeve_vol if sleeve_vol > 0 else 1.0
    else:
        scaler = 1.0
    scaler = min(scaler, max_lev)

    legs = {}   # instrument -> signed notional weight within sleeve B
    cash_w = 0.0
    for t in uni:
        wgt = base * scaler
        if sig[t] > 0:
            legs[t] = legs.get(t, 0.0) + wgt
        elif sig[t] < 0:
            inv = INVERSE_MAP.get(t)
            if inv is not None:
                # hold the inverse ETF (real instrument); note 1x-notional intent
                legs[inv] = legs.get(inv, 0.0) + wgt
            else:
                cash_w += wgt
        else:
            cash_w += wgt
    invested = sum(legs.values())
    cash_w += max(0.0, 1.0 - invested - cash_w)
    return dict(asof=asof, legs=legs, cash_weight=cash_w, scaler=float(scaler),
                n_long=int((sig > 0).sum()), n_down=int((sig < 0).sum()))


# ---------------------------------------------------------------------------
# Crypto sleeve (optional, IRA): trend-timed IBIT, 200d SMA, hold or cash.
# ---------------------------------------------------------------------------
def compute_crypto_target(px, asof=None, ticker="IBIT", ma=200):
    if asof is None:
        asof = px.index[-1]
    asof = pd.Timestamp(asof)
    if ticker not in px.columns:
        return dict(ticker=ticker, on=False, reason="no IBIT history yet", last=np.nan, ma=np.nan)
    s = px[ticker].loc[:asof].dropna()
    if len(s) < ma:
        return dict(ticker=ticker, on=False, reason=f"<{ma}d history", last=float(s.iloc[-1]) if len(s) else np.nan, ma=np.nan)
    ma_val = s.tail(ma).mean()
    on = bool(s.iloc[-1] > ma_val)
    return dict(ticker=ticker, on=on, last=float(s.iloc[-1]), ma=float(ma_val),
                reason=("ABOVE 200d MA -> HOLD" if on else "BELOW 200d MA -> CASH"))


# ---------------------------------------------------------------------------
# Assemble the full top-level target allocation (weights of the risky book).
# ---------------------------------------------------------------------------
def assemble(px, mode="blend", asof=None):
    """Return {instrument: weight} for the risky book (sums to ~1, ex-crypto)."""
    alloc = {}

    def add(t, w):
        if abs(w) < 1e-9:
            return
        alloc[t] = alloc.get(t, 0.0) + w

    # static core
    core_f = 1.0 if mode == "static" else CORE_FRACTION
    for t, w in PP_WEIGHTS.items():
        add(t, core_f * w)

    detail = {"mode": mode, "core_fraction": core_f}
    if mode == "static":
        detail["satellite"] = None
        return alloc, detail

    # active satellite = A (momentum) + B (TF)
    momA = compute_target(px, list(CORE_UNIVERSE), asof=asof)
    for t, w in momA["weights"].items():
        add(t, SAT_FRACTION * SAT_A_FRAC * w)
    # A's residual cash goes to BIL
    a_cash = SAT_FRACTION * SAT_A_FRAC * momA.get("cash_weight", 0.0)
    add("BIL", a_cash)

    tfB = compute_tf_target(px, asof=asof)
    for t, w in tfB["legs"].items():
        add(t, SAT_FRACTION * SAT_B_FRAC * w)
    add("BIL", SAT_FRACTION * SAT_B_FRAC * tfB["cash_weight"])

    detail["satellite"] = {
        "momentum_picks": momA["picks"], "momentum_regime_on": momA["regime_on"],
        "momentum_reason": momA["reason"],
        "tf_n_long": tfB["n_long"], "tf_n_down": tfB["n_down"], "tf_scaler": tfB["scaler"],
    }
    # normalize tiny drift so reported weights sum to 1 (cash absorbs residual)
    s = sum(alloc.values())
    if s > 0:
        resid = 1.0 - s
        add("BIL", resid)
    return alloc, detail


# ---------------------------------------------------------------------------
def fmt_pct(x): return f"{x*100:6.2f}%"


def print_report(alloc, detail, capital, risk, crypto_info, asof):
    book_frac = RISK_SIZING[risk]
    book_capital = capital * book_frac
    print("=" * 74)
    print("  FINAL DEPLOYABLE PORTFOLIO -- target allocation")
    print("=" * 74)
    print(f"  as-of date     : {pd.Timestamp(asof).date()}")
    print(f"  mode           : {detail['mode']}  "
          f"({'pure Permanent Portfolio' if detail['mode']=='static' else '70% PP core + 30% active satellite'})")
    print(f"  risk tolerance : {risk}  -> put {book_frac*100:.0f}% of net worth in this book")
    print(f"  total capital  : ${capital:,.0f}   risky-book capital: ${book_capital:,.0f}")
    print(f"  (remaining ${capital-book_capital:,.0f} = your emergency cash / short T-bills, OUTSIDE this engine)")
    if detail.get("satellite"):
        sd = detail["satellite"]
        print(f"  satellite A    : regime {'ON' if sd['momentum_regime_on'] else 'OFF (cash)'}; "
              f"picks={sd['momentum_picks'] or 'CASH'}")
        print(f"  satellite B(TF): {sd['tf_n_long']} long / {sd['tf_n_down']} down; vol-scaler={sd['tf_scaler']:.2f}")
    print("-" * 74)
    print(f"  {'INSTRUMENT':12}{'WEIGHT':>10}{'$ TARGET':>16}")
    print("-" * 74)
    for t, w in sorted(alloc.items(), key=lambda kv: -kv[1]):
        if abs(w) < 5e-4:
            continue
        print(f"  {t:12}{fmt_pct(w):>10}{('$'+format(w*book_capital, ',.0f')):>16}")
    tot = sum(w for w in alloc.values() if abs(w) >= 5e-4)
    print("-" * 74)
    print(f"  {'TOTAL':12}{fmt_pct(tot):>10}{('$'+format(tot*book_capital, ',.0f')):>16}")
    # crypto sleeve printed separately (NOT double-counted in book)
    if crypto_info is not None:
        print("-" * 74)
        cap = CRYPTO_SLEEVE_CAP * book_capital
        if crypto_info["on"]:
            print(f"  CRYPTO SLEEVE (IRA, separate, <= {CRYPTO_SLEEVE_CAP*100:.0f}% of book = ${cap:,.0f}):")
            print(f"    {crypto_info['ticker']}: {crypto_info['reason']}  -> HOLD up to ${cap:,.0f}")
        else:
            print(f"  CRYPTO SLEEVE (IRA, separate): {crypto_info['ticker']} {crypto_info['reason']} -> 0% (cash)")
    print("=" * 74)
    print("  NOTE: inverse ETFs (SH/PSQ/EFZ/EUM/TBT/GLL/DUG/RWM) and the TF sleeve")
    print("  are short/leveraged products -- hold in a TAXABLE account is fine but they")
    print("  are short-term by nature; the momentum sleeve churns -> prefer an IRA/Roth")
    print("  for satellites to avoid short-term-gains tax drag. PP core is tax-efficient.")
    print("=" * 74)


def paper_track(track_path, alloc, detail, capital, risk, crypto_info, asof, mode):
    asof = pd.Timestamp(asof)
    key_month = asof.strftime("%Y-%m")
    row = dict(ts=dt.datetime.utcnow().isoformat(), asof=str(asof.date()),
               month=key_month, mode=mode, risk=risk, capital=capital,
               book_fraction=RISK_SIZING[risk],
               weights={k: round(v, 5) for k, v in alloc.items() if abs(v) >= 5e-4},
               satellite=detail.get("satellite"),
               crypto=(crypto_info or {}))
    existing = []
    if os.path.exists(track_path):
        with open(track_path) as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if not (r.get("month") == key_month and r.get("mode") == mode):
                    existing.append(r)
    existing.append(row)
    with open(track_path, "w") as f:
        for r in existing:
            f.write(json.dumps(r) + "\n")
    print(f"[paper-track] wrote {track_path} (month={key_month}, mode={mode}, rows={len(existing)})")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Final deployable portfolio target allocation")
    ap.add_argument("--capital", type=float, default=10000.0)
    ap.add_argument("--mode", choices=["blend", "static"], default="blend")
    ap.add_argument("--risk", choices=list(RISK_SIZING), default="moderate")
    ap.add_argument("--crypto", action="store_true", help="add trend-timed IBIT sleeve (IRA)")
    ap.add_argument("--paper-track", action="store_true")
    ap.add_argument("--track-path", default=DEFAULT_TRACK)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args(argv)

    # universe: static + satellite long ETFs + inverse ETFs + (crypto)
    tickers = sorted(set(
        list(PP_WEIGHTS) + list(CORE_UNIVERSE) + list(TF_UNIVERSE) +
        list(INVERSE_MAP.values()) + [CASH_TICKER, "SPY"] +
        (["IBIT"] if args.crypto else [])
    ))
    try:
        px, source = fetch_prices(tickers, cache_path=args.cache)
    except RuntimeError as e:
        print(f"[fatal] {e}", file=sys.stderr)
        return 2
    print(f"[data] source={source}  range={px.index.min().date()}..{px.index.max().date()}  "
          f"cols={px.shape[1]}", file=sys.stderr)

    asof = px.index[-1]
    alloc, detail = assemble(px, mode=args.mode, asof=asof)
    crypto_info = compute_crypto_target(px, asof=asof) if args.crypto else None

    print_report(alloc, detail, args.capital, args.risk, crypto_info, asof)
    if args.paper_track:
        paper_track(args.track_path, alloc, detail, args.capital, args.risk,
                    crypto_info, asof, args.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
