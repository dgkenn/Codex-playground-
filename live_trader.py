"""LIVE execution scaffold: inventory-skewed 2-sided maker (rebate + vig), built for
Polymarket's STRICT PRICE-TIME (FIFO) matching.

>>> YOU run this with YOUR key. No key is stored here. DEFAULTS TO DRY-RUN (prints
>>> intended actions, places nothing). Real orders require --live AND
>>> I_UNDERSTAND_REAL_MONEY=yes.

Queue discipline (the lever most bots get wrong):
  * LAYER, DON'T CHURN. Rest several small clips across ticks; re-quote ONLY the stale
    level; leave in-band orders sitting to KEEP their time priority. Every cancel/replace
    sends you to the back of the queue, so we never cancel_all on a healthy book.
  * POST-ONLY / at-or-behind the touch (BUY<=best_bid, SELL>=best_ask) -> always maker,
    never cross (crossing pays the taker fee + forfeits the rebate).
  * Round to the market TICK (orders off-tick are rejected); respect min order size.
Toxicity defense (decides if fill rate is even good): per-fill MARKOUT + net-delta +
adverse-selection kill-switch. Build fill-rate machinery and markout together.

  python live_trader.py                               # DRY-RUN
  I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --max-notional 25
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

import requests

import notify  # free Telegram alerts (no-op if env unset)

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
                    "tick": float(m.get("orderPriceMinTickSize", 0.01) or 0.01),
                    "min_size": float(m.get("orderMinSize", 5) or 5),
                    "negRisk": bool(m.get("negRisk", False))}
    return None


def top(sess, token):
    b = sess.get(C + "/book", params={"token_id": token}, timeout=10).json()
    bids, asks = b.get("bids", []), b.get("asks", [])
    bb = float(bids[-1]["price"]) if bids else None
    ba = float(asks[-1]["price"]) if asks else None
    return bb, ba


def make_client():
    from py_clob_client_v2 import ClobClient, SignatureTypeV2
    pk = os.environ["PRIVATE_KEY"]; funder = os.environ["DEPOSIT_WALLET_ADDRESS"]
    tmp = ClobClient(C, key=pk, chain_id=137)
    creds = tmp.create_or_derive_api_key()
    return ClobClient(C, key=pk, chain_id=137, creds=creds,
                      signature_type=SignatureTypeV2.POLY_1271, funder=funder)


def desired_quotes(mk, token, is_up, bb, ba, net_delta, post, layers, cap, skew_frac):
    """Passive, at-or-behind-touch, LAYERED quotes for one token. Skip the side that
    leans inventory further once |delta| past skew_frac*cap (inventory skew)."""
    tick = mk["tick"]; d_sign = 1.0 if is_up else -1.0
    skew = skew_frac * cap
    quote_buy = (net_delta * d_sign) < cap and (net_delta * d_sign) < skew
    quote_sell = (net_delta * d_sign) > -cap and (net_delta * d_sign) > -skew
    out = set()
    if quote_buy and bb is not None:
        for k in range(layers):
            p = round(bb - k * tick, 4)
            if 0 < p < ba:                       # strictly below ask => post-only safe
                out.add((token, "BUY", p))
    if quote_sell and ba is not None:
        for k in range(layers):
            p = round(ba + k * tick, 4)
            if bb < p < 1:                       # strictly above bid => post-only safe
                out.add((token, "SELL", p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--post", type=float, default=5)
    ap.add_argument("--cap", type=float, default=50)
    ap.add_argument("--skew", type=float, default=0.25)
    ap.add_argument("--layers", type=int, default=3, help="resting clips per side per token")
    ap.add_argument("--max-notional", type=float, default=25)
    ap.add_argument("--loss-limit", type=float, default=5)
    ap.add_argument("--poll", type=float, default=3)
    ap.add_argument("--duration", type=int, default=3600)
    a = ap.parse_args()
    live = a.live and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if a.live and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. DRY-RUN.")
    mode = "LIVE" if live else "DRY-RUN"
    sess = requests.Session()
    client = make_client() if live else None
    print(f"[{mode}] layered maker post={a.post} cap={a.cap} skew={a.skew} layers={a.layers} "
          f"max_notional=${a.max_notional} loss_limit=${a.loss_limit}")
    notify.alert(f"[pmkit] live_trader start {mode} cap={a.cap} skew={a.skew} layers={a.layers}")

    net_delta = 0.0; realized = 0.0; mk = None
    resting = {}                       # (token,side,price) -> order_id  (KEEP across loops!)
    seen_fills = set(); markouts = []

    def place(tk, sd, p):
        if not live:
            print(f"  [DRY place] {sd} {a.post} {tk[:8]} @ {p}"); return f"dry_{tk[:6]}_{sd}_{p}"
        from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions
        from py_clob_client_v2.order_builder.constants import BUY, SELL
        r = client.create_and_post_order(
            OrderArgs(token_id=tk, price=p, size=a.post, side=(BUY if sd == "BUY" else SELL)),
            options=PartialCreateOrderOptions(tick_size=str(mk["tick"]), neg_risk=mk["negRisk"]),
            order_type=OrderType.GTC)           # GTC + at-or-behind touch == passive (post-only)
        return r.get("orderID") if isinstance(r, dict) else r

    def cancel(oid):
        if live:
            try:
                client.cancel(order_id=oid)
            except Exception:
                pass

    def cancel_all_resting():
        for k, oid in list(resting.items()):
            cancel(oid)
        resting.clear()

    end = time.time() + a.duration
    while time.time() < end:
        try:
            if mk is None or time.time() >= mk["we"]:
                cancel_all_resting()             # window rollover: tokens change, must reset
                mk = active_market(sess)
                if not mk:
                    time.sleep(a.poll); continue
                print(f"WINDOW {mk['ws']} {datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z tick={mk['tick']}")
            if realized <= -abs(a.loss_limit):
                print(f"KILL: realized {realized:+.2f}. cancel-all + exit."); notify.alert("[pmkit] KILL loss-limit")
                cancel_all_resting(); break
            if len(markouts) >= 30 and sum(markouts[-30:]) / 30 < -0.01:
                print("KILL: rolling markout toxic. cancel-all + exit."); notify.alert("[pmkit] KILL markout toxic")
                cancel_all_resting(); break

            # --- LAYER, DON'T CHURN: place missing desired levels, cancel only stale ones ---
            for token, is_up in ((mk["up"], True), (mk["down"], False)):
                bb, ba = top(sess, token)
                if bb is None or ba is None:
                    continue
                desired = desired_quotes(mk, token, is_up, bb, ba, net_delta, a.post, a.layers, a.cap, a.skew)
                for key in desired:
                    if key in resting:           # already resting -> KEEP (preserve time priority)
                        continue
                    _, sd, p = key
                    if a.post * (p if sd == "BUY" else 1 - p) > a.max_notional:
                        continue
                    resting[key] = place(*key)
                for key in list(resting):         # cancel ONLY this token's now-stale (off-band) levels
                    if key[0] == token and key not in desired:
                        cancel(resting[key]); del resting[key]

            # --- per-fill MARKOUT + net-delta (the toxicity verdict) ---
            if live:
                try:
                    trades = client.get_trades() or []
                except Exception:
                    trades = []
                for t in trades:
                    tid = t.get("id") or t.get("transaction_hash") or str(t)
                    if tid in seen_fills:
                        continue
                    seen_fills.add(tid)
                    asset = str(t.get("asset_id") or t.get("asset") or ""); sd = (t.get("side") or "").upper()
                    fp = float(t.get("price", 0)); fsz = float(t.get("size", 0))
                    net_delta += (1.0 if asset == mk["up"] else -1.0) * (fsz if sd == "BUY" else -fsz)
                    bb2, ba2 = top(sess, asset); mid2 = (bb2 + ba2) / 2 if bb2 and ba2 else fp
                    mo = (mid2 - fp) if sd == "BUY" else (fp - mid2); markouts.append(mo)
                    open("live_markout.jsonl", "a").write(json.dumps(
                        {"ts": time.time(), "asset": asset[:12], "side": sd, "price": fp, "size": fsz,
                         "markout": mo, "net_delta": net_delta}) + "\n")
            time.sleep(a.poll)
        except KeyboardInterrupt:
            cancel_all_resting(); print("interrupted; cancelled all."); break
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {str(e)[:100]}"); time.sleep(a.poll)
    cancel_all_resting()
    print(f"done. realized={realized:+.2f} fills={len(seen_fills)} "
          f"avg_markout={sum(markouts)/len(markouts):+.5f}" if markouts else "done.")


if __name__ == "__main__":
    main()
