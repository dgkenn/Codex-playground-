#!/usr/bin/env python3
"""kalshi_exec.py -- Kalshi order-execution client for the K-WX weather-nowcast bot.

SAFETY POSTURE (non-negotiable): PROPOSE-ONLY by DEFAULT. This module SIMULATES fills unless
BOTH of these are true:
  1. a credentials file exists at .kalshi_creds  (gitignored; you create it -- see below), AND
  2. the environment variable KWX_LIVE == "1"     (an explicit, deliberate opt-in).
If either is missing, every order is a DRY-RUN: it is logged and a simulated fill is returned, but
NO request is ever sent to Kalshi. There is no code path that places a live order without both gates.
This matches the program charter: no live capital without explicit human authorization.

Live auth (only when you deliberately enable it) uses Kalshi's RSA-signed scheme: an access-key id +
an RSA private key, signing `timestamp(ms) + METHOD + path` with RSA-PSS-SHA256, sent as headers
KALSHI-ACCESS-KEY / KALSHI-ACCESS-TIMESTAMP / KALSHI-ACCESS-SIGNATURE. Credentials resolve from EITHER:
  (a) the SAME env vars the existing box strategy (kalshi_trader.py) already uses --
      KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH (path to the RSA PEM) -- so if you already run a Kalshi
      bot on this host, K-WX picks up its credentials with NOTHING new to configure; OR
  (b) a local .kalshi_creds JSON: {"access_key_id": "...", "private_key_pem"|"private_key_path": "..."}.
Either way the secret never touches git (env vars aren't files; .kalshi_creds is gitignored). RSA signing
needs `cryptography` -- only imported on the live path, so dry-run has no deps.

Usage (all dry-run unless the two gates are set):
    from kalshi_exec import KalshiExec
    ex = KalshiExec()                      # DRY_RUN unless gated live
    r = ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95)
    print(r)   # {'status':'DRY_RUN'|'live', 'filled': n, 'avg_price': ..., ...}
"""
import json, os, time, base64, urllib.request, urllib.error, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
CREDS_PATH = os.path.join(HERE, ".kalshi_creds")

# --- free execution guards (only bite in bad scenarios; zero cost in normal operation) ---
HALT_FILE = os.path.join(HERE, ".kwx_halt")   # `touch .kwx_halt` -> manual kill switch, blocks ALL live orders
HARD_MAX_CONTRACTS = 200                        # fat-finger / bug ceiling: refuse any single order above this
HARD_MAX_PRICE_CENTS = 98                       # never pay above this (no-gap / dead-on-arrival protection)


class _GuardBlocked(Exception):
    """Raised by _submit_guarded when _guard refuses an order (HALT_FILE kill-switch / size / price).
    Carries the blocked record so callers can log/return it without re-deriving the reason."""
    def __init__(self, record):
        super().__init__(record.get("reason", "blocked"))
        self.record = record


def _client_order_id(ticker, side, attempt=0):
    """Deterministic idempotency key: one order per ticker+side (ticker already encodes the day). A retried
    identical order carries the SAME id -> Kalshi dedupes it, so a crash/retry can't double-fill.

    `attempt` handles the one deliberate exception: after a CONFIRMED zero-fill IOC (ask moved between quote
    and order) we re-quote and retry ONCE. Kalshi dedupes on client_order_id, so reusing the unsuffixed id
    would make the retry silently no-op -- the retry MUST carry a distinct id. The suffix is still
    deterministic ("-r1", not a uuid): if we crash between attempt 1 and attempt 2, a restart regenerates the
    SAME retry id and Kalshi dedupes it, so there is no code path that creates a third order."""
    base = f"kwx-{ticker}-{side}"
    return base if attempt == 0 else f"{base}-r{attempt}"


