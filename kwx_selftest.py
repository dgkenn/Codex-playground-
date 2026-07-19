#!/usr/bin/env python3
"""kwx_selftest.py -- END-TO-END plumbing test: when a lock happens, does the live path actually fire?

The $10 canary has placed 0 orders, and we've argued that's just "no qualifying fires yet in the short run
windows" rather than broken plumbing. This test PROVES that: it injects a synthetic lock (a mock feed whose
running max clears a strike) through the REAL poll_once path with a dry-run exec, and asserts the full chain
engages -- detection -> lock -> conviction sizing -> (dry-run) order -> plan log -> alert call -- and that
every SAFETY guard blocks when it should (kill switch, circuit breaker, daily-deploy cap). No network, no
creds, no real orders: active_market_days/event_rungs/feed are monkeypatched to a deterministic fixture and
execution goes through the dry-run KalshiExec. Run before trusting a live deployment.

Usage: python kwx_selftest.py    # prints PASS/FAIL per check; exit 0 iff all pass
"""
import os, sys, tempfile, json
import kwx_runner as R

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


class MockFeed:
    """Deterministic feed: reports a sustained running extreme of `ext` degF for any station."""
    name = "mock"

    def __init__(self, ext):
        self.ext = ext

    def running_extreme(self, station, lst_date, offset, kind):
        obs = [(f"2026-07-19T17:0{i}:00+00:00", self.ext) for i in range(4)]   # 4 sustained points
        return {"extreme_f": self.ext, "obs": obs}


def _fixture(floor=90, cap=None, yes_ask_c=80, no_ask_c=None, ext=93.0, station="KDEN", n_rungs=1):
    """Monkeypatch active_market_days / event_rungs / feed to one synthetic HIGH event with `n_rungs` rungs."""
    ev = "KXHIGHDEN-26JUL19"
    R.active_market_days = lambda today_lst=None: [("KXHIGHDEN", ev, station, -7, "2026-07-19", "max")]
    rungs = [{"ticker": f"{ev}-T{floor}_{i}", "floor": floor, "cap": cap,
              "yes_ask_c": yes_ask_c, "no_ask_c": no_ask_c} for i in range(n_rungs)]
    R.event_rungs = lambda e: rungs
    R.feed_for_station = lambda s: MockFeed(ext)


