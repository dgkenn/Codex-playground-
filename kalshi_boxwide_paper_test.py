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
  7. the P60/P300 DUAL-TRACK disposal-policy state machine: both policies share the single strand
     (first-fill) event and lock together off a shared crossing, but each watches its OWN deadline
     independently, so one can dispose while the other keeps watching and later resolves
     differently (a lock after the other already disposed, or a later dispose at a different exit
     price) -- and the pending-state/settled-CSV schema upgrade that lets rows written by the
     pre-P300 code pick up P300 tracking (or gracefully report P60-only) once loaded by this code.

Run: python kalshi_boxwide_paper.py --selftest
 or: python kalshi_boxwide_paper_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
import os
import sys
import tempfile

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
            "t_fill": None, "t_fill_iso": None, "cost": None, "dispose_deadline": None,
            "p60_done": False, "p60_result": None,
            "p300_deadline": None, "p300_done": False, "p300_result": None}


def _stranded_row(asset="BTC", entry_mid=0.50, w=0.15, strand_side="yes", ws=None, we=None,
                   entry_ts=None, t_fill=None):
    """A row already past the armed->stranded transition, with both P60 and P300 deadlines set
    the same way run_cycle/_advance_row would set them on a real first-fill event."""
    row = _fresh_row(asset=asset, entry_mid=entry_mid, w=w, ws=ws, we=we, entry_ts=entry_ts)
    t_fill = t_fill if t_fill is not None else row["entry_ts"]
    cost = row["L_yes"] if strand_side == "yes" else row["L_no"]
    row.update(state="stranded", strand_side=strand_side, t_fill=t_fill, t_fill_iso=bw.iso(),
               cost=cost, dispose_deadline=t_fill + bw.DISPOSE_DELAY_S,
               p60_done=False, p60_result=None,
               p300_deadline=bw.p300_deadline_for(t_fill, row["we"]),
               p300_done=False, p300_result=None)
    return row


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
        and new_row["strand_side"] == "yes" \
        and new_row["p60_done"] is False and new_row["p60_result"] is None \
        and new_row["p300_done"] is False and new_row["p300_result"] is None \
        and new_row["p300_deadline"] is not None
    record("armed -> stranded on a single leg fill (both P60/P300 tracks armed, still watching)",
           ok, f"{new_row}")


def test_advance_row_armed_both_legs_locks_immediately():
    row = _fresh_row(entry_mid=0.50)
    with _BookPatch(book=(0.70, 0.30, 0.30, 0.70, True)):   # both cross simultaneously
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "locked" \
        and abs(settled["pnl"] - bw.lock_pnl(row["w"])) < 1e-9 \
        and settled["p300_outcome"] == "locked" \
        and abs(settled["p300_pnl"] - bw.lock_pnl(row["w"])) < 1e-9
    record("armed -> locked when both legs cross in one poll (never stranded -> P60==P300 trivially)",
           ok, f"{settled}")


def test_advance_row_stranded_completes_within_60s_locks_both_policies():
    # SHARED LOCK: the completing leg crosses well before EITHER policy's deadline, so both
    # P60 and P300 are still watching and lock together off the same crossing event.
    row = _stranded_row(entry_mid=0.50, strand_side="yes")   # L_yes=0.35, trig_no=0.65
    now = dt.datetime.fromtimestamp(row["t_fill"] + 5.0, dt.timezone.utc)
    with _BookPatch(book=(0.66, 0.40, 0.30, 0.60, True)):   # yes_bid=0.66 >= trig_no(0.65) -> completes
        new_row, settled = bw._advance_row(row, now)
    ok = new_row is None and settled is not None and settled["outcome"] == "locked" \
        and settled["p300_outcome"] == "locked" \
        and abs(settled["pnl"] - settled["p300_pnl"]) < 1e-9
    record("stranded -> both P60 and P300 lock together on a shared early completion", ok,
           f"{settled}")


def test_advance_row_p60_disposes_p300_keeps_watching():
    # DIVERGENT DISPOSAL TIMING: P60's 60s deadline has passed with no completion, so P60 disposes
    # -- but P300's (much later) deadline has not, so P300 stays "watching" and the row stays
    # PENDING (not settled) until P300 also resolves.
    row = _stranded_row(entry_mid=0.50, strand_side="yes")
    now = dt.datetime.fromtimestamp(row["t_fill"] + 61.0, dt.timezone.utc)   # past P60's deadline
    assert now.timestamp() < row["p300_deadline"], "test setup: must be before P300's own deadline"
    with _BookPatch(book=(0.40, 0.42, 0.58, 0.60, True)):     # mid~0.41, other leg NOT crossed
        new_row, settled = bw._advance_row(row, now)
    ok = settled is None and new_row is not None and new_row["state"] == "stranded" \
        and new_row["p60_done"] is True and new_row["p60_result"]["outcome"] == "disposed" \
        and new_row["p300_done"] is False and new_row["p300_result"] is None
    record("P60 disposes at its 60s deadline while P300 keeps watching (row stays pending)", ok,
           f"{new_row}")


