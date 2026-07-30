#!/usr/bin/env python3
"""lip_quoter.py -- LIP_PILOT quoting bot for Kalshi's Liquidity Incentive Program.

Implements the FROZEN policy in venue_expansion/LIP_PILOT_REGISTRATION.md. This file is the only
thing that ever places/amends/cancels a LIP order. It ships SAFE BY DEFAULT:

  - LIP_SWITCH must contain exactly 'on'                              -> else INERT (exit 0, silent)
  - .lip_halt must be ABSENT                                          -> else INERT (exit 0, silent)
  - KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY env vars must both be set
    and the private key must parse                                   -> else INERT (exit 0, silent)
  - even with all three satisfied, no live order is ever POSTed unless env LIP_LIVE == "1" ALSO
    holds (or dry-run mode is forced off) -- see `resolve_dry_run()`. Missing that, every mutating
    call is DRY_RUN: logged with full intended context, nothing sent to the exchange.

Every cap in the registration is enforced by the `Caps` class BEFORE any order is placed (see
`place_order` / `maybe_place_escalation`), and independently re-verified every cycle by
`self_audit()`, which recomputes exposure from the exchange's OWN /portfolio endpoints -- local
bookkeeping is never trusted alone. Any cap violation detected by self_audit, or a cumulative
realized-loss breach, takes the SAME hard path as a bug: write .lip_halt, batch-cancel every
LIP- order, and fire a Telegram alert (best-effort, never raises).

Single-file, stdlib + `cryptography` only (matches the repo's proven GHA deployment reality --
see ENGINEERING_STACK.md). One persistent HTTPS session (keep-alive), RSA key held in memory for
the life of the process -- the ~500-650x subprocess/reconnect tax documented in
ENGINEERING_STACK.md section 2/3 is exactly what a warm --max-seconds leg avoids.

Usage:
    python lip_quoter.py --once                  # single cycle, exit
    python lip_quoter.py --max-seconds 900        # warm loop bounded to ~15 minutes (GHA leg)
    python lip_quoter.py --dry-run --max-seconds 900   # force dry-run regardless of LIP_LIVE

MONEY UNITS: every cent-denominated quantity in this file is an int number of US cents. This is
deliberate -- the registration's caps ($1000/$300/$100/$25/$100, all with hard <= semantics) must
be enforced exactly at the boundary, and IEEE-754 float comparison is the wrong tool for "exactly
at cap = allowed" arithmetic. Never introduce a float dollar amount into a cap comparison.
"""
import argparse
import base64
import datetime as dt
import http.client
import json
import os
import ssl
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------------------------
# Paths (module-level so tests can monkeypatch them directly, e.g. `lip_quoter.SWITCH_FILE = x`)
# ---------------------------------------------------------------------------------------------
SWITCH_FILE = os.path.join(HERE, "LIP_SWITCH")
HALT_FILE = os.path.join(HERE, ".lip_halt")
STOP_TODAY_FILE = os.path.join(HERE, ".lip_stop_today")
MARKETS_FILE = os.path.join(HERE, "lip_markets.json")
LOG_FILE = os.path.join(HERE, "lip_pilot_log.jsonl")
HEARTBEAT_FILE = os.path.join(HERE, ".lip_heartbeat")
PAYOUTS_FILE = os.path.join(HERE, "lip_payouts.jsonl")

_CA = "/root/.ccr/ca-bundle.crt"
KALSHI_HOST = "api.elections.kalshi.com"
KALSHI_BASE_PATH = "/trade-api/v2"

CID_PREFIX = "LIP-"                          # every order this bot places/owns starts with this
KWX_CONFLICT_PREFIXES = ("KXHIGH", "KXLOW")  # never quote the same series as a live kwx position
LOOP_POLL_SECONDS = 20.0                     # cadence within a warm leg


