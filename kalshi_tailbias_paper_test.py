"""kalshi_tailbias_paper_test.py -- self-contained test harness for kalshi_tailbias_paper.py.

Covers the pure-function surface (no network, no API keys):
  1. entry-band acceptance: tau band [8,10] min, tail-price band [0.07,0.15], two-sided-book
     requirement, and the "must be in tau band before entering" gate.
  2. tail-side identification, including a TIE (equal asks) -> None/ambiguous, no entry.
  3. fee math: ceil(7*p*(1-p)) cents on the taker entry price.
  4. settle classification: status=="finalized" settles with correct per-variant P&L; the OLD
     wrong status=="settled" check (root cause of a 24-day-silent-non-settlement bug in
     kalshi_longshot_paper.py) must NOT match here either (regression guard, applied from day
     one instead of retrofitted); staleness -> expired_unscored after STALE_PENDING_DAYS (2 --
     these are 15-minute markets, so 2 days unresolved is an API anomaly, not real pending state).
  5. the module has no order-placement / auth code path anywhere (paper-only, GET-only, no
     /portfolio, no API-key material) -- it is structurally incapable of placing a live order.

Run: python kalshi_tailbias_paper.py --selftest
 or: python kalshi_tailbias_paper_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import datetime as dt
import inspect
import sys

import kalshi_tailbias_paper as tb

_results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")


NOW = dt.datetime(2026, 7, 12, tzinfo=dt.timezone.utc)


# --------------------------------------------------------------------------------------------
# tail-side identification (incl. ties)
# --------------------------------------------------------------------------------------------
def test_tail_side_identification():
    ok1 = tb.identify_tail_side(0.10, 0.92) == "yes"     # YES cheaper -> YES is the tail
    record("cheaper YES ask identified as tail", ok1, f"got {tb.identify_tail_side(0.10, 0.92)!r}")

    ok2 = tb.identify_tail_side(0.90, 0.12) == "no"       # NO cheaper -> NO is the tail
    record("cheaper NO ask identified as tail", ok2, f"got {tb.identify_tail_side(0.90, 0.12)!r}")

    ok3 = tb.identify_tail_side(0.50, 0.50) is None        # tie -> ambiguous, no entry
    record("tied asks -> None (ambiguous, do not enter)", ok3, f"got {tb.identify_tail_side(0.50, 0.50)!r}")

    ok4 = tb.identify_tail_side(None, 0.10) is None and tb.identify_tail_side(0.10, None) is None
    record("missing price -> None", ok4, "")


# --------------------------------------------------------------------------------------------
# fee math
# --------------------------------------------------------------------------------------------
def test_fee_math():
    # ceil(7 * 0.9 * 0.1) = ceil(0.63) = 1
    ok1 = tb.taker_fee_cents(0.90) == 1
    record("fee ceil(7*p*(1-p)) at p=0.90 -> 1c", ok1, f"got {tb.taker_fee_cents(0.90)}")

    # ceil(7 * 0.5 * 0.5) = ceil(1.75) = 2
    ok2 = tb.taker_fee_cents(0.50) == 2
    record("fee at p=0.50 -> 2c", ok2, f"got {tb.taker_fee_cents(0.50)}")

    ok3 = tb.taker_fee_cents(None) is None and tb.taker_fee_cents(1.5) is None
    record("fee math rejects out-of-range/missing price", ok3, "")


# --------------------------------------------------------------------------------------------
# entry-band acceptance (evaluate_entry pure function)
# --------------------------------------------------------------------------------------------
def _book(tail_ask=0.10, spread=0.02, tail_side="yes"):
    """Build a two-sided book where the given side's ask == tail_ask."""
    if tail_side == "yes":
        ya = tail_ask
        yb = round(ya - spread, 4)
        nb = round(1.0 - ya, 4)             # yes_ask = 1 - no_bid
        na = round(1.0 - yb, 4)             # no_ask = 1 - yes_bid (favorite, expensive)
    else:
        na = tail_ask
        nb = round(na - spread, 4)
        yb = round(1.0 - na, 4)
        ya = round(1.0 - nb, 4)
    return yb, ya, nb, na


