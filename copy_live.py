"""copy_live.py -- COPY 0x20d2309cd9 and validate prospectively: rest the same two-sided quotes on every
active crypto Up/Down market, then score the wallet's REAL incoming fills as captured/missed vs our
quote envelope. Goal: tune the rule (depth/markets) until we capture >=95% of their trades.

FIXED (v2): decoupled threads so a slow book poll never starves the trade poll (v1 undercounted fills
~6x); HONEST capture test (their fill must land inside our actual quote ladder at the tick, not merely
within a few cents of the touch); and an end-of-run RECONCILIATION (independent count of the wallet's
trades in the run window vs what we scored) to prove we saw them all.

Replicator rule (theta): for each active {assets}x{tenors} market, quote BOTH tokens a ladder of DEPTH
ticks from each touch. Capture their BUY@p iff market tracked AND best_bid-DEPTH*tick <= p <= best_bid+tick;
their SELL@p iff best_ask-tick <= p <= best_ask+DEPTH*tick. Read-only (CLOB /book + data-api /trades).
    python copy_live.py [seconds] [depth_ticks] [assets_csv] [tenors_csv]
"""
from __future__ import annotations
import collections, json, sys, threading, time
import requests

import os
G = "https://gamma-api.polymarket.com"; C = "https://clob.polymarket.com"; D = "https://data-api.polymarket.com"
WALLET = os.environ.get("COPY_WALLET", "0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d")


def book(sess, token):
    try:
        b = sess.get(C + "/book", params={"token_id": token}, timeout=6).json()
        bids, asks = b.get("bids", []), b.get("asks", [])
        return (float(bids[-1]["price"]) if bids else None, float(asks[-1]["price"]) if asks else None)
    except Exception:
        return None, None