# =================================================================================================
# Caps -- single source of truth for every registered hard cap. ALL enforced BEFORE order placement
# (place_order / maybe_place_escalation below) AND independently cross-checked each cycle against
# the exchange's own numbers by self_audit(). Cents-integer arithmetic throughout (see module note).
# =================================================================================================
class Caps:
    """Registration caps (venue_expansion/LIP_PILOT_REGISTRATION.md, 'Hard caps' table).

    Semantics, decided explicitly (registration wording is "<= X"):
      - RESOURCE ceilings (collateral, cost basis, resting-order cost, per-market position,
        per-order size): "<= cap" is an ALLOWED range -- landing exactly ON the cap is allowed,
        the first unit that would push the projected total past the cap is blocked.
      - LOSS ceilings (daily realized loss, cumulative realized loss): the registration states the
        cap value immediately followed by the consequence ("<= $25 -> halt for the day"), i.e. the
        cap IS the trigger threshold. Fail-closed: reaching the threshold (loss >= cap) halts, it
        does not wait for the loss to exceed it. This is deliberately the more conservative of the
        two readings, appropriate for a kill path.
    """

    # ---- resource ceilings (cents) ----
    ACCOUNT_COLLATERAL_MAX_CENTS = 100_000        # <= $1,000
    OPEN_POSITION_COST_BASIS_MAX_CENTS = 30_000    # <= $300
    RESTING_ORDER_COST_MAX_CENTS = 10_000          # <= $100
    PER_ORDER_SIZE_CT = 1                          # exactly 1 contract (escalation is the ONE exception)
    PER_MARKET_POSITION_MAX_CT = 10                # <= 10 contracts, per side, per market

    # ---- loss ceilings (cents) -- reaching them halts (see docstring) ----
    DAILY_REALIZED_LOSS_MAX_CENTS = 2_500           # <= $25/day -> stop for the day
    CUMULATIVE_REALIZED_LOSS_MAX_CENTS = 10_000     # <= $100 total -> hard stop, pilot over

    # ---- the single pre-registered escalation step ----
    ESCALATION_SIZE_CT = 100
    ESCALATION_MAX_PRICE_CENTS = 15                 # cost-if-filled <= $15
    ESCALATION_MIN_REST_DAYS = 2
    ESCALATION_ZERO_PAYOUT_DAYS = 4                 # documentation constant only; see maybe_place_escalation

    # ---- quote policy ----
    LADDER_CENTS = (1, 3, 5, 8)
    RECENTER_TRIGGER_CENTS = 2
    MAX_AMENDS_PER_ORDER_PER_MIN = 1
    MIN_PRICE_CENTS = 1
    MAX_PRICE_CENTS = 99

    # ---- market selection ----
    MAX_MARKETS = 5
    MIN_MARKETS = 3

    # ------------------------------------------------------------------ resource-ceiling checks --
    @classmethod
    def order_size_ok(cls, size_ct, is_escalation=False):
        if is_escalation:
            return size_ct == cls.ESCALATION_SIZE_CT
        return size_ct == cls.PER_ORDER_SIZE_CT

    @classmethod
    def market_position_ok(cls, projected_ct):
        """<=10 allowed (both directions); 11 (or -11) blocked."""
        return abs(projected_ct) <= cls.PER_MARKET_POSITION_MAX_CT

    @classmethod
    def cost_basis_ok_cents(cls, projected_cents):
        return projected_cents <= cls.OPEN_POSITION_COST_BASIS_MAX_CENTS

    @classmethod
    def resting_cost_ok_cents(cls, projected_cents):
        return projected_cents <= cls.RESTING_ORDER_COST_MAX_CENTS

    @classmethod
    def collateral_ok_cents(cls, projected_cents):
        return projected_cents <= cls.ACCOUNT_COLLATERAL_MAX_CENTS

    # ---------------------------------------------------------------------- loss-ceiling checks --
    @classmethod
    def daily_loss_halt(cls, realized_loss_cents):
        return realized_loss_cents >= cls.DAILY_REALIZED_LOSS_MAX_CENTS

    @classmethod
    def cumulative_loss_hardstop(cls, realized_loss_cents):
        return realized_loss_cents >= cls.CUMULATIVE_REALIZED_LOSS_MAX_CENTS

    @classmethod
    def escalation_cost_ok_cents(cls, price_cents, size_ct=ESCALATION_SIZE_CT):
        return price_cents <= cls.ESCALATION_MAX_PRICE_CENTS and price_cents * size_ct <= 1500

    # -------------------------------------------------------------------------------- self-audit --
    @classmethod
    def audit(cls, resting_order_cost_cents, open_position_cost_basis_cents, collateral_cents,
               per_market_positions, escalation_market=None):
        """Given numbers RECOMPUTED FROM THE EXCHANGE (never from local running totals), return the
        list of cap names currently violated (empty == clean). Called every cycle by self_audit();
        any non-empty result triggers the hard kill path (batch-cancel + halt + alert), because by
        definition the bot's own placement-time checks should have made this impossible -- a
        violation here means state has drifted from what we intended, i.e. a bug."""
        violations = []
        if not cls.resting_cost_ok_cents(resting_order_cost_cents):
            violations.append("resting_order_cost")
        if not cls.cost_basis_ok_cents(open_position_cost_basis_cents):
            violations.append("open_position_cost_basis")
        if not cls.collateral_ok_cents(collateral_cents):
            violations.append("account_collateral")
        for ticker, pos in (per_market_positions or {}).items():
            limit = cls.PER_MARKET_POSITION_MAX_CT
            if escalation_market is not None and ticker == escalation_market:
                # The armed, pre-registered escalation order (exactly 100ct, <=15c) may
                # legitimately fill -- same documented judgment call as its placement-time bypass
                # in place_order; without this the registered step would kill its own pilot.
                limit += cls.ESCALATION_SIZE_CT
            if abs(pos) > limit:
                violations.append(f"per_market_position:{ticker}")
        return violations


# =================================================================================================
# Logging -- append-only JSONL. Every place/amend/cancel/decrease/fill/snapshot/payout-check/gate/
# cap_block/kill event goes through here with a ts + full context.
# =================================================================================================
def _now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def log_event(kind, path=None, **fields):
    path = path or LOG_FILE
    rec = {"ts": _now_iso(), "event": kind}
    rec.update(fields)
    line = json.dumps(rec, sort_keys=True, default=str)
    with open(path, "a") as fh:
        fh.write(line + "\n")
    return rec


def load_log_events(path=None):
    path = path or LOG_FILE
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def write_heartbeat(path=None):
    path = path or HEARTBEAT_FILE
    with open(path, "w") as fh:
        fh.write(_now_iso() + "\n")


# =================================================================================================
# Telegram alert -- best effort, fire-and-forget, NEVER raises into the trading loop. Reuses the
# existing repo's env var names (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID), same pattern as kwx_notify.py.
# =================================================================================================
def telegram_alert(msg):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        ctx = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else ssl.create_default_context()
        data = json.dumps({"chat_id": chat, "text": msg[:4000]}).encode()
        conn = http.client.HTTPSConnection("api.telegram.org", timeout=8, context=ctx)
        conn.request("POST", f"/bot{tok}/sendMessage", body=data, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        ok = resp.status == 200
        conn.close()
        return ok
    except Exception as e:
        print(f"[lip_quoter] telegram alert failed: {type(e).__name__}: {e}", flush=True)
        return False


# =================================================================================================
# Kalshi auth -- RSA-PSS-SHA256 over `timestamp_ms + METHOD + path`, exactly Kalshi's documented
# scheme (mirrors the box's existing kalshi_exec.py signing code so any drift is visible/reviewable).
# =================================================================================================
def load_signing_creds():
    """Best-effort load of (key_id, private_key_obj) from KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY.
    Returns (None, None) on ANY failure -- never raises -- so the secrets gate can treat that as
    'secrets not present' cleanly. Catches BaseException because a broken `cryptography` native
    build can raise a pyo3 PanicException (subclasses BaseException, not Exception)."""
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        key_id = os.environ.get("KALSHI_API_KEY_ID")
        pem = os.environ.get("KALSHI_PRIVATE_KEY")
        if not key_id or not pem:
            return None, None
        priv = load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)
        return key_id, priv
    except BaseException:
        return None, None


def rsa_sign(priv, ts_ms, method, path):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    msg = f"{ts_ms}{method}{path}".encode()
    sig = priv.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode()


def auth_headers(key_id, priv, method, path):
    ts = str(int(time.time() * 1000))
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": rsa_sign(priv, ts, method, path),
    }


