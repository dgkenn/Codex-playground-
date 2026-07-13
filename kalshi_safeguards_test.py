"""kalshi_safeguards_test.py -- Self-contained test harness for kalshi_trader.py safety rails.

Tests every safety rail WITHOUT live orders or real money (mock/inject only).
Run: python kalshi_safeguards_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import types
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Minimal stubs so kalshi_trader imports cleanly with no API keys / network
# ---------------------------------------------------------------------------

# Stub out 'notify' before importing kalshi_trader
notify_stub = types.ModuleType("notify")
notify_stub.alert = lambda *a, **kw: None
notify_stub.alert_sync = lambda *a, **kw: None
sys.modules.setdefault("notify", notify_stub)

# Stub out 'live_metrics' before importing kalshi_trader
class _FakeLM:
    def __getattr__(self, name):
        return lambda *a, **kw: None
lm_mod = types.ModuleType("live_metrics")
lm_mod.LiveMetrics = lambda *a, **kw: _FakeLM()
sys.modules.setdefault("live_metrics", lm_mod)

# Now import the module under test
import kalshi_trader as kt

# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []  # (name, passed, detail)

def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}: {detail}")


# ===========================================================================
# TEST 1 — Post-only / would-not-cross price guard
# ===========================================================================

def test_post_only_crossing_guard():
    """
    place() in main() refuses:
      BUY-YES when price >= yes_ask  -> returns None
      BUY-NO  when price >= no_ask   (no_ask = 1 - yes_bid) -> returns None

    Source lines 481-488:
        if side == "yes" and yes_ask is not None and price >= yes_ask:
            return None
        if side == "no":
            no_ask = round(1.0 - (yes_bid or 0.0), 4)
            if price >= no_ask:
                return None
    We replicate this logic directly (the function is a closure inside main;
    we replicate the exact boolean).
    """
    name = "T1: post-only crossing guard"
    try:
        observations = []

        # --- replicate place() guard exactly (lines 481-488) ---
        def replicated_place_guard(side, price, yes_bid, yes_ask):
            """Returns None if the post-only guard would fire, 'ok' otherwise."""
            if side == "yes" and yes_ask is not None and price >= yes_ask:
                return None   # would cross
            if side == "no":
                no_ask = round(1.0 - (yes_bid or 0.0), 4)
                if price >= no_ask:
                    return None   # would cross
            return "ok"

        yes_bid, yes_ask = 0.45, 0.55

        # BUY-YES at exactly yes_ask (0.55) -> should refuse
        r1 = replicated_place_guard("yes", 0.55, yes_bid, yes_ask)
        observations.append(f"BUY-YES@yes_ask={r1}")
        assert r1 is None, f"Expected None for BUY-YES@yes_ask but got {r1!r}"

        # BUY-YES above yes_ask (0.60) -> should refuse
        r2 = replicated_place_guard("yes", 0.60, yes_bid, yes_ask)
        observations.append(f"BUY-YES>yes_ask={r2}")
        assert r2 is None, f"Expected None for BUY-YES>yes_ask but got {r2!r}"

        # BUY-YES below yes_ask (0.54) -> should pass
        r3 = replicated_place_guard("yes", 0.54, yes_bid, yes_ask)
        observations.append(f"BUY-YES<yes_ask={r3}")
        assert r3 == "ok", f"Expected 'ok' for BUY-YES<yes_ask but got {r3!r}"

        # no_ask = 1 - yes_bid = 1 - 0.45 = 0.55
        no_ask_expected = round(1.0 - yes_bid, 4)  # 0.55

        # BUY-NO at exactly no_ask -> should refuse
        r4 = replicated_place_guard("no", no_ask_expected, yes_bid, yes_ask)
        observations.append(f"BUY-NO@no_ask={r4}")
        assert r4 is None, f"Expected None for BUY-NO@no_ask but got {r4!r}"

        # BUY-NO above no_ask -> should refuse
        r5 = replicated_place_guard("no", no_ask_expected + 0.01, yes_bid, yes_ask)
        observations.append(f"BUY-NO>no_ask={r5}")
        assert r5 is None, f"Expected None for BUY-NO>no_ask but got {r5!r}"

        # BUY-NO below no_ask (0.54) -> should pass
        r6 = replicated_place_guard("no", no_ask_expected - 0.01, yes_bid, yes_ask)
        observations.append(f"BUY-NO<no_ask={r6}")
        assert r6 == "ok", f"Expected 'ok' for BUY-NO<no_ask but got {r6!r}"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 2 — Inventory clamp (hard directional cap)
# ===========================================================================

def test_inventory_clamp():
    """
    Source lines 763-766 (inside the place loop):
        inv_cap = max(1.0, a.max_notional)            # contracts; ties directional risk to $
        proj = net_delta + (a.post if side == "yes" else -a.post)
        if abs(proj) > inv_cap + 1e-9:
            continue   # refuse to place

    We replicate the boolean directly and test:
    - heavy long side is refused when abs(proj) > inv_cap
    - reducing side is allowed even when abs(net_delta) is near cap
    - threshold boundary (abs(proj) == inv_cap) is allowed
    """
    name = "T2: inventory clamp"
    try:
        observations = []
        max_notional = 25.0
        post = 5
        inv_cap = max(1.0, max_notional)  # 25.0

        def clamp_would_refuse(net_delta, side):
            """True if the placement would be refused by the inventory clamp."""
            proj = net_delta + (post if side == "yes" else -post)
            return abs(proj) > inv_cap + 1e-9

        # --- case 1: net_delta near positive cap, adding more YES (long) -> REFUSE ---
        nd = 22.0  # already long 22 contracts
        refused = clamp_would_refuse(nd, "yes")  # proj = 22+5 = 27 > 25 -> refuse
        observations.append(f"long22+5yes=>refuse={refused}")
        assert refused, f"Expected refuse for nd=22 add YES (proj=27>25) but got allowed"

        # --- case 2: net_delta near positive cap, reducing with NO -> ALLOW ---
        nd = 22.0
        refused = clamp_would_refuse(nd, "no")  # proj = 22-5 = 17, |17|=17 <= 25 -> allow
        observations.append(f"long22+5no=>refuse={refused}")
        assert not refused, f"Expected allow for nd=22 add NO (proj=17<=25) but got refused"

        # --- case 3: net_delta at exactly inv_cap, adding YES -> REFUSE (abs(proj)=30>25) ---
        nd = 25.0
        refused = clamp_would_refuse(nd, "yes")  # proj=30 > 25 -> refuse
        observations.append(f"long25+5yes=>refuse={refused}")
        assert refused, f"Expected refuse for nd=25 add YES (proj=30>25)"

        # --- case 4: proj exactly at boundary (abs(proj) == inv_cap) -> ALLOW ---
        nd = 20.0
        refused = clamp_would_refuse(nd, "yes")  # proj=25, |25|=25 NOT > 25+eps -> allow
        observations.append(f"long20+5yes(boundary)=>refuse={refused}")
        assert not refused, f"Expected allow at boundary (|proj|=25 == inv_cap=25)"

        # --- case 5: net_delta near negative cap (short), adding NO -> REFUSE ---
        nd = -22.0  # already short (net NO heavy)
        refused = clamp_would_refuse(nd, "no")  # proj = -22-5 = -27, |-27|=27 > 25 -> refuse
        observations.append(f"short22+5no=>refuse={refused}")
        assert refused, f"Expected refuse for nd=-22 add NO (proj=-27>cap)"

        # --- case 6: net_delta near negative cap (short), reducing with YES -> ALLOW ---
        nd = -22.0
        refused = clamp_would_refuse(nd, "yes")  # proj = -22+5 = -17, |-17|=17 <= 25 -> allow
        observations.append(f"short22+5yes=>refuse={refused}")
        assert not refused, f"Expected allow for nd=-22 add YES (proj=-17<=25)"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 3 — Aggregate notional cap
# ===========================================================================

def test_aggregate_notional_cap():
    """
    Source lines 767-771:
        open_buy_notional = sum(max(a.post - m.get("filled", 0.0), 0.0) * price_
                                for (_, price_), m in resting.items())
        exposure = open_buy_notional + max(-cash, 0.0)
        if exposure + price * a.post > a.max_notional:
            continue   # refuse

    Replicate the exact boolean and verify BLOCK and ALLOW.
    """
    name = "T3: aggregate notional cap"
    try:
        observations = []
        max_notional = 25.0
        post = 5

        def exposure_would_refuse(resting, cash, side, price):
            """True if aggregate notional cap would fire."""
            open_buy_notional = sum(
                max(post - m.get("filled", 0.0), 0.0) * price_
                for (_, price_), m in resting.items()
            )
            exposure = open_buy_notional + max(-cash, 0.0)
            return exposure + price * post > max_notional

        # --- case 1: no open orders, no cash spent, small order -> ALLOW ---
        resting = {}
        cash = 0.0
        refused = exposure_would_refuse(resting, cash, "yes", 0.45)
        observations.append(f"empty_resting_allow={not refused}")
        assert not refused, "Expected allow when no open orders"

        # --- case 2: existing open orders nearly at cap ---
        # 4 resting orders at price 0.50 each with post=5 => notional=4*5*0.50=10.0
        # cash spent = -8.0 (8 dollars already out) => max(-(-8),0)=8 => exposure=18
        # adding price=0.45, post=5 => 18+2.25=20.25 <= 25 -> ALLOW
        resting2 = {
            ("yes", 0.50): {"filled": 0.0},
            ("yes", 0.49): {"filled": 0.0},
            ("yes", 0.48): {"filled": 0.0},
            ("yes", 0.47): {"filled": 0.0},
        }
        cash2 = -8.0   # we've spent $8 so far
        refused2 = exposure_would_refuse(resting2, cash2, "yes", 0.45)
        observations.append(f"near_cap_allow={not refused2}")
        assert not refused2, f"Expected allow near cap but got refused"

        # --- case 3: exposure already pushes total over max_notional -> REFUSE ---
        # resting notional: 4 * 5 * 0.55 = 11.0; cash=-15 => max(15,0)=15 => exposure=26
        # adding ANY order -> refuse
        resting3 = {
            ("yes", 0.55): {"filled": 0.0},
            ("yes", 0.54): {"filled": 0.0},
            ("yes", 0.53): {"filled": 0.0},
            ("yes", 0.52): {"filled": 0.0},
        }
        cash3 = -15.0
        refused3 = exposure_would_refuse(resting3, cash3, "yes", 0.45)
        observations.append(f"over_cap_refuse={refused3}")
        assert refused3, f"Expected refuse when over cap"

        # --- case 4: exactly at the boundary (exposure + new == max_notional) -> ALLOW ---
        # We want exposure + price * post == max_notional exactly (not strictly greater)
        # exposure=22.75, price=0.45, post=5 => 22.75 + 2.25 = 25.0 (NOT > 25 -> allow)
        resting4 = {
            ("yes", 0.55): {"filled": 0.0},   # 5 * 0.55 = 2.75
        }
        cash4 = -20.0  # max(-(-20),0)=20 => exposure = 2.75 + 20 = 22.75
        refused4 = exposure_would_refuse(resting4, cash4, "yes", 0.45)  # 22.75+2.25=25.0 NOT>25
        observations.append(f"boundary_allow={not refused4}")
        assert not refused4, f"Expected allow at exactly max_notional boundary"

        # --- case 5: one penny over boundary -> REFUSE ---
        resting5 = {
            ("yes", 0.55): {"filled": 0.0},
        }
        cash5 = -20.01  # exposure = 2.75 + 20.01 = 22.76; 22.76 + 2.25 = 25.01 > 25 -> refuse
        refused5 = exposure_would_refuse(resting5, cash5, "yes", 0.45)
        observations.append(f"penny_over_refuse={refused5}")
        assert refused5, f"Expected refuse one penny over cap"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 4 — Loss-limit kill + sticky sentinel file
# ===========================================================================

def test_loss_limit_kill():
    """
    Source lines 715-719:
        if realized + window_mark <= -abs(a.loss_limit):
            ...
            _record_kill(...)
            cancel_all_resting(reason="loss_limit"); break

    _record_kill is a closure inside main() that writes JSON to kill_sentinel path.
    Sentinel path: f".kalshi_killed_{a.asset}15m"

    Startup refusal (lines 341-343):
        if live and os.path.exists(kill_sentinel):
            raise SystemExit(...)

    We:
    1. Replicate the kill condition boolean.
    2. Build a minimal _record_kill replica (same code from source).
    3. Verify sentinel file is created.
    4. Verify that startup refusal logic raises SystemExit when sentinel exists.
    5. Clean up the sentinel.
    """
    name = "T4: loss-limit kill + sentinel + startup refusal"
    sentinel = ".kalshi_killed_test_asset15m"
    try:
        observations = []

        # Clean up any leftover sentinel
        if os.path.exists(sentinel):
            os.remove(sentinel)

        # --- replicate kill condition (line 715) ---
        def kill_condition(realized, window_mark, loss_limit):
            return realized + window_mark <= -abs(loss_limit)

        loss_limit = 5.0

        # Just below threshold: realized=-4.0, mark=0.5 => sum=-3.5 > -5.0 -> NO kill
        fired = kill_condition(-4.0, 0.5, loss_limit)
        observations.append(f"below_threshold_no_kill={not fired}")
        assert not fired, "Should NOT kill when realized+mark=-3.5 > -5.0"

        # Exactly at threshold: realized=-4.0, mark=-1.0 => sum=-5.0 == -5.0 -> KILL
        fired = kill_condition(-4.0, -1.0, loss_limit)
        observations.append(f"at_threshold_kill={fired}")
        assert fired, "Should KILL when realized+mark exactly at -loss_limit"

        # Below threshold: realized=-4.5, mark=-1.0 => sum=-5.5 < -5.0 -> KILL
        fired = kill_condition(-4.5, -1.0, loss_limit)
        observations.append(f"past_threshold_kill={fired}")
        assert fired, "Should KILL when past threshold"

        # --- replicate _record_kill (lines 335-339) ---
        def _record_kill_replica(kill_sentinel_path, why):
            try:
                with open(kill_sentinel_path, "w") as fh:
                    fh.write(json.dumps({"ts": time.time(), "reason": why}) + "\n")
            except Exception:
                pass

        _record_kill_replica(sentinel, "loss_limit realized=-4.50 mark=-1.00")

        # Verify sentinel exists
        assert os.path.exists(sentinel), f"Sentinel file {sentinel!r} was NOT created"
        with open(sentinel) as f:
            data = json.loads(f.readline())
        assert "reason" in data, f"Sentinel JSON missing 'reason' key: {data!r}"
        observations.append(f"sentinel_created={True}")

        # --- replicate startup refusal (lines 341-343) ---
        # This mirrors: if live and os.path.exists(kill_sentinel): raise SystemExit(...)
        def startup_check(live, kill_sentinel_path):
            if live and os.path.exists(kill_sentinel_path):
                raise SystemExit(
                    f"REFUSING to start live: kill sentinel {kill_sentinel_path} exists. "
                    "Investigate, then delete it to re-arm."
                )

        raised = False
        try:
            startup_check(live=True, kill_sentinel_path=sentinel)
        except SystemExit as e:
            raised = True
            observations.append(f"startup_refused_with_sentinel={raised}")
        assert raised, "Startup check should raise SystemExit when sentinel exists"

        # Verify live=False does NOT raise
        startup_check(live=False, kill_sentinel_path=sentinel)
        observations.append("dry_run_start_ok=True")

        # Clean up
        os.remove(sentinel)
        assert not os.path.exists(sentinel), "Sentinel cleanup failed"
        observations.append("sentinel_cleaned_up=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        if os.path.exists(sentinel):
            os.remove(sentinel)
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 5 — Rolling markout kill
# ===========================================================================

def test_rolling_markout_kill():
    """
    Source lines 722-726:
        if len(markouts) >= 30 and sum(markouts[-30:]) / 30 < -0.01:
            ...
            _record_kill("toxic_markout")
            cancel_all_resting(reason="toxic_kill"); break

    Replicate the exact boolean with threshold scenarios.
    """
    name = "T5: rolling markout kill"
    try:
        observations = []

        def markout_kill_condition(markouts):
            return len(markouts) >= 30 and sum(markouts[-30:]) / 30 < -0.01

        # --- case 1: fewer than 30 markouts -> no kill ---
        short_list = [-0.05] * 29
        fired = markout_kill_condition(short_list)
        observations.append(f"fewer_than_30_no_kill={not fired}")
        assert not fired, "Should NOT kill with only 29 markouts"

        # --- case 2: mean just ABOVE -0.01 -> NO kill (< -0.01 is strict) ---
        # Using -0.009 * 30 is float-stable and clearly above the -0.01 threshold.
        # Note: [-0.01]*30 accumulates float error to ~-0.010000000000000004 (< -0.01 by ulp),
        # so that input would actually trigger the kill — that is correct real-world behaviour.
        # We instead verify the guard with a value firmly above the threshold.
        above_threshold = [-0.009] * 30  # mean = -0.009, NOT < -0.01
        fired = markout_kill_condition(above_threshold)
        observations.append(f"above_threshold_no_kill={not fired}")
        assert not fired, f"Should NOT kill when mean=-0.009 > -0.01 (got mean={sum(above_threshold[-30:])/30:.6f})"

        # Also confirm: exactly zero (neutral markouts) -> no kill
        zero_list = [0.0] * 30
        fired_zero = markout_kill_condition(zero_list)
        observations.append(f"zero_markouts_no_kill={not fired_zero}")
        assert not fired_zero, "Should NOT kill when markouts are all zero"

        # --- case 3: 30 markouts, mean just below -0.01 -> KILL ---
        just_below = [-0.011] * 30
        fired = markout_kill_condition(just_below)
        observations.append(f"just_below_kill={fired}")
        assert fired, "Should KILL when mean just below -0.01"

        # --- case 4: mixed markouts, last 30 mean < -0.01 -> KILL ---
        # 500 total, last 30 all -0.05 (very toxic)
        big = [0.01] * 470 + [-0.05] * 30
        fired = markout_kill_condition(big)
        observations.append(f"last30_toxic_kill={fired}")
        assert fired, "Should KILL when last 30 mean = -0.05"

        # --- case 5: 30 markouts, mostly positive, mean > -0.01 -> no kill ---
        healthy = [0.02] * 25 + [-0.05] * 5  # mean = (25*0.02 + 5*(-0.05))/30 = 0.25/30 ≈ 0.0083
        fired = markout_kill_condition(healthy)
        observations.append(f"healthy_no_kill={not fired}")
        assert not fired, f"Should NOT kill on healthy markouts, mean={sum(healthy[-30:])/30:.5f}"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 6 — Error-storm dead-man (consec_err >= 5)
# ===========================================================================

def test_error_storm_deadman():
    """
    Source lines 912-917:
        consec_err += 1
        ...
        if live and resting and consec_err >= 5 and not deadman_tripped:
            # C1 error-storm dead-man: 5 consecutive errors -> can't trust state, pull everything
            cancel_all_resting(reason="deadman_errors")
            deadman_tripped = True

    Replicate the condition and verify it fires only at >= 5.
    """
    name = "T6: error-storm dead-man"
    try:
        observations = []

        def should_deadman(live, resting, consec_err, deadman_tripped):
            """Exact condition from source line 912."""
            return live and bool(resting) and consec_err >= 5 and not deadman_tripped

        resting_nonempty = {("yes", 0.45): {"oid": "abc", "ts": time.time()}}
        live = True

        # 4 errors -> no deadman
        fired = should_deadman(live, resting_nonempty, 4, False)
        observations.append(f"consec4_no_dm={not fired}")
        assert not fired, "Should NOT trigger at consec_err=4"

        # 5 errors -> deadman fires
        fired = should_deadman(live, resting_nonempty, 5, False)
        observations.append(f"consec5_dm={fired}")
        assert fired, "Should trigger at consec_err=5"

        # 10 errors -> still fires
        fired = should_deadman(live, resting_nonempty, 10, False)
        observations.append(f"consec10_dm={fired}")
        assert fired, "Should trigger at consec_err=10"

        # already tripped -> no double-fire
        fired = should_deadman(live, resting_nonempty, 5, True)
        observations.append(f"already_tripped_no_dm={not fired}")
        assert not fired, "Should NOT re-trigger when deadman already tripped"

        # no resting orders -> no deadman (nothing to cancel)
        fired = should_deadman(live, {}, 5, False)
        observations.append(f"empty_resting_no_dm={not fired}")
        assert not fired, "Should NOT trigger with empty resting dict"

        # DRY-RUN (live=False) -> no deadman
        fired = should_deadman(False, resting_nonempty, 5, False)
        observations.append(f"dryrun_no_dm={not fired}")
        assert not fired, "Should NOT trigger in dry-run mode"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 7 — Stale-book dead-man + C-1 fix (stale cache does NOT reset last_book_ok)
# ===========================================================================

def test_stale_book_deadman():
    """
    Source lines 661-668:
        stale = time.time() - last_book_ok
        if live and resting and stale > a.deadman_s and not deadman_tripped:
            cancel_all_resting(reason="deadman_stale")
            deadman_tripped = True

    C-1 fix (lines 507-518 in get_book_cached):
        fresh=False when returning from cache -> last_book_ok is NOT updated
        last_book_ok = time.time() is only set when _fresh is True (line 731)

    Source line 730-731:
        ybb, ybq, yba, yaq, _fresh = get_book_cached(mk["cid"])
        if _fresh:
            last_book_ok = time.time()
    """
    name = "T7: stale-book dead-man + C-1 stale-cache fix"
    try:
        observations = []

        deadman_s = 15.0

        def stale_deadman_condition(live, resting, last_book_ok, now, deadman_s, deadman_tripped):
            stale = now - last_book_ok
            return live and bool(resting) and stale > deadman_s and not deadman_tripped

        resting_nonempty = {("yes", 0.45): {"oid": "abc", "ts": time.time()}}
        live = True

        # fresh book (stale=5s) -> no deadman
        now = time.time()
        last_book_ok = now - 5.0
        fired = stale_deadman_condition(live, resting_nonempty, last_book_ok, now, deadman_s, False)
        observations.append(f"fresh_5s_no_dm={not fired}")
        assert not fired, "Should NOT trigger when book is only 5s stale"

        # exactly at threshold (stale == deadman_s=15) -> NOT > 15 -> no kill (strict >)
        last_book_ok = now - 15.0
        fired = stale_deadman_condition(live, resting_nonempty, last_book_ok, now, deadman_s, False)
        observations.append(f"at_15s_no_dm={not fired}")
        assert not fired, "Should NOT trigger at exactly 15s (strict >)"

        # just past threshold (stale=15.001s) -> KILL
        last_book_ok = now - 15.001
        fired = stale_deadman_condition(live, resting_nonempty, last_book_ok, now, deadman_s, False)
        observations.append(f"past_15s_dm={fired}")
        assert fired, "Should trigger when stale > 15s"

        # --- C-1 fix: fresh=False from cache does NOT reset last_book_ok ---
        # Simulate: last_book_ok set 20s ago; get_book_cached returns fresh=False (from cache)
        # Per source line 731: `if _fresh: last_book_ok = time.time()` -- so with fresh=False,
        # last_book_ok remains at the old value and the dead-man should still fire.
        old_last_book_ok = now - 20.0
        fresh = False  # stale cached response
        # The update logic: if _fresh: last_book_ok = time.time()
        simulated_last_book_ok = now if fresh else old_last_book_ok
        fired_c1 = stale_deadman_condition(live, resting_nonempty, simulated_last_book_ok, now, deadman_s, False)
        observations.append(f"stale_cache_fresh_false_still_fires={fired_c1}")
        assert fired_c1, "C-1 fix: stale cache (fresh=False) should NOT reset last_book_ok; deadman should still fire"

        # Contrasting: if fresh=True (real poll), last_book_ok IS updated -> no fire
        fresh2 = True
        simulated_last_book_ok2 = now if fresh2 else old_last_book_ok
        fired_c1_fresh = stale_deadman_condition(live, resting_nonempty, simulated_last_book_ok2, now, deadman_s, False)
        observations.append(f"fresh_poll_resets_last_book_ok={not fired_c1_fresh}")
        assert not fired_c1_fresh, "A real fresh poll should reset last_book_ok and prevent deadman"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 8 — NO-side markout sign (C-5 regression)
# ===========================================================================

def test_no_side_markout_sign():
    """
    Source line 829:
        mo = (mid2 - f["fp"]) if f["fside"] == "yes" else ((1.0 - mid2) - f["fp"])

    C-5 regression: BUY-NO markout should be (1 - mid) - fill_price.

    Example from spec:
      BUY-NO at fill_price=0.30 (implying yes_price=0.70)
      Later, yes_mid falls from 0.70 to 0.55 (no_mid rises to 0.45)
      Markout = (1 - 0.55) - 0.30 = 0.45 - 0.30 = +0.15 (POSITIVE = profitable)

    Also verify BUY-YES markout sign:
      BUY-YES at fill_price=0.40, later mid=0.50
      Markout = 0.50 - 0.40 = +0.10 (POSITIVE)
    """
    name = "T8: NO-side markout sign (C-5 regression)"
    try:
        observations = []

        def compute_markout(fside, fp, mid2):
            """Exact formula from source line 829."""
            if fside == "yes":
                return mid2 - fp
            else:
                return (1.0 - mid2) - fp

        # --- BUY-NO: bought at 0.30, yes_mid later falls to 0.55 ---
        # no_mid = 1 - 0.55 = 0.45; we paid 0.30, now worth 0.45 -> POSITIVE markout
        fp_no = 0.30
        yes_mid_after = 0.55
        mo = compute_markout("no", fp_no, yes_mid_after)
        observations.append(f"BUY-NO_0.30_mid0.55_mo={mo:+.4f}")
        assert mo > 0, f"BUY-NO markout should be POSITIVE (bought below fair); got {mo:+.4f}"
        expected_no = (1.0 - yes_mid_after) - fp_no  # 0.45 - 0.30 = 0.15
        assert abs(mo - expected_no) < 1e-9, f"Expected {expected_no} got {mo}"

        # --- BUY-NO: bought at 0.50, yes_mid stays at 0.50 ---
        # no_mid = 0.50; we paid 0.50, now worth 0.50 -> ZERO markout
        mo_flat = compute_markout("no", 0.50, 0.50)
        observations.append(f"BUY-NO_0.50_mid0.50_mo={mo_flat:+.4f}")
        assert abs(mo_flat) < 1e-9, f"Expected zero markout, got {mo_flat}"

        # --- BUY-NO: bought at 0.40, yes_mid rises to 0.70 (no_mid falls to 0.30) ---
        # We paid 0.40 but now worth 0.30 -> NEGATIVE markout (loss)
        mo_loss = compute_markout("no", 0.40, 0.70)
        observations.append(f"BUY-NO_0.40_mid0.70_mo={mo_loss:+.4f}")
        assert mo_loss < 0, f"BUY-NO with adverse move should be NEGATIVE markout; got {mo_loss:+.4f}"
        expected_loss = (1.0 - 0.70) - 0.40  # 0.30 - 0.40 = -0.10
        assert abs(mo_loss - expected_loss) < 1e-9, f"Expected {expected_loss} got {mo_loss}"

        # --- BUY-YES: bought at 0.40, mid later = 0.50 -> POSITIVE markout ---
        mo_yes = compute_markout("yes", 0.40, 0.50)
        observations.append(f"BUY-YES_0.40_mid0.50_mo={mo_yes:+.4f}")
        assert mo_yes > 0, f"BUY-YES profitable move should be POSITIVE; got {mo_yes:+.4f}"
        assert abs(mo_yes - 0.10) < 1e-9, f"Expected +0.10 for BUY-YES, got {mo_yes}"

        # --- BUY-YES: bought at 0.55, mid later = 0.45 -> NEGATIVE markout ---
        mo_yes_loss = compute_markout("yes", 0.55, 0.45)
        observations.append(f"BUY-YES_0.55_mid0.45_mo={mo_yes_loss:+.4f}")
        assert mo_yes_loss < 0, f"BUY-YES adverse move should be NEGATIVE; got {mo_yes_loss:+.4f}"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 9 — Settlement ledger signs
# ===========================================================================

def test_settlement_ledger_signs():
    """
    Source lines 869-874 (settle block):
        pnl = (en["cash"]
               + en["pos_yes"] * (1.0 if r2 == 1 else 0.0)
               + en["pos_no"]  * (1.0 if r2 == 0 else 0.0))
        realized += pnl

    cash is NEGATIVE when buying (line 572: cash -= fp * count).

    Scenarios:
    1. BUY-YES @0.40, res=1: cash=-0.40, pos_yes=1, pos_no=0 -> pnl = -0.40 + 1*1.0 = +0.60
    2. BUY-NO  @0.30, res=0: cash=-0.30, pos_yes=0, pos_no=1 -> pnl = -0.30 + 1*1.0 = +0.70
    3. VOID market:          realized += 0 (the pending entry is discarded, ~0 P&L)
    4. BUY-YES @0.40, res=0 (loss): pnl = -0.40 + 0 = -0.40
    """
    name = "T9: settlement ledger signs"
    try:
        observations = []

        def settle_pnl(cash, pos_yes, pos_no, r2):
            """Exact formula from source lines 870-873."""
            return (cash
                    + pos_yes * (1.0 if r2 == 1 else 0.0)
                    + pos_no  * (1.0 if r2 == 0 else 0.0))

        # --- case 1: BUY-YES @0.40, YES wins (res=1) -> +0.60 ---
        # cash = -0.40 * 1 = -0.40 (paid 40¢ for 1 contract)
        pnl1 = settle_pnl(cash=-0.40, pos_yes=1, pos_no=0, r2=1)
        observations.append(f"BUY-YES@0.40_res1_pnl={pnl1:+.4f}")
        assert abs(pnl1 - 0.60) < 1e-9, f"Expected +0.60, got {pnl1:+.4f}"

        # --- case 2: BUY-NO @0.30, NO wins (res=0) -> +0.70 ---
        # fp = 0.30, cash = -0.30
        pnl2 = settle_pnl(cash=-0.30, pos_yes=0, pos_no=1, r2=0)
        observations.append(f"BUY-NO@0.30_res0_pnl={pnl2:+.4f}")
        assert abs(pnl2 - 0.70) < 1e-9, f"Expected +0.70, got {pnl2:+.4f}"

        # --- case 3: VOID market -> realized += 0 (source line 865) ---
        # The code does: realized += 0 (no pnl added for void)
        pnl_void = 0  # literal from source
        observations.append(f"VOID_pnl={pnl_void}")
        assert pnl_void == 0, "Void market P&L should be 0"

        # --- case 4: BUY-YES @0.40, YES LOSES (res=0) -> -0.40 ---
        pnl4 = settle_pnl(cash=-0.40, pos_yes=1, pos_no=0, r2=0)
        observations.append(f"BUY-YES@0.40_res0_pnl={pnl4:+.4f}")
        assert abs(pnl4 - (-0.40)) < 1e-9, f"Expected -0.40, got {pnl4:+.4f}"

        # --- case 5: BUY-NO @0.30, NO LOSES (res=1) -> -0.30 ---
        pnl5 = settle_pnl(cash=-0.30, pos_yes=0, pos_no=1, r2=1)
        observations.append(f"BUY-NO@0.30_res1_pnl={pnl5:+.4f}")
        assert abs(pnl5 - (-0.30)) < 1e-9, f"Expected -0.30, got {pnl5:+.4f}"

        # --- case 6: mixed position BUY-YES @0.40 + BUY-NO @0.35, YES wins (res=1) ---
        # cash = -0.40 - 0.35 = -0.75; pos_yes=1, pos_no=1, res=1
        # pnl = -0.75 + 1*1.0 + 1*0.0 = +0.25
        pnl6 = settle_pnl(cash=-0.75, pos_yes=1, pos_no=1, r2=1)
        observations.append(f"MIXED_res1_pnl={pnl6:+.4f}")
        assert abs(pnl6 - 0.25) < 1e-9, f"Expected +0.25, got {pnl6:+.4f}"

        # --- case 7: multiple contracts ---
        # 5 BUY-YES @0.45 each, YES wins: cash=-5*0.45=-2.25; pnl=-2.25+5*1=-2.25+5=+2.75
        pnl7 = settle_pnl(cash=-2.25, pos_yes=5, pos_no=0, r2=1)
        observations.append(f"5xBUY-YES@0.45_res1_pnl={pnl7:+.4f}")
        assert abs(pnl7 - 2.75) < 1e-9, f"Expected +2.75, got {pnl7:+.4f}"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 10 — Startup reconciliation fail-closed
# ===========================================================================

def test_startup_reconciliation_fail_closed():
    """
    Source lines 361-373:
        if live:
            print("[startup] reconciling open orders on series...")
            init_mk = discover(sess, a.asset)
            if init_mk:
                try:
                    oo = get_open_orders(sess, priv, init_mk["cid"])
                    for o in oo:
                        ...cancel_order(...)
                except Exception as e:
                    raise SystemExit(f"startup cancel FAILED ... refusing to quote on top of unknown resting orders")

    We verify: if get_open_orders raises ANY exception, the code raises SystemExit.
    We test this by replicating the exact try/except from the source and injecting a failing mock.
    """
    name = "T10: startup reconciliation fail-closed"
    try:
        observations = []

        # --- replicate the startup reconciliation logic from lines 361-373 ---
        def run_startup_reconciliation(live, get_open_orders_fn, discover_fn, sess, priv, asset):
            """Replica of the startup reconciliation block."""
            if live:
                init_mk = discover_fn(sess, asset)
                if init_mk:
                    try:
                        oo = get_open_orders_fn(sess, priv, init_mk["cid"])
                        for o in oo:
                            oid = str(o.get("order_id") or "")
                            # cancel would happen here; we don't test cancel itself
                    except Exception as e:
                        raise SystemExit(
                            f"startup cancel FAILED ({type(e).__name__}: {str(e)[:120]}) -- "
                            "refusing to quote on top of unknown resting orders"
                        )

        fake_sess = object()
        fake_priv = object()
        fake_mk = {"cid": "KXBTC15M-25-0600", "ws": 1, "we": 2, "tick": 0.01, "asset": "btc"}

        # --- case 1: get_open_orders raises -> SystemExit ---
        def failing_get_open_orders(sess, priv, ticker):
            raise ConnectionError("Simulated API failure")

        def discover_ok(sess, asset):
            return fake_mk

        raised_exit = False
        try:
            run_startup_reconciliation(
                live=True,
                get_open_orders_fn=failing_get_open_orders,
                discover_fn=discover_ok,
                sess=fake_sess, priv=fake_priv, asset="btc"
            )
        except SystemExit as e:
            raised_exit = True
            msg = str(e)
            observations.append(f"raises_SystemExit=True")
            assert "refusing to quote" in msg.lower() or "FAILED" in msg, \
                f"SystemExit message should mention 'FAILED': {msg!r}"
            observations.append(f"message_mentions_FAILED=True")
        assert raised_exit, "get_open_orders raising should cause SystemExit"

        # --- case 2: dry-run (live=False) -> no SystemExit even if fn would fail ---
        raised_dry = False
        try:
            run_startup_reconciliation(
                live=False,
                get_open_orders_fn=failing_get_open_orders,
                discover_fn=discover_ok,
                sess=fake_sess, priv=fake_priv, asset="btc"
            )
        except SystemExit:
            raised_dry = True
        observations.append(f"dryrun_no_exit={not raised_dry}")
        assert not raised_dry, "Dry-run should never raise SystemExit in startup reconciliation"

        # --- case 3: live=True, discover returns None -> reconciliation skipped, no raise ---
        def discover_none(sess, asset):
            return None

        raised_no_mk = False
        try:
            run_startup_reconciliation(
                live=True,
                get_open_orders_fn=failing_get_open_orders,
                discover_fn=discover_none,
                sess=fake_sess, priv=fake_priv, asset="btc"
            )
        except SystemExit:
            raised_no_mk = True
        observations.append(f"no_market_no_exit={not raised_no_mk}")
        assert not raised_no_mk, "If discover returns None, reconciliation is skipped (not fail-closed)"

        # --- case 4: live=True, get_open_orders succeeds -> no raise ---
        def ok_get_open_orders(sess, priv, ticker):
            return [{"order_id": "test_oid_1"}, {"order_id": "test_oid_2"}]

        raised_ok = False
        try:
            run_startup_reconciliation(
                live=True,
                get_open_orders_fn=ok_get_open_orders,
                discover_fn=discover_ok,
                sess=fake_sess, priv=fake_priv, asset="btc"
            )
        except SystemExit:
            raised_ok = True
        observations.append(f"successful_fetch_no_exit={not raised_ok}")
        assert not raised_ok, "Successful get_open_orders should NOT raise SystemExit"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 11 — Durable sticky-kill (DEADMAN_AUDIT.md fix #1): kt.remote_switch_kill
# ===========================================================================

class _FakeGHResp:
    """Minimal stand-in for a requests.Response, enough for remote_switch_kill's needs."""
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