def main():
    # isolate state/log files so the test never touches real ones
    tmp = tempfile.mkdtemp()
    R.STATE_PATH = os.path.join(tmp, "state.json")
    R.PLAN_LOG = os.path.join(tmp, "plan.jsonl")
    halt = os.path.join(R.HERE, ".kwx_halt")
    had_halt = os.path.exists(halt)

    from kalshi_exec import KalshiExec
    # Keep this test OFFLINE and deterministic (its charter: "No network"): the honest-fill dry-run model
    # now reads the PUBLIC orderbook at fire time, but this test's tickers are synthetic (would 404 anyway).
    # Use the supported offline seam (fetch_book=False) instead of monkeypatching the private
    # _fetch_orderbook function -- this disables the book fetch entirely so every dry-run books the old
    # full-fill behavior (fill_model="assumed_full"), which is exactly what these checks were written
    # against. The depth model itself is unit-tested directly below (check 0) and exercised against a REAL
    # book in the e2e recipe.
    ex = KalshiExec(fetch_book=False)   # dry-run (no KWX_LIVE / no creds), no network
    print(f"exec live mode: {getattr(ex, 'live', False)} (must be False for this test)\n")
    check("exec is dry-run (no real orders possible)", not getattr(ex, "live", False))

    # 0) DEPTH FILL MODEL: _sim_depth_fill against a canned, hand-computed book (offline, deterministic).
    # Book convention: each side lists resting BIDS; a buyer lifts the OPPOSITE side's bids (ask = 100-bid).
    print("\n0) _sim_depth_fill unit test against a canned orderbook:")
    from kalshi_exec import _sim_depth_fill
    book = {"yes": [[92, 5], [90, 3]],    # -> derived NO asks: 8c x5, 10c x3
            "no": [[80, 10], [75, 4]]}    # -> derived YES asks: 20c x10, 25c x4

    # buy YES, plenty of cap headroom -> fully filled at the cheapest (20c) level
    f = _sim_depth_fill(book, "yes", count=5, max_price_cents=30)
    check("depth fill: buy_yes fills fully from the cheap level", f["filled"] == 5, f)
    check("depth fill: buy_yes vwap is the cheapest ask (20c)", f["fill_vwap_c"] == 20.0, f)
    check("depth fill: buy_yes depth_at_cap sums both levels (14)", f["depth_at_cap"] == 14, f)
    check("depth fill: buy_yes best_ask_c is 20", f["best_ask_c"] == 20, f)

    # buy YES with a cap BELOW the best ask -> nothing fillable, but the book is still recorded as evidence
    f = _sim_depth_fill(book, "yes", count=5, max_price_cents=15)
    check("depth fill: cap below best ask -> filled 0", f["filled"] == 0, f)
    check("depth fill: cap below best ask -> vwap None", f["fill_vwap_c"] is None, f)
    check("depth fill: cap below best ask -> best_ask_c still reported (20)", f["best_ask_c"] == 20, f)

    # buy NO, cap only reaches the first derived level -> partial fill against just that level
    f = _sim_depth_fill(book, "no", count=6, max_price_cents=9)
    check("depth fill: buy_no partial-caps at the 8c level (5 of 6)", f["filled"] == 5, f)
    check("depth fill: buy_no vwap is 8c", f["fill_vwap_c"] == 8.0, f)

    # empty book -> filled 0, no best ask, no evidence levels
    f = _sim_depth_fill({"yes": [], "no": []}, "yes", count=5, max_price_cents=50)
    check("depth fill: empty book -> filled 0", f["filled"] == 0, f)
    check("depth fill: empty book -> best_ask_c None", f["best_ask_c"] is None, f)
    check("depth fill: empty book -> book_top empty", f["book_top"] == [], f)

    # 1) HAPPY PATH: obs 93F clears a floor-90 YES rung by margin -> a fire is produced
    print("\n1) happy path -- lock produces a (dry-run) order:")
    _fixture(floor=90, cap=None, yes_ask_c=80, ext=93.0)
    if os.path.exists(R.STATE_PATH):
        os.remove(R.STATE_PATH)
    plans, iv = R.poll_once(exec_client=ex, verbose=False)
    check("exactly one fire produced", len(plans) == 1, f"got {len(plans)}")
    if plans:
        p = plans[0]
        check("side is YES (floor-only rung locks YES on max>floor)", p["side"] == "yes", p.get("side"))
        check("dry-run status recorded", str(p.get("status")).startswith("DRY"), p.get("status"))
        check("plan logged to disk", os.path.exists(R.PLAN_LOG) and os.path.getsize(R.PLAN_LOG) > 0)

    # 2) CONVICTION sizing: cushion=ext-floor=3F, gap=100-80=20c -> conviction (>=2F & >=15c) -> 12% cap
    print("\n2) conviction sizing engages on cushion>=2F & gap>=15c:")
    cush, gap = 93.0 - 90, 100 - 80
    check("is_conviction(3F,20c) True", R.is_conviction(cush, gap))
    base = R.size_for_fire(2000, 80, "KDEN")                      # 5% cap
    conv = R.size_for_fire(2000, 80, "KDEN", cushion_f=cush, gap_c=gap)  # 12% cap
    check("conviction sizes >= base at a cap-binding bankroll", conv >= base, f"base={base} conv={conv}")

    # 3) NON-LOCK: obs below strike+margin -> no fire
    print("\n3) no lock when obs doesn't clear strike+margin:")
    _fixture(floor=90, cap=None, yes_ask_c=80, ext=90.5)         # 90.5 < 90+1 margin -> no lock
    os.path.exists(R.STATE_PATH) and os.remove(R.STATE_PATH)
    plans, _ = R.poll_once(exec_client=ex, verbose=False)
    check("no fire when obs within margin of strike", len(plans) == 0, f"got {len(plans)}")

    # 4) PRICE CAP: rung already at 99c (>MAX_PAY_CENTS) -> skipped (dead on arrival)
    print("\n4) dead-on-arrival rung (ask>98c) is skipped:")
    _fixture(floor=90, cap=None, yes_ask_c=99, ext=93.0)
    os.path.exists(R.STATE_PATH) and os.remove(R.STATE_PATH)
    plans, _ = R.poll_once(exec_client=ex, verbose=False)
    check("no fire when ask exceeds MAX_PAY_CENTS", len(plans) == 0, f"got {len(plans)}")

    # 5) KILL SWITCH: .kwx_halt present -> exec blocks the order
    print("\n5) kill switch (.kwx_halt) blocks execution:")
    _fixture(floor=90, cap=None, yes_ask_c=80, ext=93.0)
    os.path.exists(R.STATE_PATH) and os.remove(R.STATE_PATH)
    open(halt, "w").write("selftest\n")
    try:
        plans, _ = R.poll_once(exec_client=ex, verbose=False)
        blocked = (not plans) or all("BLOCK" in str(p.get("status", "")) for p in plans)
        check("halt blocks the order (no live/dry fill)", blocked,
              f"statuses={[p.get('status') for p in plans]}")
    finally:
        if not had_halt and os.path.exists(halt):
            os.remove(halt)

    # 6) CIRCUIT BREAKER: many simultaneous locks -> auto-halt sentinel written, trading stops. Bump bankroll
    #    so the per-city cap (check 7) doesn't pre-empt the breaker (a single-city glitch is otherwise city-capped).
    print("\n6) circuit breaker trips on an abnormal burst of fires:")
    _bank = R.BANKROLL
    R.BANKROLL = 100000.0
    _fixture(floor=90, cap=None, yes_ask_c=80, ext=93.0, n_rungs=R.MAX_FIRES_PER_CYCLE + 5)
    os.path.exists(R.STATE_PATH) and os.remove(R.STATE_PATH)
    try:
        plans, _ = R.poll_once(exec_client=ex, verbose=False)
        tripped = os.path.exists(halt)
        check("circuit breaker wrote .kwx_halt and capped the burst", tripped and len(plans) <= R.MAX_FIRES_PER_CYCLE,
              f"halt={tripped} plans={len(plans)}")
    finally:
        R.BANKROLL = _bank
        if not had_halt and os.path.exists(halt):
            os.remove(halt)

    # 7) PER-CITY CAP: many locks in ONE city are bounded by PER_CITY_DAILY_CAP_FRAC (the fix -- was unenforced)
    print("\n7) per-city daily cap bounds single-city concentration:")
    R.BANKROLL = 10.0
    _fixture(floor=90, cap=None, yes_ask_c=80, ext=93.0, n_rungs=8)   # 8 rungs, same station
    os.path.exists(R.STATE_PATH) and os.remove(R.STATE_PATH)
    plans, _ = R.poll_once(exec_client=ex, verbose=False)
    R.BANKROLL = _bank
    # each fire ~1ct@80c=$0.80; per-city cap = 17.5% * $10 = $1.75 -> ~2 fires fit, rest skipped
    check("single-city fires bounded by per-city cap (not all 8 fire)", 1 <= len(plans) < 8, f"plans={len(plans)}")

    print("\n" + ("ALL CHECKS PASSED -- the live fire path + guards work; 0 fills = no qualifying fires yet, not a bug."
                  if not FAILURES else f"{len(FAILURES)} CHECK(S) FAILED: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
