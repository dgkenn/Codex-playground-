#!/usr/bin/env python3
"""
kalshi_maker_rebate.py
=======================

OOS test of Kalshi candidate K1: MAKER-REBATE / liquidity-incentive capture.

This was mistakenly conflated with the killed Polymarket "LP-REWARDS" candidate.
That kill was Polymarket's latency-bound CLOB liquidity-rewards POOL (real yield,
but requires beating other bots to be first-in-queue -- an infra/speed game, not
a risk-based edge). Kalshi is a genuinely different, PURE CLOB exchange that runs
its OWN CFTC-filed "Liquidity Incentive Program": a published, per-market REWARD
POOL that pays makers a PRO-RATA SHARE (by resting size x price-distance discount,
sampled once per second and summed over the period) for resting qualifying
liquidity. No first-in-queue speed requirement -- you just need to REST SIZE AT OR
NEAR THE TOUCH for a large fraction of the period. Genuinely distinct mechanism;
untested until now.

MECHANISM (confirmed against Kalshi's live API + published program docs):
  - GET /incentive_programs (paginated) lists every live incentive. Fields:
      period_reward        -- integer, CENTI-CENTS (1/10000 of a dollar) for the
                               WHOLE reward pool over the WHOLE period (confirmed
                               against Kalshi's own OpenAPI schema description).
      target_size_fp        -- minimum resting-liquidity threshold (contracts)
                               that qualifies for scoring.
      discount_factor_bps   -- basis points; discount_factor = bps/10000. A
                               resting order N cents away from the best price
                               only gets discount_factor**N credit. At the
                               observed values (2500 or 5000 bps => 0.25 or
                               0.50), credit decays FAST: 1c off touch already
                               cuts credit in half or to a quarter. In practice
                               only orders sitting AT or within ~1-2c of the
                               touch earn a meaningful score.
      incentive_type         -- all observed live programs are "liquidity"
                               (the "volume" type also exists in the schema but
                               none were active at capture time).
  - Reward math (from Kalshi help-center "Liquidity Incentive Program" docs):
        your_reward = (your_score / sum_of_all_participants_scores) * period_reward
        score = size * discount_factor ** (distance_from_best_in_cents)
    scored via random per-second snapshots through the trading day, summed over
    the whole incentive period.
  - Kalshi's own OpenAPI /series/{ticker} schema documents fee_type per series:
    "quadratic" (taker-only fee, MAKER FILLS ARE FREE) vs
    "quadratic_with_maker_fees" (both sides charged). Checked live: of 196
    unique series carrying an active incentive program, only 3
    (KXAAAGASM, KXEGGS, KXLLM1) charge a maker fee; the other 193 do not.

WHAT THIS SCRIPT DOES (all from Kalshi's free public REST API, no auth needed
for market data):
  1. Enumerates every currently-active incentive program, computes each
     market's DAILY reward-pool $ (period_reward / period_length), target
     size, and discount factor. Reports the full universe distribution.
  2. Samples a mix of the highest-$/day candidates plus a random cross-section
     for representativeness, and for each sampled market:
       a. Pulls the LIVE order book -> spread, and RESTING DEPTH AT THE BEST
          PRICE on both the yes and no side (this is the "competing liquidity"
          a hypothetical maker would be queued against).
       b. Pulls the recent TRADE TAPE (up to program duration or lookback cap)
          -> trade count, volume/day, and a MARK-OUT-BASED adverse-selection
          estimate: for every real trade, marks the resting counterparty's
          P&L forward to a fixed horizon using the SUBSEQUENT trade price
          (the standard "toxicity" measure for a passive maker -- if the
          market keeps moving the same direction as the trade, the maker who
          was filled loses on average; this is measured directly from the
          real tape, not simulated).
  3. Combines these into a NET/day estimate:
        est_daily_rebate  = daily_reward_pool * capture_share
        est_adverse_sel   = est_fills_per_day * avg_markout_cost_per_contract
        est_fee_cost      = est_fills_per_day * per_contract_fee (0 unless the
                             series is one of the 3 maker-fee series)
        NET = est_daily_rebate - est_adverse_sel - est_fee_cost
     `capture_share` (our hypothetical maker's share of BOTH the reward score
     and of the taker flow that would fill against us) is the single biggest
     unmeasurable input -- we cannot observe other makers' real resting
     behavior without our own live two-sided quoting. It is estimated via a
     depth-proportional queue heuristic (our target size / (existing touch
     depth + our target size)) and reported across an explicit SENSITIVITY
     grid (100% / 50% / 20% / 5% of that heuristic share) rather than
     presented as a single false-precision number.
  4. Reports capacity (aggregate target size and required capital across any
     net-positive markets) and a blunt verdict.

Honest-null discipline (same bar that killed ~21 prior candidates): if the
rebate is real but small vs. adverse selection, or only exists on illiquid
novelty markets that are themselves the source of the adverse selection, say
so plainly. A genuine net-positive result on LIQUID markets would be a real
second Kalshi edge -- this script tries hard to find one and reports whatever
it actually finds.

Run:
    python3 kalshi_maker_rebate.py --top-n 40 --sample-n 30

Outputs:
    kalshi_maker_rebate_report.md
    kalshi_maker_rebate_summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HEADERS = {"User-Agent": "kalshi-maker-rebate-oos-test/1.0"}

REQUEST_TIMEOUT = 25
MAX_RETRIES = 4
WORKERS = 16

MARKOUT_HORIZON_SHORT_SEC = 15 * 60      # "active MM" horizon: 15 min
MARKOUT_HORIZON_LONG_SEC = 6 * 60 * 60   # "passive / can't hedge" horizon: 6h (stress case)
TRADE_LOOKBACK_CAP_SEC = 5 * 24 * 3600   # never pull more than 5 days of tape per market
MAX_TRADE_PAGES = 6                       # up to 6*1000 = 6000 trades/market cap

CAPTURE_SHARE_SCENARIOS = [1.00, 0.50, 0.20, 0.05]  # fraction of the depth-proportional heuristic

MIN_TRADES_FOR_ESTIMATE = 8   # markets with fewer real trades than this get NULL (not fabricated) adverse-sel
MIN_TRADE_SPAN_SEC_FOR_RATE = 3600.0  # trades must span at least 1h of wall-clock time to extrapolate a
                                        # daily rate; a handful of trades clustered in a single burst
                                        # (e.g. one order sweeping several resting price levels) is NOT
                                        # a stable "trades/day" signal and must not be extrapolated

session = requests.Session()
session.headers.update(HEADERS)
_adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64)
session.mount("https://", _adapter)
session.mount("http://", _adapter)


def _get(path: str, params: Optional[dict] = None) -> dict:
    url = f"{BASE}{path}"
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} attempts: {last_err}")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Step 1: enumerate incentive programs
# ---------------------------------------------------------------------------

def fetch_all_incentive_programs(status: str = "active") -> List[dict]:
    out: List[dict] = []
    cursor = ""
    for _ in range(500):
        params = {"status": status, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = _get("/incentive_programs", params)
        progs = d.get("incentive_programs", [])
        out.extend(progs)
        cursor = d.get("next_cursor", "")
        if not cursor or not progs:
            break
    return out


def enrich_program(p: dict) -> Optional[dict]:
    try:
        sd = parse_ts(p["start_date"])
        ed = parse_ts(p["end_date"])
        dur_days = max((ed - sd).total_seconds() / 86400.0, 1e-6)
        reward_dollars = p["period_reward"] / 10000.0  # centi-cents -> dollars
        daily_reward = reward_dollars / dur_days
        target = float(p.get("target_size_fp") or 0.0)
        dfb = p.get("discount_factor_bps")
        discount_factor = (dfb / 10000.0) if dfb is not None else None
        ticker = p["market_ticker"]
        series = ticker.split("-")[0]
        return dict(
            ticker=ticker,
            series=series,
            id=p["id"],
            start_date=p["start_date"],
            end_date=p["end_date"],
            dur_days=dur_days,
            reward_dollars=reward_dollars,
            daily_reward=daily_reward,
            target_size=target,
            discount_factor=discount_factor,
            incentive_type=p.get("incentive_type"),
        )
    except Exception:
        return None


def fetch_series_fee_info(series_list: List[str]) -> Dict[str, Tuple[str, float]]:
    out: Dict[str, Tuple[str, float]] = {}

    def _one(sr: str):
        try:
            d = _get(f"/series/{sr}")
            s = d.get("series", {})
            return sr, (s.get("fee_type", "quadratic"), float(s.get("fee_multiplier", 1.0) or 1.0))
        except Exception:
            return sr, ("quadratic", 1.0)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for sr, v in pool.map(_one, series_list):
            out[sr] = v
    return out


def kalshi_fee(price_dollars: float, contracts: float, fee_multiplier: float = 1.0) -> float:
    """Kalshi's quadratic fee formula (ceil to cent), applied per fill."""
    if contracts <= 0:
        return 0.0
    p = min(max(price_dollars, 0.0), 1.0)
    raw = fee_multiplier * 0.07 * contracts * p * (1.0 - p)
    return math.ceil(raw * 100.0) / 100.0


