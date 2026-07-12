"""kalshi_longshot_paper_test.py -- self-contained test harness for kalshi_longshot_paper.py.

Covers the BUG-1 fix (paper tracker never settled for 24 days):
  1. status=="finalized" (Kalshi's real per-market field value) settles with correct P&L.
  2. status=="settled" (the OLD, wrong check) must NOT match -- regression guard.
  3. status=="closed"/no result stays pending while within the staleness window.
  4. a position past the staleness window with no result gets an explicit
     status=expired_unscored row instead of being silently dropped.
  5. entry filter (accepts_market) rejects markets closing >60 days out, and accepts
     an otherwise-valid market closing within the window.
  6. the module never issues a network write / order-placing call (paper-only, no auth).

No network access, no API keys. Run: python kalshi_longshot_paper.py --selftest
                                  or: python kalshi_longshot_paper_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import datetime as dt
import inspect
import sys

import kalshi_longshot_paper as lp

_results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")


NOW = dt.datetime(2026, 7, 12, tzinfo=dt.timezone.utc)


def _pending(ts_days_ago=1, entry=0.10, ticker="KXFOO-26JAN01-T1"):
    return {
        "ts": (NOW - dt.timedelta(days=ts_days_ago)).isoformat(timespec="seconds"),
        "ticker": ticker, "category": "Politics", "entry_sell_yes": entry,
        "vol_at_entry": 100.0,
    }


def test_finalized_settles_with_correct_pnl():
    p = _pending(entry=0.12)
    m = {"status": "finalized", "result": "no", "volume_fp": "250"}
    action, row = lp.classify_settlement(p, m, NOW)
    ok = action == "settle" and row["pnl_per_contract"] == 0.12 and row["status"] == "settled"
    record("finalized+no settles, pnl=entry-0", ok, f"action={action} row={row}")

    p2 = _pending(entry=0.08)
    m2 = {"status": "finalized", "result": "yes", "volume_fp": "300"}
    action2, row2 = lp.classify_settlement(p2, m2, NOW)
    ok2 = action2 == "settle" and abs(row2["pnl_per_contract"] - (0.08 - 1.0)) < 1e-9
    record("finalized+yes settles, pnl=entry-1", ok2, f"action={action2} row={row2}")


def test_old_wrong_status_string_no_longer_matches_anything_useful():
    # Regression guard for the actual root cause: the OLD code checked status=="settled",
    # which Kalshi's API never returns on a market object (only "settled" as a query-string
    # FILTER value, never as the returned `status` field). Confirm the fixed classifier does
    # NOT settle on that literal string -- if this ever starts passing, someone regressed
    # back to the wrong field value.
    p = _pending()
    m = {"status": "settled", "result": "no"}  # the wrong value the old code expected
    action, _ = lp.classify_settlement(p, m, NOW)
    record("literal status=='settled' does NOT settle (regression guard)", action != "settle",
           f"action={action}")


def test_closed_no_result_stays_pending_within_window():
    p = _pending(ts_days_ago=5)
    m = {"status": "closed", "result": ""}   # e.g. KXLOWTMIA-26JUL07-B74.5: closed, awaiting source
    action, row = lp.classify_settlement(p, m, NOW)
    record("closed/no-result stays pending inside staleness window", action == "pending" and row is None,
           f"action={action}")


def test_stale_unresolved_gets_expired_unscored_not_silently_dropped():
    p = _pending(ts_days_ago=46)             # > STALE_PENDING_DAYS default (45)
    m = {"status": "closed", "result": ""}
    action, row = lp.classify_settlement(p, m, NOW)
    ok = action == "expired" and row is not None and row["status"] == "expired_unscored" \
        and row["pnl_per_contract"] == ""
    record("stale unresolved -> explicit expired_unscored row (not dropped)", ok, f"action={action} row={row}")


def test_vanished_market_404_also_ages_out_explicitly():
    p = _pending(ts_days_ago=50)
    action, row = lp.classify_settlement(p, {}, NOW)   # get() returns {} on 404/vanish
    ok = action == "expired" and row["status"] == "expired_unscored"
    record("vanished (404) market also ages out to expired_unscored", ok, f"action={action}")


def test_far_dated_entry_rejected_over_60_days():
    now_iso = lambda days: (NOW + dt.timedelta(days=days)).isoformat().replace("+00:00", "Z")
    base = {
        "fee_type": "quadratic", "market_type": "binary",
        "yes_bid_dollars": "0.08", "yes_ask_dollars": "0.10",
        "volume_fp": "500", "open_time": (NOW - dt.timedelta(days=1)).isoformat().replace("+00:00", "Z"),
    }
    far = dict(base, close_time=now_iso(90))     # 90 days out -- must be rejected
    near = dict(base, close_time=now_iso(10))    # 10 days out -- should be accepted

    # _days_to_close/_life_frac call dt.datetime.now() internally (real wall-clock "now"),
    # not the fixed NOW above -- fine here since we only assert *relative* behavior
    # (open_time is 1 day before NOW and close_time is NOW+90d / NOW+10d, both of which are
    # comfortably within the real present at test-run time).
    far_ok = not lp.accepts_market(far)
    near_ok = lp.accepts_market(near)
    record("far-dated (close >60d out) entry rejected", far_ok, f"accepts_market(far)={not far_ok}")
    record("near-dated (close <=60d out) otherwise-valid entry accepted", near_ok, f"accepts_market(near)={near_ok}")


def test_no_network_write_or_order_placement_capability():
    src = inspect.getsource(lp)
    # the whole module must be GET-only: no POST/DELETE method args, no API-key/private-key
    # auth material anywhere (this is the paper tracker -- it must be structurally incapable
    # of placing a live order, unlike kalshi_longshot_bot.py).
    forbidden = ["method=\"POST\"", "method='POST'", "PRIVATE_KEY", "API_KEY_ID", "orders", "/portfolio"]
    hits = [f for f in forbidden if f in src]
    record("module has no order-placement / auth code path", not hits, f"hits={hits}")


def run() -> int:
    print("kalshi_longshot_paper_test.py -- BUG1 settle-logic regression tests\n")
    test_finalized_settles_with_correct_pnl()
    test_old_wrong_status_string_no_longer_matches_anything_useful()
    test_closed_no_result_stays_pending_within_window()
    test_stale_unresolved_gets_expired_unscored_not_silently_dropped()
    test_vanished_market_404_also_ages_out_explicitly()
    test_far_dated_entry_rejected_over_60_days()
    test_no_network_write_or_order_placement_capability()

    n = len(_results)
    failed = [r for r in _results if not r[1]]
    print(f"\n{n - len(failed)}/{n} PASSED")
    if failed:
        print("FAILURES:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
