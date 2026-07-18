#!/usr/bin/env python3
"""
kalshi_structural_arb.py
=========================

OOS test of the #1-ranked Kalshi strategy-sweep candidate: intra-Kalshi
STRUCTURAL / logical-consistency NO-ARB (ladder monotonicity, complement
sum, mutually-exclusive event-sum completeness).

This scans Kalshi's own free public order-book data (no auth needed for
market data) and applies the anti-stale-quote discipline that killed the
analogous Polymarket candidate (which turned out to be 100% stale-quote
artifacts, not real executable arbitrage):

  1. NET of Kalshi's real per-contract fee (quadratic formula, both legs,
     both directions -- see `kalshi_fee()`).
  2. Executable DEPTH on both legs, taken from the live order book (not a
     1-lot phantom quote) -- both from top-of-book size fields AND a direct
     /orderbook re-fetch for anything flagged.
  3. PERSISTENCE -- a violation must survive across multiple polls spaced
     minutes apart. A violation seen once and gone on the next poll is
     STALE, not real.
  4. EXACT nesting / mutual-exclusivity -- markets are only compared within
     the same Kalshi `event_ticker` (guarantees identical resolution source,
     dates, and settlement rules), using Kalshi's own `mutually_exclusive`
     event flag and `strike_type`/`floor_strike` fields to build ladders and
     exhaustive partitions. No cross-event pairing is ever attempted.

Three structures scanned (single-venue, single-exchange, all Kalshi):

  S1 LADDER MONOTONICITY   -- within one event, a family of same-direction
                               threshold markets ("greater"/"less" strike
                               type) must have monotonic YES probability.
                               Violation = higher-implication-tier YES-BID >
                               lower-implication-tier YES-ASK.
                               (PAVA/isotonic regression is used to produce
                               the diagnostic "fair" monotone curve and a
                               single ladder-level violation-mass metric,
                               mirroring the reference isotonic approaches;
                               the *tradeable* test remains the exact
                               pairwise bid/ask crossing check net of fees.)

  S2 COMPLEMENT SUM         -- single market: YES_ask + NO_ask < $1 (buy
                               both legs, collect $1 for less) or YES_bid +
                               NO_bid > $1 (sell both -- executed here as
                               "buy NO to close the YES side" is NOT
                               applicable; this is the classic two-sided
                               top-of-book cross and is expected to be
                               heavily latency-sniped).

  S3 EVENT-SUM COMPLETENESS -- an event flagged `mutually_exclusive=true`
                               by Kalshi itself (temperature/price brackets,
                               "who wins" fields, etc). Buy every YES leg
                               (sum of asks) or buy every NO leg (sum of
                               asks, no shorting needed) and compare to the
                               guaranteed payout ($1 or N-1 respectively).

Run:
    python3 kalshi_structural_arb.py --polls 6 --interval 120

Outputs:
    kalshi_structural_arb_report.md
    kalshi_structural_arb_summary.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HEADERS = {"User-Agent": "kalshi-structural-arb-oos-test/1.0"}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MIN_DEPTH_CONTRACTS = 5          # minimum resting size to count a quote as executable (not phantom)
MIN_EDGE_CENTS = 0.05            # minimum net-of-fee locked edge (in dollars) to even flag as a candidate
REQUIRE_POLLS_FOR_REAL = 3       # a violation key must be observed in at least this many polls...
REQUIRE_POLL_FRACTION = 0.5      # ...or at least this fraction of total polls, whichever is looser
ORDERBOOK_VERIFY_TOP_N = 400     # cap on how many distinct candidate keys we re-verify via /orderbook per poll
REQUEST_TIMEOUT = 25
MAX_RETRIES = 3
ORDERBOOK_VERIFY_WORKERS = 24     # thread pool size for concurrent /orderbook re-verification


# ---------------------------------------------------------------------------
# Kalshi fee model
# ---------------------------------------------------------------------------
#
# Kalshi's general trading fee (documented "quadratic" fee_type, the value
# returned per-series by /series/{ticker} as fee_type/fee_multiplier) is:
#
#     fee_dollars = ceil( fee_multiplier * 0.07 * C * P * (1-P) * 100 ) / 100
#
# where C = number of contracts, P = execution price in dollars (0..1).
# This is symmetric in P (peaks at P=0.50, worst case 1.75c/contract on
# $1 notional = 1.75%, matching the "~1.75%/leg" figure used across the
# reference repos). We charge this on EVERY leg of every structure, in
# BOTH directions, using TAKER assumptions (crossing the resting book with
# an IOC/marketable order) -- this is the conservative, correct assumption
# for "prove it's real": a resting maker order is not guaranteed to fill
# before the quote moves, which would defeat the whole point of this test.

def kalshi_fee(price_dollars: float, contracts: float = 1.0, fee_multiplier: float = 1.0) -> float:
    if contracts <= 0:
        return 0.0
    p = min(max(price_dollars, 0.0), 1.0)
    raw = fee_multiplier * 0.07 * contracts * p * (1.0 - p)
    return math.ceil(raw * 100.0) / 100.0


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update(HEADERS)
_adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)


def _get(path: str, params: Optional[dict] = None) -> dict:
    url = f"{BASE}{path}"
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} attempts: {last_err}")


def fetch_all_open_events(page_limit: int = 200, max_pages: int = 500) -> List[dict]:
    """Fetch every open event with nested markets, paginated."""
    events: List[dict] = []
    cursor = ""
    pages = 0
    while True:
        params = {"status": "open", "with_nested_markets": "true", "limit": page_limit}
        if cursor:
            params["cursor"] = cursor
        d = _get("/events", params)
        evs = d.get("events", [])
        events.extend(evs)
        cursor = d.get("cursor", "")
        pages += 1
        if not cursor or not evs or pages >= max_pages:
            break
    return events


def _fetch_one_series_fee(t: str) -> Tuple[str, float]:
    try:
        d = _get(f"/series/{t}")
        s = d.get("series", {})
        return t, float(s.get("fee_multiplier", 1.0) or 1.0)
    except Exception:
        return t, 1.0


def fetch_series_fee_multipliers(series_tickers: List[str], workers: int = 24) -> Dict[str, float]:
    """Best-effort lookup of fee_multiplier per series (defaults to 1.0).
    Kalshi has thousands of series in total, but only a handful are ever
    involved in an actual flagged candidate on a given poll, so this is
    called lazily (only for series that appear in flagged candidates) and
    in parallel, rather than for the whole ~3000-series universe up front."""
    out: Dict[str, float] = {}
    if not series_tickers:
        return out
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for t, mult in pool.map(_fetch_one_series_fee, series_tickers):
            out[t] = mult
    return out


def fetch_orderbook(ticker: str) -> Optional[dict]:
    try:
        d = _get(f"/markets/{ticker}/orderbook")
        return d.get("orderbook_fp") or d.get("orderbook")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Market parsing helpers
# ---------------------------------------------------------------------------

def f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


@dataclasses.dataclass
class Quote:
    yes_bid: float
    yes_bid_sz: float
    yes_ask: float
    yes_ask_sz: float
    no_bid: float
    no_bid_sz: float
    no_ask: float
    no_ask_sz: float

    @property
    def yes_bid_valid(self) -> bool:
        return self.yes_bid > 0 and self.yes_bid_sz >= MIN_DEPTH_CONTRACTS

    @property
    def yes_ask_valid(self) -> bool:
        return self.yes_ask > 0 and self.yes_ask_sz >= MIN_DEPTH_CONTRACTS

    @property
    def no_bid_valid(self) -> bool:
        return self.no_bid > 0 and self.no_bid_sz >= MIN_DEPTH_CONTRACTS

    @property
    def no_ask_valid(self) -> bool:
        return self.no_ask > 0 and self.no_ask_sz >= MIN_DEPTH_CONTRACTS


def parse_quote(m: dict) -> Quote:
    return Quote(
        yes_bid=f(m.get("yes_bid_dollars")),
        yes_bid_sz=f(m.get("yes_bid_size_fp")),
        yes_ask=f(m.get("yes_ask_dollars")),
        yes_ask_sz=f(m.get("yes_ask_size_fp")),
        no_bid=f(m.get("no_bid_dollars")),
        no_bid_sz=f(m.get("no_bid_size_fp")),
        no_ask=f(m.get("no_ask_dollars")),
        no_ask_sz=f(m.get("no_ask_size_fp")),
    )


def orderbook_top(levels: Optional[List[List[str]]]) -> Tuple[float, float]:
    """levels = list of [price_str, size_str], resting BUY orders (bid ladder).
    Returns (best_price, size_at_best_price). Empty -> (0,0)."""
    if not levels:
        return 0.0, 0.0
    best_price = 0.0
    best_size = 0.0
    for p, s in levels:
        p_f, s_f = float(p), float(s)
        if p_f > best_price:
            best_price, best_size = p_f, s_f
    return best_price, best_size


def verify_orderbook_depth(ticker: str, side: str, price: float, min_contracts: float) -> Tuple[bool, float]:
    """Re-fetch the live order book and confirm `price` is still the best
    quote on `side` ('yes_ask' or 'yes_bid' or 'no_ask' or 'no_bid') with at
    least `min_contracts` resting there. Returns (ok, size_confirmed)."""
    ob = fetch_orderbook(ticker)
    if not ob:
        return False, 0.0
    yes_levels = ob.get("yes_dollars") or []
    no_levels = ob.get("no_dollars") or []
    yes_bid_p, yes_bid_s = orderbook_top(yes_levels)
    no_bid_p, no_bid_s = orderbook_top(no_levels)
    yes_ask_p, yes_ask_s = (round(1.0 - no_bid_p, 4), no_bid_s) if no_bid_p > 0 else (0.0, 0.0)
    no_ask_p, no_ask_s = (round(1.0 - yes_bid_p, 4), yes_bid_s) if yes_bid_p > 0 else (0.0, 0.0)
    mapping = {
        "yes_bid": (yes_bid_p, yes_bid_s),
        "yes_ask": (yes_ask_p, yes_ask_s),
        "no_bid": (no_bid_p, no_bid_s),
        "no_ask": (no_ask_p, no_ask_s),
    }
    p, s = mapping[side]
    ok = (abs(p - price) < 1e-6) and (s >= min_contracts)
    return ok, s


# ---------------------------------------------------------------------------
# Isotonic regression (PAVA) -- diagnostic ladder-fit
# ---------------------------------------------------------------------------

def pava_isotonic(values: List[float], decreasing: bool) -> List[float]:
    """Pool-Adjacent-Violators for a 1D sequence, unweighted. Returns the
    monotone (non-increasing if decreasing=True else non-decreasing) L2
    projection of `values`."""
    y = [-v for v in values] if decreasing else list(values)
    n = len(y)
    if n == 0:
        return []
    # stack of (sum, count, level)
    level_vals = list(y)
    level_w = [1.0] * n
    stack: List[Tuple[float, float]] = []  # (mean, weight)
    for v, w in zip(level_vals, level_w):
        stack.append((v, w))
        while len(stack) > 1 and stack[-2][0] > stack[-1][0]:
            v2, w2 = stack.pop()
            v1, w1 = stack.pop()
            merged = ((v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2)
            stack.append(merged)
    out = []
    for mean, w in stack:
        out.extend([mean] * int(w))
    if decreasing:
        out = [-v for v in out]
    return out


# ---------------------------------------------------------------------------
# Structure detection & scanning
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Violation:
    key: str
    structure: str  # "S1_LADDER", "S2_COMPLEMENT", "S3_EVENTSUM"
    event_ticker: str
    series_ticker: str
    description: str
    legs: List[dict]                 # list of {ticker, side, price, size, action}
    gross_edge: float                # dollars, before fee, per 1 unit of the trade
    fee_total: float                 # dollars
    net_edge: float                  # dollars, per unit
    notional: float                  # dollars committed per unit
    depth_contracts: float           # max size tradeable at exactly these quoted prices (min across legs)


def scan_ladders(events: List[dict], fee_mult: Dict[str, float]) -> List[Violation]:
    out: List[Violation] = []
    for ev in events:
        if ev.get("mutually_exclusive"):
            continue  # ladders are the *non*-exclusive nested-implication case
        mkts = ev.get("markets", [])
        if len(mkts) < 2:
            continue
        # group by strike_type; only "greater"/"less" numeric ladders qualify
        by_type: Dict[str, List[dict]] = defaultdict(list)
        for m in mkts:
            st = m.get("strike_type")
            if st in ("greater", "less") and m.get("floor_strike") is not None:
                by_type[st].append(m)
        for st, group in by_type.items():
            if len(group) < 2:
                continue
            group_sorted = sorted(group, key=lambda m: f(m.get("floor_strike")))
            quotes = [parse_quote(m) for m in group_sorted]
            fmult = fee_mult.get(ev.get("series_ticker", ""), 1.0)
            n = len(group_sorted)
            # "greater": prob non-increasing with strike -> for i<j, need P(j)<=P(i)
            #            violation: yes_bid(j) > yes_ask(i) [sell high-strike, buy low-strike]
            # "less":    prob non-decreasing with strike -> for i<j, need P(i)<=P(j)
            #            violation: yes_bid(i) > yes_ask(j) [sell low-strike, buy high-strike]
            for i in range(n):
                for j in range(i + 1, n):
                    if st == "greater":
                        buy_m, buy_q = group_sorted[i], quotes[i]     # lower strike, buy YES ask
                        sell_m, sell_q = group_sorted[j], quotes[j]   # higher strike, sell YES (bid)
                    else:  # "less"
                        buy_m, buy_q = group_sorted[j], quotes[j]     # higher strike, buy YES ask
                        sell_m, sell_q = group_sorted[i], quotes[i]   # lower strike, sell YES (bid)
                    if not (buy_q.yes_ask_valid and sell_q.yes_bid_valid):
                        continue
                    gross = sell_q.yes_bid - buy_q.yes_ask
                    if gross <= 0:
                        continue
                    fee = kalshi_fee(buy_q.yes_ask, 1, fmult) + kalshi_fee(sell_q.yes_bid, 1, fmult)
                    net = gross - fee
                    if net < MIN_EDGE_CENTS:
                        continue
                    depth = min(buy_q.yes_ask_sz, sell_q.yes_bid_sz)
                    key = f"S1|{ev['event_ticker']}|{st}|BUY:{buy_m['ticker']}|SELL:{sell_m['ticker']}"
                    out.append(Violation(
                        key=key,
                        structure="S1_LADDER",
                        event_ticker=ev["event_ticker"],
                        series_ticker=ev.get("series_ticker", ""),
                        description=(
                            f"Ladder monotonicity ({st}): BUY YES {buy_m['ticker']} "
                            f"@{buy_q.yes_ask:.2f} (strike {buy_m.get('floor_strike')}) / "
                            f"SELL YES {sell_m['ticker']} @{sell_q.yes_bid:.2f} "
                            f"(strike {sell_m.get('floor_strike')})"
                        ),
                        legs=[
                            {"ticker": buy_m["ticker"], "side": "yes", "action": "buy",
                             "price": buy_q.yes_ask, "size": buy_q.yes_ask_sz},
                            {"ticker": sell_m["ticker"], "side": "yes", "action": "sell",
                             "price": sell_q.yes_bid, "size": sell_q.yes_bid_sz},
                        ],
                        gross_edge=gross, fee_total=fee, net_edge=net,
                        notional=buy_q.yes_ask, depth_contracts=depth,
                    ))
    return out


def scan_complement(events: List[dict], fee_mult: Dict[str, float]) -> List[Violation]:
    out: List[Violation] = []
    for ev in events:
        fmult = fee_mult.get(ev.get("series_ticker", ""), 1.0)
        for m in ev.get("markets", []):
            q = parse_quote(m)
            ticker = m["ticker"]
            # Buy YES + Buy NO: cost yes_ask+no_ask, guaranteed payout $1
            if q.yes_ask_valid and q.no_ask_valid:
                gross = 1.0 - (q.yes_ask + q.no_ask)
                if gross > 0:
                    fee = kalshi_fee(q.yes_ask, 1, fmult) + kalshi_fee(q.no_ask, 1, fmult)
                    net = gross - fee
                    if net >= MIN_EDGE_CENTS:
                        depth = min(q.yes_ask_sz, q.no_ask_sz)
                        out.append(Violation(
                            key=f"S2|{ticker}|BUYBOTH",
                            structure="S2_COMPLEMENT",
                            event_ticker=ev["event_ticker"], series_ticker=ev.get("series_ticker", ""),
                            description=(f"Complement sum: BUY YES {ticker} @{q.yes_ask:.2f} + "
                                         f"BUY NO {ticker} @{q.no_ask:.2f}, cost {q.yes_ask+q.no_ask:.2f} < $1"),
                            legs=[
                                {"ticker": ticker, "side": "yes", "action": "buy", "price": q.yes_ask, "size": q.yes_ask_sz},
                                {"ticker": ticker, "side": "no", "action": "buy", "price": q.no_ask, "size": q.no_ask_sz},
                            ],
                            gross_edge=gross, fee_total=fee, net_edge=net,
                            notional=q.yes_ask + q.no_ask, depth_contracts=depth,
                        ))
            # Sell YES + Sell NO (i.e. yes_bid+no_bid>1): equivalent tradeable
            # form is "the market is simultaneously willing to pay away more
            # than $1 total" -- we report it, executed by hitting both bids
            # (requires ability to sell/short both sides, which Kalshi supports
            # once you hold no position via bid-side marketable sell orders on
            # existing inventory OR opening orders on both sides is not always
            # symmetric; we flag it for completeness but mark it "bid-side, may
            # require inventory" in the leg action).
            if q.yes_bid_valid and q.no_bid_valid:
                gross = (q.yes_bid + q.no_bid) - 1.0
                if gross > 0:
                    fee = kalshi_fee(q.yes_bid, 1, fmult) + kalshi_fee(q.no_bid, 1, fmult)
                    net = gross - fee
                    if net >= MIN_EDGE_CENTS:
                        depth = min(q.yes_bid_sz, q.no_bid_sz)
                        out.append(Violation(
                            key=f"S2|{ticker}|SELLBOTH",
                            structure="S2_COMPLEMENT",
                            event_ticker=ev["event_ticker"], series_ticker=ev.get("series_ticker", ""),
                            description=(f"Complement sum: SELL YES {ticker} @{q.yes_bid:.2f} + "
                                         f"SELL NO {ticker} @{q.no_bid:.2f}, proceeds {q.yes_bid+q.no_bid:.2f} > $1"),
                            legs=[
                                {"ticker": ticker, "side": "yes", "action": "sell", "price": q.yes_bid, "size": q.yes_bid_sz},
                                {"ticker": ticker, "side": "no", "action": "sell", "price": q.no_bid, "size": q.no_bid_sz},
                            ],
                            gross_edge=gross, fee_total=fee, net_edge=net,
                            notional=q.yes_bid + q.no_bid, depth_contracts=depth,
                        ))
    return out


def verify_exhaustive_numeric_partition(mkts: List[dict]) -> bool:
    """PROOF of collective exhaustiveness for a range/bracket event, not just
    Kalshi's `mutually_exclusive` flag (which only guarantees "at most one").

    This matters because Kalshi's `mutually_exclusive=true` flag is used on
    BOTH (a) genuine tiled numeric brackets (temperature/price ranges, which
    ARE collectively exhaustive) and (b) named-candidate/categorical fields
    (elections, "who wins" markets) that are only a *partial list* of
    possible outcomes -- e.g. a primary race can list 2 minor candidates
    whose combined YES-ask sums to a few cents because the market assigns
    ~95% probability to an unlisted candidate winning. Buying "all" legs of
    a non-exhaustive set is NOT a guaranteed $1 payout -- it is a bet that
    one of the *listed* options wins, which is exactly the false-completeness
    trap this scan must avoid.

    We therefore only allow Structure 3 (event-sum) on events where EVERY
    market has a numeric strike_type ("less"/"between"/"greater") that can
    be proven, from Kalshi's own floor_strike/cap_strike fields, to TILE the
    real line with no gaps and no overlaps: exactly one unbounded-below
    ("less") leg, exactly one unbounded-above ("greater") leg, and
    contiguous "between" brackets in between. Categorical/candidate-style
    events (strike_type == "custom") are excluded entirely from S3, even
    though Kalshi flags them mutually_exclusive=true, because exhaustiveness
    cannot be verified from structured fields alone.
    """
    if len(mkts) < 2:
        return False
    for m in mkts:
        if m.get("strike_type") not in ("less", "between", "greater"):
            return False
    less = [m for m in mkts if m["strike_type"] == "less"]
    greater = [m for m in mkts if m["strike_type"] == "greater"]
    between = [m for m in mkts if m["strike_type"] == "between"]
    if len(less) != 1 or len(greater) != 1:
        return False
    intervals: List[Tuple[float, float]] = [(-math.inf, f(less[0].get("cap_strike")))]
    for m in sorted(between, key=lambda m: f(m.get("floor_strike"))):
        fl, cp = f(m.get("floor_strike")), f(m.get("cap_strike"))
        if cp <= fl:
            return False
        intervals.append((fl, cp))
    intervals.append((f(greater[0].get("floor_strike")), math.inf))
    gaps = []
    for i in range(len(intervals) - 1):
        gap = intervals[i + 1][0] - intervals[i][1]
        if gap < -1e-6:
            return False  # overlapping brackets -> ambiguous, not safe
        gaps.append(gap)
    if not gaps:
        return True
    med = sorted(gaps)[len(gaps) // 2]
    finite_widths = [b - a for a, b in intervals[1:-1]]
    typical_width = (sum(finite_widths) / len(finite_widths)) if finite_widths else 1.0
    outlier_tol = max(med, 0.0) + max(typical_width * 0.5, 1.0)
    for g in gaps:
        if g > outlier_tol:
            return False  # a genuinely missing bracket -> not proven exhaustive
    return True


def scan_event_sum(events: List[dict], fee_mult: Dict[str, float]) -> List[Violation]:
    out: List[Violation] = []
    for ev in events:
        if not ev.get("mutually_exclusive"):
            continue
        mkts = ev.get("markets", [])
        n = len(mkts)
        if n < 2:
            continue
        if not verify_exhaustive_numeric_partition(mkts):
            continue
        fmult = fee_mult.get(ev.get("series_ticker", ""), 1.0)
        quotes = [parse_quote(m) for m in mkts]

        # Direction A: buy every YES ask -> guaranteed payout $1
        if all(q.yes_ask_valid for q in quotes):
            sum_ask = sum(q.yes_ask for q in quotes)
            fee_total = sum(kalshi_fee(q.yes_ask, 1, fmult) for q in quotes)
            gross = 1.0 - sum_ask
            net = gross - fee_total
            if net >= MIN_EDGE_CENTS:
                depth = min(q.yes_ask_sz for q in quotes)
                out.append(Violation(
                    key=f"S3|{ev['event_ticker']}|BUYALLYES",
                    structure="S3_EVENTSUM", event_ticker=ev["event_ticker"],
                    series_ticker=ev.get("series_ticker", ""),
                    description=(f"Event-sum: BUY all {n} YES legs of {ev['event_ticker']}, "
                                 f"sum(ask)={sum_ask:.2f} < $1.00 guaranteed payout"),
                    legs=[{"ticker": m["ticker"], "side": "yes", "action": "buy",
                           "price": q.yes_ask, "size": q.yes_ask_sz} for m, q in zip(mkts, quotes)],
                    gross_edge=gross, fee_total=fee_total, net_edge=net,
                    notional=sum_ask, depth_contracts=depth,
                ))

        # Direction B: buy every NO ask -> guaranteed payout (n-1); executable
        # without shorting (equivalent to "sum(yes_bid) > 1").
        if all(q.no_ask_valid for q in quotes):
            sum_ask = sum(q.no_ask for q in quotes)
            fee_total = sum(kalshi_fee(q.no_ask, 1, fmult) for q in quotes)
            gross = (n - 1) - sum_ask
            net = gross - fee_total
            if net >= MIN_EDGE_CENTS:
                depth = min(q.no_ask_sz for q in quotes)
                out.append(Violation(
                    key=f"S3|{ev['event_ticker']}|BUYALLNO",
                    structure="S3_EVENTSUM", event_ticker=ev["event_ticker"],
                    series_ticker=ev.get("series_ticker", ""),
                    description=(f"Event-sum: BUY all {n} NO legs of {ev['event_ticker']}, "
                                 f"sum(ask)={sum_ask:.2f} < ${n-1}.00 guaranteed payout"),
                    legs=[{"ticker": m["ticker"], "side": "no", "action": "buy",
                           "price": q.no_ask, "size": q.no_ask_sz} for m, q in zip(mkts, quotes)],
                    gross_edge=gross, fee_total=fee_total, net_edge=net,
                    notional=sum_ask, depth_contracts=depth,
                ))
    return out


def ladder_pava_diagnostics(events: List[dict]) -> List[dict]:
    """Diagnostic-only: for every non-exclusive greater/less ladder with >=3
    points, fit PAVA to the mid-price curve and report total violation mass
    (sum of |raw - isotonic| over points where raw broke monotonicity)."""
    diag = []
    for ev in events:
        if ev.get("mutually_exclusive"):
            continue
        mkts = ev.get("markets", [])
        by_type: Dict[str, List[dict]] = defaultdict(list)
        for m in mkts:
            st = m.get("strike_type")
            if st in ("greater", "less") and m.get("floor_strike") is not None:
                by_type[st].append(m)
        for st, group in by_type.items():
            if len(group) < 3:
                continue
            group_sorted = sorted(group, key=lambda m: f(m.get("floor_strike")))
            mids = []
            for m in group_sorted:
                q = parse_quote(m)
                yb, ya = q.yes_bid, q.yes_ask
                if yb > 0 and ya > 0:
                    mids.append((yb + ya) / 2.0)
                elif ya > 0:
                    mids.append(ya)
                elif yb > 0:
                    mids.append(yb)
                else:
                    mids.append(None)
            if any(v is None for v in mids):
                continue
            decreasing = (st == "greater")
            fit = pava_isotonic(mids, decreasing=decreasing)
            mass = sum(abs(a - b) for a, b in zip(mids, fit))
            if mass > 0:
                diag.append({
                    "event_ticker": ev["event_ticker"], "strike_type": st,
                    "n_points": len(mids), "violation_mass": round(mass, 4),
                })
    return diag


# ---------------------------------------------------------------------------
# Main scan loop with persistence tracking
# ---------------------------------------------------------------------------

def run(polls: int, interval: float, out_prefix: str) -> None:
    t_start = time.time()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting scan: {polls} polls, {interval}s apart", flush=True)

    poll_records: List[dict] = []
    violation_history: Dict[str, List[dict]] = defaultdict(list)  # key -> list of {poll_idx, net_edge, depth, ...}
    violation_meta: Dict[str, Violation] = {}
    fee_mult_cache: Dict[str, float] = {}
    all_series_seen: set = set()
    pava_diag_last: List[dict] = []

    for poll_idx in range(polls):
        t0 = time.time()
        try:
            events = fetch_all_open_events()
        except Exception as e:
            print(f"  poll {poll_idx}: FAILED to fetch events: {e}", flush=True)
            traceback.print_exc()
            time.sleep(interval)
            continue
        fetch_s = time.time() - t0

        n_events = len(events)
        n_markets = sum(len(ev.get("markets", [])) for ev in events)
        n_mece_events = sum(1 for ev in events if ev.get("mutually_exclusive"))

        # Pass 1: cheap candidate discovery using cached / default (1.0) fee
        # multipliers. Kalshi has ~3000 distinct series in total but a given
        # poll only ever flags candidates in a handful of them, so we do NOT
        # eagerly fetch fee_multiplier for the whole universe (that would be
        # ~3000 sequential/parallel /series calls every poll). Instead we
        # discover which series are actually involved in a flagged candidate,
        # fetch just those (parallel, cached across polls), then re-run the
        # scan once more (pass 2) so every REPORTED edge uses the true
        # per-series fee_multiplier, not the 1.0 default.
        cand_s1 = scan_ladders(events, fee_mult_cache)
        cand_s2 = scan_complement(events, fee_mult_cache)
        cand_s3 = scan_event_sum(events, fee_mult_cache)
        involved_series = {v.series_ticker for v in (cand_s1 + cand_s2 + cand_s3) if v.series_ticker}
        new_series = involved_series - all_series_seen
        if new_series:
            fee_mult_cache.update(fetch_series_fee_multipliers(sorted(new_series)))
            all_series_seen |= new_series
            # Pass 2: recompute with accurate multipliers for involved series.
            cand_s1 = scan_ladders(events, fee_mult_cache)
            cand_s2 = scan_complement(events, fee_mult_cache)
            cand_s3 = scan_event_sum(events, fee_mult_cache)
        all_cand = cand_s1 + cand_s2 + cand_s3

        pava_diag_last = ladder_pava_diagnostics(events)

        # Orderbook re-verification for every candidate this poll (cap to avoid runaway calls).
        # Parallelized across a thread pool since each leg check is one HTTP round-trip
        # (~0.2-0.3s serial -> hundreds of legs would otherwise dominate wall-clock time).
        cand_to_verify = all_cand[:ORDERBOOK_VERIFY_TOP_N]
        for v in cand_to_verify:
            violation_meta[v.key] = v

        leg_jobs = []  # (violation_key, leg_idx, ticker, side_key, price)
        for v in cand_to_verify:
            for leg_idx, leg in enumerate(v.legs):
                side_key = f"{leg['side']}_{'ask' if leg['action']=='buy' else 'bid'}"
                leg_jobs.append((v.key, leg_idx, leg["ticker"], side_key, leg["price"]))

        leg_results: Dict[Tuple[str, int], Tuple[bool, float]] = {}
        verified = 0
        if leg_jobs:
            with ThreadPoolExecutor(max_workers=ORDERBOOK_VERIFY_WORKERS) as pool:
                fut_map = {
                    pool.submit(verify_orderbook_depth, ticker, side_key, price, MIN_DEPTH_CONTRACTS): (vk, li)
                    for (vk, li, ticker, side_key, price) in leg_jobs
                }
                for fut in as_completed(fut_map):
                    vk, li = fut_map[fut]
                    try:
                        ok, sz = fut.result()
                    except Exception:
                        ok, sz = False, 0.0
                    leg_results[(vk, li)] = (ok, sz)
                    verified += 1

        for v in cand_to_verify:
            ok_all = True
            min_confirmed_depth = float("inf")
            for leg_idx in range(len(v.legs)):
                ok, sz = leg_results.get((v.key, leg_idx), (False, 0.0))
                ok_all = ok_all and ok
                min_confirmed_depth = min(min_confirmed_depth, sz)
            violation_history[v.key].append({
                "poll_idx": poll_idx,
                "ts": datetime.now(timezone.utc).isoformat(),
                "net_edge": v.net_edge,
                "gross_edge": v.gross_edge,
                "fee_total": v.fee_total,
                "quoted_depth": v.depth_contracts,
                "orderbook_confirmed": ok_all,
                "orderbook_confirmed_depth": (min_confirmed_depth if min_confirmed_depth != float("inf") else 0.0),
            })

        rec = {
            "poll_idx": poll_idx,
            "ts": datetime.now(timezone.utc).isoformat(),
            "fetch_seconds": round(fetch_s, 2),
            "n_events": n_events,
            "n_markets": n_markets,
            "n_mece_events": n_mece_events,
            "n_candidates_S1": len(cand_s1),
            "n_candidates_S2": len(cand_s2),
            "n_candidates_S3": len(cand_s3),
            "n_orderbook_verifications": verified,
        }
        poll_records.append(rec)
        print(f"  poll {poll_idx}: {n_events} events / {n_markets} markets "
              f"({n_mece_events} MECE) in {fetch_s:.1f}s -> candidates S1={len(cand_s1)} "
              f"S2={len(cand_s2)} S3={len(cand_s3)}, verified {verified} legs", flush=True)

        if poll_idx < polls - 1:
            time.sleep(interval)

    total_polls_done = len(poll_records)

    # -----------------------------------------------------------------
    # Classification: REAL vs STALE per violation key
    # -----------------------------------------------------------------
    real_keys: List[str] = []
    stale_keys: List[str] = []
    threshold_polls = max(1, min(REQUIRE_POLLS_FOR_REAL, math.ceil(REQUIRE_POLL_FRACTION * total_polls_done)))

    for key, hist in violation_history.items():
        n_seen = len(hist)
        n_confirmed = sum(1 for h in hist if h["orderbook_confirmed"])
        n_net_positive = sum(1 for h in hist if h["net_edge"] >= MIN_EDGE_CENTS)
        is_real = (n_seen >= threshold_polls) and (n_confirmed >= threshold_polls) and (n_net_positive >= threshold_polls)
        if is_real:
            real_keys.append(key)
        else:
            stale_keys.append(key)

    def summarize(keys: List[str], structure_prefix: str) -> dict:
        keys = [k for k in keys if k.startswith(structure_prefix)]
        if not keys:
            return {"flagged": 0, "real": 0, "mean_net_edge_cents_per_dollar": 0.0,
                    "mean_depth_contracts": 0.0, "max_net_edge_cents_per_dollar": 0.0}
        nets = []
        depths = []
        for k in keys:
            hist = violation_history[k]
            confirmed = [h for h in hist if h["orderbook_confirmed"]]
            if confirmed:
                nets.append(max(h["net_edge"] for h in confirmed) * 100)
                depths.append(max(h["orderbook_confirmed_depth"] for h in confirmed))
            else:
                nets.append(max(h["net_edge"] for h in hist) * 100)
                depths.append(0.0)
        return {
            "flagged": len(keys),
            "mean_net_edge_cents_per_dollar": round(sum(nets) / len(nets), 3) if nets else 0.0,
            "max_net_edge_cents_per_dollar": round(max(nets), 3) if nets else 0.0,
            "mean_depth_contracts": round(sum(depths) / len(depths), 1) if depths else 0.0,
        }

    struct_summary = {}
    for pfx, name in [("S1", "S1_LADDER"), ("S2", "S2_COMPLEMENT"), ("S3", "S3_EVENTSUM")]:
        flagged_keys = [k for k in violation_history if k.startswith(pfx)]
        real_this = [k for k in real_keys if k.startswith(pfx)]
        s = summarize(flagged_keys, pfx)
        s["real"] = len(real_this)
        s["stale_or_unconfirmed"] = s["flagged"] - len(real_this)
        struct_summary[name] = s

    total_flagged = len(violation_history)
    total_real = len(real_keys)
    stale_ratio = round(1.0 - (total_real / total_flagged), 4) if total_flagged else None

    days_scanned = round((time.time() - t_start) / 86400.0, 6)
    weeks_scanned = max(days_scanned / 7.0, 1e-9)
    freq_per_week_flagged = round(total_flagged / weeks_scanned, 2) if total_flagged else 0.0
    freq_per_week_real = round(total_real / weeks_scanned, 2) if total_real else 0.0

    real_detail = []
    for k in real_keys:
        v = violation_meta[k]
        hist = violation_history[k]
        confirmed = [h for h in hist if h["orderbook_confirmed"]]
        real_detail.append({
            "key": k,
            "structure": v.structure,
            "event_ticker": v.event_ticker,
            "series_ticker": v.series_ticker,
            "description": v.description,
            "legs": v.legs,
            "n_polls_seen": len(hist),
            "n_polls_confirmed_executable": len(confirmed),
            "mean_net_edge_cents": round(sum(h["net_edge"] for h in hist) / len(hist) * 100, 3),
            "min_confirmed_depth_contracts": (min(h["orderbook_confirmed_depth"] for h in confirmed)
                                               if confirmed else 0.0),
        })
    real_detail.sort(key=lambda d: -d["mean_net_edge_cents"])

    summary = {
        "run_metadata": {
            "started_utc": datetime.fromtimestamp(t_start, tz=timezone.utc).isoformat(),
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "polls_requested": polls,
            "polls_completed": total_polls_done,
            "interval_seconds": interval,
            "persistence_threshold_polls": threshold_polls,
            "min_depth_contracts": MIN_DEPTH_CONTRACTS,
            "min_edge_dollars": MIN_EDGE_CENTS,
            "fee_model": "kalshi_fee = ceil(fee_multiplier * 0.07 * C * P * (1-P) * 100)/100 dollars, both legs, taker-side",
        },
        "universe": {
            "poll_records": poll_records,
        },
        "structure_summary": struct_summary,
        "totals": {
            "total_flagged_violation_keys": total_flagged,
            "total_real_persistent_executable_violation_keys": total_real,
            "stale_or_phantom_ratio": stale_ratio,
            "frequency_per_week_flagged": freq_per_week_flagged,
            "frequency_per_week_real": freq_per_week_real,
        },
        "pava_ladder_diagnostics_last_poll": sorted(pava_diag_last, key=lambda d: -d["violation_mass"])[:25],
        "real_violations_detail": real_detail[:50],
        "verdict": None,  # filled below
    }

    # -----------------------------------------------------------------
    # Blunt verdict
    # -----------------------------------------------------------------
    if total_real == 0:
        verdict = (
            "NULL RESULT (same conclusion as the Polymarket OOS test). Across "
            f"{total_polls_done} polls of Kalshi's live order book "
            f"(~{poll_records[-1]['n_events'] if poll_records else 0} open events / "
            f"~{poll_records[-1]['n_markets'] if poll_records else 0} open markets per poll), "
            f"{total_flagged} candidate structural violations were flagged at top-of-book across "
            "all three structures (ladder monotonicity, complement sum, event-sum completeness), "
            "but ZERO survived the anti-stale-quote gauntlet (persistence across "
            f">={threshold_polls} polls AND live /orderbook depth re-confirmation AND net-of-fee "
            "positivity every time observed). Every flagged crossing was a single-snapshot, "
            "thin/zero-depth, or fee-eaten artifact -- i.e. a stale or phantom quote, not a real "
            "tradeable edge. There is NO real, fee-surviving, deployable structural no-arb edge "
            "on Kalshi at the scale and depth thresholds tested here."
        )
    else:
        verdict = (
            f"PARTIAL POSITIVE: {total_real} of {total_flagged} flagged violation-keys "
            f"({100*total_real/total_flagged:.1f}%) survived persistence + live depth "
            "re-confirmation + net-of-fee positivity across the polling window. See "
            "real_violations_detail for the exact tickers/prices/depth. Capacity and "
            "frequency were small (see totals) -- treat as a real but likely low-capacity "
            "edge, not a scalable strategy, until confirmed with a longer live-fire test."
        )
    summary["verdict"] = verdict

    with open(f"{out_prefix}_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    write_report(summary, f"{out_prefix}_report.md")

    print("\n" + "=" * 78)
    print(verdict)
    print("=" * 78)


def write_report(summary: dict, path: str) -> None:
    meta = summary["run_metadata"]
    tot = summary["totals"]
    ss = summary["structure_summary"]
    polls = summary["universe"]["poll_records"]

    lines = []
    lines.append("# Kalshi Intra-Venue Structural / Logical-Consistency No-Arb -- OOS Test\n")
    lines.append(f"Run window: {meta['started_utc']} -> {meta['finished_utc']}  ")
    lines.append(f"Polls completed: {meta['polls_completed']} / {meta['polls_requested']} "
                 f"(spaced {meta['interval_seconds']}s apart)  ")
    lines.append(f"Persistence bar: a violation must be seen, orderbook-depth-confirmed, and "
                 f"net-fee-positive in >= {meta['persistence_threshold_polls']} of "
                 f"{meta['polls_completed']} polls to count as REAL.  ")
    lines.append(f"Min executable depth: {meta['min_depth_contracts']} contracts/leg. "
                 f"Min net edge to flag: ${meta['min_edge_dollars']:.2f}.  ")
    lines.append(f"Fee model: `{meta['fee_model']}`\n")

    lines.append("## Universe scanned per poll\n")
    lines.append("| poll | events | markets | MECE events | fetch(s) | S1 cand | S2 cand | S3 cand |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for p in polls:
        lines.append(f"| {p['poll_idx']} | {p['n_events']} | {p['n_markets']} | {p['n_mece_events']} | "
                     f"{p['fetch_seconds']} | {p['n_candidates_S1']} | {p['n_candidates_S2']} | {p['n_candidates_S3']} |")
    lines.append("")

    lines.append("## Per-structure results\n")
    lines.append("| Structure | Flagged (candidate) | REAL (persistent+executable+exact) | "
                 "Stale/unconfirmed | Mean net edge (c/$, confirmed) | Max net edge (c/$) | Mean confirmed depth (contracts) |")
    lines.append("|---|---|---|---|---|---|---|")
    name_map = {"S1_LADDER": "S1 Ladder monotonicity", "S2_COMPLEMENT": "S2 Complement sum",
                "S3_EVENTSUM": "S3 Event-sum completeness"}
    for k, label in name_map.items():
        s = ss.get(k, {})
        lines.append(f"| {label} | {s.get('flagged',0)} | {s.get('real',0)} | "
                     f"{s.get('stale_or_unconfirmed',0)} | {s.get('mean_net_edge_cents_per_dollar',0)} | "
                     f"{s.get('max_net_edge_cents_per_dollar',0)} | {s.get('mean_depth_contracts',0)} |")
    lines.append("")

    lines.append("## Totals\n")
    lines.append(f"- Total distinct violation-keys flagged (any poll, any structure): "
                 f"**{tot['total_flagged_violation_keys']}**")
    lines.append(f"- Total REAL (persistent + orderbook-confirmed + net-fee-positive every time seen): "
                 f"**{tot['total_real_persistent_executable_violation_keys']}**")
    lines.append(f"- Stale/phantom ratio: **{tot['stale_or_phantom_ratio']}** "
                 f"(fraction of flagged candidates that did NOT survive the discipline)")
    lines.append(f"- Frequency (flagged, extrapolated to /week from this run's wall-clock window): "
                 f"{tot['frequency_per_week_flagged']}")
    lines.append(f"- Frequency (REAL, extrapolated to /week from this run's wall-clock window): "
                 f"{tot['frequency_per_week_real']}\n")

    lines.append("## PAVA ladder-monotonicity diagnostics (last poll, top 25 by violation mass)\n")
    diag = summary.get("pava_ladder_diagnostics_last_poll", [])
    if diag:
        lines.append("| event | strike_type | n points | isotonic violation mass ($) |")
        lines.append("|---|---|---|---|")
        for d in diag:
            lines.append(f"| {d['event_ticker']} | {d['strike_type']} | {d['n_points']} | {d['violation_mass']} |")
    else:
        lines.append("_No isotonic-regression violation mass detected in the ladders scanned on the final poll._")
    lines.append("")

    lines.append("## REAL violations (survived full discipline) -- detail\n")
    rv = summary.get("real_violations_detail", [])
    if not rv:
        lines.append("_None. Every candidate flagged at top-of-book failed persistence, live "
                     "orderbook-depth re-confirmation, or net-of-fee positivity on at least one "
                     "re-check -- i.e. every flagged crossing was a stale or phantom quote._\n")
    else:
        for d in rv:
            lines.append(f"### `{d['key']}`")
            lines.append(f"- Structure: {d['structure']}, event `{d['event_ticker']}`, "
                         f"series `{d['series_ticker']}`")
            lines.append(f"- {d['description']}")
            lines.append(f"- Seen in {d['n_polls_seen']} polls, executable-confirmed in "
                         f"{d['n_polls_confirmed_executable']}")
            lines.append(f"- Mean net edge: {d['mean_net_edge_cents']} c/$; min confirmed depth: "
                         f"{d['min_confirmed_depth_contracts']} contracts")
            lines.append("")

    lines.append("## Method notes / anti-stale-quote discipline actually applied\n")
    lines.append("1. **NET of fees**: Kalshi's quadratic per-contract fee "
                 "(`ceil(fee_multiplier*0.07*C*P*(1-P)*100)/100` dollars, looked up per-series via "
                 "`/series/{ticker}`) is charged on *every leg*, *both directions*, at *taker* "
                 "assumptions (crossing the resting book), which is the conservative assumption "
                 "required to prove a violation is truly executable rather than a maker-only "
                 "quote that may never fill.")
    lines.append("2. **Executable depth, both legs**: every candidate's price is required to have "
                 f">= {meta['min_depth_contracts']} contracts resting at that exact price in the "
                 "top-of-book size field *and* is re-verified against a live `/orderbook` fetch "
                 "(full depth ladder, not the summary market object) before being counted.")
    lines.append("3. **Persistence**: the live book was polled repeatedly, "
                 f"{meta['interval_seconds']}s apart, over {meta['polls_completed']} polls. A "
                 "violation-key had to reappear, re-confirm executable, and stay net-fee-positive "
                 f"in >= {meta['persistence_threshold_polls']} separate polls to be counted REAL. "
                 "Anything seen once and gone (or once and un-confirmable) on the next poll is "
                 "counted as stale/phantom -- this is exactly the failure mode that made the "
                 "Polymarket logical-arb candidate NULL.")
    lines.append("4. **Exact nesting/exclusivity**: legs are only ever paired within the SAME "
                 "Kalshi `event_ticker` (guaranteeing identical settlement source, dates, and "
                 "rules). Ladders (S1) use Kalshi's own `strike_type`/`floor_strike` fields on "
                 "events flagged `mutually_exclusive=false`; event-sum sets (S3) use events "
                 "Kalshi itself flags `mutually_exclusive=true`. No cross-event or cross-series "
                 "pairing is ever attempted, so there is no false-pair risk.")
    lines.append("5. **S3 is executed buy-only** (buy every YES ask, or buy every NO ask) so no "
                 "short-selling / margin assumption is smuggled into 'executable'.\n")

    lines.append("## Verdict\n")
    lines.append(summary["verdict"])
    lines.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--polls", type=int, default=6, help="number of polls for the persistence check")
    ap.add_argument("--interval", type=float, default=120.0, help="seconds between polls")
    ap.add_argument("--out-prefix", type=str, default="kalshi_structural_arb")
    args = ap.parse_args()
    run(args.polls, args.interval, args.out_prefix)