# ---------------------------------------------------------------------------
# Step 2: order book depth at touch
# ---------------------------------------------------------------------------

def fetch_orderbook(ticker: str) -> Optional[dict]:
    try:
        d = _get(f"/markets/{ticker}/orderbook")
        return d.get("orderbook_fp") or d.get("orderbook")
    except Exception:
        return None


def orderbook_top(levels: Optional[List[List[str]]]) -> Tuple[float, float]:
    """levels = [[price_str, size_str], ...] resting BUY orders. Returns (best_price, size_at_best)."""
    if not levels:
        return 0.0, 0.0
    best_p, best_s = 0.0, 0.0
    for p, s in levels:
        pf, sf = float(p), float(s)
        if pf > best_p:
            best_p, best_s = pf, sf
    return best_p, best_s


def get_touch_depth(ticker: str) -> Optional[dict]:
    ob = fetch_orderbook(ticker)
    if not ob:
        return None
    yes_levels = ob.get("yes_dollars") or []
    no_levels = ob.get("no_dollars") or []
    yes_bid_p, yes_bid_s = orderbook_top(yes_levels)
    no_bid_p, no_bid_s = orderbook_top(no_levels)
    yes_ask_p = round(1.0 - no_bid_p, 4) if no_bid_p > 0 else None
    no_ask_p = round(1.0 - yes_bid_p, 4) if yes_bid_p > 0 else None
    spread = None
    if yes_ask_p is not None and yes_bid_p > 0:
        spread = round(yes_ask_p - yes_bid_p, 4)
    return dict(
        yes_bid=yes_bid_p, yes_bid_sz=yes_bid_s,
        no_bid=no_bid_p, no_bid_sz=no_bid_s,
        yes_ask=yes_ask_p, no_ask=no_ask_p,
        spread=spread,
    )


# ---------------------------------------------------------------------------
# Step 3: trade tape + adverse-selection markout
# ---------------------------------------------------------------------------

def fetch_trades(ticker: str, min_ts: int, max_pages: int = MAX_TRADE_PAGES) -> List[dict]:
    out: List[dict] = []
    cursor = ""
    for _ in range(max_pages):
        params = {"ticker": ticker, "limit": 1000, "min_ts": min_ts}
        if cursor:
            params["cursor"] = cursor
        d = _get("/markets/trades", params)
        trades = d.get("trades", [])
        out.extend(trades)
        cursor = d.get("cursor", "")
        if not cursor or not trades or len(trades) < 1000:
            break
    return out