def _row_with_p60_already_disposed(entry_mid=0.50, strand_side="yes", p60_dispose_mid=0.41):
    """Helper: a stranded row where P60 has ALREADY reached a terminal "disposed" outcome (as
    test_advance_row_p60_disposes_p300_keeps_watching demonstrates happens for real) but P300 is
    still watching -- used to exercise what happens to the SAME box from that point forward."""
    row = _stranded_row(entry_mid=entry_mid, strand_side=strand_side)
    pnl, fee_c, _ = bw.dispose_outcome(strand_side, row["cost"], p60_dispose_mid)
    row["p60_done"] = True
    row["p60_result"] = {"outcome": "disposed", "dispose_mid": round(p60_dispose_mid, 4),
                          "fee_c": fee_c, "pnl": pnl, "t_settle_iso": bw.iso()}
    return row


def test_advance_row_p300_locks_after_p60_already_disposed():
    # DIVERGENT OUTCOME: same box, P60 already disposed (a realized loss/cost), but P300 -- still
    # watching -- catches the completing leg and locks for the deterministic 2W profit instead.
    row = _row_with_p60_already_disposed(entry_mid=0.50, strand_side="yes")
    now = dt.datetime.fromtimestamp(row["t_fill"] + 90.0, dt.timezone.utc)   # before P300's deadline
    with _BookPatch(book=(0.66, 0.40, 0.30, 0.60, True)):   # yes_bid=0.66 >= trig_no(0.65) -> completes
        new_row, settled = bw._advance_row(row, now)
    ok = new_row is None and settled is not None \
        and settled["outcome"] == "disposed" and abs(settled["pnl"] - row["p60_result"]["pnl"]) < 1e-9 \
        and settled["p300_outcome"] == "locked" \
        and abs(settled["p300_pnl"] - bw.lock_pnl(row["w"])) < 1e-9
    record("P300 locks after P60 already disposed -- same box, DIFFERENT outcomes per policy", ok,
           f"{settled}")


def test_advance_row_p300_disposes_later_at_different_price():
    # DIVERGENT DISPOSAL PRICE: both policies end up "disposed", but P300 exits later, at
    # whatever the mid has drifted to by then -- not necessarily the same price P60 exited at.
    row = _row_with_p60_already_disposed(entry_mid=0.50, strand_side="yes", p60_dispose_mid=0.41)
    now = dt.datetime.fromtimestamp(row["p300_deadline"] + 1.0, dt.timezone.utc)
    with _BookPatch(book=(0.48, 0.50, 0.50, 0.52, True)):   # mid ~0.49 now, moved since P60's exit
        new_row, settled = bw._advance_row(row, now)
    ok = new_row is None and settled is not None \
        and settled["outcome"] == "disposed" and settled["p300_outcome"] == "disposed" \
        and abs(float(settled["dispose_mid"]) - 0.41) < 1e-9 \
        and abs(float(settled["p300_dispose_mid"]) - 0.49) < 1e-9 \
        and abs(settled["pnl"] - settled["p300_pnl"]) > 1e-9
    record("P300 disposes later than P60, at a different (drifted) exit price -> different pnl",
           ok, f"{settled}")


def test_advance_row_armed_closes_neither_at_window_end():
    row = _fresh_row(entry_mid=0.50, we=time_now() - 1.0)   # window already closed
    with _BookPatch(book=(0.50, 0.60, 0.40, 0.50, True)):    # neither level crossed
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "neither" \
        and settled["pnl"] == 0.0 and settled["p300_outcome"] == "neither" \
        and settled["p300_pnl"] == 0.0
    record("armed -> neither at window close with no fill (both policies agree, never stranded)",
           ok, f"{settled}")


def test_advance_row_stale_expires():
    row = _fresh_row(entry_mid=0.50, entry_ts=time_now() - bw.STALE_ROW_S - 10.0)
    with _BookPatch(book=(None, None, None, None, False)):   # persistently unfetchable
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["status"] == "expired_unscored" \
        and settled["p300_status"] == "expired_unscored"
    record("stale unfetchable row -> expired_unscored (both policies, all-or-nothing)", ok,
           f"{settled}")


