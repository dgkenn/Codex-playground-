"""kalshi_boxwide_paper_test.py -- self-contained test harness for kalshi_boxwide_paper.py.

Covers the pure-function/state-machine surface (no network, no API keys):
  1. level computation: L_yes/L_no/trig_no arithmetic, degenerate-mid rejection.
  2. crossing detection: touch-mode hit/no-hit on both legs, simultaneous double-hit.
  3. fee math: ceil(7*p*(1-p)) cents (shared formula w/ kalshi_tailbias_paper.py).
  4. P&L math: locked (deterministic 2W), disposed (managed-strand taker cross), ride-forced
     (settlement fallback).
  5. the row state machine (_advance_row via run_cycle-level building blocks): armed -> stranded
     on first fill, stranded -> locked on completion within 60s, stranded -> disposed at the 60s
     deadline, armed -> neither at window close with no fill, stale rows -> expired_unscored.
  6. the module has no order-placement / auth code path anywhere (paper-only, GET-only, no
     /portfolio, no API-key material) -- it is structurally incapable of placing a live order.

Run: python kalshi_boxwide_paper.py --selftest
 or: python kalshi_boxwide_paper_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import inspect
import sys

import kalshi_boxwide_paper as bw

_results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")


# --------------------------------------------------------------------------------------------
# level computation
# --------------------------------------------------------------------------------------------
def test_compute_levels():
    L_yes, L_no, trig_no = bw.compute_levels(0.50, w=0.15)
    ok = abs(L_yes - 0.35) < 1e-9 and abs(L_no - 0.35) < 1e-9 and abs(trig_no - 0.65) < 1e-9
    record("compute_levels at mid=0.50 W=0.15 is symmetric", ok,
           f"L_yes={L_yes} L_no={L_no} trig_no={trig_no}")

    # box cost check: L_yes + L_no == 1 - 2W by construction (locked P&L relies on this)
    ok2 = abs((L_yes + L_no) - (1.0 - 2 * 0.15)) < 1e-9
    record("L_yes + L_no == 1 - 2W (deterministic lock cost)", ok2, f"sum={L_yes + L_no}")

    L_yes2, L_no2, _ = bw.compute_levels(0.20, w=0.15)
    ok3 = abs(L_yes2 - 0.05) < 1e-9 and abs(L_no2 - 0.65) < 1e-9
    record("compute_levels at mid=0.20 W=0.15 asymmetric as expected", ok3,
           f"L_yes={L_yes2} L_no={L_no2}")


def test_levels_valid_rejects_degenerate():
    # mid very close to 0: L_yes goes non-positive
    L_yes, L_no, _ = bw.compute_levels(0.10, w=0.15)
    ok = not bw.levels_valid(L_yes, L_no)
    record("degenerate near-zero mid rejected by levels_valid", ok, f"L_yes={L_yes} L_no={L_no}")

    L_yes2, L_no2, _ = bw.compute_levels(0.50, w=0.15)
    ok2 = bw.levels_valid(L_yes2, L_no2)
    record("mid-market levels accepted by levels_valid", ok2, f"L_yes={L_yes2} L_no={L_no2}")


# --------------------------------------------------------------------------------------------
# crossing detection
# --------------------------------------------------------------------------------------------
def test_check_leg_fill():
    L_yes, L_no, trig_no = bw.compute_levels(0.50, w=0.15)   # L_yes=0.35, trig_no=0.65

    yes_hit, no_hit = bw.check_leg_fill(yes_bid=0.50, yes_ask=0.34, L_yes=L_yes, trig_no=trig_no)
    record("yes leg hits when ask <= L_yes", yes_hit and not no_hit, f"{(yes_hit, no_hit)}")

    yes_hit2, no_hit2 = bw.check_leg_fill(yes_bid=0.66, yes_ask=0.60, L_yes=L_yes, trig_no=trig_no)
    record("no leg hits when bid >= trig_no", no_hit2 and not yes_hit2, f"{(yes_hit2, no_hit2)}")

    yes_hit3, no_hit3 = bw.check_leg_fill(yes_bid=0.50, yes_ask=0.60, L_yes=L_yes, trig_no=trig_no)
    record("neither leg hits inside the band", not yes_hit3 and not no_hit3, f"{(yes_hit3, no_hit3)}")

    yes_hit4, no_hit4 = bw.check_leg_fill(yes_bid=None, yes_ask=None, L_yes=L_yes, trig_no=trig_no)
    record("missing book -> no hits (None-safe)", not yes_hit4 and not no_hit4, f"{(yes_hit4, no_hit4)}")

    # simultaneous double-hit (both legs cross in the same poll) is representable
    yes_hit5, no_hit5 = bw.check_leg_fill(yes_bid=0.70, yes_ask=0.30, L_yes=L_yes, trig_no=trig_no)
    record("both legs can hit in the same poll", yes_hit5 and no_hit5, f"{(yes_hit5, no_hit5)}")


# --------------------------------------------------------------------------------------------
# fee math
# --------------------------------------------------------------------------------------------
def test_fee_math():
    ok1 = bw.taker_fee_cents(0.90) == 1     # ceil(7*0.9*0.1)=ceil(0.63)=1
    record("fee ceil(7*p*(1-p)) at p=0.90 -> 1c", ok1, f"got {bw.taker_fee_cents(0.90)}")

    ok2 = bw.taker_fee_cents(0.50) == 2     # ceil(7*0.5*0.5)=ceil(1.75)=2
    record("fee at p=0.50 -> 2c", ok2, f"got {bw.taker_fee_cents(0.50)}")

    ok3 = bw.taker_fee_cents(None) is None and bw.taker_fee_cents(1.5) is None
    record("fee math rejects out-of-range/missing price", ok3, "")


# --------------------------------------------------------------------------------------------
# P&L math
# --------------------------------------------------------------------------------------------
def test_lock_pnl_deterministic():
    ok = abs(bw.lock_pnl(0.15) - 0.30) < 1e-9
    record("lock_pnl(W=0.15) == 2W == 0.30", ok, f"got {bw.lock_pnl(0.15)}")


def test_dispose_outcome_yes_strand():
    # YES strand, cost=L_yes=0.35, exit_mid=0.40 -> proceeds=0.39, fee=ceil(7*.4*.6)=ceil(1.68)=2c
    pnl, fee_c, proceeds = bw.dispose_outcome("yes", cost=0.35, exit_mid=0.40)
    exp_proceeds = 0.39
    exp_fee = 2
    exp_pnl = round(exp_proceeds - 0.35 - exp_fee / 100.0, 4)
    ok = abs(proceeds - exp_proceeds) < 1e-9 and fee_c == exp_fee and abs(pnl - exp_pnl) < 1e-9
    record("dispose_outcome YES strand math", ok,
           f"pnl={pnl} fee_c={fee_c} proceeds={proceeds} exp=({exp_pnl},{exp_fee},{exp_proceeds})")


def test_dispose_outcome_no_strand():
    # NO strand, cost=L_no=0.35, exit_mid(YES)=0.60 -> no_mid=0.40, proceeds=0.39,
    # fee=ceil(7*.4*.6)=2c
    pnl, fee_c, proceeds = bw.dispose_outcome("no", cost=0.35, exit_mid=0.60)
    exp_proceeds = 0.39
    exp_fee = 2
    exp_pnl = round(exp_proceeds - 0.35 - exp_fee / 100.0, 4)
    ok = abs(proceeds - exp_proceeds) < 1e-9 and fee_c == exp_fee and abs(pnl - exp_pnl) < 1e-9
    record("dispose_outcome NO strand math (uses 1-exit_mid)", ok,
           f"pnl={pnl} fee_c={fee_c} proceeds={proceeds} exp=({exp_pnl},{exp_fee},{exp_proceeds})")


def test_ride_pnl():
    ok1 = abs(bw.ride_pnl("yes", cost=0.35, resolved_yes=1.0) - 0.65) < 1e-9
    record("ride_pnl YES strand, resolves YES", ok1, f"got {bw.ride_pnl('yes', 0.35, 1.0)}")

    ok2 = abs(bw.ride_pnl("yes", cost=0.35, resolved_yes=0.0) - (-0.35)) < 1e-9
    record("ride_pnl YES strand, resolves NO (total loss of cost)", ok2,
           f"got {bw.ride_pnl('yes', 0.35, 0.0)}")

    ok3 = abs(bw.ride_pnl("no", cost=0.35, resolved_yes=0.0) - 0.65) < 1e-9
    record("ride_pnl NO strand, resolves NO", ok3, f"got {bw.ride_pnl('no', 0.35, 0.0)}")


# --------------------------------------------------------------------------------------------
# row state machine (_advance_row) -- network-free by monkeypatching fetch_book/fetch_market
# --------------------------------------------------------------------------------------------
def _fresh_row(asset="BTC", entry_mid=0.50, w=0.15, ws=None, we=None, entry_ts=None):
    import time as _t
    now = entry_ts if entry_ts is not None else _t.time()
    ws = ws if ws is not None else now - 130.0     # ~2min10s into the window already
    we = we if we is not None else ws + 900.0
    L_yes, L_no, trig_no = bw.compute_levels(entry_mid, w=w)
    return {"state": "armed", "asset": asset, "ticker": "KXBTC15M-TEST-T1", "ws": ws, "we": we,
            "entry_ts": now, "entry_ts_iso": bw.iso(), "entry_mid": entry_mid, "w": w,
            "L_yes": L_yes, "L_no": L_no, "trig_no": trig_no, "strand_side": None,
            "t_fill": None, "t_fill_iso": None, "cost": None, "dispose_deadline": None}


class _BookPatch:
    """Context manager: monkeypatch bw.fetch_book to return a fixed quad, bw.fetch_market for the
    ride-forced fallback path."""
    def __init__(self, book=None, market=None):
        self.book = book if book is not None else (None, None, None, None, False)
        self.market = market if market is not None else {}

    def __enter__(self):
        self._orig_book = bw.fetch_book
        self._orig_market = bw.fetch_market
        bw.fetch_book = lambda ticker: self.book
        bw.fetch_market = lambda ticker: self.market
        return self

    def __exit__(self, *a):
        bw.fetch_book = self._orig_book
        bw.fetch_market = self._orig_market


def test_advance_row_armed_to_stranded_on_one_leg():
    row = _fresh_row(entry_mid=0.50)                     # L_yes=0.35, trig_no=0.65
    with _BookPatch(book=(0.50, 0.34, 0.50, 0.66, True)):   # yes_ask=0.34 <= 0.35 -> yes leg hits
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = settled is None and new_row is not None and new_row["state"] == "stranded" \
        and new_row["strand_side"] == "yes"
    record("armed -> stranded on a single leg fill", ok, f"{new_row}")


def test_advance_row_armed_both_legs_locks_immediately():
    row = _fresh_row(entry_mid=0.50)
    with _BookPatch(book=(0.70, 0.30, 0.30, 0.70, True)):   # both cross simultaneously
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "locked" \
        and abs(settled["pnl"] - bw.lock_pnl(row["w"])) < 1e-9
    record("armed -> locked when both legs cross in one poll", ok, f"{settled}")


def test_advance_row_stranded_completes_within_60s_locks():
    row = _fresh_row(entry_mid=0.50)
    row.update(state="stranded", strand_side="yes", cost=row["L_yes"],
               t_fill=row["entry_ts"], t_fill_iso=row["entry_ts_iso"],
               dispose_deadline=row["entry_ts"] + 60.0)
    with _BookPatch(book=(0.66, 0.40, 0.30, 0.60, True)):   # yes_bid=0.66 >= trig_no(0.65) -> completes
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "locked"
    record("stranded -> locked when the other leg completes", ok, f"{settled}")


def test_advance_row_stranded_disposes_at_deadline():
    import datetime as dt
    row = _fresh_row(entry_mid=0.50)
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    row.update(state="stranded", strand_side="yes", cost=row["L_yes"],
               t_fill=row["entry_ts"], t_fill_iso=row["entry_ts_iso"],
               dispose_deadline=past.timestamp())              # deadline already passed
    with _BookPatch(book=(0.40, 0.42, 0.58, 0.60, True)):       # mid ~0.41, no completion
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "disposed" \
        and settled["dispose_mid"] is not None
    record("stranded -> disposed at the 60s deadline (no completion)", ok, f"{settled}")


def test_advance_row_armed_closes_neither_at_window_end():
    row = _fresh_row(entry_mid=0.50, we=time_now() - 1.0)   # window already closed
    with _BookPatch(book=(0.50, 0.60, 0.40, 0.50, True)):    # neither level crossed
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "neither" \
        and settled["pnl"] == 0.0
    record("armed -> neither at window close with no fill", ok, f"{settled}")


def test_advance_row_stale_expires():
    row = _fresh_row(entry_mid=0.50, entry_ts=time_now() - bw.STALE_ROW_S - 10.0)
    with _BookPatch(book=(None, None, None, None, False)):   # persistently unfetchable
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["status"] == "expired_unscored"
    record("stale unfetchable row -> expired_unscored", ok, f"{settled}")


def test_advance_row_ride_forced_when_window_closed_before_dispose():
    import datetime as dt
    row = _fresh_row(entry_mid=0.50, we=time_now() - 5.0)         # window already closed
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    row.update(state="stranded", strand_side="yes", cost=row["L_yes"],
               t_fill=row["entry_ts"], t_fill_iso=row["entry_ts_iso"],
               dispose_deadline=past.timestamp())
    with _BookPatch(book=(None, None, None, None, False),        # book gone post-close
                     market={"status": "finalized", "result": "yes"}):
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "ride_forced" \
        and abs(settled["pnl"] - bw.ride_pnl("yes", row["L_yes"], 1.0)) < 1e-9
    record("stranded + book gone post-close -> ride_forced via settlement", ok, f"{settled}")


def time_now():
    import time as _t
    return _t.time()


# --------------------------------------------------------------------------------------------
# structural: no order-placement / auth code path anywhere in the module
# --------------------------------------------------------------------------------------------
def test_no_network_write_or_order_placement_capability():
    src = inspect.getsource(bw)
    if bw.__doc__:
        src = src.replace(bw.__doc__, "", 1)
    forbidden = ["method=\"POST\"", "method='POST'", "\"POST\"", "'POST'", "DELETE",
                 "PRIVATE_KEY", "API_KEY_ID", "/portfolio", "urlopen(urllib.request.Request(url, data",
                 "place_order", "cancel_order"]
    hits = [f for f in forbidden if f in src]
    record("module has no order-placement / auth code path (paper-only, GET-only)", not hits,
           f"hits={hits}")


def run() -> int:
    print("kalshi_boxwide_paper_test.py -- level/crossing/fee/state-machine regression tests\n")
    test_compute_levels()
    test_levels_valid_rejects_degenerate()
    test_check_leg_fill()
    test_fee_math()
    test_lock_pnl_deterministic()
    test_dispose_outcome_yes_strand()
    test_dispose_outcome_no_strand()
    test_ride_pnl()
    test_advance_row_armed_to_stranded_on_one_leg()
    test_advance_row_armed_both_legs_locks_immediately()
    test_advance_row_stranded_completes_within_60s_locks()
    test_advance_row_stranded_disposes_at_deadline()
    test_advance_row_armed_closes_neither_at_window_end()
    test_advance_row_stale_expires()
    test_advance_row_ride_forced_when_window_closed_before_dispose()
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