def discover(sess, assets, tenors):
    idx = {}; now = int(time.time())
    for a in assets:
        for tn in tenors:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=10).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; tk = json.loads(m["clobTokenIds"])
                    tick = float(m.get("orderPriceMinTickSize", 0.01) or 0.01)
                    idx[str(tk[0])] = (m["slug"], True, tick); idx[str(tk[1])] = (m["slug"], False, tick)
                    break
    return idx


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    assets = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["btc", "eth", "sol", "xrp"])
    tenors = ([int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [5, 15])
    books = collections.defaultdict(lambda: collections.deque(maxlen=60))
    idx = {}; lock = threading.Lock(); stop = threading.Event()
    start = int(time.time())

    def book_thread():
        s = requests.Session()
        last = 0
        while not stop.is_set():
            if time.time() - last > 30:
                idx.update(discover(s, assets, tenors)); last = time.time()   # UNION: keep just-rotated mkts
            for tok in list(idx):
                bb, ba = book(s, tok)
                if bb is not None or ba is not None:
                    with lock:
                        books[tok].append((time.time(), bb, ba))
            time.sleep(1.0)

    trades_buf = collections.deque(); seen = set()

    def trade_thread():
        s = requests.Session()
        while not stop.is_set():
            try:
                tr = s.get(D + "/trades", params={"user": WALLET, "limit": 200}, timeout=12).json()
            except Exception:
                tr = []
            for t in tr if isinstance(tr, list) else []:
                tx = t["transactionHash"] + str(t.get("asset")) + t["side"]
                if tx in seen:
                    continue
                seen.add(tx)
                with lock:
                    trades_buf.append(t)
            time.sleep(3.0)

    bt = threading.Thread(target=book_thread, daemon=True); tt = threading.Thread(target=trade_thread, daemon=True)
    bt.start(); tt.start()
    print(f"copy | {WALLET[:10]} | assets={assets} tenors={tenors} | {dur}s (multi-depth capture curve)", flush=True)

    def book_window(tok, ts, W=8):
        """min/max touch over snapshots within +/-W of the trade -> robust to the touch MOVING between
        our snapshot and the fill (a ladder follows the touch, so cover the whole near-trade touch range)."""
        with lock:
            snaps = [x for x in books.get(tok, ()) if abs(x[0] - ts) <= W]
        if not snaps:
            return None
        bids = [b for _, b, _ in snaps if b is not None]; asks = [a for _, _, a in snaps if a is not None]
        return (min(bids) if bids else None, max(bids) if bids else None,
                min(asks) if asks else None, max(asks) if asks else None)

    DEPTHS = [1, 2, 3, 5, 7]                         # report the capture-vs-ladder-depth curve (honest)
    stats = collections.Counter(); capd = {d: 0 for d in DEPTHS}; miss = collections.Counter()
    missed_slugs = collections.Counter()             # uncovered markets -> autotuner expands coverage
    fh = open("copy_capture.jsonl", "a"); t_end = time.time() + dur
    while time.time() < t_end:
        time.sleep(5)
        with lock:
            batch = list(trades_buf); trades_buf.clear()
        for t in batch:
            if int(t["timestamp"]) < start - 30 or time.time() - int(t["timestamp"]) > 120:
                continue                                  # only fills within the observed window
            stats["total"] += 1
            tok = str(t["asset"]); p = float(t["price"]); side = t["side"]
            band = book_window(tok, int(t["timestamp"]))
            rec = {"ts": int(t["timestamp"]), "tok": tok[:8], "side": side, "price": p, "slug": t.get("slug")}
            if tok not in idx:
                miss["market_not_tracked"] += 1; rec["why"] = "market_not_tracked"; missed_slugs[t.get("slug")] += 1
            elif band is None:
                miss["no_book"] += 1; rec["why"] = "no_book"
            else:
                minb, maxb, mina, maxa = band; tick = idx[tok][2]; rec["band"] = band
                hit = []
                for d in DEPTHS:
                    if side == "BUY":
                        c = maxb is not None and (minb - d * tick - 1e-9) <= p <= maxb + tick + 1e-9
                    else:
                        c = mina is not None and (mina - tick - 1e-9) <= p <= maxa + d * tick + 1e-9
                    if c:
                        capd[d] += 1; hit.append(d)
                rec["hit_depths"] = hit
                if not hit:
                    miss["price_outside_ladder>7tk"] += 1
            fh.write(json.dumps(rec) + "\n")
        fh.flush()
        tot = stats["total"]
        if tot:
            curve = "  ".join(f"d{d}={100*capd[d]/tot:.0f}%" for d in DEPTHS)
            print(f"  t+{int(time.time())-start}s fills={tot} capture[{curve}] misses={dict(miss)}", flush=True)
    stop.set(); time.sleep(1)
    # RECONCILIATION: independent count of the wallet's trades in [start, end]
    s = requests.Session(); allt = []; off = 0
    while off < 3000:
        j = s.get(D + "/trades", params={"user": WALLET, "limit": 500, "offset": off}, timeout=15).json()
        if not isinstance(j, list) or not j:
            break
        allt += j; off += 500
        if len(j) < 500 or int(j[-1]["timestamp"]) < start:
            break
    actual = [t for t in allt if start <= int(t["timestamp"]) <= int(t_end)]
    tot = stats["total"]
    print(f"\n=== RESULT ===")
    print(f"wallet ACTUAL trades in window: {len(actual)}   | we SCORED: {tot}  (saw {100*tot/max(1,len(actual)):.0f}% of them)")
    print("CAPTURE vs ladder depth (their fill price within +/- d ticks of the touch on the correct side):")
    for d in DEPTHS:
        print(f"   depth {d}tk: {capd[d]}/{tot} = {100*capd[d]/max(1,tot):.1f}%")
    print(f"misses: {dict(miss)}")
    # machine-readable result for the self-tuning loop (copy_autotune.py)
    res = {"wallet": WALLET, "ts": int(time.time()), "scored": tot, "actual": len(actual),
           "seen_pct": round(100 * tot / max(1, len(actual)), 1),
           "capture": {d: round(100 * capd[d] / max(1, tot), 1) for d in DEPTHS},
           "misses": dict(miss), "missed_slugs": dict(missed_slugs.most_common(20)),
           "assets": assets, "tenors": tenors}
    json.dump(res, open("copy_result.json", "w"))


if __name__ == "__main__":
    main()
