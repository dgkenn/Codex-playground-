#!/usr/bin/env python3
"""
portfolio_live.py — UNIFIED LIVE / PAPER harness for the COMBINED two-sleeve book.

This is the convergent deployable: it outputs THIS month's full combined target
portfolio (BOTH sleeves' tickers + weights, with the regime / trend gates applied)
for a given capital, and a --paper-track mode that logs the combined paper equity.

It does NOT re-optimize anything. It REUSES the two LOCKED sleeve specs:

  SLEEVE A (70%) = cross-asset ETF cross-sectional momentum  [ETF_MOMENTUM.md e3e2d57]
    - ~30 liquid ETFs; 6m risk-adjusted XS momentum; top-K=5 EW; remainder BIL.
    - Gates: DUAL/absolute (hold only if 6m return > cash) + SPY>200d MA (else 100% cash).
    - (math mirrors etf_momentum.py / etf_momentum_live.py — NOT edited here.)

  SLEEVE B (30%) = inverse-ETF TREND-FOLLOWING  [TREND_FOLLOWING.md 0350194]
    - 11 cross-asset ETFs; time-series 6m trend per asset; long if own trend up;
      when DOWN hold the asset's INVERSE ETF (SH/PSQ/EFZ/EUM/TBT/GLL/DUG/RWM,
      leveraged inverses de-levered to ~1x) or cash where no clean inverse exists.
    - ~10% vol target; gross capped at 2x. (math mirrors trend_following.py.)

  COMBINATION = 70% A / 30% B, rebalanced monthly. This is the locked book chosen
  on the robust Sharpe+drawdown plateau (PORTFOLIO_COMBINED.md). No satellites.

The combined target is reported as portfolio-level weights:
  combined_weight(ticker) = 0.70*weight_in_A + 0.30*weight_in_B.
Inverse ETFs only ever appear via sleeve B. BIL/cash is the residual of both sleeves.

PAPER ONLY. No brokerage API, no orders, no secrets. The operator reads the report
and places trades manually (see the runbook in PORTFOLIO_COMBINED.md).

Graceful degradation: if yfinance is unreachable it falls back to a cached price
file if present, and refuses to write a bogus paper record.

USAGE
  python portfolio_live.py                      # $1k, dry combined report
  python portfolio_live.py --capital 10000      # size to $10k
  python portfolio_live.py --wa 0.70 --wb 0.30  # override sleeve weights (default 70/30)
  python portfolio_live.py --paper-track        # append/update combined paper-equity row
"""
from __future__ import annotations
import argparse, json, os, sys, datetime as dt
import numpy as np, pandas as pd

# ---------------------------------------------------------------------------
# LOCKED CONFIG (mirrors the two sleeve specs; do NOT re-optimize)
# ---------------------------------------------------------------------------
TRADING_DAYS = 252
LOOKBACK_DAYS = 126          # 6 months
K = 5                        # sleeve A top-K
REGIME_MA = 200              # SPY>200d gate (sleeve A)
REGIME_ASSET = "SPY"
CASH_TICKER = "BIL"
DEFAULT_WA, DEFAULT_WB = 0.70, 0.30   # locked 70/30 A/B

# Sleeve A universe (~30 liquid cross-asset ETFs)
A_SECTORS = ["XLK","XLE","XLF","XLV","XLI","XLY","XLP","XLU","XLB"]
A_STYLE   = ["SPY","QQQ","IWM"]
A_INTL    = ["EFA","EEM","EWJ","EWZ","EWG","EWU","FXI","VGK"]
A_ASSETS  = ["TLT","IEF","GLD","DBC","USO","VNQ","UUP","SLV","HYG","LQD"]
A_UNIVERSE = sorted(set(A_SECTORS + A_STYLE + A_INTL + A_ASSETS))

# Sleeve B universe + inverse map (de-lever 2x inverses to ~1x)
B_UNIVERSE = ["SPY","QQQ","EFA","EEM","TLT","IEF","DBC","GLD","USO","VNQ","UUP"]
INVERSE_MAP = {"SPY":"SH","QQQ":"PSQ","EFA":"EFZ","EEM":"EUM","TLT":"TBT",
               "VNQ":"RWM","GLD":"GLL","USO":"DUG"}
LEVERAGED_INV = {"TBT":2.0,"GLL":2.0,"DUG":2.0}
B_VOL_TARGET = 0.10
B_VOL_WIN = 63
B_MAX_LEV = 2.0

