"""LIVE execution scaffold: inventory-skewed 2-sided maker (rebate + vig) with
FAIR-VALUE PREDICTIVE REPRICING, built for Polymarket's STRICT PRICE-TIME (FIFO) match.

>>> YOU run this with YOUR key. No key is stored here. DEFAULTS TO DRY-RUN (prints
>>> intended actions, places nothing). Real orders require --live AND
>>> I_UNDERSTAND_REAL_MONEY=yes.

Two layers:
  STANDING LADDER (P1: the front of the book is sacred). Rest a band of small post-only clips
    per side; once an order ages past --age-protect it has accrued queue priority and is SACRED
    -- never reflexively repriced even if the touch drifts off it (a touch that moves back into
    an aged rung = a front-of-queue FILL, which is the whole point). All reshaping/risk is done
    at the YOUNGEST/outer rungs; the rung cap evicts the rungs FARTHEST from the touch (manage
    from the back). This is the difference our queue_sim measured between -$5/win (reprice every
    move, live at the back) and +$55/win (hold, advance via FIFO to the front).
  EV-GATED CANCEL (P2: cancellation is an EV decision, not a reflex). An aged front rung is an
    asset worth ~half a spread (Moallemi); we pull it only when toxicity beats that queue value
    -- i.e. a YOUNG toxic order is pulled, but an AGED one only on a SEVERE move (edge >
    toxic_severe*fv_margin). Knowing when NOT to cancel is the skill.
  OVERLAY (the one lever the backtest could not score -- FINDINGS.md "Tier 1"): a SPOT
    fair-value model (fvfeed.SpotFair) drives PREDICTIVE PULLS -- cancel a resting level
    the model says is about to be picked off, BEFORE the informed taker arrives. This is
    TIMING, not fill-selection (fill-selection/gating was tested and retired). The whole
    experiment is whether moving ahead of the taker earns more than the QUEUE PRIORITY it
    burns (Cartea-Sanchez-Betancourt shadow-price-of-latency), so we instrument both sides:

    reprice_log.jsonl, per model pull:
      (a) the cancel intended (token, side, old price, order id)
      (b) cancel-sent vs cancel-confirmed timestamps -> time_to_cancel_ms
      (c) did a taker hit the OLD quote anyway, and BEFORE our cancel confirmed (too slow)
      (d) resolution markout of the fill we avoided vs the fill at the new (clamped) quote
      + queue position SURRENDERED (size resting ahead of us at that level when we pulled)
      + clamp_bind events: the model wanted to quote outside the book band (kept = finding)

  The model quote is CLAMPED to within --fv-band ticks of the touch: near expiry the logit
  is vertical, a small spot tick swings p_up hard, and an unclamped reprice walks the quote
  into no-depth/toxic territory. If the spot feed is down the overlay disables itself and
  the bot runs the validated baseline (never quotes off a stale model).

PRE-WRITTEN INTERPRETATION (decide before reading numbers, same discipline as Tier 1):
  * If net P&L is a WASH but time_to_cancel >> the interval between (c) "taker hit old" and
    our cancel-confirmed -> repricing is SOUND BUT TOO SLOW; the decision is whether to buy
    the latency (faster colo/cancel path). The time_to_cancel log, not P&L, is that verdict.
  * If clamp binds constantly -> model and book disagree structurally on this market; that
    is a finding about calibration, not a tuning nuisance.
  * If pulls dodge settle-negative fills (d) by more than the queue (surrendered + forgone
    fills) they cost -> repricing earns its keep. Else retire it too and keep the baseline.
  SCOPE: validated offline on BTC 15m, one OOS split. A good pilot result here is
  "live-plausible on this market", NOT "generalizes".

  python live_trader.py                               # DRY-RUN (baseline + overlay sim)
  python live_trader.py --no-reprice                  # DRY-RUN baseline only
  I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --max-notional 25
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import threading
import time
from collections import deque
from datetime import datetime, timezone

import requests

import netfast  # latency-tuned keep-alive session (NODELAY/KEEPALIVE, warm pool) for the hot path
import notify  # free Telegram alerts (no-op if env unset)
import collateral  # ROADMAP #1 mint/merge primitive (on-chain CTF; live-only)
from fvfeed import SpotFair

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"
WS_MARKET = "wss://ws-subscriptions-clob.polymarket.com/ws/market"   # public book deltas (no auth)
DEPLETE_FRAC = 0.35   # queue-jump depletion trigger: best queue < this * its EMA => about to deplete


def active_market(sess, asset="btc", tenor_min=15):
    """Active {asset}-updown-{tenor_min}m market (breadth-ready; defaults to BTC 15m)."""
    win = tenor_min * 60
    now = int(time.time()); ws = now - (now % win)
    for cand in (ws, ws + win):
        ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-{tenor_min}m-{cand}"}, timeout=15).json()
        if ev and not ev[0]["markets"][0].get("closed"):
            m = ev[0]["markets"][0]; toks = json.loads(m["clobTokenIds"])
            return {"cid": m["conditionId"], "up": str(toks[0]), "down": str(toks[1]),
                    "ws": cand, "we": cand + win,
                    "tick": float(m.get("orderPriceMinTickSize", 0.01) or 0.01),
                    "min_size": float(m.get("orderMinSize", 5) or 5),
                    "negRisk": bool(m.get("negRisk", False))}
    return None


def book(sess, token):
    """Return (best_bid, best_ask, bid_size_at_touch, ask_size_at_touch)."""
    b = sess.get(C + "/book", params={"token_id": token}, timeout=10).json()
    bids, asks = b.get("bids", []), b.get("asks", [])
    bb = float(bids[-1]["price"]) if bids else None
    ba = float(asks[-1]["price"]) if asks else None
    bsz = float(bids[-1]["size"]) if bids else 0.0
    asz = float(asks[-1]["size"]) if asks else 0.0
    return bb, ba, bsz, asz


def resolve(sess, ws, asset="btc", tenor_min=15):
    try:
        ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-{tenor_min}m-{ws}"}, timeout=10).json()
        if ev:
            m = ev[0]["markets"][0]; op = m.get("outcomePrices")
            if m.get("closed") and op:
                op = json.loads(op) if isinstance(op, str) else op
                return 1 if float(op[0]) > 0.5 else 0
    except Exception:
        pass
    return None


def microprice(bb, ba, bsz, asz):
    """Stoikov micro-price, first-order (imbalance-weighted) form: the expected next-tick fair
    value of THIS token's own book given depth imbalance -- NOT a forecast of BTC (that's dead,
    R^2~0). micro -> ask under buy pressure (bsz>>asz), -> bid under sell pressure. Repricing
    against this instead of the stale mid gives adverse-selection aversion: you step off the
    side the book is about to leave. Book-native, always available (degrades better than the
    spot model). See LIVE_DESIGN.md #4 (Stoikov)."""
    if bb is None or ba is None:
        return None
    tot = (bsz or 0) + (asz or 0)
    if tot <= 0:
        return (bb + ba) / 2.0
    imb = (bsz or 0) / tot                       # share of size on the bid = buy pressure
    return bb + (ba - bb) * imb


