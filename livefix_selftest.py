#!/usr/bin/env python3
"""livefix_selftest.py -- required tests for the three live-path fixes (see FIX_SPEC.md).

Run: python3 livefix_selftest.py
All tests must PASS. Exits nonzero on any failure.

No network, no credentials, no real orders -- everything below is monkeypatched / synthetic. Tests import
directly from the sibling modules in this directory (kalshi_exec, kwx_forward, wx_forecast_model,
wx_forecast_forward) so they exercise the ACTUAL fixed code, not a re-implementation of it.
"""
import io
import json
import os
import sys
import unittest
import unittest.mock as mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO_ROOT = os.path.dirname(HERE)

import kalshi_exec as KE  # noqa: E402


# =====================================================================================
# FIX 1 -- kalshi_exec.py: v2 order endpoint, single-book side translation, fill parsing
# =====================================================================================
class TestV2OrderBody(unittest.TestCase):
    """v2 wire-body shape: strings, single-book side translation, required fields, forbidden legacy keys."""

    def _ex(self):
        # fetch_book=False -> no network in the dry-run path; irrelevant here since we call
        # _submit_guarded directly (bypassing buy_yes/buy_no's higher-level dry-run branch).
        return KE.KalshiExec(fetch_book=False)

    def test_buy_yes_52c_body(self):
        ex = self._ex()
        captured = {}

        def fake_post_order(v2_order):
            captured.update(v2_order)
            return {"order_id": "o1", "fill_count": "0", "remaining_count": "1", "ts_ms": 1}

        with mock.patch.object(ex, "_post_order", side_effect=fake_post_order), \
             mock.patch.object(ex, "_headers", return_value={}):
            ex._submit_guarded("KXHIGHNY-26JUL17-T90", "yes", 1, 52, "cid-1")

        self.assertEqual(captured["side"], "bid")
        self.assertEqual(captured["price"], "0.5200")
        self.assertIsInstance(captured["count"], str)
        self.assertIsInstance(captured["price"], str)
        self.assertIn("self_trade_prevention_type", captured)
        for forbidden in ("action", "type", "yes_price", "no_price"):
            self.assertNotIn(forbidden, captured, f"v2 body must not contain legacy key {forbidden!r}")

    def test_buy_no_52c_body(self):
        ex = self._ex()
        captured = {}

        def fake_post_order(v2_order):
            captured.update(v2_order)
            return {"order_id": "o1", "fill_count": "0", "remaining_count": "1", "ts_ms": 1}

        with mock.patch.object(ex, "_post_order", side_effect=fake_post_order), \
             mock.patch.object(ex, "_headers", return_value={}):
            ex._submit_guarded("KXHIGHNY-26JUL17-T90", "no", 1, 52, "cid-2")

        self.assertEqual(captured["side"], "ask")
        self.assertEqual(captured["price"], "0.4800")
        self.assertIsInstance(captured["count"], str)
        self.assertIsInstance(captured["price"], str)
        self.assertIn("self_trade_prevention_type", captured)
        for forbidden in ("action", "type", "yes_price", "no_price"):
            self.assertNotIn(forbidden, captured, f"v2 body must not contain legacy key {forbidden!r}")

    def test_refuses_out_of_range_translated_price(self):
        ex = self._ex()
        # buy YES at 0c would translate to price 0.00 -- outside the open interval (0,1)
        with self.assertRaises(ValueError):
            ex._translate_side_price("yes", 0)
        # buy NO at 100c -> translated price (100-100)/100 = 0.00 -- also out of range
        with self.assertRaises(ValueError):
            ex._translate_side_price("no", 100)
        # sane values are fine
        side, price = ex._translate_side_price("yes", 52)
        self.assertEqual((side, price), ("bid", 0.52))
        side, price = ex._translate_side_price("no", 52)
        self.assertEqual((side, price), ("ask", 0.48))


