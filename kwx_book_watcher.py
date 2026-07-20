#!/usr/bin/env python3
"""kwx_book_watcher.py -- EVENT-DRIVEN ask watcher for K-WX, filling the gap between obs polls.

WHY: kwx_runner.poll_once() only looks at asks once per obs-poll cycle (adaptive 5s-15min). The
mechanical-lock edge decays with a ~3.3-min half-life (KWX_DEPLOY.md), and a transient ask that flashes
between polls is never seen -- kwx_runner.NEAR_MISS_LOG shows almost everything already repriced to
99/100 by the time the next poll looks. This module watches ONLY the small "hot set" of rungs poll_once
already identified this cycle (locked-but-unbuyable misses, plus rungs about to lock) and fires the
instant a hot LOCKED rung's ask drops back into range -- through the EXACT SAME guarded fire path
(kwx_runner.fire_one) poll_once itself uses. It never bypasses a guard and never fires a rung on price
alone unless kwx_runner already determined it is LOCKED (lock status only changes on an obs poll).

Transport: Kalshi WebSocket (orderbook_delta + ticker channels), authenticated with the SAME RSA scheme
as kalshi_exec (kalshi_exec.load_signing_creds / _auth_headers -- no duplicated signing code). Falls back
to REST burst-polling the hot set's asks (batched via GET /markets?tickers=...) when: the `websockets`
package isn't installed, there are no usable credentials, or the WS connection errors. The `websockets`
import is fully lazy/optional -- this module works with zero extra dependencies via the REST path alone.

FAIL-SOFT (critical -- this drives a LIVE $10-canary bot): watch() NEVER raises. Any exception anywhere
in here is caught, logged as one line, and watch() returns a summary dict with transport="none" -- the
caller (kwx_paper_gate's leg loop) just falls back to sleeping until the next poll exactly as it did
before this module existed. No busy-spin: both transports respect `deadline_ts` (the runner's own
adaptive-interval next-poll time) and never poll faster than REST_BURST_S.

Public entry point: watch(hot_set, exec_client, bankroll, state, deadline_ts, verbose=False) -> summary dict.
"""
import json, os, random, time, urllib.request, urllib.error, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"

REST_BURST_S = 2.5          # base cadence for the REST fallback burst-poll (jittered below)
REST_JITTER_S = 0.75        # +/- jitter so many legs don't hammer the API in lockstep
REST_TIMEOUT_S = 4.0
REST_BACKOFF_MAX_S = 30.0   # cap on 429 backoff


class _RateLimited(Exception):
    """Internal signal: the REST burst-poll hit HTTP 429. Caller backs off; never propagates out of
    this module (watch()'s outer guard would catch it anyway, but the burst loop handles it locally so
    a single rate-limit blip doesn't end the whole watch window)."""


def _ask_cents(m, side):
    """Same schema-tolerant int-cents-or-*_dollars read kwx_runner._dollars/event_rungs use, factored
    here rather than imported (kwx_runner._dollars is private and shaped for a slightly different dict)."""
    key = f"{side}_ask"
    v = m.get(key)
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    vd = m.get(key + "_dollars")
    try:
        return int(round(float(vd) * 100)) if vd is not None else None
    except (TypeError, ValueError):
        return None


def _fetch_asks(tickers, timeout=REST_TIMEOUT_S):
    """Batched PUBLIC GET /markets?tickers=... (no auth) -> {ticker: (yes_ask_c, no_ask_c)}. Chunks at 50
    tickers/call (the hot set is small -- normally one request covers it). Raises _RateLimited on HTTP
    429 so the burst loop can back off; any other error propagates to the caller as a transient miss
    (the burst loop just tries again next tick -- a single flaky fetch must not end the watch window)."""
    out = {}
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        url = f"{KBASE}/markets?tickers={','.join(chunk)}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise _RateLimited()
            raise
        for m in d.get("markets", []):
            t = m.get("ticker")
            if not t:
                continue
            out[t] = (_ask_cents(m, "yes"), _ask_cents(m, "no"))
    return out