def would_cross(side, price, bb, ba):
    """A3 (accidental-taker guard): a resting order must NOT be marketable, or it pays the taker fee
    (~3% peak) and instantly flips the rebate edge negative. A BUY at/above the best ask crosses; a
    SELL at/below the best bid crosses. We quote at-or-behind the touch by construction, but a STALE
    book snapshot (the touch moved between read and post) can produce a crosser -- this is the last-line
    guarantee that every live order is post-only/maker, independent of any SDK post-only flag. (On the
    live box, ALSO set the venue's post-only order option if the SDK exposes one -- belt and suspenders.)"""
    if bb is None or ba is None:
        return False
    return (side == "BUY" and price >= ba) or (side == "SELL" and price <= bb)


def clob_selfcheck(sess, n=8):
    """Startup latency gate: time real HTTPS round-trips to the CLOB (warm, keep-alive) and verdict
    whether we are co-located. The CLOB matches in AWS eu-west-2 (London); sub-100ms end-to-end is
    impossible if the order POST itself is >~80ms (you're transatlantic). Prints median round-trip so
    the operator KNOWS their seat before trading. ICMP ping is useless here (Cloudflare edge); real."""
    ts = []
    for _ in range(n):
        t0 = time.time()
        try:
            sess.get(C + "/time", timeout=5)        # tiny warm request on the pooled keep-alive socket
            ts.append((time.time() - t0) * 1e3)
        except Exception:
            pass
    if not ts:
        print("  [latency] CLOB self-check FAILED (no response)"); return None
    ts.sort(); med = ts[len(ts) // 2]
    p95 = ts[min(len(ts) - 1, int(len(ts) * 0.95))]
    p99 = ts[min(len(ts) - 1, int(len(ts) * 0.99))]
    if med < 25:
        v = "co-located (eu-west-2/Dublin) -- sub-100ms reachable"
    elif med < 80:
        v = "near-region -- tighten with keep-alive/pre-sign for sub-100ms"
    else:
        v = "CROSS-REGION (likely transatlantic) -- sub-100ms UNREACHABLE; co-locate in eu-west-2"
    # p99, not mean, is what loses queue races (point 5) -- a single slow POST = back of the line.
    print(f"  [latency] CLOB round-trip median {med:.0f} ms  p95 {p95:.0f}  p99 {p99:.0f} "
          f"({len(ts)}/{n} ok) -> {v}")
    return med


def btc_lead_feeder(live_btc):
    """BTC lead signal for queue positioning (feed_race: BTC leads the token ~0.5s). PRIMARY source is
    Polymarket RTDS (chainlink btc/usd = settlement truth + binance btcusdt = higher-freq), served from
    eu-west-2 co-located with the CLOB: in-region (no transatlantic hop) and zero basis risk. Coinbase
    WS is the gap-filler when RTDS is silent >3s. Both update live_btc{px,ts,hist,src}; websockets
    imported lazily so the OMS still runs without it (lead OFF)."""
    import asyncio
    try:
        import websockets
    except Exception:
        print("  [queue-jump] websockets not installed -> lead feed OFF (queue-jump no-op)"); return

    def push(px):                              # common path: update px + 60s rolling history
        t = time.time(); live_btc["px"] = px; live_btc["ts"] = t
        h = live_btc["hist"]; h.append((t, px))
        while h and h[0][0] < t - 60:
            h.popleft()

    async def rtds():                          # PRIMARY: in-region Chainlink+Binance settlement feed
        url = "wss://ws-live-data.polymarket.com"
        sub = json.dumps({"action": "subscribe", "subscriptions": [
            {"topic": "crypto_prices_chainlink", "type": "*", "filters": "{\"symbol\":\"btc/usd\"}"},
            {"topic": "crypto_prices", "type": "*", "filters": "{\"symbol\":\"btcusdt\"}"}]})
        while True:
            try:
                async with websockets.connect(url, ping_interval=15, ping_timeout=20) as ws:
                    await ws.send(sub)
                    async for raw in ws:
                        if not raw:                              # empty ack frame -> keep the conn alive
                            continue
                        try:
                            pl = (json.loads(raw).get("payload") or {})
                        except Exception:
                            continue
                        val = pl.get("value")
                        if val is None and isinstance(pl.get("data"), list) and pl["data"]:
                            val = pl["data"][-1].get("value")    # bulk history frame -> seed latest point
                        if val is not None:
                            live_btc["rtds_ts"] = time.time(); live_btc["src"] = "rtds"; push(float(val))
            except Exception:
                await asyncio.sleep(2)

    async def coinbase():                       # FALLBACK: defers to RTDS while it is fresh
        sub = json.dumps({"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]})
        while True:
            try:
                async with websockets.connect("wss://ws-feed.exchange.coinbase.com",
                                              ping_interval=15, ping_timeout=20) as ws:
                    await ws.send(sub)
                    async for raw in ws:
                        m = json.loads(raw)
                        if m.get("type") == "ticker" and m.get("price"):
                            if time.time() - live_btc.get("rtds_ts", 0.0) <= 3.0:
                                continue           # RTDS fresh -> defer
                            live_btc["src"] = "cb"; push(float(m["price"]))
            except Exception:
                await asyncio.sleep(2)

    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.gather(rtds(), coinbase()))


def book_feeder(books, mdsub):
    """SUB-10ms BOOK PATH (LATENCY.md #1/#6): stream the token order books off the public CLOB market WS
    instead of REST-polling /book every loop. Maintains books[token] = {bb,ba,bsz,asz,ts}; the OMS reads
    this in-memory cache so a quote-pull reacts to a toxic move in WS time (ms), not on the REST poll (s).
    Resubscribes when the window rolls (mdsub['epoch'] bumps with the new tokens). Mirrors the validated
    shadow_compare book/price_change parsing. websockets imported lazily -> OMS still runs (REST fallback)
    if it's missing."""
    import asyncio
    try:
        import websockets
    except Exception:
        print("  [ws-book] websockets not installed -> book feed OFF (REST fallback only)"); return

    async def run():
        while True:
            toks = list(mdsub.get("tokens") or [])
            epoch = mdsub.get("epoch")
            if not toks:
                await asyncio.sleep(0.2); continue
            try:
                async with websockets.connect(WS_MARKET, ping_interval=10, ping_timeout=20, max_size=None) as ws:
                    await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                    async for raw in ws:
                        if mdsub.get("epoch") != epoch:
                            break                                   # window rolled -> reconnect w/ new tokens
                        if not raw:
                            continue
                        try:
                            data = json.loads(raw)
                        except Exception:
                            continue
                        for m in (data if isinstance(data, list) else [data]):
                            et = m.get("event_type")
                            if et == "book":
                                tok = str(m["asset_id"]); bids = m.get("bids") or []; asks = m.get("asks") or []
                                bb = max((float(b["price"]) for b in bids), default=None)
                                ba = min((float(a["price"]) for a in asks), default=None)
                                bsz = sum(float(b["size"]) for b in bids if bb is not None and float(b["price"]) == bb)
                                asz = sum(float(a["size"]) for a in asks if ba is not None and float(a["price"]) == ba)
                                books[tok] = {"bb": bb, "ba": ba, "bsz": bsz, "asz": asz, "ts": time.time()}
                            elif et == "price_change":
                                for pc in m.get("price_changes", []):
                                    tok = str(pc["asset_id"]); cur = books.get(tok)
                                    if cur is None:
                                        continue
                                    bb = float(pc["best_bid"]) if pc.get("best_bid") not in (None, "") else cur["bb"]
                                    ba = float(pc["best_ask"]) if pc.get("best_ask") not in (None, "") else cur["ba"]
                                    books[tok] = {"bb": bb, "ba": ba, "bsz": cur["bsz"], "asz": cur["asz"], "ts": time.time()}
            except Exception:
                await asyncio.sleep(1)

    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(run())


def btc_lead(live_btc, lag_s):
    """Signed BTC move ($) over the last lag_s seconds; 0 if no/stale feed."""
    h = live_btc.get("hist"); px = live_btc.get("px")
    if not h or px is None:
        return 0.0
    now = time.time(); prev = None
    for (t, p) in h:
        if t <= now - lag_s:
            prev = p
    if prev is None:
        prev = h[0][1]
    return px - prev


def make_client():
    from py_clob_client_v2 import ClobClient, SignatureTypeV2
    pk = os.environ["PRIVATE_KEY"]; funder = os.environ["DEPOSIT_WALLET_ADDRESS"]
    tmp = ClobClient(C, key=pk, chain_id=137)
    creds = tmp.create_or_derive_api_key()
    return ClobClient(C, key=pk, chain_id=137, creds=creds,
                      signature_type=SignatureTypeV2.POLY_1271, funder=funder)


def baseline_levels(mk, token, is_up, bb, ba, net_delta, layers, cap, skew_frac, improve=False):
    """Validated passive, at-or-behind-touch, LAYERED quotes for one token, inventory skewed.
    Returns set of (token, side, price).

    QUEUE PRIORITY (point 1): with `improve`, when the spread is >= 2 ticks we ALSO emit a quote one tick
    INSIDE the touch (bb+tick / ba-tick). Polymarket is price-time priority, so a better price jumps the
    ENTIRE queue at the touch -> instant front-of-line. It's still post-only (never crosses) and is gated
    downstream by model_filter's toxicity test, so we only actually improve on the side the microprice says
    is benign (improving the toxic side would just win adverse races). No-op on a 1-tick book (nothing to
    improve into)."""
    tick = mk["tick"]; d_sign = 1.0 if is_up else -1.0
    skew = skew_frac * cap
    quote_buy = (net_delta * d_sign) < cap and (net_delta * d_sign) < skew
    quote_sell = (net_delta * d_sign) > -cap and (net_delta * d_sign) > -skew
    out = set()
    wide = (bb is not None and ba is not None and (ba - bb) >= 2 * tick - 1e-9)   # room to step inside
    if quote_buy and bb is not None:
        if improve and wide:
            p = round(bb + tick, 4)
            if 0 < p < ba:
                out.add((token, "BUY", p))                # one tick inside -> front of the bid queue
        for k in range(layers):
            p = round(bb - k * tick, 4)
            if 0 < p < ba:
                out.add((token, "BUY", p))
    if quote_sell and ba is not None:
        if improve and wide:
            p = round(ba - tick, 4)
            if bb < p < 1:
                out.add((token, "SELL", p))               # one tick inside -> front of the ask queue
        for k in range(layers):
            p = round(ba + k * tick, 4)
            if bb < p < 1:
                out.add((token, "SELL", p))
    return out


def model_filter(levels, fair_tok, margin, bb, ba, band_px, rlog, token):
    """Split baseline levels into (safe_desired, model_suppressed) using the spot fair
    value. A resting SELL at p is toxic if p < fair_tok + margin (we'd sell below value);
    a BUY at p is toxic if p > fair_tok - margin. Also flags clamp binds: the model wants
    to quote outside the +/-band_px window around the touch. fair_tok None -> no overlay."""
    if fair_tok is None:
        return levels, set()
    safe, suppressed = set(), set()
    sell_floor = fair_tok + margin       # only willing to sell at/above this
    buy_ceil = fair_tok - margin         # only willing to buy at/below this
    if ba is not None and sell_floor > ba + band_px:
        rlog.clamp_bind(token, "SELL", sell_floor, ba + band_px)
    if bb is not None and buy_ceil < bb - band_px:
        rlog.clamp_bind(token, "BUY", buy_ceil, bb - band_px)
    for key in levels:
        _, sd, p = key
        toxic = (sd == "SELL" and p < sell_floor) or (sd == "BUY" and p > buy_ceil)
        (suppressed if toxic else safe).add(key)
    return safe, suppressed


class RepriceLog:
    """Counterfactual + latency + queue instrumentation for the predictive-reprice
    experiment. Everything the pilot needs to answer shadow-price-of-latency lives here."""

    def __init__(self, path="reprice_log.jsonl"):
        self.fh = open(path, "a")
        self.open_pulls = []     # pulls awaiting (c) taker-hit / (d) settle attribution
        self.clamp_binds = 0; self.pulls = 0

    def _w(self, o):
        o["ts"] = time.time(); self.fh.write(json.dumps(o) + "\n"); self.fh.flush()

    def clamp_bind(self, token, side, model_price, clamped_price):
        self.clamp_binds += 1
        self._w({"type": "clamp_bind", "token": token[:12], "side": side,
                 "model_price": round(model_price, 4), "clamped_price": round(clamped_price, 4)})

    def pull(self, token, side, price, oid, t_sent, t_confirmed, queue_ahead, fair_tok, ws):
        """(a)+(b)+queue-surrendered. Held open for (c)/(d)."""
        self.pulls += 1
        ttc = None if (t_confirmed is None) else round((t_confirmed - t_sent) * 1000, 1)
        rec = {"type": "pull", "ws": ws, "token": token[:12], "side": side,
               "old_price": round(price, 4), "order_id": str(oid)[:24],
               "cancel_sent": t_sent, "cancel_confirmed": t_confirmed,
               "time_to_cancel_ms": ttc, "queue_ahead_surrendered": round(queue_ahead, 2),
               "fair_token": round(fair_tok, 4), "taker_hit_old": None,
               "hit_before_confirm": None, "avoided_resolution_markout": None}
        self._w(rec)
        self.open_pulls.append(rec)

    def attribute_trade(self, token, side, price, ts):
        """(c) did a taker hit the OLD quote we pulled, and before our cancel confirmed?
        A pull of OUR SELL@p is hit by a taker BUY@p; OUR BUY@p by a taker SELL@p."""
        for r in self.open_pulls:
            if r["taker_hit_old"]:
                continue
            opp = "BUY" if r["side"] == "SELL" else "SELL"
            if r["token"] == token[:12] and side == opp and abs(price - r["old_price"]) < 1e-9:
                r["taker_hit_old"] = True
                r["hit_before_confirm"] = (r["cancel_confirmed"] is None) or (ts < r["cancel_confirmed"])
                self._w({"type": "pull_update", **{k: r[k] for k in
                         ("token", "side", "old_price", "taker_hit_old", "hit_before_confirm")}})

    def settle(self, ws, token, settle_value):
        """(d) resolution markout of the fill we AVOIDED, for pulls in this window that a
        taker actually hit (so the avoided fill was real). SELL@p avoided -> we did NOT
        sell something worth settle_value, so avoiding it was +(p-settle); a BUY@p avoided
        -> +(settle-p)? No: avoiding a BUY means we did NOT buy, so the avoided-fill markout
        (what skipping earned us) = (p - settle) for a SELL... track the avoided fill's OWN
        markout = settle - p if it was a SELL-we-avoided being short, etc. We log the fill's
        resolution P&L had we taken it; negative => the pull correctly dodged a loser."""
        for r in self.open_pulls[:]:
            if r["ws"] != ws or token[:12] != r["token"]:
                continue
            p = r["old_price"]
            # had we filled: SELL@p -> P&L = p - settle_value ; BUY@p -> settle_value - p
            avoided = (p - settle_value) if r["side"] == "SELL" else (settle_value - p)
            r["avoided_resolution_markout"] = round(avoided, 4)
            self._w({"type": "pull_settle", "token": r["token"], "side": r["side"],
                     "old_price": p, "taker_hit_old": bool(r["taker_hit_old"]),
                     "avoided_fill_pnl_to_resolution": r["avoided_resolution_markout"],
                     "note": "negative => pull dodged a settle-loser; positive => pull cost us a winner"})
            self.open_pulls.remove(r)

    def summary(self):
        return {"pulls": self.pulls, "clamp_binds": self.clamp_binds}


class OrderLog:
    """Per-order lifecycle + fill ground-truth capture (CAPTURE.md #1/#2). order_log.jsonl =
    placement context+latency and terminal state; fills_log.jsonl = fills with trader-side/fee/
    queue residence. This is the data that can't be reconstructed after the fact."""

    def __init__(self, opath="order_log.jsonl", fpath="fills_log.jsonl"):
        self.ofh = open(opath, "a"); self.ffh = open(fpath, "a"); self.n = 0

    def placed(self, oid, decision_ts, ack_ts, **ctx):
        """Full context at post: queue_depth_ahead (THE field), mid/micro/spread/spot/tau."""
        self.n += 1
        rec = {"type": "place", "oid": str(oid)[:24], "decision_ts": decision_ts, "ack_ts": ack_ts,
               "placement_latency_ms": round((ack_ts - decision_ts) * 1000, 1), **ctx,
               "log_ts": time.time()}
        self.ofh.write(json.dumps(rec) + "\n"); self.ofh.flush()

    def terminal(self, oid, state, reason, resting_s):
        self.ofh.write(json.dumps({"type": "terminal", "oid": str(oid)[:24], "state": state,
                       "reason": reason, "resting_s": round(resting_s, 2), "log_ts": time.time()}) + "\n")
        self.ofh.flush()

    def fill(self, oid, asset, taker_side, price, size, trader_side, fee_bps, resting_s, q_ahead,
             markout, source):
        self.ffh.write(json.dumps({"type": "fill", "oid": str(oid)[:24], "asset": str(asset)[:12],
                       "taker_side": taker_side, "trader_side": trader_side, "fee_bps": fee_bps,
                       "price": price, "size": size, "source": source,
                       "time_resting_s": round(resting_s, 2) if resting_s is not None else None,
                       "queue_ahead_at_post": q_ahead, "markout_5s": markout,
                       "log_ts": time.time()}) + "\n")
        self.ffh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--post", type=float, default=5)
    ap.add_argument("--cap", type=float, default=50)
    ap.add_argument("--skew", type=float, default=0.25)
    ap.add_argument("--layers", type=int, default=3, help="resting clips per side per token")
    ap.add_argument("--age-protect", type=float, default=20.0,
                    help="P1: an order older than this (s) has accrued queue priority -> SACRED, "
                         "never cancelled by reshaping; only an EV-severe toxic move pulls it")
    ap.add_argument("--max-rungs", type=int, default=5, help="max resting rungs per side (cap capital); "
                    "over-cap evicts the rungs FARTHEST from the touch (manage from the back)")
    ap.add_argument("--toxic-severe", type=float, default=2.0,
                    help="P2: pull an AGED front rung only if fair has crossed it by > toxic_severe "
                         "TICKS (a strong/informed move that beats the queue value); benign 1-tick "
                         "crossings are held so the front-of-queue fill happens")
    ap.add_argument("--reprice", action=argparse.BooleanOptionalAction, default=True,
                    help="fair-value predictive repricing overlay (--no-reprice = baseline only)")
    ap.add_argument("--fv-margin", type=float, default=0.0, help="toxic only when fair crosses the "
                    "quote by this much (0 = strictly crossed; >0 adds a buffer). Anchored to the "
                    "book microprice, which sits inside a 1c spread, so this must be ~0 or nothing quotes")
    ap.add_argument("--fv-band", type=int, default=2, help="max ticks the model quote may sit off the touch")
    ap.add_argument("--spot-symbol", default="BTCUSDT")
    ap.add_argument("--max-notional", type=float, default=25)
    ap.add_argument("--loss-limit", type=float, default=5)
    ap.add_argument("--poll", type=float, default=1.0, help="HOUSEKEEPING cadence (s): fv refresh + fills "
                    "poll + REST book fallback. The fast quote-decision loop runs at --react-poll on the WS book.")
    ap.add_argument("--react-poll", type=float, default=0.1, help="REACTION cadence (s): how often the quote "
                    "loop re-decides against the WS book cache. Sub-10ms reaction needs this small + a colo box.")
    ap.add_argument("--asset", default="btc", help="btc/eth/sol/xrp (breadth; run one instance per market)")
    ap.add_argument("--tenor-min", type=int, default=15, help="market tenor minutes (15 or 5)")
    ap.add_argument("--duration", type=int, default=3600)
    # QUEUE-POSITIONING A/B (live-only test; QUEUE.md). Arm A: lead-aware standing-rung priority --
    # on a fast BTC move, HOLD aged rungs on the side the book is moving toward (front-of-queue when
    # the touch arrives) and SHED the side it's leaving. Arm B (default) = the at-touch control.
    ap.add_argument("--queue-jump", action="store_true", help="Arm A: BTC-lead-aware rung protection/shed")
    ap.add_argument("--jump-bps", type=float, default=2.0, help="|BTC move| over jump-lag (bps of spot) to act")
    ap.add_argument("--jump-lag", type=float, default=2.0, help="BTC lookback seconds (~ the measured lead)")
    # BOX-ARB mode: direction-free/fee-free complete-set capture. Sell BOTH legs when ask_up+ask_dn>1
    # (source via on-chain split), or buy both when bid_up+bid_dn<1 (merge after). Risk-free when both fill.
    ap.add_argument("--box-arb", action="store_true", help="run the complete-set box-arb instead of the ladder")
    ap.add_argument("--box-margin", type=float, default=0.0, help="min box premium/set to act (0 = any >touch)")
    ap.add_argument("--box-sets", type=float, default=5.0, help="sets per box opportunity")
    ap.add_argument("--presign", action="store_true", help="pre-sign touch-band orders during idle so "
                    "placing a new rung is a pure POST (signing OFF the fire path). Sub-10ms enabler; "
                    "live-only, falls back to create_and_post_order on any miss. VERIFY on a burner first.")
    ap.add_argument("--deadman-s", type=float, default=15.0, help="DEAD-MAN switch (C1): if the order "
                    "book feed goes stale for this many seconds (venue/network down -> we'd be holding "
                    "resting orders blind), cancel ALL resting orders. Also fires on an error storm.")
    # --- QUEUE PRIORITY levers (QUEUE_PRIORITY.md) ---
    ap.add_argument("--improve", action="store_true", help="P1: when spread>=2 ticks, post one tick INSIDE "
                    "the touch on the BENIGN side (price-time priority -> jump the whole queue). Gated by "
                    "the toxicity overlay so we never improve into the side the book is leaving.")
    ap.add_argument("--min-rest-s", type=float, default=2.0, help="P2: never cancel a resting order younger "
                    "than this for NON-toxic reasons (reshape/reprice). Stops the 0.1s react loop from "
                    "churning away queue priority on transient book flicker; toxic-severe pulls still fire.")
    ap.add_argument("--presign-depth", type=int, default=0, help="P3: pre-sign this many EXTRA levels each "
                    "side beyond the quoted band (+ the inside-touch improve level) so a touch move fires "
                    "at the new level with zero signing on the path. live+--presign only.")
    ap.add_argument("--max-queue-ahead", type=float, default=0.0, help="P4: skip posting at a level whose "
                    "queue-ahead exceeds this (don't bury yourself behind a huge stack; quote deeper where "
                    "you're near front). 0 = no cap.")
    ap.add_argument("--lat-recheck-s", type=float, default=300.0, help="P5: re-run the CLOB latency "
                    "self-check every N seconds during the run; alert if the median round-trip regresses.")
    a = ap.parse_args()
    live = a.live and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if a.live and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. DRY-RUN.")
    mode = "LIVE" if live else "DRY-RUN"
    sess = netfast.fast_session()      # warm keep-alive, NODELAY -> a hot request is one origin RTT
    client = make_client() if live else None
    fv = SpotFair(sess, symbol=a.spot_symbol) if a.reprice else None
    rlog = RepriceLog()
    olog = OrderLog()                  # CAPTURE.md per-order lifecycle + fill ground-truth
    _boxfh = open("box_arb_log.jsonl", "a") if a.box_arb else None
    def boxlog(o):
        o["ts"] = time.time(); print(f"  [BOX {o['side']}] prem/set={o['premium_per_set']:+.4f} x{o['sets']} "
                                     f"=> gross_if_filled={o['gross_if_filled']:+.3f}")
        _boxfh.write(json.dumps(o) + "\n"); _boxfh.flush()
    live_btc = {"px": None, "ts": 0.0, "hist": deque(), "rtds_ts": 0.0, "src": None}
    lat0 = clob_selfcheck(sess)        # measure real CLOB round-trip -> are we co-located in eu-west-2?
    qema = {}                          # token -> {b,a} EMA of best-queue sizes (depletion trigger)
    # SUB-10ms book path: stream token books off the market WS; the OMS reads this cache (REST = fallback).
    books = {}                         # token -> {bb,ba,bsz,asz,ts}
    mdsub = {"tokens": None, "epoch": 0}   # bumped on window rollover so the feeder resubscribes
    threading.Thread(target=book_feeder, args=(books, mdsub), daemon=True).start()

    def cached_book(token, max_age=2.0):
        """WS book if fresh, else None (caller REST-falls-back). max_age guards against a silently dead feed."""
        c = books.get(token)
        if c and c["bb"] is not None and c["ba"] is not None and (time.time() - c["ts"]) <= max_age:
            return c["bb"], c["ba"], c["bsz"], c["asz"]
        return None

    def get_book(token):
        """Freshest top-of-book: WS cache (ms) -> REST (fallback)."""
        cb = cached_book(token)
        return cb if cb is not None else book(sess, token)

    if a.queue_jump:                   # Arm A: start the sub-second BTC lead feed
        threading.Thread(target=btc_lead_feeder, args=(live_btc,), daemon=True).start()
        jlog = open("queue_jump_log.jsonl", "a")   # A/B audit: lead-driven protect/shed actions
    print(f"[{mode}] STANDING-LADDER maker post={a.post} cap={a.cap} skew={a.skew} layers={a.layers} "
          f"max_rungs={a.max_rungs} age_protect={a.age_protect}s toxic_severe={a.toxic_severe} "
          f"reprice={a.reprice} fv_margin={a.fv_margin} max_notional=${a.max_notional} loss_limit=${a.loss_limit}")
    notify.alert(f"[pmkit] live_trader start {mode} cap={a.cap} skew={a.skew} reprice={a.reprice}")

    net_delta = 0.0; realized = 0.0; mk = None
    # P1 STANDING LADDER: each resting order keeps {oid, ts(placed), q(queue-ahead)}. We KEEP
    # aged orders across loops to let them age into front-of-queue priority; we never reflexively
    # reprice them. ts -> age -> "sacred" once age>=age_protect.
    resting = {}                       # (token,side,price) -> {"oid","ts","q"}
    seen_fills = set(); markouts = []

    presigned = {}        # (tk,sd,price3) -> signed order, pre-signed OFF the fire path (--presign)

    def _order_args(tk, sd, p):
        from py_clob_client_v2 import OrderArgs, PartialCreateOrderOptions
        from py_clob_client_v2.order_builder.constants import BUY, SELL
        return (OrderArgs(token_id=tk, price=p, size=a.post, side=(BUY if sd == "BUY" else SELL)),
                PartialCreateOrderOptions(tick_size=str(mk["tick"]), neg_risk=mk["negRisk"]))

    def presign_one(tk, sd, p):
        """Sign (EIP-712) a candidate order NOW so a later place() is a pure network POST. Each signed
        order carries its own random salt, so caching several ahead is safe. No-op unless --presign+live."""
        if not (live and a.presign):
            return
        k = (tk, sd, round(p, 3))
        if k in presigned:
            return
        try:
            args, opts = _order_args(tk, sd, p)
            presigned[k] = client.create_order(args, options=opts)
        except Exception:
            pass                                   # fall back to create_and_post_order at place() time

    def place(tk, sd, p, queue_ahead, bb=None, ba=None):
        """Returns (order_id, decision_ts, ack_ts) or None if refused. ack-decision = placement latency.
        FAST path (--presign): if this exact order was pre-signed, fire a pure POST (no signing on the
        hot path). Otherwise sign+post via the proven create_and_post_order. Any error -> safe fallback.
        A3 GUARD: refuse to post a crossing (marketable) order -> guarantees maker/post-only."""
        if would_cross(sd, p, bb, ba):
            print(f"  [POST-ONLY GUARD] refused crossing {sd} {tk[:8]} @ {p} (bb={bb} ba={ba})")
            return None
        t_dec = time.time()
        if not live:
            print(f"  [DRY place] {sd} {a.post} {tk[:8]} @ {p} (q_ahead~{queue_ahead:.0f})")
            return f"dry_{tk[:6]}_{sd}_{p}", t_dec, time.time()
        from py_clob_client_v2 import OrderType
        so = presigned.pop((tk, sd, round(p, 3)), None)
        try:
            if so is not None:                     # pre-signed -> pure POST (the sub-10ms fire path)
                r = client.post_order(so, OrderType.GTC)
            else:
                args, opts = _order_args(tk, sd, p)
                r = client.create_and_post_order(args, options=opts, order_type=OrderType.GTC)
        except Exception:                          # pre-signed POST failed (stale/expired) -> re-sign+post
            args, opts = _order_args(tk, sd, p)
            r = client.create_and_post_order(args, options=opts, order_type=OrderType.GTC)
        oid = r.get("orderID") if isinstance(r, dict) else r
        return oid, t_dec, time.time()

    def timed_cancel(oid):
        """Send the cancel and return IMMEDIATELY (t_sent, None). The old version polled get_orders() with
        sleep(0.1)x5 -> up to 0.5s of HOT-PATH BLOCKING per pull, serializing every other quote decision
        (a latency self-own on the exact path we're optimizing). The cancel SEND is the latency-critical
        action; confirmation was only a research metric (RepriceLog handles t_conf=None), so we don't block
        the reaction loop for it."""
        t_sent = time.time()
        if not live:
            return t_sent, t_sent + 0.0       # DRY: treat as instant
        try:
            client.cancel(order_id=oid)
        except Exception:
            pass
        return t_sent, None

    def drop(key, reason):
        meta = resting.pop(key); oid = meta["oid"]; q = meta.get("q", 0.0)
        t_sent, t_conf = timed_cancel(oid)
        olog.terminal(oid, "cancelled", reason, resting_s=time.time() - meta.get("ts", time.time()))
        if reason == "model_pull" and fv is not None:
            tau = max(mk["we"] - time.time(), 0.0)
            ft = fv.fair_token(key[0] == mk["up"], tau)
            rlog.pull(key[0], key[1], key[2], oid, t_sent, t_conf, q, ft if ft is not None else -1, mk["ws"])

    def cancel_all_resting(reason="rollover"):
        for key in list(resting):
            drop(key, reason)

    # C1 DEAD-MAN / cancel-on-exit: a disconnect or crash with resting orders + inventory = naked
    # directional risk that dwarfs the tiny rebate edge. Guarantee orders are pulled on ANY exit path
    # (normal end, uncaught exception, SIGTERM from systemd, Ctrl-C) -- not just the clean ones.
    _flattened = {"done": False}

    def _flatten_and_exit(reason):
        if _flattened["done"]:
            return
        _flattened["done"] = True
        try:
            print(f"[DEAD-MAN] {reason}: cancelling all resting orders")
            notify.alert(f"[pmkit] DEAD-MAN {reason}: cancel-all")
            cancel_all_resting(reason="deadman")
        except Exception as e:  # noqa: BLE001
            print(f"[DEAD-MAN] cancel failed: {str(e)[:120]}")

    atexit.register(lambda: _flatten_and_exit("process exit"))
    for _sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(_sig, lambda *_: (_flatten_and_exit(f"signal {_sig}"), os._exit(0)))
        except Exception:
            pass                                      # not main thread / unsupported -> atexit still covers it

    last_book_ok = time.time()    # staleness watchdog: last time the order book feed answered
    deadman_tripped = False
    consec_err = 0
    last_hk = 0.0                  # last housekeeping pass (fv refresh + fills poll), gated by --poll
    last_latcheck = time.time()   # P5: periodic latency re-check (alert on regression)
    end = time.time() + a.duration
    while time.time() < end:
        try:
            # C1 staleness watchdog: if the book feed has been dark longer than --deadman-s while we hold
            # resting orders, we are quoting/holding BLIND -> pull everything until the feed recovers.
            stale = time.time() - last_book_ok
            if live and resting and stale > a.deadman_s and not deadman_tripped:
                print(f"[DEAD-MAN] book feed stale {stale:.0f}s > {a.deadman_s}s -> cancel-all")
                notify.alert(f"[pmkit] DEAD-MAN feed stale {stale:.0f}s: cancel-all")
                cancel_all_resting(reason="deadman_stale"); deadman_tripped = True
            if mk is None or time.time() >= mk["we"]:
                if mk is not None:                       # settle (d) for the closing window
                    r = resolve(sess, mk["ws"], a.asset, a.tenor_min)
                    if r is not None:
                        rlog.settle(mk["ws"], mk["up"], r)
                        rlog.settle(mk["ws"], mk["down"], 1 - r)
                    # ROADMAP #1: reclaim collateral from matched Up+Down pairs. LIVE build must
                    # read on-chain token balances here; net_delta is a coarse stand-in for the
                    # unmatched leg. Merge frees capital to quote more size next window.
                    mm = collateral.MintMerge(live, neg_risk=mk.get("negRisk", False))
                    action, sets = collateral.plan(up_held=max(-net_delta, 0) + a.post,
                                                   dn_held=max(net_delta, 0) + a.post,
                                                   buffer_sets=a.post)
                    if action == "merge" and sets > 0:
                        mm.merge(mk["cid"], sets)
                cancel_all_resting()                     # window rollover: tokens change, must reset
                mk = active_market(sess, a.asset, a.tenor_min)
                if not mk:
                    time.sleep(a.poll); continue
                mdsub["tokens"] = [mk["up"], mk["down"]]; mdsub["epoch"] += 1   # point the WS feed at the new tokens
                if fv is not None:
                    # Only anchor (=> overlay ON) if we joined within 60s of the open; a
                    # mid-window join has no true S0, so run baseline-only that window.
                    if time.time() - mk["ws"] <= 60:
                        fv.set_window(fv.update())
                    else:
                        fv.update(); fv.set_window(None)
                        print("  (joined mid-window; overlay OFF until next open)")
                print(f"WINDOW {mk['ws']} {datetime.fromtimestamp(mk['ws'],timezone.utc):%H:%M}Z tick={mk['tick']}")
            hk = (time.time() - last_hk) >= a.poll       # housekeeping due? (REST-bound work runs at --poll)
            if fv is not None and hk:
                fv.update()
            # P5: continuous latency monitoring -- a CF re-route / region change silently sends us to the
            # back of every queue. Re-check periodically; alert on a >2x median regression (or cross-region).
            if a.lat_recheck_s > 0 and (time.time() - last_latcheck) >= a.lat_recheck_s:
                last_latcheck = time.time()
                med = clob_selfcheck(sess)
                if med is not None and ((lat0 and med > 2 * lat0) or med > 80):
                    notify.alert(f"[pmkit] LATENCY REGRESSION median {med:.0f}ms (was {lat0:.0f}ms)"
                                 if lat0 else f"[pmkit] LATENCY {med:.0f}ms (cross-region)")
            band_px = a.fv_band * mk["tick"]
            tau = max(mk["we"] - time.time(), 0.0)
            if realized <= -abs(a.loss_limit):
                print(f"KILL: realized {realized:+.2f}. cancel-all + exit."); notify.alert("[pmkit] KILL loss-limit")
                cancel_all_resting(); break
            if len(markouts) >= 30 and sum(markouts[-30:]) / 30 < -0.01:
                print("KILL: rolling markout toxic. cancel-all + exit."); notify.alert("[pmkit] KILL markout toxic")
                cancel_all_resting(); break

            # --- BOX-ARB mode: complete-set (UP+DOWN -> $1). TWO distinct edges (see box_probe.py):
            #   MAKER box (what we POST here): rest sells on both asks (mint-sourced) / rest buys on both
            #     bids. Earns ask_up+ask_dn-1 (~+1 tick) -- the MM spread -- and is risk-free ONLY if BOTH
            #     legs fill; if one fills you hold a directional leg (legging risk). This is the seat we
            #     already study, expressed as a complete set.  TAKER box (the genuinely risk-free/free line):
            #     bid_up+bid_dn>1 (hit both) or ask_up+ask_dn<1 (lift both) -- competed away in liquid 15m
            #     crypto. We LOG it whenever it appears so the operator sees a true free arb vs the spread. ---
            if a.box_arb:
                bbu, bau, _, _ = get_book(mk["up"]); bbd, bad, _, _ = get_book(mk["down"])
                if None not in (bbu, bau, bbd, bad):
                    last_book_ok = time.time(); deadman_tripped = False   # feed alive -> reset watchdog
                mmb = collateral.MintMerge(live, neg_risk=mk.get("negRisk", False))
                if None not in (bbu, bau, bbd, bad):     # surface any genuinely risk-free TAKER box first
                    if bbu + bbd - 1.0 > 0:
                        boxlog({"ws": mk["ws"], "side": "FREE_sell_taker", "bid_up": bbu, "bid_dn": bbd,
                                "premium_per_set": round(bbu + bbd - 1.0, 4), "sets": a.box_sets,
                                "gross_if_filled": round((bbu + bbd - 1.0) * a.box_sets, 4)})
                    if 1.0 - (bau + bad) > 0:
                        boxlog({"ws": mk["ws"], "side": "FREE_buy_taker", "ask_up": bau, "ask_dn": bad,
                                "premium_per_set": round(1.0 - (bau + bad), 4), "sets": a.box_sets,
                                "gross_if_filled": round((1.0 - (bau + bad)) * a.box_sets, 4)})
                if bau is not None and bad is not None and (bau + bad - 1.0) > a.box_margin and bau + bad < 2:
                    prem = bau + bad - 1.0                # MAKER: rest SELL both at the asks for a $1 set
                    mmb.split(mk["cid"], a.box_sets)      # mint N sets ($N) to source both legs (dry-safe)
                    place(mk["up"], "SELL", bau, 0.0, bb=bbu, ba=bau); place(mk["down"], "SELL", bad, 0.0, bb=bbd, ba=bad)
                    boxlog({"ws": mk["ws"], "side": "sell_box", "ask_up": bau, "ask_dn": bad,
                            "premium_per_set": round(prem, 4), "sets": a.box_sets, "gross_if_filled": round(prem * a.box_sets, 4)})
                if bbu is not None and bbd is not None and (1.0 - bbu - bbd) > a.box_margin and bbu + bbd > 0:
                    prem = 1.0 - bbu - bbd                # MAKER: rest BUY both at the bids; merge -> $1/set
                    place(mk["up"], "BUY", bbu, 0.0, bb=bbu, ba=bau); place(mk["down"], "BUY", bbd, 0.0, bb=bbd, ba=bad)
                    boxlog({"ws": mk["ws"], "side": "buy_box", "bid_up": bbu, "bid_dn": bbd,
                            "premium_per_set": round(prem, 4), "sets": a.box_sets, "gross_if_filled": round(prem * a.box_sets, 4)})
                time.sleep(a.poll); continue

            # --- BASELINE geometry, then MODEL predictive filter (overlay) ---
            for token, is_up in ((mk["up"], True), (mk["down"], False)):
                bb, ba, bsz, asz = get_book(token)       # WS cache (ms) -> REST fallback
                if bb is None or ba is None:
                    continue
                last_book_ok = time.time(); deadman_tripped = False   # feed alive -> reset watchdog
                if a.queue_jump:                       # rolling avg of best-queue sizes (depletion)
                    qe = qema.setdefault(token, {"b": bsz, "a": asz})
                    qe["b"] = 0.9 * qe["b"] + 0.1 * bsz; qe["a"] = 0.9 * qe["a"] + 0.1 * asz
                base = baseline_levels(mk, token, is_up, bb, ba, net_delta, a.layers, a.cap, a.skew, improve=a.improve)
                ft = fv.fair_token(is_up, tau) if fv is not None else None
                # A2 (observer effect): the venue book INCLUDES our own resting size, which would bias the
                # microprice toward OUR side -- contaminating the very signal we gate on. Subtract our resting
                # size at the touch so the microprice reflects OTHER traders' imbalance only.
                own_b = sum(a.post for k in resting if k[0] == token and k[1] == "BUY" and abs(k[2] - bb) < 1e-9)
                own_a = sum(a.post for k in resting if k[0] == token and k[1] == "SELL" and abs(k[2] - ba) < 1e-9)
                mp = microprice(bb, ba, max((bsz or 0) - own_b, 0.0), max((asz or 0) - own_a, 0.0))  # book-native (#4), own-order-excluded
                # Anchor = microprice (book imbalance), NOT the spot fair_up: drift_predict showed
                # spot is not quote-time predictive (R^2~0), and fair_up's ~0.5 window-open prior
                # falsely suppresses a side. The microprice is the surviving book-native signal and
                # sits inside the spread, so the toxic test fires only when it CROSSES a resting price.
                anchor = mp if mp is not None else ft
                desired, model_supp = model_filter(base, anchor, a.fv_margin, bb, ba, band_px, rlog, token)
                for _k in desired:                 # pre-sign the targets we're about to need (no-op unless --presign)
                    presign_one(*_k)
                # P3: warm a DEEPER pre-signed band (touch +/- extra ticks + the inside-touch improve level)
                # so a touch move fires at the new level with zero signing on the path (new-level race).
                if a.presign_depth > 0:
                    tick = mk["tick"]
                    for k in range(1, a.presign_depth + 1):
                        for sd, base_px in (("BUY", bb), ("SELL", ba)):
                            for p in (round(base_px - k * tick, 4), round(base_px + k * tick, 4)):
                                if 0 < p < 1:
                                    presign_one(token, sd, p)
                now = time.time()

                # --- P1: PLACE missing ladder rungs (KEEP existing -> they age into priority) ---
                for key in desired:
                    if key in resting:
                        continue
                    _, sd, p = key
                    if a.post * (p if sd == "BUY" else 1 - p) > a.max_notional:
                        continue
                    if sum(1 for k in resting if k[0] == token and k[1] == sd) >= a.max_rungs:
                        continue                          # side ladder full; don't over-commit capital
                    q_ahead = (bsz if sd == "BUY" else asz) if abs(p - (bb if sd == "BUY" else ba)) < 1e-9 else 0.0
                    if a.max_queue_ahead > 0 and q_ahead > a.max_queue_ahead:
                        continue                          # P4: don't bury behind a huge stack -> quote deeper where we're near front
                    res = place(*key, q_ahead, bb=bb, ba=ba)
                    if res is None:                       # post-only guard refused (would cross) -> skip
                        continue
                    oid, t_dec, t_ack = res
                    resting[key] = {"oid": oid, "ts": t_ack, "q": q_ahead}
                    olog.placed(oid, t_dec, t_ack, ws=mk["ws"], asset=token[:12], outcome=("Up" if is_up else "Down"),
                                side=sd, price=p, size=a.post, tick=mk["tick"], queue_depth_ahead=q_ahead,
                                mid=round((bb + ba) / 2, 4), microprice=round(mp, 4) if mp is not None else None,
                                best_bid=bb, best_ask=ba, spread=round(ba - bb, 4),
                                btc_spot=(fv.last if fv is not None else None), tau=round(tau, 1))

                # QUEUE-POSITIONING (Arm A): a fast BTC move says where the touch is HEADING. In a
                # 1-tick market you can't pre-post at the next level without crossing (=taker, fails the
                # fee), so the edge is RUNG PRIORITY: protect aged rungs on the side the book moves
                # TOWARD (front-of-queue when the touch arrives) and shed the side it leaves.
                lead_fav = lead_adv = None
                dspot = 0.0
                if a.queue_jump:
                    # COMBINE two signals for where the touch is heading: (i) the ~0.5s BTC lead, and
                    # (ii) Fokker-Planck queue depletion (ask queue collapsing => book steps UP;
                    # bid collapsing => DOWN). sig>0 => touch heading up => protect BUY, shed SELL.
                    dspot = btc_lead(live_btc, a.jump_lag)
                    px = live_btc.get("px") or 0.0
                    thr = px * a.jump_bps / 1e4
                    fair_move = (1.0 if is_up else -1.0) * dspot
                    sig = 0
                    if thr > 0 and abs(fair_move) >= thr:
                        sig += 1 if fair_move > 0 else -1                  # (i) BTC lead
                    qe = qema.get(token)
                    if qe:                                                # (ii) queue depletion
                        if qe["a"] > 0 and asz < DEPLETE_FRAC * qe["a"]:
                            sig += 1
                        if qe["b"] > 0 and bsz < DEPLETE_FRAC * qe["b"]:
                            sig -= 1
                    if sig > 0:
                        lead_fav, lead_adv = "BUY", "SELL"
                    elif sig < 0:
                        lead_fav, lead_adv = "SELL", "BUY"

                # --- P1 front-sacred + P2 EV-cancel: decide each resting order ---
                for key in list(resting):
                    if key[0] != token:
                        continue
                    _, sd, p = key
                    aged = (now - resting[key]["ts"]) >= a.age_protect      # accrued queue priority
                    toxic = key in model_supp                              # model says wrong side of fair
                    severe = False
                    if anchor is not None:                                 # EV pressure = how far past fair
                        edge = (anchor - p) if sd == "SELL" else (p - anchor)
                        severe = edge > a.toxic_severe * mk["tick"]         # strong/informed move (in ticks)
                    in_band = key in desired
                    if lead_adv == sd:                     # book heading away from this side -> shed it
                        drop(key, "lead_shed")
                        jlog.write(json.dumps({"ts": now, "ws": mk["ws"], "token": token[:12], "side": sd,
                                   "price": p, "action": "shed", "dspot": round(dspot, 1)}) + "\n"); jlog.flush()
                    elif lead_fav == sd:                  # book heading toward this side -> PROTECT queue priority
                        if toxic and severe:
                            drop(key, "model_pull")        # only a severe informed move overrides the protect
                        # else HOLD even if young/off-band: keep our place in the queue the touch is entering
                        else:
                            jlog.write(json.dumps({"ts": now, "ws": mk["ws"], "token": token[:12], "side": sd,
                                       "price": p, "action": "protect", "aged": aged, "dspot": round(dspot, 1)}) + "\n"); jlog.flush()
                    elif toxic and (not aged or severe):
                        drop(key, "model_pull")            # P2: cancel only if young, OR toxic beats queue value
                    elif (not aged) and (not in_band) and (now - resting[key]["ts"]) >= a.min_rest_s:
                        drop(key, "reshape")               # reshape from the back: young off-band rung...
                        # ...but only after --min-rest-s, so the 0.1s react loop can't churn away the queue
                        # priority a fresh order is accruing on transient book flicker (P2). Toxic pulls above
                        # are exempt -- the adverse-selection defense is never debounced.
                    # else: AGED, in-band, or too-fresh -> HOLD (front of book is sacred)

                # --- rung cap: evict the rungs FARTHEST from the touch (manage from the back) ---
                for sd, touch in (("BUY", bb), ("SELL", ba)):
                    ks = [k for k in resting if k[0] == token and k[1] == sd]
                    if len(ks) > a.max_rungs:
                        ks.sort(key=lambda k: abs(k[2] - touch))           # nearest-touch first
                        for k in ks[a.max_rungs:]:                         # cancel the stranded deep extras
                            drop(k, "rung_cap")

            # --- per-fill MARKOUT + net-delta + (c) taker-hit-old attribution (HOUSEKEEPING cadence) ---
            # Fills come off a REST poll, so they run at --poll (1s), not the fast --react-poll loop -- the
            # reaction (quote pulls) is what needs sub-10ms; learning about a fill ~1s late is fine for a
            # hold-to-resolution maker. (Next step for true sub-ms fills: the auth'd user WS.)
            if live and hk:
                try:
                    trades = client.get_trades() or []
                except Exception:
                    trades = []
                for t in trades:
                    tid = t.get("id") or t.get("transaction_hash") or str(t)
                    asset = str(t.get("asset_id") or t.get("asset") or ""); sd = (t.get("side") or "").upper()
                    fp = float(t.get("price", 0)); fsz = float(t.get("size", 0))
                    rlog.attribute_trade(asset, sd, fp, time.time())   # (c) regardless of dedupe
                    if tid in seen_fills:
                        continue
                    seen_fills.add(tid)
                    net_delta += (1.0 if asset == mk["up"] else -1.0) * (fsz if sd == "BUY" else -fsz)
                    bb2, ba2, _, _ = get_book(asset); mid2 = (bb2 + ba2) / 2 if bb2 and ba2 else fp
                    mo = (mid2 - fp) if sd == "BUY" else (fp - mid2); markouts.append(mo)
                    # match to OUR resting order (opposite side, same price) for queue residence
                    mkey = (asset, "SELL" if sd == "BUY" else "BUY", round(fp, 4))
                    meta = resting.pop(mkey, None)
                    resting_s = (time.time() - meta["ts"]) if meta else None
                    oidf = meta["oid"] if meta else (t.get("order_id") or t.get("maker_order_id") or "?")
                    trader_side = (t.get("maker_taker") or t.get("trader_side") or "MAKER").upper()
                    # source: this scaffold sells passively (no on-chain mint here) -> "passive";
                    # a minting bot flags "mint" so the SELL-skew can be attributed to sourcing.
                    olog.fill(oidf, asset, sd, fp, fsz, trader_side, t.get("fee_rate_bps"),
                              resting_s, (meta.get("q") if meta else None), round(mo, 5), "passive")
                    if meta:
                        olog.terminal(oidf, "filled", "fill", resting_s)
                    open("live_markout.jsonl", "a").write(json.dumps(
                        {"ts": time.time(), "asset": asset[:12], "side": sd, "price": fp, "size": fsz,
                         "markout": mo, "net_delta": net_delta}) + "\n")
            if hk:
                last_hk = time.time()                  # mark housekeeping done (fv/fills ran this pass)
            consec_err = 0                              # clean iteration -> reset the error-storm counter
            time.sleep(a.react_poll)                    # FAST reaction cadence on the WS book cache
        except KeyboardInterrupt:
            _flatten_and_exit("KeyboardInterrupt"); print("interrupted; cancelled all."); break
        except Exception as e:  # noqa: BLE001
            consec_err += 1
            print(f"[warn] {str(e)[:100]} (consec_err={consec_err})")
            if live and resting and consec_err >= 5 and not deadman_tripped:
                # C1 error-storm dead-man: repeated failures -> we can't trust our state; pull everything.
                print("[DEAD-MAN] error storm -> cancel-all"); notify.alert("[pmkit] DEAD-MAN error storm: cancel-all")
                cancel_all_resting(reason="deadman_errors"); deadman_tripped = True
            time.sleep(a.poll)
    _flatten_and_exit("loop end")
    s = rlog.summary()
    print(f"done. realized={realized:+.2f} fills={len(seen_fills)} pulls={s['pulls']} "
          f"clamp_binds={s['clamp_binds']} "
          + (f"avg_markout={sum(markouts)/len(markouts):+.5f}" if markouts else ""))


if __name__ == "__main__":
    main()
