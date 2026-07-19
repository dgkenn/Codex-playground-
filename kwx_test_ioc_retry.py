#!/usr/bin/env python3
"""kwx_test_ioc_retry.py -- unit tests for the bounded zero-fill IOC retry in kalshi_exec.py.

WHY THIS EXISTS: the live branch cannot be exercised end-to-end without credentials (correct -- nothing
in this batch trades). So we flip a KalshiExec instance to live=True and monkeypatch the two network
touchpoints (_post_order for the signed order POST, _requote_ask_cents for the public quote re-fetch)
to simulate the scenarios the retry must handle:
  (a) zero fill, ask re-quoted BELOW the cap        -> exactly one retry, DISTINCT client_order_id
  (b) zero fill, ask re-quoted ABOVE the cap        -> no retry (would overpay)
  (c) unknown fill state (reconcile returns None)   -> no retry (can't prove zero fill; retry risks doubling)
  (d) retry POST raises a non-HTTP error (timeout/connection drop AFTER the bytes left this process)
      -> fill_state="unknown" (NOT a clean zero-fill -- we can't prove the -r1 order didn't reach
      Kalshi or fill), the -r1 client_order_id is surfaced for reconciliation.
  (f) retry POST raises urllib.error.HTTPError (a DEFINITIVE rejection response) -> still a clean,
      provable zero-fill (not ambiguous) with the HTTP body captured.
  (g) HALT_FILE (.kwx_halt) appears BETWEEN the first attempt and the retry -> the retry is blocked by
      _guard exactly like a fresh order would be (the retry can no longer bypass the kill-switch).
Plus: (e) the re-quote parser handles integer-cents and *_dollars schemas and rejects garbage.

No network, no creds, no live orders: everything is monkeypatched; the exec log goes to a temp file.
Run: python kwx_test_ioc_retry.py   (exit 0 = all pass)
"""
import json, os, sys, tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_exec import KalshiExec  # noqa: E402

TICKER = "KXHIGHNY-26JUL17-T90"
FAILS = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def make_ex():
    """Dry-run-constructed KalshiExec flipped to live=True so buy_* takes the live branch; the network
    calls it would make are replaced per-test, so nothing real is ever sent."""
    ex = KalshiExec(log_path=tempfile.mkstemp(prefix="kwx_test_log_", suffix=".jsonl")[1])
    ex.live = True
    return ex


def order_resp(filled):
    """Minimal create-order response; filled=None yields an order object WITHOUT any fill fields,
    which _reconcile maps to (None, status) -- the 'unknown fill state' case."""
    o = {"status": "executed" if filled else "canceled"}
    if filled is not None:
        o["filled_count"] = filled
    return {"order": o}


def test_a_zero_fill_then_retry_fills():
    print("(a) zero fill -> re-quote below cap -> retry fills, ids differ")
    ex, posted = make_ex(), []

    def post(order):
        posted.append(order)
        return order_resp(0 if len(posted) == 1 else 7)
    ex._post_order = post
    ex._requote_ask_cents = lambda t, s: 88  # ask came back inside the 95c cap
    r = ex.buy_yes(TICKER, count=7, max_price_cents=95)
    check("two orders posted", len(posted) == 2, f"posted={len(posted)}")
    check("final filled==7", r.get("filled") == 7, str(r.get("filled")))
    check("attempts==2 recorded", r.get("attempts") == 2)
    check("retry attempted + re-quoted ask recorded",
          r.get("retry", {}).get("attempted") is True and r["retry"].get("requote_ask_c") == 88)
    check("first attempt zero fill preserved", r.get("first_attempt", {}).get("filled") == 0)
    ids = [o["client_order_id"] for o in posted]
    check("client_order_ids DIFFER (dedupe gotcha)", ids[0] != ids[1], str(ids))
    check("attempt-1 id is crash-idempotent unsuffixed", ids[0] == f"kwx-{TICKER}-yes")
    check("retry id deterministic '-r1'", ids[1] == f"kwx-{TICKER}-yes-r1")
    check("retry keeps original price cap", posted[1].get("yes_price") == 95)
    check("record shape backward-compatible",
          all(k in r for k in ("status", "ticker", "requested", "filled", "order_status", "response")))


def test_b_ask_above_cap_no_retry():
    print("(b) zero fill -> re-quote ABOVE cap -> no retry")
    ex, posted = make_ex(), []
    ex._post_order = lambda o: (posted.append(o), order_resp(0))[1]
    ex._requote_ask_cents = lambda t, s: 97  # moved above the 95c cap -> retrying would overpay
    r = ex.buy_no(TICKER, count=5, max_price_cents=95)
    check("only one order posted", len(posted) == 1, f"posted={len(posted)}")
    check("filled stays 0", r.get("filled") == 0)
    check("retry recorded as not attempted",
          r.get("retry", {}).get("attempted") is False and r["retry"].get("requote_ask_c") == 97)


def test_c_unknown_fill_no_retry():
    print("(c) unknown fill state -> no retry (never risk doubling)")
    ex, posted = make_ex(), []
    ex._post_order = lambda o: (posted.append(o), order_resp(None))[1]
    ex._requote_ask_cents = lambda t, s: (_ for _ in ()).throw(AssertionError("must not re-quote"))
    r = ex.buy_yes(TICKER, count=5, max_price_cents=95)
    check("only one order posted", len(posted) == 1, f"posted={len(posted)}")
    check("filled is None (unknown), untouched", r.get("filled") is None)
    check("no retry key on record", "retry" not in r)


