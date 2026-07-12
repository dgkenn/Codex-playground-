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
import math
import os
import signal
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

import requests

import notify          # Telegram alerts (no-op if env unset)
from fvfeed import SpotFair   # opt-in --seed-empty: spot-implied fair for empty-book seeding
from live_metrics import LiveMetrics

BASE = "https://api.elections.kalshi.com/trade-api/v2"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
MICRO_MARGIN = 0.002   # p-adaptive toxicity margin (same constant as live_trader)
# --- 32-day forward shadow A/B winners (opt-in via --gate as / --size-mode markout; defaults
# unchanged). Constants copied verbatim from shadow_compare.py so the live path matches exactly
# what was validated. AS_WINDOW_S: this module only trades KX{asset}15M (900s windows; see
# discover()'s `ws = int(ct) - 900`), so it is a constant here (shadow_compare derives it from
# --tenor-min for multi-tenor runs).
AS_K = 4e-4             # gate=="as": penalty = AS_K * |net_delta| * (tau/AS_WINDOW_S) (GATING.md)
AS_WINDOW_S = 900.0     # KX*15M window length (s); tau-to-close normalizer for the "as" gate
MO_K = 150.0            # size-mode=="markout": size *= clamp(1 + MO_K*fav, 0, 2) (MAKEREDGE.md #3)

# --- PORTFOLIO-AWARE SIZING (opt-in via --portfolio-aware; default OFF -> zero behavior change).
# From the 4-asset expansion on, each asset leg runs on its OWN GitHub Actions runner with NO
# shared local state -- the Kalshi ACCOUNT itself, reachable only via the EXISTING authenticated
# read-only calls (get_balance/get_positions, the same two startup reconciliation already uses;
# no new endpoints), is the only place that knows the whole book. The two multipliers below are
# deliberately MECHANICAL (clamp()'d linear ramps off venue-reported numbers) -- NOT a fitted
# model. This repo's one fitted sizing/gate model (the ridge-ensemble "micro_cal" gate, fit by
# gate_lab.py) failed its forward test (see GATING.md / PER_MARKET_STRATEGY.md's "pruned" row),
# so anything touching live sizing off cross-asset state stays intentionally dumb and auditable.
PORT_TICKER_PREFIX = "KX"     # crypto 15M series tickers look like "KX{ASSET}15M-..." (discover())
PORT_TICKER_INFIX = "15M"     # excludes non-crypto KX* series (e.g. weather/elections) from delta

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


def parse_book_entry(ob_json):
    """Parse a raw Kalshi GET /markets/{ticker}/orderbook JSON response (the same endpoint/shape
    get_book() reads) into a ws_entry-shaped dict {"yes": {price: qty}, "no": {price: qty}} --
    i.e. the SAME shape _apply_snapshot builds from a WS orderbook_snapshot -- so a REST orderbook
    can be classified by seed_book_state()/seed_fair_band_state() identically to a WS one
    (single-sourced classification; see --seed-empty's REST-fallback path in _seed_tick, triggered
    when the WS book never materializes for a genuinely empty book -- Kalshi's WS sends NO
    orderbook_snapshot at all for an empty book, confirmed live 2026-07-12 run r29179923486).
    Unlike get_book() (which only extracts the best level and collapses a ONE-SIDED book to the
    same all-None result as a fully empty one -- fine for "stand down" but not for --seed-empty's
    finer classification), this keeps every level, which is exactly the detail seed_book_state
    needs. Returns None if the response carries no orderbook payload at all (distinct from a
    genuinely EMPTY orderbook, which parses fine and just yields two empty dicts)."""
    o = ob_json.get("orderbook_fp") or ob_json.get("orderbook") or {}
    if not o:
        return None

    def _side(levels):
        book = {}
        for entry in (levels or []):
            try:
                p, q = float(entry[0]), float(entry[1])
                if q > 0:
                    book[p] = q
            except Exception:
                pass
        return book

    return {"yes": _side(o.get("yes_dollars")), "no": _side(o.get("no_dollars"))}


def get_book_raw(sess, ticker):
    """Full-depth REST orderbook fetch for the --seed-empty WS-unknown REST fallback -- hits the
    SAME endpoint via the SAME session as get_book() (no new HTTP client), just doesn't collapse
    one-sided/empty books to best-level-only like get_book() does. Returns a ws_entry-shaped dict
    (see parse_book_entry) or None on any HTTP/parse failure -- callers must treat None as 'no
    information', never as evidence of emptiness (a transient REST failure must not churn seeded
    quotes)."""
    try:
        ob = sess.get(f"{BASE}/markets/{ticker}/orderbook", timeout=4).json()
    except Exception:
        return None
    return parse_book_entry(ob)


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

def top5_both_depth(ws_state, ticker, n=5):
    """min(top-5 YES-bid total, top-5 YES-ask total) from the WS book -- the 'both-sides depth' the
    pair-gate study found is the dominant strand predictor (deep balanced book => both legs pair).
    YES-ask side = the NO bids. Returns None if the WS book isn't populated (=> pair-gate blocks)."""
    st = ws_state.get(ticker)
    if not st:
        return None
    yb = st.get("yes") or {}; nb = st.get("no") or {}
    if not yb or not nb:
        return None
    syes = sum(q for _, q in sorted(yb.items(), reverse=True)[:n])
    sno = sum(q for _, q in sorted(nb.items(), reverse=True)[:n])
    return min(syes, sno)


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


def get_positions(sess, private_key):
    """GET /portfolio/positions. Returns list of market-position dicts (may be empty on error).
    DEADMAN_AUDIT.md fix #2: this endpoint was never called anywhere in this file before, so a
    restarted process had no way to learn about pre-existing venue inventory at startup."""
    sc, resp = _api(sess, private_key, "GET", "/portfolio/positions", timeout=6)
    if sc < 200 or sc >= 300 or resp is None:
        return []
    return resp.get("market_positions") or resp.get("positions") or []


def _parse_inherited_position(mpos_list, ticker):
    """Extract an inherited (side, count, cost_dollars) dict for `ticker` from a
    GET /portfolio/positions response's market_positions list, or None if flat/absent.

    Sign convention matches net_delta elsewhere in this file (line ~970: "YES positions - NO
    positions, signed"): Kalshi's own `position` field is positive when long YES, negative when
    long NO. `market_exposure` (cents, the position's cost basis) seeds a best-effort win_cost so
    the C2 loss-limit's worst-open calc (kalshi_trader.py ~1584-1591, itself keyed off
    win_cost[side]/count) isn't blind to inherited inventory. A missing/odd market_exposure just
    leaves cost=0.0 -- that UNDER-estimates worst_open, never over-estimates, so a parse gap can
    only make the loss-limit slower to fire on inherited inventory, never falsely trip it.

    Defensive/never-raises: any malformed row is skipped rather than aborting the whole scan
    (startup must safe-default to pre-fix flat-assumed behavior on any parse trouble, not crash)."""
    for p in (mpos_list or []):
        try:
            if str(p.get("ticker") or "") != ticker:
                continue
            net = p.get("position")
            if net is None:
                continue
            net = float(net)
            if abs(net) < 1e-9:
                continue
            side = "yes" if net > 0 else "no"
            count = abs(net)
            cost_c = p.get("market_exposure")
            cost = round(float(cost_c) / 100.0, 4) if cost_c is not None else 0.0
            return {"side": side, "count": count, "cost": cost}
        except Exception:
            continue
    return None


def portfolio_mult_budget(committed, port_budget):
    """BUDGET multiplier (PORTFOLIO-AWARE SIZING, opt-in --portfolio-aware): shrinks smoothly
    toward 0 as the WHOLE account's open-position notional (`committed`, $, across EVERY market
    on the account -- not just this asset) fills the opt-in --port-budget envelope, BEFORE any
    hard --max-notional/--max-net cap has to bind. clamp to [0,1]; port_budget<=0 is a
    misconfiguration, not a divide-by-zero -- treated as "no budget left" (fail CLOSED on bad
    config, unlike the API-unavailability fail-safe below which fails OPEN)."""
    if port_budget <= 0:
        return 0.0
    return min(max((port_budget - committed) / port_budget, 0.0), 1.0)


def portfolio_mult_delta(agg_delta_before, side, want, port_delta_max):
    """DELTA-CONCENTRATION multiplier (PORTFOLIO-AWARE SIZING, opt-in --portfolio-aware).
    `agg_delta_before` is the signed aggregate crypto delta across ALL KX*15M positions on the
    account BEFORE this candidate fill: YES contracts count +1 toward 'up', NO contracts -1,
    summed across every asset (same signed-contract convention this module's own `net_delta`
    already uses for a single asset -- see net_delta's own docstring comment).

    A fill that would REDUCE |aggregate delta| is a de-risking trade for the WHOLE portfolio and
    is ALWAYS full size (mirrors gate_check's gate=="as" branch: "reducing |net_delta| is never
    gated" -- de-risking is always welcome). A fill that INCREASES |aggregate delta| stays full
    size until the result crosses --port-delta-max, then ramps 0.5 -> 0.0 linearly as the result
    runs up to 1.5x the limit. This is a smooth DE-RATE, not a hard stop -- the hard stop remains
    --max-net, re-applied unchanged after this multiplier composes (never bypassed)."""
    if want <= 0:
        return 1.0
    sgn = 1.0 if side == "yes" else -1.0
    agg_after = agg_delta_before + sgn * want
    if abs(agg_after) <= abs(agg_delta_before) + 1e-9:
        return 1.0                  # reduces (or doesn't increase) |delta| -> always full size
    absd = abs(agg_after)
    lo = float(port_delta_max)
    hi = 1.5 * lo
    if absd < lo:
        return 1.0                   # increasing, but still comfortably under the limit
    if hi <= lo or absd >= hi:
        return 0.0                   # at/beyond 1.5x the limit -> fully de-rated
    frac = (absd - lo) / (hi - lo)      # 0 at lo -> 1 at hi
    return max(0.0, 0.5 * (1.0 - frac))  # 0.5 AT the limit -> 0.0 at 1.5x the limit


def refresh_portfolio_state(sess, priv, asset, get_balance_fn=get_balance,
                            get_positions_fn=get_positions):
    """One refresh cycle of PortfolioState (PORTFOLIO-AWARE SIZING, opt-in --portfolio-aware):
    pulls balance + ALL-market positions via the EXISTING authenticated read-only calls (the same
    two startup reconciliation already uses -- no new endpoints) and reduces them to exactly the
    two numbers portfolio_mult_{budget,delta} need:
      committed        = sum(|market_exposure|) in dollars, across EVERY position on the account
                          (the whole shared venue book, not just this asset).
      agg_delta_other  = signed aggregate delta (YES=+1/contract, NO=-1) across all OTHER assets'
                          KX*15M positions. THIS asset's own family is deliberately excluded here
                          -- the caller already tracks its own net_delta live, fill-by-fill, far
                          more current than any --port-refresh-s poll cadence could be, and adds
                          that back on top of this before sizing (see main()'s _port_multipliers).

    Raises on ANY failure (bad/empty response, exception) rather than swallowing it -- swallowing
    is the CALLER's job (main()'s periodic refresh leaves the previous PortfolioState in place on
    any exception here; staleness then does the fail-safe work). A single malformed position row
    is skipped, not fatal -- one bad row must not blind the whole refresh."""
    bal = get_balance_fn(sess, priv)
    mpos = get_positions_fn(sess, priv)
    if bal is None or mpos is None:
        raise RuntimeError("get_balance/get_positions returned None (auth/network failure)")
    committed = 0.0
    agg_all = 0.0
    agg_this = 0.0
    this_prefix = f"KX{asset.upper()}15M"
    for p in mpos:
        try:
            exp_c = p.get("market_exposure")
            if exp_c is not None:
                committed += abs(float(exp_c)) / 100.0
            tkr = str(p.get("ticker") or "")
            if tkr.startswith(PORT_TICKER_PREFIX) and PORT_TICKER_INFIX in tkr:
                net = float(p.get("position") or 0.0)
                agg_all += net
                if tkr.startswith(this_prefix):
                    agg_this += net
        except Exception:
            continue   # one malformed row must not poison the whole refresh
    return {"committed": committed, "agg_delta_other": agg_all - agg_this, "ts": time.time()}