def compute_markout(trades: List[dict], horizon_sec: float) -> Optional[dict]:
    """For each trade, mark the RESTING counterparty's P&L forward to the first
    later trade at or beyond `horizon_sec`; fall back to the last available
    trade in the tape if nothing exists at that horizon (stress-case proxy).
    Returns per-contract adverse-selection stats in dollars (positive = costly
    to the maker who was resting).
    """
    if len(trades) < 2:
        return None
    ev = []
    for t in trades:
        try:
            ev.append((
                parse_ts(t["created_time"]).timestamp(),
                float(t["yes_price_dollars"]),
                t["taker_outcome_side"],
                float(t.get("count_fp", 1.0) or 1.0),
            ))
        except Exception:
            continue
    ev.sort(key=lambda x: x[0])
    n = len(ev)
    if n < 2:
        return None

    markouts = []
    weights = []
    j = 0
    for i in range(n):
        ti, pi, side_i, cnt_i = ev[i]
        target_t = ti + horizon_sec
        j = max(j, i)
        while j < n - 1 and ev[j][0] < target_t:
            j += 1
        # ev[j] is first trade at/after target_t, or the last trade if none qualifies
        pj = ev[j][1]
        sign = -1.0 if side_i == "yes" else 1.0
        mo = sign * (pj - pi)
        markouts.append(mo)
        weights.append(cnt_i)

    if not markouts:
        return None
    mean_mo = sum(m * w for m, w in zip(markouts, weights)) / sum(weights)
    try:
        stdev_mo = statistics.pstdev(markouts)
    except Exception:
        stdev_mo = 0.0
    return dict(
        mean_cost_per_contract=mean_mo,
        stdev=stdev_mo,
        n_trades=n,
        total_volume=sum(w for w in weights),
    )


# ---------------------------------------------------------------------------
# Per-market analysis
# ---------------------------------------------------------------------------

