"""copy_bot.py -- replicate a target MM's STRATEGY (not mirror their orders) and emit the quote set we
would place. DRY-RUN by default (prints + logs copy_orders.jsonl); live placement requires the same
guards as live_trader.py (own key, I_UNDERSTAND_REAL_MONEY=yes) and is intentionally NOT wired here.

WHY RULE-REPLICATION, NOT ORDER-MIRRORING (important, honest): Polymarket's public data exposes only
FILLS (executed trades) -- NOT other wallets' resting or cancelled LIMIT orders (those live off-chain in
the CLOB operator and are private until matched). So you CANNOT "vote their orders into the book before
they fill" from public data (Bullpen reads on-chain/fills too). The faithful copy is therefore to
reproduce their reverse-engineered RULE with our OWN quotes. For 0x20d2309cd9 (WALLET_20d2.md) that rule
is: two-sided on BOTH tokens of every active {btc,eth,sol,xrp}x{5m,15m} market; tiny clips (~$6); a
ladder of a few ticks around the touch; accumulate complete sets at a small discount; hold balanced sets
to resolution and redeem. Profile params below were measured from their tape; tune via copy_live.py.

    python copy_bot.py [seconds]        # DRY-RUN: prints the orders we'd place, logs copy_orders.jsonl
"""
from __future__ import annotations
import json, os, sys, time
import requests

G = "https://gamma-api.polymarket.com"; C = "https://clob.polymarket.com"

# --- strategy profile (measured from 0x20d2309cd9; see WALLET_20d2.md / MAKER_CHANGES.md) ---
PROFILE = {
    "assets": ["btc", "eth", "sol", "xrp"],
    "tenors": [5, 15],
    "depth_ticks": 3,          # quote a ladder this many ticks from each touch (their ~6 levels span)
    "clip_usd": 6.0,           # per-order notional (their median); scaled by position_multiplier
    "both_tokens": True,       # quote Up AND Down (two-sided complete-set accumulation)
    "buy_set_max": 1.00,       # only add to a leg if it keeps the complete-set buy-sum <= this (~discount)
    "hold_to_resolution": True, # don't flatten; balanced sets redeem to $1 (no merge gas)
    "max_per_market_usd": 50.0,
}
POSITION_MULT = float(os.environ.get("POSITION_MULTIPLIER", "1.0"))
LIVE = os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes" and "--live" in sys.argv


def book(sess, token):
    try:
        b = sess.get(C + "/book", params={"token_id": token}, timeout=6).json()
        bids, asks = b.get("bids", []), b.get("asks", [])
        return (float(bids[-1]["price"]) if bids else None, float(asks[-1]["price"]) if asks else None)
    except Exception:
        return None, None


def active_markets(sess):
    out = []; now = int(time.time())
    for a in PROFILE["assets"]:
        for tn in PROFILE["tenors"]:
            win = tn * 60; ws = now - (now % win)
            for cand in (ws, ws + win):
                try:
                    ev = sess.get(G + "/events", params={"slug": f"{a}-updown-{tn}m-{cand}"}, timeout=10).json()
                except Exception:
                    continue
                if ev and not ev[0]["markets"][0].get("closed"):
                    m = ev[0]["markets"][0]; tk = json.loads(m["clobTokenIds"])
                    out.append({"slug": m["slug"], "up": str(tk[0]), "dn": str(tk[1]),
                                "tick": float(m.get("orderPriceMinTickSize", 0.01) or 0.01)})
                    break
    return out


def quotes_for_market(sess, mk):
    """The orders the strategy would REST on this market right now (both tokens, ladder around touch)."""
    orders = []
    tick = mk["tick"]; clip = round(PROFILE["clip_usd"] * POSITION_MULT, 2)
    bbu, bau = book(sess, mk["up"]); bbd, bad = book(sess, mk["dn"])
    legs = [("up", mk["up"], bbu, bau), ("dn", mk["dn"], bbd, bad)]
    for name, tok, bb, ba in legs:
        if not PROFILE["both_tokens"] and name == "dn":
            continue
        for k in range(PROFILE["depth_ticks"]):           # BID ladder (add liquidity / accumulate cheap)
            if bb is None:
                break
            px = round(bb - k * tick, 4)
            if px <= 0:
                break
            orders.append({"slug": mk["slug"], "token": name, "side": "BUY", "price": px,
                           "size_usd": clip, "shares": round(clip / max(px, 1e-3), 1)})
        for k in range(PROFILE["depth_ticks"]):           # ASK ladder (offer the inventory back)
            if ba is None:
                break
            px = round(ba + k * tick, 4)
            if px >= 1:
                break
            orders.append({"slug": mk["slug"], "token": name, "side": "SELL", "price": px,
                           "size_usd": clip, "shares": round(clip / max(px, 1e-3), 1)})
    # complete-set discipline: only keep BID legs if the touch buy-set-sum is <= buy_set_max
    if bbu is not None and bbd is not None and (bbu + bbd) > PROFILE["buy_set_max"]:
        orders = [o for o in orders if o["side"] != "BUY"]
    return orders


def main():
    dur = int([a for a in sys.argv[1:] if a.isdigit()][0]) if any(a.isdigit() for a in sys.argv[1:]) else 60
    sess = requests.Session()
    fh = open("copy_orders.jsonl", "a")
    mode = "LIVE" if LIVE else "DRY-RUN"
    print(f"[{mode}] copy_bot pos_mult={POSITION_MULT} clip=${PROFILE['clip_usd']} depth={PROFILE['depth_ticks']}tk "
          f"assets={PROFILE['assets']} tenors={PROFILE['tenors']}")
    if LIVE:
        print("LIVE placement is NOT implemented in this scaffold by design -- wire it into live_trader.py's "
              "guarded place() on your own machine. Running DRY anyway.");
    t_end = time.time() + dur
    while time.time() < t_end:
        mkts = active_markets(sess)
        allo = []
        for mk in mkts:
            allo += quotes_for_market(sess, mk)
        snap = {"ts": int(time.time()), "n_markets": len(mkts), "n_orders": len(allo), "orders": allo}
        fh.write(json.dumps(snap) + "\n"); fh.flush()
        print(f"  t={time.strftime('%H:%M:%S')} markets={len(mkts)} -> would rest {len(allo)} orders "
              f"({sum(o['size_usd'] for o in allo):.0f} USDC notional, both sides, {PROFILE['depth_ticks']}-tk ladder)")
        time.sleep(max(3, (t_end - time.time()) / 4 if dur < 30 else 10))
    print("auto-redeem: when each market resolves, redeem the balanced set for $1 (on-chain; live-only).")
    print("see COPY_PROTOCOL.md for the live deployment checklist (keys, approve, websocket, caps).")


if __name__ == "__main__":
    main()
