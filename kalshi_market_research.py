#!/usr/bin/env python3
"""Kalshi public API market research — compact summary output."""

import requests
import time
import sys
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HEADERS = {"Accept": "application/json"}

def get(path, params=None, retries=2):
    url = BASE + path
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                time.sleep(2)
            else:
                return None
        except Exception as e:
            if attempt == retries:
                return None
            time.sleep(0.5)
    return None

def sleep():
    time.sleep(0.2)

# ── 1. Series discovery ────────────────────────────────────────────────────
CATEGORIES = ["Financials", "Economics", "Climate and Weather", "World", "Companies", "Crypto", None]

series_list = []
seen_tickers = set()

for cat in CATEGORIES:
    params = {"limit": 200}
    if cat:
        params["category"] = cat
    data = get("/series", params)
    sleep()
    if not data:
        continue
    items = data.get("series", [])
    for s in items:
        tk = s.get("ticker", "")
        if tk in seen_tickers:
            continue
        seen_tickers.add(tk)
        series_list.append({
            "ticker": tk,
            "title": s.get("title", ""),
            "category": s.get("category", cat or "unknown"),
            "frequency": s.get("frequency", ""),
        })

# ── 2. Filter non-crypto daily+ series and fetch open markets ──────────────
DAILY_FREQS = {"daily", "weekly", "hourly", "intraday", ""}   # include "" — may be daily

def looks_daily(s):
    freq = (s.get("frequency") or "").lower()
    cat = (s.get("category") or "").lower()
    if cat == "crypto":
        return False
    # exclude monthly/annual/quarterly unless we want them
    if any(x in freq for x in ["monthly", "annual", "quarterly"]):
        return False
    return True

candidate_series = [s for s in series_list if looks_daily(s)]

market_rows = []

for s in candidate_series:
    tk = s["ticker"]
    data = get("/markets", params={"series_ticker": tk, "status": "open", "limit": 20})
    sleep()
    if not data:
        continue
    markets = data.get("markets", [])
    if not markets:
        continue

    # pick first market as sample
    m = markets[0]
    yes_bid = m.get("yes_bid", 0) or 0
    no_bid  = m.get("no_bid", 0) or 0
    # Kalshi returns prices in cents (0–99)
    # box margin: 100 - yes_bid - no_bid  (all in cents)
    box_margin = 100 - yes_bid - no_bid

    vol_24h = m.get("volume_24h", 0) or 0
    oi      = m.get("open_interest", 0) or 0
    close_time = (m.get("close_time") or "")[:10]
    open_time  = (m.get("open_time")  or "")[:10]

    # tenor guess from open/close
    if close_time and open_time and close_time != open_time:
        tenor = f"{open_time}>{close_time}"
    elif close_time:
        tenor = close_time
    else:
        tenor = "?"

    market_rows.append({
        "series_ticker": tk,
        "market_ticker": m.get("ticker", ""),
        "category": s["category"],
        "frequency": s["frequency"],
        "tenor": tenor,
        "mkts_open": len(markets),
        "yes_bid": yes_bid,
        "no_bid": no_bid,
        "box_margin": box_margin,
        "vol_24h": vol_24h,
        "oi": oi,
    })

# ── 3. Daily crypto tickers ────────────────────────────────────────────────
CRYPTO_DAILY = ["KXBTCDAY", "KXBTCD", "KXBTC24H", "KXETHDAY", "KXETCDAY", "KXBTC"]
crypto_rows = []

for tk in CRYPTO_DAILY:
    data = get("/markets", params={"series_ticker": tk, "status": "open", "limit": 5})
    sleep()
    if not data:
        continue
    markets = data.get("markets", [])
    if not markets:
        continue
    m = markets[0]
    yes_bid = m.get("yes_bid", 0) or 0
    no_bid  = m.get("no_bid", 0) or 0
    box_margin = 100 - yes_bid - no_bid
    crypto_rows.append({
        "series_ticker": tk,
        "market_ticker": m.get("ticker", ""),
        "mkts_open": len(markets),
        "yes_bid": yes_bid,
        "no_bid": no_bid,
        "box_margin": box_margin,
        "vol_24h": m.get("volume_24h", 0) or 0,
        "oi": m.get("open_interest", 0) or 0,
    })