class TestSigningPathAndURL(unittest.TestCase):
    def test_post_order_uses_new_path_and_order_base(self):
        ex = KE.KalshiExec(fetch_book=False)
        seen = {}

        def fake_get(url, timeout=10, method="POST", data=None, headers=None):
            seen["url"] = url
            seen["headers"] = headers
            return {"order_id": "o1", "fill_count": "0", "remaining_count": "1", "ts_ms": 1}

        seen_headers_call = {}

        def fake_headers(method, path):
            seen_headers_call["method"] = method
            seen_headers_call["path"] = path
            return {"X": "1"}

        with mock.patch.object(KE, "_get", side_effect=fake_get), \
             mock.patch.object(ex, "_headers", side_effect=fake_headers):
            ex._post_order({"ticker": "T", "side": "bid", "count": "1", "price": "0.5000",
                             "time_in_force": "immediate_or_cancel",
                             "self_trade_prevention_type": "taker_at_cross",
                             "client_order_id": "cid"})

        self.assertEqual(seen_headers_call["path"], "/trade-api/v2/portfolio/events/orders")
        self.assertEqual(seen_headers_call["method"], "POST")
        # EXACT url -- `startswith(ORDER_BASE) + "in"` is too weak: it also passes for the duplicated
        # .../trade-api/v2/trade-api/v2/portfolio/events/orders that ORDER_BASE + path produces (404,
        # and the POSTed path then differs from the signed path). Assert the whole string.
        self.assertEqual(seen["url"],
                         "https://external-api.kalshi.com/trade-api/v2/portfolio/events/orders")
        # the POSTed path must be byte-identical to the path handed to the signer
        self.assertTrue(seen["url"].endswith(seen_headers_call["path"]))
        self.assertEqual(seen["url"].count("/trade-api/v2"), 1)
        # order host must be external-api.kalshi.com by default, NOT the public-read KBASE host
        self.assertIn("external-api.kalshi.com", KE.ORDER_BASE)
        self.assertNotIn("api.elections.kalshi.com", seen["url"])

    def test_order_url_correct_under_env_override_with_and_without_prefix(self):
        """KALSHI_ORDER_BASE is operator-settable; neither form may duplicate or drop the path prefix."""
        for base in ("https://external-api.kalshi.com/trade-api/v2",
                     "https://external-api.kalshi.com/trade-api/v2/",
                     "https://external-api.kalshi.com"):
            ex = KE.KalshiExec(fetch_book=False)
            seen = {}
            with mock.patch.object(KE, "ORDER_BASE", base), \
                 mock.patch.object(KE, "_get",
                                   side_effect=lambda url, **kw: seen.update(url=url) or {"fill_count": "0"}), \
                 mock.patch.object(ex, "_headers", side_effect=lambda m, p: seen.update(path=p) or {}):
                ex._post_order({"ticker": "T", "side": "bid"})
            self.assertEqual(seen["url"],
                             "https://external-api.kalshi.com/trade-api/v2/portfolio/events/orders",
                             f"ORDER_BASE={base!r}")
            self.assertTrue(seen["url"].endswith(seen["path"]))


class TestFillParse(unittest.TestCase):
    def test_no_buy_fill_vwap_side_translated(self):
        # fill_count="1", average_fill_price="0.4800" (a YES price) on a NO buy (v2 side "ask")
        # -> filled=1, fill_vwap_c = round((1-0.48)*100) = 52
        resp = {"order_id": "o1", "fill_count": "1", "remaining_count": "0", "ts_ms": 1,
                "average_fill_price": "0.4800", "average_fee_paid": "0.0200"}
        filled, fill_vwap_c, _status = KE.KalshiExec._parse_fill(resp, "ask")
        self.assertEqual(filled, 1)
        self.assertEqual(fill_vwap_c, 52)

    def test_yes_buy_fill_vwap_untranslated(self):
        resp = {"order_id": "o1", "fill_count": "1", "remaining_count": "0", "ts_ms": 1,
                "average_fill_price": "0.5200"}
        filled, fill_vwap_c, _status = KE.KalshiExec._parse_fill(resp, "bid")
        self.assertEqual(filled, 1)
        self.assertEqual(fill_vwap_c, 52)

    def test_zero_fill_no_vwap(self):
        resp = {"order_id": "o1", "fill_count": "0", "remaining_count": "1", "ts_ms": 1}
        filled, fill_vwap_c, _status = KE.KalshiExec._parse_fill(resp, "bid")
        self.assertEqual(filled, 0)
        self.assertIsNone(fill_vwap_c)


