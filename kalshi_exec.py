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


def _client_order_id(ticker, side):
    """Deterministic idempotency key: one order per ticker+side (ticker already encodes the day). A retried
    identical order carries the SAME id -> Kalshi dedupes it, so a crash/retry can't double-fill."""
    return f"kwx-{ticker}-{side}"


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
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     data=body, method="POST",
                                     headers=self._headers("POST", path))
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))
            filled, ostatus = self._reconcile(resp, count)
            r = {"status": "live", "ticker": ticker, "requested": int(count),
                 "filled": filled, "order_status": ostatus, "response": resp}
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
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     data=body, method="POST", headers=self._headers("POST", path))
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))
            filled, ostatus = self._reconcile(resp, count)
            r = {"status": "live", "ticker": ticker, "side": "no", "requested": int(count),
                 "filled": filled, "order_status": ostatus, "response": resp}
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r

    # ---- public: read the account's cash balance (READ-ONLY; sizing input, never a gate-loosener) ----
    def get_balance(self):
        """Return the Kalshi account's available cash balance in DOLLARS, or None if unavailable.

        READ-ONLY: authenticated GET /trade-api/v2/portfolio/balance, reusing the exact same RSA-PSS
        signing (_sign/_headers) as order placement -- no new auth surface. Deliberately gated on
        self.live (KWX_LIVE=1 AND usable creds): we do NOT load credentials just to read a balance,
        because keeping "creds are only ever touched when the operator explicitly went live" true is
        worth more than a paper-mode balance display. This can only make live sizing SAFER (see
        effective_bankroll); it never enables anything.

        Units: Kalshi's API returns the balance in CENTS -- the response is {"balance": <int cents>}
        (e.g. {"balance": 1234} == $12.34). We read the "balance" field and divide by 100.0.

        SEMANTICS (deliberate, both fail-safe DOWNWARD -- this function may only ever shrink sizing):
          - "balance" is AVAILABLE SETTLED CASH: it excludes money already tied up in open orders and
            positions. Sizing off available cash is intentionally conservative -- deployed capital
            can't be bet again anyway, and using net account value here would let sizing outrun cash.
          - A genuine 0 balance returns 0.0, NOT None: an empty account must size to zero (and
            _guard's count<1 check will refuse orders), never fall back to a fatter default.
          - The .kwx_halt kill switch means "stop interacting with Kalshi", so even this read-only
            probe stands down while halted (returns None). Purely a tightener; the order-side halt
            enforcement in _guard is untouched.

        NEVER RAISES. Any failure mode -> None, so callers fall back to their configured default:
          - not live / creds missing        -> None (no request is even attempted)
          - kill switch (.kwx_halt) present -> None (no request is even attempted)
          - HTTP error, timeout, bad JSON   -> None
          - "balance" field absent/non-int  -> None
        Failing closed to None (=> default bankroll) keeps a flaky balance endpoint from ever
        changing sizing behavior mid-session in a surprising way.
        """
        # belt-and-braces: live=True already implies creds loaded (constructor flips live off on any
        # cred failure), but a fail-closed path double-checks rather than trusts the invariant
        if not self.live or self._priv is None or self._key_id is None:
            return None
        if os.path.exists(HALT_FILE):
            return None
        path = "/trade-api/v2/portfolio/balance"
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     method="GET", headers=self._headers("GET", path))
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))
            cents = resp.get("balance") if isinstance(resp, dict) else None
            if cents is None:
                return None
            return int(cents) / 100.0
        except Exception:
            # Broad on purpose: a balance probe must never crash the trading loop, and there is
            # nothing actionable to do besides "use the default". No key material in any exception
            # we could log here, but we stay silent anyway -- the None return IS the signal.
            return None


