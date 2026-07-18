#!/usr/bin/env python3
"""
kalshi_new_listing.py

OOS test of Kalshi strategy candidate K3: NEW-LISTING / cold-market
mispricing (inspired by djmorgan26/Invest "New Listing" strategy, which used
a crude flat-10c mispricing placeholder -- we measure the REAL convergence
instead, on Kalshi's own free historical data).

HYPOTHESIS: freshly-listed Kalshi markets (<48h old) with wide bid/ask
spreads (no market-maker has arrived yet) may be mispriced at listing and
converge toward "fair value" as liquidity/attention arrives over the
following ~48h. Question: is there a systematic, fee-AND-spread-surviving
edge from trading fresh wide-spread Kalshi markets?

DATA (all free, no auth): Kalshi `/series` (fee_multiplier, category) +
`/markets?status=settled` (open_time/close_time/result) +
`/series/{s}/markets/{t}/candlesticks` (yes_bid/yes_ask price path from
listing forward). We do NOT have historical order-book snapshots, so
"spread" is read off the candlestick yes_bid/yes_ask close_dollars fields
(Kalshi's own OHLC of the resting quotes each hour) -- this is the same
information the live `/orderbook` would show at that historical instant.

METHOD
  1. Universe: settled markets across non-ultra-short-horizon categories
     (Politics, Elections, Economics, Financials, Crypto, Companies,
     Climate and Weather, World, Science and Technology, Health,
     Commodities, Entertainment) with lifetime (close_time-open_time) >=
     MIN_LIFETIME_HOURS, so a +48h "converged" snapshot sits comfortably
     inside the market's life (not contaminated by near-resolution informed
     flow at the other end).
  2. For each qualifying market, three ENTRY snapshots ("age" segmentation):
     first valid two-sided candle within [0,6)h, [6,24)h, [24,48)h of
     open_time. A single REFERENCE ("converged") snapshot: nearest valid
     candle to +48h (window [44,52)h). Segment entries by SPREAD at entry:
     wide (>=6c, "no MM yet") vs tight (<6c).
  3. Hypotheses tested, all NET of Kalshi's real quadratic per-contract fee
     and using EXECUTABLE prices (you PAY the ask to buy YES / pay 1-bid to
     buy NO -- the wide spread IS the entry cost, not a mid-price fiction):
       (a) Is the early mid a WORSE predictor of the outcome than the later
           (converged) mid? Brier score early vs later, paired, day-
           clustered t on the per-observation Brier delta. Full calibration
           (reliability) table for both.
       (b) Directional bias: does price systematically drift from entry to
           +48h in one direction (mean(later_mid-entry_mid)), and is entry
           mid systematically biased vs the realized outcome
           (mean(entry_mid-result))? Day-clustered t, by spread x age
           segment.
       (c) Strategy PnL: TRAIN (first 65% of markets by close_time) fits a
           directional rule per (spread_bucket) from the sign+significance
           of mean(result-entry_mid) on the PRIMARY 0-6h "fresh" entry
           bucket only (no peeking at TEST). That fixed rule is then
           applied on TEST, in two variants: (i) HOLD-TO-SETTLEMENT (pay
           the entry ask/no-ask, net of fee, collect $1/$0 at resolution)
           and (ii) HOLD-TO-CONVERGENCE (pay the entry ask, net of fee at
           entry AND exit, sell back at the +48h bid -- the literal
           "trade the listing mispricing, exit once a MM arrives" test).
           Day-clustered (by entry UTC date) t-stats, gross (mid, no
           spread) vs net (ask/bid, + fee) reported side by side so the
           spread's cost is visible, not hidden.
  4. Multiple-testing: every t-test actually computed is counted; a
     Bonferroni-corrected alpha is reported alongside the nominal one.
  5. Capacity: naive extrapolation of qualifying fresh+wide-spread markets
     per week in the scraped window (flagged as naive, same caveat used in
     kalshi_structural_arb.py), x observed near-entry volume, x measured
     net edge/ct (if any).

DISCIPLINE (matches the bar that killed ~21 prior candidates in this farm):
  * NET of Kalshi's quadratic fee (ceil(fee_multiplier*0.07*C*p*(1-p)*100)/
    100 per contract), fee_multiplier looked up per-series from the same
    /series call that builds the universe (no extra round-trips needed).
  * EXECUTABLE prices only for PnL: entry = ask (buy) or 1-bid (buy NO);
    exit (convergence variant) = later bid (sell) or 1-later_ask (sell NO).
    Mid is reported ONLY as the "gross" comparison to show what the spread
    costs.
  * Day-clustered t (cluster = UTC calendar date of the entry candle).
  * OOS: directional rule fit on TRAIN (chronological, by market close_time)
    only, evaluated on TEST only. No rule is fit on the segment it is
    scored on.
  * "No real quote yet" (yes_bid<=1c AND yes_ask>=99c simultaneously --
    Kalshi's empty-book tick-floor/ceiling default, not a real 98c
    "spread") is filtered out of both entry and reference candles.
  * Small-n and multiple-testing flagged; verdict is blunt.

Outputs: kalshi_new_listing_report.md, kalshi_new_listing_summary.json
Raw series/settled-market/candlestick pulls cached under
scratchpad/kalshi_newlisting_raw/ so reruns are fast and idempotent.
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict, Counter
from datetime import datetime, timezone
import concurrent.futures as cf

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/kalshi_newlisting_raw"
os.makedirs(RAW, exist_ok=True)

RNG_SEED = 20260718
random.seed(RNG_SEED)

# ---- universe / sampling ----
CATEGORIES = [
    "Politics", "Elections", "Economics", "Financials", "Crypto", "Companies",
    "Climate and Weather", "World", "Science and Technology", "Health",
    "Commodities", "Entertainment",
]
MAX_SERIES_PER_CATEGORY = 150
MAX_QUALIFYING_PER_SERIES = 15       # cap so one recurring ladder series can't dominate
MIN_LIFETIME_HOURS = 96.0            # so the +48h reference sits mid-life, not near-close
CANDLE_HORIZON_HOURS = 56.0          # fetch candles [open, open+56h] only -- bounds cost
PERIOD_INTERVAL_MIN = 60             # hourly candlesticks

# ---- entry / reference definition ----
AGE_BUCKETS = [("0-6h", 0.0, 6.0), ("6-24h", 6.0, 24.0), ("24-48h", 24.0, 48.0)]
REF_TARGET_H = 48.0
REF_WINDOW_H = (44.0, 52.0)
WIDE_SPREAD_C = 0.06                 # >=6c at entry = "no MM yet" (wide)

# ---- fee ----
FEE_RATE = 0.07

# ---- TRAIN/TEST ----
TRAIN_FRAC = 0.65

WORKERS = 24
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5


# ============================================================ HTTP
def _get(url):
    last = None
    for i in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kalshi-new-listing-oos-test/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(1.0 * (i + 1))
                continue
            time.sleep(0.4 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.4 * (i + 1))
    return {"__err": str(last)}


def parse_ts(iso_s):
    return int(datetime.fromisoformat(iso_s.replace("Z", "+00:00")).timestamp())


def date_key(unix_ts):
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%d")


# ============================================================ universe
def fetch_series_universe():
    fn = os.path.join(RAW, "series_universe.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            pass
    d = _get(f"{BASE}/series?limit=5")
    ser = d.get("series", []) if "__err" not in d else []
    json.dump(ser, open(fn, "w"))
    return ser


def list_settled(series_ticker):
    fn = os.path.join(RAW, f"settled_{series_ticker}.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            pass
    out = []
    cursor = None
    for _ in range(20):
        url = f"{BASE}/markets?series_ticker={series_ticker}&status=settled&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get(url)
        if "__err" in d:
            break
        ms = d.get("markets", [])
        out += ms
        cursor = d.get("cursor")
        if not cursor or not ms:
            break
    json.dump(out, open(fn, "w"))
    return out


def fetch_candles(series_ticker, ticker, start_ts, end_ts):
    fn = os.path.join(RAW, f"cand_{ticker}.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            pass
    url = (f"{BASE}/series/{series_ticker}/markets/{ticker}/candlesticks"
           f"?start_ts={start_ts}&end_ts={end_ts}&period_interval={PERIOD_INTERVAL_MIN}")
    d = _get(url)
    cs = d.get("candlesticks", []) if "__err" not in d else []
    json.dump(cs, open(fn, "w"))
    return cs


def _cd(node, field="close_dollars"):
    if not isinstance(node, dict):
        return None
    v = node.get(field)
    if v in (None, ""):
        return None
    try:
        return float(v)
    except Exception:
        return None


def is_empty_book(yb, ya):
    """Kalshi's tick-floor/ceiling default when literally nothing is resting
    (yes_bid pinned at $0.01, yes_ask pinned at $0.99) -- not a real 98c
    'spread', a placeholder for 'no market yet'. Excluded from both entry
    and reference candles."""
    return yb <= 0.011 and ya >= 0.989


def valid_quote(c):
    yb = _cd(c.get("yes_bid"))
    ya = _cd(c.get("yes_ask"))
    if yb is None or ya is None:
        return None
    if not (0.0 < yb < 1.0 and 0.0 < ya <= 1.0):
        return None
    if ya < yb:
        return None
    if is_empty_book(yb, ya):
        return None
    try:
        vol = float(c.get("volume_fp", 0) or 0)
    except Exception:
        vol = 0.0
    return {"yes_bid": yb, "yes_ask": ya, "mid": (yb + ya) / 2.0,
            "spread": round(ya - yb, 6), "end_ts": c.get("end_period_ts"), "volume_fp": vol}


def find_entry(candles, open_ts, lo_h, hi_h):
    lo, hi = open_ts + lo_h * 3600, open_ts + hi_h * 3600
    for c in sorted(candles, key=lambda x: x.get("end_period_ts") or 0):
        ts = c.get("end_period_ts")
        if ts is None or not (lo <= ts < hi):
            continue
        q = valid_quote(c)
        if q is None:
            continue
        q["hours_since_open"] = (ts - open_ts) / 3600.0
        return q
    return None


def find_reference(candles, open_ts):
    lo, hi = open_ts + REF_WINDOW_H[0] * 3600, open_ts + REF_WINDOW_H[1] * 3600
    best, best_dist = None, None
    for c in candles:
        ts = c.get("end_period_ts")
        if ts is None or not (lo <= ts < hi):
            continue
        q = valid_quote(c)
        if q is None:
            continue
        dist = abs((ts - open_ts) / 3600.0 - REF_TARGET_H)
        if best is None or dist < best_dist:
            best, best_dist = q, dist
    if best is not None:
        best["hours_since_open"] = (best["end_ts"] - open_ts) / 3600.0
    return best


# ============================================================ fees
def fee_ceil(p, mult=1.0):
    p = min(max(p, 0.0), 1.0)
    return math.ceil(100.0 * FEE_RATE * mult * p * (1.0 - p)) / 100.0


# ============================================================ stats
def clustered_t(values_by_group):
    """mean of per-group means, t = mean/(sd/sqrt(k)). Returns (mean,t,k,n)."""
    gmeans, n = [], 0
    for _, vs in values_by_group.items():
        if not vs:
            continue
        gmeans.append(sum(vs) / len(vs))
        n += len(vs)
    k = len(gmeans)
    if k == 0:
        return (float("nan"), float("nan"), 0, 0)
    if k < 2:
        return (statistics.mean(gmeans), float("nan"), k, n)
    m = statistics.mean(gmeans)
    sd = statistics.pstdev(gmeans) * math.sqrt(k / (k - 1)) if k > 1 else 0.0
    t = m / (sd / math.sqrt(k)) if sd > 0 else float("nan")
    return (m, t, k, n)


def group_by_date(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r["entry_date"]].append(r[key])
    return g


def brier_and_ece(rows, price_key, n_bins=10):
    if not rows:
        return {"n": 0, "brier": None, "ece": None, "table": []}
    brier = statistics.mean((r[price_key] - r["result"]) ** 2 for r in rows)
    edges = [i / n_bins for i in range(n_bins + 1)]
    table = []
    ece_num = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        sub = [r for r in rows if lo <= r[price_key] < hi or (i == n_bins - 1 and r[price_key] == hi)]
        if not sub:
            continue
        mean_p = statistics.mean(r[price_key] for r in sub)
        realized = statistics.mean(r["result"] for r in sub)
        table.append({"band": f"[{lo:.1f},{hi:.1f})", "n": len(sub),
                       "mean_price": round(mean_p, 4), "realized_freq": round(realized, 4)})
        ece_num += len(sub) * abs(mean_p - realized)
    ece = ece_num / len(rows)
    return {"n": len(rows), "brier": round(brier, 5), "ece": round(ece, 5), "table": table}


# ============================================================ collection
def collect():
    series_universe = fetch_series_universe()
    print(f"[collect] {len(series_universe)} total series on Kalshi", file=sys.stderr)
    fee_mult = {}
    by_cat = defaultdict(list)
    for s in series_universe:
        t = s.get("ticker")
        if not t:
            continue
        fee_mult[t] = float(s.get("fee_multiplier", 1.0) or 1.0)
        cat = s.get("category")
        if cat in CATEGORIES:
            by_cat[cat].append(t)

    sample_series = []
    for cat in CATEGORIES:
        pool = by_cat.get(cat, [])
        if len(pool) > MAX_SERIES_PER_CATEGORY:
            pool = random.sample(pool, MAX_SERIES_PER_CATEGORY)
        sample_series += pool
    sample_series = sorted(set(sample_series))
    print(f"[collect] sampling {len(sample_series)} series across {len(CATEGORIES)} categories", file=sys.stderr)

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        settled_lists = list(ex.map(list_settled, sample_series))

    qualifying = []
    for series_t, ms in zip(sample_series, settled_lists):
        keep = []
        for m in ms:
            r = m.get("result")
            if r not in ("yes", "no"):
                continue
            ot, ct = m.get("open_time"), m.get("close_time")
            if not ot or not ct:
                continue
            try:
                o, c = parse_ts(ot), parse_ts(ct)
            except Exception:
                continue
            life_h = (c - o) / 3600.0
            if life_h < MIN_LIFETIME_HOURS:
                continue
            keep.append({"ticker": m["ticker"], "series": series_t, "event": m.get("event_ticker"),
                         "category": m.get("category"), "title": m.get("title"),
                         "open_ts": o, "close_ts": c, "life_h": life_h,
                         "result": 1 if r == "yes" else 0})
        if len(keep) > MAX_QUALIFYING_PER_SERIES:
            keep.sort(key=lambda x: x["close_ts"])
            stride = len(keep) / MAX_QUALIFYING_PER_SERIES
            keep = [keep[int(i * stride)] for i in range(MAX_QUALIFYING_PER_SERIES)]
        qualifying.extend(keep)
    print(f"[collect] {len(qualifying)} settled markets qualify "
          f"(result present, lifetime>={MIN_LIFETIME_HOURS}h)", file=sys.stderr)

    def _fetch_one(m):
        start = m["open_ts"]
        end = min(m["close_ts"], m["open_ts"] + int(CANDLE_HORIZON_HOURS * 3600))
        cs = fetch_candles(m["series"], m["ticker"], start, end)
        return m, cs

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(_fetch_one, qualifying))
    print(f"[collect] candlesticks fetched for {len(results)} markets", file=sys.stderr)

    rows = []
    n_no_ref = 0
    n_no_entry_any = 0
    for m, cs in results:
        if not cs:
            continue
        ref = find_reference(cs, m["open_ts"])
        if ref is None:
            n_no_ref += 1
            continue
        got_any = False
        for bucket_name, lo_h, hi_h in AGE_BUCKETS:
            entry = find_entry(cs, m["open_ts"], lo_h, hi_h)
            if entry is None:
                continue
            if entry["end_ts"] >= ref["end_ts"] - 1800:  # need >=30min real gap
                continue
            got_any = True
            spread_bucket = "wide" if entry["spread"] >= WIDE_SPREAD_C else "tight"
            rows.append({
                "ticker": m["ticker"], "series": m["series"], "event": m["event"],
                "category": m["category"], "title": m["title"],
                "close_ts": m["close_ts"], "open_ts": m["open_ts"], "life_h": round(m["life_h"], 1),
                "result": m["result"],
                "age_bucket": bucket_name,
                "spread_bucket": spread_bucket,
                "entry_mid": entry["mid"], "entry_bid": entry["yes_bid"], "entry_ask": entry["yes_ask"],
                "entry_spread": entry["spread"], "entry_hours": round(entry["hours_since_open"], 2),
                "entry_volume_fp": entry["volume_fp"],
                "entry_date": date_key(entry["end_ts"]),
                "later_mid": ref["mid"], "later_bid": ref["yes_bid"], "later_ask": ref["yes_ask"],
                "later_spread": ref["spread"], "later_hours": round(ref["hours_since_open"], 2),
                "fee_mult": fee_mult.get(m["series"], 1.0),
            })
        if not got_any:
            n_no_entry_any += 1
    print(f"[collect] {len(rows)} entry observations from "
          f"{len(set(r['ticker'] for r in rows))} unique markets "
          f"(dropped: {n_no_ref} no valid +48h reference, "
          f"{n_no_entry_any} had a reference but no valid entry in any age bucket)", file=sys.stderr)
    return rows


# ============================================================ analysis
def compute_pnl_rows(rows, direction, entry_side_field_prefix="entry"):
    """direction: 'BUY_YES' or 'BUY_NO'. Returns list of dicts with gross/net
    settlement pnl and gross/net convergence pnl per row."""
    out = []
    for r in rows:
        fm = r["fee_mult"]
        if direction == "BUY_YES":
            gross_settle = r["result"] - r["entry_mid"]
            net_settle = r["result"] - r["entry_ask"] - fee_ceil(r["entry_ask"], fm)
            gross_conv = r["later_mid"] - r["entry_mid"]
            net_conv = (r["later_bid"] - r["entry_ask"]
                        - fee_ceil(r["entry_ask"], fm) - fee_ceil(r["later_bid"], fm))
        else:  # BUY_NO
            entry_no_ask = 1.0 - r["entry_bid"]
            entry_no_mid = 1.0 - r["entry_mid"]
            gross_settle = (1 - r["result"]) - entry_no_mid
            net_settle = (1 - r["result"]) - entry_no_ask - fee_ceil(entry_no_ask, fm)
            gross_conv = (1.0 - r["later_mid"]) - entry_no_mid
            # NO round-trip: buy NO at entry_no_ask=(1-entry_bid); sell NO later
            # at later_no_bid=(1-later_ask). Symmetric to the YES case.
            later_no_bid = 1.0 - r["later_ask"]
            net_conv = (later_no_bid - entry_no_ask
                        - fee_ceil(entry_no_ask, fm) - fee_ceil(later_no_bid, fm))
        out.append({**r, "direction": direction,
                    "gross_pnl_settle": gross_settle, "net_pnl_settle": net_settle,
                    "gross_pnl_conv": gross_conv, "net_pnl_conv": net_conv})
    return out


def analyze(rows):
    out = {}
    out["n_observations"] = len(rows)
    out["n_unique_markets"] = len(set(r["ticker"] for r in rows))
    out["n_series"] = len(set(r["series"] for r in rows))
    out["n_categories"] = len(set(r["category"] for r in rows if r["category"]))
    out["category_breakdown"] = Counter(r["category"] for r in rows).most_common()
    out["age_bucket_breakdown"] = Counter(r["age_bucket"] for r in rows).most_common()
    out["spread_bucket_breakdown"] = Counter(r["spread_bucket"] for r in rows).most_common()
    out["date_span"] = {
        "earliest_entry_date": min(r["entry_date"] for r in rows) if rows else None,
        "latest_entry_date": max(r["entry_date"] for r in rows) if rows else None,
    }

    n_tests = 0

    # ---------------------------------------------------- (a) calibration/Brier
    calib = {}
    calib["overall_entry"] = brier_and_ece(rows, "entry_mid")
    calib["overall_later"] = brier_and_ece(rows, "later_mid")
    brier_deltas_by_group = group_by_date(
        [{**r, "brier_delta": (r["entry_mid"] - r["result"]) ** 2 - (r["later_mid"] - r["result"]) ** 2}
         for r in rows], "brier_delta")
    m, t, k, n = clustered_t(brier_deltas_by_group)
    n_tests += 1
    calib["brier_delta_overall"] = {"mean_early_minus_later_sqerr": round(m, 5) if m == m else None,
                                     "day_clustered_t": round(t, 3) if t == t else None,
                                     "n_days": k, "n_obs": n,
                                     "interpretation": ("positive => early price has HIGHER squared error "
                                                         "than later (converged) price, i.e. later is a "
                                                         "better predictor / real mispricing resolves; "
                                                         "negative or ~0 => early is not worse")}
    calib_by_segment = {}
    for bname, _, _ in AGE_BUCKETS:
        for sbucket in ("wide", "tight"):
            sub = [r for r in rows if r["age_bucket"] == bname and r["spread_bucket"] == sbucket]
            if len(sub) < 5:
                calib_by_segment[f"{bname}|{sbucket}"] = {"n": len(sub), "note": "too small (<5), skipped"}
                continue
            d_by_g = group_by_date(
                [{**r, "bd": (r["entry_mid"] - r["result"]) ** 2 - (r["later_mid"] - r["result"]) ** 2}
                 for r in sub], "bd")
            m2, t2, k2, n2 = clustered_t(d_by_g)
            n_tests += 1
            calib_by_segment[f"{bname}|{sbucket}"] = {
                "n": len(sub), "brier_entry": brier_and_ece(sub, "entry_mid")["brier"],
                "brier_later": brier_and_ece(sub, "later_mid")["brier"],
                "mean_brier_delta": round(m2, 5) if m2 == m2 else None,
                "day_clustered_t": round(t2, 3) if t2 == t2 else None, "n_days": k2}
    calib["by_segment"] = calib_by_segment
    out["calibration"] = calib

    # ---------------------------------------------------- (b) directional bias
    bias = {}
    for bname, _, _ in AGE_BUCKETS:
        for sbucket in ("wide", "tight"):
            sub = [r for r in rows if r["age_bucket"] == bname and r["spread_bucket"] == sbucket]
            if len(sub) < 5:
                bias[f"{bname}|{sbucket}"] = {"n": len(sub), "note": "too small (<5), skipped"}
                continue
            drift_g = group_by_date([{**r, "d": r["later_mid"] - r["entry_mid"]} for r in sub], "d")
            m_drift, t_drift, k_drift, _ = clustered_t(drift_g); n_tests += 1
            bias_entry_g = group_by_date([{**r, "d": r["entry_mid"] - r["result"]} for r in sub], "d")
            m_be, t_be, k_be, _ = clustered_t(bias_entry_g); n_tests += 1
            bias_later_g = group_by_date([{**r, "d": r["later_mid"] - r["result"]} for r in sub], "d")
            m_bl, t_bl, k_bl, _ = clustered_t(bias_later_g); n_tests += 1
            bias[f"{bname}|{sbucket}"] = {
                "n": len(sub),
                "mean_price_drift_later_minus_entry": round(m_drift, 4) if m_drift == m_drift else None,
                "drift_day_clustered_t": round(t_drift, 3) if t_drift == t_drift else None,
                "mean_entry_bias_vs_result": round(m_be, 4) if m_be == m_be else None,
                "entry_bias_day_clustered_t": round(t_be, 3) if t_be == t_be else None,
                "mean_later_bias_vs_result": round(m_bl, 4) if m_bl == m_bl else None,
                "later_bias_day_clustered_t": round(t_bl, 3) if t_bl == t_bl else None,
            }
    out["directional_bias"] = bias

    # ---------------------------------------------------- (c) PnL, TRAIN-fit -> TEST-scored
    tickers_sorted = sorted(set(r["ticker"] for r in rows), key=lambda tk: next(
        r["close_ts"] for r in rows if r["ticker"] == tk))
    n_train = int(len(tickers_sorted) * TRAIN_FRAC)
    train_tickers = set(tickers_sorted[:n_train])
    test_tickers = set(tickers_sorted[n_train:])
    for r in rows:
        r["split"] = "train" if r["ticker"] in train_tickers else "test"

    primary = [r for r in rows if r["age_bucket"] == "0-6h"]
    train_primary = [r for r in primary if r["split"] == "train"]
    test_primary = [r for r in primary if r["split"] == "test"]

    rules = {}
    for sbucket in ("wide", "tight"):
        sub = [r for r in train_primary if r["spread_bucket"] == sbucket]
        if len(sub) < 8:
            rules[sbucket] = {"rule": "NO_EDGE", "reason": f"train n={len(sub)} < 8, too small to fit"}
            continue
        g = group_by_date([{**r, "d": r["result"] - r["entry_mid"]} for r in sub], "d")
        m, t, k, n = clustered_t(g)
        n_tests += 1
        if t == t and t >= 2.0 and m > 0:
            rule = "BUY_YES"
        elif t == t and t <= -2.0 and m < 0:
            rule = "BUY_NO"
        else:
            rule = "NO_EDGE"
        rules[sbucket] = {"rule": rule, "train_n": len(sub), "train_mean_result_minus_entry_mid": round(m, 4) if m == m else None,
                           "train_day_clustered_t": round(t, 3) if t == t else None, "train_n_days": k}
    out["train_fit_rules"] = rules

    pnl_results = {}
    for sbucket in ("wide", "tight"):
        rule = rules[sbucket]["rule"]
        test_sub = [r for r in test_primary if r["spread_bucket"] == sbucket]
        if rule == "NO_EDGE" or not test_sub:
            pnl_results[sbucket] = {"rule": rule, "test_n": len(test_sub),
                                     "note": "no directional rule survived TRAIN fit (or empty TEST) -> not traded"}
            continue
        priced = compute_pnl_rows(test_sub, rule)
        g_settle = group_by_date(priced, "gross_pnl_settle")
        n_settle = group_by_date(priced, "net_pnl_settle")
        g_conv = group_by_date(priced, "gross_pnl_conv")
        n_conv = group_by_date(priced, "net_pnl_conv")
        gm, gt, gk, gn = clustered_t(g_settle); n_tests += 1
        nm, nt, nk, nn = clustered_t(n_settle); n_tests += 1
        gcm, gct, gck, gcn = clustered_t(g_conv); n_tests += 1
        ncm, nct, nck, ncn = clustered_t(n_conv); n_tests += 1
        pnl_results[sbucket] = {
            "rule": rule, "test_n": len(test_sub), "test_n_days": nk,
            "hold_to_settlement": {
                "gross_pnl_per_ct": round(gm, 4) if gm == gm else None,
                "gross_day_clustered_t": round(gt, 3) if gt == gt else None,
                "net_pnl_per_ct": round(nm, 4) if nm == nm else None,
                "net_day_clustered_t": round(nt, 3) if nt == nt else None,
            },
            "hold_to_convergence_48h": {
                "gross_pnl_per_ct": round(gcm, 4) if gcm == gcm else None,
                "gross_day_clustered_t": round(gct, 3) if gct == gct else None,
                "net_pnl_per_ct": round(ncm, 4) if ncm == ncm else None,
                "net_day_clustered_t": round(nct, 3) if nct == nct else None,
            },
        }
    out["pnl_test_oos"] = pnl_results

    # pooled (wide+tight combined, whatever each segment's rule was) -- one more test
    pooled_rows = []
    for sbucket in ("wide", "tight"):
        rule = rules[sbucket]["rule"]
        if rule == "NO_EDGE":
            continue
        test_sub = [r for r in test_primary if r["spread_bucket"] == sbucket]
        pooled_rows += compute_pnl_rows(test_sub, rule)
    if pooled_rows:
        pg = group_by_date(pooled_rows, "net_pnl_settle")
        pm, pt, pk, pn = clustered_t(pg); n_tests += 1
        out["pnl_test_oos_pooled"] = {"n": len(pooled_rows), "n_days": pk,
                                       "net_pnl_per_ct_settlement": round(pm, 4) if pm == pm else None,
                                       "day_clustered_t": round(pt, 3) if pt == pt else None}
    else:
        out["pnl_test_oos_pooled"] = {"n": 0, "note": "no segment carried a TRAIN-fit directional rule"}

    out["train_test_split"] = {"n_train_markets": len(train_tickers), "n_test_markets": len(test_tickers),
                                "train_frac_target": TRAIN_FRAC}

    # ---------------------------------------------------- multiple testing
    alpha_nominal = 0.05
    alpha_bonf = alpha_nominal / max(n_tests, 1)
    out["multiple_testing"] = {
        "n_distinct_t_tests_computed": n_tests,
        "nominal_alpha": alpha_nominal,
        "bonferroni_alpha": round(alpha_bonf, 6),
        "approx_bonferroni_t_threshold_two_sided": (
            round(_approx_t_threshold(alpha_bonf), 2) if n_tests > 0 else None),
        "note": ("t-thresholds are large-sample normal approximations (repo convention); "
                 "with few day-clusters (k) in a segment the true threshold is higher (fatter "
                 "t-tails) -- n_days per segment is reported so this can be judged."),
    }

    # ---------------------------------------------------- capacity
    fresh_wide = [r for r in rows if r["age_bucket"] == "0-6h" and r["spread_bucket"] == "wide"]
    span_days = None
    cap = {"n_fresh_wide_observations_in_sample": len(fresh_wide)}
    if rows:
        dates = sorted(set(r["entry_date"] for r in rows))
        d0 = datetime.strptime(dates[0], "%Y-%m-%d")
        d1 = datetime.strptime(dates[-1], "%Y-%m-%d")
        span_days = max((d1 - d0).days, 1)
        naive_per_week = len(fresh_wide) / span_days * 7.0
        cap["scraped_window_days"] = span_days
        cap["naive_fresh_wide_markets_per_week"] = round(naive_per_week, 2)
        cap["naive_note"] = ("Settled-market sampling is a retrospective census over a mixed multi-"
                              "month/year historical window (each series' full settled history, capped "
                              f"per-series), NOT a live continuous listing-arrival stream -- this is a "
                              "naive linear rate, directional only, per the same caveat used in the K2 "
                              "structural-arb OOS test.")
        if fresh_wide:
            mean_vol = statistics.mean(r["entry_volume_fp"] for r in fresh_wide)
            cap["mean_entry_hour_volume_contracts"] = round(mean_vol, 2)
        rule_wide = rules.get("wide", {}).get("rule")
        net_edge_wide = None
        if rule_wide and rule_wide != "NO_EDGE":
            net_edge_wide = pnl_results.get("wide", {}).get("hold_to_settlement", {}).get("net_pnl_per_ct")
        if net_edge_wide:
            cap["illustrative_weekly_dollar_capacity_if_edge_real"] = round(
                naive_per_week * cap.get("mean_entry_hour_volume_contracts", 1.0) * net_edge_wide, 2)
            cap["capacity_caveat"] = ("Illustrative only: uses ONE hour's observed volume as a per-market "
                                       "size proxy, not real depth-at-price; if net edge below is not "
                                       "real/significant this number is meaningless.")
        else:
            cap["illustrative_weekly_dollar_capacity_if_edge_real"] = 0.0
            cap["capacity_caveat"] = "No surviving net-of-fee-and-spread edge in the wide-spread bucket -> capacity is moot."
    out["capacity"] = cap

    return out


def _approx_t_threshold(alpha_two_sided):
    """Inverse-normal approx (no scipy dependency) via Acklam-ish rational
    approximation, good enough for a reported threshold (not a formal p-value)."""
    p = 1.0 - alpha_two_sided / 2.0
    # Beasley-Springer-Moro approximation
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= phigh:
        q = p - 0.5
        r = q*q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    return x


# ============================================================ report
def write_report(analysis, rows, path):
    L = []
    L.append("# Kalshi NEW-LISTING / Cold-Market Mispricing -- OOS Test (K3)\n")
    L.append("Candidate: djmorgan26/Invest \"New Listing\" strategy, re-tested with the REAL measured "
             "convergence (not the source repo's flat-10c placeholder), net of Kalshi fee AND the "
             "wide entry spread cost.\n")
    L.append(f"n observations (market x age-bucket entries): **{analysis['n_observations']}**  ")
    L.append(f"n unique settled markets: **{analysis['n_unique_markets']}** across "
             f"{analysis['n_series']} series / {analysis['n_categories']} categories  ")
    L.append(f"Entry-date span: {analysis['date_span']['earliest_entry_date']} -> "
             f"{analysis['date_span']['latest_entry_date']}  ")
    L.append(f"Min lifetime required: {MIN_LIFETIME_HOURS}h; converged reference = nearest valid quote to "
             f"+{REF_TARGET_H}h (window {REF_WINDOW_H}); wide-spread threshold = {WIDE_SPREAD_C*100:.0f}c.\n")

    L.append("## Universe breakdown\n")
    L.append("**By category:**  " + ", ".join(f"{c}={n}" for c, n in analysis["category_breakdown"]))
    L.append("\n\n**By age bucket:**  " + ", ".join(f"{c}={n}" for c, n in analysis["age_bucket_breakdown"]))
    L.append("\n\n**By spread bucket:**  " + ", ".join(f"{c}={n}" for c, n in analysis["spread_bucket_breakdown"]))
    L.append("\n")

    L.append("## (a) Calibration: is the early price a WORSE predictor than the converged price?\n")
    ov = analysis["calibration"]
    L.append(f"- Overall Brier(entry_mid): **{ov['overall_entry']['brier']}** (n={ov['overall_entry']['n']})")
    L.append(f"- Overall Brier(later_mid, +48h): **{ov['overall_later']['brier']}** (n={ov['overall_later']['n']})")
    bd = ov["brier_delta_overall"]
    L.append(f"- Paired Brier delta (entry_sqerr - later_sqerr), day-clustered: mean={bd['mean_early_minus_later_sqerr']}, "
             f"t={bd['day_clustered_t']} (n_days={bd['n_days']}, n_obs={bd['n_obs']}). {bd['interpretation']}.\n")
    L.append("**Reliability table, entry_mid:**\n")
    L.append("| band | n | mean price | realized freq |")
    L.append("|---|---|---|---|")
    for row in ov["overall_entry"]["table"]:
        L.append(f"| {row['band']} | {row['n']} | {row['mean_price']} | {row['realized_freq']} |")
    L.append(f"\nECE(entry_mid) = **{ov['overall_entry']['ece']}**\n")
    L.append("**Reliability table, later_mid (+48h):**\n")
    L.append("| band | n | mean price | realized freq |")
    L.append("|---|---|---|---|")
    for row in ov["overall_later"]["table"]:
        L.append(f"| {row['band']} | {row['n']} | {row['mean_price']} | {row['realized_freq']} |")
    L.append(f"\nECE(later_mid) = **{ov['overall_later']['ece']}**\n")

    L.append("**By age x spread segment (Brier delta, day-clustered t):**\n")
    L.append("| segment | n | Brier(entry) | Brier(later) | mean delta | t | n_days |")
    L.append("|---|---|---|---|---|---|---|")
    for seg, d in ov["by_segment"].items():
        if "note" in d:
            L.append(f"| {seg} | {d['n']} | - | - | - | - | ({d['note']}) |")
        else:
            L.append(f"| {seg} | {d['n']} | {d['brier_entry']} | {d['brier_later']} | "
                     f"{d['mean_brier_delta']} | {d['day_clustered_t']} | {d['n_days']} |")
    L.append("")

    L.append("## (b) Directional bias by segment\n")
    L.append("| segment | n | drift (later-entry) mean | drift t | entry bias (entry-result) mean | t | "
             "later bias (later-result) mean | t |")
    L.append("|---|---|---|---|---|---|---|---|")
    for seg, d in analysis["directional_bias"].items():
        if "note" in d:
            L.append(f"| {seg} | {d['n']} | - | - | - | - | - | - ({d['note']}) |")
        else:
            L.append(f"| {seg} | {d['n']} | {d['mean_price_drift_later_minus_entry']} | {d['drift_day_clustered_t']} | "
                     f"{d['mean_entry_bias_vs_result']} | {d['entry_bias_day_clustered_t']} | "
                     f"{d['mean_later_bias_vs_result']} | {d['later_bias_day_clustered_t']} |")
    L.append("")

    L.append("## (c) TRAIN-fit directional rule -> TEST PnL, net of fee AND executable entry spread\n")
    tt = analysis["train_test_split"]
    L.append(f"TRAIN = {tt['n_train_markets']} markets (earliest {int(TRAIN_FRAC*100)}% by close_time), "
             f"TEST = {tt['n_test_markets']} markets. Rule fit ONLY on the 0-6h 'fresh entry' bucket of TRAIN.\n")
    for sbucket, rule_info in analysis["train_fit_rules"].items():
        L.append(f"- **{sbucket} spread, TRAIN fit**: rule=`{rule_info['rule']}`" +
                 (f", train_n={rule_info.get('train_n')}, mean(result-entry_mid)="
                  f"{rule_info.get('train_mean_result_minus_entry_mid')}, t="
                  f"{rule_info.get('train_day_clustered_t')} (n_days={rule_info.get('train_n_days')})"
                  if "reason" not in rule_info else f" ({rule_info['reason']})"))
    L.append("")
    L.append("**TEST-set results (rule applied out-of-sample):**\n")
    L.append("| spread bucket | rule | test n | gross PnL/ct (settle) | t | net PnL/ct (settle) | t | "
             "gross PnL/ct (conv 48h) | t | net PnL/ct (conv 48h) | t |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for sbucket, pr in analysis["pnl_test_oos"].items():
        if "note" in pr:
            L.append(f"| {sbucket} | {pr['rule']} | {pr['test_n']} | - | - | - | - | - | - | - | - ({pr['note']}) |")
        else:
            hs, hc = pr["hold_to_settlement"], pr["hold_to_convergence_48h"]
            L.append(f"| {sbucket} | {pr['rule']} | {pr['test_n']} | {hs['gross_pnl_per_ct']} | "
                     f"{hs['gross_day_clustered_t']} | {hs['net_pnl_per_ct']} | {hs['net_day_clustered_t']} | "
                     f"{hc['gross_pnl_per_ct']} | {hc['gross_day_clustered_t']} | {hc['net_pnl_per_ct']} | "
                     f"{hc['net_day_clustered_t']} |")
    L.append("")
    pooled = analysis["pnl_test_oos_pooled"]
    if pooled.get("n", 0) > 0:
        L.append(f"**Pooled TEST (all segments with a TRAIN-fit rule), hold-to-settlement, net**: "
                 f"n={pooled['n']}, net PnL/ct={pooled['net_pnl_per_ct_settlement']}, "
                 f"day-clustered t={pooled['day_clustered_t']} (n_days={pooled['n_days']})\n")
    else:
        L.append(f"**Pooled TEST**: {pooled.get('note')}\n")

    L.append("## Multiple testing\n")
    mt = analysis["multiple_testing"]
    L.append(f"- Distinct t-tests computed across this whole analysis: **{mt['n_distinct_t_tests_computed']}**")
    L.append(f"- Nominal alpha: {mt['nominal_alpha']}; Bonferroni-corrected alpha: {mt['bonferroni_alpha']}")
    L.append(f"- Approx. two-sided |t| threshold at Bonferroni alpha: **{mt['approx_bonferroni_t_threshold_two_sided']}** "
             f"(normal approximation; small n_days segments need a fatter threshold than this -- see n_days per row above)")
    L.append(f"- _{mt['note']}_\n")

    L.append("## Capacity\n")
    cap = analysis["capacity"]
    for k, v in cap.items():
        L.append(f"- {k}: {v}")
    L.append("")

    L.append("## Method notes / anti-artifact discipline\n")
    L.append("1. **Executable prices, not mid, for every PnL number**: buying YES pays `entry_ask`; buying NO "
             "pays `1-entry_bid`. The wide entry spread's *cost* is therefore baked directly into every net "
             "PnL figure (gross columns use mid, purely to show how much the spread itself eats -- gross minus "
             "net is the spread+fee cost).")
    L.append("2. **'Empty book' placeholder filtered out**: Kalshi shows yes_bid=$0.01/yes_ask=$0.99 as the tick "
             "floor/ceiling when literally nothing is resting yet -- this is NOT a real 98c spread, it is "
             "'no market yet', and is excluded from both entry and reference candles so 'wide spread' only "
             "captures genuine (if thin) two-sided quotes.")
    L.append("3. **OOS discipline**: the directional rule (BUY_YES / BUY_NO / NO_EDGE per spread bucket) is "
             "fit exclusively on TRAIN (chronologically earliest 65% of markets by close_time) using only the "
             "0-6h 'fresh entry' bucket, then scored, unmodified, on TEST. No rule is ever fit on the data it "
             "is evaluated on.")
    L.append("4. **Day-clustered t** throughout: cluster = UTC calendar date of the entry candle, matching the "
             "day-clustered-t convention used across this research farm (not observation-level iid t, which "
             "would overstate significance given markets sharing a listing day/week are correlated).")
    L.append("5. **+48h reference required to sit mid-life**: only markets with lifetime >= "
             f"{MIN_LIFETIME_HOURS}h qualify, so the 'converged' snapshot is not contaminated by near-"
             "resolution informed flow at the other end of the market's life.")
    L.append("6. **Two exit assumptions reported**: hold-to-SETTLEMENT (collect $1/$0, fee only at entry) and "
             "hold-to-CONVERGENCE (round-trip: pay the entry spread AND the exit spread, fee both legs) -- the "
             "literal 'trade the mispricing, exit once a MM arrives' mechanism is the convergence variant; "
             "settlement is the simpler benchmark.\n")

    L.append("## Verdict\n")
    L.append(analysis["verdict"])
    L.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(L))


def build_verdict(analysis):
    pnl = analysis["pnl_test_oos"]
    mt = analysis["multiple_testing"]
    bonf_t = mt["approx_bonferroni_t_threshold_two_sided"] or 3.5
    survivors = []
    for sbucket, pr in pnl.items():
        if "note" in pr:
            continue
        nt = pr["hold_to_settlement"]["net_day_clustered_t"]
        nm = pr["hold_to_settlement"]["net_pnl_per_ct"]
        if nt is not None and nm is not None and nt >= bonf_t and nm > 0:
            survivors.append((sbucket, "settlement", nm, nt))
        nct = pr["hold_to_convergence_48h"]["net_day_clustered_t"]
        ncm = pr["hold_to_convergence_48h"]["net_pnl_per_ct"]
        if nct is not None and ncm is not None and nct >= bonf_t and ncm > 0:
            survivors.append((sbucket, "convergence", ncm, nct))

    n_obs = analysis["n_observations"]
    small_n_flag = analysis["n_unique_markets"] < 150
    rules = analysis["train_fit_rules"]
    any_train_edge = any(r.get("rule") != "NO_EDGE" for r in rules.values())

    if not any_train_edge:
        verdict = (
            "NULL RESULT. No spread-bucket showed a day-clustered t>=2 directional bias on TRAIN "
            "(mean(result - entry_mid) for the 0-6h fresh-entry bucket) in EITHER direction, wide or "
            "tight spread -- i.e. there is no pre-registerable rule to even test out-of-sample. Fresh "
            "Kalshi listings are not systematically mispriced on YES vs NO at the moment of listing, "
            "wide-spread or not. This matches the campaign's dominant finding across "
            "K2/S1/S4/S5/W1/W3-a: Kalshi's opening quotes are calibrated, not exploitable."
        )
    elif not survivors:
        verdict = (
            "NULL RESULT (fee-and-spread-killed). A directional bias existed on TRAIN in at least one "
            "spread bucket, but when that fixed rule was scored on TEST using EXECUTABLE prices "
            "(paying the ask/no-ask, i.e. paying the wide spread you are trying to exploit) and net of "
            "Kalshi's fee, no segment survived the Bonferroni-corrected significance bar "
            f"(|t| >= {round(bonf_t,2)}) with a positive net edge, in either the hold-to-settlement or "
            "hold-to-convergence-48h variant. The mechanism the hypothesis requires -- 'the wide entry "
            "spread cost is more than repaid by convergence/resolution' -- does not survive contact with "
            "the actual cost of entering at the wide quote. Any apparent edge visible on TRAIN or in gross "
            "(mid-based) PnL is consumed by the spread + fee, exactly the failure mode flagged in the "
            "discipline section."
        )
    else:
        detail = "; ".join(f"{s} spread/{v}: net={m:.4f}/ct, t={t:.2f}" for s, v, m, t in survivors)
        verdict = (
            f"PARTIAL POSITIVE, FLAG FOR FURTHER SCRUTINY: {len(survivors)} segment(s) survived the "
            f"Bonferroni-corrected bar net of fee AND executable entry spread on TEST: {detail}. "
        )
        if small_n_flag:
            verdict += (f" CAUTION: only {analysis['n_unique_markets']} unique markets in the full sample "
                        "(small-n) -- before sizing this, re-verify with a larger/fresher settled-market "
                        "pull and a genuinely held-out forward-paper window; do not deploy on a single "
                        "backtest split of this size.")
        else:
            verdict += (" Recommend a forward-paper gate (same discipline as K-WX weather-nowcast) before "
                        "any live sizing -- a single train/test backtest split is not sufficient confirmation.")
    return verdict


def main():
    t0 = time.time()
    rows = collect()
    if len(rows) < 20:
        print(f"[main] only {len(rows)} observations collected -- widening categories/caps may be needed. "
              "Proceeding anyway (honest small-n result).", file=sys.stderr)
    analysis = analyze(rows)
    analysis["verdict"] = build_verdict(analysis)
    analysis["run_metadata"] = {
        "started_utc": datetime.fromtimestamp(t0, tz=timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "categories_scanned": CATEGORIES,
        "max_series_per_category": MAX_SERIES_PER_CATEGORY,
        "max_qualifying_per_series": MAX_QUALIFYING_PER_SERIES,
        "min_lifetime_hours": MIN_LIFETIME_HOURS,
        "wide_spread_threshold_dollars": WIDE_SPREAD_C,
        "reference_target_hours": REF_TARGET_H,
        "reference_window_hours": list(REF_WINDOW_H),
        "age_buckets": [b[0] for b in AGE_BUCKETS],
        "fee_model": "ceil(fee_multiplier*0.07*C*p*(1-p)*100)/100 dollars per contract, taker/executable side",
        "rng_seed": RNG_SEED,
    }

    out_prefix = os.path.join(HERE, "kalshi_new_listing")
    with open(f"{out_prefix}_summary.json", "w") as fh:
        json.dump(analysis, fh, indent=2, default=str)
    write_report(analysis, rows, f"{out_prefix}_report.md")

    print("\n" + "=" * 78)
    print(analysis["verdict"])
    print("=" * 78)
    print(f"[main] done in {time.time()-t0:.1f}s. Wrote {out_prefix}_report.md / _summary.json", file=sys.stderr)


if __name__ == "__main__":
    main()
