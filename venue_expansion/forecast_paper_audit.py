"""forecast_paper_audit.py -- honest re-pricing of the wx_forecast forward paper sleeve.

WHY: `wx_forecast_forward.py:settle()` computes paper pnl as

    pnl = (1 - price - fee) if won else (-price - fee)

where `price` is ALWAYS the YES ask (`yes_ask_c`), for BOTH sides. That is correct for a YES
buy and wrong for a NO buy: buying NO does not cost the YES ask. This is the `settle()`
accounting bug RESEARCH_LEDGER.md flagged ("NO-side priced at YES cost") -- still present in the
deployed script, and 179 of the 261 settled paper trades are NO trades.

The naive fix (NO cost = 1 - yes_ask) is ALSO wrong, and wrong in the flattering direction:
1 - yes_ask is the NO *bid*, i.e. the price you'd get selling NO. A NO *buyer* pays
NO_ask = 1 - yes_bid. The paper log never captured yes_bid, so the honest cost is not
recoverable from the log at all.

THIS SCRIPT recovers it from Kalshi's public candlestick API (1-minute yes_bid/yes_ask history,
no auth), at the first candle at/after each trade's own `issued` timestamp -- no look-ahead, the
entry is priced at or after the signal. It then recomputes the sleeve's P&L three ways:

  (a) as-logged            -- the buggy number the sleeve reports
  (b) naive-corrected      -- NO cost = 1 - yes_ask (the NO bid; optimistic, unfillable)
  (c) TRUE executable      -- YES cost = yes_ask, NO cost = 1 - yes_bid, both measured at signal

Day-clustered t-stats throughout (weather P&L is strongly correlated within a calendar day).
Read-only: pulls public market data, writes only its own cache + results JSON.

Usage:  python venue_expansion/forecast_paper_audit.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import statistics as st
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SETTLED = os.path.join(HERE, "paper", "wx_forecast_settled.jsonl")
CACHE = os.path.join(HERE, "cache", "candles")
OUT = os.path.join(HERE, "out", "forecast_paper_audit.json")
API = "https://api.elections.kalshi.com/trade-api/v2"


def _kalshi_fee(price_dollars: float) -> float:
    """Kalshi taker fee, cents rounded up -- the same formula the sleeve uses."""
    return math.ceil(0.07 * price_dollars * (1 - price_dollars) * 100) / 100.0


def _get(url: str, tries: int = 4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research/1.0"})
            with urllib.request.urlopen(req, timeout=40) as fh:
                return json.load(fh)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def candles(series: str, ticker: str, t0: int, t1: int):
    """1-minute candlesticks for [t0,t1], cached on disk (public endpoint, no auth)."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{ticker}_{t0}_{t1}.json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    url = f"{API}/series/{series}/markets/{ticker}/candlesticks?start_ts={t0}&end_ts={t1}&period_interval=1"
    try:
        data = _get(url).get("candlesticks", [])
    except Exception:
        data = []
    with open(path, "w") as fh:
        json.dump(data, fh)
    time.sleep(0.35)  # be polite to a free public API
    return data


def _dollars(node, field="close_dollars"):
    if not node:
        return None
    v = node.get(field)
    return float(v) if v is not None else None


def quote_at(series: str, ticker: str, issued_iso: str):
    """(yes_bid, yes_ask) from the FIRST candle ending at/after the signal time.

    At/after, never before: the entry must be executable at or after the moment the sleeve
    decided. Taking the best quote anywhere in a window is the 'best-price-in-window'
    look-ahead that this repo's graveyard is full of.
    """
    ts = int(dt.datetime.fromisoformat(issued_iso).timestamp())
    cs = candles(series, ticker, ts - 300, ts + 1800)
    for c in cs:
        if c.get("end_period_ts", 0) >= ts:
            return _dollars(c.get("yes_bid")), _dollars(c.get("yes_ask")), len(cs)
    return None, None, len(cs)


def pnl(cost: float, won: bool) -> float:
    fee = _kalshi_fee(cost)
    return (1.0 - cost - fee) if won else (-cost - fee)


