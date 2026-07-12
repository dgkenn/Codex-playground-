#!/usr/bin/env python3
"""macro_paper.py -- FORWARD paper-track of a CPI/Fed-decision event-market sleeve on Kalshi.

WHY THIS SLEEVE (see VENUE_SCAN.md): the Kalshi macro-event ladders (KXCPIYOY, KXCPICOREYOY,
KXFEDDECISION) have the WIDEST spreads on the venue (~47-53 ticks on the thin rungs) and low
volume -- high edge-per-fill IF a fair-value anchor beats the market, monthly/8x-per-year
cadence, capacity-capped by construction. This script tests exactly that, out of sample, with
real money nowhere near it (PAPER ONLY, public read-only APIs, no auth).

DATA SOURCES USED (verified reachable from this sandbox on 2026-07-12; re-verify periodically --
data vendors change endpoints without notice):
  1. Kalshi public REST (no auth): https://api.elections.kalshi.com/trade-api/v2
     /markets (ladder discovery), /markets/{ticker}/orderbook (touch), /markets/{ticker}
     (settlement poll). Same idiom as kalshi_macro_snap.py / kalshi_longshot_paper.py.
  2. Cleveland Fed Inflation Nowcasting -- CPI/core-CPI YoY anchor.
     https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_year.json?sc_lang=en
     This is the RAW JSON feed backing the FusionCharts widget embedded in
     https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting (found by curling the
     page and reading its `data-data-config` attributes -- there is no documented public API,
     but this file IS the one the live page fetches, updated daily on Cleveland Fed business
     days). It is a list of ~157 monthly chart snapshots; we take the one with the latest
     `chart._comment` date and read the last non-blank value of the "CPI Inflation" / "Core CPI
     Inflation" series (YoY, %). Confirmed working: as of the 2026-07-10 vintage it read
     CPI YoY=3.71%, core CPI YoY=2.81%.
  3. NY Fed reference rates -- current EFFR + target range (the "rate_before" anchor for Fed
     decisions). https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json
     Official, free, no key. Confirmed working: returns {percentRate, targetRateFrom,
     targetRateTo, effectiveDate}.
  4. CBOT 30-Day Fed Funds futures (ZQ) -- the "rate_after" anchor for Fed decisions.
     CME's own FedWatch API is PAID ($25+/mo) and CME's website returns HTTP 403
     ("blocked due to suspected web scraping") to a plain curl -- confirmed unreachable/
     disallowed from this sandbox, so it is NOT used. stooq.com's CSV endpoint is behind a
     JS proof-of-work challenge -- confirmed unreachable via curl. Per-contract-month ZQ
     prices ARE reachable, unauthenticated, via Yahoo Finance's chart API using CBOT month-code
     symbols (e.g. ZQQ26.CBT = August 2026): confirmed working, contracts discovered via
     https://query1.finance.yahoo.com/v1/finance/search?q=30%20Day%20Federal%20Funds%20Futures
     Fetched here directly via https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}
     using the standard CME month-code map (F,G,H,J,K,M,N,Q,U,V,X,Z = Jan..Dec).
  5. FOMC 2026 meeting calendar -- hardcoded from
     https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (fetched 2026-07-12):
     Jan27-28, Mar17-18, Apr28-29, Jun16-17, Jul28-29, Sep15-16, Oct27-28, Dec8-9.
     MUST be extended by hand once 2027 dates are published, or the Fed anchor silently stops
     (the script prints a clear WARN and skips FEDDECISION rather than guessing).

FED-DECISION ANCHOR METHODOLOGY (an approximation of CME's own "meeting probability" technique,
NOT a reimplementation of it -- differences called out explicitly):
  rate_before = today's EFFR print (NY Fed, source #3).
  rate_after  = 100 - ZQ futures price for the nearest "PURE" calendar month after the meeting
                month, i.e. the nearest following month that itself contains NO FOMC meeting, so
                its ZQ contract's implied average rate is (to first order) just the post-decision
                rate with no within-month blending to undo. If more than one meeting falls between
                the target meeting and that pure month ("gap_meetings" > 0 -- doesn't happen in
                the 2026 calendar's normal cadence but CAN happen around back-to-back meeting
                months like Jun->Jul), the anchor conflates >1 meeting's worth of expectation and
                we DO NOT TRADE it (would_trade_side forced to None, reason logged) -- we still
                log it for visibility.
  delta = rate_after - rate_before, converted to a fractional number of 25bp steps and split
  by LINEAR interpolation between the two adjacent integer step levels (standard practitioner
  approximation of a meeting-probability extraction; CME's own tool additionally does exact
  day-count blending WITHIN the meeting month itself, which we skip by construction since we
  read a pure month instead). Levels <= -2 lump into the "Cut >25bps" bucket and >= +2 into
  "Hike >25bps" bucket to match Kalshi's actual KXFEDDECISION 5-way partition (ticker suffixes
  C26/C25/H0/H25/H26, confirmed by fetching the live market list).

CPI/CORE-CPI ANCHOR METHODOLOGY: KXCPIYOY / KXCPICOREYOY are "value above X" threshold ladders
(confirmed via kalshi_macro_snap.py's book-parsing idiom, reused here). anchor_prob(above X) =
P(nowcast > X) using a Normal(nowcast, SIGMA_CPI) survival function. SIGMA_CPI is a FIXED,
DOCUMENTED PLACEHOLDER (0.15 pp), NOT fitted to Cleveland Fed's own published nowcast RMSE
tables (not fetched here) and NOT fitted to match the market (that would be circular and would
destroy the point of an independent anchor). Treat it as a first-pass assumption to be
sharpened later, not a claimed number.

PRE-REGISTERED BAR (set BEFORE looking at any settled result; printed every run so it can't
drift): CPI and FOMC-decision events happen roughly MONTHLY (CPI) / 8x/year (FOMC) -- the
generic edge_verdicts.py bar of ">=14 forward days" is a category error for this stream (14
days is less than one event; day-count says nothing about statistical power here). Instead:
    >= 6 settled EVENTS (rungs from separate event-months, not separate days -- ~6 months of
       CPI prints, or a mix of CPI+FOMC settlements) AND
    aggregate paper P&L t-statistic >= 2.0 across those settled events (using per-settled-row
       pnl as the unit of observation; rows within one event-close_time are correlated the same
       way rows-within-a-day are in edge_verdicts.py, but distinct rungs of the SAME ladder
       settle simultaneously off one true outcome, so in practice each settled EVENT contributes
       several correlated rows -- the local_verdict() helper below reports both the naive t on
       all settled rows and n_events as a separate count so this can't be misread as day-level
       power it doesn't have).
No live consideration before both bars clear. This is a LOWER statistical bar than
edge_verdicts.py's default (t>=3, 80% positive days) precisely because the event count here is
inherently small -- reaching t=3 would require years of monthly cadence. t>=2 is a deliberately
softer, honestly-labeled placeholder-of-interest, not a claim of robustness.

State (persists across runs, meant to live on the gha-data branch like kalshi_longshot_paper.py):
  <data_dir>/macro_pending.json         -- open paper positions awaiting settlement
  <data_dir>/macro_settled.jsonl        -- realized P&L, ONE JSON object per line with a "date"
                                            and "pnl" key -- directly readable by
                                            `python edge_verdicts.py score <path>` (kind=auto
                                            falls through to the generic loader, which
                                            autodetects "date"/"pnl" columns; no --date-col/
                                            --value-col flags needed). See local_verdict() below
                                            for the bar that actually governs this stream, though
                                            (edge_verdicts.py's generic day-count bar undersells
                                            an inherently monthly-cadence stream).
  <data_dir>/macro_paper_<UTC date>.jsonl -- today's full snapshot: one meta row (sources/anchors
                                            used) + one row per rung scanned {ticker, rung,
                                            market_bid/ask/mid, anchor_prob, edge, spread_cost,
                                            would_trade_side}, regardless of whether a paper
                                            trade was triggered.

Usage: python macro_paper.py [data_dir]     (data_dir defaults to "gha_data")
Public APIs only, no auth, READ-ONLY against Kalshi, PAPER ONLY -- no money moves.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
import datetime as dt

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
CF_NOWCAST_URL = ("https://www.clevelandfed.org/-/media/files/webcharts/"
                   "inflationnowcasting/nowcast_year.json?sc_lang=en")
NYFED_EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"

# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (fetched 2026-07-12).
# EXTEND THIS by hand once later years are published -- the script will not guess.
FOMC_MEETINGS_2026 = [
    ("2026-01-27", "2026-01-28"),
    ("2026-03-17", "2026-03-18"),
    ("2026-04-28", "2026-04-29"),
    ("2026-06-16", "2026-06-17"),
    ("2026-07-28", "2026-07-29"),
    ("2026-09-15", "2026-09-16"),
    ("2026-10-27", "2026-10-28"),
    ("2026-12-08", "2026-12-09"),
]

# CME/CBOT futures month-code map.
MCODE = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
         7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}

SIGMA_CPI = 0.15   # pp, FIXED PLACEHOLDER assumption -- see module docstring. NOT fitted.
FED_STEP = 0.25    # standard FOMC move increment, %
FEE_MULT = 0.07    # standard quadratic taker-fee schedule (kalshi_macro_snap.py)
STALE_DAYS = 60    # drop a pending paper position if it hasn't settled within this many days


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


# --------------------------------------------------------------------------------------
# generic HTTP helper (stdlib only -- no pip install step in the workflow)
# --------------------------------------------------------------------------------------
def http_get_json(url, tries=4):
    hdrs = {"User-Agent": "Mozilla/5.0 (research; macro_paper.py)"}
    last_err = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (a + 1))
    eprint(f"[macro_paper] WARN: failed to fetch {url}: {last_err}")
    return None


def kalshi_get(path, **params):
    url = KALSHI_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return http_get_json(url)


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def fee(p):
    if p is None or not (0 <= p <= 1):
        return 0.0
    return math.ceil(FEE_MULT * p * (1 - p) * 100) / 100


def norm_cdf(x, mu, sigma):
    if sigma is None or sigma <= 0:
        return 1.0 if x < mu else (0.5 if x == mu else 0.0)
    z = (x - mu) / (sigma * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


# --------------------------------------------------------------------------------------
# anchor #1: Cleveland Fed inflation nowcast
# --------------------------------------------------------------------------------------
def fetch_cleveland_nowcast():
    data = http_get_json(CF_NOWCAST_URL)
    if not isinstance(data, list):
        return None
    items = [it for it in data if isinstance(it, dict) and "chart" in it]
    if not items:
        return None
    items.sort(key=lambda it: it["chart"].get("_comment", ""))
    latest = items[-1]
    try:
        labels = [c.get("label") for c in latest["categories"][0]["category"]]
    except Exception:
        labels = []
    out, asof_label = {}, None
    for ds in latest.get("dataset", []):
        name = ds.get("seriesname", "")
        vals = [p.get("value") for p in ds.get("data", [])]
        for i in range(len(vals) - 1, -1, -1):
            if vals[i] not in (None, ""):
                try:
                    out[name] = float(vals[i])
                    if i < len(labels):
                        asof_label = labels[i]
                except (TypeError, ValueError):
                    pass
                break
    if not out:
        return None
    return {
        "cpi_yoy": out.get("CPI Inflation"),
        "core_cpi_yoy": out.get("Core CPI Inflation"),
        "pce_yoy": out.get("PCE Inflation"),
        "core_pce_yoy": out.get("Core PCE Inflation"),
        "asof_label": asof_label,
        "chart_vintage": latest["chart"].get("_comment"),
        "source_url": CF_NOWCAST_URL,
    }


# --------------------------------------------------------------------------------------
# anchor #2: NY Fed EFFR (rate_before) + ZQ futures (rate_after) -> Fed-decision anchor
# --------------------------------------------------------------------------------------
def fetch_nyfed_effr():
    data = http_get_json(NYFED_EFFR_URL)
    try:
        r = data["refRates"][0]
    except Exception:
        return None
    return {
        "effr": fnum(r.get("percentRate")),
        "target_lo": fnum(r.get("targetRateFrom")),
        "target_hi": fnum(r.get("targetRateTo")),
        "asof": r.get("effectiveDate"),
        "source_url": NYFED_EFFR_URL,
    }


def zq_symbol(year, month):
    return f"ZQ{MCODE[month]}{str(year)[-2:]}.CBT"


def fetch_zq_price(year, month):
    sym = zq_symbol(year, month)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    data = http_get_json(url)
    try:
        meta = data["chart"]["result"][0]["meta"]
        return fnum(meta.get("regularMarketPrice")), sym, url
    except Exception:
        return None, sym, url


def _has_meeting(year, month):
    return any(dt.date.fromisoformat(lo).year == year and dt.date.fromisoformat(lo).month == month
               for lo, hi in FOMC_MEETINGS_2026)


def next_meeting(today: dt.date):
    for lo, hi in FOMC_MEETINGS_2026:
        d1 = dt.date.fromisoformat(hi)
        if d1 >= today:
            return dt.date.fromisoformat(lo), d1
    return None, None


def compute_fed_anchor(today: dt.date):
    m0, m1 = next_meeting(today)
    if m0 is None:
        eprint("[macro_paper] WARN: no FOMC meeting >= today in the embedded 2026 calendar -- "
               "extend FOMC_MEETINGS_2026. Skipping Fed anchor.")
        return None
    y, mo = m1.year, m1.month
    pure, gap = None, None
    for step in range(1, 4):
        y2, mo2 = y, mo + step
        while mo2 > 12:
            mo2 -= 12
            y2 += 1
        if not _has_meeting(y2, mo2):
            pure, gap = (y2, mo2), step - 1
            break
    if pure is None:
        eprint("[macro_paper] WARN: no pure (meeting-free) month found within 3 months of the "
               "next FOMC meeting -- skipping Fed anchor.")
        return None
    price, sym, src = fetch_zq_price(*pure)
    if price is None:
        eprint(f"[macro_paper] WARN: ZQ fetch failed for {sym} -- skipping Fed anchor.")
        return None
    effr = fetch_nyfed_effr()
    if effr is None or effr.get("effr") is None:
        eprint("[macro_paper] WARN: NY Fed EFFR fetch failed -- skipping Fed anchor.")
        return None
    rate_after = 100.0 - price
    rate_before = effr["effr"]
    delta = rate_after - rate_before
    return {
        "meeting_start": m0.isoformat(), "meeting_end": m1.isoformat(),
        "rate_before": rate_before, "rate_after": rate_after, "delta": round(delta, 4),
        "pure_month": f"{pure[0]:04d}-{pure[1]:02d}", "gap_meetings": gap,
        "zq_symbol": sym, "zq_price": price, "zq_source_url": src,
        "effr": effr,
    }


def interp_fed_probs(delta, step=FED_STEP):
    """Split the implied fractional 25bp move between the two adjacent discrete levels by
    linear interpolation (see module docstring for what this does and doesn't replicate of
    CME's own methodology), then bucket into Kalshi's actual 5-way KXFEDDECISION partition."""
    n = delta / step
    lower = math.floor(n)
    frac = n - lower
    upper = lower + 1
    mass = {lower: 1 - frac, upper: frac}
    buckets = {"C26": 0.0, "C25": 0.0, "H0": 0.0, "H25": 0.0, "H26": 0.0}
    for lvl, p in mass.items():
        if lvl <= -2:
            buckets["C26"] += p
        elif lvl == -1:
            buckets["C25"] += p
        elif lvl == 0:
            buckets["H0"] += p
        elif lvl == 1:
            buckets["H25"] += p
        else:
            buckets["H26"] += p
    return buckets


# --------------------------------------------------------------------------------------
# Kalshi ladder plumbing (idiom shared with kalshi_macro_snap.py)
# --------------------------------------------------------------------------------------
def book(ticker):
    ob = (kalshi_get(f"/markets/{ticker}/orderbook", depth=30) or {}).get("orderbook_fp", {}) or {}
    yes = [(fnum(p), fnum(q)) for p, q in (ob.get("yes_dollars") or [])]
    no = [(fnum(p), fnum(q)) for p, q in (ob.get("no_dollars") or [])]
    yb = max((p for p, _ in yes if p is not None), default=None)
    nb = max((p for p, _ in no if p is not None), default=None)
    ya = (1 - nb) if nb is not None else None
    return yb, ya


def nearest_event(series):
    ms = (kalshi_get("/markets", series_ticker=series, status="open", limit=200) or {}).get("markets", []) or []
    ms = [m for m in ms if m.get("close_time")]
    if not ms:
        return None, []
    ms.sort(key=lambda m: m["close_time"])
    ct = ms[0]["close_time"]
    return ct, [m for m in ms if m["close_time"] == ct]


def mk_row(series, ticker, rung, close_time, yb, ya, anchor_p):
    mid = (yb + ya) / 2 if (yb is not None and ya is not None) else (yb if yb is not None else ya)
    spr = (ya - yb) if (yb is not None and ya is not None) else None
    row = {
        "series": series, "ticker": ticker, "rung": rung, "close_time": close_time,
        "market_bid": yb, "market_ask": ya, "market_mid": round(mid, 4) if mid is not None else None,
        "spread": round(spr, 4) if spr is not None else None,
        "anchor_prob": round(anchor_p, 4) if anchor_p is not None else None,
        "would_trade_side": None,
    }
    if anchor_p is None or mid is None:
        row["would_trade_reason"] = "anchor unavailable" if anchor_p is None else "no book"
        return row
    if spr is None:
        row["would_trade_reason"] = "one-sided book, no spread available"
        return row
    edge = anchor_p - mid
    cost = spr / 2 + fee(mid)
    row["edge"] = round(edge, 4)
    row["spread_cost"] = round(cost, 4)
    if edge > cost:
        row["would_trade_side"] = "YES"
        row["entry_price"] = ya
    elif -edge > cost:
        row["would_trade_side"] = "NO"
        row["entry_price"] = round(1 - yb, 4)
    return row


def process_cpi_series(series, nowcast_value, label):
    rows = []
    ct, grp = nearest_event(series)
    if not grp:
        return rows
    for m in grp:
        x = m.get("floor_strike")
        if x is None:
            continue
        yb, ya = book(m["ticker"])
        anchor_p = (1 - norm_cdf(x, nowcast_value, SIGMA_CPI)) if nowcast_value is not None else None
        row = mk_row(series, m["ticker"], f"above {x}", ct, yb, ya, anchor_p)
        row["anchor_label"] = label
        row["anchor_x"] = x
        rows.append(row)
    return rows


def process_fed_series(series, fed_anchor):
    rows = []
    ct, grp = nearest_event(series)
    if not grp:
        return rows
    buckets = interp_fed_probs(fed_anchor["delta"]) if fed_anchor else {}
    contaminated = bool(fed_anchor and fed_anchor.get("gap_meetings", 0) > 0)
    for m in grp:
        suf = m["ticker"].split("-")[-1]
        anchor_p = buckets.get(suf) if fed_anchor else None
        yb, ya = book(m["ticker"])
        row = mk_row(series, m["ticker"], suf, ct, yb, ya, anchor_p)
        row["anchor_label"] = "ZQ futures + NY Fed EFFR (approx. meeting-probability extraction)"
        if contaminated and row["would_trade_side"]:
            row["would_trade_side"] = None
            row["would_trade_reason"] = (
                f"anchor spans gap_meetings={fed_anchor['gap_meetings']} intervening FOMC "
                f"meeting(s) before reaching a pure ZQ month -- not trading a contaminated anchor")
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------
# settlement scorer local to this stream (see module docstring for why the bar differs
# from edge_verdicts.py's generic 14-forward-day bar)
# --------------------------------------------------------------------------------------
def local_verdict(settled_path, min_events=6, t_bar=2.0):
    pnls = []
    if os.path.exists(settled_path):
        with open(settled_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    pnls.append(float(d["pnl"]))
                except Exception:
                    continue
    n = len(pnls)
    out = {"n_settled_rows": n, "min_events_bar": min_events, "t_bar": t_bar}
    if n == 0:
        out.update(verdict="WAIT", reason="0 settled rows yet")
        return out
    mean = statistics.mean(pnls)
    sd = statistics.stdev(pnls) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = mean / se if se and se > 0 else float("nan")
    out.update(mean_pnl=round(mean, 4), stdev=round(sd, 4), t=(round(t, 2) if not math.isnan(t) else None))
    if n < min_events:
        out.update(verdict="WAIT", reason=f"only {n} settled rows (<{min_events} settled EVENTS required "
                                           f"-- note rows != events when a ladder has multiple triggered rungs)")
    elif not math.isnan(t) and t >= t_bar:
        out.update(verdict="PASS (bar cleared -- still requires manual review before any live step)",
                   reason=f"t={t:.2f}>={t_bar}")
    else:
        tt = f"{t:.2f}" if not math.isnan(t) else "n/a"
        out.update(verdict="FAIL", reason=f"t={tt} (need >={t_bar})")
    return out


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------
def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "gha_data"
    os.makedirs(data_dir, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    nowiso = now.isoformat(timespec="seconds")
    date_str = now.date().isoformat()

    nowcast = fetch_cleveland_nowcast()
    if nowcast is None:
        eprint("[macro_paper] WARN: Cleveland Fed nowcast unreachable this run -- CPI/core-CPI "
               "rungs will log with anchor_prob=None (no trades on them).")
    fed_anchor = compute_fed_anchor(now.date())

    rows = []
    rows += process_cpi_series("KXCPIYOY", nowcast.get("cpi_yoy") if nowcast else None,
                                "Cleveland Fed nowcast, CPI YoY")
    rows += process_cpi_series("KXCPICOREYOY", nowcast.get("core_cpi_yoy") if nowcast else None,
                                "Cleveland Fed nowcast, core CPI YoY")
    rows += process_fed_series("KXFEDDECISION", fed_anchor)

    # ---------- write today's snapshot (meta + all scanned rungs) ----------
    snap_path = os.path.join(data_dir, f"macro_paper_{date_str}.jsonl")
    with open(snap_path, "a") as f:
        f.write(json.dumps({
            "type": "meta", "date": date_str, "ts": nowiso,
            "cleveland_fed_nowcast": nowcast, "fed_anchor": fed_anchor,
            "sigma_cpi_assumption": SIGMA_CPI,
        }, default=str) + "\n")
        for r in rows:
            r2 = dict(r)
            r2["date"] = date_str
            f.write(json.dumps(r2, default=str) + "\n")

    # ---------- settle matured pendings, then add new paper positions ----------
    pend_path = os.path.join(data_dir, "macro_pending.json")
    settled_path = os.path.join(data_dir, "macro_settled.jsonl")
    pending = []
    if os.path.exists(pend_path):
        try:
            pending = json.load(open(pend_path))
        except Exception:
            pending = []

    still, n_settled = [], 0
    for p in pending:
        m = (kalshi_get(f"/markets/{p['ticker']}") or {}).get("market") or {}
        status = (m.get("status") or "").lower()
        result = (m.get("result") or "").lower()
        if status == "settled" and result in ("yes", "no"):
            win = 1.0 if result == p["side"].lower() else 0.0
            pnl = win - p["entry_price"] - fee(p["entry_price"])
            with open(settled_path, "a") as f:
                f.write(json.dumps({
                    "date": now.date().isoformat(), "settle_ts": nowiso, "snap_ts": p["ts"],
                    "ticker": p["ticker"], "series": p["series"], "rung": p["rung"],
                    "side": p["side"], "entry_price": p["entry_price"], "result": result,
                    "pnl": round(pnl, 4),
                }) + "\n")
            n_settled += 1
        else:
            try:
                age_days = (now - dt.datetime.fromisoformat(p["ts"])).days
            except Exception:
                age_days = 0
            if age_days <= STALE_DAYS:
                still.append(p)
    pending = still

    have = {p["ticker"] for p in pending}
    n_added = 0
    for r in rows:
        side = r.get("would_trade_side")
        if side and r["ticker"] not in have:
            pending.append({
                "ticker": r["ticker"], "series": r["series"], "rung": r["rung"], "side": side,
                "entry_price": r["entry_price"], "ts": nowiso, "close_time": r.get("close_time"),
                "anchor_prob_at_entry": r.get("anchor_prob"), "edge_at_entry": r.get("edge"),
            })
            have.add(r["ticker"])
            n_added += 1
    json.dump(pending, open(pend_path, "w"), indent=0)

    # ---------- report ----------
    print(f"[{nowiso}] macro_paper: scanned {len(rows)} rungs across KXCPIYOY/KXCPICOREYOY/"
          f"KXFEDDECISION | settled {n_settled} new | opened {n_added} new paper position(s) | "
          f"pending now {len(pending)}")
    if nowcast:
        print(f"  Cleveland Fed nowcast ({nowcast.get('chart_vintage')}, asof {nowcast.get('asof_label')}): "
              f"CPI YoY={nowcast.get('cpi_yoy'):.3f}%  core CPI YoY={nowcast.get('core_cpi_yoy'):.3f}%  "
              f"[{nowcast.get('source_url')}]")
    else:
        print("  Cleveland Fed nowcast: UNREACHABLE this run")
    if fed_anchor:
        print(f"  Fed anchor: EFFR(before)={fed_anchor['rate_before']:.3f}%  "
              f"ZQ-implied(after, {fed_anchor['zq_symbol']} pure month {fed_anchor['pure_month']})="
              f"{fed_anchor['rate_after']:.3f}%  delta={fed_anchor['delta']:+.3f}pp  "
              f"gap_meetings={fed_anchor['gap_meetings']}")
    else:
        print("  Fed anchor: UNREACHABLE/unavailable this run")
    n_trig = sum(1 for r in rows if r.get("would_trade_side"))
    print(f"  rungs with a triggered edge today: {n_trig}/{len(rows)}")
    for r in rows:
        if r.get("would_trade_side"):
            print(f"    {r['series']} {r['rung']}: mid={r['market_mid']} anchor={r['anchor_prob']} "
                  f"edge={r['edge']:+.3f} cost={r['spread_cost']:.3f} -> {r['would_trade_side']} "
                  f"@ {r['entry_price']}")

    v = local_verdict(settled_path)
    print(f"  PRE-REGISTERED BAR: >={v['min_events_bar']} settled events AND t>={v['t_bar']} "
          f"(see module docstring for why the event-count, not day-count, bar applies here)")
    print(f"  current: n_settled_rows={v['n_settled_rows']}  "
          f"{'mean_pnl=%+.4f t=%s ' % (v['mean_pnl'], v['t']) if v['n_settled_rows'] else ''}"
          f"VERDICT={v['verdict']} ({v['reason']})")
    print("  score anytime with: python edge_verdicts.py score "
          f"{settled_path} --kind generic")


if __name__ == "__main__":
    main()