# =================================================================================================
# KalshiClient -- ONE persistent HTTPS session (http.client.HTTPSConnection kept alive across the
# whole warm leg; ENGINEERING_STACK.md section 3: reconnect penalty is ~500-655ms, a cold connect
# at the wrong moment burns most of the reaction budget, so the connection is opened once in
# __init__ and only ever re-opened on demonstrated failure).
#
# PORTFOLIO SCHEMA NOTE: this environment has no live Kalshi credentials, so the exact field names
# returned by GET /portfolio/positions / /portfolio/balance / /portfolio/orders could not be
# confirmed against a live authenticated call (same limitation orderpath_research.json flags for
# every endpoint-cost number). Every parse below uses .get() with a safe default and is written so
# that a missing/renamed field degrades to "0" or "unknown" rather than raising -- and self_audit()
# treats an outright API failure (not just an unexpected field) as a suspected cap violation and
# takes the hard kill path, never as "assume clean and keep trading". CONFIRM the schema against a
# live GET before the switch is ever flipped to on (see LIP_PILOT_README.md checklist).
# =================================================================================================
class KalshiClient:
    def __init__(self, key_id, priv, host=KALSHI_HOST, timeout=10):
        self.key_id = key_id
        self.priv = priv
        self.host = host
        self.timeout = timeout
        self._ctx = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else ssl.create_default_context()
        self._conn = None
        self._connect()

    def _connect(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = http.client.HTTPSConnection(self.host, timeout=self.timeout, context=self._ctx)

    def _request(self, method, path, query=None, body=None, retries=2):
        full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = auth_headers(self.key_id, self.priv, method, path)
        headers["Accept"] = "application/json"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        last_exc = None
        for attempt in range(retries + 1):
            try:
                self._conn.request(method, full_path, body=data, headers=headers)
                resp = self._conn.getresponse()
                raw = resp.read()
                status = resp.status
                try:
                    parsed = json.loads(raw) if raw else {}
                except Exception:
                    parsed = {"_raw": raw.decode(errors="replace")}
                return status, parsed
            except Exception as e:
                last_exc = e
                self._connect()
        raise RuntimeError(f"kalshi request failed after {retries} retries: {last_exc}")

    # ---- reads ----
    def get_orderbook(self, ticker):
        status, body = self._request("GET", f"{KALSHI_BASE_PATH}/markets/{ticker}/orderbook")
        if status != 200:
            return None
        return body.get("orderbook", body)

    def list_orders(self, status_filter="resting", ticker=None):
        q = {}
        if status_filter:
            q["status"] = status_filter
        if ticker:
            q["ticker"] = ticker
        status, body = self._request("GET", f"{KALSHI_BASE_PATH}/portfolio/orders", query=q)
        if status != 200:
            return None
        return body.get("orders", [])

    def get_positions(self):
        status, body = self._request("GET", f"{KALSHI_BASE_PATH}/portfolio/positions")
        if status != 200:
            return None
        return body.get("market_positions", [])

    def get_balance(self):
        status, body = self._request("GET", f"{KALSHI_BASE_PATH}/portfolio/balance")
        if status != 200:
            return None
        return body.get("balance")

    # ---- writes (mutating; caller must have already decided dry-run does NOT apply) ----
    def create_order(self, ticker, side, action, price_cents, count, client_order_id):
        body = {
            "ticker": ticker, "side": side, "action": action, "count": count,
            "type": "limit", "time_in_force": "good_till_canceled",
            "client_order_id": client_order_id,
        }
        body["yes_price" if side == "yes" else "no_price"] = price_cents
        status, resp = self._request("POST", f"{KALSHI_BASE_PATH}/portfolio/orders", body=body)
        return status, resp

    def amend_order(self, order_id, price_cents, count):
        # NOTE: path corrected in safety review (had a stray "events/" segment, not a Kalshi
        # route -- every amend would have 404'd and quotes would never re-center). The BODY schema
        # (bare "price" vs side-specific yes_price/no_price + side/ticker fields) is part of the
        # unconfirmed-schema set in the PORTFOLIO SCHEMA NOTE above: a wrong body fails inert
        # (4xx logged, order left as-is), but MUST be confirmed against a live authenticated call
        # before LIP_LIVE=1 -- see LIP_PILOT_README.md pre-flight checklist.
        body = {"price": price_cents, "count": count}
        status, resp = self._request("POST", f"{KALSHI_BASE_PATH}/portfolio/orders/{order_id}/amend", body=body)
        return status, resp

    def decrease_order(self, order_id, reduce_to=None, reduce_by=None):
        body = {}
        if reduce_to is not None:
            body["reduce_to"] = reduce_to
        elif reduce_by is not None:
            body["reduce_by"] = reduce_by
        status, resp = self._request("POST", f"{KALSHI_BASE_PATH}/portfolio/orders/{order_id}/decrease", body=body)
        return status, resp

    def cancel_order(self, order_id):
        status, resp = self._request("DELETE", f"{KALSHI_BASE_PATH}/portfolio/orders/{order_id}")
        return status, resp

    def batch_cancel(self, order_ids):
        if not order_ids:
            return 200, {"cancelled": []}
        body = {"ids": list(order_ids)}
        status, resp = self._request("POST", f"{KALSHI_BASE_PATH}/portfolio/orders/batch_cancel", body=body)
        return status, resp


# =================================================================================================
# Gates -- evaluated in order at startup AND every loop iteration. Any failure => caller treats the
# whole process as inert. `secrets_ok` is only checked if a client-construction attempt is needed;
# callers pass a pre-resolved key_id/priv pair so this stays a pure function (no I/O beyond the two
# file reads), easy to unit test.
# =================================================================================================
class GateResult:
    def __init__(self, ok, reason=None):
        self.ok = ok
        self.reason = reason

    def __bool__(self):
        return self.ok


def check_gates(switch_file=None, halt_file=None, key_id=None, priv=None):
    switch_file = switch_file or SWITCH_FILE
    halt_file = halt_file or HALT_FILE
    try:
        with open(switch_file) as fh:
            sw = fh.read().strip()
    except Exception:
        sw = "off"
    if sw != "on":
        return GateResult(False, "switch_not_on")
    if os.path.exists(halt_file):
        return GateResult(False, "halt_file_present")
    if key_id is None or priv is None:
        return GateResult(False, "secrets_missing")
    return GateResult(True)


def resolve_dry_run(cli_dry_run_flag, switch_state_on, secrets_ok):
    """dry-run is the default UNLESS env LIP_LIVE=1 AND the switch reads on; an explicit --dry-run
    flag always forces dry-run regardless of LIP_LIVE (the operator asked for a rehearsal)."""
    if cli_dry_run_flag:
        return True
    live_env = os.environ.get("LIP_LIVE") == "1"
    return not (live_env and switch_state_on and secrets_ok)


# =================================================================================================
# Market selection -- lip_markets.json, operator-authored at Day-0 recon. Refuses to run if absent,
# >5 markets, <3 markets, or any series collides with a live kwx weather position (KXHIGH*/KXLOW*).
# =================================================================================================
class MarketConfigError(Exception):
    pass


def load_market_config(path=None):
    path = path or MARKETS_FILE
    if not os.path.exists(path):
        raise MarketConfigError("lip_markets.json missing -- operator must author it at Day-0 recon")
    with open(path) as fh:
        cfg = json.load(fh)
    markets = cfg.get("markets")
    if not isinstance(markets, list) or not markets:
        raise MarketConfigError("lip_markets.json has no 'markets' list")
    if len(markets) > Caps.MAX_MARKETS:
        raise MarketConfigError(f"lip_markets.json lists {len(markets)} markets, cap is {Caps.MAX_MARKETS}")
    tickers = []
    for m in markets:
        ticker = m.get("ticker") if isinstance(m, dict) else m
        if not ticker:
            raise MarketConfigError("a market entry is missing 'ticker'")
        series = (m.get("series") if isinstance(m, dict) else None) or ticker
        if any(series.upper().startswith(p) or ticker.upper().startswith(p) for p in KWX_CONFLICT_PREFIXES):
            raise MarketConfigError(f"market {ticker} collides with the kwx conflict guard ({KWX_CONFLICT_PREFIXES})")
        tickers.append(ticker)
    if len(set(tickers)) != len(tickers):
        raise MarketConfigError("duplicate tickers in lip_markets.json")
    return cfg


# =================================================================================================
# Daily ladder rotation -- deterministic from the UTC date, NO RNG at runtime. Every selected market
# always carries the full {1,3,5,8}c ladder on both quoted sides (that is what makes the discount
# curve identifiable within EVERY market, every day -- the richer signal than partitioning distances
# across markets). What genuinely needs a daily, deterministic rotation is the ORDER markets are
# processed/refreshed in each leg, so that under a rate-limit or partial-leg timeout the same market
# doesn't always win the front of the queue for re-centering/reconciliation. This is the explicit,
# documented interpretation of the registration's "ladder assignments rotate daily across markets"
# line -- flagged here (and in LIP_PILOT_README.md) as a judgment call on ambiguous wording, not a
# silent decision.
# =================================================================================================
def date_ordinal(date_iso):
    return dt.date.fromisoformat(date_iso).toordinal()


def market_processing_order(date_iso, tickers):
    tickers = list(tickers)
    n = len(tickers)
    if n == 0:
        return []
    offset = date_ordinal(date_iso) % n
    return tickers[offset:] + tickers[:offset]


def rung_prices(touch_cents, distances=Caps.LADDER_CENTS):
    """Resting-buy ladder prices below the touch, clamped to the legal [1,99]c price range."""
    out = {}
    for d in distances:
        p = touch_cents - d
        p = max(Caps.MIN_PRICE_CENTS, min(Caps.MAX_PRICE_CENTS, p))
        out[d] = p
    return out


def needs_recenter(current_order_price_cents, desired_price_cents, trigger=Caps.RECENTER_TRIGGER_CENTS):
    return abs(desired_price_cents - current_order_price_cents) >= trigger


def amend_allowed(last_amend_ts, now_ts, max_per_min=Caps.MAX_AMENDS_PER_ORDER_PER_MIN):
    min_interval = 60.0 / max_per_min
    return (now_ts - last_amend_ts) >= min_interval


def client_order_id(ticker, side, distance_cents, is_escalation=False):
    if is_escalation:
        return f"{CID_PREFIX}ESC-{ticker}"
    return f"{CID_PREFIX}{ticker}-{side}-{distance_cents}c"


def parse_cid_distance_cents(cid):
    """Inverse of client_order_id() for ladder orders: 'LIP-{ticker}-{side}-{d}c' -> d.
    rsplit from the end because Kalshi tickers themselves contain hyphens. Returns None for the
    escalation id or anything unparseable -- callers must key such orders by order_id instead of
    guessing a distance."""
    cid = str(cid or "")
    if not cid.startswith(CID_PREFIX) or cid.startswith(CID_PREFIX + "ESC-"):
        return None
    tail = cid.rsplit("-", 1)[-1]
    if not tail.endswith("c"):
        return None
    try:
        return int(tail[:-1])
    except ValueError:
        return None


# =================================================================================================
# Runtime state -- everything durable is either (a) reconstructed from the exchange each cycle via
# self_audit(), or (b) reconstructed from lip_pilot_log.jsonl, which IS committed every leg by the
# workflow. Nothing load-bearing lives only in an uncommitted local file, because a GHA leg is a
# fresh checkout every time -- an uncommitted state file would silently reset every ~15 minutes.
# =================================================================================================
class RuntimeState:
    def __init__(self):
        self.resting_by_market = {}          # ticker -> {side -> {distance_cents: order dict}}
        self.positions = {}                  # ticker -> {"yes": ct, "no": ct}
        self.resting_order_cost_cents = 0
        self.open_position_cost_basis_cents = 0
        self.collateral_committed_cents = 0
        self.last_amend_ts = {}              # order_id -> ts
        self.escalation_placed_date = None

    def position(self, ticker, side):
        return self.positions.get(ticker, {}).get(side, 0)

    def projected_resting_cost_cents(self, add_cents):
        return self.resting_order_cost_cents + add_cents

    def projected_collateral_cents(self, add_cents):
        return self.collateral_committed_cents + add_cents


def prev_positions_from_log(log_events):
    """Most recently logged per-market position snapshot, used ONLY to detect fills (a position
    delta between consecutive snapshots) -- diffed against this cycle's self_audit() positions."""
    snaps = [e for e in log_events if e.get("event") == "snapshot" and "per_market_positions" in e]
    return snaps[-1]["per_market_positions"] if snaps else {}


def detect_and_log_fills(prev_positions, current_positions, log_path=None):
    """Log a 'fill' event for every per-market position change since the last snapshot. This is a
    position-delta inference, not a read of Kalshi's own per-fill ledger (no confirmed
    /portfolio/fills schema was available to build against in this environment -- see the
    PORTFOLIO SCHEMA NOTE on KalshiClient); it is documented here as the deliberate v1 choice."""
    fills = []
    for ticker, pos in (current_positions or {}).items():
        prev = (prev_positions or {}).get(ticker, 0)
        delta = pos - prev
        if delta != 0:
            rec = log_event("fill", path=log_path, ticker=ticker, position_delta=delta,
                             position_before=prev, position_after=pos)
            fills.append(rec)
    return fills


def pnl_baselines(log_events, today_iso):
    """Reconstruct pilot-start and day-start realized-pnl baselines from our OWN committed log
    (the exchange has no notion of 'pilot start' or 'trading day boundary' for us). First-ever run
    has no snapshots yet -> both baselines equal the current total once this cycle logs its own
    snapshot, i.e. loss is correctly zero on cycle 1."""
    snaps = [e for e in log_events if e.get("event") == "snapshot" and "total_realized_pnl_cents" in e]
    if not snaps:
        return None, None
    pilot_start = snaps[0]["total_realized_pnl_cents"]
    today_snaps = [e for e in snaps if str(e.get("ts", "")).startswith(today_iso)]
    day_start = today_snaps[0]["total_realized_pnl_cents"] if today_snaps else snaps[-1]["total_realized_pnl_cents"]
    return pilot_start, day_start


# =================================================================================================
# Self-audit -- recomputes exposure from the exchange's OWN /portfolio endpoints every cycle. Any
# outright API failure is treated as a SUSPECTED cap violation (fail closed: never trade blind).
# =================================================================================================
class SelfAuditFailure(Exception):
    pass


def self_audit(client, tickers):
    orders = client.list_orders(status_filter="resting")
    positions = client.get_positions()
    if orders is None or positions is None:
        raise SelfAuditFailure("portfolio API call failed -- treating as suspected cap violation")

    ticker_set = set(tickers)
    lip_orders = []
    resting_order_cost_cents = 0
    for o in orders:
        cid = str(o.get("client_order_id", ""))
        if not cid.startswith(CID_PREFIX) or o.get("ticker") not in ticker_set:
            continue
        price = o.get("price")
        if price is None:
            price = o.get("yes_price") if o.get("side") == "yes" else o.get("no_price")
        count = o.get("remaining_count", o.get("count"))
        if price is None or count is None:
            # FAIL CLOSED on schema drift: a renamed price/size field would otherwise silently
            # zero the resting-cost/collateral caps ("assume clean and keep trading" is exactly
            # what this function exists to prevent). Same hard path as an API outage.
            raise SelfAuditFailure(f"order schema missing price/count for {cid}: keys={sorted(o)}")
        o["price"] = int(price)  # normalized for every downstream comparison
        o["_distance_cents"] = parse_cid_distance_cents(cid)
        lip_orders.append(o)
        resting_order_cost_cents += int(price) * int(count)

    per_market_positions = {}
    open_position_cost_basis_cents = 0
    total_realized_pnl_cents = 0
    for mp in positions:
        ticker = mp.get("ticker")
        if ticker not in ticker_set:
            continue
        missing = [k for k in ("position", "market_exposure", "realized_pnl") if k not in mp]
        if missing:
            # FAIL CLOSED: silent-zero here would disable the cost-basis cap AND both loss caps.
            raise SelfAuditFailure(f"position schema missing {missing} for {ticker}: keys={sorted(mp)}")
        pos = int(mp["position"])
        per_market_positions[ticker] = pos
        open_position_cost_basis_cents += abs(int(mp["market_exposure"]))
        total_realized_pnl_cents += int(mp["realized_pnl"])

    collateral_committed_cents = resting_order_cost_cents + open_position_cost_basis_cents

    resting_by_market = {}
    for o in lip_orders:
        cid = str(o.get("client_order_id", ""))
        if cid.startswith(CID_PREFIX + "ESC-"):
            continue  # the escalation order is never ladder-maintained (never amended/re-centered)
        t = o.get("ticker")
        side = o.get("side")
        d = o.get("_distance_cents")
        # key by parsed distance; unparseable -> unique order_id key so orders can NEVER collapse
        # onto one another (a collapsed map hides rungs from maintenance and re-places duplicates).
        key = d if d is not None else f"oid:{o.get('order_id')}"
        resting_by_market.setdefault(t, {}).setdefault(side, {})[key] = o

    return {
        "lip_orders": lip_orders,
        "resting_order_cost_cents": resting_order_cost_cents,
        "open_position_cost_basis_cents": open_position_cost_basis_cents,
        "collateral_committed_cents": collateral_committed_cents,
        "per_market_positions": per_market_positions,
        "total_realized_pnl_cents": total_realized_pnl_cents,
        "resting_by_market": resting_by_market,
    }


# =================================================================================================
# Order execution helpers -- caps are enforced HERE, immediately before any mutating call. `dry_run`
# short-circuits every one of these to a log line ("does everything except POST orders").
# =================================================================================================
def place_order(client, state, ticker, side, price_cents, distance_cents, dry_run, is_escalation=False,
                 log_path=None):
    size_ct = Caps.ESCALATION_SIZE_CT if is_escalation else Caps.PER_ORDER_SIZE_CT
    cid = client_order_id(ticker, side, distance_cents, is_escalation=is_escalation)

    if not Caps.order_size_ok(size_ct, is_escalation=is_escalation):
        log_event("cap_block", cap="per_order_size", ticker=ticker, side=side, size_ct=size_ct, path=log_path)
        return None
    if not (Caps.MIN_PRICE_CENTS <= price_cents <= Caps.MAX_PRICE_CENTS):
        log_event("cap_block", cap="price_bounds", ticker=ticker, side=side, price_cents=price_cents, path=log_path)
        return None
    if is_escalation and not Caps.escalation_cost_ok_cents(price_cents, size_ct):
        log_event("cap_block", cap="escalation_cost", ticker=ticker, price_cents=price_cents, path=log_path)
        return None

    # The per-market-position cap (<=10ct) governs the normal 1-contract-ladder regime. The
    # registration's escalation step is explicitly "the only exception" to that regime -- its own
    # text asserts a 100-contract order at <=15c is "inside all caps" ("cost-if-filled <= $15"),
    # which is only true if the caps meant are the DOLLAR caps (collateral/cost-basis/resting-cost,
    # all checked below and trivially satisfied at $15) rather than the count-based per-order-size/
    # per-market-position caps that a 100-contract order mechanically cannot satisfy. Documented
    # judgment call on the frozen spec, same as the ladder-rotation interpretation above.
    if not is_escalation:
        # Positions are a SIGNED net-yes count (Kalshi /portfolio/positions convention, mirrored by
        # self_audit into state.positions[t]["yes"]): a filled yes-buy moves it +1, a filled no-buy
        # moves it -1. Project the signed value and cap |projection| -- projecting the "no" key
        # would always read 0 and never block the no side.
        delta_ct = size_ct if side == "yes" else -size_ct
        projected_position = state.position(ticker, "yes") + delta_ct
        if not Caps.market_position_ok(projected_position):
            log_event("cap_block", cap="per_market_position", ticker=ticker, side=side,
                       projected=projected_position, path=log_path)
            return None

    add_cents = price_cents * size_ct
    projected_resting = state.projected_resting_cost_cents(add_cents)
    if not Caps.resting_cost_ok_cents(projected_resting):
        log_event("cap_block", cap="resting_order_cost", ticker=ticker, side=side,
                   projected_cents=projected_resting, path=log_path)
        return None

    projected_collateral = state.projected_collateral_cents(add_cents)
    if not Caps.collateral_ok_cents(projected_collateral):
        log_event("cap_block", cap="account_collateral", ticker=ticker, side=side,
                   projected_cents=projected_collateral, path=log_path)
        return None

    if dry_run:
        log_event("place_dry_run", path=log_path, ticker=ticker, side=side, price_cents=price_cents,
                   size_ct=size_ct, distance_cents=distance_cents, client_order_id=cid,
                   is_escalation=is_escalation)
        state.resting_order_cost_cents += add_cents
        state.collateral_committed_cents += add_cents
        return {"status": "DRY_RUN", "client_order_id": cid}

    status, resp = client.create_order(ticker, side, "buy", price_cents, size_ct, cid)
    log_event("place", path=log_path, ticker=ticker, side=side, price_cents=price_cents, size_ct=size_ct,
              distance_cents=distance_cents, client_order_id=cid, is_escalation=is_escalation,
              http_status=status, response=resp)
    if status in (200, 201):
        state.resting_order_cost_cents += add_cents
        state.collateral_committed_cents += add_cents
    return resp


def amend_order(client, state, order, desired_price_cents, dry_run, now_ts, log_path=None):
    order_id = order.get("order_id")
    last_ts = state.last_amend_ts.get(order_id, 0.0)
    if not amend_allowed(last_ts, now_ts):
        log_event("amend_rate_limited", path=log_path, order_id=order_id,
                   ticker=order.get("ticker"), path_field=None)
        return None
    if dry_run:
        log_event("amend_dry_run", path=log_path, order_id=order_id, ticker=order.get("ticker"),
                   from_price_cents=order.get("price"), to_price_cents=desired_price_cents)
        state.last_amend_ts[order_id] = now_ts
        return {"status": "DRY_RUN"}
    count = order.get("remaining_count", order.get("count", Caps.PER_ORDER_SIZE_CT))
    status, resp = client.amend_order(order_id, desired_price_cents, count)
    log_event("amend", path=log_path, order_id=order_id, ticker=order.get("ticker"),
               from_price_cents=order.get("price"), to_price_cents=desired_price_cents,
               http_status=status, response=resp)
    state.last_amend_ts[order_id] = now_ts
    return resp


def decrease_order_to_zero(client, order, dry_run, reason, log_path=None):
    """Position-cap side-stop removal path: decrease-to-zero rather than cancel, per
    ENGINEERING_STACK.md section 7.3 ('decrease, never cancel-replace, to downsize') -- the
    documented priority-preserving primitive, used here even for full removal so every size-
    reducing code path in this bot goes through the same, single, reviewed primitive."""
    order_id = order.get("order_id")
    if dry_run:
        log_event("decrease_dry_run", path=log_path, order_id=order_id, ticker=order.get("ticker"),
                   reduce_to=0, reason=reason)
        return {"status": "DRY_RUN"}
    status, resp = client.decrease_order(order_id, reduce_to=0)
    log_event("decrease", path=log_path, order_id=order_id, ticker=order.get("ticker"), reduce_to=0,
               reason=reason, http_status=status, response=resp)
    return resp


def cancel_order(client, order, dry_run, reason, log_path=None):
    order_id = order.get("order_id")
    if dry_run:
        log_event("cancel_dry_run", path=log_path, order_id=order_id, ticker=order.get("ticker"), reason=reason)
        return {"status": "DRY_RUN"}
    status, resp = client.cancel_order(order_id)
    log_event("cancel", path=log_path, order_id=order_id, ticker=order.get("ticker"), reason=reason,
              http_status=status, response=resp)
    return resp


def batch_cancel_all_lip_orders(client, dry_run, reason, log_path=None):
    orders = client.list_orders(status_filter="resting") or []
    lip_orders = [o for o in orders if str(o.get("client_order_id", "")).startswith(CID_PREFIX)]
    order_ids = [o.get("order_id") for o in lip_orders]
    if dry_run:
        log_event("batch_cancel_dry_run", path=log_path, order_ids=order_ids, reason=reason)
        return {"status": "DRY_RUN", "order_ids": order_ids}
    status, resp = client.batch_cancel(order_ids)
    log_event("batch_cancel", path=log_path, order_ids=order_ids, reason=reason, http_status=status,
              response=resp)
    return resp


# =================================================================================================
# Kill paths
# =================================================================================================
def kill_pilot(client, dry_run, reason, detail=None, halt_file=None, log_path=None):
    """The hard path: cap-violation detection or cumulative-loss breach. Writing .lip_halt and
    alerting are LOCAL safety actions, not trades -- they happen UNCONDITIONALLY, dry-run or not,
    because a real self_audit() finding warrants permanently stopping future runs regardless of
    whether this particular leg was armed live. Only the batch-cancel of real resting orders is
    gated by dry_run (it is the one actual POST in this function)."""
    halt_file = halt_file or HALT_FILE
    # ORDER MATTERS, fail-closed: write .lip_halt FIRST and unconditionally. The most likely reason
    # we are in here is an exchange/network failure (SelfAuditFailure) -- the same failure would
    # make the batch-cancel below raise, and an exception BEFORE the halt-file write would leave
    # the pilot armed for the next chained leg. The halt file is the one action every future leg's
    # gate honors, so nothing is allowed to run before it.
    with open(halt_file, "w") as fh:
        fh.write(f"{reason} {_now_iso()}\n")
    log_event("kill", path=log_path, reason=reason, detail=detail)
    try:
        batch_cancel_all_lip_orders(client, dry_run, reason=reason, log_path=log_path)
    except Exception as e:
        # halt is already durable; the next (gated-off) manual intervention cancels leftovers.
        log_event("kill_batch_cancel_failed", path=log_path, reason=reason,
                  error=f"{type(e).__name__}: {e}")
    telegram_alert(f"LIP PILOT HALT: {reason}\n{detail or ''}")


def stop_for_day(reason, detail=None, stop_file=None, log_path=None, today_iso=None):
    stop_file = stop_file or STOP_TODAY_FILE
    today_iso = today_iso or dt.datetime.now(dt.timezone.utc).date().isoformat()
    log_event("stop_for_day", path=log_path, reason=reason, detail=detail, date=today_iso)
    with open(stop_file, "w") as fh:
        fh.write(f"{today_iso} {reason}\n")
    telegram_alert(f"LIP PILOT stop-for-day: {reason}\n{detail or ''}")


def stop_today_active(stop_file=None, today_iso=None):
    stop_file = stop_file or STOP_TODAY_FILE
    today_iso = today_iso or dt.datetime.now(dt.timezone.utc).date().isoformat()
    if not os.path.exists(stop_file):
        return False
    try:
        with open(stop_file) as fh:
            first_tok = fh.read().split()[0]
        return first_tok == today_iso
    except Exception:
        return True  # unreadable stop file -> fail closed, treat as active


# =================================================================================================
# Reconciliation -- at leg start: list open orders, adopt/cancel orphans tagged LIP-, recompute
# positions from the portfolio API.
# =================================================================================================
def expected_client_order_ids(tickers, escalation_cfg=None):
    ids = set()
    for t in tickers:
        for side in ("yes", "no"):
            for d in Caps.LADDER_CENTS:
                ids.add(client_order_id(t, side, d))
    if escalation_cfg and escalation_cfg.get("armed") and escalation_cfg.get("escalate_market"):
        ids.add(client_order_id(escalation_cfg["escalate_market"], "yes", 0, is_escalation=True))
    return ids


def reconcile(client, tickers, dry_run, escalation_cfg=None, log_path=None):
    orders = client.list_orders(status_filter="resting")
    if orders is None:
        raise SelfAuditFailure("could not list orders for reconciliation")
    lip_orders = [o for o in orders if str(o.get("client_order_id", "")).startswith(CID_PREFIX)]
    expected = expected_client_order_ids(tickers, escalation_cfg)
    adopted, orphans = [], []
    for o in lip_orders:
        if o.get("client_order_id") in expected:
            adopted.append(o)
        else:
            orphans.append(o)
    for o in orphans:
        cancel_order(client, o, dry_run, reason="orphan_reconcile", log_path=log_path)
    log_event("reconcile", path=log_path, adopted=len(adopted), orphans_cancelled=len(orphans),
              adopted_ids=[o.get("client_order_id") for o in adopted],
              orphan_ids=[o.get("client_order_id") for o in orphans])
    return adopted


# =================================================================================================
# Escalation -- the SINGLE pre-registered exception to 1-contract sizing. This code enforces the
# mechanics/caps (size==100, price<=15c, one market, >=2 days rest) but NEVER decides on its own,
# from payout data, that the escalation condition (>=4 days of $0.00 payout) has been met -- that
# judgment is the operator's, made from lip_pilot_report.py's falsifier view, recorded by manually
# setting "armed": true in lip_markets.json's "escalation" block. This function only executes an
# already-armed, already-decided escalation; it is not a decision engine.
# =================================================================================================
def maybe_place_escalation(client, state, cfg, tickers, orderbooks, dry_run, log_path=None,
                            resting_lip_orders=None):
    esc = cfg.get("escalation")
    if not esc or not esc.get("armed"):
        return None
    market = esc.get("escalate_market")
    if not market or market not in tickers:
        log_event("escalation_skipped", path=log_path, reason="escalate_market_not_in_lip_markets",
                   market=market)
        return None
    if state.escalation_placed_date is None:
        # CROSS-LEG idempotency: a fresh GHA leg starts with an empty RuntimeState, but "ONE order,
        # ever" must survive process restarts. Two durable witnesses, either one suffices:
        # (a) the escalation order is resting exchange-side right now; (b) the committed log
        # records a successful (or dry-run) escalation placement from an earlier leg.
        esc_cid = client_order_id(market, "yes", 0, is_escalation=True)
        if any(str(o.get("client_order_id", "")) == esc_cid for o in (resting_lip_orders or [])):
            state.escalation_placed_date = "adopted_resting"
        else:
            for e in load_log_events(log_path):
                if not e.get("is_escalation"):
                    continue
                if e.get("event") == "place_dry_run" or (
                        e.get("event") == "place" and e.get("http_status") in (200, 201)):
                    state.escalation_placed_date = str(e.get("ts", ""))[:10] or "logged"
                    break
    if state.escalation_placed_date is not None:
        return None  # idempotent -- only ever placed once
    book = orderbooks.get(market)
    touch = _touch_from_book(book, "yes") if book else None
    if touch is None:
        log_event("escalation_skipped", path=log_path, reason="no_touch", market=market)
        return None
    far_distance = max(Caps.LADDER_CENTS)
    price = max(Caps.MIN_PRICE_CENTS, min(touch - far_distance, Caps.ESCALATION_MAX_PRICE_CENTS))
    resp = place_order(client, state, market, "yes", price, far_distance, dry_run, is_escalation=True,
                        log_path=log_path)
    if resp is not None:
        state.escalation_placed_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    return resp


# =================================================================================================
# Quote-cycle logic
# =================================================================================================
def _touch_from_book(book, side):
    """side in {'yes','no'}: best (highest) resting bid price for that side, in cents.
    Orderbook shape assumed [[price_cents, size], ...] best-first OR unsorted -- max() is safe
    either way. Returns None if that side of the book is empty."""
    if not book:
        return None
    levels = book.get(side) or []
    prices = [lvl[0] for lvl in levels if isinstance(lvl, (list, tuple)) and len(lvl) >= 1]
    return max(prices) if prices else None


def run_cycle(client, cfg, tickers, state, dry_run, cycle_index, log_path=None):
    today_iso = dt.datetime.now(dt.timezone.utc).date().isoformat()
    now_ts = time.time()

    # 1) self-audit -- recompute exposure from the exchange, never trust local state alone.
    try:
        audit = self_audit(client, tickers)
    except SelfAuditFailure as e:
        kill_pilot(client, dry_run, reason="self_audit_failure", detail=str(e), log_path=log_path)
        return "halted"

    state.resting_order_cost_cents = audit["resting_order_cost_cents"]
    state.open_position_cost_basis_cents = audit["open_position_cost_basis_cents"]
    state.collateral_committed_cents = audit["collateral_committed_cents"]
    per_market_positions = audit["per_market_positions"]
    for t, pos in per_market_positions.items():
        state.positions.setdefault(t, {})["yes"] = pos  # signed net-yes convention, see self_audit()

    esc_cfg = cfg.get("escalation") or {}
    esc_market = esc_cfg.get("escalate_market") if esc_cfg.get("armed") else None
    violations = Caps.audit(audit["resting_order_cost_cents"], audit["open_position_cost_basis_cents"],
                             audit["collateral_committed_cents"], per_market_positions,
                             escalation_market=esc_market)
    if violations:
        kill_pilot(client, dry_run, reason="cap_violation_detected", detail=violations, log_path=log_path)
        return "halted"

    events = load_log_events(log_path)
    detect_and_log_fills(prev_positions_from_log(events), per_market_positions, log_path=log_path)

    log_event("snapshot", path=log_path, cycle=cycle_index,
              resting_order_cost_cents=audit["resting_order_cost_cents"],
              open_position_cost_basis_cents=audit["open_position_cost_basis_cents"],
              collateral_committed_cents=audit["collateral_committed_cents"],
              total_realized_pnl_cents=audit["total_realized_pnl_cents"],
              per_market_positions=per_market_positions)

    # 2) reconciliation, once per leg
    if cycle_index == 0:
        reconcile(client, tickers, dry_run, escalation_cfg=cfg.get("escalation"), log_path=log_path)

    # 3) loss kill paths, from OUR OWN committed log as the day/pilot baseline + exchange as the
    #    authoritative current total (see pnl_baselines docstring). Re-load: fill/snapshot events
    #    above just appended to the file.
    events = load_log_events(log_path)
    pilot_start, day_start = pnl_baselines(events, today_iso)
    if pilot_start is not None:
        current = audit["total_realized_pnl_cents"]
        cumulative_loss = max(0, pilot_start - current)
        daily_loss = max(0, day_start - current)
        if Caps.cumulative_loss_hardstop(cumulative_loss):
            kill_pilot(client, dry_run, reason="cumulative_realized_loss", detail=cumulative_loss,
                       log_path=log_path)
            return "halted"
        if Caps.daily_loss_halt(daily_loss) and not stop_today_active(today_iso=today_iso):
            stop_for_day("daily_realized_loss", detail=daily_loss, log_path=log_path, today_iso=today_iso)

    # 4) payout check (best-effort; LIP payouts are not confirmed to be API-visible -- see
    #    LIP_PILOT_REGISTRATION.md; this just records what's known from lip_payouts.jsonl, if any).
    _payout_check(log_path=log_path)

    if stop_today_active(today_iso=today_iso):
        write_heartbeat()
        return "stopped_for_day"

    # 5) quote maintenance, in the deterministic daily processing order
    order = market_processing_order(today_iso, tickers)
    orderbooks = {}
    for ticker in order:
        book = client.get_orderbook(ticker)
        orderbooks[ticker] = book
        _maintain_market(client, state, ticker, book, audit["resting_by_market"].get(ticker, {}),
                          dry_run, now_ts, log_path=log_path)

    # 6) escalation (only ever executes if the operator has explicitly armed it)
    maybe_place_escalation(client, state, cfg, tickers, orderbooks, dry_run, log_path=log_path,
                            resting_lip_orders=audit["lip_orders"])

    write_heartbeat()
    return "ok"


def _maintain_market(client, state, ticker, book, resting_by_side, dry_run, now_ts, log_path=None):
    if book is None:
        log_event("no_book", path=log_path, ticker=ticker)
        return
    for side in ("yes", "no"):
        touch = _touch_from_book(book, side)
        if touch is None:
            log_event("no_touch", path=log_path, ticker=ticker, side=side)
            continue

        # signed net-yes projection, same convention as place_order: yes fill +1, no fill -1.
        delta_ct = Caps.PER_ORDER_SIZE_CT if side == "yes" else -Caps.PER_ORDER_SIZE_CT
        projected_if_filled = state.position(ticker, "yes") + delta_ct
        side_capped = not Caps.market_position_ok(projected_if_filled)

        existing = resting_by_side.get(side, {})
        if side_capped:
            for o in existing.values():
                decrease_order_to_zero(client, o, dry_run, reason="position_cap_side_stop", log_path=log_path)
            log_event("side_stopped", path=log_path, ticker=ticker, side=side,
                      position=state.position(ticker, "yes"))
            continue

        desired = rung_prices(touch)
        # existing keyed by distance if we tagged it during self_audit; fall back to price match.
        existing_by_distance = {}
        for o in existing.values():
            d = o.get("_distance_cents")
            if d is None:
                d = touch - int(o.get("price", touch))
            existing_by_distance[d] = o

        for distance, price in desired.items():
            order = existing_by_distance.get(distance)
            if order is None:
                place_order(client, state, ticker, side, price, distance, dry_run, log_path=log_path)
            elif needs_recenter(int(order.get("price", price)), price):
                amend_order(client, state, order, price, dry_run, now_ts, log_path=log_path)


def _payout_check(log_path=None):
    if not os.path.exists(PAYOUTS_FILE):
        log_event("payout_check", path=log_path, source="none",
                   note="lip_payouts.jsonl absent -- LIP payout visibility via API is unconfirmed "
                        "per LIP_PILOT_REGISTRATION.md; record daily payouts manually or via a "
                        "future API-scrape into lip_payouts.jsonl")
        return
    rows = load_log_events(PAYOUTS_FILE)
    total = sum(r.get("payout_usd", 0) for r in rows)
    log_event("payout_check", path=log_path, source="lip_payouts.jsonl", n_records=len(rows),
              total_payout_usd=total)


# =================================================================================================
# main
# =================================================================================================
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="LIP_PILOT quoting bot")
    p.add_argument("--max-seconds", type=float, default=None, help="warm-loop leg bound, like kwx_paper_gate")
    p.add_argument("--once", action="store_true", help="run a single cycle then exit")
    p.add_argument("--dry-run", action="store_true", help="force dry-run regardless of LIP_LIVE/switch")
    p.add_argument("--poll-seconds", type=float, default=LOOP_POLL_SECONDS)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    key_id, priv = load_signing_creds()
    gate = check_gates(key_id=key_id, priv=priv)
    if not gate.ok:
        sys.exit(0)  # inert, silent -- exactly per the registration's switch semantics

    try:
        cfg = load_market_config()
    except MarketConfigError as e:
        # a misconfigured/missing market file is an operator error, not a switch-off state --
        # worth one line to stderr for the workflow log, but still exits clean (no orders, ever).
        print(f"[lip_quoter] refusing to run: {e}", file=sys.stderr)
        sys.exit(0)

    tickers = [(m.get("ticker") if isinstance(m, dict) else m) for m in cfg["markets"]]
    client = KalshiClient(key_id, priv)
    dry_run = resolve_dry_run(args.dry_run, switch_state_on=True, secrets_ok=True)

    log_event("startup", dry_run=dry_run, tickers=tickers, max_seconds=args.max_seconds, once=args.once)

    state = RuntimeState()
    t_start = time.time()
    cycle = 0
    while True:
        gate = check_gates(key_id=key_id, priv=priv)
        if not gate.ok:
            log_event("gate_stop", reason=gate.reason)
            break
        result = run_cycle(client, cfg, tickers, state, dry_run, cycle)
        cycle += 1
        if result == "halted":
            break
        if args.once:
            break
        elapsed = time.time() - t_start
        if args.max_seconds is not None and elapsed >= args.max_seconds:
            break
        time.sleep(args.poll_seconds)

    sys.exit(0)


if __name__ == "__main__":
    main()