def remote_switch_kill(gh_token, remote_switch_url, reason, sess=None, retries=3,
                       backoff_s=1.5, alert_fn=None):
    """Durable sticky-kill (DEADMAN_AUDIT.md fix #1). Previously the loss-limit/toxic-markout
    trip only became permanent if a LATER workflow step, running on the SAME runner after this
    process exits, committed LIVE_SWITCH=off -- a runner hard-killed in between silently
    discarded the kill and the next cron tick resumed trading unaware anything happened. This
    does the durable part synchronously, the instant the kill fires, via the GitHub contents API
    (a PUT needs the file's current sha, fetched via a GET on the same url first). Reuses the
    exact url/repo/path/ref the process already has via REMOTE_SWITCH_URL + GH_TOKEN -- no new
    config surface.

    Clean no-op (returns False immediately, no network call) when gh_token or remote_switch_url
    is absent, e.g. local/dry runs. On total failure after `retries` attempts, falls back to the
    pre-existing sentinel+workflow-step path (caller already writes the local sentinel) and fires
    a Telegram alert flagging that the kill may not be durable.

    `sess`/`alert_fn` are injectable for testability; default to the `requests` module itself
    (matching _remote_switch_is_off's use of bare `requests.get`, not a Session) and
    notify.alert_sync respectively."""
    sess = sess or requests
    alert_fn = alert_fn or notify.alert_sync
    if not (gh_token and remote_switch_url and "api.github.com" in remote_switch_url):
        return False   # no-op: local/dry runs, or remote switch not configured
    parsed = urllib.parse.urlsplit(remote_switch_url)
    branch = (urllib.parse.parse_qs(parsed.query).get("ref") or [None])[0]
    put_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    hdrs = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
    last_err = "unknown error"
    for attempt in range(retries):
        try:
            g = sess.get(remote_switch_url, headers=hdrs, timeout=8)
            if g.status_code != 200:
                last_err = f"GET {g.status_code}"
            else:
                sha = (g.json() or {}).get("sha")
                if not sha:
                    last_err = "GET 200 but response had no sha"
                else:
                    body = {
                        "message": f"STICKY KILL (trader-side, durable): {reason}"[:200],
                        "content": base64.b64encode(b"off").decode("ascii"),
                        "sha": sha,
                    }
                    if branch:
                        body["branch"] = branch
                    p = sess.put(put_url, headers=hdrs, json=body, timeout=8)
                    if 200 <= p.status_code < 300:
                        return True
                    last_err = f"PUT {p.status_code}: {str(getattr(p, 'text', ''))[:120]}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:100]}"
        if attempt < retries - 1:
            time.sleep(backoff_s * (2 ** attempt))
    try:
        alert_fn(f"⚠️ [kalshi] STICKY KILL fired ({reason}) but the durable "
                 f"LIVE_SWITCH=off commit FAILED after {retries} attempts ({last_err}) -- "
                 "falling back to the local sentinel + workflow-step path; this kill may NOT "
                 "survive a runner death. Verify LIVE_SWITCH manually.")
    except Exception:
        pass
    return False


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


def gate_check(side, price, yes_bid, yes_ask, net_delta, gate, fv_margin, bq=0.0, aq=0.0,
               tau_left=0.0):
    """True = TOXIC (skip or pull). Mirrors live_trader ufat gate: microprice anchor with
    p-adaptive margin. BUY-YES toxic if mp < price-margin; BUY-NO toxic if mp > (1-price)+margin.

    gate=="as": Avellaneda-Stoikov inventory control (32-day shadow A/B winner, +4.67c/win
    t=+7.68; ported from shadow_compare.py _gate_one's 'as' branch). ADD-inventory fills (side
    that grows |net_delta|) must clear a variance penalty that scales with |net_delta| and
    time-to-close; fills that REDUCE |net_delta| are NEVER gated. tau_left is seconds-to-close
    (mk['we'] - now); callers that don't pass it (gate != 'as') are unaffected."""
    if yes_bid is None or yes_ask is None:
        return False
    mp = microprice(yes_bid, yes_ask, bq, aq)
    if mp is None:
        return False
    if gate == "as":
        d_per = 1.0 if side == "yes" else -1.0   # buy-yes grows net_delta; buy-no shrinks it
        if net_delta * d_per < 0:
            return False                          # reduces |net_delta| -> never gate
        # side=="yes" ~ shadow's BID-on-up (edge = mp - price); side=="no" ~ shadow's ASK-on-up at
        # the implied yes-equivalent price (edge = yes_equiv - mp), matching gate_check's own
        # yes/no <-> BID/ASK mapping used by the ufat/marg branches below.
        edge = (mp - price) if side == "yes" else (round(1.0 - price, 4) - mp)
        penalty = AS_K * abs(net_delta) * (max(tau_left, 0.0) / AS_WINDOW_S)
        return edge < penalty
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


# --- OPT-IN EMPTY-BOOK SEEDING (--seed-empty) pure helpers -----------------------------------
# Pulled out to module level (same pattern as kelly_size/gate_check/portfolio_mult_budget above)
# so the empty-book classification, width-floor, staleness, re-price-threshold, and target-price
# math is unit-testable without spinning up main()'s live/dry-run event loop. main()'s nested
# `_seed_tick` closure (state: resting orders, cash, net_delta, SpotFair instance) calls these;
# see kalshi_trader.py's main() for that wiring and the full design rationale.
SEED_WINDOW_S = 900.0    # KX*15M window length (s) -- the width-floor sqrt(tau_s/900) normalizer
SEED_FLOOR_Z = 1.0       # width-floor "Z" (one sigma of the remaining-window expected move)
SEED_UNKNOWN_REST_AFTER_S = 30.0   # SEEDING v3: a WS 'unknown' classification (no snapshot yet)
# that PERSISTS this long triggers the REST-fallback classification below -- see the SEEDING v3
# comment block after seed_burst_should_trip for why 'unknown' is structurally permanent (not
# transient) for a genuinely empty book: Kalshi's WS sends no orderbook_snapshot at all for one.
SEED_REST_POLL_MIN_S = 5.0         # SEEDING v3: rate limit for the REST-fallback orderbook fetch
# itself (independent of --react-poll) -- keeps the fallback from hammering the public REST
# endpoint every tick once a window has crossed the unknown-persistence threshold above.


def seed_book_state(ws_entry):
    """Classify book emptiness on BOTH sides from a ws_state[ticker] entry (or None if no WS
    snapshot has arrived yet for this ticker). This is deliberately NOT derived from
    get_book_cached()/get_book(): both of those collapse a ONE-SIDED book (bids with no asks, or
    vice versa) to the exact same all-None result as a FULLY EMPTY book -- fine for "should we
    stand down" (yes, either way) but not precise enough to gate empty-book seeding, which must
    NEVER fire on a one-sided book.
    Returns:
      'empty'     -- no yes-side bids AND no no-side bids (no-side bids are the yes-ask side of
                     the book) -- the ONLY state that qualifies for seeding.
      'one_sided' -- exactly one side has any resting size -- does NOT qualify.
      'has_book'  -- both sides have resting size -- normal book-anchored quoting applies.
      'unknown'   -- no WS snapshot for this ticker yet -- NOT evidence of an empty book, so
                     never treated as 'empty' (avoids seeding on a false negative right after a
                     window rollover, before the WS feeder's first snapshot arrives)."""
    if ws_entry is None:
        return "unknown"
    yb = ws_entry.get("yes") or {}   # yes-side resting bids
    nb = ws_entry.get("no") or {}    # no-side resting bids == the yes-ask side of the book
    if not yb and not nb:
        return "empty"
    if not yb or not nb:
        return "one_sided"
    return "has_book"


def seed_width_floor(tau_s, sigma, z=SEED_FLOOR_Z, window_s=SEED_WINDOW_S):
    """WIDTH FLOOR: being the SOLE maker on an empty book means an informed taker can pick off a
    too-tight quote with zero competing flow to absorb the loss first -- the half-spread must
    cover the expected move over the time this quote will sit unchallenged:
        floor_cents = 100 * Z * sigma_per_s * sqrt(tau_s / 900)
    Z=1.0 (one sigma of the remaining-window move; 100x converts the probability-space sigma to
    cents); sigma_per_s is SpotFair's live per-second log-vol estimate, which itself falls back
    internally to the offline-calibrated constant when the tape hasn't warmed up yet (see
    fvfeed.SpotFair.sigma) -- so "sigma if available, else the static default" is already
    satisfied by the caller passing seed_fv.sigma() through unchanged, no extra branching needed
    here. 900 = the KX*15M window length (s), so sqrt(tau_s/900) normalizes remaining time to a
    fraction of a full window."""
    return 100.0 * z * sigma * math.sqrt(max(tau_s, 0.0) / window_s)


def seed_effective_width(seed_width_cfg, tau_s, sigma):
    """Effective half-spread used to quote: max(--seed-width, the width floor). The floor can
    only WIDEN the configured default, never tighten it."""
    return max(seed_width_cfg, seed_width_floor(tau_s, sigma))


def seed_should_reprice(fair_cents_now, fair_cents_at_placement, seed_width_cfg):
    """RE-PRICE DISCIPLINE: keep queue priority -- only cancel/re-post a seed quote if fair moved
    more than half the CONFIGURED --seed-width since placement. Deliberately compares against the
    static --seed-width (not the dynamic per-tick floor, which only ever widens what gets quoted)
    so the reprice trigger is a fixed, testable threshold independent of tau decay."""
    return abs(fair_cents_now - fair_cents_at_placement) > seed_width_cfg / 2.0 + 1e-9


def seed_spot_is_stale(last_update_ts, ok, s0, now, max_age_s):
    """True if the SpotFair feed is unavailable (never updated, not ok, or no window anchor) OR
    its last successful poll is older than --seed-max-age-s. Caller's contract on True: do
    nothing (no place, no keep-resting quotes) and log once, rate-limited -- never quote off a
    stale model."""
    if last_update_ts is None or not ok or s0 is None:
        return True
    return (now - last_update_ts) > max_age_s


def seed_target_cents(fair_p_up, eff_width_cents):
    """(yes_bid_cents, yes_ask_cents) around fair, clamped to the tradeable [1, 99] range with the
    ask forced strictly above the bid (>=1c) if width/clamping would otherwise collapse them."""
    fair_cents = fair_p_up * 100.0
    yb = max(1, round(fair_cents - eff_width_cents))
    ya = min(99, round(fair_cents + eff_width_cents))
    if ya <= yb:
        ya = min(99, yb + 1)
    return yb, ya


# --- SEEDING v2: FAIR-BAND TRIGGER (--seed-fair-band) --------------------------------------
# LIVE OBSERVATION (2026-07-12 ~04:12Z, verified via the public API + collected WS stream): the
# real overnight KXBTC15M book was NOT literally empty -- it held penny-crumb lottery bids
# (80,418 contracts @ 0.001, ~2,600 @ 0.002, ~700 @ 0.003) with NO asks and NOTHING near fair
# (~0.50); the REST summary showed yes_bid/yes_ask null and volume_24h=0. seed_book_state alone
# classifies that book as 'one_sided' (bids exist, asks don't) -> _seed_tick never seeds it --
# missing --seed-empty's primary real-world use case. seed_fair_band_state narrows that verdict.
def seed_fair_band_state(ws_entry, fair_cents, band_cents):
    """Refines seed_book_state's 'one_sided' verdict using a band around the spot-implied fair.

    Only 'one_sided' books are re-examined ('empty' always qualifies trivially, 'has_book' and
    'unknown' never do, regardless of band -- both echoed straight through from seed_book_state).
    For a 'one_sided' book, asks: is there a resting order (on EITHER side) inside
    [fair_cents - band_cents, fair_cents + band_cents]?
      - No  -> 'crumbs_only': the resting size is parked far from fair (the observed
               0.001-0.003c crumb bids vs a 50c fair) and carries no informational content about
               where the market actually is -- QUALIFIES for spot-anchored seeding.
      - Yes -> 'one_sided' (echoed): a REAL quote sits inside the band -- somebody is actually
               making a market there. Do NOT spot-seed in that case; the normal book-anchored
               PLACE loop already knows how to join a one-sided real market (anchor off the
               resting side), so spot-anchoring here would just duplicate/fight that logic with a
               different pricing model. Deliberately conservative: when in doubt, defer to the
               book-anchored path rather than the spot model.

    ws_entry prices are dollars (see ws_feeder/_apply_snapshot); no-side entries are NO bids,
    i.e. the YES-ask side of the book (mirrors seed_book_state's docstring), so they're converted
    via implied_yes_ask = 1 - no_bid_price before the band comparison."""
    base = seed_book_state(ws_entry)
    if base != "one_sided":
        return base
    lo, hi = fair_cents - band_cents, fair_cents + band_cents
    yb = (ws_entry or {}).get("yes") or {}   # resting YES bids (dollars)
    nb = (ws_entry or {}).get("no") or {}    # resting NO bids == the YES-ask side (dollars)
    for p in yb:
        if lo <= p * 100.0 <= hi:
            return "one_sided"
    for p in nb:
        if lo <= (1.0 - p) * 100.0 <= hi:
            return "one_sided"
    return "crumbs_only"