def _rest_watch(hot_set, ex, bankroll, state, plans, deadline_ts, verbose, summary):
    """REST burst-poll fallback: re-fetch the hot set's asks every REST_BURST_S (+jitter) until
    `deadline_ts` or nothing locked is left to fire for. Fires through kwx_runner.fire_one -- the same
    guarded chokepoint poll_once uses -- the instant a locked hot rung's ask is seen <= MAX_PAY_CENTS."""
    import kwx_runner as R
    by_ticker = {}
    for h in hot_set:
        by_ticker.setdefault(h["ticker"], h)   # one hot-set entry per ticker (locked wins if duplicated)
    tickers = sorted(by_ticker)
    backoff = 1.0
    while time.time() < deadline_ts:
        locked_open = [t for t, h in by_ticker.items()
                       if h.get("locked") and t not in state.get("fired", {})]
        if not locked_open:
            break   # nothing left that CAN fire -- stop burning REST calls for the remaining window
        try:
            asks = _fetch_asks(tickers)
        except _RateLimited:
            backoff = min(backoff * 2, REST_BACKOFF_MAX_S)
            time.sleep(min(backoff, max(0.0, deadline_ts - time.time())))
            continue
        except Exception as e:
            summary["error"] = f"rest-fetch: {type(e).__name__}"
            # transient (timeout / DNS blip / schema drift) -- keep trying on the normal cadence rather
            # than give up on the whole watch window over one bad fetch.
        else:
            backoff = 1.0
            for ticker, (yes_ask, no_ask) in asks.items():
                h = by_ticker.get(ticker)
                if not h:
                    continue
                ask = yes_ask if h["side"] == "yes" else no_ask
                if ask is not None and ask <= 98:
                    summary["seen_le98"] += 1
                if h.get("locked") and ask is not None and ticker not in state.get("fired", {}) \
                        and ask <= R.MAX_PAY_CENTS:
                    outcome = R.fire_one(state, ex, bankroll, ticker, h["side"], ask, h.get("cushion_f"),
                                         h["station"], h["kind"], h.get("extreme_f"), plans,
                                         verbose=verbose, trigger="book-watch")
                    if outcome == "circuit-breaker":
                        # halt written -- END the watch window. Continuing would re-attempt every tick,
                        # re-writing .kwx_halt and re-sending the HALT alert each time (alert spam in the
                        # one scenario where the operator needs a single clear signal). poll_once stops
                        # its cycle on this outcome for the same reason.
                        summary["error"] = "circuit-breaker"
                        return
        remaining = deadline_ts - time.time()
        if remaining <= 0:
            break
        nap = min(REST_BURST_S + random.uniform(0, REST_JITTER_S), remaining)
        time.sleep(max(0.1, nap))


def _websockets_module():
    """Lazy, optional import of the `websockets` package's sync client. Returns None (never raises) if
    unavailable -- the runner's requirements may not include it (see KWX_DEPLOY.md note); the REST
    fallback covers that case completely."""
    try:
        import websockets.sync.client as wssync
        return wssync
    except Exception:
        return None


def _handle_ws_ticker_msg(msg, by_ticker, state, ex, bankroll, plans, verbose, summary):
    """Parse one 'ticker' channel message (Kalshi pushes yes_ask/no_ask per market on this channel) and
    fire through fire_one if it's a locked hot rung whose ask just dropped in range. Schema-tolerant:
    an unexpected shape is simply ignored (returns without raising) rather than killing the WS loop."""
    import kwx_runner as R
    if not isinstance(msg, dict) or msg.get("type") != "ticker":
        return
    data = msg.get("msg") or {}
    ticker = data.get("market_ticker") or data.get("ticker")
    h = by_ticker.get(ticker)
    if not h:
        return
    ask = data.get("yes_ask") if h["side"] == "yes" else data.get("no_ask")
    if not isinstance(ask, int) or isinstance(ask, bool):
        return
    if ask <= 98:
        summary["seen_le98"] += 1
    if h.get("locked") and ticker not in state.get("fired", {}) and ask <= R.MAX_PAY_CENTS:
        outcome = R.fire_one(state, ex, bankroll, ticker, h["side"], ask, h.get("cushion_f"),
                             h["station"], h["kind"], h.get("extreme_f"), plans, verbose=verbose,
                             trigger="book-watch")
        if outcome == "circuit-breaker":
            summary["error"] = "circuit-breaker"   # _ws_watch checks this and ends the window (alert-spam guard)