class TestSafetyProperties(unittest.TestCase):
    def test_dry_run_never_posts(self):
        ex = KE.KalshiExec(fetch_book=False)
        self.assertFalse(ex.live)
        with mock.patch.object(ex, "_post_order") as post:
            r = ex.buy_yes("KXHIGHNY-26JUL17-T90", count=1, max_price_cents=52, dry_fill_price=50)
        post.assert_not_called()
        self.assertEqual(r["status"], "DRY_RUN")

    def test_halt_file_blocks_submit_guarded(self):
        ex = KE.KalshiExec(fetch_book=False)
        halt_path = KE.HALT_FILE
        pre_existing = os.path.exists(halt_path)
        if not pre_existing:
            open(halt_path, "w").close()
        try:
            with mock.patch.object(ex, "_post_order") as post:
                with self.assertRaises(KE._GuardBlocked):
                    ex._submit_guarded("KXHIGHNY-26JUL17-T90", "yes", 1, 52, "cid")
            post.assert_not_called()
        finally:
            if not pre_existing and os.path.exists(halt_path):
                os.remove(halt_path)

    def test_guard_runs_before_post(self):
        ex = KE.KalshiExec(fetch_book=False)
        # oversized count must be blocked before any network call is attempted
        with mock.patch.object(ex, "_post_order") as post:
            with self.assertRaises(KE._GuardBlocked):
                ex._submit_guarded("T", "yes", KE.HARD_MAX_CONTRACTS + 1, 52, "cid")
        post.assert_not_called()