def test_advance_row_ride_forced_when_window_closed_before_dispose():
    # Both P60's AND P300's deadlines are past (P300's window_close-45s cap makes this the common
    # case once a strand survives to window close) -- both independently fall back to settlement.
    row = _fresh_row(entry_mid=0.50, we=time_now() - 5.0)         # window already closed
    past = time_now() - 1.0
    row.update(state="stranded", strand_side="yes", cost=row["L_yes"],
               t_fill=row["entry_ts"], t_fill_iso=row["entry_ts_iso"],
               dispose_deadline=past, p60_done=False, p60_result=None,
               p300_deadline=past, p300_done=False, p300_result=None)
    with _BookPatch(book=(None, None, None, None, False),        # book gone post-close
                     market={"status": "finalized", "result": "yes"}):
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = new_row is None and settled is not None and settled["outcome"] == "ride_forced" \
        and abs(settled["pnl"] - bw.ride_pnl("yes", row["L_yes"], 1.0)) < 1e-9 \
        and settled["p300_outcome"] == "ride_forced" \
        and abs(settled["p300_pnl"] - bw.ride_pnl("yes", row["L_yes"], 1.0)) < 1e-9
    record("stranded + book gone post-close -> BOTH policies ride_forced via settlement", ok,
           f"{settled}")


def test_p300_deadline_for_normal_case_uses_300s():
    # Strand early in a normal window -- t_fill+300 comfortably precedes window_close-45s, so the
    # 300s cap binds, not the close buffer.
    t_fill = 1_000_000.0
    we = t_fill + 700.0                              # window closes well after t_fill+300
    d = bw.p300_deadline_for(t_fill, we)
    ok = abs(d - (t_fill + bw.P300_DISPOSE_DELAY_S)) < 1e-9
    record("p300_deadline_for uses the 300s cap in the normal (early-strand) case", ok, f"got {d}")


def test_p300_deadline_for_late_strand_uses_close_buffer():
    # A strand forming very late in the window -- window_close-45s arrives before t_fill+300s, so
    # the close buffer binds instead.
    t_fill = 1_000_000.0
    we = t_fill + 60.0                               # window closes only 60s after the strand
    d = bw.p300_deadline_for(t_fill, we)
    ok = abs(d - (we - bw.P300_CLOSE_BUFFER_S)) < 1e-9 and d < t_fill + bw.P300_DISPOSE_DELAY_S
    record("p300_deadline_for uses the window_close-45s cap on a late strand", ok, f"got {d}")


# --------------------------------------------------------------------------------------------
# schema backward-compat: pending rows / settled CSV written by the pre-P300 code
# --------------------------------------------------------------------------------------------
def test_settled_fields_has_p300_columns():
    expected = {"p300_outcome", "p300_dispose_mid", "p300_fee_c", "p300_pnl", "p300_status"}
    ok = expected.issubset(set(bw.SETTLED_FIELDS)) and bw.SETTLED_FIELDS.index("status") < \
        min(bw.SETTLED_FIELDS.index(f) for f in expected)
    record("SETTLED_FIELDS carries the new p300_* columns after the original P60 columns", ok,
           f"{bw.SETTLED_FIELDS}")


def test_upgrade_row_for_p300_armed_row_gets_inert_defaults():
    old_armed = {"state": "armed", "asset": "BTC", "ticker": "T", "ws": 0, "we": 900,
                 "entry_ts": 0, "entry_ts_iso": "", "entry_mid": 0.5, "w": 0.15, "L_yes": 0.35,
                 "L_no": 0.35, "trig_no": 0.65, "strand_side": None, "t_fill": None,
                 "t_fill_iso": None, "cost": None, "dispose_deadline": None}
    up = bw.upgrade_row_for_p300(dict(old_armed))
    ok = up["p60_done"] is False and up["p60_result"] is None and up["p300_done"] is False \
        and up["p300_result"] is None and up["p300_deadline"] is None
    record("upgrade_row_for_p300 on an old armed row -> inert P300 defaults (not yet stranded)",
           ok, f"{up}")


def test_upgrade_row_for_p300_stranded_row_backfills_deadline():
    old_stranded = {"state": "stranded", "asset": "BTC", "ticker": "T", "ws": 0, "we": 900,
                     "entry_ts": 0, "entry_ts_iso": "", "entry_mid": 0.5, "w": 0.15,
                     "L_yes": 0.35, "L_no": 0.35, "trig_no": 0.65, "strand_side": "yes",
                     "t_fill": 130.0, "t_fill_iso": "", "cost": 0.35, "dispose_deadline": 190.0}
    up = bw.upgrade_row_for_p300(dict(old_stranded))
    exp_deadline = bw.p300_deadline_for(130.0, 900)
    ok = up["p60_done"] is False and up["p60_result"] is None and up["p300_done"] is False \
        and up["p300_result"] is None and abs(up["p300_deadline"] - exp_deadline) < 1e-9
    record("upgrade_row_for_p300 on an old in-flight stranded row -> backfills a real P300 "
           "deadline from its existing t_fill/we (picks up tracking mid-strand)", ok, f"{up}")