# --- SEEDING v2: AGGRESSOR-BURST COOLDOWN (--seed-burst-n / --seed-burst-cooldown-s) --------
# Mechanical (fill-count threshold), NOT a fitted toxicity model -- deliberately narrow. The
# 32-day A/B found reactive-pull gates cost money in NORMAL (retail-dominated) books via false
# positives, so this bot does not run one generally. But a burst of fills against a SOLE MAKER in
# a book nobody else is quoting (--seed-empty's only operating condition) has a very different
# informed-flow prior than a burst in a normal two-sided book -- hence this narrow, conservative,
# purely-mechanical version scoped to seeded quotes only.
def seed_burst_fill_count(fill_ts, now, window_s=60.0):
    """Count of `fill_ts` (an iterable of epoch timestamps) within the trailing `window_s`
    seconds of `now`. Pure/stateless so the caller's actual seeded-fill timestamp log can be
    handed in each tick/fill without this function doing its own bookkeeping."""
    return sum(1 for t in fill_ts if now - t <= window_s)


def seed_burst_should_trip(fill_ts, now, burst_n, window_s=60.0):
    """AGGRESSOR-BURST TRIP: True once seeded quotes have taken >= --seed-burst-n fills within
    any trailing `window_s` (60s) window."""
    return seed_burst_fill_count(fill_ts, now, window_s) >= burst_n


def seed_burst_cooldown_active(tripped_at, now, cooldown_s):
    """True while a burst-trip cooldown is in effect: seeding stays suppressed for
    --seed-burst-cooldown-s after `tripped_at`. tripped_at=None (never tripped) -> never active."""
    if tripped_at is None:
        return False
    return (now - tripped_at) < cooldown_s


def seed_burst_resume_width_mult(reseeds_since_cooldown):
    """WIDTH DOUBLING ON RESUME: the first seed placement after a cooldown lifts
    (reseeds_since_cooldown == 0) uses 2x the effective seed width -- an informed-flow burst just
    happened here, don't immediately re-offer the same tight quote. The next placement
    (reseeds_since_cooldown >= 1) decays back to normal (1x) width."""
    return 2.0 if reseeds_since_cooldown == 0 else 1.0