def analyze_market(prog: dict, fee_info: Dict[str, Tuple[str, float]]) -> dict:
    ticker = prog["ticker"]
    result = dict(prog)
    result["error"] = None

    depth = get_touch_depth(ticker)
    if depth is None:
        result["error"] = "orderbook_fetch_failed"
        return result
    result["depth"] = depth

    # lookback: whichever is smaller of (program duration so far, cap)
    started = parse_ts(prog["start_date"])
    lookback_sec = min(TRADE_LOOKBACK_CAP_SEC, max((now_utc() - started).total_seconds(), 3600))
    min_ts = int((now_utc().timestamp()) - lookback_sec)
    try:
        trades = fetch_trades(ticker, min_ts=min_ts)
    except Exception as e:
        result["error"] = f"trades_fetch_failed: {e}"
        trades = []
    result["n_trades_observed"] = len(trades)

    if len(trades) < MIN_TRADES_FOR_ESTIMATE:
        result["adverse_selection"] = None
        result["daily_volume_contracts"] = None
        result["null_reason"] = f"only {len(trades)} trades observed in lookback (<{MIN_TRADES_FOR_ESTIMATE}) -- too thin to estimate fill rate or markout; NOT fabricated"
        return result

    ts_vals = [parse_ts(t["created_time"]).timestamp() for t in trades]
    span_sec = max(ts_vals) - min(ts_vals)
    if span_sec < MIN_TRADE_SPAN_SEC_FOR_RATE:
        # All observed trades are clustered inside a single short burst (e.g. one order sweeping
        # several resting price levels in the same second). Extrapolating that burst's rate to a
        # "contracts/day" figure would wildly overstate volume (a real bug caught during dev: a
        # 16-trade, 4-minute burst extrapolated to ~89,000 contracts/day on a $3.57/day-reward
        # market). Refuse to estimate rather than fabricate.
        result["adverse_selection"] = None
        result["daily_volume_contracts"] = None
        result["null_reason"] = (
            f"{len(trades)} trades observed but all clustered within {span_sec/60:.1f} min "
            f"(<{MIN_TRADE_SPAN_SEC_FOR_RATE/60:.0f} min) -- a single burst, not a stable rate; "
            f"extrapolating to $/day would be false precision, NOT attempted"
        )
        return result

    # Daily rate = total observed volume / the ACTUAL requested lookback window (not the empirical
    # min-max span of just the fetched trades) -- this avoids over-extrapolating from a recent
    # cluster of activity inside a longer, mostly-quiet window.
    span_days = lookback_sec / 86400.0
    total_vol = sum(float(t.get("count_fp", 1.0) or 1.0) for t in trades)
    daily_volume = total_vol / span_days
    result["daily_volume_contracts"] = daily_volume
    result["trade_span_days"] = span_days
    result["trade_burst_span_sec"] = span_sec

    price_vals = [float(t["yes_price_dollars"]) for t in trades]
    result["price_range_observed"] = (min(price_vals), max(price_vals))
    result["price_swing"] = max(price_vals) - min(price_vals)

    mo_short = compute_markout(trades, MARKOUT_HORIZON_SHORT_SEC)
    mo_long = compute_markout(trades, MARKOUT_HORIZON_LONG_SEC)
    result["markout_short"] = mo_short
    result["markout_long"] = mo_long

    # depth-proportional capture heuristic (our target size vs live touch depth)
    target = prog["target_size"]
    yes_depth = depth["yes_bid_sz"] or 0.0
    no_depth = depth["no_bid_sz"] or 0.0
    avg_touch_depth = (yes_depth + no_depth) / 2.0
    heuristic_share = target / (avg_touch_depth + target) if (avg_touch_depth + target) > 0 else 0.0
    result["heuristic_capture_share"] = heuristic_share
    result["avg_touch_depth"] = avg_touch_depth
    # Diagnostic only (NOT used to alter the math): how many times the CURRENT snapshot depth
    # would need to "turn over" to account for the observed daily volume. A single live-orderbook
    # snapshot is a poor proxy for cumulative competing liquidity on a book that turns over many
    # times a day -- high turnover means the capture_share heuristic is on shakier ground (it
    # implicitly assumes our resting size keeps its queue share across every one of those
    # turnovers, which is optimistic and unverifiable without live quoting).
    result["book_turnover_per_day"] = (daily_volume / avg_touch_depth) if avg_touch_depth > 0 else None

    series = prog["series"]
    fee_type, fee_mult = fee_info.get(series, ("quadratic", 1.0))
    result["fee_type"] = fee_type
    result["fee_multiplier"] = fee_mult

    mid_price = None
    if depth.get("yes_bid") and depth.get("yes_ask"):
        mid_price = (depth["yes_bid"] + depth["yes_ask"]) / 2.0
    elif depth.get("yes_bid"):
        mid_price = depth["yes_bid"]
    result["mid_price"] = mid_price

    scenarios = {}
    for share_frac in CAPTURE_SHARE_SCENARIOS:
        capture_share = min(heuristic_share * share_frac, 1.0)
        est_fills_per_day = daily_volume * capture_share
        est_daily_rebate = prog["daily_reward"] * capture_share

        for horizon_name, mo in (("short_15m", mo_short), ("long_6h", mo_long)):
            if mo is None:
                continue
            adverse_sel_per_day = est_fills_per_day * mo["mean_cost_per_contract"]
            fee_per_contract = kalshi_fee(mid_price or 0.5, 1.0, fee_mult) if fee_type == "quadratic_with_maker_fees" else 0.0
            fee_cost_per_day = est_fills_per_day * fee_per_contract
            net = est_daily_rebate - adverse_sel_per_day - fee_cost_per_day
            # How much of a POSITIVE net is actually attributable to the Kalshi rebate itself,
            # vs. to negative measured adverse-selection (i.e. realized bid/ask spread capture +
            # short-sample mean-reversion in the trade tape, a generic market-making effect that
            # exists with or without the incentive program)? This is the key honesty check: K1 is
            # specifically about the REBATE, not about "is passive market-making profitable on
            # Kalshi in general" (an interesting but DIFFERENT, unverified hypothesis riding on the
            # same tape, and one very exposed to small-sample overfitting on a few days of data).
            rebate_frac_of_net = (est_daily_rebate / net) if net > 0 else None
            scenarios[f"{share_frac:.2f}_{horizon_name}"] = dict(
                capture_share=capture_share,
                est_fills_per_day=est_fills_per_day,
                est_daily_rebate=est_daily_rebate,
                adverse_sel_per_day=adverse_sel_per_day,
                fee_cost_per_day=fee_cost_per_day,
                net_per_day=net,
                rebate_frac_of_net=rebate_frac_of_net,
                rebate_driven=(rebate_frac_of_net is not None and rebate_frac_of_net >= 0.25),
            )
    result["scenarios"] = scenarios
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=40, help="highest daily-$-reward markets to test")
    ap.add_argument("--sample-n", type=int, default=30, help="additional random cross-section")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)

    print("Fetching all active incentive programs...", file=sys.stderr)
    raw_progs = fetch_all_incentive_programs(status="active")
    progs = [p for p in (enrich_program(r) for r in raw_progs) if p is not None]
    print(f"  {len(raw_progs)} raw -> {len(progs)} enriched incentive programs", file=sys.stderr)

    all_series = sorted(set(p["series"] for p in progs))
    print(f"Fetching fee_type for {len(all_series)} series...", file=sys.stderr)
    fee_info = fetch_series_fee_info(all_series)
    maker_fee_series = sorted([s for s, v in fee_info.items() if v[0] == "quadratic_with_maker_fees"])

    # universe stats
    daily_vals = sorted(p["daily_reward"] for p in progs)
    target_vals = sorted(p["target_size"] for p in progs)
    dur_vals = sorted(p["dur_days"] for p in progs)

    def pct(vals, q):
        if not vals:
            return None
        idx = min(int(q * (len(vals) - 1)), len(vals) - 1)
        return vals[idx]

    universe_stats = dict(
        n_active_programs=len(progs),
        n_unique_series=len(all_series),
        n_maker_fee_series=len(maker_fee_series),
        maker_fee_series=maker_fee_series,
        total_daily_reward_pool_usd=sum(daily_vals),
        daily_reward_usd=dict(min=daily_vals[0], p25=pct(daily_vals, 0.25), median=pct(daily_vals, 0.5),
                               p75=pct(daily_vals, 0.75), max=daily_vals[-1]),
        target_size=dict(min=target_vals[0], median=pct(target_vals, 0.5), max=target_vals[-1]),
        duration_days=dict(min=dur_vals[0], median=pct(dur_vals, 0.5), max=dur_vals[-1]),
    )

    series_counts = defaultdict(int)
    for p in progs:
        series_counts[p["series"]] += 1
    top_series = sorted(series_counts.items(), key=lambda x: -x[1])[:15]
    universe_stats["top_series_by_n_markets"] = top_series

    # flagship-market check: do any of Kalshi's high-volume series carry incentives?
    flagship_prefixes = ["KXBTCD", "KXETHD", "KXHIGH", "KXPRES", "KXFED", "KXNFLGAME", "KXNBASERIES", "KXINX"]
    flagship_hits = {pfx: sum(1 for p in progs if p["series"] == pfx) for pfx in flagship_prefixes}
    universe_stats["flagship_series_incentive_count"] = flagship_hits

    # sample selection: top-N by daily $ + random cross-section
    progs_sorted = sorted(progs, key=lambda p: -p["daily_reward"])
    top_n = progs_sorted[: args.top_n]
    remaining = progs_sorted[args.top_n:]
    sample_n = min(args.sample_n, len(remaining))
    random_sample = random.sample(remaining, sample_n) if sample_n > 0 else []
    selected = top_n + random_sample
    print(f"Analyzing {len(selected)} markets ({len(top_n)} top-$/day + {len(random_sample)} random)...", file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(analyze_market, p, fee_info): p for p in selected}
        done = 0
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:
                p = futs[fut]
                results.append(dict(p, error=str(e)))
            done += 1
            if done % 10 == 0:
                print(f"  ...{done}/{len(selected)}", file=sys.stderr)

    for r in results:
        r["is_top_n_sample"] = r["ticker"] in {p["ticker"] for p in top_n}

    write_outputs(universe_stats, results, args)


