"""strategy_fine.py -- reconstruct a target's EXACT order-placement function (toward 1:1), not just broad
params. For every fill we capture the precise microstructure at fill time (WS book) + the action, then
mine the deterministic rules:
  offset_tk   (best_bid - fill_price)/tick for BUY ; (fill_price - best_ask)/tick for SELL
              = exactly where they rest vs the touch (0 = AT touch, + = inside/deeper). The modal offset
              and its share = how rigid the placement rule is (high share => a precise code rule).
  size_sh     exact shares per order -> fixed clip(s)?
  set_sum     this-token-touch + OTHER-token-touch at the fill -> exact complete-set entry threshold
  spread_tk, imbalance (bid_sz/(bid_sz+ask_sz)), sec_in_window, running inventory (from their own tape)
Records strategy_fine.jsonl; prints the exact-rule card with fidelity %. python strategy_fine.py [secs] [wallets_csv]
"""
from __future__ import annotations
import asyncio, collections, json, os, statistics, sys, threading, time
import requests, websockets

G = "https://gamma-api.polymarket.com"; D = "https://data-api.polymarket.com"
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
ASSETS = ["btc", "eth", "sol", "xrp"]; TENORS = [5, 15]


def discover(sess):
    """token -> (slug, is_up, tick, other_token, ws_open, win)"""
    idx = {}; now = int(time.time())
    for a in ASSETS:
        for tn in TENORS:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=10).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; tk = json.loads(m["clobTokenIds"]); tick = float(m.get("orderPriceMinTickSize", 0.01) or 0.01)
                    up, dn = str(tk[0]), str(tk[1])
                    idx[up] = (m["slug"], True, tick, dn, cand, win); idx[dn] = (m["slug"], False, tick, up, cand, win)
                    break
    return idx


def analyze_file(path="strategy_fine.jsonl"):
    """offline: pool all recorded fills (e.g. across overnight gha-data runs) and print the rule cards."""
    recs = collections.defaultdict(list)
    for ln in open(path):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        recs[r["w"]].append(r)
    analyze(recs)


