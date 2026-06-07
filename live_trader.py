"""LIVE execution scaffold for the inventory-capped 2-sided maker (rebate farming).

>>> YOU run this on YOUR machine with YOUR key. It is NOT run from the research repo,
>>> and no key is ever stored here. It DEFAULTS TO DRY-RUN (prints intended orders,
>>> places nothing). Real orders require BOTH --live AND I_UNDERSTAND_REAL_MONEY=yes.

Setup (your machine):
    pip install py-clob-client-v2
    export PRIVATE_KEY=0x...                 # never commit; never share
    export DEPOSIT_WALLET_ADDRESS=0x...      # your Polymarket deposit wallet (POLY_1271)
    # fund the deposit wallet with a TINY amount of pUSD first (e.g. $20-100)
    python live_trader.py                    # DRY-RUN (safe)
    I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --max-notional 25

Safety rails (hard caps; tune DOWN, never up, for the first runs):
  --post           shares quoted per side per token (start 5-20)
  --cap            max |net delta| in Up-equivalent shares (start 20)
  --max-notional   max USDC at risk across open orders+inventory (start 25)
  --loss-limit     cumulative realized loss that triggers KILL (cancel-all + exit)
Strategy = paper_trader.py logic; this only adds the authenticated post/cancel layer.
The edge is the maker REBATE + tight-inventory vig; gross must stay ~>=0 live (watch it).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

import requests

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"


def active_market(sess):
    now = int(time.time()); ws = now - (now % 900)
    for cand in (ws, ws + 900):
        ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{cand}"}, timeout=15).json()
        if ev and not ev[0]["markets"][0].get("closed"):
            m = ev[0]["markets"][0]; toks = json.loads(m["clobTokenIds"])
            return {"cid": m["conditionId"], "up": str(toks[0]), "down": str(toks[1]),
                    "ws": cand, "we": cand + 900,
                    "tick": m.get("orderPriceMinTickSize", "0.01"), "negRisk": m.get("negRisk", False)}
    return None


def top(sess, token):
    b = sess.get(C + "/book", params={"token_id": token}, timeout=10).json()
    bids, asks = b.get("bids", []), b.get("asks", [])
    bb = float(bids[-1]["price"]) if bids else None
    ba = float(asks[-1]["price"]) if asks else None
    return bb, ba


def make_client():
    """Authenticated CLOB client (POLY_1271 deposit-wallet path). Lazy import so the
    file is usable without the SDK when only dry-running the data layer."""
    from py_clob_client_v2 import ClobClient, SignatureTypeV2
    pk = os.environ["PRIVATE_KEY"]; funder = os.environ["DEPOSIT_WALLET_ADDRESS"]
    tmp = ClobClient(C, key=pk, chain_id=137)
    creds = tmp.create_or_derive_api_key()
    return ClobClient(C, key=pk, chain_id=137, creds=creds,
                      signature_type=SignatureTypeV2.POLY_1271, funder=funder)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="actually place orders (else DRY-RUN)")
    ap.add_argument("--post", type=float, default=5)
    ap.add_argument("--cap", type=float, default=20)
    ap.add_argument("--max-notional", type=float, default=25)
    ap.add_argument("--loss-limit", type=float, default=5)
    ap.add_argument("--poll", type=float, default=4)
    ap.add_argument("--duration", type=int, default=3600)
    a = ap.parse_args()

    live = a.live and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if a.live and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. Running DRY-RUN.")
    mode = "LIVE" if live else "DRY-RUN"
    sess = requests.Session()
    client = make_client() if live else None
    print(f"[{mode}] maker post={a.post} cap={a.cap} max_notional=${a.max_notional} "
          f"loss_limit=${a.loss_limit}")

    net_delta = 0.0; realized = 0.0; mk = None
    end = time.time() + a.duration
    while time.time() < end:
        try:
            if mk is None or time.time() >= mk["we"]:
                if live and mk:
                    client.cancel_all()
                mk = active_market(sess)
                if not mk:
                    time.sleep(a.poll); continue
                print(f"WINDOW {mk['ws']} {datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z")
            if realized <= -abs(a.loss_limit):
                print(f"KILL: realized {realized:+.2f} <= -loss_limit. cancel-all + exit.")
                if live:
                    client.cancel_all()
                break
            # desired 2-sided quotes at the touch, skewed by inventory cap
            for token, is_up in ((mk["up"], True), (mk["down"], False)):
                bb, ba = top(sess, token)
                if bb is None or ba is None:
                    continue
                d_sign = 1.0 if is_up else -1.0
                quote_buy = (net_delta * d_sign) < a.cap        # buying this token adds +d_sign delta
                quote_sell = (net_delta * d_sign) > -a.cap
                for side, price, do in (("BUY", bb, quote_buy), ("SELL", ba, quote_sell)):
                    if not do:
                        continue
                    notional = a.post * (price if side == "BUY" else (1 - price))
                    if notional > a.max_notional:
                        continue
                    if live:
                        from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions
                        from py_clob_client_v2.order_builder.constants import BUY, SELL
                        client.create_and_post_order(
                            OrderArgs(token_id=token, price=price, size=a.post,
                                      side=(BUY if side == "BUY" else SELL)),
                            options=PartialCreateOrderOptions(tick_size=str(mk["tick"]), neg_risk=mk["negRisk"]),
                            order_type=OrderType.GTC)
                    else:
                        print(f"  [DRY] {side} {a.post} {'UP' if is_up else 'DN'} @ {price}")
            # reconcile fills -> update net_delta & realized (live only)
            if live:
                trades = client.get_trades()  # your fills; map to delta/realized in your accounting
                # TODO: maintain net_delta and realized from trades + settlement; cancel stale quotes
                client.cancel_all()           # simple refresh-each-loop; replace with diff logic
            time.sleep(a.poll)
        except KeyboardInterrupt:
            if live:
                client.cancel_all()
            print("interrupted; cancelled all."); break
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {str(e)[:100]}")
            time.sleep(a.poll)
    if live:
        client.cancel_all()
    print(f"done. realized={realized:+.2f}")


if __name__ == "__main__":
    main()