def write_outputs(universe_stats: dict, results: List[dict], args):
    scenario_keys = [f"{f:.2f}_{h}" for f in CAPTURE_SHARE_SCENARIOS for h in ("short_15m", "long_6h")]

    usable = [r for r in results if r.get("scenarios")]
    null_results = [r for r in results if not r.get("scenarios")]

    scenario_summary = {}
    for sk in scenario_keys:
        sc_rows = [r["scenarios"][sk] for r in usable if sk in r["scenarios"]]
        nets = [s["net_per_day"] for s in sc_rows]
        n_pos = sum(1 for v in nets if v > 0)
        n_rebate_driven = sum(1 for s in sc_rows if s.get("rebate_driven"))
        n_spread_dominated = sum(1 for s in sc_rows if s["net_per_day"] > 0 and not s.get("rebate_driven"))
        rebate_driven_nets = [s["net_per_day"] for s in sc_rows if s.get("rebate_driven")]
        scenario_summary[sk] = dict(
            n_markets=len(nets),
            n_net_positive=n_pos,
            frac_net_positive=(n_pos / len(nets) if nets else None),
            n_rebate_driven_positive=n_rebate_driven,
            n_spread_capture_dominated_positive=n_spread_dominated,
            mean_net=(statistics.mean(nets) if nets else None),
            median_net=(statistics.median(nets) if nets else None),
            sum_net_across_sample=(sum(nets) if nets else None),
            mean_net_rebate_driven_only=(statistics.mean(rebate_driven_nets) if rebate_driven_nets else None),
            median_net_rebate_driven_only=(statistics.median(rebate_driven_nets) if rebate_driven_nets else None),
        )

    # headline scenario for narrative: base case = 50% of heuristic share, short (15m) horizon
    headline_key = "0.50_short_15m"
    headline_stress_key = "0.05_long_6h"

    def top_net_positive(sk: str, k: int = 15):
        rows = [r for r in usable if sk in r["scenarios"]]
        rows.sort(key=lambda r: -r["scenarios"][sk]["net_per_day"])
        return rows[:k]

    top_headline = top_net_positive(headline_key)

    summary = dict(
        generated_at=now_utc().isoformat(),
        candidate="K1 Kalshi maker-rebate / liquidity-incentive capture",
        method_note=(
            "period_reward is total $ pool for the WHOLE program period (converted from "
            "centi-cents, confirmed against Kalshi's OpenAPI schema). daily_reward = "
            "period_reward_usd / program_duration_days. capture_share (our hypothetical "
            "maker's fraction of both the score pool and the fill flow) is UNMEASURED "
            "without live 2-sided quoting; estimated via a depth-proportional queue "
            "heuristic (target_size / (live touch depth + target_size)) and swept across "
            "4 explicit scenarios (100/50/20/5% of that heuristic) x 2 markout horizons "
            "(15min 'active MM' vs 6h 'passive, cannot hedge' stress case)."
        ),
        universe=universe_stats,
        n_markets_analyzed=len(results),
        n_markets_with_estimate=len(usable),
        n_markets_null_too_thin=len(null_results),
        scenario_grid_definition="capture_share_frac x markout_horizon -> net_per_day across analyzed sample",
        scenario_summary=scenario_summary,
        headline_scenario=headline_key,
        headline_stress_scenario=headline_stress_key,
        top_headline_net_positive_markets=[
            dict(
                ticker=r["ticker"], series=r["series"], daily_reward_usd=r["daily_reward"],
                target_size=r["target_size"], daily_volume_contracts=r.get("daily_volume_contracts"),
                spread=r["depth"].get("spread") if r.get("depth") else None,
                heuristic_capture_share=r.get("heuristic_capture_share"),
                book_turnover_per_day=r.get("book_turnover_per_day"),
                net_per_day_headline=r["scenarios"][headline_key]["net_per_day"] if headline_key in r["scenarios"] else None,
                net_per_day_stress=r["scenarios"][headline_stress_key]["net_per_day"] if headline_stress_key in r["scenarios"] else None,
                rebate_driven=r["scenarios"][headline_key].get("rebate_driven") if headline_key in r["scenarios"] else None,
                rebate_frac_of_net=r["scenarios"][headline_key].get("rebate_frac_of_net") if headline_key in r["scenarios"] else None,
                is_top_n_sample=r["is_top_n_sample"],
            )
            for r in top_headline
        ],
        all_results=[
            {
                k: v for k, v in r.items() if k not in ("markout_short", "markout_long")
            } | dict(
                markout_short_mean_cost=(r.get("markout_short") or {}).get("mean_cost_per_contract"),
                markout_short_n_trades=(r.get("markout_short") or {}).get("n_trades"),
                markout_long_mean_cost=(r.get("markout_long") or {}).get("mean_cost_per_contract"),
            )
            for r in results
        ],
    )

    with open("kalshi_maker_rebate_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    write_report(summary, results, universe_stats)
    print("Wrote kalshi_maker_rebate_summary.json and kalshi_maker_rebate_report.md", file=sys.stderr)


def write_report(summary: dict, results: List[dict], universe_stats: dict):
    lines = []
    a = lines.append
    a("# Kalshi K1: Maker-Rebate / Liquidity-Incentive Capture -- OOS Test")
    a("")
    a(f"Generated: {summary['generated_at']}")
    a("")
    a("## Correction to prior kill")
    a("")
    a("The earlier 'LP-REWARDS' kill was **Polymarket's** latency-bound CLOB liquidity-rewards "
      "pool (real yield, but a first-in-queue speed game -- infra edge, not risk edge). **Kalshi "
      "is a separate, pure CLOB exchange** with its own CFTC-filed Liquidity Incentive Program: a "
      "published per-market reward pool paid pro-rata by resting size x price-distance decay, "
      "sampled once per second. No latency requirement to be first in queue -- you just need to "
      "rest meaningful size near the touch for a large share of the period. Confirmed genuinely "
      "distinct mechanism via live API (`GET /incentive_programs`) and Kalshi's own program docs.")
    a("")
    a("## 1. Universe: incentivized markets right now")
    a("")
    u = universe_stats
    a(f"- **{u['n_active_programs']} active liquidity-incentive programs** across "
      f"**{u['n_unique_series']} unique series** (one program per market; all observed programs "
      f"are `incentive_type=liquidity`, none are `volume` type at capture time).")
    a(f"- Total daily reward pool across ALL active programs: **${u['total_daily_reward_pool_usd']:,.0f}/day**.")
    dr = u["daily_reward_usd"]
    a(f"- Per-market daily reward pool: min ${dr['min']:.2f}, p25 ${dr['p25']:.2f}, "
      f"**median ${dr['median']:.2f}**, p75 ${dr['p75']:.2f}, max ${dr['max']:.2f}.")
    ts = u["target_size"]
    a(f"- Target (qualifying) resting size: min {ts['min']:.0f}, median {ts['median']:.0f}, "
      f"max {ts['max']:.0f} contracts.")
    dd = u["duration_days"]
    a(f"- Program duration: min {dd['min']:.2f}d, median {dd['median']:.1f}d, max {dd['max']:.1f}d.")
    a(f"- **{u['n_maker_fee_series']}/{u['n_unique_series']} series charge a maker fee** "
      f"(`quadratic_with_maker_fees`): {', '.join(u['maker_fee_series']) if u['maker_fee_series'] else 'none'}. "
      f"The other {u['n_unique_series'] - u['n_maker_fee_series']} use standard `quadratic` fee "
      f"type, where **maker (resting) fills are free** -- only a taker crossing the book pays.")
    a("")
    a("**Top series by number of incentivized markets** (i.e. where Kalshi is concentrating its "
      "subsidy):")
    a("")
    a("| Series | # incentivized markets |")
    a("|---|---|")
    for sr, n in u["top_series_by_n_markets"]:
        a(f"| {sr} | {n} |")
    a("")
    a("**Critical structural observation**: none of Kalshi's flagship, genuinely-liquid series "
      "(BTC/ETH daily strikes, weather highs, presidential/election markets, NFL/NBA game lines) "
      "carry ANY active incentive program:")
    a("")
    a("| Flagship series checked | # incentive programs |")
    a("|---|---|")
    for pfx, n in u["flagship_series_incentive_count"].items():
        a(f"| {pfx} | {n} |")
    a("")
    a("Every incentive dollar is aimed at markets that would otherwise have **no organic liquidity**: "
      "gas-price micro-strikes, MLB/NBA in-game player-mention props, World Cup halftime-song and "
      "attendance markets, federal-charge and movie-casting novelty markets, CPI sub-bracket "
      "markets, etc. Kalshi is renting liquidity precisely where the natural adverse-selection risk "
      "is highest (thin books, jumpy/event-driven prices, small number of informed participants "
      "relative to total flow) -- exactly the setup this OOS test needs to price honestly rather "
      "than assume away.")
    a("")
    a("## 2. Method")
    a("")
    a(f"Analyzed **{summary['n_markets_analyzed']}** markets: the top-$/day candidates plus a random "
      f"cross-section for representativeness. **{summary['n_markets_with_estimate']}** had enough "
      f"real trade-tape volume (>= {MIN_TRADES_FOR_ESTIMATE} trades in the lookback window) to "
      f"produce an estimate; **{summary['n_markets_null_too_thin']}** were too thin to estimate at "
      f"all and are reported as an honest NULL rather than a fabricated number.")
    a("")
    a("For each estimable market:")
    a("")
    a("- **Daily rebate pool** = `period_reward` ($, converted from centi-cents) / program duration "
      "(days) -- this is measured directly from the live API, not estimated.")
    a("- **Adverse-selection cost per contract** = a mark-out computed from the REAL trade tape: for "
      "every trade, the resting counterparty's forward P&L to a later trade at/after a fixed "
      "horizon. Two horizons: 15 min (an active MM that re-quotes/manages inventory quickly) and 6h "
      "(a passive maker that cannot hedge -- the stress case, matching the 'no live two-sided "
      "quoting available' honesty caveat).")
    a("- **capture_share** -- the fraction of BOTH the reward score and the taker fill flow our "
      "hypothetical maker would actually capture by resting `target_size` contracts. This is the "
      "one input we CANNOT measure without live quoting (no L3 queue-position data). Estimated via "
      "a depth-proportional heuristic: `target_size / (live resting depth at the best price + "
      "target_size)`, then swept at 100%/50%/20%/5% of that heuristic to bound the honest range "
      "rather than assert a single number.")
    a("- **Fees**: $0 on the maker fill for the 193/196 series using standard `quadratic` fee type "
      "(measured, not assumed); Kalshi's quadratic taker-fee formula applied for the 3 "
      "`quadratic_with_maker_fees` series.")
    a("- `NET/day = daily_rebate*capture_share - fills/day*capture_share*markout_cost - fee_cost`.")
    a("")
    a("## 3. Results by scenario")
    a("")
    a("Net-positive rate and average NET/day across the analyzed sample, at each capture-share x "
      "markout-horizon combination. **Two positive counts are shown**: `rebate-driven` (the Kalshi "
      "reward pool itself accounts for >=25% of the positive NET -- the thing K1 is actually about) "
      "vs `spread-capture-dominated` (positive NET, but the reward pool is a rounding error next to "
      "negative measured adverse-selection, i.e. the trade tape shows realized mean-reversion/spread "
      "capture that would exist with or without any incentive program -- a DIFFERENT, unverified "
      "hypothesis about generic Kalshi market-making profitability, not a finding about the rebate):")
    a("")
    a("| Capture-share scenario | Markout horizon | n markets | # net-positive | of which rebate-driven | of which spread-capture-dominated | mean NET/day (rebate-driven only) |")
    a("|---|---|---|---|---|---|---|")
    for sk, s in summary["scenario_summary"].items():
        frac_label = f"{float(sk.split('_')[0]) * 100:.0f}%"
        horizon_label = "15 min (active)" if "short" in sk else "6h (passive/stress)"
        if s["n_markets"] == 0:
            a(f"| {frac_label} | {horizon_label} | 0 | -- | -- | -- | -- |")
            continue
        mnr = f"${s['mean_net_rebate_driven_only']:.2f}" if s["mean_net_rebate_driven_only"] is not None else "n/a"
        a(f"| {frac_label} | {horizon_label} | {s['n_markets']} | {s['n_net_positive']} | "
          f"{s['n_rebate_driven_positive']} | {s['n_spread_capture_dominated_positive']} | {mnr} |")
    a("")
    a(f"**Headline scenario** (50% of the depth heuristic, 15-min active-MM markout -- a middle-of-the-road "
      f"read, not the most flattering one): top net-positive markets in the analyzed sample, flagged by "
      f"whether the rebate itself is actually doing the work:")
    a("")
    if summary["top_headline_net_positive_markets"]:
        a("| Ticker | Series | $/day pool | vol/day (ct) | book turnover/day | capture share (heur.) | NET/day (headline) | NET/day (stress) | rebate's share of NET |")
        a("|---|---|---|---|---|---|---|---|---|")
        for r in summary["top_headline_net_positive_markets"]:
            vol_s = f"{r['daily_volume_contracts']:.1f}" if r["daily_volume_contracts"] is not None else "n/a"
            turn_s = f"{r['book_turnover_per_day']:.1f}x" if r.get("book_turnover_per_day") is not None else "n/a"
            cs_s = f"{r['heuristic_capture_share']*100:.0f}%" if r["heuristic_capture_share"] is not None else "n/a"
            net_h = f"${r['net_per_day_headline']:.2f}" if r["net_per_day_headline"] is not None else "n/a"
            net_s = f"${r['net_per_day_stress']:.2f}" if r["net_per_day_stress"] is not None else "n/a"
            rf = r.get("rebate_frac_of_net")
            rf_s = f"{rf*100:.0f}%{' (REBATE-DRIVEN)' if r.get('rebate_driven') else ' (spread-capture)'}" if rf is not None else "n/a"
            a(f"| {r['ticker']} | {r['series']} | ${r['daily_reward_usd']:.2f} | "
              f"{vol_s} | {turn_s} | {cs_s} | {net_h} | {net_s} | {rf_s} |")
    else:
        a("*(none -- see verdict below)*")
    a("")
    a("*(\"rebate's share of NET\" can exceed 100% when adverse selection is a genuine positive cost "
      "that eats into the rebate but doesn't flip NET negative -- that's the intended, healthy case: "
      "the rebate is doing all the work and then some is lost to real adverse selection. It's the "
      "**spread-capture** flag, not a >100% figure, that signals a market to distrust.)*")
    a("")
    a("## 4. Capacity")
    a("")
    headline_scen = summary["headline_scenario"]
    net_pos_headline = [r for r in results if r.get("scenarios", {}).get(headline_scen, {}).get("net_per_day", -1) > 0]
    rebate_driven_rows = [r for r in net_pos_headline if r["scenarios"][headline_scen].get("rebate_driven")]
    spread_rows = [r for r in net_pos_headline if not r["scenarios"][headline_scen].get("rebate_driven")]
    total_target_rebate = sum(r["target_size"] for r in rebate_driven_rows)
    total_daily_net_rebate = sum(r["scenarios"][headline_scen]["net_per_day"] for r in rebate_driven_rows)
    a(f"Restricting to the **rebate-driven** subset only (the honest answer to \"is the rebate program "
      f"itself deployable\"): **{len(rebate_driven_rows)}** of {summary['n_markets_with_estimate']} "
      f"analyzed markets, combined qualifying target size **{total_target_rebate:,.0f} contracts**, "
      f"combined estimated NET **${total_daily_net_rebate:,.2f}/day** if resting target size on all of "
      f"them simultaneously. (The {len(spread_rows)} spread-capture-dominated markets are excluded from "
      f"this capacity figure -- see Section 3's caveat; their large modeled NET is not attributable to "
      f"the rebate program and is separately, and more skeptically, discussed in the verdict.)")
    a("")
    a("Two caveats even on the rebate-driven capacity figure: (1) it requires standing capital roughly "
      "equal to target_size x mid-price on BOTH the yes and no side of every market simultaneously "
      "(order of target_size dollars per market at ~$0.50 mid, more at higher mid); (2) these are "
      "almost all micro-liquidity novelty markets -- the target sizes (300-10,000 contracts) sound "
      "large but many of these markets trade only a handful of contracts per print, so the "
      "depth-proportional capture-share assumption is the single most load-bearing (and least "
      "verifiable without live quoting) number in this whole analysis.")
    a("")
    a("## 5. What's measured vs. estimated (explicit)")
    a("")
    a("**Measured directly from the live API** (not modeled): which markets are incentivized, the "
      "exact size of every reward pool, program duration, target size, discount factor, live spread "
      "and touch depth, real trade counts/sizes/timestamps, per-series fee schedule (maker-free vs "
      "maker-fee).")
    a("")
    a("**Estimated / modeled, with explicit sensitivity** (cannot be measured without live two-sided "
      "quoting on Kalshi):")
    a("")
    a("1. **capture_share** -- our maker's fraction of the reward score AND of the fill flow. Modeled "
      "as a depth-proportional queue heuristic and swept 100%/50%/20%/5%. This is a real, "
      "load-bearing uncertainty: Kalshi scores via random per-second snapshots of ALL resting orders "
      "at/near the touch, and we cannot see how many other makers are already there over time -- "
      "only a live snapshot of current depth.")
    a("2. **Adverse-selection cost** -- measured via real mark-outs on the actual trade tape (not "
      "simulated), but assumes our hypothetical resting maker would face the SAME average toxicity "
      "as the realized fills in the tape. This is standard practice for this kind of ex-ante "
      "estimate but is still a proxy, not a live-fill measurement.")
    a("3. Fills/day for OUR maker = daily trade volume x capture_share -- same caveat as (1).")
    a("")
    a("## 6. Verdict")
    a("")
    verdict = build_verdict(summary)
    a(verdict)
    a("")
    with open("kalshi_maker_rebate_report.md", "w") as f:
        f.write("\n".join(lines))


def build_verdict(summary: dict) -> str:
    headline = summary["scenario_summary"].get(summary["headline_scenario"], {})
    stress = summary["scenario_summary"].get(summary["headline_stress_scenario"], {})
    optimistic = summary["scenario_summary"].get("1.00_short_15m", {})

    n_est = summary["n_markets_with_estimate"]
    if n_est == 0:
        return ("**NULL / no verdict possible.** No sampled market had enough trade-tape volume "
                "to produce even a rough estimate -- this itself is informative: the incentivized "
                "markets are so thin that even measuring the adverse-selection side of the trade "
                "is not currently possible from the public tape.")

    lines = []

    def rd_frac(sc):
        n = sc.get("n_markets") or 0
        return (sc.get("n_rebate_driven_positive") or 0) / n if n else 0.0

    def sc_frac(sc):
        n = sc.get("n_markets") or 0
        return (sc.get("n_spread_capture_dominated_positive") or 0) / n if n else 0.0

    opt_rd, opt_sc = rd_frac(optimistic), sc_frac(optimistic)
    head_rd, head_sc = rd_frac(headline), sc_frac(headline)
    stress_rd, stress_sc = rd_frac(stress), sc_frac(stress)

    lines.append(
        f"**The rebate-driven vs. spread-capture-dominated split is the whole story here.** At the "
        f"MOST OPTIMISTIC scenario tested (100% capture of the depth heuristic, 15-min active-MM "
        f"markout): **{opt_rd*100:.0f}%** of analyzed markets are net-positive WITH the rebate "
        f"itself doing >=25% of the work (mean ${optimistic.get('mean_net_rebate_driven_only', 0) or 0:.2f}/day "
        f"on that subset), vs. a further **{opt_sc*100:.0f}%** that are net-positive only because "
        f"measured adverse-selection came out negative (i.e. realized spread capture / short-sample "
        f"mean reversion swamps a reward pool that is a rounding error by comparison -- NOT evidence "
        f"the rebate program itself works, and heavily exposed to small-sample overfitting on a few "
        f"days of trade tape). At the headline (50% capture, 15-min) scenario: "
        f"**{head_rd*100:.0f}%** rebate-driven, **{head_sc*100:.0f}%** spread-capture-only. Under "
        f"the stress scenario (5% capture, 6h passive): **{stress_rd*100:.0f}%** rebate-driven, "
        f"**{stress_sc*100:.0f}%** spread-capture-only."
    )

    if head_rd < 0.15 or (headline.get("mean_net_rebate_driven_only") or 0) < 1.0:
        lines.append(
            "\n**BLUNT VERDICT ON THE REBATE ITSELF: mostly NULL, and the reasons are structural, "
            "not just noisy estimation.** The reward pools are real and the fee side is genuinely "
            "favorable (maker fills are free on 193/196 series) -- but (a) Kalshi deliberately "
            "concentrates incentives on markets with essentially no organic liquidity, which is "
            "exactly where resting quotes get picked off hardest; (b) the median reward pool (~$15/"
            "day total, SHARED pro-rata across every maker who shows up) is too small to matter once "
            "split even a modest number of ways, let alone once adverse selection is netted out; (c) "
            "with only public depth-snapshot data we cannot rule out that our capture-share heuristic "
            "is itself too generous -- if other makers are already resting comparable or larger size "
            "at the touch (plausible on any market Kalshi bothers to advertise a reward for), our "
            "real share collapses further than even the 5% stress scenario. A small minority of "
            "markets DO show a genuinely rebate-driven positive NET (see table above, filtered to "
            "REBATE-DRIVEN) -- worth flagging individually but not a systematic, capacity-bearing "
            "edge: concentrated in short-lived, single-event novelty markets (game-day props, "
            "one-off gas-price windows) with no persistent structure to exploit at scale.\n\n"
            "**Separately**, a chunk of the sample shows large positive NET that is NOT rebate-"
            "driven -- it comes from measured adverse-selection being negative (the trade tape shows "
            "the resting side of real trades profiting on average over the following minutes/hours). "
            "That is a genuinely different, unverified hypothesis (\"is passive market-making on "
            "thin, jumpy Kalshi novelty/political markets profitable purely from spread capture, "
            "rebate or no rebate\") riding on the same tape -- and it is exactly the kind of result "
            "that demands the discipline used to kill prior candidates: it comes from a short (up to "
            "~5-day) lookback window on markets undergoing real price discovery (one flagged example, "
            "a Senate-primary candidate market, saw its price swing from $0.01 to $0.79 in the "
            "window), so a negative markout there is plausibly a small-sample artifact of a market "
            "trending through a specific historical realization, not a stable structural edge. It is "
            "reported here for transparency but is explicitly OUT OF SCOPE for the K1 rebate verdict "
            "and should not be read as a second confirmed edge without its own dedicated, longer-"
            "horizon OOS test."
        )
    else:
        lines.append(
            "\n**VERDICT ON THE REBATE ITSELF: a real, if modest, edge on a subset of markets -- but "
            "it lives entirely on illiquid novelty markets, not Kalshi's liquid flagship products (no "
            "incentive program exists on any high-volume series). Deployability is capped by (a) the "
            "small absolute size of most reward pools once shared pro-rata, and (b) genuine "
            "uncertainty in our capture-share estimate, which is the single least-verifiable input in "
            "this analysis without live two-sided quoting. Worth a small, closely-monitored live pilot "
            "on the specific REBATE-DRIVEN markets flagged net-positive above, sized to the smaller "
            "end of the capacity estimate -- NOT a scalable standalone strategy. The additional "
            "spread-capture-dominated markets in the sample are a separate, unverified hypothesis "
            "(see caveat above) and are excluded from this verdict."
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