def main():
    if "--analyze" in sys.argv:
        analyze_file(); return
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    if len(sys.argv) > 2:
        wallets = sys.argv[2].split(",")
    else:
        mm = json.load(open("mm_score.json")); wallets = [r["w"] for r in mm[:3]]   # top 3 by default
    idx = {}; tob = {}; lock = threading.Lock(); stop = threading.Event(); start = int(time.time())

    def ws_thread():
        nonlocal idx
        s = requests.Session()
        async def run():
            nonlocal idx
            last = 0
            while not stop.is_set():
                idx = discover(s); last = time.time(); toks = list(idx)
                if not toks:
                    await asyncio.sleep(3); continue
                try:
                    async with websockets.connect(WS, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                        await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                        while not stop.is_set() and time.time() - last < 40:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                            except asyncio.TimeoutError:
                                continue
                            for m in (json.loads(raw) if raw.startswith("[") else [json.loads(raw)]):
                                et = m.get("event_type")
                                if et == "book":
                                    b = m.get("bids") or []; a = m.get("asks") or []
                                    bb = max(b, key=lambda x: float(x["price"])) if b else None
                                    ba = min(a, key=lambda x: float(x["price"])) if a else None
                                    with lock:
                                        tob[str(m["asset_id"])] = (time.time(),
                                            float(bb["price"]) if bb else None, float(bb["size"]) if bb else 0,
                                            float(ba["price"]) if ba else None, float(ba["size"]) if ba else 0)
                except Exception:
                    await asyncio.sleep(2)
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(run())

    buf = collections.deque(); seen = set()

    def trade_thread():
        s = requests.Session(); i = 0
        while not stop.is_set():
            w = wallets[i % len(wallets)]; i += 1
            try:
                tr = s.get(D + "/trades", params={"user": w, "limit": 100}, timeout=12).json()
            except Exception:
                tr = []
            for t in tr if isinstance(tr, list) else []:
                k = w + t["transactionHash"] + str(t.get("asset")) + t["side"]
                if k in seen:
                    continue
                seen.add(k)
                with lock:
                    buf.append((w, t))
            time.sleep(max(0.4, 4.0 / len(wallets)))

    threading.Thread(target=ws_thread, daemon=True).start()
    threading.Thread(target=trade_thread, daemon=True).start()
    inv = collections.defaultdict(float)             # (wallet, token) running inventory from observed fills
    recs = collections.defaultdict(list); fh = open("strategy_fine.jsonl", "a"); t_end = time.time() + dur
    print(f"fine recorder | wallets={[w[:8] for w in wallets]} | {dur}s", flush=True)
    while time.time() < t_end:
        time.sleep(6)
        with lock:
            batch = list(buf); buf.clear(); snap = dict(tob); ix = dict(idx)
        for w, t in batch:
            if time.time() - int(t["timestamp"]) > 90:
                continue
            tok = str(t["asset"]); p = float(t["price"]); side = t["side"]; sz = float(t["size"])
            inv[(w, tok)] += sz if side == "BUY" else -sz
            meta = ix.get(tok)
            if not meta or tok not in snap:
                continue
            slug, is_up, tick, other, wsop, win = meta
            _, bb, bsz, ba, asz = snap[tok]
            if side == "BUY" and bb is not None:
                offset = round((bb - p) / tick, 1)        # 0 = at the bid; + = deeper in book
            elif side == "SELL" and ba is not None:
                offset = round((p - ba) / tick, 1)
            else:
                continue
            o = snap.get(other); oset = None
            if o and bb is not None and ba is not None and o[1] is not None and o[3] is not None:
                oset = round((bb + o[1]) if False else 0, 3)
            set_bid = round(bb + o[1], 3) if (o and bb is not None and o[1] is not None) else None
            set_ask = round(ba + o[3], 3) if (o and ba is not None and o[3] is not None) else None
            spread = round((ba - bb) / tick, 1) if (bb is not None and ba is not None) else None
            imb = round(bsz / (bsz + asz), 2) if (bsz + asz) > 0 else None
            rec = {"w": w[:8], "slug": slug[:18], "side": side, "p": p, "off_tk": offset, "sz": sz,
                   "set_bid": set_bid, "set_ask": set_ask, "spread_tk": spread, "imb": imb,
                   "sec": int(t["timestamp"]) - wsop, "win": win, "inv": round(inv[(w, tok)], 1)}
            recs[w].append(rec); fh.write(json.dumps(rec) + "\n")
        fh.flush()
        print(f"  t+{int(time.time())-start}s recorded={sum(len(v) for v in recs.values())}", flush=True)
    stop.set(); analyze(recs)


def modal(xs):
    if not xs:
        return None, 0.0
    c = collections.Counter(round(x, 1) for x in xs); v, n = c.most_common(1)[0]
    return v, n / len(xs)


def analyze(recs):
    print("\n=== EXACT-RULE CARDS (1:1 reconstruction from fills) ===")
    for w, rs in recs.items():
        if len(rs) < 15:
            print(f"\n{w[:10]}: only {len(rs)} fills -- need more"); continue
        offs = [r["off_tk"] for r in rs]; szs = [r["sz"] for r in rs]
        mo, mof = modal(offs); ms, msf = modal(szs)
        buys = [r for r in rs if r["side"] == "BUY"]; sells = [r for r in rs if r["side"] == "SELL"]
        sb = [r["set_bid"] for r in buys if r["set_bid"] is not None]
        print(f"\n{w[:10]} ({len(rs)} fills, {len(buys)}B/{len(sells)}S):")
        print(f"  placement offset from touch: modal {mo}tk ({100*mof:.0f}% of fills); "
              f"median {statistics.median(offs):.1f}tk  -> {'rests AT touch' if mo==0 and mof>0.5 else 'tiered'}")
        print(f"  size: modal {ms} sh ({100*msf:.0f}%); median {statistics.median(szs):.0f}  "
              f"-> {'FIXED clip' if msf>0.6 else 'variable'}")
        if sb:
            print(f"  complete-set BUY: bid_up+bid_dn median {statistics.median(sb):.3f} "
                  f"(p10 {sorted(sb)[len(sb)//10]:.3f}) -> buys the pair when sum ~< this")
        spr = [r["spread_tk"] for r in rs if r["spread_tk"] is not None]
        print(f"  spread at fill: median {statistics.median(spr):.0f}tk" if spr else "")
        # inventory skew: does side depend on current inventory sign?
        skew = sum(1 for r in rs if (r["side"] == "SELL") == (r["inv"] > 0)) / len(rs)
        print(f"  inventory mgmt: {100*skew:.0f}% of fills REDUCE |inventory| -> {'mean-reverting/skewed' if skew>0.6 else 'accumulating'}")


if __name__ == "__main__":
    main()
