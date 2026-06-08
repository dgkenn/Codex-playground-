"""copy_live.py -- COPY 0x20d2309cd9's strategy and validate prospectively: rest the same two-sided
quotes on every active crypto Up/Down market, then check, against the wallet's REAL incoming fills,
what fraction our replicator would have captured. Iterate the rule (tol/ladder/markets) until >=95%.

Replicator rule (theta): for each active {btc,eth,sol,xrp}x{5m,15m} market, quote BOTH tokens a ladder
of DEPTH ticks from each touch (BID side down from best_bid, ASK side up from best_ask). A wallet fill
(market, token, side, price) is CAPTURED if our quote on that side covers the print: their BUY@p (a
taker sold into a bid) is captured if our best_bid >= p - tol*tick; their SELL@p if our best_ask <=
p + tol*tick (with DEPTH>0 the ladder extends the covered range). Misses are logged with a reason
(market_not_tracked / no_book / price_outside_quote) to drive the next iteration.

    python copy_live.py [seconds] [tol_ticks] [depth_ticks]
Read-only: polls CLOB /book + data-api /trades, places nothing. Writes copy_capture.jsonl.
"""
from __future__ import annotations
import collections, json, sys, time
import requests

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"
D = "https://data-api.polymarket.com"
WALLET = "0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d"
ASSETS = ("btc", "eth", "sol", "xrp")
TENORS = (5, 15)


def book(sess, token):
    try:
        b = sess.get(C + "/book", params={"token_id": token}, timeout=8).json()
        bids, asks = b.get("bids", []), b.get("asks", [])
        bb = float(bids[-1]["price"]) if bids else None
        ba = float(asks[-1]["price"]) if asks else None
        return bb, ba
    except Exception:
        return None, None


def discover(sess):
    """active markets -> {token: (slug, is_up, tick)} and list of tokens to poll."""
    idx = {}; now = int(time.time())
    for a in ASSETS:
        for tn in TENORS:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=12).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; toks = json.loads(m["clobTokenIds"])
                    tick = float(m.get("orderPriceMinTickSize", 0.01) or 0.01)
                    idx[str(toks[0])] = (m["slug"], True, tick)
                    idx[str(toks[1])] = (m["slug"], False, tick)
                    break
    return idx


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    tol = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0      # tolerance in ticks
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 2        # ladder depth in ticks (covers their ~6 levels)
    sess = requests.Session()
    books = collections.defaultdict(lambda: collections.deque(maxlen=40))   # token -> [(ts,bid,ask)]

    def book_at(tok, ts):
        """book snapshot at/just-before trade ts (nearest within 20s); else None."""
        best = None
        for (bts, bb, ba) in books.get(tok, ()):
            if bts <= ts + 3 and (best is None or bts > best[0]):
                best = (bts, bb, ba)
        if best is None and books.get(tok):
            best = min(books[tok], key=lambda x: abs(x[0] - ts))
        return best if (best and abs(best[0] - ts) <= 20) else None

    idx = discover(sess); last_disc = time.time()
    seen = set(); fh = open("copy_capture.jsonl", "a")
    stats = collections.Counter()
    miss_reason = collections.Counter()
    t_end = time.time() + dur
    last_trade_poll = 0.0
    print(f"copying {WALLET[:10]} | tracking {len(idx)} tokens | tol={tol}tk depth={depth}tk | {dur}s")
    while time.time() < t_end:
        if time.time() - last_disc > 45:       # markets cycle (5m/15m) -> refresh
            idx = discover(sess); last_disc = time.time()
        for tok in list(idx):                  # snapshot books (timestamped history)
            bb, ba = book(sess, tok)
            if bb is not None or ba is not None:
                books[tok].append((time.time(), bb, ba))
        if time.time() - last_trade_poll > 6:  # poll their new fills
            last_trade_poll = time.time()
            try:
                tr = sess.get(D + "/trades", params={"user": WALLET, "limit": 200}, timeout=15).json()
            except Exception:
                tr = []
            for t in tr if isinstance(tr, list) else []:
                tx = t["transactionHash"] + str(t.get("asset"))
                if tx in seen:
                    continue
                seen.add(tx)
                if time.time() - int(t["timestamp"]) > 90:     # only score fresh fills we could've seen
                    continue
                stats["total"] += 1
                tok = str(t["asset"]); p = float(t["price"]); side = t["side"]
                rec = {"ts": int(t["timestamp"]), "tok": tok[:10], "side": side, "price": p}
                snap = book_at(tok, int(t["timestamp"]))
                if tok not in idx:
                    miss_reason["market_not_tracked"] += 1; rec["cap"] = 0; rec["why"] = "market_not_tracked"
                elif snap is None:
                    miss_reason["no_book"] += 1; rec["cap"] = 0; rec["why"] = "no_book"
                else:
                    bts, bb, ba = snap; tick = idx[tok][2]
                    cover = (tol + depth) * tick
                    if side == "BUY":          # taker sold into a bid; we cover if our bid >= p - cover
                        cap = bb is not None and bb >= p - cover
                    else:                       # taker bought an ask; we cover if our ask <= p + cover
                        cap = ba is not None and ba <= p + cover
                    rec["cap"] = int(cap)
                    if cap:
                        stats["captured"] += 1
                    else:
                        miss_reason["price_outside_quote"] += 1; rec["why"] = "price_outside_quote"
                        rec["bid"] = bb; rec["ask"] = ba
                fh.write(json.dumps(rec) + "\n"); fh.flush()
            tot = stats["total"]; cap = stats["captured"]
            if tot:
                print(f"  t+{int(time.time()-(t_end-dur))}s  fills={tot} captured={cap} "
                      f"({100*cap/tot:.0f}%)  misses={dict(miss_reason)}", flush=True)
        time.sleep(1.5)
    tot = stats["total"]; cap = stats["captured"]
    print(f"\nCAPTURE: {cap}/{tot} = {100*cap/max(1,tot):.1f}%  | misses: {dict(miss_reason)}")
    print("iterate: market_not_tracked -> add markets; price_outside_quote -> raise depth/tol; "
          "then re-run until >=95%.")


if __name__ == "__main__":
    main()