def _ws_watch(hot_set, ex, bankroll, state, plans, deadline_ts, verbose, summary):
    """Kalshi WebSocket primary transport. Returns True if the WS session ran (even if it saw nothing
    fire-worthy) -- meaning REST should NOT also run for this window. Returns False if WS isn't usable
    (no library, no creds) or errored, meaning the caller should use the REST fallback for whatever time
    budget remains. NOTE: this parsing is best-effort against Kalshi's public WS schema and has not been
    exercised against a live authenticated session in this environment (no creds available here) -- the
    REST fallback is the transport this change is actually verified against; see the PR risk section."""
    wssync = _websockets_module()
    if wssync is None:
        return False
    import kalshi_exec
    key_id, priv = kalshi_exec.load_signing_creds()
    if key_id is None or priv is None:
        return False   # no usable creds -> REST fallback (per spec: WS requires the same RSA scheme)
    by_ticker = {}
    for h in hot_set:
        by_ticker.setdefault(h["ticker"], h)
    tickers = sorted(by_ticker)
    if not tickers:
        return True   # nothing to watch -- trivially "handled" by WS, no REST needed either
    headers = kalshi_exec._auth_headers(key_id, priv, "GET", WS_PATH)
    remaining0 = max(1, int(deadline_ts - time.time()))
    with wssync.connect(WS_URL, additional_headers=headers, open_timeout=min(10, remaining0)) as ws:
        sub = {"id": 1, "cmd": "subscribe",
               "params": {"channels": ["orderbook_delta", "ticker"], "market_tickers": tickers}}
        ws.send(json.dumps(sub))
        while time.time() < deadline_ts:
            locked_open = [t for t, h in by_ticker.items()
                           if h.get("locked") and t not in state.get("fired", {})]
            if not locked_open:
                break
            remaining = deadline_ts - time.time()
            if remaining <= 0:
                break
            try:
                raw = ws.recv(timeout=min(remaining, 5))
            except TimeoutError:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            _handle_ws_ticker_msg(msg, by_ticker, state, ex, bankroll, plans, verbose, summary)
            if summary.get("error") == "circuit-breaker":
                break   # halt written -- end the window instead of re-attempting (alert-spam guard)
    return True


def watch(hot_set, exec_client, bankroll, state, deadline_ts, verbose=False):
    """Watch `hot_set` (list of hot-rung dicts from kwx_runner.poll_once(hot_set_out=...)) between obs
    polls, firing a hot LOCKED rung through kwx_runner.fire_one() the instant its ask drops <=
    MAX_PAY_CENTS. Runs until `deadline_ts` (epoch seconds -- the runner's own next-adaptive-poll time,
    so this NEVER runs longer than the runner would have idled anyway) or the locked subset is exhausted.

    A rung that is merely near-lock (not yet locked) is watched for observability (asks-seen-<=98 count)
    but can NEVER fire here -- lock status only changes on an obs poll, never on a price observation.

    Returns: {"transport": "ws"|"rest"|"none", "hot_n": int, "locked_n": int, "seen_le98": int,
              "fired": int, "plans": [...], "error": str|None}

    FAIL-SOFT: this function does not raise. Any exception (including a library panic that doesn't
    subclass Exception -- see kalshi_exec.load_signing_creds' docstring) is caught at the outer boundary
    and reported via summary["error"]; the caller's plain-polling behavior is unaffected either way."""
    summary = {"transport": "none", "hot_n": len(hot_set), "locked_n": 0, "seen_le98": 0,
               "fired": 0, "plans": [], "error": None}
    try:
        locked = [h for h in hot_set if h.get("locked")]
        summary["locked_n"] = len(locked)
        if not hot_set or deadline_ts <= time.time():
            return summary
        plans = summary["plans"]
        try:
            used_ws = _ws_watch(hot_set, exec_client, bankroll, state, plans, deadline_ts, verbose, summary)
        except BaseException as e:   # a WS lib failure must never take down the watch window
            summary["error"] = f"ws: {type(e).__name__}: {e}"
            used_ws = False
        if used_ws:
            summary["transport"] = "ws"
        else:
            summary["transport"] = "rest"
            _rest_watch(hot_set, exec_client, bankroll, state, plans, deadline_ts, verbose, summary)
        summary["fired"] = len(plans)
        if plans:
            import kwx_runner as R
            R._save_state(state)
        return summary
    except BaseException as e:
        if verbose:
            print(f"[kwx_book_watcher] watcher failed ({type(e).__name__}: {e}); falling back to plain polling")
        summary["transport"] = "none"
        summary["error"] = f"{type(e).__name__}: {e}"
        return summary


if __name__ == "__main__":
    # smoke: dry-run watch() against an empty hot set (no network, no creds needed) -- just proves the
    # module imports and returns cleanly.
    print(watch([], None, 10.0, {"fired": {}}, time.time() + 1, verbose=True))
