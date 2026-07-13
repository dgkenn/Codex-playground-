"""kalshi_exposure_test.py -- Tests for the C8 paired-box exposure fix (cash_at_risk).

Covers the operator-approved risk-true exposure accounting (DECISION_MAP.md node M,
solution A): a paired box (equal YES + NO contracts on the same window's `pos` dict)
settles for exactly $1.00/contract at expiry regardless of outcome, so that portion
of cash spent buying it is a guaranteed return, not risk. The C8 aggregate notional
cap previously counted the FULL cash principal spent (max(-cash, 0.0)) as exposure,
double-counting the paired guarantee. This tests the extracted helper:

    paired_guaranteed = min(total YES contracts, total NO contracts) * 1.00
    cash_at_risk      = max(-cash - paired_guaranteed, 0.0)

No live orders, no real money, no network (mock/inject only), same harness style as
kalshi_safeguards_test.py / kalshi_autosize_test.py. Run: python3 kalshi_exposure_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import math
import sys
import types

# ---------------------------------------------------------------------------
# Minimal stubs so kalshi_trader imports cleanly with no API keys / network
# (identical pattern to kalshi_safeguards_test.py / kalshi_autosize_test.py)
# ---------------------------------------------------------------------------
notify_stub = types.ModuleType("notify")
notify_stub.alert = lambda *a, **kw: None
notify_stub.alert_sync = lambda *a, **kw: None
sys.modules.setdefault("notify", notify_stub)

class _FakeLM:
    def __getattr__(self, name):
        return lambda *a, **kw: None
lm_mod = types.ModuleType("live_metrics")
lm_mod.LiveMetrics = lambda *a, **kw: _FakeLM()
sys.modules.setdefault("live_metrics", lm_mod)

import kalshi_trader as kt

# ---------------------------------------------------------------------------
# Test result tracking (same convention as kalshi_safeguards_test.py)
# ---------------------------------------------------------------------------
_results: list[tuple[str, bool, str]] = []  # (name, passed, detail)

def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}: {detail}")


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ===========================================================================
# TEST 1 -- Flat / no fills: cash_at_risk == max(-cash, 0) unchanged
# ===========================================================================

def test_flat_no_fills():
    print("TEST 1: flat/no-fills -> cash_at_risk == max(-cash, 0) unchanged")
    try:
        cases = [
            (0.0, {}),
            (0.0, None),
            (5.0, {}),          # positive cash (shouldn't happen mid-window, but must be safe)
            (-3.5, {}),         # cash spent but pos empty -> no paired credit, same as naive
        ]
        for cash, pos in cases:
            got = kt.cash_at_risk(cash, pos)
            want = max(-cash, 0.0)
            assert _close(got, want), f"cash={cash} pos={pos}: expected {want}, got {got}"
        record("flat_matches_naive_formula", True,
               f"{len(cases)} flat/empty cases match max(-cash,0.0) exactly")
    except AssertionError as e:
        record("flat_matches_naive_formula", False, str(e))


# ===========================================================================
# TEST 2 -- Exactly-paired boxes: fully-guaranteed principal excluded
# ===========================================================================

def test_exact_paired_boxes():
    print("TEST 2: 3 paired boxes size 2 @ 0.99+0.99=1.98/pair -> cash_at_risk == 0")
    try:
        # 3 boxes, size 2 each side => 6 YES + 6 NO contracts, cost 1.98/pair * 3 = 5.94
        pos = {"TICK:YES": 6.0, "TICK:NO": 6.0}
        cash = -5.94
        got = kt.cash_at_risk(cash, pos)
        assert _close(got, 0.0, tol=1e-9), f"expected 0.0 (paired covers spend), got {got}"
        record("exact_pair_zero_risk", True,
               f"cash={cash} pos(YES=6,NO=6) paired_guaranteed=6.0 -> cash_at_risk={got}")
    except AssertionError as e:
        record("exact_pair_zero_risk", False, str(e))


# ===========================================================================
# TEST 3 -- Overpaid pair: only the overpayment above $1/contract is at risk
# ===========================================================================

def test_overpaid_pair():
    print("TEST 3: overpaid pair cost 2.04/pair x3, cash=-6.12, paired=6.0 -> 0.12")
    try:
        pos = {"TICK:YES": 6.0, "TICK:NO": 6.0}
        cash = -6.12
        got = kt.cash_at_risk(cash, pos)
        assert _close(got, 0.12, tol=1e-6), f"expected 0.12, got {got}"
        record("overpaid_pair_only_overpayment", True,
               f"cash={cash} paired_guaranteed=6.0 -> cash_at_risk={got:.4f} (== overpayment)")
    except AssertionError as e:
        record("overpaid_pair_only_overpayment", False, str(e))


# ===========================================================================
# TEST 4 -- Unpaired leg only: full cost is at risk (no guarantee at all)
# ===========================================================================

def test_unpaired_leg_only():
    print("TEST 4: unpaired leg only (cash=-1.14, paired=0) -> cash_at_risk == 1.14")
    try:
        pos = {"TICK:YES": 2.0}   # no NO contracts at all -> min(2,0) = 0 paired
        cash = -1.14
        got = kt.cash_at_risk(cash, pos)
        assert _close(got, 1.14, tol=1e-9), f"expected 1.14, got {got}"
        record("unpaired_full_risk", True,
               f"pos has no offsetting side -> paired_guaranteed=0 -> cash_at_risk=={got}")
    except AssertionError as e:
        record("unpaired_full_risk", False, str(e))


# ===========================================================================
# TEST 5 -- Mixed: 2 paired boxes + 1 unpaired leg
# ===========================================================================

def test_mixed_paired_and_unpaired():
    print("TEST 5: 2 pairs (overpaid) + 1 unpaired leg -> unpaired cost + pair overpayment only")
    try:
        # 2 pairs @ 1.02/pair (0.51+0.51) = 2.04 total, PLUS one extra unpaired YES @ 0.60
        # pos: YES = 2 (paired) + 1 (unpaired) = 3, NO = 2 (paired)
        pos = {"TICK:YES": 3.0, "TICK:NO": 2.0}
        pair_cost = 2 * 1.02          # 2.04 -- overpayment vs guaranteed $1/pair*2 = $2.00 -> 0.04
        unpaired_cost = 0.60
        cash = -(pair_cost + unpaired_cost)   # -2.64
        paired_guaranteed = min(3.0, 2.0) * 1.0  # = 2.0
        want = max(-cash - paired_guaranteed, 0.0)  # 2.64 - 2.00 = 0.64 = 0.04 overpay + 0.60 unpaired
        got = kt.cash_at_risk(cash, pos)
        assert _close(got, want, tol=1e-9), f"expected {want}, got {got}"
        assert _close(want, 0.64, tol=1e-9), f"sanity: expected 0.64 total, computed want={want}"
        record("mixed_paired_and_unpaired", True,
               f"cash={cash:.2f} paired_guaranteed={paired_guaranteed} -> "
               f"cash_at_risk={got:.4f} (0.04 pair-overpay + 0.60 unpaired)")
    except AssertionError as e:
        record("mixed_paired_and_unpaired", False, str(e))


# ===========================================================================
# TEST 6 -- Pathological inputs: must never raise, always >= 0
# ===========================================================================

def test_pathological_inputs_never_raise():
    print("TEST 6: pathological inputs (positive cash, empty/None pos, garbage) never raise")
    cases = [
        ("positive_cash_empty_pos", 12.5, {}),
        ("positive_cash_none_pos", 12.5, None),
        ("zero_cash_none_pos", 0.0, None),
        ("negative_cash_none_pos", -4.0, None),
        ("cash_none", None, {"TICK:YES": 1.0}),
        ("cash_nan", float("nan"), {"TICK:YES": 1.0, "TICK:NO": 1.0}),
        ("cash_string_garbage", "oops", {"TICK:YES": 1.0}),
        ("pos_not_a_dict", -1.0, ["not", "a", "dict"]),
        ("pos_values_garbage", -1.0, {"TICK:YES": "oops", "TICK:NO": None}),
        ("pos_keys_non_string", -1.0, {1: 5.0, ("tuple", "key"): 3.0}),
        ("pos_negative_counts", -1.0, {"TICK:YES": -5.0, "TICK:NO": -5.0}),
        ("empty_string_side_suffix", -1.0, {"TICK:MAYBE": 5.0}),
    ]
    try:
        for name, cash, pos in cases:
            got = kt.cash_at_risk(cash, pos)
            assert got is not None, f"{name}: returned None"
            assert isinstance(got, (int, float)), f"{name}: expected numeric, got {type(got)}"
            assert not (isinstance(got, float) and math.isnan(got)), f"{name}: returned NaN"
            assert got >= 0.0, f"{name}: expected >= 0, got {got}"
        record("pathological_inputs_safe", True,
               f"{len(cases)} pathological cases -> no raise, always numeric >= 0")
    except AssertionError as e:
        record("pathological_inputs_safe", False, str(e))
    except Exception as e:  # noqa: BLE001 -- the whole point is it must never raise
        record("pathological_inputs_safe", False, f"raised {type(e).__name__}: {e}")


# ===========================================================================
# TEST 7 -- Call-site wiring: all three C8 sites use the helper, none left naive
# ===========================================================================

def test_call_sites_wired():
    print("TEST 7: all three C8 exposure sites call cash_at_risk(cash, pos); none left naive")
    try:
        src = open(kt.__file__.replace(".pyc", ".py")).read()
        n_helper_calls = src.count("+ cash_at_risk(cash, pos)")
        assert n_helper_calls == 3, \
            f"expected exactly 3 call sites wired to cash_at_risk(cash, pos), found {n_helper_calls}"
        # the only remaining 'max(-cash' text must be inside cash_at_risk's own docstring/body
        assert src.count("max(-cash") == 2, \
            "expected exactly 2 'max(-cash' occurrences left (both inside cash_at_risk itself: " \
            "one in the docstring, one in the return statement); any more means an unfixed site"
        record("call_sites_wired", True,
               f"{n_helper_calls}/3 sites call cash_at_risk(cash, pos); no unfixed max(-cash sites")
    except AssertionError as e:
        record("call_sites_wired", False, str(e))


# ===========================================================================

def main():
    print("=" * 70)
    print("kalshi_exposure_test.py -- C8 paired-box exposure fix (cash_at_risk)")
    print("=" * 70)
    test_flat_no_fills()
    test_exact_paired_boxes()
    test_overpaid_pair()
    test_unpaired_leg_only()
    test_mixed_paired_and_unpaired()
    test_pathological_inputs_never_raise()
    test_call_sites_wired()

    # Summary table (same format as kalshi_safeguards_test.py / kalshi_autosize_test.py)
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
