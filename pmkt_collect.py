"""pmkt_collect.py -- CROSS-VENUE shadow collector for Polymarket 'Bitcoin/Ethereum Up or Down'
short-tenor markets, to TEST (offline, before any live use) whether Polymarket leads Kalshi.

WHY. Polymarket's 5-min BTC up/down markets trade $100k-273k per window -- far more than Kalshi's
15-min books. If that deeper, more-informed flow LEADS price discovery, Polymarket's probability is a
toxicity/fair-value signal we could read (not trade) to avoid adverse selection on Kalshi -- the
exact cause of the unpaired-leg losses. This collector records Polymarket's book timestamped so we
can measure the lead-lag against our Kalshi book + BTC spot, then decide. Read-only, no auth, no money.

CAVEATS this data will let us quantify: (1) tenor mismatch (Poly 5-min vs Kalshi 15-min); (2) coverage
-- Poly windows look sporadic/scheduled, not continuous; (3) both venues are downstream of BTC spot
which we already track, so the real question is whether Poly adds info BEYOND spot.

    python pmkt_collect.py [duration_s] [out_dir] [tag]
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
POLL = 1.5


def now():
    return datetime.now(timezone.utc)


def find_live(asset="bitcoin"):
    """Return (end_dt, title, up_token, down_token) for a currently-OPEN <asset> up/down market,
    or None. Best-effort: searches recent up/down events and picks one open now."""
    try:
        d = requests.get(f"{GAMMA}/public-search",
                         params={"q": f"{asset} up or down", "limit": 40}, timeout=12).json()
    except Exception:
        return None
    n = now()
    best = None
    for e in d.get("events", []):
        if "up or down" not in e.get("title", "").lower():
            continue
        end = e.get("endDate", "")
        try:
            et = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception:
            continue
        if not (n < et < n.replace(hour=23, minute=59)):  # ends later today, still ahead of now
            continue
        for m in e.get("markets", []):
            if m.get("closed"):
                continue
            toks = m.get("clobTokenIds")
            toks = json.loads(toks) if isinstance(toks, str) else toks
            if not toks or len(toks) < 2:
                continue
            if best is None or et < best[0]:
                best = (et, e.get("title", ""), toks[0], toks[1])
    return best


def book_top(token_id):
    try:
        b = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=8).json()
        bids = b.get("bids") or []; asks = b.get("asks") or []
        bb = max((float(x["price"]) for x in bids), default=None)
        ba = min((float(x["price"]) for x in asks), default=None)
        bsz = sum(float(x["size"]) for x in bids)
        asz = sum(float(x["size"]) for x in asks)
        return bb, ba, bsz, asz
    except Exception:
        return None, None, 0.0, 0.0


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"pm{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, f"pmkt_btc_updown_{tag}.jsonl.gz")
    fh = gzip.open(fp, "at")
    end = time.time() + dur
    cur = None; cur_end = 0.0
    print(f"pmkt_collect: {dur}s -> {fp}", flush=True)
    while time.time() < end:
        t0 = time.time()
        if cur is None or time.time() > cur_end:
            live = find_live("bitcoin")
            if live:
                cur_end = live[0].timestamp(); cur = live
                print(f"{now():%H:%M}Z live: {live[1][:45]} (ends {live[0]:%H:%MZ})", flush=True)
            else:
                cur = None
                time.sleep(20); continue          # no open window -> wait (coverage is sporadic)
        et, title, up_tok, down_tok = cur
        ub, ua, ubs, uas = book_top(up_tok)
        db, da, dbs, das = book_top(down_tok)
        if ub is not None or ua is not None:
            fh.write(json.dumps({
                "t": round(time.time(), 2), "end": cur_end, "venue": "polymarket",
                "asset": "btc", "title": title,
                "up_bid": ub, "up_ask": ua, "up_bsz": round(ubs, 1), "up_asz": round(uas, 1),
                "down_bid": db, "down_ask": da}) + "\n")
            fh.flush()
        time.sleep(max(0.0, POLL - (time.time() - t0)))
    fh.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
