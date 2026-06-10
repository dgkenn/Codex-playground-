"""kalshi_trader.py -- Kalshi execution adapter: port of live_trader.py's OMS/safety rails.

Passive 2-sided maker on KX{BTC,ETH,SOL,XRP}15M. Every live_trader.py safety rail is mirrored:
dead-man, loss-limit (STICKY sentinel), rolling-markout kill, post_only-only, aggregate notional
cap, startup reconciliation (fail-closed), venue reconciliation sweep, fill polling, window rollover
with next-window prefetch, and pending settle retry with >=20s grace.

    python kalshi_trader.py                              # DRY-RUN (discovers, prints DRY place lines)
    I_UNDERSTAND_REAL_MONEY=yes python kalshi_trader.py --live --max-notional 25

Auth: API key id + RSA-PSS SHA-256 (cryptography library). No EIP-712.
One physical book (YES/NO views). buy YES = bid; buy NO = ask side. Action always "buy".
TODO: replace REST book polling with auth'd WebSocket when available.
"""
from __future__ import annotations

import argparse
import atexit
import base64
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
MICRO_MARGIN = 0.002   # p-adaptive toxicity margin (same constant as live_trader)

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


def place_order(sess, private_key, ticker, side, price_dollars, count, client_oid=None):
    """POST /portfolio/orders (action=buy, post_only=True). Returns order_id or None (NOT PLACED)."""
    coid = client_oid or str(uuid.uuid4())
    body = {
        "ticker": ticker,
        "client_order_id": coid,
        "side": side,
        "action": "buy",
        "count": int(count),
        "type": "limit",
        f"{side}_price_dollars": f"{price_dollars:.4f}",
        "post_only": True,
        "expiration_ts": None,
    }
    body = {k: v for k, v in body.items() if v is not None}
    sc, resp = _api(sess, private_key, "POST", "/portfolio/orders", body=body)
    if sc < 200 or sc >= 300 or resp is None:
        return None
    oid = (resp.get("order") or {}).get("order_id")
    return str(oid) if oid else None


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
    ap.add_argument("--improve-tick", type=float, default=0.01,
                    help="one tick inside the touch (1c); set 0.001 only if/where the venue accepts sub-cent")
    ap.add_argument("--gate", choices=["ufat", "micro", "marg"], default="ufat")
    ap.add_argument("--max-notional", type=float, default=25)
    ap.add_argument("--loss-limit", type=float, default=5)
    ap.add_argument("--poll", type=float, default=1.0, help="housekeeping cadence (s): fills+balance+settles")
    ap.add_argument("--react-poll", type=float, default=0.25, help="book polling cadence (s)")
    ap.add_argument("--duration", type=int, default=3600)
    ap.add_argument("--deadman-s", type=float, default=15.0,
                    help="book stale this many seconds -> cancel-all")
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

    lm = LiveMetrics(a.asset, 15, path=f"live_metrics_kalshi_{a.asset}15m.jsonl")

    # C7 startup reconciliation: cancel all open orders on this series so we start from a provably
    # flat book. A SIGKILL'd predecessor's orders would otherwise rest blind. Fail-closed: if we
    # can't verify flat, don't trade.
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

    print(f"[{mode}] kalshi_trader asset={a.asset} post={a.post} cap={a.cap} skew={a.skew} "
          f"max_rungs={a.max_rungs} gate={a.gate} max_notional={a.max_notional} "
          f"loss_limit={a.loss_limit} improve_tick={a.improve_tick}")
    notify.alert(f"[kalshi] trader start {mode} asset={a.asset} cap={a.cap}")

    # --- state ---
    mk = None
    net_delta = 0.0          # YES positions - NO positions (signed)
    realized = 0.0           # settled P&L across closed windows
    window_mark = 0.0        # current window mark-to-mid (open position value)
    pos = {}                 # ticker+"YES"|"NO" -> contracts held (from fills)
    cash = 0.0               # net cash flow this window (positive = received)
    resting = {}             # (side, price) -> {"oid", "ts"}  for THIS window
    placed_oids = set()      # every order_id placed this session
    seen_fills = {}          # ticker -> set of fill "trade_id" already booked
    markouts = []            # rolling 5s markout list (last 500)
    pending_settles = []     # [{"cid","ws","pos_yes","pos_no","cash","r","t0"}]
    pending_markouts = []    # [(due_ts, fill_dict)]
    next_mk = {"mk": None, "tried_we": 0}   # prefetched next-window market

    last_book_ok = time.time()
    deadman_tripped = False
    consec_err = 0
    last_hk = 0.0
    last_reconcile = 0.0
    mo_fh = open("kalshi_markout.jsonl", "a")

    # --- cancel / dead-man infrastructure ---
    cancel_q = []   # [(oid, key, reason)] queued this pass (batched like live_trader.flush_cancels)

    def drop(key, reason):
        """Queue a cancel without sending yet (batched in flush_cancels)."""
        meta = resting.pop(key, None)
        if meta is None:
            return
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
                if not ok2:
                    print(f"  [CANCEL-FAIL] {oid[:16]} key={key} reason={reason}")
                    ok = False
            else:
                print(f"  [DRY cancel] key={key} reason={reason}")
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
            notify.alert_sync(f"[kalshi] DEAD-MAN {reason}: cancel-all")
        except Exception as e:
            print(f"[DEAD-MAN] cancel failed: {str(e)[:120]}")

    atexit.register(lambda: _flatten_and_exit("process exit"))
    for _sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(_sig, lambda *_, s_=_sig: (_flatten_and_exit(f"signal {s_}"), os._exit(0)))
        except Exception:
            pass

    # --- place helper ---
    def place(side, price, yes_bid, yes_ask):
        """Post one rung. Returns order_id or None. DRY-RUN: prints, returns fake id.
        side='yes'|'no'. price in dollars (up to 4 decimals).
        Post-only guard: we only ever place buy orders; Kalshi's post_only=True rejects
        if marketable. Belt-and-suspenders: also check that a BUY-YES at price < yes_ask
        and BUY-NO at price < (1-yes_bid) before sending."""
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
            print(f"  [DRY place] BUY-{side.upper()} {a.post} @ {price:.4f}")
            return fake, t_dec, time.time()
        oid = place_order(sess, priv, mk["cid"], side, price, a.post)
        t_ack = time.time()
        if oid is None:
            lm.place_reject(side, price, "no order_id from venue")
            return None
        placed_oids.add(oid)
        lm.place_ack(side, price, False, (t_ack - t_dec) * 1e3)
        return oid, t_dec, t_ack

    # --- book polling (REST; no WS in v1) ---
    _last_book_cache = {}   # ticker -> (ts, yes_bid, ybq, yes_ask, yaq)
    _book_rest_throttle = 0.0

    def get_book_cached(ticker, max_age=None):
        """Throttled REST book poll. Returns (yes_bid, ybq, yes_ask, yaq, fresh).
        fresh=True only when the REST poll inside this call succeeded."""
        max_age = max_age or a.react_poll
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
    def poll_fills():
        """Pull /portfolio/fills scoped to mk['cid'] and book into pos/cash/net_delta.
        Mirrors live_trader's housekeeping fill poll."""
        nonlocal cash, net_delta
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
            fside = str(f.get("side") or "").lower()    # "yes" or "no"
            count = float(f.get("count_fp") or f.get("count") or 0)
            # H-3: prefer yes_price_dollars; if only yes_price and > 1.0, divide by 100
            yp_raw = f.get("yes_price_dollars")
            from_cents = False
            if yp_raw is None:
                yp_raw = f.get("yes_price")
                from_cents = True
            if yp_raw is None or count <= 0 or fside not in ("yes", "no"):
                sf.add(fid)
                continue
            yp = float(yp_raw)
            if from_cents and yp > 1.0:
                yp /= 100
            fp = yp if fside == "yes" else round(1.0 - yp, 4)
            # H-3 sanity guard: skip fills with price outside (0, 1)
            if not (0.0 < fp < 1.0):
                print(f"[FILL-AMBIGUOUS] fill {fid} has price {fp} outside (0,1); skipping")
                sf.add(fid)
                continue
            # inventory bookkeeping: BUY-YES adds +1 net, BUY-NO adds -1 net
            sgn = 1.0 if fside == "yes" else -1.0
            pos_key = ticker + ":" + fside.upper()
            pos[pos_key] = pos.get(pos_key, 0.0) + count
            cash -= fp * count               # buy spends cash
            net_delta += sgn * count
            key = (fside, round(fp, 4))
            meta = resting.get(key)
            resting_s = (time.time() - meta["ts"]) if meta else None
            if meta:
                meta["filled"] = meta.get("filled", 0.0) + count
                if meta["filled"] >= a.post - 1e-9:
                    resting.pop(key, None)
            pending_markouts.append((time.time() + 5.0, {
                "fside": fside, "fp": fp, "count": count,
                "resting_s": resting_s, "oid": (meta or {}).get("oid", fid)}))
            lm.fill(fside, fp, count, resting_s, None, "taker" if f.get("is_taker") else "maker", None, 0.0)
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
                    pos.clear(); cash = 0.0; net_delta = 0.0; window_mark = 0.0

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

            # C2 LOSS-LIMIT: realized + open window mark (same double-component check as live_trader)
            if realized + window_mark <= -abs(a.loss_limit):
                print(f"KILL: realized {realized:+.2f} + mark {window_mark:+.2f}. cancel-all + exit.")
                notify.alert(f"[kalshi] KILL loss-limit (real {realized:+.2f} mark {window_mark:+.2f})")
                _record_kill(f"loss_limit realized={realized:+.2f} mark={window_mark:+.2f}")
                cancel_all_resting(reason="loss_limit"); break

            # Rolling markout kill (same threshold as live_trader)
            if len(markouts) >= 30 and sum(markouts[-30:]) / 30 < -0.01:
                print("KILL: rolling markout toxic. cancel-all + exit.")
                notify.alert("[kalshi] KILL markout toxic")
                _record_kill("toxic_markout")
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

            # --- compute desired levels (both YES and NO views) ---
            # Own-size exclusion (A2): subtract our resting size at the touch from the depth
            # so the microprice reflects other traders' imbalance only (mirrors live_trader's own_b/own_a).
            own_yes = sum(a.post for k in resting if k[0] == "yes" and abs(k[1] - ybb) < 1e-9)
            own_no  = sum(a.post for k in resting if k[0] == "no"  and abs(k[1] - round(1.0 - yba, 4)) < 1e-9)
            clean_ybq = max((ybq or 0.0) - own_yes, 0.0)
            clean_yaq = max((yaq or 0.0) - own_no,  0.0)
            mp = microprice(ybb, yba, clean_ybq, clean_yaq)

            targets = desired_levels(mk, ybb, yba, net_delta, 1, a.cap, a.skew, a.improve_tick)
            target_set = set(targets)

            # --- PLACE missing rungs ---
            for side, price in targets:
                key = (side, round(price, 4))
                if key in resting:
                    continue
                # Toxicity gate: skip placing if microprice says this side is adverse
                if mp is not None and gate_check(side, price, ybb, yba, net_delta, a.gate, 0.0, clean_ybq, clean_yaq):
                    continue
                # C8 aggregate notional cap (BUY side only; both YES and NO are buys)
                open_buy_notional = sum(price_ * a.post for (_, price_), _ in
                                        ((k, m) for k, m in resting.items()))
                exposure = open_buy_notional + max(-cash, 0.0)
                if exposure + price * a.post > a.max_notional:
                    continue
                # Side ladder rung cap
                if sum(1 for k in resting if k[0] == side) >= a.max_rungs:
                    continue
                res = place(side, price, ybb, yba)
                if res is None:
                    continue
                if isinstance(res, tuple):
                    oid, t_dec, t_ack = res
                else:
                    oid = res; t_ack = time.time()
                resting[key] = {"oid": oid, "ts": t_ack, "filled": 0.0}

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
                    if age >= 2.0:   # min-rest-s equivalent: don't churn fresh orders (P2)
                        drop(key, "reshape")

            # Rung cap: evict rungs farthest from touch if over max_rungs
            for side, touch in (("yes", ybb), ("no", round(1.0 - yba, 4))):
                ks = [k for k in resting if k[0] == side]
                if len(ks) > a.max_rungs:
                    ks.sort(key=lambda k: abs(k[1] - touch))
                    for k in ks[a.max_rungs:]:
                        drop(k, "rung_cap")

            flush_cancels()   # ONE pass for all queued cancels this tick

            # ----------------------------------------------------------------
            # HOUSEKEEPING (--poll cadence): fills, markouts, reconciliation, settles
            # ----------------------------------------------------------------
            if hk:
                if live:
                    poll_fills()
                    poll_balance_lm()

                # Score due 5s markouts
                now_mo = time.time()
                due = [pm for pm in pending_markouts if pm[0] <= now_mo]
                pending_markouts[:] = [pm for pm in pending_markouts if pm[0] > now_mo]
                for due_t, f in due:
                    try:
                        ybb2, _, yba2, _, _fresh2 = get_book_cached(mk["cid"], max_age=0.1)
                    except Exception:
                        pending_markouts.extend([(due_t, f)])
                        break
                    if ybb2 is None or yba2 is None or now_mo - due_t > 60:
                        continue
                    mid2 = (ybb2 + yba2) / 2.0
                    mo = (mid2 - f["fp"]) if f["fside"] == "yes" else ((1.0 - mid2) - f["fp"])
                    markouts.append(mo); del markouts[:-500]
                    mo_fh.write(json.dumps({
                        "ts": time.time(), "asset": a.asset, "side": f["fside"],
                        "price": f["fp"], "count": f["count"], "markout": mo,
                        "net_delta": net_delta}) + "\n")
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
            time.sleep(a.react_poll)

        except KeyboardInterrupt:
            _flatten_and_exit("KeyboardInterrupt")
            print("interrupted; cancelled all.")
            break
        except Exception as e:
            consec_err += 1
            print(f"[warn] {str(e)[:100]} (consec_err={consec_err})")
            if live and resting and consec_err >= 5 and not deadman_tripped:
                # C1 error-storm dead-man: 5 consecutive errors -> can't trust state, pull everything
                print("[DEAD-MAN] error storm -> cancel-all")
                notify.alert("[kalshi] DEAD-MAN error storm: cancel-all")
                cancel_all_resting(reason="deadman_errors")
                deadman_tripped = True
            time.sleep(a.poll)

    _flatten_and_exit("loop end")
    print(f"done. realized={realized:+.2f} net_delta={net_delta:+.1f} "
          + (f"avg_markout={sum(markouts)/len(markouts):+.5f}" if markouts else "no markouts"))


if __name__ == "__main__":
    main()
