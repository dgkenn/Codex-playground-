"""kalshi_trader.py -- Kalshi execution adapter: port of live_trader.py's OMS/safety rails.

Passive 2-sided maker on KX{BTC,ETH,SOL,XRP}15M. Every live_trader.py safety rail is mirrored:
dead-man, loss-limit (STICKY sentinel), rolling-markout kill, post_only-only, aggregate notional
cap, startup reconciliation (fail-closed), venue reconciliation sweep, fill polling, window rollover
with next-window prefetch, and pending settle retry with >=20s grace.

    python kalshi_trader.py                              # DRY-RUN (discovers, prints DRY place lines)
    I_UNDERSTAND_REAL_MONEY=yes python kalshi_trader.py --live --max-notional 25

Auth: API key id + RSA-PSS SHA-256 (cryptography library). No EIP-712.
One physical book (YES/NO views). buy YES = bid; buy NO = ask side. Action always "buy".
WS book+fill feeder: authenticated wss://api.elections.kalshi.com/trade-api/ws/v2 (orderbook_delta
+ fill channels). Mirrors live_trader.book_feeder: event-driven reaction, ms-fresh book, real-time
fills deduped against REST backstop.
"""
from __future__ import annotations

import argparse
import asyncio
import atexit
import base64
import collections
import json
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timezone

import requests

import notify          # Telegram alerts (no-op if env unset)
from live_metrics import LiveMetrics

BASE = "https://api.elections.kalshi.com/trade-api/v2"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
MICRO_MARGIN = 0.002   # p-adaptive toxicity margin (same constant as live_trader)

# --- DECISION-TIME SPOT FEED (Prevention #0: wire `sig` into each fill record) -------------------
# A daemon thread polls BTC spot so every fill can be stamped with the decision-time spot-move (the
# leading adverse-selection signal the A/B tester's `sig` uses). TELEMETRY-ONLY and fully isolated:
# it never blocks or feeds the trading loop, and any failure just leaves sig=None (trader unaffected).
_SPOT = {"px": None, "hist": collections.deque(maxlen=400)}   # (ts, px) history, ~3s cadence


# AUDIT M6: sig telemetry must track the TRADED asset's spot, not always BTC.
_COINBASE_PRODUCT = {"btc": "BTC-USD", "eth": "ETH-USD", "sol": "SOL-USD", "xrp": "XRP-USD"}


def _spot_poller(product="BTC-USD"):
    sess = requests.Session()
    while True:
        try:
            r = sess.get(f"https://api.exchange.coinbase.com/products/{product}/ticker", timeout=2)
            px = float(r.json().get("price"))
            _SPOT["px"] = px
            _SPOT["hist"].append((time.time(), px))
        except Exception:
            pass
        time.sleep(3.0)


def _spot_sig():
    """(spot, move_bps) where move_bps = BTC % move x1e4 over ~3 min -- the same signal as the A/B
    `sig`. Returns (None, None) if no spot data yet. Never raises."""
    try:
        px = _SPOT["px"]; h = _SPOT["hist"]
        if px is None or not h:
            return None, None
        now = time.time()
        old = next((p for t, p in h if now - t >= 180), h[0][1])
        if not old or old <= 0:
            return px, None
        return px, round((px / old - 1.0) * 1e4, 2)
    except Exception:
        return None, None

seeded: set = set()   # C-4: tickers whose prior-session fills have been seeded into seen_fills


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _load_private_key():
    path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not path:
        return None
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        with open(path, "rb") as fh:
            return load_pem_private_key(fh.read(), password=None)
    except Exception as e:
        raise SystemExit(f"[auth] failed to load private key from {path}: {e}")