# =====================================================================================
# FIX 2 -- kwx_forward.py: phantom-win scoring
# =====================================================================================
class TestPhantomWinScoring(unittest.TestCase):
    def setUp(self):
        import kwx_forward as F
        self.F = F

    def test_filled_none_not_scored(self):
        # filled=None with a FILL-capable status (not itself a known non-fill status) -> classified as
        # zero_fill (the "not a number" bucket). A live_error record is covered separately below and is
        # classified by its status (non_fill_status), since status is the more informative signal there.
        ok, reason = self.F._is_scoreable({"status": "DRY_RUN", "filled": None})
        self.assertFalse(ok)
        self.assertEqual(reason, "zero_fill")

    def test_rejected_record_filled_none_not_scored(self):
        # THE bug case: a rejected order (status="live_error", filled=None). Old code's
        # `if p.get("filled") == 0` let this slip through (None == 0 is False in Python) and it was then
        # scored as a WIN. Must be rejected here regardless of the reason bucket.
        ok, reason = self.F._is_scoreable({"status": "live_error", "filled": None})
        self.assertFalse(ok)

    def test_filled_zero_not_scored(self):
        ok, reason = self.F._is_scoreable({"status": "DRY_RUN", "filled": 0})
        self.assertFalse(ok)
        self.assertEqual(reason, "zero_fill")

    def test_status_live_error_not_scored(self):
        ok, reason = self.F._is_scoreable({"status": "live_error", "filled": 1})
        self.assertFalse(ok)
        self.assertEqual(reason, "non_fill_status")

    def test_status_blocked_not_scored(self):
        ok, reason = self.F._is_scoreable({"status": "BLOCKED_HALT", "filled": None})
        self.assertFalse(ok)

    def test_filled_1_with_vwap_is_scoreable(self):
        ok, reason = self.F._is_scoreable({"status": "DRY_RUN", "filled": 1, "fill_vwap_c": 52})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_end_to_end_settle_win_and_loss(self):
        """Full settle() pass: one real WIN, one real LOSS, one rejection, one zero-fill -- only the two
        real fills reach SETTLED, scored correctly both directions."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_log = os.path.join(td, "plan.jsonl")
            settled_log = os.path.join(td, "settled.jsonl")
            plans = [
                {"ticker": "WIN-TICK", "side": "no", "status": "DRY_RUN", "filled": 1,
                 "fill_vwap_c": 52, "cap_c": 52, "requested": 1},
                {"ticker": "LOSS-TICK", "side": "yes", "status": "DRY_RUN", "filled": 1,
                 "fill_vwap_c": 60, "cap_c": 60, "requested": 1},
                {"ticker": "REJECTED-TICK", "side": "no", "status": "live_error", "filled": None,
                 "fill_vwap_c": None, "cap_c": 97, "requested": 1},
                {"ticker": "EMPTYBOOK-TICK", "side": "yes", "status": "DRY_RUN", "filled": 0,
                 "fill_vwap_c": None, "cap_c": 90, "requested": 1},
            ]
            with open(plan_log, "w") as f:
                for p in plans:
                    f.write(json.dumps(p) + "\n")

            markets = {
                "WIN-TICK": {"status": "settled", "result": "no"},     # bought NO, NO won -> WIN
                "LOSS-TICK": {"status": "settled", "result": "no"},    # bought YES, NO won -> LOSS
            }

            def fake_get(url, to=20):
                for tk, m in markets.items():
                    if tk in url:
                        return {"market": m}
                raise AssertionError(f"unexpected market fetch: {url}")

            with mock.patch.object(self.F, "PLAN_LOG", plan_log), \
                 mock.patch.object(self.F, "SETTLED", settled_log), \
                 mock.patch.object(self.F, "_get", side_effect=fake_get):
                n_new, n_zero_fill, n_unfilled = self.F.settle()

            self.assertEqual(n_new, 2)
            self.assertEqual(n_zero_fill, 1)     # EMPTYBOOK-TICK
            self.assertEqual(n_unfilled, 1)      # REJECTED-TICK
            settled = self.F._load_jsonl(settled_log)
            self.assertEqual(len(settled), 2)
            by_tk = {r["ticker"]: r for r in settled}
            self.assertTrue(by_tk["WIN-TICK"]["won"])
            self.assertAlmostEqual(by_tk["WIN-TICK"]["pnl"], 1.0 - 0.52 - self.F._kalshi_fee(0.52))
            self.assertFalse(by_tk["LOSS-TICK"]["won"])
            self.assertAlmostEqual(by_tk["LOSS-TICK"]["pnl"], -0.60 - self.F._kalshi_fee(0.60))

    def test_fill_vwap_none_skips_rather_than_cap_c_fallback(self):
        """A record that somehow reaches the scoring stage with filled>0 but fill_vwap_c=None must be
        skipped, NOT priced at cap_c (cap_c is a requested cap, never an achieved price)."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_log = os.path.join(td, "plan.jsonl")
            settled_log = os.path.join(td, "settled.jsonl")
            # status/filled pass _is_scoreable (filled=1, status=DRY_RUN) but fill_vwap_c is missing --
            # simulates a bug elsewhere (or a legacy record) reaching settle() without a real vwap.
            plan = {"ticker": "NOVWAP-TICK", "side": "yes", "status": "DRY_RUN", "filled": 1,
                    "fill_vwap_c": None, "cap_c": 90, "requested": 1}
            with open(plan_log, "w") as f:
                f.write(json.dumps(plan) + "\n")

            def fake_get(url, to=20):
                return {"market": {"status": "settled", "result": "yes"}}

            with mock.patch.object(self.F, "PLAN_LOG", plan_log), \
                 mock.patch.object(self.F, "SETTLED", settled_log), \
                 mock.patch.object(self.F, "_get", side_effect=fake_get):
                n_new, n_zero_fill, n_unfilled = self.F.settle()

            self.assertEqual(n_new, 0)
            self.assertEqual(n_unfilled, 1)
            self.assertEqual(len(self.F._load_jsonl(settled_log)), 0)

    def test_the_two_real_rejected_records_score_zero(self):
        """The exact two real rejected records from venue_expansion/paper2/kwx_forward_settled.jsonl (as
        they would have appeared in the PLAN log before the phantom-win bug scored them) must produce
        ZERO scored fires under the fixed settle()."""
        # EMBEDDED, not read from disk. These are the two production records verbatim from the live
        # branch's kwx_forward_settled.jsonl (2026-07-30) -- the ones the phantom-win bug scored as
        # +0.46 and +0.02 wins off ZERO fills. They are inlined so this regression travels with the
        # test file across branches: venue_expansion/ exists only on the research branch, and a
        # fixture-path miss would silently downgrade the single most important test here to a skip.
        real_rows = [
            {"ticker": "KXLOWTSEA-26JUL29-T57", "side": "no", "cap_c": 52, "extreme_f": 55.94,
             "station": "KSEA", "kind": "min", "status": "live_error", "trigger": "obs-poll",
             "requested": 1, "filled": None, "fill_vwap_c": None, "ts": 1785398323197,
             "result": "no", "won": True, "entry": 0.52, "fee": 0.02, "pnl": 0.46},
            {"ticker": "KXLOWTSFO-26JUL30-T59", "side": "no", "cap_c": 97, "extreme_f": 57.2,
             "station": "KSFO", "kind": "min", "status": "live_error", "trigger": "obs-poll",
             "requested": 1, "filled": None, "fill_vwap_c": None, "ts": 1785401954125,
             "result": "no", "won": True, "entry": 0.97, "fee": 0.01, "pnl": 0.02},
        ]
        self.assertEqual(len(real_rows), 2, "expected exactly the two known real rejected records")
        # cross-check against the on-disk copy when this runs on a branch that carries it
        disk = os.path.join(REPO_ROOT, "venue_expansion", "paper2", "kwx_forward_settled.jsonl")
        if os.path.exists(disk):
            on_disk = self.F._load_jsonl(disk)
            self.assertEqual([r["ticker"] for r in on_disk], [r["ticker"] for r in real_rows],
                             "embedded fixture has drifted from the on-disk production records")

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_log = os.path.join(td, "plan.jsonl")
            settled_log = os.path.join(td, "settled.jsonl")
            with open(plan_log, "w") as f:
                for r in real_rows:
                    # reconstruct the PRE-settle plan record: strip the fields settle() itself adds
                    # (result/won/entry/fee/pnl) -- these are exactly the fields kwx_runner.fire_one logs.
                    plan = {k: v for k, v in r.items()
                            if k not in ("result", "won", "entry", "fee", "pnl")}
                    f.write(json.dumps(plan) + "\n")
                    # sanity: both real records are exactly the null-fill/live_error shape the bug hit
                    self.assertIsNone(r.get("filled"))
                    self.assertEqual(r.get("status"), "live_error")

            def fake_get(url, to=20):
                raise AssertionError("settle() must not even hit the network for a non-scoreable record")

            with mock.patch.object(self.F, "PLAN_LOG", plan_log), \
                 mock.patch.object(self.F, "SETTLED", settled_log), \
                 mock.patch.object(self.F, "_get", side_effect=fake_get):
                n_new, n_zero_fill, n_unfilled = self.F.settle()

            self.assertEqual(n_new, 0, "the two real rejected records must produce ZERO scored fires")
            self.assertEqual(n_unfilled, 2)
            self.assertEqual(len(self.F._load_jsonl(settled_log)), 0)