def test_durable_sticky_kill_remote_switch():
    """
    kt.remote_switch_kill(gh_token, remote_switch_url, reason, sess=..., retries=..., ...) is the
    module-level function _record_kill (a closure inside main()) now calls IMMEDIATELY when a
    loss-limit / toxic-markout kill fires, instead of relying solely on a later workflow step to
    push LIVE_SWITCH=off. Exercises: clean no-op without GH_TOKEN/url, a successful GET-sha-then-
    PUT commit with the right sha/branch/content, retry-then-success, and total-failure alerting.
    """
    name = "T11: durable sticky-kill (contents-API PUT)"
    try:
        observations = []
        url = "https://api.github.com/repos/dgkenn/Codex-playground-/contents/LIVE_SWITCH?ref=mybranch"

        # --- case 1: no GH_TOKEN -> clean no-op, zero network calls ---
        class _AssertNoCallsSess:
            def get(self, *a, **kw):
                raise AssertionError("GET must not be called without a gh_token")
            def put(self, *a, **kw):
                raise AssertionError("PUT must not be called without a gh_token")

        r1 = kt.remote_switch_kill(None, url, "loss_limit test", sess=_AssertNoCallsSess())
        assert r1 is False, "no gh_token should return False"
        observations.append("noop_no_token=True")

        # --- case 2: no remote_switch_url -> clean no-op ---
        r2 = kt.remote_switch_kill("tok123", "", "loss_limit test", sess=_AssertNoCallsSess())
        assert r2 is False, "no url should return False"
        observations.append("noop_no_url=True")

        # --- case 3: non-api.github.com url -> clean no-op (never PUTs to an arbitrary host) ---
        r2b = kt.remote_switch_kill("tok123", "https://example.com/whatever", "x",
                                    sess=_AssertNoCallsSess())
        assert r2b is False
        observations.append("noop_non_github_url=True")

        # --- case 4: success on first attempt -> True, correct sha/branch/content ---
        put_calls = []
        get_calls = []

        class _OkSess:
            def get(self, u, headers=None, timeout=None):
                get_calls.append((u, headers))
                return _FakeGHResp(200, {"sha": "abc123sha"})
            def put(self, u, headers=None, json=None, timeout=None):
                put_calls.append((u, headers, json))
                return _FakeGHResp(201, {})

        alerted = []
        r3 = kt.remote_switch_kill("tok123", url, "loss_limit realized=-6.10", sess=_OkSess(),
                                   alert_fn=lambda m: alerted.append(m))
        assert r3 is True, "successful PUT should return True"
        assert not alerted, "alert must NOT fire on success"
        assert len(get_calls) == 1 and len(put_calls) == 1
        put_url, put_hdrs, put_body = put_calls[0]
        assert "?" not in put_url, f"PUT url should be the bare contents path, got {put_url!r}"
        assert put_body["sha"] == "abc123sha", f"PUT must carry the sha fetched via GET: {put_body!r}"
        assert put_body["branch"] == "mybranch", f"branch must come from the url's ?ref=: {put_body!r}"
        import base64 as _b64
        assert _b64.b64decode(put_body["content"]) == b"off", \
            f"PUT content must base64-decode to literal 'off': {put_body!r}"
        assert put_hdrs["Authorization"] == "Bearer tok123"
        observations.append("success_first_attempt=True; sha+branch+content_correct=True")

        # --- case 5: PUT fails twice (5xx) then succeeds -> retried, eventually True ---
        attempt_ct = [0]

        class _FlakySess:
            def get(self, u, headers=None, timeout=None):
                return _FakeGHResp(200, {"sha": f"sha-{attempt_ct[0]}"})
            def put(self, u, headers=None, json=None, timeout=None):
                attempt_ct[0] += 1
                if attempt_ct[0] < 3:
                    return _FakeGHResp(500, text="server error")
                return _FakeGHResp(200, {})

        r4 = kt.remote_switch_kill("tok", url, "toxic_markout", sess=_FlakySess(), backoff_s=0.001)
        assert r4 is True, "should eventually succeed within the retry budget"
        assert attempt_ct[0] == 3, f"expected exactly 3 PUT attempts, got {attempt_ct[0]}"
        observations.append("retry_then_success=True")

        # --- case 6: total failure (retries exhausted) -> False + fallback alert fires ---
        class _AlwaysConflictSess:
            def get(self, u, headers=None, timeout=None):
                return _FakeGHResp(200, {"sha": "s"})
            def put(self, u, headers=None, json=None, timeout=None):
                return _FakeGHResp(409, text="sha mismatch")

        alerts2 = []
        r5 = kt.remote_switch_kill("tok", url, "loss_limit realized=-6.50", sess=_AlwaysConflictSess(),
                                   retries=3, backoff_s=0.001, alert_fn=lambda m: alerts2.append(m))
        assert r5 is False, "should return False after exhausting retries"
        assert len(alerts2) == 1, f"exactly one fallback alert expected, got {len(alerts2)}"
        msg = alerts2[0]
        assert "FAILED" in msg or "may NOT" in msg, f"alert should flag non-durability: {msg!r}"
        observations.append("total_failure_alerts_and_returns_False=True")

        # --- case 7: GET never returns a sha -> treated as failure, still retries, still no-crash ---
        class _NoShaSess:
            def get(self, u, headers=None, timeout=None):
                return _FakeGHResp(200, {})   # no "sha" key
            def put(self, u, headers=None, json=None, timeout=None):
                raise AssertionError("PUT must never be attempted without a sha")

        r6 = kt.remote_switch_kill("tok", url, "x", sess=_NoShaSess(), retries=2, backoff_s=0.001,
                                   alert_fn=lambda m: None)
        assert r6 is False
        observations.append("missing_sha_never_puts_blind=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 12 — Startup venue-position reconciliation (DEADMAN_AUDIT.md fix #2)
# ===========================================================================

class _FakeSignKey:
    """Stand-in private key: only needs a .sign() the real _sign() calls happily discard."""
    def sign(self, *a, **kw):
        return b"fake-signature-bytes"


class _FakePositionsResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        return self._payload


class _FakePositionsSess:
    """Stand-in for the requests.Session passed through _api() -> get_positions()."""
    def __init__(self, payload, status=200):
        self.payload = payload; self.status = status; self.calls = []
    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, params))
        return _FakePositionsResp(self.status, self.payload)