def _sign(private_key, method: str, path: str) -> dict:
    """Kalshi RSA-PSS headers: base64(RSA-PSS(SHA256,salt=digest_len) of ts_ms+METHOD+path).
    path = /trade-api/v2/... WITHOUT query string."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    msg = (ts + method.upper() + path).encode()
    sig = private_key.sign(msg, padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,  # salt_length = digest_len = 32 for SHA-256
    ), hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": os.environ.get("KALSHI_API_KEY_ID", ""),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Authenticated WebSocket book+fill feeder (mirrors live_trader.book_feeder)
# ---------------------------------------------------------------------------

def ws_feeder(ws_state, ws_sub, book_evt, ws_fills, private_key):
    """Authenticated WS feeder: orderbook_delta + fill channels on Kalshi.

    Maintains ws_state[ticker] = {yes:{price:qty}, no:{price:qty}, ts, bb, bq, ba, aq}.
    Sets book_evt on every book delta so the OMS reacts in WS time (ms), not poll cadence.
    Appends raw fill msgs to ws_fills (deque) for immediate booking.
    Resubscribes when ws_sub['epoch'] bumps (window rollover). recv timeout=1.0s so epoch
    changes are detected quickly even if the feed goes quiet (mirrors live_trader H-1 fix).
    websockets imported lazily -> if missing, prints warning and returns (REST stays active).
    """
    try:
        import websockets
    except Exception:
        print("  [ws-book] websockets not installed -> WS feed OFF (REST fallback only)")
        return

    async def run():
        while True:
            ticker = ws_sub.get("ticker")
            epoch = ws_sub.get("epoch")
            if not ticker:
                await asyncio.sleep(0.2)
                continue
            try:
                auth_hdrs = _sign(private_key, "GET", "/trade-api/ws/v2")
                # newer websockets uses additional_headers; fall back to extra_headers if needed
                try:
                    connect_ctx = websockets.connect(
                        WS_URL,
                        additional_headers=auth_hdrs,
                        ping_interval=10,
                        ping_timeout=20,
                        max_size=None,
                    )
                except TypeError:
                    connect_ctx = websockets.connect(
                        WS_URL,
                        extra_headers=auth_hdrs,
                        ping_interval=10,
                        ping_timeout=20,
                        max_size=None,
                    )
                async with connect_ctx as ws:
                    sub_msg = json.dumps({
                        "id": 1,
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["orderbook_delta", "fill"],
                            "market_tickers": [ticker],
                        },
                    })
                    await ws.send(sub_msg)
                    print(f"  [ws-book] subscribed ticker={ticker} epoch={epoch}")
                    while True:
                        # H-1 fix (mirrors live_trader): use a 1s timeout so epoch changes
                        # are detected promptly even when the feed goes quiet.
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if ws_sub.get("epoch") != epoch:
                                break   # window rolled -> reconnect + resubscribe
                            continue
                        if ws_sub.get("epoch") != epoch:
                            break       # epoch changed mid-message -> reconnect
                        if not raw:
                            continue
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        mtype = msg.get("type", "")
                        if mtype in ("subscribed", "ok"):
                            continue
                        if mtype == "error":
                            print(f"  [ws-book] error from server: {str(msg)[:120]}")
                            continue
                        payload = msg.get("msg") or {}   # WS envelope: {"type", "sid", "seq", "msg": {...}}
                        if mtype == "orderbook_snapshot":
                            _apply_snapshot(ws_state, payload)
                            if book_evt is not None:
                                book_evt.set()
                        elif mtype == "orderbook_delta":
                            _apply_delta(ws_state, payload)
                            if book_evt is not None:
                                book_evt.set()
                        elif mtype == "fill":
                            ws_fills.append(payload)
            except Exception as exc:
                print(f"  [ws-book] disconnected ({type(exc).__name__}: {str(exc)[:80]}); reconnect in 1s")
                await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())


def _apply_snapshot(ws_state, msg):
    """Process an orderbook_snapshot message into ws_state."""
    ticker = msg.get("market_ticker") or msg.get("market_id", "")
    if not ticker:
        return
    # yes_dollars_fp: [[price_str, qty_str], ...] ascending by price; best = last
    yes_raw = msg.get("yes_dollars_fp") or []
    no_raw  = msg.get("no_dollars_fp")  or []
    yes_book = {}
    for entry in yes_raw:
        try:
            p, q = float(entry[0]), float(entry[1])
            if q > 0:
                yes_book[p] = q
        except Exception:
            pass
    no_book = {}
    for entry in no_raw:
        try:
            p, q = float(entry[0]), float(entry[1])
            if q > 0:
                no_book[p] = q
        except Exception:
            pass
    ws_state[ticker] = {"yes": yes_book, "no": no_book, "ts": time.time()}
    _recompute_bba(ws_state, ticker)


def _apply_delta(ws_state, msg):
    """Apply an orderbook_delta message incrementally to ws_state."""
    ticker = msg.get("market_ticker", "")
    if not ticker:
        return
    if ticker not in ws_state:
        # No snapshot yet; ignore delta (snapshot will come first on sub)
        return
    side  = msg.get("side", "")         # "yes" or "no"
    try:
        price = float(msg.get("price_dollars", 0))
        delta = float(msg.get("delta_fp", 0))
    except Exception:
        return
    if side not in ("yes", "no"):
        return
    book_side = ws_state[ticker][side]
    new_qty = book_side.get(price, 0.0) + delta
    if new_qty <= 0.005:                 # epsilon: float residue (e.g. 8e-13) must EMPTY the level,
        book_side.pop(price, None)       # else ghost levels lock/cross the derived book
    else:
        book_side[price] = new_qty
    ws_state[ticker]["ts"] = time.time()
    _recompute_bba(ws_state, ticker)


def _recompute_bba(ws_state, ticker):
    """Recompute best bid/ask + sizes and store into ws_state[ticker]."""
    st = ws_state.get(ticker)
    if st is None:
        return
    yes_book = st["yes"]
    no_book  = st["no"]
    # Best YES bid = highest yes price
    if yes_book:
        bb = max(yes_book)
        bq = yes_book[bb]
    else:
        bb, bq = None, 0.0
    # Best NO bid = highest no price; YES ask = 1 - best_NO_bid
    if no_book:
        nb = max(no_book)
        nq = no_book[nb]
        ba = round(1.0 - nb, 4)   # YES ask
        aq = nq                   # ask qty = NO side depth at best
    else:
        ba, aq = None, 0.0
    st["bb"] = bb
    st["bq"] = bq
    st["ba"] = ba
    st["aq"] = aq


# ---------------------------------------------------------------------------
# Market discovery (public, no auth)
# ---------------------------------------------------------------------------

def discover(sess, asset="btc"):
    """Nearest open KX{asset}15M market (mirrors kalshi_collect.KalshiMarket.discover)."""
    series = f"KX{asset.upper()}15M"
    try:
        d = sess.get(f"{BASE}/markets", params={"series_ticker": series, "status": "open",
                                                 "limit": 5}, timeout=8).json()
    except Exception:
        return None
    best = None
    now = time.time()
    for m in (d.get("markets") or []):
        try:
            ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ct > now + 5 and (best is None or ct < best[1]):
            best = (m["ticker"], ct)
    if best is None:
        return None
    tk, ct = best
    ws = int(ct) - 900
    return {"cid": tk, "ws": ws, "we": int(ct), "tick": 0.01, "asset": asset}


def get_book(sess, ticker):
    """(yes_bid, ybq, yes_ask, yaq) from public orderbook_fp. best-at-END; YES ask=1-best_NO_bid."""
    try:
        ob = sess.get(f"{BASE}/markets/{ticker}/orderbook", timeout=4).json()
    except Exception:
        return None, None, None, None
    o = ob.get("orderbook_fp") or ob.get("orderbook") or {}
    yb = o.get("yes_dollars") or []
    nb = o.get("no_dollars") or []
    if not yb or not nb:
        return None, None, None, None
    ybb, ybq = float(yb[-1][0]), float(yb[-1][1])   # best YES bid (price, qty)
    nbb, nbq = float(nb[-1][0]), float(nb[-1][1])   # best NO bid
    yba = round(1.0 - nbb, 4)                        # YES ask = 1 - best NO bid (mirror)
    return ybb, ybq, yba, nbq


def resolve_result(sess, ticker):
    """Return 1 (yes wins) / 0 (no wins) / 'void' (voided/cancelled) / None (not yet settled)."""
    try:
        m = sess.get(f"{BASE}/markets/{ticker}", timeout=8).json().get("market", {})
        r = m.get("result")
        if r == "yes":
            return 1
        if r == "no":
            return 0
        if r in ("void", "voided", "cancelled", "canceled"):
            return "void"
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# microprice (identical to live_trader)
# ---------------------------------------------------------------------------

def microprice(bb, ba, bsz, asz):
    """Stoikov imbalance-weighted micro-price (identical to live_trader)."""
    if bb is None or ba is None:
        return None
    tot = (bsz or 0) + (asz or 0)
    if tot <= 0:
        return (bb + ba) / 2.0
    return bb + (ba - bb) * ((bsz or 0) / tot)


# ---------------------------------------------------------------------------
# Trading API (live only)
# ---------------------------------------------------------------------------

def _api(sess, private_key, method, path_suffix, body=None, params=None, timeout=5):
    """Authenticated REST call. Returns (status_code, json_body_or_None)."""
    url = BASE + path_suffix.removeprefix("/trade-api/v2")
    api_path = "/trade-api/v2" + path_suffix.removeprefix("/trade-api/v2")
    headers = _sign(private_key, method, api_path)
    try:
        if method == "GET":
            r = sess.get(url, headers=headers, params=params, timeout=timeout)
        elif method == "POST":
            r = sess.post(url, headers=headers, json=body, timeout=timeout)
        elif method == "DELETE":
            r = sess.delete(url, headers=headers, timeout=timeout)
        else:
            return 0, None
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception as e:
        return 0, {"_exc": str(e)[:80]}


def place_order(sess, private_key, ticker, side, price_dollars, count, client_oid=None,
                ttl_s=None, post_only=True):
    """POST /portfolio/orders (action=buy). post_only=True (default) = maker-only (venue rejects if
    marketable). post_only=False = allow CROSSING (taker) -- used ONLY by the strand-disposal path to
    COMPLETE a stranded box by taking the offer (live RCA 2026-06-13: post-only-only could never
    complete -> strands rode naked to settlement at -21.76c). Returns order_id or None (NOT PLACED).
    ttl_s -> expiration_ts: the VENUE-SIDE dead-man. A SIGKILLed process (container reap, 2x now)
    leaves GTC orders working an unattended window -- the 2026-06-12 death cost ~$1.13 when its
    orphans kept filling one side. With a TTL every orphan self-cancels at the venue within ttl_s."""
    coid = client_oid or str(uuid.uuid4())
    body = {
        "ticker": ticker,
        "client_order_id": coid,
        "side": side,
        "action": "buy",
        "count": int(count),
        "type": "limit",
        f"{side}_price_dollars": f"{price_dollars:.4f}",
        "post_only": post_only,
        "expiration_ts": int(time.time() + ttl_s) if ttl_s else None,
    }
    body = {k: v for k, v in body.items() if v is not None}
    sc, resp = _api(sess, private_key, "POST", "/portfolio/orders", body=body)
    if sc < 200 or sc >= 300 or resp is None:
        # surface the venue's actual reason (2,140 rejects were logged as the useless
        # "no order_id from venue" because this was discarded -- reject forensics 2026-06-12)
        err = ""
        try:
            err = (resp or {}).get("error", {}).get("message") or json.dumps(resp)[:120]
        except Exception:
            err = str(resp)[:120]
        return None, sc, err
    oid = (resp.get("order") or {}).get("order_id")
    return (str(oid), sc, "") if oid else (None, sc, "2xx but no order_id")


def cancel_order(sess, private_key, order_id):
    """DELETE /portfolio/orders/{order_id}. Returns True if venue accepted (2xx)."""
    sc, _ = _api(sess, private_key, "DELETE", f"/portfolio/orders/{order_id}", timeout=4)
    return 200 <= sc < 300


def get_open_orders(sess, private_key, ticker):
    """GET /portfolio/orders?ticker=. Returns list of order dicts (may be empty on error)."""
    sc, resp = _api(sess, private_key, "GET", "/portfolio/orders",
                    params={"ticker": ticker, "status": "resting"}, timeout=6)
    if sc < 200 or sc >= 300 or resp is None:
        return []
    return resp.get("orders") or []


def get_fills(sess, private_key, ticker, limit=200):
    """GET /portfolio/fills?ticker=. Returns list of fill dicts."""
    sc, resp = _api(sess, private_key, "GET", "/portfolio/fills",
                    params={"ticker": ticker, "limit": limit}, timeout=6)
    if sc < 200 or sc >= 300 or resp is None:
        return []
    return resp.get("fills") or []


def get_balance(sess, private_key):
    """GET /portfolio/balance. Returns raw dict or None."""
    sc, resp = _api(sess, private_key, "GET", "/portfolio/balance", timeout=6)
    return resp if (200 <= sc < 300 and resp is not None) else None


# ---------------------------------------------------------------------------
# Quote geometry (Kalshi two-view adaptation)
# ---------------------------------------------------------------------------

def desired_levels(mk, yes_bid, yes_ask, net_delta, layers, cap, skew_frac, improve_tick):
    """Two views: BUY-YES rungs near yes_bid; BUY-NO rungs near no_bid=(1-yes_ask).
    QUEUE PRIORITY: when spread>=0.01, place at best_bid+improve_tick to jump the queue.
    All levels are BUY orders (buy-no = ask side of the single book)."""
    tick = mk["tick"]
    d_sign = 1.0    # YES is the "up" direction
    skew = skew_frac * cap

    # Inventory gates (same logic as live_trader.baseline_levels)
    quote_yes = (net_delta < cap) and (net_delta < skew)
    quote_no  = (-net_delta < cap) and (-net_delta < skew)

    spread = yes_ask - yes_bid if (yes_bid is not None and yes_ask is not None) else 0.0
    wide = spread >= 0.01 - 1e-9   # room for sub-cent improvement

    no_bid = round(1.0 - yes_ask, 4) if yes_ask is not None else None
    no_ask = round(1.0 - yes_bid, 4) if yes_bid is not None else None

    out = []
    if quote_yes and yes_bid is not None:
        # Sub-cent improve to front of YES bid queue
        if wide:
            p = round(yes_bid + improve_tick, 4)
            if 0.0001 <= p < yes_ask:
                out.append(("yes", p))
        for k in range(layers):
            p = round(yes_bid - k * tick, 4)
            if 0.0001 <= p < (yes_ask or 1.0):
                out.append(("yes", p))
    if quote_no and no_bid is not None:
        if wide:
            p = round(no_bid + improve_tick, 4)
            if 0.0001 <= p < (no_ask or 1.0):
                out.append(("no", p))
        for k in range(layers):
            p = round(no_bid - k * tick, 4)
            if 0.0001 <= p < (no_ask or 1.0):
                out.append(("no", p))
    # deduplicate preserving order
    seen = set(); result = []
    for item in out:
        if item not in seen:
            seen.add(item); result.append(item)
    return result


# --- SMART SIZING (kalshi_sizing.py backtest verdict): size ∝ max(0, mhat - fee(p)) ---
# mhat = markout model fit on ~20k real BTC fills (IS half); spread dominates. fee=0 confirmed live
# on KX*15M makers, kept in the formula so a fee change auto-tightens sizing. The rule is a
# SELECTION effect (bet benign wide-spread fee-cheap fills, refuse the rest), ~14x more capital-
# efficient than flat -- and with fractional Kelly + a hard unit cap the per-window loss is bounded:
# RISK OF RUIN: max size KELLY_MAX units * max_notional clamp * sticky loss-limit kill => a session
# cannot lose more than --loss-limit, and re-arming requires manually deleting the sentinel.
KELLY_COEF = (-0.0085, 0.0074, 0.3794, 0.0077)   # bias, |p-.5|, spread, tau  (BTC ~20k-fill tape fit)
KELLY_T = 0.008                                  # edge threshold (kalshi_sizing.py sweep: OOS Calmar
#                                                  robustly POSITIVE in BOTH fee regimes >= 0.008;
#                                                  below ~0.004 OOS collapses from over-betting)
KELLY_MAX = 2                                     # hard contract cap per fill (units of --post)

def kelly_size(p, spread, tau_frac, fee_mult=0.0):
    """Integer fee-aware Kelly: bet only when predicted net edge clears KELLY_T, size up to KELLY_MAX
    as edge grows. Selection effect (refuse marginal/toxic fills) is what holds OUT-OF-SAMPLE."""
    b0, b1, b2, b3 = KELLY_COEF
    mhat = b0 + b1 * abs(p - 0.5) + b2 * spread + b3 * tau_frac
    edge = mhat - fee_mult * p * (1.0 - p)
    if edge <= KELLY_T:
        return 0
    return min(KELLY_MAX, 1 + int(edge // (2 * KELLY_T)))   # 1, then +1 per 2T of edge, capped


def gate_check(side, price, yes_bid, yes_ask, net_delta, gate, fv_margin, bq=0.0, aq=0.0):
    """True = TOXIC (skip or pull). Mirrors live_trader ufat gate: microprice anchor with
    p-adaptive margin. BUY-YES toxic if mp < price-margin; BUY-NO toxic if mp > (1-price)+margin."""
    if yes_bid is None or yes_ask is None:
        return False
    mp = microprice(yes_bid, yes_ask, bq, aq)
    if mp is None:
        return False
    mid = (yes_bid + yes_ask) / 2.0
    if gate == "ufat":
        margin = fv_margin + MICRO_MARGIN * 4.0 * mid * (1.0 - mid)
    elif gate == "marg":
        margin = fv_margin + MICRO_MARGIN
    else:
        margin = fv_margin
    if side == "yes":
        # BUY-YES: toxic if microprice < price - margin (we'd be buying above fair value)
        return mp < price - margin
    else:
        # BUY-NO at price p => effectively asking YES at (1-p); toxic if anchor > (1-p) + margin
        yes_equiv = round(1.0 - price, 4)
        return mp > yes_equiv + margin


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Kalshi 2-sided passive maker")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--post", type=int, default=5, help="contracts per rung")
    ap.add_argument("--cap", type=float, default=50)
    ap.add_argument("--skew", type=float, default=0.25)
    ap.add_argument("--max-rungs", type=int, default=3, help="max resting rungs per side")
    ap.add_argument("--min-lock", type=float, default=0.0,
                    help="when a quote COMPLETES a box pair, require locked spread >= this (vs the "
                         "window's avg cost of the unpaired leg). Tape: 45%% of natural completions "
                         "lock a NEGATIVE spread (a guaranteed-loss pair = a stop-loss in disguise, "
                         "and stops lose here); skipping them: +211c -> +5003c on sequential pairs")
    ap.add_argument("--close-flatten-tau", type=float, default=120.0,
                    help="in the last N seconds of a window, a COMPLETING quote (one that reduces "
                         "|net|) bypasses the tau-guard and the min-lock floor relaxes toward a small "
                         "bounded negative lock. Live forensics: every directional loss was an "
                         "unpaired leg the tau-guard forbade from completing, riding to settlement "
                         "(-66c/-31c). A small certain lock beats that tail.")
    ap.add_argument("--close-max-give", type=float, default=0.04,
                    help="max negative lock (dollars) we'll accept to complete a box at the very "
                         "close; the floor ramps from --min-lock to -this as tau->0")
    ap.add_argument("--chase-unpaired-s", type=float, default=45.0,
                    help="COMPLETION URGENCY: once a leg has sat unpaired this many seconds, the "
                         "completing side's lock floor relaxes toward --chase-max-give (ramps over "
                         "a second interval of the same length). Attacks the measured failure mode: "
                         "the market trades both sides ~99.7%% of windows but we strand legs in "
                         "~39%% -- mostly the min-lock floor refusing slightly-negative completions "
                         "mid-window until the 120s close ramp. 0 disables.")
    ap.add_argument("--chase-max-give", type=float, default=0.02,
                    help="max negative lock (dollars) the unpaired-age chase will accept mid-window "
                         "(the close ramp's --close-max-give still governs the final seconds)")
    ap.add_argument("--dispose-cross", action="store_true", default=False,
                    help="STRAND DISPOSAL (live RCA 2026-06-13): when a leg stays unpaired past "
                         "--dispose-cross-s OR within --close-flatten-tau of close, COMPLETE the box "
                         "by CROSSING to take the offer (post_only=False, a taker fill) instead of "
                         "riding the naked leg to settlement. Bounded by --chase-max-give (mid-window) "
                         "/ --close-max-give (close). OFF by default (post-only-only); the live trader "
                         "structurally could not complete without this, so strands settled at -21.76c.")
    ap.add_argument("--dispose-cross-s", type=float, default=90.0,
                    help="unpaired AGE (s) at which --dispose-cross TAKES the offer. DECOUPLED from "
                         "--chase-unpaired-s (which governs the MAKER follow-the-touch lock-relaxation) "
                         "so the maker completion gets first crack at pairing cheaply before we pay the "
                         "spread to cross. Near close (<--close-flatten-tau) the cross fires regardless.")
    ap.add_argument("--close-force-s", type=float, default=30.0,
                    help="FINAL seconds before settlement: FORCE-flatten any unpaired leg by crossing at "
                         "ANY price, IGNORING the give budget. Fixes the escaped-strand tail (run 2: 3 "
                         "legs the give-cap refused to cross rode to settlement at -39.8c each). A certain "
                         "bounded completion now always beats the binary settlement variance. Requires "
                         "--dispose-cross. 0 = off (NOT recommended live).")
    ap.add_argument("--max-net", type=int, default=1,
                    help="hard cap on |net YES-NO| contracts: 1 = strict BOX PAIRING (after a YES "
                         "fill, quote only NO until paired). Tape decomposition: box pairs earn "
                         "+18.0c/win risk-free (t=34.5) while unpaired inventory bleeds -16.3c/win "
                         "(t=-16.9); forcing L=1 keeps +1.96c/win, t 2.1->4.3, OOS Calmar 0.5->0.9")
    ap.add_argument("--max-fills-side", type=int, default=4,
                    help="hard cap on FILLS per side per window (post-mortem on 20k tape fills: "
                         "fills 1-4 in a window average +0.08..+0.30c, the 5+ tail is where the "
                         "edge dies; cap=4 keeps 81%% of net while doubling the t-stat 2.1->4.7)")
    ap.add_argument("--fill-cooldown", type=float, default=20.0,
                    help="after a fill (or failed toxic cancel) on a side, do not re-quote that side "
                         "for this many seconds (live data: re-quoting into a trend caught the knife "
                         "4x in one window -- the single largest observed bleed)")
    ap.add_argument("--min-spread", type=float, default=0.01,
                    help="only place when spread >= this (markout model on ~20k fills: 1c-spread "
                         "fills are ~zero-EV; the edge lives at >=2c)")
    ap.add_argument("--tau-guard", type=float, default=150.0,
                    help="no new quotes when under this many seconds to expiry (late fills carry "
                         "systematically worse markouts; binary gamma explodes)")
    ap.add_argument("--fee-mult", type=float, default=0.0,
                    help="maker fee multiplier for this market (fee = mult*p*(1-p)/contract). "
                         "0 = fee-exempt (CRYPTO15M confirmed live); set 0.0175 on maker-fee "
                         "series -- kelly sizing then auto-tightens selection around p=0.5 "
                         "(backtested OOS-positive under both regimes; kalshi_sizing.py)")
    ap.add_argument("--size-mode", choices=["flat", "kelly"], default="flat",
                    help="kelly = fee-aware edge sizing (kalshi_sizing.py): place only when "
                         "mhat-fee>0, size 1..KELLY_MAX units of --post; flat = always --post")
    ap.add_argument("--improve-tick", type=float, default=0.01,
                    help="one tick inside the touch (1c); set 0.001 only if/where the venue accepts sub-cent")
    ap.add_argument("--gate", choices=["ufat", "micro", "marg"], default="ufat")
    ap.add_argument("--max-notional", type=float, default=25)
    ap.add_argument("--notify-fills", dest="notify_fills", action="store_true", default=True,
                    help="push each fill to Telegram in real time (on by default; chatty)")
    ap.add_argument("--no-notify-fills", dest="notify_fills", action="store_false",
                    help="silence per-fill Telegram messages (settlement summaries still send)")
    ap.add_argument("--loss-limit", type=float, default=6,
                    help="per-session realized+mark $ loss that trips the STICKY kill. Widened from "
                         "the old 3: the box edge is near-risk-free per window (|net|<=1 caps "
                         "directional exposure at ~$1/window), and the tape's natural multi-window "
                         "drawdown reaches ~$3.5 -- a $3 stop fired on NORMAL variance. $6 is ~1.7x "
                         "that, i.e. it only trips when a session is going genuinely wrong.")
    ap.add_argument("--markout-kill-bar", type=float, default=-0.04,
                    help="rolling-markout kill: trip if the avg 5s markout over the last "
                         "--markout-kill-n fills is below this. Widened from -0.01: live data shows "
                         "NORMAL 5s markout averages -0.01 (-1c) for this maker, so -0.01 tripped on "
                         "noise (that was the 'toxic_markout' kill). -0.04 is ~4x normal = a genuine "
                         "'we are being systematically run over' regime, the only thing worth halting "
                         "a hold-to-settlement box for.")
    ap.add_argument("--markout-kill-n", type=int, default=50,
                    help="fills in the rolling-markout-kill window (more = steadier, fewer false trips)")
    ap.add_argument("--strand-scaledown", type=str, default="",
                    help="STREAK GUARD (RESEARCH_LOOP R5-5; strands are autocorrelated 2.6x). Comma "
                         "size-multipliers applied to OPENING quotes for each CONSECUTIVE stranded "
                         "window (completion quotes never suppressed). e.g. '0.75,0.5,0.25' scales "
                         "after 1/2/3+ strands; at post=1 a multiplier that rounds to 0 SKIPS opens "
                         "that window (so '0' = skip the window after any strand = the N=1 cooling-off "
                         "that cut maxConsecLoss 50%% in backtest). Empty = OFF. Resets on a clean "
                         "(non-stranded) window. RISK CONTROL, not alpha (t~1.7).")
    ap.add_argument("--poll", type=float, default=1.0, help="housekeeping cadence (s): fills+balance+settles")
    ap.add_argument("--react-poll", type=float, default=0.25, help="book polling cadence (s)")
    ap.add_argument("--duration", type=int, default=3600)
    ap.add_argument("--deadman-s", type=float, default=15.0,
                    help="book stale this many seconds -> cancel-all")
    ap.add_argument("--remote-switch-url", default=os.environ.get("REMOTE_SWITCH_URL", ""),
                    help="poll this URL for the live switch; if it returns 'off' the trader "
                         "flattens (dead-man cancel-all) and exits WITHIN --remote-switch-s seconds. "
                         "This is what makes OFF take <1 min instead of waiting out the cycle. Use the "
                         "GitHub contents API (api.github.com/repos/<o>/<r>/contents/LIVE_SWITCH?ref=<b>) "
                         "with $GH_TOKEN -- it is NOT CDN-cached, unlike raw.githubusercontent.")
    ap.add_argument("--remote-switch-s", type=float, default=20.0,
                    help="how often to poll --remote-switch-url (seconds)")
    ap.add_argument("--reject-cooldown-s", type=float, default=3.0,
                    help="after a post-only reject, do not retry the SAME side+price for this many "
                         "seconds (forensics: 95%% of 2,140 rejects were the same price re-spammed "
                         "<60s apart, 88%% <0.5s -- a churn loop that left the side UNQUOTED)")
    ap.add_argument("--order-ttl-s", type=float, default=150.0,
                    help="venue-side expiration on every order (the dead-man that survives SIGKILL: "
                         "a reaped container's orphan orders self-cancel at the venue within this). "
                         "Healthy quotes refresh via reshape/stale-refresh long before. 0 = GTC")
    ap.add_argument("--qtime-mp-margin", type=float, default=0.0,
                    help="QUEUE-TIMING EXPERIMENT (default 0=OFF). When microprice diverges from mid "
                         "by >= this (e.g. 0.01), reshape an off-target rung IMMEDIATELY instead of "
                         "waiting the 2s churn guard -- beating the mechanical ladder-MM (~1.2s "
                         "heartbeat, FINGERPRINT.md) to the new price level for front-of-queue. Run "
                         "live with this on vs off and compare markout/fill-rate (QUEUE_TIMING.md).")
    ap.add_argument("--guard-yes-spread", type=float, default=0.0,
                    help="t36 guarded opener: suppress YES OPEN quotes when spread < this (e.g. "
                         "0.02). 0 = OFF. Completion quotes (net_delta<0) are never suppressed. "
                         "ARM ONLY after the t36/t02 forward A/B clears the pre-registered bar "
                         "(SCALE_GATE Stage-A condition 4); backtest: OOS +2.07c/win vs P0 +0.69, "
                         "YES strands 36->1 (GUARDED_OPENER.md).")
    # EDGE-SELECT gate (BOX_YIELD t_edge_select): the only POSITIVE-net signal across the whole search
    # is SELECTIVITY -- open ONLY in the fat-box regime. The always-on box is net-negative (shadow + 2
    # live runs); high-vol & late-slot windows are where strands cluster and the edge dies.
    ap.add_argument("--open-k-min", type=int, default=0,
                    help="EDGE-SELECT: only OPEN when the window-minute k >= this (0=off). t_edge_select=5.")
    ap.add_argument("--open-k-max", type=int, default=12,
                    help="EDGE-SELECT: only OPEN when window-minute k <= this. t_edge_select=9.")
    ap.add_argument("--open-sig-lo", type=float, default=0.0,
                    help="EDGE-SELECT: only OPEN when |sig| (spot move bps) >= this. t_edge_select=3.")
    ap.add_argument("--open-sig-hi", type=float, default=0.0,
                    help="EDGE-SELECT: only OPEN when |sig| <= this (0=off). t_edge_select=8 (mid-vol; "
                         "high-vol is a NET LOSS -- captured spread collapses in fast markets).")
    ap.add_argument("--requote-stale-s", type=float, default=20.0,
                    help="drop a resting rung older than this IF the mid has moved >=1 tick since "
                         "placement (markout forensics: fills on >15s-old quotes run -2.04c/fill "
                         "vs +0.79c fresh -- stale quotes are the pick-off; queue position at a "
                         "wrong price is anti-value). 0 disables")
    a = ap.parse_args()

    live = a.live and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if a.live and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. DRY-RUN.")
    mode = "LIVE" if live else "DRY-RUN"

    # STICKY KILL sentinel (same as live_trader): survives systemd Restart=always so a kill-switch
    # isn't immediately overridden. Delete the file manually after investigating.
    kill_sentinel = f".kalshi_killed_{a.asset}15m"

    def _record_kill(why):
        try:
            with open(kill_sentinel, "w") as fh:
                fh.write(json.dumps({"ts": time.time(), "reason": why}) + "\n")
        except Exception:
            pass

    if live and os.path.exists(kill_sentinel):
        raise SystemExit(f"REFUSING to start live: kill sentinel {kill_sentinel} exists. "
                         "Investigate, then delete it to re-arm.")

    sess = requests.Session()
    priv = None
    if live:
        # Load RSA key at startup; a missing/invalid key is a fatal config error, not a runtime one.
        priv = _load_private_key()
        if not priv:
            raise SystemExit("KALSHI_PRIVATE_KEY_PATH not set or key unreadable; cannot trade live.")
        if not os.environ.get("KALSHI_API_KEY_ID"):
            raise SystemExit("KALSHI_API_KEY_ID not set; cannot trade live.")

    # CONTROL L1 (double-trader incident 2026-06-12): exclusive per-asset instance lock held for
    # the process lifetime. Two traders on one account each obey max-net independently and breach
    # it jointly -- this makes a second LOCAL trader physically unable to start.
    if live:
        import fcntl
        _lockf = open(f".kalshi_trader_{a.asset}15m.lock", "w")
        try:
            fcntl.flock(_lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lockf.write(f"{os.getpid()} {time.time()}\n"); _lockf.flush()
        except OSError:
            raise SystemExit(f"FATAL: another kalshi_trader holds .kalshi_trader_{a.asset}15m.lock "
                             f"-- refusing to double-trade this account")

    lm = LiveMetrics(a.asset, 15, path=f"live_metrics_kalshi_{a.asset}15m.jsonl")

    # C7 startup reconciliation: cancel all open orders on this series so we start from a provably
    # flat book. A SIGKILL'd predecessor's orders would otherwise rest blind. Fail-closed: if we
    # can't verify flat, don't trade.
    # --- WS feeder state (shared with daemon thread) ---
    # ws_state: ticker -> {yes:{price:qty}, no:{price:qty}, ts, bb, bq, ba, aq}
    ws_state = {}
    # ws_sub: ticker + epoch; feeder resubscribes when epoch bumps (window rollover)
    ws_sub = {"ticker": None, "epoch": 0}
    # book_evt: set on every WS book delta -> event-driven OMS reaction (mirrors live_trader)
    book_evt = threading.Event()
    # ws_fills: real-time own fills from WS fill channel; drained each loop before REST poll
    ws_fills = collections.deque()
    side_cooldown = {"yes": 0.0, "no": 0.0}   # no re-quote on a side until this ts (anti-knife)
    win_fills = {"yes": 0, "no": 0}            # fills per side THIS window (trend-exposure cap)
    win_cost = {"yes": 0.0, "no": 0.0}         # $ spent per side THIS window (box telemetry)
    # COMPREHENSIVE per-window microstructure (live RCA 2026-06-13): the re-validation gate (strand
    # rate, legging gap, maker/taker mix, dispose-cross firing) plus the offline strand analysis read
    # this. Written per window to kalshi_winrec_<asset>15m.jsonl, reset at rollover.
    winrec = {"taker": 0, "maker": 0, "maxnet": 0.0, "first_ts": {}, "dispose_cross": 0}
    winrec_fh = open(f"kalshi_winrec_{a.asset}15m.jsonl", "a")
    loop_ctx = {}                              # decision-time book state, stamped onto each fill
    threading.Thread(target=_spot_poller, args=(_COINBASE_PRODUCT.get(a.asset, "BTC-USD"),),
                     daemon=True).start()   # sig telemetry (isolated; non-blocking; per-asset spot)
    ops = {"place": 0, "cancel": 0, "cancel_fail": 0}   # per-window execution-quality counters

    if live:
        print("[startup] reconciling open orders on series...")
        init_mk = discover(sess, a.asset)
        if init_mk:
            try:
                oo = get_open_orders(sess, priv, init_mk["cid"])
                for o in oo:
                    oid = str(o.get("order_id") or "")
                    if oid:
                        cancel_order(sess, priv, oid)
                        print(f"  [startup] cancelled stale order {oid[:16]}")
            except Exception as e:
                raise SystemExit(f"startup cancel FAILED ({type(e).__name__}: {str(e)[:120]}) -- "
                                 "refusing to quote on top of unknown resting orders")
        print("[startup] reconciliation done.")
        # Start authenticated WS feeder (live only; needs priv key + KALSHI_API_KEY_ID)
        threading.Thread(
            target=ws_feeder,
            args=(ws_state, ws_sub, book_evt, ws_fills, priv),
            daemon=True,
        ).start()
        print("  [ws-book] feeder thread started")

    print(f"[{mode}] kalshi_trader asset={a.asset} post={a.post} cap={a.cap} skew={a.skew} "
          f"max_rungs={a.max_rungs} gate={a.gate} max_notional={a.max_notional} "
          f"loss_limit={a.loss_limit} improve_tick={a.improve_tick}")
    notify.alert(f"[kalshi] trader start {mode} asset={a.asset} cap={a.cap}")


    # --- state ---
    mk = None
    net_delta = 0.0          # YES positions - NO positions (signed)
    unpaired_since = None    # wall-clock when |net| left 0 (completion-urgency chase clock)
    realized = 0.0           # settled P&L across closed windows
    _strand_sched = [float(x) for x in a.strand_scaledown.split(",") if x.strip()]  # streak guard
    _consec_strands = 0      # consecutive stranded windows (drives --strand-scaledown)
    window_mark = 0.0        # current window mark-to-mid (open position value)
    pos = {}                 # ticker+"YES"|"NO" -> contracts held (from fills)
    cash = 0.0               # net cash flow this window (positive = received)
    resting = {}             # (side, price) -> {"oid", "ts"}  for THIS window
    placed_oids = set()      # every order_id placed this session
    seen_fills = {}          # ticker -> set of fill "trade_id" already booked
    markouts = []            # rolling 5s markout list (last 500)
    pending_settles = []     # [{"cid","ws","pos_yes","pos_no","cash","r","t0"}]
    pending_markouts = []    # [(due_ts, fill_dict)]
    _settle_cache = {}       # cid -> settled result (audit H3: score post-rollover markouts vs settlement)
    next_mk = {"mk": None, "tried_we": 0}   # prefetched next-window market

    last_book_ok = time.time()
    deadman_tripped = False
    consec_err = 0
    total_err = 0            # audit M3: cumulative loop errors (intermittent errors never reach 5-consecutive)
    last_hk = 0.0
    last_reconcile = 0.0
    mo_fh = open("kalshi_markout.jsonl", "a")

    # --- cancel / dead-man infrastructure ---
    cancel_q = []   # [(oid, key, reason)] queued this pass (batched like live_trader.flush_cancels)
    reject_cd = {}  # (side, price) -> retry-not-before ts (post-only reject churn breaker)
    qtime_ct = [0]  # queue-timing experiment: count of microprice-triggered fast reshapes
    _foreign_chk = [0.0]   # last foreign-order scan ts (CONTROL L2 throttle)

    pending_cancel = {}  # key -> meta: cancel SENT but not venue-confirmed. THE CLAMP LEAK FIX
    # (live breach 2026-06-12, |net|=-2): drop() used to erase the order from `resting` instantly;
    # on CANCEL-FAIL the order stayed LIVE at the venue but invisible to the inventory projection,
    # so a second same-side order was placed and both filled. Orders now count against the clamp
    # until the venue confirms the cancel OR their fill books.

    def drop(key, reason):
        """Queue a cancel without sending yet (batched in flush_cancels)."""
        meta = resting.pop(key, None)
        if meta is None:
            return
        meta["cq_ts"] = time.time()
        pending_cancel[key] = meta
        cancel_q.append((meta["oid"], key, reason))

    def flush_cancels():
        """Send every queued cancel sequentially in one pass (mirrors live_trader batching)."""
        if not cancel_q:
            return
        batch = cancel_q[:]
        cancel_q.clear()
        t_sent = time.time()
        ok = True
        for oid, key, reason in batch:
            if live:
                ok2 = cancel_order(sess, priv, oid)
                ops["cancel"] += 1
                if ok2:
                    pending_cancel.pop(key, None)        # venue-confirmed gone -> stop counting it
                else:
                    ops["cancel_fail"] += 1
                    lm.event("cancel_fail", side=key[0], price=key[1], reason=reason)
                    print(f"  [CANCEL-FAIL] {oid[:16]} key={key} reason={reason}")
                    side_cooldown[key[0]] = time.time() + a.fill_cooldown   # likely filling against us
                    ok = False                            # stays in pending_cancel -> clamp sees it
            else:
                print(f"  [DRY cancel] key={key} reason={reason}")
                pending_cancel.pop(key, None)
        lm.cancel_batch(len(batch), (time.time() - t_sent) * 1e3, ok)

    def cancel_all_resting(reason="rollover"):
        """Cancel everything we think is resting, then do a venue-side sweep for THIS ticker."""
        for key in list(resting):
            try:
                drop(key, reason)
            except Exception as e:
                resting.pop(key, None)
                print(f"  [DROP-FAIL] {key}: {e}")
        try:
            flush_cancels()
        except Exception as e:
            print(f"  [FLUSH-FAIL] {e}")
        # Venue-side backstop: cancel all open orders on current ticker (catches strays /
        # anything local bookkeeping lost track of). Non-rollover only (rollover re-uses the ticker
        # after the next window opens; we sweep strays in the 5s reconciliation pass instead).
        if live and reason != "rollover" and mk is not None:
            oo = get_open_orders(sess, priv, mk["cid"])
            for o in oo:
                oid2 = str(o.get("order_id") or "")
                if oid2:
                    cancel_order(sess, priv, oid2)

    # C1 DEAD-MAN: guarantee cancel-all on any exit (normal, exception, SIGTERM, Ctrl-C).
    _flattened = {"done": False}

    def _flatten_and_exit(reason):
        if _flattened["done"]:
            return
        _flattened["done"] = True
        try:
            print(f"[DEAD-MAN] {reason}: cancelling all resting orders")
            cancel_all_resting(reason="deadman")
            # LIQUIDATE open inventory (audit C2): cancel-only left naked legs riding to settlement,
            # so the loss-limit/dead-man/remote-off rails could NOT actually cap the loss. Cross to
            # flatten any net position before exiting. (Skip on 'rollover' -- that path settles normally.)
            if live and reason != "rollover" and mk is not None:
                try:
                    nd = net_delta
                    if abs(nd) > 1e-9:
                        bb_, _bq, ba_, _aq, _f = get_book_cached(mk["cid"], max_age=3.0)
                        if bb_ is not None and ba_ is not None:
                            need_ = int(round(abs(nd)))
                            if nd > 0:    # hold YES -> BUY NO at the no-offer to flatten
                                place("no", round(1.0 - bb_, 4), bb_, ba_, count=need_, cross=True)
                            else:         # hold NO -> BUY YES at the yes-offer to flatten
                                place("yes", round(ba_, 4), bb_, ba_, count=need_, cross=True)
                            print(f"[DEAD-MAN] LIQUIDATE net={nd:+.0f} via cross (rail must cap the loss)")
                            notify.alert_sync(f"[kalshi] LIQUIDATED net={nd:+.0f} on {reason}")
                except Exception as e:
                    print(f"[DEAD-MAN] liquidate failed: {str(e)[:120]}")
            # planned completions get a calm message; "DEAD-MAN" is reserved for genuine
            # protective trips (it read like a crash to the operator on a normal session end)
            if "planned" in reason:
                notify.alert_sync(f"🏁 {reason} — all orders cancelled cleanly")
            else:
                notify.alert_sync(f"[kalshi] DEAD-MAN {reason}: cancel-all")
        except Exception as e:
            print(f"[DEAD-MAN] cancel failed: {str(e)[:120]}")

    # FAST REMOTE OFF: poll the live switch out-of-band so flipping it OFF stops a RUNNING trader
    # within --remote-switch-s (the cron/cycle only gates STARTING; this gates STOPPING). Cheap GET;
    # any error is ignored (fail-safe: a transient fetch failure must NOT kill a healthy session).
    _rsw = {"last": 0.0}
    _gh_tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def _remote_switch_is_off():
        url = a.remote_switch_url
        if not url:
            return False
        now = time.time()
        if now - _rsw["last"] < a.remote_switch_s:
            return None              # not due yet
        _rsw["last"] = now
        try:
            hdrs = {"Accept": "application/vnd.github.raw+json"}
            if _gh_tok and "api.github.com" in url:
                hdrs["Authorization"] = f"Bearer {_gh_tok}"
            r = requests.get(url, headers=hdrs, timeout=6)
            if r.status_code == 200:
                return r.text.strip().lower().startswith("off")
        except Exception:
            pass
        return False                 # unreachable -> treat as still-on (fail-safe)

    atexit.register(lambda: _flatten_and_exit("process exit"))
    # SIGHUP included so closing the desktop launcher's terminal window cancels all orders cleanly
    # (the window/process lifetime is the on/off switch). SIGHUP is absent on Windows -> guarded.
    _sigs = [signal.SIGTERM, signal.SIGINT]
    if hasattr(signal, "SIGHUP"):
        _sigs.append(signal.SIGHUP)
    for _sig in _sigs:
        try:
            signal.signal(_sig, lambda *_, s_=_sig: (_flatten_and_exit(f"signal {s_}"), os._exit(0)))
        except Exception:
            pass

    # --- place helper ---
    def place(side, price, yes_bid, yes_ask, count=None, cross=False):
        """Post one rung. Returns order_id or None. DRY-RUN: prints, returns fake id.
        side='yes'|'no'. price in dollars (up to 4 decimals).
        Post-only guard (cross=False, default): we only place maker BUYs; Kalshi's post_only=True
        rejects if marketable, and belt-and-suspenders we also refuse a BUY-YES >= yes_ask / BUY-NO
        >= (1-yes_bid) before sending. cross=True (DISPOSAL ONLY): deliberately TAKE the offer to
        COMPLETE a stranded box (post_only=False) -- skip the guard; the caller bounds the give."""
        if not cross:
            if side == "yes" and yes_ask is not None and price >= yes_ask:
                print(f"  [POST-ONLY GUARD] BUY-YES {price} >= yes_ask {yes_ask}; skipped")
                return None
            if side == "no":
                no_ask = round(1.0 - (yes_bid or 0.0), 4)
                if price >= no_ask:
                    print(f"  [POST-ONLY GUARD] BUY-NO {price} >= no_ask {no_ask}; skipped")
                    return None
        t_dec = time.time()
        if not live:
            fake = f"dry_{side}_{price:.4f}_{int(t_dec*1000)%100000}"
            print(f"  [DRY {'CROSS-COMPLETE' if cross else 'place'}] BUY-{side.upper()} {count or int(a.post)} @ {price:.4f}")
            return fake, t_dec, time.time()
        oid, sc_, err_ = place_order(sess, priv, mk["cid"], side, price, count or int(a.post),
                                     ttl_s=(a.order_ttl_s or None), post_only=not cross)
        t_ack = time.time()
        if oid is None:
            lm.place_reject(side, price, f"HTTP {sc_}: {err_}")
            reject_cd[(side, round(price, 4))] = time.time() + a.reject_cooldown_s
            return None
        placed_oids.add(oid)
        ops["place"] += 1
        lm.place_ack(side, price, False, (t_ack - t_dec) * 1e3)
        return oid, t_dec, t_ack

    # --- book: WS cache (primary) + REST cache (fallback) ---
    _last_book_cache = {}   # ticker -> (ts, yes_bid, ybq, yes_ask, yaq)

    def get_book_cached(ticker, max_age=None):
        """Prefer WS book when fresh (<2s). Falls back to throttled REST poll.
        Returns (yes_bid, ybq, yes_ask, yaq, fresh).
        fresh=True when data is from the WS OR from a new REST fetch this call."""
        max_age = max_age or a.react_poll
        # --- WS primary path ---
        ws_st = ws_state.get(ticker)
        if (ws_st is not None
                and ws_st.get("bb") is not None
                and ws_st.get("ba") is not None
                and (time.time() - ws_st["ts"]) <= 2.0):
            return ws_st["bb"], ws_st["bq"], ws_st["ba"], ws_st["aq"], True
        # --- REST fallback ---
        c = _last_book_cache.get(ticker)
        if c and (time.time() - c[0]) < max_age:
            return c[1], c[2], c[3], c[4], False
        ybb, ybq, yba, yaq = get_book(sess, ticker)
        if ybb is not None:
            _last_book_cache[ticker] = (time.time(), ybb, ybq, yba, yaq)
            return ybb, ybq, yba, yaq, True
        # return stale if available (keeps dead-man watchdog from over-firing on single blips)
        return (c[1], c[2], c[3], c[4], False) if c else (None, None, None, None, False)

    # --- fill booking (poll-based, scoped to current ticker) ---
    def book_fill(ticker, f, sf):
        """Book a single fill dict into pos/cash/net_delta and pending_markouts.
        Shared by ws_fills drain (real-time) and REST poll_fills (backstop).
        sf is the seen_fills set for this ticker; caller must add fid to sf on return.
        Returns True if the fill was booked, False if skipped (caller should still add to sf)."""
        nonlocal cash, net_delta
        fside = str(f.get("side") or "").lower()    # "yes" or "no"
        count = float(f.get("count_fp") or f.get("count") or 0)
        # H-3: prefer yes_price_dollars; if only yes_price and > 1.0, divide by 100
        yp_raw = f.get("yes_price_dollars")
        from_cents = False
        if yp_raw is None:
            yp_raw = f.get("yes_price")
            from_cents = True
        if yp_raw is None or count <= 0 or fside not in ("yes", "no"):
            return False
        yp = float(yp_raw)
        if from_cents and yp > 1.0:
            yp /= 100
        fp = yp if fside == "yes" else round(1.0 - yp, 4)
        # H-3 sanity guard: skip fills with price outside (0, 1)
        if not (0.0 < fp < 1.0):
            fid_dbg = str(f.get("trade_id") or f.get("fill_id") or "?")
            print(f"[FILL-AMBIGUOUS] fill {fid_dbg} has price {fp} outside (0,1); skipping")
            return False
        # inventory bookkeeping: BUY-YES adds +1 net, BUY-NO adds -1 net
        sgn = 1.0 if fside == "yes" else -1.0
        pos_key = ticker + ":" + fside.upper()
        pos[pos_key] = pos.get(pos_key, 0.0) + count
        cash -= fp * count               # buy spends cash
        net_delta += sgn * count
        if abs(net_delta) > float(a.max_net) + 0.5:      # clamp leak tripwire (double-fill forensics)
            notify.alert(f"\u26a0\ufe0f INVENTORY BREACH: |net|={net_delta:+.0f} exceeds max-net "
                         f"{a.max_net} after {fside} fill @ {fp} -- clamp leak, investigate")
        win_fills[fside] = win_fills.get(fside, 0) + 1   # per-window same-side fill count (trend cap)
        win_cost[fside] = win_cost.get(fside, 0.0) + fp * count
        # per-window microstructure trackers (legging gap, maker/taker mix, max imbalance)
        winrec["taker" if f.get("is_taker") else "maker"] += 1
        winrec["first_ts"].setdefault(fside, time.time())
        winrec["maxnet"] = max(winrec["maxnet"], abs(net_delta))
        key = (fside, round(fp, 4))
        pc = pending_cancel.get(key)
        if pc is not None:
            pc["filled"] = pc.get("filled", 0.0) + count
            if pc["filled"] >= a.post - 1e-9:
                pending_cancel.pop(key, None)            # raced cancel resolved as a fill
        meta = resting.get(key)
        resting_s = (time.time() - meta["ts"]) if meta else None
        if meta:
            meta["filled"] = meta.get("filled", 0.0) + count
            if meta["filled"] >= meta.get("want", a.post) - 1e-9:   # AUDIT M5: per-order size, not global post
                resting.pop(key, None)
        fid = str(f.get("trade_id") or f.get("fill_id") or "")
        # MARKOUT CURVE (adverse-selection telemetry): score this fill against the mid at
        # 5s/30s/60s/300s. 5s feeds the rolling markout kill; the full curve is the offline
        # "am I getting picked off?" measurement. cid pins the window so a markout never
        # references the NEXT market's book after rollover.
        # stamp the DECISION-TIME context (Prevention #0) so each markout record is self-contained:
        # sig (spot move), microprice, spread/mid, and the active guard threshold.
        _ctx = {"sig": loop_ctx.get("sig"), "spot": loop_ctx.get("spot"),
                "micro": loop_ctx.get("micro"), "spread": loop_ctx.get("spread"),
                "mid": loop_ctx.get("mid"), "guard": (a.guard_yes_spread or None)}
        for _h in (5.0, 30.0, 60.0, 300.0):
            pending_markouts.append((time.time() + _h, {
                "fside": fside, "fp": fp, "count": count, "h": _h, "cid": ticker,
                "resting_s": resting_s, "oid": (meta or {}).get("oid", fid), **_ctx}))
        # FEE GROUND TRUTH (the load-bearing Kalshi unknown): capture the venue's reported fee on
        # every fill, raw, to a dedicated log -- the per-series maker-fee question the public docs
        # can't fully answer is settled by what Kalshi actually charges here.
        fee_val = f.get("fee_cost")  # CONFIRMED live: Kalshi fills report fee in "fee_cost" (=0 on KXBTC15M maker)
        mkr = "taker" if f.get("is_taker") else "maker"
        try:
            with open(f"kalshi_fees_{a.asset}15m.jsonl", "a") as _ff:
                _ff.write(json.dumps({"ts": time.time(), "ticker": ticker, "side": fside,
                                      "price": fp, "count": count, "role": mkr,
                                      "fee_reported": fee_val,
                                      # DECISION CONTEXT (effective spread, adverse selection,
                                      # inventory, queue metrics all derive from these):
                                      "ctx": {**loop_ctx,
                                              "net_delta_after": net_delta,
                                              "win_fills": dict(win_fills),
                                              "resting_s": resting_s,
                                              "t_in_win": round(time.time() - mk["ws"], 1)
                                                          if mk else None},
                                      "raw": f}) + "\n")
        except Exception:
            pass
        src = "WS" if f.get("_ws") else "REST"
        print(f"  [FILL/{src}] {mkr.upper()} {fside} {count}@{fp} fee={fee_val} "
              f"(roundtrip the raw fill in kalshi_fees_{a.asset}15m.jsonl)")
        # FEE TRIPWIRE (fee research 2026-06-12): the $0 maker fee is OBSERVED, not documented as an
        # exemption -- it may be a rounding artifact that breaks at larger fills, and Kalshi's FIX
        # API recently un-hardcoded settlement fees. A nonzero maker fee changes the box math NOW.
        try:
            if mkr == "maker" and fee_val is not None and float(fee_val) > 1e-9:
                notify.alert(f"🚨 FEE ALERT: maker fill charged fee={fee_val} on {ticker} "
                             f"({count}@{fp}). The $0-maker-fee assumption just broke — review "
                             f"box economics before continuing to scale.")
        except Exception:
            pass
        lm.fill(fside, fp, count, resting_s, None, mkr, fee_val, 0.0,
                # per-fill experiment/book context (telemetry upgrade 2026-06-12): makes live
                # A/B reads direct instead of proxy-based — guard state for t36 arming, qtime
                # margin in effect, decision-time spread/mid/microprice from loop_ctx.
                spread=loop_ctx.get("spread"), mid=loop_ctx.get("mid"),
                micro=loop_ctx.get("micro"),
                guard=(a.guard_yes_spread or None), qtm=(a.qtime_mp_margin or None))
        if a.notify_fills:        # real-time fill -> Telegram, framed as box economics not raw price
            py = sum(v for k_, v in pos.items() if k_.endswith(":YES"))
            pn = sum(v for k_, v in pos.items() if k_.endswith(":NO"))
            bx = min(py, pn)
            my, other = (py, pn) if fside == "yes" else (pn, py)
            if bx > 0 and my <= other:        # this fill COMPLETED a box pair (raised the matched count)
                ay = win_cost.get("yes", 0.0) / py if py else 0.0
                an = win_cost.get("no", 0.0) / pn if pn else 0.0
                lock_c = (1.0 - ay - an) * 100.0          # per-pair lock (held to settlement)
                win_c = bx * lock_c
                if lock_c >= -1e-9:
                    notify.alert(f"\U0001f4e6 box paired ({bx:g}x) +{lock_c:.1f}c/pair locked "
                                 f"risk-free (window {win_c:+.0f}c)")
                else:
                    notify.alert(f"\U0001f4e6 box flattened ({bx:g}x) {lock_c:.1f}c/pair — closing "
                                 f"unpaired legs near expiry to cap directional risk (window {win_c:+.0f}c)")
            else:                              # opened an unpaired leg, waiting for the other side
                notify.alert(f"➕ {fside} leg @ {fp:g} — waiting to pair")
        return True

    def drain_ws_fills():
        """Drain the real-time ws_fills deque and book each unseen fill immediately.
        Dedup via seen_fills so REST poll backstop can't double-book the same fill."""
        if mk is None:
            return
        ticker = mk["cid"]
        sf = seen_fills.setdefault(ticker, set())
        while ws_fills:
            try:
                f = ws_fills.popleft()
            except IndexError:
                break
            # WS fill msg may use different id fields; try both
            fid = str(f.get("trade_id") or f.get("fill_id") or "")
            if not fid:
                print(f"[FILL-NOID/WS] fill missing trade_id/fill_id: {str(f)[:120]}")
                continue
            if fid in sf:
                continue
            # Tag as WS-sourced for the log line
            f["_ws"] = True
            book_fill(ticker, f, sf)
            sf.add(fid)

    def poll_fills():
        """Pull /portfolio/fills scoped to mk['cid'] and book into pos/cash/net_delta.
        REST backstop: fills already booked via ws_fills are deduped by seen_fills.
        Mirrors live_trader's housekeeping fill poll."""
        if not live or mk is None:
            return
        ticker = mk["cid"]
        sf = seen_fills.setdefault(ticker, set())
        fills = get_fills(sess, priv, ticker)
        # C-4: on first call for a ticker, seed all existing fill ids without booking them
        if ticker not in seeded:
            for f in fills:
                fid = str(f.get("trade_id") or f.get("fill_id") or "")
                if fid:
                    sf.add(fid)
            seeded.add(ticker)
            return
        for f in fills:
            fid = str(f.get("trade_id") or f.get("fill_id") or "")
            if not fid:
                print(f"[FILL-NOID] fill missing trade_id/fill_id: {str(f)[:120]}")
                continue
            if fid in sf:
                continue
            book_fill(ticker, f, sf)
            sf.add(fid)

    def sweep_window_fills(ticker, en=None):
        """C-1 boundary-fill leak: sweep fills for a CLOSING window into the ledger (en=None)
        or into a pending_settles entry, just like live_trader.sweep_closed_window."""
        if not live:
            return
        sf = seen_fills.setdefault(ticker, set())
        fills = get_fills(sess, priv, ticker)
        for f in fills:
            fid = str(f.get("trade_id") or f.get("fill_id") or "")
            if not fid or fid in sf:
                continue
            fside = str(f.get("side") or "").lower()
            count = float(f.get("count_fp") or f.get("count") or 0)
            # H-3: prefer yes_price_dollars; if only yes_price and > 1.0, divide by 100
            yp_raw = f.get("yes_price_dollars")
            from_cents = False
            if yp_raw is None:
                yp_raw = f.get("yes_price")
                from_cents = True
            if yp_raw is None or count <= 0 or fside not in ("yes", "no"):
                sf.add(fid); continue
            yp = float(yp_raw)
            if from_cents and yp > 1.0:
                yp /= 100
            fp = yp if fside == "yes" else round(1.0 - yp, 4)
            # H-3 sanity guard: skip fills with price outside (0, 1)
            if not (0.0 < fp < 1.0):
                print(f"[FILL-AMBIGUOUS] fill {fid} has price {fp} outside (0,1); skipping")
                sf.add(fid); continue
            sgn = 1.0 if fside == "yes" else -1.0
            if en is None:
                pk = ticker + ":" + fside.upper()
                pos[pk] = pos.get(pk, 0.0) + count
                cash -= fp * count
                net_delta += sgn * count
            else:
                if fside == "yes":
                    en["pos_yes"] += count
                else:
                    en["pos_no"] += count
                en["cash"] -= fp * count
            print(f"  [LATE-FILL] BUY-{fside.upper()} {count}@{fp:.4f} booked to closing window")
            sf.add(fid)

    # --- poll live balance into live_metrics ---
    _last_balance_poll = 0.0

    def poll_balance_lm():
        nonlocal _last_balance_poll
        if not live or time.time() - _last_balance_poll < 60.0:
            return
        _last_balance_poll = time.time()
        raw = get_balance(sess, priv)
        if raw is not None:
            lm.event("balance", raw=raw if isinstance(raw, dict) else str(raw)[:200])
        else:
            lm.event("balance_err", err="no response")

    # -----------------------------------------------------------------------
    end = time.time() + a.duration
    while time.time() < end:
        try:
            # FAST OFF: operator flipped LIVE_SWITCH off -> flatten and exit this cycle now (<1 min),
            # don't ride out --duration. Returns None when not yet due (throttled), True/False on poll.
            if live and _remote_switch_is_off():
                print("[SWITCH] remote LIVE_SWITCH=off -> flatten and exit")
                notify.alert_sync("\U0001f534 live bot OFF (remote switch) — flattening, cancelling all orders")
                _flatten_and_exit("remote switch off")
                break

            # C1 staleness watchdog: book dark > deadman-s with resting orders -> cancel-all
            stale = time.time() - last_book_ok
            if live and resting and stale > a.deadman_s and not deadman_tripped:
                print(f"[DEAD-MAN] book feed stale {stale:.0f}s > {a.deadman_s}s -> cancel-all")
                notify.alert(f"[kalshi] DEAD-MAN feed stale {stale:.0f}s: cancel-all")
                lm.ws_stale(stale)
                cancel_all_resting(reason="deadman_stale")
                deadman_tripped = True

            # Window rollover
            if mk is None or time.time() >= mk["we"]:
                if mk is not None:
                    # Settle closing window: sweep boundary fills, queue pending settle
                    if live:
                        sweep_window_fills(mk["cid"])
                    r_now = resolve_result(sess, mk["cid"])
                    if pos or abs(cash) > 1e-9:
                        entry = {
                            "cid": mk["cid"], "ws": mk["ws"],
                            "pos_yes": sum(v for k, v in pos.items() if k.endswith(":YES")),
                            "pos_no":  sum(v for k, v in pos.items() if k.endswith(":NO")),
                            "cash": cash, "r": r_now, "t0": time.time(),
                        }
                        pending_settles.append(entry)
                    lm.window_summary(mk["ws"], realized, window_mark, net_delta)
                    # BOX telemetry: paired yes/no contracts pay $1 at settlement regardless of
                    # outcome -- the locked, risk-free component of this window's book.
                    py = sum(v for k, v in pos.items() if k.endswith(":YES"))
                    pn = sum(v for k, v in pos.items() if k.endswith(":NO"))
                    bx = min(py, pn)
                    if bx > 0:
                        ay = win_cost["yes"] / max(py, 1e-9)
                        an = win_cost["no"] / max(pn, 1e-9)
                        print(f"  [BOX] paired={bx:.0f} locked~${bx*(1.0-ay-an):+.2f} "
                              f"(yes {py:.0f}@{ay:.2f} + no {pn:.0f}@{an:.2f}) "
                              f"unpaired={abs(py-pn):.0f} directional")
                    nf = win_fills["yes"] + win_fills["no"]
                    print(f"  [OPS] places={ops['place']} cancels={ops['cancel']} "
                          f"cancel_fails={ops['cancel_fail']} qtime={qtime_ct[0]} fills={nf} "
                          f"quote_to_trade={ops['place']/max(nf,1):.1f}")
                    # STREAK GUARD: a window with an unpaired residual (|py-pn|>0) stranded; strands
                    # are autocorrelated (2.6x), so count consecutive strands to scale down the next
                    # window's opens (--strand-scaledown). Clean window resets the streak.
                    if _strand_sched:
                        _consec_strands = _consec_strands + 1 if abs(py - pn) > 0.5 else 0
                    # COMPREHENSIVE per-window microstructure record (re-validation gate + analysis):
                    # strand state, box edge, legging gap, maker/taker mix, dispose-cross firing.
                    _ft = winrec["first_ts"]
                    _legging = (abs(_ft["yes"] - _ft["no"]) if ("yes" in _ft and "no" in _ft) else None)
                    try:
                        winrec_fh.write(json.dumps({
                            "ts": time.time(), "asset": a.asset, "ws": mk["ws"], "cid": mk["cid"],
                            "settle": r_now, "net_final": net_delta,
                            "n_yes": win_fills["yes"], "n_no": win_fills["no"],
                            "n_boxes": int(min(py, pn)), "stranded": bool(abs(py - pn) > 0.5),
                            "abs_strand": float(abs(py - pn)), "maxnet": winrec["maxnet"],
                            "legging_gap_s": _legging, "n_taker": winrec["taker"],
                            "n_maker": winrec["maker"], "n_dispose_cross": winrec["dispose_cross"],
                            "cost_yes": round(win_cost["yes"], 4), "cost_no": round(win_cost["no"], 4),
                            "consec_strands": _consec_strands, "realized": round(realized, 4),
                            "window_mark": round(window_mark, 4),
                            "guard_yes": (a.guard_yes_spread or None),
                            "max_fills_side": a.max_fills_side, "dispose_cross_on": bool(a.dispose_cross),
                        }) + "\n")
                        winrec_fh.flush()
                    except Exception:
                        pass
                    winrec = {"taker": 0, "maker": 0, "maxnet": 0.0, "first_ts": {}, "dispose_cross": 0}
                    pos.clear(); cash = 0.0; net_delta = 0.0; window_mark = 0.0
                win_fills = {"yes": 0, "no": 0}   # fresh window, fresh trend-exposure budget
                win_cost = {"yes": 0.0, "no": 0.0}
                ops = {"place": 0, "cancel": 0, "cancel_fail": 0}

                cancel_all_resting()   # tokens change on rollover; reset resting book

                # Use prefetched next window if available (zero-RTT rollover for queue priority)
                pf = next_mk["mk"]
                now0 = int(time.time())
                if pf is not None and pf["ws"] <= now0 < pf["we"]:
                    mk = pf; next_mk["mk"] = None
                else:
                    mk = discover(sess, a.asset)
                if not mk:
                    time.sleep(a.poll); continue
                _last_book_cache.clear()
                # Update WS feeder subscription: new ticker + bump epoch so feeder resubscribes
                ws_sub["ticker"] = mk["cid"]
                ws_sub["epoch"] += 1
                print(f"WINDOW {mk['ws']} {datetime.fromtimestamp(mk['ws'], timezone.utc):%H:%M}Z "
                      f"ticker={mk['cid']}")

            hk = (time.time() - last_hk) >= a.poll

            # Prefetch next window ~45s before expiry (off-thread, same as live_trader)
            if hk and mk is not None and (mk["we"] - time.time()) < 45 and next_mk["tried_we"] != mk["we"]:
                next_mk["tried_we"] = mk["we"]
                def _prefetch(we_next, asset_=a.asset):
                    m2 = discover(requests.Session(), asset_)
                    if m2 is not None and m2["ws"] == we_next:
                        next_mk["mk"] = m2
                threading.Thread(target=_prefetch, args=(mk["we"],), daemon=True).start()

            # C2 LOSS-LIMIT: realized + open window mark. AUDIT H6: window_mark marks the open leg at MID,
            # but a held binary leg settles 0/1 -- mid HALVES the true tail risk so the limit trips late /
            # can be breached. Use the WORST-CASE open loss (the unpaired leg's full cost basis: a long
            # YES loses its cost if it settles NO, etc.) so the kill is conservative on directional risk.
            worst_open = 0.0
            if abs(net_delta) > 1e-9:
                if net_delta > 0:
                    py_ = sum(v for k_, v in pos.items() if k_.endswith(":YES"))
                    worst_open = -(win_cost["yes"] / py_ * abs(net_delta)) if py_ > 0 else 0.0
                else:
                    pn_ = sum(v for k_, v in pos.items() if k_.endswith(":NO"))
                    worst_open = -(win_cost["no"] / pn_ * abs(net_delta)) if pn_ > 0 else 0.0
            kill_mark = min(window_mark, worst_open)
            if realized + kill_mark <= -abs(a.loss_limit):
                print(f"KILL: realized {realized:+.2f} + worst-open {kill_mark:+.2f}. liquidate + exit.")
                notify.alert(f"[kalshi] KILL loss-limit (real {realized:+.2f} worst-open {kill_mark:+.2f})")
                _record_kill(f"loss_limit realized={realized:+.2f} worst_open={kill_mark:+.2f}")
                _flatten_and_exit("loss_limit"); break

            # Rolling markout kill -- the "strategy is going horribly wrong" detector. Calibrated to
            # only fire on GENUINE sustained toxicity (avg 5s markout << the strategy's normal -1c),
            # not the normal maker adverse selection that 5s mid-reversion always shows. For a box
            # held to settlement this is a regime/venue alarm, not a per-trade stop.
            n_mk = a.markout_kill_n
            if len(markouts) >= n_mk and sum(markouts[-n_mk:]) / n_mk < a.markout_kill_bar:
                avg = sum(markouts[-n_mk:]) / n_mk
                print(f"KILL: rolling markout {avg:+.4f} < {a.markout_kill_bar} over {n_mk}. cancel-all + exit.")
                notify.alert(f"[kalshi] KILL markout toxic (avg {avg:+.4f} over {n_mk})")
                _record_kill(f"toxic_markout avg={avg:+.4f} n={n_mk}")
                cancel_all_resting(reason="toxic_kill"); break

            # --- book poll (REST; react-poll cadence) ---
            ybb, ybq, yba, yaq, _fresh = get_book_cached(mk["cid"])
            if _fresh:
                last_book_ok = time.time()
            if ybb is not None and yba is not None:
                if _fresh:
                    deadman_tripped = False
            else:
                time.sleep(a.react_poll); continue

            # CLAMP-LEAK FIX (audit H1): book EVERY known WS fill into net_delta BEFORE any placement
            # decision this loop. Previously fills were drained only on the ~1s housekeeping tick (after
            # placement), so two same-side orders could both fill against a stale net_delta -> |net|>=2
            # (12/56 windows pre-fix). Draining here makes the inventory clamp act on current inventory.
            drain_ws_fills()

            # --- compute desired levels (both YES and NO views) ---
            # Own-size exclusion (A2): subtract our resting size at the touch from the depth
            # so the microprice reflects other traders' imbalance only (mirrors live_trader's own_b/own_a).
            own_yes = sum(a.post for k in resting if k[0] == "yes" and abs(k[1] - ybb) < 1e-9)
            own_no  = sum(a.post for k in resting if k[0] == "no"  and abs(k[1] - round(1.0 - yba, 4)) < 1e-9)
            clean_ybq = max((ybq or 0.0) - own_yes, 0.0)
            clean_yaq = max((yaq or 0.0) - own_no,  0.0)
            mp = microprice(ybb, yba, clean_ybq, clean_yaq)

            targets = desired_levels(mk, ybb, yba, net_delta, 1, a.cap, a.skew, a.improve_tick)
            # t36 guarded opener (GUARDED_OPENER.md): the live loss mode is a YES leg opened into
            # a thin spread that strands (every realized live loss to date). When armed, suppress
            # YES quotes at spread < guard UNLESS net_delta < 0 (then a YES fill COMPLETES an
            # unpaired NO — pairing, not opening; the chase path is untouched either way).
            if (a.guard_yes_spread > 0 and ybb is not None and yba is not None
                    and (yba - ybb) < a.guard_yes_spread - 1e-9 and net_delta >= 0):
                targets = [t for t in targets if t[0] != "yes"]
            # STREAK GUARD (--strand-scaledown): after consecutive strands, scale down opens. At post=1
            # a multiplier that rounds to 0 SUPPRESSES new OPENING quotes this window (completion of an
            # unpaired leg is never suppressed -- that reduces |net|). Resets on a clean window.
            if _strand_sched and _consec_strands > 0:
                _m = _strand_sched[min(_consec_strands - 1, len(_strand_sched) - 1)]
                if round(a.post * _m) < 1:
                    targets = [t for t in targets
                               if (net_delta > 0.5 and t[0] == "no") or (net_delta < -0.5 and t[0] == "yes")]
            # EDGE-SELECT gate (the one positive-net signal: SELECTIVITY). Open ONLY in the fat-box
            # regime -- mid-window k-slots AND mid-vol; suppress OPENS (both sides) outside it, exempt
            # COMPLETIONS. High-vol/late-slot windows are where strands cluster and the box edge dies.
            if a.open_k_min > 0 or a.open_sig_hi > 0:
                cur_k = int((time.time() - mk["ws"]) / 60.0)
                _, _sig_now = _spot_sig(); _asig = abs(_sig_now or 0.0)
                in_k = (a.open_k_min <= cur_k <= a.open_k_max) if a.open_k_min > 0 else True
                in_vol = (a.open_sig_lo <= _asig <= a.open_sig_hi) if a.open_sig_hi > 0 else True
                if not (in_k and in_vol):
                    targets = [t for t in targets
                               if (net_delta > 0.5 and t[0] == "no") or (net_delta < -0.5 and t[0] == "yes")]
            target_set = set(targets)
            # stamp decision-time book state for fill-context logging (metrics framework:
            # effective spread = fill price vs this mid; depth/imbalance for queue + toxicity)
            _spot_px, _spot_sig_bps = _spot_sig()    # decision-time spot + 3-min move (bps) for sig telemetry
            loop_ctx.update({"mid": round((ybb + yba) / 2, 4), "bb": ybb, "ba": yba,
                             "bq": round(clean_ybq, 2), "aq": round(clean_yaq, 2),
                             "micro": round(mp, 4) if mp is not None else None,
                             "spread": round(yba - ybb, 4),
                             "spot": _spot_px, "sig": _spot_sig_bps})

            # --- PLACE missing rungs ---
            spread_now = (yba - ybb) if (ybb is not None and yba is not None) else 0.0
            tau_left = max(mk["we"] - time.time(), 0.0)
            # completion-urgency clock: when did the current unpaired position open?
            if abs(net_delta) > 1e-9:
                if unpaired_since is None:
                    unpaired_since = time.time()
            else:
                unpaired_since = None
            for side, price in targets:
                key = (side, round(price, 4))
                if key in resting:
                    continue
                if reject_cd.get(key, 0.0) > time.time():
                    continue              # reject churn breaker: this exact price just bounced
                if time.time() < side_cooldown[side]:
                    continue              # tweak 1: post-fill cooldown (don't re-quote into the trend)
                # is this quote COMPLETING a box (reducing |net|)? completing only ever cuts
                # directional risk, so it is exempt from the open-only late-window guards.
                is_completing = ((net_delta > 1e-9 and side == "no") or
                                 (net_delta < -1e-9 and side == "yes"))
                if win_fills.get(side, 0) >= a.max_fills_side and not is_completing:
                    continue              # tweak 4 (post-mortem): trends outlast the cooldown -- the
                                          # 5th+ same-side fill in a window is where the edge dies
                                          # (completing legs exempt: they shed risk, never add it)
                if spread_now < a.min_spread - 1e-9:
                    continue              # tweak 2 REVISED: 1c-spread fills are zero-EV UNPAIRED,
                                          # but under --max-net pairing a 1c book locks 1c/pair
                                          # risk-free -> default lowered 0.02 -> 0.01 (tape floor
                                          # table: all-spreads +1.74c/win t=2.1 vs >=2c-only -0.13c)
                if tau_left < a.tau_guard and not is_completing:
                    continue              # tweak 3: late-window OPENING is adverse -- but a COMPLETING
                                          # leg must keep quoting (the tau-guard blocking it WAS the
                                          # directional-loss bug: unpaired legs rode to settlement)
                # Toxicity gate: skip placing if microprice says this side is adverse
                if mp is not None and gate_check(side, price, ybb, yba, net_delta, a.gate, 0.0, clean_ybq, clean_yaq):
                    continue
                # HARD DIRECTIONAL INVENTORY CLAMP -> BOX-PAIRING DISCIPLINE. A net position of N
                # binary contracts risks up to $N held; but the deeper finding (box decomposition,
                # live + 20k tape fills) is that PAIRED yes/no fills are the entire profit engine
                # (risk-free locked spread at settlement) while unpaired inventory is a consistent
                # loser. --max-net 1 turns the clamp into strict pairing: one side fills, only the
                # completing side keeps quoting. Constant, never linked to the dollar budget.
                inv_cap = float(a.max_net)
                # WORST-CASE projection: count RESTING same-side orders too, not just filled net.
                # Bug fix (live -$1.05 window): two NO rungs both resting at net=0 each passed the
                # old filled-only clamp, then both filled ~1s apart -> net -2 (double --max-net). Bound
                # the worst case where every resting same-side order AND this one fills.
                sgn = 1.0 if side == "yes" else -1.0
                rest_same = sum(max(a.post - m.get("filled", 0.0), 0.0)
                                for (s_, _p), m in resting.items() if s_ == side)
                # + cancel-sent-but-unconfirmed orders: still live at the venue until proven otherwise
                rest_same += sum(max(a.post - m.get("filled", 0.0), 0.0)
                                 for (s_, _p), m in pending_cancel.items() if s_ == side)
                proj = net_delta + sgn * (rest_same + a.post)
                if abs(proj) > inv_cap + 1e-9:
                    continue
                # BOX COMPLETION FLOOR: this quote pairs against existing inventory -> require the
                # pair to LOCK >= eff_lock vs the unpaired leg's average cost. Early in the window
                # eff_lock = --min-lock (hold out for a positive lock; don't buy a guaranteed loss).
                # Near close it RAMPS negative to -close_max_give: a bounded certain loss beats
                # riding an adversely-filled unpaired leg into settlement (the live -66c/-31c tail).
                eff_lock = a.min_lock
                if is_completing and tau_left < a.close_flatten_tau:
                    frac = 1.0 - max(tau_left, 0.0) / a.close_flatten_tau   # 0 -> 1 as tau -> 0
                    eff_lock = a.min_lock - (a.min_lock + a.close_max_give) * frac
                # COMPLETION URGENCY (chase): the close ramp generalized to UNPAIRED AGE. A leg
                # unpaired > --chase-unpaired-s relaxes the floor toward -chase_max_give (ramp over
                # a second interval of the same length); take the more permissive of the two ramps.
                # Mid-window give is capped tighter (2c) than the close ramp (4c): early on there is
                # still time for a natural completion, so we pay less for urgency.
                if (is_completing and a.chase_unpaired_s > 0 and unpaired_since is not None):
                    age_unp = time.time() - unpaired_since
                    if age_unp >= a.chase_unpaired_s:
                        u = min(1.0, age_unp / a.chase_unpaired_s - 1.0)    # 0 -> 1 over the 2nd interval
                        eff_lock = min(eff_lock,
                                       a.min_lock - (a.min_lock + a.chase_max_give) * u)
                if net_delta > 1e-9 and side == "no":
                    py_ = sum(v for k_, v in pos.items() if k_.endswith(":YES"))
                    basis = win_cost["yes"] / py_ if py_ > 0 else 0.0
                    if basis > 0 and price > 1.0 - basis - eff_lock + 1e-9:
                        continue
                elif net_delta < -1e-9 and side == "yes":
                    pn_ = sum(v for k_, v in pos.items() if k_.endswith(":NO"))
                    basis = win_cost["no"] / pn_ if pn_ > 0 else 0.0
                    if basis > 0 and price > 1.0 - basis - eff_lock + 1e-9:
                        continue
                # C8 aggregate notional cap (BUY side only; both YES and NO are buys)
                open_buy_notional = sum(max(a.post - m.get("filled", 0.0), 0.0) * price_
                                        for (_, price_), m in resting.items())
                exposure = open_buy_notional + max(-cash, 0.0)
                if exposure + price * a.post > a.max_notional:
                    continue
                # Side ladder rung cap
                if sum(1 for k in resting if k[0] == side) >= a.max_rungs:
                    continue
                units = 1
                if a.size_mode == "kelly":
                    # gate_check already refused toxic fills; here Kelly UP-SIZES strong-edge fills to
                    # KELLY_MAX while keeping a 1-contract base so the live run actually gathers fill
                    # data on the tight book (the ultra-selective 0-floor never fires at 1c spreads).
                    tau_frac = max(mk["we"] - time.time(), 0.0) / 900.0
                    units = max(1, kelly_size(price if side == "yes" else 1.0 - price,
                                              yba - ybb, tau_frac, fee_mult=a.fee_mult))
                # AUDIT M1: the inventory clamp above reserved only `post`; cap units so units*post can
                # NOT breach --max-net in a single fill (else size-mode kelly silently overshoots |net|).
                _sgn = 1.0 if side == "yes" else -1.0
                while units > 1 and abs(net_delta + _sgn * units * int(a.post)) > float(a.max_net) + 1e-9:
                    units -= 1
                want = units * int(a.post)
                res = place(side, price, ybb, yba, count=want)
                if res is None:
                    continue
                if isinstance(res, tuple):
                    oid, t_dec, t_ack = res
                else:
                    oid = res; t_ack = time.time()
                resting[key] = {"oid": oid, "ts": t_ack, "filled": 0.0, "want": want,
                                "mid0": loop_ctx.get("mid")}

            # --- STRAND DISPOSAL: cross to COMPLETE an unpaired leg the passive chase can't pair ---
            # The passive completion quote rests at the bid (post_only) and never reaches the offer,
            # so in a moving market the leg rides naked to settlement (-21.76c live, RCA 2026-06-13).
            # When --dispose-cross is armed and the leg is aged (>--chase-unpaired-s) OR near close
            # (<--close-flatten-tau), TAKE the offer to lock the box, bounded by the give budget.
            if (a.dispose_cross and abs(net_delta) > 1e-9 and unpaired_since is not None
                    and ybb is not None and yba is not None):
                age_unp = time.time() - unpaired_since
                near_close = tau_left < a.close_flatten_tau
                aged = a.dispose_cross_s > 0 and age_unp >= a.dispose_cross_s
                force = tau_left < a.close_force_s   # FINAL seconds: flatten at ANY cost (escaped-strand fix)
                if aged or near_close or force:
                    give = a.close_max_give if near_close else a.chase_max_give
                    if net_delta > 1e-9:            # hold YES -> COMPLETE by BUY-NO, take the no-offer
                        cside = "no"; cross_px = round(1.0 - ybb, 4)
                        py_ = sum(v for k_, v in pos.items() if k_.endswith(":YES"))
                        basis = win_cost["yes"] / py_ if py_ > 0 else 0.0
                    else:                            # hold NO -> COMPLETE by BUY-YES, take the yes-offer
                        cside = "yes"; cross_px = round(yba, 4)
                        pn_ = sum(v for k_, v in pos.items() if k_.endswith(":NO"))
                        basis = win_cost["no"] / pn_ if pn_ > 0 else 0.0
                    lock = 1.0 - basis - cross_px    # $ locked completing the box at the cross price
                    need = int(round(abs(net_delta)))
                    # AUDIT C3: size the cross to AVAILABLE offer depth (BUY-NO takes the YES-bid qty;
                    # BUY-YES takes the YES-ask qty). A multi-lot strand on a thin offer would otherwise
                    # partial-fill and strand the residual. Re-cross the remainder next loop (short
                    # throttle when forcing) until net is flat.
                    avail = (ybq if cside == "no" else yaq) or need
                    take = max(1, min(need, int(avail)))
                    ckey = (cside, "_xcross")
                    # FORCE near close ignores the give budget: a certain -Xc completion now ALWAYS beats
                    # riding the naked leg to binary settlement (the -39.8c escaped-strand tail, run 2).
                    if (0.0 < cross_px < 1.0 and need >= 1 and (force or lock >= -give - 1e-9)
                            and reject_cd.get(ckey, 0.0) <= time.time()):
                        if place(cside, cross_px, ybb, yba, count=take, cross=True) is not None:
                            ops["dispose_cross"] = ops.get("dispose_cross", 0) + 1
                            winrec["dispose_cross"] += 1
                            if force:
                                print(f"  [FORCE-FLATTEN] {take}/{need}x {cside.upper()} @ {cross_px:.4f} "
                                      f"lock={lock:+.3f} tau={tau_left:.0f}s (no-give-cap; beats settlement)")
                            print(f"  [DISPOSE-CROSS] complete {take}/{need}x {cside.upper()} @ {cross_px:.4f} "
                                  f"lock={lock:+.3f} (age={age_unp:.0f}s tau={tau_left:.0f}s)")
                        # short throttle while forcing/partial so the residual re-crosses promptly
                        reject_cd[ckey] = time.time() + (0.8 if (force or take < need) else 3.0)

            # --- PULL stale / toxic / off-target rungs ---
            for key in list(resting):
                side, price = key
                # Toxicity gate: pull if microprice crossed this rung (same ufat logic as live_trader)
                if mp is not None and gate_check(side, price, ybb, yba, net_delta, a.gate, 0.0, clean_ybq, clean_yaq):
                    drop(key, "toxic")
                    continue
                # Reshape: off-target young rungs (equiv to live_trader's young off-band cancel)
                if key not in target_set:
                    age = time.time() - resting[key]["ts"]
                    # QUEUE-TIMING EXPERIMENT (--qtime-mp-margin, default OFF; FINGERPRINT.md): the
                    # dominant ladder-MM reprices on a ~1.2s mechanical heartbeat (74% of its quotes
                    # stale 3s after a spot move). When MICROPRICE diverges from mid the touch is
                    # about to move -- reshaping NOW (bypassing the 2s churn guard) lands us at the
                    # new level AHEAD of the MM's next heartbeat = front-of-queue at the right price.
                    # Hypothesis under live A/B (flag on vs off); the 2s guard otherwise makes us
                    # SLOWER than the MM and we forfeit the priority.
                    fast = False
                    if a.qtime_mp_margin > 0 and mp is not None:
                        mid_n = loop_ctx.get("mid")
                        if mid_n is not None and abs(mp - mid_n) >= a.qtime_mp_margin:
                            fast = True
                            qtime_ct[0] += 1
                    if age >= 2.0 or fast:
                        drop(key, "reshape_qtime" if fast else "reshape")
                        continue
                # STALE-QUOTE REFRESH (markout forensics 2026-06-12): a quote resting >N s through a
                # >=1-tick mid move is the one that gets picked off (-2.04c/fill vs +0.79c fresh).
                # The queue position we give up was at a stale price -- anti-value, not value.
                if a.requote_stale_s > 0:
                    meta = resting[key]
                    age = time.time() - meta["ts"]
                    m0 = meta.get("mid0")
                    mid_now = loop_ctx.get("mid")
                    if (age > a.requote_stale_s and m0 is not None and mid_now is not None
                            and abs(mid_now - m0) >= 0.01 - 1e-9):
                        drop(key, "stale_refresh")

            # Rung cap: evict rungs farthest from touch if over max_rungs
            for side, touch in (("yes", ybb), ("no", round(1.0 - yba, 4))):
                ks = [k for k in resting if k[0] == side]
                if len(ks) > a.max_rungs:
                    ks.sort(key=lambda k: abs(k[1] - touch))
                    for k in ks[a.max_rungs:]:
                        drop(k, "rung_cap")

            # pending-cancel hygiene: retry stale unconfirmed cancels; purge after 60s (the
            # order TTL guarantees venue-side death; purging un-blocks the clamp slot)
            now_pc = time.time()
            for k_pc, m_pc in list(pending_cancel.items()):
                age_pc = now_pc - m_pc.get("cq_ts", now_pc)
                if age_pc > 60.0:
                    pending_cancel.pop(k_pc, None)
                elif age_pc > 10.0 and not m_pc.get("retried"):
                    m_pc["retried"] = True
                    cancel_q.append((m_pc["oid"], k_pc, "pending_retry"))
            flush_cancels()   # ONE pass for all queued cancels this tick

            # ----------------------------------------------------------------
            # HOUSEKEEPING (--poll cadence): fills, markouts, reconciliation, settles
            # ----------------------------------------------------------------
            if hk:
                if live:
                    drain_ws_fills()   # real-time WS fills first (deduped by seen_fills)
                    poll_fills()       # REST backstop (slower cadence, catches any WS misses)
                    poll_balance_lm()
                    # CONTROL L2 (cross-host double-trader guard): an open order on OUR ticker that
                    # WE did not place means another trader is live on this account (GHA + local,
                    # orphan loop, anything). Fail CLOSED: alert + flatten + exit; operator re-arms
                    # exactly one. (A lost place-ack can false-positive -- rare, and the safe side.)
                    try:
                        if mk is not None and time.time() - _foreign_chk[0] > 30:
                            _foreign_chk[0] = time.time()
                            for _o in get_open_orders(sess, priv, mk["cid"]):
                                _oid = str(_o.get("order_id") or "")
                                if _oid and _oid not in placed_oids:
                                    notify.alert_sync(
                                        f"\U0001f6a8 FOREIGN ORDER on {mk['cid']}: {_oid[:16]} not "
                                        f"placed by this trader -- ANOTHER TRADER IS LIVE on this "
                                        f"account. Halting this instance (fail-closed); ensure "
                                        f"exactly one trader then re-arm.")
                                    _flatten_and_exit("foreign order: second trader detected")
                                    os._exit(0)
                    except SystemExit:
                        raise
                    except Exception:
                        pass

                # Score due markouts (5s/30s/60s/300s curve; 5s also feeds the rolling kill)
                now_mo = time.time()
                due = [pm for pm in pending_markouts if pm[0] <= now_mo]
                pending_markouts[:] = [pm for pm in pending_markouts if pm[0] > now_mo]
                for due_t, f in due:
                    fcid = f.get("cid")
                    if mk is not None and fcid in (None, mk["cid"]):
                        # same (open) window: score against the current book
                        try:
                            ybb2, _, yba2, _, _fresh2 = get_book_cached(mk["cid"], max_age=0.1)
                        except Exception:
                            pending_markouts.extend([(due_t, f)])
                            break
                        if ybb2 is None or yba2 is None or now_mo - due_t > 60:
                            continue
                        mid2 = (ybb2 + yba2) / 2.0
                        mo = (mid2 - f["fp"]) if f["fside"] == "yes" else ((1.0 - mid2) - f["fp"])
                    else:
                        # AUDIT H3: the fill's window CLOSED -- don't silently drop (that starved the 5s
                        # rolling-kill denominator at the rollover boundary and lost all long horizons).
                        # Score against the SETTLEMENT outcome = the leg's TRUE realized markout.
                        rr = _settle_cache.get(fcid, "?")
                        if rr == "?":
                            rr = resolve_result(sess, fcid) if fcid else None
                            if rr in ("yes", "no"):
                                _settle_cache[fcid] = rr
                        if rr not in ("yes", "no"):
                            if now_mo - due_t < 120:        # settlement lags ~20s; re-queue briefly
                                pending_markouts.append((due_t, f))
                            continue
                        mo = (1.0 if rr == f["fside"] else 0.0) - f["fp"]
                    if f.get("h", 5.0) == 5.0:
                        markouts.append(mo); del markouts[:-500]   # rolling kill stays 5s-keyed
                    mo_fh.write(json.dumps({
                        "ts": time.time(), "asset": a.asset, "side": f["fside"],
                        "h": f.get("h", 5.0), "price": f["fp"], "count": f["count"],
                        "markout": mo, "resting_s": f.get("resting_s"),
                        "net_delta": net_delta,
                        # decision-time context (Prevention #0): sig/microprice/guard + spread/mid
                        "sig": f.get("sig"), "spot": f.get("spot"), "micro": f.get("micro"),
                        "spread": f.get("spread"), "mid": f.get("mid"), "guard": f.get("guard")}) + "\n")
                    mo_fh.flush()

                # Venue ORDER RECONCILIATION (C6): cancel unknown open orders every 5s
                if live and time.time() - last_reconcile >= 5.0:
                    last_reconcile = time.time()
                    try:
                        oo = get_open_orders(sess, priv, mk["cid"])
                        known = {str(m_["oid"]) for m_ in resting.values()}
                        strays = [str(o.get("order_id")) for o in oo
                                  if str(o.get("order_id")) not in known
                                  and str(o.get("order_id")) != "None"]
                        if strays:
                            print(f"  [RECONCILE] cancelling {len(strays)} unknown order(s)")
                            for s_oid in strays:
                                cancel_order(sess, priv, s_oid)
                            lm.stray_cancelled(len(strays))
                    except Exception as e:
                        print(f"  [RECONCILE-FAIL] {type(e).__name__} {str(e)[:80]}")

                # Pending settles: sweep late fills + attempt resolution (>=20s grace as live_trader)
                still = []
                for en in pending_settles:
                    if live:
                        sweep_window_fills(en["cid"], en)
                    r2 = en.get("r")
                    if r2 is None:
                        r2 = resolve_result(sess, en["cid"])
                        en["r"] = r2
                    if r2 == "void" and time.time() - en.get("t0", 0) >= 20:
                        # voided/cancelled market: cash comes back, no P&L
                        realized += 0
                        print(f"  [VOID] ws={en['ws']} market voided; cash returned, no P&L")
                        seen_fills.pop(en["cid"], None)
                    elif r2 is not None and time.time() - en.get("t0", 0) >= 20:
                        # settle: YES pays $1 if r2==1, NO pays $1 if r2==0
                        pnl = (en["cash"]
                               + en["pos_yes"] * (1.0 if r2 == 1 else 0.0)
                               + en["pos_no"]  * (1.0 if r2 == 0 else 0.0))
                        realized += pnl
                        print(f"  [SETTLE] ws={en['ws']} r={r2} pnl={pnl:+.4f} realized={realized:+.2f}")
                        # DURABLE PER-WINDOW AUDIT RECORD (clean failure-audit + backtest dataset).
                        # Captures the settled RESULT (so it's never re-fetched / lost after markets
                        # age out) + the box/unpaired decomposition. Join to kalshi_fees_*.jsonl on
                        # ticker for the per-fill prices/features. One line per settled window, append-only.
                        try:
                            _py, _pn = en["pos_yes"], en["pos_no"]
                            _bx = min(_py, _pn); _unp = abs(_py - _pn)
                            with open(f"window_audit_{a.asset}15m.jsonl", "a") as _wa:
                                _wa.write(json.dumps({
                                    "ts": time.time(), "ws": en["ws"], "ticker": en["cid"],
                                    "asset": a.asset, "result": r2, "pos_yes": _py, "pos_no": _pn,
                                    "cash": round(en["cash"], 4), "pnl": round(pnl, 4),
                                    "paired": _bx, "unpaired": _unp,
                                    "unpaired_side": ("yes" if _py > _pn else "no" if _pn > _py else None),
                                }) + "\n")
                        except Exception:
                            pass
                        # phone notification of net win/loss at settlement (Telegram via notify)
                        if abs(pnl) > 1e-9:
                            _wt = datetime.utcfromtimestamp(en["ws"]).strftime("%H:%MZ")
                            notify.alert(f"[kalshi {a.asset}] {_wt} settled {'WIN' if pnl>0 else 'LOSS'} "
                                         f"{pnl:+.2f}  (session {realized:+.2f})")
                        seen_fills.pop(en["cid"], None)
                    else:
                        still.append(en)
                pending_settles[:] = still

                # Mark open window to mid (feeds loss-limit kill)
                wm = cash
                ybb_m, _, yba_m, _, _fresh_m = get_book_cached(mk["cid"])
                mid_m = (ybb_m + yba_m) / 2.0 if (ybb_m is not None and yba_m is not None) else 0.5
                for pk, sh in pos.items():
                    if abs(sh) < 1e-9:
                        continue
                    if pk.endswith(":YES"):
                        wm += sh * mid_m
                    else:
                        wm += sh * (1.0 - mid_m)
                window_mark = wm + sum(
                    en["cash"]
                    + (en["pos_yes"] * (1.0 if en["r"] == 1 else 0.0)
                       + en["pos_no"]  * (1.0 if en["r"] == 0 else 0.0)
                       if en.get("r") is not None
                       else 0.5 * (en["pos_yes"] + en["pos_no"]))
                    for en in pending_settles
                )
                last_hk = time.time()

            consec_err = 0
            flush_cancels()   # defensive flush at end of clean pass
            # EVENT-DRIVEN reaction: wake instantly when the WS feeder applies a book delta
            # (reaction latency ~= processing time, not poll-cadence/2). --react-poll is now
            # only the idle heartbeat ceiling (mirrors live_trader event-driven pattern).
            book_evt.wait(a.react_poll)
            book_evt.clear()

        except KeyboardInterrupt:
            _flatten_and_exit("KeyboardInterrupt")
            print("interrupted; cancelled all.")
            break
        except Exception as e:
            consec_err += 1; total_err += 1
            print(f"[warn] {str(e)[:100]} (consec_err={consec_err} total={total_err})")
            # AUDIT M3: surface the FIRST error of a burst -- intermittent exceptions on inventory/
            # disposal paths were silently [warn]'d and never tripped the 5-CONSECUTIVE dead-man.
            if consec_err == 1:
                try: notify.alert(f"[kalshi] loop error: {str(e)[:140]}")
                except Exception: pass
            # error storm (5 consecutive OR 40 cumulative) -> state untrustworthy -> LIQUIDATE + exit
            # (per audit C2: was cancel-only; the chain restarts cleanly next cron).
            if live and (consec_err >= 5 or total_err >= 40) and not deadman_tripped:
                print("[DEAD-MAN] error storm -> liquidate + exit (state untrustworthy)")
                notify.alert(f"[kalshi] DEAD-MAN error storm (consec={consec_err} total={total_err}): liquidate+exit")
                deadman_tripped = True
                _flatten_and_exit("error_storm"); break
            time.sleep(a.poll)

    # PLANNED end-of-session: same cancel-all guarantee, but alerted as a normal completion --
    # the generic "DEAD-MAN" wording here read like a crash to the operator (it is not one).
    _flatten_and_exit(f"live session complete (planned, duration reached) — realized "
                      f"{realized:+.2f}; next session starts on schedule, or text 'on'")
    print(f"done. realized={realized:+.2f} net_delta={net_delta:+.1f} "
          + (f"avg_markout={sum(markouts)/len(markouts):+.5f}" if markouts else "no markouts"))


if __name__ == "__main__":
    main()
