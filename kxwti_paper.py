#!/usr/bin/env python3
"""kxwti_paper.py -- WTI crude oil (KXWTI) maker paper-tracker.

VENUE_SCAN.md (2026-07-11) found KXWTI (Kalshi daily WTI-settlement strike ladder, ~99 open
markets, 4-tick median spread, ~500 median depth) as the #2 MM-niche candidate after crypto:
same "continuous external price feed -> theoretical price -> quote both sides" architecture as
the live KXBTC15M/KXBTCD box-harvester, just DAILY windows (not 15-min) and WTI front-month
futures (not a crypto index) as the fair-value feed. This is intentionally NOT the full
shadow_compare/Variant engine (queue model, gate sweep, 25-variant roster) that kalshi_collect.py
runs for crypto -- it is a right-sized, self-contained PAPER-ONLY tracker matching the shape of
kalshi_longshot_paper.py: a cheap 2x/day snapshot+settle script with its own JSON/CSV state.
Public APIs only, no auth, NO MONEY moves. Read-only.

WHAT IT DOES, each run:
  1. Fetch every OPEN KXWTI event with nested markets (GET /events?series_ticker=KXWTI&status=
     open&with_nested_markets=true) -- the full strike ladder: floor/cap strike, strike_type,
     yes/no bid-ask (dollars), top-of-book size (yes_bid_size_fp/yes_ask_size_fp = depth),
     volume, open interest, close_time (settlement instant).
  2. Fetch the WTI front-month futures price (spot fair-value feed) + trailing daily closes for
     a realized-vol estimate -- see FAIR-VALUE MODEL below for the exact, honestly-documented
     approximations.
  3. Per rung, compute fair_p = P(settle price crosses the strike) from the vol model, and log a
     row with fair_p, mid, and the two one-sided edges (edge_bid = fair_p - yes_bid, edge_ask =
     yes_ask - fair_p) to gha_data/kxwti_paper_<date>.jsonl (one growing file per UTC date --
     this is the rich diagnostic tape, NOT the scoreable file).
  4. Where an edge is positive, register a PAPER maker quote AT THE TOUCH (join yes_bid to buy
     YES, or join yes_ask to sell YES) -- no queue/price improvement modeled. This is the
     "would-be quote" persisted in kxwti_pending.json.
  5. FILL MODEL (conservative, no look-ahead): a pending quote is marked filled only when a
     LATER run's snapshot shows the OPPOSITE side of the book has crossed all the way through
     our resting price (yes_ask <= our bid, or yes_bid >= our ask). A bid/ask touching our price
     without crossing through is NOT a fill -- this understates fill rate relative to reality
     (queue priority could earn a fill on touch alone) but never overstates it, which is the
     right conservative bias for a pre-registration gate.
  6. SETTLEMENT: once a rung's event drops out of the open-events list, its result is looked up
     directly (GET /markets/{ticker}) and: (a) filled quotes get a realized P&L row appended to
     gha_data/kxwti_settled.csv (schema matching edge_verdicts.py's generic auto-loader:
     settle_ts/snap_ts date columns, pnl_per_contract value column); (b) quotes that never
     filled are dropped with zero P&L impact (never scored -- there was no real exposure).

FAIR-VALUE MODEL (simple, honestly-approximate -- do not treat as a real options-pricing model):
  * Spot proxy S0 = the latest WTI front-month futures quote (Yahoo Finance CL=F). Kalshi's own
    settlement source for KXWTI is ICE's WTI futures product (see event.settlement_sources);
    CL=F is the NYMEX/CME WTI future. These two contracts are DESIGNED to track each other
    tightly but are not literally the same instrument -- this is a real, small, undocumented-
    elsewhere BASIS RISK between our fair-value feed and Kalshi's actual settlement source.
  * Realized daily vol sigma_daily = sample stdev of trailing ~30 daily log returns (log(close_t
    / close_{t-1})), pulled from the same Yahoo daily-bar history. No GARCH, no vol smile, no
    term structure -- one flat trailing number.
  * Horizon: horizon_days = (market close_time - now) in CALENDAR days (not trading days --
    weekends/holidays are not stripped out of the countdown, so vol is mildly overstated for
    windows spanning a weekend). sigma_h = sigma_daily * sqrt(horizon_days).
  * Zero-drift lognormal normal approximation: ln(S_T) ~ Normal(ln(S0), sigma_h^2) (the Ito
    -1/2*sigma_h^2 convexity correction is deliberately omitted to keep this a literal "normal
    approximation" per the brief, not a full GBM SDE solution -- another small, documented bias).
  * fair_p("greater", floor) = Phi((ln(S0/floor)) / sigma_h)          [[settle > floor]]
    fair_p("less", cap)      = Phi(-(ln(S0/cap))  / sigma_h)          [[settle < cap]]
    fair_p("between")        = Phi(z_floor) - Phi(z_cap)              [[floor < settle < cap]]
    (Phi = standard normal CDF via math.erf; no scipy dependency.)

PRICE-SOURCE VERIFICATION (2026-07-12, from this sandbox):
  * Yahoo Finance chart API (query1.finance.yahoo.com/v8/finance/chart/CL=F) -- WORKS, used as
    primary. Gives a live quote (meta.regularMarketPrice) and daily OHLC history in one call.
  * stooq.com CSV endpoint -- FAILS from this sandbox (blocked behind a JS proof-of-work
    challenge page, not a real CSV response). Kept as a best-effort fallback in case the
    restriction is sandbox-specific and GH Actions runners see plain CSV.
  * FRED DCOILWTICO CSV -- FAILS from this sandbox (connection timeout). Kept as a last-resort
    fallback; also NB it is WTI spot (Cushing), not a futures/forward price, and typically
    lags 1 business day, so it is a materially worse fair-value proxy even when reachable.

  ============================================================================================
  PRE-REGISTERED BAR (same one used elsewhere in this repo, see edge_verdicts.py): this stream
  is NOT scoreable, and MUST NOT inform any live-trading decision, until it clears
    >= 14 forward calendar days of settled paper rows, AND
    day-clustered t >= 3.0 (mean day-P&L vs 0, stdev across day-means, sqrt(n_days) SE), AND
    positive on >= 80% of the days observed.
  Score with: python edge_verdicts.py score gha_data/kxwti_settled.csv
  ============================================================================================

Usage:
  python kxwti_paper.py [state_dir]      # default state_dir = gha_data
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import sys
import urllib.parse
import urllib.request

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXWTI"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1d&range=90d"
STOOQ_CSV = "https://stooq.com/q/d/l/?s=cl.f&i=d"          # fallback (blocked from sandbox; kept)
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO"  # fallback (timed out)

VOL_LOOKBACK = 30           # trailing trading days for realized-vol estimate
MIN_VOL_OBS = 15            # refuse to compute a fair value with fewer return observations
STALE_GRACE_RUNS = 5        # settlement-lookup grace before we give up on a vanished ticker


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now_utc()).isoformat(timespec="seconds")


def http_get(url, headers=None, timeout=20, retries=3):
    hdrs = {"User-Agent": "research"}
    hdrs.update(headers or {})
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:  # noqa: BLE001 -- deliberately broad, we retry+report
            last_exc = e
            if attempt < retries - 1:
                import time
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {retries} tries: {type(last_exc).__name__}: {last_exc}")


def kalshi_get(path, params=None):
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    return json.loads(http_get(f"{KALSHI_BASE}{path}{qs}"))


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------------------
# fair-value feed: WTI front-month futures price + trailing realized vol
# --------------------------------------------------------------------------------------------
def fetch_cl_yahoo():
    """Returns (spot, [daily closes oldest->newest], source_name) or raises."""
    raw = http_get(YAHOO_CHART, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(raw)
    result = (d.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError("yahoo: empty chart.result")
    r = result[0]
    meta = r.get("meta") or {}
    spot = fnum(meta.get("regularMarketPrice"))
    closes = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    closes = [fnum(c) for c in closes if fnum(c) is not None]
    if spot is None or len(closes) < MIN_VOL_OBS:
        raise RuntimeError(f"yahoo: insufficient data (spot={spot}, n_closes={len(closes)})")
    return spot, closes, "yahoo_CL=F"


def fetch_cl_stooq():
    """Fallback: stooq daily CSV. Documented as FAILING from this sandbox (JS PoW gate) --
    kept in case a GH Actions runner has plainer egress."""
    raw = http_get(STOOQ_CSV, headers={"User-Agent": "Mozilla/5.0"}).decode("utf-8", "replace")
    rows = list(csv.DictReader(raw.splitlines()))
    if not rows or "Close" not in rows[0]:
        raise RuntimeError("stooq: unexpected CSV shape (likely blocked/challenge page)")
    closes = [fnum(row["Close"]) for row in rows]
    closes = [c for c in closes if c is not None]
    if len(closes) < MIN_VOL_OBS:
        raise RuntimeError("stooq: insufficient rows")
    return closes[-1], closes, "stooq_CL.F"


def fetch_cl_fred():
    """Last-resort fallback: FRED DCOILWTICO (WTI Cushing spot, ~1 business day lag -- worse
    proxy even when reachable). Documented as FAILING (timeout) from this sandbox."""
    raw = http_get(FRED_CSV, headers={"User-Agent": "Mozilla/5.0"}).decode("utf-8", "replace")
    rows = list(csv.DictReader(raw.splitlines()))
    closes = []
    for row in rows:
        v = row.get("DCOILWTICO")
        f = fnum(v)
        if f is not None:
            closes.append(f)
    if len(closes) < MIN_VOL_OBS:
        raise RuntimeError("fred: insufficient rows")
    return closes[-1], closes, "fred_DCOILWTICO"


def get_cl_feed():
    errs = []
    for fn in (fetch_cl_yahoo, fetch_cl_stooq, fetch_cl_fred):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            errs.append(f"{fn.__name__}: {e}")
    raise RuntimeError("ALL CL price sources failed, refusing to fabricate a fair value:\n  "
                        + "\n  ".join(errs))


def realized_daily_vol(closes):
    """Sample stdev of trailing log returns over the last VOL_LOOKBACK+1 closes."""
    tail = closes[-(VOL_LOOKBACK + 1):]
    rets = [math.log(tail[i] / tail[i - 1]) for i in range(1, len(tail)) if tail[i - 1] > 0]
    if len(rets) < MIN_VOL_OBS:
        raise RuntimeError(f"only {len(rets)} log-return observations (<{MIN_VOL_OBS})")
    n = len(rets)
    mean = sum(rets) / n
    var = sum((x - mean) ** 2 for x in rets) / (n - 1)
    return math.sqrt(var), n


# --------------------------------------------------------------------------------------------
# fair-value model: normal approximation on log-price, zero drift
# --------------------------------------------------------------------------------------------
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def fair_prob(strike_type, floor_strike, cap_strike, s0, sigma_h):
    """P(settle crosses strike) under S_T ~ lognormal(ln(S0), sigma_h^2), zero drift."""
    if sigma_h <= 0:
        # at/after close: degenerate to an indicator on the current spot
        if strike_type == "greater" and floor_strike is not None:
            return 1.0 if s0 > floor_strike else 0.0
        if strike_type == "less" and cap_strike is not None:
            return 1.0 if s0 < cap_strike else 0.0
        return None
    if strike_type == "greater" and floor_strike is not None and floor_strike > 0:
        z = math.log(s0 / floor_strike) / sigma_h
        return norm_cdf(z)
    if strike_type == "less" and cap_strike is not None and cap_strike > 0:
        z = math.log(s0 / cap_strike) / sigma_h
        return norm_cdf(-z)
    if strike_type in ("between", "range") and floor_strike and cap_strike:
        z_lo = math.log(s0 / floor_strike) / sigma_h
        z_hi = math.log(s0 / cap_strike) / sigma_h
        return max(0.0, min(1.0, norm_cdf(z_lo) - norm_cdf(z_hi)))
    return None


# --------------------------------------------------------------------------------------------
# KXWTI ladder
# --------------------------------------------------------------------------------------------
def fetch_ladder():
    """All open KXWTI events with nested markets -> flat list of rung dicts."""
    events, cursor = [], ""
    for _ in range(10):
        params = {"series_ticker": SERIES, "status": "open", "limit": 50,
                  "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        d = kalshi_get("/events", params)
        events += d.get("events") or []
        cursor = d.get("cursor") or ""
        if not cursor:
            break
    rungs = []
    for ev in events:
        et = ev.get("event_ticker")
        for m in ev.get("markets") or []:
            if (m.get("status") or "").lower() != "active":
                continue
            yb, ya = fnum(m.get("yes_bid_dollars")), fnum(m.get("yes_ask_dollars"))
            if yb is None or ya is None or not (0 < yb < ya < 1):
                continue
            try:
                ct = dt.datetime.fromisoformat((m.get("close_time") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            rungs.append({
                "event_ticker": et, "ticker": m.get("ticker"),
                "strike_type": m.get("strike_type"),
                "floor_strike": fnum(m.get("floor_strike")), "cap_strike": fnum(m.get("cap_strike")),
                "close_time": ct, "yes_bid": yb, "yes_ask": ya,
                "yes_bid_size": fnum(m.get("yes_bid_size_fp")), "yes_ask_size": fnum(m.get("yes_ask_size_fp")),
                "volume": fnum(m.get("volume_fp")), "open_interest": fnum(m.get("open_interest_fp")),
                "title": (m.get("yes_sub_title") or m.get("title") or "")[:60],
            })
    return rungs


def fetch_market_result(ticker):
    try:
        m = kalshi_get(f"/markets/{ticker}").get("market") or {}
    except Exception:
        return None, None
    status = (m.get("status") or "").lower()
    result = (m.get("result") or "").lower()
    if status == "settled" and result in ("yes", "no"):
        return result, m
    return None, m


# --------------------------------------------------------------------------------------------
# state I/O
# --------------------------------------------------------------------------------------------
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path))
    except Exception:
        return default


def append_csv(path, row, fieldnames):
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerow(row)


SETTLED_FIELDS = ["settle_ts", "snap_ts", "ticker", "event_ticker", "side", "quote_price",
                   "fair_p_at_quote", "edge_at_quote", "result", "pnl_per_contract",
                   "sigma_daily_at_quote", "horizon_days_at_quote"]


def main():
    state_dir = sys.argv[1] if len(sys.argv) > 1 else "gha_data"
    os.makedirs(state_dir, exist_ok=True)
    today = now_utc().date().isoformat()
    jsonl_path = os.path.join(state_dir, f"kxwti_paper_{today}.jsonl")
    pending_path = os.path.join(state_dir, "kxwti_pending.json")
    settled_path = os.path.join(state_dir, "kxwti_settled.csv")

    now = now_utc()
    nowiso = iso(now)

    # ---------- 1+2. fair-value feed ----------
    s0, closes, cl_source = get_cl_feed()
    sigma_daily, n_rets = realized_daily_vol(closes)
    print(f"[{nowiso}] CL front-month feed={cl_source} S0={s0:.2f} "
          f"sigma_daily={sigma_daily:.4f} (n={n_rets} log-returns)")

    # ---------- 3. ladder + fair value per rung ----------
    rungs = fetch_ladder()
    print(f"[{nowiso}] KXWTI ladder: {len(rungs)} active rungs")

    ladder_lookup = {}
    jsonl_rows = []
    new_quotes = []
    for r in rungs:
        horizon_days = max((r["close_time"] - now).total_seconds(), 0.0) / 86400.0
        sigma_h = sigma_daily * math.sqrt(horizon_days) if horizon_days > 0 else 0.0
        fair_p = fair_prob(r["strike_type"], r["floor_strike"], r["cap_strike"], s0, sigma_h)
        mid = (r["yes_bid"] + r["yes_ask"]) / 2.0
        ladder_lookup[r["ticker"]] = {"yes_bid": r["yes_bid"], "yes_ask": r["yes_ask"]}
        row = {
            "ts": nowiso, "event_ticker": r["event_ticker"], "ticker": r["ticker"],
            "strike_type": r["strike_type"], "floor_strike": r["floor_strike"],
            "cap_strike": r["cap_strike"], "close_time": r["close_time"].isoformat(),
            "horizon_days": round(horizon_days, 4), "cl_source": cl_source,
            "s0": s0, "sigma_daily": round(sigma_daily, 5), "sigma_h": round(sigma_h, 5),
            "fair_p": round(fair_p, 4) if fair_p is not None else None,
            "yes_bid": r["yes_bid"], "yes_ask": r["yes_ask"], "mid": round(mid, 4),
            "yes_bid_size": r["yes_bid_size"], "yes_ask_size": r["yes_ask_size"],
            "volume": r["volume"], "open_interest": r["open_interest"], "title": r["title"],
        }
        if fair_p is not None:
            edge_bid = fair_p - r["yes_bid"]     # +EV to buy YES at the bid (join it)
            edge_ask = r["yes_ask"] - fair_p     # +EV to sell YES at the ask (join it)
            row["edge_bid"] = round(edge_bid, 4)
            row["edge_ask"] = round(edge_ask, 4)
            if edge_bid > 0:
                new_quotes.append({
                    "ticker": r["ticker"], "event_ticker": r["event_ticker"], "side": "bid",
                    "quote_price": r["yes_bid"], "snap_ts": nowiso,
                    "fair_p_at_quote": fair_p, "edge_at_quote": round(edge_bid, 4),
                    "sigma_daily_at_quote": round(sigma_daily, 5),
                    "horizon_days_at_quote": round(horizon_days, 4), "status": "resting",
                })
            if edge_ask > 0:
                new_quotes.append({
                    "ticker": r["ticker"], "event_ticker": r["event_ticker"], "side": "ask",
                    "quote_price": r["yes_ask"], "snap_ts": nowiso,
                    "fair_p_at_quote": fair_p, "edge_at_quote": round(edge_ask, 4),
                    "sigma_daily_at_quote": round(sigma_daily, 5),
                    "horizon_days_at_quote": round(horizon_days, 4), "status": "resting",
                })
        jsonl_rows.append(row)

    with open(jsonl_path, "a") as f:
        for row in jsonl_rows:
            f.write(json.dumps(row) + "\n")

    # ---------- 4/5/6. process pending quotes: fill-check + settle ----------
    pending = load_json(pending_path, [])
    still_pending = []
    filled_now = 0
    settled_now = 0
    expired_unfilled = 0
    result_cache = {}

    for q in pending:
        tk = q["ticker"]
        cur = ladder_lookup.get(tk)
        if q["status"] == "resting":
            if cur is not None:
                crossed = ((q["side"] == "bid" and cur["yes_ask"] <= q["quote_price"]) or
                           (q["side"] == "ask" and cur["yes_bid"] >= q["quote_price"]))
                if crossed:
                    q["status"] = "filled"
                    q["filled_ts"] = nowiso
                    filled_now += 1
                still_pending.append(q)
                continue
            # rung dropped out of the open ladder -- settled, closed early, or delisted
            if tk not in result_cache:
                result_cache[tk] = fetch_market_result(tk)
            result, _m = result_cache[tk]
            if result is None:
                q["stale_runs"] = q.get("stale_runs", 0) + 1
                if q["stale_runs"] < STALE_GRACE_RUNS:
                    still_pending.append(q)
                # else: give up silently, never filled, nothing to score
                else:
                    expired_unfilled += 1
                continue
            # never filled before settlement -- no exposure, no P&L row, just drop it
            expired_unfilled += 1
            continue
        else:  # status == "filled", waiting on settlement
            if cur is not None:
                still_pending.append(q)   # still open, keep waiting
                continue
            if tk not in result_cache:
                result_cache[tk] = fetch_market_result(tk)
            result, _m = result_cache[tk]
            if result is None:
                q["stale_runs"] = q.get("stale_runs", 0) + 1
                if q["stale_runs"] < STALE_GRACE_RUNS:
                    still_pending.append(q)
                continue
            settle_yes = 1.0 if result == "yes" else 0.0
            if q["side"] == "bid":
                pnl = settle_yes - q["quote_price"]          # long YES at quote_price
            else:
                pnl = q["quote_price"] - settle_yes           # short YES at quote_price
            append_csv(settled_path, {
                "settle_ts": nowiso, "snap_ts": q["snap_ts"], "ticker": tk,
                "event_ticker": q["event_ticker"], "side": q["side"],
                "quote_price": round(q["quote_price"], 4),
                "fair_p_at_quote": round(q["fair_p_at_quote"], 4),
                "edge_at_quote": round(q["edge_at_quote"], 4), "result": result,
                "pnl_per_contract": round(pnl, 4),
                "sigma_daily_at_quote": q.get("sigma_daily_at_quote"),
                "horizon_days_at_quote": q.get("horizon_days_at_quote"),
            }, SETTLED_FIELDS)
            settled_now += 1

    still_pending += new_quotes
    json.dump(still_pending, open(pending_path, "w"), indent=0)

    # ---------- 7. compact run summary ----------
    n_edge_rows = sum(1 for r in jsonl_rows if r.get("fair_p") is not None)
    print(f"[{nowiso}] fair-value computed for {n_edge_rows}/{len(jsonl_rows)} rungs | "
          f"new quotes {len(new_quotes)} | filled-this-run {filled_now} | "
          f"settled-this-run {settled_now} | expired-unfilled {expired_unfilled} | "
          f"pending now {len(still_pending)}")

    if os.path.exists(settled_path):
        n = tot = wins = 0
        for row in csv.DictReader(open(settled_path)):
            n += 1
            tot += float(row["pnl_per_contract"])
            wins += float(row["pnl_per_contract"]) > 0
        if n:
            print(f"  CUMULATIVE paper harvest: n={n}  mean P&L={tot / n * 100:+.2f}c/contract  "
                  f"win rate={wins / n:.3f}  total={tot * 100:+.1f}c (per 1-contract clip)")
    else:
        print("  no settled paper positions yet (first runs only snapshot+quote; "
              "edge accrues as rungs settle)")


if __name__ == "__main__":
    main()