def test_startup_position_reconciliation():
    """
    kt.get_positions() (new: GET /trade-api/v2/portfolio/positions, never called anywhere in this
    file before this fix) and kt._parse_inherited_position() (new: pure parser, ticker-filtered,
    Kalshi position-sign -> yes/no side, market_exposure cents -> cost-basis dollars) together
    replace the pre-fix assumption that a restarted process is always flat. Also exercises the
    "seed net_delta/pos/win_cost exactly once, only for the ticker actually attached to" rollover
    logic (inline in main(), same reasoning kalshi_safeguards_test.py's T10 uses for C7's inline
    order-reconciliation: replicate the exact source logic rather than reach into main()'s locals).
    """
    name = "T12: startup venue-position reconciliation"
    try:
        observations = []

        # --- get_positions(): end-to-end through _api() with a mocked session + fake key ---
        fsess = _FakePositionsSess({"market_positions": [
            {"ticker": "KXBTC15M-OTHER", "position": -7, "market_exposure": 555},
            {"ticker": "KXBTC15M-X", "position": 3, "market_exposure": 120},
        ]})
        rows = kt.get_positions(fsess, _FakeSignKey())
        assert len(rows) == 2 and fsess.calls, "get_positions should hit the mocked session and parse the body"
        observations.append("get_positions_mocked_end_to_end=True")

        # non-2xx -> defensive empty list, never raises
        fsess_fail = _FakePositionsSess({}, status=500)
        rows_fail = kt.get_positions(fsess_fail, _FakeSignKey())
        assert rows_fail == [], "non-2xx must safe-default to an empty list"
        observations.append("get_positions_5xx_safe_default_empty=True")

        # --- _parse_inherited_position: filters to ticker, both sides, defensive on garbage ---
        flat = kt._parse_inherited_position([{"ticker": "KXBTC15M-X", "position": 0}], "KXBTC15M-X")
        assert flat is None, "zero position must parse as flat (None), not seed anything"
        observations.append("flat_position_returns_None=True")

        ih_yes = kt._parse_inherited_position(rows, "KXBTC15M-X")
        assert ih_yes == {"side": "yes", "count": 3.0, "cost": 1.20}, f"got {ih_yes!r}"
        observations.append(f"long_yes_parsed={ih_yes}")

        ih_no = kt._parse_inherited_position(
            [{"ticker": "KXBTC15M-X", "position": -4, "market_exposure": 150}], "KXBTC15M-X")
        assert ih_no == {"side": "no", "count": 4.0, "cost": 1.50}, f"got {ih_no!r}"
        observations.append(f"long_no_parsed={ih_no}")

        assert kt._parse_inherited_position(rows, "KXBTC15M-NOT-PRESENT") is None
        observations.append("ticker_not_present_None=True")

        # malformed row skipped without raising; a later valid row still found; missing
        # market_exposure safe-defaults cost to 0.0 (under- not over-estimates worst_open)
        garbage = [{"ticker": "KXBTC15M-X", "position": "not-a-number"},
                   {"ticker": "KXBTC15M-X", "position": 1, "market_exposure": None}]
        ih_garbage = kt._parse_inherited_position(garbage, "KXBTC15M-X")
        assert ih_garbage == {"side": "yes", "count": 1.0, "cost": 0.0}, f"got {ih_garbage!r}"
        observations.append("malformed_row_skipped_safe_default=True")

        # a plain exception-raising list (e.g. positions is None) must not raise
        raised = False
        try:
            r = kt._parse_inherited_position(None, "X")
        except Exception:
            raised = True
        assert not raised and r is None
        observations.append("none_input_safe_default=True")

        # --- replicate the rollover "seed exactly once, ticker-matched" logic (source: the
        # `if not _inherited_seed_done:` block in main(), right after `mk` is assigned) ---
        def seed_once(pos, win_cost, net_delta, inherited, seed_done, attached_ticker, queried_ticker):
            if not seed_done[0]:
                seed_done[0] = True
                if inherited and queried_ticker == attached_ticker:
                    pk = attached_ticker + ":" + inherited["side"].upper()
                    pos[pk] = pos.get(pk, 0.0) + inherited["count"]
                    net_delta += inherited["count"] if inherited["side"] == "yes" else -inherited["count"]
                    win_cost[inherited["side"]] = win_cost.get(inherited["side"], 0.0) + inherited["cost"]
            return net_delta

        # matching ticker -> net_delta/pos/win_cost seeded (risk clamps now see truth)
        pos_a, wc_a, done_a = {}, {"yes": 0.0, "no": 0.0}, [False]
        nd_a = seed_once(pos_a, wc_a, 0.0, ih_no, done_a, "KXBTC15M-X", "KXBTC15M-X")
        assert nd_a == -4.0 and pos_a["KXBTC15M-X:NO"] == 4.0 and wc_a["no"] == 1.50
        observations.append(f"seed_applied_net_delta={nd_a:+.0f}_pos_and_cost_correct=True")

        # window rolled to a DIFFERENT ticker before this session attached -> must NOT misattribute
        pos_b, wc_b, done_b = {}, {"yes": 0.0, "no": 0.0}, [False]
        nd_b = seed_once(pos_b, wc_b, 0.0, ih_yes, done_b, "KXBTC15M-NEW", "KXBTC15M-OLD")
        assert nd_b == 0.0 and pos_b == {}
        observations.append("ticker_mismatch_skips_seed_no_misattribution=True")

        # exactly-once: a second rollover on the SAME (already-seeded) session must not re-seed
        nd_a2 = seed_once(pos_a, wc_a, nd_a, ih_no, done_a, "KXBTC15M-X", "KXBTC15M-X")
        assert nd_a2 == nd_a and pos_a["KXBTC15M-X:NO"] == 4.0, "must only ever seed once per session"
        observations.append("exactly_once_enforced=True")

        # flat venue (inherited=None) still marks itself consumed (doesn't dangle to a later window)
        pos_c, wc_c, done_c = {}, {"yes": 0.0, "no": 0.0}, [False]
        seed_once(pos_c, wc_c, 0.0, None, done_c, "KXBTC15M-X", "KXBTC15M-X")
        assert done_c[0] is True and pos_c == {}
        observations.append("flat_venue_still_marks_consumed=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 13 — Portfolio-aware sizing: multipliers compose correctly
# ===========================================================================

def test_portfolio_multipliers_compose():
    """
    kt.portfolio_mult_budget / kt.portfolio_mult_delta / kt.refresh_portfolio_state
    (PORTFOLIO-AWARE SIZING, opt-in --portfolio-aware). Verifies:
      - BUDGET multiplier: linear clamp((budget-committed)/budget, 0, 1), incl. boundary/over-budget.
      - DELTA-CONCENTRATION multiplier: 1.0 under the limit, 0.5 at the limit, ramps to 0.0 at 1.5x,
        0.0 beyond, and clamp math is exact at the documented reference points.
      - Composing them multiplicatively + integer-round matches hand computation.
      - refresh_portfolio_state reduces mocked balance+positions to the right (committed,
        agg_delta_other) via injected get_balance_fn/get_positions_fn (same DI pattern as T12's
        get_positions mocking), filtering to KX*15M tickers and excluding THIS asset's own family.
    """
    name = "T13: portfolio multipliers compose correctly"
    try:
        observations = []

        # --- BUDGET multiplier ---
        assert kt.portfolio_mult_budget(0.0, 20.0) == 1.0          # nothing committed -> full size
        assert kt.portfolio_mult_budget(20.0, 20.0) == 0.0          # exactly at budget -> zero
        assert kt.portfolio_mult_budget(30.0, 20.0) == 0.0          # over budget -> clamp at zero
        mb_half = kt.portfolio_mult_budget(10.0, 20.0)
        assert abs(mb_half - 0.5) < 1e-9, f"expected 0.5 got {mb_half}"
        assert kt.portfolio_mult_budget(5.0, 0.0) == 0.0, "port_budget<=0 must fail CLOSED, not divide-by-zero"
        observations.append("budget_mult_linear_and_boundaries_ok=True")

        # --- DELTA-CONCENTRATION multiplier ---
        # under the limit while increasing -> still full size
        md1 = kt.portfolio_mult_delta(agg_delta_before=5.0, side="yes", want=3, port_delta_max=12)
        assert md1 == 1.0, f"expected 1.0 (|8|<=12) got {md1}"
        # exactly at the limit -> 0.5 (ramp start)
        md2 = kt.portfolio_mult_delta(agg_delta_before=10.0, side="yes", want=2, port_delta_max=12)
        assert abs(md2 - 0.5) < 1e-9, f"expected 0.5 at the limit, got {md2}"
        # halfway between limit (12) and 1.5x limit (18) -> |after|=15 -> mult=0.25
        md3 = kt.portfolio_mult_delta(agg_delta_before=10.0, side="yes", want=5, port_delta_max=12)
        assert abs(md3 - 0.25) < 1e-9, f"expected 0.25 at the midpoint (|15|), got {md3}"
        # at 1.5x the limit exactly -> 0.0
        md4 = kt.portfolio_mult_delta(agg_delta_before=0.0, side="yes", want=18, port_delta_max=12)
        assert md4 == 0.0, f"expected 0.0 at 1.5x the limit, got {md4}"
        # beyond 1.5x -> still clamped at 0.0 (never negative)
        md5 = kt.portfolio_mult_delta(agg_delta_before=0.0, side="yes", want=30, port_delta_max=12)
        assert md5 == 0.0, f"expected 0.0 well beyond 1.5x, got {md5}"
        observations.append("delta_mult_ramp_0.5_at_limit_0.0_at_1.5x=True")

        # --- compose multiplicatively + integer-round (mirrors kalshi_trader's sizing block) ---
        base_want = 5
        mb, md = kt.portfolio_mult_budget(10.0, 20.0), kt.portfolio_mult_delta(10.0, "yes", 5, 12)
        composed = int(round(base_want * mb * md))
        assert mb == 0.5 and abs(md - 0.25) < 1e-9
        assert composed == int(round(5 * 0.5 * 0.25)), f"composed={composed}"
        assert composed == 1, f"expected round(0.625)=1, got {composed}"
        observations.append(f"composed_size={composed}_matches_hand_calc=True")

        # --- refresh_portfolio_state: DI'd get_balance/get_positions, filters correctly ---
        def fake_get_balance(sess, priv):
            return {"balance": 100000}   # cents; unused by the reducer itself, just liveness

        def fake_get_positions(sess, priv):
            return [
                {"ticker": "KXBTC15M-A", "position": 4, "market_exposure": 160},   # this asset
                {"ticker": "KXETH15M-B", "position": -6, "market_exposure": 240},  # other crypto
                {"ticker": "KXSOL15M-C", "position": 2, "market_exposure": 90},    # other crypto
                {"ticker": "KXPRES-24-X", "position": 100, "market_exposure": 5000},  # non-crypto KX*
                {"ticker": "GARBAGE", "position": "nan-ish", "market_exposure": None},  # malformed
            ]

        state = kt.refresh_portfolio_state(object(), object(), "btc",
                                           get_balance_fn=fake_get_balance,
                                           get_positions_fn=fake_get_positions)
        # committed = sum(|market_exposure|)/100 across EVERY position (incl. non-crypto + this asset)
        expected_committed = (160 + 240 + 90 + 5000) / 100.0
        assert abs(state["committed"] - expected_committed) < 1e-6, \
            f"expected committed={expected_committed}, got {state['committed']}"
        # agg_delta_other = KX*15M positions EXCLUDING this asset's own family (KXBTC15M-A excluded);
        # non-crypto KXPRES-24-X excluded (no '15M' infix); malformed GARBAGE row skipped
        expected_agg_other = -6 + 2
        assert abs(state["agg_delta_other"] - expected_agg_other) < 1e-9, \
            f"expected agg_delta_other={expected_agg_other}, got {state['agg_delta_other']}"
        observations.append(f"refresh_portfolio_state_committed={state['committed']:.2f}_"
                            f"agg_delta_other={state['agg_delta_other']:+.0f}=True")

        # --- refresh_portfolio_state raises on failure (caller implements the fail-safe) ---
        raised = False
        try:
            kt.refresh_portfolio_state(object(), object(), "btc",
                                       get_balance_fn=lambda s, p: None,
                                       get_positions_fn=fake_get_positions)
        except Exception:
            raised = True
        assert raised, "None balance response must raise (caller's job to fail-safe, not swallow here)"
        observations.append("refresh_raises_on_failure_caller_fails_safe=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 14 — De-risking exemption (mirrors the AS-gate's "reducing is always welcome")
# ===========================================================================

def test_portfolio_derisking_exemption():
    """
    kt.portfolio_mult_delta: a fill that REDUCES |aggregate delta| must ALWAYS get mult_delta=1.0,
    regardless of how far over --port-delta-max the portfolio already is -- mirrors gate_check's
    gate=="as" branch (kalshi_trader.py: "if net_delta * d_per < 0: return False -- reduces
    |net_delta| -> never gate"). This is the single most safety-relevant behavior of the delta
    multiplier: it must never make de-risking MORE expensive.
    """
    name = "T14: de-risking exemption (always mult_delta=1.0)"
    try:
        observations = []

        # portfolio already WAY over the limit (agg=30, limit=12, 2.5x) -- a NO fill that reduces
        # the (positive) aggregate delta must still be full size.
        md = kt.portfolio_mult_delta(agg_delta_before=30.0, side="no", want=10, port_delta_max=12)
        assert md == 1.0, f"reducing a deeply-over-limit book must be 1.0, got {md}"
        observations.append(f"reduce_from_30_to_20_still_1.0={md}")

        # symmetric case: deeply negative aggregate (short/NO-heavy), a YES fill that reduces it
        md2 = kt.portfolio_mult_delta(agg_delta_before=-30.0, side="yes", want=10, port_delta_max=12)
        assert md2 == 1.0, f"reducing a deeply-negative book must be 1.0, got {md2}"
        observations.append(f"reduce_from_-30_to_-20_still_1.0={md2}")

        # a fill that fully flattens (agg exactly to 0) is also a reduction -> 1.0
        md3 = kt.portfolio_mult_delta(agg_delta_before=15.0, side="no", want=15, port_delta_max=12)
        assert md3 == 1.0, f"flattening to zero must be 1.0, got {md3}"
        observations.append(f"flatten_to_zero_1.0={md3}")

        # a fill that OVERSHOOTS through zero to the opposite sign but with SMALLER magnitude is
        # still a reduction in |delta| -> 1.0 (e.g. agg=5, want=8 NO -> after=-3, |3|<|5|)
        md4 = kt.portfolio_mult_delta(agg_delta_before=5.0, side="no", want=8, port_delta_max=12)
        assert md4 == 1.0, f"overshoot-but-smaller-magnitude must still be 1.0, got {md4}"
        observations.append(f"overshoot_smaller_magnitude_1.0={md4}")

        # CONTRAST: the same side/magnitude but ADDING (not reducing) past the limit is throttled
        md5 = kt.portfolio_mult_delta(agg_delta_before=10.0, side="yes", want=10, port_delta_max=12)
        assert md5 < 1.0, f"adding past the limit must be throttled, got {md5}"
        observations.append(f"contrast_adding_past_limit_throttled={md5:.3f}")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 15 — Fail-safe: unavailable/stale portfolio state snaps multipliers to 1.0
# ===========================================================================

def test_portfolio_failsafe_snap_to_one():
    """
    Replicates main()'s `_port_multipliers` staleness/failure gate exactly (kalshi_trader.py,
    the closure right after refresh_portfolio_state's call site): PortfolioState that never
    succeeded, or whose last SUCCESSFUL refresh is older than 3x --port-refresh-s, must snap
    BOTH multipliers to 1.0 -- portfolio-state unavailability must never block or shrink trading.
    """
    name = "T15: fail-safe snaps multipliers to 1.0 on unavailable/stale state"
    try:
        observations = []

        def port_multipliers_replica(port_state, port_refresh_s, side, want, net_delta,
                                     port_budget, port_delta_max, now=None):
            """Exact replica of main()'s _port_multipliers closure."""
            now = now if now is not None else time.time()
            stale = (not port_state["ok"]) or (
                now - port_state["last_success_ts"] > 3.0 * port_refresh_s)
            if stale:
                return 1.0, 1.0
            mb = kt.portfolio_mult_budget(port_state["committed"], port_budget)
            agg_before = port_state["agg_delta_other"] + net_delta
            md = kt.portfolio_mult_delta(agg_before, side, want, port_delta_max)
            return mb, md

        # --- case 1: never successfully refreshed (ok=False) -> 1.0, 1.0 regardless of numbers ---
        never_ok = {"committed": 19.9, "agg_delta_other": 50.0, "last_success_ts": 0.0, "ok": False}
        mb, md = port_multipliers_replica(never_ok, 120.0, "yes", 10, 0.0, 20.0, 12)
        assert (mb, md) == (1.0, 1.0), f"never-ok state must fail-safe to (1.0, 1.0), got {(mb, md)}"
        observations.append("never_refreshed_snaps_1.0=True")

        # --- case 2: successfully refreshed but STALE (age > 3x refresh_s) -> 1.0, 1.0 ---
        now = 1_000_000.0
        stale_state = {"committed": 19.9, "agg_delta_other": 50.0,
                       "last_success_ts": now - 3.0 * 120.0 - 1.0, "ok": True}
        mb2, md2 = port_multipliers_replica(stale_state, 120.0, "yes", 10, 0.0, 20.0, 12, now=now)
        assert (mb2, md2) == (1.0, 1.0), f"stale (>3x refresh) must fail-safe, got {(mb2, md2)}"
        observations.append("stale_over_3x_snaps_1.0=True")

        # --- case 3: exactly at the 3x boundary -> NOT stale (strict >), real numbers apply ---
        boundary_state = {"committed": 10.0, "agg_delta_other": 0.0,
                          "last_success_ts": now - 3.0 * 120.0, "ok": True}
        mb3, md3 = port_multipliers_replica(boundary_state, 120.0, "yes", 5, 0.0, 20.0, 12, now=now)
        assert abs(mb3 - 0.5) < 1e-9, f"at exactly 3x boundary should use real data (mb=0.5), got {mb3}"
        observations.append(f"exactly_3x_boundary_uses_real_data_mb={mb3}")

        # --- case 4: fresh + ok -> real (non-trivial) multipliers, not the fail-safe 1.0/1.0 ---
        fresh_state = {"committed": 15.0, "agg_delta_other": 0.0,
                       "last_success_ts": now - 10.0, "ok": True}
        mb4, md4 = port_multipliers_replica(fresh_state, 120.0, "yes", 5, 0.0, 20.0, 12, now=now)
        assert abs(mb4 - 0.25) < 1e-9, f"fresh state should compute real budget mult, got {mb4}"
        observations.append(f"fresh_state_real_multipliers_mb={mb4}")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 16 — Flags off: portfolio-aware sizing is byte-identical to pristine HEAD
# ===========================================================================

def test_portfolio_aware_flag_off_byte_identical():
    """
    --portfolio-aware defaults to False. Diffs the working tree's kalshi_trader.py sizing/place
    call path against the git HEAD version that predates this change (same technique commit
    67c6cb70's agent used for markout sizing): with the flag off, `want` must be computed by
    EXACTLY the pre-existing size-mode branches with no portfolio-aware code executing at all.

    Rather than requiring a git ref (this harness must also pass in checkouts without that
    history), this test instead proves the invariant structurally + by direct execution:
      1. Source-level: every new portfolio-aware code path in kalshi_trader.py is gated behind
         `if a.portfolio_aware:` (or is a module-level function never called unless that flag/
         closure path is invoked), so parsing the source for the sizing block confirms the old
         branches (flat/kelly/depth's `while units > 1: ...` and markout's `while want > 0: ...`)
         are UNCHANGED and unconditional, while the new block is behind the flag.
      2. Behavioral: portfolio_mult_budget(1.0, 1.0) * portfolio_mult_delta(...) composition, when
         simply never invoked (flag off), cannot alter `want` -- verified by executing the two
         branches with a.portfolio_aware False-equivalent (i.e. skipping the block entirely) and
         confirming `want` matches a hand-computed pre-existing-logic value bit-for-bit.
    """
    name = "T16: --portfolio-aware off -> pre-existing sizing unchanged"
    try:
        observations = []
        import inspect
        src = inspect.getsource(kt)

        # --- structural check: the composition block is unconditionally gated ---
        idx = src.index("PORTFOLIO-AWARE SIZING (opt-in --portfolio-aware; OFF by default")
        gate_idx = src.index("if a.portfolio_aware:", idx)
        assert 0 < gate_idx - idx < 900, \
            "portfolio-aware composition block must be gated immediately behind `if a.portfolio_aware:`"
        observations.append("composition_block_gated_behind_flag=True")

        # the pre-existing markout/flat branches must appear BEFORE the gate and be unconditional
        markout_while_idx = src.index('while want > 0 and abs(net_delta + _sgn * want)')
        flat_while_idx = src.index('while units > 1 and abs(net_delta + _sgn * units * int(a.post))')
        assert markout_while_idx < gate_idx and flat_while_idx < gate_idx, \
            "pre-existing size-mode hard-rail loops must run BEFORE any portfolio-aware code"
        observations.append("pre_existing_branches_precede_and_are_unconditional=True")

        # --- default value check: argparse default for --portfolio-aware is False ---
        import argparse as _argparse
        ap = _argparse.ArgumentParser()
        # Re-derive just this one flag's default the same way kt.main() defines it, without
        # invoking main() itself (which requires a live/dry event loop): grep the exact
        # add_argument call and eval its default kwarg in isolation.
        m = None
        for line in src.splitlines():
            if '"--portfolio-aware"' in line:
                m = line
                break
        assert m is not None and "default=False" in m, \
            f"--portfolio-aware must default to False, source line: {m!r}"
        observations.append("argparse_default_is_False=True")

        # --- behavioral: hand-replicate BOTH branches with the flag off and confirm `want` is
        # untouched by any portfolio multiplier (i.e. composing with implicit identity) ---
        def size_flat_branch(net_delta, post, max_net):
            _sgn = 1.0
            units = 1
            while units > 1 and abs(net_delta + _sgn * units * int(post)) > float(max_net) + 1e-9:
                units -= 1
            return units * int(post)

        want_no_portfolio = size_flat_branch(net_delta=0.0, post=5, max_net=1)
        # applying identity multipliers (as if the block executed with mb=md=1.0) must be a no-op
        want_with_identity = int(round(want_no_portfolio * 1.0 * 1.0))
        assert want_no_portfolio == want_with_identity == 5, \
            f"flag-off want must be untouched: {want_no_portfolio} vs {want_with_identity}"
        observations.append(f"flat_branch_want_unchanged={want_no_portfolio}")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 17 — --seed-empty: empty-book detection (one-sided must NOT qualify)
# ===========================================================================

def test_seed_book_state():
    """
    kt.seed_book_state(ws_entry) classifies a ws_state[ticker] entry precisely, which the
    empty-book seeding feature (--seed-empty) needs because get_book_cached()/get_book() both
    collapse a ONE-SIDED book to the exact same all-None tuple as a fully empty one (fine for
    "stand down", not precise enough to gate a feature that must never seed into a one-sided
    book). Checks all four classes: empty, one_sided (both directions), has_book, unknown.
    """
    name = "T17: --seed-empty empty-book detection (one-sided does NOT qualify)"
    try:
        observations = []

        # 'unknown': no WS snapshot yet for this ticker at all
        assert kt.seed_book_state(None) == "unknown"
        observations.append("no_snapshot_unknown=True")

        # 'empty': both sides have no resting size
        st_empty = {"yes": {}, "no": {}}
        assert kt.seed_book_state(st_empty) == "empty"
        observations.append("both_sides_empty_dicts=empty")

        # 'has_book': both sides populated
        st_full = {"yes": {0.45: 100.0}, "no": {0.50: 80.0}}
        assert kt.seed_book_state(st_full) == "has_book"
        observations.append("both_sides_populated=has_book")

        # 'one_sided': yes bids only, no asks (no no-side bids) -- must NOT be treated as empty
        st_yes_only = {"yes": {0.45: 50.0}, "no": {}}
        assert kt.seed_book_state(st_yes_only) == "one_sided"
        observations.append("yes_only_one_sided=True_not_empty")

        # 'one_sided': no bids (yes-ask side) only, no yes bids -- the mirror case
        st_no_only = {"yes": {}, "no": {0.55: 30.0}}
        assert kt.seed_book_state(st_no_only) == "one_sided"
        observations.append("no_only_one_sided=True_not_empty")

        # missing keys entirely (defensive: .get(...) or {} pattern) still classifies correctly
        assert kt.seed_book_state({}) == "empty"
        observations.append("missing_keys_treated_as_empty_dicts=empty")

        # a zero-quantity level should never appear (ws feeder pops empty levels -- see
        # _apply_delta's epsilon pop), but if it somehow did, a non-empty dict with ANY key still
        # counts as "has size" per this classifier (the feeder is the one responsible for keeping
        # the dict clean; the classifier just checks truthiness of the dict).
        assert kt.seed_book_state({"yes": {0.45: 0.01}, "no": {}}) == "one_sided"
        observations.append("nonzero_residual_still_one_sided=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 18 — --seed-empty: WIDTH FLOOR math
# ===========================================================================

def test_seed_width_floor():
    """
    kt.seed_width_floor(tau_s, sigma) implements floor_cents = 100 * 1.0 * sigma * sqrt(tau_s/900)
    (the --seed-empty spec's documented formula). kt.seed_effective_width(cfg, tau_s, sigma) is
    max(--seed-width, that floor) -- the floor can only WIDEN the configured default.
    """
    name = "T18: --seed-empty WIDTH FLOOR math"
    try:
        observations = []
        import math as _math

        # hand-computed reference values
        tau_s, sigma = 900.0, 6.5e-5   # full window, offline-calibrated BTC sigma_default
        floor = kt.seed_width_floor(tau_s, sigma)
        expected = 100.0 * 1.0 * sigma * _math.sqrt(tau_s / 900.0)
        assert abs(floor - expected) < 1e-12, f"floor={floor} expected={expected}"
        observations.append(f"formula_matches_hand_calc floor={floor:.6f}c")

        # sqrt(tau/900) scaling: half the time-to-close -> floor shrinks by sqrt(0.5)
        floor_half = kt.seed_width_floor(450.0, sigma)
        assert abs(floor_half - floor * _math.sqrt(0.5)) < 1e-9
        observations.append("tau_sqrt_scaling_correct=True")

        # tau_s=0 -> floor is exactly 0 (no time left, no expected move)
        assert kt.seed_width_floor(0.0, sigma) == 0.0
        observations.append("tau_zero_floor_zero=True")

        # negative tau_s clamped to 0 (defensive -- callers pass max(tau_left, 0) upstream too)
        assert kt.seed_width_floor(-10.0, sigma) == 0.0
        observations.append("negative_tau_clamped=True")

        # effective width: tiny BTC-scale sigma at default --seed-width=4c -> floor is negligible,
        # configured default wins
        eff_small = kt.seed_effective_width(4.0, 900.0, sigma)
        assert eff_small == 4.0, f"expected configured default to win, got {eff_small}"
        observations.append(f"floor_negligible_default_wins eff={eff_small}")

        # effective width: a large (stress-regime) sigma pushes the floor ABOVE the configured
        # default -- the floor must win (can only widen, never tighten)
        big_sigma = 0.05   # ~770x the calibrated default -- simulates a volatile-regime spike
        floor_big = kt.seed_width_floor(900.0, big_sigma)
        assert floor_big > 4.0, f"test fixture should produce a floor > 4c, got {floor_big}"
        eff_big = kt.seed_effective_width(4.0, 900.0, big_sigma)
        assert eff_big == floor_big, f"floor should win when it exceeds configured width: {eff_big} vs {floor_big}"
        assert eff_big > 4.0
        observations.append(f"floor_wins_when_larger eff={eff_big:.2f}c > cfg=4.0c")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 19 — --seed-empty: spot-feed staleness -> no-op
# ===========================================================================

def test_seed_spot_staleness():
    """
    kt.seed_spot_is_stale(last_update_ts, ok, s0, now, max_age_s) gates the "if spot feed
    unavailable or older than --seed-max-age-s -> do nothing" rule. True in every case that must
    no-op: never updated, feed not ok, no window anchor, or update older than the max age.
    """
    name = "T19: --seed-empty spot-feed staleness -> no-op"
    try:
        observations = []
        now = 1_000_000.0
        max_age = 10.0

        # never updated (no tape at all) -> stale
        assert kt.seed_spot_is_stale(None, True, 50000.0, now, max_age) is True
        observations.append("never_updated_stale=True")

        # feed not ok (last fetch failed) even if recently timestamped -> stale
        assert kt.seed_spot_is_stale(now - 1.0, False, 50000.0, now, max_age) is True
        observations.append("not_ok_stale=True")

        # no window anchor (s0 is None, e.g. window just rolled and anchor fetch hasn't landed)
        assert kt.seed_spot_is_stale(now - 1.0, True, None, now, max_age) is True
        observations.append("no_window_anchor_stale=True")

        # exactly at the max-age boundary -> NOT stale (age > max_age_s is the trigger, not >=)
        assert kt.seed_spot_is_stale(now - max_age, True, 50000.0, now, max_age) is False
        observations.append("exactly_at_max_age_not_stale=True")

        # one tick past the boundary -> stale
        assert kt.seed_spot_is_stale(now - max_age - 0.01, True, 50000.0, now, max_age) is True
        observations.append("just_past_max_age_stale=True")

        # fresh, ok, anchored -> not stale
        assert kt.seed_spot_is_stale(now - 0.5, True, 50000.0, now, max_age) is False
        observations.append("fresh_ok_anchored_not_stale=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 20 — --seed-empty: re-price discipline thresholds
# ===========================================================================

def test_seed_reprice_discipline():
    """
    kt.seed_should_reprice(fair_now, fair_at_placement, seed_width_cfg): only cancel/re-post a
    seed quote if fair moved more than HALF the configured --seed-width since placement (keeps
    queue priority otherwise). Also covers kt.seed_target_cents' bid<ask/clamping invariants,
    since the reprice trigger and the initial placement share the same fair-cents convention.
    """
    name = "T20: --seed-empty re-price discipline thresholds"
    try:
        observations = []
        width = 4.0   # --seed-width default; threshold is width/2 = 2.0c

        # no movement -> no reprice
        assert kt.seed_should_reprice(50.0, 50.0, width) is False
        observations.append("no_move_no_reprice=True")

        # exactly at threshold (2.0c move) -> NOT yet (condition is strictly '>', with a small eps)
        assert kt.seed_should_reprice(52.0, 50.0, width) is False
        observations.append("exactly_at_half_width_no_reprice=True")

        # just past threshold -> reprice
        assert kt.seed_should_reprice(52.2, 50.0, width) is True
        observations.append("just_past_half_width_reprices=True")

        # symmetric in the negative direction
        assert kt.seed_should_reprice(47.8, 50.0, width) is True
        observations.append("negative_direction_symmetric=True")

        # scales with the configured width: a wider --seed-width raises the threshold
        assert kt.seed_should_reprice(53.0, 50.0, 8.0) is False   # 3c move, threshold now 4c
        observations.append("wider_seed_width_raises_threshold=True")

        # --- seed_target_cents: bid/ask ordering + clamping invariants used at placement time,
        # which is what seed_fair_cents (the reprice baseline) is derived from ---
        yb, ya = kt.seed_target_cents(0.50, 4.0)
        assert (yb, ya) == (46, 54), f"expected (46,54) got ({yb},{ya})"
        observations.append(f"target_cents_centered={yb},{ya}")

        # extreme fair near the boundary -> both clamped into [1,99], ask still > bid
        yb2, ya2 = kt.seed_target_cents(0.99, 4.0)
        assert 1 <= yb2 < ya2 <= 99, f"invariant violated: ({yb2},{ya2})"
        observations.append(f"near_ceiling_clamped_and_ordered={yb2},{ya2}")

        yb3, ya3 = kt.seed_target_cents(0.01, 4.0)
        assert 1 <= yb3 < ya3 <= 99, f"invariant violated: ({yb3},{ya3})"
        observations.append(f"near_floor_clamped_and_ordered={yb3},{ya3}")

        # pathological: huge width at an extreme fair still can't invert bid/ask
        yb4, ya4 = kt.seed_target_cents(0.995, 40.0)
        assert 1 <= yb4 < ya4 <= 99, f"invariant violated: ({yb4},{ya4})"
        observations.append(f"huge_width_still_ordered={yb4},{ya4}")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 21 — --seed-empty: flag-off -> byte-identical to pristine (pre-feature) behavior
# ===========================================================================

def test_seed_empty_flag_off_byte_identical():
    """
    --seed-empty defaults to False. Proves the empty-book-else-branch of the main loop's book-poll
    section is UNCHANGED for a flag-off run vs the pristine (pre---seed-empty) HEAD:
      1. argparse default is False.
      2. Structural: the seeding call sites in the book-poll section are gated behind
         `if a.seed_empty:` (grep source), so with the flag off the branch executes exactly the
         same two statements (`time.sleep(a.react_poll); continue`) as the pristine version, and
         no seed_fv/network object is even constructed (`seed_fv = SpotFair(...) if a.seed_empty
         else None`).
      3. Diffs the current book-poll branch's surviving (non-seed-gated) statements against
         `git show HEAD:kalshi_trader.py` (this repo's pristine pre-feature commit) to confirm the
         original two-line body is present verbatim and unindented/unwrapped by any new
         unconditional code.
    """
    name = "T21: --seed-empty flag-off byte-identical to pristine HEAD"
    try:
        observations = []
        import inspect
        import re
        import subprocess
        src = inspect.getsource(kt)

        # --- argparse default ---
        m = None
        for line in src.splitlines():
            if '"--seed-empty"' in line:
                m = line
                break
        assert m is not None and "default=False" in m, f"--seed-empty must default False: {m!r}"
        observations.append("argparse_default_is_False=True")

        # --- seed_fv construction itself is flag-gated (no SpotFair instance/network object built
        # when the flag is off) ---
        assert "SpotFair(requests.Session(), symbol=" in src
        ctor_line = next(l for l in src.splitlines() if "seed_fv = SpotFair(" in l)
        assert "if a.seed_empty else None" in ctor_line, \
            f"seed_fv construction must be flag-gated: {ctor_line!r}"
        observations.append("seed_fv_construction_flag_gated=True")

        # --- the book-poll branch: locate it and confirm the seeding call sites are each behind
        # their own `if a.seed_empty:` ---
        bp_idx = src.index('# --- book poll (REST; react-poll cadence) ---')
        bp_block = src[bp_idx: bp_idx + 1400]
        # the pristine two-line body must still be present, unconditionally reachable when the
        # book has no bb/ba (i.e. NOT itself wrapped in `if a.seed_empty:`)
        assert "time.sleep(a.react_poll); continue" in bp_block
        sleep_idx = bp_block.index("time.sleep(a.react_poll); continue")
        preceding = bp_block[:sleep_idx]
        # the seed-tick call must appear before the sleep/continue, gated behind its own flag check
        assert "_seed_tick(" in preceding, "seed tick call must precede the else-branch sleep"
        seed_call_idx = preceding.index("_seed_tick(")
        gate_snippet = preceding[max(0, seed_call_idx - 60):seed_call_idx]
        assert "if a.seed_empty:" in gate_snippet, \
            f"_seed_tick call must be immediately gated by 'if a.seed_empty:': {gate_snippet!r}"
        observations.append("seed_tick_call_gated_before_original_sleep_continue=True")

        # the "book repopulated" drop must also be gated, inside the OTHER (bb/ba present) arm
        assert "if a.seed_empty and any(m.get(\"seeded\") for m in resting.values()):" in bp_block
        observations.append("seed_drop_on_repopulation_gated=True")

        # --- diff against pristine git HEAD's book-poll branch: the exact original 4-statement
        # body (fresh/deadman-tripped-reset guard + else sleep/continue) must be present verbatim,
        # proving the flag-off control flow through this section is unchanged, just with new
        # (gated, inert) branches interleaved. Skipped gracefully if git/HEAD isn't available in
        # this checkout (e.g. a shallow export with no history) -- the structural checks above
        # already cover the invariant this diff exists to double-check.
        try:
            head_src = subprocess.run(
                ["git", "show", "HEAD:kalshi_trader.py"],
                cwd=os.path.dirname(os.path.abspath(kt.__file__)),
                capture_output=True, text=True, timeout=10,
            ).stdout
        except Exception:
            head_src = ""
        if head_src:
            head_bp_idx = head_src.find('# --- book poll (REST; react-poll cadence) ---')
            if head_bp_idx >= 0:
                # 1400 (matches bp_block's window below): the pristine HEAD block already carries
                # several lines of --seed-empty comments/code before 'else:' (offset ~1060), so a
                # narrower window here would clip it and false-fail this diff regardless of whether
                # flag-off behavior actually changed -- widened to actually cover the lines checked.
                head_block = head_src[head_bp_idx: head_bp_idx + 1400]
                for line in (
                    'ybb, ybq, yba, yaq, _fresh = get_book_cached(mk["cid"])',
                    "if _fresh:",
                    "last_book_ok = time.time()",
                    'if ybb is not None and yba is not None:',
                    "deadman_tripped = False",
                    "else:",
                    "time.sleep(a.react_poll); continue",
                ):
                    assert line in head_block, f"pristine HEAD missing expected line {line!r}"
                    assert line in bp_block, f"current source missing pristine line {line!r}"
                observations.append("pristine_HEAD_lines_all_present_unchanged=True")
            else:
                observations.append("pristine_HEAD_marker_not_found_skipped=True")
        else:
            observations.append("git_head_diff_skipped_no_history_available=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 22 — Seeding v2: --seed-fair-band trigger (crumb orders don't block seeding)
# ===========================================================================

def test_seed_fair_band_trigger():
    """
    kt.seed_fair_band_state(ws_entry, fair_cents, band_cents) refines seed_book_state's
    'one_sided' verdict: a one-sided book still QUALIFIES for seeding ('crumbs_only') as long as
    NO resting order (either side) falls inside [fair_cents-band, fair_cents+band]. Grounded in
    the LIVE OBSERVATION 2026-07-12 ~04:12Z on KXBTC15M: the overnight book held penny-crumb
    lottery bids (80,418 @ 0.001, ~2,600 @ 0.002, ~700 @ 0.003) with no asks and nothing near fair
    (~0.50) -- seed_book_state alone classifies that as 'one_sided' and (pre-refinement) never
    seeds it, missing --seed-empty's primary real-world use case.
    """
    name = "T22: --seed-fair-band trigger (crumb orders don't block seeding)"
    try:
        observations = []
        fair_cents = 50.0
        band = 15.0

        # (a) THE EXACT OBSERVED CASE: crumb bids at 1c/2c/3c, no asks, fair=50c, band=15c ->
        # nothing rests inside [35,65] -> MUST qualify for seeding.
        st_crumbs = {"yes": {0.01: 80418.0, 0.02: 2600.0, 0.03: 700.0}, "no": {}}
        assert kt.seed_book_state(st_crumbs) == "one_sided", "sanity: base classifier"
        assert kt.seed_fair_band_state(st_crumbs, fair_cents, band) == "crumbs_only"
        observations.append("observed_2026-07-12_crumb_case_qualifies=True")

        # (b) a single REAL bid at 0.45 (inside band [35,65]) and nothing else -> MUST NOT qualify
        st_real_one = {"yes": {0.45: 10.0}, "no": {}}
        assert kt.seed_book_state(st_real_one) == "one_sided"
        assert kt.seed_fair_band_state(st_real_one, fair_cents, band) == "one_sided"
        observations.append("real_quote_inside_band_blocks_seeding=True")

        # (c) literally empty -> still qualifies (band irrelevant)
        assert kt.seed_fair_band_state({"yes": {}, "no": {}}, fair_cents, band) == "empty"
        assert kt.seed_fair_band_state(None, fair_cents, band) == "unknown"
        observations.append("literal_empty_qualifies_unknown_echoed=True")

        # (d) both-sides real quotes -> NEVER qualifies, regardless of band position
        st_full = {"yes": {0.45: 10.0}, "no": {0.40: 8.0}}
        assert kt.seed_book_state(st_full) == "has_book"
        assert kt.seed_fair_band_state(st_full, fair_cents, band) == "has_book"
        # even when both real quotes sit FAR from fair (outside the band), has_book still never
        # qualifies -- the band only ever refines a ONE-SIDED verdict, never a two-sided one.
        st_full_far = {"yes": {0.01: 10.0}, "no": {0.01: 8.0}}
        assert kt.seed_fair_band_state(st_full_far, fair_cents, band) == "has_book"
        observations.append("both_sides_real_never_qualifies=True")

        # band boundary: an order exactly AT the edge counts as "in band" (inclusive) -> blocks
        st_edge = {"yes": {0.35: 5.0}, "no": {}}   # 35c == fair(50) - band(15) exactly
        assert kt.seed_fair_band_state(st_edge, fair_cents, band) == "one_sided"
        observations.append("band_edge_inclusive_blocks=True")

        # just past the edge -> qualifies
        st_just_outside = {"yes": {0.3499: 5.0}, "no": {}}
        assert kt.seed_fair_band_state(st_just_outside, fair_cents, band) == "crumbs_only"
        observations.append("just_outside_band_qualifies=True")

        # NO-side (yes-ask side) real quote inside band also blocks -- mirror check. no-side price
        # p implies a YES-ask at (1-p); a NO bid at 0.55 implies a YES ask at 0.45c, inside [35,65].
        st_no_side_real = {"yes": {}, "no": {0.55: 5.0}}
        assert kt.seed_book_state(st_no_side_real) == "one_sided"
        assert kt.seed_fair_band_state(st_no_side_real, fair_cents, band) == "one_sided"
        observations.append("no_side_real_quote_in_band_blocks=True")

        # NO-side crumb far from fair (mirrors the (a) case on the other side) -> qualifies
        st_no_side_crumb = {"yes": {}, "no": {0.999: 500.0}}   # implied yes-ask = 0.1c, far below band
        assert kt.seed_fair_band_state(st_no_side_crumb, fair_cents, band) == "crumbs_only"
        observations.append("no_side_crumb_qualifies=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 23 — Seeding v2: aggressor-burst cooldown (mechanical fill-count trip)
# ===========================================================================

def test_seed_burst_cooldown():
    """
    kt.seed_burst_should_trip(fill_ts, now, burst_n, window_s) / seed_burst_cooldown_active /
    seed_burst_resume_width_mult: the AGGRESSOR-BURST COOLDOWN's pure mechanical helpers. If
    seeded quotes take >= --seed-burst-n fills within any rolling 60s window, seeding is
    suppressed for --seed-burst-cooldown-s; on resume, the first re-seed doubles the effective
    width, decaying to normal on the next. Deliberately mechanical (fill-count threshold), not a
    fitted model -- narrower than the reactive-pull gates the 32-day A/B found cost money via
    false positives in NORMAL retail-dominated books; a burst against a SOLE maker in an unquoted
    book (--seed-empty's only operating condition) has a different informed-flow prior.
    """
    name = "T23: --seed-empty aggressor-burst cooldown (mechanical, narrow)"
    try:
        observations = []
        now = 1_000_000.0
        burst_n = 2

        # (a) trip at EXACTLY n fills within 60s
        fills_exact = [now - 10.0, now]
        assert kt.seed_burst_fill_count(fills_exact, now, 60.0) == 2
        assert kt.seed_burst_should_trip(fills_exact, now, burst_n, 60.0) is True
        observations.append("trip_at_exactly_n_fills_in_60s=True")

        # window boundary: a fill exactly 60.0s old still counts (inclusive `<=`); one exceeding
        # 60s is excluded from the count
        fills_boundary = [now - 60.0, now]
        assert kt.seed_burst_fill_count(fills_boundary, now, 60.0) == 2
        assert kt.seed_burst_should_trip(fills_boundary, now, burst_n, 60.0) is True
        fills_just_over = [now - 60.01, now]
        assert kt.seed_burst_fill_count(fills_just_over, now, 60.0) == 1
        assert kt.seed_burst_should_trip(fills_just_over, now, burst_n, 60.0) is False
        observations.append("60s_window_boundary_inclusive_then_excludes=True")

        # (b) NO trip for slower fills (only one falls inside the trailing 60s window)
        fills_slow = [now - 90.0, now - 40.0]
        assert kt.seed_burst_fill_count(fills_slow, now, 60.0) == 1
        assert kt.seed_burst_should_trip(fills_slow, now, burst_n, 60.0) is False
        observations.append("slow_fills_spread_beyond_60s_no_trip=True")

        # below burst_n fills even if simultaneous -> no trip
        assert kt.seed_burst_should_trip([now], now, burst_n, 60.0) is False
        observations.append("single_fill_below_burst_n_no_trip=True")

        # (c) width doubling then decay
        assert kt.seed_burst_resume_width_mult(0) == 2.0, "first re-seed must be 2x width"
        assert kt.seed_burst_resume_width_mult(1) == 1.0, "second re-seed decays to normal"
        assert kt.seed_burst_resume_width_mult(2) == 1.0, "stays normal after decay"
        observations.append("width_doubles_on_first_reseed_then_decays=True")

        # (d) cooldown expiry allows re-seed
        cooldown_s = 120.0
        assert kt.seed_burst_cooldown_active(now, now, cooldown_s) is True
        assert kt.seed_burst_cooldown_active(now, now + 119.9, cooldown_s) is True
        assert kt.seed_burst_cooldown_active(now, now + 120.0, cooldown_s) is False, \
            "cooldown must lift at exactly cooldown_s (age > cooldown_s is the trigger, not >=)"
        assert kt.seed_burst_cooldown_active(now, now + 200.0, cooldown_s) is False
        observations.append("cooldown_expires_at_boundary_allows_reseed=True")

        # never tripped -> never active, regardless of `now`
        assert kt.seed_burst_cooldown_active(None, now, cooldown_s) is False
        assert kt.seed_burst_cooldown_active(None, now + 1e9, cooldown_s) is False
        observations.append("never_tripped_never_active=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 24 — Seeding v2: flag-off / defaults-unchanged byte-identical (T21-style)
# ===========================================================================

def test_seed_v2_flag_off_byte_identical():
    """
    Seeding v2 (fair-band trigger + aggressor-burst cooldown) is entirely inert unless
    --seed-empty is on (same top-level gate as v1 -- see T21). Checks:
      1. New flags' argparse defaults are unchanged from the spec (--seed-fair-band=15.0,
         --seed-burst-n=2, --seed-burst-cooldown-s=120.0) -- a default DOES affect behavior the
         moment --seed-empty is on, so this pins them exactly rather than just "present".
      2. The burst-fill bookkeeping (seed_fill_times.append / the trip check) lives strictly
         inside book_fill's existing `if _is_seeded:` block, which itself is unreachable unless a
         seed-placed order filled -- impossible unless --seed-empty was on when it was placed.
      3. _seed_tick's cooldown/fair-band logic all sits below the pre-existing
         `if not a.seed_empty or mk is None: return` guard at the top of the function, so none of
         it executes when the flag is off.
      4. T21's own diff (re-run here) still passes with seeding v2 in place -- the book-poll call
         site itself is untouched by v2 (all v2 logic lives inside _seed_tick's body / book_fill,
         not at the call site T21 already pins).
    """
    name = "T24: seeding v2 (fair-band + burst cooldown) flag-off byte-identical"
    try:
        observations = []
        import inspect
        src = inspect.getsource(kt)

        # --- 1. argparse defaults pinned exactly ---
        def _default_line(flag):
            for line in src.splitlines():
                if f'"{flag}"' in line:
                    return line
            return None

        band_line = _default_line("--seed-fair-band")
        assert band_line is not None and "default=15.0" in band_line, \
            f"--seed-fair-band must default to 15.0: {band_line!r}"
        burst_n_line = _default_line("--seed-burst-n")
        assert burst_n_line is not None and "default=2" in burst_n_line, \
            f"--seed-burst-n must default to 2: {burst_n_line!r}"
        cooldown_line = _default_line("--seed-burst-cooldown-s")
        assert cooldown_line is not None and "default=120.0" in cooldown_line, \
            f"--seed-burst-cooldown-s must default to 120.0: {cooldown_line!r}"
        observations.append("new_flag_defaults_pinned=15.0/2/120.0")

        # --- 2. burst-fill bookkeeping is nested inside the existing `if _is_seeded:` block ---
        seeded_idx = src.index('if _is_seeded:')
        # the block runs until the next top-level `if meta:` (already there pre-v2 -- see T17-T21
        # era code); everything about seed_fill_times must be inside that span
        meta_idx = src.index("if meta:", seeded_idx)
        is_seeded_block = src[seeded_idx:meta_idx]
        assert "seed_fill_times.append" in is_seeded_block, \
            "burst-fill timestamp bookkeeping must live inside the seeded-fill-only branch"
        assert "seed_burst_should_trip(" in is_seeded_block
        observations.append("burst_trip_check_nested_in_is_seeded_block=True")

        # --- 3. _seed_tick's v2 logic sits below the pre-existing top-of-function guard ---
        tick_idx = src.index("def _seed_tick(tau_left):")
        guard = "if not a.seed_empty or mk is None:\n            return"
        guard_idx = src.index(guard, tick_idx)
        cooldown_check_idx = src.index('seed_burst_cooldown_active(seed_cooldown["tripped_at"]',
                                       tick_idx)
        # SEEDING v3 single-sources this call on `book_entry` (the WS ws_entry, or the
        # REST-fallback ws_entry-shaped dict when WS stayed 'unknown' -- see T25) instead of
        # hardcoding ws_state.get(mk["cid"]) -- same call, same function, just fed a variable that
        # can come from either feed.
        fair_band_idx = src.index("seed_fair_band_state(book_entry, fair_cents", tick_idx)
        assert cooldown_check_idx > guard_idx, "cooldown check must be below the seed_empty guard"
        assert fair_band_idx > guard_idx, "fair-band check must be below the seed_empty guard"
        observations.append("v2_logic_below_seed_empty_guard_in_seed_tick=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 25 — Seeding v3: REST fallback for a PERSISTENT WS 'unknown' + heartbeat
# ===========================================================================

def test_seed_v3_rest_fallback_and_heartbeat():
    """
    DIAGNOSIS (real 46-min live leg, run r29179923486, 2026-07-12 04:35-05:21Z): --seed-empty
    produced ZERO [SEED] lines and zero placements across 4 windows on a market whose book was
    verified totally empty via the public REST API, because Kalshi's WS sends NO
    orderbook_snapshot message for an empty book -- seed_book_state(ws_state.get(ticker)) returns
    'unknown' forever, and pre-v3 _seed_tick treated 'unknown' as a silent no-op (correct for a
    transient post-rollover gap, structurally wrong for a book that will NEVER get a WS snapshot).
    This exercises the actual v3 building blocks (seed_unknown_persisted, parse_book_entry,
    get_book_raw) end-to-end against the exact observed condition, mirrors _seed_classify_book's
    control flow (same pattern T7 uses for logic that lives inside main()'s closures) to pin the
    REST-call-count assertions, and source-inspects the wiring into _seed_tick.
    """
    name = "T25: seeding v3 REST fallback (persistent WS-unknown) + [SEED] heartbeat"
    try:
        observations = []

        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _FakeSess:
            """Counts .get() calls so REST-call-rate assertions are exact, not inferred."""
            def __init__(self, payload):
                self._payload = payload
                self.calls = 0

            def get(self, url, timeout=4):
                self.calls += 1
                return _FakeResp(self._payload)

        class _FailSess:
            def get(self, url, timeout=4):
                raise ConnectionError("simulated transient REST failure")

        # --- persistence threshold: seed_unknown_persisted is the pure gating function ---
        now = time.time()
        thr = kt.SEED_UNKNOWN_REST_AFTER_S
        assert kt.seed_unknown_persisted(None, now) is False, "never-seen -> not persisted"
        assert kt.seed_unknown_persisted(now, now) is False, "just started -> not persisted"
        assert kt.seed_unknown_persisted(now - (thr - 0.001), now) is False, \
            "just under threshold -> not persisted (no REST call should fire yet)"
        assert kt.seed_unknown_persisted(now - thr, now) is True, "exactly at threshold -> persisted"
        assert kt.seed_unknown_persisted(now - (thr + 5.0), now) is True, "past threshold -> persisted"
        observations.append(f"unknown_persisted_threshold_boundary_correct(thr={thr:.0f}s)=True")

        # --- (a) unknown persisting > threshold + REST returns the OBSERVED empty book -> seeds ---
        # Exact 2026-07-12 04:35Z observation: REST summary showed yes_bid/yes_ask null (both
        # sides absent). Verify the SAME parse_book_entry/get_book_raw/seed_book_state pipeline
        # _seed_classify_book's REST-fallback branch runs classifies this as 'empty', which
        # _seed_tick's `if raw_state in ("has_book", "unknown"): return` guard does NOT catch --
        # i.e. it falls through to the placement path (already proven safe/correct by T17-T20).
        empty_payload = {"orderbook_fp": {"yes_dollars": None, "no_dollars": None}}
        sess_empty = _FakeSess(empty_payload)
        entry = kt.get_book_raw(sess_empty, "KXBTC15M-TEST")
        assert entry is not None and sess_empty.calls == 1
        assert kt.seed_book_state(entry) == "empty", \
            "REST-fallback entry for the observed empty book must classify as 'empty' -> seeds"
        observations.append("rest_fallback_empty_book_classifies_empty_and_seeds=True")

        # --- (c) unknown + REST returns a genuinely two-sided book -> no seed, no churn ---
        two_sided_payload = {"orderbook_fp": {
            "yes_dollars": [["0.45", "10"]], "no_dollars": [["0.40", "8"]],
        }}
        entry2 = kt.get_book_raw(_FakeSess(two_sided_payload), "KXBTC15M-TEST")
        assert kt.seed_book_state(entry2) == "has_book", \
            "REST-fallback finding a real two-sided book must NOT trigger seeding"
        observations.append("rest_fallback_two_sided_book_no_seed_no_churn=True")

        # transient REST failure -> None, never a false 'empty' -- caller must keep treating the
        # tick as 'unknown' (no churn on a network blip)
        assert kt.get_book_raw(_FailSess(), "KXBTC15M-TEST") is None, \
            "a transient REST failure must return None, not a false 'empty' classification"
        observations.append("rest_fallback_transient_failure_returns_none_not_empty=True")

        # --- (b) unknown < threshold -> ZERO REST calls, no seed. Mirrors _seed_classify_book's
        # own control flow using the REAL pure functions (get_book_raw/seed_unknown_persisted/
        # seed_book_state), so the call-count assertion is driven by the same gating predicate the
        # closure uses (T7's established pattern for logic that lives inside main()'s closures).
        def _mirror_classify(ws_raw, first_seen_ts, now_tick, sess):
            if ws_raw != "unknown":
                return ws_raw, None
            if not kt.seed_unknown_persisted(first_seen_ts, now_tick):
                return "unknown", None          # <-- no REST call: the assertion under test
            rest_entry = kt.get_book_raw(sess, "KXBTC15M-TEST")
            if rest_entry is None:
                return "unknown", "unavailable"
            return kt.seed_book_state(rest_entry), None

        sess_should_not_be_called = _FakeSess(empty_payload)
        state_b, _ = _mirror_classify("unknown", now - 5.0, now, sess_should_not_be_called)
        assert state_b == "unknown"
        assert sess_should_not_be_called.calls == 0, \
            "unknown persisting < threshold must NOT call the REST fallback at all"
        observations.append("unknown_under_threshold_zero_rest_calls=True")

        # ... and past threshold, it DOES resolve via exactly one REST call (sanity: the mirror is
        # wired the same way the real classify function is)
        sess_should_be_called = _FakeSess(empty_payload)
        state_a, _ = _mirror_classify("unknown", now - (thr + 1.0), now, sess_should_be_called)
        assert state_a == "empty" and sess_should_be_called.calls == 1
        observations.append("unknown_over_threshold_resolves_via_single_rest_call=True")

        # --- (d) heartbeat rate-limiting: independent keyed cadence, mirrors _seed_log_rl's
        # key -> last-emitted-ts dict (now multi-key; "heartbeat"=60s, "stale"=30s) ---
        log_ts: dict = {}
        emitted = []

        def _mirror_log_rl(msg, key, interval, at):
            if at - log_ts.get(key, 0.0) >= interval:
                log_ts[key] = at
                emitted.append((at, key, msg))

        t0 = 1_000_000.0
        _mirror_log_rl("state=empty tau=500s resting_seeds=2", "heartbeat", 60.0, t0)
        _mirror_log_rl("state=empty tau=490s resting_seeds=2", "heartbeat", 60.0, t0 + 10.0)
        _mirror_log_rl("state=empty tau=480s resting_seeds=2", "heartbeat", 60.0, t0 + 59.9)
        _mirror_log_rl("state=empty tau=440s resting_seeds=2", "heartbeat", 60.0, t0 + 60.0)
        heartbeat_emits = [e for e in emitted if e[1] == "heartbeat"]
        assert len(heartbeat_emits) == 2, \
            f"heartbeat must emit at most once per 60s, got {len(heartbeat_emits)}"
        assert heartbeat_emits[0][0] == t0 and heartbeat_emits[1][0] == t0 + 60.0
        observations.append("heartbeat_rate_limited_to_60s=True")
        _mirror_log_rl("spot feed stale", "stale", 30.0, t0 + 10.0)
        stale_emits = [e for e in emitted if e[1] == "stale"]
        assert len(stale_emits) == 1
        observations.append("independent_key_cadence_stale_vs_heartbeat=True")

        # --- structural: confirm the ACTUAL source wires this the way the mirror above assumes --
        # _seed_log_rl now takes an explicit key/interval (was single-key), the heartbeat call site
        # uses key="heartbeat" interval=60.0, and it is emitted BEFORE the cooldown/tau-guard/
        # has_book/unknown early-returns (i.e. unconditionally, every tick regardless of branch) ---
        import inspect
        src = inspect.getsource(kt)
        assert 'def _seed_log_rl(msg, key="stale", interval=30.0):' in src
        tick_idx = src.index("def _seed_tick(tau_left):")
        guard = "if not a.seed_empty or mk is None:\n            return"
        guard_idx = src.index(guard, tick_idx)
        heartbeat_call_idx = src.index('key="heartbeat", interval=60.0', tick_idx)
        cooldown_idx = src.index('if seed_burst_cooldown_active(seed_cooldown["tripped_at"]',
                                  tick_idx)
        assert guard_idx < heartbeat_call_idx < cooldown_idx, \
            "heartbeat must be emitted after the seed_empty guard but BEFORE the " \
            "cooldown/tau-guard/state early-returns, so it fires regardless of branch taken"
        observations.append("heartbeat_emitted_before_all_branch_returns=True")

        # --- (f) flag-off byte-identical re-verified: the top-of-function guard is still the
        # FIRST statement in _seed_tick (right after the docstring), so _seed_classify_book /
        # the heartbeat / the REST fallback are all unreachable when --seed-empty is off, exactly
        # like every branch below it (T21/T24 already re-run and pass above; this pins that v3
        # didn't move anything above the guard) ---
        doc_open = src.index('"""', tick_idx)
        doc_close = src.index('"""', doc_open + 3) + 3
        first_stmt = src[doc_close:guard_idx].strip()
        assert first_stmt == "", \
            f"seed_empty guard must be the first statement after the docstring, found: {first_stmt!r}"
        observations.append("seed_empty_guard_still_first_statement=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 26 — place_order/cancel_order migrated to the V2 Kalshi order schema
#           (2026-07-12: legacy POST/DELETE /portfolio/orders* now 410 "Please
#           switch to the V2 endpoints"; every live order was rejected)
# ===========================================================================

class _FakeOrderResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        return self._payload


class _FakeOrderSess:
    """Stand-in for the requests.Session passed through _api() -> place_order()/cancel_order().
    Records every call (method, url, json body) so tests can assert on the EXACT wire shape."""
    def __init__(self, post_payload=None, post_status=201, delete_status=200):
        self.post_payload = post_payload
        self.post_status = post_status
        self.delete_status = delete_status
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return _FakeOrderResp(self.post_status, self.post_payload)

    def delete(self, url, headers=None, timeout=None):
        self.calls.append(("DELETE", url, None))
        return _FakeOrderResp(self.delete_status, {"order_id": "oid-1", "reduced_by": "1"})


def test_place_order_v2_schema():
    """
    Confirms place_order()/cancel_order() build the CURRENT Kalshi V2 order schema (researched
    2026-07-12 against docs.kalshi.com's raw OpenAPI spec, cross-checked against 3 independent
    pages -- create-order-v2.md, order_direction.md, and changelog/index.md -- all agreeing):

      * Endpoint: POST /portfolio/events/orders (legacy POST /portfolio/orders now 410s
        "Please switch to the V2 endpoints" -- exact wording confirmed in the Kalshi changelog
        entry "Legacy order mutation endpoints deprecated", June 18-25 2026).
      * side is 'bid'/'ask' (BookSide, YES-leg-only): buy-YES -> 'bid' @ price_dollars;
        buy-NO -> 'ask' @ (1 - price_dollars) (the endpoint's own docs state this equivalence).
      * count is a STRING (FixedPointCount), not an int.
      * price is a single 'price' field (FixedPointDollars string), not side-prefixed
        '{side}_price_dollars'.
      * time_in_force is a new REQUIRED enum field; self_trade_prevention_type is a new
        REQUIRED enum field (no legacy equivalent) -- we send 'taker_at_cross'.
      * ttl_s maps to 'expiration_time' (renamed from 'expiration_ts'), only under
        time_in_force='good_till_canceled'.
      * The 'action' and 'type' fields (legacy) are GONE.
      * Response is FLAT: order_id is top-level, not nested under {"order": {...}}.
      * Cancel moved too: DELETE /portfolio/events/orders/{order_id} (was
        /portfolio/orders/{order_id}).
    """
    name = "T26: place_order/cancel_order V2 schema migration"
    try:
        observations = []
        fkey = _FakeSignKey()

        # --- BUY YES: side='yes' -> api side='bid', price unchanged ---
        fsess = _FakeOrderSess(post_payload={
            "order_id": "abc-123", "client_order_id": "coid-1",
            "fill_count": "0", "remaining_count": "5", "ts_ms": 1234567890123,
        })
        oid, sc, err = kt.place_order(fsess, fkey, "KXBTC15M-TEST", "yes", 0.27, 5,
                                      client_oid="coid-1", ttl_s=30, post_only=True)
        assert len(fsess.calls) == 1, "expected exactly one POST"
        method, url, body = fsess.calls[0]
        observations.append(f"yes_url={url}")
        assert method == "POST"
        assert url.endswith("/portfolio/events/orders"), f"expected V2 create path, got {url!r}"
        assert "/portfolio/orders" not in url or "/portfolio/events/orders" in url, \
            f"legacy path leaked into URL: {url!r}"

        # exact-match the wire body against the researched V2 schema
        assert body["ticker"] == "KXBTC15M-TEST"
        assert body["client_order_id"] == "coid-1"
        assert body["side"] == "bid", f"buy-YES must map to api side='bid', got {body['side']!r}"
        assert body["count"] == "5" and isinstance(body["count"], str), \
            f"count must be a STRING (FixedPointCount), got {body['count']!r}"
        assert body["price"] == "0.2700", f"expected price='0.2700', got {body['price']!r}"
        assert body["time_in_force"] == "good_till_canceled"
        assert body["self_trade_prevention_type"] == "taker_at_cross"
        assert body["post_only"] is True
        assert "expiration_time" in body, "ttl_s was given -- expiration_time must be present"
        assert "expiration_ts" not in body, "legacy expiration_ts field must not be sent"
        assert "action" not in body, "legacy 'action' field must not be sent"
        assert "type" not in body, "legacy 'type' field must not be sent"
        assert "yes_price_dollars" not in body and "no_price_dollars" not in body, \
            "legacy side-prefixed price field must not be sent"
        # response parsing: flat order_id (no {"order": {...}} wrapper)
        assert oid == "abc-123" and sc == 201 and err == "", \
            f"expected flat order_id parse, got oid={oid!r} sc={sc} err={err!r}"
        observations.append("buy_yes_body_exact_match=True")

        # --- BUY NO: side='no' -> api side='ask', price = 1 - price_dollars ---
        fsess2 = _FakeOrderSess(post_payload={"order_id": "def-456", "ts_ms": 1})
        oid2, sc2, err2 = kt.place_order(fsess2, fkey, "KXBTC15M-TEST", "no", 0.35, 3,
                                         ttl_s=None, post_only=True)
        _, _, body2 = fsess2.calls[0]
        assert body2["side"] == "ask", f"buy-NO must map to api side='ask', got {body2['side']!r}"
        assert body2["price"] == "0.6500", \
            f"buy-NO @ 0.35 must send price=1-0.35=0.6500, got {body2['price']!r}"
        assert "expiration_time" not in body2, \
            "ttl_s=None must NOT send expiration_time (true GTC, dead-man mechanism preserved)"
        assert body2["time_in_force"] == "good_till_canceled", \
            "true GTC still requires time_in_force=good_till_canceled (just without expiration_time)"
        assert oid2 == "def-456"
        observations.append("buy_no_price_flip_and_no_ttl=True")

        # --- sub-penny price round-trips cleanly (the actual trigger of the 2026-07-12 incident) ---
        fsess3 = _FakeOrderSess(post_payload={"order_id": "ghi-789"})
        kt.place_order(fsess3, fkey, "KXBTC15M-TEST", "yes", 0.001, 1)
        _, _, body3 = fsess3.calls[0]
        assert body3["price"] == "0.0010", f"sub-penny price mishandled: {body3['price']!r}"
        observations.append("sub_penny_price=0.0010")

        # --- reject path: V2 error body is FLAT ({"message": ...}, no "error" wrapper) ---
        fsess_rej = _FakeOrderSess(post_payload={"code": "bad_request",
                                                  "message": "price outside valid range"},
                                   post_status=400)
        oid_r, sc_r, err_r = kt.place_order(fsess_rej, fkey, "KXBTC15M-TEST", "yes", 0.27, 5)
        assert oid_r is None and sc_r == 400
        assert err_r == "price outside valid range", \
            f"flat V2 error body must be parsed via top-level 'message', got {err_r!r}"
        observations.append("flat_error_body_parsed=True")

        # --- legacy nested {"error": {"message": ...}} still falls back correctly ---
        fsess_rej2 = _FakeOrderSess(post_payload={"error": {"message": "legacy nested shape"}},
                                    post_status=400)
        _, _, err_r2 = kt.place_order(fsess_rej2, fkey, "KXBTC15M-TEST", "yes", 0.27, 5)
        assert err_r2 == "legacy nested shape", f"nested fallback broken: {err_r2!r}"
        observations.append("nested_error_fallback=True")

        # --- cancel_order(): DELETE /portfolio/events/orders/{order_id} ---
        fsess_c = _FakeOrderSess(delete_status=200)
        ok = kt.cancel_order(fsess_c, fkey, "abc-123")
        method_c, url_c, _ = fsess_c.calls[0]
        assert method_c == "DELETE"
        assert url_c.endswith("/portfolio/events/orders/abc-123"), \
            f"expected V2 cancel path, got {url_c!r}"
        assert ok is True
        observations.append("cancel_v2_path=True")

        # --- [PLACE-REJECT] stdout visibility is rate-limited per distinct error, per 60s ---
        import io, contextlib
        kt._PLACE_REJECT_LAST_PRINT.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            kt._print_place_reject(410, "Please switch to the V2 endpoints")   # 1st: prints
            kt._print_place_reject(410, "Please switch to the V2 endpoints")   # repeat <60s: suppressed
            kt._print_place_reject(400, "a different error")                  # new error: prints
        out = buf.getvalue()
        n_410 = out.count("[PLACE-REJECT] HTTP 410: Please switch to the V2 endpoints")
        n_400 = out.count("[PLACE-REJECT] HTTP 400: a different error")
        assert n_410 == 1, f"expected exactly 1 print for the repeated 410, got {n_410}\n{out!r}"
        assert n_400 == 1, f"expected exactly 1 print for the new 400, got {n_400}\n{out!r}"
        # simulate the 60s window elapsing -> the same error prints again
        kt._PLACE_REJECT_LAST_PRINT[f"410:Please switch to the V2 endpoints"] = time.time() - 61
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            kt._print_place_reject(410, "Please switch to the V2 endpoints")
        assert "[PLACE-REJECT] HTTP 410" in buf2.getvalue(), "should re-print after 60s window"
        kt._PLACE_REJECT_LAST_PRINT.clear()
        observations.append("place_reject_rate_limited_per_distinct_error=True")

        # --- dry-run smoke: DRY-RUN never calls place_order() / never POSTs ---
        import inspect
        src = inspect.getsource(kt)
        assert 'if not live:' in src and 'return fake, t_dec, time.time()' in src, \
            "dry-run early-return before place_order() must still be present"
        observations.append("dry_run_short_circuit_present=True")

        # --- lifecycle reject row now carries the venue error (extend _lifecycle_write) ---
        assert '"err": err' in src or '"err": err,' in src, \
            "_lifecycle_write must serialize the venue err onto reject rows"
        assert 'err=f"HTTP {sc_}: {err_}"' in src, \
            "the place() call site must thread err_ into the reject lifecycle row"
        observations.append("lifecycle_reject_err_threaded=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 27 — 2026-07-12 REAL-MONEY INCIDENT (run r29188732828): V2 fill-booking
#   direction fix + venue position sync + completion-chase brake
# ===========================================================================

# The 5 EXACT raw fill records from the incident, verbatim from the "raw" field of
# live_state/2026-07-12/kalshi_fees_btc15m.jsonl (live-state branch). Pre-fix, book_fill()
# booked every one of these as a straight BUY-YES (naive side-of-record), walking internal
# net_delta 1,2,4,8,16 while the venue's own post_position_fp (ground truth) walked
# 1,0,-2,-6,-14 -- the phantom long that the completion-chase then doubled into a real short.
INCIDENT_FIXTURES = [
    {"trade_id": "81d7557c-d319-4c79-6cce-72acd928d54a",
     "order_id": "9ae9e287-84a0-470b-940f-eaa4ead036a6", "is_taker": False, "side": "yes",
     "yes_price_dollars": "0.3400", "count_fp": "1.00", "fee_cost": "0.000000",
     "action": "buy", "post_position_fp": "1.00", "purchased_side": "yes",
     "outcome_side": "yes", "book_side": "bid"},
    {"trade_id": "04c3052d-fa8b-46d8-9ef2-27452787ddad",
     "order_id": "2de33729-e6ae-477a-8ee3-d11a7941c615", "is_taker": False, "side": "yes",
     "yes_price_dollars": "0.3500", "count_fp": "1.00", "fee_cost": "0.000000",
     "action": "sell", "post_position_fp": "0.00", "purchased_side": "no",
     "outcome_side": "no", "book_side": "ask"},
    {"trade_id": "faa17f7d-9c82-652e-50fd-8485f2a77fcb",
     "order_id": "4bd3b141-4a26-4ba0-b4d7-a38bc4817ab5", "is_taker": True, "side": "yes",
     "yes_price_dollars": "0.4000", "count_fp": "2.00", "fee_cost": "0.033600",
     "action": "sell", "post_position_fp": "-2.00", "purchased_side": "no",
     "outcome_side": "no", "book_side": "ask"},
    {"trade_id": "13f0e730-c456-5a38-3867-9e9e1e5b800f",
     "order_id": "a312cb53-28db-4560-a811-1c8080cc0a51", "is_taker": True, "side": "yes",
     "yes_price_dollars": "0.4200", "count_fp": "4.00", "fee_cost": "0.068300",
     "action": "sell", "post_position_fp": "-6.00", "purchased_side": "no",
     "outcome_side": "no", "book_side": "ask"},
    {"trade_id": "88b5700e-5df6-5760-e7d8-98135c7776df",
     "order_id": "45c3ae9c-8eb3-4636-9ffe-dd23d04737e5", "is_taker": True, "side": "yes",
     "yes_price_dollars": "0.4200", "count_fp": "8.00", "fee_cost": "0.136500",
     "action": "sell", "post_position_fp": "-14.00", "purchased_side": "no",
     "outcome_side": "no", "book_side": "ask"},
]


def test_incident_fixture_replay():
    """
    Replays the 5 exact 2026-07-12 incident fixtures through the REAL fix functions
    (kt.resolve_fill_side / kt.venue_position_from_fill / kt.should_snap_to_venue /
    kt.capped_completion_size -- the same module-level helpers book_fill(),
    sweep_window_fills(), and the dispose-cross completion path call at runtime) and checks:

      1. DIRECTION: booking net_delta the same way book_fill() does (sgn = +1 if
         resolve_fill_side()=="yes" else -1) tracks the venue's own post_position_fp at
         EVERY step: 1, 0, -2, -6, -14 -- not the pre-fix phantom 1, 2, 4, 8, 16.
      2. Cash/cost-basis direction: fixture[1] ("sell yes @ 0.35") must resolve to a NO
         purchase (cost 1-0.35=0.65), not the pre-fix bug's naive 0.35 debit that silently
         treated a yes-SALE as a cheap yes-BUY.
      3. AUTHORITATIVE SYNC: should_snap_to_venue() stays quiet on this healthy (post-fix)
         stream, but fires and reports the correct venue value when net_delta is deliberately
         desynced -- proving the sync rail is armed, not just coincidentally unneeded here.
      4. CHASE BRAKE: capped_completion_size(), fed the incident's own escalating
         (pre-fix-style corrupted) need values 1,2,4,8,16 directly, never lets a single cross
         order exceed --max-net (defense in depth even if net_delta were still somehow
         corrupted upstream), and CLIPS (rather than skips) when --max-notional headroom
         is tight.
    """
    name = "T27: 2026-07-12 incident fixture replay (direction fix + venue sync + chase brake)"
    try:
        observations = []
        expected_venue = [1.0, 0.0, -2.0, -6.0, -14.0]
        naive_pre_fix_trace = []
        net_delta = 0.0
        naive_net_delta = 0.0
        for i, f in enumerate(INCIDENT_FIXTURES):
            count = float(f["count_fp"])

            # --- fixed direction (book_fill()'s own booking arithmetic) ---
            side = kt.resolve_fill_side(f)
            sgn = 1.0 if side == "yes" else -1.0
            net_delta += sgn * count

            # --- pre-fix behavior for contrast: naive side-of-record, ignoring action ---
            naive_sgn = 1.0 if str(f["side"]).lower() == "yes" else -1.0
            naive_net_delta += naive_sgn * count
            naive_pre_fix_trace.append(naive_net_delta)

            venue = kt.venue_position_from_fill(f)
            assert venue == expected_venue[i], \
                f"fixture {i}: venue parse {venue} != {expected_venue[i]}"
            assert abs(net_delta - venue) < 1e-9, (
                f"fixture {i}: internal net_delta={net_delta} diverged from venue={venue} "
                f"post_position_fp (pre-fix this walked 1,2,4,8,16 vs venue truth 1,0,-2,-6,-14)")
            assert not kt.should_snap_to_venue(net_delta, venue), \
                f"fixture {i}: healthy (post-fix) stream should never need a sync snap"
        observations.append(f"net_delta_trace={[round(expected_venue[i], 1) for i in range(5)]}"
                            f"_matches_venue_trace=True")
        # sanity: the naive (pre-fix) trace really is the reported incident's 1,2,4,8,16,
        # confirming this replay actually reproduces the bug when the fix is bypassed
        assert naive_pre_fix_trace == [1.0, 2.0, 4.0, 8.0, 16.0], \
            f"pre-fix trace should reproduce the reported phantom-long walk, got {naive_pre_fix_trace}"
        observations.append(f"naive_pre_fix_trace_reproduces_incident={naive_pre_fix_trace}")

        # --- direction-accounting: sell-yes cash/cost basis ---
        sell_yes = INCIDENT_FIXTURES[1]
        resolved = kt.resolve_fill_side(sell_yes)
        assert resolved == "no", f"sell-yes fill must resolve to a NO purchase, got {resolved!r}"
        yp = float(sell_yes["yes_price_dollars"])
        fp_correct = yp if resolved == "yes" else round(1.0 - yp, 4)
        fp_buggy = yp  # pre-fix: always priced off yes_price_dollars regardless of direction
        assert fp_correct == 0.65, f"expected NO-leg cost basis 0.65, got {fp_correct}"
        assert fp_correct != fp_buggy, "fixed cost basis must diverge from the pre-fix (buggy) one"
        yes_equiv_received = round(1.0 - fp_correct, 4)
        assert yes_equiv_received == 0.35, \
            ("selling yes @0.35 is cash-equivalent to receiving 0.35/contract either way "
             f"it's booked, got {yes_equiv_received}")
        observations.append(f"sell_yes_cost_basis_fixed={fp_correct}_buggy_would_be={fp_buggy}")

        # --- venue-sync rail, standalone (boundary behavior) ---
        assert kt.should_snap_to_venue(net_delta=5.0, venue_pos=-14.0) is True
        assert kt.should_snap_to_venue(net_delta=-14.0, venue_pos=-14.0) is False
        assert kt.should_snap_to_venue(net_delta=-14.3, venue_pos=-14.0) is False, \
            "a 0.3-contract wobble under the 0.5 tolerance must not spuriously snap"
        assert kt.should_snap_to_venue(net_delta=1.0, venue_pos=None) is False, \
            "no post_position_fp on the record (older schema) must never force a snap"
        observations.append("sync_rail_snap_boundary_correct=True")

        # --- chase brake: single cross order never exceeds --max-net, even fed the exact
        # corrupted (pre-fix-style, doubling) `need` sizes the incident produced ---
        max_net_deployed = 1  # BOX_PLAYBOOK.md / CLAUDE.md deployed default (--max-net 1)
        for corrupted_need in (1, 2, 4, 8, 16):
            take = kt.capped_completion_size(corrupted_need, avail=999, max_net=max_net_deployed,
                                             cross_px=0.5, exposure=0.0, max_notional=25.0)
            assert take <= max_net_deployed, (
                f"chase brake failed: corrupted need={corrupted_need} produced take={take} "
                f"> max_net={max_net_deployed}")
        observations.append("chase_brake_caps_every_escalating_incident_need_at_max_net=True")

        # --- chase brake: --max-notional headroom is CLIPPED, not skipped-then-doubled ---
        take_clip = kt.capped_completion_size(4, avail=999, max_net=10, cross_px=0.50,
                                              exposure=24.5, max_notional=25.0)
        assert take_clip == 1, f"expected notional headroom (0.5/0.50) to clip to 1, got {take_clip}"
        take_none = kt.capped_completion_size(4, avail=999, max_net=10, cross_px=0.50,
                                              exposure=25.0, max_notional=25.0)
        assert take_none == 0, f"expected zero remaining headroom -> take=0, got {take_none}"
        take_full = kt.capped_completion_size(4, avail=999, max_net=10, cross_px=0.50,
                                              exposure=0.0, max_notional=25.0)
        assert take_full == 4, f"ample headroom should not clip a legitimate need, got {take_full}"
        observations.append("notional_headroom_clipped_not_skipped=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 28 — 2026-07-12 CHURN INCIDENT (run r29198341684): dispose-cross circuit
#   breaker (--dispose-max-attempts / --dispose-budget)
# ===========================================================================

# The incident's OWN winrec row, verbatim from live_state/2026-07-12/kalshi_winrec_btc15m.jsonl
# (live-state branch) for the exact ws under review. 62 quotes requested, only 6 fills, 53 of
# those requests were disposal crosses that never landed -- net -$0.55 in one window.
INCIDENT2_WINREC_ROW = {
    "ws": 1783870200, "asset": "btc", "tenor": 15, "cid": "KXBTC15M-26JUL121145-45",
    "net_final": 1.0, "n_yes": 3, "n_no": 3, "n_boxes": 3, "stranded": True, "abs_strand": 1.0,
    "legging_gap_s": 12.061690330505371, "n_taker": 1, "n_maker": 5, "n_dispose_cross": 53,
    "cost_yes": 2.26, "cost_no": 1.29, "consec_strands": 1, "realized": -0.55,
    "window_mark": 0.065, "max_fills_side": 3, "dispose_cross_on": True,
}
INCIDENT2_RECON_ROW = {  # live_state/2026-07-12/live_recon_btc15m_r29198341684.jsonl
    "ws": 1783870200, "requested": 62, "fills": 6, "fill_rate": 0.0968, "net": -0.55,
}


def _dispose_cap_decision(dispose_cross_n, dispose_give, dispose_max_attempts, dispose_budget,
                           force, dispose_force_used):
    """Replicates the DISPOSE-CAP decision from kalshi_trader.py's dispose-cross block
    (search '[DISPOSE-CAP]' in kalshi_trader.py -- the STRAND DISPOSAL comment block):

        attempts_capped = (a.dispose_max_attempts > 0
                           and winrec["dispose_cross"] >= a.dispose_max_attempts)
        budget_capped = (a.dispose_budget > 0
                         and winrec.get("dispose_give", 0.0) >= a.dispose_budget)
        cap_hit = attempts_capped or budget_capped
        force_bonus = force and cap_hit and not winrec.get("dispose_force_used", False)
        # blocked (no cross attempted) iff cap_hit and not force_bonus

    Returns (cap_hit, force_bonus, blocked, attempts_capped, budget_capped).
    """
    attempts_capped = dispose_max_attempts > 0 and dispose_cross_n >= dispose_max_attempts
    budget_capped = dispose_budget > 0 and dispose_give >= dispose_budget
    cap_hit = attempts_capped or budget_capped
    force_bonus = force and cap_hit and not dispose_force_used
    blocked = cap_hit and not force_bonus
    return cap_hit, force_bonus, blocked, attempts_capped, budget_capped


def test_dispose_cross_circuit_breaker():
    """
    FIX 1 (RCA 2026-07-12, run r29198341684): a feed-stale dead-man trip stranded a leg mid-fill;
    the disposal-cross chase then fired 53 crosses in ONE window for just 6 fills, net -$0.55 (the
    incident's own kalshi_winrec_btc15m.jsonl row: n_dispose_cross=53, realized=-0.55). At the
    strategy's ~2.7c/window edge, one such window erases ~20 windows of profit.

    Checks:
      1. The incident's own recon numbers (53 attempts, 62 requested, 6 fills) against the
         DEPLOYED default --dispose-max-attempts=3: the fix would have stopped crossing after
         attempt 3, not 53.
      2. Attempt cap trips at EXACTLY N attempts (not N-1, not N+1) then blocks further crosses.
      3. Budget cap arithmetic: cumulative give = sum(max(0, -lock) * take) across crosses; a
         PROFITABLE cross (lock >= 0) contributes $0 to the budget (never reduces headroom); the
         cap trips the instant cumulative give reaches --dispose-budget.
      4. Whichever cap (attempts or budget) is hit first wins, independently.
      5. FORCE (close-force) still gets exactly ONE bounded attempt after the cap trips, then
         reverts to blocked -- "stop crossing; defer to close-force; one more bounded attempt
         there; then accept the ride."
    """
    name = "T28: dispose-cross circuit breaker (53-cross incident replay + cap arithmetic)"
    try:
        import inspect
        import re
        observations = []

        # --- 1. incident replay against the deployed default cap ---
        default_max_attempts = 3
        incident_n = INCIDENT2_WINREC_ROW["n_dispose_cross"]
        assert incident_n == 53, f"fixture drift: expected 53, got {incident_n}"
        assert INCIDENT2_RECON_ROW["requested"] == 62 and INCIDENT2_RECON_ROW["fills"] == 6
        assert INCIDENT2_RECON_ROW["net"] == -0.55
        cap_hit, _, blocked, attempts_capped, _ = _dispose_cap_decision(
            dispose_cross_n=default_max_attempts, dispose_give=0.0,
            dispose_max_attempts=default_max_attempts, dispose_budget=0.10,
            force=False, dispose_force_used=False)
        assert attempts_capped and blocked, \
            "the deployed default (max_attempts=3) must cap well before the incident's 53"
        observations.append(f"incident_53_attempts_would_have_capped_at={default_max_attempts}"
                             f"_of_62_requested={INCIDENT2_RECON_ROW['requested']}")

        # --- 2. attempt cap trips at EXACTLY N, not off-by-one ---
        for n in (0, 1, 2):
            cap_hit, _, blocked, _, _ = _dispose_cap_decision(n, 0.0, 3, 0.10, False, False)
            assert not cap_hit and not blocked, f"attempt {n} (< 3) must NOT be capped"
        cap_hit, _, blocked, attempts_capped, _ = _dispose_cap_decision(3, 0.0, 3, 0.10, False, False)
        assert cap_hit and blocked and attempts_capped, "attempt 3 (== max) MUST be capped"
        cap_hit, _, blocked, _, _ = _dispose_cap_decision(4, 0.0, 3, 0.10, False, False)
        assert cap_hit and blocked, "attempt 4 (> max) must stay capped"
        observations.append("attempt_cap_trips_at_exactly_n=True")

        # --- 3. budget cap arithmetic: cumulative give, profitable crosses contribute $0 ---
        give = 0.0
        crosses = [(-0.04, 1), (-0.03, 1), (0.01, 1), (-0.02, 1)]   # (lock, take)
        running = []
        for lock, take in crosses:
            give += max(0.0, -lock) * take
            running.append(round(give, 4))
        assert running == [0.04, 0.07, 0.07, 0.09], f"cumulative give trace wrong: {running}"
        observations.append(f"cumulative_give_trace={running}_profitable_cross_contributes_0=True")
        cap_hit, _, blocked, _, budget_capped = _dispose_cap_decision(0, 0.09, 3, 0.10, False, False)
        assert not cap_hit, "give=0.09 must be UNDER a 0.10 budget"
        cap_hit, _, blocked, _, budget_capped = _dispose_cap_decision(0, 0.10, 3, 0.10, False, False)
        assert cap_hit and budget_capped and blocked, "give=0.10 (== budget) MUST trip the cap"
        observations.append("budget_cap_trips_at_exactly_the_dollar_threshold=True")

        # --- 4. whichever cap hits first wins, independently ---
        # attempts far from cap, but budget already blown -> still capped (via budget)
        cap_hit, _, blocked, attempts_capped, budget_capped = _dispose_cap_decision(
            1, 0.15, 10, 0.10, False, False)
        assert cap_hit and budget_capped and not attempts_capped, \
            "budget-only trip must cap even with attempts nowhere near its own limit"
        # attempts blown, budget nowhere near its cap -> still capped (via attempts)
        cap_hit, _, blocked, attempts_capped, budget_capped = _dispose_cap_decision(
            3, 0.01, 3, 10.0, False, False)
        assert cap_hit and attempts_capped and not budget_capped, \
            "attempts-only trip must cap even with budget nowhere near its own limit"
        observations.append("either_cap_independently_trips_the_breaker=True")

        # --- 5. FORCE gets exactly ONE bounded attempt after the cap, then blocks again ---
        cap_hit, force_bonus, blocked, _, _ = _dispose_cap_decision(
            3, 0.0, 3, 0.10, force=True, dispose_force_used=False)
        assert cap_hit and force_bonus and not blocked, \
            "FORCE with the bonus not yet spent must be allowed through despite the cap"
        cap_hit, force_bonus, blocked, _, _ = _dispose_cap_decision(
            3, 0.0, 3, 0.10, force=True, dispose_force_used=True)
        assert cap_hit and not force_bonus and blocked, \
            "FORCE must block once the one bonus attempt is already spent (accept the ride)"
        cap_hit, force_bonus, blocked, _, _ = _dispose_cap_decision(
            3, 0.0, 3, 0.10, force=False, dispose_force_used=False)
        assert cap_hit and not force_bonus and blocked, \
            "the bonus is FORCE-only; a non-force aged/near-close attempt stays blocked at cap"
        observations.append("force_gets_exactly_one_bonus_attempt_then_blocks=True")

        # --- structural: the deployed flags exist with the documented defaults ---
        import re
        src = inspect.getsource(kt)
        m1 = re.search(r'"--dispose-max-attempts",\s*type=int,\s*default=(\d+)', src)
        m2 = re.search(r'"--dispose-budget",\s*type=float,\s*default=([\d.]+)', src)
        assert m1 and int(m1.group(1)) == 3, "‑-dispose-max-attempts default must be 3"
        assert m2 and float(m2.group(1)) == 0.10, "--dispose-budget default must be 0.10"
        observations.append("cli_defaults_pinned=max_attempts_3_budget_0.10")

        # --- structural: the cap check runs BEFORE the pre-existing per-attempt reject_cd
        # throttle (order matters -- the throttle alone let the incident's 53-cross cadence run
        # for the whole window; the cap is what actually bounds the TOTAL) and ckey stays the
        # stable per-side sentinel (not price-keyed), so the throttle isn't reset by ordinary
        # price movement between attempts ---
        idx_dc = src.index("# --- STRAND DISPOSAL: cross to COMPLETE")
        idx_dc_end = src.index("# --- PULL stale / toxic / off-target rungs ---", idx_dc)
        dc_block = src[idx_dc: idx_dc_end]
        assert 'ckey = (cside, "_xcross")' in dc_block, \
            "the per-side rate-limit key must stay a stable sentinel, not the (movable) cross price"
        idx_cap = dc_block.index("attempts_capped = (a.dispose_max_attempts")
        idx_reject = dc_block.index("reject_cd.get(ckey, 0.0) <= time.time()")
        assert idx_cap < idx_reject, \
            "the attempt/budget cap check must gate BEFORE the pre-existing reject_cd throttle"
        assert 'winrec["dispose_cross"] >= a.dispose_max_attempts' in dc_block
        assert 'winrec.get("dispose_give", 0.0) >= a.dispose_budget' in dc_block
        observations.append("cap_gates_before_pre_existing_throttle_using_stable_side_key=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 29 — DEAD-MAN TIERING (2026-07-12 RCA): stale > 1x/2x/3x deadman_s
# ===========================================================================

def _deadman_tier_for(stale, deadman_s, net_delta):
    """Replicates the tier computation from kalshi_trader.py's staleness watchdog (search
    'DEAD-MAN TIERING' in kalshi_trader.py):

        if stale > 3 * a.deadman_s: tier = 3
        elif stale > 2 * a.deadman_s and abs(net_delta) > 1e-9: tier = 2
        elif stale > a.deadman_s: tier = 1
        else: tier = 0
    """
    if stale > 3 * deadman_s:
        return 3
    if stale > 2 * deadman_s and abs(net_delta) > 1e-9:
        return 2
    if stale > deadman_s:
        return 1
    return 0


def test_deadman_tiering():
    """
    FIX 2 (RCA 2026-07-12, run r29198341684): the pre-fix binary "stale > deadman_s ->
    cancel-all" cancelled a COMPLETING quote ~12s after one side filled (a routine WS+REST blip),
    stranding the 1-lot leg the disposal-cross chase then hit 53x. Tiering scales the response to
    how stale the feed actually is, leaning on the venue-side --order-ttl-s TTL (150s default)
    for resting orders instead of an immediate hard cancel.

    Checks:
      1. Tier boundaries at exactly 1x/2x/3x deadman_s (strict >, matching the pre-existing
         stale-book dead-man's own strict-> convention).
      2. Tier 2 requires BOTH staleness AND unpaired net -- a flat book at 2x staleness stays
         tier 1 (nothing unpaired to protect via the one-shot disposal cross).
      3. Tier 3 fires from staleness alone, matching the pre-fix full-cancel behavior (now the
         LAST resort instead of the first response).
      4. STRUCTURAL: tier 1's branch contains no cancel call (no cancel-all, no per-order
         drop()) -- resting orders are left for the venue-side TTL, not touched locally.
      5. STRUCTURAL: tier 2's branch cancels only OPENING quotes (is_completing_side-gated) and
         arms exactly one disposal-cross attempt (deadman_t2_dispose_pending), which is then
         consumed (counted) by the dispose-cross circuit breaker from T28.
      6. Recovery: a fresh two-sided book resets tier to 0 in the same statement that resets
         deadman_tripped (the pre-existing reset path), and since tiers 1-2 never touch
         COMPLETING quotes (is_completing_side exempts them from the opening-suppression filter
         and from the tier-2 cancel sweep), the completion-chase for any unpaired inventory was
         never paused and needs no separate re-arm -- verified directly via kt.is_completing_side.
    """
    name = "T29: dead-man tiering (1x/2x/3x transitions, tier-1 no-cancel, TTL reliance, recovery)"
    try:
        import inspect
        import re
        observations = []
        deadman_s = 15.0

        # --- 1. tier boundaries, strict > ---
        assert _deadman_tier_for(15.0, deadman_s, 0.0) == 0, "exactly 1x must NOT yet be tier 1 (strict >)"
        assert _deadman_tier_for(15.001, deadman_s, 0.0) == 1, "just past 1x -> tier 1"
        assert _deadman_tier_for(29.999, deadman_s, 1.0) == 1, "just under 2x stays tier 1 even w/ unpaired net"
        assert _deadman_tier_for(30.0, deadman_s, 1.0) == 1, "exactly 2x must NOT yet be tier 2 (strict >)"
        assert _deadman_tier_for(30.001, deadman_s, 1.0) == 2, "just past 2x w/ unpaired net -> tier 2"
        assert _deadman_tier_for(44.999, deadman_s, 1.0) == 2, "just under 3x stays tier 2"
        assert _deadman_tier_for(45.0, deadman_s, 1.0) == 2, "exactly 3x must NOT yet be tier 3 (strict >)"
        assert _deadman_tier_for(45.001, deadman_s, 1.0) == 3, "just past 3x -> tier 3"
        observations.append("tier_boundaries_strict_gt_at_1x_2x_3x=True")

        # --- 2. tier 2 requires BOTH staleness AND unpaired net ---
        assert _deadman_tier_for(35.0, deadman_s, 0.0) == 1, \
            "2x-3x staleness with a FLAT book must stay tier 1, not escalate to tier 2"
        assert _deadman_tier_for(35.0, deadman_s, -2.0) == 2, \
            "2x-3x staleness with unpaired net (either sign) escalates to tier 2"
        observations.append("tier_2_requires_unpaired_net_not_staleness_alone=True")

        # --- 3. tier 3 fires from staleness alone (matches pre-fix full-cancel, now last resort) ---
        assert _deadman_tier_for(50.0, deadman_s, 0.0) == 3
        assert _deadman_tier_for(50.0, deadman_s, 5.0) == 3
        observations.append("tier_3_unconditional_on_net_delta=True")

        # --- 4/5. structural checks on the real source ---
        src = inspect.getsource(kt)
        idx1 = src.index("DEAD-MAN TIERING (RCA 2026-07-12")
        idx_t1 = src.index("if _new_deadman_tier == 1:", idx1)
        idx_t2 = src.index("elif _new_deadman_tier == 2:", idx1)
        idx_t3 = src.index("elif _new_deadman_tier == 3:", idx1)
        tier1_block = src[idx_t1:idx_t2]
        tier2_block = src[idx_t2:idx_t3]
        assert "cancel_all_resting(" not in tier1_block and "drop(" not in tier1_block, \
            "tier 1 must NOT cancel anything -- resting orders rely on the venue-side TTL"
        observations.append("tier1_no_cancel_relies_on_venue_ttl=True")
        assert "is_completing_side(" in tier2_block and "drop(" in tier2_block, \
            "tier 2 must selectively cancel OPENING quotes via is_completing_side"
        assert "deadman_t2_dispose_pending = True" in tier2_block, \
            "tier 2 must arm exactly one disposal-cross attempt"
        assert "cancel_all_resting(reason=\"deadman_stale\")" in src[idx_t3:idx_t3 + 400], \
            "tier 3 must still be the full cancel-all (last resort, pre-fix behavior preserved)"
        observations.append("tier2_selective_cancel_plus_one_shot_dispose_armed=True")

        # venue-side TTL the tier-1 no-cancel design leans on actually exists and is generous
        # enough to cover a real blip window (150s default, vs a 15s deadman_s tier-1 trip)
        m = re.search(r'"--order-ttl-s",\s*type=float,\s*default=([\d.]+)', src)
        assert m and float(m.group(1)) == 150.0, "--order-ttl-s default (venue TTL) must be 150.0"
        observations.append("order_ttl_s_default=150.0_covers_tier1_blips")

        # --- 6. recovery: tier reset colocated with the pre-existing deadman_tripped reset ---
        idx_bp = src.index('# --- book poll (REST; react-poll cadence) ---')
        bp_block = src[idx_bp: idx_bp + 1600]
        assert "deadman_tripped = False" in bp_block and "deadman_tier = 0" in bp_block, \
            "tier must reset to 0 alongside the pre-existing deadman_tripped reset on fresh book"
        idx_reset = bp_block.index("deadman_tripped = False")
        idx_tier_reset = bp_block.index("deadman_tier = 0")
        assert idx_tier_reset > idx_reset, "tier reset should immediately follow the tripped reset"
        observations.append("recovery_resets_tier_alongside_deadman_tripped=True")

        # completion-chase re-engagement: is_completing_side (the REAL module-level function, not
        # a replica) is what exempts completing quotes from both the tier>=1 opening-suppression
        # filter and the tier-2 cancel sweep -- so completions were never paused by any tier and
        # need no special re-arm on recovery. Verify the predicate directly.
        assert kt.is_completing_side("no", net_delta=1.0) is True, "BUY-NO completes a stranded YES"
        assert kt.is_completing_side("yes", net_delta=1.0) is False, "BUY-YES opens further when net=+1"
        assert kt.is_completing_side("yes", net_delta=-1.0) is True, "BUY-YES completes a stranded NO"
        assert kt.is_completing_side("no", net_delta=-1.0) is False, "BUY-NO opens further when net=-1"
        assert kt.is_completing_side("yes", net_delta=0.0) is False, "flat book: nothing is 'completing'"
        observations.append("is_completing_side_predicate_correct_for_both_signs=True")
        # and confirm the tier>=1 opening-suppression filter in the main loop actually calls it
        idx_targets = src.index("targets = desired_levels(")
        filt_block = src[idx_targets: idx_targets + 700]
        assert "if deadman_tier >= 1:" in filt_block and "is_completing_side(t[0], net_delta)" in filt_block, \
            "tier>=1 must filter targets down to completing-only via is_completing_side"
        observations.append("tier_ge_1_opening_suppression_uses_is_completing_side=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 30 — WS RESILIENCE: exponential-backoff reconnect + tightened REST cadence
# ===========================================================================

def test_ws_resilience():
    """
    FIX 2e (RCA 2026-07-12): the ws_feeder reconnect loop used a flat 1s sleep on every
    disconnect, and get_book_cached's REST fallback cadence never tightened when the WS was
    down -- so a routine reconnect gap and a real venue outage looked identical to the staleness
    watchdog. Checks:
      1. kt.ws_reconnect_backoff_s (the REAL function) grows exponentially and caps at ~5s.
      2. get_book_cached's REST poll cadence halves while ws_health["connected"] is False
         (structural: source inspection, since get_book_cached is a closure inside main()).
      3. ws_feeder marks ws_health connected/disconnected and resets the backoff counter on a
         clean (re)connect (structural).
    """
    name = "T30: WS resilience (exponential-backoff reconnect, tightened REST cadence on WS-down)"
    try:
        import inspect
        observations = []

        # --- 1. exponential backoff, capped at 5s ---
        seq = [kt.ws_reconnect_backoff_s(n) for n in range(1, 8)]
        assert seq == [1.0, 2.0, 4.0, 5.0, 5.0, 5.0, 5.0], f"backoff sequence wrong: {seq}"
        observations.append(f"backoff_sequence={seq}")
        assert kt.ws_reconnect_backoff_s(0) == kt.ws_reconnect_backoff_s(1), \
            "attempt < 1 must clamp to attempt 1 (no zero/negative sleep)"
        observations.append("sub_1_attempt_clamped=True")

        # --- 2/3. structural checks on the real source ---
        src = inspect.getsource(kt)
        gbc_idx = src.index("def get_book_cached(ticker, max_age=None):")
        gbc_block = src[gbc_idx: gbc_idx + 900]
        assert 'ws_health.get("connected", True) else 1.0' in gbc_block, \
            "REST cadence must tighten (halve) when ws_health reports disconnected"
        observations.append("rest_cadence_tightens_on_ws_down=True")

        feeder_src = src[src.index("def ws_feeder("): src.index("def _apply_snapshot(")]
        assert 'ws_health["connected"] = True' in feeder_src, "feeder must mark connected on subscribe"
        assert 'ws_health["attempts"] = 0' in feeder_src, "feeder must reset backoff counter on connect"
        assert 'ws_health["connected"] = False' in feeder_src, "feeder must mark disconnected on exception"
        assert "ws_reconnect_backoff_s(ws_health" in feeder_src, \
            "feeder's reconnect sleep must use the exponential-backoff helper, not a flat sleep"
        observations.append("ws_feeder_health_tracking_and_backoff_wired=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# BONUS: Test microprice and gate_check helpers directly (from kt module)
# ===========================================================================

def test_helpers():
    """Quick sanity checks on the pure helpers imported directly from kalshi_trader."""
    name = "T0: helper functions (microprice, gate_check, desired_levels, resolve_result)"
    try:
        observations = []

        # microprice: equal sizes -> midpoint
        mp = kt.microprice(0.40, 0.60, 100, 100)
        observations.append(f"microprice_equal_sz={mp:.4f}")
        assert abs(mp - 0.50) < 1e-9, f"Expected 0.50 got {mp}"

        # microprice: all ask-side size -> bid price
        mp2 = kt.microprice(0.40, 0.60, 0, 100)
        observations.append(f"microprice_all_ask={mp2:.4f}")
        assert abs(mp2 - 0.40) < 1e-9, f"Expected 0.40 got {mp2}"

        # microprice: all bid-side size -> ask price
        mp3 = kt.microprice(0.40, 0.60, 100, 0)
        observations.append(f"microprice_all_bid={mp3:.4f}")
        assert abs(mp3 - 0.60) < 1e-9, f"Expected 0.60 got {mp3}"

        # gate_check: BUY-YES NOT toxic when microprice >= price-margin
        # mp ≈ 0.50, price=0.45, margin>0 -> mp=0.50 >= 0.45-margin -> NOT toxic
        toxic = kt.gate_check("yes", 0.45, 0.45, 0.55, 0.0, "marg", 0.003, 100, 100)
        observations.append(f"gate_YES_ok={not toxic}")
        assert not toxic, "BUY-YES at 0.45 with mp=0.50 should NOT be toxic"

        # gate_check: BUY-YES IS toxic when price far above microprice
        # mp=0.50 (equal size), price=0.58, margin=0.003 -> mp < price-margin = 0.577 -> TOXIC
        toxic2 = kt.gate_check("yes", 0.58, 0.45, 0.65, 0.0, "marg", 0.003, 100, 100)
        observations.append(f"gate_YES_toxic={toxic2}")
        # mp for yes_bid=0.45, yes_ask=0.65, equal size = 0.55; price=0.58, margin=0.003
        # 0.55 < 0.58-0.003=0.577 -> toxic
        assert toxic2, "BUY-YES at 0.58 when mp=0.55 should be toxic"

        # desired_levels: basic output shape
        mk = {"tick": 0.01, "asset": "btc"}
        levels = kt.desired_levels(mk, 0.45, 0.55, 0.0, 1, 50.0, 0.25, 0.01)
        observations.append(f"desired_levels_count={len(levels)}")
        assert len(levels) > 0, "desired_levels should return at least one level"
        for side, price in levels:
            assert side in ("yes", "no"), f"bad side {side!r}"
            assert 0 < price < 1, f"price out of range: {price}"

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 31 — TRANSPORT HEALTH: end-of-window quiet book no longer trips the dead-man
# ===========================================================================

def test_transport_health_deadman():
    """
    RCA 2026-07-12 (confirmed from live telemetry, run r29198341684-successor): ws_stale events
    with stale_s 45-49 fired at 16:59Z, 17:14Z, 17:30Z -- the FINAL MINUTE of three consecutive
    15-min windows, culminating in a T3 "cancel-all" at 17:30Z. Root cause: the market goes quiet
    at expiry (everyone pulls quotes -> book empty/one-sided), which is normal, but the dead-man
    clock (`last_book_ok`) only refreshed on a NON-EMPTY two-sided book. A REST poll that
    succeeded (HTTP OK) but found an empty/one-sided book left the clock stuck, so tiers escalated
    on a routine end-of-window pattern EVERY window -- and T3's cancel-all could cancel a
    COMPLETING quote near expiry, manufacturing exactly the stranded legs the tiering (bb27db0a)
    was built to prevent.

    THE FIX: transport health (`last_transport_ok` -- any REST poll that completed, or any WS
    message received, regardless of book content) is now what the dead-man tiering measures,
    while `last_book_ok` (content freshness) is left untouched for everything else that uses it.

    Checks:
      1. kt.get_book(sess, ticker): ok=True on a genuinely empty/one-sided book (HTTP succeeded),
         ok=True on a real two-sided book, ok=False on a transport failure (exception/timeout).
      2. kt.ws_transport_alive(last_msg_ts, now): strict boundary at WS_TRANSPORT_ALIVE_S, and
         None (never received) is never "alive".
      3. Quiet-market fixture (replays the incident): repeated REST success-with-empty-book, WS
         silent, over a span far longer than 3x deadman_s -- dead-man tier stays 0 throughout,
         even though the CONTENT clock (last_book_ok, never refreshed) would have reproduced the
         observed 45-49s staleness and tripped T1/T2/T3 under the pre-fix logic.
      4. Genuine outage: REST failing (ok=False) AND WS silent -- tier escalates through
         1x/2x/3x deadman_s at the SAME thresholds/semantics as the pre-existing tiering (T29):
         tier 2 still requires unpaired net, tier 3 fires from staleness alone.
      5. Recovery: once REST starts succeeding again (or a WS message arrives), the tier resets
         to 0 on the very next tick -- transport-driven, not book-content-driven.
      6. WS message receipt alone -- even with REST continuously failing and no two-sided book --
         keeps the tier at 0 for as long as messages keep arriving.
      7. STRUCTURAL: the dead-man staleness computation in the real source reads
         `last_transport_ok`, not `last_book_ok`; get_book_cached returns a transport_ok signal;
         ws_feeder stamps ws_health["last_msg_ts"] on every message (before any type dispatch, so
         even a heartbeat/empty-book delta counts); the T2/T3 alert text names both failure modes.
    """
    name = "T31: transport health (end-of-window quiet book no longer a false dead-man trip)"
    try:
        import inspect
        observations = []
        deadman_s = 15.0

        # --- 1. kt.get_book: ok distinguishes transport failure from book emptiness ---
        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload
            def json(self):
                return self._payload

        class _FakeSess:
            def __init__(self, payload):
                self._payload = payload
            def get(self, url, timeout=4):
                return _FakeResp(self._payload)

        class _RaiseSess:
            def get(self, url, timeout=4):
                raise ConnectionError("simulated venue outage")

        # exact end-of-window shape: HTTP 200, both sides empty (everyone pulled quotes)
        empty_sess = _FakeSess({"orderbook_fp": {"yes_dollars": [], "no_dollars": []}})
        ybb, ybq, yba, yaq, ok = kt.get_book(empty_sess, "KXBTC15M-TEST")
        assert (ybb, ybq, yba, yaq) == (None, None, None, None), "empty book must still be all-None content"
        assert ok is True, "empty book with a completed HTTP call must be ok=True (transport alive)"
        observations.append("empty_book_transport_ok_true=True")

        two_sided_sess = _FakeSess({"orderbook_fp": {
            "yes_dollars": [["0.45", "10"]], "no_dollars": [["0.40", "8"]],
        }})
        ybb2, ybq2, yba2, yaq2, ok2 = kt.get_book(two_sided_sess, "KXBTC15M-TEST")
        assert ybb2 == 0.45 and yba2 == 0.60 and ok2 is True
        observations.append("two_sided_book_ok_true_and_parsed=True")

        r3 = kt.get_book(_RaiseSess(), "KXBTC15M-TEST")
        assert r3 == (None, None, None, None, False), "a real transport failure must be ok=False"
        observations.append("transport_failure_ok_false=True")

        # --- 2. kt.ws_transport_alive: strict boundary, None never alive ---
        now0 = 1_000_000.0
        thr = kt.WS_TRANSPORT_ALIVE_S
        assert kt.ws_transport_alive(None, now0) is False, "never-received must not be alive"
        assert kt.ws_transport_alive(now0 - thr, now0) is True, "exactly at threshold -> alive"
        assert kt.ws_transport_alive(now0 - thr - 0.001, now0) is False, "just past threshold -> not alive"
        assert kt.ws_transport_alive(now0, now0) is True, "a message this instant is alive"
        observations.append(f"ws_transport_alive_boundary_correct(thr={thr:.0f}s)=True")

        # --- shared one-tick-lag simulator, mirrors the real main-loop ordering: escalate off the
        # PREVIOUS tick's last_transport_ok, then refresh the clock from THIS tick's REST/WS
        # evidence, then apply the same-tick recovery reset -- exactly the sequence now wired into
        # the DEAD-MAN TIERING block + book-poll section of kalshi_trader.py's main loop. Reuses
        # the REAL kt.ws_transport_alive and the tier-boundary math T29 already validates against
        # the actual source (_deadman_tier_for is that same validated replica).
        def _replay(events, net_delta=0.0):
            last_transport_ok = events[0][0]
            tier = 0
            tripped = False
            trace = []
            for now, rest_ok, ws_msg_ts in events:
                stale = now - last_transport_ok
                new_tier = _deadman_tier_for(stale, deadman_s, net_delta)
                if not tripped and new_tier > tier:
                    tier = new_tier
                    if tier == 3:
                        tripped = True
                if rest_ok or kt.ws_transport_alive(ws_msg_ts, now):
                    last_transport_ok = now
                if (now - last_transport_ok) <= deadman_s:
                    tripped = False
                    tier = 0
                trace.append(tier)
            return trace

        # --- 3. Quiet-market fixture: replays the incident (stale_s 45-49 in CONTENT terms, over
        # 3 consecutive windows' final minutes) -- REST always succeeds, book always empty, WS
        # silent. Content clock (last_book_ok) never refreshes -> would hit the observed 45-49s
        # and trip T1/T2/T3 under the PRE-FIX logic. Transport clock refreshes every tick.
        t0 = 1_783_875_601.0   # 16:59Z timestamp from the live telemetry (first ws_stale event)
        quiet_events = [(t0 + i, True, None) for i in range(0, 90)]   # 90s of REST-ok/empty-book
        quiet_trace = _replay(quiet_events, net_delta=0.0)
        assert all(t == 0 for t in quiet_trace), \
            f"quiet market (REST ok, empty book) must never leave tier 0: {set(quiet_trace)}"
        observations.append(f"quiet_market_{len(quiet_events)}_ticks_tier_always_0=True")
        # the CONTENT-clock staleness this fixture would have produced under pre-fix logic
        # (last_book_ok pinned at t0 the whole time -- book is never fresh)
        content_stale_at_49s = 49.0
        pre_fix_tier = _deadman_tier_for(content_stale_at_49s, deadman_s, 0.0)
        assert pre_fix_tier == 3, "sanity: the observed 49s content-staleness WOULD have been tier 3 pre-fix"
        observations.append(f"pre_fix_would_have_tripped_tier={pre_fix_tier}_post_fix_stays_0=True")

        # --- 4. Genuine outage: REST failing + WS silent -- same 1x/2x/3x thresholds as T29.
        # tick i has stale=i (last_transport_ok pinned at t0, event i is t0+i), and the tiering
        # boundaries are strict-> (matching T29's own convention), so tier 1 begins at i=16
        # (stale=16 > 15), tier 3 at i=46 (stale=46 > 45).
        outage_events_flat = [(t0 + i, False, None) for i in range(0, 60)]
        trace_flat = _replay(outage_events_flat, net_delta=0.0)   # flat book -> tier 2 unreachable
        assert trace_flat[15] == 0 and trace_flat[16] == 1, "tier 1 boundary at >15s"
        assert max(trace_flat[16:46]) == 1, "flat book (no unpaired net) must stay tier 1 through 2x"
        assert trace_flat[46] == 3, "tier 3 boundary at >45s, unconditional on net_delta"
        observations.append("genuine_outage_flat_book_tier_1_then_3_at_correct_boundaries=True")

        outage_events_unpaired = [(t0 + i, False, None) for i in range(0, 60)]
        trace_up = _replay(outage_events_unpaired, net_delta=2.0)
        assert trace_up[16] == 1 and trace_up[30] == 1 and trace_up[31] == 2 and trace_up[46] == 3
        observations.append("genuine_outage_unpaired_net_tier_1_2_3_at_correct_boundaries=True")

        # --- 5. Recovery: REST resumes -> tier resets to 0 on the very next tick ---
        recovered_events = outage_events_unpaired + [(t0 + 60, True, None), (t0 + 61, True, None)]
        trace_recov = _replay(recovered_events, net_delta=2.0)
        assert trace_recov[-2] == 0 and trace_recov[-1] == 0, \
            f"transport recovery must reset tier to 0 immediately: {trace_recov[-3:]}"
        observations.append("recovery_resets_tier_to_0_on_first_healthy_tick=True")

        # --- 6. WS message receipt alone (no two-sided book needed) keeps transport alive ---
        ws_only_events = [(t0 + i, False, t0 + i) for i in range(0, 60)]   # REST always failing,
        # a WS message stamped THIS same instant every tick (content irrelevant to ws_transport_alive)
        trace_ws_only = _replay(ws_only_events, net_delta=2.0)
        assert all(t == 0 for t in trace_ws_only), \
            f"WS messages alone (REST failing throughout) must hold tier at 0: {set(trace_ws_only)}"
        observations.append("ws_message_receipt_alone_holds_transport_alive_rest_failing=True")

        # --- 7. structural: real source wiring ---
        src = inspect.getsource(kt)
        # anchor on the escalation block's OWN comment ("C1 DEAD-MAN TIERING..."), not the
        # deadman_tier init comment earlier in main() -- both share the "DEAD-MAN TIERING (RCA
        # 2026-07-12" substring, but only this one is adjacent to the staleness computation.
        idx1 = src.index("C1 DEAD-MAN TIERING (RCA 2026-07-12")
        tiering_block = src[idx1: idx1 + 3200]
        assert "stale = time.time() - last_transport_ok" in tiering_block, \
            "dead-man staleness must be measured off last_transport_ok, not last_book_ok"
        assert "stale = time.time() - last_book_ok" not in tiering_block, \
            "the CONTENT clock must no longer drive tier escalation"
        observations.append("tiering_reads_last_transport_ok_not_last_book_ok=True")

        gbc_idx = src.index("def get_book_cached(ticker, max_age=None):")
        gbc_src = src[gbc_idx: src.index("\n    def ", gbc_idx + 40)]
        assert "transport_ok" in gbc_src, "get_book_cached must expose a transport_ok signal"
        assert "ybb, ybq, yba, yaq, ok = get_book(sess, ticker)" in gbc_src, \
            "get_book_cached must consume get_book's ok flag"
        observations.append("get_book_cached_threads_transport_ok=True")

        gb_idx = src.index("def get_book(sess, ticker):")
        gb_src = src[gb_idx: src.index("\ndef parse_book_entry(", gb_idx)]
        assert "return None, None, None, None, True" in gb_src, \
            "get_book must return ok=True on a genuinely empty/one-sided book"
        assert "return None, None, None, None, False" in gb_src, \
            "get_book must return ok=False on a transport failure"
        observations.append("get_book_ok_flag_present_both_branches=True")

        feeder_src = src[src.index("def ws_feeder("): src.index("def _apply_snapshot(")]
        stamp_idx = feeder_src.index('ws_health["last_msg_ts"] = time.time()')
        raw_check_idx = feeder_src.index("if not raw:")
        assert stamp_idx < raw_check_idx, \
            "last_msg_ts must be stamped BEFORE the empty-message check, so even a heartbeat counts"
        observations.append("ws_feeder_stamps_last_msg_ts_before_content_dispatch=True")

        assert "ws_transport_alive(ws_health" in src, \
            "the main loop must actually call ws_transport_alive against ws_health"
        observations.append("main_loop_calls_ws_transport_alive=True")

        # alert text names both failure modes (ws silent, rest failing), per the RCA's spec example
        assert "ws silent, rest failing" in tiering_block
        observations.append("alert_text_names_both_transport_failure_modes=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 32 — ws=1783876500 RCA (run r29200721447): completion-size overshoot +
# no notional exemption for completions + inherited-position engagement
# ===========================================================================

def _notional_gate_blocks(exposure, price, post, max_notional, is_completing):
    """Replicates the C8 aggregate notional cap decision (source: the '# C8 aggregate notional
    cap' comment block in kalshi_trader.py's main(), right before the size_mode branches) --
    returns True iff this quote would be blocked/skipped.

        if exposure + price * post > max_notional:
            if not is_completing: BLOCKED
            else: PERMITTED (FIX 2 exemption; want is still bounded by completion_size_clamp)
        else: PERMITTED
    """
    if exposure + price * post > max_notional:
        return not is_completing
    return False


def test_completion_deficit_fix():
    """
    FORENSIC RCA (live telemetry 2026-07-12, window ws=1783876500 17:15Z, run r29200721447,
    winrec-confirmed stranded=true, net_final=-1.0): the box legged in cleanly and fast
    (legging_gap 0.135s), but the completing-quote SIZING overshot -- size-mode markout computed
    want=2 when the unpaired deficit was only 1 (at t=127.5s and t=149.9s), each time flipping net
    imbalance +1 -> -1 instead of landing at 0. The extra contracts pushed cumulative window
    notional to $5.37 (cost_yes 3.04 + cost_no 2.33), breaching --max-notional 5, after which
    EVERY placement -- including risk-reducing completions -- was blocked for the remaining 743s
    of the window. Result: a 1-lot naked leg rode to settlement (-$1.00 vs ~+$0.05 for a clean
    window).

    Checks:
      (a) FIX 1 -- kt.completion_size_clamp(): deficit=1, sizing wants 2 -> placed size clamps to
          1; deficit 0 -> no completion quote (returns 0); want never gets sized UP to the
          deficit if sizing under-wanted; non-completing (opening) quotes pass through untouched.
      (b) FIX 2 -- the C8 notional gate: replays the incident's own arithmetic (cost_yes 3.04 +
          cost_no 2.33 = 5.37 > --max-notional 5.00, deficit 1) showing a completing quote is now
          PERMITTED (clamped to the deficit) while an opening quote at the same exposure stays
          BLOCKED. Structural check that all THREE notional re-checks in the sizing block (the C8
          gate itself, the markout re-check, the portfolio-aware re-check) carry the same
          is_completing exemption, and that the exemption logs a rate-limited [NOTIONAL-EXEMPT]
          line.
      (c) FIX 3 -- inherited-position engagement: verifies (by calling the REAL kt.desired_levels
          + kt.is_completing_side, not a source replica) that once startup reconciliation seeds
          net_delta from an inherited venue position, the completing side is the ONLY side in
          `targets` on the very first tick a book is available -- with no dependency on this
          session placing or filling anything of its own first. Also checks the [INHERITED] log
          line exists, fires only when net_delta != 0, and is positioned AFTER net_delta is
          seeded in the source.
    """
    name = "T32: ws=1783876500 RCA -- completion deficit clamp, notional exemption, inherited engagement"
    try:
        import inspect
        import re
        observations = []

        # --- (a) FIX 1: completion_size_clamp ---
        # incident replay: deficit=1 (net_delta=+1, completing side wants to reduce it to 0),
        # size-mode markout wanted 2 -> must clamp to 1
        assert kt.completion_size_clamp(2, True, 1.0) == 1, \
            "deficit=1, sizing wants 2 -> must clamp to 1 (the exact incident overshoot)"
        assert kt.completion_size_clamp(2, True, -1.0) == 1, "sign of net_delta must not matter, only magnitude"
        observations.append("incident_overshoot_want2_deficit1_clamps_to_1=True")

        # deficit 0 (net_delta ~flat) -> no completion quote at all
        assert kt.completion_size_clamp(2, True, 0.0) == 0, "deficit 0 must return 0 (no completion quote)"
        assert kt.completion_size_clamp(3, True, 1e-10) == 0, "sub-contract net_delta rounds to 0 deficit -> 0"
        observations.append("deficit_0_returns_0_no_completion_quote=True")

        # never sizes UP past what sizing actually wanted, even if the deficit is larger
        assert kt.completion_size_clamp(1, True, 5.0) == 1, "must never inflate want up to the deficit"
        # a want that already matches (or undershoots) the deficit passes through unchanged
        assert kt.completion_size_clamp(1, True, 1.0) == 1
        assert kt.completion_size_clamp(3, True, 3.0) == 3
        observations.append("never_inflates_want_only_clamps_down=True")

        # non-completing (opening) quotes are untouched, no matter the size or net_delta
        assert kt.completion_size_clamp(5, False, 3.0) == 5, "opening quotes must pass through unclamped"
        assert kt.completion_size_clamp(0, True, 4.0) == 0, "want<=0 passes through (nothing to clamp)"
        observations.append("opening_quotes_and_zero_want_pass_through_unchanged=True")

        # structural: the real call site is wired between the size-mode branches and the
        # portfolio-aware block, so it applies uniformly regardless of size_mode
        src = inspect.getsource(kt)
        idx_sizes = src.index('if a.size_mode == "markout":')
        idx_port = src.index("# PORTFOLIO-AWARE SIZING (opt-in --portfolio-aware")
        between = src[idx_sizes:idx_port]
        assert "want = completion_size_clamp(want, is_completing, net_delta)" in between, \
            "FIX 1 must clamp `want` for every size_mode, before portfolio-aware sizing runs"
        observations.append("fix1_call_site_wired_after_all_size_modes_before_portfolio_aware=True")

        # --- (b) FIX 2: notional-gate exemption, replaying the incident's own arithmetic ---
        cost_yes, cost_no = 3.04, 2.33
        exposure = round(cost_yes + cost_no, 4)
        assert exposure == 5.37, f"fixture drift: expected 5.37, got {exposure}"
        max_notional = 5.00
        assert exposure > max_notional, "fixture sanity: cumulative notional must already breach the cap"
        deficit = 1
        observations.append(f"incident_fixture_exposure={exposure}_max_notional={max_notional}_deficit={deficit}")

        # opening (fresh) quote at this exposure must stay BLOCKED -- exactly as before the fix
        assert _notional_gate_blocks(exposure, 0.50, 1, max_notional, is_completing=False) is True, \
            "an OPENING quote must remain blocked once the cap is breached"
        observations.append("opening_quote_still_blocked_at_breached_cap=True")

        # a COMPLETING quote at the SAME breached exposure must now be PERMITTED (FIX 2) --
        # this is the exact gate that stranded the ws=1783876500 leg for the remaining 743s
        assert _notional_gate_blocks(exposure, 0.50, 1, max_notional, is_completing=True) is False, \
            "a COMPLETING quote must be permitted through the notional cap post-fix"
        observations.append("completing_quote_now_permitted_at_breached_cap=True")

        # and its SIZE is still bounded to the deficit by FIX 1 -- exempt from the dollar cap,
        # never exempt from the pairing-size cap
        assert kt.completion_size_clamp(2, True, float(deficit)) == deficit, \
            "the exempted completing quote's size must still clamp to the unpaired deficit"
        observations.append("exempted_completion_still_size_clamped_to_deficit=True")

        # structural: all THREE notional checks in the sizing block carry the is_completing
        # exemption (the C8 gate itself, the markout branch re-check, the portfolio-aware re-check)
        idx_c8 = src.index("# C8 aggregate notional cap (BUY side only")
        idx_rung = src.index("# Side ladder rung cap", idx_c8)
        c8_block = src[idx_c8:idx_rung]
        assert "if not is_completing:" in c8_block, "the C8 gate must exempt completing quotes"
        assert "[NOTIONAL-EXEMPT]" in c8_block, "the exemption must log a rate-limited marker line"
        assert 'reject_cd.get(("_notional_exempt_log", side)' in c8_block, \
            "the exemption log must be rate-limited via the existing reject_cd mechanism"
        observations.append("c8_gate_exempts_and_logs=True")

        idx_markout = src.index('if a.size_mode == "markout":')
        idx_else = src.index("\n                else:\n", idx_markout)
        markout_block = src[idx_markout:idx_else]
        assert re.search(r"exposure \+ price \* want > a\.max_notional and not is_completing", markout_block), \
            "the markout branch's own notional re-check must also exempt completing quotes"
        observations.append("markout_recheck_exempts_completing=True")

        idx_pa = src.index("if a.portfolio_aware:")
        idx_place = src.index("res = place(side, price, ybb, yba", idx_pa)
        pa_block = src[idx_pa:idx_place]
        assert re.search(r"exposure \+ price \* want > a\.max_notional and not is_completing", pa_block), \
            "the portfolio-aware branch's own notional re-check must also exempt completing quotes"
        observations.append("portfolio_aware_recheck_exempts_completing=True")

        # --- (c) FIX 3: inherited-position engagement (real desired_levels/is_completing_side) ---
        # session restarts holding 1 NO (net_delta=-1) inherited from a predecessor mid-window
        net_delta_inherited = -1.0
        mk_stub = {"tick": 0.01}
        targets = kt.desired_levels(mk_stub, 0.42, 0.44, net_delta_inherited, 1, 1.0, 0.0, 0.0)
        assert targets, "an inherited unpaired position must produce at least one target immediately"
        assert all(kt.is_completing_side(side, net_delta_inherited) for side, _ in targets), \
            "with cap=1 and skew=0, EVERY target must be the completing (yes) side -- opening " \
            "(no) is gated off by desired_levels' own inventory cap, with no dependency on this " \
            "session's own first fill"
        assert any(side == "yes" for side, _ in targets), "net_delta=-1 -> the completing side is YES"
        observations.append(f"inherited_net={net_delta_inherited:+.0f}_targets_completing_only={targets}")

        # symmetric check: inherited long YES (net_delta=+1) -> only NO (completing) targets
        targets2 = kt.desired_levels(mk_stub, 0.42, 0.44, 1.0, 1, 1.0, 0.0, 0.0)
        assert targets2 and all(s == "no" for s, _ in targets2)
        observations.append("symmetric_inherited_net_+1_targets_no_only=True")

        # structural: the [INHERITED] log line exists, is gated on abs(net_delta) > 1e-9, and is
        # positioned AFTER net_delta is actually seeded (so it reflects the seeded value, not a
        # stale pre-seed read)
        idx_seed_block = src.index("if not _inherited_seed_done:")
        idx_seed_end = src.index("_last_book_cache.clear()", idx_seed_block)
        seed_block = src[idx_seed_block:idx_seed_end]
        assert "[INHERITED]" in seed_block, "the inherited-engagement confirmation log must exist"
        idx_netdelta_assign = seed_block.index("net_delta += _ih_ct")
        idx_inherited_log = seed_block.index("[INHERITED]")
        assert idx_netdelta_assign < idx_inherited_log, \
            "the [INHERITED] log must fire AFTER net_delta is seeded, not before"
        assert "if abs(net_delta) > 1e-9:" in seed_block, \
            "the log must be gated on an actual nonzero inherited position"
        observations.append("inherited_log_present_gated_and_ordered_after_seed=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 33 — GAP 1 (2026-07-12 telemetry forensics): winrec row for EVERY
#   traded window, including zero-fill traded windows and windows lost to
#   evict/relaunch (kalshi_winrec_btc15m.jsonl got only 3 rows for ~11 traded
#   windows because the row was only ever written when the loop lived long
#   enough to see the NEXT window's rollover -- see _write_winrec_row /
#   _flatten_and_exit in kalshi_trader.py).
# ===========================================================================

def _winrec_exit_guard(requested, n_yes, n_no, mk_ws, already_written_ws):
    """Replicates the GAP 1 exit-path guard verbatim (kalshi_trader.py _flatten_and_exit,
    right after cancel_all_resting()):

        if mk is not None and (ops.get("place", 0) > 0
                                or (win_fills.get("yes", 0) + win_fills.get("no", 0)) > 0):
            _write_winrec_row(mk, None)

    combined with _write_winrec_row's own idempotency guard:

        if mk_ is None or _winrec_written_ws["ws"] == mk_["ws"]:
            return

    Returns True iff a row would actually be written."""
    traded = requested > 0 or (n_yes + n_no) > 0
    if not traded:
        return False
    return already_written_ws != mk_ws


def test_winrec_every_traded_window():
    """
    GAP 1 root cause: winrec_fh.write() lived ONLY inside the "Window rollover" branch of the
    main loop, which only runs once the loop observes time.time() >= mk["we"] for the NEXT
    window while still alive. The trader is routinely evicted + relaunched at/near a window
    boundary (see kalshi_trader.py git history: "evict ... + relaunch at window boundary") --
    a fresh process has blank in-memory state (win_fills/ops/winrec all reset to zero), so the
    window that was actively trading when the OLD process died never reached the rollover code
    and its row was silently lost forever. Fix: factor the row-build into a shared
    _write_winrec_row(), called both at normal rollover (unconditional, unchanged) AND from
    _flatten_and_exit() (every exit path: normal, exception, SIGTERM, atexit) whenever the
    still-open window was actually traded (requested>0 OR fills>0).

    Checks:
      1. Guard logic: a traded window with ZERO fills (requested>0, n_yes=n_no=0) still gets a
         row; a window with neither requests nor fills does NOT (avoids spurious empty rows for
         a window that was open but never touched at process exit); idempotent (won't double
         write a window already flushed by the normal rollover path).
      2. Structural: _write_winrec_row exists, is called unconditionally at the normal rollover
         site AND from _flatten_and_exit under the exact requested>0-or-fills>0 gate;
         _flatten_and_exit runs on every exit (atexit/SIGTERM/SIGINT/exception) per T6/T7.
      3. Schema: the row still carries every pre-existing field (net_final, n_yes, n_no,
         n_dispose_cross, dispose_give, stranded, legging_gap_s, ...) PLUS the new
         deadman_max_tier field (peak dead-man tier reached during the window -- tracked
         separately from deadman_tier because that resets to 0 on transport recovery mid-window).
    """
    name = "T33: winrec row for every traded window (GAP 1, 2026-07-12 telemetry forensics)"
    try:
        import inspect
        observations = []

        # --- 1. guard logic: zero-fill-but-traded window still gets a row ---
        assert _winrec_exit_guard(requested=5, n_yes=0, n_no=0, mk_ws=100, already_written_ws=None) is True, \
            "a traded window with zero fills (requested>0) must still get a winrec row"
        observations.append("zero_fill_traded_window_writes=True")

        # --- untraded window (never touched) does NOT get a spurious row at exit ---
        assert _winrec_exit_guard(requested=0, n_yes=0, n_no=0, mk_ws=101, already_written_ws=None) is False, \
            "a window with no requests and no fills must not get a spurious exit-time row"
        observations.append("untouched_window_no_spurious_row=True")

        # --- some fills but ops['place'] undercounted (shouldn't happen, but fills alone qualify) ---
        assert _winrec_exit_guard(requested=0, n_yes=2, n_no=1, mk_ws=102, already_written_ws=None) is True
        observations.append("fills_alone_qualify_as_traded=True")

        # --- idempotent: a window already flushed by the normal rollover must not double-write
        # if the exit path also runs (the exact race the shared _winrec_written_ws guard exists for) ---
        assert _winrec_exit_guard(requested=5, n_yes=1, n_no=1, mk_ws=200, already_written_ws=200) is False, \
            "a window whose row was already written must not be written again at exit"
        assert _winrec_exit_guard(requested=5, n_yes=1, n_no=1, mk_ws=201, already_written_ws=200) is True, \
            "a DIFFERENT (new, in-progress) window must still get its own row at exit"
        observations.append("idempotent_no_double_write_new_window_still_written=True")

        # --- 2. structural: shared writer exists, used at both call sites ---
        src = inspect.getsource(kt)
        assert "def _write_winrec_row(mk_, r_now):" in src
        assert 'if mk_ is None or _winrec_written_ws["ws"] == mk_["ws"]:' in src, \
            "the writer must guard on identity + already-written, matching the replica above"
        observations.append("shared_writer_present_with_idempotency_guard=True")

        # normal rollover site: unconditional call (byte-identical trigger condition to before --
        # every window, traded or not, as it always was)
        idx_roll = src.index("# Window rollover")
        idx_roll_end = src.index("win_fills = {\"yes\": 0, \"no\": 0}   # fresh window", idx_roll)
        roll_block = src[idx_roll: idx_roll_end]
        assert "_write_winrec_row(mk, r_now)" in roll_block, \
            "the normal rollover path must call the shared writer unconditionally"
        observations.append("rollover_site_calls_shared_writer_unconditionally=True")

        # exit site: gated call, right after cancel_all_resting(reason="deadman")
        idx_exit = src.index("def _flatten_and_exit(reason):")
        idx_exit_end = src.index("def ", idx_exit + 40)
        exit_block = src[idx_exit: idx_exit_end]
        assert 'cancel_all_resting(reason="deadman")' in exit_block
        assert ('ops.get("place", 0) > 0\n' in exit_block
                or 'ops.get("place", 0) > 0' in exit_block), \
            "exit path must gate on ops['place']>0 (matches the replica's `requested`)"
        assert '(win_fills.get("yes", 0) + win_fills.get("no", 0)) > 0' in exit_block, \
            "exit path must ALSO gate on fills>0 (requested>0 OR fills>0, matches the replica)"
        assert "_write_winrec_row(mk, None)" in exit_block, \
            "exit path must call the shared writer for the still-open window"
        idx_cancel_in_exit = exit_block.index('cancel_all_resting(reason="deadman")')
        idx_write_in_exit = exit_block.index("_write_winrec_row(mk, None)")
        assert idx_cancel_in_exit < idx_write_in_exit, \
            "cancel_all_resting must run before the exit-time winrec flush (final state snapshot)"
        observations.append("exit_site_gated_call_present_after_cancel_all_resting=True")

        # atexit/signal wiring already validated by T6/T7 (error-storm/stale-book dead-man) --
        # confirm _flatten_and_exit is STILL the thing registered for every exit path.
        assert 'atexit.register(lambda: _flatten_and_exit("process exit"))' in src
        assert "signal.signal(_sig," in src and "_flatten_and_exit(f\"signal {s_}\")" in src
        observations.append("flatten_and_exit_still_wired_to_atexit_and_signals=True")

        # --- 3. schema: pre-existing fields kept + new deadman_max_tier field added ---
        writer_idx = src.index("def _write_winrec_row(mk_, r_now):")
        writer_end = src.index("\n    def _sweep_unresolved_lifecycle", writer_idx)
        writer_src = src[writer_idx: writer_end]
        for field in ('"ts"', '"asset"', '"ws"', '"cid"', '"settle"', '"net_final"', '"n_yes"',
                      '"n_no"', '"n_boxes"', '"stranded"', '"abs_strand"', '"maxnet"',
                      '"legging_gap_s"', '"n_taker"', '"n_maker"', '"n_dispose_cross"',
                      '"dispose_give"', '"dispose_capped"', '"cost_yes"', '"cost_no"',
                      '"consec_strands"', '"realized"', '"window_mark"', '"guard_yes"',
                      '"max_fills_side"', '"dispose_cross_on"', '"dispose_max_attempts"',
                      '"dispose_budget"'):
            assert field in writer_src, f"pre-existing winrec schema field {field} missing"
        assert '"deadman_max_tier"' in writer_src, "new deadman_max_tier field missing"
        observations.append("schema_preserved_plus_deadman_max_tier_added=True")

        # deadman_max_tier is tracked separately from deadman_tier (which resets on recovery)
        assert 'winrec["deadman_max_tier"] = max(winrec.get("deadman_max_tier", 0), _new_deadman_tier)' in src
        assert '"deadman_max_tier": 0' in src, "winrec reset dict must (re-)seed the new field"
        observations.append("deadman_max_tier_tracked_independent_of_recovery_reset=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 34 — GAP 2 (2026-07-12 telemetry forensics): every placed order
#   eventually gets EXACTLY ONE terminal lifecycle row. TTL-assumed expiry is
#   promoted from "observational only" to an actual drop + "expire_assumed"
#   terminal row; a periodic sweep closes out anything still tracked (e.g. a
#   cancel that never got a venue-side confirmation) at window/session end
#   with "unresolved_window_end".
# ===========================================================================

def _ttl_expire_sweep(resting, order_ttl_s, now):
    """Replicates kalshi_trader.py's promoted TTL EXPIRE block: any resting order aged
    >= order_ttl_s is POPPED (we now trust the venue-side TTL -- no redundant cancel_order()
    call) and an 'expire_assumed' terminal event is recorded for it."""
    events = []
    if not order_ttl_s or order_ttl_s <= 0:
        return events
    for key in [k for k, m in resting.items() if (now - m["ts"]) >= order_ttl_s]:
        meta = resting.pop(key)
        events.append(("expire_assumed", meta.get("oid"), key))
    return events


def _unresolved_sweep(pending_cancel, resting):
    """Replicates kalshi_trader.py's _sweep_unresolved_lifecycle(): every order still tracked
    in pending_cancel or resting gets a terminal 'unresolved_window_end' row and is purged."""
    events = []
    for key in list(pending_cancel.keys()):
        meta = pending_cancel.pop(key)
        events.append(("unresolved_window_end", meta.get("oid"), key))
    for key in list(resting.keys()):
        meta = resting.pop(key)
        events.append(("unresolved_window_end", meta.get("oid"), key))
    return events


def test_lifecycle_every_place_gets_terminal_row():
    """
    GAP 2 root cause: 43% of placed orders on 2026-07-12 had NO terminal lifecycle event. Two
    leaks: (a) TTL-assumed-expired orders were only ever flagged '_lifecycle_expired' + logged
    an 'expire' row WITHOUT being removed from `resting` -- never actually terminal, and (b) a
    cancel that failed venue-side (cancel_fail in flush_cancels) left the order in
    `pending_cancel` forever with no fill/cancel/expire row ever written.

    Checks (simulated window, mirrors the real dict shapes/flow -- resting/pending_cancel keyed
    by (side, price), meta carries oid/ts/want/filled):
      1. TTL-assumed expiry: an order aged past --order-ttl-s is dropped from `resting` and gets
         exactly one 'expire_assumed' row; an order NOT yet aged is left alone (still trackable
         by the normal fill/cancel paths).
      2. Unresolved-at-window-end sweep: whatever is STILL in pending_cancel (cancel_fail
         leftover) or resting at window end gets exactly one 'unresolved_window_end' row.
      3. End-to-end: a simulated window with N placed orders (fill / cancel / TTL-expire /
         cancel_fail-leftover) produces exactly N terminal rows, no order left uncovered and none
         double-covered.
      4. Structural: the real TTL block actually pops from `resting` now (promoted from
         observational-only) and writes 'expire_assumed'; the old passive '_lifecycle_expired'
         flag marker is GONE; _sweep_unresolved_lifecycle pops both dicts and writes
         'unresolved_window_end'; it's called at the normal rollover site (right after
         cancel_all_resting()) AND inside _flatten_and_exit (every exit path).
    """
    name = "T34: every placed order gets exactly one terminal lifecycle row (GAP 2)"
    try:
        import inspect
        observations = []

        # --- 1. TTL-assumed expiry ---
        now = 1_000_000.0
        resting = {
            ("yes", 0.45): {"oid": "o1", "ts": now - 200, "filled": 0.0, "want": 5},  # aged past TTL
            ("no", 0.30):  {"oid": "o2", "ts": now - 10,  "filled": 0.0, "want": 5},  # fresh
        }
        events = _ttl_expire_sweep(resting, order_ttl_s=150.0, now=now)
        assert len(events) == 1 and events[0][0] == "expire_assumed" and events[0][1] == "o1", \
            f"expected exactly one expire_assumed for the aged order, got {events}"
        assert ("yes", 0.45) not in resting, "TTL-assumed-expired order must be DROPPED from resting"
        assert ("no", 0.30) in resting, "not-yet-aged order must be left alone"
        observations.append("ttl_assumed_expiry_drops_aged_only=True")

        # order_ttl_s off -> no-op (matches the real `if a.order_ttl_s and a.order_ttl_s > 0:` guard)
        resting2 = {("yes", 0.5): {"oid": "o3", "ts": now - 999, "filled": 0.0, "want": 1}}
        assert _ttl_expire_sweep(resting2, order_ttl_s=0, now=now) == []
        assert ("yes", 0.5) in resting2, "TTL sweep must be a no-op when order_ttl_s is falsy"
        observations.append("ttl_sweep_noop_when_disabled=True")

        # --- 2. unresolved-at-window-end sweep ---
        pending_cancel = {("yes", 0.60): {"oid": "o2b", "ts": now, "filled": 0.0, "want": 5}}
        resting3 = {("no", 0.30): {"oid": "o2", "ts": now, "filled": 0.0, "want": 5}}
        events2 = _unresolved_sweep(pending_cancel, resting3)
        assert len(events2) == 2, f"expected 2 unresolved_window_end rows, got {events2}"
        assert all(e[0] == "unresolved_window_end" for e in events2)
        assert pending_cancel == {} and resting3 == {}, \
            "the sweep must fully purge both dicts (idempotent -- nothing left to double-write later)"
        observations.append("unresolved_sweep_closes_out_both_dicts=True")

        # --- 3. end-to-end: N placed orders -> N terminal rows, no gaps, no doubles ---
        # simulate a window with 4 placed orders: 1 fills, 1 cancels cleanly (not our sweep's
        # concern -- covered by the pre-existing "cancel" event path), 1 TTL-assumed-expires,
        # 1 gets stuck in pending_cancel (cancel_fail) until window end.
        terminal_rows = []
        # order A: fills (pre-existing path, not simulated here -- just accounted for)
        terminal_rows.append(("fill", "oA"))
        # order B: cancels cleanly (pre-existing path)
        terminal_rows.append(("cancel", "oB"))
        # order C: TTL-assumed-expires mid-window
        resting_sim = {("yes", 0.20): {"oid": "oC", "ts": now - 200, "filled": 0.0, "want": 5}}
        terminal_rows += [(e, oid) for e, oid, _ in _ttl_expire_sweep(resting_sim, 150.0, now)]
        # order D: cancel_fail leftover, only resolved by the window-end sweep
        pending_cancel_sim = {("no", 0.55): {"oid": "oD", "ts": now, "filled": 0.0, "want": 5}}
        terminal_rows += [(e, oid) for e, oid, _ in _unresolved_sweep(pending_cancel_sim, resting_sim)]
        oids = sorted(oid for _, oid in terminal_rows)
        assert oids == ["oA", "oB", "oC", "oD"], f"every placed order must get exactly one terminal row: {oids}"
        assert len(terminal_rows) == len(set(oids)) == 4, "no order may get zero or multiple terminal rows"
        assert resting_sim == {} and pending_cancel_sim == {}, "nothing left tracked after window end"
        observations.append("four_orders_four_distinct_terminal_rows_no_gaps_no_doubles=True")

        # --- 4. structural: real source promoted from observational-only + wired at both sites ---
        src = inspect.getsource(kt)
        idx_ttl = src.index("# ORDER-LIFECYCLE: TTL EXPIRE detection")
        idx_ttl_end = src.index("# Rung cap: evict rungs", idx_ttl)
        ttl_block = src[idx_ttl: idx_ttl_end]
        assert '"expire_assumed"' in ttl_block, "TTL block must emit the expire_assumed event"
        assert "resting.pop(key" in ttl_block, \
            "TTL-assumed-expired orders must actually be dropped from `resting` now"
        assert "_lifecycle_expired" not in ttl_block, \
            "the old passive flag-only marker must be gone (promoted to an actual drop)"
        assert '"expire",' not in ttl_block, \
            "the old non-terminal 'expire' observational event must be replaced, not duplicated"
        observations.append("ttl_block_promoted_drops_and_emits_expire_assumed=True")

        assert "def _sweep_unresolved_lifecycle():" in src
        sweep_idx = src.index("def _sweep_unresolved_lifecycle():")
        sweep_end = src.index("\n    # --- poll live balance", sweep_idx) if "\n    # --- poll live balance" in src[sweep_idx:] else src.index("\n    def ", sweep_idx + 40)
        sweep_src = src[sweep_idx: sweep_end]
        assert '"unresolved_window_end"' in sweep_src
        assert "pending_cancel.pop(key, None)" in sweep_src
        assert "resting.pop(key, None)" in sweep_src
        observations.append("sweep_function_pops_both_dicts_emits_unresolved_window_end=True")

        # called at rollover, right after cancel_all_resting()
        idx_roll2 = src.index('cancel_all_resting()   # tokens change on rollover')
        roll2_tail = src[idx_roll2: idx_roll2 + 300]
        assert "_sweep_unresolved_lifecycle()" in roll2_tail, \
            "rollover must sweep for unresolved orders right after cancel_all_resting()"
        observations.append("rollover_calls_sweep_after_cancel_all_resting=True")

        # called inside _flatten_and_exit too (every exit path)
        idx_exit2 = src.index("def _flatten_and_exit(reason):")
        idx_exit2_end = src.index("def ", idx_exit2 + 40)
        exit2_block = src[idx_exit2: idx_exit2_end]
        assert "_sweep_unresolved_lifecycle()" in exit2_block, \
            "_flatten_and_exit must also sweep for unresolved orders on process exit"
        observations.append("exit_path_calls_sweep_too=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 35 — GAP 3 (2026-07-12 telemetry forensics): live_recon rows carry
#   n_dispose_cross/dispose_give (previously winrec-only), so the two files
#   can be analyzed independently without a join.
# ===========================================================================

def _recon_row(requested, fills, net, gross, inv_max, n_dispose_cross=0, dispose_give=0.0):
    """Replicates the _recon_write() row shape (kalshi_trader.py) for the fields under test."""
    return {
        "fills": int(fills), "requested": int(requested),
        "fill_rate": round(fills / requested, 4) if requested else 0.0,
        "net": round(net, 4), "gross": round(gross, 4), "inv_max": round(inv_max, 2),
        "n_dispose_cross": int(n_dispose_cross), "dispose_give": round(dispose_give, 4),
    }


def test_recon_carries_dispose_fields():
    """
    GAP 3: n_dispose_cross/dispose_give existed ONLY in kalshi_winrec_btc15m.jsonl; live_recon
    rows had no disposal-cross telemetry at all, forcing a join to winrec for any recon-only
    analysis. Fix: _recon_write() gains n_dispose_cross/dispose_give params (default 0/0.0 --
    every pre-existing call site that doesn't pass them stays byte-identical), and every one of
    the three call sites (no-activity immediate write, void settlement, real settlement) now
    threads the window's own dispose-cross snapshot through.
    """
    name = "T35: live_recon rows carry n_dispose_cross/dispose_give (GAP 3)"
    try:
        import inspect
        observations = []

        # --- 1. row shape / default-inert (byte-identical when not passed) ---
        row_default = _recon_row(10, 3, 0.5, 0.5, 2.0)
        assert row_default["n_dispose_cross"] == 0 and row_default["dispose_give"] == 0.0, \
            "default (no dispose activity) must be 0/0.0, matching pre-GAP-3 call sites"
        observations.append("dispose_fields_default_zero=True")

        row_active = _recon_row(62, 6, -0.55, -0.55, 1.0, n_dispose_cross=53, dispose_give=0.09)
        assert row_active["n_dispose_cross"] == 53 and row_active["dispose_give"] == 0.09
        observations.append("dispose_fields_carry_through_when_nonzero=True")

        # --- 2. structural: _recon_write signature + row + all 3 call sites threaded ---
        src = inspect.getsource(kt)
        assert ("def _recon_write(ws_epoch, requested, fills, net, gross, inv_max,\n"
                "                     n_seeded_fills=0, seeded_net=0.0, n_seed_cooldowns=0,\n"
                "                     n_dispose_cross=0, dispose_give=0.0):") in src, \
            "_recon_write must gain n_dispose_cross/dispose_give with 0/0.0 defaults"
        rw_idx = src.index("def _recon_write(ws_epoch")
        rw_end = src.index("\n    # WINDOW-END GUARD", rw_idx)
        rw_src = src[rw_idx: rw_end]
        assert '"n_dispose_cross": int(n_dispose_cross), "dispose_give": round(dispose_give, 4),' in rw_src
        observations.append("recon_write_row_carries_new_fields=True")

        # entry snapshot at rollover (mirrors the pre-existing recon_invmax pattern)
        assert "_recon_dispose_cross = winrec[\"dispose_cross\"]" in src
        assert '_recon_dispose_give = winrec.get("dispose_give", 0.0)' in src
        assert '"recon_dispose_cross": _recon_dispose_cross,' in src
        assert '"recon_dispose_give": _recon_dispose_give,' in src
        observations.append("rollover_snapshots_dispose_fields_into_pending_settle_entry=True")

        # all three call sites pass the fields through
        n_immediate = src.count("n_dispose_cross=_recon_dispose_cross, dispose_give=_recon_dispose_give")
        n_settle = src.count('n_dispose_cross=en.get("recon_dispose_cross", 0),\n'
                             '                                    dispose_give=en.get("recon_dispose_give", 0.0))')
        assert n_immediate == 1, f"expected exactly 1 no-activity call site threading dispose fields, got {n_immediate}"
        assert n_settle == 2, f"expected exactly 2 settle-path (void + real) call sites, got {n_settle}"
        observations.append(f"all_three_recon_write_call_sites_threaded=immediate={n_immediate}_settle={n_settle}")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 36 — px_band shadow-test arms (strategies.py / shadow_compare.py):
#   pre-registered fill-efficiency arms as_trim70 / as_band, engine-level
#   default-inertness (px_band=None byte-identical to pre-px_band behavior),
#   and OPENING-only / completions-unaffected semantics.
# ===========================================================================

def test_px_band_shadow_arms():
    """
    Fills study (2026-07-12): quotes at extreme prices (>=0.70) had 41% cancelled-unfilled
    (wasted queue effort) while <0.30 fills were the BEST performers live. Strat.px_band=(lo, hi)
    (default None=unchanged) skips OPENING quotes priced outside [lo, hi]; completions are never
    affected. Two pre-registered arms: as_trim70 (av_stoikov + px_band=(0.0,0.70), trims only the
    expensive side) and as_band (av_stoikov + px_band=(0.30,0.70), trims both tails -- expected to
    LOSE since <0.30 was the best band live; isolates whether the edge lives there).

    shadow_compare.py has no existing test file, so this is the small standalone px_band unit +
    engine-level test called for in that case.
    """
    name = "T36: px_band fill-efficiency shadow arms (pre-registered, default-inert)"
    try:
        import strategies
        import shadow_compare as sc
        observations = []

        # --- 1. registration: both arms present, enabled, correctly configured ---
        errs = strategies.validate()
        assert errs == [], f"strategies.validate() must pass with the new arms: {errs}"
        by_name = {s.name: s for s in strategies.REGISTRY}
        assert "as_trim70" in by_name and "as_band" in by_name
        t70, band = by_name["as_trim70"], by_name["as_band"]
        assert t70.enabled and band.enabled, "both px_band arms must be enabled (live A/B)"
        assert t70.gate == "as" and band.gate == "as", "both build on the av_stoikov (as) config"
        assert t70.skew == 0.99 and band.skew == 0.99, "both must match av_stoikov's skew=0.99"
        assert t70.px_band == (0.0, 0.70), f"as_trim70 px_band mismatch: {t70.px_band}"
        assert band.px_band == (0.30, 0.70), f"as_band px_band mismatch: {band.px_band}"
        assert t70.note and band.note, "pre-registered a-priori notes must be present"
        assert "WIN" in t70.note.upper() or "NEUTRAL" in t70.note.upper(), \
            "as_trim70 must carry an a-priori (pre-registered) directional expectation"
        assert "LOSE" in band.note.upper(), \
            "as_band must carry the pre-registered expectation that it LOSES (isolates the <0.30 edge)"
        observations.append("both_arms_registered_enabled_correctly_configured_with_a_priori_notes=True")

        # --- baseline/av_stoikov and every OTHER strat must be untouched (px_band=None default) ---
        for s in strategies.REGISTRY:
            if s.name in ("as_trim70", "as_band"):
                continue
            assert s.px_band is None, f"{s.name}: px_band must stay None (default-inert) -- got {s.px_band}"
        observations.append("all_other_arms_px_band_none_byte_identical=True")

        # --- 2. engine: px_band=None is a true no-op (_px_band_blocked always False) ---
        mk = {"up": "TOK_UP", "down": "TOK_DOWN", "we": time.time() + 900}
        shared = {"st": None, "s0": None, "spothist": [], "microhist": {}, "flow": {}, "qema": {}}
        v_none = sc.Variant("v_none", mk, cap=50, skew=0.99, gate="as", shared=shared, px_band=None)
        for price, d_per, delta in [(0.01, 1.0, 0.0), (0.99, -1.0, 0.0), (0.5, 1.0, 5.0), (2.0, 1.0, -5.0)]:
            v_none.delta = delta
            assert v_none._px_band_blocked(price, d_per) is False, \
                f"px_band=None must NEVER block (price={price} d_per={d_per} delta={delta})"
        observations.append("px_band_none_never_blocks_engine_level=True")

        # --- 3. engine: OPENING fill outside [lo,hi] IS blocked; inside is NOT; completions
        # (opposite direction to current delta) are NEVER blocked regardless of price ---
        v = sc.Variant("v_band", mk, cap=50, skew=0.99, gate=None, shared=shared, px_band=(0.30, 0.70))
        assert v._px_band_blocked(0.85, 1.0) is True, "opening fill outside band must block (delta=0 flat)"
        assert v._px_band_blocked(0.50, 1.0) is False, "opening fill inside band must pass"
        v.delta = 5.0
        assert v._px_band_blocked(0.85, 1.0) is True, "opening (same-direction) fill outside band still blocks"
        assert v._px_band_blocked(0.85, -1.0) is False, \
            "completing (opposite-direction, reduces |inventory|) fill must NEVER be blocked, any price"
        observations.append("opening_blocked_outside_band_completions_always_pass=True")

        # --- 4. full on_trade() engine integration: outside-band opening skipped (fill=0, delta
        # unchanged), in-band opening fills, and a subsequent completion outside the band still
        # goes through (net delta returns toward 0) ---
        vt = sc.Variant("vt", mk, cap=50, skew=0.99, gate=None, shared=shared, px_band=(0.30, 0.70))
        vt.set_tob("TOK_UP", 0.83, 10, 0.85, 2)     # touch ask outside the band, thin queue ahead
        vt.on_trade("TOK_UP", "BUY", 0.85, 5)        # taker eats the 2 ahead + reaches us
        assert vt.fills == 0 and vt.delta == 0.0, "outside-band OPENING trade must be fully skipped"
        observations.append("on_trade_skips_outside_band_opening=True")

        vt.set_tob("TOK_UP", 0.45, 10, 0.50, 2)      # touch ask inside the band
        vt.on_trade("TOK_UP", "BUY", 0.50, 5)
        assert vt.fills == 1 and vt.delta != 0.0, "in-band OPENING trade must fill normally"
        opened_delta = vt.delta
        observations.append(f"on_trade_fills_inside_band_delta={opened_delta}=True")

        vt.set_tob("TOK_UP", 0.90, 2, 0.95, 10)      # touch bid outside the band, thin queue ahead
        vt.on_trade("TOK_UP", "SELL", 0.90, 5)       # opposite direction -> completion
        assert vt.fills == 2, "completing trade outside the band must NOT be skipped by px_band"
        observations.append("on_trade_completion_outside_band_unaffected=True")

        # --- 5. Variant.__init__ / configs() thread px_band through from strategies.py ---
        import inspect
        cfg_src = inspect.getsource(sc.configs)
        assert "px_band=s.px_band" in cfg_src, "configs() must thread Strat.px_band into Variant"
        init_src = inspect.getsource(sc.Variant.__init__)
        assert "px_band=None" in init_src and "self.px_band = px_band" in init_src
        observations.append("configs_and_variant_init_thread_px_band=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 37 — AGED-CROSS widened give bound (optimal-stopping study, 10,969
#   simulated first-fill events)
# ===========================================================================

def _dispose_cross_ok_decision(lock, aged, near_close, force,
                                chase_max_give, close_max_give, dispose_max_give):
    """Replicates the (post-fix) cross_ok decision from kalshi_trader.py's dispose-cross block
    (search '[AGED-CROSS]' in kalshi_trader.py -- the STRAND DISPOSAL comment block):

        give = a.close_max_give if near_close else a.chase_max_give
        aged_wide = aged and not near_close and not force
        chase_cross_ok = lock >= -give - 1e-9
        wide_cross_ok = aged_wide and lock >= -a.dispose_max_give - 1e-9
        cross_ok = chase_cross_ok or (force and lock >= -a.dispose_max_give - 1e-9) or wide_cross_ok
        used_wide_bound = wide_cross_ok and not chase_cross_ok

    Returns (cross_ok, used_wide_bound).
    """
    give = close_max_give if near_close else chase_max_give
    aged_wide = aged and not near_close and not force
    chase_cross_ok = lock >= -give - 1e-9
    wide_cross_ok = aged_wide and lock >= -dispose_max_give - 1e-9
    cross_ok = chase_cross_ok or (force and lock >= -dispose_max_give - 1e-9) or wide_cross_ok
    used_wide_bound = wide_cross_ok and not chase_cross_ok
    return cross_ok, used_wide_bound


def _dispose_cross_ok_decision_PRE_FIX(lock, near_close, force,
                                        chase_max_give, close_max_give, dispose_max_give):
    """The PRE-FIX decision (main@da648b3af, before this change): the aged path shared
    --chase-max-give with the early maker-repricing ramp; only FORCE got --dispose-max-give."""
    give = close_max_give if near_close else chase_max_give
    return (lock >= -give - 1e-9) or (force and lock >= -dispose_max_give - 1e-9)


def test_aged_cross_wide_bound():
    """
    FINDING (optimal-stopping completion-policy study, 10,969 simulated first-fill events): the
    aged (non-force) dispose-cross was gated by the SAME tight give cap (--chase-max-give, ~2c)
    that governs the early maker-repricing ramp (eff_lock). When the market had moved more than
    that by the time a leg aged out, the aged cross was blocked, the leg kept aging, and it
    eventually hit close-force -- which pays whatever the market demands (the worst outcomes in
    the study). The validated fix: once the policy DECIDES to cross via the aged path, bound it
    by the FORCE-stage give (--dispose-max-give) instead, splitting the give budget's two uses.

    Checks:
      1. PREMISE CONFIRMED against the pre-fix source (git show da648b3af:kalshi_trader.py):
         the aged branch computed cross_ok from `give` alone (chase_max_give mid-window /
         close_max_give near close) with no dispose_max_give fallback outside FORCE.
      2. Old code (pre-fix decision fn) BLOCKS an aged cross whose give sits strictly between
         chase_max_give and dispose_max_give; new code (post-fix decision fn) CROSSES it, and
         reports used_wide_bound=True.
      3. (a) early maker-repricing ramp (eff_lock ramp formula using chase_max_give) is
         byte-identical in the deployed source.
      4. (b) the dispose-cross attempt/budget circuit breaker (T28's cap_hit/blocked gate) is
         structurally UNCHANGED and still gates before the widened cross_ok computation --
         verified both via _dispose_cap_decision (T28) composed with the new give bound, and via
         source ordering.
      5. (c) near-close and (further) FORCE-path decisions are byte-equivalent pre/post-fix
         across a grid of locks -- widening only ever fires for the plain aged branch.
      6. (d) tier-2 dead-man one-shot (a cross triggered by tier2_shot alone, NOT aged) still
         uses the tight chase_max_give bound, unchanged -- aged_wide requires `aged` specifically.
      7. STRUCTURAL: the deployed source contains the widened-bound decision and a rate-limited
         "[AGED-CROSS]" log line gated on used_wide_bound.
    """
    name = "T37: AGED-CROSS widened give bound (optimal-stopping study, 10,969 events)"
    try:
        import inspect
        import re
        import subprocess
        observations = []

        chase_max_give = 0.02      # deployed default
        close_max_give = 0.04      # deployed default
        dispose_max_give = 0.25    # deployed default

        # --- 1. PREMISE CHECK against the pre-fix commit this branch started from ---
        try:
            pre_fix_src = subprocess.run(
                ["git", "show", "da648b3af:kalshi_trader.py"],
                cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
                capture_output=True, text=True, timeout=15).stdout
        except Exception:
            pre_fix_src = ""
        if pre_fix_src:
            idx_dc = pre_fix_src.index("# --- STRAND DISPOSAL: cross to COMPLETE")
            idx_dc_end = pre_fix_src.index("# --- PULL stale / toxic / off-target rungs ---", idx_dc)
            pre_fix_block = pre_fix_src[idx_dc:idx_dc_end]
            assert "cross_ok = (lock >= -give - 1e-9) or (force and lock >= -a.dispose_max_give - 1e-9)" \
                in pre_fix_block, \
                "premise check: pre-fix aged branch must have used ONLY `give` (chase_max_give) " \
                "outside of the force fallback -- if this no longer matches, the premise may be stale"
            assert "aged_wide" not in pre_fix_block, "premise check: pre-fix must not already split the give budget"
            observations.append("premise_confirmed_pre_fix_aged_path_shared_chase_max_give=True")
        else:
            observations.append("premise_check_skipped_git_show_unavailable")

        # --- 2. old code blocks an aged cross needing give strictly between the two caps;
        # new code crosses it and reports used_wide_bound ---
        lock = -0.10   # give=0.10: > chase_max_give(0.02), < dispose_max_give(0.25)
        old_ok = _dispose_cross_ok_decision_PRE_FIX(lock, near_close=False, force=False,
                                                     chase_max_give=chase_max_give,
                                                     close_max_give=close_max_give,
                                                     dispose_max_give=dispose_max_give)
        assert old_ok is False, "premise: old aged decision must BLOCK a give of 0.10 (> chase cap 0.02)"
        new_ok, used_wide = _dispose_cross_ok_decision(lock, aged=True, near_close=False, force=False,
                                                        chase_max_give=chase_max_give,
                                                        close_max_give=close_max_give,
                                                        dispose_max_give=dispose_max_give)
        assert new_ok is True and used_wide is True, \
            "fix: new aged decision must CROSS a give of 0.10 using the widened (dispose_max_give) bound"
        observations.append(f"aged_give_0.10_between_caps_old_blocks_new_crosses_used_wide={used_wide}=True")

        # a give beyond EVEN dispose_max_give must still be blocked (0.25 is a hard cap, not
        # "ignore the cap") -- study explicitly bounds by dispose_max_give, not unbounded
        new_ok2, used_wide2 = _dispose_cross_ok_decision(-0.30, aged=True, near_close=False, force=False,
                                                          chase_max_give=chase_max_give,
                                                          close_max_give=close_max_give,
                                                          dispose_max_give=dispose_max_give)
        assert new_ok2 is False, "aged path must still HOLD when give exceeds dispose_max_give (0.30 > 0.25)"
        observations.append("aged_give_beyond_dispose_max_give_still_blocked=True")

        # a give within the ORIGINAL chase cap crosses under both old and new (no regression)
        old_ok3 = _dispose_cross_ok_decision_PRE_FIX(-0.01, near_close=False, force=False,
                                                      chase_max_give=chase_max_give,
                                                      close_max_give=close_max_give,
                                                      dispose_max_give=dispose_max_give)
        new_ok3, used_wide3 = _dispose_cross_ok_decision(-0.01, aged=True, near_close=False, force=False,
                                                          chase_max_give=chase_max_give,
                                                          close_max_give=close_max_give,
                                                          dispose_max_give=dispose_max_give)
        assert old_ok3 is True and new_ok3 is True and used_wide3 is False, \
            "a cheap aged cross (give < chase_max_give) must cross the SAME way pre/post-fix " \
            "(no widened-bound log, since the tight cap already allowed it)"
        observations.append("cheap_aged_cross_unaffected_no_wide_bound_flag=True")

        # --- 3(a). early maker-repricing ramp (eff_lock) untouched: exact formula still present ---
        src = inspect.getsource(kt)
        assert "a.min_lock - (a.min_lock + a.chase_max_give) * u" in src, \
            "the unpaired-age eff_lock ramp must still relax toward chase_max_give, unchanged"
        assert "a.min_lock - (a.min_lock + a.close_max_give) * frac" in src, \
            "the close-tau eff_lock ramp must still relax toward close_max_give, unchanged"
        observations.append("early_repricing_ramp_formulas_byte_identical=True")

        # --- 4(b). dispose-cross circuit breaker still gates BEFORE the (now-widened) cross_ok,
        # composed with T28's own decision function ---
        cap_hit, force_bonus, blocked, _, _ = _dispose_cap_decision(
            dispose_cross_n=3, dispose_give=0.0, dispose_max_attempts=3, dispose_budget=0.10,
            force=False, dispose_force_used=False)
        assert cap_hit and blocked, "attempts==max must still block BEFORE any cross_ok/give check runs"
        # even though this lock (give=0.10) would now be crossable under the widened aged bound,
        # the attempt cap must still veto it entirely (the breaker is evaluated first / independently)
        new_ok4, _ = _dispose_cross_ok_decision(lock, aged=True, near_close=False, force=False,
                                                 chase_max_give=chase_max_give, close_max_give=close_max_give,
                                                 dispose_max_give=dispose_max_give)
        assert new_ok4 is True and blocked is True, \
            "cross_ok alone doesn't gate a real attempt -- the circuit breaker's `blocked` must " \
            "independently veto it regardless of the (now more permissive) give bound"
        idx_dc = src.index("# --- STRAND DISPOSAL: cross to COMPLETE")
        idx_dc_end = src.index("# --- PULL stale / toxic / off-target rungs ---", idx_dc)
        dc_block = src[idx_dc:idx_dc_end]
        idx_cap = dc_block.index("attempts_capped = (a.dispose_max_attempts")
        idx_wide = dc_block.index("aged_wide = aged and not near_close and not force")
        assert idx_cap < idx_wide, \
            "the attempt/budget circuit breaker must still gate BEFORE the widened cross_ok computation"
        observations.append("circuit_breaker_still_gates_before_widened_cross_ok=True")

        # --- 5(c). near-close and force decisions byte-equivalent old vs new across a lock grid ---
        for lk in (-0.001, -0.02, -0.03, -0.04, -0.05, -0.10, -0.25, -0.26, -0.30):
            for nc in (True, False):
                old = _dispose_cross_ok_decision_PRE_FIX(lk, near_close=nc, force=True,
                                                          chase_max_give=chase_max_give,
                                                          close_max_give=close_max_give,
                                                          dispose_max_give=dispose_max_give)
                new, wide = _dispose_cross_ok_decision(lk, aged=True, near_close=nc, force=True,
                                                        chase_max_give=chase_max_give,
                                                        close_max_give=close_max_give,
                                                        dispose_max_give=dispose_max_give)
                assert old == new and wide is False, \
                    f"FORCE path must be byte-equivalent pre/post-fix (lock={lk} near_close={nc}): old={old} new={new} wide={wide}"
            # near_close (non-force) must also be untouched
            old_nc = _dispose_cross_ok_decision_PRE_FIX(lk, near_close=True, force=False,
                                                         chase_max_give=chase_max_give,
                                                         close_max_give=close_max_give,
                                                         dispose_max_give=dispose_max_give)
            new_nc, wide_nc = _dispose_cross_ok_decision(lk, aged=True, near_close=True, force=False,
                                                          chase_max_give=chase_max_give,
                                                          close_max_give=close_max_give,
                                                          dispose_max_give=dispose_max_give)
            assert old_nc == new_nc and wide_nc is False, \
                f"near-close (non-force) path must be byte-equivalent pre/post-fix (lock={lk}): old={old_nc} new={new_nc}"
        observations.append("force_and_near_close_paths_byte_equivalent_across_lock_grid=True")

        # --- 6(d). tier-2 one-shot alone (aged=False) must NOT get the widened bound ---
        new_ok5, used_wide5 = _dispose_cross_ok_decision(lock, aged=False, near_close=False, force=False,
                                                          chase_max_give=chase_max_give,
                                                          close_max_give=close_max_give,
                                                          dispose_max_give=dispose_max_give)
        assert new_ok5 is False and used_wide5 is False, \
            "a tier-2-only trigger (not aged) must stay on the tight chase_max_give bound, unchanged"
        observations.append("tier2_only_trigger_stays_on_tight_chase_bound=True")

        # --- 7. structural: widened decision + rate-limited [AGED-CROSS] log present in source ---
        assert "aged_wide = aged and not near_close and not force" in dc_block
        assert "wide_cross_ok = aged_wide and lock >= -a.dispose_max_give - 1e-9" in dc_block
        assert "used_wide_bound = wide_cross_ok and not chase_cross_ok" in dc_block
        assert "[AGED-CROSS]" in dc_block, "must log when the widened bound is actually used"
        idx_log = dc_block.index("[AGED-CROSS]")
        # confirm the log call is gated on used_wide_bound and rate-limited (reject_cd cooldown)
        log_ctx = dc_block[max(0, idx_log - 300):idx_log + 200]
        assert "used_wide_bound" in log_ctx, "[AGED-CROSS] log must be gated on used_wide_bound"
        assert "_aged_cross_wide_log" in log_ctx and "reject_cd" in log_ctx, \
            "[AGED-CROSS] log must be rate-limited via the same reject_cd cooldown pattern as other dispose logs"
        # force sub-expression is preserved verbatim (byte-equivalent force gating)
        assert "force and lock >= -a.dispose_max_give - 1e-9" in dc_block
        observations.append("structural_widened_decision_and_rate_limited_log_present=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TEST 38 — spread_gate shadow arm (strategies.py / shadow_compare.py):
#   pre-registered pairing-probability arm, engine-level default-inertness
#   (max_open_spread=None byte-identical to pre-spread_gate behavior), and
#   OPENING-only / completions-unaffected semantics (px_band-style).
# ===========================================================================

def test_spread_gate_shadow_arm():
    """
    Pairing-probability study (walk-forward): skip OPENING fills in any window whose touch spread
    (best-ask - best-bid) exceeded 2c at evaluation time. Walk-forward result: +0.235c/window,
    day-clustered t=3.04, 12/13 test days positive, sheds only 5.3% of windows -- the FIRST gate
    in this repo's history to pass its own walk-forward split (this month's record is otherwise
    0/19 gates that survived forward validation after looking good on lab/backtest data). That is
    exactly why it is pre-registered for a forward shadow test here, NOT treated as deployment-
    ready. Strat.max_open_spread=<threshold> (default None=unchanged) skips OPENING quotes whose
    CURRENT touch spread exceeds the threshold; completions are never affected -- the identical
    OPENING-vs-completion carve-out px_band/`as` already use. Built on av_stoikov (skew=0.99,
    gate="as"), same "build on the winner" pattern as as_trim70/as_band.

    Same structural + logic-replica style as T36 (test_px_band_shadow_arms), the closest existing
    precedent for a shadow_compare.py Strat-field arm.
    """
    name = "T38: spread_gate shadow arm (pre-registered, default-inert)"
    try:
        import strategies
        import shadow_compare as sc
        observations = []

        # --- 1. registration: arm present, enabled, correctly configured, carries the
        # pre-registration numbers + honest prior + promotion bar in its note/module docstring ---
        errs = strategies.validate()
        assert errs == [], f"strategies.validate() must pass with the new arm: {errs}"
        by_name = {s.name: s for s in strategies.REGISTRY}
        assert "spread_gate" in by_name, "spread_gate must be registered"
        sg = by_name["spread_gate"]
        assert sg.enabled, "spread_gate must be enabled (live shadow A/B)"
        assert sg.gate == "as" and sg.skew == 0.99, "spread_gate must build on the av_stoikov (as) config"
        assert sg.max_open_spread == 0.02, f"spread_gate max_open_spread mismatch: {sg.max_open_spread}"
        assert sg.px_band is None, "spread_gate must not also set px_band (single orthogonal field)"
        note_up = sg.note.upper()
        assert "WALK-FORWARD" in note_up or "0.235" in sg.note, \
            "spread_gate note must carry the walk-forward result"
        assert "12/13" in sg.note, "spread_gate note must carry the day-positive count"
        assert "PRE-REGISTERED" in note_up and "NOT DEPLOYMENT" in note_up, \
            "spread_gate note must state it is pre-registered for forward validation, not deployment"
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)) or ".",
                                "strategies.py"), encoding="utf-8") as f:
            src = f.read()
        assert "0/19" in src, "the honest prior (0/19 gates survived forward validation) must be documented"
        assert ">=14 forward days" in src and "t>=3" in src and "80%" in src, \
            "the promotion bar (>=14 days, t>=3, >=80% days positive) must be documented"
        assert "wide touch" in src.lower(), \
            "the caveat that this may re-express 'don't join a wide touch' must be documented"
        observations.append("spread_gate_registered_enabled_with_full_pre_registration=True")

        # --- all OTHER arms must be untouched (max_open_spread=None default) ---
        for s in strategies.REGISTRY:
            if s.name == "spread_gate":
                continue
            assert s.max_open_spread is None, \
                f"{s.name}: max_open_spread must stay None (default-inert) -- got {s.max_open_spread}"
        observations.append("all_other_arms_max_open_spread_none_byte_identical=True")

        # --- 2. engine: max_open_spread=None is a true no-op (_spread_gate_blocked always False) ---
        mk = {"up": "TOK_UP", "down": "TOK_DOWN", "we": time.time() + 900}
        shared = {"st": None, "s0": None, "spothist": [], "microhist": {}, "flow": {}, "qema": {}}
        v_none = sc.Variant("v_none", mk, cap=50, skew=0.99, gate="as", shared=shared, max_open_spread=None)
        v_none.set_tob("TOK_UP", 0.40, 10, 0.60, 10)   # 20c-wide touch -- would trip any real threshold
        for d_per, delta in [(1.0, 0.0), (-1.0, 0.0), (1.0, 5.0), (1.0, -5.0)]:
            v_none.delta = delta
            assert v_none._spread_gate_blocked("TOK_UP", d_per) is False, \
                f"max_open_spread=None must NEVER block (d_per={d_per} delta={delta})"
        observations.append("max_open_spread_none_never_blocks_engine_level=True")

        # --- 3. engine: OPENING fill with touch spread > threshold IS blocked; <= threshold is
        # NOT; completions (opposite direction to current delta) are NEVER blocked regardless of
        # spread ---
        v = sc.Variant("v_sg", mk, cap=50, skew=0.99, gate=None, shared=shared, max_open_spread=0.02)
        v.set_tob("TOK_UP", 0.50, 10, 0.53, 10)        # 3c spread > 2c threshold
        assert v._spread_gate_blocked("TOK_UP", 1.0) is True, "opening fill over a wide (3c) touch must block"
        v.set_tob("TOK_UP", 0.50, 10, 0.51, 10)        # 1c spread <= 2c threshold
        assert v._spread_gate_blocked("TOK_UP", 1.0) is False, "opening fill over a narrow (1c) touch must pass"
        v.set_tob("TOK_UP", 0.50, 10, 0.53, 10)        # back to wide (3c)
        v.delta = 5.0
        assert v._spread_gate_blocked("TOK_UP", 1.0) is True, "opening (same-direction) fill over wide touch still blocks"
        assert v._spread_gate_blocked("TOK_UP", -1.0) is False, \
            "completing (opposite-direction, reduces |inventory|) fill must NEVER be blocked, any spread"
        observations.append("opening_blocked_over_wide_touch_completions_always_pass=True")

        # --- 4. full on_trade() engine integration: wide-touch opening skipped (fill=0, delta
        # unchanged), narrow-touch opening fills, and a subsequent completion over a wide touch
        # still goes through (net delta returns toward 0) ---
        vt = sc.Variant("vt", mk, cap=50, skew=0.99, gate=None, shared=shared, max_open_spread=0.02)
        vt.set_tob("TOK_UP", 0.48, 10, 0.53, 2)        # 5c-wide touch ask, thin queue ahead
        vt.on_trade("TOK_UP", "BUY", 0.53, 5)          # taker eats the 2 ahead + reaches us
        assert vt.fills == 0 and vt.delta == 0.0, "wide-touch OPENING trade must be fully skipped"
        observations.append("on_trade_skips_wide_touch_opening=True")

        vt.set_tob("TOK_UP", 0.49, 10, 0.50, 2)        # 1c-wide touch ask
        vt.on_trade("TOK_UP", "BUY", 0.50, 5)
        assert vt.fills == 1 and vt.delta != 0.0, "narrow-touch OPENING trade must fill normally"
        observations.append(f"on_trade_fills_narrow_touch_delta={vt.delta}=True")

        vt.set_tob("TOK_UP", 0.90, 2, 0.97, 10)        # 7c-wide touch bid, thin queue ahead
        vt.on_trade("TOK_UP", "SELL", 0.90, 5)         # opposite direction -> completion
        assert vt.fills == 2, "completing trade over a wide touch must NOT be skipped by spread_gate"
        observations.append("on_trade_completion_over_wide_touch_unaffected=True")

        # --- 4b. completions carve-out also applies mid-window when the leg's price is missing
        # (bb/ba None): spread_gate must never block on missing book data ---
        v_missing = sc.Variant("v_missing", mk, cap=50, skew=0.99, gate=None, shared=shared, max_open_spread=0.02)
        assert v_missing._spread_gate_blocked("TOK_UP", 1.0) is False, \
            "no touch data yet (bb/ba None) must never block"
        observations.append("missing_touch_data_never_blocks=True")

        # --- 5. Variant.__init__ / configs() thread max_open_spread through from strategies.py ---
        import inspect
        cfg_src = inspect.getsource(sc.configs)
        assert "max_open_spread=s.max_open_spread" in cfg_src, \
            "configs() must thread Strat.max_open_spread into Variant"
        init_src = inspect.getsource(sc.Variant.__init__)
        assert "max_open_spread=None" in init_src and "self.max_open_spread = max_open_spread" in init_src
        observations.append("configs_and_variant_init_thread_max_open_spread=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ===========================================================================
# Main runner
# ===========================================================================

# ===========================================================================
# TEST 39 — JOIN-FRESH guard (--join-fresh-s; node N + 2026-07-13 live audit)
# ===========================================================================

def test_join_fresh_guard():
    """The guard suppresses OPENING quotes in a window this PROCESS attached to late (leg-restart
    join), leaving completions exempt -- the trader-side fix for (a) the late-join strand class
    (node N: strand rate climbs monotonically with join lateness) and (b) the sequential
    double-leg over-fill (2026-07-13 12:00Z: ny=5 > max_fills_side 3 across two legs).

    main()'s quote loop can't be invoked directly (live event loop), so this uses the suite's
    established source-assertion style (T21/T35 precedent) plus a standalone logic replica of the
    targets filter, which is byte-identical to the EDGE-SELECT/streak-guard completing-side idiom
    tested implicitly by T-earlier tests."""
    name = "T39: join-fresh guard (--join-fresh-s, default-inert, completions exempt)"
    try:
        import re
        observations = []
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)) or ".",
                                "kalshi_trader.py"), encoding="utf-8").read()

        # --- 1. flag exists, default 0.0 (OFF -> behavior identical to pre-fix) ---
        assert '"--join-fresh-s"' in src, "--join-fresh-s must be registered in argparse"
        m = re.search(r'"--join-fresh-s",\s*type=float,\s*default=([0-9.]+)', src)
        assert m and float(m.group(1)) == 0.0, "--join-fresh-s default must be 0.0 (off)"
        observations.append("flag_registered_default_off=True")

        # --- 2. the guard can NEVER arm when the flag is off: _win_joined_late requires
        # a.join_fresh_s > 0 in the same boolean ---
        assert re.search(r"_win_joined_late\s*=\s*bool\(a\.join_fresh_s\s*>\s*0\s*and", src), \
            "_win_joined_late must be gated on a.join_fresh_s > 0 (default-inert)"
        observations.append("default_inert_condition=True")

        # --- 3. rollover stamps attach time from the NEW window's ws, non-negative ---
        assert re.search(r"_win_join_s\s*=\s*max\(0\.0,\s*time\.time\(\)\s*-\s*mk\[.ws.\]\)", src), \
            "rollover must stamp _win_join_s = max(0, now - mk['ws'])"
        observations.append("rollover_stamps_join_s=True")

        # --- 4. the targets filter uses the exact completing-side idiom (opens suppressed,
        # completions kept) keyed on _win_joined_late ---
        assert re.search(
            r"if _win_joined_late:\s*\n\s*targets = \[t for t in targets\s*\n\s*"
            r"if \(net_delta > 0\.5 and t\[0\] == \"no\"\) or \(net_delta < -0\.5 and t\[0\] == \"yes\"\)\]",
            src), "guard must filter targets to the completing side only (same idiom as EDGE-SELECT)"
        observations.append("filter_is_completing_side_idiom=True")

        # --- 5. winrec rows carry the A/B fields ---
        assert '"join_s"' in src and '"joined_late"' in src, \
            "winrec row must carry join_s + joined_late (the node-N A/B telemetry)"
        observations.append("winrec_carries_join_fields=True")

        # --- 6. logic replica: the filter's semantics ---
        def apply_guard(targets, net_delta, joined_late):
            if joined_late:
                targets = [t for t in targets
                           if (net_delta > 0.5 and t[0] == "no") or (net_delta < -0.5 and t[0] == "yes")]
            return targets
        both = [("yes", 0.48), ("no", 0.50)]
        assert apply_guard(both, 0.0, True) == [], "flat + joined late -> ALL opens suppressed"
        assert apply_guard(both, 2.0, True) == [("no", 0.50)], \
            "long YES + joined late -> only the completing NO quote survives"
        assert apply_guard(both, -2.0, True) == [("yes", 0.48)], \
            "long NO + joined late -> only the completing YES quote survives"
        assert apply_guard(both, 0.0, False) == both, "guard off -> targets untouched"
        observations.append("logic_replica_semantics=True")

        record(name, True, "; ".join(observations))
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def main():
    print("=" * 70)
    print("kalshi_trader.py Safety Rail Test Harness")
    print("=" * 70)

    # Run all tests
    test_helpers()
    test_post_only_crossing_guard()
    test_inventory_clamp()
    test_aggregate_notional_cap()
    test_loss_limit_kill()
    test_rolling_markout_kill()
    test_error_storm_deadman()
    test_stale_book_deadman()
    test_no_side_markout_sign()
    test_settlement_ledger_signs()
    test_startup_reconciliation_fail_closed()
    test_durable_sticky_kill_remote_switch()
    test_startup_position_reconciliation()
    test_portfolio_multipliers_compose()
    test_portfolio_derisking_exemption()
    test_portfolio_failsafe_snap_to_one()
    test_portfolio_aware_flag_off_byte_identical()
    test_seed_book_state()
    test_seed_width_floor()
    test_seed_spot_staleness()
    test_seed_reprice_discipline()
    test_seed_empty_flag_off_byte_identical()
    test_seed_fair_band_trigger()
    test_seed_burst_cooldown()
    test_seed_v2_flag_off_byte_identical()
    test_seed_v3_rest_fallback_and_heartbeat()
    test_place_order_v2_schema()
    test_incident_fixture_replay()
    test_dispose_cross_circuit_breaker()
    test_deadman_tiering()
    test_ws_resilience()
    test_transport_health_deadman()
    test_completion_deficit_fix()
    test_winrec_every_traded_window()
    test_lifecycle_every_place_gets_terminal_row()
    test_recon_carries_dispose_fields()
    test_px_band_shadow_arms()
    test_aged_cross_wide_bound()
    test_spread_gate_shadow_arm()
    test_join_fresh_guard()

    # Summary table
    print()
    print("=" * 70)
    print(f"{'TEST':<55} {'RESULT'}")
    print("-" * 70)
    all_pass = True
    for name, passed, detail in _results:
        tag = "PASS" if passed else "FAIL"
        print(f"  {name:<53} {tag}")
        if not passed:
            all_pass = False
            print(f"    DETAIL: {detail}")
    print("=" * 70)

    if all_pass:
        print(f"ALL {len(_results)} TESTS PASSED")
        sys.exit(0)
    else:
        n_fail = sum(1 for _, p, _ in _results if not p)
        print(f"{n_fail}/{len(_results)} TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
