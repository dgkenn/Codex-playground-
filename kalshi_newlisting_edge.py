#!/usr/bin/env python3
"""
kalshi_newlisting_edge.py

NEW-LISTING MAKER EDGE TEST (Kalshi public API, no auth).

Hypothesis (from MAKER_VENUES brief): on a SOFT-category market, is the longshot/maker
premium RICHEST in the first HOURS of a newly-listed market -- before recreational flow
and any competing maker arrive (wider spreads, mispriced initial quotes)?

This is distinct from KALSHI_LONGSHOT_OPT.md's "early life (>=50% of LIFE remaining)"
filter, which buckets by FRACTION of total market life. THIS test buckets by ABSOLUTE
hours since open_time, and characterizes:

  (A) SPREAD WIDTH vs age:   currently-open soft markets, snapshot of yes_bid/yes_ask,
      bucketed by age = now - open_time. Is the touch spread WIDER in the first hours?
  (B) LONGSHOT-SELL HARVEST vs age:  settled soft markets, per-fill realized maker P&L
      to settlement (same SELL_YES p in [0.05,0.15) metric as the validated edge),
      bucketed by absolute hours since open_time at the time of fill. Is the per-contract
      edge RICHER in the first hours? Event-clustered z.

Usage:
  python3 kalshi_newlisting_edge.py spread     # (A) cross-sectional open-market snapshot
  python3 kalshi_newlisting_edge.py harvest     # (B) historical fills-by-age (slow, cached)
  python3 kalshi_newlisting_edge.py all
"""

import sys
import json
import gzip
import time
import math
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SOFT_CATS = ["Politics", "Economics", "Climate and Weather", "Entertainment",
             "Science and Technology", "World", "Companies"]
REQUEST_PAUSE = 0.4
SPREAD_CACHE = "newlisting_spread.json.gz"
HARVEST_CACHE = "newlisting_harvest.json.gz"