DEFAULT_CACHE = "/tmp/pfdep_data/live_prices.csv"
DEFAULT_TRACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "portfolio_paper_track.jsonl")

ALL_INVERSE = sorted(set(INVERSE_MAP.values()))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def needed_tickers(crypto=False):
    t = set(A_UNIVERSE) | set(B_UNIVERSE) | set(ALL_INVERSE) | {REGIME_ASSET, CASH_TICKER}
    return sorted(t)

def fetch_prices(tickers, cache_path=DEFAULT_CACHE, lookback_years=3):
    """Daily dividend-adjusted closes via yfinance. (px_df, source)."""
    tickers = sorted(set(tickers))
    px = None
    try:
        import yfinance as yf
        raw = yf.download(tickers, period=f"{lookback_years+1}y", auto_adjust=True,
                          progress=False, threads=True)
        if raw is not None and len(raw) > 0:
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
            if isinstance(close, pd.Series):
                close = close.to_frame(tickers[0])
            close = close.dropna(how="all").sort_index()
            if len(close) >= REGIME_MA + 10:
                px = close
    except Exception as e:
        print(f"[warn] yfinance fetch failed: {e!r}", file=sys.stderr)
    if px is not None:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            px.to_csv(cache_path)
        except Exception:
            pass
        return px, "yfinance"
    if os.path.exists(cache_path):
        print(f"[warn] yfinance unreachable; using cache {cache_path}", file=sys.stderr)
        return pd.read_csv(cache_path, index_col=0, parse_dates=True).sort_index(), "cache"
    raise RuntimeError(f"yfinance unreachable and no cache at {cache_path}.")

def cash_index(px):
    if CASH_TICKER in px.columns and px[CASH_TICKER].notna().sum() > 60:
        return px[CASH_TICKER].ffill().bfill()
    daily = (1+0.02)**(1/TRADING_DAYS)
    return pd.Series(daily**np.arange(len(px.index)), index=px.index)


# ---------------------------------------------------------------------------
# SLEEVE A target (mirrors etf_momentum.py math)
# ---------------------------------------------------------------------------
def risk_adj_momentum(px, asof, lb=LOOKBACK_DAYS):
    w = px.loc[:asof].tail(lb+1)
    if len(w) < lb*0.8: return pd.Series(dtype=float)
    rets = np.log(w).diff().dropna(how="all")
    total = np.log(w.iloc[-1]/w.iloc[0])
    vol = rets.std()*np.sqrt(TRADING_DAYS)
    score = total/vol.replace(0,np.nan)
    valid = w.notna().sum() >= lb*0.8
    return score[valid].dropna()

def abs_vs_cash(px, asof, cash, lb=LOOKBACK_DAYS):
    w = px.loc[:asof].tail(lb+1); cw = cash.loc[:asof].tail(lb+1)
    if len(w) < lb*0.8: return pd.Series(dtype=float)
    return (w.iloc[-1]/w.iloc[0]-1) - (cw.iloc[-1]/cw.iloc[0]-1)

def regime_on(px, asof, ma=REGIME_MA):
    ra = px[REGIME_ASSET].loc[:asof].dropna()
    if len(ra) < ma: return False, np.nan, np.nan
    mv = ra.tail(ma).mean()
    return bool(ra.iloc[-1] > mv), float(ra.iloc[-1]), float(mv)

def sleeve_A_target(px, asof):
    """Returns dict: weights (within-sleeve, sum<=1), picks, scores, regime fields, reason."""
    cash = cash_index(px)
    avail = [t for t in A_UNIVERSE if t in px.columns]
    sub = px[avail]
    on, spy_last, spy_ma = regime_on(px, asof)
    w = {t: 0.0 for t in avail}
    if not on:
        return dict(weights=w, picks=[], scores={}, regime_on=False,
                    spy_last=spy_last, spy_ma=spy_ma,
                    reason="REGIME OFF: SPY<200d MA -> sleeve A 100% CASH")
    score = risk_adj_momentum(sub, asof).dropna()
    am = abs_vs_cash(sub, asof, cash)
    score = score[am.reindex(score.index) > 0].sort_values(ascending=False)
    picks = score.head(K).index.tolist()
    if not picks:
        return dict(weights=w, picks=[], scores={}, regime_on=True,
                    spy_last=spy_last, spy_ma=spy_ma,
                    reason="ABSOLUTE FILTER: nothing beats cash -> sleeve A 100% CASH")
    for t in picks: w[t] = 1.0/len(picks)
    return dict(weights=w, picks=picks, scores=score.head(K).round(4).to_dict(),
                regime_on=True, spy_last=spy_last, spy_ma=spy_ma,
                reason=f"RISK-ON: sleeve A holds top {len(picks)} by 6m risk-adj momentum")