# ── 4. Orderbook depth for top viable series ──────────────────────────────
# Sort by positive box margin, pick top 8
viable = sorted([r for r in market_rows if r["box_margin"] > 0],
                key=lambda x: -x["box_margin"])[:8]

ob_rows = []
for r in viable:
    mt = r["market_ticker"]
    if not mt:
        continue
    data = get(f"/markets/{mt}/orderbook")
    sleep()
    if not data:
        continue
    ob = data.get("orderbook", data)
    yes_book = ob.get("yes", [])
    no_book  = ob.get("no", [])
    # each entry: [price, quantity]
    best_yes = yes_book[0] if yes_book else [0, 0]
    best_no  = no_book[0]  if no_book  else [0, 0]
    depth_yes = sum(e[1] for e in yes_book[:3]) if yes_book else 0
    depth_no  = sum(e[1] for e in no_book[:3])  if no_book  else 0
    ob_rows.append({
        "market_ticker": mt,
        "series_ticker": r["series_ticker"],
        "best_yes_bid": best_yes[0],
        "depth_yes_top3": depth_yes,
        "best_no_bid": best_no[0],
        "depth_no_top3": depth_no,
        "box_margin": r["box_margin"],
    })

# ══════════════════════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SERIES_DISCOVERY:")
print(f"{'TICKER':<20} {'CATEGORY':<22} {'FREQ':<12} TITLE")
print("-" * 80)
for s in sorted(series_list, key=lambda x: (x["category"], x["ticker"])):
    title = s["title"][:45]
    print(f"{s['ticker']:<20} {s['category']:<22} {s['frequency']:<12} {title}")

print()
print("=" * 80)
print("MARKET_STATS (non-crypto, daily+, has open markets):")
print(f"{'SERIES':<18} {'CAT':<18} {'TENOR':<22} {'#MKT':<5} {'Y_BID':<7} {'N_BID':<7} {'BOX_C':<7} {'VOL24H':<9} OI")
print("-" * 80)
for r in sorted(market_rows, key=lambda x: -x["box_margin"]):
    print(f"{r['series_ticker']:<18} {r['category'][:17]:<18} {r['tenor'][:21]:<22} "
          f"{r['mkts_open']:<5} {r['yes_bid']:<7} {r['no_bid']:<7} "
          f"{r['box_margin']:<7} {r['vol_24h']:<9} {r['oi']}")

print()
print("=" * 80)
print("CRYPTO DAILY SERIES:")
print(f"{'SERIES':<18} {'#MKT':<5} {'Y_BID':<7} {'N_BID':<7} {'BOX_C':<7} {'VOL24H':<9} OI")
print("-" * 80)
for r in crypto_rows:
    print(f"{r['series_ticker']:<18} {r['mkts_open']:<5} {r['yes_bid']:<7} {r['no_bid']:<7} "
          f"{r['box_margin']:<7} {r['vol_24h']:<9} {r['oi']}")

print()
print("=" * 80)
print("ORDERBOOK_DEPTH (top viable series, touch level):")
print(f"{'MARKET_TICKER':<32} {'SERIES':<18} {'BY_BID':<7} {'Y_D3':<9} {'BN_BID':<7} {'N_D3':<9} BOX_C")
print("-" * 80)
for r in ob_rows:
    print(f"{r['market_ticker']:<32} {r['series_ticker']:<18} "
          f"{r['best_yes_bid']:<7} {r['depth_yes_top3']:<9} "
          f"{r['best_no_bid']:<7} {r['depth_no_top3']:<9} {r['box_margin']}")

print()
print(f"Total series discovered: {len(series_list)}")
print(f"Non-crypto candidate series: {len(candidate_series)}")
print(f"Series with open markets: {len(market_rows)}")
print(f"Viable (box_margin>0): {len([r for r in market_rows if r['box_margin']>0])}")
print(f"Orderbook samples: {len(ob_rows)}")
