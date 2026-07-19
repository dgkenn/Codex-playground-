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


# ---- honest paper fills: depth-aware dry-run fill model ("depth_v1") ----
# WHY: the dry-run path used to assume a 100% fill of the requested size at the cap price. The repo's own
# orderbook study (kalshi_weather_orderbook_summary.json / wx_capacity_probe.py) measured ~21% of books EMPTY
# at the fire instant and a median best-ask size of ~13 contracts -- so "full fill" systematically overstates
# paper fills, which makes the go-live gate's "live==tested" claim dishonest on the fill dimension. These two
# helpers read the PUBLIC orderbook (no auth -- same endpoint wx_capacity_probe.py uses) at fire time and cap
# the simulated fill at the DISPLAYED depth within our price cap. Expect measured paper EV to DROP vs the old
# assumption; that drop is the honesty we're buying. Fail-OPEN on any fetch error: fall back to the old
# full-fill behavior, tagged fill_model="assumed_full", so a network blip never crashes a paper cycle and
# downstream analysis can segment honest vs assumed records.

def _get(url, timeout=6, method="GET", data=None, headers=None):
    """Shared JSON-over-HTTP helper: builds the Request, calls urlopen with our shared SSL context, and
    parses the JSON body. Used for every request this module makes (public book fetch, live order POSTs)
    so the timeout/context/json.load boilerplate lives in exactly one place."""
    req = urllib.request.Request(url, data=data, method=method,
                                  headers=headers or {"Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))


def _fetch_orderbook(ticker, timeout=1.5):
    """Fetch the PUBLIC orderbook for `ticker`, normalized to {'yes': [[price_c, size], ...], 'no': [...]}
    (integer cents / integer contracts -- the shape wx_capacity_probe was written against). Returns None on
    ANY error OR an unrecognized schema -- callers treat None as "book unknown" and fall back to the old
    full-fill assumption. Distinguishing "unknown" from "empty" matters: a schema drift must NOT masquerade
    as 21%-style empty books and silently zero every paper fill.

    Handles BOTH response schemas: the legacy 'orderbook' ({'yes': [[cents, count]], 'no': ...}) and the
    current 'orderbook_fp' ({'yes_dollars': [['0.9900', '148.51'], ...], ...}) where prices are dollar
    strings and sizes are (possibly fractional) CONTRACT counts -- verified against live data: a market's
    top no_dollars level size exactly equals its yes_ask_size_fp quote, so the second element is contracts,
    not notional dollars. Fractional sizes floor to int (we trade whole contracts; conservative).

    timeout defaults to a TIGHT ~1.5s (not the module's normal 6-10s): this fetch sits in the adaptive
    paper loop's fastest cadence (5s, when a cross is imminent -- see kwx_runner.adaptive_interval_s), so a
    slow/hanging book endpoint must not stall detection. A timeout is just another fetch error -> fail open
    to "book unknown" (assumed_full), never a crashed or stalled cycle.

    Kept as a module-level function; KalshiExec(fetch_book=False) (or env KWX_NO_BOOK_FETCH=1) skips calling
    it at all for offline/deterministic callers -- see the class docstring."""
    def _norm(levels, price_scale):
        out = []
        for lvl in (levels or []):
            try:
                out.append([int(round(float(lvl[0]) * price_scale)), int(float(lvl[1]))])
            except Exception:
                continue   # schema-tolerant: skip a malformed level, keep the rest
        return out
    try:
        url = f"{KBASE}/markets/{ticker}/orderbook"
        d = _get(url, timeout=timeout)
        ob = d.get("orderbook")
        if isinstance(ob, dict):      # legacy schema: already integer cents
            return {"yes": _norm(ob.get("yes"), 1), "no": _norm(ob.get("no"), 1)}
        fp = d.get("orderbook_fp")
        if isinstance(fp, dict):      # current schema: dollar strings -> cents
            return {"yes": _norm(fp.get("yes_dollars"), 100), "no": _norm(fp.get("no_dollars"), 100)}
        return None   # unrecognized schema -> unknown, NOT empty
    except Exception:
        return None   # fail open: unknown book != empty book


def _sim_depth_fill(book, side, count, max_price_cents, top_n=3):
    """Simulate an IOC taker fill against the displayed book. Returns a dict of fill fields to merge into the
    dry-run record (fill_model="depth_v1").

    Book convention (mirrors wx_capacity_probe.orderbook_ask_depth): Kalshi's public book lists resting BIDS
    per side -- {'yes': [[price_c, size], ...], 'no': [[price_c, size], ...]}. A YES buyer lifts the resting
    NO bids: a NO bid at q cents IS a YES ask at (100 - q). Symmetrically a NO buyer lifts the resting YES
    bids: a YES bid at p IS a NO ask at (100 - p). So the ask ladder we can hit is derived from the OPPOSITE
    side's bids.

    Fill = min(requested, sum of derived ask sizes at price <= our cap) -- possibly 0 (empty book: the 21%
    case the study measured). We also record what we saw (best ask, depth, top levels) so the exec log carries
    the evidence, not just the conclusion, and fill_vwap_c = the walk-the-book average price actually paid
    (<= cap; the old model charged the cap even when the ask was cheaper)."""
    resting = (book.get("no") if side == "yes" else book.get("yes")) or []
    levels = []
    for lvl in resting:
        try:
            q, size = lvl[0], lvl[1]   # already normalized to int by _fetch_orderbook's _norm; no re-cast
        except Exception:
            continue   # schema-tolerant: skip malformed levels rather than crash a paper cycle
        ask = 100 - q
        if 1 <= ask <= 99 and size > 0:
            levels.append((ask, size))
    levels.sort()                                        # cheapest ask first = the order an IOC walks the book
    depth = sum(s for a, s in levels if a <= int(max_price_cents))
    filled = min(int(count), depth)
    # walk the book for the volume-weighted price of the simulated fill (only levels within the cap)
    remaining, cost = filled, 0
    for a, s in levels:
        if remaining <= 0 or a > int(max_price_cents):
            break
        take = min(s, remaining)
        cost += take * a
        remaining -= take
    return {
        "fill_model": "depth_v1",
        "filled": filled,
        "depth_at_cap": depth,
        "best_ask_c": levels[0][0] if levels else None,   # best displayed ask, cap or not (None = empty book)
        "best_ask_size": levels[0][1] if levels else None,
        "book_top": [[a, s] for a, s in levels[:top_n]],  # compact snapshot: top few ask levels as evidence
        "fill_vwap_c": (round(cost / filled, 2) if filled else None),
    }


class KalshiExec:
    def __init__(self, base=KBASE, log_path=os.path.join(HERE, "kwx_exec_log.jsonl"), fetch_book=True):
        """fetch_book=False (or env KWX_NO_BOOK_FETCH=1) disables the depth_v1 public-book fetch on the
        dry-run path entirely: every dry-run then books the old full-fill assumption (fill_model=
        "assumed_full"), deterministically and with zero network calls. This is the supported OFFLINE seam
        for tests/backtests -- prefer it over monkeypatching the private _fetch_orderbook function."""
        self.base = base
        self.log_path = log_path
        self.fetch_book = bool(fetch_book) and os.environ.get("KWX_NO_BOOK_FETCH") != "1"
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
        None, the dry-run books avg_price_cents at max_price_cents (conservative). The dry-run FILL
        COUNT is depth-aware (fill_model="depth_v1"): capped at the displayed public-book depth within
        the cap at fire time, possibly 0 -- falling back to full-fill ("assumed_full") only if the book
        can't be read. See _sim_depth_fill for why (honest paper EV)."""
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
            # default = the OLD assumption (full fill at cap), tagged so analysis can tell it apart; the
            # depth model below OVERWRITES filled/fill_model when the public book is actually readable.
            r = {"status": "DRY_RUN", "ticker": ticker, "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order,
                 "fill_model": "assumed_full"}
            if self.fetch_book:
                book = _fetch_orderbook(ticker)
                if book is not None:   # None = fetch failed -> fail open on the assumed-full record above
                    r.update(_sim_depth_fill(book, "yes", count, max_price_cents))
            self._log(r)
            return r
        # ---- live path (only reached when KWX_LIVE=1 AND creds present) ----
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        try:
            resp = _get(self.base.replace("/trade-api/v2", "") + path, timeout=10,
                        method="POST", data=body, headers=self._headers("POST", path))
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
            # same honest-fill treatment as buy_yes: assumed_full is the fail-open default, depth_v1 when
            # the public book is readable (NO asks derived from resting YES bids -- see _sim_depth_fill).
            r = {"status": "DRY_RUN", "ticker": ticker, "side": "no", "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order,
                 "fill_model": "assumed_full"}
            if self.fetch_book:
                book = _fetch_orderbook(ticker)
                if book is not None:
                    r.update(_sim_depth_fill(book, "no", count, max_price_cents))
            self._log(r)
            return r
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        try:
            resp = _get(self.base.replace("/trade-api/v2", "") + path, timeout=10,
                        method="POST", data=body, headers=self._headers("POST", path))
            filled, ostatus = self._reconcile(resp, count)
            r = {"status": "live", "ticker": ticker, "side": "no", "requested": int(count),
                 "filled": filled, "order_status": ostatus, "response": resp}
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r


if __name__ == "__main__":
    ex = KalshiExec()
    print("LIVE ENABLED:", ex.live, "(needs KWX_LIVE=1 AND .kalshi_creds)")
    print("dry-run demo:", ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95, dry_fill_price=88))