# ---------------------------------------------------------------------------
# SLEEVE B target (mirrors trend_following.py math, down='inverse')
# ---------------------------------------------------------------------------
def ts_signal(px, asof, lb=LOOKBACK_DAYS):
    w = px.loc[:asof].tail(lb+1)
    if len(w) < lb*0.6: return pd.Series(dtype=float)
    valid = w.notna().sum() >= lb*0.6
    sig = np.sign(w.iloc[-1]/w.iloc[0]-1)
    return sig[valid].dropna()

def trailing_vol(px, asof, win=B_VOL_WIN):
    w = px.loc[:asof].tail(win+1)
    return w.pct_change().std()*np.sqrt(TRADING_DAYS)

def sleeve_B_target(px, asof):
    """Inverse-when-down TF sleeve. Returns within-sleeve gross weights per ticker
    (positive long-ETF weight, positive inverse-ETF weight) + cash residual + diag."""
    uni = [t for t in B_UNIVERSE if t in px.columns]
    sub = px[uni]
    sig = ts_signal(sub, asof).reindex(uni).fillna(0.0)
    have = sub.loc[:asof].iloc[-1].notna()
    sig = sig.where(have, 0.0)
    n = int(have.sum()); base = 1.0/max(n,1)
    vols = trailing_vol(sub, asof).reindex(uni)
    av = vols[have].dropna()
    sv = base*np.sqrt((av**2).sum()) if len(av)>0 else 0.0
    scaler = min(B_VOL_TARGET/sv if sv>0 else 1.0, B_MAX_LEV)
    wgt = base*scaler
    longs, invs = {}, {}; cash_w = 0.0; legs=[]
    for t in uni:
        if sig[t] > 0:
            longs[t] = longs.get(t,0.0)+wgt; legs.append((t,"LONG",t,wgt))
        elif sig[t] < 0:
            it = INVERSE_MAP.get(t)
            if it and it in px.columns and px[it].notna().any():
                invs[it] = invs.get(it,0.0)+wgt; legs.append((t,"SHORT-via-inv",it,wgt))
            else:
                cash_w += wgt; legs.append((t,"CASH(no inv)",CASH_TICKER,wgt))
        else:
            cash_w += wgt; legs.append((t,"CASH",CASH_TICKER,wgt))
    gross = sum(longs.values())+sum(invs.values())
    return dict(longs=longs, invs=invs, cash_w=cash_w, scaler=scaler, gross=gross,
                legs=legs, n_active=n,
                reason=f"TF: {len(longs)} long / {len(invs)} inverse / vol-target {B_VOL_TARGET:.0%}, "
                       f"gross {gross:.2f}x")


# ---------------------------------------------------------------------------
# COMBINE -> portfolio-level target weights
# ---------------------------------------------------------------------------
def combined_target(px, asof, wa=DEFAULT_WA, wb=DEFAULT_WB):
    A = sleeve_A_target(px, asof)
    B = sleeve_B_target(px, asof)
    comb = {}
    for t, w in A["weights"].items():
        if w > 0: comb[t] = comb.get(t,0.0) + wa*w
    for t, w in B["longs"].items():
        comb[t] = comb.get(t,0.0) + wb*w
    for it, w in B["invs"].items():
        comb[it] = comb.get(it,0.0) + wb*w
    # cash residual = whatever each sleeve left uninvested, weighted
    a_cash = 1.0 - sum(A["weights"].values())
    b_invested = sum(B["longs"].values()) + sum(B["invs"].values()) + B["cash_w"]
    b_cash = max(0.0, 1.0 - b_invested) + B["cash_w"]
    cash_weight = wa*a_cash + wb*b_cash
    # (note: sleeve B may run >1.0 gross via vol-target leverage; comb can sum>1 net of cash)
    invested = sum(comb.values())
    return dict(asof=asof, weights=comb, cash_weight=cash_weight,
                invested=invested, A=A, B=B, wa=wa, wb=wb)