def test_upgrade_row_for_p300_is_idempotent():
    row = _stranded_row(entry_mid=0.5, strand_side="yes")
    before = dict(row)
    up = bw.upgrade_row_for_p300(dict(row))
    ok = up["p300_deadline"] == before["p300_deadline"] and up["p60_done"] == before["p60_done"]
    record("upgrade_row_for_p300 is a no-op on an already-current row", ok, f"{up}")


def test_load_pending_upgrades_old_schema_json_on_disk():
    old_pending = [
        {"state": "armed", "asset": "BTC", "ticker": "TA", "ws": 0, "we": 900, "entry_ts": 0,
         "entry_ts_iso": "", "entry_mid": 0.5, "w": 0.15, "L_yes": 0.35, "L_no": 0.35,
         "trig_no": 0.65, "strand_side": None, "t_fill": None, "t_fill_iso": None, "cost": None,
         "dispose_deadline": None},
        {"state": "stranded", "asset": "ETH", "ticker": "TB", "ws": 0, "we": 900, "entry_ts": 0,
         "entry_ts_iso": "", "entry_mid": 0.5, "w": 0.15, "L_yes": 0.35, "L_no": 0.35,
         "trig_no": 0.65, "strand_side": "no", "t_fill": 140.0, "t_fill_iso": "", "cost": 0.35,
         "dispose_deadline": 200.0},
    ]
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w") as f:
            json.dump(old_pending, f)
        loaded = bw.load_pending(path)
        armed, stranded = loaded[0], loaded[1]
        ok = ("p60_done" in armed and armed["p60_done"] is False and armed["p300_deadline"] is None
              and "p60_done" in stranded and stranded["p60_done"] is False
              and abs(stranded["p300_deadline"] - bw.p300_deadline_for(140.0, 900)) < 1e-9)
        record("load_pending upgrades an old-schema pending.json in place on load", ok,
               f"{loaded}")
    finally:
        os.remove(path)


def test_advance_row_stranded_missing_p300_fields_upgrades_and_advances():
    # A raw pre-P300 stranded row handed straight to _advance_row (not pre-processed by
    # load_pending) must still work -- _advance_row upgrades it itself before advancing either
    # policy, so an old row picks up P300 tracking on its very next cycle instead of erroring.
    t_fill = time_now() - 5.0
    row = {"state": "stranded", "asset": "BTC", "ticker": "KXBTC15M-TEST-T1", "ws": t_fill - 130,
           "we": t_fill + 700, "entry_ts": t_fill - 130, "entry_ts_iso": bw.iso(),
           "entry_mid": 0.5, "w": 0.15, "L_yes": 0.35, "L_no": 0.35, "trig_no": 0.65,
           "strand_side": "yes", "t_fill": t_fill, "t_fill_iso": bw.iso(), "cost": 0.35,
           "dispose_deadline": t_fill + 60.0}
    assert "p60_done" not in row and "p300_deadline" not in row, "test setup: old-schema row"
    with _BookPatch(book=(0.40, 0.42, 0.58, 0.60, True)):     # mid~0.41, no completion yet
        new_row, settled = bw._advance_row(row, bw.now_utc())
    ok = settled is None and new_row is not None and "p60_done" in new_row \
        and new_row["p60_done"] is False and new_row["p300_deadline"] is not None \
        and abs(new_row["p300_deadline"] - bw.p300_deadline_for(t_fill, row["we"])) < 1e-9
    record("_advance_row upgrades a raw old-schema stranded row before advancing either policy",
           ok, f"{new_row}")


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
    test_advance_row_stranded_completes_within_60s_locks_both_policies()
    test_advance_row_p60_disposes_p300_keeps_watching()
    test_advance_row_p300_locks_after_p60_already_disposed()
    test_advance_row_p300_disposes_later_at_different_price()
    test_advance_row_armed_closes_neither_at_window_end()
    test_advance_row_stale_expires()
    test_advance_row_ride_forced_when_window_closed_before_dispose()
    test_p300_deadline_for_normal_case_uses_300s()
    test_p300_deadline_for_late_strand_uses_close_buffer()
    test_settled_fields_has_p300_columns()
    test_upgrade_row_for_p300_armed_row_gets_inert_defaults()
    test_upgrade_row_for_p300_stranded_row_backfills_deadline()
    test_upgrade_row_for_p300_is_idempotent()
    test_load_pending_upgrades_old_schema_json_on_disk()
    test_advance_row_stranded_missing_p300_fields_upgrades_and_advances()
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