class TestPaperGateSamePattern(unittest.TestCase):
    """kwx_paper_gate.py must not re-introduce the phantom-win pattern, and must surface the same
    zero-fill/unfilled counters kwx_forward.py does (FIX 2, 'check kwx_paper_gate.py ... fix identically
    if present')."""

    def test_report_metrics_surfaces_tally_when_nothing_settled(self):
        import tempfile
        import kwx_paper_gate as G
        import kwx_forward as F
        with tempfile.TemporaryDirectory() as td:
            plan_log = os.path.join(td, "plan.jsonl")
            settled_log = os.path.join(td, "settled.jsonl")
            with open(plan_log, "w") as f:
                f.write(json.dumps({"ticker": "A", "side": "no", "status": "live_error",
                                     "filled": None}) + "\n")
                f.write(json.dumps({"ticker": "B", "side": "yes", "status": "DRY_RUN",
                                     "filled": 0}) + "\n")
            open(settled_log, "w").close()
            with mock.patch.object(F, "PLAN_LOG", plan_log), \
                 mock.patch.object(F, "SETTLED", settled_log):
                m = G._report_metrics()
        self.assertIsNotNone(m)
        self.assertEqual(m["n_unfilled"], 1)
        self.assertEqual(m["n_zero_fill"], 1)
        self.assertNotIn("win", m)   # nothing settled -> no fabricated win rate