# ---------------------------------------------------------------------------
# Trade list (full target; combined book rebalanced monthly to target)
# ---------------------------------------------------------------------------
def load_holdings(path):
    cur = {}
    if path and os.path.exists(path):
        with open(path) as f: data = json.load(f)
        for k,v in data.items(): cur[k] = cur.get(k,0.0)+float(v)
    return cur

def build_trades(tgt, current, last_prices, capital):
    total = sum(current.values())
    if total <= 0 and capital and capital > 0:
        current = {"CASH": float(capital)}; total = float(capital)
    tw = tgt["weights"]
    tickers = sorted(set(list(tw) + [k for k in current if k != "CASH"]))
    rows = []
    for t in tickers:
        cur_d = current.get(t, 0.0)
        cur_w = cur_d/total if total>0 else 0.0
        tgt_d = tw.get(t,0.0)*total
        trade_d = tgt_d - cur_d
        p = last_prices.get(t, np.nan)
        sh = trade_d/p if (p and not np.isnan(p)) else np.nan
        rows.append(dict(ticker=t, cur_w=cur_w, tgt_w=tw.get(t,0.0),
                         cur_d=cur_d, tgt_d=tgt_d, trade_d=trade_d, price=p, shares=sh))
    return dict(total=total, rows=rows)


# ---------------------------------------------------------------------------
# Paper track
# ---------------------------------------------------------------------------
def paper_track(track_path, tgt, last_prices, capital):
    month_key = pd.Timestamp(tgt["asof"]).strftime("%Y-%m")
    rows = []
    if os.path.exists(track_path):
        with open(track_path) as f:
            for line in f:
                line=line.strip()
                if line:
                    try: rows.append(json.loads(line))
                    except json.JSONDecodeError: pass
    prior = rows[-1] if rows else None
    if prior is None:
        equity = float(capital); period_ret = 0.0
    else:
        pw = prior.get("weights", {}); ppx = prior.get("prices", {}); period_ret = 0.0
        for t,w in pw.items():
            p0 = ppx.get(t); p1 = last_prices.get(t)
            if p0 and p1 and p0>0: period_ret += w*(p1/p0-1.0)
        equity = float(prior["paper_equity"]) * (1.0+period_ret)
    rec = dict(
        date=pd.Timestamp(tgt["asof"]).strftime("%Y-%m-%d"),
        run_ts=dt.datetime.utcnow().isoformat(timespec="seconds")+"Z",
        book=f"combined_{int(tgt['wa']*100)}_{int(tgt['wb']*100)}",
        regime_on=tgt["A"]["regime_on"],
        spy_last=round(tgt["A"]["spy_last"],2) if tgt["A"]["spy_last"]==tgt["A"]["spy_last"] else None,
        spy_ma200=round(tgt["A"]["spy_ma"],2) if tgt["A"]["spy_ma"]==tgt["A"]["spy_ma"] else None,
        sleeveA_picks=tgt["A"]["picks"],
        sleeveB_gross=round(tgt["B"]["gross"],3),
        weights={t: round(w,4) for t,w in tgt["weights"].items() if w>0},
        cash_weight=round(tgt["cash_weight"],4),
        prices={t: round(float(last_prices[t]),4) for t in tgt["weights"]
                if t in last_prices and last_prices[t]==last_prices[t]},
        period_return=round(period_ret,6),
        paper_equity=round(equity,2),
    )
    kept = [r for r in rows if not str(r.get("date","")).startswith(month_key)]
    kept.append(rec); kept.sort(key=lambda r: r.get("date",""))
    with open(track_path,"w") as f:
        for r in kept: f.write(json.dumps(r)+"\n")
    return rec


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt(x): return f"{x*100:6.1f}%" if x==x else "   n/a"