def test_d_retry_ambiguous_error_is_unknown_not_flat():
    print("(d) retry POST raises non-HTTP error -> fill_state=unknown, NOT a clean zero-fill")
    ex, posted = make_ex(), []

    def post(order):
        posted.append(order)
        if len(posted) == 1:
            return order_resp(0)
        raise OSError("simulated network drop on retry")
    ex._post_order = post
    ex._requote_ask_cents = lambda t, s: 80
    r = ex.buy_yes(TICKER, count=5, max_price_cents=95)
    check("exactly two posts (no extra loop)", len(posted) == 2, f"posted={len(posted)}")
    check("filled is None (unknown), NOT clean zero", r.get("filled") is None, str(r.get("filled")))
    check("top-level fill_state==unknown", r.get("fill_state") == "unknown", str(r.get("fill_state")))
    check("retry.fill_state==unknown", r.get("retry", {}).get("fill_state") == "unknown")
    check("retry error captured", "error" in r.get("retry", {}))
    check("retry client_order_id surfaced for reconciliation",
          r.get("retry", {}).get("client_order_id") == f"kwx-{TICKER}-yes-r1")


def test_f_retry_http_rejection_is_clean_zero():
    print("(f) retry POST raises HTTPError (definitive rejection) -> still a clean zero-fill, body captured")
    import io
    ex, posted = make_ex(), []

    def post(order):
        posted.append(order)
        if len(posted) == 1:
            return order_resp(0)
        raise urllib.error.HTTPError(url="x", code=400, msg="bad request",
                                     hdrs=None, fp=io.BytesIO(b'{"error":"insufficient balance"}'))
    ex._post_order = post
    ex._requote_ask_cents = lambda t, s: 80
    r = ex.buy_yes(TICKER, count=5, max_price_cents=95)
    check("exactly two posts", len(posted) == 2, f"posted={len(posted)}")
    check("filled stays 0 (definitive rejection, not ambiguous)", r.get("filled") == 0)
    check("no fill_state=unknown leak", r.get("fill_state") != "unknown")
    check("HTTP body captured in retry error",
          "insufficient balance" in r.get("retry", {}).get("error", ""),
          str(r.get("retry")))


def test_g_halt_between_attempts_blocks_retry():
    print("(g) .kwx_halt appears BETWEEN the first attempt and the retry -> retry is blocked, not bypassed")
    import kalshi_exec as KE
    ex, posted = make_ex(), []
    halt_path = tempfile.mkstemp(prefix="kwx_test_halt_")[1]
    os.remove(halt_path)  # start absent
    real_halt = KE.HALT_FILE
    KE.HALT_FILE = halt_path

    def post(order):
        posted.append(order)
        # simulate the kill-switch being touched by an operator right after the first attempt lands
        if len(posted) == 1:
            open(halt_path, "w").write("emergency stop\n")
        return order_resp(0)
    try:
        ex._post_order = post
        ex._requote_ask_cents = lambda t, s: 80
        r = ex.buy_yes(TICKER, count=5, max_price_cents=95)
        check("only ONE order posted (retry never sent)", len(posted) == 1, f"posted={len(posted)}")
        check("retry recorded as not attempted", r.get("retry", {}).get("attempted") is False)
        check("guard reason surfaced", "halt" in str(r.get("retry", {}).get("reason", "")).lower(),
              str(r.get("retry")))
        check("filled stays 0 (original zero-fill stands)", r.get("filled") == 0)
    finally:
        KE.HALT_FILE = real_halt
        if os.path.exists(halt_path):
            os.remove(halt_path)


def test_e_requote_parsing():
    print("(e) re-quote parser: cents int / dollars fallback / garbage -> None")
    import kalshi_exec as KE
    ex = make_ex()

    class FakeResp:
        def __init__(self, payload):
            self._b = json.dumps(payload).encode()

        def read(self):
            return self._b
    real = KE.urllib.request.urlopen
    payload = {}
    KE.urllib.request.urlopen = lambda req, timeout=10, context=None: FakeResp(payload)
    try:
        payload = {"market": {"yes_ask": 42, "no_ask": 61}}
        check("integer-cents yes_ask", ex._requote_ask_cents(TICKER, "yes") == 42)
        check("integer-cents no_ask", ex._requote_ask_cents(TICKER, "no") == 61)
        payload = {"market": {"yes_ask_dollars": "0.55"}}
        check("dollars fallback", ex._requote_ask_cents(TICKER, "yes") == 55)
        payload = {"market": {"yes_ask": 0.55}}  # dollars float in the cents field must NOT read as 1c
        check("non-integral cents rejected", ex._requote_ask_cents(TICKER, "yes") is None)
        payload = {"market": {"yes_ask": 0}}  # 0 = no ask displayed
        check("zero ask -> None", ex._requote_ask_cents(TICKER, "yes") is None)
        payload = {"nope": True}
        check("missing market -> None", ex._requote_ask_cents(TICKER, "yes") is None)
    finally:
        KE.urllib.request.urlopen = real


if __name__ == "__main__":
    tests = (test_a_zero_fill_then_retry_fills, test_b_ask_above_cap_no_retry,
             test_c_unknown_fill_no_retry, test_d_retry_ambiguous_error_is_unknown_not_flat,
             test_f_retry_http_rejection_is_clean_zero, test_g_halt_between_attempts_blocks_retry,
             test_e_requote_parsing)
    for t in tests:
        t()
    print(("ALL %d CHECK GROUPS PASS" % len(tests)) if not FAILS else f"FAILURES: {FAILS}")
    sys.exit(1 if FAILS else 0)
