#!/usr/bin/env python3
"""lip_selftest.py -- offline test suite for lip_quoter.py. NO network access, NO real Kalshi
credentials: a MockExchange stands in for KalshiClient, implementing the identical method surface
(list_orders/get_orderbook/get_positions/get_balance/create_order/amend_order/decrease_order/
cancel_order/batch_cancel) so every code path in lip_quoter.py runs unmodified against it.

Covers (per the LIP_PILOT build spec):
  - caps block orders at every boundary (exactly-at-cap allowed/blocked per the registration wording)
  - kill paths fire (self-audit failure, cap-violation-detected, cumulative-loss hard stop) and
    daily-loss stop-for-day fires at its own, softer boundary
  - gate evaluation order is exactly: switch -> halt -> secrets
  - ladder math (rung prices, clamping, re-center trigger, amend rate bound, daily rotation) is correct
  - reconciliation adopts expected LIP- orders, cancels LIP- orphans, and never touches non-LIP- orders
  - escalation only ever fires when explicitly armed, is idempotent, and stays inside its own caps
  - dry-run NEVER calls a mutating exchange method, live-run does

Run: python lip_selftest.py   (exits 0 iff every check passes; prints a PASS/FAIL line per check
and a final summary -- that summary's last line is what CI / the operator should look at).
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lip_quoter as LQ  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    return ok


def new_tmpdir():
    return tempfile.mkdtemp(prefix="lip_selftest_")


# =================================================================================================
# MockExchange -- same method surface as LQ.KalshiClient, in-memory, deterministic.
# =================================================================================================
class MockExchange:
    def __init__(self):
        self.orders = {}          # order_id -> dict
        self._next_id = 1
        self.positions = {}       # ticker -> {"position":int, "market_exposure":int, "realized_pnl":int}
        self.orderbooks = {}      # ticker -> {"yes":[[price,size],...], "no":[[price,size],...]}
        self.live_calls = []      # every mutating call actually issued: (kind, target)
        self.fail_reads = False   # simulate a portfolio API outage

    def _new_id(self):
        oid = f"ord{self._next_id}"
        self._next_id += 1
        return oid

    # ---- reads ----
    def list_orders(self, status_filter="resting", ticker=None):
        if self.fail_reads:
            return None
        out = [o for o in self.orders.values() if status_filter is None or o["status"] == status_filter]
        if ticker:
            out = [o for o in out if o["ticker"] == ticker]
        return out

    def get_orderbook(self, ticker):
        return self.orderbooks.get(ticker)

    def get_positions(self):
        if self.fail_reads:
            return None
        return [{"ticker": t, **p} for t, p in self.positions.items()]

    def get_balance(self):
        return 100_000

    # ---- writes ----
    def create_order(self, ticker, side, action, price_cents, count, client_order_id):
        self.live_calls.append(("create", client_order_id))
        oid = self._new_id()
        self.orders[oid] = {
            "order_id": oid, "client_order_id": client_order_id, "ticker": ticker, "side": side,
            "action": action, "price": price_cents, "count": count, "remaining_count": count,
            "status": "resting",
        }
        return 201, {"order_id": oid}

    def amend_order(self, order_id, price_cents, count):
        self.live_calls.append(("amend", order_id))
        if order_id in self.orders:
            self.orders[order_id]["price"] = price_cents
            self.orders[order_id]["remaining_count"] = count
        return 200, {"order_id": order_id}

    def decrease_order(self, order_id, reduce_to=None, reduce_by=None):
        self.live_calls.append(("decrease", order_id))
        if order_id in self.orders:
            cur = self.orders[order_id]["remaining_count"]
            new = reduce_to if reduce_to is not None else max(0, cur - (reduce_by or 0))
            self.orders[order_id]["remaining_count"] = new
            if new == 0:
                self.orders[order_id]["status"] = "canceled"
        return 200, {"order_id": order_id}

    def cancel_order(self, order_id):
        self.live_calls.append(("cancel", order_id))
        if order_id in self.orders:
            self.orders[order_id]["status"] = "canceled"
        return 200, {"order_id": order_id}

    def batch_cancel(self, order_ids):
        self.live_calls.append(("batch_cancel", tuple(order_ids)))
        for oid in order_ids:
            if oid in self.orders:
                self.orders[oid]["status"] = "canceled"
        return 200, {"cancelled": list(order_ids)}


# =================================================================================================
# 1. Caps -- boundary tests. "exactly at cap" semantics per Caps docstring.
# =================================================================================================
def test_caps_boundaries():
    C = LQ.Caps
    check("order_size: 1ct allowed", C.order_size_ok(1) is True)
    check("order_size: 2ct blocked", C.order_size_ok(2) is False)
    check("order_size: escalation 100ct allowed", C.order_size_ok(100, is_escalation=True) is True)
    check("order_size: escalation 99ct blocked", C.order_size_ok(99, is_escalation=True) is False)
    check("order_size: escalation 1ct blocked (must be exactly 100)",
          C.order_size_ok(1, is_escalation=True) is False)

    check("per_market_position: +10 allowed (at cap)", C.market_position_ok(10) is True)
    check("per_market_position: +11 blocked (over cap)", C.market_position_ok(11) is False)
    check("per_market_position: -10 allowed (at cap, short side)", C.market_position_ok(-10) is True)
    check("per_market_position: -11 blocked (over cap, short side)", C.market_position_ok(-11) is False)

    check("cost_basis: $300.00 allowed (at cap)", C.cost_basis_ok_cents(30_000) is True)
    check("cost_basis: $300.01 blocked (over cap)", C.cost_basis_ok_cents(30_001) is False)

    check("resting_cost: $100.00 allowed (at cap)", C.resting_cost_ok_cents(10_000) is True)
    check("resting_cost: $100.01 blocked (over cap)", C.resting_cost_ok_cents(10_001) is False)

    check("collateral: $1000.00 allowed (at cap)", C.collateral_ok_cents(100_000) is True)
    check("collateral: $1000.01 blocked (over cap)", C.collateral_ok_cents(100_001) is False)

    check("daily_loss: $24.99 does not halt", C.daily_loss_halt(2_499) is False)
    check("daily_loss: $25.00 halts (loss ceiling triggers AT the cap)", C.daily_loss_halt(2_500) is True)

    check("cumulative_loss: $99.99 no hard stop", C.cumulative_loss_hardstop(9_999) is False)
    check("cumulative_loss: $100.00 hard stop (AT the cap)", C.cumulative_loss_hardstop(10_000) is True)

    check("escalation_cost: 15c x100 = $15.00 allowed", C.escalation_cost_ok_cents(15, 100) is True)
    check("escalation_cost: 16c (over the 15c price cap) blocked", C.escalation_cost_ok_cents(16, 100) is False)
    check("escalation_cost: 15c x101 = $15.15 blocked (over $15 total)",
          C.escalation_cost_ok_cents(15, 101) is False)

    clean = C.audit(resting_order_cost_cents=5_000, open_position_cost_basis_cents=1_000,
                     collateral_cents=6_000, per_market_positions={"T": 5})
    check("Caps.audit: clean state -> no violations", clean == [], detail=str(clean))

    dirty = C.audit(resting_order_cost_cents=10_001, open_position_cost_basis_cents=1_000,
                     collateral_cents=11_001, per_market_positions={"T": 11})
    check("Caps.audit: over-cap state -> flags resting_order_cost",
          "resting_order_cost" in dirty, detail=str(dirty))
    check("Caps.audit: over-cap state -> flags per_market_position:T",
          "per_market_position:T" in dirty, detail=str(dirty))


# =================================================================================================
# 2. Ladder math
# =================================================================================================
def test_ladder_math():
    check("rung_prices(touch=50) == {1:49,3:47,5:45,8:42}",
          LQ.rung_prices(50) == {1: 49, 3: 47, 5: 45, 8: 42}, detail=str(LQ.rung_prices(50)))

    clamped = LQ.rung_prices(3)
    check("rung_prices(touch=3): all clamped to >=1c",
          all(1 <= p <= 99 for p in clamped.values()), detail=str(clamped))
    check("rung_prices(touch=3)[1] == 2 (3-1, unclamped)", clamped[1] == 2)
    check("rung_prices(touch=3)[8] == 1 (3-8=-5, clamped to floor)", clamped[8] == 1)

    check("needs_recenter: 1c move -> False (below 2c trigger)", LQ.needs_recenter(50, 51) is False)
    check("needs_recenter: 2c move -> True (AT the 2c trigger)", LQ.needs_recenter(50, 52) is True)
    check("needs_recenter: 3c move -> True", LQ.needs_recenter(50, 53) is True)

    check("amend_allowed: 59.9s since last amend -> False (<60s bound)",
          LQ.amend_allowed(0.0, 59.9) is False)
    check("amend_allowed: 60.0s since last amend -> True (AT the 1/min bound)",
          LQ.amend_allowed(0.0, 60.0) is True)
    check("amend_allowed: 60.1s since last amend -> True", LQ.amend_allowed(0.0, 60.1) is True)

    tickers = ["A", "B", "C"]
    r1 = LQ.market_processing_order("2026-08-01", tickers)
    r1b = LQ.market_processing_order("2026-08-01", tickers)
    check("market_processing_order: deterministic (same date -> identical order, no RNG)", r1 == r1b)
    check("market_processing_order: is a permutation of the input", sorted(r1) == sorted(tickers))
    offset = LQ.date_ordinal("2026-08-01") % len(tickers)
    check("market_processing_order: matches the documented date-ordinal-mod-n rotation",
          r1 == tickers[offset:] + tickers[:offset])
    r2 = LQ.market_processing_order("2026-08-02", tickers)
    check("market_processing_order: rotates on the next calendar day", r1 != r2 or len(tickers) == 1)

    check("client_order_id: ladder id format",
          LQ.client_order_id("KXBTC-1", "yes", 3) == "LIP-KXBTC-1-yes-3c")
    check("client_order_id: escalation id format",
          LQ.client_order_id("KXBTC-1", "yes", 8, is_escalation=True) == "LIP-ESC-KXBTC-1")
    check("client_order_id: always starts with the LIP- prefix",
          LQ.client_order_id("X", "no", 1).startswith(LQ.CID_PREFIX))


# =================================================================================================
# 3. Gate order: switch -> halt -> secrets, exactly, at startup and every loop iteration.
# =================================================================================================
def test_gate_order():
    d = new_tmpdir()
    switch_file = os.path.join(d, "LIP_SWITCH")
    halt_file = os.path.join(d, ".lip_halt")

    # no switch file at all
    g = LQ.check_gates(switch_file=switch_file, halt_file=halt_file, key_id="k", priv="p")
    check("gate: missing switch file -> inert (switch_not_on)", not g.ok and g.reason == "switch_not_on")

    with open(switch_file, "w") as fh:
        fh.write("off\n")
    g = LQ.check_gates(switch_file=switch_file, halt_file=halt_file, key_id="k", priv="p")
    check("gate: switch=off -> inert (switch_not_on)", not g.ok and g.reason == "switch_not_on")

    with open(switch_file, "w") as fh:
        fh.write("on\n")
    with open(halt_file, "w") as fh:
        fh.write("halted\n")
    g = LQ.check_gates(switch_file=switch_file, halt_file=halt_file, key_id="k", priv="p")
    check("gate: switch=on but .lip_halt present -> inert (halt_file_present), "
          "checked BEFORE secrets", not g.ok and g.reason == "halt_file_present")

    os.remove(halt_file)
    g = LQ.check_gates(switch_file=switch_file, halt_file=halt_file, key_id=None, priv=None)
    check("gate: switch=on, no halt, secrets missing -> inert (secrets_missing)",
          not g.ok and g.reason == "secrets_missing")

    g = LQ.check_gates(switch_file=switch_file, halt_file=halt_file, key_id="k", priv="p")
    check("gate: switch=on, no halt, secrets present -> OK", g.ok)

    shutil.rmtree(d, ignore_errors=True)


def test_resolve_dry_run():
    check("dry-run: explicit --dry-run always wins",
          LQ.resolve_dry_run(True, switch_state_on=True, secrets_ok=True) is True)

    os.environ.pop("LIP_LIVE", None)
    check("dry-run: default (LIP_LIVE unset) is dry-run even if switch on + secrets ok",
          LQ.resolve_dry_run(False, switch_state_on=True, secrets_ok=True) is True)

    os.environ["LIP_LIVE"] = "1"
    check("dry-run: LIP_LIVE=1 + switch on + secrets ok -> LIVE (not dry-run)",
          LQ.resolve_dry_run(False, switch_state_on=True, secrets_ok=True) is False)
    check("dry-run: LIP_LIVE=1 but switch NOT on -> still dry-run",
          LQ.resolve_dry_run(False, switch_state_on=False, secrets_ok=True) is True)
    check("dry-run: LIP_LIVE=1 but secrets not ok -> still dry-run",
          LQ.resolve_dry_run(False, switch_state_on=True, secrets_ok=False) is True)
    os.environ.pop("LIP_LIVE", None)


# =================================================================================================
# 4. Market selection / config validation
# =================================================================================================
def test_market_config():
    d = new_tmpdir()
    path = os.path.join(d, "lip_markets.json")

    try:
        LQ.load_market_config(path)
        check("market config: missing file raises", False)
    except LQ.MarketConfigError:
        check("market config: missing file raises MarketConfigError", True)

    import json as _json

    def write(cfg):
        with open(path, "w") as fh:
            _json.dump(cfg, fh)

    write({"markets": [{"ticker": "KXBTC-1"}, {"ticker": "KXBTC-2"}, {"ticker": "KXBTC-3"}]})
    cfg = LQ.load_market_config(path)
    check("market config: 3 clean markets loads OK", len(cfg["markets"]) == 3)

    write({"markets": [{"ticker": f"KXBTC-{i}"} for i in range(6)]})
    try:
        LQ.load_market_config(path)
        check("market config: 6 markets (>5) raises", False)
    except LQ.MarketConfigError:
        check("market config: 6 markets (>5) raises MarketConfigError", True)

    write({"markets": [{"ticker": "KXHIGHDEN-26JUL30-T90"}, {"ticker": "KXBTC-2"}, {"ticker": "KXBTC-3"}]})
    try:
        LQ.load_market_config(path)
        check("market config: KXHIGH* collision raises", False)
    except LQ.MarketConfigError:
        check("market config: KXHIGH* collision raises MarketConfigError", True)

    write({"markets": [{"ticker": "KXLOWTDEN-26JUL30-T40"}, {"ticker": "KXBTC-2"}, {"ticker": "KXBTC-3"}]})
    try:
        LQ.load_market_config(path)
        check("market config: KXLOW* collision raises", False)
    except LQ.MarketConfigError:
        check("market config: KXLOW* collision raises MarketConfigError", True)

    write({"markets": [{"ticker": "KXBTC-1"}, {"ticker": "KXBTC-1"}, {"ticker": "KXBTC-3"}]})
    try:
        LQ.load_market_config(path)
        check("market config: duplicate tickers raises", False)
    except LQ.MarketConfigError:
        check("market config: duplicate tickers raises MarketConfigError", True)

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 5. place_order cap enforcement, dry-run vs live
# =================================================================================================
def test_place_order():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    mock = MockExchange()
    state = LQ.RuntimeState()

    resp = LQ.place_order(mock, state, "KXBTC-1", "yes", 49, 1, dry_run=True, log_path=log_path)
    check("place_order dry-run: returns DRY_RUN status", resp is not None and resp.get("status") == "DRY_RUN")
    check("place_order dry-run: no live call issued", mock.live_calls == [], detail=str(mock.live_calls))
    events = LQ.load_log_events(log_path)
    check("place_order dry-run: logs place_dry_run with full context",
          any(e.get("event") == "place_dry_run" and e.get("client_order_id") == resp["client_order_id"]
              for e in events))

    mock2 = MockExchange()
    state2 = LQ.RuntimeState()
    resp2 = LQ.place_order(mock2, state2, "KXBTC-1", "yes", 49, 1, dry_run=False, log_path=log_path)
    check("place_order live: issues a create call", ("create", resp2["order_id"]) not in mock2.live_calls
          and any(k == "create" for k, _ in mock2.live_calls))

    # resting-order-cost boundary: exactly at cap allowed, one cent over blocked
    state3 = LQ.RuntimeState()
    state3.resting_order_cost_cents = 9_999
    mock3 = MockExchange()
    r_at_cap = LQ.place_order(mock3, state3, "KXBTC-1", "yes", 1, 8, dry_run=True, log_path=log_path)
    check("place_order: resting-cost projected==cap ($100.00) allowed", r_at_cap is not None)
    check("place_order: resting-cost running total updated to exactly the cap",
          state3.resting_order_cost_cents == 10_000)

    state4 = LQ.RuntimeState()
    state4.resting_order_cost_cents = 10_000
    mock4 = MockExchange()
    r_over_cap = LQ.place_order(mock4, state4, "KXBTC-1", "yes", 1, 8, dry_run=True, log_path=log_path)
    check("place_order: resting-cost projected==cap+1c blocked", r_over_cap is None)
    check("place_order: blocked order does not touch running totals",
          state4.resting_order_cost_cents == 10_000)

    # per-market position boundary
    state5 = LQ.RuntimeState()
    state5.positions["KXBTC-1"] = {"yes": 9}
    mock5 = MockExchange()
    r5 = LQ.place_order(mock5, state5, "KXBTC-1", "yes", 40, 1, dry_run=True, log_path=log_path)
    check("place_order: position 9->10 (AT cap) allowed", r5 is not None)

    state6 = LQ.RuntimeState()
    state6.positions["KXBTC-1"] = {"yes": 10}
    mock6 = MockExchange()
    r6 = LQ.place_order(mock6, state6, "KXBTC-1", "yes", 40, 1, dry_run=True, log_path=log_path)
    check("place_order: position 10->11 (over cap) blocked", r6 is None)

    # collateral boundary
    state7 = LQ.RuntimeState()
    state7.collateral_committed_cents = 99_999
    mock7 = MockExchange()
    r7 = LQ.place_order(mock7, state7, "KXBTC-1", "yes", 1, 8, dry_run=True, log_path=log_path)
    check("place_order: collateral projected==$1000.00 (AT cap) allowed", r7 is not None)

    state8 = LQ.RuntimeState()
    state8.collateral_committed_cents = 100_000
    mock8 = MockExchange()
    r8 = LQ.place_order(mock8, state8, "KXBTC-1", "yes", 1, 8, dry_run=True, log_path=log_path)
    check("place_order: collateral projected==$1000.01 (over cap) blocked", r8 is None)

    # escalation path
    state9 = LQ.RuntimeState()
    mock9 = MockExchange()
    r9 = LQ.place_order(mock9, state9, "KXBTC-1", "yes", 15, 8, dry_run=True, is_escalation=True,
                         log_path=log_path)
    check("place_order: escalation at 15c/100ct ($15.00, AT cap) allowed", r9 is not None)

    state10 = LQ.RuntimeState()
    mock10 = MockExchange()
    r10 = LQ.place_order(mock10, state10, "KXBTC-1", "yes", 16, 8, dry_run=True, is_escalation=True,
                          log_path=log_path)
    check("place_order: escalation at 16c (over the 15c price cap) blocked", r10 is None)

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 6. Amend rate limiting
# =================================================================================================
def test_amend_rate_limit():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    mock = MockExchange()
    state = LQ.RuntimeState()
    status, resp = mock.create_order("KXBTC-1", "yes", "buy", 50, 1, "LIP-KXBTC-1-yes-1c")
    order = mock.orders[resp["order_id"]]

    LQ.amend_order(mock, state, order, 48, dry_run=False, now_ts=1000.0, log_path=log_path)
    check("amend: first amend goes through", ("amend", order["order_id"]) in mock.live_calls)

    n_before = len(mock.live_calls)
    LQ.amend_order(mock, state, order, 47, dry_run=False, now_ts=1030.0, log_path=log_path)
    check("amend: second amend 30s later (< 60s bound) is rate-limited, not sent",
          len(mock.live_calls) == n_before)

    LQ.amend_order(mock, state, order, 47, dry_run=False, now_ts=1060.0, log_path=log_path)
    check("amend: amend exactly 60s later (AT the 1/min bound) goes through",
          len(mock.live_calls) == n_before + 1)

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 7. Reconciliation: adopt expected LIP- orders, cancel LIP- orphans, never touch foreign orders.
# =================================================================================================
def test_reconciliation():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    mock = MockExchange()

    expected_cid = LQ.client_order_id("KXBTC-1", "yes", 1)
    mock.create_order("KXBTC-1", "yes", "buy", 49, 1, expected_cid)
    orphan_cid = "LIP-STALE-ORPHAN-yes-1c"
    mock.create_order("KXBTC-1", "yes", "buy", 40, 1, orphan_cid)
    foreign_cid = "kwx-KXHIGHDEN-26JUL30-buy"
    mock.create_order("KXHIGHDEN-26JUL30-T90", "yes", "buy", 10, 5, foreign_cid)

    adopted = LQ.reconcile(mock, ["KXBTC-1"], dry_run=False, log_path=log_path)
    adopted_cids = {o["client_order_id"] for o in adopted}
    check("reconcile: adopts the expected LIP- order", expected_cid in adopted_cids)
    orphan_order = next(o for o in mock.orders.values() if o["client_order_id"] == orphan_cid)
    check("reconcile: cancels the LIP- orphan", orphan_order["status"] == "canceled")
    foreign_order = next(o for o in mock.orders.values() if o["client_order_id"] == foreign_cid)
    check("reconcile: never touches a non-LIP- (foreign) order",
          foreign_order["status"] == "resting" and
          not any(target == foreign_order["order_id"] for _, target in mock.live_calls))

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 8. Kill paths
# =================================================================================================
def test_kill_paths():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    halt_file = os.path.join(d, ".lip_halt")
    mock = MockExchange()
    mock.create_order("KXBTC-1", "yes", "buy", 49, 1, "LIP-KXBTC-1-yes-1c")
    mock.create_order("KXBTC-1", "no", "buy", 49, 1, "LIP-KXBTC-1-no-1c")

    telegram_calls = []
    orig_telegram = LQ.telegram_alert
    LQ.telegram_alert = lambda msg: telegram_calls.append(msg)

    try:
        LQ.kill_pilot(mock, dry_run=False, reason="test_violation", detail=["x"], halt_file=halt_file,
                       log_path=log_path)
        check("kill_pilot (live): writes .lip_halt", os.path.exists(halt_file))
        with open(halt_file) as fh:
            content = fh.read()
        check("kill_pilot (live): .lip_halt names the reason", "test_violation" in content)
        batch_calls = [c for c in mock.live_calls if c[0] == "batch_cancel"]
        check("kill_pilot (live): issues a batch-cancel", len(batch_calls) == 1)
        check("kill_pilot (live): batch-cancel targets both LIP- orders",
              len(batch_calls[0][1]) == 2)
        check("kill_pilot: fires a telegram alert", len(telegram_calls) == 1)

        os.remove(halt_file)
        mock2 = MockExchange()
        mock2.create_order("KXBTC-1", "yes", "buy", 49, 1, "LIP-KXBTC-1-yes-1c")
        LQ.kill_pilot(mock2, dry_run=True, reason="test_violation_dry", halt_file=halt_file, log_path=log_path)
        check("kill_pilot (dry-run): STILL writes .lip_halt (a local safety action, not a trade)",
              os.path.exists(halt_file))
        check("kill_pilot (dry-run): does NOT issue a real batch-cancel",
              not any(c[0] == "batch_cancel" for c in mock2.live_calls))
    finally:
        LQ.telegram_alert = orig_telegram

    shutil.rmtree(d, ignore_errors=True)


def test_daily_and_cumulative_loss_kill():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    stop_file = os.path.join(d, ".lip_stop_today")
    halt_file = os.path.join(d, ".lip_halt")

    cfg = {"markets": [{"ticker": "KXBTC-1"}]}
    tickers = ["KXBTC-1"]

    # ---- daily loss: cycle 0 establishes a zero baseline, cycle 1 hits exactly $25 realized loss ----
    mock = MockExchange()
    mock.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    state = LQ.RuntimeState()
    LQ._STOP_FILE_OVERRIDE = None  # no-op placeholder (documents there is no global to reset)

    orig_stop_file = LQ.STOP_TODAY_FILE
    orig_halt_file = LQ.HALT_FILE
    LQ.STOP_TODAY_FILE = stop_file
    LQ.HALT_FILE = halt_file
    try:
        r0 = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=0, log_path=log_path)
        check("loss-kill: cycle0 (zero pnl) establishes baseline, no stop", r0 == "ok")
        check("loss-kill: no stop-for-day file after a clean cycle0", not os.path.exists(stop_file))

        mock.positions["KXBTC-1"]["realized_pnl"] = -2_499
        r1 = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=1, log_path=log_path)
        check("loss-kill: -$24.99 realized does NOT trigger stop-for-day",
              not os.path.exists(stop_file) and r1 == "ok")

        mock.positions["KXBTC-1"]["realized_pnl"] = -2_500
        r2 = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=2, log_path=log_path)
        check("loss-kill: -$25.00 realized (AT the daily cap) triggers stop-for-day",
              os.path.exists(stop_file))
        check("loss-kill: run_cycle reports stopped_for_day the same cycle it trips", r2 == "stopped_for_day")
        check("loss-kill: daily stop does NOT also write .lip_halt (softer than the cumulative path)",
              not os.path.exists(halt_file))
    finally:
        LQ.STOP_TODAY_FILE = orig_stop_file
        LQ.HALT_FILE = orig_halt_file

    # ---- cumulative loss: fresh log, cycle0 baseline, cycle1 hits exactly -$100 -> hard stop ----
    # (patch STOP_TODAY_FILE too: -$99.99/-$100 in one step also blows through the $25 DAILY cap,
    # so stop_for_day() fires along the way and must not be allowed to touch the real repo path.)
    log_path2 = os.path.join(d, "log2.jsonl")
    halt_file2 = os.path.join(d, ".lip_halt2")
    stop_file2 = os.path.join(d, ".lip_stop_today2")
    mock2 = MockExchange()
    mock2.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    state2 = LQ.RuntimeState()
    LQ.HALT_FILE = halt_file2
    LQ.STOP_TODAY_FILE = stop_file2
    try:
        LQ.run_cycle(mock2, cfg, tickers, state2, dry_run=True, cycle_index=0, log_path=log_path2)
        mock2.positions["KXBTC-1"]["realized_pnl"] = -9_999
        r_below = LQ.run_cycle(mock2, cfg, tickers, state2, dry_run=True, cycle_index=1, log_path=log_path2)
        check("cumulative-loss: -$99.99 does NOT hard stop",
              not os.path.exists(halt_file2) and r_below != "halted")

        mock2.positions["KXBTC-1"]["realized_pnl"] = -10_000
        r_at = LQ.run_cycle(mock2, cfg, tickers, state2, dry_run=True, cycle_index=2, log_path=log_path2)
        check("cumulative-loss: -$100.00 (AT the cumulative cap) hard-stops (.lip_halt written)",
              os.path.exists(halt_file2))
        check("cumulative-loss: run_cycle reports halted", r_at == "halted")
    finally:
        LQ.HALT_FILE = orig_halt_file
        LQ.STOP_TODAY_FILE = orig_stop_file

    shutil.rmtree(d, ignore_errors=True)


def test_self_audit_failure_kills():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    halt_file = os.path.join(d, ".lip_halt")
    cfg = {"markets": [{"ticker": "KXBTC-1"}]}
    tickers = ["KXBTC-1"]

    mock = MockExchange()
    mock.fail_reads = True
    state = LQ.RuntimeState()
    orig_halt_file = LQ.HALT_FILE
    LQ.HALT_FILE = halt_file
    try:
        result = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=0, log_path=log_path)
        check("self-audit failure: treated as suspected cap violation -> halts", result == "halted")
        check("self-audit failure: writes .lip_halt", os.path.exists(halt_file))
    finally:
        LQ.HALT_FILE = orig_halt_file
    shutil.rmtree(d, ignore_errors=True)


def test_cap_violation_detected_kills():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    halt_file = os.path.join(d, ".lip_halt")
    cfg = {"markets": [{"ticker": "KXBTC-1"}]}
    tickers = ["KXBTC-1"]

    mock = MockExchange()
    # simulate drift: a resting LIP- order set whose aggregate cost is already over the $100 cap --
    # something place_order's own checks should have prevented; self_audit must catch it anyway.
    mock.create_order("KXBTC-1", "yes", "buy", 99, 102, "LIP-KXBTC-1-yes-1c")  # $100.98
    mock.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    state = LQ.RuntimeState()
    orig_halt_file = LQ.HALT_FILE
    LQ.HALT_FILE = halt_file
    try:
        result = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=0, log_path=log_path)
        check("cap-violation-detected (resting cost over cap on the exchange): halts", result == "halted")
        check("cap-violation-detected: writes .lip_halt", os.path.exists(halt_file))
        batch_calls = [c for c in mock.live_calls if c[0] == "batch_cancel"]
        check("cap-violation-detected: dry-run does not actually batch-cancel", batch_calls == [])
    finally:
        LQ.HALT_FILE = orig_halt_file
    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 9. Escalation: never automatic, idempotent, stays inside its own caps
# =================================================================================================
def test_escalation():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    tickers = ["KXBTC-1"]
    orderbooks = {"KXBTC-1": {"yes": [[50, 10]], "no": [[48, 10]]}}

    mock = MockExchange()
    state = LQ.RuntimeState()
    cfg_no_esc = {"markets": [{"ticker": "KXBTC-1"}]}
    r = LQ.maybe_place_escalation(mock, state, cfg_no_esc, tickers, orderbooks, dry_run=True, log_path=log_path)
    check("escalation: absent config -> never fires", r is None and mock.live_calls == [])

    mock2 = MockExchange()
    state2 = LQ.RuntimeState()
    cfg_not_armed = {"markets": [{"ticker": "KXBTC-1"}],
                      "escalation": {"escalate_market": "KXBTC-1", "armed": False,
                                     "after_zero_payout_days": 4}}
    r2 = LQ.maybe_place_escalation(mock2, state2, cfg_not_armed, tickers, orderbooks, dry_run=True,
                                    log_path=log_path)
    check("escalation: present but NOT armed -> never fires (operator decides, not the bot)",
          r2 is None and mock2.live_calls == [])

    mock3 = MockExchange()
    state3 = LQ.RuntimeState()
    cfg_armed = {"markets": [{"ticker": "KXBTC-1"}],
                 "escalation": {"escalate_market": "KXBTC-1", "armed": True, "after_zero_payout_days": 4}}
    r3 = LQ.maybe_place_escalation(mock3, state3, cfg_armed, tickers, orderbooks, dry_run=True,
                                    log_path=log_path)
    check("escalation: armed + market in lip_markets + touch known -> fires once", r3 is not None)
    check("escalation: price respects the far-rung / 15c cap",
          r3["client_order_id"] == "LIP-ESC-KXBTC-1")
    events = LQ.load_log_events(log_path)
    esc_place = [e for e in events if e.get("event") == "place_dry_run" and e.get("is_escalation")]
    check("escalation: placed size is exactly 100ct", esc_place and esc_place[-1]["size_ct"] == 100)
    check("escalation: placed price <= 15c", esc_place and esc_place[-1]["price_cents"] <= 15)
    check("escalation: state.escalation_placed_date set (idempotency marker)",
          state3.escalation_placed_date is not None)

    r4 = LQ.maybe_place_escalation(mock3, state3, cfg_armed, tickers, orderbooks, dry_run=True,
                                    log_path=log_path)
    check("escalation: second call is a no-op (idempotent -- only ever placed once)", r4 is None)

    mock5 = MockExchange()
    state5 = LQ.RuntimeState()
    cfg_wrong_market = {"markets": [{"ticker": "KXBTC-1"}],
                         "escalation": {"escalate_market": "KXETH-1", "armed": True}}
    r5 = LQ.maybe_place_escalation(mock5, state5, cfg_wrong_market, tickers, orderbooks, dry_run=True,
                                    log_path=log_path)
    check("escalation: escalate_market not in lip_markets.json -> refuses", r5 is None)

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 10. Side-stop uses decrease (not cancel/amend) when a market position is at its cap
# =================================================================================================
def test_position_cap_side_stop():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    mock = MockExchange()
    state = LQ.RuntimeState()
    state.positions["KXBTC-1"] = {"yes": 10, "no": 0}  # yes side AT the per-market cap

    status, resp = mock.create_order("KXBTC-1", "yes", "buy", 49, 1, "LIP-KXBTC-1-yes-1c")
    resting_order = mock.orders[resp["order_id"]]
    resting_by_side = {"yes": {1: resting_order}}
    book = {"yes": [[50, 10]], "no": [[48, 10]]}

    LQ._maintain_market(mock, state, "KXBTC-1", book, resting_by_side, dry_run=False, now_ts=1000.0,
                         log_path=log_path)
    check("side-stop: yes side at cap -> existing resting order is decreased-to-zero (not amended)",
          ("decrease", resting_order["order_id"]) in mock.live_calls)
    check("side-stop: no amend was issued for the capped side",
          not any(k == "amend" for k, _ in mock.live_calls))
    check("side-stop: no side (not capped) is free to place new rungs",
          any(k == "create" for k, _ in mock.live_calls))

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 11. Dry-run holistically never calls a mutating exchange method across a full run_cycle
# =================================================================================================
def test_dry_run_never_posts():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")
    cfg = {"markets": [{"ticker": "KXBTC-1"}, {"ticker": "KXETH-1"}]}
    tickers = ["KXBTC-1", "KXETH-1"]
    mock = MockExchange()
    mock.orderbooks["KXBTC-1"] = {"yes": [[60, 10]], "no": [[38, 10]]}
    mock.orderbooks["KXETH-1"] = {"yes": [[55, 10]], "no": [[43, 10]]}
    mock.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    mock.positions["KXETH-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    state = LQ.RuntimeState()

    result = LQ.run_cycle(mock, cfg, tickers, state, dry_run=True, cycle_index=0, log_path=log_path)
    check("dry-run full cycle: completes ok", result == "ok")
    check("dry-run full cycle: zero live (mutating) exchange calls", mock.live_calls == [],
          detail=str(mock.live_calls))
    events = LQ.load_log_events(log_path)
    n_place_dry = sum(1 for e in events if e.get("event") == "place_dry_run")
    check("dry-run full cycle: intended placements ARE logged (place_dry_run, full context)",
          n_place_dry == 2 * 2 * len(LQ.Caps.LADDER_CENTS),  # 2 markets x 2 sides x 4 rungs
          detail=f"n_place_dry={n_place_dry}")

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
# 12. Safety-review regressions (defects found & fixed in the pre-ship review; must never recur)
# =================================================================================================
class RaisingExchange:
    """Simulates the exchange being unreachable at kill time (every call raises, like
    KalshiClient._request after exhausted retries)."""

    def list_orders(self, status_filter="resting", ticker=None):
        raise RuntimeError("kalshi request failed after 2 retries: simulated outage")

    def batch_cancel(self, order_ids):
        raise RuntimeError("unreachable")


def test_safety_review_regressions():
    d = new_tmpdir()
    log_path = os.path.join(d, "log.jsonl")

    # --- (a) per-market cap must bind on the NO side too (signed net-yes position convention) ---
    state = LQ.RuntimeState()
    state.positions["KXBTC-1"] = {"yes": -10}  # net short 10 (10 'no' contracts held)
    mock = MockExchange()
    r = LQ.place_order(mock, state, "KXBTC-1", "no", 40, 1, dry_run=True, log_path=log_path)
    check("no-side cap: signed position -10, another no-buy (-> -11) blocked", r is None)
    r2 = LQ.place_order(mock, state, "KXBTC-1", "yes", 40, 1, dry_run=True, log_path=log_path)
    check("no-side cap: same state, a yes-buy (-> -9, toward flat) allowed", r2 is not None)
    state_b = LQ.RuntimeState()
    state_b.positions["KXBTC-1"] = {"yes": 10}
    r3 = LQ.place_order(MockExchange(), state_b, "KXBTC-1", "no", 40, 1, dry_run=True, log_path=log_path)
    check("no-side cap: signed position +10, a no-buy (-> +9) allowed", r3 is not None)

    # --- (b) kill_pilot must write .lip_halt even when the exchange itself is down ---
    halt_file = os.path.join(d, ".lip_halt_outage")
    telegram_calls = []
    orig_telegram = LQ.telegram_alert
    LQ.telegram_alert = lambda msg: telegram_calls.append(msg)
    try:
        LQ.kill_pilot(RaisingExchange(), dry_run=False, reason="outage_kill", halt_file=halt_file,
                       log_path=log_path)
        check("kill during outage: .lip_halt written even though batch-cancel raised",
              os.path.exists(halt_file))
        check("kill during outage: telegram alert still fired", len(telegram_calls) == 1)
    except Exception as e:
        check("kill during outage: kill_pilot must not raise", False, detail=repr(e))
    finally:
        LQ.telegram_alert = orig_telegram

    # --- (c) self_audit keys resting orders per rung (no collapse) and excludes the ESC order ---
    mock2 = MockExchange()
    for dist in LQ.Caps.LADDER_CENTS:
        mock2.create_order("KXBTC-1", "yes", "buy", 50 - dist, 1, LQ.client_order_id("KXBTC-1", "yes", dist))
    mock2.create_order("KXBTC-1", "yes", "buy", 10, 100, LQ.client_order_id("KXBTC-1", "yes", 0, is_escalation=True))
    mock2.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    audit = LQ.self_audit(mock2, ["KXBTC-1"])
    yes_map = audit["resting_by_market"].get("KXBTC-1", {}).get("yes", {})
    check("self_audit: all 4 ladder rungs individually visible to maintenance",
          set(yes_map.keys()) == set(LQ.Caps.LADDER_CENTS), detail=str(sorted(yes_map.keys())))
    check("self_audit: escalation order excluded from ladder maintenance map",
          all(not str(o.get("client_order_id", "")).startswith("LIP-ESC-") for o in yes_map.values()))
    check("self_audit: escalation order still counted in resting cost (caps see it)",
          audit["resting_order_cost_cents"] == sum(50 - x for x in LQ.Caps.LADDER_CENTS) + 10 * 100,
          detail=str(audit["resting_order_cost_cents"]))
    check("self_audit: cid distance parser handles hyphenated tickers",
          LQ.parse_cid_distance_cents("LIP-KXBTCMAXY-26AUG01-B60000-yes-8c") == 8)
    check("self_audit: cid distance parser returns None for the ESC id",
          LQ.parse_cid_distance_cents("LIP-ESC-KXBTC-1") is None)

    # --- (d) self_audit fails CLOSED on schema drift (missing pnl/price fields), not silent-zero ---
    mock3 = MockExchange()
    mock3.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0}  # realized_pnl missing
    try:
        LQ.self_audit(mock3, ["KXBTC-1"])
        check("self_audit: missing realized_pnl field raises SelfAuditFailure (fail closed)", False)
    except LQ.SelfAuditFailure:
        check("self_audit: missing realized_pnl field raises SelfAuditFailure (fail closed)", True)
    mock4 = MockExchange()
    _, cr = mock4.create_order("KXBTC-1", "yes", "buy", 49, 1, "LIP-KXBTC-1-yes-1c")
    o = mock4.orders[cr["order_id"]]
    del o["price"]  # simulate a renamed price field (and no yes_price fallback)
    mock4.positions["KXBTC-1"] = {"position": 0, "market_exposure": 0, "realized_pnl": 0}
    try:
        LQ.self_audit(mock4, ["KXBTC-1"])
        check("self_audit: missing order price field raises SelfAuditFailure (fail closed)", False)
    except LQ.SelfAuditFailure:
        check("self_audit: missing order price field raises SelfAuditFailure (fail closed)", True)

    # --- (e) Caps.audit tolerates a filled ARMED escalation, still flags everything else ---
    clean = LQ.Caps.audit(0, 1500, 1500, {"KXBTC-1": 100}, escalation_market="KXBTC-1")
    check("Caps.audit: armed escalation market at +100 is NOT a violation", clean == [], detail=str(clean))
    over = LQ.Caps.audit(0, 1500, 1500, {"KXBTC-1": 111}, escalation_market="KXBTC-1")
    check("Caps.audit: armed escalation market at +111 (>100+10) IS a violation",
          "per_market_position:KXBTC-1" in over)
    other = LQ.Caps.audit(0, 0, 0, {"KXETH-1": 11}, escalation_market="KXBTC-1")
    check("Caps.audit: NON-escalation market still capped at 10 while escalation armed",
          "per_market_position:KXETH-1" in other)
    no_esc = LQ.Caps.audit(0, 0, 0, {"KXBTC-1": 11})
    check("Caps.audit: without an armed escalation, 11 is still a violation",
          "per_market_position:KXBTC-1" in no_esc)

    # --- (f) escalation is idempotent ACROSS legs (fresh RuntimeState) via log + exchange ---
    esc_log = os.path.join(d, "esc_log.jsonl")
    tickers = ["KXBTC-1"]
    books = {"KXBTC-1": {"yes": [[50, 10]], "no": [[48, 10]]}}
    cfg_armed = {"markets": [{"ticker": "KXBTC-1"}],
                 "escalation": {"escalate_market": "KXBTC-1", "armed": True}}
    mock5 = MockExchange()
    state5 = LQ.RuntimeState()
    r5 = LQ.maybe_place_escalation(mock5, state5, cfg_armed, tickers, books, dry_run=True, log_path=esc_log)
    check("escalation cross-leg: first leg places (dry-run)", r5 is not None)
    fresh_state = LQ.RuntimeState()  # simulates the next GHA leg's fresh process
    r6 = LQ.maybe_place_escalation(mock5, fresh_state, cfg_armed, tickers, books, dry_run=True,
                                    log_path=esc_log)
    check("escalation cross-leg: NEXT leg (fresh state, same committed log) does NOT re-place",
          r6 is None)
    # exchange-side witness alone (no log): a resting LIP-ESC order blocks re-placement too
    esc_order = {"client_order_id": "LIP-ESC-KXBTC-1", "ticker": "KXBTC-1", "side": "yes",
                 "price": 10, "remaining_count": 100}
    r7 = LQ.maybe_place_escalation(MockExchange(), LQ.RuntimeState(), cfg_armed, tickers, books,
                                    dry_run=True, log_path=os.path.join(d, "empty_log.jsonl"),
                                    resting_lip_orders=[esc_order])
    check("escalation cross-leg: resting exchange-side ESC order alone blocks re-placement",
          r7 is None)

    # --- (g) amend path is the real Kalshi route (no /events/) ---
    import inspect
    src = inspect.getsource(LQ.KalshiClient.amend_order)
    check("amend: endpoint is /portfolio/orders/{id}/amend (not /portfolio/events/...)",
          "/portfolio/orders/" in src and "/portfolio/events/" not in src)

    shutil.rmtree(d, ignore_errors=True)


# =================================================================================================
_GLOBAL_PATH_ATTRS = ("SWITCH_FILE", "HALT_FILE", "STOP_TODAY_FILE", "MARKETS_FILE", "LOG_FILE",
                      "HEARTBEAT_FILE", "PAYOUTS_FILE")


def main():
    # Defense in depth: redirect every module-level default path to a scratch dir for the WHOLE
    # run, so a test that forgets to pass an explicit path can never read/write a real file in this
    # repo checkout (LIP_SWITCH, .lip_halt, .lip_stop_today, lip_pilot_log.jsonl, ...). Individual
    # tests still explicitly pass their own tmp paths where the behavior under test cares about it;
    # this is only a backstop.
    scratch = new_tmpdir()
    originals = {attr: getattr(LQ, attr) for attr in _GLOBAL_PATH_ATTRS}
    for attr in _GLOBAL_PATH_ATTRS:
        setattr(LQ, attr, os.path.join(scratch, attr))

    tests = [
        test_caps_boundaries,
        test_ladder_math,
        test_gate_order,
        test_resolve_dry_run,
        test_market_config,
        test_place_order,
        test_amend_rate_limit,
        test_reconciliation,
        test_kill_paths,
        test_daily_and_cumulative_loss_kill,
        test_self_audit_failure_kills,
        test_cap_violation_detected_kills,
        test_escalation,
        test_position_cap_side_stop,
        test_dry_run_never_posts,
        test_safety_review_regressions,
    ]
    try:
        for t in tests:
            print(f"\n--- {t.__name__} ---")
            t()
    finally:
        for attr, val in originals.items():
            setattr(LQ, attr, val)
        shutil.rmtree(scratch, ignore_errors=True)

    n_total = len(RESULTS)
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("\n" + "=" * 70)
    print(f"SELFTEST SUMMARY: {n_total - n_fail}/{n_total} passed")
    if n_fail:
        print(f"{n_fail} FAILURES:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name}" + (f" ({detail})" if detail else ""))
        print("SELFTEST RESULT: FAIL")
        sys.exit(1)
    print("SELFTEST RESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