def print_report(tgt, trades, capital, source):
    asof = pd.Timestamp(tgt["asof"]).strftime("%Y-%m-%d")
    A, B = tgt["A"], tgt["B"]
    print("="*78)
    print("  COMBINED TWO-SLEEVE PORTFOLIO — LIVE TARGET (LOCKED, PAPER ONLY)")
    print("="*78)
    print(f"  data source     : {source}")
    print(f"  as-of (last bar): {asof}")
    print(f"  book            : {int(tgt['wa']*100)}% A (ETF XS-momentum) / "
          f"{int(tgt['wb']*100)}% B (inverse-ETF trend-following)")
    gate = "ON (risk-on)" if A["regime_on"] else "OFF -> sleeve A to CASH"
    sl, sm = A["spy_last"], A["spy_ma"]
    if sl==sl:
        print(f"  SPY 200d gate   : {gate}   (SPY {sl:.2f} vs 200d {sm:.2f})")
    else:
        print(f"  SPY 200d gate   : {gate}")
    print(f"  sleeve A        : {A['reason']}")
    print(f"  sleeve B        : {B['reason']}")
    print("-"*78)
    print("  COMBINED TARGET (portfolio-level weights = 0.70*A + 0.30*B):")
    print(f"    {'ticker':<8}{'weight':>9}{'sleeve':>22}")
    aset, bl, bi = set(A["picks"]), set(B["longs"]), set(B["invs"])
    for t,w in sorted(tgt["weights"].items(), key=lambda kv:-kv[1]):
        src=[]
        if t in aset: src.append("A-mom")
        if t in bl: src.append("B-long")
        if t in bi: src.append("B-inverse")
        print(f"    {t:<8}{fmt(w):>9}{(' + '.join(src)):>22}")
    print(f"    {'BIL/CASH':<8}{fmt(tgt['cash_weight']):>9}{'A+B residual':>22}")
    print(f"    {'-'*40}")
    print(f"    invested (risk) weight: {fmt(tgt['invested'])}  (sleeve B vol-target may lever its 30% share)")
    print("-"*78)
    print(f"  FULL-TARGET TRADES (combined book rebalanced to target), capital ${capital:,.0f}")
    print(f"    current value of supplied holdings: ${trades['total']:,.2f}")
    print(f"    {'ticker':<8}{'cur w':>8}{'tgt w':>8}{'trade $':>11}{'~shares':>9}{'price':>9}")
    for r in sorted(trades["rows"], key=lambda x:-abs(x["trade_d"])):
        if abs(r["trade_d"]) < 0.5 and r["cur_w"]==0 and r["tgt_w"]==0: continue
        act = "BUY " if r["trade_d"]>0 else "SELL"
        sh = f"{r['shares']:+.1f}" if r["shares"]==r["shares"] else "n/a"
        pr = f"{r['price']:.2f}" if r["price"]==r["price"] else "n/a"
        print(f"    {r['ticker']:<8}{fmt(r['cur_w']):>8}{fmt(r['tgt_w']):>8}"
              f"{r['trade_d']:>+10.2f} {act:<4}{sh:>8}{pr:>9}")
    print("-"*78)
    print("  NOTE: PAPER ONLY. Place trades manually. Inverse ETFs (SH/PSQ/EFZ/EUM/")
    print("  TBT/GLL/DUG/RWM) appear ONLY via sleeve B's short-in-downtrend leg.")
    print("="*78)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Combined two-sleeve live/paper harness (locked).")
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--wa", type=float, default=DEFAULT_WA)
    ap.add_argument("--wb", type=float, default=DEFAULT_WB)
    ap.add_argument("--holdings", type=str, default=None)
    ap.add_argument("--paper-track", action="store_true")
    ap.add_argument("--track-file", type=str, default=DEFAULT_TRACK)
    ap.add_argument("--cache", type=str, default=DEFAULT_CACHE)
    args = ap.parse_args(argv)
    if abs((args.wa+args.wb)-1.0) > 1e-6:
        print("[error] --wa + --wb must sum to 1.0", file=sys.stderr); return 2
    try:
        px, source = fetch_prices(needed_tickers(), cache_path=args.cache)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr); return 2
    asof = px.index[-1]
    last_prices = {t: float(px[t].dropna().iloc[-1]) for t in px.columns if px[t].notna().any()}
    tgt = combined_target(px, asof, wa=args.wa, wb=args.wb)
    current = load_holdings(args.holdings)
    trades = build_trades(tgt, current, last_prices, args.capital)
    print_report(tgt, trades, args.capital, source)
    if args.paper_track:
        if source != "yfinance":
            print("[warn] not writing paper-track: prices from cache, not a fresh fetch.", file=sys.stderr)
        else:
            rec = paper_track(args.track_file, tgt, last_prices, args.capital)
            print(f"[paper-track] {rec['date']} ({rec['book']}): equity ${rec['paper_equity']:,.2f}, "
                  f"period_ret {rec['period_return']*100:+.2f}% -> {args.track_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