# --- SEEDING v3: REST FALLBACK FOR A PERSISTENT WS 'unknown' -------------------------------
# LIVE EVIDENCE (real 46-min live leg, run r29179923486, 2026-07-12 04:35-05:21Z): --seed-empty
# produced ZERO [SEED] log lines and zero placements across 4 windows on a market whose book was
# verified totally empty via the public REST API. Root cause: seed_book_state(ws_state.get(...))
# returns 'unknown' because Kalshi's WS sends NO orderbook_snapshot message at all for an empty
# book -- the ws_state entry for that ticker never materializes. 'unknown' is the correct verdict
# for a brief WS gap right after window rollover (transient), but it is structurally PERMANENT
# for an empty book (no snapshot is ever coming), so silently standing down on it forever is a
# real-money-relevant blind spot: the market's whole most-favorable-maker-condition window (the
# entire time nobody else is quoting) passes with the bot never seeding it. This section fixes
# that by falling back to the REST orderbook (parse_book_entry/get_book_raw above) once 'unknown'
# has PERSISTED past SEED_UNKNOWN_REST_AFTER_S, and classifying the REST snapshot through the
# SAME seed_book_state/seed_fair_band_state functions the WS path uses, so classification stays
# single-sourced regardless of which feed produced the book snapshot.
def seed_unknown_persisted(first_seen_ts, now, threshold_s=SEED_UNKNOWN_REST_AFTER_S):
    """True once a WS 'unknown' classification has been continuously observed for >= threshold_s,
    given the epoch timestamp it was FIRST seen (first_seen_ts, None if never seen / already
    resolved). Pure/stateless -- caller owns the actual 'first seen' bookkeeping (mirrors
    seed_burst_fill_count's pattern: the caller's timestamp log is handed in, no bookkeeping
    happens inside this function). This is the gate for attempting the REST fallback at all: below
    threshold, 'unknown' is treated as an ordinary transient WS gap (no REST call, no churn) --
    only a PERSISTENT unknown is treated as REST-fallback-worthy."""
    if first_seen_ts is None:
        return False
    return (now - first_seen_ts) >= threshold_s


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
    ap.add_argument("--size-mode", choices=["flat", "kelly", "depth", "markout"], default="flat",
                    help="kelly = fee-aware edge sizing; depth = DEPTH-PROPORTIONAL (size ~ both-side "
                         "top-5 depth, captures the ~$27/day capacity ceiling on the pair-gated box, "
                         "IS/OOS-stable); markout = continuous micro-favorability sizing, 32-day shadow "
                         "A/B winner (+1.88c/win, t=+5.76; MAKEREDGE.md #3, shadow_compare.py _size "
                         "'markout' branch, ported verbatim incl. MO_K); flat = always --post")
    ap.add_argument("--depth-size-frac", type=float, default=0.005,
                    help="--size-mode depth: target contracts = frac * min(top-5 both-side depth) "
                         "(capacity study: ~0.005 * depth ~ 165ct at 33k depth was the gross optimum).")
    ap.add_argument("--depth-size-cap", type=float, default=10.0,
                    help="--size-mode depth: hard cap on contracts/leg (also bounded by --max-notional).")
    ap.add_argument("--improve-tick", type=float, default=0.01,
                    help="one tick inside the touch (1c); set 0.001 only if/where the venue accepts sub-cent")
    ap.add_argument("--gate", choices=["ufat", "micro", "marg", "as"], default="ufat",
                    help="as = Avellaneda-Stoikov inventory control, 32-day shadow A/B winner "
                         "(+4.67c/win, t=+7.68; GATING.md, shadow_compare.py _gate_one 'as' branch, "
                         "ported verbatim incl. AS_K): only ADD net inventory when the microprice edge "
                         "clears a variance penalty scaling with |net_delta| and time-to-close; fills "
                         "that REDUCE |net_delta| are never gated")
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
    # PAIR-OR-DONT-PLAY (audit 2026-06-14): edge is intact on PAIRED boxes; the loss is strands. Only
    # open when BOTH legs are likely to pair -- balanced book + depth on both sides.
    ap.add_argument("--pair-gate", action="store_true", default=False,
                    help="only OPEN a box when min(top-5 both-side depth) >= --pair-min-depth. The pair-gate "
                         "study: depth is the DOMINANT strand predictor -- deep balanced books pair both legs; "
                         "thin books strand one. Cuts strand 14.8%%->1.9%% keeping 86%% volume. Completions exempt.")
    ap.add_argument("--pair-min-depth", type=float, default=33000.0,
                    help="min of (top-5 YES-bid total, top-5 YES-ask total) to allow a fresh OPEN under "
                         "--pair-gate. Study-calibrated 33000 (the tape median); deeper = lower strand rate.")
    ap.add_argument("--dispose-max-give", type=float, default=0.25,
                    help="give-CAP for the strand cross: complete by crossing ONLY if the lock loss <= "
                         "this ($); if completing would cost MORE, HOLD the bounded leg. Stranded legs "
                         "settle WORTHLESS ~100%% (adversely selected), so completing at any price <$1 "
                         "beats holding; EV is MONOTONE in the cap (recovery=basis-give). "
                         "COMPLETION-EXEC AUDIT 2026-06-14 (BOX_COMPLETION_EXEC.md): the live loss is "
                         "DEEP over-fill-residual strands that ride NAKED to ~-50c because the old 0.10 cap "
                         "REFUSED to cross them (give>10c -> held). Raised to 0.25 so a deep residual is "
                         "crossed at a bounded ~-25c instead of held to -50c (~+2.8c/box). 0.25 still bounds "
                         "the repeated-recross thrash. (Supersedes the 0.10 cap, whose 'wash' sample "
                         "under-represented the deep residuals; root-cause prevention is --post-complete-freeze.)")
    ap.add_argument("--post-complete-freeze", type=float, default=0.0,
                    help="OVER-FILL RESIDUAL GUARD (BOX_COMPLETION_EXEC.md). When a completion returns "
                         "inventory to FLAT, cancel all resting OPENING rungs and hold off NEW opens for "
                         "this many seconds. Kills the dominant live loss: 14/16 toxic strands were "
                         "over-fill residuals -- a clean box forms, then a stale same-side ladder rung fills "
                         "1-3s later UNPARTNERED and rides naked to ~-50c. Completing quotes (net!=0) are "
                         "NEVER frozen. 0 = OFF (default); live A/B enables ~1.5s.")
    ap.add_argument("--requote-stale-s", type=float, default=20.0,
                    help="drop a resting rung older than this IF the mid has moved >=1 tick since "
                         "placement (markout forensics: fills on >15s-old quotes run -2.04c/fill "
                         "vs +0.79c fresh -- stale quotes are the pick-off; queue position at a "
                         "wrong price is anti-value). 0 disables")
    ap.add_argument("--portfolio-aware", action="store_true", default=False,
                    help="OPT-IN, OFF by default (zero behavior change unless set). Composes two "
                         "MECHANICAL multipliers (no fitted model -- see PORT_TICKER_PREFIX comment) "
                         "onto whatever --size-mode already picked, using the account's OWN "
                         "authenticated balance+positions (the shared venue state across ALL "
                         "per-asset runners): a BUDGET multiplier that shrinks as the whole "
                         "account's open notional fills --port-budget, and a DELTA-CONCENTRATION "
                         "multiplier that de-rates fills which would push aggregate cross-asset "
                         "directional exposure past --port-delta-max (de-risking fills are always "
                         "exempt). Applied strictly BEFORE the existing --max-net/--max-notional "
                         "hard rails, which are re-applied unchanged afterward -- can only shrink "
                         "size, never bypass a cap. Any portfolio-state API failure or staleness "
                         "(>3x --port-refresh-s) snaps both multipliers to 1.0 (fail-safe: never "
                         "block trading on this being unavailable).")
    ap.add_argument("--port-budget", type=float, default=20,
                    help="--portfolio-aware: $ of whole-account open-position notional at which "
                         "the BUDGET multiplier reaches 0 (linear ramp from --port-budget down to 0).")
    ap.add_argument("--port-delta-max", type=int, default=12,
                    help="--portfolio-aware: contracts of aggregate signed cross-asset KX*15M delta "
                         "(YES=+1, NO=-1) at which the DELTA-CONCENTRATION multiplier starts "
                         "de-rating add-inventory fills (0.5 at the limit, 0.0 at 1.5x the limit).")
    ap.add_argument("--port-refresh-s", type=float, default=120,
                    help="--portfolio-aware: PortfolioState refresh cadence (s). Data older than "
                         "3x this is treated as stale -> multipliers fail-safe to 1.0.")
    ap.add_argument("--seed-empty", action="store_true", default=False,
                    help="OPT-IN, OFF by default (zero behavior change unless set). Normally an "
                         "empty book (no resting YES bids AND no resting YES asks from ANYONE) "
                         "makes the bot stand down -- it anchors quotes off the existing book. But "
                         "an empty book is the single most favorable maker condition (zero queue "
                         "competition, full spread to whoever quotes). When enabled, on a book "
                         "confirmed empty on BOTH sides (a one-sided book does NOT qualify -- see "
                         "_seed_book_state), post post-only 1-lot quotes around the SpotFair spot-"
                         "implied fair P(up) instead. Being the SOLE maker also means an informed "
                         "taker can pick you off with zero competing flow to absorb it first, so "
                         "width is floored by expected move (--seed-width) and quotes are pulled the "
                         "instant fair drifts past half the width or the book is no longer empty. "
                         "PRE-REGISTERED EVALUATION BAR: seeded orders are tagged {'seeded': true} "
                         "in the order-lifecycle log; recon window rows gain n_seeded_fills/"
                         "seeded_net. If seeded_net < 0 after >=30 seeded fills, this mode should be "
                         "disabled pending review -- that is an operator action off the recon data, "
                         "not an automatic kill.")
    ap.add_argument("--seed-width", type=float, default=4.0,
                    help="--seed-empty: half-spread (cents) each side of the SpotFair fair when "
                         "seeding an empty book -- YES bid = fair-width, YES ask = fair+width. Also "
                         "the re-price threshold (fair moving > width/2 since placement reprices the "
                         "seed quotes). Floored per-tick by the expected-move formula: effective "
                         "width = max(--seed-width, 100*1.0*sigma*sqrt(tau_s/900)) -- see the "
                         "WIDTH FLOOR comment on _seed_width_floor.")
    ap.add_argument("--seed-max-age-s", type=float, default=10.0,
                    help="--seed-empty: max SpotFair staleness (s). If the spot feed has no update "
                         "newer than this (or never got one), seeding no-ops -- does not place or "
                         "keep resting seed quotes -- and logs one rate-limited line. Never quote "
                         "off a stale model.")
    ap.add_argument("--seed-tau-min-s", type=int, default=150,
                    help="--seed-empty: never seed (and cancel any resting seed quotes) inside this "
                         "many seconds of window close -- the same force-flatten discipline every "
                         "other rung gets, applied earlier because a sole-maker fill this late has "
                         "no time left to find a natural pair.")
    ap.add_argument("--seed-fair-band", type=float, default=15.0,
                    help="--seed-empty FAIR-BAND TRIGGER: cents around the SpotFair fair "
                         "(fair*100 +/- this) used to refine a 'one_sided' book verdict (see "
                         "seed_fair_band_state). A one-sided book still qualifies for seeding "
                         "('crumbs_only') as long as NO resting order on either side falls inside "
                         "the band -- e.g. penny-crumb lottery bids parked far from fair (observed "
                         "2026-07-12 ~04:12Z on KXBTC15M: 80,418 contracts @0.001, ~2,600 @0.002, "
                         "~700 @0.003, no asks, fair ~0.50) do NOT block seeding. A REAL quote "
                         "inside the band on one side DOES block it -- the normal book-anchored "
                         "PLACE loop handles joining that market instead.")
    ap.add_argument("--seed-burst-n", type=int, default=2,
                    help="--seed-empty AGGRESSOR-BURST COOLDOWN: if seeded quotes take >= this "
                         "many fills within any rolling 60s window, cancel remaining seed quotes "
                         "immediately and suppress new seeding for --seed-burst-cooldown-s. "
                         "Mechanical fill-count trip, not a fitted model -- narrower than the "
                         "reactive-pull gates that cost money via false positives in NORMAL "
                         "retail-dominated books over the 32-day A/B: a fill burst against a SOLE "
                         "maker in an unquoted book has a very different informed-flow prior.")
    ap.add_argument("--seed-burst-cooldown-s", type=float, default=120.0,
                    help="--seed-empty AGGRESSOR-BURST COOLDOWN: seconds to suppress new seeding "
                         "after a --seed-burst-n trip. On resume, the first re-seed quotes at 2x "
                         "the effective seed width (see seed_burst_resume_width_mult), decaying to "
                         "normal width on the next re-seed.")
    a = ap.parse_args()

    live = a.live and os.environ.get("I_UNDERSTAND_REAL_MONEY") == "yes"
    if a.live and not live:
        print("REFUSING --live without I_UNDERSTAND_REAL_MONEY=yes. DRY-RUN.")
    mode = "LIVE" if live else "DRY-RUN"

    # STICKY KILL sentinel (same as live_trader): survives systemd Restart=always so a kill-switch
    # isn't immediately overridden. Delete the file manually after investigating.
    kill_sentinel = f".kalshi_killed_{a.asset}15m"

    # Hoisted above _record_kill (below) and reused by _remote_switch_is_off (further down): both
    # need the same GH token, and _record_kill needs it FIRST so a kill trip can commit
    # LIVE_SWITCH=off durably at the moment it fires (DEADMAN_AUDIT.md fix #1) rather than only
    # ever writing the local, gitignored, non-durable sentinel below.
    _gh_tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def _record_kill(why):
        try:
            with open(kill_sentinel, "w") as fh:
                fh.write(json.dumps({"ts": time.time(), "reason": why}) + "\n")
        except Exception:
            pass
        # DURABLE STICKY-KILL (DEADMAN_AUDIT.md fix #1): commit LIVE_SWITCH=off to the branch
        # RIGHT NOW via the GitHub contents API, instead of depending on a later workflow step
        # (on the same runner) to push it -- a runner hard-killed between here and that step
        # previously lost the kill entirely. No-op when GH_TOKEN/--remote-switch-url are absent
        # (local/dry runs); on total failure, remote_switch_kill() itself alerts and we still
        # fall back to the sentinel written just above + the existing workflow-step path.
        try:
            if remote_switch_kill(_gh_tok, a.remote_switch_url, why):
                print("[STICKY-KILL] LIVE_SWITCH=off committed durably via GitHub contents API")
        except Exception as e:
            print(f"[STICKY-KILL] remote commit raised unexpectedly (sentinel still written): "
                  f"{type(e).__name__}: {str(e)[:120]}")

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

    # --- OPT-IN empty-book seeding (--seed-empty; OFF by default -> seed_fv stays None and every
    # seeding closure below no-ops on that, zero cost/behavior change). SpotFair instance mirrors
    # kalshi_collect.KalshiMarket's own (same class, same per-asset symbol construction) so the fair
    # value seeded quotes anchor to is the SAME validated model, not a reimplementation.
    seed_fv = SpotFair(requests.Session(), symbol=f"{a.asset.upper()}USDT") if a.seed_empty else None
    _seed_poll_ts = {"t": 0.0}    # rate-limits SpotFair.update() to >=1/s (independent of --react-poll)
    _seed_log_ts = {}             # rate-limit KEY -> last-emitted epoch ts (see _seed_log_rl);
    # keys in use: "stale" (30s, spot-feed-unavailable notice), "heartbeat" (60s, SEEDING v3
    # [SEED] state=... observability line, emitted every tick regardless of branch taken).
    _seed_unknown_since = {"ticker": None, "ts": None}   # SEEDING v3: epoch ts the CURRENT
    # ticker's WS book classification was first observed as 'unknown' (None if not currently
    # unknown, or no ticker seen yet). Reset whenever the ticker changes (new window -> fresh WS
    # snapshot wait) or the WS classification resolves to anything else. Feeds
    # seed_unknown_persisted() to gate the REST fallback below.
    _seed_rest_cache = {"ticker": None, "ts": 0.0, "entry": None}   # SEEDING v3: last successful
    # REST-fallback orderbook fetch (ws_entry-shaped, via get_book_raw), rate-limited to
    # >=SEED_REST_POLL_MIN_S and reused across ticks within that window / on a transient REST
    # failure. Reset whenever the ticker changes.
    seed_win = {"n_fills": 0, "cash": 0.0, "pos_yes": 0.0, "pos_no": 0.0}   # THIS window's seeded-fill
    # accumulator (audit: recon rows compute n_seeded_fills/seeded_net from this, reset at rollover).
    # AGGRESSOR-BURST COOLDOWN (--seed-burst-n/--seed-burst-cooldown-s):
    seed_fill_times: list = []     # epoch ts of seeded fills, pruned to a rolling 60s window on each
    # append -- feeds seed_burst_should_trip. Never touched when --seed-empty is off (no seeded
    # fills are possible), so this is zero cost/behavior change by default.
    seed_cooldown = {"tripped_at": None, "resumes": None}   # tripped_at: epoch of the last burst
    # trip (None = never tripped -> cooldown never active). resumes: # of seed placements since
    # that cooldown lifted (None until the first trip ever happens; 0 -> the next placement gets
    # 2x width per seed_burst_resume_width_mult, then increments so the one after decays to 1x).
    seed_cooldown_win = {"n": 0}   # THIS window's burst-cooldown TRIP count -> recon row
    # n_seed_cooldowns (mirrors seed_win's reset-at-rollover pattern).
    # COMPREHENSIVE per-window microstructure (live RCA 2026-06-13): the re-validation gate (strand
    # rate, legging gap, maker/taker mix, dispose-cross firing) plus the offline strand analysis read
    # this. Written per window to kalshi_winrec_<asset>15m.jsonl, reset at rollover.
    winrec = {"taker": 0, "maker": 0, "maxnet": 0.0, "first_ts": {}, "dispose_cross": 0}
    winrec_fh = open(f"kalshi_winrec_{a.asset}15m.jsonl", "a")
    # LIVE-VS-SHADOW RECONCILIATION (BACKTEST_VS_LIVE.md-style): one row per settled window, named
    # to match shadow_windows_<asset><tenor>m_r<RUNID>.jsonl so each live window pairs against the
    # shadow row for the same (asset, tenor, ws) -- realized vs predicted edge and fill-rate. Runs
    # into gha_data/ so collect.yml's existing commit step sweeps it up like the other data streams.
    _RUNID = os.environ.get("GITHUB_RUN_ID", "local")
    _RECON_TENOR = 15   # this module only trades KX{asset}15M (see discover(): ws = we - 900)
    _RECON_PATH = os.path.join("gha_data", f"live_recon_{a.asset}{_RECON_TENOR}m_r{_RUNID}.jsonl")
    _STRATEGY_TAG = f"{a.gate}+{a.size_mode}"

    # ORDER-LIFECYCLE LOG (queue/fill-model calibration -- the last unverified assumption
    # between shadow edge and real money). One row per place/fill/partial/cancel/reject/expire
    # event, keyed by order_id, with queue_ahead_est = the size resting at that price level
    # (on the side we're joining) at the moment we placed -- the actual queue-position proxy
    # the fill model needs. Named like live_recon_*/shadow_windows_* so collect.yml's existing
    # gha_data commit step sweeps it up automatically. Best-effort/non-blocking throughout
    # (same try/except pattern as _recon_write): logging must never affect trading.
    _LIFECYCLE_PATH = os.path.join("gha_data", f"order_lifecycle_{a.asset}15m_r{_RUNID}.jsonl")

    def _lifecycle_write(event, order_id, side, price, size, queue_ahead_est,
                         port_mult_budget=None, port_mult_delta=None, seeded=False):
        """port_mult_budget/port_mult_delta (AUDITABILITY, PORTFOLIO-AWARE SIZING): the two
        multipliers applied to THIS sizing decision when --portfolio-aware is on; always null
        when it's off (or for event types the portfolio-aware path doesn't size, e.g. cancels) --
        every sizing decision stays reconstructable from this log alone.
        seeded (AUDIT, --seed-empty): True for every event on an order that was placed by the
        empty-book seeding path; False (default) for everything else -- always present (not just
        when true) so seeded vs. normal rows are trivially filterable for the pre-registered
        seeded_net evaluation."""
        try:
            os.makedirs("gha_data", exist_ok=True)
            with open(_LIFECYCLE_PATH, "a") as _lf:
                _lf.write(json.dumps({
                    "ts": time.time(), "event": event, "order_id": order_id, "side": side,
                    "price": round(price, 4) if price is not None else None,
                    "size": size, "queue_ahead_est": queue_ahead_est,
                    "port_mult_budget": (round(port_mult_budget, 4)
                                        if port_mult_budget is not None else None),
                    "port_mult_delta": (round(port_mult_delta, 4)
                                       if port_mult_delta is not None else None),
                    "seeded": bool(seeded),
                }) + "\n")
        except Exception:
            pass

    def _lifecycle_write_seed_cooldown(fills_in_burst):
        """AGGRESSOR-BURST COOLDOWN trip event: {"event": "seed_cooldown", "fills_in_burst": n}.
        Appended to the same order-lifecycle log as every other seed event (best-effort/non-
        blocking, same try/except pattern as _lifecycle_write -- logging must never affect
        trading)."""
        try:
            os.makedirs("gha_data", exist_ok=True)
            with open(_LIFECYCLE_PATH, "a") as _lf:
                _lf.write(json.dumps({
                    "ts": time.time(), "event": "seed_cooldown",
                    "fills_in_burst": int(fills_in_burst),
                }) + "\n")
        except Exception:
            pass

    def _queue_ahead_est(side, price):
        """Size resting at `price` on `side` (yes/no book) at the instant we're about to join it,
        i.e. the WS book level BEFORE our own order lands there -- the queue-position proxy this
        log exists to calibrate. Falls back to None if the WS book isn't populated for this
        ticker/price (e.g. DRY-RUN with no live feed, or a level with no resting size)."""
        try:
            if mk is None:
                return None
            st = ws_state.get(mk["cid"])
            if not st:
                return None
            book_side = st.get(side) or {}
            v = book_side.get(round(price, 4))
            return round(v, 4) if v is not None else 0.0
        except Exception:
            return None

    def _recon_write(ws_epoch, requested, fills, net, gross, inv_max,
                     n_seeded_fills=0, seeded_net=0.0, n_seed_cooldowns=0):
        """Append one reconciliation row. Best-effort/non-blocking: any failure here must never
        affect trading (mirrors the try/except pattern around winrec_fh.write above).
        n_seeded_fills/seeded_net (AUDIT, --seed-empty PRE-REGISTERED EVALUATION): fills against
        seeded orders and their settled P&L for THIS window only (0/0.0 when --seed-empty is off,
        or when this window had no seeded fills). The bar: if seeded_net < 0 after >=30 cumulative
        seeded fills across recon rows, --seed-empty should be disabled pending review.
        n_seed_cooldowns (AUDIT, AGGRESSOR-BURST COOLDOWN): count of --seed-burst-n trips during
        THIS window (0 when --seed-empty is off, or when no burst tripped)."""
        try:
            os.makedirs("gha_data", exist_ok=True)
            with open(_RECON_PATH, "a") as _rf:
                _rf.write(json.dumps({
                    "ws": ws_epoch, "asset": a.asset, "tenor": _RECON_TENOR,
                    "strategy": _STRATEGY_TAG, "fills": int(fills), "requested": int(requested),
                    "fill_rate": round(fills / requested, 4) if requested else 0.0,
                    "net": round(net, 4), "gross": round(gross, 4), "inv_max": round(inv_max, 2),
                    "n_seeded_fills": int(n_seeded_fills), "seeded_net": round(seeded_net, 4),
                    "n_seed_cooldowns": int(n_seed_cooldowns),
                }) + "\n")
        except Exception:
            pass

    # --- PORTFOLIO-AWARE SIZING runtime state (opt-in --portfolio-aware; see the module-level
    # comment by PORT_TICKER_PREFIX and portfolio_mult_budget/portfolio_mult_delta/
    # refresh_portfolio_state for the design). Entirely inert when the flag is off: neither
    # closure below is ever called from the sizing path unless a.portfolio_aware is True.
    _port_state = {"committed": 0.0, "agg_delta_other": 0.0, "last_attempt_ts": 0.0,
                   "last_success_ts": 0.0, "ok": False}

    def _port_refresh_if_due():
        """Re-pull PortfolioState at most once per --port-refresh-s (rate-limited on ATTEMPT
        time, not success, so a persistently-unavailable API -- e.g. DRY-RUN with no secrets --
        logs/retries at a bounded cadence instead of hammering every loop tick)."""
        if not a.portfolio_aware:
            return
        now = time.time()
        if now - _port_state["last_attempt_ts"] < a.port_refresh_s:
            return
        _port_state["last_attempt_ts"] = now
        if not live:
            # DRY-RUN: no authenticated session is possible (no priv key) -- portfolio state is
            # definitionally unavailable here. FAIL-SAFE (never blocks trading): _port_multipliers
            # below reads "ok"/"last_success_ts" and snaps to 1.0 on its own; this is just the log.
            print("[portfolio-aware] DRY-RUN: no authenticated session -> portfolio state "
                  "unavailable, sizing multipliers snap to 1.0 (fail-safe)")
            return
        try:
            fresh = refresh_portfolio_state(sess, priv, a.asset)
            _port_state["committed"] = fresh["committed"]
            _port_state["agg_delta_other"] = fresh["agg_delta_other"]
            _port_state["last_success_ts"] = fresh["ts"]
            _port_state["ok"] = True
        except Exception as e:
            # FAIL-SAFE: leave the previous (possibly-empty) state in place; staleness in
            # _port_multipliers is what actually snaps sizing multipliers to 1.0 -- an API
            # failure must never itself block or shrink trading.
            print(f"[portfolio-aware] refresh FAILED (fail-safe: multipliers snap to 1.0 until "
                  f"the next successful refresh): {type(e).__name__}: {str(e)[:120]}")

    def _port_multipliers(side, want, net_delta):
        """(mult_budget, mult_delta) for THIS candidate fill. FAIL-SAFE: unavailable (never
        succeeded) or STALE (last success > 3x --port-refresh-s ago) snaps BOTH to 1.0 --
        portfolio-state unavailability must never block/shrink trading, only ever additionally
        constrain it when fresh data says to. agg_delta_other (refreshed, other assets) is
        combined with `net_delta` (this session's OWN live, fill-by-fill-accurate inventory for
        the current asset -- see refresh_portfolio_state's docstring for why the split)."""
        now = time.time()
        stale = (not _port_state["ok"]) or (now - _port_state["last_success_ts"] >
                                            3.0 * a.port_refresh_s)
        if stale:
            return 1.0, 1.0
        mb = portfolio_mult_budget(_port_state["committed"], a.port_budget)
        agg_before = _port_state["agg_delta_other"] + net_delta
        md = portfolio_mult_delta(agg_before, side, want, a.port_delta_max)
        return mb, md

    loop_ctx = {}                              # decision-time book state, stamped onto each fill
    threading.Thread(target=_spot_poller, args=(_COINBASE_PRODUCT.get(a.asset, "BTC-USD"),),
                     daemon=True).start()   # sig telemetry (isolated; non-blocking; per-asset spot)
    ops = {"place": 0, "cancel": 0, "cancel_fail": 0}   # per-window execution-quality counters

    # DEADMAN_AUDIT.md fix #2 payload: filled in by the startup position-reconciliation block
    # below (live only) and consumed once, when this session first attaches to a window (see
    # "_inherited_seed_done" near the state-init block a little further down). Stays None for
    # dry-run/local so the seeding path there is a guaranteed no-op. init_mk is likewise defined
    # unconditionally (None unless live) so the later rollover block can reference it safely.
    _inherited = None
    init_mk = None

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

        # C8 startup INVENTORY reconciliation (DEADMAN_AUDIT.md fix #2): the trader previously
        # never queried real venue positions, so a restarted process always assumed
        # net_delta==0 -- combined with poll_fills'/sweep_window_fills' first-call fill-seeding
        # (which marks any already-resting fills "seen" without booking them), a restart landing
        # on the same still-open ticker as a dead predecessor had NO way to learn it wasn't
        # actually flat. Query positions here (read-only, same auth already established above)
        # and filter to the active ticker; the state-init block below seeds net_delta/pos/
        # win_cost from `_inherited` so every downstream risk clamp (--max-net, the C2 loss-limit
        # worst-open calc, dispose-cross/chase-unpaired) sees the TRUE starting inventory instead
        # of a blind zero, and treats it exactly like any position opened this session.
        # Defensive/never-fatal throughout, unlike the fail-closed order reconciliation above:
        # any failure here logs and safe-defaults to the PRE-FIX behavior (assume flat) rather
        # than blocking startup -- a missed inherited position is the status quo ante, not a new
        # hazard this fix could introduce.
        try:
            print("[startup] reconciling venue positions...")
            mpos = get_positions(sess, priv)
            if init_mk:
                _inherited = _parse_inherited_position(mpos, init_mk["cid"])
            if _inherited:
                _msg = (f"inherited venue position at startup: {_inherited['side'].upper()} "
                        f"x{_inherited['count']:.0f} {init_mk['cid']} "
                        f"cost~${_inherited['cost']:.2f} -- seeding into risk state, existing "
                        "disposal/flatten machinery will manage it like any position")
                print(f"  [startup] {_msg}")
                notify.alert(f"⚠️ [kalshi] {_msg}")
            else:
                print("  [startup] venue positions clean (flat) on active ticker")
        except Exception as e:
            print(f"[startup] position reconciliation FAILED (non-fatal; defaulting to flat, "
                  f"same as pre-fix behavior): {type(e).__name__}: {str(e)[:120]}")
            _inherited = None

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
    last_complete_ts = 0.0   # wall-clock of the last |net|->0 completion (over-fill freeze clock)
    prev_net_freeze = 0.0    # net_delta at the previous loop top (to detect a completion transition)
    realized = 0.0           # settled P&L across closed windows
    _strand_sched = [float(x) for x in a.strand_scaledown.split(",") if x.strip()]  # streak guard
    _consec_strands = 0      # consecutive stranded windows (drives --strand-scaledown)
    window_mark = 0.0        # current window mark-to-mid (open position value)
    pos = {}                 # ticker+"YES"|"NO" -> contracts held (from fills)
    cash = 0.0               # net cash flow this window (positive = received)
    # DEADMAN_AUDIT.md fix #2: `_inherited` (set by startup reconciliation above; None if flat/
    # dry-run/lookup failed) is applied exactly once, at the first window this session attaches
    # to (see the rollover block below). `_inherited_seed_done` gates that "exactly once" -- it
    # must flip regardless of whether `_inherited` actually held anything, so a flat-venue result
    # doesn't leave this dangling to (incorrectly) fire on some later window instead.
    _inherited_seed_done = False
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
            _meta = pending_cancel.get(key) or {}
            _rem = max(_meta.get("want", a.post) - _meta.get("filled", 0.0), 0.0)
            if live:
                ok2 = cancel_order(sess, priv, oid)
                ops["cancel"] += 1
                if ok2:
                    pending_cancel.pop(key, None)        # venue-confirmed gone -> stop counting it
                    _lifecycle_write("cancel", oid, key[0], key[1], _rem, _meta.get("qahead"),
                                     seeded=bool(_meta.get("seeded")))
                else:
                    ops["cancel_fail"] += 1
                    lm.event("cancel_fail", side=key[0], price=key[1], reason=reason)
                    print(f"  [CANCEL-FAIL] {oid[:16]} key={key} reason={reason}")
                    side_cooldown[key[0]] = time.time() + a.fill_cooldown   # likely filling against us
                    ok = False                            # stays in pending_cancel -> clamp sees it
            else:
                print(f"  [DRY cancel] key={key} reason={reason}")
                pending_cancel.pop(key, None)
                _lifecycle_write("cancel", oid, key[0], key[1], _rem, _meta.get("qahead"),
                                 seeded=bool(_meta.get("seeded")))
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
    # _gh_tok is hoisted above _record_kill now (durable sticky-kill needs it first); reused here.
    _rsw = {"last": 0.0}

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
    def place(side, price, yes_bid, yes_ask, count=None, cross=False, port_mult=None, seeded=False):
        """Post one rung. Returns order_id or None. DRY-RUN: prints, returns fake id.
        side='yes'|'no'. price in dollars (up to 4 decimals).
        Post-only guard (cross=False, default): we only place maker BUYs; Kalshi's post_only=True
        rejects if marketable, and belt-and-suspenders we also refuse a BUY-YES >= yes_ask / BUY-NO
        >= (1-yes_bid) before sending. cross=True (DISPOSAL ONLY): deliberately TAKE the offer to
        COMPLETE a stranded box (post_only=False) -- skip the guard; the caller bounds the give.
        port_mult (AUDITABILITY, PORTFOLIO-AWARE SIZING): optional (mult_budget, mult_delta) tuple
        stamped onto the lifecycle log row when the caller applied portfolio-aware sizing to this
        fill; None (default, and always for cross/chase/dispose call sites that don't size via
        that path) -> both log fields are null.
        seeded (AUDIT, --seed-empty): True when this order is an empty-book seed quote -- stamped
        onto the lifecycle row so seeded orders are provably tagged from placement through fill."""
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
        _sz = count or int(a.post)
        _qahead = _queue_ahead_est(side, price)   # snapshot BEFORE the order lands (queue-ahead proxy)
        _pmb, _pmd = port_mult if port_mult is not None else (None, None)
        if not live:
            fake = f"dry_{side}_{price:.4f}_{int(t_dec*1000)%100000}"
            print(f"  [DRY {'CROSS-COMPLETE' if cross else 'place'}] BUY-{side.upper()} {count or int(a.post)} @ {price:.4f}")
            _lifecycle_write("place", fake, side, price, _sz, _qahead,
                             port_mult_budget=_pmb, port_mult_delta=_pmd, seeded=seeded)
            return fake, t_dec, time.time()
        oid, sc_, err_ = place_order(sess, priv, mk["cid"], side, price, count or int(a.post),
                                     ttl_s=(a.order_ttl_s or None), post_only=not cross)
        t_ack = time.time()
        if oid is None:
            lm.place_reject(side, price, f"HTTP {sc_}: {err_}")
            reject_cd[(side, round(price, 4))] = time.time() + a.reject_cooldown_s
            _lifecycle_write("reject", None, side, price, _sz, _qahead,
                             port_mult_budget=_pmb, port_mult_delta=_pmd, seeded=seeded)
            return None
        placed_oids.add(oid)
        ops["place"] += 1
        lm.place_ack(side, price, False, (t_ack - t_dec) * 1e3)
        _lifecycle_write("place", oid, side, price, _sz, _qahead,
                         port_mult_budget=_pmb, port_mult_delta=_pmd, seeded=seeded)
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

    # ------------------------------------------------------------------
    # OPT-IN EMPTY-BOOK SEEDING (--seed-empty; every closure below is a no-op when the flag is off
    # -- seed_fv is None, and every call site below is itself gated on a.seed_empty, so this is
    # zero behavior/cost change by default).
    #
    # WHY: the normal path (below, in the main loop) stands down when get_book_cached returns no
    # usable bb/ba -- it anchors quotes off the EXISTING book, so no book means no anchor. But a
    # book with NO resting orders from anyone is the single most favorable maker condition: zero
    # queue competition, the full spread to whoever quotes first. This mode fills that gap with a
    # SpotFair spot-implied fair (the same model kalshi_collect.py's shadow/backtest pipeline
    # validates offline) instead of the book, ONLY when the book is confirmed empty on BOTH sides.
    #
    # PRE-REGISTERED EVALUATION BAR (documented here, enforced by the operator off the recon data,
    # NOT automatically by this code): seeded orders carry {"seeded": true} through every lifecycle
    # event (see place()/_lifecycle_write() above); recon window rows gain n_seeded_fills/seeded_net
    # (see the pending_settles loop below). If seeded_net < 0 after >=30 cumulative seeded fills,
    # --seed-empty should be disabled pending review.
    # ------------------------------------------------------------------

    def _seed_spot_fair(tau_left):
        """Rate-limited (>=1/s, independent of --react-poll) SpotFair poll, then delegates the
        actual staleness/availability call to the module-level seed_spot_is_stale() (unit-tested
        directly). Returns (fair_p_up, sigma_per_s) or (None, None) if the feed is unavailable or
        stale -- the caller's contract is to then do nothing (no place, no keep-resting) and log
        once, rate-limited. Never quote off a stale model."""
        if seed_fv is None:
            return None, None
        now = time.time()
        if now - _seed_poll_ts["t"] >= 1.0:
            _seed_poll_ts["t"] = now
            seed_fv.update()
        last_ts = seed_fv.tape[-1][0] if seed_fv.tape else None
        if seed_spot_is_stale(last_ts, seed_fv.ok, seed_fv.s0, now, a.seed_max_age_s):
            return None, None
        fair = seed_fv.p_up(tau_left)
        if fair is None:
            return None, None
        return fair, seed_fv.sigma()

    def _seed_log_rl(msg, key="stale", interval=30.0):
        """Rate-limited [SEED] log line, keyed independently so unrelated messages (the
        spot-stale notice, the SEEDING v3 heartbeat) don't reset each other's cadence."""
        now = time.time()
        if now - _seed_log_ts.get(key, 0.0) >= interval:
            _seed_log_ts[key] = now
            print(f"  [SEED] {msg}")

    def _seed_drop_all(reason):
        for key in [k for k, m in resting.items() if m.get("seeded")]:
            drop(key, reason)

    def _seed_rest_book(ticker, now_tick):
        """SEEDING v3: rate-limited (>=SEED_REST_POLL_MIN_S) REST orderbook fetch for the
        WS-unknown fallback. Reuses get_book_raw() (same public endpoint/session as get_book(),
        no new HTTP client). Caches the last successful fetch per ticker so calls inside the
        rate-limit window -- or a transient REST failure -- reuse it rather than treating a
        momentary blip as still 'no information'. Resets on ticker change (new window)."""
        if _seed_rest_cache["ticker"] != ticker:
            _seed_rest_cache["ticker"] = ticker
            _seed_rest_cache["ts"] = 0.0
            _seed_rest_cache["entry"] = None
        if now_tick - _seed_rest_cache["ts"] >= SEED_REST_POLL_MIN_S:
            _seed_rest_cache["ts"] = now_tick
            fetched = get_book_raw(sess, ticker)
            if fetched is not None:
                _seed_rest_cache["entry"] = fetched
        return _seed_rest_cache["entry"]

    def _seed_classify_book(now_tick):
        """SEEDING v3: WS-primary / REST-fallback book classification for THIS window's ticker.
        Returns (book_state, book_entry, rest_label):
          book_state  -- 'empty'/'one_sided'/'has_book'/'unknown' (seed_book_state's vocabulary;
                         'crumbs_only' is NOT resolved here -- that's the existing one_sided
                         fair-band refinement further down in _seed_tick, applied uniformly to
                         `book_entry` regardless of whether it came from WS or this fallback, so
                         classification stays single-sourced through seed_fair_band_state either
                         way).
          book_entry  -- the ws_entry-shaped dict to feed into seed_fair_band_state for that
                         refinement (the WS ws_state entry, or the REST-built one).
          rest_label  -- None when no REST fallback was attempted (WS answered definitively, or
                         'unknown' hasn't persisted past SEED_UNKNOWN_REST_AFTER_S yet); else the
                         REST fallback's own seed_book_state verdict, or 'unavailable' on a
                         transient REST failure (caller keeps treating the tick as 'unknown' --
                         no churn).
        WHY 'unknown' needs this at all: Kalshi's WS sends NO orderbook_snapshot message for a
        genuinely empty book, so ws_state[ticker] never materializes -- 'unknown' is structurally
        PERMANENT for that case, not a transient post-rollover gap (confirmed live 2026-07-12, run
        r29179923486: zero [SEED] lines across 4 windows on a REST-verified-empty book). The
        get_book_cached() call at _seed_tick's call site already found no two-sided book via REST
        before ever reaching here, so REST evidence of emptiness exists at every call -- this just
        fetches the FULL-depth book (get_book_cached collapses one-sided/empty to the same
        all-None result) so seed_book_state can tell them apart."""
        ticker = mk["cid"]
        ws_raw = seed_book_state(ws_state.get(ticker))
        if ws_raw != "unknown":
            _seed_unknown_since["ticker"] = None
            _seed_unknown_since["ts"] = None
            return ws_raw, ws_state.get(ticker), None
        if _seed_unknown_since["ticker"] != ticker:
            _seed_unknown_since["ticker"] = ticker
            _seed_unknown_since["ts"] = now_tick
        if not seed_unknown_persisted(_seed_unknown_since["ts"], now_tick):
            return "unknown", None, None
        rest_entry = _seed_rest_book(ticker, now_tick)
        if rest_entry is None:
            return "unknown", None, "unavailable"
        rest_state = seed_book_state(rest_entry)
        return rest_state, rest_entry, rest_state

    def _seed_tick(tau_left):
        """Empty-book seeding entry point. Called ONLY from the main loop's book-poll branch where
        the normal book-anchored path found no usable bb/ba (both REST and WS agree there is no
        two-sided book) -- see the call site below. Entirely self-contained: mirrors (does not
        share, so this stays independently testable/auditable) the --max-notional / --max-net /
        --max-fills-side / --max-rungs / gate_check rails the normal PLACE loop enforces, plus the
        module-level seed_book_state/seed_effective_width/seed_should_reprice/seed_target_cents
        helpers above for the empty-book-specific math. loss-limit and the rolling-markout kill are
        already enforced upstream of this call every tick (top of the main while-loop), so nothing
        extra is needed for those here.

        SEEDING v3 (REST fallback + heartbeat): book classification (_seed_classify_book) and the
        [SEED] heartbeat log both happen FIRST, unconditionally, before any of the cooldown/
        boundary/state early-returns below -- so the heartbeat fires every tick regardless of which
        branch this function ultimately takes, closing the silent-standdown gap that let a
        persistently-'unknown' empty book seed nothing for 46 minutes with zero log evidence."""
        if not a.seed_empty or mk is None:
            return
        now_tick = time.time()
        raw_state, book_entry, rest_label = _seed_classify_book(now_tick)
        resting_seeds = sum(1 for m in resting.values() if m.get("seeded"))
        disp_state = f"unknown(REST-fallback={rest_label})" if rest_label is not None else raw_state
        _seed_log_rl(f"state={disp_state} tau={tau_left:.0f}s resting_seeds={resting_seeds}",
                     key="heartbeat", interval=60.0)
        # AGGRESSOR-BURST COOLDOWN: seeding stays suppressed for --seed-burst-cooldown-s after a
        # --seed-burst-n trip (the trip itself -- detecting the burst + the immediate cancel-all --
        # happens fill-side, in book_fill(), since it must react the instant the Nth fill lands,
        # not wait for the next poll tick). Nothing should be resting here (book_fill's trip
        # handler already dropped it), but _seed_drop_all is idempotent, so make it a no-op guard
        # rather than trusting that invariant.
        if seed_burst_cooldown_active(seed_cooldown["tripped_at"], now_tick, a.seed_burst_cooldown_s):
            _seed_drop_all("seed_burst_cooldown")
            return
        # BOUNDARY DISCIPLINE: never seed inside the final --seed-tau-min-s of a window, and cancel
        # any resting seed quotes there -- same force-flatten discipline as every other rung, just
        # earlier (a sole-maker fill this late has no time left to find a natural pair).
        if tau_left < a.seed_tau_min_s:
            _seed_drop_all("seed_tau_guard")
            return
        if raw_state in ("has_book", "unknown"):
            # has_book: real two-sided market -- normal book-anchored PLACE loop handles it, and
            # any resting seed quotes are pulled the instant this is detected at the book-poll call
            # site (see 'seed_book_no_longer_empty' above _seed_tick's call). unknown: either a
            # brief WS gap right after rollover that hasn't yet crossed SEED_UNKNOWN_REST_AFTER_S,
            # or a persistent one where the REST fallback itself came back unavailable/still
            # two-sided -- neither is evidence the book is empty, so left alone rather than
            # churned (spec: REST 'has_book' or a transient REST failure behave as before).
            return
        # FAIR-BAND TRIGGER (--seed-fair-band): needs `fair` even for a merely 'one_sided' book now
        # (not just 'empty'), since seed_fair_band_state's crumbs-vs-real distinction is fair-
        # relative. _seed_spot_fair is internally rate-limited (>=1/s), so this adds no meaningful
        # extra cost on the 'one_sided' path.
        fair, sigma = _seed_spot_fair(tau_left)
        if fair is None:
            _seed_log_rl(f"spot feed unavailable/stale (>{a.seed_max_age_s:.0f}s) -- not seeding",
                         key="stale", interval=30.0)
            _seed_drop_all("seed_spot_stale")
            return
        fair_cents = fair * 100.0
        state = raw_state
        if raw_state == "one_sided":
            # `book_entry` is single-sourced by _seed_classify_book above: the WS ws_entry in the
            # normal case, or the REST-fallback ws_entry-shaped dict when WS stayed 'unknown' past
            # the threshold -- either way this is the SAME seed_fair_band_state call classifying
            # crumbs-vs-real quotes identically regardless of which feed produced the snapshot.
            state = seed_fair_band_state(book_entry, fair_cents, a.seed_fair_band)
            if state == "one_sided":
                # A REAL quote sits inside the fair band -- someone is actually making a market
                # here. Do NOT spot-seed: the normal book-anchored PLACE loop already knows how to
                # join a one-sided real market (anchor off the resting side), so spot-anchoring
                # here would just duplicate/fight that logic with a different pricing model. If we
                # were resting seed quotes, someone else just quoted inside us -- revert to normal
                # book-anchored behavior immediately.
                _seed_drop_all("seed_book_one_sided")
                return
            # else: 'crumbs_only' -- every resting order on this book sits outside the fair band
            # (e.g. the observed 2026-07-12 penny-crumb lottery bids at 0.001-0.003c vs a ~0.50
            # fair) and carries no informational content about where the market actually is.
            # QUALIFIES for spot-anchored seeding exactly like a literally-empty book.
        eff_width = seed_effective_width(a.seed_width, tau_left, sigma)
        # AGGRESSOR-BURST COOLDOWN, width doubling on resume: the first seed placement after a
        # cooldown lifts quotes at 2x the effective width (seed_cooldown["resumes"] is None until
        # the first-ever trip, so pre-trip behavior is byte-identical to before this feature).
        if seed_cooldown["resumes"] is not None:
            eff_width *= seed_burst_resume_width_mult(seed_cooldown["resumes"])
        # RE-PRICE DISCIPLINE: keep queue priority -- only cancel/re-post a seed quote if fair moved
        # more than half the CONFIGURED --seed-width since placement.
        for key, meta in list(resting.items()):
            if not meta.get("seeded"):
                continue
            if seed_should_reprice(fair_cents, meta.get("seed_fair_cents", fair_cents), a.seed_width):
                drop(key, "seed_reprice")
        yb_cents, ya_cents = seed_target_cents(fair, eff_width)
        seed_count = min(1, int(a.post))    # post-only 1-lot, but never exceed the configured --post
        if seed_count < 1:
            return
        placed_any = False
        for side, price in (("yes", round(yb_cents / 100.0, 4)),
                            ("no", round(1.0 - ya_cents / 100.0, 4))):
            key = (side, round(price, 4))
            if key in resting or reject_cd.get(key, 0.0) > time.time():
                continue
            if time.time() < side_cooldown[side]:
                continue
            if win_fills.get(side, 0) >= a.max_fills_side:
                continue
            if sum(1 for k in resting if k[0] == side) >= a.max_rungs:
                continue
            # inventory clamp (--max-net), worst-case projection (mirrors the main PLACE loop)
            sgn = 1.0 if side == "yes" else -1.0
            rest_same = sum(max(a.post - m.get("filled", 0.0), 0.0)
                            for (s_, _p), m in resting.items() if s_ == side)
            rest_same += sum(max(a.post - m.get("filled", 0.0), 0.0)
                             for (s_, _p), m in pending_cancel.items() if s_ == side)
            if abs(net_delta + sgn * (rest_same + seed_count)) > float(a.max_net) + 1e-9:
                continue
            # aggregate notional cap (--max-notional), same formula as the main PLACE loop
            open_buy_notional = sum(max(a.post - m.get("filled", 0.0), 0.0) * price_
                                    for (_, price_), m in resting.items())
            exposure = open_buy_notional + max(-cash, 0.0)
            if exposure + price * seed_count > a.max_notional:
                continue
            # AS gate (or whichever --gate is active): gate_check always returns False when
            # yes_bid/yes_ask are None (empty book -- nothing to be toxic against), so this is
            # provably a pass-through, not an exemption -- seeded quotes go through the SAME gate
            # call every other quote does.
            if gate_check(side, price, None, None, net_delta, a.gate, 0.0, 0.0, 0.0, tau_left=tau_left):
                continue
            res = place(side, price, None, None, count=seed_count, seeded=True)
            if res is None:
                continue
            if isinstance(res, tuple):
                oid, t_dec, t_ack = res
            else:
                oid = res; t_ack = time.time()
            resting[key] = {"oid": oid, "ts": t_ack, "filled": 0.0, "want": seed_count,
                            "mid0": None, "qahead": _queue_ahead_est(side, price),
                            "seeded": True, "seed_fair_cents": fair_cents,
                            "seed_width_used": eff_width}
            placed_any = True
            print(f"  [SEED] empty book -> {side.upper()} {seed_count}@{price:.4f} "
                  f"fair={fair_cents:.1f}c width={eff_width:.1f}c tau={tau_left:.0f}s"
                  f"{' state=' + state if state == 'crumbs_only' else ''}")
        # AGGRESSOR-BURST COOLDOWN, width doubling on resume: advance the resume counter only after
        # an actual placement -- seed_burst_resume_width_mult(0) applies once, then this bumps it
        # to 1 so the NEXT tick's placement decays back to normal width.
        if placed_any and seed_cooldown["resumes"] is not None:
            seed_cooldown["resumes"] += 1

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
        fid = str(f.get("trade_id") or f.get("fill_id") or "")
        _lifecycle_oid = (meta or {}).get("oid", fid)
        _lifecycle_qahead = (meta or {}).get("qahead")
        _is_seeded = bool((meta or {}).get("seeded"))
        if _is_seeded:
            # AUDIT (--seed-empty PRE-REGISTERED EVALUATION): this window's seeded-fill accumulator
            # -- mirrors the whole-window cash/pos_yes/pos_no bookkeeping above but scoped to fills
            # against seeded orders only, so seeded_net at settlement is computed the exact same way
            # (cash + pos*payout) just partitioned to the seeded subset.
            seed_win["n_fills"] += 1
            seed_win["cash"] -= fp * count
            if fside == "yes":
                seed_win["pos_yes"] += count
            else:
                seed_win["pos_no"] += count
            # AGGRESSOR-BURST COOLDOWN (--seed-burst-n/--seed-burst-cooldown-s): react to the burst
            # the instant the Nth fill lands (fill-triggered, not poll-triggered -- the whole point
            # is to cancel remaining seed quotes before more of them get picked off). Checked only
            # when not already in cooldown, so a trip can't re-trip itself / reset the resume
            # counter early while suppressed (no new seed quotes rest during cooldown anyway, so no
            # further seeded fills should occur here until it lifts).
            _now_fill = time.time()
            seed_fill_times.append(_now_fill)
            while seed_fill_times and _now_fill - seed_fill_times[0] > 60.0:
                seed_fill_times.pop(0)
            if not seed_burst_cooldown_active(seed_cooldown["tripped_at"], _now_fill,
                                              a.seed_burst_cooldown_s):
                if seed_burst_should_trip(seed_fill_times, _now_fill, a.seed_burst_n, 60.0):
                    _fills_in_burst = seed_burst_fill_count(seed_fill_times, _now_fill, 60.0)
                    _seed_drop_all("seed_burst_cooldown")
                    seed_cooldown["tripped_at"] = _now_fill
                    seed_cooldown["resumes"] = 0
                    seed_cooldown_win["n"] += 1
                    _lifecycle_write_seed_cooldown(_fills_in_burst)
                    print(f"  [SEED] burst cooldown TRIP: {_fills_in_burst} fills in 60s -> "
                          f"cancel remaining seed quotes, suppress seeding for "
                          f"{a.seed_burst_cooldown_s:.0f}s")
        if meta:
            meta["filled"] = meta.get("filled", 0.0) + count
            _full = meta["filled"] >= meta.get("want", a.post) - 1e-9   # AUDIT M5: per-order size, not global post
            if _full:
                resting.pop(key, None)
            _lifecycle_write("fill" if _full else "partial", _lifecycle_oid, fside, fp, count,
                             _lifecycle_qahead, seeded=_is_seeded)
        else:
            # no resting-meta match (e.g. a taker/cross completion fill, or a race where the local
            # order already dropped): still a genuine fill, log it without queue-ahead context.
            _lifecycle_write("fill", _lifecycle_oid, fside, fp, count, None, seeded=_is_seeded)
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
            # PORTFOLIO-AWARE SIZING: refresh PortfolioState (opt-in --portfolio-aware; no-op and
            # zero cost when off). Internally rate-limited to --port-refresh-s; safe to call every
            # loop tick.
            _port_refresh_if_due()

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
                    # snapshot this window's recon telemetry BEFORE it resets below (ops/win_fills/
                    # winrec all reset a few lines down at rollover)
                    _recon_requested = ops["place"]
                    _recon_fills = win_fills["yes"] + win_fills["no"]
                    _recon_invmax = winrec["maxnet"]
                    if pos or abs(cash) > 1e-9:
                        entry = {
                            "cid": mk["cid"], "ws": mk["ws"],
                            "pos_yes": sum(v for k, v in pos.items() if k.endswith(":YES")),
                            "pos_no":  sum(v for k, v in pos.items() if k.endswith(":NO")),
                            "cash": cash, "r": r_now, "t0": time.time(),
                            # carried through to the settle block below for _recon_write (fills>0 here)
                            "recon_requested": _recon_requested, "recon_fills": _recon_fills,
                            "recon_invmax": _recon_invmax,
                            # AUDIT (--seed-empty): snapshot of THIS window's seeded-fill accumulator,
                            # carried through to settlement so seeded_net can be computed the same way
                            # (cash + pos*payout) at the same time as the whole-window pnl.
                            "seed": dict(seed_win),
                            # AUDIT (AGGRESSOR-BURST COOLDOWN): THIS window's cooldown-trip count,
                            # carried through to settlement -> _recon_write's n_seed_cooldowns.
                            "n_seed_cooldowns": seed_cooldown_win["n"],
                        }
                        pending_settles.append(entry)
                    else:
                        # no activity this window (no fills => no cash spent, no position held) ->
                        # net/gross are trivially $0; write the recon row now (no settlement to await).
                        # (pos empty implies seed_win is also empty -- every fill, seeded or not,
                        # adds to pos -- so n_seeded_fills/seeded_net/n_seed_cooldowns are trivially
                        # 0/0.0/0 here too: a burst trip requires >=1 seeded fill.)
                        _recon_write(mk["ws"], _recon_requested, _recon_fills, 0.0, 0.0, _recon_invmax,
                                    n_seed_cooldowns=seed_cooldown_win["n"])
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
                    seed_win = {"n_fills": 0, "cash": 0.0, "pos_yes": 0.0, "pos_no": 0.0}
                    seed_cooldown_win = {"n": 0}   # reset THIS window's cooldown-trip counter; the
                    # cooldown state itself (seed_cooldown: tripped_at/resumes) is NOT window-scoped
                    # -- a 120s cooldown can span a rollover, so it persists independently.
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

                # DEADMAN_AUDIT.md fix #2: apply the startup-inherited venue position (if any)
                # exactly once, the FIRST time this session attaches to a window -- only relevant
                # when that window is the SAME ticker the startup positions query filtered to
                # (init_mk["cid"]); if the window rolled between the startup query and here (a
                # narrow race), we deliberately do NOT misattribute the old ticker's inventory to
                # a new one -- seeding is skipped and the Telegram alert already sent above is
                # the record of it. pos/net_delta/win_cost are seeded exactly as book_fill() would
                # book a real fill, so every downstream risk clamp and the existing dispose-cross/
                # chase-unpaired/close-force machinery treats it like any position opened this
                # session -- no separate handling needed.
                if not _inherited_seed_done:
                    _inherited_seed_done = True
                    if _inherited and init_mk and mk["cid"] == init_mk["cid"]:
                        _ih_side = _inherited["side"]; _ih_ct = _inherited["count"]
                        _ih_pk = mk["cid"] + ":" + _ih_side.upper()
                        pos[_ih_pk] = pos.get(_ih_pk, 0.0) + _ih_ct
                        net_delta += _ih_ct if _ih_side == "yes" else -_ih_ct
                        win_cost[_ih_side] = win_cost.get(_ih_side, 0.0) + _inherited["cost"]
                        print(f"[startup] seeded inherited position into risk state: "
                              f"net_delta={net_delta:+.0f} pos[{_ih_pk}]={pos[_ih_pk]:.0f} "
                              f"win_cost[{_ih_side}]={win_cost[_ih_side]:.2f}")

                _last_book_cache.clear()
                # Update WS feeder subscription: new ticker + bump epoch so feeder resubscribes
                ws_sub["ticker"] = mk["cid"]
                ws_sub["epoch"] += 1
                print(f"WINDOW {mk['ws']} {datetime.fromtimestamp(mk['ws'], timezone.utc):%H:%M}Z "
                      f"ticker={mk['cid']}")

                # --seed-empty: anchor SpotFair's S0 at this window's open (mirrors
                # kalshi_collect.KalshiMarket.discover's own fv.update()/set_window pattern).
                # Invalidate the PREVIOUS window's anchor synchronously (cheap, no network -- using
                # a stale S0 would silently mis-price the fair for the whole new window) but do the
                # actual spot fetch off-thread, same pattern as the next-window prefetch just above:
                # this rollover path is the queue-priority-sensitive one (zero-RTT rollover comment
                # above) for EVERY window, seeded or not, so it must never block on a spot HTTP call.
                if a.seed_empty and seed_fv is not None:
                    seed_fv.s0 = None
                    def _seed_anchor(ws_open=mk["ws"]):
                        try:
                            sp = seed_fv.update()
                            if sp and time.time() - ws_open <= 60:
                                seed_fv.set_window(sp)
                        except Exception:
                            pass
                    threading.Thread(target=_seed_anchor, daemon=True).start()

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
                # --seed-empty: a two-sided book exists again (get_book_cached only returns non-None
                # bb/ba for a genuinely two-sided book -- see _seed_book_state's docstring). Any
                # resting seed quotes' spot-anchored rationale is gone the instant that's true --
                # pull them immediately rather than waiting for the generic reshape grace period
                # (spec: "someone else quoted inside us -> revert to normal book-anchored behavior
                # immediately"). The normal PLACE loop below then re-quotes off the real book as usual.
                if a.seed_empty and any(m.get("seeded") for m in resting.values()):
                    _seed_drop_all("seed_book_no_longer_empty")
            else:
                if a.seed_empty:
                    _seed_tick(max(mk["we"] - time.time(), 0.0))
                time.sleep(a.react_poll); continue

            # CLAMP-LEAK FIX (audit H1): book EVERY known WS fill into net_delta BEFORE any placement
            # decision this loop. Previously fills were drained only on the ~1s housekeeping tick (after
            # placement), so two same-side orders could both fill against a stale net_delta -> |net|>=2
            # (12/56 windows pre-fix). Draining here makes the inventory clamp act on current inventory.
            drain_ws_fills()

            # OVER-FILL RESIDUAL GUARD (BOX_COMPLETION_EXEC.md): a completion just returned inventory to
            # FLAT -> cancel resting OPENING rungs so a stale same-side ladder rung can't fill unpartnered
            # 1-3s later and ride naked to ~-50c (14/16 live toxic strands were these). The freeze on NEW
            # opens is applied below (targets). Completing quotes only exist at net!=0 and are untouched.
            if (a.post_complete_freeze > 0 and abs(prev_net_freeze) > 1e-9
                    and abs(net_delta) <= 1e-9):
                last_complete_ts = time.time()
                for _k in list(resting):
                    drop(_k, "post_complete_freeze")
            prev_net_freeze = net_delta

            # --- compute desired levels (both YES and NO views) ---
            # Own-size exclusion (A2): subtract our resting size at the touch from the depth
            # so the microprice reflects other traders' imbalance only (mirrors live_trader's own_b/own_a).
            own_yes = sum(a.post for k in resting if k[0] == "yes" and abs(k[1] - ybb) < 1e-9)
            own_no  = sum(a.post for k in resting if k[0] == "no"  and abs(k[1] - round(1.0 - yba, 4)) < 1e-9)
            clean_ybq = max((ybq or 0.0) - own_yes, 0.0)
            clean_yaq = max((yaq or 0.0) - own_no,  0.0)
            mp = microprice(ybb, yba, clean_ybq, clean_yaq)

            targets = desired_levels(mk, ybb, yba, net_delta, 1, a.cap, a.skew, a.improve_tick)
            # post-completion freeze: hold off NEW opens for a beat after a box completes (net==0 means
            # every target is an opening rung; completing quotes live at net!=0 and are never frozen).
            if (a.post_complete_freeze > 0 and abs(net_delta) <= 1e-9
                    and (time.time() - last_complete_ts) < a.post_complete_freeze):
                targets = []
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
            # PAIR-OR-DONT-PLAY gate (audit 2026-06-14): the edge is intact on PAIRED boxes (+0.69c);
            # the entire loss is STRANDS. So only OPEN a box when BOTH legs are likely to pair: a
            # BALANCED book (microprice near mid -- not being swept one way) AND DEPTH on both the bid
            # and ask we'd join. Imbalanced/thin books are where one leg fills and the other strands.
            # Suppress OPENS when the book is imbalanced or thin; COMPLETIONS are always exempt.
            if a.pair_gate and net_delta == 0:    # only gates fresh opens (net!=0 -> only completes anyway)
                # DEPTH is the dominant strand predictor (pair_gate study): min(top-5 both-side depth)
                # >= --pair-min-depth. Deep balanced books pair both legs; thin books strand one. The
                # study found microprice-DIVERGENCE gates KILL the edge, so we gate on DEPTH only.
                d5 = top5_both_depth(ws_state, mk["cid"])
                if d5 is None or d5 < a.pair_min_depth:
                    targets = []      # no depth (or thin) -> don't open; wait for a deep, fillable book
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
                if mp is not None and gate_check(side, price, ybb, yba, net_delta, a.gate, 0.0, clean_ybq, clean_yaq, tau_left=tau_left):
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
                elif a.size_mode == "depth":
                    # DEPTH-PROPORTIONAL sizing (capacity+optimize studies 2026-06-14): on the pair-gated
                    # clean-box regime, size ~ available both-side depth captures the ~$27/day ceiling
                    # vs the unit-size floor (net/win up to +2.3c, IS/OOS-stable). Bounded by --depth-size-cap
                    # contracts AND the existing --max-notional / --max-net caps below. Only meaningful once
                    # --max-notional is raised (at the live $5 cap the notional cap binds first).
                    d5 = top5_both_depth(ws_state, mk["cid"])
                    if d5:
                        units = max(1, min(int(a.depth_size_cap), int(round(a.depth_size_frac * d5))))
                # AUDIT M1: the inventory clamp above reserved only `post`; cap units so units*post can
                # NOT breach --max-net in a single fill (else size-mode kelly silently overshoots |net|).
                _sgn = 1.0 if side == "yes" else -1.0
                if a.size_mode == "markout":
                    # 32-day shadow A/B winner (+1.88c/win, t=+5.76; MAKEREDGE.md #3, ported verbatim
                    # from shadow_compare.py's _size 'markout' branch, incl. MO_K): scale size
                    # continuously by micro-favorability -- UP quoting away from the microprice
                    # (benign), toward 0 when adverse. Same edge sign convention as gate=="as" above.
                    fav = 0.0 if mp is None else (
                        (mp - price) if side == "yes" else (round(1.0 - price, 4) - mp))
                    mo_mult = min(max(1.0 + MO_K * fav, 0.0), 2.0)   # clamp [0, 2x] (shadow-validated)
                    want = int(round(a.post * mo_mult))
                    # never bypass the --max-net clamp: shed contracts one at a time (same rule as
                    # the AUDIT M1 units clamp above, just applied to a continuous want).
                    while want > 0 and abs(net_delta + _sgn * want) > float(a.max_net) + 1e-9:
                        want -= 1
                    # never bypass --max-notional: the C8 check above only reserved a.post; markout can
                    # size up to 2x --post, so re-check against the ACTUAL want before placing.
                    if want > 0 and exposure + price * want > a.max_notional:
                        want = 0
                    if want <= 0:
                        continue
                else:
                    while units > 1 and abs(net_delta + _sgn * units * int(a.post)) > float(a.max_net) + 1e-9:
                        units -= 1
                    want = units * int(a.post)

                # PORTFOLIO-AWARE SIZING (opt-in --portfolio-aware; OFF by default -> this whole
                # block is skipped and `want`/place() below are BYTE-IDENTICAL to pre-existing
                # behavior). Composes MULTIPLICATIVELY onto whatever size path (flat/kelly/depth/
                # markout) just picked `want`, integer-rounds, THEN re-applies the exact same hard
                # rails those paths already enforce above (max-net contract-by-contract shed +
                # notional pre-check -- same pattern commit 67c6cb70's markout sizing used) so this
                # can only ever SHRINK want, never let it slip past --max-net/--max-notional.
                port_mult = None
                if a.portfolio_aware:
                    pmb, pmd = _port_multipliers(side, want, net_delta)
                    want = int(round(want * pmb * pmd))
                    while want > 0 and abs(net_delta + _sgn * want) > float(a.max_net) + 1e-9:
                        want -= 1
                    if want > 0 and exposure + price * want > a.max_notional:
                        want = 0
                    if want <= 0:
                        continue
                    port_mult = (pmb, pmd)

                res = place(side, price, ybb, yba, count=want, port_mult=port_mult)
                if res is None:
                    continue
                if isinstance(res, tuple):
                    oid, t_dec, t_ack = res
                else:
                    oid = res; t_ack = time.time()
                resting[key] = {"oid": oid, "ts": t_ack, "filled": 0.0, "want": want,
                                "mid0": loop_ctx.get("mid"), "qahead": _queue_ahead_est(side, price)}

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
                    # GIVE-CAPPED disposal (audit 2026-06-14): cross when CHEAP (lock>=-give, the
                    # opportunistic/early path) OR when forcing near close BUT only up to --dispose-max-give.
                    # If even the forced completion would lock worse than the cap (book ran far away), HOLD
                    # the bounded leg instead -- a -22c expected hold beats a -83c catastrophic cross
                    # (the force-at-ANY-price fix overpaid: it created the -16.4c/box crossed-completion leak).
                    cross_ok = (lock >= -give - 1e-9) or (force and lock >= -a.dispose_max_give - 1e-9)
                    if (0.0 < cross_px < 1.0 and need >= 1 and cross_ok
                            and reject_cd.get(ckey, 0.0) <= time.time()):
                        if place(cside, cross_px, ybb, yba, count=take, cross=True) is not None:
                            ops["dispose_cross"] = ops.get("dispose_cross", 0) + 1
                            winrec["dispose_cross"] += 1
                            print(f"  [DISPOSE-CROSS{'/FORCE' if force else ''}] {take}/{need}x "
                                  f"{cside.upper()} @ {cross_px:.4f} lock={lock:+.3f} "
                                  f"(age={age_unp:.0f}s tau={tau_left:.0f}s)")
                        reject_cd[ckey] = time.time() + (0.8 if (force or take < need) else 3.0)
                    elif force and lock < -a.dispose_max_give:
                        # bounded HOLD: crossing would cost more than the cap; ride the (capped) leg
                        if reject_cd.get(ckey, 0.0) <= time.time():
                            print(f"  [HOLD-CAPPED] {cside.upper()} cross lock={lock:+.3f} < -{a.dispose_max_give:.2f} "
                                  f"cap; holding bounded leg vs catastrophic cross (tau={tau_left:.0f}s)")
                            reject_cd[ckey] = time.time() + 5.0

            # --- PULL stale / toxic / off-target rungs ---
            for key in list(resting):
                side, price = key
                # Toxicity gate: pull if microprice crossed this rung (same ufat logic as live_trader)
                if mp is not None and gate_check(side, price, ybb, yba, net_delta, a.gate, 0.0, clean_ybq, clean_yaq, tau_left=tau_left):
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

            # ORDER-LIFECYCLE: TTL EXPIRE detection (observational only -- does NOT touch `resting`/
            # trading state; every other path here already reshapes on-target rungs well inside
            # --order-ttl-s under normal operation, so this fires only in the edge case an on-target
            # rung sits untouched long enough for the venue-side TTL dead-man to self-cancel it,
            # which local bookkeeping would otherwise never learn about until the next fill/cancel).
            if a.order_ttl_s and a.order_ttl_s > 0:
                for key, meta in resting.items():
                    if meta.get("_lifecycle_expired"):
                        continue
                    if (time.time() - meta["ts"]) >= a.order_ttl_s:
                        meta["_lifecycle_expired"] = True
                        _rem = max(meta.get("want", a.post) - meta.get("filled", 0.0), 0.0)
                        _lifecycle_write("expire", meta.get("oid"), key[0], key[1], _rem,
                                        meta.get("qahead"), seeded=bool(meta.get("seeded")))

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
                    # AUDIT (--seed-empty PRE-REGISTERED EVALUATION): seeded fills settle exactly like
                    # any other fill (same $1/$0 payout) -- compute their slice of pnl the same way,
                    # scoped to the seed_win snapshot captured at rollover.
                    _sw = en.get("seed") or {}
                    _swn = int(_sw.get("n_fills", 0))
                    _sw_cd = int(en.get("n_seed_cooldowns", 0))
                    if r2 == "void" and time.time() - en.get("t0", 0) >= 20:
                        # voided/cancelled market: cash comes back, no P&L
                        realized += 0
                        print(f"  [VOID] ws={en['ws']} market voided; cash returned, no P&L")
                        _recon_write(en["ws"], en.get("recon_requested", 0), en.get("recon_fills", 0),
                                    0.0, 0.0, en.get("recon_invmax", 0.0),
                                    n_seeded_fills=_swn, seeded_net=0.0, n_seed_cooldowns=_sw_cd)
                        seen_fills.pop(en["cid"], None)
                    elif r2 is not None and time.time() - en.get("t0", 0) >= 20:
                        # settle: YES pays $1 if r2==1, NO pays $1 if r2==0
                        pnl = (en["cash"]
                               + en["pos_yes"] * (1.0 if r2 == 1 else 0.0)
                               + en["pos_no"]  * (1.0 if r2 == 0 else 0.0))
                        realized += pnl
                        print(f"  [SETTLE] ws={en['ws']} r={r2} pnl={pnl:+.4f} realized={realized:+.2f}")
                        seeded_pnl = ((_sw.get("cash", 0.0)
                                      + _sw.get("pos_yes", 0.0) * (1.0 if r2 == 1 else 0.0)
                                      + _sw.get("pos_no", 0.0) * (1.0 if r2 == 0 else 0.0))
                                     if _swn > 0 else 0.0)
                        if _swn > 0:
                            print(f"  [SEED] ws={en['ws']} seeded_fills={_swn} seeded_pnl={seeded_pnl:+.4f}")
                        # LIVE-VS-SHADOW reconciliation row (CRYPTO15M maker fee is $0, confirmed on
                        # every live fill -- gross == net here; kept as separate fields to match the
                        # shadow schema in case that assumption ever breaks, see the FEE TRIPWIRE above).
                        _recon_write(en["ws"], en.get("recon_requested", 0), en.get("recon_fills", 0),
                                    pnl, pnl, en.get("recon_invmax", 0.0),
                                    n_seeded_fills=_swn, seeded_net=seeded_pnl, n_seed_cooldowns=_sw_cd)
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
