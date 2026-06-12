"""kalshi_thin_collect.py -- shadow collector for the THIN/NEW-MARKET MAKER and FAVORITE-BAND MAKER
prospective tests (KALSHI_GOLD_CANDIDATES.md #4 and #1; the $1000-stage diversification legs).

WHAT IT DOES. Each discovery cycle it scans open Kalshi markets (excluding our crypto-15m/ladder
series) for the maker-relevant universe: two-sided books, mid in [0.05,0.95], spread >= 3c (wide
enough to pay a maker), LOW 24h volume (the documented volume-conditional mispricing regime, with
recently-opened markets flagged). It tracks the best ~40 and snapshots their top-of-book + last +
volume every poll. SCORING happens offline (a box_policy_ab-style scorer, once data accumulates):
paper-rest quotes at the recorded touch, infer fills from later last_price/volume prints, hold to
settlement/markout -- the SAME prospective standard as the crypto A/B. No orders, no auth, no money.

    python kalshi_thin_collect.py [duration_s] [out_dir] [tag]
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
EXCLUDE_PREF = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M",     # our box engine's turf
                "KXBTCD", "KXETHD", "KXINXU", "KXNASDAQ100U",       # the ladder collector's turf
                "KXMVE")     # auto-generated multivariate/parlay combos: dead books, no organic flow
DISCOVER_S = 600.0      # re-scan the universe every 10 min (new listings get caught here)
POLL_S = 60.0           # snapshot cadence for tracked markets (thin markets move slowly)
N_TRACK = 40
MIN_SPREAD = 0.03
MAX_SPREAD = 0.35       # wider = an EMPTY book, not a thin one; nobody crosses 90c
MAX_VOL24 = 5000.0      # contracts -- the "informed flow hasn't arrived" proxy
MIN_LIFE = 5.0          # require oi or vol >= this: somebody real holds/trades it
N_PAGES = 12            # KXMVE parlay combos flood the listing pages; scan deep to reach real events


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mfields(m):
    """Normalize across legacy and *_dollars/_fp field generations."""
    bid = f(m.get("yes_bid_dollars")) or (f(m.get("yes_bid")) or 0) / 100.0 or None
    ask = f(m.get("yes_ask_dollars")) or (f(m.get("yes_ask")) or 0) / 100.0 or None
    last = f(m.get("last_price_dollars")) or (f(m.get("last_price")) or 0) / 100.0 or None
    vol = f(m.get("volume_24h_fp")) or f(m.get("volume_24h")) or 0.0
    oi = f(m.get("open_interest_fp")) or f(m.get("open_interest")) or 0.0
    return bid, ask, last, vol, oi


CATEGORIES = ("Politics", "Economics", "Companies", "Financials", "Climate and Weather",
              "Entertainment", "World", "Science and Technology")
SERIES_PER_CYCLE = 40    # probe this many series per discovery cycle (round-robin -> full coverage)


def list_series(sess):
    """Category -> non-parlay series tickers. The /markets listing is FLOODED by auto-generated
    KXMVE parlays (2400+ on the first 12 pages), so discovery must go category->series->markets."""
    out = []
    for cat in CATEGORIES:
        try:
            d = sess.get(f"{B}/series", params={"category": cat}, timeout=12).json()
            for s in d.get("series") or []:
                tk = s.get("ticker", "")
                if tk and not any(tk.startswith(p) for p in EXCLUDE_PREF):
                    out.append(tk)
        except Exception:
            pass
        time.sleep(0.2)
    return out


def probe_series(sess, series_list):
    """One /markets call per series -> thin two-sided wide-spread candidates."""
    cand = []
    for st in series_list:
        try:
            d = sess.get(f"{B}/markets", params={"series_ticker": st, "status": "open",
                                                 "limit": 100}, timeout=10).json()
        except Exception:
            continue
        for m in d.get("markets") or []:
            tk = m.get("ticker", "")
            bid, ask, last, vol, oi = mfields(m)
            if bid is None or ask is None or not (0.05 <= (bid + ask) / 2 <= 0.95):
                continue
            spread = ask - bid
            if not (MIN_SPREAD <= spread <= MAX_SPREAD) or vol > MAX_VOL24:
                continue
            if max(vol, oi) < MIN_LIFE:
                continue                                 # zero-life book: no counterparty to make for
            cand.append({"tk": tk, "event": m.get("event_ticker"), "spread": round(spread, 3),
                         "vol24": vol, "oi": oi, "open": m.get("open_time"),
                         "close": m.get("close_time")})
        time.sleep(0.2)
    # widest spread x lowest volume first (the mispricing sweet spot)
    cand.sort(key=lambda c: (-c["spread"], c["vol24"]))
    return cand


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"tn{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, f"thin_mkts_{tag}.jsonl.gz")
    fh = gzip.open(fp, "at")
    sess = requests.Session()
    end = time.time() + dur
    tracked, last_disc = [], 0.0
    all_series, rot = [], 0
    print(f"thin_collect: {dur}s -> {fp}", flush=True)
    while time.time() < end:
        t0 = time.time()
        if t0 - last_disc > DISCOVER_S or not tracked:
            try:
                if not all_series:
                    all_series = list_series(sess)
                    print(f"series catalogue: {len(all_series)} non-parlay series", flush=True)
                batch = [all_series[(rot + i) % len(all_series)] for i in range(SERIES_PER_CYCLE)]
                rot = (rot + SERIES_PER_CYCLE) % max(len(all_series), 1)
                new = probe_series(sess, batch)
                # merge: keep already-tracked (stickiness for time-series continuity) + best new
                seen = {c["tk"] for c in tracked}
                tracked = (tracked + [c for c in new if c["tk"] not in seen])[:N_TRACK]
                last_disc = t0
                fh.write(json.dumps({"t": round(t0, 1), "type": "universe",
                                     "n": len(tracked), "markets": tracked}) + "\n")
                print(f"universe: {len(tracked)} tracked (+{len(new)} candidates this cycle)", flush=True)
            except Exception as e:
                print(f"discover ERR {str(e)[:60]}", flush=True)
        # snapshot tracked markets in batches via the per-series endpoint? cheapest correct way:
        # one GET per market ticker (tracked <= 40, 60s cadence -> well under rate limits)
        for c in tracked:
            try:
                d = sess.get(f"{B}/markets/{c['tk']}", timeout=8).json().get("market", {})
                bid, ask, last, vol, oi = mfields(d)
                if bid is None and ask is None:
                    continue
                fh.write(json.dumps({"t": round(time.time(), 1), "type": "snap", "tk": c["tk"],
                                     "bid": bid, "ask": ask, "last": last,
                                     "vol": vol, "oi": oi,
                                     "res": d.get("result") or None}) + "\n")
            except Exception:
                pass
            time.sleep(0.15)
        fh.flush()
        time.sleep(max(0.0, POLL_S - (time.time() - t0)))
    fh.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
