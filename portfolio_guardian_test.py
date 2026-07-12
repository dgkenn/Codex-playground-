"""portfolio_guardian_test.py -- Self-contained test harness for portfolio_guardian.py.

Tests every rule + the durable-kill wiring WITHOUT live orders, real money, or network access
(mock/inject/synthetic-files only). Run: python portfolio_guardian_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile
import types

import unittest.mock as mock

# Stub out 'kalshi_trader' import so this file never depends on the trader module's (heavier)
# dependency surface -- exercises portfolio_guardian's OWN fallback _api/_load_private_key/
# remote_switch_kill implementations directly, same reasoning equity_snap.py's fallback exists for.
sys.modules.pop("kalshi_trader", None)
_orig_import = __builtins__.__import__ if isinstance(__builtins__, dict) else __builtins__.__import__


def _blocking_import(name, *a, **kw):
    if name == "kalshi_trader":
        raise ImportError("kalshi_trader intentionally unavailable for this test run")
    return _orig_import(name, *a, **kw)


with mock.patch("builtins.__import__", side_effect=_blocking_import):
    import portfolio_guardian as pg

# ---------------------------------------------------------------------------
# Test result tracking (mirrors kalshi_safeguards_test.py)
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}: {detail}")


# ===========================================================================
# TEST 1 -- fallback _api/remote_switch_kill are in effect (sanity: the mock worked)
# ===========================================================================

def test_fallback_wiring_active():
    name = "T1: kalshi_trader import blocked -> local fallback impls in use"
    try:
        assert pg._api.__module__ == "portfolio_guardian", \
            f"_api should be the local fallback, got module {pg._api.__module__!r}"
        assert pg.remote_switch_kill.__module__ == "portfolio_guardian", \
            f"remote_switch_kill should be the local fallback, got {pg.remote_switch_kill.__module__!r}"
        record(name, True, "both _api and remote_switch_kill resolved to portfolio_guardian's fallback")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 2 -- DAILY_DD: down >15% vs most recent prior-day snapshot -> CRITICAL
# ===========================================================================

def test_daily_dd_critical():
    name = "T2: DAILY_DD >15% day-over-day -> CRITICAL"
    try:
        rows_by_date = {"2026-07-11": [{"balance_cents": 5000, "ts": 1}]}
        # 20% down from $50.00 -> $40.00
        criticals, warns = pg._evaluate_rules(4000, 0, rows_by_date, "2026-07-12")
        observ = f"criticals={criticals}"
        assert any("DAILY_DD" in c for c in criticals), f"expected a DAILY_DD critical: {observ}"
        record(name, True, observ)
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_daily_dd_below_threshold_no_trip():
    name = "T2b: DAILY_DD <=15% day-over-day -> no trip"
    try:
        rows_by_date = {"2026-07-11": [{"balance_cents": 5000, "ts": 1}]}
        # 10% down from $50.00 -> $45.00 (under the 15% limit)
        criticals, warns = pg._evaluate_rules(4500, 0, rows_by_date, "2026-07-12")
        assert not any("DAILY_DD" in c for c in criticals), f"unexpected DAILY_DD trip: {criticals}"
        record(name, True, f"criticals={criticals}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_daily_dd_no_prior_day_skips():
    name = "T2c: no prior-day snapshot -> DAILY_DD silently skipped (day 1)"
    try:
        rows_by_date = {"2026-07-12": [{"balance_cents": 100, "ts": 1}]}  # only TODAY's own file
        criticals, warns = pg._evaluate_rules(100, 0, rows_by_date, "2026-07-12")
        assert not any("DAILY_DD" in c for c in criticals), f"unexpected DAILY_DD trip: {criticals}"
        record(name, True, "no crash, no trip with only same-day history")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 3 -- TOTAL_DD: down >30% vs max snapshot ever -> CRITICAL
# ===========================================================================

def test_total_dd_critical():
    name = "T3: TOTAL_DD >30% vs all-time high -> CRITICAL"
    try:
        rows_by_date = {
            "2026-07-01": [{"balance_cents": 10000, "ts": 1}],   # all-time high $100
            "2026-07-10": [{"balance_cents": 9000, "ts": 2}],
            "2026-07-11": [{"balance_cents": 8000, "ts": 3}],    # prior-day baseline $80
        }
        # $69 is 13.75% down from prior-day $80 (under the 15% DAILY_DD limit) but 31% down from
        # the all-time high $100 (over the 30% TOTAL_DD limit) -- isolates TOTAL_DD from DAILY_DD.
        criticals, warns = pg._evaluate_rules(6900, 0, rows_by_date, "2026-07-12")
        observ = f"criticals={criticals}"
        assert any("TOTAL_DD" in c for c in criticals), f"expected a TOTAL_DD critical: {observ}"
        assert not any("DAILY_DD" in c for c in criticals), f"DAILY_DD should NOT have tripped: {observ}"
        record(name, True, observ)
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_total_dd_uses_max_across_multiple_rows_per_day():
    name = "T3b: TOTAL_DD max is computed across ALL rows in a file, not just the last"
    try:
        # Intraday cron now writes several rows/day -- the peak can be mid-file, not the last row.
        rows_by_date = {
            "2026-07-12": [
                {"balance_cents": 10000, "ts": 1},
                {"balance_cents": 4000, "ts": 2},   # last row is low, but the peak (10000) counts
            ],
        }
        best = pg._max_balance_ever(rows_by_date)
        assert best == 10000, f"expected max_balance_ever=10000, got {best}"
        record(name, True, f"max_balance_ever={best}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 4 -- EXPOSURE: open notional >50% of balance -> WARN (never CRITICAL, never kills)
# ===========================================================================

def test_exposure_warn_only():
    name = "T4: EXPOSURE >50% of balance -> WARN, not CRITICAL"
    try:
        # balance $50, open notional $30 (60%) -> WARN
        criticals, warns = pg._evaluate_rules(5000, 3000, {}, "2026-07-12")
        assert not criticals, f"EXPOSURE must never produce a CRITICAL: {criticals}"
        assert any("EXPOSURE" in w for w in warns), f"expected an EXPOSURE warn: {warns}"
        record(name, True, f"warns={warns}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_exposure_below_threshold_no_warn():
    name = "T4b: EXPOSURE <=50% -> no warn"
    try:
        criticals, warns = pg._evaluate_rules(5000, 2000, {}, "2026-07-12")  # 40%
        assert not warns, f"unexpected warn: {warns}"
        record(name, True, "no warn at 40% exposure")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_notional_cents_helper():
    name = "T4c: _notional_cents sums |market_exposure| and tolerates junk"
    try:
        positions = [
            {"ticker": "A", "position": 3, "market_exposure": 120},
            {"ticker": "B", "position": -7, "market_exposure": 555},
            {"ticker": "C", "position": 1, "market_exposure": None},   # safe-defaults to 0
            {"ticker": "D", "position": 2, "market_exposure": "garbage"},  # safe-defaults to 0
        ]
        total = pg._notional_cents(positions)
        assert total == 675, f"expected 120+555=675, got {total}"
        record(name, True, f"total={total}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 5 -- balance <= 0 is always CRITICAL regardless of history
# ===========================================================================

def test_zero_balance_critical():
    name = "T5: balance <= $0 -> CRITICAL even with no history"
    try:
        criticals, warns = pg._evaluate_rules(0, 0, {}, "2026-07-12")
        assert any("balance is $0.00" in c for c in criticals), f"expected a balance<=0 critical: {criticals}"
        record(name, True, f"criticals={criticals}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 6 -- synthetic gha_data files on disk: _rows_by_date / _prior_day_baseline round-trip,
# INCLUDING multiple rows per day (the switch from daily -> every-6h cron)
# ===========================================================================

def test_rows_by_date_from_synthetic_files():
    name = "T6: _rows_by_date reads real files, handles multi-row-per-day"
    tmpdir = tempfile.mkdtemp(prefix="pg_test_")
    try:
        with open(os.path.join(tmpdir, "equity_2026-07-10.jsonl"), "w") as fh:
            fh.write(json.dumps({"ts": 1, "balance_cents": 5000}) + "\n")
        with open(os.path.join(tmpdir, "equity_2026-07-11.jsonl"), "w") as fh:
            # THREE rows in one day (the new every-6h cadence) -- last one must win as baseline
            fh.write(json.dumps({"ts": 10, "balance_cents": 4900}) + "\n")
            fh.write(json.dumps({"ts": 11, "balance_cents": 4950}) + "\n")
            fh.write(json.dumps({"ts": 12, "balance_cents": 4800}) + "\n")
            fh.write("\n")  # blank line tolerated
            fh.write("{not json\n")  # corrupt line tolerated

        rows_by_date = pg._rows_by_date(tmpdir)
        assert set(rows_by_date) == {"2026-07-10", "2026-07-11"}, f"got dates {set(rows_by_date)}"
        assert len(rows_by_date["2026-07-11"]) == 3, f"expected 3 valid rows, got {rows_by_date['2026-07-11']}"

        baseline = pg._prior_day_baseline(rows_by_date, "2026-07-12")
        assert baseline["balance_cents"] == 4800, \
            f"baseline must be the LAST row of the most recent prior day, got {baseline}"

        # End-to-end: a 20% overnight drop off that last-row baseline (4800 -> 3840) trips DAILY_DD.
        criticals, _ = pg._evaluate_rules(3840, 0, rows_by_date, "2026-07-12")
        assert any("DAILY_DD" in c for c in criticals), f"expected DAILY_DD trip: {criticals}"

        record(name, True, f"dates={sorted(rows_by_date)}; baseline_balance=4800; end_to_end_trip=True")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ===========================================================================
# TEST 7 -- remote_switch_kill PUT body/sha logic against a mocked contents API (fallback impl)
# ===========================================================================

class _FakeGHResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


def test_remote_switch_kill_put_body_and_sha():
    name = "T7: remote_switch_kill GET-sha then PUT off (mocked contents API)"
    try:
        url = "https://api.github.com/repos/dgkenn/Codex-playground-/contents/LIVE_SWITCH?ref=guardbranch"
        get_calls, put_calls = [], []

        class _OkSess:
            def get(self, u, headers=None, timeout=None):
                get_calls.append((u, headers))
                return _FakeGHResp(200, {"sha": "deadbeef"})

            def put(self, u, headers=None, json=None, timeout=None):
                put_calls.append((u, headers, json))
                return _FakeGHResp(200, {})

        alerted = []
        ok = pg.remote_switch_kill("tok-abc", url, "portfolio_guardian: DAILY_DD trip",
                                   sess=_OkSess(), alert_fn=lambda m: alerted.append(m))
        assert ok is True, "expected True on a clean GET+PUT"
        assert not alerted, "no alert expected on success"
        assert len(get_calls) == 1 and len(put_calls) == 1

        put_url, put_hdrs, put_body = put_calls[0]
        import base64 as _b64
        assert "?" not in put_url, f"PUT url must be the bare contents path: {put_url!r}"
        assert put_body["sha"] == "deadbeef", f"PUT must carry the GET-fetched sha: {put_body!r}"
        assert put_body["branch"] == "guardbranch", f"branch must come from ?ref=: {put_body!r}"
        assert _b64.b64decode(put_body["content"]) == b"off", \
            f"PUT content must decode to literal 'off': {put_body!r}"
        assert put_hdrs["Authorization"] == "Bearer tok-abc"

        record(name, True, "sha/branch/content all correct; no false alert")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_remote_switch_kill_noop_without_token_or_url():
    name = "T7b: remote_switch_kill clean no-op without gh_token/url (zero network calls)"
    try:
        class _AssertNoCalls:
            def get(self, *a, **kw):
                raise AssertionError("must not GET without gh_token/url")

            def put(self, *a, **kw):
                raise AssertionError("must not PUT without gh_token/url")

        r1 = pg.remote_switch_kill(None, "https://api.github.com/x", "reason", sess=_AssertNoCalls())
        r2 = pg.remote_switch_kill("tok", "", "reason", sess=_AssertNoCalls())
        r3 = pg.remote_switch_kill("tok", "https://example.com/not-github", "reason", sess=_AssertNoCalls())
        assert r1 is False and r2 is False and r3 is False
        record(name, True, "all three no-op paths returned False with zero network calls")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_remote_switch_kill_total_failure_alerts():
    name = "T7c: remote_switch_kill exhausts retries -> False + exactly one alert"
    try:
        url = "https://api.github.com/repos/o/r/contents/LIVE_SWITCH?ref=b"

        class _AlwaysFailSess:
            def get(self, u, headers=None, timeout=None):
                return _FakeGHResp(200, {"sha": "s"})

            def put(self, u, headers=None, json=None, timeout=None):
                return _FakeGHResp(409, text="conflict")

        alerts = []
        ok = pg.remote_switch_kill("tok", url, "x", sess=_AlwaysFailSess(), retries=2,
                                   backoff_s=0.001, alert_fn=lambda m: alerts.append(m))
        assert ok is False
        assert len(alerts) == 1, f"expected exactly one alert, got {len(alerts)}"
        assert "FAILED" in alerts[0]
        record(name, True, f"alert={alerts[0][:60]!r}...")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# TEST 8 -- end-to-end: CRITICAL path invokes the durable kill with mocked API + mocked Kalshi
# balance/positions fetch, and never touches the switch on WARN or OK
# ===========================================================================

def test_end_to_end_critical_invokes_kill_and_alert():
    name = "T8: end-to-end main() on a 20% day-over-day drop -> kill invoked, Telegram alert sent"
    tmpdir = tempfile.mkdtemp(prefix="pg_test_e2e_")
    old_cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmpdir, "gha_data"))
        with open(os.path.join(tmpdir, "gha_data", "equity_2026-07-11.jsonl"), "w") as fh:
            fh.write(json.dumps({"ts": 1, "balance_cents": 5000}) + "\n")  # prior day $50.00
        os.chdir(tmpdir)

        pem_path = os.path.join(tmpdir, "dummy.pem")
        with open(pem_path, "w") as fh:
            fh.write("not a real key -- _load_private_key is mocked below, only os.path.exists matters")

        env = {
            "KALSHI_API_KEY_ID": "kid",
            "KALSHI_PRIVATE_KEY_PATH": pem_path,
            "GH_TOKEN": "tok",
            "GITHUB_REPOSITORY": "dgkenn/Codex-playground-",
            "BRANCH": "claude/polymarket-bot-live-ready-vw7ut5",
            "TELEGRAM_BOT_TOKEN": "ttok",
            "TELEGRAM_CHAT_ID": "chat1",
        }

        kill_calls = []
        telegram_msgs = []

        def _fake_kill(gh_token, url, reason, sess=None):
            kill_calls.append((gh_token, url, reason))
            assert "DAILY_DD" in reason, f"reason should name the tripped rule: {reason!r}"
            assert url == ("https://api.github.com/repos/dgkenn/Codex-playground-/contents/"
                            "LIVE_SWITCH?ref=claude/polymarket-bot-live-ready-vw7ut5"), \
                f"url should be constructed from GITHUB_REPOSITORY+BRANCH: {url!r}"
            return True

        def _fake_telegram(msg):
            telegram_msgs.append(msg)
            return True

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(pg, "_load_private_key", return_value=object()), \
             mock.patch.object(pg, "_api", side_effect=[
                 (200, {"balance": 4000}),                                    # $40.00 balance (-20%)
                 (200, {"market_positions": [{"ticker": "X", "position": 1, "market_exposure": 100}]}),
             ]), \
             mock.patch.object(pg, "remote_switch_kill", side_effect=_fake_kill), \
             mock.patch.object(pg, "_telegram_send", side_effect=_fake_telegram):
            rc = pg.main()

        assert rc == 0, f"main() should return 0 even on a CRITICAL trip, got {rc}"
        assert len(kill_calls) == 1, f"expected exactly one kill invocation, got {kill_calls}"
        assert len(telegram_msgs) == 1, f"expected exactly one Telegram alert, got {telegram_msgs}"
        assert "CRITICAL" in telegram_msgs[0] and "./live_switch.sh on" in telegram_msgs[0], \
            f"alert must state why + how to re-arm: {telegram_msgs[0]!r}"

        record(name, True, f"kill_reason={kill_calls[0][2]!r}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_end_to_end_ok_never_calls_kill():
    name = "T8b: end-to-end main() with a healthy account -> kill never invoked, no alert"
    tmpdir = tempfile.mkdtemp(prefix="pg_test_e2e_ok_")
    old_cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmpdir, "gha_data"))
        with open(os.path.join(tmpdir, "gha_data", "equity_2026-07-11.jsonl"), "w") as fh:
            fh.write(json.dumps({"ts": 1, "balance_cents": 5000}) + "\n")
        os.chdir(tmpdir)

        pem_path = os.path.join(tmpdir, "dummy.pem")
        with open(pem_path, "w") as fh:
            fh.write("not a real key -- _load_private_key is mocked below, only os.path.exists matters")

        env = {
            "KALSHI_API_KEY_ID": "kid",
            "KALSHI_PRIVATE_KEY_PATH": pem_path,
        }

        kill_calls = []
        telegram_msgs = []
        api_calls = []

        def _fake_api(*a, **kw):
            api_calls.append((a, kw))
            if len(api_calls) == 1:
                return (200, {"balance": 4900})   # only 2% down -- healthy
            return (200, {"market_positions": []})

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(pg, "_load_private_key", return_value=object()), \
             mock.patch.object(pg, "_api", side_effect=_fake_api), \
             mock.patch.object(pg, "remote_switch_kill", side_effect=lambda *a, **kw: kill_calls.append(a) or True), \
             mock.patch.object(pg, "_telegram_send", side_effect=lambda m: telegram_msgs.append(m) or True):
            rc = pg.main()

        assert rc == 0
        assert len(api_calls) == 2, f"expected balance+positions fetch to actually run, got {api_calls}"
        assert not kill_calls, f"kill must NEVER be invoked on a healthy account: {kill_calls}"
        assert not telegram_msgs, f"no alert expected when OK: {telegram_msgs}"
        record(name, True, "no kill, no alert on healthy account (real path exercised, not a no-op)")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


# ===========================================================================
# TEST 9 -- no secrets -> clean no-op, exit 0, zero network calls
# ===========================================================================

def test_no_secrets_clean_noop():
    name = "T9: missing KALSHI secrets -> clean no-op, exit 0, no network"
    try:
        env_clear = {k: "" for k in ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH")}

        def _assert_not_called(*a, **kw):
            raise AssertionError("_api must not be called with no secrets")

        with mock.patch.dict(os.environ, env_clear, clear=False), \
             mock.patch.object(pg, "_api", side_effect=_assert_not_called):
            rc = pg.main()
        assert rc == 0, f"expected exit 0, got {rc}"
        record(name, True, "no secrets -> exit 0, _api never called")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


def test_never_flips_switch_on():
    name = "T10: static check -- portfolio_guardian.py source never encodes/PUTs literal 'on'"
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_guardian.py")) as fh:
            src = fh.read()
        # The only base64/content-writing call in this file is inside remote_switch_kill's PUT,
        # and it must always encode the literal b"off" -- never a variable, never b"on".
        assert 'base64.b64encode(b"off")' in src, "expected the durable-kill PUT to hardcode b'off'"
        assert 'b64encode(b"on")' not in src and "content\": \"on\"" not in src
        record(name, True, "source only ever encodes literal 'off' for the contents-API PUT")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")


# ===========================================================================
# Runner
# ===========================================================================

def main() -> None:
    test_fallback_wiring_active()
    test_daily_dd_critical()
    test_daily_dd_below_threshold_no_trip()
    test_daily_dd_no_prior_day_skips()
    test_total_dd_critical()
    test_total_dd_uses_max_across_multiple_rows_per_day()
    test_exposure_warn_only()
    test_exposure_below_threshold_no_warn()
    test_notional_cents_helper()
    test_zero_balance_critical()
    test_rows_by_date_from_synthetic_files()
    test_remote_switch_kill_put_body_and_sha()
    test_remote_switch_kill_noop_without_token_or_url()
    test_remote_switch_kill_total_failure_alerts()
    test_end_to_end_critical_invokes_kill_and_alert()
    test_end_to_end_ok_never_calls_kill()
    test_no_secrets_clean_noop()
    test_never_flips_switch_on()

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
