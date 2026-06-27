"""test_physio_network.py -- Offline unit tests for the physiologic coupling network.

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
The pure helpers (alignment; sliding-window correlation network; decoupling-event
counter; transfer entropy) are tested against hand-built synthetic series with a
KNOWN expected direction:

  * a tightly-coupled ensemble (high mean connectivity, no decouple events),
  * a decoupling-over-time ensemble (positive connectivity decline + break events),
  * a constructed driver -> follower pair (TE(driver->follower) > TE(follower->driver)),
  * empty / missing inputs -> None / 0 / [].

Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_physio_network -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.physio_network import (
    # Module-level constants
    SPECS, EDGE_ON, GRID_DT_S, MAX_STALE_S, WINDOW_S,
    MIN_SIGNALS, MIN_JOINT_POINTS, TE_NBINS,
    # Pure helpers
    _pearson,
    _align_grid,
    _network_per_window,
    _mean_connectivity,
    _connectivity_decline,
    _decouple_events,
    _weak_edge_frac,
    _tercile_bins,
    _transfer_entropy,
    _mean_te,
    compute_network_features,
)
from vitaldb_aki.features.base import audit_specs, LeakageError


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_audit_passes(self):
        """audit_specs() must not raise (no postop feature)."""
        audit_specs(SPECS)

    def test_no_postop_timing(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop",
                                msg=f"{s.name} has postop timing -- leakage!")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "physnet_available",
                         "First spec must be the availability flag")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in physio_network SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "physnet_available",
            "physnet_n_signals",
            "physnet_mean_connectivity",
            "physnet_connectivity_decline",
            "physnet_decouple_event_rate",
            "physnet_weak_edge_frac",
            "physnet_mean_transfer_entropy",
            "physnet_te_asymmetry",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing physio_network specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 8, "Expected exactly 8 physio_network specs")

    def test_te_features_are_pk(self):
        """Transfer-entropy features are pk-tier (heavier); topology is comprehensive."""
        by_name = {s.name: s for s in SPECS}
        self.assertEqual(by_name["physnet_mean_transfer_entropy"].fset, "pk")
        self.assertEqual(by_name["physnet_te_asymmetry"].fset, "pk")
        for nm in ("physnet_available", "physnet_n_signals",
                   "physnet_mean_connectivity", "physnet_connectivity_decline",
                   "physnet_decouple_event_rate", "physnet_weak_edge_frac"):
            self.assertEqual(by_name[nm].fset, "comprehensive",
                             f"{nm} should be comprehensive (topology)")


# ===========================================================================
# 2. Pearson helper
# ===========================================================================

class TestPearson(unittest.TestCase):
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [2.0, 4.0, 6.0, 8.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [8.0, 6.0, 4.0, 2.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, -1.0, places=6)

    def test_none_when_constant(self):
        self.assertIsNone(_pearson([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]))

    def test_none_when_too_few(self):
        self.assertIsNone(_pearson([1.0], [2.0]))


# ===========================================================================
# 3. _align_grid -- multi-signal alignment, joint points only
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def test_two_aligned_signals_full_grid(self):
        """Two dense signals sampled every 5 s yield a full joint grid."""
        a = [(float(i * 5), float(i)) for i in range(11)]      # 0..50
        b = [(float(i * 5), float(i) * 2) for i in range(11)]
        times, aligned = _align_grid({"A": a, "B": b}, 0.0, 50.0, dt=5.0, max_stale=10.0)
        self.assertEqual(len(times), 11)
        self.assertEqual(len(aligned["A"]), 11)
        self.assertEqual(len(aligned["B"]), 11)
        self.assertEqual(aligned["A"][0], 0.0)
        self.assertEqual(aligned["B"][10], 20.0)

    def test_last_value_hold(self):
        """A sparse signal is held forward within the staleness cap."""
        a = [(0.0, 1.0), (5.0, 2.0), (10.0, 3.0)]
        # B has a sample only at t=0; stale by t=10 (>max_stale=10? exactly 10 is ok)
        b = [(0.0, 100.0)]
        times, aligned = _align_grid({"A": a, "B": b}, 0.0, 10.0, dt=5.0, max_stale=10.0)
        # At t=0 fresh; t=5 age=5 ok; t=10 age=10 == max_stale ok -> all 3 joint
        self.assertEqual(len(times), 3)
        self.assertEqual(aligned["B"], [100.0, 100.0, 100.0])

    def test_stale_drops_joint_point(self):
        """A grid point where one signal is too stale is dropped."""
        a = [(float(i * 5), float(i)) for i in range(5)]   # dense 0..20
        b = [(0.0, 50.0)]                                   # only at t=0
        times, aligned = _align_grid({"A": a, "B": b}, 0.0, 20.0, dt=5.0, max_stale=10.0)
        # B fresh at t=0 (age 0), t=5 (age 5), t=10 (age 10 ok); t=15 age 15 stale,
        # t=20 age 20 stale -> only 3 joint points kept.
        self.assertEqual(len(times), 3)
        self.assertEqual(times, [0.0, 5.0, 10.0])
        self.assertEqual(len(aligned["A"]), 3)

    def test_empty_signals_dict(self):
        times, aligned = _align_grid({}, 0.0, 50.0)
        self.assertEqual(times, [])
        self.assertEqual(aligned, {})

    def test_no_joint_points_when_signal_starts_late(self):
        """If a signal has no sample at/near any grid time, no joint points."""
        a = [(float(i * 5), float(i)) for i in range(5)]   # 0..20
        b = [(1000.0, 1.0)]                                 # far in the future
        times, aligned = _align_grid({"A": a, "B": b}, 0.0, 20.0, dt=5.0, max_stale=10.0)
        self.assertEqual(times, [])
        self.assertEqual(aligned["A"], [])
        self.assertEqual(aligned["B"], [])

    def test_three_signals_intersection(self):
        a = [(float(i * 5), float(i)) for i in range(11)]
        b = [(float(i * 5), float(i)) for i in range(11)]
        c = [(float(i * 5), float(i)) for i in range(11)]
        times, aligned = _align_grid({"A": a, "B": b, "C": c}, 0.0, 50.0, dt=5.0)
        self.assertEqual(len(times), 11)
        self.assertEqual(set(aligned.keys()), {"A", "B", "C"})


# ===========================================================================
# 4. _network_per_window -- sliding (non-overlapping) correlation network
# ===========================================================================

def _ramp(n: int, slope: float = 1.0, start: float = 0.0) -> list[float]:
    return [start + slope * i for i in range(n)]


def _sine(n: int, period: float, phase: float = 0.0, amp: float = 1.0) -> list[float]:
    return [amp * math.sin(2 * math.pi * (i / period) + phase) for i in range(n)]


class TestNetworkPerWindow(unittest.TestCase):
    def test_identical_channels_high_connectivity(self):
        """Two identical channels => |corr| ~ 1 in every window."""
        n = 120
        base = _sine(n, period=20.0)
        chans = {"A": list(base), "B": list(base)}
        nets = _network_per_window(chans, win_pts=24, edge_on=EDGE_ON)
        self.assertGreater(len(nets), 0)
        for net in nets:
            self.assertIn(("A", "B"), net)
            self.assertGreater(net[("A", "B")], 0.99,
                               "Identical channels must give |corr| ~ 1")

    def test_strongly_coupled_high_connectivity(self):
        """B = 2*A + const => perfect correlation each window."""
        n = 96
        a = _sine(n, period=16.0)
        b = [2.0 * v + 5.0 for v in a]
        nets = _network_per_window({"A": a, "B": b}, win_pts=24)
        self.assertGreater(len(nets), 0)
        mc = _mean_connectivity(nets)
        self.assertIsNotNone(mc)
        self.assertGreater(mc, 0.95)

    def test_non_overlapping_window_count(self):
        """96 points / 24 per window => 4 windows (trailing partial dropped)."""
        n = 100  # 4 full windows of 24 = 96, last 4 dropped
        a = _ramp(n)
        b = _ramp(n, slope=2.0)
        nets = _network_per_window({"A": a, "B": b}, win_pts=24)
        self.assertEqual(len(nets), 4)

    def test_empty_when_one_channel(self):
        self.assertEqual(_network_per_window({"A": _ramp(50)}, win_pts=10), [])

    def test_empty_when_too_few_points(self):
        self.assertEqual(_network_per_window({"A": [1.0], "B": [2.0]}, win_pts=10), [])

    def test_constant_channel_omits_edge(self):
        """A constant channel => undefined corr => edge omitted that window."""
        n = 48
        a = [7.0] * n              # constant
        b = _ramp(n)
        nets = _network_per_window({"A": a, "B": b}, win_pts=24)
        self.assertEqual(len(nets), 2)
        for net in nets:
            self.assertNotIn(("A", "B"), net,
                             "Constant channel should yield no defined edge")


# ===========================================================================
# 5. Connectivity decline + decouple events (network disintegration)
# ===========================================================================

class TestNetworkDisintegration(unittest.TestCase):
    def _coupled_ensemble(self, n: int) -> dict[str, list[float]]:
        """A tightly-coupled ensemble: all channels track one driver."""
        driver = _sine(n, period=20.0)
        return {
            "MAP": [v for v in driver],
            "HR": [2.0 * v + 1.0 for v in driver],
            "EtCO2": [0.5 * v + 3.0 for v in driver],
        }

    def _decoupling_ensemble(self, n: int) -> dict[str, list[float]]:
        """Coupled early, then channels drift to independent noise late.

        First half: every channel tracks the driver (high |corr|).
        Second half: channels follow distinct, out-of-phase oscillators so
        their pairwise correlation collapses across windows.
        """
        half = n // 2
        driver = _sine(half, period=20.0)
        a = list(driver)
        b = [2.0 * v for v in driver]
        c = [0.5 * v for v in driver]
        # Late half: distinct periods/phases -> low mutual correlation.
        a += _sine(n - half, period=7.0, phase=0.0)
        b += _sine(n - half, period=11.0, phase=1.3)
        c += _sine(n - half, period=17.0, phase=2.7)
        return {"MAP": a, "HR": b, "EtCO2": c}

    def test_coupled_high_connectivity_no_events(self):
        n = 144
        chans = self._coupled_ensemble(n)
        nets = _network_per_window(chans, win_pts=24)
        mc = _mean_connectivity(nets)
        self.assertIsNotNone(mc)
        self.assertGreater(mc, 0.95, "Tightly-coupled ensemble => high connectivity")
        # No edge should break (all stay strongly on).
        self.assertEqual(_decouple_events(nets, EDGE_ON), 0)
        # Decline should be ~0 (stable network).
        decl = _connectivity_decline(nets)
        self.assertIsNotNone(decl)
        self.assertLess(abs(decl), 0.1, "Stable network => near-zero decline")

    def test_decoupling_positive_decline_and_events(self):
        n = 288
        chans = self._decoupling_ensemble(n)
        nets = _network_per_window(chans, win_pts=24)
        self.assertGreater(len(nets), 5)
        # Connectivity should decline (first third strong, last third weak).
        decl = _connectivity_decline(nets)
        self.assertIsNotNone(decl)
        self.assertGreater(decl, 0.1,
                           "Decoupling-over-time ensemble => positive connectivity decline")
        # At least one edge should break as the network fragments.
        self.assertGreater(_decouple_events(nets, EDGE_ON), 0,
                           "Decoupling ensemble should produce edge break events")
        # Weak-edge fraction should be appreciable (fragmentation).
        wef = _weak_edge_frac(nets, EDGE_ON)
        self.assertIsNotNone(wef)
        self.assertGreater(wef, 0.0)

    def test_decline_none_when_few_windows(self):
        n = 48  # only 2 windows of 24
        chans = self._coupled_ensemble(n)
        nets = _network_per_window(chans, win_pts=24)
        self.assertLess(len(nets), 3)
        self.assertIsNone(_connectivity_decline(nets),
                          "< 3 windows => connectivity_decline must be None")

    def test_decouple_events_empty(self):
        self.assertEqual(_decouple_events([], EDGE_ON), 0)
        self.assertEqual(_decouple_events([{("A", "B"): 0.9}], EDGE_ON), 0)

    def test_decouple_event_counts_only_breaks(self):
        """Edge >=EDGE_ON then <EDGE_ON counts once; recovery does not."""
        nets = [
            {("A", "B"): 0.9},   # on
            {("A", "B"): 0.2},   # break (1 event)
            {("A", "B"): 0.8},   # recover (not counted)
            {("A", "B"): 0.1},   # break (2nd event)
        ]
        self.assertEqual(_decouple_events(nets, EDGE_ON), 2)

    def test_weak_edge_frac_none_when_empty(self):
        self.assertIsNone(_weak_edge_frac([], EDGE_ON))
        self.assertIsNone(_weak_edge_frac([{}, {}], EDGE_ON))

    def test_mean_connectivity_none_when_no_edges(self):
        self.assertIsNone(_mean_connectivity([]))
        self.assertIsNone(_mean_connectivity([{}, {}]))


# ===========================================================================
# 6. Transfer entropy -- terciles + directionality
# ===========================================================================

class TestTercileBins(unittest.TestCase):
    def test_equal_count_bins(self):
        vals = [float(i) for i in range(9)]
        bins = _tercile_bins(vals, nbins=3)
        # 9 values -> 3 each.
        self.assertEqual(bins.count(0), 3)
        self.assertEqual(bins.count(1), 3)
        self.assertEqual(bins.count(2), 3)

    def test_monotone_order(self):
        vals = [10.0, 0.0, 5.0]
        bins = _tercile_bins(vals, nbins=3)
        # smallest -> bin 0, mid -> 1, largest -> 2
        self.assertEqual(bins[1], 0)  # value 0.0
        self.assertEqual(bins[2], 1)  # value 5.0
        self.assertEqual(bins[0], 2)  # value 10.0

    def test_empty(self):
        self.assertEqual(_tercile_bins([], nbins=3), [])


class TestTransferEntropy(unittest.TestCase):
    def _driver_follower(self, n: int) -> tuple[list[float], list[float]]:
        """Driver is random-ish; follower copies the driver one step late.

        follower[t] = driver[t-1] (pure lag-1 copy) => the driver's past
        predicts the follower's future beyond the follower's own past, so
        TE(driver -> follower) should exceed TE(follower -> driver).
        """
        # Deterministic pseudo-random driver (no numpy): a chaotic logistic map.
        x = 0.37
        driver: list[float] = []
        for _ in range(n):
            x = 3.95 * x * (1.0 - x)
            driver.append(x)
        follower = [driver[0]] + driver[:-1]  # follower[t] = driver[t-1]
        return driver, follower

    def test_directionality_driver_gt_follower(self):
        n = 600
        driver, follower = self._driver_follower(n)
        te_df = _transfer_entropy(driver, follower, nbins=3)
        te_fd = _transfer_entropy(follower, driver, nbins=3)
        self.assertIsNotNone(te_df)
        self.assertIsNotNone(te_fd)
        self.assertGreater(te_df, te_fd,
                           "TE(driver->follower) must exceed TE(follower->driver)")

    def test_te_nonnegative(self):
        n = 300
        driver, follower = self._driver_follower(n)
        for x, y in ((driver, follower), (follower, driver)):
            te = _transfer_entropy(x, y, nbins=3)
            self.assertIsNotNone(te)
            self.assertGreaterEqual(te, 0.0)

    def test_independent_series_low_te(self):
        """Two independent chaotic series => small TE both ways."""
        x = 0.11
        a: list[float] = []
        for _ in range(400):
            x = 3.99 * x * (1.0 - x)
            a.append(x)
        y = 0.83
        b: list[float] = []
        for _ in range(400):
            y = 3.91 * y * (1.0 - y)
            b.append(y)
        te = _transfer_entropy(a, b, nbins=3)
        self.assertIsNotNone(te)
        self.assertLess(te, 0.2, "Independent series should have small TE")

    def test_none_when_too_few(self):
        self.assertIsNone(_transfer_entropy([1.0, 2.0], [3.0, 4.0]))


class TestMeanTE(unittest.TestCase):
    def test_asymmetry_positive_for_driver_follower(self):
        """An ensemble containing a driver->follower pair => positive asymmetry."""
        x = 0.42
        driver: list[float] = []
        for _ in range(500):
            x = 3.95 * x * (1.0 - x)
            driver.append(x)
        follower = [driver[0]] + driver[:-1]
        # A third, near-constant-ish slow signal.
        third = [math.sin(i / 30.0) for i in range(500)]
        chans = {"A_driver": driver, "B_follower": follower, "C_slow": third}
        mean_te, asym = _mean_te(chans, nbins=3)
        self.assertIsNotNone(mean_te)
        self.assertIsNotNone(asym)
        self.assertGreaterEqual(mean_te, 0.0)
        self.assertGreater(asym, 0.0, "Driver/follower pair => positive TE asymmetry")

    def test_none_when_single_channel(self):
        mean_te, asym = _mean_te({"A": [1.0, 2.0, 3.0]})
        self.assertIsNone(mean_te)
        self.assertIsNone(asym)


# ===========================================================================
# 7. compute_network_features -- end-to-end on aligned channels
# ===========================================================================

class TestComputeNetworkFeatures(unittest.TestCase):
    def _coupled_aligned(self, n: int) -> dict[str, list[float]]:
        driver = _sine(n, period=20.0)
        return {
            "MAP": [v for v in driver],
            "HR": [2.0 * v + 1.0 for v in driver],
            "EtCO2": [0.5 * v + 3.0 for v in driver],
        }

    def test_available_zero_when_too_few_signals(self):
        aligned = {"MAP": _sine(120, 20.0), "HR": _sine(120, 20.0)}  # only 2
        row = compute_network_features(aligned, 0.0, 600.0)
        self.assertEqual(row["physnet_available"], 0)
        for s in SPECS:
            if s.name != "physnet_available":
                self.assertIsNone(row[s.name],
                                  f"{s.name} must be None when < {MIN_SIGNALS} signals")

    def test_available_zero_when_too_few_points(self):
        n = MIN_JOINT_POINTS - 5
        aligned = self._coupled_aligned(n)
        row = compute_network_features(aligned, 0.0, float(n * GRID_DT_S))
        self.assertEqual(row["physnet_available"], 0)
        self.assertIsNone(row["physnet_mean_connectivity"])

    def test_coupled_ensemble_high_connectivity(self):
        n = 300  # well above MIN_JOINT_POINTS and TE_MIN_POINTS
        aligned = self._coupled_aligned(n)
        t_start, t_end = 0.0, float(n * GRID_DT_S)
        row = compute_network_features(aligned, t_start, t_end)
        self.assertEqual(row["physnet_available"], 1)
        self.assertEqual(row["physnet_n_signals"], 3)
        self.assertIsNotNone(row["physnet_mean_connectivity"])
        self.assertGreater(row["physnet_mean_connectivity"], 0.9,
                           "Coupled ensemble => high mean connectivity")
        # No breaks for a stable coupled network.
        self.assertIsNotNone(row["physnet_decouple_event_rate"])
        self.assertEqual(row["physnet_decouple_event_rate"], 0.0)
        # TE features computed (>= TE_MIN_POINTS).
        self.assertIsNotNone(row["physnet_mean_transfer_entropy"])
        self.assertIsNotNone(row["physnet_te_asymmetry"])

    def test_te_skipped_below_min_points(self):
        """Between MIN_JOINT_POINTS and TE_MIN_POINTS: topology yes, TE None."""
        n = MIN_JOINT_POINTS + 10  # 70 (< TE_MIN_POINTS=100)
        self.assertLess(n, 100)
        aligned = self._coupled_aligned(n)
        row = compute_network_features(aligned, 0.0, float(n * GRID_DT_S))
        self.assertEqual(row["physnet_available"], 1)
        self.assertIsNotNone(row["physnet_mean_connectivity"])
        self.assertIsNone(row["physnet_mean_transfer_entropy"],
                          "TE must be None below TE_MIN_POINTS joint points")
        self.assertIsNone(row["physnet_te_asymmetry"])


# ===========================================================================
# 8. Leakage guard: alignment never extends past t_end (opend)
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    def test_align_grid_never_exceeds_t_end(self):
        """No aligned grid time may exceed t_end (== opend, the cutoff)."""
        a = [(float(i * 5), float(i)) for i in range(40)]   # 0..195
        b = [(float(i * 5), float(i)) for i in range(40)]
        c = [(float(i * 5), float(i)) for i in range(40)]
        t_end = 100.0
        times, _aligned = _align_grid({"A": a, "B": b, "C": c}, 0.0, t_end,
                                      dt=5.0, max_stale=10.0)
        self.assertTrue(times, "expected some joint grid points")
        for g in times:
            self.assertLessEqual(g, t_end,
                                 f"grid time {g} exceeds opend cutoff {t_end} -- leakage!")

    def test_clip_excludes_post_opend(self):
        """Samples after opend are excluded from the gated input (extract path)."""
        from vitaldb_aki.features.physio_network import _clip_to_window
        samples = [(float(i * 5), float(i)) for i in range(40)]  # 0..195
        clipped = _clip_to_window(samples, 0.0, 100.0)
        self.assertTrue(all(t <= 100.0 for t, _ in clipped))
        self.assertFalse(any(t > 100.0 for t, _ in clipped))


# ===========================================================================
# 9. extract() smoke test (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """Smoke test extract() with synthetic cfg / cases / tracks (no network).

    extract() lazy-imports first_available / download_track from
    vitaldb_aki.data.tracks, so we patch at the source module.
    """

    def test_extract_none_row_when_too_few_signals(self):
        """Only one signal available => physnet_available=0, others None."""
        import unittest.mock as mock

        map_track = [(float(i * 5), 80.0 + (i % 3)) for i in range(200)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("ART_MBP" in tn or "NIBP_MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=lambda *a, **k: []):
            from vitaldb_aki.features.physio_network import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 1000.0}}
            result = extract(cfg, cases, ["1"])

        row = result["1"]
        self.assertEqual(row["physnet_available"], 0)
        for s in SPECS:
            if s.name != "physnet_available":
                self.assertIsNone(row[s.name])

    def test_extract_computes_with_three_signals(self):
        """MAP/HR/EtCO2 present and coupled => physnet_available=1, features set."""
        import unittest.mock as mock

        n = 300
        # Three coupled signals on a 5 s grid spanning [0, 1500].
        driver = [math.sin(2 * math.pi * i / 20.0) for i in range(n)]
        map_track = [(float(i * 5), 80.0 + 10.0 * driver[i]) for i in range(n)]
        hr_track = [(float(i * 5), 70.0 + 15.0 * driver[i]) for i in range(n)]
        etco2_track = [(float(i * 5), 35.0 + 5.0 * driver[i]) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("ART_MBP" in tn or "NIBP_MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            if any(tn.endswith("/HR") or tn.endswith("PLETH_HR") for tn in tnames):
                return ("Solar8000/HR", hr_track)
            if any("ETCO2" in tn for tn in tnames):
                return ("Solar8000/ETCO2", etco2_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=lambda *a, **k: []):
            from vitaldb_aki.features.physio_network import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(n * 5)}}
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["physnet_available"], 1)
        self.assertEqual(row["physnet_n_signals"], 3)
        self.assertIsNotNone(row["physnet_mean_connectivity"])
        self.assertGreater(row["physnet_mean_connectivity"], 0.9)

    def test_extract_missing_case(self):
        from vitaldb_aki.features.physio_network import extract
        cfg = {"data": {"cache_dir": "/tmp"}}
        result = extract(cfg, {}, ["nope"])
        self.assertEqual(result["nope"]["physnet_available"], 0)
        for s in SPECS:
            if s.name != "physnet_available":
                self.assertIsNone(result["nope"][s.name])


if __name__ == "__main__":
    unittest.main(verbosity=2)