def test_entry_accepted_in_band():
    yb, ya, nb, na = _book(tail_ask=0.10, tail_side="yes")
    tau_s = 9 * 60.0                       # 9 minutes -- middle of [8,10]
    d = tb.evaluate_entry(yb, ya, nb, na, tau_s, yes_bid_qty=500, no_bid_qty=800)
    ok = d is not None and d["tail_side"] == "yes" and d["fav_side"] == "no" \
        and abs(d["tail_px"] - 0.10) < 1e-9 and d["taker_px"] == round(na, 4)
    record("in-band entry accepted, tail=YES -> BUY favorite (NO)", ok, f"{d}")


def test_entry_rejected_outside_tau_band():
    yb, ya, nb, na = _book(tail_ask=0.10, tail_side="yes")
    d_early = tb.evaluate_entry(yb, ya, nb, na, 11 * 60.0)   # tau=11min, before the window opens
    d_late = tb.evaluate_entry(yb, ya, nb, na, 5 * 60.0)     # tau=5min, after the window closes
    record("tau outside [8,10]min rejected (too early)", d_early is None, f"{d_early}")
    record("tau outside [8,10]min rejected (too late)", d_late is None, f"{d_late}")


def test_entry_rejected_outside_price_band():
    yb, ya, nb, na = _book(tail_ask=0.05, tail_side="yes")   # below TAIL_LO=0.07
    d_low = tb.evaluate_entry(yb, ya, nb, na, 9 * 60.0)
    record("tail price below [0.07,0.15] rejected", d_low is None, f"{d_low}")

    yb, ya, nb, na = _book(tail_ask=0.20, tail_side="yes")   # above TAIL_HI=0.15
    d_high = tb.evaluate_entry(yb, ya, nb, na, 9 * 60.0)
    record("tail price above [0.07,0.15] rejected", d_high is None, f"{d_high}")

    # boundary inclusivity
    yb, ya, nb, na = _book(tail_ask=0.07, tail_side="yes")
    d_lo_edge = tb.evaluate_entry(yb, ya, nb, na, 9 * 60.0)
    record("tail price at lower boundary 0.07 accepted (inclusive)", d_lo_edge is not None, f"{d_lo_edge}")

    yb, ya, nb, na = _book(tail_ask=0.15, tail_side="yes")
    d_hi_edge = tb.evaluate_entry(yb, ya, nb, na, 9 * 60.0)
    record("tail price at upper boundary 0.15 accepted (inclusive)", d_hi_edge is not None, f"{d_hi_edge}")


def test_entry_requires_two_sided_book():
    d = tb.evaluate_entry(None, None, 0.90, 0.95, 9 * 60.0)
    record("one-sided/missing book rejected", d is None, f"{d}")


def test_entry_tie_is_not_entered():
    d = tb.evaluate_entry(0.50, 0.50, 0.50, 0.50, 9 * 60.0)  # degenerate/tied, also invalid range
    record("tied book never enters a position", d is None, f"{d}")


# --------------------------------------------------------------------------------------------
# settle classification
# --------------------------------------------------------------------------------------------
def _pending(ts_days_ago=0.5, taker_px=0.90, maker_px=0.89, fav_side="no", ticker="KXBTC15M-26JAN01-T1"):
    return {
        "ts": (NOW - dt.timedelta(days=ts_days_ago)).isoformat(timespec="seconds"),
        "asset": "BTC", "ticker": ticker, "ws": 0, "we": 900, "tau_s_at_entry": 540.0,
        "tail_side": "yes" if fav_side == "no" else "no", "tail_px": round(1 - taker_px, 4),
        "fav_side": fav_side, "fav_bid": round(taker_px - 0.02, 4), "fav_ask": taker_px,
        "spread": 0.02, "size_at_touch": 400.0,
        "taker_px": taker_px, "taker_fee_c": tb.taker_fee_cents(taker_px), "maker_px": maker_px,
    }