def day_clustered(rows, key):
    """Mean and t computed over per-day means -- the correct clustering unit here."""
    byday = collections.defaultdict(list)
    for r in rows:
        byday[r["date"]].append(key(r))
    dm = [st.mean(v) for v in byday.values()]
    if len(dm) < 2:
        return None, None, len(dm)
    m = st.mean(dm)
    se = st.stdev(dm) / math.sqrt(len(dm))
    return m, (m / se if se else float("nan")), len(dm)


def main() -> None:
    rows = [json.loads(l) for l in open(SETTLED) if l.strip()]
    print(f"settled paper trades: {len(rows)}  days: {len(set(r['date'] for r in rows))}")

    priced, unpriced = [], 0
    for i, r in enumerate(rows, 1):
        yb, ya, ncand = quote_at(r["series"], r["ticker"], r["issued"])
        if yb is None or ya is None:
            unpriced += 1
            continue
        r["mkt_yes_bid"], r["mkt_yes_ask"], r["n_candles"] = yb, ya, ncand
        r["true_cost"] = ya if r["side"] == "yes" else 1.0 - yb
        r["naive_cost"] = r["price"] if r["side"] == "yes" else 1.0 - r["price"]
        r["pnl_true"] = pnl(r["true_cost"], r["won"])
        r["pnl_naive"] = pnl(r["naive_cost"], r["won"])
        priced.append(r)
        if i % 40 == 0:
            print(f"  priced {len(priced)}/{i}...")

    print(f"\npriced {len(priced)}/{len(rows)} (no candle coverage: {unpriced})")
    if not priced:
        return

    # quote-quality reality check: what the sleeve ASSUMED vs what the book actually was
    spreads = [round((r["mkt_yes_ask"] - r["mkt_yes_bid"]) * 100) for r in priced]
    drift = [abs(r["mkt_yes_ask"] - r["price"]) * 100 for r in priced]
    print(f"\nmeasured yes spread at signal (cents): median={st.median(spreads):.0f} "
          f"p25={st.quantiles(spreads,n=4)[0]:.0f} p75={st.quantiles(spreads,n=4)[2]:.0f} max={max(spreads)}")
    print(f"logged yes_ask vs measured yes_ask (cents apart): median={st.median(drift):.1f} max={max(drift):.1f}")
    nos = [r for r in priced if r["side"] == "no"]
    if nos:
        gap = [(r["true_cost"] - r["naive_cost"]) * 100 for r in nos]
        print(f"NO-side cost understatement by the naive fix (cents): median={st.median(gap):.1f} "
              f"mean={st.mean(gap):.1f} max={max(gap):.1f}")

    results = {"n_settled": len(rows), "n_priced": len(priced), "n_unpriced": unpriced,
               "median_spread_c": st.median(spreads), "arms": {}}

    print("\n" + "=" * 78)
    print(f"{'arm':34s} {'n':>4s} {'win%':>6s} {'EV/ct':>9s} {'day-clust t':>12s} {'days':>5s}")
    print("=" * 78)
    arms = [
        ("(a) as-logged [BUGGY]", priced, lambda r: r["pnl"]),
        ("(b) naive fix (NO=1-yes_ask)", priced, lambda r: r["pnl_naive"]),
        ("(c) TRUE executable", priced, lambda r: r["pnl_true"]),
        ("    -- YES only (acct was ok)", [r for r in priced if r["side"] == "yes"], lambda r: r["pnl_true"]),
        ("    -- NO only", nos, lambda r: r["pnl_true"]),
    ]
    for label, sub, key in arms:
        if not sub:
            continue
        m, t, d = day_clustered(sub, key)
        ev = st.mean([key(r) for r in sub])
        win = 100 * sum(r["won"] for r in sub) / len(sub)
        print(f"{label:34s} {len(sub):4d} {win:5.1f}% {ev:+9.4f} {t:+12.2f} {d:5d}")
        results["arms"][label.strip()] = {"n": len(sub), "win_pct": round(win, 1),
                                          "ev_per_ct": round(ev, 4),
                                          "day_clustered_t": round(t, 2) if t else None, "days": d}
    print("=" * 78)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({"summary": results,
                   "trades": [{k: v for k, v in r.items()
                               if k in ("date", "ticker", "side", "price", "mkt_yes_bid", "mkt_yes_ask",
                                        "true_cost", "won", "pnl", "pnl_naive", "pnl_true", "edge", "fc_prob")}
                              for r in priced]}, fh, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