def http_get(path, params=None, retries=6):
    url = BASE + path
    if params:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
                     if v is not None and v != "")
        url = url + "?" + q
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json",
                              "User-Agent": "newlisting-edge-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (i + 1)); continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def parse_ts(s):
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# series fee_type, so we can keep only zero-maker-fee (quadratic) soft series
def list_series(category):
    out, cursor = [], ""
    while True:
        d = http_get("/series", {"category": category, "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("series", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= 600:
            break
        time.sleep(REQUEST_PAUSE)
    return out


# ----------------------------------------------------------------------------
# (A) CROSS-SECTIONAL SPREAD-BY-AGE on currently-open soft markets
# ----------------------------------------------------------------------------
def best_touch(ticker):
    """Return (yes_bid, yes_ask, n_yes_levels, n_no_levels, depth_at_touch) from the
    public orderbook. Kalshi orderbook_fp: yes_dollars = YES bid ladder, no_dollars =
    NO bid ladder. best_yes_bid = max yes price; best_yes_ask = 1 - max no price."""
    ob = http_get(f"/markets/{ticker}/orderbook")
    if not ob:
        return None
    obk = ob.get("orderbook_fp") or ob.get("orderbook") or {}
    yd = obk.get("yes_dollars") or obk.get("yes") or []
    nd = obk.get("no_dollars") or obk.get("no") or []

    def top_price(ladder):
        best = None
        bestsz = 0.0
        for lvl in ladder:
            try:
                px = float(lvl[0]); sz = float(lvl[1])
            except Exception:
                continue
            if best is None or px > best:
                best = px; bestsz = sz
        return best, bestsz
    yb, yb_sz = top_price(yd)
    nb, nb_sz = top_price(nd)
    yes_ask = (1.0 - nb) if nb is not None else None
    return yb, yes_ask, len(yd), len(nd), (yb_sz, nb_sz)


def collect_open_markets():
    """Snapshot open soft-category markets: orderbook touch + open_time + age."""
    series_by_cat = {}
    feetype = {}
    for cat in SOFT_CATS:
        s = list_series(cat)
        series_by_cat[cat] = s
        for ser in s:
            feetype[ser.get("ticker")] = ser.get("fee_type", "quadratic")
    rows = []
    now = time.time()
    seen = 0
    for cat, sers in series_by_cat.items():
        # cap series/cat so the orderbook probing stays in the time budget
        for ser in sers[:25]:
            st = ser.get("ticker")
            if not st:
                continue
            md = http_get("/markets", {"series_ticker": st, "status": "open", "limit": 100})
            if not md:
                continue
            mkts = md.get("markets", [])
            for m in mkts[:40]:
                ot = parse_ts(m.get("open_time"))
                ct = parse_ts(m.get("close_time"))
                tk = m.get("ticker")
                if ot is None or not tk:
                    continue
                age_h = (now - ot) / 3600.0
                t = best_touch(tk)
                seen += 1
                time.sleep(REQUEST_PAUSE)
                if t is None:
                    continue
                yb, ya, nyes, nno, depth = t
                two_sided = (yb is not None and ya is not None)
                row = {
                    "cat": cat, "series": st,
                    "fee_type": feetype.get(st, "quadratic"),
                    "ticker": tk, "age_h": age_h,
                    "life_h": ((ct - ot) / 3600.0) if (ct and ot) else None,
                    "yes_bid": yb, "yes_ask": ya,
                    "n_yes_levels": nyes, "n_no_levels": nno,
                    "empty_book": (nyes == 0 and nno == 0),
                    "one_sided": (not two_sided) and (nyes > 0 or nno > 0),
                    "two_sided": two_sided,
                    "spread": (ya - yb) if two_sided else None,
                    "mid": ((ya + yb) / 2.0) if two_sided else None,
                    "touch_yes_sz": depth[0], "touch_no_sz": depth[1],
                }
                rows.append(row)
            time.sleep(REQUEST_PAUSE)
    with gzip.open(SPREAD_CACHE, "wt") as f:
        json.dump(rows, f)
    print(f"[spread] probed {seen} markets, stored {len(rows)} rows -> {SPREAD_CACHE}")
    return rows


def analyze_spread():
    with gzip.open(SPREAD_CACHE, "rt") as f:
        rows = json.load(f)
    print(f"\n=== (A) BOOK-STATE & SPREAD-BY-AGE, open soft markets (n={len(rows)}) ===")
    rows = [r for r in rows if r["fee_type"] == "quadratic"]
    print(f"zero-maker-fee (quadratic) subset: n={len(rows)}")

    age_buckets = [(0, 2), (2, 6), (6, 24), (24, 72), (72, 168), (168, 1e9)]
    labels = ["0-2h", "2-6h", "6-24h", "1-3d", "3-7d", ">7d"]

    # CORE: book-state by age -- is the new-listing window literally an EMPTY book?
    print("\nBOOK STATE by age (the structural new-listing question):")
    print(f"{'age':>6} | {'n':>5} | {'empty%':>7} | {'1-sided%':>8} | {'2-sided%':>8} | {'med_spread(2s)':>14}")
    for (lo, hi), lab in zip(age_buckets, labels):
        sub = [r for r in rows if lo <= r["age_h"] < hi]
        if not sub:
            continue
        n = len(sub)
        emp = sum(1 for r in sub if r["empty_book"])
        one = sum(1 for r in sub if r["one_sided"])
        two = [r for r in sub if r["two_sided"]]
        if two:
            sp = sorted(r["spread"] for r in two)
            meds = f"{sp[len(sp)//2]*100:.2f}c"
        else:
            meds = "n/a"
        print(f"{lab:>6} | {n:>5} | {100*emp/n:>6.0f}% | {100*one/n:>7.0f}% | "
              f"{100*len(two)/n:>7.0f}% | {meds:>14}")

    # spread in the longshot mid region, among two-sided books only
    ls = [r for r in rows if r["two_sided"] and r["mid"] is not None
          and 0.03 <= r["mid"] < 0.20]
    print(f"\nSPREAD in longshot mid region (mid in [0.03,0.20)), two-sided books only "
          f"(n={len(ls)}):")
    print(f"{'age':>6} | {'n':>5} | {'med_spread':>10} | {'mean_spread':>11}")
    for (lo, hi), lab in zip(age_buckets, labels):
        sub = [r for r in ls if lo <= r["age_h"] < hi]
        if not sub:
            continue
        sp = sorted(r["spread"] for r in sub)
        med = sp[len(sp) // 2]; mean = sum(sp) / len(sp)
        print(f"{lab:>6} | {len(sub):>5} | {med*100:>9.2f}c | {mean*100:>10.2f}c")

    print("\nINTERPRETATION: a maker premium requires a recreational TAKER to lift your")
    print("resting quote. An EMPTY/one-sided book in the first hours means NO flow yet to")
    print("harvest -- the 'wide spread' there is a phantom (no counterparty), not an edge.")


# ----------------------------------------------------------------------------
# (B) HISTORICAL HARVEST-BY-AGE on settled soft markets
# ----------------------------------------------------------------------------
def list_settled_markets(series_ticker, cap=60):
    out, cursor = [], ""
    while True:
        d = http_get("/markets", {"series_ticker": series_ticker, "status": "settled",
                                  "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("markets", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= cap:
            break
        time.sleep(REQUEST_PAUSE)
    return out[:cap]


def get_trades(ticker, cap=4000):
    out, cursor = [], ""
    while True:
        d = http_get("/markets/trades", {"ticker": ticker, "limit": 1000, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("trades", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= cap:
            break
        time.sleep(REQUEST_PAUSE)
    return out


def collect_harvest():
    """Per-fill SELL_YES harvest records in p in [0.05,0.15), tagged by absolute
    hours-since-open at fill time. Cached."""
    fills = []
    n_mkts = 0
    # Climate/Econ/SciTech/Entertainment carry the validated edge & the most settled
    # binaries; cap tightly so the (slow) trades pull fits the time budget.
    cats = ["Climate and Weather", "Economics", "Science and Technology", "Entertainment"]
    for cat in cats:
        sers = list_series(cat)
        cap_series = 12
        for ser in sers[:cap_series]:
            st = ser.get("ticker")
            ft = ser.get("fee_type", "quadratic")
            if ft != "quadratic":
                continue  # zero-maker-fee universe only
            mkts = list_settled_markets(st, cap=20)
            for m in mkts:
                ot = parse_ts(m.get("open_time"))
                res = m.get("result")
                if ot is None or res not in ("yes", "no"):
                    continue
                settle = 1.0 if res == "yes" else 0.0
                trades = get_trades(m.get("ticker"), cap=3000)
                got = 0
                for t in trades:
                    # SELL_YES harvest fill = taker lifted YES (taker_side=="yes")
                    if t.get("taker_side") != "yes":
                        continue
                    # fields are *_dollars strings (e.g. "0.0100" == 1c) + count_fp
                    p = fnum(t.get("yes_price_dollars"))
                    if p is None:
                        p = fnum(t.get("yes_price"))
                        if p is not None:
                            p = p / 100.0
                    if p is None:
                        continue
                    if not (0.05 <= p < 0.15):
                        continue
                    cnt = fnum(t.get("count_fp"), None)
                    if cnt is None:
                        cnt = fnum(t.get("count"), 1.0)
                    tt = parse_ts(t.get("created_time"))
                    if tt is None:
                        continue
                    age_h = (tt - ot) / 3600.0
                    pnl = p - settle  # maker SHORT yes
                    fills.append({
                        "cat": cat, "event": m.get("event_ticker") or m.get("ticker"),
                        "ticker": m.get("ticker"), "p": p, "count": cnt,
                        "age_h": age_h, "pnl": pnl,
                    })
                    got += 1
                if got:
                    n_mkts += 1
                time.sleep(REQUEST_PAUSE)
            time.sleep(REQUEST_PAUSE)
        print(f"[harvest] {cat}: cumulative fills={len(fills)} mkts={n_mkts}")
    with gzip.open(HARVEST_CACHE, "wt") as f:
        json.dump(fills, f)
    print(f"[harvest] stored {len(fills)} SELL_YES fills p in [0.05,0.15) -> {HARVEST_CACHE}")
    return fills


def analyze_harvest():
    with gzip.open(HARVEST_CACHE, "rt") as f:
        fills = json.load(f)
    print(f"\n=== (B) HARVEST-BY-AGE: SELL_YES, p in [0.05,0.15), zero-fee soft (n_fills={len(fills)}) ===")

    age_buckets = [(0, 2), (2, 6), (6, 24), (24, 72), (72, 168), (168, 1e9)]
    labels = ["0-2h", "2-6h", "6-24h", "1-3d", "3-7d", ">7d"]

    def clustered(sub):
        """contract(dollar)-weighted mean pnl + event-clustered z."""
        if not sub:
            return None
        # event aggregation: sum count, sum count*pnl per event
        by_ev = defaultdict(lambda: [0.0, 0.0])
        for f in sub:
            e = by_ev[f["event"]]
            e[0] += f["count"]
            e[1] += f["count"] * f["pnl"]
        tot_w = sum(v[0] for v in by_ev.values())
        if tot_w <= 0:
            return None
        vw_mean = sum(v[1] for v in by_ev.values()) / tot_w
        # event-level weighted: each event contributes (w_e, mean_e)
        evs = [(v[0], v[1] / v[0]) for v in by_ev.values() if v[0] > 0]
        if len(evs) < 2:
            return {"n_fills": len(sub), "n_events": len(evs), "contracts": tot_w,
                    "vw_pnl": vw_mean, "z": float("nan")}
        # weighted variance of event means around vw_mean
        wsum = sum(w for w, _ in evs)
        var = sum(w * (mn - vw_mean) ** 2 for w, mn in evs) / wsum
        # effective N events; SE via weighted (Kish) effective sample size
        w2 = sum(w * w for w, _ in evs)
        n_eff = (wsum * wsum) / w2 if w2 > 0 else len(evs)
        se = math.sqrt(var / max(n_eff, 1.0))
        z = vw_mean / se if se > 0 else float("nan")
        return {"n_fills": len(sub), "n_events": len(evs), "contracts": tot_w,
                "vw_pnl": vw_mean, "z": z}

    print(f"\n{'age':>6} | {'n_fills':>7} | {'n_evt':>5} | {'contracts':>10} | {'vw_pnl/ct':>9} | {'clust_z':>7}")
    for (lo, hi), lab in zip(age_buckets, labels):
        sub = [f for f in fills if lo <= f["age_h"] < hi]
        s = clustered(sub)
        if s:
            print(f"{lab:>6} | {s['n_fills']:>7} | {s['n_events']:>5} | "
                  f"{s['contracts']:>10.0f} | {s['vw_pnl']*100:>+8.2f}c | {s['z']:>+7.1f}")

    # headline contrast: first 6h vs rest
    first = [f for f in fills if f["age_h"] < 6]
    rest = [f for f in fills if f["age_h"] >= 6]
    sf, sr = clustered(first), clustered(rest)
    print("\nCONTRAST (first 6h vs >=6h):")
    if sf:
        print(f"  first<6h : vw_pnl={sf['vw_pnl']*100:+.2f}c  z={sf['z']:+.1f}  "
              f"n_evt={sf['n_events']}  contracts={sf['contracts']:.0f}")
    if sr:
        print(f"  rest>=6h : vw_pnl={sr['vw_pnl']*100:+.2f}c  z={sr['z']:+.1f}  "
              f"n_evt={sr['n_events']}  contracts={sr['contracts']:.0f}")
    if sf and sr:
        print(f"  LIFT (first6h - rest) = {(sf['vw_pnl']-sr['vw_pnl'])*100:+.2f}c/contract")

    # ALSO: what fraction of harvestable contract flow even occurs in the first hours?
    tot = sum(f["count"] for f in fills)
    for cut, lab in [(2, "<2h"), (6, "<6h"), (24, "<24h")]:
        c = sum(f["count"] for f in fills if f["age_h"] < cut)
        print(f"  flow share {lab:>5}: {100*c/tot:5.1f}% of harvestable contracts" if tot else "")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("spread", "all"):
        try:
            with gzip.open(SPREAD_CACHE, "rt") as f:
                json.load(f)
            print("[spread] cache present, skipping collect (delete to refresh)")
        except Exception:
            collect_open_markets()
        analyze_spread()
    if mode in ("harvest", "all"):
        try:
            with gzip.open(HARVEST_CACHE, "rt") as f:
                json.load(f)
            print("[harvest] cache present, skipping collect (delete to refresh)")
        except Exception:
            collect_harvest()
        analyze_harvest()