def test_finalized_settles_with_correct_pnl_both_variants():
    # favorite=NO, result=no -> favorite WINS, settle_fav=1.0
    p = _pending(taker_px=0.90, maker_px=0.89, fav_side="no")
    m = {"status": "finalized", "result": "no"}
    action, row = tb.classify_settlement(p, m, NOW)
    exp_taker = round(1.0 - 0.90 - (p["taker_fee_c"] / 100.0), 4)
    exp_maker = round(1.0 - 0.89, 4)
    ok = (action == "settle" and row["status"] == "settled"
          and abs(row["pnl_taker"] - exp_taker) < 1e-9 and abs(row["pnl_maker"] - exp_maker) < 1e-9)
    record("finalized+favorite wins settles with correct taker & maker pnl", ok,
           f"action={action} row={row} exp_taker={exp_taker} exp_maker={exp_maker}")

    # favorite=NO, result=yes -> favorite LOSES, settle_fav=0.0
    p2 = _pending(taker_px=0.90, maker_px=0.89, fav_side="no")
    m2 = {"status": "finalized", "result": "yes"}
    action2, row2 = tb.classify_settlement(p2, m2, NOW)
    exp_taker2 = round(0.0 - 0.90 - (p2["taker_fee_c"] / 100.0), 4)
    ok2 = action2 == "settle" and abs(row2["pnl_taker"] - exp_taker2) < 1e-9
    record("finalized+favorite loses settles with correct (negative) taker pnl", ok2,
           f"action={action2} row={row2} exp_taker={exp_taker2}")


def test_old_wrong_status_string_does_not_settle():
    # regression guard for the same root cause fixed in kalshi_longshot_paper.py: Kalshi's API
    # never returns status=="settled" on a market object (only as a query FILTER value).
    p = _pending()
    m = {"status": "settled", "result": "no"}
    action, _ = tb.classify_settlement(p, m, NOW)
    record("literal status=='settled' does NOT settle (regression guard)", action != "settle",
           f"action={action}")


def test_closed_no_result_stays_pending_within_window():
    p = _pending(ts_days_ago=0.8)
    m = {"status": "closed", "result": ""}
    action, row = tb.classify_settlement(p, m, NOW)
    record("closed/no-result stays pending within staleness window", action == "pending" and row is None,
           f"action={action}")


def test_stale_unresolved_gets_expired_unscored():
    p = _pending(ts_days_ago=3.1)             # > STALE_PENDING_DAYS (2) -- .days must read >2
    m = {"status": "closed", "result": ""}
    action, row = tb.classify_settlement(p, m, NOW)
    ok = action == "expired" and row is not None and row["status"] == "expired_unscored" \
        and row["pnl_taker"] == "" and row["pnl_maker"] == ""
    record("stale unresolved (>2d) -> explicit expired_unscored row", ok, f"action={action} row={row}")


def test_vanished_market_404_also_ages_out():
    p = _pending(ts_days_ago=3.0)
    action, row = tb.classify_settlement(p, {}, NOW)   # fetch_market returns {} on 404/vanish
    ok = action == "expired" and row["status"] == "expired_unscored"
    record("vanished (404) market ages out to expired_unscored", ok, f"action={action}")


# --------------------------------------------------------------------------------------------
# structural: no order-placement / auth code path anywhere in the module
# --------------------------------------------------------------------------------------------
def test_no_network_write_or_order_placement_capability():
    src = inspect.getsource(tb)
    if tb.__doc__:
        # strip the module docstring itself -- it PROSE-describes what the module does NOT do
        # (e.g. mentions "/portfolio" while explaining there's no call to it), which would
        # otherwise false-positive this scan. Only the actual code must be clean.
        src = src.replace(tb.__doc__, "", 1)
    forbidden = ["method=\"POST\"", "method='POST'", "\"POST\"", "'POST'", "DELETE",
                 "PRIVATE_KEY", "API_KEY_ID", "/portfolio", "urlopen(urllib.request.Request(url, data",
                 "place_order", "cancel_order"]
    hits = [f for f in forbidden if f in src]
    record("module has no order-placement / auth code path (paper-only, GET-only)", not hits,
           f"hits={hits}")


def run() -> int:
    print("kalshi_tailbias_paper_test.py -- entry-band / tail-side / fee / settle regression tests\n")
    test_tail_side_identification()
    test_fee_math()
    test_entry_accepted_in_band()
    test_entry_rejected_outside_tau_band()
    test_entry_rejected_outside_price_band()
    test_entry_requires_two_sided_book()
    test_entry_tie_is_not_entered()
    test_finalized_settles_with_correct_pnl_both_variants()
    test_old_wrong_status_string_does_not_settle()
    test_closed_no_result_stays_pending_within_window()
    test_stale_unresolved_gets_expired_unscored()
    test_vanished_market_404_also_ages_out()
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