def effective_bankroll(default_dollars, exec_client=None):
    """The bankroll the sizer should use: min(default_dollars, live account balance).

    WHY min() and not the live balance outright: `default_dollars` (the runner's BANKROLL constant)
    is the OPERATOR'S authorized risk ceiling, not an estimate of account size. Two failure modes,
    both covered:
      - Fat account (balance > constant): sizing must NOT silently scale UP past what the operator
        authorized -- e.g. a $10 canary must stay a $10 canary even on a $5k account. min() keeps
        the constant binding.
      - Drawn-down account (balance < constant): sizing MUST scale DOWN, because sizing off a
        bankroll we no longer have overbets every fire (Kelly fractions assume the denominator is
        real money). min() makes the real balance binding.
    So min() is fail-safe in BOTH directions; the only way to size bigger is the operator editing
    the constant, exactly as intended.

    When no live balance is available (paper mode, missing creds, API hiccup -> get_balance()
    returns None) we fall back to default_dollars unchanged, which preserves today's behavior
    exactly -- this function is a pure, optional tightener.

    exec_client: pass an existing KalshiExec to reuse its loaded creds; else one is constructed.
    Construction alone never touches the network and only loads creds when gated live -- but a
    per-poll-cycle caller (the runner) should pass its existing client, so the live path doesn't
    re-read + re-parse the RSA PEM from disk every cycle.
    """
    try:
        ex = exec_client if exec_client is not None else KalshiExec()
        bal = ex.get_balance()
    except Exception:
        bal = None  # even a constructor surprise must not break sizing -- fall back to the default
    if bal is None:
        return float(default_dollars)
    return min(float(default_dollars), bal)


def _runner_default_bankroll(fallback=10.0):
    """Best-effort read of kwx_runner.BANKROLL for the --balance smoke path, WITHOUT importing
    kwx_runner (its import constructs the live feed stack -- too heavy/side-effectful for a smoke
    print). Parsing the constant straight out of the source keeps the smoke display from silently
    drifting when the operator bumps the runner's ceiling. Any problem -> `fallback` ($10 canary,
    operator-authorized 2026-07-18). Display-only: the runner itself always passes its own constant."""
    import re
    try:
        with open(os.path.join(HERE, "kwx_runner.py")) as fh:
            m = re.search(r"^BANKROLL\s*=\s*([0-9]+(?:\.[0-9]+)?)", fh.read(), re.M)
        return float(m.group(1)) if m else fallback
    except Exception:
        return fallback


if __name__ == "__main__":
    import sys
    _balflags = [a for a in sys.argv[1:] if a == "--balance" or a.startswith("--balance=")]
    if _balflags:
        # Smoke path: `python kalshi_exec.py --balance [default_dollars]` (or `--balance=50`)
        # prints the effective bankroll and its provenance. Default ceiling comes from
        # kwx_runner.BANKROLL (parsed, not imported -- see _runner_default_bankroll); an explicit
        # value lets the operator smoke-test against any ceiling.
        _default = _runner_default_bankroll()
        _raw = None
        if "=" in _balflags[0]:
            _raw = _balflags[0].split("=", 1)[1]
        else:
            _rest = sys.argv[sys.argv.index("--balance") + 1:]
            if _rest:
                _raw = _rest[0]
        if _raw is not None:
            try:
                _default = float(_raw)
            except ValueError:
                print(f"[kalshi_exec] ignoring non-numeric default {_raw!r}; using {_default}")
        _ex = KalshiExec()
        _bal = _ex.get_balance()   # the ONLY balance probe: one HTTP round-trip even when live

        class _Probed:
            """Feeds the single probe result back through effective_bankroll, so the printed number
            is exactly the policy function's output without a second HTTP call (and without the
            display and the policy ever disagreeing about which balance they saw)."""
            def get_balance(self):
                return _bal

        _eff = effective_bankroll(_default, exec_client=_Probed())
        if _bal is None:
            # covers: paper mode, missing creds, halt, or API failure -- all fail closed to default
            _why = "no creds -> default" if not _ex.live else "live but balance unavailable -> default"
            print(f"effective bankroll: ${_eff:.2f} ({_why})")
        else:
            # provenance derived from the policy OUTPUT (_eff vs _default), not a re-derived rule
            _src = "live balance binds" if _eff < _default else "default (operator ceiling) binds"
            print(f"live balance: ${_bal:.2f}; effective bankroll: ${_eff:.2f} "
                  f"(min of default ${_default:.2f} and live -> {_src})")
        sys.exit(0)
    ex = KalshiExec()
    print("LIVE ENABLED:", ex.live, "(needs KWX_LIVE=1 AND .kalshi_creds)")
    print("dry-run demo:", ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95, dry_fill_price=88))