# =====================================================================================
# FIX 3 -- bracket floor off-by-one, derived from data
# =====================================================================================
class TestBracketConvention(unittest.TestCase):
    def setUp(self):
        import wx_forecast_forward as WF
        import wx_forecast_model as WM
        self.WF = WF
        self.WM = WM

    def test_known_case_lo81_hi82_realized81_is_yes(self):
        # the exact known case from FIX_SPEC.md: lo=81, hi=82, realized=81 -> YES (inclusive floor)
        self.assertTrue(self.WF._bracket_won(81, 82, 81))
        self.assertFalse(self.WF._bracket_won(81, 82, 83))
        self.assertTrue(self.WF._bracket_won(81, 82, 82))

    def test_top_rung_unchanged_exclusive_floor(self):
        self.assertFalse(self.WF._bracket_won(80, None, 80))
        self.assertTrue(self.WF._bracket_won(80, None, 81))

    def test_cap_only_exclusive_cap(self):
        self.assertFalse(self.WF._bracket_won(None, 80, 80))
        self.assertTrue(self.WF._bracket_won(None, 80, 79))

    def test_bracket_prob_adjacent_rungs_no_gap_no_overlap(self):
        # two adjacent full brackets [97,98] and [99,100] plus the top rung floor=100 (cap=None):
        # their continuous half-degree-corrected intervals must exactly tile with no gap/overlap.
        mu, sigma = 98.5, 2.0
        p1 = self.WM.bracket_prob(97, 98, mu, sigma)
        p2 = self.WM.bracket_prob(99, 100, mu, sigma)
        p_top = self.WM.bracket_prob(100, None, mu, sigma)
        from scipy.stats import norm
        # p1+p2 should equal cdf(98.5)-cdf(96.5) exactly (tiled, no gap/overlap)
        expected = norm.cdf(100.5, mu, sigma) - norm.cdf(96.5, mu, sigma)
        self.assertAlmostEqual(p1 + p2, expected, places=9)
        # the cap-only-equivalent top rung starting where the ladder ends should sum to 1 with everything
        # below it (sanity: mass below 96.5 + p1 + p2 + p_top == 1)
        below = norm.cdf(96.5, mu, sigma)
        self.assertAlmostEqual(below + p1 + p2 + p_top, 1.0, places=9)

    def test_bracket_prob_matches_derived_discrete_rule_direction(self):
        # inclusive-floor full bracket should assign MORE mass than the old exclusive-floor version would
        # have, when mu sits right at the floor (this is exactly the case the old code under-priced).
        mu, sigma = 81.0, 1.2
        p_new = self.WM.bracket_prob(81, 82, mu, sigma)
        # old (exclusive floor) equivalent: cdf(82)-cdf(81), no continuity correction
        from scipy.stats import norm
        p_old_style = norm.cdf(82, mu, sigma) - norm.cdf(81, mu, sigma)
        self.assertGreater(p_new, p_old_style)


class TestBracketDisagreementRateDerivation(unittest.TestCase):
    """Reproduces the derivation from FIX_SPEC.md against the real 616-row sample: per-shape candidate
    table, and the post-fix overall disagreement rate."""

    @classmethod
    def setUpClass(cls):
        settled_path = os.path.join(REPO_ROOT, "venue_expansion", "paper2", "wx_forecast_settled.jsonl")
        official_path = os.path.join(REPO_ROOT, "venue_expansion", "cache", "official_results.json")
        cls.have_data = os.path.exists(settled_path) and os.path.exists(official_path)
        if not cls.have_data:
            return
        with open(settled_path) as f:
            cls.rows = [json.loads(l) for l in f]
        with open(official_path) as f:
            cls.official = json.load(f)

    def _official_yes(self, ticker):
        o = self.official.get(ticker)
        if not o or o.get("result") not in ("yes", "no"):
            return None
        return o["result"] == "yes"

    def test_row_count(self):
        if not self.have_data:
            self.skipTest("evidence files not present in this checkout")
        self.assertEqual(len(self.rows), 616)

    def test_post_fix_disagreement_drops_from_21_9_to_near_7_percent(self):
        if not self.have_data:
            self.skipTest("evidence files not present in this checkout")
        import wx_forecast_forward as WF

        def old_bracket_won(lo, hi, x):
            if lo is not None and not (x > lo):
                return False
            if hi is not None and not (x <= hi):
                return False
            return True

        n = dis_old = dis_new = 0
        for r in self.rows:
            oy = self._official_yes(r["ticker"])
            if oy is None:
                continue
            n += 1
            if old_bracket_won(r["lo"], r["hi"], r["realized"]) != oy:
                dis_old += 1
            if WF._bracket_won(r["lo"], r["hi"], r["realized"]) != oy:
                dis_new += 1
        self.assertEqual(n, 616)
        old_rate = dis_old / n
        new_rate = dis_new / n
        # matches FORWARD_DATA_2026-08-02.md's measured 21.9% (135/616) under the OLD convention
        self.assertEqual(dis_old, 135)
        self.assertAlmostEqual(old_rate, 0.2192, places=3)
        # fixed convention: measured 43/616 = 7.0% (residual is dated IEM-lag noise, not boundary error --
        # see wx_forecast_forward._bracket_won docstring); assert it dropped sharply and is well under old.
        self.assertLess(new_rate, 0.08)
        self.assertLess(new_rate, old_rate / 2)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