class KalshiExec:
    def __init__(self, base=KBASE, log_path=os.path.join(HERE, "kwx_exec_log.jsonl")):
        self.base = base
        self.log_path = log_path
        self._priv = None
        self._key_id = None
        # LIVE requires the explicit KWX_LIVE gate AND usable credentials. Credentials resolve from EITHER
        # source (whichever is present):
        #   (a) the SAME env vars the box strategy (kalshi_trader.py) uses -- KALSHI_API_KEY_ID +
        #       KALSHI_PRIVATE_KEY_PATH (a PEM file) -- so an existing Kalshi setup works with no new config; OR
        #   (b) a local .kalshi_creds JSON ({access_key_id, private_key_pem|private_key_path}).
        creds_available = bool(os.environ.get("KALSHI_API_KEY_ID") and
                               (os.environ.get("KALSHI_PRIVATE_KEY_PATH") or os.environ.get("KALSHI_PRIVATE_KEY"))) \
            or os.path.exists(CREDS_PATH)
        self.live = (os.environ.get("KWX_LIVE") == "1") and creds_available
        if self.live:
            self._load_creds()  # may flip self.live back to False if creds unusable

    # ---- credential loading (live path only) ----
    def _load_creds(self):
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            env_id = os.environ.get("KALSHI_API_KEY_ID")
            env_pem_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
            env_pem = os.environ.get("KALSHI_PRIVATE_KEY")   # PEM content directly (GitHub-secret style)
            if env_id and (env_pem_path or env_pem):
                # box-strategy-compatible: key id + PEM (from a file path OR the raw secret content)
                self._key_id = env_id
                if env_pem_path:
                    with open(env_pem_path, "rb") as fh:
                        pem_bytes = fh.read()
                else:
                    pem_bytes = env_pem.encode()
                self._priv = load_pem_private_key(pem_bytes, password=None)
            else:
                creds = json.load(open(CREDS_PATH))
                self._key_id = creds["access_key_id"]
                pem = creds.get("private_key_pem")
                if not pem and creds.get("private_key_path"):
                    pem = open(creds["private_key_path"]).read()
                self._priv = load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)
        except Exception as e:
            # Any failure -> stay in dry-run rather than risk a malformed live attempt.
            print(f"[kalshi_exec] creds load failed ({e}); staying DRY_RUN")
            self.live = False

    def _sign(self, ts_ms, method, path):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        msg = f"{ts_ms}{method}{path}".encode()
        # Kalshi's scheme: RSA-PSS, MGF1-SHA256, salt_length = digest length (matches Kalshi's SDK example).
        sig = self._priv.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode()

    def _headers(self, method, path):
        ts = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": self._sign(ts, method, path),
        }

    def _guard(self, ticker, count, price_cents):
        """Pre-trade safety guards (free insurance). Returns a 'blocked' record if the order must be
        refused, else None. Applies to BOTH dry-run and live so paper testing exercises them too."""
        if os.path.exists(HALT_FILE):
            return {"status": "BLOCKED_HALT", "ticker": ticker, "reason": "kill-switch .kwx_halt present"}
        if int(count) < 1:
            return {"status": "BLOCKED_SIZE", "ticker": ticker, "reason": f"count {count} < 1"}
        if int(count) > HARD_MAX_CONTRACTS:
            return {"status": "BLOCKED_SIZE", "ticker": ticker,
                    "reason": f"count {count} > HARD_MAX_CONTRACTS {HARD_MAX_CONTRACTS} (fat-finger guard)"}
        if int(price_cents) > HARD_MAX_PRICE_CENTS:
            return {"status": "BLOCKED_PRICE", "ticker": ticker,
                    "reason": f"price {price_cents}c > cap {HARD_MAX_PRICE_CENTS}c (no gap left)"}
        if int(price_cents) < 1 or int(price_cents) > 99:
            return {"status": "BLOCKED_PRICE", "ticker": ticker, "reason": f"price {price_cents}c out of [1,99]"}
        return None

    def _log(self, rec):
        rec = {**rec, "ts": int(time.time() * 1000), "live": self.live}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    @staticmethod
    def _reconcile(resp, count):
        """Best-effort fill reconciliation from Kalshi's create-order response (schema-tolerant). IOC orders
        fill-or-cancel immediately, so the response's order object carries the outcome. Returns
        (filled_count_or_None, order_status). Lets the caller record ACTUAL fills, not just what was requested
        -- so a partial fill (book thinner than our size) doesn't silently overstate our position."""
        o = resp.get("order", {}) if isinstance(resp, dict) else {}
        if not isinstance(o, dict):
            o = {}
        filled = o.get("filled_count", o.get("filled"))
        if filled is None and o.get("remaining_count") is not None:
            try:
                filled = int(count) - int(o["remaining_count"])
            except Exception:
                filled = None
        return filled, o.get("status")

    # ---- live-order plumbing (shared by buy_yes / buy_no and the one bounded retry) ----
    def _post_order(self, order):
        """POST one signed create-order request; returns the parsed response dict. Raises on HTTP/network
        errors -- callers decide how to fail (buy_* logs live_error; the retry path fails CLOSED back to
        the original zero-fill record)."""
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     data=body, method="POST",
                                     headers=self._headers("POST", path))
        return json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))

    def _submit_guarded(self, ticker, side, count, price_cents, client_order_id):
        """SINGLE chokepoint for every live order POST -- the initial attempt AND the bounded retry both
        go through here, no exceptions. Runs _guard (HALT_FILE kill-switch + count/size/price guards)
        IMMEDIATELY before building/sending the order.

        This exists because the retry previously called _post_order directly and only re-checked price
        ad-hoc: `touch .kwx_halt` between the initial zero-fill and the retry would NOT have stopped the
        retry order. Routing both call sites through one guarded method closes that gap structurally --
        there is no live POST path that skips _guard.

        Raises _GuardBlocked(record) if refused (record is the same shape _guard/buy_* already produce).
        Otherwise POSTs and returns (resp, order); raises urllib.error.HTTPError / other network errors
        same as _post_order (callers decide how to handle those)."""
        blocked = self._guard(ticker, count, price_cents)
        if blocked:
            raise _GuardBlocked(blocked)
        price_key = "yes_price" if side == "yes" else "no_price"
        order = {
            "ticker": ticker, "action": "buy", "side": side,
            "count": int(count), "type": "limit", price_key: int(price_cents),
            "time_in_force": "immediate_or_cancel", "client_order_id": client_order_id,
        }
        return self._post_order(order), order

    def _requote_ask_cents(self, ticker, side):
        """Re-fetch the CURRENT displayed ask for one side from the PUBLIC market endpoint
        (GET /trade-api/v2/markets/{ticker} -- no auth, same data kwx_runner.event_rungs reads off the
        events endpoint). Returns int cents in [1,99], or None on any failure/absence -- callers treat
        None as 'do not retry' (fail closed). Schema-tolerant like kwx_runner._dollars: prefers the
        integer-cents `yes_ask`/`no_ask` field, falls back to the `*_dollars` variant."""
        try:
            req = urllib.request.Request(f"{self.base}/markets/{ticker}",
                                         headers={"Accept": "application/json"})
            m = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX)).get("market") or {}
            key = "yes_ask" if side == "yes" else "no_ask"
            v = m.get(key)
            # `yes_ask`/`no_ask` are documented as integer CENTS; only trust integral values so a
            # dollars-float (e.g. 0.55) can never be misread as 1c.
            if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 99:
                return v
            vd = m.get(key + "_dollars")
            if vd is not None:
                c = int(round(float(vd) * 100))
                if 1 <= c <= 99:
                    return c
        except Exception as e:
            print(f"[kalshi_exec] re-quote failed for {ticker}/{side} ({e}); no retry")
        return None

    def _retry_once(self, first_rec, ticker, side, count, max_price_cents):
        """ONE bounded retry after a CONFIRMED zero-fill live IOC (the 'ask moved between quote and order'
        case -- without this the runner marks the ticker fired and the edge is permanently abandoned).
        Re-quotes the ask and re-fires ONLY if it is still <= the original max_price_cents (and <= the 98c
        hard ceiling), using the distinct-but-deterministic '-r1' client_order_id (see _client_order_id for
        why reuse would silently no-op), and ALWAYS through _submit_guarded so the retry re-runs _guard
        (HALT_FILE kill-switch + count/price) fresh, not just a price re-check.

        Outcome handling is deliberately NOT one blanket try/except:
          - a re-quote miss, an over-cap re-quote, or a _GuardBlocked -> the retry was never sent; the
            original zero-fill record stands untouched (nothing ambiguous happened).
          - urllib.error.HTTPError -> Kalshi gave us a DEFINITIVE rejection response; the -r1 order was
            never accepted, so this is still a clean, provable zero-fill.
          - any OTHER exception (timeout, connection drop, decode error, ...) can happen AFTER the retry
            bytes left this process -- we have no proof whether -r1 reached Kalshi or filled. That case
            is recorded as fill_state="unknown" (never as a clean zero) so nothing downstream silently
            treats an ambiguous send as flat; it must be reconciled against client_order_id before being
            trusted either way.
        Returns the record to log."""
        ask = self._requote_ask_cents(ticker, side)
        if ask is None:
            return {**first_rec, "retry": {"attempted": False, "requote_ask_c": None,
                                           "reason": "re-quote failed or no ask"}}
        if ask > int(max_price_cents) or ask > HARD_MAX_PRICE_CENTS:
            return {**first_rec, "retry": {"attempted": False, "requote_ask_c": ask,
                                           "reason": f"requoted ask {ask}c > cap"}}
        retry_id = _client_order_id(ticker, side, attempt=1)
        try:
            resp, _order = self._submit_guarded(ticker, side, count, max_price_cents, retry_id)
        except _GuardBlocked as e:
            # Not sent at all (e.g. HALT_FILE touched between the first attempt and now) -- unambiguous,
            # original zero-fill stands.
            return {**first_rec, "retry": {"attempted": False, "requote_ask_c": ask,
                                           "reason": e.record.get("reason", "guard blocked"),
                                           "guard_status": e.record.get("status")}}
        except urllib.error.HTTPError as e:
            # Definitive rejection -- we got an HTTP response back, so the retry order was never
            # accepted by Kalshi. Not ambiguous: still a clean zero-fill.
            body = e.read().decode()[:300] if hasattr(e, "read") else ""
            return {**first_rec, "retry": {"attempted": True, "requote_ask_c": ask,
                                           "client_order_id": retry_id,
                                           "error": f"HTTP {e.code}: {body}"}}
        except Exception as e:
            print(f"[kalshi_exec] retry send AMBIGUOUS for {ticker}/{side} ({e}); "
                  f"fill_state=unknown -- reconcile client_order_id={retry_id} before assuming flat")
            return {**first_rec, "filled": None, "fill_state": "unknown",
                    "retry": {"attempted": True, "requote_ask_c": ask, "fill_state": "unknown",
                              "client_order_id": retry_id, "error": str(e)[:200],
                              "reason": "send outcome unknown (not an HTTP rejection) -- "
                                        "reconcile before assuming flat"}}
        filled, ostatus = self._reconcile(resp, count)
        fill_state = ("flat" if filled == 0 else "filled" if filled == count
                      else "partial" if isinstance(filled, int) else "unknown")
        # Retry succeeded (as an API call): the record's top-level fields now reflect the FINAL
        # outcome (attempt 1 filled exactly 0, so retry fill == total fill); the first attempt's
        # outcome is preserved under first_attempt. All keys are additive -> shape stays
        # backward-compatible with existing log readers.
        return {**first_rec, "attempts": 2, "filled": filled, "order_status": ostatus,
                "fill_state": fill_state, "response": resp,
                "retry": {"attempted": True, "requote_ask_c": ask, "filled": filled,
                          "order_status": ostatus, "client_order_id": retry_id},
                "first_attempt": {"filled": first_rec.get("filled"),
                                  "order_status": first_rec.get("order_status")}}

    # ---- public: place a YES buy (taker, immediate-or-cancel at a price cap) ----
    def buy_yes(self, ticker, count, max_price_cents, dry_fill_price=None):
        """Buy `count` YES contracts at up to `max_price_cents`. DRY-RUN unless gated live.

        dry_fill_price (cents) lets a simulator/backtest inject the price it believes fillable; if
        None, the dry-run assumes a fill at max_price_cents (conservative)."""
        blocked = self._guard(ticker, count, max_price_cents)
        if blocked:
            self._log(blocked)
            return blocked
        order = {
            "ticker": ticker, "action": "buy", "side": "yes",
            "count": int(count), "type": "limit", "yes_price": int(max_price_cents),
            "time_in_force": "immediate_or_cancel", "client_order_id": _client_order_id(ticker, "yes"),
        }
        if not self.live:
            fill = int(dry_fill_price if dry_fill_price is not None else max_price_cents)
            r = {"status": "DRY_RUN", "ticker": ticker, "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order}
            self._log(r)
            return r
        # ---- live path (only reached when KWX_LIVE=1 AND creds present) ----
        try:
            # _submit_guarded re-runs _guard right before sending -- same chokepoint the retry uses, so
            # a HALT_FILE written between the guard check above and this POST still blocks the order.
            resp, order = self._submit_guarded(ticker, "yes", count, max_price_cents, order["client_order_id"])
            filled, ostatus = self._reconcile(resp, count)
            r = {"status": "live", "ticker": ticker, "requested": int(count),
                 "filled": filled, "order_status": ostatus, "response": resp}
            # CONFIRMED zero fill (ask moved between the runner's quote and our IOC) -> one bounded
            # retry at a fresh quote. `type(filled) is int` deliberately excludes None/unknown fill
            # state (and bool): retrying when we can't PROVE zero fill risks doubling the position.
            if type(filled) is int and filled == 0:
                r = self._retry_once(r, ticker, "yes", count, max_price_cents)
        except _GuardBlocked as e:
            r = e.record
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r

    def buy_no(self, ticker, count, max_price_cents, dry_fill_price=None):
        """Buy `count` NO contracts (for the 'locked NO' rungs). Mirror of buy_yes."""
        blocked = self._guard(ticker, count, max_price_cents)
        if blocked:
            self._log(blocked)
            return blocked
        order = {
            "ticker": ticker, "action": "buy", "side": "no",
            "count": int(count), "type": "limit", "no_price": int(max_price_cents),
            "time_in_force": "immediate_or_cancel", "client_order_id": _client_order_id(ticker, "no"),
        }
        if not self.live:
            fill = int(dry_fill_price if dry_fill_price is not None else max_price_cents)
            r = {"status": "DRY_RUN", "ticker": ticker, "side": "no", "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order}
            self._log(r)
            return r
        try:
            # Same guarded chokepoint as buy_yes (see comment there).
            resp, order = self._submit_guarded(ticker, "no", count, max_price_cents, order["client_order_id"])
            filled, ostatus = self._reconcile(resp, count)
            r = {"status": "live", "ticker": ticker, "side": "no", "requested": int(count),
                 "filled": filled, "order_status": ostatus, "response": resp}
            # Same bounded zero-fill retry as buy_yes (see comment there); None/unknown -> no retry.
            if type(filled) is int and filled == 0:
                r = self._retry_once(r, ticker, "no", count, max_price_cents)
        except _GuardBlocked as e:
            r = e.record
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r


if __name__ == "__main__":
    ex = KalshiExec()
    print("LIVE ENABLED:", ex.live, "(needs KWX_LIVE=1 AND .kalshi_creds)")
    print("dry-run demo:", ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95, dry_fill_price=88))
